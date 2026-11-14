"""
第 093 讲 · NumPy 向量化、广播与内存布局
与教程正文一一对应的示例代码

课程页面：/data-ai/numpy
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/093-numpy.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/093-numpy.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# (3, 1) + (1, 4) -> (3, 4)
# (2, 3) + (3,) -> (2, 3)
# (2, 3) + (2,) -> None
# (5, 4) + (3, 4) -> None

def broadcast_shape(a, b):
    out = []
    i, j = len(a) - 1, len(b) - 1
    while i >= 0 or j >= 0:
        da = a[i] if i >= 0 else 1
        db = b[j] if j >= 0 else 1
        if da == db or da == 1 or db == 1:
            out.append(max(da, db))
        else:
            return None
        i -= 1; j -= 1
    return tuple(reversed(out))

pairs = [((3, 1), (1, 4)), ((2, 3), (3,)), ((2, 3), (2,)), ((5, 4), (3, 4))]
for a, b in pairs:
    print(a, '+', b, '->', broadcast_shape(a, b))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# row [4, 5, 6, 7]
# after [4, 99, 6, 7]

class View:
    def __init__(self, data, shape, strides, offset=0):
        self.data, self.shape, self.strides, self.offset = data, shape, strides, offset
    def get(self, idx):
        addr = self.offset + sum(i * s for i, s in zip(idx, self.strides))
        return self.data[addr]

base = list(range(12))
row = View(base, (4,), (1,), offset=4)
print('row', [row.get((j,)) for j in range(4)])
base[5] = 99
print('after', [row.get((j,)) for j in range(4)])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# list container 120 one float 24
# array container 128 itemsize 8
# list per element 44

import sys, array
lst = [float(i) for i in range(6)]
arr = array.array('d', lst)
print('list container', sys.getsizeof(lst), 'one float', sys.getsizeof(lst[0]))
print('array container', sys.getsizeof(arr), 'itemsize', arr.itemsize)
print('list per element', (sys.getsizeof(lst) + 6 * sys.getsizeof(lst[0])) // 6)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

def transform(batch, mean, gain, bias):
    scaled = [gain * (x - mean) + bias for x in batch]
    clipped = [0 if v < 0 else 255 if v > 255 else v for v in scaled]
    return clipped

def summarize(batch, mean=100.0, gain=1.2, bias=10.0):
    out = transform(batch, mean, gain, bias)
    low = sum(1 for v in out if v == 0)
    high = sum(1 for v in out if v == 255)
    return {'count': len(out), 'low_clip': low, 'high_clip': high,
            'first': round(out[0], 1), 'mean': round(sum(out) / len(out), 1)}

pixels = [float((i * 7) % 256) for i in range(600)]
print(summarize(pixels))
print('same length', len(transform(pixels, 100, 1.2, 10)) == len(pixels))
