"""
第 107 讲 · 分布式事务：2PC / TCC / Saga / 消息最终一致
与教程正文一一对应的示例代码

课程页面：/distributed/dist-tx
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/107-dist-tx.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/107-dist-tx.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# step_failed order RuntimeError
# state {'stock': 5, 'balance': 100, 'order': 0}
# compensated ['balance', 'stock']
# duplicate_comp skip-duplicate

class Saga:
    def __init__(self):
        self.done = []
        self.compensated = set()
    def run(self, name, forward, backward):
        try:
            forward()
        except RuntimeError as err:
            print('step_failed', name, type(err).__name__)
            return False
        self.done.append((name, backward))
        return True
    def compensate(self, name):
        if name in self.compensated:
            return 'skip-duplicate'
        self.compensated.add(name)
        return 'compensated'
    def rollback(self):
        for name, backward in reversed(self.done):
            backward()
            self.compensated.add(name)

state = {'stock': 5, 'balance': 100, 'order': 0}
def dec_stock(): state['stock'] -= 1
def inc_stock(): state['stock'] += 1
def dec_balance(): state['balance'] -= 10
def inc_balance(): state['balance'] += 10
def make_order(): raise RuntimeError('payment timeout')
def drop_order(): state['order'] = 0

s = Saga()
for name, fwd, back in [
    ('stock', dec_stock, inc_stock),
    ('balance', dec_balance, inc_balance),
    ('order', make_order, drop_order),
]:
    if not s.run(name, fwd, back):
        s.rollback()
        break
print('state', state)
print('compensated', sorted(s.compensated))
print('duplicate_comp', s.compensate('stock'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# db {'order:1': 'paid'}
# queued 1
# sent ['order.paid:1']

class Outbox:
    def __init__(self):
        self.db = {}
        self.queue = []
    def transact(self, key, value, event):
        self.db[key] = value
        self.queue.append(event)
    def dispatch(self):
        sent = []
        while self.queue:
            sent.append(self.queue.pop(0))
        return sent

o = Outbox()
o.transact('order:1', 'paid', 'order.paid:1')
print('db', o.db)
print('queued', len(o.queue))
print('sent', o.dispatch())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# balance 110
# applied ['refund']

state = {'balance': 100}
applied = set()
def compensate():
    state['balance'] += 10
def once(name, fn):
    if name not in applied:
        fn()
        applied.add(name)
once('refund', compensate)
once('refund', compensate)
print('balance', state['balance'])
print('applied', sorted(applied))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import hashlib

class Broker:
    def __init__(self):
        self.log = []
        self.delivered = []
        self.consumed = set()
    def transact(self, event, idem):
        self.log.append((event, idem))
    def dispatch(self):
        for event, idem in self.log:
            self.delivered.append(event)
    def consume(self, idem):
        if idem in self.consumed:
            return 'duplicate'
        self.consumed.add(idem)
        return 'applied'

b = Broker()
key = hashlib.md5(b'order:7').hexdigest()[:12]
b.transact('order.paid:7', key)
b.dispatch()
b.dispatch()
print('delivered', len(b.delivered))
print('first', b.consume(key))
print('retry', b.consume(key))
print('applied_once', len(b.consumed))
print('reconcile', len(b.delivered), len(b.consumed))
