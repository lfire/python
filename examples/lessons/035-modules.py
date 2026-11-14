"""
第 035 讲 · 模块与包：import 机制与循环导入
与教程正文一一对应的示例代码

课程页面：/functions/modules
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/035-modules.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/035-modules.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# True True
# module json
# json True
# 42 True demo
# True

import sys, importlib, types

first = importlib.import_module('json')
second = importlib.import_module('json')
print(first is second, 'json' in sys.modules)
print(type(first).__name__, first.__name__)
print(first.__spec__.name, hasattr(first, '__file__'))

m = types.ModuleType('demo')
m.value = 42
sys.modules['demo'] = m
import demo
print(demo.value, demo is m, demo.__name__)
print(demo.__dict__ is m.__dict__)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# 99 ['VALUE']
# True True

import sys, tempfile, pathlib, importlib

root = tempfile.mkdtemp()
p = pathlib.Path(root)
(p / 'pkg').mkdir()
(p / 'pkg' / '__init__.py').write_text('from .mod import VALUE' + chr(10) + '__all__ = ' + str(['VALUE']) + chr(10))
(p / 'pkg' / 'mod.py').write_text('VALUE = 99' + chr(10))
sys.path.insert(0, root)
import pkg
print(pkg.VALUE, pkg.__all__)
print(pkg.__file__ is not None, 'pkg.mod' in sys.modules)
sys.path.remove(root)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# SourceFileLoader json
# True
# True
# True True

import sys, importlib

mod = importlib.import_module('json')
print(type(mod.__loader__).__name__, mod.__spec__.name)
print(mod.__spec__.origin is not None)
print('PathFinder' in [m.__name__ for m in sys.meta_path])
print(sys.modules['json'] is mod, importlib.import_module('json') is mod)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import sys, tempfile, pathlib, importlib

root = tempfile.mkdtemp()
d = pathlib.Path(root)
(d / 'm_a.py').write_text('import m_b' + chr(10) + 'class A:' + chr(10) + '    peer = m_b.B' + chr(10))
(d / 'm_b.py').write_text('import m_a' + chr(10) + 'X = m_a.A' + chr(10) + 'class B:' + chr(10) + '    pass' + chr(10))
sys.path.insert(0, root)
try:
    importlib.import_module('m_a')
except AttributeError as e:
    print(type(e).__name__, 'circular' in str(e))

(d / 'm_types.py').write_text('class B:' + chr(10) + '    pass' + chr(10))
(d / 'm_a2.py').write_text('from m_types import B' + chr(10) + 'class A2:' + chr(10) + '    peer = B' + chr(10))
print(importlib.import_module('m_a2').A2.peer.__name__)
