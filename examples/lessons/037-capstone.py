"""
第 037 讲 · 阶段综合：缓存装饰器库与插件注册表
与教程正文一一对应的示例代码

课程页面：/functions/capstone
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/037-capstone.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/037-capstone.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# 6 6
# 1 {'hit': 1, 'miss': 1, 'size': 1}
# 6 2

import time, threading
from functools import wraps

def cache(ttl, clock=time.monotonic):
    def deco(fn):
        store = {}
        lock = threading.RLock()
        hits = {'hit': 0, 'miss': 0}
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = clock()
            with lock:
                item = store.get(key)
                if item and now < item[0]:
                    hits['hit'] += 1
                    return item[1]
                hits['miss'] += 1
                value = fn(*args, **kwargs)
                store[key] = (now + ttl, value)
                return value
        wrapper.cache_clear = store.clear
        wrapper.cache_info = lambda: dict(hits, size=len(store))
        return wrapper
    return deco

calls = {'n': 0}
@cache(ttl=60)
def slow(x):
    calls['n'] += 1
    return x * 2

print(slow(3), slow(3))
print(calls['n'], slow.cache_info())
slow.cache_clear()
print(slow(3), calls['n'])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# 2 2 1
# 2 2
# ValueError neg
# 3

from functools import wraps

class Clock:
    def __init__(self):
        self.t = 0.0
    def __call__(self):
        return self.t
    def advance(self, dt):
        self.t += dt

clk = Clock()

def tcache(ttl, clock):
    def deco(fn):
        store = {}
        @wraps(fn)
        def wrapper(*a, **k):
            key = (a, tuple(sorted(k.items())))
            now = clock()
            if key in store and now < store[key][0]:
                return store[key][1]
            value = fn(*a, **k)
            store[key] = (now + ttl, value)
            return value
        return wrapper
    return deco

calls = []
@tcache(ttl=10, clock=clk)
def f(x):
    calls.append(x)
    if x < 0:
        raise ValueError('neg')
    return x + 1

print(f(1), f(1), len(calls))
clk.advance(11)
print(f(1), len(calls))
try:
    f(-1)
except ValueError as e:
    print(type(e).__name__, str(e))
print(len(calls))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# 1 10 build (k)

import threading, inspect
from functools import wraps

def locked_cache(fn):
    store = {}
    lock = threading.Lock()
    calls = {'n': 0}
    @wraps(fn)
    def wrapper(key):
        with lock:
            if key in store:
                return store[key]
            calls['n'] += 1
            store[key] = fn(key)
            return store[key]
    wrapper.calls = calls
    return wrapper

@locked_cache
def build(k):
    return k * 10

barrier = threading.Barrier(8)
def task():
    barrier.wait()
    return build(1)
ts = [threading.Thread(target=task) for _ in range(8)]
for t in ts: t.start()
for t in ts: t.join()
print(build.calls['n'], build(1), build.__name__, inspect.signature(build))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from functools import wraps

class Registry:
    def __init__(self):
        self._items = {}
    def register(self, name):
        def deco(fn):
            if name in self._items:
                raise KeyError('duplicate: ' + name)
            self._items[name] = fn
            @wraps(fn)
            def wrapper(*a, **k):
                return fn(*a, **k)
            return wrapper
        return deco
    def get(self, name):
        return self._items[name]
    def names(self):
        return sorted(self._items)
    def clear(self):
        self._items.clear()

plugins = Registry()

@plugins.register('upper')
def upper(s):
    return s.upper()

@plugins.register('reverse')
def reverse(s):
    return s[::-1]

print(plugins.names())
print(plugins.get('upper')('hi'))
try:
    @plugins.register('upper')
    def dup(s):
        return s
except KeyError as e:
    print(type(e).__name__, str(e))
plugins.clear()
print(plugins.names())
