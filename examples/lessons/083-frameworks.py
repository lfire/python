"""
第 083 讲 · FastAPI / Flask / Django 选型
与教程正文一一对应的示例代码

课程页面：/server/frameworks
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/083-frameworks.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/083-frameworks.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# name str required
# age int required
# active bool True

import inspect
from typing import get_type_hints

def create_user(name: str, age: int, active: bool = True):
    return {'name': name, 'age': age, 'active': active}

sig = inspect.signature(create_user)
hints = get_type_hints(create_user)
for pname, p in sig.parameters.items():
    ann = hints.get(pname)
    default = 'required' if p.default is inspect.Parameter.empty else str(p.default)
    print(pname, ann.__name__, default)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# {'name': 'ada', 'age': 36, 'active': True}
# {'name': 'ada', 'age': 36, 'active': False}
# error int coercion failed for age

from typing import get_type_hints
import inspect

def parse(fn, raw):
    hints = get_type_hints(fn)
    sig = inspect.signature(fn)
    out = {}
    for name, p in sig.parameters.items():
        t = hints.get(name)
        if name not in raw:
            if p.default is not inspect.Parameter.empty:
                out[name] = p.default
            else:
                raise ValueError('missing field ' + name)
        else:
            v = raw[name]
            if t is int:
                try:
                    out[name] = int(v)
                except (ValueError, TypeError):
                    raise ValueError('int coercion failed for ' + name)
            elif t is bool:
                out[name] = v if isinstance(v, bool) else str(v).lower() in ('1', 'true')
            else:
                out[name] = str(v)
    return out

def handler(name: str, age: int, active: bool = True):
    return (name, age, active)
print(parse(handler, {'name': 'ada', 'age': '36'}))
print(parse(handler, {'name': 'ada', 'age': '36', 'active': 'false'}))
try:
    parse(handler, {'name': 'ada', 'age': 'abc'})
except ValueError as e:
    print('error', str(e))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# flask_view params [] ann {}
# fastapi_view params ['name', 'age'] ann {'name': 'str', 'age': 'int'}
# django_view params ['request'] ann {}

import inspect

def flask_view():
    return None
def fastapi_view(name: str, age: int = 0):
    return (name, age)
def django_view(request):
    return request

for fn in (flask_view, fastapi_view, django_view):
    ann = {k: getattr(v, '__name__', str(v)) for k, v in fn.__annotations__.items()}
    print(fn.__name__, 'params', list(inspect.signature(fn).parameters), 'ann', ann)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

SCORES = {
    'Flask':   {'api': 2, 'admin': 2, 'realtime': 1, 'light': 5, 'decouple': 5, 'speed': 3},
    'FastAPI': {'api': 5, 'admin': 2, 'realtime': 5, 'light': 3, 'decouple': 4, 'speed': 4},
    'Django':  {'api': 3, 'admin': 5, 'realtime': 3, 'light': 2, 'decouple': 2, 'speed': 5},
}

def rank(weights):
    total = {}
    for name, dims in SCORES.items():
        total[name] = sum(dims[d] * w for d, w in weights.items())
    return sorted(total.items(), key=lambda kv: -kv[1])

typed_api = {'api': 5, 'admin': 1, 'realtime': 2, 'light': 2, 'decouple': 3, 'speed': 2}
cms = {'api': 1, 'admin': 5, 'realtime': 1, 'light': 1, 'decouple': 1, 'speed': 5}
print('typed api', rank(typed_api))
print('cms', rank(cms))
best_api = rank(typed_api)[0][0]
best_cms = rank(cms)[0][0]
print('different winners', best_api != best_cms)
