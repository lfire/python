"""
第 023 讲 · set / frozenset：哈希、集合运算与去重
与教程正文一一对应的示例代码

课程页面：/containers/set
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/023-set.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/023-set.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# after add [1, 2, 3, 4] 4
# remove missing KeyError
# union [1, 2, 3, 4, 5]
# intersection [3]
# difference [1, 2]
# symmetric [1, 2, 4, 5]
# subset True True True
# comprehension [0, 1, 4, 9, 16, 25]
# frozenset hashable value
# frozenset ops [1, 2, 3, 4] frozenset
# set dedup ['a', 'b', 'c']
# ordered dedup ['b', 'a', 'c']
# empty set is dict? True

s = {1, 2, 3}
s.add(4)
s.discard(10)
print('after add', sorted(s), len(s))
try:
    s.remove(10)
except KeyError as e:
    print('remove missing', type(e).__name__)

a = {1, 2, 3}
b = {3, 4, 5}
print('union', sorted(a | b))
print('intersection', sorted(a & b))
print('difference', sorted(a - b))
print('symmetric', sorted(a ^ b))
print('subset', {1, 2} <= a, {1, 2} < a, a.isdisjoint({9}))

squares = {x * x for x in range(6)}
print('comprehension', sorted(squares))

fs = frozenset([1, 2, 3])
print('frozenset hashable', {fs: 'value'}[frozenset([3, 2, 1])])
print('frozenset ops', sorted(fs | {4}), type(fs | {4}).__name__)

seq = ['b', 'a', 'b', 'c', 'a']
print('set dedup', sorted(set(seq)))
print('ordered dedup', list(dict.fromkeys(seq)))
print('empty set is dict?', isinstance({}, dict))

# ======================== 2. 对照写法 ========================
# 预期输出：
# set much faster than list True
# pop returns arbitrary True 2
# in-place union [1, 2, 3, 4]
# int hash stable True True
# str hash is int True

from time import perf_counter

data = list(range(4000))
probes = list(range(4000))
def bench(seq):
    t0 = perf_counter()
    for x in probes:
        x in seq
    return perf_counter() - t0
t_list = bench(data)
t_set = bench(set(data))
print('set much faster than list', t_list > t_set * 5)

s = set('abc')
print('pop returns arbitrary', isinstance(s.pop(), str), len(s))
s2 = {1, 2, 3}
s2 |= {3, 4}
print('in-place union', sorted(s2))
print('int hash stable', hash(7) == 7, hash(-1) == -2)
print('str hash is int', isinstance(hash('python'), int))

# ======================== 3. 原理验证 ========================
# 预期输出：
# set resize stepwise True
# frozenset hashable True
# set unhashable TypeError
# hash stable in process True
# empty literal is dict True empty set set

import sys

s = set()
sizes = []
for i in range(100):
    s.add(i)
    sizes.append(sys.getsizeof(s))
changes = sum(1 for i in range(1, len(sizes)) if sizes[i] != sizes[i - 1])
print('set resize stepwise', 0 < changes < 100)

print('frozenset hashable', isinstance(hash(frozenset([1, 2])), int))
try:
    hash({1, 2})
except TypeError as e:
    print('set unhashable', type(e).__name__)

print('hash stable in process', hash('abc') == hash('abc'))
print('empty literal is dict', isinstance({}, dict), 'empty set', type(set()).__name__)

# ======================== 4. 工程案例 ========================

RECORDS = [
    ('r1', frozenset(['a', 'b'])),
    ('r2', frozenset(['a'])),
    ('r1', frozenset(['a', 'b'])),
    ('r3', frozenset(['b', 'c'])),
    ('r4', frozenset([])),
]

seen = set()
ordered = []
for rid, tags in RECORDS:
    if rid not in seen:
        seen.add(rid)
        ordered.append((rid, tags))
print('unique count', len(ordered), 'order', [r for r, _ in ordered])

rule_cache = {frozenset(['a', 'b']): 'rule-AB'}
print('rule hit', rule_cache.get(frozenset(['b', 'a'])))

with_a = {rid for rid, tags in RECORDS if 'a' in tags}
with_b = {rid for rid, tags in RECORDS if 'b' in tags}
print('both', sorted(with_a & with_b))
print('a not b', sorted(with_a - with_b))
print('symmetric', sorted(with_a ^ with_b))
