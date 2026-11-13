---
title: 第 020 讲 · tuple 与具名元组：不可变性的价值
description: 知道什么时候该用不可变容器
---

<StageHeader stage='L2 · 容器与序列' level='★☆☆☆☆' time='25 分钟' goal='知道什么时候该用不可变容器' prereq='第 019 讲 · list 进阶：切片赋值、排序与常见陷阱' />

# 第 020 讲 · tuple 与具名元组：不可变性的价值

有些数据一旦写好就不该再动：一个坐标、一条记录、一组配置。上一讲把可变的列表翻了个遍，这一讲换个方向，看把容器定住能换来什么、这份“定住”又管到哪一层。

一个报表服务把查询条件拼成缓存键，读代码的人得数下标才分清哪位是维度；某次把一项传成列表，整层缓存悄悄失效；还有人少写一个逗号，以为得到单元素元组。我们先从逗号才是构造符说起，看清不可变只约束外层引用、里面装着列表时依旧会变；再用具名元组给字段安上名字；最后走到元组解包与它凭什么能当字典键。需要你熟悉列表、哈希与解包。学完你能判断一份数据该用列表还是 tuple，把复合键写清楚。


## 想写一个单元素元组：逗号才是构造符

一个报表服务把查询条件拼成缓存键，最初写成 key = (start, end, metrics)，读代码的人必须数下标才知道第三个是维度还是指标；某次有人把 metrics 传成 list，`hash(key)` 直接抛 TypeError: unhashable type: 'list'，整层缓存静默失效。

另一处更隐蔽：配置元组 cfg = (['a', 'b'], 3) 被当成'不可变所以线程安全'，结果 cfg[0].append('c') 照样改了内容，两个请求读到不同结果。还有人写 single = (8080) 以为得到单元素元组，实际是 int，传给需要元组的接口直接报参数类型错。

这些坑都指向同一件事：元组的不可变只约束它保存的引用数组。本讲把单元素写法、浅层不可变与可哈希条件、NamedTuple 与 frozen dataclass 的差别、解包与序列模式匹配逐条讲清。

元组由逗号创建，括号在多数场合只是分组：1, 2 与 (1, 2) 都是 tuple，`x = 1`, 得到单元素 tuple，空元组写 ()。因此单元素必须写 (1,)——`type((1)`) 是 int，`type((1,)`) 才是 tuple，这个逗号是初学者最高频的语法坑。

不可变指 PyTupleObject 里那串 PyObject* 指针不能增删改：没有 append、下标赋值 t[0] = x 抛 TypeError: 'tuple' object does not support item assignment，t += (x,) 也不是原地改，而是用 `__add__` 构造新 tuple 再把名字重新绑定过去。

但这层不可变是浅的：t[0] 若指向一个 list，改不了指针却能改那个 list 的内容，t[0].`append(x)` 合法且所有持有 t 的地方都能看到变化。

要真正只读，嵌套容器也得换成 tuple，或用 `dataclass(frozen=True)` 配合不可变字段。

`hash(tuple)` 逐元素取哈希再组合，只要有一个元素不可哈希（list / dict / set）就抛 TypeError，所以含 list 的元组既不能当 dict 键也不能进 set；这也是它适合做坐标、复合缓存键，却不适合塞可变载荷的原因。

```python
from collections import namedtuple

single = (1,)
not_tuple = (1)
print('single', type(single).__name__, 'no comma', type(not_tuple).__name__)

t = ([1, 2], 3)
t[0].append(9)
print('shallow immutable', t)
try:
    t[0] = [0]
except TypeError as e:
    print('assign error', type(e).__name__)

try:
    print(hash(([1, 2],)))
except TypeError as e:
    print('unhashable', type(e).__name__)

coord = (10, 20)
print('dict key', {(1, 2): 'a'}[(1, 2)])
a, b = coord
head, *tail = (1, 2, 3, 4)
print('unpack', a, b, 'star', head, tail)

def classify(point):
    match point:
        case (0, 0):
            return 'origin'
        case (x, 0):
            return 'x-axis'
        case (x, y):
            return 'quadrant'

print('match', classify((0, 0)), classify((5, 0)), classify((2, 3)))

Point = namedtuple('Point', 'x y')
p = Point(3, 4)
print('named', p.x, p.y, p._asdict(), p._replace(y=9))
print('is tuple', isinstance(p, tuple), p[0] + p[1])
```

<OutputBox title='主示例运行结果' output='single tuple no comma int\nshallow immutable ([1, 2, 9], 3)\nassign error TypeError\nunhashable TypeError\ndict key a\nunpack 10 20 star 1 [2, 3, 4]\nmatch origin x-axis quadrant\nnamed 3 4 {&#39;x&#39;: 3, &#39;y&#39;: 4} Point(x=3, y=9)\nis tuple True 7' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from collections import namedtuple\n\nsingle = (1,)\nnot_tuple = (1)\nprint(&#39;single&#39;, type(single).__name__, &#39;no comma&#39;, type(not_tuple).__name__)\n\nt = ([1, 2], 3)\nt[0].append(9)\nprint(&#39;shallow immutable&#39;, t)\ntry:\n    t[0] = [0]\nexcept TypeError as e:\n    print(&#39;assign error&#39;, type(e).__name__)\n\ntry:\n    print(hash(([1, 2],)))\nexcept TypeError as e:\n    print(&#39;unhashable&#39;, type(e).__name__)\n\ncoord = (10, 20)\nprint(&#39;dict key&#39;, {(1, 2): &#39;a&#39;}[(1, 2)])\na, b = coord\nhead, *tail = (1, 2, 3, 4)\nprint(&#39;unpack&#39;, a, b, &#39;star&#39;, head, tail)\n\ndef classify(point):\n    match point:\n        case (0, 0):\n            return &#39;origin&#39;\n        case (x, 0):\n            return &#39;x-axis&#39;\n        case (x, y):\n            return &#39;quadrant&#39;\n\nprint(&#39;match&#39;, classify((0, 0)), classify((5, 0)), classify((2, 3)))\n\nPoint = namedtuple(&#39;Point&#39;, &#39;x y&#39;)\np = Point(3, 4)\nprint(&#39;named&#39;, p.x, p.y, p._asdict(), p._replace(y=9))\nprint(&#39;is tuple&#39;, isinstance(p, tuple), p[0] + p[1])' :notes='["导入 namedtuple 工厂，用于给字段命名", "单元素元组必须写逗号，这是唯一的构造依据", "漏写逗号时括号只做分组，得到的是 int", "打印两个类型，对比 tuple 与 int", "构造一个含 list 的元组，演示浅层不可变", "改不了指针，却能改 t[0] 指向的 list 内容", "打印被原地修改后的元组内容", "尝试给元组下标赋值", "触发 TypeError，证明引用数组不可变", "捕获预期的 TypeError 并打印类型", "尝试对含 list 的元组取哈希", "list 不可哈希会让整个元组不可哈希", "捕获 TypeError，说明它不能作 dict 键", "构造纯不可变元组作为坐标", "用 tuple 作 dict 键并成功取回值", "基本解包把两个位置绑定到 a 与 b", "扩展解包，星号目标取剩余元素", "星号目标 tail 是 list 而不是 tuple", "定义函数演示 3.10+ 的序列模式匹配", "match 对 tuple 按位置匹配", "case (0, 0) 匹配原点，字面量按相等比较", "返回原点标记", "case (x, 0) 匹配第二个元素为 0 的点", "x 按位置捕获，未用到的名字不影响匹配", "case (x, y) 兜底绑定两个坐标", "返回象限标记", "对三种点分别匹配并打印结果", "用工厂函数生成带字段名 x、y 的 tuple 子类", "构造 Point 实例，仍按位置存值", "字段按名字读，_asdict 转 dict，_replace 生成新实例", "namedtuple 是 tuple 子类，索引与加法沿用 tuple 行为", "不可变是浅层的：不能改指针，但能改指针指向的 list；hash 要求所有元素可哈希", "tuple 无 allocated 过度分配，比同元素 list 省内存；只含常量时会被折叠进 co_consts"]' title='第 020 讲 · tuple 与具名元组：不可变性的价值' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='flow3' title='第 020 讲 · 语法与浅层不可变：逗号才是构造符' labels='语法与浅层不可变：逗号才是构造符|命名元组与 frozen dataclass|解包、序列模式匹配与作为字典键' caption='知道什么时候该用不可变容器' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## tuple 与 list 对照：什么时候该用不可变

**tuple 与 list 对照**

| 维度 | tuple | list |
| --- | --- | --- |
| 构造语法 | (1, 2) 或 1, 2；单元素必须 (1,) | [1, 2]；单元素 [1] 无需逗号 |
| 可变性 | 不可变，下标赋值抛 TypeError | 可变，append / insert / 切片赋值 |
| 可哈希 | 所有元素可哈希时可作 dict 键 | 永远不可哈希 |
| 内存（3.13 / 64 位） | (1,2,3) 为 64 字节，无过度分配 | [1,2,3] 为 88 字节，有 allocated 冗余 |
| 典型用途 | 坐标、复合键、函数多返回值、记录 | 需要原地增删的同构序列 |


## 命名元组与 frozen dataclass：给字段一个名字

只带下标的元组强迫读者数位置，工程上应给字段命名。

`collections.namedtuple(typename, field_names)` 是工厂函数，返回一个 tuple 子类：字段用描述符按位置读取，实例仍是 tuple，索引、解包、迭代、比较与 hash 全部沿用 tuple 行为，另有 _fields、`_asdict()`（3.8 起返回普通 dict，之前是 OrderedDict）、`_replace(**kwargs)` 返回新实例、`_make(iterable)` 从序列构造、_field_defaults；

defaults 参数要到 3.7 才有，`rename=True` 会把非法或重复字段名自动重命名。

`typing.NamedTuple` 用类语法（3.6+）在类体里写类型注解与默认值，可读性最好，还能加方法。

`dataclasses.dataclass(frozen=True)`（3.7+）是另一种方案：它是普通类，装饰器生成 `__init__`、`__repr__`、`__eq__` 与拦截赋值的 `__setattr__`，字段赋值抛 FrozenInstanceError（AttributeError 的子类），frozen 且 eq 为真时会自动生成 `__hash__`，因此实例同样可作 dict 键，但不再具备 tuple 的索引与解包协议。

选择依据很直接：要当缓存键、要解包、要和现有 tuple 代码互通就用 NamedTuple；要方法、校验、可变默认值策略就用 frozen dataclass。

```python
from typing import NamedTuple
from dataclasses import dataclass, FrozenInstanceError

class Point(NamedTuple):
    x: int
    y: int = 0

p = Point(3)
print('NamedTuple defaults', p, Point._field_defaults, p._asdict())

@dataclass(frozen=True)
class Config:
    host: str
    port: int = 8080

c = Config('localhost')
print('frozen hash', hash(c) == hash(Config('localhost', 8080)))
try:
    c.port = 9090
except FrozenInstanceError as e:
    print('frozen error', type(e).__name__)

def minmax(xs):
    return min(xs), max(xs)
lo, hi = minmax([3, 1, 9])
print('multi return', lo, hi, type(minmax([1])).__name__)
```

<OutputBox title='对照写法：先自己猜，再点开' output='NamedTuple defaults Point(x=3, y=0) {&#39;y&#39;: 0} {&#39;x&#39;: 3, &#39;y&#39;: 0}\nfrozen hash True\nfrozen error FrozenInstanceError\nmulti return 1 9 tuple' guess="true" />


## 解包、序列模式匹配与作为字典键

函数返回多个值本质是返回一个 tuple，调用方用 a, `b = f`() 解包；a, *`rest = t` 是扩展解包（3.0+），星号目标永远是 list，即使源是 tuple；嵌套结构可写 (a, (b, c)) = data 逐层解包，元素个数不符抛 ValueError。

3.10 起 match-case 的序列模式能直接对 tuple 与 list 按位置匹配：case (0, 0) 匹配原点、case (x, 0) 匹配落在 x 轴上的点、case (x, y) 兜底绑定两个坐标，模式里出现的字面量按相等比较、出现的名字按位置捕获。

元组按元素字典序比较，(1, 2) < (1, 3) 为真，因此 sorted 一堆坐标会先按第一个字段排，这正是复合键天然有序的原因；把 (x, y) 当 dict 键还能做网格、坐标映射与 memo 缓存。

多参数函数的 *args 在函数内部就是一个 tuple，也印证了元组是 Python 里传递'一组固定位置值'的默认载体。

CPython 的 tuple 是 PyTupleObject：对象头之后紧跟一段与 ob_size 等长的 PyObject* 数组，一次性分配、没有 list 那样的 allocated 冗余，因此同样元素下比 list 省内存（64 位 3.13 实测 (1,2,3) 为 64 字节、[1,2,3] 为 88 字节）；

只含常量的元组还会被编译器折叠进 code object 的 co_consts。不可变只约束这串指针：t[0] 存的是某个 list 对象的引用，改不了指针本身，却能改那个 list 的内容，所以'元组不可变'是浅层的。

`hash(tuple)` 逐元素取哈希并组合，只要有一个元素不可哈希就抛 TypeError，这解释了为什么含 list 的元组不能当 dict 键。

`collections.namedtuple` 生成一个 tuple 子类，字段是 property 描述符，底层仍按位置存指针，因此索引、解包、比较与 hash 全部沿用 tuple 行为，只是多了可读名字；

`typing.NamedTuple` 是同一思路的类语法糖，而 `dataclass(frozen=True)` 是普通类加生成的 `__setattr__` 拦截，frozen 且 eq 为真时 dataclass 装饰器会一并生成 `__hash__`。


## 配置快照：用 NamedTuple 命名字段并做可哈希的缓存键

一个报表服务把查询条件（时间范围、指标列表、维度）拼成缓存键。最初用普通 tuple (start, end, `tuple(metrics)`)，读代码的人必须数下标，某次有人把指标列表写成 list 导致 hash 抛 TypeError，整层缓存失效。

改用 `typing.NamedTuple` 给字段命名并声明类型，字段全部用不可变值（指标用 tuple 而不是 list），实例仍是 tuple 子类，可直接当 dict 键；

_replace 生成新实例便于派生变体，_asdict 便于打日志，解包与索引仍然可用。重点是'可哈希、字段自解释、可派生'三件事由类型本身保证，而不是靠调用方记得怎么拼；下游按位置解包也与旧代码无缝衔接。真实工程还会把 key 的哈希值与命中率打进监控，但类型选型的边界在这里已经定死。

```python
from typing import NamedTuple

class QueryKey(NamedTuple):
    start: int
    end: int
    metrics: tuple

cache = {}

def lookup(key):
    if key not in cache:
        cache[key] = {'rows': key.end - key.start, 'metrics': len(key.metrics)}
    return cache[key]

k = QueryKey(100, 200, ('pv', 'uv'))
print('first', lookup(k))
print('same key reused', lookup(QueryKey(100, 200, ('pv', 'uv'))) is cache[k])
variant = k._replace(end=300)
print('variant', variant, lookup(variant))
print('asdict keys', list(k._asdict()))

a, b, m = k
print('unpack', a, b, m)
```

<Callout type="idea" title='落地提示' text='用 NamedTuple 或 dataclass(frozen=True) 给字段命名，既保留不可变性又让接口自解释' />


## 错因速查与选型练习

<Exercise title='基础：单元素元组与浅层不可变的边界' task='写出单元素元组的正确写法，用 type 验证 (1) 与 (1,) 的区别；构造含 list 的元组，修改内部 list 并尝试 hash，打印两类结果。' solution='one = (1,)\nprint(&#39;types&#39;, type((1)).__name__, type(one).__name__)\nt = ([1, 2], &#39;x&#39;)\nt[0].append(3)\nprint(&#39;inner mutable&#39;, t)\ntry:\n    hash(t)\nexcept TypeError as e:\n    print(&#39;hash error&#39;, type(e).__name__)\nprint(&#39;tuple of tuple ok&#39;, hash(((1, 2), &#39;x&#39;)) is not None)' explain='括号只是分组，逗号才是元组构造符；不可变只约束外层指针数组，内层 list 可改且会让整体不可哈希。把嵌套容器换成 tuple 即可恢复可哈希，这也是复合缓存键的正确写法。' />

<Exercise title='进阶：用 NamedTuple 与 frozen dataclass 表达同一份配置并对比' task='分别用 typing.NamedTuple 与 dataclass(frozen=True) 定义带默认端口的配置，比较二者是否可作 dict 键、赋值失败时各抛什么异常，并说明选择依据。' solution='from typing import NamedTuple\nfrom dataclasses import dataclass, FrozenInstanceError\n\nclass NT(NamedTuple):\n    host: str\n    port: int = 8080\n\n@dataclass(frozen=True)\nclass DC:\n    host: str\n    port: int = 8080\n\nnt, dc = NT(&#39;h&#39;), DC(&#39;h&#39;)\nprint(&#39;nt key&#39;, {nt: 1}[NT(&#39;h&#39;, 8080)], &#39;dc key&#39;, {dc: 2}[DC(&#39;h&#39;, 8080)])\nprint(&#39;nt is tuple&#39;, isinstance(nt, tuple), &#39;dc is tuple&#39;, isinstance(dc, tuple))\nfor obj in (nt, dc):\n    try:\n        obj.port = 9\n    except (AttributeError, FrozenInstanceError) as e:\n        print(type(obj).__name__, &#39;-&gt;&#39;, type(e).__name__)' explain='NamedTuple 仍是 tuple 子类，天然可哈希、可解包、可按下标访问，适合当缓存键与记录；frozen dataclass 是普通类，可写方法与字段校验，但不再具备 tuple 的序列协议。两者都禁止字段赋值，异常分别是 AttributeError 与它的子类 FrozenInstanceError。' />

<Quiz no='020-1' q='type((1)) 与 type((1,)) 分别是什么？' :options='["tuple 与 tuple", "int 与 tuple", "int 与 int", "tuple 与 int"]' answer="1" explain='括号只做分组，元组的构造靠逗号；单元素必须写 (1,)，漏写逗号得到的就是括号里的标量 int。' />

<Quiz no='020-2' q='关于元组可作 dict 键，哪项正确？' :options='["所有元组都可哈希", "只要所有元素都可哈希，元组就可哈希；含 list 会抛 TypeError", "元组永远不可哈希", "只有空元组可哈希"]' answer="1" explain='hash(tuple) 逐元素取哈希并组合，含 list / dict / set 等不可哈希元素时整体抛 TypeError，不能作键。' />

<Quiz no='020-3' q='collections.namedtuple 与 typing.NamedTuple 生成的类有什么共同点？' :options='["都是 list 子类", "都是 tuple 子类，实例支持索引、解包与 hash", "都不可哈希", "都要求 3.10 以上"]' answer="1" explain='两者底层都是 tuple 子类，字段是描述符，_fields / _asdict / _replace 可用，索引、解包、比较与 hash 全部沿用 tuple 行为。' />

<KnowledgeCard :points='["元组由逗号构造，单元素必须写 (1,)；括号多数场合可省", "不可变是浅层的：不能改指针，但能改指针指向的 list；hash 要求所有元素可哈希", "tuple 无 allocated 过度分配，比同元素 list 省内存；只含常量时会被折叠进 co_consts", "collections.namedtuple 与 typing.NamedTuple 都生成 tuple 子类，保留索引、解包、比较与可哈希", "dataclass(frozen=True) 赋值抛 FrozenInstanceError，frozen 且 eq 为真时自动生成 __hash__", "需要命名字段又想当缓存键用 NamedTuple；需要方法与校验用 frozen dataclass；需要原地增删才用 list"]' :pitfalls='["想表示单元素元组却写成 (1)，得到的是整数", "把含 list 的元组当 dict 键时抛 TypeError", "以为 tuple 不可变就代表里面数据不会变", "把坐标、配置项、数据库一行记录都塞进只带下标的元组，读代码的人必须数位置"]' summary='元组的不可变只约束引用，里面若装了 list 依然可变；可哈希要求所有元素都可哈希' />

1. 元组由逗号构造，单元素必须写 (1,)；括号多数场合可省

2. 不可变是浅层的：不能改指针，但能改指针指向的 list；hash 要求所有元素可哈希

3. tuple 无 allocated 过度分配，比同元素 list 省内存；只含常量时会被折叠进 co_consts

[下一讲：dict：哈希表、视图与插入顺序](/containers/dict-basics)

<Predict no='020-P' q='t = ([1, 2], 3); t[0].append(9); hash(t) 这三步的结果依次是？' :options='["t 变成 ([1, 2, 9], 3)，hash 正常返回整数", "抛 TypeError，因为 tuple 不支持内部 list 修改", "t 变成 ([1, 2, 9], 3)，随后 hash 抛 TypeError"]' answer='2' output='t 变成 ([1, 2, 9], 3)，随后 hash 抛 TypeError' explain='元组的不可变只约束它保存的指针数组，t[0] 指向的 list 仍可原地 append；但 hash(tuple) 要求每个元素可哈希，含 list 时抛 TypeError: unhashable type: &#39;list&#39;。' />

<FillBlank no='020-F' tpl='from collections  ___ namedtuple' :answers='["import"]' hint='回想本讲关于 元组与单元素写法 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 语法与浅层不可变：逗号才是构造符 的落点。' />
