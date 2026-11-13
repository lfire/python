---
title: 第 105 讲 · CAP / BASE 与一致性模型
description: 能说清一次写入之后别人能看到什么
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★☆' time='40 分钟' goal='能说清一次写入之后别人能看到什么' prereq='第 104 讲 · LLM 应用工程：Prompt、RAG、Agent 与成本' />

# 第 105 讲 · CAP / BASE 与一致性模型

阶段九走到末尾，一个能回答问题的应用跑起来了。一旦铺到多台机器、读写分给副本，会冒出单机时代没有的问题：用户刚付完款，刷新却查不到订单，说一句『最终一致，正常』含糊不过去。本讲是分布式阶段的开头，先说清一致性承诺了什么。

先把 CAP 的正确表述摆正——它约束分区时的取舍，不是平时二选一——再铺开强一致与最终一致的谱系；接着谈读写一致性、BASE 与补偿，把收敛时间窗写进 SLA；最后看版本与向量时钟怎样识别并发写、冲突怎么解。需要函数、字典、异常处理，以及前面 HTTP 与接口的调用边界。学完你能按操作定级：支付扣款走强一致，评论点赞走最终一致。


## 支付成功后列表里查不到刚下的单

用户支付成功、页面也提示扣款完成，跳到订单列表却显示「暂无订单」，客服当天被同类工单淹没。排查发现服务写主库、列表读从库，主从异步复制有几十到几百毫秒延迟，写完后立刻读从库自然读不到。团队辩解「我们用的是最终一致，这是正常的」——把最终一致当成了「一致性不用管」，既没定义收敛窗口，也没给用户做读己之写。

另一场评审里，有人用 CAP 否决了所有强一致方案，理由是「CAP 说一致性和可用性只能选一个」；这其实是对定理的误读：CAP 约束的是网络分区发生时的取舍，没有分区时正常系统可以同时满足两者。本讲把「一次写入之后别人能看到什么」拆成可定义、可模拟、可写进 SLA 的具体等级。

<Callout type="warn" title='先看一个真实会出错的写法' text='支付成功后列表读不到刚下的单，还称「最终一致正常」：写主读从、异步复制有延迟，且没实现读己之写，也没定义收敛窗口' />


## CAP 的正确表述：只在分区时取舍

CAP 定理说的是：一个分布式系统无法同时保证 Consistency、Availability、Partition tolerance 三者。这里的 C 指线性一致性（linearizability，每次读都能读到最近一次已完成写的结果，等价于所有操作看起来像在单副本上按某个全局顺序原子执行），不是 ACID 里的 C；

A 指每个对非故障节点的请求都能在有限时间内返回（不保证是最新值）；P 指网络分区（节点间消息丢失或延迟）时系统仍能继续运行。

由于物理网络里分区不可避免，P 是前提而不是可选项，真正的取舍只发生在分区期间：选 CP 就拒绝那些无法保证一致读写的请求（如基于 Raft 的 etcd、ZooKeeper、HBase 多数派），牺牲分区内可用性换强一致；

选 AP 就继续接受读写、但可能返回旧值或产生冲突（如 Cassandra、Dynamo、Eureka），靠事后收敛。关键澄清是「没有分区时，系统可以同时做到 C 与 A」——单主同步复制在正常网络下读主库即可线性一致且可用。因此 CAP 不是「平时二选一」的许可证，而是「分区发生时怎么办」的应急预案。

工程上更常用细粒度权衡：按操作定义一致性等级，支付与扣款强一致、商品评论与点赞可接受最终一致，并明确各自的收敛窗口。

**一致性等级对照（按操作定义）**

| 等级 | 保证 | 实现方式 | 典型场景 |
| --- | --- | --- | --- |
| 线性一致 | 读必见最近写，全局单副本序 | 多数派 / 读主库 | 支付、库存扣减 |
| 因果一致 | 有因果的操作顺序一致 | 向量时钟 / 依赖跟踪 | 评论回复链 |
| 读己之写 | 自己写入后自己能读到 | 会话版本号 / 写后读主 | 订单列表、个人资料 |
| 单调读 | 不会读到比之前更旧的值 | 会话粘滞到同一副本 | 翻页浏览 |
| 最终一致 | 无新写时副本终将收敛 | 异步复制 + 反熵 | 点赞、浏览量 |

<Callout type="tip" title='核心心智模型' text='CAP 定理说的是：一个分布式系统无法同时保证 Consistency、Availability、Partition tolerance 三者。这里的 C 指线性一致性（linearizability，每次读都能读到最近一次已完成写的结果，等价于所有操作看起来像在单副本上按某个全局顺序原子执行），不' />


## 一致性谱系、BASE 与收敛窗口

最终一致只承诺「如果没有新写入，副本终将收敛到同一值」，但没承诺多久、也没承诺某个用户立刻能看到自己刚写的东西。

于是需要一组以客户端会话为作用域的一致性保证：读己之写（read-your-writes，用户写入后自己随后的读一定能看到，常用写后读主库、或给请求带会话版本号、从库版本不足就回退主库）、单调读（用户一旦读到某版本，后续不会读到更旧版本，常靠把会话粘滞到同一副本）、单调写、因果一致（有因果关系的操作对所有节点顺序一致）、以及最强的线性一致。

BASE 是对 ACID 的放宽：Basically Available（基本可用，故障时允许降级响应）、Soft state（软状态，允许副本间存在中间态）、Eventually consistent（最终一致），它用「接受一个不一致窗口 + 补偿路径」换可用性与吞吐。

窗口必须写成可量化指标并进 SLA：主从复制延迟的 P99、最大不一致时长、以及超过窗口后的补偿（对账、重试、消息补发、人工兜底）。「支付后立即查不到订单」之所以是事故，不是因为最终一致错了，而是因为没定义读己之写策略，也没把收敛时间写进业务可接受范围。

```python
replicas = {'R1': (0, 0), 'R2': (0, 0), 'R3': (0, 0)}
def write(val, version):
    replicas['R1'] = (version, val)
def replicate(targets):
    for t in targets:
        replicas[t] = replicas['R1']
def read(rid):
    return replicas[rid]
write('订单A', 1)
print('read R1 (primary)', read('R1'))
print('read R2 (before replication)', read('R2'))
replicate(['R2', 'R3'])
print('read R2 (after)', read('R2'))
```

<OutputBox title='主示例运行结果' output='read R1 (primary) (1, &#39;订单A&#39;)\nread R2 (before replication) (0, 0)\nread R2 (after) (1, &#39;订单A&#39;)' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='replicas = {&#39;R1&#39;: (0, 0), &#39;R2&#39;: (0, 0), &#39;R3&#39;: (0, 0)}\ndef write(val, version):\n    replicas[&#39;R1&#39;] = (version, val)\ndef replicate(targets):\n    for t in targets:\n        replicas[t] = replicas[&#39;R1&#39;]\ndef read(rid):\n    return replicas[rid]\nwrite(&#39;订单A&#39;, 1)\nprint(&#39;read R1 (primary)&#39;, read(&#39;R1&#39;))\nprint(&#39;read R2 (before replication)&#39;, read(&#39;R2&#39;))\nreplicate([&#39;R2&#39;, &#39;R3&#39;])\nprint(&#39;read R2 (after)&#39;, read(&#39;R2&#39;))' :notes='["三个副本，各存 (版本号, 值)，初始版本 0、值为占位 0", "写操作先落到主副本 R1，模拟单主写入", "主副本记录新版本与值，版本号用于判断新旧", "异步复制函数，把主副本状态推送到指定副本", "逐一遍历目标副本", "每个副本被更新为主副本当前的 (版本, 值)", "读函数按副本 id 取出其 (版本, 值)", "返回该副本的完整状态，便于比较版本差异", "模拟一次成功支付，主副本版本升到 1", "写后立刻读主副本：能看到刚写入的订单，版本为 1", "写后立刻读从副本 R2：复制尚未发生，仍是旧值 (0, 0)", "触发异步复制到 R2 与 R3", "复制完成后再读 R2：已收敛到版本 1 的订单A"]' title='第 105 讲 · CAP / BASE 与一致性模型' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**分区期间的 CAP 抉择**

| 选择 | 分区时行为 | 代表系统 | 代价 |
| --- | --- | --- | --- |
| CP | 拒绝无法保证一致的读写 | etcd / ZooKeeper / HBase | 分区内不可用 |
| AP | 继续服务，可能返回旧值 | Cassandra / Dynamo / Eureka | 需冲突合并与补偿 |
| 无分区时 | 可同时满足 C 与 A | 同步复制的单主 | 受网络延迟约束 |

<ConceptDiagram type='layers3' title='第 105 讲 · 分层视角' labels='CAP 的正确表述与一致性谱系|读写一致性、BASE 与业务窗口|版本、向量时钟与冲突解决|业务可接受窗口' caption='版本、向量时钟与冲突解决' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **业务可接受窗口** 落在哪一层。


## 版本、向量时钟与并发写冲突

多主或无主架构里，分区期间两个副本可能各自接受对同一 key 的写，恢复后需要判断这两次写是「有先后」还是「并发」。Lamport 逻辑时钟给事件一个偏序编号，但无法区分并发；向量时钟给每个节点一个计数器向量，规则是：本地事件把自己的分量加一，发消息时附带整个向量，收消息时对每个分量取 max 再把自己的分量加一。

比较两个向量：若 a 的各分量都大于等于 b 且至少一个严格大于，则 b 因果上早于 a，可用 a 覆盖；若 a 有分量比 b 大、b 也有分量比 a 大，则两次写并发，存在冲突，不能简单覆盖。本讲 alt 里 va=&#123;'A':2,'B':1&#125; 与 vb=&#123;'A':1,'B':2&#125; 各有一维更大，因此判定并发。

冲突解决有几种策略：Last-Write-Wins 用时间戳取最新（实现简单，但时钟漂移会丢写，且物理时钟不可靠）、merge 取各分量 max 得到合并向量、CRDT（满足交换律/结合律/幂等的数据结构，副本自动收敛无需协调）、业务自定义合并、或把冲突保留成兄弟值交给应用层/用户选择（Dynamo 的 siblings、购物车的并集）。

版本号还支撑乐观锁：更新时带上读到的版本，版本不匹配就重试（CAS）。选哪种取决于业务能否容忍丢失——计数、金额类绝不能用 LWW 悄悄丢写。

```python
def merge(a, b):
    return {k: max(a.get(k, 0), b.get(k, 0)) for k in sorted(set(a) | set(b))}
def concurrent(a, b):
    keys = set(a) | set(b)
    a_ge = all(a.get(k, 0) >= b.get(k, 0) for k in keys)
    b_ge = all(b.get(k, 0) >= a.get(k, 0) for k in keys)
    return not (a_ge or b_ge)
va = {'A': 2, 'B': 1}
vb = {'A': 1, 'B': 2}
print('concurrent?', concurrent(va, vb))
print('merged', merge(va, vb))
vc = {'A': 3, 'B': 2}
print('vc dominates va?', not concurrent(va, vc))
```

<OutputBox title='对照写法：先自己猜，再点开' output='concurrent? True\nmerged {&#39;A&#39;: 2, &#39;B&#39;: 2}\nvc dominates va? True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "replicas = {&#39;R1&#39;: (0, 0), &#39;R2&#39;: (0, 0), &#39;R3&#39;: (0, 0)}\ndef write(val, version):\n    replicas[&#39;R1&#39;] = (version, val)\ndef replicate(targets):\n    for t in targets:\n        replicas[t] = replicas[&#39;R1&#39;]\ndef read(rid):\n    return replicas[rid]\nwrite(&#39;订单A&#39;, 1)\nprint(&#39;read R1 (primary)&#39;, read(&#39;R1&#39;))\nprint(&#39;read R2 (before replication)&#39;, read(&#39;R2&#39;))\nreplicate([&#39;R2&#39;, &#39;R3&#39;])\nprint(&#39;read R2 (after)&#39;, read(&#39;R2&#39;))", "note": "CAP 的正确表述与一致性谱系"}, {"label": "对照 / 进阶", "code": "def merge(a, b):\n    return {k: max(a.get(k, 0), b.get(k, 0)) for k in sorted(set(a) | set(b))}\ndef concurrent(a, b):\n    keys = set(a) | set(b)\n    a_ge = all(a.get(k, 0) &gt;= b.get(k, 0) for k in keys)\n    b_ge = all(b.get(k, 0) &gt;= a.get(k, 0) for k in keys)\n    return not (a_ge or b_ge)\nva = {&#39;A&#39;: 2, &#39;B&#39;: 1}\nvb = {&#39;A&#39;: 1, &#39;B&#39;: 2}\nprint(&#39;concurrent?&#39;, concurrent(va, vb))\nprint(&#39;merged&#39;, merge(va, vb))\nvc = {&#39;A&#39;: 3, &#39;B&#39;: 2}\nprint(&#39;vc dominates va?&#39;, not concurrent(va, vc))", "note": "读写一致性、BASE 与业务窗口"}]' title='两种写法切换看' />


## LWW 时间戳与时钟漂移为什么会丢写

CAP 的不可兼得可用一个两节点反证说明：设网络分区把节点分成 A、B 两组且互不能通信，客户端先向 A 写 `x=2`、再向 B 读 x。若系统要保 A（可用），B 必须在有限时间内返回，但它无法知道 A 已经写过，只能返回旧值 1，于是违反线性一致；若要保 C（一致），B 必须拒绝或阻塞这个读，于是违反可用性。

因此 P 发生时 C 与 A 只能取其一，且这一结论只在分区窗口内成立。线性一致性要求所有操作可排成一个与实时顺序一致的全局全序，等价于「读必见最近已完成写」，实现上靠多数派 quorum（W + R > N）或单主读主。

向量时钟把「 happened-before 」偏序编码成向量：a 因果晚于 b 当且仅当 a 各分量 ≥ b 且至少一项严格大；互有大小则并发，必须层冲突。最终一致的收敛依赖异步复制、反熵（Merkle 树比对）与读修复，BASE 正是用「软状态 + 可接受窗口 + 补偿」把强一致的协调成本换成可用性与吞吐。

```python
zone_a = {'x': 1}
zone_b = {'x': 1}
zone_a['x'] = 2
zone_b['x'] = 3
print('after partition: A', zone_a['x'], 'B', zone_b['x'])
print('diverged?', zone_a['x'] != zone_b['x'])
print('CP choice: reject B write -> A,B stay', 2, 2)
```

<OutputBox title='原理验证' output='after partition: A 2 B 3\ndiverged? True\nCP choice: reject B write -&gt; A,B stay 2 2' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 支付成功后列表读不到刚下的单，还称「最终一致正常」 | 写主读从、异步复制有延迟，且没实现读己之写，也没定义收敛窗口 | 实现读己之写：写后读主库或带会话版本号回退主库；把复制延迟 P99 与补偿路径写进 SLA |
| 用 CAP 否决所有强一致方案，说「C 和 A 只能选一个」 | 把 CAP 误读成平时二选一；它约束的是分区发生时的取舍，无分区时可同时满足 C 与 A | 按操作定义一致性等级：支付/扣款强一致、评论/点赞最终一致，分区预案分别设计 |
| 多主冲突用 LWW 时间戳悄悄覆盖 | 物理时钟有漂移、NTP 跳变，Last-Write-Wins 会丢失一次真实写入且不可察觉 | 用向量时钟或版本向量检测并发，按业务选择 CRDT、合并或保留兄弟值；金额类禁止 LWW 覆盖 |

<Callout type="warn" title='本讲最容易踩的坑' text='支付成功后列表读不到刚下的单，还称「最终一致正常」：写主读从、异步复制有延迟，且没实现读己之写，也没定义收敛窗口' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：支付成功后列表读不到刚下的单，还称「最终一致", "body": "写主读从、异步复制有延迟，且没实现读己之写，也没定义收敛窗口", "tip": "实现读己之写：写后读主库或带会话版本号回退主库；把复制延迟 P99 与补偿路径写进 SLA"}, {"title": "第 2 步：用 CAP 否决所有强一致方案，说「C 和 ", "body": "把 CAP 误读成平时二选一；它约束的是分区发生时的取舍，无分区时可同时满足 C 与 A", "tip": "按操作定义一致性等级：支付/扣款强一致、评论/点赞最终一致，分区预案分别设计"}, {"title": "第 3 步：多主冲突用 LWW 时间戳悄悄覆盖", "body": "物理时钟有漂移、NTP 跳变，Last-Write-Wins 会丢失一次真实写入且不可察觉", "tip": "用向量时钟或版本向量检测并发，按业务选择 CRDT、合并或保留兄弟值；金额类禁止 LWW 覆盖"}]' />


## 读己之写：用会话版本号兜住异步复制延迟

「用户支付后立刻能看到订单」是会话级一致性，不需要把所有读都强一致地压到主库。可复用的做法是：写入成功后把该次版本号记入会话，读从库时先比对自己副本的版本，低于会话版本就回退读主库（或等待该副本追上），这样既保住读己之写，又把绝大部分读留在从库。

下面用纯标准库把这条策略写成一个自洽模块：write 升版本、replicate 模拟异步复制、read 带 min_version 参数在从库落后时回退主库，并打印三种时机的读结果。

真实项目把版本号换成复制位点/GTID 或会话 token，把 read 换成带 sticky 的数据库连接路由，结构不变——关键是会话版本随写更新、读侧有明确的回退出口。

```python
replicas = {'primary': (0, None), 'replica': (0, None)}
session_version = 0
def write(val):
    global session_version
    session_version += 1
    replicas['primary'] = (session_version, val)
def replicate():
    replicas['replica'] = replicas['primary']
def read(rid, min_version=0):
    ver, val = replicas[rid]
    if ver < min_version:
        ver, val = replicas['primary']
    return (ver, val)
write('订单A')
print('read replica(no sticky)', read('replica'))
print('read replica(read-your-writes)', read('replica', session_version))
replicate()
print('read replica(after replication)', read('replica', session_version))
```

<Callout type="idea" title='落地提示' text='按操作定义一致性等级，明确收敛时间窗、读己之写策略与补偿路径，并写进 SLA' />

<CheckList id='P105b' title='上线前自检' :items='["能复现并解释「支付成功后列表读不到刚下的单，还称「最终一致正常」」", "能复现并解释「用 CAP 否决所有强一致方案，说「C 和 A 只能选一个」」", "能复现并解释「多主冲突用 LWW 时间戳悄悄覆盖」", "能用一条命令验证 CAP 的正确表述", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

把输入换成你自己的数据，观察结果是否仍符合 **CAP 的正确表述** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 练习、自测与一致性速记

<Exercise title='基础：模拟异步复制下的读写窗口' task='用三个副本与版本号，打印「写主后读主 / 写主后读从 / 复制后读从」三处结果，说明哪个时机对应「用户查不到订单」的事故。' solution='r={&#39;R1&#39;:(0,0),&#39;R2&#39;:(0,0)}\nr[&#39;R1&#39;]=(1,&#39;订单A&#39;)\nprint(&#39;primary&#39;,r[&#39;R1&#39;])\nprint(&#39;replica before&#39;,r[&#39;R2&#39;])\nr[&#39;R2&#39;]=r[&#39;R1&#39;]\nprint(&#39;replica after&#39;,r[&#39;R2&#39;])' explain='「写主后读从」这一步从库仍是 (0,0)，对应用户支付后立即查不到订单；复制完成后从库才收敛到版本 1。' />

<Exercise title='进阶：用向量时钟判断并发写' task='实现 concurrent(a,b)，验证 va={&#39;A&#39;:2,&#39;B&#39;:1} 与 vb={&#39;A&#39;:1,&#39;B&#39;:2} 并发，而 vc={&#39;A&#39;:3,&#39;B&#39;:2} 因果晚于 va，并说明判据。' solution='def concurrent(a,b):\n    ks=set(a)|set(b)\n    age=all(a.get(k,0)&gt;=b.get(k,0) for k in ks)\n    bge=all(b.get(k,0)&gt;=a.get(k,0) for k in ks)\n    return not (age or bge)\nprint(concurrent({&#39;A&#39;:2,&#39;B&#39;:1},{&#39;A&#39;:1,&#39;B&#39;:2}))\nprint(concurrent({&#39;A&#39;:2,&#39;B&#39;:1},{&#39;A&#39;:3,&#39;B&#39;:2}))' explain='va 与 vb 互有分量更大，判为并发冲突；vc 各分量都 ≥ va 且至少一项更大，因果晚于 va 可覆盖。判据就是向量偏序。' />

<Quiz no='105-1' q='关于 CAP，下面哪项表述准确？' :options='["P 是前提，取舍发生在网络分区期间：CP 拒绝部分请求、AP 返回可能旧的值", "平时必须在 C 与 A 之间二选一", "三者可以同时完全满足", "C 指 ACID 里的一致性"]' answer="0" explain='网络分区不可避免，P 是前提；分区时保 C 就得拒绝无法一致的读写（CP），保 A 就得接受旧值（AP）。无分区时可同时满足 C 与 A，且 CAP 的 C 是线性一致性。' />

<Quiz no='105-2' q='用户支付后立即查不到订单，最贴切的修复是？' :options='["实现读己之写：写后读主或带会话版本号回退主库，并把收敛窗口写进 SLA", "把整个系统改成强一致", "关闭异步复制", "让用户刷新几次就好"]' answer="0" explain='这是会话级一致性问题，不必全局强一致：写后读主、会话版本号回退主库即可，同时要定义复制延迟 P99 与超过窗口的补偿路径。' />

<Quiz no='105-3' q='两个向量时钟 va={&#39;A&#39;:2,&#39;B&#39;:1}、vb={&#39;A&#39;:1,&#39;B&#39;:2}，关系应判定为？' :options='["并发写，存在冲突，不能简单覆盖", "vb 因果晚于 va", "va 因果晚于 vb", "完全相同"]' answer="0" explain='A 分量 va 更大、B 分量 vb 更大，互有大小即并发，恢复后必须走冲突合并（CRDT/业务合并/兄弟值），不能用 LWW 悄悄覆盖。' />

<Predict no='105-P' q='前面 code 里，写主副本后、复制发生前读 R2 会得到什么？' :options='["(0, 0)", "(1, &#39;订单A&#39;)", "抛异常"]' answer='0' output='read R2 (before replication) (0, 0)' explain='写只落到主副本 R1，异步复制尚未执行，R2 仍是初始的 (版本 0, 值 0)。这正是「支付成功却查不到订单」的复现：读从库落在不一致窗口里。' />

<KnowledgeCard :points='["CAP 的 C 是线性一致性、P 是前提；取舍只在网络分区期间发生，无分区时 C 与 A 可兼得", "CP 分区时拒绝无法一致的读写（etcd/ZK），AP 继续服务但返回旧值（Cassandra/Dynamo）", "最终一致不等于不管一致性：要用读己之写、单调读等会话级保证兜住复制延迟", "BASE = 基本可用 + 软状态 + 最终一致；收敛窗口 P99 与补偿路径要写进 SLA", "向量时钟按分量比较判定因果/并发：互有大小即并发冲突，需合并或保留兄弟值", "LWW 时间戳受时钟漂移会丢写；金额类用多数派/乐观锁，别悄悄覆盖"]' :pitfalls='["支付成功后列表读不到刚下的单，还称「最终一致正常」", "用 CAP 否决所有强一致方案，说「C 和 A 只能选一个」", "多主冲突用 LWW 时间戳悄悄覆盖", "把「最终一致」当成「不用管一致性」，用户支付后立即查不到订单，客服工单就会爆"]' summary='CAP 说的是网络分区发生时在可用性与一致性之间取舍，不是平时可以随便二选一；多数系统实际在做细粒度权衡' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| CAP 的 C 是线性一致性、P 是前提；取舍只在网络分区期间发生，无分区时 C 与 A 可兼得 | 建立直觉 |
| CP 分区时拒绝无法一致的读写（etcd/ZK），AP 继续服务但返回旧值（Cassandra/Dynamo） | 跑通示例 |
| 最终一致不等于不管一致性：要用读己之写、单调读等会话级保证兜住复制延迟 | 深入边界 |
| BASE = 基本可用 + 软状态 + 最终一致；收敛窗口 P99 与补偿路径要写进 SLA | 工程落地 |
| 向量时钟按分量比较判定因果/并发：互有大小即并发冲突，需合并或保留兄弟值 | 随堂检测 |
| LWW 时间戳受时钟漂移会丢写；金额类用多数派/乐观锁，别悄悄覆盖 | 复盘 |

1. CAP 的 C 是线性一致性、P 是前提；取舍只在网络分区期间发生，无分区时 C 与 A 可兼得

2. CP 分区时拒绝无法一致的读写（etcd/ZK），AP 继续服务但返回旧值（Cassandra/Dynamo）

3. 最终一致不等于不管一致性：要用读己之写、单调读等会话级保证兜住复制延迟

[下一讲：幂等、分布式锁与限流](/distributed/idempotency)

<FillBlank no='105-F' tpl='___ write(val, version):' :answers='["def"]' hint='回想本讲关于 CAP 的正确表述 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 CAP 的正确表述与一致性谱系 的落点。' />
