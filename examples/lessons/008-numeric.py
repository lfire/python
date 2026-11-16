"""
第 008 讲 · 数值体系：int 任意精度、float、Decimal 与 bool
与教程正文一一对应的示例代码

课程页面：/foundation/numeric
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/008-numeric.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/008-numeric.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# float_sum 0.30000000000000004
# equal False
# isclose True
# decimal 0.3
# decimal_eq True
# fraction 1/2

from decimal import Decimal
from fractions import Fraction
import math

print('float_sum', 0.1 + 0.2)
print('equal', 0.1 + 0.2 == 0.3)
print('isclose', math.isclose(0.1 + 0.2, 0.3))
print('decimal', Decimal('0.1') + Decimal('0.2'))
print('decimal_eq', Decimal('0.1') + Decimal('0.2') == Decimal('0.3'))
print('fraction', Fraction(1, 3) + Fraction(1, 6))

# ======================== 2. 对照写法 ========================
# 预期输出：
# big_digits 31
# no_overflow True
# bool_sub True 2
# shift 1024
# bitand 8
# complex (3+4j) 5.0

big = 2 ** 100
print('big_digits', len(str(big)))
print('no_overflow', big * big > big)
print('bool_sub', isinstance(True, int), True + True)
print('shift', 1 << 10)
print('bitand', 0b1100 & 0b1010)
print('complex', 3 + 4j, abs(3 + 4j))

# ======================== 3. 原理验证 ========================
# 预期输出：
# float_hex 3fb999999999999a
# int_grows True
# isclose_default True
# isclose_tight False
# float_radix 2

import sys, struct, math
print('float_hex', struct.pack('>d', 0.1).hex())
print('int_grows', sys.getsizeof(2 ** 100) > sys.getsizeof(0))
print('isclose_default', math.isclose(1.0, 1.0 + 1e-10))
print('isclose_tight', math.isclose(1.0, 1.0 + 1e-3, rel_tol=1e-9))
print('float_radix', sys.float_info.radix)

# ======================== 4. 工程案例 ========================

from decimal import Decimal, ROUND_HALF_UP, localcontext
import math

CENT = Decimal('0.01')

def money(s):
    return Decimal(s)

def settle(rows, rate):
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        total = Decimal('0')
        for s in rows:
            total += money(s)
        fee = (total * Decimal(rate)).quantize(CENT)
        return (total + fee).quantize(CENT)

rows = ['0.10'] * 10
gross = settle(rows, '0.006')
float_sum = 0.0
for s in rows:
    float_sum += float(s)
print('decimal_total', gross)
print('float_exact', float_sum == 1.0)
print('float_isclose', math.isclose(float_sum, 1.0))
print('two_places', str(gross))
