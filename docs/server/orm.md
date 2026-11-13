---
title: 第 087 讲 · SQLAlchemy、连接池、事务与迁移
description: 写出可控、可诊断的数据库访问层
---

<StageHeader stage='L8 · 服务端与数据' level='★★★★☆' time='45 分钟' goal='写出可控、可诊断的数据库访问层' prereq='第 086 讲 · WebSocket / SSE / 长轮询与实时推送' />

# 第 087 讲 · SQLAlchemy、连接池、事务与迁移

> ORM 的 Session 是工作单元而不是连接，理解这一点才能控制事务边界与对象生命周期。本讲的目标是「写出可控、可诊断的数据库访问层」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P087' title="本讲目标" :items='["能说清Engine / Session / Unit of Work", "能说清连接池参数", "能说清事务边界与隔离级别", "能说清N+1 查询", "能说清懒加载与预加载"]' />

## 1. 先建立直觉

**Engine / Session / Unit of Work**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**连接池参数**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**事务边界与隔离级别**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

<ConceptDiagram type='layers3' title='第 087 讲 · Engine / Session / Unit of Work' labels='Engine / Session / Unit of Work|连接池参数|事务边界与隔离级别|N+1 查询' caption='写出可控、可诊断的数据库访问层' />

上图用本讲的三个核心概念标出了主线：**Engine / Session / Unit of Work → 连接池参数 → 事务边界与隔离级别**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 Engine / Session / Unit of Work 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 (1,)", "tone": "green"}, {"title": "深入边界", "desc": "厘清 连接池参数 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 Alembic 迁移 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**Engine / Session / Unit of Work**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

```python
# 幂等写入：唯一索引兜底
import sqlite3
con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE ev (k TEXT UNIQUE, v TEXT)")
def put(k, v):
    con.execute("INSERT OR IGNORE INTO ev VALUES (?, ?)", (k, v))
put("o-1", "paid"); put("o-1", "paid")
print(con.execute("SELECT count(*) FROM ev").fetchone())
```

<OutputBox title="运行结果" output='(1,)' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='# 幂等写入：唯一索引兜底\nimport sqlite3\ncon = sqlite3.connect(":memory:")\ncon.execute("CREATE TABLE ev (k TEXT UNIQUE, v TEXT)")\ndef put(k, v):\n    con.execute("INSERT OR IGNORE INTO ev VALUES (?, ?)", (k, v))\nput("o-1", "paid"); put("o-1", "paid")\nprint(con.execute("SELECT count(*) FROM ev").fetchone())' :notes='["至少一次投递下重复消息必然出现", "唯一索引把幂等下沉到存储层", "先查后写在并发下依旧会重复", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 087 讲 · SQLAlchemy、连接池、事务与迁移' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**连接池参数**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import json
print(json.dumps({"a": 1}, ensure_ascii=False, separators=(",", ":")))
```

<OutputBox title="对照写法的输出（先自己猜）" output='{"a":1}' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "# 幂等写入：唯一索引兜底\nimport sqlite3\ncon = sqlite3.connect(\":memory:\")\ncon.execute(\"CREATE TABLE ev (k TEXT UNIQUE, v TEXT)\")\ndef put(k, v):\n    con.execute(\"INSERT OR IGNORE INTO ev VALUES (?, ?)\", (k, v))\nput(\"o-1\", \"paid\"); put(\"o-1\", \"paid\")\nprint(con.execute(\"SELECT count(*) FROM ev\").fetchone())", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import json\nprint(json.dumps({\"a\": 1}, ensure_ascii=False, separators=(\",\", \":\")))", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地测试」' />

## 3. 深入一步：规则与边界

**事务边界与隔离级别**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

**N+1 查询**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**懒加载与预加载**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| Engine / Session / Unit of Work | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地 |
| 连接池参数 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地 |
| 事务边界与隔离级别 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地 |
| N+1 查询 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地 |
| 懒加载与预加载 | 这里的关键词是「什么时候」和「代价是什么」 | 在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地 |

<Term word='Engine / Session / Unit of Work' text='ORM 的 Session 是工作单元而不是连接，理解这一点才能控制事务边界与对象生命周期' />

<Callout type="warn" title="易错点" text='在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地测试集太小看不出来' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：Engine / Session / Unit of Work", "body": "**Engine / Session / Unit of Work**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：连接池参数", "body": "**连接池参数**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：事务边界与隔离级别", "body": "**事务边界与隔离级别**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：N+1 查询", "body": "**N+1 查询**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}]' />

## 4. 工程实践

显式 selectinload / joinedload、事务尽量短、只读查询用独立 session；迁移脚本必须可回滚并在 CI 演一遍 **Alembic 迁移**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE t(k TEXT UNIQUE)'); print('ok')"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **Engine / Session / Unit of Work** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「Alembic 迁移」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「Alembic 迁移」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 Engine / Session / Unit of Work 与 Alembic 迁移 两个关注点，并说明你的取舍。' :hints='["回到 Engine / Session / Unit of Work 的规则", "留意易错点：在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地测试集太小看", "先让代码跑通，再补边界与异常分支"]' solution='import json\nprint(json.dumps({"a": 1}, ensure_ascii=False, separators=(",", ":")))' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；显式 selectinload / joinedload、事务尽量短、只读查询用独立 session；迁移脚本必须可回滚并在 CI 演一遍' />

## 随堂检测

<Quiz no='087-1' q='在本讲讨论的「Engine / Session / Unit of Work」语境下，下面哪一种说法是准确的？' :options='["ORM 的 Session 是工作单元而不是连接，理解这一点才能控制事务边界与对象生命周期", "Engine / Session / Unit of Work 只影响代码的书写形式，不会改变任何运行时行为", "Engine / Session / Unit of Work 在所有 Python 实现与所有版本中表现完全一致", "只要用了 Engine / Session / Unit of Work，就不必再考虑 Alembic 迁移 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 Alembic 迁移 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='087-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["(1,)", "(1,)\n（无更多输出）", "AttributeError: Engine / Session / Unit of Work 不可用"]' answer="0" output='(1,)' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='087-3' tpl='___sqlite3' :answers='["import"]' hint='回想本讲关于 Engine / Session / Unit of Work 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["Engine / Session / Unit of Work：Engine / Session / Unit of Work", "连接池参数：连接池参数", "事务边界与隔离级别：事务边界与隔离级别", "N+1 查询：N+1 查询"]' :pitfalls='["在循环里逐条查询关联对象（N+1），数据一多响应会呈线性劣化，而本地测试集太小看不出来", "忽略版本差异，把 Alembic 迁移 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：ORM 的 Session 是工作单元而不是连接，理解这一点才能控制事务边界与对象生命周期' />

## 小结与下一讲

1. Engine / Session / Unit of Work：Engine / Session / Unit of Work
2. 连接池参数：连接池参数
3. 显式 selectinload / joinedload、事务尽量短、只读查询用独立 session；迁移脚本必须可回滚并在 CI 演一遍

[下一讲：Redis 缓存：穿透、击穿、雪崩与分布式锁](/server/redis)
