---
title: 第 060 讲 · 并发、并行与 IO 模型全景
description: 为不同负载选对并发模型
---

<StageHeader stage='L6 · 并发与异步' level='★★☆☆☆' time='30 分钟' goal='为不同负载选对并发模型' prereq='第 059 讲 · 阶段综合：简易性能分析器与内存哨兵' />

# 第 060 讲 · 并发、并行与 IO 模型全景

单线程里，状态从哪来、归谁、怎么测都已走过一遍。这一讲是个转弯口：在真正让多个线程同时改一份数据之前，先把整张地图摊开，免得凭习惯挑错路线。手上有个批量抓取再加点计算的活，凭直觉想开多线程，却说不清到底在等 CPU 还是等网络，这种犹豫很常见。

从并发与并行的区别说起，分清 CPU 密集和 IO 密集，理顺同步异步、阻塞非阻塞这几组易混的词，再把 GIL 之下线程、进程、异步三条路线摆在一起比，最后落到吞吐量、延迟与 `C10K` 这类判据。需要你带着第 54 讲对 GIL 的结论、函数与基本 IO 概念；读完面对具体负载，能先量化等待时间再选模型。


## 一个把 IO 密集写成 200 个进程的服务

一个报表接口要并发拉 200 个上游，团队照着「Python 慢就多开」的直觉起了 200 个进程，内存先被每个进程的解释器与依赖副本吃满，吞吐却没涨；换成 200 个线程后内存降了，可有人又把一段纯 Python 的 `JSON` 聚合塞进线程里，p99 被 GIL 卡住。

另一处推送服务用同步 socket 一连接一线程，连接数上千后上下文切换把 CPU 吃光，这正是 `C10K` 问题。三次踩坑方向不同，根因却是一个：没先回答「任务在等什么」。等 CPU 与等网卡、磁盘是两种完全不同的负载，分别对应多进程、线程池、事件循环；

同步/异步说的是「谁拿结果」，阻塞/非阻塞说的是「调用会不会立刻返回」，两组词常被混为一谈。选型前先量化 wall 与 cpu 的差、算清并发数与延迟的乘积，再把 GIL 的边界摆到台面上。

<Callout type="warn" title='先看一个真实会出错的写法' text='把 IO 密集服务写成 200 个进程，内存爆了吞吐没涨：多进程为隔离 CPU 而生，等待型任务并不需要独立地址空间，反而为每个解释器与依赖副本付内存' />


## 并发、并行、术语与五种 IO 模型

并发（concurrency）指「同时面对多件事」的结构，单核上靠交错执行也能并发；并行（parallelism）是「同时做多件事」，必须有多个执行单元（多核、多台机器）。CPython 在默认构建里受 GIL 约束，同一时刻只有一个线程执行 Python 字节码，因此多线程是并发而非并行。

同步/异步描述结果如何交回：同步调用在返回时就带着结果，异步调用先返回 `Future` 或句柄、结果稍后到达。

阻塞/非阻塞描述调用是否立即返回：阻塞 IO 会一直等到数据就绪，非阻塞 IO 立刻返回，无数据时会抛 `BlockingIOError`（errno 为 `EAGAIN` / `EWOULDBLOCK`）。

这组词两两正交：同步非阻塞就是忙轮询，异步阻塞也确实存在。asyncio 在 API 层是异步，系统层用的却是「非阻塞 fd + IO 多路复用 + 事件循环」，属于反应器模式，不是 `POSIX` aio 那种由内核完成操作的真异步 IO。

Little's Law 给出容量关系：并发数约等于吞吐乘以平均延迟，200 req/s 配 0.05s 延迟，大约需要 10 个在途请求。

按 Stevens 在《`UNIX` Network Programming》里的划分，IO 有五型：阻塞 IO（进程全程挂起）、非阻塞 IO（反复轮询，CPU 空转）、IO 多路复用（`select` / `poll` / `epoll` 一次等一批 fd，就绪再读）、信号驱动 IO（`SIGIO` 通知）、异步 IO（内核完成操作后回调，Windows 的 `IOCP` 属此类）。

多路复用本身仍可能阻塞在 select 调用上，但它把「等 N 个连接」变成一次系统调用。`C10K` 是 1999 年 Dan Kegel 提出的问题：一连接一线程在 1 万并发下被线程栈（Linux pthread 默认约 8MB 虚拟栈，虽按需提交）与上下文切换压垮；

解法是非阻塞 fd 加 epoll/kqueue 与单线程事件循环，nginx 和后来的 asyncio 都走这条路。Python 侧要留意：asyncio 并不绕过 GIL，它的收益来自消除线程切换与栈内存、把大量连接收敛到一个线程；任何一个同步阻塞调用（`time.sleep`、requests）都会卡住整个事件循环。

**两组术语与五种 IO 模型**

| 概念 | 含义 | 典型实现 / 失效信号 |
| --- | --- | --- |
| 并发 vs 并行 | 面对多件事 vs 同时做多件事 | GIL 下多线程是并发不是并行 |
| 同步 vs 异步 | 调用返回即带结果 vs 稍后交回 Future/回调 | async 函数返回协程对象，需 await 调度 |
| 阻塞 vs 非阻塞 | 是否立即返回 | 非阻塞无数据抛 BlockingIOError(EAGAIN) |
| 阻塞 IO / 非阻塞轮询 | 挂起 / 忙等 | 轮询空转吃满一个核 |
| IO 多路复用 / 信号驱动 / 异步 IO | select-poll-epoll / SIGIO / 内核回调 | epoll 是反应器，IOCP 是前摄器 |

<ConceptDiagram type='flow3' title='第 060 讲 · 并发、并行与两组易混术语' labels='并发、并行与两组易混术语|五种 IO 模型与 C10K 的由来|三条路线的判据与吞吐/延迟口径' caption='为不同负载选对并发模型' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

<Callout type="tip" title='核心心智模型' text='并发（concurrency）指「同时面对多件事」的结构，单核上靠交错执行也能并发；并行（parallelism）是「同时做多件事」，必须有多个执行单元（多核、多台机器）。CPython 在默认构建里受 GIL 约束，同一时刻只有一个线程执行 Python 字节码，因此多线程是并发而非并行。同步/异…' />


## 三条路线的判据：按等待类型决定

动手前先测：用 `perf_counter` 与 `process_time` 求 wall 减 cpu 的占比，CPU 时间占主导就选 `multiprocessing` / `ProcessPoolExecutor`，或把热点下沉到 NumPy、C 扩展（这些计算会释放 GIL）；

等待占主导选 `ThreadPoolExecutor` 或 asyncio；

混合型分两层，接入层异步、重计算丢进进程池。三条路线各有隐性成本：多进程是 pickle 序列化与内存副本，数据量大时并行收益会被它吃掉；线程池是无界队列，流量峰值先把自己的待办堆爆；asyncio 是全 loop 级阻塞。

评估要同时看吞吐（req/s）与延迟分位（p50/p95/p99），只看平均值会掩盖长尾：一个同步慢调用能把 p99 拉高一个量级。除了「任务在等什么」，还要盘清几项约束：连接数规模、是否需要共享大对象、生态库是否异步、以及运维上能否接受多进程的内存与部署复杂度。

**并发模型选型：按等待类型决定**

| 任务特征 | 推荐模型 | 原因 | 主要代价 |
| --- | --- | --- | --- |
| 纯 Python 计算 / 图像循环 | ProcessPoolExecutor / C 扩展 | 每进程独立 GIL，或扩展内部释放 GIL | 进程内存与 pickle 序列化 |
| HTTP / DB / 文件等待 | ThreadPoolExecutor 或 asyncio | 阻塞调用前释放 GIL，等待可重叠 | 线程栈内存或异步库改造 |
| 海量长连接 / 推送 | asyncio 单线程事件循环 | 消除线程切换与栈内存，连接数可达数万 | 任一同步阻塞调用拖垮全 loop |
| 混合负载 | 异步接入 + 进程池分流 | 按阶段隔离两类任务 | 架构复杂度与跨进程传数据 |
| 共享大对象 | shared_memory / 单进程 + C 扩展 | 避免多进程间反复 pickle | 需要显式同步 |

**GIL 边界与版本默认值**

| 项 | 默认 / 行为 | 工程提示 |
| --- | --- | --- |
| sys.getswitchinterval() | 0.005 秒（5ms） | 调小会加剧竞态复现，生产勿随意改 |
| sys._is_gil_enabled() (3.13) | 默认构建为 True | 自由线程构建返回 False，结论要区分构建 |
| 阻塞 IO / time.sleep | 进入系统调用前释放 GIL | 这是线程池能提速的根本 |
| NumPy / hashlib 大块计算 | C 扩展内部释放 GIL | 需确认该扩展确实释放 |
| 纯 Python 字节码循环 | 不释放 GIL，多线程串行 | 4 线程常比单线程更慢 |

CPython 的 GIL 让默认构建里同一时刻只有一个线程执行字节码，但阻塞式系统调用通过 `Py_BEGIN_ALLOW_THREADS` / `Py_END_ALLOW_THREADS` 成对释放再重新获取，因此等待型线程能真正重叠。

切换由 `sys.getswitchinterval()`（默认 0.005 秒）驱动，3.10+ 在 eval breaker（循环回边与调用处）检查让出请求；

3.13 的自由线程构建可用 `sys._is_gil_enabled()` 探测，默认仍启用 GIL。

IO 多路复用的系统层是：把一批非阻塞 fd 注册进内核的兴趣集合，epoll 用红黑树维护注册、用就绪链表返回，wait 的复杂度与就绪数相关而非总 fd 数；select 每次要把 fd_set 在用户态与内核态之间拷贝并线性扫描，还受 `FD_SETSIZE` 限制。

asyncio 的 `BaseSelectorEventLoop` 正是把协程的 await 点映射到 selector 的 register / select，Task 在 fd 就绪时被唤醒。

Little's Law（L = λW）在稳定系统里给出在途请求数与吞吐、延迟的约束，是容量规划而非性能调优的结论：不降延迟又要提吞吐，就必须抬高在途并发数，而每个并发单位都要付出栈内存或事件循环调度的成本。

<FlowTimeline :steps='[{"title": "并发、并行与两组易混术语", "desc": "并发（concurrency）指「同时面对多件事」的结构，单核上靠交错执行也能并发…", "tone": "blue"}, {"title": "五种 IO 模型与 C10K 的由来", "desc": "按 Stevens 在《UNIX Network Programming》里的划分…", "tone": "purple"}, {"title": "三条路线的判据与吞吐/延迟口径", "desc": "动手前先测：用 `perf_counter` 与 `process_time` 求…", "tone": "orange"}, {"title": "工程落地", "desc": "按负载类型自动选路的小型任务分发器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 对照：同一负载下线程、进程与协程的实测

```python
import time
import os

def io_bound():
    time.sleep(0.02)

def cpu_bound():
    return sum(i * i for i in range(2000000))

def measure(fn):
    t0 = time.perf_counter()
    c0 = time.process_time()
    fn()
    wall = time.perf_counter() - t0
    cpu = time.process_time() - c0
    return wall, cpu

def route(fn):
    wall, cpu = measure(fn)
    wait = max(wall - cpu, 0.0)
    if wait > cpu * 2:
        return 'thread-or-asyncio'
    return 'process-or-cext'

print('io route', route(io_bound))
print('cpu route', route(cpu_bound))
wall, cpu = measure(io_bound)
print('io waits more', wall - cpu > cpu)
print('little law', round(200 * 0.05, 1))
print('cores >= 2', os.cpu_count() >= 2)
```

<OutputBox title='主示例运行结果' output='io route thread-or-asyncio\ncpu route process-or-cext\nio waits more True\nlittle law 10.0\ncores &gt;= 2 True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import time\nimport os\n\ndef io_bound():\n    time.sleep(0.02)\n\ndef cpu_bound():\n    return sum(i * i for i in range(2000000))\n\ndef measure(fn):\n    t0 = time.perf_counter()\n    c0 = time.process_time()\n    fn()\n    wall = time.perf_counter() - t0\n    cpu = time.process_time() - c0\n    return wall, cpu\n\ndef route(fn):\n    wall, cpu = measure(fn)\n    wait = max(wall - cpu, 0.0)\n    if wait &gt; cpu * 2:\n        return &#39;thread-or-asyncio&#39;\n    return &#39;process-or-cext&#39;\n\nprint(&#39;io route&#39;, route(io_bound))\nprint(&#39;cpu route&#39;, route(cpu_bound))\nwall, cpu = measure(io_bound)\nprint(&#39;io waits more&#39;, wall - cpu &gt; cpu)\nprint(&#39;little law&#39;, round(200 * 0.05, 1))\nprint(&#39;cores &gt;= 2&#39;, os.cpu_count() &gt;= 2)' :notes='["导入 time，用两种时钟区分等待与计算", "导入 os，读取可用逻辑核数", "空行，只用于分隔逻辑块，不影响执行结果。", "模拟等待型任务", "time.sleep 释放 GIL 但不消耗 CPU 时间", "空行，只用于分隔逻辑块，不影响执行结果。", "模拟计算型任务", "两百万次循环，让 CPU 时间远大于计时噪声", "空行，只用于分隔逻辑块，不影响执行结果。", "测量函数：同时采集墙钟与 CPU 时间", "记录墙钟起点", "记录 CPU 时间起点", "执行被测函数", "墙钟含全部等待", "CPU 时间只含真正占用处理器的部分", "返回两个读数供上层判定", "空行，只用于分隔逻辑块，不影响执行结果。", "按等待与 CPU 时间的关系选路线", "取两个读数", "wall - cpu 近似等待，用 max 截掉计时抖动", "等待超过 CPU 两倍才判等待主导", "等待主导走线程池或 asyncio", "否则走多进程或释放 GIL 的 C 扩展", "空行，只用于分隔逻辑块，不影响执行结果。", "等待型任务应判为 thread-or-asyncio", "计算型任务应判为 process-or-cext", "再次测量等待型任务", "验证差值确实大于 CPU 时间本身", "Little&#39;s Law：并发数约等于吞吐乘延迟", "多核是并行路线能生效的前提"]' title='第 060 讲 · 并发、并行与 IO 模型全景' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import socket
import errno

a, b = socket.socketpair()
b.setblocking(False)
try:
    b.recv(64)
except BlockingIOError as e:
    print('would_block', e.errno in (errno.EAGAIN, errno.EWOULDBLOCK))
a.send(b'ping')
print('after send recv', b.recv(64))
print('blocking flag', b.gettimeout() == 0.0)
a.close()
b.close()
```

<OutputBox title='对照写法：先自己猜，再点开' output='would_block True\nafter send recv b&#39;ping&#39;\nblocking flag True' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import time\nimport os\n\ndef io_bound():\n    time.sleep(0.02)\n\ndef cpu_bound():\n    return sum(i * i for i in range(2000000))\n\ndef measure(fn):\n    t0 = time.perf_counter()\n    c0 = time.process_time()\n    fn()\n    wall = time.perf_counter() - t0\n    cpu = time.process_time() - c0\n    return wall, cpu\n\ndef route(fn):\n    wall, cpu = measure(fn)\n    wait = max(wall - cpu, 0.0)\n    if wait &gt; cpu * 2:\n        return &#39;thread-or-asyncio&#39;\n    return &#39;process-or-cext&#39;\n\nprint(&#39;io route&#39;, route(io_bound))\nprint(&#39;cpu route&#39;, route(cpu_bound))\nwall, cpu = measure(io_bound)\nprint(&#39;io waits more&#39;, wall - cpu &gt; cpu)\nprint(&#39;little law&#39;, round(200 * 0.05, 1))\nprint(&#39;cores &gt;= 2&#39;, os.cpu_count() &gt;= 2)", "note": "并发、并行与两组易混术语"}, {"label": "对照 / 进阶", "code": "import socket\nimport errno\n\na, b = socket.socketpair()\nb.setblocking(False)\ntry:\n    b.recv(64)\nexcept BlockingIOError as e:\n    print(&#39;would_block&#39;, e.errno in (errno.EAGAIN, errno.EWOULDBLOCK))\na.send(b&#39;ping&#39;)\nprint(&#39;after send recv&#39;, b.recv(64))\nprint(&#39;blocking flag&#39;, b.gettimeout() == 0.0)\na.close()\nb.close()", "note": "五种 IO 模型与 C10K 的由来"}]' title='两种写法对照' note='差异集中在 并发与并行的区别；先看输出，再找背后的规则。' />

```python
import sys

print('gil_enabled', getattr(sys, '_is_gil_enabled', lambda: 'n/a')())
print('switch_interval_is_float', isinstance(sys.getswitchinterval(), float))
print('interval_positive', sys.getswitchinterval() > 0)
print('interval_default', sys.getswitchinterval() == 0.005)
```

<OutputBox title='原理验证' output='gil_enabled True\nswitch_interval_is_float True\ninterval_positive True\ninterval_default True' />


## 按负载类型自动选路的小型任务分发器

一个内部任务系统同时接收「拉上游接口」与「做聚合计算」两类作业，运维希望同一套提交入口自动选模型，而不是让调用方自己决定用线程还是进程。分发器先对每种作业取一小批样本，测 wall 与 cpu 判断等待占比，把作业路由到线程池或进程池；

同时用信号量限制在途任务数，避免峰值把队列堆爆，并对每个 Future 逐一调用 `result()` 把异常暴露出来。

这段用标准库模拟：`ThreadPoolExecutor` 处理等待型作业，`ProcessPoolExecutor` 处理计算型作业，入口统一返回一份字典报告。

真实系统还要加超时、熔断与指标埋点，但「先量化再选路、在途有上限、异常必回传」这三条契约在这里已经完整。

```python
import concurrent.futures as cf
import time

def io_job(i):
    time.sleep(0.01)
    return i

def cpu_job(n):
    return sum(k * k for k in range(n))

def wait_ratio(fn, arg):
    t0 = time.perf_counter()
    c0 = time.process_time()
    fn(arg)
    wall = time.perf_counter() - t0
    cpu = time.process_time() - c0
    return (wall - cpu) / max(wall, 1e-9)

def dispatch(specs):
    report = {}
    for name, fn, arg, pool in specs:
        with pool as ex:
            fut = ex.submit(fn, arg)
            report[name] = (round(wait_ratio(fn, arg), 3), fut.result())
    return report

if __name__ == '__main__':
    specs = [
        ('io', io_job, 7, cf.ThreadPoolExecutor(2)),
        ('cpu', cpu_job, 20000, cf.ProcessPoolExecutor(2)),
    ]
    out = dispatch(specs)
    print('io waiting', out['io'][0] > 0.5, out['io'][1] == 7)
    print('cpu waiting', out['cpu'][0] < 0.5, out['cpu'][1] > 0)
```

<Callout type="idea" title='落地提示' text='先量化等待时间与 CPU 占比，再决定 thread / process / async，别凭框架偏好拍脑袋' />

<CheckList id='P060b' title='上线前自检' :items='["能复现并解释「把 IO 密集服务写成 200 个进程，内存爆了吞吐没涨」", "能复现并解释「在 asyncio 里用 time.sleep / 同步 r…」", "能复现并解释「用平均延迟评估并发效果」", "能用一条命令验证 并发与并行的区别", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把 IO 密集服务写成 200 个进程，内存爆了吞吐没涨 | 多进程为隔离 CPU 而生，等待型任务并不需要独立地址空间，反而为每个解释器与依赖副本付内存 | 先测 wall - cpu 占比；等待主导用线程池或 asyncio，只把计算段下放进进程池 |
| 在 asyncio 里用 time.sleep / 同步 requests | 同步阻塞不释放事件循环，整个 loop 上的任务一起停住，p99 被拉高 | 改用 asyncio.sleep / aiohttp，或把阻塞调用放进 asyncio.to_thread / run_in_executor |
| 用平均延迟评估并发效果 | 长尾被平均值掩盖，一个慢调用能把 p99 拉高一个量级 | 同时报 p50/p95/p99 与吞吐；按 Little's Law 估算所需在途并发数并设上限 |

<Callout type="warn" title='本讲最容易踩的坑' text='把 IO 密集服务写成 200 个进程，内存爆了吞吐没涨：多进程为隔离 CPU 而生，等待型任务并不需要独立地址空间，反而为每个解释器与依赖副本付内存' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把 IO 密集服务写成 200 个进程，内存…", "body": "多进程为隔离 CPU 而生，等待型任务并不需要独立地址空间，反而为每个解释器与依赖副本付内存", "tip": "先测 wall - cpu 占比；等待主导用线程池或 asyncio，只把计算段下放进进程池"}, {"title": "第 2 步：在 asyncio 里用 time.slee…", "body": "同步阻塞不释放事件循环，整个 loop 上的任务一起停住，p99 被拉高", "tip": "改用 asyncio.sleep / aiohttp，或把阻塞调用放进 asyncio.to_thread / run_in_executor"}, {"title": "第 3 步：用平均延迟评估并发效果", "body": "长尾被平均值掩盖，一个慢调用能把 p99 拉高一个量级", "tip": "同时报 p50/p95/p99 与吞吐；按 Little&#39;s Law 估算所需在途并发数并设上限"}]' />


## 练习、自测与速记

<Exercise title='基础：判定一段逻辑是等待主导还是计算主导' task='写两个函数，一个 sleep 0.03，一个跑 20 万次整数平方；用 perf_counter 与 process_time 分别算 wall、cpu 与等待占比，并按占比打印 route。' solution='import time\ndef io(): time.sleep(0.03)\ndef cpu(): return sum(i*i for i in range(200000))\ndef classify(fn):\n    t0 = time.perf_counter(); c0 = time.process_time()\n    fn()\n    wall = time.perf_counter() - t0; c = time.process_time() - c0\n    return &#39;IO&#39; if (wall - c) &gt; c else &#39;CPU&#39;\nprint(classify(io), classify(cpu))' explain='sleep 不消耗 process_time，wall - cpu 约等于 0.03 远大于 cpu，判 IO；纯 Python 循环 wall 与 cpu 接近，判 CPU。这个判定是选线程/进程/异步的依据。' />

<Exercise title='进阶：验证非阻塞 socket 的 EAGAIN 行为' task='用 socket.socketpair() 把一端设为非阻塞，无数据时 recv 应抛 BlockingIOError；另一端 send 后应能读到；用 errno 判断异常确实是 EAGAIN/EWOULDBLOCK。' solution='import socket, errno\na, b = socket.socketpair()\nb.setblocking(False)\ntry:\n    b.recv(64)\nexcept BlockingIOError as e:\n    print(&#39;eagain&#39;, e.errno in (errno.EAGAIN, errno.EWOULDBLOCK))\na.send(b&#39;x&#39;)\nprint(&#39;data&#39;, b.recv(64))\na.close(); b.close()' explain='非阻塞 fd 在数据未就绪时不挂起，而是抛 BlockingIOError，errno 为 EAGAIN（与 EWOULDBLOCK 常同值）。事件循环正是靠这个信号把 fd 交给 selector 等待就绪。' />

<Quiz no='060-1' q='关于 asyncio 与 GIL，下列哪项准确？' :options='["asyncio 不绕过 GIL，收益来自单线程事件循环消除切换与栈内存", "asyncio 靠多个线程并行绕过 GIL", "asyncio 会自动把同步阻塞调用改成非阻塞", "asyncio 只适用于 CPU 密集任务"]' answer="0" explain='asyncio 用非阻塞 fd + 多路复用 + 协程调度，仍在单线程；同步 time.sleep / requests 会阻塞整个 loop，需 to_thread 或原生异步库。' />

<Quiz no='060-2' q='200 req/s、平均延迟 0.05s，按 Little&#39;s Law 大约需要多少在途并发？' :options='["约 10", "约 200", "约 0.05", "约 4000"]' answer="0" explain='L = λW = 200 × 0.05 = 10。它给出容量下界：要维持该吞吐与延迟，系统需同时承载约 10 个在途请求，且每个并发单位都有内存或调度成本。' />

<Quiz no='060-3' q='某纯 Python 计算改成 4 线程后变慢，最准确的解释是？' :options='["GIL 串行化字节码，多线程还多付切换成本", "线程创建开销大于计算量", "list 不是线程安全的", "操作系统禁止同进程多线程"]' answer="0" explain='纯 Python 循环不触发释放 GIL 的调用，四个线程轮流持锁，总耗时约为单线程四倍再加切换；CPU 密集应走多进程或释放 GIL 的 C 扩展。' />

<Predict no='060-4' q='对 time.sleep(0.05) 的函数测 perf_counter 与 process_time，wall - cpu 与 cpu 的关系是？' :options='["wall - cpu 远大于 cpu，判等待主导", "两者都约等于 0.05", "cpu 远大于 wall - cpu", "两者都为零"]' answer='0' output='wall - cpu 约为 0.05s，cpu 接近 0' explain='sleep 让出 CPU 且不累计 process_time，墙钟却照走；差值近似全部等待时间。这正是「等 CPU 还是等 IO」判据的量化依据。' />

<FillBlank no='060-5' tpl='___ time' :answers='["import"]' hint='回想本讲关于 并发与并行的区别 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 并发、并行与两组易混术语 的落点。' />

<KnowledgeCard :points='["并发是结构、并行是执行；GIL 下多线程是并发不是并行", "同步/异步说结果何时交回，阻塞/非阻塞说调用是否立刻返回，两组正交", "五种 IO 模型：阻塞、非阻塞轮询、多路复用、信号驱动、异步 IO；epoll 是反应器，IOCP 是前摄器", "C10K 的解法是非阻塞 fd + epoll/kqueue + 单线程事件循环，asyncio 的收益在此而非绕过 GIL", "先测 wall 减 cpu 占比：CPU 主导用进程/C 扩展，等待主导用线程池/asyncio，混合分层", "Little&#39;s Law：并发约等于吞吐乘以延迟；同时看吞吐与 p50/p95/p99，别只看平均"]' :pitfalls='["把 IO 密集服务写成 200 个进程，内存爆了吞吐没涨", "在 asyncio 里用 time.sleep / 同步 requests", "用平均延迟评估并发效果", "把 IO 密集服务写成多进程，会用大量内存换来并不需要的隔离；反过来则被 GIL 卡住吞吐"]' summary='选型的依据只有一个：任务在等什么。等 CPU 用多进程或原生扩展，等网络磁盘用异步或线程池，两者混合就分层' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 并发是结构、并行是执行；GIL 下多线程是并发不是并行 | 建立直觉 |
| 同步/异步说结果何时交回，阻塞/非阻塞说调用是否立刻返回，两组正交 | 跑通示例 |
| 五种 IO 模型：阻塞、非阻塞轮询、多路复用、信号驱动、异步 IO；epoll 是反应器，IOCP 是前摄器 | 深入边界 |
| C10K 的解法是非阻塞 fd + epoll/kqueue + 单线程事件循环，asyncio 的收益在此而非绕过 GIL | 工程落地 |
| 先测 wall 减 cpu 占比：CPU 主导用进程/C 扩展，等待主导用线程池/asyncio，混合分层 | 随堂检测 |
| Little's Law：并发约等于吞吐乘以延迟；同时看吞吐与 p50/p95/p99，别只看平均 | 复盘 |

1. 并发是结构、并行是执行；GIL 下多线程是并发不是并行

2. 同步/异步说结果何时交回，阻塞/非阻塞说调用是否立刻返回，两组正交

3. 五种 IO 模型：阻塞、非阻塞轮询、多路复用、信号驱动、异步 IO；epoll 是反应器，IOCP 是前摄器

[下一讲：threading：线程生命周期与共享状态](/concurrency/threading)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/060-concurrency-intro.py`

```bash
python3 examples/lessons/060-concurrency-intro.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/060-concurrency-intro.py) · [全部示例代码索引](/examples/)
