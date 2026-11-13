---
title: 第 027 讲 · 阶段综合：词频统计与内存版 KV
description: 用容器与生成器交付一个可测的小工具
---

<StageHeader stage='L2 · 容器与序列' level='★★☆☆☆' time='45 分钟' goal='用容器与生成器交付一个可测的小工具' prereq='第 026 讲 · 生成器与 yield：send / throw / close' />

# 第 027 讲 · 阶段综合：词频统计与内存版 KV

容器、迭代器、生成器一路走下来，手里已有一整盒零件：装数据的、按名字取的、边读边吐的都有。这一讲收束这一阶段，把它们拼成能交付、日后能换零件的小工具。

一个词频脚本跑两 GB 日志就撑不住，因为先把整份文本一次读进来、再切出几千万个词；换成逐行读、边读边累计，内存只剩几十 MB。可统计和读文件写死在一处，缓存又把字典直接摊给业务，接持久化时调用点全得改。我们先做文本规整与分词，把噪声挡在计数前；再用生成器管道配计数器增量统计；最后给 KV 抽出读写删的窄接口。需要你带着字典、计数器、生成器与 with 来。学完你能交出存储层能替换的小工具。


## 一次性 read() 进 list，文件一大就 OOM

一个词频统计脚本上线后跑 2GB 的日志直接 OOM：它先 `read()` 把整份文本读成字符串，再 `split()` 成几千万个词的 list，最后才交给 Counter。同一份数据换成逐行迭代加增量累计后内存只剩几十 MB。

第二个工单来自另一个方向：统计逻辑和文件读取写死在一个函数里，单元测试为了跑一次要造临时文件、还要清理，CI 上频繁因为权限和路径失败。第三个更长期：KV 缓存直接用模块级 dict 暴露给业务代码，后来要接持久化时十几个调用点全部得改。这三个问题分别对应内存、可测性与接口抽象。

本讲把文本规整、生成器管道、Counter 增量统计、get / set / delete 窄接口与基准测量串成一个可交付的小工具。

<Callout type="warn" title='先看一个真实会出错的写法' text='一次性把所有行 read() 进 list 做词频，文件一大就 OOM：物化整份文本与中间词列表，内存随数据量线性增长' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段二 · 容器与序列 |
| 前置 | 第 026 讲 · 生成器与 yield：send / throw / close |
| 难度 / 建议时长 | ★★☆☆☆ · 45 分钟 |
| 本讲新增 | 文本规整与分词、Counter 与排序、生成器管道 |
| 一句话目标 | 用容器与生成器交付一个可测的小工具 |
| 为下一讲铺垫 | 函数定义与参数形态 |

<CheckList id='P027a' title='学完你应当能' :items='["能讲清 文本规整与分词：把噪声挡在统计之前", "能讲清 生成器管道与增量统计：内存只与不同词有关", "能讲清 KV 窄接口、持久化与可替换实现", "能在工程里处理 基准测量"]' />


## 文本规整与分词：把噪声挡在统计之前

词频看起来只是 split 一下，实际要先把噪声挡掉才有意义。大小写归一用 `str.casefold()`（3.3+）而不是 `lower()`：casefold 专为 Unicode 无大小写比较设计，能把德语 ß 折成 ss、把连字与带点 I 归一，lower 只做简单映射，跨语言文本会漏词。

去标点用 `str.translate` 配 `str.maketrans()`，字符映射在 C 层一次完成，比逐字符 `replace()` 或正则替换更快；

也可以直接用 `re.findall()` 自定义词法。`str.split()` 默认按任意空白切分且忽略首尾空白，适合已规整的文本。要注意标点删除会把 '3.13' 拼成 '313'、把连字符词合成一个 token，这类取舍必须按语料定，并写进测试样本。

统计侧用 `collections.Counter`：`update()` 是累加而非覆盖，缺键返回 0，`most_common(n)` 按计数降序、相等时按首次出现顺序，`total()` 返回所有计数之和（3.10+）；

数据量大时取 top-N 用 `heapq.nlargest()` 比全表 `sorted()` 更省。

```python
import re, string
from collections import Counter
from time import perf_counter

TRANS = str.maketrans('', '', string.punctuation)

def words(line):
    cleaned = line.casefold().translate(TRANS)
    return re.findall(r'[a-z0-9]+', cleaned)

def count_lines(lines):
    counter = Counter()
    for line in lines:
        counter.update(words(line))
    return counter

TEXT = ['Hello, hello!', 'Python 3.13 and python.', 'Guide to the Python.']
c = count_lines(TEXT)
print('total tokens', c.total())
print('hello', c['hello'], 'python', c['python'])
print('top3', c.most_common(3))

class MemoryKV:
    def __init__(self):
        self._data = {}
    def get(self, key, default=None):
        return self._data.get(key, default)
    def set(self, key, value):
        self._data[key] = value
    def delete(self, key):
        return self._data.pop(key, None) is not None
    def __len__(self):
        return len(self._data)

kv = MemoryKV()
for cmd in [('set', 'a', 1), ('set', 'b', 2), ('delete', 'a')]:
    op = cmd[0]
    if op == 'set':
        kv.set(cmd[1], cmd[2])
    elif op == 'delete':
        kv.delete(cmd[1])
print('kv state', kv.get('a'), kv.get('b'), len(kv))

t0 = perf_counter()
big = count_lines(['w' + str(i) for i in range(2000)])
cost = perf_counter() - t0
print('bench ran', big.total() == 2000, cost >= 0)
```

<OutputBox title='主示例运行结果' output='total tokens 10\nhello 2 python 3\ntop3 [(&#39;python&#39;, 3), (&#39;hello&#39;, 2), (&#39;313&#39;, 1)]\nkv state None 2 1\nbench ran True True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import re, string\nfrom collections import Counter\nfrom time import perf_counter\n\nTRANS = str.maketrans(&#39;&#39;, &#39;&#39;, string.punctuation)\n\ndef words(line):\n    cleaned = line.casefold().translate(TRANS)\n    return re.findall(r&#39;[a-z0-9]+&#39;, cleaned)\n\ndef count_lines(lines):\n    counter = Counter()\n    for line in lines:\n        counter.update(words(line))\n    return counter\n\nTEXT = [&#39;Hello, hello!&#39;, &#39;Python 3.13 and python.&#39;, &#39;Guide to the Python.&#39;]\nc = count_lines(TEXT)\nprint(&#39;total tokens&#39;, c.total())\nprint(&#39;hello&#39;, c[&#39;hello&#39;], &#39;python&#39;, c[&#39;python&#39;])\nprint(&#39;top3&#39;, c.most_common(3))\n\nclass MemoryKV:\n    def __init__(self):\n        self._data = {}\n    def get(self, key, default=None):\n        return self._data.get(key, default)\n    def set(self, key, value):\n        self._data[key] = value\n    def delete(self, key):\n        return self._data.pop(key, None) is not None\n    def __len__(self):\n        return len(self._data)\n\nkv = MemoryKV()\nfor cmd in [(&#39;set&#39;, &#39;a&#39;, 1), (&#39;set&#39;, &#39;b&#39;, 2), (&#39;delete&#39;, &#39;a&#39;)]:\n    op = cmd[0]\n    if op == &#39;set&#39;:\n        kv.set(cmd[1], cmd[2])\n    elif op == &#39;delete&#39;:\n        kv.delete(cmd[1])\nprint(&#39;kv state&#39;, kv.get(&#39;a&#39;), kv.get(&#39;b&#39;), len(kv))\n\nt0 = perf_counter()\nbig = count_lines([&#39;w&#39; + str(i) for i in range(2000)])\ncost = perf_counter() - t0\nprint(&#39;bench ran&#39;, big.total() == 2000, cost &gt;= 0)' :notes='["导入正则、标点常量与计时模块", "导入 Counter 做增量计数", "导入 perf_counter 用于基准测量", "用 maketrans 生成&#39;删除所有标点&#39;的映射表", "定义单行分词函数", "casefold 归一大小写，translate 在 C 层去掉标点", "用正则取出字母数字词，注意标点删除会把 3.13 拼成 313", "核心统计函数只接受可迭代的行", "创建空 Counter，缺键返回 0", "逐行迭代，内存里一次只有一行", "update 是累加语义，把本行的词计入总数", "返回累计结果，不物化全量词列表", "三行演示文本，含标点、大小写与数字", "对文本列表做统计，测试不必造文件", "total() 是 3.10+ 的方法，返回所有计数之和", "取出两个高频词验证规整结果", "most_common(3) 按计数降序，相等时按首次出现顺序", "定义内存版 KV，只暴露窄接口", "底层就是一个 dict", "get 允许给默认值，缺失不抛异常", "set 写入键值", "delete 用 pop 并返回是否真的删到", "实现 __len__ 便于观测条数", "创建 KV 实例", "把命令解析成 (op, key, value) 元组走分发表", "取出操作类型", "set 分支调用窄接口", "delete 分支调用窄接口", "a 被删、b 保留，长度为 1", "记录基准起点", "用 2000 个不同词测量一次统计", "计算墙钟耗时", "断言结果与耗时非负，输出可复现", "casefold()（3.3+）比 lower() 更适合 Unicode 无大小写归一；top-N 用 most_common 或 heapq.nlargest", "KV 定义 get / set / delete 窄接口，dict 内存版可无痛替换为 shelve / sqlite3 / redis", "命令分发把 (op, key, value) 映射到接口调用；基准用 perf_counter 测耗时、tracemalloc 测峰值内存", "词频管道：casefold / translate 规整、生成器分词、Counter 增量累计，统计与 IO 分离", "核心函数只接受可迭代对象，测试传 list、生产传文件或标准输入，不必造临时文件", "逐行迭代加生成器管道让内存只与不同词数量有关；read() 全量会随文件大小线性增长", "casefold()（3.3+）比 lower() 更适合 Unicode 无大小写归一；top-N 用 most_common 或 heapq.nlargest"]' title='第 027 讲 · 阶段综合：词频统计与内存版 KV' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='layers3' title='第 027 讲 · 文本规整与分词：把噪声挡在统计之前' labels='文本规整与分词：把噪声挡在统计之前|生成器管道与增量统计：内存只与不同词有关|KV 窄接口、持久化与可替换实现' caption='用容器与生成器交付一个可测的小工具' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### 文本规整与计数工具

**文本规整与计数工具**

| 步骤 | 标准库工具 | 要点 |
| --- | --- | --- |
| 大小写归一 | str.casefold() / lower() | casefold 更适合 Unicode 无大小写比较（3.3+） |
| 去标点 | str.translate(str.maketrans('', '', string.punctuation)) | C 层字符映射，比逐字符 replace 快 |
| 分词 | str.split() / re.findall(r'[a-z0-9]+', text) | split 按任意空白，正则可自定义词法 |
| 计数 | collections.Counter.update(iterable) | 累加语义，缺键返回 0 |
| Top-N | most_common(n) / heapq.nlargest(n, d, key=d.get) | 数据量大时 nlargest 省一次全排序 |

<Callout type="tip" title='核心心智模型' text='词频看起来只是 split 一下，实际要先把噪声挡掉才有意义。大小写归一用 `str.casefold()`（3.3+）而不是 `lower()`：casefold 专为 Unicode 无大小写比较设计，能把德语 ß 折成 ss、把连字与带点 I 归一，lower 只做简单映射，跨语言文本会漏词。' />


## 生成器管道与增量统计：内存只与不同词有关

把「去标点 → 转小写 → 分词 → 计数」每一步写成生成器表达式或小的生成器函数，再用 `yield from` 串成惰性管道，只有最终 Counter 或聚合才真正消费。

CPython 里 `for line in file` 由 TextIOWrapper 逐行缓冲，一次只在内存里放一行；

生成器表达式更进一步，连中间词列表都省掉，每个 token 产出后立刻被计数、随即释放。于是内存占用与不同词的数量相关，而不是文件字节数或总行数，几百 MB 的日志也能在固定内存里跑完。反面写法是 `read()` / `readlines()` 全量读入、再用列表推导物化词列表，内存随数据量线性增长，文件一大就 OOM。

工程上把统计逻辑做成只接受可迭代对象的纯函数：测试传 list、生产传文件对象或标准输入都不用改，也不必造临时文件；

命令分发把输入解析成 `(op, key, value)` 元组走分发表，新增命令只改分发表而不是改统计核心。

基准用 `time.perf_counter` 测墙钟、tracemalloc 测峰值分配，两者结合才能证明「省内存」而不是凭感觉。

```python
import io, shelve, tempfile, os
from collections import Counter

def token_stream(text):
    for line in io.StringIO(text):
        for word in line.split():
            yield word.casefold()

def count_stream(stream):
    c = Counter()
    for token in stream:
        c[token] += 1
    return c

print('stream count', count_stream(token_stream('A a B b a')).most_common())

path = os.path.join(tempfile.gettempdir(), 'depth27.db')
with shelve.open(path) as db:
    db['user:1'] = {'name': 'amy'}
    db['user:2'] = {'name': 'bob'}
    print('shelve keys', sorted(db.keys()))
for suffix in ('', '.db', '.dat', '.dir', '.bak'):
    try:
        os.remove(path + suffix)
    except OSError:
        pass
```

<OutputBox title='对照写法：先自己猜，再点开' output='stream count [(&#39;a&#39;, 3), (&#39;b&#39;, 2)]\nshelve keys [&#39;user:1&#39;, &#39;user:2&#39;]' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import re, string\nfrom collections import Counter\nfrom time import perf_counter\n\nTRANS = str.maketrans(&#39;&#39;, &#39;&#39;, string.punctuation)\n\ndef words(line):\n    cleaned = line.casefold().translate(TRANS)\n    return re.findall(r&#39;[a-z0-9]+&#39;, cleaned)\n\ndef count_lines(lines):\n    counter = Counter()\n    for line in lines:\n        counter.update(words(line))\n    return counter\n\nTEXT = [&#39;Hello, hello!&#39;, &#39;Python 3.13 and python.&#39;, &#39;Guide to the Python.&#39;]\nc = count_lines(TEXT)\nprint(&#39;total tokens&#39;, c.total())\nprint(&#39;hello&#39;, c[&#39;hello&#39;], &#39;python&#39;, c[&#39;python&#39;])\nprint(&#39;top3&#39;, c.most_common(3))\n\nclass MemoryKV:\n    def __init__(self):\n        self._data = {}\n    def get(self, key, default=None):\n        return self._data.get(key, default)\n    def set(self, key, value):\n        self._data[key] = value\n    def delete(self, key):\n        return self._data.pop(key, None) is not None\n    def __len__(self):\n        return len(self._data)\n\nkv = MemoryKV()\nfor cmd in [(&#39;set&#39;, &#39;a&#39;, 1), (&#39;set&#39;, &#39;b&#39;, 2), (&#39;delete&#39;, &#39;a&#39;)]:\n    op = cmd[0]\n    if op == &#39;set&#39;:\n        kv.set(cmd[1], cmd[2])\n    elif op == &#39;delete&#39;:\n        kv.delete(cmd[1])\nprint(&#39;kv state&#39;, kv.get(&#39;a&#39;), kv.get(&#39;b&#39;), len(kv))\n\nt0 = perf_counter()\nbig = count_lines([&#39;w&#39; + str(i) for i in range(2000)])\ncost = perf_counter() - t0\nprint(&#39;bench ran&#39;, big.total() == 2000, cost &gt;= 0)", "note": "文本规整与分词：把噪声挡在统计之前"}, {"label": "对照 / 进阶", "code": "import io, shelve, tempfile, os\nfrom collections import Counter\n\ndef token_stream(text):\n    for line in io.StringIO(text):\n        for word in line.split():\n            yield word.casefold()\n\ndef count_stream(stream):\n    c = Counter()\n    for token in stream:\n        c[token] += 1\n    return c\n\nprint(&#39;stream count&#39;, count_stream(token_stream(&#39;A a B b a&#39;)).most_common())\n\npath = os.path.join(tempfile.gettempdir(), &#39;depth27.db&#39;)\nwith shelve.open(path) as db:\n    db[&#39;user:1&#39;] = {&#39;name&#39;: &#39;amy&#39;}\n    db[&#39;user:2&#39;] = {&#39;name&#39;: &#39;bob&#39;}\n    print(&#39;shelve keys&#39;, sorted(db.keys()))\nfor suffix in (&#39;&#39;, &#39;.db&#39;, &#39;.dat&#39;, &#39;.dir&#39;, &#39;.bak&#39;):\n    try:\n        os.remove(path + suffix)\n    except OSError:\n        pass", "note": "生成器管道与增量统计：内存只与不同词有关"}]' title='两种写法切换看' />


## IO 与内存策略：逐行迭代而不是全量载入

**IO 与内存策略**

| 策略 | 内存 | 适用 |
| --- | --- | --- |
| read() 全量读入再 split | O(文件大小) | 小文件、需要随机访问 |
| 逐行迭代 for line in file | O(单行) | 大文件、日志流 |
| 生成器管道加增量 Counter | O(不同词数) | 远超内存的数据，只保留计数 |
| list 物化中间结果 | O(元素数) | 需要多次遍历或按下标访问 |
| tracemalloc 峰值观测 | 额外开销小 | 验证惰性管道是否真的省内存 |

```python
import sys, io, tracemalloc
from collections import Counter

text = 'word ' * 2000
materialized = [w for line in io.StringIO(text) for w in line.split()]
stream = (w for line in io.StringIO(text) for w in line.split())
print('list much larger than gen', sys.getsizeof(materialized) > sys.getsizeof(stream) * 10)
print('same counts', Counter(materialized) == Counter(stream))

tracemalloc.start()
lazy = Counter()
for line in io.StringIO(text):
    for w in line.split():
        lazy[w] += 1
peak = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print('incremental total', lazy.total(), 'peak positive', peak > 0)
```

<OutputBox title='原理验证' output='list much larger than gen True\nsame counts True\nincremental total 2000 peak positive True' />

把统计逻辑与 IO 分开，核心是一个接受任意可迭代对象的纯函数：它逐行取数据、用生成器把去标点、转小写、分词串成惰性管道，再用 `Counter.update` 增量累计，内存只与不同词的数量有关，而不是文件字节数。

CPython 里 `for line in file` 由 TextIOWrapper 逐行缓冲，一次只在内存里放一行；

生成器表达式更进一步，把中间结果也省掉，每个 token 产出后立刻被消费。

`casefold()`（3.3+）比 `lower()` 更彻底（如德语 ß 变成 ss），`str.translate` 配 `str.maketrans()` 在 C 层做字符映射。

Counter 的 `most_common()` 内部用 `heapq.nlargest()`，大数据下比 `sorted()` 全表更省。

KV 层定义 get / set / delete 三个窄方法：内存版用 dict，持久化版换 shelve（值必须可 pickle）或 sqlite3，业务代码完全不用改；

命令分发把输入解析成 `(op, key, value)` 元组后走分发表，新命令只增不改。

基准用 `time.perf_counter` 测墙钟、tracemalloc 测峰值分配，两者才能证明省内存而不是凭感觉。


## KV 窄接口、持久化与可替换实现

内存版 KV 只需暴露 get / set / delete 三个操作：dict 实现最快、进程内、重启即丢，适合测试与短期缓存；把业务代码直接绑在 dict 上，后面换持久化就要改十几个调用点。定义窄接口后，实现可以无痛替换：shelve 是标准库的 dbm 键值存储，值必须可 pickle，接口与 dict 几乎一致；

sqlite3 提供事务与查询；redis 提供跨进程共享与过期淘汰能力。

命令分发把 `(op, key, value)` 映射到接口调用，业务层不知道底层是内存还是磁盘，测试用内存版跑同一组断言、生产注入持久化版即可。

可观测性也要跟上：统计 total 与不同词数、记录处理行数与耗时、对异常行做计数而不是静默跳过。持久化版本还要考虑序列化成本、连接生命周期与并发写，这些属于实现细节，不应渗进业务接口。把「统计与 IO 分离、存储与业务分离」两条边界守住，后面接网络层、分片层都只是换一个实现类。


### 为什么 dict 不该直接暴露给业务代码

**KV 接口与可替换实现**

| 接口 / 实现 | 特点 | 替换成本 |
| --- | --- | --- |
| get / set / delete 窄接口 | 只暴露三个操作，调用方不依赖底层 | 换成网络层、分片层不改业务代码 |
| dict 内存实现 | 最快、进程内、重启即丢 | 测试用它，生产换持久化 |
| shelve 持久化 | 标准库 dbm 键值存储，值需可 pickle | 接口一致，直接替换 |
| sqlite3 / redis | 事务、查询或跨进程共享 | 实现同一接口即可 |
| 命令分发 (op, key, value) | 把输入解析与存储解耦 | 加新命令只改分发表 |

<Term word='文本规整与分词' text='词频看起来只是 split 一下，实际要先把噪声挡掉才有意义。大小写归一用 `str.casefold()`（3.3+）而不是 `lower()`：casefold 专为 Unicode 无大小写比较设计，能把德语 ß 折成 ss、把连字与带点 I 归一，lower 只做简单映射，跨语言文本会漏词。去标点用 `str.' />

<Term word='Counter 与排序' text='把「去标点 → 转小写 → 分词 → 计数」每一步写成生成器表达式或小的生成器函数，再用 `yield from` 串成惰性管道，只有最终 Counter 或聚合才真正消费。CPython 里 `for line in file` 由 TextIOWrapper 逐行缓冲，一次只在内存里放一行；生成器表达式更进一步，连' />


## 可测的词频 CLI：核心纯函数、生成器管道与可替换 KV

把词频工具拆成三层：tokenize 只做文本规整与分词、count_stream 对任意可迭代行做增量统计、MemoryKV 提供 get / set / delete 窄接口缓存结果。核心函数只接受可迭代对象，测试时传 list、生产时传文件或标准输入都不用改，也不必造临时文件。

命令分发把 `(op, key, value)` 元组映射到 KV 操作，新增命令只改分发表。

整个工具没有把整份文本物化，内存只与不同词的数量有关；用 `io.StringIO` 模拟文件即可端到端验证。重点是统计与 IO 分离、存储与业务分离这两条边界，以及每一步都留可自动化的测试入口，而不是把逻辑堆在一个函数里。

```python
import io, re, string
from collections import Counter

TRANS = str.maketrans('', '', string.punctuation)

def tokenize(lines):
    for line in lines:
        cleaned = line.casefold().translate(TRANS)
        yield from re.findall(r'[a-z0-9]+', cleaned)

def count_stream(lines):
    counter = Counter()
    for token in tokenize(lines):
        counter[token] += 1
    return counter

class MemoryKV:
    def __init__(self): self._data = {}
    def get(self, k, default=None): return self._data.get(k, default)
    def set(self, k, v): self._data[k] = v
    def delete(self, k): return self._data.pop(k, None) is not None

def dispatch(kv, cmd):
    op, k, v = cmd
    if op == 'set': kv.set(k, v)
    elif op == 'delete': kv.delete(k)
    return kv.get(k)

kv = MemoryKV()
doc = io.StringIO('Hello, hello!' + chr(10) + 'Python and python.' + chr(10) + 'Guide to Python.')
counts = count_stream(doc)
dispatch(kv, ('set', 'top', counts.most_common(2)))
dispatch(kv, ('delete', 'missing', None))
print('top', kv.get('top'), 'missing', kv.get('missing'))
print('total', counts.total(), 'hello', counts['hello'], 'python', counts['python'])
```

<Callout type="idea" title='落地提示' text='为 KV 定义 get / set / delete 的窄接口，后面网络层、持久化层、分片层都可以无痛替换实现' />

<CheckList id='P027b' title='上线前自检' :items='["能复现并解释「一次性把所有行 read() 进 list 做词频，文件一大」", "能复现并解释「用 lower() 做大小写归一，非 ASCII 文本统计对」", "能复现并解释「把 KV 的 dict 直接暴露给业务代码，后面加持久化要全」", "能用一条命令验证 文本规整与分词", "关键路径有自动化测试与失败分支"]' />

```bash
python -m timeit -n 1000 "sum(range(100))"
```

把输入换成你自己的数据，观察结果是否仍符合 文本规整与分词 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 失败模式、基准测量与交付自检

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 一次性把所有行 read() 进 list 做词频，文件一大就 OOM | 物化整份文本与中间词列表，内存随数据量线性增长 | 逐行迭代文件对象、用生成器管道边读边累计 Counter，只保留不同词的计数 |
| 用 lower() 做大小写归一，非 ASCII 文本统计对不上 | lower() 对德语 ß、土耳其语带点 I 等 Unicode 大小写折叠不完整 | 用 str.casefold()（3.3+）做无大小写比较；分词后再统一 |
| 把 KV 的 dict 直接暴露给业务代码，后面加持久化要全改 | 业务与具体存储耦合，缺少稳定的窄接口 | 定义 get / set / delete 接口，内存版用 dict 实现，生产替换为 shelve / sqlite3 / redis |

<Callout type="warn" title='本讲最容易踩的坑' text='一次性把所有行 read() 进 list 做词频，文件一大就 OOM：物化整份文本与中间词列表，内存随数据量线性增长' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：一次性把所有行 read() 进 list ", "body": "物化整份文本与中间词列表，内存随数据量线性增长", "tip": "逐行迭代文件对象、用生成器管道边读边累计 Counter，只保留不同词的计数"}, {"title": "第 2 步：用 lower() 做大小写归一，非 ASC", "body": "lower() 对德语 ß、土耳其语带点 I 等 Unicode 大小写折叠不完整", "tip": "用 str.casefold()（3.3+）做无大小写比较；分词后再统一"}, {"title": "第 3 步：把 KV 的 dict 直接暴露给业务代码，", "body": "业务与具体存储耦合，缺少稳定的窄接口", "tip": "定义 get / set / delete 接口，内存版用 dict 实现，生产替换为 shelve / sqlite3 / redis"}]' />


## 练习题与验收

<Exercise title='基础：写一个不物化全量数据的词频函数' task='实现 count_stream(lines)，逐行迭代、用生成器分词、用 Counter 增量累计；用 io.StringIO 验证结果与一次性 list 版本一致。' solution='import io, re\nfrom collections import Counter\n\ndef count_stream(lines):\n    c = Counter()\n    for line in lines:\n        for w in re.findall(r&#39;[a-z]+&#39;, line.casefold()):\n            c[w] += 1\n    return c\n\ntext = &#39;A a B b a&#39;\nprint(&#39;stream&#39;, count_stream(io.StringIO(text)).most_common())\nprint(&#39;list version&#39;, count_stream(text.split()).most_common())' explain='核心只依赖可迭代对象，io.StringIO 与 list 都能喂进去，测试不必造临时文件；逐行迭代加增量累计让内存只与不同词数量有关。' />

<Exercise title='进阶：给 KV 抽象加一个持久化实现并共用同一组测试' task='定义 get / set / delete 窄接口，分别用 dict 与 shelve 实现；写一组不依赖具体实现的断言，两个实现都跑一遍，说明替换成本。' solution='import shelve, tempfile, os\n\nclass DictKV:\n    def __init__(self): self.d = {}\n    def get(self, k): return self.d.get(k)\n    def set(self, k, v): self.d[k] = v\n    def delete(self, k): return self.d.pop(k, None) is not None\n\nclass ShelveKV:\n    def __init__(self, path): self.db = shelve.open(path)\n    def get(self, k): return self.db.get(k)\n    def set(self, k, v): self.db[k] = v\n    def delete(self, k): return self.db.pop(k, None) is not None\n    def close(self): self.db.close()\n\ndef exercise(kv):\n    kv.set(&#39;k&#39;, 7)\n    assert kv.get(&#39;k&#39;) == 7\n    kv.delete(&#39;k&#39;)\n    assert kv.get(&#39;k&#39;) is None\n    return &#39;ok&#39;\n\nprint(&#39;dict&#39;, exercise(DictKV()))\np = os.path.join(tempfile.gettempdir(), &#39;depth27ex.db&#39;)\ns = ShelveKV(p)\nprint(&#39;shelve&#39;, exercise(s))\ns.close()\nfor suffix in (&#39;&#39;, &#39;.db&#39;, &#39;.dat&#39;, &#39;.dir&#39;, &#39;.bak&#39;):\n    try:\n        os.remove(p + suffix)\n    except OSError:\n        pass' explain='两个实现遵守同一组 get / set / delete，exercise 只依赖接口，换持久化不改测试；shelve 的值要可 pickle，dict 版进程内最快、重启即丢。' />

<Quiz no='027-1' q='为什么大文件词频不该用 read() 全量读入再统计？' :options='["因为 read() 更慢但内存一样", "因为物化整份文本与中间词列表，内存随文件大小线性增长，容易 OOM", "因为 Counter 不支持大数", "因为 split() 有长度上限"]' answer="1" explain='逐行迭代文件对象一次只在内存放一行，配生成器管道与增量 Counter，内存只与不同词数量有关；全量 read() 会把整份文本与词列表都物化。' />

<Quiz no='027-2' q='做 Unicode 无大小写归一，哪个方法更彻底？' :options='["str.lower()", "str.casefold()（3.3+）", "str.upper()", "str.swapcase()"]' answer="1" explain='casefold 专为无大小写比较设计，能把德语 ß 折成 ss 等；lower 只做简单小写映射，跨语言统计会漏词。' />

<Quiz no='027-3' q='为 KV 定义 get / set / delete 窄接口的主要收益是？' :options='["让 dict 变快", "业务代码不依赖具体存储，后面换 shelve / sqlite3 / redis 只改实现", "自动支持事务", "省掉所有测试"]' answer="1" explain='窄接口把存储与业务解耦，测试可跑内存版、生产换持久化实现；持久化本身还需处理序列化与连接管理。' />

<Predict no='027-4' q='c = Counter(); c.update(&#39;aab&#39;); c.update([&#39;a&#39;]); print(c[&#39;a&#39;], c.total()) 输出什么？' :options='["2 3", "3 4", "3 5"]' answer='1' output='3 4' explain='&#39;aab&#39; 让 a 为 2、b 为 1；Counter.update 是累加，再加一个 a 得 3；total() 返回所有计数之和 3 + 1 = 4。若误把 update 当覆盖会得到 1。' />

<FillBlank no='027-5' tpl='___ re, string' :answers='["import"]' hint='回想本讲关于 文本规整与分词 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 文本规整与分词：把噪声挡在统计之前 的落点。' />

<KnowledgeCard :points='["词频管道：casefold / translate 规整、生成器分词、Counter 增量累计，统计与 IO 分离", "核心函数只接受可迭代对象，测试传 list、生产传文件或标准输入，不必造临时文件", "逐行迭代加生成器管道让内存只与不同词数量有关；read() 全量会随文件大小线性增长", "casefold()（3.3+）比 lower() 更适合 Unicode 无大小写归一；top-N 用 most_common 或 heapq.nlargest", "KV 定义 get / set / delete 窄接口，dict 内存版可无痛替换为 shelve / sqlite3 / redis", "命令分发把 (op, key, value) 映射到接口调用；基准用 perf_counter 测耗时、tracemalloc 测峰值内存"]' :pitfalls='["一次性把所有行 read() 进 list 做词频，文件一大就 OOM", "用 lower() 做大小写归一，非 ASCII 文本统计对不上", "把 KV 的 dict 直接暴露给业务代码，后面加持久化要全改", "一次性把所有行读进 list 做统计，文件一大就 OOM；应逐行迭代、增量累计"]' summary='把统计逻辑与 IO 分开，同一套核心既能读文件也能读标准输入，测试时才不必造临时文件' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 词频管道：casefold / translate 规整、生成器分词、Counter 增量累计，统计与 IO 分离 | 建立直觉 |
| 核心函数只接受可迭代对象，测试传 list、生产传文件或标准输入，不必造临时文件 | 跑通示例 |
| 逐行迭代加生成器管道让内存只与不同词数量有关；read() 全量会随文件大小线性增长 | 深入边界 |
| casefold()（3.3+）比 lower() 更适合 Unicode 无大小写归一；top-N 用 most_common 或 heapq.nlargest | 工程落地 |
| KV 定义 get / set / delete 窄接口，dict 内存版可无痛替换为 shelve / sqlite3 / redis | 随堂检测 |
| 命令分发把 (op, key, value) 映射到接口调用；基准用 perf_counter 测耗时、tracemalloc 测峰值内存 | 复盘 |

1. 词频管道：casefold / translate 规整、生成器分词、Counter 增量累计，统计与 IO 分离

2. 核心函数只接受可迭代对象，测试传 list、生产传文件或标准输入，不必造临时文件

3. 逐行迭代加生成器管道让内存只与不同词数量有关；read() 全量会随文件大小线性增长

[下一讲：函数定义与参数形态](/functions/function-basics)
