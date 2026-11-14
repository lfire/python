"""
第 069 讲 · asyncio 深入：Task、Future 与事件循环
与教程正文一一对应的示例代码

课程页面：/concurrency/asyncio
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/069-asyncio.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/069-asyncio.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# initial False False
# after set_result True ready
# slow got CancelledError
# slow finally cleanup
# await t raised CancelledError

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# caught ExceptionGroup count 1
# t1.done True t2.cancelled False

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# Task subclass of Future True
# CancelledError is BaseException True
# TaskGroup 3.11+ True True
# call_later type TimerHandle
# cancelled before False
# cancelled after True

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

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
