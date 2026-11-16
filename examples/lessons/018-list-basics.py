"""
第 018 讲 · list：动态数组、操作与时间复杂度
与教程正文一一对应的示例代码

课程页面：/containers/list-basics
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/018-list-basics.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/018-list-basics.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# mixed types ['int', 'str', 'list']
# stores refs True TWO
# reallocs far fewer True
# size never shrinks True
# after insert(0) ['head', 0, 1, 2, 3]
# pop(0) head now [0, 1, 2, 3]
# pop() 3 now [0, 1, 2]
# deque [0, 1, 2, 3, 4] 0 4

import sys
from collections import deque

row = [1, 'two', [3]]
print('mixed types', [type(x).__name__ for x in row])
print('stores refs', row[2] is row[2], row[1].upper())

a = []
sizes = []
for i in range(200):
    a.append(i)
    sizes.append(sys.getsizeof(a))
reallocs = sum(1 for i in range(1, len(sizes)) if sizes[i] != sizes[i - 1])
print('reallocs far fewer', reallocs < 20)
print('size never shrinks', all(sizes[i] >= sizes[i - 1] for i in range(1, len(sizes))))

b = [0, 1, 2, 3]
b.insert(0, 'head')
print('after insert(0)', b)
print('pop(0)', b.pop(0), 'now', b)
print('pop()', b.pop(), 'now', b)

d = deque([1, 2, 3])
d.appendleft(0)
d.append(4)
print('deque', list(d), d.popleft(), d.pop())

# ======================== 2. 对照写法 ========================
# 预期输出：
# insert(0) much slower than append True
# deque.appendleft faster than insert(0) True

from collections import deque
from time import perf_counter

def build(mode, n):
    seq = deque() if mode == 'deque' else []
    t0 = perf_counter()
    for i in range(n):
        if mode == 'list-insert':
            seq.insert(0, i)
        elif mode == 'deque':
            seq.appendleft(i)
        else:
            seq.append(i)
    return perf_counter() - t0

n = 10000
t_insert = build('list-insert', n)
t_append = build('list-append', n)
t_deque = build('deque', n)
print('insert(0) much slower than append', t_insert > t_append * 5)
print('deque.appendleft faster than insert(0)', t_deque < t_insert)

# ======================== 3. 原理验证 ========================
# 预期输出：
# growth is stepwise True
# all growth positive True
# container stores reference True
# append compiles to CALL True

import sys, dis

a = []
cap = []
for i in range(1, 40):
    a.append(i)
    cap.append(sys.getsizeof(a))
changes = [i + 1 for i in range(1, len(cap)) if cap[i] != cap[i - 1]]
print('growth is stepwise', 0 < len(changes) < 39)
print('all growth positive', all(cap[i] >= cap[i - 1] for i in range(1, len(cap))))

obj = []
holder = [obj]
print('container stores reference', holder[0] is obj)
print('append compiles to CALL', 'CALL' in dis.Bytecode(lambda x: x.append(1)).dis())

# ======================== 4. 工程案例 ========================

from collections import deque
import statistics

SAMPLES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

def moving_avg(samples, width, stride):
    window = deque(maxlen=width)
    out = [0.0] * ((len(samples) - width) // stride + 1)
    k = 0
    for i, v in enumerate(samples):
        window.append(v)
        if len(window) == width and (i + 1 - width) % stride == 0:
            out[k] = round(statistics.mean(window), 2)
            k += 1
    return out[:k]

print('width 3 stride 2', moving_avg(SAMPLES, 3, 2))
print('width 4 stride 1', moving_avg(SAMPLES, 4, 1))
q = deque(maxlen=3)
for x in (1, 2, 3, 4):
    q.append(x)
print('bounded deque', list(q), len(q))
