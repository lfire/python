"""
第 026 讲 · 生成器与 yield：send / throw / close
与教程正文一一对应的示例代码

课程页面：/containers/generator
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/026-generator.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/026-generator.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# state created GEN_CREATED
# prime 0
# send 10 10 send 5 15
# return value 15
# state closed GEN_CLOSED
# yield from [0, 1, 2, 'got: source done']
# first working
# throw ValueError ['cleaned']
# after close ['cleaned'] GEN_CLOSED

import inspect

def accumulator():
    total = 0
    while True:
        value = yield total
        if value is None:
            break
        total += value
    return total

g = accumulator()
print('state created', inspect.getgeneratorstate(g))
print('prime', next(g))
print('send 10', g.send(10), 'send 5', g.send(5))
try:
    g.send(None)
except StopIteration as e:
    print('return value', e.value)
print('state closed', inspect.getgeneratorstate(g))

def source(n):
    for i in range(n):
        yield i
    return 'source done'

def wrapper():
    result = yield from source(3)
    yield 'got: ' + result

print('yield from', list(wrapper()))

def with_cleanup(log):
    try:
        yield 'working'
        yield 'more'
    finally:
        log.append('cleaned')

log = []
c = with_cleanup(log)
print('first', next(c))
print('throw', end=' ')
try:
    c.throw(ValueError('stop'))
except ValueError as e:
    print(type(e).__name__, log)
c.close()
print('after close', log, inspect.getgeneratorstate(c))

# ======================== 2. 对照写法 ========================
# 预期输出：
# next a
# close triggers finally ['finally branch']
# GeneratorExit is BaseException BaseException
# inside T
# contextmanager log ['finally branch', 'enter T', 'exit T']

from contextlib import contextmanager

def guarded(log):
    try:
        yield 'a'
    except Exception:
        log.append('Exception branch')
    finally:
        log.append('finally branch')

log = []
g = guarded(log)
print('next', next(g))
g.close()
print('close triggers finally', log)
print('GeneratorExit is BaseException', GeneratorExit.__mro__[1].__name__)

@contextmanager
def tag(name):
    log.append('enter ' + name)
    yield name
    log.append('exit ' + name)

with tag('T') as t:
    print('inside', t)
print('contextmanager log', log)

# ======================== 3. 原理验证 ========================
# 预期输出：
# not started True GEN_CREATED
# locals before {}
# first 1
# locals after {'x': 1}
# running flag False
# state GEN_SUSPENDED
# CO_GENERATOR flag True
# YIELD in bytecode True

import inspect, dis

def gen():
    x = 1
    yield x
    x += 1
    yield x

g = gen()
print('not started', g.gi_frame is not None, inspect.getgeneratorstate(g))
print('locals before', g.gi_frame.f_locals)
print('first', next(g))
print('locals after', g.gi_frame.f_locals)
print('running flag', g.gi_running)
print('state', inspect.getgeneratorstate(g))
print('CO_GENERATOR flag', bool(gen.__code__.co_flags & inspect.CO_GENERATOR))
print('YIELD in bytecode', 'YIELD' in dis.Bytecode(gen).dis())

# ======================== 4. 工程案例 ========================

from contextlib import closing
import inspect

def source(rows):
    for r in rows:
        yield r
    return 'source done'

def filtering(rows, log):
    threshold = 0
    try:
        label = yield from source(rows)
        while True:
            new = yield label
            if new is None:
                break
            threshold = new
            log.append('threshold ' + str(threshold))
    finally:
        log.append('cleaned')
    return threshold

log = []
with closing(filtering([1, 2, 3], log)) as g:
    print('start', next(g))
    print('send 5', g.send(5))
print('log', log)
print('state', inspect.getgeneratorstate(g))
