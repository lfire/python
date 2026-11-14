"""
第 095 讲 · 可视化：Matplotlib / Seaborn / Plotly 与图表选型
与教程正文一一对应的示例代码

课程页面：/data-ai/visualization
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/095-visualization.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/095-visualization.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# 一季度 | ############# 120
# 二季度 | #################### 180
# 三季度 | ########### 95

def bars(values, labels, width=20):
    top = max(values)
    out = []
    for lab, v in zip(labels, values):
        n = round(v / top * width)
        out.append(lab + ' | ' + '#' * n + ' ' + str(v))
    return chr(10).join(out)

data = [('一季度', 120), ('二季度', 180), ('三季度', 95)]
print(bars([v for _, v in data], [l for l, _ in data]))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# bins 1-3/4-6/7-9/10-12 [6, 3, 4, 1]
# total 14 n 14

data = [1, 2, 2, 3, 3, 3, 4, 5, 5, 7, 8, 9, 9, 10]
bins = [0] * 4
for v in data:
    bins[min(3, (v - 1) // 3)] += 1
print('bins 1-3/4-6/7-9/10-12', bins)
print('total', sum(bins), 'n', len(data))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# from zero [0.92, 0.96, 1.0]
# truncated at 90 [0.2, 0.6, 1.0]
# ratio gap zero 0.08 gap truncated 0.8

vals = [92, 96, 100]
print('from zero', [round(v / 100, 2) for v in vals])
print('truncated at 90', [round((v - 90) / 10, 2) for v in vals])
print('ratio gap zero', round((100 - 92) / 100, 2), 'gap truncated', round((100 - 92) / 10, 2))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

def build_bars(records, width=40):
    values = [v for _, v in records]
    top = max(values)
    assert min(values) >= 0, 'bar baseline must be zero'
    lines = []
    for label, v in records:
        length = round(v / top * width)
        lines.append(label + ' | ' + '#' * length + ' ' + str(v))
    return lines

def caption(records):
    vals = [v for _, v in records]
    n = sum(vals)
    ratio = round(max(vals) / min(vals), 2)
    return 'n=' + str(len(vals)) + ' total=' + str(n) + ' max/min=' + str(ratio)

records = [('A 产品', 96), ('B 产品', 100), ('C 产品', 98)]
for line in build_bars(records):
    print(line)
print(caption(records))
