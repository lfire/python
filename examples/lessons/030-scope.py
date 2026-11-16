"""
第 030 讲 · 作用域、LEGB 与闭包延迟绑定
与教程正文一一对应的示例代码

课程页面：/functions/scope
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/030-scope.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/030-scope.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# [3, 3, 3, 3]
# [0, 1, 2, 3]
# ('i',)
# 3

def build_bad():
    return [lambda: i for i in range(4)]

def build_good():
    return [lambda i=i: i for i in range(4)]

print([f() for f in build_bad()])
print([f() for f in build_good()])
print(build_bad()[0].__code__.co_freevars)
print(build_bad()[0].__closure__[0].cell_contents)

# ======================== 2. 对照写法 ========================
# 预期输出：
# [0, 1, 2]
# 1 2 3
# UnboundLocalError cannot access local variable 'x' where it is not associated with a value

def make(n):
    def reader():
        return n
    return reader

fs = [make(i) for i in range(3)]
print([f() for f in fs])

def counter():
    c = 0
    def bump():
        nonlocal c
        c += 1
        return c
    return bump

b = counter()
print(b(), b(), b())

def broken():
    print(x)
    x = 1
try:
    broken()
except UnboundLocalError as e:
    print(type(e).__name__, str(e))

# ======================== 3. 原理验证 ========================
# 预期输出：
# ('x',) 1
# 10
# True
# {'x': 10}

import dis, inspect

def outer():
    x = 10
    def inner():
        return x
    return inner

fn = outer()
cd = fn.__code__
print(cd.co_freevars, len(fn.__closure__))
print(fn.__closure__[0].cell_contents)
ops = [i.opname for i in dis.get_instructions(fn)]
print('LOAD_DEREF' in ops)
print(inspect.getclosurevars(fn).nonlocals)

# ======================== 4. 工程案例 ========================

def make_validator(limit):
    def check(value):
        return 0 <= value <= limit
    return check

rules = {}
for name, cap in [('cpu', 100), ('mem', 512), ('disk', 2048)]:
    rules[name] = make_validator(cap)

print([(k, rules[k](50)) for k in rules])
print(rules['cpu'].__closure__[0].cell_contents)

def make_counter():
    n = 0
    def inc():
        nonlocal n
        n += 1
        return n
    return inc

calls = make_counter()
print(calls(), calls(), calls())
print(make_counter.__code__.co_cellvars)
