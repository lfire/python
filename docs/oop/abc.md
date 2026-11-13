---
title: 第 044 讲 · 鸭子类型、抽象基类与 Protocol
description: 在灵活与契约之间做出正确取舍
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='35 分钟' goal='在灵活与契约之间做出正确取舍' prereq='第 043 讲 · __slots__、弱引用与对象内存布局' />

# 第 044 讲 · 鸭子类型、抽象基类与 Protocol

> Python 有两种契约：ABC 靠继承显式声明，Protocol 靠结构隐式匹配；后者对第三方类型零侵入，特别适合插件体系。本讲的目标是「在灵活与契约之间做出正确取舍」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P044' title="本讲目标" :items='["能说清鸭子类型与 EAFP", "能说清abc.ABC 与 abstractmethod", "能说清虚拟子类 register", "能说清typing.Protocol 结构化子类型", "能说清运行时检查的代价"]' />

## 1. 先建立直觉

**鸭子类型与 EAFP**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**abc.ABC 与 abstractmethod**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**虚拟子类 register**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

<ConceptDiagram type='compare2' title='第 044 讲 · 鸭子类型与 EAFP' labels='鸭子类型与 EAFP|abc.ABC 与 abstractmethod|虚拟子类 register|typing.Protocol 结构化子类型' caption='在灵活与契约之间做出正确取舍' />

上图用本讲的三个核心概念标出了主线：**鸭子类型与 EAFP → abc.ABC 与 abstractmethod → 虚拟子类 register**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 鸭子类型与 EAFP 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 3", "tone": "green"}, {"title": "深入边界", "desc": "厘清 abc.ABC 与 abstractmethod 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 接口隔离 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**鸭子类型与 EAFP**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

```python
class Positive:
    def __set_name__(self, owner, name):
        self.name = name
    def __get__(self, obj, owner=None):
        return obj.__dict__.get(self.name, 0)
    def __set__(self, obj, value):
        if value < 0: raise ValueError("must be positive")
        obj.__dict__[self.name] = value

class Order:
    qty = Positive()

o = Order(); o.qty = 3
print(o.qty)
```

<OutputBox title="运行结果" output='3' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='class Positive:\n    def __set_name__(self, owner, name):\n        self.name = name\n    def __get__(self, obj, owner=None):\n        return obj.__dict__.get(self.name, 0)\n    def __set__(self, obj, value):\n        if value &lt; 0: raise ValueError("must be positive")\n        obj.__dict__[self.name] = value\n\nclass Order:\n    qty = Positive()\n\no = Order(); o.qty = 3\nprint(o.qty)' :notes='["实现 __set__ 即为数据描述符，优先级高于实例字典", "__set_name__ 在类创建时拿到字段名", "校验集中在一处，所有赋值路径都受约束", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色", "第 13 行：与上文规则对照，观察它在整体流程里承担的角色", "第 14 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 044 讲 · 鸭子类型、抽象基类与 Protocol' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**abc.ABC 与 abstractmethod**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
class Vector:
    def __init__(self, x, y): self.x, self.y = x, y
    def __len__(self): return 2
    def __repr__(self): return f"V({self.x},{self.y})"

v = Vector(1, 2)
print(len(v), bool(v), v)
```

<OutputBox title="对照写法的输出（先自己猜）" output='2 True V(1,2)' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "class Positive:\n    def __set_name__(self, owner, name):\n        self.name = name\n    def __get__(self, obj, owner=None):\n        return obj.__dict__.get(self.name, 0)\n    def __set__(self, obj, value):\n        if value &lt; 0: raise ValueError(\"must be positive\")\n        obj.__dict__[self.name] = value\n\nclass Order:\n    qty = Positive()\n\no = Order(); o.qty = 3\nprint(o.qty)", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "class Vector:\n    def __init__(self, x, y): self.x, self.y = x, y\n    def __len__(self): return 2\n    def __repr__(self): return f\"V({self.x},{self.y})\"\n\nv = Vector(1, 2)\nprint(len(v), bool(v), v)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束」' />

## 3. 深入一步：规则与边界

**虚拟子类 register**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**typing.Protocol 结构化子类型**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**运行时检查的代价**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| 鸭子类型与 EAFP | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束 |
| abc.ABC 与 abstractmethod | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束 |
| 虚拟子类 register | 这里的关键词是「什么时候」和「代价是什么」 | 为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束 |
| typing.Protocol 结构化子类型 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束 |
| 运行时检查的代价 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束 |

<Term word='鸭子类型与 EAFP' text='Python 有两种契约：ABC 靠继承显式声明，Protocol 靠结构隐式匹配；后者对第三方类型零侵入，特别适合插件体系' />

<Callout type="warn" title="易错点" text='为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：鸭子类型与 EAFP", "body": "**鸭子类型与 EAFP**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：abc.ABC 与 abstractmethod", "body": "**abc.ABC 与 abstractmethod**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：虚拟子类 register", "body": "**虚拟子类 register**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：typing.Protocol 结构化子类型", "body": "**typing.Protocol 结构化子类型**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

对外部生态用 Protocol 描述最小需求，对框架内部用 ABC 提供默认实现与复用 **接口隔离**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "from collections.abc import Sized; print(isinstance([1], Sized))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **鸭子类型与 EAFP** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「接口隔离」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「接口隔离」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 鸭子类型与 EAFP 与 接口隔离 两个关注点，并说明你的取舍。' :hints='["回到 鸭子类型与 EAFP 的规则", "留意易错点：为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束", "先让代码跑通，再补边界与异常分支"]' solution='class Vector:\n    def __init__(self, x, y): self.x, self.y = x, y\n    def __len__(self): return 2\n    def __repr__(self): return f"V({self.x},{self.y})"\n\nv = Vector(1, 2)\nprint(len(v), bool(v), v)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；对外部生态用 Protocol 描述最小需求，对框架内部用 ABC 提供默认实现与复用' />

## 随堂检测

<Quiz no='044-1' q='在本讲讨论的「鸭子类型与 EAFP」语境下，下面哪一种说法是准确的？' :options='["Python 有两种契约：ABC 靠继承显式声明，Protocol 靠结构隐式匹配；后者对第三方类型零侵入，特别适合插件体系", "鸭子类型与 EAFP 只影响代码的书写形式，不会改变任何运行时行为", "鸭子类型与 EAFP 在所有 Python 实现与所有版本中表现完全一致", "只要用了 鸭子类型与 EAFP，就不必再考虑 接口隔离 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 接口隔离 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='044-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["3", "3\n（无更多输出）", "AttributeError: 鸭子类型与 EAFP 不可用"]' answer="0" output='3' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='044-3' tpl='    _____set_name__(self, owner, name):' :answers='["def"]' hint='回想本讲关于 鸭子类型与 EAFP 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["鸭子类型与 EAFP：鸭子类型与 EAFP", "abc.ABC 与 abstractmethod：abc.ABC 与 abstractmethod", "虚拟子类 register：虚拟子类 register", "typing.Protocol 结构化子类型：typing.Protocol 结构化子类型"]' :pitfalls='["为了「规范」给所有内部类型套一层抽象基类，只会增加层次而不增加约束", "忽略版本差异，把 接口隔离 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：Python 有两种契约：ABC 靠继承显式声明，Protocol 靠结构隐式匹配；后者对第三方类型零侵入，特别适合插件体系' />

## 小结与下一讲

1. 鸭子类型与 EAFP：鸭子类型与 EAFP
2. abc.ABC 与 abstractmethod：abc.ABC 与 abstractmethod
3. 对外部生态用 Protocol 描述最小需求，对框架内部用 ABC 提供默认实现与复用

[下一讲：元类：__new__、type 与类创建过程](/oop/metaclass)
