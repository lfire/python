---
title: 第 121 讲 · 资深能力图谱、技术选型与持续精进
description: 建立可自我更新的技术判断框架
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='40 分钟' goal='建立可自我更新的技术判断框架' prereq='第 120 讲 · 架构设计：领域分层、演进与重构' />

# 第 121 讲 · 资深能力图谱、技术选型与持续精进

上一讲把架构决策落成边界与契约，可「该不该拆、选哪条路」仍要人拍板，阶段也在此收尾。本讲整理一套判断框架：把分水岭从记住多少 API，挪到信息不全时也能给出带假设、可回退的方案。

一个日均两亿条日志的系统要选型，有人凭「生态成熟、大家都在用」当场定了；三个月后写入跟不上、磁盘被打满，才看清真实限制是峰值、只查七天、运维一人、不许商用许可。我们先用硬门槛淘汰候选，再用显式权重打分、浮动争议权重看排名稳不稳，最后把结论写成带假设与回退的选型评估记录。需要你读过前面的性能、并发与架构几讲；学完能让决策可核对、可回放。


## 信息不全时，资深该拿出什么

一个团队要给日均两亿条日志的检索系统选型，A 工程师凭「Elasticsearch 生态成熟、大家都在用」当场拍板，没写任何约束。上线三个月后单机写入跟不上、冷热数据没分层、磁盘被打满，回溯才发现真实约束是：写入峰值每秒五万条、只查最近七天、运维只有一人、预算不许上商用许可。

朴素解法失败在把选型当成「我熟悉什么、什么最火」，信息不全时既没把假设写出来，也没给代价、验证与回退。资深的分水岭不是知道多少 API，而是能在约束残缺时给出带假设、可验证、可回退的方案：先立硬门槛淘汰不合格者，再用显式权重给合格者打分，做敏感性分析看结论是否依赖某个权重，把决策与复盘都沉淀成可检索的记录。

本讲把这套判断框架落到能计算、能回放的具体结构上。

<CheckList id='P121a' title='学完你应当能' :items='["能讲清 选型评估：把主观偏好变成硬门槛加加权矩阵", "能讲清 技术决策记录 ADR：带假设、代价、验证与回退", "能讲清 复盘与能力自更新：从结论到自动化检查表", "能在工程里处理 持续学习路径"]' />


## 把主观偏好变成硬门槛加加权矩阵

可复用的评估分两层。第一层是硬门槛（must-have），不满足直接淘汰、不参与打分：例如写入吞吐不低于五万条每秒、许可必须是 Apache-2.0 或 MIT、单节点运维人力不超过一人、数据保留七天可配置 TTL。

第二层才是加权评分：维度取吞吐、p99 延迟、运维成本、团队熟悉度、回退难度等，每维给权重 `w_i` 与 1 到 5 分的评分 `s_i`，得分按 `score = Σ(w_i·s_i) / Σw_i` 计算，权重和为一时就是加权平均。

关键是每个维度都要可核对：「我熟悉」量化成团队内会独立排障的人数，「生态好」量化成可用客户端语言数与近一年公开问题数，避免把印象当数据。层次分析法 AHP 用两两比较矩阵求权重，并算一致性比率 CR，CR 大于 0.1 说明判断自相矛盾、矩阵要重填。

无论哪种方法都要做敏感性分析：把争议最大的权重上下浮动，若最优方案翻转，说明结论依赖主观权重，必须回到硬门槛或补一次压测来消解分歧，而不是强行定案。

**选型评估维度：硬门槛与加权偏好要分开**

| 维度 | 类型 | 可核对的度量 | 不满足时的处理 |
| --- | --- | --- | --- |
| 写入吞吐 | 硬门槛 | 压测每秒写入条数 ≥ 5 万 | 直接淘汰，不进入打分 |
| 许可协议 | 硬门槛 | 许可为 Apache-2.0 / MIT | 商用许可或协议不明即淘汰 |
| p99 延迟 | 加权 | 压测 p99 毫秒数映射 1-5 分 | 低分拉低加权总分 |
| 团队熟悉度 | 加权 | 能独立排障的人数 | 低分计入培训成本 |
| 回退难度 | 加权 | 能否双写与切回旧集群 | 高分代表回退路径短 |

<Callout type="tip" title='核心心智模型' text='可复用的评估分两层。第一层是硬门槛（must-have），不满足直接淘汰、不参与打分：例如写入吞吐不低于五万条每秒、许可必须是 Apache-2.0 或 MIT、单节点运维人力不超过一人、数据保留七天可配置 TTL。第二层才是加权评分：维度取吞吐、p99 延迟、运维成本、团队熟悉度、回退难度等，每维' />

<ConceptDiagram type='flow4' title='第 121 讲 · 选型评估：把主观偏好变成硬门槛加加权矩阵' labels='选型评估：把主观偏好变成硬门槛加加权矩阵|技术决策记录 ADR：带假设、代价、验证与回|复盘与能力自更新：从结论到自动化检查表' caption='建立可自我更新的技术判断框架' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 加权评分为什么必须先过不可补偿的约束

加权评分模型本质是线性效用函数 `U(x) = Σw_i·s_i`，它假设各维度可互相补偿（某维低分能被另一维高分抵消），这正是必须前置硬门槛的原因：硬门槛表达不可补偿的约束，用布尔淘汰而非加权，否则「写入不达标但运维省事」会被算成可接受。

AHP 通过两两比较矩阵求特征向量作为权重，一致性比率 `CR=CI/RI` 用来检测判断矩阵的逻辑矛盾，CR 大于 0.1 时矩阵不可用。敏感性分析考察的是解对权重向量的稳定区间：当最优解在权重微小扰动下就翻转，说明数据不足以支撑决策，应补压测而非调权重。

ADR 用不可变编号加 Superseded 状态构成只追加的决策日志，等价于事件溯源里的 append-only log，因此任一时刻的架构状态都可从记录序列重建。把复盘结论转成 lint 与 CI 规则，是把「人的记忆」迁移到「可执行的确定性检查」，降低了同类故障的复发概率。

```python
O = {'es': (4, 3, 2, 5, 3), 'clickhouse': (5, 5, 3, 2, 4), 'sqlite': (1, 2, 5, 5, 5)}

def rank(weights):
    def sc(v):
        return round(sum(w * x for w, x in zip(weights, v)) / sum(weights), 3)
    return sorted(O, key=lambda k: -sc(O[k]))

print('base', rank([0.30, 0.25, 0.20, 0.15, 0.10]))
print('ops-heavy', rank([0.10, 0.10, 0.60, 0.10, 0.10]))
```

<OutputBox title='对照写法：先自己猜，再点开' output='base [&#39;clickhouse&#39;, &#39;es&#39;, &#39;sqlite&#39;]\nops-heavy [&#39;sqlite&#39;, &#39;clickhouse&#39;, &#39;es&#39;]' guess="true" />


## 技术决策记录 ADR 里要写清哪几件事

Michael Nygard 提出的架构决策记录（ADR）是一段短文本，字段固定为编号、标题、状态、上下文、决策、后果、验证、回退；状态取 Proposed、Accepted、Deprecated、Superseded，编号单调递增且不可修改，新决策「取代」旧决策而不是删掉它，从而保留完整演进史。

写一条合格决策要满足三点：假设可证伪，例如「若压测写入达不到五万条每秒，则本决策作废」，而不是「应该扛得住」；验证有指标与阈值，例如 p99 小于 200 毫秒、磁盘占用三十天低于 80%；代价与回退显式写出，例如团队需补运维手册、双写保留两周后可切回旧集群。

回退必须是可执行动作：特性开关、影子流量、双写与数据对账脚本，而不是「必要时回滚」这种无法验证的话。把「问题—约束—备选—代价—验证—回退」做成模板填进版本库，评审讨论的是字段内容而非个人经验，决策才有可审计的依据。

**ADR 固定字段与填写要求**

| 字段 | 内容要求 | 反例 |
| --- | --- | --- |
| 编号 / 状态 | 单调递增不可改；状态含 Superseded | 删除旧决策、复用编号 |
| 上下文 / 决策 | 写清约束与所选方案 | 只写「采用新框架」 |
| 后果 | 显式列出代价与新增约束 | 只写优点不写运维负担 |
| 验证 | 指标 + 阈值 + 测量方式 | 「上线后观察」这类无法判定的话 |
| 回退 | 可执行动作：开关 / 双写 / 对账 | 「必要时回滚」 |

```python
CRITERIA = [('write_tps', 0.30), ('p99_ms', 0.25), ('ops_cost', 0.20), ('familiarity', 0.15), ('rollback', 0.10)]
OPTIONS = {
    'es': {'write_tps': 4, 'p99_ms': 3, 'ops_cost': 2, 'familiarity': 5, 'rollback': 3},
    'clickhouse': {'write_tps': 5, 'p99_ms': 5, 'ops_cost': 3, 'familiarity': 2, 'rollback': 4},
    'sqlite': {'write_tps': 1, 'p99_ms': 2, 'ops_cost': 5, 'familiarity': 5, 'rollback': 5},
}
MUST = {'write_tps': 3}

def score(opt, weights):
    vals = OPTIONS[opt]
    num = sum(weights[k] * vals[k] for k, _ in CRITERIA)
    return round(num / sum(weights.values()), 3)

def eligible(opt):
    return all(OPTIONS[opt][k] >= v for k, v in MUST.items())

w = dict(CRITERIA)
for opt in OPTIONS:
    print(opt, 'eligible', eligible(opt), 'score', score(opt, w))
pool = [o for o in OPTIONS if eligible(o)]
print('winner', max(pool, key=lambda o: score(o, w)))
```

<OutputBox title='主示例运行结果' output='es eligible True score 3.4\nclickhouse eligible True score 4.05\nsqlite eligible False score 3.05\nwinner clickhouse' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='CRITERIA = [(&#39;write_tps&#39;, 0.30), (&#39;p99_ms&#39;, 0.25), (&#39;ops_cost&#39;, 0.20), (&#39;familiarity&#39;, 0.15), (&#39;rollback&#39;, 0.10)]\nOPTIONS = {\n    &#39;es&#39;: {&#39;write_tps&#39;: 4, &#39;p99_ms&#39;: 3, &#39;ops_cost&#39;: 2, &#39;familiarity&#39;: 5, &#39;rollback&#39;: 3},\n    &#39;clickhouse&#39;: {&#39;write_tps&#39;: 5, &#39;p99_ms&#39;: 5, &#39;ops_cost&#39;: 3, &#39;familiarity&#39;: 2, &#39;rollback&#39;: 4},\n    &#39;sqlite&#39;: {&#39;write_tps&#39;: 1, &#39;p99_ms&#39;: 2, &#39;ops_cost&#39;: 5, &#39;familiarity&#39;: 5, &#39;rollback&#39;: 5},\n}\nMUST = {&#39;write_tps&#39;: 3}\n\ndef score(opt, weights):\n    vals = OPTIONS[opt]\n    num = sum(weights[k] * vals[k] for k, _ in CRITERIA)\n    return round(num / sum(weights.values()), 3)\n\ndef eligible(opt):\n    return all(OPTIONS[opt][k] &gt;= v for k, v in MUST.items())\n\nw = dict(CRITERIA)\nfor opt in OPTIONS:\n    print(opt, &#39;eligible&#39;, eligible(opt), &#39;score&#39;, score(opt, w))\npool = [o for o in OPTIONS if eligible(o)]\nprint(&#39;winner&#39;, max(pool, key=lambda o: score(o, w)))' :notes='["定义五维评估标准，每项配显式权重，权重之和为 1.0", "备选方案表，键为方案名，值为各维 1-5 分评分", "Elasticsearch：写入 4、延迟 3、运维 2、熟悉度 5、回退 3", "ClickHouse：写入与延迟都满分，运维 3、熟悉度 2、回退 4", "SQLite：运维与熟悉度满分，但写入仅 1 分", "关闭方案表", "硬门槛：写入吞吐评分必须至少 3，不满足直接淘汰", "score 计算某方案在给定权重下的加权得分", "取出该方案各维评分", "按 CRITERIA 逐维做权重乘评分再求和，得到分子", "除以权重总和归一化，保留三位小数消除浮点尾差", "eligible 判断方案是否满足全部硬门槛", "all 要求每个 must-have 维度都不低于阈值", "把权重列表转成字典，供 score 按维度名索引", "遍历三个方案逐一打印资格与得分", "硬门槛与加权分一起输出，淘汰原因一目了然", "只在通过硬门槛的方案里形成候选池", "按加权分取候选池最大值，输出最终赢家"]' title='第 121 讲 · 资深能力图谱、技术选型与持续精进' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 定案前做敏感性分析：换个权重结论会不会翻转

<CodeTabs :tabs='[{"label": "主示例", "code": "CRITERIA = [(&#39;write_tps&#39;, 0.30), (&#39;p99_ms&#39;, 0.25), (&#39;ops_cost&#39;, 0.20), (&#39;familiarity&#39;, 0.15), (&#39;rollback&#39;, 0.10)]\nOPTIONS = {\n    &#39;es&#39;: {&#39;write_tps&#39;: 4, &#39;p99_ms&#39;: 3, &#39;ops_cost&#39;: 2, &#39;familiarity&#39;: 5, &#39;rollback&#39;: 3},\n    &#39;clickhouse&#39;: {&#39;write_tps&#39;: 5, &#39;p99_ms&#39;: 5, &#39;ops_cost&#39;: 3, &#39;familiarity&#39;: 2, &#39;rollback&#39;: 4},\n    &#39;sqlite&#39;: {&#39;write_tps&#39;: 1, &#39;p99_ms&#39;: 2, &#39;ops_cost&#39;: 5, &#39;familiarity&#39;: 5, &#39;rollback&#39;: 5},\n}\nMUST = {&#39;write_tps&#39;: 3}\n\ndef score(opt, weights):\n    vals = OPTIONS[opt]\n    num = sum(weights[k] * vals[k] for k, _ in CRITERIA)\n    return round(num / sum(weights.values()), 3)\n\ndef eligible(opt):\n    return all(OPTIONS[opt][k] &gt;= v for k, v in MUST.items())\n\nw = dict(CRITERIA)\nfor opt in OPTIONS:\n    print(opt, &#39;eligible&#39;, eligible(opt), &#39;score&#39;, score(opt, w))\npool = [o for o in OPTIONS if eligible(o)]\nprint(&#39;winner&#39;, max(pool, key=lambda o: score(o, w)))", "note": "选型评估：把主观偏好变成硬门槛加加权矩阵"}, {"label": "对照 / 进阶", "code": "O = {&#39;es&#39;: (4, 3, 2, 5, 3), &#39;clickhouse&#39;: (5, 5, 3, 2, 4), &#39;sqlite&#39;: (1, 2, 5, 5, 5)}\n\ndef rank(weights):\n    def sc(v):\n        return round(sum(w * x for w, x in zip(weights, v)) / sum(weights), 3)\n    return sorted(O, key=lambda k: -sc(O[k]))\n\nprint(&#39;base&#39;, rank([0.30, 0.25, 0.20, 0.15, 0.10]))\nprint(&#39;ops-heavy&#39;, rank([0.10, 0.10, 0.60, 0.10, 0.10]))", "note": "技术决策记录 ADR：带假设、代价、验证与回退"}]' title='两种写法切换看' />

```python
import inspect, json

sig = inspect.signature(json.dumps)
kw = [p.name for p in sig.parameters.values() if p.kind is p.KEYWORD_ONLY]
print('obj kind', sig.parameters['obj'].kind.name)
print('keyword-only params', kw)
print('param count', len(sig.parameters))
```

<OutputBox title='原理验证' output='obj kind POSITIONAL_OR_KEYWORD\nkeyword-only params [&#39;skipkeys&#39;, &#39;ensure_ascii&#39;, &#39;check_circular&#39;, &#39;allow_nan&#39;, &#39;cls&#39;, &#39;indent&#39;, &#39;separators&#39;, &#39;default&#39;, &#39;sort_keys&#39;]\nparam count 11' />


## 技术决策的回退路径与验证项

故障复盘采用无指责复盘（blameless postmortem）：先还原精确到分钟的时间线，再用 5 Whys 找贡献因素而非单一根因，行动项必须带 owner、截止与验证方式，否则复盘会退化成纪要。

最高价值的动作是把结论转成机器可执行的约束：把「凭证不能写死」变成 pre-commit 的密钥扫描规则，把「超时必须显式」变成 lint 规则，把「批量操作先 dry-run」变成流水线里的强制步骤，把监控阈值与 runbook 一起提交。

读源码也是可验证的能力：`inspect.getsource` 与 `getsourcelines` 拿到函数源码与行号，`inspect.signature` 读参数默认值与类别（3.13 的 `json.dumps` 里 obj 是 `POSITIONAL_OR_KEYWORD`，星号之后的参数都是 `KEYWORD_ONLY`），`importlib.metadata.version` 查发行包版本，`dis.get_instructions` 看字节码验证短路或分派结论，任何「我猜是这样」都应落成这类事实。

能力矩阵按「能交付什么」而非「学过什么」定义出口，例如能独立给出带压测数据的选型、能主持一次复盘并产出检查表。持续学习靠把这些 ADR 与复盘归档成可检索库，让下一次决策站在上一次的验证数据上。

<Callout type="warn" title='本讲最容易踩的坑' text='把「我熟悉」「生态好」直接写成分数，评审时各说各话：主观印象没有可核对口径，权重再精确结论也不可复现' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把「我熟悉」「生态好」直接写成分数，评审时各", "body": "主观印象没有可核对口径，权重再精确结论也不可复现", "tip": "把熟悉度量化为会独立排障的人数、生态量化为客户端语言数与公开问题数，硬门槛与加权分开"}, {"title": "第 2 步：定案不做敏感性分析，上线后换个权重结论就翻转", "body": "加权解对争议权重高度敏感，却没被测量", "tip": "上下浮动争议权重看排名是否稳定，翻转就回到硬门槛或补压测，而非强行收敛"}, {"title": "第 3 步：复盘只有纪要，行动项没有 owner、验证与", "body": "结论停留在人的记忆里，同类故障反复发生", "tip": "每条行动项带 owner 与验证方式，并转成 lint / CI / 监控规则随代码提交"}]' />


## 把复盘结论沉淀成可检索的 ADR 与检查表

一次检索系统选型结束后，团队用 dataclass 定义固定的 ADR 结构：编号、标题、状态、上下文、决策、后果、验证、回退八个字段全部必填，`frozen=True` 保证记录一旦写入不被悄悄改写。脚本在生成记录时自动检查「验证」与「回退」是否为空，缺任一项就拒绝归档；

再序列化成 `JSON` 存入版本库，便于全文检索与后续复盘引用。复盘产出的检查表也被编码成字段列表，CI 里逐项断言这些字段都有值，把「写清楚」变成机器可判定的条件。真实项目会把 ADR 编号与 Git 提交关联、给 Superseded 记录加指向新编号的字段，并在压测报告里回填验证结果。

下面片段可直接运行，重点看结构如何强制承载代价与回退。

```python
import dataclasses, json

@dataclasses.dataclass(frozen=True)
class ADR:
    number: int
    title: str
    status: str
    context: str
    decision: str
    consequences: str
    verify: str
    rollback: str

REQUIRED = ('context', 'decision', 'consequences', 'verify', 'rollback')

def archive(adr):
    missing = [k for k in REQUIRED if not getattr(adr, k)]
    if missing:
        return 'reject: empty ' + ','.join(missing)
    return json.dumps(dataclasses.asdict(adr), ensure_ascii=False)

adr = ADR(7, '日志检索选 ClickHouse', 'Accepted',
          '写入五万每秒，查最近七天，运维一人',
          '冷热分层加七天 TTL',
          '需补运维手册与培训',
          'p99 小于 200ms 且磁盘三十天低于 80%',
          '特性开关切回 ES，双写保留两周')

print('fields', [f.name for f in dataclasses.fields(ADR)])
print('status roundtrip', json.loads(archive(adr))['status'])
print('checklist filled', [k for k in REQUIRED if getattr(adr, k)])
print('reject empty', archive(dataclasses.replace(adr, verify='')))
```

<Callout type="idea" title='落地提示' text='用「问题—约束—备选—代价—验证—回退」模板写技术决策，把复盘结论沉淀成检查表与自动化' />

**把复盘结论转成可执行约束**

| 复盘结论 | 自动化载体 | 验证信号 |
| --- | --- | --- |
| 凭证不得写死 | pre-commit 密钥扫描规则 | 提交里出现疑似密钥即被拦截 |
| 网络调用必须带超时 | lint 规则检查调用参数 | 无 timeout 的调用无法合并 |
| 批量操作先 dry-run | 流水线强制步骤 | 未产出计划文件即中止 |
| 超时要有降级 | 监控告警 + runbook | 演练时按 runbook 完成降级 |

<CheckList id='P121b' title='上线前自检' :items='["能复现并解释「把「我熟悉」「生态好」直接写成分数，评审时各说各话」", "能复现并解释「定案不做敏感性分析，上线后换个权重结论就翻转」", "能复现并解释「复盘只有纪要，行动项没有 owner、验证与自动化」", "能用一条命令验证 能力矩阵与短板", "关键路径有自动化测试与失败分支"]' />


## 加权评分的可补偿性缺陷与硬门槛的词典序

把选型写成各维度打分乘权重求和时，隐含了一个很强的假设：维度之间可完全补偿——运维成本打 1 分，只要性能打 10 分就能被抵消。真实约束往往不可补偿，例如必须支持同城双活是一条布尔硬门槛，任何分数都换不来，正确做法是词典序：先跑硬门槛淘汰，再对存活方案加权排序，而不是让权重去表达否决。

加权和还有第二个缺陷，即不满足无关备选独立性：新增或删掉一个方案可能让原有两名排序翻转，这正是换个权重结论就翻转之外更隐蔽的 rank reversal。

可复现的评估框架分三步：第一步把主观形容词换成可核对的代理量，团队熟悉量化为能独立 on-call 排障的人数（bus factor），生态好量化为官方客户端语言数、issue 中位解决时长与发布节奏；第二步先算 Pareto 前沿，若方案 X 在所有维度都不劣于 Y 且至少一维更优，Y 被支配，直接剪掉；

第三步才对前沿方案做敏感性扫描，上下浮动争议权重看排名是否稳定，翻转就回到硬门槛或补压测数据。决策还要按可逆性分级：可回滚的 type-2 决策用轻量流程快速定，不可逆的 type-1 决策才值得完整 ADR 与回退预案。

```python
def pareto_front(options):
    front = []
    for name, vec in options.items():
        dominated = any(
            all(o[j] >= vec[j] for j in range(len(vec))) and
            any(o[j] > vec[j] for j in range(len(vec)))
            for other, o in options.items() if other != name
        )
        if not dominated:
            front.append(name)
    return sorted(front)

options = {'A': (5, 3, 4), 'B': (4, 4, 4), 'C': (2, 5, 5), 'D': (5, 3, 3)}
print('front', pareto_front(options))
print('D_passes_gate', all(v >= lim for v, lim in zip(options['D'], (3, 3, 3))))
print('C_passes_gate', all(v >= lim for v, lim in zip(options['C'], (3, 3, 3))))
```

<OutputBox title='扩展示例运行结果' output='front [&#39;A&#39;, &#39;B&#39;, &#39;C&#39;]\nD_passes_gate True\nC_passes_gate False' />

<LineByLine code='def pareto_front(options):\n    front = []\n    for name, vec in options.items():\n        dominated = any(\n            all(o[j] &gt;= vec[j] for j in range(len(vec))) and\n            any(o[j] &gt; vec[j] for j in range(len(vec)))\n            for other, o in options.items() if other != name\n        )\n        if not dominated:\n            front.append(name)\n    return sorted(front)\n\noptions = {&#39;A&#39;: (5, 3, 4), &#39;B&#39;: (4, 4, 4), &#39;C&#39;: (2, 5, 5), &#39;D&#39;: (5, 3, 3)}\nprint(&#39;front&#39;, pareto_front(options))\nprint(&#39;D_passes_gate&#39;, all(v &gt;= lim for v, lim in zip(options[&#39;D&#39;], (3, 3, 3))))\nprint(&#39;C_passes_gate&#39;, all(v &gt;= lim for v, lim in zip(options[&#39;C&#39;], (3, 3, 3))))' :notes='["保留不被任何其他方案支配的候选", "存在某方案全维度不劣且至少一维更优即被支配", "非支配解进入前沿并排序保证输出稳定", "四个候选，D 被 A 在所有维度不劣且一维更优所支配", "打印前沿，D 被剪掉", "D 三个维度都过 3 分硬门槛", "C 第一维只有 2 分，被硬门槛淘汰", "score = Σ(w_i·s_i)/Σw_i；每个维度都要可核对，禁止把「熟悉/生态好」当印象分", "AHP 用一致性比率 CR &gt; 0.1 判矩阵自相矛盾；敏感性分析看解对权重扰动是否翻转", "ADR 固定八字段、编号只增不改、用 Superseded 取代旧决策，等价于 append-only 决策日志", "验证要指标加阈值、回退要可执行动作（特性开关 / 双写 / 对账），假设必须可证伪", "读结论用 inspect.signature / getsource / importlib.metadata.version / dis 落成事实；复盘结论转成 lint 与 CI 规则", "选型分两层：硬门槛（must-have）用布尔淘汰不可补偿约束，加权分只在合格池内排序", "score = Σ(w_i·s_i)/Σw_i；每个维度都要可核对，禁止把「熟悉/生态好」当印象分", "AHP 用一致性比率 CR &gt; 0.1 判矩阵自相矛盾；敏感性分析看解对权重扰动是否翻转"]' title='扩展示例逐行讲解' />


### 把主观维度换成可观测代理量

**选型维度的可观测量化与失效信号**

| 主观维度 | 可观测代理量 | 失效信号 | ADR 对应字段 |
| --- | --- | --- | --- |
| 团队熟悉度 | 能独立 on-call 排障的人数（bus factor） | 仅 1 人能改且无文档 | 约束 / 假设 |
| 生态成熟度 | 客户端语言数、issue 中位解决时长、发布节奏 | 半年无 release | 备选与代价 |
| 运维成本 | 部署组件数、升级需停机时长 | 需专人维护且无托管方案 | 代价 |
| 性能 | 同负载 p99 与资源配额的实测值 | 只引用厂商白皮书数字 | 验证 / 基准 |
| 可逆性 | 回退步骤数与数据迁移量 | 上线后无法回滚 | 回退方案 |


### rank reversal 与 Pareto 前沿先行剪枝

一次消息队列选型评审，三套方案在权重 (0.5, 0.3, 0.2) 下稳定由 A 胜出，会议纪要据此定案。半年后运维成本因自建集群扩容翻倍，把权重改成 (0.2, 0.2, 0.6) 重算，排名变成 C 第一、A 垫底，团队才发现当初结论完全由运维成本这个争议权重撑着，却没人测过它浮动时的稳定性。

补做敏感性扫描后，复盘把两处写进制度：一是所有加权定案必须附权重扰动表，标注排名翻转的临界权重；二是把运维成本从主观分改成可观测的部署组件数加升级停机时长，用硬门槛表达不接受需停机升级。行动项指定 owner，并要求把临界权重检查做成 CI 脚本随 ADR 提交。下面是复盘用的最小扫描：对同一矩阵跑两组权重，打印排名是否翻转。

```python
def score(row, w):
    return sum(a * b for a, b in zip(row, w))

opts = {'pg': (5, 3, 4), 'mysql': (4, 4, 4), 'sqlite': (2, 5, 5)}

def rank(w):
    return sorted(opts, key=lambda k: -round(score(opts[k], w), 6))

r1 = rank((0.5, 0.3, 0.2))
r2 = rank((0.2, 0.2, 0.6))
print('rank_original', r1)
print('rank_reviewed', r2)
print('ranking_flipped', r1 != r2)
```


### ADR 状态机与复盘结论的机器可验证性

ADR 不是写完就归档的散文，而是一条带状态迁移的记录链。

Nygard / `MADR` 格式给每条记录固定编号与字段：status（proposed 到 accepted 再到 superseded）、context、decision、consequences，被取代时不是删旧文，而是写 superseded by ADR-00xx 形成可追溯的双向链接，这样三年后能看到当时为什么选它、后来被什么条件推翻。

让 ADR 真正生效的是把验证写成可机器判定的触发条件，例如若 p99 连续 7 天超过 200ms 就重开 ADR-0012——把结论挂到监控指标上，而不是靠人记得回头看。

故障复盘同样要落到约束：blameless postmortem 用 contributing factors 而非单一 root cause，时间线之后每条行动项必须有 owner、截止时间与 verification 方式；

只有能被 lint、CI 或监控规则自动判定的行动项才算闭环，例如禁止裸 `os.remove` 要转成一个 pre-commit 检查函数，故障转移未演练要转成一个季度跑一次的混沌脚本。衡量复盘是否有效的指标是同类故障复发率与 `MTTR`，而不是纪要字数。

把这套约束随代码提交，技术判断才会从依赖个人记忆变成组织可复用的检查表。

<Exercise title='把复盘行动项转成可判定的 CI 检查' task='写一个检查函数，扫描若干行源码，凡出现裸 os.remove( 或 shutil.rmtree( 就返回违规行号列表，并用一个含两处违规、一处合规的样例自测；说明为什么这样的检查比复盘纪要里提醒大家更可靠。' solution='BANNED = (&#39;os.remove(&#39;, &#39;shutil.rmtree(&#39;)\n\ndef check(lines):\n    bad = []\n    for lineno, line in enumerate(lines, 1):\n        code = line.split(&#39;#&#39;, 1)[0]\n        if any(token in code for token in BANNED):\n            bad.append(lineno)\n    return bad\n\nsample = [\n    &#39;import os, shutil&#39;,\n    &#39;os.remove(path)&#39;,\n    &#39;shutil.move(src, trash)&#39;,\n    &#39;shutil.rmtree(cache)&#39;,\n]\nprint(&#39;violations&#39;, check(sample))\nprint(&#39;expected&#39;, [2, 4])' explain='把行动项写成对源码逐行扫描的纯函数，输出是确定的行号列表，可挂进 pre-commit 或 CI；纪要里的提醒依赖人主动记得，无法被自动判定也没有回归保护，同类违规会反复出现。sample 里第 2、4 行触发，第 3 行只是 shutil.move 被放过。' />

<Term word='superseded by（ADR 取代链）' text='ADR 被新决策推翻时不删旧记录，而是把 status 改成 superseded 并写明 superseded by ADR-00xx，新记录也回指被取代者，形成双向可追溯链；这样能还原当时约束、后来变化、为何重开，是 MADR / Nygard 格式区别于普通会议纪要的关键。' />


## 练习、自测与速记

<Exercise title='基础：实现硬门槛淘汰加加权评分' task='给定三个方案的五维评分与一个写入吞吐硬门槛，先淘汰不合格者，再对合格者用显式权重算加权分并输出赢家；解释为什么硬门槛不能并入加权。' solution='C = [(&#39;w&#39;, 0.4), (&#39;lat&#39;, 0.3), (&#39;ops&#39;, 0.3)]\nO = {&#39;a&#39;: (5, 3, 2), &#39;b&#39;: (4, 5, 3), &#39;c&#39;: (1, 5, 5)}\nMUST = 3\ndef sc(v): return round(sum(w*x for (_,w),x in zip(C,v))/sum(w for _,w in C), 3)\npool = [k for k in O if O[k][0] &gt;= MUST]\nprint(&#39;pool&#39;, pool)\nprint(&#39;winner&#39;, max(pool, key=lambda k: sc(O[k])))' explain='c 的写入 1 分被硬门槛淘汰；硬门槛表达不可补偿的约束，若并入加权，高熟悉度会把不达标的方案算成可接受。加权只在合格池内排序。' />

<Exercise title='进阶：用 inspect.signature 验证一个 API 假设' task='用 inspect.signature 读取 json.dumps 的参数，打印 obj 的参数类别与哪些带默认值参数是 KEYWORD_ONLY，并据此判断「能否用位置参数传 skipkeys」。' solution='import inspect, json\nsig = inspect.signature(json.dumps)\nkw = [p.name for p in sig.parameters.values() if p.kind is p.KEYWORD_ONLY]\nprint(&#39;obj kind&#39;, sig.parameters[&#39;obj&#39;].kind.name)\nprint(&#39;keyword-only&#39;, kw)\nprint(&#39;skipkeys keyword-only&#39;, sig.parameters[&#39;skipkeys&#39;].kind is inspect.Parameter.KEYWORD_ONLY)' explain='星号之后所有带默认值的参数都是 KEYWORD_ONLY，skipkeys 只能按关键字传；凭印象写 json.dumps(obj, False) 会报 TypeError。obj 本身是 POSITIONAL_OR_KEYWORD，读签名把印象变成可核对的事实。' />

<Quiz no='121-1' q='关于选型里的硬门槛与加权评分，哪一项准确？' :options='["硬门槛用布尔淘汰表达不可补偿约束，加权只在合格者内排序", "所有维度都应加权，硬门槛会丢信息", "权重和必须大于 1 才能拉开差距", "敏感性分析是为了把权重调到让心仪方案胜出"]' answer="0" explain='加权模型假设维度可互相补偿，硬门槛表达不可补偿的约束；先淘汰再排序才不会让不达标方案靠别的维度翻盘。敏感性分析是检验结论稳定性，不是调权重凑结果。' />

<Quiz no='121-2' q='一条合格的 ADR 最不该缺哪一类字段？' :options='["可证伪的验证指标与可执行的回退动作", "作者的职称", "方案的市场占有率", "会议纪要的出席名单"]' answer="0" explain='ADR 的价值在于决策可审计、可回退；验证要有指标与阈值，回退要是特性开关、双写、对账这类可执行动作，缺了这两类字段记录就退化为口号。' />

<Quiz no='121-3' q='用 inspect.signature(json.dumps) 在 3.13 上能直接核对的结论是？' :options='["obj 是 POSITIONAL_OR_KEYWORD，星号之后带默认值的参数都是 KEYWORD_ONLY", "json.dumps 是 C 实现，查不到签名", "所有参数都能按位置传入", "签名会随 PYTHONHASHSEED 变化"]' answer="0" explain='3.13 的签名是 (obj, *, skipkeys=False, ..., **kw)：obj 可用位置或关键字传入，但星号之后的参数都是 KEYWORD_ONLY，因此 json.dumps(obj, False) 会抛 TypeError。这是可用 inspect 直接核对的事实。' />

<KnowledgeCard :points='["选型分两层：硬门槛（must-have）用布尔淘汰不可补偿约束，加权分只在合格池内排序", "score = Σ(w_i·s_i)/Σw_i；每个维度都要可核对，禁止把「熟悉/生态好」当印象分", "AHP 用一致性比率 CR &gt; 0.1 判矩阵自相矛盾；敏感性分析看解对权重扰动是否翻转", "ADR 固定八字段、编号只增不改、用 Superseded 取代旧决策，等价于 append-only 决策日志", "验证要指标加阈值、回退要可执行动作（特性开关 / 双写 / 对账），假设必须可证伪", "读结论用 inspect.signature / getsource / importlib.metadata.version / dis 落成事实；复盘结论转成 lint 与 CI 规则"]' :pitfalls='["把「我熟悉」「生态好」直接写成分数，评审时各说各话", "定案不做敏感性分析，上线后换个权重结论就翻转", "复盘只有纪要，行动项没有 owner、验证与自动化", "追逐每个新框架却不建立评估维度，选型的依据永远只剩热度"]' summary='资深的分水岭是能否在信息不全时给出带假设、带代价、可验证的方案，而不是知道多少 API' />

1. 选型分两层：硬门槛（must-have）用布尔淘汰不可补偿约束，加权分只在合格池内排序

2. score = Σ(w_i·s_i)/Σw_i；每个维度都要可核对，禁止把「熟悉/生态好」当印象分

3. AHP 用一致性比率 CR > 0.1 判矩阵自相矛盾；敏感性分析看解对权重扰动是否翻转

[下一讲：实战 01 · 待办清单 CLI 与命令分发](/projects/cli-todo)

```bash
python -c "import dis, sys; print(sys.version.split()[0]); dis.dis(lambda x:x)"
```

把输入换成你自己的数据，观察结果是否仍符合 能力矩阵与短板 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

<Predict no='121-4' q='把上面评分矩阵的运维成本权重从 0.20 提到 0.60、其余相应压低，排名最可能怎样变化？' :options='["翻转：SQLite 因运维满分升到第一，ClickHouse 退到第二", "不变：ClickHouse 仍稳居第一", "报错：权重和不再等于 1"]' answer='0' output='base [&#39;clickhouse&#39;, &#39;es&#39;, &#39;sqlite&#39;] 变为 ops-heavy [&#39;sqlite&#39;, &#39;clickhouse&#39;, &#39;es&#39;]' explain='运维成本权重占主导时，SQLite 的 ops_cost=5 抵消了写入低分，排名翻转说明该结论对权重高度敏感；这时应回到「写入五万每秒」硬门槛淘汰 SQLite，而不是接受翻转后的排序。' />

<FillBlank no='121-5' tpl='___ score(opt, weights):' :answers='["def"]' hint='回想本讲关于 能力矩阵与短板 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 选型评估：把主观偏好变成硬门槛加加权矩阵 的落点。' />
