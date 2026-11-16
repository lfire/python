---
title: 第 061 讲 · threading：线程生命周期与共享状态
description: 能安全地在线程间传递数据
---

<StageHeader stage='L6 · 并发与异步' level='★★★☆☆' time='35 分钟' goal='能安全地在线程间传递数据' prereq='第 060 讲 · 并发、并行与 IO 模型全景' />

# 第 061 讲 · threading：线程生命周期与共享状态

全景把路线摆好，现在真正迈出第一步：让不止一条执行流同时跑起来。所谓「多个线程同时改它」，就从这个最小例子开始看清，而不是一上来铺大框架。起两个线程各对同一个计数加一万次，结果常比两万少；子线程里出了岔子，主线程日志却干干净净，任务就这么静默失败。

由浅入深：先认 `threading.Thread` 与 `daemon`、线程局部存储，再看共享变量的可见性，亲手复现一次竞争条件，接着弄明白 `queue.Queue` 为何线程安全，最后处理线程异常不冒泡怎么收。前置是函数、对象引用、基本异常，以及 GIL 只保单条字节码原子这点；学完能用队列在线程间安全传数据，把子线程的失败收集回来。


## 四个线程累加十万次，总数总少几万

一个对账服务起了四个线程各累加十万次计数器，跑完发现总数总比 400000 少几万；有人给每个线程加 `time.sleep` 想「让它们别抢」，结果更慢、也照样少。

另一次故障里子线程抛了异常，主线程 `join` 完照常打印「成功」，日志里只有一行 stderr 的 Traceback 被采集系统丢掉，任务静默失败，直到对账差额暴露才被发现。还有人把结果写进全局 list 当成线程间传递，偶尔读到半截数据。

三处问题的根不在「线程不安全」这句笼统结论：GIL 只保证单条字节码原子，而 `counter += 1` 是多条；子线程的异常不会向 `join` 方传播；`list.append` 虽然是单条 C 操作，业务上的「读—改—写」仍得自己保证。

要写对，先得把 GIL 的原子边界、线程生命周期，以及队列与 `Future` 各自承担的失败传播职责分清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='认为有 GIL 就不用给 counter 加锁：GIL 只保证单条字节码原子；counter += 1 是四条字节码，中间被切换就写回旧值' />


## Thread 生命周期、daemon 与线程局部存储

`threading.Thread` 的构造参数有 `group`、`target`、`name`、`args`、`kwargs` 与 `daemon`，其中 `group` 是保留参数，必须传 `None`。

`start()` 只能调一次，重复调用抛 `RuntimeError`（threads can only be started once）；`join(timeout=None)` 等待结束，但既不返回目标函数的结果，也不重抛子线程的异常；`is_alive()`、ident、`native_id`（3.8+）与 name 用于观测。

`daemon=True` 的线程在解释器关闭时被直接丢弃，finally 与 atexit 都不保证执行，写文件、刷缓冲这类收尾不能放进去；非 daemon 线程则会在退出时被解释器隐式 join。

`threading.local()` 给每个线程一份独立属性空间，子类可重写 `__init__` 做初始化，但它不感知协程，async 场景要换用 `contextvars`（3.7+）。

线程异常默认交给 `threading.excepthook`（3.8+）打到 `sys.stderr`，主线程完全收不到——这正是「静默失败」的来源，改用线程池的 `Future.result()` 才会重新抛出。

**Thread 方法与语义边界**

| 方法 / 属性 | 行为 | 常见误用 |
| --- | --- | --- |
| start() | 启动且只能一次，重复抛 RuntimeError | 误以为可以重启同一线程 |
| join(timeout=None) | 等待结束，不返回结果、不重抛异常 | 以为 join 后能拿到子线程异常 |
| is_alive() / ident / native_id (3.8+) | 存活与系统线程标识 | 把 native_id 当跨机器稳定 ID |
| daemon=True | 解释器退出时被直接丢弃 | 把刷盘、finally 清理放进 daemon 线程 |
| threading.local() | 每线程独立属性空间 | 在 async 协程里用它，应改 contextvars |

<Callout type="tip" title='核心心智模型' text='`threading.Thread` 的构造参数有 `group`、`target`、`name`、`args`、`kwargs` 与 `daemon`，其中 `group` 是保留参数，必须传 `None`。`start()` 只能调一次，重复调用抛 `RuntimeError`（threads…' />

<ConceptDiagram type='flow4' title='第 061 讲 · Thread 生命周期、daemon 与线程局部存储' labels='Thread 生命周期、daemon 与线程…|GIL 原子边界与竞态的可复现条件|队列、Future 与失败传播|线程异常不冒泡' caption='能安全地在线程间传递数据' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 命名、超时与可观测的执行器骨架

```python
import threading
import queue

q = queue.Queue()
results = []

def worker(n):
    q.put(n * n)
    results.append(threading.current_thread().name)

ts = [threading.Thread(target=worker, args=(i,), name='w' + str(i)) for i in range(4)]
print('before start alive', [t.is_alive() for t in ts])
for t in ts: t.start()
for t in ts: t.join()
print('queue size', q.qsize())
print('results', sorted(results))
print('all joined', all(not t.is_alive() for t in ts))
```

<OutputBox title='主示例运行结果' output='before start alive [False, False, False, False]\nqueue size 4\nresults [&#39;w0&#39;, &#39;w1&#39;, &#39;w2&#39;, &#39;w3&#39;]\nall joined True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import threading\nimport queue\n\nq = queue.Queue()\nresults = []\n\ndef worker(n):\n    q.put(n * n)\n    results.append(threading.current_thread().name)\n\nts = [threading.Thread(target=worker, args=(i,), name=&#39;w&#39; + str(i)) for i in range(4)]\nprint(&#39;before start alive&#39;, [t.is_alive() for t in ts])\nfor t in ts: t.start()\nfor t in ts: t.join()\nprint(&#39;queue size&#39;, q.qsize())\nprint(&#39;results&#39;, sorted(results))\nprint(&#39;all joined&#39;, all(not t.is_alive() for t in ts))' :notes='["导入 threading 建线程并读取当前线程名", "导入 queue，用线程安全队列传数据", "空行，只用于分隔逻辑块，不影响执行结果。", "无界队列，put/get 内部带锁与 Condition", "普通 list 只收集线程名，最后一次读", "空行，只用于分隔逻辑块，不影响执行结果。", "worker 把平方值放进队列", "队列 put 单次调用即线程安全", "单次 append 可依赖 GIL 原子性", "空行，只用于分隔逻辑块，不影响执行结果。", "建 4 个命名线程，args 必须是元组", "start 之前 is_alive 全为 False", "start 只能一次，重复抛 RuntimeError", "join 等待结束，但不返回结果、不重抛异常", "qsize 是近似值；此处无消费者稳定为 4", "排序后打印四个名字，证明都跑过", "join 返回后所有线程已结束"]' title='第 061 讲 · threading：线程生命周期与共享状态' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<CheckList id='P061a' title='上线前自检' :items='["能复现并解释「认为有 GIL 就不用给 counter 加锁」", "能复现并解释「子线程抛异常后主线程 join 完打印成功」", "能复现并解释「用 daemon 线程做日志落盘或缓存刷新」", "能用一条命令验证 Thread 与 daemon", "关键路径有自动化测试与失败分支"]' />


## GIL 原子边界与竞态的可复现条件

GIL 保证的是单条字节码层面的原子性，不是业务操作的原子性。

模块级的 `counter += 1` 在 3.13 反汇编为 `LOAD_GLOBAL` / `LOAD_CONST` / `BINARY_OP` / `STORE_GLOBAL` 四条指令，切换可以落在任意两条之间：两个线程都读到旧值、各自加一，再写回同一个结果，一次更新就丢了。

少计数能否稳定复现，取决于让出时机：切换间隔由 `sys.getswitchinterval()`（默认 0.005 秒）控制，3.10+ 又把检查收敛到 eval breaker 的循环回边与函数调用处，所以老版本里常见的现象在新版本上概率会变，但语义上始终是竞态，不能拿版本行为当保证。

修复是用 `threading.Lock()` 包住整个复合操作，或者干脆换成一次原子调用——`queue.Queue.put` 与 `get` 内部带锁，`collections.Counter` 的更新却仍要自己加锁。

判断标准很简单：只要一段逻辑跨越多条字节码又共享可变状态，就必须显式同步，与有没有 GIL 无关。

**竞态相关事实与修复**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 4 线程各加十万次，总数偏小 | counter += 1 跨 4 条字节码，切换写回旧值 | threading.Lock 包住整段，或用 queue.Queue |
| 新版本不再复现少计数 | 3.10+ eval breaker 在循环回边检查让出 | 语义仍是竞态，照样加锁，不依赖版本 |
| 子线程异常后主线程照常成功 | 异常交给 threading.excepthook 打到 stderr | 用 Future.result() 收集并重新抛出 |
| list 读到半截数据 | 单次 append 原子，但读—改—写是多步 | 用 Lock 或 queue.Queue 传递完整消息 |


### 一次自增在字节码里不是原子的

```python
import threading
import concurrent.futures as cf

def boom():
    raise ValueError('child-boom')

old = threading.excepthook
threading.excepthook = lambda args: None
t = threading.Thread(target=boom, name='boomer')
t.start()
t.join()
threading.excepthook = old
print('join returned', not t.is_alive())

with cf.ThreadPoolExecutor(1) as ex:
    fut = ex.submit(boom)
    try:
        fut.result()
    except ValueError as e:
        print('future reraises', str(e))
```

<OutputBox title='对照写法：先自己猜，再点开' output='join returned True\nfuture reraises child-boom' guess="true" />


## 对照：不加锁与加锁的输出差

<CodeTabs :tabs='[{"label": "主示例", "code": "import threading\nimport queue\n\nq = queue.Queue()\nresults = []\n\ndef worker(n):\n    q.put(n * n)\n    results.append(threading.current_thread().name)\n\nts = [threading.Thread(target=worker, args=(i,), name=&#39;w&#39; + str(i)) for i in range(4)]\nprint(&#39;before start alive&#39;, [t.is_alive() for t in ts])\nfor t in ts: t.start()\nfor t in ts: t.join()\nprint(&#39;queue size&#39;, q.qsize())\nprint(&#39;results&#39;, sorted(results))\nprint(&#39;all joined&#39;, all(not t.is_alive() for t in ts))", "note": "Thread 生命周期、daemon 与线程局部存储"}, {"label": "对照 / 进阶", "code": "import threading\nimport concurrent.futures as cf\n\ndef boom():\n    raise ValueError(&#39;child-boom&#39;)\n\nold = threading.excepthook\nthreading.excepthook = lambda args: None\nt = threading.Thread(target=boom, name=&#39;boomer&#39;)\nt.start()\nt.join()\nthreading.excepthook = old\nprint(&#39;join returned&#39;, not t.is_alive())\n\nwith cf.ThreadPoolExecutor(1) as ex:\n    fut = ex.submit(boom)\n    try:\n        fut.result()\n    except ValueError as e:\n        print(&#39;future reraises&#39;, str(e))", "note": "GIL 原子边界与竞态的可复现条件"}]' title='两种写法切换看' />

```python
import dis
import threading

counter = 0
def bump():
    global counter
    counter += 1

print('opnames', [i.opname for i in dis.get_instructions(bump)])
tls = threading.local()
tls.value = 0
def child():
    tls.value = 99
t = threading.Thread(target=child)
t.start(); t.join()
print('main tls value', tls.value)
```

<OutputBox title='原理验证' output='opnames [&#39;RESUME&#39;, &#39;LOAD_GLOBAL&#39;, &#39;LOAD_CONST&#39;, &#39;BINARY_OP&#39;, &#39;STORE_GLOBAL&#39;, &#39;RETURN_CONST&#39;]\nmain tls value 0' />


## 队列为什么是线程安全的

线程间传数据首选 `queue.Queue(maxsize=0)`：它内部用一把互斥锁加 not_empty / not_full / all_tasks_done 三个 Condition，put/get 天然线程安全。

`qsize()` 只是近似值（多消费者下会变），`empty()` 与 `full()` 也不能拿来作条件判断；`task_done()` 配合 `join()` 才能等一批任务真正处理完。

`LifoQueue`、`PriorityQueue` 换的是出队顺序，`SimpleQueue`（3.7+，C 实现）更轻，但没有 task_done 机制。

要拿到返回值与异常，用 `ThreadPoolExecutor.submit` 返回 `Future`，再逐个 `result()`：异常存在 Future 里，`result()` 时重新抛出；若 Future 从不被读取，异常就永远没人发现。

给线程起有意义的 name 并接入统一日志，配合 `threading.enumerate()` 与 `active_count()` 做存活观测。

最后记住：`list.append`、dict 单次赋值这类单条 C 操作可以依赖 GIL，但「先检查再插入」「读出来改完写回」这类组合，永远要自己加锁。

**线程间传值方案选型**

| 方案 | 线程安全 | 能否拿到返回值/异常 | 适用 |
| --- | --- | --- | --- |
| queue.Queue(maxsize=0) | 是，内含 Lock + Condition | 只传数据，异常需自己塞进消息 | 生产者—消费者、有界背压 |
| LifoQueue / PriorityQueue | 是 | 同 Queue | 改出队顺序 |
| SimpleQueue (3.7+) | 是，C 实现更轻 | 无 task_done 机制 | 单向大批量传递 |
| ThreadPoolExecutor + Future |  executor 内部同步 | result() 重抛异常 | 需要结果与失败传播 |
| 全局 list / dict 共享 | 单条 C 操作安全，组合不安全 | 没有 | 只做只读或已加锁的简单计数 |


## ceval 主循环、GIL 与 ob_refcnt

CPython 的 ceval 主循环在执行字节码前假定当前线程持有 GIL；`Py_INCREF` / `Py_DECREF` 直接改对象头的 `ob_refcnt`，全局锁让这些增减不必再加细粒度锁。

于是「单条字节码原子、多条字节码可被打断」成了硬事实：`counter += 1` 编译为 `LOAD_GLOBAL` / `LOAD_CONST` / `BINARY_OP` / `STORE_GLOBAL`，两个线程完全可能在 `LOAD` 之后、`STORE` 之前各读到同一个旧值。

`threading.Thread` 在 C 层对应一个 `PyThreadState` 与一条 OS 线程，异常若未被捕获，会走 `threading.excepthook` 输出到 `sys.stderr`，不会沿 join 传播到父线程；`Future.result()` 之所以能重抛，是因为 worker 把异常对象存进 Future 状态，`result()` 检查到异常再 raise。

`threading.local` 用线程状态里的字典实现，因此与协程调度不兼容。

至于让出时机，仍由 `sys.getswitchinterval()` 的间隔与 3.10+ 的 eval breaker 检查决定，阻塞式系统调用前则通过 `Py_BEGIN_ALLOW_THREADS` 主动释放 GIL——这部分与全景那一讲是同一套机制，这里只需记住它不改变竞态结论。

<Term word='Thread 与 daemon' text='`threading.Thread` 的构造参数有 `group`、`target`、`name`、`args`、`kwargs` 与 `daemon`，其中 `group` 是保留参数，必须传 `None`。`start()` 只能调一次，重复调用抛 `RuntimeError`（threads can only b…' />

<Term word='线程局部存储' text='GIL 保证的是单条字节码层面的原子性，不是业务操作的原子性。模块级的 `counter += 1` 在 3.13 反汇编为 `LOAD_GLOBAL` / `LOAD_CONST` / `BINARY_OP` / `STORE_GLOBAL` 四条指令，切换可以落在任意两条之间：两个线程都读到旧值、各自加一，再写回同…' />


## 可观测的批量任务执行器：命名、超时、异常一个不丢

一个定时任务要并发跑几十个校验项，要求：每项有名字便于定位、单项超时不能拖死整体、任何一项失败都要汇总上报而不是静默。

裸 `threading.Thread` 做不到后两点：`join` 不返回结果，异常也传不回来。

改用 `ThreadPoolExecutor` 把每项包成 `Future`，用 `wait(timeout=...)` 分批收集，对未完成项取消并标记超时，对完成项逐个 `result()` 把异常转成结构化记录。

下面用标准库模拟：任务里故意让一项抛 `ValueError`、一项睡眠超时，执行器输出一张含状态与原因的表。真实系统把 records 换成上报接口即可，重点是「异常必被读取、超时有出口、线程有名字」这三条契约。

```python
import concurrent.futures as cf
import threading
import time

def check(item):
    name, delay, fail = item
    time.sleep(delay)
    if fail:
        raise ValueError(name + ' invalid')
    return name + ' ok'

ITEMS = [('fast', 0.01, False), ('boom', 0.01, True), ('slow', 0.30, False)]

def run_all(items, timeout=0.1):
    records = []
    with cf.ThreadPoolExecutor(max_workers=3,
                              thread_name_prefix='checker') as ex:
        futs = {ex.submit(check, it): it[0] for it in items}
        done, pending = cf.wait(futs, timeout=timeout)
        for f in done:
            label = futs[f]
            try:
                records.append((label, 'ok', f.result()))
            except Exception as e:
                records.append((label, 'failed', type(e).__name__ + ': ' + str(e)))
        for f in pending:
            f.cancel()
            records.append((futs[f], 'timeout', 'cancelled'))
    return sorted(records)

if __name__ == '__main__':
    for row in run_all(ITEMS):
        print(row[0], row[1], row[2].split(':')[0])
    print('main thread', threading.current_thread().name)
```

<Callout type="idea" title='落地提示' text='用队列传递数据、用 ThreadPoolExecutor 收集 Future 异常、给线程命名并接入统一日志' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 认为有 GIL 就不用给 counter 加锁 | GIL 只保证单条字节码原子；counter += 1 是四条字节码，中间被切换就写回旧值 | 用 threading.Lock 包住复合操作，或把状态放进 queue.Queue 由单消费者更新 |
| 子线程抛异常后主线程 join 完打印成功 | 子线程异常经 threading.excepthook 打到 stderr，不向 join 方传播 | 改用 ThreadPoolExecutor.submit 拿 Future，逐个 result() 暴露异常；给线程命名并接统一日志 |
| 用 daemon 线程做日志落盘或缓存刷新 | 解释器退出时 daemon 线程被直接终止，finally 与缓冲刷新不保证执行 | 关键收尾放非 daemon 线程并显式 join，或用队列 + 主线程收尾 |

<Callout type="warn" title='本讲最容易踩的坑' text='认为有 GIL 就不用给 counter 加锁：GIL 只保证单条字节码原子；counter += 1 是四条字节码，中间被切换就写回旧值' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：认为有 GIL 就不用给 counter 加…", "body": "GIL 只保证单条字节码原子；counter += 1 是四条字节码，中间被切换就写回旧值", "tip": "用 threading.Lock 包住复合操作，或把状态放进 queue.Queue 由单消费者更新"}, {"title": "第 2 步：子线程抛异常后主线程 join 完打印成功", "body": "子线程异常经 threading.excepthook 打到 stderr，不向 join 方传播", "tip": "改用 ThreadPoolExecutor.submit 拿 Future，逐个 result() 暴露异常；给线程命名并接统一日志"}, {"title": "第 3 步：用 daemon 线程做日志落盘或缓存刷新", "body": "解释器退出时 daemon 线程被直接终止，finally 与缓冲刷新不保证执行", "tip": "关键收尾放非 daemon 线程并显式 join，或用队列 + 主线程收尾"}]' />


## 练习、自测与速记

<Exercise title='基础：让竞态稳定复现并修好' task='四个线程各对全局 counter 加 100000 次，先不加锁跑一次记录结果，再加 threading.Lock 跑一次；解释为什么不同 Python 版本复现概率不同。' solution='import threading\ncounter = 0\nlock = threading.Lock()\ndef bump(use_lock):\n    global counter\n    for _ in range(100000):\n        if use_lock:\n            with lock: counter += 1\n        else:\n            counter += 1\ndef run(use_lock):\n    global counter\n    counter = 0\n    ts = [threading.Thread(target=bump, args=(use_lock,)) for _ in range(4)]\n    for t in ts: t.start()\n    for t in ts: t.join()\n    return counter\nprint(&#39;no lock&#39;, run(False), &#39;with lock&#39;, run(True))' explain='3.10+ 把切换检查收敛到循环回边，纯字节码长循环可能很少让出 GIL，老版本常见的少计数在新版不一定复现——但语义上仍是竞态。加锁后恒为 400000。' />

<Exercise title='进阶：用 Future 把子线程异常汇总上报' task='提交三个任务，其中一个抛异常；用 as_completed 逐个 result()，把成功值与异常类型收集成列表并打印，证明异常没有丢。' solution='import concurrent.futures as cf\ndef job(i):\n    if i == 1:\n        raise ValueError(&#39;bad&#39;)\n    return i * i\nout = []\nwith cf.ThreadPoolExecutor(2) as ex:\n    futs = [ex.submit(job, i) for i in range(3)]\n    for f in cf.as_completed(futs):\n        try:\n            out.append((&#39;ok&#39;, f.result()))\n        except Exception as e:\n            out.append((&#39;err&#39;, type(e).__name__))\nprint(sorted(out, key=lambda r: r[0]))' explain='异常被存进 Future 状态，只有 result() 才重新抛出；若 Future 从不读取，异常会永久静默。as_completed 保证每个 Future 都被消费一次。' />

<Quiz no='061-1' q='关于「有 GIL 是否还需要加锁」，哪项正确？' :options='["仍需要，counter += 1 跨多条字节码，中途可能被切换", "不需要，GIL 保证所有操作原子", "只有多进程才需要锁", "只要用 dis 看过字节码就不需要锁"]' answer="0" explain='GIL 保证单条字节码原子。读—改—写由 LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL 组成，切换可发生在指令之间，写回旧值造成丢失更新。' />

<Quiz no='061-2' q='子线程抛异常且未捕获，主线程 join 后会怎样？' :options='["异常经 threading.excepthook 打到 stderr，主线程照常继续", "join 重新抛出该异常", "整个进程立即退出", "异常被写进线程对象供 is_alive 读取"]' answer="0" explain='threading.excepthook（3.8+）负责输出到 sys.stderr，不向 join 方传播。要拿到异常须用 Future.result() 或在 worker 内自己捕获并塞进队列。' />

<Quiz no='061-3' q='关于 queue.Queue，下列哪项准确？' :options='["put/get 内部带锁与 Condition，qsize() 只是近似值", "qsize() 精确，可用来做条件判断", "它是非线程安全的，需要额外加锁", "task_done() 是 SimpleQueue 才有的"]' answer="0" explain='Queue 用互斥锁加 not_empty/not_full/all_tasks_done 三个 Condition 实现同步；qsize 在多消费者下会变，不能当判断依据。SimpleQueue 没有 task_done。' />

<Predict no='061-4' q='dis 反汇编 global counter; counter += 1（3.13）最可能看到哪组指令？' :options='["LOAD_GLOBAL / LOAD_CONST / BINARY_OP / STORE_GLOBAL / RETURN_CONST", "单条 ATOMIC_INC 指令", "LOAD_FAST / STORE_FAST 两条"]' answer='0' output='LOAD_GLOBAL / LOAD_CONST / BINARY_OP / STORE_GLOBAL / RETURN_CONST' explain='模块级名字走 LOAD_GLOBAL / STORE_GLOBAL，自增由 BINARY_OP(+=) 完成，3.13 用 RETURN_CONST 收尾。读与写分离正是竞态的窗口。' />

<FillBlank no='061-5' tpl='___ threading' :answers='["import"]' hint='回想本讲关于 Thread 与 daemon 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Thread 生命周期、daemon 与线程局部存储 的落点。' />

<KnowledgeCard :points='["GIL 只保证单条字节码原子；counter += 1 跨四条字节码，复合操作必须显式加锁", "start() 只能用一次；join() 不返回结果也不重抛异常；daemon 线程退出时 finally 不保证执行", "子线程异常走 threading.excepthook 打到 stderr 就结束，Future.result() 才会重新抛出", "queue.Queue(maxsize=0) 内部带 Lock + 三个 Condition；qsize/empty/full 只是近似，不能作条件", "threading.local 是每线程字典、不感知协程；async 场景用 contextvars（3.7+）", "线程要命名、接统一日志；用 ThreadPoolExecutor + as_completed 保证每个 Future 的异常都被读取"]' :pitfalls='["认为有 GIL 就不用给 counter 加锁", "子线程抛异常后主线程 join 完打印成功", "用 daemon 线程做日志落盘或缓存刷新", "子线程里抛出的异常不会传到主线程，任务静默失败，日志里却什么都没有"]' summary='GIL 保证单条字节码原子，但业务上的读—改—写是多条字节码，因此复合操作依然会竞态' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| GIL 只保证单条字节码原子；counter += 1 跨四条字节码，复合操作必须显式加锁 | 建立直觉 |
| start() 只能用一次；join() 不返回结果也不重抛异常；daemon 线程退出时 finally 不保证执行 | 跑通示例 |
| 子线程异常走 threading.excepthook 打到 stderr 就结束，Future.result() 才会重新抛出 | 深入边界 |
| queue.Queue(maxsize=0) 内部带 Lock + 三个 Condition；qsize/empty/full 只是近似，不能作条件 | 工程落地 |
| threading.local 是每线程字典、不感知协程；async 场景用 contextvars（3.7+） | 随堂检测 |
| 线程要命名、接统一日志；用 ThreadPoolExecutor + as_completed 保证每个 Future 的异常都被读取 | 复盘 |

1. GIL 只保证单条字节码原子；counter += 1 跨四条字节码，复合操作必须显式加锁

2. start() 只能用一次；join() 不返回结果也不重抛异常；daemon 线程退出时 finally 不保证执行

3. 子线程异常走 threading.excepthook 打到 stderr 就结束，Future.result() 才会重新抛出

[下一讲：线程同步：Lock、Condition、Semaphore、Event](/concurrency/sync-primitives)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/061-threading.py`

```bash
python3 examples/lessons/061-threading.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/061-threading.py) · [全部示例代码索引](/examples/)
