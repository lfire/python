---
title: 第 069 讲 · asyncio 深入：Task、Future 与事件循环
description: 掌握任务生命周期与取消语义
---

<StageHeader stage='L6 · 并发与异步' level='★★★★☆' time='45 分钟' goal='掌握任务生命周期与取消语义' prereq='第 068 讲 · async / await 与协程对象' />

# 第 069 讲 · asyncio 深入：Task、Future 与事件循环

> Task 是协程的调度单位，取消是「在下一个 await 点抛 CancelledError」而非强杀，所以清理逻辑必须写在 finally。本讲的目标是「掌握任务生命周期与取消语义」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P069' title="本讲目标" :items='["能说清loop 与策略", "能说清create_task 与 gather", "能说清Future 状态", "能说清call_soon / call_later", "能说清TaskGroup 结构化并发"]' />

## 1. 先建立直觉

**loop 与策略**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**create_task 与 gather**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**Future 状态**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

<ConceptDiagram type='compare2' title='第 069 讲 · loop 与策略' labels='loop 与策略|create_task 与 gather|Future 状态|call_soon / call_later' caption='掌握任务生命周期与取消语义' />

上图用本讲的三个核心概念标出了主线：**loop 与策略 → create_task 与 gather → Future 状态**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 loop 与策略 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 cleanup 1", "tone": "green"}, {"title": "深入边界", "desc": "厘清 create_task 与 gather 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 取消与 CancelledError 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**loop 与策略**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

```python
import asyncio

async def job(i):
    try:
        await asyncio.sleep(1)
    except asyncio.CancelledError:
        print("cleanup", i)
        raise

async def main():
    t = asyncio.create_task(job(1))
    await asyncio.sleep(0)
    t.cancel()
    try: await t
    except asyncio.CancelledError: pass
asyncio.run(main())
```

<OutputBox title="运行结果" output='cleanup 1' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='import asyncio\n\nasync def job(i):\n    try:\n        await asyncio.sleep(1)\n    except asyncio.CancelledError:\n        print("cleanup", i)\n        raise\n\nasync def main():\n    t = asyncio.create_task(job(1))\n    await asyncio.sleep(0)\n    t.cancel()\n    try: await t\n    except asyncio.CancelledError: pass\nasyncio.run(main())' :notes='["取消是在下一个 await 点抛 CancelledError", "资源清理必须写在 finally / except 并重抛", "不保存 task 引用可能导致任务被回收", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色", "第 13 行：与上文规则对照，观察它在整体流程里承担的角色", "第 14 行：与上文规则对照，观察它在整体流程里承担的角色", "第 15 行：与上文规则对照，观察它在整体流程里承担的角色", "第 16 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 069 讲 · asyncio 深入：Task、Future 与事件循环' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**create_task 与 gather**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import selectors, socket
sel = selectors.DefaultSelector()
print(type(sel).__name__)
```

<OutputBox title="对照写法的输出（先自己猜）" output='KqueueSelector  (macOS) / EpollSelector  (Linux)' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "import asyncio\n\nasync def job(i):\n    try:\n        await asyncio.sleep(1)\n    except asyncio.CancelledError:\n        print(\"cleanup\", i)\n        raise\n\nasync def main():\n    t = asyncio.create_task(job(1))\n    await asyncio.sleep(0)\n    t.cancel()\n    try: await t\n    except asyncio.CancelledError: pass\nasyncio.run(main())", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import selectors, socket\nsel = selectors.DefaultSelector()\nprint(type(sel).__name__)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「用裸 create_task 不保存引用，任务可能被 GC 回收，异常也」' />

## 3. 深入一步：规则与边界

**Future 状态**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**call_soon / call_later**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**TaskGroup 结构化并发**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| loop 与策略 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 用裸 create_task 不保存引用，任务可能被 GC 回收，异 |
| create_task 与 gather | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 用裸 create_task 不保存引用，任务可能被 GC 回收，异 |
| Future 状态 | 这里的关键词是「什么时候」和「代价是什么」 | 用裸 create_task 不保存引用，任务可能被 GC 回收，异 |
| call_soon / call_later | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 用裸 create_task 不保存引用，任务可能被 GC 回收，异 |
| TaskGroup 结构化并发 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 用裸 create_task 不保存引用，任务可能被 GC 回收，异 |

<Term word='loop 与策略' text='Task 是协程的调度单位，取消是「在下一个 await 点抛 CancelledError」而非强杀，所以清理逻辑必须写在 finally' />

<Callout type="warn" title="易错点" text='用裸 create_task 不保存引用，任务可能被 GC 回收，异常也永远没人读取' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：loop 与策略", "body": "**loop 与策略**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：create_task 与 gather", "body": "**create_task 与 gather**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：Future 状态", "body": "**Future 状态**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：call_soon / call_later", "body": "**call_soon / call_later**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

用 TaskGroup 做结构化并发，设置超时与失败策略，并显式处理屏蔽取消的清理段 **取消与 CancelledError**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import asyncio; print(len(asyncio.run(asyncio.gather(*[asyncio.sleep(0,i) for i in range(3)]))))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **loop 与策略** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「取消与 CancelledError」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「取消与 CancelledError」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 loop 与策略 与 取消与 CancelledError 两个关注点，并说明你的取舍。' :hints='["回到 loop 与策略 的规则", "留意易错点：用裸 create_task 不保存引用，任务可能被 GC 回收，异常也永远没人", "先让代码跑通，再补边界与异常分支"]' solution='import selectors, socket\nsel = selectors.DefaultSelector()\nprint(type(sel).__name__)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；用 TaskGroup 做结构化并发，设置超时与失败策略，并显式处理屏蔽取消的清理段' />

## 随堂检测

<Quiz no='069-1' q='在本讲讨论的「loop 与策略」语境下，下面哪一种说法是准确的？' :options='["Task 是协程的调度单位，取消是「在下一个 await 点抛 CancelledError」而非强杀，所以清理逻辑必须写在 finally", "loop 与策略 只影响代码的书写形式，不会改变任何运行时行为", "loop 与策略 在所有 Python 实现与所有版本中表现完全一致", "只要用了 loop 与策略，就不必再考虑 取消与 CancelledError 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 取消与 CancelledError 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='069-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["cleanup 1", "cleanup 1\n（无更多输出）", "AttributeError: loop 与策略 不可用"]' answer="0" output='cleanup 1' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='069-3' tpl='import ___io' :answers='["async"]' hint='回想本讲关于 loop 与策略 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["loop 与策略：loop 与策略", "create_task 与 gather：create_task 与 gather", "Future 状态：Future 状态", "call_soon / call_later：call_soon / call_later"]' :pitfalls='["用裸 create_task 不保存引用，任务可能被 GC 回收，异常也永远没人读取", "忽略版本差异，把 取消与 CancelledError 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：Task 是协程的调度单位，取消是「在下一个 await 点抛 CancelledError」而非强杀，所以清理逻辑必须写在 finally' />

## 小结与下一讲

1. loop 与策略：loop 与策略
2. create_task 与 gather：create_task 与 gather
3. 用 TaskGroup 做结构化并发，设置超时与失败策略，并显式处理屏蔽取消的清理段

[下一讲：阶段综合：并发爬虫四级演进](/concurrency/capstone)
