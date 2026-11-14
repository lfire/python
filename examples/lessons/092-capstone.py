"""
第 092 讲 · 阶段综合：生产级短链服务
与教程正文一一对应的示例代码

课程页面：/server/capstone
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/092-capstone.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/092-capstone.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# codes 1 2
# big id ZZZZZZZ
# resolve (302, 'https://example.com/a')
# missing (404, None)
# clicks 1

import sqlite3
ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
BASE = len(ALPHABET)
def to62(n):
    out = []
    while n:
        n, r = divmod(n, BASE)
        out.append(ALPHABET[r])
    return ''.join(reversed(out)) or '0'
db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE links (id INTEGER PRIMARY KEY, url TEXT, code TEXT UNIQUE, clicks INT DEFAULT 0)')
def create(url):
    oid = db.execute('INSERT INTO links (url, code) VALUES (?, ?)', (url, '')).lastrowid
    code = to62(oid)
    db.execute('UPDATE links SET code=? WHERE id=?', (code, oid))
    return code
def resolve(code):
    row = db.execute('SELECT url, clicks FROM links WHERE code=?', (code,)).fetchone()
    if row is None:
        return (404, None)
    db.execute('UPDATE links SET clicks=clicks+1 WHERE code=?', (code,))
    return (302, row[0])
c1 = create('https://example.com/a')
c2 = create('https://example.com/b')
print('codes', c1, c2)
print('big id', to62(3521614606207))
print('resolve', resolve(c1))
print('missing', resolve('zzzz'))
print('clicks', db.execute('SELECT clicks FROM links WHERE code=?', (c1,)).fetchone()[0])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# burst [True, True, False]
# after 0.5s True
# after 1.0s True

class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last = None
    def allow(self, now):
        if self.last is None:
            self.last = now
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

b = TokenBucket(rate=2, capacity=2)
t0 = 100.0
print('burst', [b.allow(t0) for _ in range(3)])
print('after 0.5s', b.allow(t0 + 0.5))
print('after 1.0s', b.allow(t0 + 1.0))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# 1000 decimal 4 base62 2
# 1000000 decimal 7 base62 4
# 1000000000 decimal 10 base62 6

import math

for n in (1000, 1000000, 1000000000):
    dec = len(str(n))
    b62 = math.ceil(math.log(n + 1, 62)) if n > 0 else 1
    print(n, 'decimal', dec, 'base62', b62)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import sqlite3
import collections

ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
def to62(n):
    out = []
    while n:
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return ''.join(reversed(out)) or '0'

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE links (id INTEGER PRIMARY KEY, code TEXT UNIQUE, url TEXT)')
db.execute('CREATE TABLE idem (k TEXT PRIMARY KEY, code TEXT)')
cache, event_q = {}, collections.deque()

class Bucket:
    def __init__(self, rate, cap):
        self.rate, self.cap, self.tokens, self.last = rate, cap, float(cap), None
    def allow(self, now):
        if self.last is None: self.last = now
        self.tokens = min(self.cap, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

limiter = Bucket(rate=2, cap=2)
def create(url, key, now):
    if not limiter.allow(now):
        return (429, None)
    row = db.execute('SELECT code FROM idem WHERE k=?', (key,)).fetchone()
    if row: return (200, row[0])
    oid = db.execute('INSERT INTO links (code, url) VALUES (?, ?)', ('', url)).lastrowid
    code = to62(oid)
    db.execute('UPDATE links SET code=? WHERE id=?', (code, oid))
    db.execute('INSERT INTO idem VALUES (?, ?)', (key, code))
    cache[code] = url
    return (201, code)

def resolve(code):
    url = cache.get(code)
    if url is None:
        r = db.execute('SELECT url FROM links WHERE code=?', (code,)).fetchone()
        if r is None: return (404, None)
        url = r[0]
        cache[code] = url
    event_q.append(code)
    return (302, url)

print(create('https://a', 'k1', 0.0))
print(create('https://a', 'k1', 0.0))
print(resolve('1'))
print('events', list(event_q))
