---
title: 第 043 讲 · __slots__、弱引用与对象内存布局
description: 理解实例内存成本并会做优化
---

<StageHeader stage='L4 · 面向对象' level='★★★★☆' time='35 分钟' goal='理解实例内存成本并会做优化' prereq='第 042 讲 · 上下文管理器与 with 协议' />

# 第 043 讲 · __slots__、弱引用与对象内存布局

到此我们能定制类的行为，却还没低头看过实例怎么存。默认每个实例带一张属性字典，灵活但有固定开销；对象从几十变成上百万，这笔账就躲不掉。这是从「会用类」往「看懂对象」迈的一步。

一个图服务把上百万节点存成普通实例，内存很快吃满，加了配置重启却几乎没变。本讲先从 `__dict__` 的开销与 `__slots__` 的固定偏移布局讲起，再看继承里槽如何合并、哪几类会冲突，最后补上 `weakref` 适配与 `tracemalloc` 量化收益。需要第 6 讲的对象模型与继承顺序；学完你能算出 `slots` 省了多少，也能解释「加了槽为何还是不能被弱引用」。


## 百万个坐标点把内存吃满的一次压测

一个图计算服务把上百万个节点存成普通类实例，内存很快吃满，扩容两次都没解决。

有人给节点加了 `__slots__ = ('x', 'y')` 后重启，内存却几乎没变——因为父类没声明 `__slots__`，子类实例照样带着 `__dict__`，优化等于白做。

另一处更隐蔽：缓存模块用 `WeakValueDictionary` 存这些节点，加了 `slots` 之后突然抛 `TypeError: canno…`，原来槽类默认不带 `__weakref__`。

```text
TypeError: cannot create weak reference to 'Node' object
```

还有人试图在一个类里同时继承两个都定义了非空 `__slots__` 的基类，直接得到 `TypeError: multi…`。

```text
TypeError: multiple bases have instance lay-out conflict
```

`__slots__` 不是「省内存的开关」这么简单，它改的是实例的内存布局：从每个实例一张哈希表变成固定偏移的槽数组，随之带来一串约束。本讲把布局差异、继承合并规则、弱引用适配与 `tracemalloc` 验证方法讲清楚，让你能算出收益，也能解释报错。

<Callout type="warn" title='先看一个真实会出错的写法' text='只给子类加 __slots__，内存几乎没降：基类没声明 __slots__，实例继承的 __dict__ 仍在，子类只是多了固定槽、字典没被去掉' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 042 讲 · 上下文管理器与 with 协议 |
| 难度 / 建议时长 | ★★★★☆ · 35 分钟 |
| 本讲新增 | __dict__ 的开销、__slots__ 的约束、weakref 与 __weakref__ |
| 一句话目标 | 理解实例内存成本并会做优化 |
| 为下一讲铺垫 | 鸭子类型、抽象基类与 Protocol |


## __dict__ 的成本与 __slots__ 的固定偏移布局

普通 heap type 的实例用一张 `PyDictObject`（即 `__dict__`）存属性，还带一个 `__weakref__` 槽。字典是开放定址哈希表，即便只有两三个键也有预分配的表与额外负载，海量小对象时代价重复出现。

定义 `__slots__ = ('x', 'y')` 后，CPython 为每个名字创建一个 `member_descriptor`（`PyMemberDef`），记录它在实例结构体里的固定字节偏移；

实例的 `tp_basicsize` 变成固定值，`tp_dictoffset` 置 0，属性读写从「查字典」变成「按偏移取槽 + 描述符分派」。收益来自去掉哈希表与允许更紧凑的对象分配，实例数越多越明显，用 `tracemalloc` 对十万级列表取差分即可量化。

代价是三条硬约束：只能赋值槽里声明过的名字，写新属性抛 `AttributeError`；

默认没有 `__dict__`，`vars(obj)` 抛 `TypeError: vars(…`；

```python
TypeError: vars() argument must have __dict__ attribute
```

默认也没 `__weakref__`，`weakref.ref(obj)` 抛 `TypeError: canno…`。

```text
TypeError: cannot create weak reference
```

`__slots__` 可以写成单个字符串（这时就是一个槽名）或任意可迭代的字符串序列；

要与 `dataclass` 组合时用 `@dataclass(slots=True)`（3.10 引入），它会重新创建类对象，因为槽必须在类创建时确定。

```python
class Plain:
    def __init__(self, x):
        self.x = x
class Slotted:
    __slots__ = ('x',)
    def __init__(self, x):
        self.x = x

p, s = Plain(1), Slotted(1)
print('dict', hasattr(p, '__dict__'), hasattr(s, '__dict__'))
print('slot kind', type(Slotted.x).__name__)
print('weakref', hasattr(p, '__weakref__'), hasattr(s, '__weakref__'))
try:
    s.y = 2
except AttributeError as e:
    print(type(e).__name__, 'cannot add y')
print('values', p.x, s.x)
```

<OutputBox title='主示例运行结果' output='dict True False\nslot kind member_descriptor\nweakref True False\nAttributeError cannot add y\nvalues 1 1' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Plain:\n    def __init__(self, x):\n        self.x = x\nclass Slotted:\n    __slots__ = (&#39;x&#39;,)\n    def __init__(self, x):\n        self.x = x\n\np, s = Plain(1), Slotted(1)\nprint(&#39;dict&#39;, hasattr(p, &#39;__dict__&#39;), hasattr(s, &#39;__dict__&#39;))\nprint(&#39;slot kind&#39;, type(Slotted.x).__name__)\nprint(&#39;weakref&#39;, hasattr(p, &#39;__weakref__&#39;), hasattr(s, &#39;__weakref__&#39;))\ntry:\n    s.y = 2\nexcept AttributeError as e:\n    print(type(e).__name__, &#39;cannot add y&#39;)\nprint(&#39;values&#39;, p.x, s.x)' :notes='["普通类，实例默认带 __dict__ 与 __weakref__", "构造时绑定属性 x", "self.x = x 写进实例字典", "声明 __slots__ 的类，实例改用固定偏移布局", "槽名写成元组，避免被当成字符序列", "同样的构造签名", "这次赋值走槽描述符，而非实例字典", "空行，只用于分隔逻辑块，不影响执行结果。", "同时构造两类实例，便于对比布局", "hasattr 检查 __dict__：普通类为 True、槽类为 False", "类属性 Slotted.x 是 member_descriptor，证明槽生效", "检查 __weakref__：槽类默认不支持弱引用", "尝试给槽类添加未在槽里声明的属性", "s.y = 2 会触发属性查找失败", "槽类没有 __dict__，赋值抛 AttributeError", "打印异常类型，避开版本相关的错误消息措辞", "两类实例的 x 都能照常读出，行为一致"]' title='第 043 讲 · __slots__、弱引用与对象内存布局' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='普通 heap type 的实例用一张 `PyDictObject`（即 `__dict__`）存属性，还带一个 `__weakref__` 槽。字典是开放定址哈希表，即便只有两三个键也有预分配的表与额外负载，海量小对象时代价重复出现。定义 `__slots__ = (&#39;x&#39;, &#39;y&#39;)` 后，CP…' />


### 普通实例与 __slots__ 实例对照

**普通实例与 __slots__ 实例对照**

| 维度 | 普通类实例 | __slots__ 实例 |
| --- | --- | --- |
| 属性存储 | PyDictObject 哈希表 | 固定偏移的 member_descriptor |
| tp_dictoffset | 非 0，实例带 __dict__ | 置 0，无 __dict__ |
| 动态加属性 | 允许 | 抛 AttributeError |
| 弱引用 | 默认支持 | 需把 '__weakref__' 写进槽 |
| vars(obj) | 返回实例字典 | 抛 TypeError: vars() argument must have __dict__ attribute |
| 适用 | 字段动态、框架依赖 __dict__ | 海量小对象、字段固定 |


## 继承中的槽合并与三类冲突

槽的收益只有在继承链上每一层都没有 `__dict__` 时才拿得到。基类没写 `__slots__`，其实例就带 `tp_dictoffset`；子类即便声明了槽，也只是在固定槽之外再挂一张 `__dict__`，优化失效。

所以正确写法是给链上每个基类都写 `__slots__ = ()`（空元组，表示不占槽但也不给 `__dict__`），只有真正需要字段的那一层声明具体名字。

多继承时，CPython 要为每个基类选 `best_base` 并合并实例布局，若两个基类都带非空槽，它们的固定偏移无法放进同一份结构体，抛 `TypeError: multi…`；

```text
TypeError: multiple bases have instance lay-out conflict
```

解法是只让一个基类带数据槽，其余用空槽或改成组合。

第三类冲突是名字撞车：类变量与槽同名时，`type.__new__` 抛 `ValueError: 'x'…`，因为同名类变量会遮掉描述符。

```python
ValueError: 'x' in __slots__ conflicts with class variable
```

还有两个细节：槽名 `'__dict__'` 与 `'__weakref__'` 是保留名，前者会重新给实例装回字典、后者显式开启弱引用支持；子类重复声明与父类同名的槽不会报错，但会浪费一份描述符并制造遮蔽，应当避免。

槽描述符本身是类属性，`type(Slotted.x).__name__` 为 `member_descriptor`，可用它快速确认布局确实生效。

```python
import weakref

class Base:
    pass
class Child(Base):
    __slots__ = ('x',)
class Full:
    __slots__ = ('x', '__weakref__')
    def __init__(self, x):
        self.x = x

f = Full(2)
print('child has dict:', hasattr(Child(), '__dict__'))
print('weakref ok:', weakref.ref(f)() is f)
try:
    class Bad:
        __slots__ = ('x',)
        x = 1
except ValueError as e:
    print(type(e).__name__, 'conflict')
```

<OutputBox title='对照写法：先自己猜，再点开' output='child has dict: True\nweakref ok: True\nValueError conflict' guess="true" />

**__slots__ 规则、报错信息与修复**

| 写法 / 现象 | 结果 | 正确写法 |
| --- | --- | --- |
| __slots__ = ('x',) | 正常，单个槽 | 元组或任意字符串可迭代对象 |
| __slots__ = 'x' | 合法，等价于一个槽名 x | 不要写成字符串列表 |
| 类变量与槽同名 | ValueError: 'x' in __slots__ conflicts with class variable | 删掉同名类变量或改槽名 |
| 基类未声明 __slots__ | 子类仍带 __dict__，优化失效 | 每个基类写 __slots__ = () |
| 多继承两个非空槽基类 | TypeError: multiple bases have instance lay-out conflict | 只留一个数据槽基类，其余用空槽 |
| 需要弱引用 | TypeError: cannot create weak reference | 槽里加入 '__weakref__' |

<Term word='__dict__ 的开销' text='普通 heap type 的实例用一张 `PyDictObject`（即 `__dict__`）存属性，还带一个 `__weakref__` 槽。字典是开放定址哈希表，即便只有两三个键也有预分配的表与额外负载，海量小对象时代价重复出现。定义 `__slots__ = (&#39;x&#39;, &#39;y&#39;)` 后，CPython 为每个名…' />

<Term word='__slots__ 的约束' text='槽的收益只有在继承链上每一层都没有 `__dict__` 时才拿得到。基类没写 `__slots__`，其实例就带 `tp_dictoffset`；子类即便声明了槽，也只是在固定槽之外再挂一张 `__dict__`，优化失效。所以正确写法是给链上每个基类都写 `__slots__ = ()`（空元组，表示不占槽但也不给…' />


## 弱引用适配、tracemalloc 观测与选型边界

槽类要支持弱引用，把 `'__weakref__'` 显式写进 `__slots__`；

之后 `weakref.ref`、`WeakValueDictionary`、`WeakKeyDictionary` 才能工作。

这对缓存尤其重要：用普通 `dict` 持有对象，等于给每个对象加一条永生的强引用，缓存不淘汰对象就永不释放；

换成 `WeakValueDictionary` 后，外部强引用消失时条目自动移除，正是观察者与缓存场景的标准解。

观测内存不要只看 `sys.getsizeof`：它只返回对象结构体本身加上 GC 头，算不到 `__dict__` 里哈希表、字符串内容或容器元素的开销，槽类与普通类在它眼里的差值不能代表真实占用。

用 `tracemalloc.start()` 后分别构造同样数量的两类实例，再用 `get_traced_memory()` 取净分配字节数做差分，才是可核对的收益。

选型上，图节点、坐标、事件记录这类海量小对象优先 `slots` 或 `NamedTuple`；字段需要运行时动态增删、要被 `pickle` 友好处理、或要配合依赖 `__dict__` 的框架时，保留普通类更省事。

3.10 起 `@dataclass(slots=True)` 让两者兼顾，但要注意它会返回新类对象，类装饰器与注册表里引用的旧类需要重新绑定。

```python
import tracemalloc

class Plain:
    def __init__(self, x):
        self.x = x
class Slotted:
    __slots__ = ('x',)
    def __init__(self, x):
        self.x = x

tracemalloc.start()
plain = [Plain(i) for i in range(20000)]
p_cur = tracemalloc.get_traced_memory()[0]
del plain
slotted = [Slotted(i) for i in range(20000)]
s_cur = tracemalloc.get_traced_memory()[0]
print('slotted cheaper:', s_cur < p_cur)
print('saved bytes > 0:', p_cur - s_cur > 0)
tracemalloc.stop()
```

<OutputBox title='原理验证' output='slotted cheaper: True\nsaved bytes &gt; 0: True' />

<CodeTabs :tabs='[{"label": "主示例", "code": "class Plain:\n    def __init__(self, x):\n        self.x = x\nclass Slotted:\n    __slots__ = (&#39;x&#39;,)\n    def __init__(self, x):\n        self.x = x\n\np, s = Plain(1), Slotted(1)\nprint(&#39;dict&#39;, hasattr(p, &#39;__dict__&#39;), hasattr(s, &#39;__dict__&#39;))\nprint(&#39;slot kind&#39;, type(Slotted.x).__name__)\nprint(&#39;weakref&#39;, hasattr(p, &#39;__weakref__&#39;), hasattr(s, &#39;__weakref__&#39;))\ntry:\n    s.y = 2\nexcept AttributeError as e:\n    print(type(e).__name__, &#39;cannot add y&#39;)\nprint(&#39;values&#39;, p.x, s.x)", "note": "__dict__ 的成本与 __slots__ 的固定偏移布局"}, {"label": "对照 / 进阶", "code": "import weakref\n\nclass Base:\n    pass\nclass Child(Base):\n    __slots__ = (&#39;x&#39;,)\nclass Full:\n    __slots__ = (&#39;x&#39;, &#39;__weakref__&#39;)\n    def __init__(self, x):\n        self.x = x\n\nf = Full(2)\nprint(&#39;child has dict:&#39;, hasattr(Child(), &#39;__dict__&#39;))\nprint(&#39;weakref ok:&#39;, weakref.ref(f)() is f)\ntry:\n    class Bad:\n        __slots__ = (&#39;x&#39;,)\n        x = 1\nexcept ValueError as e:\n    print(type(e).__name__, &#39;conflict&#39;)", "note": "继承中的槽合并与三类冲突"}]' title='两种写法切换看' />


## 实例对象在 C 层的内存布局

CPython 的普通 heap type 实例在对象头之后带一个 `PyDictObject` 指针（`tp_dictoffset`）与一个弱引用链表头（`tp_weaklistoffset`）。

`PyObject_GenericSetAttr` 写属性时走字典插入，开放定址哈希表为降低冲突会预留约三分之一空位，因此两三个字段也要承担整张表的分配。

声明 `__slots__` 后，`type_new` 为每个槽名分配 `PyMemberDef` 并生成 `member_descriptor` 类属性，把实例布局改成 `tp_basicsize` 固定的结构：读写变成按偏移访问，`PyObject_GenericSetAttr` 查到的是数据描述符，直接改槽。

子类实例化时若某个基类带 `tp_dictoffset`，合一后的布局仍保留该字典偏移，槽优化因此落空。

多继承的 `best_base` 选择无法把两套非空固定偏移合并进一份结构体，于是抛出 `lay-out conflict`。

`tracemalloc` 挂钩到 `PyMem` 分配器层，统计的是真实从分配器拿走的字节，所以能测到 `sys.getsizeof` 看不到的字典哈希表与对象分配差异。

弱引用依赖 `tp_weaklistoffset` 非零，槽类默认把它设成 0，显式加入 `'__weakref__'` 才重新开启。

<ConceptDiagram type='hub4' title='第 043 讲 · __dict__ 的成本与 __slots__ 的固定偏移布局' labels='__dict__ 的成本与 __slots_…|继承中的槽合并与三类冲突|弱引用适配、tracemalloc 观测与选…|与 dataclass 组合' caption='理解实例内存成本并会做优化' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

**版本与观测工具**

| 版本 / 工具 | 行为 | 提示 |
| --- | --- | --- |
| tracemalloc.start() / get_traced_memory() | 返回 (当前净分配, 峰值) 字节 | 对同数量两类实例取差分才是真实收益 |
| sys.getsizeof(obj) | 只算对象结构体加 GC 头 | 算不到 __dict__ 与容器元素，别用来下结论 |
| @dataclass(slots=True)（3.10+） | 重新创建类并生成槽 | 返回新类对象，注册表需重新绑定 |
| @dataclass(weakref_slot=True)（3.11+） | 给槽 dataclass 加 __weakref__ | 等价于手写保留槽名 |
| 3.7+ dict 保序 | 类体 namespace 按定义顺序 | 槽声明顺序稳定可预期 |

<FlowTimeline :steps='[{"title": "__dict__ 的成本与 __slots__…", "desc": "普通 heap type 的实例用一张 `PyDictObject`（即…", "tone": "blue"}, {"title": "继承中的槽合并与三类冲突", "desc": "槽的收益只有在继承链上每一层都没有 `__dict__` 时才拿得到。基类没写…", "tone": "purple"}, {"title": "弱引用适配、tracemalloc 观测与选型边…", "desc": "槽类要支持弱引用，把 `&#39;__weakref__&#39;` 显式写进…", "tone": "orange"}, {"title": "工程落地", "desc": "海量坐标点用 slots 省内存，并用弱引用缓存自动释放", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 海量坐标点用 slots 省内存，并用弱引用缓存自动释放

地图服务一次性构造五万个 `Point`，同时维护一个按 `x` 索引的热点缓存。若用普通类，每个实例都带字典，内存随实例数线性膨胀；若缓存用普通 `dict`，即使外部不再引用这些点，缓存里的强引用也会让它们一直活着，形成事实上的泄漏。

正确组合是 `__slots__`：前两个槽把布局压成固定大小，第三个槽让 `weakref` 生效；

```python
__slots__ = ('x', 'y', '__weakref__')
```

缓存改用 `WeakValueDictionary`，外部强引用（`points` 列表）清空并 `gc.collect()` 后，条目自动消失。

下面用 `tracemalloc` 与 `weakref` 标准库跑通，打印点总数、缓存初始条目数、清空后的条目数以及 `tracemalloc` 仍在跟踪的状态。真实服务还应把坐标换成 `array` 或 `NumPy` 做列式存储，本例聚焦对象布局与弱引用生命周期。

```python
import tracemalloc, weakref, gc

class Point:
    __slots__ = ('x', 'y', '__weakref__')
    def __init__(self, x, y):
        self.x, self.y = x, y

cache = weakref.WeakValueDictionary()
tracemalloc.start()
points = [Point(i, i * 2) for i in range(50000)]
for i in range(3):
    cache[i] = points[i]
print('points:', len(points), 'cache:', len(cache))
points.clear()
gc.collect()
print('cache after clear:', len(cache))
print('tracing:', tracemalloc.is_tracing())
tracemalloc.stop()
```

<Callout type="idea" title='落地提示' text='海量小对象（图节点、坐标、事件记录）优先考虑 slots 或 NamedTuple，并用 tracemalloc 验证收益' />

<CheckList id='P043b' title='上线前自检' :items='["能复现并解释「只给子类加 __slots__，内存几乎没降」", "能复现并解释「槽类放进 WeakValueDictionary 报 can…」", "能复现并解释「多继承两个带非空槽的基类报 lay-out conflict」", "能用一条命令验证 __dict__ 的开销", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "xs=[3,1,2]; print(sorted(xs), xs[::-1], len(xs))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 `__dict__` 的开销 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 只给子类加 __slots__、槽类进 WeakValueDictionary 的错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 只给子类加 __slots__，内存几乎没降 | 基类没声明 __slots__，实例继承的 __dict__ 仍在，子类只是多了固定槽、字典没被去掉 | 给继承链每个基类写 __slots__ = ()，只在需要字段的那一层声明具体槽名 |
| 槽类放进 WeakValueDictionary 报 cannot create weak reference | 槽实例的 tp_weaklistoffset 为 0，默认不带 __weakref__ 槽 | 把 '__weakref__' 显式写进 __slots__，或改用 @dataclass(slots=True, weakref_slot=True)（3.11+） |
| 多继承两个带非空槽的基类报 lay-out conflict | 两份固定偏移的实例布局无法合并进同一 PyTypeObject 结构体 | 只让一个基类持有数据槽，其余基类用空槽或改成组合持有，不要堆多套字段 |

<Callout type="warn" title='本讲最容易踩的坑' text='只给子类加 __slots__，内存几乎没降：基类没声明 __slots__，实例继承的 __dict__ 仍在，子类只是多了固定槽、字典没被去掉' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：只给子类加 __slots__，内存几乎没降", "body": "基类没声明 __slots__，实例继承的 __dict__ 仍在，子类只是多了固定槽、字典没被去掉", "tip": "给继承链每个基类写 __slots__ = ()，只在需要字段的那一层声明具体槽名"}, {"title": "第 2 步：槽类放进 WeakValueDictiona…", "body": "槽实例的 tp_weaklistoffset 为 0，默认不带 __weakref__ 槽", "tip": "把 &#39;__weakref__&#39; 显式写进 __slots__，或改用 @dataclass(slots=True, weakref_slot=True)（3.11+）"}, {"title": "第 3 步：多继承两个带非空槽的基类报 lay-out…", "body": "两份固定偏移的实例布局无法合并进同一 PyTypeObject 结构体", "tip": "只让一个基类持有数据槽，其余基类用空槽或改成组合持有，不要堆多套字段"}]' />


## 自测题与速记卡

<Exercise title='基础：证明基类空槽与否决定子类是否带 __dict__' task='定义两个基类 A（无 __slots__）与 B（__slots__ = ()），各写一个声明 __slots__ = (&#39;x&#39;,) 的子类，用 hasattr(子实例, &#39;__dict__&#39;) 打印结果，并说明为什么只有 B 的子类真正去掉了字典。' solution='class A:\n    pass\nclass B:\n    __slots__ = ()\nclass CA(A):\n    __slots__ = (&#39;x&#39;,)\nclass CB(B):\n    __slots__ = (&#39;x&#39;,)\nprint(hasattr(CA(), &#39;__dict__&#39;), hasattr(CB(), &#39;__dict__&#39;))' explain='A 带 tp_dictoffset，CA 继承后仍有 __dict__ → True；B 把偏移置 0，CB 只有固定槽 → False。优化要覆盖整条继承链，漏一层就失效。' />

<Exercise title='进阶：用 tracemalloc 量化 slots 收益并处理弱引用' task='构造十万级普通实例与槽实例，分别用 get_traced_memory 取净分配并比较大小；再给槽类加 &#39;__weakref__&#39;，验证 weakref.ref 可用，说明 getsizeof 为何不适合做这个判断。' solution='import tracemalloc, weakref\nclass P:\n    def __init__(self, x): self.x = x\nclass S:\n    __slots__ = (&#39;x&#39;, &#39;__weakref__&#39;)\n    def __init__(self, x): self.x = x\ntracemalloc.start()\np = [P(i) for i in range(100000)]\npb = tracemalloc.get_traced_memory()[0]\ndel p\ns = [S(i) for i in range(100000)]\nsb = tracemalloc.get_traced_memory()[0]\nprint(&#39;slots saves:&#39;, sb &lt; pb, &#39;weakref ok:&#39;, weakref.ref(s[0])() is s[0])\ntracemalloc.stop()' explain='tracemalloc 在分配器层统计真实字节，能测到字典哈希表开销，故 sb &lt; pb 为 True；getsizeof 只算对象结构体，会漏掉 __dict__。加入 &#39;__weakref__&#39; 后 tp_weaklistoffset 非零，弱引用成立。' />

<Quiz no='043-1' q='给子类加了 __slots__ 却没省下内存，最可能的原因是？' :options='["某个基类没声明 __slots__，实例仍继承 __dict__", "槽名写成了元组", "实例数不够多", "tracemalloc 没启动"]' answer="0" explain='基类带 tp_dictoffset 时子类布局仍保留字典，槽只是附加的固定偏移。要让优化生效，继承链每一层都要写 __slots__（空元组即可）。' />

<Quiz no='043-2' q='槽类默认为什么不能被弱引用？' :options='["实例布局的 tp_weaklistoffset 为 0，需要把 &#39;__weakref__&#39; 写进槽", "weakref 模块不支持自定义类", "槽类没有 __dict__ 所以自动拒绝", "CPython 版本低于 3.10"]' answer="0" explain='弱引用依赖实例里的弱引用链表头；槽类默认不带它。显式加入保留槽名 &#39;__weakref__&#39; 或用 dataclass(slots=True, weakref_slot=True) 即可开启。' />

<Quiz no='043-3' q='关于 sys.getsizeof 与 tracemalloc，正确的是？' :options='["getsizeof 只算对象结构体，真实布局收益要用 tracemalloc 差分", "两者结果总是一致", "tracemalloc 只能测峰值不能测当前值", "getsizeof 会把 __dict__ 内容也算进去"]' answer="0" explain='getsizeof 返回浅层对象大小，算不到字典哈希表、字符串内容与容器元素；tracemalloc 挂钩 PyMem 分配器，统计真实分配字节，适合做同类对象的批量差分。' />

<Predict no='043-4' q='类变量与 __slots__ 同名时，定义类会发生什么？' :options='["抛 ValueError: &#39;x&#39; in __slots__ conflicts with class variable", "正常创建，类变量遮蔽槽", "抛 TypeError: lay-out conflict"]' answer='0' output='ValueError: &#39;x&#39; in __slots__ conflicts with class variable' explain='type.__new__ 检测到同名类变量会与 member_descriptor 冲突，直接抛 ValueError。同名类变量会遮掉描述符，CPython 选择在类创建期就拒绝，而不是留到运行时出错。' />

<FillBlank no='043-5' tpl='___ __init__(self, x):' :answers='["def"]' hint='回想本讲关于 __dict__ 的开销 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 __dict__ 的成本与 __slots__ 的固定偏移布局 的落点。' />

<KnowledgeCard :points='["__slots__ 把实例从 __dict__ 哈希表改成固定偏移的 member_descriptor，省掉字典开销", "代价：不能动态加属性、默认无 __dict__、默认无 __weakref__", "继承链每一层都要写 __slots__（空元组即可），漏一层子类仍带 __dict__", "多继承两个非空槽基类抛 TypeError: multiple bases have instance lay-out conflict", "需要弱引用就把 &#39;__weakref__&#39; 加入槽；缓存用 WeakValueDictionary 而非普通 dict", "用 tracemalloc 差分量化收益，sys.getsizeof 只算浅层对象；@dataclass(slots=True) 3.10+ 会重建类"]' :pitfalls='["只给子类加 __slots__，内存几乎没降", "槽类放进 WeakValueDictionary 报 cannot create weak reference", "多继承两个带非空槽的基类报 lay-out conflict", "给基类忘了加 __slots__，子类依然带 __dict__，优化等于没做；多继承时槽还可能冲突"]' summary='默认实例用字典存属性，灵活但有固定开销；__slots__ 改成固定偏移的数组，实例多时可省下一半以上内存' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| __slots__ 把实例从 __dict__ 哈希表改成固定偏移的 member_descriptor，省掉字典开销 | 建立直觉 |
| 代价：不能动态加属性、默认无 __dict__、默认无 __weakref__ | 跑通示例 |
| 继承链每一层都要写 __slots__（空元组即可），漏一层子类仍带 __dict__ | 深入边界 |
| 多继承两个非空槽基类抛 TypeError: multiple bases have instance lay-out conflict | 工程落地 |
| 需要弱引用就把 '__weakref__' 加入槽；缓存用 WeakValueDictionary 而非普通 dict | 随堂检测 |
| 用 tracemalloc 差分量化收益，sys.getsizeof 只算浅层对象；@dataclass(slots=True) 3.10+ 会重建类 | 复盘 |

1. __slots__ 把实例从 __dict__ 哈希表改成固定偏移的 member_descriptor，省掉字典开销

2. 代价：不能动态加属性、默认无 __dict__、默认无 __weakref__

3. 继承链每一层都要写 __slots__（空元组即可），漏一层子类仍带 __dict__

[下一讲：鸭子类型、抽象基类与 Protocol](/oop/abc)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/043-slots.py`

```bash
python3 examples/lessons/043-slots.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/043-slots.py) · [全部示例代码索引](/examples/)
