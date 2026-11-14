"""
第 019 讲 · list 进阶：切片赋值、排序与常见陷阱
与教程正文一一对应的示例代码

课程页面：/containers/list-advanced
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/019-list-advanced.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/019-list-advanced.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# sort returns None
# after sort [('a', 1), ('a', 3), ('b', 2), ('b', 1)]
# stable for equal keys [1, 3]
# sorted new list [('y', 1), ('z', 2), ('x', 3)] src intact [('x', 3), ('y', 1), ('z', 2)]
# key calls 3 equals len True
# slice assign changes length [0, 'a', 'b', 'c', 3, 4]
# extended slice error ValueError
# shared rows True [[9, 0, 0], [9, 0, 0], [9, 0, 0]]
# fixed rows False [9, 0, 0]
# safe removal [1, 3, 5]

from operator import itemgetter

pairs = [('b', 2), ('a', 1), ('a', 3), ('b', 1)]
print('sort returns', pairs.sort(key=itemgetter(0)))
print('after sort', pairs)
print('stable for equal keys', [p[1] for p in pairs if p[0] == 'a'])

src = [('x', 3), ('y', 1), ('z', 2)]
new = sorted(src, key=itemgetter(1))
print('sorted new list', new, 'src intact', src)

calls = []
def key_count(record):
    calls.append(record)
    return record[1]
sorted(src, key=key_count)
print('key calls', len(calls), 'equals len', len(calls) == len(src))

a = [0, 1, 2, 3, 4]
a[1:3] = ['a', 'b', 'c']
print('slice assign changes length', a)
try:
    a[::2] = [1, 2]
except ValueError as e:
    print('extended slice error', type(e).__name__)

grid = [[0] * 3] * 3
grid[0][0] = 9
print('shared rows', grid[0] is grid[1], grid)
fixed = [[0] * 3 for _ in range(3)]
fixed[0][0] = 9
print('fixed rows', fixed[0] is fixed[1], fixed[0])

nums = [1, 2, 3, 4, 5]
for x in nums[:]:
    if x % 2 == 0:
        nums.remove(x)
print('safe removal', nums)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# reverse keeps stability [(2, 'c'), (1, 'b'), (1, 'a'), (1, 'd')]
# by score then name [('bob', 25), ('amy', 30), ('cy', 30)]
# cmp_to_key [1, -2, 2, -3]

from operator import itemgetter
from functools import cmp_to_key

data = [(1, 'b'), (1, 'a'), (2, 'c'), (1, 'd')]
print('reverse keeps stability', sorted(data, key=lambda r: r[0], reverse=True))

rows = [('amy', 30), ('bob', 25), ('cy', 30)]
print('by score then name', sorted(rows, key=itemgetter(1, 0)))

def by_abs(a, b):
    return (abs(a) > abs(b)) - (abs(a) < abs(b))
print('cmp_to_key', sorted([-3, 1, -2, 2], key=cmp_to_key(by_abs)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# key called once per item True 4
# iterated values [1, 2, 4, 6]
# skipped item 3? True
# prealloc no larger True

from operator import itemgetter
import sys

hit = {'n': 0}
def key(record):
    hit['n'] += 1
    return record[1]

rows = [('a', 3), ('b', 1), ('c', 2), ('d', 1)]
sorted(rows, key=key)
print('key called once per item', hit['n'] == len(rows), hit['n'])

nums = [1, 2, 3, 4, 5, 6]
kept = []
for x in nums:
    if x % 2 == 0:
        nums.remove(x)
    kept.append(x)
print('iterated values', kept)
print('skipped item 3?', 3 not in kept)

a = [None] * 1000
b = []
for _ in range(1000):
    b.append(None)
print('prealloc no larger', sys.getsizeof(a) <= sys.getsizeof(b))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from operator import itemgetter

LOGS = [
    ('INFO', 3, 'started'),
    ('DEBUG', 1, 'cache warm'),
    ('INFO', 2, 'connected'),
    ('ERROR', 4, 'timeout'),
    ('DEBUG', 5, 'retry'),
    ('INFO', 6, 'done'),
]

def pipeline(records):
    kept = [r for r in records if r[0] != 'DEBUG']
    ordered = sorted(kept, key=itemgetter(0, 1))
    out = [None] * len(ordered)
    out[:] = ordered
    return out

result = pipeline(LOGS)
print('count', len(result))
print('first', result[0], 'last', result[-1])
print('info order', [r[1] for r in result if r[0] == 'INFO'])
print('stable within level', result[1][0] == result[2][0])

buf = [0, 0, 0, 0, 0]
buf[1:4] = [10, 20]
print('slice shrink', len(buf), buf)
