"""
第 068 讲 · async / await 与协程对象
与教程正文一一对应的示例代码

课程页面：/concurrency/async-await
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/068-async-await.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/068-async-await.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# is coroutine function True
# calling returns coroutine True
# A:10
# B:45

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

# ======================== 2. 对照写法 ========================
# 预期输出：
# isawaitable True
# await returned resumed

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

# ======================== 3. 原理验证 ========================
# 预期输出：
# CO_COROUTINE 128
# flag set True
# iscoroutinefunction True
# has GET_AWAITABLE True
# has SEND True
# call result coroutine

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

# ======================== 4. 工程案例 ========================

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
