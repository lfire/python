"""
第 118 讲 · GIL 源码、自适应解释器与无 GIL 路线
与教程正文一一对应的示例代码

课程页面：/advanced/gil-source
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/118-gil-source.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/118-gil-source.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# gil_enabled True
# switch_interval 0.005
# has_adaptive True
# co_code_len 22
# both_run True
#   6           RESUME                   0
# 
#   7           LOAD_FAST_LOAD_FAST      0 (x, x)
#               BINARY_OP                0 (+)
#               CACHE                    0 (counter: 0)
#               LOAD_FAST                0 (x)
#               BINARY_OP                0 (+)
#               CACHE                    0 (counter: 0)
#               LOAD_FAST                0 (x)
#               BINARY_OP                0 (+)
#               CACHE                    0 (counter: 0)
#               RETURN_VALUE

import sys, dis, time

print('gil_enabled', sys._is_gil_enabled())
print('switch_interval', sys.getswitchinterval())

def hot(x):
    return x + x + x + x

print('has_adaptive', hasattr(hot.__code__, '_co_code_adaptive'))
print('co_code_len', len(hot.__code__.co_code))

def bench():
    t0 = time.perf_counter()
    for i in range(200000):
        hot(i)
    return time.perf_counter() - t0

a = bench(); b = bench()
print('both_run', a > 0 and b > 0)
dis.dis(hot, show_caches=True)

# ======================== 2. 对照写法 ========================
# 预期输出：
# main_gil True
# worker_gil True
# switch_set 0.001
# switch_restored 0.005

import sys, threading

result = []
def worker():
    result.append(sys._is_gil_enabled())

t = threading.Thread(target=worker)
t.start(); t.join()
print('main_gil', sys._is_gil_enabled())
print('worker_gil', result[0])
sys.setswitchinterval(0.001)
print('switch_set', sys.getswitchinterval())
sys.setswitchinterval(0.005)
print('switch_restored', sys.getswitchinterval())

# ======================== 3. 原理验证 ========================
# 预期输出：
# specialized_load_attr True
# cache_lines 9
# has_adaptive True

import dis, io

def read_attr(o):
    return o.value

class C:
    def __init__(self):
        self.value = 7

obj = C()
for _ in range(200):
    read_attr(obj)

buf = io.StringIO()
dis.dis(read_attr, file=buf, show_caches=True, adaptive=True)
text = buf.getvalue()
print('specialized_load_attr', 'INSTANCE_VALUE' in text or 'LOAD_ATTR_SLOT' in text)
print('cache_lines', text.count('CACHE'))
print('has_adaptive', hasattr(read_attr.__code__, '_co_code_adaptive'))

# ======================== 4. 工程案例 ========================

import sys, time, timeit

def context():
    print('py', sys.version_info[0], sys.version_info[1])
    print('tag', sys.implementation.cache_tag)
    print('gil_enabled', sys._is_gil_enabled())
    print('switch', sys.getswitchinterval())

def hot(x):
    return x + x + x + x

def bench(repeat=5, number=50000):
    for _ in range(2):
        timeit.timeit(lambda: hot(3), number=number)
    ts = [timeit.timeit(lambda: hot(3), number=number) for _ in range(repeat)]
    print('has_adaptive', hasattr(hot.__code__, '_co_code_adaptive'))
    print('min_seconds', round(min(ts), 6))

context()
bench()
