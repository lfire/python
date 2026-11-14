---
title: RAG 框架与大模型 API 实战
description: 从 PDF 解析与分块、Embedding 与向量库、LlamaIndex 检索器，到混合检索重排、兼容 OpenAI 协议的流式 API、Token 成本、溯源拒答、Agent 降级与评测的工程落地清单。
---

# RAG 框架与大模型 API 实战

第 104 讲用标准库把 RAG 的核心机制跑通了：分块、向量化、按相似度取回片段、拼进提示词。那套代码把原理讲透，但每一样都是玩具实现，PDF 靠手写解析、没有真正的向量库、相似度临时算、回答是本地拼的字符串，既连不上大模型，也算不清一次调用花多少钱。真做财报问答或知识库助手，会立刻撞上一排工程问题：扫描版 PDF 怎么切成不丢表格的块、换 embedding 模型后旧索引为什么全废、DeepSeek 这类兼容 OpenAI 协议的接口怎么流式输出、几千页资料的 Token 开销怎么压进预算、答案引用怎么保证不张冠李戴。这一篇按检索增强生成的落地动线补上：先讲解析与分块，再落向量库与 LlamaIndex 检索器，接着做混合检索与重排、流式 API、Prompt 与结构化输出，然后处理成本核算、溯源拒答、Agent 降级与评测，最后讲密钥隔离。每个依赖框架或密钥的示例都配一段纯标准库的最小等价演示，没装库、没密钥也能先把机制跑通。

真实框架示例统一依赖下面这条安装命令，CPU 环境即可；`llama-index-embeddings-huggingface` 会附带拉取 `torch`：

```bash
pip install llama-index llama-index-embeddings-huggingface pypdf openai httpx python-dotenv
```

## PDF 解析与分块策略：块大小、重叠与元数据

解析是 RAG 的第一道关。`pypdf` 能取文本层，但扫描件没有文本层，要先过 OCR；财报里的合并表格按纯文本读会行列错位，需要专门的表格抽取并转成「行：科目、列：年度」的结构化字符串。分块决定后续能召回什么：块太大，一次塞进提示词噪声多、还容易顶到 Token 上限；块太小，一句话被拦腰截断，语义不完整，相似度也失真。常见的折中是每块三百到八百字，相邻块留五十到一百字重叠，让跨边界的信息至少完整落进某一块。切块时要顺手写入元数据：`doc_id`、`page`、`chunk_id`、标题层级，后面溯源、按章节过滤、去重都靠它们。

| 分块策略 | 切分依据 | 块大小 / 重叠 | 适用 | 主要缺点 |
| --- | --- | --- | --- | --- |
| 固定长度 | 字符窗口 | 512 字 / 64 字 | 通用文本、日志 | 容易把句子或表格切断 |
| 递归字符 | 段落、句子、字符逐级回退 | 512 字 / 64 字 | 大多数文档 | 对版式复杂的 PDF 仍会错位 |
| 按标题层级 | 章节与小节边界 | 不固定 | 财报、论文、手册 | 长章节仍需二次切分 |
| 语义分块 | 相邻句嵌入相似度谷点 | 不固定 | 问答型知识库 | 需额外模型调用、成本高 |

## Embedding 与向量库：把文本变成可检索的稠密向量

Embedding 模型把一段文本映射成固定维度的向量，例如七百六十八或一千五百三十六维，语义相近的文本在向量空间里距离也近，检索时用余弦相似度或点积排序。向量库（FAISS、Chroma、Milvus、`pgvector`）为这些向量建近似最近邻索引，做到百万级数据毫秒召回，并支持按元数据先过滤再检索。有一条硬约束：索引的维度由 embedding 模型决定，换模型或换维度后旧索引全部作废，必须清空集合重新写入，最好把模型名与维度记进集合元信息，启动时先校验再服务。

下面这段纯标准库演示用字符词频字典冒充 embedding、用余弦相似度排序，把「切块、向量化、取 top-k」三件事跑通，不需要任何库，也不需要密钥。

```python
import math

def chunk_text(text, size=24, overlap=6):
    """按字符窗口切块，overlap 保留边界上下文，纯标准库演示。"""
    chunks, start = [], 0
    while start < len(text):
        chunks.append({"chunk_id": len(chunks), "text": text[start:start + size]})
        start += size - overlap
    return chunks

def bow_vector(text):
    """用字符词频模拟 embedding：真实系统用模型输出稠密向量。"""
    vec = {}
    for ch in text.lower():
        if ch.isalnum():               # isalnum 对中文字符同样为真
            vec[ch] = vec.get(ch, 0) + 1
    return vec

def cosine(a, b):
    dot = sum(a[t] * b[t] for t in set(a) & set(b))
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0

def retrieve(query, chunks, top_k=2):
    q = bow_vector(query)
    scored = [(c["chunk_id"], cosine(q, bow_vector(c["text"]))) for c in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(cid, round(s, 3)) for cid, s in scored[:top_k]]

doc = "RAG 先检索文档片段再让大模型作答，分块要保留边界重叠，检索按向量相似度排序。"
chunks = chunk_text(doc)
print("chunk count:", len(chunks))
print("top hits:", retrieve("向量相似度 分块", chunks))
```

## LlamaIndex：`VectorStoreIndex` 与检索器

LlamaIndex 把「解析、切块、向量化、入库、检索」封成一条链。`SimpleDirectoryReader` 读目录下 PDF，`SentenceSplitter` 按句切块并带重叠，`VectorStoreIndex` 建索引，`.as_retriever(similarity_top_k=...)` 得到检索器，`.retrieve()` 返回带分数的节点。要注意兼容协议的边界：DeepSeek 提供的是兼容 OpenAI 的聊天接口，并不提供 embedding 服务，所以向量化得另配模型，下面用本地 `HuggingFaceEmbedding` 演示，这样连密钥都不需要。若要长期复用，用 `StorageContext` 把索引持久化到磁盘，别每次重启都重新嵌入一遍。

```python
# 依赖开头 bash 块安装的 llama-index / llama-index-embeddings-huggingface / pypdf / python-dotenv
import os
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

load_dotenv()
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-zh-v1.5")

docs = SimpleDirectoryReader("./reports", required_exts=[".pdf"]).load_data()
nodes = SentenceSplitter(chunk_size=512, chunk_overlap=64).get_nodes_from_documents(docs)
index = VectorStoreIndex(nodes)
retriever = index.as_retriever(similarity_top_k=4)
hits = retriever.retrieve("公司第四季度营收同比变化是多少？")
for h in hits:
    print(h.node.node_id, round(h.score or 0.0, 3), h.node.metadata.get("page_label"))
```

<Callout type='warn' title='换 embedding 模型要重建索引' text='向量库的维度由 embedding 模型决定，换模型或换维度后旧索引无法复用，必须清空集合重新写入，并在集合元数据里记录模型名与维度，服务启动时先校验再对外提供检索。' />

## 混合检索与重排：RRF 融合与二次打分

只用向量检索会漏掉专有名词、编号、罕见缩写：问「合同编号 HT-2024-088 的违约金」，语义相近但编号对不上的块照样排前面。补一路 BM25 关键词检索就能按字面精确命中。两路结果分数口径不同，不能直接相加，常用倒数排名融合 RRF：对每个文档，把它在各路结果里的名次取倒数后求和，公式是 `score = sum(1 / (k + rank))`，`k` 常取六十，名次靠前的文档自然被推上来。融合后取前二十到五十个候选，再用 cross-encoder 或让模型逐条打分做重排，把最相关的三到五块留给提示词，这一步通常比调大 `top_k` 更有效。

| 检索策略 | 召回强项 | 精度 | 额外延迟 | 适用 |
| --- | --- | --- | --- | --- |
| 向量检索 | 同义、 paraphrase、语义相近 | 中 | 低 | 开放式提问 |
| BM25 关键词 | 编号、专有名词、精确短语 | 高 | 低 | 条款、型号、代码报错 |
| 混合 + RRF | 兼顾语义与字面 | 较高 | 中 | 通用知识库默认选择 |
| 混合 + 重排 | 长文档里定位关键段 | 最高 | 较高 | 财报、法规、病历 |

下面用纯标准库把 BM25、RRF 与重排串起来，能看到融合前后名次怎么变。

```python
import math

def bm25_scores(query, docs, k1=1.5, b=0.75):
    """极简 BM25：纯标准库演示关键词检索这一路。"""
    q, n = set(query), len(docs)
    avg = sum(len(d) for d in docs) / n
    out = []
    for i, d in enumerate(docs):
        tf = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for t in q:
            if t not in tf:
                continue
            df = sum(1 for other in docs if t in other)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            s += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(d) / avg))
        out.append((i, s))
    return out

def rrf_fuse(rank_lists, k=60, top_k=3):
    """倒数排名融合：合并多路名次，不要求分数可比。"""
    fused = {}
    for ranks in rank_lists:
        for r, doc_id in enumerate(ranks, 1):
            fused[doc_id] = fused.get(doc_id, 0.0) + 1.0 / (k + r)
    return sorted(fused, key=fused.get, reverse=True)[:top_k]

def rerank(query, cand_ids, docs):
    """重排：用查询与候选块的词面重合度二次打分。"""
    q = set(query)
    scored = [(i, len(q & set(docs[i]))) for i in cand_ids]
    return [i for i, _ in sorted(scored, key=lambda x: x[1], reverse=True)]

docs = [
    list("营收同比增长百分之八，第四季度财报"),
    list("员工培训计划与差旅报销规定"),
    list("第四季度营收十二点三亿元，同比增八"),
    list("研发费用资本化会计政策"),
]
query = set("第四季度营收")
vec_rank = [2, 0, 1, 3]
kw_rank = [i for i, _ in sorted(bm25_scores(query, docs), key=lambda x: x[1], reverse=True)]
fused = rrf_fuse([vec_rank, kw_rank], top_k=3)
print("bm25 rank:", kw_rank)
print("rrf fused:", fused, "-> rerank:", rerank(query, fused, docs))
```

## 兼容 OpenAI 协议的 API：DeepSeek 调用与流式 `iter_lines`

DeepSeek 及一批国产模型都实现了 OpenAI 协议，意味着 `openai` SDK 只要换掉 `base_url` 与 `api_key` 就能复用，不必为每个平台学一套新接口。非流式调用直接取 `choices[0].message.content`；流式调用在请求体里置 `stream` 为真，服务端以 SSE 逐事件返回，每行形如 `data: {...}`，最后以 `data: [DONE]` 收尾。用 `httpx.stream` 拿到响应后 `iter_lines()` 逐行读取，跳过空行与非 `data:` 行，解析出 `delta` 里的增量文字边收边显示，首字延迟比等整段生成低得多。

```python
# 依赖开头 bash 块安装的 openai / httpx / python-dotenv
import json
import os
import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")

# 方式一：OpenAI SDK 走兼容协议，非流式一句话调用
client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
quick = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "用一句话解释 RAG"}],
    temperature=0.0,
)
print("sdk:", quick.choices[0].message.content)

# 方式二：直接发流式请求，用 iter_lines 逐行读 SSE；具体路径以平台文档为准
def stream_answer(question, context):
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "只依据资料作答，资料不足就回答无法回答。"},
            {"role": "user", "content": f"资料：{context}\n问题：{question}"},
        ],
        "stream": True, "temperature": 0.0, "max_tokens": 512,
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    parts = []
    with httpx.stream("POST", BASE_URL + "/chat/completions",
                      json=body, headers=headers, timeout=30.0) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines():
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line or not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                break
            parts.append(json.loads(payload)["choices"][0]["delta"].get("content", ""))
            print(parts[-1], end="", flush=True)
    return "".join(parts)

text = stream_answer("第四季度营收是多少？", "财报摘要：第四季度营收 12.3 亿元，同比增长 8%。")
```

### 没有密钥时怎么先跑通解析逻辑

`iter_lines` 的价值不在于网络，而在于「逐行、跳过空行、按前缀取 payload、遇结束标记收尾」这套解析纪律。下面用纯标准库造一段假的 SSE 字节流，把同样的解析函数跑一遍，不需要 `httpx`、不需要网络、不需要密钥。

```python
import json

def fake_stream(events):
    """模拟服务端 SSE：无网络、无密钥也能看懂逐行解析。"""
    for ev in events:
        yield b"data: " + json.dumps(ev, ensure_ascii=False).encode("utf-8")
        yield b""                       # 事件之间的空行
    yield b"data: [DONE]"

def parse_stream(raw_lines):
    parts = []
    for raw in raw_lines:
        if not raw:                     # 跳过心跳空行
            continue
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if not line.startswith("data: "):
            continue
        payload = line[len("data: "):].strip()
        if payload == "[DONE]":
            break
        parts.append(json.loads(payload)["delta"])
    return "".join(parts)

events = [
    {"delta": "第四季度"},
    {"delta": "营收 "},
    {"delta": "12.3 亿元。"},
]
print("streamed:", parse_stream(fake_stream(events)))
```

## Prompt 模板、结构化输出与溯源拒答

把 system 指令、检索到的块、用户问题、输出格式固定成模板，能让行为稳定、也方便回归测试。模板别用 `str.format` 去拼来源不可信的资料，因为资料里出现的花括号会被当成占位符；更稳的做法是用 `string.Template` 或先把资料单独转义，再替换。要程序消费答案，就要求模型只输出 JSON，声明 `answer` 与 `citations` 两个字段，解析后校验引用编号必须来自本次真实检索到的块编号，伪造引用直接判为无效。检索为空、最高分低于阈值、或答案引用对不上候选集，都要走固定拒答，而不是让模型凭参数记忆自由发挥。

```python
import json

TEMPLATE = ("你只依据下面的资料回答问题，答案逐句标注来源编号。 "
            "资料： {context} "
            "问题： {question} "
            "只输出 JSON，字段为 answer 与 citations。")

def render_prompt(question, hits):
    lines = [f"[{cid}] {text}" for (cid, text), _ in hits]
    return TEMPLATE.format(context=" / ".join(lines), question=question)

def maybe_refuse(hits, min_score=0.35):
    """无命中或最高分过低，直接给固定拒答，不交给模型发挥。"""
    if not hits or max(s for _, s in hits) < min_score:
        return {"answer": "根据现有资料无法回答", "citations": []}
    return None

def parse_and_check(raw, valid_ids):
    data = json.loads(raw)
    bad = [c for c in data.get("citations", []) if c not in valid_ids]
    if bad:
        return {"answer": "引用无效，已拒答", "citations": [], "bad": bad}
    return data

hits = [((3, "第四季度营收 12.3 亿元"), 0.82), ((7, "全年营收 45 亿元"), 0.61)]
print("prompt:", render_prompt("第四季度营收多少？", hits))
print("no hit:", maybe_refuse([]))
print("checked:", parse_and_check('{"answer": "12.3 亿元", "citations": [3]}', {3, 7}))
print("forged:", parse_and_check('{"answer": "x", "citations": [99]}', {3, 7}))
```

## Token 成本核算与预算守门

费用按输入与输出 Token 分别计价，中文通常一个字约一到两个 Token，英文约四个字符一个 Token，精确计数用 `tiktoken`，无库时可用启发式估算先做量级判断。一次 RAG 请求的输入 = 模板 + 系统指令 + 检索到的若干块 + 问题，输出由 `max_tokens` 封顶；把检索块数从十压到四、对重复问题加缓存、给长答案设上限，是三个最直接的省钱动作。生产里要有一个预算守门：请求前先估算本次花费，累加到当日或当月用量，超阈值就降级（减小 `top_k`、截断上下文、换更便宜的模型）或直接拒绝，并把每次实际消耗记回台账。

| 模型 | 输入单价（每百万 Token） | 输出单价（每百万 Token） | 单次典型成本 | 月度一万次估算 |
| --- | --- | --- | --- | --- |
| `deepseek-chat` | 1.0 元 | 2.0 元 | 约 0.002 元 | 约 20 元 |
| `gpt-4o-mini` | 1.1 元 | 4.4 元 | 约 0.004 元 | 约 40 元 |
| 旗舰推理模型 | 10.0 元 | 30.0 元 | 约 0.03 元 | 约 300 元 |

单价仅用于演示量级，实际以平台当日定价为准。下面这段纯标准库实现估算、计费与超预算降级。

```python
def approx_tokens(text):
    """启发式估算：中文按每字 1 Token，其余约 4 字符 1 Token。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    return cjk + (len(text) - cjk) / 4

PRICE = {"deepseek-chat": (1.0, 2.0), "gpt-4o-mini": (1.1, 4.4)}

def cost(model, prompt, answer):
    pin, pout = PRICE[model]
    return approx_tokens(prompt) / 1e6 * pin + approx_tokens(answer) / 1e6 * pout

class BudgetGuard:
    def __init__(self, daily_limit=5.0):
        self.limit, self.spent = daily_limit, 0.0
    def check(self, model, prompt, max_out=512):
        est = cost(model, prompt, "x" * (max_out * 2))
        if self.spent + est > self.limit:
            return "降级或拒绝"       # 减 top_k、换便宜模型或拒答
        return "放行"
    def record(self, model, prompt, answer):
        self.spent += cost(model, prompt, answer)

prompt = "资料：" + "营收数据。" * 200 + "问题：第四季度营收？"
print("approx tokens:", round(approx_tokens(prompt), 1))
print("single cost:", round(cost("deepseek-chat", prompt, "12.3 亿元"), 6))
print("tiny budget:", BudgetGuard(daily_limit=0.0).check("deepseek-chat", prompt))
```

## Agent 工具调用与失败降级

让大模型不止回答、还能动手，就把检索、计算、查库注册成工具，由模型输出工具名与参数，调度器执行后把结果回填。工具层必须假设一切都会失败：超时、参数不合法、上游报错、返回空结果、模型编造了不存在的工具名。可靠的调度器做三件事：给每个工具登记备用工具，失败先重试一次、再降级到备用、仍失败就带不确定说明返回；限制最大步数防止死循环；所有写操作保证幂等，避免重试造成重复下单。

```python
def tool_search(query):
    return {"chunks": ["第四季度营收 12.3 亿元"]}

def tool_calculator(expr):
    a, b = expr.split("*")
    return {"value": round(float(a) * float(b), 4)}

def tool_unstable(query):
    raise RuntimeError("upstream timeout")

REGISTRY = {
    "search": (tool_search, "search"),
    "calc": (tool_calculator, None),
    "unstable": (tool_unstable, "search"),
}

def dispatch(name, arg, _depth=0):
    """执行工具；失败时按注册表降级，仍失败则返回带说明的结果。"""
    if name not in REGISTRY:
        return {"ok": False, "note": "未知工具"}
    fn, fallback = REGISTRY[name]
    try:
        return {"ok": True, "tool": name, "data": fn(arg)}
    except Exception as exc:
        if fallback and fallback != name and _depth < 1:
            return dispatch(fallback, arg, _depth + 1)
        return {"ok": False, "tool": name, "note": f"失败：{type(exc).__name__}"}

for call in [("search", "第四季度营收"), ("calc", "12.3*1.08"),
             ("unstable", "x"), ("missing", "x")]:
    print(call[0], "->", dispatch(*call))
```

## 评测：Recall@K、忠实度与拒答正确率

没有标注集就谈不上调优。先攒一批「问题到相关块编号」的小样本，再用三个指标看住系统：Recall@K 衡量检索是否把相关块捞进前 K 条，忠实度衡量答案里的断言能否被检索上下文支撑，拒答正确率衡量资料不足时是否老实说不知道。Recall@K 低说明分块或检索策略要改；忠实度低而 Recall@K 高，说明模型没用好资料、提示词或重排要调；拒答正确率低则是阈值与兜底逻辑的问题。忠实度可用另一个模型当裁判打分，离线阶段也能用答案字符在上下文里的覆盖率做快速近似。

| 指标 | 定义 | 低分指向 | 优先修复 |
| --- | --- | --- | --- |
| Recall@K | 前 K 条命中相关块的比例 | 检索没捞到 | 分块、混合检索、重排 |
| 忠实度 | 有上下文支撑的断言占比 | 模型编造 | 结构化输出、引用校验 |
| 拒答正确率 | 应拒答时正确拒答的比例 | 幻觉兜不住 | 相似度阈值、空结果兜底 |
| 首字延迟 | 流式首个 Token 到达时间 | 体验卡顿 | 流式、减小上下文 |

```python
def recall_at_k(retrieved, relevant, k):
    if not relevant:
        return 0.0
    return len(set(retrieved[:k]) & set(relevant)) / len(relevant)

def faithfulness(answer, context):
    """近似忠实度：答案字符能在检索上下文里找到的比例。"""
    ctx = set("".join(context))
    chars = [ch for ch in answer if ch.isalnum()]
    return sum(ch in ctx for ch in chars) / len(chars) if chars else 0.0

gold = {"q1": ["doc3", "doc7"], "q2": ["doc1"]}
runs = {"q1": ["doc3", "doc2", "doc7"], "q2": ["doc5", "doc1"]}
for q, rel in gold.items():
    print(q, "Recall@2:", recall_at_k(runs[q], rel, 2),
          "Recall@3:", recall_at_k(runs[q], rel, 3))
context = ["第四季度营收 12.3 亿元，同比增长 8%"]
print("grounded:", round(faithfulness("第四季度营收 12.3 亿元", context), 2))
print("hallucinated:", round(faithfulness("公司净利润 50 亿元并购对手", context), 2))
```

<Callout type='warn' title='密钥别写进代码或日志' text='把 DEEPSEEK_API_KEY 放进 .env 并用 python-dotenv 读取，同时把 .env 写进 .gitignore；一旦硬编码或打印到日志，密钥会随代码仓库与构建产物一起泄漏，轮换成本远高于提前隔离。' />

## 密钥隔离：`dotenv` 与 `.gitignore`

密钥管理只有一条底线：代码里不出现明文。`python-dotenv` 在项目根放一个 `.env` 文件，按 `key=value` 的格式写一行 `DEEPSEEK_API_KEY=xxx`，等号右侧换成真实值，程序开头 `load_dotenv()` 后统一用 `os.getenv` 读取；`.gitignore` 必须包含 `.env`，并补一份不含真实值的 `.env.example` 供协作者照格式填写。生产环境不走文件，改由容器或 CI 注入环境变量；日志与错误信息里只打印模型名、耗时、Token 数，绝不回显密钥或完整请求头。客户端网页、小程序前端一律不能放密钥，凡是浏览器能拿到的都等于公开，必须由自己的服务端代发请求。

## 常见坑 / 边界

1. **向量库维度不匹配**：换了 embedding 模型但沿用旧集合，写入时报维度错误或检索结果全乱。修复动作：换模型即清空并重建索引，把模型名与维度写进集合元数据，启动时校验不一致就拒绝服务。
2. **Token 超预算**：把整章 PDF 或几十个检索块全塞进提示词，触发截断、报错或账单暴涨。修复动作：只传重排后的前四块，设 `max_tokens` 上限，请求前用预算守门估算，超阈值自动减小 `top_k` 或换便宜模型。
3. **流式解析漏结束标记**：忽略空行、不判 `[DONE]`、把注释行也丢给 `json.loads`，导致解析异常或答案尾部被截断。修复动作：逐行跳过空行与非 `data:` 前缀行，遇结束标记立即收尾，对单条 JSON 解析失败做兜底跳过。
4. **溯源缺失与伪造引用**：块没带 `doc_id` 与页码，或答案直接编造引用编号，用户无法核对。修复动作：切块时写元数据、生成时把编号注入模板、解析后校验引用必须落在本次候选集，无效即拒答。
5. **密钥硬编码进仓库**：把 `api_key` 写死在脚本或提交进 `.env`。修复动作：改用 `dotenv` 加环境变量，`.gitignore` 排除 `.env`，并提供脱敏的 `.env.example`；已泄漏的立即轮换。

## 练习

::: details 练习 1 · 用纯标准库实现 RRF 融合
向量检索给出名次 `[2, 0, 1, 3]`，关键词检索给出名次 `[0, 2, 3, 1]`，用 `k=60` 的 RRF 融合两路结果，输出得分最高的两个文档编号。不装任何库。

```python
# 参考解
def rrf(rank_lists, k=60, top_k=2):
    score = {}
    for ranks in rank_lists:
        for r, doc_id in enumerate(ranks, 1):
            score[doc_id] = score.get(doc_id, 0.0) + 1.0 / (k + r)
    return sorted(score, key=score.get, reverse=True)[:top_k]

print("top2 by rrf:", rrf([[2, 0, 1, 3], [0, 2, 3, 1]], k=60, top_k=2))
```
:::

::: details 练习 2 · 给流式解析补上异常兜底
基于前面的 SSE 解析函数，要求跳过无法解析的 `data:` 行、忽略空行、遇 `[DONE]` 停止，并给出最终拼接文本。用一段可运行代码验证，输入里故意混入一行坏 JSON。

```python
# 参考解
import json

def parse_stream(lines):
    parts = []
    for raw in lines:
        line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        if not line or not line.startswith("data: "):
            continue
        payload = line[len("data: "):].strip()
        if payload == "[DONE]":
            break
        try:
            parts.append(json.loads(payload)["delta"])
        except (json.JSONDecodeError, KeyError):
            continue          # 坏行兜底跳过
    return "".join(parts)

def sse(delta):
    return b"data: " + json.dumps({"delta": delta}, ensure_ascii=False).encode("utf-8")

lines = [
    sse("营收 "),
    b"",                       # 空行
    b"data: {broken json",     # 坏 JSON
    b": heartbeat",            # 非 data 行
    sse("12.3 亿元"),
    b"data: [DONE]",
]
print("result:", parse_stream(lines))
```
:::

回到 [专题补遗](/topics/) · [课程总目录](/guide/curriculum)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能跑通本专题按正文顺序整理的标准库示例；需要第三方库的片段会自动跳过并打印安装提示，不装任何库也能看到核心结果。" />

**本专题示例代码** · 仓内路径 `examples/topics/rag-frameworks.py`

```bash
python3 examples/topics/rag-frameworks.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/topics/rag-frameworks.py) · [全部示例代码索引](/examples/)
