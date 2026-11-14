"""
第 049 讲 · CPython 编译流程：AST 到字节码
与教程正文一一对应的示例代码

课程页面：/core/compile-pipeline
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/049-compile-pipeline.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/049-compile-pipeline.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# type Module
# body ['Assign', 'Expr']
# target x
# op Add
# consts (3, None)
# names ('x', 'print')
# folded consts (3,)
# mode eval returns 3

import ast

src = 'x = 1 + 2' + chr(10) + 'print(x)'
tree = ast.parse(src)
print('type', type(tree).__name__)
print('body', [type(n).__name__ for n in tree.body])
print('target', tree.body[0].targets[0].id)
print('op', type(tree.body[0].value.op).__name__)
code = compile(src, 'demo.py', 'exec')
print('consts', code.co_consts)
print('names', code.co_names)
folded = compile('1 + 2', 'f', 'eval')
print('folded consts', folded.co_consts)
print('mode eval returns', eval(folded))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# rewritten 20 + 10
# result 30

import ast

tree = ast.parse('10 + 5', mode='eval')
class Double(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, int):
            return ast.copy_location(ast.Constant(value=node.value * 2), node)
        return node
new = Double().visit(tree)
ast.fix_missing_locations(new)
print('rewritten', ast.unparse(new))
print('result', eval(compile(new, 'r', 'eval')))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# no binary op True
# has return True
# folded consts (3,)
# co_names ()
# opt2 removes assert True
# sys module ok True

import dis, sys

lit = compile('1 + 2', 'c', 'eval')
ops = [i.opname for i in dis.get_instructions(lit)]
print('no binary op', not any(o in ops for o in ('BINARY_OP', 'BINARY_ADD')))
print('has return', any(o in ops for o in ('RETURN_VALUE', 'RETURN_CONST')))
print('folded consts', lit.co_consts)
print('co_names', lit.co_names)
print('opt2 removes assert', len(compile('assert False', 'a', 'exec', optimize=2).co_code) < len(compile('assert False', 'a', 'exec', optimize=0).co_code))
print('sys module ok', hasattr(sys, 'getsizeof'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import ast

SOURCE = 'def load(raw):' + chr(10) + '    return eval(raw)' + chr(10) + 'def ok(x):' + chr(10) + '    return int(x)'
class EvalFinder(ast.NodeVisitor):
    def __init__(self):
        self.hits = []
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'eval':
            self.hits.append(('eval', node.lineno, node.col_offset))
        self.generic_visit(node)

tree = ast.parse(SOURCE)
finder = EvalFinder()
finder.visit(tree)
print('functions', [n.name for n in tree.body if isinstance(n, ast.FunctionDef)])
print('unsafe calls', finder.hits)
print('literal_eval safe', ast.literal_eval('[1, 2, 3]'))
try:
    ast.literal_eval('__import__(' + chr(34) + 'os' + chr(34) + ')')
except ValueError:
    print('rejected by literal_eval')
