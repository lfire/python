---
title: 第 109 讲 · Raft 共识、服务发现与配置中心
description: 理解一致性组件替你承担了什么
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★★' time='45 分钟' goal='理解一致性组件替你承担了什么' prereq='第 108 讲 · 分布式 ID、一致性哈希与分片' />

# 第 109 讲 · Raft 共识、服务发现与配置中心

数据分片后机器多了，新麻烦浮出来：几台机器各存一份关键状态，到底谁说了算。改一个开关，希望所有节点同时看到同一个值，可网络一抖，彼此的记录就对不上。这类让多台机器认同一串操作的问题，靠存储或分片补不上，得有专门的机制托底。

从一次朴素的选主讲起：为什么需要 Leader、任期怎么防旧主复活、日志为何凑够多数派才敢提交；再看成员变更和 etcd 承担什么，最后谈配置推送与灰度回滚。需要 CAP 里关于分区的取舍、超时与重试；学完你能说清 Raft 替你扛了哪部分复杂度，也明白配置中心该放元数据、不该当数据库频繁读写。


## Raft 集群做成四节点，为什么只容忍一台故障

一个团队把服务发现当作万能注册中心：实例启动时写一条记录，之后既不续约也不下线；配置中心被用来高频读写业务开关，每次请求都去查一次。某次网络抖动，半数实例与注册中心短暂失联，健康检查还没来得及剔除，流量继续打到已不可用的实例，错误率飙升；

更糟的是配置中心被当成数据库扛读写，Raft 组因为频繁写入和 leader 切换出现延迟，依赖它的服务集体超时。根因是把共识组件承担的职责理解反了：Raft 解决的是多台机器对同一序列达成一致，它昂贵，只该承载少量关键元数据，不该承载业务数据或高频读。本讲把选举、日志复制、租约、健康检查、配置推送这几层各自的边界拆清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='把配置中心当业务数据库每次请求都读写：每次写都要走 Raft 日志复制与多数派落盘，吞吐受限，leader 切换时全部依赖方一起超时' />

<Callout type="tip" title='核心心智模型' text='Raft 把一致性问题拆成 Leader 选举、日志复制、安全性三个子问题。节点处于 follower / candidate / leader 三态，任期 `term` 单调递增；follower 在选举超时（etcd 默认 1000ms 量级，实际按 heartbeat interval 的倍数…' />


## Raft 的多数派与任期：Leader 选举、日志复制

Raft 把一致性问题拆成 Leader 选举、日志复制、安全性三个子问题。节点处于 follower / candidate / leader 三态，任期 `term` 单调递增；

follower 在选举超时（etcd 默认 1000ms 量级，实际按 heartbeat interval 的倍数）内没收到心跳就自增 term 转为 candidate 拉票，获得多数派选票才成为 leader。多数派是 `floor(N/2)+1`：5 节点集群 quorum 为 3，能容忍 2 节点故障；

4 节点 quorum 仍是 3，只容忍 1 节点故障，所以生产集群一律用奇数节点。日志复制时 leader 把条目追加到本地并并行发给 follower，收到多数派确认后才推进 `commitIndex` 并应用状态机；`commitIndex` 等于把各节点 `matchIndex` 降序排列后第 quorum 个值。

只有已提交条目对客户端可见，未提交条目在新 leader 上任后可能被覆盖。任期保证旧 leader 的过期请求被拒绝：任何 RPC 携带小于当前 term 的任期，都会让接收方返回失败并促使对方退位。

**Raft 集群规模与容错**

| 节点数 | 多数派 quorum | 可容忍故障节点 | 说明 |
| --- | --- | --- | --- |
| 3 | 2 | 1 | 最小可用奇数集群 |
| 4 | 3 | 1 | 偶数不增加容错，浪费一台 |
| 5 | 3 | 2 | 常见生产配置 |
| 7 | 4 | 3 | 写延迟随多数派变大，非必要不增大 |

<ConceptDiagram type='compare2' title='第 109 讲 · Leader 选举、任期与日志复制的多数派' labels='Leader 选举、任期与日志复制的多数派|成员变更、etcd 定位与租约维持的注册|健康检查、配置推送与灰度回滚|配置推送与灰度' caption='理解一致性组件替你承担了什么' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## commitIndex 与未提交条目的覆盖

Raft 的安全性由两条机制保证：选举限制要求 candidate 的日志至少与多数派一样新才能当选，避免已提交条目被覆盖；提交规则要求 leader 只推进被多数派复制的当前任期条目，间接提交旧任期条目。

多数派 `quorum = floor(N/2)+1` 让任意两个多数派必然相交，从而新旧 leader 不可能就同一日志索引提交冲突值，这是共识成立的组合结构。

代价是每次写都要 leader 追加日志、并行复制到多数派、落盘后再响应，吞吐受限于最慢的多数派成员与磁盘 fsync，所以 Raft 只适合少量关键元数据。租约把存活判断转成时间：实例周期性续约，停止续约后 TTL 到期由中心删除键，这比依赖崩溃时主动注销可靠，因为进程可能被 `SIGKILL` 或整机掉电。

但租约依赖各节点时钟推进速度大致一致，跨机房时钟偏差过大时会提前或延后失效，因此 lease TTL 要远大于续约间隔并留足网络抖动的余量。


### matchIndex 如何决定一条日志能否提交

```python
class Term:
    def __init__(self):
        self.current = 0
    def step(self, t):
        if t < self.current:
            return 'reject-stale'
        self.current = t
        return 'accept'
r = Term()
print(r.step(3))
print(r.step(2))
print(r.step(5))
print('term', r.current)
```

<OutputBox title='原理验证' output='accept\nreject-stale\naccept\nterm 5' />


## 成员变更、etcd 定位与租约维持的注册

成员变更不能一步从旧配置切到新配置，否则可能出现两个不相交的多数派同时选出两个 leader；Raft 用联合共识（joint consensus）或单节点逐步变更过渡，etcd 的 `ConfChange` 走的就是受控的成员变更流程。

etcd 基于 Raft 存键值，提供 `Watch`、`Lease`、`Txn`：服务注册通常不是写一条永久记录，而是申请一个带 TTL 的租约并周期性 `KeepAlive`，实例崩溃后停止续约，租约到期键自动删除，这比依赖主动注销可靠。

Consul 用 Raft 存服务目录、用 gossip 协议做成员与故障探测，定位类似但实现不同。关键边界是共识组件只存少量需要强一致的元数据（成员、租约、配置版本、leader 归属），业务数据留在各自存储；

把配置中心当数据库高频读写，会让每次写都走一次 Raft 日志复制与落盘，吞吐上不去，还会放大 leader 切换的影响。

```python
class Cluster:
    def __init__(self, n):
        self.n = n
        self.match = [0] * n
    def commit_index(self):
        replicas = sorted(self.match, reverse=True)
        return replicas[self.n // 2]
    def writable(self, alive):
        return alive > self.n // 2

c = Cluster(5)
print('quorum', 5 // 2 + 1)
print('commit_initial', c.commit_index())
c.match = [5, 4, 3, 0, 0]
print('commit_after_replication', c.commit_index())
print('alive3_writable', c.writable(3))
print('alive2_writable', c.writable(2))
```

<OutputBox title='主示例运行结果' output='quorum 3\ncommit_initial 0\ncommit_after_replication 3\nalive3_writable True\nalive2_writable False' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Cluster:\n    def __init__(self, n):\n        self.n = n\n        self.match = [0] * n\n    def commit_index(self):\n        replicas = sorted(self.match, reverse=True)\n        return replicas[self.n // 2]\n    def writable(self, alive):\n        return alive &gt; self.n // 2\n\nc = Cluster(5)\nprint(&#39;quorum&#39;, 5 // 2 + 1)\nprint(&#39;commit_initial&#39;, c.commit_index())\nc.match = [5, 4, 3, 0, 0]\nprint(&#39;commit_after_replication&#39;, c.commit_index())\nprint(&#39;alive3_writable&#39;, c.writable(3))\nprint(&#39;alive2_writable&#39;, c.writable(2))' :notes='["定义模拟 5 节点 Raft 集群", "构造器接收节点总数", "保存节点数用于计算多数派", "match 是各节点已复制的最大日志索引，初始为 0", "求可提交的最大日志索引", "把 matchIndex 降序排列", "取第 n//2 项，即多数派都达到的索引", "判断当前存活数能否形成多数派", "存活数必须严格大于半数", "空行，只用于分隔逻辑块，不影响执行结果。", "创建 5 节点集群", "多数派为 5//2+1，即 3", "初始所有 matchIndex 为 0，提交点为 0", "模拟复制进度：两节点落后", "降序第 2 项为 3，即 commitIndex 为 3", "存活 3 台满足多数派，可写", "存活 2 台不足多数派，拒绝写入以保证安全"]' title='第 109 讲 · Raft 共识、服务发现与配置中心' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 对照：永久注册记录与带 TTL 租约的输出

```python
import time

class Lease:
    def __init__(self, ttl):
        self.ttl = ttl
        self.expire = time.monotonic() + ttl
    def valid(self, now):
        return now < self.expire
    def renew(self, now):
        self.expire = now + self.ttl

l = Lease(10)
t0 = time.monotonic()
print('valid_now', l.valid(t0))
print('valid_later', l.valid(t0 + 11))
l.renew(t0 + 11)
print('valid_after_renew', l.valid(t0 + 12))
```

<OutputBox title='对照写法：先自己猜，再点开' output='valid_now True\nvalid_later False\nvalid_after_renew True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "class Cluster:\n    def __init__(self, n):\n        self.n = n\n        self.match = [0] * n\n    def commit_index(self):\n        replicas = sorted(self.match, reverse=True)\n        return replicas[self.n // 2]\n    def writable(self, alive):\n        return alive &gt; self.n // 2\n\nc = Cluster(5)\nprint(&#39;quorum&#39;, 5 // 2 + 1)\nprint(&#39;commit_initial&#39;, c.commit_index())\nc.match = [5, 4, 3, 0, 0]\nprint(&#39;commit_after_replication&#39;, c.commit_index())\nprint(&#39;alive3_writable&#39;, c.writable(3))\nprint(&#39;alive2_writable&#39;, c.writable(2))", "note": "Leader 选举、任期与日志复制的多数派"}, {"label": "对照 / 进阶", "code": "import time\n\nclass Lease:\n    def __init__(self, ttl):\n        self.ttl = ttl\n        self.expire = time.monotonic() + ttl\n    def valid(self, now):\n        return now &lt; self.expire\n    def renew(self, now):\n        self.expire = now + self.ttl\n\nl = Lease(10)\nt0 = time.monotonic()\nprint(&#39;valid_now&#39;, l.valid(t0))\nprint(&#39;valid_later&#39;, l.valid(t0 + 11))\nl.renew(t0 + 11)\nprint(&#39;valid_after_renew&#39;, l.valid(t0 + 12))", "note": "成员变更、etcd 定位与租约维持的注册"}]' title='两种写法切换看' />


## 健康检查、配置推送与灰度回滚

服务发现的健康检查分两层：注册中心侧（租约到期、TTL、主动 `HTTP` / TCP 探活）与客户端侧（调用失败率、熔断、本地缓存）。不能把健康判断全压给注册中心：网络分区时中心看到的可用，与调用方实际能连通未必一致，因此调用方要保留本地缓存与失败摘除，并在注册中心不可用时用上次快照降级。

配置推送用 `Watch` 监听键变更，避免轮询；变更要可灰度、可回滚、可审计：给配置带版本号，先对少量实例下发，观察核心指标后再全量，出问题直接切回上一版本，同时记录谁在何时改了哪个键。配置读取要有本地缓存与解析失败的兜底（保留上一个有效值），否则一次格式错误的推送会让所有实例同时崩掉。

监控要看 Raft 的 commit 延迟、leader 切换次数、租约续约失败率与 Watch 断连重连次数，而不是只看注册中心进程是否存活。

**etcd / Consul 定位与机制**

| 组件 | 一致性协议 | 成员探测 | 典型用途 |
| --- | --- | --- | --- |
| etcd | Raft | 租约 KeepAlive 与 Watch | K8s 元数据存储、分布式锁、服务注册 |
| Consul | Raft 存目录 | gossip 做成员与故障探测 | 服务发现、健康检查、KV 配置 |
| ZooKeeper | Zab | 临时节点 + session | 旧一代选主与配置（本讲对照） |


## 把配置中心当业务数据库每次请求都读写

<Callout type="warn" title='本讲最容易踩的坑' text='把配置中心当业务数据库每次请求都读写：每次写都要走 Raft 日志复制与多数派落盘，吞吐受限，leader 切换时全部依赖方一起超时' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把配置中心当业务数据库每次请求都读写", "body": "每次写都要走 Raft 日志复制与多数派落盘，吞吐受限，leader 切换时全部依赖方一起超时", "tip": "配置用 Watch 推送加本地缓存，业务数据留在各自存储，中心只放成员、租约、配置版本等强一致元数据"}, {"title": "第 2 步：服务注册写一条永久记录，不续约也不下线", "body": "实例被 SIGKILL 或整机掉电后来不及注销，注册表长期残留死地址，流量持续打过去", "tip": "注册时申请带 TTL 的租约并周期 KeepAlive，崩溃后租约到期自动删除，调用方再加本地失败摘除"}, {"title": "第 3 步：4 节点 Raft 集群期望能容忍 2 节点…", "body": "4 节点 quorum 仍是 3，只容忍 1 节点故障，偶数规模不提升容错还多付一次复制", "tip": "生产用奇数节点（3 或 5）；成员变更走受控的 joint consensus 或单节点逐步变更，避免双多数派"}]' />

**注册中心常见误用与失效信号**

| 现象 | 根因 | 可观测信号 |
| --- | --- | --- |
| 网络抖动后流量打到死实例 | 只依赖中心侧健康检查，无客户端摘除 | 调用失败率与中心健康列表不一致 |
| Raft 写入延迟飙升 | 把配置中心当业务数据库高频读写 | commit 延迟、raft 日志落盘耗时 |
| 实例崩溃后记录长期残留 | 注册时未绑定带 TTL 的租约 | 租约到期删除数、KeepAlive 失败率 |
| 一次配置推送打垮全部实例 | 无本地缓存、无灰度、无解析兜底 | Watch 重连数、配置解析错误计数 |


## 基于租约与多数派判定的服务注册表

把共识组件该承担的和该下沉的拆开：中心侧只维护带 TTL 的租约与一个多数派写入门禁，调用方保留本地缓存与失败摘除。

下面这段用标准库模拟最小注册表：`register` 绑定租约，`renew` 续约，`expire` 清理过期实例，`write_config` 先检查存活节点是否构成多数派再接受变更，客户端 `list_alive` 同时参考中心列表与本地失败计数。

真实实现里租约由 etcd 的 `Lease` 提供，多数派由 Raft 保证，本例用字典与计数把两个约束显式化，便于断言行为。重点是任何一次配置写入都有 quorum 校验，任何一次读取都有本地降级路径。

```python
import time

class Registry:
    def __init__(self, quorum):
        self.quorum = quorum
        self.leases = {}
        self.version = 0
    def register(self, name, ttl, now):
        self.leases[name] = now + ttl
    def renew(self, name, ttl, now):
        if name in self.leases:
            self.leases[name] = now + ttl
    def expire(self, now):
        dead = [k for k, v in self.leases.items() if v <= now]
        for k in dead:
            del self.leases[k]
        return dead
    def alive(self, now):
        return [k for k, v in self.leases.items() if v > now]
    def write_config(self, alive_count):
        if alive_count < self.quorum:
            return 'reject-no-quorum'
        self.version += 1
        return 'v' + str(self.version)

r = Registry(3)
t = time.monotonic()
for n in ('a', 'b', 'c', 'd', 'e'):
    r.register(n, 30, t)
print(r.write_config(len(r.alive(t))))
print(r.write_config(2))
print('expired', r.expire(t + 31))
```

<Callout type="idea" title='落地提示' text='关键元数据放 etcd 并用租约维持，业务数据留在各自存储；配置变更要可灰度、可回滚、可审计' />

<CheckList id='P109b' title='上线前自检' :items='["能复现并解释「把配置中心当业务数据库每次请求都读写」", "能复现并解释「服务注册写一条永久记录，不续约也不下线」", "能复现并解释「4 节点 Raft 集群期望能容忍 2 节点故障」", "能用一条命令验证 Leader 选举与日志复制", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 Leader 选举与日志复制 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把配置中心当业务数据库每次请求都读写 | 每次写都要走 Raft 日志复制与多数派落盘，吞吐受限，leader 切换时全部依赖方一起超时 | 配置用 Watch 推送加本地缓存，业务数据留在各自存储，中心只放成员、租约、配置版本等强一致元数据 |
| 服务注册写一条永久记录，不续约也不下线 | 实例被 SIGKILL 或整机掉电后来不及注销，注册表长期残留死地址，流量持续打过去 | 注册时申请带 TTL 的租约并周期 KeepAlive，崩溃后租约到期自动删除，调用方再加本地失败摘除 |
| 4 节点 Raft 集群期望能容忍 2 节点故障 | 4 节点 quorum 仍是 3，只容忍 1 节点故障，偶数规模不提升容错还多付一次复制 | 生产用奇数节点（3 或 5）；成员变更走受控的 joint consensus 或单节点逐步变更，避免双多数派 |


## 多数派交集与 Leader Completeness 的证明

Raft 的安全性不靠「leader 不会出错」，而靠两条可证明的不变量。第一条是多数派交集：任意两个多数派 A、B 都在 N 个节点里，|A| 与 |B| 都至少 `floor(N/2)`+1，于是 |A|+|B| 不小于 N+2，严格大于 N，故 A 与 B 交集非空。

一条日志被标记 committed 意味着它已存于某个多数派；此后任何新 leader 必须拿到另一个多数派的选票，两个多数派至少共享一个节点，该节点持有这条已提交日志。

第二条是选举限制（Leader Completeness）：candidate 在 RequestVote 里带最后一条日志的(lastLogTerm, lastLogIndex)，follower 只在「候选人日志至少和自己一样新」时投票，比较式是 lastLogTerm 大者更新、term 相同则 lastLogIndex 大者更新。

共享节点同时持有已提交条目且日志前缀连续，于是新 leader 必然包含所有已提交条目——这就是「已提交日志不会被覆盖」的完整证明链。跳过选举限制，日志落后的节点仍可能靠网络时序拿到多数票，上任后用短日志覆盖已提交条目，状态机安全性立刻破功。

推论有三：commitIndex 只推进当前 term 的条目、leader 不能靠数副本直接提交前任任期的日志、成员变更必须走 joint consensus 让新旧配置多数派在过渡期同时生效。

源码路径（etcd 3.5/3.6）：raft/`raft.go` 的 Step 与 becomeCandidate、raft/`log.go` 的 commitTo、raft/`rawnode.go` 的 Advance。

<ConceptDiagram type='flow4' title='第 109 讲 · 扩展图解' labels='A 与 B 的票数之和大于 N|A 与 B 交集非空|共享节点持已提交条目|isUpToDate 过滤落后候选' caption='多数派交集与选举限制共同保证新 leader 必含全部已提交条目，缺一不可' />


### RequestVote 里 isUpToDate 的比较式

把 isUpToDate 写成可核对的谓词：`upToDate(cand, voter)` 成立当且仅当 `cand.lastTerm` > `voter.lastTerm`，或两者 lastTerm 相等且 `cand.lastIndex` 不小于 `voter.lastIndex`。

etcd 的 raft/`raft.go` 里对应函数先比 term、再比 index，返回 false 就拒绝投票并附当前 term；hashicorp/raft 的 `raft.go` 在 electSelf 之前做同样检查。这条规则解释两个常被忽略的现象。

其一，刚重启、日志落后的 follower 不会拖慢选举：它拿不到票也不会当选，但会投给日志最新的 candidate，集群恢复取决于「至少 `floor(N/2)`+1 个节点持有最新日志」而非全部节点。

其二，日志截断只发生在 follower 与 leader 冲突时：AppendEntries 带 prevLogIndex 与 prevLogTerm，不匹配就返回失败，leader 递减 nextIndex 重试直到找到一致前缀再删冲突条目——所以「已提交」与「已复制」必须严格区分，未提交条目被覆盖是预期行为。

参数上论文要求 broadcastTime 远小于 electionTimeout，后者远小于 `MTBF`；

etcd 默认 `heartbeat-interval=100ms`、`election-timeout=1000ms`，并把超时随机化到[election-timeout, 2·election-timeout)。

若 electionTimeout 小于一次跨机房广播往返，follower 会频繁误判 leader 失联、自增 term 触发重选，出现「term 飙升但无写入」的假活状态，监控必须同时看 term 变化率与 commit 延迟。

**Raft 五条安全性不变量与保证机制**

| 不变量 | 保证机制 | 被破坏后的后果 |
| --- | --- | --- |
| Election Safety | 每个 term 每个节点只投一票，term 单调递增 | 同一 term 出现两个 leader |
| Leader Append-Only | leader 只追加、不覆盖自身日志 | 已提交条目被改写 |
| Log Matching | prevLogIndex 与 prevLogTerm 检查加冲突截断 | 副本日志持续分叉 |
| Leader Completeness | 多数派交集加 isUpToDate 选举限制 | 新 leader 缺已提交条目 |
| State Machine Safety | 只在 commitIndex 之后 apply 到状态机 | 各节点执行出不同命令序列 |


## 随机化选举超时压制分裂投票的实测

```python
import random

def first_round_success(n, trials, jitter_ms, seed=5):
    rng = random.Random(seed)
    wins = 0
    for _ in range(trials):
        timeouts = [150 + (rng.uniform(0, jitter_ms) if jitter_ms else 0) for _ in range(n)]
        t1, t2 = sorted(timeouts)[:2]
        if t2 - t1 > 10:
            wins += 1
    return round(wins / trials, 3)

print('no_jitter', first_round_success(5, 2000, 0))
print('jitter_100ms', first_round_success(5, 2000, 100))
print('jitter_300ms', first_round_success(5, 2000, 300))
```

<OutputBox title='扩展示例运行结果' output='no_jitter 0.0\njitter_100ms 0.59\njitter_300ms 0.845' />

<LineByLine code='import random\n\ndef first_round_success(n, trials, jitter_ms, seed=5):\n    rng = random.Random(seed)\n    wins = 0\n    for _ in range(trials):\n        timeouts = [150 + (rng.uniform(0, jitter_ms) if jitter_ms else 0) for _ in range(n)]\n        t1, t2 = sorted(timeouts)[:2]\n        if t2 - t1 &gt; 10:\n            wins += 1\n    return round(wins / trials, 3)\n\nprint(&#39;no_jitter&#39;, first_round_success(5, 2000, 0))\nprint(&#39;jitter_100ms&#39;, first_round_success(5, 2000, 100))\nprint(&#39;jitter_300ms&#39;, first_round_success(5, 2000, 300))' :notes='["固定种子保证分裂投票概率可复现", "空行，只用于分隔逻辑块，不影响执行结果。", "jitter=0 表示所有节点选举超时相同，必然同时发起投票", "取最早与次早超时之差，差值超过 10ms 广播延迟才算唯一 candidate 拿到多数票", "这一行 `wins = 0` 的作用，可对照上方输出逐项核对。", "这一行 `for _ in range(trials):` 的作用，可对照上方输出逐项核对。", "这一行 `timeouts = [150 + (rng.uniform(0, jitter_ms) if jitt` 的作用，可对照上方输出逐项核对。", "这一行 `t1, t2 = sorted(timeouts)[:2]` 的作用，可对照上方输出逐项核对。", "这一行 `if t2 - t1 &gt; 10:` 的作用，可对照上方输出逐项核对。", "这一行 `wins += 1` 的作用，可对照上方输出逐项核对。", "这一行 `return round(wins / trials, 3)` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `print(&#39;no_jitter&#39;, first_round_success(5, 2000, 0))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;jitter_100ms&#39;, first_round_success(5, 2000, 1` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;jitter_300ms&#39;, first_round_success(5, 2000, 3` 的作用，可对照上方输出逐项核对。"]' title='扩展示例逐行讲解' />

<Quiz no='109-1' q='5 节点 Raft 集群里，为什么两个不同任期产生的多数派一定包含同一条已提交日志？' :options='["两个多数派必有交集，共享节点持有已提交条目，且 isUpToDate 保证它只投给日志不比自己旧的 candidate", "因为所有节点使用完全相同的 election timeout", "因为 leader 会把日志广播给全部 5 个节点之后才提交", "因为 term 单调递增会自动回滚掉旧任期的日志"]' answer="0" explain='多数派交集给出共享节点，选举限制给出「新 leader 日志不旧于投票者」，两者合起来才是 Leader Completeness；单靠 term 或全副本广播都不够，提交只需多数派确认。' />


## 线性一致读：ReadIndex 与租约读的边界

一个 3 节点 etcd 集群被网络分成 2+1 两半，业务侧把读请求发给少数派那台旧 leader，它仍认为自己是 leader、本地状态机也有数据，于是直接返回旧值；与此同时多数派侧已选出新 leader 并写入新配置，同一个 key 在两个客户端读到不同版本。

根因是把「能从 leader 读到」当成线性一致：Raft 只对「经多数派确认的日志复制」保证顺序，旧 leader 在孤立分区里若不做额外检查，完全可能用过期状态机响应只读请求。

修复有三条：读也走 ReadIndex（leader 先向多数派发心跳确认自己仍是 leader，再等状态机 apply 到该 readIndex 才返回）、启用 lease read（依赖时钟界限，NTP 漂移要慎用）、或把只读请求也当日志条目复制一遍。下面模拟分区下旧 leader 的直接读与 ReadIndex 读。

```python
class Partition:
    def __init__(self):
        self.log = ['v1']
        self.term = 1
        self.side = 'minority'
    def write_majority(self, value):
        if self.side == 'majority':
            self.log.append(value)
    def stale_read(self):
        return self.log[-1]
    def read_index(self, majority_confirms):
        if not majority_confirms:
            return 'reject: not leader anymore'
        return self.log[-1]

p = Partition()
p.side = 'majority'
p.write_majority('v2')
print('majority_log', p.log[-1])
old = Partition()
print('old_leader_stale_read', old.stale_read())
print('old_leader_read_index', old.read_index(False))
```


## 两道梯度练习与选择题

<Exercise title='基础：计算不同规模集群的 quorum 与容错' task='写出函数 quorum(n) 与 tolerate(n)，对 n 取 3 到 7 打印结果，并解释为什么 4 节点与 3 节点容错相同。' solution='def quorum(n):\n    return n // 2 + 1\ndef tolerate(n):\n    return quorum(n) - 1\nfor n in range(3, 8):\n    print(n, quorum(n), tolerate(n))' explain='quorum 是 n//2+1，可容忍故障数为 quorum-1。4 节点 quorum=3、容错 1，与 3 节点相同，偶数规模多一台机器却不增加容错。' />

<Exercise title='进阶：实现任期单调递增与过期写入拒绝' task='给一个 Term 状态机加 step(t)，要求拒绝小于当前任期的写入并打印被拒次数，用序列 2,5,3,6 验证旧任期请求被隔离。' solution='class Term:\n    def __init__(self):\n        self.current = 0\n        self.rejected = 0\n    def step(self, t):\n        if t &lt; self.current:\n            self.rejected += 1\n            return False\n        self.current = t\n        return True\nr = Term()\nfor t in (2, 5, 3, 6):\n    r.step(t)\nprint(r.current, r.rejected)' explain='任期只增不减，序列里 3 小于当前 5 被拒绝，final term 为 6、rejected 为 1。旧 leader 携带过期 term 的请求会被接收方拒绝并促其退位。' />

<Quiz no='109-2' q='5 节点 Raft 集群的 quorum 与可容忍故障数分别是？' :options='["quorum 3，容忍 2 节点故障", "quorum 5，容忍 0 节点故障", "quorum 2，容忍 3 节点故障", "quorum 3，容忍 3 节点故障"]' answer="0" explain='quorum = 5//2+1 = 3，只要存活达到 3 就能提交；可容忍故障为 N - quorum = 2。' />

<Quiz no='109-3' q='关于 etcd 中的服务注册，最稳妥的做法是？' :options='["申请带 TTL 的租约并周期 KeepAlive，崩溃后自动过期删除", "写一条永久键， shutdown 时主动删除", "每次请求都重写一次键刷新存活", "把实例列表存进配置中心由业务轮询更新"]' answer="0" explain='进程可能被 SIGKILL 或掉电，来不及主动注销；租约到期由中心删除键，比主动注销可靠，也不需要每次请求都写 Raft。' />

<Quiz no='109-4' q='网络分区时，为什么不能把健康判断全交给注册中心？' :options='["中心看到的可用与调用方实际能连通未必一致，调用方需本地缓存与失败摘除", "注册中心在任何分区下都能精确判断", "调用方本地缓存会破坏强一致，必须禁用", "健康检查只能由 leader 执行"]' answer="0" explain='分区时中心与调用方视角可能相反，因此调用侧要保留快照降级与失败摘除；把全部责任压给中心会放大故障影响面。' />

<FillBlank no='109-5' tpl='___ __init__(self, n):' :answers='["def"]' hint='回想本讲关于 Leader 选举与日志复制 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Leader 选举、任期与日志复制的多数派 的落点。' />

<Predict no='109-6' q='matchIndex 为 [5,4,3,0,0] 的 5 节点集群，commitIndex 是多少？' :options='["3，即多数派都达到的最大索引", "5，leader 的最大索引", "0，存在落后节点就不能提交"]' answer='0' output='3' explain='把 matchIndex 降序得 [5,4,3,0,0]，第 quorum 个（索引 2）是 3，表示至少 3 台复制到了索引 3，只有这部分日志可提交；两节点落后不影响多数派决策。' />

<KnowledgeCard :points='["Raft 拆成 Leader 选举、日志复制、安全性三题；`term` 单调递增，`floor(N/2)+1` 为多数派", "5 节点容忍 2 故障、4 节点只容忍 1，生产用奇数节点；收到多数派确认才推进 `commitIndex`", "选举限制保证新 leader 含全部已提交条目；只提交当前任期条目，前任期条目被间接提交", "成员变更走 joint consensus / 单节点逐步过渡，etcd 用 `ConfChange`；每次写都要复制落盘，Raft 只适合少量元数据", "服务注册用 `Lease` + `KeepAlive` 而非永久记录，崩溃即停续约、TTL 到期删键，比主动注销可靠", "健康检查分中心侧与客户端侧两层；配置用 `Watch` 推送、带版本可灰度可回滚，读取保留本地缓存与旧值兜底"]' :pitfalls='["把配置中心当业务数据库每次请求都读写", "服务注册写一条永久记录，不续约也不下线", "4 节点 Raft 集群期望能容忍 2 节点故障", "把配置中心当数据库频繁读写，或让服务发现承担健康判断的全部责任，都会在故障时放大影响"]' summary='共识算法解决的是「多台机器对同一序列达成一致」，因此它昂贵且只在少量关键状态上使用，不用来承载业务数据' />

1. Raft 拆成 Leader 选举、日志复制、安全性三题；`term` 单调递增，`floor(N/2)+1` 为多数派

2. 5 节点容忍 2 故障、4 节点只容忍 1，生产用奇数节点；收到多数派确认才推进 `commitIndex`

3. 选举限制保证新 leader 含全部已提交条目；只提交当前任期条目，前任期条目被间接提交

[下一讲：容器化与 Kubernetes 部署](/distributed/docker-k8s)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/109-consensus.py`

```bash
python3 examples/lessons/109-consensus.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/109-consensus.py) · [全部示例代码索引](/examples/)
