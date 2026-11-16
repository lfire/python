"""
第 053 讲 · 分代 GC、循环引用与 weakref
与教程正文一一对应的示例代码

课程页面：/core/gc
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/053-gc.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/053-gc.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# weak alive True
# collected True
# weak dead True
# cache size 1
# cache size after 0

import gc, weakref

class Node:
    pass
a = Node()
b = Node()
a.peer = b
b.peer = a
wr = weakref.ref(a)
print('weak alive', wr() is a)
del a, b
collected = gc.collect()
print('collected', collected > 0)
print('weak dead', wr() is None)
cache = weakref.WeakValueDictionary()
obj = Node()
cache['k'] = obj
print('cache size', len(cache))
del obj
gc.collect()
print('cache size after', len(cache))

# ======================== 2. 对照写法 ========================
# 预期输出：
# threshold (2000, 10, 10)（3.13 起；3.12 及以前为 (700, 10, 10)）
# enabled True
# collected with del True
# garbage list True
# count True

import gc

print('threshold', gc.get_threshold())
print('enabled', gc.isenabled())
class WithDel:
    def __del__(self):
        pass
x = WithDel()
x.self = x
del x
n = gc.collect()
print('collected with del', n > 0)
print('garbage list', isinstance(gc.garbage, list))
print('count', len(gc.get_count()) == 3)

# ======================== 3. 原理验证 ========================
# 预期输出：
# objects grow True
# objects reclaimed True
# tracemalloc available True
# refcount positive True

import gc, sys

gc.collect()
before = len(gc.get_objects())
temp = [object() for _ in range(5000)]
during = len(gc.get_objects())
del temp
gc.collect()
after = len(gc.get_objects())
print('objects grow', during > before)
print('objects reclaimed', after < during)
print('tracemalloc available', hasattr(sys, 'getallocatedblocks'))
print('refcount positive', sys.getrefcount(gc) > 0)

# ======================== 4. 工程案例 ========================

import gc, weakref

class Session:
    def __init__(self, uid):
        self.uid = uid
strong_cache = {}
weak_cache = weakref.WeakValueDictionary()

def fill(caches, n):
    for i in range(n):
        s = Session(i)
        caches[0]['s' + str(i)] = s
        caches[1]['s' + str(i)] = s

gc.collect()
base = len(gc.get_objects())
fill((strong_cache, weak_cache), 500)
gc.collect()
print('strong cache alive', len(strong_cache))
print('weak cache alive', len(weak_cache))
print('objects grew', len(gc.get_objects()) > base)
print('weak cache emptied', len(weak_cache) == 0)
