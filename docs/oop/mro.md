---
title: 第 039 讲 · 属性查找、MRO 与 super
description: 能推导多继承下的方法解析顺序
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='35 分钟' goal='能推导多继承下的方法解析顺序' prereq='第 038 讲 · 类与实例：__init__、self 与属性' />

# 第 039 讲 · 属性查找、MRO 与 super

单个类里属性怎么找到已经清楚，一旦继承连成网，同名该听谁的就得有个次序。`MRO` 与 `super` 处理的正是多继承下的先后，把直觉换成能推的链条：菱形继承里几个父类都写了 `super`，共同祖先的初始化却只发生一次；有人改成直接点名父类调用，链子当场断掉，后面某个初始化被跳过。

我们先看 `__mro__` 怎么由 `C3` 线性化排出来；再拆开 `super` 的含义——它不是父类，而是沿 `MRO` 往后找下一站，顺带说清零参数依赖的隐式 `cell`；最后回到属性查找链，把描述符优先级摆进图里。接着类与实例那讲，再多一层继承；学完你能对着一个类把解析顺序推出来。


## 菱形继承里，初始化为什么跑两次

一个菱形继承里 `D(B, C)`，`B` 和 `C` 都继承 `A`，每个 `__init__` 都写 `super().__init__()`，结果 `A.__init__` 只跑了一次，团队里有人以为 `super` 调父类所以该跑两次；

另一个人把某个类改成显式 `A.__init__(self)`，链式调用立刻断掉，`C.__init__` 被整个跳过。

更隐蔽的是零参数 `super()` 为什么能工作——它依赖编译器悄悄塞进来的 `__class__` cell，把方法整体挪到别的类里就会失效。本讲把 `C3` 线性化、`super` 的真实语义、协作式多继承与属性查找链讲清楚，让 `MRO` 变成能自己推导、`super` 变成能解释的东西，而不是背结论。

<Callout type="warn" title='先看一个真实会出错的写法' text='以为 super() 是调用父类，菱形继承里 A.__init__ 应该跑两次：super 沿 MRO 找当前类之后的下一实现，C3 保证 A 在链尾只出现一次' />


## 先建模型：super 不是调用父类

<Callout type="tip" title='核心心智模型' text='每个类都有 `__mro__` 元组，`Class.mro()` 返回等价的列表，`inspect.getmro` 也能取到。`MRO` 由 `C3` 线性化在类创建时（`type.__new__`）算好：约束是子类优先于父类、保持基类声明顺序、并递归合并每个基类自身的 `MRO`，每步选出一个不在' />

<ConceptDiagram type='compare2' title='第 039 讲 · C3 线性化与 __mro__' labels='C3 线性化与 __mro__|super 的真实语义与零参数形式|属性查找链与 __getattribute_' caption='能推导多继承下的方法解析顺序' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 038 讲 · 类与实例：__init__、self 与属性 |
| 难度 / 建议时长 | ★★★☆☆ · 35 分钟 |
| 本讲新增 | __mro__ 与 C3 线性化、super 的真实语义、菱形继承 |
| 一句话目标 | 能推导多继承下的方法解析顺序 |
| 为下一讲铺垫 | 访问控制、property 与描述符协议 |


## C3 线性化与 __mro__

每个类都有 `__mro__` 元组，`Class.mro()` 返回等价的列表，`inspect.getmro` 也能取到。`MRO` 由 `C3` 线性化在类创建时（`type.__new__`）算好：约束是子类优先于父类、保持基类声明顺序、并递归合并每个基类自身的 `MRO`，每步选出一个不在任何候选序列尾部出现的表头类。

菱形 `class A`、`class B(A)`、`class C(A)`、`class D(B, C)` 得到 `(D, B, C, A, object)`，`A` 只出现一次、`object` 恒在末尾。

若基类顺序自相矛盾，例如 `class C(A, B)` 且 `B` 已经继承 `A`，则抛 `TypeError: Canno…`。

```python
TypeError: Cannot create a consistent method resolution order (MRO) for bases A, B
```

`MRO` 同时决定属性查找顺序与 `super` 的下一站；Python 3 所有类默认继承 `object` 并统一用 `C3`，Python 2 的经典类不走这套算法，这是读旧资料时要留意的版本差异。

```python
class A:
    def __init__(self):
        print('A')

class B(A):
    def __init__(self):
        print('B')
        super().__init__()

class C(A):
    def __init__(self):
        print('C')
        super().__init__()

class D(B, C):
    def __init__(self):
        print('D')
        super().__init__()

print([c.__name__ for c in D.__mro__])
d = D()
print(D.__mro__ == (D, B, C, A, object))
```

<OutputBox title='主示例运行结果' output='[&#39;D&#39;, &#39;B&#39;, &#39;C&#39;, &#39;A&#39;, &#39;object&#39;]\nD\nB\nC\nA\nTrue' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class A:\n    def __init__(self):\n        print(&#39;A&#39;)\n\nclass B(A):\n    def __init__(self):\n        print(&#39;B&#39;)\n        super().__init__()\n\nclass C(A):\n    def __init__(self):\n        print(&#39;C&#39;)\n        super().__init__()\n\nclass D(B, C):\n    def __init__(self):\n        print(&#39;D&#39;)\n        super().__init__()\n\nprint([c.__name__ for c in D.__mro__])\nd = D()\nprint(D.__mro__ == (D, B, C, A, object))' :notes='["菱形继承的公共基类 A", "A 的初始化只打印一行标记", "打印 A，用于观察它被调用的次数", "B 继承 A", "B 的初始化", "先打印 B", "用 super() 沿 MRO 找下一个实现", "C 也继承 A", "C 的初始化", "先打印 C", "继续用 super()，不是直接调 A", "D 同时继承 B 与 C", "D 的初始化", "先打印 D", "启动协作链", "打印 C3 线性化后的 MRO", "实例化 D，触发整条 super 链", "确认 MRO 恰为 D B C A object"]' title='第 039 讲 · 属性查找、MRO 与 super' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**C3 线性化规则与结果**

| 规则 / 例子 | 内容 | 可核对细节 |
| --- | --- | --- |
| 核心规则 | 子类优先于父类、保持声明顺序、合并各基类 MRO | 取在所有候选表头都不出现在别的表尾的类 |
| 菱形 D(B, C), B(A), C(A) | D.__mro__ = (D, B, C, A, object) | A 只出现一次，object 恒在末尾 |
| 不一致顺序 | class C(A, B) 且 B(A) | TypeError: Cannot create a consistent method resolution order (MRO) for bases A, B |
| 查看方式 | Class.__mro__ 元组 / Class.mro() / inspect.getmro | 三者顺序一致 |
| 版本差异 | Python 2 经典类不用 C3 | Python 3 所有类默认继承 object |


### 合并规则与 __mro__ 的推导

```python
import inspect

class Base:
    def ping(self):
        return 'base'

class Sub(Base):
    def ping(self):
        return super().ping() + '-sub'

s = Sub()
print([c.__name__ for c in inspect.getmro(Sub)])
print(inspect.getmro(Sub) == Sub.__mro__)
print('__class__' in Sub.ping.__code__.co_freevars)
print(s.ping())

def inconsistent():
    class A: pass
    class B(A): pass
    class C(A, B): pass
try:
    inconsistent()
except TypeError as e:
    print(type(e).__name__, str(e))
```

<OutputBox title='原理验证' output='[&#39;Sub&#39;, &#39;Base&#39;, &#39;object&#39;]\nTrue\nTrue\nbase-sub\nTypeError Cannot create a consistent method resolution order (MRO) for bases A, B' />

<Predict no='039-1' q='菱形 D(B, C), B(A), C(A) 下 print(D.__mro__.count(A)) 输出什么？' :options='["1", "2", "0"]' answer='0' output='1' explain='C3 线性化保证每个类在 MRO 里只出现一次，公共基类 A 被合并到链尾，计数恰为 1。' />


## super 的真实语义与零参数形式

`super()` 不是调用父类，而是返回一个代理对象，沿 `type(self).__mro__` 里当前类之后的位置查找属性：`super(C, obj).m()` 从 `MRO` 中 `C` 的下一个类开始找 `m`。

实例方法里的零参数 `super()` 等价于 `super(__class__, self)`，其中 `__class__` 是编译器为任何用到 `super()` 或 `__class__` 的方法自动创建的一个闭包 cell（可在该方法的 `co_freevars` 里看到），运行时由解释器填充；

这也解释了为什么把方法整体复制到别的类、或用 `super(C, self)` 写死类名容易出错。

类方法里 `super()` 等价 `super(__class__, cls)`，而静态方法没有 `self` 也没有 `cls`，零参数形式不可用。

协作式多继承要求链上每个类的 `__init__` 都调用 `super().__init__()` 并统一用 `**kwargs` 透传参数，这样每个初始化才恰好执行一次、参数不丢；

一旦混用显式 `A.__init__(self)`，协作链就从那里断开，`MRO` 后续类的 `__init__` 被跳过或被重复调用。

`Mixin` 只提供单一能力、全部方法用 `super` 协作、不持有实例状态，是稳妥的用法。

**super 的真实语义与协作**

| 写法 | 等价 / 行为 | 风险 |
| --- | --- | --- |
| 实例方法里 super() | super(__class__, self)，沿 MRO 找当前类之后的下一实现 | 不是调用父类 |
| __class__ cell | 编译器为用 super() 或 __class__ 的方法创建闭包 cell | 把方法挪到别的类或用 super(C, self) 写死类名会出错 |
| 类方法里 super() | super(__class__, cls) | 静态方法无 self / cls，零参数 super() 不可用 |
| 协作式多继承 | 链上每个 __init__ 都 super().__init__() 并用 **kwargs 透传 | A.__init__ 只执行一次 |
| 混用显式父类调用 | 用 A.__init__(self) 打断协作链 | 后续类被跳过或某方法被执行两次 |

```python
class A:
    def __init__(self):
        print('A')

class B(A):
    def __init__(self):
        print('B')
        A.__init__(self)

class C(A):
    def __init__(self):
        print('C')
        super().__init__()

class D(B, C):
    def __init__(self):
        super().__init__()

print([c.__name__ for c in D.__mro__])
D()
print('__class__' in B.__init__.__code__.co_freevars)
print(C.__init__.__code__.co_freevars)
```

<OutputBox title='对照写法：先自己猜，再点开' output='[&#39;D&#39;, &#39;B&#39;, &#39;C&#39;, &#39;A&#39;, &#39;object&#39;]\nB\nA\nFalse\n(&#39;__class__&#39;,)' guess="true" />


### __class__ cell 与无参 super 的解析

`MRO` 由 `C3` 线性化在类创建时（`type.__new__`）计算并固化进 `__mro__` 元组：它把子类、各基类 `MRO` 与基类声明顺序当作约束序列反复合并，选出一个不违反任何序列相对顺序的类，无法合并就抛 `TypeError`。

`super` 的实现是一个代理对象，内部持有 `__class__`（当前类）与 `self`（实例或类），查找属性时从 `type(self).__mro__` 里 `__class__` 之后的位置开始扫描，因此它找的是 `MRO` 的下一个实现而非语法上的父类；

零参数 `super()` 之所以成立，是因为编译器扫描到方法体里的 `super` 或 `__class__` 时，会自动创建一个 `__class__` cell 放进该方法的 `co_freevars`，运行时由解释器填充。

属性查找统一由 `object.__getattribute__` 驱动：它先在类及基类上按 `MRO` 找同名属性，若该属性是数据描述符就优先调用其 `__get__`，否则再查实例 `__dict__`，随后才轮到非数据描述符与普通类属性；

全失败后才把控制权交给 `__getattr__`。这条优先级正是 `property` 能拦截赋值、而实例同名键能盖住方法的根本原因。

<ConceptDiagram type='layers3' title='第 039 讲 · 分层视角' labels='C3 线性化与 __mro__|super 的真实语义与零参数形式|属性查找链与 __getattribut|__getattribute__ 入口' caption='属性查找链与 __getattribute__ 入口' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 `__getattribute__` 入口 落在哪一层。


## 属性查找链与 __getattribute__ 入口

`obj.attr` 的入口永远是 `object.__getattribute__`，重写它要极其小心，通常得用 `super().__getattribute__(name)` 兜底，否则内部再访问 `self.x` 会无限递归。

```python
object.__getattribute__(obj, 'attr')
```

查找优先级是：数据描述符（实现了 `__set__` 或 `__delete__`）→ 实例 `__dict__` → 非数据描述符（只有 `__get__`，如 `function`、`staticmethod`）→ 类属性 → 若以上都失败且定义了 `__getattr__` 才调用它 → 否则抛 `AttributeError`。

关键结论有两条：数据描述符优先于实例字典，所以 `property` 的 `setter` 无法被实例同名键绕过；非数据描述符会被实例字典遮蔽，所以可以给实例赋一个同名值盖住类里的方法。`__getattr__` 只在常规查找失败后触发，适合懒加载与代理；

`__getattribute__` 则每次访问都触发。

类属性查找走 `type.__getattribute__`，与实例链不同；

描述符的 `__get__(self, obj, objtype)` 在类访问时 `obj` 为 `None`。

用 `dis` 看 `LOAD_METHOD` / `LOAD_ATTR`，或打印 `__mro__`，都能把顺序变成可核对的证据。

**obj.attr 的查找优先级**

| 顺序 | 来源 | 说明 |
| --- | --- | --- |
| 1 数据描述符 | 类里实现 __set__ 或 __delete__ 的对象 | 优先于实例 __dict__，property setter 无法被绕过 |
| 2 实例 __dict__ | obj.__dict__ | 同名键遮蔽非数据描述符与类属性 |
| 3 非数据描述符 | 只有 __get__，如 function / staticmethod | 会被实例字典里的同名值覆盖 |
| 4 类属性 | Class.__dict__ | 沿 MRO 依次查找 |
| 5 __getattr__ | 仅在以上都失败后调用 | 做懒加载 / 代理；__getattribute__ 每次访问都触发 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：以为 super() 是调用父类，菱形继承里", "body": "super 沿 MRO 找当前类之后的下一实现，C3 保证 A 在链尾只出现一次", "tip": "按 D.__mro__ 推导调用链；每个类统一用 super().__init__() 协作"}, {"title": "第 2 步：混用 super() 与显式 A.__ini", "body": "显式调用打断协作链，MRO 里后续类的 __init__ 不再被触及", "tip": "链上所有类都用 super().__init__() 并用 **kwargs 透传参数，Mixin 不持有状态"}, {"title": "第 3 步：重写 __getattribute__ 时忘", "body": "所有属性访问都会经过它，内部再访问 self.x 会再次触发自身", "tip": "只做前置拦截后 return super().__getattribute__(name)，懒加载改用 __getattr__"}]' />


## 从实例字典到描述符的查找全链

<FlowTimeline :steps='[{"title": "C3 线性化与 __mro__", "desc": "每个类都有 `__mro__` 元组，`Class.mro()` 返回等价的列表，`…", "tone": "blue"}, {"title": "super 的真实语义与零参数形式", "desc": "`super()` 不是调用父类，而是返回一个代理对象，沿 `type(self).…", "tone": "purple"}, {"title": "属性查找链与 __getattribute__ 入口", "desc": "`obj.attr` 的入口永远是 `object.__getattribute__…", "tone": "orange"}, {"title": "工程落地", "desc": "协作式 Mixin：让多个能力沿同一条 super 链组合", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

<Term word='__mro__ 与 C3 线性化' text='每个类都有 `__mro__` 元组，`Class.mro()` 返回等价的列表，`inspect.getmro` 也能取到。`MRO` 由 `C3` 线性化在类创建时（`type.__new__`）算好：约束是子类优先于父类、保持基类声明顺序、并递归合并每个基类自身的 `MRO`，每步选出一个不在任何候选序列尾部出现' />

<Term word='super 的真实语义' text='`super()` 不是调用父类，而是返回一个代理对象，沿 `type(self).__mro__` 里当前类之后的位置查找属性：`super(C, obj).m()` 从 `MRO` 中 `C` 的下一个类开始找 `m`。实例方法里的零参数 `super()` 等价于 `super(__class__, self)`' />

<CodeTabs :tabs='[{"label": "主示例", "code": "class A:\n    def __init__(self):\n        print(&#39;A&#39;)\n\nclass B(A):\n    def __init__(self):\n        print(&#39;B&#39;)\n        super().__init__()\n\nclass C(A):\n    def __init__(self):\n        print(&#39;C&#39;)\n        super().__init__()\n\nclass D(B, C):\n    def __init__(self):\n        print(&#39;D&#39;)\n        super().__init__()\n\nprint([c.__name__ for c in D.__mro__])\nd = D()\nprint(D.__mro__ == (D, B, C, A, object))", "note": "C3 线性化与 __mro__"}, {"label": "对照 / 进阶", "code": "class A:\n    def __init__(self):\n        print(&#39;A&#39;)\n\nclass B(A):\n    def __init__(self):\n        print(&#39;B&#39;)\n        A.__init__(self)\n\nclass C(A):\n    def __init__(self):\n        print(&#39;C&#39;)\n        super().__init__()\n\nclass D(B, C):\n    def __init__(self):\n        super().__init__()\n\nprint([c.__name__ for c in D.__mro__])\nD()\nprint(&#39;__class__&#39; in B.__init__.__code__.co_freevars)\nprint(C.__init__.__code__.co_freevars)", "note": "super 的真实语义与零参数形式"}]' title='两种写法切换看' />


## 协作式 Mixin：让多个能力沿同一条 super 链组合

一个用户对象需要 `JSON` 序列化、问候语加前缀、以及基础姓名存储三种能力。若每种能力各写一套显式调用，加一个新 `Mixin` 就要改所有类的初始化顺序；用协作式多继承则不必：每个 `Mixin` 只提供单一能力、不持有状态，需要下一环时统一用 `super()`。

下面定义 `PrefixMixin.greet` 与 `JSONMixin.to_json`、`Base` 提供姓名与基础 `greet`，再让 `User` 组合三者；

打印 `MRO`、问候语与序列化结果，可以看到 `PrefixMixin` 的 `super().greet()` 会跳过没有 `greet` 的 `JSONMixin`、落到 `Base`，正是沿 `MRO` 查找的直观证据。

真实项目里所有 `__init__` 还要用 `**kwargs` 透传参数。

```python
import json

class JSONMixin:
    def to_json(self):
        return json.dumps(self.as_dict())
    def as_dict(self):
        return dict(self.__dict__)

class PrefixMixin:
    def greet(self):
        return '[' + super().greet() + ']'

class Base:
    def __init__(self, name):
        self.name = name
    def greet(self):
        return 'hi ' + self.name

class User(PrefixMixin, JSONMixin, Base):
    pass

u = User('ada')
print([c.__name__ for c in User.__mro__])
print(u.greet())
print(u.to_json())
print(u.as_dict())
```

<Callout type="idea" title='落地提示' text='Mixin 只做单一能力、全部用 super 协作、不持有状态，是多继承唯一稳妥的用法' />

<CheckList id='P039b' title='上线前自检' :items='["能复现并解释「以为 super() 是调用父类，菱形继承里 A.__ini」", "能复现并解释「混用 super() 与显式 A.__init__(self」", "能复现并解释「重写 __getattribute__ 时忘了调 super」", "能用一条命令验证 __mro__ 与 C3 线性化", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "print(type('Demo', (), {}).__mro__)"
```

把输入换成你自己的数据，观察结果是否仍符合 `__mro__` 与 C3 线性化 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## super 与 __getattribute__ 错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 以为 super() 是调用父类，菱形继承里 A.__init__ 应该跑两次 | super 沿 MRO 找当前类之后的下一实现，C3 保证 A 在链尾只出现一次 | 按 D.__mro__ 推导调用链；每个类统一用 super().__init__() 协作 |
| 混用 super() 与显式 A.__init__(self)，某个初始化被跳过或执行两次 | 显式调用打断协作链，MRO 里后续类的 __init__ 不再被触及 | 链上所有类都用 super().__init__() 并用 **kwargs 透传参数，Mixin 不持有状态 |
| 重写 __getattribute__ 时忘了调 super，属性访问全乱或无限递归 | 所有属性访问都会经过它，内部再访问 self.x 会再次触发自身 | 只做前置拦截后 return super().__getattribute__(name)，懒加载改用 __getattr__ |

<Callout type="warn" title='本讲最容易踩的坑' text='以为 super() 是调用父类，菱形继承里 A.__init__ 应该跑两次：super 沿 MRO 找当前类之后的下一实现，C3 保证 A 在链尾只出现一次' />

<CheckList id='P039a' title='学完你应当能' :items='["能讲清 C3 线性化与 __mro__", "能讲清 super 的真实语义与零参数形式", "能讲清 属性查找链与 __getattribute__ 入口", "能在工程里处理 __getattribute__ 入口"]' />


## 推导 MRO 的练习与自测

<Exercise title='基础：推导菱形继承的 MRO' task='定义 A、B(A)、C(A)、D(B, C)，打印 [c.__name__ for c in D.__mro__]，并解释 A 为什么只出现一次。' solution='class A: pass\nclass B(A): pass\nclass C(A): pass\nclass D(B, C): pass\nprint([c.__name__ for c in D.__mro__])' explain='C3 线性化把子类放前、保持声明顺序并合并各基类 MRO，得到 D B C A object，重复的 A 被合并成一次。' />

<Exercise title='进阶：写一条协作式 super 链' task='定义 Root 收 **kw，M1 与 M2 都只做 super().__init__(**kw)，Leaf 继承两者，打印 MRO 并验证 Leaf(x=1) 的参数一路传到 Root。' solution='class Root:\n    def __init__(self, **kw):\n        self.kw = kw\n\nclass M1(Root):\n    def __init__(self, **kw):\n        super().__init__(**kw)\n\nclass M2(Root):\n    def __init__(self, **kw):\n        super().__init__(**kw)\n\nclass Leaf(M1, M2):\n    pass\nprint([c.__name__ for c in Leaf.__mro__])\nprint(Leaf(x=1).kw)' explain='每个类都用 super().__init__(**kw) 透传，初始化沿 MRO 依次经过 M1、M2 到 Root，参数不丢且 Root 只执行一次。' />

<Quiz no='039-2' q='super() 的真实语义是？' :options='["沿当前类的 MRO 找下一个实现", "调用直接父类", "调用 object 的方法", "按名字查全局函数"]' answer="0" explain='super 返回代理对象，从 type(self).__mro__ 里 __class__ 之后的位置开始查找，不是语法上的父类调用。' />

<Quiz no='039-3' q='菱形 D(B, C), B(A), C(A) 的 MRO 是？' :options='["(D, B, C, A, object)", "(D, B, A, C, object)", "(D, C, B, A, object)", "(D, A, B, C, object)"]' answer="0" explain='C3 保持 B 在 C 前的声明顺序、子类优先，并把菱形底端的 A 合并到二者之后，得到 D B C A object。' />

<Quiz no='039-4' q='obj.x 查找时，数据描述符与实例 __dict__ 谁优先？' :options='["数据描述符优先，实例字典无法绕过它", "实例字典优先", "看定义顺序", "两者都不查，直接 __getattr__"]' answer="0" explain='object.__getattribute__ 先处理数据描述符（有 __set__ / __delete__），所以 property setter 拦得住每次赋值；非数据描述符才会被实例字典遮蔽。' />

<FillBlank no='039-5' tpl='___ __init__(self):' :answers='["def"]' hint='回想本讲关于 __mro__ 与 C3 线性化 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 C3 线性化与 __mro__ 的落点。' />

<KnowledgeCard :points='["MRO 由 C3 线性化在类创建时算好存进 __mro__；子类优先、保持声明顺序、object 恒在末尾", "菱形 D(B, C), B(A), C(A) → (D, B, C, A, object)；不一致顺序抛 Cannot create a consistent method resolution order (MRO)", "super() 不是调父类，是沿 type(self).__mro__ 找当前类之后的下一实现；零参数形式依赖编译器塞入的 __class__ cell", "协作式多继承：链上每个 __init__ 都 super().__init__() 并用 **kwargs 透传；Mixin 单一能力、不持有状态", "混用显式 A.__init__(self) 会断链，导致类被跳过或方法执行两次", "obj.attr 优先级：数据描述符 &gt; 实例 __dict__ &gt; 非数据描述符 &gt; 类属性 &gt; __getattr__；__getattribute__ 是所有访问的入口"]' :pitfalls='["以为 super() 是调用父类，菱形继承里 A.__init__ 应该跑两次", "混用 super() 与显式 A.__init__(self)，某个初始化被跳过或执行两次", "重写 __getattribute__ 时忘了调 super，属性访问全乱或无限递归", "混用 super() 与显式父类调用，会让某个初始化方法被执行两次或完全跳过"]' summary='super() 不是调用父类，而是沿当前类的 MRO 找下一个实现；理解这点才能写好协作式多继承' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| MRO 由 C3 线性化在类创建时算好存进 __mro__；子类优先、保持声明顺序、object 恒在末尾 | 建立直觉 |
| 菱形 D(B, C), B(A), C(A) → (D, B, C, A, object)；不一致顺序抛 Cannot create a consistent method resolution order (MRO) | 跑通示例 |
| super() 不是调父类，是沿 type(self).__mro__ 找当前类之后的下一实现；零参数形式依赖编译器塞入的 __class__ cell | 深入边界 |
| 协作式多继承：链上每个 __init__ 都 super().__init__() 并用 **kwargs 透传；Mixin 单一能力、不持有状态 | 工程落地 |
| 混用显式 A.__init__(self) 会断链，导致类被跳过或方法执行两次 | 随堂检测 |
| obj.attr 优先级：数据描述符 > 实例 __dict__ > 非数据描述符 > 类属性 > __getattr__；__getattribute__ 是所有访问的入口 | 复盘 |

1. MRO 由 C3 线性化在类创建时算好存进 __mro__；子类优先、保持声明顺序、object 恒在末尾

2. 菱形 D(B, C), B(A), C(A) → (D, B, C, A, object)；不一致顺序抛 Cannot create a consistent method resolution order (MRO)

3. super() 不是调父类，是沿 type(self).__mro__ 找当前类之后的下一实现；零参数形式依赖编译器塞入的 __class__ cell

[下一讲：访问控制、property 与描述符协议](/oop/property)
