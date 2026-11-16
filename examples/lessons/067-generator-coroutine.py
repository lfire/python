"""
第 067 讲 · 生成器协程：send、yield from 与调度器
与教程正文一一对应的示例代码

课程页面：/concurrency/generator-coroutine
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/067-generator-coroutine.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/067-generator-coroutine.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# prime 0
# send 10 10
# send 5 15
# return value 15

def accumulator():
    total = 0
    while True:
        value = yield total
        if value is None:
            return total
        total += value

acc = accumulator()
print('prime', next(acc))
print('send 10', acc.send(10))
print('send 5', acc.send(5))
try:
    acc.send(None)
except StopIteration as e:
    print('return value', e.value)

# ======================== 2. 对照写法 ========================
# 预期输出：
# first sub-ready
# delegated result:42
# delegator done None
# g first 1
# throw caught:x
# closed True

def sub():
    v = yield 'sub-ready'
    return v * 2

def delegator():
    result = yield from sub()
    yield 'result:' + str(result)

d = delegator()
print('first', next(d))
print('delegated', d.send(21))
try:
    d.send(None)
except StopIteration as e:
    print('delegator done', e.value)

def guarded():
    try:
        yield 1
    except ValueError as e:
        yield 'caught:' + str(e)

g = guarded()
print('g first', next(g))
print('throw', g.throw(ValueError('x')))
g.close()
print('closed', True)

# ======================== 3. 原理验证 ========================
# 预期输出：
# state created GEN_CREATED
# first 1
# state suspended GEN_SUSPENDED
# opnames ['RETURN_GENERATOR', 'POP_TOP', 'RESUME', 'LOAD_CONST', 'YIELD_VALUE', 'RESUME', 'STORE_FAST', 'LOAD_FAST', 'RETURN_VALUE', 'CALL_INTRINSIC_1', 'RERAISE']
# CO_GENERATOR True
# return value None
# state closed GEN_CLOSED
# pep479 True

import dis
import inspect

def gen():
    x = yield 1
    return x

g = gen()
print('state created', inspect.getgeneratorstate(g))
print('first', next(g))
print('state suspended', inspect.getgeneratorstate(g))
print('opnames', [i.opname for i in dis.get_instructions(gen)])
print('CO_GENERATOR', bool(gen.__code__.co_flags & inspect.CO_GENERATOR))
try:
    next(g)
except StopIteration as e:
    print('return value', e.value)
    print('state closed', inspect.getgeneratorstate(g))

def bad():
    yield 1
    raise StopIteration('pep479')

b = bad()
next(b)
try:
    next(b)
except RuntimeError as e:
    print('pep479', 'generator raised StopIteration' in str(e))

# ======================== 4. 工程案例 ========================

from collections import deque

def task(name, steps):
    for i in range(steps):
        yield ('ready', name, i)
        if i + 1 < steps:
            yield ('wait', name, i)

def run(tasks):
    queue = deque(tasks)
    log = []
    while queue:
        t = queue.popleft()
        try:
            token = next(t)
            log.append(token)
            if token[0] == 'wait':
                try:
                    next(t)
                    queue.append(t)
                except StopIteration:
                    pass
            else:
                queue.append(t)
        except StopIteration:
            pass
    return log

if __name__ == '__main__':
    out = run([task('A', 3), task('B', 2)])
    print('steps', len(out))
    print('first', out[0])
    print('round robin', [x[1] for x in out if x[0] == 'ready'])
