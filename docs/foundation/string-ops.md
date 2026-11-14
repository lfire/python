---
title: 第 010 讲 · 字符串操作：切片、f-string 与常用方法
description: 熟练处理文本清洗与格式化输出
---

<StageHeader stage='L1 · 编程地基' level='★☆☆☆☆' time='30 分钟' goal='熟练处理文本清洗与格式化输出' prereq='第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义' />

# 第 010 讲 · 字符串操作：切片、f-string 与常用方法

边界划清，文本稳稳拿在手里了。这一讲只把字符串操作练熟：截一段、把字段拼成句、给报表排版。都是写脚本天天要做的零碎活，做得顺手，效率差别很大。拿日志举例：想取中间几个字符，下标一多就晕；想把数字按千分位对齐，手动补空格既累又难改；把一批词拼成句若在循环里 +=，数据一多就变慢。我们先摸清索引与切片的规矩，包括越界不报错、负步长怎样改边界；再用 f-string 一次成型；最后比 join 与循环拼接，认清 split、partition、strip 各管哪段。带着第 9 讲的不可变印象就够；学完常见文本清洗你能写得又快又干净。


## 切片越界不报错、拼接大量字符串突然变慢

一个日志脚本用循环把十万条记录拼成一行：`text += line`，跑起来内存涨、耗时比预期长一个量级；换成空串 join 之后立刻快下来，却没人说得清差在哪。另一处解析文件名时写 `name[5:20]`，源串只有 8 个字符，程序却没报错，静默返回了短一截的结果，下游按固定长度切字段全乱了；

还有人用 `s[::-1]` 反转后按正向下标取元素，边界含义完全变了却以为对称。报表里拼数字用字符串相加，对齐靠手工补空格，改个宽度就要重排一整列。朴素解法是「多写几个加号和切片就行」，它失败在没意识到字符串不可变：每次 += 都可能产生新对象并复制旧内容，大量拼接是平方级开销；

切片越界也被设计成静默裁剪，错误不会在出错点暴露。本讲把索引切片规则、f-string 格式规范、join 的性能依据、split/partition/strip 的行为讲清，让文本处理既快又不会静默出错。


## 索引与切片：越界不报错、负步长改变边界

str 是不可变的码点序列，`s[i]` 取单字符，负索引从末尾算（`s[-1]` 是最后一个字符）。

切片 `s[start:stop:step]` 遵循三条规则：start 缺省为 0（step 为负时缺省为末尾）、stop 缺省为长度（step 为负时缺省为开头之前）、step 缺省为 1 且不能为 0（抛 ValueError，提示切片步长不能为 0）。

最关键的是越界不报错：`s[2:99]` 在长度 6 的串上返回 `s[2:]`，`s[-100:3]` 把 start 夹到 0，静默裁剪而非抛 IndexError——但单下标 `s[99]` 会抛 IndexError，提示 string index out of range，二者行为不同。

step 为负时方向反转：`s[::-1]` 得到倒序串，此时 start 应大于 stop 才有内容，`s[5:1:-1]` 从下标 5 取到 2，写成 `s[1:5:-1]` 得到空串。切片总是返回新对象（哪怕 `s[:]` 也不是原对象），因为 str 不可变、任何「修改」都得新建。

边界信号：解析结果比预期短却没有任何异常，八成是切片越界被静默夹断，应显式检查 `len(s)` 或用 partition 按分隔符取，而不是赌下标范围。

```python
s = 'Python'
print('index', s[0], s[-1])
print('slice', s[1:4], s[::-1])
print('out_of_range', s[2:99])
print('align', repr(f'{42:>6d}'))
print('precision', repr(f'{3.14159:.2f}'))
print('thousands', repr(f'{1234567:,d}'))
print('split', 'a,b,c'.split(','))
print('partition', 'k=v'.partition('='))
print('strip', '  x  '.strip())
```

<OutputBox title='主示例运行结果' output='index P n\nslice yth nohtyP\nout_of_range thon\nalign &#39;    42&#39;\nprecision &#39;3.14&#39;\nthousands &#39;1,234,567&#39;\nsplit [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;]\npartition (&#39;k&#39;, &#39;=&#39;, &#39;v&#39;)\nstrip x' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='s = &#39;Python&#39;\nprint(&#39;index&#39;, s[0], s[-1])\nprint(&#39;slice&#39;, s[1:4], s[::-1])\nprint(&#39;out_of_range&#39;, s[2:99])\nprint(&#39;align&#39;, repr(f&#39;{42:&gt;6d}&#39;))\nprint(&#39;precision&#39;, repr(f&#39;{3.14159:.2f}&#39;))\nprint(&#39;thousands&#39;, repr(f&#39;{1234567:,d}&#39;))\nprint(&#39;split&#39;, &#39;a,b,c&#39;.split(&#39;,&#39;))\nprint(&#39;partition&#39;, &#39;k=v&#39;.partition(&#39;=&#39;))\nprint(&#39;strip&#39;, &#39;  x  &#39;.strip())' :notes='["s 是不可变的码点序列，长度 6", "s[0] 取首字符 P，s[-1] 负索引取末字符 n", "s[1:4] 左闭右开得 yth，s[::-1] 负步长反转得 nohtyP", "stop 越界不报错，被夹到长度，等价于 s[2:] 得 thon", "f-string 右对齐宽 6，用 repr 显示前导空格", "格式规范 .2f 保留两位小数得 3.14", "格式规范 ,d 加千分位得 1,234,567", "split 按逗号切成含三个元素的 list", "partition 只切一次，返回含分隔符的三元组", "strip 默认去掉首尾空白，得到 x"]' title='第 010 讲 · 字符串操作：切片、f-string 与常用方法' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**切片规则与边界（s='Python'）**

| 写法 | 结果 | 要点 |
| --- | --- | --- |
| s[0], s[-1] | P, n | 负索引从末尾算 |
| s[1:4] | yth | 左闭右开 |
| s[2:99] | thon | stop 越界静默夹到长度 |
| s[::-1] | nohtyP | step 为负时方向反转 |
| s[1:5:-1] | 空串 | 负步长要求 start 大于 stop |
| s[99] | 抛 IndexError | 单下标越界与切片不同 |


### s[::-1] 为什么能反转

```python
import timeit

def plus_loop(parts):
    s = ''
    for p in parts:
        s += p
    return s

def use_join(parts):
    return ''.join(parts)

parts = ['word'] * 500
t_plus = timeit.timeit(lambda: plus_loop(parts), number=200)
t_join = timeit.timeit(lambda: use_join(parts), number=200)
print('same_result', plus_loop(parts) == use_join(parts))
print('join_faster', t_join < t_plus)
print('rsplit', 'a.b.c'.rsplit('.', 1))
print('splitlines', len(('a' + chr(10) + 'b').splitlines()))
```

<OutputBox title='对照写法：先自己猜，再点开' output='same_result True\njoin_faster True\nrsplit [&#39;a.b&#39;, &#39;c&#39;]\nsplitlines 2' guess="true" />


## f-string 与格式规范：对齐、精度、千分位一次成型

f-string（3.6 起）在编译期把表达式与格式规范编成 `BUILD_STRING` 与 `FORMAT_VALUE` 指令，比 % 格式化和 `str.format` 都快，且表达式直接写在花括号里可读性好。

格式规范跟在冒号后：`f'{42:>6d}'` 右对齐宽 6 得带四个空格的 42，`f'{3.14159:.2f}'` 保留两位得 3.14，`f'{1234567:,d}'` 加千分位得 1,234,567；

对齐符 <、>、^ 分别对应左、右、居中，宽度前加填充字符可写成 `f'{7:0>3d}'` 得 007。3.8 起 `f'{x=}'` 会连变量名一起打印（调试用），3.12 起放宽了花括号内引号与嵌套的限制（PEP 701），可以在 f-string 里复用同种引号、写多行表达式。

字符串方法里 join 负责拼接：空串 join 先算总长度一次分配内存，属于线性；循环 += 因不可变要反复复制，数据量大时是平方级，这是性能差一个量级的根因。`split(sep)` 按分隔符切成 list，`split(None)` 按任意空白切；

`partition(sep)` 只切一次、返回 (前, 分隔符, 后) 三元组且找不到时后两段为空，适合解析 `key=value`；`strip()` 默认去首尾空白，传参数则按字符集合去除，不是按子串。


## 不可变与方法选型：把清洗管道写对

str 的方法都不会原地修改，全部返回新对象：upper、replace、strip、split 皆然，因此链式调用 `s.strip().lower().replace(...)` 每次都产生中间串，数据极大时要考虑生成器或逐段处理。

常用方法要按语义选：startswith 与 endswith 接受元组做多前缀匹配；find 返回下标、找不到给 -1，而 index 找不到抛 ValueError，别混用；count 数非重叠出现次数；`splitlines()` 按各类换行边界切分且默认不带行尾符，比手动按 `chr(10)` 切稳健；

join 只接受元素全为 str 的可迭代对象，混入 int 会抛 TypeError，需先 `map(str, ...)`。正则初识放在 re 模块：`re.split`、`re.sub`、`re.findall` 处理模式化文本，但简单分隔用 str 方法更快更可读；

写正则模式时用 raw 字符串前缀 r 避免反斜杠被当作转义。格式化输出优先 f-string 加格式规范，日志与报表里的对齐、精度、千分位都由规范一次完成，不要手工拼空格。判断两个清洗结果是否一致用 ==，切片与拼接产生的新对象用 is 比较没有意义。

CPython 用 PEP 393 的紧凑定宽数组存 str，且对象不可变——底层字符缓冲一旦写入就不允许改。于是 `s + t` 必须新建一段足够长的缓冲区并把两边内容复制进去，循环里 k 次 += 的总复制量约为 1 加 2 一直加到 k，呈平方级；

空串 join 先用 PyUnicode_Join 遍历一次算出总长度、一次性分配、逐段 memcpy，整体线性，这就是性能差一个量级的来源（CPython 对局部变量的 += 有原地优化，但只在无其他引用时生效，不能依赖）。

切片由 PyUnicode_Substring 实现：先把 start 与 stop 按长度和 step 符号夹到合法区间，越界时静默 clamp 而非报错，再按定宽字节拷贝出一段新对象。

f-string 在编译期生成 `FORMAT_VALUE` 指令，运行时调用对应类型的 `__format__(spec)`，格式规范里的对齐、精度、千分位都由该方法解析。

理解「不可变加定宽存储」，就能推出拼接要 join、切片必是新对象、越界被夹断这些结论。

<ConceptDiagram type='flow3' title='第 010 讲 · 索引与切片：越界不报错、负步长改变边界' labels='索引与切片：越界不报错、负步长改变边界|f-string 与格式规范：对齐、精度、千…|不可变与方法选型：把清洗管道写对' caption='熟练处理文本清洗与格式化输出' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 监控报表：用格式规范与一次 join 生成对齐行

一个监控脚本要把事件按级别、名称、耗时、计数打成对齐的表格行，早期用字符串相加手工补空格，改列宽就要重排，还在循环里 += 拼十万行导致内存与耗时都失控。

下面这段给出工程写法：用 f-string 的格式规范一次完成左对齐、右对齐、两位小数与千分位，用 join 把列拼成行、再用一次 join 把所有行合成输出，用 partition 解析 `key=value` 型事件，用 splitlines 统计行数。

全程只在最后做一次拼接，中间用列表收集，既快又能在列宽变化时只改一处格式规范。真实系统还会把行写进 logging 而不是 print，但格式化与拼接的原则不变。

```python
def fmt_row(level, name, ms, count):
    cells = [
        f'{level:<8s}',
        f'{name:<12s}',
        f'{ms:>8.2f}',
        f'{count:>10,d}',
    ]
    return ''.join(cells)

def parse_event(line):
    key, sep, value = line.partition('=')
    return key, value if sep else ''

rows = [
    fmt_row('INFO', 'fetch', 12.5, 1234567),
    fmt_row('WARN', 'retry', 3.5, 890),
    fmt_row('ERROR', 'timeout', 250.0, 42),
]
out = chr(10).join(rows)
print('lines', len(out.splitlines()))
print('width', len(rows[0]))
key, value = parse_event('status=ok')
print('key', key, 'value', value)
print('has_count', '1,234,567' in rows[0])
print('aligned', rows[0].startswith('INFO'))
```

<Callout type="idea" title='落地提示' text='日志与报表优先用 f-string 加格式规范（对齐、精度、千分位），既快又可读' />


## 清洗管道错因与文本速记

<Exercise title='基础：用 f-string 格式化报表' task='打印 f&#39;{42:&gt;6d}&#39;、f&#39;{3.14159:.2f}&#39;、f&#39;{1234567:,d}&#39; 的 repr，再写一行把两个字段拼成对齐串。' solution='print(repr(f&#39;{42:&gt;6d}&#39;))\nprint(repr(f&#39;{3.14159:.2f}&#39;))\nprint(repr(f&#39;{1234567:,d}&#39;))\nname = &#39;a&#39;\nprint(&#39;&#39;.join([f&#39;{name:&lt;4s}&#39;, f&#39;{7:0&gt;3d}&#39;]))' explain='格式规范由各类型的 __format__ 解析；join 把多个定宽字段拼成一行，比手工补空格更稳，改宽度只动一处规范。' />

<Exercise title='进阶：量化 join 与 += 的差距' task='用 timeit 分别测循环 += 与空串 join 拼接 500 个单词的耗时，打印两者是否都大于 0 以及 join 是否更快，并解释不可变带来的复制成本。' solution='import timeit\ndef plus_loop(parts):\n    s = &#39;&#39;\n    for p in parts: s += p\n    return s\ndef use_join(parts):\n    return &#39;&#39;.join(parts)\nparts = [&#39;word&#39;] * 500\na = timeit.timeit(lambda: plus_loop(parts), number=200)\nb = timeit.timeit(lambda: use_join(parts), number=200)\nprint(&#39;both_positive&#39;, a &gt; 0 and b &gt; 0)\nprint(&#39;join_faster&#39;, b &lt; a)' explain='循环 += 每次复制已累积内容，总复制量随次数平方增长；join 一次分配总长度线性拷贝，单词越多差距越明显。' />

<Quiz no='010-1' q='&#39;Python&#39;[2:99] 的结果是？' :options='["&#39;thon&#39;，stop 越界被静默夹到长度", "抛 IndexError", "&#39;thon&#39; 再补空格到 99", "空串"]' answer="0" explain='切片会把越界的 stop 夹到 len(s)，等价于 s[2:]；单下标 s[99] 才会抛 IndexError，两者行为不同。' />

<Quiz no='010-2' q='大量字符串拼接首选哪种写法？' :options='["空串 join(parts)，一次分配总长度为线性", "循环 s += p，解释器总会原地优化", "用 % 格式化", "先转成 bytes 再拼"]' answer="0" explain='str 不可变导致循环 += 反复复制旧串；join 先算总长一次分配。局部变量的原地优化只在无其他引用时生效，不能依赖。' />

<Quiz no='010-3' q='partition(&#39;=&#39;) 与 split(&#39;=&#39;) 的差别是？' :options='["partition 只切一次并返回含分隔符的三元组，split 切成 list", "两者完全一样", "partition 返回 list", "split 只切一次"]' answer="0" explain='partition 返回 (前, 分隔符, 后) 且找不到时后两段为空，适合解析 key=value；split 会按所有分隔符切成多段 list。' />

<Predict no='010-4' q='主示例里 print(&#39;slice&#39;, s[1:4], s[::-1])（s=&#39;Python&#39;）输出什么？' :options='["slice yth nohtyP", "slice yth nohty", "slice Pyt nohtyP"]' answer='0' output='slice yth nohtyP' explain='s[1:4] 左闭右开取下标 1、2、3 得 yth；s[::-1] 以 -1 步长反转整个串得 nohtyP。两处都未越界，不涉及夹断。' />

<FillBlank no='010-5' tpl='___ = &#39;Python&#39;' :answers='["s"]' hint='回想本讲关于 索引与切片规则 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 索引与切片：越界不报错、负步长改变边界 的落点。' />

<KnowledgeCard :points='["str 不可变：拼接、切片、方法都返回新对象；循环 += 是平方级，空串 join 一次分配是线性", "切片 s[start:stop:step] 越界静默夹到边界；单下标越界抛 IndexError；step 为负时 start 应大于 stop", "f-string（3.6 起，3.12 PEP 701 放宽引号）用 :&gt;6d、:.2f、:,d 完成对齐、精度、千分位", "partition 只切一次返回三元组，split 按分隔符切 list，rsplit(sep, 1) 只切最后一次", "strip 参数按字符集合去首尾而非子串；find 返回 -1、index 找不到抛 ValueError", "日志与报表用 f-string 格式规范一次成型，不要手工拼空格；元素非 str 时先 map(str, parts)"]' :pitfalls='["循环里用 += 拼接大量字符串", "依赖切片越界报错，或按正向直觉写负步长切片", "把 partition 当 split、把 strip 参数当子串", "切片越界不报错、步长为负时边界含义变化，是文本处理里最容易写错的地方"]' summary='字符串不可变，所以每次拼接都可能产生新对象；join 一次成型比循环 += 在大量数据时快一个量级' />

1. str 不可变：拼接、切片、方法都返回新对象；循环 += 是平方级，空串 join 一次分配是线性

2. 切片 s[start:stop:step] 越界静默夹到边界；单下标越界抛 IndexError；step 为负时 start 应大于 stop

3. f-string（3.6 起，3.12 PEP 701 放宽引号）用 :>6d、:.2f、:,d 完成对齐、精度、千分位

[下一讲：运算符与表达式：优先级、短路与真值](/foundation/operators)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/010-string-ops.py`

```bash
python3 examples/lessons/010-string-ops.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/010-string-ops.py) · [全部示例代码索引](/examples/)
