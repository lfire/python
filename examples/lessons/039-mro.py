"""
第 039 讲 · 属性查找、MRO 与 super
与教程正文一一对应的示例代码

课程页面：/oop/mro
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/039-mro.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/039-mro.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# ['D', 'B', 'C', 'A', 'object']
# D
# B
# C
# A
# True

class A:
    def __init__(self):
        print('A')

class B(A):
    def __init__(self):
        print('B')
        super().__init__()

class C(A):
    def __init__(self):
        print('C')
        super().__init__()

class D(B, C):
    def __init__(self):
        print('D')
        super().__init__()

print([c.__name__ for c in D.__mro__])
d = D()
print(D.__mro__ == (D, B, C, A, object))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# ['D', 'B', 'C', 'A', 'object']
# B
# A
# False
# ('__class__',)

class A:
    def __init__(self):
        print('A')

class B(A):
    def __init__(self):
        print('B')
        A.__init__(self)

class C(A):
    def __init__(self):
        print('C')
        super().__init__()

class D(B, C):
    def __init__(self):
        super().__init__()

print([c.__name__ for c in D.__mro__])
D()
print('__class__' in B.__init__.__code__.co_freevars)
print(C.__init__.__code__.co_freevars)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# ['Sub', 'Base', 'object']
# True
# True
# base-sub
# TypeError Cannot create a consistent method resolution order (MRO) for bases A, B

import inspect

class Base:
    def ping(self):
        return 'base'

class Sub(Base):
    def ping(self):
        return super().ping() + '-sub'

s = Sub()
print([c.__name__ for c in inspect.getmro(Sub)])
print(inspect.getmro(Sub) == Sub.__mro__)
print('__class__' in Sub.ping.__code__.co_freevars)
print(s.ping())

def inconsistent():
    class A: pass
    class B(A): pass
    class C(A, B): pass
try:
    inconsistent()
except TypeError as e:
    print(type(e).__name__, str(e))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import json

class JSONMixin:
    def to_json(self):
        return json.dumps(self.as_dict())
    def as_dict(self):
        return dict(self.__dict__)

class PrefixMixin:
    def greet(self):
        return '[' + super().greet() + ']'

class Base:
    def __init__(self, name):
        self.name = name
    def greet(self):
        return 'hi ' + self.name

class User(PrefixMixin, JSONMixin, Base):
    pass

u = User('ada')
print([c.__name__ for c in User.__mro__])
print(u.greet())
print(u.to_json())
print(u.as_dict())
