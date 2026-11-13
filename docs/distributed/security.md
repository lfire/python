---
title: 第 113 讲 · 安全工程：依赖、注入、序列化与密钥
description: 把安全做成默认行为而不是事后补丁
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★☆' time='40 分钟' goal='把安全做成默认行为而不是事后补丁' prereq='第 112 讲 · 任务调度、SRE 与混沌工程' />

# 第 113 讲 · 安全工程：依赖、注入、序列化与密钥

> Python 应用最常见的高危问题不在语法层：eval / pickle 处理外部数据、拼接 SQL、把密钥打进镜像或日志，任意一条都能直接导致失陷。本讲的目标是「把安全做成默认行为而不是事后补丁」。先建立直觉，再用可运行代码把规则固定下来，最后放进工程场景里看边界与代价；全程建议边读边改参数、边猜输出。

## 这一讲你会得到什么

<CheckList id='P113' title="本讲目标" :items='["能说清依赖漏洞与 SBOM", "能说清注入与参数化", "能说清不安全的反序列化", "能说清密钥与凭证轮换", "能说清权限最小化"]' />

## 1. 先建立直觉

**依赖漏洞与 SBOM**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

**注入与参数化**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

**不安全的反序列化**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。

<ConceptDiagram type='hub4' title='第 113 讲 · 依赖漏洞与 SBOM' labels='依赖漏洞与 SBOM|注入与参数化|不安全的反序列化|密钥与凭证轮换' caption='把安全做成默认行为而不是事后补丁' />

上图用本讲的三个核心概念标出了主线：**依赖漏洞与 SBOM → 注入与参数化 → 不安全的反序列化**。点击可放大，滚轮与双指可缩放，拖拽可平移；读图时先顺着箭头走一遍，再回到代码里找对应的那几行。

<FlowTimeline :steps='[{"title": "建立直觉", "desc": "先理解 依赖漏洞与 SBOM 解决什么问题", "tone": "blue"}, {"title": "跑通示例", "desc": "亲手执行主示例，核对 True True False", "tone": "green"}, {"title": "深入边界", "desc": "厘清 注入与参数化 的失效条件", "tone": "orange"}, {"title": "工程落地", "desc": "把 审计与应急响应 放进真实场景验证", "tone": "purple"}]' direction="horizontal" title="本讲的知识推进" />

## 2. 语法与规则：把行为跑出来

### 2.1 主示例

**依赖漏洞与 SBOM**。建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾。这三问能覆盖绝大多数线上问题，也是后续阶段反复使用的分析框架；能回答这三问，才算真正掌握而不是记住了 API 名字。

```python
# 令牌桶限流
import time
class Bucket:
    def __init__(self, rate, cap):
        self.rate, self.cap, self.tokens, self.t = rate, cap, cap, time.monotonic()
    def allow(self):
        now = time.monotonic()
        self.tokens = min(self.cap, self.tokens + (now - self.t) * self.rate)
        self.t = now
        if self.tokens < 1: return False
        self.tokens -= 1
        return True
b = Bucket(1, 2)
print(b.allow(), b.allow(), b.allow())
```

<OutputBox title="运行结果" output='True True False' note="输出可能随 Python 版本与平台略有差异；以你本机实际执行结果为准，差异本身也是很好的讨论素材。" />

上面每一行在做什么，点开逐行看：

<LineByLine code='# 令牌桶限流\nimport time\nclass Bucket:\n    def __init__(self, rate, cap):\n        self.rate, self.cap, self.tokens, self.t = rate, cap, cap, time.monotonic()\n    def allow(self):\n        now = time.monotonic()\n        self.tokens = min(self.cap, self.tokens + (now - self.t) * self.rate)\n        self.t = now\n        if self.tokens &lt; 1: return False\n        self.tokens -= 1\n        return True\nb = Bucket(1, 2)\nprint(b.allow(), b.allow(), b.allow())' :notes='["按时间补充令牌，允许突发但限制平均速率", "容量决定突发上限，速率决定长期均值", "分布式限流要在共享存储上做原子扣减", "第 4 行：与上文规则对照，观察它在整体流程里承担的角色", "第 5 行：与上文规则对照，观察它在整体流程里承担的角色", "第 6 行：与上文规则对照，观察它在整体流程里承担的角色", "第 7 行：与上文规则对照，观察它在整体流程里承担的角色", "第 8 行：与上文规则对照，观察它在整体流程里承担的角色", "第 9 行：与上文规则对照，观察它在整体流程里承担的角色", "第 10 行：与上文规则对照，观察它在整体流程里承担的角色", "第 11 行：与上文规则对照，观察它在整体流程里承担的角色", "第 12 行：与上文规则对照，观察它在整体流程里承担的角色", "第 13 行：与上文规则对照，观察它在整体流程里承担的角色", "第 14 行：与上文规则对照，观察它在整体流程里承担的角色"]' title='第 113 讲 · 安全工程：依赖、注入、序列化与密钥' />

换一种写法，重点观察**行为是否改变**以及**代价落在哪里**。**注入与参数化**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。 两段代码的输出可以直接对照，差异往往就藏着本讲最关键的规则。

### 2.2 对照写法

```python
# 容器清单要点（示意）
cfg = {"readinessProbe": "/healthz", "livenessProbe": "/live",
       "resources": {"limits": {"memory": "512Mi"}}}
print(sorted(cfg))
```

<OutputBox title="对照写法的输出（先自己猜）" output='[&#39;livenessProbe&#39;, &#39;readinessProbe&#39;, &#39;resources&#39;]' guess="true" />

<Compare :panels='[{"label": "主写法", "code": "# 令牌桶限流\nimport time\nclass Bucket:\n    def __init__(self, rate, cap):\n        self.rate, self.cap, self.tokens, self.t = rate, cap, cap, time.monotonic()\n    def allow(self):\n        now = time.monotonic()\n        self.tokens = min(self.cap, self.tokens + (now - self.t) * self.rate)\n        self.t = now\n        if self.tokens &lt; 1: return False\n        self.tokens -= 1\n        return True\nb = Bucket(1, 2)\nprint(b.allow(), b.allow(), b.allow())", "note": "本讲主示例，关注行为与输出"}, {"label": "对照写法", "code": "# 容器清单要点（示意）\ncfg = {\"readinessProbe\": \"/healthz\", \"livenessProbe\": \"/live\",\n       \"resources\": {\"limits\": {\"memory\": \"512Mi\"}}}\nprint(sorted(cfg))", "note": "换一种组织方式，对照可读性与代价"}]' title="两种写法对照" note='对照时关注「依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口写进」' />

## 3. 深入一步：规则与边界

**不安全的反序列化**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。

**密钥与凭证轮换**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。

**权限最小化**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。

| 知识点 | 规则要点 | 常见误用 |
| --- | --- | --- |
| 依赖漏洞与 SBOM | 工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、 | 依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口 |
| 注入与参数化 | 建议把它和相邻知识点连成一条线：输入是什么、状态存在哪里、失败时谁负责收尾 | 依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口 |
| 不安全的反序列化 | 先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则 | 依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口 |
| 密钥与凭证轮换 | 这里的关键词是「什么时候」和「代价是什么」 | 依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口 |
| 权限最小化 | 从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上 | 依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口 |

<Term word='依赖漏洞与 SBOM' text='Python 应用最常见的高危问题不在语法层：eval / pickle 处理外部数据、拼接 SQL、把密钥打进镜像或日志，任意一条都能直接导致失陷' />

<Callout type="warn" title="易错点" text='依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口写进交付物' />

<StepBox title="遇到异常时按这个顺序排查" :steps='[{"title": "第 1 步：依赖漏洞与 SBOM", "body": "**依赖漏洞与 SBOM**。先把这个概念放进可验证的场景：写一段最小代码，观察它的输出，再回头读规则。很多误解来自只记结论、没有亲手跑过边界情况；本讲要求把每一步的结论都用一段可运行代码固定下来，而不是停在「大概是这样」。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 2 步：注入与参数化", "body": "**注入与参数化**。这里的关键词是「什么时候」和「代价是什么」。Python 的机制大多不是非黑即白的开关，而是在可读性、性能与灵活性之间做的取舍。把取舍写清楚，遇到新版本或新框架时才能自己推导，而不是重新背一遍结论。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 3 步：不安全的反序列化", "body": "**不安全的反序列化**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。", "tip": "先用最小示例复现，再放大输入规模"}, {"title": "第 4 步：密钥与凭证轮换", "body": "**密钥与凭证轮换**。工程里最容易出问题的不是不会用，而是用在错误的边界上：数据规模变大、并发进入、依赖升级、跨平台部署之后，原本成立的假设会逐个失效。因此本讲同时给出适用条件、失效信号和一条可回退的路径。", "tip": "先用最小示例复现，再放大输入规模"}]' />

<SequenceDiagram title='第 113 讲 · 调用时序' caption='从触发到收尾，标出可能失败的位置' :actors='["调用方", "处理逻辑", "依赖资源"]' :steps='[{"from": "调用方", "to": "处理逻辑", "label": "发起调用", "note": "依赖漏洞与 SBOM", "kind": "call"}, {"from": "处理逻辑", "to": "处理逻辑", "label": "校验状态", "note": "注入与参数化", "kind": "self"}, {"from": "处理逻辑", "to": "依赖资源", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "依赖资源", "to": "处理逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "处理逻辑", "to": "调用方", "label": "返回或失败", "note": "清理资源", "kind": "return"}]' />

## 4. 工程实践

用参数化查询、禁止对不可信数据 pickle/eval、密钥托管与轮换、CI 做依赖与镜像扫描 **审计与应急响应**。从实现角度看，这一层的行为最终会落到对象协议、字节码或运行时状态上。理解底层并不意味着每次都要写底层代码，而是当现象与直觉不符时，你知道该用 dis、inspect、tracemalloc 还是 cProfile 去验证，从而把猜测变成证据。 落地时把这条结论写进检查表或自动化测试，避免只停留在口头约定。

### 用命令行复现

本机不用起服务，一条命令就能把本讲的关键行为再验证一次：

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

把命令里的输入换成你自己的数据，观察输出是否仍符合 **依赖漏洞与 SBOM** 的规则；若结果不一致，先核对 Python 版本与依赖版本，再回到主示例逐行定位差异。这条命令也可以直接加进 CI，作为本讲结论的回归检查。

<Callout type="idea" title="生产提示" text='把「审计与应急响应」写成检查项，并在 CI 里用最小用例守住它。' />

把本讲结论接到真实系统时，至少回答三个问题：数据量上来后是否还成立；并发进入后状态由谁拥有；失败之后谁负责收尾与重试。回答不上来，就先补一个最小压测或故障注入，而不是直接上线。

## 动手练一练

<Exercise title='动手：围绕「审计与应急响应」改写示例' task='在不改变输出语义的前提下改写本讲主示例，使其显式处理 依赖漏洞与 SBOM 与 审计与应急响应 两个关注点，并说明你的取舍。' :hints='["回到 依赖漏洞与 SBOM 的规则", "留意易错点：依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口写进交付物", "先让代码跑通，再补边界与异常分支"]' solution='# 容器清单要点（示意）\ncfg = {"readinessProbe": "/healthz", "livenessProbe": "/live",\n       "resources": {"limits": {"memory": "512Mi"}}}\nprint(sorted(cfg))' explain='对照写法展示了另一种组织方式。关键不是代码更短，而是把状态与失败路径显式化；用参数化查询、禁止对不可信数据 pickle/eval、密钥托管与轮换、CI 做依赖与镜像扫描' />

## 随堂检测

<Quiz no='113-1' q='在本讲讨论的「依赖漏洞与 SBOM」语境下，下面哪一种说法是准确的？' :options='["Python 应用最常见的高危问题不在语法层：eval / pickle 处理外部数据、拼接 SQL、把密钥打进镜像或日志，任意一条都能直接导致失陷", "依赖漏洞与 SBOM 只影响代码的书写形式，不会改变任何运行时行为", "依赖漏洞与 SBOM 在所有 Python 实现与所有版本中表现完全一致", "只要用了 依赖漏洞与 SBOM，就不必再考虑 审计与应急响应 带来的约束"]' answer="0" explain='正确项来自本讲的核心洞察。其余三项是常见误解：把语言机制当成纯语法糖、忽略实现与版本差异、以及误以为某个特性能替代对 审计与应急响应 的判断。遇到这类判断，回到可运行的最小示例验证，比记结论可靠。' />

<Predict no='113-2' q='下面这段主示例在 CPython 3.10+ 中运行，最贴近的输出是哪一项？' :options='["True True False", "True True False\n（无更多输出）", "AttributeError: 依赖漏洞与 SBOM 不可用"]' answer="0" output='True True False' explain='真正输出是第一段。第二项漏掉了后续行的结果，第三项把「概念不理解」误当成运行时异常。建议先自己在本机跑一遍，再用 dis 或 print 把中间状态打出来对照。' />

<FillBlank no='113-3' tpl='___time' :answers='["import"]' hint='回想本讲关于 依赖漏洞与 SBOM 的规则' explain='被挖掉的关键字决定了这一行的语义；补回去后再跑一遍，确认输出与上面的运行结果一致。' />

## 一页纸速记

<KnowledgeCard :points='["依赖漏洞与 SBOM：依赖漏洞与 SBOM", "注入与参数化：注入与参数化", "不安全的反序列化：不安全的反序列化", "密钥与凭证轮换：密钥与凭证轮换"]' :pitfalls='["依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口写进交付物", "忽略版本差异，把 审计与应急响应 的结论当成跨版本通用", "只看示例代码跑通，没有验证边界输入与失败路径"]' summary='本讲一句话：Python 应用最常见的高危问题不在语法层：eval / pickle 处理外部数据、拼接 SQL、把密钥打进镜像或日志，任意一条都能直接导致失陷' />

## 小结与下一讲

1. 依赖漏洞与 SBOM：依赖漏洞与 SBOM
2. 注入与参数化：注入与参数化
3. 用参数化查询、禁止对不可信数据 pickle/eval、密钥托管与轮换、CI 做依赖与镜像扫描

[下一讲：CPython 源码：对象、帧与求值循环](/advanced/cpython-source)
