---
title: 第 046 讲 · 反射与自省：getattr、inspect 与 __dict__
description: 构建可插拔的框架式代码
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='30 分钟' goal='构建可插拔的框架式代码' prereq='第 045 讲 · 元类：__new__、type 与类创建过程' />

# 第 046 讲 · 反射与自省：getattr、inspect 与 __dict__

> 自省让框架可以在不知道具体类型的前提下发现能力，插件系统、序列化器与 CLI 路由都依赖它。本讲的目标是「构建可插拔的框架式代码」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P046' title="本讲目标" :items='["能说清getattr / setattr / hasattr", "能说清inspect.signature 与 getmembers", "能说清__dict__ 与 vars", "能说清动态导入 importlib", "能说清函数注解读取"]' />

## 1. 先建立直觉

**getattr / setattr / hasattr**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**inspect.signature 与 getmembers**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**__dict__ 与 vars**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

<ConceptDiagram type='flow4' title='第 046 讲 · getattr / setattr / hasattr' labels='getattr / setattr / hasattr|inspect.signature 与 getmembers|__dict__ 与 vars|动态导入 importlib' caption='构建可插拔的框架式代码' />

上图用本讲的三个核心概念标出了主线：**getattr / setattr / hasattr → inspect.signature 与 getmembers → __dict__ 与 vars**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 getattr / setattr / hasattr 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 False json", "tone": "green"}, {"title": "深入边界", "desc": "厘清 inspect.signature 与 getmembers 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 反射的边界 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**getattr / setattr / hasattr**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

```python
# pkg/__init__.py 只做轻量导出，重依赖延迟到函数内部
# pkg/core.py
import importlib, sys

def load(name):
    return importlib.import_module(name)

print("json" in sys.modules, load("json").__name__)
```

<OutputBox title="运行结果" output='False json' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='# pkg/__init__.py 只做轻量导出，重依赖延迟到函数内部\n# pkg/core.py\nimport importlib, sys\n\ndef load(name):\n    return importlib.import_module(name)\n\nprint("json" in sys.modules, load("json").__name__)' :notes='["importlib 支持运行时按名字加载模块", "sys.modules 是已导入模块的缓存", "顶层保持轻量可显著缩短启动时间", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 046 讲 · 反射与自省：getattr、inspect 与 __dict__' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**inspect.signature 与 getmembers**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
from typing import Protocol

class Sized(Protocol):
    def __len__(self) -> int: ...

def size(x: Sized) -> int:
    return len(x)

print(size([1, 2, 3]))
```

<OutputBox title="对照写法的输出（先自己猜）" output='3' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "# pkg/__init__.py 只做轻量导出，重依赖延迟到函数内部\n# pkg/core.py\nimport importlib, sys\n\ndef load(name):\n    return importlib.import_module(name)\n\nprint(\"json\" in sys.modules, load(\"json\").__name__)", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "from typing import Protocol\n\nclass Sized(Protocol):\n    def __len__(self) -&gt; int: ...\n\ndef size(x: Sized) -&gt; int:\n    return len(x)\n\nprint(size([1, 2, 3]))", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法执行」' />

## 3. 深入一步：规则与边界

**__dict__ 与 vars**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**动态导入 importlib**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**函数注解读取**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| getattr / setattr / hasattr | 这里的关键词是「什么时候」和「代价是什么」 | 对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法 |
| inspect.signature 与 getmembers | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法 |
| __dict__ 与 vars | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法 |
| 动态导入 importlib | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法 |
| 函数注解读取 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法 |

<Term word='getattr / setattr / hasattr' text='自省让框架可以在不知道具体类型的前提下发现能力，插件系统、序列化器与 CLI 路由都依赖它' />

<Callout type="warn" title="易错点" text='对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法执行入口' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：getattr / setattr / hasattr", "body": "**getattr / setattr / hasattr**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：inspect.signature 与 getmembers", "body": "**inspect.signature 与 getmembers**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：__dict__ 与 vars", "body": "**__dict__ 与 vars**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：动态导入 importlib", "body": "**动态导入 importlib**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

反射入口要配白名单与显式注册表，把「能被调用什么」收敛到可控集合 **反射的边界**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import importlib.util; print(importlib.util.find_spec('json').origin)"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **getattr / setattr / hasattr** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「反射的边界」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「反射的边界」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 getattr / setattr / hasattr 与 反射的边界 两个关注点，并说明你的取舍。' :hints='["回到 getattr / setattr / hasattr 的规则", "留意易错点：对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法执行入口", "先让代码跑通，再补边界与异常分支"]' solution='from typing import Protocol\n\nclass Sized(Protocol):\n    def __len__(self) -&gt; int: ...\n\ndef size(x: Sized) -&gt; int:\n    return len(x)\n\nprint(size([1, 2, 3]))' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；反射入口要配白名单与显式注册表，把「能被调用什么」收敛到可控集合' />

## 随堂检测

<Quiz no='046-1' q='在本讲讨论的「getattr / setattr / hasattr」语境下，下面哪一种说法是准确的？' :options='["自省让框架可以在不知道具体类型的前提下发现能力，插件系统、序列化器与 CLI 路由都依赖它", "getattr / setattr / hasattr 只影响代码的书写形式，不会改变任何运行时行为", "getattr / setattr / hasattr 在所有 Python 实现与所有版本中表现完全一致", "只要用了 getattr / setattr / hasattr，就不必再考虑 反射的边界 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 反射的边界 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='046-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["False json", "False json\n（无更多输出）", "AttributeError: getattr / setattr / hasattr 不可用"]' answer="0" output='False json' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='046-3' tpl='___importlib, sys' :answers='["import"]' hint='回想本讲关于 getattr / setattr / hasattr 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["getattr / setattr / hasattr：getattr / setattr / hasattr", "inspect.signature 与 getmembers：inspect.signature 与 getmembers", "__dict__ 与 vars：__dict__ 与 vars", "动态导入 importlib：动态导入 importlib"]' :pitfalls='["对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法执行入口", "忽略版本差异，把 反射的边界 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：自省让框架可以在不知道具体类型的前提下发现能力，插件系统、序列化器与 CLI 路由都依赖它' />

## 小结与下一讲

1. getattr / setattr / hasattr：getattr / setattr / hasattr
2. inspect.signature 与 getmembers：inspect.signature 与 getmembers
3. 反射入口要配白名单与显式注册表，把「能被调用什么」收敛到可控集合

[下一讲：dataclass、attrs 与 pydantic 模型](/oop/dataclass)
