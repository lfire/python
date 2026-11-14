"""
第 070 讲 · 阶段综合：并发爬虫四级演进
与教程正文一一对应的示例代码

课程页面：/concurrency/capstone
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/070-capstone.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/070-capstone.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# unique 3
# results [('u1', 5), ('u2', 4), ('u3', 5)]
# retries [('u2', 0)]

import asyncio

PAGES = {
    'u1': 'alpha',
    'u2': 'beta',
    'u3': 'gamma',
}

async def fetch(url, fail_first=False, attempts=None):
    for i in range(3):
        if fail_first and i == 0 and url == 'u2':
            attempts.append((url, i))
            await asyncio.sleep(0)
            continue
        await asyncio.sleep(0)
        return len(PAGES[url])

async def crawl(urls, limit=2):
    seen = set()
    sem = asyncio.Semaphore(limit)
    attempts = []

    async def one(url):
        if url in seen:
            return None
        seen.add(url)
        async with sem:
            n = await fetch(url, True, attempts)
            return (url, n)

    results = await asyncio.gather(*(one(u) for u in urls))
    return results, attempts

async def main():
    urls = ['u1', 'u2', 'u1', 'u3']
    results, attempts = await crawl(urls)
    print('unique', len([r for r in results if r]))
    print('results', sorted(r for r in results if r))
    print('retries', attempts)

asyncio.run(main())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# serial == threaded True
# sum 14995000

from concurrent.futures import ThreadPoolExecutor

def work(n):
    return sum(range(n))

nums = [1000, 2000, 3000, 4000]
with ThreadPoolExecutor(max_workers=4) as ex:
    threaded = list(ex.map(work, nums))
serial = [work(n) for n in nums]
print('serial == threaded', serial == threaded)
print('sum', sum(serial))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# materialized peak > generator peak True

import tracemalloc

def collect_all(urls):
    return [len(u) * 100 for u in urls]

def stream(urls):
    for u in urls:
        yield len(u) * 100

urls = ['page-%d' % i for i in range(50000)]
tracemalloc.start()
all_pages = collect_all(urls)
peak_all = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
tracemalloc.start()
gen = stream(urls)
next(gen)
peak_stream = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print('materialized peak > generator peak', peak_all > peak_stream)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import asyncio, json

PAGES = {'a': 3, 'b': 5, 'c': 2, 'd': 7, 'e': 4}

async def fetch(url, fail_once=False):
    for attempt in range(3):
        if fail_once and url == 'b' and attempt == 0:
            await asyncio.sleep(0)
            continue
        await asyncio.sleep(0)
        return PAGES.get(url, 0)

async def crawl(urls, seen, sem):
    async def one(url):
        if url in seen:
            return None
        seen.add(url)
        async with sem:
            value = await fetch(url, True)
            return (url, value)
    return await asyncio.gather(*(one(u) for u in urls))

async def main():
    seen = set()
    sem = asyncio.Semaphore(2)
    batches = [['a', 'b', 'a', 'c'], ['b', 'd', 'c'], ['e']]
    for batch in batches:
        rows = await crawl(batch, seen, sem)
        print('batch', len(batch), 'new', len([r for r in rows if r]))
    print('total unique', len(seen))
    print('checkpoint', json.dumps(sorted(seen)))

if __name__ == '__main__':
    asyncio.run(main())
