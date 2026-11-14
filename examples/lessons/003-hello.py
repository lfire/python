"""
第 003 讲 · 第一行 Python：从源码到字节码再到执行
与教程正文一一对应的示例代码

课程页面：/guide/hello
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/003-hello.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/003-hello.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# type code
# consts (42, None)
# names ('x', 'print')
# nbytes True
# 42

src = 'x = 6 * 7' + chr(10) + 'print(x)'
code_obj = compile(src, '<demo>', 'exec')
print('type', type(code_obj).__name__)
print('consts', code_obj.co_consts)
print('names', code_obj.co_names)
print('nbytes', len(code_obj.co_code) > 0)
exec(code_obj)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# exec_returns None
# eval_returns 3
# exec_has_none_const True
# eval_consts (3,)
# eval_names ()

exec_code = compile('1 + 2', '<x>', 'exec')
eval_code = compile('1 + 2', '<y>', 'eval')
print('exec_returns', exec(exec_code))
print('eval_returns', eval(eval_code))
print('exec_has_none_const', None in exec_code.co_consts)
print('eval_consts', eval_code.co_consts)
print('eval_names', eval_code.co_names)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# fold_consts (7,)
# live_consts ()
# live_names ('a', 'b')
# has_binary_op True
# in_pycache True
# ends_pyc True

import dis, importlib.util
a = compile('1 + 2 * 3', '<a>', 'eval')
b = compile('a + b', '<b>', 'eval')
print('fold_consts', a.co_consts)
print('live_consts', b.co_consts)
print('live_names', b.co_names)
print('has_binary_op', any(i.opname == 'BINARY_OP' for i in dis.get_instructions(b)))
cache = importlib.util.cache_from_source('pkg/mod.py')
print('in_pycache', '__pycache__' in cache)
print('ends_pyc', cache.endswith('.pyc'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import os, dis, importlib.util, ast, tempfile

def audit(src, filename, key_const):
    tree = compile(src, filename, 'exec', ast.PyCF_ONLY_AST)
    node_count = sum(1 for _ in ast.walk(tree))
    code_obj = compile(src, filename, 'exec')
    ops = [i.opname for i in dis.get_instructions(code_obj)]
    return {
        'nodes': node_count,
        'const_ok': key_const in code_obj.co_consts,
        'instrs': len(ops),
        'pyc': importlib.util.cache_from_source(filename),
        'magic_len': len(importlib.util.MAGIC_NUMBER),
    }

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, 'demo_mod.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('LIMIT = 6 * 7' + chr(10))
    r = audit('LIMIT = 6 * 7' + chr(10), path, 42)
    print('const_ok', r['const_ok'])
    print('instrs_positive', r['instrs'] > 0)
    print('pyc_in_cache', '__pycache__' in r['pyc'])
    print('magic_len', r['magic_len'])
