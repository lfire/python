"""
第 102 讲 · 模型调优：交叉验证、正则化与过拟合
与教程正文一一对应的示例代码

课程页面：/data-ai/model-tuning
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/102-model-tuning.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/102-model-tuning.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# k 1 train_err 0.0 valid_err 0.333
# k 3 train_err 0.111 valid_err 0.167
# k 5 train_err 0.222 valid_err 0.0
# k 7 train_err 0.222 valid_err 0.0
# k 9 train_err 0.444 valid_err 0.5

import math
train = [(1, 0), (2, 0), (3, 1), (4, 0), (5, 0), (6, 1), (7, 1), (8, 1), (9, 1)]
valid = [(2.5, 0), (3.5, 0), (4.5, 0), (5.5, 1), (6.5, 1), (8.5, 1)]
def knn_err(train, data, k):
    wrong = 0
    for x, lab in data:
        near = sorted(train, key=lambda r: abs(r[0] - x))[:k]
        votes = sum(1 for _, l in near if l == 1)
        pred = 1 if votes > k / 2 else 0
        wrong += int(pred != lab)
    return round(wrong / len(data), 3)
for k in (1, 3, 5, 7, 9):
    print('k', k, 'train_err', knn_err(train, train, k), 'valid_err', knn_err(train, valid, k))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# grid [(1, 0.333), (3, 0.167), (5, 0.0), (7, 0.0), (9, 0.5)]
# best_k 5

grid = [(k, knn_err(train, valid, k)) for k in (1, 3, 5, 7, 9)]
best_k = min(grid, key=lambda t: t[1])[0]
print('grid', grid)
print('best_k', best_k)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# mean pred 10.5
# bias^2 0.25
# variance 1.675
# MSE approx 1.925

import statistics as st
preds = [11.2, 9.5, 10.8, 12.1, 8.9]
truth = 10.0
bias = st.mean(preds) - truth
var = st.variance(preds)
print('mean pred', round(st.mean(preds), 3))
print('bias^2', round(bias ** 2, 3))
print('variance', round(var, 3))
print('MSE approx', round(bias ** 2 + var, 3))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

def knn_err(train, data, k):
    wrong = 0
    for x, lab in data:
        near = sorted(train, key=lambda r: abs(r[0] - x))[:k]
        votes = sum(1 for _, l in near if l == 1)
        wrong += int((1 if votes > k / 2 else 0) != lab)
    return wrong / len(data)

base = [(1, 0), (2, 0), (3, 0), (4, 1), (6, 0), (7, 1), (8, 1), (9, 1),
        (5, 0), (10, 1), (11, 1), (12, 0)]
valid = [(2.5, 0), (5.5, 1), (8.5, 1), (3.5, 0), (6.5, 1)]
for frac in (0.3, 0.6, 1.0):
    n = max(3, int(len(base) * frac))
    tr = base[:n]
    print('n', n, 'valid_err(k=3)', round(knn_err(tr, valid, 3), 3))
