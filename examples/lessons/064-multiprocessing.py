"""
第 064 讲 · multiprocessing：进程、Pool 与共享内存
与教程正文一一对应的示例代码

课程页面：/concurrency/multiprocessing
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/064-multiprocessing.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/064-multiprocessing.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# start method spawn on darwin
# all methods ['spawn', 'fork', 'forkserver']
# cpu count True
# pool map [1, 4, 9, 16]
# imap chunksize [1, 4, 9, 16]
# exitcode 0
# shm byte 7 size_ge_16 True

import multiprocessing as mp
import os
import sys
from multiprocessing import shared_memory as shm

def square(x):
    return x * x

if __name__ == '__main__':
    print('start method', mp.get_start_method(), 'on', sys.platform)
    print('all methods', mp.get_all_start_methods())
    print('cpu count', os.cpu_count() > 0)
    with mp.Pool(processes=2) as pool:
        print('pool map', pool.map(square, [1, 2, 3, 4]))
        print('imap chunksize', list(pool.imap(square, [1, 2, 3, 4], chunksize=2)))
    p = mp.Process(target=square, args=(5,))
    p.start()
    p.join()
    print('exitcode', p.exitcode)
    sh = shm.SharedMemory(create=True, size=16)
    sh.buf[0] = 7
    print('shm byte', sh.buf[0], 'size_ge_16', sh.size >= 16)
    sh.close()
    sh.unlink()

# ======================== 2. 对照写法 ========================
# 预期输出：
# top-level picklable True
# lambda PicklingError
# fork context fork

import multiprocessing as mp
import pickle

def top_fn(x):
    return x + 1

if __name__ == '__main__':
    print('top-level picklable', pickle.dumps(top_fn)[0] == 128)
    try:
        pickle.dumps(lambda x: x)
    except pickle.PicklingError as e:
        print('lambda', type(e).__name__)
    ctx = mp.get_context('fork')
    print('fork context', ctx.get_start_method())

# ======================== 3. 原理验证 ========================
# 预期输出：
# pickle bytes 29778
# protocol 5
# payload bytes 80056
# start method spawn

import pickle
import sys
import multiprocessing as mp

payload = list(range(10000))
blob = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
print('pickle bytes', len(blob))
print('protocol', pickle.HIGHEST_PROTOCOL)
print('payload bytes', sys.getsizeof(payload))
print('start method', mp.get_start_method())

# ======================== 4. 工程案例 ========================

import array
import multiprocessing as mp
from multiprocessing import shared_memory as shm

def partial_sum(args):
    name, start, end, total_len = args
    block = shm.SharedMemory(name=name)
    try:
        raw = array.array('q')
        raw.frombytes(bytes(block.buf[: total_len * 8]))
        return sum(raw[start:end])
    finally:
        block.close()

if __name__ == '__main__':
    N = 4000
    sh = shm.SharedMemory(create=True, size=N * 8)
    arr = array.array('q', range(N))
    sh.buf[: N * 8] = arr.tobytes()
    chunks = [(sh.name, i, i + 1000, N) for i in range(0, N, 1000)]
    with mp.Pool(processes=2) as pool:
        parts = pool.map(partial_sum, chunks)
    print('parts', len(parts), 'total', sum(parts))
    print('expected', sum(range(N)))
    sh.close()
    sh.unlink()
