"""
第 126 讲 · 实战 05 · 短链与图片服务
与教程正文一一对应的示例代码

课程页面：/projects/net-shortlink
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/126-net-shortlink.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/126-net-shortlink.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# codes ['0', 'z', '10', '100']
# roundtrip True
# lru 1 4 ['c', 'b']
# etag 7f016ee1
# status 301 Moved Permanently 302 Found

import hashlib
from collections import OrderedDict
from http import HTTPStatus

ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

def b62(n):
    if n == 0:
        return '0'
    out = []
    while n:
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return ''.join(reversed(out))

def unb62(s):
    n = 0
    for ch in s:
        n = n * 62 + ALPHABET.index(ch)
    return n

class LRU:
    def __init__(self, cap):
        self.cap = cap
        self.d = OrderedDict()
        self.hit = 0
        self.miss = 0
    def get(self, k):
        if k in self.d:
            self.hit += 1
            self.d.move_to_end(k)
            return self.d[k]
        self.miss += 1
        return None
    def put(self, k, v):
        self.d[k] = v
        self.d.move_to_end(k)
        if len(self.d) > self.cap:
            self.d.popitem(last=False)

print('codes', [b62(i) for i in (0, 61, 62, 3844)])
print('roundtrip', all(unb62(b62(i)) == i for i in range(1000)))
cache = LRU(cap=2)
for k in ('a', 'b', 'a', 'c', 'b'):
    if cache.get(k) is None:
        cache.put(k, 'url-' + k)
print('lru', cache.hit, cache.miss, list(cache.d))
etag = hashlib.md5(b'img-bytes').hexdigest()[:8]
print('etag', etag)
print('status', HTTPStatus.MOVED_PERMANENTLY.value, HTTPStatus.MOVED_PERMANENTLY.phrase,
      HTTPStatus.FOUND.value, HTTPStatus.FOUND.phrase)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# signed e971917f0dc31851
# valid ok
# tampered bad signature
# expired expired
# content-type gate True

import hashlib, hmac

SECRET = b'server-key'

def sign(resource, expires):
    payload = resource + ':' + str(expires)
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16]

def verify(resource, expires, sig, now):
    if now > expires:
        return 'expired'
    return 'ok' if hmac.compare_digest(sign(resource, expires), sig) else 'bad signature'

s = sign('img/42.png', expires=1000)
print('signed', s)
print('valid', verify('img/42.png', 1000, s, now=500))
print('tampered', verify('img/43.png', 1000, s, now=500))
print('expired', verify('img/42.png', 1000, s, now=2000))
print('content-type gate', 'image/png' in {'image/png', 'image/jpeg'})

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# 1 1 1
# 61 z 1
# 62 10 2
# 3843 zz 2
# 3844 100 3
# 238327 zzz 3
# base 62 log62(1e9) 5.02

import math

ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
def b62(n):
    if n == 0:
        return '0'
    s = ''
    while n:
        n, r = divmod(n, 62)
        s = ALPHABET[r] + s
    return s
for n in (1, 61, 62, 3843, 3844, 238327):
    print(n, b62(n), len(b62(n)))
print('base', len(ALPHABET), 'log62(1e9)', round(math.log(1e9, 62), 2))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from collections import OrderedDict

ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

def b62(n):
    s = ''
    while n:
        n, r = divmod(n, 62)
        s = ALPHABET[r] + s
    return s or '0'

class ShortLink:
    def __init__(self, cap=2):
        self.seq, self.store, self.cache, self.cap = 1000, {}, OrderedDict(), cap
        self.blocked = set()
    def create(self, url, permanent=False):
        self.seq += 1
        code = b62(self.seq)
        self.store[code] = (url, 301 if permanent else 302)
        return code
    def resolve(self, code, ip):
        if ip in self.blocked:
            return 429
        if code in self.cache:
            self.cache.move_to_end(code)
            return self.cache[code][1]
        if code not in self.store:
            return 404
        self.cache[code] = self.store[code]
        if len(self.cache) > self.cap:
            self.cache.popitem(last=False)
        return self.store[code][1]

svc = ShortLink()
a = svc.create('https://a.example', permanent=True)
b = svc.create('https://b.example')
print('codes', a, b)
print('resolve', svc.resolve(a, '1.2.3.4'), svc.resolve(a, '1.2.3.4'))
svc.blocked.add('9.9.9.9')
print('blocked', svc.resolve(a, '9.9.9.9'))
print('missing', svc.resolve('zzzz', '1.2.3.4'))
