"""
第 029 讲 · 返回值、None 与多返回值
与教程正文一一对应的示例代码

课程页面：/functions/returns
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/029-returns.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/029-returns.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# (2, 8, 5.0)
# 2 8 5.0
# True
# TypeError cannot unpack non-iterable NoneType object
# 1 [2, 3, 4]

def stats(xs):
    if not xs:
        return None
    return min(xs), max(xs), sum(xs) / len(xs)

print(stats([2, 8, 5]))
lo, hi, avg = stats([2, 8, 5])
print(lo, hi, avg)
print(stats([]) is None)
try:
    a, b = stats([])
except TypeError as e:
    print(type(e).__name__, str(e))
first, *rest = (1, 2, 3, 4)
print(first, rest)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# ['book', 'pen'] True
# ('book', 'pen') tuple
# a
# StopIteration end

class Cart:
    def __init__(self):
        self.items = []
    def raw(self):
        return self.items
    def snapshot(self):
        return tuple(self.items)

c = Cart()
c.items.append('book')
r = c.raw()
r.append('pen')
print(list(c.items), r is c.items)
print(c.snapshot(), type(c.snapshot()).__name__)

def pages():
    yield 'a'
    return 'end'
g = pages()
print(next(g))
try:
    next(g)
except StopIteration as e:
    print(type(e).__name__, e.value)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# (None,) (None,)
# True 1
# True generator
# 32 True

import dis, inspect

def pair(a, b):
    return a, b

def single(a):
    return a

print(pair.__code__.co_consts, single.__code__.co_consts)
ops = [i.opname for i in dis.get_instructions(pair)]
print('BUILD_TUPLE' in ops, ops.count('BUILD_TUPLE'))
def gen():
    yield 1
    return 'done'
print(inspect.isgeneratorfunction(gen), type(gen()).__name__)
print(gen.__code__.co_flags & 0x20, None is type(None)())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from dataclasses import dataclass

@dataclass(frozen=True)
class Result:
    ok: bool
    value: object
    error: str

USERS = {'u1': ('Ada', 36), 'u2': ('Lin', None)}

def find(uid):
    if uid not in USERS:
        return Result(False, None, 'not found')
    name, age = USERS[uid]
    return Result(True, (name, age), '')

def display(uid):
    r = find(uid)
    if not r.ok:
        return 'error: ' + r.error
    name, age = r.value
    return name + ' / ' + ('unknown' if age is None else str(age))

print(display('u1'))
print(display('u2'))
print(display('u9'))
print(find('u1').value)
