---
title: 第 088 讲 · Redis 缓存：穿透、击穿、雪崩与分布式锁
description: 设计正确且可降级的缓存层
---

<StageHeader stage='L8 · 服务端与数据' level='★★★★☆' time='40 分钟' goal='设计正确且可降级的缓存层' prereq='第 087 讲 · SQLAlchemy、连接池、事务与迁移' />

# 第 088 讲 · Redis 缓存：穿透、击穿、雪崩与分布式锁

数据库访问稳了，可再快的查询也架不住回源。给读多写少的接口垫一层 Redis 缓存很自然；但它先要回答失效时谁重建、会不会打穿库、自己挂了服务还能不能活。本讲把这层设计到能降级。

一次大促三种失效挤在一起：批量查不存在的 ID 每次落到库上，热点 key 过期瞬间几千请求同时回源，所有 key 统一设 300 秒又在同秒失效。我们看五种数据结构与选型、缓存模式与失效怎么定，再分别对准穿透、击穿、雪崩给出空值缓存、互斥重建与 TTL 抖动，最后讲清分布式锁的正确删法。需要事务边界与字典、过期时间的概念；学完能设计失效时仍兜得住库的缓存层。


## 批量预热后同一秒集体失效，缓存把 DB 打垮

商品详情页加了 Redis 缓存后 QPS 涨了五倍，一次大促却把数据库打到 CPU 100%。

复盘看到三种失效挤在一起：有人用脚本批量查根本不存在的商品 ID，每次都穿透到 DB；一个热点 key 过期的瞬间，几千个请求同时回源重建；而运维为图省事给所有缓存统一设了 300 秒 TTL，凌晨批量预热的那批 key 在同一秒集体失效。更糟的是缓存进程重启后服务直接 `500`，因为读路径没有降级。

团队最初的补法是给每个 key 都加过期时间，这恰恰解释不了为什么加了 TTL 还是雪崩。三种故障的根因不同：查不存在、并发重建、集中过期，对应的防线分别是空值缓存与布隆过滤、互斥重建、TTL 抖动。本讲用标准库把三者与分布式锁的正确删法跑通。

<Callout type="warn" title='先看一个真实会出错的写法' text='用 SETNX 加锁后再单独 EXPIRE，进程崩在两句之间留下永久锁：两条命令非原子，加锁成功却没设上过期时间，持锁者崩溃后无人能再获取' />


## 五种数据结构与 Cache-Aside 读写流程

Redis 五种基础结构各有明确分工：`String`（`GET` / `SET` / `SETEX` / `INCR`）存单值、计数器与分布式锁；`Hash`（`HGET` / `HSET` / `HGETALL`）存对象的多个字段，可只更新一个字段；`List`（`LPUSH` / `RPUSH` / `LPOP` / `BRPOP`）做消息队列与最新 N 条列表；`Set`（`SADD` / `SISMEMBER` / `SINTER`）做去重、共同关注、抽奖；`ZSet`（`ZADD` / `ZRANGEBYSCORE`）按 `score` 排序，用于排行榜与延迟队列。

`SET key value EX seconds NX` 是一条命令原子完成「设值 + 过期 + 仅当键不存在时设」，是锁与幂等占位的基石：`NX` 保证互斥，`EX` 保证崩溃后能自动释放，`PX` 用毫秒。

Cache-Aside（旁路缓存）读路径：先 `GET`，命中直接返回，未命中读 DB、把结果 `SET` 回缓存并设 TTL；写路径通常是「先更新 DB 再删缓存」（`DEL` 而非 `UPDATE`，避免两个并发写把旧值写回），删除失败要重试或订阅 binlog 补偿。

缓存与 DB 之间是最终一致：存在短暂脏读窗口，强一致需要分布式锁或双删，代价很高，一般业务接受秒级不一致。`key` 要带业务前缀与版本（`product:v2:42`），并把 TTL 设为基础值加随机抖动。

**五种数据结构与典型命令**

| 结构 | 代表命令 | 典型用途 |
| --- | --- | --- |
| String | GET / SET / SETEX / INCR | 单值缓存、计数器、分布式锁 |
| Hash | HGET / HSET / HGETALL | 对象多字段、可部分更新 |
| List | LPUSH / BRPOP | 消息队列、最新列表 |
| Set | SADD / SISMEMBER / SINTER | 去重、共同关注、抽奖 |
| ZSet | ZADD / ZRANGEBYSCORE | 排行榜、延迟队列按 score 取 |

<Callout type="tip" title='核心心智模型' text='Redis 五种基础结构各有明确分工：`String`（`GET` / `SET` / `SETEX` / `INCR`）存单值、计数器与分布式锁；`Hash`（`HGET` / `HSET` / `HGETALL`）存对象的多个字段，可只更新一个字段；`List`（`LPUSH`…' />

<ConceptDiagram type='hub4' title='第 088 讲 · 五种数据结构与 Cache-Aside 读写流程' labels='五种数据结构与 Cache-Aside 读写…|穿透、击穿、雪崩：三种失效各自的防线|分布式锁的正确实现与缓存一致性|缓存一致性' caption='设计正确且可降级的缓存层' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 主示例：一次读穿透到回写的完整路径

```python
import random
random.seed(0)

store, hits, misses = {}, [0], [0]
def cache_get(key):
    v = store.get(key)
    if v is None: misses[0] += 1
    else: hits[0] += 1
    return v

def query(key):
    hit = cache_get(key)
    if hit is not None:
        return hit['v'] if hit['v'] != '__NULL__' else None
    value = {'id': key} if key >= 0 else None
    if value is None:
        store[key] = {'v': '__NULL__', 'ttl': 60}
        return None
    store[key] = {'v': value, 'ttl': 300 + random.randint(0, 60)}
    return value

print(query(1))
print(query(1))
print(query(-1))
print(query(-1))
print('hits', hits[0], 'misses', misses[0])
print('ttl key1', store[1]['ttl'], 'null ttl', store[-1]['ttl'])
```

<OutputBox title='主示例运行结果' output='{&#39;id&#39;: 1}\n{&#39;id&#39;: 1}\nNone\nNone\nhits 2 misses 2\nttl key1 354 null ttl 60' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import random\nrandom.seed(0)\n\nstore, hits, misses = {}, [0], [0]\ndef cache_get(key):\n    v = store.get(key)\n    if v is None: misses[0] += 1\n    else: hits[0] += 1\n    return v\n\ndef query(key):\n    hit = cache_get(key)\n    if hit is not None:\n        return hit[&#39;v&#39;] if hit[&#39;v&#39;] != &#39;__NULL__&#39; else None\n    value = {&#39;id&#39;: key} if key &gt;= 0 else None\n    if value is None:\n        store[key] = {&#39;v&#39;: &#39;__NULL__&#39;, &#39;ttl&#39;: 60}\n        return None\n    store[key] = {&#39;v&#39;: value, &#39;ttl&#39;: 300 + random.randint(0, 60)}\n    return value\n\nprint(query(1))\nprint(query(1))\nprint(query(-1))\nprint(query(-1))\nprint(&#39;hits&#39;, hits[0], &#39;misses&#39;, misses[0])\nprint(&#39;ttl key1&#39;, store[1][&#39;ttl&#39;], &#39;null ttl&#39;, store[-1][&#39;ttl&#39;])' :notes='["导入 random，用于给 TTL 加抖动", "固定随机种子，让示例输出可复现", "空行，只用于分隔逻辑块，不影响执行结果。", "store 模拟 Redis，hits/misses 用单元素列表便于闭包累加", "定义缓存读取函数", "store.get 返回 None 表示未命中（空值缓存用哨兵对象区分）", "未命中累加 misses", "命中累加 hits", "返回缓存对象或 None", "空行，只用于分隔逻辑块，不影响执行结果。", "定义业务查询，串起读缓存、回源、回写", "先读缓存", "命中且不是空值哨兵时直接返回真实值", "命中空值哨兵说明查过不存在，返回 None 不再回源", "模拟 DB：负数 id 表示不存在的记录", "DB 返回空时走防穿透分支", "把空结果用短 TTL（60 秒）缓存，挡住后续穿透请求", "返回 None", "正常值用基础 300 秒 + 0..60 秒抖动，打散过期时刻防雪崩", "返回业务值", "空行，只用于分隔逻辑块，不影响执行结果。", "首次查 key=1，未命中回源", "再次查 key=1，命中缓存", "首次查不存在的 key=-1，回源并写空值", "再次查 key=-1，命中空值缓存，不再回源", "统计：两次命中、两次未命中", "打印抖动后的 TTL（354）与空值 TTL（60），两者策略不同"]' title='第 088 讲 · Redis 缓存：穿透、击穿、雪崩与分布式锁' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import random
random.seed(42)
ttls = [300 + random.randint(0, 60) for _ in range(6)]
print('ttls with jitter', ttls)
print('distinct', len(set(ttls)))
```

<OutputBox title='原理验证' output='ttls with jitter [340, 307, 301, 347, 317, 315]\ndistinct 6' />


### 空值缓存为什么能挡住穿透

```python
import uuid

class Store:
    def __init__(self):
        self.d = {}
    def set_nx(self, key, value, ex):
        if key in self.d:
            return None
        self.d[key] = (value, ex)
        return 'OK'
    def get(self, key):
        v = self.d.get(key)
        return v[0] if v else None
    def delete(self, key):
        self.d.pop(key, None)

store = Store()
token = str(uuid.uuid4())[:8]
print('acquire A', store.set_nx('lock:order', token, ex=5))
print('acquire B', store.set_nx('lock:order', 'other', ex=5))
def safe_release(store, key, token):
    if store.get(key) == token:
        store.delete(key)
        return 'released'
    return 'not-owner, keep'
print('B release wrong', safe_release(store, 'lock:order', 'other'))
print('A release', safe_release(store, 'lock:order', token))
print('final', store.get('lock:order'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='acquire A OK\nacquire B None\nB release wrong not-owner, keep\nA release released\nfinal None' guess="true" />


## 穿透、击穿、雪崩：三种失效各自的防线

穿透是查询一个 DB 与缓存里都不存在的 `key`，由于空结果不缓存，每次请求都落到 DB；攻击者用随机 ID 批量刷就能打满。

防线是把空值也缓存下来（`SET key '__NULL__' EX 60`）与布隆过滤器（bitmap 判「一定不存在」，有误判率但绝不漏判），并在入口做参数合法性校验。

击穿是某个热点 `key` 恰好过期的瞬间，大量并发同时未命中、一起回源重建，DB 被瞬时峰值压垮。防线是互斥重建：用一条带 `NX` 的命令抢一把重建锁，只让一个线程回源写缓存，其它线程等待后重读；或逻辑过期（`value` 里存 `expire_at`，物理键不删，后台异步续期），读请求永不阻塞但可能短暂返回旧值。

雪崩是大批 `key` 在同一时刻集中过期，或 Redis 整体不可用，流量瞬间全压到 DB。

防线是 TTL 加抖动（如 `300 + random(0,60)` 把过期时刻散开）、多级缓存、Redis 高可用（哨兵 / 集群）、以及服务降级与限流——缓存挂了要能直接读 DB 并限流，而不是整站 `500`。

三者根因不同，统一「再加个过期时间」只会让雪崩更整齐。

**穿透 / 击穿 / 雪崩对照**

| 现象 | 根因 | 防线 |
| --- | --- | --- |
| 穿透 | 查不存在的 key，空结果不缓存 | 空值缓存 + 布隆过滤 + 参数校验 |
| 击穿 | 单个热点 key 过期瞬间并发回源 | 互斥重建（SETNX）/ 逻辑过期 + 后台续期 |
| 雪崩 | 大批 key 同时过期或 Redis 整体不可用 | TTL 抖动、多级缓存、高可用、降级限流 |
| 缓存挂掉服务 500 | 读路径无降级 | 直接读 DB + 限流，返回兜底数据 |

<Compare :panels='[{"label": "主示例", "code": "import random\nrandom.seed(0)\n\nstore, hits, misses = {}, [0], [0]\ndef cache_get(key):\n    v = store.get(key)\n    if v is None: misses[0] += 1\n    else: hits[0] += 1\n    return v\n\ndef query(key):\n    hit = cache_get(key)\n    if hit is not None:\n        return hit[&#39;v&#39;] if hit[&#39;v&#39;] != &#39;__NULL__&#39; else None\n    value = {&#39;id&#39;: key} if key &gt;= 0 else None\n    if value is None:\n        store[key] = {&#39;v&#39;: &#39;__NULL__&#39;, &#39;ttl&#39;: 60}\n        return None\n    store[key] = {&#39;v&#39;: value, &#39;ttl&#39;: 300 + random.randint(0, 60)}\n    return value\n\nprint(query(1))\nprint(query(1))\nprint(query(-1))\nprint(query(-1))\nprint(&#39;hits&#39;, hits[0], &#39;misses&#39;, misses[0])\nprint(&#39;ttl key1&#39;, store[1][&#39;ttl&#39;], &#39;null ttl&#39;, store[-1][&#39;ttl&#39;])", "note": "五种数据结构与 Cache-Aside 读写流程"}, {"label": "对照 / 进阶", "code": "import uuid\n\nclass Store:\n    def __init__(self):\n        self.d = {}\n    def set_nx(self, key, value, ex):\n        if key in self.d:\n            return None\n        self.d[key] = (value, ex)\n        return &#39;OK&#39;\n    def get(self, key):\n        v = self.d.get(key)\n        return v[0] if v else None\n    def delete(self, key):\n        self.d.pop(key, None)\n\nstore = Store()\ntoken = str(uuid.uuid4())[:8]\nprint(&#39;acquire A&#39;, store.set_nx(&#39;lock:order&#39;, token, ex=5))\nprint(&#39;acquire B&#39;, store.set_nx(&#39;lock:order&#39;, &#39;other&#39;, ex=5))\ndef safe_release(store, key, token):\n    if store.get(key) == token:\n        store.delete(key)\n        return &#39;released&#39;\n    return &#39;not-owner, keep&#39;\nprint(&#39;B release wrong&#39;, safe_release(store, &#39;lock:order&#39;, &#39;other&#39;))\nprint(&#39;A release&#39;, safe_release(store, &#39;lock:order&#39;, token))\nprint(&#39;final&#39;, store.get(&#39;lock:order&#39;))", "note": "穿透、击穿、雪崩：三种失效各自的防线"}]' title='两种写法对照' note='差异集中在 五种数据结构与选型；先看输出，再找背后的规则。' />


## 分布式锁：原子加锁、随机值与比对删除

一把正确的锁要满足互斥、不死锁、不误删。

加锁用 `SET key uuid NX PX 30000`，随机值用 `uuid` 生成，`NX` 保证只有一个客户端拿到，`PX` 毫秒级 TTL 保证持锁者崩溃后能自动释放。

释放的坑最深：必须先 `GET` 锁的 `value`、确认等于自己的随机值再 `DEL`，否则 A 的锁超时后 B 已加锁，A 一个 `DEL` 会删掉 B 的锁。而「比对 + 删除」两步必须用 Lua 脚本在 Redis 内原子执行，因为比对通过后、删除前锁可能刚好过期并被别人抢走。

Redlock 是对多个独立实例取多数派的方案，但依赖时钟假设、对 GC 停顿敏感，工程上优先用成熟库或数据库 / etcd 的租约。缓存一致性方面：写 DB 后删缓存，删失败进消息队列异步重试；更可靠的是订阅 MySQL binlog（`Canal` / `Debezium`）做失效，避免业务代码漏删。

读到脏数据的时间窗靠短 TTL 与监控兜底，并提供手动失效接口。

**分布式锁命令与删法**

| 步骤 | 正确写法 | 错误后果 |
| --- | --- | --- |
| 加锁 | SET key uuid NX PX 30000 | 用两条命令 SETNX + EXPIRE 非原子，崩溃即死锁 |
| 持锁标识 | value 用 uuid 随机值 | 用固定值无法区分锁的持有者 |
| 释放 | Lua 里比对 value 再 DEL | 先 GET 后 DEL 非原子，会误删别人的锁 |
| 过期 | PX 毫秒 TTL | 不设 TTL 时持锁者崩溃永久占锁 |

`SET key value NX EX` 的原子性来自 Redis 单线程执行命令：整个「检查键是否存在 + 写入 + 设过期」在一个事件循环步骤里完成，多个客户端并发时只有一个能拿到 `OK`，这正是互斥锁与幂等占位的基础；把 `SETNX` 与 `EXPIRE` 拆成两条命令就会在中间崩溃留下永不过期的锁。

过期删除靠 Redis 的惰性删除（访问时发现过期才删）加定期抽样主动清理，因此大批同 TTL 的键会在相近时刻集中失效，流量像雪崩一样压向 DB——给 TTL 加抖动就是把这个尖峰摊平。

互斥重建用同一把锁把并发回源收敛成一个，其余请求等待或读旧值；逻辑过期则把过期时间放进 `value`、物理键不删，用后台线程异步续，读路径永不阻塞。空值缓存针对的是「不存在」这个查询结果本身也要有表示：用一个哨兵值与短 TTL 占住 `key`，让重复查询不再回源。

布隆过滤器用一个位数组加多个哈希函数判「一定不存在」，以可控误判率换内存效率。释放锁的 compare-and-delete 必须用 Lua，是因为 Redis 执行 Lua 脚本期间不会被其它命令插入，从而保证比对与删除之间锁不被换主。

<Term word='五种数据结构与选型' text='Redis 五种基础结构各有明确分工：`String`（`GET` / `SET` / `SETEX` / `INCR`）存单值、计数器与分布式锁；`Hash`（`HGET` / `HSET` / `HGETALL`）存对象的多个字段，可只更新一个字段；`List`（`LPUSH` / `RPUSH` / `LPOP`…' />

<Term word='缓存模式与失效' text='穿透是查询一个 DB 与缓存里都不存在的 `key`，由于空结果不缓存，每次请求都落到 DB；攻击者用随机 ID 批量刷就能打满。防线是把空值也缓存下来（`SET key &#39;__NULL__&#39; EX 60`）与布隆过滤器（bitmap 判「一定不存在」，有误判率但绝不漏判），并在入口做参数合法性校验。击穿是某个热点…' />


### 为什么 SETNX 与 EXPIRE 必须合成一条命令

<Callout type="warn" title='本讲最容易踩的坑' text='用 SETNX 加锁后再单独 EXPIRE，进程崩在两句之间留下永久锁：两条命令非原子，加锁成功却没设上过期时间，持锁者崩溃后无人能再获取' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 SETNX 加锁后再单独 EXPIRE…", "body": "两条命令非原子，加锁成功却没设上过期时间，持锁者崩溃后无人能再获取", "tip": "用单条 SET key uuid NX PX 30000 原子完成加锁与过期；确需分两步时用 Lua 脚本包起来"}, {"title": "第 2 步：释放锁时直接 DEL，偶尔把别的请求的锁删掉", "body": "A 的锁超时后 B 已重新加锁，A 不比对 value 就 DEL 会删掉 B 的锁", "tip": "value 存 uuid，释放前先比对，且把『比对 + 删除』放进 Lua 脚本原子执行：if redis.call(&#39;get&#39;,KEYS[1])==ARGV[1] then return redis.call(&#39;del&#39;,KEYS[1]) end"}, {"title": "第 3 步：给所有缓存统一设 300 秒 TTL，批量预…", "body": "集中过期造成雪崩，且读路径没有降级，Redis 一抖服务就 500", "tip": "TTL 用 300 + random(0,60) 抖动；加多级缓存与 Redis 高可用；读路径在缓存不可用时降级直读 DB 并限流"}]' />


## 带互斥重建、空值缓存与降级的多级缓存层

下面把缓存层写成一个可运行的骨架，覆盖三道防线与一条降级路径：`query` 先读缓存，命中空值哨兵直接返回（防穿透）；未命中时用一条带 `NX` 的命令抢重建锁，抢到的线程回源写缓存并加 TTL 抖动，没抢到的短暂等待后重读（防击穿）；空结果写短 TTL 空值；`load_from_db` 抛异常时降级读一个本地兜底字典并返回 `degraded` 标记，保证缓存 / DB 抖动时服务不 `500`。

真实项目把 `store` 换成 `redis` 客户端（读路径就是 `redis.get(key)`）、把 `sleep` 换成订阅通知、把兜底换成限流后的静态页，但「空值、互斥、抖动、降级」四件事的结构不变。

```python
import random
import uuid
random.seed(1)
store = {}
FALLBACK = {1: {'id': 1, 'name': 'cached-copy'}}

def set_nx(key, value, ex):
    if key in store:
        return None
    store[key] = {'v': value, 'ex': ex}
    return 'OK'

def rebuild(key):
    token = str(uuid.uuid4())[:8]
    if set_nx('lock:' + str(key), token, ex=5) == 'OK':
        value = {'id': key, 'name': 'item'} if key > 0 else None
        if value is None:
            store[key] = {'v': '__NULL__', 'ex': 60}
        else:
            store[key] = {'v': value, 'ex': 300 + random.randint(0, 60)}
        store.pop('lock:' + str(key), None)

def query(key):
    hit = store.get(key)
    if hit is not None:
        return (None if hit['v'] == '__NULL__' else hit['v'], False)
    try:
        rebuild(key)
    except Exception:
        return (FALLBACK.get(key), True)
    h = store.get(key)
    return (None if h and h['v'] == '__NULL__' else (h['v'] if h else None), False)

print(query(1))
print(query(1))
print(query(-1))
print(query(-1))
print('keys', sorted(store))
```

<Callout type="idea" title='落地提示' text='空值缓存与布隆过滤防穿透、互斥重建防击穿、TTL 加抖动防雪崩；锁用 Redlock 或成熟库' />

<CheckList id='P088a' title='上线前自检' :items='["能复现并解释「用 SETNX 加锁后再单独 EXPIRE，进程崩在两句之间…」", "能复现并解释「释放锁时直接 DEL，偶尔把别的请求的锁删掉」", "能复现并解释「给所有缓存统一设 300 秒 TTL，批量预热后同一秒集体失…」", "能用一条命令验证 五种数据结构与选型", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE t(k TEXT UNIQUE)'); print('ok')"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 五种数据结构与选型 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

<FlowTimeline :steps='[{"title": "五种数据结构与 Cache-Aside 读写流程", "desc": "Redis 五种基础结构各有明确分工：`String`（`GET` / `SET`…", "tone": "blue"}, {"title": "穿透、击穿、雪崩：三种失效各自的防线", "desc": "穿透是查询一个 DB 与缓存里都不存在的 `key`，由于空结果不缓存，每次请求都落…", "tone": "purple"}, {"title": "分布式锁的正确实现与缓存一致性", "desc": "一把正确的锁要满足互斥、不死锁、不误删。加锁用…", "tone": "orange"}, {"title": "工程落地", "desc": "带互斥重建、空值缓存与降级的多级缓存层", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 SETNX 加锁后再单独 EXPIRE，进程崩在两句之间留下永久锁 | 两条命令非原子，加锁成功却没设上过期时间，持锁者崩溃后无人能再获取 | 用单条 SET key uuid NX PX 30000 原子完成加锁与过期；确需分两步时用 Lua 脚本包起来 |
| 释放锁时直接 DEL，偶尔把别的请求的锁删掉 | A 的锁超时后 B 已重新加锁，A 不比对 value 就 DEL 会删掉 B 的锁 | value 存 uuid，释放前先比对，且把『比对 + 删除』放进 Lua 脚本原子执行：if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) end |
| 给所有缓存统一设 300 秒 TTL，批量预热后同一秒集体失效打垮 DB | 集中过期造成雪崩，且读路径没有降级，Redis 一抖服务就 500 | TTL 用 300 + random(0,60) 抖动；加多级缓存与 Redis 高可用；读路径在缓存不可用时降级直读 DB 并限流 |


## expires 字典与定期删除抽样的收敛条件

Redis 每个 db 有两张字典：dict 存键值，expires 存 key 到 long long 毫秒过期时间。过期时间不挂在 value 里而是独立字典，这是 lookupKeyRead 里 `O(1)` 判过期的基础。

删除分两段：expireIfNeeded（`src/db.c`）在访问键时惰性触发，读 expires、比对 `mstime()`，过期则同时删 dict 与 expires 并传播 DEL 事件；activeExpireCycle（`src/expire.c`）由 serverCron 定期驱动，分 `SLOW`（按 `server.hz` 默认 10 次每秒，时间预算约 25 毫秒每次）与 beforeSleep 里的 `FAST`（预算约 1 毫秒）。

每轮从 expires 随机抽 `ACTIVE_EXPIRE_CYCLE_LOOKUPS_PER_LOOP` 个键，删掉已过期的，若过期数除以抽样数大于 25% 就再抽一轮，直到低于阈值或时间预算耗尽。

```python
ACTIVE_EXPIRE_CYCLE_LOOKUPS_PER_LOOP = 20
```

数学上设真实过期比例为 q，一轮里过期数 X 服从二项分布 `Binomial(20, q)`，续轮条件是 X 大于 5；q 小时 P(X 大于 5) 极小，几乎一轮就停，所以主动删除每轮只清理一小撮，大批同 TTL 的键仍靠惰性删除在访问瞬间集中爆发，这正是正文「集中过期」的源码根据，TTL 抖动是把 q 的时间分布摊平而不是改变删除算法。

还有一处易忽略：主从复制下从库不主动删过期键、等主库同步 DEL，因此读写分离可能短暂读到已过期数据，Redis 3.2 起读从库才额外做一次 expireIfNeeded 判断返回空值，这是「从库读到脏值」的故障来源。

```python
import random

random.seed(7)

def expire_pressure(ttls, now, sample=20):
    alive = dict(ttls)
    rounds = 0
    removed = 0
    while rounds < 200:
        rounds += 1
        pick = random.sample(list(alive), min(sample, len(alive)))
        dead = [k for k in pick if alive[k] <= now]
        for k in dead:
            del alive[k]
        removed += len(dead)
        if len(dead) * 4 <= len(pick):
            break
    return removed, rounds, len(alive)

flat = {'k' + str(i): 300 for i in range(600)}
jit = {'k' + str(i): 300 + random.randint(0, 60) for i in range(600)}
print('flat', expire_pressure(flat, 300))
print('jitter', expire_pressure(jit, 300))

```

<OutputBox title='扩展示例运行结果' output='flat (600, 31, 0)\njitter (1, 1, 599)' />

<LineByLine code='import random\n\nrandom.seed(7)\n\ndef expire_pressure(ttls, now, sample=20):\n    alive = dict(ttls)\n    rounds = 0\n    removed = 0\n    while rounds &lt; 200:\n        rounds += 1\n        pick = random.sample(list(alive), min(sample, len(alive)))\n        dead = [k for k in pick if alive[k] &lt;= now]\n        for k in dead:\n            del alive[k]\n        removed += len(dead)\n        if len(dead) * 4 &lt;= len(pick):\n            break\n    return removed, rounds, len(alive)\n\nflat = {&#39;k&#39; + str(i): 300 for i in range(600)}\njit = {&#39;k&#39; + str(i): 300 + random.randint(0, 60) for i in range(600)}\nprint(&#39;flat&#39;, expire_pressure(flat, 300))\nprint(&#39;jitter&#39;, expire_pressure(jit, 300))\n' :notes='["导入 random，用可复现的随机抽样模拟过期键抽查", "空行，只用于分隔逻辑块，不影响执行结果。", "固定随机种子 7，让两组对照实验的抽样序列一致", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 expire_pressure，复刻 activeExpireCycle 的抽样循环", "alive 复制出一份 expires 字典，充当尚未删除的键", "rounds 记录已经跑过的抽样轮数", "removed 累计被删掉的过期键数", "最多跑 200 轮，给不收敛的情况兜底", "每进入一轮，轮数加一", "从存活键里随机抽 sample 个，对应每轮 LOOKUPS_PER_LOOP", "dead 是本轮抽中且已到期的键", "逐个处理本轮到期键", "从 alive 删掉到期键，模拟惰性删除落地", "把本轮删除数累加进 removed", "过期比例不超过 25% 就停，等价于 len(dead)*4 不大于抽样数", "满足条件即跳出循环，停止续轮", "返回 (删除数, 轮数, 剩余键数) 三个可核对的量", "空行，只用于分隔逻辑块，不影响执行结果。", "flat 模拟 600 个键统一 300 秒 TTL", "jit 模拟 300 加 0 到 60 秒抖动的 TTL", "统一 TTL 时每轮全命中，跑 31 轮把 600 个键清空", "抖动后单轮只抽到 1 个到期键就收敛，剩 599 个待后续惰性删除", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />


## SDS、渐进式 rehash 与 lazyfree 的内存路径

Redis 的字符串不是 C 的 char 指针而是 sds（`src/sds.h`）：sdshdr8 里有 len、alloc、flags、`buf[]`，取长度 `O(1)`、二进制安全、`APPEND` 时按翻倍预分配但不超过 1MB，这解释了 `INCR` 与 `APPEND` 的代价模型。

dict（`src/dict.h`）挂两张 dictht 哈希表 `ht[0]` 与 `ht[1]` 以及 rehashidx：扩容时把 `ht[1]` 设为两倍、rehashidx 置 0，之后每次增删改查顺带把 `ht[0]` 的一个 bucket 迁到 `ht[1]`，查询同时查两张表，避免一次性 `O(n)` 停顿，这也是「大字典扩容期间延迟抖动」的来源。

底层编码按元素个数与大小切换：小 Hash 与小 List 用 listpack（ziplist 的后继，一块连续内存省指针开销），大对象转 hashtable 或 quicklist；ZSet 小集合用 listpack，大集合用 skiplist 加 dict 双索引，dict 保证 `ZSCORE` 是 `O(1)`、skiplist 保证 `ZRANGE` 是 `O(log n)`。

删除大 key 的架构权衡最尖锐：DEL 同步释放整块内存，百万字段的 Hash 会让单线程卡几十毫秒；4.0 起 `UNLINK` 把 value 从 dict 摘下（`O(1)`）后丢给 bio 后台线程 lazyfree（`src/bio.c`），`FLUSHALL` `ASYNC` 与 lazyfree-lazy-eviction、lazyfree-lazy-expire、lazyfree-lazy-server-del 三个配置项控制哪些路径走异步。

故障复盘：高峰期 DEL 一个 200 万字段的 Hash，主线程阻塞约 80 毫秒，期间所有请求 RT 尖刺，看起来像「Redis 挂了」，实际是同步内存回收。

**Redis 过期与内存管理的源码组件**

| 源码文件 | 数据结构 / 常量 | 触发时机 |
| --- | --- | --- |
| src/db.c expireIfNeeded | db->expires 字典，key 到毫秒时间戳 | lookupKeyRead 访问键时惰性删除 |
| src/expire.c activeExpireCycle | 每轮抽样 20 键，过期比超 25% 续轮 | serverCron 的 SLOW 周期与 beforeSleep 的 FAST 周期 |
| src/sds.h sdshdr8 | len / alloc / flags / buf[] | APPEND 与 INCR 的字符串表示 |
| src/dict.h dictht ht[2] | 两张哈希表加 rehashidx | 扩容期间每次 CRUD 迁移一个 bucket |
| src/bio.c lazyfree | 后台线程任务队列 | UNLINK、FLUSHALL ASYNC 与淘汰过期删除 |

大促前半小时商品详情接口 RT 突然从 2 毫秒尖刺到 90 毫秒，Redis CPU 没满、网络也正常。

最后定位到运营脚本同步 DEL 了一个 200 万字段的 Hash：DEL 从 dict 摘键是 `O(1)`，但主线程要逐个释放 200 万个 redisObject 与 SDS，几十毫秒内无法处理任何命令，所有客户端一起排队。

Redis 4.0 之后的 `UNLINK` 把 value 从 dict 摘下就返回，把整块释放丢给 bio 后台线程 lazyfree，`FLUSHALL` `ASYNC` 同理；三个配置项分别控制淘汰、过期与隐式删除是否走异步。

下面用纯 Python 模拟这条分界：unlink 只做字典 pop 并把引用挂到待释放队列，真正的字段清点在 drain 里发生，主线程路径不与元素个数成正比。

```python
class LazyFree:
    def __init__(self):
        self.dict = {}
        self.pending = []
    def set(self, k, v):
        self.dict[k] = v
    def unlink(self, k):
        v = self.dict.pop(k, None)
        if v is not None:
            self.pending.append(v)
        return len(v) if v is not None else 0
    def drain(self):
        n = sum(len(v) for v in self.pending)
        self.pending.clear()
        return n

cache = LazyFree()
cache.set('product:42', {'f' + str(i): i for i in range(1000)})
print('unlink returns O(1) size', cache.unlink('product:42'))
print('key still in dict?', 'product:42' in cache.dict)
print('background drained fields', cache.drain())

```

<Quiz no='088-1' q='关于 Redis 的过期删除与主动抽样，下面哪项准确？' :options='["过期时间存在独立的 db-&gt;expires 字典；activeExpireCycle 每轮随机抽 20 个键，过期比例超过 25% 才继续下一轮", "过期时间写在 value 头部，访问时解析 value 才能判断是否过期", "serverCron 每轮扫描全库所有键并删除全部过期键", "从库会主动删除过期键，因此读写分离绝不会读到已过期数据"]' answer="0" explain='expires 是独立字典使判过期 O(1)。惰性删除由 expireIfNeeded 在访问时触发，主动删除的 SLOW 周期有约 25 毫秒时间预算、按抽样命中率决定是否续轮，不做全库扫描；从库不主动删过期键、靠主库同步 DEL，3.2 起读从库才额外做 expireIfNeeded 判断返回空值。统一 TTL 让惰性删除在同一秒集中爆发，抖动是把尖峰摊平而非改变算法本身。' />

<Term word='渐进式 rehash' text='dict 扩容时不一次性搬完 ht[0]，而是置 rehashidx 为 0 后，在每次增删改查顺带把一个 bucket 从 ht[0] 迁到 ht[1]，查询同时查两张表，直到 rehashidx 走完再把 ht[1] 换回 ht[0]。它把 O(n) 的停顿摊成每次操作 O(1) 的开销，代价是扩容窗口内每次查询多一次哈希查找，这也是大字典扩容期延迟抖动的来源。' />


## 练习、自测与一页纸速记

<Exercise title='基础：给 Cache-Aside 加空值缓存与 TTL 抖动' task='实现 query(key)，未命中时若 DB 返回 None 则缓存一个短 TTL 空值哨兵，否则缓存真实值并用 300 + random(0,60) 设 TTL；验证重复查不存在的 key 不再回源。' solution='import random\nrandom.seed(0)\nstore = {}\ndef db(k):\n    return {&#39;id&#39;: k} if k &gt; 0 else None\ndef query(k):\n    h = store.get(k)\n    if h is not None:\n        return None if h[&#39;v&#39;] == &#39;__NULL__&#39; else h[&#39;v&#39;]\n    v = db(k)\n    store[k] = {&#39;v&#39;: &#39;__NULL__&#39;, &#39;ex&#39;: 60} if v is None else {&#39;v&#39;: v, &#39;ex&#39;: 300 + random.randint(0, 60)}\n    return v\nprint(query(1), query(1))\nprint(query(-1), query(-1))\nprint(store[-1][&#39;ex&#39;], store[1][&#39;ex&#39;])' explain='空值用短 TTL 哨兵占住 key 防穿透，真实值用带抖动的 TTL 防雪崩；两次查询不存在的 key 只回源一次。' />

<Exercise title='进阶：实现 compare-and-delete 的安全解锁' task='写一个 release(store, key, token)，仅当 store.get(key) 等于 token 时才删除，构造『B 持锁时 A 用旧 token 释放』的场景验证不会误删。' solution='store = {&#39;lock:order&#39;: &#39;B-token&#39;}\ndef release(store, key, token):\n    if store.get(key) == token:\n        del store[key]\n        return &#39;released&#39;\n    return &#39;not-owner, keep&#39;\nprint(release(store, &#39;lock:order&#39;, &#39;A-token&#39;))\nprint(store)\nprint(release(store, &#39;lock:order&#39;, &#39;B-token&#39;))\nprint(store)' explain='比对 value 是防误删的关键；真实 Redis 里还要把比对与删除放进 Lua 保证原子，避免比对后锁过期被别人抢走再被删。' />

<Quiz no='088-2' q='大量请求查一个 DB 里根本不存在的 ID，每次都打到数据库，这是哪种失效及对策？' :options='["缓存穿透，用空值缓存与布隆过滤器挡住", "缓存击穿，用互斥重建", "缓存雪崩，用 TTL 抖动", "缓存一致性问题，用双删"]' answer="0" explain='查不存在的 key 且空结果不缓存即穿透；把空值用短 TTL 缓存下来，再用布隆过滤器判『一定不存在』，让请求不再回源。' />

<Quiz no='088-3' q='释放 Redis 分布式锁最稳妥的做法是？' :options='["用 Lua 脚本比对 value 等于自己的随机值后再 DEL", "直接 DEL 键即可", "用 EXPIRE 把键设为 0", "只比对 value 不删除，等它自动过期"]' answer="0" explain='value 存 uuid 区分持有者；比对 + 删除必须原子（Lua 脚本），否则 A 的锁超时后 B 已加锁，A 的 DEL 会误删 B 的锁。' />

<Quiz no='088-4' q='关于加分布式锁的加锁命令，下面哪项准确？' :options='["SET key uuid NX PX 30000 一条命令原子完成互斥与过期", "SETNX 加 EXPIRE 两条命令即可", "只用 SET key value 不加过期", "用 GET 判断为空再 SET"]' answer="0" explain='NX 保证互斥、PX 毫秒 TTL 保证崩溃后自动释放，单条命令原子；拆成 SETNX + EXPIRE 会在中间崩溃留下永不过期的锁。' />

<Predict no='088-5' q='对 seed(42) 下 300 + random.randint(0,60) 生成 6 个 TTL，这 6 个值最可能呈现什么？' :options='["6 个各不相同的分散值", "全部等于 300", "全部等于 360"]' answer='0' output='ttls with jitter [340, 307, 301, 347, 317, 315]，distinct 6' explain='抖动把过期时刻从同一秒摊到 0..60 秒区间内，避免批量预热后同一秒集体失效造成雪崩；统一 TTL 反而会让失效更整齐。' />

<FillBlank no='088-6' tpl='___ random' :answers='["import"]' hint='回想本讲关于 五种数据结构与选型 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 五种数据结构与 Cache-Aside 读写流程 的落点。' />

<KnowledgeCard :points='["五种结构：String 单值/锁、Hash 对象、List 队列、Set 去重、ZSet 排行榜", "SET key value EX seconds NX 单命令原子完成设值+过期+仅不存在时设；PX 用毫秒", "穿透→空值缓存+布隆过滤；击穿→互斥重建/逻辑过期；雪崩→TTL 抖动+高可用+降级", "Cache-Aside 写路径是先更新 DB 再删缓存，删失败靠重试或订阅 binlog 补偿", "锁 value 用 uuid，释放必须 Lua 里『比对再删』原子执行，防止误删他人锁", "缓存挂了要能降级直读 DB 并限流；key 带业务前缀与版本，TTL 基础值加抖动"]' :pitfalls='["用 SETNX 加锁后再单独 EXPIRE，进程崩在两句之间留下永久锁", "释放锁时直接 DEL，偶尔把别的请求的锁删掉", "给所有缓存统一设 300 秒 TTL，批量预热后同一秒集体失效打垮 DB", "用 SETNX 加过期时间做锁却不在 finally 里比对随机值再删，可能误删别人的锁"]' summary='缓存不是加一层就变快，而是要回答「失效时谁负责重建」「并发重建会不会打穿 DB」「缓存挂了服务是否还能活」' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 五种结构：String 单值/锁、Hash 对象、List 队列、Set 去重、ZSet 排行榜 | 建立直觉 |
| SET key value EX seconds NX 单命令原子完成设值+过期+仅不存在时设；PX 用毫秒 | 跑通示例 |
| 穿透→空值缓存+布隆过滤；击穿→互斥重建/逻辑过期；雪崩→TTL 抖动+高可用+降级 | 深入边界 |
| Cache-Aside 写路径是先更新 DB 再删缓存，删失败靠重试或订阅 binlog 补偿 | 工程落地 |
| 锁 value 用 uuid，释放必须 Lua 里『比对再删』原子执行，防止误删他人锁 | 随堂检测 |
| 缓存挂了要能降级直读 DB 并限流；key 带业务前缀与版本，TTL 基础值加抖动 | 复盘 |

1. 五种结构：String 单值/锁、Hash 对象、List 队列、Set 去重、ZSet 排行榜

2. SET key value EX seconds NX 单命令原子完成设值+过期+仅不存在时设；PX 用毫秒

3. 穿透→空值缓存+布隆过滤；击穿→互斥重建/逻辑过期；雪崩→TTL 抖动+高可用+降级

[下一讲：消息队列：Celery / RabbitMQ / Kafka](/server/mq)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/088-redis.py`

```bash
python3 examples/lessons/088-redis.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/088-redis.py) · [全部示例代码索引](/examples/)
