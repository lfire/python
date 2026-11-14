"""
第 032 讲 · 装饰器原理与 functools.wraps
与教程正文一一对应的示例代码

课程页面：/functions/decorator
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/032-decorator.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/032-decorator.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# wrapper (*args, **kwargs)
# volume (w, h, d)
# False True
# (*args, **kwargs)
# 6 24

from functools import wraps
import inspect

def log_bad(fn):
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

def log_good(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper

def area(w, h):
    return w * h
def volume(w, h, d):
    return w * h * d

bad = log_bad(area)
good = log_good(volume)
print(bad.__name__, inspect.signature(bad))
print(good.__name__, inspect.signature(good))
print(hasattr(bad, '__wrapped__'), hasattr(good, '__wrapped__'))
print(inspect.signature(good, follow_wrapped=False))
print(bad(2, 3), good(2, 3, 4))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# ['task']
# job
# 2 4 2

from functools import wraps

events = []
def register(name):
    def deco(fn):
        events.append(name)
        @wraps(fn)
        def wrapper(*a, **k):
            return fn(*a, **k)
        return wrapper
    return deco

def counted(fn):
    n = 0
    @wraps(fn)
    def wrapper(*a, **k):
        nonlocal n
        n += 1
        wrapper.calls = n
        return fn(*a, **k)
    wrapper.calls = 0
    return wrapper

@register('task')
def job(x):
    return x + 1

@counted
def work(x):
    return x * 2

print(events)
print(job.__name__)
print(work(1), work(2), work.calls)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# orig (x)
# True
# True
# True True

import inspect, functools
from functools import wraps

def deco(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        return fn(*a, **k)
    return wrapper

def orig(x):
    return x

w = deco(orig)
print(w.__name__, inspect.signature(w))
print('__wrapped__' in w.__dict__)
print(inspect.unwrap(w) is orig)
print('__name__' in functools.WRAPPER_ASSIGNMENTS, '__doc__' in functools.WRAPPER_ASSIGNMENTS)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import time
from functools import wraps

def timed(enabled=True):
    def deco(fn):
        if not enabled:
            return fn
        @wraps(fn)
        def wrapper(*a, **k):
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                wrapper.last_ms = (time.perf_counter() - t0) * 1000
        wrapper.last_ms = 0.0
        return wrapper
    return deco

@timed()
def fetch(n):
    return sum(range(n))

print(fetch.__name__, fetch(1000))
print(fetch.last_ms >= 0, fetch.__wrapped__(1000))

@timed(False)
def raw(x):
    return x
print(type(raw).__name__, raw(9), hasattr(raw, '__wrapped__'))
