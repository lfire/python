---
title: 第 065 讲 · 进程间通信：Queue、Pipe 与信号
description: 构建可停止、可监控的多进程程序
---

<StageHeader stage='L6 · 并发与异步' level='★★★☆☆' time='30 分钟' goal='构建可停止、可监控的多进程程序' prereq='第 064 讲 · multiprocessing：进程、Pool 与共享内存' />

# 第 065 讲 · 进程间通信：Queue、Pipe 与信号

进程能各自跑了，可它们不共享内存，数据怎么递、收尾怎么收成了新问题。这一讲把并发从「让任务跑起来」推到「让一组进程可停止、可监控」，先把进程间通信理顺再谈别的。生产者进程崩了，消费者还傻等；主进程一退出，子进程没人回收，队列里没确认的消息也不知丢没丢。

从 `Queue` 与 `Pipe` 起步，走到 `Manager` 代理对象、共享 ctypes 值与跨进程 `Event`，再谈优雅退出与 `SIGTERM`，最后是僵尸进程回收。前置是多进程、Queue 与信号处理概念；学完能定义清晰的 ack、给 join 设超时、注册信号转发，写出关得掉、查得动的多进程程序。


## SIGTERM 强杀后，队列里已取未确认的消息丢了

一个多进程 ETL 跑得好好的，主进程被 Kubernetes 发来 `SIGTERM` 后强杀，队列里已取未确认的消息永久丢失；重启后又重复处理了一批，下游出现重复扣款。运维查 ps 发现一堆 `<defunct>` 僵尸进程——父进程 join 没设超时，卡在某个不响应退出的子进程上。

还有人把 `multiprocessing.Queue` 当成 `queue.Queue` 用，调 `task_done()` 直接抛 `AttributeError`；

或以为 `Manager().dict()` 和普通 dict 一样快，结果每次自增都走一次 IPC，吞吐掉了一个量级。

IPC 的难点从来不在「把数据传过去」，而在收尾：生产者崩了消费者要能感知、退出信号要能被转发、未确认消息要可重放、子进程要能被回收。这几条契约定不下来，选 Queue 还是 Pipe 其实无关紧要。

<Callout type="warn" title='先看一个真实会出错的写法' text='对 multiprocessing.Queue 调 task_done()：task_done/join 是线程版 queue.Queue 的 API，进程版 Queue 没有' />


## Queue 与 Pipe 的语义差别

`multiprocessing.Queue(maxsize=0)` 是多生产者多消费者队列：内部用一个 Pipe 加一把锁，put 把对象 pickle 后先放进本进程的 buffer，再由独立的 feeder 线程后台刷进管道，因此 put 通常立即返回、并不保证对方已经收到；

get 阻塞取，`qsize()` 在 macOS 上因 sem_getvalue 未实现会抛 `NotImplementedError`，`empty()` 与 `full()` 也不可靠。

它没有 `task_done()` / `join()`——那是线程版 `queue.Queue` 的 API，确认语义得自己用 ack 通道实现。

`close()` 之后不能再 put，`join_thread()` 等 feeder 刷完，`cancel_join_thread()` 允许退出时不刷缓冲。

`SimpleQueue` 是更简单的锁定管道，没有 feeder 线程，也没有 task_done。

`Pipe(duplex=True)` 返回 (conn1, conn2)，`duplex=False` 时返回 (只读, 只写)；

`Connection.send` / `recv` 走 pickle，`poll(timeout)` 查询就绪，对端关闭后 recv 抛 `EOFError`；

`multiprocessing.connection.wait` 可一次等多路。

Queue 适合多对多，Pipe 适合确定的一对一双向对话。

**IPC 通道语义对照**

| 通道 | 方向 | 确认机制 | 失效信号 |
| --- | --- | --- | --- |
| multiprocessing.Queue | 多对多 | 无 task_done，需自造 ack 通道 | qsize() 在 macOS 抛 NotImplementedError |
| SimpleQueue | 多对多，锁定管道 | 无 feeder 线程，也无 task_done | 无缓冲刷盘语义，put 更即时 |
| Pipe(duplex=True) | 确定的一对一双向 | 由应用自己约定 | 对端关闭后 recv 抛 EOFError |
| Manager().dict() | 任意进程经代理访问 | 每次操作一次 IPC | 读—改—写非原子，自增会丢更新 |
| Value / Array (ctypes) | 共享内存 | lock=True 自带进程锁 | 类型固定，仅标量/定长数组 |

<Callout type="tip" title='核心心智模型' text='`multiprocessing.Queue(maxsize=0)` 是多生产者多消费者队列：内部用一个 Pipe 加一把锁，put 把对象 pickle 后先放进本进程的 buffer，再由独立的 feeder 线程后台刷进管道，因此 put 通常立即返回、并不保证对方已经收到；get 阻塞取，`' />

<ConceptDiagram type='flow3' title='第 065 讲 · Queue / Pipe 的语义差别' labels='Queue / Pipe 的语义差别|Manager 代理、共享 ctypes 值|优雅退出、信号与僵尸回收' caption='构建可停止、可监控的多进程程序' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 对照：单向 Pipe 与双向 Pipe 的收发

```python
import multiprocessing as mp

def producer(q, ev):
    for i in range(3):
        q.put(i)
    ev.set()

if __name__ == '__main__':
    ctx = mp.get_context()
    q = ctx.Queue()
    ev = ctx.Event()
    p = ctx.Process(target=producer, args=(q, ev))
    p.start()
    got = [q.get(timeout=5) for _ in range(3)]
    print('queue got', got)
    print('event set', ev.is_set())
    p.join()

    parent, child = ctx.Pipe(duplex=True)
    parent.send({'k': 1})
    print('pipe recv', child.recv())
    parent.close()
    child.close()

    with ctx.Manager() as mgr:
        d = mgr.dict()
        d['a'] = 1
        print('manager dict', d['a'], type(d).__name__)
```

<OutputBox title='主示例运行结果' output='queue got [0, 1, 2]\nevent set True\npipe recv {&#39;k&#39;: 1}\nmanager dict 1 DictProxy' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import multiprocessing as mp\n\ndef producer(q, ev):\n    for i in range(3):\n        q.put(i)\n    ev.set()\n\nif __name__ == &#39;__main__&#39;:\n    ctx = mp.get_context()\n    q = ctx.Queue()\n    ev = ctx.Event()\n    p = ctx.Process(target=producer, args=(q, ev))\n    p.start()\n    got = [q.get(timeout=5) for _ in range(3)]\n    print(&#39;queue got&#39;, got)\n    print(&#39;event set&#39;, ev.is_set())\n    p.join()\n\n    parent, child = ctx.Pipe(duplex=True)\n    parent.send({&#39;k&#39;: 1})\n    print(&#39;pipe recv&#39;, child.recv())\n    parent.close()\n    child.close()\n\n    with ctx.Manager() as mgr:\n        d = mgr.dict()\n        d[&#39;a&#39;] = 1\n        print(&#39;manager dict&#39;, d[&#39;a&#39;], type(d).__name__)' :notes='["导入 multiprocessing，全部用 ctx 显式取对象", "顶层函数才能被 spawn 子进程 pickle", "生产者放三条再置位 Event", "投递三个编号", "通知消费方数据已齐", "spawn 平台守卫，子进程重导入时不会执行入口", "用默认上下文创建统一的原语", "多生产者多消费者队列，内部是 Pipe + feeder 线程", "跨进程 Event，底层是 POSIX 信号量", "把 Queue 与 Event 作为可 pickle 参数交给子进程", "启动子进程", "get 带超时，避免父进程永久挂住", "按序取到三条", "Event 已置位，说明生产者跑到收尾", "join 回收子进程，防止僵尸", "Pipe(duplex=True) 返回两端都可收发", "send 把对象 pickle 后写入管道", "对端 recv 反序列化还原成 dict", "关闭父端", "关闭子端；对端关闭后 recv 会抛 EOFError", "Manager 起一个服务进程，with 负责收尾", "代理字典，操作走 IPC", "读取一次即一次进程间往返", "打印值与代理类型，确认不是普通 dict"]' title='第 065 讲 · 进程间通信：Queue、Pipe 与信号' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import multiprocessing as mp
import signal

def noop():
    pass

if __name__ == '__main__':
    ctx = mp.get_context()
    val = ctx.Value('i', 0)
    arr = ctx.Array('i', 3)
    print('value', val.value, 'array', list(arr))
    sq = ctx.SimpleQueue()
    sq.put('x')
    print('simple queue', sq.get())
    print('queue has task_done', hasattr(ctx.Queue(), 'task_done'))
    print('SIGTERM', int(signal.SIGTERM))
    p = ctx.Process(target=noop)
    p.start()
    p.join()
    print('exitcode', p.exitcode, 'alive', p.is_alive())
    print('children', mp.active_children())
```

<OutputBox title='对照写法：先自己猜，再点开' output='value 0 array [0, 0, 0]\nsimple queue x\nqueue has task_done False\nSIGTERM 15\nexitcode 0 alive False\nchildren []' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import multiprocessing as mp\n\ndef producer(q, ev):\n    for i in range(3):\n        q.put(i)\n    ev.set()\n\nif __name__ == &#39;__main__&#39;:\n    ctx = mp.get_context()\n    q = ctx.Queue()\n    ev = ctx.Event()\n    p = ctx.Process(target=producer, args=(q, ev))\n    p.start()\n    got = [q.get(timeout=5) for _ in range(3)]\n    print(&#39;queue got&#39;, got)\n    print(&#39;event set&#39;, ev.is_set())\n    p.join()\n\n    parent, child = ctx.Pipe(duplex=True)\n    parent.send({&#39;k&#39;: 1})\n    print(&#39;pipe recv&#39;, child.recv())\n    parent.close()\n    child.close()\n\n    with ctx.Manager() as mgr:\n        d = mgr.dict()\n        d[&#39;a&#39;] = 1\n        print(&#39;manager dict&#39;, d[&#39;a&#39;], type(d).__name__)", "note": "Queue / Pipe 的语义差别"}, {"label": "对照 / 进阶", "code": "import multiprocessing as mp\nimport signal\n\ndef noop():\n    pass\n\nif __name__ == &#39;__main__&#39;:\n    ctx = mp.get_context()\n    val = ctx.Value(&#39;i&#39;, 0)\n    arr = ctx.Array(&#39;i&#39;, 3)\n    print(&#39;value&#39;, val.value, &#39;array&#39;, list(arr))\n    sq = ctx.SimpleQueue()\n    sq.put(&#39;x&#39;)\n    print(&#39;simple queue&#39;, sq.get())\n    print(&#39;queue has task_done&#39;, hasattr(ctx.Queue(), &#39;task_done&#39;))\n    print(&#39;SIGTERM&#39;, int(signal.SIGTERM))\n    p = ctx.Process(target=noop)\n    p.start()\n    p.join()\n    print(&#39;exitcode&#39;, p.exitcode, &#39;alive&#39;, p.is_alive())\n    print(&#39;children&#39;, mp.active_children())", "note": "Manager 代理、共享 ctypes 值与跨进程 Event"}]' title='两种写法切换看' />


## Queue 底层：写锁、buffer 与 feeder 线程

把 `multiprocessing.Queue` 拆开看，它是「一个单向 Pipe 加一把写锁、本进程 buffer 与 feeder 后台线程」：put 把对象 pickle 进 deque 就返回，feeder 线程负责把字节刷进管道，get 则从管道读字节再反序列化。

所以 put 与「对端已收到」之间没有 happens-before 保证，进程若赶在 feeder 刷完前退出就会丢消息，这正是需要 `join_thread()` 与 ack 语义的原因。

Pipe 是一对 Connection，`duplex=False` 时一端只读一端只写，底层是 socketpair 或匿名管道，send/recv 用 `ForkingPickler`，对端 close 后读端收到 EOF 即抛 `EOFError`。

Manager 起一个服务进程持有真实对象，代理把每次 `__getitem__` / `__setitem__` 序列化成请求再等回复，故 `d['k'] += 1` 至少是读、加、写三次往返且非原子。

僵尸进程的本质是子进程退出后父进程未 `wait(2)`，`join()` 与 `active_children()` 都会触发 waitpid 回收；

`SIGTERM` 只在主进程主线程可注册 handler，容器里 PID 1 必须转发信号，否则子进程永远等不到通知。

<Term word='Queue 与 Pipe 语义' text='`multiprocessing.Queue(maxsize=0)` 是多生产者多消费者队列：内部用一个 Pipe 加一把锁，put 把对象 pickle 后先放进本进程的 buffer，再由独立的 feeder 线程后台刷进管道，因此 put 通常立即返回、并不保证对方已经收到；get 阻塞取，`qsize()` 在' />

<Term word='Manager 代理对象' text='`Manager()` 启动一个服务进程，返回 `DictProxy` / `ListProxy` / `Namespace` / `Lock` / `Event` / `Queue` 等代理对象；代理可以 pickle 后继续传给其它进程，但每一次 `d[&#39;k&#39;] += 1` 都是一次进程间调用（读、改、写至少三次往' />


### put 返回后消息一定进管道了吗

```python
import inspect
import multiprocessing as mp
import multiprocessing.queues as mq
import sys

print('Queue has feeder', '_feed' in inspect.getsource(mq.Queue))
print('Queue has task_done', hasattr(mq.Queue, 'task_done'))
print('Pipe duplex default', inspect.signature(mp.Pipe).parameters['duplex'].default)
print('connection.wait available', hasattr(__import__('multiprocessing.connection', fromlist=['wait']), 'wait'))
print('platform', sys.platform)
```

<OutputBox title='原理验证' output='Queue has feeder True\nQueue has task_done False\nPipe duplex default True\nconnection.wait available True\nplatform darwin' />


## Manager 代理、共享 ctypes 值与跨进程 Event

`Manager()` 启动一个服务进程，返回 `DictProxy` / `ListProxy` / `Namespace` / `Lock` / `Event` / `Queue` 等代理对象；

代理可以 pickle 后继续传给其它进程，但每一次 `d['k'] += 1` 都是一次进程间调用（读、改、写至少三次往返），比共享 ctypes 慢一两个量级，还可能因「读—改—写」非原子而丢更新。

`Value` 与 `Array` 基于 ctypes 分配在共享内存上，`lock=True` 时自带一把进程间锁，适合计数器与定长数组；小标量用它比 Manager 轻得多。

`multiprocessing.Event`、`Lock`、`Semaphore`、`Condition` 是跨进程版本，底层用 `POSIX` 信号量或命名锁，行为与 threading 的同名类相似，但作用范围是进程。

选型顺序是：能共享 ctypes 就不用 Manager，能一次传一批就不要每个元素一次 IPC；只有需要任意可 pickle 对象或嵌套容器时才上 Manager。

**共享状态方案性能与适用**

| 方案 | 每次访问成本 | 适用 | 典型误用 |
| --- | --- | --- | --- |
| Value('i', ...) / Array | 一次共享内存读写，可带锁 | 计数器、定长数组 | 拿它存任意嵌套对象 |
| Manager().dict() | 至少一次 IPC 往返 | 任意可 pickle 对象、嵌套容器 | 当普通 dict 高频自增 |
| SharedMemory (3.8+) | 零拷贝 memoryview | 大数组、字节缓冲 | 忘记 close/unlink 触发泄漏告警 |
| 进程间 Event / Lock | 一次信号量操作 | 停止标志、互斥 | 用 threading.Event 跨进程（无效） |


## 优雅退出、SIGTERM 契约与僵尸回收

`signal.signal` 只能在主进程的主线程注册；容器里 PID 1 若不转发信号，子进程收不到 `SIGTERM`，会一直跑到被 `SIGKILL` 强杀。

稳妥做法是主进程收到 `SIGTERM` 后置一个跨进程的 `Event`、停止投递新任务，消费者循环检测该标志并排空在途后退出，再用 `join(timeout)` 逐个回收；超时仍不退才 `terminate()` / `kill()`。

未被 wait 的子进程会变成 `<defunct>` 僵尸，`join()`、`active_children()`（会顺带 reap 已结束的子进程）以及退出时对非 daemon 子进程的隐式 join，都是回收手段。

消息可靠性要有 ack 语义：消费者处理完往 ack 队列写回 id，生产者或协调者只对已 ack 的消息提交位点；崩溃重放时用幂等键去重。还要显式设置 join 超时与在途上限，否则「等一个卡住的子进程」本身就成了新的挂死点。

**优雅退出与信号契约**

| 环节 | 做法 | 触犯后果 |
| --- | --- | --- |
| 信号注册 | signal.signal(SIGTERM, handler) 仅主进程主线程 | 容器 PID 1 不转发，子进程收不到终止通知 |
| 停止投递 | 置跨进程 Event，生产者不再 put | 主进程退出后子进程还在写，消息丢失 |
| 排空与 ack | 消费者处理完写回 ack id，只提交已确认位点 | 未确认消息永久丢失或重启后重复处理 |
| 回收 | join(timeout) 逐个回收，超时才 terminate/kill | 未 wait 的子进程变 &lt;defunct> 僵尸 |
| 重放 | 写操作带幂等键 | 重复消费导致重复扣款 |


## 可停止、带 ack 的多进程消费组

一个订单处理服务用两个 worker 从队列取消息，要求：主进程收到停止信号后不再投递、worker 排空在途后优雅退出、每条消息处理完有 ack、join 带超时兜底。

实现上用跨进程的 `Event` 做停止标志，用第二条 ack 队列记录已处理的 id，主进程注册 `SIGTERM` handler 置位 Event 并关闭生产者，最后对 worker 逐个 `join(timeout)`，超时才 `terminate()`。

下面用标准库模拟完整流程：worker 在循环里 `get(timeout)` 并检测 Event，退出前把已处理数量写回 ack 队列；main 打印停止标志、ack 总数与是否还有存活子进程。真实系统把 handle 换成写库并在 ack 前保证幂等即可。

```python
import multiprocessing as mp
import signal
import time

def worker(wid, q, ack, stop):
    done = 0
    while True:
        try:
            item = q.get(timeout=0.1)
        except Exception:
            if stop.is_set():
                break
            continue
        done += 1
    ack.put((wid, done))

if __name__ == '__main__':
    ctx = mp.get_context()
    q, ack, stop = ctx.Queue(), ctx.Queue(), ctx.Event()
    procs = [ctx.Process(target=worker, args=(i, q, ack, stop)) for i in range(2)]
    for p in procs: p.start()
    for i in range(20): q.put(i)
    def on_term(signum, frame):
        stop.set()
    signal.signal(signal.SIGTERM, on_term)
    time.sleep(0.3)
    stop.set()
    for p in procs:
        p.join(timeout=2)
        if p.is_alive():
            p.terminate()
    total = sum(ack.get(timeout=1)[1] for _ in range(2))
    print('stop', stop.is_set(), 'acked', total,
          'alive', [p.is_alive() for p in procs])
```

<Callout type="idea" title='落地提示' text='明确 ack 语义、设置 join 超时、注册信号处理，并在容器环境里由 PID 1 负责转发信号' />

<CheckList id='P065b' title='上线前自检' :items='["能复现并解释「对 multiprocessing.Queue 调 task」", "能复现并解释「主进程被 SIGTERM 强杀后消息丢失或重复」", "能复现并解释「用 Manager().dict() 高频自增计数，吞吐掉一」", "能用一条命令验证 Queue 与 Pipe 语义", "关键路径有自动化测试与失败分支"]' />

<Callout type="warn" title='本讲最容易踩的坑' text='对 multiprocessing.Queue 调 task_done()：task_done/join 是线程版 queue.Queue 的 API，进程版 Queue 没有' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：对 multiprocessing.Queu", "body": "task_done/join 是线程版 queue.Queue 的 API，进程版 Queue 没有", "tip": "自建 ack 队列：消费者处理完 put 回 id，协调者只提交已 ack 位点"}, {"title": "第 2 步：主进程被 SIGTERM 强杀后消息丢失或重", "body": "容器 PID 1 未转发信号、队列 put 不保证送达、无 ack 与幂等键", "tip": "注册 SIGTERM handler 置 Event 停止投递，排空在途后 join；写操作带幂等键"}, {"title": "第 3 步：用 Manager().dict() 高频自", "body": "每次访问都是一次 IPC，且读—改—写非原子", "tip": "计数器改 Value(&#39;i&#39;, lock=True) 自带进程锁；只有任意嵌套对象才用 Manager"}]' />


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 对 multiprocessing.Queue 调 task_done() | task_done/join 是线程版 queue.Queue 的 API，进程版 Queue 没有 | 自建 ack 队列：消费者处理完 put 回 id，协调者只提交已 ack 位点 |
| 主进程被 SIGTERM 强杀后消息丢失或重复 | 容器 PID 1 未转发信号、队列 put 不保证送达、无 ack 与幂等键 | 注册 SIGTERM handler 置 Event 停止投递，排空在途后 join；写操作带幂等键 |
| 用 Manager().dict() 高频自增计数，吞吐掉一个量级 | 每次访问都是一次 IPC，且读—改—写非原子 | 计数器改 Value('i', lock=True) 自带进程锁；只有任意嵌套对象才用 Manager |


## 练习、自测与速记

<Exercise title='基础：用 Pipe 双向传一次请求与应答' task='Pipe(duplex=True) 两端互发一个 dict，父端 send 请求、子端 recv 后 send 回包、父端再 recv；打印往返结果并说明对端关闭后 recv 抛什么。' solution='import multiprocessing as mp\ndef echo(conn):\n    req = conn.recv()\n    conn.send({&#39;echo&#39;: req[&#39;v&#39;]})\n    conn.close()\nif __name__ == &#39;__main__&#39;:\n    a, b = mp.Pipe(duplex=True)\n    p = mp.Process(target=echo, args=(b,))\n    p.start()\n    a.send({&#39;v&#39;: 7})\n    print(a.recv())\n    p.join()\n    a.close(); b.close()' explain='Connection.send/recv 走 pickle；duplex=True 两端都可收发。对端 close 后再 recv 会抛 EOFError，poll(timeout) 可在读之前判断就绪。' />

<Exercise title='进阶：为队列补 ack 与优雅停止' task='起一个消费者，主进程投 10 条后置 Event，消费者排空退出并把处理数写回 ack 队列；主进程 join(timeout) 后打印 ack 数等于 10。' solution='import multiprocessing as mp\ndef consume(q, ack, stop):\n    n = 0\n    while True:\n        try:\n            q.get(timeout=0.1); n += 1\n        except Exception:\n            if stop.is_set(): break\n    ack.put(n)\nif __name__ == &#39;__main__&#39;:\n    ctx = mp.get_context()\n    q, ack, stop = ctx.Queue(), ctx.Queue(), ctx.Event()\n    p = ctx.Process(target=consume, args=(q, ack, stop))\n    p.start()\n    for i in range(10): q.put(i)\n    stop.set()\n    p.join(timeout=2)\n    print(&#39;acked&#39;, ack.get(timeout=1))' explain='ack 队列把「处理完」变成可观测事实；Event 让消费者在无新消息时退出；join 带超时避免父进程被卡住的子进程拖死。' />

<Quiz no='065-1' q='关于 multiprocessing.Queue，下列哪项准确？' :options='["内部有 feeder 线程，put 不保证对端已收到；没有 task_done()", "有 task_done()/join()，与 queue.Queue 完全一致", "qsize() 在所有平台都精确", "put 一定等对方 recv 才返回"]' answer="0" explain='put 把对象放进本进程 buffer 就返回，由 feeder 线程刷进 Pipe；确认要自己造 ack 通道。qsize 在 macOS 因 sem_getvalue 未实现抛 NotImplementedError。' />

<Quiz no='065-2' q='Manager().dict() 高频自增很慢，根因是？' :options='["每次访问都是一次服务进程 IPC，且读—改—写非原子", "dict 本身是 Python 实现", "GIL 跨进程串行", "pickle 协议版本太低"]' answer="0" explain='代理把每次 __getitem__/__setitem__ 变成一次请求—回复往返，d[k] += 1 至少三次往返且不是原子；计数器应改用 Value(&#39;i&#39;, lock=True)。' />

<Quiz no='065-3' q='容器里主进程收到 SIGTERM，子进程却一直不退出，最常见原因是？' :options='["PID 1 未转发信号，且未在 handler 里置跨进程停止标志", "子进程没有 GIL", "Queue 已满", "Pipe 是半双工"]' answer="0" explain='SIGTERM 只在主进程主线程可注册 handler；容器 PID 1 需转发信号，并应置 Event 让消费者排空后协作式退出，再 join(timeout) 回收。' />

<Predict no='065-4' q='对端 Connection.close() 之后，在另一端调用 recv() 会发生什么？' :options='["抛 EOFError", "永久阻塞", "返回 None", "返回上一条消息"]' answer='0' output='EOFError' explain='管道对端全部关闭后写端不会再发数据，读端读到文件结束标记，Connection.recv 将其转换为 EOFError；可用 poll(timeout) 或捕获 EOFError 做收尾。' />

<FillBlank no='065-5' tpl='___ multiprocessing as mp' :answers='["import"]' hint='回想本讲关于 Queue 与 Pipe 语义 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Queue / Pipe 的语义差别 的落点。' />

<KnowledgeCard :points='["multiprocessing.Queue 是 Pipe + 写锁 + buffer + feeder 线程，put 不保证送达且没有 task_done", "Pipe(duplex=True) 一对一双向；对端关闭后 recv 抛 EOFError；connection.wait 可一次等多路", "Manager 代理每次访问一次 IPC、读—改—写非原子；Value/Array 是共享 ctypes，lock=True 带进程锁", "SIGTERM 仅主进程主线程可注册，容器 PID 1 必须转发；用跨进程 Event 做协作式停止", "消息可靠性靠 ack 通道 + 幂等键；join(timeout) 逐个回收，超时才 terminate/kill，避免 &lt;defunct&gt; 僵尸", "qsize 在 macOS 抛 NotImplementedError，empty/full 不可靠；SimpleQueue 无 feeder 线程"]' :pitfalls='["对 multiprocessing.Queue 调 task_done()", "主进程被 SIGTERM 强杀后消息丢失或重复", "用 Manager().dict() 高频自增计数，吞吐掉一个量级", "只靠 kill 强杀进程，队列里未确认的消息会永久丢失或重复处理"]' summary='IPC 的难点不在传数据而在收尾：生产者崩了消费者要能感知，主进程退出时子进程要能被回收' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| multiprocessing.Queue 是 Pipe + 写锁 + buffer + feeder 线程，put 不保证送达且没有 task_done | 建立直觉 |
| Pipe(duplex=True) 一对一双向；对端关闭后 recv 抛 EOFError；connection.wait 可一次等多路 | 跑通示例 |
| Manager 代理每次访问一次 IPC、读—改—写非原子；Value/Array 是共享 ctypes，lock=True 带进程锁 | 深入边界 |
| SIGTERM 仅主进程主线程可注册，容器 PID 1 必须转发；用跨进程 Event 做协作式停止 | 工程落地 |
| 消息可靠性靠 ack 通道 + 幂等键；join(timeout) 逐个回收，超时才 terminate/kill，避免 &lt;defunct> 僵尸 | 随堂检测 |
| qsize 在 macOS 抛 NotImplementedError，empty/full 不可靠；SimpleQueue 无 feeder 线程 | 复盘 |

1. multiprocessing.Queue 是 Pipe + 写锁 + buffer + feeder 线程，put 不保证送达且没有 task_done

2. Pipe(duplex=True) 一对一双向；对端关闭后 recv 抛 EOFError；connection.wait 可一次等多路

3. Manager 代理每次访问一次 IPC、读—改—写非原子；Value/Array 是共享 ctypes，lock=True 带进程锁

[下一讲：IO 多路复用：select / poll / epoll](/concurrency/io-multiplex)

```bash
python -c "from concurrent.futures import ThreadPoolExecutor as P; print(list(P(2).map(abs,[-1,-2])))"
```

把输入换成你自己的数据，观察结果是否仍符合 Queue 与 Pipe 语义 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。
