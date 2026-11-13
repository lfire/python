---
title: 第 033 讲 · 带参装饰器、叠加顺序与类装饰器
description: 处理生产环境里的装饰器组合
---

<StageHeader stage='L3 · 函数与抽象' level='★★★☆☆' time='30 分钟' goal='处理生产环境里的装饰器组合' prereq='第 032 讲 · 装饰器原理与 functools.wraps' />

# 第 033 讲 · 带参装饰器、叠加顺序与类装饰器

上一版装饰器已能安静包住函数，真实项目里却还想带上参数，比如缓存多久、重试几次。这一讲把装饰器从能用推到能组合，处理几件外衣叠在一起时的先后与状态。给同一个接口既加鉴权又加缓存，顺序摆反，未授权的结果也可能被存下来，问题藏得很深。

先拆开带参装饰器那三层函数各管什么，少一层会怎样；再用打印标记核对叠加顺序，记住包装自下而上、执行自上而下；最后换成类来当装饰器，让状态有个规整住处。延续刚写过的无参装饰器，再带上默认参数与闭包；做完你能从容安排生产环境里的装饰器组合。


## 一次越权结果被缓存的线上事故

给接口加缓存和鉴权两个装饰器，写成 @cache 在上还是 @auth 在上，团队里争了半天，上线后选错顺序：缓存把鉴权失败的结果也缓存了下来，未授权用户在 TTL 内一直拿到不该看的响应。

另一个新人写带参装饰器 @`repeat(3)` 时少返回一层，得到 TypeError 提示某个对象不可调用、或看似无关的缺少参数报错，查半天定位不到是哪一层断了。

本讲把三层函数结构、从下往上包装从上往下执行、类装饰器用 `__call__` 与状态保存讲清楚，并给出可 bypass 的工程写法，让装饰器组合从碰运气变成可推导。

<Callout type="warn" title='先看一个真实会出错的写法' text='带参装饰器少写一层 return，报 TypeError: &#39;NoneType&#39; object is not callable：外层没返回 deco 或中层没返回 wrapper，得到 None 却被当函数调用' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段三 · 函数与抽象 |
| 前置 | 第 032 讲 · 装饰器原理与 functools.wraps |
| 难度 / 建议时长 | ★★★☆☆ · 30 分钟 |
| 本讲新增 | 三层函数结构、叠加顺序由近及远、类作为装饰器 |
| 一句话目标 | 处理生产环境里的装饰器组合 |
| 为下一讲铺垫 | 偏函数、可调用对象与函数式工具 |

<Callout type="tip" title='核心心智模型' text='带参装饰器其实是装饰器工厂：def repeat(n): def deco(fn): def wrapper(*a, **k): ...; return wrapper; return deco。@repeat(3) 先调用 repeat(3) 得到 deco，再把 deco 应用到函数。三层职责分' />


## 三层函数结构与少一层的报错

带参装饰器其实是装饰器工厂：def `repeat(n)`: def `deco(fn)`: def `wrapper(*a, **k)`: ...; return wrapper; return deco。

@`repeat(3)` 先调用 `repeat(3)` 得到 deco，再把 deco 应用到函数。三层职责分明：外层接收配置参数、中层接收被装饰函数、内层接收每次调用的实参。

常见断点有三类：中层忘了 return wrapper，deco 返回 None，于是 f 变成 None，调用时报 TypeError: 'NoneType' object is not callable；外层忘了 return deco，`repeat(3)` 直接返回 None，@ 应用阶段就报同样的错；

写成 @repeat 漏了括号，则把函数对象本身当成配置 n 传进去，配置被当函数用，报出各种看似无关的 TypeError。

定位方法是逐层打印中间返回值，或用 `inspect.signature(repeat)` 确认外层只收配置。

不带参装饰器是两层（deco + wrapper），带参是三层，两者结构不要混用。

```python
from functools import wraps

def tag(label):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            print('enter', label)
            r = fn(*a, **k)
            print('exit', label)
            return r
        return wrapper
    return deco

@tag('outer')
@tag('inner')
def work(x):
    print('run', x)
    return x + 1

print(work(1))
print(work.__name__)
```

<OutputBox title='主示例运行结果' output='enter outer\nenter inner\nrun 1\nexit inner\nexit outer\n2\nwork' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from functools import wraps\n\ndef tag(label):\n    def deco(fn):\n        @wraps(fn)\n        def wrapper(*a, **k):\n            print(&#39;enter&#39;, label)\n            r = fn(*a, **k)\n            print(&#39;exit&#39;, label)\n            return r\n        return wrapper\n    return deco\n\n@tag(&#39;outer&#39;)\n@tag(&#39;inner&#39;)\ndef work(x):\n    print(&#39;run&#39;, x)\n    return x + 1\n\nprint(work(1))\nprint(work.__name__)' :notes='["导入 wraps，保证叠加后元数据仍指向原函数", "定义带参装饰器工厂，外层收标签配置", "中层接收被装饰函数", "用 wraps 把名字与 __wrapped__ 装到 wrapper", "内层接收每次调用的实参", "进入时打印标签，用于观察执行顺序", "调用下一层（可能是另一个 wrapper 或原函数）", "退出时再打印一条，finally 类清理会逆序", "把结果原样返回", "中层必须返回 wrapper，否则 f 会变成 None", "外层必须返回 deco，否则 @tag(...) 得到 None", "外层装饰器，定义时最后包装、成为最外层", "内层装饰器，定义时最先包装", "定义真正的业务函数", "打印一次运行标记", "返回结果值", "调用 work(1)：先看到各层 enter / exit，再打印返回值 2", "两层 wraps 传播后 __name__ 仍是 work"]' title='第 033 讲 · 带参装饰器、叠加顺序与类装饰器' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**带参装饰器三层函数的职责与断点**

| 层 | 接收 | 返回 | 少一层 return 的报错 |
| --- | --- | --- | --- |
| 外层 repeat(n) | 配置参数 | 装饰器 deco | repeat(3) 得 None，@ 应用报 NoneType not callable |
| 中层 deco(fn) | 被装饰函数 | 包装函数 wrapper | f 变 None，调用报 NoneType not callable |
| 内层 wrapper(*a, **k) | 调用实参 | 原函数结果 | 返回 None，调用方拿到 None |
| @repeat 漏括号 | 把函数当配置传入 | 结构错乱 | 配置被当函数，报 TypeError |


## 叠加顺序：包装自下而上、执行自上而下

@d1 / @d2 / def f 等价于 `f = d1`(`d2(f)`)：定义时离 def 最近的 d2 先包装，d1 后包装并成为最外层对象。调用时从最外层进入，顺序是 `d1.wrapper` → `d2.wrapper` → f，也就是从上往下执行；返回时各层的 finally 清理再逆序退出。

顺序错会出真实事故：@cache 在外、@auth 在内时，最外层 cache 一旦命中就直接返回，根本不会调用内层 auth，于是未授权结果被写进缓存并在 TTL 内反复返回；@auth 在外、@cache 在内才对。一般规律是越便宜、越该早失败的（鉴权、限流、参数校验）放外层，越昂贵、越依赖结果的（缓存、重试、计时）放靠内。

验证手段很直接：每个 wrapper 在调用前后各打印一条进入 / 退出标记，调用一次就能看到真实顺序；也可用 `__wrapped__` 链从外向内 unwrap。

与 classmethod / staticmethod / property 叠加时，内置装饰器要放最外层（staticmethod 最外），否则方法绑定与签名会错乱。

**叠加顺序与执行方向**

| 写法 / 维度 | 等价展开 / 方向 | 调用进入顺序 | 返回退出顺序 |
| --- | --- | --- | --- |
| @d1 / @d2 / def f | f = d1(d2(f)) | d1 → d2 → f | f → d2 → d1（finally 逆序） |
| 包装方向 | 自下而上，离 def 最近的先包 | — | — |
| @cache 在外 @auth 在内 | cache(auth(f)) | 命中缓存直接返回，跳过 auth | 未授权结果被缓存 |
| @auth 在外 @cache 在内 | auth(cache(f)) | 先鉴权再查缓存 | 正确：失败不进缓存 |

```python
import inspect
from functools import wraps

def deco(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        return fn(*a, **k)
    return wrapper

def f(x):
    return x

stacked = deco(deco(f))
print(stacked.__name__, inspect.signature(stacked))
n = 0
cur = stacked
while hasattr(cur, '__wrapped__'):
    n += 1
    cur = cur.__wrapped__
print(n, cur is f)
print(inspect.unwrap(stacked) is f)
print(callable(stacked), type(stacked).__name__)
```

<OutputBox title='原理验证' output='f (x)\n2 True\nTrue\nTrue function' />


## 类装饰器、__call__ 与状态保存

类也可以作装饰器：@Cls 等价于 `f = Cls`(f)，要求返回的是可调用对象，因此类实例要实现 `__call__(self, *a, **k)`；

类同样可以装饰另一个类，此时 `__call__` 接收类、返回类。用类保存状态比闭包清晰：计数器、命中率、配置都是实例属性，天然可读可测；

配合 `functools.update_wrapper(self, fn)` 把 `__name__`、`__doc__`、`__wrapped__` 等搬到实例上（update_wrapper 对任何带 `__dict__` 的对象都可用）。

带参类装饰器可以让 `__init__` 收配置、`__call__` 收函数并返回 self，或直接在 `__init__` 里存下函数。

要留意描述符交互：函数对象本身是非数据描述符（实现了 `__get__`），而普通类实例没有 `__get__`，所以把类装饰器实例放进类属性当方法用时不会自动绑定 self，这是第 040 讲描述符协议要处理的点。

对外发布的装饰器应提供参数化开关与 bypass 路径（`enabled=False` 直接返回原函数），方便测试与灰度绕开；类型注解侧可用 ParamSpec / TypeVar（第 036 讲）表达保持被装饰函数签名，避免静态类型退化成 Any。

```python
from functools import update_wrapper

class Count:
    def __init__(self, fn):
        self.fn = fn
        self.calls = 0
        update_wrapper(self, fn)
    def __call__(self, *a, **k):
        self.calls += 1
        return self.fn(*a, **k)

@Count
def add(a, b):
    return a + b

print(add(1, 2), add(3, 4), add.calls, add.__name__)

def maybe(enabled):
    def deco(fn):
        return fn if not enabled else Count(fn)
    return deco

@maybe(False)
def raw(x):
    return x
print(type(raw).__name__, raw(9), hasattr(raw, '__wrapped__'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='3 7 2 add\nfunction 9 False' guess="true" />

<Predict no='033-P' q='@tag(&#39;A&#39;) 与 @tag(&#39;B&#39;) 叠加，每个 wrapper 进入时打印标签，调用 f() 的输出顺序是？' :options='["enter A\nenter B", "enter B\nenter A", "只有 enter A"]' answer='0' output='enter A\nenter B' explain='包装自下而上（B 先包、A 后包成为最外层），调用从最外层进入，因此 A 的进入标记先打印，再打印 B 的。' />

**类装饰器与内置装饰器叠加规则**

| 对象 | 要求 | 注意 |
| --- | --- | --- |
| 类作装饰器 @Cls | 实例实现 __call__(self, *a, **k) | 用 update_wrapper(self, fn) 搬元数据 |
| 类装饰类 | __call__ 接收类并返回类 | 返回新类会替换原名字绑定 |
| staticmethod | 放在最外层 | 否则被其它 wrapper 包住后绑定失效 |
| classmethod | 通常紧邻 def、在自定义装饰器内侧 | 与 property 叠加时顺序敏感 |
| ParamSpec / TypeVar | 第 036 讲类型注解 | 让装饰后签名在静态检查里不退化成 Any |


## 底层：三层闭包与描述符如何共同生效

@ 展开后是模块字节码里连续的 CALL：先算出装饰器表达式的值（带参时先 CALL `repeat(n)` 得到 deco），再把函数对象作为参数 CALL 一次，把返回值 STORE 回名字。多层装饰时这些 CALL 从内向外依次发生，因此离 def 最近的先包装、最远的最后包装并成为最外层对象。

每个 wrapper 通过 `__wrapped__` 串成一条链：`inspect.signature` 与 `inspect.unwrap` 沿链向内走，最外层决定调用入口、最内层才是原逻辑；

调用时外层 wrapper 先执行前置逻辑再调 fn（也就是下一层 wrapper），返回时各层 finally 逆序退出。类装饰器走同一条路径，只是返回的是实现了 `__call__` 的实例。

函数对象本身是非数据描述符（有 `__get__`），而普通类实例没有 `__get__`，所以把类装饰器实例放进类属性时不会自动绑定 self，这正是描述符协议（第 040 讲）要处理的问题。

<SequenceDiagram title='第 033 讲 · 调用时序' caption='从触发到收尾，标出最可能失败的两个位置' :actors='["调用方", "核心逻辑", "外部依赖"]' :steps='[{"from": "调用方", "to": "核心逻辑", "label": "发起调用", "note": "三层函数结构与少一层的报错", "kind": "call"}, {"from": "核心逻辑", "to": "核心逻辑", "label": "检查前置", "note": "叠加顺序：包装自下而上、执行", "kind": "self"}, {"from": "核心逻辑", "to": "外部依赖", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "外部依赖", "to": "核心逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "核心逻辑", "to": "调用方", "label": "返回或降级", "note": "清理资源", "kind": "return"}]' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：带参装饰器少写一层 return，报 Typ", "body": "外层没返回 deco 或中层没返回 wrapper，得到 None 却被当函数调用", "tip": "牢记三层：外层 return deco、中层 return wrapper、内层 return fn(*a, **k)；逐层打印返回值定位断点"}, {"title": "第 2 步：@cache 写在 @auth 外面，未授权", "body": "最外层 cache 命中后直接返回，根本不会调用内层 auth", "tip": "把鉴权、限流这类早失败的装饰器放外层，缓存放内侧；用进入 / 退出打印验证顺序"}, {"title": "第 3 步：类装饰器实例放进类里当方法用，self 没自", "body": "普通实例没有 __get__，不是描述符，不会做方法绑定", "tip": "给类实现 __get__ 返回绑定方法，或改用闭包函数装饰器；理解函数描述符后再设计"}]' />

<Term word='三层函数结构' text='带参装饰器其实是装饰器工厂：def repeat(n): def deco(fn): def wrapper(*a, **k): ...; return wrapper; return deco。@repeat(3) 先调用 repeat(3) 得到 deco，再把 deco 应用到函数。三层职责分明：外层接收配置参数' />

<Term word='叠加顺序由近及远' text='@d1 / @d2 / def f 等价于 f = d1(d2(f))：定义时离 def 最近的 d2 先包装，d1 后包装并成为最外层对象。调用时从最外层进入，顺序是 d1.wrapper → d2.wrapper → f，也就是从上往下执行；返回时各层的 finally 清理再逆序退出。顺序错会出真实事故：@cac' />

<CodeTabs :tabs='[{"label": "主示例", "code": "from functools import wraps\n\ndef tag(label):\n    def deco(fn):\n        @wraps(fn)\n        def wrapper(*a, **k):\n            print(&#39;enter&#39;, label)\n            r = fn(*a, **k)\n            print(&#39;exit&#39;, label)\n            return r\n        return wrapper\n    return deco\n\n@tag(&#39;outer&#39;)\n@tag(&#39;inner&#39;)\ndef work(x):\n    print(&#39;run&#39;, x)\n    return x + 1\n\nprint(work(1))\nprint(work.__name__)", "note": "三层函数结构与少一层的报错"}, {"label": "对照 / 进阶", "code": "from functools import update_wrapper\n\nclass Count:\n    def __init__(self, fn):\n        self.fn = fn\n        self.calls = 0\n        update_wrapper(self, fn)\n    def __call__(self, *a, **k):\n        self.calls += 1\n        return self.fn(*a, **k)\n\n@Count\ndef add(a, b):\n    return a + b\n\nprint(add(1, 2), add(3, 4), add.calls, add.__name__)\n\ndef maybe(enabled):\n    def deco(fn):\n        return fn if not enabled else Count(fn)\n    return deco\n\n@maybe(False)\ndef raw(x):\n    return x\nprint(type(raw).__name__, raw(9), hasattr(raw, &#39;__wrapped__&#39;))", "note": "叠加顺序：包装自下而上、执行自上而下"}]' title='两种写法切换看' />


## 鉴权与缓存的组合：用顺序杜绝越权结果被缓存

报表接口要先鉴权、再查缓存。若把 @cache 写在 @auth 上面，最外层缓存一旦命中就跳过鉴权，guest 拿到的 denied 也会被缓存，甚至可能把 admin 的结果反向暴露。正确顺序是 @auth 在外、@cache 在内：每次请求先经过鉴权，未授权直接返回 denied，根本不会触及缓存。

下面实现两个带参装饰器：auth 用 wraps 保留元数据，cache 用一个字典按 (位置参数, 排序后的关键字参数) 构造可哈希键，并演示 admin、guest、admin 三次调用的结果，以及关闭开关时绕过包装。真实项目还要给缓存加 TTL、上限和线程锁，那是第 037 讲的内容。

```python
from functools import wraps

def auth(ok=True):
    def deco(fn):
        @wraps(fn)
        def wrapper(user, *a, **k):
            if not ok or user != 'admin':
                return 'denied'
            return fn(user, *a, **k)
        return wrapper
    return deco

def cache(enabled=True):
    def deco(fn):
        store = {}
        @wraps(fn)
        def wrapper(*a, **k):
            if not enabled:
                return fn(*a, **k)
            key = (a, tuple(sorted(k.items())))
            if key not in store:
                store[key] = fn(*a, **k)
            return store[key]
        return wrapper
    return deco

@auth()
@cache()
def report(user):
    return 'secret-data'

print(report('admin'))
print(report('guest'))
print(report('admin'))
print(report.__name__)
```

<Callout type="idea" title='落地提示' text='对外发布的装饰器要提供参数化开关与 bypass 路径，方便在测试与灰度环境里绕开' />

<CheckList id='P033b' title='上线前自检' :items='["能复现并解释「带参装饰器少写一层 return，报 TypeError: 」", "能复现并解释「@cache 写在 @auth 外面，未授权结果被缓存」", "能复现并解释「类装饰器实例放进类里当方法用，self 没自动传入」", "能用一条命令验证 三层函数结构", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from functools import lru_cache; f=lru_cache(64)(lambda x:x*x); print(f(4))"
```

把输入换成你自己的数据，观察结果是否仍符合 **三层函数结构** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 少一层 return、顺序颠倒与 self 丢失

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 带参装饰器少写一层 return，报 TypeError: 'NoneType' object is not callable | 外层没返回 deco 或中层没返回 wrapper，得到 None 却被当函数调用 | 牢记三层：外层 return deco、中层 return wrapper、内层 return fn(*a, **k)；逐层打印返回值定位断点 |
| @cache 写在 @auth 外面，未授权结果被缓存 | 最外层 cache 命中后直接返回，根本不会调用内层 auth | 把鉴权、限流这类早失败的装饰器放外层，缓存放内侧；用进入 / 退出打印验证顺序 |
| 类装饰器实例放进类里当方法用，self 没自动传入 | 普通实例没有 __get__，不是描述符，不会做方法绑定 | 给类实现 __get__ 返回绑定方法，或改用闭包函数装饰器；理解函数描述符后再设计 |

<Callout type="warn" title='本讲最容易踩的坑' text='带参装饰器少写一层 return，报 TypeError: &#39;NoneType&#39; object is not callable：外层没返回 deco 或中层没返回 wrapper，得到 None 却被当函数调用' />

<CheckList id='P033a' title='学完你应当能' :items='["能讲清 三层函数结构与少一层的报错", "能讲清 叠加顺序：包装自下而上、执行自上而下", "能讲清 类装饰器、__call__ 与状态保存", "能在工程里处理 装饰器与类型注解"]' />


## 组合顺序的练习与自测

<Exercise title='基础：实现一个三层带参装饰器' task='实现 repeat(n)，让被装饰函数连续执行 n 次并把结果收集成列表返回，用 wraps 保留名字，打印 greet(&#39;a&#39;) 与 __name__。' solution='from functools import wraps\n\ndef repeat(n):\n    def deco(fn):\n        @wraps(fn)\n        def wrapper(*a, **k):\n            return [fn(*a, **k) for _ in range(n)]\n        return wrapper\n    return deco\n\n@repeat(3)\ndef greet(x):\n    return &#39;hi &#39; + x\nprint(greet(&#39;a&#39;))\nprint(greet.__name__)' explain='三层分别是 repeat(n) 收配置、deco(fn) 收函数、wrapper(*a, **k) 收实参；少任何一层 return 都会得到 NoneType not callable。' />

<Exercise title='进阶：打印标记验证叠加顺序' task='用带参装饰器 mark(tag) 在每个 wrapper 进入时打印 tag，叠加 @mark(&#39;A&#39;) 与 @mark(&#39;B&#39;) 后调用一次，解释为什么 A 先打印。' solution='from functools import wraps\n\ndef mark(tag):\n    def deco(fn):\n        @wraps(fn)\n        def wrapper(*a, **k):\n            print(&#39;in&#39;, tag)\n            return fn(*a, **k)\n        return wrapper\n    return deco\n\n@mark(&#39;A&#39;)\n@mark(&#39;B&#39;)\ndef f():\n    return 0\nprint(f())' explain='展开为 f = mark(&#39;A&#39;)(mark(&#39;B&#39;)(f))：B 先包装、A 后包装成为最外层，调用从最外层进入，所以先打印 in A 再 in B。' />

<Quiz no='033-1' q='@d1 在 @d2 之上、下面是 def f，等价展开是？' :options='["f = d1(d2(f))", "f = d2(d1(f))", "d1(d2)(f)", "d2(f) 与 d1(f) 各调用一次"]' answer="0" explain='定义时离 def 最近的 d2 先包装，d1 最后包装并成为最外层，故展开为 f = d1(d2(f))。' />

<Quiz no='033-2' q='@cache 在外、@auth 在内的真实风险是？' :options='["缓存命中会跳过鉴权，未授权结果被缓存", "鉴权变慢", "cache 装饰器完全不生效", "抛 TypeError"]' answer="0" explain='最外层 cache 命中即返回，不会调用内层 auth；于是 denied 或越权响应被写进缓存并在有效期内反复返回。' />

<Quiz no='033-3' q='带参装饰器 @repeat(3) 需要几层函数？' :options='["三层：工厂、装饰器、wrapper", "两层", "一层", "四层"]' answer="0" explain='外层 repeat(n) 收配置返回 deco，中层 deco(fn) 收函数返回 wrapper，内层 wrapper(*a, **k) 收实参；不带参装饰器才是两层。' />

<FillBlank no='033-F' tpl='from functools  ___ wraps' :answers='["import"]' hint='回想本讲关于 三层函数结构 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 三层函数结构与少一层的报错 的落点。' />

<KnowledgeCard :points='["带参装饰器是三层：外层收配置返回 deco、中层收函数返回 wrapper、内层收调用实参", "少一层 return 会得到 NoneType not callable；@repeat 漏括号会把函数对象当成配置", "@d1 / @d2 / def f 等价 f = d1(d2(f))：包装自下而上、调用进入自上而下、finally 逆序退出", "鉴权 / 限流放外层、缓存 / 重试放内侧；顺序错会把未授权结果缓存", "类装饰器要求实例实现 __call__，用 functools.update_wrapper(self, fn) 搬元数据；实例不是描述符不会自动绑定 self", "staticmethod 置最外层；对外装饰器要提供 enabled=False 的 bypass 与可单测路径"]' :pitfalls='["带参装饰器少写一层 return，报 TypeError: &#39;NoneType&#39; object is not callable", "@cache 写在 @auth 外面，未授权结果被缓存", "类装饰器实例放进类里当方法用，self 没自动传入", "带参装饰器少写一层返回值，会得到「缺少参数」这类看似无关的报错"]' summary='多个装饰器从下往上包装、从上往下执行，顺序错了会让缓存包住鉴权，把未授权结果也缓存下来' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 带参装饰器是三层：外层收配置返回 deco、中层收函数返回 wrapper、内层收调用实参 | 建立直觉 |
| 少一层 return 会得到 NoneType not callable；@repeat 漏括号会把函数对象当成配置 | 跑通示例 |
| @d1 / @d2 / def f 等价 f = d1(d2(f))：包装自下而上、调用进入自上而下、finally 逆序退出 | 深入边界 |
| 鉴权 / 限流放外层、缓存 / 重试放内侧；顺序错会把未授权结果缓存 | 工程落地 |
| 类装饰器要求实例实现 __call__，用 functools.update_wrapper(self, fn) 搬元数据；实例不是描述符不会自动绑定 self | 随堂检测 |
| staticmethod 置最外层；对外装饰器要提供 enabled=False 的 bypass 与可单测路径 | 复盘 |

1. 带参装饰器是三层：外层收配置返回 deco、中层收函数返回 wrapper、内层收调用实参

2. 少一层 return 会得到 NoneType not callable；@repeat 漏括号会把函数对象当成配置

3. @d1 / @d2 / def f 等价 f = d1(d2(f))：包装自下而上、调用进入自上而下、finally 逆序退出

[下一讲：偏函数、可调用对象与函数式工具](/functions/partial)
