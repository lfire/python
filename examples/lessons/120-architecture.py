"""
第 120 讲 · 架构设计：领域分层、演进与重构
与教程正文一一对应的示例代码

课程页面：/advanced/architecture
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/120-architecture.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/120-architecture.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# memory True memory pass
# json True json pass
# annotation ['port']

import json
from typing import Protocol, runtime_checkable

@runtime_checkable
class RatePort(Protocol):
    def get(self, key: str) -> float: ...
    def put(self, key: str, value: float) -> None: ...

class MemoryAdapter:
    def __init__(self):
        self._d = {}
    def get(self, key):
        return self._d.get(key, 1.0)
    def put(self, key, value):
        self._d[key] = value

class JsonAdapter:
    def __init__(self):
        self._blob = '{}'
    def get(self, key):
        return json.loads(self._blob).get(key, 1.0)
    def put(self, key, value):
        d = json.loads(self._blob)
        d[key] = value
        self._blob = json.dumps(d)

class Pricing:
    def __init__(self, port: RatePort):
        self.port = port
    def total(self, base, key):
        return round(base * self.port.get(key), 2)

def contract(port, label):
    assert isinstance(port, RatePort), label
    port.put('vip', 0.8)
    svc = Pricing(port)
    assert svc.total(100.0, 'vip') == 80.0, label
    assert svc.total(100.0, 'guest') == 100.0, label
    return label + ' pass'

for label, port in [('memory', MemoryAdapter()), ('json', JsonAdapter())]:
    print(label, isinstance(port, RatePort), contract(port, label))
print('annotation', list(Pricing.__init__.__annotations__))

# ======================== 2. 对照写法 ========================
# 预期输出：
# compliant pass
# violating contract violated: got 0.0

class CompliantStore:
    def get(self, key):
        return 0.9

class ViolatingStore:
    def get(self, key):
        return 0.0

def verify(store):
    v = store.get('x')
    if v != 0.9:
        return 'contract violated: got ' + str(v)
    return 'pass'

print('compliant', verify(CompliantStore()))
print('violating', verify(ViolatingStore()))

# ======================== 3. 原理验证 ========================
# 预期输出：
# domain names ['round']
# coupled names ['json', 'round', 'sqlite3']
# fan-out delta 2

def pure_domain(base, rate):
    return round(base * rate, 2)

def coupled(base):
    import json
    import sqlite3
    return round(base * 1.0, 2)

print('domain names', sorted(pure_domain.__code__.co_names))
print('coupled names', sorted(coupled.__code__.co_names))
print('fan-out delta', len(set(coupled.__code__.co_names)) - len(set(pure_domain.__code__.co_names)))

# ======================== 4. 工程案例 ========================

import json
from typing import Protocol

class RatePort(Protocol):
    def get(self, key: str) -> float: ...
    def put(self, key: str, value: float) -> None: ...

class MemoryRate:
    def __init__(self):
        self.d = {}
    def get(self, key):
        return self.d.get(key, 1.0)
    def put(self, key, value):
        self.d[key] = value

class JsonRate:
    def __init__(self):
        self.blob = '{}'
    def get(self, key):
        return json.loads(self.blob).get(key, 1.0)
    def put(self, key, value):
        d = json.loads(self.blob)
        d[key] = value
        self.blob = json.dumps(d)

class PricingService:
    def __init__(self, rates: RatePort):
        self.rates = rates
    def quote(self, base, tier):
        return round(base * self.rates.get(tier), 2)

REGISTRY = {'memory': MemoryRate, 'json': JsonRate}

def contract_suite(make):
    svc = PricingService(make())
    svc.rates.put('vip', 0.8)
    assert svc.quote(100.0, 'vip') == 80.0
    assert svc.quote(100.0, 'new') == 100.0
    return type(svc.rates).__name__

def compose(impl):
    return PricingService(REGISTRY[impl]())

for name in REGISTRY:
    print(name, contract_suite(REGISTRY[name]))
print('quote', compose('json').quote(200.0, 'vip'))
