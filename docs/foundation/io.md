---
title: 第 014 讲 · 输入输出与文件初识：print、input、open、with
description: 完成程序与外界的第一批数据交换
---

<StageHeader stage='L1 · 编程地基' level='★☆☆☆☆' time='25 分钟' goal='完成程序与外界的第一批数据交换' prereq='第 013 讲 · 循环：for / while、range 与循环 else' />

# 第 014 讲 · 输入输出与文件初识：print、input、open、with

会算、会判断、会重复，可程序还关在内存里，结果只停在屏幕上。好用的脚本总要和外面打交道：读配置、写结果、留日志。看似只是几个函数，却藏着不少安静的坑。

比如读中文配置换个系统就乱了；调试信息和数据都打向屏幕，下游一接混作一团；大日志一次读进内存当场吃紧；处理到一半出错，文件还开着没关。先看 `print` 的 `sep`、`end`、`file`，把日志和数据分流；再讲 `open` 的模式与显式编码，用 `pathlib` 拼路径；最后落到 `with`——中途抛错也保证关闭，以及 `input` 怎么稳妥转成数字。有变量、字符串与一点异常印象；学完你能让脚本可靠读写文件。


## 同一份代码在 Windows 与 Linux 读出不同中文

一个导出脚本在 macOS 上跑得好好的，迁到 Windows 容器后读出的中文配置全乱——代码里是 `open(path)`，没写 `encoding`，两边平台的默认编码不一样。另一处把调试信息全用 `print` 打到 `stdout`，下游用管道接这个脚本时，日志和真正的 `CSV` 数据混在一起，解析直接崩；

还有人用 `f.read()` 一次把几百 MB 的日志读进内存，容器 `OOM` 被杀。

更隐蔽的是异常路径：文件打开后处理到一半抛错，没关的文件描述符一直占着，跑久了报 `too many open files`。

「在 `finally` 里关一下」或「把 `print` 换成别的」都只治了一半：手写的 `try/finally` 容易漏分支，`print` 也没有级别和输出目标。

本讲把 `print` 的 `sep`/`end`/`file`、`open` 的模式与编码、`with` 的上下文协议、`pathlib` 与逐行迭代讲清，让程序与外界的交换既安全又可测。


## print 的参数与输出目标：sep / end / file / flush

`print` 的完整签名里，`sep` 默认一个空格，`end` 默认是换行符（值等于 `chr(10)`），`file` 缺省 `sys.stdout`，`flush` 默认 `False`，行缓冲还是块缓冲由流自己决定。它把每个对象转成 `str` 后用 `sep` 连接、末尾追加 `end`，再写到 `file`。

给 `file` 传 `io.StringIO` 就能把输出收进内存做断言，给 `sys.stderr` 则把日志与正常数据分流——管道场景下这一步非做不可，否则调试信息和数据挤在同一条 `stdout` 里会污染下游。

`print` 返回 `None`，而且只是「写文本流」的一层封装，真正决定编码的是流本身：`sys.stdout` 的 `encoding` 受环境与 `PYTHONIOENCODING` 影响，3.7 起还能用 `sys.stdout.reconfigure` 把编码直接设成 `'utf-8'`。

需要不换行就把 `end` 设为空串；需要把换行符当值参与拼接时用 `chr(10)`，别在字面量里堆转义序列。

重定向既可以用 `print(..., file=f)`，也可以用 `contextlib.redirect_stdout(buf)` 临时替换 `sys.stdout`，用完再换回。

工程上日志应交给 `logging`（带级别、时间戳、`Handler`），`print` 只留给人看的命令行输出。

```python
import io
buf = io.StringIO()
print('a', 'b', 'c', sep='|', end='.', file=buf)
print('captured', repr(buf.getvalue()))
print('sep', repr('|'.join(['x', 'y'])))
print('end_default', repr('line'))
```

<OutputBox title='主示例运行结果' output='captured &#39;a|b|c.&#39;\nsep &#39;x|y&#39;\nend_default &#39;line&#39;' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import io\nbuf = io.StringIO()\nprint(&#39;a&#39;, &#39;b&#39;, &#39;c&#39;, sep=&#39;|&#39;, end=&#39;.&#39;, file=buf)\nprint(&#39;captured&#39;, repr(buf.getvalue()))\nprint(&#39;sep&#39;, repr(&#39;|&#39;.join([&#39;x&#39;, &#39;y&#39;])))\nprint(&#39;end_default&#39;, repr(&#39;line&#39;))' :notes='["导入 io 以创建内存文本流 StringIO", "buf 作为输出目标，替代默认 sys.stdout", "sep 用竖线连接三个对象、end 用句点替代默认换行，写入 buf", "buf.getvalue() 得到 a|b|c. 六个字符，repr 显示带引号", "演示 join 得到 x|y，与 sep 的拼接语义一致", "单独一个字符串用 repr 打印，显示引号而不含转义"]' title='第 014 讲 · 输入输出与文件初识：print、input、open、with' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**print 常用参数**

| 参数 | 默认值 | 作用 |
| --- | --- | --- |
| sep | 一个空格 | 连接多个对象 |
| end | 换行符 chr(10) | 末尾追加，设空串则不换行 |
| file | sys.stdout | 可传 StringIO 或 sys.stderr 分流 |
| flush | False | 是否立即刷出缓冲区 |


## 把日志从 stdout 分流到 stderr

```python
import tempfile, pathlib
with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / 'note.txt'
    p.write_text('hello' + chr(10) + 'world', encoding='utf-8')
    print('exists', p.exists())
    print('parts', p.name)
    with p.open(encoding='utf-8') as f:
        lines = f.read().splitlines()
    print('lines', lines)
print('cleaned', not pathlib.Path(d).exists())
```

<OutputBox title='对照写法：先自己猜，再点开' output='exists True\nparts note.txt\nlines [&#39;hello&#39;, &#39;world&#39;]\ncleaned True' guess="true" />


## open 的模式、编码与 pathlib

`open` 的 `mode` 决定是文本还是二进制：`r` 只读文本，`w` 写入并截断，`a` 追加，`x` 独占创建（文件已存在会抛 `FileExistsError`），加 `b` 进二进制模式（`rb` 与 `wb` 返回 `bytes`、不做编解码），加 `+` 读写兼备。

最要紧的是 `encoding`：文本模式省略时依赖 `locale.getpreferredencoding(False)`，Windows 历史上是 `cp936` 一类的多字节编码，Linux 与 macOS 多是 `utf-8`，同一份代码跨平台读出的中文可能不同，因此必须显式写 `encoding='utf-8'`。

`newline` 控制换行转换（默认值把各类换行统一成 `chr(10)`），读带 BOM 的文件用 `encoding='utf-8-sig'`。

路径拼接交给 `pathlib`：`Path(base)` 用斜杠运算符连上子目录与文件名，能跨平台生成正确的分隔符；

`Path.read_text(encoding='utf-8')`、`write_text`、`exists`、`name`、`stem`、`suffix`、`glob` 都比手写 `os.path` 好读。

`Path` 不会自动建父目录，要先调 `Path.mkdir`，并把 `parents=True`、`exist_ok=True` 传上。文件对象本身可迭代，逐行 `for line in f` 内存恒定，绝不要用 `f.read()` 把大文件全量载入；

读进来的行末尾带换行符，用 `splitlines()` 或 `rstrip` 处理。


### 带 BOM 的文件为什么要用 utf-8-sig

Excel 导出的 UTF-8 开头常有 EF BB BF，是把 U+`FEFF` 当签名写进去的 BOM。

utf-8-sig 专为它准备：`open` 读时剥掉串首 BOM、写时补回这三字节。

```python
open(path, encoding='utf-8-sig')
```

仍用 `encoding='utf-8'` 读，BOM 会解成串首零宽 U+`FEFF`（码点 65279），CSV 首字段名多出不可见前缀，按原名查字典键静默落空。

`codecs.BOM_UTF8.hex()` 可核对字节，后面的命令演示对比首字符码点。

```bash
python -c "s='中文'; b=s.encode('utf-8'); print(len(s), len(b), b.hex())"
```

把输入换成你自己的数据，观察结果是否仍符合 print 的 sep / end / file 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## with 与上下文协议：异常路径也保证关闭

`with` 表达式 `as` 变量并不是语法糖，而是把 `try/finally` 固化进协议：进入时调对象的 `__enter__` 并把返回值绑给 `as` 变量，退出时无论正常、`return`、还是抛异常，都保证调 `__exit__(exc_type, exc, tb)`；

`__exit__` 返回 `True` 会抑制异常，返回 `False` 或 `None` 则异常继续向外传播。文件对象的 `__exit__` 会 `flush` 并关闭文件描述符，所以即便处理到一半抛错也不泄漏句柄——这正是手写 `try/finally` 容易漏掉分支的地方。

`contextlib` 备了一批现成上下文：`redirect_stdout(buf)` 临时换 `sys.stdout`、`suppress(FileNotFoundError)` 吞掉指定异常、`ExitStack` 动态管理多个资源；

用 `@contextmanager` 装饰一个含 `yield` 的生成器函数就能自定义上下文，`yield` 之前的逻辑进 `__enter__`、之后放在 `finally` 里的逻辑进 `__exit__`。

多个资源也能写在同一行 `with` 里，比如把 `open(a)` 与 `open(b)` 各绑一个名字，退出时按进入的逆序依次关闭。`input(prompt)` 从 `stdin` 读一行并去掉末尾换行、始终返回 `str`，要数字得显式 `int()` 并捕获 `ValueError`；

它只适合交互脚本，服务里应改从参数、配置或标准输入流读，免得阻塞。


## __enter__ / __exit__ 与文件描述符的底层

`print` 在 C 层把每个对象转成 `str` 写进 `file` 的 `write` 方法，`sep` 与 `end` 只是两次额外的写调用；

`file` 缺省 `sys.stdout`，它是一个 `TextIOWrapper`，负责按自身 `encoding` 把 `str` 编码成字节再交给 `BufferedWriter`，所以输出乱码或编码错误多半出在这一层，而非 `print` 本身。

`open` 返回的 `TextIOWrapper` 内部包了 `IncrementalDecoder`，逐块把字节解码成 `str`；

`for line in f` 由它的 `__next__` 每次读到换行符为止，内存只随单行长度变化，而 `read()` 会一次性申请整块缓冲。

`with` 编译成带 `finally` 语义的指令：进入时把 `__exit__` 压入退出栈、调 `__enter__`，退出时无论正常还是异常都取出 `__exit__` 并把异常三元组传进去；`__exit__` 返回真值则由解释器清除当前异常。

文件对象的 `__exit__` 最终调 `close` 释放操作系统文件描述符，这正是「保证关闭」的底层依据。理解这条协议，就知道 `finally` 为什么能省，以及 `__exit__` 为什么不该顺手把异常吞掉。

<ConceptDiagram type='compare2' title='第 014 讲 · print 的参数与输出目标：sep / end / file / flush' labels='print 的参数与输出目标：sep / e|open 的模式、编码与 pathlib|with 与上下文协议：异常路径也保证关闭' caption='完成程序与外界的第一批数据交换' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 逐行迭代为什么比 read() 全量载入更安全

文件对象本身就是迭代器：TextIOWrapper 的 `__iter__` 返回自身、`__next__` 每次只读到换行符交出一行，for line in f 内存里始终只有一行，与文件大小无关。`f.read()` 不带 size 则把整份字节解码成一个 str 一次性物化，几百 MB 日志撑满堆就 OOM。

要按行处理用 `enumerate(f)` 边读边算，配生成器与 Counter 累计，内存只跟不同词数量走。后面的时间线把改成流式管道的迁移摊开。

<FlowTimeline :steps='[{"title": "print 的参数与输出目标：sep / end / file / flush", "desc": "`print` 的完整签名里，`sep` 默认一个空格，`end` 默认是换行符（值…", "tone": "blue"}, {"title": "open 的模式、编码与 pathlib", "desc": "`open` 的 `mode` 决定是文本还是二进制：`r` 只读文本，`w` 写入…", "tone": "purple"}, {"title": "with 与上下文协议：异常路径也保证关闭", "desc": "`with` 表达式 `as` 变量并不是语法糖，而是把 `try/finally`…", "tone": "orange"}, {"title": "工程落地", "desc": "安全导出：显式编码、with 关闭、输出分流、逐行读回", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：open 不写 encoding，或用系统默", "body": "文本模式省略 encoding 时依赖 locale 默认编码，Windows 与 Linux/macOS 可能读出不同中文", "tip": "一律 open(path, encoding=&#39;utf-8&#39;)；带 BOM 用 utf-8-sig；二进制数据用 rb"}, {"title": "第 2 步：用 f.read() 一次读入大文件，或把日", "body": "read() 全量载入会吃满内存；print 与数据混在同一条 stdout 会污染管道下游", "tip": "逐行 for line in f 迭代；日志改用 logging 或 print 的 file 参数指向 sys.stderr 分流"}, {"title": "第 3 步：手写 try/finally 关文件却漏了异", "body": "漏分支会泄漏文件描述符；__exit__ 返回真值会静默吞掉异常，让上层以为成功", "tip": "用 with open(...) 保证关闭；__exit__ 只在明确要抑制某类异常时才返回 True"}]' />


## 安全导出：显式编码、with 关闭、输出分流、逐行读回

一个 CLI 工具要把处理结果写成 `UTF-8` 文件、把进度打到 `stderr`，还要保证中途失败时不留下泄漏的句柄。

下面这段给出工程写法：用 `pathlib` 拼路径并创建父目录，用 `with` 明确 `encoding` 让异常路径也关闭描述符，用 `print` 的 `file` 参数把进度与数据分流，用 `StringIO` 捕获一段输出做断言，最后验证文件逐行读回的内容与写入一致。

真实项目还应先写临时文件再原子替换、用 `logging` 代替 `print`，但「显式编码、`with` 关闭、分流输出、逐行迭代」这四条原则不变。

```python
import io, sys, tempfile, pathlib

buf = io.StringIO()
print('a', 'b', sep='|', end='!', file=buf)
print('captured', repr(buf.getvalue()))
print('progress', 'start', file=sys.stderr)

with tempfile.TemporaryDirectory() as d:
    p = pathlib.Path(d) / 'out' / 'report.txt'
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w', encoding='utf-8') as f:
        f.write('name,score' + chr(10))
        f.write('ada,98' + chr(10))
    with p.open('r', encoding='utf-8') as f:
        rows = [line.splitlines()[0] for line in f]
    print('rows', rows)
    print('exists', p.exists())
print('cleaned', not p.exists())
```

<Callout type="idea" title='落地提示' text='工程上用 pathlib 拼路径、用 logging 代替 print、对大文件逐行迭代而不是 read() 全量载入' />


## 编码与资源释放的错因速查

这类问题少有显眼报错，按现象反推。

读乱码或 UnicodeDecodeError，先查 open 有没有写 encoding：省略时由 locale 定，Windows 常是 cp936、Linux 多为 UTF-8，同一份中文就对不上，一律显式 `encoding='utf-8'`、带 BOM 用 utf-8-sig。

另一头是资源：异常路径没关的描述符一直占着，久了报 too many open files，靠 with 让 `__exit__` 抛错时也关闭。下面按现象、根因、动作列成速查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| open 不写 encoding，或用系统默认编码读文件 | 文本模式省略 encoding 时依赖 locale 默认编码，Windows 与 Linux/macOS 可能读出不同中文 | 一律 open(path, encoding='utf-8')；带 BOM 用 utf-8-sig；二进制数据用 rb |
| 用 f.read() 一次读入大文件，或把日志 print 到 stdout | read() 全量载入会吃满内存；print 与数据混在同一条 stdout 会污染管道下游 | 逐行 for line in f 迭代；日志改用 logging 或 print 的 file 参数指向 sys.stderr 分流 |
| 手写 try/finally 关文件却漏了异常分支，或 __exit__ 里顺手返回 True | 漏分支会泄漏文件描述符；__exit__ 返回真值会静默吞掉异常，让上层以为成功 | 用 with open(...) 保证关闭；__exit__ 只在明确要抑制某类异常时才返回 True |

<Callout type="warn" title='本讲最容易踩的坑' text='open 不写 encoding，或用系统默认编码读文件：文本模式省略 encoding 时依赖 locale 默认编码，Windows 与 Linux/macOS 可能读出不同中文' />


## 把 IO 写进协议：练习、自测与速记

<Exercise title='基础：用 print 参数与 StringIO 捕获输出' task='把三个值用 sep 与自定义 end 写进 StringIO，打印捕获内容；再检查 sys.stderr 是否可写，说明分流的意义。' solution='import io, sys\nbuf = io.StringIO()\nprint(&#39;a&#39;, &#39;b&#39;, &#39;c&#39;, sep=&#39;|&#39;, end=&#39;.&#39;, file=buf)\nprint(&#39;captured&#39;, repr(buf.getvalue()))\nprint(&#39;stderr_writable&#39;, hasattr(sys.stderr, &#39;write&#39;))' explain='给 file 传 StringIO 后输出被完整收进内存，便于断言；日志写 sys.stderr 可避免与管道里的数据混在一起。' />

<Exercise title='进阶：验证 with 在异常路径也关闭资源' task='定义一个实现 __enter__ 与 __exit__ 的资源类，在 with 内抛异常，验证 __exit__ 被调用、且异常按 __exit__ 的返回值决定是否传播。' solution='class Res:\n    def __enter__(self):\n        self.closed = False\n        return self\n    def __exit__(self, t, v, tb):\n        self.closed = True\n        return False\nr = Res()\ntry:\n    with r:\n        raise ValueError(&#39;boom&#39;)\nexcept ValueError:\n    pass\nprint(&#39;closed&#39;, r.closed)' explain='with 退出时无论是否抛异常都会调用 __exit__，故 closed 为 True；返回 False 不抑制异常，try/except 仍能捕获到 ValueError。' />

<Quiz no='014-1' q='open 文本模式省略 encoding 的风险是？' :options='["依赖平台默认编码，Windows 与 Linux 可能读出不同中文", "一定抛异常", "自动改用 ASCII", "文件会被截断"]' answer="0" explain='文本模式省略 encoding 时用 locale.getpreferredencoding(False)，不同平台默认值不同；显式写 utf-8 才能保证一致。' />

<Quiz no='014-2' q='with 保证资源在异常路径也关闭，靠的是？' :options='["退出时无论正常或异常都调用 __exit__", "解释器自动调用 del", "try/except 吞掉异常", "垃圾回收立即回收"]' answer="0" explain='with 把 __exit__ 压入退出栈，退出时必调用并把异常三元组传入；文件对象的 __exit__ 会 flush 并 close 释放描述符。' />

<Quiz no='014-3' q='逐行读大文件应优先用？' :options='["for line in f，内存只随单行变化", "f.read() 一次读入", "readlines() 得到全量列表", "先 read 再 split"]' answer="0" explain='文件对象是可迭代的，__next__ 每次只读到换行符为止；read() 与 readlines() 都会把整个文件载入内存，大文件会 OOM。' />

<Predict no='014-4' q='主示例里 print(&#39;captured&#39;, repr(buf.getvalue())) 输出什么？' :options='["captured &#39;a|b|c.&#39;", "captured &#39;a b c&#39;", "captured &#39;a|b|c.&#39; 后再补一个空行"]' answer='0' output='captured &#39;a|b|c.&#39;' explain='sep 为竖线连接三个对象、end 为句点替代默认换行，缓冲区里恰好是 a|b|c. 六个字符；repr 显示带引号的字面量，外层 print 再补一个换行。' />

<FillBlank no='014-5' tpl='___ io' :answers='["import"]' hint='回想本讲关于 print 的 sep / end / file 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 print 的参数与输出目标：sep / end / file / flush 的落点。' />

<KnowledgeCard :points='["print 的 sep 默认空格、end 默认换行符、file 缺省 sys.stdout；给 file 传 StringIO 可捕获、传 sys.stderr 可分流", "open 文本模式必须显式 encoding=&#39;utf-8&#39;；rb/wb 返回 bytes；x 独占创建、a 追加、+ 读写", "with 靠 __enter__ 与 __exit__ 保证异常路径也关闭；__exit__ 返回 True 会抑制异常", "用 pathlib 的斜杠运算符拼路径、read_text/write_text/mkdir；Path 不会自动建父目录", "大文件逐行 for line in f 迭代，别用 read() 全量载入；日志交给 logging 而非 print 到 stdout", "contextlib.redirect_stdout / suppress / ExitStack / @contextmanager 把重定向与清理写成可复用上下文"]' :pitfalls='["open 不写 encoding，或用系统默认编码读文件", "用 f.read() 一次读入大文件，或把日志 print 到 stdout", "手写 try/finally 关文件却漏了异常分支，或 __exit__ 里顺手返回 True", "不指定 encoding 的 open 依赖平台默认编码，同一份代码在 Windows 与 Linux 上可能读出不同结果"]' summary='with 不只是语法糖：它保证异常路径上也能关闭文件描述符，等价于把 try/finally 写进协议' />

1. print 的 sep 默认空格、end 默认换行符、file 缺省 sys.stdout；给 file 传 StringIO 可捕获、传 sys.stderr 可分流

2. open 文本模式必须显式 encoding='utf-8'；rb/wb 返回 bytes；x 独占创建、a 追加、+ 读写

3. with 靠 __enter__ 与 __exit__ 保证异常路径也关闭；__exit__ 返回 True 会抑制异常

[下一讲：异常：捕获、异常链与自定义异常](/foundation/exceptions)
