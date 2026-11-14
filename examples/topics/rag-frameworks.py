"""RAG 框架与大模型 API 实战 —— 专题补遗示例

课程页：/topics/rag-frameworks
GitHub：https://github.com/lfire/python/blob/main/examples/topics/rag-frameworks.py

依赖安装（可选，仅真实框架 / API 片段需要；纯标准库等价演示无需安装）：
    pip install llama-index llama-index-embeddings-huggingface pypdf openai httpx python-dotenv

运行：
    python3 examples/topics/rag-frameworks.py

说明：依赖 llama_index / openai / httpx / dotenv / pypdf 的片段都用 try/except ImportError
包成可选段，未安装时打印跳过提示；涉及 API Key 一律用占位符，绝不读取真实环境变量或密钥，
绝不发起真实 API 请求、不下载 embedding 模型、不访问外网。纯标准库等价演示（词频检索、
BM25/RRF、假 SSE 流解析、溯源拒答、成本守门、工具降级、评测等）在纯净环境里直接跑出结果。
"""

# == 段 1 == 对应节：Embedding 与向量库：把文本变成可检索的稠密向量
# 演示（纯标准库）：按字符窗口切块、用词频字典冒充 embedding、余弦相似度取 top-k。
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


# == 段 2 == 对应节：LlamaIndex：VectorStoreIndex 与检索器
# 演示（可选，需 llama-index 等）：SimpleDirectoryReader / SentenceSplitter /
# VectorStoreIndex / as_retriever 这条链，以及 Settings.embed_model 的配置位置。
# 安全说明：源文会 load_dotenv 读真实密钥、实例化 HuggingFaceEmbedding 下载模型、读取
# ./reports 目录并建索引检索；本可选段只确认组件可用，绝不下载模型、不读密钥、不发请求。
try:
    import os
    from dotenv import load_dotenv
    from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding
except ImportError:
    print("跳过：需要 pip install llama-index llama-index-embeddings-huggingface pypdf python-dotenv")
else:
    names = [VectorStoreIndex.__name__, SimpleDirectoryReader.__name__,
             SentenceSplitter.__name__, Settings.__name__, HuggingFaceEmbedding.__name__]
    print("LlamaIndex 组件就绪:", names)
    print("(本段不下载 embedding 模型、不建索引、不发起检索)")


# == 段 3 == 对应节：混合检索与重排：RRF 融合与二次打分
# 演示（纯标准库）：BM25 关键词检索 + RRF 倒数排名融合 + 词面重合度重排。
# RRF 公式：score = sum(1 / (k + rank))，k 常取 60，融合两路名次不要求分数可比。
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


# == 段 4 == 对应节：兼容 OpenAI 协议的 API：DeepSeek 调用与流式 iter_lines
# 演示（可选，需 openai/httpx/dotenv）：换 base_url 复用 OpenAI SDK、请求体置 stream、
# httpx.stream + iter_lines 逐行解析 SSE。
# 安全说明：API Key 一律用占位符，不调用 load_dotenv、不读真实环境变量；只构造客户端并
# 保留 stream_answer 的定义，绝不调用 create / stream 发起真实请求。
try:
    import json
    import os
    import httpx
    from dotenv import load_dotenv
    from openai import OpenAI
except ImportError:
    print("跳过：需要 pip install openai httpx python-dotenv")
else:
    API_KEY = "YOUR_DEEPSEEK_API_KEY"          # 占位符，绝不读取真实密钥
    BASE_URL = "https://api.deepseek.com".rstrip("/")
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    print("OpenAI 兼容客户端已用占位 key 构造(未发起请求):", type(client).__name__)

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

    print("stream_answer 已定义(本段不调用，避免真实 API 请求)")


# == 段 5 == 对应节：没有密钥时怎么先跑通解析逻辑
# 演示（纯标准库）：造一段假的 SSE 字节流，逐行跳过空行与非 data 行、遇 [DONE] 收尾。
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


# == 段 6 == 对应节：Prompt 模板、结构化输出与溯源拒答
# 演示（纯标准库）：渲染含来源编号的模板、无命中或低分固定拒答、解析 JSON 后校验引用编号。
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


# == 段 7 == 对应节：Token 成本核算与预算守门
# 演示（纯标准库）：启发式 Token 估算、按输入/输出单价计费、超预算降级或拒绝。
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


# == 段 8 == 对应节：Agent 工具调用与失败降级
# 演示（纯标准库）：工具注册表 + 调度器，失败先降级到备用工具、仍失败带说明返回，限制步数防死循环。
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


# == 段 9 == 对应节：评测：Recall@K、忠实度与拒答正确率
# 演示（纯标准库）：Recall@K 命中比例、用答案字符在上下文里的覆盖率近似忠实度。
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


# == 段 10 == 对应节：练习 1 · 用纯标准库实现 RRF 融合
# 演示（纯标准库）：k=60 的倒数排名融合，输出得分最高的两个文档编号。
def rrf(rank_lists, k=60, top_k=2):
    score = {}
    for ranks in rank_lists:
        for r, doc_id in enumerate(ranks, 1):
            score[doc_id] = score.get(doc_id, 0.0) + 1.0 / (k + r)
    return sorted(score, key=score.get, reverse=True)[:top_k]

print("top2 by rrf:", rrf([[2, 0, 1, 3], [0, 2, 3, 1]], k=60, top_k=2))


# == 段 11 == 对应节：练习 2 · 给流式解析补上异常兜底
# 演示（纯标准库）：跳过坏 JSON 的 data 行、忽略空行与非 data 行、遇 [DONE] 停止并拼接文本。
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
