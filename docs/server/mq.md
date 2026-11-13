---
title: 第 089 讲 · 消息队列：Celery / RabbitMQ / Kafka
description: 用异步任务解耦并保证可靠投递
---

<StageHeader stage='L8 · 服务端与数据' level='★★★★☆' time='45 分钟' goal='用异步任务解耦并保证可靠投递' prereq='第 088 讲 · Redis 缓存：穿透、击穿、雪崩与分布式锁' />

# 第 089 讲 · 消息队列：Celery / RabbitMQ / Kafka

缓存把重复的读挡在了数据库前面，可有些活不该挤在一次请求里：发券、发短信、写审计，下游稍微一抖就把下单接口拖到超时。把它们挪到后台异步执行，吞吐确实上来了，代价是同一条消息可能被交到消费者手里两次。这一讲用消息队列把耗时活从主链路解耦，重点讲清什么叫可靠投递。

改成后台任务之后，用户收到两张券、短信发了三遍：生产者等不到确认就重发，消费者处理完还没确认就崩溃、消息又被投递一次。翻遍配置项也找不到『恰好一次』的开关，主流队列默认承诺的是至少一次。我们先分清队列与发布订阅，再谈确认、重试与死信队列，接着把任务幂等和去重表落成能数得清的结果，最后说顺序与分区。需要函数、异常处理、Redis 与 sqlite3；学完能把慢活拆成可重入任务，也说得清『恰好一次』为什么只能由消费端实现。


## 一条毒消息无限重试，把整条队列堵死

订单系统把发券、发短信、写审计全塞进同步请求里，一次下游抖动就让下单接口整体超时。换成 Celery 异步任务后吞吐上来了，却冒出更麻烦的事：用户收到两条券、短信发了三遍。查下来是网络抖动导致生产者重发、消费者处理完还没确认就崩溃又被重新投递——同一条消息被交了两次。有人提议把中间件调成『恰好一次』，可翻遍配置也没这个开关；

另一次故障是一条格式错误的毒消息被无限重试，后面的消息全被堵住。这些现象指向同一条结论：主流中间件承诺的都是至少一次投递，『恰好一次』必须由消费端幂等来补。本讲用标准库的 queue 与 sqlite3 把去重、确认、重试、死信跑成能数得清的结果。

<Callout type="warn" title='先看一个真实会出错的写法' text='把『恰好一次』当配置项去中间件里找开关：主流中间件默认只承诺至少一次，确认丢失就会重投，配置无法消除重复' />


## 队列、发布订阅与三种投递语义

队列（point-to-point）里一条消息只被一个消费者取走处理，RabbitMQ 的 queue 加 consumer、Celery 的 task queue 都属于这一类，适合把工作分发给多个 worker 做负载均衡。发布订阅（pub/sub）反过来，一条消息广播给所有订阅者；

Kafka 的 topic 加 consumer group 把两者掺在一起：组内消费者分摊分区，组与组之间各自收到全量。投递语义有三种：at-most-once 最多一次、可能丢，at-least-once 至少一次、可能重，exactly-once 恰好一次。

现实中几乎所有中间件的默认与承诺都是至少一次，原因很直接——要保证不丢，就必须在『没收到确认』时重投：生产者发出后等不到确认会重发，消费者处理完还没确认就崩溃会被重新交付。因此『恰好一次』不是一个配置项，只能由消费端幂等来补：消息带上业务幂等键，消费端用去重表或唯一约束记下已处理的 key，重复到达直接确认跳过。

写 Celery 任务时要短小、可重入，参数能用 `JSON` 序列化（别塞大对象或数据库连接对象），`acks_late=True` 让失败的消息重投，也把幂等要求抬得更高。

**三种投递语义与实现责任**

| 语义 | 可能情况 | 谁来保证 |
| --- | --- | --- |
| at-most-once | 可能丢，不会重 | 发后不等确认 |
| at-least-once | 可能重复，不会丢 | 主流中间件默认；幂等靠消费端 |
| exactly-once | 不丢不重 | 消费端幂等 + 事务，非配置项 |
| Kafka 事务 | 跨分区原子写 | 仍需消费端幂等兜底 |

<Callout type="tip" title='核心心智模型' text='队列（point-to-point）里一条消息只被一个消费者取走处理，RabbitMQ 的 queue 加 consumer、Celery 的 task queue 都属于这一类，适合把工作分发给多个 worker 做负载均衡。发布订阅（pub/sub）反过来，一条消息广播给所有订阅者；Kafka ' />

<ConceptDiagram type='compare2' title='第 089 讲 · 队列、发布订阅与三种投递语义' labels='队列、发布订阅与三种投递语义|确认、重试、死信与顺序|可靠投递的工程清单' caption='用异步任务解耦并保证可靠投递' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 主示例：至少一次投递下的重复消息

```python
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
```

<OutputBox title='主示例运行结果' output='m1 acked attempt 1\nm1 duplicate-skipped\nm2 dead-lettered\nledger rows 1\ndlq size 1' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE done (key TEXT PRIMARY KEY)&#39;)\ndb.execute(&#39;CREATE TABLE ledger (id INTEGER PRIMARY KEY, amount INT)&#39;)\ndlq = []\ndef handle(msg):\n    if msg[&#39;amount&#39;] == 13:\n        raise ValueError(&#39;downstream error&#39;)\n    db.execute(&#39;INSERT INTO ledger (amount) VALUES (?)&#39;, (msg[&#39;amount&#39;],))\ndef consume(msg, max_retries=3):\n    key = msg[&#39;key&#39;]\n    if db.execute(&#39;SELECT 1 FROM done WHERE key=?&#39;, (key,)).fetchone():\n        return &#39;duplicate-skipped&#39;\n    for attempt in range(max_retries):\n        try:\n            handle(msg)\n            db.execute(&#39;INSERT INTO done (key) VALUES (?)&#39;, (key,))\n            return &#39;acked attempt &#39; + str(attempt + 1)\n        except ValueError:\n            continue\n    dlq.append(msg)\n    return &#39;dead-lettered&#39;\nfor m in [\n    {&#39;key&#39;:&#39;m1&#39;,&#39;amount&#39;:10},\n    {&#39;key&#39;:&#39;m1&#39;,&#39;amount&#39;:10},\n    {&#39;key&#39;:&#39;m2&#39;,&#39;amount&#39;:13},\n]:\n    print(m[&#39;key&#39;], consume(m))\nprint(&#39;ledger rows&#39;, db.execute(&#39;SELECT COUNT(*) FROM ledger&#39;).fetchone()[0])\nprint(&#39;dlq size&#39;, len(dlq))' :notes='["导入 sqlite3，用内存库实现去重表与账本", "建立内存连接", "done 表以业务幂等键为主键，记录已处理消息", "ledger 表模拟真实业务写入（记账）", "dlq 列表收集超过重试次数的死信", "定义业务处理函数，只做一次副作用", "amount 为 13 时模拟下游持续失败", "抛出可重试异常", "正常路径向账本插入一行", "定义消费函数，含幂等、重试与死信三段", "取出业务幂等键", "先查去重表，命中说明这条消息处理过", "命中直接跳过，等价于 ack 且不重复执行副作用", "最多重试 max_retries 次", "尝试执行业务", "调用 handle 执行业务写入，把副作用与去重分离", "业务成功后再写去重标记，二者应在同一事务", "返回 ack 结果与尝试次数", "可重试异常则进入下一轮", "continue 推进重试", "超过次数把消息放入死信队列", "返回死信状态", "构造三条消息，第一条与第二条例子是重复投递", "m1 首次，正常处理", "m1 重复到达，应被幂等跳过", "m2 一直失败，应进死信", "遍历并消费", "打印每条消息的处理结果", "账本只有 1 行，证明重复投递未重复记账", "死信队列 1 条，毒消息被隔离而非无限重试"]' title='第 089 讲 · 消息队列：Celery / RabbitMQ / Kafka' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
def backoff(attempt, base=0.01):
    return round(base * (2 ** attempt), 4)
print('backoff', [backoff(a) for a in range(4)])
import collections
deliveries = ['m1','m1','m2','m1','m3']
print('delivery counts', dict(collections.Counter(deliveries)))
```

<OutputBox title='原理验证' output='backoff [0.01, 0.02, 0.04, 0.08]\ndelivery counts {&#39;m1&#39;: 3, &#39;m2&#39;: 1, &#39;m3&#39;: 1}' />


## 对照：把「恰好一次」当开关与消费端幂等

```python
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
```

<OutputBox title='对照写法：先自己猜，再点开' output='acked [0, 2]\ndlq [1]\ndeliveries of id1 3' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE done (key TEXT PRIMARY KEY)&#39;)\ndb.execute(&#39;CREATE TABLE ledger (id INTEGER PRIMARY KEY, amount INT)&#39;)\ndlq = []\ndef handle(msg):\n    if msg[&#39;amount&#39;] == 13:\n        raise ValueError(&#39;downstream error&#39;)\n    db.execute(&#39;INSERT INTO ledger (amount) VALUES (?)&#39;, (msg[&#39;amount&#39;],))\ndef consume(msg, max_retries=3):\n    key = msg[&#39;key&#39;]\n    if db.execute(&#39;SELECT 1 FROM done WHERE key=?&#39;, (key,)).fetchone():\n        return &#39;duplicate-skipped&#39;\n    for attempt in range(max_retries):\n        try:\n            handle(msg)\n            db.execute(&#39;INSERT INTO done (key) VALUES (?)&#39;, (key,))\n            return &#39;acked attempt &#39; + str(attempt + 1)\n        except ValueError:\n            continue\n    dlq.append(msg)\n    return &#39;dead-lettered&#39;\nfor m in [\n    {&#39;key&#39;:&#39;m1&#39;,&#39;amount&#39;:10},\n    {&#39;key&#39;:&#39;m1&#39;,&#39;amount&#39;:10},\n    {&#39;key&#39;:&#39;m2&#39;,&#39;amount&#39;:13},\n]:\n    print(m[&#39;key&#39;], consume(m))\nprint(&#39;ledger rows&#39;, db.execute(&#39;SELECT COUNT(*) FROM ledger&#39;).fetchone()[0])\nprint(&#39;dlq size&#39;, len(dlq))", "note": "队列、发布订阅与三种投递语义"}, {"label": "对照 / 进阶", "code": "import queue\n\nq = queue.Queue()\nfor i in range(3):\n    q.put({&#39;id&#39;: i, &#39;tries&#39;: 0})\nacked, dlq = [], []\nwhile not q.empty():\n    m = q.get()\n    m[&#39;tries&#39;] += 1\n    if m[&#39;id&#39;] == 1 and m[&#39;tries&#39;] &lt; 3:\n        q.put(m)\n    elif m[&#39;id&#39;] == 1:\n        dlq.append(m[&#39;id&#39;])\n    else:\n        acked.append(m[&#39;id&#39;])\n    q.task_done()\nprint(&#39;acked&#39;, acked)\nprint(&#39;dlq&#39;, dlq)\nprint(&#39;deliveries of id1&#39;, 3)", "note": "确认、重试、死信与顺序"}]' title='两种写法切换看' />


## 确认、重试、死信与顺序

RabbitMQ 这边，消费者处理完显式 `basic_ack`，没确认且连接断开的消息会 requeue 重新投递；

`basic_qos(prefetch_count)` 限制未确认消息数，免得慢消费者被灌满内存；

处理失败可以 `basic_nack(requeue=False)`，或配置 `x-dead-letter-exchange` 把消息转进死信队列（DLX）。

Kafka 这边，消费者提交 offset，提交时机决定语义：先处理再提交可能重复，先提交再处理可能丢；只有同一 key 路由到同一分区才有分区内有序，跨分区一律无序。

重试必须有上限和退避：指数退避取 0.01、0.02、0.04、0.08 秒再加随机抖动，超过 `max_retries` 就进死信，否则一条毒消息会无限循环、把后续消息全堵死。死信队列要可观测、可人工重放，重放前先把数据修好，不然重放还是失败。

Celery 侧对应的是 `@app.task(bind=True,max_retries=3)` 配 `self.retry(countdown=...)`；

result backend 只存结果，并不提供幂等保证。顺序和幂等冲突时优先幂等：为保序把所有消息塞进单分区会牺牲吞吐，而幂等能同时容忍乱序和重复。

**RabbitMQ 与 Kafka 关键机制**

| 机制 | RabbitMQ | Kafka |
| --- | --- | --- |
| 确认 | basic_ack / basic_nack | 提交 offset |
| 流控 | basic_qos(prefetch_count) | 分区数 + consumer group |
| 失败隔离 | DLX 死信交换 | 独立死信 topic / 跳过 |
| 顺序 | 单队列有序 | 分区内有序，按 key 路由 |
| 回放 | 重新发布或死信重投 | 重置 offset 回放 |


## 可靠投递的工程清单

消息体固定带四样东西：`message_id`、业务幂等键、产生时间、schema 版本；

大对象放对象存储只传引用，免得队列被大 payload 拖垮（Kafka 有 `message.max.bytes`，RabbitMQ 对内存敏感）。

消费端流程固定成四步：校验、查去重表（命中即确认跳过）、在事务里执行业务并写去重标记、确认；业务写与去重标记必须落在同一事务，否则会出现『做了业务没记标记』，重投时仍会重复扣款。监控覆盖队列积压（queue depth 或 consumer lag）、消费耗时分布、重试率、死信增长、重复投递率；

积压告警通常比 CPU 更早暴露问题。灰度与回放：Kafka 靠重置 offset 回放历史，RabbitMQ 靠死信重投或重新发布，两者都以消费端幂等为前提。任务设计上把一次网络调用、一次数据库写当成一个可重入单元，别把多个外部副作用捆进一个拆不开的任务；跨服务用 `trace_id` 把链路串起来。

**可靠投递清单**

| 项 | 要求 | 违反后果 |
| --- | --- | --- |
| 消息体 | 带 message_id / 幂等键 / schema 版本 | 无法去重、升级即炸 |
| 大对象 | 放对象存储只传引用 | 撑爆队列内存与 message.max.bytes |
| 去重事务 | 业务写与去重标记同一事务 | 做了业务没记标记仍重复扣款 |
| 重试 | 上限 + 指数退避 + 死信 | 毒消息无限循环堵住后续 |
| 监控 | 积压/lag、重试率、死信增长 | 问题只能靠用户投诉发现 |

<CheckList id='P089b' title='上线前自检' :items='["能复现并解释「把『恰好一次』当配置项去中间件里找开关」", "能复现并解释「业务写成功了但去重标记没写，重投仍重复扣款」", "能复现并解释「消费失败就无限重试，一条毒消息堵住整条队列」", "能用一条命令验证 队列与发布订阅", "关键路径有自动化测试与失败分支"]' />


## 为什么中间件只承诺至少一次

至少一次投递是『不丢消息』与『无法确定对端是否收到』两条约束叠出来的必然结果：生产者把消息发出后，确认（ack 或 commit）可能在网络上丢失，发送方分不清『对端没收到』和『收到了但确认丢了』，唯一安全的动作就是重发；消费者侧同理，处理完成到提交确认之间一旦崩溃，消息就会被重新交付。

于是重复投递不可避免，系统层面的『恰好一次』只能由业务层把副作用设计成幂等来逼近：用唯一约束把『处理过这个 key』变成一个原子事实，重复到达时数据库直接拒绝第二次写入，副作用自然只发生一次。把业务写与去重标记放进同一事务是关键，`ACID` 的原子性保证不会出现二者只成功其一的中间态。

RabbitMQ 的 prefetch 用未确认计数做背压，Kafka 的 offset 是分区内的消费进度指针——先处理再提交可能重复、先提交再处理可能丢，这个次序正是投递语义在消费端的翻版。死信队列把反复失败的消息从主链路隔离，避免单条毒消息靠无限重试拖垮整体吞吐。

<Term word='队列与发布订阅' text='队列（point-to-point）里一条消息只被一个消费者取走处理，RabbitMQ 的 queue 加 consumer、Celery 的 task queue 都属于这一类，适合把工作分发给多个 worker 做负载均衡。发布订阅（pub/sub）反过来，一条消息广播给所有订阅者；Kafka 的 topic 加 ' />

<Term word='至少一次与恰好一次的真相' text='RabbitMQ 这边，消费者处理完显式 `basic_ack`，没确认且连接断开的消息会 requeue 重新投递；`basic_qos(prefetch_count)` 限制未确认消息数，免得慢消费者被灌满内存；处理失败可以 `basic_nack(requeue=False)`，或配置 `x-dead-lette' />

<FlowTimeline :steps='[{"title": "队列、发布订阅与三种投递语义", "desc": "队列（point-to-point）里一条消息只被一个消费者取走处理，RabbitM…", "tone": "blue"}, {"title": "确认、重试、死信与顺序", "desc": "RabbitMQ 这边，消费者处理完显式 `basic_ack`，没确认且连接断开的…", "tone": "purple"}, {"title": "可靠投递的工程清单", "desc": "消息体固定带四样东西：`message_id`、业务幂等键、产生时间、schema …", "tone": "orange"}, {"title": "工程落地", "desc": "带去重表、死信与退避的任务消费者", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 带去重表、死信与退避的任务消费者

下面把消费端做成一条完整的可靠链路：`consume` 先查 `done` 去重表，命中即跳过；未命中就带 `max_retries` 调用 `handle`，成功后把业务写与去重标记绑在同一个事务里提交，再返回确认；持续失败的消息超过次数后写进 `dead_letter` 表并给出指数退避等待，主循环因此不会被毒消息卡住。

`run` 用 `queue.Queue` 驱动，模拟至少一次投递下的重复消息。

真实项目里把 `Queue` 换成 Celery 或 RabbitMQ 消费者、把 `done` 换成带 TTL 的去重表、把退避换成 `self.retry(countdown=...)`，但四段结构不变：去重、事务、确认、死信。

```python
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
```

<Callout type="idea" title='落地提示' text='消息带业务幂等键、消费端做去重表、失败进死信、重试带退避与最大次数；Celery 任务保持短小且可重入' />

```bash
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE t(k TEXT UNIQUE)'); print('ok')"
```

把输入换成你自己的数据，观察结果是否仍符合 队列与发布订阅 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把『恰好一次』当配置项去中间件里找开关 | 主流中间件默认只承诺至少一次，确认丢失就会重投，配置无法消除重复 | 消费端做幂等：消息带业务幂等键，用带唯一约束的去重表，重复到达直接 ack 跳过 |
| 业务写成功了但去重标记没写，重投仍重复扣款 | 业务操作与去重记录不在同一事务，崩溃时只完成了一半 | 把业务写入与 INSERT 去重标记放进同一数据库事务，提交成功后再 ack |
| 消费失败就无限重试，一条毒消息堵住整条队列 | 没有重试上限与死信，失败消息反复 requeue 排在队首 | 设 max_retries 与指数退避，超限 basic_nack(requeue=False) 进 DLX 死信队列，并监控死信增长 |

<Callout type="warn" title='本讲最容易踩的坑' text='把『恰好一次』当配置项去中间件里找开关：主流中间件默认只承诺至少一次，确认丢失就会重投，配置无法消除重复' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把『恰好一次』当配置项去中间件里找开关", "body": "主流中间件默认只承诺至少一次，确认丢失就会重投，配置无法消除重复", "tip": "消费端做幂等：消息带业务幂等键，用带唯一约束的去重表，重复到达直接 ack 跳过"}, {"title": "第 2 步：业务写成功了但去重标记没写，重投仍重复扣款", "body": "业务操作与去重记录不在同一事务，崩溃时只完成了一半", "tip": "把业务写入与 INSERT 去重标记放进同一数据库事务，提交成功后再 ack"}, {"title": "第 3 步：消费失败就无限重试，一条毒消息堵住整条队列", "body": "没有重试上限与死信，失败消息反复 requeue 排在队首", "tip": "设 max_retries 与指数退避，超限 basic_nack(requeue=False) 进 DLX 死信队列，并监控死信增长"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：给消费者加幂等去重表' task='建一张 done(key PRIMARY KEY) 表，写 consume(msg) 先查表，命中即跳过，否则执行业务并把 key 写入 done，验证同一 key 投递两次只记一笔账。' solution='import sqlite3\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE done (key TEXT PRIMARY KEY)&#39;)\ndb.execute(&#39;CREATE TABLE ledger (amount INT)&#39;)\ndef consume(key, amount):\n    if db.execute(&#39;SELECT 1 FROM done WHERE key=?&#39;, (key,)).fetchone():\n        return &#39;skipped&#39;\n    db.execute(&#39;INSERT INTO ledger VALUES (?)&#39;, (amount,))\n    db.execute(&#39;INSERT INTO done VALUES (?)&#39;, (key,))\n    return &#39;acked&#39;\nprint(consume(&#39;k1&#39;, 10), consume(&#39;k1&#39;, 10))\nprint(db.execute(&#39;SELECT COUNT(*) FROM ledger&#39;).fetchone()[0])' explain='去重表用主键唯一约束把『处理过』变成原子事实；重复投递在查表阶段即被跳过，账本只会有一行。生产里业务写与去重写要同一事务。' />

<Exercise title='进阶：实现带退避与死信的重试' task='写 consume(msg, max_retries=3)，每次失败按 base*(2**attempt) 计算退避，超限写入死信表；构造一条始终失败的消息验证它进死信且不阻塞其它消息。' solution='import sqlite3\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE dlq (k TEXT)&#39;)\ndef consume(msg, max_retries=3):\n    for a in range(max_retries):\n        if msg.get(&#39;bad&#39;):\n            wait = round(0.01 * (2 ** a), 4)\n            continue\n        return &#39;acked&#39;\n    db.execute(&#39;INSERT INTO dlq VALUES (?)&#39;, (msg[&#39;k&#39;],))\n    return &#39;dead-lettered&#39;\nprint(consume({&#39;k&#39;:&#39;x&#39;,&#39;bad&#39;:True}))\nprint(consume({&#39;k&#39;:&#39;y&#39;}))\nprint(db.execute(&#39;SELECT * FROM dlq&#39;).fetchall())' explain='指数退避给下游恢复时间，max_retries 把毒消息隔离进死信，避免它无限 requeue 堵住后续消息；死信表还要支持人工重放。' />

<Quiz no='089-1' q='为什么主流消息队列都只承诺至少一次投递？' :options='["确认可能在网络上丢失，发送方无法区分『没收到』与『收到了但确认丢了』，重发是唯一安全选择", "因为磁盘太慢", "因为消费者一定是单线程", "因为消息不能带 id"]' answer="0" explain='要保证不丢就必须在没收到确认时重投，于是重复不可避免；『恰好一次』只能靠消费端幂等（去重表 + 唯一约束 + 同事务）逼近，不是配置项。' />

<Quiz no='089-2' q='关于业务写与去重标记，下面哪项准确？' :options='["二者必须放在同一数据库事务里，提交成功后再 ack", "先写去重标记再慢慢做业务", "分两个事务性能更好", "去重标记可省略，靠重试次数判断"]' answer="0" explain='若不在同一事务，崩溃时会留下『做了业务没记标记』，重投仍重复扣款；ACID 原子性保证二者要么都成功要么都不成功。' />

<Quiz no='089-3' q='一条消息反复处理失败，正确的处理是？' :options='["设重试上限与指数退避，超限进死信队列并监控", "无限重试直到成功", "直接丢弃且不记录", "阻塞主队列等待人工处理"]' answer="0" explain='无限重试会让毒消息堵住后续消息；上限 + 退避 + DLX 死信把失败隔离出主链路，死信需可观测与可人工重放。' />

<Predict no='089-4' q='在至少一次投递下，[&#39;m1&#39;,&#39;m1&#39;,&#39;m2&#39;,&#39;m1&#39;,&#39;m3&#39;] 用 Counter 统计，m1 的投递次数是多少？' :options='["3 次", "1 次", "5 次"]' answer='0' output='delivery counts {&#39;m1&#39;: 3, &#39;m2&#39;: 1, &#39;m3&#39;: 1}' explain='同一消息被交付 3 次正是至少一次语义的直接体现；消费端必须按业务幂等键去重，否则 3 次投递就会造成 3 次扣款。' />

<FillBlank no='089-5' tpl='___ sqlite3' :answers='["import"]' hint='回想本讲关于 队列与发布订阅 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 队列、发布订阅与三种投递语义 的落点。' />

<KnowledgeCard :points='["队列一条消息一个消费者，pub/sub 广播给所有订阅者；Kafka consumer group 组内分摊分区、组间各收全量", "at-most-once 可能丢、at-least-once 可能重、exactly-once 是目标；主流默认至少一次，因为确认丢失时只能重发", "重复来自两处：生产者等不到确认重发、消费者处理完未确认就崩溃被重新交付", "恰好一次靠消费端幂等：消息带业务幂等键，业务写与去重标记同事务，重复到达直接确认跳过", "RabbitMQ 用 basic_ack、basic_qos(prefetch_count)、basic_nack(requeue=False) 与 DLX；Kafka 的 offset 提交次序决定重复还是丢", "重试带上限、指数退避与抖动，毒消息进死信；acks_late=True 让失败重投，也更要求幂等"]' :pitfalls='["把『恰好一次』当配置项去中间件里找开关", "业务写成功了但去重标记没写，重投仍重复扣款", "消费失败就无限重试，一条毒消息堵住整条队列", "把任务体里塞大对象、或消费失败就无限重试，会拖垮队列并阻塞后续消息"]' summary='几乎所有中间件承诺的都是至少一次投递，所以「恰好一次」必须由消费端幂等来实现，而不是靠配置' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 队列一条消息一个消费者，pub/sub 广播给所有订阅者；Kafka consumer group 组内分摊分区、组间各收全量 | 建立直觉 |
| at-most-once 可能丢、at-least-once 可能重、exactly-once 是目标；主流默认至少一次，因为确认丢失时只能重发 | 跑通示例 |
| 重复来自两处：生产者等不到确认重发、消费者处理完未确认就崩溃被重新交付 | 深入边界 |
| 恰好一次靠消费端幂等：消息带业务幂等键，业务写与去重标记同事务，重复到达直接确认跳过 | 工程落地 |
| RabbitMQ 用 basic_ack、basic_qos(prefetch_count)、basic_nack(requeue=False) 与 DLX；Kafka 的 offset 提交次序决定重复还是丢 | 随堂检测 |
| 重试带上限、指数退避与抖动，毒消息进死信；acks_late=True 让失败重投，也更要求幂等 | 复盘 |

1. 队列一条消息一个消费者，pub/sub 广播给所有订阅者；Kafka consumer group 组内分摊分区、组间各收全量

2. at-most-once 可能丢、at-least-once 可能重、exactly-once 是目标；主流默认至少一次，因为确认丢失时只能重发

3. 重复来自两处：生产者等不到确认重发、消费者处理完未确认就崩溃被重新交付

[下一讲：认证授权：Session、JWT、OAuth2 与 RBAC](/server/auth)
