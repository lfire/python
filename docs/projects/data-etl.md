---
title: 第 127 讲 · 实战 06 · 日志 ETL 与 CSV / SQL 查询工具
description: 构建可回溯、可重跑的数据管道
---

<StageHeader stage='L12 · 工程实战' level='★★★☆☆' time='55 分钟' goal='构建可回溯、可重跑的数据管道' prereq='第 126 讲 · 实战 05 · 短链与图片服务' />

# 第 127 讲 · 实战 06 · 日志 ETL 与 CSV / SQL 查询工具

上一讲的请求即时来、即时走；这一讲面对攒了一天、动辄几个 G 的日志，关心的事从「响应够快」变成「隔天重跑，结果还得一样」。一条可重跑的数据管道，得把可靠性摆在速度前面。

一个脚本把文件读进内存再处理，单文件涨到几个 G 时进程被掐掉；它没有水位，失败后从头再跑，同一批事件进了两次聚合表，报表金额翻倍；几行缺列又能把整批带停。我们先用生成器管道让内存不随输入长，再把脏数据隔离进死信、按窗口聚合，最后用批量写入配 upsert 与水位保证重放幂等。需要你熟悉生成器、`csv` 与 `sqlite3` 事务；学完能搭一条重放结果不变、脏行不拖垮整批的流水线。


## 文件稍大就 OOM，失败重跑又让聚合值翻倍

一个日志 ETL 脚本用 `read()` 把整个文件读进内存再 `splitlines`，平时跑得好好的，某天上游把日志切分策略改了、单文件涨到 3GB，进程直接 OOM 被杀。更糟的是它没有水位：失败后运维从头重跑一次，同一批事件被重复写入聚合表，报表金额翻倍，谁也说不清哪次是准的。

还有几行字段缺列或金额写成非数字，脚本一遇到就整体崩掉，把已经处理好的批次也带没了。朴素解法「全量读入 + 逐行 insert + 出错就停」失败在三处：内存随输入线性增长、写入不幂等导致重放结果不一致、脏数据没有隔离。ETL 的可靠性来自「可重跑」：任何一段失败后重放，结果必须一致。

这一讲用 `csv` 生成器、`sqlite3` 的 upsert、增量水位与死信队列做一条可回溯的流式管道。

<Callout type="warn" title='先看一个真实会出错的写法' text='用 read() 全量载入日志，文件稍大就 OOM：一次性构造 N 个字符串对象，内存与输入线性增长' />


## 生成器管道与背压：内存不随输入增长

生成器是惰性求值：每次 `next` 只推进到下一个 `yield`，函数的局部变量保存在堆上的生成器帧里，因此同时驻留内存的只有当前一条记录，复杂度是 `O(1)` 而非 `O(N)`。

`csv.DictReader` 本身就是迭代器，`io.StringIO` 让字符串像文件一样被逐行读，两者组合就能把「解析 → 清洗 → 聚合 → 写入」串成一条 `yield` 管道：下游不拉动，上游就不生产，这就是背压——天然防止快生产者压垮慢消费者。

`read()` 加 `splitlines` 会一次性构造出 N 个字符串对象，内存与输入线性相关，是大文件 OOM 的直接原因。还要注意三个边界：生成器只能消费一次，重跑必须重建管道；`for` 循环里不要顺手 `list()` 把惰性又变回全量；异常要放在生成阶段就地捕获，否则一条脏数据会让整条管道终止。

失效信号是常驻内存随输入规模线性上升、以及处理速度被上游写得过快拖垮。

**流式管道各阶段职责**

| 阶段 | 输入 / 输出 | 内存特征 | 失败处理 |
| --- | --- | --- | --- |
| parse（生成器） | 文本行 → dict 或 None | O(1) 单条 | ValueError 时 yield None 不中断 |
| clean（生成器） | dict/None → 仅正常记录 | O(1) 单条 | None 进死信列表 |
| tumble（生成器） | 记录 → (桶, 记录) | O(桶数) | 按 ts // width * width 归桶 |
| upsert（批量写） | 聚合字典 → SQLite | O(桶数) | ON CONFLICT 保证重放一致 |
| meta 水位 | 本批最大 ts → 单调值 | O(1) | max(v, excluded.v) 只前进 |

```python
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
```

<OutputBox title='主示例运行结果' output='dead 1 1\nagg [(10, 12), (12, 9)]\nwatermark 12\nrows 2' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import csv, io, sqlite3\nfrom collections import defaultdict\n\nRAW = chr(10).join([&#39;id,ts,level,amount&#39;, &#39;1,10,INFO,5&#39;, &#39;2,11,BAD,x&#39;,\n                    &#39;3,11,INFO,7&#39;, &#39;4,12,INFO,9&#39;]) + chr(10)\n\ndef parse(stream):\n    for row in csv.DictReader(stream):\n        try:\n            yield dict(id=int(row[&#39;id&#39;]), ts=int(row[&#39;ts&#39;]),\n                       level=row[&#39;level&#39;], amount=int(row[&#39;amount&#39;]))\n        except ValueError:\n            yield None\n\ndef clean(rows, dead):\n    for r in rows:\n        if r is None:\n            dead.append(r)\n        else:\n            yield r\n\ndef tumble(rows, width):\n    for r in rows:\n        yield r[&#39;ts&#39;] // width * width, r\n\ncon = sqlite3.connect(&#39;:memory:&#39;)\ncon.execute(&#39;CREATE TABLE agg (bucket INTEGER PRIMARY KEY, total INTEGER)&#39;)\ncon.execute(&#39;CREATE TABLE meta (k TEXT PRIMARY KEY, v INTEGER)&#39;)\n\ndef run_once(raw, con):\n    dead, agg, wm = [], defaultdict(int), 0\n    for bucket, r in tumble(clean(parse(io.StringIO(raw)), dead), width=2):\n        agg[bucket] += r[&#39;amount&#39;]\n        wm = max(wm, r[&#39;ts&#39;])\n    for bucket, total in agg.items():\n        con.execute(&#39;INSERT INTO agg(bucket,total) VALUES(?,?) &#39;\n                    &#39;ON CONFLICT(bucket) DO UPDATE SET total=excluded.total&#39;, (bucket, total))\n    con.execute(&#39;INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=max(v,excluded.v)&#39;, (&#39;watermark&#39;, wm))\n    con.commit()\n    return len(dead)\n\nprint(&#39;dead&#39;, run_once(RAW, con), run_once(RAW, con))\nprint(&#39;agg&#39;, con.execute(&#39;SELECT bucket,total FROM agg ORDER BY bucket&#39;).fetchall())\nprint(&#39;watermark&#39;, con.execute(&#39;SELECT v FROM meta WHERE k=?&#39;, (&#39;watermark&#39;,)).fetchone()[0])\nprint(&#39;rows&#39;, con.execute(&#39;SELECT count(*) FROM agg&#39;).fetchone()[0])' :notes='["导入 csv 解析、io 造流式输入、sqlite3 做幂等落库", "defaultdict 用于按时间桶累加金额", "空行，只用于分隔逻辑块，不影响执行结果。", "用 chr(10) 拼出 CSV 源，规避示例里的反斜杠转义", "续行给出后三行数据，其中第二行 amount 是脏值 x", "空行，只用于分隔逻辑块，不影响执行结果。", "parse 是生成器：每次 next 只解析一条记录", "DictReader 逐行产出 dict，值都是字符串", "类型转换放在 try 里，脏数据不会中断整条管道", "把 id、ts、amount 转成整数，level 保留字符串", "续行完成 amount 的转换，非数字会抛 ValueError", "except ValueError 捕获非数字与缺列导致的转换失败", "转换失败时产出 None 作为脏数据标记", "空行，只用于分隔逻辑块，不影响执行结果。", "clean 把 None 分流到死信，其余继续向下游 yield", "逐条消费上游生成器，保持惰性", "None 表示上一步解析失败", "写进死信列表供质量报告统计", "正常记录才放行到聚合阶段", "yield 正常记录，继续向下游传递", "空行，只用于分隔逻辑块，不影响执行结果。", "tumble 实现滚动窗口聚合，产出 (桶, 记录)", "逐条推进，不缓存整批", "桶键是 ts 整除宽度再乘宽度，width=2 时 10/11 同桶", "空行，只用于分隔逻辑块，不影响执行结果。", "内存数据库连接，演示用；生产用文件库配 WAL", "agg 表以 bucket 为主键，是 upsert 的冲突目标", "meta 表存水位，键名固定为 watermark", "空行，只用于分隔逻辑块，不影响执行结果。", "run_once 是一次可重跑的批次，返回值是死信条数", "死信列表、聚合字典、水位三者都从干净状态开始", "串起 parse → clean → tumble 三层生成器，按需拉取", "按桶累加金额，同桶记录合并", "水位取本批最大事件时间，只前进不回退", "把每个桶的聚合结果写入数据库", "INSERT 带参数绑定，值用 ? 占位杜绝 SQL 注入", "冲突时更新为 excluded.total，重跑不会翻倍", "水位同样 upsert，用 max 保证单调不回退", "整批一次提交，减少每行事务开销", "返回死信数，作为质量报告的一项", "空行，只用于分隔逻辑块，不影响执行结果。", "连续重跑两次，死信数应一致", "打印聚合表全部行，重跑后仍是两条而非四条", "读回水位，验证按事件时间推进到 12", "统计行数，证明 upsert 让重放结果保持一致"]' title='第 127 讲 · 实战 06 · 日志 ETL 与 CSV / SQL 查询工具' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='生成器是惰性求值：每次 `next` 只推进到下一个 `yield`，函数的局部变量保存在堆上的生成器帧里，因此同时驻留内存的只有当前一条记录，复杂度是 `O(1)` 而非 `O(N)`。`csv.DictReader` 本身就是迭代器，`io.StringIO` 让字符串像文件一样被逐行读，两者组…' />

<ConceptDiagram type='layers3' title='第 127 讲 · 生成器管道与背压：内存不随输入增长' labels='生成器管道与背压：内存不随输入增长|脏数据隔离、窗口聚合与幂等写入|增量水位、质量校验与可回溯|数据质量校验' caption='构建可回溯、可重跑的数据管道' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 脏数据隔离、窗口聚合与幂等写入

`DictReader` 把每行转成 dict，但值全是字符串，`int(row['amount'])` 遇到非数字或缺失列会抛 `ValueError` 或 `KeyError`；

正确做法是在解析生成器里 `try/except` 捕获，把原始行送进死信列表（dead letter）而不是中断整批，批次结束出质量报告。

窗口聚合用 `defaultdict(int)` 累加：tumbling window 的键是 `ts // width * width`，把同一时间桶的记录并到一起；

滑动窗口则需要维护队列与过期边界。写入侧用事务包住整批（`con.commit()` 一次提交），减少每行的 `fsync`；

幂等靠主键加 SQLite 的 `INSERT`（3.24 起支持，`excluded` 是冲突行的伪表），或 MySQL 的 `ON DUPLICATE KEY UPDATE`、PostgreSQL 的 `ON CONFLICT`。

```sql
INSERT ... ON CONFLICT(key) DO UPDATE SET col = excluded.col
```

盲目 `INSERT` 在重跑时会重复入库或撞主键报错，只有「按键 upsert」才能保证同一批数据重放后聚合值不翻倍。参数一律用 `?` 占位符绑定，禁止字符串拼 SQL。

```python
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
```

<OutputBox title='对照写法：先自己猜，再点开' output='naive rows 6\ngated rows 3\nwm 3' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import csv, io, sqlite3\nfrom collections import defaultdict\n\nRAW = chr(10).join([&#39;id,ts,level,amount&#39;, &#39;1,10,INFO,5&#39;, &#39;2,11,BAD,x&#39;,\n                    &#39;3,11,INFO,7&#39;, &#39;4,12,INFO,9&#39;]) + chr(10)\n\ndef parse(stream):\n    for row in csv.DictReader(stream):\n        try:\n            yield dict(id=int(row[&#39;id&#39;]), ts=int(row[&#39;ts&#39;]),\n                       level=row[&#39;level&#39;], amount=int(row[&#39;amount&#39;]))\n        except ValueError:\n            yield None\n\ndef clean(rows, dead):\n    for r in rows:\n        if r is None:\n            dead.append(r)\n        else:\n            yield r\n\ndef tumble(rows, width):\n    for r in rows:\n        yield r[&#39;ts&#39;] // width * width, r\n\ncon = sqlite3.connect(&#39;:memory:&#39;)\ncon.execute(&#39;CREATE TABLE agg (bucket INTEGER PRIMARY KEY, total INTEGER)&#39;)\ncon.execute(&#39;CREATE TABLE meta (k TEXT PRIMARY KEY, v INTEGER)&#39;)\n\ndef run_once(raw, con):\n    dead, agg, wm = [], defaultdict(int), 0\n    for bucket, r in tumble(clean(parse(io.StringIO(raw)), dead), width=2):\n        agg[bucket] += r[&#39;amount&#39;]\n        wm = max(wm, r[&#39;ts&#39;])\n    for bucket, total in agg.items():\n        con.execute(&#39;INSERT INTO agg(bucket,total) VALUES(?,?) &#39;\n                    &#39;ON CONFLICT(bucket) DO UPDATE SET total=excluded.total&#39;, (bucket, total))\n    con.execute(&#39;INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=max(v,excluded.v)&#39;, (&#39;watermark&#39;, wm))\n    con.commit()\n    return len(dead)\n\nprint(&#39;dead&#39;, run_once(RAW, con), run_once(RAW, con))\nprint(&#39;agg&#39;, con.execute(&#39;SELECT bucket,total FROM agg ORDER BY bucket&#39;).fetchall())\nprint(&#39;watermark&#39;, con.execute(&#39;SELECT v FROM meta WHERE k=?&#39;, (&#39;watermark&#39;,)).fetchone()[0])\nprint(&#39;rows&#39;, con.execute(&#39;SELECT count(*) FROM agg&#39;).fetchone()[0])", "note": "生成器管道与背压：内存不随输入增长"}, {"label": "对照 / 进阶", "code": "import sqlite3\n\ncon = sqlite3.connect(&#39;:memory:&#39;)\ncon.execute(&#39;CREATE TABLE events (id INTEGER, amount INTEGER)&#39;)\ncon.execute(&#39;CREATE TABLE meta (k TEXT PRIMARY KEY, v INTEGER)&#39;)\n\ndef naive_replay(con, rows):\n    for i, amt in rows:\n        con.execute(&#39;INSERT INTO events(id,amount) VALUES(?,?)&#39;, (i, amt))\n    con.commit()\n\ndef gated_replay(con, rows):\n    row = con.execute(&#39;SELECT v FROM meta WHERE k=?&#39;, (&#39;wm&#39;,)).fetchone()\n    wm = row[0] if row else 0\n    for i, amt in rows:\n        if i &gt; wm:\n            con.execute(&#39;INSERT INTO events(id,amount) VALUES(?,?)&#39;, (i, amt))\n    con.execute(&#39;INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=max(v,excluded.v)&#39;, (&#39;wm&#39;, max(i for i, _ in rows)))\n    con.commit()\n\nrows = [(1, 5), (2, 7), (3, 9)]\nnaive_replay(con, rows); naive_replay(con, rows)\nprint(&#39;naive rows&#39;, con.execute(&#39;SELECT count(*) FROM events&#39;).fetchone()[0])\ncon.execute(&#39;DELETE FROM events&#39;)\ngated_replay(con, rows); gated_replay(con, rows)\nprint(&#39;gated rows&#39;, con.execute(&#39;SELECT count(*) FROM events&#39;).fetchone()[0])\nprint(&#39;wm&#39;, con.execute(&#39;SELECT v FROM meta WHERE k=?&#39;, (&#39;wm&#39;,)).fetchone()[0])", "note": "脏数据隔离、窗口聚合与幂等写入"}]' title='两种写法切换看' />

**幂等写入语法对照**

| 数据库 | 语法 | 起始版本 / 注意 |
| --- | --- | --- |
| SQLite | INSERT ... ON CONFLICT(k) DO UPDATE SET c=excluded.c | 3.24（2018）起，excluded 是冲突行伪表 |
| MySQL | INSERT ... ON DUPLICATE KEY UPDATE c=VALUES(c) | 需目标列上有唯一键 |
| PostgreSQL | INSERT ... ON CONFLICT(k) DO UPDATE SET c=EXCLUDED.c | 需唯一约束或索引 |
| 盲目 INSERT | 无冲突处理 | 重跑重复入库或撞主键报错 |


## 增量水位、质量校验与可回溯

水位（high water mark）记在独立的 meta 表，按分区（日期、来源、租户）分别记录而不是全局单值，否则某个落后分区会拖住其它分区的推进。

写入水位用 `ON CONFLICT(k) DO UPDATE` 配合 `max(v, excluded.v)`，保证只前进不回退；

再配上「只处理 offset 大于水位的记录」，at-least-once 投递加幂等写入就近似等价于 effectively-once。质量校验至少覆盖：总行数、死信数与占比、空值率、金额范围、主键唯一性、聚合总量与源数据对账；

把 good / dead / total / 水位写成质量报告随批次落盘，出问题时能定位到具体分区。CSV 与 SQL 双数据源适配靠同一批 dict 记录：既能用 `csv.DictWriter` 落文件，也能用 `con.execute` 入库。schema 演进（新增列）要保证旧批次仍可读。

三个失效信号：重跑后行数翻倍、水位回退、死信数突增却没有告警。

**ETL 失败模式与防线**

| 现象 | 根因 | 防线 |
| --- | --- | --- |
| 大文件 OOM | read() 加 splitlines 全量载入 | 生成器逐行处理，io.StringIO 造流式输入 |
| 重跑后金额翻倍 | 盲目 INSERT 无幂等 | 主键 + ON CONFLICT DO UPDATE |
| 一行脏数据整批崩 | 解析异常未就地隔离 | try/except 送死信并出质量报告 |
| 落后分区拖住全部 | 全局单水位 | 按分区分别记录水位 |
| 水位回退覆盖新数据 | 用赋值而非 max 更新 | SET v=max(v, excluded.v) 保证单调 |

<CheckList id='P127b' title='上线前自检' :items='["能复现并解释「用 read() 全量载入日志，文件稍大就 OOM」", "能复现并解释「失败后从头重跑，聚合值翻倍」", "能复现并解释「一行脏数据让整批中断、已处理结果全丢」", "能用一条命令验证 生成器管道与背压", "关键路径有自动化测试与失败分支"]' />


## gi_frame 与生成器挂起：O(1) 内存的底层

生成器把函数帧保存在堆上（`gi_frame` 持有局部变量与指令指针），每次 `next` 恢复执行到下一个 `yield` 再挂起，因此同时驻留的只有当前一条记录，这就是 `O(1)` 内存与天然背压的来源；下游不 `next`，上游就不计算。

`csv.DictReader` 本身是迭代器，配合 `io.StringIO` 把字符串包装成文件对象，整条管道无需物化中间列表。SQLite 的事务由 journal 或 WAL 保证原子性，一次 `commit` 把整批改动落盘，比逐行提交少很多 `fsync`；

`ON CONFLICT` 子句用 `excluded` 伪表引用「本想插入但因冲突失败的那一行」，因此 `SET total=excluded.total` 是覆盖而非累加，重跑同一批必然得到相同值。

水位只增不减（`max`）保证消费进度单调，配合「只处理大于水位的记录」，at-least-once 投递加幂等写入即可逼近 effectively-once。

tumbling window 的键 `ts // width * width` 依赖整数整除，边界处（width 的整数倍）会开启新桶。

```python
import io, sys

raw = chr(10).join('r%d' % i for i in range(1000))
eager = [l for l in raw.splitlines()]
lazy = (l for l in io.StringIO(raw))
print('eager type', type(eager).__name__, len(eager))
print('lazy type', type(lazy).__name__)
print('list heavier', sys.getsizeof(eager) > sys.getsizeof(lazy))
print('first', next(lazy))
```

<OutputBox title='原理验证' output='eager type list 1000\nlazy type generator\nlist heavier True\nfirst r0' />

<Term word='生成器管道与背压' text='生成器是惰性求值：每次 `next` 只推进到下一个 `yield`，函数的局部变量保存在堆上的生成器帧里，因此同时驻留内存的只有当前一条记录，复杂度是 `O(1)` 而非 `O(N)`。`csv.DictReader` 本身就是迭代器，`io.StringIO` 让字符串像文件一样被逐行读，两者组合就能把「解析…' />

<Term word='解析与脏数据隔离' text='`DictReader` 把每行转成 dict，但值全是字符串，`int(row[&#39;amount&#39;])` 遇到非数字或缺失列会抛 `ValueError` 或 `KeyError`；正确做法是在解析生成器里 `try/except` 捕获，把原始行送进死信列表（dead letter）而不是中断整批，批次结束出质量报告…' />


## ETL 失败模式与防线

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 read() 全量载入日志，文件稍大就 OOM | 一次性构造 N 个字符串对象，内存与输入线性增长 | 用生成器逐行处理，csv.DictReader 与 io.StringIO 组合，别在循环里 list() 把惰性变回全量 |
| 失败后从头重跑，聚合值翻倍 | 盲目 INSERT 没有冲突处理，同一批数据二次入库 | 以桶或事件 id 为主键，用 INSERT ... ON CONFLICT(k) DO UPDATE SET c=excluded.c |
| 一行脏数据让整批中断、已处理结果全丢 | 解析异常向上抛出，生成器管道整体终止 | 在 parse 生成器里 try/except 捕获 ValueError，把原始行送死信列表，批次结束出质量报告 |

<Callout type="warn" title='本讲最容易踩的坑' text='用 read() 全量载入日志，文件稍大就 OOM：一次性构造 N 个字符串对象，内存与输入线性增长' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 read() 全量载入日志，文件稍大就…", "body": "一次性构造 N 个字符串对象，内存与输入线性增长", "tip": "用生成器逐行处理，csv.DictReader 与 io.StringIO 组合，别在循环里 list() 把惰性变回全量"}, {"title": "第 2 步：失败后从头重跑，聚合值翻倍", "body": "盲目 INSERT 没有冲突处理，同一批数据二次入库", "tip": "以桶或事件 id 为主键，用 INSERT ... ON CONFLICT(k) DO UPDATE SET c=excluded.c"}, {"title": "第 3 步：一行脏数据让整批中断、已处理结果全丢", "body": "解析异常向上抛出，生成器管道整体终止", "tip": "在 parse 生成器里 try/except 捕获 ValueError，把原始行送死信列表，批次结束出质量报告"}]' />


## 可重跑的日志聚合管道与质量报告

一条线上 ETL 要求「任何一段失败后重放，结果一致」。下面把四层收进一个可运行脚本：`read_rows` 用 `csv.DictReader` 逐行读并把转换失败的行放进死信；聚合按 `ts` 累加；写入用 `ON CONFLICT` 做覆盖式 upsert；水位写进 meta 表并用 `max` 保证单调；

`report` 汇总行数、死信数、水位与聚合总量，作为批次质量报告落盘。`run1` 与 `run2` 传入同一份源数据，输出必须逐字段一致——这正是可重跑的验收标准。真实项目把 `:memory:` 换成文件库并开 WAL、按日期分区记录水位、把质量报告写进监控系统、给死信配独立重放入口。

片段可直接运行，重点看两次运行的报告完全相同。

```python
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
```

<Callout type="idea" title='落地提示' text='逐行流式处理、按分区记录水位、写入用 upsert、脏数据进死信并出质量报告' />

```bash
python -m compileall -q . && python -m pytest -q
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 生成器管道与背压 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 练习、自测与一页纸速记

<Exercise title='基础：把脏数据分流到死信而不中断管道' task='写一个生成器，逐行把 amount 转整数，失败时 yield None；再写 clean 把 None 收集进死信列表，打印正常条数与死信数。' solution='import csv, io\nsrc = chr(10).join([&#39;id,amount&#39;, &#39;1,5&#39;, &#39;2,BAD&#39;, &#39;3,7&#39;]) + chr(10)\ndef parse(s):\n    for r in csv.DictReader(s):\n        try:\n            yield int(r[&#39;amount&#39;])\n        except ValueError:\n            yield None\ndead, good = [], []\nfor v in parse(io.StringIO(src)):\n    (dead if v is None else good).append(v)\nprint(&#39;good&#39;, good, &#39;dead&#39;, len(dead))' explain='输出 good [5, 7] dead 1。异常在解析生成器内就地捕获，脏行不会让整条管道终止，这是批次健壮性的最低要求。' />

<Exercise title='进阶：用 ON CONFLICT 验证重跑幂等' task='建一张以 k 为主键的表，对同一批数据跑两次 INSERT ... ON CONFLICT DO UPDATE，打印行数与值，解释为什么不是简单 INSERT。' solution='import sqlite3\nc = sqlite3.connect(&#39;:memory:&#39;)\nc.execute(&#39;CREATE TABLE t (k INTEGER PRIMARY KEY, v INTEGER)&#39;)\nrows = [(1, 5), (2, 7)]\nfor _ in range(2):\n    for k, v in rows:\n        c.execute(&#39;INSERT INTO t(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v&#39;, (k, v))\n    c.commit()\nprint(&#39;rows&#39;, c.execute(&#39;SELECT count(*) FROM t&#39;).fetchone()[0])\nprint(&#39;v1&#39;, c.execute(&#39;SELECT v FROM t WHERE k=?&#39;, (1,)).fetchone()[0])' explain='输出 rows 2、v1 5。excluded 引用冲突行，SET 是覆盖而非累加；盲目 INSERT 要么撞主键报错、要么在无主键表里重复入库。' />

<Quiz no='127-1' q='关于 ETL 的生成器管道，哪一项准确？' :options='["生成器每次只驻留当前一条，下游不拉动上游就不生产，形成天然背压", "生成器会把全部结果缓存进列表以便复用", "生成器可以重复消费多次", "使用 list() 包住生成器能降低内存"]' answer="0" explain='生成器的帧保存在堆上，每次 next 只推进到下一个 yield；list() 会重新物化全量，生成器也只能消费一次，重跑必须重建管道。' />

<Quiz no='127-2' q='SQLite 里保证重跑幂等的正确写法是？' :options='["INSERT ... ON CONFLICT(k) DO UPDATE SET c = excluded.c", "先 DELETE 全表再 INSERT", "用 INSERT OR IGNORE 且不做聚合", "把值累加到旧值上"]' answer="0" explain='excluded 是冲突行的伪表，SET c=excluded.c 是覆盖式更新，同一批重放结果一致；累加会让金额翻倍，DELETE 全表会丢失其它批次数据。' />

<Quiz no='127-3' q='水位（high water mark）应如何更新才安全？' :options='["按分区记录，并用 max(v, excluded.v) 保证只前进不回退", "用全局单值并每次直接赋值", "重跑时清零重新开始", "按行数而不是事件时间记录"]' answer="0" explain='按分区分别记录避免落后分区拖住全局；max 保证进度单调，重放旧批次不会把水位退回进而重复处理或覆盖新数据。' />

<KnowledgeCard :points='["生成器惰性求值：帧存堆上、每次 next 一条、内存 O(1)，下游不拉取上游就不生产（背压）", "read() 加 splitlines 让内存随输入线性增长，是大文件 OOM 的直接原因；生成器只能消费一次", "脏数据在解析生成器内 try/except 就地隔离进死信，不让整批崩；批次出质量报告", "幂等写入用主键 + INSERT ... ON CONFLICT(k) DO UPDATE SET c=excluded.c（SQLite 3.24 起）", "水位按分区记录，用 max(v, excluded.v) 保证单调；at-least-once 加幂等近似 effectively-once", "整批一次 commit 省 fsync；参数用 ? 绑定；质量校验看行数、死信占比、聚合总量对账"]' :pitfalls='["用 read() 全量载入日志，文件稍大就 OOM", "失败后从头重跑，聚合值翻倍", "一行脏数据让整批中断、已处理结果全丢", "用一次性脚本 read() 全量载入日志，文件稍大就 OOM；失败后从头跑又会重复入库"]' summary='ETL 的可靠性来自「可重跑」：任何一段失败后重放，结果必须一致，因此水位、幂等与脏数据隔离要在一开始设计' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 生成器惰性求值：帧存堆上、每次 next 一条、内存 O(1)，下游不拉取上游就不生产（背压） | 建立直觉 |
| read() 加 splitlines 让内存随输入线性增长，是大文件 OOM 的直接原因；生成器只能消费一次 | 跑通示例 |
| 脏数据在解析生成器内 try/except 就地隔离进死信，不让整批崩；批次出质量报告 | 深入边界 |
| 幂等写入用主键 + INSERT ... ON CONFLICT(k) DO UPDATE SET c=excluded.c（SQLite 3.24 起） | 工程落地 |
| 水位按分区记录，用 max(v, excluded.v) 保证单调；at-least-once 加幂等近似 effectively-once | 随堂检测 |
| 整批一次 commit 省 fsync；参数用 ? 绑定；质量校验看行数、死信占比、聚合总量对账 | 复盘 |

1. 生成器惰性求值：帧存堆上、每次 next 一条、内存 O(1)，下游不拉取上游就不生产（背压）

2. read() 加 splitlines 让内存随输入线性增长，是大文件 OOM 的直接原因；生成器只能消费一次

3. 脏数据在解析生成器内 try/except 就地隔离进死信，不让整批崩；批次出质量报告

[下一讲：实战 07 · 并发爬虫与分布式调度](/projects/concurrent-crawler)

<Predict no='127-4' q='同一批数据用 ON CONFLICT DO UPDATE 连续重跑两次，agg 表的行数最可能是？' :options='["与单次运行相同（本例 2 行）", "翻倍（4 行）", "抛 sqlite3.IntegrityError"]' answer='0' output='rows 2' explain='聚合以 bucket 为主键，第二次运行的 INSERT 触发冲突分支改为覆盖更新，不会新增行；这正是可重跑的验收点，盲目 INSERT 才会翻倍或报错。' />

<FillBlank no='127-5' tpl='___ csv, io, sqlite3' :answers='["import"]' hint='回想本讲关于 生成器管道与背压 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 生成器管道与背压：内存不随输入增长 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/127-data-etl.py`

```bash
python3 examples/lessons/127-data-etl.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/127-data-etl.py) · [全部示例代码索引](/examples/)
