"""
第 127 讲 · 实战 06 · 日志 ETL 与 CSV / SQL 查询工具
与教程正文一一对应的示例代码

课程页面：/projects/data-etl
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/127-data-etl.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/127-data-etl.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# dead 1 1
# agg [(10, 12), (12, 9)]
# watermark 12
# rows 2

import csv, io, sqlite3
from collections import defaultdict

RAW = chr(10).join(['id,ts,level,amount', '1,10,INFO,5', '2,11,BAD,x',
                    '3,11,INFO,7', '4,12,INFO,9']) + chr(10)

def parse(stream):
    for row in csv.DictReader(stream):
        try:
            yield dict(id=int(row['id']), ts=int(row['ts']),
                       level=row['level'], amount=int(row['amount']))
        except ValueError:
            yield None

def clean(rows, dead):
    for r in rows:
        if r is None:
            dead.append(r)
        else:
            yield r

def tumble(rows, width):
    for r in rows:
        yield r['ts'] // width * width, r

con = sqlite3.connect(':memory:')
con.execute('CREATE TABLE agg (bucket INTEGER PRIMARY KEY, total INTEGER)')
con.execute('CREATE TABLE meta (k TEXT PRIMARY KEY, v INTEGER)')

def run_once(raw, con):
    dead, agg, wm = [], defaultdict(int), 0
    for bucket, r in tumble(clean(parse(io.StringIO(raw)), dead), width=2):
        agg[bucket] += r['amount']
        wm = max(wm, r['ts'])
    for bucket, total in agg.items():
        con.execute('INSERT INTO agg(bucket,total) VALUES(?,?) '
                    'ON CONFLICT(bucket) DO UPDATE SET total=excluded.total', (bucket, total))
    con.execute('INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=max(v,excluded.v)', ('watermark', wm))
    con.commit()
    return len(dead)

print('dead', run_once(RAW, con), run_once(RAW, con))
print('agg', con.execute('SELECT bucket,total FROM agg ORDER BY bucket').fetchall())
print('watermark', con.execute('SELECT v FROM meta WHERE k=?', ('watermark',)).fetchone()[0])
print('rows', con.execute('SELECT count(*) FROM agg').fetchone()[0])

# ======================== 2. 对照写法 ========================
# 预期输出：
# naive rows 6
# gated rows 3
# wm 3

import sqlite3

con = sqlite3.connect(':memory:')
con.execute('CREATE TABLE events (id INTEGER, amount INTEGER)')
con.execute('CREATE TABLE meta (k TEXT PRIMARY KEY, v INTEGER)')

def naive_replay(con, rows):
    for i, amt in rows:
        con.execute('INSERT INTO events(id,amount) VALUES(?,?)', (i, amt))
    con.commit()

def gated_replay(con, rows):
    row = con.execute('SELECT v FROM meta WHERE k=?', ('wm',)).fetchone()
    wm = row[0] if row else 0
    for i, amt in rows:
        if i > wm:
            con.execute('INSERT INTO events(id,amount) VALUES(?,?)', (i, amt))
    con.execute('INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=max(v,excluded.v)', ('wm', max(i for i, _ in rows)))
    con.commit()

rows = [(1, 5), (2, 7), (3, 9)]
naive_replay(con, rows); naive_replay(con, rows)
print('naive rows', con.execute('SELECT count(*) FROM events').fetchone()[0])
con.execute('DELETE FROM events')
gated_replay(con, rows); gated_replay(con, rows)
print('gated rows', con.execute('SELECT count(*) FROM events').fetchone()[0])
print('wm', con.execute('SELECT v FROM meta WHERE k=?', ('wm',)).fetchone()[0])

# ======================== 3. 原理验证 ========================
# 预期输出：
# eager type list 1000
# lazy type generator
# list heavier True
# first r0

import io, sys

raw = chr(10).join('r%d' % i for i in range(1000))
eager = [l for l in raw.splitlines()]
lazy = (l for l in io.StringIO(raw))
print('eager type', type(eager).__name__, len(eager))
print('lazy type', type(lazy).__name__)
print('list heavier', sys.getsizeof(eager) > sys.getsizeof(lazy))
print('first', next(lazy))

# ======================== 4. 工程案例 ========================

import csv, io, sqlite3
from collections import defaultdict

SOURCE = chr(10).join(['ts,user,amount', '1,a,5', '2,b,BAD', '2,c,7', '3,a,9']) + chr(10)

def read_rows(stream, dead):
    for row in csv.DictReader(stream):
        try:
            yield {'ts': int(row['ts']), 'user': row['user'], 'amount': int(row['amount'])}
        except ValueError:
            dead.append(row)

def report(con, dead, wm):
    return {'rows': con.execute('SELECT count(*) FROM agg').fetchone()[0],
            'dead': len(dead), 'watermark': wm,
            'total': con.execute('SELECT sum(total) FROM agg').fetchone()[0]}

con = sqlite3.connect(':memory:')
con.execute('CREATE TABLE agg (ts INTEGER PRIMARY KEY, total INTEGER)')
con.execute('CREATE TABLE meta (k TEXT PRIMARY KEY, v INTEGER)')

def run(source):
    dead, agg, wm = [], defaultdict(int), 0
    for r in read_rows(io.StringIO(source), dead):
        agg[r['ts']] += r['amount']
        wm = max(wm, r['ts'])
    for ts, total in agg.items():
        con.execute('INSERT INTO agg(ts,total) VALUES(?,?) ON CONFLICT(ts) DO UPDATE SET total=excluded.total', (ts, total))
    con.execute('INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=max(v,excluded.v)', ('wm', wm))
    con.commit()
    return report(con, dead, wm)

print('run1', run(SOURCE))
print('run2', run(SOURCE))
