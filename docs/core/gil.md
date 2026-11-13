---
title: 第 054 讲 · GIL 真相：存在原因、切换与影响边界
description: 能判断何时该用线程、进程还是异步
---

<StageHeader stage='L5 · 核心机制' level='★★★★★' time='45 分钟' goal='能判断何时该用线程、进程还是异步' prereq='第 053 讲 · 分代 GC、循环引用与 weakref' />

# 第 054 讲 · GIL 真相：存在原因、切换与影响边界

> GIL 保护的是解释器内部状态而非你的业务数据，所以多线程依然需要锁；CPU 密集任务无法靠线程利用多核，IO 密集则可以。本讲的目标是「能判断何时该用线程、进程还是异步」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P054' title="本讲目标" :items='["能说清GIL 保护什么", "能说清切换间隔与字节码边界", "能说清IO 释放 GIL", "能说清C 扩展与释放", "能说清对多核 CPU 的影响"]' />

## 1. 先建立直觉

**GIL 保护什么**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**切换间隔与字节码边界**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**IO 释放 GIL**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

<ConceptDiagram type='compare2' title='第 054 讲 · GIL 保护什么' labels='GIL 保护什么|切换间隔与字节码边界|IO 释放 GIL|C 扩展与释放' caption='能判断何时该用线程、进程还是异步' />

上图用本讲的三个核心概念标出了主线：**GIL 保护什么 → 切换间隔与字节码边界 → IO 释放 GIL**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 GIL 保护什么 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 threads done True", "tone": "green"}, {"title": "深入边界", "desc": "厘清 切换间隔与字节码边界 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 自由线程化路线 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**GIL 保护什么**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

```python
import threading
counter = 0
def bump():
    global counter
    for _ in range(100000):
        counter += 1

ts = [threading.Thread(target=bump) for _ in range(4)]
[t.start() for t in ts]; [t.join() for t in ts]
print("threads done", counter > 0)
```

<OutputBox title="运行结果" output='threads done True' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='import threading\ncounter = 0\ndef bump():\n    global counter\n    for _ in range(100000):\n        counter += 1\n\nts = [threading.Thread(target=bump) for _ in range(4)]\n[t.start() for t in ts]; [t.join() for t in ts]\nprint("threads done", counter &gt; 0)' :notes='["GIL 让字节码逐条执行，但复合操作仍可能被切换", "读—改—写跨越多条字节码，存在竞态", "需要 Lock 或原子结构才能保证计数准确", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 054 讲 · GIL 真相：存在原因、切换与影响边界' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**切换间隔与字节码边界**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import threading
lock = threading.Lock()
counter = 0
def safe():
    global counter
    for _ in range(100000):
        with lock: counter += 1
ts = [threading.Thread(target=safe) for _ in range(4)]
[t.start() for t in ts]; [t.join() for t in ts]
print(counter)
```

<OutputBox title="对照写法的输出（先自己猜）" output='400000' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "import threading\ncounter = 0\ndef bump():\n    global counter\n    for _ in range(100000):\n        counter += 1\n\nts = [threading.Thread(target=bump) for _ in range(4)]\n[t.start() for t in ts]; [t.join() for t in ts]\nprint(\"threads done\", counter &gt; 0)", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import threading\nlock = threading.Lock()\ncounter = 0\ndef safe():\n    global counter\n    for _ in range(100000):\n        with lock: counter += 1\nts = [threading.Thread(target=safe) for _ in range(4)]\n[t.start() for t in ts]; [t.join() for t in ts]\nprint(counter)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集逻辑」' />

## 3. 深入一步：规则与边界

**IO 释放 GIL**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**C 扩展与释放**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**对多核 CPU 的影响**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| GIL 保护什么 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集 |
| 切换间隔与字节码边界 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集 |
| IO 释放 GIL | 这里的关键词是「什么时候」和「代价是什么」 | 以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集 |
| C 扩展与释放 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集 |
| 对多核 CPU 的影响 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集 |

<Term word='GIL 保护什么' text='GIL 保护的是解释器内部状态而非你的业务数据，所以多线程依然需要锁；CPU 密集任务无法靠线程利用多核，IO 密集则可以' />

<Callout type="warn" title="易错点" text='以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集逻辑塞进线程只会更慢' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：GIL 保护什么", "body": "**GIL 保护什么**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：切换间隔与字节码边界", "body": "**切换间隔与字节码边界**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：IO 释放 GIL", "body": "**IO 释放 GIL**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：C 扩展与释放", "body": "**C 扩展与释放**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

CPU 密集用进程/原生扩展，IO 密集用 asyncio 或线程池，混合型任务拆成两级池 **自由线程化路线**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import sys; print(sys.version_info[:2])"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **GIL 保护什么** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「自由线程化路线」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「自由线程化路线」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 GIL 保护什么 与 自由线程化路线 两个关注点，并说明你的取舍。' :hints='["回到 GIL 保护什么 的规则", "留意易错点：以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集逻辑塞进线程", "先让代码跑通，再补边界与异常分支"]' solution='import threading\nlock = threading.Lock()\ncounter = 0\ndef safe():\n    global counter\n    for _ in range(100000):\n        with lock: counter += 1\nts = [threading.Thread(target=safe) for _ in range(4)]\n[t.start() for t in ts]; [t.join() for t in ts]\nprint(counter)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；CPU 密集用进程/原生扩展，IO 密集用 asyncio 或线程池，混合型任务拆成两级池' />

## 随堂检测

<Quiz no='054-1' q='在本讲讨论的「GIL 保护什么」语境下，下面哪一种说法是准确的？' :options='["GIL 保护的是解释器内部状态而非你的业务数据，所以多线程依然需要锁；CPU 密集任务无法靠线程利用多核，IO 密集则可以", "GIL 保护什么 只影响代码的书写形式，不会改变任何运行时行为", "GIL 保护什么 在所有 Python 实现与所有版本中表现完全一致", "只要用了 GIL 保护什么，就不必再考虑 自由线程化路线 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 自由线程化路线 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='054-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["threads done True", "threads done True\n（无更多输出）", "AttributeError: GIL 保护什么 不可用"]' answer="0" output='threads done True' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='054-3' tpl='___threading' :answers='["import"]' hint='回想本讲关于 GIL 保护什么 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["GIL 保护什么：GIL 保护什么", "切换间隔与字节码边界：切换间隔与字节码边界", "IO 释放 GIL：IO 释放 GIL", "C 扩展与释放：C 扩展与释放"]' :pitfalls='["以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集逻辑塞进线程只会更慢", "忽略版本差异，把 自由线程化路线 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：GIL 保护的是解释器内部状态而非你的业务数据，所以多线程依然需要锁；CPU 密集任务无法靠线程利用多核，IO 密集则可以' />

## 小结与下一讲

1. GIL 保护什么：GIL 保护什么
2. 切换间隔与字节码边界：切换间隔与字节码边界
3. CPU 密集用进程/原生扩展，IO 密集用 asyncio 或线程池，混合型任务拆成两级池

[下一讲：导入系统源码级：finder、loader 与缓存](/core/import-system)
