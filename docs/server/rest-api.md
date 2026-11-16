---
title: 第 085 讲 · REST API 设计、OpenAPI 与幂等
description: 设计出稳定、可演进的接口契约
---

<StageHeader stage='L8 · 服务端与数据' level='★★★☆☆' time='35 分钟' goal='设计出稳定、可演进的接口契约' prereq='第 084 讲 · 路由、依赖注入与请求校验' />

# 第 085 讲 · REST API 设计、OpenAPI 与幂等

入口薄了、参数也校验过了，接下来要回答更靠外的一问：接口以什么样子交给别人，才算长期不变的约定。本讲把重心从函数写法挪到契约怎么定，让接口在重试与改版时稳得住。

常见的一幕：支付回调抖了一下，客户端没等到响应又发一次，服务端没有幂等保护就多出一笔订单；也有人给失败都回 `200` 加 `ok=false`，监控便看不见错误率。我们理清资源与动词、状态码语义和分页与过滤，再谈幂等键与重试为何成对、版本演进，最后让 `OpenAPI` 成为文档与客户端唯一来源，并用去重表把 `REST` 幂等跑通。需要响应模型与状态码、`HTTP` 方法；学完能设计可演进、可重试的契约。


## 网络重试之后，用户被扣了两次款

支付回调网络抖了一下，客户端没收到响应，按重试策略又发了一次 `POST /charges`。服务端没有幂等保护，两笔请求各插一条订单，用户被扣了两次款；对账时发现同一笔业务流水号对应两行记录，却无法自动判定该退哪一笔。

补锅时有人建议「让客户端别重试」，这在移动网络下根本做不到——超时后调用方无法区分是请求没到、还是响应丢了，重试是唯一能收敛的手段。另一次故障是列表接口用 `POST` 承担所有操作，缓存、重试与审计全部失效；还有人给所有失败都返回 `200` 加一个 `ok=false`，监控因此长期看不到错误率。

这些问题的共同解是契约：资源与动词的语义、精确的状态码、写接口的幂等键、以及作为唯一事实来源的 `OpenAPI`。本讲用 `sqlite3` 把幂等落成可运行的去重表。

<Callout type="warn" title='先看一个真实会出错的写法' text='用『先 SELECT 查幂等键、没有再 INSERT』防重复，并发下仍产生两笔订单：检查与使用之间有时间窗（TOCTOU），两个请求同时查到空后各自插入' />


## 资源、动词与状态码语义

`REST` 把接口建模成资源 + 标准动词，而不是一堆 RPC 动作。

资源用复数名词：`/v1/orders`、`/v1/orders/{id}`。

`GET` 只读且安全，`POST` 创建且非幂等，`PUT` 整体替换且幂等（同一请求重复执行结果一致），`PATCH` 部分更新，`DELETE` 删除且幂等（重复删同一资源结果都是不存在）。幂等是协议层承诺，决定了网关与客户端能否安全重试：`PUT`、`DELETE`、`GET` 可重试，`POST` 必须靠幂等键兜底。

状态码要精确：`200` 通用成功、`201` 创建成功且应在 `Location` 头给出新资源 URL、`202` 已接受异步处理、`204` 成功无响应体、`304` 协商缓存未变、`400` 请求格式错、`401` 未认证、`403` 已认证但无权限、`404` 资源不存在、`409` 状态冲突、`422` 语义校验失败、`429` 限流、`500` / `503` 服务端故障。

列表接口要分页：`limit` + `offset` 简单但深翻页会偏移、且在高写入下漏重，cursor（游标）分页用上一页最后一条的排序键更稳；过滤、排序字段要写进契约。错误响应统一成一个结构（`code`、`message`、`request_id`），别让每个接口自造格式。

**HTTP 动词的幂等性与安全**

| 动词 | 语义 | 安全(不改状态) | 幂等(可重试) |
| --- | --- | --- | --- |
| GET | 读取资源 | 是 | 是 |
| POST | 创建资源 | 否 | 否，需幂等键 |
| PUT | 整体替换 | 否 | 是 |
| PATCH | 部分更新 | 否 | 通常否 |
| DELETE | 删除资源 | 否 | 是 |
| HEAD/OPTIONS | 取元信息 | 是 | 是 |

**精确状态码对照**

| 码 | 含义 | 典型场景 |
| --- | --- | --- |
| 200 | 通用成功 | GET/PUT 返回体 |
| 201 | 已创建 | POST 成功，Location 指向新资源 |
| 202 | 已接受异步处理 | 任务入队 |
| 204 | 成功无响应体 | DELETE 成功 |
| 400 / 422 | 格式错 / 语义校验失败 | 参数非法、字段约束不符 |
| 401 / 403 | 未认证 / 无权限 | 缺 token、越权 |
| 409 / 429 | 状态冲突 / 限流 | 重复创建、超配额 |
| 500 / 503 | 服务端故障 / 暂不可用 | 未捕获异常、过载 |

<Callout type="tip" title='核心心智模型' text='REST 把接口建模成资源 + 标准动词，而不是一堆 RPC 动作。资源用复数名词：`/v1/orders`、`/v1/orders/{id}`。`GET` 只读且安全，`POST` 创建且非幂等，`PUT` 整体替换且幂等（同一请求重复执行结果一致），`PATCH` 部分更新，`DELETE` 删…' />

<ConceptDiagram type='flow3' title='第 085 讲 · 资源、动词与状态码语义' labels='资源、动词与状态码语义|幂等键：唯一约束去重与原子性|OpenAPI 与版本策略：让契约可生成、可…' caption='设计出稳定、可演进的接口契约' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 对照：先查再插为什么挡不住并发重复

```python
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
```

<OutputBox title='主示例运行结果' output='(&#39;created&#39;, 1)\n(&#39;replayed&#39;, 1)\norder count 1' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, amount INTEGER)&#39;)\ndb.execute(&#39;CREATE TABLE idempotency (key TEXT PRIMARY KEY, order_id INTEGER)&#39;)\n\ndef place_order(key, amount):\n    row = db.execute(&#39;SELECT order_id FROM idempotency WHERE key=?&#39;, (key,)).fetchone()\n    if row is not None:\n        return (&#39;replayed&#39;, row[0])\n    cur = db.execute(&#39;INSERT INTO orders (amount) VALUES (?)&#39;, (amount,))\n    oid = cur.lastrowid\n    db.execute(&#39;INSERT INTO idempotency (key, order_id) VALUES (?, ?)&#39;, (key, oid))\n    return (&#39;created&#39;, oid)\n\nprint(place_order(&#39;k-100&#39;, 50))\nprint(place_order(&#39;k-100&#39;, 50))\nprint(&#39;order count&#39;, db.execute(&#39;SELECT COUNT(*) FROM orders&#39;).fetchone()[0])' :notes='["导入 sqlite3，用内存库演示去重表，无需外部服务", "空行，只用于分隔逻辑块，不影响执行结果。", "建立内存数据库连接", "业务表 orders，自增主键记录真实订单", "幂等表 idempotency，key 设为主键即带唯一约束", "空行，只用于分隔逻辑块，不影响执行结果。", "定义下单函数，接收幂等键与金额", "先按幂等键查询去重表", "命中说明是重放，直接返回首次记录的订单号", "重放分支不再插入业务表，避免重复扣款", "未命中才真正插入订单", "lastrowid 取回新订单的自增主键", "把幂等键与订单号写入去重表，供下次重放", "返回创建状态与订单号", "空行，只用于分隔逻辑块，不影响执行结果。", "首次请求，插入一条订单", "同一幂等键重放，走到重放分支", "统计订单总数，仍是 1 证明重复请求未产生第二笔"]' title='第 085 讲 · REST API 设计、OpenAPI 与幂等' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
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
```

<OutputBox title='对照写法：先自己猜，再点开' output='201 created\n200 replay 99\n201 created' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, amount INTEGER)&#39;)\ndb.execute(&#39;CREATE TABLE idempotency (key TEXT PRIMARY KEY, order_id INTEGER)&#39;)\n\ndef place_order(key, amount):\n    row = db.execute(&#39;SELECT order_id FROM idempotency WHERE key=?&#39;, (key,)).fetchone()\n    if row is not None:\n        return (&#39;replayed&#39;, row[0])\n    cur = db.execute(&#39;INSERT INTO orders (amount) VALUES (?)&#39;, (amount,))\n    oid = cur.lastrowid\n    db.execute(&#39;INSERT INTO idempotency (key, order_id) VALUES (?, ?)&#39;, (key, oid))\n    return (&#39;created&#39;, oid)\n\nprint(place_order(&#39;k-100&#39;, 50))\nprint(place_order(&#39;k-100&#39;, 50))\nprint(&#39;order count&#39;, db.execute(&#39;SELECT COUNT(*) FROM orders&#39;).fetchone()[0])", "note": "资源、动词与状态码语义"}, {"label": "对照 / 进阶", "code": "import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE charges (key TEXT PRIMARY KEY, amount INT)&#39;)\n\ndef charge(key, amount):\n    cur = db.execute(&#39;INSERT OR IGNORE INTO charges (key, amount) VALUES (?, ?)&#39;, (key, amount))\n    if cur.rowcount == 1:\n        return &#39;201 created&#39;\n    return &#39;200 replay &#39; + str(db.execute(&#39;SELECT amount FROM charges WHERE key=?&#39;, (key,)).fetchone()[0])\n\nprint(charge(&#39;pay-1&#39;, 99))\nprint(charge(&#39;pay-1&#39;, 99))\nprint(charge(&#39;pay-2&#39;, 10))", "note": "幂等键：唯一约束去重与原子性"}]' title='两种写法切换看' />

```python
import inspect

def write_endpoint(body: dict, idempotency_key: str = ''):
    return (body, idempotency_key)
def read_endpoint(page: int = 1, size: int = 20):
    return (page, size)

IDEMPOTENT = frozenset(('GET', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'))
for method, fn in (('POST', write_endpoint), ('PUT', write_endpoint), ('GET', read_endpoint)):
    param_names = list(inspect.signature(fn).parameters)
    print(method, 'idempotent', method in IDEMPOTENT, 'params', param_names)
```

<OutputBox title='原理验证' output='POST idempotent False params [&#39;body&#39;, &#39;idempotency_key&#39;]\nPUT idempotent True params [&#39;body&#39;, &#39;idempotency_key&#39;]\nGET idempotent True params [&#39;page&#39;, &#39;size&#39;]' />


## 幂等键：唯一约束去重与原子性

所有写操作都应接受 `Idempotency-Key`（或业务流水号）请求头，服务端以它为去重依据。

最朴素的实现是「先 `SELECT` 查有没有、没有再 `INSERT`」，这在并发下会失效：两个请求同时查到空、都去插入，仍产生两条记录。

正确做法把判定交给数据库唯一约束：为幂等键建 `PRIMARY KEY` 或 `UNIQUE` 索引，用 `INSERT` 配 `ON CONFLICT DO NOTHING`（PostgreSQL / SQLite）或 `INSERT OR IGNORE`（SQLite）做原子占位，再依据 `rowcount` 判断本次是不是首次执行。

SQLite 里 `cur.rowcount` 为 `1` 表示插入成功、为 `0` 表示键已存在；PostgreSQL 用 `RETURNING` 或检查 `ON CONFLICT` 影响行数。流程应是单事务：在同一个事务里完成占位、写业务表、记录响应快照，任何一步失败整笔回滚，避免留下「有占位没结果」的悬挂状态。

重放时不能再执行业务逻辑，而是直接返回第一次存下的响应（含相同状态码与 body）。

键要有作用域与过期：按 `(tenant_id, key)` 联合唯一，保存 24 小时到 7 天，避免无限膨胀，也要防止攻击者用大量随机键撑爆去重表。

**幂等实现与分页选型**

| 决策点 | 朴素做法与问题 | 正确做法 |
| --- | --- | --- |
| 去重判定 | 先 SELECT 再 INSERT，并发下双写 | 唯一约束 + INSERT OR IGNORE，看 rowcount |
| 事务边界 | 占位与业务写分开，可能悬挂 | 单事务内完成占位、写表、存响应 |
| 重放结果 | 重新执行业务逻辑 | 直接返回首次存下的状态码与 body |
| 键的作用域 | 全局单键，跨租户串数据 | (tenant, key) 联合唯一，设 TTL |
| 深翻页 | limit+offset 偏移且漏重 | cursor 分页按排序键续读 |


## OpenAPI 与版本策略：契约如何生成、测试与演进

`OpenAPI 3.1`（对齐 `JSON Schema 2020-12`）把路径、参数、请求体、响应、错误结构、安全方案写成机器可读文档，FastAPI 在 `/openapi.json` 暴露它、`/docs` 渲染 Swagger UI。

它的价值不是好看，而是作为唯一事实来源：用 `openapi-generator` 生成各语言客户端与服务端桩，用 `schemathesis` 之类工具做契约测试与基于属性的模糊测试，用 CI 里的 diff 检查是否引入了破坏性变更（删字段、改类型、改必填性）。

版本策略要在 URL 与请求头之间选：路径前缀 `/v1`、`/v2` 最直观、便于灰度与缓存隔离；用 `Accept` 头带 `application/vnd.api+json;version=2` 这样的媒体类型、或自定义版本头，URL 更干净，但 CDN 与网关的缓存键必须把版本头纳入 `Vary`，否则会串版本。

演进原则是只做加法（新增可选字段、新增端点），破坏性变更才升主版本，并保留旧版本一段时间与弃用头（`Deprecation`、`Sunset`）。契约要有测试守住：把示例请求与响应固定成契约测试，任何字段变更先改文档与测试，再改实现。

<FlowTimeline :steps='[{"title": "资源、动词与状态码语义", "desc": "REST 把接口建模成资源 + 标准动词，而不是一堆 RPC 动作。资源用复数名词…", "tone": "blue"}, {"title": "幂等键：唯一约束去重与原子性", "desc": "所有写操作都应接受 `Idempotency-Key`（或业务流水号）请求头，服务端…", "tone": "purple"}, {"title": "OpenAPI 与版本策略：让契约可生成、可测试", "desc": "`OpenAPI 3.1`（对齐 `JSON Schema 2020-12`）把路径…", "tone": "orange"}, {"title": "工程落地", "desc": "带幂等键、分页与统一错误结构的订单资源", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

幂等的本质是把「执行了几次」与「状态改变了几次」解耦。网络超时后调用方无法区分三种情况：请求未达、处理中、响应丢失，因此重试是唯一能收敛的策略；服务端必须让同一逻辑请求无论到达一次还是多次，最终状态都等于到达一次。

数据库唯一约束提供了这个保证的原子支点：B 树索引在插入时对每个键做唯一性检查，两个并发事务试图插同键时，一个先行成功、另一个被约束拒绝或阻塞，数据库用锁与 `MVCC` 保证不会同时成功，这比应用层「先查后写」的 `TOCTOU`（检查与使用之间被插入）可靠得多。

`INSERT OR IGNORE` 把冲突转成 `rowcount=0`，调用方据此区分首次与重放。

事务把占位、业务写、响应快照绑成一个原子单元：`ACID` 的原子性确保不会出现有占位没结果的中间态，隔离性由隔离级别决定（MySQL 默认 `REPEATABLE READ`、PostgreSQL 默认 `READ COMMITTED`）。

`OpenAPI` 则把这套语义外化成机器可读契约，缓存键、重试策略、客户端生成都从它派生。

<Term word='资源与动词' text='REST 把接口建模成资源 + 标准动词，而不是一堆 RPC 动作。资源用复数名词：`/v1/orders`、`/v1/orders/{id}`。`GET` 只读且安全，`POST` 创建且非幂等，`PUT` 整体替换且幂等（同一请求重复执行结果一致），`PATCH` 部分更新，`DELETE` 删除且幂等（重复删同一…' />

<Term word='状态码语义' text='所有写操作都应接受 `Idempotency-Key`（或业务流水号）请求头，服务端以它为去重依据。最朴素的实现是「先 SELECT 查有没有、没有再 INSERT」，这在并发下会失效：两个请求同时查到空、都去插入，仍产生两条记录。正确做法把判定交给数据库唯一约束：为幂等键建 `PRIMARY KEY` 或…' />


## 带幂等键、分页与统一错误结构的订单资源

下面把订单接口做成一个自包含的资源层：写操作接收 `idempotency_key`，用唯一约束原子去重，首次返回 `201` 与 `Location`，重放返回 `200` 与同一 body；读操作支持 cursor 分页，按 `id` 续读而不是 `offset`；所有错误经一个函数转成统一结构，带上 `request_id` 便于追踪。

响应体用 `dict` 表达，状态码由调用方映射到 `HTTP`。重点看三处工程约束：去重与业务写在同一事务里、重放直接取历史响应、列表分页用排序键而非偏移量。真实项目把 `db` 换成连接池、把响应快照存进带 TTL 的表，就能直接对接网关的重试。

```python
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
```

<Callout type="idea" title='落地提示' text='所有写操作接受幂等键，错误响应统一结构，OpenAPI 作为生成客户端与契约测试的唯一来源' />

<CheckList id='P085a' title='上线前自检' :items='["能复现并解释「用『先 SELECT 查幂等键、没有再 INSERT』防重复…」", "能复现并解释「重放请求时重新跑了一遍业务逻辑，只是最后没写库」", "能复现并解释「写接口全部返回 200 加 ok=false，监控看不到错误…」", "能用一条命令验证 资源与动词", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from urllib.parse import urlencode; print(urlencode({'page':2}))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 资源与动词 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用『先 SELECT 查幂等键、没有再 INSERT』防重复，并发下仍产生两笔订单 | 检查与使用之间有时间窗（TOCTOU），两个请求同时查到空后各自插入 | 给幂等键建 UNIQUE/PRIMARY KEY，用 INSERT OR IGNORE 或 ON CONFLICT DO NOTHING 原子占位，再据 rowcount 判断是否首次 |
| 重放请求时重新跑了一遍业务逻辑，只是最后没写库 | 重放分支仍执行了扣款、发消息等副作用 | 命中去重表后立即返回第一次持久化的响应快照，跳过全部业务副作用 |
| 写接口全部返回 200 加 ok=false，监控看不到错误率 | 状态码不参与语义表达，告警与网关重试策略失去依据 | 按语义返回 201/400/401/409/422/429/500，错误响应用统一结构（code、message、request_id） |

<Callout type="warn" title='本讲最容易踩的坑' text='用『先 SELECT 查幂等键、没有再 INSERT』防重复，并发下仍产生两笔订单：检查与使用之间有时间窗（TOCTOU），两个请求同时查到空后各自插入' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用『先 SELECT 查幂等键、没有再 IN…", "body": "检查与使用之间有时间窗（TOCTOU），两个请求同时查到空后各自插入", "tip": "给幂等键建 UNIQUE/PRIMARY KEY，用 INSERT OR IGNORE 或 ON CONFLICT DO NOTHING 原子占位，再据 rowcount 判断是否首次"}, {"title": "第 2 步：重放请求时重新跑了一遍业务逻辑，只是最后没写…", "body": "重放分支仍执行了扣款、发消息等副作用", "tip": "命中去重表后立即返回第一次持久化的响应快照，跳过全部业务副作用"}, {"title": "第 3 步：写接口全部返回 200 加 ok=false…", "body": "状态码不参与语义表达，告警与网关重试策略失去依据", "tip": "按语义返回 201/400/401/409/422/429/500，错误响应用统一结构（code、message、request_id）"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：用唯一约束实现幂等' task='建一张带 PRIMARY KEY 的 charges 表，写 charge(key, amount) 用 INSERT OR IGNORE 原子占位，依据 rowcount 返回 201 created 或 200 replay，验证同一 key 调两次只插一行。' solution='import sqlite3\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE charges (key TEXT PRIMARY KEY, amount INT)&#39;)\ndef charge(key, amount):\n    cur = db.execute(&#39;INSERT OR IGNORE INTO charges VALUES (?, ?)&#39;, (key, amount))\n    return &#39;201 created&#39; if cur.rowcount == 1 else &#39;200 replay&#39;\nprint(charge(&#39;p1&#39;, 10))\nprint(charge(&#39;p1&#39;, 10))\nprint(db.execute(&#39;SELECT COUNT(*) FROM charges&#39;).fetchone()[0])' explain='INSERT OR IGNORE 遇主键冲突时静默跳过且 rowcount 为 0，据此区分首次与重放；唯一约束的原子性避免了先查后写的竞态。' />

<Exercise title='进阶：给分页接口换成 cursor 并加统一错误' task='实现 list_orders(after, limit) 用 WHERE id&gt;? ORDER BY id LIMIT ? 做游标分页，再加一个 error(code, message, rid) 统一错误结构，构造越界参数返回 422。' solution='import sqlite3\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE orders (id INT PRIMARY KEY, amount INT)&#39;)\ndb.executemany(&#39;INSERT INTO orders VALUES (?, ?)&#39;, [(1,10),(2,20),(3,30)])\ndef error(code, message, rid):\n    return {&#39;code&#39;: code, &#39;message&#39;: message, &#39;request_id&#39;: rid}\ndef list_orders(after, limit):\n    if limit &lt; 1 or limit &gt; 100:\n        return (422, error(&#39;bad_limit&#39;, &#39;limit out of range&#39;, &#39;r1&#39;))\n    rows = db.execute(&#39;SELECT id FROM orders WHERE id&gt;? ORDER BY id LIMIT ?&#39;, (after, limit)).fetchall()\n    return (200, {&#39;items&#39;: [r[0] for r in rows]})\nprint(list_orders(1, 2))\nprint(list_orders(0, 0))' explain='cursor 分页按排序键续读，避免 offset 在高写入下漏重与深翻页偏移；错误结构统一后才能被网关与监控一致处理。' />

<Quiz no='085-1' q='客户端超时后重试 POST /charges，服务端防止重复扣款最可靠的做法是？' :options='["写接口接受幂等键，用数据库唯一约束原子去重，重放返回首次响应", "要求客户端不要重试", "把 POST 改成 GET", "在响应里加一个 ok=false 字段"]' answer="0" explain='超时后调用方无法区分请求未达与响应丢失，重试不可避免；唯一约束 + INSERT OR IGNORE 原子占位，按 rowcount 判定首次/重放，重放直接返回历史响应。' />

<Quiz no='085-2' q='关于 PUT 与 POST 的幂等性，下面哪项准确？' :options='["PUT 幂等可重试，POST 非幂等需幂等键", "两者都幂等", "POST 幂等，PUT 非幂等", "幂等性由响应状态码决定"]' answer="0" explain='PUT 整体替换同一资源，重复执行结果一致故可重试；POST 每次创建会新增资源，必须靠 Idempotency-Key 才能让重试收敛。' />

<Quiz no='085-3' q='新资源创建成功，最合适的状态码与配套头是？' :options='["201 并在 Location 头给出新资源 URL", "200 且无额外头", "204 且带响应体", "302 跳转到列表"]' answer="0" explain='201 Created 表示已创建，Location 指向新资源；204 语义是成功但无响应体，不能带 body；200 是通用成功，未表达创建语义。' />

<Predict no='085-4' q='对 charges(key PRIMARY KEY) 执行两次 INSERT OR IGNORE 同一 key，第二次 cur.rowcount 是多少？' :options='["0，表示冲突被忽略", "1，表示又插了一行", "-1，表示 SQLite 报错"]' answer='0' output='第一次 rowcount=1（201 created），第二次 rowcount=0（200 replay）' explain='INSERT OR IGNORE 在唯一键冲突时不插入也不报错，受影响行数为 0；这个可直接观测的值正是区分首次请求与重放的依据。' />

<FillBlank no='085-5' tpl='___ sqlite3' :answers='["import"]' hint='回想本讲关于 资源与动词 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 资源、动词与状态码语义 的落点。' />

<KnowledgeCard :points='["资源用复数名词，POST 非幂等、PUT/DELETE/GET 幂等可重试；POST 必须配幂等键", "状态码要精确：201+Location、204 无体、422 语义校验、409 冲突、429 限流", "幂等判定交给数据库唯一约束：INSERT OR IGNORE / ON CONFLICT DO NOTHING，看 rowcount", "去重、业务写、响应快照放在同一事务；重放直接返回首次持久化结果", "幂等键按 (租户, key) 联合唯一并设 TTL；列表用 cursor 分页而非深 offset", "OpenAPI 3.1 是契约唯一来源，用来生成客户端、做契约测试与破坏性变更检查"]' :pitfalls='["用『先 SELECT 查幂等键、没有再 INSERT』防重复，并发下仍产生两笔订单", "重放请求时重新跑了一遍业务逻辑，只是最后没写库", "写接口全部返回 200 加 ok=false，监控看不到错误率", "用 POST 承担所有操作、或不给写接口加幂等键，网络重试就会重复扣款、重复下单"]' summary='接口的稳定性来自契约而不是代码：路径、字段、错误结构、幂等语义都要写进文档并由测试守住' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 资源用复数名词，POST 非幂等、PUT/DELETE/GET 幂等可重试；POST 必须配幂等键 | 建立直觉 |
| 状态码要精确：201+Location、204 无体、422 语义校验、409 冲突、429 限流 | 跑通示例 |
| 幂等判定交给数据库唯一约束：INSERT OR IGNORE / ON CONFLICT DO NOTHING，看 rowcount | 深入边界 |
| 去重、业务写、响应快照放在同一事务；重放直接返回首次持久化结果 | 工程落地 |
| 幂等键按 (租户, key) 联合唯一并设 TTL；列表用 cursor 分页而非深 offset | 随堂检测 |
| OpenAPI 3.1 是契约唯一来源，用来生成客户端、做契约测试与破坏性变更检查 | 复盘 |

1. 资源用复数名词，POST 非幂等、PUT/DELETE/GET 幂等可重试；POST 必须配幂等键

2. 状态码要精确：201+Location、204 无体、422 语义校验、409 冲突、429 限流

3. 幂等判定交给数据库唯一约束：INSERT OR IGNORE / ON CONFLICT DO NOTHING，看 rowcount

[下一讲：WebSocket / SSE / 长轮询与实时推送](/server/websocket)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/085-rest-api.py`

```bash
python3 examples/lessons/085-rest-api.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/085-rest-api.py) · [全部示例代码索引](/examples/)
