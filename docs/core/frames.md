---
title: 第 051 讲 · 帧、调用栈与命名空间
description: 理解执行上下文如何被创建与销毁
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='35 分钟' goal='理解执行上下文如何被创建与销毁' prereq='第 050 讲 · 字节码、栈式虚拟机与 dis 实战' />

# 第 051 讲 · 帧、调用栈与命名空间

> 每次函数调用都创建一个帧，生成器把帧挂起而不是销毁，这是惰性求值与协程能成立的物理基础。本讲的目标是「理解执行上下文如何被创建与销毁」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P051' title="本讲目标" :items='["能说清帧对象与 f_locals / f_globals", "能说清调用栈与递归深度", "能说清sys.setprofile 与 tracing", "能说清traceback 的来源", "能说清生成器帧的保留"]' />

## 1. 先建立直觉

**帧对象与 f_locals / f_globals**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**调用栈与递归深度**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**sys.setprofile 与 tracing**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

<ConceptDiagram type='flow4' title='第 051 讲 · 帧对象与 f_locals / f_globals' labels='帧对象与 f_locals / f_globals|调用栈与递归深度|sys.setprofile 与 tracing|traceback 的来源' caption='理解执行上下文如何被创建与销毁' />

上图用本讲的三个核心概念标出了主线：**帧对象与 f_locals / f_globals → 调用栈与递归深度 → sys.setprofile 与 tracing**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 帧对象与 f_locals / f_globals 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 frame 1 True", "tone": "green"}, {"title": "深入边界", "desc": "厘清 调用栈与递归深度 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 locals() 的语义 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**帧对象与 f_locals / f_globals**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

```python
import sys
def depth(n):
    print("frame", n, bool(sys._getframe().f_back))
    if n: depth(n-1)
depth(1)
```

<OutputBox title="运行结果" output='frame 1 True\nframe 0 True' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='import sys\ndef depth(n):\n    print("frame", n, bool(sys._getframe().f_back))\n    if n: depth(n-1)\ndepth(1)' :notes='["每次调用创建一个新的帧对象", "f_back 串起调用栈", "traceback 正是沿这条链还原出来的", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 051 讲 · 帧、调用栈与命名空间' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**调用栈与递归深度**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import dis
def gen():
    yield 1
    yield 2
print(gen.__code__.co_flags & 0x20 != 0)
dis.dis(gen)
```

<OutputBox title="对照写法的输出（先自己猜）" output='True\n...YIELD_VALUE...' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "import sys\ndef depth(n):\n    print(\"frame\", n, bool(sys._getframe().f_back))\n    if n: depth(n-1)\ndepth(1)", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import dis\ndef gen():\n    yield 1\n    yield 2\nprint(gen.__code__.co_flags &amp; 0x20 != 0)\ndis.dis(gen)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会生效」' />

## 3. 深入一步：规则与边界

**sys.setprofile 与 tracing**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**traceback 的来源**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**生成器帧的保留**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| 帧对象与 f_locals / f_globals | 这里的关键词是「什么时候」和「代价是什么」 | 在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会 |
| 调用栈与递归深度 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会 |
| sys.setprofile 与 tracing | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会 |
| traceback 的来源 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会 |
| 生成器帧的保留 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会 |

<Term word='帧对象与 f_locals / f_globals' text='每次函数调用都创建一个帧，生成器把帧挂起而不是销毁，这是惰性求值与协程能成立的物理基础' />

<Callout type="warn" title="易错点" text='在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会生效' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：帧对象与 f_locals / f_globals", "body": "**帧对象与 f_locals / f_globals**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：调用栈与递归深度", "body": "**调用栈与递归深度**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：sys.setprofile 与 tracing", "body": "**sys.setprofile 与 tracing**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：traceback 的来源", "body": "**traceback 的来源**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

写 profiler、覆盖率工具、调试器时用 sys.setprofile / settrace；生产环境避免长期开启，开销与线程行为都要评估 **locals() 的语义**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import dis; dis.dis(lambda x: x+1)"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **帧对象与 f_locals / f_globals** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「locals() 的语义」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「locals() 的语义」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 帧对象与 f_locals / f_globals 与 locals() 的语义 两个关注点，并说明你的取舍。' :hints='["回到 帧对象与 f_locals / f_globals 的规则", "留意易错点：在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会生效", "先让代码跑通，再补边界与异常分支"]' solution='import dis\ndef gen():\n    yield 1\n    yield 2\nprint(gen.__code__.co_flags &amp; 0x20 != 0)\ndis.dis(gen)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；写 profiler、覆盖率工具、调试器时用 sys.setprofile / settrace；生产环境避免长期开启，开销与线程行为都要评估' />

## 随堂检测

<Quiz no='051-1' q='在本讲讨论的「帧对象与 f_locals / f_globals」语境下，下面哪一种说法是准确的？' :options='["每次函数调用都创建一个帧，生成器把帧挂起而不是销毁，这是惰性求值与协程能成立的物理基础", "帧对象与 f_locals / f_globals 只影响代码的书写形式，不会改变任何运行时行为", "帧对象与 f_locals / f_globals 在所有 Python 实现与所有版本中表现完全一致", "只要用了 帧对象与 f_locals / f_globals，就不必再考虑 locals() 的语义 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 locals() 的语义 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='051-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["frame 1 True\nframe 0 True", "frame 1 True\n（无更多输出）", "AttributeError: 帧对象与 f_locals / f_globals 不可用"]' answer="0" output='frame 1 True\nframe 0 True' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='051-3' tpl='___sys' :answers='["import"]' hint='回想本讲关于 帧对象与 f_locals / f_globals 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["帧对象与 f_locals / f_globals：帧对象与 f_locals / f_globals", "调用栈与递归深度：调用栈与递归深度", "sys.setprofile 与 tracing：sys.setprofile 与 tracing", "traceback 的来源：traceback 的来源"]' :pitfalls='["在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会生效", "忽略版本差异，把 locals() 的语义 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：每次函数调用都创建一个帧，生成器把帧挂起而不是销毁，这是惰性求值与协程能成立的物理基础' />

## 小结与下一讲

1. 帧对象与 f_locals / f_globals：帧对象与 f_locals / f_globals
2. 调用栈与递归深度：调用栈与递归深度
3. 写 profiler、覆盖率工具、调试器时用 sys.setprofile / settrace；生产环境避免长期开启，开销与线程行为都要评估

[下一讲：对象内存布局、引用计数与小对象池](/core/memory)
