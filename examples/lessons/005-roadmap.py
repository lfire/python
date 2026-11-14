"""
第 005 讲 · 学习路线：十三个阶段如何递进
与教程正文一一对应的示例代码

课程页面：/guide/roadmap
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/005-roadmap.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/005-roadmap.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# no_cycle True
# stage_count 5
# L3_needs ['L1', 'L2']
# L0_is_root True

stages = {
    'L0': [],
    'L1': ['L0'],
    'L2': ['L1'],
    'L3': ['L1', 'L2'],
    'L4': ['L3'],
}

def has_cycle(graph):
    visiting, done = set(), set()
    def visit(node):
        if node in visiting: return True
        if node in done: return False
        visiting.add(node)
        for dep in graph.get(node, []):
            if visit(dep): return True
        visiting.discard(node)
        done.add(node)
        return False
    return any(visit(n) for n in graph)

print('no_cycle', not has_cycle(stages))
print('stage_count', len(stages))
print('L3_needs', sorted(stages['L3']))
print('L0_is_root', stages['L0'] == [])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# order ['L0', 'L1', 'L2', 'L3']
# L1_before_L3 True

graph = {'L0': [], 'L1': ['L0'], 'L2': ['L1'], 'L3': ['L1', 'L2']}
order, seen = [], set()
def emit(n):
    if n in seen: return
    for d in graph[n]: emit(d)
    seen.add(n); order.append(n)
for n in graph: emit(n)
print('order', order)
print('L1_before_L3', order.index('L1') < order.index('L3'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# params ['a', 'b']
# default 2
# code_varnames ('a', 'b')
# callable True
# closure_none True

import inspect

def f(a, b=2): return a + b
sig = inspect.signature(f)
print('params', list(sig.parameters))
print('default', sig.parameters['b'].default)
print('code_varnames', f.__code__.co_varnames)
print('callable', callable(f))
print('closure_none', f.__closure__ is None)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

GRAPH = {
    'L0': [], 'L1': ['L0'], 'L2': ['L1'],
    'L3': ['L1', 'L2'], 'L4': ['L1', 'L3'], 'L5': ['L1', 'L4'],
}

def prereqs(node, graph, seen=None):
    if seen is None:
        seen = set()
    for dep in graph.get(node, []):
        if dep not in seen:
            seen.add(dep)
            prereqs(dep, graph, seen)
    return seen

def has_cycle(graph):
    visiting, done = set(), set()
    def visit(n):
        if n in visiting: return True
        if n in done: return False
        visiting.add(n)
        if any(visit(d) for d in graph.get(n, [])):
            return True
        visiting.discard(n); done.add(n)
        return False
    return any(visit(n) for n in graph)

def plan(target, completed):
    need = prereqs(target, GRAPH)
    return {'acyclic': not has_cycle(GRAPH),
            'missing': sorted(need - set(completed)),
            'total': len(need)}

r = plan('L5', ['L0', 'L1'])
print('acyclic', r['acyclic'])
print('missing', r['missing'])
print('total', r['total'])
