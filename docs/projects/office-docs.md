---
title: 第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频
description: 串起办公文档的全套自动化流水线
---

<StageHeader stage='L12 · 工程实战' level='★★★☆☆' time='55 分钟' goal='串起办公文档的全套自动化流水线' prereq='第 123 讲 · 实战 02 · 文件检索、日志与自动化办公' />

# 第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频

> 文档自动化的通用套路是「模板 + 数据 + 批量渲染」，把不变的部分留给模板，只让代码填变化字段。本讲的目标是「串起办公文档的全套自动化流水线」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P124' title="本讲目标" :items='["能说清smtplib / yagmail 与授权码", "能说清pypdf 拆分合并", "能说清openpyxl / pandas 读写表格", "能说清python-docx 模板渲染", "能说清Pillow 与二维码"]' />

## 1. 先建立直觉

**smtplib / yagmail 与授权码**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**pypdf 拆分合并**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**openpyxl / pandas 读写表格**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

<ConceptDiagram type='compare2' title='第 124 讲 · smtplib / yagmail 与授权码' labels='smtplib / yagmail 与授权码|pypdf 拆分合并|openpyxl / pandas 读写表格|python-docx 模板渲染' caption='串起办公文档的全套自动化流水线' />

上图用本讲的三个核心概念标出了主线：**smtplib / yagmail 与授权码 → pypdf 拆分合并 → openpyxl / pandas 读写表格**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 smtplib / yagmail 与授权码 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 Namespace(done=False)", "tone": "green"}, {"title": "深入边界", "desc": "厘清 pypdf 拆分合并 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 moviepy 批处理 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**smtplib / yagmail 与授权码**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

```python
import argparse, json, os, tempfile

def save(path, data):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)

p = argparse.ArgumentParser()
p.add_argument("--done", action="store_true")
print(p.parse_args([]))
```

<OutputBox title="运行结果" output='Namespace(done=False)' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='import argparse, json, os, tempfile\n\ndef save(path, data):\n    d = os.path.dirname(path) or "."\n    fd, tmp = tempfile.mkstemp(dir=d)\n    with os.fdopen(fd, "w", encoding="utf-8") as f:\n        json.dump(data, f, ensure_ascii=False)\n    os.replace(tmp, path)\n\np = argparse.ArgumentParser()\np.add_argument("--done", action="store_true")\nprint(p.parse_args([]))' :notes='["临时文件 + os.replace 保证写入原子性", "argparse 把 CLI 契约集中声明", "崩溃时不会留下半截 JSON", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**pypdf 拆分合并**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import json, pathlib
p = pathlib.Path("todos.json")
print(json.loads(p.read_text()) if p.exists() else [])
```

<OutputBox title="对照写法的输出（先自己猜）" output='[]' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "import argparse, json, os, tempfile\n\ndef save(path, data):\n    d = os.path.dirname(path) or \".\"\n    fd, tmp = tempfile.mkstemp(dir=d)\n    with os.fdopen(fd, \"w\", encoding=\"utf-8\") as f:\n        json.dump(data, f, ensure_ascii=False)\n    os.replace(tmp, path)\n\np = argparse.ArgumentParser()\np.add_argument(\"--done\", action=\"store_true\")\nprint(p.parse_args([]))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import json, pathlib\np = pathlib.Path(\"todos.json\")\nprint(json.loads(p.read_text()) if p.exists() else [])", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来凭证」' />

## 3. 深入一步：规则与边界

**openpyxl / pandas 读写表格**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**python-docx 模板渲染**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**Pillow 与二维码**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| smtplib / yagmail 与授权码 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来 |
| pypdf 拆分合并 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来 |
| openpyxl / pandas 读写表格 | 这里的关键词是「什么时候」和「代价是什么」 | 把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来 |
| python-docx 模板渲染 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来 |
| Pillow 与二维码 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来 |

<Term word='smtplib / yagmail 与授权码' text='文档自动化的通用套路是「模板 + 数据 + 批量渲染」，把不变的部分留给模板，只让代码填变化字段' />

<Callout type="warn" title="易错点" text='把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来凭证泄漏与内容错乱' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：smtplib / yagmail 与授权码", "body": "**smtplib / yagmail 与授权码**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：pypdf 拆分合并", "body": "**pypdf 拆分合并**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：openpyxl / pandas 读写表格", "body": "**openpyxl / pandas 读写表格**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：python-docx 模板渲染", "body": "**python-docx 模板渲染**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

凭证走环境变量、模板用 Jinja2、附件做类型与大小校验、批量发送加限速与失败清单 **moviepy 批处理**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -m compileall -q . && python -m pytest -q
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **smtplib / yagmail 与授权码** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「moviepy 批处理」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「moviepy 批处理」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 smtplib / yagmail 与授权码 与 moviepy 批处理 两个关注点，并说明你的取舍。' :hints='["回到 smtplib / yagmail 与授权码 的规则", "留意易错点：把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来凭证泄漏与内", "先让代码跑通，再补边界与异常分支"]' solution='import json, pathlib\np = pathlib.Path("todos.json")\nprint(json.loads(p.read_text()) if p.exists() else [])' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；凭证走环境变量、模板用 Jinja2、附件做类型与大小校验、批量发送加限速与失败清单' />

## 随堂检测

<Quiz no='124-1' q='在本讲讨论的「smtplib / yagmail 与授权码」语境下，下面哪一种说法是准确的？' :options='["文档自动化的通用套路是「模板 + 数据 + 批量渲染」，把不变的部分留给模板，只让代码填变化字段", "smtplib / yagmail 与授权码 只影响代码的书写形式，不会改变任何运行时行为", "smtplib / yagmail 与授权码 在所有 Python 实现与所有版本中表现完全一致", "只要用了 smtplib / yagmail 与授权码，就不必再考虑 moviepy 批处理 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 moviepy 批处理 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='124-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["Namespace(done=False)", "Namespace(done=False)\n（无更多输出）", "AttributeError: smtplib / yagmail 与授权码 不可用"]' answer="0" output='Namespace(done=False)' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='124-3' tpl='___argparse, json, os, tempfile' :answers='["import"]' hint='回想本讲关于 smtplib / yagmail 与授权码 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["smtplib / yagmail 与授权码：smtplib / yagmail 与授权码", "pypdf 拆分合并：pypdf 拆分合并", "openpyxl / pandas 读写表格：openpyxl / pandas 读写表格", "python-docx 模板渲染：python-docx 模板渲染"]' :pitfalls='["把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来凭证泄漏与内容错乱", "忽略版本差异，把 moviepy 批处理 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：文档自动化的通用套路是「模板 + 数据 + 批量渲染」，把不变的部分留给模板，只让代码填变化字段' />

## 小结与下一讲

1. smtplib / yagmail 与授权码：smtplib / yagmail 与授权码
2. pypdf 拆分合并：pypdf 拆分合并
3. 凭证走环境变量、模板用 Jinja2、附件做类型与大小校验、批量发送加限速与失败清单

[下一讲：实战 04 · Selenium 表单自动化与定时任务](/projects/browser-auto)
