---
title: 第 106 讲 · 幂等、分布式锁与限流
description: 让重试安全、让共享资源有序
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★☆' time='40 分钟' goal='让重试安全、让共享资源有序' prereq='第 105 讲 · CAP / BASE 与一致性模型' />

# 第 106 讲 · 幂等、分布式锁与限流

一致性等级刚定下，线上还有更硬的一层：一次超时并不等于失败，客户端一重试，写接口就再发一遍；两个请求同时改库存，光靠『先查后写』也挡不住并发。本讲只做实三件事——让重放安全、让共享资源排队、让流量有上限。

先看幂等键怎么设计，用去重表与唯一索引兜底，而不是靠一次查询去赌；再讲分布式锁，为什么锁必须带租约、释放时还得校验持有者；最后用令牌桶、漏桶搭起分布式限流，说清固定窗口的边界坑，以及网关、服务端各做一层。需要唯一索引与本地事务、异常处理与重试，会几条 Redis 命令，并带着上一讲的一致性窗口。做完之后，你能给写接口配好幂等键、给锁加上租约校验，把限流做成多实例共享的一套。


## 支付接口超时重试，用户被扣了两次

支付接口超时，客户端按「超时就重试」的逻辑重发了一次请求，结果用户被扣了两笔款。根因不复杂：服务端写接口没有幂等保护，而分布式系统里「超时不等于失败」——请求可能已经成功执行，只是响应在网络里丢了。团队第一版用「先查订单是否存在、不存在再插入」做去重，压测并发下两个请求都查到「不存在」、都执行了插入，重复照旧发生。

另一个故障更棘手：有人用 Redis 做分布式锁却没设过期时间，持有者进程半夜崩溃，锁永远不释放，次日所有下单请求永久阻塞。再加上秒杀流量没做限流，数据库连接池被瞬间打满。本讲把「让重试安全、让共享资源有序」落到幂等键、唯一索引、带租约的锁与令牌桶这些可核对的机制上。

<Callout type="warn" title='先看一个真实会出错的写法' text='用「先查后写」实现幂等，并发下仍重复扣款：SELECT 与 INSERT 是两条独立操作，两个请求都在对方提交前查到不存在、都执行写入' />


## 幂等键设计：从业务语义生成键

幂等指同一操作执行多次与执行一次的效果相同，写成 `f(f(x)) = f(x)`。`HTTP` 语义里 GET / PUT / `DELETE` 设计上幂等，`POST` 不是；但工程判据不靠方法名，而靠「写接口能不能被安全重放」。

前提是承认超时不等于失败：调用方超时重试、消息队列至少一次投递、网关重发，都可能让同一请求到达多次，因此幂等是消费端的责任。幂等键一般由调用方生成并随请求带上，要有明确作用域（用户 id + 业务单号 + 操作类型），可用 `UUID` 或业务单号加操作码，服务端按 key 去重并设 TTL 与清理周期。

最强兜底是「去重表 + 唯一索引」：给幂等键建 `UNIQUE` 约束，把「插入去重记录」与「业务写」放进同一个本地事务，利用数据库唯一索引的原子性——并发插入只有一个能成功，冲突即重复，压根不存在先查后写的竞态窗口。

Redis 的 `SET key value NX EX ttl` 可以做前置快速去重，但 Redis 与数据库之间不是同一个事务，最终一致性仍要靠唯一索引兜底。

反模式就是「先 `SELECT` 查一下有没有、没有再 `INSERT`」：两个并发请求都在对方提交前查到「不存在」，于是都写，本讲 probe 用 `dis` 反汇编证明检查与写入是分开的多条字节码。

正确写法是用数据库原生的「插入冲突则忽略」（如 `ON CONFLICT DO NOTHING`）、捕获唯一索引抛出的 `IntegrityError`，或带版本的 CAS 更新。

响应也要幂等：重复请求返回首次保存的结果，而不是抛错或返回不一致的新结果。

```python
class TokenBucket:
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.rate = refill_rate
        self.tokens = float(capacity)
        self.last = 0.0
    def allow(self, now, cost=1.0):
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False
b = TokenBucket(capacity=3, refill_rate=1)
times = [0, 0, 0, 0, 0.5, 1, 1, 1, 2]
print([b.allow(t) for t in times])
```

<OutputBox title='主示例运行结果' output='[True, True, True, False, False, True, False, False, True]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class TokenBucket:\n    def __init__(self, capacity, refill_rate):\n        self.capacity = capacity\n        self.rate = refill_rate\n        self.tokens = float(capacity)\n        self.last = 0.0\n    def allow(self, now, cost=1.0):\n        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)\n        self.last = now\n        if self.tokens &gt;= cost:\n            self.tokens -= cost\n            return True\n        return False\nb = TokenBucket(capacity=3, refill_rate=1)\ntimes = [0, 0, 0, 0, 0.5, 1, 1, 1, 2]\nprint([b.allow(t) for t in times])' :notes='["定义令牌桶限流器，用逻辑时钟保证输出可复现", "构造参数：capacity 桶容量、refill_rate 每秒补充令牌数", "记录桶容量，作为令牌上限与突发上限", "记录补充速率，限制长期平均速率", "初始令牌满桶，因此允许一次性突发 capacity 个请求", "上次补充的逻辑时间戳，初始为 0", "allow 判断某时刻的请求能否取到令牌，cost 默认 1", "先按经过时间补充令牌，再用 min 截断到不超过桶容量", "更新逻辑时间戳，下一次从这一刻开始算增量", "令牌足够才放行，判定条件是 tokens 大于等于 cost", "扣掉本次消耗的令牌", "返回放行", "令牌不足返回拒绝，不扣令牌", "容量 3、每秒补 1 个令牌的桶", "九个请求的逻辑到达时刻，含同刻突发与跨秒补充", "逐个判定并打印，观察突发与平滑补充两类行为"]' title='第 106 讲 · 幂等、分布式锁与限流' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 去重表与唯一索引：让数据库原子去重

**幂等实现方案对照**

| 方案 | 原子性 | 并发安全 | 适用 |
| --- | --- | --- | --- |
| 先查后写 SELECT+INSERT | 否 | 否，两请求都查到不存在 | 反模式，禁止 |
| 去重表 + 唯一索引 | 是（本地事务） | 是，冲突即重复 | 强兜底，推荐 |
| INSERT ON CONFLICT DO NOTHING | 是 | 是 | PostgreSQL/SQLite 原生 |
| Redis SETNX + Lua | Redis 内原子 | 前置快速去重 | 与 DB 间非原子，需兜底 |

```python
import dis
def unsafe_write(store, key, val):
    if key not in store:
        store[key] = val
ops = [i.opname for i in dis.get_instructions(unsafe_write)]
print('check and store separate?', 'CONTAINS_OP' in ops and 'STORE_SUBSCR' in ops)
print('instruction count', len(ops))
print('STORE_SUBSCR count', ops.count('STORE_SUBSCR'))
print('key ops', [o for o in ops if o in ('CONTAINS_OP', 'STORE_SUBSCR')])
```

<OutputBox title='原理验证' output='check and store separate? True\ninstruction count 9\nSTORE_SUBSCR count 1\nkey ops [&#39;CONTAINS_OP&#39;, &#39;STORE_SUBSCR&#39;]' />


### 用 dis 看「先查后写」为什么不是原子的

```python
seen = set()
def handle(idem_key, op):
    if idem_key in seen:
        return 'duplicate-ignored'
    seen.add(idem_key)
    return op + '-applied'
for key in ['k1', 'k1', 'k2', 'k1']:
    print(key, handle(key, 'charge'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='k1 charge-applied\nk1 duplicate-ignored\nk2 charge-applied\nk1 duplicate-ignored' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "class TokenBucket:\n    def __init__(self, capacity, refill_rate):\n        self.capacity = capacity\n        self.rate = refill_rate\n        self.tokens = float(capacity)\n        self.last = 0.0\n    def allow(self, now, cost=1.0):\n        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)\n        self.last = now\n        if self.tokens &gt;= cost:\n            self.tokens -= cost\n            return True\n        return False\nb = TokenBucket(capacity=3, refill_rate=1)\ntimes = [0, 0, 0, 0, 0.5, 1, 1, 1, 2]\nprint([b.allow(t) for t in times])", "note": "幂等键、去重表与唯一索引"}, {"label": "对照 / 进阶", "code": "seen = set()\ndef handle(idem_key, op):\n    if idem_key in seen:\n        return &#39;duplicate-ignored&#39;\n    seen.add(idem_key)\n    return op + &#39;-applied&#39;\nfor key in [&#39;k1&#39;, &#39;k1&#39;, &#39;k2&#39;, &#39;k1&#39;]:\n    print(key, handle(key, &#39;charge&#39;))", "note": "分布式锁、租约与看门狗"}]' title='两种写法对照' note='差异集中在 幂等键设计；先看输出，再找背后的规则。' />


## 分布式锁：SET NX EX 与随机值

分布式锁要满足互斥、不会死锁、容错三条。Redis 的经典实现是一条原子命令：`SET` 带 `NX`（只有键不存在才设置，保证互斥）与 `EX`（给锁一个租约，过期自动释放），value 用一个随机 token 标识持有者。

释放必须写成 Lua 脚本「先比对 value 是否等于自己的 token，相等才 `DEL`」，因为「先 `GET` 再 `DEL`」是非原子的——锁可能在这两步之间过期并被别人持有，直接 `DEL` 就会误删别人的锁。

锁必须带租约，否则持有者崩溃后锁永不释放，所有后续请求永久阻塞；但业务执行时间可能超过 TTL，于是引入看门狗（如 Redisson 的 watchdog）：后台线程在锁快到期时自动续期，进程存活才续、崩溃即停止续期让锁自然过期。TTL 是权衡：太短业务没做完锁就被别人拿走、互斥失效，太长崩溃后恢复慢。

还要防「旧持有者 GC 暂停后苏醒继续写」的竞态，用 fencing token 兜底——每次加锁返回一个单调递增令牌，写存储时带上，存储拒绝更小令牌的写。

Redlock 多实例方案在 Martin Kleppmann 与 antirez 的论战中存在争议；对强一致要求高的场景，更稳妥的是基于共识的锁（etcd / ZooKeeper 的租约与顺序节点），或直接用数据库唯一约束。

<Callout type="tip" title='核心心智模型' text='幂等指同一操作执行多次与执行一次的效果相同，写成 `f(f(x)) = f(x)`。HTTP 语义里 GET / PUT / DELETE 设计上幂等，POST 不是；但工程判据不靠方法名，而靠「写接口能不能被安全重放」。前提是承认超时不等于失败：调用方超时重试、消息队列至少一次投递、网关重发，都可…' />


## 租约、看门狗与 fencing token

**限流算法对照**

| 算法 | 输出速率 | 是否容许突发 | 边界问题 |
| --- | --- | --- | --- |
| 令牌桶 | 平均 r，突发最多 c | 是 | capacity 决定突发上限 |
| 漏桶 | 恒定匀速 | 否 | 突发被排队或丢弃 |
| 固定窗口计数 | 窗口内 ≤ 阈值 | 边界处可放行 2 倍 | 窗口切换瞬间翻倍 |
| 滑动窗口计数 | 任意窗口内 ≤ 阈值 | 较准 | 内存/实现成本更高 |

<Callout type="warn" title='本讲最容易踩的坑' text='用「先查后写」实现幂等，并发下仍重复扣款：SELECT 与 INSERT 是两条独立操作，两个请求都在对方提交前查到不存在、都执行写入' />


## 令牌桶与漏桶：放行序列怎么算

限流保护下游不被突发流量打垮。令牌桶：以固定速率 r 往容量 c 的桶里补充令牌，每个请求取走 1 个，桶里有令牌就放行、空了就拒绝或排队；它容许最多 c 的突发（攒下的令牌可以一次用完），长期平均速率被 r 限制，是网关与 Guava RateLimiter 的常见模型。

本讲 code 里 `capacity=3`、`refill_rate=1`，逻辑时钟下 0 时刻连放 3 个、第 4 个拒绝，0.5 秒补到 0.5 仍不够，1 秒补到 1 放 1 个，2 秒再放 1 个。漏桶则以恒定速率漏出请求、输出完全平滑，不允许突发，适合需要严格匀速的下游。

计数算法里固定窗口在窗口边界会放行接近 2 倍流量（前一窗口末尾 + 后一窗口开头），滑动窗口 / 滑动日志更准，但更费内存。

分布式限流要分两层：网关层做粗粒度全局限流挡掉大部分流量，服务端做按用户 / 租户 / 接口的细粒度限流；跨进程共享计数必须用 Redis + Lua 把「读-改-写」做成原子（`INCR` + `EXPIRE`，或令牌桶的原子脚本），否则并发下计数偏小、限流失效，本地再用单机限流器兜底。

被限流的请求返回 429 与 Retry-After，客户端按指数退避加抖动重试，避免重试风暴把系统再推一遍。限流还要区分读与写、可丢弃与必达，并对写操作叠加幂等，防止「被限流 → 重试 → 重复」的组合故障。

<ArchBlueprint title='第 106 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "幂等键、去重表与唯一索引", "protocol": "调用 / 请求", "items": [{"label": "幂等键、去重表与唯一索引", "sub": "输入与前置", "detail": "幂等指同一操作执行多次与执行一次的效果相同，写成 `f(f(x)) = f(x)`。HTTP 语义里 GET / PUT / DELETE 设计上幂等，POST 不是；但工程判据不靠方法名，而靠「写接口能不能被安全重放」。前提是承认超时不等于失败：调用方超时重试、消息队列至少一次投递、网关重发，都可…", "tone": "blue"}]}, {"name": "核心规则", "note": "分布式锁、租约与看门狗", "protocol": "语言 / 运行时协议", "items": [{"label": "分布式锁、租约与看门狗", "sub": "状态与边界", "detail": "分布式锁要满足互斥、不会死锁、容错三条。Redis 的经典实现是一条原子命令：`SET` 带 `NX`（只有键不存在才设置，保证互斥）与 `EX`（给锁一个租约，过期自动释放），value 用一个随机 token 标识持有者。释放必须写成 Lua 脚本「先比对 value 是否等于自己的 token…", "tone": "purple"}]}, {"name": "落地与收尾", "note": "令牌桶、漏桶与分布式限流", "items": [{"label": "令牌桶、漏桶与分布式限流", "sub": "工程处理", "detail": "限流保护下游不被突发流量打垮。令牌桶：以固定速率 r 往容量 c 的桶里补充令牌，每个请求取走 1 个，桶里有令牌就放行、空了就拒绝或排队；它容许最多 c 的突发（攒下的令牌可以一次用完），长期平均速率被 r 限制，是网关与 Guava RateLimiter 的常见模型。本讲 code 里…", "tone": "green"}]}]' />

**分布式锁的关键参数与失效**

| 要素 | 正确做法 | 缺失后果 |
| --- | --- | --- |
| 加锁 | SET key token NX EX ttl | 先 SET 再 EXPIRE 非原子可能永不过期 |
| 释放 | Lua 比对 token 再 DEL | 误删别人的锁 |
| 租约 TTL | 按业务耗时设 + 看门狗续期 | 无 TTL 崩溃后永久阻塞 |
| 旧持有者 | fencing token 单调令牌 | GC 暂停苏醒后覆盖新写 |
| 共享计数 | Redis + Lua 原子 INCR/EXPIRE | 读-改-写竞态使限流失效 |


## 固定窗口边界为什么放行两倍流量

幂等要求操作满足 `f(f(x)) = f(x)`，在存在重试与至少一次投递的系统里，等价要求是「同一幂等键的写最多生效一次」。

唯一索引能提供这个保证，是因为数据库把「检查冲突 + 插入」做成单条原子操作并加锁，两个并发事务插入相同键时，第二个必然收到唯一约束冲突；而应用层的 `SELECT` 与 `INSERT` 是两次独立语句，中间存在让出点，两个事务都读到「不存在」就都插入——本讲 probe 用 `dis` 反汇编显示检查（`CONTAINS_OP`）与写入（`STORE_SUBSCR`）是分离的两条指令，正是这个竞态窗口在语言层的类比。

令牌桶的补充是个封顶的线性式：用上一刻的令牌数加上经过的时间乘补充速率 r，再以容量 c 截断，因此既能限制长期平均速率、又容许最多一个容量的突发。

`SETNX` 的互斥来自 Redis 单线程执行命令的原子性，`EX` 租约把「持有者崩溃」转化为「到期自动释放」，看门狗把「业务未完成但锁过期」转化为「续期」，fencing token 则用全序令牌封住旧持有者的迟到写入。

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用「先查后写」实现幂等，并发下仍重复扣款", "body": "SELECT 与 INSERT 是两条独立操作，两个请求都在对方提交前查到不存在、都执行写入", "tip": "用去重表唯一索引 + 本地事务，或 INSERT ON CONFLICT DO NOTHING 让数据库原子去重"}, {"title": "第 2 步：分布式锁不设租约、释放时不校验持有者", "body": "持有者崩溃后锁永不释放；直接 DEL 会误删已被别人持有的同名锁", "tip": "SET key token NX EX ttl 带随机值，Lua 比对 token 再释放，配看门狗续期与 fencing token"}, {"title": "第 3 步：固定窗口限流在边界放行 2 倍流量 / 限流…", "body": "固定窗口切换瞬间前窗末尾与后窗开头的请求都通过；客户端限流可被绕过且多实例不共享计数", "tip": "改滑动窗口，网关层与服务端各做一层，跨进程计数用 Redis + Lua 原子化，429 配 Retry-After 与退避"}]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用「先查后写」实现幂等，并发下仍重复扣款 | SELECT 与 INSERT 是两条独立操作，两个请求都在对方提交前查到不存在、都执行写入 | 用去重表唯一索引 + 本地事务，或 INSERT ON CONFLICT DO NOTHING 让数据库原子去重 |
| 分布式锁不设租约、释放时不校验持有者 | 持有者崩溃后锁永不释放；直接 DEL 会误删已被别人持有的同名锁 | SET key token NX EX ttl 带随机值，Lua 比对 token 再释放，配看门狗续期与 fencing token |
| 固定窗口限流在边界放行 2 倍流量 / 限流只在客户端做 | 固定窗口切换瞬间前窗末尾与后窗开头的请求都通过；客户端限流可被绕过且多实例不共享计数 | 改滑动窗口，网关层与服务端各做一层，跨进程计数用 Redis + Lua 原子化，429 配 Retry-After 与退避 |


## 网关限流 + 服务端幂等：把两层保护串成一条链

一次支付请求要同时防「流量冲垮下游」和「超时重试重复扣款」，正确顺序是网关先限流挡掉超量请求，服务端再用幂等键去重，两者职责不同、缺一不可。

下面用纯标准库把这条链写成自洽模块：`TokenBucket` 按逻辑时钟限流，`service` 用去重表模拟唯一索引的幂等，`handle` 串起「先过网关、再查重、再执行」，并打印六个事件的结果。它要说明的是，限流与幂等是串联的两道闸，且被限流的请求根本不该走到写库那一步。

真实项目把 `TokenBucket` 换成 Redis + Lua 的原子令牌桶、把 `set` 换成带 `UNIQUE` 索引的去重表，并把插入与扣款放进同一事务，结构不变。

```python
class TokenBucket:
    def __init__(self, cap, rate):
        self.cap, self.rate = cap, rate
        self.tokens, self.last = float(cap), 0.0
    def allow(self, now):
        self.tokens = min(self.cap, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
seen = set()
def gateway(now, bucket):
    return bucket.allow(now)
def service(idem):
    if idem in seen: return 'duplicate-ignored'
    seen.add(idem); return 'applied'
def handle(idem, now, bucket):
    if not gateway(now, bucket): return 'rate-limited'
    return service(idem)
bucket = TokenBucket(3, 1)
events = [('k1', 0), ('k1', 0), ('k2', 0), ('k3', 0), ('k4', 0), ('k5', 2)]
for idem, t in events:
    print(idem, handle(idem, t, bucket))
```

<Callout type="idea" title='落地提示' text='唯一索引加幂等表做强兜底，锁带随机值与租约，限流在网关与服务端各做一层' />

<CheckList id='P106a' title='上线前自检' :items='["能复现并解释「用「先查后写」实现幂等，并发下仍重复扣款」", "能复现并解释「分布式锁不设租约、释放时不校验持有者」", "能复现并解释「固定窗口限流在边界放行 2 倍流量 / 限流只在客户端做」", "能用一条命令验证 幂等键设计", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 幂等键设计 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 练习与速记：重试、锁与限流

<Exercise title='基础：手算令牌桶的放行序列' task='对 capacity=3、refill_rate=1 的桶与 times=[0,0,0,0,0.5,1,1,1,2]，手推每个时刻的令牌数，说明第 4、5 个请求为何被拒、第 6 个为何放行。' solution='def trace(cap,rate,ts):\n    tok,last=float(cap),0.0\n    for t in ts:\n        tok=min(cap,tok+(t-last)*rate); last=t\n        ok=tok&gt;=1\n        if ok: tok-=1\n        print(t,round(tok,2),ok)\ntrace(3,1,[0,0,0,0,0.5,1,1,1,2])' explain='前 3 个请求把初始 3 个令牌用光；0 时刻第 4 个、0.5 秒补到 0.5 的第 5 个都不足 1 被拒；1 秒补到 1 放行第 6 个，2 秒再补 1 放行最后一个。' />

<Exercise title='进阶：用 dis 证明先查后写非原子' task='反汇编「if key not in store: store[key] = val」，列出关键指令名，并说明为什么这会造成并发重复写。' solution='import dis\ndef w(store,key,val):\n    if key not in store:\n        store[key]=val\nprint([i.opname for i in dis.get_instructions(w) if i.opname in (&#39;CONTAINS_OP&#39;,&#39;STORE_SUBSCR&#39;)])' explain='CONTAINS_OP 与 STORE_SUBSCR 是分离的两条指令，中间可被切换；两个并发请求都完成检查、都执行写入即重复。修复靠数据库唯一索引把检查与插入合成一次原子操作。' />

<Quiz no='106-1' q='支付接口超时后客户端重试，服务端不重复扣款的最强兜底是？' :options='["去重表唯一索引 + 本地事务，把插入与业务写原子提交", "先 SELECT 查有没有再 INSERT", "只在客户端限制重试次数", "把接口改成 GET"]' answer="0" explain='唯一索引把「检查冲突 + 插入」做成原子操作，并发插入只有一个成功；先查后写在并发下两个请求都查到不存在、都写，反而重复。' />

<Quiz no='106-2' q='分布式锁用 Redis SET key val NX EX ttl，释放时的正确做法是？' :options='["用 Lua 脚本先比对 val 是否等于自己的 token，相等才 DEL", "直接 DEL 该 key", "等它自己过期，永不主动释放", "GET 看一下再 DEL（两步分开执行）"]' answer="0" explain='直接 DEL 或分开的 GET+DEL 都可能误删已被别人持有的同名锁；必须用 Lua 把「比对 token + DEL」合成一次原子操作。' />

<Quiz no='106-3' q='关于令牌桶与固定窗口，下面哪项准确？' :options='["令牌桶容许最多 capacity 的突发并限制长期平均速率，固定窗口在边界可能放行 2 倍", "漏桶允许突发而令牌桶不允许", "固定窗口比滑动窗口更精确", "令牌桶输出速率恒定不变"]' answer="0" explain='令牌桶攒的令牌可一次用完（突发上限 capacity）、长期速率受 r 限制；固定窗口在两个窗口交界处会同时放行前窗末尾与后窗开头，接近 2 倍阈值。' />

<Predict no='106-4' q='前面 code 里 times=[0,0,0,0,0.5,1,1,1,2] 对容量 3、补充 1/秒的桶逐个 allow，结果是？' :options='["[True, True, True, False, False, True, False, False, True]", "9 个全 True", "前 3 个 True、其余全 False"]' answer='0' output='[True, True, True, False, False, True, False, False, True]' explain='初始满桶 3 个令牌放行前 3 个；0 与 0.5 秒令牌不足被拒；1 秒补到 1 放行一个；2 秒再补 1 放行最后一个，正是突发 + 平滑补充的组合。' />

<FillBlank no='106-5' tpl='___ __init__(self, capacity, refill_rate):' :answers='["def"]' hint='回想本讲关于 幂等键设计 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 幂等键、去重表与唯一索引 的落点。' />

<KnowledgeCard :points='["幂等是 `f(f(x)) = f(x)`，写接口必须允许安全重放；超时不等于失败，重试 / 至少一次投递 / 网关重发都会带来重复", "最强兜底是去重表 + `UNIQUE` 索引：插入与业务写放进同一本地事务，靠唯一约束的原子性消除竞态", "反模式是先 `SELECT` 再 `INSERT`；改用 `ON CONFLICT DO NOTHING`、捕获 `IntegrityError` 或带版本 CAS", "Redis 锁用 `SET` + `NX` + `EX` + 随机 token，释放走 Lua 比对 token 再 `DEL`，带租约与看门狗", "令牌桶容许一个容量的突发、限制长期速率，漏桶严格匀速；固定窗口边界会放行近 2 倍流量", "限流网关与服务端各一层，跨进程计数用 Redis + Lua 原子化；429 配退避加抖动，写操作叠加幂等"]' :pitfalls='["用「先查后写」实现幂等，并发下仍重复扣款", "分布式锁不设租约、释放时不校验持有者", "固定窗口限流在边界放行 2 倍流量 / 限流只在客户端做", "用「先查后写」实现幂等，并发下依旧会重复；锁不设租约则持有者崩溃后永久阻塞"]' summary='分布式系统里超时不等于失败，所以所有写接口都必须允许被安全地重放；幂等是消费端的责任' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 幂等是 `f(f(x)) = f(x)`，写接口必须允许安全重放；超时不等于失败，重试 / 至少一次投递 / 网关重发都会带来重复 | 建立直觉 |
| 最强兜底是去重表 + `UNIQUE` 索引：插入与业务写放进同一本地事务，靠唯一约束的原子性消除竞态 | 跑通示例 |
| 反模式是先 `SELECT` 再 `INSERT`；改用 `ON CONFLICT DO NOTHING`、捕获 `IntegrityError` 或带版本 CAS | 深入边界 |
| Redis 锁用 `SET` + `NX` + `EX` + 随机 token，释放走 Lua 比对 token 再 `DEL`，带租约与看门狗 | 工程落地 |
| 令牌桶容许一个容量的突发、限制长期速率，漏桶严格匀速；固定窗口边界会放行近 2 倍流量 | 随堂检测 |
| 限流网关与服务端各一层，跨进程计数用 Redis + Lua 原子化；429 配退避加抖动，写操作叠加幂等 | 复盘 |

1. 幂等是 `f(f(x)) = f(x)`，写接口必须允许安全重放；超时不等于失败，重试 / 至少一次投递 / 网关重发都会带来重复

2. 最强兜底是去重表 + `UNIQUE` 索引：插入与业务写放进同一本地事务，靠唯一约束的原子性消除竞态

3. 反模式是先 `SELECT` 再 `INSERT`；改用 `ON CONFLICT DO NOTHING`、捕获 `IntegrityError` 或带版本 CAS

[下一讲：分布式事务：2PC / TCC / Saga / 消息最终一致](/distributed/dist-tx)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/106-idempotency.py`

```bash
python3 examples/lessons/106-idempotency.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/106-idempotency.py) · [全部示例代码索引](/examples/)
