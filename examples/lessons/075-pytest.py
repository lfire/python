"""
第 075 讲 · 单元测试：pytest、fixture 与参数化
与教程正文一一对应的示例代码

课程页面：/engineering/pytest
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/075-pytest.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/075-pytest.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# cases 4
# all passed True
# fixture content seed
# cleaned up True

import tempfile, os
from contextlib import contextmanager

CASES = [(2, 3, 5), (0, 0, 0), (-1, 1, 0), (10, -3, 7)]

def add(a, b):
    return a + b

results = []
for a, b, expected in CASES:
    got = add(a, b)
    results.append((a, b, got == expected))
print('cases', len(results))
print('all passed', all(ok for *_, ok in results))

@contextmanager
def tmp_file():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'data.txt')
        with open(path, 'w') as f:
            f.write('seed')
        yield path

with tmp_file() as p:
    with open(p) as f:
        print('fixture content', f.read())
print('cleaned up', not os.path.exists(p))

# ======================== 2. 对照写法 ========================
# 预期输出：
# is Assert node True
# test is Compare True
# left is Call True
# inside patch True
# after patch restored False

import ast
from unittest.mock import patch

tree = ast.parse('assert add(2, 3) == 6')
node = tree.body[0]
print('is Assert node', isinstance(node, ast.Assert))
print('test is Compare', isinstance(node.test, ast.Compare))
print('left is Call', isinstance(node.test.left, ast.Call))

class Config:
    DEBUG = False

with patch.object(Config, 'DEBUG', True):
    print('inside patch', Config.DEBUG)
print('after patch restored', Config.DEBUG)

# ======================== 3. 原理验证 ========================
# 预期输出：
# assert nodes 1
# more instr True
# flags.optimize 0
# optimize=0 AssertionError
# optimize=1 passed

import ast, dis, sys

src = 'assert x > 0' + chr(10) + 'out = "passed"'
print('assert nodes', sum(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(src))))
code0 = compile(src, '<s>', 'exec', optimize=0)
code1 = compile(src, '<s>', 'exec', optimize=1)
print('more instr', len(list(dis.get_instructions(code0))) > len(list(dis.get_instructions(code1))))
print('flags.optimize', sys.flags.optimize)

def run(x, code):
    ns = {'x': x}
    exec(code, ns)
    return ns['out']

try:
    run(-1, code0)
except AssertionError:
    print('optimize=0 AssertionError')
print('optimize=1', run(-1, code1))

# ======================== 4. 工程案例 ========================

FIXTURES = {}

def fixture(scope='function'):
    def deco(fn):
        FIXTURES[fn.__name__] = (scope, fn)
        return fn
    return deco

@fixture(scope='session')
def db():
    return {'users': ['ann', 'bob'], 'port': 5432}

def parametrize(cases):
    def deco(fn):
        def run():
            return [fn(*case) for case in cases]
        return run
    return deco

@parametrize([(2, 3, 5), (0, 0, 0), (-1, 1, 0)])
def test_add(a, b, expected):
    assert a + b == expected, (a, b)
    return True

print('fixtures', sorted(FIXTURES))
print('db scope', FIXTURES['db'][0])
print('db port', FIXTURES['db'][1]()['port'])
print('param results', test_add())
