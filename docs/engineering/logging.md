---
title: 第 078 讲 · 日志：logging、结构化日志与追踪关联
description: 让线上问题可检索、可关联、可告警
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='35 分钟' goal='让线上问题可检索、可关联、可告警' prereq='第 077 讲 · 属性测试、基准测试与模糊测试' />

# 第 078 讲 · 日志：logging、结构化日志与追踪关联

> 日志是给机器检索的数据，不是给人看的散文；结构化字段加 trace_id 才能把一次请求跨服务串起来。本讲的目标是「让线上问题可检索、可关联、可告警」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P078' title="本讲目标" :items='["能说清Logger / Handler / Formatter", "能说清级别与传播", "能说清结构化 JSON", "能说清trace_id 注入", "能说清采样与脱敏"]' />

## 1. 先建立直觉

**Logger / Handler / Formatter**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**级别与传播**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**结构化 JSON**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

<ConceptDiagram type='hub4' title='第 078 讲 · Logger / Handler / Formatter' labels='Logger / Handler / Formatter|级别与传播|结构化 JSON|trace_id 注入' caption='让线上问题可检索、可关联、可告警' />

上图用本讲的三个核心概念标出了主线：**Logger / Handler / Formatter → 级别与传播 → 结构化 JSON**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 Logger / Handler / Formatter 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 {\"level\": \"INFO\", \"msg\": \"", "tone": "green"}, {"title": "深入边界", "desc": "厘清 级别与传播 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 与 OpenTelemetry 关联 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**Logger / Handler / Formatter**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

```python
import logging, json

class JsonFormatter(logging.Formatter):
    def format(self, r):
        return json.dumps({"level": r.levelname,
                           "msg": r.getMessage(),
                           "trace": getattr(r, "trace", "-")}, ensure_ascii=False)

h = logging.StreamHandler(); h.setFormatter(JsonFormatter())
log = logging.getLogger("demo"); log.addHandler(h); log.setLevel(logging.INFO)
log.info("order created", extra={"trace": "t-123"})
```

<OutputBox title="运行结果" output='{"level": "INFO", "msg": "order created", "trace": "t-123"}' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='import logging, json\n\nclass JsonFormatter(logging.Formatter):\n    def format(self, r):\n        return json.dumps({"level": r.levelname,\n                           "msg": r.getMessage(),\n                           "trace": getattr(r, "trace", "-")}, ensure_ascii=False)\n\nh = logging.StreamHandler(); h.setFormatter(JsonFormatter())\nlog = logging.getLogger("demo"); log.addHandler(h); log.setLevel(logging.INFO)\nlog.info("order created", extra={"trace": "t-123"})' :notes='["结构化日志便于机器检索与聚合", "extra 把 trace_id 注入每条记录", "Formatter 决定输出形态，与业务代码解耦", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 078 讲 · 日志：logging、结构化日志与追踪关联' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**级别与传播**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
import logging
log = logging.getLogger(__name__)
try:
    1 / 0
except ZeroDivisionError:
    log.exception("calc failed")
```

<OutputBox title="对照写法的输出（先自己猜）" output='calc failed\nTraceback ...' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "import logging, json\n\nclass JsonFormatter(logging.Formatter):\n    def format(self, r):\n        return json.dumps({\"level\": r.levelname,\n                           \"msg\": r.getMessage(),\n                           \"trace\": getattr(r, \"trace\", \"-\")}, ensure_ascii=False)\n\nh = logging.StreamHandler(); h.setFormatter(JsonFormatter())\nlog = logging.getLogger(\"demo\"); log.addHandler(h); log.setLevel(logging.INFO)\nlog.info(\"order created\", extra={\"trace\": \"t-123\"})", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "import logging\nlog = logging.getLogger(__name__)\ntry:\n    1 / 0\nexcept ZeroDivisionError:\n    log.exception(\"calc failed\")", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事故」' />

## 3. 深入一步：规则与边界

**结构化 JSON**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**trace_id 注入**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**采样与脱敏**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| Logger / Handler / Formatter | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事 |
| 级别与传播 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事 |
| 结构化 JSON | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事 |
| trace_id 注入 | 这里的关键词是「什么时候」和「代价是什么」 | 在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事 |
| 采样与脱敏 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事 |

<Term word='Logger / Handler / Formatter' text='日志是给机器检索的数据，不是给人看的散文；结构化字段加 trace_id 才能把一次请求跨服务串起来' />

<Callout type="warn" title="易错点" text='在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事故' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：Logger / Handler / Formatter", "body": "**Logger / Handler / Formatter**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：级别与传播", "body": "**级别与传播**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：结构化 JSON", "body": "**结构化 JSON**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：trace_id 注入", "body": "**trace_id 注入**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}]' />

<SequenceDiagram title='第 078 讲 · 调用时序' caption='从触发到收尾，标出可能失败的位置' :actors='["调用方", "处理逻辑", "依赖资源"]' :steps='[{"from": "调用方", "to": "处理逻辑", "label": "发起调用", "note": "Logger / Handl", "kind": "call"}, {"from": "处理逻辑", "to": "处理逻辑", "label": "校验状态", "note": "级别与传播", "kind": "self"}, {"from": "处理逻辑", "to": "依赖资源", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "依赖资源", "to": "处理逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "处理逻辑", "to": "调用方", "label": "返回或失败", "note": "清理资源", "kind": "return"}]' />

## 4. 工程实践

统一日志格式、按级别采样、敏感字段默认脱敏，异常必须带上下文而不是只打一句 failed **与 OpenTelemetry 关联**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import logging; logging.basicConfig(level=logging.INFO); logging.info('hello')"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **Logger / Handler / Formatter** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「与 OpenTelemetry 关联」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「与 OpenTelemetry 关联」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 Logger / Handler / Formatter 与 与 OpenTelemetry 关联 两个关注点，并说明你的取舍。' :hints='["回到 Logger / Handler / Formatter 的规则", "留意易错点：在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事故", "先让代码跑通，再补边界与异常分支"]' solution='import logging\nlog = logging.getLogger(__name__)\ntry:\n    1 / 0\nexcept ZeroDivisionError:\n    log.exception("calc failed")' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；统一日志格式、按级别采样、敏感字段默认脱敏，异常必须带上下文而不是只打一句 failed' />

## 随堂检测

<Quiz no='078-1' q='在本讲讨论的「Logger / Handler / Formatter」语境下，下面哪一种说法是准确的？' :options='["日志是给机器检索的数据，不是给人看的散文；结构化字段加 trace_id 才能把一次请求跨服务串起来", "Logger / Handler / Formatter 只影响代码的书写形式，不会改变任何运行时行为", "Logger / Handler / Formatter 在所有 Python 实现与所有版本中表现完全一致", "只要用了 Logger / Handler / Formatter，就不必再考虑 与 OpenTelemetry 关联 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 与 OpenTelemetry 关联 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='078-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["{\"level\": \"INFO\", \"msg\": \"order created\", \"trace\": \"t-123\"}", "{\"level\": \"INFO\", \"msg\": \"order created\", \"trace\": \"t-123\"}\n（无更多输出）", "AttributeError: Logger / Handler / Formatter 不可用"]' answer="0" output='{"level": "INFO", "msg": "order created", "trace": "t-123"}' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='078-3' tpl='___logging, json' :answers='["import"]' hint='回想本讲关于 Logger / Handler / Formatter 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["Logger / Handler / Formatter：Logger / Handler / Formatter", "级别与传播：级别与传播", "结构化 JSON：结构化 JSON", "trace_id 注入：trace_id 注入"]' :pitfalls='["在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事故", "忽略版本差异，把 与 OpenTelemetry 关联 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：日志是给机器检索的数据，不是给人看的散文；结构化字段加 trace_id 才能把一次请求跨服务串起来' />

## 小结与下一讲

1. Logger / Handler / Formatter：Logger / Handler / Formatter
2. 级别与传播：级别与传播
3. 统一日志格式、按级别采样、敏感字段默认脱敏，异常必须带上下文而不是只打一句 failed

[下一讲：配置管理：环境变量、.env 与配置中心](/engineering/config)
