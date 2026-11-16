"""
第 084 讲 · 路由、依赖注入与请求校验
与教程正文一一对应的示例代码

课程页面：/server/routing
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/084-routing.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/084-routing.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
#   open db
# result (7, 'db-1')
# cache keys ['get_db', 'get_user', 'endpoint']

import inspect

class Depends:
    def __init__(self, fn):
        self.fn = fn

def get_db():
    print('  open db')
    return {'conn': 'db-1'}

def get_user(db=Depends(get_db)):
    return {'uid': 7, 'db': db['conn']}

CACHE = {}
def resolve(callable_):
    if callable_ in CACHE:
        return CACHE[callable_]
    sig = inspect.signature(callable_)
    kwargs = {}
    for name, p in sig.parameters.items():
        if isinstance(p.default, Depends):
            kwargs[name] = resolve(p.default.fn)
    value = callable_(**kwargs)
    CACHE[callable_] = value
    return value

def endpoint(user=Depends(get_user), db=Depends(get_db)):
    return (user['uid'], db['conn'])

CACHE.clear()
print('result', resolve(endpoint))
print('cache keys', [f.__name__ for f in CACHE])

# ======================== 2. 对照写法 ========================
# 预期输出：
# {'page': 2, 'size': 20, 'q': 'py'}
# reject page must be > 0
# reject size must be int

import inspect
from typing import get_type_hints

def coerce(fn, raw):
    hints = get_type_hints(fn)
    out = {}
    for name, p in inspect.signature(fn).parameters.items():
        t = hints.get(name)
        if name not in raw:
            raise KeyError('missing ' + name)
        v = raw[name]
        if t is int:
            if not isinstance(v, int):
                raise ValueError(name + ' must be int')
            if v <= 0:
                raise ValueError(name + ' must be > 0')
            out[name] = v
        elif t is bool:
            out[name] = bool(v)
        else:
            out[name] = str(v)
    return out

def endpoint(page: int, size: int, q: str):
    return (page, size, q)

print(coerce(endpoint, {'page': 2, 'size': 20, 'q': 'py'}))
for bad in ({'page': 0, 'size': 20, 'q': 'py'}, {'page': 1, 'size': 'x', 'q': 'py'}):
    try:
        coerce(endpoint, bad)
    except ValueError as e:
        print('reject', str(e))

# ======================== 3. 原理验证 ========================
# 预期输出：
# endpoint defaults ['Depends', 'Depends']
# resolves to ['get_user', 'get_db']
# get_user param ['db']

import inspect

class Depends:
    def __init__(self, fn):
        self.fn = fn

def get_db():
    return 'db'
def get_user(db=Depends(get_db)):
    return 'uid'
def endpoint(user=Depends(get_user), db=Depends(get_db)):
    return user

print('endpoint defaults', [type(d).__name__ for d in endpoint.__defaults__])
print('resolves to', [d.fn.__name__ for d in endpoint.__defaults__])
print('get_user param', list(inspect.signature(get_user).parameters))

# ======================== 4. 工程案例 ========================

import inspect

class Depends:
    def __init__(self, fn):
        self.fn = fn

def get_repo():
    return {'orders': [], 'next_id': 1}

ROUTES = {}
OVERRIDES = {}

def route(path):
    def deco(fn):
        ROUTES[path] = fn
        return fn
    return deco

def resolve(fn, cache):
    if fn in cache:
        return cache[fn]
    kwargs = {}
    for name, p in inspect.signature(fn).parameters.items():
        if isinstance(p.default, Depends):
            dep = OVERRIDES.get(p.default.fn, p.default.fn)
            kwargs[name] = resolve(dep, cache)
    cache[fn] = fn(**kwargs)
    return cache[fn]

def place_order(uid, amount, repo):
    if amount <= 0:
        raise ValueError('amount must be positive')
    oid = repo['next_id']
    repo['next_id'] += 1
    repo['orders'].append((oid, uid, amount))
    return {'id': oid}

@route('/orders')
def create(amount: int, uid: int, repo=Depends(get_repo)):
    return (201, place_order(uid, amount, repo))

def dispatch(path, params):
    fn = ROUTES[path]
    try:
        params = {k: int(v) for k, v in params.items()}
        return resolve_with_params(fn, params)
    except ValueError as e:
        return (422, {'error': 'validation_error', 'detail': str(e)})

def resolve_with_params(fn, params):
    cache = {}
    deps = {}
    for name, p in inspect.signature(fn).parameters.items():
        if isinstance(p.default, Depends):
            deps[name] = resolve(OVERRIDES.get(p.default.fn, p.default.fn), cache)
    return fn(**params, **deps)

fake = {'orders': [], 'next_id': 100}
OVERRIDES[get_repo] = lambda: fake
print(dispatch('/orders', {'amount': 50, 'uid': 7}))
print(dispatch('/orders', {'amount': 0, 'uid': 7}))
print('orders', fake['orders'])
