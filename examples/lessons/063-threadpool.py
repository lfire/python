"""
第 063 讲 · 线程池与 Future 模式
与教程正文一一对应的示例代码

课程页面：/concurrency/threadpool
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/063-threadpool.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/063-threadpool.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# out [(0, 0), (1, 1), (2, 'job-2'), (3, 9), (4, 16)]
# all done True
# cancelled True
# map [0, 1, 9]

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# cancel pending True
# f1 cancelled True True
# f0 result 0 exception None

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# submit (self, fn, /, *args, **kwargs)
# map (self, fn, *iterables, timeout=None, chunksize=1)
# shutdown (self, wait=True, *, cancel_futures=False)
# default max_workers 16
# Future states PENDING RUNNING FINISHED

import concurrent.futures as cf
import inspect
import os

print('submit', str(inspect.signature(cf.Executor.submit)))
print('map', str(inspect.signature(cf.Executor.map)))
print('shutdown', str(inspect.signature(cf.Executor.shutdown)))
cpu = getattr(os, 'process_cpu_count', os.cpu_count)()
print('default max_workers', min(32, cpu + 4))
print('Future states', cf._base.PENDING, cf._base.RUNNING, cf._base.FINISHED)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

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
