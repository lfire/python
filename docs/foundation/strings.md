---
title: 第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义
description: 能定位并解决绝大多数乱码问题
---

<StageHeader stage='L1 · 编程地基' level='★★☆☆☆' time='30 分钟' goal='能定位并解决绝大多数乱码问题' prereq='第 008 讲 · 数值体系：int 任意精度、float、Decimal 与 bool' />

# 第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义

数字刚算清，程序平日打交道的却更多是字符串与文本。偏偏文字更易出岔子：同一份中文配置换台机器就花了，表头还莫名多个看不见的前缀。毛病几乎都绕不开一个根：字符和字节被混成了一回事。这一讲就把边界画清。我们先从 Unicode 码点与编码讲起，立住 str 是字符序列、bytes 是字节序列、二者不能互转；再看 encode 与 decode 碰到非法字节怎么办、BOM 是什么；最后落在习惯上——源码、文件、`HTTP` 头、数据库都显式声明 UTF-8，转换只在边界做一次。有变量、类型与一点文件读写的印象就够；学完再遇乱码，你能顺着『字符还是字节』定位。


## 报表首列名多了个看不见的字符：乱码从哪来

一个服务在 macOS 上读用户上传的 CSV 一切正常，部署到 Windows 容器后中文列名全变乱码，日志里还夹着问号方块；排查发现代码里 `open(path)` 没写 encoding，依赖了平台默认编码，而两边默认编码并不一致。

另一处把 `HTTP` 响应体（bytes）和用户拼的字符串直接相加，得到 TypeError，提示 str 不能与 bytes 拼接；还有人把带 BOM 的文件用 utf-8 读进来，第一列字段名前面多了个看不见的字符，导致字典查键永远失败。

朴素解法是「到处 `decode('utf-8')` 一下」或「把乱码字符 replace 掉」，前者会在已经解码的 str 上再抛 AttributeError，后者把数据悄悄改坏。

Python 3 把 str 与 bytes 的边界画得很清楚：str 是 Unicode 码点序列，bytes 是字节序列，二者之间必须显式编码与解码。本讲把码点、UTF-8 编码规则、BOM、错误处理与四处显式声明讲清，让乱码变成可定位的问题。


## 码点、编码与 str / bytes 的硬边界

str 是 Unicode 码点的不可变序列，`len('中文')` 得 2 是码点数，`ord('中')` 得 20013（U+4E2D），`chr(20013)` 反查回字符；bytes 是 0 到 255 整数的不可变序列，`len('中文'.encode('utf-8'))` 得 6 是字节数。

二者之间只有两个方向：`str.encode(encoding)` 生成 bytes，`bytes.decode(encoding)` 生成 str，没有隐式转换。

UTF-8 是变长编码：`ASCII` 字符占 1 字节，`U+0080` 到 `U+07FF` 占 2 字节，`U+0800` 到 `U+FFFF` 占 3 字节（汉字在此），`U+10000` 以上占 4 字节，`'中'.encode('utf-8').hex()` 得 e4b8ad 就是三字节。

Python 3 明确禁止 str 与 bytes 拼接、比较或混写：两者相加会抛 TypeError，用 == 比较恒为 False 且不报错。`open()` 的文本模式负责在边界处解码，二进制模式 rb 则原样返回 bytes；混用是乱码与类型错误的共同来源。

源码文件默认按 UTF-8 读（PEP 3120，3.0 起），可用首行编码声明覆盖，但工程上统一 UTF-8 更省心。raw 字符串前缀 r 让反斜杠不参与转义，适合写正则与路径；需要真实换行值时用 `chr(10)` 或多行字符串，不要在字面量里堆转义序列。

```python
s = '中文'
b = s.encode('utf-8')
print('str_len', len(s))
print('bytes_len', len(b))
print('hex', b.hex())
print('roundtrip', b.decode('utf-8') == s)
print('codepoint', ord('中'))
```

<OutputBox title='主示例运行结果' output='str_len 2\nbytes_len 6\nhex e4b8ade69687\nroundtrip True\ncodepoint 20013' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='s = &#39;中文&#39;\nb = s.encode(&#39;utf-8&#39;)\nprint(&#39;str_len&#39;, len(s))\nprint(&#39;bytes_len&#39;, len(b))\nprint(&#39;hex&#39;, b.hex())\nprint(&#39;roundtrip&#39;, b.decode(&#39;utf-8&#39;) == s)\nprint(&#39;codepoint&#39;, ord(&#39;中&#39;))' :notes='["s 是 str，长度按 Unicode 码点计", "encode 把码点序列映射为 UTF-8 字节序列，得到 bytes", "两个汉字对应两个码点，len 为 2", "UTF-8 里每个汉字占 3 字节，故字节数为 6", "hex 以十六进制显示原始字节，便于核对编码规则", "decode 把字节按同一编码还原，与原始 str 相等", "ord 返回 &#39;中&#39; 的码点 20013，即 U+4E2D"]' title='第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**str 与 bytes 的边界**

| 操作 | 输入 | 输出 | 出错信号 |
| --- | --- | --- | --- |
| s.encode('utf-8') | str | bytes | 编码到 ascii 且含汉字时抛 UnicodeEncodeError |
| b.decode('utf-8') | bytes | str | 非法字节抛 UnicodeDecodeError |
| len(s) | str | 码点数 | '中文' 为 2 |
| len(s.encode('utf-8')) | 字节数 | 整数 | '中文' 为 6 |
| str 加 bytes | 混合类型 | 报错 | TypeError，无隐式转换 |

<ConceptDiagram type='compare2' title='第 009 讲 · 码点、编码与 str / bytes 的硬边界' labels='码点、编码与 str / bytes 的硬边…|encode / decode 的错误处理与…|四处显式声明：把乱码挡在边界之外|多行字符串' caption='能定位并解决绝大多数乱码问题' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## encode / decode 的错误处理与 BOM

decode 的默认 errors 是 strict，遇到非法字节序列抛 UnicodeDecodeError（含 start、end、reason）；可改成 ignore 丢弃非法字节、replace 换成 `U+FFFD`、backslashreplace 保留成转义文本。

encode 同样有 errors：中文编码到 ascii 会用 strict 抛 UnicodeEncodeError，xmlcharrefreplace 能转成字符引用。

BOM（字节顺序标记）是 `U+FEFF`，用 `codecs.BOM_UTF8.hex()` 可核对为 efbbbf；UTF-8 本身无字节序问题，但有些 Windows 工具会写 BOM，用普通 utf-8 解码会把 `U+FEFF` 当成一个真实字符留在串首，导致首列名多一个不可见前缀，此时应用 `utf-8-sig` 自动剥离。

UTF-16 与 UTF-32 必须区分大小端：`'A'.encode('utf-16-le').hex()` 是 4100，而 utf-16 会在开头加 ff fe 的 BOM。

codecs 模块暴露了 `BOM_UTF8`、`BOM_UTF16_LE` 等常量便于核对；`sys.getdefaultencoding()` 是 str 内部转换用的编码（3.x 固定 utf-8），`sys.getfilesystemencoding()` 是文件名编码（macOS 与多数 Linux 是 utf-8，Windows 历史上是 mbcs），二者不是一回事，别拿前者去猜文件内容的编码。

```python
import codecs
raw = bytes([0xe4, 0xb8, 0xad])
print('decoded', raw.decode('utf-8'))
print('encoded_len', len('中'.encode('utf-8')))
try:
    bytes([0xff]).decode('utf-8')
except UnicodeDecodeError as e:
    print('strict_error', type(e).__name__)
print('ignore_len', len(bytes([0xff]).decode('utf-8', errors='ignore')))
print('bom', codecs.BOM_UTF8.hex())
print('utf16_hex', 'A'.encode('utf-16-le').hex())
```

<OutputBox title='对照写法：先自己猜，再点开' output='decoded 中\nencoded_len 3\nstrict_error UnicodeDecodeError\nignore_len 0\nbom efbbbf\nutf16_hex 4100' guess="true" />


## decode 的 errors 策略：replace 为什么不可逆

乱码几乎都发生在系统边界，工程上要在四处都写明 UTF-8：源码文件（保存为 UTF-8，必要时加编码声明）、文件 IO（用 `open()` 时显式传 `encoding='utf-8'`，绝不要省略让平台默认值决定）、`HTTP` 头（Content-Type 带 `charset=utf-8`，响应体 encode 与请求体 decode 成对）、数据库连接（连接串或驱动参数指定 charset，如 MySQL 的 utf8mb4，注意 utf8mb3 存不下四字节的表情符号）。

每处只做一次转换：读入时 decode 成 str，内部全程用 str 处理，写出时再 encode 成 bytes；在两个边界之间反复编解码既慢又容易把已替换的字符二次破坏。

诊断顺序也有章法：先确认原始字节（用 `.hex()` 或 `repr(bytes)` 看到底是什么），再确认声明的编码，最后确认是否被 BOM、`errors='replace'` 或双重解码改过；直接对乱码字符串再 decode 会在 str 上抛 AttributeError。

日志里打印 bytes 的十六进制比打印乱码字符有用得多，因为前者保留了原始证据。


## 四处显式声明：把乱码挡在边界之外

CPython 内部用 PEP 393 的灵活字符串表示：一个 str 对象按最大码点选择 1、2 或 4 字节的定宽存储（Latin-1、UCS-2、UCS-4），因此索引是 `O(1)` 且不含变长编码的歧义；bytes 则是简单的 PyBytesObject，存一段 char 数组加长度。

编码与解码的本质是在「码点序列」与「字节序列」之间按某个 codec 做映射，UTF-8 用首字节的高位模式声明后续字节数（110xxxxx 表示 2 字节、1110xxxx 表示 3 字节），解码器据此还原码点；非法序列（如孤立的 `0xff`）无法匹配任何模式，于是 strict 模式抛 UnicodeDecodeError 并给出出错区间。

BOM 只是 `U+FEFF` 这个码点在流开头的约定，UTF-16 与 UTF-32 靠它判断大小端，UTF-8 不需要但常被写入，故有 `utf-8-sig` 这个专门剥离它的 codec。

`open()` 的文本模式在 C 层包了一个 IncrementalDecoder，逐块读入字节并增量解码，写入时用 IncrementalEncoder 反向处理。理解「内部定宽码点、边界才做变长字节映射」，就知道为什么不能在 str 上调 decode、为什么省略 encoding 会跨平台翻车。


## 跨系统 CSV：入口解码一次、出口编码一次

一批用户上传的 CSV 来自不同系统：有的带 UTF-8 BOM，有的用 `ASCII` 兼容编码，个别文件还混入非法字节。直接 `read_text` 要么首列多出不可见字符，要么整批抛异常。

下面这段给出边界清晰的清洗流程：先以二进制拿到原始 bytes 并留十六进制摘要，按声明的编码在入口解码一次（带 BOM 的用 `utf-8-sig` 自动剥离），内部全程用 str 处理，写出时再编码一次并验证往返无损。重点是每处只做一次转换，并把原始字节摘要打进日志，便于事后回溯而不是靠猜编码。

真实系统还应为解码失败的文件单独记录字节片段并跳过，不让一条脏数据中断整批。

```python
import codecs

def decode_once(blob, enc):
    return blob.decode(enc)

def summarize(blob):
    return blob[:6].hex()

def encode_once(text):
    return text.encode('utf-8')

bom_blob = codecs.BOM_UTF8 + 'name,city'.encode('utf-8')
plain_blob = 'name,city'.encode('ascii')
for enc, blob in [('utf-8-sig', bom_blob), ('ascii', plain_blob)]:
    text = decode_once(blob, enc)
    out = encode_once(text)
    print('hex', summarize(blob))
    print('first', text.split(',')[0])
    print('clean', text == 'name,city')
    print('roundtrip', out.decode('utf-8') == text)
```

<Callout type="idea" title='落地提示' text='工程上统一 UTF-8：源码、文件 IO、HTTP 头、数据库连接四处都要显式声明，边界处做一次转换' />


## 编码错因速查

乱码排查先留原始字节：UnicodeDecodeError 的 start、end 定位到哪一段，用 .`hex()` 记下，比对 `codecs.BOM_UTF8` 的 efbbbf 便知 BOM 有没有剥。

再看声明：open 省略 encoding 时由 locale 默认值决定，Windows 常是 cp936，用 utf-8 解就报错。

`errors='replace'` 换成 U+`FFFD` 不可逆，对 str 再 decode 抛 AttributeError。

下表按现象、根因、写法列出，配排查顺序。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| open 不写 encoding，或把 str 与 bytes 直接相加 | 省略 encoding 时依赖 locale 默认编码，Windows 与 Linux 可能不同；str 与 bytes 无隐式转换，拼接会抛 TypeError | open 一律写明 encoding='utf-8'；边界处先 encode/decode 再参与运算 |
| 用普通 utf-8 读带 BOM 的文件 | 串首会留下不可见的 U+FEFF，导致首列名多一个前缀、字典查键静默失败 | 改用 encoding='utf-8-sig' 自动剥离 BOM，或用 codecs.BOM_UTF8 核对字节 |
| 对已经是 str 的乱码再 decode，或用 errors='replace' 兜底 | str 没有 decode 方法会抛 AttributeError；replace 把非法字节换成 U+FFFD 且不可逆 | 保留原始 bytes 并用 .hex() 或 repr 记录证据，在唯一边界处按正确编码解码一次 |

<Callout type="warn" title='本讲最容易踩的坑' text='open 不写 encoding，或把 str 与 bytes 直接相加：省略 encoding 时依赖 locale 默认编码，Windows 与 Linux 可能不同；str 与 bytes 无隐式转换，拼接会抛 TypeError' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：open 不写 encoding，或把 st…", "body": "省略 encoding 时依赖 locale 默认编码，Windows 与 Linux 可能不同；str 与 bytes 无隐式转换，拼接会抛 TypeError", "tip": "open 一律写明 encoding=&#39;utf-8&#39;；边界处先 encode/decode 再参与运算"}, {"title": "第 2 步：用普通 utf-8 读带 BOM 的文件", "body": "串首会留下不可见的 U+FEFF，导致首列名多一个前缀、字典查键静默失败", "tip": "改用 encoding=&#39;utf-8-sig&#39; 自动剥离 BOM，或用 codecs.BOM_UTF8 核对字节"}, {"title": "第 3 步：对已经是 str 的乱码再 decode，或…", "body": "str 没有 decode 方法会抛 AttributeError；replace 把非法字节换成 U+FFFD 且不可逆", "tip": "保留原始 bytes 并用 .hex() 或 repr 记录证据，在唯一边界处按正确编码解码一次"}]' />


## 边界处只做一次转换：练习、自测与速记

<Exercise title='基础：验证 str 与 bytes 的长度差' task='打印 len(&#39;中文&#39;)、len(&#39;中文&#39;.encode(&#39;utf-8&#39;))、&#39;中&#39;.encode(&#39;utf-8&#39;).hex()、ord(&#39;中&#39;)，并解释前两者为何相差三倍。' solution='s = &#39;中文&#39;\nprint(&#39;chars&#39;, len(s))\nprint(&#39;bytes&#39;, len(s.encode(&#39;utf-8&#39;)))\nprint(&#39;hex&#39;, &#39;中&#39;.encode(&#39;utf-8&#39;).hex())\nprint(&#39;codepoint&#39;, ord(&#39;中&#39;))' explain='str 长度是码点数 2，UTF-8 里每个汉字占 3 字节故字节数为 6；&#39;中&#39; 的编码是 e4b8ad，码点是 20013（U+4E2D）。' />

<Exercise title='进阶：用 utf-8-sig 处理 BOM' task='构造带 BOM 的字节，分别用 utf-8 与 utf-8-sig 解码，打印首字符的码点，说明普通 utf-8 为何让首列查键失败。' solution='import codecs\nblob = codecs.BOM_UTF8 + &#39;name&#39;.encode(&#39;utf-8&#39;)\na = blob.decode(&#39;utf-8&#39;)\nb = blob.decode(&#39;utf-8-sig&#39;)\nprint(&#39;plain_first_ord&#39;, ord(a[0]))\nprint(&#39;sig_first&#39;, b[0])\nprint(&#39;bom_hex&#39;, codecs.BOM_UTF8.hex())' explain='普通 utf-8 把 U+FEFF 当真实字符留在串首，ord 为 65279，导致首字段名变成带不可见前缀的键；utf-8-sig 剥离它，首字符回到 n。' />

<Quiz no='009-1' q='&#39;中文&#39;.encode(&#39;utf-8&#39;) 的长度是？' :options='["6，汉字在 UTF-8 里各占 3 字节", "2，等于码点数", "4，固定每字 2 字节", "9，含 BOM"]' answer="0" explain='U+0800 到 U+FFFF 的码点在 UTF-8 里用 3 字节表示，两个汉字共 6 字节；UTF-8 编码本身不附加 BOM。' />

<Quiz no='009-2' q='读带 UTF-8 BOM 的文件，正确的 encoding 是？' :options='["utf-8-sig，自动剥离串首 U+FEFF", "utf-8，效果完全相同", "ascii", "latin-1"]' answer="0" explain='普通 utf-8 会把 U+FEFF 解码成一个真实字符留在串首；utf-8-sig 是专门剥离 BOM 的 codec，适合 Excel 等工具导出的文件。' />

<Quiz no='009-3' q='关于 str 与 bytes，哪项描述准确？' :options='["二者必须显式 encode/decode，拼接会抛 TypeError 且无隐式转换", "Python 3 会自动把 bytes 转成 str", "对 str 调 decode 可修复乱码", "== 比较会先尝试自动解码"]' answer="0" explain='Python 3 取消了 Python 2 时代的隐式转换：str 与 bytes 拼接抛 TypeError，== 恒为 False；str 没有 decode 方法，转换只在边界显式进行。' />

<Predict no='009-4' q='主示例里 print(&#39;hex&#39;, b.hex())（b = &#39;中文&#39;.encode(&#39;utf-8&#39;)）输出什么？' :options='["e4b8ade69687", "4e2d6587", "efbbbfe4b8ade69687"]' answer='0' output='e4b8ade69687' explain='两个汉字各占 3 字节：&#39;中&#39; 为 e4b8ad、&#39;文&#39; 为 e69687，拼成 12 个十六进制字符；UTF-8 编码不自带 BOM，故没有 efbbbf 前缀。' />

<FillBlank no='009-5' tpl='print(&#39;roundtrip&#39;, b.decode(&#39;utf-8&#39;) ___ s)' :answers='["=="]' hint='回想本讲关于 Unicode 码点与编码 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 码点、编码与 str / bytes 的硬边界 的落点。' />

<KnowledgeCard :points='["str 是 Unicode 码点序列、bytes 是 0 到 255 字节序列，二者必须显式 encode/decode", "UTF-8 变长：ASCII 1 字节、汉字 3 字节；&#39;中&#39; 编码 e4b8ad，ord(&#39;中&#39;) 为 20013", "BOM 是 U+FEFF，UTF-8 的 BOM 字节 efbbbf；带 BOM 文件用 utf-8-sig 解码自动剥离", "decode 的 errors：strict 抛 UnicodeDecodeError，ignore 与 replace 会静默或不可逆地改数据", "open 文本模式在边界增量解码，省略 encoding 会依赖平台默认编码导致跨平台乱码", "四处显式 UTF-8：源码、文件 IO、HTTP 头、数据库连接；每处只做一次转换"]' :pitfalls='["open 不写 encoding，或把 str 与 bytes 直接相加", "用普通 utf-8 读带 BOM 的文件", "对已经是 str 的乱码再 decode，或用 errors=&#39;replace&#39; 兜底", "用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台时突然乱码"]' summary='str 是字符序列，bytes 是字节序列，二者之间必须显式编码/解码；Python 3 把这条边界画得很清楚，正是为了消灭 Python 2 时代的隐式转换' />

1. str 是 Unicode 码点序列、bytes 是 0 到 255 字节序列，二者必须显式 encode/decode

2. UTF-8 变长：ASCII 1 字节、汉字 3 字节；'中' 编码 e4b8ad，ord('中') 为 20013

3. BOM 是 U+FEFF，UTF-8 的 BOM 字节 efbbbf；带 BOM 文件用 utf-8-sig 解码自动剥离

[下一讲：字符串操作：切片、f-string 与常用方法](/foundation/string-ops)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/009-strings.py`

```bash
python3 examples/lessons/009-strings.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/009-strings.py) · [全部示例代码索引](/examples/)
