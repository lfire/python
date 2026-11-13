---
title: 第 091 讲 · 文件、对象存储、搜索与 gRPC
description: 补齐服务端的外部依赖版图
---

<StageHeader stage='L8 · 服务端与数据' level='★★★☆☆' time='40 分钟' goal='补齐服务端的外部依赖版图' prereq='第 090 讲 · 认证授权：Session、JWT、OAuth2 与 RBAC' />

# 第 091 讲 · 文件、对象存储、搜索与 gRPC

路由、数据、缓存、身份都齐了，服务还差几块外部依赖：大文件放哪、内容怎么被搜到、内部服务之间怎么说话。这一讲把版图补齐，让服务不再只靠本机磁盘和一条 SQL 撑着。

上传视频先落本地盘，容器一重启还没转存的就丢了，扩到两台后 A 写、B 读便读不到；文章用 `LIKE` 到百万行全表扫描，还匹配不到同义词；内部用 `JSON` 传字段，改了名字线上才炸。我们从上传与断点续传、预签名 URL 讲起，再谈对象存储一致性、倒排索引与 ES，最后落到 gRPC 与 Protobuf 的错误传播。需要 `HTTP`、哈希签名与序列化；学完能为服务选对文件、搜索与通信方案。


## 容器一重启，用户刚上传的文件就读不到了

一个内容平台把用户上传的视频先落到应用服务器的本地磁盘，再由后台任务转存到对象存储。容器一次重启，还没转存的文件全丢了；扩容到两个实例后，上传请求打到 A、下载请求打到 B，B 的磁盘上根本没有这个文件。第二次改造让文件经应用服务器中转，带宽与内存立刻被大文件吃满。

搜索也出问题：用 SQL 的 `LIKE` 配 '%关键词%' 做模糊查询，数据到百万行后全表扫描把库拖慢，还匹配不到同义词。内部服务之间用 `JSON` over `HTTP` 来回传，字段改了没有编译期约束，线上才炸。四类问题分属四个外部依赖：对象存储、上传协议、倒排索引、RPC 序列化。

本讲用标准库实现倒排索引与 `BM25`、预签名签名和 Protobuf varint，把『为什么这样设计』变成可跑的证据。

<Callout type="warn" title='先看一个真实会出错的写法' text='把上传文件先落到应用服务器本地磁盘，容器重启或扩容后文件丢失/读不到：本地磁盘是实例级、非共享且非持久，另一实例没有该文件' />


## 上传、断点续传与预签名直传

大文件不该经过应用服务器：预签名 URL 让服务端只做鉴权与元数据，客户端拿一个带签名的临时 URL 直传对象存储（S3、MinIO、COS），带宽与内存压力转给存储。

签名思路（AWS SigV4）是把 `HTTP` method、资源 path、过期时间、日期等按规范拼成待签串，用 `HMAC-SHA256` 派生出签名放进查询参数（`X-Amz-Algorithm`、`X-Amz-Date`、`X-Amz-Expires`、`X-Amz-Signature`），篡改 path 或过期时间都会让服务端重算的签名不匹配；

签发时还要限定 Content-Type、最大大小与有效期（如 900 秒）。分片上传是 initiate 拿 `uploadId`、逐片 PUT（带 `partNumber`，返回 `ETag`）、complete 合并；

失败只重传某片，断点续传靠客户端记录已传 part 或服务端返回 offset，续传带 Range 或 uploadId。对象存储一致性有个常被写错的结论：S3 自 2020 年 12 月起对 PUT、GET、`DELETE`、`LIST` 提供强一致的 read-after-write，旧教程里『最终一致』的说法已经过时；

但 CDN 缓存与跨区域复制仍有延迟，元数据（原始名、owner、size、hash）要存自己的数据库，不能只信对象存储。

**预签名 URL 与上传要点**

| 环节 | 做法 | 要点 |
| --- | --- | --- |
| 鉴权 | 服务端校验用户与文件元数据 | 只发签名，不经应用服务器传文件 |
| 签名 | HMAC-SHA256 绑定 method/path/过期时间 | 篡改 path 或 expires 即失效 |
| 有效期 | X-Amz-Expires 如 900 秒 | 过期即拒，限制滥用窗口 |
| 分片 | initiate → PUT part(ETag) → complete | 失败只重传某片 |
| 续传 | 记录 uploadId / 已传 part 或 Range | 别整文件重传 |

<Callout type="tip" title='核心心智模型' text='大文件不该经过应用服务器：预签名 URL 让服务端只做鉴权与元数据，客户端拿一个带签名的临时 URL 直传对象存储（S3、MinIO、COS），带宽与内存压力转给存储。签名思路（AWS SigV4）是把 `HTTP` method、资源 path、过期时间、日期等按规范拼成待签串，用 `HMAC-S' />


## 主示例：给路径与有效期签一个不可篡改的名

```python
import math
from collections import defaultdict
DOCS = {
    1: 'short link redis cache',
    2: 'redis cache penetration avalanche',
    3: 'sqlalchemy connection pool',
}
def tokenize(text):
    return [w.lower() for w in text.split()]
postings = defaultdict(list)
for doc_id, text in DOCS.items():
    for term in set(tokenize(text)):
        postings[term].append(doc_id)
N = len(DOCS)
idf = {t: math.log(1 + (N - len(ids) + 0.5) / (len(ids) + 0.5))
       for t, ids in postings.items()}
def search(query, k=3):
    scores = defaultdict(float)
    for term in set(tokenize(query)):
        for doc_id in postings.get(term, []):
            tf = 1
            scores[doc_id] += idf[term] * (tf * 2.2) / (tf + 1.2)
    return [(d, round(s, 3)) for d, s in sorted(scores.items(), key=lambda kv: -kv[1])[:k]]
print('index terms', len(postings))
print('redis df', len(postings['redis']), 'idf', round(idf['redis'], 4))
print('query redis cache', search('redis cache'))
print('query sqlalchemy', search('sqlalchemy'))
```

<OutputBox title='主示例运行结果' output='index terms 9\nredis df 2 idf 0.47\nquery redis cache [(1, 0.94), (2, 0.94)]\nquery sqlalchemy [(3, 0.981)]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import math\nfrom collections import defaultdict\nDOCS = {\n    1: &#39;short link redis cache&#39;,\n    2: &#39;redis cache penetration avalanche&#39;,\n    3: &#39;sqlalchemy connection pool&#39;,\n}\ndef tokenize(text):\n    return [w.lower() for w in text.split()]\npostings = defaultdict(list)\nfor doc_id, text in DOCS.items():\n    for term in set(tokenize(text)):\n        postings[term].append(doc_id)\nN = len(DOCS)\nidf = {t: math.log(1 + (N - len(ids) + 0.5) / (len(ids) + 0.5))\n       for t, ids in postings.items()}\ndef search(query, k=3):\n    scores = defaultdict(float)\n    for term in set(tokenize(query)):\n        for doc_id in postings.get(term, []):\n            tf = 1\n            scores[doc_id] += idf[term] * (tf * 2.2) / (tf + 1.2)\n    return [(d, round(s, 3)) for d, s in sorted(scores.items(), key=lambda kv: -kv[1])[:k]]\nprint(&#39;index terms&#39;, len(postings))\nprint(&#39;redis df&#39;, len(postings[&#39;redis&#39;]), &#39;idf&#39;, round(idf[&#39;redis&#39;], 4))\nprint(&#39;query redis cache&#39;, search(&#39;redis cache&#39;))\nprint(&#39;query sqlalchemy&#39;, search(&#39;sqlalchemy&#39;))' :notes='["导入 math，BM25 的 idf 用自然对数", "导入 defaultdict，posting list 与得分表都用它", "三篇模拟文档，词已按空格分好", "文档 1 讲短链与缓存", "文档 2 讲缓存失效的两种现象", "文档 3 讲 ORM 连接池", "闭合 DOCS 字典，3 篇文档构成后续 N=3 的检索语料库", "定义极简分词：按空格切并转小写", "真实系统还要去停用词、词干化，中文需分词器", "postings 是 term 到 doc_id 列表的倒排表", "遍历每篇文档建索引", "set 去重，同一文档里词频此处简化为 1", "把文档 id 追加到该 term 的 posting list", "N 是文档总数，BM25 的 idf 需要它", "按 df 计算每个 term 的 idf，df 越高分越低", "len(ids) 即文档频率 df", "定义检索函数，k 控制返回条数", "scores 累加每个文档的相关性得分", "对查询去重后的每个 term 处理", "取出该 term 命中的全部文档 id", "简化词频 tf=1（示例每词在文档出现一次）", "套用 BM25 的 tf 饱和项 k1=1.2 的简化形式", "按得分降序取前 k，分数保留三位小数", "打印索引里的 term 总数", "redis 出现在 2 篇文档，打印其 df 与 idf", "查两个词，命中文档 1 与 2 且分数相同", "查稀有词 sqlalchemy，只命中文档 3 且 idf 更高"]' title='第 091 讲 · 文件、对象存储、搜索与 gRPC' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)
for n in (1, 127, 128, 300, 150):
    print(n, '->', list(varint(n)))
```

<OutputBox title='原理验证' output='1 -&gt; [1]\n127 -&gt; [127]\n128 -&gt; [128, 1]\n300 -&gt; [172, 2]\n150 -&gt; [150, 1]' />


## 对照：落本地磁盘与直传对象存储的边界

```python
import hmac, hashlib

def presign(path, expires, now=1700000000):
    sts = 'GET' + chr(10) + path + chr(10) + str(now + expires)
    sig = hmac.new(b'secret', sts.encode(), hashlib.sha256).hexdigest()[:16]
    return '?X-Amz-Date=' + str(now) + '&X-Amz-Expires=' + str(expires) + '&X-Amz-Signature=' + sig

a = presign('/uploads/a.bin', 900)
b = presign('/uploads/b.bin', 900)
c = presign('/uploads/a.bin', 3600)
print('a sig', a.split('Signature=')[1])
print('b sig', b.split('Signature=')[1])
print('c sig', c.split('Signature=')[1])
print('path bound', a.split('Signature=')[1] != b.split('Signature=')[1])
print('expiry bound', a.split('Signature=')[1] != c.split('Signature=')[1])
```

<OutputBox title='对照写法：先自己猜，再点开' output='a sig 2b4695f4ebd92815\nb sig c0ca2afd07f099dd\nc sig ba6f382a5296292a\npath bound True\nexpiry bound True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import math\nfrom collections import defaultdict\nDOCS = {\n    1: &#39;short link redis cache&#39;,\n    2: &#39;redis cache penetration avalanche&#39;,\n    3: &#39;sqlalchemy connection pool&#39;,\n}\ndef tokenize(text):\n    return [w.lower() for w in text.split()]\npostings = defaultdict(list)\nfor doc_id, text in DOCS.items():\n    for term in set(tokenize(text)):\n        postings[term].append(doc_id)\nN = len(DOCS)\nidf = {t: math.log(1 + (N - len(ids) + 0.5) / (len(ids) + 0.5))\n       for t, ids in postings.items()}\ndef search(query, k=3):\n    scores = defaultdict(float)\n    for term in set(tokenize(query)):\n        for doc_id in postings.get(term, []):\n            tf = 1\n            scores[doc_id] += idf[term] * (tf * 2.2) / (tf + 1.2)\n    return [(d, round(s, 3)) for d, s in sorted(scores.items(), key=lambda kv: -kv[1])[:k]]\nprint(&#39;index terms&#39;, len(postings))\nprint(&#39;redis df&#39;, len(postings[&#39;redis&#39;]), &#39;idf&#39;, round(idf[&#39;redis&#39;], 4))\nprint(&#39;query redis cache&#39;, search(&#39;redis cache&#39;))\nprint(&#39;query sqlalchemy&#39;, search(&#39;sqlalchemy&#39;))", "note": "上传、断点续传与预签名直传"}, {"label": "对照 / 进阶", "code": "import hmac, hashlib\n\ndef presign(path, expires, now=1700000000):\n    sts = &#39;GET&#39; + chr(10) + path + chr(10) + str(now + expires)\n    sig = hmac.new(b&#39;secret&#39;, sts.encode(), hashlib.sha256).hexdigest()[:16]\n    return &#39;?X-Amz-Date=&#39; + str(now) + &#39;&amp;X-Amz-Expires=&#39; + str(expires) + &#39;&amp;X-Amz-Signature=&#39; + sig\n\na = presign(&#39;/uploads/a.bin&#39;, 900)\nb = presign(&#39;/uploads/b.bin&#39;, 900)\nc = presign(&#39;/uploads/a.bin&#39;, 3600)\nprint(&#39;a sig&#39;, a.split(&#39;Signature=&#39;)[1])\nprint(&#39;b sig&#39;, b.split(&#39;Signature=&#39;)[1])\nprint(&#39;c sig&#39;, c.split(&#39;Signature=&#39;)[1])\nprint(&#39;path bound&#39;, a.split(&#39;Signature=&#39;)[1] != b.split(&#39;Signature=&#39;)[1])\nprint(&#39;expiry bound&#39;, a.split(&#39;Signature=&#39;)[1] != c.split(&#39;Signature=&#39;)[1])", "note": "倒排索引与搜索打分"}]' title='两种写法切换看' />

<ConceptDiagram type='flow4' title='第 091 讲 · 上传、断点续传与预签名直传' labels='上传、断点续传与预签名直传|倒排索引与搜索打分|gRPC、Protobuf 与跨服务错误传播' caption='补齐服务端的外部依赖版图' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 倒排索引与搜索打分

倒排索引把『文档 → 词』反转成『词 → 文档列表』（posting list）：先分词（英文 lowercase、去停用词、词干化；中文要 jieba 等分词器），为每个 term 记录 (doc_id, tf, positions)。

查询时对多个 term 取 posting list 合并，用 `BM25` 打分：逆文档频率 `idf=ln(1+(N-df+0.5)/(df+0.5))`，df 越高区分度越低；

词频饱和项 `tf*(k1+1)/(tf+k1*(1-b+b*dl/avgdl))`，k1 常取 1.2、b 取 0.75，避免长文档靠堆词占优。

倒排把『包含某词』从全表扫描 `O(N)` 降到直接定位 posting list，是 Lucene 与 Elasticsearch 的核心。ES 之上还有分片与副本、analyzer、mapping、评分与高亮。索引与业务库的一致性靠异步双写（经消息队列解耦）或 CDC 订阅 binlog，做到最终一致；

重建索引用别名切换（reindex 到新索引再原子换 alias）避免停服。

深翻页用 `search_after` 而非 `from+size`，后者受 `max_result_window` 默认 10000 限制且深页数成本高。

选型上，关键词检索、模糊匹配、聚合用 ES，精确主键查询仍走数据库。

**倒排索引 / BM25 与 ES**

| 概念 | 作用 | 典型取值 |
| --- | --- | --- |
| posting list | term 到 doc_id 列表 | 倒排把 O(N) 扫描降为定位 |
| idf | 词区分度 | ln(1+(N-df+0.5)/(df+0.5)) |
| k1 / b | 词频饱和 / 长度归一 | 1.2 / 0.75 |
| max_result_window | from+size 深翻页上限 | 默认 10000，改用 search_after |
| 一致性 | 业务库与索引 | 异步双写或 CDC，别名切换重建 |


## gRPC、Protobuf 与跨服务错误传播

gRPC 基于 `HTTP/2` 多路复用与 Protobuf 二进制编码：在 .proto 里定义 service 与 message，字段用 varint（每字节 7 位有效数据、最高位表示是否还有后续字节）与 zigzag 编码有符号整数，字段号加 wire type 打标签，比 `JSON` 更省带宽且强类型；

代码生成产出客户端 stub 与服务端基类，契约由 .proto 唯一确定。四种流式：unary、server streaming、client streaming、bidirectional。

错误传播用标准 status code，按数值排开是 `OK=0`、`CANCELLED=1`、`INVALID_ARGUMENT=3`、`DEADLINE_EXCEEDED=4`、`NOT_FOUND=5`、`ALREADY_EXISTS=6`、`PERMISSION_DENIED=7`、`RESOURCE_EXHAUSTED=8`、`INTERNAL=13`、`UNAVAILABLE=14`、`UNAUTHENTICATED=16`，别把业务错误塞进 `HTTP` 200 的 body。

跨服务用 metadata 传 `trace_id` 串起链路，设置 deadline 与重试（仅对幂等调用）、对 `UNAVAILABLE` 做退避、对 `RESOURCE_EXHAUSTED` 做限流。

生产还要配负载均衡、健康检查与 TLS/mTLS。选型：内部高频、强契约、多语言用 gRPC；对外、需人类可读与浏览器直连用 `REST/JSON`。

**gRPC status code 与场景**

| 码 | 名称 | 处理 |
| --- | --- | --- |
| 0 | OK | 成功 |
| 3 | INVALID_ARGUMENT | 参数错，不重试 |
| 4 | DEADLINE_EXCEEDED | 设更长 deadline 或降级 |
| 5 / 6 | NOT_FOUND / ALREADY_EXISTS | 业务判定，不重试 |
| 8 / 14 | RESOURCE_EXHAUSTED / UNAVAILABLE | 限流 / 退避重试 |
| 16 | UNAUTHENTICATED | 刷新凭据 |

预签名 URL 把信任从『传输通道』转移到『一次性签名』：服务端用自己的密钥对 method、path、过期时间等做 `HMAC`，客户端凭签名直接对存储发起请求，存储用同一密钥重算比对；因为签名绑定了具体资源与时刻，攻击者改路径或拖到过期之后都会校验失败，服务端也就无需代理文件字节。

倒排索引是空间换时间的典型：建索引时把每篇文档切成 term，写进 term 到 (doc_id, tf, positions) 列表的映射，查询时只需对查询词取对应链表做归并，把全表扫描的 `O(N)` 变成与命中文档数相关；`BM25` 用 idf 压低高频词、用 k1 让词频饱和，避免长文档靠重复词刷分。

Protobuf 的 varint 用最高位作续位标志、每字节存 7 位有效数据，小整数只占 1 字节；zigzag 把 -1、1 这类小负数映射成小正数，配合 varint 省去符号位浪费；字段名不进编码、只传字段号加 wire type，是它比 `JSON` 紧凑的根本原因。

gRPC 借 `HTTP/2` 的多路复用在一条连接上并发多个 stream，状态码把错误语义标准化，避免各服务自定义 body 错误。

<Term word='上传与断点续传' text='大文件不该经过应用服务器：预签名 URL 让服务端只做鉴权与元数据，客户端拿一个带签名的临时 URL 直传对象存储（S3、MinIO、COS），带宽与内存压力转给存储。签名思路（AWS SigV4）是把 `HTTP` method、资源 path、过期时间、日期等按规范拼成待签串，用 `HMAC-SHA256` 派生出' />

<Term word='预签名 URL' text='倒排索引把『文档 → 词』反转成『词 → 文档列表』（posting list）：先分词（英文 lowercase、去停用词、词干化；中文要 jieba 等分词器），为每个 term 记录 (doc_id, tf, positions)。查询时对多个 term 取 posting list 合并，用 `BM25` 打分' />


## 预签名直传加倒排检索的最小服务层

下面把两个外部依赖拼成一个自包含服务层：`presign` 用 `HMAC` 把 method、path、有效期绑进签名，`verify_sig` 在服务端重算比对，模拟客户端拿 URL 直传前的校验；

`InvertedIndex` 建 term 到 doc_id 的倒排表并用简化 `BM25` 打分，`add`/`search` 分别对应写入与检索。重点看两个『边界』：签名把资源与过期时间绑定，改一个字节就失效；索引把查询从扫全表变成查 posting list。

真实项目把 `presign` 换成 SDK 的 `generate_presigned_url`、把内存索引换成 ES、把业务库到索引的同步换成 CDC 或消息队列双写，鉴权、签名绑定、倒排打分这三层结构不变。

```python
import hmac, hashlib, math
from collections import defaultdict

SECRET = b'storage-secret'
def sign(path, expires, now=1700000000):
    sts = 'PUT' + chr(10) + path + chr(10) + str(now + expires)
    return hmac.new(SECRET, sts.encode(), hashlib.sha256).hexdigest()[:16]
def verify_sig(path, expires, sig, now=1700000000):
    return hmac.compare_digest(sign(path, expires, now), sig)

class InvertedIndex:
    def __init__(self):
        self.postings = defaultdict(list)
        self.n = 0
    def add(self, doc_id, text):
        self.n += 1
        for t in set(text.lower().split()):
            self.postings[t].append(doc_id)
    def search(self, q):
        scores = defaultdict(float)
        for t in set(q.lower().split()):
            ids = self.postings.get(t, [])
            idf = math.log(1 + (self.n - len(ids) + 0.5) / (len(ids) + 0.5))
            for d in ids:
                scores[d] += idf * 2.2 / 2.2
        return sorted(scores, key=lambda d: -scores[d])

sig = sign('/uploads/a.bin', 900)
print('sig valid', verify_sig('/uploads/a.bin', 900, sig))
print('path changed', verify_sig('/uploads/b.bin', 900, sig))
print('expired', verify_sig('/uploads/a.bin', 3600, sig))
idx = InvertedIndex()
idx.add(1, 'redis cache penetration')
idx.add(2, 'redis cache avalanche')
idx.add(3, 'sqlalchemy pool')
print('search redis cache', idx.search('redis cache'))
```

<Callout type="idea" title='落地提示' text='对象存储配生命周期与 CDN、搜索用异步双写或 CDC 保持索引最终一致、内部 RPC 用 gRPC 并统一错误码' />

<CheckList id='P091b' title='上线前自检' :items='["能复现并解释「把上传文件先落到应用服务器本地磁盘，容器重启或扩容后文件丢失」", "能复现并解释「用 SQL 的 LIKE &#39;%词%&#39; 做搜索，数据量大后全表」", "能复现并解释「内部服务把业务错误塞进 HTTP 200 的 body，字段」", "能用一条命令验证 上传与断点续传", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE t(k TEXT UNIQUE)'); print('ok')"
```

把输入换成你自己的数据，观察结果是否仍符合 上传与断点续传 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

<FlowTimeline :steps='[{"title": "上传、断点续传与预签名直传", "desc": "大文件不该经过应用服务器：预签名 URL 让服务端只做鉴权与元数据，客户端拿一个带签…", "tone": "blue"}, {"title": "倒排索引与搜索打分", "desc": "倒排索引把『文档 → 词』反转成『词 → 文档列表』（posting list）：先…", "tone": "purple"}, {"title": "gRPC、Protobuf 与跨服务错误传播", "desc": "gRPC 基于 `HTTP/2` 多路复用与 Protobuf 二进制编码：在 .p…", "tone": "orange"}, {"title": "工程落地", "desc": "预签名直传 + 倒排检索的最小服务层", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把上传文件先落到应用服务器本地磁盘，容器重启或扩容后文件丢失/读不到 | 本地磁盘是实例级、非共享且非持久，另一实例没有该文件 | 用预签名 URL 让客户端直传对象存储，服务端只存鉴权与元数据；必须落临时文件时用共享卷并尽快转存 |
| 用 SQL 的 LIKE '%词%' 做搜索，数据量大后全表扫描拖垮库 | 前置通配符无法命中 B 树索引，只能逐行扫描，也没有相关度排序 | 建倒排索引（ES/Lucene），用 BM25 打分；精确主键查询仍走数据库，检索与事务库分开 |
| 内部服务把业务错误塞进 HTTP 200 的 body，字段改了线上才炸 | JSON 无编译期契约，错误码各自定义，调用方无法统一处理 | 用 gRPC + Protobuf 由 .proto 生成强类型 stub，错误走标准 status code，metadata 传 trace_id，并对非幂等调用禁止重试 |

<Callout type="warn" title='本讲最容易踩的坑' text='把上传文件先落到应用服务器本地磁盘，容器重启或扩容后文件丢失/读不到：本地磁盘是实例级、非共享且非持久，另一实例没有该文件' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把上传文件先落到应用服务器本地磁盘，容器重启", "body": "本地磁盘是实例级、非共享且非持久，另一实例没有该文件", "tip": "用预签名 URL 让客户端直传对象存储，服务端只存鉴权与元数据；必须落临时文件时用共享卷并尽快转存"}, {"title": "第 2 步：用 SQL 的 LIKE &#39;%词%&#39; 做搜索", "body": "前置通配符无法命中 B 树索引，只能逐行扫描，也没有相关度排序", "tip": "建倒排索引（ES/Lucene），用 BM25 打分；精确主键查询仍走数据库，检索与事务库分开"}, {"title": "第 3 步：内部服务把业务错误塞进 HTTP 200 的", "body": "JSON 无编译期契约，错误码各自定义，调用方无法统一处理", "tip": "用 gRPC + Protobuf 由 .proto 生成强类型 stub，错误走标准 status code，metadata 传 trace_id，并对非幂等调用禁止重试"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：实现签名绑定 path 与过期时间' task='写 sign(path, expires) 用 HMAC-SHA256 把 method/path/过期时间拼串签名，验证改 path 或改 expires 后重算签名不一致。' solution='import hmac, hashlib\ndef sign(path, expires, now=0):\n    sts = &#39;GET&#39; + chr(10) + path + chr(10) + str(now + expires)\n    return hmac.new(b&#39;k&#39;, sts.encode(), hashlib.sha256).hexdigest()[:16]\na = sign(&#39;/a.bin&#39;, 900)\nb = sign(&#39;/b.bin&#39;, 900)\nc = sign(&#39;/a.bin&#39;, 3600)\nprint(a == b, a == c)' explain='待签串绑定了具体资源与到期时刻，任何一项变化都会得到不同摘要；这就是预签名 URL 能限制滥用范围的原理。' />

<Exercise title='进阶：给倒排索引加 BM25 的 idf 与 tf 饱和' task='在倒排索引基础上，为每个查询 term 计算 idf 并用 tf*(k1+1)/(tf+k1) 打分，验证高频词得分低于稀有词。' solution='import math\nfrom collections import defaultdict\ndocs = {1:&#39;a b&#39;, 2:&#39;a c&#39;, 3:&#39;a d&#39;}\np = defaultdict(list)\nfor d, t in docs.items():\n    for w in set(t.split()): p[w].append(d)\nN = len(docs)\nfor w in (&#39;a&#39;,&#39;b&#39;):\n    df = len(p[w])\n    idf = math.log(1 + (N - df + 0.5)/(df + 0.5))\n    print(w, &#39;df&#39;, df, &#39;idf&#39;, round(idf, 4))' explain='a 出现在全 3 篇、df 高故 idf 低；b 只在 1 篇、idf 高。BM25 借此压低 ubiquitous 词，让稀有词更能区分文档。' />

<Quiz no='091-1' q='预签名 URL 能让客户端直传对象存储、服务端不经手文件，靠的是什么？' :options='["服务端用密钥对 method/path/过期时间做 HMAC 签名，存储端重算比对", "把文件先加密再传", "给客户端一个长期有效的账号密码", "靠 CDN 缓存文件"]' answer="0" explain='签名把信任从通道转到一次性凭证：绑定具体资源与有效期，改 path 或过期即失效，服务端只做鉴权与元数据，不代理字节。' />

<Quiz no='091-2' q='用 LIKE &#39;%关键词%&#39; 做全文检索随数据量变慢，根本原因是？' :options='["前置通配符无法命中 B 树索引，退化为全表扫描且无相关度排序", "SQL 不支持字符串", "数据库不允许建索引", "LIKE 只能查英文"]' answer="0" explain='应改用倒排索引（term → posting list）把 O(N) 扫描降为定位命中文档，再用 BM25 打分；精确主键查询仍走数据库。' />

<Quiz no='091-3' q='关于 Protobuf 的 varint 编码，下面哪项准确？' :options='["每字节存 7 位数据、最高位表示是否有后续字节，小整数只占 1 字节", "每个整数固定 4 字节", "把字段名一起写进编码", "只能编码非负整数"]' answer="0" explain='varint 用续位标志变长存储，1 字节存 0..127；zigzag 让小负数也映射成小正数；字段名不进编码，只传字段号 + wire type，这是比 JSON 紧凑的根本原因。' />

<Predict no='091-4' q='对整数 150 做 Protobuf varint 编码，最可能得到哪组字节？' :options='["[150, 1]", "[150]", "[1, 150]"]' answer='0' output='150 -&gt; [150, 1]' explain='150 = 0x96，低 7 位是 0x16(22)，加续位得 0x96(150)；剩余 1 编成 0x01。这正是 Protobuf 文档里的经典示例，证明小整数用两字节而非固定四字节。' />

<FillBlank no='091-5' tpl='___ math' :answers='["import"]' hint='回想本讲关于 上传与断点续传 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 上传、断点续传与预签名直传 的落点。' />

<KnowledgeCard :points='["大文件不该经过应用服务器：预签名 URL 用 HMAC-SHA256 绑定 method/path/有效期，客户端直传对象存储", "分片上传 initiate→逐片 PUT(partNumber, ETag)→complete；断点续传只重传某片，带 Range 或 uploadId", "S3 自 2020-12 起 PUT/GET/DELETE/LIST 强一致 read-after-write；CDN 与跨区复制仍有延迟", "倒排索引把『文档→词』反转成『词→posting list』；BM25 用 idf 与词频饱和项打分，k1=1.2、b=0.75", "Protobuf varint 每字节 7 位+续位标志、zigzag 压缩小负数，字段号+wire type 打标签，比 JSON 紧凑", "gRPC 用 HTTP/2 多路复用与标准 status code；内部高频强契约用 gRPC，对外可读用 REST/JSON"]' :pitfalls='["把上传文件先落到应用服务器本地磁盘，容器重启或扩容后文件丢失/读不到", "用 SQL 的 LIKE &#39;%词%&#39; 做搜索，数据量大后全表扫描拖垮库", "内部服务把业务错误塞进 HTTP 200 的 body，字段改了线上才炸", "把上传文件直接写本地磁盘，容器重启即丢，扩容后另一实例也读不到"]' summary='大文件不该经过应用服务器：预签名直传把带宽与内存压力交给对象存储，服务端只做鉴权与元数据' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 大文件不该经过应用服务器：预签名 URL 用 HMAC-SHA256 绑定 method/path/有效期，客户端直传对象存储 | 建立直觉 |
| 分片上传 initiate→逐片 PUT(partNumber, ETag)→complete；断点续传只重传某片，带 Range 或 uploadId | 跑通示例 |
| S3 自 2020-12 起 PUT/GET/DELETE/LIST 强一致 read-after-write；CDN 与跨区复制仍有延迟 | 深入边界 |
| 倒排索引把『文档→词』反转成『词→posting list』；BM25 用 idf 与词频饱和项打分，k1=1.2、b=0.75 | 工程落地 |
| Protobuf varint 每字节 7 位+续位标志、zigzag 压缩小负数，字段号+wire type 打标签，比 JSON 紧凑 | 随堂检测 |
| gRPC 用 HTTP/2 多路复用与标准 status code；内部高频强契约用 gRPC，对外可读用 REST/JSON | 复盘 |

1. 大文件不该经过应用服务器：预签名 URL 用 HMAC-SHA256 绑定 method/path/有效期，客户端直传对象存储

2. 分片上传 initiate→逐片 PUT(partNumber, ETag)→complete；断点续传只重传某片，带 Range 或 uploadId

3. S3 自 2020-12 起 PUT/GET/DELETE/LIST 强一致 read-after-write；CDN 与跨区复制仍有延迟

[下一讲：阶段综合：生产级短链服务](/server/capstone)
