"""
第 012 讲 · 分支：if / elif / else 与 match-case
与教程正文一一对应的示例代码

课程页面：/foundation/control-flow
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/012-control-flow.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/012-control-flow.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# move 3 4
# stop done
# positive 9
# unknown
# unknown

def describe(cmd):
    match cmd:
        case ['go', x, y]:
            return 'move ' + str(x) + ' ' + str(y)
        case {'type': 'stop', 'reason': r}:
            return 'stop ' + str(r)
        case [x] if x > 0:
            return 'positive ' + str(x)
        case _:
            return 'unknown'

print(describe(['go', 3, 4]))
print(describe({'type': 'stop', 'reason': 'done'}))
print(describe([9]))
print(describe([-1]))
print(describe('anything'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# 5
# 6
# 3
# None
# ternary even

def apply(op, a, b):
    table = {
        'add': lambda: a + b,
        'mul': lambda: a * b,
        'max': lambda: a if a > b else b,
    }
    return table.get(op, lambda: None)()

print(apply('add', 2, 3))
print(apply('mul', 2, 3))
print(apply('max', 2, 3))
print(apply('mod', 2, 3))
print('ternary', 'even' if 4 % 2 == 0 else 'odd')

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# version_ge_310 True
# has_match_seq True
# has_jump True
# list_case 5
# fallback -1
# instr_count True

import sys, dis

def route(x):
    match x:
        case [a, b]: return a + b
        case _: return -1

ops = [i.opname for i in dis.get_instructions(route)]
print('version_ge_310', sys.version_info >= (3, 10))
print('has_match_seq', 'MATCH_SEQUENCE' in ops)
print('has_jump', any('JUMP' in o for o in ops))
print('list_case', route([2, 3]))
print('fallback', route(7))
print('instr_count', len(ops) > 5)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

def route(cmd):
    match cmd:
        case ['go', x, y]:
            return 'move ' + str(x) + ' ' + str(y)
        case {'type': 'stop', 'reason': why}:
            return 'stop ' + str(why)
        case [x] if x > 0:
            return 'positive ' + str(x)
        case _:
            return 'unknown'

OPS = {
    'add': lambda a, b: a + b,
    'mul': lambda a, b: a * b,
    'max': lambda a, b: a if a > b else b,
}

def compute(op, a, b):
    fn = OPS.get(op)
    return fn(a, b) if fn else None

for cmd in (['go', 3, 4], {'type': 'stop', 'reason': 'done'}, [9], [-1], 'x'):
    print(route(cmd))
print('add', compute('add', 2, 3), 'max', compute('max', 2, 3))
print('missing', compute('mod', 2, 3))
