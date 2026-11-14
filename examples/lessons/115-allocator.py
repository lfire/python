"""
第 115 讲 · 内存分配器 pymalloc 与 GC 源码
与教程正文一一对应的示例代码

课程页面：/advanced/allocator
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/115-allocator.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/115-allocator.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# threshold (2000, 10, 10)
# tracked_list True
# tracked_int False
# node_referrers 1
# cycle_collectable True
# gen0_below_threshold True

import gc

print('threshold', gc.get_threshold())
print('tracked_list', gc.is_tracked([]))
print('tracked_int', gc.is_tracked(1))

class Node:
    __slots__ = ('ref',)
    def __init__(self):
        self.ref = None

a = Node(); b = Node()
a.ref = b; b.ref = a
refs = len([r for r in gc.get_referrers(b) if isinstance(r, Node)])
print('node_referrers', refs)
del a, b
found = gc.collect(2)
print('cycle_collectable', found >= 2)
print('gen0_below_threshold', gc.get_count()[0] < gc.get_threshold()[0])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# alive_without_gc True
# collected True
# weak_dead True

import gc, weakref

class C:
    pass

gc.disable()
a = C(); a.self = a
r = weakref.ref(a)
del a
print('alive_without_gc', r() is not None)
n = gc.collect()
print('collected', n >= 1)
print('weak_dead', r() is None)
gc.enable()

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# tracked_obj False
# generations 3
# alloc_positive True
# getsizeof_dict 64
# getsizeof_int 28

import gc, tracemalloc, sys

print('tracked_obj', gc.is_tracked(object()))
print('generations', len(gc.get_stats()))
tracemalloc.start()
snap1 = tracemalloc.take_snapshot()
block = [dict(i=i) for i in range(500)]
snap2 = tracemalloc.take_snapshot()
top = snap2.compare_to(snap1, 'lineno')[0]
print('alloc_positive', top.size > 0)
print('getsizeof_dict', sys.getsizeof({}))
print('getsizeof_int', sys.getsizeof(1))
tracemalloc.stop()

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import gc, tracemalloc, weakref, sys

def diagnose(build):
    tracemalloc.start()
    s1 = tracemalloc.take_snapshot()
    obj = build()
    s2 = tracemalloc.take_snapshot()
    top = s2.compare_to(s1, 'lineno')[0]
    cur, peak = tracemalloc.get_traced_memory()
    print('growth_bytes', top.size, 'traced', cur)
    print('gen_counts', gc.get_count())
    r = weakref.ref(obj)
    del obj
    print('alive_before_collect', r() is not None)
    n = gc.collect()
    print('collected', n, 'alive_after', r() is not None)
    tracemalloc.stop()
    return cur

class Node:
    def __init__(self):
        self.ref = self

diagnose(Node)
