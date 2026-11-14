---
title: 第 086 讲 · WebSocket / SSE / 长轮询与实时推送
description: 为实时场景选对通道并管理连接状态
---

<StageHeader stage='L8 · 服务端与数据' level='★★★★☆' time='35 分钟' goal='为实时场景选对通道并管理连接状态' prereq='第 085 讲 · REST API 设计、OpenAPI 与幂等' />

# 第 086 讲 · WebSocket / SSE / 长轮询与实时推送

到上一讲，接口都是一来一回：请求到了、答完就断开。可有些场景要服务端主动把新消息送出去，页面上的看板、提醒都等不起反复刷新。这一讲就为实时需求挑通道，并把连接当成要长期照看的状态。

单机时推送很顺，连接存在内存里、广播就是遍历；扩到三台实例后，用户刷新被分到另一台，刚到的未读消息就没了，半开的长连接还会占满描述符。我们把 WebSocket、SSE 与长轮询三种通道摆在一起，看清握手与帧、重连的差别，再谈连接管理与广播、心跳与背压，最后落到跨实例广播。需要 `HTTP` 请求响应、`ASGI` 双工与并发印象；读完能选对通道，也说得出断线重连谁负责。


## 扩容到第二台实例后，用户收不到别人发的消息

一个在线协作看板上线时，第一条消息推送得很顺：单机内存里存着所有 WebSocket 连接，广播就是遍历一遍 `send`。扩容到三台实例后，用户刷新被负载均衡分到另一台，刚刚的未读消息全没了；更隐蔽的是某台实例上的长连接因网络半开一直没断，连接表越积越大，最终把文件描述符耗尽。

有人给每条消息都加一次数据库轮询想补状态，QPS 直接翻倍。这些故障都指向同一个误判：把实时推送当成「发第一条消息」，而真正的工程难点在断线重连、消息补发与跨实例广播。WebSocket、SSE、长轮询是三种不同的通道契约，握手、帧、重连语义与背压处理各不相同。

本讲先用标准库复现 RFC 6455 的握手计算与帧头编码，再把连接状态管理讲清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='把 WebSocket 连接对象只存在单机内存，扩容后用户收不到别人发的消息：负载均衡把连接分散到不同实例，本机广播到不了其它实例持有的连接' />


## 三种实时通道：握手、帧与单向流

WebSocket（RFC 6455）从一次 `HTTP` Upgrade 开始：客户端发 `Upgrade: websocket`、`Connection: Upgrade`、`Sec-WebSocket-Key`（16 字节随机值的 base64）与 `Sec-WebSocket-Version: 13`；

服务端把该 key 与固定 `GUID` `258EAFA5-E914-47DA-95CA-C5AB0DC85B11` 拼接，取 SHA-1 再做 base64，作为 `Sec-WebSocket-Accept` 返回，状态码 `101 Switching Protocols`。

握手后连接换成帧协议：第一个字节高位是 `FIN`、低 4 位是 `opcode`（`0x1` 文本、`0x2` 二进制、`0x8` close、`0x9` ping、`0xA` pong），后续是掩码位与变长 `payload length`（`<126` 用 1 字节、`126` 用后接 2 字节、`127` 用后接 8 字节），小文本帧头仅 2 字节，远省于 `HTTP`。

SSE 则是普通 `HTTP` 响应，`Content-Type` 设为 `text/event-stream`，体由 `data:`、`event:`、`id:`、`retry:` 行加空行分隔，浏览器 `EventSource` 自动重连并在 `Last-Event-ID` 头带回上次 id；

它只有服务端到客户端单向、且基于 `HTTP`/1.1 长连，天然穿透代理。长轮询是客户端反复发普通请求、服务端挂住直到有数据或超时，实现最兼容但每次都要重建请求头。全双工互动（聊天、协同）选 WebSocket，单向通知（行情、进度、日志流）选 SSE，兼容性兜底才用长轮询。

**三种实时通道对照**

| 维度 | WebSocket | SSE | 长轮询 |
| --- | --- | --- | --- |
| 方向 | 全双工 | 服务端到客户端单向 | 半双工，靠反复请求 |
| 协议 | HTTP Upgrade 后走帧，101 | 普通 HTTP，text/event-stream | 普通 HTTP 短/长请求 |
| 握手/标识 | Sec-WebSocket-Key + GUID SHA-1 | Last-Event-ID 重连头 | 每次带自定义游标 |
| 重连 | 手动实现，带 last_event_id | EventSource 自动重连 | 天然每次新请求 |
| 头部开销 | 小帧 2 字节 | 每事件若干文本行 | 每次完整 HTTP 头 |
| 适用 | 聊天、协同、游戏 | 行情、进度、日志流 | 兼容性兜底 |

<Compare :panels='[{"label": "主示例", "code": "import hashlib\nimport base64\n\nGUID = &#39;258EAFA5-E914-47DA-95CA-C5AB0DC85B11&#39;\nclient_key = &#39;dGhlIHNhbXBsZSBub25jZQ==&#39;\naccept = base64.b64encode(hashlib.sha1((client_key + GUID).encode()).digest()).decode()\nprint(&#39;Sec-WebSocket-Accept&#39;, accept)\nprint(&#39;GUID len&#39;, len(GUID))", "note": "三种通道：握手、帧与单向流"}, {"label": "对照 / 进阶", "code": "def sse_frame(event_id, event, data, retry_ms=3000):\n    lines = [&#39;id: &#39; + str(event_id), &#39;event: &#39; + event,\n             &#39;retry: &#39; + str(retry_ms), &#39;data: &#39; + data, &#39;&#39;, &#39;&#39;]\n    return chr(10).join(lines)\n\ndef resume(events, last_event_id):\n    return [e for e in events if e[&#39;id&#39;] &gt; last_event_id]\n\nevents = [{&#39;id&#39;: 1, &#39;data&#39;: &#39;a&#39;}, {&#39;id&#39;: 2, &#39;data&#39;: &#39;b&#39;}, {&#39;id&#39;: 3, &#39;data&#39;: &#39;c&#39;}]\nframe = sse_frame(3, &#39;tick&#39;, &#39;c&#39;)\nprint(&#39;frame lines&#39;, frame.split(chr(10)))\nprint(&#39;replay after id 1&#39;, resume(events, 1))", "note": "断线重连、消息补发与心跳背压"}]' title='两种写法对照' note='差异集中在 三种通道对比；先看输出，再找背后的规则。' />

<Callout type="tip" title='核心心智模型' text='WebSocket（RFC 6455）从一次 HTTP Upgrade 开始：客户端发 `Upgrade: websocket`、`Connection: Upgrade`、`Sec-WebSocket-Key`（16 字节随机值的 base64）与…' />


### WebSocket 帧的 opcode 与长度编码

**WebSocket 帧 opcode 与长度编码**

| 项 | 取值 | 含义 |
| --- | --- | --- |
| opcode | 0x1 / 0x2 | 文本帧 / 二进制帧 |
| opcode | 0x8 / 0x9 / 0xA | close / ping / pong 控制帧 |
| payload len | < 126 | 长度直接放第 2 字节，头共 2 字节 |
| payload len | 126 + 2 字节 | 126 到 65535，头共 4 字节 |
| payload len | 127 + 8 字节 | 更大长度，头共 10 字节 |
| 掩码位 | 客户端必须为 1 | 客户端到服务端的帧必须掩码 |


## 主示例：握手升级与一次消息收发

```python
import hashlib
import base64

GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
client_key = 'dGhlIHNhbXBsZSBub25jZQ=='
accept = base64.b64encode(hashlib.sha1((client_key + GUID).encode()).digest()).decode()
print('Sec-WebSocket-Accept', accept)
print('GUID len', len(GUID))
```

<OutputBox title='主示例运行结果' output='Sec-WebSocket-Accept s3pPLMBiTxaQ9kYGzzhZRbK+xOo=\nGUID len 36' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import hashlib\nimport base64\n\nGUID = &#39;258EAFA5-E914-47DA-95CA-C5AB0DC85B11&#39;\nclient_key = &#39;dGhlIHNhbXBsZSBub25jZQ==&#39;\naccept = base64.b64encode(hashlib.sha1((client_key + GUID).encode()).digest()).decode()\nprint(&#39;Sec-WebSocket-Accept&#39;, accept)\nprint(&#39;GUID len&#39;, len(GUID))' :notes='["导入 hashlib，握手校验要用 SHA-1", "导入 base64，Sec-WebSocket-Accept 是 base64 编码结果", "空行，只用于分隔逻辑块，不影响执行结果。", "RFC 6455 规定的固定 GUID，所有实现都用这一个常量", "客户端发来的 Sec-WebSocket-Key，值取自 RFC 示例", "把 key 与 GUID 拼接后取 SHA-1，再做 base64 得到 Accept", "打印计算结果，用于和客户端/服务端抓包比对", "GUID 长度 36，是标准 UUID 字符串形式"]' title='第 086 讲 · WebSocket / SSE / 长轮询与实时推送' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import struct

OPCODE = {'text': 0x1, 'binary': 0x2, 'close': 0x8, 'ping': 0x9, 'pong': 0xA}
def header(n):
    if n < 126:
        return bytes([0x80 | OPCODE['text'], n])
    elif n < 65536:
        return bytes([0x80 | OPCODE['text'], 126]) + struct.pack('!H', n)
    return bytes([0x80 | OPCODE['text'], 127]) + struct.pack('!Q', n)
for n in (5, 125, 126, 70000):
    print(n, '->', len(header(n)), 'header bytes')
```

<OutputBox title='原理验证' output='5 -&gt; 2 header bytes\n125 -&gt; 2 header bytes\n126 -&gt; 4 header bytes\n70000 -&gt; 10 header bytes' />


### 对照：边缘只收一帧与读到空

```python
def sse_frame(event_id, event, data, retry_ms=3000):
    lines = ['id: ' + str(event_id), 'event: ' + event,
             'retry: ' + str(retry_ms), 'data: ' + data, '', '']
    return chr(10).join(lines)

def resume(events, last_event_id):
    return [e for e in events if e['id'] > last_event_id]

events = [{'id': 1, 'data': 'a'}, {'id': 2, 'data': 'b'}, {'id': 3, 'data': 'c'}]
frame = sse_frame(3, 'tick', 'c')
print('frame lines', frame.split(chr(10)))
print('replay after id 1', resume(events, 1))
```

<OutputBox title='对照写法：先自己猜，再点开' output='frame lines [&#39;id: 3&#39;, &#39;event: tick&#39;, &#39;retry: 3000&#39;, &#39;data: c&#39;, &#39;&#39;, &#39;&#39;]\nreplay after id 1 [{&#39;id&#39;: 2, &#39;data&#39;: &#39;b&#39;}, {&#39;id&#39;: 3, &#39;data&#39;: &#39;c&#39;}]' guess="true" />


## 断线重连、消息补发与心跳背压

实时系统的可靠性在断线之后。TCP 半开（一端已断、另一端未收到 `FIN`）靠应用层心跳发现：WebSocket 用 `ping` / `pong` 控制帧，SSE 用注释行 `: keep-alive` 定期写入，超过若干周期无响应即判定死亡并清理。

重连要带偏移：SSE 用 `Last-Event-ID`，WebSocket 则在连接建立的首条消息里带客户端记录的 `last_event_id`，服务端据此从持久化日志（Redis Stream、Kafka）补发缺失消息，而不是把状态只放在单机内存。

消息必须有单调递增的 `id` 与去重能力，客户端按 `id` 去重，避免补发与实时推送重叠造成重复。背压同样关键：慢客户端的发送缓冲区会被写满，若服务端无脑 `send`，内存随队列增长；

正确做法是给每个连接设带上限的有界队列、超限就降级（丢弃低优先级消息或断开让客户端带 `id` 重连），并用 TCP 背压或应用层 `ack` 控制速率。连接清理要有空闲超时与总数上限，防止半开连接耗尽 `fd`。

<ConceptDiagram type='flow4' title='第 086 讲 · 三种通道：握手、帧与单向流' labels='三种通道：握手、帧与单向流|断线重连、消息补发与心跳背压|水平扩展：跨实例广播与粘性会话|水平扩展与粘性会话' caption='为实时场景选对通道并管理连接状态' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

<Callout type="warn" title='本讲最容易踩的坑' text='把 WebSocket 连接对象只存在单机内存，扩容后用户收不到别人发的消息：负载均衡把连接分散到不同实例，本机广播到不了其它实例持有的连接' />


## 水平扩展：跨实例广播与粘性会话

单机内存里的连接表在扩容后必然失效：用户重连到另一实例，既拿不到旧连接的订阅关系，也收不到别的实例产生的消息。两条路线：一是让所有实例订阅同一个 Redis Pub/Sub 频道或 Kafka 主题，任意实例产生消息就广播到频道，每台实例收到后只推给本机持有的连接；

消息日志同时用于重连补发（Redis Stream 的 `XREAD` 从 `last_id` 续读）。二是粘性会话（sticky session），让负载均衡按用户 `id` 或 cookie 把同一用户的连接固定到同一实例，简化状态但引入扩容迁移与单点热点问题，且实例宕机时仍要重连补发。

无论哪条，连接状态都要区分「连接态」（本机持有、不可共享）与「订阅态 / 消息日志」（共享存储、可重建）。广播还要防环与放大：给消息带来源实例 `id`，实例收到自己发出的广播直接丢弃；扇出前先按订阅过滤，别把全量消息推给所有连接。

容量上按「单机可维持连接数 × 内存 / 连接」估算，压测时同时观察 `fd`、发送队列长度与心跳超时率。

**实时系统故障与修复**

| 现象 | 根因 | 修复 |
| --- | --- | --- |
| 扩容后收不到消息 | 连接表只在单机内存 | Redis Pub/Sub 或 Kafka 跨实例广播 |
| 刷新丢未读 | 消息未持久化、无 last_event_id | Redis Stream 存日志，重连按 id 补发 |
| 半开连接耗尽 fd | 无心跳与空闲清理 | ping/pong + 空闲超时 + 总数上限 |
| 慢客户端拖垮服务 | 发送队列无界 | 有界队列 + 超限降级/断开 |
| 广播成环放大 | 未标识来源实例 | 消息带 source_id，收到自产消息丢弃 |

<ArchBlueprint title='第 086 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "三种通道：握手、帧与单向流", "protocol": "调用 / 请求", "items": [{"label": "三种通道：握手、帧与单向…", "sub": "输入与前置", "detail": "WebSocket（RFC 6455）从一次 HTTP Upgrade 开始：客户端发 `Upgrade: websocket`、`Connection: Upgrade`、`Sec-WebSocket-Key`（16 字节随机值的 base64）与…", "tone": "blue"}]}, {"name": "核心规则", "note": "断线重连、消息补发与心跳背压", "protocol": "语言 / 运行时协议", "items": [{"label": "断线重连、消息补发与心跳…", "sub": "状态与边界", "detail": "实时系统的可靠性在断线之后。TCP 半开（一端已断、另一端未收到 `FIN`）靠应用层心跳发现：WebSocket 用 `ping` / `pong` 控制帧，SSE 用注释行 `: keep-alive` 定期写入，超过若干周期无响应即判定死亡并清理。重连要带偏移：SSE 用…", "tone": "purple"}]}, {"name": "落地与收尾", "note": "水平扩展：跨实例广播与粘性会话", "items": [{"label": "水平扩展：跨实例广播与粘…", "sub": "工程处理", "detail": "单机内存里的连接表在扩容后必然失效：用户重连到另一实例，既拿不到旧连接的订阅关系，也收不到别的实例产生的消息。两条路线：一是让所有实例订阅同一个 Redis Pub/Sub 频道或 Kafka 主题，任意实例产生消息就广播到频道，每台实例收到后只推给本机持有的连接；消息日志同时用于重连补发（Redi…", "tone": "green"}]}]' />


### 半开连接为什么把文件描述符耗尽

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把 WebSocket 连接对象只存在单机内…", "body": "负载均衡把连接分散到不同实例，本机广播到不了其它实例持有的连接", "tip": "用 Redis Pub/Sub 或 Kafka 做跨实例广播，消息日志用 Redis Stream/Kafka 持久化并重连补发；实例收到自产消息按 source_id 丢弃"}, {"title": "第 2 步：用 SETNX 式的心跳但只靠 TCP 判断…", "body": "一端断网不发 FIN，另一端内核无感知，连接表持续累积", "tip": "应用层 ping/pong 或 SSE 注释心跳，配合空闲超时与连接总数上限主动清理"}, {"title": "第 3 步：给每个慢客户端无界缓冲并同步 send，内存…", "body": "发送队列没有上限，背压无法回传到生产者", "tip": "每连接用有界队列，超限丢弃低优先级消息或断开让客户端带 last_event_id 重连，并按订阅先过滤再扇出"}]' />


## 帧、ping/pong 与背压的协议层来源

WebSocket 握手把 `HTTP` 连接升级为一条长期存活的 TCP 双工通道，`Sec-WebSocket-Accept` 的计算（key + 固定 `GUID` → SHA-1 → base64）不是为了加密，而是让服务端证明确实理解 WebSocket 协议、并防止缓存代理把普通 `HTTP` 请求误当升级响应。

升级后数据以帧传输：`FIN` 与 `opcode` 在首字节，长度用变长编码（`126` / `127` 作为扩展标记）以兼顾小帧效率与大消息，客户端帧必须带 4 字节掩码以缓解代理缓存污染。

SSE 则完全复用 `HTTP`：服务器保持响应体不结束，按空行分隔写文本事件，浏览器 `EventSource` 在断线时自动带上 `Last-Event-ID` 重连，服务端据此做增量补发——这把「可靠投递」下沉成 `id` + 日志两个可持久化的东西。

TCP 无法感知半开连接，因此心跳（`ping` / `pong` 或注释行）是应用层存活探测；背压来自内核发送缓冲区与用户态队列，慢消费者会填满它们。

跨实例广播用发布订阅把「消息产生」与「连接持有」解耦：共享日志负责可重放，本机连接表负责最后的扇出，这样任一实例宕机都能通过重连 + 按 `id` 补发恢复，而状态不在进程内存里丢掉。

<Term word='三种通道对比' text='WebSocket（RFC 6455）从一次 HTTP Upgrade 开始：客户端发 `Upgrade: websocket`、`Connection: Upgrade`、`Sec-WebSocket-Key`（16 字节随机值的 base64）与 `Sec-WebSocket-Version: 13`；服务端把该…' />

<Term word='握手与帧' text='实时系统的可靠性在断线之后。TCP 半开（一端已断、另一端未收到 `FIN`）靠应用层心跳发现：WebSocket 用 `ping` / `pong` 控制帧，SSE 用注释行 `: keep-alive` 定期写入，超过若干周期无响应即判定死亡并清理。重连要带偏移：SSE 用 `Last-Event-ID`，WebS…' />

<FlowTimeline :steps='[{"title": "三种通道：握手、帧与单向流", "desc": "WebSocket（RFC 6455）从一次 HTTP Upgrade 开始：客户端…", "tone": "blue"}, {"title": "断线重连、消息补发与心跳背压", "desc": "实时系统的可靠性在断线之后。TCP 半开（一端已断、另一端未收到 `FIN`）靠应用…", "tone": "purple"}, {"title": "水平扩展：跨实例广播与粘性会话", "desc": "单机内存里的连接表在扩容后必然失效：用户重连到另一实例，既拿不到旧连接的订阅关系，也…", "tone": "orange"}, {"title": "工程落地", "desc": "带心跳、有界队列与重连补发的连接管理器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 带心跳、有界队列与重连补发的连接管理器

下面用标准库实现一个缩略版连接管理器，把三个关键约束写成可运行代码：连接表按 `conn_id` 索引、每条连接有有界发送队列（满则丢最旧消息并计 `dropped`）；消息日志按自增 `id` 持久化，重连时按 `last_event_id` 补发；

`broadcast` 只推给本机连接并过滤订阅主题，同时带 `source_id` 防环。`tick` 模拟心跳，把超过 `idle_limit` 没活动的连接剔除，防止半开连接堆积。

真实项目把 `queue` 换成网络写、把 `log` 换成 Redis Stream、用 Redis Pub/Sub 接跨实例消息，但连接态与消息日志分离、有界队列、按 `id` 补发这三条结构不变。

```python
import collections
import time

class Hub:
    def __init__(self, max_queue=3, idle_limit=30):
        self.conns = {}
        self.log = []
        self.next_id = 1
        self.max_queue = max_queue
        self.idle_limit = idle_limit
        self.dropped = 0
    def connect(self, cid, topics, now):
        self.conns[cid] = {'queue': collections.deque(), 'topics': set(topics), 'last': now}
    def publish(self, topic, payload, source='local'):
        msg = {'id': self.next_id, 'topic': topic, 'data': payload, 'source': source}
        self.next_id += 1
        self.log.append(msg)
        self.fanout(msg)
        return msg['id']
    def fanout(self, msg):
        for cid, c in self.conns.items():
            if msg['topic'] not in c['topics'] or msg['source'] == cid:
                continue
            if len(c['queue']) >= self.max_queue:
                c['queue'].popleft()
                self.dropped += 1
            c['queue'].append(msg)
    def resume(self, last_id):
        return [m for m in self.log if m['id'] > last_id]
    def tick(self, now):
        dead = [cid for cid, c in self.conns.items() if now - c['last'] > self.idle_limit]
        for cid in dead:
            del self.conns[cid]
        return dead

hub = Hub(max_queue=2, idle_limit=10)
hub.connect('c1', ('price',), now=0)
hub.connect('c2', ('news',), now=0)
for i in range(3):
    hub.publish('price', i)
print('c1 queued', len(hub.conns['c1']['queue']))
print('c2 queued', len(hub.conns['c2']['queue']))
print('dropped', hub.dropped)
print('resume from 1', [m['id'] for m in hub.resume(1)])
print('dead after tick', hub.tick(now=11))
```

<Callout type="idea" title='落地提示' text='用 Redis Pub/Sub 或消息中间件做跨实例广播，客户端带 last_event_id 重连，服务端做心跳与空闲清理' />

<CheckList id='P086b' title='上线前自检' :items='["能复现并解释「把 WebSocket 连接对象只存在单机内存，扩容后用户收…」", "能复现并解释「用 SETNX 式的心跳但只靠 TCP 判断存活，半开连接把…」", "能复现并解释「给每个慢客户端无界缓冲并同步 send，内存随积压增长」", "能用一条命令验证 三种通道对比", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from urllib.parse import urlencode; print(urlencode({'page':2}))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 三种通道对比 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把 WebSocket 连接对象只存在单机内存，扩容后用户收不到别人发的消息 | 负载均衡把连接分散到不同实例，本机广播到不了其它实例持有的连接 | 用 Redis Pub/Sub 或 Kafka 做跨实例广播，消息日志用 Redis Stream/Kafka 持久化并重连补发；实例收到自产消息按 source_id 丢弃 |
| 用 SETNX 式的心跳但只靠 TCP 判断存活，半开连接把文件描述符耗尽 | 一端断网不发 FIN，另一端内核无感知，连接表持续累积 | 应用层 ping/pong 或 SSE 注释心跳，配合空闲超时与连接总数上限主动清理 |
| 给每个慢客户端无界缓冲并同步 send，内存随积压增长 | 发送队列没有上限，背压无法回传到生产者 | 每连接用有界队列，超限丢弃低优先级消息或断开让客户端带 last_event_id 重连，并按订阅先过滤再扇出 |


## 练习、自测与一页纸速记

<Exercise title='基础：复现 WebSocket 握手校验' task='写一个函数 accept(key)，实现 key + GUID 的 SHA-1 再 base64，验证 RFC 6455 示例 key 得到 s3pPLMBiTxaQ9kYGzzhZRbK+xOo=，并说明 GUID 的作用。' solution='import hashlib, base64\nGUID = &#39;258EAFA5-E914-47DA-95CA-C5AB0DC85B11&#39;\ndef accept(key):\n    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()\nprint(accept(&#39;dGhlIHNhbXBsZSBub25jZQ==&#39;))' explain='GUID 是协议固定的常量，用于让服务端证明理解 WebSocket 并防止缓存代理误复用 HTTP 响应；它不是密钥，算法是 SHA-1 后 base64。' />

<Exercise title='进阶：给 SSE 加编号与断线补发' task='实现 sse_frame(id, event, data) 生成含 id/event/data/retry 的帧，并实现 resume(log, last_id) 按 id 补发，构造三条事件验证从 last_id=1 重连能拿到后两条。' solution='def sse_frame(eid, event, data, retry=3000):\n    lines = [&#39;id: &#39; + str(eid), &#39;event: &#39; + event, &#39;retry: &#39; + str(retry), &#39;data: &#39; + data, &#39;&#39;, &#39;&#39;]\n    return chr(10).join(lines)\ndef resume(log, last_id):\n    return [m for m in log if m[&#39;id&#39;] &gt; last_id]\nlog = [{&#39;id&#39;: 1, &#39;data&#39;: &#39;a&#39;}, {&#39;id&#39;: 2, &#39;data&#39;: &#39;b&#39;}, {&#39;id&#39;: 3, &#39;data&#39;: &#39;c&#39;}]\nprint(sse_frame(3, &#39;tick&#39;, &#39;c&#39;).split(chr(10)))\nprint(resume(log, 1))' explain='SSE 帧以空行结束，EventSource 重连时把最后收到的 id 放进 Last-Event-ID；服务端按 id 从日志续发，客户端按 id 去重，保证不丢不重。' />

<Quiz no='086-1' q='WebSocket 服务端计算 Sec-WebSocket-Accept 的正确过程是？' :options='["把 Sec-WebSocket-Key 与固定 GUID 拼接，取 SHA-1 后 base64", "对 key 做 HMAC-SHA256", "把 key 原样 base64 回显", "对整段 HTTP 头做 MD5"]' answer="0" explain='RFC 6455 规定：拼接 key 与 GUID 258EAFA5-...，SHA-1 摘要再 base64；这是协议一致性校验，不是加密或认证。' />

<Quiz no='086-2' q='服务端单向推送进度与日志，且希望浏览器自动重连，最合适的通道是？' :options='["SSE，text/event-stream 配 Last-Event-ID 自动重连", "WebSocket，全双工帧", "长轮询，每次重建请求", "普通短轮询 GET"]' answer="0" explain='单向推送用 SSE 最省：复用 HTTP、EventSource 内置断线重连并带 Last-Event-ID；WebSocket 适合双向互动，长轮询只是兼容兜底。' />

<Quiz no='086-3' q='扩容到多实例后消息广播的正确做法是？' :options='["用 Redis Pub/Sub 或 Kafka 跨实例广播，消息日志持久化并重连补发", "把连接表做成进程内全局单例", "让所有用户粘性到同一实例即可，不需其它改动", "每条消息写数据库让各实例轮询"]' answer="0" explain='连接态本机持有、订阅与消息日志必须共享：发布订阅负责跨实例扇出，Redis Stream/Kafka 负责按 id 重连补发；粘性会话不能解决宕机后的状态重建。' />

<Predict no='086-4' q='对长度 5、125、126、70000 的 WebSocket 文本帧（服务端不掩码），帧头各占多少字节？' :options='["2、2、4、10", "2、2、2、2", "6、6、8、14"]' answer='0' output='5 -&gt; 2 header bytes; 125 -&gt; 2 header bytes; 126 -&gt; 4 header bytes; 70000 -&gt; 10 header bytes' explain='RFC 6455 的变长长度编码：小于 126 时长度直接放第 2 字节（头 2 字节），126 触发后接 2 字节（头 4 字节），127 触发后接 8 字节（头 10 字节）。' />

<FillBlank no='086-5' tpl='___ hashlib' :answers='["import"]' hint='回想本讲关于 三种通道对比 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 三种通道：握手、帧与单向流 的落点。' />

<KnowledgeCard :points='["WebSocket 握手：key + 固定 GUID 取 SHA-1 再 base64 得 Sec-WebSocket-Accept，状态 101", "帧 opcode：0x1 文本、0x2 二进制、0x8 close、0x9 ping、0xA pong；长度 &lt;126/126/127 三段变长", "SSE 是 text/event-stream 单向流，EventSource 自动带 Last-Event-ID 重连，适合通知/日志", "心跳探活 + 空闲超时 + 连接总数上限；慢客户端用有界队列与降级防背压", "连接态本机持有、消息日志共享持久化；Redis Pub/Sub/Kafka 跨实例广播，按 id 补发", "消息带 source_id 防环、带单调 id 去重；补发与实时推送重叠靠客户端按 id 去重"]' :pitfalls='["把 WebSocket 连接对象只存在单机内存，扩容后用户收不到别人发的消息", "用 SETNX 式的心跳但只靠 TCP 判断存活，半开连接把文件描述符耗尽", "给每个慢客户端无界缓冲并同步 send，内存随积压增长", "把连接状态只存在单机内存里，扩容后用户重连到另一台实例就会丢消息"]' summary='实时推送的难点从来不是发第一条消息，而是断线重连、消息补发与多实例之间的广播' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| WebSocket 握手：key + 固定 GUID 取 SHA-1 再 base64 得 Sec-WebSocket-Accept，状态 101 | 建立直觉 |
| 帧 opcode：0x1 文本、0x2 二进制、0x8 close、0x9 ping、0xA pong；长度 <126/126/127 三段变长 | 跑通示例 |
| SSE 是 text/event-stream 单向流，EventSource 自动带 Last-Event-ID 重连，适合通知/日志 | 深入边界 |
| 心跳探活 + 空闲超时 + 连接总数上限；慢客户端用有界队列与降级防背压 | 工程落地 |
| 连接态本机持有、消息日志共享持久化；Redis Pub/Sub/Kafka 跨实例广播，按 id 补发 | 随堂检测 |
| 消息带 source_id 防环、带单调 id 去重；补发与实时推送重叠靠客户端按 id 去重 | 复盘 |

1. WebSocket 握手：key + 固定 GUID 取 SHA-1 再 base64 得 Sec-WebSocket-Accept，状态 101

2. 帧 opcode：0x1 文本、0x2 二进制、0x8 close、0x9 ping、0xA pong；长度 <126/126/127 三段变长

3. SSE 是 text/event-stream 单向流，EventSource 自动带 Last-Event-ID 重连，适合通知/日志

[下一讲：SQLAlchemy、连接池、事务与迁移](/server/orm)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/086-websocket.py`

```bash
python3 examples/lessons/086-websocket.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/086-websocket.py) · [全部示例代码索引](/examples/)
