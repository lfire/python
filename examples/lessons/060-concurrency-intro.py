"""
第 060 讲 · 并发、并行与 IO 模型全景
与教程正文一一对应的示例代码

课程页面：/concurrency/concurrency-intro
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/060-concurrency-intro.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/060-concurrency-intro.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# io route thread-or-asyncio
# cpu route process-or-cext
# io waits more True
# little law 10.0
# cores >= 2 True

import time
import os

def io_bound():
    time.sleep(0.02)

def cpu_bound():
    return sum(i * i for i in range(2000000))

def measure(fn):
    t0 = time.perf_counter()
    c0 = time.process_time()
    fn()
    wall = time.perf_counter() - t0
    cpu = time.process_time() - c0
    return wall, cpu

def route(fn):
    wall, cpu = measure(fn)
    wait = max(wall - cpu, 0.0)
    if wait > cpu * 2:
        return 'thread-or-asyncio'
    return 'process-or-cext'

print('io route', route(io_bound))
print('cpu route', route(cpu_bound))
wall, cpu = measure(io_bound)
print('io waits more', wall - cpu > cpu)
print('little law', round(200 * 0.05, 1))
print('cores >= 2', os.cpu_count() >= 2)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# would_block True
# after send recv b'ping'
# blocking flag True

import socket
import errno

a, b = socket.socketpair()
b.setblocking(False)
try:
    b.recv(64)
except BlockingIOError as e:
    print('would_block', e.errno in (errno.EAGAIN, errno.EWOULDBLOCK))
a.send(b'ping')
print('after send recv', b.recv(64))
print('blocking flag', b.gettimeout() == 0.0)
a.close()
b.close()

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# gil_enabled True
# switch_interval_is_float True
# interval_positive True
# interval_default True

import sys

print('gil_enabled', getattr(sys, '_is_gil_enabled', lambda: 'n/a')())
print('switch_interval_is_float', isinstance(sys.getswitchinterval(), float))
print('interval_positive', sys.getswitchinterval() > 0)
print('interval_default', sys.getswitchinterval() == 0.005)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import concurrent.futures as cf
import time

def io_job(i):
    time.sleep(0.01)
    return i

def cpu_job(n):
    return sum(k * k for k in range(n))

def wait_ratio(fn, arg):
    t0 = time.perf_counter()
    c0 = time.process_time()
    fn(arg)
    wall = time.perf_counter() - t0
    cpu = time.process_time() - c0
    return (wall - cpu) / max(wall, 1e-9)

def dispatch(specs):
    report = {}
    for name, fn, arg, pool in specs:
        with pool as ex:
            fut = ex.submit(fn, arg)
            report[name] = (round(wait_ratio(fn, arg), 3), fut.result())
    return report

if __name__ == '__main__':
    specs = [
        ('io', io_job, 7, cf.ThreadPoolExecutor(2)),
        ('cpu', cpu_job, 20000, cf.ProcessPoolExecutor(2)),
    ]
    out = dispatch(specs)
    print('io waiting', out['io'][0] > 0.5, out['io'][1] == 7)
    print('cpu waiting', out['cpu'][0] < 0.5, out['cpu'][1] > 0)
