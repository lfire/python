"""
第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event
与教程正文一一对应的示例代码

课程页面：/concurrency/sync-primitives
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/062-sync-primitives.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/062-sync-primitives.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# out [0, 1, 2]
# wait_for rechecks True
# locked 20000

import threading

cond = threading.Condition()
ready = []
out = []

def consumer():
    with cond:
        cond.wait_for(lambda: len(ready) >= 3)
        out.extend(ready)

def producer():
    for i in range(3):
        with cond:
            ready.append(i)
            cond.notify_all()

c = threading.Thread(target=consumer, name='consumer')
c.start()
producer()
c.join()
print('out', out)
print('wait_for rechecks', len(out) == 3)

lock = threading.Lock()
counter = [0]
def add():
    for _ in range(5000):
        with lock:
            counter[0] += 1
ts = [threading.Thread(target=add) for _ in range(4)]
for t in ts: t.start()
for t in ts: t.join()
print('locked', counter[0])

# ======================== 2. 对照写法 ========================
# 预期输出：
# before set False
# broadcast [0, 1, 2]
# overflow ValueError
# parties 2 broken False
# rlock reentrant True

import threading

go = threading.Event()
seen = []
ws = [threading.Thread(target=lambda i=i: (go.wait(), seen.append(i))) for i in range(3)]
for t in ws: t.start()
print('before set', go.is_set())
go.set()
for t in ws: t.join()
print('broadcast', sorted(seen))

sem = threading.BoundedSemaphore(2)
sem.acquire()
sem.release()
try:
    sem.release()
    sem.release()
    sem.release()
except ValueError as e:
    print('overflow', type(e).__name__)

bar = threading.Barrier(2)
def peer():
    bar.wait()
t = threading.Thread(target=peer)
t.start()
print('parties', bar.parties, 'broken', bar.broken)
bar.wait()
t.join()

rl = threading.RLock()
with rl:
    with rl:
        print('rlock reentrant', True)

# ======================== 3. 原理验证 ========================
# 预期输出：
# has while loop True
# wait_for sig (self, predicate, timeout=None)
# Semaphore value default 1
# Event wait sig (self, timeout=None)
# switch interval True

import inspect
import sys
import threading

src = inspect.getsource(threading.Condition.wait_for)
print('has while loop', 'while' in src)
print('wait_for sig', str(inspect.signature(threading.Condition.wait_for)))
print('Semaphore value default', inspect.signature(threading.Semaphore).parameters['value'].default)
print('Event wait sig', str(inspect.signature(threading.Event.wait)))
print('switch interval', sys.getswitchinterval() == 0.005)

# ======================== 4. 工程案例 ========================

import collections
import threading
import time

class BoundedBuffer:
    def __init__(self, cap):
        self.cap = cap
        self.buf = collections.deque()
        self.cv = threading.Condition()
        self.stopped = threading.Event()
    def put(self, item):
        with self.cv:
            self.cv.wait_for(lambda: len(self.buf) < self.cap or self.stopped.is_set())
            if self.stopped.is_set():
                return False
            self.buf.append(item)
            self.cv.notify_all()
        return True
    def drain(self):
        while True:
            with self.cv:
                ok = self.cv.wait_for(
                    lambda: len(self.buf) > 0 or self.stopped.is_set(), timeout=0.2)
                if self.buf:
                    item = self.buf.popleft()
                    self.cv.notify_all()
                elif self.stopped.is_set():
                    return
    def stop(self):
        with self.cv:
            self.stopped.set()
            self.cv.notify_all()

if __name__ == '__main__':
    b = BoundedBuffer(2)
    t = threading.Thread(target=b.drain, name='writer')
    t.start()
    for i in range(6):
        b.put(i)
    b.stop()
    t.join(timeout=2)
    print('stopped', b.stopped.is_set(), 'alive', t.is_alive())
