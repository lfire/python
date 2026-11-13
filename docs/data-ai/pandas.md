---
title: 第 094 讲 · Pandas 清洗、分组、透视与时间序列
description: 把脏数据变成可分析的数据集
---

<StageHeader stage='L9 · 数据与 AI' level='★★★☆☆' time='45 分钟' goal='把脏数据变成可分析的数据集' prereq='第 093 讲 · NumPy 向量化、广播与内存布局' />

# 第 094 讲 · Pandas 清洗、分组、透视与时间序列

> Pandas 的核心心智模型是「带标签的对齐运算」：很多诡异的 NaN 都来自索引没对齐而不是数据缺失。本讲的目标是「把脏数据变成可分析的数据集」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P094' title="本讲目标" :items='["能说清Series 与 DataFrame 索引", "能说清缺失值与重复", "能说清groupby / agg / transform", "能说清merge 与 join", "能说清透视与重采样"]' />

## 1. 先建立直觉

**Series 与 DataFrame 索引**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**缺失值与重复**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**groupby / agg / transform**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

<ConceptDiagram type='compare2' title='第 094 讲 · Series 与 DataFrame 索引' labels='Series 与 DataFrame 索引|缺失值与重复|groupby / agg / transform|merge 与 join' caption='把脏数据变成可分析的数据集' />

上图用本讲的三个核心概念标出了主线：**Series 与 DataFrame 索引 → 缺失值与重复 → groupby / agg / transform**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 Series 与 DataFrame 索引 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对       mean  max", "tone": "green"}, {"title": "深入边界", "desc": "厘清 缺失值与重复 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 类型与内存优化 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**Series 与 DataFrame 索引**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

```python
import pandas as pd
df = pd.DataFrame({"city": ["A", "A", "B"],
                   "price": [10, 20, 30]})
print(df.groupby("city")["price"].agg(["mean", "max"]))
```

<OutputBox title="运行结果" output='      mean  max\ncity           \nA      15.0   20\nB      30.0   30' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='import pandas as pd\ndf = pd.DataFrame({"city": ["A", "A", "B"],\n                   "price": [10, 20, 30]})\nprint(df.groupby("city")["price"].agg(["mean", "max"]))' :notes='["groupby 按标签对齐后聚合", "agg 可一次给出多个统计量", "索引是 Pandas 运算对齐的核心", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 094 讲 · Pandas 清洗、分组、透视与时间序列' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**缺失值与重复**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import pandas as pd
s = pd.Series([1, None, 3])
print(s.fillna(s.mean()).tolist())
```

<OutputBox title="对照写法的输出（先自己猜）" output='[1.0, 2.0, 3.0]' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "import pandas as pd\ndf = pd.DataFrame({\"city\": [\"A\", \"A\", \"B\"],\n                   \"price\": [10, 20, 30]})\nprint(df.groupby(\"city\")[\"price\"].agg([\"mean\", \"max\"]))", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import pandas as pd\ns = pd.Series([1, None, 3])\nprint(s.fillna(s.mean()).tolist())", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「用 inplace 链式操作、或在循环里逐行 iterrows，既慢又容」' />

## 3. 深入一步：规则与边界

**groupby / agg / transform**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**merge 与 join**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**透视与重采样**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| Series 与 DataFrame 索引 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 用 inplace 链式操作、或在循环里逐行 iterrows，既慢 |
| 缺失值与重复 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 用 inplace 链式操作、或在循环里逐行 iterrows，既慢 |
| groupby / agg / transform | 这里的关键词是「什么时候」和「代价是什么」 | 用 inplace 链式操作、或在循环里逐行 iterrows，既慢 |
| merge 与 join | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 用 inplace 链式操作、或在循环里逐行 iterrows，既慢 |
| 透视与重采样 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 用 inplace 链式操作、或在循环里逐行 iterrows，既慢 |

<Term word='Series 与 DataFrame 索引' text='Pandas 的核心心智模型是「带标签的对齐运算」：很多诡异的 NaN 都来自索引没对齐而不是数据缺失' />

<Callout type="warn" title="易错点" text='用 inplace 链式操作、或在循环里逐行 iterrows，既慢又容易产生 SettingWithCopy 警告下的静默错误' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：Series 与 DataFrame 索引", "body": "**Series 与 DataFrame 索引**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：缺失值与重复", "body": "**缺失值与重复**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：groupby / agg / transform", "body": "**groupby / agg / transform**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：merge 与 join", "body": "**merge 与 join**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

先定 schema 与索引，再做缺失策略，分组聚合一次成型；大表用 category / 分块 / Polars **类型与内存优化**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import statistics as s; print(s.mean([1,2,3,100]), s.median([1,2,3,100]))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **Series 与 DataFrame 索引** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「类型与内存优化」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「类型与内存优化」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 Series 与 DataFrame 索引 与 类型与内存优化 两个关注点，并说明你的取舍。' :hints='["回到 Series 与 DataFrame 索引 的规则", "留意易错点：用 inplace 链式操作、或在循环里逐行 iterrows，既慢又容易产生 ", "先让代码跑通，再补边界与异常分支"]' solution='import pandas as pd\ns = pd.Series([1, None, 3])\nprint(s.fillna(s.mean()).tolist())' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；先定 schema 与索引，再做缺失策略，分组聚合一次成型；大表用 category / 分块 / Polars' />

## 随堂检测

<Quiz no='094-1' q='在本讲讨论的「Series 与 DataFrame 索引」语境下，下面哪一种说法是准确的？' :options='["Pandas 的核心心智模型是「带标签的对齐运算」：很多诡异的 NaN 都来自索引没对齐而不是数据缺失", "Series 与 DataFrame 索引 只影响代码的书写形式，不会改变任何运行时行为", "Series 与 DataFrame 索引 在所有 Python 实现与所有版本中表现完全一致", "只要用了 Series 与 DataFrame 索引，就不必再考虑 类型与内存优化 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 类型与内存优化 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='094-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["      mean  max\ncity           \nA      15.0   20\nB      30.0   30", "      mean  max\n（无更多输出）", "AttributeError: Series 与 DataFrame 索引 不可用"]' answer="0" output='      mean  max\ncity           \nA      15.0   20\nB      30.0   30' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='094-3' tpl='___pandas as pd' :answers='["import"]' hint='回想本讲关于 Series 与 DataFrame 索引 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["Series 与 DataFrame 索引：Series 与 DataFrame 索引", "缺失值与重复：缺失值与重复", "groupby / agg / transform：groupby / agg / transform", "merge 与 join：merge 与 join"]' :pitfalls='["用 inplace 链式操作、或在循环里逐行 iterrows，既慢又容易产生 SettingWithCopy 警告下的静默错误", "忽略版本差异，把 类型与内存优化 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：Pandas 的核心心智模型是「带标签的对齐运算」：很多诡异的 NaN 都来自索引没对齐而不是数据缺失' />

## 小结与下一讲

1. Series 与 DataFrame 索引：Series 与 DataFrame 索引
2. 缺失值与重复：缺失值与重复
3. 先定 schema 与索引，再做缺失策略，分组聚合一次成型；大表用 category / 分块 / Polars

[下一讲：可视化：Matplotlib / Seaborn / Plotly 与图表选型](/data-ai/visualization)
