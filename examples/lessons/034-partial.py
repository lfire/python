"""
第 034 讲 · 偏函数、可调用对象与函数式工具
与教程正文一一对应的示例代码

课程页面：/functions/partial
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/034-partial.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/034-partial.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# 25 power () {'exp': 2}
# 27
# 55
# CacheInfo(hits=8, misses=11, maxsize=32, currsize=11)
# 0
# TypeError unhashable type: 'list'

from functools import partial, lru_cache

def power(base, exp):
    return base ** exp

square = partial(power, exp=2)
print(square(5), square.func.__name__, square.args, square.keywords)
print(square(3, exp=3))

@lru_cache(maxsize=32)
def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)

print(fib(10))
print(fib.cache_info())
fib.cache_clear()
print(fib.cache_info().currsize)
try:
    fib([1])
except TypeError as e:
    print(type(e).__name__, str(e))

# ======================== 2. 对照写法 ========================
# 预期输出：
# int: 3 list of 2 other: str
# True
# ['int', 'list', 'object']
# (1, 2, 3) (1, 2, 3) 1
# True True

from functools import singledispatch, cached_property

@singledispatch
def describe(x):
    return 'other: ' + type(x).__name__

@describe.register
def _(x: int):
    return 'int: ' + str(x)

@describe.register
def _(x: list):
    return 'list of ' + str(len(x))

print(describe(3), describe([1, 2]), describe('s'))
print(describe.dispatch(float) is describe.dispatch(object))
print(sorted(t.__name__ for t in describe.registry))

class Config:
    def __init__(self, raw):
        self.raw = raw
    @cached_property
    def parsed(self):
        self.builds = getattr(self, 'builds', 0) + 1
        return tuple(self.raw)

c = Config([1, 2, 3])
print(c.parsed, c.parsed, c.builds)
print('parsed' in c.__dict__, callable(describe))

# ======================== 3. 原理验证 ========================
# 预期输出：
# 3 3.0
# 0 2 {'maxsize': 8, 'typed': True}
# True 9
# {'base': 2}
# True True

import functools, inspect

@functools.lru_cache(maxsize=8, typed=True)
def f(x):
    return x

print(f(3), f(3.0))
print(f.cache_info().hits, f.cache_info().misses, f.cache_parameters())
print(inspect.isfunction(f.__wrapped__), f.__wrapped__(9))
print(functools.partial(int, base=2).keywords)
print(callable(f), callable(functools.partial(int, base=2)))

# ======================== 4. 工程案例 ========================

from functools import partial, lru_cache

def fetch(url, timeout, retries):
    return url + ' t=' + str(timeout) + ' r=' + str(retries)

fetch_short = partial(fetch, timeout=1, retries=2)
print(fetch_short('/a'))
print(fetch_short('/b', retries=5))

@lru_cache(maxsize=64)
def parse_key(key):
    return tuple(int(p) for p in key.split('.'))

print(parse_key('1.2.3'))
print(parse_key('1.2.3'))
print(parse_key.cache_info().hits)
parse_key.cache_clear()
print(parse_key.cache_info().currsize)
