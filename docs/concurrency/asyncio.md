---
title: 第 069 讲 · asyncio 深入：Task、Future 与事件循环
description: 掌握任务生命周期与取消语义
---

<StageHeader stage='L6 · 并发与异步' level='★★★★☆' time='45 分钟' goal='掌握任务生命周期与取消语义' prereq='第 068 讲 · async / await 与协程对象' />

# 第 069 讲 · asyncio 深入：Task、Future 与事件循环

单个协程能跑对之后，真实服务里往往是一批任务一起上，要理清的是谁被调度、结果怎么收、取消时谁来收尾。一个对账脚本起了几十个子任务，计数总比预期少几条，日志却干净，换台机器又正常，这种时灵时不灵最磨人。

从 asyncio 的事件循环、`Task`、`Future` 三者的分工起步，走到 `asyncio.create_task` 与 `asyncio.gather` 怎样组织并发，再看 `Future` 的状态与取消语义，末了用 `TaskGroup` 收成结构化并发。前置是 async/await、协程对象与 gather；学完能掌握任务生命周期，把超时、失败策略与清理逻辑写进 `finally`，让并发关得干净。


## 压测里莫名少了几条计数，日志却没有任何异常

一个对账服务用 `asyncio.create_task` 起了几十个子任务拉数据，压测时发现计数总比预期少几条，日志里却没有任何异常；换一台机器又正常。

排查两周才定位到两件事：事件循环对 `Task` 只持弱引用，没被变量持有的任务会在执行途中被 GC 回收；另一个协程里用 `except Exception` 想把收尾逻辑兜住，结果取消时清理代码根本没跑——因为 3.8 起 `asyncio.CancelledError` 已改成 `BaseException` 子类，except Exception 捕获不到它。

有人以为调用 `task.cancel()` 是「强杀线程」，实际它只是请求在下一个 `await` 点抛 CancelledError。这些都不是语法细节，而是 `Task`、`Future`、事件循环三者分工与取消语义没对齐。本讲把任务生命周期、`Future` 状态机与结构化并发讲到能推导线上行为。

<Callout type="warn" title='先看一个真实会出错的写法' text='裸 asyncio.create_task(...) 不保存引用：事件循环只弱引用 Task，任务可能执行途中被 GC 回收，异常也无人读取' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段六 · 并发与异步 |
| 前置 | 第 068 讲 · async / await 与协程对象 |
| 难度 / 建议时长 | ★★★★☆ · 45 分钟 |
| 本讲新增 | loop 与策略、create_task 与 gather、Future 状态 |
| 一句话目标 | 掌握任务生命周期与取消语义 |
| 为下一讲铺垫 | 阶段综合：并发爬虫四级演进 |


## 事件循环是单线程反应器：就绪队列、定时堆与 selector

`asyncio.Future` 表示一个「还没填值的结果」，状态由 `PENDING` 走到 `FINISHED` 或 `CANCELLED`：`done()` 判断是否结束、`cancelled()` 判断是否被取消、`result()` 在已取消时抛 CancelledError、设置了异常则抛该异常、`exception()` 返回异常对象。

标准写法是 `loop.create_future()`，不要直接构造 `asyncio.Future()`（后者需要显式绑定 loop）。

`add_done_callback(cb)` 在状态落定时回调，回调经 `loop.call_soon` 调度。

`asyncio.Task` 是 `Future` 的子类，它额外持有要驱动的协程：`asyncio.create_task(coro)`（3.7 起）把协程包装成 `Task` 并用 `call_soon` 排进就绪队列，要求当前线程有运行中的 loop，可传 `name` 给任务命名，`Task.get_name` 与 `set_name` 是 3.8 起才有。

`loop.call_soon(cb, *args)` 按 `FIFO` 排入就绪队列，`loop.call_later(delay, cb)` 返回 `TimerHandle`，它的 `cancel()` 只返回 None、并不报告是否取消成功，要判断状态得读 `cancelled()`（3.7 起）——这与 `Future.cancel()` 返回布尔值不同。

事件循环对 `Task` 只保留弱引用，官方文档明确要求调用方自己保存强引用（例如一个 set），否则任务可能被中途回收。

<Callout type="tip" title='核心心智模型' text='`asyncio.Future` 表示一个「还没填值的结果」，状态由 `PENDING` 走到 `FINISHED` 或 `CANCELLED`：`done()` 判断是否结束、`cancelled()` 判断是否被取消、`result()` 在已取消时抛 CancelledError、设置了异常则…' />

<ConceptDiagram type='compare2' title='第 069 讲 · Task 是调度单位，Future 是结果占位符' labels='Task 是调度单位，Future 是结果占…|取消是协作式的：在下一个 await 点抛…|结构化并发：TaskGroup 与异常组|取消与 CancelledError' caption='掌握任务生命周期与取消语义' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

事件循环本质是单线程反应器：一个就绪队列（deque 的 `Handle`）、一个按到期时间组织的小根堆（`TimerHandle`）、以及 select/epoll/kqueue 的 IO 多路复用。

`loop._run_once` 先用最近定时器算出 select 的超时，取就绪 fd 把对应回调 `call_soon` 入队，再把到期定时器移入就绪队列，最后逐个执行 `Handle._run`。

`Task.__step` 调用 `coro.send(None)`：协程 yield 出 None 就重新入队、yield 出未完成 `Future` 就给它挂 done 回调、`Future` 完成则把结果 send 回去；`asyncio.sleep` 正是 `call_later` 加一个 `Future`。

`cancel()` 设置 `_must_cancel`，下一次 `__step` 改为 `throw(CancelledError)` 而非 `send(None)`，所以取消点必然落在 `await`。

3.11 的 `TaskGroup` 在 `_on_task_done` 里一旦见到异常就中止其余任务并把异常装进 `ExceptionGroup`，保证离开作用域时没有游离任务。


## Task 是调度单位，Future 只是结果占位符

**Future / Task / Handle 关键 API 与状态**

| API / 状态 | 签名或所属 | 语义 / 边界 |
| --- | --- | --- |
| loop.create_future() | Future | 推荐创建方式，初始 PENDING |
| Future.done() / cancelled() | bool | 区分结束与「被取消而结束」 |
| Future.result() | 值 / 抛异常 | CANCELLED 抛 CancelledError，set_exception 抛该异常 |
| add_done_callback(cb) | Future | 状态落定后经 call_soon 回调 |
| asyncio.create_task(coro, name=None) | 3.7+ Task | 需 running loop；Task 是 Future 子类 |
| loop.call_soon(cb, *args) | Handle | FIFO 排入就绪队列 |
| loop.call_later(delay, cb) | TimerHandle | cancel() 在 3.13 返回 None，读状态用 cancelled() |
| Task.get_name() / set_name() | 3.8+ | 给任务命名便于日志定位 |

<Term word='loop 与策略' text='`asyncio.Future` 表示一个「还没填值的结果」，状态由 `PENDING` 走到 `FINISHED` 或 `CANCELLED`：`done()` 判断是否结束、`cancelled()` 判断是否被取消、`result()` 在已取消时抛 CancelledError、设置了异常则抛该异常…' />

<Term word='create_task 与 gather' text='`task.cancel()` 并不中断线程，只是把 `Task` 标成「待取消」；当下一次 `Task.__step` 驱动协程时，不再 `send(None)` 而是在当前 `await` 点 `throw(asyncio.CancelledError)`。自 3.8 起…' />


## create_task、gather 与 call_soon 的原语对照

```python
import asyncio

async def main():
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    print('initial', fut.done(), fut.cancelled())

    def finish():
        fut.set_result('ready')

    loop.call_soon(finish)
    await fut
    print('after set_result', fut.done(), fut.result())

    async def slow():
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            print('slow got CancelledError')
            raise
        finally:
            print('slow finally cleanup')

    t = asyncio.create_task(slow())
    await asyncio.sleep(0)
    t.cancel()
    try:
        await t
    except asyncio.CancelledError:
        print('await t raised CancelledError')

asyncio.run(main())
```

<OutputBox title='主示例运行结果' output='initial False False\nafter set_result True ready\nslow got CancelledError\nslow finally cleanup\nawait t raised CancelledError' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import asyncio\n\nasync def main():\n    loop = asyncio.get_running_loop()\n    fut = loop.create_future()\n    print(&#39;initial&#39;, fut.done(), fut.cancelled())\n\n    def finish():\n        fut.set_result(&#39;ready&#39;)\n\n    loop.call_soon(finish)\n    await fut\n    print(&#39;after set_result&#39;, fut.done(), fut.result())\n\n    async def slow():\n        try:\n            await asyncio.sleep(10)\n        except asyncio.CancelledError:\n            print(&#39;slow got CancelledError&#39;)\n            raise\n        finally:\n            print(&#39;slow finally cleanup&#39;)\n\n    t = asyncio.create_task(slow())\n    await asyncio.sleep(0)\n    t.cancel()\n    try:\n        await t\n    except asyncio.CancelledError:\n        print(&#39;await t raised CancelledError&#39;)\n\nasyncio.run(main())' :notes='["导入 asyncio 以使用事件循环、Future 与 Task", "空行，只用于分隔逻辑块，不影响执行结果。", "定义入口协程，asyncio.run 会驱动它", "get_running_loop 取当前运行中的 loop", "loop.create_future 创建 PENDING 状态的 Future", "初始 done 与 cancelled 均为 False", "空行，只用于分隔逻辑块，不影响执行结果。", "定义回调，用于给 Future 填结果", "set_result 把 Future 推进到 FINISHED", "空行，只用于分隔逻辑块，不影响执行结果。", "call_soon 把回调排进就绪队列，下一轮执行", "await fut 挂起 main，直到回调填值后恢复", "恢复后 done 为 True，result 取回 ready", "空行，只用于分隔逻辑块，不影响执行结果。", "定义会被取消的慢任务", "await 点是取消注入的位置", "显式捕获 CancelledError，因它是 BaseException 子类", "打印证据后重新抛出，保持取消语义", "finally 放清理逻辑，取消时也会执行", "create_task 把 slow 包装成 Task 并调度", "sleep(0) 让 slow 运行到它的 await 点", "cancel 只请求取消，在下一 await 点抛异常", "空行，只用于分隔逻辑块，不影响执行结果。", "await 已取消的 Task 同样抛 CancelledError", "在调用方接住，避免异常冒出 asyncio.run", "统一入口：建 loop、跑 main、收尾关闭", "loop.call_soon 走 FIFO 就绪队列，call_later 返回 TimerHandle，cancel() 返回 None、读状态用 cancelled()", "gather 默认不取消兄弟任务；3.11 TaskGroup 失败即取消全组并抛 ExceptionGroup，用 except* 处理", "3.11 起 asyncio.TimeoutError 等于内置 TimeoutError，asyncio.timeout 与 Task.uncancel() 配套结构化并发", "Task 是 Future 子类：Future 占位结果（done/cancelled/result/exception），Task 额外驱动协程", "空行，只用于分隔逻辑块，不影响执行结果。", "loop.create_future() 是标准创建方式；create_task 需 running loop，且调用方必须保存强引用"]' title='第 069 讲 · asyncio 深入：Task、Future 与事件循环' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import asyncio

async def ok(n):
    await asyncio.sleep(0)
    return n * 2

async def boom():
    await asyncio.sleep(0)
    raise ValueError('bad')

async def main():
    try:
        async with asyncio.TaskGroup() as tg:
            t1 = tg.create_task(ok(3))
            t2 = tg.create_task(boom())
    except* ValueError as eg:
        print('caught', type(eg).__name__, 'count', len(eg.exceptions))
    print('t1.done', t1.done(), 't2.cancelled', t2.cancelled())

asyncio.run(main())
```

<OutputBox title='对照写法：先自己猜，再点开' output='caught ExceptionGroup count 1\nt1.done True t2.cancelled False' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import asyncio\n\nasync def main():\n    loop = asyncio.get_running_loop()\n    fut = loop.create_future()\n    print(&#39;initial&#39;, fut.done(), fut.cancelled())\n\n    def finish():\n        fut.set_result(&#39;ready&#39;)\n\n    loop.call_soon(finish)\n    await fut\n    print(&#39;after set_result&#39;, fut.done(), fut.result())\n\n    async def slow():\n        try:\n            await asyncio.sleep(10)\n        except asyncio.CancelledError:\n            print(&#39;slow got CancelledError&#39;)\n            raise\n        finally:\n            print(&#39;slow finally cleanup&#39;)\n\n    t = asyncio.create_task(slow())\n    await asyncio.sleep(0)\n    t.cancel()\n    try:\n        await t\n    except asyncio.CancelledError:\n        print(&#39;await t raised CancelledError&#39;)\n\nasyncio.run(main())", "note": "Task 是调度单位，Future 是结果占位符"}, {"label": "对照 / 进阶", "code": "import asyncio\n\nasync def ok(n):\n    await asyncio.sleep(0)\n    return n * 2\n\nasync def boom():\n    await asyncio.sleep(0)\n    raise ValueError(&#39;bad&#39;)\n\nasync def main():\n    try:\n        async with asyncio.TaskGroup() as tg:\n            t1 = tg.create_task(ok(3))\n            t2 = tg.create_task(boom())\n    except* ValueError as eg:\n        print(&#39;caught&#39;, type(eg).__name__, &#39;count&#39;, len(eg.exceptions))\n    print(&#39;t1.done&#39;, t1.done(), &#39;t2.cancelled&#39;, t2.cancelled())\n\nasyncio.run(main())", "note": "取消是协作式的：在下一个 await 点抛 CancelledError"}]' title='两种写法切换看' />


## 实测：一次取消在哪个 await 点真正生效

```python
import asyncio, inspect, sys

print('Task subclass of Future', issubclass(asyncio.Task, asyncio.Future))
print('CancelledError is BaseException', asyncio.CancelledError.__mro__[1] is BaseException)
print('TaskGroup 3.11+', hasattr(asyncio, 'TaskGroup'), sys.version_info >= (3, 11))
loop = asyncio.new_event_loop()
h = loop.call_later(10, lambda: None)
print('call_later type', type(h).__name__)
print('cancelled before', h.cancelled())
h.cancel()
print('cancelled after', h.cancelled())
loop.close()
```

<OutputBox title='原理验证' output='Task subclass of Future True\nCancelledError is BaseException True\nTaskGroup 3.11+ True True\ncall_later type TimerHandle\ncancelled before False\ncancelled after True' />

```bash
python -c "import asyncio; print(len(asyncio.run(asyncio.gather(*[asyncio.sleep(0,i) for i in range(3)]))))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 loop 与策略 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 取消是协作式的：CancelledError 与 finally 清理

`task.cancel()` 并不中断线程，只是把 `Task` 标成「待取消」；当下一次 `Task.__step` 驱动协程时，不再 `send(None)` 而是在当前 `await` 点 `throw(asyncio.CancelledError)`。

自 3.8 起 `asyncio.CancelledError` 继承 `BaseException`（其 `__mro__` 是 CancelledError → BaseException → object），因此 except Exception 完全捕获不到它，清理逻辑必须放在 `finally`，或用 except `asyncio.CancelledError` 显式接住后再 raise。

清理段里若又 `await`，可能被二次取消，敏感收尾可用 `asyncio.shield(aw)` 屏蔽外层取消。

`asyncio.wait_for` 超时会取消内层并抛 TimeoutError（3.11 起 `asyncio.TimeoutError` 就是内置 `TimeoutError`），3.11 起还有 `asyncio.timeout` 上下文管理器与 `Task.uncancel()`。

要警惕「吞掉取消」：若在协程里接住 CancelledError 却不重新抛出，`Task` 会以为正常完成，`finally` 之后的收尾与上层取消协议全部失效。


## 取消语义从 3.7 到 3.11 的版本差异

**取消语义的版本差异与影响**

| 版本 / 机制 | 行为 | 对代码的要求 |
| --- | --- | --- |
| 3.8 起 CancelledError | 改为 BaseException 子类 | except Exception 抓不到，必须 finally 或显式捕获 |
| task.cancel() | 在下一 await 点 throw CancelledError | 非强杀；清理放 finally，敏感段用 shield |
| asyncio.wait_for | 超时取消内层并抛 TimeoutError | 3.11 起 asyncio.TimeoutError 即内置 TimeoutError |
| 3.11 TaskGroup (PEP 654) | 失败取消兄弟并抛 ExceptionGroup | 用 except* 按类型拆组处理 |
| 3.11 Task.uncancel() | 撤销取消计数 | 结构化并发里恢复被屏蔽的任务 |
| 裸 create_task 无强引用 | 事件循环只弱引用 Task | 用 set 或 TaskGroup 持有引用 |

<FlowTimeline :steps='[{"title": "Task 是调度单位，Future 是结果占位符", "desc": "`asyncio.Future` 表示一个「还没填值的结果」，状态由…", "tone": "blue"}, {"title": "取消是协作式的：在下一个 await 点抛 Ca…", "desc": "`task.cancel()` 并不中断线程，只是把 `Task` 标成「待取消」…", "tone": "purple"}, {"title": "结构化并发：TaskGroup 与异常组", "desc": "`asyncio.gather(*aws)` 并发收集结果，默认…", "tone": "orange"}, {"title": "工程落地", "desc": "可观测的任务生命周期：命名、取消与清理确认", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 结构化并发：TaskGroup 与异常组

`asyncio.gather(*aws)` 并发收集结果，默认 `return_exceptions=False`：某个 awaitable 抛异常时立即把异常抛给调用方，但不会自动取消其它兄弟任务，它们仍在后台跑；`return_exceptions=True` 则把异常当普通结果返回。

3.11 的 `asyncio.TaskGroup`（配合 PEP 654 的异常组）提供结构化并发：把它作为异步上下文管理器，块内用 `tg.create_task(coro)` 建任务，任意子任务失败时组内其余任务被取消，退出时统一抛 `ExceptionGroup`（含 BaseException 时为 `BaseExceptionGroup`），必须用 except* 按类型拆组处理。

实测单个 ValueError 会包装成含 1 个异常的 `ExceptionGroup`，已完成的任务 `done()` 为 True、失败任务 `cancelled()` 为 False（它是异常结束而非被取消）。这保证离开这个上下文时所有子任务都已收尾，不会出现「异常已上报、后台任务还在写库」的竞态。

`asyncio.timeout` 与 `TaskGroup` 组合还能同时约束时间与生命周期。

**gather 与 TaskGroup 对照**

| 维度 | asyncio.gather | asyncio.TaskGroup (3.11+) |
| --- | --- | --- |
| 某子任务失败 | 立即抛给调用方，兄弟不自动取消 | 取消其余子任务，退出时抛 ExceptionGroup |
| 异常捕获 | return_exceptions=True 收进结果 | except* 按异常类型拆组 |
| 任务引用 | 需调用方自行保存 | 组内统一管理，退出即全部收尾 |
| 结果获取 | 按传入顺序返回结果列表 | 读各 Task 的 result() |
| 适用场景 | 需要按序拿全部结果 | 要求失败即整体收敛的结构化并发 |


## 可观测的任务生命周期：命名、取消与清理确认

批量任务最怕两种静默失败：任务被 GC 中途蒸发，或取消时锁没释放、临时文件没删。

可靠的封装要把三件事做实：用 `create_task(name=...)` 给每个 `Task` 命名以便日志定位、把清理逻辑放进 `finally` 保证取消也执行、用 `return_exceptions=True` 的 `asyncio.gather` 一次性收集所有结果类型，确认没有任务悬空。

下面片段起三个带名字的任务，启动后立刻全部取消，打印结果类型、清理日志条数与任务名，用来验证「取消发生在 `await` 点、`finally` 一定执行、任务全部收尾」这三条契约。真实系统还会加超时与指标上报。

```python
import asyncio

async def job(i, log):
    try:
        await asyncio.sleep(10)
        return i
    except asyncio.CancelledError:
        log.append(('cancelled', i))
        raise
    finally:
        log.append(('finally', i))

async def main():
    log = []
    loop = asyncio.get_running_loop()
    tasks = [loop.create_task(job(i, log), name='job-' + str(i)) for i in range(3)]
    await asyncio.sleep(0)
    for t in tasks:
        t.cancel()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print('result kinds', [type(r).__name__ for r in results])
    print('cleanup count', len(log))
    print('names', [t.get_name() for t in tasks])

if __name__ == '__main__':
    asyncio.run(main())
```

<Callout type="idea" title='落地提示' text='用 TaskGroup 做结构化并发，设置超时与失败策略，并显式处理屏蔽取消的清理段' />

<CheckList id='P069a' title='上线前自检' :items='["能复现并解释「裸 asyncio.create_task(...) 不保存…」", "能复现并解释「用 except Exception 兜住取消并做清理」", "能复现并解释「以为 gather 里一个任务抛异常其它会自动停」", "能用一条命令验证 loop 与策略", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 裸 asyncio.create_task(...) 不保存引用 | 事件循环只弱引用 Task，任务可能执行途中被 GC 回收，异常也无人读取 | 用模块级 set 保存强引用并在 done 回调里 discard，或改用 TaskGroup 托管 |
| 用 except Exception 兜住取消并做清理 | 3.8 起 CancelledError 继承 BaseException，except Exception 捕获不到，清理不执行 | 清理放 finally；需要感知时用 except asyncio.CancelledError 接住后重新 raise |
| 以为 gather 里一个任务抛异常其它会自动停 | gather 默认把异常立即抛给调用方，但不取消兄弟任务，后台任务继续写库 | 要求失败即整体收敛时改用 TaskGroup；或 gather(return_exceptions=True) 显式收集后再处理结果 |

<Callout type="warn" title='本讲最容易踩的坑' text='裸 asyncio.create_task(...) 不保存引用：事件循环只弱引用 Task，任务可能执行途中被 GC 回收，异常也无人读取' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：裸 asyncio.create_task…", "body": "事件循环只弱引用 Task，任务可能执行途中被 GC 回收，异常也无人读取", "tip": "用模块级 set 保存强引用并在 done 回调里 discard，或改用 TaskGroup 托管"}, {"title": "第 2 步：用 except Exception 兜住取…", "body": "3.8 起 CancelledError 继承 BaseException，except Exception 捕获不到，清理不执行", "tip": "清理放 finally；需要感知时用 except asyncio.CancelledError 接住后重新 raise"}, {"title": "第 3 步：以为 gather 里一个任务抛异常其它会自…", "body": "gather 默认把异常立即抛给调用方，但不取消兄弟任务，后台任务继续写库", "tip": "要求失败即整体收敛时改用 TaskGroup；或 gather(return_exceptions=True) 显式收集后再处理结果"}]' />


## Task.__step 的恢复点与 _fut_waiter 挂起链

Task 的恢复点在 CPython 里有两套实现：纯 Python 回退在 `Lib/asyncio/tasks.py` 的 `Task.__step`，默认启用的是扩展模块 `Modules/_asynciomodule.c` 里的 `task_step_impl`（`import asyncio` 时若 `_asyncio` 可用，Python 版 `Task` 会被 C 版替换）。

两者字段一致：`_coro` 是被驱动的协程，`_fut_waiter` 指向当前 await 挂起所等的 Future，`_must_cancel` 是取消请求标志，`_context` 是 `contextvars.Context` 的快照。

`__step` 里执行 `coro.send(None)`；若协程 yield 出一个未完成的 Future，`Task` 把它写进 `_fut_waiter` 并给它挂 `add_done_callback(self.__wakeup)`，随后自己退出、不再进入就绪队列，这就是挂起的全部含义。

`__wakeup` 被回调时先读一次 `fut.result()`（连异常一并取走，避免日志刷出 Future exception was never retrieved），清空 `_fut_waiter`，再用 `loop.call_soon(self.__step)` 把任务重新排入 `_ready`。

于是一次 await 至少跨越两次事件循环迭代：`__step` 发 send、协程 yield Future、`__wakeup` 取结果、`call_soon` 再排 `__step`。

`asyncio.sleep(0)` 内部的 `__sleep0` 是 `yield None` 的特例，`Task` 直接重新入队、不经过 `_fut_waiter`，少一次 Future 分配。

`create_task` 本身也只是 `call_soon` 排入首跳 `__step`，所以「创建即运行」从来不成立。这条源码链把正文的 Task 状态机落到具体函数与字段上。

```python
import collections

class MiniFuture:
    def __init__(self, loop):
        self.loop = loop
        self._done = False
        self._result = None
        self._callbacks = []
    def done(self):
        return self._done
    def set_result(self, v):
        self._done = True
        self._result = v
        for cb in self._callbacks:
            self.loop.ready.append((cb, self))
        self._callbacks.clear()
    def add_done_callback(self, cb):
        if self._done:
            self.loop.ready.append((cb, self))
        else:
            self._callbacks.append(cb)
    def result(self):
        return self._result
    def __await__(self):
        if not self._done:
            yield self
        return self._result
        yield

class MiniLoop:
    def __init__(self):
        self.ready = collections.deque()
        self.log = []
    def call_soon(self, cb, arg=None):
        self.ready.append((cb, arg))
    def create_future(self):
        return MiniFuture(self)
    def run(self):
        while self.ready:
            cb, arg = self.ready.popleft()
            cb(arg)

class CancelledError(BaseException):
    pass

def step(task):
    loop = task.loop
    try:
        if task.must_cancel:
            task.must_cancel = False
            yielded = task.coro.throw(CancelledError)
        else:
            yielded = task.coro.send(None)
    except StopIteration as e:
        task.done = True
        task.result = e.value
        return
    if yielded is None:
        loop.call_soon(step, task)
        loop.log.append('yield None -> call_soon')
    else:
        task.fut_waiter = yielded
        yielded.add_done_callback(lambda f: wakeup(task, f))
        loop.log.append('yield Future -> wait __wakeup')

def wakeup(task, fut):
    task.fut_waiter = None
    task.loop.log.append('__wakeup: result ' + str(fut.result()))
    task.loop.call_soon(step, task)

class MiniTask:
    def __init__(self, coro, loop):
        self.coro = coro
        self.loop = loop
        self.fut_waiter = None
        self.must_cancel = False
        self.done = False
        self.result = None
        loop.call_soon(step, self)

async def worker(loop):
    loop.log.append('worker step 1')
    f = loop.create_future()
    loop.call_soon(lambda _: f.set_result(42))
    v = await f
    loop.log.append('worker step 2 got ' + str(v))
    return v * 2

loop = MiniLoop()
t = MiniTask(worker(loop), loop)
loop.run()
print('task result', t.result)
for line in loop.log:
    print(line)

```

<OutputBox title='扩展示例运行结果' output='task result 84\nworker step 1\nyield Future -&gt; wait __wakeup\n__wakeup: result 42\nworker step 2 got 42' />

<LineByLine code='import collections\n\nclass MiniFuture:\n    def __init__(self, loop):\n        self.loop = loop\n        self._done = False\n        self._result = None\n        self._callbacks = []\n    def done(self):\n        return self._done\n    def set_result(self, v):\n        self._done = True\n        self._result = v\n        for cb in self._callbacks:\n            self.loop.ready.append((cb, self))\n        self._callbacks.clear()\n    def add_done_callback(self, cb):\n        if self._done:\n            self.loop.ready.append((cb, self))\n        else:\n            self._callbacks.append(cb)\n    def result(self):\n        return self._result\n    def __await__(self):\n        if not self._done:\n            yield self\n        return self._result\n        yield\n\nclass MiniLoop:\n    def __init__(self):\n        self.ready = collections.deque()\n        self.log = []\n    def call_soon(self, cb, arg=None):\n        self.ready.append((cb, arg))\n    def create_future(self):\n        return MiniFuture(self)\n    def run(self):\n        while self.ready:\n            cb, arg = self.ready.popleft()\n            cb(arg)\n\nclass CancelledError(BaseException):\n    pass\n\ndef step(task):\n    loop = task.loop\n    try:\n        if task.must_cancel:\n            task.must_cancel = False\n            yielded = task.coro.throw(CancelledError)\n        else:\n            yielded = task.coro.send(None)\n    except StopIteration as e:\n        task.done = True\n        task.result = e.value\n        return\n    if yielded is None:\n        loop.call_soon(step, task)\n        loop.log.append(&#39;yield None -&gt; call_soon&#39;)\n    else:\n        task.fut_waiter = yielded\n        yielded.add_done_callback(lambda f: wakeup(task, f))\n        loop.log.append(&#39;yield Future -&gt; wait __wakeup&#39;)\n\ndef wakeup(task, fut):\n    task.fut_waiter = None\n    task.loop.log.append(&#39;__wakeup: result &#39; + str(fut.result()))\n    task.loop.call_soon(step, task)\n\nclass MiniTask:\n    def __init__(self, coro, loop):\n        self.coro = coro\n        self.loop = loop\n        self.fut_waiter = None\n        self.must_cancel = False\n        self.done = False\n        self.result = None\n        loop.call_soon(step, self)\n\nasync def worker(loop):\n    loop.log.append(&#39;worker step 1&#39;)\n    f = loop.create_future()\n    loop.call_soon(lambda _: f.set_result(42))\n    v = await f\n    loop.log.append(&#39;worker step 2 got &#39; + str(v))\n    return v * 2\n\nloop = MiniLoop()\nt = MiniTask(worker(loop), loop)\nloop.run()\nprint(&#39;task result&#39;, t.result)\nfor line in loop.log:\n    print(line)\n' :notes='["导入 collections，用 deque 充当事件循环的就绪队列", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 MiniFuture，模拟 lib/asyncio 的 Future，只保留 done 与回调表", "构造时收下所属的 loop", "保存 loop 引用", "_done 初始为 False", "_result 初始为 None", "_callbacks 收集完成时要触发的回调", "done 返回是否已完成", "读回 _done", "set_result 填入结果", "标记完成", "保存结果值", "遍历已登记的回调", "把回调挂进 loop.ready，等价于 add_done_callback 经 call_soon 调度", "清空回调表，避免重复触发", "add_done_callback 登记一个回调", "若已完成", "立即把回调排进就绪队列", "否则尚未完成", "暂存进回调表等待 set_result", "result 返回结果", "读回 _result", "__await__ 让 Future 可被 await", "若未完成", "yield 出自身，把暂停点交给调度器", "恢复后返回结果", "补一条 yield，保证 __await__ 是生成器", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 MiniLoop，模拟事件循环", "构造就绪队列与日志", "ready 是 FIFO deque", "log 记录执行轨迹", "call_soon 安排回调", "只是 append 一个 (回调, 参数) 元组", "create_future 造一个 Future", "绑定当前 loop", "run 消费就绪队列", "队列非空就一直循环", "从队首取出回调与参数", "执行回调，对应 _run_once 的 Handle 消费", "空行，只用于分隔逻辑块，不影响执行结果。", "自定义 CancelledError 继承 BaseException，复刻 3.8 起的层级", "空实现，只借继承关系", "空行，只用于分隔逻辑块，不影响执行结果。", "step 对应 Task.__step", "取出所属 loop", "try 包裹 send 与 throw", "若有取消请求", "清掉取消标志", "用 throw 注入 CancelledError", "否则正常推进", "send(None) 驱动协程到下一个暂停点", "协程以 StopIteration 结束", "标记完成", "以 StopIteration.value 落地为 Task 的结果", "结束本次 step", "若 yield 出的是 None", "sleep(0) 捷径，直接重新入队", "记录这次重新入队", "若 yield 出的是未完成 Future", "把它记进 _fut_waiter", "给它挂上 __wakeup 回调", "记录进入挂起链", "空行，只用于分隔逻辑块，不影响执行结果。", "wakeup 是 Future 完成后的回调", "清空 _fut_waiter", "先 result() 取回值并记日志，避免异常未取", "再 call_soon 排下一次 step", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 MiniTask，模拟 Task", "构造时收协程与 loop", "保存协程", "保存 loop", "_fut_waiter 初始为空", "must_cancel 初始为 False", "done 初始为 False", "result 初始为 None", "构造只 call_soon 排首跳，创建时不执行函数体", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 worker 协程", "记录第一步", "造一个 Future", "排一个回调稍后给 Future 设结果 42", "await f 制造一次真实的 Future 挂起", "恢复后记录取到的值", "返回 v 乘 2 作为协程结果", "空行，只用于分隔逻辑块，不影响执行结果。", "造事件循环实例", "用 worker 协程构造 MiniTask", "启动事件循环", "打印任务最终结果", "遍历执行日志", "逐行打印，验证一次 await 跨两次事件循环迭代", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />


### cancelling 与 uncancel 的取消计数协议

3.11 起取消不再是单个布尔位。

`Task.cancel(msg=None)` 除把 `_must_cancel` 置真外，还把 `_num_cancels_requested` 加一；`cancelling()` 返回这个计数，`uncancel()` 减一。

它解决的是正文没展开的问题：timeout 与 `TaskGroup` 需要区分「被取消了几次」与「是否已经补偿」。

`asyncio.timeout` 的 `__aexit__` 在超时分支里调用 `self._task.uncancel()`，只有计数归零且捕获到 `CancelledError` 时才把异常换成 `TimeoutError`；若协程里接住 `CancelledError`、调了 `uncancel()` 却不重抛，await 会正常返回，`__aexit__` 看到的 exc_type 为 None，超时被静默吞掉，这是升级到 3.11 之后新出现的一类故障。

shield 的实现（同样在 `Lib/asyncio/tasks.py`）也靠这套协议：它给外层 Future 挂 `_outer_done_callback`，外层被取消时只把外层标成 `CANCELLED`、内层继续跑，内层异常由 `_inner_done_callback` 消费，既屏蔽取消又不丢错误。

架构上计数协议把取消从一次性命令变成可协商的状态机，代价是每个 `Task` 多一个整数字段与三条 API，且任何自定义取消逻辑都要显式处理 `uncancel` 的配对，否则超时判定就会失真。

**Task 内部字段与 CPython 源码位置**

| 字段 / 回调 | 定义位置 | 在调度中的作用 |
| --- | --- | --- |
| _coro | Lib/asyncio/tasks.py / Modules/_asynciomodule.c | 被 send 或 throw 驱动的目标协程 |
| _fut_waiter | task_step_impl | 记录挂起所等的 Future，非空即不在就绪队列 |
| _must_cancel | Task.cancel | 下一次 __step 改 throw 而非 send |
| _num_cancels_requested | 3.11+ Task.cancelling | 取消计数，供 uncancel 与 timeout 协商 |
| __wakeup | Task 私有方法 | 取回 Future 结果并 call_soon 重新入队 |
| _context | contextvars.Context | 每次 __step 前恢复任务上下文快照 |

一次超时治理事故里，网关把下游调用包在 `asyncio.timeout(0.2)` 内，发版后监控发现超时计数归零、P99 却涨到秒级。

复盘定位到公共重试装饰器接住了 `CancelledError`，调 `task.uncancel()` 后直接 return 一个降级值、没有重抛：timeout 的 `__aexit__` 既没收到 `CancelledError`、计数又被减回零，于是判定为正常完成，超时彻底失效。

下面的实验把两次 cancel 叠加与一次 uncancel 的计数变化打印出来，能看到「接住时计数为 2、uncancel 后为 1、await 依旧抛 `CancelledError`」，说明只要不重抛、计数不为零，取消协议就还在；真正吞掉超时的是「减到零且不抛」这个组合。

修复是把降级逻辑移出 `CancelledError` 分支，只在 `TimeoutError` 里做兜底，并禁止库代码私自调用 `uncancel`。

```python
import asyncio

async def job():
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        t = asyncio.current_task()
        print('job catch, cancelling =', t.cancelling())
        t.uncancel()
        print('job after uncancel =', t.cancelling())
        raise

async def main():
    t = asyncio.create_task(job(), name='job')
    await asyncio.sleep(0)
    t.cancel('first')
    t.cancel('second')
    print('queued cancels', t.cancelling())
    try:
        await t
    except asyncio.CancelledError:
        print('await raised, cancelling =', t.cancelling())

asyncio.run(main())

```


## 就绪队列与定时器堆的调度成本

<Quiz no='069-1' q='关于 3.11 的 Task.cancelling() 与 uncancel()，下面哪项准确？' :options='["cancelling() 返回累计取消请求数，uncancel() 减一，timeout 靠计数是否归零判断是否转换 TimeoutError", "cancelling() 返回任务已运行秒数，uncancel() 会重启协程", "uncancel() 会撤销所有已排队的 call_soon 回调", "CancelledError 在 3.11 被改回 Exception 子类，故 except Exception 能接住"]' answer="0" explain='3.11 的取消计数让 timeout 与 TaskGroup 能协商：__aexit__ 调 uncancel() 后只有计数归零且捕获到 CancelledError 才把它转成 TimeoutError；接住取消却减到零且不重抛会静默吞掉超时。CancelledError 自 3.8 起仍是 BaseException 子类，与 3.11 新增的计数无关，不能混为一谈。' />

<Exercise title='观测就绪队列与两次迭代的 await 往返' task='用 loop._ready 的长度在 call_soon 前后打点，说明一次 await Future 为何至少两次 _run_once，再对比 asyncio.sleep(0) 的 yield None 捷径。' solution='import asyncio\n\nasync def main():\n    loop = asyncio.get_running_loop()\n    fut = loop.create_future()\n    loop.call_soon(lambda: fut.set_result(&#39;ok&#39;))\n    print(&#39;ready before await&#39;, len(loop._ready))\n    await fut\n    print(&#39;after await result&#39;, fut.result())\n\nasyncio.run(main())\n' explain='await 一个未完成 Future 时 Task 把 __step 挂到 __wakeup，__wakeup 再 call_soon 重新排入 _ready，所以至少两次 _run_once 才恢复；sleep(0) 走 yield None 的捷径，Task 直接重新入队，只多一次迭代。_ready 是 collections.deque，call_soon 是 O(1) 的 append、消费是 popleft，而 _scheduled 是按到期时间组织的小根堆，插入 O(log n)。' />


### __wakeup 回调与首跳到恢复的调度时序

<Term word='Task.__wakeup' text='Task 挂起所等的 Future 落定时被 add_done_callback 触发的私有回调：它先取回结果或异常以免日志报出未读取的异常，清空 _fut_waiter，再用 loop.call_soon(__step) 把任务重新排进就绪队列。它是 await 能恢复的唯一入口，也是「一次 await 至少两轮事件循环」的来源。' />

<ConceptDiagram type='flow4' title='第 069 讲 · 扩展图解' labels='send(None) 首跳|yield Future 挂起|__wakeup 取结果|call_soon 重新入队' caption='一次 await 在事件循环里的四拍：至少两次 _run_once 才能从 yield 走到恢复；sleep(0) 用 yield None 跳过中间两拍。' />


## 练习、自测与一页纸速记

<Exercise title='基础：观察 Future 的状态机' task='在协程里用 loop.create_future() 建 Future，打印初始 done/cancelled，set_result 后再打印 done 与 await 取回的值。' solution='import asyncio\nasync def main():\n    f = asyncio.get_running_loop().create_future()\n    print(&#39;pending&#39;, f.done(), f.cancelled())\n    f.set_result(&#39;ok&#39;)\n    print(&#39;done&#39;, f.done(), await f)\nasyncio.run(main())' explain='Future 初始 PENDING，done 与 cancelled 都 False；set_result 推进到 FINISHED，await 已完成的 Future 立即返回，不会挂起事件循环。' />

<Exercise title='进阶：用 TaskGroup 验证失败收敛' task='在 TaskGroup 里建一个正常任务与一个抛 ValueError 的任务，用 except* ValueError 捕获异常组并打印异常数，再确认正常任务 done() 为 True。' solution='import asyncio\nasync def main():\n    async def ok(i):\n        await asyncio.sleep(0)\n        return i\n    async def bad():\n        await asyncio.sleep(0)\n        raise ValueError(&#39;x&#39;)\n    try:\n        async with asyncio.TaskGroup() as tg:\n            a = tg.create_task(ok(1))\n            tg.create_task(bad())\n    except* ValueError as eg:\n        print(&#39;caught&#39;, len(eg.exceptions))\n    print(&#39;a done&#39;, a.done())\nasyncio.run(main())' explain='TaskGroup 把单个 ValueError 也包装成 ExceptionGroup，except* 按类型拆组；退出时所有子任务已收尾，正常任务 done() 为 True。' />

<Quiz no='069-2' q='关于 asyncio.CancelledError，下面哪项准确？' :options='["3.8 起继承 BaseException，except Exception 捕获不到，清理应放 finally", "继承 Exception，except Exception 能接住", "是 RuntimeError 的别名", "只在多进程里抛出"]' answer="0" explain='3.8 起 CancelledError → BaseException → object，普通 except Exception 会漏掉它；清理逻辑必须放 finally 或显式 except asyncio.CancelledError 后重抛。' />

<Quiz no='069-3' q='task.cancel() 之后任务会怎样？' :options='["在下一个 await 点被抛入 CancelledError，属于协作式取消", "操作系统立即强杀该线程", "任务被立即从内存删除且无任何回调", "把 Future 标成 FINISHED 并返回 None"]' answer="0" explain='cancel 只设置取消请求，下一次 Task.__step 在 await 点 throw CancelledError；finally 仍会执行，await 该 Task 的调用方也会收到 CancelledError。' />

<Quiz no='069-4' q='TaskGroup 中某子任务抛 ValueError 时，会？' :options='["取消其余子任务并在退出时抛 ExceptionGroup，用 except* 处理", "立刻把 ValueError 原样抛给调用方，兄弟任务继续跑", "静默忽略该异常", "自动重试该任务三次"]' answer="0" explain='PEP 654 的结构化并发保证组内任务一起收敛：失败触发兄弟取消，退出时统一抛 ExceptionGroup（含 BaseException 时为 BaseExceptionGroup），必须用 except* 拆分处理。' />

<Predict no='069-5' q='对 PENDING 的 Future 调 done() 与 cancelled()，输出是？' :options='["False False", "True False", "False True"]' answer='0' output='False False' explain='Future 初始为 PENDING：既没结束（done 为 False）也不是被取消（cancelled 为 False）。只有 set_result / set_exception / cancel 落定后这两个布尔值才会变化。' />

<FillBlank no='069-6' tpl='import  ___ io' :answers='["async"]' hint='回想本讲关于 loop 与策略 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Task 是调度单位，Future 是结果占位符 的落点。' />

<KnowledgeCard :points='["Task 是 Future 子类：Future 占位结果（done/cancelled/result/exception），Task 额外驱动协程", "loop.create_future() 是标准创建方式；create_task 需 running loop，且调用方必须保存强引用", "CancelledError 自 3.8 起继承 BaseException，清理放 finally；cancel 只在下一 await 点注入异常", "loop.call_soon 走 FIFO 就绪队列，call_later 返回 TimerHandle，cancel() 返回 None、读状态用 cancelled()", "gather 默认不取消兄弟任务；3.11 TaskGroup 失败即取消全组并抛 ExceptionGroup，用 except* 处理", "3.11 起 asyncio.TimeoutError 等于内置 TimeoutError，asyncio.timeout 与 Task.uncancel() 配套结构化并发"]' :pitfalls='["裸 asyncio.create_task(...) 不保存引用", "用 except Exception 兜住取消并做清理", "以为 gather 里一个任务抛异常其它会自动停", "用裸 create_task 不保存引用，任务可能被 GC 回收，异常也永远没人读取"]' summary='Task 是协程的调度单位，取消是「在下一个 await 点抛 CancelledError」而非强杀，所以清理逻辑必须写在 finally' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| Task 是 Future 子类：Future 占位结果（done/cancelled/result/exception），Task 额外驱动协程 | 建立直觉 |
| loop.create_future() 是标准创建方式；create_task 需 running loop，且调用方必须保存强引用 | 跑通示例 |
| CancelledError 自 3.8 起继承 BaseException，清理放 finally；cancel 只在下一 await 点注入异常 | 深入边界 |
| loop.call_soon 走 FIFO 就绪队列，call_later 返回 TimerHandle，cancel() 返回 None、读状态用 cancelled() | 工程落地 |
| gather 默认不取消兄弟任务；3.11 TaskGroup 失败即取消全组并抛 ExceptionGroup，用 except* 处理 | 随堂检测 |
| 3.11 起 asyncio.TimeoutError 等于内置 TimeoutError，asyncio.timeout 与 Task.uncancel() 配套结构化并发 | 复盘 |

1. Task 是 Future 子类：Future 占位结果（done/cancelled/result/exception），Task 额外驱动协程

2. loop.create_future() 是标准创建方式；create_task 需 running loop，且调用方必须保存强引用

3. CancelledError 自 3.8 起继承 BaseException，清理放 finally；cancel 只在下一 await 点注入异常

[下一讲：阶段综合：并发爬虫四级演进](/concurrency/capstone)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/069-asyncio.py`

```bash
python3 examples/lessons/069-asyncio.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/069-asyncio.py) · [全部示例代码索引](/examples/)
