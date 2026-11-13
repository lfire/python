---
title: 第 083 讲 · FastAPI / Flask / Django 选型
description: 按团队与场景选框架而不是按热度
---

<StageHeader stage='L8 · 服务端与数据' level='★★☆☆☆' time='30 分钟' goal='按团队与场景选框架而不是按热度' prereq='第 082 讲 · HTTP 协议与 WSGI / ASGI' />

# 第 083 讲 · FastAPI / Flask / Django 选型

> 框架差异主要在「替你决定多少」：Flask 只给内核、FastAPI 把类型注解变成校验与文档、Django 自带全栈约定。本讲的目标是「按团队与场景选框架而不是按热度」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P083' title="本讲目标" :items='["能说清三者定位差异", "能说清路由与依赖注入", "能说清校验与序列化", "能说清ORM 与迁移内置程度", "能说清生态与插件"]' />

## 1. 先建立直觉

**三者定位差异**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**路由与依赖注入**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**校验与序列化**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

<ConceptDiagram type='hub4' title='第 083 讲 · 三者定位差异' labels='三者定位差异|路由与依赖注入|校验与序列化|ORM 与迁移内置程度' caption='按团队与场景选框架而不是按热度' />

上图用本讲的三个核心概念标出了主线：**三者定位差异 → 路由与依赖注入 → 校验与序列化**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 三者定位差异 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 [&#39;http.response.start&#39;, &#39;h", "tone": "green"}, {"title": "深入边界", "desc": "厘清 路由与依赖注入 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 团队成本 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**三者定位差异**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

```python
# ASGI 最小应用（示意）
async def app(scope, receive, send):
    await send({"type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"ok"})

import asyncio
sent = []
async def send(m): sent.append(m)
asyncio.run(app("http", None, send))
print([m["type"] for m in sent])
```

<OutputBox title="运行结果" output='[&#39;http.response.start&#39;, &#39;http.response.body&#39;]' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='# ASGI 最小应用（示意）\nasync def app(scope, receive, send):\n    await send({"type": "http.response.start",\n                "status": 200,\n                "headers": [(b"content-type", b"text/plain")]})\n    await send({"type": "http.response.body", "body": b"ok"})\n\nimport asyncio\nsent = []\nasync def send(m): sent.append(m)\nasyncio.run(app("http", None, send))\nprint([m["type"] for m in sent])' :notes='["ASGI 用消息而不是单一返回值表达响应", "双工消息模型天然支持 SSE 与 WebSocket", "同步栈无法承载长连接，选框架前先确认协议", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 083 讲 · FastAPI / Flask / Django 选型' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**路由与依赖注入**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
from urllib.parse import urlencode
print(urlencode({"q": "python", "page": 2}))
```

<OutputBox title="对照写法的输出（先自己猜）" output='q=python&amp;page=2' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "# ASGI 最小应用（示意）\nasync def app(scope, receive, send):\n    await send({\"type\": \"http.response.start\",\n                \"status\": 200,\n                \"headers\": [(b\"content-type\", b\"text/plain\")]})\n    await send({\"type\": \"http.response.body\", \"body\": b\"ok\"})\n\nimport asyncio\nsent = []\nasync def send(m): sent.append(m)\nasyncio.run(app(\"http\", None, send))\nprint([m[\"type\"] for m in sent])", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "from urllib.parse import urlencode\nprint(urlencode({\"q\": \"python\", \"page\": 2}))", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「微服务里硬套 Django 的整套 ORM 与 admin，会背上用不到」' />

## 3. 深入一步：规则与边界

**校验与序列化**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**ORM 与迁移内置程度**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**生态与插件**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| 三者定位差异 | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 微服务里硬套 Django 的整套 ORM 与 admin，会背上用 |
| 路由与依赖注入 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 微服务里硬套 Django 的整套 ORM 与 admin，会背上用 |
| 校验与序列化 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 微服务里硬套 Django 的整套 ORM 与 admin，会背上用 |
| ORM 与迁移内置程度 | 这里的关键词是「什么时候」和「代价是什么」 | 微服务里硬套 Django 的整套 ORM 与 admin，会背上用 |
| 生态与插件 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 微服务里硬套 Django 的整套 ORM 与 admin，会背上用 |

<Term word='三者定位差异' text='框架差异主要在「替你决定多少」：Flask 只给内核、FastAPI 把类型注解变成校验与文档、Django 自带全栈约定' />

<Callout type="warn" title="易错点" text='微服务里硬套 Django 的整套 ORM 与 admin，会背上用不到的启动与依赖成本' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：三者定位差异", "body": "**三者定位差异**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：路由与依赖注入", "body": "**路由与依赖注入**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：校验与序列化", "body": "**校验与序列化**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：ORM 与迁移内置程度", "body": "**ORM 与迁移内置程度**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}]' />

<SequenceDiagram title='第 083 讲 · 调用时序' caption='从触发到收尾，标出可能失败的位置' :actors='["调用方", "处理逻辑", "依赖资源"]' :steps='[{"from": "调用方", "to": "处理逻辑", "label": "发起调用", "note": "三者定位差异", "kind": "call"}, {"from": "处理逻辑", "to": "处理逻辑", "label": "校验状态", "note": "路由与依赖注入", "kind": "self"}, {"from": "处理逻辑", "to": "依赖资源", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "依赖资源", "to": "处理逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "处理逻辑", "to": "调用方", "label": "返回或失败", "note": "清理资源", "kind": "return"}]' />

## 4. 工程实践

小工具用 Flask、类型化 API 用 FastAPI、内容型后台与快速交付用 Django；同一仓里不要混两套范式 **团队成本**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "from urllib.parse import urlencode; print(urlencode({'page':2}))"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **三者定位差异** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「团队成本」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「团队成本」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 三者定位差异 与 团队成本 两个关注点，并说明你的取舍。' :hints='["回到 三者定位差异 的规则", "留意易错点：微服务里硬套 Django 的整套 ORM 与 admin，会背上用不到的启动与", "先让代码跑通，再补边界与异常分支"]' solution='from urllib.parse import urlencode\nprint(urlencode({"q": "python", "page": 2}))' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；小工具用 Flask、类型化 API 用 FastAPI、内容型后台与快速交付用 Django；同一仓里不要混两套范式' />

## 随堂检测

<Quiz no='083-1' q='在本讲讨论的「三者定位差异」语境下，下面哪一种说法是准确的？' :options='["框架差异主要在「替你决定多少」：Flask 只给内核、FastAPI 把类型注解变成校验与文档、Django 自带全栈约定", "三者定位差异 只影响代码的书写形式，不会改变任何运行时行为", "三者定位差异 在所有 Python 实现与所有版本中表现完全一致", "只要用了 三者定位差异，就不必再考虑 团队成本 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 团队成本 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='083-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["[&#39;http.response.start&#39;, &#39;http.response.body&#39;]", "[&#39;http.response.start&#39;, &#39;http.response.body&#39;]\n（无更多输出）", "AttributeError: 三者定位差异 不可用"]' answer="0" output='[&#39;http.response.start&#39;, &#39;http.response.body&#39;]' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='083-3' tpl='___ def app(scope, receive, send):' :answers='["async"]' hint='回想本讲关于 三者定位差异 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["三者定位差异：三者定位差异", "路由与依赖注入：路由与依赖注入", "校验与序列化：校验与序列化", "ORM 与迁移内置程度：ORM 与迁移内置程度"]' :pitfalls='["微服务里硬套 Django 的整套 ORM 与 admin，会背上用不到的启动与依赖成本", "忽略版本差异，把 团队成本 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：框架差异主要在「替你决定多少」：Flask 只给内核、FastAPI 把类型注解变成校验与文档、Django 自带全栈约定' />

## 小结与下一讲

1. 三者定位差异：三者定位差异
2. 路由与依赖注入：路由与依赖注入
3. 小工具用 Flask、类型化 API 用 FastAPI、内容型后台与快速交付用 Django；同一仓里不要混两套范式

[下一讲：路由、依赖注入与请求校验](/server/routing)
