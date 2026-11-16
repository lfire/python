"""
第 050 讲 · 字节码、栈式虚拟机与 dis 实战
与教程正文一一对应的示例代码

课程页面：/core/bytecode
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/050-bytecode.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/050-bytecode.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# argcount 2
# varnames ('a', 'b', 'c')
# has load_fast True
# has store_fast True
# has binary True
# has return True
# freevars ('x',)
# has LOAD_DEREF True

import dis

def add(a, b):
    c = a + b
    return c
print('argcount', add.__code__.co_argcount)
print('varnames', add.__code__.co_varnames)
ops = [i.opname for i in dis.get_instructions(add)]
print('has load_fast', 'LOAD_FAST' in ops)
print('has store_fast', 'STORE_FAST' in ops)
print('has binary', any(o in ops for o in ('BINARY_OP', 'BINARY_ADD')))
print('has return', 'RETURN_VALUE' in ops)
def outer():
    x = 10
    def inner():
        return x
    return inner
inner = outer()
print('freevars', inner.__code__.co_freevars)
print('has LOAD_DEREF', 'LOAD_DEREF' in [i.opname for i in dis.get_instructions(inner)])

# ======================== 2. 对照写法 ========================
# 预期输出：
# nested code objects []（3.12+ PEP 709 内联；3.11 及以前为 ['<listcomp>']）
# has exceptiontable True（3.11+；3.10 及以前为 False）
# caught in python

import dis

def comp(n):
    return [i * i for i in range(n)]
nested = [c.co_name for c in comp.__code__.co_consts if hasattr(c, 'co_name')]
print('nested code objects', nested)
print('has exceptiontable', hasattr(comp.__code__, 'co_exceptiontable'))
try:
    with open('nope-not-exist', 'r'):
        pass
except FileNotFoundError:
    print('caught in python')

# ======================== 3. 原理验证 ========================
# 预期输出：
# stack ins ['LOAD_FAST', 'LOAD_CONST', 'RETURN_VALUE']
# has binary op True
# dis has adaptive True（3.11+；3.10 为 False）
# int bits positive True
# stacksize positive True

import dis, sys, inspect

def f(x):
    return x + 1
ins = [i.opname for i in dis.get_instructions(f)]
print('stack ins', [o for o in ins if o in ('LOAD_FAST', 'LOAD_CONST', 'RETURN_VALUE')])
print('has binary op', any(o in ins for o in ('BINARY_OP', 'BINARY_ADD')))
print('dis has adaptive', 'adaptive' in inspect.signature(dis.dis).parameters)
print('int bits positive', sys.int_info.bits_per_digit > 0)
print('stacksize positive', f.__code__.co_stacksize > 0)

# ======================== 4. 工程案例 ========================

import dis

def loop_sum(xs):
    total = 0
    for x in xs:
        total += x
    return total

def builtin_sum(xs):
    return sum(xs)

def count(fn):
    return len([i for i in dis.get_instructions(fn) if i.opname not in ('CACHE', 'RESUME')])

print('loop heavier', count(loop_sum) > count(builtin_sum))
print('loop names', loop_sum.__code__.co_names)
print('builtin names', builtin_sum.__code__.co_names)
print('has line table', hasattr(loop_sum.__code__, 'co_linetable') or hasattr(loop_sum.__code__, 'co_lnotab'))
