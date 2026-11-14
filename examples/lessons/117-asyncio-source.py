"""
第 117 讲 · asyncio 事件循环与 Task 源码
与教程正文一一对应的示例代码

课程页面：/advanced/asyncio-source
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/117-asyncio-source.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/117-asyncio-source.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# task_type Task
# coro work
# cancelling_before 0
# cancelling_after 1
# result cancelled
# cancelled_flag False done True

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# shield_got_cancelled True
# task_cancelled False
# task_result ok

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# loop_class _UnixSelectorEventLoop
# time_positive True
# timer_type TimerHandle
# calls ['soon', 'later']

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

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
