---
title: 第 122 讲 · 实战 01 · 待办清单 CLI 与命令分发
description: 交付一个可安装、可测试、可持久化的命令行工具
---

<StageHeader stage='L12 · 工程实战' level='★★☆☆☆' time='45 分钟' goal='交付一个可安装、可测试、可持久化的命令行工具' prereq='第 121 讲 · 资深能力图谱、技术选型与持续精进' />

# 第 122 讲 · 实战 01 · 待办清单 CLI 与命令分发

上一讲收束了判断框架，从这一讲起转入工程实战：把前面十一阶段的知识放进能跑的小项目里用熟。头一个项目选待办清单 CLI，就因为它边界最干净——输入、领域、存储、输出四层彼此隔开，任何一层都能单独替换、单独测试。

设想两个真实故障：清单用覆盖写存盘，进程写到一半被打断，次日打开时 `JSON` 只剩半截；还有一条 `done` 命令没找到条目却照样报成功，外层脚本照着往下跑。这一讲先用 `argparse` 子命令把参数解析与业务逻辑隔开，再用临时文件配合 `os.replace` 做原子写入，最后补上退出码、入口点打包与端到端测试。需要你熟悉函数、字典、`json` 与文件读写；读完能交付一个可安装、被中断也不丢数据的小工具。


## 进程被杀后，待办文件只剩半截 JSON

一个待办清单 CLI 用 `open(path, 'w').write(json.dumps(todos))` 存盘，某次进程写到一半被 `kill -9`，磁盘上留下截断的半截 `JSON`；

第二天所有命令一起抛 `json.JSONDecodeError`，用户数据就此丢失。

团队还发现没有退出码约定：`todo done 99` 明明没找到条目却返回 `0`，外层脚本以为成功，继续把后续步骤全带偏。最朴素的写法「直接覆盖写、报错就 `print` 一句」失败在两处：写操作不是原子的，进程随时可能停在文件写到一半；错误只打印给人看，没有通过进程退出码传给调用方，自动化脚本无从判定成败。

这一讲用 `tempfile.mkstemp` 加 `os.replace` 做原子写、用 `argparse` 子命令做分发、让 `main` 返回整数再交给 `sys.exit` 定退出码，并把输入、领域、存储、输出四层拆开做端到端测试。


## argparse 子命令与命令分发：命令层只解析不碰业务

`ArgumentParser(prog='todo')` 建出解析器，`add_subparsers` 再挂子命令，其中 `dest='cmd'` 决定命令名存到哪个字段、`required=True` 让缺子命令时直接报错而不是静默返回 `None`——这个参数从 3.7 起才支持。

每个 `add_parser('add')` 返回一台独立的子解析器，可以继续用 `add_argument('title')` 声明位置参数、用 `add_argument` 声明整数参数；

```python
add_argument('tid', type=int)
```

`type=int` 会在解析阶段把字符串转成整数，转不动就由 `argparse` 统一报错。

`parse_args(argv)` 返回 `Namespace`，把 `argv` 做成参数（默认 `None` 表示读 `sys.argv`）是让 `main` 可测试的关键。

用法错误时 `argparse` 调 `parser.error`，把 usage 打到 stderr 并以退出码 `2` 结束，这就划清了它与业务错误码的界线：`0` 成功、`1` 业务错误（如条目不存在）、`2` 用法错误。

命令层只把 `Namespace` 翻译成对领域层的调用，绝不自己 `open` 文件，换存储实现时它一行都不用改。

`set_defaults(func=handler)` 能把处理函数挂到 `Namespace` 上做表驱动分发，不过对初学者，显式的 `if/elif` 分支更透明。

```python
import argparse, json, os, tempfile

def load(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save(path, rows):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

def add(path, title):
    rows = load(path)
    rows.append({'id': len(rows) + 1, 'title': title, 'done': False})
    save(path, rows)
    return rows[-1]['id']

def done(path, tid):
    rows = load(path)
    hit = [r for r in rows if r['id'] == tid]
    if not hit:
        return 1
    hit[0]['done'] = True
    save(path, rows)
    return 0

def main(argv=None):
    p = argparse.ArgumentParser(prog='todo')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('add').add_argument('title')
    sub.add_parser('done').add_argument('tid', type=int)
    ns = p.parse_args(argv)
    path = os.environ.get('TASK_PATH', 'todos.json')
    if ns.cmd == 'add':
        print('added', add(path, ns.title))
        return 0
    return done(path, ns.tid)

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, 'todos.json')
    os.environ['TASK_PATH'] = path
    print('add', main(['add', '写精讲']), main(['add', '跑自检']))
    print('done', main(['done', '1']), 'missing', main(['done', '99']))
    print('rows', json.load(open(path, encoding='utf-8')))
os.environ.pop('TASK_PATH', None)
```

<OutputBox title='主示例运行结果' output='added 1\nadded 2\nadd 0 0\ndone 0 missing 1\nrows [{&#39;id&#39;: 1, &#39;title&#39;: &#39;写精讲&#39;, &#39;done&#39;: True}, {&#39;id&#39;: 2, &#39;title&#39;: &#39;跑自检&#39;, &#39;done&#39;: False}]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import argparse, json, os, tempfile\n\ndef load(path):\n    if not os.path.exists(path):\n        return []\n    with open(path, &#39;r&#39;, encoding=&#39;utf-8&#39;) as f:\n        return json.load(f)\n\ndef save(path, rows):\n    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or &#39;.&#39;)\n    try:\n        with os.fdopen(fd, &#39;w&#39;, encoding=&#39;utf-8&#39;) as f:\n            json.dump(rows, f, ensure_ascii=False)\n            f.flush()\n            os.fsync(f.fileno())\n        os.replace(tmp, path)\n    finally:\n        if os.path.exists(tmp):\n            os.remove(tmp)\n\ndef add(path, title):\n    rows = load(path)\n    rows.append({&#39;id&#39;: len(rows) + 1, &#39;title&#39;: title, &#39;done&#39;: False})\n    save(path, rows)\n    return rows[-1][&#39;id&#39;]\n\ndef done(path, tid):\n    rows = load(path)\n    hit = [r for r in rows if r[&#39;id&#39;] == tid]\n    if not hit:\n        return 1\n    hit[0][&#39;done&#39;] = True\n    save(path, rows)\n    return 0\n\ndef main(argv=None):\n    p = argparse.ArgumentParser(prog=&#39;todo&#39;)\n    sub = p.add_subparsers(dest=&#39;cmd&#39;, required=True)\n    sub.add_parser(&#39;add&#39;).add_argument(&#39;title&#39;)\n    sub.add_parser(&#39;done&#39;).add_argument(&#39;tid&#39;, type=int)\n    ns = p.parse_args(argv)\n    path = os.environ.get(&#39;TASK_PATH&#39;, &#39;todos.json&#39;)\n    if ns.cmd == &#39;add&#39;:\n        print(&#39;added&#39;, add(path, ns.title))\n        return 0\n    return done(path, ns.tid)\n\nwith tempfile.TemporaryDirectory() as d:\n    path = os.path.join(d, &#39;todos.json&#39;)\n    os.environ[&#39;TASK_PATH&#39;] = path\n    print(&#39;add&#39;, main([&#39;add&#39;, &#39;写精讲&#39;]), main([&#39;add&#39;, &#39;跑自检&#39;]))\n    print(&#39;done&#39;, main([&#39;done&#39;, &#39;1&#39;]), &#39;missing&#39;, main([&#39;done&#39;, &#39;99&#39;]))\n    print(&#39;rows&#39;, json.load(open(path, encoding=&#39;utf-8&#39;)))\nos.environ.pop(&#39;TASK_PATH&#39;, None)' :notes='["导入 argparse 做命令解析，json 做持久化，os 做原子替换，tempfile 建临时文件", "空行，只用于分隔逻辑块，不影响执行结果。", "load 读取清单；文件不存在视为空库", "os.path.exists 先判断，避免首次运行时 FileNotFoundError", "不存在返回空列表，作为初始状态", "以 UTF-8 显式打开，跨平台不依赖系统默认编码", "json.load 反序列化，文件损坏时这里会抛 JSONDecodeError", "空行，只用于分隔逻辑块，不影响执行结果。", "save 用临时文件加 os.replace 实现原子写", "mkstemp 必须在目标文件所在目录建临时文件，保证同文件系统", "try 包住整段写入，异常时走 finally 清理", "os.fdopen 把 fd 包成文本文件对象", "json.dump 序列化，ensure_ascii=False 让中文原样落盘", "f.flush 把用户态缓冲刷进内核页缓存", "os.fsync 把页缓存真正写到磁盘，防止断电丢数据", "os.replace 原子替换：读者只会看到完整旧文件或完整新文件", "finally 无论成功失败都执行清理", "仅在临时文件仍存在时才删，replace 成功后它已不存在", "删除残留的 .tmp，避免目录里堆积垃圾", "空行，只用于分隔逻辑块，不影响执行结果。", "add 是纯领域逻辑，只依赖 load/save 返回的列表", "先读当前清单", "追加一条待办，id 用长度加一，done 初始为 False", "调用原子写落盘", "返回新条目的 id 供输出层使用", "空行，只用于分隔逻辑块，不影响执行结果。", "done 按 id 标记完成，找不到返回业务错误码 1", "读取当前清单", "用列表推导找出匹配 id 的条目", "没命中则走业务错误分支", "return 1 让调用方据此设退出码", "命中则置 done 为 True", "保存回磁盘", "成功返回 0", "空行，只用于分隔逻辑块，不影响执行结果。", "main 接收可注入的 argv，便于测试，默认 None 表示读 sys.argv", "建顶层解析器，prog 影响 usage 里显示的程序名", "add_subparsers 的 required=True 自 3.7 起支持，缺子命令直接报错", "add 子命令声明一个名为 title 的位置参数", "done 子命令声明 tid，type=int 在解析阶段完成字符串到整数转换", "parse_args 返回 Namespace，命令层只到这里为止", "存储路径从环境变量取，遵循 12-factor 配置外置", "命令分发：add 分支调用领域层并打印结果", "打印新 id", "add 成功固定返回 0", "其余命令把领域层返回的码原样作为退出码", "空行，只用于分隔逻辑块，不影响执行结果。", "用 TemporaryDirectory 建隔离目录，测试不污染真实家目录", "组合出目标文件路径", "通过环境变量把路径注入 main，演示配置外置", "连续两次 add，外层 print 先输出两次内部打印再打印两个返回码", "done 命中返回 0，done 99 未命中返回 1，退出码区分业务成败", "直接读取最终文件，验证持久化内容正确", "清理环境变量，避免污染同进程的其它测试"]' title='第 122 讲 · 实战 01 · 待办清单 CLI 与命令分发' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='layers3' title='第 122 讲 · argparse 子命令与命令分发：命令层只解析不碰业务' labels='argparse 子命令与命令分发：命令层只…|JSON 持久化与原子写入：临时文件加 os…|四层分离、退出码与端到端测试|端到端测试' caption='交付一个可安装、可测试、可持久化的命令行工具' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### 对照：把解析和业务塞进同一个函数

```python
import json, os, tempfile

target = os.path.join(tempfile.mkdtemp(), 'todos.json')
old = json.dumps([{'id': 1, 'done': False}])
with open(target, 'w', encoding='utf-8') as f:
    f.write(old)
with open(target, 'w', encoding='utf-8') as f:
    f.write(old[:8])
try:
    json.loads(open(target, encoding='utf-8').read())
except json.JSONDecodeError as e:
    print('direct-write corrupt', type(e).__name__)
tmp = target + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    f.write(old)
os.replace(tmp, target)
print('atomic restore', json.loads(open(target, encoding='utf-8').read()))
```

<OutputBox title='对照写法：先自己猜，再点开' output='direct-write corrupt JSONDecodeError\natomic restore [{&#39;id&#39;: 1, &#39;done&#39;: False}]' guess="true" />


## JSON 持久化与原子写入：临时文件加 os.replace

`json.dump` 负责序列化、`json.load` 负责反序列化，`ensure_ascii=False` 让中文原样写进文件，`indent=2` 便于人读。

原子写有一套固定姿势：先让 `tempfile.mkstemp` 在目标文件所在目录（也就是同一文件系统）建临时文件，它返回一个文件描述符与临时路径；

用 `os.fdopen(fd, 'w')` 包成文件对象后写入，`f.flush()` 把用户态缓冲刷进内核，`os.fsync(f.fileno())` 再把页缓存真正落盘，最后 `os.replace(tmp, target)` 一步原子替换。

之所以稳妥，是因为 `POSIX` 的 `rename(2)` 在同一文件系统内是原子的：任何时刻的读者要么看到完整的旧文件、要么看到完整的新文件，绝不会撞上半截；

而直接 `open(target,'w')` 会先截断再逐字节写，做不到这一点。

跨文件系统 rename 会抛 `OSError` 的 `EXDEV`（errno 18），所以临时文件必须与目标同目录，这正是上面那条约束的由来；再用 `try/finally` 保证异常时删掉残留的临时文件。

加载侧要分清两件事：文件不存在可以返回空列表，但文件存在却解析失败、`json.load` 抛 `json.JSONDecodeError` 时必须报错退出，绝不能当成空列表再覆盖写，否则会把损坏的数据悄悄抹掉。

**进程退出码约定与产生方式**

| 退出码 | 含义 | 产生方式 |
| --- | --- | --- |
| 0 | 命令成功 | main 返回 0，sys.exit(main()) 透传 |
| 1 | 业务错误，如条目 id 不存在 | 领域层返回 1，命令层原样返回 |
| 2 | 用法错误，参数缺失或类型不对 | argparse 的 parser.error 自动以此码退出 |
| 126 / 127 | 不可执行 / 命令未找到 | 由 shell 产生，非 Python 程序控制 |


## os.replace 为什么是原子写

`os.replace` 能当原子提交点，根子在 `POSIX` 的 `rename(2)`：同一挂载点内，内核把目录项从旧 `inode` 改指向新 `inode` 是一次原子更新，不存在「改到一半」的中间状态，并发读者只会打开到旧 `inode` 或新 `inode` 之一。

反过来，直接 `open(path,'w')` 会先以 `O_TRUNC` 把文件截零再逐字节写，崩溃窗口里目标文件本身就是半成品，这正是数据永久损坏的根因。

`f.flush` 只把 Python 的 `BufferedWriter` 缓冲交给内核，断电时页缓存照样会丢，必须再调 `os.fsync` 触发文件系统把数据写入稳定存储；两者职责不同，谁也替代不了谁。

临时文件用 `tempfile.mkstemp` 建在目标同目录，是为了保证与目标同一文件系统，否则 `rename` 会返回 `EXDEV`。

退出码的分工也在这里定型：用法错误那一路，`argparse` 通过 `parser.error` 内部调 `sys.exit(2)`；业务码则由 `main` 的返回值经 `sys.exit` 透传。把两者分开，自动化脚本才能用 `returncode` 区分「命令用错了」和「业务没成功」。


### rename(2) 的同一挂载点前提

`os.replace(tmp, target)` 能当原子提交点，靠的是 `POSIX` 的 `rename(2)`：同一挂载点内，内核把目录项从旧 `inode` 改指向新 `inode` 是一次原子更新，读者只会看到旧文件或新文件之一。

前提正卡在挂载点上——临时文件建在 `/tmp`、目标却在另一块盘，就跨不了设备，会抛 `OSError` 的 `EXDEV`（errno 18）。

所以 `tempfile.mkstemp` 的 `dir` 必须指向目标文件所在目录；

提交前还要 `f.flush()` 加 `os.fsync(fd)` 把数据真正落盘。后面的探针会复现 `EXDEV`。

```python
import os, tempfile

d = tempfile.mkdtemp()
a = os.path.join(d, 'a.json')
b = os.path.join(d, 'b.tmp')
open(a, 'w').write('old')
open(b, 'w').write('new')
ino_before = os.stat(a).st_ino
os.replace(b, a)
print('content', open(a).read())
print('inode changed', os.stat(a).st_ino != ino_before)
print('tmp gone', not os.path.exists(b))
print('same dir', os.path.dirname(a) == os.path.dirname(b))
```

<OutputBox title='原理验证' output='content new\ninode changed True\ntmp gone True\nsame dir True' />

<Term word='命令解析 argparse / click' text='`ArgumentParser(prog=&#39;todo&#39;)` 建出解析器，`add_subparsers` 再挂子命令，其中 `dest=&#39;cmd&#39;` 决定命令名存到哪个字段、`required=True` 让缺子命令时直接报错而不是静默返回 `None`——这个参数从 3.7 起才支持。每个…' />

<Term word='数据模型与 JSON 持久化' text='`json.dump` 负责序列化、`json.load` 负责反序列化，`ensure_ascii=False` 让中文原样写进文件，`indent=2` 便于人读。原子写有一套固定姿势：先让 `tempfile.mkstemp` 在目标文件所在目录（也就是同一文件系统）建临时文件，它返回一个文件描述符与临时路径；用…' />


## 四层分离与替换点

把 CLI 拆成四层：输入层用 `argparse`，领域层是纯逻辑（比如 `add` 与 `done`），存储层管 `load` 与 `save` 的原子写，输出层只做 `print` 格式化。每层都能单独替换与测试：领域层注入一份内存里的假存储就能测，完全不用碰磁盘。

`main(argv)` 返回整数而不是自己调 `sys.exit`，测试里可以直接断言返回值；

真正把整数变成进程退出码的是入口那行守卫——`if __name__ == '__main__'` 里调用 `sys.exit(main())`。

端到端测试有两条路：`click` 生态用 `click.testing.CliRunner` 捕获 `stdout` 与 `exit_code`；

只用标准库就用 `subprocess.run` 断言 `stdout` 与 `returncode`，或者把 `main` 设计成可注入 `argv` 与输出流后直接调用。

打包入口写在 `pyproject.toml` 的 `[project.scripts]` 下，一行 `todo = 'todo.cli:main'`；

`pip install` 后由 setuptools 或 hatchling 生成可执行脚本，脚本调用 `main()` 并拿它的返回值当退出码。

```bash
pip install -e .
```

三个失效信号很直观：命令函数里直接 `open()`、测试要清理真实家目录、以及所有路径都返回 `0`。


## 退出码约定：别让所有路径都返回 0

外层脚本靠退出码判断成败，别让每条路径都回 `0`。

约定三层：`0` 成功、`1` 业务错误（如 `done 99` 没找到条目）、`2` 用法错误——`argparse` 的 `parser.error` 自带 `2`，`add_subparsers` 的 `required=True` 自 3.7 起支持，缺子命令不再静默返回 `None`。

实现上让 `main(argv)` 返回整数，末尾用 `sys.exit(main())` 透传；

领域层把「没找到」映射成 `1`，断言 `main(['done','99']) == 1` 就能锁住。

下表列出码值与产生方式。

**四层分离与替换点**

| 层 | 职责 | 可替换/可测手段 |
| --- | --- | --- |
| 输入层 | argparse 解析 argv 为 Namespace | 注入 argv 列表直接断言 |
| 领域层 | add/done 纯逻辑 | 注入内存 Fake 存储，不碰磁盘 |
| 存储层 | load/save 原子读写 JSON | 换成 sqlite 适配器而领域层不变 |
| 输出层 | print 格式化与 stdout | CliRunner / subprocess 捕获断言 |

<Callout type="warn" title='本讲最容易踩的坑' text='直接 open(path,&#39;w&#39;) 覆盖写，进程被杀留下半截 JSON：先截断再逐字节写，崩溃窗口里目标文件本身就是损坏状态' />


## 错因速查与排查顺序

待办文件损坏时按「能不能读、会不会覆盖、看退出码」三步查。

`json.load` 抛 `json.JSONDecodeError`，说明磁盘上是半截 `JSON`；

此时若在 `except` 里当成空列表继续 `save`，会抹掉仅存的数据——只有文件不存在才返回空列表，存在却解析失败必须报错退出、留着原文件供恢复。

写侧依次核对：`tempfile.mkstemp` 的 `dir` 是否与目标同目录、有没有 `f.flush()` 与 `os.fsync(fd)`、是否走了 `os.replace`；

缺一步就可能在崩溃窗口留下半成品，跨设备则会报 `EXDEV`。最后确认 `main` 把业务失败映射成了非 `0`。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 直接 open(path,'w') 覆盖写，进程被杀留下半截 JSON | 先截断再逐字节写，崩溃窗口里目标文件本身就是损坏状态 | tempfile.mkstemp 在目标同目录写临时文件，flush + fsync 后 os.replace 原子替换 |
| 把 json.JSONDecodeError 当成空列表继续 save | 文件损坏时静默当成空库并覆盖写，把用户仅存的数据抹掉 | 文件不存在才返回空列表；存在但解析失败要报错退出，保留原文件供人工恢复 |
| 所有路径都返回 0，外层脚本误判成功 | 业务失败只 print 没设退出码，returncode 恒为 0 | main 返回整数、入口 sys.exit(main())；业务错误返 1，用法错误由 argparse 返 2 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：直接 open(path,&#39;w&#39;) 覆盖写…", "body": "先截断再逐字节写，崩溃窗口里目标文件本身就是损坏状态", "tip": "tempfile.mkstemp 在目标同目录写临时文件，flush + fsync 后 os.replace 原子替换"}, {"title": "第 2 步：把 json.JSONDecodeError…", "body": "文件损坏时静默当成空库并覆盖写，把用户仅存的数据抹掉", "tip": "文件不存在才返回空列表；存在但解析失败要报错退出，保留原文件供人工恢复"}, {"title": "第 3 步：所有路径都返回 0，外层脚本误判成功", "body": "业务失败只 print 没设退出码，returncode 恒为 0", "tip": "main 返回整数、入口 sys.exit(main())；业务错误返 1，用法错误由 argparse 返 2"}]' />


## 可安装 CLI：pyproject 入口点与端到端断言

要把待办工具交付成可安装命令，项目结构大体是 `todo/cli.py`、`todo/store.py`，外加 `pyproject.toml` 里 `[project.scripts]` 的一行 `todo = 'todo.cli:main'`。

下面的片段把四层收进一个可运行脚本：`JsonTodoRepo` 承担原子存储，`build_parser` 承担输入，`dispatch` 把 `Namespace` 翻译成领域调用并返回「退出码 + 消息」，`e2e_test` 用 `TemporaryDirectory` 建一座隔离库、注入仓储，再断言返回码与落盘内容。

因为 `dispatch` 只认 `repo` 的方法、不认具体路径，换成 `sqlite` 实现时领域层与测试都不用改。真实项目里 `e2e_test` 会交给 `pytest`，另用 `subprocess.run` 断言安装后脚本的 `returncode` 与 `stdout`。

读这段时重点看各层之间只传数据与整数，不共享文件句柄。

```python
import argparse, json, os, tempfile

class JsonTodoRepo:
    def __init__(self, path):
        self.path = path
    def load(self):
        if not os.path.exists(self.path):
            return []
        return json.load(open(self.path, encoding='utf-8'))
    def save(self, rows):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or '.')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(rows, f)
        os.replace(tmp, self.path)
    def add(self, title):
        rows = self.load()
        rows.append({'title': title, 'done': False})
        self.save(rows)
        return len(rows)

def build_parser():
    p = argparse.ArgumentParser(prog='todo')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('add').add_argument('title')
    return p

def dispatch(argv, repo):
    ns = build_parser().parse_args(argv)
    if ns.cmd == 'add':
        return 0, 'added ' + str(repo.add(ns.title))
    return 2, 'unknown command'

def e2e_test():
    with tempfile.TemporaryDirectory() as d:
        repo = JsonTodoRepo(os.path.join(d, 't.json'))
        rc, msg = dispatch(['add', 'task-a'], repo)
        assert rc == 0
        assert repo.load() == [{'title': 'task-a', 'done': False}]
        return msg

print(e2e_test())
```

<Callout type="idea" title='落地提示' text='临时文件加 os.replace 实现原子写，命令层不碰业务逻辑，用 CliRunner 做端到端测试' />


## 动手加一个 done 子命令，再自测

<Exercise title='基础：复现半截 JSON 并用原子写恢复' task='先直接覆盖写把一个合法 JSON 截成前半段，捕获 json.loads 的异常类型；再用 os.replace 把完整内容写回，打印恢复后的对象。' solution='import json, os, tempfile\np = os.path.join(tempfile.mkdtemp(), &#39;t.json&#39;)\nfull = json.dumps([{&#39;id&#39;: 1}])\nopen(p, &#39;w&#39;).write(full[:6])\ntry:\n    json.loads(open(p).read())\nexcept json.JSONDecodeError as e:\n    print(&#39;corrupt&#39;, type(e).__name__)\ntmp = p + &#39;.tmp&#39;\nopen(tmp, &#39;w&#39;).write(full)\nos.replace(tmp, p)\nprint(&#39;restored&#39;, json.loads(open(p).read()))' explain='截断后的内容不是合法 JSON，json.loads 抛 JSONDecodeError；os.replace 把完整文件原子换回，读者不会看到中间态。' />

<Exercise title='进阶：给 done 命令补退出码并解释 argparse 的 2' task='写一个 main，命中 id 返回 0、未命中返回 1；用 type=int 让 tid 在解析阶段转成整数。说明为什么「用法错误」是退出码 2 而不是业务错误 1。' solution='import argparse\n\ndef main(argv):\n    p = argparse.ArgumentParser()\n    sub = p.add_subparsers(dest=&#39;cmd&#39;, required=True)\n    sub.add_parser(&#39;done&#39;).add_argument(&#39;tid&#39;, type=int)\n    ns = p.parse_args(argv)\n    return 0 if ns.tid in (1, 2) else 1\n\nprint(&#39;hit&#39;, main([&#39;done&#39;, &#39;1&#39;]), &#39;miss&#39;, main([&#39;done&#39;, &#39;99&#39;]))' explain='命中返回 0、未命中返回 1，由 main 的整数经 sys.exit 透传；用法错误（缺参数、类型不对）是 argparse 的 parser.error 走 sys.exit(2)，与业务失败分开，外层脚本据此判定是命令用错还是业务没成。' />

<Quiz no='122-1' q='关于 os.replace 的原子性，哪一项准确？' :options='["同一文件系统内 rename 是原子的，读者只会看到完整旧文件或完整新文件", "它先把目标清零再写，与直接 open(&#39;w&#39;) 一样", "它靠 Python 层的锁保证并发安全", "跨文件系统也能原子，只是慢一点"]' answer="0" explain='os.replace 落到 rename(2)，同挂载点内是一次原子目录项更新；跨文件系统会抛 OSError Errno 18 EXDEV，所以临时文件必须建在目标同目录。' />

<Quiz no='122-2' q='argparse 解析参数失败时，进程退出码通常是？' :options='["2（parser.error 触发的用法错误）", "0", "1", "126"]' answer="0" explain='argparse 遇到缺参数、类型不对等用法错误会调用 parser.error，打印 usage 到 stderr 并以 sys.exit(2) 结束；业务错误才由程序自己返回 1，两者要分开。' />

<Quiz no='122-3' q='文件已存在但 json.load 抛 JSONDecodeError，正确做法是？' :options='["报错退出并保留原文件，供人工恢复", "当成空列表继续 save", "删掉文件重新建库", "捕获后返回 0"]' answer="0" explain='只有文件不存在才返回空列表；存在却解析失败说明数据已损坏，静默当空库再覆盖会抹掉仅存数据，必须报错退出并保留现场。' />

<Predict no='122-4' q='进程在 os.replace 之前被杀，目标文件会是什么状态？' :options='["仍是完整的旧文件，临时文件是半成品但目标未被触碰", "是半截 JSON，下次 load 抛异常", "变成空文件"]' answer='0' output='目标仍是完整的旧文件，损坏的只是同目录的临时文件' explain='崩溃发生在 replace 之前时，目标文件从未被截断，写入只发生在临时文件上；replace 是唯一的提交点，要么整体生效要么完全不生效，这正是原子写隔离崩溃窗口的原理。' />

<FillBlank no='122-5' tpl='___ argparse, json, os, tempfile' :answers='["import"]' hint='回想本讲关于 命令解析 argparse / click 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 argparse 子命令与命令分发：命令层只解析不碰业务 的落点。' />

<KnowledgeCard :points='["原子写 = 同目录 mkstemp 临时文件 + f.flush + os.fsync + os.replace，replace 是唯一提交点", "os.replace 依赖同文件系统 rename(2)，跨挂载点抛 OSError（errno 18，EXDEV）", "退出码分三类：0 成功、1 业务错误、2 argparse 用法错误；main 返整数配 sys.exit 透传", "add_subparsers 的 required=True 自 3.7 起支持；type=int 在解析阶段完成转换", "四层分离：输入 argparse / 领域纯逻辑 / 存储原子写 / 输出格式化，各层可独立替换与测试", "文件损坏时保留现场报错退出，绝不静默当空库覆盖；入口点写在 pyproject.toml 的 [project.scripts]"]' :pitfalls='["直接 open(path,&#39;w&#39;) 覆盖写，进程被杀留下半截 JSON", "把 json.JSONDecodeError 当成空列表继续 save", "所有路径都返回 0，外层脚本误判成功", "直接覆盖写文件，进程中途被杀就会留下半截 JSON，数据永久损坏"]' summary='CLI 是最适合练「边界清晰」的项目：输入、领域逻辑、存储、输出四层都能单独替换与测试' />

1. 原子写 = 同目录 mkstemp 临时文件 + f.flush + os.fsync + os.replace，replace 是唯一提交点

2. os.replace 依赖同文件系统 rename(2)，跨挂载点抛 OSError（errno 18，EXDEV）

3. 退出码分三类：0 成功、1 业务错误、2 argparse 用法错误；main 返整数配 sys.exit 透传

[下一讲：实战 02 · 文件检索、日志与自动化办公](/projects/office-files)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/122-cli-todo.py`

```bash
python3 examples/lessons/122-cli-todo.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/122-cli-todo.py) · [全部示例代码索引](/examples/)
