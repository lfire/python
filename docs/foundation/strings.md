---
title: 第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义
description: 能定位并解决绝大多数乱码问题
---

<StageHeader stage='L1 · 编程地基' level='★★☆☆☆' time='30 分钟' goal='能定位并解决绝大多数乱码问题' prereq='第 008 讲 · 数值体系：int 任意精度、float、Decimal 与 bool' />

# 第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义

> str 是字符序列，bytes 是字节序列，二者之间必须显式编码/解码；Python 3 把这条边界画得很清楚，正是为了消灭 Python 2 时代的隐式转换。本讲的目标是「能定位并解决绝大多数乱码问题」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P009' title="本讲目标" :items='["能说清Unicode 码点与编码", "能说清str 与 bytes 的边界", "能说清encode / decode", "能说清UTF-8 与 BOM", "能说清raw 字符串与转义"]' />

## 1. 先建立直觉

**Unicode 码点与编码**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**str 与 bytes 的边界**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**encode / decode**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

<ConceptDiagram type='compare2' title='第 009 讲 · Unicode 码点与编码' labels='Unicode 码点与编码|str 与 bytes 的边界|encode / decode|UTF-8 与 BOM' caption='能定位并解决绝大多数乱码问题' />

上图用本讲的三个核心概念标出了主线：**Unicode 码点与编码 → str 与 bytes 的边界 → encode / decode**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 Unicode 码点与编码 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 第一行", "tone": "green"}, {"title": "深入边界", "desc": "厘清 str 与 bytes 的边界 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 多行字符串 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**Unicode 码点与编码**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

```python
from pathlib import Path
p = Path("data") / "report.txt"
with p.open("w", encoding="utf-8") as f:
    f.write("第一行" + chr(10))
with p.open(encoding="utf-8") as f:
    print(f.read().strip())
```

<OutputBox title="运行结果" output='第一行' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='from pathlib import Path\np = Path("data") / "report.txt"\nwith p.open("w", encoding="utf-8") as f:\n    f.write("第一行" + chr(10))\nwith p.open(encoding="utf-8") as f:\n    print(f.read().strip())' :notes='["pathlib 用 / 拼路径，跨平台安全", "open 显式指定 encoding，避免默认编码差异", "with 保证异常路径也会关闭文件", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**str 与 bytes 的边界**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
from contextlib import contextmanager

@contextmanager
def tag(name):
    print("enter", name)
    yield
    print("exit", name)

with tag("job"):
    print("work")
```

<OutputBox title="对照写法的输出（先自己猜）" output='enter job\nwork\nexit job' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "from pathlib import Path\np = Path(\"data\") / \"report.txt\"\nwith p.open(\"w\", encoding=\"utf-8\") as f:\n    f.write(\"第一行\" + chr(10))\nwith p.open(encoding=\"utf-8\") as f:\n    print(f.read().strip())", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "from contextlib import contextmanager\n\n@contextmanager\ndef tag(name):\n    print(\"enter\", name)\n    yield\n    print(\"exit\", name)\n\nwith tag(\"job\"):\n    print(\"work\")", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台时突」' />

## 3. 深入一步：规则与边界

**encode / decode**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**UTF-8 与 BOM**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**raw 字符串与转义**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| Unicode 码点与编码 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台 |
| str 与 bytes 的边界 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台 |
| encode / decode | 这里的关键词是「什么时候」和「代价是什么」 | 用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台 |
| UTF-8 与 BOM | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台 |
| raw 字符串与转义 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台 |

<Term word='Unicode 码点与编码' text='str 是字符序列，bytes 是字节序列，二者之间必须显式编码/解码；Python 3 把这条边界画得很清楚，正是为了消灭 Python 2 时代的隐式转换' />

<Callout type="warn" title="易错点" text='用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台时突然乱码' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：Unicode 码点与编码", "body": "**Unicode 码点与编码**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：str 与 bytes 的边界", "body": "**str 与 bytes 的边界**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：encode / decode", "body": "**encode / decode**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：UTF-8 与 BOM", "body": "**UTF-8 与 BOM**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

工程上统一 UTF-8：源码、文件 IO、HTTP 头、数据库连接四处都要显式声明，边界处做一次转换 **多行字符串**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "s='中文'; b=s.encode('utf-8'); print(len(s), len(b), b.hex())"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **Unicode 码点与编码** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「多行字符串」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「多行字符串」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 Unicode 码点与编码 与 多行字符串 两个关注点，并说明你的取舍。' :hints='["回到 Unicode 码点与编码 的规则", "留意易错点：用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台时突然乱码", "先让代码跑通，再补边界与异常分支"]' solution='from contextlib import contextmanager\n\n@contextmanager\ndef tag(name):\n    print("enter", name)\n    yield\n    print("exit", name)\n\nwith tag("job"):\n    print("work")' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；工程上统一 UTF-8：源码、文件 IO、HTTP 头、数据库连接四处都要显式声明，边界处做一次转换' />

## 随堂检测

<Quiz no='009-1' q='在本讲讨论的「Unicode 码点与编码」语境下，下面哪一种说法是准确的？' :options='["str 是字符序列，bytes 是字节序列，二者之间必须显式编码/解码；Python 3 把这条边界画得很清楚，正是为了消灭 Python 2 时代的隐式转", "Unicode 码点与编码 只影响代码的书写形式，不会改变任何运行时行为", "Unicode 码点与编码 在所有 Python 实现与所有版本中表现完全一致", "只要用了 Unicode 码点与编码，就不必再考虑 多行字符串 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 多行字符串 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='009-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["第一行", "第一行\n（无更多输出）", "AttributeError: Unicode 码点与编码 不可用"]' answer="0" output='第一行' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='009-3' tpl='from pathlib ___Path' :answers='["import"]' hint='回想本讲关于 Unicode 码点与编码 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["Unicode 码点与编码：Unicode 码点与编码", "str 与 bytes 的边界：str 与 bytes 的边界", "encode / decode：encode / decode", "UTF-8 与 BOM：UTF-8 与 BOM"]' :pitfalls='["用 str 去拼接 bytes、或用系统默认编码打开文件，会在跨平台时突然乱码", "忽略版本差异，把 多行字符串 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：str 是字符序列，bytes 是字节序列，二者之间必须显式编码/解码；Python 3 把这条边界画得很清楚，正是为了消灭 Python 2 时代的隐式转换' />

## 小结与下一讲

1. Unicode 码点与编码：Unicode 码点与编码
2. str 与 bytes 的边界：str 与 bytes 的边界
3. 工程上统一 UTF-8：源码、文件 IO、HTTP 头、数据库连接四处都要显式声明，边界处做一次转换

[下一讲：字符串操作：切片、f-string 与常用方法](/foundation/string-ops)
