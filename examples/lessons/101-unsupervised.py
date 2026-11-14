"""
第 101 讲 · 无监督学习：KMeans、DBSCAN、PCA 与异常检测
与教程正文一一对应的示例代码

课程页面：/data-ai/unsupervised
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/101-unsupervised.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/101-unsupervised.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# (0, 10.0, [3, 4])
# (1, 4.67, [3, 4])
# (2, 4.67, [3, 4])
# centers [(1.33, 3.0), (8.5, 8.5)]

import math
pts = [(1, 2), (1, 4), (2, 3), (8, 8), (9, 8), (8, 9), (9, 9)]
def dist(a, b): return math.dist(a, b)
def kmeans(pts, centers, rounds=3):
    hist = []
    for r in range(rounds):
        groups = [[] for _ in centers]
        for p in pts:
            k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))
            groups[k].append(p)
        sse = sum(dist(p, centers[k]) ** 2 for k, g in enumerate(groups) for p in g)
        hist.append((r, round(sse, 2), [len(g) for g in groups]))
        centers = [(sum(x for x, y in g) / len(g), sum(y for x, y in g) / len(g)) if g else c
                   for g, c in zip(groups, centers)]
    return hist, centers
hist, centers = kmeans(pts, [(1, 2), (8, 8)])
for h in hist: print(h)
print('centers', [(round(a, 2), round(b, 2)) for a, b in centers])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# K=1 168.0
# K=2 7.0
# K=3 5.0

def sse_for_k(pts, centers):
    groups = [[] for _ in centers]
    for p in pts:
        k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))
        groups[k].append(p)
    return round(sum(dist(p, centers[k]) ** 2 for k, g in enumerate(groups) for p in g), 2)
print('K=1', sse_for_k(pts, [(4, 5)]))
print('K=2', sse_for_k(pts, [(1, 3), (8, 8)]))
print('K=3', sse_for_k(pts, [(1, 3), (8, 8), (9, 9)]))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# d(p,q) 1.0 d(p,r) 50.0
# after x*100: d(p,q) 100.0 d(p,r) 50.0

p, q, r = (0, 0), (1, 0), (0, 50)
print('d(p,q)', dist(p, q), 'd(p,r)', dist(p, r))
sp, sq, sr = [(x * 100, y) for x, y in (p, q, r)]
print('after x*100: d(p,q)', dist(sp, sq), 'd(p,r)', dist(sp, sr))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import math

pts = [(1, 2), (1, 4), (2, 3), (8, 8), (9, 8), (8, 9), (9, 9), (50, 50)]
def dist(a, b): return math.dist(a, b)

def kmeans(pts, centers, rounds=5):
    for _ in range(rounds):
        groups = [[] for _ in centers]
        for p in pts:
            k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))
            groups[k].append(p)
        centers = [(sum(x for x, y in g) / len(g), sum(y for x, y in g) / len(g)) if g else c
                   for g, c in zip(groups, centers)]
    return centers

centers = kmeans(pts, [(1, 2), (8, 8)])
scores = [round(min(dist(p, c) for c in centers), 2) for p in pts]
srt = sorted(scores)
q3 = srt[int(len(srt) * 0.75)]
thr = round(q3 * 1.5 + 0.5, 2)
flagged = [p for p, s in zip(pts, scores) if s > thr]
print('centers', [(round(a, 1), round(b, 1)) for a, b in centers])
print('scores', scores)
print('threshold', thr, 'flagged', flagged)
