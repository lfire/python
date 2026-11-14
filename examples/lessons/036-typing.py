"""
第 036 讲 · 类型注解、typing 与渐进式类型
与教程正文一一对应的示例代码

课程页面：/functions/typing
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/036-typing.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/036-typing.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# ['a', 'b', 'return']
# ['int', 'int', 'float']
# True
# int | None
# True

import typing
from typing import get_type_hints

def distance(a: int, b: int = 0) -> float:
    return float(a - b)

h = get_type_hints(distance)
print(sorted(h))
print([h[k].__name__ for k in ('a', 'b', 'return')])
print(distance.__annotations__['a'] is int)
print(str(int | None))
print(get_type_hints(distance) == distance.__annotations__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# True
# {'host': <class 'str'>, 'port': <class 'int'>}
# ['host', 'port']
# typing.Literal['r', 'w']
# False

from typing import Protocol, runtime_checkable, TypedDict, Literal, TYPE_CHECKING

@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...

class Config(TypedDict):
    host: str
    port: int

Mode = Literal['r', 'w']

class File:
    def close(self) -> None:
        pass

print(isinstance(File(), Closeable))
print(Config.__annotations__)
print(sorted(Config.__required_keys__))
print(Mode)
print(TYPE_CHECKING)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# {'a': <class 'int'>, 'return': <class 'int'>}
# True
# False True {'x': <class 'int'>}
# ['RETURN_VALUE']

import dis

def f(a: int) -> int:
    return a

print(f.__annotations__)
print('a' in f.__code__.co_varnames)
src = 'x: int'
ns = {}
exec(compile(src, '<s>', 'exec'), ns)
print('x' in ns, '__annotations__' in ns, ns['__annotations__'])
print([i.opname for i in dis.get_instructions(f) if i.opname == 'RETURN_VALUE'])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from typing import TypedDict, Literal, get_type_hints

class Event(TypedDict):
    kind: Literal['click', 'view']
    user_id: int
    ts: float

def validate(raw):
    hints = get_type_hints(Event)
    if set(raw) != set(hints):
        return 'bad keys'
    if raw['kind'] not in ('click', 'view'):
        return 'bad kind'
    if not isinstance(raw['user_id'], int):
        return 'bad user_id'
    return 'ok'

print(validate({'kind': 'click', 'user_id': 7, 'ts': 1.0}))
print(validate({'kind': 'buy', 'user_id': 7, 'ts': 1.0}))
print(validate({'kind': 'click', 'user_id': '7', 'ts': 1.0}))
print(sorted(get_type_hints(Event)))
