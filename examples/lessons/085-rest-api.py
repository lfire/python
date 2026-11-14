"""
第 085 讲 · REST API 设计、OpenAPI 与幂等
与教程正文一一对应的示例代码

课程页面：/server/rest-api
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/085-rest-api.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/085-rest-api.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# ('created', 1)
# ('replayed', 1)
# order count 1

import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, amount INTEGER)')
db.execute('CREATE TABLE idempotency (key TEXT PRIMARY KEY, order_id INTEGER)')

def place_order(key, amount):
    row = db.execute('SELECT order_id FROM idempotency WHERE key=?', (key,)).fetchone()
    if row is not None:
        return ('replayed', row[0])
    cur = db.execute('INSERT INTO orders (amount) VALUES (?)', (amount,))
    oid = cur.lastrowid
    db.execute('INSERT INTO idempotency (key, order_id) VALUES (?, ?)', (key, oid))
    return ('created', oid)

print(place_order('k-100', 50))
print(place_order('k-100', 50))
print('order count', db.execute('SELECT COUNT(*) FROM orders').fetchone()[0])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# 201 created
# 200 replay 99
# 201 created

import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE charges (key TEXT PRIMARY KEY, amount INT)')

def charge(key, amount):
    cur = db.execute('INSERT OR IGNORE INTO charges (key, amount) VALUES (?, ?)', (key, amount))
    if cur.rowcount == 1:
        return '201 created'
    return '200 replay ' + str(db.execute('SELECT amount FROM charges WHERE key=?', (key,)).fetchone()[0])

print(charge('pay-1', 99))
print(charge('pay-1', 99))
print(charge('pay-2', 10))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# POST idempotent False params ['body', 'idempotency_key']
# PUT idempotent True params ['body', 'idempotency_key']
# GET idempotent True params ['page', 'size']

import inspect

def write_endpoint(body: dict, idempotency_key: str = ''):
    return (body, idempotency_key)
def read_endpoint(page: int = 1, size: int = 20):
    return (page, size)

IDEMPOTENT = frozenset(('GET', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'))
for method, fn in (('POST', write_endpoint), ('PUT', write_endpoint), ('GET', read_endpoint)):
    param_names = list(inspect.signature(fn).parameters)
    print(method, 'idempotent', method in IDEMPOTENT, 'params', param_names)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import sqlite3
import uuid

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, amount INT)')
db.execute('CREATE TABLE idem (key TEXT PRIMARY KEY, order_id INT, amount INT)')

def error(code, message, rid):
    return {'code': code, 'message': message, 'request_id': rid}

def create_order(amount, key, rid):
    if amount <= 0:
        return (422, error('invalid_amount', 'amount must be > 0', rid))
    try:
        db.execute('BEGIN')
        cur = db.execute('INSERT OR IGNORE INTO idem (key, order_id, amount) VALUES (?, -1, ?)', (key, amount))
        if cur.rowcount == 0:
            row = db.execute('SELECT order_id FROM idem WHERE key=?', (key,)).fetchone()
            db.execute('ROLLBACK')
            return (200, {'id': row[0], 'replayed': True})
        o = db.execute('INSERT INTO orders (amount) VALUES (?)', (amount,))
        db.execute('UPDATE idem SET order_id=? WHERE key=?', (o.lastrowid, key))
        db.execute('COMMIT')
        return (201, {'id': o.lastrowid, 'replayed': False})
    except sqlite3.Error:
        db.execute('ROLLBACK')
        return (500, error('db_error', 'write failed', rid))

def list_orders(after=0, limit=2):
    rows = db.execute('SELECT id, amount FROM orders WHERE id>? ORDER BY id LIMIT ?', (after, limit)).fetchall()
    return (200, {'items': [{'id': r[0], 'amount': r[1]} for r in rows]})

r1 = str(uuid.uuid4())[:8]
print(create_order(50, 'pay-1', r1))
print(create_order(50, 'pay-1', r1))
print(create_order(0, 'pay-2', r1))
create_order(30, 'pay-3', r1)
create_order(20, 'pay-4', r1)
print(list_orders(after=1, limit=2))
