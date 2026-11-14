"""
第 052 讲 · 对象内存布局、引用计数与小对象池
与教程正文一一对应的示例代码

课程页面：/core/memory
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/052-memory.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/052-memory.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# small int pooled True
# runtime int distinct False
# getrefcount extra True
# interned same True
# sizeof empty list True

import sys

a = 256
b = 256
print('small int pooled', a is b)
x = int('257')
y = int('257')
print('runtime int distinct', x is y)
print('getrefcount extra', sys.getrefcount(x) > 0)
s1 = sys.intern('cache_key_12345')
s2 = sys.intern('cache_key_12345')
print('interned same', s1 is s2)
print('sizeof empty list', sys.getsizeof([]) > 0)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# list header True
# element size True
# tracemalloc sees growth True

import sys, tracemalloc

items = [str(i) for i in range(1000)]
print('list header', sys.getsizeof(items) > 0)
print('element size', sys.getsizeof(items[0]) > 0)
tracemalloc.start()
before = tracemalloc.take_snapshot()
more = [str(i) for i in range(1000)]
after = tracemalloc.take_snapshot()
diff = sum(s.size_diff for s in after.compare_to(before, 'filename') if s.size_diff > 0)
print('tracemalloc sees growth', diff > 0)
tracemalloc.stop()

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# alias increments True
# del decrements True
# back to base True

import sys

obj = object()
before = sys.getrefcount(obj)
holder = [obj]
during = sys.getrefcount(obj)
del holder
after = sys.getrefcount(obj)
print('alias increments', during > before)
print('del decrements', after < during)
print('back to base', after == before)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import tracemalloc
from collections import namedtuple

Point = namedtuple('Point', 'x y')
tracemalloc.start()
def build_dict(n):
    return [{'x': i, 'y': i * 2} for i in range(n)]
def build_tuple(n):
    return [Point(i, i * 2) for i in range(n)]

d = build_dict(20000)
dict_mem = tracemalloc.get_traced_memory()[0]
del d
t = build_tuple(20000)
tuple_mem = tracemalloc.get_traced_memory()[0]
print('dict heavier', dict_mem > tuple_mem)
print('both positive', dict_mem > 0 and tuple_mem > 0)
print('point fields', Point._fields)
tracemalloc.stop()
