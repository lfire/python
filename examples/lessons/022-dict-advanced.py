"""
第 022 讲 · dict 进阶：默认字典、计数器与合并
与教程正文一一对应的示例代码

课程页面：/containers/dict-advanced
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/022-dict-advanced.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/022-dict-advanced.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# groups {1: ['a', 'c'], 2: ['bb', 'dd', 'ee']}
# read created key True
# get avoids factory None False
# counts 3 0 [('a', 3), ('n', 2)]
# update adds 4 1 8
# layered True 9000
# writes to first ['debug', 'timeout'] env untouched {'port': 9000}
# pipe merge {'x': 2, 'y': 3}
# unpack merge {'x': 2, 'y': 3}
# chainmap is live 20

from collections import defaultdict, Counter, ChainMap

groups = defaultdict(list)
for word in ('a', 'bb', 'c', 'dd', 'ee'):
    groups[len(word)].append(word)
print('groups', dict(groups))
before = len(groups)
_ = groups[99]
print('read created key', len(groups) == before + 1)
print('get avoids factory', groups.get(98), 98 in groups)

c = Counter('banana')
print('counts', c['a'], c['z'], c.most_common(2))
c.update(['a', 'x'])
print('update adds', c['a'], c['x'], c.total())

defaults = {'debug': False, 'port': 8080}
env = {'port': 9000}
user = {'debug': True}
cfg = ChainMap(user, env, defaults)
print('layered', cfg['debug'], cfg['port'])
cfg['timeout'] = 5
print('writes to first', list(user), 'env untouched', env)

a = {'x': 1}
b = {'x': 2, 'y': 3}
print('pipe merge', a | b)
print('unpack merge', {**a, **b})
view = ChainMap(b, {'z': 9})
b['x'] = 20
print('chainmap is live', view['x'])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# moved ['b', 'a'] popitem FIFO ('b', 2)
# dict eq ignores order True
# ordered eq is strict False
# add Counter({'a': 4, 'b': 3})
# subtract drops nonpositive Counter({'a': 2})
# intersection min Counter({'a': 1, 'b': 1})
# frozen is plain dict dict False

from collections import OrderedDict, Counter, defaultdict

o = OrderedDict([('a', 1), ('b', 2)])
o.move_to_end('a')
print('moved', list(o), 'popitem FIFO', o.popitem(last=False))

d = {'a': 1, 'b': 2}
print('dict eq ignores order', d == {'b': 2, 'a': 1})
print('ordered eq is strict', OrderedDict(a=1, b=2) == OrderedDict(b=2, a=1))

c1 = Counter(a=3, b=1)
c2 = Counter(a=1, b=2)
print('add', c1 + c2)
print('subtract drops nonpositive', c1 - c2)
print('intersection min', c1 & c2)

g = defaultdict(list, {'x': [1]})
frozen = dict(g)
print('frozen is plain dict', type(frozen).__name__, hasattr(frozen, 'default_factory'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# counter is dict subclass True
# chainmap is mapping True
# defaultdict is dict subclass True
# counter missing zero 0
# mapping abstract ['__getitem__', '__iter__', '__len__']
# factory type type
# get does not insert None 0
# getitem inserts 1 0

from collections import Counter, ChainMap, defaultdict
from collections.abc import Mapping, MutableMapping

print('counter is dict subclass', issubclass(Counter, dict))
print('chainmap is mapping', issubclass(ChainMap, MutableMapping))
print('defaultdict is dict subclass', issubclass(defaultdict, dict))
print('counter missing zero', Counter().__missing__('k'))
print('mapping abstract', sorted(Mapping.__abstractmethods__))

d = defaultdict(int)
print('factory type', type(d.default_factory).__name__)
print('get does not insert', d.get('x'), len(d))
_ = d['x']
print('getitem inserts', len(d), d['x'])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from collections import ChainMap, Counter, defaultdict

defaults = {'port': 8080, 'debug': False, 'retries': 3}
env = {'port': 9000}
user = {'debug': True}
cfg = ChainMap(user, env, defaults)
hits = Counter()
changes = defaultdict(list)

def layer_name(layer):
    if layer is user: return 'user'
    if layer is env: return 'env'
    return 'defaults'

def read(key, tag):
    for layer in cfg.maps:
        if key in layer:
            hits[layer_name(layer)] += 1
            changes[key].append((tag, layer[key]))
            return layer[key]
    raise KeyError(key)

print('port', read('port', 'boot'))
print('debug', read('debug', 'boot'))
defaults['retries'] = 5
print('retries after hot update', read('retries', 'hot'))
snapshot = dict(cfg)
print('snapshot debug', snapshot['debug'])
print('hits', dict(hits))
print('log frozen', type(dict(changes)).__name__)
