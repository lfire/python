---
title: 第 041 讲 · 特殊方法：repr、比较、算术与容器协议
description: 让自定义类型像内置类型一样自然
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='35 分钟' goal='让自定义类型像内置类型一样自然' prereq='第 040 讲 · 访问控制、property 与描述符协议' />

# 第 041 讲 · 特殊方法：repr、比较、算术与容器协议

上一讲把属性访问交给描述符与 `property`，类已能按意愿响应取值赋值。再往前是个朴素问题：为什么 `len(obj)`、`a + b` 对内置类型天生成立，自己写的类却常常不理？答案是一组特殊方法的协议，实现一个常牵动另一处行为。

一份订单汇总脚本把金额对象当字典键，日志里却打印成面向开发者的串。本讲先从 `repr` 与 `str` 走起，再看 `__eq__` 与哈希联动、`len` / `bool` / `contains` 的回退次序，最后落到算术反向方法。需要第 40 讲的描述符与阶段二的哈希要求；学完你能解释「加了比较方法为何当不了键」，也能写出可哈希的值对象。


## 一个把 Money 当 dict 键却报 unhashable 的工单

一个订单聚合脚本把 `Money(amount, currency)` 当作 `dict` 的键做汇总，第一次上线就抛 `TypeError: unhas…`。

```text
TypeError: unhashable type: 'Money'
```

团队为了让两笔金额能比较相等，给类加了 `__eq__`，却不知道这一步会让类自动失去哈希能力。

有人补救时写 `__hash__ = object.__hash__`，结果金额相等的两笔订单因为 `id` 不同得到不同哈希，聚合结果直接错乱；

还有人只定义了 `__repr__`，日志里看着正常，运营看到的报表却是给开发者看的串，因为忘了 `__str__`。更隐蔽的一处：给容器写了 `__len__` 之后，`if obj` 的真假值也跟着变了，某个空对象突然被当成 `False` 跳过。

这些都不是零散语法，而是数据模型协议的一整套联动：定义一个方法，别的行为会跟着被改。本讲把 `repr` / `str` 回退、`eq` / `hash` 联动、`len` / `bool` / `contains` 优先级与算术反射调用逐条拆开，给出每一处的修复写法和失效信号。

<Callout type="warn" title='先看一个真实会出错的写法' text='定义 __eq__ 后实例无法作为 dict 键或 set 元素：type.__new__ 把未显式定义 __hash__ 的类设为 __hash__ = None，hash() 抛 TypeError: unhashable type' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 040 讲 · 访问控制、property 与描述符协议 |
| 难度 / 建议时长 | ★★★☆☆ · 35 分钟 |
| 本讲新增 | __repr__ 与 __str__、__eq__ 与 __hash__ 联动、functools.total_ordering |
| 一句话目标 | 让自定义类型像内置类型一样自然 |
| 为下一讲铺垫 | 上下文管理器与 with 协议 |

<CheckList id='P041a' title='学完你应当能' :items='["能讲清 repr 与 str 是两条独立输出路径，容器强制走 repr", "能讲清 定义 __eq__ 会让类失去哈希，除非显式补 __hash__", "能讲清 容器与数值协议：len、bool、contains 的回退链与反向运算", "能在工程里处理 __bool__"]' />


## 特殊方法怎样挂进 PyTypeObject 的槽位

CPython 把每个特殊方法登记进 `PyTypeObject` 的槽（slot）：`__eq__` / `__lt__` 等填入 `tp_richcompare`，`__hash__` 填 `tp_hash`，`__len__` 填 `sq_length`，`__add__` / `__radd__` 填 `nb_add` 数值子结构。

类创建结束时，`PyType_Ready` 依据 `slotdefs` 表把类字典里的 Python 函数包装成 `slot_tp_richcompare` 之类的 C 分派器，运算符最终落到 `PyObject_RichCompare`、`PyNumber_Add` 这些 C API。

`type.__new__` 里有一段明确的修补：当类体出现 `__eq__` 而没有 `__hash__` 时，把 `tp_hash` 对应的 `__hash__` 设成 `None`（底层是 `PyObject_HashNotImplemented`），`hash()` 因而抛 `TypeError`。

`NotImplemented` 是全局单例，`PyNumber_Add` 见到它才转去查另一侧的 `nb_add`；这正是「返回 `NotImplemented` 而非 `False`」能生效的原因。

`__bool__` 走 `nb_bool`，`__len__` 走 `sq_length`，`PyObject_IsTrue` 先试 `nb_bool` 再试 `sq_length`，这条顺序决定了优先链。

理解槽表与单例，比背方法名更能解释为什么改一个方法会牵动一整组行为。

<Callout type="tip" title='核心心智模型' text='`__repr__` 面向开发者，目标是无歧义、最好能被 `eval` 复原；`__str__` 面向终端用户，目标是可读。`print(obj)`、`str(obj)`、`f&#39;{obj}&#39;` 与 `format` 的空转换走 `__str__`；`repr(obj)`、交互式回显、`logging' />


### slotdefs、PyType_Ready 与 NotImplemented 单例

<Term word='__repr__ 与 __str__' text='`__repr__` 面向开发者，目标是无歧义、最好能被 `eval` 复原；`__str__` 面向终端用户，目标是可读。`print(obj)`、`str(obj)`、`f&#39;{obj}&#39;` 与 `format` 的空转换走 `__str__`；`repr(obj)`、交互式回显、`logging` 的 `%r`、`' />

<Term word='__eq__ 与 __hash__ 联动' text='CPython 在 `type.__new__` 里检查：若类体定义了 `__eq__` 却没有定义 `__hash__`，就把类的 `__hash__` 设成 `None`。于是 `hash(obj)` 抛 `TypeError: unhashable type: &#39;X&#39;`，`obj` 也进不了 `set`、当不了 ' />

<ConceptDiagram type='flow4' title='第 041 讲 · repr 与 str 是两条独立输出路径，容器强制走 repr' labels='repr 与 str 是两条独立输出路径，容|定义 __eq__ 会让类失去哈希，除非显式|容器与数值协议：len、bool、conta' caption='让自定义类型像内置类型一样自然' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## repr 与 str 是两条独立输出路径，容器强制走 repr

`__repr__` 面向开发者，目标是无歧义、最好能被 `eval` 复原；`__str__` 面向终端用户，目标是可读。`print(obj)`、`str(obj)`、`f'{obj}'` 与 `format` 的空转换走 `__str__`；

`repr(obj)`、交互式回显、`logging` 的 `%r`、`f'{obj!r}'` 走 `__repr__`。关键回退规则：`object.__str__` 默认调用 `__repr__`，所以只实现 `__repr__` 就能同时覆盖两条路径，这是最小实现；

反过来只实现 `__str__` 时，`repr(obj)` 会用 `object.__repr__` 给出带类名与内存地址的默认串，地址每次运行都变，不能写进快照测试。

列表、元组、字典、集合打印元素时一律用 `repr`，因为容器需要无歧义表示而不是友好文案——`print([a])` 看到的是 `repr` 结果，哪怕 `a` 定义了漂亮的 `__str__`。`f'{obj!s}'` 与 `f'{obj!r}'` 分别强制两条路径。

`datetime.date`、`decimal.Decimal` 等内置类型的 `__str__` 与 `__repr__` 明显不同，可直接对照。

判断自己写对没有，用一个最小类同时打印 `str`、`repr` 与装进 `list` 的结果即可。

```python
class Vec:
    def __init__(self, x, y):
        self.x, self.y = x, y
    def __repr__(self):
        return 'Vec(' + repr(self.x) + ', ' + repr(self.y) + ')'
    def __eq__(self, other):
        if not isinstance(other, Vec):
            return NotImplemented
        return (self.x, self.y) == (other.x, other.y)
    def __len__(self):
        return 2
    def __bool__(self):
        return bool(self.x or self.y)
    def __contains__(self, v):
        return v in (self.x, self.y)

a = Vec(1, 2)
print(repr(a), [a])
print('eq', a == Vec(1, 2), 'ne', a != Vec(1, 3))
print('hash', Vec.__hash__)
print('bool', bool(a), bool(Vec(0, 0)), 'len', len(a))
print('contains', 2 in a, 9 in a)
```

<OutputBox title='主示例运行结果' output='Vec(1, 2) [Vec(1, 2)]\neq True ne True\nhash None\nbool True False len 2\ncontains True False' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Vec:\n    def __init__(self, x, y):\n        self.x, self.y = x, y\n    def __repr__(self):\n        return &#39;Vec(&#39; + repr(self.x) + &#39;, &#39; + repr(self.y) + &#39;)&#39;\n    def __eq__(self, other):\n        if not isinstance(other, Vec):\n            return NotImplemented\n        return (self.x, self.y) == (other.x, other.y)\n    def __len__(self):\n        return 2\n    def __bool__(self):\n        return bool(self.x or self.y)\n    def __contains__(self, v):\n        return v in (self.x, self.y)\n\na = Vec(1, 2)\nprint(repr(a), [a])\nprint(&#39;eq&#39;, a == Vec(1, 2), &#39;ne&#39;, a != Vec(1, 3))\nprint(&#39;hash&#39;, Vec.__hash__)\nprint(&#39;bool&#39;, bool(a), bool(Vec(0, 0)), &#39;len&#39;, len(a))\nprint(&#39;contains&#39;, 2 in a, 9 in a)' :notes='["定义值类 Vec，集中演示六条数据模型协议", "构造时把两个坐标绑定到实例", "元组解包一次赋值，注意实例此时带 __dict__", "__repr__ 面向开发者，容器打印元素时强制走它", "用 repr 拼字段，保证输出无歧义且可被 eval 复原", "__eq__ 定义后 type.__new__ 会把 __hash__ 置 None", "不认识的类型不能返回 False", "返回 NotImplemented，让解释器去试对方的反射方法", "只有同类才按坐标元组判等", "__len__ 参与 len() 与 bool() 的回退链", "必须返回非负 Py_ssize_t，这里固定为 2", "__bool__ 优先级高于 __len__，决定 if obj 的真假", "返回严格 bool：两个坐标全 0 时为假", "__contains__ 支撑 in 运算，优先于迭代回退", "把成员判断委托给坐标元组", "空行分隔类定义与验证代码", "构造实例 a", "repr(a) 与装进 list 的打印都走 __repr__", "__ne__ 由 object 对 __eq__ 取反，无需手写", "类属性 __hash__ 已被设为 None，实例不可哈希", "bool 走 __bool__，len 走 __len__"]' title='第 041 讲 · 特殊方法：repr、比较、算术与容器协议' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 定义 __eq__ 会让类失去哈希，除非显式补 __hash__

CPython 在 `type.__new__` 里检查：若类体定义了 `__eq__` 却没有定义 `__hash__`，就把类的 `__hash__` 设成 `None`。

于是 `hash(obj)` 抛 `TypeError: unhas…`，`obj` 也进不了 `set`、当不了 `dict` 键。

```text
TypeError: unhashable type: 'X'
```

这样设计是为了守住哈希契约——相等的对象必须有相等的哈希值；

默认的 `object.__hash__` 基于身份 `id`，两个 `__eq__` 判等的不同实例哈希必然不同，留着它只会制造「相等却查不到」的诡异 bug。

修复分两种意图：可变对象明确写 `__hash__ = None` 表明它就是不可哈希；

值对象应冻结（`frozen dataclass`、`NamedTuple`）并对全部参与 `__eq__` 的字段求哈希，例如 `hash((self.x, self.y))`。

哈希值必须是 `int`，且在对象生命周期内不变，所以参与哈希的字段不能事后被改。另一个易错点：`__eq__` 遇到不认识的类型应返回 `NotImplemented` 这个单例，而不是返回 `False` 或抛异常；返回 `NotImplemented` 后解释器会去试对方的反射方法，都失败才退化为 `is` 身份比较。

Python 3 里 `__ne__` 由 `object.__ne__` 对 `__eq__` 取反，通常不用手写。`str` 的哈希会被缓存进对象，`tuple` 的哈希每次重新计算，这也是值对象优先用元组打包字段的原因之一。

```python
from functools import total_ordering

@total_ordering
class Score:
    def __init__(self, v):
        self.v = v
    def __eq__(self, other):
        return isinstance(other, Score) and self.v == other.v
    def __lt__(self, other):
        return isinstance(other, Score) and self.v < other.v
    def __radd__(self, other):
        return Score(self.v + other)
    def __repr__(self):
        return 'Score(' + repr(self.v) + ')'

print(Score(3) < Score(5), Score(3) <= Score(3))
print('ge', Score(5) >= Score(4))
print('radd', repr(10 + Score(1)))
```

<OutputBox title='对照写法：先自己猜，再点开' output='True True\nge True\nradd Score(11)' guess="true" />


### __eq__ 与 __hash__ 组合结果

**__eq__ 与 __hash__ 组合结果（CPython type.__new__ 行为）**

| 类体定义 | __hash__ 结果 | hash(obj) | 能否进 set / 做 dict 键 |
| --- | --- | --- | --- |
| 都不定义 | 继承 object.__hash__ | 按 id 计算 | 能 |
| 只定义 __eq__ | 被设为 None | 抛 TypeError: unhashable type | 不能 |
| 定义 __eq__ 且写 __hash__ = None | None | 抛 TypeError | 不能，意图显式 |
| 定义 __eq__ 且显式 __hash__ | 保留自定义函数 | 按自定义逻辑 | 能，需满足相等者哈希相等 |
| frozen=True 的 dataclass(eq=True) | 自动生成，按字段元组 | 按字段计算 | 能 |


## 容器与数值协议：len、bool、contains 的回退链与反向运算

`__len__` 必须返回非负整数，CPython 用 `Py_ssize_t` 接收：返回负数抛 `ValueError:`，超过 `sys.maxsize` 抛 `OverflowError: c…`。

```python
ValueError: __len__() should return >= 0
OverflowError: cannot fit 'int' into an index-sized integer
```

`bool(obj)` 与 `if obj` 先找 `__bool__`，它必须返回严格的 `bool`，返回 `int` 会抛 `TypeError: __boo…`；

```python
TypeError: __bool__ should return bool, returned int
```

没有 `__bool__` 才回退 `__len__`，长度 0 为假。`in` 先找 `__contains__`，没有则回退 `__iter__` 迭代，再没有回退旧的 `__getitem__` 下标协议。

算术是一组对称协议：`a + b` 先调 `a.__add__(b)`，若返回 `NotImplemented` 再调 `b.__radd__(a)`；当右操作数是左操作数类型的子类且重写了反射方法时，反射方法反而优先，避免子类被基类的 `__add__` 抢走。

`a += b` 先试 `__iadd__` 做原地修改，未定义才回退 `__add__` 再重新绑定，因此不可变类型的 `+=` 会生成新对象。

`functools.total_ordering` 要求类至少定义 `__eq__` 与 `__lt__` / `__le__` / `__gt__` / `__ge__` 之一，装饰器补齐其余四个；

它生成的是 Python 层组合方法，比逐个手写多一层调用，且强依赖 `__eq__` 已定义，适合字段少、比较不热的场景。

```python
import inspect

class EqOnly:
    def __eq__(self, other):
        return True
class WithHash:
    def __eq__(self, other):
        return isinstance(other, WithHash)
    def __hash__(self):
        return hash((1, 2))

print('static hash:', inspect.getattr_static(EqOnly, '__hash__', 'missing'))
try:
    hash(EqOnly())
except TypeError as e:
    print('TypeError:', str(e)[:36])
print('hash equal:', WithHash().__hash__() == WithHash().__hash__())
print('ne uses eq:', EqOnly() != object())
```

<OutputBox title='原理验证' output='static hash: None\nTypeError: unhashable type: &#39;EqOnly&#39;\nhash equal: True\nne uses eq: False' />

<CodeTabs :tabs='[{"label": "主示例", "code": "class Vec:\n    def __init__(self, x, y):\n        self.x, self.y = x, y\n    def __repr__(self):\n        return &#39;Vec(&#39; + repr(self.x) + &#39;, &#39; + repr(self.y) + &#39;)&#39;\n    def __eq__(self, other):\n        if not isinstance(other, Vec):\n            return NotImplemented\n        return (self.x, self.y) == (other.x, other.y)\n    def __len__(self):\n        return 2\n    def __bool__(self):\n        return bool(self.x or self.y)\n    def __contains__(self, v):\n        return v in (self.x, self.y)\n\na = Vec(1, 2)\nprint(repr(a), [a])\nprint(&#39;eq&#39;, a == Vec(1, 2), &#39;ne&#39;, a != Vec(1, 3))\nprint(&#39;hash&#39;, Vec.__hash__)\nprint(&#39;bool&#39;, bool(a), bool(Vec(0, 0)), &#39;len&#39;, len(a))\nprint(&#39;contains&#39;, 2 in a, 9 in a)", "note": "repr 与 str 是两条独立输出路径，容器强制走 repr"}, {"label": "对照 / 进阶", "code": "from functools import total_ordering\n\n@total_ordering\nclass Score:\n    def __init__(self, v):\n        self.v = v\n    def __eq__(self, other):\n        return isinstance(other, Score) and self.v == other.v\n    def __lt__(self, other):\n        return isinstance(other, Score) and self.v &lt; other.v\n    def __radd__(self, other):\n        return Score(self.v + other)\n    def __repr__(self):\n        return &#39;Score(&#39; + repr(self.v) + &#39;)&#39;\n\nprint(Score(3) &lt; Score(5), Score(3) &lt;= Score(3))\nprint(&#39;ge&#39;, Score(5) &gt;= Score(4))\nprint(&#39;radd&#39;, repr(10 + Score(1)))", "note": "定义 __eq__ 会让类失去哈希，除非显式补 __hash__"}]' title='两种写法切换看' />


## 特殊方法与触发入口、回退链对照

**特殊方法与触发入口、回退链对照**

| 特殊方法 | 触发入口 | 缺省或回退行为 | 返回值约束 |
| --- | --- | --- | --- |
| __repr__ | repr(obj)、容器元素打印、!r | object.__repr__ 给出类名加地址 | 必须返回 str |
| __str__ | print/str/f-string 空转换、!s | object.__str__ 回退调用 __repr__ | 必须返回 str |
| __eq__ | ==、!= 经 object.__ne__ 取反 | 默认 object 的身份比较 | 应返回 bool 或 NotImplemented |
| __len__ | len()、bool() 回退 | 无则不获取长度 | 非负 Py_ssize_t |
| __bool__ | if/while/and/or/not | 无则回退 __len__，再无恒为 True | 必须返回 bool |
| __contains__ | in / not in | 无则回退 __iter__ 再回退 __getitem__ | 任意对象，按真值判定 |

**算术协议调用顺序与常见失败信号**

| 表达式 | 首选方法 | 次选 / 回退 | 典型异常 |
| --- | --- | --- | --- |
| a + b | a.__add__(b) | 返回 NotImplemented 后 b.__radd__(a) | 两者都没有时 TypeError: unsupported operand |
| b 为 a 的子类且重写 __radd__ | b.__radd__(a) | a.__add__(b) | 顺序反转不会报错，需主动验证 |
| a += b | a.__iadd__(b) | 未定义则 __add__ 再重新绑定 | 不可变类型会悄悄换对象 |
| a < b | a.__lt__(b) | b.__gt__(a) | total_ordering 缺 __eq__ 时抛 ValueError |
| len(a) | a.__len__() | 无回退 | 负数 ValueError，超 sys.maxsize OverflowError |


## 值对象 Money 用于 dict 聚合与 set 去重

结算服务要把上千笔流水按币种汇总，还要对重复的金额对象去重。若用普通类，`__eq__` 一加就失去哈希，既当不了 `dict` 键也进不了 `set`；若用可变对象做键，事后改了字段会让哈希与相等性一起失效，账目再也查不出来。

正确做法是把 `Money` 冻结成不可变值对象：`frozen dataclass` 在 `eq=True` 时自动生成按字段元组求值的 `__hash__`，于是相等对象哈希相等，聚合与去重都成立；

`__add__` 里先校验币种一致再返回新实例，避免隐式跨币种相加。

下面用标准库 `dataclasses` 完整跑通：三笔 `CNY` 与一笔 `USD` 汇总、用 `set` 去重、并验证冻结后赋值会抛 `FrozenInstanceError`（它是 `AttributeError` 的子类）。

真实项目还应把金额换成 `Decimal` 而不是 `int`，本例为聚焦协议用整数演示。

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Money:
    amount: int
    currency: str
    def __add__(self, other):
        if self.currency != other.currency:
            raise ValueError('currency mismatch')
        return Money(self.amount + other.amount, self.currency)

ledger = {}
def record(m):
    base = ledger.get(m.currency, Money(0, m.currency))
    ledger[m.currency] = base + m

for m in [Money(100, 'CNY'), Money(250, 'CNY'), Money(30, 'USD'), Money(70, 'CNY')]:
    record(m)
print({k: v.amount for k, v in ledger.items()})
print('dedup', len({Money(1, 'CNY'), Money(1, 'CNY'), Money(2, 'CNY')}))
try:
    Money(1, 'CNY').amount = 9
except AttributeError as e:
    print(type(e).__name__)
```

<Callout type="idea" title='落地提示' text='值对象应设为 frozen dataclass 并哈希全部关键字段；可变对象明确设 __hash__ = None 表明意图' />

<CheckList id='P041b' title='上线前自检' :items='["能复现并解释「定义 __eq__ 后实例无法作为 dict 键或 set 」", "能复现并解释「__eq__ 里对不认识的类型直接 return False」", "能复现并解释「__len__ 返回负数，或 __bool__ 返回整数 0」", "能用一条命令验证 __repr__ 与 __str__", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from collections.abc import Sized; print(isinstance([1], Sized))"
```

把输入换成你自己的数据，观察结果是否仍符合 `__repr__` 与 `__str__` 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 定义 __eq__ 后无法进 set、返回 False 的错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 定义 __eq__ 后实例无法作为 dict 键或 set 元素 | type.__new__ 把未显式定义 __hash__ 的类设为 __hash__ = None，hash() 抛 TypeError: unhashable type | 值对象用 frozen dataclass 或 NamedTuple，并写 __hash__ = hash((self.x, self.y))；可变对象显式写 __hash__ = None 表明意图 |
| __eq__ 里对不认识的类型直接 return False 或抛异常 | 返回 False 会阻断解释器尝试对方反射方法，破坏对称性，也让本可相等的比较永久失败 | 对非本类类型返回 NotImplemented，让解释器回退到对方方法，最终再退化为 is 身份判断 |
| __len__ 返回负数，或 __bool__ 返回整数 0/1 | __len__ 受 Py_ssize_t 约束，负数抛 ValueError: __len__() should return >= 0；__bool__ 必须返回严格 bool，返回 int 抛 TypeError: __bool__ should return bool | __len__ 写 return len(self._items)；__bool__ 写 return bool(self.x)，或直接省略让它回退 __len__ |

<Callout type="warn" title='本讲最容易踩的坑' text='定义 __eq__ 后实例无法作为 dict 键或 set 元素：type.__new__ 把未显式定义 __hash__ 的类设为 __hash__ = None，hash() 抛 TypeError: unhashable type' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：定义 __eq__ 后实例无法作为 dict", "body": "type.__new__ 把未显式定义 __hash__ 的类设为 __hash__ = None，hash() 抛 TypeError: unhashable type", "tip": "值对象用 frozen dataclass 或 NamedTuple，并写 __hash__ = hash((self.x, self.y))；可变对象显式写 __hash__ = None 表明意图"}, {"title": "第 2 步：__eq__ 里对不认识的类型直接 retu", "body": "返回 False 会阻断解释器尝试对方反射方法，破坏对称性，也让本可相等的比较永久失败", "tip": "对非本类类型返回 NotImplemented，让解释器回退到对方方法，最终再退化为 is 身份判断"}, {"title": "第 3 步：__len__ 返回负数，或 __bool_", "body": "__len__ 受 Py_ssize_t 约束，负数抛 ValueError: __len__() should return &gt;= 0；__bool__ 必须返回严格 bool，返回 int 抛 TypeError: __bool__ should return bool", "tip": "__len__ 写 return len(self._items)；__bool__ 写 return bool(self.x)，或直接省略让它回退 __len__"}]' />


## 动手、自测与速记

<Exercise title='基础：一次看清 repr、len、bool、contains 的回退' task='定义类 Bag，保存一个 items 列表，实现 __repr__、__len__、__contains__，不实现 __bool__；分别打印 repr(b)、[b]、len(b)、bool(b)、某元素 in b，并解释 bool(b) 为什么由 __len__ 决定。' solution='class Bag:\n    def __init__(self, items):\n        self.items = items\n    def __repr__(self):\n        return &#39;Bag(&#39; + repr(self.items) + &#39;)&#39;\n    def __len__(self):\n        return len(self.items)\n    def __contains__(self, v):\n        return v in self.items\nb = Bag([1, 2])\nprint(repr(b), [b], len(b), bool(b), 2 in b, 9 in b)\nBag([]).__len__()' explain='未定义 __bool__ 时 PyObject_IsTrue 回退到 sq_length，即 __len__；空 Bag 为假。容器打印元素走 __repr__，不是 __str__。in 直接命中 __contains__。' />

<Exercise title='进阶：让值对象同时可比较、可哈希、支持反射加法' task='用 functools.total_ordering 与显式 __hash__ 实现一个 Score，验证它能放进 set、能用 &lt; 与 &gt;= 比较、且 10 + Score(1) 触发 __radd__ 得到新对象；说明为何 __hash__ 只对 eq 用到的字段求值。' solution='from functools import total_ordering\n@total_ordering\nclass Score:\n    def __init__(self, v):\n        self.v = v\n    def __eq__(self, o):\n        return isinstance(o, Score) and self.v == o.v\n    def __lt__(self, o):\n        return isinstance(o, Score) and self.v &lt; o.v\n    def __hash__(self):\n        return hash(self.v)\n    def __radd__(self, o):\n        return Score(self.v + o)\ns = {Score(1), Score(1), Score(2)}\nprint(len(s), Score(1) &lt; Score(2), Score(3) &gt;= Score(3))\nprint((10 + Score(1)).v)' explain='total_ordering 用 __eq__ 与 __lt__ 补齐其余比较；显式 __hash__ 恢复可哈希，且只与 __eq__ 用到的 v 字段一致，保证相等者哈希相等。int.__add__ 对 Score 返回 NotImplemented，转调 __radd__。' />

<Quiz no='041-1' q='类里定义了 __eq__ 却没定义 __hash__，下列哪项准确描述了结果？' :options='["type.__new__ 把 __hash__ 设为 None，实例 hash() 抛 TypeError 且无法进 set", "实例继承 object.__hash__，按 id 哈希，可以进 set", "Python 自动按所有字段生成一个 __hash__", "只有 eq=True 的 dataclass 才会这样，普通类不会"]' answer="0" explain='CPython 在 type.__new__ 里检查：定义 __eq__ 而未定义 __hash__ 时把 __hash__ 设成 None，任何普通类都如此。这样避免相等对象因 id 不同而哈希不同、违反哈希契约。' />

<Quiz no='041-2' q='__eq__ 遇到不认识的类型时，正确做法是？' :options='["返回 NotImplemented，让解释器尝试对方的反射方法", "返回 False，明确表示不相等", "抛出 TypeError 阻止比较", "返回 None 交给上层处理"]' answer="0" explain='NotImplemented 是单例，PyNumber/PyObject_RichCompare 见到它才转查另一侧方法；返回 False 会直接结束比较，破坏对称性；返回 None 在布尔上下文会被当真值，语义全错。' />

<Quiz no='041-3' q='关于 bool(obj) 的求值顺序，正确的是？' :options='["先找 __bool__，没有才回退 __len__，长度 0 为假", "先找 __len__，再找 __bool__", "只要定义了 __len__，__bool__ 永远被忽略", "bool(obj) 只取决于对象是否为空字典"]' answer="0" explain='PyObject_IsTrue 先试 nb_bool（__bool__），没有实现才试 sq_length（__len__）；__bool__ 必须返回严格 bool，否则抛 TypeError: __bool__ should return bool。' />

<Predict no='041-4' q='定义 __eq__ 且未定义 __hash__ 的类，下面代码输出什么？' :options='["hash None / TypeError", "hash 一个整数 / 正常运行", "hash None / 正常运行"]' answer='0' output='hash None\nTypeError: unhashable type' explain='类属性 __hash__ 被 type.__new__ 置为 None，打印得 None；对它调用 hash() 会抛 TypeError: unhashable type。这是定义 __eq__ 的联动后果，不是哈希函数写错了。' />

<FillBlank no='041-5' tpl='___ __init__(self, x, y):' :answers='["def"]' hint='回想本讲关于 __repr__ 与 __str__ 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 repr 与 str 是两条独立输出路径，容器强制走 repr 的落点。' />

<KnowledgeCard :points='["只实现 __repr__ 即可覆盖 print 与 repr 两条路径；容器打印元素强制用 repr", "定义 __eq__ 而未定义 __hash__ 时，CPython 把 __hash__ 置 None，实例不可哈希", "值对象冻结并对全部 eq 字段求哈希；可变对象显式写 __hash__ = None", "__eq__ 遇到不认识的类型返回 NotImplemented，不是 False；Py3 的 __ne__ 自动对 __eq__ 取反", "bool(obj) 先找 __bool__ 再回退 __len__；in 先找 __contains__ 再回退迭代", "a+b 先 __add__ 后 __radd__；a+=b 先试 __iadd__ 原地修改，未定义才回退 __add__"]' :pitfalls='["定义 __eq__ 后实例无法作为 dict 键或 set 元素", "__eq__ 里对不认识的类型直接 return False 或抛异常", "__len__ 返回负数，或 __bool__ 返回整数 0/1", "定义了 __eq__ 却忘记 __hash__，对象立刻不能进 set 或做 dict 键"]' summary='数据模型方法是一套协议而非语法糖：实现 __len__ 后 len() 与真值测试会一起生效，实现 __eq__ 则会让类自动变成不可哈希' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 只实现 __repr__ 即可覆盖 print 与 repr 两条路径；容器打印元素强制用 repr | 建立直觉 |
| 定义 __eq__ 而未定义 __hash__ 时，CPython 把 __hash__ 置 None，实例不可哈希 | 跑通示例 |
| 值对象冻结并对全部 eq 字段求哈希；可变对象显式写 __hash__ = None | 深入边界 |
| __eq__ 遇到不认识的类型返回 NotImplemented，不是 False；Py3 的 __ne__ 自动对 __eq__ 取反 | 工程落地 |
| bool(obj) 先找 __bool__ 再回退 __len__；in 先找 __contains__ 再回退迭代 | 随堂检测 |
| a+b 先 __add__ 后 __radd__；a+=b 先试 __iadd__ 原地修改，未定义才回退 __add__ | 复盘 |

1. 只实现 __repr__ 即可覆盖 print 与 repr 两条路径；容器打印元素强制用 repr

2. 定义 __eq__ 而未定义 __hash__ 时，CPython 把 __hash__ 置 None，实例不可哈希

3. 值对象冻结并对全部 eq 字段求哈希；可变对象显式写 __hash__ = None

[下一讲：上下文管理器与 with 协议](/oop/context)
