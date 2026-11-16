---
title: 第 034 讲 · 偏函数、可调用对象与函数式工具
description: 用标准库工具削减重复参数
---

<StageHeader stage='L3 · 函数与抽象' level='★★☆☆☆' time='25 分钟' goal='用标准库工具削减重复参数' prereq='第 033 讲 · 带参装饰器、叠加顺序与类装饰器' />

# 第 034 讲 · 偏函数、可调用对象与函数式工具

装饰器把「包一层」玩熟之后，会碰到另一类重复：好几个调用总是带着同一串固定参数。这一讲收拢标准库里帮我们省事的函数式工具，把「先固定一部分参数」做成可以四处传递的数据。回调接口往往只收一个可调用对象，手头的函数却有好几个入参，每次临时写一个 `lambda` 去凑签名，既不好读也难复用。

先看 `functools.partial` 怎样冻结参数；再看 `lru_cache` 的键怎么构造、容量与命中统计怎么看，以及它为什么只适合纯函数；最后捎带 `singledispatch` 与可调用协议，让工具函数能按类型分派。这一讲要用到参数、闭包和装饰器的经验；学完你能少写不少样板参数，也清楚缓存该在什么时候清掉。


## 回调接口只收一个可调用对象，参数却对不上

一个回调接口只接收单参数函数，手头却是 `power(base, exp)`，需要固定 `exp=2`；最省事的写法是堆一堆 `lambda` 或再包一层 `def`，可参数一改就要动好几处，这些匿名函数既没法 `pickle`，日志里又全叫 `<lambda>`。

另一类坑更隐蔽：给查询函数套上 `@lru_cache` 想提速，传入 `list` 参数时直接抛 `TypeError: unhas…`；给一个会写日志、读当前时间的函数加缓存，后续调用全拿到第一次的旧值；把可变返回值交给调用方原地修改，还会污染缓存里那同一份引用。

```text
TypeError: unhashable type: 'list'
```

本讲把 `functools` 里几件工具讲透：`partial` 如何冻结参数、`lru_cache` 的键与边界、`singledispatch` 按类型分派、`cached_property` 与 `__dict__` 的关系，以及可调用协议，把函数式工具从会用变成用对。

<Callout type="warn" title='先看一个真实会出错的写法' text='给含可变参数的函数加 lru_cache 报 TypeError: unhashable type: &#39;list&#39;：缓存键由 args + kwargs 组成，要求每个元素可哈希，list / dict / set 都不行' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段三 · 函数与抽象 |
| 前置 | 第 033 讲 · 带参装饰器、叠加顺序与类装饰器 |
| 难度 / 建议时长 | ★★☆☆☆ · 25 分钟 |
| 本讲新增 | functools.partial、lru_cache 与缓存策略、singledispatch 分派 |
| 一句话目标 | 用标准库工具削减重复参数 |
| 为下一讲铺垫 | 模块与包：import 机制与循环导入 |


## functools 常用工具与关键参数

**functools 常用工具与关键参数**

| 工具 | 关键参数 / 默认值 | 返回 / 行为 | 注意 |
| --- | --- | --- | --- |
| functools.partial | partial(func, /, *args, **keywords) | partial 对象，冻结参数 | 关键字可被再次调用覆盖；默认无 __name__ |
| lru_cache | maxsize=128, typed=False | 包装函数，带 cache_info | 键须可哈希；typed=True 区分 1 与 1.0 |
| singledispatch | 按第一个参数类型分派 | 泛型函数，register 注册 | 基于 MRO 找最具体类型；3.7+ 支持注解注册 |
| cached_property | 3.8+ | 首次计算写入实例 __dict__ | 非数据描述符，实例需有 __dict__ |
| singledispatchmethod | 3.8+ | 方法版分派 | 按非 self 的第一个参数类型分派 |

<CheckList id='P034a' title='学完你应当能' :items='["能讲清 functools.partial：把固定参数变成数据", "能讲清 lru_cache：键、边界与统计", "能讲清 singledispatch、cached_property 与可调用协议", "能在工程里处理 工具函数组合"]' />


## functools.partial：把固定参数变成数据

`functools.partial` 返回一个 partial 对象，把一部分位置参数与关键字参数冻结下来；再次调用时，新传入的实参追加在已冻结的位置参数之后，关键字参数则允许被同名新值覆盖，例如 `p = partial(f, a=1)` 后再 `p(a=2)`，真正用的是 2。

```python
functools.partial(func, /, *args, **keywords)
```

partial 对象把冻结内容摊在 `.func`、`.args`、`.keywords` 三个属性上，可以直接核对；它默认没有 `__name__`，需要时用 `functools.update_wrapper` 补齐即可。

与 `lambda` 相比，partial 保存的是原函数引用，只要 `func` 与 `args` 可 pickle 它就能 pickle，读起来清楚、也能被内省；而 `lambda` 每次新建，`__name__` 恒为 `<lambda>`。

它最典型的用途是适配签名：回调接口、`sorted` / `max` 的 `key`、线程池 `submit` 里带固定配置的函数，都只收一个可调用对象却和参数个数对不上，这时 partial 一行就能补齐。

类里要冻结方法参数，改用 `functools.partialmethod`，它是描述符版本，能正确处理 `self` 绑定。

```python
from functools import partial, lru_cache

def power(base, exp):
    return base ** exp

square = partial(power, exp=2)
print(square(5), square.func.__name__, square.args, square.keywords)
print(square(3, exp=3))

@lru_cache(maxsize=32)
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)

print(fib(10))
print(fib.cache_info())
fib.cache_clear()
print(fib.cache_info().currsize)
try:
    fib([1])
except TypeError as e:
    print(type(e).__name__, str(e))
```

<OutputBox title='主示例运行结果' output='25 power () {&#39;exp&#39;: 2}\n27\n55\nCacheInfo(hits=8, misses=11, maxsize=32, currsize=11)\n0\nTypeError unhashable type: &#39;list&#39;' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from functools import partial, lru_cache\n\ndef power(base, exp):\n    return base ** exp\n\nsquare = partial(power, exp=2)\nprint(square(5), square.func.__name__, square.args, square.keywords)\nprint(square(3, exp=3))\n\n@lru_cache(maxsize=32)\ndef fib(n):\n    return n if n &lt; 2 else fib(n - 1) + fib(n - 2)\n\nprint(fib(10))\nprint(fib.cache_info())\nfib.cache_clear()\nprint(fib.cache_info().currsize)\ntry:\n    fib([1])\nexcept TypeError as e:\n    print(type(e).__name__, str(e))' :notes='["从 functools 导入 partial 与 lru_cache", "空行，只用于分隔逻辑块，不影响执行结果。", "定义一个需要两个参数的普通函数", "返回幂运算结果", "空行，只用于分隔逻辑块，不影响执行结果。", "用 partial 冻结 exp=2，得到单参数可调用对象", "读出 .func / .args / .keywords，确认冻结内容", "再次调用时 exp=3 覆盖冻结值，得到 27", "空行，只用于分隔逻辑块，不影响执行结果。", "用 maxsize=32 装饰斐波那契，限制缓存容量", "定义递归函数，重复子问题会命中缓存", "基线情形直接返回，否则递归求和", "空行，只用于分隔逻辑块，不影响执行结果。", "fib(10) 得 55，同时填充缓存", "cache_info 给出命中、未命中、容量与当前条目数", "cache_clear 清空缓存，便于测试与热更新", "清空后 currsize 为 0", "准备捕获不可哈希参数", "list 不能作缓存键", "捕获预期的 TypeError", "打印异常类型与消息"]' title='第 034 讲 · 偏函数、可调用对象与函数式工具' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Compare :panels='[{"label": "主示例", "code": "from functools import partial, lru_cache\n\ndef power(base, exp):\n    return base ** exp\n\nsquare = partial(power, exp=2)\nprint(square(5), square.func.__name__, square.args, square.keywords)\nprint(square(3, exp=3))\n\n@lru_cache(maxsize=32)\ndef fib(n):\n    return n if n &lt; 2 else fib(n - 1) + fib(n - 2)\n\nprint(fib(10))\nprint(fib.cache_info())\nfib.cache_clear()\nprint(fib.cache_info().currsize)\ntry:\n    fib([1])\nexcept TypeError as e:\n    print(type(e).__name__, str(e))", "note": "functools.partial：把固定参数变成数据"}, {"label": "对照 / 进阶", "code": "from functools import singledispatch, cached_property\n\n@singledispatch\ndef describe(x):\n    return &#39;other: &#39; + type(x).__name__\n\n@describe.register\ndef _(x: int):\n    return &#39;int: &#39; + str(x)\n\n@describe.register\ndef _(x: list):\n    return &#39;list of &#39; + str(len(x))\n\nprint(describe(3), describe([1, 2]), describe(&#39;s&#39;))\nprint(describe.dispatch(float) is describe.dispatch(object))\nprint(sorted(t.__name__ for t in describe.registry))\n\nclass Config:\n    def __init__(self, raw):\n        self.raw = raw\n    @cached_property\n    def parsed(self):\n        self.builds = getattr(self, &#39;builds&#39;, 0) + 1\n        return tuple(self.raw)\n\nc = Config([1, 2, 3])\nprint(c.parsed, c.parsed, c.builds)\nprint(&#39;parsed&#39; in c.__dict__, callable(describe))", "note": "lru_cache：键、边界与统计"}]' title='两种写法对照' note='差异集中在 functools.partial；先看输出，再找背后的规则。' />

<ConceptDiagram type='compare2' title='第 034 讲 · functools.partial：把固定参数变成数据' labels='functools.partial：把固定参…|lru_cache：键、边界与统计|singledispatch、cached_…|工具函数组合' caption='用标准库工具削减重复参数' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## lru_cache 参数与 CacheInfo

**lru_cache 参数与 CacheInfo**

| 项 | 值 / 默认 | 说明 |
| --- | --- | --- |
| maxsize | 128 / None / 2 的幂 | None 表示无界不淘汰；2 的幂时淘汰最高效 |
| typed | False | True 时 1 与 1.0 视为不同键 |
| 键构造 | args + kwargs | 全部元素须可哈希；kwargs 书写顺序影响键 |
| cache_info() | CacheInfo(hits, misses, maxsize, currsize) | 具名元组，用于观测命中率 |
| cache_clear / __wrapped__ / cache_parameters | 3.9+ 提供参数字典 | 清空缓存 / 取原函数 / 读 maxsize 与 typed |

<Callout type="tip" title='核心心智模型' text='`functools.partial(func, /, *args, **keywords)` 返回一个 partial 对象，把一部分位置参数与关键字参数冻结下来；再次调用时，新传入的实参追加在已冻结的位置参数之后，关键字参数则允许被同名新值覆盖，例如 `p = partial(f, a=1)`…' />


## lru_cache：键、边界与统计

`functools.lru_cache` 的默认配置是 `maxsize=128`、`typed=False`，既可以写成带参数的 `@lru_cache(maxsize=128)`，也可以先 `@lru_cache(maxsize)` 再作用于 `fn`（即 `lru_cache(maxsize)(fn)` 两步走）。

`maxsize` 默认 128，设为 `None` 表示无界、不做淘汰，取 2 的幂时淘汰效率最好；`typed` 默认 `False`，置 `True` 会把 `1` 与 `1.0` 当成不同的键。

缓存键由位置参数与关键字参数共同构造，要求每个元素可哈希，传入 `list`、`dict`、`set` 会抛 `TypeError: unhas…`；关键字参数的书写顺序也会影响键，同一组键值用不同顺序传入可能被当成两个键。

```text
TypeError: unhashable type: 'list'
```

`cache_info()` 返回具名元组 `CacheInfo`，`cache_clear()` 清空缓存，`__wrapped__` 能取到未缓存的原函数，`cache_parameters()`（3.9+）返回 `{'maxsize': ...…`。

```python
CacheInfo(hits, misses, maxsize, currsize)
{'maxsize': ..., 'typed': ...}
```

内部用哈希表加双向链表实现 LRU，命中 `O(1)`，并用一把锁保证结构一致，但同一键并发未命中时函数仍可能被重复计算。最要紧的一条边界是只对纯函数使用：依赖时间、随机、外部状态或带副作用的函数被缓存后会串数据甚至带来安全问题；返回值若是可变对象，调用方原地修改会污染缓存里的同一份引用。

```python
from functools import singledispatch, cached_property

@singledispatch
def describe(x):
    return 'other: ' + type(x).__name__

@describe.register
def _(x: int):
    return 'int: ' + str(x)

@describe.register
def _(x: list):
    return 'list of ' + str(len(x))

print(describe(3), describe([1, 2]), describe('s'))
print(describe.dispatch(float) is describe.dispatch(object))
print(sorted(t.__name__ for t in describe.registry))

class Config:
    def __init__(self, raw):
        self.raw = raw
    @cached_property
    def parsed(self):
        self.builds = getattr(self, 'builds', 0) + 1
        return tuple(self.raw)

c = Config([1, 2, 3])
print(c.parsed, c.parsed, c.builds)
print('parsed' in c.__dict__, callable(describe))
```

<OutputBox title='对照写法：先自己猜，再点开' output='int: 3 list of 2 other: str\nTrue\n[&#39;int&#39;, &#39;list&#39;, &#39;object&#39;]\n(1, 2, 3) (1, 2, 3) 1\nTrue True' guess="true" />

```python
import functools, inspect

@functools.lru_cache(maxsize=8, typed=True)
def f(x):
    return x

print(f(3), f(3.0))
print(f.cache_info().hits, f.cache_info().misses, f.cache_parameters())
print(inspect.isfunction(f.__wrapped__), f.__wrapped__(9))
print(functools.partial(int, base=2).keywords)
print(callable(f), callable(functools.partial(int, base=2)))
```

<OutputBox title='原理验证' output='3 3.0\n0 2 {&#39;maxsize&#39;: 8, &#39;typed&#39;: True}\nTrue 9\n{&#39;base&#39;: 2}\nTrue True' />

<Predict no='034-1' q='@lru_cache(maxsize=8, typed=True) 装饰 def f(x): return x 后，print(f(1), f(1.0), f.cache_info().misses) 输出什么？' :options='["1 1.0 2", "1 1.0 1", "1 1 2"]' answer='0' output='1 1.0 2' explain='typed=True 把 1（int）与 1.0（float）当成两个不同的键，两次调用都是未命中，因此 misses 为 2，返回值分别是 1 与 1.0。' />


## singledispatch、cached_property 与可调用协议

`functools.singledispatch` 按第一个参数的类型分派：用 `@singledispatch` 定义默认实现，再用 `@fun.register(int)` 或带类型注解的 `@fun.register`（3.7+ 支持从注解推断）注册各类型实现，`dispatch(type)` 能查到具体会走哪个函数，`registry` 就是类型到实现的映射；查找沿类型的 `__mro__` 进行，子类会回退到最近的已注册父类，注册到 `ABC` 同样生效，3.8+ 还提供方法版 `singledispatchmethod`。

`cached_property`（3.8+）把首次计算的结果以同名键写进实例 `__dict__`，之后实例属性查找直接命中、不再调用计算函数；它是只实现 `__get__` 的非数据描述符，正因没有 `__set__` 才会被实例字典覆盖，也因此要求实例有 `__dict__`，与去掉字典的 `__slots__` 冲突。

和 `property` 相比，`property` 每次访问都重新计算，`cached_property` 只算一次。

可调用协议更通用：任何实现 `__call__` 的对象都满足 `callable(obj)`，函数、类、`partial`、`lru_cache` 包装后的对象、带 `__call__` 的实例都在此列，函数组合正是据此把多个工具函数拼成一条流水线。

从实现层看，`lru_cache` 在 C 层用一张哈希表加一条双向循环链表维护 LRU：命中时把节点移到链表头并直接返回结果，未命中时调用 `__wrapped__` 计算、用 `args` 与 `kwargs` 生成键（每个元素必须可哈希）后插入；超过 `maxsize` 就从链表尾淘汰最久未用的条目。

整段操作由一把锁保护缓存结构，所以并发下结构一致，但同一键并发未命中时函数仍可能被重复计算；`typed=True` 会把键元素的类型也纳入键，于是 `1` 与 `1.0` 分开存放。

`partial` 是纯 Python 的可调用对象，内部只存 `func`、`args`、`keywords`，`__call__` 时把它们与本次实参合并再调用 `func`，因此没有额外的闭包作用域，也就能 pickle。

`cached_property` 是只实现 `__get__` 的非数据描述符：首次访问时计算并把结果以同名键写进实例 `__dict__`，之后实例字典优先于它，计算便只发生一次；没有 `__set__` 既是它能被实例字典覆盖的原因，也决定了 `__slots__` 去掉 `__dict__` 后无法使用。

`singledispatch` 则用 `registry` 字典把类型映射到实现，`dispatch` 沿类型的 `__mro__` 找到第一个注册命中的类。

<Term word='functools.partial' text='`functools.partial(func, /, *args, **keywords)` 返回一个 partial 对象，把一部分位置参数与关键字参数冻结下来；再次调用时，新传入的实参追加在已冻结的位置参数之后，关键字参数则允许被同名新值覆盖，例如 `p = partial(f, a=1)` 后再…' />

<Term word='lru_cache 与缓存策略' text='`functools.lru_cache` 的默认配置是 `maxsize=128`、`typed=False`，既可以写成带参数的 `@lru_cache(maxsize=128)`，也可以先 `@lru_cache(maxsize)` 再作用于 `fn`（即 `lru_cache(maxsize)(fn)` 两步走…' />


## 用 partial 适配回调，并给纯解析函数加可清理的缓存

一个任务队列的回调只接受单参数函数，底层 `fetch` 却有三个参数；用 `partial` 冻结 `timeout` 与 `retries`，就得到一个符合接口的可调用对象，调用时还能按名覆盖个别配置。

```python
fetch(url, timeout, retries)
```

另一处是版本号字符串解析：它是纯函数、输入量有限、又会被反复调用，适合加 `lru_cache`，但必须留出 `cache_clear`，方便配置热更新与单元测试之间做隔离。

下面把这两件事写成一个可直接运行的片段：打印 `partial` 适配后的调用、关键字覆盖的效果、解析结果的重复命中，以及清空缓存后 `currsize` 归零。真实项目还应把 `cache_info` 的命中率上报，命中率偏低时及时把缓存关掉。

```python
from functools import partial, lru_cache

def fetch(url, timeout, retries):
    return url + ' t=' + str(timeout) + ' r=' + str(retries)

fetch_short = partial(fetch, timeout=1, retries=2)
print(fetch_short('/a'))
print(fetch_short('/b', retries=5))

@lru_cache(maxsize=64)
def parse_key(key):
    return tuple(int(p) for p in key.split('.'))

print(parse_key('1.2.3'))
print(parse_key('1.2.3'))
print(parse_key.cache_info().hits)
parse_key.cache_clear()
print(parse_key.cache_info().currsize)
```

<Callout type="idea" title='落地提示' text='缓存务必设 maxsize、明确键的可哈希性，并提供 cache_clear 供测试与热更新' />

```bash
python -c "import inspect; print(inspect.signature(print))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 `functools.partial` 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

<CheckList id='P034b' title='上线前自检' :items='["能复现并解释「给含可变参数的函数加 lru_cache 报 TypeErr…」", "能复现并解释「给读当前时间或写日志的函数加 lru_cache，结果一直是…」", "能复现并解释「cached_property 在定义了 __slots__…」", "能用一条命令验证 functools.partial", "关键路径有自动化测试与失败分支"]' />


## 缓存与分派的错误对照

**缓存与分派的错误对照**

| 现象 / 消息 | 根因 | 正确写法 |
| --- | --- | --- |
| TypeError: unhashable type: 'list' | 传入 list / dict / set 作缓存键 | 改用可哈希的 tuple / frozenset，或不用缓存 |
| 加了 lru_cache 后结果一直是旧值 | 被缓存函数依赖时间 / 随机 / 外部状态或有副作用 | 只缓存纯函数；有副作用就去掉缓存或显式 cache_clear |
| 返回值是可变对象且被外部修改 | 缓存里存的是同一对象引用 | 返回不可变副本，或在文档里声明不得修改 |
| singledispatch 对子类走了默认分支 | 未注册该类型且 MRO 上无更具体实现 | register 具体类型，或注册其 ABC |

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 给含可变参数的函数加 lru_cache 报 TypeError: unhashable type: 'list' | 缓存键由 args + kwargs 组成，要求每个元素可哈希，list / dict / set 都不行 | 把参数规范成 tuple / frozenset 或可哈希标识，也可以放弃缓存 |
| 给读当前时间或写日志的函数加 lru_cache，结果一直是第一次的旧值 | 缓存按参数键返回首次结果，函数依赖外部状态或带副作用时后续调用被跳过 | 只对纯函数缓存；有副作用就去掉缓存、把状态显式放进参数，或提供 cache_clear 热更新 |
| cached_property 在定义了 __slots__ 的类上不可用 | cached_property 要把结果写入实例 __dict__，而 __slots__ 去掉了实例字典 | 在 __slots__ 里显式加 '__dict__'，或改用普通 property / 手动缓存 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：给含可变参数的函数加 lru_cache 报…", "body": "缓存键由 args + kwargs 组成，要求每个元素可哈希，list / dict / set 都不行", "tip": "把参数规范成 tuple / frozenset 或可哈希标识，也可以放弃缓存"}, {"title": "第 2 步：给读当前时间或写日志的函数加 lru_cac…", "body": "缓存按参数键返回首次结果，函数依赖外部状态或带副作用时后续调用被跳过", "tip": "只对纯函数缓存；有副作用就去掉缓存、把状态显式放进参数，或提供 cache_clear 热更新"}, {"title": "第 3 步：cached_property 在定义了 _…", "body": "cached_property 要把结果写入实例 __dict__，而 __slots__ 去掉了实例字典", "tip": "在 __slots__ 里显式加 &#39;__dict__&#39;，或改用普通 property / 手动缓存"}]' />

<Callout type="warn" title='本讲最容易踩的坑' text='给含可变参数的函数加 lru_cache 报 TypeError: unhashable type: &#39;list&#39;：缓存键由 args + kwargs 组成，要求每个元素可哈希，list / dict / set 都不行' />


## 工具上手练习与速记

<Exercise title='基础：partial 的冻结与关键字覆盖' task='用 partial 把 power(b, e) 的 e 冻结为 2，打印调用结果、再用 e=3 覆盖，并读出 .func / .args / .keywords 三个属性。' solution='from functools import partial\n\ndef power(b, e):\n    return b ** e\n\nsq = partial(power, e=2)\nprint(sq(4), sq(4, e=3))\nprint(sq.func.__name__, sq.args, sq.keywords)' explain='partial 冻结的是关键字 e=2；再次调用给出同名关键字会覆盖它；.func 指向原函数，.args 为空元组，.keywords 是冻结的关键字字典。' />

<Exercise title='进阶：typed 缓存与 cache_clear' task='给函数加 lru_cache(maxsize=16, typed=True)，分别传 1 与 1.0，打印 misses，再 cache_clear 后打印 currsize。' solution='from functools import lru_cache\n\n@lru_cache(maxsize=16, typed=True)\ndef f(x):\n    return x\n\nprint(f(1), f(1.0))\nprint(f.cache_info().misses)\nf.cache_clear()\nprint(f.cache_info().currsize)' explain='typed=True 把 int 与 float 视为不同键，1 与 1.0 各产生一次未命中，misses 为 2；cache_clear 后 currsize 归零。' />

<Quiz no='034-2' q='lru_cache 的 maxsize 与 typed 默认值分别是？' :options='["128 与 False", "None 与 True", "32 与 False", "256 与 True"]' answer="0" explain='签名是 lru_cache(maxsize=128, typed=False)；maxsize=None 表示无界，typed=True 才把 1 与 1.0 分开缓存。' />

<Quiz no='034-3' q='给 lru_cache 包装的函数传入 list 参数会怎样？' :options='["抛 TypeError: unhashable type: &#39;list&#39;", "正常缓存", "自动把 list 转成 tuple 再缓存", "静默地不缓存这次调用"]' answer="0" explain='缓存键由 args + kwargs 构成，要求每个元素可哈希；list / dict / set 不可哈希，构造键时即抛 TypeError。' />

<Quiz no='034-4' q='cached_property 与 property 最关键的区别是？' :options='["cached_property 首次计算后写入实例 __dict__，之后不再调用", "property 会自动缓存结果", "cached_property 每次访问都重新计算", "两者行为完全相同"]' answer="0" explain='cached_property 是非数据描述符，首次计算后把结果写进实例字典，后续由实例字典优先命中；property 每次都会调用 fget。' />

<FillBlank no='034-5' tpl='from functools  ___ partial, lru_cache' :answers='["import"]' hint='回想本讲关于 functools.partial 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 functools.partial：把固定参数变成数据 的落点。' />

<KnowledgeCard :points='["functools.partial(func, /, *args, **keywords) 冻结参数、返回可 pickle 的 partial 对象，.func/.args/.keywords 可读，关键字可被覆盖", "lru_cache 默认 maxsize=128、typed=False；键由 args + kwargs 组成且须全可哈希，否则 TypeError: unhashable type: &#39;list&#39;", "cache_info() 返回 CacheInfo(hits, misses, maxsize, currsize)；cache_clear() 清空；__wrapped__ 取原函数；cache_parameters()（3.9+）读配置", "typed=True 把 1 与 1.0 分开缓存；maxsize=None 无界不淘汰，取 2 的幂淘汰最高效", "singledispatch 按第一个参数沿 MRO 分派（3.7+ 支持注解注册，3.8+ 有 singledispatchmethod）；cached_property（3.8+）写入实例 __dict__ 且要求实例有字典", "callable(obj) 判断 __call__；只对纯函数缓存，返回可变对象要给副本，并提供 cache_clear 供测试与热更新"]' :pitfalls='["给含可变参数的函数加 lru_cache 报 TypeError: unhashable type: &#39;list&#39;", "给读当前时间或写日志的函数加 lru_cache，结果一直是第一次的旧值", "cached_property 在定义了 __slots__ 的类上不可用", "给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数据甚至安全问题"]' summary='偏函数把「固定一部分参数」变成数据，回调接口只要一个可调用对象时特别好用；lru_cache 则把纯函数变成带边界的记忆化' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| functools.partial(func, /, *args, **keywords) 冻结参数、返回可 pickle 的 partial 对象，.func/.args/.keywords 可读，关键字可被覆盖 | 建立直觉 |
| lru_cache 默认 maxsize=128、typed=False；键由 args + kwargs 组成且须全可哈希，否则 TypeError: unhashable type: 'list' | 跑通示例 |
| cache_info() 返回 CacheInfo(hits, misses, maxsize, currsize)；cache_clear() 清空；__wrapped__ 取原函数；cache_parameters()（3.9+）读配置 | 深入边界 |
| typed=True 把 1 与 1.0 分开缓存；maxsize=None 无界不淘汰，取 2 的幂淘汰最高效 | 工程落地 |
| singledispatch 按第一个参数沿 MRO 分派（3.7+ 支持注解注册，3.8+ 有 singledispatchmethod）；cached_property（3.8+）写入实例 __dict__ 且要求实例有字典 | 随堂检测 |
| callable(obj) 判断 __call__；只对纯函数缓存，返回可变对象要给副本，并提供 cache_clear 供测试与热更新 | 复盘 |

1. functools.partial(func, /, *args, **keywords) 冻结参数、返回可 pickle 的 partial 对象，.func/.args/.keywords 可读，关键字可被覆盖

2. lru_cache 默认 maxsize=128、typed=False；键由 args + kwargs 组成且须全可哈希，否则 TypeError: unhashable type: 'list'

3. cache_info() 返回 CacheInfo(hits, misses, maxsize, currsize)；cache_clear() 清空；__wrapped__ 取原函数；cache_parameters()（3.9+）读配置

[下一讲：模块与包：import 机制与循环导入](/functions/modules)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/034-partial.py`

```bash
python3 examples/lessons/034-partial.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/034-partial.py) · [全部示例代码索引](/examples/)
