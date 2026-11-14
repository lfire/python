"""
第 076 讲 · Mock 与测试替身：时间、网络与随机
与教程正文一一对应的示例代码

课程页面：/engineering/mock
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/076-mock.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/076-mock.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# baseline hi real
# patch definition site hi real
# patch use site hi FAKE

import sys, os, tempfile
from unittest.mock import patch

with tempfile.TemporaryDirectory() as d:
    open(os.path.join(d, 'clock.py'), 'w').write('def now():' + chr(10) + '    return "real"' + chr(10))
    open(os.path.join(d, 'service.py'), 'w').write('from clock import now' + chr(10) + 'def greet():' + chr(10) + '    return "hi " + now()' + chr(10))
    sys.path.insert(0, d)
    import service, clock
    print('baseline', service.greet())

    with patch.object(clock, 'now', return_value='FAKE'):
        print('patch definition site', service.greet())

    with patch.object(service, 'now', return_value='FAKE'):
        print('patch use site', service.greet())
    sys.path.remove(d)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# id1 101-7
# id2 102-7
# clock advanced 102
# seeded reproducible True

import random

class FakeClock:
    def __init__(self, start):
        self.t = start
    def now(self):
        self.t += 1
        return self.t

class FakeRNG:
    def __init__(self, values):
        self.values = list(values)
    def randrange(self, n):
        return self.values.pop(0) % n

def make_id(clock, rng):
    return str(clock.now()) + '-' + str(rng.randrange(100))

c = FakeClock(100)
r = FakeRNG([7, 7, 7])
print('id1', make_id(c, r))
print('id2', make_id(c, r))
print('clock advanced', c.t)
print('seeded reproducible', random.Random(7).randrange(100) == random.Random(7).randrange(100))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# bare mock invents attr True
# autospec rejects typo True
# autospec call ok fake

from unittest.mock import Mock, create_autospec

class Service:
    def fetch(self, key):
        return 'real'

m = Mock()
print('bare mock invents attr', hasattr(m, 'fetchh'))
m.fetchh()
safe = create_autospec(Service, instance=True)
try:
    safe.fetchh()
except AttributeError:
    print('autospec rejects typo', True)
safe.fetch.return_value = 'fake'
print('autospec call ok', safe.fetch('k'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import random

class FakeHTTP:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []
    def get(self, url):
        self.calls.append(url)
        return self.pages.get(url, '')

class Clock:
    def __init__(self, start=0):
        self.t = start
    def now(self):
        self.t += 1
        return self.t

def collect(http, clock, rng, urls):
    rows = []
    for url in urls:
        body = http.get(url)
        rows.append((url, len(body), clock.now(), rng.randrange(1000)))
    return rows

http = FakeHTTP({'/a': 'alpha', '/b': 'beta'})
clock = Clock(100)
rng = random.Random(7)
rows = collect(http, clock, rng, ['/a', '/b', '/missing'])
print('rows', len(rows))
print('http calls', http.calls)
print('clock end', clock.t)
print('seeded reproducible', random.Random(7).randrange(1000) == random.Random(7).randrange(1000))
