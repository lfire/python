"""
第 091 讲 · 文件、对象存储、搜索与 gRPC
与教程正文一一对应的示例代码

课程页面：/server/storage
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/091-storage.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/091-storage.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# index terms 9
# redis df 2 idf 0.47
# query redis cache [(1, 0.94), (2, 0.94)]
# query sqlalchemy [(3, 0.981)]

import math
from collections import defaultdict
DOCS = {
    1: 'short link redis cache',
    2: 'redis cache penetration avalanche',
    3: 'sqlalchemy connection pool',
}
def tokenize(text):
    return [w.lower() for w in text.split()]
postings = defaultdict(list)
for doc_id, text in DOCS.items():
    for term in set(tokenize(text)):
        postings[term].append(doc_id)
N = len(DOCS)
idf = {t: math.log(1 + (N - len(ids) + 0.5) / (len(ids) + 0.5))
       for t, ids in postings.items()}
def search(query, k=3):
    scores = defaultdict(float)
    for term in set(tokenize(query)):
        for doc_id in postings.get(term, []):
            tf = 1
            scores[doc_id] += idf[term] * (tf * 2.2) / (tf + 1.2)
    return [(d, round(s, 3)) for d, s in sorted(scores.items(), key=lambda kv: -kv[1])[:k]]
print('index terms', len(postings))
print('redis df', len(postings['redis']), 'idf', round(idf['redis'], 4))
print('query redis cache', search('redis cache'))
print('query sqlalchemy', search('sqlalchemy'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# a sig 2b4695f4ebd92815
# b sig c0ca2afd07f099dd
# c sig ba6f382a5296292a
# path bound True
# expiry bound True

import hmac, hashlib

def presign(path, expires, now=1700000000):
    sts = 'GET' + chr(10) + path + chr(10) + str(now + expires)
    sig = hmac.new(b'secret', sts.encode(), hashlib.sha256).hexdigest()[:16]
    return '?X-Amz-Date=' + str(now) + '&X-Amz-Expires=' + str(expires) + '&X-Amz-Signature=' + sig

a = presign('/uploads/a.bin', 900)
b = presign('/uploads/b.bin', 900)
c = presign('/uploads/a.bin', 3600)
print('a sig', a.split('Signature=')[1])
print('b sig', b.split('Signature=')[1])
print('c sig', c.split('Signature=')[1])
print('path bound', a.split('Signature=')[1] != b.split('Signature=')[1])
print('expiry bound', a.split('Signature=')[1] != c.split('Signature=')[1])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# 1 -> [1]
# 127 -> [127]
# 128 -> [128, 1]
# 300 -> [172, 2]
# 150 -> [150, 1]

def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)
for n in (1, 127, 128, 300, 150):
    print(n, '->', list(varint(n)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import hmac, hashlib, math
from collections import defaultdict

SECRET = b'storage-secret'
def sign(path, expires, now=1700000000):
    sts = 'PUT' + chr(10) + path + chr(10) + str(now + expires)
    return hmac.new(SECRET, sts.encode(), hashlib.sha256).hexdigest()[:16]
def verify_sig(path, expires, sig, now=1700000000):
    return hmac.compare_digest(sign(path, expires, now), sig)

class InvertedIndex:
    def __init__(self):
        self.postings = defaultdict(list)
        self.n = 0
    def add(self, doc_id, text):
        self.n += 1
        for t in set(text.lower().split()):
            self.postings[t].append(doc_id)
    def search(self, q):
        scores = defaultdict(float)
        for t in set(q.lower().split()):
            ids = self.postings.get(t, [])
            idf = math.log(1 + (self.n - len(ids) + 0.5) / (len(ids) + 0.5))
            for d in ids:
                scores[d] += idf * 2.2 / 2.2
        return sorted(scores, key=lambda d: -scores[d])

sig = sign('/uploads/a.bin', 900)
print('sig valid', verify_sig('/uploads/a.bin', 900, sig))
print('path changed', verify_sig('/uploads/b.bin', 900, sig))
print('expired', verify_sig('/uploads/a.bin', 3600, sig))
idx = InvertedIndex()
idx.add(1, 'redis cache penetration')
idx.add(2, 'redis cache avalanche')
idx.add(3, 'sqlalchemy pool')
print('search redis cache', idx.search('redis cache'))
