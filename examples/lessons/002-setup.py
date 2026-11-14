"""
第 002 讲 · 环境与工具链：解释器、虚拟环境与编辑器
与教程正文一一对应的示例代码

课程页面：/guide/setup
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/002-setup.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/002-setup.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# keys ['cwd', 'executable', 'in_venv', 'site_count', 'version']
# in_venv False
# version_major 3
# site_ok True
# cwd_abs True

import os, sys, site

report = {
    'version': '%d.%d.%d' % sys.version_info[:3],
    'executable': sys.executable,
    'in_venv': sys.prefix != sys.base_prefix,
    'cwd': os.getcwd(),
    'site_count': len(site.getsitepackages()),
}

print('keys', sorted(report))
print('in_venv', report['in_venv'])
print('version_major', sys.version_info[0])
print('site_ok', report['site_count'] >= 1)
print('cwd_abs', os.path.isabs(report['cwd']))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# impl_name cpython
# version_len True
# hexversion_positive True
# flags_optimize 0
# flags_isolated False
# flags_no_site False
# path_ordered True

import sys
f = sys.flags
print('impl_name', sys.implementation.name)
print('version_len', len(sys.version_info) >= 5)
print('hexversion_positive', sys.hexversion > 0)
print('flags_optimize', f.optimize)
print('flags_isolated', bool(f.isolated))
print('flags_no_site', bool(f.no_site))
print('path_ordered', isinstance(sys.path, list))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# spec_found True
# is_package True
# origin_init True
# cached True
# has_dumps True

import sys, importlib.util, importlib
spec = importlib.util.find_spec('json')
print('spec_found', spec is not None)
print('is_package', spec.submodule_search_locations is not None)
print('origin_init', spec.origin.endswith('__init__.py'))
mod = importlib.import_module('json')
print('cached', mod is sys.modules['json'])
print('has_dumps', hasattr(mod, 'dumps'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import sys, os, tempfile, hashlib, importlib.util

def env_checks(least, deps, lock_bytes):
    checks = {}
    checks['version'] = sys.version_info >= least
    checks['venv'] = sys.prefix != sys.base_prefix
    checks['deps'] = all(importlib.util.find_spec(m) is not None for m in deps)
    checks['lock_sha'] = hashlib.sha256(lock_bytes).hexdigest()[:12]
    return checks

with tempfile.NamedTemporaryFile(delete=False) as tmp:
    tmp.write(b'requests==2.32.3' + bytes([10]))
    path = tmp.name
with open(path, 'rb') as f:
    blob = f.read()
os.unlink(path)

r = env_checks((3, 8), ['json', 'hashlib'], blob)
print('version_ok', r['version'])
print('deps_ok', r['deps'])
print('lock_sha_len', len(r['lock_sha']))
print('all_importable', r['deps'] and r['version'])
