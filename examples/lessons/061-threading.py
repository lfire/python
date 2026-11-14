"""
第 061 讲 · threading：线程生命周期与共享状态
与教程正文一一对应的示例代码

课程页面：/concurrency/threading
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/061-threading.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/061-threading.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# before start alive [False, False, False, False]
# queue size 4
# results ['w0', 'w1', 'w2', 'w3']
# all joined True

import threading
import queue

q = queue.Queue()
results = []

def worker(n):
    q.put(n * n)
    results.append(threading.current_thread().name)

ts = [threading.Thread(target=worker, args=(i,), name='w' + str(i)) for i in range(4)]
print('before start alive', [t.is_alive() for t in ts])
for t in ts: t.start()
for t in ts: t.join()
print('queue size', q.qsize())
print('results', sorted(results))
print('all joined', all(not t.is_alive() for t in ts))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# join returned True
# future reraises child-boom

import threading
import concurrent.futures as cf

def boom():
    raise ValueError('child-boom')

old = threading.excepthook
threading.excepthook = lambda args: None
t = threading.Thread(target=boom, name='boomer')
t.start()
t.join()
threading.excepthook = old
print('join returned', not t.is_alive())

with cf.ThreadPoolExecutor(1) as ex:
    fut = ex.submit(boom)
    try:
        fut.result()
    except ValueError as e:
        print('future reraises', str(e))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# opnames ['RESUME', 'LOAD_GLOBAL', 'LOAD_CONST', 'BINARY_OP', 'STORE_GLOBAL', 'RETURN_CONST']
# main tls value 0

import dis
import threading

counter = 0
def bump():
    global counter
    counter += 1

print('opnames', [i.opname for i in dis.get_instructions(bump)])
tls = threading.local()
tls.value = 0
def child():
    tls.value = 99
t = threading.Thread(target=child)
t.start(); t.join()
print('main tls value', tls.value)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import concurrent.futures as cf
import threading
import time

def check(item):
    name, delay, fail = item
    time.sleep(delay)
    if fail:
        raise ValueError(name + ' invalid')
    return name + ' ok'

ITEMS = [('fast', 0.01, False), ('boom', 0.01, True), ('slow', 0.30, False)]

def run_all(items, timeout=0.1):
    records = []
    with cf.ThreadPoolExecutor(max_workers=3,
                              thread_name_prefix='checker') as ex:
        futs = {ex.submit(check, it): it[0] for it in items}
        done, pending = cf.wait(futs, timeout=timeout)
        for f in done:
            label = futs[f]
            try:
                records.append((label, 'ok', f.result()))
            except Exception as e:
                records.append((label, 'failed', type(e).__name__ + ': ' + str(e)))
        for f in pending:
            f.cancel()
            records.append((futs[f], 'timeout', 'cancelled'))
    return sorted(records)

if __name__ == '__main__':
    for row in run_all(ITEMS):
        print(row[0], row[1], row[2].split(':')[0])
    print('main thread', threading.current_thread().name)
