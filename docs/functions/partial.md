---
title: 第 034 讲 · 偏函数、可调用对象与函数式工具
description: 用标准库工具削减重复参数
---

<StageHeader stage='L3 · 函数与抽象' level='★★☆☆☆' time='25 分钟' goal='用标准库工具削减重复参数' prereq='第 033 讲 · 带参装饰器、叠加顺序与类装饰器' />

# 第 034 讲 · 偏函数、可调用对象与函数式工具

> 偏函数把「固定一部分参数」变成数据，回调接口只要一个可调用对象时特别好用；lru_cache 则把纯函数变成带边界的记忆化。本讲的目标是「用标准库工具削减重复参数」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P034' title="本讲目标" :items='["能说清functools.partial", "能说清lru_cache 与缓存策略", "能说清singledispatch 分派", "能说清cached_property", "能说清可调用协议"]' />

## 1. 先建立直觉

**functools.partial**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**lru_cache 与缓存策略**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**singledispatch 分派**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

<ConceptDiagram type='compare2' title='第 034 讲 · functools.partial' labels='functools.partial|lru_cache 与缓存策略|singledispatch 分派|cached_property' caption='用标准库工具削减重复参数' />

上图用本讲的三个核心概念标出了主线：**functools.partial → lru_cache 与缓存策略 → singledispatch 分派**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 functools.partial 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 (&#39;example.com&#39;, 8080, 5, {", "tone": "green"}, {"title": "深入边界", "desc": "厘清 lru_cache 与缓存策略 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 工具函数组合 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**functools.partial**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

```python
def connect(host, /, port=80, *, timeout=3, **opts):
    return (host, port, timeout, opts)

print(connect("example.com", 8080, timeout=5, retry=2))
```

<OutputBox title="运行结果" output='(&#39;example.com&#39;, 8080, 5, {&#39;retry&#39;: 2})' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='def connect(host, /, port=80, *, timeout=3, **opts):\n    return (host, port, timeout, opts)\n\nprint(connect("example.com", 8080, timeout=5, retry=2))' :notes='["/ 之前的参数只能按位置传", "* 之后的参数必须写名字", "**opts 收集未声明的关键字参数", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 034 讲 · 偏函数、可调用对象与函数式工具' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**lru_cache 与缓存策略**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
def bad(x, acc=[]):
    acc.append(x)
    return acc

print(bad(1), bad(2))
```

<OutputBox title="对照写法的输出（先自己猜）" output='[1] [1, 2]' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "def connect(host, /, port=80, *, timeout=3, **opts):\n    return (host, port, timeout, opts)\n\nprint(connect(\"example.com\", 8080, timeout=5, retry=2))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "def bad(x, acc=[]):\n    acc.append(x)\n    return acc\n\nprint(bad(1), bad(2))", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数据甚」' />

## 3. 深入一步：规则与边界

**singledispatch 分派**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**cached_property**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**可调用协议**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| functools.partial | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数 |
| lru_cache 与缓存策略 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数 |
| singledispatch 分派 | 这里的关键词是「什么时候」和「代价是什么」 | 给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数 |
| cached_property | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数 |
| 可调用协议 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数 |

<Term word='functools.partial' text='偏函数把「固定一部分参数」变成数据，回调接口只要一个可调用对象时特别好用；lru_cache 则把纯函数变成带边界的记忆化' />

<Callout type="warn" title="易错点" text='给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数据甚至安全问题' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：functools.partial", "body": "**functools.partial**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：lru_cache 与缓存策略", "body": "**lru_cache 与缓存策略**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：singledispatch 分派", "body": "**singledispatch 分派**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：cached_property", "body": "**cached_property**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

缓存务必设 maxsize、明确键的可哈希性，并提供 cache_clear 供测试与热更新 **工具函数组合**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import inspect; print(inspect.signature(print))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **functools.partial** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「工具函数组合」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「工具函数组合」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 functools.partial 与 工具函数组合 两个关注点，并说明你的取舍。' :hints='["回到 functools.partial 的规则", "留意易错点：给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数据甚至安全问", "先让代码跑通，再补边界与异常分支"]' solution='def bad(x, acc=[]):\n    acc.append(x)\n    return acc\n\nprint(bad(1), bad(2))' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；缓存务必设 maxsize、明确键的可哈希性，并提供 cache_clear 供测试与热更新' />

## 随堂检测

<Quiz no='034-1' q='在本讲讨论的「functools.partial」语境下，下面哪一种说法是准确的？' :options='["偏函数把「固定一部分参数」变成数据，回调接口只要一个可调用对象时特别好用；lru_cache 则把纯函数变成带边界的记忆化", "functools.partial 只影响代码的书写形式，不会改变任何运行时行为", "functools.partial 在所有 Python 实现与所有版本中表现完全一致", "只要用了 functools.partial，就不必再考虑 工具函数组合 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 工具函数组合 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='034-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["(&#39;example.com&#39;, 8080, 5, {&#39;retry&#39;: 2})", "(&#39;example.com&#39;, 8080, 5, {&#39;retry&#39;: 2})\n（无更多输出）", "AttributeError: functools.partial 不可用"]' answer="0" output='(&#39;example.com&#39;, 8080, 5, {&#39;retry&#39;: 2})' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='034-3' tpl='___connect(host, /, port=80, *, timeout=3, **opts):' :answers='["def"]' hint='回想本讲关于 functools.partial 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["functools.partial：functools.partial", "lru_cache 与缓存策略：lru_cache 与缓存策略", "singledispatch 分派：singledispatch 分派", "cached_property：cached_property"]' :pitfalls='["给含可变参数或带副作用的函数加 lru_cache，会得到跨调用串数据甚至安全问题", "忽略版本差异，把 工具函数组合 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：偏函数把「固定一部分参数」变成数据，回调接口只要一个可调用对象时特别好用；lru_cache 则把纯函数变成带边界的记忆化' />

## 小结与下一讲

1. functools.partial：functools.partial
2. lru_cache 与缓存策略：lru_cache 与缓存策略
3. 缓存务必设 maxsize、明确键的可哈希性，并提供 cache_clear 供测试与热更新

[下一讲：模块与包：import 机制与循环导入](/functions/modules)
