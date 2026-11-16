"""
第 011 讲 · 运算符与表达式：优先级、短路与真值
与教程正文一一对应的示例代码

课程页面：/foundation/operators
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/011-operators.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/011-operators.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# or_value default
# and_value 3
# and_short 0
# floordiv -4 3
# mod 1
# chain True False
# divmod (3, 1)

print('or_value', 0 or 0.0 or 'default')
print('and_value', 1 and 2 and 3)
print('and_short', 0 and (1 / 0))
print('floordiv', -7 // 2, 7 // 2)
print('mod', -7 % 2)
print('chain', 1 < 2 < 3, 1 < 3 < 2)
print('divmod', divmod(7, 2))

# ======================== 2. 对照写法 ========================
# 预期输出：
# walrus_n 3
# or_bug fallback
# fixed 0
# truthy_empty False False False
# nonzero True True

data = [1, 2, 3]
if (n := len(data)) > 2:
    print('walrus_n', n)

count = 0
print('or_bug', count or 'fallback')
print('fixed', count if count is not None else 'fallback')
print('truthy_empty', bool([]), bool(''), bool(0))
print('nonzero', bool([0]), bool('0'))

# ======================== 3. 原理验证 ========================
# 预期输出：
# bool_via_len False
# none_is_false False
# refcount_ge True
# int_bool_slot True
# list_len_slot True
# short_circuit 0

import sys

class Box:
    def __len__(self): return 0

print('bool_via_len', bool(Box()))
print('none_is_false', bool(None))
print('refcount_ge', sys.getrefcount(None) > 1)
print('int_bool_slot', hasattr(int, '__bool__'))
print('list_len_slot', hasattr(list, '__len__'))
print('short_circuit', 0 and (1 // 0))

# ======================== 4. 工程案例 ========================

def read_int(cfg, key, default):
    raw = cfg.get(key)
    return default if raw is None else int(raw)

def read_bool(cfg, key, default):
    raw = cfg.get(key)
    return default if raw is None else bool(raw)

def in_range(value, lo, hi):
    return lo <= value <= hi

cfg = {'timeout': 0, 'retries': 0, 'enabled': ''}
timeout = read_int(cfg, 'timeout', 30)
retries = read_int(cfg, 'retries', 3)
enabled = read_bool(cfg, 'enabled', True)
print('timeout', timeout, 'in_range', in_range(timeout, 0, 60))
print('retries', retries)
print('enabled', enabled)
if (n := len(cfg)) >= 3:
    print('keys', n)
q, r = divmod(timeout, 7)
print('divmod', q, r)
