---
title: 第 117 讲 · asyncio 事件循环与 Task 源码
description: 读懂取消、超时与回调的真实路径
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='45 分钟' goal='读懂取消、超时与回调的真实路径' prereq='第 116 讲 · 导入系统源码与 import hook' />

# 第 117 讲 · asyncio 事件循环与 Task 源码

导入、执行、内存都摸过一遍，接着看那条「用会了却讲不清」的 async 路径。超时设了不生效，取消后清理没跑干净，一段没有 `await` 的循环又卡住整条链路。会写 `await` 是一回事，知道它把控制权交给谁，是另一回事。

本讲从事件循环的 selector 讲起，看 Handle 排队；再看 `Task.__step` 只推进到下一个 await、Future 回调与取消怎样串起；最后把 shield 与 TaskGroup 放一起，说清 finally 收尾。需要协程与异常处理；学完你能读懂取消的真实路径，把 asyncio 与 Task 的清理写对。


## async 里一段无 await 的循环，让所有超时失效

一个 asyncio 服务给每个请求加了 `asyncio.wait_for(timeout=0.5)`，但某次上游变慢后超时完全没生效，心跳与超时一起失效，请求全卡住。

排查发现有人把一段 CPU 密集的纯 Python 循环直接放进了 async 函数，中间没有任何 `await`，事件循环被这个协程独占，定时器回调根本没机会运行。另一个 bug 出现在清理逻辑：开发者在 finally 里 `await` 一段关闭连接的代码，取消时这个 `await` 又被同一次取消打断，连接没关干净；

改用 shield 却又忘了限超时，结果清理段自己挂死。还有人捕获 `CancelledError` 后没重新抛出，让本该取消的 Task 变成了正常完成。Task 每次恢复只推进到下一个 await，取消是在这之后注入异常；理解这条路径，才能写对超时、finally 与 shield。

本讲沿 BaseEventLoop 与 Task 源码把取消与回调链拆开。

<Callout type="warn" title='先看一个真实会出错的写法' text='在 async 函数里跑无 await 的 CPU 密集循环：协程在一次 _ready 回调里一路跑完，_run_once 回不到 selector，所有超时、定时器与心跳一起饿死' />

<CheckList id='P117a' title='学完你应当能' :items='["能讲清 事件循环 _run_once、selector 与 Handle / TimerHandle", "能讲清 Task.__step、Future 回调链与取消语义", "能讲清 shield、超时与 TaskGroup 的正确组合", "能在工程里处理 调试模式与慢回调"]' />


## 事件循环 _run_once、selector 与 Handle / TimerHandle

asyncio 的事件循环基类在 `Lib/asyncio/base_events.py`，Unix 上默认实现是 `_UnixSelectorEventLoop`（用 selectors 封装 epoll、kqueue）。

核心是 `BaseEventLoop._run_once`：先算出最近定时器的到期时间，作为 `selector.select` 的 timeout；

把到期的 `TimerHandle` 从 `_scheduled` 堆移到 `_ready` 队列；再处理 selector 返回的就绪 IO 事件；最后按 `FIFO` 执行 `_ready` 里的 `Handle`。

`loop.call_soon` 把回调包成 Handle 追加到 `_ready`，`loop.call_later` 包成 TimerHandle 放进按时间排序的 `_scheduled`（`heapq`）。

`loop.time()` 返回单调时钟 `time.monotonic`，避免系统时间回拨影响定时器。关键推论：任何一个不含 `await`、或 `await` 到一个立即完成对象的协程，会在一次 `_ready` 回调里一路跑到结束，期间 `_run_once` 回不到 selector，所有定时器、IO 与心跳一起饿死。

CPU 密集循环必须放进进程池或用 `asyncio.to_thread`，debug 模式下 `slow_callback_duration`（默认 0.1 秒）会把超过该时长的回调打进日志。

**事件循环核心对象与职责**

| 对象 | 源码位置 | 职责 |
| --- | --- | --- |
| BaseEventLoop | base_events.py | _run_once 调度就绪回调与定时器 |
| _UnixSelectorEventLoop | selector_events.py | 用 selectors 封装 epoll/kqueue 做 IO 多路复用 |
| Handle | events.py | call_soon 包装的就绪回调 |
| TimerHandle | events.py | call_later 包装的定时回调，进 _scheduled 堆 |
| Task | tasks.py | Future 子类，__step 推进协程到下一个 await |

<SequenceDiagram title='第 117 讲 · 调用时序' caption='从触发到收尾，标出最可能失败的两个位置' :actors='["调用方", "核心逻辑", "外部依赖"]' :steps='[{"from": "调用方", "to": "核心逻辑", "label": "发起调用", "note": "事件循环 _run_once…", "kind": "call"}, {"from": "核心逻辑", "to": "核心逻辑", "label": "检查前置", "note": "Task.__step、Fu…", "kind": "self"}, {"from": "核心逻辑", "to": "外部依赖", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "外部依赖", "to": "核心逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "核心逻辑", "to": "调用方", "label": "返回或降级", "note": "清理资源", "kind": "return"}]' />


### _ready 回调一路跑完，selector 回不去

```python
import asyncio

async def main():
    loop = asyncio.get_running_loop()
    print('loop_class', type(loop).__name__)
    print('time_positive', loop.time() > 0)
    calls = []
    loop.call_soon(calls.append, 'soon')
    h = loop.call_later(0.001, calls.append, 'later')
    print('timer_type', type(h).__name__)
    await asyncio.sleep(0.02)
    print('calls', calls)

asyncio.run(main())
```

<OutputBox title='原理验证' output='loop_class _UnixSelectorEventLoop\ntime_positive True\ntimer_type TimerHandle\ncalls [&#39;soon&#39;, &#39;later&#39;]' />


## Task.__step、Future 回调链与取消语义

Task 是 Future 的子类（`Lib/asyncio/tasks.py`），`create_task` 把协程包成 Task 并用 call_soon 调度它的 `__step`。

`__step` 每次只把协程推进到下一个 `await`：若 `await` 的 Future 未完成，Task 把自己通过 `add_done_callback` 注册为唤醒回调；

Future 完成时调用 `__wakeup`，再 call_soon 重新排入 `__step`，如此往复。

取消不是抢占：`Task.cancel()` 设置 `_must_cancel` 并递增 cancelling 计数，若 Task 正挂在某个 Future 上，就改为取消那个 Future，使 `__wakeup` 收到 `CancelledError`；下一次 `__step` 在协程内抛出该异常。

3.11 起 `Task.cancelling()` 返回被请求取消的次数、`Task.uncancel()` 递减它，用来区分「被外部取消」与「协程自己吞掉取消」。

若协程捕获 `CancelledError` 后不重新抛出，Task 会以正常结果完成，`cancelled()` 为 False——这是很多超时逻辑悄悄失效的根因。取消会触发 finally，但 finally 里的 `await` 本身也可能被同一次取消链打断，因此清理段要用 shield 保护并再套一层超时。

```python
import asyncio

async def work():
    try:
        await asyncio.sleep(10)
        return 'done'
    except asyncio.CancelledError:
        return 'cancelled'

async def main():
    t = asyncio.create_task(work())
    print('task_type', type(t).__name__)
    print('coro', t.get_coro().__name__)
    await asyncio.sleep(0)
    print('cancelling_before', t.cancelling())
    t.cancel()
    print('cancelling_after', t.cancelling())
    r = await t
    print('result', r)
    print('cancelled_flag', t.cancelled(), 'done', t.done())

asyncio.run(main())
```

<OutputBox title='主示例运行结果' output='task_type Task\ncoro work\ncancelling_before 0\ncancelling_after 1\nresult cancelled\ncancelled_flag False done True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import asyncio\n\nasync def work():\n    try:\n        await asyncio.sleep(10)\n        return &#39;done&#39;\n    except asyncio.CancelledError:\n        return &#39;cancelled&#39;\n\nasync def main():\n    t = asyncio.create_task(work())\n    print(&#39;task_type&#39;, type(t).__name__)\n    print(&#39;coro&#39;, t.get_coro().__name__)\n    await asyncio.sleep(0)\n    print(&#39;cancelling_before&#39;, t.cancelling())\n    t.cancel()\n    print(&#39;cancelling_after&#39;, t.cancelling())\n    r = await t\n    print(&#39;result&#39;, r)\n    print(&#39;cancelled_flag&#39;, t.cancelled(), &#39;done&#39;, t.done())\n\nasyncio.run(main())' :notes='["导入 asyncio", "空行，只用于分隔逻辑块，不影响执行结果。", "定义被取消的工作协程", "捕获取消异常以观察 Task 最终状态", "长时间睡眠，模拟等待中的任务", "正常完成时的返回值", "CancelledError 被吞掉并返回一个字符串", "吞掉取消后 Task 变为正常完成而非取消态", "空行，只用于分隔逻辑块，不影响执行结果。", "主协程创建并管理 Task", "create_task 把协程包成 Task 并排入事件循环", "打印类型，确认为 Task", "get_coro 取回被包装的协程对象及其名字", "让出一次控制权，使 Task 推进到 sleep", "取消前 cancelling 计数为 0", "cancel 设置取消请求并递增计数", "cancel 后 cancelling 变为 1", "await Task 取回结果", "协程吞掉 CancelledError，返回 cancelled 字符串", "cancelled() 为 False，因为异常没再抛出", "空行，只用于分隔逻辑块，不影响执行结果。", "用 asyncio.run 驱动事件循环"]' title='第 117 讲 · asyncio 事件循环与 Task 源码' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：吞掉 CancelledError 与重新抛出

```python
import asyncio

async def main():
    async def job():
        await asyncio.sleep(0.01)
        return 'ok'
    t = asyncio.create_task(job())
    s = asyncio.shield(t)
    s.cancel()
    try:
        await s
    except asyncio.CancelledError:
        print('shield_got_cancelled', True)
    print('task_cancelled', t.cancelled())
    print('task_result', await t)

asyncio.run(main())
```

<OutputBox title='对照写法：先自己猜，再点开' output='shield_got_cancelled True\ntask_cancelled False\ntask_result ok' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import asyncio\n\nasync def work():\n    try:\n        await asyncio.sleep(10)\n        return &#39;done&#39;\n    except asyncio.CancelledError:\n        return &#39;cancelled&#39;\n\nasync def main():\n    t = asyncio.create_task(work())\n    print(&#39;task_type&#39;, type(t).__name__)\n    print(&#39;coro&#39;, t.get_coro().__name__)\n    await asyncio.sleep(0)\n    print(&#39;cancelling_before&#39;, t.cancelling())\n    t.cancel()\n    print(&#39;cancelling_after&#39;, t.cancelling())\n    r = await t\n    print(&#39;result&#39;, r)\n    print(&#39;cancelled_flag&#39;, t.cancelled(), &#39;done&#39;, t.done())\n\nasyncio.run(main())", "note": "事件循环 _run_once、selector 与 Handle / TimerHandle"}, {"label": "对照 / 进阶", "code": "import asyncio\n\nasync def main():\n    async def job():\n        await asyncio.sleep(0.01)\n        return &#39;ok&#39;\n    t = asyncio.create_task(job())\n    s = asyncio.shield(t)\n    s.cancel()\n    try:\n        await s\n    except asyncio.CancelledError:\n        print(&#39;shield_got_cancelled&#39;, True)\n    print(&#39;task_cancelled&#39;, t.cancelled())\n    print(&#39;task_result&#39;, await t)\n\nasyncio.run(main())", "note": "Task.__step、Future 回调链与取消语义"}]' title='两种写法切换看' />


## 捕获 CancelledError 后不重新抛出

<Callout type="warn" title='本讲最容易踩的坑' text='在 async 函数里跑无 await 的 CPU 密集循环：协程在一次 _ready 回调里一路跑完，_run_once 回不到 selector，所有超时、定时器与心跳一起饿死' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：在 async 函数里跑无 await 的…", "body": "协程在一次 _ready 回调里一路跑完，_run_once 回不到 selector，所有超时、定时器与心跳一起饿死", "tip": "把计算放进 asyncio.to_thread 或进程池，或在循环里定期 await asyncio.sleep(0)；开 debug 模式查慢回调"}, {"title": "第 2 步：捕获 CancelledError 后不重新…", "body": "Task 变成正常完成，cancelled() 为 False，上层超时逻辑以为任务成功，取消语义被悄悄吞掉", "tip": "清理完成后重新 raise，让取消向上传播；需要区分来源时用 cancelling()/uncancel()"}, {"title": "第 3 步：finally 里直接 await 清理且不…", "body": "清理段的 await 可能被同一次取消链再次打断，连接与缓冲没关干净", "tip": "用 asyncio.shield 包裹清理并再套 asyncio.timeout 限定上限，保留对 inner 的引用并最终 await 它"}]' />


## shield、超时与 TaskGroup 的正确组合

`asyncio.shield(inner)` 包一层外层 Future：取消外层只影响 shield 本身，被保护的 inner Task 继续运行，适用于「撤销等待但保留后台工作」或保护清理段。

要注意 shield 若无人再 `await` inner，inner 的异常可能没人接收，因此得保留对 inner 的引用，最终 await 它或加 done callback。

`asyncio.timeout`（3.11 起）用上下文管理器在超时时向其作用域内的当前 Task 注入取消，配合 `Task.uncancel()` 可把「超时」与「外部取消」区分开；

`asyncio.wait_for` 内部同样基于取消实现，超时后默认会等待被取消协程真正结束。

TaskGroup（3.11 起，与 PEP 654 的 `ExceptionGroup` 配套）把一组子任务的生命周期绑在一起：任一子任务抛异常就取消其余子任务，并以 `ExceptionGroup` 汇总，退出 async with 时保证所有任务已结束，避免遗留游离 Task。

取消路径的正确写法是：清理段用 shield 包裹并限定超时，捕获 `CancelledError` 后做完清理再 raise 让取消语义向上传播，同时开 debug 模式查慢回调与「Task was destroyed but it is pending」这类泄漏信号。

**取消相关 API 与版本**

| API | 版本 | 行为 |
| --- | --- | --- |
| Task.cancel() | 长期 | 设取消请求，向等待的 Future 或下次 __step 注入 CancelledError |
| Task.cancelling() | 3.11+ | 返回累计取消请求次数 |
| Task.uncancel() | 3.11+ | 递减计数，配合 asyncio.timeout 区分超时 |
| asyncio.shield | 长期 | 取消外层 Future，不取消被保护的 inner |
| asyncio.timeout | 3.11+ | 上下文管理器超时注入取消 |
| TaskGroup | 3.11+ 与 PEP 654 | 异常取消其余子任务并以 ExceptionGroup 汇总 |

asyncio 是单线程协作式调度：`_run_once` 一次循环先把到期 `TimerHandle` 从 `_scheduled` 堆移到 `_ready`，处理 selector 返回的就绪 IO，再按 `FIFO` 执行 `_ready` 里的 `Handle`。每个 Handle 都必须尽快返回，否则整轮循环停摆。

`Task.__step` 让协程每次只推进到下一个 `await`：若等待的 Future 未完成，Task 通过 `add_done_callback` 把 `__wakeup` 挂到该 Future 上，Future 完成时再 call_soon 重新排入 `__step`；

于是取消不是抢占线程，而是设置 `_must_cancel` 并在下一次 `__step`、或经 `__wakeup` 向协程注入 `CancelledError`。这解释了三个结论：无 `await` 的循环让定时器永远等不到 `_run_once` 的下一次迭代；

捕获 `CancelledError` 不重新抛出会让 Task 以正常结果结束、`cancelled()` 变 False；finally 里的 `await` 仍处在同一个取消链上，可能被再次打断。shield 通过包一层外层 Future 把取消隔离在外层，inner 继续运行；

TaskGroup 用结构化并发保证退出时无游离任务，异常以 `ExceptionGroup` 汇总；

3.11 的 `cancelling` 与 `uncancel` 让 `asyncio.timeout` 能把自己的取消与外部取消区分开。


## 取消路径的失效信号

**取消路径的失效信号**

| 现象 | 根因 | 可观测信号 |
| --- | --- | --- |
| 超时与心跳一起失效 | async 函数里无 await 的 CPU 循环独占事件循环 | slow_callback_duration 日志、loop 停滞时长 |
| 捕获 CancelledError 后任务仍正常完成 | 异常被吞未重新抛出 | task.cancelled() 为 False |
| finally 里的清理没跑完 | 清理段 await 被同一次取消打断 | 连接未关闭、资源计数不归零 |
| Task was destroyed but it is pending | 未 await 的游离 Task 被丢弃 | debug 模式警告 |


## 带超时、取消与 shield 清理的任务运行器

把一个外部调用封装成有边界的异步操作：用 `asyncio.timeout` 限定总时长，取消时保护清理段不被同一次取消打断，清理本身再套超时，并保留对后台任务的引用避免游离 Task。

真实服务里还要开 debug 模式、记录慢回调与取消次数指标。下面这段用标准库把取消路径写成可核对的流程，重点观察清理如何被 shield 保护、取消如何向上传播，以及每个 `await` 都有明确边界。

```python
import asyncio

async def close_conn():
    await asyncio.sleep(0.01)
    return 'closed'

async def call_remote():
    await asyncio.sleep(10)
    return 'ok'

async def run_once():
    try:
        async with asyncio.timeout(0.05):
            return await call_remote()
    except TimeoutError:
        cleanup = asyncio.create_task(close_conn())
        try:
            async with asyncio.timeout(0.05):
                await asyncio.shield(cleanup)
        except TimeoutError:
            cleanup.cancel()
        return 'timeout'

async def main():
    print(await run_once())

asyncio.run(main())
```

<Callout type="idea" title='落地提示' text='开启 debug 模式查慢回调，用 TaskGroup 管理生命周期，清理段用 shield 并限定超时' />

<CheckList id='P117b' title='上线前自检' :items='["能复现并解释「在 async 函数里跑无 await 的 CPU 密集循环」", "能复现并解释「捕获 CancelledError 后不重新抛出」", "能复现并解释「finally 里直接 await 清理且不加保护」", "能用一条命令验证 BaseEventLoop 与 selector", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import dis, sys; print(sys.version.split()[0]); dis.dis(lambda x:x)"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 BaseEventLoop 与 selector 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 在 async 函数里跑无 await 的 CPU 密集循环 | 协程在一次 _ready 回调里一路跑完，_run_once 回不到 selector，所有超时、定时器与心跳一起饿死 | 把计算放进 asyncio.to_thread 或进程池，或在循环里定期 await asyncio.sleep(0)；开 debug 模式查慢回调 |
| 捕获 CancelledError 后不重新抛出 | Task 变成正常完成，cancelled() 为 False，上层超时逻辑以为任务成功，取消语义被悄悄吞掉 | 清理完成后重新 raise，让取消向上传播；需要区分来源时用 cancelling()/uncancel() |
| finally 里直接 await 清理且不加保护 | 清理段的 await 可能被同一次取消链再次打断，连接与缓冲没关干净 | 用 asyncio.shield 包裹清理并再套 asyncio.timeout 限定上限，保留对 inner 的引用并最终 await 它 |


## 练习、预测题与速记

<Exercise title='基础：观察取消与吞掉取消的区别' task='创建 Task 后 cancel，分别写「捕获后不 re-raise」与「捕获后 re-raise」两版，打印各自的 cancelled() 与结果。' solution='import asyncio\nasync def keep():\n    try:\n        await asyncio.sleep(10)\n    except asyncio.CancelledError:\n        return &#39;kept&#39;\nasync def main():\n    t = asyncio.create_task(keep())\n    await asyncio.sleep(0)\n    t.cancel()\n    print(await t, t.cancelled())\nasyncio.run(main())' explain='不 re-raise 时 Task 正常完成、cancelled() 为 False；要维持取消语义必须在清理后重新 raise CancelledError。' />

<Exercise title='进阶：验证 shield 不取消 inner' task='用 shield 包一个 Task，取消外层后打印 inner.cancelled() 与 inner 结果，并解释为什么还要最终 await inner。' solution='import asyncio\nasync def job():\n    await asyncio.sleep(0.01)\n    return &#39;ok&#39;\nasync def main():\n    t = asyncio.create_task(job())\n    s = asyncio.shield(t)\n    s.cancel()\n    try:\n        await s\n    except asyncio.CancelledError:\n        pass\n    print(t.cancelled(), await t)\nasyncio.run(main())' explain='取消 shield 只影响外层 Future，inner 继续运行；必须保留引用并最终 await，否则 inner 的异常可能无人接收或成为游离 Task。' />

<Quiz no='117-1' q='某 async 函数里一段无 await 的纯 Python 循环让所有超时失效，原因是？' :options='["协程独占事件循环，_run_once 回不到 selector，定时器回调无法执行", "asyncio.timeout 在 CPU 循环里不生效", "GIL 被释放导致竞态", "sleep 被编译器优化掉"]' answer="0" explain='协作式调度下每个回调必须尽快返回；无 await 的循环在一次 _ready 回调里跑完，IO 与定时器全部饿死，应放 to_thread 或进程池。' />

<Quiz no='117-2' q='捕获 CancelledError 后不重新抛出，Task 的最终状态是？' :options='["正常完成，cancelled() 为 False", "仍为 cancelled() 为 True", "抛 RuntimeError", "永久 pending"]' answer="0" explain='取消靠向协程注入异常实现；异常被吞掉后 __step 拿到正常返回值，Task 以结果完成，上层超时逻辑会误判成功。' />

<Quiz no='117-3' q='关于 finally 里的清理 await，最稳妥的写法是？' :options='["用 shield 包裹并再套一层 timeout 限定上限", "直接 await，取消不会影响 finally", "用 time.sleep 替代 await", "把清理放到另一个线程即可"]' answer="0" explain='finally 中的 await 仍可能被同一次取消链打断；shield 隔离取消、外层 timeout 防止清理自身挂死，并保留 inner 引用最终 await。' />

<Predict no='117-4' q='work() 捕获 CancelledError 并返回 &#39;cancelled&#39;，被 cancel 后 t.cancelled() 是多少？' :options='["False，因为异常被吞掉，Task 正常完成", "True，只要调用过 cancel 就成立", "抛 InvalidStateError"]' answer='0' output='cancelled_flag False done True' explain='Task.cancel 注入 CancelledError，但 work 捕获后返回字符串未重新抛出，__step 以正常结果结束；cancelling() 虽为 1，cancelled() 仍为 False。' />

<FillBlank no='117-5' tpl='import  ___ io' :answers='["async"]' hint='回想本讲关于 BaseEventLoop 与 selector 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 事件循环 _run_once、selector 与 Handle / TimerHandle 的落点。' />

<KnowledgeCard :points='["BaseEventLoop._run_once 处理定时器、selector 就绪 IO 与 _ready 回调；无 await 的循环会独占 loop", "call_soon 生成 Handle 进 _ready，call_later 生成 TimerHandle 进 _scheduled 堆，loop.time 用单调时钟", "Task.__step 每次只推进到下一个 await，Future 完成经 add_done_callback/__wakeup 重新调度", "取消是注入 CancelledError 而非抢占；吞掉异常会让 cancelled() 变 False", "3.11+ 的 cancelling/uncancel 配合 asyncio.timeout 区分超时与外部取消；TaskGroup 用 ExceptionGroup 汇总", "清理段用 shield 加 timeout 保护并保留 inner 引用；debug 模式用 slow_callback_duration 查慢回调"]' :pitfalls='["在 async 函数里跑无 await 的 CPU 密集循环", "捕获 CancelledError 后不重新抛出", "finally 里直接 await 清理且不加保护", "把 CPU 密集循环放进 async 函数不加 await，事件循环会被独占，所有超时与心跳一起失效"]' summary='Task 每次恢复只推进到下一个 await，取消则是在这之后注入异常；理解这条路径才能写对 finally 与 shield' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| BaseEventLoop._run_once 处理定时器、selector 就绪 IO 与 _ready 回调；无 await 的循环会独占 loop | 建立直觉 |
| call_soon 生成 Handle 进 _ready，call_later 生成 TimerHandle 进 _scheduled 堆，loop.time 用单调时钟 | 跑通示例 |
| Task.__step 每次只推进到下一个 await，Future 完成经 add_done_callback/__wakeup 重新调度 | 深入边界 |
| 取消是注入 CancelledError 而非抢占；吞掉异常会让 cancelled() 变 False | 工程落地 |
| 3.11+ 的 cancelling/uncancel 配合 asyncio.timeout 区分超时与外部取消；TaskGroup 用 ExceptionGroup 汇总 | 随堂检测 |
| 清理段用 shield 加 timeout 保护并保留 inner 引用；debug 模式用 slow_callback_duration 查慢回调 | 复盘 |

1. BaseEventLoop._run_once 处理定时器、selector 就绪 IO 与 _ready 回调；无 await 的循环会独占 loop

2. call_soon 生成 Handle 进 _ready，call_later 生成 TimerHandle 进 _scheduled 堆，loop.time 用单调时钟

3. Task.__step 每次只推进到下一个 await，Future 完成经 add_done_callback/__wakeup 重新调度

[下一讲：GIL 源码、自适应解释器与无 GIL 路线](/advanced/gil-source)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/117-asyncio-source.py`

```bash
python3 examples/lessons/117-asyncio-source.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/117-asyncio-source.py) · [全部示例代码索引](/examples/)
