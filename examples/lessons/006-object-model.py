"""
第 006 讲 · 一切皆对象：id、type、value 与可变性
与教程正文一一对应的示例代码

课程页面：/foundation/object-model
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/006-object-model.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/006-object-model.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# small_same True
# big_same False
# values_equal True
# bool_is_int True 2
# type_ok True

small_a = 100
small_b = 100
big_a = int('1000')
big_b = int('1000')
print('small_same', small_a is small_b)
print('big_same', big_a is big_b)
print('values_equal', big_a == big_b)
print('bool_is_int', isinstance(True, int), True + True)
print('type_ok', type(small_a) is int)

# ======================== 2. 对照写法 ========================
# 预期输出：
# int_rebound True
# list_inplace True
# list_value [1, 2]

n = 1
id_before = id(n)
n += 1
print('int_rebound', id(n) != id_before)

lst = [1]
lst_id = id(lst)
lst += [2]
print('list_inplace', id(lst) == lst_id)
print('list_value', lst)

# ======================== 3. 原理验证 ========================
# 预期输出：
# cached True
# sizeof_list_grows True
# refcount_ge True
# none_singleton True
# type_vs_isinstance True

import sys
a = 100
b = 100
print('cached', a is b)
print('sizeof_list_grows', sys.getsizeof([]) < sys.getsizeof([1, 2, 3]))
print('refcount_ge', sys.getrefcount(a) >= 2)
print('none_singleton', None is None)
print('type_vs_isinstance', isinstance(True, int) and type(True) is bool)

# ======================== 4. 工程案例 ========================

import sys

def audit(a, b):
    return {'same_object': a is b,
            'refcount_ge': sys.getrefcount(a) >= 3,
            'value_equal': a == b}

shared = []
alias = shared
print('before', audit(shared, alias))
shared.append('tag')
print('after_alias', alias)

def bad_add(tag, bucket=[]):
    bucket.append(tag)
    return bucket

def good_add(tag, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(tag)
    return bucket

b1, b2 = bad_add('a'), bad_add('b')
g1, g2 = good_add('a'), good_add('b')
print('bad_shared', b1 is b2)
print('good_isolated', g1 is not g2)
print('good_values', g1, g2)
