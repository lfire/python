"""
第 065 讲 · 进程间通信：Queue、Pipe 与信号
与教程正文一一对应的示例代码

课程页面：/concurrency/ipc
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/065-ipc.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/065-ipc.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# queue got [0, 1, 2]
# event set True
# pipe recv {'k': 1}
# manager dict 1 DictProxy

import multiprocessing as mp

def producer(q, ev):
    for i in range(3):
        q.put(i)
    ev.set()

if __name__ == '__main__':
    ctx = mp.get_context()
    q = ctx.Queue()
    ev = ctx.Event()
    p = ctx.Process(target=producer, args=(q, ev))
    p.start()
    got = [q.get(timeout=5) for _ in range(3)]
    print('queue got', got)
    print('event set', ev.is_set())
    p.join()

    parent, child = ctx.Pipe(duplex=True)
    parent.send({'k': 1})
    print('pipe recv', child.recv())
    parent.close()
    child.close()

    with ctx.Manager() as mgr:
        d = mgr.dict()
        d['a'] = 1
        print('manager dict', d['a'], type(d).__name__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# value 0 array [0, 0, 0]
# simple queue x
# queue has task_done False
# SIGTERM 15
# exitcode 0 alive False
# children []

import multiprocessing as mp
import signal

def noop():
    pass

if __name__ == '__main__':
    ctx = mp.get_context()
    val = ctx.Value('i', 0)
    arr = ctx.Array('i', 3)
    print('value', val.value, 'array', list(arr))
    sq = ctx.SimpleQueue()
    sq.put('x')
    print('simple queue', sq.get())
    print('queue has task_done', hasattr(ctx.Queue(), 'task_done'))
    print('SIGTERM', int(signal.SIGTERM))
    p = ctx.Process(target=noop)
    p.start()
    p.join()
    print('exitcode', p.exitcode, 'alive', p.is_alive())
    print('children', mp.active_children())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# Queue has feeder True
# Queue has task_done False
# Pipe duplex default True
# connection.wait available True
# platform darwin

import inspect
import multiprocessing as mp
import multiprocessing.queues as mq
import sys

print('Queue has feeder', '_feed' in inspect.getsource(mq.Queue))
print('Queue has task_done', hasattr(mq.Queue, 'task_done'))
print('Pipe duplex default', inspect.signature(mp.Pipe).parameters['duplex'].default)
print('connection.wait available', hasattr(__import__('multiprocessing.connection', fromlist=['wait']), 'wait'))
print('platform', sys.platform)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import multiprocessing as mp
import signal
import time

def worker(wid, q, ack, stop):
    done = 0
    while True:
        try:
            item = q.get(timeout=0.1)
        except Exception:
            if stop.is_set():
                break
            continue
        done += 1
    ack.put((wid, done))

if __name__ == '__main__':
    ctx = mp.get_context()
    q, ack, stop = ctx.Queue(), ctx.Queue(), ctx.Event()
    procs = [ctx.Process(target=worker, args=(i, q, ack, stop)) for i in range(2)]
    for p in procs: p.start()
    for i in range(20): q.put(i)
    def on_term(signum, frame):
        stop.set()
    signal.signal(signal.SIGTERM, on_term)
    time.sleep(0.3)
    stop.set()
    for p in procs:
        p.join(timeout=2)
        if p.is_alive():
            p.terminate()
    total = sum(ack.get(timeout=1)[1] for _ in range(2))
    print('stop', stop.is_set(), 'acked', total,
          'alive', [p.is_alive() for p in procs])
