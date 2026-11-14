"""
第 017 讲 · 序列协议与通用操作
与教程正文一一对应的示例代码

课程页面：/containers/sequence
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/017-sequence.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/017-sequence.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# 5 Mon Fri
# ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'] True
# Week ['Tue', 'Thu']
# 3 1 ['Fri', 'Thu', 'Wed', 'Tue', 'Mon']
# ['x', 'y', 'z'] ['Y', 'z']

from collections.abc import Sequence

class Week(Sequence):
    def __init__(self, names):
        self._names = tuple(names)
    def __len__(self):
        return len(self._names)
    def __getitem__(self, index):
        if isinstance(index, slice):
            return Week(self._names[index])
        return self._names[index]

w = Week(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
print(len(w), w[0], w[-1])
print(list(w), 'Wed' in w)
s = w[1:4:2]
print(type(s).__name__, list(s))
print(w.index('Thu'), w.count('Mon'), list(reversed(w)))

a = ['x', 'y', 'z']
b = a[1:]
b[0] = 'Y'
print(a, b)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# False
# ['v0', 'v1', 'v2']
# True False
# (2, -1, -1)
# (1, 5, 2)

class Legacy:
    def __getitem__(self, i):
        if i >= 3:
            raise IndexError(i)
        return 'v' + str(i)

x = Legacy()
print(hasattr(x, '__iter__'))
print(list(iter(x)))
print('v2' in x, 'v9' in x)

print(slice(None, None, -1).indices(3))
print(slice(1, 10, 2).indices(5))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# abstract ['__getitem__', '__len__']
# isabstract True
# __iter__ True
# __contains__ True
# __reversed__ True
# index True
# count True
# isinstance True
# mixin owner Sequence.__iter__

from collections.abc import Sequence
import inspect

class Week(Sequence):
    def __init__(self, names):
        self._names = tuple(names)
    def __len__(self):
        return len(self._names)
    def __getitem__(self, index):
        return self._names[index]

print('abstract', sorted(Sequence.__abstractmethods__))
print('isabstract', inspect.isabstract(Sequence))
for m in ('__iter__', '__contains__', '__reversed__', 'index', 'count'):
    print(m, m in Sequence.__dict__)
print('isinstance', isinstance(Week(['a']), Sequence))
print('mixin owner', Sequence.__iter__.__qualname__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from collections.abc import Sequence

class RingView(Sequence):
    def __init__(self, capacity):
        self._buf = [None] * capacity
        self._start = 0
        self._size = 0
    def push(self, item):
        cap = len(self._buf)
        idx = (self._start + self._size) % cap
        self._buf[idx] = item
        if self._size == cap:
            self._start = (self._start + 1) % cap
        else:
            self._size += 1
    def __len__(self):
        return self._size
    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(self._size)))
        if index < 0:
            index += self._size
        if not 0 <= index < self._size:
            raise IndexError(index)
        return self._buf[(self._start + index) % len(self._buf)]

v = RingView(3)
for n in (10, 20, 30, 40):
    v.push(n)
print(len(v), list(v), v[0], v[-1])
print('30 in view', 30 in v, '10 in view', 10 in v)
print('slice', v[1:3], 'reversed', list(reversed(v)))
