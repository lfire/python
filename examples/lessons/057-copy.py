"""
第 057 讲 · 可变性、深浅拷贝与共享状态
与教程正文一一对应的示例代码

课程页面：/core/copy
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/057-copy.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/057-copy.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# outer is shallow False
# shallow inner shared True
# deep inner new True
# deep keeps alias True
# shallow sees [1, 2, 3]
# deep isolated [1, 2]

import copy

inner = [1, 2]
outer = [inner, inner]
shallow = copy.copy(outer)
deep = copy.deepcopy(outer)
print('outer is shallow', outer is shallow)
print('shallow inner shared', shallow[0] is outer[0])
print('deep inner new', deep[0] is not outer[0])
print('deep keeps alias', deep[0] is deep[1])
outer[0].append(3)
print('shallow sees', shallow[0])
print('deep isolated', deep[0])

# ======================== 2. 对照写法 ========================
# 预期输出：
# cycle ok True True
# str reused True
# int reused True
# tuple copy reused True

import copy

node = {'name': 'root'}
node['self'] = node
clone = copy.deepcopy(node)
print('cycle ok', clone['self'] is clone, clone is not node)
s = 'immutable'
n = 10 ** 40
print('str reused', copy.deepcopy(s) is s)
print('int reused', copy.deepcopy(n) is n)
t = (1, 2, 3)
print('tuple copy reused', copy.copy(t) is t)

# ======================== 3. 原理验证 ========================
# 预期输出：
# shallow delta > 0 True
# deep delta > shallow True
# delta ratio > 5 True

import copy
import tracemalloc

data = [[i] for i in range(2000)]
tracemalloc.start()
base = tracemalloc.get_traced_memory()[0]
copy.copy(data)
after_shallow = tracemalloc.get_traced_memory()[0]
copy.deepcopy(data)
after_deep = tracemalloc.get_traced_memory()[0]
print('shallow delta > 0', after_shallow - base > 0)
print('deep delta > shallow', (after_deep - after_shallow) > (after_shallow - base))
print('delta ratio > 5', (after_deep - after_shallow) // max(1, after_shallow - base) > 5)
tracemalloc.stop()

# ======================== 4. 工程案例 ========================

import copy
from types import MappingProxyType

class RequestConfig:
    def __init__(self, raw):
        object.__setattr__(self, '_data', copy.deepcopy(raw))
    @property
    def view(self):
        return MappingProxyType(object.__getattribute__(self, '_data'))
    def export(self):
        return copy.deepcopy(object.__getattribute__(self, '_data'))
    def freeze(self):
        d = object.__getattribute__(self, '_data')
        return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in d.items()))
    def __setattr__(self, name, value):
        raise AttributeError('use export() to get a mutable copy')

if __name__ == '__main__':
    raw = {'tags': ['a', 'b'], 'limit': 10}
    cfg = RequestConfig(raw)
    raw['tags'].append('hack')
    print('isolated', cfg.view['tags'])
    v = cfg.export()
    v['tags'].append('local')
    print('export isolated', cfg.view['tags'])
    print('frozen', cfg.freeze())
    try:
        cfg.view['x'] = 1
    except TypeError as e:
        print('view read only', type(e).__name__)
