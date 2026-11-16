"""
第 046 讲 · 反射与自省：getattr、inspect 与 __dict__
与教程正文一一对应的示例代码

课程页面：/oop/introspection
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/046-introspection.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/046-introspection.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# getattr 1.0 default
# hasattr True False
# sig (n: int, flag: bool = False) -> str
# annotations {'n': <class 'int'>, 'flag': <class 'bool'>, 'return': <class 'str'>}
# members ['run']
# dict keys []

import inspect

class Service:
    version = '1.0'
    def run(self, n: int, flag: bool = False) -> str:
        return 'ok'

svc = Service()
print('getattr', getattr(svc, 'version'), getattr(svc, 'missing', 'default'))
print('hasattr', hasattr(svc, 'run'), hasattr(svc, 'missing'))
print('sig', str(inspect.signature(svc.run)))
print('annotations', svc.run.__annotations__)
print('members', sorted(k for k, _ in inspect.getmembers(svc) if k == 'run'))
print('dict keys', sorted(vars(svc).keys()))

# ======================== 2. 对照写法 ========================
# 预期输出：
# {"a": 1}
# blocked: not allowed: rmtree

import importlib

ALLOWED = {'dumps': 'json', 'loads': 'json'}
def call(name, *args):
    if name not in ALLOWED:
        raise ValueError('not allowed: ' + name)
    mod = importlib.import_module(ALLOWED[name])
    return getattr(mod, name)(*args)

print(call('dumps', {'a': 1}))
try:
    call('rmtree', '/tmp')
except ValueError as e:
    print('blocked:', str(e))

# ======================== 3. 原理验证 ========================
# 预期输出：
# hasattr broken: False
# in dict: False
# isfunction: True
# raw: {'x': 'int', 'y': <class 'list'>, 'return': 'dict'}
# hints: {'x': <class 'int'>, 'y': <class 'list'>, 'return': <class 'dict'>}

from typing import get_type_hints
import inspect

class Trap:
    @property
    def broken(self):
        raise AttributeError('boom')

t = Trap()
print('hasattr broken:', hasattr(t, 'broken'))
print('in dict:', 'broken' in vars(t))

def f(x: 'int', y: list = None) -> 'dict':
    pass
print('isfunction:', inspect.isfunction(f))
print('raw:', f.__annotations__)
print('hints:', get_type_hints(f))

# ======================== 4. 工程案例 ========================

import inspect

class Commands:
    def add(self, a: int, b: int) -> int:
        return a + b
    def echo(self, text: str) -> str:
        return text

ROUTER = Commands()
ROUTE = {'add': Commands.add, 'echo': Commands.echo}
def dispatch(name, **kwargs):
    if name not in ROUTE:
        raise KeyError('unknown command: ' + name)
    fn = ROUTE[name]
    sig = inspect.signature(fn)
    bound = sig.bind(ROUTER, **kwargs)
    return fn(*bound.args, **bound.kwargs)

print('add:', dispatch('add', a=2, b=3))
print('echo:', dispatch('echo', text='hi'))
try:
    dispatch('add', a=1)
except TypeError as e:
    print(type(e).__name__, 'missing arg')
try:
    dispatch('delete', a=1)
except KeyError:
    print('KeyError', 'rejected')
