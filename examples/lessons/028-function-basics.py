"""
第 028 讲 · 函数定义与参数形态
与教程正文一一对应的示例代码

课程页面：/functions/function-basics
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/028-function-basics.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/028-function-basics.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# ('db.local', 5432, 2.0, 5, {'ssl': True})
# host POSITIONAL_ONLY no-default
# port POSITIONAL_ONLY no-default
# timeout POSITIONAL_OR_KEYWORD 1.0
# retries KEYWORD_ONLY 3
# options VAR_KEYWORD no-default

import inspect

def connect(host, port, /, timeout=1.0, *, retries=3, **options):
    return (host, port, timeout, retries, options)

sig = inspect.signature(connect)
print(connect('db.local', 5432, 2.0, retries=5, ssl=True))
for name, p in sig.parameters.items():
    default = 'no-default' if p.default is inspect.Parameter.empty else repr(p.default)
    print(name, p.kind.name, default)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# ([],)
# ['a', 'b'] ['a', 'b'] True
# (['a', 'b'],)
# ['a'] ['b']

def add(item, seen=[]):
    seen.append(item)
    return seen

print(add.__defaults__)
r1 = add('a')
r2 = add('b')
print(r1, r2, r1 is r2)
print(add.__defaults__)

def add2(item, seen=None):
    if seen is None:
        seen = []
    seen.append(item)
    return seen
print(add2('a'), add2('b'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# (1,) {'c': 2}
# 2 0 1 8
# {'a': 9, 'c': 7, 'kw': {'x': 1}}
# True True

import inspect, dis

def f(a, b=1, *, c=2, **kw):
    return a + b + c

cd = f.__code__
print(f.__defaults__, f.__kwdefaults__)
print(cd.co_argcount, cd.co_posonlyargcount, cd.co_kwonlyargcount, cd.co_flags & 0x08)
print(inspect.signature(f).bind(9, c=7, x=1).arguments)
ops = [i.opname for i in dis.get_instructions(f)]
print('RETURN_VALUE' in ops, len(ops) > 0)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import inspect

def query(page, size, /, *, timeout=1.0, retries=3):
    return {'page': page, 'size': size, 'timeout': timeout, 'retries': retries}

sig = inspect.signature(query)

def safe_call(*args, **kwargs):
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    return query(*bound.args, **bound.kwargs)

print(safe_call(1, 20))
print(safe_call(1, 20, timeout=2.5))
try:
    safe_call(1, size=20)
except TypeError as e:
    print(type(e).__name__, str(e))
