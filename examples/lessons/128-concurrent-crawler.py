"""
第 128 讲 · 实战 07 · 并发爬虫与分布式调度
与教程正文一一对应的示例代码

课程页面：/projects/concurrent-crawler
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/128-concurrent-crawler.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/128-concurrent-crawler.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# unique ['/a', '/b', '/c', '/d']
# priority order ['/c', '/b', '/a', '/d']
# fetched ['/A', '/B', '/C', '/D']

import asyncio, hashlib, heapq

class Bloom:
    def __init__(self, size, k):
        self.size, self.k, self.bits = size, k, [0] * size
    def _slots(self, s):
        for i in range(self.k):
            yield int(hashlib.md5((str(i) + s).encode()).hexdigest(), 16) % self.size
    def add(self, s):
        for p in self._slots(s):
            self.bits[p] = 1
    def maybe_seen(self, s):
        return all(self.bits[p] for p in self._slots(s))

feed = [(2, '/a'), (1, '/b'), (2, '/a'), (0, '/c'), (1, '/b'), (3, '/d')]
bloom = Bloom(size=128, k=2)
queue, unique = [], []
for pri, u in feed:
    if bloom.maybe_seen(u):
        continue
    bloom.add(u)
    unique.append(u)
    heapq.heappush(queue, (pri, u))
print('unique', unique)
print('priority order', [heapq.heappop(queue)[1] for _ in range(len(queue))])

async def crawl(urls, limit):
    sem = asyncio.Semaphore(limit)
    async def one(u):
        async with sem:
            await asyncio.sleep(0)
            return u.upper()
    return await asyncio.gather(*(one(u) for u in urls))
print('fetched', asyncio.run(crawl(unique, 2)))

# ======================== 2. 对照写法 ========================
# 预期输出：
# acked ['/a'] inflight []
# unacked inflight /b ['/b']
# requeued ['/b', '/c']

from collections import deque

class Queue:
    def __init__(self):
        self.pending = deque()
        self.inflight = {}
        self.done = []
    def push(self, items):
        for i in items:
            self.pending.append(i)
    def take(self):
        item = self.pending.popleft()
        self.inflight[item] = 'taken'
        return item
    def ack(self, item):
        self.inflight.pop(item, None)
        self.done.append(item)

q = Queue()
q.push(['/a', '/b', '/c'])
job = q.take()
q.ack(job)
print('acked', q.done, 'inflight', list(q.inflight))
lost = q.take()
print('unacked inflight', lost, list(q.inflight))
q.pending.appendleft(lost)
del q.inflight[lost]
print('requeued', list(q.pending))

# ======================== 3. 原理验证 ========================
# 预期输出：
# n 4 m 128 k 2 fp~ 0.0037
# n 100 m 1024 k 3 fp~ 0.0164
# n 1000 m 1024 k 3 fp~ 0.8482
# bits per item 10.24

import math

def fp_rate(n, m, k):
    return (1 - math.exp(-k * n / m)) ** k

for n, m, k in [(4, 128, 2), (100, 1024, 3), (1000, 1024, 3)]:
    print('n', n, 'm', m, 'k', k, 'fp~', round(fp_rate(n, m, k), 4))
print('bits per item', round(1024 / 100, 2))

# ======================== 4. 工程案例 ========================

import heapq, json, tempfile
from pathlib import Path

def load_checkpoint(path):
    if not Path(path).exists():
        return {'done': [], 'queue': []}
    return json.loads(Path(path).read_text(encoding='utf-8'))

def save_checkpoint(path, done, queue):
    body = json.dumps({'done': done, 'queue': queue})
    tmp = path + '.tmp'
    Path(tmp).write_text(body, encoding='utf-8')
    Path(tmp).replace(path)

class Worker:
    def __init__(self, checkpoint):
        self.path = checkpoint
        state = load_checkpoint(checkpoint)
        self.done = set(state['done'])
        self.heap = list(state['queue'])
        heapq.heapify(self.heap)
    def submit(self, pri, url):
        if url not in self.done:
            heapq.heappush(self.heap, (pri, url))
    def run(self, n):
        out = []
        for _ in range(n):
            if not self.heap:
                break
            pri, url = heapq.heappop(self.heap)
            self.done.add(url)
            out.append(url)
        save_checkpoint(self.path, sorted(self.done), self.heap)
        return out

path = str(Path(tempfile.mkdtemp()) / 'ck.json')
w = Worker(path)
for pri, u in [(1, '/a'), (0, '/b'), (2, '/c')]:
    w.submit(pri, u)
print('batch1', w.run(2))
w2 = Worker(path)
print('resume done', sorted(w2.done))
print('remaining', [u for _, u in sorted(w2.heap)])
