"""
第 114 讲 · CPython 源码：对象、帧与求值循环
与教程正文一一对应的示例代码

课程页面：/advanced/cpython-source
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/114-cpython-source.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/114-cpython-source.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# name add
# varnames ('a', 'b')
# consts (None,)
# names ()
# stacksize 2
# bytecode_len 10
# caller <module>
# result 5
#   3           RESUME                   0
# 
#   4           LOAD_FAST_LOAD_FAST      1 (a, b)
#               BINARY_OP                0 (+)
#               RETURN_VALUE

import sys, dis

def add(a, b):
    return a + b

co = add.__code__
print('name', co.co_name)
print('varnames', co.co_varnames)
print('consts', co.co_consts)
print('names', co.co_names)
print('stacksize', co.co_stacksize)
print('bytecode_len', len(co.co_code))

def caller_name():
    return sys._getframe(1).f_code.co_name

print('caller', caller_name())
print('result', add(2, 3))
dis.dis(add)

# ======================== 2. 对照写法 ========================
# 预期输出：
# f_consts (None, 3)
# g_consts (None, 2)
# f_nbytes 4
# g_nbytes 12

import dis

def f():
    return 1 + 2

def g(x):
    return x + 2

print('f_consts', f.__code__.co_consts)
print('g_consts', g.__code__.co_consts)
print('f_nbytes', len(f.__code__.co_code))
print('g_nbytes', len(g.__code__.co_code))

# ======================== 3. 原理验证 ========================
# 预期输出：
# rc_start 1
# rc_alias 2
# rc_unbind 1
# consts (None, 2)
# names ()
#  10           RESUME                   0
# 
#  11           LOAD_FAST                0 (a)
#               LOAD_CONST               1 (2)
#               BINARY_OP                5 (*)
#               RETURN_VALUE

import sys, dis

x = [1, 2, 3]
print('rc_start', sys.getrefcount(x) - 1)
y = x
print('rc_alias', sys.getrefcount(x) - 1)
y = 0
print('rc_unbind', sys.getrefcount(x) - 1)

def scale(a):
    return a * 2

print('consts', scale.__code__.co_consts)
print('names', scale.__code__.co_names)
dis.dis(scale)

# ======================== 4. 工程案例 ========================

import dis, sys

def inspect_fn(fn, *args):
    co = fn.__code__
    print('fn', co.co_name)
    print('consts', co.co_consts)
    print('varnames', co.co_varnames)
    print('names', co.co_names)
    print('stacksize', co.co_stacksize)
    print('nbytes', len(co.co_code))
    print('has_exctable', hasattr(co, 'co_exceptiontable'))
    print('result', fn(*args))
    dis.dis(fn)

def compute(a, b):
    t = a * b
    return t + 1

inspect_fn(compute, 3, 4)
print('current_frame', sys._getframe().f_code.co_name)
