---
title: 第 040 讲 · 访问控制、property 与描述符协议
description: 掌握属性访问的底层协议
---

<StageHeader stage='L4 · 面向对象' level='★★★★☆' time='40 分钟' goal='掌握属性访问的底层协议' prereq='第 039 讲 · 属性查找、MRO 与 super' />

# 第 040 讲 · 访问控制、property 与描述符协议

理清查找顺序，还差一层：访问控制若只靠下划线，或把校验写死在 `__init__` 里，一句赋值就绕了过去。描述符协议道出了 `property` 与类方法为何是同一套机制：在 `__init__` 里校验过年龄非负，别处一次赋值却改出负数；把校验拆进 `getter` 和 `setter`，字段一多就得复制。

先从名称改写谈起，看清「私有」只是约定；再借 `property` 引出 `__get__` / `__set__` 协议，区分数据描述符与非数据描述符；最后按优先级写个校验字段，做到一处定义、处处生效。接着类与实例、属性查找两讲往下走；学完你能解释校验为何该写进 `setter`，也为特殊方法留个入口。


## user.age = -1 绕过了所有校验

一个 `User` 类在 `__init__` 里校验 `age` 必须是非负整数，上线后发现 `age` 字段仍出现负数——别处直接写 `user.age = -1` 就绕过了 `__init__` 的校验，而 `__init__` 只在创建时跑一次。

有人改成把属性藏成 `_age` 再加一对 `getter` / `setter`，校验逻辑散落在两个方法里，加新字段时又得复制一遍。更根本的困惑是：`property`、`method`、`classmethod`、`staticmethod` 看起来毫不相干，凭什么说它们是同一套机制？

还有人以为双下划线开头就是真私有，结果外部照样能改到内部状态。本讲把描述符协议讲透：`__get__` / `__set__` / `__delete__` / `__set_name__`、数据描述符与非数据描述符的优先级、名称改写的真实边界，并用一个可复用的校验字段描述符，把「一处定义、全局生效」落地。

<Callout type="warn" title='先看一个真实会出错的写法' text='校验写在 __init__ 里，后续 user.age = -1 绕过校验：__init__ 只在创建时跑一次，直接赋值走 object.__setattr__ 不经过它' />


## 属性访问协议的版图

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 039 讲 · 属性查找、MRO 与 super |
| 难度 / 建议时长 | ★★★★☆ · 40 分钟 |
| 本讲新增 | 名称改写与私有约定、property 的 getter / setter、数据描述符与非数据描述符 |
| 一句话目标 | 掌握属性访问的底层协议 |
| 为下一讲铺垫 | 特殊方法：repr、比较、算术与容器协议 |

<CheckList id='P040a' title='学完你应当能' :items='["能讲清 名称改写与私有约定", "能讲清 property 与描述符协议", "能讲清 优先级规则与自定义描述符", "能在工程里处理 __set_name__"]' />

<ConceptDiagram type='layers3' title='第 040 讲 · 分层视角' labels='名称改写与私有约定|property 与描述符协议|优先级规则与自定义描述符|__set_name__' caption='优先级规则与自定义描述符' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 `__set_name__` 落在哪一层。


## 名称改写与私有约定

单下划线 `_name` 只是约定，提示内部使用，不影响访问；

`from module import *` 默认不导入以 `_` 开头的名字，除非模块定义了 `__all__` 把它们列进去。

双下划线前缀且最多一个尾部下划线的名字（如 `__x`、`__x_`，但 `__x__` 不算）会被名称改写：编译器在编译类体时把它重写成 `_ClassName__x`，并写进 code object 的 `co_names` 与常量，用 `dis` 能看到改写后的属性名。

改写的真实目的是避免子类意外覆盖父类的内部名，不是访问控制——外部仍可通过 `_ClassName__x` 这个真实键访问，`obj.__dict__` 与 `dir(obj)` 都看得到。这条规则只在类体内生效：在类外写 `obj.__x` 不会改写，自然也访问不到改写后的键；

`__x__` 这种前后双下划线的 dunder 名完全不改写，留给语言的特殊方法使用。理解编译期改写，才能解释为什么继承体系里两个同名的 `__x` 互不干扰，也才能明白所谓「私有」其实只是命名约定。

```python
class User:
    def __init__(self, age):
        self.__secret = 7
        self.age = age
    @property
    def age(self):
        return self._age
    @age.setter
    def age(self, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError('age must be non-negative int')
        self._age = value

u = User(18)
print(u.age, '_User__secret' in u.__dict__)
try:
    u.age = -1
except ValueError as e:
    print(type(e).__name__, str(e))
print(u.age)
print(type(User.__dict__['age']).__name__)
print(isinstance(User.__dict__['age'], property))
```

<OutputBox title='主示例运行结果' output='18 True\nValueError age must be non-negative int\n18\nproperty\nTrue' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class User:\n    def __init__(self, age):\n        self.__secret = 7\n        self.age = age\n    @property\n    def age(self):\n        return self._age\n    @age.setter\n    def age(self, value):\n        if not isinstance(value, int) or value &lt; 0:\n            raise ValueError(&#39;age must be non-negative int&#39;)\n        self._age = value\n\nu = User(18)\nprint(u.age, &#39;_User__secret&#39; in u.__dict__)\ntry:\n    u.age = -1\nexcept ValueError as e:\n    print(type(e).__name__, str(e))\nprint(u.age)\nprint(type(User.__dict__[&#39;age&#39;]).__name__)\nprint(isinstance(User.__dict__[&#39;age&#39;], property))' :notes='["定义 User 类，演示校验与名称改写", "构造器接收初始年龄", "双下划线名在类体内被改写为 _User__secret", "self.age 赋值会触发 property 的 setter 校验", "@property 把 age 变成数据描述符的 getter", "getter 返回私有存储里的值", "从 _age 读出，避免再次触发描述符", "@age.setter 生成带 fset 的新 property", "setter 接收待赋的值", "校验类型与非负约束", "不满足就抛 ValueError，赋值不会被写入", "校验通过后写进实例字典", "空行，只用于分隔逻辑块，不影响执行结果。", "创建实例，__init__ 内部已走一次 setter", "年龄可读，改写后的键确实在实例字典里", "准备捕获非法赋值", "直接赋 -1，绕过 __init__ 但仍经过 setter", "捕获预期的 ValueError", "打印异常类型与消息", "非法值未写入，age 仍是 18", "类字典里的 age 是一个 property 对象", "isinstance 确认它确实是 property"]' title='第 040 讲 · 访问控制、property 与描述符协议' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**命名约定与名称改写**

| 写法 | 真实行为 | 边界 |
| --- | --- | --- |
| _name | 约定为内部使用，不改写 | from m import * 默认不导入，除非 __all__ 列出 |
| __name（至多一个尾部下划线） | 编译期改写为 _ClassName__name | 目的是防子类覆盖，不是访问控制 |
| __name__ | 不改写，留给特殊方法 | dunder 名由语言使用 |
| 类外 obj.__x | 不改写，访问不到改写后的键 | 要看真实键用 obj.__dict__ 或 dir |


### _Class__name 是怎么改写的

```python
import dis

class C:
    __hidden = 1
    def m(self):
        return self.__hidden
    @property
    def p(self):
        return 1

p = C.__dict__['p']
m = C.__dict__['m']
print(hasattr(p, '__set__'), hasattr(p, '__get__'))
print(hasattr(m, '__set__'), hasattr(m, '__get__'))
print('_C__hidden' in C.__dict__)
print([n for n in C.__dict__ if 'hidden' in n])
ops = [i.argval for i in dis.get_instructions(C.m)]
print('_C__hidden' in ops)
```

<OutputBox title='原理验证' output='True True\nFalse True\nTrue\n[&#39;_C__hidden&#39;]\nTrue' />


## property 与描述符协议

描述符协议由三个方法构成：`__get__`、`__set__(self, obj, value)`、`__delete__(self, obj)`。

```python
__get__(self, obj, objtype=None)
```

一个对象只要实现了其中任意一个就是描述符，而且必须作为类属性才生效，放进实例字典不会触发分派。数据描述符是实现 `__set__` 或 `__delete__` 的描述符（哪怕只实现其一），非数据描述符只实现 `__get__`。

`property` 是典型的数据描述符：`@property` 生成带 `fget` 的 `getter`，`@x.setter` 用新 `fset` 构造一个新的 `property`，`@x.deleter` 同理；

只读 `property` 赋值会抛 `AttributeError…`。

```text
AttributeError: property 'x' of 'C' object has no setter
```

校验必须写在 `setter` 里，因为 `property` 是数据描述符、优先于实例 `__dict__`，每次赋值都会经过同一入口，写在 `__init__` 里的校验则会被后续直接赋值绕过。

`__set_name__`（3.6+）在类创建时由 `type.__new__` 自动对每个描述符调用一次，把字段名告诉它，省去手写 `name` 参数，`ORM` 字段与 `dataclass` 大量依赖它。

```python
__set_name__(self, owner, name)
```

```python
class Checked:
    def __set_name__(self, owner, name):
        self.name = name
        self.key = '_' + name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.key)
    def __set__(self, obj, value):
        if value < 0:
            raise ValueError('negative')
        obj.__dict__[self.key] = value

class Loose:
    def __get__(self, obj, objtype=None):
        return 'loose'

class Item:
    price = Checked()
    tag = Loose()
    def __init__(self, price):
        self.price = price

it = Item(10)
print(it.price, Item.price.name, Item.price.key)
it.tag = 'mine'
print(it.tag, 'tag' in it.__dict__)
try:
    it.price = -5
except ValueError as e:
    print(type(e).__name__, str(e))
```

<OutputBox title='对照写法：先自己猜，再点开' output='10 price _price\nmine True\nValueError negative' guess="true" />


### getter / setter 如何落到描述符方法

<Term word='名称改写与私有约定' text='单下划线 `_name` 只是约定，提示内部使用，不影响访问；`from module import *` 默认不导入以 `_` 开头的名字，除非模块定义了 `__all__` 把它们列进去。双下划线前缀且最多一个尾部下划线的名字（如 `__x`、`__x_`，但 `__x__` 不算）会被名称改写：编译器在编译类体时…' />

<Term word='property 的 getter / setter' text='描述符协议由三个方法构成：`__get__(self, obj, objtype=None)`、`__set__(self, obj, value)`、`__delete__(self, obj)`。一个对象只要实现了其中任意一个就是描述符，而且必须作为类属性才生效，放进实例字典不会触发分派。数据描述符是实现…' />


## 数据描述符与非数据描述符

**数据描述符与非数据描述符**

| 类别 | 实现的方法 | 优先级 | 实例 |
| --- | --- | --- | --- |
| 数据描述符 | __set__ 或 __delete__（含 __get__） | 优先于实例 __dict__ | property、__slots__ 槽、自定义带 __set__ 的描述符 |
| 非数据描述符 | 只有 __get__ | 被实例 __dict__ 同名键遮蔽 | function、staticmethod、cached_property |
| __set_name__(owner, name) | 3.6+ 类创建时自动调用 | 把字段名交给描述符 | ORM 字段、校验字段 |
| __get__(obj, objtype) | obj 为 None 表示类访问 | 类访问通常返回描述符自身 | Class.field |

<Compare :panels='[{"label": "主示例", "code": "class User:\n    def __init__(self, age):\n        self.__secret = 7\n        self.age = age\n    @property\n    def age(self):\n        return self._age\n    @age.setter\n    def age(self, value):\n        if not isinstance(value, int) or value &lt; 0:\n            raise ValueError(&#39;age must be non-negative int&#39;)\n        self._age = value\n\nu = User(18)\nprint(u.age, &#39;_User__secret&#39; in u.__dict__)\ntry:\n    u.age = -1\nexcept ValueError as e:\n    print(type(e).__name__, str(e))\nprint(u.age)\nprint(type(User.__dict__[&#39;age&#39;]).__name__)\nprint(isinstance(User.__dict__[&#39;age&#39;], property))", "note": "名称改写与私有约定"}, {"label": "对照 / 进阶", "code": "class Checked:\n    def __set_name__(self, owner, name):\n        self.name = name\n        self.key = &#39;_&#39; + name\n    def __get__(self, obj, objtype=None):\n        if obj is None:\n            return self\n        return obj.__dict__.get(self.key)\n    def __set__(self, obj, value):\n        if value &lt; 0:\n            raise ValueError(&#39;negative&#39;)\n        obj.__dict__[self.key] = value\n\nclass Loose:\n    def __get__(self, obj, objtype=None):\n        return &#39;loose&#39;\n\nclass Item:\n    price = Checked()\n    tag = Loose()\n    def __init__(self, price):\n        self.price = price\n\nit = Item(10)\nprint(it.price, Item.price.name, Item.price.key)\nit.tag = &#39;mine&#39;\nprint(it.tag, &#39;tag&#39; in it.__dict__)\ntry:\n    it.price = -5\nexcept ValueError as e:\n    print(type(e).__name__, str(e))", "note": "property 与描述符协议"}]' title='两种写法对照' note='差异集中在 名称改写与私有约定；先看输出，再找背后的规则。' />

<Callout type="tip" title='核心心智模型' text='单下划线 `_name` 只是约定，提示内部使用，不影响访问；`from module import *` 默认不导入以 `_` 开头的名字，除非模块定义了 `__all__` 把它们列进去。双下划线前缀且最多一个尾部下划线的名字（如 `__x`、`__x_`，但 `__x__` 不算）会被名称改写…' />


## 底层：__getattribute__ 里的描述符分派

描述符协议是 CPython 属性访问的统一钩子。

任何类属性对象只要实现了 `__get__`、`__set__`、`__delete__` 之一，`object.__getattribute__` 查到它时就会分派：若它是数据描述符（有 `__set__` 或 `__delete__`），优先调用 `__get__(obj, type(obj))`，连 `obj.__dict__` 里的同名键都不看；

若是非数据描述符（只有 `__get__`），则先让实例字典有机会。

`object.__setattr__` 同样先看数据描述符的 `__set__`，因此 `property` 的 `setter` 能拦住每一次赋值，而 `__init__` 里写死的校验会在后续直接赋值时被绕过。

`property` 本身是 C 实现的数据描述符，`@x.setter` 会构造一个新的 `property` 把 `fset` 换进去；只读 `property` 的 `__set__` 存在却没有 `fset`，赋值时抛 `AttributeError`。

名称改写是编译期行为：编译器把类体内 `__x` 的每次引用重写成 `_ClassName__x`，并写进 code object 的 `co_names` 与常量，用 `dis` 能看到改写后的属性名。

`__set_name__` 由 `type.__new__` 在类创建时对每个描述符调用一次，把字段名注入，让 `ORM` 字段无需重复声明名字。`classmethod` 与 `staticmethod` 也都是描述符：前者 `__get__` 绑定 `cls`，后者 `__get__` 原样返回函数。

<ArchBlueprint title='第 040 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "名称改写与私有约定", "protocol": "调用 / 请求", "items": [{"label": "名称改写与私有约定", "sub": "输入与前置", "detail": "单下划线 `_name` 只是约定，提示内部使用，不影响访问；`from module import *` 默认不导入以 `_` 开头的名字，除非模块定义了 `__all__` 把它们列进去。双下划线前缀且最多一个尾部下划线的名字（如 `__x`、`__x_`，但 `__x__` 不算）会被名称改写…", "tone": "blue"}]}, {"name": "核心规则", "note": "property 与描述符协议", "protocol": "语言 / 运行时协议", "items": [{"label": "property 与描述…", "sub": "状态与边界", "detail": "描述符协议由三个方法构成：`__get__(self, obj, objtype=None)`、`__set__(self, obj, value)`、`__delete__(self, obj)`。一个对象只要实现了其中任意一个就是描述符，而且必须作为类属性才生效，放进实例字典不会触发分派。数据描…", "tone": "purple"}]}, {"name": "落地与收尾", "note": "优先级规则与自定义描述符", "items": [{"label": "优先级规则与自定义描述符", "sub": "工程处理", "detail": "`object.__getattribute__` 的完整优先级是：数据描述符 → 实例 `__dict__` → 非数据描述符 → 类属性 → 全失败后才调用 `__getattr__`；`object.__setattr__` 里数据描述符的 `__set__` 也优先于写入实例字典，而非数据描…", "tone": "green"}]}]' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：校验写在 __init__ 里，后续 use…", "body": "__init__ 只在创建时跑一次，直接赋值走 object.__setattr__ 不经过它", "tip": "用 property 的 setter 或自定义数据描述符，把校验放进 __set__，保证每次赋值都过同一入口"}, {"title": "第 2 步：自定义描述符忘了实现 __set__，校验被…", "body": "只实现 __get__ 的是非数据描述符，优先级低于实例 __dict__，obj.x = v 直接写进字典", "tip": "实现 __set__（或 __delete__）让它成为数据描述符；__get__ 里读写 obj.__dict__[key] 避免递归"}, {"title": "第 3 步：以为双下划线是真私有，外部仍改到了内部状态", "body": "名称改写只是编译期把 __x 改成 _ClassName__x，不是访问控制", "tip": "按约定用单下划线表达内部；确需隔离靠 property / 描述符与文档约束"}]' />


## 优先级规则与自定义描述符

`object.__getattribute__` 的完整优先级是：数据描述符 → 实例 `__dict__` → 非数据描述符 → 类属性 → 全失败后才调用 `__getattr__`；

`object.__setattr__` 里数据描述符的 `__set__` 也优先于写入实例字典，而非数据描述符会被实例同名键覆盖。

据此可以写一个可复用的校验字段：`__set_name__` 记录 `name` 与存储键，`__get__` 从 `obj.__dict__` 读，`__set__` 先校验类型与范围再写回，一处定义让所有用了它的字段自动获得校验。

常见失效信号有三个：把描述符实例赋给实例属性（`obj.x = descriptor`）不生效，因为它不在类上；

忘了实现 `__set__` 就退化成非数据描述符，校验会被实例字典绕过；

`__get__` 里若访问 `obj.name` 又会触发描述符本身，造成无限递归，应读写 `obj.__dict__[key]`。

典型应用包括 `ORM` 字段、配置校验、懒加载属性（`cached_property` 正是非数据描述符）与类型约束；

`classmethod` 与 `staticmethod` 也由描述符实现，前者 `__get__` 绑定 `cls`、后者原样返回函数。`__slots__` 生成的槽本身也是数据描述符。

**属性访问优先级与失效信号**

| 场景 | 结果 | 原因 / 修复 |
| --- | --- | --- |
| 数据描述符 vs 实例字典 | 数据描述符胜出 | object.__getattribute__ 先查数据描述符 |
| 非数据描述符 vs 实例同名键 | 实例字典胜出 | 忘写 __set__ 会让校验被绕过 |
| 只读 property 赋值 | AttributeError: property 'x' of 'C' object has no setter | property 有 __set__ 但无 fset，赋新值时报错 |
| 把描述符放进实例字典 | 不生效 | 描述符必须作为类属性 |
| __get__ 里访问 obj.name 递归 | 无限递归 | 应读写 obj.__dict__[key] 或 super().__getattribute__ |


### 数据描述符为何压过实例字典

<Predict no='040-1' q='class C 里 @property def p；print(hasattr(C.__dict__[&#39;p&#39;], &#39;__set__&#39;), hasattr(C.__dict__[&#39;p&#39;], &#39;__get__&#39;)) 输出什么？' :options='["True True", "False True", "True False"]' answer='0' output='True True' explain='property 是数据描述符，同时实现 __get__ 与 __set__；即使是只读 property，__set__ 方法依旧存在，只是赋值时会抛 AttributeError。' />


## 从命名约定到描述符的版本演进

<FlowTimeline :steps='[{"title": "名称改写与私有约定", "desc": "单下划线 `_name` 只是约定，提示内部使用，不影响访问…", "tone": "blue"}, {"title": "property 与描述符协议", "desc": "描述符协议由三个方法构成…", "tone": "purple"}, {"title": "优先级规则与自定义描述符", "desc": "`object.__getattribute__` 的完整优先级是：数据描述符…", "tone": "orange"}, {"title": "工程落地", "desc": "可复用的校验字段描述符：一个 ORM 雏形", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

```bash
python -c "from collections.abc import Sized; print(isinstance([1], Sized))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 名称改写与私有约定 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 可复用的校验字段描述符：一个 ORM 雏形

一个商品模型需要 `price` 为浮点且非负、`stock` 为整数且非负，若在每个 `setter` 里各写一遍校验，字段一多就重复且容易漏。

正确做法是把校验逻辑收进一个 `Field` 描述符：`__init__` 收目标类型与下限，`__set_name__` 在类创建时自动拿到字段名并算出存储键，`__get__` 从实例字典读，`__set__` 先校验类型与范围再写入。

因为实现了 `__set__`，它是数据描述符，每次赋值都经过同一入口，`__init__` 里的第一次赋值也不例外。下面用标准库实现一个最小 `ORM` 雏形，演示正常构造、类上访问描述符拿到字段名，以及两类非法赋值分别抛 `ValueError` 与 `TypeError`。

真实项目还会在此基础上加默认值、必填标记与数据库列名映射。

```python
class Field:
    def __init__(self, typ, minimum=None):
        self.typ = typ
        self.minimum = minimum
    def __set_name__(self, owner, name):
        self.name = name
        self.key = '_' + name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.key)
    def __set__(self, obj, value):
        if not isinstance(value, self.typ):
            raise TypeError('bad type for ' + self.name)
        if self.minimum is not None and value < self.minimum:
            raise ValueError('too small for ' + self.name)
        obj.__dict__[self.key] = value

class Product:
    price = Field(float, minimum=0.0)
    stock = Field(int, minimum=0)
    def __init__(self, price, stock):
        self.price = price
        self.stock = stock

p = Product(9.9, 5)
print(p.price, p.stock, Product.price.name)
for attr, val in [('price', -1.0), ('stock', 'x')]:
    try:
        setattr(p, attr, val)
    except (TypeError, ValueError) as e:
        print(type(e).__name__, str(e))
```

<Callout type="idea" title='落地提示' text='ORM 字段、配置校验、懒加载属性、类型约束都适合用描述符实现，一处定义全局生效' />

<CheckList id='P040b' title='上线前自检' :items='["能复现并解释「校验写在 __init__ 里，后续 user.age =…」", "能复现并解释「自定义描述符忘了实现 __set__，校验被实例字典绕过」", "能复现并解释「以为双下划线是真私有，外部仍改到了内部状态」", "能用一条命令验证 名称改写与私有约定", "关键路径有自动化测试与失败分支"]' />


## 校验写在 __init__、__set__ 缺失与假私有

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 校验写在 __init__ 里，后续 user.age = -1 绕过校验 | __init__ 只在创建时跑一次，直接赋值走 object.__setattr__ 不经过它 | 用 property 的 setter 或自定义数据描述符，把校验放进 __set__，保证每次赋值都过同一入口 |
| 自定义描述符忘了实现 __set__，校验被实例字典绕过 | 只实现 __get__ 的是非数据描述符，优先级低于实例 __dict__，obj.x = v 直接写进字典 | 实现 __set__（或 __delete__）让它成为数据描述符；__get__ 里读写 obj.__dict__[key] 避免递归 |
| 以为双下划线是真私有，外部仍改到了内部状态 | 名称改写只是编译期把 __x 改成 _ClassName__x，不是访问控制 | 按约定用单下划线表达内部；确需隔离靠 property / 描述符与文档约束 |

<Callout type="warn" title='本讲最容易踩的坑' text='校验写在 __init__ 里，后续 user.age = -1 绕过校验：__init__ 只在创建时跑一次，直接赋值走 object.__setattr__ 不经过它' />


## 描述符练习与速记

<Exercise title='基础：用 property setter 做校验' task='定义一个带 @property 与 @x.setter 的类，setter 里拒绝负数；正常赋值后打印，再赋负值捕获异常。' solution='class C:\n    @property\n    def x(self):\n        return self._x\n    @x.setter\n    def x(self, v):\n        if v &lt; 0:\n            raise ValueError(&#39;neg&#39;)\n        self._x = v\n\nc = C()\nc.x = 5\nprint(c.x)\ntry:\n    c.x = -1\nexcept ValueError as e:\n    print(type(e).__name__, str(e))' explain='property 是数据描述符，setter 拦住每一次赋值；校验写在 __init__ 则会被后续直接赋值绕过。' />

<Exercise title='进阶：自定义描述符加 __set_name__' task='实现一个描述符，__set_name__ 记录存储键，__get__/__set__ 读写 obj.__dict__ 且 __set__ 把值翻倍，验证类访问返回描述符自身。' solution='class D:\n    def __set_name__(self, owner, name):\n        self.key = &#39;_&#39; + name\n    def __get__(self, obj, objtype=None):\n        return self if obj is None else obj.__dict__.get(self.key)\n    def __set__(self, obj, value):\n        obj.__dict__[self.key] = value * 2\n\nclass C:\n    v = D()\nc = C()\nc.v = 3\nprint(c.v, C.v.key)' explain='__set_name__ 在类创建时把字段名注入；__get__ 里 obj 为 None 表示类访问，应返回描述符自身；__set__ 让它成为数据描述符。' />

<Quiz no='040-2' q='把 __x 写在类体里，编译器会怎么处理？' :options='["改写为 _ClassName__x，防子类意外覆盖而非访问控制", "加密存储，禁止外部访问", "自动生成一个 property", "原样保留，完全不变"]' answer="0" explain='名称改写是编译期行为，把类体内的 __x 重写成 _ClassName__x 并写进 co_names；目的是避免子类覆盖，不是真正的私有。' />

<Quiz no='040-3' q='数据描述符与非数据描述符的区别是？' :options='["实现 __set__ 或 __delete__ 的是数据描述符，优先于实例 __dict__", "实现 __get__ 的就是数据描述符", "两者优先级完全相同", "定义在类里的都是数据描述符"]' answer="0" explain='object.__getattribute__ 让数据描述符优先于实例字典；只实现 __get__ 的非数据描述符会被实例同名键遮蔽。' />

<Quiz no='040-4' q='__set_name__ 在什么时候被调用？' :options='["类创建时由 type.__new__ 对每个描述符自动调用一次", "每次访问属性时", "每个实例创建时", "必须手动调用才触发"]' answer="0" explain='3.6 起类创建阶段自动把字段名传给描述符，ORM 字段因此无需在声明里重复写名字。' />

<FillBlank no='040-5' tpl='___ __init__(self, age):' :answers='["def"]' hint='回想本讲关于 名称改写与私有约定 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 名称改写与私有约定 的落点。' />

<KnowledgeCard :points='["双下划线前缀名在类体内被编译期改写为 _ClassName__x，防子类覆盖而非私有；dunder 名不改写", "描述符协议 __get__ / __set__ / __delete__；实现 __set__ 或 __delete__ 的是数据描述符，优先于实例 __dict__", "property 是数据描述符，setter 保证每次赋值都过同一入口；只读赋值抛 AttributeError: ... has no setter", "__set_name__(owner, name)（3.6+）在类创建时自动调用，把字段名注入描述符", "优先级：数据描述符 &gt; 实例 __dict__ &gt; 非数据描述符 &gt; 类属性 &gt; __getattr__；function / staticmethod / cached_property 是非数据描述符", "自定义描述符要作类属性、__get__ 里读写 obj.__dict__[key] 避免递归；ORM 字段、配置校验、懒加载都用它"]' :pitfalls='["校验写在 __init__ 里，后续 user.age = -1 绕过校验", "自定义描述符忘了实现 __set__，校验被实例字典绕过", "以为双下划线是真私有，外部仍改到了内部状态", "把校验写在 __init__ 里，后续赋值就绕过了校验；数据描述符才能保证每次赋值都经过同一入口"]' summary='描述符是 Python 里最被低估的机制：property、method、classmethod、staticmethod 全部由它实现，实例属性查找优先级也由它决定' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 双下划线前缀名在类体内被编译期改写为 _ClassName__x，防子类覆盖而非私有；dunder 名不改写 | 建立直觉 |
| 描述符协议 __get__ / __set__ / __delete__；实现 __set__ 或 __delete__ 的是数据描述符，优先于实例 __dict__ | 跑通示例 |
| property 是数据描述符，setter 保证每次赋值都过同一入口；只读赋值抛 AttributeError: ... has no setter | 深入边界 |
| __set_name__(owner, name)（3.6+）在类创建时自动调用，把字段名注入描述符 | 工程落地 |
| 优先级：数据描述符 > 实例 __dict__ > 非数据描述符 > 类属性 > __getattr__；function / staticmethod / cached_property 是非数据描述符 | 随堂检测 |
| 自定义描述符要作类属性、__get__ 里读写 obj.__dict__[key] 避免递归；ORM 字段、配置校验、懒加载都用它 | 复盘 |

1. 双下划线前缀名在类体内被编译期改写为 _ClassName__x，防子类覆盖而非私有；dunder 名不改写

2. 描述符协议 __get__ / __set__ / __delete__；实现 __set__ 或 __delete__ 的是数据描述符，优先于实例 __dict__

3. property 是数据描述符，setter 保证每次赋值都过同一入口；只读赋值抛 AttributeError: ... has no setter

[下一讲：特殊方法：repr、比较、算术与容器协议](/oop/special-methods)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/040-property.py`

```bash
python3 examples/lessons/040-property.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/040-property.py) · [全部示例代码索引](/examples/)
