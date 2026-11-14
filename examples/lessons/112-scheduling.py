"""
第 112 讲 · 任务调度、SRE 与混沌工程
与教程正文一一对应的示例代码

课程页面：/distributed/scheduling
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/112-scheduling.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/112-scheduling.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# order ['extract', 'clean', 'join', 'report']

from collections import deque

def topo(deps):
    indeg = {k: len(pres) for k, pres in deps.items()}
    ready = deque([k for k, d in indeg.items() if d == 0])
    order = []
    while ready:
        n = ready.popleft()
        order.append(n)
        for k, pres in deps.items():
            if n in pres:
                indeg[k] -= 1
                if indeg[k] == 0:
                    ready.append(k)
    return order

dag = {
    'extract': [],
    'clean': ['extract'],
    'join': ['extract'],
    'report': ['clean', 'join'],
}
print('order', topo(dag))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# delays [0.1, 0.2, 0.4, 0.8, 1.6, 2.0]
# executed
# skip

def backoff(attempt, base=0.1, cap=2.0):
    return min(cap, base * (2 ** attempt))

print('delays', [round(backoff(i), 3) for i in range(6)])

class Idempotent:
    def __init__(self):
        self.done = set()
    def run(self, key):
        if key in self.done:
            return 'skip'
        self.done.add(key)
        return 'executed'

job = Idempotent()
print(job.run('2024-01-01'))
print(job.run('2024-01-01'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# sli 0.997
# page_by_user_sli True
# page_when_healthy False
# cpu_threshold True

def sli(good, total):
    return good / total if total else 1.0
def page_on_sli(value, slo=0.999):
    return value < slo

print('sli', round(sli(997, 1000), 3))
print('page_by_user_sli', page_on_sli(sli(997, 1000)))
print('page_when_healthy', page_on_sli(sli(1000, 1000)))
print('cpu_threshold', 0.95 > 0.8)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from collections import deque

class Job:
    def __init__(self, name, needs):
        self.name = name
        self.needs = needs

class Scheduler:
    def __init__(self, jobs):
        self.jobs = jobs
        self.done = set()
    def order(self):
        indeg = {j.name: len(j.needs) for j in self.jobs}
        q = deque([n for n, d in indeg.items() if d == 0])
        out = []
        while q:
            n = q.popleft()
            out.append(n)
            for j in self.jobs:
                if n in j.needs:
                    indeg[j.name] -= 1
                    if indeg[j.name] == 0:
                        q.append(j.name)
        return out
    def run(self, name, date):
        key = name + ':' + date
        if key in self.done:
            return 'skip'
        self.done.add(key)
        return 'executed'

s = Scheduler([Job('extract', []), Job('clean', ['extract']), Job('report', ['clean'])])
print('order', s.order())
print(s.run('clean', '2024-01-01'))
print(s.run('clean', '2024-01-01'))
