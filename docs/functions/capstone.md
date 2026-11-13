---
title: 第 037 讲 · 阶段综合：缓存装饰器库与插件注册表
description: 交付一个可发布的抽象工具集
---

<StageHeader stage='L3 · 函数与抽象' level='★★★☆☆' time='45 分钟' goal='交付一个可发布的抽象工具集' prereq='第 036 讲 · 类型注解、typing 与渐进式类型' />

# 第 037 讲 · 阶段综合：缓存装饰器库与插件注册表

参数、闭包、装饰器、模块、注解一路走来，是时候放进同一个小项目收一收。作为阶段综合，这一讲不添新语法，只检验那些抽象经不经得起并发、测试和扩展。团队想发一个内部工具库，给任意函数加带时限的缓存、留一个插件登记表；第一版用全局字典，压测时同一个冷键被算了好几遍，异常也被当成结果存下。

先把 TTL 缓存做扎实——单调时钟、加锁、异常不入库、留出统计；再把注册表从裸字典改成显式接口，让第三方通过入口点接进来；最后用假时钟和并发用例把单元测试补齐。要用到整个阶段的装饰器、functools、模块与注解，外加异常；完成后你手里是可发布、可禁用的工具集。


## 一个想做成库的缓存装饰器，需求清单

团队要发布一个内部工具库，包含给任意函数加 TTL 缓存和插件注册表两件事。第一版 @cache 用一个全局 dict 存结果、TTL 用 `time.time()` 判断过期，多线程压测下出现同一冷键被并发重复计算，偶发还有字典竞争；更糟的是把异常也缓存了，上游一次超时被反复返回。

插件注册表则写成模块级裸字典，测试之间互相污染，第三方想加插件必须改核心代码。朴素解法是给每个函数各写一份缓存逻辑、把插件名字硬编码进核心列表，结果重复代码越堆越多、扩展一次改一次。本讲把这两件事做成可发布的抽象：带锁的 TTL 缓存、单调时钟、异常处理、统计与单测隔离，以及显式注册 API 与 entry_points。

<Callout type="warn" title='先看一个真实会出错的写法' text='装饰器里用全局 dict 缓存不加锁，多线程重复计算且状态竞争：查 + 算 + 写跨多步，线程切换会让同一冷键被算多次，字典并发读写也不安全' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段三 · 函数与抽象 |
| 前置 | 第 036 讲 · 类型注解、typing 与渐进式类型 |
| 难度 / 建议时长 | ★★★☆☆ · 45 分钟 |
| 本讲新增 | 装饰器组合设计、注册表与入口点、TTL 与淘汰策略 |
| 一句话目标 | 交付一个可发布的抽象工具集 |
| 为下一讲铺垫 | 类与实例：__init__、self 与属性 |


## 整体蓝图：缓存、注册表与发布边界

<Callout type="tip" title='核心心智模型' text='TTL 必须用 time.monotonic() 而不是 time.time()：前者由操作系统保证单调递增，不受 NTP 回拨或管理员手动改时影响，用墙上时钟存 expire_at 一旦回拨就可能把刚写入的条目误判为过期、或把过期条目当成有效。缓存项存 (expire_at, value)，命中时' />

<SequenceDiagram title='第 037 讲 · 调用时序' caption='从触发到收尾，标出最可能失败的两个位置' :actors='["调用方", "核心逻辑", "外部依赖"]' :steps='[{"from": "调用方", "to": "核心逻辑", "label": "发起调用", "note": "TTL 缓存：单调时钟、锁与", "kind": "call"}, {"from": "核心逻辑", "to": "核心逻辑", "label": "检查前置", "note": "注册表与 entry_poi", "kind": "self"}, {"from": "核心逻辑", "to": "外部依赖", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "外部依赖", "to": "核心逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "核心逻辑", "to": "调用方", "label": "返回或降级", "note": "清理资源", "kind": "return"}]' />

<FlowTimeline :steps='[{"title": "TTL 缓存：单调时钟、锁与异常处理", "desc": "TTL 必须用 time.monotonic() 而不是 time.time()：前…", "tone": "blue"}, {"title": "注册表与 entry_points", "desc": "注册表不要写成模块级裸全局 dict，而要做成显式实例 API：一个 Registr…", "tone": "purple"}, {"title": "单元测试与可发布抽象", "desc": "可发布的抽象必须自带可测性。TTL 缓存把 clock 参数化，测试里传一个假时钟、…", "tone": "orange"}, {"title": "工程落地", "desc": "把插件注册表做成显式 API：可隔离、可拒绝重复、可扩展", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## TTL 缓存：单调时钟、锁与异常处理

TTL 必须用 `time.monotonic()` 而不是 `time.time()`：前者由操作系统保证单调递增，不受 NTP 回拨或管理员手动改时影响，用墙上时钟存 expire_at 一旦回拨就可能把刚写入的条目误判为过期、或把过期条目当成有效。

缓存项存 (expire_at, value)，命中时比较 `monotonic()` < expire_at 决定复用还是重算。

并发上，检查—计算—写入是典型的 check-then-act 竞态：用 `threading.RLock` 把整段包住，N 个线程同时未命中时只有一个真正执行底层函数，避免 thundering herd 与字典并发读写；

RLock 可重入，能容忍同线程嵌套调用，但持锁期间绝不能调用可能回调本缓存的外部代码。异常处理同样关键：只有 fn 正常返回才把结果写进 store，异常直接抛出，否则一次上游抖动会被缓存放大成整段 TTL 的持续失败。

生产版还要有容量上限：除了 TTL，用 maxsize 配合 `OrderedDict.move_to_end` 做 `O(1)` 的 LRU 淘汰或定期清理，防止长跑内存无界增长。

键由 args 加排序后的 kwargs 构成，必须全部可哈希；

用 `functools.wraps` 保留元数据，并暴露 cache_clear 与 cache_info 供测试、灰度与热更新。

```python
import time, threading
from functools import wraps

def cache(ttl, clock=time.monotonic):
    def deco(fn):
        store = {}
        lock = threading.RLock()
        hits = {'hit': 0, 'miss': 0}
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = clock()
            with lock:
                item = store.get(key)
                if item and now < item[0]:
                    hits['hit'] += 1
                    return item[1]
                hits['miss'] += 1
                value = fn(*args, **kwargs)
                store[key] = (now + ttl, value)
                return value
        wrapper.cache_clear = store.clear
        wrapper.cache_info = lambda: dict(hits, size=len(store))
        return wrapper
    return deco

calls = {'n': 0}
@cache(ttl=60)
def slow(x):
    calls['n'] += 1
    return x * 2

print(slow(3), slow(3))
print(calls['n'], slow.cache_info())
slow.cache_clear()
print(slow(3), calls['n'])
```

<OutputBox title='主示例运行结果' output='6 6\n1 {&#39;hit&#39;: 1, &#39;miss&#39;: 1, &#39;size&#39;: 1}\n6 2' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import time, threading\nfrom functools import wraps\n\ndef cache(ttl, clock=time.monotonic):\n    def deco(fn):\n        store = {}\n        lock = threading.RLock()\n        hits = {&#39;hit&#39;: 0, &#39;miss&#39;: 0}\n        @wraps(fn)\n        def wrapper(*args, **kwargs):\n            key = (args, tuple(sorted(kwargs.items())))\n            now = clock()\n            with lock:\n                item = store.get(key)\n                if item and now &lt; item[0]:\n                    hits[&#39;hit&#39;] += 1\n                    return item[1]\n                hits[&#39;miss&#39;] += 1\n                value = fn(*args, **kwargs)\n                store[key] = (now + ttl, value)\n                return value\n        wrapper.cache_clear = store.clear\n        wrapper.cache_info = lambda: dict(hits, size=len(store))\n        return wrapper\n    return deco\n\ncalls = {&#39;n&#39;: 0}\n@cache(ttl=60)\ndef slow(x):\n    calls[&#39;n&#39;] += 1\n    return x * 2\n\nprint(slow(3), slow(3))\nprint(calls[&#39;n&#39;], slow.cache_info())\nslow.cache_clear()\nprint(slow(3), calls[&#39;n&#39;])' :notes='["导入 time 取单调时钟、threading 取可重入锁", "导入 wraps 保留被装饰函数的元数据", "外层收 ttl 与可注入的 clock，默认用 monotonic", "中层接收被装饰函数", "store 存 key 到 (expire_at, value) 的映射", "RLock 保护检查、计算、写入整段临界区", "命中与未命中计数器，供 cache_info 观测", "把名字、文档、__wrapped__ 搬到 wrapper", "内层接收每次调用的实参", "键由位置参数与排序后的关键字参数构成，须可哈希", "读取当前单调时钟值", "进入临界区，避免并发冷键重复计算", "查缓存，item 是 (过期时刻, 值) 或 None", "未过期才算命中", "命中计数加一", "直接返回缓存值，不执行底层函数", "未命中计数加一", "仅在未命中时调用底层函数", "把结果与过期时刻写入 store", "返回新计算的值", "暴露 cache_clear 供测试与热更新", "暴露 cache_info 返回命中统计与条目数", "中层必须返回 wrapper", "外层必须返回 deco", "用字典记录底层函数被真正执行的次数", "用 ttl=60 装饰一个模拟慢函数", "定义被装饰的模拟慢函数 slow", "每次真正执行就把计数加一", "返回计算结果", "两次调用只算一次，结果都是 6", "底层只执行 1 次，命中 1 次、未命中 1 次、缓存 1 条", "清空缓存，验证冷启动路径", "清空后重新计算，底层执行次数变 2"]' title='第 037 讲 · 阶段综合：缓存装饰器库与插件注册表' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**TTL 缓存的关键决策**

| 决策点 | 错误做法 | 正确做法 | 原因 |
| --- | --- | --- | --- |
| 时钟 | time.time() | time.monotonic() | 单调时钟不受 NTP 回拨 / 手动改时影响 |
| 并发 | 裸全局 dict 无锁 | threading.RLock 包住查 + 算 + 写 | 避免同一冷键被并发重复计算与字典竞争 |
| 异常 | 把异常也写进缓存 | 只在成功时写，异常直接抛 | 一次超时不应被放大成整段 TTL 的失败 |
| 容量 | 无界增长 | maxsize 上限 + LRU / 定期清理 | 防止长跑内存膨胀 |
| 键 | args + kwargs 原样 | 排序 kwargs、规范成 tuple 且须可哈希 | kwargs 顺序不同不应产生两个键 |


### 为什么用 time.monotonic 而不是 time.time

```python
import threading, inspect
from functools import wraps

def locked_cache(fn):
    store = {}
    lock = threading.Lock()
    calls = {'n': 0}
    @wraps(fn)
    def wrapper(key):
        with lock:
            if key in store:
                return store[key]
            calls['n'] += 1
            store[key] = fn(key)
            return store[key]
    wrapper.calls = calls
    return wrapper

@locked_cache
def build(k):
    return k * 10

barrier = threading.Barrier(8)
def task():
    barrier.wait()
    return build(1)
ts = [threading.Thread(target=task) for _ in range(8)]
for t in ts: t.start()
for t in ts: t.join()
print(build.calls['n'], build(1), build.__name__, inspect.signature(build))
```

<OutputBox title='原理验证' output='1 10 build (k)' />

<Predict no='037-P' q='带锁 TTL 缓存里执行 slow(3); slow(3) 后 print(calls[&#39;n&#39;], slow.cache_info()) 输出什么？' :options='["1 {&#39;hit&#39;: 1, &#39;miss&#39;: 1, &#39;size&#39;: 1}", "2 {&#39;hit&#39;: 0, &#39;miss&#39;: 2, &#39;size&#39;: 1}", "1 {&#39;hit&#39;: 0, &#39;miss&#39;: 1, &#39;size&#39;: 1}"]' answer='0' output='1 {&#39;hit&#39;: 1, &#39;miss&#39;: 1, &#39;size&#39;: 1}' explain='第一次未命中并计算，第二次命中缓存；底层函数只执行一次，store 里留 1 条，命中与未命中各计 1 次。' />


## 底层：锁、哈希表与异常边界

TTL 缓存的正确性来自三件事的协同。

单调时钟 `time.monotonic()` 由操作系统提供保证递增的计时源，不受系统墙上时钟被 NTP 或管理员回拨的影响，用 `time.time()` 存 expire_at 一旦回拨就可能把刚写入的条目判成过期或把过期条目判成有效。

并发上，检查—计算—写入是典型的 check-then-act 竞态：若不加锁包住整段，N 个线程同时未命中会各自执行一遍底层函数，既浪费又可能让后写的结果覆盖先写的；

用 `threading.RLock` 把这段串行化，并用可重入避免同一线程嵌套调用时自锁，但持锁期间不能调用会回调本缓存的外部代码。

异常必须排除在写入路径之外：只有 fn 正常返回才把 (expire_at, value) 存进 store，否则一次上游抖动会被缓存成整段 TTL 的持续失败。

注册表用实例而非模块全局字典，是为了让每个测试拿到干净状态，并让第三方通过 entry_points 的 `load()` 把实现注入进来，核心只依赖协议而不依赖具体插件。

<ConceptDiagram type='layers3' title='第 037 讲 · 分层视角' labels='TTL 缓存：单调时钟、锁与异常处理|注册表与 entry_points|单元测试与可发布抽象|打包配置' caption='单元测试与可发布抽象' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **打包配置** 落在哪一层。

<Term word='装饰器组合设计' text='TTL 必须用 time.monotonic() 而不是 time.time()：前者由操作系统保证单调递增，不受 NTP 回拨或管理员手动改时影响，用墙上时钟存 expire_at 一旦回拨就可能把刚写入的条目误判为过期、或把过期条目当成有效。缓存项存 (expire_at, value)，命中时比较 monoton' />

<Term word='注册表与入口点' text='注册表不要写成模块级裸全局 dict，而要做成显式实例 API：一个 Registry 类提供 register(name) 装饰器、get(name)、names() 与 clear()，实例可注入让每个测试拿到干净状态。重复注册要有明确约定——默认抛 KeyError 或显式覆盖，绝不能静默覆盖掉已有插件；按名字查' />


## 注册表与 entry_points

注册表不要写成模块级裸全局 dict，而要做成显式实例 API：一个 Registry 类提供 `register(name)` 装饰器、`get(name)`、`names()` 与 `clear()`，实例可注入让每个测试拿到干净状态。重复注册要有明确约定——默认抛 KeyError 或显式覆盖，绝不能静默覆盖掉已有插件；

按名字查找失败时给出清晰的 KeyError 而不是 None。

第三方扩展靠 `importlib.metadata.entry_points`（3.8 起的新 API，用 `group= 过滤`）：第三方包在 `pyproject.toml` 里声明 `[project.entry-points.GROUP]`，核心在运行时用 `entry_points(group=...)` 发现并调用 `ep.load()`，无需改动核心代码即可接入新能力；

3.10 前旧 API 返回 dict，3.12 起去掉了旧的字典式接口，用 group 参数才跨版本稳妥。插件要有统一协议（约定函数签名或 Protocol），加载时要隔离异常，一个坏插件不能拖垮全部；核心只依赖协议、不依赖具体实现。

打包侧用 `pyproject.toml` 声明 `[build-system]`、`[project]`、依赖与入口点，版本与元数据用 `importlib.metadata.version()` 读取。

**注册表与 entry_points**

| 机制 | API / 版本 | 作用 |
| --- | --- | --- |
| 显式注册表 | Registry.register / get / names / clear | 实例可注入，测试隔离，避免裸全局 dict |
| 重复注册 | 默认报错或显式覆盖 | 给出清晰 KeyError，避免静默覆盖 |
| importlib.metadata.entry_points | 3.8+ 新 API，group= 过滤 | 第三方声明入口点，核心运行时发现并 load() |
| pyproject.toml | [project.entry-points.GROUP] | 不改核心代码即可扩展能力 |
| importlib.metadata.version | 3.8+ | 读取已安装分发的版本与元数据 |

```python
from functools import wraps

class Clock:
    def __init__(self):
        self.t = 0.0
    def __call__(self):
        return self.t
    def advance(self, dt):
        self.t += dt

clk = Clock()

def tcache(ttl, clock):
    def deco(fn):
        store = {}
        @wraps(fn)
        def wrapper(*a, **k):
            key = (a, tuple(sorted(k.items())))
            now = clock()
            if key in store and now < store[key][0]:
                return store[key][1]
            value = fn(*a, **k)
            store[key] = (now + ttl, value)
            return value
        return wrapper
    return deco

calls = []
@tcache(ttl=10, clock=clk)
def f(x):
    calls.append(x)
    if x < 0:
        raise ValueError('neg')
    return x + 1

print(f(1), f(1), len(calls))
clk.advance(11)
print(f(1), len(calls))
try:
    f(-1)
except ValueError as e:
    print(type(e).__name__, str(e))
print(len(calls))
```

<OutputBox title='对照写法：先自己猜，再点开' output='2 2 1\n2 2\nValueError neg\n3' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import time, threading\nfrom functools import wraps\n\ndef cache(ttl, clock=time.monotonic):\n    def deco(fn):\n        store = {}\n        lock = threading.RLock()\n        hits = {&#39;hit&#39;: 0, &#39;miss&#39;: 0}\n        @wraps(fn)\n        def wrapper(*args, **kwargs):\n            key = (args, tuple(sorted(kwargs.items())))\n            now = clock()\n            with lock:\n                item = store.get(key)\n                if item and now &lt; item[0]:\n                    hits[&#39;hit&#39;] += 1\n                    return item[1]\n                hits[&#39;miss&#39;] += 1\n                value = fn(*args, **kwargs)\n                store[key] = (now + ttl, value)\n                return value\n        wrapper.cache_clear = store.clear\n        wrapper.cache_info = lambda: dict(hits, size=len(store))\n        return wrapper\n    return deco\n\ncalls = {&#39;n&#39;: 0}\n@cache(ttl=60)\ndef slow(x):\n    calls[&#39;n&#39;] += 1\n    return x * 2\n\nprint(slow(3), slow(3))\nprint(calls[&#39;n&#39;], slow.cache_info())\nslow.cache_clear()\nprint(slow(3), calls[&#39;n&#39;])", "note": "TTL 缓存：单调时钟、锁与异常处理"}, {"label": "对照 / 进阶", "code": "from functools import wraps\n\nclass Clock:\n    def __init__(self):\n        self.t = 0.0\n    def __call__(self):\n        return self.t\n    def advance(self, dt):\n        self.t += dt\n\nclk = Clock()\n\ndef tcache(ttl, clock):\n    def deco(fn):\n        store = {}\n        @wraps(fn)\n        def wrapper(*a, **k):\n            key = (a, tuple(sorted(k.items())))\n            now = clock()\n            if key in store and now &lt; store[key][0]:\n                return store[key][1]\n            value = fn(*a, **k)\n            store[key] = (now + ttl, value)\n            return value\n        return wrapper\n    return deco\n\ncalls = []\n@tcache(ttl=10, clock=clk)\ndef f(x):\n    calls.append(x)\n    if x &lt; 0:\n        raise ValueError(&#39;neg&#39;)\n    return x + 1\n\nprint(f(1), f(1), len(calls))\nclk.advance(11)\nprint(f(1), len(calls))\ntry:\n    f(-1)\nexcept ValueError as e:\n    print(type(e).__name__, str(e))\nprint(len(calls))", "note": "注册表与 entry_points"}]' title='两种写法切换看' />


## 单元测试与可发布抽象

可发布的抽象必须自带可测性。

TTL 缓存把 clock 参数化，测试里传一个假时钟、调用 `advance(ttl + 1)` 就能验证过期重算，完全不用真 sleep；

`cache_info()` 返回 hits / misses / size 让命中率可观测，低命中时及时关掉缓存。异常不缓存要有专门用例：让函数抛 ValueError、再调用一次，断言第二次仍会真正执行而不是直接抛旧异常。

并发正确性是最容易漏掉的用例：用 `threading.Barrier` 让 8 个线程同时到达冷键，断言底层函数只执行一次，这能直接暴露忘记加锁的回归。

注册表每个测试用新实例或 `clear()`，并覆盖重复注册、缺失名字与 bypass 开关。

装饰器还要可禁用（`enabled=False` 直接返回原函数）、可单测（借 `__wrapped__` 测原逻辑）、可观测（`functools.wraps` 保留 `__name__` 让日志带上真名）。

文档里写清 TTL 单位、键的可哈希要求与线程语义，才算达到可交付标准。

**可发布抽象的测试清单**

| 用例 | 做法 | 验证目标 |
| --- | --- | --- |
| TTL 过期 | 注入假时钟 advance(ttl + 1) | 无需真 sleep，验证过期重算 |
| 命中统计 | cache_info() 返回 hits / misses | 可观测，低命中时关缓存 |
| 异常不缓存 | 让函数抛 ValueError 再调用 | 失败不被缓存放大 |
| 并发冷键 | Barrier 让 8 线程同时调用 | 断言底层函数只执行一次 |
| 禁用与隔离 | enabled=False 返回原函数、每测 clear() | 灰度绕开、测试不串状态 |

<CheckList id='P037a' title='学完你应当能' :items='["能讲清 TTL 缓存：单调时钟、锁与异常处理", "能讲清 注册表与 entry_points", "能讲清 单元测试与可发布抽象", "能在工程里处理 打包配置"]' />


## 把插件注册表做成显式 API：可隔离、可拒绝重复、可扩展

一个报表框架要允许业务方注册自定义导出器。若用模块级裸字典，单元测试之间会互相污染，第三方加插件还得改核心代码。正确做法是把注册表封装成一个类：`register(name)` 返回装饰器并把函数登记进实例字典，get / names / clear 提供显式访问与清理；

重复注册直接抛 KeyError 而不是静默覆盖，避免同名插件悄悄顶掉别人。下面用标准库实现一个可直接运行的 Registry，演示注册两个插件、读取调用、拦截重复注册、以及 clear 后清空。

对外发布时再把第三方发现换成 `importlib.metadata.entry_points(group=...)`，核心只依赖一个统一的插件协议，既能测试隔离也能不改代码扩展。

```python
from functools import wraps

class Registry:
    def __init__(self):
        self._items = {}
    def register(self, name):
        def deco(fn):
            if name in self._items:
                raise KeyError('duplicate: ' + name)
            self._items[name] = fn
            @wraps(fn)
            def wrapper(*a, **k):
                return fn(*a, **k)
            return wrapper
        return deco
    def get(self, name):
        return self._items[name]
    def names(self):
        return sorted(self._items)
    def clear(self):
        self._items.clear()

plugins = Registry()

@plugins.register('upper')
def upper(s):
    return s.upper()

@plugins.register('reverse')
def reverse(s):
    return s[::-1]

print(plugins.names())
print(plugins.get('upper')('hi'))
try:
    @plugins.register('upper')
    def dup(s):
        return s
except KeyError as e:
    print(type(e).__name__, str(e))
plugins.clear()
print(plugins.names())
```

<Callout type="idea" title='落地提示' text='把注册表做成显式 API 并支持 entry_points，第三方才能在不改核心代码的前提下扩展能力' />

<CheckList id='P037b' title='上线前自检' :items='["能复现并解释「装饰器里用全局 dict 缓存不加锁，多线程重复计算且状态竞」", "能复现并解释「TTL 用 time.time() 判断，NTP 回拨后缓存」", "能复现并解释「把异常结果也缓存，一次超时被返回整个 TTL」", "能用一条命令验证 装饰器组合设计", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from functools import lru_cache; print(lru_cache(8)(lambda n:n)(1))"
```

把输入换成你自己的数据，观察结果是否仍符合 **装饰器组合设计** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 全局 dict、NTP 回拨与缓存异常

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 装饰器里用全局 dict 缓存不加锁，多线程重复计算且状态竞争 | 查 + 算 + 写跨多步，线程切换会让同一冷键被算多次，字典并发读写也不安全 | 用 threading.RLock 包住整段，或按键分锁；持锁期间不要回调本缓存 |
| TTL 用 time.time() 判断，NTP 回拨后缓存行为错乱 | 墙上时钟可被回拨，expire_at 与 now 的比较失去单调性 | 改用 time.monotonic() 存过期时间；测试里注入假时钟推进 |
| 把异常结果也缓存，一次超时被返回整个 TTL | 写入路径没有区分成功与失败，异常对象或失败值被存进缓存 | 只在 fn 正常返回时写 store，异常直接抛出；必要时给失败单独设短 TTL |

<Callout type="warn" title='本讲最容易踩的坑' text='装饰器里用全局 dict 缓存不加锁，多线程重复计算且状态竞争：查 + 算 + 写跨多步，线程切换会让同一冷键被算多次，字典并发读写也不安全' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：装饰器里用全局 dict 缓存不加锁，多线程", "body": "查 + 算 + 写跨多步，线程切换会让同一冷键被算多次，字典并发读写也不安全", "tip": "用 threading.RLock 包住整段，或按键分锁；持锁期间不要回调本缓存"}, {"title": "第 2 步：TTL 用 time.time() 判断，N", "body": "墙上时钟可被回拨，expire_at 与 now 的比较失去单调性", "tip": "改用 time.monotonic() 存过期时间；测试里注入假时钟推进"}, {"title": "第 3 步：把异常结果也缓存，一次超时被返回整个 TTL", "body": "写入路径没有区分成功与失败，异常对象或失败值被存进缓存", "tip": "只在 fn 正常返回时写 store，异常直接抛出；必要时给失败单独设短 TTL"}]' />


## 从练习到可发布清单

<Exercise title='基础：实现带 cache_clear 的最小 TTL 缓存' task='用 time.monotonic() 存过期时刻，键由 args 与排序后的 kwargs 构成，暴露 cache_clear，验证两次调用只算一次、清空后重算。' solution='import time\nfrom functools import wraps\n\ndef mini_cache(ttl):\n    def deco(fn):\n        store = {}\n        @wraps(fn)\n        def wrapper(*a, **k):\n            key = (a, tuple(sorted(k.items())))\n            now = time.monotonic()\n            if key in store and now &lt; store[key][0]:\n                return store[key][1]\n            v = fn(*a, **k)\n            store[key] = (now + ttl, v)\n            return v\n        wrapper.cache_clear = store.clear\n        return wrapper\n    return deco\n\n@mini_cache(60)\ndef sq(x):\n    return x * x\nprint(sq(4), sq(4))\nsq.cache_clear()\nprint(sq(4))' explain='单调时钟避免回拨错乱，键须可哈希，cache_clear 供测试与热更新；生产版还要加锁与容量上限。' />

<Exercise title='进阶：注册表拒绝重复注册' task='写一个 Reg 类，register 在名字已存在时抛 KeyError，names 返回有序名字列表，演示注册、调用与重复拦截。' solution='class Reg:\n    def __init__(self):\n        self.d = {}\n    def register(self, name):\n        def deco(fn):\n            if name in self.d:\n                raise KeyError(name)\n            self.d[name] = fn\n            return fn\n        return deco\n    def names(self):\n        return sorted(self.d)\n\nr = Reg()\n@r.register(&#39;a&#39;)\ndef a():\n    return 1\nprint(r.names(), r.d[&#39;a&#39;]())\ntry:\n    @r.register(&#39;a&#39;)\n    def b():\n        return 2\nexcept KeyError as e:\n    print(type(e).__name__, str(e))' explain='重复注册默认报错而非静默覆盖，避免同名插件悄悄顶掉已有实现；实例化的 Reg 让每个测试状态隔离。' />

<Quiz no='037-1' q='TTL 缓存判断过期，用哪个时钟最稳妥？' :options='["time.monotonic()", "time.time()", "time.clock()", "datetime.now()"]' answer="0" explain='单调时钟保证递增，不受 NTP 回拨或手动改时影响；time.time() 是墙上时钟，回拨会让 expire_at 比较失真。' />

<Quiz no='037-2' q='装饰器里用全局 dict 缓存却不加锁，主要风险是？' :options='["并发下同一冷键被重复计算且字典读写竞争", "缓存命中变慢", "TTL 自动失效", "functools.wraps 失效"]' answer="0" explain='查 + 算 + 写是多步竞态，N 个线程同时未命中会各算一遍；用 threading.RLock 把整段串行化。' />

<Quiz no='037-3' q='让第三方不改核心代码就能扩展插件，应使用？' :options='["importlib.metadata.entry_points 发现并 load()", "在核心里硬编码插件列表", "把所有插件塞进一个全局 list", "用 eval 动态执行外部代码"]' answer="0" explain='第三方在 pyproject.toml 声明入口点，核心用 entry_points(group=...) 发现并 load()，只依赖统一协议。' />

<FillBlank no='037-F' tpl='___ time, threading' :answers='["import"]' hint='回想本讲关于 装饰器组合设计 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 TTL 缓存：单调时钟、锁与异常处理 的落点。' />

<KnowledgeCard :points='["TTL 用 time.monotonic()（单调），不用 time.time()（可回拨）；缓存项存 (expire_at, value)", "threading.RLock 包住查 + 算 + 写，避免并发冷键重复计算与字典竞争；持锁时不回调本缓存", "异常不缓存：只在 fn 正常返回时写 store，否则一次失败被放大成整段 TTL", "键由 args + 排序后的 kwargs 构成且须可哈希；functools.wraps 保留元数据；暴露 cache_clear / cache_info", "注册表做成显式实例 API（register / get / names / clear），每测 clear 隔离；第三方用 entry_points(group=...) 扩展", "测试要点：注入假时钟推进 TTL、Barrier 并发冷键断言只算一次、enabled=False 绕过、cache_info 观测命中率"]' :pitfalls='["装饰器里用全局 dict 缓存不加锁，多线程重复计算且状态竞争", "TTL 用 time.time() 判断，NTP 回拨后缓存行为错乱", "把异常结果也缓存，一次超时被返回整个 TTL", "装饰器里用全局字典缓存而不加锁，多线程下会出现重复计算与状态竞争"]' summary='好的抽象让调用方只写一行 @cache(ttl=60)，却把失效、统计、异常与并发都处理妥当' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| TTL 用 time.monotonic()（单调），不用 time.time()（可回拨）；缓存项存 (expire_at, value) | 建立直觉 |
| threading.RLock 包住查 + 算 + 写，避免并发冷键重复计算与字典竞争；持锁时不回调本缓存 | 跑通示例 |
| 异常不缓存：只在 fn 正常返回时写 store，否则一次失败被放大成整段 TTL | 深入边界 |
| 键由 args + 排序后的 kwargs 构成且须可哈希；functools.wraps 保留元数据；暴露 cache_clear / cache_info | 工程落地 |
| 注册表做成显式实例 API（register / get / names / clear），每测 clear 隔离；第三方用 entry_points(group=...) 扩展 | 随堂检测 |
| 测试要点：注入假时钟推进 TTL、Barrier 并发冷键断言只算一次、enabled=False 绕过、cache_info 观测命中率 | 复盘 |

1. TTL 用 time.monotonic()（单调），不用 time.time()（可回拨）；缓存项存 (expire_at, value)

2. threading.RLock 包住查 + 算 + 写，避免并发冷键重复计算与字典竞争；持锁时不回调本缓存

3. 异常不缓存：只在 fn 正常返回时写 store，否则一次失败被放大成整段 TTL

[下一讲：类与实例：__init__、self 与属性](/oop/class-basics)
