"""
第 100 讲 · 集成学习：Boosting、XGBoost 与 LightGBM
与教程正文一一对应的示例代码

课程页面：/data-ai/ensemble
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/100-ensemble.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/100-ensemble.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# round 1 threshold 3.5 mse 11.947
# round 2 threshold 2.5 mse 3.328
# round 3 threshold 5.5 mse 1.191

xs = [1, 2, 3, 4, 5, 6]
y = [2, 4, 6, 8, 10, 12]
def stump(resid):
    best = None
    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:
        li = [i for i, x in enumerate(xs) if x <= t]
        ri = [i for i, x in enumerate(xs) if x > t]
        lv = sum(resid[i] for i in li) / len(li)
        rv = sum(resid[i] for i in ri) / len(ri)
        err = sum((resid[i] - lv) ** 2 for i in li) + sum((resid[i] - rv) ** 2 for i in ri)
        if best is None or err < best[0]:
            best = (err, t, li, ri, lv, rv)
    return best
lr = 0.6
F = [0.0] * len(xs)
for m in range(1, 4):
    resid = [yi - fi for yi, fi in zip(y, F)]
    err, t, li, ri, lv, rv = stump(resid)
    h = [lv if i in li else rv for i in range(len(xs))]
    F = [fi + lr * hi for fi, hi in zip(F, h)]
    mse = sum((a - b) ** 2 for a, b in zip(y, F)) / len(y)
    print('round', m, 'threshold', t, 'mse', round(mse, 3))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# lr=0.8 x3 [4.99, 1.81, 0.82]
# lr=0.2 x12 [39.79, 26.42, 17.51, 11.77, 8.02, 5.51, 3.85, 2.67, 1.91, 1.35, 0.98, 0.71]

def boost(lr, rounds):
    F = [0.0] * len(xs)
    out = []
    for _ in range(rounds):
        resid = [yi - fi for yi, fi in zip(y, F)]
        err, t, li, ri, lv, rv = stump(resid)
        h = [lv if i in li else rv for i in range(len(xs))]
        F = [fi + lr * hi for fi, hi in zip(F, h)]
        out.append(round(sum((a - b) ** 2 for a, b in zip(y, F)) / len(y), 2))
    return out
print('lr=0.8 x3', boost(0.8, 3))
print('lr=0.2 x12', boost(0.2, 12))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# exact split candidates 999999
# histogram candidates 254
# ratio 3937

n_samples = 1000000
n_bins = 255
print('exact split candidates', n_samples - 1)
print('histogram candidates', n_bins - 1)
print('ratio', round((n_samples - 1) / (n_bins - 1)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

xs = [1, 2, 3, 4, 5, 6]
y = [2, 4, 6, 8, 10, 12]
val_x = [1.5, 3.5, 5.5]
val_y = [3.0, 7.0, 11.0]

def fit_stump(resid):
    best = None
    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:
        lo = [resid[i] for i, x in enumerate(xs) if x <= t]
        hi = [resid[i] for i, x in enumerate(xs) if x > t]
        lv, rv = sum(lo) / len(lo), sum(hi) / len(hi)
        err = sum((v - lv) ** 2 for v in lo) + sum((v - rv) ** 2 for v in hi)
        if best is None or err < best[0]: best = (err, t, lv, rv)
    return best

lr, rounds_used = 0.6, []
F = [0.0] * len(xs)
best_round, best_val, trace = 0, float('inf'), []
for m in range(1, 11):
    resid = [y[i] - F[i] for i in range(len(xs))]
    err, t, lv, rv = fit_stump(resid)
    rounds_used.append((t, lv, rv))
    F = [F[i] + lr * (lv if xs[i] <= t else rv) for i in range(len(xs))]
    def pred(x): return lr * sum((a if x <= c else b) for c, a, b in rounds_used)
    val_mse = sum((pred(vx) - vy) ** 2 for vx, vy in zip(val_x, val_y)) / len(val_x)
    trace.append(round(val_mse, 3))
    if val_mse < best_val: best_val, best_round = val_mse, m
print('val mse trajectory', trace)
print('best round', best_round, 'best val', round(best_val, 3))
