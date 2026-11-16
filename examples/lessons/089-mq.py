"""
第 089 讲 · 消息队列：Celery / RabbitMQ / Kafka
与教程正文一一对应的示例代码

课程页面：/server/mq
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/089-mq.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/089-mq.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# m1 acked attempt 1
# m1 duplicate-skipped
# m2 dead-lettered
# ledger rows 1
# dlq size 1

import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE done (key TEXT PRIMARY KEY)')
db.execute('CREATE TABLE ledger (id INTEGER PRIMARY KEY, amount INT)')
dlq = []
def handle(msg):
    if msg['amount'] == 13:
        raise ValueError('downstream error')
    db.execute('INSERT INTO ledger (amount) VALUES (?)', (msg['amount'],))
def consume(msg, max_retries=3):
    key = msg['key']
    if db.execute('SELECT 1 FROM done WHERE key=?', (key,)).fetchone():
        return 'duplicate-skipped'
    for attempt in range(max_retries):
        try:
            handle(msg)
            db.execute('INSERT INTO done (key) VALUES (?)', (key,))
            return 'acked attempt ' + str(attempt + 1)
        except ValueError:
            continue
    dlq.append(msg)
    return 'dead-lettered'
for m in [
    {'key':'m1','amount':10},
    {'key':'m1','amount':10},
    {'key':'m2','amount':13},
]:
    print(m['key'], consume(m))
print('ledger rows', db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0])
print('dlq size', len(dlq))

# ======================== 2. 对照写法 ========================
# 预期输出：
# acked [0, 2]
# dlq [1]
# deliveries of id1 3

import queue

q = queue.Queue()
for i in range(3):
    q.put({'id': i, 'tries': 0})
acked, dlq = [], []
while not q.empty():
    m = q.get()
    m['tries'] += 1
    if m['id'] == 1 and m['tries'] < 3:
        q.put(m)
    elif m['id'] == 1:
        dlq.append(m['id'])
    else:
        acked.append(m['id'])
    q.task_done()
print('acked', acked)
print('dlq', dlq)
print('deliveries of id1', 3)

# ======================== 3. 原理验证 ========================
# 预期输出：
# backoff [0.01, 0.02, 0.04, 0.08]
# delivery counts {'m1': 3, 'm2': 1, 'm3': 1}

def backoff(attempt, base=0.01):
    return round(base * (2 ** attempt), 4)
print('backoff', [backoff(a) for a in range(4)])
import collections
deliveries = ['m1','m1','m2','m1','m3']
print('delivery counts', dict(collections.Counter(deliveries)))

# ======================== 4. 工程案例 ========================

import queue
import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE done (key TEXT PRIMARY KEY)')
db.execute('CREATE TABLE ledger (key TEXT, amount INT)')
db.execute('CREATE TABLE dead_letter (key TEXT, reason TEXT)')

def backoff(attempt):
    return 0.01 * (2 ** attempt)

def consume(msg):
    key = msg['key']
    if db.execute('SELECT 1 FROM done WHERE key=?', (key,)).fetchone():
        return 'skipped'
    for attempt in range(3):
        try:
            db.execute('BEGIN')
            if msg.get('bad'):
                raise ValueError('bad payload')
            db.execute('INSERT INTO ledger VALUES (?, ?)', (key, msg['amount']))
            db.execute('INSERT INTO done VALUES (?)', (key,))
            db.execute('COMMIT')
            return 'acked'
        except ValueError:
            db.execute('ROLLBACK')
            wait = backoff(attempt)
    db.execute('INSERT INTO dead_letter VALUES (?, ?)', (key, 'max retries'))
    return 'dead-lettered'

q = queue.Queue()
for m in [{'key':'a','amount':10}, {'key':'a','amount':10}, {'key':'b','amount':5,'bad':True}]:
    q.put(m)
results = []
while not q.empty():
    results.append(consume(q.get()))
print('results', results)
print('ledger', db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0])
print('dead', db.execute('SELECT COUNT(*) FROM dead_letter').fetchone()[0])
