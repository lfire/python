"""
第 080 讲 · 打包与发布：pyproject、wheel 与 PyPI
与教程正文一一对应的示例代码

课程页面：/engineering/packaging
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/080-packaging.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/080-packaging.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# wheel entries 6
# has METADATA True
# Name field demo_pkg
# Requires-Dist requests>=2.28
# entry point demo_pkg.cli:main

import zipfile, os, tempfile, email

name = 'demo_pkg'
version = '1.2.3'
wheel = name + '-' + version + '-py3-none-any.whl'
dist_info = name + '-' + version + '.dist-info'

metadata = chr(10).join([
    'Metadata-Version: 2.1',
    'Name: ' + name,
    'Version: ' + version,
    'Requires-Python: >=3.9',
    'Requires-Dist: requests>=2.28',
])
wheel_meta = chr(10).join([
    'Wheel-Version: 1.0',
    'Generator: demo',
    'Root-Is-Purelib: true',
    'Tag: py3-none-any',
])
entry_points = '[console_scripts]' + chr(10) + 'demo-cli = demo_pkg.cli:main' + chr(10)

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, wheel)
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr(dist_info + '/METADATA', metadata)
        z.writestr(dist_info + '/WHEEL', wheel_meta)
        z.writestr(dist_info + '/entry_points.txt', entry_points)
        z.writestr(dist_info + '/RECORD', '')
        z.writestr(name + '/__init__.py', 'VERSION = "1.2.3"' + chr(10))
        z.writestr(name + '/cli.py', 'def main():' + chr(10) + '    return 0' + chr(10))
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        print('wheel entries', len(names))
        print('has METADATA', dist_info + '/METADATA' in names)
        msg = email.message_from_bytes(z.read(dist_info + '/METADATA'))
        print('Name field', msg['Name'])
        print('Requires-Dist', msg['Requires-Dist'])
        ep = z.read(dist_info + '/entry_points.txt').decode()
        print('entry point', ep.split('=')[1].strip())

# ======================== 2. 对照写法 ========================
# 预期输出：
# entry found True
# target demo_cli_xyz:main
# dist version 1.2.3

import sys, os, tempfile
import importlib.metadata as im
import importlib
importlib.invalidate_caches()

with tempfile.TemporaryDirectory() as d:
    di = os.path.join(d, 'demo_cli_xyz-1.2.3.dist-info')
    os.makedirs(di)
    open(os.path.join(di, 'METADATA'), 'w').write('Metadata-Version: 2.1' + chr(10) + 'Name: demo-cli-xyz' + chr(10) + 'Version: 1.2.3' + chr(10))
    open(os.path.join(di, 'entry_points.txt'), 'w').write('[console_scripts]' + chr(10) + 'demo-xyz = demo_cli_xyz:main' + chr(10))
    sys.path.insert(0, d)
    dist = im.distribution('demo-cli-xyz')
    eps = [e for e in dist.entry_points if e.group == 'console_scripts']
    print('entry found', len(eps) == 1)
    print('target', eps[0].value)
    print('dist version', dist.version)
    sys.path.remove(d)

# ======================== 3. 原理验证 ========================
# 预期输出：
# wheel vs sdist [True, True, False]
# pure tag ['py3', 'none', 'any']
# platform tag macosx_11_0_arm64
# python 3 13

import sys

wheels = ['demo-1.2.3-py3-none-any.whl',
          'demo-1.2.3-cp313-cp313-macosx_11_0_arm64.whl',
          'demo-1.2.3.tar.gz']

def is_wheel(n):
    return n.endswith('.whl')

def tags(n):
    return n[:-4].split('-')[-3:]

print('wheel vs sdist', [is_wheel(w) for w in wheels])
print('pure tag', tags(wheels[0]))
print('platform tag', tags(wheels[1])[-1])
print('python', sys.version_info[0], sys.version_info[1])

# ======================== 4. 工程案例 ========================

import zipfile, os, tempfile, email, hashlib

NAME, VERSION = 'reportkit', '0.4.0'
di = NAME + '-' + VERSION + '.dist-info'
metadata = chr(10).join([
    'Metadata-Version: 2.1', 'Name: ' + NAME, 'Version: ' + VERSION,
    'Requires-Python: >=3.10', 'Requires-Dist: requests>=2.31',
    'Summary: report helpers'])
entry = '[console_scripts]' + chr(10) + 'report = reportkit.cli:main' + chr(10)

with tempfile.TemporaryDirectory() as d:
    whl = os.path.join(d, NAME + '-' + VERSION + '-py3-none-any.whl')
    files = {
        di + '/METADATA': metadata,
        di + '/WHEEL': 'Wheel-Version: 1.0' + chr(10) + 'Root-Is-Purelib: true' + chr(10) + 'Tag: py3-none-any' + chr(10),
        di + '/entry_points.txt': entry,
        NAME + '/__init__.py': '__version__ = "0.4.0"' + chr(10),
        NAME + '/cli.py': 'def main():' + chr(10) + '    print("report")' + chr(10),
    }
    record_lines = []
    with zipfile.ZipFile(whl, 'w') as z:
        for path, content in files.items():
            data = content.encode()
            z.writestr(path, data)
            record_lines.append(path + ',sha256=' + hashlib.sha256(data).hexdigest()[:12] + ',' + str(len(data)))
        z.writestr(di + '/RECORD', chr(10).join(record_lines) + chr(10))
    with zipfile.ZipFile(whl) as z:
        msg = email.message_from_bytes(z.read(di + '/METADATA'))
        print('name', msg['Name'], 'version', msg['Version'])
        print('requires', msg['Requires-Dist'])
        print('pure wheel', 'true' in z.read(di + '/WHEEL').decode())
        print('record rows', len(z.read(di + '/RECORD').decode().splitlines()))
