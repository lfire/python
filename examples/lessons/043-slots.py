"""
第 043 讲 · __slots__、弱引用与对象内存布局
与教程正文一一对应的示例代码

课程页面：/oop/slots
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/043-slots.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/043-slots.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# dict True False
# slot kind member_descriptor
# weakref True False
# AttributeError cannot add y
# values 1 1

class Plain:
    def __init__(self, x):
        self.x = x
class Slotted:
    __slots__ = ('x',)
    def __init__(self, x):
        self.x = x

p, s = Plain(1), Slotted(1)
print('dict', hasattr(p, '__dict__'), hasattr(s, '__dict__'))
print('slot kind', type(Slotted.x).__name__)
print('weakref', hasattr(p, '__weakref__'), hasattr(s, '__weakref__'))
try:
    s.y = 2
except AttributeError as e:
    print(type(e).__name__, 'cannot add y')
print('values', p.x, s.x)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# child has dict: True
# weakref ok: True
# ValueError conflict

import weakref

class Base:
    pass
class Child(Base):
    __slots__ = ('x',)
class Full:
    __slots__ = ('x', '__weakref__')
    def __init__(self, x):
        self.x = x

f = Full(2)
print('child has dict:', hasattr(Child(), '__dict__'))
print('weakref ok:', weakref.ref(f)() is f)
try:
    class Bad:
        __slots__ = ('x',)
        x = 1
except ValueError as e:
    print(type(e).__name__, 'conflict')

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# slotted cheaper: True
# saved bytes > 0: True

import tracemalloc

class Plain:
    def __init__(self, x):
        self.x = x
class Slotted:
    __slots__ = ('x',)
    def __init__(self, x):
        self.x = x

tracemalloc.start()
plain = [Plain(i) for i in range(20000)]
p_cur = tracemalloc.get_traced_memory()[0]
del plain
slotted = [Slotted(i) for i in range(20000)]
s_cur = tracemalloc.get_traced_memory()[0]
print('slotted cheaper:', s_cur < p_cur)
print('saved bytes > 0:', p_cur - s_cur > 0)
tracemalloc.stop()

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import tracemalloc, weakref, gc

class Point:
    __slots__ = ('x', 'y', '__weakref__')
    def __init__(self, x, y):
        self.x, self.y = x, y

cache = weakref.WeakValueDictionary()
tracemalloc.start()
points = [Point(i, i * 2) for i in range(50000)]
for i in range(3):
    cache[i] = points[i]
print('points:', len(points), 'cache:', len(cache))
points.clear()
gc.collect()
print('cache after clear:', len(cache))
print('tracing:', tracemalloc.is_tracing())
tracemalloc.stop()
