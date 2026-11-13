---
title: 第 032 讲 · 装饰器原理与 functools.wraps
description: 从零实现并正确调试装饰器
---

<StageHeader stage='L3 · 函数与抽象' level='★★★☆☆' time='35 分钟' goal='从零实现并正确调试装饰器' prereq='第 031 讲 · 高阶函数、lambda 与 map / filter / reduce' />

# 第 032 讲 · 装饰器原理与 functools.wraps

函数既然能当值传来传去，不动原函数而给它添一层也就顺理成章。装饰器对付的是日志、计时、缓存、鉴权这类横切需求，不该反复抄进每个函数体。一个服务上线后想给若干接口都记下耗时，最省事的不是逐个去改，而是统一披一层外衣，调用方还毫无察觉。

我们先弄清装饰器即一次在导入期发生的函数替换，再谈为何要靠 wraps 把名字、文档和签名搬回包装后的对象；最后做一版能记住状态的装饰器，看闭包怎样留住计数。需要一等对象、闭包与高阶函数；掌握后你能从零写出装饰器，也能解释日志里函数名为何忽然全变成同一个词。


## 日志里所有函数都叫 wrapper

给所有视图函数加一个计时日志装饰器，上线后发现 APM 里所有接口都叫 wrapper，文档生成工具导出的函数签名全是 (*args, **kwargs)，某个按参数名做依赖注入的框架直接注入失败。

原因很朴素：装饰器本质是一次函数替换，运行期拿到的是 wrapper 而不是原函数，而没写 `functools.wraps` 时元数据全部丢失。

另一个坑是有人以为 @ 那行在请求进来时才执行，其实它在模块导入时就把函数换掉了，副作用（注册路由、连库）也发生在导入阶段；包装 async def 时若用同步 wrapper，拿到的还只是个协程对象。本讲从 @ 的等价展开、闭包保存原函数、wraps 搬回哪些字段、以及带状态计数器讲起，把装饰器变成可推导、可调试的东西。

<Callout type="warn" title='先看一个真实会出错的写法' text='不写 functools.wraps，所有函数都叫 wrapper：装饰器返回的是新函数，元数据没搬回来，日志 / 文档 / 依赖注入全部失真' />


## 先有模型：装饰器是一次函数替换

<Callout type="tip" title='核心心智模型' text='@deco 紧跟在 def f 之前，等价于在 def 执行完之后立即执行 f = deco(f)：deco 在模块导入、执行到该语句时被调用一次，不是每次调用 f 时。装饰器是接收一个可调用、返回一个可调用的对象，返回值被绑定到原名字，之后所有调用走的是包装后的函数。因为替换发生在导入期，装饰器里' />

<ConceptDiagram type='layers3' title='第 032 讲 · @ 语法的求值时机与函数替换' labels='@ 语法的求值时机与函数替换|functools.wraps 到底搬回了什|带状态装饰器、闭包与常见应用' caption='从零实现并正确调试装饰器' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段三 · 函数与抽象 |
| 前置 | 第 031 讲 · 高阶函数、lambda 与 map / filter / reduce |
| 难度 / 建议时长 | ★★★☆☆ · 35 分钟 |
| 本讲新增 | 装饰器即函数替换、@ 语法的求值时机、wraps 保留元数据 |
| 一句话目标 | 从零实现并正确调试装饰器 |
| 为下一讲铺垫 | 带参装饰器、叠加顺序与类装饰器 |


## @ 语法的求值时机与函数替换

@deco 紧跟在 def f 之前，等价于在 def 执行完之后立即执行 `f = deco`(f)：deco 在模块导入、执行到该语句时被调用一次，不是每次调用 f 时。装饰器是接收一个可调用、返回一个可调用的对象，返回值被绑定到原名字，之后所有调用走的是包装后的函数。

因为替换发生在导入期，装饰器里的顶层副作用（注册路由、打开连接、读配置）也在导入时执行，这正是 Web 框架靠装饰器收集路由、插件系统靠装饰器完成发现的原因。用等价写法可以验证：def f... 之后写 `f = deco`(f)，得到的 `__name__` 与行为与 @deco 完全一致。

多个装饰器叠加时从下往上依次替换（第 033 讲展开顺序）。装饰器可作用于函数、方法与类；接收函数时，返回值通常是函数或实现了 `__call__` 的对象。

还要注意装饰不改变函数本身是同步还是异步：包装 async def 时 wrapper 也得是 async def 并 return await `fn(...)`，否则同步 wrapper 只拿到一个协程对象，异常与计时都落空。

```python
from functools import wraps
import inspect

def log_bad(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

def log_good(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

def area(w, h):
    return w * h
def volume(w, h, d):
    return w * h * d

bad = log_bad(area)
good = log_good(volume)
print(bad.__name__, inspect.signature(bad))
print(good.__name__, inspect.signature(good))
print(hasattr(bad, '__wrapped__'), hasattr(good, '__wrapped__'))
print(inspect.signature(good, follow_wrapped=False))
print(bad(2, 3), good(2, 3, 4))
```

<OutputBox title='主示例运行结果' output='wrapper (*args, **kwargs)\nvolume (w, h, d)\nFalse True\n(*args, **kwargs)\n6 24' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from functools import wraps\nimport inspect\n\ndef log_bad(fn):\n    def wrapper(*args, **kwargs):\n        return fn(*args, **kwargs)\n    return wrapper\n\ndef log_good(fn):\n    @wraps(fn)\n    def wrapper(*args, **kwargs):\n        return fn(*args, **kwargs)\n    return wrapper\n\ndef area(w, h):\n    return w * h\ndef volume(w, h, d):\n    return w * h * d\n\nbad = log_bad(area)\ngood = log_good(volume)\nprint(bad.__name__, inspect.signature(bad))\nprint(good.__name__, inspect.signature(good))\nprint(hasattr(bad, &#39;__wrapped__&#39;), hasattr(good, &#39;__wrapped__&#39;))\nprint(inspect.signature(good, follow_wrapped=False))\nprint(bad(2, 3), good(2, 3, 4))' :notes='["导入 wraps，用于把元数据从原函数搬到 wrapper", "导入 inspect，signature 用来验证装饰前后的签名差异", "定义不带 wraps 的装饰器", "wrapper 用 *args / **kwargs 透传任意实参", "调用原函数并返回结果", "返回包装函数，完成一次函数替换", "定义带 wraps 的装饰器", "@wraps(fn) 把名字、文档、注解与 __wrapped__ 装到 wrapper", "wrapper 同样透传实参", "调用原函数", "返回包装后的函数", "定义被装饰的二参数函数 area", "返回面积", "定义三参数函数 volume", "返回体积", "显式写 f = deco(f)，与 @log_bad 完全等价", "显式写 f = deco(f)，与 @log_good 完全等价", "没 wraps：名字是 wrapper，签名退化成 (*args, **kwargs)", "有 wraps：名字是 volume，signature 沿 __wrapped__ 还原", "只有 wraps 版本才带 __wrapped__ 属性", "关闭 follow_wrapped 后看到的是 wrapper 自身签名", "两次调用都返回正确结果，装饰不改变业务逻辑"]' title='第 032 讲 · 装饰器原理与 functools.wraps' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import inspect, functools
from functools import wraps

def deco(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        return fn(*a, **k)
    return wrapper

def orig(x):
    return x

w = deco(orig)
print(w.__name__, inspect.signature(w))
print('__wrapped__' in w.__dict__)
print(inspect.unwrap(w) is orig)
print('__name__' in functools.WRAPPER_ASSIGNMENTS, '__doc__' in functools.WRAPPER_ASSIGNMENTS)
```

<OutputBox title='原理验证' output='orig (x)\nTrue\nTrue\nTrue True' />


### 导入时替换，调用时只见包装层

**装饰器执行时机与叠加顺序**

| 问题 | 答案 | 可核对细节 |
| --- | --- | --- |
| @deco 何时执行 | 模块导入执行到该 def 时 | 等价 f = deco(f)，副作用在导入期发生 |
| 装饰发生几次 | 一次 | 每次调用 f 走 wrapper，不重新装饰 |
| 多个装饰器的包装顺序 | 自下而上依次替换 | f = d1(d2(f))，第 033 讲展开调用顺序 |
| classmethod / staticmethod 顺序 | staticmethod 通常置最外层 | 否则绑定行为与签名会错 |

<FlowTimeline :steps='[{"title": "@ 语法的求值时机与函数替换", "desc": "@deco 紧跟在 def f 之前，等价于在 def 执行完之后立即执行 f = …", "tone": "blue"}, {"title": "functools.wraps 到底搬回了什么", "desc": "不写 wraps，wrapper 的 __name__ 是字符串 wrapper、_…", "tone": "purple"}, {"title": "带状态装饰器、闭包与常见应用", "desc": "计数器、命中率这类状态可以用闭包自由变量加 nonlocal 保存：wrapper …", "tone": "orange"}, {"title": "工程落地", "desc": "可禁用、可观测、可单测的计时装饰器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## functools.wraps 到底搬回了什么

不写 wraps，wrapper 的 `__name__` 是字符串 wrapper、`__doc__` 是 None、`__annotations__` 是空字典，`inspect.signature` 看到的是 (*args, **kwargs)：日志聚合、Sphinx 文档、按名字的测试收集、依赖注入会同时失真。

`functools.wraps` 是 `functools.update_wrapper` 的偏函数式封装：它按 WRAPPER_ASSIGNMENTS（默认含 `__module__`、`__name__`、`__qualname__`、`__annotations__`、`__doc__`，3.12 起还含 `__type_params__`）逐个从被包装函数复制字段，再执行 `wrapper.__dict__.update(wrapped.__dict__)` 保留自定义属性，最后设置 `wrapper.__wrapped__ = wrapped`。

其中 `__wrapped__` 最关键：`inspect.signature` 默认 `follow_wrapped=True`，会沿这条链一路解包到没有 `__wrapped__` 的函数再取签名，所以加了 wraps 才能把签名还原成 (w, h, d)；

`inspect.unwrap` 能显式取到最内层的原函数。wraps 还提供 assigned 与 updated 参数用于裁剪复制项。要清楚 wraps 只搬元数据，调用链仍然走 wrapper，f 与 `f.__wrapped__` 用 is 判断为假。

**functools.wraps 复制与设置的字段**

| 字段 | 来源 | 作用 | 不设置的后果 |
| --- | --- | --- | --- |
| __module__ / __name__ / __qualname__ | WRAPPER_ASSIGNMENTS | 日志与测试收集显示真实名字 | 全叫 wrapper，APM 与 pytest 收集失真 |
| __doc__ / __annotations__ | WRAPPER_ASSIGNMENTS | 文档生成与注解读取 | 文档为空、类型信息丢失 |
| __dict__ | update(wrapped.__dict__) | 保留原函数自定义属性 | 自定义标记丢失 |
| __wrapped__ | update_wrapper 额外设置 | inspect.signature / unwrap 沿链解包 | 签名显示 (*args, **kwargs)，依赖注入失败 |

<Compare :panels='[{"label": "主示例", "code": "from functools import wraps\nimport inspect\n\ndef log_bad(fn):\n    def wrapper(*args, **kwargs):\n        return fn(*args, **kwargs)\n    return wrapper\n\ndef log_good(fn):\n    @wraps(fn)\n    def wrapper(*args, **kwargs):\n        return fn(*args, **kwargs)\n    return wrapper\n\ndef area(w, h):\n    return w * h\ndef volume(w, h, d):\n    return w * h * d\n\nbad = log_bad(area)\ngood = log_good(volume)\nprint(bad.__name__, inspect.signature(bad))\nprint(good.__name__, inspect.signature(good))\nprint(hasattr(bad, &#39;__wrapped__&#39;), hasattr(good, &#39;__wrapped__&#39;))\nprint(inspect.signature(good, follow_wrapped=False))\nprint(bad(2, 3), good(2, 3, 4))", "note": "@ 语法的求值时机与函数替换"}, {"label": "对照 / 进阶", "code": "from functools import wraps\n\nevents = []\ndef register(name):\n    def deco(fn):\n        events.append(name)\n        @wraps(fn)\n        def wrapper(*a, **k):\n            return fn(*a, **k)\n        return wrapper\n    return deco\n\ndef counted(fn):\n    n = 0\n    @wraps(fn)\n    def wrapper(*a, **k):\n        nonlocal n\n        n += 1\n        wrapper.calls = n\n        return fn(*a, **k)\n    wrapper.calls = 0\n    return wrapper\n\n@register(&#39;task&#39;)\ndef job(x):\n    return x + 1\n\n@counted\ndef work(x):\n    return x * 2\n\nprint(events)\nprint(job.__name__)\nprint(work(1), work(2), work.calls)", "note": "functools.wraps 到底搬回了什么"}]' title='两种写法对照' note='差异集中在 装饰器即函数替换；先看输出，再找背后的规则。' />


### WRAPPER_ASSIGNMENTS 与 __wrapped__

<Term word='装饰器即函数替换' text='@deco 紧跟在 def f 之前，等价于在 def 执行完之后立即执行 f = deco(f)：deco 在模块导入、执行到该语句时被调用一次，不是每次调用 f 时。装饰器是接收一个可调用、返回一个可调用的对象，返回值被绑定到原名字，之后所有调用走的是包装后的函数。因为替换发生在导入期，装饰器里的顶层副作用（注册路' />

<Term word='@ 语法的求值时机' text='不写 wraps，wrapper 的 __name__ 是字符串 wrapper、__doc__ 是 None、__annotations__ 是空字典，inspect.signature 看到的是 (*args, **kwargs)：日志聚合、Sphinx 文档、按名字的测试收集、依赖注入会同时失真。functool' />


## 从闭包 cell 到元数据搬运的底层

@ 是纯语法糖：编译器把 @deco 紧跟的 def 编译成一段模块级字节码——先 MAKE_FUNCTION 生成原函数对象压栈，再 LOAD 装饰器对象、CALL 调用它，最后把返回值 STORE 回原名字，整个序列随模块导入执行一次。

装饰器返回的 wrapper 是一个全新的函数对象，它通过闭包 cell 保存原函数引用（wrapper 的 co_freevars 里有 fn，读取走 LOAD_DEREF），因此调用链是 wrapper 再到 fn。

update_wrapper 的实现很直接：遍历 WRAPPER_ASSIGNMENTS，用 getattr 从 wrapped 取值、setattr 到 wrapper，缺失字段跳过；

随后 `wrapper.__dict__.update(wrapped.__dict__)`，最后设 `__wrapped__ = wrapped`。

`inspect.signature` 默认 `follow_wrapped=True`，会沿 `__wrapped__` 链一路 unwrap 到没有该属性的函数再取签名，所以加了 wraps 才能还原 (w, h, d)；

`inspect.unwrap` 做的是同一件事。这也解释了身份变化：f 本身是 wrapper，`f.__wrapped__` 才是原函数，二者用 is 比较为假。

<ConceptDiagram type='layers3' title='第 032 讲 · 分层视角' labels='@ 语法的求值时机与函数替换|functools.wraps 到底搬回|带状态装饰器、闭包与常见应用|常见应用' caption='带状态装饰器、闭包与常见应用' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **常见应用** 落在哪一层。

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：不写 functools.wraps，所有函", "body": "装饰器返回的是新函数，元数据没搬回来，日志 / 文档 / 依赖注入全部失真", "tip": "在 wrapper 上加 @wraps(fn)，或直接调 functools.update_wrapper(wrapper, fn)"}, {"title": "第 2 步：以为 @deco 在每次请求时执行", "body": "装饰在模块导入期发生一次、只是替换名字；顶层的注册与连库副作用也在导入时触发", "tip": "把运行期逻辑放进 wrapper，把一次性副作用明确写在装饰器里并加可控开关"}, {"title": "第 3 步：包装 async def 却用了同步 wra", "body": "同步 wrapper 直接返回协程对象，日志拿不到结果、异常也不会经过 wrapper 的 try / except", "tip": "wrapper 定义为 async def 并 return await fn(*a, **k)，或用 inspect.iscoroutinefunction 分支处理"}]' />


## 带状态装饰器、闭包与常见应用

计数器、命中率这类状态可以用闭包自由变量加 nonlocal 保存：wrapper 的 co_freevars 里会有该名字，读写走 LOAD_DEREF / STORE_DEREF，每次调用递增。

但模块级装饰器若被多个函数共用，闭包状态的共享范围要设计清楚，用函数属性 `fn.count`、或改用类装饰器（第 033 讲）把状态放到实例属性往往更好读也好测。典型应用包括缓存（第 034 讲 lru_cache）、鉴权、重试（带指数退避与次数上限）、计时、事务边界与注册。

工程上有三条硬要求：可禁用，用环境变量或 enabled 开关让装饰器直接返回原函数，便于测试与灰度；可观测，靠 wraps 保留 `__name__` 让日志与指标带上真实名字；可单测，借 `__wrapped__` 拿到未包装逻辑单独验证，不必穿透日志与重试。

叠加顺序也影响绑定：classmethod / staticmethod 与自定义装饰器一起用时，staticmethod 通常放最外层，否则方法绑定与签名会错乱。

```python
from functools import wraps

events = []
def register(name):
    def deco(fn):
        events.append(name)
        @wraps(fn)
        def wrapper(*a, **k):
            return fn(*a, **k)
        return wrapper
    return deco

def counted(fn):
    n = 0
    @wraps(fn)
    def wrapper(*a, **k):
        nonlocal n
        n += 1
        wrapper.calls = n
        return fn(*a, **k)
    wrapper.calls = 0
    return wrapper

@register('task')
def job(x):
    return x + 1

@counted
def work(x):
    return x * 2

print(events)
print(job.__name__)
print(work(1), work(2), work.calls)
```

<OutputBox title='对照写法：先自己猜，再点开' output='[&#39;task&#39;]\njob\n2 4 2' guess="true" />

<Predict no='032-P' q='def deco(fn): def wrapper(*a,**k): return fn(*a,**k); return wrapper；@deco def f(x): return x；print(f.__name__, inspect.signature(f)) 输出？' :options='["wrapper (*args, **kwargs)", "f (x)", "wrapper (x)", "f (*args, **kwargs)"]' answer='0' output='wrapper (*args, **kwargs)' explain='没有 wraps 就没有 __wrapped__，名字与签名都来自 wrapper 本身：__name__ 是 wrapper，签名是它声明的 (*args, **kwargs)。' />


## 典型应用与必须提供的开关

**典型装饰器应用与必须提供的开关**

| 应用 | 实现要点 | 风险 |
| --- | --- | --- |
| 计时 / 日志 | 用 wraps 保留 __name__，日志带名字 | 无 wraps 时指标全聚合到 wrapper |
| 鉴权 | 调用前校验，失败直接抛或返回 | 被缓存包住会把未授权结果缓存（第 033 讲） |
| 重试 | 仅幂等操作、带退避与次数上限 | 非幂等写操作重试会重复扣款 |
| 缓存 | 第 034 讲 lru_cache，键须可哈希 | 可变参数或副作用函数会串数据 |
| 可禁用 / 可测试 | 开关直接返回原函数，借 __wrapped__ 单测 | 测试与灰度环境需要绕开装饰 |

<Callout type="warn" title='本讲最容易踩的坑' text='不写 functools.wraps，所有函数都叫 wrapper：装饰器返回的是新函数，元数据没搬回来，日志 / 文档 / 依赖注入全部失真' />

<CheckList id='P032a' title='学完你应当能' :items='["能讲清 @ 语法的求值时机与函数替换", "能讲清 functools.wraps 到底搬回了什么", "能讲清 带状态装饰器、闭包与常见应用", "能在工程里处理 常见应用"]' />


## 不写 wraps 的代价与 async 陷阱

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 不写 functools.wraps，所有函数都叫 wrapper | 装饰器返回的是新函数，元数据没搬回来，日志 / 文档 / 依赖注入全部失真 | 在 wrapper 上加 @wraps(fn)，或直接调 functools.update_wrapper(wrapper, fn) |
| 以为 @deco 在每次请求时执行 | 装饰在模块导入期发生一次、只是替换名字；顶层的注册与连库副作用也在导入时触发 | 把运行期逻辑放进 wrapper，把一次性副作用明确写在装饰器里并加可控开关 |
| 包装 async def 却用了同步 wrapper | 同步 wrapper 直接返回协程对象，日志拿不到结果、异常也不会经过 wrapper 的 try / except | wrapper 定义为 async def 并 return await fn(*a, **k)，或用 inspect.iscoroutinefunction 分支处理 |

```bash
python -c "from functools import lru_cache; f=lru_cache(64)(lambda x:x*x); print(f(4))"
```

把输入换成你自己的数据，观察结果是否仍符合 **装饰器即函数替换** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 可禁用、可观测、可单测的计时装饰器

生产环境的计时装饰器至少要满足三点：一个开关能在测试与灰度里彻底绕开包装；用 wraps 让日志与指标带上真实函数名；把被装饰函数的原始逻辑通过 `__wrapped__` 暴露出来，方便单元测试直接验证业务而不必穿透计时代码。下面实现一个带参装饰器 `timed(enabled)`，未启用时直接返回原函数；

启用时把每次耗时记到 wrapper 的 last_ms 属性，并用 try / finally 保证函数抛异常时也能记录耗时。最后演示通过 `__wrapped__` 直接调用原始逻辑、以及关闭开关后拿回的是普通函数。真实项目还应把耗时上报到指标系统，并给异常路径单独打点。

```python
import time
from functools import wraps

def timed(enabled=True):
    def deco(fn):
        if not enabled:
            return fn
        @wraps(fn)
        def wrapper(*a, **k):
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                wrapper.last_ms = (time.perf_counter() - t0) * 1000
        wrapper.last_ms = 0.0
        return wrapper
    return deco

@timed()
def fetch(n):
    return sum(range(n))

print(fetch.__name__, fetch(1000))
print(fetch.last_ms >= 0, fetch.__wrapped__(1000))

@timed(False)
def raw(x):
    return x
print(type(raw).__name__, raw(9), hasattr(raw, '__wrapped__'))
```

<Callout type="idea" title='落地提示' text='缓存、鉴权、重试、计时、事务边界都适合做成装饰器，但要保证可禁用、可观测、可单独测试' />

<CheckList id='P032b' title='上线前自检' :items='["能复现并解释「不写 functools.wraps，所有函数都叫 wrap」", "能复现并解释「以为 @deco 在每次请求时执行」", "能复现并解释「包装 async def 却用了同步 wrapper」", "能用一条命令验证 装饰器即函数替换", "关键路径有自动化测试与失败分支"]' />


## 计时装饰器的练习与自测

<Exercise title='基础：对比有无 wraps 的元数据' task='写两个装饰器，一个不 wraps、一个用 @wraps，分别包装同一个函数，打印包装后对象的 __name__ 与 inspect.signature。' solution='import inspect\nfrom functools import wraps\n\ndef deco(fn):\n    def wrapper(*a, **k):\n        return fn(*a, **k)\n    return wrapper\n\ndef deco2(fn):\n    @wraps(fn)\n    def wrapper(*a, **k):\n        return fn(*a, **k)\n    return wrapper\n\ndef f(x):\n    return x\nprint(deco(f).__name__, inspect.signature(deco(f)))\nprint(deco2(f).__name__, inspect.signature(deco2(f)))' explain='不带 wraps 得到 wrapper 与 (*args, **kwargs)；带 wraps 因设置了 __wrapped__，名字还原为 f、签名还原为 (x)。' />

<Exercise title='进阶：实现带状态的计数器装饰器' task='用闭包自由变量加 nonlocal 记录调用次数，把次数同步到 wrapper 的函数属性上，并用 wraps 保留名字，验证三次调用的结果。' solution='from functools import wraps\n\ndef counted(fn):\n    n = 0\n    @wraps(fn)\n    def wrapper(*a, **k):\n        nonlocal n\n        n += 1\n        wrapper.calls = n\n        return fn(*a, **k)\n    wrapper.calls = 0\n    return wrapper\n\n@counted\ndef add(a, b):\n    return a + b\nprint(add(1, 2), add(3, 4), add.calls, add.__name__)' explain='nonlocal 改写闭包 cell，函数属性把状态暴露给外部读取，wraps 保证 __name__ 仍是 add；状态也可用类装饰器存到实例属性。' />

<Quiz no='032-1' q='@deco 这一行在什么时候执行？' :options='["模块导入执行到该 def 时，等价于 f = deco(f)", "每次调用 f 时", "第一次访问 f.__name__ 时", "垃圾回收时"]' answer="0" explain='装饰是模块顶层的一次赋值替换，随导入发生且只发生一次；运行期每次调用走的是 wrapper。' />

<Quiz no='032-2' q='functools.wraps 里让 inspect.signature 能还原签名的是哪一项？' :options='["设置 __wrapped__ 指向原函数", "复制 __doc__", "改写 __name__", "清空 __dict__"]' answer="0" explain='inspect.signature 默认 follow_wrapped=True，沿 __wrapped__ 链解包；没有它就只能看到 wrapper 的 (*args, **kwargs)。' />

<Quiz no='032-3' q='包装一个 async def 函数，正确做法是？' :options='["wrapper 也用 async def 并 return await fn(...)", "同步 wrapper 里直接返回 fn(...)", "把 fn 改成同步函数", "用 threading 再包一层"]' answer="0" explain='同步 wrapper 只会拿到协程对象，结果与异常都不经过包装逻辑；async wrapper 才能 await 到真实返回值与异常。' />

<FillBlank no='032-F' tpl='from functools  ___ wraps' :answers='["import"]' hint='回想本讲关于 装饰器即函数替换 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 @ 语法的求值时机与函数替换 的落点。' />

<KnowledgeCard :points='["@deco 等价于 def 后立即 f = deco(f)，在模块导入期执行一次；运行期调用的是 wrapper", "装饰器接收可调用、返回可调用；wrapper 用闭包 cell（co_freevars 含 fn）保存原函数", "不写 wraps：__name__ 为 wrapper、__doc__ 为 None、签名 (*args, **kwargs)，日志 / 文档 / 依赖注入失真", "functools.wraps 即 update_wrapper：复制 WRAPPER_ASSIGNMENTS、update __dict__、设置 __wrapped__", "inspect.signature 默认 follow_wrapped=True 沿 __wrapped__ 解包；inspect.unwrap 可取到最内层原函数", "装饰器要可禁用（开关返回原函数）、可观测（wraps 保名）、可单测（借 __wrapped__）；包装 async def 需用 async wrapper"]' :pitfalls='["不写 functools.wraps，所有函数都叫 wrapper", "以为 @deco 在每次请求时执行", "包装 async def 却用了同步 wrapper", "不写 wraps 会让所有被装饰函数都叫 wrapper，日志、文档生成、依赖注入与调试全部失真"]' summary='装饰器在模块导入时就执行替换，运行期看到的是包装后的函数；wraps 负责把 __name__、__doc__、签名等元数据搬回来' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| @deco 等价于 def 后立即 f = deco(f)，在模块导入期执行一次；运行期调用的是 wrapper | 建立直觉 |
| 装饰器接收可调用、返回可调用；wrapper 用闭包 cell（co_freevars 含 fn）保存原函数 | 跑通示例 |
| 不写 wraps：__name__ 为 wrapper、__doc__ 为 None、签名 (*args, **kwargs)，日志 / 文档 / 依赖注入失真 | 深入边界 |
| functools.wraps 即 update_wrapper：复制 WRAPPER_ASSIGNMENTS、update __dict__、设置 __wrapped__ | 工程落地 |
| inspect.signature 默认 follow_wrapped=True 沿 __wrapped__ 解包；inspect.unwrap 可取到最内层原函数 | 随堂检测 |
| 装饰器要可禁用（开关返回原函数）、可观测（wraps 保名）、可单测（借 __wrapped__）；包装 async def 需用 async wrapper | 复盘 |

1. @deco 等价于 def 后立即 f = deco(f)，在模块导入期执行一次；运行期调用的是 wrapper

2. 装饰器接收可调用、返回可调用；wrapper 用闭包 cell（co_freevars 含 fn）保存原函数

3. 不写 wraps：__name__ 为 wrapper、__doc__ 为 None、签名 (*args, **kwargs)，日志 / 文档 / 依赖注入失真

[下一讲：带参装饰器、叠加顺序与类装饰器](/functions/decorator-params)
