---
title: 第 056 讲 · 属性访问链路与 __getattribute__
description: 解释所有属性相关现象的统一模型
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='35 分钟' goal='解释所有属性相关现象的统一模型' prereq='第 055 讲 · 导入系统源码级：finder、loader 与缓存' />

# 第 056 讲 · 属性访问链路与 __getattribute__

> 一次 obj.x 要依次问：类及其 MRO 上的数据描述符、实例 __dict__、非数据描述符、最后才是 __getattr__，所有属性现象都由这条链解释。本讲的目标是「解释所有属性相关现象的统一模型」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P056' title="本讲目标" :items='["能说清__getattribute__ 总入口", "能说清数据描述符优先", "能说清实例字典", "能说清非数据描述符", "能说清__getattr__ 兜底"]' />

## 1. 先建立直觉

**__getattribute__ 总入口**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**数据描述符优先**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**实例字典**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

<ConceptDiagram type='flow4' title='第 056 讲 · __getattribute__ 总入口' labels='__getattribute__ 总入口|数据描述符优先|实例字典|非数据描述符' caption='解释所有属性相关现象的统一模型' />

上图用本讲的三个核心概念标出了主线：**__getattribute__ 总入口 → 数据描述符优先 → 实例字典**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 __getattribute__ 总入口 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 3", "tone": "green"}, {"title": "深入边界", "desc": "厘清 数据描述符优先 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 性能与递归风险 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**__getattribute__ 总入口**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

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

<LineByLine code='class Positive:\n    def __set_name__(self, owner, name):\n        self.name = name\n    def __get__(self, obj, owner=None):\n        return obj.__dict__.get(self.name, 0)\n    def __set__(self, obj, value):\n        if value &lt; 0: raise ValueError("must be positive")\n        obj.__dict__[self.name] = value\n\nclass Order:\n    qty = Positive()\n\no = Order(); o.qty = 3\nprint(o.qty)' :notes='["实现 __set__ 即为数据描述符，优先级高于实例字典", "__set_name__ 在类创建时拿到字段名", "校验集中在一处，所有赋值路径都受约束", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色", "第 13 行：与上文规则对照，观察它在整体流程里承担的角色", "第 14 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 056 讲 · 属性访问链路与 __getattribute__' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**数据描述符优先**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

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

<Compare :panels='[{"label": "主写法", "code": "class Positive:\n    def __set_name__(self, owner, name):\n        self.name = name\n    def __get__(self, obj, owner=None):\n        return obj.__dict__.get(self.name, 0)\n    def __set__(self, obj, value):\n        if value &lt; 0: raise ValueError(\"must be positive\")\n        obj.__dict__[self.name] = value\n\nclass Order:\n    qty = Positive()\n\no = Order(); o.qty = 3\nprint(o.qty)", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "class Vector:\n    def __init__(self, x, y): self.x, self.y = x, y\n    def __len__(self): return 2\n    def __repr__(self): return f\"V({self.x},{self.y})\"\n\nv = Vector(1, 2)\nprint(len(v), bool(v), v)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「在 __getattribute__ 里用 self.x 取属性会无限递」' />

## 3. 深入一步：规则与边界

**实例字典**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**非数据描述符**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**__getattr__ 兜底**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| __getattribute__ 总入口 | 这里的关键词是「什么时候」和「代价是什么」 | 在 __getattribute__ 里用 self.x 取属性会无 |
| 数据描述符优先 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 在 __getattribute__ 里用 self.x 取属性会无 |
| 实例字典 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 在 __getattribute__ 里用 self.x 取属性会无 |
| 非数据描述符 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 在 __getattribute__ 里用 self.x 取属性会无 |
| __getattr__ 兜底 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 在 __getattribute__ 里用 self.x 取属性会无 |

<Term word='__getattribute__ 总入口' text='一次 obj.x 要依次问：类及其 MRO 上的数据描述符、实例 __dict__、非数据描述符、最后才是 __getattr__，所有属性现象都由这条链解释' />

<Callout type="warn" title="易错点" text='在 __getattribute__ 里用 self.x 取属性会无限递归，必须用 object.__getattribute__' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：__getattribute__ 总入口", "body": "**__getattribute__ 总入口**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：数据描述符优先", "body": "**数据描述符优先**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：实例字典", "body": "**实例字典**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：非数据描述符", "body": "**非数据描述符**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

代理对象、懒加载、远程属性用 __getattr__ 实现；不要滥改 __getattribute__，它位于每次属性访问的热路径上 **性能与递归风险**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "from collections.abc import Sized; print(isinstance([1], Sized))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **__getattribute__ 总入口** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「性能与递归风险」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「性能与递归风险」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 __getattribute__ 总入口 与 性能与递归风险 两个关注点，并说明你的取舍。' :hints='["回到 __getattribute__ 总入口 的规则", "留意易错点：在 __getattribute__ 里用 self.x 取属性会无限递归，必须", "先让代码跑通，再补边界与异常分支"]' solution='class Vector:\n    def __init__(self, x, y): self.x, self.y = x, y\n    def __len__(self): return 2\n    def __repr__(self): return f"V({self.x},{self.y})"\n\nv = Vector(1, 2)\nprint(len(v), bool(v), v)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；代理对象、懒加载、远程属性用 __getattr__ 实现；不要滥改 __getattribute__，它位于每次属性访问的热路径上' />

## 随堂检测

<Quiz no='056-1' q='在本讲讨论的「__getattribute__ 总入口」语境下，下面哪一种说法是准确的？' :options='["一次 obj.x 要依次问：类及其 MRO 上的数据描述符、实例 __dict__、非数据描述符、最后才是 __getattr__，所有属性现象都由这条链解", "__getattribute__ 总入口 只影响代码的书写形式，不会改变任何运行时行为", "__getattribute__ 总入口 在所有 Python 实现与所有版本中表现完全一致", "只要用了 __getattribute__ 总入口，就不必再考虑 性能与递归风险 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 性能与递归风险 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='056-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["3", "3\n（无更多输出）", "AttributeError: __getattribute__ 总入口 不可用"]' answer="0" output='3' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='056-3' tpl='    _____set_name__(self, owner, name):' :answers='["def"]' hint='回想本讲关于 __getattribute__ 总入口 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["__getattribute__ 总入口：__getattribute__ 总入口", "数据描述符优先：数据描述符优先", "实例字典：实例字典", "非数据描述符：非数据描述符"]' :pitfalls='["在 __getattribute__ 里用 self.x 取属性会无限递归，必须用 object.__getattribute__", "忽略版本差异，把 性能与递归风险 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：一次 obj.x 要依次问：类及其 MRO 上的数据描述符、实例 __dict__、非数据描述符、最后才是 __getattr__，所有属性现象都由这条链解释' />

## 小结与下一讲

1. __getattribute__ 总入口：__getattribute__ 总入口
2. 数据描述符优先：数据描述符优先
3. 代理对象、懒加载、远程属性用 __getattr__ 实现；不要滥改 __getattribute__，它位于每次属性访问的热路径上

[下一讲：可变性、深浅拷贝与共享状态](/core/copy)
