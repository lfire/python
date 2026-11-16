---
title: 第 129 讲 · 实战 08 · KV 贯穿线 ① 内存版与接口抽象
description: 为四讲演进线奠定可替换的接口
---

<StageHeader stage='L12 · 工程实战' level='★★★☆☆' time='50 分钟' goal='为四讲演进线奠定可替换的接口' prereq='第 128 讲 · 实战 07 · 并发爬虫与分布式调度' />

# 第 129 讲 · 实战 08 · KV 贯穿线 ① 内存版与接口抽象

前面几讲各做各的，从这一讲起换成连着走四讲的小项目：同一个 KV 要一路长出网络、落盘与多机能力。头一件事是划好地基——把会变的部分挡在接口后面，先把存储引擎接口和命令模型定稳。

第一版图省事，命令层直接读写全局 `dict`；两周后要加过期、网络、持久化，才发现每个调用点都得改，连「键不存在」与代码笔误都混在一起。我们先定只含 `get`、`set`、`delete` 的窄接口与错误类型，再做内存实现与 TTL 过期，接着用锁分片处理并发安全，最后以同一组契约测试收口。需要你熟悉字典、类、`Protocol` 和线程锁；学完得到一个内存版 KV，往后的网络与落盘都不必重写命令层。


## 一开始就把 dict 暴露给命令层，后面每加一层都要重写

一个 KV 服务第一版图省事，命令层直接读写一个全局 `dict`：SET 就一句 `d[k] = v`，GET 就 `return d[k]`。上线两周要加过期、加网络、加持久化，团队发现每个调用点都得改一遍：过期判断散落在各处 GET、网络层拿到字节后要自己解析命令、持久化又要拦截所有写。

更糟的是 `dict` 的 `KeyError` 既可能表示「键不存在」，也可能来自代码里别处的拼写错误，调用方只能笼统 `catch KeyError`，错误语义一团糟。朴素解法「先把 `dict` 用起来再说」失败在把「会变的部分」暴露给了上层：存储引擎、网络层、持久化、分片本来要依次替换，接口却一处没留。

这一讲先定义窄接口、命令模型与错误类型，再让内存实现通过同一组契约测试，为四讲演进线奠定可替换的地基。

<Callout type="tip" title='核心心智模型' text='命令用 `dataclasses.dataclass` 配 `frozen=True` 表达 `(op, key, value, ttl)`，不可变保证命令在解析、排队、传输途中不被偷偷改；`op` 取 `SET` / `GET` / `DEL` / `EXPIRE` 这类封闭集合，命令语义在四讲演…' />


## 命令模型与窄接口：把变化挡在抽象后面

命令用 `dataclasses.dataclass` 配 `frozen=True` 表达 `(op, key, value, ttl)`，不可变保证命令在解析、排队、传输途中不被偷偷改；`op` 取 `SET` / `GET` / `DEL` / `EXPIRE` 这类封闭集合，命令语义在四讲演进线里始终不变。

错误语义要有自己的层级：自定义 `KVError` 基类，下分 `KeyNotFound`（键不存在或已过期）与 `CommandError`（未知命令、参数非法），不要让调用方 `catch` 裸 `KeyError`——`dict` 的 `KeyError` 与业务「键不存在」混在一起，排查时无法区分是数据问题还是代码 bug。

存储引擎接口要窄：只有 `get` / `set` / `delete`（可选 `exists` / `ttl`），用 `typing.Protocol`（PEP 544，3.8 起）声明，实现类靠结构化子类型满足、不必继承。

上层命令分发只依赖这个协议，后面换成网络引擎、WAL 引擎、分片引擎时，命令层一行不改。反面是把 `dict` 直接暴露给命令层：加持久化时所有调用点都要重写，过期逻辑也会散落到每个 `GET`。失效信号：命令函数里出现引擎的具体类名、换个实现要改超过一处、单测必须 `mock` 内部字典。

**KV 命令与错误语义**

| 命令 / 错误 | 语义 | 返回 / 抛出 |
| --- | --- | --- |
| SET key value [ttl] | 写入并可选设过期 | 通常返回 None 或 OK |
| GET key | 读取，键不存在或已过期 | 抛 KeyNotFound |
| DEL key | 删除，含 tombstone 语义 | 成功 True，不存在抛 KeyNotFound |
| 未知 op | 命令层错误 | 抛 ValueError / CommandError |
| 锁内复合操作 | 检查过期加删除 | 必须整体加锁，不能只锁写 |

```python
import threading

class KeyNotFound(KeyError):
    pass

class MemoryEngine:
    def __init__(self):
        self.data, self.exp, self.now = {}, {}, 0
        self.lock = threading.Lock()
    def _live(self, key):
        if self.exp.get(key, -1) != -1 and self.exp[key] <= self.now:
            del self.data[key]
            del self.exp[key]
            return False
        return key in self.data
    def get(self, key):
        with self.lock:
            if not self._live(key):
                raise KeyNotFound(key)
            return self.data[key]
    def set(self, key, value, ttl=0):
        with self.lock:
            self.data[key] = value
            self.exp[key] = self.now + ttl if ttl else -1
    def delete(self, key):
        with self.lock:
            if not self._live(key):
                raise KeyNotFound(key)
            del self.data[key]
            return True

def execute(eng, op, key, value='', ttl=0):
    if op == 'SET': return eng.set(key, value, ttl)
    if op == 'GET': return eng.get(key)
    if op == 'DEL': return eng.delete(key)
    raise ValueError('unknown op ' + op)

def contract(eng):
    eng.set('k', 'v', ttl=3)
    assert eng.get('k') == 'v'
    eng.now += 3
    try:
        eng.get('k')
    except KeyNotFound:
        return 'ok'
    return 'violation'

e = MemoryEngine()
print('contract', contract(e))
print('set/get', execute(e, 'SET', 'b', '2'), execute(e, 'GET', 'b'))
print('del', execute(e, 'DEL', 'b'))
try:
    execute(e, 'PING', 'x')
except ValueError as err:
    print('bad op', type(err).__name__)
```

<OutputBox title='主示例运行结果' output='contract ok\nset/get None 2\ndel True\nbad op ValueError' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import threading\n\nclass KeyNotFound(KeyError):\n    pass\n\nclass MemoryEngine:\n    def __init__(self):\n        self.data, self.exp, self.now = {}, {}, 0\n        self.lock = threading.Lock()\n    def _live(self, key):\n        if self.exp.get(key, -1) != -1 and self.exp[key] &lt;= self.now:\n            del self.data[key]\n            del self.exp[key]\n            return False\n        return key in self.data\n    def get(self, key):\n        with self.lock:\n            if not self._live(key):\n                raise KeyNotFound(key)\n            return self.data[key]\n    def set(self, key, value, ttl=0):\n        with self.lock:\n            self.data[key] = value\n            self.exp[key] = self.now + ttl if ttl else -1\n    def delete(self, key):\n        with self.lock:\n            if not self._live(key):\n                raise KeyNotFound(key)\n            del self.data[key]\n            return True\n\ndef execute(eng, op, key, value=&#39;&#39;, ttl=0):\n    if op == &#39;SET&#39;: return eng.set(key, value, ttl)\n    if op == &#39;GET&#39;: return eng.get(key)\n    if op == &#39;DEL&#39;: return eng.delete(key)\n    raise ValueError(&#39;unknown op &#39; + op)\n\ndef contract(eng):\n    eng.set(&#39;k&#39;, &#39;v&#39;, ttl=3)\n    assert eng.get(&#39;k&#39;) == &#39;v&#39;\n    eng.now += 3\n    try:\n        eng.get(&#39;k&#39;)\n    except KeyNotFound:\n        return &#39;ok&#39;\n    return &#39;violation&#39;\n\ne = MemoryEngine()\nprint(&#39;contract&#39;, contract(e))\nprint(&#39;set/get&#39;, execute(e, &#39;SET&#39;, &#39;b&#39;, &#39;2&#39;), execute(e, &#39;GET&#39;, &#39;b&#39;))\nprint(&#39;del&#39;, execute(e, &#39;DEL&#39;, &#39;b&#39;))\ntry:\n    execute(e, &#39;PING&#39;, &#39;x&#39;)\nexcept ValueError as err:\n    print(&#39;bad op&#39;, type(err).__name__)' :notes='["导入 threading，为引擎准备并发安全所需的锁", "空行，只用于分隔逻辑块，不影响执行结果。", "自定义 KeyNotFound 继承 KeyError，把业务错误与 dict 的裸 KeyError 区分开", "类体只有 pass，异常类型本身就承载了语义", "空行，只用于分隔逻辑块，不影响执行结果。", "MemoryEngine 是第一版存储实现，后面会被网络版与 WAL 版替换", "构造时初始化三个状态容器与时钟", "data 存键值、exp 存绝对过期时刻、now 是可推进的逻辑时钟", "整把锁保护复合操作，避免读—检查—删之间被切换", "_live 判断键是否仍有效，并顺带做惰性删除", "有过期时刻且已到达当前时钟，判定为失效", "惰性删除：清掉值", "同时清掉过期表项，避免残留", "返回 False 表示该键已不可用", "其余情况以键是否在 data 中为准", "get 是读路径，也要在锁内完成检查与取值", "进入临界区，检查与返回不可被其它线程插入", "失效则抛业务异常，而不是返回 None 让调用方猜", "抛出 KeyNotFound，携带键名便于排查", "返回当前值", "set 写路径，ttl 为 0 表示永不过期", "写操作同样在锁内", "写入值", "记绝对过期时刻；无 ttl 时写 -1 作为哨兵", "delete 也要走 _live，过期键不能被当成成功删除", "锁内完成检查与删除", "失效则抛 KeyNotFound", "返回 False 分支已由 _live 处理，这里抛出异常", "删除键", "返回 True 表示确实删掉了一条记录", "空行，只用于分隔逻辑块，不影响执行结果。", "execute 是命令分发层，只认识引擎的窄接口", "SET 转发三个参数，返回引擎的返回值", "GET 只转发键", "DEL 只转发键", "未知命令抛 ValueError，属于命令层错误语义", "空行，只用于分隔逻辑块，不影响执行结果。", "contract 是一组对每个引擎都跑的契约断言", "带 ttl=3 写入一个键", "立即读取应拿到原值", "把逻辑时钟推进到过期时刻", "过期后再读应当失败", "尝试读取已过期键", "捕获 KeyNotFound 说明过期语义正确", "契约通过返回 ok", "若没抛异常则说明实现违约", "空行，只用于分隔逻辑块，不影响执行结果。", "实例化内存引擎", "打印契约结果，ok 表示过期与错误语义达标", "SET 返回 None、GET 返回 &#39;2&#39;，命令层与引擎解耦", "DEL 返回 True", "未知命令触发命令层异常", "传入一个不存在的 op", "捕获 ValueError，验证错误语义可区分", "打印异常类型，确认是命令层错误而非数据层错误"]' title='第 129 讲 · 实战 08 · KV 贯穿线 ① 内存版与接口抽象' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='compare2' title='第 129 讲 · 命令模型与窄接口：把变化挡在抽象后面' labels='命令模型与窄接口：把变化挡在抽象后面|内存实现与过期策略：惰性删除与逻辑时钟|并发安全、契约测试与替换点|错误语义' caption='为四讲演进线奠定可替换的接口' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 内存实现与过期策略：惰性删除与逻辑时钟

内存引擎用两个字典：`data` 存键值、`exp` 存绝对过期时刻，逻辑时钟 `now` 由测试推进而不是直接读系统时间，这样过期行为可复现。

TTL 记绝对时刻而非倒计时，才能避免时钟调整带来的漂移；生产里用 `time.monotonic()`（不受系统时间回拨影响）而不要用 `time.time()`。

`ttl` 小于等于 0 表示永不过期，`SET` 一个已有键时必须清掉旧的 `exp`，否则旧过期时刻会让新值提前失效。过期删除有两种：惰性删除在读时检查 `exp` 并顺手清理，实现简单但过期键若没人访问就一直占内存；定期删除由后台线程按采样扫描补上，Redis 用的正是两者组合。

删除也要写成 `DEL` 命令而不是直接 `del data[key]`，因为后面 WAL 需要记录 tombstone，否则重放后已删键会复活。基准测试用 `timeit` 或 `perf_counter` 测纯内存 QPS，务必预热、区分读写比例、记录 p99；只报平均吞吐会掩盖锁竞争下的长尾。

**过期策略对照**

| 策略 | 触发时机 | 优点 | 代价 |
| --- | --- | --- | --- |
| 惰性删除 | GET/DEL 时检查 exp | 实现简单、零后台开销 | 冷键长期占内存 |
| 定期抽样删除 | 后台线程周期扫描 | 能回收冷键 | 需控制扫描比例与 CPU |
| 绝对过期时刻 | now + ttl 存入 exp | 不受时钟回拨影响 | 要用 time.monotonic |
| 倒计时 TTL | 存剩余秒数 | 直观 | 时钟调整会漂移 |

```python
class Memory:
    def __init__(self): self.d = {}
    def get(self, k):
        if k not in self.d: raise KeyError(k)
        return self.d[k]
    def set(self, k, v): self.d[k] = v

class Logged:
    def __init__(self): self.d, self.log = {}, []
    def get(self, k):
        self.log.append('get ' + k)
        if k not in self.d: raise KeyError(k)
        return self.d[k]
    def set(self, k, v):
        self.log.append('set ' + k)
        self.d[k] = v

def suite(make):
    e = make()
    e.set('a', '1')
    assert e.get('a') == '1'
    try:
        e.get('missing')
    except KeyError:
        return 'pass'
    return 'violation'

print('memory', suite(Memory))
print('logged', suite(Logged))
```

<OutputBox title='对照写法：先自己猜，再点开' output='memory pass\nlogged pass' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import threading\n\nclass KeyNotFound(KeyError):\n    pass\n\nclass MemoryEngine:\n    def __init__(self):\n        self.data, self.exp, self.now = {}, {}, 0\n        self.lock = threading.Lock()\n    def _live(self, key):\n        if self.exp.get(key, -1) != -1 and self.exp[key] &lt;= self.now:\n            del self.data[key]\n            del self.exp[key]\n            return False\n        return key in self.data\n    def get(self, key):\n        with self.lock:\n            if not self._live(key):\n                raise KeyNotFound(key)\n            return self.data[key]\n    def set(self, key, value, ttl=0):\n        with self.lock:\n            self.data[key] = value\n            self.exp[key] = self.now + ttl if ttl else -1\n    def delete(self, key):\n        with self.lock:\n            if not self._live(key):\n                raise KeyNotFound(key)\n            del self.data[key]\n            return True\n\ndef execute(eng, op, key, value=&#39;&#39;, ttl=0):\n    if op == &#39;SET&#39;: return eng.set(key, value, ttl)\n    if op == &#39;GET&#39;: return eng.get(key)\n    if op == &#39;DEL&#39;: return eng.delete(key)\n    raise ValueError(&#39;unknown op &#39; + op)\n\ndef contract(eng):\n    eng.set(&#39;k&#39;, &#39;v&#39;, ttl=3)\n    assert eng.get(&#39;k&#39;) == &#39;v&#39;\n    eng.now += 3\n    try:\n        eng.get(&#39;k&#39;)\n    except KeyNotFound:\n        return &#39;ok&#39;\n    return &#39;violation&#39;\n\ne = MemoryEngine()\nprint(&#39;contract&#39;, contract(e))\nprint(&#39;set/get&#39;, execute(e, &#39;SET&#39;, &#39;b&#39;, &#39;2&#39;), execute(e, &#39;GET&#39;, &#39;b&#39;))\nprint(&#39;del&#39;, execute(e, &#39;DEL&#39;, &#39;b&#39;))\ntry:\n    execute(e, &#39;PING&#39;, &#39;x&#39;)\nexcept ValueError as err:\n    print(&#39;bad op&#39;, type(err).__name__)", "note": "命令模型与窄接口：把变化挡在抽象后面"}, {"label": "对照 / 进阶", "code": "class Memory:\n    def __init__(self): self.d = {}\n    def get(self, k):\n        if k not in self.d: raise KeyError(k)\n        return self.d[k]\n    def set(self, k, v): self.d[k] = v\n\nclass Logged:\n    def __init__(self): self.d, self.log = {}, []\n    def get(self, k):\n        self.log.append(&#39;get &#39; + k)\n        if k not in self.d: raise KeyError(k)\n        return self.d[k]\n    def set(self, k, v):\n        self.log.append(&#39;set &#39; + k)\n        self.d[k] = v\n\ndef suite(make):\n    e = make()\n    e.set(&#39;a&#39;, &#39;1&#39;)\n    assert e.get(&#39;a&#39;) == &#39;1&#39;\n    try:\n        e.get(&#39;missing&#39;)\n    except KeyError:\n        return &#39;pass&#39;\n    return &#39;violation&#39;\n\nprint(&#39;memory&#39;, suite(Memory))\nprint(&#39;logged&#39;, suite(Logged))", "note": "内存实现与过期策略：惰性删除与逻辑时钟"}]' title='两种写法切换看' />


## 并发安全：GIL 不等于读—检查—删原子

`Protocol` 是结构化子类型：typing 在类创建时用元类收集方法名构成协议，实现类不必继承，只要能解析出同名可调用属性就满足接口；`@runtime_checkable` 只检查成员存在，不校验签名。

把引擎藏在窄接口后面，等价于把「会变的部分」隔离到单一替换点，命令层只依赖抽象，后续网络、WAL、分片依次替换时行为不变，这正是开闭原则。惰性删除的复杂度是每次读 `O(1)`，但内存占用与过期未访问键数成正比；绝对过期时刻配合 `time.monotonic` 避免系统时间回拨造成的提前或延后失效。

并发层面，`GIL` 只保证单条字节码原子，`dis` 显示 `box[0] += 1` 由 `BINARY_OP` 与 `STORE_SUBSCR` 等多条指令组成，切换可发生在中间，因此读—检查—删必须整体加锁。契约测试把跨实现的隐含假设显式化，是替换安全性的唯一证据。

```python
import dis, threading
from concurrent.futures import ThreadPoolExecutor

def bump(box, lock):
    with lock:
        box[0] += 1

ops = [i.opname for i in dis.get_instructions(bump)]
print('multi-bytecode', 'BINARY_OP' in ops and 'STORE_SUBSCR' in ops)
box, lock = [0], threading.Lock()
with ThreadPoolExecutor(4) as ex:
    list(ex.map(lambda _: bump(box, lock), range(500)))
print('guarded count', box[0])
print('lock type', type(lock).__name__)
```

<OutputBox title='原理验证' output='multi-bytecode True\nguarded count 500\nlock type lock' />

<Term word='命令模型与协议设计' text='命令用 `dataclasses.dataclass` 配 `frozen=True` 表达 `(op, key, value, ttl)`，不可变保证命令在解析、排队、传输途中不被偷偷改；`op` 取 `SET` / `GET` / `DEL` / `EXPIRE` 这类封闭集合，命令语义在四讲演进线里始终不变。错误…' />

<Term word='存储引擎接口' text='内存引擎用两个字典：`data` 存键值、`exp` 存绝对过期时刻，逻辑时钟 `now` 由测试推进而不是直接读系统时间，这样过期行为可复现。TTL 记绝对时刻而非倒计时，才能避免时钟调整带来的漂移；生产里用 `time.monotonic()`（不受系统时间回拨影响）而不要用 `time.time()`。`ttl`…' />


## 契约测试与替换点：四讲演进的同一组用例

`dict` 的单次读写在 `GIL` 下是原子的，但「检查是否过期 → 删 → 返回」是复合操作，必须用 `threading.Lock` 包住整个临界区。

`dis` 能看到 `box[0] += 1` 编成 `BINARY_OP` 加 `STORE_SUBSCR` 等多条字节码，线程切换可发生在指令之间，因此读—改—写不加锁必然有竞态。

一把大锁简单但把所有写串行化；锁分片按 `hash(key) % N` 把键映射到 N 把独立锁，不同分片可并行写，N 常取 2 的幂；这层机制等讲到持久化与并发时还会再展开，届时把它和 WAL 的写入顺序放在一起看。注意内置 `hash` 对字符串有随机化，只影响分片选择、不影响正确性。

契约测试是一组对每个实现都跑同样断言的用例：`SET` 后 `GET` 能取回、`DEL` 后 `GET` 抛 `KeyNotFound`、TTL 到期后 `GET` 抛异常、未知命令抛 `CommandError`。任何新引擎都必须通过同一组用例才能替换，这是 Liskov 替换原则在存储层的落地。

失效信号：并发压测后计数偏小、换实现后契约用例失败、基准只报平均值。

**四讲演进的替换点**

| 讲次 | 替换的部分 | 保持不变的部分 |
| --- | --- | --- |
| 129 内存版 | dict + exp 引擎 | 命令语义、窄接口、契约测试 |
| 130 网络层 | 传输方式与协议帧 | 命令语义与引擎接口 |
| 131 WAL | 持久化与恢复 | 命令语义与引擎接口 |
| 132 分片复制 | 路由与副本 | 命令语义与契约测试 |

<CheckList id='P129a' title='上线前自检' :items='["能复现并解释「命令层直接读写全局 dict」", "能复现并解释「用裸 KeyError 表示所有错误」", "能复现并解释「认为 GIL 让读—检查—删天然安全」", "能用一条命令验证 命令模型与协议设计", "关键路径有自动化测试与失败分支"]' />


## 窄接口 + 命令层 + 契约测试 + 装配根

贯穿线的第一讲要把地基打对：`Engine` 用 `typing.Protocol` 声明三个方法，`MemoryEngine` 只实现这三个方法，`Service` 通过构造函数接收引擎、把 `SET`/`GET`/`DEL` 翻译成方法调用，`contract` 对任意 `make()` 出来的实现跑同一组断言，`compose` 作为装配根按名字选实现。

因为 `Service` 只认识 `Engine`，后面换成网络引擎、WAL 引擎、分片引擎时，命令层、契约测试与调用方都不用改。真实项目还会给契约测试补过期、并发、未知命令三类用例，并把契约文件随版本库提交，让跨实现的替换在 CI 里自动验收。片段可直接运行，重点看引擎是如何被挡在接口后面的。

```python
from typing import Protocol

class Engine(Protocol):
    def get(self, key: str) -> str: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> bool: ...

class MemoryEngine:
    def __init__(self): self.d = {}
    def get(self, key):
        if key not in self.d: raise KeyError(key)
        return self.d[key]
    def set(self, key, value): self.d[key] = value
    def delete(self, key):
        if key not in self.d: raise KeyError(key)
        del self.d[key]
        return True

class Service:
    def __init__(self, engine: Engine): self.engine = engine
    def execute(self, op, key, value=''):
        if op == 'SET': return self.engine.set(key, value)
        if op == 'GET': return self.engine.get(key)
        if op == 'DEL': return self.engine.delete(key)
        raise ValueError(op)

def contract(make):
    svc = Service(make())
    svc.execute('SET', 'k', 'v')
    assert svc.execute('GET', 'k') == 'v'
    assert svc.execute('DEL', 'k') is True
    return type(svc.engine).__name__

def compose(name):
    return Service({'memory': MemoryEngine}[name]())

print('contract', contract(MemoryEngine))
print('service', type(compose('memory').engine).__name__)
```

<Callout type="idea" title='落地提示' text='先定义窄接口与错误类型，配一组契约测试，再让每个实现都通过同一组用例' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 命令层直接读写全局 dict | 把存储细节暴露给上层，加过期/网络/持久化时所有调用点都要重写 | 定义只含 get/set/delete 的 Protocol 窄接口，命令层通过构造注入引擎 |
| 用裸 KeyError 表示所有错误 | dict 的 KeyError 与业务「键不存在」混在一起，调用方无法区分数据问题与代码 bug | 自定义 KVError 层级，分出 KeyNotFound 与 CommandError，让错误语义可判定 |
| 认为 GIL 让读—检查—删天然安全 | GIL 只保证单条字节码原子，复合操作跨多条指令，切换可发生在中间 | 用 threading.Lock 包住整个临界区；高并发再按 hash(key) % N 做锁分片 |

<Callout type="warn" title='本讲最容易踩的坑' text='命令层直接读写全局 dict：把存储细节暴露给上层，加过期/网络/持久化时所有调用点都要重写' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：命令层直接读写全局 dict", "body": "把存储细节暴露给上层，加过期/网络/持久化时所有调用点都要重写", "tip": "定义只含 get/set/delete 的 Protocol 窄接口，命令层通过构造注入引擎"}, {"title": "第 2 步：用裸 KeyError 表示所有错误", "body": "dict 的 KeyError 与业务「键不存在」混在一起，调用方无法区分数据问题与代码 bug", "tip": "自定义 KVError 层级，分出 KeyNotFound 与 CommandError，让错误语义可判定"}, {"title": "第 3 步：认为 GIL 让读—检查—删天然安全", "body": "GIL 只保证单条字节码原子，复合操作跨多条指令，切换可发生在中间", "tip": "用 threading.Lock 包住整个临界区；高并发再按 hash(key) % N 做锁分片"}]' />


## typing.Protocol 的结构化子类型与 _ProtocolMeta

PEP 544 的结构化子类型让存储引擎不必继承任何基类：命令层只依赖一个 Protocol，实现类只要方法名与签名匹配就被视为满足。

源码在 `Lib/typing.py` 的 _ProtocolMeta（继承 ABCMeta）：类创建时收集 mro 里所有带注解的方法与属性，存进 `__protocol_attrs__`（3.12 起可用 `typing.get_protocol_members` 读取），并置 `_is_protocol = True`；非 protocol 的子类若没有显式把它置 False，就被当作具体实现。

加 `@runtime_checkable` 后 `__instancecheck__` / `__subclasscheck__` 才启用，但它只逐个检查成员名是否存在，不校验类型注解、不执行方法、也不看签名，所以 `isinstance(obj, Engine)` 通过并不代表 `engine.set(k, v)` 的参数顺序正确。

真正的类型约束在静态检查器里完成，运行时只需要这层有没有 get / set / delete 的闸门。

与之相对，`abc.ABC` 配 `@abstractmethod` 是名义子类型：`Objects/typeobject.c` 的 `__instancecheck__` 走 `ABCMeta.__subclasscheck__` 与 _abc 缓存，未实现抽象方法在实例化阶段就抛 TypeError。

选哪个是明确的架构权衡：Protocol 让内存、网络代理、WAL 引擎、分片客户端四种实现完全解耦、可独立替换，代价是错误只能在运行时或静态检查里暴露；ABC 把契约钉死在继承关系上，代价是所有实现被绑进同一棵类树。

```python
from typing import Protocol, runtime_checkable, get_protocol_members

@runtime_checkable
class Engine(Protocol):
    def get(self, key): ...
    def set(self, key, value): ...
    def delete(self, key): ...

print('protocol_members', sorted(get_protocol_members(Engine)))
print('is_protocol', Engine._is_protocol)

class MemoryEngine:
    def __init__(self):
        self._d = {}
    def get(self, key):
        return self._d.get(key)
    def set(self, key, value):
        self._d[key] = value
    def delete(self, key):
        self._d.pop(key, None)

print('isinstance_memory', isinstance(MemoryEngine(), Engine))
print('structural_issubclass', issubclass(MemoryEngine, Engine))
```

<OutputBox title='扩展示例运行结果' output='protocol_members [&#39;delete&#39;, &#39;get&#39;, &#39;set&#39;]\nis_protocol True\nisinstance_memory True\nstructural_issubclass True' />

<LineByLine code='from typing import Protocol, runtime_checkable, get_protocol_members\n\n@runtime_checkable\nclass Engine(Protocol):\n    def get(self, key): ...\n    def set(self, key, value): ...\n    def delete(self, key): ...\n\nprint(&#39;protocol_members&#39;, sorted(get_protocol_members(Engine)))\nprint(&#39;is_protocol&#39;, Engine._is_protocol)\n\nclass MemoryEngine:\n    def __init__(self):\n        self._d = {}\n    def get(self, key):\n        return self._d.get(key)\n    def set(self, key, value):\n        self._d[key] = value\n    def delete(self, key):\n        self._d.pop(key, None)\n\nprint(&#39;isinstance_memory&#39;, isinstance(MemoryEngine(), Engine))\nprint(&#39;structural_issubclass&#39;, issubclass(MemoryEngine, Engine))' :notes='["声明为运行时可检查协议，方法体用占位符", "空行，只用于分隔逻辑块，不影响执行结果。", "get_protocol_members 返回协议声明的成员集合", "_is_protocol 由 _ProtocolMeta 置为 True", "内存实现完全不继承 Engine", "runtime_checkable 的 isinstance 只查成员存在", "同理 issubclass 对未继承但成员齐全的类也返回 True", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `print(&#39;protocol_members&#39;, sorted(get_protocol_member` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;is_protocol&#39;, Engine._is_protocol)` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `class MemoryEngine:` 的作用，可对照上方输出逐项核对。", "这一行 `def __init__(self):` 的作用，可对照上方输出逐项核对。", "这一行 `self._d = {}` 的作用，可对照上方输出逐项核对。", "这一行 `def get(self, key):` 的作用，可对照上方输出逐项核对。", "这一行 `return self._d.get(key)` 的作用，可对照上方输出逐项核对。", "这一行 `def set(self, key, value):` 的作用，可对照上方输出逐项核对。", "这一行 `self._d[key] = value` 的作用，可对照上方输出逐项核对。", "这一行 `def delete(self, key):` 的作用，可对照上方输出逐项核对。", "这一行 `self._d.pop(key, None)` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `print(&#39;isinstance_memory&#39;, isinstance(MemoryEngine()` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;structural_issubclass&#39;, issubclass(MemoryEngi` 的作用，可对照上方输出逐项核对。"]' title='扩展示例逐行讲解' />


## 窄接口、错误层级与四讲共用的契约测试

贯穿线要求存储引擎、网络层、持久化、分片依次替换而命令语义不变，接口宽度就是第一个架构决策。

把接口收窄到 get / set / delete 三个方法，加上可选的 ttl 与 close，替换点才只有一处：任何新实现只需满足这三个方法，命令层、过期逻辑、错误映射都不改；一旦把内部 dict、游标或连接池方法漏进接口，后面每加一层都要回去改调用点。

错误语义同样要抽象成类型层级而不是裸 KeyError：定义 KVError 基类，分出 KeyNotFound（数据问题，返回空）与 CommandError（协议或代码 bug，应告警），网络层把断连映射成 CommandError，WAL 层把校验失败映射成同类，调用方 except 的分支才稳定。

让行为不变可验证的是把契约测试写成参数化用例：对 SET、GET、GET 缺失、DEL、TTL 过期、值含换行等固定输入与期望输出录成表，用一个 for engine in engines 循环对每个实现跑同一组断言。

四种实现共用这一组用例，是渐进式演进里唯一能证明换实现没改语义的证据；契约测试不是单元测试的补充，它就是接口的可执行规范。

**接口抽象的两种子类型与契约强度**

| 机制 | 判定方式 | 源码位置 | 代价与适用 |
| --- | --- | --- | --- |
| typing.Protocol（结构化） | 成员名子集匹配，仅查存在性 | Lib/typing.py _ProtocolMeta | 实现零耦合，静态期才校验签名 |
| @runtime_checkable | __instancecheck__ 逐成员探测 | Lib/typing.py | 不校验注解、不执行方法 |
| abc.ABC + @abstractmethod | 名义子类型，实例化强制实现 | Lib/abc.py、Objects/typeobject.c | 要求继承，实现被绑进类树 |
| get_protocol_members | 读取 __protocol_attrs__ 集合 | Lib/typing.py（3.12+） | 用于自动生成契约测试 |
| KVError 错误层级 | 异常类型分支，非返回码 | 项目领域层 | 让 KeyNotFound 与 CommandError 可判定 |

<Quiz no='129-1' q='关于 @runtime_checkable 的 Protocol，哪一项准确？' :options='["isinstance 与 issubclass 只检查成员名是否存在，不校验注解与签名", "它会执行方法体以确认返回值类型", "它要求实现类必须显式继承该 Protocol", "它把方法签名编译进 C 层做静态分派"]' answer="0" explain='_ProtocolMeta 的 __instancecheck__ 用属性探测检查成员是否存在，运行时不做类型注解比对、不调用方法；签名正确性由静态检查器或契约测试保证，所以 issubclass 对未继承但成员齐全的类也返回 True。' />

<Exercise title='用 get_protocol_members 生成契约测试骨架' task='读取一个 Protocol 的成员集合，检查若干候选实现是否都具备这些成员，对缺失者打印缺项；用它验证给接口加方法会立刻暴露未同步的实现。' solution='from typing import Protocol, runtime_checkable, get_protocol_members\n\n@runtime_checkable\nclass Engine(Protocol):\n    def get(self, key): ...\n    def set(self, key, value): ...\n    def delete(self, key): ...\n\nclass Memory:\n    def get(self, key): return None\n    def set(self, key, value): pass\n    def delete(self, key): pass\n\nclass Partial:\n    def get(self, key): return None\n\ndef audit(proto, impl):\n    return sorted(m for m in get_protocol_members(proto) if not hasattr(impl, m))\n\nprint(&#39;memory_missing&#39;, audit(Engine, Memory))\nprint(&#39;partial_missing&#39;, audit(Engine, Partial))' explain='get_protocol_members 返回 Protocol 声明的成员集合，audit 对每个实现用 hasattr 查出缺项；Memory 返回空列表，Partial 缺 set 与 delete。把它放进 CI，任何人给接口加方法却漏改某个实现时测试立刻失败，接口演进不再靠人工记忆。' />


## 练习、自测与速记

<Exercise title='基础：给内存引擎补 TTL 过期' task='在 MemoryEngine 里加 exp 字典与逻辑时钟 now，实现 set(key, value, ttl) 与惰性删除的 get，验证推进时钟后读取抛 KeyNotFound。' solution='class E:\n    def __init__(self): self.d, self.exp, self.now = {}, {}, 0\n    def set(self, k, v, ttl=0):\n        self.d[k] = v\n        self.exp[k] = self.now + ttl if ttl else -1\n    def get(self, k):\n        if self.exp.get(k, -1) != -1 and self.exp[k] &lt;= self.now:\n            del self.d[k]; del self.exp[k]; raise KeyError(k)\n        if k not in self.d: raise KeyError(k)\n        return self.d[k]\ne = E(); e.set(&#39;a&#39;, &#39;1&#39;, ttl=3); print(e.get(&#39;a&#39;))\ne.now += 3\ntry:\n    e.get(&#39;a&#39;)\nexcept KeyError as err:\n    print(&#39;expired&#39;, type(err).__name__)' explain='第一次输出 1，推进 3 后抛 KeyError 并打印 expired KeyError。TTL 记绝对时刻、读时惰性清理，是内存版最轻量的过期实现。' />

<Exercise title='进阶：用同一组契约测试验收两个引擎' task='写 suite(make) 覆盖 SET/GET/DEL 与键不存在，分别用内存引擎与带日志的引擎运行，打印两次结果并解释接口替换的判据。' solution='class M:\n    def __init__(self): self.d = {}\n    def set(self,k,v): self.d[k]=v\n    def get(self,k):\n        if k not in self.d: raise KeyError(k)\n        return self.d[k]\nclass L(M):\n    def __init__(self): super().__init__(); self.log=[]\n    def set(self,k,v): self.log.append(k); super().set(k,v)\ndef suite(make):\n    e=make(); e.set(&#39;a&#39;,&#39;1&#39;); assert e.get(&#39;a&#39;)==&#39;1&#39;\n    try: e.get(&#39;x&#39;)\n    except KeyError: return &#39;pass&#39;\n    return &#39;violation&#39;\nprint(suite(M), suite(L))' explain='输出 pass pass。两个实现都满足同一组断言；新引擎只要通过这组契约就能替换，命令层无需改动。' />

<Quiz no='129-2' q='贯穿线第一讲为什么要先定义窄接口而不是直接用 dict？' :options='["存储引擎、网络层、持久化、分片要依次替换，窄接口让命令语义保持不变", "dict 性能不够", "Protocol 会自动持久化", "dict 不支持中文键"]' answer="0" explain='把会变的部分挡在 get/set/delete 窄接口后面，后续三讲替换实现时命令层与契约测试都不用改；直接暴露 dict 会让每个调用点都成为替换点。' />

<Quiz no='129-3' q='关于 TTL 过期，哪一项准确？' :options='["记绝对过期时刻、用 time.monotonic、读时惰性删除，冷键还需定期扫描补上", "记倒计时秒数最稳", "time.time 不受系统时间回拨影响", "惰性删除能回收所有过期冷键"]' answer="0" explain='绝对时刻加 time.monotonic 避免时钟回拨漂移；惰性删除只在被访问时触发，长期不访问的冷键要靠定期抽样扫描回收，Redis 正是两者组合。' />

<Quiz no='129-4' q='GIL 已经保证原子，为什么读—检查—删还要加锁？' :options='["该操作跨 BINARY_OP、STORE_SUBSCR 等多条字节码，切换可发生在中间", "GIL 只保护 C 扩展", "加锁是为了绕过 GIL", "dict 本身不是线程安全的"]' answer="0" explain='GIL 保证的是单条字节码层面的原子性；dis 可见复合自增是多指令，读—检查过期—删同样跨多步，必须整体加锁，高并发再按 key 做锁分片。' />

<KnowledgeCard :points='["命令用 frozen dataclass 表达 (op,key,value,ttl)；错误语义自定义 KVError 层级，别用裸 KeyError", "存储引擎窄接口只有 get/set/delete，用 typing.Protocol（PEP 544，3.8）声明，实现类靠结构化子类型满足", "TTL 记绝对过期时刻 + time.monotonic；惰性删除简单但冷键需定期抽样扫描，SET 时要清旧 exp", "GIL 只保证单条字节码原子，读—检查—删是多指令复合操作，必须 threading.Lock 整体包住", "高并发用 hash(key) % N 锁分片；内置 hash 随机化只影响分片选择，不影响正确性", "契约测试对每个实现跑同一组断言，是四讲演进中安全替换的唯一证据；基准要预热并记 p99"]' :pitfalls='["命令层直接读写全局 dict", "用裸 KeyError 表示所有错误", "认为 GIL 让读—检查—删天然安全", "一开始就把 dict 直接暴露给命令层，后面加网络与持久化时必须重写全部调用点"]' summary='贯穿式项目的关键是把「会变的部分」挡在接口后面：存储引擎、网络层、持久化、分片依次替换，上层命令语义始终不变' />

1. 命令用 frozen dataclass 表达 (op,key,value,ttl)；错误语义自定义 KVError 层级，别用裸 KeyError

2. 存储引擎窄接口只有 get/set/delete，用 typing.Protocol（PEP 544，3.8）声明，实现类靠结构化子类型满足

3. TTL 记绝对过期时刻 + time.monotonic；惰性删除简单但冷键需定期抽样扫描，SET 时要清旧 exp

[下一讲：实战 09 · KV 贯穿线 ② 协议帧与网络层](/projects/kv-network)

```bash
python -m compileall -q . && python -m pytest -q
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 命令模型与协议设计 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

<Predict no='129-5' q='ttl=3 的键在逻辑时钟推进 3 后再 GET，契约测试最可能的结果是？' :options='["抛 KeyNotFound，契约返回 ok", "仍返回原值", "返回 None"]' answer='0' output='contract ok' explain='过期时刻是 now + ttl，推进到相等时按 &lt;= 判为失效；惰性删除在 get 里清掉键并抛 KeyNotFound，契约函数捕获它返回 ok。' />

<FillBlank no='129-6' tpl='___ threading' :answers='["import"]' hint='回想本讲关于 命令模型与协议设计 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 命令模型与窄接口：把变化挡在抽象后面 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/129-kv-memory.py`

```bash
python3 examples/lessons/129-kv-memory.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/129-kv-memory.py) · [全部示例代码索引](/examples/)
