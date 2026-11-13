---
title: 第 107 讲 · 分布式事务：2PC / TCC / Saga / 消息最终一致
description: 按业务代价选择事务方案
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★★' time='45 分钟' goal='按业务代价选择事务方案' prereq='第 106 讲 · 幂等、分布式锁与限流' />

# 第 107 讲 · 分布式事务：2PC / TCC / Saga / 消息最终一致

上一讲把重试、幂等键和分布式锁理顺了，可那些办法都默认数据还在一个库里、一次提交就能收口。等扣库存、扣余额、建订单分到三个服务，这个默认就不成立了。本讲先把单机的本地事务边界划清楚，再谈多台机器怎么协调一次业务写入。

想象一次下单：库存扣了，消息没发出进程就停了，下游始终不知道有这单。我们从两阶段提交为何被长锁拖住讲起，再看 TCC 把锁换成预留字段、Saga 用逆序补偿收尾，最后落到 outbox 把提交与消息绑成一次原子写、用对账兜底。需要函数、异常处理和上一讲的幂等与唯一索引；读完后你能为一条跨服务链路选对方案，也说得出代价落在哪。


## 订单服务里提交与发消息之间的窗口

一个订单服务把扣库存、扣余额、创建订单拆成三个微服务，工程师先各自提交本地事务，再尽量发一条 MQ 消息通知下一步。上线后对账发现两类脏数据：库存扣成功但进程在发消息前崩溃，下游永远没收到；以及消息已投递、本地事务却回滚，下游按一条不存在的订单发了货。

团队想把发消息包进数据库事务来补救，立刻失败——消息队列不是同一个资源管理器，没有共享的事务协调者，commit 与 send 之间存在无法消除的窗口。再换 2PC/XA 强一致，prepare 阶段要长时间锁住三个库的行，协调者一挂所有参与者卡在 in-doubt，吞吐被拖垮。

本讲把跨服务一致性拆成可选择的方案族：2PC 的阻塞代价、TCC 的预留字段、Saga 的逆序补偿，以及 outbox 把本地提交与消息落地绑成一次原子写，最后用对账兜底。

<Callout type="warn" title='先看一个真实会出错的写法' text='先提交本地事务再发 MQ 消息：两次写之间没有事务保护，进程在提交后发送前崩溃就永久丢消息；反向先发消息则本地回滚后消息已不可撤回' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段十 · 分布式与云原生 |
| 前置 | 第 106 讲 · 幂等、分布式锁与限流 |
| 难度 / 建议时长 | ★★★★★ · 45 分钟 |
| 本讲新增 | 本地事务边界、2PC 的阻塞问题、TCC 三阶段 |
| 一句话目标 | 按业务代价选择事务方案 |
| 为下一讲铺垫 | 分布式 ID、一致性哈希与分片 |


## 本地事务的 ACID 边界与 2PC 为何阻塞

`ACID` 的原子性由单个资源管理器用 undo/redo 日志与锁保证，一旦事务跨越 MQ、Redis、多个数据库，就没有共享的提交点。XA 规范用两阶段提交补这个缺口：第一阶段协调者向所有参与者发 prepare，各参与者写 redo 并锁定行后返回 ready；第二阶段协调者再发 commit 或 rollback。

问题出在同步阻塞：从 prepare 到 commit 之间，参与者持有的行锁与连接不能释放，任一参与者或网络变慢，整条链路一起等；协调者若在写完全局提交日志后宕机，参与者停在 in-doubt 状态，只能靠事务日志由恢复进程裁决。

MySQL 的 XA 与 PostgreSQL 的 `PREPARE TRANSACTION` 提供这套接口，后者由 `max_prepared_transactions` 控制，默认常为 0，也就是关闭。

CAP 定理下 2PC 选的是 CP：网络分区时宁可阻塞也不放行，因此跨机房的长事务几乎不会用它；微服务的强一致通常只落在同一个库内部，用唯一索引与本地事务解决。

<ConceptDiagram type='layers3' title='第 107 讲 · 本地事务的 ACID 边界与 2PC 为何阻塞' labels='本地事务的 ACID 边界与 2PC 为何阻|TCC 预留与 Saga 逆序补偿：用业务逻|outbox、事务消息与至少一次投递下的幂等' caption='按业务代价选择事务方案' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## prepare 到 commit 之间，2PC 的阻塞点在哪

跨服务原子提交做不到，是因为两阶段提交要求所有参与者共享一个能持久化的全局决策日志，而这个日志本身又成了新的单点。CAP 在发生分区时只允许在一致性与可用性之间二选一：2PC 的 prepare 让参与者把同意提交持久化并锁住资源，等于分区期间放弃可用性。

Outbox 绕开全局协调，它把写业务状态和记一条待发事件放进同一个数据库的同一次事务，利用单资源本来就有的 `ACID` 原子性，把跨系统问题降维成单库问题；之后投递是异步可重试的，消息可能重复但绝不会丢。

这一步的代价是把一致性从即时变成最终，并要求消费端用唯一索引把重复投递收敛成一次生效，数据库唯一约束同样依赖单库原子性，正好与 outbox 的前提一致。因此整套最终一致的成立条件可以精确表述为：至少一次投递、幂等消费、可观测对账，三者缺一就会在线上留下需要人工修补的差额。

**2PC 故障点与失效信号**

| 阶段 | 状态 | 失效信号 |
| --- | --- | --- |
| prepare 后参与者等待 | 行锁与连接被占用 | 数据库锁等待超时、连接池耗尽 |
| 协调者写提交日志后宕机 | 参与者 in-doubt | 需查 XA RECOVER 或 pg_prepared_xacts |
| 分区导致部分参与者不可达 | 全局阻塞或单侧提交 | 监控长事务时长与 in-doubt 数量 |
| 消费端重复投递 | 消息重放 | 唯一索引冲突计数、去重表命中率 |


### 协调者宕机后参与者停在 in-doubt

```python
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
```

<OutputBox title='原理验证' output='balance 110\napplied [&#39;refund&#39;]' />


## TCC 预留与 Saga 逆序补偿：用业务逻辑换可用性

TCC 把一个操作拆成 Try / Confirm / Cancel 三段：Try 不做最终扣减而是预留资源，例如把余额从 `available` 挪到 `frozen` 字段，Confirm 真正提交，Cancel 释放预留。

它把 2PC 的锁从数据库行搬到业务字段，避免长事务，代价是每个接口要写三份逻辑，还得处理空回滚（Cancel 先于 Try 到达）、悬挂（Try 迟到）与幂等。Saga 则把长事务切成一串本地事务 T1 到 Tn，为每个 Ti 配一个补偿 Ci，正常顺序执行，失败时按 Cn-1 到 C1 逆序补偿。

补偿不是回滚，而是一次新的业务写，因此必须满足幂等（重复调用结果相同，靠幂等键或去重表）、可重试（失败进队列重试）；补偿本身也可能失败，所以要留对账与人工兜底入口。Saga 没有隔离性，即 `ACID` 里缺的那个 I，中间状态会被其它请求看到，需用语义锁或状态机约束。

编排式由一个协调器集中驱动，协同式靠事件各自订阅，后者链路更松散、观测与排障更难。

```python
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
```

<OutputBox title='主示例运行结果' output='step_failed order RuntimeError\nstate {&#39;stock&#39;: 5, &#39;balance&#39;: 100, &#39;order&#39;: 0}\ncompensated [&#39;balance&#39;, &#39;stock&#39;]\nduplicate_comp skip-duplicate' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Saga:\n    def __init__(self):\n        self.done = []\n        self.compensated = set()\n    def run(self, name, forward, backward):\n        try:\n            forward()\n        except RuntimeError as err:\n            print(&#39;step_failed&#39;, name, type(err).__name__)\n            return False\n        self.done.append((name, backward))\n        return True\n    def compensate(self, name):\n        if name in self.compensated:\n            return &#39;skip-duplicate&#39;\n        self.compensated.add(name)\n        return &#39;compensated&#39;\n    def rollback(self):\n        for name, backward in reversed(self.done):\n            backward()\n            self.compensated.add(name)\n\nstate = {&#39;stock&#39;: 5, &#39;balance&#39;: 100, &#39;order&#39;: 0}\ndef dec_stock(): state[&#39;stock&#39;] -= 1\ndef inc_stock(): state[&#39;stock&#39;] += 1\ndef dec_balance(): state[&#39;balance&#39;] -= 10\ndef inc_balance(): state[&#39;balance&#39;] += 10\ndef make_order(): raise RuntimeError(&#39;payment timeout&#39;)\ndef drop_order(): state[&#39;order&#39;] = 0\n\ns = Saga()\nfor name, fwd, back in [\n    (&#39;stock&#39;, dec_stock, inc_stock),\n    (&#39;balance&#39;, dec_balance, inc_balance),\n    (&#39;order&#39;, make_order, drop_order),\n]:\n    if not s.run(name, fwd, back):\n        s.rollback()\n        break\nprint(&#39;state&#39;, state)\nprint(&#39;compensated&#39;, sorted(s.compensated))\nprint(&#39;duplicate_comp&#39;, s.compensate(&#39;stock&#39;))' :notes='["定义 Saga 编排器，负责正向步骤与逆序补偿", "构造器初始化已完成步骤与补偿登记", "done 保存步骤名与补偿函数，供回滚逆序遍历", "compensated 集合实现补偿幂等去重", "run 执行单个本地事务步骤并登记其补偿", "try 包裹正向操作，隔离业务失败", "执行正向动作，例如扣库存", "只捕获预期的业务异常类型", "打印失败步骤名与异常类型，便于对账", "返回 False 通知调用方触发回滚", "成功后把步骤与补偿登记进 done", "返回 True 表示本步骤已提交", "compensate 供外部显式触发单步补偿", "已补偿过则直接跳过，保证幂等", "重复调用返回 skip-duplicate 而不重复执行", "登记步骤名为已补偿", "首次补偿返回 compensated", "rollback 在整体失败时逆序调用补偿", "reversed(done) 是 Saga 核心：后提交的先补偿", "执行该步骤的补偿函数恢复状态", "同时登记进 compensated，防止与显式补偿冲突", "共享状态模拟三个服务的资源", "扣减库存的正向操作", "补偿：把库存加回去", "扣减账户余额", "补偿：退还余额", "模拟下单失败，抛出业务异常", "下单补偿为空操作，仅占位", "创建 Saga 实例", "按业务顺序声明三个步骤及各自补偿", "第一步：库存预留", "第二步：余额扣减", "第三步：创建订单，会失败", "结束步骤列表", "任一步失败即触发回滚", "逆序执行已完成步骤的补偿", "跳出循环，不再继续后续步骤", "打印最终状态，验证库存与余额已恢复", "打印实际被补偿的步骤名，不含失败的 order", "再次补偿已完成步骤，验证幂等返回 skip-duplicate"]' title='第 107 讲 · 分布式事务：2PC / TCC / Saga / 消息最终一致' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：把补偿当 undo 与幂等补偿的输出差

```python
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
```

<OutputBox title='对照写法：先自己猜，再点开' output='db {&#39;order:1&#39;: &#39;paid&#39;}\nqueued 1\nsent [&#39;order.paid:1&#39;]' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "class Saga:\n    def __init__(self):\n        self.done = []\n        self.compensated = set()\n    def run(self, name, forward, backward):\n        try:\n            forward()\n        except RuntimeError as err:\n            print(&#39;step_failed&#39;, name, type(err).__name__)\n            return False\n        self.done.append((name, backward))\n        return True\n    def compensate(self, name):\n        if name in self.compensated:\n            return &#39;skip-duplicate&#39;\n        self.compensated.add(name)\n        return &#39;compensated&#39;\n    def rollback(self):\n        for name, backward in reversed(self.done):\n            backward()\n            self.compensated.add(name)\n\nstate = {&#39;stock&#39;: 5, &#39;balance&#39;: 100, &#39;order&#39;: 0}\ndef dec_stock(): state[&#39;stock&#39;] -= 1\ndef inc_stock(): state[&#39;stock&#39;] += 1\ndef dec_balance(): state[&#39;balance&#39;] -= 10\ndef inc_balance(): state[&#39;balance&#39;] += 10\ndef make_order(): raise RuntimeError(&#39;payment timeout&#39;)\ndef drop_order(): state[&#39;order&#39;] = 0\n\ns = Saga()\nfor name, fwd, back in [\n    (&#39;stock&#39;, dec_stock, inc_stock),\n    (&#39;balance&#39;, dec_balance, inc_balance),\n    (&#39;order&#39;, make_order, drop_order),\n]:\n    if not s.run(name, fwd, back):\n        s.rollback()\n        break\nprint(&#39;state&#39;, state)\nprint(&#39;compensated&#39;, sorted(s.compensated))\nprint(&#39;duplicate_comp&#39;, s.compensate(&#39;stock&#39;))", "note": "本地事务的 ACID 边界与 2PC 为何阻塞"}, {"label": "对照 / 进阶", "code": "class Outbox:\n    def __init__(self):\n        self.db = {}\n        self.queue = []\n    def transact(self, key, value, event):\n        self.db[key] = value\n        self.queue.append(event)\n    def dispatch(self):\n        sent = []\n        while self.queue:\n            sent.append(self.queue.pop(0))\n        return sent\n\no = Outbox()\no.transact(&#39;order:1&#39;, &#39;paid&#39;, &#39;order.paid:1&#39;)\nprint(&#39;db&#39;, o.db)\nprint(&#39;queued&#39;, len(o.queue))\nprint(&#39;sent&#39;, o.dispatch())", "note": "TCC 预留与 Saga 逆序补偿：用业务逻辑换可用性"}]' title='两种写法切换看' />


## outbox、事务消息与至少一次投递下的幂等

消息最终一致的关键不是 MQ 可靠，而是让本地提交与消息存在成为一次原子写。Transactional Outbox 的做法是业务表与 `outbox` 表在同一个本地事务里 `INSERT`，事务提交即两者同时可见；独立投递进程或 Debezium 之类 CDC 读 `binlog` 扫描未发送行，投递成功后标记或删除。

这样不会出现库提交了但消息没发，或消息发了但库回滚。RocketMQ 的事务消息用 half message 加事务回查实现类似语义：先发对消费者不可见的半消息，执行本地事务后 commit 或 rollback，超时未决则回查生产者。

投递链路通常是 at-least-once，因此消费端必须幂等：用幂等键列加唯一索引，配合插入冲突则忽略的写法（`ON CONFLICT DO NOTHING`），或用去重表加状态机。

Kafka 与 RocketMQ 都不保证跨系统 exactly-once，业务侧靠幂等把重复收敛。最后要有对账任务比对 outbox、投递日志与消费结果，按业务单号找出不一致并告警或自动补偿，人工兜底入口必须保留。

**幂等与对账的实现要点**

| 机制 | 实现 | 可核对信号 |
| --- | --- | --- |
| 幂等键 | 业务单号加操作类型做唯一索引 | INSERT 冲突后返回既有结果 |
| 去重表 | 消费前查 processed 表 | 重复消费命中数 |
| outbox | 业务表与消息表同事务写 | pending 行积压时长 |
| 对账 | 定时比对三方记录 | 不一致条数与自动补偿成功率 |


## 跨服务事务方案选型

**跨服务事务方案选型**

| 方案 | 一致性 | 主要代价 | 适用场景 |
| --- | --- | --- | --- |
| 2PC / XA | 强一致 CP | 同步阻塞、协调者单点、in-doubt 需恢复 | 同机房短事务、强一致刚需 |
| TCC | 最终一致业务层 | 三套接口、空回滚与悬挂、幂等都要处理 | 支付交易等需预留资源的核心链路 |
| Saga | 最终一致补偿 | 无隔离性、补偿可失败、需对账 | 长流程、跨多服务、可容忍中间态 |
| Outbox + 消息 | 最终一致至少一次 | 消费端必须幂等、需投递与对账组件 | 异步通知、事件驱动、跨系统解耦 |


## 带 outbox、幂等消费与对账的下单编排

把一次下单落成可复现的最小骨架：业务状态与待发事件在同一次 `transact` 里写入日志，投递进程可以反复 `dispatch` 模拟至少一次送达，消费端用幂等键集合把重复事件收敛成一次生效，最后用对账数字确认投递数、消费数与生效数是否自洽。

真实系统里 `transact` 对应一次数据库提交，`dispatch` 对应轮询 `outbox` 或 CDC 读 `binlog`，`consume` 对应带唯一索引的去重表；把任意一环拆成两次无保护的写，就会重新引入本讲开头那两类脏数据。

重点是每个失败分支都有可观测出口：重复投递能被计数、重复消费能被识别、不一致能被对账发现。

```python
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
```

<Callout type="idea" title='落地提示' text='优先用 outbox + 事务消息保证本地提交与消息发送的原子性，为每个补偿定义幂等与可重试，并保留对账入口' />

<CheckList id='P107b' title='上线前自检' :items='["能复现并解释「先提交本地事务再发 MQ 消息」", "能复现并解释「Saga 只写正向流程，把补偿当成 undo 日志」", "能复现并解释「用 2PC 跨公网服务追求强一致」", "能用一条命令验证 本地事务边界", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

把输入换成你自己的数据，观察结果是否仍符合 本地事务边界 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 先提交本地事务再发 MQ 消息 | 两次写之间没有事务保护，进程在提交后发送前崩溃就永久丢消息；反向先发消息则本地回滚后消息已不可撤回 | 把消息写进与业务表同库的 outbox 表，用同一个本地事务提交，再由独立投递进程读取发送 |
| Saga 只写正向流程，把补偿当成 undo 日志 | 补偿是一次新的业务写，也可能超时或失败；网络重试还会让同一补偿到达多次，重复退款会造成资损 | 为每个补偿定义幂等键、可重试队列与终态，保留对账任务扫描未完成补偿并告警 |
| 用 2PC 跨公网服务追求强一致 | prepare 到 commit 之间长时间持锁，任一参与者抖动整链阻塞，协调者宕机留下 in-doubt 事务 | 强一致收缩到单库内，跨服务改用 outbox 或 Saga；必须使用时监控长事务与 prepared 事务数量 |

<Callout type="warn" title='本讲最容易踩的坑' text='先提交本地事务再发 MQ 消息：两次写之间没有事务保护，进程在提交后发送前崩溃就永久丢消息；反向先发消息则本地回滚后消息已不可撤回' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：先提交本地事务再发 MQ 消息", "body": "两次写之间没有事务保护，进程在提交后发送前崩溃就永久丢消息；反向先发消息则本地回滚后消息已不可撤回", "tip": "把消息写进与业务表同库的 outbox 表，用同一个本地事务提交，再由独立投递进程读取发送"}, {"title": "第 2 步：Saga 只写正向流程，把补偿当成 undo", "body": "补偿是一次新的业务写，也可能超时或失败；网络重试还会让同一补偿到达多次，重复退款会造成资损", "tip": "为每个补偿定义幂等键、可重试队列与终态，保留对账任务扫描未完成补偿并告警"}, {"title": "第 3 步：用 2PC 跨公网服务追求强一致", "body": "prepare 到 commit 之间长时间持锁，任一参与者抖动整链阻塞，协调者宕机留下 in-doubt 事务", "tip": "强一致收缩到单库内，跨服务改用 outbox 或 Saga；必须使用时监控长事务与 prepared 事务数量"}]' />


## FLP 不可能性与 2PC 的终止性缺口

2PC 的阻塞不是实现缺陷，而是协议在异步网络下的结构性代价。Fischer、Lynch、Paterson 1985 年的结论（FLP）是：在允许哪怕一个进程崩溃的异步系统里，不存在确定性保证所有正确进程在有限步内达成一致的算法——无法区分「对端崩了」和「对端只是慢」，任何声称能终止的协议都存在一个把消息无限延迟的调度。

2PC 直接撞在这条边界上：协调者在 prepare 之后、写全局提交日志之前崩溃，已返回 ready 的参与者既不能自行 commit（万一别人 rollback）、也不能自行 rollback（万一别人 commit），只能停在 in-doubt 等裁决，行锁与连接一路持有。

XA 把这段状态显式化：MySQL 的 XA `START`、XA END、XA `PREPARE` 把分支置为 `PREPARED`，连接断开后事务仍以 in-doubt 分支存活，由 XA `RECOVER` 列出再裁决；

PostgreSQL 的 `PREPARE` `TRANSACTION` 把事务落盘为 prepared xact，由 max_prepared_transactions 限制数量（默认常为 0），恢复靠 pg_prepared_xacts 与 `COMMIT` `PREPARED`。

3PC 想用 pre-commit 消除阻塞，但分区下会出现「一部分已 pre-commit、另一部分未收到」，安全性不成立，生产几乎不用。工程结论是：强一致只留给同一个资源管理器内部，跨服务改用 outbox / Saga 把「必须同时决定」的时刻压成一次本地写。

```python
def two_pc(participants, crash, ticks=6):
    state = {p: 'prepared' for p in participants}
    locks = {p: 1 for p in participants}
    if not crash:
        for p in state:
            state[p] = 'committed'
            locks[p] = 0
        return 'all_committed', 0, 0
    in_doubt = sum(1 for s in state.values() if s == 'prepared')
    for p in state:
        if state[p] == 'prepared':
            state[p] = 'committed'
    return 'coordinator_crashed_before_decision', in_doubt, sum(locks.values()) * ticks

print('normal', two_pc(['stock', 'balance', 'order'], False))
print('crash', two_pc(['stock', 'balance', 'order'], True))
```

<OutputBox title='扩展示例运行结果' output='normal (&#39;all_committed&#39;, 0, 0)\ncrash (&#39;coordinator_crashed_before_decision&#39;, 3, 18)' />

<LineByLine code='def two_pc(participants, crash, ticks=6):\n    state = {p: &#39;prepared&#39; for p in participants}\n    locks = {p: 1 for p in participants}\n    if not crash:\n        for p in state:\n            state[p] = &#39;committed&#39;\n            locks[p] = 0\n        return &#39;all_committed&#39;, 0, 0\n    in_doubt = sum(1 for s in state.values() if s == &#39;prepared&#39;)\n    for p in state:\n        if state[p] == &#39;prepared&#39;:\n            state[p] = &#39;committed&#39;\n    return &#39;coordinator_crashed_before_decision&#39;, in_doubt, sum(locks.values()) * ticks\n\nprint(&#39;normal&#39;, two_pc([&#39;stock&#39;, &#39;balance&#39;, &#39;order&#39;], False))\nprint(&#39;crash&#39;, two_pc([&#39;stock&#39;, &#39;balance&#39;, &#39;order&#39;], True))' :notes='["prepare 阶段把所有参与者置为 prepared 并上锁", "正常路径写 commit 决定、释放全部锁，无 in-doubt", "故障注入：协调者崩溃，统计 prepared 数与累计锁持有 tick", "正常路径 0 个 in-doubt；崩溃路径 3 个参与者各持锁 6 tick 共 18", "outbox 把业务表与消息放进同一次本地事务，投递 at-least-once，消费端用唯一索引收敛重复", "最终一致成立条件 = 至少一次投递 + 幂等消费 + 可观测对账，缺一就留人工修补的差额", "本地事务靠单资源管理器的 undo/redo 日志与锁；跨 MQ / Redis / 多库就没有共享提交点", "2PC 的 prepare 锁行到 commit，协调者宕机让参与者卡在 in-doubt；`PREPARE TRANSACTION` 受 `max_prepared_transactions` 限制，默认常为 0", "TCC 用 Try / Confirm / Cancel 把锁搬到业务字段，要防空回滚、悬挂与幂等", "Saga 为每个本地事务配补偿、失败逆序执行，补偿是新的业务写、缺隔离性；编排式与协同式各有权衡", "outbox 把业务表与消息放进同一次本地事务，投递 at-least-once，消费端用唯一索引收敛重复", "最终一致成立条件 = 至少一次投递 + 幂等消费 + 可观测对账，缺一就留人工修补的差额", "本地事务靠单资源管理器的 undo/redo 日志与锁；跨 MQ / Redis / 多库就没有共享提交点", "2PC 的 prepare 锁行到 commit，协调者宕机让参与者卡在 in-doubt；`PREPARE TRANSACTION` 受 `max_prepared_transactions` 限制，默认常为 0", "TCC 用 Try / Confirm / Cancel 把锁搬到业务字段，要防空回滚、悬挂与幂等"]' title='扩展示例逐行讲解' />

<ConceptDiagram type='flow4' title='第 107 讲 · 扩展图解' labels='prepare ready|写全局提交日志|commit 广播|in-doubt 窗口' caption='协调者崩溃落在两条日志之间时，参与者既不能提交也不能回滚，锁一直持有到恢复进程裁决' />


### XA 状态机里 in-doubt 的恢复裁决

把 in-doubt 的代价写成可算的量：设一个 XA 事务涉及 P 个参与者、每个 prepare 后持有 R 行行锁，协调者在写完 redo 但未广播 commit 时崩溃，恢复进程平均 T_rec 秒后读全局日志裁决，则冻结的锁数是 P·R，锁持有总时间是 P·R·T_rec 锁秒。

若同类事务以每秒 lambda 个到达，里托定理给出平均同时 in-doubt 的锁数 `L = lambda`·P·R·T_rec：`lambda=50`、`P=3`、`R=8`、`T_rec=30` 秒时 `L=36000` 个行锁，连接池与锁表先耗尽，吞吐塌到接近零。

这正是「协调者单点」的量化形式：2PC 可用性约等于所有参与者与协调者可用性的连乘。恢复裁决还有不对称性：协调者若在写全局日志前崩溃，参与者只能集体 rollback；若已写 commit 日志则集体 commit；

日志落盘与广播之间这「一条日志的窗口」决定整个集群走向，所以 XA 实现都在 prepare 阶段把 redo 强制刷盘，这是 2PC 延迟的主要来源。

相比之下 outbox 把「业务行加 outbox 行」放进同一个本地事务，commit 一次落盘即原子可见，根本不存在 in-doubt，代价是下游至少一次投递必须由消费端幂等兜住——把强一致的阻塞换成最终一致的重复，正是两类方案的架构分界。

**故障注入下各方案能否终止**

| 故障场景 | 2PC / XA | 3PC | TCC | Saga 与 outbox |
| --- | --- | --- | --- | --- |
| 协调者 prepare 后崩溃 | in-doubt 等恢复裁决，锁不释放 | pre-commit 未齐时仍可能阻塞 | Try 已预留，靠 Cancel 超时释放 | 本地已提交，投递继续，无阻塞 |
| 网络分区成两半 | 多数派侧阻塞，CP 选择不放行 | 分区下安全性不成立，可双提交 | 预留各自可见，靠业务超时 | 各自处理本地事务，靠对账收敛 |
| 终止性保证 | 无，受 FLP 边界限制 | 仅在网络同步假设下成立 | 有超时驱动 | 有，异步最终一致 |


### 回查次数与事务消息的悬挂窗口

RocketMQ 事务消息的一次线上悬挂：订单服务发 half message 后执行本地事务，本地事务提交成功但进程在二次 commit 前被 OOMKill，broker 一直没收到确认，消息停在「待回查」。

broker 按默认策略回查 checkLocalTransaction，可回查实现只查内存里的事务状态表，进程重启后这张表是空的，于是连续返回 `UNKNOWN`；RocketMQ 默认最多回查 15 次、间隔按配置递增，超过次数后把消息直接丢弃，下游永远没收到扣库存通知。

复盘补了两处：回查必须查数据库里的本地事务记录而不是内存，并为 half message 落带业务单号的状态表；超过回查上限的消息进死信队列并告警，由对账任务每日扫描补齐。下面模拟「内存状态丢失」与「状态持久化」两条路径下消息最终是否投递。

```python
def transaction_state_table(db, order_id):
    return db.get(order_id, 'UNKNOWN')

def broker_check(db, order_id, max_checks=15, memory_state=None):
    for attempt in range(1, max_checks + 1):
        state = memory_state if memory_state is not None else transaction_state_table(db, order_id)
        if state == 'COMMIT':
            return 'delivered_at_check', attempt
        if state == 'ROLLBACK':
            return 'discarded_at_check', attempt
    return 'dropped_after_max_checks', max_checks

db_empty = {}
db_persisted = {'ORDER-9': 'COMMIT'}
print('memory_only', broker_check(db_empty, 'ORDER-9', memory_state='UNKNOWN'))
print('persisted', broker_check(db_persisted, 'ORDER-9'))
```

<Quiz no='107-1' q='关于 FLP 不可能性与 2PC，下面哪项准确？' :options='["异步网络里无法区分崩溃与极慢，2PC 在协调者崩溃后必然留下 in-doubt 窗口，阻塞由协议结构决定", "3PC 已经彻底解决分区下的终止性与安全性，生产可放心替换 2PC", "in-doubt 参与者可以自行 commit，因为多数派已经返回 ready", "只要把超时设得足够短，2PC 就不会发生阻塞"]' answer="0" explain='FLP 说明异步加可能崩溃下不存在确定性终止的一致性算法；2PC 在 prepare 与 commit 之间协调者崩溃会让参与者既不能提交也不能回滚，只能等恢复裁决。3PC 在分区下安全性不成立，自行提交会破坏原子性。' />


### 行锁持有时间随协调者恢复延迟的放大

<Exercise title='进阶：用里托定理估算 in-doubt 锁数并给出降级阈值' task='实现函数按 lambda·P·R·T_rec 计算平均冻结行锁数，对 lambda=50、P=3、R=8、T_rec=30 求值，并求把 L 压到 6000 以内允许的 T_rec 上限。' solution='def frozen_locks(rate, participants, rows, recovery_s):\n    return rate * participants * rows * recovery_s\n\nbase = frozen_locks(50, 3, 8, 30)\nmax_recovery = 6000 / (50 * 3 * 8)\nprint(&#39;frozen_locks&#39;, base)\nprint(&#39;max_recovery_s&#39;, round(max_recovery, 2))\nprint(&#39;with_5s_recovery&#39;, frozen_locks(50, 3, 8, 5))' explain='L 与 T_rec 成正比；把恢复时间从 30 秒压到 5 秒才能把冻结锁数压到 6000 以内。业务量上来后靠缩短恢复时间已不现实，架构上应改用 outbox 把 in-doubt 状态整个消除。' />


## 练习、自测与一页纸速记

<Exercise title='基础：给 Saga 补偿加幂等键' task='改写一个三步 Saga，让每个补偿带幂等键，重复触发 rollback 两次后打印库存只被加回一次，并说明为什么补偿必须可重入。' solution='state = {&#39;stock&#39;: 5}\ndone = set()\ndef compensate(name, fn):\n    if name not in done:\n        fn()\n        done.add(name)\ncompensate(&#39;stock&#39;, lambda: state.__setitem__(&#39;stock&#39;, 6))\ncompensate(&#39;stock&#39;, lambda: state.__setitem__(&#39;stock&#39;, 6))\nprint(state[&#39;stock&#39;], sorted(done))' explain='补偿会被消息队列重放或人工重试，没有幂等键就会重复加库存；用 done 集合登记已执行的名字，第二次调用直接跳过，状态只加一次。' />

<Exercise title='进阶：实现带 pending 超时告警的 outbox' task='给 outbox 每行加创建时间戳，实现 scan_pending(now, timeout) 返回超时未投递的行数，并解释这个指标为什么能提前发现投递进程僵死。' solution='rows = [(&#39;e1&#39;, 1000), (&#39;e2&#39;, 1005)]\ndef scan_pending(rows, now, timeout, sent):\n    return [e for e, t in rows if e not in sent and now - t &gt; timeout]\nprint(scan_pending(rows, 1100, 50, set()))\nprint(scan_pending(rows, 1100, 50, {&#39;e1&#39;, &#39;e2&#39;}))' explain='outbox 积压时长是投递链路健康度的直接信号；超时仍为 pending 说明投递进程卡住或 MQ 不可用，比等业务侧报数据不一致更早暴露故障。' />

<Quiz no='107-2' q='某系统先写数据库再发 MQ，进程恰好在两者之间崩溃，最准确的后果是？' :options='["本地提交已生效但消息永久丢失，下游状态与上游不一致", "数据库会自动回滚这次提交", "MQ 会补发这条丢失的消息", "2PC 会隐式介入保证两者原子"]' answer="0" explain='两次写没有共享事务协调者，commit 之后崩溃不会回滚，消息也没发出；这正是 outbox 要消除的窗口，MQ 与数据库之间不存在自动的 XA 协调。' />

<Quiz no='107-3' q='关于 Saga 补偿操作，下面哪项描述正确？' :options='["补偿是一次新的业务写，必须幂等、可重试并保留对账入口", "补偿就是数据库 undo 日志，天然幂等", "补偿一定不会失败，无需监控", "逆序补偿能保证隔离性，其它请求看不到中间态"]' answer="0" explain='补偿通过退款、加库存等新写操作抵消效果，网络重试会让它重复到达，因此要幂等；它本身可能失败，且 Saga 没有隔离性，中间态对外可见。' />

<Quiz no='107-4' q='Transactional Outbox 成立的关键前提是什么？' :options='["业务表与 outbox 表在同一个数据库、同一次本地事务里写入", "MQ 支持 exactly-once 语义", "所有服务共享同一个 2PC 协调者", "消费端不使用任何去重机制"]' answer="0" explain='outbox 把跨系统原子性降维成单库 ACID：一次事务同时写业务状态与待发事件。投递仍是至少一次，因此消费端必须幂等。' />

<Predict no='107-5' q='Saga 第三步骤抛 RuntimeError 后，compensated 集合最可能是什么？' :options='["[&#39;balance&#39;, &#39;stock&#39;]，只补偿已成功的两步", "[&#39;order&#39;, &#39;balance&#39;, &#39;stock&#39;]，含失败步骤", "[]，因为整体失败不做任何补偿"]' answer='0' output='[&#39;balance&#39;, &#39;stock&#39;]' explain='rollback 遍历 done，而 done 只登记正向执行成功的步骤；失败的 order 在 append 之前就返回 False，不会进入 done，因此逆序补偿 balance 与 stock。' />

<FillBlank no='107-6' tpl='___ __init__(self):' :answers='["def"]' hint='回想本讲关于 本地事务边界 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 本地事务的 ACID 边界与 2PC 为何阻塞 的落点。' />

<KnowledgeCard :points='["本地事务靠单资源管理器的 undo/redo 日志与锁；跨 MQ / Redis / 多库就没有共享提交点", "2PC 的 prepare 锁行到 commit，协调者宕机让参与者卡在 in-doubt；`PREPARE TRANSACTION` 受 `max_prepared_transactions` 限制，默认常为 0", "TCC 用 Try / Confirm / Cancel 把锁搬到业务字段，要防空回滚、悬挂与幂等", "Saga 为每个本地事务配补偿、失败逆序执行，补偿是新的业务写、缺隔离性；编排式与协同式各有权衡", "outbox 把业务表与消息放进同一次本地事务，投递 at-least-once，消费端用唯一索引收敛重复", "最终一致成立条件 = 至少一次投递 + 幂等消费 + 可观测对账，缺一就留人工修补的差额"]' :pitfalls='["先提交本地事务再发 MQ 消息", "Saga 只写正向流程，把补偿当成 undo 日志", "用 2PC 跨公网服务追求强一致", "Saga 的补偿操作本身也可能失败，只写正向流程等于把不一致留到线上"]' summary='跨服务没有免费的 ACID：强一致方案牺牲可用与吞吐，最终一致方案把复杂度转移到补偿与对账' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 本地事务靠单资源管理器的 undo/redo 日志与锁；跨 MQ / Redis / 多库就没有共享提交点 | 建立直觉 |
| 2PC 的 prepare 锁行到 commit，协调者宕机让参与者卡在 in-doubt；`PREPARE TRANSACTION` 受 `max_prepared_transactions` 限制，默认常为 0 | 跑通示例 |
| TCC 用 Try / Confirm / Cancel 把锁搬到业务字段，要防空回滚、悬挂与幂等 | 深入边界 |
| Saga 为每个本地事务配补偿、失败逆序执行，补偿是新的业务写、缺隔离性；编排式与协同式各有权衡 | 工程落地 |
| outbox 把业务表与消息放进同一次本地事务，投递 at-least-once，消费端用唯一索引收敛重复 | 随堂检测 |
| 最终一致成立条件 = 至少一次投递 + 幂等消费 + 可观测对账，缺一就留人工修补的差额 | 复盘 |

1. 本地事务靠单资源管理器的 undo/redo 日志与锁；跨 MQ / Redis / 多库就没有共享提交点

2. 2PC 的 prepare 锁行到 commit，协调者宕机让参与者卡在 in-doubt；`PREPARE TRANSACTION` 受 `max_prepared_transactions` 限制，默认常为 0

3. TCC 用 Try / Confirm / Cancel 把锁搬到业务字段，要防空回滚、悬挂与幂等

[下一讲：分布式 ID、一致性哈希与分片](/distributed/sharding)
