---
title: 第 068 讲 · async / await 与协程对象
description: 正确创建并驱动协程
---

<StageHeader stage='L6 · 并发与异步' level='★★★☆☆' time='35 分钟' goal='正确创建并驱动协程' prereq='第 067 讲 · 生成器协程：send、yield from 与调度器' />

# 第 068 讲 · async / await 与协程对象

上一讲顺着生成器把 async/await 的来历推了出来：暂停点加上外部驱动，就是协程的原型。现在轮到把语法接到手上——写好一个 async 函数，怎么让它真跑起来，又不把整条执行流堵住。一个常见的画面：把三个串行接口改成并发，日志里既没请求也没报错，结果却一直拿不到，像调用悄悄落了空。

由近及远：先看调用 async 函数拿到的只是协程对象，再认 `await` 与 awaitable 协议怎样推动它，接着交代 `asyncio.run` 这条入口与同步异步的边界，最后把阻塞调用挪进线程。带着生成器、`yield` 与事件循环的印象来；读完能正确创建并驱动协程，也说得出一个慢请求为什么拖住所有并发任务。


## 一个「没有请求、也没有报错」的并发改造

线上有个接口改造：把 3 个串行 `HTTP` 调用改成并发，工程师写下 `result = fetch_user(1)` 就把返回值拿去解析，日志里既没有请求也没有报错，偶尔只冒出一句 RuntimeWarning: coroutine 'fetch_user' was never awaited。

根因是 async def 定义的函数被调用时只返回一个 coroutine 对象，函数体一行都不会执行；只有 `await` 或交给事件循环调度才真正驱动它。拿多线程那套「调用即执行」的直觉去套协程必然落空。

更隐蔽的是把 `time.sleep(2)`、同步 `requests.get` 写进 async 函数：它们不释放事件循环，一个慢请求会把同一 loop 上所有并发任务一起拖住，反而比串行更慢。本讲把协程对象、awaitable 协议与 `asyncio.run` 的边界讲清楚，并给出把阻塞调用安全下沉到线程的标准写法。

<Callout type="warn" title='先看一个真实会出错的写法' text='调用 async 函数直接把返回值当结果用：调用只创建 coroutine 对象、函数体不执行，还会触发 RuntimeWarning: coroutine was never awaited' />


## 调用 async 函数只返回协程对象，函数体一行不执行

包含 async def 的函数在编译期被打上 `CO_COROUTINE` 标志（值为 128），调用它并不执行函数体，只返回一个 `types.CoroutineType` 实例。

`inspect.iscoroutinefunction(f)` 看函数、`inspect.iscoroutine(obj)` 看调用结果、`inspect.isawaitable(obj)` 看能否被 `await`，三者判定层级不同。

协程对象要靠外部驱动：首次 `coro.send(None)` 或 `await` 才推进到第一个 await 点；

若创建后既不 `await` 也不 close，对象被回收时 CPython 会打印 RuntimeWarning: coroutine 'f' was never awaited，这是「调用了却什么都没发生」最常见的现场证据，显式丢弃应调 `coro.close()`。

`await` 只能出现在 async def 内部，写在模块顶层或普通 def 里会在编译期报 SyntaxError: 'await' outside function。

统一入口是 `asyncio.run(coro)`（3.7 起）：它新建一个事件循环、把协程包装成 `Task` 跑到完成、取消残留任务、关闭异步生成器并关掉 loop；

同一线程已有运行中的 loop 时再调用会抛 `RuntimeError`（提示 cannot be called from a running event loop），所以库代码只应暴露 async 函数，把 run 留给最外层入口调用一次。

<Callout type="tip" title='核心心智模型' text='包含 async def 的函数在编译期被打上 `CO_COROUTINE` 标志（值为 128），调用它并不执行函数体，只返回一个 `types.CoroutineType` 实例。`inspect.iscoroutinefunction(f)` 看函数、`inspect.iscoroutine(' />

**协程标志、常量与判定 API**

| 名称 / 签名 | 值 / 返回 | 语义 |
| --- | --- | --- |
| inspect.CO_COROUTINE | 128 | async def 原生协程的编译标志 |
| CO_ITERABLE_COROUTINE | 256 | types.coroutine 标记的生成器协程 |
| CO_ASYNC_GENERATOR | 512 | async def 内含 yield 的异步生成器 |
| inspect.iscoroutinefunction(f) | bool | 判定函数是否为协程函数 |
| inspect.isawaitable(o) | bool | 判定对象能否被 await |
| asyncio.run(coro) | 3.7+ 入口 | 建新 loop、跑完、取消残留、关闭 |
| asyncio.create_task(coro, name=None) | 3.7+ | 需运行中的 loop，返回 Task |
| asyncio.to_thread(fn, *args) | 3.9+ | 把阻塞调用下沉到默认线程池 |


## awaitable 协议：三类可等待对象与暂停点

`await` 的操作数必须满足 awaitable 协议，共三类：原生协程（`CO_COROUTINE`）、用 `types.coroutine` 装饰、带 `CO_ITERABLE_COROUTINE`（256）的生成器协程、以及任意实现了 `__await__` 且返回迭代器的对象，`inspect.isawaitable` 对三者都返回 True。

`__await__` 生成器里 yield 出去的值会沿 `yield from` 链路交到事件循环：`asyncio.sleep(0)` 内部就是一个产出 None 的 `__sleep0`，`Task` 收到 None 便用 `loop.call_soon` 安排下一次 `send(None)` 恢复；

yield 出一个未完成的 `Future` 时，`Task` 给它挂 `add_done_callback` 等待就绪。

对非 awaitable 调用 `await` 会抛 TypeError: object int can't be used in 'await' expression。

3.6 起 `CO_ASYNC_GENERATOR`（512，PEP 525）标记 async def 里含 `yield` 的异步生成器，需配合 async for / `__aiter__` / `__anext__`；

async with 则从 3.5 的 PEP 492 起就依赖 `__aenter__` / `__aexit__`。

这套协议把暂停点标准化了：`asyncio.gather`、`asyncio.create_task`、`asyncio.ensure_future` 都先检查或包装成 awaitable 再交给 loop 调度。

```python
import asyncio
import inspect

async def work(name, n):
    total = 0
    for i in range(n):
        total += i
    await asyncio.sleep(0)
    return name + ':' + str(total)

async def main():
    a = asyncio.create_task(work('A', 5))
    b = asyncio.create_task(work('B', 10))
    results = await asyncio.gather(a, b)
    for r in results:
        print(r)

coro = main()
print('is coroutine function', inspect.iscoroutinefunction(main))
print('calling returns', type(coro).__name__, inspect.iscoroutine(coro))
asyncio.run(coro)
```

<OutputBox title='主示例运行结果' output='is coroutine function True\ncalling returns coroutine True\nA:10\nB:45' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import asyncio\nimport inspect\n\nasync def work(name, n):\n    total = 0\n    for i in range(n):\n        total += i\n    await asyncio.sleep(0)\n    return name + &#39;:&#39; + str(total)\n\nasync def main():\n    a = asyncio.create_task(work(&#39;A&#39;, 5))\n    b = asyncio.create_task(work(&#39;B&#39;, 10))\n    results = await asyncio.gather(a, b)\n    for r in results:\n        print(r)\n\ncoro = main()\nprint(&#39;is coroutine function&#39;, inspect.iscoroutinefunction(main))\nprint(&#39;calling returns&#39;, type(coro).__name__, inspect.iscoroutine(coro))\nasyncio.run(coro)' :notes='["导入 asyncio 提供事件循环、任务与 gather", "导入 inspect 用于判定协程函数与协程对象", "定义原生协程 work，调用它只返回协程对象", "累加器初值为 0", "用 range 控制循环次数，结果可精确预测", "纯 Python 累加，不涉及阻塞 IO", "await asyncio.sleep(0) 显式让出事件循环", "把 name 与累加结果拼成字符串返回", "定义入口协程 main，负责创建并收集任务", "create_task 把 work(&#39;A&#39;,5) 包装成 Task 并调度", "create_task 把 work(&#39;B&#39;,10) 包装成第二个 Task", "gather 并发等待两个 Task，按传入顺序收集结果", "遍历结果列表", "逐个打印 A 与 B 的返回值", "调用 main() 只得到协程对象，函数体尚未执行", "iscoroutinefunction 对 async def 返回 True", "type 为 coroutine、iscoroutine 为 True，证明未执行", "asyncio.run 是唯一入口：建 loop、跑协程、收尾关闭"]' title='第 068 讲 · async / await 与协程对象' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Term word='coroutine 与 async function' text='包含 async def 的函数在编译期被打上 `CO_COROUTINE` 标志（值为 128），调用它并不执行函数体，只返回一个 `types.CoroutineType` 实例。`inspect.iscoroutinefunction(f)` 看函数、`inspect.iscoroutine(obj)` 看调用结' />

<Term word='await 只能用在 async 内' text='`await` 的操作数必须满足 awaitable 协议，共三类：原生协程（`CO_COROUTINE`）、用 `types.coroutine` 装饰、带 `CO_ITERABLE_COROUTINE`（256）的生成器协程、以及任意实现了 `__await__` 且返回迭代器的对象，`inspect.isawai' />


### __await__ 里 yield 出去的值交回给了谁

```python
import inspect, dis

async def compute(x):
    await step()
    return x * 2

opnames = [i.opname for i in dis.get_instructions(compute)]
print('CO_COROUTINE', inspect.CO_COROUTINE)
print('flag set', bool(compute.__code__.co_flags & inspect.CO_COROUTINE))
print('iscoroutinefunction', inspect.iscoroutinefunction(compute))
print('has GET_AWAITABLE', 'GET_AWAITABLE' in opnames)
print('has SEND', 'SEND' in opnames)
obj = compute(3)
print('call result', type(obj).__name__)
obj.close()
```

<OutputBox title='原理验证' output='CO_COROUTINE 128\nflag set True\niscoroutinefunction True\nhas GET_AWAITABLE True\nhas SEND True\ncall result coroutine' />


## 对照：await 一个 int 与顶层写 await

```python
import asyncio, inspect
class Pause:
    def __await__(self):
        yield
        return 'resumed'
async def main():
    p = Pause()
    print('isawaitable', inspect.isawaitable(p))
    value = await p
    print('await returned', value)
asyncio.run(main())
```

<OutputBox title='对照写法：先自己猜，再点开' output='isawaitable True\nawait returned resumed' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import asyncio\nimport inspect\n\nasync def work(name, n):\n    total = 0\n    for i in range(n):\n        total += i\n    await asyncio.sleep(0)\n    return name + &#39;:&#39; + str(total)\n\nasync def main():\n    a = asyncio.create_task(work(&#39;A&#39;, 5))\n    b = asyncio.create_task(work(&#39;B&#39;, 10))\n    results = await asyncio.gather(a, b)\n    for r in results:\n        print(r)\n\ncoro = main()\nprint(&#39;is coroutine function&#39;, inspect.iscoroutinefunction(main))\nprint(&#39;calling returns&#39;, type(coro).__name__, inspect.iscoroutine(coro))\nasyncio.run(coro)", "note": "调用 async 函数只创建协程对象，不执行函数体"}, {"label": "对照 / 进阶", "code": "import asyncio, inspect\nclass Pause:\n    def __await__(self):\n        yield\n        return &#39;resumed&#39;\nasync def main():\n    p = Pause()\n    print(&#39;isawaitable&#39;, inspect.isawaitable(p))\n    value = await p\n    print(&#39;await returned&#39;, value)\nasyncio.run(main())", "note": "awaitable 协议：三类可等待对象与暂停点"}]' title='两种写法对照' note='差异集中在 coroutine 与 async function；先看输出，再找背后的规则。' />


## 同步异步边界：别在协程里 time.sleep 或跑同步 requests

事件循环是单线程协作式调度器，一个协程不主动让出，其它任务就没有执行机会。`time.sleep`、同步 `requests.get`、阻塞的数据库驱动、甚至一个纯 Python 长循环写在 async def 里，都会占住唯一线程；

只有 `await asyncio.sleep(0)` 这类显式让出才能把控制权交回 loop。

正确做法有三类：把同步阻塞函数交给 `asyncio.to_thread`（3.9 起）或 `loop.run_in_executor` 下沉到线程池，`asyncio.to_thread` 还会继承当前 contextvars；

改用原生异步库（`aiohttp`、`httpx.AsyncClient`、`asyncpg`、`aiosqlite`）；

CPU 密集计算交给进程池或 C 扩展。

要注意 `asyncio.to_thread` 并不绕过 GIL，纯 Python 计算换成线程依旧无法并行，只有释放 GIL 的 IO 或 C 扩展才受益。

还有一个边界是任务引用：`asyncio.run` 收尾会取消所有未完成任务，而事件循环对 `Task` 只持弱引用，裸 `asyncio.create_task(...)` 不保存强引用时可能被 GC 中途回收、异常也没人读取，应当用集合或 `TaskGroup` 持有——这背后的任务生命周期与取消语义，下一讲专门展开。

**同步阻塞写法与异步替代**

| 同步写法 | 异步替代 | 留在协程里的后果 |
| --- | --- | --- |
| time.sleep(2) | await asyncio.sleep(2) | 占住唯一线程，所有任务停摆 |
| requests.get(url) | aiohttp / httpx.AsyncClient | 同步 IO 不释放事件循环 |
| sqlite3 同步查询 | aiosqlite / to_thread | 一次慢查询拖垮全部并发 |
| open() 大文件读 | to_thread(fn) 或 aiofiles | 阻塞回调队列 |
| queue.Queue.get() | asyncio.Queue.get() | 阻塞式 get 卡死 loop |
| threading.Lock | asyncio.Lock | 跨 await 持锁易死锁 |


### asyncio.run 收尾时为什么取消残留任务

**asyncio.run 边界与典型报错**

| 场景 | 结果 / 报错 |
| --- | --- |
| 顶层 asyncio.run(main()) | 正常：建 loop 跑完并关闭 |
| 已有 running loop 再 run | RuntimeError: asyncio.run() cannot be called from a running event loop |
| 模块顶层写 await f() | SyntaxError: 'await' outside function |
| 协程创建后从不 await | RuntimeWarning: coroutine 'f' was never awaited |
| create_task 不保存强引用 | 任务可能被 GC 中途回收、异常无人读取 |
| await 一个 int | TypeError: object int can't be used in 'await' expression |

<FlowTimeline :steps='[{"title": "调用 async 函数只创建协程对象，不执行函数体", "desc": "包含 async def 的函数在编译期被打上 `CO_COROUTINE` 标志（…", "tone": "blue"}, {"title": "awaitable 协议：三类可等待对象与暂停点", "desc": "`await` 的操作数必须满足 awaitable 协议，共三类：原生协程（`CO…", "tone": "purple"}, {"title": "同步异步边界：不要在协程里阻塞事件循环", "desc": "事件循环是单线程协作式调度器，一个协程不主动让出，其它任务就没有执行机会。`time…", "tone": "orange"}, {"title": "工程落地", "desc": "把同步阻塞计算安全下沉到线程池的边界封装", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## PyCoroObject 与 send 驱动协程的底层

async def 编译出的 code object 带 `CO_COROUTINE` 标志，调用时 CPython 不执行帧，而是构造 `PyCoroObject` 把帧保存在 `cr_frame` 里，指令指针停在起点。

3.11 起 await 的字节码大致是 `GET_AWAITABLE` 取操作数的 `am_await` 槽得到迭代器，再用 `LOAD_CONST` 压入 None、`SEND` 把它送进子迭代器、`YIELD_VALUE` 把值交还调用者并冻结栈帧，3.12 起开头还多一条 `RETURN_GENERATOR`；

用 `dis` 能直接看到这组指令。

真正的驱动者是事件循环里的 `Task.__step`：它调用 `coro.send(None)`，根据 yield 出来的值决定下一步——None 用 `call_soon` 重新入队、`Future` 未完成就挂回调、`Future` 完成则把结果 send 回去，这正是 PEP 492 把生成器协议固化为原生协程的机器级形态。

`asyncio.run` 借助 3.11 起的 `Runner` 管理循环生命周期，退出前跑 `_cancel_all_tasks` 与 `shutdown_asyncgens`，保证没有泄漏任务。

<ConceptDiagram type='hub4' title='第 068 讲 · 调用 async 函数只创建协程对象，不执行函数体' labels='调用 async 函数只创建协程对象，不执行|awaitable 协议：三类可等待对象与暂|同步异步边界：不要在协程里阻塞事件循环' caption='正确创建并驱动协程' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 把同步阻塞计算安全下沉到线程池的边界封装

重构老服务时，总有几段同步函数短期无法改成异步：哈希、压缩、老 SDK 的调用。把它们直接放进 async 函数会拖垮事件循环，全量改写又不现实。

折中做法是用 `asyncio.to_thread` 把每个同步调用包一层，由 `asyncio.gather` 并发驱动，并在外层统计结果类型与去重数量，确认没有任务被静默吞掉。

真实项目还会加超时、线程池容量上限与异常回传。下面片段用纯标准库模拟四类文本的哈希，重点看阻塞函数如何被封装成可 `await` 的边界、以及结果如何被统一校验，而不是把同步代码硬塞进协程。

```python
import asyncio

def blocking_hash(text, rounds):
    h = 0
    for _ in range(rounds):
        h = (h * 31 + len(text)) % 1000003
    return h

async def main():
    texts = ['alpha', 'beta', 'gamma', 'delta']
    tasks = [asyncio.to_thread(blocking_hash, t, 5000) for t in texts]
    results = await asyncio.gather(*tasks)
    print('hashed', len(results))
    print('all int', all(isinstance(r, int) for r in results))
    print('unique', len(set(results)))

if __name__ == '__main__':
    asyncio.run(main())
```

<Callout type="idea" title='落地提示' text='把阻塞调用放进 to_thread / run_in_executor，或换成原生异步库；入口统一用 asyncio.run' />

<CheckList id='P068b' title='上线前自检' :items='["能复现并解释「调用 async 函数直接把返回值当结果用」", "能复现并解释「在协程里用 time.sleep 或同步 requests.」", "能复现并解释「顶层写 await 或在已有 loop 的线程里再调 asy」", "能用一条命令验证 coroutine 与 async function", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 调用 async 函数直接把返回值当结果用 | 调用只创建 coroutine 对象、函数体不执行，还会触发 RuntimeWarning: coroutine was never awaited | 用 await、asyncio.run 或 create_task 驱动；丢弃时显式 coro.close() |
| 在协程里用 time.sleep 或同步 requests.get | 同步阻塞不释放事件循环，整个 loop 上的并发任务一起停住 | 改 await asyncio.sleep / aiohttp / httpx.AsyncClient，或 await asyncio.to_thread(fn, ...) |
| 顶层写 await 或在已有 loop 的线程里再调 asyncio.run | 前者编译期 SyntaxError: 'await' outside function，后者 RuntimeError: cannot be called from a running event loop | 库代码只暴露 async 函数，把 asyncio.run 放在最外层同步入口且只调一次 |

<Callout type="warn" title='本讲最容易踩的坑' text='调用 async 函数直接把返回值当结果用：调用只创建 coroutine 对象、函数体不执行，还会触发 RuntimeWarning: coroutine was never awaited' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：调用 async 函数直接把返回值当结果用", "body": "调用只创建 coroutine 对象、函数体不执行，还会触发 RuntimeWarning: coroutine was never awaited", "tip": "用 await、asyncio.run 或 create_task 驱动；丢弃时显式 coro.close()"}, {"title": "第 2 步：在协程里用 time.sleep 或同步 r", "body": "同步阻塞不释放事件循环，整个 loop 上的并发任务一起停住", "tip": "改 await asyncio.sleep / aiohttp / httpx.AsyncClient，或 await asyncio.to_thread(fn, ...)"}, {"title": "第 3 步：顶层写 await 或在已有 loop 的线", "body": "前者编译期 SyntaxError: &#39;await&#39; outside function，后者 RuntimeError: cannot be called from a running event loop", "tip": "库代码只暴露 async 函数，把 asyncio.run 放在最外层同步入口且只调一次"}]' />

```bash
python -c "import asyncio; print(len(asyncio.run(asyncio.gather(*[asyncio.sleep(0,i) for i in range(3)]))))"
```

把输入换成你自己的数据，观察结果是否仍符合 coroutine 与 async function 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 练习、自测与一页纸速记

<Exercise title='基础：证明调用 async 函数不执行函数体' task='定义 async def f() 带一处 print 和 return 1，只调用 f() 并打印 type、iscoroutine，不驱动它；说明为什么没有输出 print，最后用 close() 避免警告。' solution='import inspect\nasync def f():\n    print(&#39;ran&#39;)\n    return 1\nc = f()\nprint(type(c).__name__, inspect.iscoroutine(c))\nprint(&#39;body executed?&#39;, False)\nc.close()' explain='async def 调用只建 PyCoroObject，帧未启动，函数体一行不跑；必须 await 或交给 loop 驱动。close() 显式关闭未启动协程，避免 never awaited 警告。' />

<Exercise title='进阶：用自定义 __await__ 观察暂停与恢复' task='写一个 __await__ 生成器，yield None 一次后 return 42，在协程里 await 它并用 asyncio.run 驱动，打印结果；解释事件循环如何恢复它。' solution='import asyncio\nclass Pause:\n    def __await__(self):\n        yield\n        return 42\nasync def main():\n    return await Pause()\nprint(asyncio.run(main()))' explain='__await__ 返回迭代器，yield None 让 Task 用 call_soon 重新调度 send(None)；第二次推进到 return，值 42 成为 await 表达式结果，等价于 asyncio.sleep(0) 的机制。' />

<Quiz no='068-1' q='调用一个 async def 函数（不 await）会得到什么？' :options='["一个 coroutine 对象，函数体不执行，可能被 GC 时警告 never awaited", "立即执行函数体并返回 return 的值", "一个已完成的 asyncio.Future", "抛 RuntimeError: no running loop"]' answer="0" explain='async def 调用只构造协程对象；函数体直到 send(None) 或 await 才运行，从不驱动会在回收时打印 RuntimeWarning: coroutine was never awaited。' />

<Quiz no='068-2' q='协程里必须跑同步阻塞函数，最稳妥的做法是？' :options='["await asyncio.to_thread(fn, *args) 或换原生异步库", "直接调用 fn()，它会自动让出 GIL", "改用 time.sleep 给 loop 喘息时间", "用 threading.Thread 启动后不 join"]' answer="0" explain='同步调用不释放事件循环；to_thread 把它放进线程池并在完成时把结果送回 loop，还继承 contextvars。纯 Python 计算换线程仍受 GIL 限制，但 IO 与释放 GIL 的 C 扩展能重叠。' />

<Quiz no='068-3' q='在普通 def（非 async）里写 await f()，结果是？' :options='["编译期 SyntaxError: &#39;await&#39; outside function", "正常运行，只是没有并发", "运行时 TypeError", "自动把该函数升级为协程"]' answer="0" explain='await 是语法层面的保留用法，只允许出现在 async def 体内；编译器在生成字节码前就拒绝，与运行时是否有 loop 无关。' />

<Predict no='068-4' q='下面 asyncio.run 中 gather(work(&#39;A&#39;,5), work(&#39;B&#39;,10)) 的输出顺序是？' :options='["A:10 然后 B:45", "B:45 然后 A:10", "抛 RuntimeError: no running event loop"]' answer='0' output='A:10\nB:45' explain='work 计算 0..n-1 的累加，A 得 10、B 得 45；asyncio.gather 按传入 awaitable 的顺序收集结果，与两个 Task 谁先就绪无关，所以打印顺序固定为 A 再 B。' />

<FillBlank no='068-5' tpl='import  ___ io' :answers='["async"]' hint='回想本讲关于 coroutine 与 async function 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 调用 async 函数只创建协程对象，不执行函数体 的落点。' />

<KnowledgeCard :points='["async def 带 CO_COROUTINE=128；调用只返回 coroutine 对象，函数体不执行，要 await / asyncio.run / create_task 驱动", "await 只能出现在 async def 内；顶层写 await 报 SyntaxError: &#39;await&#39; outside function", "awaitable 三类：原生协程、types.coroutine 生成器协程、实现 __await__ 的对象；inspect.isawaitable 可判定", "asyncio.run 建新 loop → 跑协程 → _cancel_all_tasks → 关异步生成器 → 关 loop；已有 loop 时再调用报 RuntimeError", "协程里禁止 time.sleep / 同步 requests，用 asyncio.to_thread / run_in_executor 下沉阻塞或换原生异步库", "CO_ASYNC_GENERATOR 是 3.6（PEP 525）、async with 是 3.5；裸 create_task 须保存强引用否则可能被 GC 回收"]' :pitfalls='["调用 async 函数直接把返回值当结果用", "在协程里用 time.sleep 或同步 requests.get", "顶层写 await 或在已有 loop 的线程里再调 asyncio.run", "在协程里调用 time.sleep 或同步 requests 会阻塞整个事件循环，一个慢请求拖垮所有并发"]' summary='调用 async 函数只创建协程对象，不会执行任何一行；必须 await 或交给事件循环调度，这是最常见的入门坑' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| async def 带 CO_COROUTINE=128；调用只返回 coroutine 对象，函数体不执行，要 await / asyncio.run / create_task 驱动 | 建立直觉 |
| await 只能出现在 async def 内；顶层写 await 报 SyntaxError: 'await' outside function | 跑通示例 |
| awaitable 三类：原生协程、types.coroutine 生成器协程、实现 __await__ 的对象；inspect.isawaitable 可判定 | 深入边界 |
| asyncio.run 建新 loop → 跑协程 → _cancel_all_tasks → 关异步生成器 → 关 loop；已有 loop 时再调用报 RuntimeError | 工程落地 |
| 协程里禁止 time.sleep / 同步 requests，用 asyncio.to_thread / run_in_executor 下沉阻塞或换原生异步库 | 随堂检测 |
| CO_ASYNC_GENERATOR 是 3.6（PEP 525）、async with 是 3.5；裸 create_task 须保存强引用否则可能被 GC 回收 | 复盘 |

1. async def 带 CO_COROUTINE=128；调用只返回 coroutine 对象，函数体不执行，要 await / asyncio.run / create_task 驱动

2. await 只能出现在 async def 内；顶层写 await 报 SyntaxError: 'await' outside function

3. awaitable 三类：原生协程、types.coroutine 生成器协程、实现 __await__ 的对象；inspect.isawaitable 可判定

[下一讲：asyncio 深入：Task、Future 与事件循环](/concurrency/asyncio)
