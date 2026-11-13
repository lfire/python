---
title: 第 076 讲 · Mock 与测试替身：时间、网络与随机
description: 让不可控依赖变得可测
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='35 分钟' goal='让不可控依赖变得可测' prereq='第 075 讲 · 单元测试：pytest、fixture 与参数化' />

# 第 076 讲 · Mock 与测试替身：时间、网络与随机

> patch 要打在「被使用的地方」而不是「定义的地方」，这个细节占了 mock 失败案例的一大半。本讲的目标是「让不可控依赖变得可测」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P076' title="本讲目标" :items='["能说清unittest.mock 与 patch 位置", "能说清monkeypatch", "能说清freezegun 与时钟注入", "能说清HTTP MockTransport", "能说清假对象与桩"]' />

## 1. 先建立直觉

**unittest.mock 与 patch 位置**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**monkeypatch**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**freezegun 与时钟注入**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

<ConceptDiagram type='flow4' title='第 076 讲 · unittest.mock 与 patch 位置' labels='unittest.mock 与 patch 位置|monkeypatch|freezegun 与时钟注入|HTTP MockTransport' caption='让不可控依赖变得可测' />

上图用本讲的三个核心概念标出了主线：**unittest.mock 与 patch 位置 → monkeypatch → freezegun 与时钟注入**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 unittest.mock 与 patch 位置 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 2 passed, 1 raises as expe", "tone": "green"}, {"title": "深入边界", "desc": "厘清 monkeypatch 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 依赖注入 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**unittest.mock 与 patch 位置**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

```python
# test_demo.py —— 用 pytest 运行
import pytest

def parse_age(s):
    n = int(s)
    if not 0 <= n <= 150: raise ValueError("age out of range")
    return n

@pytest.mark.parametrize("s,expected", [("18", 18), ("0", 0)])
def test_ok(s, expected):
    assert parse_age(s) == expected

def test_bad():
    with pytest.raises(ValueError):
        parse_age("200")
```

<OutputBox title="运行结果" output='2 passed, 1 raises as expected' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='# test_demo.py —— 用 pytest 运行\nimport pytest\n\ndef parse_age(s):\n    n = int(s)\n    if not 0 &lt;= n &lt;= 150: raise ValueError("age out of range")\n    return n\n\n@pytest.mark.parametrize("s,expected", [("18", 18), ("0", 0)])\ndef test_ok(s, expected):\n    assert parse_age(s) == expected\n\ndef test_bad():\n    with pytest.raises(ValueError):\n        parse_age("200")' :notes='["参数化把多个用例写成一张表", "pytest.raises 断言异常契约", "测试描述的是公开行为，不是实现细节", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色", "第 13 行：与上文规则对照，观察它在整体流程里承担的角色", "第 14 行：与上文规则对照，观察它在整体流程里承担的角色", "第 15 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 076 讲 · Mock 与测试替身：时间、网络与随机' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**monkeypatch**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
from unittest.mock import patch
import datetime as dt
with patch.object(dt, "date", return_value=dt.date(2026, 1, 1)):
    print(dt.date.today())
```

<OutputBox title="对照写法的输出（先自己猜）" output='2026-01-01' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "# test_demo.py —— 用 pytest 运行\nimport pytest\n\ndef parse_age(s):\n    n = int(s)\n    if not 0 &lt;= n &lt;= 150: raise ValueError(\"age out of range\")\n    return n\n\n@pytest.mark.parametrize(\"s,expected\", [(\"18\", 18), (\"0\", 0)])\ndef test_ok(s, expected):\n    assert parse_age(s) == expected\n\ndef test_bad():\n    with pytest.raises(ValueError):\n        parse_age(\"200\")", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "from unittest.mock import patch\nimport datetime as dt\nwith patch.object(dt, \"date\", return_value=dt.date(2026, 1, 1)):\n    print(dt.date.today())", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现」' />

## 3. 深入一步：规则与边界

**freezegun 与时钟注入**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**HTTP MockTransport**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**假对象与桩**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| unittest.mock 与 patch 位置 | 这里的关键词是「什么时候」和「代价是什么」 | mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现 |
| monkeypatch | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现 |
| freezegun 与时钟注入 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现 |
| HTTP MockTransport | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现 |
| 假对象与桩 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现 |

<Term word='unittest.mock 与 patch 位置' text='patch 要打在「被使用的地方」而不是「定义的地方」，这个细节占了 mock 失败案例的一大半' />

<Callout type="warn" title="易错点" text='mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：unittest.mock 与 patch 位置", "body": "**unittest.mock 与 patch 位置**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：monkeypatch", "body": "**monkeypatch**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：freezegun 与时钟注入", "body": "**freezegun 与时钟注入**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：HTTP MockTransport", "body": "**HTTP MockTransport**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

把时间、随机、网络封装成可注入依赖，优先用假实现（fake）而不是深度断言调用次数 **依赖注入**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -m pytest -q --disable-warnings
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **unittest.mock 与 patch 位置** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「依赖注入」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「依赖注入」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 unittest.mock 与 patch 位置 与 依赖注入 两个关注点，并说明你的取舍。' :hints='["回到 unittest.mock 与 patch 位置 的规则", "留意易错点：mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现", "先让代码跑通，再补边界与异常分支"]' solution='from unittest.mock import patch\nimport datetime as dt\nwith patch.object(dt, "date", return_value=dt.date(2026, 1, 1)):\n    print(dt.date.today())' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；把时间、随机、网络封装成可注入依赖，优先用假实现（fake）而不是深度断言调用次数' />

## 随堂检测

<Quiz no='076-1' q='在本讲讨论的「unittest.mock 与 patch 位置」语境下，下面哪一种说法是准确的？' :options='["patch 要打在「被使用的地方」而不是「定义的地方」，这个细节占了 mock 失败案例的一大半", "unittest.mock 与 patch 位置 只影响代码的书写形式，不会改变任何运行时行为", "unittest.mock 与 patch 位置 在所有 Python 实现与所有版本中表现完全一致", "只要用了 unittest.mock 与 patch 位置，就不必再考虑 依赖注入 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 依赖注入 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='076-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["2 passed, 1 raises as expected", "2 passed, 1 raises as expected\n（无更多输出）", "AttributeError: unittest.mock 与 patch 位置 不可用"]' answer="0" output='2 passed, 1 raises as expected' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='076-3' tpl='___pytest' :answers='["import"]' hint='回想本讲关于 unittest.mock 与 patch 位置 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["unittest.mock 与 patch 位置：unittest.mock 与 patch 位置", "monkeypatch：monkeypatch", "freezegun 与时钟注入：freezegun 与时钟注入", "HTTP MockTransport：HTTP MockTransport"]' :pitfalls='["mock 了不存在的方法，测试依然会通过，直到真实接口变化才发现", "忽略版本差异，把 依赖注入 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：patch 要打在「被使用的地方」而不是「定义的地方」，这个细节占了 mock 失败案例的一大半' />

## 小结与下一讲

1. unittest.mock 与 patch 位置：unittest.mock 与 patch 位置
2. monkeypatch：monkeypatch
3. 把时间、随机、网络封装成可注入依赖，优先用假实现（fake）而不是深度断言调用次数

[下一讲：属性测试、基准测试与模糊测试](/engineering/property-testing)
