---
title: 第 054 讲 · GIL 真相：存在原因、切换与影响边界
description: 能判断何时该用线程、进程还是异步
---

<StageHeader stage='L5 · 核心机制' level='★★★★★' time='45 分钟' goal='能判断何时该用线程、进程还是异步' prereq='第 053 讲 · 分代 GC、循环引用与 weakref' />

# 第 054 讲 · GIL 真相：存在原因、切换与影响边界

前面几讲我们把对象、内存和回收一路拆到了引用计数：每次赋值、传参、容器存取，解释器都在悄悄改一个对象头里的计数。到这里会自然冒出一个问题——如果好几个线程同时跑，这些计数该怎么保持正确？这个看似实现细节的疑问，正是理解 Python 并发表现的关键。

本讲不急着下结论。我们先从一个「加了四个线程反而更慢」的线上现象出发，亲手量一次；再看 GIL 究竟锁住了什么、线程在什么时刻会交出执行权；最后才把线程、进程、异步三条路线放在同一张判据表里比较。需要你已经熟悉函数、对象引用和基本的异常处理；学完这一讲，面对一个具体任务，你能说清它该用哪种并发模型，以及为什么另一种会更慢。


## 一个「加了线程反而变慢」的线上工单

一个真实的线上工单：某服务把图片缩略图计算从单线程改成 4 线程，期望快 4 倍，结果 p99 延迟反而涨了 15%。排查发现这段逻辑是纯 Python 的整数运算，四个线程在 CPython 里轮流持有同一把全局解释器锁，非但没有并行，还多付了上下文切换与锁竞争的开销。

另一个工单方向相反：把同步 requests 换成线程池后吞吐提升了 6 倍。两者都是 Python、都是多线程，结论却完全相反。分界线不在「线程好不好」，而在任务在等什么：等 CPU 还是等 IO。本讲把 GIL 从「一个听说过名词」变成可测量、可推导的机制。

<Callout type="warn" title='先看一个真实会出错的写法' text='认为有 GIL 就不需要给 counter 加锁：GIL 只保证单条字节码原子；counter += 1 编译成 LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL 多条指令，中间被切换就会写回旧值' />


## GIL 锁住的到底是什么

GIL（Global Interpreter Lock）是 CPython 里保护解释器共享状态的一把互斥锁，包括对象引用计数、模块字典、类型系统等。它不是锁你的业务数据，也不是语言规范的一部分——PyPy、Jython 没有它，CPython 3.13 的自由线程构建还可以关掉它。

它存在的直接原因是引用计数：每个 `PyObject` 头里的 `ob_refcnt` 会在赋值、传参、容器存取时被大量增减，如果每次都用细粒度原子操作或锁，单线程性能会明显下降。1990 年代 Guido 选择用一把大锁换取单线程快与 C 扩展好写，这个取舍一直延续至今。

直接后果有两条：同一时刻只有一个线程执行 Python 字节码（多核 CPU 对纯 Python 计算无效）；但业务层的读—改—写仍然跨多条字节码，切换随时可能发生，所以该加的 `Lock` 一个都不能少。

<ConceptDiagram type='compare2' title='第 054 讲 · GIL 到底锁住了什么：引用计数的历史代价' labels='GIL 到底锁住了什么：引用计数的历史代价|切换机制：5 毫秒、字节码边界与 eval…|三条路线的判据：先量化等待，再选模型|自由线程化路线' caption='能判断何时该用线程、进程还是异步' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

<Callout type="tip" title='核心心智模型' text='GIL（Global Interpreter Lock）是 CPython 里保护解释器共享状态的一把互斥锁，包括对象引用计数、模块字典、类型系统等。它不是锁你的业务数据，也不是语言规范的一部分——PyPy、Jython 没有它，CPython 3.13 的自由线程构建还可以关掉它。它存在的直接原因…' />


## 5 毫秒与 eval breaker：切换发生在哪

持有 GIL 的线程不会一直跑到结束。

`sys.getswitchinterval()` 默认返回 0.005（5 毫秒），表示解释器每隔这么久设置一次「请交出 GIL」的请求；真正检查请求的点在不同版本有变化：旧版在字节码计数边界检查，CPython 3.10 之后把检查收敛到 eval breaker，主要在后向跳转（循环回边）与函数调用处，不再每若干条指令检查一次。

阻塞式 IO 与 `time.sleep` 会在进入系统调用前通过 `Py_BEGIN_ALLOW_THREADS` 主动释放 GIL，操作完成后再重新获取——这是 IO 密集任务能靠线程提速的根本原因。

NumPy、hashlib 等 C 扩展在大块计算时也会释放 GIL。

可以用 `sys.setswitchinterval(0.001)` 人为加剧切换，观察竞态复现概率变化，但生产环境不要随意调小：切换本身有成本，且会让锁竞争更频繁。

```python
import dis, sys

counter = 0
def bump():
    global counter
    counter += 1

print('switchinterval', sys.getswitchinterval())
dis.dis(bump)
```

<OutputBox title='原理验证' output='switchinterval 0.005\n  LOAD_GLOBAL 0 (counter)\n  LOAD_CONST 1 (1)\n  BINARY_OP 13 (+=)\n  STORE_GLOBAL 0 (counter)\n  RETURN_CONST 0 (None)' />

<Term word='GIL 保护什么' text='GIL（Global Interpreter Lock）是 CPython 里保护解释器共享状态的一把互斥锁，包括对象引用计数、模块字典、类型系统等。它不是锁你的业务数据，也不是语言规范的一部分——PyPy、Jython 没有它，CPython 3.13 的自由线程构建还可以关掉它。它存在的直接原因是引用计数：每个…' />

<Term word='切换间隔与字节码边界' text='持有 GIL 的线程不会一直跑到结束。`sys.getswitchinterval()` 默认返回 0.005（5 毫秒），表示解释器每隔这么久设置一次「请交出 GIL」的请求；真正检查请求的点在不同版本有变化：旧版在字节码计数边界检查，CPython 3.10 之后把检查收敛到 eval breaker，主要在后向跳…' />


### 用字节码看一次自增为什么不是原子的

把模块级的 `counter += 1` 交给 `dis` 看，3.13 上会展开成 `LOAD_GLOBAL` / `LOAD_CONST` / `BINARY_OP` / `STORE_GLOBAL` 四条指令；GIL 只保证其中单条字节码的原子性，让出却可以落在任意两条之间。

两个线程都读到旧值、各自加一，再先后写回同一个结果，一次更新就这样丢了。

下表把「计数偏小」「sleep 场景线程数翻倍吞吐反而上升」这些现象和各自对应的机制列在一起，顺着它回溯到字节码，就知道该用 `threading.Lock` 包住整个读—改—写，或换成 `queue.Queue` 这种内部带锁的结构，而不能指望 GIL 替业务数据兜底。

**常见现象与对应机制**

| 现象 | 根因 |
| --- | --- |
| 4 线程计算比单线程慢 | GIL 串行 + 切换开销 |
| 多线程 counter 计数偏小 | LOAD/STORE 之间被切换，写回旧值 |
| sleep 场景线程数翻倍吞吐上升 | 阻塞调用释放 GIL |
| 协程里 requests 卡住全部任务 | 同步 IO 不释放事件循环 |
| 多进程反而更慢 | pickle 大对象 + 任务粒度太细 |


## 三条并发路线的判据

选型的唯一依据是任务在等什么。

用 `cProfile` 或简单的 `perf_counter` 分段计时，算出 CPU 时间占比与等待时间占比：CPU 占比高 → `multiprocessing` / `ProcessPoolExecutor`，或把热点交给 C 扩展与 NumPy；等待占比高（网络、磁盘、数据库）→ `ThreadPoolExecutor` 或 `asyncio`；两者混合 → 分层，例如 Web 请求用异步框架接收，CPU 重的解析任务丢进进程池。

`asyncio` 并不绕过 GIL，它的收益来自单线程内用事件循环消除线程切换与栈内存开销，适合大量并发连接而非大量并行计算。还要注意序列化的隐性成本：多进程间传大对象要 `pickle`，数据量大时并行收益可能被序列化吃光，此时共享内存或内存映射更合适。

**并发模型选型：按等待类型决定**

| 任务特征 | 推荐模型 | 原因 | 主要代价 |
| --- | --- | --- | --- |
| 纯 Python 计算 / 图像处理循环 | ProcessPoolExecutor | 每个进程有独立 GIL，可用满多核 | 进程启动与 pickle 序列化开销 |
| HTTP / DB / 文件 IO | ThreadPoolExecutor 或 asyncio | 阻塞调用前释放 GIL，等待可重叠 | 线程栈内存或异步库改造成本 |
| C 扩展密集计算 | 线程池 + NumPy / hashlib | 扩展内部主动释放 GIL | 需确认该扩展确实释放 |
| 海量长连接 / 推送 | asyncio 单线程事件循环 | 避免线程切换与栈内存，连接数可达数万 | 任何一个同步阻塞调用都会拖垮全loop |
| 混合负载 | 异步接入 + 进程池分流 | 按阶段把两类任务隔离 | 架构复杂度与跨进程数据传递 |

<FlowTimeline :steps='[{"title": "GIL 到底锁住了什么：引用计数的历史代价", "desc": "GIL（Global Interpreter Lock）是 CPython 里保护解…", "tone": "blue"}, {"title": "切换机制：5 毫秒、字节码边界与 eval br…", "desc": "持有 GIL 的线程不会一直跑到结束。…", "tone": "purple"}, {"title": "三条路线的判据：先量化等待，再选模型", "desc": "选型的唯一依据是任务在等什么。用 `cProfile` 或简单的…", "tone": "orange"}, {"title": "工程落地", "desc": "混合负载服务：异步接入 + 进程池分流", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 实测：CPU 密集下线程为什么更慢

```python
import threading, time

def cpu(n):
    s = 0
    for i in range(n):
        s += i * i
    return s

N = 1_000_000
t0 = time.perf_counter(); cpu(N); single = time.perf_counter() - t0

ts = [threading.Thread(target=cpu, args=(N,)) for _ in range(4)]
t0 = time.perf_counter()
for t in ts: t.start()
for t in ts: t.join()
multi = time.perf_counter() - t0
print('single', round(single, 3), 'threads', round(multi, 3))
print('switchinterval', __import__('sys').getswitchinterval())
```

<OutputBox title='主示例运行结果' output='single 0.052 threads 0.211\nswitchinterval 0.005' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import threading, time\n\ndef cpu(n):\n    s = 0\n    for i in range(n):\n        s += i * i\n    return s\n\nN = 1_000_000\nt0 = time.perf_counter(); cpu(N); single = time.perf_counter() - t0\n\nts = [threading.Thread(target=cpu, args=(N,)) for _ in range(4)]\nt0 = time.perf_counter()\nfor t in ts: t.start()\nfor t in ts: t.join()\nmulti = time.perf_counter() - t0\nprint(&#39;single&#39;, round(single, 3), &#39;threads&#39;, round(multi, 3))\nprint(&#39;switchinterval&#39;, __import__(&#39;sys&#39;).getswitchinterval())' :notes='["导入线程与计时模块", "空行，只用于分隔逻辑块，不影响执行结果。", "定义纯 Python 的 CPU 密集函数，循环内全是字节码运算", "累加器初始化为 0，每次迭代都要更新 ob_refcnt", "循环 N 次，GIL 不会在运算期间被释放", "返回累加结果，防止被优化掉", "设定单次工作量，数值越大差异越明显", "空行，只用于分隔逻辑块，不影响执行结果。", "测量单线程基线耗时", "创建四个线程，每个执行同样的工作量", "空行，只用于分隔逻辑块，不影响执行结果。", "记录多线程起点", "启动四个线程，它们将轮流争抢同一把 GIL", "等待全部结束", "多线程总耗时约为单线程的 4 倍，还多付切换成本", "打印两个耗时，直观看到「并行」没有发生", "读取默认切换间隔 0.005 秒", "阻塞 IO、time.sleep、释放 GIL 的 C 扩展能让线程真正重叠；纯 Python 计算不能"]' title='第 054 讲 · GIL 真相：存在原因、切换与影响边界' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Compare :panels='[{"label": "主示例", "code": "import threading, time\n\ndef cpu(n):\n    s = 0\n    for i in range(n):\n        s += i * i\n    return s\n\nN = 1_000_000\nt0 = time.perf_counter(); cpu(N); single = time.perf_counter() - t0\n\nts = [threading.Thread(target=cpu, args=(N,)) for _ in range(4)]\nt0 = time.perf_counter()\nfor t in ts: t.start()\nfor t in ts: t.join()\nmulti = time.perf_counter() - t0\nprint(&#39;single&#39;, round(single, 3), &#39;threads&#39;, round(multi, 3))\nprint(&#39;switchinterval&#39;, __import__(&#39;sys&#39;).getswitchinterval())", "note": "GIL 到底锁住了什么：引用计数的历史代价"}, {"label": "对照 / 进阶", "code": "import threading, time\n\ndef io_bound():\n    time.sleep(0.05)   # 进入系统调用前释放 GIL\n\ndef run(n, use_thread):\n    t0 = time.perf_counter()\n    if use_thread:\n        ts = [threading.Thread(target=io_bound) for _ in range(n)]\n        for t in ts: t.start()\n        for t in ts: t.join()\n    else:\n        for _ in range(n): io_bound()\n    return time.perf_counter() - t0\n\nprint(&#39;serial&#39;, round(run(8, False), 3), &#39;threads&#39;, round(run(8, True), 3))", "note": "切换机制：5 毫秒、字节码边界与 eval breaker"}]' title='两种写法对照' note='差异集中在 GIL 保护什么；先看输出，再找背后的规则。' />


### 对照：IO 密集时线程确实有效

```python
import threading, time

def io_bound():
    time.sleep(0.05)   # 进入系统调用前释放 GIL

def run(n, use_thread):
    t0 = time.perf_counter()
    if use_thread:
        ts = [threading.Thread(target=io_bound) for _ in range(n)]
        for t in ts: t.start()
        for t in ts: t.join()
    else:
        for _ in range(n): io_bound()
    return time.perf_counter() - t0

print('serial', round(run(8, False), 3), 'threads', round(run(8, True), 3))
```

<OutputBox title='对照写法：先自己猜，再点开' output='serial 0.402 threads 0.051' guess="true" />


## 底层：引用计数、Py_BEGIN_ALLOW_THREADS 与 PEP 703

在 CPython 源码里，ceval 的主循环每次执行字节码前都假定当前线程持有 GIL。引用计数的宏 `Py_INCREF` / `Py_DECREF` 直接改 `ob_refcnt`，若没有全局锁，两个线程同时增减同一对象就会丢更新，进而提前释放仍被引用的对象。

C 扩展要跑长计算时，标准写法是用 `Py_BEGIN_ALLOW_THREADS` 临时释放 GIL、计算完再 `Py_END_ALLOW_THREADS` 重新获取，期间不能触碰任何 Python 对象。

线程调度层面，持有者定期检查 eval_breaker 标志位，被请求让出时释放 GIL 并唤醒等待者；5ms 内没主动释放，IO 也可能被延迟，这就是「一个 CPU 密集线程会让其它线程卡顿」的来源。PEP 703 的做法是把引用计数改为偏向线程局部 + 延迟合并、对象访问加细粒度锁，代价是单线程性能回退与巨大的生态适配工作。

因此「去掉 GIL」不是开关，而是一次全生态迁移。

**GIL 相关版本与参数差异**

| 版本 / 参数 | 行为 | 排查提示 |
| --- | --- | --- |
| sys.getswitchinterval() 默认 0.005 | 每 5ms 发起一次 GIL 让出请求 | 调小会加剧竞态复现，但生产勿随意改 |
| 3.9 及以前 | 按字节码计数检查切换请求 | 旧文章的指令级结论多基于这一版 |
| 3.10+ eval breaker | 检查点收敛到循环回边与调用处 | 同一份竞态代码复现概率会变化 |
| 3.12 每解释器 GIL (PEP 684) | 子解释器可各自持锁 | 仍需 C 扩展配合才能安全并行 |
| 3.13 自由线程构建 (PEP 703) | 可用 --disable-gil 构建去掉 GIL | 单线程有性能回退，扩展兼容性需逐个验证 |


## 混合负载服务怎么分层

一个报表服务既要并发拉取上百个上游接口（IO 密集），又要对拉回的数据做 CPU 密集的聚合。全部塞进线程池，聚合阶段会被 GIL 卡住；全部塞进进程池，每个等待中的连接都要占一个进程，内存先爆。

正确做法是分两级：`asyncio` 负责接入与并发 IO，把重计算通过 `loop.run_in_executor` 投递给一个固定大小的进程池，并用信号量限制在途任务数，避免队列无限堆积。

下面用标准库模拟这个结构，重点看任务如何分层、如何限制并发、以及异常如何回传。

示例用 `ProcessPoolExecutor` 投递重计算，在 macOS、Windows 这类默认 spawn 启动方式的平台上，子进程会重新导入主模块，顶层代码必须收进 `if __name__ == '__main__':` 守卫，否则会递归创建出一串子进程；配套示例文件已加 环境兜底，在受限沙箱里会打印跳过原因而不是中断。

真实项目还要加超时、熔断与指标埋点。

```python
import asyncio, concurrent.futures, time

def heavy(n):
    return sum(i * i for i in range(n))

async def fetch(i):
    await asyncio.sleep(0.01)      # 模拟网络等待
    return i

async def main(loop, pool, sem):
    async def one(i):
        async with sem:
            v = await fetch(i)
            return await loop.run_in_executor(pool, heavy, 20000 + v)
    return await asyncio.gather(*(one(i) for i in range(20)))

with concurrent.futures.ProcessPoolExecutor(2) as pool:
    loop = asyncio.new_event_loop()
    sem = asyncio.Semaphore(8)
    t0 = time.perf_counter()
    out = loop.run_until_complete(main(loop, pool, sem))
    print(len(out), 'tasks done in', round(time.perf_counter() - t0, 3), 's')
    loop.close()
```

<Callout type="idea" title='落地提示' text='CPU 密集用进程/原生扩展，IO 密集用 asyncio 或线程池，混合型任务拆成两级池' />

<ArchBlueprint title='第 054 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "GIL 到底锁住了什么：引用计数的历史代价", "protocol": "调用 / 请求", "items": [{"label": "GIL 到底锁住了什么…", "sub": "输入与前置", "detail": "GIL（Global Interpreter Lock）是 CPython 里保护解释器共享状态的一把互斥锁，包括对象引用计数、模块字典、类型系统等。它不是锁你的业务数据，也不是语言规范的一部分——PyPy、Jython 没有它，CPython 3.13 的自由线程构建还可以关掉它。它存在的直接原因…", "tone": "blue"}]}, {"name": "核心规则", "note": "切换机制：5 毫秒、字节码边界与 eval breaker", "protocol": "语言 / 运行时协议", "items": [{"label": "切换机制：5 毫秒、字节…", "sub": "状态与边界", "detail": "持有 GIL 的线程不会一直跑到结束。`sys.getswitchinterval()` 默认返回 0.005（5 毫秒），表示解释器每隔这么久设置一次「请交出 GIL」的请求；真正检查请求的点在不同版本有变化：旧版在字节码计数边界检查，CPython 3.10 之后把检查收敛到 eval brea…", "tone": "purple"}]}, {"name": "落地与收尾", "note": "三条路线的判据：先量化等待，再选模型", "items": [{"label": "三条路线的判据：先量化等…", "sub": "工程处理", "detail": "选型的唯一依据是任务在等什么。用 `cProfile` 或简单的 `perf_counter` 分段计时，算出 CPU 时间占比与等待时间占比：CPU 占比高 → `multiprocessing` / `ProcessPoolExecutor`，或把热点交给 C 扩展与 NumPy；等待占比高（网…", "tone": "green"}]}]' />

<CheckList id='P054a' title='上线前自检' :items='["能复现并解释「认为有 GIL 就不需要给 counter 加锁」", "能复现并解释「在 async 函数里调用 time.sleep 或同步 r…」", "能复现并解释「用多进程传大 DataFrame 却埋怨没加速」", "能用一条命令验证 GIL 保护什么", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import sys; print(sys.version_info[:2])"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 GIL 保护什么 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 认为有 GIL 就不需要给 counter 加锁 | GIL 只保证单条字节码原子；counter += 1 编译成 LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL 多条指令，中间被切换就会写回旧值 | 用 threading.Lock 包住整个复合操作，或改用 queue.Queue 这类内部带锁的线程安全结构；collections.Counter 的更新同样跨多条字节码、并不是单次原子调用，仍要自己加锁 |
| 在 async 函数里调用 time.sleep 或同步 requests | 同步阻塞不释放事件循环，整个 loop 上的所有任务一起停住，超时与心跳同时失效 | 改用 asyncio.sleep / aiohttp / httpx.AsyncClient，或把阻塞调用放进 asyncio.to_thread |
| 用多进程传大 DataFrame 却埋怨没加速 | 跨进程参数与返回值要 pickle，序列化与内存拷贝常常超过并行收益 | 用 shared_memory / 内存映射，或把任务粒度调大、在子进程内部完成加载 |

<Callout type="warn" title='本讲最容易踩的坑' text='认为有 GIL 就不需要给 counter 加锁：GIL 只保证单条字节码原子；counter += 1 编译成 LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL 多条指令，中间被切换就会写回旧值' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：认为有 GIL 就不需要给 counter…", "body": "GIL 只保证单条字节码原子；counter += 1 编译成 LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL 多条指令，中间被切换就会写回旧值", "tip": "用 threading.Lock 包住整个复合操作，或改用 queue.Queue 这类内部带锁的线程安全结构；collections.Counter 的更新同样跨多条字节码、并不是单次原子调用，仍要自己加锁"}, {"title": "第 2 步：在 async 函数里调用 time.sle…", "body": "同步阻塞不释放事件循环，整个 loop 上的所有任务一起停住，超时与心跳同时失效", "tip": "改用 asyncio.sleep / aiohttp / httpx.AsyncClient，或把阻塞调用放进 asyncio.to_thread"}, {"title": "第 3 步：用多进程传大 DataFrame 却埋怨没加…", "body": "跨进程参数与返回值要 pickle，序列化与内存拷贝常常超过并行收益", "tip": "用 shared_memory / 内存映射，或把任务粒度调大、在子进程内部完成加载"}]' />


## ceval_gil.c 里的 drop_gil / take_gil 握手

把 GIL 落到源码：`Python/ceval_gil.c` 只有 drop_gil 与 take_gil 两个动作，共享状态是 `Include/internal/pycore_gil.h` 的 struct _gil_runtime_state。

drop_gil 持 mutex 把 locked 清 0、置 last_holder、向 cond 发信号；take_gil 发现 locked 就进 PyCOND_TIMEDWAIT。

关键不是这把 mutex，而是 gil_drop_request：持锁线程在 `Python/ceval.c` 的 eval breaker 检查点看到它被置位就主动 drop_gil，等待线程被 cond 唤醒接手。

`sys.setswitchinterval(0.005)` 写的正是 gil->interval；3.10 起检查点收敛到循环回边与函数调用处，紧凑纯计算循环仍会在回边被强制切断。

switch_number 防止刚放锁的线程立刻抢回，避免一批线程排成 convoy。这套握手是协作式的，不靠操作系统抢占线程，也解释了 4 线程跑纯 Python 整数循环为何比单线程更慢，多出的不是并行，是 drop/take 与 cond 往返开销。

```python
import sys
import threading

print('gil_enabled', sys._is_gil_enabled())
print('interval', sys.getswitchinterval())
print('immortal refcount', sys.getrefcount(None) > 1000000)
names = []
def worker():
    names.append(threading.current_thread().name)
ts = [threading.Thread(target=worker, name='w%d' % i) for i in range(3)]
for t in ts: t.start()
for t in ts: t.join()
print('workers', sorted(names))
print('active', threading.active_count())

```

<OutputBox title='扩展示例运行结果' output='gil_enabled True\ninterval 0.005\nimmortal refcount True\nworkers [&#39;w0&#39;, &#39;w1&#39;, &#39;w2&#39;]\nactive 1' />

<LineByLine code='import sys\nimport threading\n\nprint(&#39;gil_enabled&#39;, sys._is_gil_enabled())\nprint(&#39;interval&#39;, sys.getswitchinterval())\nprint(&#39;immortal refcount&#39;, sys.getrefcount(None) &gt; 1000000)\nnames = []\ndef worker():\n    names.append(threading.current_thread().name)\nts = [threading.Thread(target=worker, name=&#39;w%d&#39; % i) for i in range(3)]\nfor t in ts: t.start()\nfor t in ts: t.join()\nprint(&#39;workers&#39;, sorted(names))\nprint(&#39;active&#39;, threading.active_count())\n' :notes='["导入 sys，后面用它读 GIL 开关、切换间隔与引用计数。", "导入 threading，起几个线程观察 GIL 下的并发行为。", "空行，只用于分隔逻辑块，不影响执行结果。", "sys._is_gil_enabled() 是 3.13 新增的探测函数：标准构建返回 True，自由线程（无 GIL）构建返回 False。", "读回 gil-&gt;interval，默认 0.005 秒，正是 sys.setswitchinterval 写入的那个值。", "PEP 683 把 None 等单例标成 immortal，getrefcount 返回一个固定大数，用大于一百万判断即可，不必写死具体值。", "用一个共享 list 收集各线程的名字；list.append 是单条 C 操作，GIL 下不会撕裂。", "定义工作函数，它只做一件事：把当前线程名追加进 names。", "current_thread().name 取当前线程名并追加，用于后面核对三个线程都跑过。", "一次性创建 3 个线程对象并显式命名 w0/w1/w2；此时还没 start，不会执行 worker。", "逐个 start()，线程进入就绪队列；GIL 决定同一时刻只有一个在跑字节码。", "逐个 join() 等三个线程收尾，保证打印 names 时所有追加都已完成。", "sorted 把线程名排序，消除调度顺序的不确定性，输出稳定为 [&#39;w0&#39;, &#39;w1&#39;, &#39;w2&#39;]。", "三个工作线程都已结束，活动线程只剩主线程，因此 active_count() 为 1。", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />


### gil_drop_request 与 cond 超时如何规避 convoy

<ConceptDiagram type='flow4' title='第 054 讲 · 扩展图解' labels='eval_breaker 置位|drop_gil 释放锁|cond 唤醒等待者|take_gil 重新持有' caption='一次强制切换的四步：解释器在回边看到 gil_drop_request 后放锁，等待线程被 cond 唤醒接手，switch_number 防止刚放锁者立刻抢回。' />


### _gil_runtime_state 的字段与线程状态绑定

_gil_runtime_state 的字段可直接对照行为：locked 表示锁是否被某 PyThreadState 持有，last_holder 记上次持有者，switch_number 是切换计数，gil_drop_request 是请交出的原子标志，cond 与 mutex 是同步原语，interval 存着 setswitchinterval 的值。

绑定发生在 `Python/pystate.c`：take_gil 成功后把当前 PyThreadState 挂回 TLS（_PyThreadState_Swap），此后字节码、异常状态、求值栈都属于这一个 tstate。

理解这层绑定才能解释 Py_BEGIN_ALLOW_THREADS 为何必须成对：`Include/ceval.h` 里它展开为 `_save = PyEval_SaveThread()`，先 drop_gil 再把 tstate 从 TLS 摘下；Py_END_ALLOW_THREADS 展开为 `PyEval_RestoreThread(_save)`，重新 take_gil 并挂回。

宏保护的是无 GIL 期间不持有线程状态。方向相反的是 PyGILState_Ensure / Release：给从 C 回调反入的外来线程临时建 tstate 并拿锁，两者混用是 C 扩展典型的死锁来源。

**GIL 相关原语与它们的边界**

| 机制 | 宏或字段 | GIL 状态 | 允许的操作 |
| --- | --- | --- | --- |
| 主动释放 | Py_BEGIN_ALLOW_THREADS | 无 | 纯 C 计算、阻塞式系统调用 |
| 重新获取 | Py_END_ALLOW_THREADS | 有 | 任意 Python C API |
| 外部线程反入 | PyGILState_Ensure | 获取中 | 调用 Python 回调 |
| 请求切换 | gil_drop_request | 持有中即将释放 | 回边与调用点检查 |
| 切换节奏 | interval | 无关 | 由 setswitchinterval 写入 |


## Py_BEGIN_ALLOW_THREADS 展开后的 PyThreadState 边界

`Py_BEGIN_ALLOW_THREADS` 展开成 `PyEval_SaveThread()`：摘下当前 `PyThreadState`、放掉 GIL，让纯 C 计算或阻塞系统调用在无解释器状态时跑完；`Py_END_ALLOW_THREADS` 再用 `PyEval_RestoreThread(_save)` 重新拿锁、把 tstate 挂回，两者必须成对。

这段区间既无 GIL 也无线程状态，任何触碰 `PyObject` 的 C API 都是未定义行为；方向相反的 `PyGILState_Ensure` / `Release` 供外部线程反入时临时建 tstate，混用就是 C 扩展典型的死锁来源。

下面这个案例用 cProfile 把计算型与等待型工单的剖面并排跑，让这层边界在真实调用树上显形。

那两个结论相反的工单可用同一份剖面分清。

图片缩放是纯 Python 整数循环，4 线程 p99 涨 15%：cProfile 的 cumtime 全落在计算函数，没有 sleep 或 socket 等待，四个线程轮流持有 GIL，还多付 drop/take 与 cond 往返；换 ProcessPoolExecutor 才吃到多核。

requests 换线程池吞吐 6 倍是另一张剖面：cumtime 绝大部分是 `time.sleep` 或 socket 等待，进入系统调用前 Py_BEGIN_ALLOW_THREADS 已放掉 GIL。

判据不是线程好不好，而是 CPU 时间与等待时间各占多少，以及计算是 Python 字节码还是释放了 GIL 的 C 扩展。下面代码在同一段函数里混合 CPU 与 sleep，用 pstats 把两者都抓进报告：sleep 以 built-in method time sleep 出现，正是等待型任务的信号。

生产上还要按线程分桶，避免把别的线程事件算进当前调用树。

```python
import cProfile
import pstats
import io
import time

def cpu_bound(n):
    return sum(i * i for i in range(n))

def io_bound():
    time.sleep(0.01)

pr = cProfile.Profile()
pr.enable()
cpu_bound(20000)
io_bound()
pr.disable()
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats('cumulative').print_stats(3)
report = s.getvalue()
print('has cpu_bound', 'cpu_bound' in report)
print('has io_bound', 'io_bound' in report)
print('has sleep', 'sleep' in report)

```

<Term word='gil_drop_request' text='_gil_runtime_state 里的原子标志；eval breaker 在回边看到它被置位后，持锁线程 drop_gil 主动放锁，等待线程被 cond 唤醒接手，让切换不依赖操作系统抢占线程。' />


### PEP 703 自由线程构建的实测差异

PEP 703 让 CPython 可以用 `--disable-gil` 构建出真正并行的自由线程版本，改的不是一处开关：引用计数改成偏向线程局部再延迟合并，对象访问加细粒度锁，`None`、`True`、小整数等单例先经 PEP 683 变成 immortal，省掉几十个线程反复写同一条缓存行。

代价也测得到——单线程有可观的性能回退，C 扩展要逐个适配。

3.13 里可用 `sys._is_gil_enabled()` 探测当前构建是否仍启用 GIL，标准构建返回 `True`，自由线程构建返回 `False`；示例打印的 `gil_enabled` 与 `immortal refcount` 就是这层差异的两个可观测信号。

下面两道自测分别钉住「释放区间里不能碰 Python 对象」和「切换间隔由谁写入」。

<Quiz no='054-1' q='在 Py_BEGIN_ALLOW_THREADS 与 Py_END_ALLOW_THREADS 之间，下列哪一项操作是明确禁止的？' :options='["调用阻塞的 read(2) 等待网络数据", "对纯 C 数组做大块数值计算", "调用 PyList_GET_ITEM 读取列表元素并 Py_INCREF", "用 time.sleep 让出 CPU 给其他线程"]' answer="2" explain='宏展开后当前线程已 drop_gil 且 PyThreadState 从 TLS 摘下，解释器共享状态不受保护；任何 Python C API（包括 PyList_GET_ITEM 与 Py_INCREF）都会读写无锁的引用计数，属于未定义行为。纯 C 计算与阻塞式系统调用不触碰 PyObject，正是这个宏的用途；time.sleep 进入系统调用前也主动释放 GIL。需要操作 Python 对象时先用 Py_BLOCK_THREADS 或出宏后再处理。' />

<Exercise title='用 setswitchinterval 复现一次切换窗口' task='把切换间隔临时调到 1e-6 秒，在子线程读回并验证它小于默认 0.005，再恢复原值确认成功；输出只要两个确定的布尔值。' solution='import sys\nimport threading\n\nold = sys.getswitchinterval()\nsys.setswitchinterval(1e-6)\nhits = []\ndef watcher():\n    hits.append(sys.getswitchinterval())\nt = threading.Thread(target=watcher)\nt.start()\nt.join()\nsys.setswitchinterval(old)\nprint(&#39;tiny interval seen&#39;, hits[0] &lt; old)\nprint(&#39;restored&#39;, sys.getswitchinterval() == old)\n' explain='sys.setswitchinterval 写的是 _gil_runtime_state.interval，子线程读到的值与主线程一致，因为间隔是解释器级而非线程级。调小会加剧 gil_drop_request 置位频率，让读改写竞态更易复现，但生产不要照做：切换有 drop/take 与 cond 往返成本。用两个布尔收尾，避免把不确定的 wall-clock 时间写进断言。' />


## 动手与自测

<Exercise title='基础：让竞态稳定复现' task='把 counter += 1 放进四个线程各执行 100000 次，先不加锁跑三次记录结果，再加 threading.Lock 跑三次；解释为什么结果在不同 Python 版本上复现概率不同。' solution='import threading\ncounter = 0\nlock = threading.Lock()\ndef bump(use_lock):\n    global counter\n    for _ in range(100000):\n        if use_lock:\n            with lock: counter += 1\n        else:\n            counter += 1\ndef run(use_lock):\n    global counter\n    counter = 0\n    ts = [threading.Thread(target=bump, args=(use_lock,)) for _ in range(4)]\n    for t in ts: t.start()\n    for t in ts: t.join()\n    return counter\nprint(&#39;no lock&#39;, run(False), &#39;with lock&#39;, run(True))' explain='3.10+ 把切换检查收敛到循环回边，长时间运行的纯字节码循环可能很少让出 GIL，因此老版本常见的少计数现象在新版本上不一定复现——但语义上仍是竞态，不能依赖版本行为。加锁后恒为 400000。' />

<Exercise title='进阶：量化 IO 与 CPU 混合的收益' task='写一个函数，参数控制 IO 等待时长与 CPU 循环次数，分别用串行、线程池、进程池跑 8 个任务，画出（或打印）三种方案耗时随两类参数变化的趋势，并给出选型阈值。' solution='import time, threading, concurrent.futures as cf\n\ndef task(io_s, n):\n    time.sleep(io_s)\n    return sum(i*i for i in range(n))\n\ndef bench(io_s, n, mode):\n    t0 = time.perf_counter()\n    if mode == &#39;serial&#39;:\n        for _ in range(8): task(io_s, n)\n    elif mode == &#39;thread&#39;:\n        with cf.ThreadPoolExecutor(8) as ex: list(ex.map(lambda _: task(io_s, n), range(8)))\n    else:\n        with cf.ProcessPoolExecutor(4) as ex: list(ex.map(lambda _: task(io_s, n), range(8)))\n    return round(time.perf_counter()-t0, 3)\n\nfor io_s, n in [(0.05, 1000), (0.0, 500000)]:\n    print(io_s, n, {m: bench(io_s, n, m) for m in (&#39;serial&#39;,&#39;thread&#39;,&#39;process&#39;)})' explain='IO 占主导时线程池接近 1/8 耗时且比进程池省内存；CPU 占主导且无等待时只有进程池能随核数伸缩。阈值不是固定数字，要用线上真实输入测出来。' />

<Quiz no='054-2' q='某纯 Python 计算任务改成 4 线程后反而变慢，最准确的解释是？' :options='["GIL 使同一时刻只有一个线程执行字节码，多线程还额外付出切换成本", "线程创建开销大于计算量", "Python 的 list 不是线程安全的", "操作系统不允许同进程多线程并行"]' answer="0" explain='GIL 串行化字节码执行，四个线程轮流持有锁；若循环里没有触发释放 GIL 的调用，总耗时约为单线程四倍再加切换开销。' />

<Quiz no='054-3' q='关于「有 GIL 是否还需要加锁」，下面哪项正确？' :options='["仍需要，因为 counter += 1 跨多条字节码，中途可能被切换", "不需要，GIL 保证所有操作原子", "只有多进程才需要锁", "只要用 dis 看过字节码就不需要锁"]' answer="0" explain='GIL 保证的是单条字节码层面的原子性。读—改—写由 LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL 组成，切换可发生在指令之间，写回旧值造成丢失更新。' />

<Quiz no='054-4' q='3.13 自由线程构建（PEP 703）带来的主要代价是？' :options='["单线程性能回退且 C 扩展需逐个适配", "语法不兼容 Python 3", "无法再使用 asyncio", "所有第三方库自动获得多线程加速"]' answer="0" explain='去掉 GIL 后引用计数要改成线程局部加延迟合并、对象访问需要细粒度同步，单线程有可测的性能回退；依赖 C API 的扩展必须逐个验证线程安全。' />

<Predict no='054-5' q='dis 反汇编 global counter; counter += 1 后，最可能看到哪组指令？' :options='["LOAD_GLOBAL / LOAD_CONST / BINARY_OP / STORE_GLOBAL", "单条 ATOMIC_INC 指令", "LOAD_FAST / STORE_FAST 两条"]' answer='0' output='LOAD_GLOBAL / LOAD_CONST / BINARY_OP / STORE_GLOBAL' explain='模块级名字走 LOAD_GLOBAL / STORE_GLOBAL，自增由 BINARY_OP 完成。正因为读与写是分离的两步，中间被切换就会丢失更新。' />

<FillBlank no='054-6' tpl='___ threading, time' :answers='["import"]' hint='回想本讲关于 GIL 保护什么 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 GIL 到底锁住了什么：引用计数的历史代价 的落点。' />

<KnowledgeCard :points='["GIL 保护解释器状态（含引用计数），不保护业务数据；它不是语言规范，而是 CPython 实现选择", "默认切换间隔 5ms；3.10+ 由 eval breaker 在循环回边与调用处检查让出请求", "阻塞 IO、time.sleep、释放 GIL 的 C 扩展能让线程真正重叠；纯 Python 计算不能", "counter += 1 是多条字节码，必须加锁；GIL 不等于原子性", "CPU 密集 → 进程/C 扩展；IO 密集 → 线程池/asyncio；混合 → 异步接入 + 进程池分流", "多进程要先算 pickle 与内存拷贝成本；asyncio 里任何同步阻塞调用都是全 loop 级故障"]' :pitfalls='["认为有 GIL 就不需要给 counter 加锁", "在 async 函数里调用 time.sleep 或同步 requests", "用多进程传大 DataFrame 却埋怨没加速", "以为有 GIL 就不用加锁，会在复合操作上写出竞态；把 CPU 密集逻辑塞进线程只会更慢"]' summary='GIL 保护的是解释器内部状态而非你的业务数据，所以多线程依然需要锁；CPU 密集任务无法靠线程利用多核，IO 密集则可以' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| GIL 保护解释器状态（含引用计数），不保护业务数据；它不是语言规范，而是 CPython 实现选择 | 建立直觉 |
| 默认切换间隔 5ms；3.10+ 由 eval breaker 在循环回边与调用处检查让出请求 | 跑通示例 |
| 阻塞 IO、time.sleep、释放 GIL 的 C 扩展能让线程真正重叠；纯 Python 计算不能 | 深入边界 |
| counter += 1 是多条字节码，必须加锁；GIL 不等于原子性 | 工程落地 |
| CPU 密集 → 进程/C 扩展；IO 密集 → 线程池/asyncio；混合 → 异步接入 + 进程池分流 | 随堂检测 |
| 多进程要先算 pickle 与内存拷贝成本；asyncio 里任何同步阻塞调用都是全 loop 级故障 | 复盘 |

1. GIL 保护解释器状态（含引用计数），不保护业务数据；它不是语言规范，而是 CPython 实现选择

2. 默认切换间隔 5ms；3.10+ 由 eval breaker 在循环回边与调用处检查让出请求

3. 阻塞 IO、time.sleep、释放 GIL 的 C 扩展能让线程真正重叠；纯 Python 计算不能

[下一讲：导入系统源码级：finder、loader 与缓存](/core/import-system)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/054-gil.py`

```bash
python3 examples/lessons/054-gil.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/054-gil.py) · [全部示例代码索引](/examples/)
