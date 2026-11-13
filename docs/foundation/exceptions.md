---
title: 第 015 讲 · 异常：捕获、异常链与自定义异常
description: 建立 EAFP 风格的错误处理直觉
---

<StageHeader stage='L1 · 编程地基' level='★★☆☆☆' time='30 分钟' goal='建立 EAFP 风格的错误处理直觉' prereq='第 014 讲 · 输入输出与文件初识：print、input、open、with' />

# 第 015 讲 · 异常：捕获、异常链与自定义异常

> Python 鼓励先做再补救（EAFP）：异常在正常路径上几乎零成本，而层层预检查既慢又容易有竞态。本讲的目标是「建立 EAFP 风格的错误处理直觉」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P015' title="本讲目标" :items='["能说清异常层级与 BaseException", "能说清try / except / else / finally", "能说清raise from 与异常链", "能说清自定义异常类", "能说清EAFP 与 LBYL"]' />

## 1. 先建立直觉

**异常层级与 BaseException**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**try / except / else / finally**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**raise from 与异常链**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

<ConceptDiagram type='flow3' title='第 015 讲 · 异常层级与 BaseException' labels='异常层级与 BaseException|try / except / else / finally|raise from 与异常链|自定义异常类' caption='建立 EAFP 风格的错误处理直觉' />

上图用本讲的三个核心概念标出了主线：**异常层级与 BaseException → try / except / else / finally → raise from 与异常链**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 异常层级与 BaseException 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 1 -1", "tone": "green"}, {"title": "深入边界", "desc": "厘清 try / except / else / finally 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 异常的性能开销 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**异常层级与 BaseException**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

```python
def find(xs, target):
    for i, x in enumerate(xs):
        if x == target:
            return i
    else:
        return -1

print(find([3, 5, 7], 5), find([3, 5], 9))
```

<OutputBox title="运行结果" output='1 -1' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='def find(xs, target):\n    for i, x in enumerate(xs):\n        if x == target:\n            return i\n    else:\n        return -1\n\nprint(find([3, 5, 7], 5), find([3, 5], 9))' :notes='["for-else 只在未被 break 时执行", "早返回让主路径更清晰", "else 天然表达「找完了但没找到」", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 015 讲 · 异常：捕获、异常链与自定义异常' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**try / except / else / finally**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
try:
    n = int("12a")
except ValueError as e:
    print("bad input:", e)
else:
    print("ok", n)
```

<OutputBox title="对照写法的输出（先自己猜）" output='bad input: invalid literal for int() with base 10: &#39;12a&#39;' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "def find(xs, target):\n    for i, x in enumerate(xs):\n        if x == target:\n            return i\n    else:\n        return -1\n\nprint(find([3, 5, 7], 5), find([3, 5], 9))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "try:\n    n = int(\"12a\")\nexcept ValueError as e:\n    print(\"bad input:\", e)\nelse:\n    print(\"ok\", n)", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「用裸 except 或 except Exception 吞掉一切，会把」' />

## 3. 深入一步：规则与边界

**raise from 与异常链**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**自定义异常类**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**EAFP 与 LBYL**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| 异常层级与 BaseException | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 用裸 except 或 except Exception 吞掉一切， |
| try / except / else / finally | 这里的关键词是「什么时候」和「代价是什么」 | 用裸 except 或 except Exception 吞掉一切， |
| raise from 与异常链 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 用裸 except 或 except Exception 吞掉一切， |
| 自定义异常类 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 用裸 except 或 except Exception 吞掉一切， |
| EAFP 与 LBYL | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 用裸 except 或 except Exception 吞掉一切， |

<Term word='异常层级与 BaseException' text='Python 鼓励先做再补救（EAFP）：异常在正常路径上几乎零成本，而层层预检查既慢又容易有竞态' />

<Callout type="warn" title="易错点" text='用裸 except 或 except Exception 吞掉一切，会把键盘中断与编程错误一起藏起来，排障时只剩一个沉默的系统' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：异常层级与 BaseException", "body": "**异常层级与 BaseException**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：try / except / else / finally", "body": "**try / except / else / finally**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：raise from 与异常链", "body": "**raise from 与异常链**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：自定义异常类", "body": "**自定义异常类**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}]' />

<ArchBlueprint title='第 015 讲 · 分层视角' caption='把「异常层级与 BaseException」放进系统分层里看' :layers='[{"name": "入口层", "note": "请求与使用方式", "protocol": "函数调用 / HTTP", "items": [{"label": "异常层级与 BaseEx", "sub": "对外接口", "detail": "**异常层级与 BaseException**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」", "tone": "blue"}]}, {"name": "逻辑层", "note": "规则、状态与校验", "protocol": "Python 对象协议", "items": [{"label": "try / except", "sub": "核心处理", "detail": "**try / except / else / finally**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推", "tone": "purple"}]}, {"name": "资源层", "note": "数据、IO 与失败处理", "items": [{"label": "异常的性能开销", "sub": "落地与收尾", "detail": "库代码定义自己的异常基类，边界层统一转成错误码与日志；finally 只做资源释放，不放业务逻辑", "tone": "green"}]}]' />

## 4. 工程实践

库代码定义自己的异常基类，边界层统一转成错误码与日志；finally 只做资源释放，不放业务逻辑 **异常的性能开销**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -X importtime -c "print('ok')" 2>&1 | tail -3
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **异常层级与 BaseException** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「异常的性能开销」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「异常的性能开销」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 异常层级与 BaseException 与 异常的性能开销 两个关注点，并说明你的取舍。' :hints='["回到 异常层级与 BaseException 的规则", "留意易错点：用裸 except 或 except Exception 吞掉一切，会把键盘中断", "先让代码跑通，再补边界与异常分支"]' solution='try:\n    n = int("12a")\nexcept ValueError as e:\n    print("bad input:", e)\nelse:\n    print("ok", n)' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；库代码定义自己的异常基类，边界层统一转成错误码与日志；finally 只做资源释放，不放业务逻辑' />

## 随堂检测

<Quiz no='015-1' q='在本讲讨论的「异常层级与 BaseException」语境下，下面哪一种说法是准确的？' :options='["Python 鼓励先做再补救（EAFP）：异常在正常路径上几乎零成本，而层层预检查既慢又容易有竞态", "异常层级与 BaseException 只影响代码的书写形式，不会改变任何运行时行为", "异常层级与 BaseException 在所有 Python 实现与所有版本中表现完全一致", "只要用了 异常层级与 BaseException，就不必再考虑 异常的性能开销 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 异常的性能开销 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='015-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["1 -1", "1 -1\n（无更多输出）", "AttributeError: 异常层级与 BaseException 不可用"]' answer="0" output='1 -1' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='015-3' tpl='___find(xs, target):' :answers='["def"]' hint='回想本讲关于 异常层级与 BaseException 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["异常层级与 BaseException：异常层级与 BaseException", "try / except / else / finally：try / except / else / finally", "raise from 与异常链：raise from 与异常链", "自定义异常类：自定义异常类"]' :pitfalls='["用裸 except 或 except Exception 吞掉一切，会把键盘中断与编程错误一起藏起来，排障时只剩一个沉默的系统", "忽略版本差异，把 异常的性能开销 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：Python 鼓励先做再补救（EAFP）：异常在正常路径上几乎零成本，而层层预检查既慢又容易有竞态' />

## 小结与下一讲

1. 异常层级与 BaseException：异常层级与 BaseException
2. try / except / else / finally：try / except / else / finally
3. 库代码定义自己的异常基类，边界层统一转成错误码与日志；finally 只做资源释放，不放业务逻辑

[下一讲：阶段综合：交互式命令行计算器](/foundation/capstone)
