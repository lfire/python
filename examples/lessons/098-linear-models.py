"""
第 098 讲 · 经典算法：KNN、线性与逻辑回归
与教程正文一一对应的示例代码

课程页面：/data-ai/linear-models
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/098-linear-models.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/098-linear-models.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# raw B
# scaled A

import math

def knn_predict(train, labels, q, k=3):
    dists = []
    for row, lab in zip(train, labels):
        dists.append((math.dist(row, q), lab))
    dists.sort()
    votes = {}
    for _, lab in dists[:k]:
        votes[lab] = votes.get(lab, 0) + 1
    return max(votes, key=votes.get)

train = [[0.1, 100], [0.2, 9000], [0.15, 300], [0.9, 8000], [0.8, 200], [0.85, 9500]]
labels = ['A', 'A', 'A', 'B', 'B', 'B']
q = [0.12, 5000]
print('raw', knn_predict(train, labels, q))
cols = list(zip(*train))
means = [sum(c) / len(c) for c in cols]
stds = [(sum((x - m) ** 2 for x in c) / len(c)) ** 0.5 for m, c in zip(means, cols)]
def scale(row):
    return [(x - m) / s for x, m, s in zip(row, means, stds)]
strain = [scale(r) for r in train]
print('scaled', knn_predict(strain, labels, scale(q)))

# ======================== 2. 对照写法 ========================
# 预期输出：
# closed 0.6 2.2 0.48
# gd 0.6 2.2 0.48

xs = [1, 2, 3, 4, 5]
ys = [2, 4, 5, 4, 5]
def mse(w, b): return sum((w * x + b - y) ** 2 for x, y in zip(xs, ys)) / len(xs)
mx, my = sum(xs) / 5, sum(ys) / 5
w = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
b = my - w * mx
print('closed', round(w, 3), round(b, 3), round(mse(w, b), 3))
wg, bg, lr = 0.0, 0.0, 0.05
for _ in range(2000):
    dw = sum(2 * (wg * x + bg - y) * x for x, y in zip(xs, ys)) / 5
    db = sum(2 * (wg * x + bg - y) for x, y in zip(xs, ys)) / 5
    wg -= lr * dw; bg -= lr * db
print('gd', round(wg, 3), round(bg, 3), round(mse(wg, bg), 3))

# ======================== 3. 原理验证 ========================
# 预期输出：
# L2 after 10 0.479
# L1 after 10 0.3

w, lr, lam = 0.8, 0.1, 0.5
w2 = [0.8]
w1 = [0.8]
for _ in range(10):
    w2.append(w2[-1] * (1 - lr * lam))
    v = w1[-1] - lr * lam
    w1.append(max(0.0, v) if v > 0 else 0.0)
print('L2 after 10', round(w2[-1], 4))
print('L1 after 10', round(w1[-1], 4))

# ======================== 4. 工程案例 ========================

import math

def standardize(rows):
    cols = list(zip(*rows))
    means = [sum(c) / len(c) for c in cols]
    stds = [(sum((x - m) ** 2 for x in c) / len(c)) ** 0.5 or 1.0
           for m, c in zip(means, cols)]
    out = [[(x - m) / s for x, m, s in zip(r, means, stds)] for r in rows]
    return out, means, stds

def knn(train, labels, q, k=3):
    d = sorted((math.dist(row, q), lab) for row, lab in zip(train, labels))
    votes = {}
    for _, lab in d[:k]:
        votes[lab] = votes.get(lab, 0) + 1
    return max(votes, key=votes.get)

raw = [[0.1, 100], [0.2, 9000], [0.15, 300], [0.9, 8000], [0.8, 200], [0.85, 9500]]
labels = ['A', 'A', 'A', 'B', 'B', 'B']
train, means, stds = standardize(raw)
def transform(r): return [(x - m) / s for x, m, s in zip(r, means, stds)]
queries = [[0.12, 5000], [0.88, 7000], [0.5, 4500]]
print('predictions', [knn(train, labels, transform(q)) for q in queries])
