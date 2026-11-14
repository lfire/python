"""
第 040 讲 · 访问控制、property 与描述符协议
与教程正文一一对应的示例代码

课程页面：/oop/property
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/040-property.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/040-property.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# 18 True
# ValueError age must be non-negative int
# 18
# property
# True

class User:
    def __init__(self, age):
        self.__secret = 7
        self.age = age
    @property
    def age(self):
        return self._age
    @age.setter
    def age(self, value):
        if not isinstance(value, int) or value < 0:
            raise ValueError('age must be non-negative int')
        self._age = value

u = User(18)
print(u.age, '_User__secret' in u.__dict__)
try:
    u.age = -1
except ValueError as e:
    print(type(e).__name__, str(e))
print(u.age)
print(type(User.__dict__['age']).__name__)
print(isinstance(User.__dict__['age'], property))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# 10 price _price
# mine True
# ValueError negative

class Checked:
    def __set_name__(self, owner, name):
        self.name = name
        self.key = '_' + name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.key)
    def __set__(self, obj, value):
        if value < 0:
            raise ValueError('negative')
        obj.__dict__[self.key] = value

class Loose:
    def __get__(self, obj, objtype=None):
        return 'loose'

class Item:
    price = Checked()
    tag = Loose()
    def __init__(self, price):
        self.price = price

it = Item(10)
print(it.price, Item.price.name, Item.price.key)
it.tag = 'mine'
print(it.tag, 'tag' in it.__dict__)
try:
    it.price = -5
except ValueError as e:
    print(type(e).__name__, str(e))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# True True
# False True
# True
# ['_C__hidden']
# True

import dis

class C:
    __hidden = 1
    def m(self):
        return self.__hidden
    @property
    def p(self):
        return 1

p = C.__dict__['p']
m = C.__dict__['m']
print(hasattr(p, '__set__'), hasattr(p, '__get__'))
print(hasattr(m, '__set__'), hasattr(m, '__get__'))
print('_C__hidden' in C.__dict__)
print([n for n in C.__dict__ if 'hidden' in n])
ops = [i.argval for i in dis.get_instructions(C.m)]
print('_C__hidden' in ops)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

class Field:
    def __init__(self, typ, minimum=None):
        self.typ = typ
        self.minimum = minimum
    def __set_name__(self, owner, name):
        self.name = name
        self.key = '_' + name
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return obj.__dict__.get(self.key)
    def __set__(self, obj, value):
        if not isinstance(value, self.typ):
            raise TypeError('bad type for ' + self.name)
        if self.minimum is not None and value < self.minimum:
            raise ValueError('too small for ' + self.name)
        obj.__dict__[self.key] = value

class Product:
    price = Field(float, minimum=0.0)
    stock = Field(int, minimum=0)
    def __init__(self, price, stock):
        self.price = price
        self.stock = stock

p = Product(9.9, 5)
print(p.price, p.stock, Product.price.name)
for attr, val in [('price', -1.0), ('stock', 'x')]:
    try:
        setattr(p, attr, val)
    except (TypeError, ValueError) as e:
        print(type(e).__name__, str(e))
