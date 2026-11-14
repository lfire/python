"""
第 031 讲 · 高阶函数、lambda 与 map / filter / reduce
与教程正文一一对应的示例代码

课程页面：/functions/higher-order
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/031-higher-order.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/031-higher-order.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# [3, -2, 0, 4] [3, 4]
# [3, -2, 0, 4] []
# 12
# 1
# TypeError reduce() of empty iterable with no initial value

from functools import reduce
from operator import mul

raw = ['3', '-2', '0', '4']
nums = list(map(int, raw))
pos = list(filter(lambda x: x > 0, nums))
print(nums, pos)
m = map(int, raw)
print(list(m), list(m))
print(reduce(mul, [3, 4], 1))
print(reduce(mul, [], 1))
try:
    print(reduce(mul, []))
except TypeError as e:
    print(type(e).__name__, str(e))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# [('b', 1), ('c', 2), ('a', 3)]
# [3, 1, 2]
# 12 7
# [2, 3] []
# 6

from operator import itemgetter, add, mul
from functools import reduce

rows = [('a', 3), ('b', 1), ('c', 2)]
print(sorted(rows, key=itemgetter(1)))
print(list(map(itemgetter(1), rows)))

OPS = {'add': add, 'mul': mul}
def apply(op, a, b):
    return OPS[op](a, b)
print(apply('mul', 3, 4), apply('add', 3, 4))

f = filter(lambda x: x > 1, [1, 2, 3])
print(list(f), list(f))
print(reduce(add, (1, 2, 3)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# map True 0
# [2, 4, 6] 3
# [] 3
# twice <lambda>
# True False

import dis

calls = []
def twice(x):
    calls.append(x)
    return x * 2

m = map(twice, [1, 2, 3])
print(type(m).__name__, iter(m) is m, len(calls))
print(list(m), len(calls))
print(list(m), len(calls))
print(twice.__name__, (lambda x: x).__name__)
ops = [i.opname for i in dis.get_instructions(twice)]
print('RETURN_VALUE' in ops, 'BUILD_TUPLE' in ops)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from functools import reduce
from operator import add, mul

def pipeline(rows, transforms, predicate):
    stream = rows
    for t in transforms:
        stream = map(t, stream)
    kept = filter(predicate, stream)
    return list(kept)

data = ['3', '4', 'x', '5']

def to_int(s):
    try:
        return int(s)
    except ValueError:
        return 0

good = pipeline(data, [to_int], lambda x: x > 0)
print(good)
print(reduce(add, good, 0))
print(reduce(mul, [], 1))
