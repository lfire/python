"""
第 116 讲 · 导入系统源码与 import hook
与教程正文一一对应的示例代码

课程页面：/advanced/import-source
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/116-import-source.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/116-import-source.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# fractions_asked True
# decimal_asked True
# cached_not_reasked True
# origin_is_py True

import sys, importlib.abc, importlib

class Spy(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.seen = []
    def find_spec(self, fullname, path=None, target=None):
        self.seen.append(fullname)
        return None

spy = Spy()
sys.meta_path.insert(0, spy)
importlib.import_module('fractions')
print('fractions_asked', 'fractions' in spy.seen)
print('decimal_asked', 'decimal' in spy.seen)
import fractions
print('cached_not_reasked', spy.seen.count('fractions') == 1)
print('origin_is_py', fractions.__spec__.origin.endswith('.py'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# decimal_before False
# result 1.1
# decimal_after True

import sys

def heavy():
    import decimal
    return decimal.Decimal('1.1')

print('decimal_before', 'decimal' in sys.modules)
print('result', str(heavy()))
print('decimal_after', 'decimal' in sys.modules)

# ======================== 3. 原理验证 ========================
# 预期输出：
# is_package True
# has_location True
# loader SourceFileLoader
# cache_tag cpython-313
# json_cached True
# same_origin True

import importlib.util, sys

spec = importlib.util.find_spec('json')
print('is_package', spec.submodule_search_locations is not None)
print('has_location', spec.has_location)
print('loader', type(spec.loader).__name__)
print('cache_tag', sys.implementation.cache_tag)
print('json_cached', 'json' in sys.modules)
spec2 = importlib.util.find_spec('json')
print('same_origin', spec.origin == spec2.origin)

# ======================== 4. 工程案例 ========================

import sys, time, importlib.abc, importlib.util

class PluginFinder(importlib.abc.MetaPathFinder):
    def __init__(self, sources):
        self.sources = sources
        self.calls = 0
    def find_spec(self, fullname, path=None, target=None):
        self.calls += 1
        if fullname not in self.sources:
            return None
        return importlib.util.spec_from_loader(fullname, loader=None)

src = {'plug_demo': 'VALUE = 42' + chr(10)}
f = PluginFinder(src)
sys.meta_path.insert(0, f)
t0 = time.perf_counter()
importlib.invalidate_caches()
cost = time.perf_counter() - t0
print('allowed', sorted(src))
print('find_spec_calls', f.calls >= 0)
print('invalidate_cost_positive', cost >= 0)
sys.meta_path.remove(f)
