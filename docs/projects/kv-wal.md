---
title: 第 131 讲 · 实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制
description: 让数据在崩溃后依然可恢复
---

<StageHeader stage='L12 · 工程实战' level='★★★★★' time='60 分钟' goal='让数据在崩溃后依然可恢复' prereq='第 130 讲 · 实战 09 · KV 贯穿线 ② 协议帧与网络层' />

# 第 131 讲 · 实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制

上一讲网络通了，可一次断电后，回了 OK 的几百个写重启全不见了——数据还只在内存里。第三步补的是「崩溃之后还在不在」，答案押在落笔先后：先写日志刷盘、再改内存、最后应答。

团队先试「先改内存、再异步写文件」，崩溃偏卡在两步之间；另一个极端是每次写都 fsync，吞吐从每秒几万掉到几百。我们先把 WAL 的追加写顺序与记录格式定稳，再讲重放、检查点、快照与压缩，然后把刷盘做成可配置三档，用截断尾记录的故障注入验恢复，并发靠锁分片守住。需要你熟悉前两讲的帧格式与 os.fsync；学完 KV 能回到最后一条已应答的写。单机终究有上限，多机留到最后。


## 先改内存后写 WAL，崩溃丢掉已应答的写

内存 KV 加完网络层后，一次机房断电让运维措手不及：进程里已向客户端返回 OK 的几百个写，重启后全没了，因为数据只在 dict 里。团队补了个「先改内存、再异步写文件」的方案，结果崩溃恰好发生在两者之间，已应答的写照样丢。另一个极端是每次写都 fsync，吞吐从每秒几万掉到几百，客户端大面积超时。

问题出在写入顺序与刷盘粒度没想清楚：持久化的正确性取决于先落 WAL 并刷盘、再改内存，崩溃时才能靠重放恢复，顺序反了就会丢已应答的写；而刷盘策略要在一致性与吞吐之间显式取舍。本讲用长度 + CRC32 的 WAL 记录、重放、检查点与故障注入，把崩溃一致性变成可验证的行为。

<Callout type="warn" title='先看一个真实会出错的写法' text='先改内存后写 WAL，崩溃丢已应答的写：客户端已拿到 OK 而磁盘尚无记录，重放后数据永久丢失' />


## WAL 与写入顺序：先落盘再应答

Write-Ahead Logging 的规则只有一条却极易写反：先把操作追加到只追加（append-only）日志文件并刷盘，再修改内存状态，最后才向客户端返回成功。顺序反了（先改内存后写盘），崩溃恰好发生在中间时，客户端已拿到 OK 而磁盘上没有这条记录，重放后数据永久丢失。追加写是顺序 IO，比随机更新快得多；

`f.flush()` 只把 Python 缓冲交给内核页缓存，`os.fsync(fd)` 才把页缓存真正落盘，断电场景必须两者都做（新建文件还要 fsync 目录，目录项才持久化）。

刷盘策略三档：always（每次写 fsync，最强一致、吞吐最低）、everysec（每秒批量 fsync，最多丢一秒数据）、never（交给操作系统，断电可能丢一批已应答写）；

SQLite 的 `synchronous=FULL`/NORMAL/OFF 与 Redis AOF 的 appendfsync always/everysec/no 就是同一取舍。

失效信号：恢复后丢已应答的写、吞吐随写入量骤降却查不到别的原因。

**刷盘策略对照**

| 策略 | fsync 时机 | 一致性 | 吞吐 / 崩溃损失 |
| --- | --- | --- | --- |
| always | 每次写后 fsync | 最强，已应答写不丢 | 最低，受磁盘 IOPS 限制 |
| everysec | 每秒批量 fsync | 较强 | 最多丢一秒数据 |
| never | 仅 f.flush，交给 OS | 最弱 | 断电可能丢一批已应答写 |
| SQLite 类比 | synchronous=FULL/NORMAL/OFF | 同三档语义 | 同一取舍 |
| Redis AOF | appendfsync always/everysec/no | 同三档语义 | 同一取舍 |

```python
import json, os, struct, tempfile, zlib

def encode_rec(rec):
    body = json.dumps(rec, sort_keys=True).encode()
    return struct.pack('>II', len(body), zlib.crc32(body) & 0xffffffff) + body

def append(path, rec, fsync=False):
    with open(path, 'ab') as f:
        f.write(encode_rec(rec))
        f.flush()
        if fsync:
            os.fsync(f.fileno())

def replay(path):
    state, valid, corrupt = {}, 0, 0
    data = open(path, 'rb').read()
    pos = 0
    while pos + 8 <= len(data):
        length, crc = struct.unpack('>II', data[pos:pos + 8])
        end = pos + 8 + length
        if end > len(data) or (zlib.crc32(data[pos + 8:end]) & 0xffffffff) != crc:
            corrupt += 1
            break
        rec = json.loads(data[pos + 8:end])
        if rec['op'] == 'DEL':
            state.pop(rec['key'], None)
        else:
            state[rec['key']] = rec['value']
        valid += 1
        pos = end
    return state, valid, corrupt

def checkpoint(path, snap):
    state, _, _ = replay(path)
    with open(snap, 'w', encoding='utf-8') as f:
        json.dump(state, f, sort_keys=True)
    open(path, 'wb').close()
    return sorted(state)

work = tempfile.mkdtemp()
wal = os.path.join(work, 'kv.wal')
append(wal, {'op': 'SET', 'key': 'a', 'value': '1'}, fsync=True)
append(wal, {'op': 'SET', 'key': 'b', 'value': '2'})
append(wal, {'op': 'DEL', 'key': 'a', 'value': ''})
print('replay', replay(wal))
raw = open(wal, 'rb').read()
open(wal, 'wb').write(raw[:-3])
print('crash replay', replay(wal))
snap = os.path.join(work, 'snap.json')
print('checkpoint', checkpoint(wal, snap))
print('wal empty', os.path.getsize(wal) == 0)
print('snap', json.load(open(snap, encoding='utf-8')))
```

<OutputBox title='主示例运行结果' output='replay ({&#39;b&#39;: &#39;2&#39;}, 3, 0)\ncrash replay ({&#39;a&#39;: &#39;1&#39;, &#39;b&#39;: &#39;2&#39;}, 2, 1)\ncheckpoint [&#39;a&#39;, &#39;b&#39;]\nwal empty True\nsnap {&#39;a&#39;: &#39;1&#39;, &#39;b&#39;: &#39;2&#39;}' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import json, os, struct, tempfile, zlib\n\ndef encode_rec(rec):\n    body = json.dumps(rec, sort_keys=True).encode()\n    return struct.pack(&#39;&gt;II&#39;, len(body), zlib.crc32(body) &amp; 0xffffffff) + body\n\ndef append(path, rec, fsync=False):\n    with open(path, &#39;ab&#39;) as f:\n        f.write(encode_rec(rec))\n        f.flush()\n        if fsync:\n            os.fsync(f.fileno())\n\ndef replay(path):\n    state, valid, corrupt = {}, 0, 0\n    data = open(path, &#39;rb&#39;).read()\n    pos = 0\n    while pos + 8 &lt;= len(data):\n        length, crc = struct.unpack(&#39;&gt;II&#39;, data[pos:pos + 8])\n        end = pos + 8 + length\n        if end &gt; len(data) or (zlib.crc32(data[pos + 8:end]) &amp; 0xffffffff) != crc:\n            corrupt += 1\n            break\n        rec = json.loads(data[pos + 8:end])\n        if rec[&#39;op&#39;] == &#39;DEL&#39;:\n            state.pop(rec[&#39;key&#39;], None)\n        else:\n            state[rec[&#39;key&#39;]] = rec[&#39;value&#39;]\n        valid += 1\n        pos = end\n    return state, valid, corrupt\n\ndef checkpoint(path, snap):\n    state, _, _ = replay(path)\n    with open(snap, &#39;w&#39;, encoding=&#39;utf-8&#39;) as f:\n        json.dump(state, f, sort_keys=True)\n    open(path, &#39;wb&#39;).close()\n    return sorted(state)\n\nwork = tempfile.mkdtemp()\nwal = os.path.join(work, &#39;kv.wal&#39;)\nappend(wal, {&#39;op&#39;: &#39;SET&#39;, &#39;key&#39;: &#39;a&#39;, &#39;value&#39;: &#39;1&#39;}, fsync=True)\nappend(wal, {&#39;op&#39;: &#39;SET&#39;, &#39;key&#39;: &#39;b&#39;, &#39;value&#39;: &#39;2&#39;})\nappend(wal, {&#39;op&#39;: &#39;DEL&#39;, &#39;key&#39;: &#39;a&#39;, &#39;value&#39;: &#39;&#39;})\nprint(&#39;replay&#39;, replay(wal))\nraw = open(wal, &#39;rb&#39;).read()\nopen(wal, &#39;wb&#39;).write(raw[:-3])\nprint(&#39;crash replay&#39;, replay(wal))\nsnap = os.path.join(work, &#39;snap.json&#39;)\nprint(&#39;checkpoint&#39;, checkpoint(wal, snap))\nprint(&#39;wal empty&#39;, os.path.getsize(wal) == 0)\nprint(&#39;snap&#39;, json.load(open(snap, encoding=&#39;utf-8&#39;)))' :notes='["导入 json 序列化记录、os 做 fsync、struct 定长头、tempfile 建隔离目录、zlib 做校验", "encode_rec 把一条操作编成自描述的 WAL 记录", "sort_keys=True 让字节稳定可核对", "8 字节头写长度与 CRC32，后跟 payload", "append 以二进制追加模式打开，保证顺序写", "with open(path, &#39;ab&#39;) 追加打开，避免覆盖已有日志", "写入一条完整记录", "f.flush 把 Python 缓冲交给内核页缓存", "fsync 开关由调用方的刷盘策略决定", "真正把页缓存落盘，断电才不丢", "replay 从 WAL 重建状态，返回状态、有效条数、损坏条数", "三个累加器初始化", "一次读进全部字节用于演示，生产应流式读", "从偏移 0 开始逐条切", "至少要有 8 字节头才尝试解析", "按大端读出长度与 CRC32", "算出本条记录的结束偏移", "长度越界或校验和不符就在此停止，保留此前完整记录", "损坏计数加一", "跳出循环，不继续解析可疑尾部", "校验通过才反序列化 payload", "DEL 是 tombstone，重放时要删除键", "从状态里移除，避免已删键复活", "else 分支处理 SET 记录", "SET 覆盖写入键值，天然幂等", "有效记录数加一", "推进到下一记录起点", "返回三元组，供恢复与质量报告使用", "checkpoint 把当前状态写成快照并清空 WAL，即压缩", "先重放得到最新完整状态", "以文本写快照，键序稳定", "json.dump 以 sort_keys=True 写出稳定状态", "写完后截断 WAL，后续只追加快照之后的记录", "返回快照里的键，便于核对", "建隔离工作目录，测试不污染真实数据", "组合出 WAL 文件路径", "第一条用 fsync=True 演示最强一致档", "第二条演示批量刷盘档", "DEL 也写日志，否则重放会让已删键复活", "正常重放：三条记录全有效，a 已被删除，只剩 b", "读出全部字节用于制造崩溃", "截掉最后三字节，模拟写到一半被杀", "崩溃重放：前两条完整生效，尾部半条被判损坏", "组合出快照路径", "做检查点，把当前状态固化并清空 WAL", "验证 WAL 已被截断为空", "读回快照，确认恢复源已切换到快照"]' title='第 131 讲 · 实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：顺序反了，重放恢复不回那笔写

```python
def simulate(order):
    mem, disk = {}, []
    def write(k, v):
        if order == 'memory-first':
            mem[k] = v
            return 'ack'
        disk.append((k, v))
        mem[k] = v
        return 'ack'
    ack = write('a', '1')
    return ack, dict(disk).get('a')

print('memory-first', simulate('memory-first'))
print('wal-first', simulate('wal-first'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='memory-first (&#39;ack&#39;, None)\nwal-first (&#39;ack&#39;, &#39;1&#39;)' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import json, os, struct, tempfile, zlib\n\ndef encode_rec(rec):\n    body = json.dumps(rec, sort_keys=True).encode()\n    return struct.pack(&#39;&gt;II&#39;, len(body), zlib.crc32(body) &amp; 0xffffffff) + body\n\ndef append(path, rec, fsync=False):\n    with open(path, &#39;ab&#39;) as f:\n        f.write(encode_rec(rec))\n        f.flush()\n        if fsync:\n            os.fsync(f.fileno())\n\ndef replay(path):\n    state, valid, corrupt = {}, 0, 0\n    data = open(path, &#39;rb&#39;).read()\n    pos = 0\n    while pos + 8 &lt;= len(data):\n        length, crc = struct.unpack(&#39;&gt;II&#39;, data[pos:pos + 8])\n        end = pos + 8 + length\n        if end &gt; len(data) or (zlib.crc32(data[pos + 8:end]) &amp; 0xffffffff) != crc:\n            corrupt += 1\n            break\n        rec = json.loads(data[pos + 8:end])\n        if rec[&#39;op&#39;] == &#39;DEL&#39;:\n            state.pop(rec[&#39;key&#39;], None)\n        else:\n            state[rec[&#39;key&#39;]] = rec[&#39;value&#39;]\n        valid += 1\n        pos = end\n    return state, valid, corrupt\n\ndef checkpoint(path, snap):\n    state, _, _ = replay(path)\n    with open(snap, &#39;w&#39;, encoding=&#39;utf-8&#39;) as f:\n        json.dump(state, f, sort_keys=True)\n    open(path, &#39;wb&#39;).close()\n    return sorted(state)\n\nwork = tempfile.mkdtemp()\nwal = os.path.join(work, &#39;kv.wal&#39;)\nappend(wal, {&#39;op&#39;: &#39;SET&#39;, &#39;key&#39;: &#39;a&#39;, &#39;value&#39;: &#39;1&#39;}, fsync=True)\nappend(wal, {&#39;op&#39;: &#39;SET&#39;, &#39;key&#39;: &#39;b&#39;, &#39;value&#39;: &#39;2&#39;})\nappend(wal, {&#39;op&#39;: &#39;DEL&#39;, &#39;key&#39;: &#39;a&#39;, &#39;value&#39;: &#39;&#39;})\nprint(&#39;replay&#39;, replay(wal))\nraw = open(wal, &#39;rb&#39;).read()\nopen(wal, &#39;wb&#39;).write(raw[:-3])\nprint(&#39;crash replay&#39;, replay(wal))\nsnap = os.path.join(work, &#39;snap.json&#39;)\nprint(&#39;checkpoint&#39;, checkpoint(wal, snap))\nprint(&#39;wal empty&#39;, os.path.getsize(wal) == 0)\nprint(&#39;snap&#39;, json.load(open(snap, encoding=&#39;utf-8&#39;)))", "note": "WAL 与写入顺序：先落盘再应答"}, {"label": "对照 / 进阶", "code": "def simulate(order):\n    mem, disk = {}, []\n    def write(k, v):\n        if order == &#39;memory-first&#39;:\n            mem[k] = v\n            return &#39;ack&#39;\n        disk.append((k, v))\n        mem[k] = v\n        return &#39;ack&#39;\n    ack = write(&#39;a&#39;, &#39;1&#39;)\n    return ack, dict(disk).get(&#39;a&#39;)\n\nprint(&#39;memory-first&#39;, simulate(&#39;memory-first&#39;))\nprint(&#39;wal-first&#39;, simulate(&#39;wal-first&#39;))", "note": "记录格式、重放与检查点压缩"}]' title='两种写法切换看' />


## 刷盘策略：f.flush、fsync 与断电丢一批

<Callout type="warn" title='本讲最容易踩的坑' text='先改内存后写 WAL，崩溃丢已应答的写：客户端已拿到 OK 而磁盘尚无记录，重放后数据永久丢失' />


## WAL 记录字段、重放与检查点压缩

每条 WAL 记录必须自描述且可校验：`struct.pack`('>II', length, crc) 作 8 字节头，后面跟 payload；长度让重放能按边界逐条切，`zlib.crc32` 检测半条记录与位翻转，重放遇到「长度越界」或「校验和不符」就在该处停止，保留此前所有完整记录，这正是崩溃一致性的落点。

payload 用 `json.dumps(sort_keys=True)` 让字节稳定可核对；

DEL 也要写日志（tombstone），否则重放后已删键会复活；SET 是覆盖式幂等操作，重放多次结果一致，但累加类操作不能这样设计。日志会无限增长、拖慢重启，因此要检查点：把当前状态写成快照（临时文件加 `os.replace` 原子替换，带版本号与校验和），确认落盘后再截断或删除旧 WAL，这就是压缩。

恢复顺序固定为先加载快照、再重放快照之后的 WAL。测试里应断言重放后的状态与快照字节完全一致，而不只是「能启动」。

**WAL 记录字段**

| 字段 | 字节数 | 作用 |
| --- | --- | --- |
| 长度 >I | 4 | 让重放按边界逐条切记录 |
| CRC32 >I | 4 | 检出半条记录与位翻转 |
| payload | length | json.dumps(sort_keys=True) 的操作 |
| DEL tombstone | 随 payload | 重放时删除键，防已删键复活 |
| 快照版本号 | 自定义 | 检查点压缩后的恢复起点 |

<SequenceDiagram title='第 131 讲 · 调用时序' caption='从触发到收尾，标出最可能失败的两个位置' :actors='["调用方", "核心逻辑", "外部依赖"]' :steps='[{"from": "调用方", "to": "核心逻辑", "label": "发起调用", "note": "WAL 与写入顺序：先落盘再", "kind": "call"}, {"from": "核心逻辑", "to": "核心逻辑", "label": "检查前置", "note": "记录格式、重放与检查点压缩", "kind": "self"}, {"from": "核心逻辑", "to": "外部依赖", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "外部依赖", "to": "核心逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "核心逻辑", "to": "调用方", "label": "返回或降级", "note": "清理资源", "kind": "return"}]' />


## 追加写为什么比随机更新页快

持久化的本质是把「内存中的状态变更」变成「磁盘上只追加的有序记录」：追加写是顺序 IO，比随机更新页快，且崩溃时只需从尾部截断而不必修复中间。`f.flush` 把用户态缓冲交给内核页缓存，`os.fsync` 触发文件系统把页缓存写入稳定存储，两者职责不同；断电时页缓存会丢，所以最强一致档必须调用 fsync。

重放是确定性的状态机重演：SET 覆盖幂等，DEL 是 tombstone，长度加 CRC32 让「写到一半」的尾部记录可被识别并丢弃，重放停在第一个损坏点，之前所有完整记录全部生效，这就是崩溃一致性的边界。

检查点把 `O(记录数)` 的重放代价压缩成 `O(状态大小)`：先写快照（临时文件加 `os.replace` 原子替换），确认落盘后才截断 WAL，恢复时先加载快照再重放增量。锁分片按 `hash(key)` % N 把串行写拆成 N 个并行临界区，代价是跨键事务要按固定顺序加锁防死锁。

```python
import os, struct, tempfile, inspect

p = os.path.join(tempfile.mkdtemp(), 'w')
with open(p, 'ab') as f:
    f.write(b'12345')
    f.flush()
    os.fsync(f.fileno())
s1 = os.stat(p).st_size
with open(p, 'ab') as f:
    f.write(b'678')
s2 = os.stat(p).st_size
print('sizes', s1, s2, s2 - s1)
print('header bytes', struct.calcsize('>II'))
print('fsync signature', str(inspect.signature(os.fsync)))
```

<OutputBox title='原理验证' output='sizes 5 8 3\nheader bytes 8\nfsync signature (fd)' />

<Term word='追加写与 fsync' text='Write-Ahead Logging 的规则只有一条却极易写反：先把操作追加到只追加（append-only）日志文件并刷盘，再修改内存状态，最后才向客户端返回成功。顺序反了（先改内存后写盘），崩溃恰好发生在中间时，客户端已拿到 OK 而磁盘上没有这条记录，重放后数据永久丢失。追加写是顺序 IO，比随机更新快得多；f' />

<Term word='WAL 记录格式' text='每条 WAL 记录必须自描述且可校验：struct.pack(&#39;&gt;II&#39;, length, crc) 作 8 字节头，后面跟 payload；长度让重放能按边界逐条切，zlib.crc32 检测半条记录与位翻转，重放遇到「长度越界」或「校验和不符」就在该处停止，保留此前所有完整记录，这正是崩溃一致性的落点。payloa' />


## 故障注入、崩溃一致性与锁分片

只测正常路径等于没测持久化。故障注入要在测试里模拟三类崩溃：写到一半（截断文件尾部制造半条记录）、乱序落盘、进程被 kill -9；每次恢复都应回到「最近一次完整记录 + 快照」的状态，且已应答的写不丢。截断尾部是最好用的手段：重放读到长度越界就停，前面完整记录全部生效，尾部半条被丢弃。

并发控制方面，一把大锁串行所有写，简单但吞吐受限；锁分片按 `hash(key)` % N 把键映射到 N 把独立锁，不同分片可并行写，N 常取 2 的幂，内置 hash 的字符串随机化只影响分片选择、不影响正确性；跨键事务要按固定顺序加锁防死锁。读也要考虑与写的可见性（读写锁或快照读）。

三个失效信号：恢复后丢已应答写、重放到一半卡死、WAL 无限增长让重启越来越慢。

**崩溃与恢复失败模式**

| 现象 | 根因 | 防线 |
| --- | --- | --- |
| 丢已应答的写 | 先改内存后写盘，崩溃在中间 | 先 WAL + fsync 再改内存，最后应答 |
| 重放到一半卡死 | 尾部半条记录无校验 | 长度越界或 CRC 不符即停止，保留完整前缀 |
| 已删键恢复后又出现 | DEL 没写日志 | DEL 也要追加 tombstone |
| WAL 无限增长 | 从不检查点 | 定期快照 + 原子 replace，再截断 WAL |
| 快照半截损坏 | 直接覆盖写快照 | 临时文件加 os.replace 原子替换 |

<CheckList id='P131b' title='上线前自检' :items='["能复现并解释「先改内存后写 WAL，崩溃丢已应答的写」", "能复现并解释「每次写 fsync 导致吞吐骤降，或完全不刷盘断电丢一批」", "能复现并解释「DEL 不写日志、快照直接覆盖写」", "能用一条命令验证 追加写与 fsync", "关键路径有自动化测试与失败分支"]' />


## 带 WAL、刷盘策略与锁分片的 KV 引擎

把前三讲的接口接到持久化上：KV 启动时先 _replay 从 WAL 重建状态，set 按 `hash(key)` % N 选一把分片锁，在锁内先 _append 写记录并按策略 fsync，再改内存；get 直接读内存。_rec 用长度加 CRC32 的头保证重放可校验，_replay 遇到损坏尾部即停。

这样「重新打开一个 KV 实例」就等价于一次崩溃恢复，能直接验证数据是否还在。真实项目还要加 DEL tombstone、定期快照压缩、故障注入测试（截断尾部、kill -9）、以及把刷盘策略写进配置与 ADR。片段可直接运行，重点看写入顺序与重开后的恢复。

```python
import json, os, struct, tempfile, threading, zlib

class KV:
    def __init__(self, path, fsync_policy='always', shards=4):
        self.path = path
        self.policy = fsync_policy
        self.locks = [threading.Lock() for _ in range(shards)]
        self.data = {}
        self._replay()
    def _rec(self, op, key, value):
        body = json.dumps({'op': op, 'key': key, 'value': value}, sort_keys=True).encode()
        return struct.pack('>II', len(body), zlib.crc32(body) & 0xffffffff) + body
    def _append(self, rec):
        with open(self.path, 'ab') as f:
            f.write(rec)
            f.flush()
            if self.policy == 'always':
                os.fsync(f.fileno())
    def _replay(self):
        data = open(self.path, 'rb').read() if os.path.exists(self.path) else b''
        pos = 0
        while pos + 8 <= len(data):
            n, crc = struct.unpack('>II', data[pos:pos + 8])
            end = pos + 8 + n
            if end > len(data) or (zlib.crc32(data[pos + 8:end]) & 0xffffffff) != crc:
                break
            r = json.loads(data[pos + 8:end])
            self.data[r['key']] = r['value']
            pos = end
    def set(self, key, value):
        idx = hash(key) % len(self.locks)
        with self.locks[idx]:
            self._append(self._rec('SET', key, value))
            self.data[key] = value
    def get(self, key):
        return self.data.get(key)

p = os.path.join(tempfile.mkdtemp(), 'kv.wal')
kv = KV(p)
kv.set('a', '1')
kv.set('b', '2')
print('before', kv.get('a'), kv.get('b'))
print('reopen', KV(p).get('a'), KV(p).get('b'))
print('shards', len(kv.locks), 'policy', kv.policy)
```

<Callout type="idea" title='落地提示' text='提供可配置的刷盘策略、写 checksum 与长度、定期快照压缩，并用故障注入验证恢复路径' />

```bash
python -m compileall -q . && python -m pytest -q
```

把输入换成你自己的数据，观察结果是否仍符合 **追加写与 fsync** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 先改内存后写 WAL，崩溃丢已应答的写 | 客户端已拿到 OK 而磁盘尚无记录，重放后数据永久丢失 | 严格按 WAL 追加 + fsync → 改内存 → 返回成功的顺序，把应答放在最后 |
| 每次写 fsync 导致吞吐骤降，或完全不刷盘断电丢一批 | 把一致性与吞吐当成二选一，没有显式策略 | 提供 always / everysec / never 可配置策略，按业务对丢失的容忍度选择并写进 ADR |
| DEL 不写日志、快照直接覆盖写 | 重放后已删键复活；覆盖写快照被杀会留下半截文件 | DEL 追加 tombstone；快照用临时文件加 os.replace 原子替换，恢复先快照后重放增量 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：先改内存后写 WAL，崩溃丢已应答的写", "body": "客户端已拿到 OK 而磁盘尚无记录，重放后数据永久丢失", "tip": "严格按 WAL 追加 + fsync → 改内存 → 返回成功的顺序，把应答放在最后"}, {"title": "第 2 步：每次写 fsync 导致吞吐骤降，或完全不刷", "body": "把一致性与吞吐当成二选一，没有显式策略", "tip": "提供 always / everysec / never 可配置策略，按业务对丢失的容忍度选择并写进 ADR"}, {"title": "第 3 步：DEL 不写日志、快照直接覆盖写", "body": "重放后已删键复活；覆盖写快照被杀会留下半截文件", "tip": "DEL 追加 tombstone；快照用临时文件加 os.replace 原子替换，恢复先快照后重放增量"}]' />


## 一致性哈希环的虚拟节点与有界负载变体

哈希分片的第一个坑是 `hash(key)` % N：扩到 N+1 片时约 N/(N+1) 的键要搬迁，八扩九接近九成，迁移期间双写、校验与回退压力巨大。一致性哈希把节点与键都映射到 2^32（或 2^64）环上，键顺时针落到第一个节点，新增一个节点只接管它与前驱之间的那段弧，迁移量降到约 1/(N+1)。

但裸环有两个工程问题：节点少时弧长不均会倾斜，且一个热点键压垮单节点无从缓解。前者靠虚拟节点——每个物理节点在环上放 128 到 256 个 token，用 bisect 在有序 token 列表里二分定位，分布随 vnode 数增加迅速收敛；

后者要靠有界负载一致性哈希（Mirrokni 等）：给每个节点设容量上限，顺时针找第一个未超容量的节点，牺牲少量定位跳数换掉热点溢出。

真正的搬迁比例可以直接实测：对一万个键分别跑取模与 jump consistent hash，从 4 桶扩到 5 桶，取模约迁移 80%，jump hash 约 20%（正好 1/5），这个数字比任何架构图的说服力都强。分片键的选择同样是架构决策：哈希分布均匀但没有范围局部性，按时间范围查询会扇出到全部分片；

范围分片便于扫描却要预分区并处理热点，选键前先列清主查询维度。

```python
import hashlib

MASK64 = (1 << 64) - 1

def h64(key):
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), 'little')

def jump_hash(key, buckets):
    b, j = -1, 0
    h = h64(key)
    while j < buckets:
        b = j
        h = (h * 2862933555777941757 + 3037000493) & MASK64
        j = int((b + 1) * (1 << 31) / ((h >> 33) + 1))
    return b

def mod_hash(key, buckets):
    return h64(key) % buckets

keys = ['k' + str(i) for i in range(10000)]
mod_moved = sum(mod_hash(k, 4) != mod_hash(k, 5) for k in keys)
jump_moved = sum(jump_hash(k, 4) != jump_hash(k, 5) for k in keys)
print('mod_moved', mod_moved)
print('jump_moved', jump_moved)
print('jump_ratio', round(jump_moved / len(keys), 4))
```

<OutputBox title='扩展示例运行结果' output='mod_moved 8004\njump_moved 2023\njump_ratio 0.2023' />

<LineByLine code='import hashlib\n\nMASK64 = (1 &lt;&lt; 64) - 1\n\ndef h64(key):\n    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), &#39;little&#39;)\n\ndef jump_hash(key, buckets):\n    b, j = -1, 0\n    h = h64(key)\n    while j &lt; buckets:\n        b = j\n        h = (h * 2862933555777941757 + 3037000493) &amp; MASK64\n        j = int((b + 1) * (1 &lt;&lt; 31) / ((h &gt;&gt; 33) + 1))\n    return b\n\ndef mod_hash(key, buckets):\n    return h64(key) % buckets\n\nkeys = [&#39;k&#39; + str(i) for i in range(10000)]\nmod_moved = sum(mod_hash(k, 4) != mod_hash(k, 5) for k in keys)\njump_moved = sum(jump_hash(k, 4) != jump_hash(k, 5) for k in keys)\nprint(&#39;mod_moved&#39;, mod_moved)\nprint(&#39;jump_moved&#39;, jump_moved)\nprint(&#39;jump_ratio&#39;, round(jump_moved / len(keys), 4))' :notes='["用 blake2b 生成稳定 64 位哈希，掩码模拟 uint64_t 回绕", "jump consistent hash 是 Google 的纯算术分桶算法", "线性同余扰动后按高 31 位算下一个跳跃点", "对照组：朴素取模分桶", "构造一万个键，统计 4 扩 5 的搬迁数", "取模几乎全量搬迁，约八成", "jump hash 比例 0.2023，贴近理论值 1/(N+1)", "f.flush 交内核页缓存，os.fsync 才落盘；策略 always / everysec / never 对应 SQLite synchronous 与 Redis appendfsync 三档", "记录 = 长度 &gt;I + CRC32 &gt;I + payload；重放遇长度越界或校验不符即停，保留完整前缀", "DEL 也要写 tombstone，否则重放后已删键复活；SET 覆盖天然幂等", "检查点 = 快照（临时文件 + os.replace 原子替换）+ 截断 WAL；恢复先快照后增量重放", "故障注入截断尾部、kill -9 验证恢复；锁分片用 hash(key) % N 并行写，跨键事务按固定顺序加锁防死锁", "WAL 顺序：追加 + fsync → 改内存 → 返回成功；顺序反了会丢已应答的写", "f.flush 交内核页缓存，os.fsync 才落盘；策略 always / everysec / never 对应 SQLite synchronous 与 Redis appendfsync 三档", "记录 = 长度 &gt;I + CRC32 &gt;I + payload；重放遇长度越界或校验不符即停，保留完整前缀", "DEL 也要写 tombstone，否则重放后已删键复活；SET 覆盖天然幂等", "检查点 = 快照（临时文件 + os.replace 原子替换）+ 截断 WAL；恢复先快照后增量重放", "故障注入截断尾部、kill -9 验证恢复；锁分片用 hash(key) % N 并行写，跨键事务按固定顺序加锁防死锁", "WAL 顺序：追加 + fsync → 改内存 → 返回成功；顺序反了会丢已应答的写", "f.flush 交内核页缓存，os.fsync 才落盘；策略 always / everysec / never 对应 SQLite synchronous 与 Redis appendfsync 三档"]' title='扩展示例逐行讲解' />


## jump consistent hash：不建环也能只迁移 1/(N+1)

**分片与复制的数据结构对照**

| 机制 | 数据结构 | 扩容迁移量 | 适用与代价 |
| --- | --- | --- | --- |
| hash(key) % N | 取模 | 约 N/(N+1) | 简单，扩缩容几乎全量搬迁 |
| 一致性哈希 + vnode | 有序 token 环加 bisect | 约 1/(N+1) | 128 到 256 vnode 每节点，内存换均匀 |
| 有界负载变体 | 容量计数加顺延探测 | 随容量浮动 | 压住热点，定位多几次跳 |
| jump consistent hash | 无环，纯算术 | 恰好约 1/(N+1) | 桶必须连续编号，不能带权重 |
| fencing token | 单调递增 epoch | 不搬迁 | 阻止旧主脑裂后继续写 |

<Quiz no='131-X' q='把 4 个桶的一致性哈希扩到 5 桶，jump consistent hash 的键迁移比例最接近？' :options='["约 1/5（20%）", "约 4/5（80%）", "约 1/2（50%）", "全部键都不动"]' answer="0" explain='jump hash 保证只有落到新桶 4 的键需要移动，其份额约 1/(N+1)=1/5；而 hash(key)%N 从 4 扩到 5 会让约 4/5 的键换桶，实测一万个键分别为 2023 与 8004。' />


## 副本放置、Merkle 反熵与 fencing token 选主

副本不能和分片混为一谈：分片解决容量，副本解决可用性。`N=3`、`W=2`、`R=2` 时 R+W>N，读集合与写集合必有交集，能读到最新一次成功写；

但 `W=2` 意味着应答后仍有一个副本落后，故障转移时若选中的新主恰好是落后副本，就可能丢数据，所以选主要带 epoch / fencing token（单调递增的任期号），存储层拒绝小于当前 epoch 的旧主写入，堵住脑裂后的双写。副本放置要跨机架或可用区，避免一次交换机故障同时打掉 N 个副本。

落后副本的收敛靠两条路径：读修复（读时对比多个副本版本，把旧的补写）与反熵（后台用 Merkle 树逐层比对，只传哈希不一致的分支，`O(log n)` 定位差异而不是全量拉）。

冲突判定不能只用时间戳：时钟回拨会让后写被判成旧值，要用向量时钟或版本向量记录 (node, counter) 的偏序，无法定序时交给 LWW 寄存器或业务侧 CRDT 合并。

扩容的工程代价集中在数据搬运：先双写到新旧分片、从 WAL 或 binlog 追平增量、用 Merkle 校验一致，再在一个 fencing 边界切路由，全程限速并可回滚。

一次从 4 片扩到 5 片，团队用 `hash(key)`%N 且没有限速，扩容脚本一启动就把缓存打穿：约八成键换片，回源流量瞬间涨了六倍，数据库 CPU 打满，双写队列积压到告警。更糟的是迁移中途一个节点重启，路由表已切到新片却还有旧片没追平，读到了空值。

复盘把扩容拆成可回滚的几段：改用一致性哈希加虚拟节点把迁移量压到约 1/5；迁移限速到集群 QPS 的 5%，按 token 区间灰度切流；双写期间用 WAL 增量追平并以 Merkle 树逐区间校验，校验不过就退回旧路由；每个阶段带 fencing epoch，旧主重启后凭过期 epoch 被拒写。

下面是复盘用的守卫脚本：构造带 vnode 的环并演示 epoch 拒绝旧主。

```python
import hashlib

def h64(key):
    return int.from_bytes(hashlib.blake2b(key.encode(), digest_size=8).digest(), 'little')

class Guard:
    def __init__(self):
        self.epoch = 0
    def write(self, epoch):
        if epoch < self.epoch:
            return 'rejected-stale-epoch'
        self.epoch = epoch
        return 'ok'

tokens = sorted((h64('node' + str(n) + '-' + str(v)) % (1 << 32), n)
                for n in range(4) for v in range(64))
print('ring_tokens', len(tokens))
g = Guard()
print('accept_new', g.write(7))
print('reject_old', g.write(3))
```

<ConceptDiagram type='flow4' title='第 131 讲 · 扩展图解' labels='分片键选择|vnode 环 bisect 定位|双写追平 Merkle 校验|fencing epoch 切流' caption='扩容四段：先定键、再定位、追平校验、最后凭 epoch 原子切路由，每段可限速可回滚' />


## 练习、自测与速记

<Exercise title='基础：对比写入顺序对崩溃恢复的影响' task='写两个 write 函数：一个先改内存、一个先写 WAL，都返回 ack；模拟崩溃后只剩磁盘，打印各自能否找回写入值。' solution='def sim(order):\n    mem, disk = {}, []\n    def w(k,v):\n        if order==&#39;mem&#39;: mem[k]=v\n        else: disk.append((k,v)); mem[k]=v\n        return &#39;ack&#39;\n    return w(&#39;a&#39;,&#39;1&#39;), dict(disk).get(&#39;a&#39;)\nprint(&#39;mem&#39;, sim(&#39;mem&#39;))\nprint(&#39;wal&#39;, sim(&#39;wal&#39;))' explain='输出 mem (&#39;ack&#39;, None) 与 wal (&#39;ack&#39;, &#39;1&#39;)。先改内存后写盘时，已应答的写在崩溃后无处可寻；WAL 优先才能靠重放恢复。' />

<Exercise title='进阶：给 WAL 记录加长度与 CRC32 并注入截断' task='写 encode_rec 与 replay，追加三条记录后截掉文件尾部三字节，打印重放的状态、有效条数与损坏条数。' solution='import struct, zlib, json\ndef enc(r):\n    b=json.dumps(r,sort_keys=True).encode()\n    return struct.pack(&#39;&gt;II&#39;,len(b),zlib.crc32(b)&amp;0xffffffff)+b\ndef replay(d):\n    st,v,c,pos={},0,0,0\n    while pos+8&lt;=len(d):\n        n,crc=struct.unpack(&#39;&gt;II&#39;,d[pos:pos+8]); end=pos+8+n\n        if end&gt;len(d) or (zlib.crc32(d[pos+8:end])&amp;0xffffffff)!=crc: c+=1; break\n        r=json.loads(d[pos+8:end]); st[r[&#39;k&#39;]]=r[&#39;v&#39;]; v+=1; pos=end\n    return st,v,c\nd=enc({&#39;k&#39;:&#39;a&#39;,&#39;v&#39;:&#39;1&#39;})+enc({&#39;k&#39;:&#39;b&#39;,&#39;v&#39;:&#39;2&#39;})\nprint(replay(d))\nprint(replay(d[:-3]))' explain='完整流返回 ({&#39;a&#39;: &#39;1&#39;, &#39;b&#39;: &#39;2&#39;}, 2, 0)，截断后返回 ({&#39;a&#39;: &#39;1&#39;}, 1, 1)。长度加 CRC32 让半条记录被识别并丢弃，之前完整记录全部生效。' />

<Quiz no='131-1' q='关于 WAL 写入顺序，哪一项准确？' :options='["先追加并 fsync WAL、再改内存、最后返回成功", "先改内存再写 WAL，减少客户端等待", "先返回成功再异步写盘", "顺序无关，重放总能恢复"]' answer="0" explain='顺序反了会让「已应答但磁盘无记录」的写在崩溃后永久丢失；把应答放在 WAL 落盘之后，才保证任何 ACK 过的写都能重放回来。' />

<Quiz no='131-2' q='关于 f.flush 与 os.fsync，准确的说法是？' :options='["f.flush 只交到内核页缓存，os.fsync 才落盘；断电场景两者都要", "两者等价", "os.fsync 会清空 Python 缓冲", "f.flush 已经足够防断电"]' answer="0" explain='f.flush 处理的是用户态 BufferedWriter，断电时页缓存仍会丢；os.fsync(fd) 触发文件系统把数据写入稳定存储，最强一致档必须调用它。' />

<Quiz no='131-3' q='重放遇到尾部半条记录（长度越界）时应如何处理？' :options='["在该处停止，保留此前所有完整记录，把尾部判为损坏", "跳过继续解析后面的字节", "整个恢复失败并清空状态", "用零填充补齐记录"]' answer="0" explain='长度加 CRC32 的目的就是识别「写到一半」的尾部；停在第一个损坏点，之前完整记录全部生效，这正是崩溃一致性的边界。' />

<KnowledgeCard :points='["WAL 顺序：追加 + fsync → 改内存 → 返回成功；顺序反了会丢已应答的写", "f.flush 交内核页缓存，os.fsync 才落盘；策略 always / everysec / never 对应 SQLite synchronous 与 Redis appendfsync 三档", "记录 = 长度 &gt;I + CRC32 &gt;I + payload；重放遇长度越界或校验不符即停，保留完整前缀", "DEL 也要写 tombstone，否则重放后已删键复活；SET 覆盖天然幂等", "检查点 = 快照（临时文件 + os.replace 原子替换）+ 截断 WAL；恢复先快照后增量重放", "故障注入截断尾部、kill -9 验证恢复；锁分片用 hash(key) % N 并行写，跨键事务按固定顺序加锁防死锁"]' :pitfalls='["先改内存后写 WAL，崩溃丢已应答的写", "每次写 fsync 导致吞吐骤降，或完全不刷盘断电丢一批", "DEL 不写日志、快照直接覆盖写", "每次写都 fsync 保证最强一致但吞吐很低，完全不刷盘又可能在断电时丢一批已返回成功的请求"]' summary='持久化的正确性取决于写入顺序：先落 WAL 并刷盘，再改内存，崩溃时才能靠重放恢复；顺序反了就会丢已应答的写' />

1. WAL 顺序：追加 + fsync → 改内存 → 返回成功；顺序反了会丢已应答的写

2. f.flush 交内核页缓存，os.fsync 才落盘；策略 always / everysec / never 对应 SQLite synchronous 与 Redis appendfsync 三档

3. 记录 = 长度 >I + CRC32 >I + payload；重放遇长度越界或校验不符即停，保留完整前缀

[下一讲：实战 11 · 分片复制、AI 网关与能力收束](/projects/kv-distributed)

<Predict no='131-P' q='先改内存后写 WAL，崩溃后只剩磁盘，最可能的结果是？' :options='["已应答的写丢失（返回值 ack，磁盘查不到）", "写被完整保留", "恢复时抛异常"]' answer='0' output='memory-first (&#39;ack&#39;, None)' explain='客户端已拿到 ack，但磁盘上没有这条记录，重放无从恢复；wal-first 才会把 (键, 值) 留在磁盘上，输出 (&#39;ack&#39;, &#39;1&#39;)。' />

<FillBlank no='131-F' tpl='___ json, os, struct, tempfile, zlib' :answers='["import"]' hint='回想本讲关于 追加写与 fsync 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 WAL 与写入顺序：先落盘再应答 的落点。' />
