---
title: 第 064 讲 · multiprocessing：进程、Pool 与共享内存
description: 绕过 GIL 处理 CPU 密集任务
---

<StageHeader stage='L6 · 并发与异步' level='★★★★☆' time='40 分钟' goal='绕过 GIL 处理 CPU 密集任务' prereq='第 063 讲 · 线程池与 Future 模式' />

# 第 064 讲 · multiprocessing：进程、Pool 与共享内存

> 进程之间地址空间隔离，所有跨进程数据都要序列化；数据量大时，序列化成本可能超过并行收益。本讲的目标是「绕过 GIL 处理 CPU 密集任务」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P064' title="本讲目标" :items='["能说清fork / spawn / forkserver", "能说清进程间不共享内存", "能说清序列化 pickle 成本", "能说清Pool 与 chunksize", "能说清shared_memory"]' />

## 1. 先建立直觉

**fork / spawn / forkserver**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**进程间不共享内存**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**序列化 pickle 成本**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

<ConceptDiagram type='compare2' title='第 064 讲 · fork / spawn / forkserver' labels='fork / spawn / forkserver|进程间不共享内存|序列化 pickle 成本|Pool 与 chunksize' caption='绕过 GIL 处理 CPU 密集任务' />

上图用本讲的三个核心概念标出了主线：**fork / spawn / forkserver → 进程间不共享内存 → 序列化 pickle 成本**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 fork / spawn / forkserver 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 [0, 1, 4, 9, 16]", "tone": "green"}, {"title": "深入边界", "desc": "厘清 进程间不共享内存 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 进程启动开销 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**fork / spawn / forkserver**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

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

<LineByLine code='from concurrent.futures import ThreadPoolExecutor, as_completed\n\ndef fetch(i):\n    return i * i\n\nwith ThreadPoolExecutor(max_workers=4) as ex:\n    futs = [ex.submit(fetch, i) for i in range(5)]\n    print(sorted(f.result() for f in as_completed(futs)))' :notes='["线程池把并发度与生命周期收敛到一处", "Future 让异步结果可以像值一样传递", "取 result() 才会重新抛出任务里的异常", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 064 讲 · multiprocessing：进程、Pool 与共享内存' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**进程间不共享内存**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

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

<Compare :panels='[{"label": "主写法", "code": "from concurrent.futures import ThreadPoolExecutor, as_completed\n\ndef fetch(i):\n    return i * i\n\nwith ThreadPoolExecutor(max_workers=4) as ex:\n    futs = [ex.submit(fetch, i) for i in range(5)]\n    print(sorted(f.result() for f in as_completed(futs)))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import threading, queue\nq = queue.Queue()\ndef worker():\n    while True:\n        item = q.get()\n        if item is None: break\n        q.task_done()\nt = threading.Thread(target=worker, daemon=True); t.start()\nq.put(1); q.join(); q.put(None)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「在 spawn 平台把不可 pickle 的对象（lambda、打开的连」' />

## 3. 深入一步：规则与边界

**序列化 pickle 成本**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**Pool 与 chunksize**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**shared_memory**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| fork / spawn / forkserver | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 在 spawn 平台把不可 pickle 的对象（lambda、打开 |
| 进程间不共享内存 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 在 spawn 平台把不可 pickle 的对象（lambda、打开 |
| 序列化 pickle 成本 | 这里的关键词是「什么时候」和「代价是什么」 | 在 spawn 平台把不可 pickle 的对象（lambda、打开 |
| Pool 与 chunksize | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 在 spawn 平台把不可 pickle 的对象（lambda、打开 |
| shared_memory | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 在 spawn 平台把不可 pickle 的对象（lambda、打开 |

<Term word='fork / spawn / forkserver' text='进程之间地址空间隔离，所有跨进程数据都要序列化；数据量大时，序列化成本可能超过并行收益' />

<Callout type="warn" title="易错点" text='在 spawn 平台把不可 pickle 的对象（lambda、打开的连接）传给子进程，会在启动时报莫名其妙的错误' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：fork / spawn / forkserver", "body": "**fork / spawn / forkserver**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：进程间不共享内存", "body": "**进程间不共享内存**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：序列化 pickle 成本", "body": "**序列化 pickle 成本**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：Pool 与 chunksize", "body": "**Pool 与 chunksize**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

大数组用 shared_memory / 内存映射，任务粒度用 chunksize 调平，避免在进程间传大对象 **进程启动开销**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "from concurrent.futures import ThreadPoolExecutor as P; print(list(P(2).map(abs,[-1,-2])))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **fork / spawn / forkserver** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「进程启动开销」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「进程启动开销」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 fork / spawn / forkserver 与 进程启动开销 两个关注点，并说明你的取舍。' :hints='["回到 fork / spawn / forkserver 的规则", "留意易错点：在 spawn 平台把不可 pickle 的对象（lambda、打开的连接）传给", "先让代码跑通，再补边界与异常分支"]' solution='import threading, queue\nq = queue.Queue()\ndef worker():\n    while True:\n        item = q.get()\n        if item is None: break\n        q.task_done()\nt = threading.Thread(target=worker, daemon=True); t.start()\nq.put(1); q.join(); q.put(None)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；大数组用 shared_memory / 内存映射，任务粒度用 chunksize 调平，避免在进程间传大对象' />

## 随堂检测

<Quiz no='064-1' q='在本讲讨论的「fork / spawn / forkserver」语境下，下面哪一种说法是准确的？' :options='["进程之间地址空间隔离，所有跨进程数据都要序列化；数据量大时，序列化成本可能超过并行收益", "fork / spawn / forkserver 只影响代码的书写形式，不会改变任何运行时行为", "fork / spawn / forkserver 在所有 Python 实现与所有版本中表现完全一致", "只要用了 fork / spawn / forkserver，就不必再考虑 进程启动开销 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 进程启动开销 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='064-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["[0, 1, 4, 9, 16]", "[0, 1, 4, 9, 16]\n（无更多输出）", "AttributeError: fork / spawn / forkserver 不可用"]' answer="0" output='[0, 1, 4, 9, 16]' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='064-3' tpl='from concurrent.futures ___ThreadPoolExecutor, as_completed' :answers='["import"]' hint='回想本讲关于 fork / spawn / forkserver 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["fork / spawn / forkserver：fork / spawn / forkserver", "进程间不共享内存：进程间不共享内存", "序列化 pickle 成本：序列化 pickle 成本", "Pool 与 chunksize：Pool 与 chunksize"]' :pitfalls='["在 spawn 平台把不可 pickle 的对象（lambda、打开的连接）传给子进程，会在启动时报莫名其妙的错误", "忽略版本差异，把 进程启动开销 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：进程之间地址空间隔离，所有跨进程数据都要序列化；数据量大时，序列化成本可能超过并行收益' />

## 小结与下一讲

1. fork / spawn / forkserver：fork / spawn / forkserver
2. 进程间不共享内存：进程间不共享内存
3. 大数组用 shared_memory / 内存映射，任务粒度用 chunksize 调平，避免在进程间传大对象

[下一讲：进程间通信：Queue、Pipe 与信号](/concurrency/ipc)
