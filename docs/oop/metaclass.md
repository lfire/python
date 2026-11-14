---
title: 第 045 讲 · 元类：__new__、type 与类创建过程
description: 能读懂并写出框架级的类定制逻辑
---

<StageHeader stage='L4 · 面向对象' level='★★★★★' time='45 分钟' goal='能读懂并写出框架级的类定制逻辑' prereq='第 044 讲 · 鸭子类型、抽象基类与 Protocol' />

# 第 045 讲 · 元类：__new__、type 与类创建过程

前面几讲一直在用类、改类。到这里值得问个更根本的问题：类自己是谁造出来的？Python 里类也是对象，`class` 语句得到的类同样是被创建出来的；想通这层，ORM 里「类里写一行就自动生效」就不神秘了。

比如 ORM 在类定义时收集字段，却拿不到预期顺序，两个第三方基类一继承还会冲突。本讲先用 `type` 的三参数形式亲手造一个类，再按时间线走过 `__new__` 与 `__init__`，最后比较元类、`__init_subclass__` 与类装饰器各管哪一段。需要第 40 讲的描述符；学完你能读懂框架级的类定制逻辑，也清楚哪些需求用不上元类。


## 框架里一个字段声明顺序总是对不上的 bug

一个 ORM 框架要在类定义时自动收集字段并生成表名，开发者把收集逻辑写进元类的 `__init__`，却发现拿到的类字典顺序和预期不一致，而且 `__set_name__`、`__init_subclass__` 已经先跑过一轮，注册结果对不上。

另一处更直接：有人在 `__new__` 里做校验却忘了 `return super().__new__(mcls, name, bases, ns)`，类对象变成 `None`，实例化时抛 `TypeError`，提示 `NoneType` 不可调用。

还有团队同时继承两个第三方基类，各自带不同元类，一继承就抛 `metaclass conflict`：候选元类必须是所有候选的（非严格）子类，否则选不出一个能兼容全部基类的创建者。

这些故障都压在同一个认知上：类也是对象，它的创建由元类控制。

`__new__` 与 `__init__` 谁先谁后、`__set_name__` 与 `__init_subclass__` 在哪个阶段被触发、`type(name, bases, ns)` 三参数形式到底做了什么，决定了框架能不能把「类里写字段」正确翻译成运行时行为。

本讲按类创建发生的先后把每个阶段摆开，并明确哪些需求其实用不上元类。

<Callout type="warn" title='先看一个真实会出错的写法' text='元类 __new__ 里漏写 return super().__new__(...)：__new__ 必须返回类对象，返回 None 会让 class 语句绑定到 None，实例化时报 TypeError: &#39;NoneType&#39; object is not callable' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 044 讲 · 鸭子类型、抽象基类与 Protocol |
| 难度 / 建议时长 | ★★★★★ · 45 分钟 |
| 本讲新增 | 类也是对象、type 的三参数形式、__new__ 与 __init__ 分工 |
| 一句话目标 | 能读懂并写出框架级的类定制逻辑 |
| 为下一讲铺垫 | 反射与自省：getattr、inspect 与 __dict__ |


## 类也是对象：type 的三参数形式与默认元类

在 CPython 里类本身是堆上的对象，`type(obj)` 返回它的类型；对普通类 `C` 来说 `type(C)` 是 `type`，而 `type` 自己也是自己的实例。

类有三种创建方式：`class` 语句、`type(name, bases, ns)` 三参数调用、以及自定义元类。

`type` 与写 `class Dyn: value = 42` 等价，返回一个可直接实例化、可赋属性的类对象；

```python
type('Dyn', (object,), {'value': 42})
```

`bases` 是基类元组，`namespace` 是字符串键到对象的映射，类体里的名字、方法、注解都落在里面。默认元类的选择规则是：显式写了 `metaclass=` 就用它；否则取所有基类 `type(base)` 里最派生的那一个；

若这些元类互不为子类，就报 `metaclass conflict`。

类对象上能读到的东西都在它的字典与槽里：`__name__`、`__bases__`、`__mro__`、`__dict__`。理解「类是 `type` 的实例」后，元类就不再神秘——它只是「类的类」，重写它的 `__new__` / `__init__` 就能干预类创建。

要注意 `type(obj)` 与 `obj.__class__` 通常一致，但代理对象可以改写 `__class__` 属性来伪装，排查时应以 `type()` 为准。

钩子的归属也各有位置：`__prepare__` 由 `__build_class__` 在类体执行前调用，`__set_name__` 与 `__init_subclass__` 则在 `type.__new__` 内部触发。

```python
class Registry(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        cls.registered = name.lower()
        return cls
class Model(metaclass=Registry):
    pass

print('metaclass', type(Model).__name__)
print('registered', Model.registered)
Dynamic = type('Dynamic', (object,), {'value': 42})
print('dynamic', Dynamic.__name__, Dynamic.value)
print('bases', [b.__name__ for b in Model.__bases__])
```

<OutputBox title='主示例运行结果' output='metaclass Registry\nregistered model\ndynamic Dynamic 42\nbases [&#39;object&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Registry(type):\n    def __new__(mcls, name, bases, ns):\n        cls = super().__new__(mcls, name, bases, ns)\n        cls.registered = name.lower()\n        return cls\nclass Model(metaclass=Registry):\n    pass\n\nprint(&#39;metaclass&#39;, type(Model).__name__)\nprint(&#39;registered&#39;, Model.registered)\nDynamic = type(&#39;Dynamic&#39;, (object,), {&#39;value&#39;: 42})\nprint(&#39;dynamic&#39;, Dynamic.__name__, Dynamic.value)\nprint(&#39;bases&#39;, [b.__name__ for b in Model.__bases__])' :notes='["自定义元类，继承 type 才能干预类创建", "__new__ 在 __init__ 之前，可改写 namespace 与 bases", "必须调用 super().__new__ 并传 mcls，拿到真正的类对象", "在类创建期注入一个 registered 属性", "务必 return 类对象，漏掉会让类变成 None", "用 metaclass= 指定元类", "空类体，registered 由元类补上", "空行，只用于分隔逻辑块，不影响执行结果。", "空行分隔定义与验证", "type(Model) 是元类 Registry，不是 type", "读回元类注入的属性，值为小写的类名", "type(name, bases, ns) 三参数形式动态创建类", "动态类名与类属性都能正常访问"]' title='第 045 讲 · 元类：__new__、type 与类创建过程' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='在 CPython 里类本身是堆上的对象，`type(obj)` 返回它的类型；对普通类 `C` 来说 `type(C)` 是 `type`，而 `type` 自己也是自己的实例。类有三种创建方式：`class` 语句、`type(name, bases, ns)` 三参数调用、以及自定义元类。…' />


### type 三参数形式与类对象属性

**type 三参数形式与类对象属性**

| 表达式 / 属性 | 含义 | 返回值 |
| --- | --- | --- |
| type('D', (object,), &#123;'v': 1&#125;) | 动态创建类 | 新类对象 |
| type(C) | C 的元类 | 默认 type 或自定义元类 |
| C.__bases__ | 直接基类元组 | tuple of class |
| C.__mro__ | 方法解析顺序 | tuple of class |
| C.__dict__ | 类命名空间映射 | mappingproxy |
| type(C) is type | 判断是否默认元类 | bool |


## 类创建时间线：__prepare__、类体、__new__、set_name、init_subclass、__init__

执行 `class` 语句时，CPython 的 `__build_class__` 先确定元类，再调用元类的 `__prepare__(name, bases)` 拿到命名空间映射，默认返回普通 `dict`；

3.7 起 `dict` 正式保证插入顺序（CPython 3.6 已实现，只是当时尚未写进语言规范），所以在 `__prepare__` 里专门返回 `collections.OrderedDict` 来保序的旧写法已无必要，但这个钩子仍可用来注入名字或记录声明顺序。

接着类体在独立帧里执行，所有赋值与方法定义写进这个映射。

然后调用 `metaclass(name, bases, ns)`，即 `type.__call__` → 元类 `__new__` → 元类 `__init__`。

顺序里有两处常被忽略：`type.__new__` 内部会遍历 `namespace`，对每个定义了 `__set_name__` 的描述符回调（PEP 487，3.6 引入，回调时收到 `owner` 与 `name`），让描述符知道自己在类里的属性名；

随后调用基类的 `__init_subclass__`（同样是 3.6，自动是 `classmethod`），把子类创建通知给父类。

这两步都在 `__new__` 里完成，早于元类 `__init__`。

所以「在 `__init__` 里收集字段」拿到的是已经跑过 `__set_name__` 和 `__init_subclass__` 的类，顺序与内容都可能被改过；

要改写 `namespace`、`bases` 或注入属性，必须放在 `__new__` 里，并且务必 `return` 新建的类对象。`__init__` 只做初始化，此时类已定型，换不了 `bases` 也换不了对象本身。

```python
import inspect

class M(type):
    @classmethod
    def __prepare__(mcls, name, bases):
        print('prepare', name)
        return {}
class C(metaclass=M):
    pass
print('type of class:', type(C) is type, type(C).__name__)
print('is type instance:', isinstance(C, type))
print('MRO:', [c.__name__ for c in inspect.getmro(C)])
```

<OutputBox title='原理验证' output='prepare C\ntype of class: False M\nis type instance: True\nMRO: [&#39;C&#39;, &#39;object&#39;]' />


### 类创建各阶段、钩子与可干预内容

**类创建各阶段、钩子与可干预内容**

| 阶段 | 钩子 / 调用 | 能否改写 | 引入版本 |
| --- | --- | --- | --- |
| 确定元类 | __build_class__ 取最派生元类 | 冲突则报 metaclass conflict | 长期可用 |
| 准备命名空间 | metaclass.__prepare__(name, bases) | 可返回自定义映射 | 3.x，3.7 起 dict 保序 |
| 执行类体 | 独立帧写入 namespace | 写入即定型 | 长期可用 |
| 创建类对象 | metaclass.__new__(mcls, name, bases, ns) | 可改 bases、ns、注入属性，必须 return 类 | 长期可用 |
| 描述符命名 | type.__new__ 回调 __set_name__(owner, name) | 描述符可记录属性名 | 3.6 / PEP 487 |
| 通知父类 | type.__new__ 回调 __init_subclass__(**kw) | 基类可登记/校验子类 | 3.6 / PEP 487 |
| 初始化类 | metaclass.__init__(cls, ...) | 类已定型，不能换对象 | 长期可用 |


## 从 type_new 到 PyType_Ready 的源码路径

CPython 把每个类表示为 `PyTypeObject`（heap type 或 static type）。

执行 `class` 语句时 `__build_class__` 先按 `bases` 计算 metaclass，调用其 `__prepare__` 拿到 `namespace`，再让类体字节码在独立帧里把名字写进这个映射，最后调用 `metaclass(name, bases, ns)`。

这一次调用经 `type.__call__` 分派到 `type.__new__`：它分配 `PyTypeObject`、把 `ns` 里的函数包装成 slot（`PyType_Ready`）、遍历 `ns` 对带 `__set_name__` 的描述符回调 `type_new_set_names`，再调用 `super().__init_subclass__`（`type_new_init_subclass`），最后返回类对象；

随后才是元类 `__init__`。

因此 `__set_name__` 与 `__init_subclass__` 都发生在 `__new__` 内、早于 `__init__`。

零参数 `super()` 靠编译器在类体方法里塞一个 `__class__` cell，指向正在定义的类；元类若重建类对象，这个闭包可能指向旧类，是框架里的隐蔽 bug 源。

`metaclass conflict` 来自 `__build_class__` 的判定：候选元类必须是其它所有候选的（非严格）子类，否则无法选出一个能兼容全部基类的创建者。

理解这条 C 层链路，就知道为什么「收集字段」必须放 `__new__`、为什么漏 `return` 会让类变成 `None`。

<ConceptDiagram type='flow3' title='第 045 讲 · 类也是对象：type 的三参数形式与默认元类' labels='类也是对象：type 的三参数形式与默认元类|类创建时间线：__prepare__、类体…|选型与冲突：元类、__init_subcla…' caption='能读懂并写出框架级的类定制逻辑' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## __set_name__ 与 __init_subclass__ 如何替代部分元类

<FlowTimeline :steps='[{"title": "类也是对象：type 的三参数形式与默认元类", "desc": "在 CPython 里类本身是堆上的对象，`type(obj)` 返回它的类型；对普…", "tone": "blue"}, {"title": "类创建时间线：__prepare__、类体、__…", "desc": "执行 `class` 语句时，CPython 的 `__build_class__`…", "tone": "purple"}, {"title": "选型与冲突：元类、__init_subclass…", "desc": "元类控制「类如何被创建」，能力最强，也最容易让 IDE、类型检查器与调试器失去线索…", "tone": "orange"}, {"title": "工程落地", "desc": "ORM 字段注册：元类收集映射 + __set_name__ 命名", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

<Term word='类也是对象' text='在 CPython 里类本身是堆上的对象，`type(obj)` 返回它的类型；对普通类 `C` 来说 `type(C)` 是 `type`，而 `type` 自己也是自己的实例。类有三种创建方式：`class` 语句、`type(name, bases, ns)` 三参数调用、以及自定义元类。…' />

<Term word='type 的三参数形式' text='执行 `class` 语句时，CPython 的 `__build_class__` 先确定元类，再调用元类的 `__prepare__(name, bases)` 拿到命名空间映射，默认返回普通 `dict`；3.7 起 `dict` 正式保证插入顺序（CPython 3.6 已实现，只是当时尚未写进语言规范），所以…' />

<SequenceDiagram title='第 045 讲 · 调用时序' caption='从触发到收尾，标出最可能失败的两个位置' :actors='["调用方", "核心逻辑", "外部依赖"]' :steps='[{"from": "调用方", "to": "核心逻辑", "label": "发起调用", "note": "类也是对象：type 的三参…", "kind": "call"}, {"from": "核心逻辑", "to": "核心逻辑", "label": "检查前置", "note": "类创建时间线：__prepa…", "kind": "self"}, {"from": "核心逻辑", "to": "外部依赖", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "外部依赖", "to": "核心逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "核心逻辑", "to": "调用方", "label": "返回或降级", "note": "清理资源", "kind": "return"}]' />


## 选型与冲突：元类、__init_subclass__、类装饰器各管一段

元类控制「类如何被创建」，能力最强，也最容易让 IDE、类型检查器与调试器失去线索：静态工具看不到运行时注入的属性，反射出来的 MRO 也和源码不一致。

绝大多数需求有更轻的替代：只是想在子类创建时做登记或校验，用基类上的 `__init_subclass__`；

只是想给描述符拿到属性名，用 `__set_name__`；只是想给成品类加方法或改属性，用类装饰器（接收类、返回类，不改变继承关系）。元类真正不可替代的场景是必须改 `bases`、必须替换 `namespace` 类型、或必须让 `isinstance` / 类级别行为随创建过程改变，ORM 字段收集与接口注册属于经典用法。

元类冲突的修复是新建一个同时继承所有相关元类的新元类，再让子类用它，或统一让所有基类共用同一元类。还有两个细节：零参数 `super()` 依赖编译器在类体里生成的 `__class__` cell，元类若重建类要留意这个闭包是否仍指向预期类；

`super().__new__(mcls, ...)` 必须显式传 `mcls`，漏了会把 `name` 当成元类参数而触发类型错误。

写元类前先问一句「`__init_subclass__` 能不能做」，能就别上元类。

```python
class Field:
    def __set_name__(self, owner, name):
        self.name = name
        print('set_name', name)
class Base:
    subclasses = []
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        Base.subclasses.append(cls.__name__)
        print('init_subclass', cls.__name__)
class User(Base):
    uid = Field()
print('registry', Base.subclasses)
print('field name', User.uid.name)
```

<OutputBox title='对照写法：先自己猜，再点开' output='set_name uid\ninit_subclass User\nregistry [&#39;User&#39;]\nfield name uid' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "class Registry(type):\n    def __new__(mcls, name, bases, ns):\n        cls = super().__new__(mcls, name, bases, ns)\n        cls.registered = name.lower()\n        return cls\nclass Model(metaclass=Registry):\n    pass\n\nprint(&#39;metaclass&#39;, type(Model).__name__)\nprint(&#39;registered&#39;, Model.registered)\nDynamic = type(&#39;Dynamic&#39;, (object,), {&#39;value&#39;: 42})\nprint(&#39;dynamic&#39;, Dynamic.__name__, Dynamic.value)\nprint(&#39;bases&#39;, [b.__name__ for b in Model.__bases__])", "note": "类也是对象：type 的三参数形式与默认元类"}, {"label": "对照 / 进阶", "code": "class Field:\n    def __set_name__(self, owner, name):\n        self.name = name\n        print(&#39;set_name&#39;, name)\nclass Base:\n    subclasses = []\n    def __init_subclass__(cls, **kw):\n        super().__init_subclass__(**kw)\n        Base.subclasses.append(cls.__name__)\n        print(&#39;init_subclass&#39;, cls.__name__)\nclass User(Base):\n    uid = Field()\nprint(&#39;registry&#39;, Base.subclasses)\nprint(&#39;field name&#39;, User.uid.name)", "note": "类创建时间线：__prepare__、类体、__new__、set_name、init_subclass、__init__"}]' title='两种写法切换看' />


## 需求到工具的选型

**需求到工具的选型**

| 需求 | 首选工具 | 原因 |
| --- | --- | --- |
| 子类创建时登记 | __init_subclass__ | 更轻，静态工具可见，不需元类 |
| 描述符拿到属性名 | __set_name__ | 由 type.__new__ 自动回调 |
| 给成品类加方法 | 类装饰器 | 接收类返回类，不改继承关系 |
| 改写 bases 或 namespace | 元类 __new__ | 只有这一层能改创建输入 |
| 多个元类不兼容 | 合并元类 | 新建继承所有相关元类的元类 |
| 零参数 super() | __class__ cell | 由编译器在类体生成，重建类时要留意 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：元类 __new__ 里漏写 return…", "body": "__new__ 必须返回类对象，返回 None 会让 class 语句绑定到 None，实例化时报 TypeError: &#39;NoneType&#39; object is not callable", "tip": "始终 cls = super().__new__(mcls, name, bases, ns) 并在末尾 return cls；改写逻辑只作用于 cls"}, {"title": "第 2 步：把字段收集或校验放进元类 __init__…", "body": "__set_name__ 与 __init_subclass__ 已在 __new__ 内跑过，__init__ 拿到的类可能已被改过，且无法再改 bases", "tip": "需要改写 namespace、bases 或注入属性的逻辑放 __new__；只做登记时改用 __init_subclass__"}, {"title": "第 3 步：同时继承两个带不同自定义元类的基类", "body": "__build_class__ 无法选出兼容所有基类的最派生元类，抛 metaclass conflict", "tip": "新建一个继承所有相关元类的元类并指定给子类，或统一让所有基类共用同一元类"}]' />


## ORM 字段注册：元类收集映射 + __set_name__ 命名

声明式 ORM 的核心是把「类里写字段」翻译成「运行时表结构」：开发者只写 `uid = Field(int)`，框架要得到表名、列名与类型映射。

这段翻译分两层：`__set_name__` 在 `type.__new__` 里回调，让每个描述符记住自己的列名；元类 `__new__` 扫描类命名空间收集所有 `Field`，生成 `_columns` 与 `_table`，并跳过抽象基类本身。

下面用标准库完整跑通：定义 `Model` 基类、`User` 模型，打印表名与列映射，再生成一个参数化的 `CREATE TABLE` 语句。

要点是收集发生在 `__new__`（此时 `namespace` 尚未被后续钩子改动），而列名的获得交给 `__set_name__`——两处各管一段，比在 `__init__` 里硬猜字段名可靠。真实框架还会在这里加类型校验、索引与迁移，但骨架就是这两个钩子。

```python
class Field:
    def __init__(self, typ):
        self.typ = typ
    def __set_name__(self, owner, name):
        self.name = name
class ModelMeta(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        if name != 'Model':
            cls._columns = {}
            for k, v in ns.items():
                if isinstance(v, Field):
                    cls._columns[v.name] = v.typ.__name__
            cls._table = name.lower() + 's'
        return cls
class Model(metaclass=ModelMeta):
    pass
class User(Model):
    uid = Field(int)
    name = Field(str)
print('table', User._table)
print('columns', User._columns)
def create_sql(model):
    cols = ', '.join(k + ' ' + v.upper() for k, v in model._columns.items())
    return 'CREATE TABLE ' + model._table + ' (' + cols + ')'
print(create_sql(User))
```

<Callout type="idea" title='落地提示' text='ORM 映射、字段注册、接口校验是元类的经典场景；写之前先确认没有更轻的方案' />

<CheckList id='P045b' title='上线前自检' :items='["能复现并解释「元类 __new__ 里漏写 return super().…」", "能复现并解释「把字段收集或校验放进元类 __init__，结果与声明顺序不…」", "能复现并解释「同时继承两个带不同自定义元类的基类」", "能用一条命令验证 类也是对象", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "print(type('Demo', (), {'x':1}).__mro__)"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 类也是对象 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 漏写 super().__new__、在 __init__ 里收集字段、元类冲突的错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 元类 __new__ 里漏写 return super().__new__(...) | __new__ 必须返回类对象，返回 None 会让 class 语句绑定到 None，实例化时报 TypeError: 'NoneType' object is not callable | 始终 cls = super().__new__(mcls, name, bases, ns) 并在末尾 return cls；改写逻辑只作用于 cls |
| 把字段收集或校验放进元类 __init__，结果与声明顺序不符 | __set_name__ 与 __init_subclass__ 已在 __new__ 内跑过，__init__ 拿到的类可能已被改过，且无法再改 bases | 需要改写 namespace、bases 或注入属性的逻辑放 __new__；只做登记时改用 __init_subclass__ |
| 同时继承两个带不同自定义元类的基类 | __build_class__ 无法选出兼容所有基类的最派生元类，抛 metaclass conflict | 新建一个继承所有相关元类的元类并指定给子类，或统一让所有基类共用同一元类 |

<Callout type="warn" title='本讲最容易踩的坑' text='元类 __new__ 里漏写 return super().__new__(...)：__new__ 必须返回类对象，返回 None 会让 class 语句绑定到 None，实例化时报 TypeError: &#39;NoneType&#39; object is not callable' />


## __build_class__ 到 type_new：类创建的 C 层调用链

class 语句编译出 `LOAD_BUILD_CLASS`，把类体函数、类名与基类元组交给 Python/`bltinmodule.c` 的 builtin`___build_class__`：先对每个 base 调 `__mro_entries__`（PEP 560）归一化基类，再按 _PyType_CalculateMetaclass 选元类，然后调 `__prepare__` 拿到命名空间映射，类体在独立帧执行，赋值、方法、注解与编译器为 `super()` 生成的 `__classcell__` 都写进去。

真正创建类在 Objects/`typeobject.c` 的 type_new：把 namespace 复制进 tp_dict，type_new_set_names 对 `__set_name__` 描述符逐个回调，type_new_init_subclass 调基类的 `__init_subclass__`，最后 PyType_Ready 固化 MRO、填 tp_slots、把 `__dict__` 变成 mappingproxy。

关键边界：类体用的 dict 在类创建后被丢弃，元类 `__init__` 拿到的 `cls.__dict__` 是只读代理；

`__set_name__` 与 `__init_subclass__` 都在 type_new 内、早于元类 `__init__`，因此改 bases 或 namespace 只能放在 `__new__`。

```python
import types

class Meta(type):
    def __new__(mcls, name, bases, ns, **kw):
        cell = ns.get('__classcell__')
        print('classcell in ns', isinstance(cell, types.CellType))
        return super().__new__(mcls, name, bases, ns)

class Base:
    pass

class C(Base, metaclass=Meta):
    def m(self):
        return super().m()

print('cell type', type(C.m.__closure__[0]).__name__)
print('cell points to C', C.m.__closure__[0].cell_contents is C)

```

<OutputBox title='扩展示例运行结果' output='classcell in ns True\ncell type cell\ncell points to C True' />

<LineByLine code='import types\n\nclass Meta(type):\n    def __new__(mcls, name, bases, ns, **kw):\n        cell = ns.get(&#39;__classcell__&#39;)\n        print(&#39;classcell in ns&#39;, isinstance(cell, types.CellType))\n        return super().__new__(mcls, name, bases, ns)\n\nclass Base:\n    pass\n\nclass C(Base, metaclass=Meta):\n    def m(self):\n        return super().m()\n\nprint(&#39;cell type&#39;, type(C.m.__closure__[0]).__name__)\nprint(&#39;cell points to C&#39;, C.m.__closure__[0].cell_contents is C)\n' :notes='["types.CellType 用来核验 ns 里的 __classcell__ 是不是闭包单元", "空行，只用于分隔逻辑块，不影响执行结果。", "自定义元类继承 type，才能在 __new__ 阶段读到原始命名空间", "类体用了零参数 super()，编译器会把 __classcell__ 写进 ns", "把 ns 原样交给 type.__new__，cell 才会被取出并回填到方法闭包", "读回方法闭包的第一个 cell，确认其运行时类型", "cell 内容指向 C 本身，证明 __classcell__ 已被 type_new 正确回填", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `class Base:` 的作用，可对照上方输出逐项核对。", "这一行 `pass` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `class C(Base, metaclass=Meta):` 的作用，可对照上方输出逐项核对。", "这一行 `def m(self):` 的作用，可对照上方输出逐项核对。", "这一行 `return super().m()` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `print(&#39;cell type&#39;, type(C.m.__closure__[0]).__name__` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;cell points to C&#39;, C.m.__closure__[0].cell_co` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />


### __classcell__ 如何穿过 namespace 回到零参数 super

<ConceptDiagram type='flow4' title='第 045 讲 · 扩展图解' labels='__build_class__ 字节码|__prepare__ 命名空间|type_new_set_names 回调|__classcell__ 回填闭包' caption='类创建在 C 层的四段关键帧：字节码入口先解析基类、命名空间承载声明、type_new 触发描述符回调，最后把闭包 cell 回填给 super()。' />

<Term word='__classcell__' text='类体引用零参数 super() 时编译器生成的闭包单元，以 __classcell__ 键塞进命名空间；type_new 取出它填进方法闭包，元类重建 ns 必须原样透传，3.8 起漏传抛 RuntimeError。' />


## _PyType_CalculateMetaclass 与 __mro_entries__ 的基类归一化

_PyType_CalculateMetaclass（Objects/`typeobject.c`）在 `__prepare__` 之前执行：遍历归一化后的 bases，对每个取 `Py_TYPE(base)` 作候选元类，维护 winner，winner 是 candidate 子类则保留、candidate 是 winner 子类则替换，互不相关就抛 TypeError: metaclass conflict。

这解释了显式 `metaclass=` 也要与所有基类的元类兼容，修复冲突只能造一个同时继承双方的新元类。

`__mro_entries__` 来自 PEP 560：base 不是 type 实例但定义了该钩子时，builtin`___build_class__` 调它拿回替换元组，`typing.Generic[T]` 才能出现在 class 括号里。

顺序固定：先归一化 bases，再算元类，最后 `__prepare__`，所以 `__mro_entries__` 返回的类会改变元类选择。

解释器还把原始 base 元组存进 `__orig_bases__` 供 typing 反射。

**C 层函数与它触发的 Python 钩子**

| C 层函数 | 源码文件 | 触发的钩子或动作 |
| --- | --- | --- |
| builtin___build_class__ | Python/bltinmodule.c | __mro_entries__、元类选择、__prepare__ |
| type_new | Objects/typeobject.c | 把 namespace 复制进 tp_dict |
| type_new_set_names | Objects/typeobject.c | 描述符的 __set_name__(owner, name) |
| type_new_init_subclass | Objects/typeobject.c | 基类的 __init_subclass__(cls, **kw) |
| PyType_Ready | Objects/typeobject.c | 算 MRO、填 tp_slots、__dict__ 转 mappingproxy |
| _PyType_CalculateMetaclass | Objects/typeobject.c | metaclass conflict 的 winner 判定 |


### 元类重建命名空间时的字段丢失复盘

某 ORM 元类把双下划线开头的键全过滤掉再交给 `super().__new__`，上线后所有用零参数 `super()` 的模型类在定义阶段就崩：RuntimeError: `__class__` not set defining 'User' ... Was `__classcell__` propagated to `type.__new__`?。

根因是编译器为 `super()` 生成的 `__classcell__` 也是双下划线开头，被一并丢掉，type_new 拿不到 cell 就填不进方法闭包，3.8 起显式报错。修复是清洗后补回该键，或先复制 ns 再 pop，别误伤解释器注入的键；

`__qualname__`、`__annotations__` 同理要进白名单。

下面用同一个 Cleaning 元类配开关，先复现报错再验收修复，以闭包内容是否指向类本身为准。

```python
KEEP_CELL = False

class Cleaning(type):
    def __new__(mcls, name, bases, ns):
        clean = {k: v for k, v in ns.items() if not k.startswith('__')}
        if KEEP_CELL and '__classcell__' in ns:
            clean['__classcell__'] = ns['__classcell__']
        return super().__new__(mcls, name, bases, clean)

class Base:
    pass

try:
    class Broken(Base, metaclass=Cleaning):
        def m(self):
            return super().m()
    print('built', 'ok')
except RuntimeError as e:
    print('error', type(e).__name__)
    print('mentions classcell', '__classcell__' in str(e))

KEEP_CELL = True

class Fixed(Base, metaclass=Cleaning):
    def m(self):
        return super().m()
print('fixed super', Fixed.m.__closure__[0].cell_contents is Fixed)

```

<Quiz no='045-1' q='元类在 __new__ 里用字典推导重建了 namespace，随后某个使用了零参数 super() 的子类在定义时抛 RuntimeError: __class__ not set defining，最可能的根因是什么？' :options='["__init_subclass__ 没有显式调用 super().__init_subclass__()", "重建 namespace 时丢弃了编译器注入的 __classcell__", "子类的 __set_name__ 描述符没有接收 owner 参数", "type_new 之后 __dict__ 被转成了只读 mappingproxy"]' answer="1" explain='零参数 super() 依赖编译器生成的 __class__ 闭包单元，它以 __classcell__ 键存在于类命名空间里，type.__new__ 负责取出并填入方法闭包。用前缀过滤重建 ns 会把这个双下划线键一并丢掉，3.8 起解释器检测到 cell 未回填就抛 RuntimeError。__init_subclass__ 是否调 super 只影响钩子链，__dict__ 变 mappingproxy 发生在类创建完成之后，都不会在定义阶段触发这条报错。' />


## 读得懂框架才算学会

<Exercise title='基础：用 type 三参数动态创建类并验证' task='用 type(name, bases, ns) 创建一个带方法 hello 的类，实例化并调用；再打印 type(C) 与 C.__bases__，说明它和 class 语句等价在哪里。' solution='def hello(self):\n    return &#39;hi &#39; + self.tag\nC = type(&#39;C&#39;, (object,), {&#39;hello&#39;: hello, &#39;tag&#39;: &#39;x&#39;})\nc = C()\nprint(c.hello(), type(C) is type, [b.__name__ for b in C.__bases__])' explain='type(name, bases, ns) 返回的类与 class 语句生成的都是 PyTypeObject，可实例化、可继承；ns 里的函数成为方法。默认元类为 type，__bases__ 为 (object,)。' />

<Exercise title='进阶：用 __init_subclass__ 替代元类做子类登记' task='写基类 Registry，在 __init_subclass__ 里把子类名收进列表；再定义两个子类，打印登记表，说明为什么这比元类更容易被 IDE 与类型检查器理解。' solution='class Registry:\n    items = []\n    def __init_subclass__(cls, **kw):\n        super().__init_subclass__(**kw)\n        Registry.items.append(cls.__name__)\nclass A(Registry): pass\nclass B(Registry): pass\nprint(Registry.items)' explain='__init_subclass__ 由 type.__new__ 在类创建期自动调用，逻辑写在基类源码里、静态可见，不改 MRO、不注入隐藏属性；只有必须改 bases 或 namespace 时才需要元类。' />

<Quiz no='045-2' q='类创建时 __set_name__ 与元类 __init__ 的先后顺序是？' :options='["__set_name__ 在 type.__new__ 内先触发，__init__ 最后", "__init__ 先，__set_name__ 后", "两者同时", "取决于是否写了 metaclass"]' answer="0" explain='type.__new__ 内部遍历 namespace 回调 __set_name__，再调 __init_subclass__，之后才返回类对象并进入元类 __init__。因此收集字段应放 __new__。' />

<Quiz no='045-3' q='元类 __new__ 忘了 return 类对象会怎样？' :options='["类绑定到 None，实例化报 TypeError: &#39;NoneType&#39; object is not callable", "自动回退到 type.__new__", "抛 metaclass conflict", "类被创建但缺少自定义属性"]' answer="0" explain='__new__ 的返回值就是 class 语句绑定的对象；返回 None 后名字指向 None，调用它自然报 &#39;NoneType&#39; object is not callable。必须显式 return cls。' />

<Quiz no='045-4' q='同时继承两个带不兼容元类的基类，正确修复是？' :options='["新建一个继承所有相关元类的元类并指定给子类", "给子类加 metaclass=type", "删掉其中一个基类的方法", "把其中一个元类改成普通函数"]' answer="0" explain='__build_class__ 要求候选元类是其它候选的子类；新建一个合并元类（同时继承两者）即可兼容。指定 type 会与自定义元类冲突，删方法或改函数都不解决判定。' />

<Predict no='045-5' q='下面代码里，User 创建时打印的先后顺序是什么？' :options='["set_name uid 先于 init_subclass User", "init_subclass User 先于 set_name uid", "两者都不打印"]' answer='0' output='set_name uid\ninit_subclass User' explain='type.__new__ 先执行 type_new_set_names 回调 __set_name__，再执行 type_new_init_subclass 通知基类；两者都在 __new__ 内，且都早于元类 __init__。' />

<FillBlank no='045-6' tpl='___ __new__(mcls, name, bases, ns):' :answers='["def"]' hint='回想本讲关于 类也是对象 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 类也是对象：type 的三参数形式与默认元类 的落点。' />

<KnowledgeCard :points='["类是 type 的实例；type(name, bases, ns) 三参数形式与 class 语句等价", "类创建顺序：__prepare__ → 类体 → __new__ → __set_name__/__init_subclass__ → __init__", "__new__ 可改 bases 与 namespace 且必须 return 类对象；__init__ 时类已定型", "__set_name__(owner, name) 与 __init_subclass__(**kw) 都是 3.6 / PEP 487 的 type.__new__ 内回调", "元类冲突需新建继承所有相关元类的合并元类；零参 super() 依赖 __class__ cell", "登记/校验优先 __init_subclass__，加方法优先类装饰器，只有改创建输入才用元类"]' :pitfalls='["元类 __new__ 里漏写 return super().__new__(...)", "把字段收集或校验放进元类 __init__，结果与声明顺序不符", "同时继承两个带不同自定义元类的基类", "在元类里做重逻辑会让 IDE、类型检查器与调试器全部失去线索"]' summary='元类控制的是「类如何被创建」，而不是实例如何被创建；绝大多数需求用类装饰器或 __init_subclass__ 就能更清楚地解决' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 类是 type 的实例；type(name, bases, ns) 三参数形式与 class 语句等价 | 建立直觉 |
| 类创建顺序：__prepare__ → 类体 → __new__ → __set_name__/__init_subclass__ → __init__ | 跑通示例 |
| __new__ 可改 bases 与 namespace 且必须 return 类对象；__init__ 时类已定型 | 深入边界 |
| __set_name__(owner, name) 与 __init_subclass__(**kw) 都是 3.6 / PEP 487 的 type.__new__ 内回调 | 工程落地 |
| 元类冲突需新建继承所有相关元类的合并元类；零参 super() 依赖 __class__ cell | 随堂检测 |
| 登记/校验优先 __init_subclass__，加方法优先类装饰器，只有改创建输入才用元类 | 复盘 |

1. 类是 type 的实例；type(name, bases, ns) 三参数形式与 class 语句等价

2. 类创建顺序：__prepare__ → 类体 → __new__ → __set_name__/__init_subclass__ → __init__

3. __new__ 可改 bases 与 namespace 且必须 return 类对象；__init__ 时类已定型

[下一讲：反射与自省：getattr、inspect 与 __dict__](/oop/introspection)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/045-metaclass.py`

```bash
python3 examples/lessons/045-metaclass.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/045-metaclass.py) · [全部示例代码索引](/examples/)
