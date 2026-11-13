---
title: 第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event
description: 用正确的原语表达协作关系
---

<StageHeader stage='L6 · 并发与异步' level='★★★☆☆' time='40 分钟' goal='用正确的原语表达协作关系' prereq='第 061 讲 · threading：线程生命周期与共享状态' />

# 第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event

> 同步原语表达的是关系而不是「加锁」：互斥用 Lock、条件等待用 Condition、容量用 Semaphore、一次性广播用 Event。本讲的目标是「用正确的原语表达协作关系」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P062' title="本讲目标" :items='["能说清Lock 与 RLock", "能说清Condition 等待通知", "能说清Semaphore 限流", "能说清Event 广播", "能说清Barrier 汇合"]' />

## 1. 先建立直觉

**Lock 与 RLock**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**Condition 等待通知**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**Semaphore 限流**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

<ConceptDiagram type='layers3' title='第 062 讲 · Lock 与 RLock' labels='Lock 与 RLock|Condition 等待通知|Semaphore 限流|Event 广播' caption='用正确的原语表达协作关系' />

上图用本讲的三个核心概念标出了主线：**Lock 与 RLock → Condition 等待通知 → Semaphore 限流**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 Lock 与 RLock 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 [0, 1, 4, 9, 16]", "tone": "green"}, {"title": "深入边界", "desc": "厘清 Condition 等待通知 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 死锁四条件与规避 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**Lock 与 RLock**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch(i):
    return i * i

with ThreadPoolExecutor(max_workers=4) as ex:
    futs = [ex.submit(fetch, i) for i in range(5)]
    print(sorted(f.result() for f in as_completed(futs)))
```

<OutputBox title="运行结果" output='[0, 1, 4, 9, 16]' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='from concurrent.futures import ThreadPoolExecutor, as_completed\n\ndef fetch(i):\n    return i * i\n\nwith ThreadPoolExecutor(max_workers=4) as ex:\n    futs = [ex.submit(fetch, i) for i in range(5)]\n    print(sorted(f.result() for f in as_completed(futs)))' :notes='["线程池把并发度与生命周期收敛到一处", "Future 让异步结果可以像值一样传递", "取 result() 才会重新抛出任务里的异常", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**Condition 等待通知**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import threading, queue
q = queue.Queue()
def worker():
    while True:
        item = q.get()
        if item is None: break
        q.task_done()
t = threading.Thread(target=worker, daemon=True); t.start()
q.put(1); q.join(); q.put(None)
```

<OutputBox title="对照写法的输出（先自己猜）" output='(无输出，队列是线程安全的)' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "from concurrent.futures import ThreadPoolExecutor, as_completed\n\ndef fetch(i):\n    return i * i\n\nwith ThreadPoolExecutor(max_workers=4) as ex:\n    futs = [ex.submit(fetch, i) for i in range(5)]\n    print(sorted(f.result() for f in as_completed(futs)))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import threading, queue\nq = queue.Queue()\ndef worker():\n    while True:\n        item = q.get()\n        if item is None: break\n        q.task_done()\nt = threading.Thread(target=worker, daemon=True); t.start()\nq.put(1); q.join(); q.put(None)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的两个」' />

## 3. 深入一步：规则与边界

**Semaphore 限流**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**Event 广播**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**Barrier 汇合**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| Lock 与 RLock | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的 |
| Condition 等待通知 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的 |
| Semaphore 限流 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的 |
| Event 广播 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的 |
| Barrier 汇合 | 这里的关键词是「什么时候」和「代价是什么」 | 用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的 |

<Term word='Lock 与 RLock' text='同步原语表达的是关系而不是「加锁」：互斥用 Lock、条件等待用 Condition、容量用 Semaphore、一次性广播用 Event' />

<Callout type="warn" title="易错点" text='用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的两个来源' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：Lock 与 RLock", "body": "**Lock 与 RLock**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：Condition 等待通知", "body": "**Condition 等待通知**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：Semaphore 限流", "body": "**Semaphore 限流**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：Event 广播", "body": "**Event 广播**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

锁的粒度按数据而不是按代码划分，统一获取顺序，并用超时与可观测日志兜底 **死锁四条件与规避**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "from concurrent.futures import ThreadPoolExecutor as P; print(list(P(2).map(abs,[-1,-2])))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **Lock 与 RLock** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「死锁四条件与规避」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「死锁四条件与规避」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 Lock 与 RLock 与 死锁四条件与规避 两个关注点，并说明你的取舍。' :hints='["回到 Lock 与 RLock 的规则", "留意易错点：用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的两个来源", "先让代码跑通，再补边界与异常分支"]' solution='import threading, queue\nq = queue.Queue()\ndef worker():\n    while True:\n        item = q.get()\n        if item is None: break\n        q.task_done()\nt = threading.Thread(target=worker, daemon=True); t.start()\nq.put(1); q.join(); q.put(None)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；锁的粒度按数据而不是按代码划分，统一获取顺序，并用超时与可观测日志兜底' />

## 随堂检测

<Quiz no='062-1' q='在本讲讨论的「Lock 与 RLock」语境下，下面哪一种说法是准确的？' :options='["同步原语表达的是关系而不是「加锁」：互斥用 Lock、条件等待用 Condition、容量用 Semaphore、一次性广播用 Event", "Lock 与 RLock 只影响代码的书写形式，不会改变任何运行时行为", "Lock 与 RLock 在所有 Python 实现与所有版本中表现完全一致", "只要用了 Lock 与 RLock，就不必再考虑 死锁四条件与规避 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 死锁四条件与规避 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='062-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["[0, 1, 4, 9, 16]", "[0, 1, 4, 9, 16]\n（无更多输出）", "AttributeError: Lock 与 RLock 不可用"]' answer="0" output='[0, 1, 4, 9, 16]' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='062-3' tpl='from concurrent.futures ___ThreadPoolExecutor, as_completed' :answers='["import"]' hint='回想本讲关于 Lock 与 RLock 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["Lock 与 RLock：Lock 与 RLock", "Condition 等待通知：Condition 等待通知", "Semaphore 限流：Semaphore 限流", "Event 广播：Event 广播"]' :pitfalls='["用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的两个来源", "忽略版本差异，把 死锁四条件与规避 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：同步原语表达的是关系而不是「加锁」：互斥用 Lock、条件等待用 Condition、容量用 Semaphore、一次性广播用 Event' />

## 小结与下一讲

1. Lock 与 RLock：Lock 与 RLock
2. Condition 等待通知：Condition 等待通知
3. 锁的粒度按数据而不是按代码划分，统一获取顺序，并用超时与可观测日志兜底

[下一讲：线程池与 Future 模式](/concurrency/threadpool)
