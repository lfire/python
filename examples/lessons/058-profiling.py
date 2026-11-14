"""
第 058 讲 · 性能剖析：timeit、cProfile 与 tracemalloc
与教程正文一一对应的示例代码

课程页面：/core/profiling
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/058-profiling.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/058-profiling.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# wall > cpu True
# sleep dominates True
# rounds 5 min_le_mean True

import time
import timeit

def mixed():
    time.sleep(0.05)
    return sum(range(1000))

t0 = time.perf_counter()
c0 = time.process_time()
mixed()
wall = time.perf_counter() - t0
cpu = time.process_time() - c0
print('wall > cpu', wall > cpu)
print('sleep dominates', wall - cpu > cpu)
samples = timeit.repeat('sum(range(1000))', number=500, repeat=5)
print('rounds', len(samples), 'min_le_mean', min(samples) <= sum(samples) / len(samples))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# driver tracked True
# hot tracked True
# genexpr tracked True
# total_calls_positive True
# sort key cumulative

import cProfile
import pstats
import io

def hot(n):
    return sum(i * i for i in range(n))

def driver():
    return hot(5000) + hot(5000)

pr = cProfile.Profile()
pr.enable()
driver()
pr.disable()
buf = io.StringIO()
st = pstats.Stats(pr, stream=buf)
st.strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE)
st.print_stats()
text = buf.getvalue()
print('driver tracked', 'driver' in text)
print('hot tracked', 'hot' in text)
print('genexpr tracked', 'genexpr' in text)
print('total_calls_positive', st.total_calls > 0)
print('sort key', pstats.SortKey.CUMULATIVE.value)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# peak >= current True
# diff rows > 0 True
# top size_diff >= 0 True
# traced bytes > 0 True

import tracemalloc

def build(n):
    return [dict(i=i, sq=i * i) for i in range(n)]

tracemalloc.start(1)
snap0 = tracemalloc.take_snapshot()
cache = build(2000)
snap1 = tracemalloc.take_snapshot()
current, peak = tracemalloc.get_traced_memory()
print('peak >= current', peak >= current)
diff = snap1.compare_to(snap0, 'lineno')
print('diff rows > 0', len(diff) > 0)
print('top size_diff >= 0', diff[0].size_diff >= 0)
print('traced bytes > 0', current > 0)
tracemalloc.stop()

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import cProfile
import io
import pstats
import time
import tracemalloc

def parse(rows):
    return [r.strip().split(',') for r in rows]

def aggregate(rows):
    total = 0
    for parts in parse(rows):
        total += len(parts)
    return total

ROWS = ['a,b,c', 'd,e', 'f,g,h,i'] * 4000

if __name__ == '__main__':
    t0 = time.perf_counter()
    c0 = time.process_time()
    result = aggregate(ROWS)
    print('result', result, 'wall', round(time.perf_counter() - t0, 4),
          'cpu', round(time.process_time() - c0, 4))
    pr = cProfile.Profile()
    pr.enable()
    aggregate(ROWS)
    pr.disable()
    buf = io.StringIO()
    pstats.Stats(pr, stream=buf).sort_stats('cumulative').print_stats(3)
    print('top funcs', [ln.strip().split()[-1] for ln in buf.getvalue().splitlines()
                      if 'function calls' not in ln and ln.strip()][-3:])
    tracemalloc.start()
    s0 = tracemalloc.take_snapshot()
    aggregate(ROWS)
    s1 = tracemalloc.take_snapshot()
    print('alloc rows', len(s1.compare_to(s0, 'lineno')) > 0)
    tracemalloc.stop()
