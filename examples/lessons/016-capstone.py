"""
第 016 讲 · 阶段综合：交互式命令行计算器
与教程正文一一对应的示例代码

课程页面：/foundation/capstone
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/016-capstone.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/016-capstone.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# 1 + 2 * 3 = 7
# (4 + 6) / 2 = 5.0
# -3 ** 2 = -9
# 2 ** 10 = 1024
# reject 'abs(-2)' ValueError
# reject '1 / 0' ZeroDivisionError
# reject 'x + 1' ValueError

import ast, operator

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def evaluate(expr):
    tree = ast.parse(expr, mode='eval')
    return _eval(tree.body)

def _eval(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](_eval(node.operand))
    raise ValueError('unsupported syntax')

for s in ('1 + 2 * 3', '(4 + 6) / 2', '-3 ** 2', '2 ** 10'):
    print(s, '=', evaluate(s))
for bad in ('abs(-2)', '1 / 0', 'x + 1'):
    try:
        evaluate(bad)
    except (ValueError, ZeroDivisionError) as e:
        print('reject', repr(bad), type(e).__name__)

# ======================== 2. 对照写法 ========================
# 预期输出：
# float 0.30000000000000004
# decimal 0.3
# literal_eval [1, 2, 3]
# literal_eval reject ValueError
# eval runs call 3
# restricted eval 42

import ast
from decimal import Decimal, getcontext

getcontext().prec = 28
print('float', 0.1 + 0.2)
print('decimal', Decimal('0.1') + Decimal('0.2'))
print('literal_eval', ast.literal_eval('[1, 2, 3]'))
try:
    print(ast.literal_eval('1 + 2'))
except ValueError as e:
    print('literal_eval reject', type(e).__name__)
print('eval runs call', eval('len([1, 2, 3])'))
print('restricted eval', eval('40 + 2', {'__builtins__': {}}, {}))

# ======================== 3. 原理验证 ========================
# 预期输出：
# root Expression
# node kinds ['Add', 'BinOp', 'Constant', 'Expression', 'Mult']
# has Call False
# danger has Call True
# danger has Name True
# eval compiles to LOAD_GLOBAL True

import ast, dis

tree = ast.parse('1 + 2 * 3', mode='eval')
print('root', type(tree).__name__)
print('node kinds', sorted({type(n).__name__ for n in ast.walk(tree)}))
print('has Call', any(isinstance(n, ast.Call) for n in ast.walk(tree)))

danger = ast.parse('eval(x)', mode='eval')
print('danger has Call', any(isinstance(n, ast.Call) for n in ast.walk(danger)))
print('danger has Name', any(isinstance(n, ast.Name) for n in ast.walk(danger)))

def f(x):
    return eval(x)

print('eval compiles to LOAD_GLOBAL', 'LOAD_GLOBAL' in dis.Bytecode(f).dis())

# ======================== 4. 工程案例 ========================

import argparse, ast, operator
from decimal import Decimal, getcontext

BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub,
          ast.Mult: operator.mul, ast.Div: operator.truediv,
          ast.Pow: operator.pow}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def compute(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Decimal(str(node.value))
    if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
        return BINOPS[type(node.op)](compute(node.left), compute(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](compute(node.operand))
    raise ValueError('unsupported node: ' + type(node).__name__)

def evaluate(expr):
    return compute(ast.parse(expr, mode='eval').body)

def render(expr):
    try:
        return str(evaluate(expr))
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        return 'error: ' + type(e).__name__

def main():
    p = argparse.ArgumentParser(description='safe calculator')
    p.add_argument('--precision', type=int, default=28)
    args = p.parse_args([])
    getcontext().prec = args.precision
    for expr in ('1 + 2 * 3', '0.1 + 0.2', '1 / 0', 'abs(-2)'):
        print(expr, '=', render(expr))

main()
