"""
第 077 讲 · 属性测试、基准测试与模糊测试
与教程正文一一对应的示例代码

课程页面：/engineering/property-testing
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/077-property-testing.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/077-property-testing.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# generated cases 85
# counterexamples 9
# minimal ['NL']

import itertools

def encode(s):
    return s.replace(chr(10), 'NL')

def decode(s):
    return s.replace('NL', chr(10))

def prop(s):
    return decode(encode(s)) == s

alphabet = ['N', 'L', chr(10), 'a']
candidates = [''.join(p) for n in range(4) for p in itertools.product(alphabet, repeat=n)]
failing = [s for s in candidates if not prop(s)]
print('generated cases', len(candidates))
print('counterexamples', len(failing))

def shrink(s):
    best = s
    changed = True
    while changed:
        changed = False
        for i in range(len(best)):
            cand = best[:i] + best[i+1:]
            if cand and not prop(cand):
                best = cand
                changed = True
                break
    return best

minimal = {shrink(s) for s in failing}
print('minimal', sorted(m for m in minimal))

# ======================== 2. 对照写法 ========================
# 预期输出：
# builtin faster True
# both correct True

import timeit

def loop_sum(n):
    total = 0
    for i in range(n):
        total += i
    return total

def builtin_sum(n):
    return sum(range(n))

t_loop = timeit.timeit(lambda: loop_sum(5000), number=200)
t_builtin = timeit.timeit(lambda: builtin_sum(5000), number=200)
print('builtin faster', t_builtin < t_loop)
print('both correct', loop_sum(5000) == builtin_sum(5000))

# ======================== 3. 原理验证 ========================
# 预期输出：
# seeded reproducible True
# seed 7 differs from 8 True
# interpreter 3 13

import random, sys

def stream(seed, k=6):
    rng = random.Random(seed)
    return [rng.randrange(1000) for _ in range(k)]

print('seeded reproducible', stream(7) == stream(7))
print('seed 7 differs from 8', stream(7) != stream(8))
print('interpreter', sys.version_info[0], sys.version_info[1])

# ======================== 4. 工程案例 ========================

import itertools, json

def compact(s):
    return s.replace('  ', ' ')

def prop(s):
    r = compact(s)
    return compact(r) == r

alphabet = [' ', 'a']
cases = [''.join(p) for n in range(6) for p in itertools.product(alphabet, repeat=n)]

def shrink(s):
    best = s
    changed = True
    while changed:
        changed = False
        for i in range(len(best)):
            cand = best[:i] + best[i + 1:]
            if not prop(cand):
                best = cand
                changed = True
                break
    return best

failing = [s for s in cases if not prop(s)]
minimal = sorted({shrink(s) for s in failing})
print('generated', len(cases), 'failing', len(failing))
print('minimal', [repr(m) for m in minimal[:3]])
print('pinned regression', json.dumps([repr(m) for m in minimal[:3]]))
