"""
第 096 讲 · 统计基础：分布、检验与相关性
与教程正文一一对应的示例代码

课程页面：/data-ai/statistics
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/096-statistics.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/096-statistics.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# mean 22.8
# median 14.5
# stdev 27.149
# pstdev 25.756
# q1 q2 q3 [13.75, 14.5, 15.25]
# fences 11.5 17.5
# outliers [100]

import statistics as st
data = [12, 15, 14, 16, 15, 100, 13, 14, 15, 14]
print('mean', st.mean(data))
print('median', st.median(data))
print('stdev', round(st.stdev(data), 3))
print('pstdev', round(st.pstdev(data), 3))
q = st.quantiles(data, n=4)
print('q1 q2 q3', q)
iqr = q[2] - q[0]
lo, hi = q[0] - 1.5 * iqr, q[2] + 1.5 * iqr
print('fences', round(lo, 1), round(hi, 1))
print('outliers', [x for x in data if x < lo or x > hi])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# population mean 50.5
# population pstdev 28.866
# means mean 50.399
# means stdev 5.358
# predicted SE 5.27

import random, statistics as st
random.seed(7)
pop = list(range(1, 101))
means = [st.mean(random.choices(pop, k=30)) for _ in range(2000)]
print('population mean', st.mean(pop))
print('population pstdev', round(st.pstdev(pop), 3))
print('means mean', round(st.mean(means), 3))
print('means stdev', round(st.stdev(means), 3))
print('predicted SE', round(st.pstdev(pop) / (30 ** 0.5), 3))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# r(ice, drown) 1.0
# alpha .05 x20 false-positive 0.642

def pearson(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = sum((a - mx) ** 2 for a in x) ** 0.5
    dy = sum((b - my) ** 2 for b in y) ** 0.5
    return round(num / (dx * dy), 4)

t = list(range(1, 11))
ice = [20 + 3 * i for i in t]
drown = [5 + 2 * i for i in t]
print('r(ice, drown)', pearson(ice, drown))
print('alpha .05 x20 false-positive', round(1 - 0.95 ** 20, 3))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import statistics as st

def explore(sample):
    q = st.quantiles(sample, n=4)
    iqr = q[2] - q[0]
    lo, hi = q[0] - 1.5 * iqr, q[2] + 1.5 * iqr
    outliers = [x for x in sample if x < lo or x > hi]
    se = st.stdev(sample) / (len(sample) ** 0.5)
    mean = st.mean(sample)
    return {
        'n': len(sample),
        'mean': round(mean, 2),
        'median': st.median(sample),
        'stdev': round(st.stdev(sample), 2),
        'outliers': len(outliers),
        'se': round(se, 2),
        'ci95': [round(mean - 1.96 * se, 2), round(mean + 1.96 * se, 2)],
    }

sample = [12, 15, 14, 16, 15, 13, 14, 15, 14, 16, 13, 15, 100]
print(explore(sample))
