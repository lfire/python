"""
第 108 讲 · 分布式 ID、一致性哈希与分片
与教程正文一一对应的示例代码

课程页面：/distributed/sharding
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/108-sharding.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/108-sharding.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# total 2000
# moved 546
# ratio 0.273
# ideal 0.25

import hashlib, bisect

def hkey(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

class Ring:
    def __init__(self, nodes, replicas=100):
        self.replicas = replicas
        self.keys = []
        self.map = {}
        for n in nodes:
            self.add(n)
    def add(self, n):
        for i in range(self.replicas):
            k = hkey(n + '#' + str(i))
            bisect.insort(self.keys, k)
            self.map[k] = n
    def node_for(self, key):
        k = hkey(key)
        i = bisect.bisect_left(self.keys, k) % len(self.keys)
        return self.map[self.keys[i]]

keys = ['user:' + str(i) for i in range(2000)]
r = Ring(['n1', 'n2', 'n3'])
before = {k: r.node_for(k) for k in keys}
r.add('n4')
moved = sum(1 for k in keys if r.node_for(k) != before[k])
print('total', len(keys))
print('moved', moved)
print('ratio', round(moved / len(keys), 3))
print('ideal', round(1 / 4, 3))

# ======================== 2. 对照写法 ========================
# 预期输出：
# id 7130316800000020481
# ts_back 1700000000000
# worker 5
# seq 1
# bits 63

def snowflake(ts_ms, worker, seq):
    return (ts_ms << 22) | (worker << 12) | seq

ts = 1700000000000
sid = snowflake(ts, 5, 1)
print('id', sid)
print('ts_back', sid >> 22)
print('worker', (sid >> 12) & 0x3FF)
print('seq', sid & 0xFFF)
print('bits', sid.bit_length())

# ======================== 3. 原理验证 ========================
# 预期输出：
# 1000
# clock_backwards
# 1001

class Gen:
    def __init__(self):
        self.last = 0
    def next(self, now_ms):
        if now_ms < self.last:
            return 'clock_backwards'
        self.last = now_ms
        return now_ms

g = Gen()
print(g.next(1000))
print(g.next(999))
print(g.next(1001))

# ======================== 4. 工程案例 ========================

import hashlib, bisect

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

class Router:
    def __init__(self, nodes, replicas=128):
        self.replicas = replicas
        self.ring = []
        self.owner = {}
        for n in nodes:
            self.add_node(n)
    def add_node(self, n):
        for i in range(self.replicas):
            p = h(n + ':' + str(i))
            bisect.insort(self.ring, p)
            self.owner[p] = n
    def node_for(self, key):
        p = h(key)
        idx = bisect.bisect_left(self.ring, p) % len(self.ring)
        return self.owner[self.ring[idx]]

keys = ['user:' + str(i) for i in range(5000)]
r = Router(['a', 'b', 'c'])
before = {k: r.node_for(k) for k in keys}
r.add_node('d')
changed = sum(1 for k in keys if r.node_for(k) != before[k])
print('migration_ratio', round(changed / len(keys), 3))
