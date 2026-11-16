"""
第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建
与教程正文一一对应的示例代码

课程页面：/engineering/deps
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/072-deps.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/072-deps.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# pinned ['2.32.3', '2024.8.30']
# hash bits 256
# exact match ok True
# tampered rejected True
# unpinned upgrade rejected True

import hashlib

def digest(body):
    return hashlib.sha256(body.encode()).hexdigest()

lock = [
    ('requests', '2.32.3', digest('requests-2.32.3')),
    ('certifi', '2024.8.30', digest('certifi-2024.8.30')),
]

def verify(pkg, payload):
    return digest(payload) == pkg[2]

print('pinned', [v for _, v, _ in lock])
print('hash bits', len(lock[0][2]) * 4)
print('exact match ok', verify(lock[0], 'requests-2.32.3'))
print('tampered rejected', not verify(lock[0], 'requests-2.32.3-tampered'))
print('unpinned upgrade rejected', not verify(lock[0], 'requests-2.33.0'))

# ======================== 2. 对照写法 ========================
# 预期输出：
# name demo-pkg
# version 1.2.3
# requires-python >=3.9
# requires ['requests>=2.28']

import sys, os, tempfile
import importlib.metadata as im
import importlib
importlib.invalidate_caches()

with tempfile.TemporaryDirectory() as d:
    di = os.path.join(d, 'demo_pkg-1.2.3.dist-info')
    os.makedirs(di)
    with open(os.path.join(di, 'METADATA'), 'w') as f:
        f.write('Metadata-Version: 2.1' + chr(10) + 'Name: demo-pkg' + chr(10)
                + 'Version: 1.2.3' + chr(10) + 'Requires-Python: >=3.9' + chr(10)
                + 'Requires-Dist: requests>=2.28' + chr(10))
    sys.path.insert(0, d)
    dist = im.distribution('demo-pkg')
    print('name', dist.metadata['Name'])
    print('version', dist.version)
    print('requires-python', dist.metadata['Requires-Python'])
    print('requires', dist.requires)
    sys.path.remove(d)

# ======================== 3. 原理验证 ========================
# 预期输出：
# installed {'app': '1.0', 'lib': '1.5'}
# conflict detected True

import sys, os, tempfile
import importlib.metadata as im
import importlib

def make_dist(root, name, version, requires_lines):
    di = os.path.join(root, name + '-' + version + '.dist-info')
    os.makedirs(di)
    lines = ['Metadata-Version: 2.1', 'Name: ' + name, 'Version: ' + version]
    lines += ['Requires-Dist: ' + r for r in requires_lines]
    open(os.path.join(di, 'METADATA'), 'w').write(chr(10).join(lines) + chr(10))

importlib.invalidate_caches()
with tempfile.TemporaryDirectory() as d:
    make_dist(d, 'app', '1.0', ['lib>=2.0'])
    make_dist(d, 'lib', '1.5', [])
    sys.path.insert(0, d)
    versions = {n: im.version(n) for n in ('app', 'lib')}
    print('installed', versions)
    need = 2
    have = int(versions['lib'].split('.')[0])
    print('conflict detected', have < need)
    sys.path.remove(d)

# ======================== 4. 工程案例 ========================

import hashlib, json

def sha(body):
    return hashlib.sha256(body.encode()).hexdigest()

LOCK = [
    ('httpx', '0.27.0', sha('httpx-0.27.0')),
    ('certifi', '2024.7.4', sha('certifi-2024.7.4')),
    ('idna', '3.7', sha('idna-3.7')),
]

def install(pkg, payload):
    name, version, expected = pkg
    if sha(payload) != expected:
        raise ValueError('hash mismatch for ' + name)
    return name + '==' + version

def build_manifest(lock, artifacts):
    pinned = [install(pkg, payload) for pkg, payload in zip(lock, artifacts)]
    return {'python': '3.13', 'packages': pinned, 'hashes': True}

artifacts = ['httpx-0.27.0', 'certifi-2024.7.4', 'idna-3.7']
print(json.dumps(build_manifest(LOCK, artifacts), sort_keys=True))
try:
    build_manifest(LOCK, ['httpx-0.27.0-evil', 'certifi-2024.7.4', 'idna-3.7'])
except ValueError as e:
    print('rejected', str(e))
