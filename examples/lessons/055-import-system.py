"""
第 055 讲 · 导入系统源码级：finder、loader 与缓存
与教程正文一一对应的示例代码

课程页面：/core/import-system
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/055-import-system.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/055-import-system.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# 3 2
# memory:virtual_cfg MemoryLoader
# True

import sys
import importlib.abc
import importlib.util

class MemoryLoader(importlib.abc.Loader):
    def __init__(self, source):
        self.source = source
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        exec(self.source, module.__dict__)

class MemoryFinder(importlib.abc.MetaPathFinder):
    def __init__(self, sources):
        self.sources = sources
    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.sources:
            return importlib.util.spec_from_loader(
                fullname, MemoryLoader(self.sources[fullname]),
                origin='memory:' + fullname)
        return None

SOURCES = {'virtual_cfg': 'TIMEOUT = 3' + chr(10) + 'RETRIES = 2'}
sys.meta_path.insert(0, MemoryFinder(SOURCES))

import virtual_cfg
print(virtual_cfg.TIMEOUT, virtual_cfg.RETRIES)
print(virtual_cfg.__spec__.origin, type(virtual_cfg.__loader__).__name__)
print('virtual_cfg' in sys.modules)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# manual True 1
# cached 99
# ModuleNotFoundError True

import sys
import types
import importlib

name = '_cfg_demo_55'
m = types.ModuleType(name)
m.VALUE = 1
sys.modules[name] = m
print('manual', importlib.import_module(name) is m, m.VALUE)
m.VALUE = 99
print('cached', importlib.import_module(name).VALUE)
sys.modules['_blocked_55'] = None
try:
    importlib.import_module('_blocked_55')
except ModuleNotFoundError as e:
    print(type(e).__name__, 'halted' in str(e))

# ======================== 3. 原理验证 ========================
# 预期输出：
# py 3 13
# meta_path ['BuiltinImporter', 'FrozenImporter', 'PathFinder']
# finder_sig (fullname, path=None, target=None)
# pyc demo.cpython-313.pyc
# json_is_package True

import sys
import importlib.util
import inspect

print('py', sys.version_info[0], sys.version_info[1])
print('meta_path', [f.__name__ for f in sys.meta_path])
print('finder_sig', str(inspect.signature(sys.meta_path[2].find_spec)))
print('pyc', importlib.util.cache_from_source('demo.py').split('/')[-1])
print('json_is_package', importlib.util.find_spec('json').submodule_search_locations is not None)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import sys
import importlib.abc
import importlib.util
import threading

class RegistryLoader(importlib.abc.Loader):
    def __init__(self, registry, lock):
        self.registry = registry
        self.lock = lock
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        with self.lock:
            source = self.registry[module.__spec__.name]
        exec(compile(source, module.__spec__.origin, 'exec'), module.__dict__)

class RegistryFinder(importlib.abc.MetaPathFinder):
    def __init__(self, registry, lock):
        self.registry = registry
        self.lock = lock
    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.registry:
            return importlib.util.spec_from_loader(
                fullname, RegistryLoader(self.registry, self.lock),
                origin='registry:' + fullname)
        return None

def install(registry):
    lock = threading.Lock()
    sys.meta_path.insert(0, RegistryFinder(registry, lock))

if __name__ == '__main__':
    reg = {
        'cfg_limit': 'LIMIT = 10' + chr(10) + 'def allow(n): return n <= LIMIT',
        'cfg_tags': "TAGS = ('a', 'b')",
    }
    install(reg)
    import cfg_limit
    import cfg_tags
    print(cfg_limit.allow(7), cfg_limit.allow(99))
    print(cfg_tags.TAGS, 'cached', 'cfg_tags' in sys.modules)
