"""
第 099 讲 · SVM、核方法、决策树与随机森林
与教程正文一一对应的示例代码

课程页面：/data-ai/svm-trees
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/099-svm-trees.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/099-svm-trees.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# root gini 0.5
# best split (0.0, 3.5, 3, 3)

def gini(labels):
    n = len(labels)
    if n == 0: return 0.0
    counts = {}
    for l in labels: counts[l] = counts.get(l, 0) + 1
    return 1 - sum((c / n) ** 2 for c in counts.values())

def best_split(rows):
    xs = sorted(set(r[0] for r in rows))
    best_w, best_t, best_left, best_right = None, None, 0, 0
    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:
        left = [l for x, l in rows if x <= t]
        right = [l for x, l in rows if x > t]
        w = (len(left) * gini(left) + len(right) * gini(right)) / len(rows)
        if best_w is None or w < best_w:
            best_w, best_t = w, t
            best_left, best_right = len(left), len(right)
    return (round(best_w, 4), best_t, best_left, best_right)

data = [(1, 'N'), (2, 'N'), (3, 'N'), (4, 'P'), (5, 'P'), (6, 'P')]
print('root gini', round(gini([l for _, l in data]), 4))
print('best split', best_split(data))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# mapped [(-1, 1, 1), (0, 0, -1), (1, 1, 1)]
# K(-1,1) 0 K(-1,0) 1

def poly_kernel(x, z, degree=2, c=1):
    return (x * z + c) ** degree
pts = [(-1, 1), (0, -1), (1, 1)]
print('mapped', [(x, x * x, lab) for x, lab in pts])
print('K(-1,1)', poly_kernel(-1, 1), 'K(-1,0)', poly_kernel(-1, 0))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# single var 1.103
# bagged var 0.142

import statistics as st
trees = [[10.5, 9.2, 11.1, 8.7, 10.8],
         [9.8, 11.5, 9.1, 10.6, 9.9],
         [12.0, 8.5, 10.2, 11.3, 9.4]]
single = trees[0]
avg = [st.mean(col) for col in zip(*trees)]
print('single var', round(st.variance(single), 3))
print('bagged var', round(st.variance(avg), 3))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from collections import Counter

def gini(labels):
    n = len(labels)
    if not n: return 0.0
    c = Counter(labels)
    return 1 - sum((v / n) ** 2 for v in c.values())

def split(rows):
    xs = sorted(set(r[0] for r in rows))
    best = None
    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:
        L = [r for r in rows if r[0] <= t]
        R = [r for r in rows if r[0] > t]
        w = (len(L) * gini([l for _, l in L]) + len(R) * gini([l for _, l in R])) / len(rows)
        if best is None or w < best[0]: best = (w, t, L, R)
    return best

def build(rows, depth, max_depth):
    labels = [l for _, l in rows]
    if depth >= max_depth or gini(labels) == 0 or len(set(r[0] for r in rows)) < 2:
        return ('leaf', len(rows), round(gini(labels), 3))
    w, t, L, R = split(rows)
    return ('split', round(t, 1), build(L, depth + 1, max_depth), build(R, depth + 1, max_depth))

def leaves(node):
    return 1 if node[0] == 'leaf' else leaves(node[2]) + leaves(node[3])

data = [(1, 'N'), (2, 'N'), (3, 'N'), (4, 'P'), (5, 'P'), (6, 'P'), (7, 'P'), (8, 'N')]
print('depth1 leaves', leaves(build(data, 0, 1)))
print('depth3 leaves', leaves(build(data, 0, 3)))
print('depth3 tree', build(data, 0, 1))
