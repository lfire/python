"""
第 111 讲 · GitOps、灰度发布与可观测平台
与教程正文一一对应的示例代码

课程页面：/distributed/gitops
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/111-gitops.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/111-gitops.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# pct 5 canary_users 59
# pct 20 canary_users 191
# pct 50 canary_users 487
# rollback_when_high True
# keep_when_low False

import hashlib

def bucket(user, mod=1000):
    return int(hashlib.md5(user.encode()).hexdigest()[:8], 16) % mod

def route(user, canary_pct):
    return 'canary' if bucket(user) < canary_pct * 10 else 'stable'

users = ['u' + str(i) for i in range(1000)]
for pct in (5, 20, 50):
    c = sum(1 for u in users if route(u, pct) == 'canary')
    print('pct', pct, 'canary_users', c)

def should_rollback(errors, total, threshold=0.02):
    return total > 0 and errors / total > threshold

print('rollback_when_high', should_rollback(8, 100))
print('keep_when_low', should_rollback(1, 100))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# budget_requests 1000
# burned_500 0.5
# burned_1500 1.5

def error_budget(slo, requests):
    return (1 - slo) * requests
def burned(allowed, errors):
    return round(errors / allowed, 3)

budget = error_budget(0.999, 1000000)
print('budget_requests', int(budget))
print('burned_500', burned(budget, 500))
print('burned_1500', burned(budget, 1500))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# diff {'replicas': (2, 4), 'image': ('app:v1', 'app:v2')}
# need_apply True

desired = {'replicas': 4, 'image': 'app:v2'}
current = {'replicas': 2, 'image': 'app:v1'}
diff = {k: (current.get(k), desired[k]) for k in desired if current.get(k) != desired[k]}
print('diff', diff)
print('need_apply', len(diff) > 0)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import hashlib

class Canary:
    def __init__(self, pct, threshold=0.02, min_samples=30):
        self.pct = pct
        self.threshold = threshold
        self.min_samples = min_samples
        self.stats = {'canary': [0, 0], 'stable': [0, 0]}
        self.audit = []
    def bucket(self, uid):
        return int(hashlib.md5(uid.encode()).hexdigest()[:8], 16) % 1000
    def version(self, uid):
        return 'canary' if self.bucket(uid) < self.pct * 10 else 'stable'
    def observe(self, uid, failed):
        v = self.version(uid)
        self.stats[v][0] += 1
        self.stats[v][1] += int(failed)
    def decide(self):
        n, e = self.stats['canary']
        if n < self.min_samples:
            return 'observing'
        if e / n > self.threshold:
            self.audit.append('rollback at pct ' + str(self.pct))
            return 'rollback'
        self.audit.append('promote')
        return 'promote'

c = Canary(20)
for i in range(200):
    c.observe('u' + str(i), failed=(i % 3 == 0))
print('decision', c.decide())
print('stats', c.stats)
print('audit', c.audit)
