---
title: 第 115 讲 · 内存分配器 pymalloc 与 GC 源码
description: 定位并解决苛刻场景下的内存问题
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='45 分钟' goal='定位并解决苛刻场景下的内存问题' prereq='第 114 讲 · CPython 源码：对象、帧与求值循环' />

# 第 115 讲 · 内存分配器 pymalloc 与 GC 源码

> pymalloc 为小于 512 字节的对象做了专用池，所以「对象已释放但 RSS 不降」常常是 arena 没整体空闲，而非泄漏。本讲的目标是「定位并解决苛刻场景下的内存问题」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P115' title="本讲目标" :items='["能说清arena / pool / block 三级", "能说清小对象分配路径", "能说清分代 GC 触发逻辑", "能说清gcmodule 收集过程", "能说清内存碎片与归还"]' />

## 1. 先建立直觉

**arena / pool / block 三级**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**小对象分配路径**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**分代 GC 触发逻辑**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

<ConceptDiagram type='flow3' title='第 115 讲 · arena / pool / block 三级' labels='arena / pool / block 三级|小对象分配路径|分代 GC 触发逻辑|gcmodule 收集过程' caption='定位并解决苛刻场景下的内存问题' />

上图用本讲的三个核心概念标出了主线：**arena / pool / block 三级 → 小对象分配路径 → 分代 GC 触发逻辑**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 arena / pool / block 三级 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 problem -&gt; options -&gt; veri", "tone": "green"}, {"title": "深入边界", "desc": "厘清 小对象分配路径 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 与 glibc malloc 关系 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**arena / pool / block 三级**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

```python
# 技术决策模板：问题—约束—备选—代价—验证—回退
decision = {
    "problem": "读多写少，热点集中",
    "options": ["本地缓存", "Redis 集中缓存"],
    "verify": "压测 QPS 与命中率",
    "rollback": "开关切回直连 DB",
}
print(" -> ".join(decision))
```

<OutputBox title="运行结果" output='problem -&gt; options -&gt; verify -&gt; rollback' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='# 技术决策模板：问题—约束—备选—代价—验证—回退\ndecision = {\n    "problem": "读多写少，热点集中",\n    "options": ["本地缓存", "Redis 集中缓存"],\n    "verify": "压测 QPS 与命中率",\n    "rollback": "开关切回直连 DB",\n}\nprint(" -&gt; ".join(decision))' :notes='["方案必须带可验证指标与回退路径", "约束写清楚，结论才可复盘", "把模板沉淀成团队检查表", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 115 讲 · 内存分配器 pymalloc 与 GC 源码' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**小对象分配路径**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import time
print(time.perf_counter_ns() > 0)
```

<OutputBox title="对照写法的输出（先自己猜）" output='True' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "# 技术决策模板：问题—约束—备选—代价—验证—回退\ndecision = {\n    \"problem\": \"读多写少，热点集中\",\n    \"options\": [\"本地缓存\", \"Redis 集中缓存\"],\n    \"verify\": \"压测 QPS 与命中率\",\n    \"rollback\": \"开关切回直连 DB\",\n}\nprint(\" -&gt; \".join(decision))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import time\nprint(time.perf_counter_ns() &gt; 0)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加停顿」' />

## 3. 深入一步：规则与边界

**分代 GC 触发逻辑**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**gcmodule 收集过程**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**内存碎片与归还**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| arena / pool / block 三级 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加 |
| 小对象分配路径 | 这里的关键词是「什么时候」和「代价是什么」 | 看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加 |
| 分代 GC 触发逻辑 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加 |
| gcmodule 收集过程 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加 |
| 内存碎片与归还 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加 |

<Term word='arena / pool / block 三级' text='pymalloc 为小于 512 字节的对象做了专用池，所以「对象已释放但 RSS 不降」常常是 arena 没整体空闲，而非泄漏' />

<Callout type="warn" title="易错点" text='看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加停顿而不解决问题' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：arena / pool / block 三级", "body": "**arena / pool / block 三级**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：小对象分配路径", "body": "**小对象分配路径**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：分代 GC 触发逻辑", "body": "**分代 GC 触发逻辑**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：gcmodule 收集过程", "body": "**gcmodule 收集过程**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}]' />

<ArchBlueprint title='第 115 讲 · 分层视角' caption='把「arena / pool / block 三级」放进系统分层里看' :layers='[{"name": "入口层", "note": "请求与使用方式", "protocol": "函数调用 / HTTP", "items": [{"label": "arena / pool", "sub": "对外接口", "detail": "**arena / pool / block 三级**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概", "tone": "blue"}]}, {"name": "逻辑层", "note": "规则、状态与校验", "protocol": "Python 对象协议", "items": [{"label": "小对象分配路径", "sub": "核心处理", "detail": "**小对象分配路径**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tone": "purple"}]}, {"name": "资源层", "note": "数据、IO 与失败处理", "items": [{"label": "与 glibc mall", "sub": "落地与收尾", "detail": "用 tracemalloc 与 pympler 区分「仍被引用」「碎片」「未归还」，再决定改生命周期还是改分配策略", "tone": "green"}]}]' />

## 4. 工程实践

用 tracemalloc 与 pympler 区分「仍被引用」「碎片」「未归还」，再决定改生命周期还是改分配策略 **与 glibc malloc 关系**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import dis, sys; print(sys.version.split()[0]); dis.dis(lambda x:x)"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **arena / pool / block 三级** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「与 glibc malloc 关系」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「与 glibc malloc 关系」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 arena / pool / block 三级 与 与 glibc malloc 关系 两个关注点，并说明你的取舍。' :hints='["回到 arena / pool / block 三级 的规则", "留意易错点：看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加停顿而不解决", "先让代码跑通，再补边界与异常分支"]' solution='import time\nprint(time.perf_counter_ns() &gt; 0)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；用 tracemalloc 与 pympler 区分「仍被引用」「碎片」「未归还」，再决定改生命周期还是改分配策略' />

## 随堂检测

<Quiz no='115-1' q='在本讲讨论的「arena / pool / block 三级」语境下，下面哪一种说法是准确的？' :options='["pymalloc 为小于 512 字节的对象做了专用池，所以「对象已释放但 RSS 不降」常常是 arena 没整体空闲，而非泄漏", "arena / pool / block 三级 只影响代码的书写形式，不会改变任何运行时行为", "arena / pool / block 三级 在所有 Python 实现与所有版本中表现完全一致", "只要用了 arena / pool / block 三级，就不必再考虑 与 glibc malloc 关系 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 与 glibc malloc 关系 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='115-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["problem -&gt; options -&gt; verify -&gt; rollback", "problem -&gt; options -&gt; verify -&gt; rollback\n（无更多输出）", "AttributeError: arena / pool / block 三级 不可用"]' answer="0" output='problem -&gt; options -&gt; verify -&gt; rollback' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='115-3' tpl='dec___ion = {' :answers='["is"]' hint='回想本讲关于 arena / pool / block 三级 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["arena / pool / block 三级：arena / pool / block 三级", "小对象分配路径：小对象分配路径", "分代 GC 触发逻辑：分代 GC 触发逻辑", "gcmodule 收集过程：gcmodule 收集过程"]' :pitfalls='["看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加停顿而不解决问题", "忽略版本差异，把 与 glibc malloc 关系 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：pymalloc 为小于 512 字节的对象做了专用池，所以「对象已释放但 RSS 不降」常常是 arena 没整体空闲，而非泄漏' />

## 小结与下一讲

1. arena / pool / block 三级：arena / pool / block 三级
2. 小对象分配路径：小对象分配路径
3. 用 tracemalloc 与 pympler 区分「仍被引用」「碎片」「未归还」，再决定改生命周期还是改分配策略

[下一讲：导入系统源码与 import hook](/advanced/import-source)
