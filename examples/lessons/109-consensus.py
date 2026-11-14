"""
第 109 讲 · Raft 共识、服务发现与配置中心
与教程正文一一对应的示例代码

课程页面：/distributed/consensus
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/109-consensus.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/109-consensus.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# quorum 3
# commit_initial 0
# commit_after_replication 3
# alive3_writable True
# alive2_writable False

class Cluster:
    def __init__(self, n):
        self.n = n
        self.match = [0] * n
    def commit_index(self):
        replicas = sorted(self.match, reverse=True)
        return replicas[self.n // 2]
    def writable(self, alive):
        return alive > self.n // 2

c = Cluster(5)
print('quorum', 5 // 2 + 1)
print('commit_initial', c.commit_index())
c.match = [5, 4, 3, 0, 0]
print('commit_after_replication', c.commit_index())
print('alive3_writable', c.writable(3))
print('alive2_writable', c.writable(2))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# valid_now True
# valid_later False
# valid_after_renew True

import time

class Lease:
    def __init__(self, ttl):
        self.ttl = ttl
        self.expire = time.monotonic() + ttl
    def valid(self, now):
        return now < self.expire
    def renew(self, now):
        self.expire = now + self.ttl

l = Lease(10)
t0 = time.monotonic()
print('valid_now', l.valid(t0))
print('valid_later', l.valid(t0 + 11))
l.renew(t0 + 11)
print('valid_after_renew', l.valid(t0 + 12))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# accept
# reject-stale
# accept
# term 5

class Term:
    def __init__(self):
        self.current = 0
    def step(self, t):
        if t < self.current:
            return 'reject-stale'
        self.current = t
        return 'accept'
r = Term()
print(r.step(3))
print(r.step(2))
print(r.step(5))
print('term', r.current)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import time

class Registry:
    def __init__(self, quorum):
        self.quorum = quorum
        self.leases = {}
        self.version = 0
    def register(self, name, ttl, now):
        self.leases[name] = now + ttl
    def renew(self, name, ttl, now):
        if name in self.leases:
            self.leases[name] = now + ttl
    def expire(self, now):
        dead = [k for k, v in self.leases.items() if v <= now]
        for k in dead:
            del self.leases[k]
        return dead
    def alive(self, now):
        return [k for k, v in self.leases.items() if v > now]
    def write_config(self, alive_count):
        if alive_count < self.quorum:
            return 'reject-no-quorum'
        self.version += 1
        return 'v' + str(self.version)

r = Registry(3)
t = time.monotonic()
for n in ('a', 'b', 'c', 'd', 'e'):
    r.register(n, 30, t)
print(r.write_config(len(r.alive(t))))
print(r.write_config(2))
print('expired', r.expire(t + 31))
