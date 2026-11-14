"""
第 094 讲 · Pandas 清洗、分组、透视与时间序列
与教程正文一一对应的示例代码

课程页面：/data-ai/pandas
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/094-pandas.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/094-pandas.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# add {'北京': 11, '上海': 25, '广州': None, '深圳': None}
# fill0 {'北京': 11, '上海': 25, '广州': 30, '深圳': 8}

def align_add(a, b, fill=None):
    keys = list(dict.fromkeys(list(a) + list(b)))
    out = {}
    for k in keys:
        if k in a and k in b:
            out[k] = a[k] + b[k]
        elif fill is None:
            out[k] = None
        else:
            out[k] = a.get(k, fill) + b.get(k, fill)
    return out

s1 = {'北京': 10, '上海': 20, '广州': 30}
s2 = {'上海': 5, '深圳': 8, '北京': 1}
print('add', align_add(s1, s2))
print('fill0', align_add(s1, s2, fill=0))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# agg {'A': 15.0, 'B': 7.0}
# transform [-5.0, 5.0, -2.0, 0.0, 2.0]
# lengths 2 5

from collections import defaultdict
rows = [('A', 10), ('A', 20), ('B', 5), ('B', 7), ('B', 9)]
g = defaultdict(list)
for k, v in rows: g[k].append(v)
means = {k: sum(v) / len(v) for k, v in g.items()}
print('agg', means)
print('transform', [v - means[k] for k, v in rows])
print('lengths', len(means), len(rows))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# distinct str objects 1000
# object approx bytes 49000
# codes raw bytes 4000 itemsize 4
# category total approx 4196 ratio 11.7

import sys, array
n = 1000
cells = ['region-' + str(i % 4) for i in range(n)]
str_bytes = sum(sys.getsizeof(c) for c in cells)
codes = array.array('i', [i % 4 for i in range(n)])
cat_raw = codes.buffer_info()[1] * codes.itemsize
cat_bytes = cat_raw + sum(sys.getsizeof('region-' + str(k)) for k in range(4))
print('distinct str objects', len({id(c) for c in cells}))
print('object approx bytes', str_bytes)
print('codes raw bytes', cat_raw, 'itemsize', codes.itemsize)
print('category total approx', cat_bytes, 'ratio', round(str_bytes / cat_bytes, 1))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from collections import defaultdict
from datetime import datetime

raw = [
    ('o1', '华东 ', '2024-03-01', 120),
    ('o2', '华北', '2024-03-01', 80),
    ('o1', '华东 ', '2024-03-01', 120),
    ('o3', '华东', '2024-03-02', 200),
]

def clean(rows):
    seen, out = set(), []
    for oid, region, day, amount in rows:
        key = oid
        if key in seen: continue
        seen.add(key)
        out.append((oid, region.strip(), datetime.strptime(day, '%Y-%m-%d').date(), amount))
    return out

def report(rows):
    g = defaultdict(int)
    for _, region, _, amount in rows: g[region] += amount
    means = {r: g[r] / max(1, sum(1 for x in rows if x[1] == r)) for r in g}
    dev = [(oid, amount - means[region]) for oid, region, _, amount in rows]
    return dict(g), len(rows), dev

cleaned = clean(raw)
totals, n, dev = report(cleaned)
print('rows after dedup', n, 'totals', totals)
print('deviation', [(o, round(d, 1)) for o, d in dev])
