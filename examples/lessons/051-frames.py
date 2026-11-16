"""
第 051 讲 · 帧、调用栈与命名空间
与教程正文一一对应的示例代码

课程页面：/core/frames
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/051-frames.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/051-frames.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# locals snapshot True
# f_locals writes through True（3.13+ PEP 667 写透代理；3.12 及以前为 False）
# names ['frame', 'snap', 'x']
# globals is module True
# G changed True
# result True

import sys

G = 0
def probe():
    x = 1
    snap = locals()
    snap['x'] = 50
    print('locals snapshot', x == 1)
    frame = sys._getframe()
    frame.f_locals['x'] = 99
    print('f_locals writes through', x == 99)
    print('names', sorted(frame.f_code.co_varnames))
    print('globals is module', frame.f_globals is globals())
    globals()['G'] = 7
    print('G changed', G == 7)
    return frame.f_lasti >= 0
print('result', probe())

# ======================== 2. 对照写法 ========================
# 预期输出：
# state created GEN_CREATED
# first 10
# gi_frame kept True
# locals ['a']
# state suspended GEN_SUSPENDED
# second 20
# third exhausted
# frame cleared True

import inspect

def gen():
    a = 10
    yield a
    b = 20
    yield b
g = gen()
print('state created', inspect.getgeneratorstate(g))
print('first', next(g))
print('gi_frame kept', g.gi_frame is not None)
print('locals', sorted(g.gi_frame.f_locals))
print('state suspended', inspect.getgeneratorstate(g))
print('second', next(g))
try:
    next(g)
except StopIteration:
    print('third exhausted')
print('frame cleared', g.gi_frame is None)

# ======================== 3. 原理验证 ========================
# 预期输出：
# call events present True
# recursionlimit True
# RecursionError raised

import sys

events = []
def profiler(frame, event, arg):
    if event in ('call', 'return'):
        events.append((event, frame.f_code.co_name))
def work(n):
    if n == 0:
        return 0
    return work(n - 1)
sys.setprofile(profiler)
work(2)
sys.setprofile(None)
print('call events present', sum(1 for e, _ in events if e == 'call') >= 3)
print('recursionlimit', sys.getrecursionlimit() > 0)
try:
    sys.setrecursionlimit(50)
    work(1000)
except RecursionError:
    print('RecursionError raised')
finally:
    sys.setrecursionlimit(1000)

# ======================== 4. 工程案例 ========================

import sys

coverage = {}
def tracer(frame, event, arg):
    if event == 'call':
        coverage.setdefault(frame.f_code.co_name, set())
        return tracer
    if event == 'line':
        coverage[frame.f_code.co_name].add(frame.f_lineno)
    return tracer

def branch(x):
    if x > 0:
        return 'positive'
    return 'non-positive'

sys.settrace(tracer)
branch(3)
branch(-1)
sys.settrace(None)
print('branch covered multiple lines', len(coverage.get('branch', ())) > 1)
print('trace disabled after', sys.gettrace() is None)
