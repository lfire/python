"""
第 020 讲 · tuple 与具名元组：不可变性的价值
与教程正文一一对应的示例代码

课程页面：/containers/tuple
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/020-tuple.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/020-tuple.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# single tuple no comma int
# shallow immutable ([1, 2, 9], 3)
# assign error TypeError
# unhashable TypeError
# dict key a
# unpack 10 20 star 1 [2, 3, 4]
# match origin x-axis quadrant
# named 3 4 {'x': 3, 'y': 4} Point(x=3, y=9)
# is tuple True 7

from collections import namedtuple

single = (1,)
not_tuple = (1)
print('single', type(single).__name__, 'no comma', type(not_tuple).__name__)

t = ([1, 2], 3)
t[0].append(9)
print('shallow immutable', t)
try:
    t[0] = [0]
except TypeError as e:
    print('assign error', type(e).__name__)

try:
    print(hash(([1, 2],)))
except TypeError as e:
    print('unhashable', type(e).__name__)

coord = (10, 20)
print('dict key', {(1, 2): 'a'}[(1, 2)])
a, b = coord
head, *tail = (1, 2, 3, 4)
print('unpack', a, b, 'star', head, tail)

def classify(point):
    match point:
        case (0, 0):
            return 'origin'
        case (x, 0):
            return 'x-axis'
        case (x, y):
            return 'quadrant'

print('match', classify((0, 0)), classify((5, 0)), classify((2, 3)))

Point = namedtuple('Point', 'x y')
p = Point(3, 4)
print('named', p.x, p.y, p._asdict(), p._replace(y=9))
print('is tuple', isinstance(p, tuple), p[0] + p[1])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# NamedTuple defaults Point(x=3, y=0) {'y': 0} {'x': 3, 'y': 0}
# frozen hash True
# frozen error FrozenInstanceError
# multi return 1 9 tuple

from typing import NamedTuple
from dataclasses import dataclass, FrozenInstanceError

class Point(NamedTuple):
    x: int
    y: int = 0

p = Point(3)
print('NamedTuple defaults', p, Point._field_defaults, p._asdict())

@dataclass(frozen=True)
class Config:
    host: str
    port: int = 8080

c = Config('localhost')
print('frozen hash', hash(c) == hash(Config('localhost', 8080)))
try:
    c.port = 9090
except FrozenInstanceError as e:
    print('frozen error', type(e).__name__)

def minmax(xs):
    return min(xs), max(xs)
lo, hi = minmax([3, 1, 9])
print('multi return', lo, hi, type(minmax([1])).__name__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# tuple smaller True
# has append False has append list True
# inner changed ([1, 9], 2)
# hash requires all hashable TypeError
# namedtuple mro ['Point', 'tuple', 'object']
# fields ('x', 'y') is tuple subclass True
# hash namedtuple True

import sys
from collections import namedtuple

a = (1, 2, 3)
b = [1, 2, 3]
print('tuple smaller', sys.getsizeof(a) < sys.getsizeof(b))
print('has append', hasattr(a, 'append'), 'has append list', hasattr(b, 'append'))

t = ([1], 2)
t[0].append(9)
print('inner changed', t)
try:
    hash(t)
except TypeError as e:
    print('hash requires all hashable', type(e).__name__)

Point = namedtuple('Point', 'x y')
p = Point(1, 2)
print('namedtuple mro', [c.__name__ for c in Point.__mro__[:3]])
print('fields', Point._fields, 'is tuple subclass', issubclass(Point, tuple))
print('hash namedtuple', hash(p) == hash((1, 2)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from typing import NamedTuple

class QueryKey(NamedTuple):
    start: int
    end: int
    metrics: tuple

cache = {}

def lookup(key):
    if key not in cache:
        cache[key] = {'rows': key.end - key.start, 'metrics': len(key.metrics)}
    return cache[key]

k = QueryKey(100, 200, ('pv', 'uv'))
print('first', lookup(k))
print('same key reused', lookup(QueryKey(100, 200, ('pv', 'uv'))) is cache[k])
variant = k._replace(end=300)
print('variant', variant, lookup(variant))
print('asdict keys', list(k._asdict()))

a, b, m = k
print('unpack', a, b, m)
