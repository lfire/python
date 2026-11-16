"""
第 010 讲 · 字符串操作：切片、f-string 与常用方法
与教程正文一一对应的示例代码

课程页面：/foundation/string-ops
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/010-string-ops.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/010-string-ops.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# index P n
# slice yth nohtyP
# out_of_range thon
# align '    42'
# precision '3.14'
# thousands '1,234,567'
# split ['a', 'b', 'c']
# partition ('k', '=', 'v')
# strip x

s = 'Python'
print('index', s[0], s[-1])
print('slice', s[1:4], s[::-1])
print('out_of_range', s[2:99])
print('align', repr(f'{42:>6d}'))
print('precision', repr(f'{3.14159:.2f}'))
print('thousands', repr(f'{1234567:,d}'))
print('split', 'a,b,c'.split(','))
print('partition', 'k=v'.partition('='))
print('strip', '  x  '.strip())

# ======================== 2. 对照写法 ========================
# 预期输出：
# same_result True
# join_faster True
# rsplit ['a.b', 'c']
# splitlines 2

import timeit

def plus_loop(parts):
    s = ''
    for p in parts:
        s += p
    return s

def use_join(parts):
    return ''.join(parts)

parts = ['word'] * 500
t_plus = timeit.timeit(lambda: plus_loop(parts), number=200)
t_join = timeit.timeit(lambda: use_join(parts), number=200)
print('same_result', plus_loop(parts) == use_join(parts))
print('join_faster', t_join < t_plus)
print('rsplit', 'a.b.c'.rsplit('.', 1))
print('splitlines', len(('a' + chr(10) + 'b').splitlines()))

# ======================== 3. 原理验证 ========================
# 预期输出：
# new_object True
# same_prefix True
# interned_literal True
# getsizeof_grows True
# slice_is_copy True

import sys
a = 'abc'
b = 'abc'
t = a + 'd'
print('new_object', t is not a)
print('same_prefix', t[:3] == a)
print('interned_literal', a is b)
print('getsizeof_grows', sys.getsizeof('abcd') >= sys.getsizeof('abc'))
print('slice_is_copy', a[1:] is not a)

# ======================== 4. 工程案例 ========================

def fmt_row(level, name, ms, count):
    cells = [
        f'{level:<8s}',
        f'{name:<12s}',
        f'{ms:>8.2f}',
        f'{count:>10,d}',
    ]
    return ''.join(cells)

def parse_event(line):
    key, sep, value = line.partition('=')
    return key, value if sep else ''

rows = [
    fmt_row('INFO', 'fetch', 12.5, 1234567),
    fmt_row('WARN', 'retry', 3.5, 890),
    fmt_row('ERROR', 'timeout', 250.0, 42),
]
out = chr(10).join(rows)
print('lines', len(out.splitlines()))
print('width', len(rows[0]))
key, value = parse_event('status=ok')
print('key', key, 'value', value)
print('has_count', '1,234,567' in rows[0])
print('aligned', rows[0].startswith('INFO'))
