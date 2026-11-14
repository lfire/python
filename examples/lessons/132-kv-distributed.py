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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# distribution [111, 88, 101]
# balanced True
# quorum R+W>N True

import hashlib

N = 3
def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)
counts = [0, 0, 0]
for i in range(300):
    counts[h('key' + str(i)) % N] += 1
print('distribution', counts)
print('balanced', max(counts) - min(counts) < 60)
print('quorum R+W>N', 2 + 2 > 3)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import hashlib

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

class Gateway:
    def __init__(self, nodes, token_budget=100):
        self.nodes = list(nodes)
        self.alive = set(nodes)
        self.budget = token_budget
        self.spent = 0
    def shard(self, key):
        return self.nodes[h(key) % len(self.nodes)]
    def route(self, key):
        pref = self.shard(key)
        if pref in self.alive:
            return pref
        for nd in self.nodes:
            if nd in self.alive:
                return nd
        return None
    def quorum_ok(self, w=2):
        return len(self.alive) >= w
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
print('shard', gw.shard('user-42'))
gw.alive.discard(gw.shard('user-42'))
print('failover', gw.route('user-42'), 'quorum', gw.quorum_ok())
print('stream', gw.stream([(1, 'A'), (2, 'B'), (3, 'C'), (4, 'D')], deadline=10))
print('cost', gw.cost())
