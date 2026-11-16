"""
第 119 讲 · 极致优化：从剖析到 C 扩展的十倍案例
与教程正文一一对应的示例代码

课程页面：/advanced/optimization
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/119-optimization.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/119-optimization.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# counts 667 667
# equal True
# set_is_faster True

import time

data = list(range(2000))
targets = list(range(0, 2000, 3))

def naive(xs, ys):
    out = 0
    for x in xs:
        for y in ys:
            if x == y:
                out += 1
                break
    return out

def with_set(xs, ys):
    s = set(ys)
    return sum(1 for x in xs if x in s)

t0 = time.perf_counter(); a = naive(data, targets); t1 = time.perf_counter()
t2 = time.perf_counter(); b = with_set(data, targets); t3 = time.perf_counter()
print('counts', a, b)
print('equal', a == b)
print('set_is_faster', (t3 - t2) < (t1 - t0))

# ======================== 2. 对照写法 ========================
# 预期输出：
# equal True
# builtin_faster True
# values 499999500000

import time

data = list(range(1000000))
t0 = time.perf_counter(); a = sum(data); t1 = time.perf_counter()
t2 = time.perf_counter()
b = 0
for x in data:
    b += x
t3 = time.perf_counter()
print('equal', a == b)
print('builtin_faster', (t1 - t0) < (t3 - t2))
print('values', a)

# ======================== 3. 原理验证 ========================
# 预期输出：
# result 2666466670000
# has_work True
# has_genexpr True

import cProfile, pstats, io

def work():
    return sum(i * i for i in range(20000))

pr = cProfile.Profile()
pr.enable(); v = work(); pr.disable()
s = io.StringIO()
pstats.Stats(pr, stream=s).strip_dirs().sort_stats('cumtime').print_stats()
text = s.getvalue()
print('result', v)
print('has_work', 'work' in text)
print('has_genexpr', 'genexpr' in text)

# ======================== 4. 工程案例 ========================

import time, cProfile, pstats, io

def measure(name, fn):
    t0 = time.perf_counter()
    r = fn()
    return name, r, (time.perf_counter() - t0) * 1000

data = list(range(20000))
targets = set(range(0, 20000, 3))

def loop_version():
    return sum(1 for x in data if x in targets)

def set_version():
    return len(set(data) & targets)

results = [measure('loop', loop_version), measure('set', set_version)]
for name, r, ms in results:
    print(name, r, round(ms, 3))
print('equal', results[0][1] == results[1][1])

pr = cProfile.Profile()
pr.enable(); loop_version(); pr.disable()
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats('cumtime').print_stats(3)
print('profile_has_loop', 'loop_version' in s.getvalue())
