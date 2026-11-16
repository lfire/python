"""
第 071 讲 · 项目结构与 src 布局
与教程正文一一对应的示例代码

课程页面：/engineering/layout
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/071-layout.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/071-layout.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# flat layout resolves to root True
# src layout resolves to src True

import sys, os, tempfile

with tempfile.TemporaryDirectory() as root:
    flat_pkg = os.path.join(root, 'myapp')
    src_pkg = os.path.join(root, 'src', 'myapp')
    os.makedirs(flat_pkg)
    os.makedirs(src_pkg)
    for p in (flat_pkg, src_pkg):
        with open(os.path.join(p, '__init__.py'), 'w') as f:
            f.write('ORIGIN = ' + repr(os.path.dirname(p)) + chr(10))
    sys.path.insert(0, root)
    import myapp
    print('flat layout resolves to root', myapp.ORIGIN == root)
    del sys.modules['myapp']
    sys.path.remove(root)
    sys.path.insert(0, os.path.join(root, 'src'))
    import myapp
    print('src layout resolves to src', myapp.ORIGIN == os.path.join(root, 'src'))
    del sys.modules['myapp']
    sys.path.remove(os.path.join(root, 'src'))

# ======================== 2. 对照写法 ========================
# 预期输出：
# add via package 9
# __all__ ['add']
# star imports ['add']

import sys, os, tempfile

with tempfile.TemporaryDirectory() as root:
    pkg = os.path.join(root, 'webapp')
    os.makedirs(pkg)
    open(os.path.join(pkg, '__init__.py'), 'w').write(
        'from .core import add' + chr(10) + '__all__ = ["add"]' + chr(10))
    open(os.path.join(pkg, 'core.py'), 'w').write(
        'def add(a, b):' + chr(10) + '    return a + b' + chr(10))
    sys.path.insert(0, root)
    import webapp
    print('add via package', webapp.add(4, 5))
    print('__all__', webapp.__all__)
    ns = {}
    exec('from webapp import *', ns)
    print('star imports', sorted(k for k in ns if not k.startswith('__')))
    sys.path.remove(root)
    del sys.modules['webapp']

# ======================== 3. 原理验证 ========================
# 预期输出：
# implicit relative fails True

import sys, os, tempfile, importlib

with tempfile.TemporaryDirectory() as root:
    pkg = os.path.join(root, 'legacy')
    os.makedirs(pkg)
    open(os.path.join(pkg, '__init__.py'), 'w').write('')
    open(os.path.join(pkg, 'a.py'), 'w').write('VALUE = 7' + chr(10))
    open(os.path.join(pkg, 'b.py'), 'w').write('import a' + chr(10) + 'RESULT = a.VALUE' + chr(10))
    sys.path.insert(0, root)
    try:
        m = importlib.import_module('legacy.b')
        print('unexpected success', m.RESULT)
    except ModuleNotFoundError as e:
        print('implicit relative fails', "No module named 'a'" in str(e))
    sys.path.remove(root)

# ======================== 4. 工程案例 ========================

import pathlib, tempfile, sys, importlib

ROOT = pathlib.Path(tempfile.mkdtemp())
SRC = ROOT / 'src'
PKG = SRC / 'orderapp'
PKG.mkdir(parents=True)
(PKG / '__init__.py').write_text('from .core import total' + chr(10) + '__all__ = ["total"]' + chr(10))
(PKG / 'core.py').write_text('def total(xs):' + chr(10) + '    return sum(xs)' + chr(10))
(ROOT / 'pyproject.toml').write_text(
    '[build-system]' + chr(10) + 'requires = ["setuptools>=68"]' + chr(10)
    + 'build-backend = "setuptools.build_meta"' + chr(10))
(ROOT / 'README.md').write_text('# orderapp' + chr(10))

sys.path.insert(0, str(SRC))
pkg = importlib.import_module('orderapp')
print('import from src ok', pkg.total([1, 2, 3]))
print('public api', pkg.__all__)
print('layout files', sorted(p.name for p in ROOT.iterdir()))
sys.path.remove(str(SRC))
