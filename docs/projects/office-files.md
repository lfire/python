---
title: 第 123 讲 · 实战 02 · 文件检索、日志与自动化办公
description: 把重复的文件劳动变成一条可调度命令
---

<StageHeader stage='L12 · 工程实战' level='★★☆☆☆' time='45 分钟' goal='把重复的文件劳动变成一条可调度命令' prereq='第 122 讲 · 实战 01 · 待办清单 CLI 与命令分发' />

# 第 123 讲 · 实战 02 · 文件检索、日志与自动化办公

> 自动化办公的风险在「批量」：一个错误的匹配规则会在几秒内改动上千个文件，且没有撤销。本讲的目标是「把重复的文件劳动变成一条可调度命令」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P123' title="本讲目标" :items='["能说清pathlib 遍历与 glob", "能说清os.walk 与元数据", "能说清按类型容量统计", "能说清logging 落盘", "能说清datetime 与调度"]' />

## 1. 先建立直觉

**pathlib 遍历与 glob**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**os.walk 与元数据**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**按类型容量统计**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

<ConceptDiagram type='hub4' title='第 123 讲 · pathlib 遍历与 glob' labels='pathlib 遍历与 glob|os.walk 与元数据|按类型容量统计|logging 落盘' caption='把重复的文件劳动变成一条可调度命令' />

上图用本讲的三个核心概念标出了主线：**pathlib 遍历与 glob → os.walk 与元数据 → 按类型容量统计**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 pathlib 遍历与 glob 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 True", "tone": "green"}, {"title": "深入边界", "desc": "厘清 os.walk 与元数据 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 批量重命名安全 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**pathlib 遍历与 glob**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

```python
import asyncio, json

async def handle(reader, writer):
    raw = await reader.read(1024)
    cmd = json.loads(raw.decode())
    writer.write(json.dumps({"ok": True, "cmd": cmd}).encode())
    await writer.drain()
    writer.close()

print(callable(handle))
```

<OutputBox title="运行结果" output='True' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='import asyncio, json\n\nasync def handle(reader, writer):\n    raw = await reader.read(1024)\n    cmd = json.loads(raw.decode())\n    writer.write(json.dumps({"ok": True, "cmd": cmd}).encode())\n    await writer.drain()\n    writer.close()\n\nprint(callable(handle))' :notes='["长度前缀/JSON 帧解决 TCP 粘包的第一层", "asyncio 让单机连接数不再受线程限制", "真实协议还要处理半包、超时与版本", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 123 讲 · 实战 02 · 文件检索、日志与自动化办公' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**os.walk 与元数据**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import os, signal
print(hasattr(signal, "SIGTERM"), os.name)
```

<OutputBox title="对照写法的输出（先自己猜）" output='True posix' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "import asyncio, json\n\nasync def handle(reader, writer):\n    raw = await reader.read(1024)\n    cmd = json.loads(raw.decode())\n    writer.write(json.dumps({\"ok\": True, \"cmd\": cmd}).encode())\n    await writer.drain()\n    writer.close()\n\nprint(callable(handle))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import os, signal\nprint(hasattr(signal, \"SIGTERM\"), os.name)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉目标」' />

## 3. 深入一步：规则与边界

**按类型容量统计**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**logging 落盘**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**datetime 与调度**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| pathlib 遍历与 glob | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉 |
| os.walk 与元数据 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉 |
| 按类型容量统计 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉 |
| logging 落盘 | 这里的关键词是「什么时候」和「代价是什么」 | 直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉 |
| datetime 与调度 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉 |

<Term word='pathlib 遍历与 glob' text='自动化办公的风险在「批量」：一个错误的匹配规则会在几秒内改动上千个文件，且没有撤销' />

<Callout type="warn" title="易错点" text='直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉目标目录之外的东西' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：pathlib 遍历与 glob", "body": "**pathlib 遍历与 glob**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：os.walk 与元数据", "body": "**os.walk 与元数据**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：按类型容量统计", "body": "**按类型容量统计**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：logging 落盘", "body": "**logging 落盘**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}]' />

<SequenceDiagram title='第 123 讲 · 调用时序' caption='从触发到收尾，标出可能失败的位置' :actors='["调用方", "处理逻辑", "依赖资源"]' :steps='[{"from": "调用方", "to": "处理逻辑", "label": "发起调用", "note": "pathlib 遍历与 gl", "kind": "call"}, {"from": "处理逻辑", "to": "处理逻辑", "label": "校验状态", "note": "os.walk 与元数据", "kind": "self"}, {"from": "处理逻辑", "to": "依赖资源", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "依赖资源", "to": "处理逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "处理逻辑", "to": "调用方", "label": "返回或失败", "note": "清理资源", "kind": "return"}]' />

## 4. 工程实践

先 dry-run 打印计划、默认走回收站、路径全部用 pathlib 校验、操作写审计日志 **批量重命名安全**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -m compileall -q . && python -m pytest -q
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **pathlib 遍历与 glob** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「批量重命名安全」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「批量重命名安全」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 pathlib 遍历与 glob 与 批量重命名安全 两个关注点，并说明你的取舍。' :hints='["回到 pathlib 遍历与 glob 的规则", "留意易错点：直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉目标目录之外", "先让代码跑通，再补边界与异常分支"]' solution='import os, signal\nprint(hasattr(signal, "SIGTERM"), os.name)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；先 dry-run 打印计划、默认走回收站、路径全部用 pathlib 校验、操作写审计日志' />

## 随堂检测

<Quiz no='123-1' q='在本讲讨论的「pathlib 遍历与 glob」语境下，下面哪一种说法是准确的？' :options='["自动化办公的风险在「批量」：一个错误的匹配规则会在几秒内改动上千个文件，且没有撤销", "pathlib 遍历与 glob 只影响代码的书写形式，不会改变任何运行时行为", "pathlib 遍历与 glob 在所有 Python 实现与所有版本中表现完全一致", "只要用了 pathlib 遍历与 glob，就不必再考虑 批量重命名安全 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 批量重命名安全 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='123-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["True", "True\n（无更多输出）", "AttributeError: pathlib 遍历与 glob 不可用"]' answer="0" output='True' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='123-3' tpl='import ___io, json' :answers='["async"]' hint='回想本讲关于 pathlib 遍历与 glob 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["pathlib 遍历与 glob：pathlib 遍历与 glob", "os.walk 与元数据：os.walk 与元数据", "按类型容量统计：按类型容量统计", "logging 落盘：logging 落盘"]' :pitfalls='["直接用 os.remove 做清理脚本，路径拼接错一个斜杠就可能删掉目标目录之外的东西", "忽略版本差异，把 批量重命名安全 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：自动化办公的风险在「批量」：一个错误的匹配规则会在几秒内改动上千个文件，且没有撤销' />

## 小结与下一讲

1. pathlib 遍历与 glob：pathlib 遍历与 glob
2. os.walk 与元数据：os.walk 与元数据
3. 先 dry-run 打印计划、默认走回收站、路径全部用 pathlib 校验、操作写审计日志

[下一讲：实战 03 · 邮件、PDF、Excel、Word 与图像视频](/projects/office-docs)
