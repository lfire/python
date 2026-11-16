---
title: 第 126 讲 · 实战 05 · 短链与图片服务
description: 把服务端综合项目做成可压测的产品
---

<StageHeader stage='L12 · 工程实战' level='★★★☆☆' time='50 分钟' goal='把服务端综合项目做成可压测的产品' prereq='第 125 讲 · 实战 04 · Selenium 表单自动化与定时任务' />

# 第 126 讲 · 实战 05 · 短链与图片服务

上一讲操心「把一次操作做稳」；这一讲换成「同一份数据被很多人反复来取」，也就是读多写少的服务。把项目做成可压测的产品之后，重点落在缓存命中率与大对象该放在哪。

短链用了永久重定向，运营改了落地页，老短码仍指向旧地址，浏览器和 CDN 还缓存着旧映射；图片把二进制塞进关系库，两个月后备份翻十倍、列表查询从二十毫秒涨到几百毫秒。我们先用发号与 `Base62` 把短码做成定长，再分清 `301` 与 `302` 的缓存语义、加 LRU 缓存与防刷，最后做图片上传、`ETag` 与预签名直传，用压测报出 QPS。需要你熟悉 `HTTP` 状态码与字典哈希；学完能给这类服务压出瓶颈数字。


## 读多写少的服务，优化重点不在框架

一个短链服务上线后用 `301` 永久重定向，运营改了活动落地页却发现老短码仍指向旧地址——浏览器与 CDN 把 `301` 缓存了几个月，改数据库根本不生效。

另一边图片功能把二进制塞进 MySQL，两个月后备份体积翻了十倍、列表查询因为要扫大字段从 20 毫秒涨到 800 毫秒；上传又只信客户端传来的 `Content-Type`，一个改了后缀的 `HTML` 被当图片直出，成了存储型风险。

朴素解法「随机码 + `301` + 图片入库」失败在三点：随机码要查重带来写放大、`301` 的可缓存语义与短链需要随时改目标相冲突、大对象进关系库把备份和查询一起拖垮。读多写少的服务，优化重点从来不是框架，而是缓存命中率、重定向路径长度与静态资源的存放位置。

这一讲用标准库实现 `Base62` 发号、LRU 缓存、`ETag` 与 `HMAC` 预签名，并给出可压测的容量口径。

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段十二 · 工程实战 |
| 前置 | 第 125 讲 · 实战 04 · Selenium 表单自动化与定时任务 |
| 难度 / 建议时长 | ★★★☆☆ · 50 分钟 |
| 本讲新增 | 发号与 Base62、301 / 302 语义、缓存与防刷 |
| 一句话目标 | 把服务端综合项目做成可压测的产品 |
| 为下一讲铺垫 | 实战 06 · 日志 ETL 与 CSV / SQL 查询工具 |

<Callout type="tip" title='核心心智模型' text='短码来自一个单调递增的发号器：数据库自增主键、Redis 的 `INCR` 或 Snowflake（时间戳 + 机器号 + 序列）。拿到整数 id 后用 `Base62` 压成短码，字符集固定为 0-9、A-Z、a-z 共 62 个 URL 安全字符；码长约等于…' />


## 发号与 Base62：为什么不用 UUID 或内容哈希

短码来自一个单调递增的发号器：数据库自增主键、Redis 的 `INCR` 或 Snowflake（时间戳 + 机器号 + 序列）。

拿到整数 id 后用 `Base62` 压成短码，字符集固定为 0-9、A-Z、a-z 共 62 个 URL 安全字符；码长约等于 `floor(log_62(n)) + 1`，62 的 3 次方是 `238328`、6 次方约 `5.68×10^10`，因此十亿量级 id 只需要 6 位。

不能用 `md5(url)` 当码：同一个 URL 重复、无法自定义、32 位十六进制太长，且哈希碰撞要靠查重兜底；也不能用随机码加唯一索引冲突重试，写放大随冲突率上升。发号器必须持久化且单调，进程重启不能回退，否则会撞出重复短码；若不想暴露递增规律，可对 id 做一次可逆置换或异或掩码。

字符集顺序一旦上线就不能改，否则历史短码全部解码错误；大小写混合虽省字符但要求路由层大小写敏感，需要人工输入时可换 Crockford Base32 去掉易混的 0/O、1/l/I。失效信号：短码长度突然变长（发号器溢出或回退）、不同 id 解出同一码、URL 里出现需要百分号编码的字符。

```python
import hashlib
from collections import OrderedDict
from http import HTTPStatus

ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

def b62(n):
    if n == 0:
        return '0'
    out = []
    while n:
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return ''.join(reversed(out))

def unb62(s):
    n = 0
    for ch in s:
        n = n * 62 + ALPHABET.index(ch)
    return n

class LRU:
    def __init__(self, cap):
        self.cap = cap
        self.d = OrderedDict()
        self.hit = 0
        self.miss = 0
    def get(self, k):
        if k in self.d:
            self.hit += 1
            self.d.move_to_end(k)
            return self.d[k]
        self.miss += 1
        return None
    def put(self, k, v):
        self.d[k] = v
        self.d.move_to_end(k)
        if len(self.d) > self.cap:
            self.d.popitem(last=False)

print('codes', [b62(i) for i in (0, 61, 62, 3844)])
print('roundtrip', all(unb62(b62(i)) == i for i in range(1000)))
cache = LRU(cap=2)
for k in ('a', 'b', 'a', 'c', 'b'):
    if cache.get(k) is None:
        cache.put(k, 'url-' + k)
print('lru', cache.hit, cache.miss, list(cache.d))
etag = hashlib.md5(b'img-bytes').hexdigest()[:8]
print('etag', etag)
print('status', HTTPStatus.MOVED_PERMANENTLY.value, HTTPStatus.MOVED_PERMANENTLY.phrase,
      HTTPStatus.FOUND.value, HTTPStatus.FOUND.phrase)
```

<OutputBox title='主示例运行结果' output='codes [&#39;0&#39;, &#39;z&#39;, &#39;10&#39;, &#39;100&#39;]\nroundtrip True\nlru 1 4 [&#39;c&#39;, &#39;b&#39;]\netag 7f016ee1\nstatus 301 Moved Permanently 302 Found' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import hashlib\nfrom collections import OrderedDict\nfrom http import HTTPStatus\n\nALPHABET = &#39;0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz&#39;\n\ndef b62(n):\n    if n == 0:\n        return &#39;0&#39;\n    out = []\n    while n:\n        n, r = divmod(n, 62)\n        out.append(ALPHABET[r])\n    return &#39;&#39;.join(reversed(out))\n\ndef unb62(s):\n    n = 0\n    for ch in s:\n        n = n * 62 + ALPHABET.index(ch)\n    return n\n\nclass LRU:\n    def __init__(self, cap):\n        self.cap = cap\n        self.d = OrderedDict()\n        self.hit = 0\n        self.miss = 0\n    def get(self, k):\n        if k in self.d:\n            self.hit += 1\n            self.d.move_to_end(k)\n            return self.d[k]\n        self.miss += 1\n        return None\n    def put(self, k, v):\n        self.d[k] = v\n        self.d.move_to_end(k)\n        if len(self.d) &gt; self.cap:\n            self.d.popitem(last=False)\n\nprint(&#39;codes&#39;, [b62(i) for i in (0, 61, 62, 3844)])\nprint(&#39;roundtrip&#39;, all(unb62(b62(i)) == i for i in range(1000)))\ncache = LRU(cap=2)\nfor k in (&#39;a&#39;, &#39;b&#39;, &#39;a&#39;, &#39;c&#39;, &#39;b&#39;):\n    if cache.get(k) is None:\n        cache.put(k, &#39;url-&#39; + k)\nprint(&#39;lru&#39;, cache.hit, cache.miss, list(cache.d))\netag = hashlib.md5(b&#39;img-bytes&#39;).hexdigest()[:8]\nprint(&#39;etag&#39;, etag)\nprint(&#39;status&#39;, HTTPStatus.MOVED_PERMANENTLY.value, HTTPStatus.MOVED_PERMANENTLY.phrase,\n      HTTPStatus.FOUND.value, HTTPStatus.FOUND.phrase)' :notes='["导入 hashlib，用于内容哈希生成 ETag", "OrderedDict 是手写 LRU 的基础结构，兼具哈希与顺序", "HTTPStatus 提供状态码的标准 phrase，避免自己记错 302 名称", "空行，只用于分隔逻辑块，不影响执行结果。", "Base62 字符集：10 个数字 + 26 大写 + 26 小写，共 62 个 URL 安全字符", "空行，只用于分隔逻辑块，不影响执行结果。", "编码函数把整数 id 转成短码", "0 单独处理，避免 while 循环产出空串", "返回字符集中的第一个字符", "用列表收集每一位的字符", "循环取 62 进制的每一位", "divmod 同时得到商与余数，比 % 与 // 分两次算更省", "按余数从字符集取字符", "高位在低索引，反转后拼成最终短码", "空行，只用于分隔逻辑块，不影响执行结果。", "解码函数验证编码可逆，是发号器正确性的最低要求", "累加器从 0 开始", "逐字符按 62 进制还原", "index 返回字符在字符集中的位置，字符集顺序必须固定", "返回还原后的整数 id", "空行，只用于分隔逻辑块，不影响执行结果。", "LRU 缓存：OrderedDict 加命中/未命中计数", "构造时记下容量上限", "保存容量", "用 OrderedDict 维护访问顺序，末尾是最近使用", "命中计数初始化为 0", "未命中计数初始化为 0", "get 是读路径，命中要顺带更新顺序", "键存在即命中", "命中数加一，用于算命中率", "move_to_end 把该键移到末尾，标记为最近使用", "返回缓存值，不回源", "未命中数加一", "返回 None，让调用方回源并回填", "put 是写路径，同样维护顺序与容量", "写入或覆盖键值", "新写入的键也要移到末尾", "超过容量时触发淘汰", "popitem(last=False) 淘汰最久未用的头部，O(1)", "空行，只用于分隔逻辑块，不影响执行结果。", "打印 0、61、62、3844 的短码，验证进位边界", "对前一千个 id 做编解码往返，全部一致才算可信", "容量为 2 的缓存，序列里故意重复访问 a 制造一次命中", "按序访问 a b a c b，观察淘汰行为", "未命中才回填，模拟回源加载", "回填时键值为拼接出来的 URL", "打印命中数、未命中数与最终键顺序", "用内容哈希的前 8 位十六进制作演示用 ETag", "打印 ETag，相同内容必然得到相同值", "打印 301 与 302 的标准 phrase，注意 302 是 Found", "续行给出 302 的值与 phrase，与 301 并列对照"]' title='第 126 讲 · 实战 05 · 短链与图片服务' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：自增 seq 编解码与内容哈希的输出

```python
import hashlib, hmac

SECRET = b'server-key'

def sign(resource, expires):
    payload = resource + ':' + str(expires)
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16]

def verify(resource, expires, sig, now):
    if now > expires:
        return 'expired'
    return 'ok' if hmac.compare_digest(sign(resource, expires), sig) else 'bad signature'

s = sign('img/42.png', expires=1000)
print('signed', s)
print('valid', verify('img/42.png', 1000, s, now=500))
print('tampered', verify('img/43.png', 1000, s, now=500))
print('expired', verify('img/42.png', 1000, s, now=2000))
print('content-type gate', 'image/png' in {'image/png', 'image/jpeg'})
```

<OutputBox title='对照写法：先自己猜，再点开' output='signed e971917f0dc31851\nvalid ok\ntampered bad signature\nexpired expired\ncontent-type gate True' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import hashlib\nfrom collections import OrderedDict\nfrom http import HTTPStatus\n\nALPHABET = &#39;0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz&#39;\n\ndef b62(n):\n    if n == 0:\n        return &#39;0&#39;\n    out = []\n    while n:\n        n, r = divmod(n, 62)\n        out.append(ALPHABET[r])\n    return &#39;&#39;.join(reversed(out))\n\ndef unb62(s):\n    n = 0\n    for ch in s:\n        n = n * 62 + ALPHABET.index(ch)\n    return n\n\nclass LRU:\n    def __init__(self, cap):\n        self.cap = cap\n        self.d = OrderedDict()\n        self.hit = 0\n        self.miss = 0\n    def get(self, k):\n        if k in self.d:\n            self.hit += 1\n            self.d.move_to_end(k)\n            return self.d[k]\n        self.miss += 1\n        return None\n    def put(self, k, v):\n        self.d[k] = v\n        self.d.move_to_end(k)\n        if len(self.d) &gt; self.cap:\n            self.d.popitem(last=False)\n\nprint(&#39;codes&#39;, [b62(i) for i in (0, 61, 62, 3844)])\nprint(&#39;roundtrip&#39;, all(unb62(b62(i)) == i for i in range(1000)))\ncache = LRU(cap=2)\nfor k in (&#39;a&#39;, &#39;b&#39;, &#39;a&#39;, &#39;c&#39;, &#39;b&#39;):\n    if cache.get(k) is None:\n        cache.put(k, &#39;url-&#39; + k)\nprint(&#39;lru&#39;, cache.hit, cache.miss, list(cache.d))\netag = hashlib.md5(b&#39;img-bytes&#39;).hexdigest()[:8]\nprint(&#39;etag&#39;, etag)\nprint(&#39;status&#39;, HTTPStatus.MOVED_PERMANENTLY.value, HTTPStatus.MOVED_PERMANENTLY.phrase,\n      HTTPStatus.FOUND.value, HTTPStatus.FOUND.phrase)", "note": "发号与 Base62：为什么不用 UUID 或内容哈希"}, {"label": "对照 / 进阶", "code": "import hashlib, hmac\n\nSECRET = b&#39;server-key&#39;\n\ndef sign(resource, expires):\n    payload = resource + &#39;:&#39; + str(expires)\n    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()[:16]\n\ndef verify(resource, expires, sig, now):\n    if now &gt; expires:\n        return &#39;expired&#39;\n    return &#39;ok&#39; if hmac.compare_digest(sign(resource, expires), sig) else &#39;bad signature&#39;\n\ns = sign(&#39;img/42.png&#39;, expires=1000)\nprint(&#39;signed&#39;, s)\nprint(&#39;valid&#39;, verify(&#39;img/42.png&#39;, 1000, s, now=500))\nprint(&#39;tampered&#39;, verify(&#39;img/43.png&#39;, 1000, s, now=500))\nprint(&#39;expired&#39;, verify(&#39;img/42.png&#39;, 1000, s, now=2000))\nprint(&#39;content-type gate&#39;, &#39;image/png&#39; in {&#39;image/png&#39;, &#39;image/jpeg&#39;})", "note": "301 / 302 语义、LRU 缓存与防刷"}]' title='两种写法对照' note='差异集中在 发号与 Base62；先看输出，再找背后的规则。' />


## Base62 的码长与容量：六位为什么够覆盖 568 亿

`Base62` 是 62 进制的位置记数法，码长 `floor(log_62(n)) + 1` 由信息密度决定：一个字符携带 `log2(62)≈5.95` 比特，6 位即可覆盖约 568 亿个 id，这正是短码能短的原因；编码用 `divmod` 逐位取余、解码按权重累加，二者互逆的前提是字符集顺序固定且不含重复字符。

`OrderedDict` 内部是哈希表加一条双向链表，`move_to_end` 改链表指针、`popitem(last=False)` 摘头节点，均为 `O(1)`，因此 LRU 的读写都是常数时间；回源压力与未命中率线性相关，命中率从 0.9 到 0.99 会让回源 QPS 降为原来的十分之一。

`HTTP` 缓存语义由响应头决定：`301` 未带禁用缓存的头即可被长期缓存，`302` 需显式 `Cache-Control` 才会缓存；`ETag` 配合 `If-None-Match` 用内容哈希做条件请求，命中返回 `304` 省掉正文传输。

预签名 URL 把信任交给 `HMAC`：服务端只签发带过期时间的签名，客户端直传对象存储，校验用 `compare_digest` 避免时序侧信道。容量上界由并发除以平均延迟给出，监控命中率与回源率才能定位瓶颈是 CPU、内存、带宽还是数据库。

**重定向状态码语义对照**

| 状态码 | HTTPStatus phrase | 缓存行为 | 方法/body | 短链适用性 |
| --- | --- | --- | --- | --- |
| 301 | Moved Permanently | 浏览器与 CDN 强缓存 | 常被改为 GET | 仅用于永不变更的映射 |
| 302 | Found | 默认不缓存，除非显式 Cache-Control | 常被改为 GET | 短链默认，便于统计与改目标 |
| 307 | Temporary Redirect | 默认不缓存 | 保留方法与 body | 重定向 POST 且不改方法 |
| 308 | Permanent Redirect | 可缓存 | 保留方法与 body | 永久且需保留方法的场景 |

```python
import math

ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
def b62(n):
    if n == 0:
        return '0'
    s = ''
    while n:
        n, r = divmod(n, 62)
        s = ALPHABET[r] + s
    return s
for n in (1, 61, 62, 3843, 3844, 238327):
    print(n, b62(n), len(b62(n)))
print('base', len(ALPHABET), 'log62(1e9)', round(math.log(1e9, 62), 2))
```

<OutputBox title='原理验证' output='1 1 1\n61 z 1\n62 10 2\n3843 zz 2\n3844 100 3\n238327 zzz 3\nbase 62 log62(1e9) 5.02' />


## 重定向 301 与 302：运营改目标后老链接为什么不生效

`http.HTTPStatus` 里 `301` 的 phrase 是 Moved Permanently、`302` 是 Found（不是 Moved Temporarily），这正好点出关键差别：`301` 会被浏览器与 CDN 强缓存，短链一旦发出就无法靠改库撤回，只适合永不变更的映射；`302` 默认不缓存（除非响应显式带 `Cache-Control` 或 `Expires`），每次回源便于统计点击与改目标，是短链默认选择。

`307` Temporary Redirect 与 `308` Permanent Redirect 进一步要求保留原请求方法与 body，重定向 `POST` 时不会像 `301`/`302` 那样被改成 GET。

读多写少的核心指标是缓存命中率：用 `collections.OrderedDict` 实现 LRU，命中时 `move_to_end` 把键移到末尾、超容量时 `popitem(last=False)` 淘汰最久未用，两个操作都是 `O(1)`；回源 QPS 约等于总 QPS 乘以未命中率，命中率从 90% 提到 99%、未命中率从 10% 降到 1%，能让数据库压力降一个数量级。

缓存穿透（不存在的短码反复回源）用空值缓存或布隆过滤挡住；热点键在活动前预热；防刷按 IP 与短码做令牌桶或滑动窗口限流，超限返回 `429` Too Many Requests。

**Base62 码长与容量**

| id 范围 | 码长 | 可表示数量 | 验算 |
| --- | --- | --- | --- |
| 0 到 61 | 1 位 | 62 | 62 的 1 次方 |
| 62 到 3843 | 2 位 | 3844 | 62 的 2 次方 |
| 3844 到 238327 | 3 位 | 238328 | 62 的 3 次方 |
| 十亿量级 | 约 6 位 | 约 5.68×10^10 | 62 的 6 次方，math.log(1e9,62)≈5.02 |


## LRU 缓存、热点码预热与入口防刷

<ConceptDiagram type='flow4' title='第 126 讲 · 发号与 Base62：为什么不用 UUID 或内容哈希' labels='发号与 Base62：为什么不用 UUID…|301 / 302 语义、LRU 缓存与防刷|图片服务：ETag、预签名直传与容量评估|监控与容量' caption='把服务端综合项目做成可压测的产品' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

<Callout type="warn" title='本讲最容易踩的坑' text='短链用 301，运营改目标后老链接不生效：301 是永久重定向，浏览器与 CDN 会强缓存，改库不影响已缓存的映射' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：短链用 301，运营改目标后老链接不生效", "body": "301 是永久重定向，浏览器与 CDN 会强缓存，改库不影响已缓存的映射", "tip": "默认返回 302 Found；只有确认永不变更的映射才用 301，且提前声明缓存头策略"}, {"title": "第 2 步：把图片二进制存进 MySQL", "body": "大字段让备份膨胀、缓冲池命中率下降、列表查询变慢，且对象存储的成本与带宽优势全丢", "tip": "DB 只存 URL、尺寸、Content-Type 与哈希，二进制放对象存储并用预签名 URL 直传"}, {"title": "第 3 步：上传只按文件名或 Content-Type…", "body": "后缀与客户端声明都可伪造，伪装成图片的 HTML 被直出会带来存储型脚本风险", "tip": "扩展名白名单 + magic bytes（PNG 89 50 4E 47、JPEG FF D8 FF）+ 大小上限，三者叠加"}]' />


## 图片服务：ETag、预签名直传与容量评估

图片二进制不要进关系库：DB 只存对象存储 URL、尺寸、`Content-Type` 与内容哈希，大字段会让备份膨胀、缓冲池命中率下降、列表查询变慢。

上传校验要三重叠加：`Content-Type` 白名单、文件头 magic bytes（PNG 为 89 50 4E 47、`JPEG` 为 FF D8 FF）、大小上限，因为后缀与客户端声明都可伪造；SVG 与 `HTML` 若被当图片直出会带来存储型脚本风险，应拒绝或强制以附件下载。

缩略图生成交给异步 worker（`Pillow` 解码大图耗内存，还要限制像素总量），产出多规格后再更新元数据。`ETag` 用内容哈希（`hashlib.md5` 或 sha256 的十六进制），客户端带 `If-None-Match` 回来且哈希未变就返回 `304` Not Modified，只花一个头不传正文。

预签名 URL 用 `hmac.new` 配 `hashlib.sha256`，把密钥、资源名与过期时间拼成消息生成签名并附带过期时间，让客户端直传对象存储而不经服务端；校验时用 `hmac.compare_digest` 做常量时间比较、先判过期再比签名。

容量评估要压测出单机 QPS 与瓶颈位置：并发数除以平均延迟是吞吐上界，监控 p99 延迟、缓存命中率、回源率、带宽与 4xx/5xx 占比，才能判断该加缓存、加带宽还是加实例。

<ConceptDiagram type='layers3' title='第 126 讲 · 分层视角' labels='发号与 Base62：为什么不用 UUI…|301 / 302 语义、LRU 缓存与…|图片服务：ETag、预签名直传与容量评估|监控与容量' caption='图片服务：ETag、预签名直传与容量评估' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 监控与容量 落在哪一层。


### 压测得出的单机 QPS 与瓶颈位置

<Term word='发号与 Base62' text='短码来自一个单调递增的发号器：数据库自增主键、Redis 的 `INCR` 或 Snowflake（时间戳 + 机器号 + 序列）。拿到整数 id 后用 `Base62` 压成短码，字符集固定为 0-9、A-Z、a-z 共 62 个 URL 安全字符；码长约等于 `floor(log_62(n)) + 1`，62 的…' />

<Term word='301 / 302 语义' text='`http.HTTPStatus` 里 `301` 的 phrase 是 Moved Permanently、`302` 是 Found（不是 Moved Temporarily），这正好点出关键差别：`301` 会被浏览器与 CDN 强缓存，短链一旦发出就无法靠改库撤回，只适合永不变更的映射；`302` 默认不缓存…' />

<CheckList id='P126a' title='上线前自检' :items='["能复现并解释「短链用 301，运营改目标后老链接不生效」", "能复现并解释「把图片二进制存进 MySQL」", "能复现并解释「上传只按文件名或 Content-Type 判类型」", "能用一条命令验证 发号与 Base62", "关键路径有自动化测试与失败分支"]' />


## 短链与图片服务的失败模式

**短链与图片服务失败模式**

| 现象 | 根因 | 防线 |
| --- | --- | --- |
| 改了目标但老短码仍指旧址 | 301 被浏览器/CDN 强缓存 | 默认用 302，永久映射才用 301 |
| 备份与列表查询一起变慢 | 图片二进制存进关系库 | DB 只存 URL 与元数据，对象存储放文件 |
| 上传的 HTML 被当图片直出 | 只信后缀与 Content-Type | 白名单 + magic bytes + 大小上限三重校验 |
| 数据库 QPS 居高不下 | 缓存命中率低、缓存穿透 | LRU 预热热点键、空值缓存或布隆挡穿透 |
| 压测加实例仍不涨吞吐 | 瓶颈在带宽或回源而非 CPU | 先看命中率与回源率，再决定扩容方向 |

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 短链用 301，运营改目标后老链接不生效 | 301 是永久重定向，浏览器与 CDN 会强缓存，改库不影响已缓存的映射 | 默认返回 302 Found；只有确认永不变更的映射才用 301，且提前声明缓存头策略 |
| 把图片二进制存进 MySQL | 大字段让备份膨胀、缓冲池命中率下降、列表查询变慢，且对象存储的成本与带宽优势全丢 | DB 只存 URL、尺寸、Content-Type 与哈希，二进制放对象存储并用预签名 URL 直传 |
| 上传只按文件名或 Content-Type 判类型 | 后缀与客户端声明都可伪造，伪装成图片的 HTML 被直出会带来存储型脚本风险 | 扩展名白名单 + magic bytes（PNG 89 50 4E 47、JPEG FF D8 FF）+ 大小上限，三者叠加 |


## 带发号、缓存与防刷的短链服务核心

一个读多写少的短链服务要把四件事做对：发号必须单调且可编解码、解析路径要尽可能短、热点码要留在内存缓存、异常来源要能挡在入口。

下面用标准库实现最小内核：`b62` 把自增 `seq` 压成短码，`create` 按 `permanent` 参数决定 `301` 还是 `302` 并写进 store，`resolve` 先查 blocked 集合做防刷、再查 LRU 缓存命中就直接返回状态码、未命中才回源 store 并回填缓存，容量超限时淘汰最久未用键。

真实项目把 store 换成数据库、cache 换成 Redis、blocked 换成令牌桶，并在 `create` 前预热活动短码、在 `resolve` 埋点统计点击与命中率，再用压测得出单机 QPS。片段可直接运行，重点看缓存命中如何缩短重定向路径。

```python
from collections import OrderedDict

ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

def b62(n):
    s = ''
    while n:
        n, r = divmod(n, 62)
        s = ALPHABET[r] + s
    return s or '0'

class ShortLink:
    def __init__(self, cap=2):
        self.seq, self.store, self.cache, self.cap = 1000, {}, OrderedDict(), cap
        self.blocked = set()
    def create(self, url, permanent=False):
        self.seq += 1
        code = b62(self.seq)
        self.store[code] = (url, 301 if permanent else 302)
        return code
    def resolve(self, code, ip):
        if ip in self.blocked:
            return 429
        if code in self.cache:
            self.cache.move_to_end(code)
            return self.cache[code][1]
        if code not in self.store:
            return 404
        self.cache[code] = self.store[code]
        if len(self.cache) > self.cap:
            self.cache.popitem(last=False)
        return self.store[code][1]

svc = ShortLink()
a = svc.create('https://a.example', permanent=True)
b = svc.create('https://b.example')
print('codes', a, b)
print('resolve', svc.resolve(a, '1.2.3.4'), svc.resolve(a, '1.2.3.4'))
svc.blocked.add('9.9.9.9')
print('blocked', svc.resolve(a, '9.9.9.9'))
print('missing', svc.resolve('zzzz', '1.2.3.4'))
```

<Callout type="idea" title='落地提示' text='热点键预热、对象存储直传、图片处理异步化，并用压测得出单机 QPS 与瓶颈位置' />


## 练习、自测与速记

<Exercise title='基础：实现 Base62 编解码并验证往返' task='写 b62(n) 与 unb62(s)，对 0、61、62、3844 打印编码，并检查前一千个整数往返是否全部一致。' solution='A = &#39;0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz&#39;\ndef b62(n):\n    if n == 0: return &#39;0&#39;\n    s = &#39;&#39;\n    while n:\n        n, r = divmod(n, 62)\n        s = A[r] + s\n    return s\ndef unb62(s):\n    n = 0\n    for ch in s:\n        n = n * 62 + A.index(ch)\n    return n\nprint([b62(i) for i in (0, 61, 62, 3844)])\nprint(all(unb62(b62(i)) == i for i in range(1000)))' explain='依次得到 [&#39;0&#39;, &#39;z&#39;, &#39;10&#39;, &#39;100&#39;] 与 True。divmod 逐位取余、按权重累加还原，字符集顺序固定是二者互逆的前提。' />

<Exercise title='进阶：用 HMAC 签发并校验带过期时间的预签名 URL' task='实现 sign(resource, expires) 与 verify(resource, expires, sig, now)，验证合法、篡改资源、过期三种情况，说明为何要先判过期。' solution='import hashlib, hmac\nS = b&#39;k&#39;\ndef sign(res, exp):\n    return hmac.new(S, (res + &#39;:&#39; + str(exp)).encode(), hashlib.sha256).hexdigest()[:16]\ndef verify(res, exp, sig, now):\n    if now &gt; exp: return &#39;expired&#39;\n    return &#39;ok&#39; if hmac.compare_digest(sign(res, exp), sig) else &#39;bad signature&#39;\ns = sign(&#39;img/1.png&#39;, 100)\nprint(verify(&#39;img/1.png&#39;, 100, s, 50))\nprint(verify(&#39;img/2.png&#39;, 100, s, 50))\nprint(verify(&#39;img/1.png&#39;, 100, s, 200))' explain='依次输出 ok、bad signature、expired。先判过期能避免给已失效链接做无谓的签名计算与比较，compare_digest 提供常量时间比较。' />

<Quiz no='126-1' q='短链服务默认应选哪个重定向状态码，原因是什么？' :options='["302 Found，默认不缓存，便于统计点击与随时改目标", "301 Moved Permanently，浏览器会缓存更快", "307，因为它保留请求方法", "308，因为它最稳定"]' answer="0" explain='301 会被浏览器与 CDN 强缓存，改库也无法撤回已发出的短码；302 的 phrase 是 Found，默认不缓存，每次回源让统计与目标变更都可控。' />

<Quiz no='126-2' q='Base62 相比 md5(url) 作短码的关键优势是？' :options='["由单调 id 生成、长度约 6 位且无碰撞查重，可自定义", "码长固定 32 位更整齐", "同一 URL 必然得到同一码", "不需要持久化发号器"]' answer="0" explain='md5(url) 是 32 位十六进制、同 URL 重复、无法自定义且仍需碰撞兜底；Base62 由持久化单调 id 生成，十亿量级仅约 6 位，且可做可逆混淆。' />

<Quiz no='126-3' q='关于 ETag 与 304，准确的说法是？' :options='["内容哈希作 ETag，带 If-None-Match 且未变时返回 304 不传正文", "304 表示内容已变化需要重传", "ETag 必须用 URL 作值", "304 会带上完整图片正文"]' answer="0" explain='ETag 是内容哈希，客户端用 If-None-Match 回带；服务端比对一致则返回 304 Not Modified，只传响应头省掉正文带宽。' />

<Predict no='126-4' q='b62(3844) 的结果以及 62 进制的进位含义是？' :options='["&#39;100&#39;，因为 3844 等于 62 的 2 次方，进入 3 位", "&#39;zz&#39;，因为 3844 是 62 的 2 次方减一", "&#39;61z&#39;，按十进制逐位映射"]' answer='0' output='codes [&#39;0&#39;, &#39;z&#39;, &#39;10&#39;, &#39;100&#39;]' explain='62 进制里 61 是 &#39;z&#39;，62 进位成 &#39;10&#39;，62 的 2 次方 3844 进位成 &#39;100&#39;；而 3843 才是 &#39;zz&#39;。每多一位可多表示 62 倍数量。' />

<FillBlank no='126-5' tpl='___ hashlib' :answers='["import"]' hint='回想本讲关于 发号与 Base62 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 发号与 Base62：为什么不用 UUID 或内容哈希 的落点。' />

<KnowledgeCard :points='["短码由持久化单调发号器 + Base62 生成，码长 floor(log_62(n))+1，十亿量级约 6 位", "301 Moved Permanently 可强缓存且不可撤回；302 Found 默认不缓存，是短链默认；307/308 保留方法与 body", "OrderedDict 的 move_to_end 与 popitem(last=False) 实现 O(1) LRU；回源 QPS = 总 QPS × (1 - 命中率)", "图片二进制放对象存储、DB 只存元数据；上传用白名单 + magic bytes + 大小上限三重校验", "ETag 用内容哈希，If-None-Match 命中返回 304；预签名 URL 用 HMAC 加过期时间，compare_digest 常量时间比较", "容量看 p99、命中率、回源率与带宽；并发除以平均延迟是吞吐上界，扩容前先定位瓶颈"]' :pitfalls='["短链用 301，运营改目标后老链接不生效", "把图片二进制存进 MySQL", "上传只按文件名或 Content-Type 判类型", "把图片二进制存进数据库，备份与查询会一起变慢；不做 Content-Type 校验还会带来存储型风险"]' summary='读多写少的服务，优化重点在缓存命中率与重定向路径的长度，而不是框架本身' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 短码由持久化单调发号器 + Base62 生成，码长 floor(log_62(n))+1，十亿量级约 6 位 | 建立直觉 |
| 301 Moved Permanently 可强缓存且不可撤回；302 Found 默认不缓存，是短链默认；307/308 保留方法与 body | 跑通示例 |
| OrderedDict 的 move_to_end 与 popitem(last=False) 实现 O(1) LRU；回源 QPS = 总 QPS × (1 - 命中率) | 深入边界 |
| 图片二进制放对象存储、DB 只存元数据；上传用白名单 + magic bytes + 大小上限三重校验 | 工程落地 |
| ETag 用内容哈希，If-None-Match 命中返回 304；预签名 URL 用 HMAC 加过期时间，compare_digest 常量时间比较 | 随堂检测 |
| 容量看 p99、命中率、回源率与带宽；并发除以平均延迟是吞吐上界，扩容前先定位瓶颈 | 复盘 |

1. 短码由持久化单调发号器 + Base62 生成，码长 floor(log_62(n))+1，十亿量级约 6 位

2. 301 Moved Permanently 可强缓存且不可撤回；302 Found 默认不缓存，是短链默认；307/308 保留方法与 body

3. OrderedDict 的 move_to_end 与 popitem(last=False) 实现 O(1) LRU；回源 QPS = 总 QPS × (1 - 命中率)

[下一讲：实战 06 · 日志 ETL 与 CSV / SQL 查询工具](/projects/data-etl)

```bash
python -m compileall -q . && python -m pytest -q
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 发号与 Base62 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/126-net-shortlink.py`

```bash
python3 examples/lessons/126-net-shortlink.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/126-net-shortlink.py) · [全部示例代码索引](/examples/)
