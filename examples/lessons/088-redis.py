"""
第 088 讲 · Redis 缓存：穿透、击穿、雪崩与分布式锁
与教程正文一一对应的示例代码

课程页面：/server/redis
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/088-redis.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/088-redis.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# {'id': 1}
# {'id': 1}
# None
# None
# hits 2 misses 2
# ttl key1 354 null ttl 60

import random
random.seed(0)

store, hits, misses = {}, [0], [0]
def cache_get(key):
    v = store.get(key)
    if v is None: misses[0] += 1
    else: hits[0] += 1
    return v

def query(key):
    hit = cache_get(key)
    if hit is not None:
        return hit['v'] if hit['v'] != '__NULL__' else None
    value = {'id': key} if key >= 0 else None
    if value is None:
        store[key] = {'v': '__NULL__', 'ttl': 60}
        return None
    store[key] = {'v': value, 'ttl': 300 + random.randint(0, 60)}
    return value

print(query(1))
print(query(1))
print(query(-1))
print(query(-1))
print('hits', hits[0], 'misses', misses[0])
print('ttl key1', store[1]['ttl'], 'null ttl', store[-1]['ttl'])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# acquire A OK
# acquire B None
# B release wrong not-owner, keep
# A release released
# final None

import uuid

class Store:
    def __init__(self):
        self.d = {}
    def set_nx(self, key, value, ex):
        if key in self.d:
            return None
        self.d[key] = (value, ex)
        return 'OK'
    def get(self, key):
        v = self.d.get(key)
        return v[0] if v else None
    def delete(self, key):
        self.d.pop(key, None)

store = Store()
token = str(uuid.uuid4())[:8]
print('acquire A', store.set_nx('lock:order', token, ex=5))
print('acquire B', store.set_nx('lock:order', 'other', ex=5))
def safe_release(store, key, token):
    if store.get(key) == token:
        store.delete(key)
        return 'released'
    return 'not-owner, keep'
print('B release wrong', safe_release(store, 'lock:order', 'other'))
print('A release', safe_release(store, 'lock:order', token))
print('final', store.get('lock:order'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# ttls with jitter [340, 307, 301, 347, 317, 315]
# distinct 6

import random
random.seed(42)
ttls = [300 + random.randint(0, 60) for _ in range(6)]
print('ttls with jitter', ttls)
print('distinct', len(set(ttls)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import random
import uuid
random.seed(1)
store = {}
FALLBACK = {1: {'id': 1, 'name': 'cached-copy'}}

def set_nx(key, value, ex):
    if key in store:
        return None
    store[key] = {'v': value, 'ex': ex}
    return 'OK'

def rebuild(key):
    token = str(uuid.uuid4())[:8]
    if set_nx('lock:' + str(key), token, ex=5) == 'OK':
        value = {'id': key, 'name': 'item'} if key > 0 else None
        if value is None:
            store[key] = {'v': '__NULL__', 'ex': 60}
        else:
            store[key] = {'v': value, 'ex': 300 + random.randint(0, 60)}
        store.pop('lock:' + str(key), None)

def query(key):
    hit = store.get(key)
    if hit is not None:
        return (None if hit['v'] == '__NULL__' else hit['v'], False)
    try:
        rebuild(key)
    except Exception:
        return (FALLBACK.get(key), True)
    h = store.get(key)
    return (None if h and h['v'] == '__NULL__' else (h['v'] if h else None), False)

print(query(1))
print(query(1))
print(query(-1))
print(query(-1))
print('keys', sorted(store))
