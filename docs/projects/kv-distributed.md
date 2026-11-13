---
title: 第 132 讲 · 实战 11 · 分片复制、AI 网关与能力收束
description: 完成贯穿线并连接后续成长路径
---

<StageHeader stage='L12 · 工程实战' level='★★★★★' time='60 分钟' goal='完成贯穿线并连接后续成长路径' prereq='第 131 讲 · 实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制' />

# 第 132 讲 · 实战 11 · 分片复制、AI 网关与能力收束

上一讲之后，KV 已扛得住重启；最后一讲让数据住进一组节点，再把网关接到另一种负载上，替四讲收尾。回望一路：先定接口、再框协议帧、然后靠 WAL 落盘，命令语义始终没变。

磁盘故障让分片数据永久没了：只切片、没留副本；把网关接到流式推理后添状况：一个供应商响应极慢，长连接不释放，连接池被拖空；另一个请求反复重试，单次吃掉整日预算。我们先从取模走到一致性哈希做分片与路由，再谈副本、quorum 与故障转移，然后给流式网关补超时与预算闸门，最后用四讲共用的用例确认语义没漂，把代价与回退记进复盘。需要你走完前三讲；学完能说清一份数据写几份、坏一台会怎样。


## 只做分片不做副本，节点一挂就是永久丢数据

贯穿线走到最后，单机 KV 已经能扛住重启，但一次磁盘故障让某个分片上的数据永久丢失——只做了分片、没做副本，节点一挂就是不可恢复的损失。把同样的网关能力接到 LLM 流式推理后又出新问题：一个模型供应商响应极慢，长连接一直挂着不释放，连接池被拖空；另一个请求在 Agent 循环里反复重试，单次吃掉整日 Token 预算。

只做分片不做副本、流式接口不设超时与预算上限，是这一讲要收束的两个典型失败。本讲把分片路由、副本 quorum、故障转移与流式网关的超时/成本闸门合成一个可运行骨架，并用契约测试锁住四讲演进中命令语义始终不变，最后把每个取舍的代价与回退方案写进复盘。

<ConceptDiagram type='layers3' title='第 132 讲 · 分层视角' labels='分片与路由：从取模到一致性哈希|副本、读写 quorum 与故障转移|AI 网关、成本限流与项目复盘|项目复盘与能力图谱' caption='AI 网关、成本限流与项目复盘' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **项目复盘与能力图谱** 落在哪一层。


## 分片与路由：从取模到一致性哈希

分片把键空间分布到多节点。取模 `hash(key)` % N 最简单，但节点数一变，绝大多数键的归属都改变，扩缩容要全量迁移；一致性哈希把节点映射成环上多个虚拟节点（vnode，生产常取 100 到 200 个），键按哈希顺时针落到遇到的第一个节点，增删节点只影响相邻区间，迁移量约 1/N，虚拟节点还能缓解数据倾斜。

路由表要版本化，配合 gossip 或配置中心同步，避免不同客户端看到不同拓扑。跨键事务与批量操作要么限制在单分片，要么引入协调者，否则一致性与延迟都难保证。热点键要单独处理：本地缓存、拆成多个子键、或读写分离。失效信号：某节点容量显著高于均值、扩容后缓存命中率骤降、路由表版本不一致导致写错节点。

**分片方案对照**

| 方案 | 扩缩容迁移量 | 倾斜风险 | 适用 |
| --- | --- | --- | --- |
| hash(key) % N 取模 | 几乎全量重分布 | 低 | 节点数固定的小规模集群 |
| 一致性哈希 | 约 1/N 区间 | 需虚拟节点缓解 | 需要弹性扩缩容 |
| 一致性哈希 + vnode | 约 1/N 且更均匀 | 低 | 生产常用，vnode 约 100-200 |
| 范围分片 | 按区间分裂 | 热点区间风险 | 有序扫描与范围查询 |

```python
import hashlib

NODES = ['n1', 'n2', 'n3']
REPLICAS = 3

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

ring = sorted((h(nd + '#' + str(i)), nd) for nd in NODES for i in range(REPLICAS))

def primary(key):
    x = h(key)
    for slot, nd in ring:
        if x <= slot:
            return nd
    return ring[0][1]

def replica_set(key):
    seen, out = [], []
    for slot, nd in ring:
        if nd not in seen:
            seen.append(nd)
            out.append(nd)
    start = out.index(primary(key))
    return out[start:] + out[:start]

def route(key, alive):
    for nd in replica_set(key):
        if nd in alive:
            return nd
    return None

def quorum_ok(key, alive, w=2):
    return sum(1 for nd in replica_set(key) if nd in alive) >= w

print('primary of a', primary('a'))
print('replica set', replica_set('a'))
all_alive = set(NODES)
print('write ok', quorum_ok('a', all_alive, w=2))
one_down = all_alive - {primary('a')}
print('failover to', route('a', one_down))
print('quorum after loss', quorum_ok('a', one_down, w=2))
print('quorum single', quorum_ok('a', {'n1'}, w=2))
```

<OutputBox title='主示例运行结果' output='primary of a n2\nreplica set [&#39;n2&#39;, &#39;n3&#39;, &#39;n1&#39;]\nwrite ok True\nfailover to n3\nquorum after loss True\nquorum single False' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import hashlib\n\nNODES = [&#39;n1&#39;, &#39;n2&#39;, &#39;n3&#39;]\nREPLICAS = 3\n\ndef h(s):\n    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)\n\nring = sorted((h(nd + &#39;#&#39; + str(i)), nd) for nd in NODES for i in range(REPLICAS))\n\ndef primary(key):\n    x = h(key)\n    for slot, nd in ring:\n        if x &lt;= slot:\n            return nd\n    return ring[0][1]\n\ndef replica_set(key):\n    seen, out = [], []\n    for slot, nd in ring:\n        if nd not in seen:\n            seen.append(nd)\n            out.append(nd)\n    start = out.index(primary(key))\n    return out[start:] + out[:start]\n\ndef route(key, alive):\n    for nd in replica_set(key):\n        if nd in alive:\n            return nd\n    return None\n\ndef quorum_ok(key, alive, w=2):\n    return sum(1 for nd in replica_set(key) if nd in alive) &gt;= w\n\nprint(&#39;primary of a&#39;, primary(&#39;a&#39;))\nprint(&#39;replica set&#39;, replica_set(&#39;a&#39;))\nall_alive = set(NODES)\nprint(&#39;write ok&#39;, quorum_ok(&#39;a&#39;, all_alive, w=2))\none_down = all_alive - {primary(&#39;a&#39;)}\nprint(&#39;failover to&#39;, route(&#39;a&#39;, one_down))\nprint(&#39;quorum after loss&#39;, quorum_ok(&#39;a&#39;, one_down, w=2))\nprint(&#39;quorum single&#39;, quorum_ok(&#39;a&#39;, {&#39;n1&#39;}, w=2))' :notes='["导入 hashlib，用 md5 生成稳定可复现的环上位置", "三个节点构成集群", "每个节点映射 3 个虚拟节点，缓解数据倾斜", "h 把字符串映射成整数，md5 不受 PYTHONHASHSEED 随机化影响", "取前 8 位十六进制转整数，作为环坐标", "构造有序的 (槽位, 节点) 环，是一致性哈希的核心", "primary 按键哈希顺时针找第一个槽位", "算出键的环坐标", "按槽位升序扫描环", "键哈希小于等于槽位即命中该节点", "返回主副本节点", "越过最大槽位则回绕到环首节点", "replica_set 给出该键的副本顺序", "seen 去重、out 保存首次出现的节点顺序", "遍历环上的虚拟节点", "只记录每个物理节点第一次出现", "追加到去重集合", "追加到有序节点列表", "找到主副本在顺序表里的位置", "旋转列表，让副本顺序从主副本开始", "route 在存活节点里挑第一个可用副本", "按副本顺序逐个检查", "命中存活节点即返回，实现故障转移", "把存活副本作为本次路由结果返回", "全不可用时返回 None，由上层降级", "quorum_ok 判断存活副本数是否达到写确认数 W", "统计副本集合里存活的节点数并与 W 比较", "打印键 a 的主副本，验证路由确定性", "打印副本顺序，副本从主节点开始排列", "构造全存活集合", "三副本全在时 W=2 的写入通过", "模拟主副本宕机，从集合里移除它", "路由自动转到下一个存活副本", "失去一个节点后仍有两个存活副本，W=2 仍满足", "只剩单节点时达不到 W=2，写入被拒绝"]' title='第 132 讲 · 实战 11 · 分片复制、AI 网关与能力收束' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 一致性哈希环与虚拟节点：迁移量为什么约 1/N

一致性哈希把节点和键都映射到同一个哈希环，增删节点只影响相邻区间，迁移量约 1/N；虚拟节点把每个物理节点拆成多个槽位，让分布更均匀，代价是路由表变大。md5 等确定性哈希不受进程内 hash 随机化影响，适合跨节点共享的路由计算。

quorum 的正确性来自集合交集：写集合大小 W 与读集合大小 R 满足 W + R > N 时二者必有重叠副本，因此读至少能看到一个承载最新写的副本；这是鸽巢原理的直接应用，也是 CAP 下选择一致性或可用性的定量依据。SSE 把长连接建模成「逐块产出」的生成器，背压由消费方拉取速度决定；

超时与预算上限把不确定长尾关进有限边界。契约测试之所以能锁住四讲演进中的行为不变，是因为它把命令语义显式化为对每个实现都成立的输入输出对，任何替换违反契约都会在 CI 暴露。

```python
import hashlib

N = 3
def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)
counts = [0, 0, 0]
for i in range(300):
    counts[h('key' + str(i)) % N] += 1
print('distribution', counts)
print('balanced', max(counts) - min(counts) < 60)
print('quorum R+W>N', 2 + 2 > 3)
```

<OutputBox title='原理验证' output='distribution [111, 88, 101]\nbalanced True\nquorum R+W&gt;N True' />

<Term word='分片与路由' text='分片把键空间分布到多节点。取模 hash(key) % N 最简单，但节点数一变，绝大多数键的归属都改变，扩缩容要全量迁移；一致性哈希把节点映射成环上多个虚拟节点（vnode，生产常取 100 到 200 个），键按哈希顺时针落到遇到的第一个节点，增删节点只影响相邻区间，迁移量约 1/N，虚拟节点还能缓解数据倾斜。路由' />

<Term word='副本与读写 quorum' text='只分片不复制，节点一挂就是永久丢数据。每份数据写到 N 个副本，写入需 W 个确认、读取需 R 个；满足 R + W &gt; N 时读写集合必有交集，因此能读到最新写，N=3、W=2、R=2 是经典配置。W=N 最一致但任一副本故障就不可写，W=1 延迟最低但可能丢写，选型要在 CAP 约束下显式决定网络分区时保一致性还是' />


## 副本、读写 quorum 与故障转移

只分片不复制，节点一挂就是永久丢数据。每份数据写到 N 个副本，写入需 W 个确认、读取需 R 个；满足 R + W > N 时读写集合必有交集，因此能读到最新写，`N=3`、`W=2`、`R=2` 是经典配置。

`W=N` 最一致但任一副本故障就不可写，`W=1` 延迟最低但可能丢写，选型要在 CAP 约束下显式决定网络分区时保一致性还是保可用性。副本间用版本号、vector clock 或领导者复制处理冲突，读修复与反熵补齐差异。故障转移靠心跳加租约判定存活，主节点失效后从副本选主，必须用多数派或 fencing token 防脑裂；

短时故障还可用 hinted handoff 把本该写到宕机节点的记录暂存在邻居，恢复后再回传，避免直接拒绝写入。失效信号：单节点故障后数据不可读、两个主同时接受写、副本间版本长期不一致。

**quorum 配置与一致性**

| 配置 (N,R,W) | R+W>N | 可用性 | 一致性 |
| --- | --- | --- | --- |
| 3, 2, 2 | 4>3 成立 | 可容忍 1 节点故障 | 读写有交集，能读到最新写 |
| 3, 1, 3 | 4>3 成立 | 写需全部副本，故障即不可写 | 最强一致 |
| 3, 1, 1 | 2>3 不成立 | 最高 | 可能读到旧值、可能丢写 |
| 3, 3, 1 | 4>3 成立 | 读需全部副本 | 读强一致、写低延迟 |

<Compare :panels='[{"label": "主示例", "code": "import hashlib\n\nNODES = [&#39;n1&#39;, &#39;n2&#39;, &#39;n3&#39;]\nREPLICAS = 3\n\ndef h(s):\n    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)\n\nring = sorted((h(nd + &#39;#&#39; + str(i)), nd) for nd in NODES for i in range(REPLICAS))\n\ndef primary(key):\n    x = h(key)\n    for slot, nd in ring:\n        if x &lt;= slot:\n            return nd\n    return ring[0][1]\n\ndef replica_set(key):\n    seen, out = [], []\n    for slot, nd in ring:\n        if nd not in seen:\n            seen.append(nd)\n            out.append(nd)\n    start = out.index(primary(key))\n    return out[start:] + out[:start]\n\ndef route(key, alive):\n    for nd in replica_set(key):\n        if nd in alive:\n            return nd\n    return None\n\ndef quorum_ok(key, alive, w=2):\n    return sum(1 for nd in replica_set(key) if nd in alive) &gt;= w\n\nprint(&#39;primary of a&#39;, primary(&#39;a&#39;))\nprint(&#39;replica set&#39;, replica_set(&#39;a&#39;))\nall_alive = set(NODES)\nprint(&#39;write ok&#39;, quorum_ok(&#39;a&#39;, all_alive, w=2))\none_down = all_alive - {primary(&#39;a&#39;)}\nprint(&#39;failover to&#39;, route(&#39;a&#39;, one_down))\nprint(&#39;quorum after loss&#39;, quorum_ok(&#39;a&#39;, one_down, w=2))\nprint(&#39;quorum single&#39;, quorum_ok(&#39;a&#39;, {&#39;n1&#39;}, w=2))", "note": "分片与路由：从取模到一致性哈希"}, {"label": "对照 / 进阶", "code": "def sse_frames(chunks):\n    for c in chunks:\n        yield &#39;data: &#39; + c + chr(10) + chr(10)\n\ndef gateway(chunks, budget, deadline):\n    out, used = [], 0\n    for t, text in chunks:\n        if t &gt; deadline:\n            out.append(&#39;[timeout]&#39;)\n            break\n        if used &gt;= budget:\n            out.append(&#39;[budget]&#39;)\n            break\n        out.append(text)\n        used += 1\n    return out, used\n\nframes = list(sse_frames([&#39;你&#39;, &#39;好&#39;]))\nprint(&#39;frame count&#39;, len(frames))\nprint(&#39;has data prefix&#39;, frames[0].startswith(&#39;data: &#39;))\nprint(&#39;has newline&#39;, chr(10) in frames[0])\nchunks = [(1, &#39;你&#39;), (2, &#39;好&#39;), (3, &#39;！&#39;)]\nprint(&#39;normal&#39;, gateway(chunks, budget=5, deadline=10))\nprint(&#39;budget&#39;, gateway(chunks, budget=2, deadline=10))\nprint(&#39;timeout&#39;, gateway([(1, &#39;A&#39;), (99, &#39;B&#39;)], budget=5, deadline=10))", "note": "副本、读写 quorum 与故障转移"}]' title='两种写法对照' note='差异集中在 分片与路由；先看输出，再找背后的规则。' />


## AI 网关：流式推理、超时与成本预算上限

把同样的网关能力用于 LLM 流式推理：SSE 属于 text/event-stream，帧以 data: 开头、空行分隔，用生成器逐块 yield 即可实现背压。长连接必须设四道闸：首 token 超时与总时长上限、Token 预算上限、并发连接上限、累计金额上限，否则一个慢流会拖空连接池、一次异常重试会吃掉整日预算。

多供应商适配靠统一接口（请求 / 流式块 / 用量）挡在后面，重试只对幂等请求生效并带指数退避；每轮记录 trace_id、Token、耗时与工具名；降级路径明确——超预算返回已生成部分加提示，而不是空响应。项目复盘用契约测试锁住四讲演进过程中命令语义不变：内存版、网络版、WAL 版、分片版都跑同一组断言；

把每个取舍的代价与回退方案写成 ADR，包括分片迁移代价、副本一致性级别、刷盘策略与网关超时阈值。

**AI 网关与分布式失败模式**

| 现象 | 根因 | 防线 |
| --- | --- | --- |
| 节点一挂永久丢数据 | 只分片不做副本 | N 副本 + W 确认 + 故障转移选主 |
| 脑裂出现两个主 | 无多数派或 fencing | 多数派选主 + fencing token |
| 慢流拖空连接池 | 长连接无超时与并发上限 | 首 token/总时长超时 + Semaphore 限连接 |
| 一次异常吃整日预算 | Agent 循环无步数与 Token 上限 | 累计 Token/金额上限 + 步数上限 + 幂等重试 |
| 演进后命令语义漂移 | 换实现没跑同一组用例 | 四讲共用契约测试 + 每个取舍写 ADR |

<Callout type="warn" title='本讲最容易踩的坑' text='只做分片不做副本，节点故障造成永久丢数据：每个键只有一个持有者，磁盘损坏或节点宕机即不可恢复' />


## 把网关能力用于 LLM 流式：deadline 与逐块产出

```python
def sse_frames(chunks):
    for c in chunks:
        yield 'data: ' + c + chr(10) + chr(10)

def gateway(chunks, budget, deadline):
    out, used = [], 0
    for t, text in chunks:
        if t > deadline:
            out.append('[timeout]')
            break
        if used >= budget:
            out.append('[budget]')
            break
        out.append(text)
        used += 1
    return out, used

frames = list(sse_frames(['你', '好']))
print('frame count', len(frames))
print('has data prefix', frames[0].startswith('data: '))
print('has newline', chr(10) in frames[0])
chunks = [(1, '你'), (2, '好'), (3, '！')]
print('normal', gateway(chunks, budget=5, deadline=10))
print('budget', gateway(chunks, budget=2, deadline=10))
print('timeout', gateway([(1, 'A'), (99, 'B')], budget=5, deadline=10))
```

<OutputBox title='对照写法：先自己猜，再点开' output='frame count 2\nhas data prefix True\nhas newline True\nnormal ([&#39;你&#39;, &#39;好&#39;, &#39;！&#39;], 3)\nbudget ([&#39;你&#39;, &#39;好&#39;, &#39;[budget]&#39;], 2)\ntimeout ([&#39;A&#39;, &#39;[timeout]&#39;], 1)' guess="true" />

<Callout type="tip" title='核心心智模型' text='分片把键空间分布到多节点。取模 hash(key) % N 最简单，但节点数一变，绝大多数键的归属都改变，扩缩容要全量迁移；一致性哈希把节点映射成环上多个虚拟节点（vnode，生产常取 100 到 200 个），键按哈希顺时针落到遇到的第一个节点，增删节点只影响相邻区间，迁移量约 1/N，虚拟节点还' />


## 演进过程中用契约测试与 ADR 锁住行为不变

<CheckList id='P132b' title='上线前自检' :items='["能复现并解释「只做分片不做副本，节点故障造成永久丢数据」", "能复现并解释「流式接口不设超时与预算上限」", "能复现并解释「演进过程中没有契约测试与 ADR」", "能用一条命令验证 分片与路由", "关键路径有自动化测试与失败分支"]' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：只做分片不做副本，节点故障造成永久丢数据", "body": "每个键只有一个持有者，磁盘损坏或节点宕机即不可恢复", "tip": "每份数据写 N 个副本，W 个确认后应答，配故障转移选主与读修复"}, {"title": "第 2 步：流式接口不设超时与预算上限", "body": "慢流占住连接池、Agent 循环无上限重试会吃整日 Token 预算", "tip": "设首 token/总时长超时、Token 与金额累计上限、并发连接上限，超预算返回已生成部分"}, {"title": "第 3 步：演进过程中没有契约测试与 ADR", "body": "换实现时命令语义悄悄漂移，取舍的代价与回退没人记得", "tip": "四讲共用同一组契约测试，把分片迁移、quorum 级别、刷盘策略、超时阈值写成 ADR"}]' />


## 分片路由 + quorum + 流式预算的统一网关

把最后一讲的两条线合到一个网关：数据面用 md5 选分片、route 在主副本宕机时自动切到存活副本、quorum_ok 判断剩余副本是否够 W；推理面用 stream 逐块产出并受 deadline 与 token_budget 双重约束，cost 据实际用量计费。

这个结构同时覆盖「分片复制」与「AI 网关」两个议题：同一套路由、限流、可观测能力既能服务 KV，也能服务 LLM 流式推理。真实项目还要加心跳与租约、多数派选主防脑裂、多供应商统一接口、retry 幂等键与 trace_id，并把四讲的契约测试跑在分片版上验证命令语义不变。片段可直接运行，重点看故障转移与预算降级两条路径。

```python
import hashlib

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

class Gateway:
    def __init__(self, nodes, token_budget=100):
        self.nodes = list(nodes)
        self.alive = set(nodes)
        self.budget = token_budget
        self.spent = 0
    def shard(self, key):
        return self.nodes[h(key) % len(self.nodes)]
    def route(self, key):
        pref = self.shard(key)
        if pref in self.alive:
            return pref
        for nd in self.nodes:
            if nd in self.alive:
                return nd
        return None
    def quorum_ok(self, w=2):
        return len(self.alive) >= w
    def stream(self, chunks, deadline):
        out = []
        for t, text in chunks:
            if t > deadline or self.spent >= self.budget:
                return out, 'degraded'
            out.append(text)
            self.spent += 1
        return out, 'ok'
    def cost(self, price=0.002):
        return round(self.spent * price, 4)

gw = Gateway(['n1', 'n2', 'n3'], token_budget=3)
print('shard', gw.shard('user-42'))
gw.alive.discard(gw.shard('user-42'))
print('failover', gw.route('user-42'), 'quorum', gw.quorum_ok())
print('stream', gw.stream([(1, 'A'), (2, 'B'), (3, 'C'), (4, 'D')], deadline=10))
print('cost', gw.cost())
```

<Callout type="idea" title='落地提示' text='用契约测试锁住演进过程中的行为不变，复盘写下每个取舍的代价与回退方案' />

```bash
python -m compileall -q . && python -m pytest -q
```

把输入换成你自己的数据，观察结果是否仍符合 **分片与路由** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 只做分片不做副本，节点故障造成永久丢数据 | 每个键只有一个持有者，磁盘损坏或节点宕机即不可恢复 | 每份数据写 N 个副本，W 个确认后应答，配故障转移选主与读修复 |
| 流式接口不设超时与预算上限 | 慢流占住连接池、Agent 循环无上限重试会吃整日 Token 预算 | 设首 token/总时长超时、Token 与金额累计上限、并发连接上限，超预算返回已生成部分 |
| 演进过程中没有契约测试与 ADR | 换实现时命令语义悄悄漂移，取舍的代价与回退没人记得 | 四讲共用同一组契约测试，把分片迁移、quorum 级别、刷盘策略、超时阈值写成 ADR |


## SSE 帧格式、chunked 编码与背压队列

把 LLM 流式响应用 SSE 推给客户端，网关面对的是一条不会按时结束的长连接。

SSE 的有线格式很朴素：Content-Type 为 text/event-stream，每个事件是 data 行加一个空行结束，可选 event、id、retry 字段，HTTP/1.1 用 Transfer-Encoding: chunked 分块下发，HTTP/2 则走 DATA 帧；

中间若有代理缓冲或 Nagle 攒包，首 token 会被卡住，必须配 X-Accel-Buffering: no 与周期性心跳注释帧。

网关内部真正的问题是背压：上游推理按 token 产出，客户端或网络慢时若用无界队列缓冲，一个慢消费者就能吃光内存，因此 asyncio 侧用 `asyncio.Queue(maxsize=N)`，满了就让 producer 在 await `queue.put()` 上挂起，把压力反向传到上游；

队列大小与单连接内存上限要写进容量模型。客户端中途断开是常态而非异常：连接关闭要触发 CancelledError，网关必须 `cancel()` 上游推理任务并 await 它收尾，否则模型侧继续生成、继续计费，形成孤儿推理；清理段要用 `asyncio.shield` 加超时保护，避免取消链把关闭逻辑也打断。

再往上是一组分层超时：连接超时、首 token 超时（TTFT）、逐 token 的空闲超时与整条流的总时长上限，任何一层触发都返回已生成部分并把 finish_reason 标成 timeout。

```python
class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
    def allow(self, cost=1.0):
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False
    def advance(self, seconds):
        self.tokens = min(self.capacity, self.tokens + self.rate * seconds)
        return self.tokens

bucket = TokenBucket(rate=10.0, capacity=5.0)
results = [bucket.allow() for _ in range(7)]
print('burst_accepted', sum(results))
print('tail_rejected', results[5:] == [False, False])
refilled = bucket.advance(0.3)
print('refilled_tokens', round(refilled, 2))
print('allow_after_refill', bucket.allow())
print('tokens_after', round(bucket.tokens, 2))
```

<OutputBox title='扩展示例运行结果' output='burst_accepted 5\ntail_rejected True\nrefilled_tokens 3.0\nallow_after_refill True\ntokens_after 2.0' />

<LineByLine code='class TokenBucket:\n    def __init__(self, rate, capacity):\n        self.rate = rate\n        self.capacity = capacity\n        self.tokens = float(capacity)\n    def allow(self, cost=1.0):\n        if self.tokens &gt;= cost:\n            self.tokens -= cost\n            return True\n        return False\n    def advance(self, seconds):\n        self.tokens = min(self.capacity, self.tokens + self.rate * seconds)\n        return self.tokens\n\nbucket = TokenBucket(rate=10.0, capacity=5.0)\nresults = [bucket.allow() for _ in range(7)]\nprint(&#39;burst_accepted&#39;, sum(results))\nprint(&#39;tail_rejected&#39;, results[5:] == [False, False])\nrefilled = bucket.advance(0.3)\nprint(&#39;refilled_tokens&#39;, round(refilled, 2))\nprint(&#39;allow_after_refill&#39;, bucket.allow())\nprint(&#39;tokens_after&#39;, round(bucket.tokens, 2))' :notes='["令牌桶：rate 是补充速率，capacity 是突发容量，初始满额", "推进虚拟时钟按 rate 补充但不超过容量", "容量内突发只放行前 5 个请求", "第 6、7 个被拒", "0.3 秒补 3 个令牌", "补后放行一个，剩余令牌降到 2.0", "取模分片扩缩容几乎全量迁移；一致性哈希只迁移约 1/N 区间，虚拟节点（100-200 个）缓解倾斜", "quorum 满足 R + W &gt; N 时读写集合必有交集；N=3、W=2、R=2 可容忍单点故障", "只分片不复制，节点一挂即永久丢数据；故障转移靠心跳租约 + 多数派/fencing 防脑裂", "SSE 用生成器逐块 yield 实现背压；首 token/总时长超时、Token/金额上限、并发连接上限缺一不可", "多供应商靠统一接口适配，重试只对幂等请求生效；每轮记 trace_id、Token、耗时，降级返回已生成部分", "四讲共用契约测试锁住命令语义不变；把分片迁移、quorum 级别、刷盘策略、超时阈值写成 ADR 并给回退方案", "取模分片扩缩容几乎全量迁移；一致性哈希只迁移约 1/N 区间，虚拟节点（100-200 个）缓解倾斜", "quorum 满足 R + W &gt; N 时读写集合必有交集；N=3、W=2、R=2 可容忍单点故障", "只分片不复制，节点一挂即永久丢数据；故障转移靠心跳租约 + 多数派/fencing 防脑裂", "SSE 用生成器逐块 yield 实现背压；首 token/总时长超时、Token/金额上限、并发连接上限缺一不可", "多供应商靠统一接口适配，重试只对幂等请求生效；每轮记 trace_id、Token、耗时，降级返回已生成部分", "四讲共用契约测试锁住命令语义不变；把分片迁移、quorum 级别、刷盘策略、超时阈值写成 ADR 并给回退方案", "取模分片扩缩容几乎全量迁移；一致性哈希只迁移约 1/N 区间，虚拟节点（100-200 个）缓解倾斜", "quorum 满足 R + W &gt; N 时读写集合必有交集；N=3、W=2、R=2 可容忍单点故障", "只分片不复制，节点一挂即永久丢数据；故障转移靠心跳租约 + 多数派/fencing 防脑裂"]' title='扩展示例逐行讲解' />


### 客户端断连时的取消传播与孤儿推理清理

**流式网关的分层约束与失效信号**

| 层级 | 约束 / 字段 | 失效信号 | 处置 |
| --- | --- | --- | --- |
| 传输 | text/event-stream、chunked、心跳帧 | 首 token 迟迟不到 | 关代理缓冲、加心跳帧 |
| 背压 | asyncio.Queue(maxsize) | 无界队列吃满内存 | producer 在 put 挂起反压 |
| 断连 | cancel 加 await 上游任务 | 客户端走后仍在计费 | shield 包裹清理并限时 |
| 超时 | connect / TTFT / idle / total | 慢流占住连接池 | 分级返回已生成部分 |
| 预算 | 令牌桶加累计 Token 与金额上限 | Agent 循环吃尽日预算 | 超预算截断并标 finish_reason |


## 三级超时、令牌桶限流与 Token 预算截断

限流要同时挡住两个维度：请求速率与累计成本。速率用令牌桶而非固定窗口——桶以 rate 个 token 每秒补充、容量 capacity 决定允许的突发，窗口边界不会像固定计数那样出现临界点双倍流量，实现只需记录上次补充时间与余量，纯函数即可用虚拟时钟测试，不依赖真实 sleep。

成本维度更关键：Agent 的一次工具循环可能反复调用模型，若只在单请求上设超时而不累计 Token 与金额，一日预算会在无人察觉时被长连接吃尽；

网关要按租户维护累计计数，达到软阈值降速、达到硬阈值直接截断当前流并返回 `finish_reason=budget_exceeded` 与已生成部分。

并发连接上限、每连接队列大小、单流最大 token 数共同构成准入控制，超限走 429 或降级到非流式摘要。

收束处要把四讲的决定连成一条可复核的链：129 的窄接口与一组契约测试保证换实现不改命令语义，130 的刷盘方案、131 的 quorum 级别、132 的超时阈值全部写进 ADR 并标代价与回退，故障注入脚本随 CI 跑。能力图谱的终点不是会用多少框架，而是能否在信息不全时给出带假设、带可验证代价、带回退的方案。


### TTFT 与 TPOT：流式网关该盯哪两个分位数

<Quiz no='132-X' q='流式推理网关里，客户端中途断开后最容易被漏掉、且会直接造成成本损失的失效是？' :options='["没有 cancel 并 await 上游推理任务，模型继续生成形成孤儿推理", "没有把 Content-Type 设成 application/json", "没有给 SSE 事件加 id 字段", "没有用 HTTP/2 明文传输"]' answer="0" explain='连接关闭只影响客户端一侧，若网关不把 CancelledError 传播并取消上游任务，模型侧会继续吐 token 直到最大长度，既占连接又持续计费；清理段要用 shield 加超时，保证取消链不会把关闭逻辑也打断。' />


### 连接池耗尽与慢流占位的失效信号

<ConceptDiagram type='flow4' title='第 132 讲 · 扩展图解' labels='SSE 帧与 chunked|Queue(maxsize) 背压|四级超时加断连取消|令牌桶加 Token 预算' caption='流式网关四道闸：从传输帧到背压、生命周期、成本，任何一道缺失都会被长连接放大' />


## 四讲收束：契约测试、ADR 与能力图谱

<Exercise title='用虚拟时钟验证令牌桶的突发与补充' task='实现一个不依赖真实时间的令牌桶，构造容量内突发全部放行、超出被拒、推进 0.3 秒后按 rate 补充再放行的用例并打印结果；说明为什么固定窗口计数在窗口临界点会放行双倍流量。' solution='class TokenBucket:\n    def __init__(self, rate, capacity):\n        self.rate, self.capacity = rate, capacity\n        self.tokens = float(capacity)\n    def allow(self, cost=1.0):\n        if self.tokens &gt;= cost:\n            self.tokens -= cost\n            return True\n        return False\n    def advance(self, seconds):\n        self.tokens = min(self.capacity, self.tokens + self.rate * seconds)\n\nb = TokenBucket(10.0, 5.0)\nburst = [b.allow() for _ in range(7)]\nprint(&#39;burst_accepted&#39;, sum(burst))\nb.advance(0.3)\nprint(&#39;tokens_after_0_3s&#39;, round(b.tokens, 2))\nprint(&#39;allow_after_refill&#39;, b.allow())\nprint(&#39;tokens_final&#39;, round(b.tokens, 2))' explain='令牌桶按 rate 连续补充、容量 cap 限制突发，5 个令牌一次放行 5 个请求后其余被拒；推进 0.3 秒补 3 个，再放行一个。固定窗口按整段计数，窗口切换瞬间前后各能放行一整窗配额，临界点出现双倍流量，令牌桶没有这个边界。' />


## 从练习到能力图谱：自测与速记

<Exercise title='基础：实现一致性哈希环并观察故障转移' task='用 md5 把三个节点各映射 3 个虚拟节点构成有序环，写 primary(key) 与 route(key, alive)，移除主副本后打印新路由。' solution='import hashlib\ndef h(s): return int(hashlib.md5(s.encode()).hexdigest()[:8],16)\nring=sorted((h(n+&#39;#&#39;+str(i)),n) for n in [&#39;n1&#39;,&#39;n2&#39;,&#39;n3&#39;] for i in range(3))\ndef primary(k):\n    x=h(k)\n    for s,n in ring:\n        if x&lt;=s: return n\n    return ring[0][1]\nalive={&#39;n1&#39;,&#39;n2&#39;,&#39;n3&#39;}\np=primary(&#39;a&#39;)\nprint(&#39;primary&#39;,p)\nalive.discard(p)\nprint(&#39;failover&#39;,next(n for s,n in ring if n in alive))' explain='输出主副本与移除后的下一个存活节点。增删节点只影响相邻区间，是一致性哈希相比取模的核心优势。' />

<Exercise title='进阶：给流式网关加超时与 Token 预算' task='写 gateway(chunks, budget, deadline)，逐块检查时间戳与累计用量，超限时返回已生成部分加降级标记，验证正常、超预算、超时三种情况。' solution='def gw(chunks,budget,deadline):\n    out,used=[],0\n    for t,x in chunks:\n        if t&gt;deadline: return out,&#39;timeout&#39;\n        if used&gt;=budget: return out,&#39;budget&#39;\n        out.append(x); used+=1\n    return out,&#39;ok&#39;\nc=[(1,&#39;A&#39;),(2,&#39;B&#39;),(3,&#39;C&#39;)]\nprint(gw(c,5,10))\nprint(gw(c,2,10))\nprint(gw([(1,&#39;A&#39;),(99,&#39;B&#39;)],5,10))' explain='依次输出 ([&#39;A&#39;,&#39;B&#39;,&#39;C&#39;],&#39;ok&#39;)、([&#39;A&#39;,&#39;B&#39;],&#39;budget&#39;)、([&#39;A&#39;],&#39;timeout&#39;)。超时与预算把不确定的长尾关进有限边界，是流式接口的硬性约束。' />

<Quiz no='132-1' q='关于 N=3、W=2、R=2 的 quorum，哪一项准确？' :options='["R+W=4&gt;3，读写集合必有交集，能读到最新写且可容忍 1 节点故障", "W=2 表示必须三个副本都确认", "该配置允许两个主同时接受写", "该配置无法容忍任何节点故障"]' answer="0" explain='W+R&gt;N 保证读集合与写集合至少重叠一个副本，因此能读到最新写；N=3、W=2 时失去一个节点仍有 2 个可确认，可容忍单点故障。' />

<Quiz no='132-2' q='一致性哈希相比取模分片的关键优势是？' :options='["增删节点只影响相邻区间，迁移量约 1/N", "实现更简单", "完全不需要虚拟节点", "保证强一致"]' answer="0" explain='取模在节点数变化时会让几乎所有键重新分布；一致性哈希把节点与键映射到同一环上，只迁移相邻区间，虚拟节点用来缓解倾斜。' />

<Quiz no='132-3' q='流式推理网关最不该缺哪一类约束？' :options='["首 token/总时长超时 + Token/金额累计上限 + 并发连接上限", "更大的上下文窗口", "更高的 temperature", "更长的系统提示"]' answer="0" explain='慢流会占住连接池、无上限的 Agent 重试会吃整日预算；超时、预算与并发上限属于工程契约，与提示词措辞无关，且要有明确的降级出口。' />

<Predict no='132-P' q='N=3、R=2、W=2 时，R+W&gt;N 是否成立及其含义是？' :options='["成立（4&gt;3），读写必有交集", "不成立（4&lt;3）", "成立但只能容忍两节点同时故障"]' answer='0' output='quorum R+W&gt;N True' explain='4 大于 3，读集合与写集合必然至少重叠一个副本，因此能读到最新写；这也是鸽巢原理在副本一致性上的直接应用。' />

<FillBlank no='132-F' tpl='___ hashlib' :answers='["import"]' hint='回想本讲关于 分片与路由 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 分片与路由：从取模到一致性哈希 的落点。' />

<KnowledgeCard :points='["取模分片扩缩容几乎全量迁移；一致性哈希只迁移约 1/N 区间，虚拟节点（100-200 个）缓解倾斜", "quorum 满足 R + W &gt; N 时读写集合必有交集；N=3、W=2、R=2 可容忍单点故障", "只分片不复制，节点一挂即永久丢数据；故障转移靠心跳租约 + 多数派/fencing 防脑裂", "SSE 用生成器逐块 yield 实现背压；首 token/总时长超时、Token/金额上限、并发连接上限缺一不可", "多供应商靠统一接口适配，重试只对幂等请求生效；每轮记 trace_id、Token、耗时，降级返回已生成部分", "四讲共用契约测试锁住命令语义不变；把分片迁移、quorum 级别、刷盘策略、超时阈值写成 ADR 并给回退方案"]' :pitfalls='["只做分片不做副本，节点故障造成永久丢数据", "流式接口不设超时与预算上限", "演进过程中没有契约测试与 ADR", "只做分片不做副本，节点一挂就是永久丢数据；流式接口不设超时与预算上限则会被长连接拖垮"]' summary='最后一讲把贯穿线接到真实生产议题上：数据分片、副本一致、故障转移，以及把同样的网关能力用于 LLM 流式推理' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 取模分片扩缩容几乎全量迁移；一致性哈希只迁移约 1/N 区间，虚拟节点（100-200 个）缓解倾斜 | 建立直觉 |
| quorum 满足 R + W > N 时读写集合必有交集；N=3、W=2、R=2 可容忍单点故障 | 跑通示例 |
| 只分片不复制，节点一挂即永久丢数据；故障转移靠心跳租约 + 多数派/fencing 防脑裂 | 深入边界 |
| SSE 用生成器逐块 yield 实现背压；首 token/总时长超时、Token/金额上限、并发连接上限缺一不可 | 工程落地 |
| 多供应商靠统一接口适配，重试只对幂等请求生效；每轮记 trace_id、Token、耗时，降级返回已生成部分 | 随堂检测 |
| 四讲共用契约测试锁住命令语义不变；把分片迁移、quorum 级别、刷盘策略、超时阈值写成 ADR 并给回退方案 | 复盘 |

1. 取模分片扩缩容几乎全量迁移；一致性哈希只迁移约 1/N 区间，虚拟节点（100-200 个）缓解倾斜

2. quorum 满足 R + W > N 时读写集合必有交集；N=3、W=2、R=2 可容忍单点故障

3. 只分片不复制，节点一挂即永久丢数据；故障转移靠心跳租约 + 多数派/fencing 防脑裂

[进入练习与速查](/practice/)
