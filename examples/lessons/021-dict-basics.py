"""
第 021 讲 · dict：哈希表、视图与插入顺序
与教程正文一一对应的示例代码

课程页面：/containers/dict-basics
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/021-dict-basics.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/021-dict-basics.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# get 1 None 99
# setdefault new 3 existing 1
# order ['a', 'b', 'c'] 3
# view live ['a', 'b', 'c', 'd'] 4 True
# view set ops ['a', 'd']
# merge new 20 5 original b 2
# update returns None has g True
# unhashable TypeError
# reversed keys ['g', 'f', 'd', 'c', 'b', 'a']

d = {'a': 1, 'b': 2}
print('get', d.get('a'), d.get('z'), d.get('z', 99))
print('setdefault new', d.setdefault('c', 3), 'existing', d.setdefault('a', 100))
print('order', list(d), d['c'])

keys = d.keys()
values = d.values()
items = d.items()
d['d'] = 4
print('view live', list(keys), len(values), ('d', 4) in items)
print('view set ops', sorted(keys & {'a', 'd'}))

merged = d | {'b': 20, 'e': 5}
print('merge new', merged['b'], merged['e'], 'original b', d['b'])
d.update({'f': 6})
print('update returns', d.update({'g': 7}), 'has g', 'g' in d)

class NoHash:
    def __eq__(self, other):
        return True
try:
    {NoHash(): 1}
except TypeError as e:
    print('unhashable', type(e).__name__)
print('reversed keys', list(reversed(d)))

# ======================== 2. 对照写法 ========================
# 预期输出：
# resize during iteration RuntimeError
# fromkeys shared {'x': [9], 'y': [9]}
# hash seed differs int
# keys view type dict_keys
# values has set ops False

d = {'a': 1, 'b': 2}
try:
    for k in d:
        d[k * 2] = 1
except RuntimeError as e:
    print('resize during iteration', type(e).__name__)

shared = dict.fromkeys(['x', 'y'], [])
shared['x'].append(9)
print('fromkeys shared', shared)

print('hash seed differs', type(hash('a')).__name__)
print('keys view type', type(d.keys()).__name__)
print('values has set ops', hasattr(d.values(), '__and__'))

# ======================== 3. 原理验证 ========================
# 预期输出：
# hash slot is None True
# resize is stepwise True
# view reflects size True
# view type dict_keys
# hash is int True

import sys

class NoHash:
    def __eq__(self, other):
        return True
print('hash slot is None', NoHash.__hash__ is None)

d = {}
sizes = []
for i in range(200):
    d[i] = i
    sizes.append(sys.getsizeof(d))
changes = sum(1 for i in range(1, len(sizes)) if sizes[i] != sizes[i - 1])
print('resize is stepwise', 0 < changes < 200)

v = d.keys()
print('view reflects size', len(v) == len(d))
print('view type', type(v).__name__)
print('hash is int', isinstance(hash('k'), int))

# ======================== 4. 工程案例 ========================

RECORDS = [
    {'id': 1001, 'tier': 'vip'},
    {'id': 1002, 'tier': 'free'},
    {'id': 1003, 'tier': 'vip'},
]

def build_index(rows):
    return {r['id']: r for r in rows}

index = build_index(RECORDS)
online = index.keys()
print('lookup 1002', index.get(1002), 'missing', index.get(9999))
print('online count', len(online))

batch = {1004: {'id': 1004, 'tier': 'free'}, 1002: {'id': 1002, 'tier': 'vip'}}
new_index = index | batch
print('merge overrides', new_index[1002]['tier'], 'original', index[1002]['tier'])

new_index.setdefault(1005, {'id': 1005, 'tier': 'free'})
print('after setdefault', len(new_index), sorted(new_index)[:3])
print('vip ids', [k for k in sorted(new_index) if new_index[k]['tier'] == 'vip'])
