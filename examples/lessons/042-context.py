"""
第 042 讲 · 上下文管理器与 with 协议
与教程正文一一对应的示例代码

课程页面：/oop/context
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/042-context.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/042-context.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# begin t1
# body t1
# exit True no-error
# begin t2
# exit False ValueError
# caught boom

class Transaction:
    def __init__(self, name):
        self.name = name
    def __enter__(self):
        print('begin', self.name)
        return self
    def __exit__(self, exc_type, exc_value, tb):
        print('exit', exc_type is None, type(exc_value).__name__ if exc_value else 'no-error')
        return False

with Transaction('t1') as t:
    print('body', t.name)
try:
    with Transaction('t2'):
        raise ValueError('boom')
except ValueError as e:
    print('caught', str(e))

# ======================== 2. 对照写法 ========================
# 预期输出：
# enter A
# enter B
# body
# callback
# exit B
# exit A
# after suppress

from contextlib import contextmanager, ExitStack, suppress

@contextmanager
def tag(label):
    print('enter', label)
    try:
        yield label
    finally:
        print('exit', label)

with ExitStack() as stack:
    stack.enter_context(tag('A'))
    stack.enter_context(tag('B'))
    stack.callback(print, 'callback')
    print('body')
with suppress(ZeroDivisionError):
    print(1 / 0)
print('after suppress')

# ======================== 3. 原理验证 ========================
# 预期输出：
# protocol: True True
# exit args: 3 False
# exc_info set: True
# propagated

import sys

class Probe:
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        print('exit args:', len(exc), exc[0] is None)
        print('exc_info set:', sys.exc_info()[0] is exc[0])
        return False

print('protocol:', hasattr(Probe, '__enter__'), hasattr(Probe, '__exit__'))
try:
    with Probe():
        raise KeyError('k')
except KeyError:
    print('propagated')

# ======================== 4. 工程案例 ========================

import sqlite3

class Tx:
    def __init__(self, conn):
        self.conn = conn
    def __enter__(self):
        self.cur = self.conn.cursor()
        return self.cur
    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.cur.close()
        return False

conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE acc (id INTEGER PRIMARY KEY, bal INTEGER)')
conn.execute('INSERT INTO acc VALUES (1, 100)')
conn.commit()
try:
    with Tx(conn) as cur:
        cur.execute('UPDATE acc SET bal = bal - 50 WHERE id = 1')
        cur.execute('UPDATE acc SET bal = ? WHERE id = ?', (999, 2))
        raise ValueError('abort')
except ValueError:
    pass
print('bal after rollback:', conn.execute('SELECT bal FROM acc').fetchone()[0])
with Tx(conn) as cur:
    cur.execute('UPDATE acc SET bal = bal + 10 WHERE id = 1')
print('bal after commit:', conn.execute('SELECT bal FROM acc').fetchone()[0])
conn.close()
