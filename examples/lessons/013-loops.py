"""
第 013 讲 · 循环：for / while、range 与循环 else
与教程正文一一对应的示例代码

课程页面：/foundation/loops
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/013-loops.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/013-loops.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# range_len 3
# range_list [2, 5, 8]
# range_mem True
# enumerate [(1, 'a'), (2, 'b'), (3, 'c')]
# zip [('a', 1), ('b', 2)]
# no_break loop completed

import sys
r = range(2, 10, 3)
print('range_len', len(r))
print('range_list', list(r))
print('range_mem', sys.getsizeof(range(1000000)) == sys.getsizeof(range(1)))

words = ['a', 'b', 'c']
print('enumerate', list(enumerate(words, 1)))
print('zip', list(zip(words, [1, 2])))

for w in words:
    if w == 'x':
        break
else:
    print('no_break', 'loop completed')

# ======================== 2. 对照写法 ========================
# 预期输出：
# buggy [2, 5]
# fixed [5]

nums = [2, 2, 4, 5]
for n in nums:
    if n % 2 == 0:
        nums.remove(n)
print('buggy', nums)
clean = [n for n in [2, 2, 4, 5] if n % 2 != 0]
print('fixed', clean)

# ======================== 3. 原理验证 ========================
# 预期输出：
# has_iter True
# has_next True
# next_values 1 2
# stop raised
# range_no_next True
# range_is_iterable True

it = iter([1, 2])
print('has_iter', hasattr(it, '__iter__'))
print('has_next', hasattr(it, '__next__'))
print('next_values', next(it), next(it))
try:
    next(it)
except StopIteration:
    print('stop', 'raised')
print('range_no_next', not hasattr(range(3), '__next__'))
print('range_is_iterable', hasattr(range(3), '__iter__'))

# ======================== 4. 工程案例 ========================

def generate_lines(n):
    for i in range(n):
        yield 'row-' + str(i) if i % 3 else ''

def is_valid(line):
    return bool(line) and not line.startswith('#')

def clean(lines):
    return [line for line in lines if is_valid(line)]

raw = list(generate_lines(10))
valid = clean(raw)
print('total', len(raw), 'kept', len(valid))
for idx, line in enumerate(valid, 1):
    if idx <= 2:
        print('first', idx, line)
for line in valid:
    if line == 'missing':
        break
else:
    print('scan', 'no break happened')
pairs = list(zip(valid, ['src'] * len(valid)))
print('pairs', len(pairs), 'first_tag', pairs[0][1])
