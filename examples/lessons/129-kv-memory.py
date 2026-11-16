"""
第 129 讲 · 实战 08 · KV 贯穿线 ① 内存版与接口抽象
与教程正文一一对应的示例代码

课程页面：/projects/kv-memory
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/129-kv-memory.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/129-kv-memory.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# contract ok
# set/get None 2
# del True
# bad op ValueError

import threading

class KeyNotFound(KeyError):
    pass

class MemoryEngine:
    def __init__(self):
        self.data, self.exp, self.now = {}, {}, 0
        self.lock = threading.Lock()
    def _live(self, key):
        if self.exp.get(key, -1) != -1 and self.exp[key] <= self.now:
            del self.data[key]
            del self.exp[key]
            return False
        return key in self.data
    def get(self, key):
        with self.lock:
            if not self._live(key):
                raise KeyNotFound(key)
            return self.data[key]
    def set(self, key, value, ttl=0):
        with self.lock:
            self.data[key] = value
            self.exp[key] = self.now + ttl if ttl else -1
    def delete(self, key):
        with self.lock:
            if not self._live(key):
                raise KeyNotFound(key)
            del self.data[key]
            return True

def execute(eng, op, key, value='', ttl=0):
    if op == 'SET': return eng.set(key, value, ttl)
    if op == 'GET': return eng.get(key)
    if op == 'DEL': return eng.delete(key)
    raise ValueError('unknown op ' + op)

def contract(eng):
    eng.set('k', 'v', ttl=3)
    assert eng.get('k') == 'v'
    eng.now += 3
    try:
        eng.get('k')
    except KeyNotFound:
        return 'ok'
    return 'violation'

e = MemoryEngine()
print('contract', contract(e))
print('set/get', execute(e, 'SET', 'b', '2'), execute(e, 'GET', 'b'))
print('del', execute(e, 'DEL', 'b'))
try:
    execute(e, 'PING', 'x')
except ValueError as err:
    print('bad op', type(err).__name__)

# ======================== 2. 对照写法 ========================
# 预期输出：
# memory pass
# logged pass

class Memory:
    def __init__(self): self.d = {}
    def get(self, k):
        if k not in self.d: raise KeyError(k)
        return self.d[k]
    def set(self, k, v): self.d[k] = v

class Logged:
    def __init__(self): self.d, self.log = {}, []
    def get(self, k):
        self.log.append('get ' + k)
        if k not in self.d: raise KeyError(k)
        return self.d[k]
    def set(self, k, v):
        self.log.append('set ' + k)
        self.d[k] = v

def suite(make):
    e = make()
    e.set('a', '1')
    assert e.get('a') == '1'
    try:
        e.get('missing')
    except KeyError:
        return 'pass'
    return 'violation'

print('memory', suite(Memory))
print('logged', suite(Logged))

# ======================== 3. 原理验证 ========================
# 预期输出：
# multi-bytecode True
# guarded count 500
# lock type lock

import dis, threading
from concurrent.futures import ThreadPoolExecutor

def bump(box, lock):
    with lock:
        box[0] += 1

ops = [i.opname for i in dis.get_instructions(bump)]
print('multi-bytecode', 'BINARY_OP' in ops and 'STORE_SUBSCR' in ops)
box, lock = [0], threading.Lock()
with ThreadPoolExecutor(4) as ex:
    list(ex.map(lambda _: bump(box, lock), range(500)))
print('guarded count', box[0])
print('lock type', type(lock).__name__)

# ======================== 4. 工程案例 ========================

from typing import Protocol

class Engine(Protocol):
    def get(self, key: str) -> str: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> bool: ...

class MemoryEngine:
    def __init__(self): self.d = {}
    def get(self, key):
        if key not in self.d: raise KeyError(key)
        return self.d[key]
    def set(self, key, value): self.d[key] = value
    def delete(self, key):
        if key not in self.d: raise KeyError(key)
        del self.d[key]
        return True

class Service:
    def __init__(self, engine: Engine): self.engine = engine
    def execute(self, op, key, value=''):
        if op == 'SET': return self.engine.set(key, value)
        if op == 'GET': return self.engine.get(key)
        if op == 'DEL': return self.engine.delete(key)
        raise ValueError(op)

def contract(make):
    svc = Service(make())
    svc.execute('SET', 'k', 'v')
    assert svc.execute('GET', 'k') == 'v'
    assert svc.execute('DEL', 'k') is True
    return type(svc.engine).__name__

def compose(name):
    return Service({'memory': MemoryEngine}[name]())

print('contract', contract(MemoryEngine))
print('service', type(compose('memory').engine).__name__)
