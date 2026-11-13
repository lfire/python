---
title: 第 063 讲 · 线程池与 Future 模式
description: 管理并发度、结果收集与失败传播
---

<StageHeader stage='L6 · 并发与异步' level='★★★☆☆' time='35 分钟' goal='管理并发度、结果收集与失败传播' prereq='第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event' />

# 第 063 讲 · 线程池与 Future 模式

> 线程池的价值是把「创建销毁」与「并发度控制」收敛到一处，Future 则把异步结果变成可传递的值。本讲的目标是「管理并发度、结果收集与失败传播」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P063' title="本讲目标" :items='["能说清Executor 抽象", "能说清submit / map / as_completed", "能说清Future 状态机", "能说清并发度与队列", "能说清取消语义"]' />

## 1. 先建立直觉

**Executor 抽象**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**submit / map / as_completed**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**Future 状态机**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

<ConceptDiagram type='hub4' title='第 063 讲 · Executor 抽象' labels='Executor 抽象|submit / map / as_completed|Future 状态机|并发度与队列' caption='管理并发度、结果收集与失败传播' />

上图用本讲的三个核心概念标出了主线：**Executor 抽象 → submit / map / as_completed → Future 状态机**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 Executor 抽象 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 [0, 1, 2, 3, 4]", "tone": "green"}, {"title": "深入边界", "desc": "厘清 submit / map / as_completed 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 异常传播 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**Executor 抽象**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

```python
import threading, time
lock = threading.Lock()
shared = []
def writer(i):
    with lock:
        shared.append(i)
ts = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
[t.start() for t in ts]; [t.join() for t in ts]
print(sorted(shared))
```

<OutputBox title="运行结果" output='[0, 1, 2, 3, 4]' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='import threading, time\nlock = threading.Lock()\nshared = []\ndef writer(i):\n    with lock:\n        shared.append(i)\nts = [threading.Thread(target=writer, args=(i,)) for i in range(5)]\n[t.start() for t in ts]; [t.join() for t in ts]\nprint(sorted(shared))' :notes='["锁把复合操作变成临界区", "with 保证异常时也释放锁", "共享可变状态是并发 bug 的主要来源", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 063 讲 · 线程池与 Future 模式' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**submit / map / as_completed**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
from multiprocessing import Pool
def sq(x): return x*x
if __name__ == "__main__":
    with Pool(2) as p: print(p.map(sq, [1,2,3]))
```

<OutputBox title="对照写法的输出（先自己猜）" output='[1, 4, 9]' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "import threading, time\nlock = threading.Lock()\nshared = []\ndef writer(i):\n    with lock:\n        shared.append(i)\nts = [threading.Thread(target=writer, args=(i,)) for i in range(5)]\n[t.start() for t in ts]; [t.join() for t in ts]\nprint(sorted(shared))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "from multiprocessing import Pool\ndef sq(x): return x*x\nif __name__ == \"__main__\":\n    with Pool(2) as p: print(p.map(sq, [1,2,3]))", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的队列」' />

## 3. 深入一步：规则与边界

**Future 状态机**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**并发度与队列**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**取消语义**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| Executor 抽象 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的 |
| submit / map / as_completed | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的 |
| Future 状态机 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的 |
| 并发度与队列 | 这里的关键词是「什么时候」和「代价是什么」 | 无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的 |
| 取消语义 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的 |

<Term word='Executor 抽象' text='线程池的价值是把「创建销毁」与「并发度控制」收敛到一处，Future 则把异步结果变成可传递的值' />

<Callout type="warn" title="易错点" text='无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的队列压垮' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：Executor 抽象", "body": "**Executor 抽象**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：submit / map / as_completed", "body": "**submit / map / as_completed**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：Future 状态机", "body": "**Future 状态机**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：并发度与队列", "body": "**并发度与队列**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}]' />

<SequenceDiagram title='第 063 讲 · 调用时序' caption='从触发到收尾，标出可能失败的位置' :actors='["调用方", "处理逻辑", "依赖资源"]' :steps='[{"from": "调用方", "to": "处理逻辑", "label": "发起调用", "note": "Executor 抽象", "kind": "call"}, {"from": "处理逻辑", "to": "处理逻辑", "label": "校验状态", "note": "submit / map /", "kind": "self"}, {"from": "处理逻辑", "to": "依赖资源", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "依赖资源", "to": "处理逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "处理逻辑", "to": "调用方", "label": "返回或失败", "note": "清理资源", "kind": "return"}]' />

## 4. 工程实践

按依赖类型分池、设置有界队列与超时、对 Future 逐一取结果以暴露异常 **异常传播**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "from concurrent.futures import ThreadPoolExecutor as P; print(list(P(2).map(abs,[-1,-2])))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **Executor 抽象** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「异常传播」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「异常传播」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 Executor 抽象 与 异常传播 两个关注点，并说明你的取舍。' :hints='["回到 Executor 抽象 的规则", "留意易错点：无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的队列压垮", "先让代码跑通，再补边界与异常分支"]' solution='from multiprocessing import Pool\ndef sq(x): return x*x\nif __name__ == "__main__":\n    with Pool(2) as p: print(p.map(sq, [1,2,3]))' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；按依赖类型分池、设置有界队列与超时、对 Future 逐一取结果以暴露异常' />

## 随堂检测

<Quiz no='063-1' q='在本讲讨论的「Executor 抽象」语境下，下面哪一种说法是准确的？' :options='["线程池的价值是把「创建销毁」与「并发度控制」收敛到一处，Future 则把异步结果变成可传递的值", "Executor 抽象 只影响代码的书写形式，不会改变任何运行时行为", "Executor 抽象 在所有 Python 实现与所有版本中表现完全一致", "只要用了 Executor 抽象，就不必再考虑 异常传播 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 异常传播 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='063-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["[0, 1, 2, 3, 4]", "[0, 1, 2, 3, 4]\n（无更多输出）", "AttributeError: Executor 抽象 不可用"]' answer="0" output='[0, 1, 2, 3, 4]' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='063-3' tpl='___threading, time' :answers='["import"]' hint='回想本讲关于 Executor 抽象 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["Executor 抽象：Executor 抽象", "submit / map / as_completed：submit / map / as_completed", "Future 状态机：Future 状态机", "并发度与队列：并发度与队列"]' :pitfalls='["无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的队列压垮", "忽略版本差异，把 异常传播 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：线程池的价值是把「创建销毁」与「并发度控制」收敛到一处，Future 则把异步结果变成可传递的值' />

## 小结与下一讲

1. Executor 抽象：Executor 抽象
2. submit / map / as_completed：submit / map / as_completed
3. 按依赖类型分池、设置有界队列与超时、对 Future 逐一取结果以暴露异常

[下一讲：multiprocessing：进程、Pool 与共享内存](/concurrency/multiprocessing)
