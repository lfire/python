"""
第 038 讲 · 类与实例：__init__、self 与属性
与教程正文一一对应的示例代码

课程页面：/oop/class-basics
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/038-class-basics.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/038-class-basics.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# ['book'] [] ['pen']
# function method
# True True
# {'owner': 'a', 'items': ['book']}

class Cart:
    shared = []
    def __new__(cls, owner):
        return super().__new__(cls)
    def __init__(self, owner):
        self.owner = owner
        self.items = []
    def add(self, item):
        self.items.append(item)
        return self.items

a = Cart('a')
b = Cart('b')
a.add('book')
a.shared.append('pen')
print(a.items, b.items, b.shared)
print(type(Cart.add).__name__, type(a.add).__name__)
print(a.add.__self__ is a, a.add.__func__ is Cart.add)
print(vars(a))

# ======================== 2. 对照写法 ========================
# 预期输出：
# TypeError __init__() should return None, not 'int'
# 1 2 False
# AttributeError 'SlotPoint' object has no attribute 'z' and no __dict__ for setting new attributes
# Point(x=3, y=0) 3 0

from dataclasses import dataclass

class BadInit:
    def __init__(self):
        self.x = 1
        return self.x
try:
    BadInit()
except TypeError as e:
    print(type(e).__name__, str(e))

class SlotPoint:
    __slots__ = ('x', 'y')
    def __init__(self, x, y):
        self.x = x
        self.y = y
p = SlotPoint(1, 2)
print(p.x, p.y, hasattr(p, '__dict__'))
try:
    p.z = 3
except AttributeError as e:
    print(type(e).__name__, str(e))

@dataclass
class Point:
    x: int
    y: int = 0
q = Point(3)
print(q, q.x, q.y)

# ======================== 3. 原理验证 ========================
# 预期输出：
# function method
# True True
# True
# True
# True

import dis, types

class C:
    def m(self, x):
        return x

c = C()
print(type(C.__dict__['m']).__name__, type(c.m).__name__)
print(isinstance(c.m, types.MethodType), c.m.__self__ is c)
print(C.m.__get__(c, C).__func__ is C.m)
print('self' in C.m.__code__.co_varnames)
ops = [i.opname for i in dis.get_instructions(C.m)]
print('LOAD_FAST' in ops or 'LOAD_FAST_LOAD_FAST' in ops)

# ======================== 4. 工程案例 ========================

from dataclasses import dataclass

@dataclass(slots=True)
class Money:
    amount: int
    currency: str = 'CNY'
    def add(self, other):
        if self.currency != other.currency:
            raise ValueError('currency mismatch')
        return Money(self.amount + other.amount, self.currency)
    def as_dict(self):
        return {'amount': self.amount, 'currency': self.currency}

a = Money(100)
b = Money(50)
c = a.add(b)
print(c, c.amount, c.currency)
print(hasattr(a, '__dict__'), hasattr(c, '__dict__'))
print(type(Money.add).__name__, type(a.add).__name__, a.add.__self__ is a)
print(a.as_dict())
try:
    a.extra = 1
except AttributeError as e:
    print(type(e).__name__, str(e))
