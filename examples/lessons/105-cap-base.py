"""
第 105 讲 · CAP / BASE 与一致性模型
与教程正文一一对应的示例代码

课程页面：/distributed/cap-base
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/105-cap-base.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/105-cap-base.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# read R1 (primary) (1, '订单A')
# read R2 (before replication) (0, 0)
# read R2 (after) (1, '订单A')

replicas = {'R1': (0, 0), 'R2': (0, 0), 'R3': (0, 0)}
def write(val, version):
    replicas['R1'] = (version, val)
def replicate(targets):
    for t in targets:
        replicas[t] = replicas['R1']
def read(rid):
    return replicas[rid]
write('订单A', 1)
print('read R1 (primary)', read('R1'))
print('read R2 (before replication)', read('R2'))
replicate(['R2', 'R3'])
print('read R2 (after)', read('R2'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# concurrent? True
# merged {'A': 2, 'B': 2}
# vc dominates va? True

def merge(a, b):
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in sorted(set(a) | set(b))}
def concurrent(a, b):
    keys = set(a) | set(b)
    a_ge = all(a.get(k, 0) >= b.get(k, 0) for k in keys)
    b_ge = all(b.get(k, 0) >= a.get(k, 0) for k in keys)
    return not (a_ge or b_ge)
va = {'A': 2, 'B': 1}
vb = {'A': 1, 'B': 2}
print('concurrent?', concurrent(va, vb))
print('merged', merge(va, vb))
vc = {'A': 3, 'B': 2}
print('vc dominates va?', not concurrent(va, vc))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# after partition: A 2 B 3
# diverged? True
# CP choice: reject B write -> A,B stay 2 2

zone_a = {'x': 1}
zone_b = {'x': 1}
zone_a['x'] = 2
zone_b['x'] = 3
print('after partition: A', zone_a['x'], 'B', zone_b['x'])
print('diverged?', zone_a['x'] != zone_b['x'])
print('CP choice: reject B write -> A,B stay', 2, 2)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

replicas = {'primary': (0, None), 'replica': (0, None)}
session_version = 0
def write(val):
    global session_version
    session_version += 1
    replicas['primary'] = (session_version, val)
def replicate():
    replicas['replica'] = replicas['primary']
def read(rid, min_version=0):
    ver, val = replicas[rid]
    if ver < min_version:
        ver, val = replicas['primary']
    return (ver, val)
write('订单A')
print('read replica(no sticky)', read('replica'))
print('read replica(read-your-writes)', read('replica', session_version))
replicate()
print('read replica(after replication)', read('replica', session_version))
