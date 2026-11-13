---
title: 第 041 讲 · 特殊方法：repr、比较、算术与容器协议
description: 让自定义类型像内置类型一样自然
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='35 分钟' goal='让自定义类型像内置类型一样自然' prereq='第 040 讲 · 访问控制、property 与描述符协议' />

# 第 041 讲 · 特殊方法：repr、比较、算术与容器协议

> 数据模型方法是一套协议而非语法糖：实现 __len__ 后 len() 与真值测试会一起生效，实现 __eq__ 则会让类自动变成不可哈希。本讲的目标是「让自定义类型像内置类型一样自然」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P041' title="本讲目标" :items='["能说清__repr__ 与 __str__", "能说清__eq__ 与 __hash__ 联动", "能说清functools.total_ordering", "能说清数值运算与反向方法", "能说清__len__ / __contains__"]' />

## 1. 先建立直觉

**__repr__ 与 __str__**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**__eq__ 与 __hash__ 联动**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**functools.total_ordering**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

<ConceptDiagram type='flow4' title='第 041 讲 · __repr__ 与 __str__' labels='__repr__ 与 __str__|__eq__ 与 __hash__ 联动|functools.total_ordering|数值运算与反向方法' caption='让自定义类型像内置类型一样自然' />

上图用本讲的三个核心概念标出了主线：**__repr__ 与 __str__ → __eq__ 与 __hash__ 联动 → functools.total_ordering**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 __repr__ 与 __str__ 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 True", "tone": "green"}, {"title": "深入边界", "desc": "厘清 __eq__ 与 __hash__ 联动 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 __bool__ 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**__repr__ 与 __str__**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

```python
from abc import ABC, abstractmethod

class Store(ABC):
    @abstractmethod
    def get(self, key): ...
    def has(self, key):
        return self.get(key) is not None

class Memory(Store):
    def get(self, key): return {"a": 1}.get(key)

print(Memory().has("a"))
```

<OutputBox title="运行结果" output='True' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='from abc import ABC, abstractmethod\n\nclass Store(ABC):\n    @abstractmethod\n    def get(self, key): ...\n    def has(self, key):\n        return self.get(key) is not None\n\nclass Memory(Store):\n    def get(self, key): return {"a": 1}.get(key)\n\nprint(Memory().has("a"))' :notes='["抽象方法强制子类实现关键契约", "基类可提供依赖该契约的默认方法", "实例化未实现抽象方法的类会直接报错", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 041 讲 · 特殊方法：repr、比较、算术与容器协议' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**__eq__ 与 __hash__ 联动**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Readable(Protocol):
    def read(self) -> str: ...

print(isinstance(open(__file__), Readable))
```

<OutputBox title="对照写法的输出（先自己猜）" output='True' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "from abc import ABC, abstractmethod\n\nclass Store(ABC):\n    @abstractmethod\n    def get(self, key): ...\n    def has(self, key):\n        return self.get(key) is not None\n\nclass Memory(Store):\n    def get(self, key): return {\"a\": 1}.get(key)\n\nprint(Memory().has(\"a\"))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "from typing import Protocol, runtime_checkable\n\n@runtime_checkable\nclass Readable(Protocol):\n    def read(self) -&gt; str: ...\n\nprint(isinstance(open(__file__), Readable))", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「定义了 __eq__ 却忘记 __hash__，对象立刻不能进 set 」' />

## 3. 深入一步：规则与边界

**functools.total_ordering**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**数值运算与反向方法**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**__len__ / __contains__**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| __repr__ 与 __str__ | 这里的关键词是「什么时候」和「代价是什么」 | 定义了 __eq__ 却忘记 __hash__，对象立刻不能进 se |
| __eq__ 与 __hash__ 联动 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 定义了 __eq__ 却忘记 __hash__，对象立刻不能进 se |
| functools.total_ordering | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 定义了 __eq__ 却忘记 __hash__，对象立刻不能进 se |
| 数值运算与反向方法 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 定义了 __eq__ 却忘记 __hash__，对象立刻不能进 se |
| __len__ / __contains__ | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 定义了 __eq__ 却忘记 __hash__，对象立刻不能进 se |

<Term word='__repr__ 与 __str__' text='数据模型方法是一套协议而非语法糖：实现 __len__ 后 len() 与真值测试会一起生效，实现 __eq__ 则会让类自动变成不可哈希' />

<Callout type="warn" title="易错点" text='定义了 __eq__ 却忘记 __hash__，对象立刻不能进 set 或做 dict 键' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：__repr__ 与 __str__", "body": "**__repr__ 与 __str__**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：__eq__ 与 __hash__ 联动", "body": "**__eq__ 与 __hash__ 联动**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：functools.total_ordering", "body": "**functools.total_ordering**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：数值运算与反向方法", "body": "**数值运算与反向方法**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

值对象应设为 frozen dataclass 并哈希全部关键字段；可变对象明确设 __hash__ = None 表明意图 **__bool__**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "from collections.abc import Sized; print(isinstance([1], Sized))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **__repr__ 与 __str__** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「__bool__」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「__bool__」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 __repr__ 与 __str__ 与 __bool__ 两个关注点，并说明你的取舍。' :hints='["回到 __repr__ 与 __str__ 的规则", "留意易错点：定义了 __eq__ 却忘记 __hash__，对象立刻不能进 set 或做 d", "先让代码跑通，再补边界与异常分支"]' solution='from typing import Protocol, runtime_checkable\n\n@runtime_checkable\nclass Readable(Protocol):\n    def read(self) -&gt; str: ...\n\nprint(isinstance(open(__file__), Readable))' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；值对象应设为 frozen dataclass 并哈希全部关键字段；可变对象明确设 __hash__ = None 表明意图' />

## 随堂检测

<Quiz no='041-1' q='在本讲讨论的「__repr__ 与 __str__」语境下，下面哪一种说法是准确的？' :options='["数据模型方法是一套协议而非语法糖：实现 __len__ 后 len() 与真值测试会一起生效，实现 __eq__ 则会让类自动变成不可哈希", "__repr__ 与 __str__ 只影响代码的书写形式，不会改变任何运行时行为", "__repr__ 与 __str__ 在所有 Python 实现与所有版本中表现完全一致", "只要用了 __repr__ 与 __str__，就不必再考虑 __bool__ 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 __bool__ 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='041-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["True", "True\n（无更多输出）", "AttributeError: __repr__ 与 __str__ 不可用"]' answer="0" output='True' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='041-3' tpl='from abc ___ABC, abstractmethod' :answers='["import"]' hint='回想本讲关于 __repr__ 与 __str__ 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["__repr__ 与 __str__：__repr__ 与 __str__", "__eq__ 与 __hash__ 联动：__eq__ 与 __hash__ 联动", "functools.total_ordering：functools.total_ordering", "数值运算与反向方法：数值运算与反向方法"]' :pitfalls='["定义了 __eq__ 却忘记 __hash__，对象立刻不能进 set 或做 dict 键", "忽略版本差异，把 __bool__ 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：数据模型方法是一套协议而非语法糖：实现 __len__ 后 len() 与真值测试会一起生效，实现 __eq__ 则会让类自动变成不可哈希' />

## 小结与下一讲

1. __repr__ 与 __str__：__repr__ 与 __str__
2. __eq__ 与 __hash__ 联动：__eq__ 与 __hash__ 联动
3. 值对象应设为 frozen dataclass 并哈希全部关键字段；可变对象明确设 __hash__ = None 表明意图

[下一讲：上下文管理器与 with 协议](/oop/context)
