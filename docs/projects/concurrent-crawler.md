---
title: 第 128 讲 · 实战 07 · 并发爬虫与分布式调度
description: 把单机采集演进成可调度的分布式系统
---

<StageHeader stage='L12 · 工程实战' level='★★★★☆' time='55 分钟' goal='把单机采集演进成可调度的分布式系统' prereq='第 127 讲 · 实战 06 · 日志 ETL 与 CSV / SQL 查询工具' />

# 第 128 讲 · 实战 07 · 并发爬虫与分布式调度

上一讲把单机管道做稳了；这一讲把采集摊到多个 worker 上，本以为吞吐翻倍，先来的却是单机没有的麻烦——重复、乱序、部分失败和节点失联。

多节点后重复抓取涨到三成——每台各记一份已抓集合，同一批 URL 被反复请求；某台半夜掉线，取走却没确认的任务就此消失；没限速，短时间对同一域名发了几千次请求，被挡在门外。我们先立一条串行基线，再换 `asyncio` 配连接池与限流，接着用布隆过滤和最小堆做 URL 去重与优先级，最后靠任务队列的 `ack` 与断点快照补齐。需要你熟悉 `asyncio`、集合与哈希；学完能回答「节点崩了任务会不会丢」。


## 分布式化之后，新增的不是「更快的抓取」

把单机爬虫改成多 worker 分布式调度后，团队期待吞吐翻倍，结果监控里重复抓取率涨到 30%：每个节点各维护一份已抓集合，同一批 URL 被不同 worker 反复请求；某台节点半夜崩溃，它从队列取走但没确认的任务就此消失，第二天补数怎么都对不齐。还因为没做限速，短时间对同一个域名发了几千个请求，被对方直接封了 IP。

朴素解法「多开几个进程 + 内存 set 去重」失败在三点：去重集合没有共享、任务取出即丢失缺少确认机制、频率与优先级没有统一约束。分布式化之后新增的不是「更快的抓取」，而是重复、乱序、部分失败与节点失联。这一讲用标准库搭出布隆去重、优先队列、`asyncio` 限流、`ack` 出队与断点快照的最小可运行骨架。

<ConceptDiagram type='hub4' title='第 128 讲 · 串行到 asyncio：连接池、限流与合规默认值' labels='串行到 asyncio：连接池、限流与合规默|URL 去重与优先级：布隆过滤与最小堆|任务队列、ack、断点续爬与监控' caption='把单机采集演进成可调度的分布式系统' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 串行基线到 asyncio：连接池、限流与合规默认值

串行 `requests` 的耗时是所有 RTT 之和，吞吐被单连接往返卡住。

`asyncio` 配 `aiohttp.ClientSession` 用单线程事件循环把等待重叠：`TCPConnector` 用 `limit` 与 `limit_per_host` 限制总连接与单主机连接，`Semaphore` 限制在途协程数，`ClientTimeout` 必须显式给出总超时与连接超时，否则一个慢响应会占住连接与协程。

`asyncio.gather` 保留结果顺序，但默认只要有协程抛异常，异常就立刻向外传播、其余任务的结果不再被收集，批量抓取应传 `return_exceptions=True` 把失败当结果收下，或改用 3.11 起的 `TaskGroup` 统一管理生命周期。

连接复用靠 keep-alive 与 DNS 缓存，别为每个 URL 新建 `Session`。

合规要写成默认策略：用 `urllib.robotparser.RobotFileParser` 读 `robots.txt`、按域名设最小请求间隔、带清楚标识的 User-Agent、对 `429` 与 `5xx` 做指数退避与重试上限。

三个失效信号：某域名 QPS 突增触发封禁、在途任务数无限上涨、慢请求拖垮整个事件循环。

**并发模型与限流参数**

| 组件 | 参数 / 默认值 | 作用 | 缺失后果 |
| --- | --- | --- | --- |
| aiohttp.TCPConnector | limit=100, limit_per_host=0(不限) | 限制总连接与单主机连接 | 单域名被打满触发封禁 |
| asyncio.Semaphore(n) | 自定义在途上限 | 限制并发协程数 | 在途任务无限堆积 |
| aiohttp.ClientTimeout | total 默认 300 秒 | 给等待设上界 | 慢请求拖垮事件循环 |
| asyncio.gather | return_exceptions=False | 并发收集且保留顺序 | 一个异常取消全部任务 |
| RobotFileParser | 读 robots.txt | 合规默认策略 | 抓禁止路径引发法律风险 |

```python
import asyncio, hashlib, heapq

class Bloom:
    def __init__(self, size, k):
        self.size, self.k, self.bits = size, k, [0] * size
    def _slots(self, s):
        for i in range(self.k):
            yield int(hashlib.md5((str(i) + s).encode()).hexdigest(), 16) % self.size
    def add(self, s):
        for p in self._slots(s):
            self.bits[p] = 1
    def maybe_seen(self, s):
        return all(self.bits[p] for p in self._slots(s))

feed = [(2, '/a'), (1, '/b'), (2, '/a'), (0, '/c'), (1, '/b'), (3, '/d')]
bloom = Bloom(size=128, k=2)
queue, unique = [], []
for pri, u in feed:
    if bloom.maybe_seen(u):
        continue
    bloom.add(u)
    unique.append(u)
    heapq.heappush(queue, (pri, u))
print('unique', unique)
print('priority order', [heapq.heappop(queue)[1] for _ in range(len(queue))])

async def crawl(urls, limit):
    sem = asyncio.Semaphore(limit)
    async def one(u):
        async with sem:
            await asyncio.sleep(0)
            return u.upper()
    return await asyncio.gather(*(one(u) for u in urls))
print('fetched', asyncio.run(crawl(unique, 2)))
```

<OutputBox title='主示例运行结果' output='unique [&#39;/a&#39;, &#39;/b&#39;, &#39;/c&#39;, &#39;/d&#39;]\npriority order [&#39;/c&#39;, &#39;/b&#39;, &#39;/a&#39;, &#39;/d&#39;]\nfetched [&#39;/A&#39;, &#39;/B&#39;, &#39;/C&#39;, &#39;/D&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import asyncio, hashlib, heapq\n\nclass Bloom:\n    def __init__(self, size, k):\n        self.size, self.k, self.bits = size, k, [0] * size\n    def _slots(self, s):\n        for i in range(self.k):\n            yield int(hashlib.md5((str(i) + s).encode()).hexdigest(), 16) % self.size\n    def add(self, s):\n        for p in self._slots(s):\n            self.bits[p] = 1\n    def maybe_seen(self, s):\n        return all(self.bits[p] for p in self._slots(s))\n\nfeed = [(2, &#39;/a&#39;), (1, &#39;/b&#39;), (2, &#39;/a&#39;), (0, &#39;/c&#39;), (1, &#39;/b&#39;), (3, &#39;/d&#39;)]\nbloom = Bloom(size=128, k=2)\nqueue, unique = [], []\nfor pri, u in feed:\n    if bloom.maybe_seen(u):\n        continue\n    bloom.add(u)\n    unique.append(u)\n    heapq.heappush(queue, (pri, u))\nprint(&#39;unique&#39;, unique)\nprint(&#39;priority order&#39;, [heapq.heappop(queue)[1] for _ in range(len(queue))])\n\nasync def crawl(urls, limit):\n    sem = asyncio.Semaphore(limit)\n    async def one(u):\n        async with sem:\n            await asyncio.sleep(0)\n            return u.upper()\n    return await asyncio.gather(*(one(u) for u in urls))\nprint(&#39;fetched&#39;, asyncio.run(crawl(unique, 2)))' :notes='["导入 asyncio 做并发、hashlib 造多哈希、heapq 做优先队列", "Bloom 是概率型去重结构，用比特数组表示见过哪些 URL", "构造时记下位数 m、哈希个数 k，并初始化全 0 比特数组", "把三个参数压缩到一行，bits 即长度 size 的列表", "_slots 生成 k 个哈希位置，是布隆过滤的核心", "用不同前缀 i 区分 k 个独立哈希", "md5 前缀加 URL 后取十六进制转整数，再对 size 取模得位置", "add 把某个 URL 对应的所有位置置 1", "遍历该 URL 的每个哈希位置", "置位为 1，表示已见过", "maybe_seen 判断所有位是否都已置 1", "全为 1 才返回 True，故存在误判可能但不会漏判", "模拟待抓 feed，含重复 /a 与 /b，优先级是元组第一项", "m=128、k=2 的布隆，参数决定误判率", "queue 是最小堆，unique 记录首次出现的 URL", "按 feed 顺序处理每条 (优先级, URL)", "布隆说见过就跳过，重复项在此被挡掉", "跳过重复 URL，不进入优先队列", "首次见到的 URL 加入布隆，置位所有哈希位置", "记录到 unique，作为本次真正要抓的集合", "按 (priority, url) 压入最小堆，O(log n)", "打印去重结果，四个不同 URL 各出现一次", "依次弹堆，验证数字小的优先级先出队", "crawl 是 asyncio 并发抓取骨架，limit 控制在途数", "在事件循环内创建 Semaphore，避免绑定未运行的 loop", "one 是单个抓取协程，模拟一次网络往返", "async with sem 把并发限制在 limit 以内", "await 让出事件循环，模拟等待网络响应", "返回处理后的结果，保持与输入一一对应", "gather 并发跑全部协程并按输入顺序收集结果", "用 asyncio.run 启动事件循环，打印抓取结果"]' title='第 128 讲 · 实战 07 · 并发爬虫与分布式调度' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：无限速猛抓同一域名与 Semaphore 限流

```python
from collections import deque

class Queue:
    def __init__(self):
        self.pending = deque()
        self.inflight = {}
        self.done = []
    def push(self, items):
        for i in items:
            self.pending.append(i)
    def take(self):
        item = self.pending.popleft()
        self.inflight[item] = 'taken'
        return item
    def ack(self, item):
        self.inflight.pop(item, None)
        self.done.append(item)

q = Queue()
q.push(['/a', '/b', '/c'])
job = q.take()
q.ack(job)
print('acked', q.done, 'inflight', list(q.inflight))
lost = q.take()
print('unacked inflight', lost, list(q.inflight))
q.pending.appendleft(lost)
del q.inflight[lost]
print('requeued', list(q.pending))
```

<OutputBox title='对照写法：先自己猜，再点开' output='acked [&#39;/a&#39;] inflight []\nunacked inflight /b [&#39;/b&#39;]\nrequeued [&#39;/b&#39;, &#39;/c&#39;]' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import asyncio, hashlib, heapq\n\nclass Bloom:\n    def __init__(self, size, k):\n        self.size, self.k, self.bits = size, k, [0] * size\n    def _slots(self, s):\n        for i in range(self.k):\n            yield int(hashlib.md5((str(i) + s).encode()).hexdigest(), 16) % self.size\n    def add(self, s):\n        for p in self._slots(s):\n            self.bits[p] = 1\n    def maybe_seen(self, s):\n        return all(self.bits[p] for p in self._slots(s))\n\nfeed = [(2, &#39;/a&#39;), (1, &#39;/b&#39;), (2, &#39;/a&#39;), (0, &#39;/c&#39;), (1, &#39;/b&#39;), (3, &#39;/d&#39;)]\nbloom = Bloom(size=128, k=2)\nqueue, unique = [], []\nfor pri, u in feed:\n    if bloom.maybe_seen(u):\n        continue\n    bloom.add(u)\n    unique.append(u)\n    heapq.heappush(queue, (pri, u))\nprint(&#39;unique&#39;, unique)\nprint(&#39;priority order&#39;, [heapq.heappop(queue)[1] for _ in range(len(queue))])\n\nasync def crawl(urls, limit):\n    sem = asyncio.Semaphore(limit)\n    async def one(u):\n        async with sem:\n            await asyncio.sleep(0)\n            return u.upper()\n    return await asyncio.gather(*(one(u) for u in urls))\nprint(&#39;fetched&#39;, asyncio.run(crawl(unique, 2)))", "note": "串行到 asyncio：连接池、限流与合规默认值"}, {"label": "对照 / 进阶", "code": "from collections import deque\n\nclass Queue:\n    def __init__(self):\n        self.pending = deque()\n        self.inflight = {}\n        self.done = []\n    def push(self, items):\n        for i in items:\n            self.pending.append(i)\n    def take(self):\n        item = self.pending.popleft()\n        self.inflight[item] = &#39;taken&#39;\n        return item\n    def ack(self, item):\n        self.inflight.pop(item, None)\n        self.done.append(item)\n\nq = Queue()\nq.push([&#39;/a&#39;, &#39;/b&#39;, &#39;/c&#39;])\njob = q.take()\nq.ack(job)\nprint(&#39;acked&#39;, q.done, &#39;inflight&#39;, list(q.inflight))\nlost = q.take()\nprint(&#39;unacked inflight&#39;, lost, list(q.inflight))\nq.pending.appendleft(lost)\ndel q.inflight[lost]\nprint(&#39;requeued&#39;, list(q.pending))", "note": "URL 去重与优先级：布隆过滤与最小堆"}]' title='两种写法对照' note='差异集中在 串行基线到 asyncio；先看输出，再找背后的规则。' />


## URL 去重与优先级：布隆过滤与最小堆

去重前先规范化 URL：去掉 fragment、按字典序排 query、host 转小写、默认端口归一化，否则同一个页面会有多种写法绕过去重。

共享去重可用 Redis 的 `SETNX`（精确、可计数）或布隆过滤（省内存）：布隆用 m 位比特数组加 k 个独立哈希，插入 n 个元素后的误判率约 `(1 - e^(-kn/m))^k`，只增不删（要删用 Counting Bloom），因此它「说没见过一定没见过、说见过可能误判」，工程上把误判当作少抓一个 URL 的代价，并在后端再做一次精确判重。

标准库可用 `hashlib.md5` 加不同前缀生成多个哈希位置。

优先级队列用 `heapq` 的最小堆：push 与 pop 都是 `O(log n)`，元素取 `(priority, url)` 元组，priority 数字越小越先抓；

若优先级可能相同，要插入序号变成 `(pri, seq, url)`，避免两个不可比较的对象触发 `TypeError`。

队列要定期快照到磁盘或 Redis，否则节点崩溃后优先级信息全部丢失。

**去重方案对照**

| 方案 | 内存 / 精度 | 能否删除 | 适用 |
| --- | --- | --- | --- |
| 内存 set | 精确，随 URL 数线性增长 | 能 | 单机、量小 |
| Redis SETNX | 精确，集中共享 | 能 | 多 worker 分布式 |
| 布隆过滤 | 省内存，有误判无漏判 | 不能（需 Counting Bloom） | 海量 URL 预筛 |
| 规范化 + 精确判重 | 精确 | 能 | 布隆之后的二次确认 |

```python
import math

def fp_rate(n, m, k):
    return (1 - math.exp(-k * n / m)) ** k

for n, m, k in [(4, 128, 2), (100, 1024, 3), (1000, 1024, 3)]:
    print('n', n, 'm', m, 'k', k, 'fp~', round(fp_rate(n, m, k), 4))
print('bits per item', round(1024 / 100, 2))
```

<OutputBox title='原理验证' output='n 4 m 128 k 2 fp~ 0.0037\nn 100 m 1024 k 3 fp~ 0.0164\nn 1000 m 1024 k 3 fp~ 0.8482\nbits per item 10.24' />


## 任务队列、ack 语义与断点续爬

分布式新增的四类问题要各自有机制。重复：消息是 at-least-once 投递，worker take 后任务进入 inflight 表，只有处理成功并 `ack` 才真正出队；节点崩溃时 inflight 里未确认的任务靠可见性超时或重启扫描重新入队，配合按 URL 主键 upsert 的幂等写入，重复抓取不会产生重复数据。

乱序：优先级只保证出队顺序，不保证完成顺序，结果表要带抓取时间戳。部分失败：失败的单个 URL 进失败队列并记录原因，不拖垮整批。节点失联：心跳与租约判定存活，定期把 done 集合与优先队列写成检查点（临时文件加原子 replace），重启从快照恢复，这就是断点续爬。

监控至少要有：在途任务数、重复率、失败率、每域名 QPS、队列积压、节点心跳与快照时间；压测时先看这些指标再决定加 worker 还是加限流。

<ArchBlueprint title='第 128 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "串行到 asyncio：连接池、限流与合规默认值", "protocol": "调用 / 请求", "items": [{"label": "串行到 asyncio：", "sub": "输入与前置", "detail": "串行 `requests` 的耗时是所有 RTT 之和，吞吐被单连接往返卡住。`asyncio` 配 `aiohttp.ClientSession` 用单线程事件循环把等待重叠：`TCPConnector` 用 `limit` 与 `limit_per_host` 限制总连接与单主机连接，`Sema", "tone": "blue"}]}, {"name": "核心规则", "note": "URL 去重与优先级：布隆过滤与最小堆", "protocol": "语言 / 运行时协议", "items": [{"label": "URL 去重与优先级：布", "sub": "状态与边界", "detail": "去重前先规范化 URL：去掉 fragment、按字典序排 query、host 转小写、默认端口归一化，否则同一个页面会有多种写法绕过去重。共享去重可用 Redis 的 `SETNX`（精确、可计数）或布隆过滤（省内存）：布隆用 m 位比特数组加 k 个独立哈希，插入 n 个元素后的误判率约 `(", "tone": "purple"}]}, {"name": "落地与收尾", "note": "任务队列、ack、断点续爬与监控", "items": [{"label": "任务队列、ack、断点续", "sub": "工程处理", "detail": "分布式新增的四类问题要各自有机制。重复：消息是 at-least-once 投递，worker take 后任务进入 inflight 表，只有处理成功并 `ack` 才真正出队；节点崩溃时 inflight 里未确认的任务靠可见性超时或重启扫描重新入队，配合按 URL 主键 upsert 的幂等写", "tone": "green"}]}]' />


## 事件循环与 Semaphore 的等待者队列

`asyncio` 用单线程事件循环加 selector 把大量 IO 等待重叠，`Semaphore` 内部是计数器加等待者队列，acquire 减到 0 时后续协程挂起，`await` 把控制权交回循环；因此并发上限由 `Semaphore` 与连接器 `limit` 共同决定，超时则决定慢请求不会永久占住槽位。

布隆过滤的误判率来自 k 个哈希独立置位的假设：某位仍为 0 的概率是 `e^(-kn/m)`，全被置 1 的概率是 `(1 - e^(-kn/m))^k`；

它只会出现「误判为见过」的假阳性，不会漏判，因此适合做预筛，后面仍需一次精确判重。

`heapq` 用数组表示二叉最小堆，push/pop 都是 `O(log n)`，元组比较按字典序逐项进行，所以 `(pri, seq, url)` 的序号能避免优先级相同时比较不可排序对象。

分布式队列的 at-least-once 语义意味着任务可能被投递多次，只有「`ack` 后出队」加「按主键 upsert 的幂等写入」才能把重复投递收敛成一致结果；检查点用临时文件加原子 replace，保证快照不会是半截状态。

<Term word='串行基线到 asyncio' text='串行 `requests` 的耗时是所有 RTT 之和，吞吐被单连接往返卡住。`asyncio` 配 `aiohttp.ClientSession` 用单线程事件循环把等待重叠：`TCPConnector` 用 `limit` 与 `limit_per_host` 限制总连接与单主机连接，`Semaphore` 限制在' />

<Term word='连接池与限流' text='去重前先规范化 URL：去掉 fragment、按字典序排 query、host 转小写、默认端口归一化，否则同一个页面会有多种写法绕过去重。共享去重可用 Redis 的 `SETNX`（精确、可计数）或布隆过滤（省内存）：布隆用 m 位比特数组加 k 个独立哈希，插入 n 个元素后的误判率约 `(1 - e^(-kn' />


## 去重方案对照：内存 set 与布隆过滤的边界

**分布式失败模式与防线**

| 现象 | 根因 | 防线 |
| --- | --- | --- |
| 多 worker 重复抓同一 URL | 各节点各持一份去重集合 | 共享去重：Redis SETNX 或布隆过滤 |
| 节点崩溃后任务永久丢失 | 取出即出队、无确认机制 | inflight + ack 后出队，未确认靠超时重投 |
| 重投产生重复数据 | 写库无幂等 | 按 URL 主键 upsert |
| 优先级与完成顺序错乱 | 并发不保证完成顺序 | 结果带抓取时间戳，优先级只管出队 |
| 重启后从头再抓 | 无检查点 | 定期快照 done 集合与优先队列，原子 replace |


## 分布式失败模式与防线

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 多 worker 各用内存 set 去重，重复抓取率飙升 | 去重集合没有共享，同一 URL 在不同节点都被判定为首次 | 改用 Redis SETNX 或共享布隆过滤，布隆之后再做一次精确判重 |
| 任务取出即出队，节点崩溃后任务永久丢失 | 没有 inflight 与确认机制，取出与完成之间发生故障就无从恢复 | worker take 后进 inflight、成功才 ack 出队，未确认任务靠可见性超时或重启扫描重新入队 |
| 不限速短时间猛抓同一域名，被封 IP | 没有每域名最小间隔、并发上限与退避，也没有读 robots.txt | 把 robots、limit_per_host、Semaphore 与 5xx/429 指数退避做成默认策略，并埋每域名 QPS 监控 |

<Callout type="warn" title='本讲最容易踩的坑' text='多 worker 各用内存 set 去重，重复抓取率飙升：去重集合没有共享，同一 URL 在不同节点都被判定为首次' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：多 worker 各用内存 set 去重，重", "body": "去重集合没有共享，同一 URL 在不同节点都被判定为首次", "tip": "改用 Redis SETNX 或共享布隆过滤，布隆之后再做一次精确判重"}, {"title": "第 2 步：任务取出即出队，节点崩溃后任务永久丢失", "body": "没有 inflight 与确认机制，取出与完成之间发生故障就无从恢复", "tip": "worker take 后进 inflight、成功才 ack 出队，未确认任务靠可见性超时或重启扫描重新入队"}, {"title": "第 3 步：不限速短时间猛抓同一域名，被封 IP", "body": "没有每域名最小间隔、并发上限与退避，也没有读 robots.txt", "tip": "把 robots、limit_per_host、Semaphore 与 5xx/429 指数退避做成默认策略，并埋每域名 QPS 监控"}]' />


## 监控与合规默认值

<CheckList id='P128b' title='上线前自检' :items='["能复现并解释「多 worker 各用内存 set 去重，重复抓取率飙升」", "能复现并解释「任务取出即出队，节点崩溃后任务永久丢失」", "能复现并解释「不限速短时间猛抓同一域名，被封 IP」", "能用一条命令验证 串行基线到 asyncio", "关键路径有自动化测试与失败分支"]' />


## 带优先级、ack 语义与断点快照的 worker

一个可调度的采集节点要满足三点：按优先级出队、只处理未完成的任务、崩溃后能从快照续跑。下面用标准库实现最小骨架：Worker 启动时从 `json` 检查点恢复 done 集合与 `heapq` 优先队列；`submit` 先查 done 再入堆；

`run` 弹出 n 个任务、把 URL 记入 done，并用「临时文件加 `Path.replace`」原子写回检查点；再次构造 Worker 即模拟节点重启，读回后发现已完成集合与剩余队列都被正确恢复。

真实项目把 done 换成 Redis 集合、给任务加 inflight 与 `ack`、用可见性超时重投未确认任务，并定期压缩快照。片段可直接运行，重点看快照如何把断点续爬变成可验证的行为。

```python
import heapq, json, tempfile
from pathlib import Path

def load_checkpoint(path):
    if not Path(path).exists():
        return {'done': [], 'queue': []}
    return json.loads(Path(path).read_text(encoding='utf-8'))

def save_checkpoint(path, done, queue):
    body = json.dumps({'done': done, 'queue': queue})
    tmp = path + '.tmp'
    Path(tmp).write_text(body, encoding='utf-8')
    Path(tmp).replace(path)

class Worker:
    def __init__(self, checkpoint):
        self.path = checkpoint
        state = load_checkpoint(checkpoint)
        self.done = set(state['done'])
        self.heap = list(state['queue'])
        heapq.heapify(self.heap)
    def submit(self, pri, url):
        if url not in self.done:
            heapq.heappush(self.heap, (pri, url))
    def run(self, n):
        out = []
        for _ in range(n):
            if not self.heap:
                break
            pri, url = heapq.heappop(self.heap)
            self.done.add(url)
            out.append(url)
        save_checkpoint(self.path, sorted(self.done), self.heap)
        return out

path = str(Path(tempfile.mkdtemp()) / 'ck.json')
w = Worker(path)
for pri, u in [(1, '/a'), (0, '/b'), (2, '/c')]:
    w.submit(pri, u)
print('batch1', w.run(2))
w2 = Worker(path)
print('resume done', sorted(w2.done))
print('remaining', [u for _, u in sorted(w2.heap)])
```

<Callout type="idea" title='落地提示' text='用布隆过滤或 Redis 去重、消息 ack 后出队、定期快照优先级队列，并把 robots 与限速做成默认策略' />

```bash
python -m compileall -q . && python -m pytest -q
```

把输入换成你自己的数据，观察结果是否仍符合 串行基线到 asyncio 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 动手练习、自测与速记

<Exercise title='基础：用布隆过滤做 URL 预去重' task='写一个 m=128、k=2 的布隆类（md5 加前缀造多哈希），对含重复项的 feed 打印去重后的列表，并说明为什么它不会漏判。' solution='import hashlib\nclass B:\n    def __init__(self, m, k):\n        self.m, self.k, self.bits = m, k, [0]*m\n    def slots(self, s):\n        return [int(hashlib.md5((str(i)+s).encode()).hexdigest(),16)%self.m for i in range(self.k)]\n    def seen(self, s):\n        return all(self.bits[p] for p in self.slots(s))\n    def add(self, s):\n        for p in self.slots(s): self.bits[p]=1\nb=B(128,2); out=[]\nfor u in [&#39;/a&#39;,&#39;/b&#39;,&#39;/a&#39;,&#39;/c&#39;]:\n    if not b.seen(u): b.add(u); out.append(u)\nprint(out)' explain='输出 [&#39;/a&#39;, &#39;/b&#39;, &#39;/c&#39;]。只有所有哈希位都为 1 才判见过，插入过的 URL 位必然全 1，故不会漏判；未插入的 URL 可能因位碰巧全 1 而误判。' />

<Exercise title='进阶：用 heapq 验证优先级出队顺序' task='把 (2,&#39;/a&#39;), (1,&#39;/b&#39;), (0,&#39;/c&#39;), (3,&#39;/d&#39;) 依次 heappush 再全部弹出，打印顺序并解释元组比较规则。' solution='import heapq\nq=[]\nfor pri,u in [(2,&#39;/a&#39;),(1,&#39;/b&#39;),(0,&#39;/c&#39;),(3,&#39;/d&#39;)]:\n    heapq.heappush(q,(pri,u))\nprint([heapq.heappop(q)[1] for _ in range(len(q))])' explain='输出 [&#39;/c&#39;, &#39;/b&#39;, &#39;/a&#39;, &#39;/d&#39;]。heapq 是最小堆，元组按字典序逐项比较，第一项 priority 越小越先弹出；同优先级才比第二项。' />

<Quiz no='128-1' q='关于布隆过滤，哪一项准确？' :options='["可能误判为见过，但不会把见过的判成没见过", "既能误判也能漏判", "支持删除单个元素", "误判率与插入元素个数无关"]' answer="0" explain='插入过的元素其 k 个哈希位必然全为 1，因此不会假阴性；未插入元素的位可能碰巧全 1 造成假阳性，误判率约 (1-e^(-kn/m))^k 随 n 增大而上升。' />

<Quiz no='128-2' q='分布式任务队列里，防止节点崩溃丢任务的机制是？' :options='["任务取出后进 inflight，处理成功才 ack 出队，未确认的靠超时重投", "取出即出队以提高吞吐", "每个节点各存一份队列副本", "把所有任务一次性发给一个 worker"]' answer="0" explain='at-least-once 投递下任务可能被投多次；inflight 加 ack 让未完成任务在崩溃后可被重新入队，再配合按主键 upsert 的幂等写入收敛重复。' />

<Quiz no='128-3' q='asyncio 批量抓取时，关于 gather 与限流哪项准确？' :options='["gather 保留结果顺序，默认一个异常会取消其余任务；并发还要靠 Semaphore 与超时约束", "gather 会按完成顺序返回结果", "Semaphore 只限制连接数不影响协程数", "不设超时只是稍慢，没有其它后果"]' answer="0" explain='gather 按输入顺序收集，return_exceptions 默认 False 时一个异常会传播并取消其余任务；Semaphore 限制在途协程，ClientTimeout 防止慢请求永久占住槽位。' />

<Predict no='128-4' q='对 (2,&#39;/a&#39;), (1,&#39;/b&#39;), (0,&#39;/c&#39;), (3,&#39;/d&#39;) 依次 heappush 再全部弹出，顺序是？' :options='["&#39;/c&#39;, &#39;/b&#39;, &#39;/a&#39;, &#39;/d&#39;", "&#39;/a&#39;, &#39;/b&#39;, &#39;/c&#39;, &#39;/d&#39;", "&#39;/d&#39;, &#39;/c&#39;, &#39;/b&#39;, &#39;/a&#39;"]' answer='0' output='priority order [&#39;/c&#39;, &#39;/b&#39;, &#39;/a&#39;, &#39;/d&#39;]' explain='heapq 是最小堆，按元组第一项 priority 升序弹出，同优先级才比较第二项；0 对应的 /c 最先出队，3 对应的 /d 最后。' />

<FillBlank no='128-5' tpl='import  ___ io, hashlib, heapq' :answers='["async"]' hint='回想本讲关于 串行基线到 asyncio 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 串行到 asyncio：连接池、限流与合规默认值 的落点。' />

<KnowledgeCard :points='["asyncio 用事件循环重叠 IO 等待；TCPConnector 的 limit/limit_per_host、Semaphore、ClientTimeout 三者共同约束并发", "URL 先规范化再去重；布隆误判率约 (1-e^(-kn/m))^k，只增不删，只做预筛需后端精确判重", "heapq 最小堆 push/pop 是 O(log n)，元素用 (pri, seq, url) 避免同优先级比较不可排序对象", "分布式队列 at-least-once：inflight + ack 后出队，未确认靠可见性超时重投，配 upsert 幂等写入", "断点续爬靠定期快照 done 集合与优先队列，临时文件加原子 replace 保证快照不半截", "robots.txt、按域名限速、User-Agent 标识、5xx/429 指数退避要做成默认策略并监控每域名 QPS"]' :pitfalls='["多 worker 各用内存 set 去重，重复抓取率飙升", "任务取出即出队，节点崩溃后任务永久丢失", "不限速短时间猛抓同一域名，被封 IP", "没有共享去重集合，多个 worker 会重复抓同一批 URL；节点崩溃后队列里的任务会永久丢失"]' summary='分布式化之后新增的不是「更快的抓取」，而是重复、乱序、部分失败与节点失联这些问题' />

1. asyncio 用事件循环重叠 IO 等待；TCPConnector 的 limit/limit_per_host、Semaphore、ClientTimeout 三者共同约束并发

2. URL 先规范化再去重；布隆误判率约 (1-e^(-kn/m))^k，只增不删，只做预筛需后端精确判重

3. heapq 最小堆 push/pop 是 O(log n)，元素用 (pri, seq, url) 避免同优先级比较不可排序对象

[下一讲：实战 08 · KV 贯穿线 ① 内存版与接口抽象](/projects/kv-memory)
