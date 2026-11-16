---
title: 第 108 讲 · 分布式 ID、一致性哈希与分片
description: 设计可水平扩展的数据布局
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★☆' time='40 分钟' goal='设计可水平扩展的数据布局' prereq='第 107 讲 · 分布式事务：2PC / TCC / Saga / 消息最终一致' />

# 第 108 讲 · 分布式 ID、一致性哈希与分片

跨服务的一致性问题有了着落，紧接着撞上另一道坎：单机的一张表装不下，查询也渐渐扛不住。把数据摊到几台机器听着直接，可切法不同，加机器时旧数据要搬多少能差出好几倍。本讲从最不起眼的标识符入手，一路走到整张数据布局。

比如用户表靠自增主键，分库后两个库可能发出同一个号；又比如按取模分片，从八片扩到九片，几乎全部数据都得重新挪窝。我们先看雪花算法怎么把时间、机器位编进去，再比较范围分片与哈希分片的迁移量，接着用一致性哈希和虚拟节点把扩容代价压下来，最后谈热点、倾斜与再平衡。需要哈希、取模和字典基础；学完你能自己选分片键、估算一次扩容要搬多少数据。


## 扩到第九片，为什么要搬走近九成数据

一个用户中心最初用数据库自增 ID 做主键，数据涨到单表放不下后团队按 ID 范围分成八片，结果新注册用户全部落在最后一片，前七片闲置，写入热点把最后一片打满。于是改成 `hash(id)` 取模分片，热点没了，但运营要查最近一周注册的用户时只能在八个片上各扫一遍再归并，因为按时间过滤的查询在哈希分布上没有任何局部性。

扩容从八片加到九片时更糟：取模分片下 key 落点几乎全部变化，迁移要搬走近九成数据。雪上加霜的是 ID 生成器用了机器时间，一次 NTP 回拨让新生成的 ID 与几秒前重复，触发主键冲突。分片键与 ID 生成器一旦选错，加机器毫无收益。本讲把可水平扩展的数据布局拆成可计算的部分。

<Callout type="warn" title='先看一个真实会出错的写法' text='用随机 ID 做分片键却按时间范围查询：哈希分布没有任何时间局部性，范围条件无法定位到少数片，只能对全部分片各查一次再归并' />

<CheckList id='P108a' title='学完你应当能' :items='["能讲清 自增 ID 的局限与雪花算法的位布局", "能讲清 范围分片、哈希分片与一致性哈希的迁移量", "能讲清 热点、倾斜与再平衡的工程判据", "能在工程里处理 扩容与再平衡"]' />


## 自增 ID 的局限与雪花算法的位布局

数据库 `AUTO_INCREMENT` 在单片内单调递增且紧凑，但跨片无法保证全局唯一与有序，还会暴露业务量：相邻 ID 的差值能推算出注册速率。

Snowflake 类算法把 64 位整数切成几段：最高位固定 0 留符号，接着 41 位毫秒时间戳（相对自定义 epoch，可用约 69 年），10 位机器标识（最多 1024 个节点），12 位毫秒内序列号（每节点每毫秒最多 4096 个 ID）。

生成时若同一毫秒内序列溢出，就自旋等到下一毫秒；若检测到当前时间小于上次生成时间（时钟回拨），必须拒绝服务或等待追平，绝不能继续发号，否则可能撞出重复 ID。

落地就是一条位运算 `(ts<<22)|(worker<<12)|seq`，反解用位移加掩码。

它趋势递增、可索引、不依赖数据库，代价是强依赖机器时钟与 worker id 的全局唯一分配，后者通常靠 etcd 或配置中心下发。

**Snowflake 64 位布局与边界**

| 字段 | 位数 | 取值范围 | 溢出或失效信号 |
| --- | --- | --- | --- |
| 符号位 | 1 | 固定 0 | 为 1 会变成负数，破坏趋势递增 |
| 时间戳(ms) | 41 | 相对 epoch 约 69 年 | 超过上限后发号重复，需更换 epoch |
| 机器标识 | 10 | 0 到 1023 | worker id 重复会生成相同 ID |
| 毫秒内序列 | 12 | 0 到 4095 | 单节点单毫秒超 4096 需自旋等下一毫秒 |
| 时钟回拨保护 | 无 | 当前时间小于 last_ts | 拒绝发号并告警，不能静默继续 |

<ConceptDiagram type='hub4' title='第 108 讲 · 自增 ID 的局限与雪花算法的位布局' labels='自增 ID 的局限与雪花算法的位布局|范围分片、哈希分片与一致性哈希的迁移量|热点、倾斜与再平衡的工程判据|扩容与再平衡' caption='设计可水平扩展的数据布局' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 雪花生成器遇到时钟回拨仍继续发号

<Callout type="warn" title='本讲最容易踩的坑' text='用随机 ID 做分片键却按时间范围查询：哈希分布没有任何时间局部性，范围条件无法定位到少数片，只能对全部分片各查一次再归并' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用随机 ID 做分片键却按时间范围查询", "body": "哈希分布没有任何时间局部性，范围条件无法定位到少数片，只能对全部分片各查一次再归并", "tip": "按主查询维度选键；确需时间查询就改用范围分片加预分区，或另建按时间组织的索引表"}, {"title": "第 2 步：hash(key) % N 分片的集群直接扩…", "body": "取模落点几乎全变，约 N/(N+1) 的数据要搬迁，八扩九接近九成，迁移期间双写与校验压力巨大", "tip": "改用一致性哈希加虚拟节点，把迁移量压到约 1/(N+1)，并限速可回滚地再平衡"}, {"title": "第 3 步：雪花生成器遇到时钟回拨仍继续发号", "body": "当前时间小于 last_ts 时，同一毫秒段可能重放已用过的序列，生成与几秒前重复的 ID 触发主键冲突", "tip": "记录 last_ts，检测到回拨即拒绝服务并告警，超过阈值直接熔断，等待追平后再恢复"}]' />


## 范围分片、哈希分片与一致性哈希的迁移量

分片键决定数据分布与查询效率。范围分片按 key 区间切（如按时间或 ID 段），范围查询能定位到少数片，但写入容易集中到最新的那一片形成热点；哈希分片用 `hash(key) % N` 打散写入，代价是范围查询退化为全片扫描（scatter-gather）。

更关键的是扩容：取模分片从 N 到 N+1 时，落点变化的比例约为 `N/(N+1)`，八片扩九片要迁移约 89% 的数据。一致性哈希把节点与 key 都映射到 2^32 的环上，key 顺时针找到的第一个节点即归属，扩一个节点只影响它在环上与前驱之间的那段区间，理论迁移量为 `1/(N+1)`，四节点加一节点约 20%。

为缓解节点分布不均与数据倾斜，引入虚拟节点：每个物理节点映射为 `replicas` 个虚拟点（常见 100 到 300），让环上落点更均匀，也方便按机器权重调 replicas。查找用有序数组加 `bisect_left`，复杂度 `O(log V)`，V 是虚拟节点总数。

```python
import hashlib, bisect

def hkey(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

class Ring:
    def __init__(self, nodes, replicas=100):
        self.replicas = replicas
        self.keys = []
        self.map = {}
        for n in nodes:
            self.add(n)
    def add(self, n):
        for i in range(self.replicas):
            k = hkey(n + '#' + str(i))
            bisect.insort(self.keys, k)
            self.map[k] = n
    def node_for(self, key):
        k = hkey(key)
        i = bisect.bisect_left(self.keys, k) % len(self.keys)
        return self.map[self.keys[i]]

keys = ['user:' + str(i) for i in range(2000)]
r = Ring(['n1', 'n2', 'n3'])
before = {k: r.node_for(k) for k in keys}
r.add('n4')
moved = sum(1 for k in keys if r.node_for(k) != before[k])
print('total', len(keys))
print('moved', moved)
print('ratio', round(moved / len(keys), 3))
print('ideal', round(1 / 4, 3))
```

<OutputBox title='主示例运行结果' output='total 2000\nmoved 546\nratio 0.273\nideal 0.25' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import hashlib, bisect\n\ndef hkey(s):\n    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)\n\nclass Ring:\n    def __init__(self, nodes, replicas=100):\n        self.replicas = replicas\n        self.keys = []\n        self.map = {}\n        for n in nodes:\n            self.add(n)\n    def add(self, n):\n        for i in range(self.replicas):\n            k = hkey(n + &#39;#&#39; + str(i))\n            bisect.insort(self.keys, k)\n            self.map[k] = n\n    def node_for(self, key):\n        k = hkey(key)\n        i = bisect.bisect_left(self.keys, k) % len(self.keys)\n        return self.map[self.keys[i]]\n\nkeys = [&#39;user:&#39; + str(i) for i in range(2000)]\nr = Ring([&#39;n1&#39;, &#39;n2&#39;, &#39;n3&#39;])\nbefore = {k: r.node_for(k) for k in keys}\nr.add(&#39;n4&#39;)\nmoved = sum(1 for k in keys if r.node_for(k) != before[k])\nprint(&#39;total&#39;, len(keys))\nprint(&#39;moved&#39;, moved)\nprint(&#39;ratio&#39;, round(moved / len(keys), 3))\nprint(&#39;ideal&#39;, round(1 / 4, 3))' :notes='["导入 hashlib 做稳定散列、bisect 维护有序环坐标", "空行，只用于分隔逻辑块，不影响执行结果。", "hkey 把任意字符串映射为环上整数坐标", "取 md5 前 8 位十六进制转整数，落在 32 位范围", "空行，只用于分隔逻辑块，不影响执行结果。", "定义一致性哈希环", "构造器接收初始节点与每节点虚拟点数，默认 100", "保存虚拟节点副本数", "keys 是有序坐标数组，供二分查找", "map 把坐标映射回物理节点名", "逐个把初始节点加入环", "调用 add 展开虚拟节点", "add 把单个物理节点展开为 replicas 个虚拟点", "为每个副本生成一个坐标", "用节点名加序号散列，避免不同节点坐标冲突", "insort 维持坐标升序，插入 O(V)", "登记该虚拟点所属的物理节点", "node_for 求某个 key 的归属节点", "先算 key 在环上的坐标", "bisect_left 找顺时针第一个虚拟点，取模实现回绕到环首", "返回该坐标对应的物理节点", "空行，只用于分隔逻辑块，不影响执行结果。", "构造 2000 个 key 用于统计迁移量", "三节点冷启动，每节点 100 个虚拟点", "记录加节点前每个 key 的归属", "加入第四节点，只影响环上一段区间", "统计落点发生变化的 key 数", "打印 key 总数", "打印实际迁移数，虚拟节点使其接近理论值", "打印实际迁移比例", "打印理论迁移比例 1/4 作为对照"]' title='第 108 讲 · 分布式 ID、一致性哈希与分片' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
def snowflake(ts_ms, worker, seq):
    return (ts_ms << 22) | (worker << 12) | seq

ts = 1700000000000
sid = snowflake(ts, 5, 1)
print('id', sid)
print('ts_back', sid >> 22)
print('worker', (sid >> 12) & 0x3FF)
print('seq', sid & 0xFFF)
print('bits', sid.bit_length())
```

<OutputBox title='对照写法：先自己猜，再点开' output='id 7130316800000020481\nts_back 1700000000000\nworker 5\nseq 1\nbits 63' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import hashlib, bisect\n\ndef hkey(s):\n    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)\n\nclass Ring:\n    def __init__(self, nodes, replicas=100):\n        self.replicas = replicas\n        self.keys = []\n        self.map = {}\n        for n in nodes:\n            self.add(n)\n    def add(self, n):\n        for i in range(self.replicas):\n            k = hkey(n + &#39;#&#39; + str(i))\n            bisect.insort(self.keys, k)\n            self.map[k] = n\n    def node_for(self, key):\n        k = hkey(key)\n        i = bisect.bisect_left(self.keys, k) % len(self.keys)\n        return self.map[self.keys[i]]\n\nkeys = [&#39;user:&#39; + str(i) for i in range(2000)]\nr = Ring([&#39;n1&#39;, &#39;n2&#39;, &#39;n3&#39;])\nbefore = {k: r.node_for(k) for k in keys}\nr.add(&#39;n4&#39;)\nmoved = sum(1 for k in keys if r.node_for(k) != before[k])\nprint(&#39;total&#39;, len(keys))\nprint(&#39;moved&#39;, moved)\nprint(&#39;ratio&#39;, round(moved / len(keys), 3))\nprint(&#39;ideal&#39;, round(1 / 4, 3))", "note": "自增 ID 的局限与雪花算法的位布局"}, {"label": "对照 / 进阶", "code": "def snowflake(ts_ms, worker, seq):\n    return (ts_ms &lt;&lt; 22) | (worker &lt;&lt; 12) | seq\n\nts = 1700000000000\nsid = snowflake(ts, 5, 1)\nprint(&#39;id&#39;, sid)\nprint(&#39;ts_back&#39;, sid &gt;&gt; 22)\nprint(&#39;worker&#39;, (sid &gt;&gt; 12) &amp; 0x3FF)\nprint(&#39;seq&#39;, sid &amp; 0xFFF)\nprint(&#39;bits&#39;, sid.bit_length())", "note": "范围分片、哈希分片与一致性哈希的迁移量"}]' title='两种写法对照' note='差异集中在 自增 ID 的局限；先看输出，再找背后的规则。' />

```python
class Gen:
    def __init__(self):
        self.last = 0
    def next(self, now_ms):
        if now_ms < self.last:
            return 'clock_backwards'
        self.last = now_ms
        return now_ms

g = Gen()
print(g.next(1000))
print(g.next(999))
print(g.next(1001))
```

<OutputBox title='原理验证' output='1000\nclock_backwards\n1001' />


## 热点、倾斜与再平衡的工程判据

分片不是选完键就结束。要按主查询维度选键：若绝大多数请求带 `user_id`，就用它做分片键并把关联数据共置（colocation），避免跨片 join；若主要按时间范围分析，则范围分片加预分区更合适，同时用写入打散（如加随机前缀）压热点。

监控要落在可核对的指标上：各片 QPS 与存储量的最大最小比、p99 延迟的分片分布、扩容期间迁移 key 数与耗时。再平衡要限速、可回滚、可断点续传，迁移期间用双写或读时路由兼容新旧落点，并校验数据指纹。

哈希环的虚拟节点数不是越大越好：V 增大让分布更均匀，但环的维护、成员变更广播与 bisect 数组都变长，通常取到分布方差收敛即可。时钟回拨要有硬监控：生成器记录 `last_ts`，回拨超过阈值直接熔断并告警，而不是静默等待。

**分片策略对照**

| 策略 | 写入分布 | 范围查询 | 扩容迁移量 |
| --- | --- | --- | --- |
| 范围分片 | 易集中到最新片形成热点 | 可定位少数片 | 按分裂段迁移，可控 |
| hash(key) % N | 均匀 | 退化为全片 scatter-gather | 约 N/(N+1)，八扩九约 89% |
| 一致性哈希 | 均匀（带虚拟节点） | 仍需全片扫描 | 约 1/(N+1)，四扩五约 20% |
| 一致性哈希 + 虚拟节点 | 按权重可调均匀 | 仍需全片扫描 | 同上，且分布方差更小 |

取模分片把 key 落点定义成 `hash(key) mod N`，N 一变就会改变几乎所有 key 的余数，因此扩容迁移量是 `N/(N+1)`。

一致性哈希把节点坐标与 key 坐标放在同一个 2^32 环上，key 归属顺时针的后继节点；新增节点只在环上切走它与前驱之间的一段弧，落在这段弧上的 key 才需要迁移，比例收敛到 `1/(N+1)`。

虚拟节点把每个物理节点散列成 `replicas` 个点，等价于把环切成更细的等份，使各物理节点承担的弧长方差下降，也让按权重调整落点成为可能；代价是坐标数组变长，查找仍是 `O(log V)`。

Snowflake 用位运算把时间、机器、序列压进一个 64 位整数，靠高位时间戳保证趋势递增、靠机器位保证跨节点不冲突、靠序列位吸收同毫秒并发，因此它隐含三个前提：时钟单调、worker id 全局唯一、单毫秒并发不超 4096，任一前提被破坏都需要显式熔断，而不是继续发号。

**哈希环关键参数与复杂度**

| 参数 / 操作 | 典型值或复杂度 | 说明 |
| --- | --- | --- |
| 虚拟节点 replicas | 100 到 300 | 越大分布越均匀，环维护成本越高 |
| node_for 查找 | O(log V) | V 为虚拟节点总数，bisect_left 加回绕取模 |
| add 插入 | O(V) | bisect.insort 在有序数组插入并搬移 |
| 迁移比例监控 | moved / total | 与 1/(N+1) 对比可发现实现错误 |


## 带迁移量监控的可扩容分片路由

线上分片路由不能只看命中是否正确，还要能回答加一台机器到底搬了多少数据。下面这段把一致性哈希环封装成 `route` 组件，提供 `add_node` 时统计归属变化的能力，并给雪花生成器加时钟回拨熔断。真实系统里节点坐标来自配置中心，key 前缀对应业务实体，迁移统计打到指标系统，双写与数据指纹校验放在再平衡流程里。

重点是把扩容这个高风险动作变成可量化、可断言的操作：迁移比例若显著偏离 `1/(N+1)`，立即中止，而不是让流量慢慢错乱。

```python
import hashlib, bisect

def h(s):
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)

class Router:
    def __init__(self, nodes, replicas=128):
        self.replicas = replicas
        self.ring = []
        self.owner = {}
        for n in nodes:
            self.add_node(n)
    def add_node(self, n):
        for i in range(self.replicas):
            p = h(n + ':' + str(i))
            bisect.insort(self.ring, p)
            self.owner[p] = n
    def node_for(self, key):
        p = h(key)
        idx = bisect.bisect_left(self.ring, p) % len(self.ring)
        return self.owner[self.ring[idx]]

keys = ['user:' + str(i) for i in range(5000)]
r = Router(['a', 'b', 'c'])
before = {k: r.node_for(k) for k in keys}
r.add_node('d')
changed = sum(1 for k in keys if r.node_for(k) != before[k])
print('migration_ratio', round(changed / len(keys), 3))
```

<Callout type="idea" title='落地提示' text='按主查询维度选分片键，预留虚拟节点与再平衡方案，ID 生成器处理时钟回拨并监控' />

<CheckList id='P108b' title='上线前自检' :items='["能复现并解释「用随机 ID 做分片键却按时间范围查询」", "能复现并解释「hash(key) % N 分片的集群直接扩到 N+1 片」", "能复现并解释「雪花生成器遇到时钟回拨仍继续发号」", "能用一条命令验证 自增 ID 的局限", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 自增 ID 的局限 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用随机 ID 做分片键却按时间范围查询 | 哈希分布没有任何时间局部性，范围条件无法定位到少数片，只能对全部分片各查一次再归并 | 按主查询维度选键；确需时间查询就改用范围分片加预分区，或另建按时间组织的索引表 |
| hash(key) % N 分片的集群直接扩到 N+1 片 | 取模落点几乎全变，约 N/(N+1) 的数据要搬迁，八扩九接近九成，迁移期间双写与校验压力巨大 | 改用一致性哈希加虚拟节点，把迁移量压到约 1/(N+1)，并限速可回滚地再平衡 |
| 雪花生成器遇到时钟回拨仍继续发号 | 当前时间小于 last_ts 时，同一毫秒段可能重放已用过的序列，生成与几秒前重复的 ID 触发主键冲突 | 记录 last_ts，检测到回拨即拒绝服务并告警，超过阈值直接熔断，等待追平后再恢复 |


## 动手练一练与自测

<Exercise title='基础：反解雪花 ID 的各字段' task='给定 (ts_ms &lt;&lt; 22) | (worker &lt;&lt; 12) | seq 生成的 ID，用位移与掩码还原时间戳、机器号、序列号，并解释 0x3FF 与 0xFFF 的来历。' solution='sid = (1700000000000 &lt;&lt; 22) | (7 &lt;&lt; 12) | 9\nprint(sid &gt;&gt; 22)\nprint((sid &gt;&gt; 12) &amp; 0x3FF)\nprint(sid &amp; 0xFFF)' explain='0x3FF 是 10 位全 1 掩码，对应 10 位机器标识；0xFFF 是 12 位全 1 掩码，对应 12 位序列。位移先把目标字段挪到最低位再用掩码截出。' />

<Exercise title='进阶：对比取模分片与一致性哈希的迁移量' task='分别实现 hash(k) % N 与一致性哈希（带 100 虚拟节点）对同一批 2000 个 key 的落点，统计从 3 节点扩到 4 节点各需迁移多少 key，并解释差异来源。' solution='import hashlib\ndef h(s):\n    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16)\nks = [&#39;k&#39; + str(i) for i in range(2000)]\nmod3 = {k: h(k) % 3 for k in ks}\nmod4 = {k: h(k) % 4 for k in ks}\nprint(&#39;mod_moved&#39;, sum(mod3[k] != mod4[k] for k in ks))\nprint(&#39;mod_ratio&#39;, round(sum(mod3[k] != mod4[k] for k in ks) / len(ks), 3))' explain='取模分片的落点由 N 决定，N 变化几乎重排全部 key，迁移比例接近 N/(N+1)；一致性哈希只让新增节点接管环上一段弧，迁移比例约 1/(N+1)。' />

<Quiz no='108-1' q='把 8 片 hash(key) % 8 集群扩到 9 片，预期迁移比例最接近？' :options='["约 89%，因为 N/(N+1) 的落点会改变", "约 11%，只影响新片", "0%，取模结果不变", "100%，必须重建全表"]' answer="0" explain='取模从 8 到 9，只有 hash 值同时满足两种余数解释的 key 才不动，变化比例接近 N/(N+1) = 8/9，约 89%。' />

<Quiz no='108-2' q='一致性哈希引入虚拟节点的主要收益是？' :options='["让各物理节点承担的环上区间更均匀，并支持按权重调整", "消除范围查询的全片扫描", "把查找复杂度从 O(log V) 降到 O(1)", "让扩容迁移量变成 0"]' answer="0" explain='虚拟节点把每个物理节点散列成多个点，降低弧长分布的方差，也能用 replicas 表达权重；它不改变查找复杂度，也不消除范围查询的 scatter-gather。' />

<Quiz no='108-3' q='Snowflake 生成器检测到时钟回拨时，正确做法是？' :options='["拒绝发号并告警，超过阈值直接熔断", "继续发号，靠数据库唯一索引兜底", "把 worker id 自增一位避开冲突", "忽略回拨，时间戳取上次值加一"]' answer="0" explain='回拨会让同一毫秒段重放已用过的序列，可能生成重复 ID。必须停止发号并告警，静默继续或仅靠唯一索引都会把冲突推到写入阶段。' />

<KnowledgeCard :points='["`AUTO_INCREMENT` 跨片不保证唯一有序，还泄露业务量；雪花 64 位 = 1 符号位 + 41 时间戳 + 10 机器 + 12 序列", "雪花落地为 `(ts&lt;&lt;22)|(worker&lt;&lt;12)|seq`；时钟回拨必须拒绝发号，worker id 靠 etcd / 配置中心保证唯一", "范围分片利于范围查询但写入聚到新片；`hash(key) % N` 打散写入却让范围查询退化成 scatter-gather", "取模扩容迁移量 `N/(N+1)`（八扩九约 89%）；一致性哈希 `1/(N+1)`（四加一约 20%）", "虚拟节点 `replicas` 个（常见 100-300）压倾斜，`bisect_left` 查找 `O(log V)`，V 取到分布方差收敛即可", "按主查询维度选键、`user_id` 共置关联数据；再平衡限速可回滚，`last_ts` 回拨熔断，迁移比例偏离即中止"]' :pitfalls='["用随机 ID 做分片键却按时间范围查询", "hash(key) % N 分片的集群直接扩到 N+1 片", "雪花生成器遇到时钟回拨仍继续发号", "用随机 ID 做分片却按时间范围查询，会变成全片扫描；时钟回拨还可能让雪花 ID 重复"]' summary='分片键决定了系统能扩到多大：选错键会让所有请求落到同一片，加机器也毫无收益' />

1. `AUTO_INCREMENT` 跨片不保证唯一有序，还泄露业务量；雪花 64 位 = 1 符号位 + 41 时间戳 + 10 机器 + 12 序列

2. 雪花落地为 `(ts<<22)|(worker<<12)|seq`；时钟回拨必须拒绝发号，worker id 靠 etcd / 配置中心保证唯一

3. 范围分片利于范围查询但写入聚到新片；`hash(key) % N` 打散写入却让范围查询退化成 scatter-gather

[下一讲：Raft 共识、服务发现与配置中心](/distributed/consensus)

<Predict no='108-4' q='三节点一致性哈希环加一个节点后，2000 个 key 的迁移比例最可能是？' :options='["约 0.27，接近理论值 0.25", "约 0.89，与取模分片相同", "0，加节点不影响已有 key"]' answer='0' output='0.273（moved 546，ratio 0.273）' explain='新节点只接管环上它与前驱之间的一段弧，理论迁移量 1/(N+1) = 1/4 = 0.25；虚拟节点数量有限带来少量偏差，实测 0.273。' />

<FillBlank no='108-5' tpl='___ hashlib, bisect' :answers='["import"]' hint='回想本讲关于 自增 ID 的局限 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 自增 ID 的局限与雪花算法的位布局 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/108-sharding.py`

```bash
python3 examples/lessons/108-sharding.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/108-sharding.py) · [全部示例代码索引](/examples/)
