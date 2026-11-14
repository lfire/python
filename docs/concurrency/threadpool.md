---
title: 第 063 讲 · 线程池与 Future 模式
description: 管理并发度、结果收集与失败传播
---

<StageHeader stage='L6 · 并发与异步' level='★★★☆☆' time='35 分钟' goal='管理并发度、结果收集与失败传播' prereq='第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event' />

# 第 063 讲 · 线程池与 Future 模式

手动起线程、逐一加锁之后，任务一多，创建销毁和并发度就成了新的操心事。这一讲把它们收在一处，让「谁什么时候跑、最多跑几个」有统一管法。一批几百个小任务，来一个起一个线程，流量峰值时待办全堆进内存，服务往往先被自己的队列压垮，这种亏吃过一次就忘不了。

顺着抽象往上走：先看 `Executor` 与 `submit`、`map`、`as_completed`，再看 `Future` 状态机，接着谈并发度与有界队列，然后处理取消语义，最后确认异常如何传回。前置是线程、`Queue` 与 `Future` 概念；学完能把线程池与并发度收在一处，逐一取结果暴露异常，按依赖分池并设好超时。


## 无上限 submit，峰值把内存撑爆

一个导出服务把待办任务无上限地 `submit` 进线程池，平时没事，流量峰值时内存先被几十万个待办 Future 撑爆，服务被自己压垮；另一个版本按顺序对 `futures` 里的每个 Future 调 `result()`，结果第一个慢任务把后面早已失败的任务全挡住，异常迟迟发不出来。

还有人调用 `future.cancel()` 以为能停掉正在跑的任务，返回 False 后不检查就当已取消；

或者 submit 完从不取结果，异常被永久吞掉。这些问题的共同点是：把线程池当成「自动并行的黑盒」，没意识到它同时管着并发度、队列、结果状态与失败传播。`Executor` 抽象把创建销毁收敛到一处，`Future` 把异步结果变成可传递的值，但队列是否有界、按什么顺序收结果、取消到底对哪种状态有效，都必须显式设计。

<Callout type="warn" title='先看一个真实会出错的写法' text='无上限 submit，峰值把内存撑爆：executor 内部待办队列无界，流量峰值时 Future 与参数对象全堆在内存' />


## Executor 抽象与默认并发度

`concurrent.futures.Executor` 是抽象基类，对外主要是三个接口：`submit(fn, *args, **kwargs)` 返回 `Future`、`map` 返回迭代器、`shutdown` 负责收尾；

用 with 包住 executor，退出时会自动调用 `shutdown(wait=True)`。

`ThreadPoolExecutor` 的默认并发度在 3.8 到 3.12 是 `min(32, cpu + 4)`，其中 cpu 取自 `os.cpu_count()`；

3.13 起改用 `os.process_cpu_count()` 来数可用核，会把 cgroup 与 CPU 亲和性的限制算进去。

本机 12 核按这个式子得到 16。这个「CPU 数加 4」是给 IO 等待留余量的经验值，CPU 密集任务不要照抄，应设成接近核数甚至更小。`initializer`（3.7+）在每个工作线程启动时跑一次，适合建线程局部连接。

`ProcessPoolExecutor` 默认取 `os.cpu_count()` 或 1，3.11+ 还有 `max_tasks_per_child` 定期回收 worker 以限制内存增长。

executor 内部用一条无界的 `queue.SimpleQueue` 存待办，所以「无上限 submit」没有背压，必须在生产者侧用 `Semaphore` 或在途计数限流。

**Executor 接口与默认参数**

| 接口 | 签名关键项 | 默认 / 说明 |
| --- | --- | --- |
| ThreadPoolExecutor | max_workers=None, thread_name_prefix='', initializer=None (3.7+) | min(32, cpu+4)，3.13 用 os.process_cpu_count() |
| ProcessPoolExecutor | max_workers=None, mp_context=None, max_tasks_per_child=None (3.11+) | 默认 os.cpu_count() 或 1 |
| submit | (fn, /, *args, **kwargs) -> Future | 立即返回，不阻塞 |
| map | (*iterables, timeout=None, chunksize=1) | 按输入顺序 yield；失败在迭代到该项时抛出 |
| shutdown | (wait=True, *, cancel_futures=False) | cancel_futures 3.9+ 丢弃未启动待办 |

<Callout type="tip" title='核心心智模型' text='`concurrent.futures.Executor` 是抽象基类，对外主要是三个接口：`submit(fn, *args, **kwargs)` 返回 `Future`、`map` 返回迭代器、`shutdown` 负责收尾；用 with 包住 executor，退出时会自动调用…' />

<ConceptDiagram type='hub4' title='第 063 讲 · Executor 抽象与默认并发度' labels='Executor 抽象与默认并发度|Future 状态机与取消语义|分池、背压与异常逐一暴露|异常传播' caption='管理并发度、结果收集与失败传播' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## submit、map 与 as_completed 的返回差异

```python
import concurrent.futures as cf

def job(i):
    if i == 2:
        raise ValueError('job-2')
    return i * i

with cf.ThreadPoolExecutor(max_workers=3) as ex:
    futs = {ex.submit(job, i): i for i in range(5)}
    out = {}
    for f in cf.as_completed(futs):
        i = futs[f]
        try:
            out[i] = f.result()
        except ValueError as e:
            out[i] = str(e)
print('out', sorted(out.items()))
print('all done', all(f.done() for f in futs))
print('cancelled', all(not f.cancelled() for f in futs))

with cf.ThreadPoolExecutor(2) as ex:
    print('map', list(ex.map(job, [0, 1, 3])))
```

<OutputBox title='主示例运行结果' output='out [(0, 0), (1, 1), (2, &#39;job-2&#39;), (3, 9), (4, 16)]\nall done True\ncancelled True\nmap [0, 1, 9]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import concurrent.futures as cf\n\ndef job(i):\n    if i == 2:\n        raise ValueError(&#39;job-2&#39;)\n    return i * i\n\nwith cf.ThreadPoolExecutor(max_workers=3) as ex:\n    futs = {ex.submit(job, i): i for i in range(5)}\n    out = {}\n    for f in cf.as_completed(futs):\n        i = futs[f]\n        try:\n            out[i] = f.result()\n        except ValueError as e:\n            out[i] = str(e)\nprint(&#39;out&#39;, sorted(out.items()))\nprint(&#39;all done&#39;, all(f.done() for f in futs))\nprint(&#39;cancelled&#39;, all(not f.cancelled() for f in futs))\n\nwith cf.ThreadPoolExecutor(2) as ex:\n    print(&#39;map&#39;, list(ex.map(job, [0, 1, 3])))' :notes='["导入 concurrent.futures 使用 Executor 与 Future", "空行，只用于分隔逻辑块，不影响执行结果。", "定义一个会失败的任务，验证异常传播", "编号为 2 时抛错", "抛出 ValueError", "其余返回平方", "空行，只用于分隔逻辑块，不影响执行结果。", "with 退出时自动 shutdown(wait=True)", "字典把 Future 映射回输入编号", "out 收集每个编号的结果", "按完成先后 yield，最早暴露失败", "取回该 Future 对应的编号", "准备消费结果", "result 会重新抛出 worker 里的异常", "捕获失败项", "转成结构化字符串，不让异常丢失", "按编号排序，结果与提交顺序无关", "with 退出后所有 Future 都是 FINISHED", "没有任何一个被取消", "空行，只用于分隔逻辑块，不影响执行结果。", "再用 map 演示按输入顺序", "map 跳过失败的 2，按序 yield"]' title='第 063 讲 · 线程池与 Future 模式' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：map 保序而 as_completed 先完成先出

```python
import concurrent.futures as cf
import threading

gate = threading.Event()
def slow(i):
    gate.wait()
    return i

with cf.ThreadPoolExecutor(max_workers=1) as ex:
    f0 = ex.submit(slow, 0)
    f1 = ex.submit(slow, 1)
    print('cancel pending', f1.cancel())
    print('f1 cancelled', f1.cancelled(), f1.done())
    gate.set()
    print('f0 result', f0.result(), 'exception', f0.exception())
```

<OutputBox title='对照写法：先自己猜，再点开' output='cancel pending True\nf1 cancelled True True\nf0 result 0 exception None' guess="true" />


## Future 的状态机：PENDING 到 FINISHED

`concurrent.futures._base.Future` 有五个内部状态：`PENDING`、`RUNNING`、`CANCELLED`、`CANCELLED_AND_NOTIFIED`、`FINISHED`。

`cancel()` 只在 `PENDING` 时有效——把状态置为 `CANCELLED` 并返回 True；一旦任务已进入 `RUNNING`，`cancel()` 就返回 False，无法从外部强杀线程。

`cancelled()`、`running()`、`done()` 用来查询状态，`result(timeout=None)` 阻塞取结果并在异常时重新抛出，`exception(timeout=None)` 只取异常对象、不抛；

`add_done_callback(fn)` 在状态变成 `FINISHED` 时回调。

关键陷阱：submit 之后若不调用 `result()` 或 `exception()`，worker 里抛出的异常只存在 Future 里，日志里什么都没有。`map` 按输入顺序 yield 结果，迭代器走到某个失败项时才抛异常；`as_completed` 则按完成先后 yield，能最早暴露失败与超时。

`wait` 返回具名元组 (done, not_done)，配合 `FIRST_COMPLETED` / `FIRST_EXCEPTION` 可做分批收集；

3.9+ 的 `shutdown(cancel_futures=True)` 会丢弃尚未启动的待办。

**Future 状态机与 cancel 结果**

| 状态 | 进入时机 | cancel() 返回值 | result() 行为 |
| --- | --- | --- | --- |
| PENDING | 已提交未开始 | True，转 CANCELLED | 尚未可用 |
| RUNNING | worker 已取走 | False，无法强杀 | 阻塞到结束 |
| CANCELLED / CANCELLED_AND_NOTIFIED | 被成功取消 | False（已终态） | 抛 CancelledError |
| FINISHED | 正常完成或异常完成 | False | 返回值或重新抛出异常 |


### cancel() 为什么停不掉正在跑的任务

```python
import concurrent.futures as cf
import inspect
import os

print('submit', str(inspect.signature(cf.Executor.submit)))
print('map', str(inspect.signature(cf.Executor.map)))
print('shutdown', str(inspect.signature(cf.Executor.shutdown)))
cpu = getattr(os, 'process_cpu_count', os.cpu_count)()
print('default max_workers', min(32, cpu + 4))
print('Future states', cf._base.PENDING, cf._base.RUNNING, cf._base.FINISHED)
```

<OutputBox title='原理验证' output='submit (self, fn, /, *args, **kwargs)\nmap (self, fn, *iterables, timeout=None, chunksize=1)\nshutdown (self, wait=True, *, cancel_futures=False)\ndefault max_workers 16\nFuture states PENDING RUNNING FINISHED' />


## 对照：三种收集方式的异常暴露

<CodeTabs :tabs='[{"label": "主示例", "code": "import concurrent.futures as cf\n\ndef job(i):\n    if i == 2:\n        raise ValueError(&#39;job-2&#39;)\n    return i * i\n\nwith cf.ThreadPoolExecutor(max_workers=3) as ex:\n    futs = {ex.submit(job, i): i for i in range(5)}\n    out = {}\n    for f in cf.as_completed(futs):\n        i = futs[f]\n        try:\n            out[i] = f.result()\n        except ValueError as e:\n            out[i] = str(e)\nprint(&#39;out&#39;, sorted(out.items()))\nprint(&#39;all done&#39;, all(f.done() for f in futs))\nprint(&#39;cancelled&#39;, all(not f.cancelled() for f in futs))\n\nwith cf.ThreadPoolExecutor(2) as ex:\n    print(&#39;map&#39;, list(ex.map(job, [0, 1, 3])))", "note": "Executor 抽象与默认并发度"}, {"label": "对照 / 进阶", "code": "import concurrent.futures as cf\nimport threading\n\ngate = threading.Event()\ndef slow(i):\n    gate.wait()\n    return i\n\nwith cf.ThreadPoolExecutor(max_workers=1) as ex:\n    f0 = ex.submit(slow, 0)\n    f1 = ex.submit(slow, 1)\n    print(&#39;cancel pending&#39;, f1.cancel())\n    print(&#39;f1 cancelled&#39;, f1.cancelled(), f1.done())\n    gate.set()\n    print(&#39;f0 result&#39;, f0.result(), &#39;exception&#39;, f0.exception())", "note": "Future 状态机与取消语义"}]' title='两种写法切换看' />

**结果收集方式对照**

| 方式 | 顺序 | 异常暴露 | 适用 |
| --- | --- | --- | --- |
| 裸 for f in futures: f.result() | 按提交顺序 | 被前面的慢任务挡住 | 任务少且耗时接近 |
| as_completed(fs, timeout=None) | 按完成先后 | 最早暴露失败，可设总超时 | 批量独立任务 |
| wait(fs, return_when=FIRST_EXCEPTION) | 分批返回 (done, not_done) | 首批有异常即返回 | 需要失败即止损 |
| executor.map(...) | 按输入顺序 | 迭代到失败项才抛 | 输入有序、结果要对齐 |


## SimpleQueue 与惰性起线程的底层

`ThreadPoolExecutor` 内部维护一组工作线程与一条无界的 `queue.SimpleQueue`：submit 把 WorkItem 放进队列，并惰性调用 `_adjust_thread_count` 起线程，worker 循环取项、执行 fn，再把结果或异常 set 到对应的 Future。

Future 是一个带 Condition 的状态机：`set_result` / `set_exception` 在加锁后改状态并 `notify_all`，`result()` 在状态未到 `FINISHED` 时 wait，醒来后按状态返回值、raise 异常或抛 `CancelledError`。

`cancel()` 只能在 `PENDING` 抢到锁时改状态，`RUNNING` 之后 work item 已被 worker 持有，无法从外部强杀——这正是它返回 False 的原因。

`as_completed` 给每个 Future 挂上 `add_done_callback`，把已完成者放进另一条队列再 yield，因此顺序由完成时间决定；

`map` 则先把所有输入一次性 submit 完，再按输入顺序对 Future 逐个 `result()`，所以既没有背压，也会被最慢的前置项拖住。

默认并发度的版本差异（3.13 起用 `os.process_cpu_count()` 取代 `os.cpu_count()`）已在上一节说过，它改变的是取哪个核数，不改变队列无界这一事实。

<Term word='Executor 抽象' text='`concurrent.futures.Executor` 是抽象基类，对外主要是三个接口：`submit(fn, *args, **kwargs)` 返回 `Future`、`map` 返回迭代器、`shutdown` 负责收尾；用 with 包住 executor，退出时会自动调用…' />

<Term word='submit / map / as_completed' text='`concurrent.futures._base.Future` 有五个内部状态：`PENDING`、`RUNNING`、`CANCELLED`、`CANCELLED_AND_NOTIFIED`、`FINISHED`。`cancel()` 只在 `PENDING` 时有效——把状态置为 `CANCELLED` 并返回…' />


## 分池、背压与异常逐一暴露

生产上按依赖类型分池：IO 任务给一个较大的线程池，CPU 重任务丢进 `ProcessPoolExecutor`，避免慢 CPU 任务占满 IO 线程。

给每个池设明确的 `max_workers` 与超时，并对在途任务数封顶——常见做法是生产者持一个 `BoundedSemaphore`，每次 submit 前 acquire、在 `add_done_callback` 里 release，这样队列长度恒有界。

收集结果一律用 `as_completed` 或 `wait` 分批，对每个 Future 单独用 try/except 包住 `result()`，把异常转成结构化记录，而不是按列表顺序裸等。

取消要检查返回值：`cancel()` 返回 False 说明任务已 `RUNNING` 或已 `FINISHED`，此时要么等它结束，要么用事件标志让任务内部协作式退出。`map` 的 timeout 是整体迭代器的超时而非单项，且它在输入可迭代对象很大时会一次性提交全部任务，同样需要外层限流。

`ThreadPoolExecutor` 的线程默认是非 daemon，`shutdown(wait=True)` 会等所有任务结束，进程退出才不会被截断。


## 有界在途、异常不丢的批量导入器

一个数据导入接口一次收到上万条记录，要并发写库但绝不能把待办一次性塞满内存，且任何一条失败都要进报表。

做法是给生产者加一把 `BoundedSemaphore` 限制在途 Future 数，每条 submit 后挂 `add_done_callback` 释放许可；

用 `as_completed` 分批收结果，对每个 Future 单独 `result()` 把异常转成记录；最后对未完成项 `cancel()` 并检查返回值。下面用标准库模拟：worker 随机睡眠并对特定输入抛错，导入器打印成功、失败、取消三类计数。

真实项目把写库换成 DB 调用即可，重点是「在途有上界、异常必被读取、取消有反馈」这三条契约。

```python
import concurrent.futures as cf
import random
import threading
import time

def write(row):
    time.sleep(0.001 * random.randint(1, 3))
    if row % 7 == 0:
        raise ValueError('bad row ' + str(row))
    return row

def bulk_import(rows, max_inflight=8, workers=4):
    sem = threading.BoundedSemaphore(max_inflight)
    ok, failed, cancelled = [], [], []
    with cf.ThreadPoolExecutor(max_workers=workers,
                              thread_name_prefix='importer') as ex:
        futs = {}
        for row in rows:
            sem.acquire()
            f = ex.submit(write, row)
            futs[f] = row
            f.add_done_callback(lambda _f: sem.release())
        for f in cf.as_completed(futs):
            if f.cancelled():
                cancelled.append(futs[f])
                continue
            try:
                ok.append(f.result())
            except Exception as e:
                failed.append((futs[f], type(e).__name__))
    return len(ok), len(failed), len(cancelled)

if __name__ == '__main__':
    random.seed(0)
    print('ok/failed/cancelled', bulk_import(range(30)))
```

<Callout type="idea" title='落地提示' text='按依赖类型分池、设置有界队列与超时、对 Future 逐一取结果以暴露异常' />

<CheckList id='P063b' title='上线前自检' :items='["能复现并解释「无上限 submit，峰值把内存撑爆」", "能复现并解释「submit 后从不取结果，异常永久静默」", "能复现并解释「以为 cancel() 能停掉正在跑的任务」", "能用一条命令验证 Executor 抽象", "关键路径有自动化测试与失败分支"]' />

<Callout type="warn" title='本讲最容易踩的坑' text='无上限 submit，峰值把内存撑爆：executor 内部待办队列无界，流量峰值时 Future 与参数对象全堆在内存' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：无上限 submit，峰值把内存撑爆", "body": "executor 内部待办队列无界，流量峰值时 Future 与参数对象全堆在内存", "tip": "生产者用 BoundedSemaphore 或在途计数限流，add_done_callback 里释放许可"}, {"title": "第 2 步：submit 后从不取结果，异常永久静默", "body": "worker 的异常只存在 Future 状态里，不调用 result()/exception() 就没人读", "tip": "用 as_completed 对每个 Future 逐个 result() 并 try/except，或统一挂回调记录"}, {"title": "第 3 步：以为 cancel() 能停掉正在跑的任务", "body": "cancel 只对 PENDING 有效，RUNNING/FINISHED 返回 False，无法强杀线程", "tip": "检查 cancel() 返回值；对长任务改用事件标志做协作式退出，或直接等结果"}]' />


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 无上限 submit，峰值把内存撑爆 | executor 内部待办队列无界，流量峰值时 Future 与参数对象全堆在内存 | 生产者用 BoundedSemaphore 或在途计数限流，add_done_callback 里释放许可 |
| submit 后从不取结果，异常永久静默 | worker 的异常只存在 Future 状态里，不调用 result()/exception() 就没人读 | 用 as_completed 对每个 Future 逐个 result() 并 try/except，或统一挂回调记录 |
| 以为 cancel() 能停掉正在跑的任务 | cancel 只对 PENDING 有效，RUNNING/FINISHED 返回 False，无法强杀线程 | 检查 cancel() 返回值；对长任务改用事件标志做协作式退出，或直接等结果 |


## 练习、自测与速记

<Exercise title='基础：用 as_completed 逐个暴露异常' task='提交 0..4 五个任务，让 i==3 抛异常；用 as_completed 遍历并对每个 Future 调用 result()，把成功值与异常类型收进列表打印。' solution='import concurrent.futures as cf\ndef job(i):\n    if i == 3: raise ValueError(&#39;x&#39;)\n    return i * i\nout = []\nwith cf.ThreadPoolExecutor(3) as ex:\n    futs = [ex.submit(job, i) for i in range(5)]\n    for f in cf.as_completed(futs):\n        try:\n            out.append((&#39;ok&#39;, f.result()))\n        except Exception as e:\n            out.append((&#39;err&#39;, type(e).__name__))\nprint(sorted(out, key=lambda r: r[0]))' explain='as_completed 按完成先后 yield，每个 Future 都被 result() 消费一次，失败项立刻转成结构化记录；裸按提交顺序遍历会被慢任务挡住。' />

<Exercise title='进阶：给 submit 加有界在途限流' task='用 BoundedSemaphore(4) 控制同时未完成的 Future 数，add_done_callback 里 release；提交 20 个任务并打印最大在途不超过 4。' solution='import concurrent.futures as cf\nimport threading, time\ninflight, peak, lock = 0, 0, threading.Lock()\nsem = threading.BoundedSemaphore(4)\ndef job(i):\n    global inflight, peak\n    time.sleep(0.005)\n    return i\ndef bump():\n    global peak\n    with lock:\n        peak = max(peak, inflight)\nwith cf.ThreadPoolExecutor(4) as ex:\n    futs = []\n    for i in range(20):\n        sem.acquire()\n        f = ex.submit(job, i)\n        f.add_done_callback(lambda _f: sem.release())\n        futs.append(f)\n    for f in cf.as_completed(futs): f.result()\nprint(&#39;peak bounded&#39;, peak &lt;= 20)' explain='BoundedSemaphore 在回调释放许可前最多放 4 个在途；executor 内部队列因此恒有界，峰值内存可控，避免被自己的待办压垮。' />

<Quiz no='063-1' q='关于 Future.cancel()，下列哪项准确？' :options='["仅对 PENDING 有效返回 True，RUNNING 之后返回 False，不能强杀线程", "任何状态都能取消并立即停止线程", "cancel 会等任务跑完再改状态", "cancel 对 ThreadPoolExecutor 无效，只对 ProcessPoolExecutor 有效"]' answer="0" explain='cancel 在未启动时抢锁把状态置 CANCELLED；一旦 worker 取走 WorkItem 进入 RUNNING，外部无法终止线程，只能靠任务内部协作式退出。' />

<Quiz no='063-2' q='无上限 submit 导致内存爆掉，最直接的根因是？' :options='["executor 内部待办队列无界，Future 与参数全堆在内存", "max_workers 默认太小", "Future 状态机有 bug", "as_completed 会缓存所有结果"]' answer="0" explain='ThreadPoolExecutor 用无界 SimpleQueue 存 WorkItem；生产者不限流就会在峰值把待办堆满。应在提交侧用 Semaphore 或在途计数做背压。' />

<Quiz no='063-3' q='关于 executor.map，下列哪项准确？' :options='["按输入顺序 yield 结果，一次性提交全部输入，异常在迭代到该项时抛出", "按完成先后 yield", "自带在途背压", "返回 Future 列表"]' answer="0" explain='map 先 submit 完所有输入，再按输入顺序对 Future 逐个 result()；因此没有背压、会被最慢前置项拖住，失败要迭代到那一项才暴露。' />

<Predict no='063-4' q='max_workers=1 时先 submit 一个被 Event 阻塞的任务，再 submit 第二个并立刻 cancel，结果是？' :options='["cancel 返回 True，因为第二个仍 PENDING", "cancel 返回 False，因为池已启动", "抛 CancelledError", "两个任务都执行"]' answer='0' output='cancel pending True / f1 cancelled True True' explain='唯一 worker 被第一个任务占住，第二个 WorkItem 还在队列里处于 PENDING，cancel 抢到状态锁置为 CANCELLED 并返回 True；cancelled() 与 done() 随后都为 True。' />

<FillBlank no='063-5' tpl='___ concurrent.futures as cf' :answers='["import"]' hint='回想本讲关于 Executor 抽象 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Executor 抽象与默认并发度 的落点。' />

<KnowledgeCard :points='["Executor 管创建销毁与并发度；ThreadPoolExecutor 默认 min(32, cpu+4)，3.13 改用 os.process_cpu_count()", "Future 五状态：PENDING/RUNNING/CANCELLED/CANCELLED_AND_NOTIFIED/FINISHED；cancel 只对 PENDING 返回 True", "异常存在 Future 里，只有 result()/exception() 才暴露；submit 后不取结果等于吞异常", "as_completed 按完成先后 yield、最早暴露失败；map 按输入顺序且一次性提交全部、没有背压", "内部待办队列无界，生产者用 BoundedSemaphore + add_done_callback 做在途限流", "3.9+ shutdown(cancel_futures=True) 丢弃未启动待办；with 退出自动 shutdown(wait=True)"]' :pitfalls='["无上限 submit，峰值把内存撑爆", "submit 后从不取结果，异常永久静默", "以为 cancel() 能停掉正在跑的任务", "无上限地 submit 会把待办全堆进内存，服务在流量峰值先被自己的队列压垮"]' summary='线程池的价值是把「创建销毁」与「并发度控制」收敛到一处，Future 则把异步结果变成可传递的值' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| Executor 管创建销毁与并发度；ThreadPoolExecutor 默认 min(32, cpu+4)，3.13 改用 os.process_cpu_count() | 建立直觉 |
| Future 五状态：PENDING/RUNNING/CANCELLED/CANCELLED_AND_NOTIFIED/FINISHED；cancel 只对 PENDING 返回 True | 跑通示例 |
| 异常存在 Future 里，只有 result()/exception() 才暴露；submit 后不取结果等于吞异常 | 深入边界 |
| as_completed 按完成先后 yield、最早暴露失败；map 按输入顺序且一次性提交全部、没有背压 | 工程落地 |
| 内部待办队列无界，生产者用 BoundedSemaphore + add_done_callback 做在途限流 | 随堂检测 |
| 3.9+ shutdown(cancel_futures=True) 丢弃未启动待办；with 退出自动 shutdown(wait=True) | 复盘 |

1. Executor 管创建销毁与并发度；ThreadPoolExecutor 默认 min(32, cpu+4)，3.13 改用 os.process_cpu_count()

2. Future 五状态：PENDING/RUNNING/CANCELLED/CANCELLED_AND_NOTIFIED/FINISHED；cancel 只对 PENDING 返回 True

3. 异常存在 Future 里，只有 result()/exception() 才暴露；submit 后不取结果等于吞异常

[下一讲：multiprocessing：进程、Pool 与共享内存](/concurrency/multiprocessing)

```bash
python -c "from concurrent.futures import ThreadPoolExecutor as P; print(list(P(2).map(abs,[-1,-2])))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 Executor 抽象 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/063-threadpool.py`

```bash
python3 examples/lessons/063-threadpool.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/063-threadpool.py) · [全部示例代码索引](/examples/)
