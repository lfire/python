---
title: 第 038 讲 · 类与实例：__init__、self 与属性
description: 建立对象创建与属性存储的准确模型
---

<StageHeader stage='L4 · 面向对象' level='★☆☆☆☆' time='30 分钟' goal='建立对象创建与属性存储的准确模型' prereq='第 037 讲 · 阶段综合：缓存装饰器库与插件注册表' />

# 第 038 讲 · 类与实例：__init__、self 与属性

上一讲给函数与抽象收了尾，接下来让数据和行为住在一起。类与实例是面向对象地基的起点，讲的是一份状态怎么被造出来、又怎么被找到：写个购物车把商品列表放在类上，两个实例加东西时竟发现彼此多出对方的商品；也有人以为 `__init__` 造对象，直到写了返回值才碰壁。

先分清 `__new__` 与 `__init__` 各管一段，`self` 只是个约定名；再看实例字典与类字典的查找先后，方法调用时 `self` 怎么被补上；最后聊 `__slots__` 和 `dataclass` 怎样把字段说清楚。需要对象模型与函数绑定的底子；读完你能把各实例该独立的状态放对地方。


## 两个实例改一个，数据怎么串了

一个购物车类把 `items` 写成类属性 `items = []`，实例化两个购物车后往第一个加商品，第二个也凭空多出同样的商品——所有实例共享了同一份列表。

排查时还发现 `__init__` 里写 `return self.items` 会抛 `TypeError: __ini…`；有人一直以为 `__init__` 是构造函数，其实对象早在 `__new__` 里就造好了。

```text
TypeError: __init__() should return None, not 'list'
```

另一个疑惑是方法定义写成 `def add(self, item)`，调用却只写 `cart.add(item)`，`self` 到底从哪来。

本讲把对象创建、属性存储与方法绑定讲清楚：`__new__` 与 `__init__` 的分工、实例 `__dict__` 与类 `__dict__` 的查找顺序、函数是描述符带来的绑定、类属性共享陷阱，以及 `__slots__` 与 `dataclass` 的字段集合。

<Callout type="warn" title='先看一个真实会出错的写法' text='所有状态放类属性，多个实例共享同一份可变数据：可变类属性存在类 __dict__，实例通过查找链看到的是同一个 list / dict' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 037 讲 · 阶段综合：缓存装饰器库与插件注册表 |
| 难度 / 建议时长 | ★☆☆☆☆ · 30 分钟 |
| 本讲新增 | 类对象与实例对象、__init__ 不是构造函数、实例字典 __dict__ |
| 一句话目标 | 建立对象创建与属性存储的准确模型 |
| 为下一讲铺垫 | 属性查找、MRO 与 super |


## __new__ 与 __init__ 的分工

真正创建实例的是 `__new__`，它被 Python 自动当作静态方法处理，返回一个实例（通常由 `object.__new__(cls)` 分配内存）；`__init__(self, ...)` 只负责初始化这个已存在的实例，必须返回 `None`，返回其它值会抛 `TypeError: __ini…`。

```python
__new__(cls, *args, **kwargs)
TypeError: __init__() should return None, not 'list'
```

调用 `C()` 的完整链路是 `type.__call__` 先调 `C.__new__(C)`、确认返回值是 `C`（或其子类）的实例后再自动调 `C.__init__(obj, ...)`、最后把 `obj` 返回给调用方；若 `__new__` 返回的不是当前类的实例，`__init__` 根本不会被调用，这一特性常用于单例、对象池或返回子类实例。

`__new__` 的典型用途还有给 `int`、`tuple` 这类不可变类型在创建时定值（继承它们时，值必须在 `__new__` 阶段确定），普通类几乎不需要重写它。`self` 只是约定名，本质是 `__init__` 收到的实例引用，写成 `this` 语法上合法但不合约定，也会让读代码的人困惑。

```python
class Cart:
    shared = []
    def __new__(cls, owner):
        return super().__new__(cls)
    def __init__(self, owner):
        self.owner = owner
        self.items = []
    def add(self, item):
        self.items.append(item)
        return self.items

a = Cart('a')
b = Cart('b')
a.add('book')
a.shared.append('pen')
print(a.items, b.items, b.shared)
print(type(Cart.add).__name__, type(a.add).__name__)
print(a.add.__self__ is a, a.add.__func__ is Cart.add)
print(vars(a))
```

<OutputBox title='主示例运行结果' output='[&#39;book&#39;] [] [&#39;pen&#39;]\nfunction method\nTrue True\n{&#39;owner&#39;: &#39;a&#39;, &#39;items&#39;: [&#39;book&#39;]}' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Cart:\n    shared = []\n    def __new__(cls, owner):\n        return super().__new__(cls)\n    def __init__(self, owner):\n        self.owner = owner\n        self.items = []\n    def add(self, item):\n        self.items.append(item)\n        return self.items\n\na = Cart(&#39;a&#39;)\nb = Cart(&#39;b&#39;)\na.add(&#39;book&#39;)\na.shared.append(&#39;pen&#39;)\nprint(a.items, b.items, b.shared)\nprint(type(Cart.add).__name__, type(a.add).__name__)\nprint(a.add.__self__ is a, a.add.__func__ is Cart.add)\nprint(vars(a))' :notes='["定义一个购物车类", "类属性 shared 是可变列表，会被所有实例共享", "重写 __new__，演示对象在此阶段分配", "用 super().__new__(cls) 真正创建实例并返回", "__init__ 只做初始化，不负责创建", "把 owner 写进实例字典", "每个实例拿到独立的 items 列表", "定义实例方法，形参 self 由绑定自动传入", "把商品追加到实例自己的列表", "返回列表便于观察", "空行，只用于分隔逻辑块，不影响执行结果。", "创建两个独立实例", "创建第二个实例", "只给 a 加一件商品", "改动类属性 shared，所有实例都会看到", "a 有商品、b 的 items 仍空，但 b.shared 已被改", "类上取到的是 function，实例上取到的是 bound method", "__self__ 绑定 a，__func__ 指回类里的原函数", "vars(a) 显示实例字典里只有 owner 与 items"]' title='第 038 讲 · 类与实例：__init__、self 与属性' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**对象创建链路与字段**

| 阶段 | 方法 | 职责 | 约束 |
| --- | --- | --- | --- |
| 分配实例 | __new__(cls, *a, **k) | 返回实例对象，通常 object.__new__(cls) | 被当作 staticmethod；返回非本类实例则不调 __init__ |
| 初始化 | __init__(self, *a, **k) | 给已存在实例填属性 | 必须返回 None，否则 TypeError: __init__() should return None, not '...' |
| 入口 | type.__call__ | 串起 __new__ 与 __init__ | C() 的完整链路，元类可拦截 |
| self | 只是约定名 | 指向正在初始化的实例 | 写成别的名字合法但不合约定 |

<ConceptDiagram type='hub4' title='第 038 讲 · __new__ 与 __init__ 的分工' labels='__new__ 与 __init__ 的分工|实例字典、类属性与方法绑定|__slots__、dataclass 与属…|self 的本质' caption='建立对象创建与属性存储的准确模型' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 实例字典、类属性与方法绑定

实例属性默认存 `instance.__dict__`（一张 `dict`），类属性存 `Class.__dict__`（`mappingproxy`，不能像普通 `dict` 那样直接赋值修改）；`vars(obj)` 等价于 `obj.__dict__`。

属性查找先查实例 `__dict__`、再查类 `__dict__`、再沿 MRO 查基类，所以实例字典里的同名键会遮蔽类属性（对非数据描述符而言）。

把所有状态放成可变类属性（`list`、`dict`）时，所有实例通过查找链看到的是同一个对象，一处 `append` 影响全部实例，这正是购物车串数据的根因；每个实例独立的状态必须放进 `__init__` 里的 `self.x = []`。

方法能自动收到 `self`，根本原因是类里的 `function` 对象是非数据描述符、实现了 `__get__`：`obj.method` 访问时触发 `__get__(obj, type(obj))`，生成一个 bound method（`types.MethodType`）把 `obj` 固定为第一个参数，于是 `cart.add(item)` 实际调用的是 `C.add(cart, item)`；而 `Class.method` 触发 `__get__(None, C)` 返回原函数，需要显式传 `self`。

可以用 `obj.method.__self__ is obj` 与 `obj.method.__fun…` 验证。

```text
obj.method.__func__ is Class.method
```

**类属性、实例属性与方法绑定**

| 项 | 存放位置 | 行为 |
| --- | --- | --- |
| 实例属性 | obj.__dict__（dict） | 每个实例独立；vars(obj) 可查看 |
| 类属性 | Class.__dict__（mappingproxy） | 所有实例共享；同名实例键会遮蔽它 |
| 可变类属性 | 类 __dict__ 里的 list / dict | 一处 append 影响全部实例，典型 bug |
| 类里的函数 | 类 __dict__ 的 function（非数据描述符） | obj.m 经 __get__ 生成 bound method，自动传 self |
| bound method | types.MethodType | __self__ 是实例、__func__ 是原函数 |

```python
import dis, types

class C:
    def m(self, x):
        return x

c = C()
print(type(C.__dict__['m']).__name__, type(c.m).__name__)
print(isinstance(c.m, types.MethodType), c.m.__self__ is c)
print(C.m.__get__(c, C).__func__ is C.m)
print('self' in C.m.__code__.co_varnames)
ops = [i.opname for i in dis.get_instructions(C.m)]
print('LOAD_FAST' in ops or 'LOAD_FAST_LOAD_FAST' in ops)
```

<OutputBox title='原理验证' output='function method\nTrue True\nTrue\nTrue\nTrue' />

`C()` 的入口是元类 `type.__call__`：它先调用 `C.__new__(C, ...)` 分配一个实例，只有返回值确实是 `C`（或其子类）的实例时才继续调用 `C.__init__(obj, ...)`，最后把 `obj` 返回给调用方。

这也解释了为什么 `__init__` 必须返回 `None`——它的返回值会被 `type.__call__` 丢弃，返回任何别的东西都会触发 `TypeError`。

实例属性默认存在 `obj.__dict__` 这张哈希表里，类属性存在类对象的 `__dict__`（`mappingproxy`）里；属性查找先查实例字典、再查类字典、再沿 MRO 查基类，所以可变类属性会被所有实例共享。

方法能自动收到 `self`，根本原因是 `function` 对象实现了描述符协议 `__get__`：`obj.m` 触发 `function.__get__`，返回一个把 `obj` 绑定为第一个参数的 `MethodType`；`C.m` 触发 `__get__(None, C)` 则原样返回函数。

```python
function.__get__(obj, type(obj))
```

`__slots__` 把实例字典替换成一组固定偏移的槽描述符，槽本身是数据描述符，既省掉每张哈希表的内存，也把可赋属性名限制在声明集合内，代价是失去 `__dict__` 与依赖它的机制。

<Term word='类对象与实例对象' text='真正创建实例的是 `__new__(cls, *args, **kwargs)`，它被 Python 自动当作静态方法处理，返回一个实例（通常由 `object.__new__(cls)` 分配内存）；`__init__(self, ...)` 只负责初始化这个已存在的实例，必须返回 `None`，返回其它值会抛…' />

<Term word='__init__ 不是构造函数' text='实例属性默认存 `instance.__dict__`（一张 `dict`），类属性存 `Class.__dict__`（`mappingproxy`，不能像普通 `dict` 那样直接赋值修改）；`vars(obj)` 等价于 `obj.__dict__`。属性查找先查实例 `__dict__`、再查类…' />


## __slots__、dataclass 与属性边界

`__slots__ = ('x', 'y')` 让类不再为实例分配 `__dict__` 与 `__weakref__`，改用固定偏移的槽（槽本身是数据描述符），既显著省内存，也把能赋的属性名限制在声明集合内；给未声明的名字赋值抛 `AttributeError`，若确实需要动态属性，可在 slots 里显式加 `'__dict__'`。

代价是失去实例字典，因此 `cached_property`（第 034 讲）这类依赖 `__dict__` 的机制不可用；子类若不写自己的 `__slots__`，仍会生成 `__dict__`，父类的省内存效果被抵消。

`dataclass`（PEP 557，3.7+）按类级注解自动生成 `__init__`、`__repr__`、`__eq__`，字段集合自文档化，配合 `frozen=True` 生成不可变对象、`slots=True`（3.10+）自动生成 `__slots__`。

选型上，常量与共享只读数据放类属性（用不可变值），每个实例独立的状态放 `__init__`。

`type(obj) is C`、`isinstance(obj, C)` 与 `obj.__class__` 都能查类型，用 `sys.getsizeof` 可观察到 `__slots__` 省下的主要是实例字典那张哈希表的开销。

```python
from dataclasses import dataclass

class BadInit:
    def __init__(self):
        self.x = 1
        return self.x
try:
    BadInit()
except TypeError as e:
    print(type(e).__name__, str(e))

class SlotPoint:
    __slots__ = ('x', 'y')
    def __init__(self, x, y):
        self.x = x
        self.y = y
p = SlotPoint(1, 2)
print(p.x, p.y, hasattr(p, '__dict__'))
try:
    p.z = 3
except AttributeError as e:
    print(type(e).__name__, str(e))

@dataclass
class Point:
    x: int
    y: int = 0
q = Point(3)
print(q, q.x, q.y)
```

<OutputBox title='对照写法：先自己猜，再点开' output='TypeError __init__() should return None, not &#39;int&#39;\n1 2 False\nAttributeError &#39;SlotPoint&#39; object has no attribute &#39;z&#39; and no __dict__ for setting new attributes\nPoint(x=3, y=0) 3 0' guess="true" />

**__slots__ 与 dataclass 对照**

| 特性 | 版本 | 作用 | 边界 |
| --- | --- | --- | --- |
| __slots__ | 长期稳定 | 去掉实例 __dict__，改固定槽省内存 | 未声明属性赋值抛 AttributeError；cached_property 不可用 |
| 子类不写 slots | — | 仍会生成 __dict__ | 父类的省内存效果被抵消 |
| dataclass（PEP 557） | 3.7+ | 按注解生成 __init__ / __repr__ / __eq__ | 字段集合自文档化 |
| dataclass(slots=True) | 3.10+ | 自动生成 __slots__ | 与手写的实例字典假设冲突 |
| sys.getsizeof | 标准库 | 观察对象与字典的内存占用 | __slots__ 省下的主要是实例字典 |


## 用 dataclass 加 __slots__ 定义一个值对象，并读懂方法绑定

一个金额值对象需要固定字段、可读的 `repr`、相等比较，还要在大量实例下省内存。

手写 `__init__` 容易漏字段或把可变默认值写错，用 `@dataclass(slots=True)` 一行就能按注解生成 `__init__` / `__repr__` / `__eq__`，并自动生成 `__slots__` 去掉实例字典。

下面实现 `Money`：`add` 方法先校验币种再返回新对象，`as_dict` 给出可序列化形式；随后验证实例确实没有 `__dict__`、给未声明属性赋值会抛 `AttributeError`，并打印类上取到的 `function` 与实例上取到的 bound method，把 `self` 的来源变成可核对的证据。

真实项目里这类值对象还常加 `frozen=True` 变成不可变。

```python
from dataclasses import dataclass

@dataclass(slots=True)
class Money:
    amount: int
    currency: str = 'CNY'
    def add(self, other):
        if self.currency != other.currency:
            raise ValueError('currency mismatch')
        return Money(self.amount + other.amount, self.currency)
    def as_dict(self):
        return {'amount': self.amount, 'currency': self.currency}

a = Money(100)
b = Money(50)
c = a.add(b)
print(c, c.amount, c.currency)
print(hasattr(a, '__dict__'), hasattr(c, '__dict__'))
print(type(Money.add).__name__, type(a.add).__name__, a.add.__self__ is a)
print(a.as_dict())
try:
    a.extra = 1
except AttributeError as e:
    print(type(e).__name__, str(e))
```

<Callout type="idea" title='落地提示' text='用 __slots__ 或 dataclass 明确字段集合，既省内存也让接口自文档化' />

<Compare :panels='[{"label": "主示例", "code": "class Cart:\n    shared = []\n    def __new__(cls, owner):\n        return super().__new__(cls)\n    def __init__(self, owner):\n        self.owner = owner\n        self.items = []\n    def add(self, item):\n        self.items.append(item)\n        return self.items\n\na = Cart(&#39;a&#39;)\nb = Cart(&#39;b&#39;)\na.add(&#39;book&#39;)\na.shared.append(&#39;pen&#39;)\nprint(a.items, b.items, b.shared)\nprint(type(Cart.add).__name__, type(a.add).__name__)\nprint(a.add.__self__ is a, a.add.__func__ is Cart.add)\nprint(vars(a))", "note": "__new__ 与 __init__ 的分工"}, {"label": "对照 / 进阶", "code": "from dataclasses import dataclass\n\nclass BadInit:\n    def __init__(self):\n        self.x = 1\n        return self.x\ntry:\n    BadInit()\nexcept TypeError as e:\n    print(type(e).__name__, str(e))\n\nclass SlotPoint:\n    __slots__ = (&#39;x&#39;, &#39;y&#39;)\n    def __init__(self, x, y):\n        self.x = x\n        self.y = y\np = SlotPoint(1, 2)\nprint(p.x, p.y, hasattr(p, &#39;__dict__&#39;))\ntry:\n    p.z = 3\nexcept AttributeError as e:\n    print(type(e).__name__, str(e))\n\n@dataclass\nclass Point:\n    x: int\n    y: int = 0\nq = Point(3)\nprint(q, q.x, q.y)", "note": "实例字典、类属性与方法绑定"}]' title='两种写法对照' note='差异集中在 类对象与实例对象；先看输出，再找背后的规则。' />

<Callout type="tip" title='核心心智模型' text='真正创建实例的是 `__new__(cls, *args, **kwargs)`，它被 Python 自动当作静态方法处理，返回一个实例（通常由 `object.__new__(cls)` 分配内存）；`__init__(self, ...)` 只负责初始化这个已存在的实例，必须返回 `None`…' />


## 对象创建与属性赋值错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 所有状态放类属性，多个实例共享同一份可变数据 | 可变类属性存在类 __dict__，实例通过查找链看到的是同一个 list / dict | 把每个实例独立的状态放进 __init__ 里的 self.x = []；类属性只放不可变常量 |
| 在 __init__ 里 return 一个值，抛 TypeError: __init__() should return None, not '...' | __init__ 的返回值会被 type.__call__ 丢弃，非 None 即报错 | __init__ 只做赋值、不写 return 值；需要计算后的对象用 __new__ 或工厂方法 |
| 给 __slots__ 类的实例赋未声明属性报 AttributeError | slots 去掉了实例 __dict__，可赋名字被限制在声明集合内 | 把字段加进 __slots__，或去掉 slots；需要动态属性时在 slots 里显式加 '__dict__' |

<Callout type="warn" title='本讲最容易踩的坑' text='所有状态放类属性，多个实例共享同一份可变数据：可变类属性存在类 __dict__，实例通过查找链看到的是同一个 list / dict' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：所有状态放类属性，多个实例共享同一份可变数据", "body": "可变类属性存在类 __dict__，实例通过查找链看到的是同一个 list / dict", "tip": "把每个实例独立的状态放进 __init__ 里的 self.x = []；类属性只放不可变常量"}, {"title": "第 2 步：在 __init__ 里 return 一个…", "body": "__init__ 的返回值会被 type.__call__ 丢弃，非 None 即报错", "tip": "__init__ 只做赋值、不写 return 值；需要计算后的对象用 __new__ 或工厂方法"}, {"title": "第 3 步：给 __slots__ 类的实例赋未声明属性…", "body": "slots 去掉了实例 __dict__，可赋名字被限制在声明集合内", "tip": "把字段加进 __slots__，或去掉 slots；需要动态属性时在 slots 里显式加 &#39;__dict__&#39;"}]' />

<CheckList id='P038a' title='学完你应当能' :items='["能讲清 __new__ 与 __init__ 的分工", "能讲清 实例字典、类属性与方法绑定", "能讲清 __slots__、dataclass 与属性边界", "能在工程里处理 self 的本质"]' />


## 动手定义值对象并自测

<Exercise title='基础：对比类属性共享与实例独立' task='定义 Bad（items 是类属性）与 Good（items 在 __init__ 里），各建两个实例，给第一个 append 后打印两者的列表与身份比较。' solution='class Bad:\n    items = []\n    def __init__(self):\n        pass\n\nclass Good:\n    def __init__(self):\n        self.items = []\n\na, b = Bad(), Bad()\na.items.append(1)\nprint(a.items, b.items, a.items is b.items)\ng1, g2 = Good(), Good()\ng1.items.append(1)\nprint(g1.items, g2.items, g1.items is g2.items)' explain='Bad 的两个实例通过类字典共享同一个 list（is 为真）；Good 每个实例在 __init__ 里新建列表，互不干扰。' />

<Exercise title='进阶：验证 __new__ 先于 __init__ 与方法绑定' task='定义含 __new__ 打印、__init__ 赋值、get 方法的类，打印实例字典、bound method 的 __self__，以及用类上取到的函数显式传实例调用。' solution='class C:\n    def __new__(cls, x):\n        print(&#39;new&#39;, x)\n        return super().__new__(cls)\n    def __init__(self, x):\n        self.x = x\n    def get(self):\n        return self.x\n\nc = C(5)\nprint(c.get(), C.get(c), c.get.__self__ is c)\nprint(vars(c))' explain='__new__ 先执行分配、再进 __init__ 初始化；obj.get 是 bound method，C.get 是原函数需显式传 self；vars(c) 只有实例属性。' />

<Quiz no='038-1' q='真正创建实例、分配内存的是哪个方法？' :options='["__new__", "__init__", "__call__", "self"]' answer="0" explain='__new__(cls) 由 type.__call__ 首先调用并返回一个实例，__init__ 只是随后初始化它，且必须返回 None。' />

<Quiz no='038-2' q='obj.m() 调用时 self 是从哪来的？' :options='["function 的 __get__ 生成 bound method 并绑定实例", "调用方手动传入", "解释器全局注入", "__init__ 的返回值"]' answer="0" explain='类里的 function 是非数据描述符，obj.m 经 __get__(obj, type) 生成 MethodType，把 obj 固定为第一个参数。' />

<Quiz no='038-3' q='关于 __slots__，下面哪项准确？' :options='["去掉实例 __dict__，给未声明属性赋值抛 AttributeError", "让实例可以存任意属性", "自动生成 __init__ 方法", "只影响类属性不影响实例"]' answer="0" explain='__slots__ 用固定槽替换实例字典，省内存且限制属性名；代价是没有 __dict__，cached_property 等机制不可用。' />

<Predict no='038-4' q='class C: shared = []；a = C(); b = C(); a.shared.append(1); print(b.shared) 输出什么？' :options='["[1]", "[]", "抛 AttributeError"]' answer='0' output='[1]' explain='shared 是类属性，a 与 b 通过查找链看到的是同一个列表；a 的 append 改动的是这份共享对象，所以 b.shared 也是 [1]。' />

<FillBlank no='038-5' tpl='___ __new__(cls, owner):' :answers='["def"]' hint='回想本讲关于 类对象与实例对象 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 __new__ 与 __init__ 的分工 的落点。' />

<KnowledgeCard :points='["真正创建实例的是 __new__(cls)，__init__(self) 只初始化且必须返回 None（否则 TypeError: __init__() should return None, not &#39;...&#39;）", "C() 链路：type.__call__ → __new__ →（返回本类实例才）__init__ → 返回实例；__new__ 返回别类实例则不调 __init__", "实例属性存 obj.__dict__，类属性存 Class.__dict__（mappingproxy）；查找先实例后类，实例同名键遮蔽类属性", "可变类属性被所有实例共享，独立状态要放 __init__ 里的 self.x = []", "类里的 function 是非数据描述符，obj.m 经 __get__ 生成 bound method（__self__=实例、__func__=原函数）；C.m 返回原函数", "__slots__ 去掉实例 __dict__ 省内存、限制属性名；dataclass（3.7+）按注解生成 __init__/__repr__/__eq__，slots=True（3.10+）自动生成槽"]' :pitfalls='["所有状态放类属性，多个实例共享同一份可变数据", "在 __init__ 里 return 一个值，抛 TypeError: __init__() should return None, not &#39;...&#39;", "给 __slots__ 类的实例赋未声明属性报 AttributeError", "把所有状态都放类属性，多个实例会共享同一份可变数据，改一个实例影响全部"]' summary='真正创建实例的是 __new__，__init__ 只负责初始化；方法之所以能自动收到 self，是因为函数实现了描述符协议' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 真正创建实例的是 __new__(cls)，__init__(self) 只初始化且必须返回 None（否则 TypeError: __init__() should return None, not '...'） | 建立直觉 |
| C() 链路：type.__call__ → __new__ →（返回本类实例才）__init__ → 返回实例；__new__ 返回别类实例则不调 __init__ | 跑通示例 |
| 实例属性存 obj.__dict__，类属性存 Class.__dict__（mappingproxy）；查找先实例后类，实例同名键遮蔽类属性 | 深入边界 |
| 可变类属性被所有实例共享，独立状态要放 __init__ 里的 self.x = [] | 工程落地 |
| 类里的 function 是非数据描述符，obj.m 经 __get__ 生成 bound method（__self__=实例、__func__=原函数）；C.m 返回原函数 | 随堂检测 |
| __slots__ 去掉实例 __dict__ 省内存、限制属性名；dataclass（3.7+）按注解生成 __init__/__repr__/__eq__，slots=True（3.10+）自动生成槽 | 复盘 |

1. 真正创建实例的是 __new__(cls)，__init__(self) 只初始化且必须返回 None（否则 TypeError: __init__() should return None, not '...'）

2. C() 链路：type.__call__ → __new__ →（返回本类实例才）__init__ → 返回实例；__new__ 返回别类实例则不调 __init__

3. 实例属性存 obj.__dict__，类属性存 Class.__dict__（mappingproxy）；查找先实例后类，实例同名键遮蔽类属性

[下一讲：属性查找、MRO 与 super](/oop/mro)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/038-class-basics.py`

```bash
python3 examples/lessons/038-class-basics.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/038-class-basics.py) · [全部示例代码索引](/examples/)
