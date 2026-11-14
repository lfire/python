"""
第 007 讲 · 变量是名字绑定：赋值、引用与命名规范
与教程正文一一对应的示例代码

课程页面：/foundation/variables
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/007-variables.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/007-variables.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# swapped 2 1
# first 10 middle [20, 30] last 40
# chain_alias [1]
# int_aug 6

a, b = 1, 2
a, b = b, a
print('swapped', a, b)

first, *middle, last = [10, 20, 30, 40]
print('first', first, 'middle', middle, 'last', last)

x = y = []
x.append(1)
print('chain_alias', y)

n = 5
n += 1
print('int_aug', n)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# r1 ['a']
# r2 ['a', 'b']
# shared True
# fixed ['a'] ['b']

def collect(item, bucket=[]):
    bucket.append(item)
    return bucket

r1 = collect('a')
print('r1', r1)
r2 = collect('b')
print('r2', r2)
print('shared', r1 is r2)

def fixed(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket

print('fixed', fixed('a'), fixed('b'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# defaults ([],)
# default_shared True
# param_default []
# after_call ([1],)

import inspect

def f(x, acc=[]):
    acc.append(x)
    return acc

print('defaults', f.__defaults__)
print('default_shared', f.__defaults__[0] is inspect.signature(f).parameters['acc'].default)
sig = inspect.signature(f)
print('param_default', sig.parameters['acc'].default)
f(1)
print('after_call', f.__defaults__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

def summarize(rows, acc=None):
    if acc is None:
        acc = []
    for name, amount in rows:
        acc.append((name, amount))
    total = sum(amount for _, amount in acc)
    return total, acc

def render(report):
    head, *body, tail = report
    return {'head': head, 'rows': len(body), 'tail': tail}

batch1 = [('north', 10), ('south', 20)]
batch2 = [('east', 5)]
t1, r1 = summarize(batch1)
t2, r2 = summarize(batch2)
print('totals', t1, t2)
print('isolated', r1 is not r2)
print('r2_len', len(r2))
lines = ['HEAD', 'r1', 'r2', 'FOOT']
print('render', render(lines))
