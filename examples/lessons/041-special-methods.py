"""
第 041 讲 · 特殊方法：repr、比较、算术与容器协议
与教程正文一一对应的示例代码

课程页面：/oop/special-methods
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/041-special-methods.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/041-special-methods.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# Vec(1, 2) [Vec(1, 2)]
# eq True ne True
# hash None
# bool True False len 2
# contains True False

class Vec:
    def __init__(self, x, y):
        self.x, self.y = x, y
    def __repr__(self):
        return 'Vec(' + repr(self.x) + ', ' + repr(self.y) + ')'
    def __eq__(self, other):
        if not isinstance(other, Vec):
            return NotImplemented
        return (self.x, self.y) == (other.x, other.y)
    def __len__(self):
        return 2
    def __bool__(self):
        return bool(self.x or self.y)
    def __contains__(self, v):
        return v in (self.x, self.y)

a = Vec(1, 2)
print(repr(a), [a])
print('eq', a == Vec(1, 2), 'ne', a != Vec(1, 3))
print('hash', Vec.__hash__)
print('bool', bool(a), bool(Vec(0, 0)), 'len', len(a))
print('contains', 2 in a, 9 in a)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# True True
# ge True
# radd Score(11)

from functools import total_ordering

@total_ordering
class Score:
    def __init__(self, v):
        self.v = v
    def __eq__(self, other):
        return isinstance(other, Score) and self.v == other.v
    def __lt__(self, other):
        return isinstance(other, Score) and self.v < other.v
    def __radd__(self, other):
        return Score(self.v + other)
    def __repr__(self):
        return 'Score(' + repr(self.v) + ')'

print(Score(3) < Score(5), Score(3) <= Score(3))
print('ge', Score(5) >= Score(4))
print('radd', repr(10 + Score(1)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# static hash: None
# TypeError: unhashable type: 'EqOnly'
# hash equal: True
# ne uses eq: False

import inspect

class EqOnly:
    def __eq__(self, other):
        return True
class WithHash:
    def __eq__(self, other):
        return isinstance(other, WithHash)
    def __hash__(self):
        return hash((1, 2))

print('static hash:', inspect.getattr_static(EqOnly, '__hash__', 'missing'))
try:
    hash(EqOnly())
except TypeError as e:
    print('TypeError:', str(e)[:36])
print('hash equal:', WithHash().__hash__() == WithHash().__hash__())
print('ne uses eq:', EqOnly() != object())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from dataclasses import dataclass

@dataclass(frozen=True)
class Money:
    amount: int
    currency: str
    def __add__(self, other):
        if self.currency != other.currency:
            raise ValueError('currency mismatch')
        return Money(self.amount + other.amount, self.currency)

ledger = {}
def record(m):
    base = ledger.get(m.currency, Money(0, m.currency))
    ledger[m.currency] = base + m

for m in [Money(100, 'CNY'), Money(250, 'CNY'), Money(30, 'USD'), Money(70, 'CNY')]:
    record(m)
print({k: v.amount for k, v in ledger.items()})
print('dedup', len({Money(1, 'CNY'), Money(1, 'CNY'), Money(2, 'CNY')}))
try:
    Money(1, 'CNY').amount = 9
except AttributeError as e:
    print(type(e).__name__)
