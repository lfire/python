"""
第 033 讲 · 带参装饰器、叠加顺序与类装饰器
与教程正文一一对应的示例代码

课程页面：/functions/decorator-params
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/033-decorator-params.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/033-decorator-params.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# enter outer
# enter inner
# run 1
# exit inner
# exit outer
# 2
# work

from functools import wraps

def tag(label):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **k):
            print('enter', label)
            r = fn(*a, **k)
            print('exit', label)
            return r
        return wrapper
    return deco

@tag('outer')
@tag('inner')
def work(x):
    print('run', x)
    return x + 1

print(work(1))
print(work.__name__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# 3 7 2 add
# function 9 False

from functools import update_wrapper

class Count:
    def __init__(self, fn):
        self.fn = fn
        self.calls = 0
        update_wrapper(self, fn)
    def __call__(self, *a, **k):
        self.calls += 1
        return self.fn(*a, **k)

@Count
def add(a, b):
    return a + b

print(add(1, 2), add(3, 4), add.calls, add.__name__)

def maybe(enabled):
    def deco(fn):
        return fn if not enabled else Count(fn)
    return deco

@maybe(False)
def raw(x):
    return x
print(type(raw).__name__, raw(9), hasattr(raw, '__wrapped__'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# f (x)
# 2 True
# True
# True function

import inspect
from functools import wraps

def deco(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        return fn(*a, **k)
    return wrapper

def f(x):
    return x

stacked = deco(deco(f))
print(stacked.__name__, inspect.signature(stacked))
n = 0
cur = stacked
while hasattr(cur, '__wrapped__'):
    n += 1
    cur = cur.__wrapped__
print(n, cur is f)
print(inspect.unwrap(stacked) is f)
print(callable(stacked), type(stacked).__name__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from functools import wraps

def auth(ok=True):
    def deco(fn):
        @wraps(fn)
        def wrapper(user, *a, **k):
            if not ok or user != 'admin':
                return 'denied'
            return fn(user, *a, **k)
        return wrapper
    return deco

def cache(enabled=True):
    def deco(fn):
        store = {}
        @wraps(fn)
        def wrapper(*a, **k):
            if not enabled:
                return fn(*a, **k)
            key = (a, tuple(sorted(k.items())))
            if key not in store:
                store[key] = fn(*a, **k)
            return store[key]
        return wrapper
    return deco

@auth()
@cache()
def report(user):
    return 'secret-data'

print(report('admin'))
print(report('guest'))
print(report('admin'))
print(report.__name__)
