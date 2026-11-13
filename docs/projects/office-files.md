---
title: 第 123 讲 · 实战 02 · 文件检索、日志与自动化办公
description: 把重复的文件劳动变成一条可调度命令
---

<StageHeader stage='L12 · 工程实战' level='★★☆☆☆' time='45 分钟' goal='把重复的文件劳动变成一条可调度命令' prereq='第 122 讲 · 实战 01 · 待办清单 CLI 与命令分发' />

# 第 123 讲 · 实战 02 · 文件检索、日志与自动化办公

上一讲把小工具拆成四层、存盘也稳了；这一讲把「处理一个对象」放大成「处理一整批文件」。本讲落在自动化办公易被低估的一面：批量操作一写错，几秒就作用到上千个文件，默认没有撤销。

一条清理脚本本想只删下载目录的过期文件，路径里多了一处 ..，解析后指到项目根目录，转眼改掉上百个源文件。我们先用 pathlib 遍历与路径运算校验边界，再借 os.stat 按类型容量统计、用 logging 落审计日志，最后把 dry-run、回收站与调度串成先出计划、可回退的流程。需要你熟悉路径运算与 os.walk；学完能把重复的文件劳动变成可调度、出事能撤回的命令。


## 一个匹配规则写错，几秒改动上千个文件

一条清理脚本用 `os.remove` 配合手工拼的字符串路径，本意只删下载目录里的过期临时文件，结果路径里多了一个 ..，解析后指到了项目根目录，几秒内删掉上百个源文件且没有回收站可找。另一个脚本按固定规则批量重命名，正则写宽了一点，把同事刚提交的报告也改了名，因为没有任何预演与审计记录，谁也说不清改过哪些。

自动化办公的风险全在「批量」：一条错误的匹配规则会在几秒内作用到上千个文件，而且默认不可逆。朴素解法「拼路径 + 直接删或直接改 + print 一句」失败在三处：字符串拼接不校验边界、破坏性操作没有 dry-run 与撤销、过程没有可回溯的审计日志。

本讲用 pathlib 做路径校验、rglob 与 `os.stat` 做容量统计、logging 落审计日志，把批量操作变成先出计划、可核对、可回退的流程。


## pathlib 遍历：PurePath、具体路径与 glob 的大小写边界

pathlib 把路径分成两层：PurePath 只做词法与字符串操作（拼 /、取 .suffix、.stem、.name、.parent、.with_name），完全不碰磁盘；Path 继承它并加上 stat、iterdir、rglob、rename 这些 IO 方法。

`Path.rglob`('*') 递归遍历所有后代，等价于 glob('**/*')，而 glob('*.txt') 只匹配当前一层；`Path.iterdir()` 只列直接子项。

一个高频坑是 suffix 保留原始大小写：Path('A.TXT').suffix 得到 '.TXT'，按扩展名聚合前必须 .`lower()` 归一，否则 .TXT 与 .txt 会被算成两类。

`os.walk(root)` 走另一套：它基于 `os.scandir` 自顶向下返回 (dirpath, dirnames, filenames) 三元组，topdown 默认 True，followlinks 默认 False（不跟随目录符号链接，正是为了避免符号链接环造成无限递归），还可传 onerror 回调吞掉权限错误。

`Path.resolve()` 默认 `strict=False`（3.6 起），把 .. 与符号链接解析成绝对路径；

`Path.is_relative_to(other)`（3.9 起）用来断言结果仍在允许目录内，是阻止 .. 越界的关键一道校验。

`Path.mkdir(parents=True, exist_ok=True)` 显式声明父目录与已存在时的行为，省去手写 try。

三个失效信号：glob 莫名漏文件（大小写）、遍历卡死不返回（符号链接环）、日志里出现根目录之外的路径。

**遍历与路径 API 对照**

| API | 作用范围 | 默认行为 / 参数 | 典型坑 |
| --- | --- | --- | --- |
| Path.rglob('*') | 递归所有后代 | 等价于 glob('**/*') | 符号链接环可能卡死 |
| Path.glob('*.txt') | 仅当前一层 | 不递归 | 漏掉子目录里的同名文件 |
| os.walk(root) | 自顶向下三元组 | topdown=True, followlinks=False | followlinks=True 时符号链接成环 |
| Path.resolve() | 解析 .. 与符号链接 | strict=False（3.6 起） | 不校验是否在允许目录内 |
| Path.is_relative_to(o) | 判断路径归属 | 3.9 起提供 | 必须先 resolve 再比较 |
| Path.suffix / .lower() | 取扩展名 | 保留原始大小写 | '.TXT' 与 '.txt' 会被算成两类 |

```python
import logging, tempfile
from pathlib import Path
from collections import defaultdict

root = Path(tempfile.mkdtemp())
(root / 'docs').mkdir()
(root / 'docs' / 'report.TXT').write_bytes(b'x' * 120)
(root / 'notes.txt').write_bytes(b'x' * 40)
(root / 'pic.png').write_bytes(b'x' * 300)
(root / 'pic2.PNG').write_bytes(b'x' * 100)

stat = defaultdict(lambda: [0, 0])
for p in sorted(root.rglob('*')):
    if p.is_file():
        stat[p.suffix.lower()][0] += 1
        stat[p.suffix.lower()][1] += p.stat().st_size
print('by ext', sorted((k, v[0], v[1]) for k, v in stat.items()))

plan = [(p.name, p.stem + p.suffix.lower())
        for p in sorted(root.rglob('*'))
        if p.is_file() and p.suffix != p.suffix.lower()]
print('rename plan', plan)
print('applied', 0)

log_path = root / 'audit.log'
logging.basicConfig(filename=str(log_path), level=logging.INFO, filemode='w',
                    format='%(levelname)s|%(message)s', force=True)
for old, new in plan:
    logging.info('rename %s -> %s', old, new)
print('audit', log_path.read_text(encoding='utf-8').splitlines())
```

<OutputBox title='主示例运行结果' output='by ext [(&#39;.png&#39;, 2, 400), (&#39;.txt&#39;, 2, 160)]\nrename plan [(&#39;report.TXT&#39;, &#39;report.txt&#39;), (&#39;pic2.PNG&#39;, &#39;pic2.png&#39;)]\napplied 0\naudit [&#39;INFO|rename report.TXT -&gt; report.txt&#39;, &#39;INFO|rename pic2.PNG -&gt; pic2.png&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import logging, tempfile\nfrom pathlib import Path\nfrom collections import defaultdict\n\nroot = Path(tempfile.mkdtemp())\n(root / &#39;docs&#39;).mkdir()\n(root / &#39;docs&#39; / &#39;report.TXT&#39;).write_bytes(b&#39;x&#39; * 120)\n(root / &#39;notes.txt&#39;).write_bytes(b&#39;x&#39; * 40)\n(root / &#39;pic.png&#39;).write_bytes(b&#39;x&#39; * 300)\n(root / &#39;pic2.PNG&#39;).write_bytes(b&#39;x&#39; * 100)\n\nstat = defaultdict(lambda: [0, 0])\nfor p in sorted(root.rglob(&#39;*&#39;)):\n    if p.is_file():\n        stat[p.suffix.lower()][0] += 1\n        stat[p.suffix.lower()][1] += p.stat().st_size\nprint(&#39;by ext&#39;, sorted((k, v[0], v[1]) for k, v in stat.items()))\n\nplan = [(p.name, p.stem + p.suffix.lower())\n        for p in sorted(root.rglob(&#39;*&#39;))\n        if p.is_file() and p.suffix != p.suffix.lower()]\nprint(&#39;rename plan&#39;, plan)\nprint(&#39;applied&#39;, 0)\n\nlog_path = root / &#39;audit.log&#39;\nlogging.basicConfig(filename=str(log_path), level=logging.INFO, filemode=&#39;w&#39;,\n                    format=&#39;%(levelname)s|%(message)s&#39;, force=True)\nfor old, new in plan:\n    logging.info(&#39;rename %s -&gt; %s&#39;, old, new)\nprint(&#39;audit&#39;, log_path.read_text(encoding=&#39;utf-8&#39;).splitlines())' :notes='["导入 logging 写审计、tempfile 建隔离目录，避免污染真实文件", "从 pathlib 取 Path，所有路径用它拼而不是字符串相加", "defaultdict 存每个扩展名的 [文件数, 总字节数]", "建一个临时根目录，测试在隔离目录里进行", "用 / 运算符创建 docs 子目录，Path 负责分隔符", "写入 120 字节的 report.TXT，故意用大写扩展名", "写入 40 字节的 notes.txt", "写入 300 字节的 pic.png", "写入 100 字节的 pic2.PNG，同样是大写扩展名", "聚合表：键是扩展名，值是可变的 [计数, 字节]", "rglob(&#39;*&#39;) 递归遍历全部后代，排序保证输出确定", "只统计文件，跳过 docs 这类目录", "suffix.lower() 归一大小写，.TXT 与 .txt 归为同一类", "累加 st_size，即文件逻辑字节数", "打印按扩展名排序后的三元组，结果可核对", "dry-run 计划：列表推导收集 (原名, 目标名)，不执行任何改名", "对排序后的全部后代再做一次遍历", "仅当 suffix 不等于其小写形式时才纳入计划", "打印计划，人工核对条数与样例后才真正执行", "applied 固定为 0，明确表示本次没有任何副作用", "审计日志写到隔离目录内", "basicConfig 用 force=True（3.8 起）重置 root handler，避免重复日志", "format 指定级别与消息，filemode=&#39;w&#39; 每次重写", "遍历 dry-run 计划，逐条落到审计日志", "logging.info 用 %s 惰性插值，记录源名与目标名", "读回日志文件并打印，验证审计确实落盘"]' title='第 123 讲 · 实战 02 · 文件检索、日志与自动化办公' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 元数据、容量统计与 logging 落盘

`Path.stat()` 返回 `os.stat_result`，字段含义必须分清：st_size 是文件逻辑字节数，st_mtime 是最后修改时间的浮点秒，st_ino 是 inode 号，st_mode 含类型与权限位；

st_ctime 在 Unix 上是 inode 元数据最后变更时间（chmod、chown 都会更新），并不是创建时间——只有 Windows 上它才近似创建时间，把它当「文件什么时候建的」会得出错误报表。

磁盘实际占用要看 st_blocks 乘 512 字节，稀疏文件的 st_size 很大而 st_blocks 很小，二者不相等。

`datetime.fromtimestamp(st_mtime)` 把浮点秒转成本地 datetime，单位换算用 1024 进制（1 `MiB = 1048576` 字节）。

聚合按扩展名用 `collections.defaultdict(lambda: [0, 0])` 存 [文件数, 总字节数] 最省事。

审计日志走 logging 的 Logger / Handler / Formatter 三层：`logging.basicConfig`(filename=, level=, filemode='w', format=, `force=True`) 一次配好，force 自 3.8 起会先移除 root 上已有 handler，避免同一进程重复执行时日志翻倍；

format 常用 %(asctime)s、%(levelname)s、%(message)s 占位。

按大小轮转用 `RotatingFileHandler(maxBytes, backupCount)`（maxBytes 默认 0 表示不轮转，必须显式给值），按时间轮转用 TimedRotatingFileHandler(when='midnight', `interval=1`, backupCount)。

审计记录至少要有时间戳、源路径、目标路径、动作与结果，否则出事无法回放。

```python
import os, tempfile
from pathlib import Path

base = Path(tempfile.mkdtemp())
target = base / 'safe'
target.mkdir()
(base / 'safe' / 'keep.txt').write_text('keep')
bad = os.path.join(str(base), '..', 'safe', 'keep.txt')
print('naive join escapes', Path(bad).resolve() != (target / 'keep.txt').resolve())
resolved = (target / 'keep.txt').resolve()
print('resolve inside base', resolved.is_relative_to(base.resolve()))
plan = [p.name for p in sorted(target.iterdir()) if p.is_file()]
print('dry-run would act on', plan)
print('actually removed', 0)
print('still exists', (target / 'keep.txt').exists())
```

<OutputBox title='对照写法：先自己猜，再点开' output='naive join escapes True\nresolve inside base True\ndry-run would act on [&#39;keep.txt&#39;]\nactually removed 0\nstill exists True' guess="true" />


## build_plan 与 apply_plan：把批量操作拆成计划与执行

批量错误的破坏力等于「一条规则乘以上千个文件」，所以正确流程把计划与执行分开。第一步 dry-run：只把 (src, dst) 收集进列表并打印，applied 计数固定为 0，人工核对计划条数与样例后才真正执行；

第二步边界校验：所有路径用 / 运算符拼（Path 会处理分隔符），目标先 `dst.resolve()`.`is_relative_to(root.resolve()`) 确认没跑出允许目录，`dst.exists()` 时跳过并记入失败清单，避免覆盖已有文件；

第三步撤销路径：不要用 `os.remove` 直接删，改成 `shutil.move` 把文件移到同分区的 .trash 回收站目录，重命名用 `Path.rename` 或 `os.replace`（同文件系统内原子）。幂等也要设计：把「suffix 不等于其小写」作为唯一改名条件，重复跑不会二次改名。

审计用 logging 落盘并带 datetime 时间戳，形成可回溯的操作序列。调度侧用 datetime 触发，或 APScheduler 的 CronTrigger / IntervalTrigger；标准库 sched 能做最简定时。

定时任务要处理两类失效：上一轮未结束又触发（max_instances 限制重叠）、以及错过触发后堆积补跑（coalesce 合并、misfire_grace_time 设定容忍窗口）。三个报警信号：一次跑改动文件数远超预期、审计日志里出现 root 之外路径、以及没有任何 dry-run 就直接执行破坏性操作。

<ConceptDiagram type='hub4' title='第 123 讲 · pathlib 遍历：PurePath、具体路径与 glob 的大小写边界' labels='pathlib 遍历：PurePath、具体|元数据、容量统计与 logging 落盘|批量操作安全：dry-run、回收站、路径校' caption='把重复的文件劳动变成一条可调度命令' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## PurePath 的 flavour 决定大小写敏感

PurePath 内部持有一个 flavour 对象（PosixFlavour 或 _WindowsFlavour），决定分隔符、大小写敏感性与盘符规则，所以同一段 glob 在 Windows 上不区分大小写、在 POSIX 上区分；rglob 把模式编译成选择器后递归调用 scandir。

`Path.stat()` 落到 `stat(2)` 系统调用：st_size 是目录项记录的逻辑长度，稀疏文件靠孔洞不占块，因此实际占用必须看 st_blocks；st_ctime 在 Unix 语义是 inode 变更时间，这是文件系统而非 Python 的定义。

logging 的 Logger 以点号构成层级、propagate 默认 True 向上传播到 root，Handler 决定落点，Formatter 决定文本；basicConfig 的 `force=True` 会先清空 root 已有 handler，因此同一进程里重复配置不会写出两遍。

`shutil.move` 在同文件系统内走 `os.rename`（原子）、跨文件系统才退化为复制加删除，所以回收站目录要与目标同分区。dry-run 的正确性来自把副作用推迟到显式确认之后：计划是纯数据，执行才触碰磁盘。


## 带 dry-run、路径校验与审计的批量重命名

报表目录里混着 `A.TXT`、`B.PNG` 这类大写扩展名，需要统一成小写，但脚本一旦跑错会改动成百上千个文件。

工程做法是把操作拆成 build_plan 与 apply_plan 两段：build_plan 用 rglob 递归收集需要改名的 (源, 目标)，对每个目标先 resolve 再断言 `dst.parent` 仍是根目录，防止 .. 与符号链接把文件挪出去；

apply_plan 在 `dry_run=True` 时只写审计日志、返回 0，只有显式关掉 dry_run 才调用 `Path.rename`。

日志用 `logging.basicConfig` 的 `force=True` 与 filemode='w' 保证每次运行都是干净的一份，消息里带 datetime 时间戳、动作与两个文件名。

真实项目还会把计划写成 JSON 供人工评审、把失败清单落盘重试、用 APScheduler 定时触发并设 max_instances 防止重叠。下面片段可直接运行，重点看 dry_run 分支如何做到零副作用。

```python
import logging, tempfile
from datetime import datetime
from pathlib import Path

def build_plan(root):
    root = Path(root).resolve()
    out = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or not p.suffix or p.suffix == p.suffix.lower():
            continue
        dst = p.with_name(p.stem + p.suffix.lower())
        if dst.resolve().parent != root:
            raise ValueError('target escapes root')
        out.append((p, dst))
    return out

def apply_plan(plan, dry_run):
    for src, dst in plan:
        stamp = datetime.now().isoformat(timespec='seconds')
        if dry_run:
            logging.info('%s DRY-RUN %s -> %s', stamp, src.name, dst.name)
        else:
            src.rename(dst)
            logging.info('%s RENAMED %s -> %s', stamp, src.name, dst.name)
    return 0 if dry_run else len(plan)

root = Path(tempfile.mkdtemp())
for n in ('A.TXT', 'B.PNG', 'c.txt'):
    (root / n).write_text('x')
log_path = root / 'plan.log'
logging.basicConfig(filename=str(log_path), level=logging.INFO,
                    filemode='w', format='%(message)s', force=True)
plan = build_plan(root)
print('planned', len(plan))
print('applied', apply_plan(plan, dry_run=True))
print('unchanged', sorted(p.name for p in root.iterdir()))
```

<Callout type="idea" title='落地提示' text='先 dry-run 打印计划、默认走回收站、路径全部用 pathlib 校验、操作写审计日志' />


## 练习、自测与速记

<Exercise title='基础：按扩展名聚合容量并归一大小写' task='在一个临时目录里建 A.TXT、b.txt、c.PNG 三个文件，用 rglob 与 defaultdict 按 suffix.lower() 统计文件数与总字节数，打印排序结果。' solution='from pathlib import Path\nfrom collections import defaultdict\nimport tempfile\nroot = Path(tempfile.mkdtemp())\nfor n, sz in [(&#39;A.TXT&#39;, 10), (&#39;b.txt&#39;, 20), (&#39;c.PNG&#39;, 30)]:\n    (root / n).write_bytes(b&#39;x&#39; * sz)\nd = defaultdict(lambda: [0, 0])\nfor p in root.rglob(&#39;*&#39;):\n    if p.is_file():\n        d[p.suffix.lower()][0] += 1\n        d[p.suffix.lower()][1] += p.stat().st_size\nprint(sorted((k, v[0], v[1]) for k, v in d.items()))' explain='suffix 保留大小写，必须 .lower() 归一，否则 A.TXT 与 b.txt 会被拆成两类；结果应是 [(&#39;.png&#39;, 1, 30), (&#39;.txt&#39;, 2, 30)]。' />

<Exercise title='进阶：证明 resolve 能挡住 .. 越界' task='构造一个含 .. 的字符串路径，用 Path.resolve() 解析后与允许根目录比较，打印 is_relative_to 的结果，并说明为什么字符串 startswith 不够。' solution='from pathlib import Path\nimport tempfile, os\nbase = Path(tempfile.mkdtemp()).resolve()\nbad = os.path.join(str(base), &#39;..&#39;, &#39;outside.txt&#39;)\np = Path(bad).resolve()\nprint(&#39;escapes&#39;, p.is_relative_to(base))\nprint(&#39;string startswith&#39;, bad.startswith(str(base)))\nprint(&#39;target parent&#39;, p.parent == base.parent)' explain='startswith 只看字符串前缀，.. 仍以 base 开头却已跳出目录；resolve 把 .. 折叠成真实绝对路径后，is_relative_to 才能可靠判定归属。' />

<Quiz no='123-1' q='Path(&#39;report.TXT&#39;).suffix 的值以及按扩展名统计时的正确做法是？' :options='["&#39;.TXT&#39;，聚合前要 .lower() 归一", "&#39;.txt&#39;，Path 会自动小写", "&#39;TXT&#39;，不含点号", "抛 AttributeError"]' answer="0" explain='suffix 保留原始大小写，Path(&#39;report.TXT&#39;).suffix 得到 &#39;.TXT&#39;；不归一就会把 .TXT 与 .txt 算成两类，容量报表随之失真。' />

<Quiz no='123-2' q='关于 os.stat_result 的 st_ctime，准确的说法是？' :options='["Unix 上是 inode 元数据最后变更时间，不是创建时间", "所有平台都是文件创建时间", "等于 st_mtime", "单位是天"]' answer="0" explain='Unix 的 st_ctime 记录 inode 变更（chmod、chown 也更新），Windows 上才近似创建时间；要表达修改时间用 st_mtime，要磁盘占用用 st_blocks 乘 512。' />

<Quiz no='123-3' q='批量破坏性脚本最该先加的三道防线是？' :options='["dry-run 出计划、resolve 加 is_relative_to 校验、删除改移入回收站", "直接 os.remove 外加 try/except", "把日志级别调到 DEBUG", "扩大 glob 范围一次处理完"]' answer="0" explain='批量错误会被文件数量放大：先 dry-run 让人核对计划，再用 resolve 与 is_relative_to 挡住越界，最后用 shutil.move 到同分区回收站保留撤销路径，三者缺一不可。' />

<KnowledgeCard :points='["PurePath 只做词法操作、Path 才带 IO；suffix 保留大小写，统计前必须 .lower() 归一", "rglob(&#39;*&#39;) 递归、glob(&#39;*.txt&#39;) 只当前层；os.walk 的 followlinks 默认 False 防符号链接环", "Path.resolve() 默认 strict=False；配合 is_relative_to（3.9 起）挡住 .. 越界，别用字符串 startswith", "st_size 是逻辑字节数，磁盘占用看 st_blocks 乘 512；Unix 的 st_ctime 是 inode 变更时间而非创建时间", "basicConfig 的 force=True（3.8 起）重置 root handler 防重复日志；审计要含时间戳与源/目标路径", "批量操作先 dry-run、再校验、后执行；删除用 shutil.move 到同分区回收站保留撤销，dst.exists() 时跳过防覆盖"]' :pitfalls='["字符串拼路径带 .. 越界，删掉了目标目录之外的文件", "用 os.remove 批量清理，误删后无法恢复", "把 st_ctime 当文件创建时间、把 st_size 当磁盘占用", "直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉目标目录之外的东西"]' summary='自动化办公的风险在「批量」：一个错误的匹配规则会在几秒内改动上千个文件，且没有撤销' />

1. PurePath 只做词法操作、Path 才带 IO；suffix 保留大小写，统计前必须 .lower() 归一

2. rglob('*') 递归、glob('*.txt') 只当前层；os.walk 的 followlinks 默认 False 防符号链接环

3. Path.resolve() 默认 strict=False；配合 is_relative_to（3.9 起）挡住 .. 越界，别用字符串 startswith

[下一讲：实战 03 · 邮件、PDF、Excel、Word 与图像视频](/projects/office-docs)

<Predict no='123-P' q='对含 report.TXT 与 pic2.PNG 的目录跑 dry-run 重命名，最可能的输出组合是？' :options='["列出两条计划、applied 为 0、文件保持原样", "applied 为 2 且文件已改成小写", "抛 FileNotFoundError 因为目标不存在"]' answer='0' output='rename plan [(&#39;report.TXT&#39;, &#39;report.txt&#39;), (&#39;pic2.PNG&#39;, &#39;pic2.png&#39;)] 且 applied 0' explain='dry-run 只把 (源, 目标) 收集进计划并写审计日志，不调用 Path.rename；applied 恒为 0，磁盘状态不变，因此可以先人工核对计划再真正执行。' />

<FillBlank no='123-F' tpl='___ logging, tempfile' :answers='["import"]' hint='回想本讲关于 pathlib 遍历与 glob 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 pathlib 遍历：PurePath、具体路径与 glob 的大小写边界 的落点。' />
