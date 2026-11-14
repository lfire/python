"""
第 024 讲 · 推导式：四种写法与可读性边界
与教程正文一一对应的示例代码

课程页面：/containers/comprehension
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/024-comprehension.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/024-comprehension.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# list [1, 4, 9, 16, 25]
# set [0, 1, 2] dict {1: 1, 2: 4, 3: 9, 4: 16, 5: 25}
# gen type generator sum 55
# no leak outer [0, 1, 2]
# nested for [(0, 0), (0, 1), (0, 2), (1, 0)] len 6
# two ifs [4]
# conditional expr ['odd', 'even', 'odd', 'even', 'odd']
# outer iterable captured [1, 2, 3]
# walrus [4, 6]

nums = [1, 2, 3, 4, 5]
squares = [x * x for x in nums]
uniq = {x % 3 for x in nums}
mapping = {x: x * x for x in nums}
gen = (x * x for x in nums)
print('list', squares)
print('set', sorted(uniq), 'dict', mapping)
print('gen type', type(gen).__name__, 'sum', sum(gen))

i = 'outer'
comp = [i for i in range(3)]
print('no leak', i, comp)

pairs = [(a, b) for a in range(2) for b in range(3)]
print('nested for', pairs[:4], 'len', len(pairs))
filtered = [x for x in nums if x % 2 == 0 if x > 2]
print('two ifs', filtered)
labels = ['even' if x % 2 == 0 else 'odd' for x in nums]
print('conditional expr', labels)

data = [1, 2, 3]
g = (x for x in data)
data = [9, 9]
print('outer iterable captured', list(g))

doubled = [y for x in [1, 2, 3] if (y := x * 2) > 2]
print('walrus', doubled)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# pipeline [16, 25]
# gen size constant True
# map filter [2, 4, 6] [3, 4]
# walrus in iterable SyntaxError

import sys

def pipeline(rows):
    cleaned = (int(r.strip()) for r in rows if r.strip())
    squared = (x * x for x in cleaned)
    return (x for x in squared if x > 10)

rows = [' 1 ', '2', '', ' 4 ', '5']
print('pipeline', list(pipeline(rows)))
print('gen size constant', sys.getsizeof((x for x in range(10**6))) < 1000)

mapped = list(map(lambda x: x * 2, [1, 2, 3]))
filtered = list(filter(lambda x: x > 2, [1, 2, 3, 4]))
print('map filter', mapped, filtered)

try:
    code = '[y for x in (n := 3) for y in range(n)]'
    compile(code, '<s>', 'eval')
except SyntaxError as e:
    print('walrus in iterable', type(e).__name__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# scope isolated ('outer', [0, 1, 2])
# frame exists True
# first value 0
# generator protocol True True True
# comprehension faster True
# LIST_APPEND present True

import dis
from time import perf_counter

def with_comp():
    x = 'outer'
    return x, [x for x in range(3)]
print('scope isolated', with_comp())

g = (x for x in range(3))
print('frame exists', g.gi_frame is not None)
print('first value', next(g))
print('generator protocol', hasattr(g, 'send'), hasattr(g, 'throw'), hasattr(g, 'close'))

def loop(n):
    out = []
    for i in range(n):
        out.append(i * i)
    return out
n = 100000
t0 = perf_counter(); loop(n); t_loop = perf_counter() - t0
t0 = perf_counter(); [i * i for i in range(n)]; t_comp = perf_counter() - t0
print('comprehension faster', t_comp < t_loop)
print('LIST_APPEND present', 'LIST_APPEND' in dis.Bytecode(lambda: [i for i in range(3)]).dis())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import io

def make_source(text):
    return io.StringIO(text)

def pipeline(lines):
    stripped = (line.strip() for line in lines)
    nonempty = (s for s in stripped if s)
    numbers = (int(s) for s in nonempty)
    big = (n for n in numbers if n >= 10)
    squared = (n * n for n in big)
    return squared

rows = ' 1' + chr(10) + '20' + chr(10) + '' + chr(10) + '5' + chr(10) + '30'
result = list(pipeline(make_source(rows)))
print('filtered squares', result)
print('count', len(result), 'sum', sum(result))

def aggregate(lines):
    total = 0
    count = 0
    for value in pipeline(lines):
        total += value
        count += 1
    return {'count': count, 'total': total}

print('aggregate from list', aggregate(['12', ' 40 ', '3']))
print('aggregate from file', aggregate(make_source('11' + chr(10) + '25')))
