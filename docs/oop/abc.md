---
title: 第 044 讲 · 鸭子类型、抽象基类与 Protocol
description: 在灵活与契约之间做出正确取舍
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='35 分钟' goal='在灵活与契约之间做出正确取舍' prereq='第 043 讲 · __slots__、弱引用与对象内存布局' />

# 第 044 讲 · 鸭子类型、抽象基类与 Protocol

会写类、会定制类之后，问题从「一个类怎么样」变成「一群类之间怎么约定」。插件体系里常只关心对象有没有某个方法，不想强制它继承谁；Python 给了两条路：靠继承显式声明，或靠结构隐式匹配。

一个插件平台为让所有导出器都有 export，给十几个内部类型套了基类，层次多了三层却没复用实现，第三方对象更进不来。本讲先从鸭子类型与 EAFP 说起，再讲 abc.ABC 与 register 的边界，看 Protocol 怎样零侵入，最后比较运行时代价与选型。需要类与继承、阶段三的类型注解；学完你能对外部用最小需求描述接口，在框架内部用 ABC 复用实现。


## 插件接入时该信 isinstance 还是该信方法名

一个插件平台为了让「所有导出器都有 export 方法」，给十几个内部类型都套了一层抽象基类，结果继承树多出三层、默认实现却一个没复用，代码评审时没人说得清这层约束到底带来了什么。

另一边，接入第三方 SDK 的对象根本无法继承自家基类，于是有人用 `ABCMeta.register` 把它们注册成虚拟子类，注册后 isinstance 确实返回 True，调用 export 时却抛 AttributeError——register 只改类型判定，不会凭空长出方法。

还有团队把 `typing.Protocol` 当运行时校验用，对没加 @runtime_checkable 的 Protocol 直接 isinstance，得到 TypeError: Instance and class checks can only be used with @runtime_checkable protocols；

加了装饰器后又误以为它检查方法签名，结果一个签名完全不对的类被判合格。Python 里「契约」有两条完全不同的实现路径：ABC 靠继承显式声明，Protocol 靠结构隐式匹配。本讲把两条路径的判定机制、运行时代价与选型边界讲透。

<Callout type="warn" title='先看一个真实会出错的写法' text='为了规范给所有内部类型套一层 ABC：ABC 只在需要复用默认实现或强制补齐方法时才有收益，纯继承层次不增加任何运行时约束' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 043 讲 · __slots__、弱引用与对象内存布局 |
| 难度 / 建议时长 | ★★★☆☆ · 35 分钟 |
| 本讲新增 | 鸭子类型与 EAFP、abc.ABC 与 abstractmethod、虚拟子类 register |
| 一句话目标 | 在灵活与契约之间做出正确取舍 |
| 为下一讲铺垫 | 元类：__new__、type 与类创建过程 |


## ABC 与 Protocol 两条契约路径对照

**ABC 与 Protocol 两条契约路径对照**

| 维度 | abc.ABC / ABCMeta | typing.Protocol |
| --- | --- | --- |
| 判定依据 | 显式继承或 register 注册 | 结构上是否具备声明的成员 |
| 对第三方类型 | 需继承或 register，侵入 | 零侵入，天然兼容 |
| 默认运行时 isinstance | 支持（ABCMeta.__instancecheck__） | 不支持，需 @runtime_checkable |
| 运行时检查内容 | 真实类型关系 + 缓存 | 只做 hasattr 式成员名检查 |
| 能否提供默认实现 | 能，基类可写具体方法 | 不能，方法体通常是 ... |
| 主要作用层 | 运行时分派与复用 | 静态检查（mypy / pyright） |

<Callout type="tip" title='核心心智模型' text='Python 的默认风格是鸭子类型配 EAFP（Easier to Ask Forgiveness than Permission）：直接调用方法，失败再捕获 AttributeError/TypeError，而不是先做一串 LBYL 的 isinstance 检查。abc 模块提供的是显式契约：类' />


## 关键 API、版本与行为

**关键 API、版本与行为**

| API / 版本 | 行为 | 排查提示 |
| --- | --- | --- |
| abc.abstractmethod | 配合 ABCMeta 才写入 __abstractmethods__ | 标在普通类上不阻止实例化 |
| ABCMeta.register（长期可用） | 建虚拟子类，只改 issubclass/isinstance | 不继承方法体，调用前仍需兜底 |
| __subclasshook__ | 自定义 issubclass 逻辑，collections.abc 大量使用 | Sized 靠 __len__ 判定 |
| typing.Protocol（3.8 / PEP 544） | 结构化子类型，隐式匹配 | 类本身不可实例化，_is_protocol 为 True |
| @runtime_checkable | 开放 isinstance，仅查成员名 | 不校验签名与返回类型，别当校验器 |
| @dataclass 结合 Protocol | 注解不产生运行时约束 | 脏数据校验交给 pydantic |

<Term word='鸭子类型与 EAFP' text='Python 的默认风格是鸭子类型配 EAFP（Easier to Ask Forgiveness than Permission）：直接调用方法，失败再捕获 AttributeError/TypeError，而不是先做一串 LBYL 的 isinstance 检查。abc 模块提供的是显式契约：类继承 abc.ABC' />

<Term word='abc.ABC 与 abstractmethod' text='typing.Protocol（PEP 544，3.8 引入）表达的是结构化子类型：一个类只要结构上具备 Protocol 声明的成员，静态检查器就认为它兼容，完全不需要继承或注册，对第三方类型零侵入。Protocol 类本身带 _is_protocol = True，且不可实例化（直接调用抛 TypeError: P' />


## 鸭子类型、EAFP 与 ABC 的显式契约

Python 的默认风格是鸭子类型配 EAFP（Easier to Ask Forgiveness than Permission）：直接调用方法，失败再捕获 AttributeError/TypeError，而不是先做一串 LBYL 的 isinstance 检查。

abc 模块提供的是显式契约：类继承 `abc.ABC`（其元类是 ABCMeta）并用 @abstractmethod 标记方法，`type.__new__` 会把这些方法名收进 `__abstractmethods__`（frozenset），实例化时解释器检查该集合非空就抛 TypeError: Can't instantiate abstract class。

关键细节：@abstractmethod 只有配合 ABCMeta 才生效，标在普通类上只是给函数加了个 `__isabstractmethod__` 标记，类仍可实例化。

ABC 的真正价值是「复用」——在基类里写公共方法与默认实现，子类只补抽象方法；若只是为了「规范」给每个内部类型套一层，只增加层次不增加约束。

`ABCMeta.register(SomeClass)` 建立虚拟子类：issubclass/isinstance 立刻返回 True，但被注册类不继承任何方法体，也不校验它是否真的有那些方法，所以调用前仍要自己兜底。

`collections.abc` 里的 Sized、Iterable 等大量用 `__subclasshook__` 做结构化判定：只要类实现了 `__len__` 就被认作 Sized，无需继承。

```python
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

class Reader(ABC):
    @abstractmethod
    def read(self):
        pass
class FileReader(Reader):
    def read(self):
        return 'file-data'

try:
    Reader()
except TypeError as e:
    print(type(e).__name__, 'abstract')
print('isinstance', isinstance(FileReader(), Reader))

@runtime_checkable
class HasRead(Protocol):
    def read(self) -> str:
        ...
class Duck:
    def read(self):
        return 'duck-data'
print('protocol isinstance', isinstance(Duck(), HasRead))
Reader.register(Duck)
print('registered', isinstance(Duck(), Reader), 'has read:', hasattr(Duck(), 'read'))
```

<OutputBox title='主示例运行结果' output='TypeError abstract\nisinstance True\nprotocol isinstance True\nregistered True has read: True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from abc import ABC, abstractmethod\nfrom typing import Protocol, runtime_checkable\n\nclass Reader(ABC):\n    @abstractmethod\n    def read(self):\n        pass\nclass FileReader(Reader):\n    def read(self):\n        return &#39;file-data&#39;\n\ntry:\n    Reader()\nexcept TypeError as e:\n    print(type(e).__name__, &#39;abstract&#39;)\nprint(&#39;isinstance&#39;, isinstance(FileReader(), Reader))\n\n@runtime_checkable\nclass HasRead(Protocol):\n    def read(self) -&gt; str:\n        ...\nclass Duck:\n    def read(self):\n        return &#39;duck-data&#39;\nprint(&#39;protocol isinstance&#39;, isinstance(Duck(), HasRead))\nReader.register(Duck)\nprint(&#39;registered&#39;, isinstance(Duck(), Reader), &#39;has read:&#39;, hasattr(Duck(), &#39;read&#39;))' :notes='["导入 ABC 与 abstractmethod，建立显式契约", "导入 Protocol 与 runtime_checkable，建立结构化契约", "继承 ABC，元类为 ABCMeta", "@abstractmethod 把方法名写入 __abstractmethods__", "声明抽象方法 read", "方法体用 pass 占位", "具体子类必须实现 read 才能实例化", "实现 read", "返回固定数据，便于后续 isinstance 验证", "尝试直接实例化含抽象方法的类", "Reader() 会触发实例化检查", "含抽象方法时抛 TypeError", "打印异常类型，避开版本相关的完整消息", "具体子类是 Reader 的实例，isinstance 为 True", "@runtime_checkable 让协议可用于 isinstance", "声明结构化协议，只要求有 read 成员", "方法签名带返回注解，注解仅静态期生效", "方法体用 Ellipsis 占位", "Duck 完全不继承 Reader", "但结构上实现了 read", "返回固定数据，供运行时判定", "runtime_checkable 按成员名判定，结构兼容返回 True", "把 Duck 注册成 Reader 的虚拟子类", "注册后 isinstance 为 True；Duck 本来就有 read，hasattr 为 True"]' title='第 044 讲 · 鸭子类型、抽象基类与 Protocol' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='compare2' title='第 044 讲 · 鸭子类型、EAFP 与 ABC 的显式契约' labels='鸭子类型、EAFP 与 ABC 的显式契约|Protocol 的结构化子类型与 runt|选型与运行时成本：两条契约各自落在哪一层' caption='在灵活与契约之间做出正确取舍' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## Protocol 的结构化子类型与 runtime_checkable 边界

`typing.Protocol`（PEP 544，3.8 引入）表达的是结构化子类型：一个类只要结构上具备 Protocol 声明的成员，静态检查器就认为它兼容，完全不需要继承或注册，对第三方类型零侵入。

Protocol 类本身带 `_is_protocol = True`，且不可实例化（直接调用抛 TypeError: Protocols cannot be instantiated）；

它的方法体通常写 ... 或加 @abstractmethod。默认情况下 Protocol 只作用于静态检查（mypy / pyright），不能用于 isinstance/issubclass；

加上 @`typing.runtime_checkable` 才把 `__instancecheck__` 换成运行时成员检查。

这个检查非常浅：它遍历协议声明的属性名做 hasattr 式判断，只确认名字存在，不调用方法、也不比对签名、不校验返回类型，因此一个 `export(self, x, y, z)` 的类也会被判为符合 `export(self, rows)`。

正因为如此，运行时用它做插件准入时必须再补一层：白名单注册表、显式调用探测，或直接让插件走真实调用并记录异常。泛型协议可写 Protocol`[T]` 约束成员类型，但这些注解同样只在静态期起作用。

```python
from abc import ABCMeta

class Meta(metaclass=ABCMeta):
    pass
class NoMethods:
    pass
Meta.register(NoMethods)
print('registered subclass:', issubclass(NoMethods, Meta))
print('has missing method:', hasattr(NoMethods(), 'read'))
try:
    NoMethods().read()
except AttributeError as e:
    print(type(e).__name__, 'no real method')
```

<OutputBox title='对照写法：先自己猜，再点开' output='registered subclass: True\nhas missing method: False\nAttributeError no real method' guess="true" />

```python
from abc import ABC, abstractmethod
from typing import Protocol
import inspect

class Reader(ABC):
    @abstractmethod
    def read(self):
        pass
print('abstractmethods:', Reader.__abstractmethods__)
print('metaclass:', type(Reader).__name__)
print('isabstract:', inspect.isabstract(Reader))

class PlainProtocol(Protocol):
    def read(self):
        ...
try:
    isinstance(object(), PlainProtocol)
except TypeError:
    print('TypeError needs runtime_checkable')
print('is_protocol:', PlainProtocol._is_protocol)
```

<OutputBox title='原理验证' output='abstractmethods: frozenset({&#39;read&#39;})\nmetaclass: ABCMeta\nisabstract: True\nTypeError needs runtime_checkable\nis_protocol: True' />


## 运行时检查的代价与失败信号

**运行时检查的代价与失败信号**

| 现象 | 根因 | 定位 / 修复 |
| --- | --- | --- |
| isinstance(obj, P) 抛 TypeError | Protocol 未加 @runtime_checkable | 加装饰器，或改用静态检查 |
| 签名不对的类被判兼容 | runtime_checkable 只做 hasattr 成员名检查 | 加白名单或真实调用探测 |
| register 后调用方法抛 AttributeError | 虚拟子类不继承方法体 | 改用继承，或调用前 hasattr 兜底 |
| ABC 实例化抛 TypeError | __abstractmethods__ 非空 | 实现全部抽象方法或去掉 @abstractmethod |
| isinstance 变慢 | ABCMeta 缓存未命中 / Protocol 成员多 | 缓存预热后复测，缩减协议成员 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：为了规范给所有内部类型套一层 ABC", "body": "ABC 只在需要复用默认实现或强制补齐方法时才有收益，纯继承层次不增加任何运行时约束", "tip": "内部类型直接用鸭子类型或 Protocol 描述最小需求；确需公共实现与 isinstance 分派时才引入 ABC"}, {"title": "第 2 步：用 register 让第三方类通过 isi", "body": "ABCMeta.register 只写 _abc_registry 改类型判定，不继承也不校验方法是否真实存在", "tip": "改用真实继承获得默认实现，或在调用前显式探测并捕获 AttributeError；register 仅用于让判定认识外部类型"}, {"title": "第 3 步：对未加 @runtime_checkable", "body": "默认协议只能静态检查；加了装饰器也只按成员名 hasattr 判定，不比对参数与返回类型", "tip": "需要运行时判定时加 @runtime_checkable，并补白名单或真实调用探测；签名一致性交给 mypy / pyright"}]' />


## 选型与运行时成本：两条契约各自落在哪一层

把选型落到具体问题：需要给一组自家类型提供公共实现、强制子类补齐方法、或做 isinstance 分派时，用 ABC；需要描述「对外部对象的最小需求」、允许任何第三方类型零改接入时，用 Protocol，尤其适合插件体系与回调接口。

ABC 的 isinstance 走 `ABCMeta.__instancecheck__`，结果会进 _abc_cache 与 _abc_negative_cache 的弱引用缓存，并遍历 _abc_registry，重复调用后接近常数，但比普通类型判定多一层 Python 逻辑；

Protocol 的运行时检查要遍历协议成员集合逐个 hasattr，成员多时代价线性增长。两者都不要当成数据校验器：类型注解与协议都不在实例化时拦脏数据，那是 pydantic 或显式校验的活（第 47 讲）。接口隔离同样重要：协议应只声明真正会调用的最小成员，声明越多、满足它的类型越少、运行时检查越慢。

实践里最常见的错是把 ABC 当命名空间、把 register 当继承、把 runtime_checkable 当签名校验；认清「ABC 管继承与复用、Protocol 管结构与静态描述、运行时检查只保证名字存在」，这三类误用就能一次性避开。

isinstance 与 issubclass 的入口是 PyObject_IsInstance / PyObject_IsSubclass，它们会优先调用类型（元类）上定义的 `__instancecheck__` / `__subclasscheck__` 钩子，而不是只比对 tp_base 链。

ABCMeta 重写了这两个方法：先查 _abc_cache（WeakSet）与 _abc_negative_cache 缓存，未命中再遍历 MRO 与 _abc_registry（register 写入的弱引用集合），并可调用 `__subclasshook__` 做结构化判定，结果写回缓存，因此重复检查接近常数。

Protocol 由 _ProtocolMeta（继承 ABCMeta）实现，@runtime_checkable 把 `__instancecheck__` 换成一个只遍历 `__protocol_attrs__` 做 hasattr 的轻量实现，成员存在即返回 True，完全不触碰签名对象。

PEP 544 的「结构化」发生在静态检查期：mypy 把类的成员集合与协议声明做集合包含判断，与运行时继承无关。

这解释了三个事实：普通类上的 abstractmethod 无效（没有 ABCMeta 计算 `__abstractmethods__`）、register 不产生方法体、runtime_checkable 会放过签名不符的类——三者分别落在元类钩子、继承语义与浅层成员检查上。

<Compare :panels='[{"label": "主示例", "code": "from abc import ABC, abstractmethod\nfrom typing import Protocol, runtime_checkable\n\nclass Reader(ABC):\n    @abstractmethod\n    def read(self):\n        pass\nclass FileReader(Reader):\n    def read(self):\n        return &#39;file-data&#39;\n\ntry:\n    Reader()\nexcept TypeError as e:\n    print(type(e).__name__, &#39;abstract&#39;)\nprint(&#39;isinstance&#39;, isinstance(FileReader(), Reader))\n\n@runtime_checkable\nclass HasRead(Protocol):\n    def read(self) -&gt; str:\n        ...\nclass Duck:\n    def read(self):\n        return &#39;duck-data&#39;\nprint(&#39;protocol isinstance&#39;, isinstance(Duck(), HasRead))\nReader.register(Duck)\nprint(&#39;registered&#39;, isinstance(Duck(), Reader), &#39;has read:&#39;, hasattr(Duck(), &#39;read&#39;))", "note": "鸭子类型、EAFP 与 ABC 的显式契约"}, {"label": "对照 / 进阶", "code": "from abc import ABCMeta\n\nclass Meta(metaclass=ABCMeta):\n    pass\nclass NoMethods:\n    pass\nMeta.register(NoMethods)\nprint(&#39;registered subclass:&#39;, issubclass(NoMethods, Meta))\nprint(&#39;has missing method:&#39;, hasattr(NoMethods(), &#39;read&#39;))\ntry:\n    NoMethods().read()\nexcept AttributeError as e:\n    print(type(e).__name__, &#39;no real method&#39;)", "note": "Protocol 的结构化子类型与 runtime_checkable 边界"}]' title='两种写法对照' note='差异集中在 鸭子类型与 EAFP；先看输出，再找背后的规则。' />


## 插件平台用 Protocol 描述最小接口并配白名单准入

报表平台允许各业务方提供导出器，平台既不能要求对方继承自家基类，也要防止把缺方法的对象注册进路由造成线上 AttributeError。用 Protocol 描述「只要有 `export(rows)` 就能用」这一最小需求，对第三方类型零侵入；

再配一张显式注册表做准入：注册时用 @runtime_checkable 的 isinstance 先做粗筛，通过后再由真实调用兜底，并把允许的名字收敛到白名单，避免反射任意方法。下面用标准库跑通：CsvExporter 结构合规被收录，Broken 只有 run 方法被拒绝，最后打印已注册插件与一次真实导出结果。

要点是 Protocol 负责描述结构、注册表负责收敛可调用集合、两者都不承担数据校验——脏数据要在 export 内部或边界层单独处理。

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Exporter(Protocol):
    def export(self, rows):
        ...

class CsvExporter:
    def export(self, rows):
        return ','.join(str(r) for r in rows)
class Broken:
    def run(self):
        return 0

registry = {}
def register(name, obj):
    if not isinstance(obj, Exporter):
        raise TypeError('missing export')
    registry[name] = obj

register('csv', CsvExporter())
try:
    register('bad', Broken())
except TypeError as e:
    print('rejected:', str(e))
print('registered:', sorted(registry))
print('output:', registry['csv'].export([1, 2, 3]))
```

<Callout type="idea" title='落地提示' text='对外部生态用 Protocol 描述最小需求，对框架内部用 ABC 提供默认实现与复用' />

<CheckList id='P044b' title='上线前自检' :items='["能复现并解释「为了规范给所有内部类型套一层 ABC」", "能复现并解释「用 register 让第三方类通过 isinstance 」", "能复现并解释「对未加 @runtime_checkable 的 Proto」", "能用一条命令验证 鸭子类型与 EAFP", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from collections.abc import Sized; print(isinstance([1], Sized))"
```

把输入换成你自己的数据，观察结果是否仍符合 **鸭子类型与 EAFP** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 为了规范给所有内部类型套一层 ABC | ABC 只在需要复用默认实现或强制补齐方法时才有收益，纯继承层次不增加任何运行时约束 | 内部类型直接用鸭子类型或 Protocol 描述最小需求；确需公共实现与 isinstance 分派时才引入 ABC |
| 用 register 让第三方类通过 isinstance 后直接调用方法 | ABCMeta.register 只写 _abc_registry 改类型判定，不继承也不校验方法是否真实存在 | 改用真实继承获得默认实现，或在调用前显式探测并捕获 AttributeError；register 仅用于让判定认识外部类型 |
| 对未加 @runtime_checkable 的 Protocol 用 isinstance，或把通过检查当成签名合规 | 默认协议只能静态检查；加了装饰器也只按成员名 hasattr 判定，不比对参数与返回类型 | 需要运行时判定时加 @runtime_checkable，并补白名单或真实调用探测；签名一致性交给 mypy / pyright |

<Callout type="warn" title='本讲最容易踩的坑' text='为了规范给所有内部类型套一层 ABC：ABC 只在需要复用默认实现或强制补齐方法时才有收益，纯继承层次不增加任何运行时约束' />

<FlowTimeline :steps='[{"title": "鸭子类型、EAFP 与 ABC 的显式契约", "desc": "Python 的默认风格是鸭子类型配 EAFP（Easier to Ask Forg…", "tone": "blue"}, {"title": "Protocol 的结构化子类型与 runtime_checkable 边界", "desc": "typing.Protocol（PEP 544，3.8 引入）表达的是结构化子类型：…", "tone": "purple"}, {"title": "选型与运行时成本：两条契约各自落在哪一层", "desc": "把选型落到具体问题：需要给一组自家类型提供公共实现、强制子类补齐方法、或做 isin…", "tone": "orange"}, {"title": "工程落地", "desc": "插件平台用 Protocol 描述最小接口并配白名单准入", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 把取舍写进练习与自检

<Exercise title='基础：验证 abstractmethod 必须配合 ABCMeta' task='写两个类，一个继承 ABC 并用 @abstractmethod，一个普通类也用 @abstractmethod；分别打印 __abstractmethods__ 并尝试实例化，解释为什么后者不报错。' solution='from abc import ABC, abstractmethod\nclass A(ABC):\n    @abstractmethod\n    def go(self): pass\nclass B:\n    @abstractmethod\n    def go(self): pass\nprint(A.__abstractmethods__, B.__dict__.get(&#39;__abstractmethods__&#39;))\ntry:\n    A()\nexcept TypeError as e:\n    print(type(e).__name__)\nprint(&#39;B ok:&#39;, B() is not None)' explain='ABCMeta 在 type.__new__ 里把抽象方法名收进 __abstractmethods__（frozenset），实例化时检查；普通类的元类是 type，没有这段逻辑，__abstractmethods__ 根本不存在，B 可正常实例化。' />

<Exercise title='进阶：对比 register 与真实继承，并给 Protocol 做签名探测' task='用 ABCMeta.register 注册一个没有目标方法的类，验证 issubclass 为 True 但调用抛 AttributeError；再写一个 @runtime_checkable 的 Protocol，构造一个名字对但参数个数不符的类，证明 isinstance 仍为 True，并补一段真实调用探测把它挡掉。' solution='from abc import ABCMeta\nfrom typing import Protocol, runtime_checkable\nclass M(metaclass=ABCMeta):\n    def run(self): return &#39;base&#39;\nclass X: pass\nM.register(X)\nprint(issubclass(X, M), hasattr(X(), &#39;run&#39;))\n@runtime_checkable\nclass P(Protocol):\n    def go(self, a): ...\nclass Wrong:\n    def go(self, a, b, c): return 0\nprint(&#39;isinstance:&#39;, isinstance(Wrong(), P))\ntry:\n    Wrong().go(1)\nexcept TypeError as e:\n    print(&#39;rejected by real call:&#39;, type(e).__name__)' explain='register 只改类型判定、不继承 run；runtime_checkable 只按成员名 hasattr 判定，故参数个数不符仍返回 True。真实调用 go(1) 抛 TypeError，说明运行时准入必须补真实调用或签名探测。' />

<Quiz no='044-1' q='关于 ABCMeta.register，准确的说法是？' :options='["注册后 issubclass/isinstance 为 True，但被注册类不继承任何方法体", "注册会把基类方法复制给被注册类", "注册会校验被注册类是否实现了抽象方法", "注册只对 Protocol 有效"]' answer="0" explain='register 写入 _abc_registry，仅影响 __subclasscheck__ / __instancecheck__ 的判定。它不改变 MRO、不注入方法，也不做校验，因此调用前仍需自己兜底。' />

<Quiz no='044-2' q='对未加 @runtime_checkable 的 Protocol 使用 isinstance 会怎样？' :options='["抛 TypeError，提示只能用于 @runtime_checkable 协议", "返回 False", "返回 True，因为结构匹配", "自动降级为静态检查"]' answer="0" explain='默认 Protocol 只服务静态检查，_ProtocolMeta 的 __instancecheck__ 会拒绝运行时判定；加 @runtime_checkable 后才换成按成员名 hasattr 的浅层检查。' />

<Quiz no='044-3' q='@runtime_checkable 的 Protocol 通过 isinstance 意味着什么？' :options='["对象具备协议声明的成员名，但签名与返回类型未必匹配", "方法签名完全一致", "对象已继承该 Protocol", "对象通过了完整的数据校验"]' answer="0" explain='运行时检查遍历 __protocol_attrs__ 做 hasattr，只确认名字存在，不调用方法也不比对签名。签名一致性由 mypy / pyright 在静态期判断，数据校验更不属于协议职责。' />

<Predict no='044-P' q='普通类上用 @abstractmethod 标记方法，实例化会怎样？' :options='["正常实例化，不报错", "抛 TypeError: Can&#39;t instantiate abstract class", "抛 AttributeError"]' answer='0' output='正常实例化，__abstractmethods__ 不存在' explain='@abstractmethod 只是给函数加 __isabstractmethod__ 标记；只有 ABCMeta（继承 ABC）才会在 type.__new__ 里收集 __abstractmethods__ 并在实例化时检查。普通类元类是 type，没有这层逻辑。' />

<FillBlank no='044-F' tpl='from abc  ___ ABC, abstractmethod' :answers='["import"]' hint='回想本讲关于 鸭子类型与 EAFP 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 鸭子类型、EAFP 与 ABC 的显式契约 的落点。' />

<KnowledgeCard :points='["鸭子类型配 EAFP 是默认风格；ABC 的价值在复用默认实现与强制补齐，不在「规范」本身", "@abstractmethod 必须配合 ABCMeta / ABC 才生效，结果写入 __abstractmethods__", "ABCMeta.register 建虚拟子类，只改 issubclass/isinstance，不继承方法体也不校验成员", "typing.Protocol（3.8 / PEP 544）按结构隐式匹配，对第三方类型零侵入，主要服务静态检查", "@runtime_checkable 只做成员名 hasattr 判定，放过签名不符的类；运行时准入要补白名单或真实调用", "isinstance 走元类 __instancecheck__ 钩子；ABC 有缓存，Protocol 检查代价随成员数线性增长"]' :pitfalls='["为了规范给所有内部类型套一层 ABC", "用 register 让第三方类通过 isinstance 后直接调用方法", "对未加 @runtime_checkable 的 Protocol 用 isinstance，或把通过检查当成签名合规", "为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束"]' summary='Python 有两种契约：ABC 靠继承显式声明，Protocol 靠结构隐式匹配；后者对第三方类型零侵入，特别适合插件体系' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 鸭子类型配 EAFP 是默认风格；ABC 的价值在复用默认实现与强制补齐，不在「规范」本身 | 建立直觉 |
| @abstractmethod 必须配合 ABCMeta / ABC 才生效，结果写入 __abstractmethods__ | 跑通示例 |
| ABCMeta.register 建虚拟子类，只改 issubclass/isinstance，不继承方法体也不校验成员 | 深入边界 |
| typing.Protocol（3.8 / PEP 544）按结构隐式匹配，对第三方类型零侵入，主要服务静态检查 | 工程落地 |
| @runtime_checkable 只做成员名 hasattr 判定，放过签名不符的类；运行时准入要补白名单或真实调用 | 随堂检测 |
| isinstance 走元类 __instancecheck__ 钩子；ABC 有缓存，Protocol 检查代价随成员数线性增长 | 复盘 |

1. 鸭子类型配 EAFP 是默认风格；ABC 的价值在复用默认实现与强制补齐，不在「规范」本身

2. @abstractmethod 必须配合 ABCMeta / ABC 才生效，结果写入 __abstractmethods__

3. ABCMeta.register 建虚拟子类，只改 issubclass/isinstance，不继承方法体也不校验成员

[下一讲：元类：__new__、type 与类创建过程](/oop/metaclass)
