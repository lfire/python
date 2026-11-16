"""
第 074 讲 · 静态检查：mypy / pyright 与渐进式类型
与教程正文一一对应的示例代码

课程页面：/engineering/typecheck
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/074-typecheck.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/074-typecheck.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# hints {'a': 'int', 'b': 'int', 'return': 'int'}
# signature (a: int, b: int) -> int
# isinstance generic raises TypeError True
# Any to int at runtime not an int

import typing, inspect

def add(a: int, b: int) -> int:
    return a + b

print('hints', {k: v.__name__ for k, v in typing.get_type_hints(add).items()})
print('signature', str(inspect.signature(add)))
try:
    isinstance([1, 2], list[int])
except TypeError as e:
    print('isinstance generic raises TypeError', 'generic' in str(e).lower())
x: typing.Any = 'not an int'
y: int = x
print('Any to int at runtime', y)

# ======================== 2. 对照写法 ========================
# 预期输出：
# stored as string True
# resolved hints {'x': 'int', 'return': 'str'}

import typing

ns = {}
exec('from __future__ import annotations' + chr(10)
     + 'def f(x: int) -> str:' + chr(10)
     + '    return str(x)', ns)
f = ns['f']
print('stored as string', isinstance(f.__annotations__['x'], str))
print('resolved hints', {k: getattr(v, '__name__', str(v)) for k, v in typing.get_type_hints(f).items()})

# ======================== 3. 原理验证 ========================
# 预期输出：
# origin list[int] list
# args list[int] ['int']
# Literal args ('a', 'b')
# Union pipe equals True
# python 3 13

import typing, sys

print('origin list[int]', typing.get_origin(list[int]).__name__)
print('args list[int]', [a.__name__ for a in typing.get_args(list[int])])
print('Literal args', typing.get_args(typing.Literal['a', 'b']))
print('Union pipe equals', (int | str) == typing.Union[int, str])
print('python', sys.version_info[0], sys.version_info[1])

# ======================== 4. 工程案例 ========================

import typing

def add(a: int, b: int) -> int:
    return a + b

def validate(func, data):
    hints = typing.get_type_hints(func)
    for name, value in data.items():
        expected = hints.get(name)
        if expected is int and not isinstance(value, int):
            raise TypeError(name + ' must be int, got ' + type(value).__name__)
    return func(**data)

print('static hints', {k: v.__name__ for k, v in typing.get_type_hints(add).items()})
print('valid call', validate(add, {'a': 2, 'b': 3}))
try:
    validate(add, {'a': '2', 'b': 3})
except TypeError as e:
    print('runtime guard', str(e))
print('annotation not enforced', add('x', 'y'))
