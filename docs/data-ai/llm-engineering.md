---
title: 第 104 讲 · LLM 应用工程：Prompt、RAG、Agent 与成本
description: 把大模型能力做成可靠、可控、可观测的应用
---

<StageHeader stage='L9 · 数据与 AI' level='★★★★☆' time='50 分钟' goal='把大模型能力做成可靠、可控、可观测的应用' prereq='第 103 讲 · 深度学习与 PyTorch：张量、自动微分与训练循环' />

# 第 104 讲 · LLM 应用工程：Prompt、RAG、Agent 与成本

到这里，数据处理、经典算法和模型评估都已经过了一遍。可把一个模型变成用户真正能用的产品，中间还隔着一层常被低估的工程问题：检索回来的内容对不对、上下文放得下多少、工具调用失败后谁负责收尾、一次请求花了多少钱。这些和提示词写得好不好关系不大，却直接决定系统能不能上线。

本讲从一次「回答很流利却答非所问」的上线反馈切入，先算清上下文这笔账，再一步步走到分块与检索质量、Agent 循环的约束、成本模型，最后用一个纯标准库的最小实现把这些约束落成可运行的代码。需要你了解函数、字典、异常处理与基本的 `HTTP` 概念；学完之后，你能独立给一个大模型应用划出预算、超时与降级边界，而不是只停留在调用接口。


## 一个「答得流利却答非所问」的 RAG 系统

一个 RAG 问答系统上线后，用户反馈「答案看着流利，但经常答非所问，还偶尔把 A 产品的参数安到 B 产品上」。团队第一反应是换更大的模型，成本翻了三倍，问题只改善了一点。

真正的故障点在模型之外：PDF 按固定 500 字切块，把表格拦腰截断；检索只取相似度 Top-5，其中三块来自同一页的重复页眉；prompt 把八块内容一股脑塞进上下文，关键条款被埋在中间；Agent 循环没有步数上限，一次工具返回异常就反复重试到超时。这类系统的工程质量几乎全压在检索、预算、幂等与可观测性上。

本讲用纯标准库实现一个可运行的最小 RAG，把每个环节的错误都变成能看见、能测量的现象。

<Callout type="warn" title='先看一个真实会出错的写法' text='按固定字数切块，表格与条款被拦腰截断：检索到的块语义不完整，模型只能看到半句话，进而用参数知识补全' />


## 先算账：上下文窗口怎么分配

Prompt 与结构化输出先定下这次调用的输入契约：系统提示、检索片段、对话历史、用户问题要组装成一条 prompt，并要求模型按可解析、可溯源的结构（带引用的段落或 `JSON`）回答，而不是放任自由发挥。

组装的第一道硬约束是上下文窗口不是「越多越好」：一次调用的 Token 由系统提示、检索片段、对话历史、用户问题与预留输出共同占用；若窗口 8K、输出要留 1K、历史与提示占 2K，检索片段的预算就只剩 5K。分块要对付两个相互冲突的要求：块太小则语义不完整（表格被切断、指代丢失），块太大则一个块里混进多个主题、向量被稀释。

实践上按文档结构切（标题、段落、表格整体），再设 200 到 500 Token 的目标大小与 10% 到 15% 的重叠，同时给每块写入 `section`、`page`、`doc_id` 等元数据，供过滤与溯源。还要主动去重：页眉页脚、目录、重复模板在不同页的向量几乎一样，会白白挤占 Top-K 名额。

把「召回了几块、各占多少 Token、被丢弃了几块」打进日志，才谈得上调优。

**上下文预算表（以 8K 窗口为例，8192 Token 正好用满）**

| 组成 | 预算上限 | 超限时的处理 |
| --- | --- | --- |
| 系统提示 + 输出格式约束 | 600 Token | 精简指令，移到系统消息 |
| 对话历史 | 1200 Token | 摘要化或滑动窗口丢弃最早轮次 |
| 检索片段 | 4992 Token | 按重排分数裁剪，并把最优块放首尾 |
| 用户问题 | 400 Token | 超长问题先做查询改写 |
| 预留输出 | 1000 Token | 不足时直接降级，不强行截输出 |

<ConceptDiagram type='compare2' title='第 104 讲 · 上下文预算与分块：先算账，再往里塞' labels='上下文预算与分块：先算账，再往里塞|检索质量：把「答非所问」拆成可测的指标|Agent 循环与成本：把不确定性关进笼子|Token 成本与降级' caption='把大模型能力做成可靠、可控、可观测的应用' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 分块、去重与元数据：让检索拿得到完整语义

```python
import collections

DOCS = [
    ('A-1', '型号 A100 支持 8 路输入，质保三年'),
    ('A-2', 'A100 的工作温度为 0 到 40 摄氏度'),
    ('B-1', '型号 B200 支持 4 路输入，质保一年'),
]

def tokens(s):
    return len(s) + len(s.split()) // 2  # 粗略估算，仅用于演示预算

def retrieve(query, k=2, budget=40):
    q = set(query)
    scored = []
    for doc_id, text in DOCS:
        overlap = len(q & set(text)) / (len(q) + 1)
        scored.append((overlap, doc_id, text))
    scored.sort(reverse=True)
    picked, used = [], 0
    for score, doc_id, text in scored[:k]:
        if used + tokens(text) > budget: break
        picked.append((doc_id, text)); used += tokens(text)
    return picked, used

picked, used = retrieve('A100 质保', k=3)
print('used', used, 'blocks', len(picked))
print([doc_id for doc_id, _ in picked])
```

<OutputBox title='主示例运行结果' output='used 40 blocks 2\n[&#39;A-1&#39;, &#39;A-2&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import collections\n\nDOCS = [\n    (&#39;A-1&#39;, &#39;型号 A100 支持 8 路输入，质保三年&#39;),\n    (&#39;A-2&#39;, &#39;A100 的工作温度为 0 到 40 摄氏度&#39;),\n    (&#39;B-1&#39;, &#39;型号 B200 支持 4 路输入，质保一年&#39;),\n]\n\ndef tokens(s):\n    return len(s) + len(s.split()) // 2  # 粗略估算，仅用于演示预算\n\ndef retrieve(query, k=2, budget=40):\n    q = set(query)\n    scored = []\n    for doc_id, text in DOCS:\n        overlap = len(q &amp; set(text)) / (len(q) + 1)\n        scored.append((overlap, doc_id, text))\n    scored.sort(reverse=True)\n    picked, used = [], 0\n    for score, doc_id, text in scored[:k]:\n        if used + tokens(text) &gt; budget: break\n        picked.append((doc_id, text)); used += tokens(text)\n    return picked, used\n\npicked, used = retrieve(&#39;A100 质保&#39;, k=3)\nprint(&#39;used&#39;, used, &#39;blocks&#39;, len(picked))\nprint([doc_id for doc_id, _ in picked])' :notes='["导入 collections 备用；本例用集合交集做关键词打分", "空行，只用于分隔逻辑块，不影响执行结果。", "模拟文档库，每条带 doc_id 便于溯源", "三条文档分别是两个型号的参数", "文档 1：A100 路数与质保", "文档 2：A100 工作温度", "文档 3：B200 参数，用于检验是否会串型号", "空行，只用于分隔逻辑块，不影响执行结果。", "定义极简 Token 估算：真实项目用 tiktoken 或服务端计数", "字符数加词数补偿，仅用于演示预算裁剪", "空行，只用于分隔逻辑块，不影响执行结果。", "retrieve 接受 k（候选数）与 budget（Token 预算）两个独立约束", "把查询转成字符集合，演示关键词召回", "scored 存放 (分数, 文档号, 正文)", "逐条计算字符重合度作为相似度", "记录三元组", "按分数降序，模拟 Top-K 排序", "picked 保存最终入选块，used 累计已用预算", "遍历候选，关键是预算与 k 双重限制", "超预算就停止，宁可少给也不撑爆窗口", "入选并记录已用 Token", "返回块与用量，供日志与观测", "查询 A100 质保，k=3 但预算只够 2 块", "空行，只用于分隔逻辑块，不影响执行结果。", "打印实际用量与块数", "打印溯源 ID，答案必须能指回这些块", "Agent 四道闸：步数上限、总预算上限、`timeout` 与退避、幂等键；每轮记 Token / 耗时 / `trace_id`"]' title='第 104 讲 · LLM 应用工程：Prompt、RAG、Agent 与成本' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='Prompt 与结构化输出先定下这次调用的输入契约：系统提示、检索片段、对话历史、用户问题要组装成一条 prompt，并要求模型按可解析、可溯源的结构（带引用的段落或 JSON）回答，而不是放任自由发挥。组装的第一道硬约束是上下文窗口不是「越多越好」：一次调用的 Token 由系统提示、检索片段、对…' />


### 对照：带溯源的答案组装

```python
# 承接主示例：DOCS、tokens()、retrieve() 已在上方定义，本片段需与主示例一同运行。
def assemble(picked, question, max_ctx=60):
    head = '资料：' + ' | '.join(t for _, t in picked)
    if len(head) > max_ctx:
        head = head[:max_ctx] + '...[截断]'
    prompt = head + chr(10) + '问题：' + question + chr(10) + '仅依据资料回答，无依据则回答未找到。'
    return prompt

blocks, _ = retrieve('B200 质保', k=3, budget=40)
print(assemble(blocks, 'B200 质保多久？'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='资料：型号 B200 支持 4 路输入，质保一年 | 型号 A100 支持 8 路输入，质保三年...[截断]\n问题：B200 质保多久？\n仅依据资料回答，无依据则回答未找到。' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import collections\n\nDOCS = [\n    (&#39;A-1&#39;, &#39;型号 A100 支持 8 路输入，质保三年&#39;),\n    (&#39;A-2&#39;, &#39;A100 的工作温度为 0 到 40 摄氏度&#39;),\n    (&#39;B-1&#39;, &#39;型号 B200 支持 4 路输入，质保一年&#39;),\n]\n\ndef tokens(s):\n    return len(s) + len(s.split()) // 2  # 粗略估算，仅用于演示预算\n\ndef retrieve(query, k=2, budget=40):\n    q = set(query)\n    scored = []\n    for doc_id, text in DOCS:\n        overlap = len(q &amp; set(text)) / (len(q) + 1)\n        scored.append((overlap, doc_id, text))\n    scored.sort(reverse=True)\n    picked, used = [], 0\n    for score, doc_id, text in scored[:k]:\n        if used + tokens(text) &gt; budget: break\n        picked.append((doc_id, text)); used += tokens(text)\n    return picked, used\n\npicked, used = retrieve(&#39;A100 质保&#39;, k=3)\nprint(&#39;used&#39;, used, &#39;blocks&#39;, len(picked))\nprint([doc_id for doc_id, _ in picked])", "note": "上下文预算与分块：先算账，再往里塞"}, {"label": "对照 / 进阶", "code": "# 承接主示例：DOCS、tokens()、retrieve() 已在上方定义，本片段需与主示例一同运行。\ndef assemble(picked, question, max_ctx=60):\n    head = &#39;资料：&#39; + &#39; | &#39;.join(t for _, t in picked)\n    if len(head) &gt; max_ctx:\n        head = head[:max_ctx] + &#39;...[截断]&#39;\n    prompt = head + chr(10) + &#39;问题：&#39; + question + chr(10) + &#39;仅依据资料回答，无依据则回答未找到。&#39;\n    return prompt\n\nblocks, _ = retrieve(&#39;B200 质保&#39;, k=3, budget=40)\nprint(assemble(blocks, &#39;B200 质保多久？&#39;))", "note": "检索质量：把「答非所问」拆成可测的指标"}]' title='两种写法对照' note='差异集中在 Prompt 与结构化输出；先看输出，再找背后的规则。' />


## 检索质量怎么量：Recall@K 与拒答率

Embedding 与向量检索是这套问答的地基：把文本映射成高维向量，用余弦距离或内积近似语义相关，擅长同义改写，却对精确编号、型号、错误码不敏感，因为这类 token 在训练语料里往往被切分或低频、向量位置不稳定。检索不是一次性配好就完事的组件，它有自己独立的评价口径。

常用指标有 `Recall@K`（人工标注的相关块是否出现在前 K 个结果里）、MRR（第一个正确结果的排名倒数），以及答案的引用命中率（生成内容能否回溯到召回块）。

混合检索通常优于单一向量检索：`BM25` 等关键词检索对精确编号、型号、错误码更稳，向量检索对同义改写更稳，用 RRF（倒数排名融合）把两路结果合并；重排阶段再对 Top-20 做精排取 Top-5。

要特别注意「lost in the middle」现象：关键信息放在长上下文的中段时，模型引用它的概率明显下降，所以组装 prompt 时应把最相关的块放在首尾。评估集至少要包含无答案的问题、需要跨块综合的问题、含否定词的问题，否则指标会虚高。

<Term word='Prompt 与结构化输出' text='Prompt 与结构化输出先定下这次调用的输入契约：系统提示、检索片段、对话历史、用户问题要组装成一条 prompt，并要求模型按可解析、可溯源的结构（带引用的段落或 JSON）回答，而不是放任自由发挥。组装的第一道硬约束是上下文窗口不是「越多越好」：一次调用的 Token 由系统提示、检索片段、对话历史、用户问题与预…' />

<Term word='Embedding 与向量检索' text='Embedding 与向量检索是这套问答的地基：把文本映射成高维向量，用余弦距离或内积近似语义相关，擅长同义改写，却对精确编号、型号、错误码不敏感，因为这类 token 在训练语料里往往被切分或低频、向量位置不稳定。检索不是一次性配好就完事的组件，它有自己独立的评价口径。常用指标有 `Recall@K`（人工标注的相关…' />


## Agent 循环的四道闸

工具调用让模型能查数据库或调接口，也把失败面放大了一圈。一条可靠的调用链需要四道闸：步数上限（如最多 6 轮，防止模型在工具报错后反复重试）、总预算上限（累计 Token 或金额，超限直接降级为「无法回答」）、超时与退避（网络调用必须带 `timeout`，重试只对幂等操作生效）、以及幂等键（写操作重复执行不能重复扣款）。

每一轮都要记录输入 / 输出 Token、耗时、工具名、参数摘要、返回状态与 `trace_id`；流式输出要同时处理连接中断与部分结果。降级路径也得提前设计：检索无结果时明确回答「资料中未找到」，而不是让模型用参数知识补全；模型超时时返回已生成的部分加一句提示，而不是空响应。这些约束与提示词措辞无关，属于工程契约。

**Agent 循环的硬性约束**

| 约束 | 建议默认值 | 触犯后果 |
| --- | --- | --- |
| 最大步数 | 6 轮 | 工具报错后无限重试，请求挂死 |
| 单次调用超时 | 10-30 秒 | 长连接堆积占满连接池 |
| 累计 Token/金额上限 | 按业务设 | 一次异常吃掉整日预算 |
| 重试策略 | 仅幂等操作，指数退避 | 重复下单、重复扣款 |
| 日志字段 | trace_id/工具/参数摘要/耗时/Token | 线上无法复盘，只能靠猜 |

<FlowTimeline :steps='[{"title": "上下文预算与分块：先算账，再往里塞", "desc": "Prompt 与结构化输出先定下这次调用的输入契约：系统提示、检索片段、对话历史、用…", "tone": "blue"}, {"title": "检索质量：把「答非所问」拆成可测的指标", "desc": "Embedding 与向量检索是这套问答的地基：把文本映射成高维向量，用余弦距离或内…", "tone": "purple"}, {"title": "Agent 循环与成本：把不确定性关进笼子", "desc": "工具调用让模型能查数据库或调接口，也把失败面放大了一圈。一条可靠的调用链需要四道闸…", "tone": "orange"}, {"title": "工程落地", "desc": "带预算、超时、幂等与可观测的调用封装", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

<ConceptDiagram type='layers3' title='第 104 讲 · 分层视角' labels='上下文预算与分块：先算账，再往里塞|检索质量：把「答非所问」拆成可测的指标|Agent 循环与成本：把不确定性关进笼…|Token 成本与降级' caption='Agent 循环与成本：把不确定性关进笼子' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 Token 成本与降级 落在哪一层。


## 成本模型与失败模式

```python
def cost(prompt_tokens, output_tokens, price_in=0.002, price_out=0.008):
    return round((prompt_tokens / 1000) * price_in + (output_tokens / 1000) * price_out, 6)

for n in (2000, 8000, 32000):
    print(n, 'prompt tokens ->', cost(n, 500), 'USD per call')
print('10000 calls @8k ->', cost(8000, 500) * 10000, 'USD')
```

<OutputBox title='原理验证' output='2000 prompt tokens -&gt; 0.008 USD per call\n8000 prompt tokens -&gt; 0.02 USD per call\n32000 prompt tokens -&gt; 0.068 USD per call\n10000 calls @8k -&gt; 200.0 USD' />

**RAG 失败模式与定位手段**

| 现象 | 常见根因 | 定位指标 |
| --- | --- | --- |
| 答非所问 | 分块切断语义、Top-K 混入无关块 | Recall@K、命中块的人工抽检 |
| 参数串到别的型号 | 未做元数据过滤、块内缺标题 | 检索结果里的 doc_id 分布 |
| 答案编造 | prompt 未禁止无依据作答 | 引用命中率、无答案问题的拒答率 |
| 关键条款被忽略 | 片段放在长上下文中段 | 调整块顺序后的引用率对比 |
| 成本突然翻倍 | Agent 循环失控或历史未裁剪 | 每轮 Token、步数、工具调用次数 |


## 为什么「塞更多上下文」反而更差

向量检索把文本映射成高维向量，用余弦距离或内积近似语义相关；它擅长同义改写，却对精确编号、型号、错误码不敏感，因为这类 token 在训练语料里往往被切分或低频，向量位置不稳定。`BM25` 等稀疏检索恰好相反，靠词频与逆文档频率匹配字面。

混合检索用 RRF 把两路排名融合（分数取 `1/(k+rank)` 之和，不依赖两路分数的量纲），再交给重排模型精排。生成侧的注意力计算量随上下文长度增长，且实证研究表明长上下文中段信息的引用率偏低（lost in the middle），因此「把更多块塞进去」既增加成本、又可能拉低准确率。

这也是为什么预算裁剪、去重、重排与块顺序是工程问题，而不是提示词技巧问题。


## 工程落地：带预算、超时与幂等的调用封装

下面这段不依赖任何大模型 SDK，用标准库把一次「组装 → 生成」的最小调用封装成有边界的操作：检索结果由调用方以 blocks 传入，入口先判空，没有资料就明确降级为「资料中未找到」；接着用 `estimate_tokens` 核对上下文预算，超限直接降级；生成阶段套一层 `MAX_STEPS` 步数上限的循环，作为工具报错后反复重试的防御骨架；每次响应带上 `trace` 与按 prompt 内容算出的幂等键 `idem`，供上游打点与去重。

要强调这只是一副骨架：`call_model` 首次就返回文本，循环体实际只走一步；耗时、真正的重试、幂等去重与检索都留给真实项目——把 `call_model` 换成带 `timeout` 与重试的 SDK 调用、把每轮耗时与 Token 接进日志、用去重表加唯一索引让幂等键真正挡住重复写。

重点不在代码量，而在每个失败分支都有一个明确、可观测的出口。

```python
import hashlib, time, uuid

BUDGET_TOKENS = 4000
MAX_STEPS = 6

def estimate_tokens(s):
    return len(s) // 3 + 1

def call_model(prompt, trace_id):
    time.sleep(0.001)  # 模拟网络往返
    return {'text': '依据资料：质保一年', 'tokens': estimate_tokens(prompt), 'trace': trace_id}

def answer(question, blocks, idem_key=None):
    trace = str(uuid.uuid4())[:8]
    if not blocks:
        return {'text': '资料中未找到', 'trace': trace, 'degraded': True}
    prompt = '资料：' + ' | '.join(blocks) + chr(10) + '问题：' + question
    if estimate_tokens(prompt) > BUDGET_TOKENS:
        return {'text': '上下文超预算，已降级', 'trace': trace, 'degraded': True}
    key = idem_key or hashlib.sha256(prompt.encode()).hexdigest()[:16]
    for step in range(MAX_STEPS):
        r = call_model(prompt, trace)
        if r['text']:
            return {'text': r['text'], 'trace': trace, 'idem': key, 'step': step, 'tokens': r['tokens']}
    return {'text': '达到最大步数', 'trace': trace, 'degraded': True}

print(answer('B200 质保多久？', ['型号 B200 质保一年']))
print(answer('未知型号？', []))
```

<Callout type="idea" title='落地提示' text='为每次调用记录输入/输出/耗时/Token、设置步数与预算上限、工具调用做幂等与超时、关键结论要求可溯源引用' />

<ArchBlueprint title='第 104 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "上下文预算与分块：先算账，再往里塞", "protocol": "调用 / 请求", "items": [{"label": "上下文预算与分块：先算账…", "sub": "输入与前置", "detail": "Prompt 与结构化输出先定下这次调用的输入契约：系统提示、检索片段、对话历史、用户问题要组装成一条 prompt，并要求模型按可解析、可溯源的结构（带引用的段落或 JSON）回答，而不是放任自由发挥。组装的第一道硬约束是上下文窗口不是「越多越好」：一次调用的 Token 由系统提示、检索片段、对…", "tone": "blue"}]}, {"name": "核心规则", "note": "检索质量：把「答非所问」拆成可测的指标", "protocol": "语言 / 运行时协议", "items": [{"label": "检索质量：把「答非所问」…", "sub": "状态与边界", "detail": "Embedding 与向量检索是这套问答的地基：把文本映射成高维向量，用余弦距离或内积近似语义相关，擅长同义改写，却对精确编号、型号、错误码不敏感，因为这类 token 在训练语料里往往被切分或低频、向量位置不稳定。检索不是一次性配好就完事的组件，它有自己独立的评价口径。常用指标有…", "tone": "purple"}]}, {"name": "落地与收尾", "note": "Agent 循环与成本：把不确定性关进笼子", "items": [{"label": "Agent 循环与成本…", "sub": "工程处理", "detail": "工具调用让模型能查数据库或调接口，也把失败面放大了一圈。一条可靠的调用链需要四道闸：步数上限（如最多 6 轮，防止模型在工具报错后反复重试）、总预算上限（累计 Token 或金额，超限直接降级为「无法回答」）、超时与退避（网络调用必须带 `timeout`，重试只对幂等操作生效）、以及幂等键（写操作…", "tone": "green"}]}]' />

<CheckList id='P104a' title='上线前自检' :items='["能复现并解释「按固定字数切块，表格与条款被拦腰截断」", "能复现并解释「把 Top-K 结果直接拼进 prompt 不做去重」", "能复现并解释「工具调用无步数与预算上限」", "能用一条命令验证 Prompt 与结构化输出", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import textwrap; print(textwrap.wrap('检索内容按语义切块再拼进提示词', 8))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 Prompt 与结构化输出 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 按固定字数切块，表格与条款被拦腰截断 | 检索到的块语义不完整，模型只能看到半句话，进而用参数知识补全 | 按文档结构切（标题/段落/表格整体），保留 section 与 page 元数据，再设目标 Token 与重叠 |
| 把 Top-K 结果直接拼进 prompt 不做去重 | 页眉、目录、模板在不同页向量几乎相同，会挤占名额并稀释关键信息 | 按 doc_id + 内容指纹去重，重排后把最相关块放在上下文首尾 |
| 工具调用无步数与预算上限 | 模型遇到工具异常会反复重试，单次请求可能耗尽整日预算并占满连接池 | 设最大步数、累计 Token/金额上限、超时与退避；写操作带幂等键并只对幂等调用重试 |

<Callout type="warn" title='本讲最容易踩的坑' text='按固定字数切块，表格与条款被拦腰截断：检索到的块语义不完整，模型只能看到半句话，进而用参数知识补全' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：按固定字数切块，表格与条款被拦腰截断", "body": "检索到的块语义不完整，模型只能看到半句话，进而用参数知识补全", "tip": "按文档结构切（标题/段落/表格整体），保留 section 与 page 元数据，再设目标 Token 与重叠"}, {"title": "第 2 步：把 Top-K 结果直接拼进 prompt…", "body": "页眉、目录、模板在不同页向量几乎相同，会挤占名额并稀释关键信息", "tip": "按 doc_id + 内容指纹去重，重排后把最相关块放在上下文首尾"}, {"title": "第 3 步：工具调用无步数与预算上限", "body": "模型遇到工具异常会反复重试，单次请求可能耗尽整日预算并占满连接池", "tip": "设最大步数、累计 Token/金额上限、超时与退避；写操作带幂等键并只对幂等调用重试"}]' />


## 高维距离集中：余弦与内积的判别力退化

把 query 与文档向量归一化到单位长度后，内积 q·d 等于 `cos(theta)`，余弦与内积排序完全等价；若再比较 L2 距离，`norm`，三者互为单调变换，换度量救不了召回。

```python
norm(q-d)^2 = 2 - 2cos(theta)
```

真正的问题是高维距离集中：设 q、d 各分量独立同分布、均值 0、方差 sigma^2，则 `norm(q-d)^2` 是 2d 个独立项平方和，均值 2d·sigma^2、方差 8d·sigma^4（卡方分布），相对标准差 = `sqrt`，随 d 增大趋于 0。

```python
sqrt(8d·sigma^4)/(2d·sigma^2) = sqrt(2/d)
```

于是所有文档到 query 的距离越挤在同一个值附近，max/min 比值趋于 1，Top-K 名次由微小噪声决定，`Recall@K` 变得不稳定。余弦也逃不掉：随机两向量的 `|cos(theta)|` 期望约 `sqrt(2/(pi·d))`，`d=1024` 时不到 0.025，向量几乎两两正交。

这解释了「0.78 还是 0.81」在千维空间没有区分意义、阈值不能跨版本复用；压到 256 或 384 维常反而更省内存、更稳。缓解只有两类：投到低维子空间（对比学习、PCA 白化），或 ANN 先圈候选再精排。

```python
import math, random

def l2(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

def cos_abs(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return abs(dot / (na * nb))

def spread(dim, pairs, seed):
    rng = random.Random(seed)
    ds, cs = [], []
    for _ in range(pairs):
        a = [rng.gauss(0, 1) for _ in range(dim)]
        b = [rng.gauss(0, 1) for _ in range(dim)]
        ds.append(l2(a, b))
        cs.append(cos_abs(a, b))
    return round(max(ds) / min(ds), 2), round(sum(cs) / pairs, 4)

for d in (2, 16, 128, 1024):
    ratio, mean_cos = spread(d, 120, 11)
    print('dim', d, 'dist_max/min', ratio, 'mean_abs_cos', mean_cos)
```

<OutputBox title='扩展示例运行结果' output='dim 2 dist_max/min 28.78 mean_abs_cos 0.6624\ndim 16 dist_max/min 2.2 mean_abs_cos 0.2005\ndim 128 dist_max/min 1.32 mean_abs_cos 0.0671\ndim 1024 dist_max/min 1.12 mean_abs_cos 0.0258' />

<LineByLine code='import math, random\n\ndef l2(a, b):\n    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))\n\ndef cos_abs(a, b):\n    dot = sum(x * y for x, y in zip(a, b))\n    na = math.sqrt(sum(x * x for x in a))\n    nb = math.sqrt(sum(y * y for y in b))\n    return abs(dot / (na * nb))\n\ndef spread(dim, pairs, seed):\n    rng = random.Random(seed)\n    ds, cs = [], []\n    for _ in range(pairs):\n        a = [rng.gauss(0, 1) for _ in range(dim)]\n        b = [rng.gauss(0, 1) for _ in range(dim)]\n        ds.append(l2(a, b))\n        cs.append(cos_abs(a, b))\n    return round(max(ds) / min(ds), 2), round(sum(cs) / pairs, 4)\n\nfor d in (2, 16, 128, 1024):\n    ratio, mean_cos = spread(d, 120, 11)\n    print(&#39;dim&#39;, d, &#39;dist_max/min&#39;, ratio, &#39;mean_abs_cos&#39;, mean_cos)' :notes='["欧氏距离：2d 个独立项平方和的平方根", "空行，只用于分隔逻辑块，不影响执行结果。", "余弦绝对值：单位向量下与内积、L2 互为单调变换", "固定种子保证输出可核对，返回 max/min 距离比与平均 |cos|", "空行，只用于分隔逻辑块，不影响执行结果。", "遍历四个维度，观察相对标准差 sqrt(2/d) 的收缩", "这一行 `dot = sum(x * y for x, y in zip(a, b))` 的作用，可对照上方输出逐项核对。", "这一行 `na = math.sqrt(sum(x * x for x in a))` 的作用，可对照上方输出逐项核对。", "这一行 `nb = math.sqrt(sum(y * y for y in b))` 的作用，可对照上方输出逐项核对。", "这一行 `return abs(dot / (na * nb))` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `def spread(dim, pairs, seed):` 的作用，可对照上方输出逐项核对。", "这一行 `rng = random.Random(seed)` 的作用，可对照上方输出逐项核对。", "这一行 `ds, cs = [], []` 的作用，可对照上方输出逐项核对。", "这一行 `for _ in range(pairs):` 的作用，可对照上方输出逐项核对。", "这一行 `a = [rng.gauss(0, 1) for _ in range(dim)]` 的作用，可对照上方输出逐项核对。", "这一行 `b = [rng.gauss(0, 1) for _ in range(dim)]` 的作用，可对照上方输出逐项核对。", "这一行 `ds.append(l2(a, b))` 的作用，可对照上方输出逐项核对。", "这一行 `cs.append(cos_abs(a, b))` 的作用，可对照上方输出逐项核对。", "这一行 `return round(max(ds) / min(ds), 2), round(sum(cs) / ` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `for d in (2, 16, 128, 1024):` 的作用，可对照上方输出逐项核对。", "这一行 `ratio, mean_cos = spread(d, 120, 11)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;dim&#39;, d, &#39;dist_max/min&#39;, ratio, &#39;mean_abs_cos` 的作用，可对照上方输出逐项核对。"]' title='扩展示例逐行讲解' />

<ConceptDiagram type='flow4' title='第 104 讲 · 扩展图解' labels='norm(q-d)^2=2-2cos|相对标准差 sqrt(2/d)|max/min 趋近 1|Recall@K 抖动' caption='单位向量下 L2、内积、余弦互为单调变换；高维集中让排序失去判别力，换度量救不了召回' />


### HNSW 与 IVF-PQ 的召回吞吐前沿

Flat 检索与 N 个向量逐个算内积，单次查询 `O(N·d)`，N 上千万时 QPS 掉到个位数，于是用 ANN 换吞吐，代价是 `Recall@K` 不再为 1。

`HNSW` 建分层可导航小世界图：节点按指数分布随机分配到最高层，查询从顶层入口贪心下探，底层用 efSearch 个候选做宽度优先；建图参数 M（每层邻居数，常见 16 到 64）与 efConstruction 决定图质量与构建内存，efSearch 越大召回越高、延迟越长，内存是每向量约 M·8 字节邻接表加原始向量，一千万条 768 维 float32 光向量就约 30GB。

IVF-PQ 先用 k-means 把空间切成 nlist 个粗簇、查询只扫 nprobe 个，再用乘积量化把残差切成 m 段、每段量化到 256 个中心，单向量压到 m 字节，代价是量化误差。

真实项目用 faiss（`faiss/IndexHNSW.cpp` 与 `faiss/IndexIVFPQ.cpp`）或 hnswlib 在 C++ 层算距离；本讲实测用纯标准库复现距离集中而非图索引。

选型看 QPS 与内存：内存足选 `HNSW`，向量上亿选 IVF-PQ 加 GPU；建库后固定标注 query 测 Recall@10 与 p99 延迟再定参数。

**ANN 索引参数与召回吞吐前沿**

| 索引 | 关键参数 | 召回随参数变化 | 内存与延迟代价 |
| --- | --- | --- | --- |
| Flat 精确检索 | 无 | Recall 恒为 1 | O(N·d) 每查询，QPS 最低 |
| HNSW | M / efConstruction / efSearch | efSearch 增大则召回升，M 增大图更连通 | 邻接表约 M·8 字节每向量加原始向量 |
| IVF | nlist / nprobe | nprobe 增大则召回升，漏簇即漏召回 | 码本加倒排表，需先训练 k-means |
| PQ | m 段 / 256 个中心 | 压缩越狠量化误差越大 | 单向量压到 m 字节，可省十倍以上 |


### embedding 版本漂移后旧索引召回塌方

某知识库把 embedding 从 v1 升到 v2，只换推理端点、没重建索引。上线一周「答非所问」涨六倍，但 Top-5 相似度仍普遍在 0.8 以上：v2 做了不同归一化，与旧索引 v1 向量的 cos 分布被压得很窄且集中，名次由噪声决定，只告警「分数低于 0.5」的监控完全没触发。

根因是 embedding 版本属于索引，换模型必须全量重建。下面用纯标准库模拟同版本检索与新旧混查，量化 Recall@5 的塌方。

```python
import math, random

def cos(a, b):
    return sum(x*y for x,y in zip(a,b)) / math.sqrt(sum(x*x for x in a)*sum(y*y for y in b))

def unit(rng, d, s=0.0):
    v = [rng.gauss(0,1)+s for _ in range(d)]
    n = math.sqrt(sum(x*x for x in v))
    return [x/n for x in v]

def recall(same, trials=100, seed=3):
    rng = random.Random(seed)
    hit = 0
    for _ in range(trials):
        docs = [unit(rng, 32) for _ in range(20)]
        q = [x+0.05*rng.gauss(0,1) for x in docs[0]] if same else unit(rng, 32, 3.0)
        hit += 0 in sorted(range(20), key=lambda i: -cos(q, docs[i]))[:5]
    return round(hit/trials, 3)

print('same_version_recall@5', recall(True))
print('mixed_version_recall@5', recall(False))
```

<Quiz no='104-1' q='把 embedding 服务从 v1 升到 v2 后只换推理端点、不重建索引，最可能发生什么？' :options='["新旧向量不在同一坐标系，cos 分布被压缩且集中，Top-K 名次由噪声决定，Recall@K 塌方而相似度分数可能仍不低", "检索会按向量维度自动对齐，召回保持不变", "只会让查询延迟变高，召回完全不受影响", "只要相似度阈值告警没触发，就说明切换没有问题"]' answer="0" explain='embedding 版本是索引的一部分，换模型必须全量重建。漂移后分数不一定下降，仅靠分数阈值监控会漏报，必须在标注集上测 Recall@K 并做新旧索引双读对比。' />


## 索引重建期的双读灰度与回滚判据

<Exercise title='进阶：给版本切换写一份双读灰度判据' task='实现 gate：新版 Recall@5 不得低于旧版减 0.01，且 p99 延迟不得超过旧版 1.2 倍，两个条件同时成立才放量；用三组模拟分数验证。' solution='def gate(old_recall, new_recall, old_p99, new_p99):\n    recall_ok = new_recall &gt;= old_recall - 0.01\n    latency_ok = new_p99 &lt;= old_p99 * 1.2\n    return recall_ok and latency_ok, recall_ok, latency_ok\n\ncases = [(0.91, 0.90, 40, 45), (0.91, 0.83, 40, 45), (0.91, 0.90, 40, 60)]\nfor old_r, new_r, old_p, new_p in cases:\n    print(&#39;pair&#39;, old_r, new_r, &#39;gate&#39;, gate(old_r, new_r, old_p, new_p))' explain='放量判据必须同时约束召回与延迟，且用标注集上的 Recall@K 而非相似度分数；任一不达标就回滚到旧索引继续双读，灰度期间新旧两路结果都记日志便于归因。' />

<Term word='距离集中' text='高维随机向量的距离相对标准差按 sqrt(2/d) 收缩，max/min 比值趋近 1，Top-K 排序失去判别力；单位向量下 L2、内积、余弦互为单调变换，换距离度量无法解决。' />


## 练习、自测与速记

<Exercise title='基础：给检索加元数据过滤与去重' task='在最小 RAG 的 retrieve 里加入 doc_id 前缀过滤（只查指定型号）与内容指纹去重，构造包含重复页眉的文档验证 Top-K 不再被同一块占满，并打印被过滤掉的数量。' solution='import hashlib\n\ndef retrieve_filtered(docs, query, prefix, k=3):\n    seen, out = set(), []\n    for doc_id, text in docs:\n        if not doc_id.startswith(prefix): continue\n        fp = hashlib.md5(text.encode()).hexdigest()\n        if fp in seen: continue\n        seen.add(fp)\n        out.append((doc_id, text, len(set(query) &amp; set(text))))\n    out.sort(key=lambda r: -r[2])\n    return out[:k]\n\ndocs = [(&#39;A-1&#39;,&#39;页眉&#39;),(&#39;A-2&#39;,&#39;页眉&#39;),(&#39;A-3&#39;,&#39;A100 质保三年&#39;),(&#39;B-1&#39;,&#39;B200 质保一年&#39;)]\nprint(retrieve_filtered(docs, &#39;A100 质保&#39;, &#39;A-&#39;))' explain='过滤把 B 型号排除，指纹去重去掉重复页眉，最终返回 A-3 与一条页眉，相关块不再被挤掉。指纹应按正文规范化后计算。' />

<Exercise title='进阶：为 RAG 写一份可复用的评测脚本' task='给定一个含 10 条问题的标注集（每条写明相关 doc_id 与是否应拒答），实现 Recall@K 与拒答准确率两个指标，并对比「纯关键词」与「关键词+元数据过滤」两种方案。' solution='def recall_at_k(hits, gold, k=3):\n    return len(set(hits[:k]) &amp; set(gold)) / max(1, len(gold))\n\ndef eval_strategy(strategy, cases):\n    r, refuse = [], 0\n    for q, gold, should_refuse in cases:\n        hits = strategy(q)\n        r.append(recall_at_k(hits, gold))\n        refuse += int((not hits) == should_refuse)\n    return round(sum(r)/len(r), 3), round(refuse/len(cases), 3)\n\ncases = [(&#39;A100 质保&#39;, [&#39;A-3&#39;], False), (&#39;未知型号&#39;, [], True)]\nprint(eval_strategy(lambda q: [&#39;A-3&#39;] if &#39;A100&#39; in q else [], cases))' explain='Recall@K 衡量相关块是否进入候选，拒答准确率衡量无依据时是否老实说不知道；两者要一起看，只优化前者会让系统变得爱编造。' />

<Quiz no='104-2' q='检索结果里重复页眉挤占 Top-K，最直接的修复是？' :options='["按内容指纹去重并做元数据过滤，再重排", "把 Top-K 从 5 改成 20", "换更大的生成模型", "提高 temperature"]' answer="0" explain='重复模板的向量几乎相同，增加 K 只会放进更多重复内容；去重与元数据过滤才是针对根因的修复，生成模型无法弥补召回缺陷。' />

<Quiz no='104-3' q='关于「lost in the middle」，准确的说法是？' :options='["关键信息放在长上下文中段时，被引用概率下降，应把最优块放首尾", "模型只能读前 512 Token", "上下文越长准确率必然线性上升", "把 temperature 调低即可消除"]' answer="0" explain='这是长上下文利用的经验现象，与位置有关；工程上通过重排后调整块顺序、控制总长度与预算来缓解，不是解码参数问题。' />

<Quiz no='104-4' q='Agent 工具调用里，重试策略最稳妥的是？' :options='["只对幂等操作重试，并带指数退避、超时与累计预算上限", "所有失败都立即重试三次", "由模型自行决定重试次数", "不设超时，交给网关兜底"]' answer="0" explain='非幂等写操作重试会造成重复扣款；模型自决会失控；没有超时会让连接堆积。步数、预算、超时、幂等键四者缺一不可。' />

<Predict no='104-5' q='retrieve(&#39;A100 质保&#39;, k=3, budget=40) 最可能返回几块？' :options='["2 块，第三块因预算不足被丢弃", "3 块，k 优先于预算", "0 块，预算小于所有文档"]' answer='0' output='2 块（used 40，[&#39;A-1&#39;, &#39;A-2&#39;]）' explain='k 是候选上限，budget 是硬预算；循环里先判断 used + tokens(text) &gt; budget 就 break，因此实际入选项可能少于 k。宁可少给也不能撑爆窗口。' />

<FillBlank no='104-6' tpl='___ collections' :answers='["import"]' hint='回想本讲关于 Prompt 与结构化输出 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 上下文预算与分块：先算账，再往里塞 的落点。' />

<KnowledgeCard :points='["上下文窗口是硬预算：系统提示 + 检索片段 + 历史 + 问题 + 预留输出，先算账再往里塞", "分块按文档结构切，200-500 Token 加 10-15% 重叠，写 `section` / `page` / `doc_id` 元数据，主动去重页眉目录", "检索有独立口径：`Recall@K`、MRR、引用命中率；混合检索用 BM25 + 向量 + RRF，再重排", "lost in the middle：最相关的块放首尾；评估集要含无答案、跨块综合、含否定词的问题", "Agent 四道闸：步数上限、总预算上限、`timeout` 与退避、幂等键；每轮记 Token / 耗时 / `trace_id`", "降级要显式：检索无结果答「资料中未找到」，超时返已生成部分；失败分支都可观测"]' :pitfalls='["按固定字数切块，表格与条款被拦腰截断", "把 Top-K 结果直接拼进 prompt 不做去重", "工具调用无步数与预算上限", "把检索到的片段无脑塞进上下文、或让 Agent 无上限循环调用工具，会同时推高成本与失控概率"]' summary='大模型应用的工程质量主要在模型之外：检索质量、上下文预算、工具幂等、失败降级与可观测性，而不是提示词措辞' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 上下文窗口是硬预算：系统提示 + 检索片段 + 历史 + 问题 + 预留输出，先算账再往里塞 | 建立直觉 |
| 分块按文档结构切，200-500 Token 加 10-15% 重叠，写 `section` / `page` / `doc_id` 元数据，主动去重页眉目录 | 跑通示例 |
| 检索有独立口径：`Recall@K`、MRR、引用命中率；混合检索用 BM25 + 向量 + RRF，再重排 | 深入边界 |
| lost in the middle：最相关的块放首尾；评估集要含无答案、跨块综合、含否定词的问题 | 工程落地 |
| Agent 四道闸：步数上限、总预算上限、`timeout` 与退避、幂等键；每轮记 Token / 耗时 / `trace_id` | 随堂检测 |
| 降级要显式：检索无结果答「资料中未找到」，超时返已生成部分；失败分支都可观测 | 复盘 |

1. 上下文窗口是硬预算：系统提示 + 检索片段 + 历史 + 问题 + 预留输出，先算账再往里塞

2. 分块按文档结构切，200-500 Token 加 10-15% 重叠，写 `section` / `page` / `doc_id` 元数据，主动去重页眉目录

3. 检索有独立口径：`Recall@K`、MRR、引用命中率；混合检索用 BM25 + 向量 + RRF，再重排

[下一讲：CAP / BASE 与一致性模型](/distributed/cap-base)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/104-llm-engineering.py`

```bash
python3 examples/lessons/104-llm-engineering.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/104-llm-engineering.py) · [全部示例代码索引](/examples/)
