"""
第 047 讲 · dataclass、attrs 与 pydantic 模型
与教程正文一一对应的示例代码

课程页面：/oop/dataclass
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/047-dataclass.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/047-dataclass.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# eq True lt True
# hash True
# repr Item(name='pen', qty=2)
# post [] 2
# FrozenInstanceError

from dataclasses import dataclass, field, FrozenInstanceError

@dataclass(frozen=True, order=True)
class Item:
    name: str
    qty: int = 0
    tags: list = field(default_factory=list, repr=False, compare=False)

a = Item('pen', 2)
b = Item('pen', 2)
print('eq', a == b, 'lt', Item('pen', 1) < a)
print('hash', hash(a) == hash(b))
print('repr', repr(a))
print('post', a.tags, a.qty)
try:
    a.qty = 9
except FrozenInstanceError as e:
    print(type(e).__name__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# asdict {'items': ['x']}
# replace Bag(items=['y'])
# ValueError mutable default

from dataclasses import dataclass, field, asdict, replace

@dataclass
class Bag:
    items: list = field(default_factory=list)

b = Bag()
b.items.append('x')
print('asdict', asdict(b))
print('replace', replace(b, items=['y']))
try:
    @dataclass
    class Bad:
        items: list = []
except ValueError as e:
    print(type(e).__name__, 'mutable default')

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# generated: ['__init__', '__repr__', '__eq__']
# hash plain: None
# hash frozen: True
# field names: ['x']
# params: ['init', 'repr', 'eq']

from dataclasses import dataclass, fields
import inspect

@dataclass
class Plain:
    x: int
@dataclass(frozen=True)
class Frozen:
    x: int

print('generated:', [n for n in ('__init__', '__repr__', '__eq__') if n in Plain.__dict__])
print('hash plain:', Plain.__hash__)
print('hash frozen:', Frozen.__hash__ is not None)
print('field names:', [f.name for f in fields(Plain)])
print('params:', [p for p in inspect.signature(dataclass).parameters if p in ('init', 'repr', 'eq')])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    host: str
    port: int
    retries: int = 3

def validate(raw):
    errors = []
    port = raw.get('port')
    if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
        errors.append('port must be int in 1..65535')
    host = raw.get('host')
    if not isinstance(host, str) or not host:
        errors.append('host must be non-empty str')
    if errors:
        raise ValueError('; '.join(errors))
    return Config(host=host, port=port, retries=raw.get('retries', 3))

print(validate({'host': 'db.local', 'port': 5432}))
for bad in [{'host': '', 'port': 5432}, {'host': 'x', 'port': 70000}, {'host': 'x', 'port': '80'}]:
    try:
        validate(bad)
    except ValueError as e:
        print('rejected:', str(e))
print('frozen value:', validate({'host': 'h', 'port': 80}).port)
