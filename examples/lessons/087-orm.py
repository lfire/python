"""
第 087 讲 · SQLAlchemy、连接池、事务与迁移
与教程正文一一对应的示例代码

课程页面：/server/orm
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/087-orm.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/087-orm.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# N+1 result [('a', 30), ('b', 30), ('c', 40)]
# JOIN result {'a': 30, 'b': 30, 'c': 40}
# N+1 queries 4
# JOIN queries 1

import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE users (id INT, name TEXT)')
db.execute('CREATE TABLE orders (id INT, uid INT, total INT)')
db.executemany('INSERT INTO users VALUES (?,?)', [(1,'a'),(2,'b'),(3,'c')])
db.executemany('INSERT INTO orders VALUES (?,?,?)', [(1,1,10),(2,1,20),(3,2,30),(4,3,40)])

def count_queries(fn):
    n = [0]
    db.set_trace_callback(lambda q: n.__setitem__(0, n[0]+1))
    fn()
    db.set_trace_callback(None)
    return n[0]

def n_plus_one():
    out = []
    for uid, name in db.execute('SELECT id, name FROM users').fetchall():
        orders = db.execute('SELECT total FROM orders WHERE uid=?', (uid,)).fetchall()
        out.append((name, sum(r[0] for r in orders)))
    return out

def join_once():
    rows = db.execute('SELECT u.name, o.total FROM users u LEFT JOIN orders o ON u.id=o.uid').fetchall()
    totals = {}
    for name, total in rows:
        totals[name] = totals.get(name, 0) + (total or 0)
    return totals

print('N+1 result', n_plus_one())
print('JOIN result', join_once())
print('N+1 queries', count_queries(n_plus_one))
print('JOIN queries', count_queries(join_once))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# after rollback 0
# after commit 1

import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE t (id INT, v INT)')
try:
    db.execute('BEGIN')
    db.execute('INSERT INTO t VALUES (1, 10)')
    db.execute('INSERT INTO t VALUES (2, 20)')
    db.execute('ROLLBACK')
except sqlite3.Error:
    pass
print('after rollback', db.execute('SELECT COUNT(*) FROM t').fetchone()[0])
db.execute('BEGIN')
db.execute('INSERT INTO t VALUES (3, 30)')
db.execute('COMMIT')
print('after commit', db.execute('SELECT COUNT(*) FROM t').fetchone()[0])

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# sql count 4
#   SELECT id FROM u
#   SELECT * FROM o WHERE uid=1
#   SELECT * FROM o WHERE uid=2
#   SELECT * FROM o WHERE uid=3

import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE u (id INT)')
db.execute('CREATE TABLE o (uid INT)')
db.executemany('INSERT INTO u VALUES (?)', [(1,),(2,),(3,)])
seen = []
db.set_trace_callback(seen.append)
for (uid,) in db.execute('SELECT id FROM u').fetchall():
    db.execute('SELECT * FROM o WHERE uid=?', (uid,)).fetchall()
db.set_trace_callback(None)
print('sql count', len(seen))
for q in seen:
    print(' ', q)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)')
db.execute('CREATE TABLE orders (id INTEGER PRIMARY KEY, uid INT, total INT)')
db.executemany('INSERT INTO users VALUES (?,?)', [(1,'a'),(2,'b')])
db.executemany('INSERT INTO orders VALUES (?,?,?)', [(1,1,10),(2,1,20),(3,2,30)])

REPORT_SQL = ('SELECT u.id, u.name, o.total FROM users u '
              'LEFT JOIN orders o ON u.id=o.uid ORDER BY u.id')

class Repo:
    def __init__(self, conn):
        self.conn = conn
    def report(self):
        rows = self.conn.execute(REPORT_SQL).fetchall()
        out = {}
        for uid, name, total in rows:
            r = out.setdefault(uid, {'name': name, 'total': 0, 'items': 0})
            r['total'] += total or 0
            r['items'] += 1 if total is not None else 0
        return out
    def transfer(self, src, dst, amount):
        try:
            self.conn.execute('BEGIN')
            self.conn.execute('UPDATE orders SET total=total-? WHERE uid=?', (amount, src))
            self.conn.execute('UPDATE orders SET total=total+? WHERE uid=?', (amount, dst))
            self.conn.execute('COMMIT')
            return True
        except sqlite3.Error:
            self.conn.execute('ROLLBACK')
            return False

repo = Repo(db)
print('report', repo.report())
print('transfer', repo.transfer(1, 2, 5))
print('after', repo.report())
