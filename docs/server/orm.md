---
title: 第 087 讲 · SQLAlchemy、连接池、事务与迁移
description: 写出可控、可诊断的数据库访问层
---

<StageHeader stage='L8 · 服务端与数据' level='★★★★☆' time='45 分钟' goal='写出可控、可诊断的数据库访问层' prereq='第 086 讲 · WebSocket / SSE / 长轮询与实时推送' />

# 第 087 讲 · SQLAlchemy、连接池、事务与迁移

接口与推送都通了，数据得有落脚处。前面读写靠临时文件或内存字典，表一涨到几十万行，查询就从几十毫秒变成几秒。这一讲借 SQLAlchemy 把数据库访问收成可控、可诊断的层。

订单列表小数据上很快，上线三个月却占满连接池；加索引没用，改成全局单例又读到未提交的数据——根子在循环里逐条查关联，SQL 条数随行数增长。理清 Engine、Session 与工作单元，再谈连接池参数与事务边界，接着用可数的 SQL 条数认出 N+1 查询，最后落到 Alembic 迁移的回滚。需要函数、上下文管理器与基本 SQL；学完能写出边界清楚的事务，也能诊断慢查询。


## 列表接口随数据量线性变慢，本地测试却完全正常

一个订单列表接口在本地测试集上响应 30 毫秒，上线三个月后数据表涨到二十万行，同样的接口变成 8 秒，偶尔还把连接池占满。团队先给外键加索引，几乎没改善；再把数据库连接改成全局单例，结果并发下不同请求读到了彼此未提交的数据。

真正原因藏在两处：一是 ORM 在循环里对每个用户各发一条关联查询，SQL 条数等于 1 加父行数，随数据线性增长，小数据集完全看不出来；二是把 Session 当成了连接，让一个长生命周期对象跨请求复用，事务边界与对象状态全部失控。另一类事故来自迁移脚本只写了 upgrade 没写 downgrade，发布失败时无法回滚。

本讲用 sqlite3 把 N+1 变成可数的 SQL 条数，再把 Engine、Session、事务与迁移的边界讲清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='列表接口随数据量线性变慢，本地测试却完全正常：循环中对每个父对象访问关联属性触发懒加载，SQL 条数为 1+N，小数据集看不出' />


## Engine、Session 与 Unit of Work 各管什么

`create_engine(url)` 返回的是 Engine，它是连接池与 SQL 方言的入口，不是一条连接。

默认池是 QueuePool，关键参数：`pool_size=5`（常驻连接数）、`max_overflow=10`（池满后最多再临时借出的连接）、`pool_timeout=30`（无可用连接时等待的秒数）、`pool_recycle=3600`（连接存活超过该秒数就回收，规避 MySQL wait_timeout 主动断连）、`pool_pre_ping=True`（每次借出前发一条探活语句）、`echo=False`（为 True 时把所有 SQL 打到日志）。

`engine.connect()` 才真正借出连接。

Session 由 `sessionmaker(bind=engine)` 产生，语义是工作单元（Unit of Work）而非连接：它维护 identity map（同一主键在同一 Session 里只对应一个对象）、跟踪新增/脏/删除状态、在 flush 时按依赖顺序生成 SQL、commit 时提交事务。

Session 借连接是惰性且用完即还的，因此长 Session 不等于长连接，但一个开了事务却迟迟不提交的 Session 会一直占着借出的连接。

SQLAlchemy 2.0（2023 年发布）统一用 `select()` 配 `session.execute()`，弃用旧式 `session.query()`，并要求显式 begin，autocommit 模式被移除。

expire_on_commit 默认 True，commit 后对象属性过期，模板里再访问会触发重查甚至 DetachedInstanceError。

**create_engine 连接池关键参数（默认 QueuePool）**

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| pool_size | 5 | 常驻连接数 |
| max_overflow | 10 | 池满后可临时借出的额外连接 |
| pool_timeout | 30 | 无可用连接时等待秒数 |
| pool_recycle | 3600 | 连接存活超过该秒数即回收，规避 MySQL wait_timeout |
| pool_pre_ping | False | 借出前发探活语句，建议设 True |
| echo | False | 为 True 时打印全部 SQL 便于诊断 |

<Callout type="tip" title='核心心智模型' text='create_engine(url) 返回的是 Engine，它是连接池与 SQL 方言的入口，不是一条连接。默认池是 QueuePool，关键参数：pool_size=5（常驻连接数）、max_overflow=10（池满后最多再临时借出的连接）、pool_timeout=30（无可用连接时等待的' />

<ConceptDiagram type='layers3' title='第 087 讲 · Engine、Session 与 Unit of Work：三个常被当成一个东西的对象' labels='Engine、Session 与 Unit |事务边界与隔离级别：短事务、正确级别、可诊断|N+1、加载策略与 Alembic 迁移' caption='写出可控、可诊断的数据库访问层' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 主示例：一次会话里的对象生命周期

```python
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
```

<OutputBox title='主示例运行结果' output='N+1 result [(&#39;a&#39;, 30), (&#39;b&#39;, 30), (&#39;c&#39;, 40)]\nJOIN result {&#39;a&#39;: 30, &#39;b&#39;: 30, &#39;c&#39;: 40}\nN+1 queries 4\nJOIN queries 1' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE users (id INT, name TEXT)&#39;)\ndb.execute(&#39;CREATE TABLE orders (id INT, uid INT, total INT)&#39;)\ndb.executemany(&#39;INSERT INTO users VALUES (?,?)&#39;, [(1,&#39;a&#39;),(2,&#39;b&#39;),(3,&#39;c&#39;)])\ndb.executemany(&#39;INSERT INTO orders VALUES (?,?,?)&#39;, [(1,1,10),(2,1,20),(3,2,30),(4,3,40)])\n\ndef count_queries(fn):\n    n = [0]\n    db.set_trace_callback(lambda q: n.__setitem__(0, n[0]+1))\n    fn()\n    db.set_trace_callback(None)\n    return n[0]\n\ndef n_plus_one():\n    out = []\n    for uid, name in db.execute(&#39;SELECT id, name FROM users&#39;).fetchall():\n        orders = db.execute(&#39;SELECT total FROM orders WHERE uid=?&#39;, (uid,)).fetchall()\n        out.append((name, sum(r[0] for r in orders)))\n    return out\n\ndef join_once():\n    rows = db.execute(&#39;SELECT u.name, o.total FROM users u LEFT JOIN orders o ON u.id=o.uid&#39;).fetchall()\n    totals = {}\n    for name, total in rows:\n        totals[name] = totals.get(name, 0) + (total or 0)\n    return totals\n\nprint(&#39;N+1 result&#39;, n_plus_one())\nprint(&#39;JOIN result&#39;, join_once())\nprint(&#39;N+1 queries&#39;, count_queries(n_plus_one))\nprint(&#39;JOIN queries&#39;, count_queries(join_once))' :notes='["导入 sqlite3，用内存库模拟关系数据库，无需外部服务", "建立内存连接", "建 users 父表，三个用户", "建 orders 子表，uid 关联到 users", "批量插入三个用户，避免逐条 execute 干扰计数", "批量插入四条订单，用户 1 有两条", "定义计数函数，用 trace 回调统计 SQL 条数", "用单元素列表在闭包里累计次数", "set_trace_callback 对执行的每条语句调用一次", "执行被测函数，期间所有 SQL 被计数", "取消回调，避免后续语句计入", "返回累计条数", "N+1 写法：先取全部用户", "out 保存每个用户的汇总", "遍历用户，父查询已一次性取回", "对每个用户再发一条子查询，正是 1+N 的来源", "累加该用户的订单金额", "返回汇总列表", "对照写法：一条 JOIN 取回全部数据", "LEFT JOIN 保留无订单用户，行数按订单展开", "在 Python 侧按用户名归集总额", "遍历 JOIN 结果的每一行，取出用户名与金额", "逐行累加，total 为 NULL 时按 0 处理", "返回聚合字典", "打印两种写法的结果，验证等价", "打印 JOIN 结果，与 N+1 一致", "N+1 触发 1 条父查询 + 3 条子查询 = 4 条", "JOIN 只发 1 条 SQL，与父行数无关"]' title='第 087 讲 · SQLAlchemy、连接池、事务与迁移' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
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
```

<OutputBox title='原理验证' output='sql count 4\n  SELECT id FROM u\n  SELECT * FROM o WHERE uid=1\n  SELECT * FROM o WHERE uid=2\n  SELECT * FROM o WHERE uid=3' />


## 对照：懒加载触发的 N+1 与预加载的 SQL 条数

```python
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
```

<OutputBox title='对照写法：先自己猜，再点开' output='after rollback 0\nafter commit 1' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE users (id INT, name TEXT)&#39;)\ndb.execute(&#39;CREATE TABLE orders (id INT, uid INT, total INT)&#39;)\ndb.executemany(&#39;INSERT INTO users VALUES (?,?)&#39;, [(1,&#39;a&#39;),(2,&#39;b&#39;),(3,&#39;c&#39;)])\ndb.executemany(&#39;INSERT INTO orders VALUES (?,?,?)&#39;, [(1,1,10),(2,1,20),(3,2,30),(4,3,40)])\n\ndef count_queries(fn):\n    n = [0]\n    db.set_trace_callback(lambda q: n.__setitem__(0, n[0]+1))\n    fn()\n    db.set_trace_callback(None)\n    return n[0]\n\ndef n_plus_one():\n    out = []\n    for uid, name in db.execute(&#39;SELECT id, name FROM users&#39;).fetchall():\n        orders = db.execute(&#39;SELECT total FROM orders WHERE uid=?&#39;, (uid,)).fetchall()\n        out.append((name, sum(r[0] for r in orders)))\n    return out\n\ndef join_once():\n    rows = db.execute(&#39;SELECT u.name, o.total FROM users u LEFT JOIN orders o ON u.id=o.uid&#39;).fetchall()\n    totals = {}\n    for name, total in rows:\n        totals[name] = totals.get(name, 0) + (total or 0)\n    return totals\n\nprint(&#39;N+1 result&#39;, n_plus_one())\nprint(&#39;JOIN result&#39;, join_once())\nprint(&#39;N+1 queries&#39;, count_queries(n_plus_one))\nprint(&#39;JOIN queries&#39;, count_queries(join_once))", "note": "Engine、Session 与 Unit of Work：三个常被当成一个东西的对象"}, {"label": "对照 / 进阶", "code": "import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE t (id INT, v INT)&#39;)\ntry:\n    db.execute(&#39;BEGIN&#39;)\n    db.execute(&#39;INSERT INTO t VALUES (1, 10)&#39;)\n    db.execute(&#39;INSERT INTO t VALUES (2, 20)&#39;)\n    db.execute(&#39;ROLLBACK&#39;)\nexcept sqlite3.Error:\n    pass\nprint(&#39;after rollback&#39;, db.execute(&#39;SELECT COUNT(*) FROM t&#39;).fetchone()[0])\ndb.execute(&#39;BEGIN&#39;)\ndb.execute(&#39;INSERT INTO t VALUES (3, 30)&#39;)\ndb.execute(&#39;COMMIT&#39;)\nprint(&#39;after commit&#39;, db.execute(&#39;SELECT COUNT(*) FROM t&#39;).fetchone()[0])", "note": "事务边界与隔离级别：短事务、正确级别、可诊断"}]' title='两种写法切换看' />

**加载策略与 SQL 条数**

| 策略 | SQL 条数 | 适用 / 注意 |
| --- | --- | --- |
| lazy='select' | 1 + N | 默认，访问关联时才查，线上易成 N+1 |
| selectinload | 2 | 一条 IN 查询取集合，适合一对多 |
| joinedload | 1 | JOIN 取回，一对多会重复父行需去重 |
| raiseload | 0（未加载即抛错） | 测试环境主动暴露漏掉的预加载 |
| bulk_insert_mappings | 按批 | 批量写，别在循环里逐条 commit |


## 事务边界与隔离级别：短事务、正确级别

事务要满足 ACID，隔离级别决定并发下能看到什么：READ UNCOMMITTED 允许脏读；READ COMMITTED 避免脏读但同一事务里两次读同一行可能不同（不可重复读）；REPEATABLE READ 靠 MVCC 保证事务内重复读一致，MySQL InnoDB 默认为它并用间隙锁抑制部分幻读；

SERIALIZABLE 最强但并发最低。PostgreSQL 默认是 READ COMMITTED，SQLAlchemy 用 create_engine(..., isolation_level='REPEATABLE READ') 或对连接设 execution_options 覆盖。

边界写法要显式且尽量短：写操作用 with `session.begin()`: 包住，只读查询开独立 Session，绝不把 HTTP 调用、文件 IO 或人工确认塞进事务里。

长事务的代价很具体：借出的连接迟迟不归还池、行锁与间隙锁阻塞其它写入、MVCC 旧版本无法回收导致表膨胀。

排查用数据库侧的 pg_stat_activity 或 `information_schema.innodb_trx` 找长事务，应用侧用 before_cursor_execute 事件记录每条 SQL 与耗时。

批量写用 bulk_insert_mappings 或 executemany 一次提交，别在循环里逐条 commit——那既放大往返开销，又把一次逻辑操作拆成多个事务。

**隔离级别与并发现象**

| 级别 | 避免 | 仍可能发生 |
| --- | --- | --- |
| READ UNCOMMITTED | 无 | 脏读 |
| READ COMMITTED | 脏读 | 不可重复读（PostgreSQL 默认） |
| REPEATABLE READ | 脏读、不可重复读 | 幻读（MySQL InnoDB 默认，间隙锁缓解） |
| SERIALIZABLE | 三者 | 并发度最低 |


## 加载策略与迁移：从 N+1 到 Alembic 可回滚

N+1 是遍历 N 个父对象、对每个再查一次关联，SQL 条数为 1+N，随 N 线性增长；二十万行父表就是二十万次往返，本地二十行测试集毫无征兆。加载策略按关系类型选：默认 lazy='select' 在访问属性时才查；

selectinload 用一条 WHERE id IN (...) 把全部关联一次取回（总条数固定、适合一对多集合）；joinedload 用 JOIN 一条 SQL 取回（条数 1，但一对多会让父行重复，需在内存去重，且大集合列数膨胀）；raiseload 可在测试环境把未预加载的访问直接抛错，让 N+1 当场暴露。

检测手段有 `echo=True`、SQLAlchemy 事件计数、或 sqlite3 的 set_trace_callback 数 SQL 条数。

Alembic 管理 schema 演进：alembic init migrations 初始化，`revision --autogenerate -m` 'msg' 生成含 `upgrade()` 与 `downgrade()` 的脚本，upgrade head 应用、downgrade -1 回滚；

脚本必须成对、纳入版本库，CI 里从空库 upgrade head 再 downgrade base 演一遍。部署顺序是先跑迁移再发代码，且迁移要对新旧两版代码兼容（先加可空列、分两次发布再删旧列），否则滚动发布期间旧代码会因缺列报错。

SQLAlchemy 的 Session 实现 Unit of Work：它内部用 identity map（以 (类, 主键) 为键的弱引用字典）保证同一行在一个事务里只有一个 Python 对象，用状态集合记录 new/dirty/deleted，flush 时按表间依赖拓扑排序生成 INSERT/UPDATE/DELETE，commit 时把整批语句放进一个数据库事务提交。

这种延迟批量让多次属性修改合并成一条 UPDATE，但也意味着 SQL 在你访问属性或 flush 之前不会发出——N+1 正是懒加载在遍历时逐条触发这条机制的结果。

连接来自 Engine 的 QueuePool：池用队列保存空闲连接，借出时校验 pool_recycle 与 pre_ping，归还时回滚未提交事务并放回队列，所以『连接』和『Session』生命周期解耦。

数据库侧的隔离由 MVCC 与锁实现：READ COMMITTED 每条语句新建读视图，REPEATABLE READ 整个事务复用同一快照，InnoDB 再用间隙锁阻止范围内插入以抑制幻读。

Alembic 不直接改库，而是把 schema 差异渲染成带 upgrade/downgrade 的 Python 脚本，靠 version 表记录当前 revision，从而让迁移可版本化、可回滚。

<Term word='Engine / Session / Unit of Work' text='create_engine(url) 返回的是 Engine，它是连接池与 SQL 方言的入口，不是一条连接。默认池是 QueuePool，关键参数：pool_size=5（常驻连接数）、max_overflow=10（池满后最多再临时借出的连接）、pool_timeout=30（无可用连接时等待的秒数）、pool_r' />

<Term word='连接池参数' text='事务要满足 ACID，隔离级别决定并发下能看到什么：READ UNCOMMITTED 允许脏读；READ COMMITTED 避免脏读但同一事务里两次读同一行可能不同（不可重复读）；REPEATABLE READ 靠 MVCC 保证事务内重复读一致，MySQL InnoDB 默认为它并用间隙锁抑制部分幻读；SERIAL' />


## 可控的仓储层：短事务、预加载与可回滚迁移

下面把数据访问层做成不依赖 ORM 框架的最小实现，用来说明三条工程约束如何落地：`report()` 用一条 JOIN 把所有关联一次取回，绝不在循环里查库，等价 selectinload 的效果；

`transfer()` 把两步 UPDATE 包在同一个 BEGIN/COMMIT 里，异常则 ROLLBACK，保证转账要么全做要么全不做，且事务里没有远程调用；所有读都通过同一个连接句柄但每次 execute 自备语句，不缓存跨请求的 Session。

真实项目把 conn 换成 Session、把 JOIN 换成 selectinload、把 BEGIN/COMMIT 换成 with `session.begin()`，结构不变。

迁移侧同理：每个变更都写成可 upgrade 可 downgrade 的成对脚本，发布前在 CI 里从空库演一遍。

```python
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
```

<Callout type="idea" title='落地提示' text='显式 selectinload / joinedload、事务尽量短、只读查询用独立 session；迁移脚本必须可回滚并在 CI 演一遍' />

<CheckList id='P087b' title='上线前自检' :items='["能复现并解释「列表接口随数据量线性变慢，本地测试却完全正常」", "能复现并解释「把 Session 做成模块级全局单例，并发请求串了数据」", "能复现并解释「迁移脚本只写 upgrade，发布失败无法回滚」", "能用一条命令验证 Engine / Session / Unit of Work", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE t(k TEXT UNIQUE)'); print('ok')"
```

把输入换成你自己的数据，观察结果是否仍符合 **Engine / Session / Unit of Work** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 列表接口随数据量线性变慢，本地测试却完全正常 | 循环中对每个父对象访问关联属性触发懒加载，SQL 条数为 1+N，小数据集看不出 | 对集合用 selectinload、对多对一用 joinedload；在测试环境用 raiseload 禁止懒加载，并用 set_trace_callback 或 echo 数 SQL 条数守住 |
| 把 Session 做成模块级全局单例，并发请求串了数据 | Session 不是连接也不是线程安全的，identity map 与未提交事务被多个请求共享 | 用 sessionmaker 按请求创建 Session，with session.begin(): 显式包住写操作，响应结束即 close；只读查询用独立 Session |
| 迁移脚本只写 upgrade，发布失败无法回滚 | downgrade 缺失或没在 CI 里演过，revision 无法回退到上一个可用 schema | 每个 revision 都写可逆的 upgrade/downgrade，CI 从空库跑 upgrade head 再 downgrade base 验证；滚动发布期间迁移要兼容新旧两版代码 |

<Callout type="warn" title='本讲最容易踩的坑' text='列表接口随数据量线性变慢，本地测试却完全正常：循环中对每个父对象访问关联属性触发懒加载，SQL 条数为 1+N，小数据集看不出' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：列表接口随数据量线性变慢，本地测试却完全正常", "body": "循环中对每个父对象访问关联属性触发懒加载，SQL 条数为 1+N，小数据集看不出", "tip": "对集合用 selectinload、对多对一用 joinedload；在测试环境用 raiseload 禁止懒加载，并用 set_trace_callback 或 echo 数 SQL 条数守住"}, {"title": "第 2 步：把 Session 做成模块级全局单例，并发", "body": "Session 不是连接也不是线程安全的，identity map 与未提交事务被多个请求共享", "tip": "用 sessionmaker 按请求创建 Session，with session.begin(): 显式包住写操作，响应结束即 close；只读查询用独立 Session"}, {"title": "第 3 步：迁移脚本只写 upgrade，发布失败无法回", "body": "downgrade 缺失或没在 CI 里演过，revision 无法回退到上一个可用 schema", "tip": "每个 revision 都写可逆的 upgrade/downgrade，CI 从空库跑 upgrade head 再 downgrade base 验证；滚动发布期间迁移要兼容新旧两版代码"}]' />


## identity map 的键结构与 Unit of Work 的拓扑排序

identity map 的源码在 Lib/sqlalchemy/orm/`identity.py` 的 WeakInstanceDict：键是 identity key，即 (映射类, 主键值元组, identity_token)，值是 `weakref.ref` 到实例，实例被 GC 时由回调把键清掉。

为什么用 identity key 而不是 `id(obj)`：Session 在 refresh、merge 与跨结果集查询时是按数据库主键判断「这是同一行」，与 Python 对象地址无关；identity_token 用于分片或多绑定场景区分同主键不同库的记录。

InstanceState（Lib/sqlalchemy/orm/`state.py`）挂在每个映射实例的 _sa_instance_state 上，committed_state 保存上次 flush 后的属性快照，属性赋值经 InstrumentedAttribute 的 `__set__` 触发 `state._modified_event()` 把对象标脏但不发 SQL。

flush 时 Lib/sqlalchemy/orm/`unitofwork.py` 的 UOWTransaction 按 mapper 的外键依赖图做拓扑排序：先 INSERT 父表再 INSERT 子表，DELETE 逆序；

两表互引外键形成的环由 relationship 的 `post_update=True` 断掉，即第二轮补一条 UPDATE。

`persistence.py` 的 _organize_states_for_save 再按 (表, 操作类型) 分组走 executemany 批量执行，复杂度 `O(V+E)`（V 是待 flush 的 mapper 与 state 数）。

这就是正文「多次属性修改合并成一条 UPDATE」「N+1 是懒加载触发」的源码根据，而不是 API 层面的约定。

```python
class InstanceState:
    def __init__(self, key, table):
        self.key = key
        self.table = table
        self.committed = {}
        self.dirty = set()

class Row:
    def __init__(self, table, pk, **attrs):
        self.table = table
        self.pk = pk
        self.state = InstanceState((table, pk), table)
        for k, v in attrs.items():
            setattr(self, k, v)
        self.state.committed = dict(attrs)

class Session:
    def __init__(self):
        self.identity_map = {}
        self.new = []
        self.dirty = []
    def add(self, row):
        self.identity_map[(row.table, row.pk)] = row
        self.new.append(row)
    def get(self, table, pk):
        return self.identity_map.get((table, pk))
    def flush(self, order):
        statements = []
        for row in sorted(self.new, key=lambda r: order.index(r.table)):
            statements.append('INSERT INTO ' + row.table + ' (pk) VALUES (' + str(row.pk) + ')')
        for row in self.dirty:
            for col in row.state.dirty:
                statements.append('UPDATE ' + row.table + ' SET ' + col + '=? WHERE pk=' + str(row.pk))
        self.new.clear()
        self.dirty.clear()
        return statements

s = Session()
u = Row('users', 1, name='a')
o = Row('orders', 7, uid=1)
s.add(u)
s.add(o)
print('same object', s.get('users', 1) is u)
print('flush order', s.flush(['users', 'orders']))
u.name = 'b'
u.state.dirty.add('name')
s.dirty.append(u)
print('second flush', s.flush(['users', 'orders']))

```

<OutputBox title='扩展示例运行结果' output='same object True\nflush order [&#39;INSERT INTO users (pk) VALUES (1)&#39;, &#39;INSERT INTO orders (pk) VALUES (7)&#39;]\nsecond flush [&#39;UPDATE users SET name=? WHERE pk=1&#39;]' />

<LineByLine code='class InstanceState:\n    def __init__(self, key, table):\n        self.key = key\n        self.table = table\n        self.committed = {}\n        self.dirty = set()\n\nclass Row:\n    def __init__(self, table, pk, **attrs):\n        self.table = table\n        self.pk = pk\n        self.state = InstanceState((table, pk), table)\n        for k, v in attrs.items():\n            setattr(self, k, v)\n        self.state.committed = dict(attrs)\n\nclass Session:\n    def __init__(self):\n        self.identity_map = {}\n        self.new = []\n        self.dirty = []\n    def add(self, row):\n        self.identity_map[(row.table, row.pk)] = row\n        self.new.append(row)\n    def get(self, table, pk):\n        return self.identity_map.get((table, pk))\n    def flush(self, order):\n        statements = []\n        for row in sorted(self.new, key=lambda r: order.index(r.table)):\n            statements.append(&#39;INSERT INTO &#39; + row.table + &#39; (pk) VALUES (&#39; + str(row.pk) + &#39;)&#39;)\n        for row in self.dirty:\n            for col in row.state.dirty:\n                statements.append(&#39;UPDATE &#39; + row.table + &#39; SET &#39; + col + &#39;=? WHERE pk=&#39; + str(row.pk))\n        self.new.clear()\n        self.dirty.clear()\n        return statements\n\ns = Session()\nu = Row(&#39;users&#39;, 1, name=&#39;a&#39;)\no = Row(&#39;orders&#39;, 7, uid=1)\ns.add(u)\ns.add(o)\nprint(&#39;same object&#39;, s.get(&#39;users&#39;, 1) is u)\nprint(&#39;flush order&#39;, s.flush([&#39;users&#39;, &#39;orders&#39;]))\nu.name = &#39;b&#39;\nu.state.dirty.add(&#39;name&#39;)\ns.dirty.append(u)\nprint(&#39;second flush&#39;, s.flush([&#39;users&#39;, &#39;orders&#39;]))\n' :notes='["InstanceState 对应 _sa_instance_state，committed 存 flush 后快照", "dirty 集合记录被改过的列名，属性赋值只标脏不发 SQL", "Row 把 (表, 主键) 作为 identity key 的来源", "Session.identity_map 用字典模拟 WeakInstanceDict 的按键索引", "add 同时登记 identity map 与待插入列表", "get 按 (表, 主键) 取回，验证同一行返回同一对象", "flush 的 order 参数即 mapper 依赖图的拓扑序", "按拓扑序生成 INSERT，父表 users 必须排在子表 orders 前", "脏对象按列生成 UPDATE，多次修改同名列合并为一条", "清空 new 与 dirty，模拟 flush 之后状态复位", "构造 users 与 orders 两个存在外键依赖的实例", "打印 identity map 命中结果，确认一行一对象", "打印首次 flush 的语句顺序，验证父先子后", "改 name 后把列记进 dirty 集合", "第二次 flush 只产出一条 UPDATE，不重发 INSERT", "N+1 是 1+N 条 SQL；集合用 selectinload（2 条）、多对一用 joinedload（1 条），测试用 raiseload 暴露", "隔离级别：MySQL InnoDB 默认 REPEATABLE READ，PostgreSQL 默认 READ COMMITTED；事务要短", "Alembic 的 upgrade/downgrade 必须成对且 CI 演一遍；滚动发布期迁移要兼容新旧代码", "Engine 是连接池工厂（默认 QueuePool：pool_size=5、max_overflow=10、pool_pre_ping 建议 True），不是连接", "Session 是 Unit of Work：identity map + 脏状态跟踪 + flush 批量发 SQL，不线程安全、按请求创建", "SQLAlchemy 2.0 用 select() + session.execute()，弃用 query()，要求显式 begin；expire_on_commit 默认 True", "N+1 是 1+N 条 SQL；集合用 selectinload（2 条）、多对一用 joinedload（1 条），测试用 raiseload 暴露", "隔离级别：MySQL InnoDB 默认 REPEATABLE READ，PostgreSQL 默认 READ COMMITTED；事务要短", "Alembic 的 upgrade/downgrade 必须成对且 CI 演一遍；滚动发布期迁移要兼容新旧代码", "Engine 是连接池工厂（默认 QueuePool：pool_size=5、max_overflow=10、pool_pre_ping 建议 True），不是连接", "Session 是 Unit of Work：identity map + 脏状态跟踪 + flush 批量发 SQL，不线程安全、按请求创建", "SQLAlchemy 2.0 用 select() + session.execute()，弃用 query()，要求显式 begin；expire_on_commit 默认 True", "N+1 是 1+N 条 SQL；集合用 selectinload（2 条）、多对一用 joinedload（1 条），测试用 raiseload 暴露", "隔离级别：MySQL InnoDB 默认 REPEATABLE READ，PostgreSQL 默认 READ COMMITTED；事务要短", "Alembic 的 upgrade/downgrade 必须成对且 CI 演一遍；滚动发布期迁移要兼容新旧代码", "Engine 是连接池工厂（默认 QueuePool：pool_size=5、max_overflow=10、pool_pre_ping 建议 True），不是连接", "Session 是 Unit of Work：identity map + 脏状态跟踪 + flush 批量发 SQL，不线程安全、按请求创建", "SQLAlchemy 2.0 用 select() + session.execute()，弃用 query()，要求显式 begin；expire_on_commit 默认 True", "N+1 是 1+N 条 SQL；集合用 selectinload（2 条）、多对一用 joinedload（1 条），测试用 raiseload 暴露", "隔离级别：MySQL InnoDB 默认 REPEATABLE READ，PostgreSQL 默认 READ COMMITTED；事务要短", "Alembic 的 upgrade/downgrade 必须成对且 CI 演一遍；滚动发布期迁移要兼容新旧代码", "Engine 是连接池工厂（默认 QueuePool：pool_size=5、max_overflow=10、pool_pre_ping 建议 True），不是连接", "Session 是 Unit of Work：identity map + 脏状态跟踪 + flush 批量发 SQL，不线程安全、按请求创建", "SQLAlchemy 2.0 用 select() + session.execute()，弃用 query()，要求显式 begin；expire_on_commit 默认 True", "N+1 是 1+N 条 SQL；集合用 selectinload（2 条）、多对一用 joinedload（1 条），测试用 raiseload 暴露", "隔离级别：MySQL InnoDB 默认 REPEATABLE READ，PostgreSQL 默认 READ COMMITTED；事务要短", "Alembic 的 upgrade/downgrade 必须成对且 CI 演一遍；滚动发布期迁移要兼容新旧代码", "Engine 是连接池工厂（默认 QueuePool：pool_size=5、max_overflow=10、pool_pre_ping 建议 True），不是连接", "Session 是 Unit of Work：identity map + 脏状态跟踪 + flush 批量发 SQL，不线程安全、按请求创建", "SQLAlchemy 2.0 用 select() + session.execute()，弃用 query()，要求显式 begin；expire_on_commit 默认 True"]' title='扩展示例逐行讲解' />


### pysqlite 的隐式 BEGIN 与 autocommit 边界

Python 标准库 sqlite3 的 legacy transaction control 是 PEP 249 留下的坑：默认 isolation_level 非空串时，pysqlite 只对 INSERT、UPDATE、DELETE、REPLACE 这类 DML 隐式发 BEGIN，对 SELECT 与 DDL 不开事务，COMMIT 之后也不会自动开启新事务；

connect(':memory:') 在多线程下每个线程拿到独立连接，只有 SingletonThreadPool 或 StaticPool 才共享同一个内存库。

把 isolation_level 设为 None 进入 autocommit，此时必须显式写 BEGIN 或 BEGIN IMMEDIATE 才能拿到写锁，否则两个连接并发写会撞上 database is locked，而且 SQLite 的锁是库级而非行级，一个写事务会阻塞所有其它写者。

SQLAlchemy 的 pysqlite 方言（Lib/sqlalchemy/dialects/sqlite/`pysqlite.py`）为此在 do_begin 里补发 BEGIN，并用事件钩子把 BEGIN 追加到 DDL 之前，官方文档专门用一节讲 Serializable isolation、Savepoints 与 Transactional DDL。

故障往往出在「以为把 with `session.begin()` 换成显式 BEGIN 就等价」：DDL 没进事务，迁移中途失败就留下半张表，且 rollback 只撤掉了 INSERT。

正文讲的是隔离级别标准，这里讲的是驱动层到底什么时候才真的开了事务。

**SQLAlchemy 与 pysqlite 的源码组件**

| 组件 | 源码位置 | 数据结构 / 行为 |
| --- | --- | --- |
| WeakInstanceDict | Lib/sqlalchemy/orm/identity.py | identity key 到 weakref 的字典，GC 回调清理 |
| InstanceState | Lib/sqlalchemy/orm/state.py | committed_state 存快照，_modified_event 标脏 |
| UOWTransaction | Lib/sqlalchemy/orm/unitofwork.py | 按 mapper 依赖图拓扑排序待 flush 状态 |
| _organize_states_for_save | Lib/sqlalchemy/orm/persistence.py | 按 (表, 操作) 分组后 executemany 批量发 SQL |
| QueuePool._pool | Lib/sqlalchemy/pool/impl.py | 空闲连接队列，借出校验 recycle 与 pre_ping |
| pysqlite do_begin | Lib/sqlalchemy/dialects/sqlite/pysqlite.py | legacy 模式只对 DML 隐式发 BEGIN |


### QueuePool 借还路径与 pre_ping 的失效探测

一次迁移脚本在测试库跑得好好的，上预发却留下半张表：脚本用 `sqlite3.connect(..., isolation_level=None)` 关掉了 pysqlite 的 legacy 事务控制，以为显式 BEGIN 加 COMMIT 与 ORM 的 with `session.begin()` 等价。

但 autocommit 模式下 DDL 不进任何事务，CREATE TABLE 之后第二条语句失败时前一张表已经永久落盘，ROLLBACK 只撤掉了显式 BEGIN 里的 INSERT。

排查还发现并发写时两个连接都报 database is locked，因为 SQLite 是库级写锁，必须显式 BEGIN IMMEDIATE 才能提前占锁。

下面用标准库复现：显式 BEGIN 内的 INSERT 能被 ROLLBACK 撤销，而 autocommit 下直接 INSERT 立刻生效，in_transaction 始终为 False，说明驱动根本没有替你开事务。

```python
import sqlite3

db = sqlite3.connect(':memory:', isolation_level=None)
db.execute('CREATE TABLE t (id INT, v INT)')
db.execute('BEGIN')
db.execute('INSERT INTO t VALUES (1, 10)')
db.execute('ROLLBACK')
print('after rollback', db.execute('SELECT COUNT(*) FROM t').fetchone()[0])
print('in_transaction', db.in_transaction)
db.execute('INSERT INTO t VALUES (2, 20)')
print('autocommit rows', db.execute('SELECT COUNT(*) FROM t').fetchone()[0])
print('in_transaction after autocommit insert', db.in_transaction)

```

<Quiz no='087-X' q='关于 SQLAlchemy 的 identity map 与 flush 排序，下面哪项准确？' :options='["identity key 由类、主键元组与 identity_token 组成，用 weakref 存实例；flush 按 mapper 依赖拓扑排序，循环依赖靠 post_update 补 UPDATE 断环", "identity map 用 id(obj) 作键，因此同一行被查两次会得到两个对象", "flush 按对象创建顺序逐条发 SQL，每次属性赋值各发一条 UPDATE", "QueuePool 在每次属性访问时借出一条连接"]' answer="0" explain='identity key 与 Python 对象地址无关，Session 靠它保证同一主键一行一对象；UOWTransaction 对外键依赖做拓扑排序，父子表按序 INSERT、DELETE 逆序，互引外键用 post_update 的第二轮 UPDATE 断环。属性赋值只标脏、不发 SQL，flush 时按表分组批量执行；连接来自 QueuePool 且是惰性借还，与属性访问无关。' />


### expire_on_commit 之后的对象状态机

<Exercise title='用 identity key 判断两行是否同一对象' task='实现一个 mini identity map，用 (表, 主键元组) 作键，验证同主键两次 get 返回同一对象、新建的同主键实例不会被自动合并，并说明键里为什么不能放 id(obj)。' solution='class IdentityMap:\n    def __init__(self):\n        self._map = {}\n    def key(self, table, pk):\n        return (table, tuple(pk))\n    def put(self, table, pk, obj):\n        self._map[self.key(table, pk)] = obj\n        return obj\n    def get(self, table, pk):\n        return self._map.get(self.key(table, pk))\n\nclass Row:\n    def __init__(self, pk):\n        self.pk = pk\n\ns1 = IdentityMap()\na = s1.put(&#39;users&#39;, (1,), Row(1))\nprint(&#39;same object&#39;, s1.get(&#39;users&#39;, (1,)) is a)\nprint(&#39;identity key&#39;, s1.key(&#39;users&#39;, (1,)))\nb = Row(1)\nprint(&#39;new object not merged&#39;, s1.get(&#39;users&#39;, (1,)) is not b)\n' explain='identity map 的键是 (映射类, 主键元组, identity_token)，与 Python 对象地址无关；同一 Session 内按主键取回的必然是同一实例，因此两次修改累加到同一个对象的 committed_state，flush 时合并成一条 UPDATE。若用 id(obj) 作键，从库里重新查出的同主键行会被当成新对象，Unit of Work 就失去「一行一对象」的保证。不同 Session 各持一张 map、互不共享，这也是 Session 不能做模块级单例的原因。' />

<Term word='identity key' text='SQLAlchemy 用来标识「数据库里同一行」的元组 (映射类, 主键值元组, identity_token)：它不含 Python 对象地址，所以 refresh、merge 与跨 Session 合并都能按主键认出同一行；identity_token 用于分片或多绑定下区分同主键不同库的记录，WeakInstanceDict 以它为键存放 weakref。' />


## 练习、自测与一页纸速记

<Exercise title='基础：用 trace 回调数出 N+1' task='建 users 与 orders 两表，写 n_plus_one() 与 join_once()，用 set_trace_callback 分别统计两者的 SQL 条数，解释为什么一个随父行数增长、一个恒定。' solution='import sqlite3\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE u (id INT)&#39;)\ndb.execute(&#39;CREATE TABLE o (uid INT)&#39;)\ndb.executemany(&#39;INSERT INTO u VALUES (?)&#39;, [(1,),(2,),(3,)])\ndef count(fn):\n    n = [0]\n    db.set_trace_callback(lambda q: n.__setitem__(0, n[0]+1))\n    fn()\n    db.set_trace_callback(None)\n    return n[0]\ndef n1():\n    for (uid,) in db.execute(&#39;SELECT id FROM u&#39;).fetchall():\n        db.execute(&#39;SELECT * FROM o WHERE uid=?&#39;, (uid,)).fetchall()\ndef join():\n    db.execute(&#39;SELECT * FROM u LEFT JOIN o ON u.id=o.uid&#39;).fetchall()\nprint(&#39;n+1&#39;, count(n1), &#39;join&#39;, count(join))' explain='set_trace_callback 对每条执行语句调用一次：n1 是 1 条父查询 + 3 条子查询 = 4，join 恒为 1。父行数涨到 N 时前者变 1+N，后者不变。' />

<Exercise title='进阶：给事务加失败回滚验证原子性' task='写一个 transfer 函数把两步 UPDATE 放进同一事务，在第二步故意触发异常，验证转账前后两账户总额不变、未留下半做状态。' solution='import sqlite3\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE acct (id INT, bal INT)&#39;)\ndb.executemany(&#39;INSERT INTO acct VALUES (?,?)&#39;, [(1,100),(2,100)])\ndef transfer(src, dst, amt, fail=False):\n    try:\n        db.execute(&#39;BEGIN&#39;)\n        db.execute(&#39;UPDATE acct SET bal=bal-? WHERE id=?&#39;, (amt, src))\n        if fail: raise ValueError(&#39;boom&#39;)\n        db.execute(&#39;UPDATE acct SET bal=bal+? WHERE id=?&#39;, (amt, dst))\n        db.execute(&#39;COMMIT&#39;)\n    except Exception:\n        db.execute(&#39;ROLLBACK&#39;)\ntransfer(1, 2, 30, fail=True)\nprint(db.execute(&#39;SELECT SUM(bal) FROM acct&#39;).fetchone()[0])' explain='异常发生在两步之间时被 ROLLBACK 整体撤销，总额仍为 200；事务的原子性保证不会出现只扣不加的中间态，异常分支必须显式回滚。' />

<Quiz no='087-1' q='关于 SQLAlchemy 的 Session，下面哪项准确？' :options='["Session 是工作单元而非连接，维护 identity map 并在 flush 时批量生成 SQL", "Session 就是一条数据库连接", "Session 是线程安全的全局单例", "Session 每次属性赋值立即发一条 UPDATE"]' answer="0" explain='Session 用 identity map 保证同一主键一个对象、跟踪脏状态、flush 时批量发 SQL；它从 Engine 的池里惰性借连接、用完归还，本身不是连接也不线程安全。' />

<Quiz no='087-2' q='某对多集合关联在循环里被逐条访问，导致响应随数据量线性变慢，最合适的加载策略是？' :options='["selectinload，用一条 IN 查询一次性取回集合", "保持 lazy=&#39;select&#39; 并给外键加索引", "joinedload 并关闭去重", "在循环里手动 commit"]' answer="0" explain='selectinload 把 1+N 压成固定 2 条 SQL；joinedload 虽是 1 条但一对多会重复父行需去重；加索引不能减少往返条数，循环里 commit 更糟。' />

<Quiz no='087-3' q='关于隔离级别，下面哪项准确？' :options='["MySQL InnoDB 默认 REPEATABLE READ，PostgreSQL 默认 READ COMMITTED", "两者默认都是 SERIALIZABLE", "MySQL 默认 READ UNCOMMITTED", "PostgreSQL 默认 REPEATABLE READ"]' answer="0" explain='MySQL InnoDB 默认 REPEATABLE READ 并用 MVCC + 间隙锁缓解幻读；PostgreSQL 默认 READ COMMITTED，每条语句新建读视图。跨库迁移时这个差异会影响并发表现。' />

<Predict no='087-P' q='对 3 个用户各发一条关联查询的循环，配合 1 条父查询，用 set_trace_callback 会数到几条 SQL？' :options='["4 条", "1 条", "3 条"]' answer='0' output='sql count 4 且序列为 SELECT id FROM u 加三条 SELECT * FROM o WHERE uid=...' explain='父查询 1 条 + 每个用户 1 条子查询共 3 条 = 4，正是 1+N。看到回调里逐条展开的 uid=1/2/3，就是 N+1 最直接的证据；改成一条 JOIN 后恒为 1 条。' />

<FillBlank no='087-F' tpl='___ sqlite3' :answers='["import"]' hint='回想本讲关于 Engine / Session / Unit of Work 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Engine、Session 与 Unit of Work：三个常被当成一个东西的对象 的落点。' />

<KnowledgeCard :points='["Engine 是连接池工厂（默认 QueuePool：pool_size=5、max_overflow=10、pool_pre_ping 建议 True），不是连接", "Session 是 Unit of Work：identity map + 脏状态跟踪 + flush 批量发 SQL，不线程安全、按请求创建", "SQLAlchemy 2.0 用 select() + session.execute()，弃用 query()，要求显式 begin；expire_on_commit 默认 True", "N+1 是 1+N 条 SQL；集合用 selectinload（2 条）、多对一用 joinedload（1 条），测试用 raiseload 暴露", "隔离级别：MySQL InnoDB 默认 REPEATABLE READ，PostgreSQL 默认 READ COMMITTED；事务要短", "Alembic 的 upgrade/downgrade 必须成对且 CI 演一遍；滚动发布期迁移要兼容新旧代码"]' :pitfalls='["列表接口随数据量线性变慢，本地测试却完全正常", "把 Session 做成模块级全局单例，并发请求串了数据", "迁移脚本只写 upgrade，发布失败无法回滚", "在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地测试集太小看不出来"]' summary='ORM 的 Session 是工作单元而不是连接，理解这一点才能控制事务边界与对象生命周期' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| Engine 是连接池工厂（默认 QueuePool：pool_size=5、max_overflow=10、pool_pre_ping 建议 True），不是连接 | 建立直觉 |
| Session 是 Unit of Work：identity map + 脏状态跟踪 + flush 批量发 SQL，不线程安全、按请求创建 | 跑通示例 |
| SQLAlchemy 2.0 用 select() + session.execute()，弃用 query()，要求显式 begin；expire_on_commit 默认 True | 深入边界 |
| N+1 是 1+N 条 SQL；集合用 selectinload（2 条）、多对一用 joinedload（1 条），测试用 raiseload 暴露 | 工程落地 |
| 隔离级别：MySQL InnoDB 默认 REPEATABLE READ，PostgreSQL 默认 READ COMMITTED；事务要短 | 随堂检测 |
| Alembic 的 upgrade/downgrade 必须成对且 CI 演一遍；滚动发布期迁移要兼容新旧代码 | 复盘 |

1. Engine 是连接池工厂（默认 QueuePool：pool_size=5、max_overflow=10、pool_pre_ping 建议 True），不是连接

2. Session 是 Unit of Work：identity map + 脏状态跟踪 + flush 批量发 SQL，不线程安全、按请求创建

3. SQLAlchemy 2.0 用 select() + session.execute()，弃用 query()，要求显式 begin；expire_on_commit 默认 True

[下一讲：Redis 缓存：穿透、击穿、雪崩与分布式锁](/server/redis)
