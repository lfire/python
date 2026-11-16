"""
第 132 讲 · 实战 11 · 分片复制、AI 网关与能力收束
与教程正文一一对应的示例代码

课程页面：/projects/kv-distributed
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/132-kv-distributed.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/132-kv-distributed.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# primary of a n2
# replica set ['n2', 'n3', 'n1']
# write ok True
# failover to n3
# quorum after loss True
# quorum single False

import hashlib

NODES = ['n1', 'n2', 'n3']
REPLICAS = 3

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

ring = sorted((h(nd + '#' + str(i)), nd) for nd in NODES for i in range(REPLICAS))

def primary(key):
    x = h(key)
    for slot, nd in ring:
        if x <= slot:
            return nd
    return ring[0][1]

def replica_set(key):
    seen, out = [], []
    for slot, nd in ring:
        if nd not in seen:
            seen.append(nd)
            out.append(nd)
    start = out.index(primary(key))
    return out[start:] + out[:start]

def route(key, alive):
    for nd in replica_set(key):
        if nd in alive:
            return nd
    return None

def quorum_ok(key, alive, w=2):
    return sum(1 for nd in replica_set(key) if nd in alive) >= w

print('primary of a', primary('a'))
print('replica set', replica_set('a'))
all_alive = set(NODES)
print('write ok', quorum_ok('a', all_alive, w=2))
one_down = all_alive - {primary('a')}
print('failover to', route('a', one_down))
print('quorum after loss', quorum_ok('a', one_down, w=2))
print('quorum single', quorum_ok('a', {'n1'}, w=2))

# ======================== 2. 对照写法 ========================
# 预期输出：
# frame count 2
# has data prefix True
# has newline True
# normal (['你', '好', '！'], 3)
# budget (['你', '好', '[budget]'], 2)
# timeout (['A', '[timeout]'], 1)

def sse_frames(chunks):
    for c in chunks:
        yield 'data: ' + c + chr(10) + chr(10)

def gateway(chunks, budget, deadline):
    out, used = [], 0
    for t, text in chunks:
        if t > deadline:
            out.append('[timeout]')
            break
        if used >= budget:
            out.append('[budget]')
            break
        out.append(text)
        used += 1
    return out, used

frames = list(sse_frames(['你', '好']))
print('frame count', len(frames))
print('has data prefix', frames[0].startswith('data: '))
print('has newline', chr(10) in frames[0])
chunks = [(1, '你'), (2, '好'), (3, '！')]
print('normal', gateway(chunks, budget=5, deadline=10))
print('budget', gateway(chunks, budget=2, deadline=10))
print('timeout', gateway([(1, 'A'), (99, 'B')], budget=5, deadline=10))

# ======================== 3. 原理验证 ========================
# 预期输出：
# ring moved 94 of 300 = 0.313
# modulo moved 225 of 300 = 0.75
# quorum 2+2>3 True

import hashlib

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

def ring(nodes, replicas=3):
    return sorted((h(nd + '#' + str(i)), nd) for nd in nodes for i in range(replicas))

def owner(key, r):
    x = h(key)
    for slot, nd in r:
        if x <= slot:
            return nd
    return r[0][1]

keys = ['key' + str(i) for i in range(300)]
r3 = ring(['n1', 'n2', 'n3'])
r4 = ring(['n1', 'n2', 'n3', 'n4'])
ring_moved = sum(owner(k, r3) != owner(k, r4) for k in keys)
mod_moved = sum(h(k) % 3 != h(k) % 4 for k in keys)
print('ring moved', ring_moved, 'of 300 =', round(ring_moved / 300, 3))
print('modulo moved', mod_moved, 'of 300 =', round(mod_moved / 300, 3))
print('quorum 2+2>3', 2 + 2 > 3)

# ======================== 4. 工程案例 ========================

import hashlib

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

class Gateway:
    def __init__(self, nodes, replicas=3, token_budget=100, w=2, r=2):
        self.nodes = list(nodes)
        self.alive = set(nodes)
        self.w, self.r = w, r
        self.budget = token_budget
        self.spent = 0
        self.ring = sorted((h(nd + '#' + str(i)), nd)
                           for nd in self.nodes for i in range(replicas))
    def replica_set(self, key):
        order = []
        for slot, nd in self.ring:
            if nd not in order:
                order.append(nd)
        x = h(key)
        primary = next((nd for slot, nd in self.ring if x <= slot), self.ring[0][1])
        k = order.index(primary)
        return order[k:] + order[:k]
    def route(self, key):
        for nd in self.replica_set(key):
            if nd in self.alive:
                return nd
        return None
    def quorum_ok(self, key):
        live = sum(1 for nd in self.replica_set(key) if nd in self.alive)
        return live >= self.w and self.w + self.r > len(self.replica_set(key))
    def stream(self, chunks, deadline):
        out = []
        for t, text in chunks:
            if t > deadline or self.spent >= self.budget:
                return out, 'degraded'
            out.append(text)
            self.spent += 1
        return out, 'ok'
    def cost(self, price=0.002):
        return round(self.spent * price, 4)

gw = Gateway(['n1', 'n2', 'n3'], token_budget=3)
key = 'user-42'
print('replicas', gw.replica_set(key))
gw.alive.discard(gw.replica_set(key)[0])
print('failover', gw.route(key), 'quorum', gw.quorum_ok(key))
print('stream', gw.stream([(1, 'A'), (2, 'B'), (3, 'C'), (4, 'D')], deadline=10))
print('cost', gw.cost())
