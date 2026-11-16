"""
第 056 讲 · 属性访问链路与 __getattribute__
与教程正文一一对应的示例代码

课程页面：/core/attribute-lookup
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/056-attribute-lookup.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/056-attribute-lookup.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# data-desc
# instance-b
# assigned
# DataDesc True

class DataDesc:
    def __get__(self, obj, owner):
        return 'data-desc'
    def __set__(self, obj, value):
        pass

class NonDataDesc:
    def __get__(self, obj, owner):
        return 'non-data-desc'

class Demo:
    a = DataDesc()
    b = NonDataDesc()

d = Demo()
d.__dict__['a'] = 'instance-a'
d.__dict__['b'] = 'instance-b'
print(d.a)
print(d.b)
d.b = 'assigned'
print(d.b)
print(type(Demo.__dict__['a']).__name__, hasattr(DataDesc, '__set__'))

# ======================== 2. 对照写法 ========================
# 预期输出：
# lazy:computed_total
# {}
# fallback:missing
# True

class Lazy:
    def __init__(self):
        object.__setattr__(self, 'cache', {})
    def __getattribute__(self, name):
        if name.startswith('computed_'):
            return 'lazy:' + name
        return object.__getattribute__(self, name)
    def __getattr__(self, name):
        return 'fallback:' + name

x = Lazy()
print(x.computed_total)
print(x.cache)
print(x.missing)
print(x.__dict__['cache'] == {})

# ======================== 3. 原理验证 ========================
# 预期输出：
# static True
# dynamic 100
# opnames ['RESUME', 'LOAD_FAST', 'LOAD_ATTR', 'RETURN_VALUE']

import dis
import inspect

class D:
    def __get__(self, o, t):
        return 100

class C:
    x = D()

def read(o):
    return o.x

c = C()
print('static', inspect.getattr_static(c, 'x') is C.__dict__['x'])
print('dynamic', c.x)
print('opnames', [i.opname for i in dis.get_instructions(read)])

# ======================== 4. 工程案例 ========================

class Model:
    def __init__(self, rowid):
        object.__setattr__(self, 'rowid', rowid)
        object.__setattr__(self, '_hits', 0)
    def __getattribute__(self, name):
        if not name.startswith('_'):
            object.__setattr__(self, '_hits', object.__getattribute__(self, '_hits') + 1)
        return object.__getattribute__(self, name)
    @property
    def profile(self):
        d = object.__getattribute__(self, '__dict__')
        if '_profile' not in d:
            d['_profile'] = 'profile-of-' + str(d['rowid'])
        return d['_profile']
    @profile.setter
    def profile(self, value):
        if not isinstance(value, str):
            raise TypeError('profile must be str')
        self.__dict__['_profile'] = value
    def __getattr__(self, name):
        if name.startswith('col_'):
            return 'from-db:' + name
        raise AttributeError(name)

if __name__ == '__main__':
    m = Model(7)
    print(m.profile)
    m.profile = 'edited'
    print(m.profile, m.col_extra)
    try:
        m.missing
    except AttributeError as e:
        print('missing', type(e).__name__)
