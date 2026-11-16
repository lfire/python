---
title: 第 092 讲 · 阶段综合：生产级短链服务
description: 把服务端各层串成一个可上线系统
---

<StageHeader stage='L8 · 服务端与数据' level='★★★★☆' time='60 分钟' goal='把服务端各层串成一个可上线系统' prereq='第 091 讲 · 文件、对象存储、搜索与 gRPC' />

# 第 092 讲 · 阶段综合：生产级短链服务

走到这里，路由、契约、推送、事务、缓存、队列、身份与存储都讲过一遍，却一直以单点的样子出现。这一讲是服务端阶段的阶段综合，用短链服务把这些层串成一条能上线的链路。

短链读多写少、缓存友好、可压测可灰度，正好当验收场：点击数据和第三方对不上，老用户改了目标地址还跳旧的，大促被刷接口打满发号器。我们从发号与 Base62、路由与重定向起步，说清 301 与 302 的取舍，再叠上缓存与限流、数据模型与索引，接着补埋点与监控，最后用压测得出单机容量。需要前面各讲，尤其幂等、缓存降级与状态码；做完后手上是一个分层清楚、可观测、能压测的系统。


## 短链上线后被刷接口，发号器先被打满

一个短链服务上线三个月，运营反馈点击数据和第三方统计对不上，有时一个用户点了三次只记了一次；SEO 同事发现把目标地址改了之后，老用户浏览器里还是跳到旧地址；大促时被刷接口打满发号器，正常用户创建短链全部超时。

复盘看到三处设计没定死：有人图省事用了 301 永久重定向，浏览器和 CDN 把结果强缓存，后续请求根本不回服务端，埋点自然缺失；发号与重定向、缓存、限流各写各的，没人说得清一次跳转经过哪些层；压测也没做过，扩容全凭感觉。短链是麻雀虽小五脏俱全的服务：读多写少、缓存友好、可压测、可灰度，正好把本阶段各层串起来验证。

本讲用 sqlite3 与标准库把发号、重定向、缓存、限流、埋点跑成一条可测的链路。

<Callout type="warn" title='先看一个真实会出错的写法' text='用 301 做短链重定向，点击统计对不上且改目标不生效：301 被浏览器与 CDN 强缓存，后续请求不再回源，服务端收不到埋点，旧目标也被长期记住' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段八 · 服务端与数据 |
| 前置 | 第 091 讲 · 文件、对象存储、搜索与 gRPC |
| 难度 / 建议时长 | ★★★★☆ · 60 分钟 |
| 本讲新增 | 发号与 Base62、路由与重定向、缓存与限流 |
| 一句话目标 | 把服务端各层串成一个可上线系统 |
| 为下一讲铺垫 | NumPy 向量化、广播与内存布局 |


## 发号与 Base62：把自增 ID 编成短码

核心是给长 URL 分配一个短码。用数据库自增主键发号最简：`INSERT` 一行拿 `lastrowid`，再把整数编成 62 进制（字符集 0-9a-zA-Z），`62^7≈3.5e12`，7 位足够容纳万亿级。

编码就是反复 `divmod(n, 62)` 取余查字符集，解码按位乘回；注意 `n=0` 要单独返回字符集首字符，否则 while 循环产出空串。

自增 ID 可预测、会暴露业务量，若要不可猜测可加一层混淆（与固定 mask 做 XOR 或用 Feistel 置换），或用雪花 ID（时间戳加机器位加序列）、号段模式（一次从 DB 取一段如 1000 个放内存分配）分散发号、避免单点。

短码列必须建 `UNIQUE` 索引，创建时把 code 与长 URL 一起落库；重复创建用幂等键返回同一 code，别生成两个短码指向同一 URL。还要给 links 表加 `created_at`、`expires_at` 支持过期短链，并预留状态位用于举报下线。

真正上线时发号器要压测出单机 QPS 上限，再决定号段大小与扩容方案。

**发号方案对照**

| 方案 | 优点 | 代价 |
| --- | --- | --- |
| DB 自增 id | 最简、有序、无冲突 | 可预测、暴露业务量、单点 |
| 自增 + 混淆(XOR/Feistel) | 不可猜测 | 需可逆映射与密钥管理 |
| 号段模式 | 一次取一段减 DB 压力 | 重启丢未用号段，需记录上限 |
| 雪花 ID | 分布式、趋势有序 | 依赖时钟，需处理回拨 |

<Callout type="tip" title='核心心智模型' text='核心是给长 URL 分配一个短码。用数据库自增主键发号最简：`INSERT` 一行拿 `lastrowid`，再把整数编成 62 进制（字符集 0-9a-zA-Z），`62^7≈3.5e12`，7 位足够容纳万亿级。编码就是反复 `divmod(n, 62)` 取余查字符集，解码按位乘回；注意…' />


## 主示例：一次发号到短码的编解码

```python
import sqlite3
ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
BASE = len(ALPHABET)
def to62(n):
    out = []
    while n:
        n, r = divmod(n, BASE)
        out.append(ALPHABET[r])
    return ''.join(reversed(out)) or '0'
db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE links (id INTEGER PRIMARY KEY, url TEXT, code TEXT UNIQUE, clicks INT DEFAULT 0)')
def create(url):
    oid = db.execute('INSERT INTO links (url, code) VALUES (?, ?)', (url, '')).lastrowid
    code = to62(oid)
    db.execute('UPDATE links SET code=? WHERE id=?', (code, oid))
    return code
def resolve(code):
    row = db.execute('SELECT url, clicks FROM links WHERE code=?', (code,)).fetchone()
    if row is None:
        return (404, None)
    db.execute('UPDATE links SET clicks=clicks+1 WHERE code=?', (code,))
    return (302, row[0])
c1 = create('https://example.com/a')
c2 = create('https://example.com/b')
print('codes', c1, c2)
print('big id', to62(3521614606207))
print('resolve', resolve(c1))
print('missing', resolve('zzzz'))
print('clicks', db.execute('SELECT clicks FROM links WHERE code=?', (c1,)).fetchone()[0])
```

<OutputBox title='主示例运行结果' output='codes 1 2\nbig id ZZZZZZZ\nresolve (302, &#39;https://example.com/a&#39;)\nmissing (404, None)\nclicks 1' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sqlite3\nALPHABET = &#39;0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ&#39;\nBASE = len(ALPHABET)\ndef to62(n):\n    out = []\n    while n:\n        n, r = divmod(n, BASE)\n        out.append(ALPHABET[r])\n    return &#39;&#39;.join(reversed(out)) or &#39;0&#39;\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE links (id INTEGER PRIMARY KEY, url TEXT, code TEXT UNIQUE, clicks INT DEFAULT 0)&#39;)\ndef create(url):\n    oid = db.execute(&#39;INSERT INTO links (url, code) VALUES (?, ?)&#39;, (url, &#39;&#39;)).lastrowid\n    code = to62(oid)\n    db.execute(&#39;UPDATE links SET code=? WHERE id=?&#39;, (code, oid))\n    return code\ndef resolve(code):\n    row = db.execute(&#39;SELECT url, clicks FROM links WHERE code=?&#39;, (code,)).fetchone()\n    if row is None:\n        return (404, None)\n    db.execute(&#39;UPDATE links SET clicks=clicks+1 WHERE code=?&#39;, (code,))\n    return (302, row[0])\nc1 = create(&#39;https://example.com/a&#39;)\nc2 = create(&#39;https://example.com/b&#39;)\nprint(&#39;codes&#39;, c1, c2)\nprint(&#39;big id&#39;, to62(3521614606207))\nprint(&#39;resolve&#39;, resolve(c1))\nprint(&#39;missing&#39;, resolve(&#39;zzzz&#39;))\nprint(&#39;clicks&#39;, db.execute(&#39;SELECT clicks FROM links WHERE code=?&#39;, (c1,)).fetchone()[0])' :notes='["导入 sqlite3，用内存库存短链与点击数", "定义 62 进制字符集，顺序决定短码字典序", "BASE 为字符集长度 62", "定义发号编码函数", "out 存放低位到高位的字符", "循环取余直到商为 0", "divmod 同时得到新商与余数", "用余数作下标取字符", "反转拼接；n=0 时回退到字符 &#39;0&#39;", "建立内存数据库连接", "links 表：自增 id 发号，code 唯一，clicks 计数", "创建短链函数，一次插入拿到自增 id", "INSERT 时 code 先留空，lastrowid 即发号结果", "把自增 id 编成 Base62 短码", "回填 code 到该行，code 列唯一约束防冲突", "返回短码", "解析函数，返回 (状态码, 目标 URL)", "按 code 查询目标与当前点击数", "若查询无结果则判定该 code 不存在", "查不到返回 404，不重定向", "命中则把点击数加 1，模拟同步埋点", "返回 302 临时重定向与目标 URL（不是 301）", "创建第一条短链，自增 id 为 1", "创建第二条短链，自增 id 为 2", "打印两条短码，分别是 &#39;1&#39; 与 &#39;2&#39;", "62^7-1 的编码是 7 个 Z，验证 7 位容量", "解析 c1，返回 302 与目标地址", "解析不存在的 code，返回 404", "读取点击数，验证跳转被记录了一次"]' title='第 092 讲 · 阶段综合：生产级短链服务' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import math

for n in (1000, 1000000, 1000000000):
    dec = len(str(n))
    b62 = math.ceil(math.log(n + 1, 62)) if n > 0 else 1
    print(n, 'decimal', dec, 'base62', b62)
```

<OutputBox title='原理验证' output='1000 decimal 4 base62 2\n1000000 decimal 7 base62 4\n1000000000 decimal 10 base62 6' />


### 对照：不同发号方案在扩容时的表现

```python
class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last = None
    def allow(self, now):
        if self.last is None:
            self.last = now
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

b = TokenBucket(rate=2, capacity=2)
t0 = 100.0
print('burst', [b.allow(t0) for _ in range(3)])
print('after 0.5s', b.allow(t0 + 0.5))
print('after 1.0s', b.allow(t0 + 1.0))
```

<OutputBox title='对照写法：先自己猜，再点开' output='burst [True, True, False]\nafter 0.5s True\nafter 1.0s True' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import sqlite3\nALPHABET = &#39;0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ&#39;\nBASE = len(ALPHABET)\ndef to62(n):\n    out = []\n    while n:\n        n, r = divmod(n, BASE)\n        out.append(ALPHABET[r])\n    return &#39;&#39;.join(reversed(out)) or &#39;0&#39;\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE links (id INTEGER PRIMARY KEY, url TEXT, code TEXT UNIQUE, clicks INT DEFAULT 0)&#39;)\ndef create(url):\n    oid = db.execute(&#39;INSERT INTO links (url, code) VALUES (?, ?)&#39;, (url, &#39;&#39;)).lastrowid\n    code = to62(oid)\n    db.execute(&#39;UPDATE links SET code=? WHERE id=?&#39;, (code, oid))\n    return code\ndef resolve(code):\n    row = db.execute(&#39;SELECT url, clicks FROM links WHERE code=?&#39;, (code,)).fetchone()\n    if row is None:\n        return (404, None)\n    db.execute(&#39;UPDATE links SET clicks=clicks+1 WHERE code=?&#39;, (code,))\n    return (302, row[0])\nc1 = create(&#39;https://example.com/a&#39;)\nc2 = create(&#39;https://example.com/b&#39;)\nprint(&#39;codes&#39;, c1, c2)\nprint(&#39;big id&#39;, to62(3521614606207))\nprint(&#39;resolve&#39;, resolve(c1))\nprint(&#39;missing&#39;, resolve(&#39;zzzz&#39;))\nprint(&#39;clicks&#39;, db.execute(&#39;SELECT clicks FROM links WHERE code=?&#39;, (c1,)).fetchone()[0])", "note": "发号与 Base62：把自增 ID 编成短码"}, {"label": "对照 / 进阶", "code": "class TokenBucket:\n    def __init__(self, rate, capacity):\n        self.rate = rate\n        self.capacity = capacity\n        self.tokens = float(capacity)\n        self.last = None\n    def allow(self, now):\n        if self.last is None:\n            self.last = now\n        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)\n        self.last = now\n        if self.tokens &gt;= 1:\n            self.tokens -= 1\n            return True\n        return False\n\nb = TokenBucket(rate=2, capacity=2)\nt0 = 100.0\nprint(&#39;burst&#39;, [b.allow(t0) for _ in range(3)])\nprint(&#39;after 0.5s&#39;, b.allow(t0 + 0.5))\nprint(&#39;after 1.0s&#39;, b.allow(t0 + 1.0))", "note": "重定向、缓存与限流：状态码要写进契约"}]' title='两种写法对照' note='差异集中在 发号与 Base62；先看输出，再找背后的规则。' />


## 永久重定向与临时重定向：状态码要写进契约

重定向状态码必须选对：301 Moved Permanently 会被浏览器与 CDN 强缓存，后续请求不再到服务端，点击统计直接失真，且一旦发错很难收回；302 Found（或 307、308 明确保持方法）是临时重定向，每次都回源，短链服务通常用 302 保证埋点准确且允许改目标。

读多写少，缓存友好：把 code 到 long_url 的映射放进 Redis 或本地 LRU，命中直接 302，未命中查库再回填；长 URL 变更要主动失效缓存，否则改了不生效。

限流保护发号器与查询接口：令牌桶（按 rate 补充令牌、capacity 允许一定突发）或滑动窗口，按 IP 或用户限流，超限返回 `429`；刷接口会打满发号器，必须在入口前置。

数据模型：links 表在 code 上建唯一索引，`expires_at` 支持过期；clicks 计数用异步埋点（先写 events 表或消息队列再批量汇总）而非每次同步 `UPDATE`，避免写放大把读路径拖慢。301 与 302 混用会让统计口径与 SEO 行为都不受控，这条要在接口契约里写死。

**301 与 302 的语义与短链取舍**

| 码 | 语义 | 缓存行为 | 短链适用 |
| --- | --- | --- | --- |
| 301 | Moved Permanently 永久 | 浏览器/CDN 强缓存，后续不回源 | 不适用，埋点丢失且改目标难收回 |
| 302 | Found 临时 | 每次回源 | 推荐，埋点准确、可改目标 |
| 307/308 | 临时/永久且保持方法 | 按语义缓存 | 需保持 POST 等方法时使用 |
| 404 | Not Found | 无 | code 不存在 |
| 429 | Too Many Requests | 无 | 限流触发 |


## 缓存、限流与创建幂等

每次跳转记一条事件：code、ts、ip 粗化、UA、referer、trace_id，先写本地队列或日志再批量入库，别让埋点阻塞重定向主链路；异步还要保证事件不丢（本地缓冲加重试）。

监控看四组指标：QPS 与 p99 延迟、缓存命中率、302/404/429 比例、发号器与 DB 连接池水位；短链被滥用做钓鱼时要接安全审核与举报下线。

压测得出单机容量：用固定并发逐步加压，记录 QPS 拐点与 p99 变化，据此决定扩容——无状态层水平扩、DB 读写分离、缓存分片；容量要落成数字（单机可维持 QPS 乘冗余系数），而不是凭感觉加机器。灰度与回滚：新版本先放小流量，代码保持对旧 code 兼容；缓存结构与 DB schema 变更要先迁移再发布。

埋点口径要和 302 的选择一起评审：用了 301 就等于主动放弃服务端点击数据，无论埋点代码写得多完整都补不回来。

<Callout type="warn" title='本讲最容易踩的坑' text='用 301 做短链重定向，点击统计对不上且改目标不生效：301 被浏览器与 CDN 强缓存，后续请求不再回源，服务端收不到埋点，旧目标也被长期记住' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 301 做短链重定向，点击统计对不上且改…", "body": "301 被浏览器与 CDN 强缓存，后续请求不再回源，服务端收不到埋点，旧目标也被长期记住", "tip": "统一用 302（或需保持方法时 307），把状态码写进接口契约；要改目标时 302 每次回源才生效"}, {"title": "第 2 步：创建短链不做幂等，同一长 URL 生成多个…", "body": "没有幂等键与限流，重复请求各插一行、刷接口直接耗尽发号 QPS", "tip": "创建接口接受幂等键，命中返回同一 code；入口用令牌桶按 IP 限流，超限返 429"}, {"title": "第 3 步：每次跳转同步 UPDATE clicks，读…", "body": "高频读请求夹带一次同步写，DB 写锁与连接池成为瓶颈", "tip": "埋点先写本地队列/日志再批量异步入库，clicks 用汇总表；把埋点移出重定向主链路并监控事件丢失"}]' />


### 为什么每次跳转同步 UPDATE clicks 会写放大

<ConceptDiagram type='layers3' title='第 092 讲 · 发号与 Base62：把自增 ID 编成短码' labels='发号与 Base62：把自增 ID 编成短码|重定向、缓存与限流：状态码要写进契约|埋点、监控、压测与容量|压测与容量' caption='把服务端各层串成一个可上线系统' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 读多写少下的分层与容量指标

**短链服务分层与容量指标**

| 层 | 职责 | 关键指标 |
| --- | --- | --- |
| 发号器 | 生成唯一 code | 单机 QPS、号段剩余量 |
| 重定向 | 302 + 埋点 | p99 延迟、302/404 比例 |
| 缓存 | code→url | 命中率、失效延迟 |
| 限流 | 令牌桶/滑动窗口 | 429 比例、突发容量 |
| 存储 | links 唯一索引 + events | 连接池水位、写入放大 |

<ArchBlueprint title='第 092 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "发号与 Base62：把自增 ID 编成短码", "protocol": "调用 / 请求", "items": [{"label": "发号与 Base62：把…", "sub": "输入与前置", "detail": "核心是给长 URL 分配一个短码。用数据库自增主键发号最简：`INSERT` 一行拿 `lastrowid`，再把整数编成 62 进制（字符集 0-9a-zA-Z），`62^7≈3.5e12`，7 位足够容纳万亿级。编码就是反复 `divmod(n, 62)` 取余查字符集，解码按位乘回；注意…", "tone": "blue"}]}, {"name": "核心规则", "note": "重定向、缓存与限流：状态码要写进契约", "protocol": "语言 / 运行时协议", "items": [{"label": "重定向、缓存与限流：状态…", "sub": "状态与边界", "detail": "重定向状态码必须选对：301 Moved Permanently 会被浏览器与 CDN 强缓存，后续请求不再到服务端，点击统计直接失真，且一旦发错很难收回；302 Found（或 307、308 明确保持方法）是临时重定向，每次都回源，短链服务通常用 302 保证埋点准确且允许改目标。读多写少，缓存…", "tone": "purple"}]}, {"name": "落地与收尾", "note": "埋点、监控、压测与容量", "items": [{"label": "埋点、监控、压测与容量", "sub": "工程处理", "detail": "每次跳转记一条事件：code、ts、ip 粗化、UA、referer、trace_id，先写本地队列或日志再批量入库，别让埋点阻塞重定向主链路；异步还要保证事件不丢（本地缓冲加重试）。监控看四组指标：QPS 与 p99 延迟、缓存命中率、302/404/429 比例、发号器与 DB 连接池水位；短链…", "tone": "green"}]}]' />


## 重定向链路的底层：缓存命中、限流与埋点

Base62 本质是进制转换：把自增整数反复 `divmod(n, 62)` 取余，余数作字符集下标，逆序拼接即短码；字符集 62 个字符决定每个码位携带 `log2(62)≈5.95` bit，7 位可表示 `62^7≈3.5e12` 个 id，比同长度十进制多装近一倍，这正是短链选择 62 进制而非十进制的原因。

用数据库自增主键发号把『唯一性』交给 B 树唯一索引与事务保证，避免分布式 ID 的冲突处理，代价是可预测——混淆层只是对整数做可逆置换，不改变底层发号。

301 与 302 的差别在缓存语义：301 的响应可被浏览器与 CDN 长期缓存，命中缓存的请求根本不到服务端，于是服务端埋点缺失、SEO 把永久跳转当作权威地址；302 每次回源，统计与改目标才可控。

令牌桶用『按固定速率补充、上限为 capacity』把平均速率与突发量解耦：tokens 随经过时间线性增长、每次请求扣 1、扣空即拒绝，因此既能限制长期 QPS 又允许短时突发，比固定窗口计数更平滑。读多写少场景下，缓存命中率与 302 回源率直接决定 DB 压力，容量必须靠压测测出拐点而非估计。

<Term word='发号与 Base62' text='核心是给长 URL 分配一个短码。用数据库自增主键发号最简：`INSERT` 一行拿 `lastrowid`，再把整数编成 62 进制（字符集 0-9a-zA-Z），`62^7≈3.5e12`，7 位足够容纳万亿级。编码就是反复 `divmod(n, 62)` 取余查字符集，解码按位乘回；注意 `n=0` 要单独返回字…' />

<Term word='路由与重定向' text='重定向状态码必须选对：301 Moved Permanently 会被浏览器与 CDN 强缓存，后续请求不再到服务端，点击统计直接失真，且一旦发错很难收回；302 Found（或 307、308 明确保持方法）是临时重定向，每次都回源，短链服务通常用 302 保证埋点准确且允许改目标。读多写少，缓存友好：把 code…' />

<FlowTimeline :steps='[{"title": "发号与 Base62：把自增 ID 编成短码", "desc": "核心是给长 URL 分配一个短码。用数据库自增主键发号最简：`INSERT` 一行拿…", "tone": "blue"}, {"title": "重定向、缓存与限流：状态码要写进契约", "desc": "重定向状态码必须选对：301 Moved Permanently 会被浏览器与 CD…", "tone": "purple"}, {"title": "埋点、监控、压测与容量", "desc": "每次跳转记一条事件：code、ts、ip 粗化、UA、referer、trace_i…", "tone": "orange"}, {"title": "工程落地", "desc": "把各层串起来的短链服务骨架", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 把各层串起来的短链服务骨架

下面把发号、Base62、302 重定向、缓存、令牌桶限流与异步埋点收进一个自包含服务：`create` 用幂等键去重、发号后回填 code 并写缓存；`resolve` 走缓存优先、命中即 302、同时把点击事件压进队列而不是同步写库；`create` 前先过令牌桶，超限返回 `429`。

`redirect` 返回的状态码固定 302，把上一条 pitfall 的修复落到代码里。真实项目把 `cache` 换成 Redis、把 `event_q` 换成消息队列消费者、把内存 sqlite 换成主从库并加唯一索引与 `expires_at`，但各层职责与数据流不变：这是本阶段服务端各讲的一次合流。

```python
import sqlite3
import collections

ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
def to62(n):
    out = []
    while n:
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return ''.join(reversed(out)) or '0'

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE links (id INTEGER PRIMARY KEY, code TEXT UNIQUE, url TEXT)')
db.execute('CREATE TABLE idem (k TEXT PRIMARY KEY, code TEXT)')
cache, event_q = {}, collections.deque()

class Bucket:
    def __init__(self, rate, cap):
        self.rate, self.cap, self.tokens, self.last = rate, cap, float(cap), None
    def allow(self, now):
        if self.last is None: self.last = now
        self.tokens = min(self.cap, self.tokens + (now - self.last) * self.rate)
        self.last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

limiter = Bucket(rate=2, cap=2)
def create(url, key, now):
    if not limiter.allow(now):
        return (429, None)
    row = db.execute('SELECT code FROM idem WHERE k=?', (key,)).fetchone()
    if row: return (200, row[0])
    oid = db.execute('INSERT INTO links (code, url) VALUES (?, ?)', ('', url)).lastrowid
    code = to62(oid)
    db.execute('UPDATE links SET code=? WHERE id=?', (code, oid))
    db.execute('INSERT INTO idem VALUES (?, ?)', (key, code))
    cache[code] = url
    return (201, code)

def resolve(code):
    url = cache.get(code)
    if url is None:
        r = db.execute('SELECT url FROM links WHERE code=?', (code,)).fetchone()
        if r is None: return (404, None)
        url = r[0]
        cache[code] = url
    event_q.append(code)
    return (302, url)

print(create('https://a', 'k1', 0.0))
print(create('https://a', 'k1', 0.0))
print(resolve('1'))
print('events', list(event_q))
```

<Callout type="idea" title='落地提示' text='读写分离缓存、幂等创建、可观测埋点，并用压测得出单机容量再决定扩容策略' />

<CheckList id='P092a' title='上线前自检' :items='["能复现并解释「用 301 做短链重定向，点击统计对不上且改目标不生效」", "能复现并解释「创建短链不做幂等，同一长 URL 生成多个 code，或被刷…」", "能复现并解释「每次跳转同步 UPDATE clicks，读路径被写放大拖慢」", "能用一条命令验证 发号与 Base62", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from urllib.parse import urlencode; print(urlencode({'page':2}))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 发号与 Base62 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 301 做短链重定向，点击统计对不上且改目标不生效 | 301 被浏览器与 CDN 强缓存，后续请求不再回源，服务端收不到埋点，旧目标也被长期记住 | 统一用 302（或需保持方法时 307），把状态码写进接口契约；要改目标时 302 每次回源才生效 |
| 创建短链不做幂等，同一长 URL 生成多个 code，或被刷接口打满发号器 | 没有幂等键与限流，重复请求各插一行、刷接口直接耗尽发号 QPS | 创建接口接受幂等键，命中返回同一 code；入口用令牌桶按 IP 限流，超限返 429 |
| 每次跳转同步 UPDATE clicks，读路径被写放大拖慢 | 高频读请求夹带一次同步写，DB 写锁与连接池成为瓶颈 | 埋点先写本地队列/日志再批量异步入库，clicks 用汇总表；把埋点移出重定向主链路并监控事件丢失 |


## 练习、自测与一页纸速记

<Exercise title='基础：实现 Base62 编解码并验证 7 位容量' task='写 to62(n) 与 from62(s)，验证 to62(3521614606207) 得到 &#39;ZZZZZZZ&#39;，且 from62(to62(n)) == n 对若干 n 成立。' solution='A = &#39;0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ&#39;\ndef to62(n):\n    out = []\n    while n:\n        n, r = divmod(n, 62)\n        out.append(A[r])\n    return &#39;&#39;.join(reversed(out)) or &#39;0&#39;\ndef from62(s):\n    n = 0\n    for ch in s:\n        n = n * 62 + A.index(ch)\n    return n\nprint(to62(3521614606207))\nprint(from62(to62(123456)) == 123456)' explain='编码是反复 divmod 取余、解码按位乘回；62^7-1 对应 7 个 Z，7 位即可容纳约 3.5e12 个 id。' />

<Exercise title='进阶：把 301 换成 302 并加令牌桶限流' task='给 resolve 固定返回 302，写一个 TokenBucket(rate, capacity) 用固定时间戳驱动，验证 capacity 允许突发、rate 决定补充速度、超限返回 429 语义。' solution='class TB:\n    def __init__(s, rate, cap): s.rate,s.cap,s.t,s.last=rate,cap,float(cap),None\n    def allow(s, now):\n        if s.last is None: s.last=now\n        s.t=min(s.cap, s.t+(now-s.last)*s.rate); s.last=now\n        if s.t&gt;=1: s.t-=1; return True\n        return False\nb=TB(2,2); t=100.0\nprint([b.allow(t) for _ in range(3)])\nprint(b.allow(t+0.5), b.allow(t+1.0))' explain='容量 2 允许一次突发两个，随后按每秒 2 个补充；固定时间戳让输出可复现。限流要在发号器前生效，超限映射成 429。' />

<Quiz no='092-1' q='短链重定向为什么通常用 302 而不是 301？' :options='["302 每次回源，埋点准确且允许改目标；301 被强缓存后请求不再到服务端", "302 比 301 更快", "301 已被 HTTP 标准废弃", "302 对 SEO 更友好所以必须用它"]' answer="0" explain='301 会被浏览器与 CDN 强缓存，后续点击不回源导致点击统计缺失、改目标难收回；302 临时重定向每次回源，统计与可控性才有保障。' />

<Quiz no='092-2' q='用数据库自增 id 做短链发号，最主要的代价是？' :options='["ID 可预测、暴露业务量，且单点发号器需要压测与扩容", "无法保证唯一", "编码后长度一定超过 10 位", "不能建唯一索引"]' answer="0" explain='自增 id 靠唯一约束保证不冲突、编码成 Base62 很短，但顺序可猜；要不可猜测需加混淆或换号段/雪花 ID，并对发号器压测定容。' />

<Quiz no='092-3' q='每次短链跳转都同步 UPDATE clicks，最可能的问题是什么？' :options='["高频读夹带同步写造成写放大，DB 写锁与连接池成瓶颈", "302 状态码会失效", "Base62 编码会变慢", "缓存命中率会下降"]' answer="0" explain='读多写少场景应把埋点移出主链路：先写本地队列/日志再批量异步入库，clicks 走汇总表，避免一次跳转一次同步 UPDATE。' />

<Predict no='092-4' q='对 n=3521614606207 做 Base62 编码，最可能得到什么？' :options='["ZZZZZZZ（7 个 Z）", "9999999", "报错，超出 32 位"]' answer='0' output='big id ZZZZZZZ' explain='3521614606207 = 62^7 - 1，恰好是 7 位 Base62 的最大表示，字符集末位都是 Z。这说明 7 位短码可容纳约 3.5 万亿个 id，容量绰绰有余。' />

<FillBlank no='092-5' tpl='___ sqlite3' :answers='["import"]' hint='回想本讲关于 发号与 Base62 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 发号与 Base62：把自增 ID 编成短码 的落点。' />

<KnowledgeCard :points='["自增主键配 Base62：反复 divmod(n, 62) 取余，n=0 单独处理；62^7≈3.5e12，7 位够万亿级", "短码列建 UNIQUE 索引，重复创建用幂等键返回同一 code；自增 ID 可预测，可加 XOR 混淆或号段/雪花 ID", "301 被浏览器与 CDN 强缓存、埋点失真且难收回；短链用 302 每次回源，保证统计准确、允许改目标", "读路径 code→long_url 缓存优先、未命中查库回填，改目标要主动失效缓存；clicks 用异步埋点避免写放大", "入口令牌桶或滑动窗口限流，超限返回 429，防止刷接口打满发号器", "容量靠压测测出 QPS 拐点与 p99，落成数字再决定水平扩容、读写分离与缓存分片"]' :pitfalls='["用 301 做短链重定向，点击统计对不上且改目标不生效", "创建短链不做幂等，同一长 URL 生成多个 code，或被刷接口打满发号器", "每次跳转同步 UPDATE clicks，读路径被写放大拖慢", "把 301 与 302 混用，会让统计口径与 SEO 行为都不受控；不做限流则会被刷接口打满发号器"]' summary='短链是麻雀虽小五脏俱全的服务：读多写少、缓存友好、可压测、可灰度，非常适合验证整套服务端能力' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 自增主键配 Base62：反复 divmod(n, 62) 取余，n=0 单独处理；62^7≈3.5e12，7 位够万亿级 | 建立直觉 |
| 短码列建 UNIQUE 索引，重复创建用幂等键返回同一 code；自增 ID 可预测，可加 XOR 混淆或号段/雪花 ID | 跑通示例 |
| 301 被浏览器与 CDN 强缓存、埋点失真且难收回；短链用 302 每次回源，保证统计准确、允许改目标 | 深入边界 |
| 读路径 code→long_url 缓存优先、未命中查库回填，改目标要主动失效缓存；clicks 用异步埋点避免写放大 | 工程落地 |
| 入口令牌桶或滑动窗口限流，超限返回 429，防止刷接口打满发号器 | 随堂检测 |
| 容量靠压测测出 QPS 拐点与 p99，落成数字再决定水平扩容、读写分离与缓存分片 | 复盘 |

1. 自增主键配 Base62：反复 divmod(n, 62) 取余，n=0 单独处理；62^7≈3.5e12，7 位够万亿级

2. 短码列建 UNIQUE 索引，重复创建用幂等键返回同一 code；自增 ID 可预测，可加 XOR 混淆或号段/雪花 ID

3. 301 被浏览器与 CDN 强缓存、埋点失真且难收回；短链用 302 每次回源，保证统计准确、允许改目标

[下一讲：NumPy 向量化、广播与内存布局](/data-ai/numpy)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/092-capstone.py`

```bash
python3 examples/lessons/092-capstone.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/092-capstone.py) · [全部示例代码索引](/examples/)
