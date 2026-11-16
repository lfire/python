"""
第 001 讲 · 开篇：Python 是什么，为什么值得学
与教程正文一一对应的示例代码

课程页面：/guide/opening
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/001-opening.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/001-opening.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# int 1
# str one
# (3, 12, 4) CPython
# TypeError unsupported operand type(s) for +

import sys, platform

x = 1
print(type(x).__name__, x)
x = 'one'
print(type(x).__name__, x)
print(sys.version_info[:3], platform.python_implementation())
try:
    print(1 + '1')
except TypeError as e:
    print(type(e).__name__, str(e)[:40])

# ======================== 2. 对照写法 ========================
# 预期输出：
# 6 abab [1, 2, 1, 2]
# {}

def twice(x):
    return x * 2

print(twice(3), twice('ab'), twice([1, 2]))
print(twice.__annotations__)

# ======================== 3. 原理验证 ========================
# 预期输出：
# ('x',) (None, 2)
#   LOAD_FAST 0 (x)
#   LOAD_CONST 1 (2)
#   BINARY_OP 5 (*)
#   RETURN_VALUE

import dis

def twice(x):
    return x * 2

print(twice.__code__.co_varnames, twice.__code__.co_consts)
dis.dis(twice)

# ======================== 4. 工程案例 ========================

import time

data = list(range(200000))

def loop_sum(xs):
    total = 0
    for x in xs:
        total += x
    return total

for name, fn in [('python-loop', loop_sum), ('builtin', sum)]:
    t0 = time.perf_counter()
    result = fn(data)
    cost = (time.perf_counter() - t0) * 1000
    print(f'{name:12s} {result:>12d}  {cost:6.2f} ms')
