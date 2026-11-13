---
title: 第 047 讲 · dataclass、attrs 与 pydantic 模型
description: 选对数据建模工具并理解校验边界
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='35 分钟' goal='选对数据建模工具并理解校验边界' prereq='第 046 讲 · 反射与自省：getattr、inspect 与 __dict__' />

# 第 047 讲 · dataclass、attrs 与 pydantic 模型

> dataclass 只在类创建时生成样板方法，不做事后校验；pydantic 在实例化时按类型强制转换与验证，两者解决的是不同层的问题。本讲的目标是「选对数据建模工具并理解校验边界」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P047' title="本讲目标" :items='["能说清dataclass 生成了什么", "能说清field 与 default_factory", "能说清frozen 与 order", "能说清slots 参数", "能说清pydantic 运行时校验"]' />

## 1. 先建立直觉

**dataclass 生成了什么**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**field 与 default_factory**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**frozen 与 order**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

<ConceptDiagram type='layers3' title='第 047 讲 · dataclass 生成了什么' labels='dataclass 生成了什么|field 与 default_factory|frozen 与 order|slots 参数' caption='选对数据建模工具并理解校验边界' />

上图用本讲的三个核心概念标出了主线：**dataclass 生成了什么 → field 与 default_factory → frozen 与 order**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 dataclass 生成了什么 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 [&lt;class &#39;D&#39;&gt;, &lt;class &#39;B&#39;&gt;,", "tone": "green"}, {"title": "深入边界", "desc": "厘清 field 与 default_factory 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 与 ORM 的边界 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**dataclass 生成了什么**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

```python
class A:
    def who(self): return "A"
class B(A):
    def who(self): return "B+" + super().who()
class C(A):
    def who(self): return "C+" + super().who()
class D(B, C): pass

print(D.mro())
print(D().who())
```

<OutputBox title="运行结果" output='[&lt;class &#39;D&#39;&gt;, &lt;class &#39;B&#39;&gt;, &lt;class &#39;C&#39;&gt;, &lt;class &#39;A&#39;&gt;, &lt;class &#39;object&#39;&gt;]\nB+C+A' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='class A:\n    def who(self): return "A"\nclass B(A):\n    def who(self): return "B+" + super().who()\nclass C(A):\n    def who(self): return "C+" + super().who()\nclass D(B, C): pass\n\nprint(D.mro())\nprint(D().who())' :notes='["MRO 由 C3 线性化决定，可用 __mro__ 查看", "super() 沿 MRO 找下一个实现，不是简单的父类", "菱形继承下 A.who 只被调用一次", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 047 讲 · dataclass、attrs 与 pydantic 模型' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**field 与 default_factory**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
class Mix:
    def log(self): print("log", type(self).__name__)
class Service(Mix):
    def run(self): self.log()
Service().run()
```

<OutputBox title="对照写法的输出（先自己猜）" output='log Service' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "class A:\n    def who(self): return \"A\"\nclass B(A):\n    def who(self): return \"B+\" + super().who()\nclass C(A):\n    def who(self): return \"C+\" + super().who()\nclass D(B, C): pass\n\nprint(D.mro())\nprint(D().who())", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "class Mix:\n    def log(self): print(\"log\", type(self).__name__)\nclass Service(Mix):\n    def run(self): self.log()\nService().run()", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据，错误」' />

## 3. 深入一步：规则与边界

**frozen 与 order**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**slots 参数**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**pydantic 运行时校验**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| dataclass 生成了什么 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据， |
| field 与 default_factory | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据， |
| frozen 与 order | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据， |
| slots 参数 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据， |
| pydantic 运行时校验 | 这里的关键词是「什么时候」和「代价是什么」 | 把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据， |

<Term word='dataclass 生成了什么' text='dataclass 只在类创建时生成样板方法，不做事后校验；pydantic 在实例化时按类型强制转换与验证，两者解决的是不同层的问题' />

<Callout type="warn" title="易错点" text='把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据，错误会推迟到业务深处才爆' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：dataclass 生成了什么", "body": "**dataclass 生成了什么**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：field 与 default_factory", "body": "**field 与 default_factory**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：frozen 与 order", "body": "**frozen 与 order**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：slots 参数", "body": "**slots 参数**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

边界层（HTTP、消息队列、配置文件）用 pydantic 校验，内部领域对象用 frozen dataclass **与 ORM 的边界**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "print(type('Demo', (), {}).__mro__)"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **dataclass 生成了什么** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「与 ORM 的边界」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「与 ORM 的边界」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 dataclass 生成了什么 与 与 ORM 的边界 两个关注点，并说明你的取舍。' :hints='["回到 dataclass 生成了什么 的规则", "留意易错点：把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据，错误会推迟到", "先让代码跑通，再补边界与异常分支"]' solution='class Mix:\n    def log(self): print("log", type(self).__name__)\nclass Service(Mix):\n    def run(self): self.log()\nService().run()' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；边界层（HTTP、消息队列、配置文件）用 pydantic 校验，内部领域对象用 frozen dataclass' />

## 随堂检测

<Quiz no='047-1' q='在本讲讨论的「dataclass 生成了什么」语境下，下面哪一种说法是准确的？' :options='["dataclass 只在类创建时生成样板方法，不做事后校验；pydantic 在实例化时按类型强制转换与验证，两者解决的是不同层的问题", "dataclass 生成了什么 只影响代码的书写形式，不会改变任何运行时行为", "dataclass 生成了什么 在所有 Python 实现与所有版本中表现完全一致", "只要用了 dataclass 生成了什么，就不必再考虑 与 ORM 的边界 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 与 ORM 的边界 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='047-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["[&lt;class &#39;D&#39;&gt;, &lt;class &#39;B&#39;&gt;, &lt;class &#39;C&#39;&gt;, &lt;class &#39;A&#39;&gt;, &lt;class &#39;object&#39;&gt;]\nB+C+A", "[&lt;class &#39;D&#39;&gt;, &lt;class &#39;B&#39;&gt;, &lt;class &#39;C&#39;&gt;, &lt;class &#39;A&#39;&gt;, &lt;class &#39;object&#39;&gt;]\n（无更多输出）", "AttributeError: dataclass 生成了什么 不可用"]' answer="0" output='[&lt;class &#39;D&#39;&gt;, &lt;class &#39;B&#39;&gt;, &lt;class &#39;C&#39;&gt;, &lt;class &#39;A&#39;&gt;, &lt;class &#39;object&#39;&gt;]\nB+C+A' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='047-3' tpl='    def who(self): ___"A"' :answers='["return"]' hint='回想本讲关于 dataclass 生成了什么 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["dataclass 生成了什么：dataclass 生成了什么", "field 与 default_factory：field 与 default_factory", "frozen 与 order：frozen 与 order", "slots 参数：slots 参数"]' :pitfalls='["把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据，错误会推迟到业务深处才爆", "忽略版本差异，把 与 ORM 的边界 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：dataclass 只在类创建时生成样板方法，不做事后校验；pydantic 在实例化时按类型强制转换与验证，两者解决的是不同层的问题' />

## 小结与下一讲

1. dataclass 生成了什么：dataclass 生成了什么
2. field 与 default_factory：field 与 default_factory
3. 边界层（HTTP、消息队列、配置文件）用 pydantic 校验，内部领域对象用 frozen dataclass

[下一讲：阶段综合：最小 ORM 与校验框架](/oop/capstone)
