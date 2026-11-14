---
title: 第 130 讲 · 实战 09 · KV 贯穿线 ② 协议帧与网络层
description: 用 asyncio 实现可并发的服务端
---

<StageHeader stage='L12 · 工程实战' level='★★★★☆' time='55 分钟' goal='用 asyncio 实现可并发的服务端' prereq='第 129 讲 · 实战 08 · KV 贯穿线 ① 内存版与接口抽象' />

# 第 130 讲 · 实战 09 · KV 贯穿线 ② 协议帧与网络层

上一讲把命令语义和窄接口钉稳；这一讲给它开一扇远程的门，上层命令一行都不用动。难点很朴素：`TCP` 是连成一片的字节流，不替你标出消息从哪到哪。

第一版用换行分隔命令，值里带换行就把一条拆成两条；另一个客户端一次发来两条，服务端并成一帧；又没设长度上限，一个超长请求就能把内存吃满。我们先用长度前缀加最大帧限制把一帧框清楚，再比较序列化选型，然后用 `asyncio` 的 `readexactly` 收拾拆包粘包、连接管理与超时，最后包一个 SDK。需要你熟悉上一步的命令模型与 `asyncio`；学完 KV 能被多个客户端并发访问，只是数据还全在内存。


## 一次 read 既可能拿到半条命令，也可能拿到两条半

给内存 KV 加网络层，团队第一版用换行分隔命令：客户端发 `SET k v` 后加一个换行，服务端 `readline` 读一行。上线当天就出错——某个用户的值里带了换行，一条命令被拆成两行，第二条被当成新命令解析，状态彻底错乱；另一个客户端一次发来两条命令，服务端把两帧当成一帧处理，把值拼到了键后面。

还没有长度上限，一个恶意请求声明超长 body 直接把内存吃满。根因只有一个：`TCP` 是字节流，没有消息边界，一次 `read` 既可能拿到半条命令也可能拿到两条半。

这一讲用长度前缀加 `MAGIC`、版本、`CRC32` 与最大帧限制定义协议帧，用 `asyncio` 的 `readexactly` 解决拆包粘包，并用契约测试覆盖半包、粘包、超大帧与校验和错误。

```python
import struct, zlib, inspect, os

print('H size', struct.calcsize('>H'))
print('I size', struct.calcsize('>I'))
print('big endian', struct.pack('>H', 258).hex())
print('little endian', struct.pack('<H', 258).hex())
print('crc32 KV1', zlib.crc32(b'KV1'))
print('crc32 empty', zlib.crc32(b''))
print('fsync signature', str(inspect.signature(os.fsync)))
```

<OutputBox title='原理验证' output='H size 2\nI size 4\nbig endian 0102\nlittle endian 0201\ncrc32 KV1 1051804123\ncrc32 empty 0\nfsync signature (fd)' />


## TCP 字节流与长度前缀帧：消息边界要自己造

`TCP` 只保证字节按序到达，不保留 send 的边界：内核按 MSS、发送/接收缓冲与 Nagle 算法任意切分，一次 `recv` 可能拿到半条、一条半、多条，这是拆包与粘包的根源。换行分隔在值里含换行时立即失效，且要为分隔符做转义；

正确做法是长度前缀：固定字节头声明 body 长度，例如 `struct.pack('>H', n)` 两字节大端（网络字节序），或 `'>I'` 四字节，最大 `2^32-1`，但生产必须另设 `MAX_FRAME`（如 1MB）防止单条超大请求打满内存。

帧头再加 `MAGIC`（如 `b'KV'`）快速识别协议、`VERSION` 显式版本号便于不兼容升级、`CRC32`（`zlib.crc32`，检错不防篡改，防篡改要 `HMAC`）。

服务端用 `asyncio.StreamReader.readexactly` 精确读 n 字节，它内部循环 `read` 直到凑齐或抛 `IncompleteReadError`；

半包要先把已到字节缓存进缓冲区等下一批，粘包要在一个循环里连续切出多帧。失效信号：偶发解析错位、大请求打满内存、旧客户端连上后返回乱码。

**帧格式字段布局**

| 偏移 | 字段 | 字节数 | 作用 |
| --- | --- | --- | --- |
| 0-1 | MAGIC b'KV' | 2 | 识别协议，错则拒绝 |
| 2 | VERSION | 1 | 版本协商，不兼容升级时拒绝 |
| 3-4 | 长度 >H | 2 | body 字节数，最大 65535 |
| 5.. | body | length | 命令文本，需另设 MAX_FRAME |
| 尾 4 字节 | CRC32 >I | 4 | 检错，不符返回 bad checksum |

```python
import struct, zlib

MAGIC = b'KV'
VERSION = 1
MAX_FRAME = 1024

def encode(op, key, value=b''):
    parts = [op.encode(), key.encode()]
    if value:
        parts.append(value)
    body = b' '.join(parts)
    frame = MAGIC + bytes([VERSION]) + struct.pack('>H', len(body)) + body
    crc = zlib.crc32(frame) & 0xffffffff
    return frame + struct.pack('>I', crc)

def decode(stream):
    out = []
    while len(stream) >= 9:
        if stream[:2] != MAGIC:
            return out, 'bad magic'
        ver = stream[2]
        length = struct.unpack('>H', stream[3:5])[0]
        total = 5 + length + 4
        if length > MAX_FRAME:
            return out, 'frame too large'
        if len(stream) < total:
            break
        frame = stream[:5 + length]
        got = struct.unpack('>I', stream[5 + length:total])[0]
        if (zlib.crc32(frame) & 0xffffffff) != got:
            return out, 'bad checksum'
        if ver != VERSION:
            return out, 'version mismatch'
        out.append(frame[5:5 + length].decode())
        stream = stream[total:]
    return out, 'complete' if not stream else 'partial'

f1 = encode('SET', 'a', b'1')
f2 = encode('GET', 'a')
print('frame sizes', len(f1), len(f2))
print('two in one read', decode(f1 + f2))
print('half frame', decode(f1[:9]))
print('with tail', decode(f1 + f2[:-3]))
bad = bytearray(f1)
bad[-1] ^= 1
print('corrupt', decode(bytes(bad)))
print('oversize', decode(encode('SET', 'k', b'x' * 1100)))
```

<OutputBox title='主示例运行结果' output='frame sizes 16 14\ntwo in one read ([&#39;SET a 1&#39;, &#39;GET a&#39;], &#39;complete&#39;)\nhalf frame ([], &#39;partial&#39;)\nwith tail ([&#39;SET a 1&#39;], &#39;partial&#39;)\ncorrupt ([], &#39;bad checksum&#39;)\noversize ([], &#39;frame too large&#39;)' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import struct, zlib\n\nMAGIC = b&#39;KV&#39;\nVERSION = 1\nMAX_FRAME = 1024\n\ndef encode(op, key, value=b&#39;&#39;):\n    parts = [op.encode(), key.encode()]\n    if value:\n        parts.append(value)\n    body = b&#39; &#39;.join(parts)\n    frame = MAGIC + bytes([VERSION]) + struct.pack(&#39;&gt;H&#39;, len(body)) + body\n    crc = zlib.crc32(frame) &amp; 0xffffffff\n    return frame + struct.pack(&#39;&gt;I&#39;, crc)\n\ndef decode(stream):\n    out = []\n    while len(stream) &gt;= 9:\n        if stream[:2] != MAGIC:\n            return out, &#39;bad magic&#39;\n        ver = stream[2]\n        length = struct.unpack(&#39;&gt;H&#39;, stream[3:5])[0]\n        total = 5 + length + 4\n        if length &gt; MAX_FRAME:\n            return out, &#39;frame too large&#39;\n        if len(stream) &lt; total:\n            break\n        frame = stream[:5 + length]\n        got = struct.unpack(&#39;&gt;I&#39;, stream[5 + length:total])[0]\n        if (zlib.crc32(frame) &amp; 0xffffffff) != got:\n            return out, &#39;bad checksum&#39;\n        if ver != VERSION:\n            return out, &#39;version mismatch&#39;\n        out.append(frame[5:5 + length].decode())\n        stream = stream[total:]\n    return out, &#39;complete&#39; if not stream else &#39;partial&#39;\n\nf1 = encode(&#39;SET&#39;, &#39;a&#39;, b&#39;1&#39;)\nf2 = encode(&#39;GET&#39;, &#39;a&#39;)\nprint(&#39;frame sizes&#39;, len(f1), len(f2))\nprint(&#39;two in one read&#39;, decode(f1 + f2))\nprint(&#39;half frame&#39;, decode(f1[:9]))\nprint(&#39;with tail&#39;, decode(f1 + f2[:-3]))\nbad = bytearray(f1)\nbad[-1] ^= 1\nprint(&#39;corrupt&#39;, decode(bytes(bad)))\nprint(&#39;oversize&#39;, decode(encode(&#39;SET&#39;, &#39;k&#39;, b&#39;x&#39; * 1100)))' :notes='["导入 struct 处理定长头、zlib 做 CRC32 校验", "空行，只用于分隔逻辑块，不影响执行结果。", "MAGIC 两字节，快速识别这是本协议的帧", "显式版本号，不兼容升级时据此拒绝老格式", "最大帧上限，防止单条超大请求打满内存", "空行，只用于分隔逻辑块，不影响执行结果。", "encode 把命令编码成一条完整帧", "把 op 与 key 编成字节列表", "有值时才追加，避免尾部多余的空格", "把值字节追加进 parts", "用空格拼成 body，长度由此确定", "帧 = MAGIC + 版本 + 两字节大端长度 + body", "对帧头与 body 计算 CRC32，只检错不防篡改", "帧尾追加四字节大端校验和", "空行，只用于分隔逻辑块，不影响执行结果。", "decode 从字节流里连续切出所有完整帧", "out 收集已解出的 body 文本", "stream 至少要有最小完整帧长度才进入解析", "MAGIC 不符立即返回错误，避免按错格式解析", "返回 bad magic 状态，不继续按错格式解析", "读出版本号供兼容性判断", "按两字节大端读出 body 长度", "整帧长度 = 5 字节头 + body + 4 字节校验和", "超过 MAX_FRAME 直接拒绝，不分配大缓冲", "返回 frame too large，超限帧一律拒绝", "字节不够一整帧就跳出，保留 stream 供下次续读", "break 保留剩余 stream，等下一批字节续读", "取出帧头加 body 用于校验", "读出帧尾携带的校验和", "重算 CRC 与携带值比较，不符说明损坏", "校验和错误返回明确状态", "版本不匹配也返回明确状态而非静默错解", "返回 version mismatch，交给上层做版本协商", "校验通过的 body 解码成文本加入结果", "切掉已消费的一帧，继续处理粘包的后续帧", "流被消费完返回 complete，否则返回 partial", "空行，只用于分隔逻辑块，不影响执行结果。", "编码一条 SET 帧", "编码一条 GET 帧", "打印两帧字节长度，验证头部开销固定", "把两帧拼成一次 read 的字节流，验证粘包切分", "只给前半帧，验证拆包时返回 partial", "一帧加半帧，验证切出一条后仍报 partial", "把合法帧拷成可变的 bytearray", "翻转校验和最后一个字节，制造损坏", "打印损坏帧的解码结果，应为 bad checksum", "构造超过 MAX_FRAME 的帧，验证上限拦截"]' title='第 130 讲 · 实战 09 · KV 贯穿线 ② 协议帧与网络层' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：换行分隔遇到含换行的值就失效

```python
def frame_newline(value):
    return b'SET k ' + value

def cut_newline(stream):
    return [p for p in stream.split(bytes([10])) if p]

one = frame_newline(b'hello')
two = frame_newline(b'a' + bytes([10]) + b'b')
print('single', cut_newline(one))
print('value with newline', cut_newline(two))
```

<OutputBox title='对照写法：先自己猜，再点开' output='single [b&#39;SET k hello&#39;]\nvalue with newline [b&#39;SET k a&#39;, b&#39;b&#39;]' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import struct, zlib\n\nMAGIC = b&#39;KV&#39;\nVERSION = 1\nMAX_FRAME = 1024\n\ndef encode(op, key, value=b&#39;&#39;):\n    parts = [op.encode(), key.encode()]\n    if value:\n        parts.append(value)\n    body = b&#39; &#39;.join(parts)\n    frame = MAGIC + bytes([VERSION]) + struct.pack(&#39;&gt;H&#39;, len(body)) + body\n    crc = zlib.crc32(frame) &amp; 0xffffffff\n    return frame + struct.pack(&#39;&gt;I&#39;, crc)\n\ndef decode(stream):\n    out = []\n    while len(stream) &gt;= 9:\n        if stream[:2] != MAGIC:\n            return out, &#39;bad magic&#39;\n        ver = stream[2]\n        length = struct.unpack(&#39;&gt;H&#39;, stream[3:5])[0]\n        total = 5 + length + 4\n        if length &gt; MAX_FRAME:\n            return out, &#39;frame too large&#39;\n        if len(stream) &lt; total:\n            break\n        frame = stream[:5 + length]\n        got = struct.unpack(&#39;&gt;I&#39;, stream[5 + length:total])[0]\n        if (zlib.crc32(frame) &amp; 0xffffffff) != got:\n            return out, &#39;bad checksum&#39;\n        if ver != VERSION:\n            return out, &#39;version mismatch&#39;\n        out.append(frame[5:5 + length].decode())\n        stream = stream[total:]\n    return out, &#39;complete&#39; if not stream else &#39;partial&#39;\n\nf1 = encode(&#39;SET&#39;, &#39;a&#39;, b&#39;1&#39;)\nf2 = encode(&#39;GET&#39;, &#39;a&#39;)\nprint(&#39;frame sizes&#39;, len(f1), len(f2))\nprint(&#39;two in one read&#39;, decode(f1 + f2))\nprint(&#39;half frame&#39;, decode(f1[:9]))\nprint(&#39;with tail&#39;, decode(f1 + f2[:-3]))\nbad = bytearray(f1)\nbad[-1] ^= 1\nprint(&#39;corrupt&#39;, decode(bytes(bad)))\nprint(&#39;oversize&#39;, decode(encode(&#39;SET&#39;, &#39;k&#39;, b&#39;x&#39; * 1100)))", "note": "TCP 字节流与长度前缀帧：消息边界要自己造"}, {"label": "对照 / 进阶", "code": "def frame_newline(value):\n    return b&#39;SET k &#39; + value\n\ndef cut_newline(stream):\n    return [p for p in stream.split(bytes([10])) if p]\n\none = frame_newline(b&#39;hello&#39;)\ntwo = frame_newline(b&#39;a&#39; + bytes([10]) + b&#39;b&#39;)\nprint(&#39;single&#39;, cut_newline(one))\nprint(&#39;value with newline&#39;, cut_newline(two))", "note": "序列化选型与 asyncio 服务端"}]' title='两种写法对照' note='差异集中在 TCP 粘包与长度前缀；先看输出，再找背后的规则。' />


## 长度前缀与半包：decode 为什么返回 partial

<Callout type="tip" title='核心心智模型' text='`TCP` 只保证字节按序到达，不保留 send 的边界：内核按 MSS、发送/接收缓冲与 Nagle 算法任意切分，一次 `recv` 可能拿到半条、一条半、多条，这是拆包与粘包的根源。换行分隔在值里含换行时立即失效，且要为分隔符做转义；正确做法是长度前缀：固定字节头声明 body 长度，例如…' />

<ConceptDiagram type='flow3' title='第 130 讲 · TCP 字节流与长度前缀帧：消息边界要自己造' labels='TCP 字节流与长度前缀帧：消息边界要自己造|序列化选型与 asyncio 服务端|协议兼容、契约测试与失败模式' caption='用 asyncio 实现可并发的服务端' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### 两帧一次到、半帧、超大帧与坏校验和

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用换行分隔命令，值里含换行就失效", "body": "TCP 字节流里换行只是普通字节，值中的换行会把一条命令拆成两行", "tip": "改用长度前缀帧，值可以含任意字节；服务端用 readexactly 精确读取"}, {"title": "第 2 步：不设最大帧长度，单条超大请求打满内存", "body": "长度字段可声明极大 body，服务端按声明分配缓冲", "tip": "在解析出 length 后先与 MAX_FRAME 比较，超限立即返回 frame too large"}, {"title": "第 3 步：只测能跑通，不测半包与粘包", "body": "边界错误偶发且难复现，上线后才暴露为解析错位", "tip": "写逐字节契约测试覆盖半包、粘包、超大帧、错误 MAGIC、校验和错误、连接中断"}]' />


## 序列化选型对照与显式版本号

文本协议（空格分隔）简单可调试，但值里含空格或换行就要转义；`json.dumps`/`loads` 跨语言、可读、`sort_keys=True` 可让字节稳定，但不支持裸二进制且数字精度有限；msgpack 与 Protobuf 紧凑且有 schema，需第三方库；

`pickle` 绝不能用于网络——反序列化会执行任意代码，是明确的远程代码执行风险；`struct` 适合定长头与数值。

服务端用 `asyncio.start_server` 返回 `Server`，每个连接调一次 `handle(reader, writer)` 协程；

连接管理要设超时（`asyncio.wait_for` 或 3.11 起的 `asyncio.timeout` 上下文）、限制并发连接数（`Semaphore`）、处理半关闭（EOF 时 `readexactly` 抛 `IncompleteReadError`，`finally` 里 `writer.close()` 配 `await writer.wait_closed()`），并记录 peer 地址。

客户端 SDK 封装 `open_connection`、帧编码、读响应、超时与重连，让调用方看不到字节。

绑定端口用 `('127.0.0.1', 0)` 让内核分配空闲端口，测试才不冲突。

**拆包粘包失败模式与契约测试**

| 场景 | 朴素写法后果 | 契约测试断言 |
| --- | --- | --- |
| 半包分两次到达 | readline 拿到残缺命令 | decode 返回 partial 且不出结果 |
| 两帧一次到达 | 两帧拼成一帧错解 | decode 切出两条并返回 complete |
| 单条超大帧 | 分配巨大缓冲打满内存 | length > MAX_FRAME 返回 frame too large |
| 校验和损坏 | 错数据被当成有效命令 | 返回 bad checksum |
| 连接中途断开 | readexactly 抛未捕获异常 | 捕获 IncompleteReadError 并半关闭 |


## asyncio start_server 与客户端 SDK

<ConceptDiagram type='layers3' title='第 130 讲 · 分层视角' labels='TCP 字节流与长度前缀帧：消息边界要自…|序列化选型与 asyncio 服务端|协议兼容、契约测试与失败模式|协议兼容与版本' caption='协议兼容、契约测试与失败模式' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 协议兼容与版本 落在哪一层。

<Term word='TCP 粘包与长度前缀' text='`TCP` 只保证字节按序到达，不保留 send 的边界：内核按 MSS、发送/接收缓冲与 Nagle 算法任意切分，一次 `recv` 可能拿到半条、一条半、多条，这是拆包与粘包的根源。换行分隔在值里含换行时立即失效，且要为分隔符做转义；正确做法是长度前缀：固定字节头声明 body 长度，例如…' />

<Term word='序列化选型' text='文本协议（空格分隔）简单可调试，但值里含空格或换行就要转义；`json.dumps`/`loads` 跨语言、可读、`sort_keys=True` 可让字节稳定，但不支持裸二进制且数字精度有限；msgpack 与 Protobuf 紧凑且有 schema，需第三方库；`pickle` 绝不能用于网络——反序列化会执行…' />


## TCP 的 send 边界在接收侧不可见

`TCP` 是面向字节流的传输层协议，send 的边界在接收侧不可见：内核按 MSS 与缓冲区切分，Nagle 还可能合并小包，因此消息边界必须由应用层协议自己定义。

长度前缀把边界编码进固定字节头，接收方用 `readexactly(n)` 循环 `read` 直到凑齐 n 字节或抛 `IncompleteReadError`，这正是把「不知道读多少」变成「精确读多少」；

`struct` 的 `>` 前缀指定大端（网络字节序），`'>H'` 是 2 字节、`'>I'` 是 4 字节，258 编码成 0102 而小端是 0201。`CRC32` 是循环冗余校验，能检出随机位翻转但不防恶意篡改，后者要 `HMAC`。

`asyncio` 的 `StreamReader`/`StreamWriter` 把 socket 包成协程友好的流，`start_server` 为每个连接起一个 `handle` 协程，`Semaphore` 与 `wait_for` 分别约束连接数与超时；端口 0 让内核分配空闲端口，避免测试冲突。

半关闭与 `TIME_WAIT` 由 `writer.close` 配 `wait_closed` 收尾。


## 最大帧长度、超时与半关闭处理

<Callout type="warn" title='本讲最容易踩的坑' text='用换行分隔命令，值里含换行就失效：TCP 字节流里换行只是普通字节，值中的换行会把一条命令拆成两行' />


## 协议兼容、契约测试与失败模式

版本号放在固定偏移，服务端对不支持的版本返回明确错误而非静默按新格式错解；新增可选字段要向后兼容（旧客户端忽略未知字段），不兼容变更升主版本并保留双协议并存窗口；后面网关要同时对接多家供应商时，用的也是这套「统一接口 + 版本协商」的思路。

契约测试必须逐字节覆盖：半包（一帧分两次到达）、粘包（两帧一次到达）、超大帧（`length` 超过 `MAX_FRAME`）、错误 `MAGIC`、校验和错误、版本不匹配、连接中途断开、读超时。断言要检查解码后的字节与预期完全一致，不能只测「能跑通」，否则边界错误会漏到线上。

三个失效信号：偶发解析错位、大请求打满内存、旧客户端连上后返回乱码。协议字段一旦上线就不能改偏移，新增内容只能追加可选字段或升版本。

**序列化选型对照**

| 方案 | 跨语言 | 二进制 | 主要风险 |
| --- | --- | --- | --- |
| 空格分隔文本 | 是 | 否 | 值含分隔符需转义 |
| JSON (sort_keys=True) | 是 | 否 | 无裸二进制、数字精度有限 |
| msgpack / Protobuf | 是 | 是 | 需第三方库与 schema 管理 |
| struct 定长头 | 是 | 是 | 只适合定长字段 |
| pickle | 否 | 是 | 反序列化执行任意代码，禁止用于网络 |

<CheckList id='P130b' title='上线前自检' :items='["能复现并解释「用换行分隔命令，值里含换行就失效」", "能复现并解释「不设最大帧长度，单条超大请求打满内存」", "能复现并解释「只测能跑通，不测半包与粘包」", "能用一条命令验证 TCP 粘包与长度前缀", "关键路径有自动化测试与失败分支"]' />


## 拆包粘包失败模式速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用换行分隔命令，值里含换行就失效 | TCP 字节流里换行只是普通字节，值中的换行会把一条命令拆成两行 | 改用长度前缀帧，值可以含任意字节；服务端用 readexactly 精确读取 |
| 不设最大帧长度，单条超大请求打满内存 | 长度字段可声明极大 body，服务端按声明分配缓冲 | 在解析出 length 后先与 MAX_FRAME 比较，超限立即返回 frame too large |
| 只测能跑通，不测半包与粘包 | 边界错误偶发且难复现，上线后才暴露为解析错位 | 写逐字节契约测试覆盖半包、粘包、超大帧、错误 MAGIC、校验和错误、连接中断 |


## asyncio 长度前缀服务端与客户端 SDK

把协议帧落到真实连接上：服务端用 `asyncio.start_server` 绑定 127.0.0.1 与端口 0，每个连接先用 `readexactly(4)` 读四字节长度头，再 `readexactly(length)` 读 body，回写同样的长度前缀帧；

客户端 SDK 封装 `open_connection`、编码、读响应、`writer.close` 与 `wait_closed`，让调用方只看到字节结果。

handler 里必须捕获 `IncompleteReadError` 处理半关闭，`finally` 里关闭 writer，避免连接泄漏。

真实项目还要加 `asyncio.wait_for` 超时、`Semaphore` 限制并发连接、`MAGIC` 与版本校验、`CRC32` 检错，并把契约测试覆盖到真实 socket 上。

片段可直接运行，重点看 `readexactly` 如何把字节流还原成一条条完整帧。

```python
import asyncio, struct

async def handle(reader, writer):
    try:
        head = await reader.readexactly(4)
        length = struct.unpack('>I', head)[0]
        body = await reader.readexactly(length)
        writer.write(struct.pack('>I', len(body)) + body)
        await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    finally:
        writer.close()

async def client(port, payload):
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    writer.write(struct.pack('>I', len(payload)) + payload)
    await writer.drain()
    n = struct.unpack('>I', await reader.readexactly(4))[0]
    reply = await reader.readexactly(n)
    writer.close()
    await writer.wait_closed()
    return reply

async def main():
    server = await asyncio.start_server(handle, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    out = await client(port, b'SET a 1')
    server.close()
    await server.wait_closed()
    return out

print(asyncio.run(main()))
```

<Callout type="idea" title='落地提示' text='长度前缀加最大帧限制、显式版本号、超时与半关闭处理，并用契约测试覆盖拆包粘包' />

```bash
python -m compileall -q . && python -m pytest -q
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 TCP 粘包与长度前缀 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## WAL 记录的字节布局与 CRC32 的校验边界

把 WAL 记录设计成 total_len、crc32、op、klen、vlen、key、value 七个字段，长度放最前是为了重放时自同步：读到长度就能跳过整条记录，尾部半条记录（声明长度大于剩余字节）直接判定为崩溃截断并停止，不必扫描魔数。

`CRC32` 用 `zlib.crc32`（`IEEE` 802.3 多项式 0xEDB88320），覆盖 op 到 value 的整个 body，却刻意不覆盖 total_len 本身——长度损坏会先被剩余字节不足拦下，把 CRC 也盖在长度上反而可能让坏长度配出合法校验值。

校验和写入与重放各算一次，成本相对 fsync 可不计；换 xxHash 或 `CRC32C` 能再降几个百分点，却引入第三方依赖，标准库 `CRC32` 对几十到几百字节的记录足够。

torn write 更隐蔽：一次 append 被断电截在 512 字节扇区中间时，长度字段可能完整而 body 少一截，只有长度加 CRC 双重判定能识别。记录必须带类型字节区分 PUT 与 tombstone（DEL），重放按序应用、同一 key 最后一条胜出，删掉的键才不会在恢复后复活。

字节序统一小端，把字段位宽与判定顺序写死到字节级，恢复在任意截断位置才能给出确定结论：要么完整记录，要么停在上一条完整记录之后。

```python
import struct, zlib

META = struct.Struct('<BHI')

def encode(op, key, value):
    kb, vb = key.encode(), value.encode()
    body = META.pack(op, len(kb), len(vb)) + kb + vb
    crc = zlib.crc32(body) & 0xffffffff
    return struct.pack('<II', len(body), crc) + body

frame = encode(1, 'user:42', 'alice')
length, crc = struct.unpack('<II', frame[:8])
body = frame[8:]
print('declared_len', length)
print('actual_len', len(body))
print('crc_ok', (zlib.crc32(body) & 0xffffffff) == crc)
tampered = bytearray(frame)
tampered[9] ^= 0x80
print('tamper_crc_fail', (zlib.crc32(bytes(tampered[8:])) & 0xffffffff) != crc)
partial = frame[:14]
p_len = struct.unpack('<II', partial[:8])[0]
print('partial_body_avail', len(partial) - 8)
print('truncated', p_len > len(partial) - 8)
```

<OutputBox title='扩展示例运行结果' output='declared_len 19\nactual_len 19\ncrc_ok True\ntamper_crc_fail True\npartial_body_avail 6\ntruncated True' />

<LineByLine code='import struct, zlib\n\nMETA = struct.Struct(&#39;&lt;BHI&#39;)\n\ndef encode(op, key, value):\n    kb, vb = key.encode(), value.encode()\n    body = META.pack(op, len(kb), len(vb)) + kb + vb\n    crc = zlib.crc32(body) &amp; 0xffffffff\n    return struct.pack(&#39;&lt;II&#39;, len(body), crc) + body\n\nframe = encode(1, &#39;user:42&#39;, &#39;alice&#39;)\nlength, crc = struct.unpack(&#39;&lt;II&#39;, frame[:8])\nbody = frame[8:]\nprint(&#39;declared_len&#39;, length)\nprint(&#39;actual_len&#39;, len(body))\nprint(&#39;crc_ok&#39;, (zlib.crc32(body) &amp; 0xffffffff) == crc)\ntampered = bytearray(frame)\ntampered[9] ^= 0x80\nprint(&#39;tamper_crc_fail&#39;, (zlib.crc32(bytes(tampered[8:])) &amp; 0xffffffff) != crc)\npartial = frame[:14]\np_len = struct.unpack(&#39;&lt;II&#39;, partial[:8])[0]\nprint(&#39;partial_body_avail&#39;, len(partial) - 8)\nprint(&#39;truncated&#39;, p_len &gt; len(partial) - 8)' :notes='["META 定义 op(u8)、klen(u16)、vlen(u32) 共 7 字节小端布局", "空行，只用于分隔逻辑块，不影响执行结果。", "CRC32 只覆盖 body，按 32 位无符号截断", "空行，只用于分隔逻辑块，不影响执行结果。", "返回 8 字节头（长度加 CRC）拼接 body", "声明长度 19，等于 7 加 7 加 5", "重算 CRC 与头部比对确认完整", "翻转 body 首字节一位模拟位腐坏", "截取半条记录模拟断电截断", "空行，只用于分隔逻辑块，不影响执行结果。", "声明长度大于剩余字节，判定为截断并停止重放", "这一行 `length, crc = struct.unpack(&#39;&lt;II&#39;, frame[:8])` 的作用，可对照上方输出逐项核对。", "这一行 `body = frame[8:]` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;declared_len&#39;, length)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;actual_len&#39;, len(body))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;crc_ok&#39;, (zlib.crc32(body) &amp; 0xffffffff) == c` 的作用，可对照上方输出逐项核对。", "这一行 `tampered = bytearray(frame)` 的作用，可对照上方输出逐项核对。", "这一行 `tampered[9] ^= 0x80` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;tamper_crc_fail&#39;, (zlib.crc32(bytes(tampered[` 的作用，可对照上方输出逐项核对。", "这一行 `partial = frame[:14]` 的作用，可对照上方输出逐项核对。", "这一行 `p_len = struct.unpack(&#39;&lt;II&#39;, partial[:8])[0]` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;partial_body_avail&#39;, len(partial) - 8)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;truncated&#39;, p_len &gt; len(partial) - 8)` 的作用，可对照上方输出逐项核对。"]' title='扩展示例逐行讲解' />


### 检查点压缩的崩溃窗口与 CURRENT 清单

**WAL 记录字段与崩溃判定**

| 字段 | 位宽 / 编码 | 作用 | 损坏时判定 |
| --- | --- | --- | --- |
| total_len | u32 小端 | body 字节数，重放自同步 | 大于剩余字节则尾部截断 |
| crc32 | u32，zlib.crc32(body) | 覆盖 op 到 value | 不匹配则记录作废 |
| op | u8 | 1 为 PUT、2 为 tombstone(DEL) | 未知类型则拒绝并停 |
| klen / vlen | u16 / u32 | key 与 value 长度 | 越界则按截断处理 |
| 写入顺序 | WAL 到 fsync 到内存到应答 | 崩溃一致性 | 顺序反了会丢已应答的写 |

<Quiz no='130-1' q='WAL 记录把 total_len 放在最前、CRC32 不覆盖长度字段，主要理由是？' :options='["长度用于自同步与截断判定，长度本身损坏应由剩余字节不足拦截", "CRC32 无法计算长度字段的值", "为了让记录长度总是 4 的倍数", "为了兼容大端机器"]' answer="0" explain='长度字段承担重放时的跳过与截断判定，先读长度再看剩余字节即可定位半条记录；若 CRC 覆盖长度，一个被改坏的长度可能配出合法校验，反而掩盖截断。body 的完整性由 CRC 保证，两者职责分离。' />


## 组提交、目录 fsync 与断电演练复盘

WAL 的吞吐瓶颈从来不是 append 而是 fsync。每次写都 fsync 能保证最强一致，但一次 fsync 要刷数据加元数据，单请求串行等它 QPS 会被钉死。

组提交把同一时间窗内到达的多条 append 排成队列：leader 负责一次性 write 加 fsync，follower 挂在这个完成事件上一起返回，N 条写摊薄成一次刷盘，吞吐随并发上升而单请求延迟只增加一个排队时长；

InnoDB 的 innodb_flush_log_at_trx_commit 与 RocksDB 的 group commit 都是这个结构。代价是延迟尾部长尾化，且要定义刷盘方案：always 每条都刷、everysec 由后台线程每秒刷一批、never 交给 OS。

第二个常被漏掉的点是目录 fsync：`os.replace` 改的是目录项，文件本身 fsync 只保证内容落盘，rename 的持久性还要对父目录以 `O_DIRECTORY` 打开再 fsync 一次，否则断电后新快照名可能回退。

检查点压缩按固定序：写 `snapshot.tmp`、fsync、原子 rename、更新 `CURRENT` 清单（记录快照号与起始 LSN）、fsync 目录、才截断旧 WAL。崩溃窗口逐个可判：tmp 阶段崩溃删 tmp 重来；rename 后 `CURRENT` 未更新按旧清单重放全部 WAL；

`CURRENT` 已更新但 WAL 未截断，重放跳过已覆盖的 LSN 即可，重复应用幂等。

上线前用 kill -9 做断电演练，在 WAL 追加、fsync、改内存、返回 OK 四步各注入一次崩溃。第一次暴露两个问题：开发机把刷盘方案设成 never，断电后 37 条已返回 OK 的写全丢；检查点直接覆盖写快照，压缩中途被杀留下半截文件，恢复时把它当有效快照，数据回退两天。

修复按复盘结论固化：默认方案改 everysec 并写进 ADR，快照改临时文件加 `os.replace`，`CURRENT` 原子替换且先 fsync 目录再截断 WAL，注入脚本随流水线跑。下面是最小故障注入：模拟一条记录被截断，验证恢复循环停在完整记录边界。

```python
import struct, zlib

META = struct.Struct('<BHI')

def encode(op, key, value):
    kb, vb = key.encode(), value.encode()
    body = META.pack(op, len(kb), len(vb)) + kb + vb
    return struct.pack('<II', len(body), zlib.crc32(body) & 0xffffffff) + body

log = encode(1, 'a', '1') + encode(1, 'b', '2')
cut = log[:len(encode(1, 'a', '1')) + 9]
recovered = []
pos = 0
while pos + 8 <= len(cut):
    length, crc = struct.unpack('<II', cut[pos:pos + 8])
    body = cut[pos + 8:pos + 8 + length]
    if len(body) < length or (zlib.crc32(body) & 0xffffffff) != crc:
        break
    op, klen, vlen = META.unpack(body[:7])
    recovered.append((op, body[7:7 + klen].decode()))
    pos += 8 + length
print('recovered', recovered)
print('stopped_at_complete_boundary', len(recovered) == 1)
```

<Term word='组提交（group commit）' text='把同一时间窗内多个事务的 WAL append 合并成一次 write 加 fsync：leader 执行刷盘，follower 挂在该完成事件上一起返回，N 条写摊薄成一次刷盘。吞吐随并发上升，代价是单请求多一段排队延迟，需要显式定义 always / everysec / never 刷盘方案。' />


## 练习、自测与一页纸速记

<Exercise title='基础：实现长度前缀编解码并验证粘包' task='写 encode(op,key,value) 与 decode(stream)，用 struct.pack(&#39;&gt;H&#39;, n) 作长度头，把两帧拼在一起验证能切出两条 body。' solution='import struct\ndef enc(body):\n    return struct.pack(&#39;&gt;H&#39;, len(body)) + body\ndef dec(s):\n    out = []\n    while len(s) &gt;= 2:\n        n = struct.unpack(&#39;&gt;H&#39;, s[:2])[0]\n        if len(s) &lt; 2 + n: break\n        out.append(s[2:2+n]); s = s[2+n:]\n    return out\nprint(dec(enc(b&#39;SET a 1&#39;) + enc(b&#39;GET a&#39;)))' explain='输出 [b&#39;SET a 1&#39;, b&#39;GET a&#39;]。长度头让循环能连续切出多帧；若用换行分隔，值里的换行就会把帧切错。' />

<Exercise title='进阶：给帧加 CRC32 并构造损坏用例' task='在帧尾追加 zlib.crc32(frame) 的四字节校验和，decode 时重算比对；翻转一个字节验证返回 bad checksum。' solution='import struct, zlib\ndef enc(body):\n    f = struct.pack(&#39;&gt;H&#39;, len(body)) + body\n    return f + struct.pack(&#39;&gt;I&#39;, zlib.crc32(f) &amp; 0xffffffff)\ndef dec(s):\n    n = struct.unpack(&#39;&gt;H&#39;, s[:2])[0]\n    f = s[:2+n]\n    got = struct.unpack(&#39;&gt;I&#39;, s[2+n:6+n])[0]\n    return &#39;ok&#39; if (zlib.crc32(f) &amp; 0xffffffff) == got else &#39;bad checksum&#39;\nf = bytearray(enc(b&#39;SET a 1&#39;)); print(dec(bytes(f)))\nf[-1] ^= 1; print(dec(bytes(f)))' explain='依次输出 ok 与 bad checksum。CRC32 只检错不防篡改；要防篡改需换成 HMAC 并把密钥放在服务端。' />

<Quiz no='130-2' q='关于 TCP 与消息边界，哪一项准确？' :options='["TCP 是字节流，一次 read 可能拿到半条或多条，边界要靠长度前缀自己定义", "每次 send 对应一次 recv", "换行分隔天然安全，因为值里不会有换行", "readexactly 会一次返回全部数据"]' answer="0" explain='内核按 MSS 与缓冲区任意切分，Nagle 还会合并小包；长度前缀加 readexactly 把「读多少」变成确定值，半包续读、粘包循环切分。' />

<Quiz no='130-3' q='协议帧里 MAX_FRAME 的作用与缺失后果是？' :options='["限制单帧长度，防止恶意超大请求打满内存", "提高 CRC32 校验速度", "让大端序生效", "决定版本号"]' answer="0" explain='长度字段可声明极大 body，服务端若照声明分配缓冲就会被单条请求打满内存；解析出 length 后先与 MAX_FRAME 比较再分配。' />

<Quiz no='130-4' q='关于网络序列化，哪一项准确？' :options='["pickle 反序列化会执行任意代码，禁止用于网络；JSON 与 msgpack 更安全", "pickle 跨语言且最紧凑，应优先使用", "JSON 支持裸二进制无需编码", "struct 能替代完整序列化方案"]' answer="0" explain='pickle 的 __reduce__ 可在反序列化时执行任意代码，是远程代码执行风险；JSON 跨语言可读，msgpack/Protobuf 紧凑有 schema，struct 只适合定长头。' />

<Predict no='130-5' q='把两条合法帧拼成一次 read 的字节流传给 decode，最可能返回什么？' :options='["([&#39;SET a 1&#39;, &#39;GET a&#39;], &#39;complete&#39;)", "([&#39;SET a 1&#39;], &#39;partial&#39;)", "抛 struct.error"]' answer='0' output='two in one read ([&#39;SET a 1&#39;, &#39;GET a&#39;], &#39;complete&#39;)' explain='decode 用 while 循环按长度前缀连续切帧：第一帧消费后 stream 剩下第二帧，继续切出，流被消费完返回 complete。这正是粘包场景的正确处理。' />

<FillBlank no='130-6' tpl='___ struct, zlib' :answers='["import"]' hint='回想本讲关于 TCP 粘包与长度前缀 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 TCP 字节流与长度前缀帧：消息边界要自己造 的落点。' />

<KnowledgeCard :points='["TCP 是字节流无消息边界；长度前缀 + readexactly 解决拆包粘包，半包续读、粘包循环切分", "帧 = MAGIC + VERSION + 长度头 + body + CRC32；struct 的 &gt; 是大端网络字节序，&#39;&gt;H&#39; 2 字节、&#39;&gt;I&#39; 4 字节", "必须设 MAX_FRAME 上限，解析出 length 先比较再分配缓冲，否则超大帧打满内存", "CRC32 只检错不防篡改（防篡改用 HMAC）；pickle 禁止用于网络，会执行任意代码", "asyncio.start_server 每连接一个 handle；readexactly 抛 IncompleteReadError 要捕获，finally 里 close 配 wait_closed", "契约测试逐字节覆盖半包、粘包、超大帧、错误 MAGIC、校验和错误、版本不匹配、连接中断"]' :pitfalls='["用换行分隔命令，值里含换行就失效", "不设最大帧长度，单条超大请求打满内存", "只测能跑通，不测半包与粘包", "用换行分隔却允许值里出现换行，协议立刻失效；不做长度上限还会被单条超大请求打满内存"]' summary='网络层第一道坎是消息边界：TCP 是字节流，一次 read 既可能拿到半条命令也可能拿到两条半' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| TCP 是字节流无消息边界；长度前缀 + readexactly 解决拆包粘包，半包续读、粘包循环切分 | 建立直觉 |
| 帧 = MAGIC + VERSION + 长度头 + body + CRC32；struct 的 > 是大端网络字节序，'>H' 2 字节、'>I' 4 字节 | 跑通示例 |
| 必须设 MAX_FRAME 上限，解析出 length 先比较再分配缓冲，否则超大帧打满内存 | 深入边界 |
| CRC32 只检错不防篡改（防篡改用 HMAC）；pickle 禁止用于网络，会执行任意代码 | 工程落地 |
| asyncio.start_server 每连接一个 handle；readexactly 抛 IncompleteReadError 要捕获，finally 里 close 配 wait_closed | 随堂检测 |
| 契约测试逐字节覆盖半包、粘包、超大帧、错误 MAGIC、校验和错误、版本不匹配、连接中断 | 复盘 |

1. TCP 是字节流无消息边界；长度前缀 + readexactly 解决拆包粘包，半包续读、粘包循环切分

2. 帧 = MAGIC + VERSION + 长度头 + body + CRC32；struct 的 > 是大端网络字节序，'>H' 2 字节、'>I' 4 字节

3. 必须设 MAX_FRAME 上限，解析出 length 先比较再分配缓冲，否则超大帧打满内存

[下一讲：实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制](/projects/kv-wal)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/130-kv-network.py`

```bash
python3 examples/lessons/130-kv-network.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/130-kv-network.py) · [全部示例代码索引](/examples/)
