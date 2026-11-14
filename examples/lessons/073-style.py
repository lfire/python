"""
第 073 讲 · 代码规范：PEP 8、ruff、black 与 pre-commit
与教程正文一一对应的示例代码

课程页面：/engineering/style
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/073-style.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/073-style.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# line-length 88
# selected ['E', 'F', 'I', 'N', 'UP']
# defs ['CalcTotal']
# naming N802 True
# too long E501 lines [2]

import ast, tomllib

cfg = tomllib.loads(chr(10).join([
    '[tool.ruff]',
    'line-length = 88',
    'target-version = "py311"',
    '[tool.ruff.lint]',
    'select = ["E", "F", "I", "N", "UP"]',
]))
limit = cfg['tool']['ruff']['line-length']
print('line-length', limit)
print('selected', cfg['tool']['ruff']['lint']['select'])

source = [
    'def CalcTotal(a,b):',
    '    return a+b  # ' + 'x' * 90,
]
tree = ast.parse(chr(10).join(source))
names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
long_lines = [i + 1 for i, ln in enumerate(source) if len(ln) > limit]
print('defs', names)
print('naming N802', any(n != n.lower() for n in names))
print('too long E501 lines', long_lines)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# stdlib ['os', 'sys']
# third ['requests']
# local ['myapp']
# I001 needs reorder True

import ast

STDLIB = {'os', 'sys', 'collections'}
source = chr(10).join([
    'import sys',
    'from myapp import core',
    'import requests',
    'import os',
])

def top(module):
    return module.split('.')[0]

tree = ast.parse(source)
mods = []
for n in tree.body:
    if isinstance(n, ast.Import):
        mods += [a.name for a in n.names]
    elif isinstance(n, ast.ImportFrom):
        mods.append(n.module or '')

groups = {'stdlib': [], 'third': [], 'local': []}
for m in mods:
    root = top(m)
    key = 'stdlib' if root in STDLIB else ('local' if root == 'myapp' else 'third')
    groups[key].append(m)
for k in ('stdlib', 'third', 'local'):
    groups[k] = sorted(groups[k])
print('stdlib', groups['stdlib'])
print('third', groups['third'])
print('local', groups['local'])
print('I001 needs reorder', mods != groups['stdlib'] + groups['third'] + groups['local'])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# same AST True
# node type BinOp
# col offset 4

import ast

a = 'x=1+2'
b = 'x = 1 + 2'
print('same AST', ast.dump(ast.parse(a)) == ast.dump(ast.parse(b)))
tree = ast.parse(b)
node = tree.body[0].value
print('node type', type(node).__name__)
print('col offset', node.col_offset)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import ast, tomllib

CONFIG = tomllib.loads(chr(10).join([
    '[tool.ruff.lint]',
    'select = ["N", "E501"]',
    '[tool.ruff.lint.per-file-ignores]',
    '"legacy/*" = ["N"]',
]))

def check(path, source, limit=88):
    ignored = CONFIG['tool']['ruff']['lint']['per-file-ignores']
    skip_naming = any(path.startswith(k.rstrip('*')) for k in ignored)
    violations = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != node.name.lower() and not skip_naming:
            violations.append('N802:' + node.name)
    for i, line in enumerate(source.splitlines(), 1):
        if len(line) > limit:
            violations.append('E501:' + str(i))
    return violations

FILES = {
    'app/service.py': 'def fetch(x):' + chr(10) + '    return x' + chr(10),
    'legacy/old.py': 'def BadName(x):' + chr(10) + '    return x' + chr(10),
}
for name, src in FILES.items():
    print(name, check(name, src))
