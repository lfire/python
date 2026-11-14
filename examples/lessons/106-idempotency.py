"""
第 106 讲 · 幂等、分布式锁与限流
与教程正文一一对应的示例代码

课程页面：/distributed/idempotency
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/106-idempotency.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/106-idempotency.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# [True, True, True, False, False, True, False, False, True]

class TokenBucket:
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.rate = refill_rate
        self.tokens = float(capacity)
        self.last = 0.0
    def allow(self, now, cost=1.0):
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False
b = TokenBucket(capacity=3, refill_rate=1)
times = [0, 0, 0, 0, 0.5, 1, 1, 1, 2]
print([b.allow(t) for t in times])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# k1 charge-applied
# k1 duplicate-ignored
# k2 charge-applied
# k1 duplicate-ignored

seen = set()
def handle(idem_key, op):
    if idem_key in seen:
        return 'duplicate-ignored'
    seen.add(idem_key)
    return op + '-applied'
for key in ['k1', 'k1', 'k2', 'k1']:
    print(key, handle(key, 'charge'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# check and store separate? True
# instruction count 9
# STORE_SUBSCR count 1
# key ops ['CONTAINS_OP', 'STORE_SUBSCR']

import dis
def unsafe_write(store, key, val):
    if key not in store:
        store[key] = val
ops = [i.opname for i in dis.get_instructions(unsafe_write)]
print('check and store separate?', 'CONTAINS_OP' in ops and 'STORE_SUBSCR' in ops)
print('instruction count', len(ops))
print('STORE_SUBSCR count', ops.count('STORE_SUBSCR'))
print('key ops', [o for o in ops if o in ('CONTAINS_OP', 'STORE_SUBSCR')])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

class TokenBucket:
    def __init__(self, cap, rate):
        self.cap, self.rate = cap, rate
        self.tokens, self.last = float(cap), 0.0
    def allow(self, now):
        self.tokens = min(self.cap, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
seen = set()
def gateway(now, bucket):
    return bucket.allow(now)
def service(idem):
    if idem in seen: return 'duplicate-ignored'
    seen.add(idem); return 'applied'
def handle(idem, now, bucket):
    if not gateway(now, bucket): return 'rate-limited'
    return service(idem)
bucket = TokenBucket(3, 1)
events = [('k1', 0), ('k1', 0), ('k2', 0), ('k3', 0), ('k4', 0), ('k5', 2)]
for idem, t in events:
    print(idem, handle(idem, t, bucket))
