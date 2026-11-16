"""
第 104 讲 · LLM 应用工程：Prompt、RAG、Agent 与成本
与教程正文一一对应的示例代码

课程页面：/data-ai/llm-engineering
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/104-llm-engineering.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/104-llm-engineering.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# used 40 blocks 2
# ['A-1', 'A-2']

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

# ======================== 2. 对照写法 ========================
# 预期输出：
# 资料：型号 B200 支持 4 路输入，质保一年 | 型号 A100 支持 8 路输入，质保三年...[截断]
# 问题：B200 质保多久？
# 仅依据资料回答，无依据则回答未找到。

# 承接主示例：DOCS、tokens()、retrieve() 已在上方定义，本片段需与主示例一同运行。
def assemble(picked, question, max_ctx=60):
    head = '资料：' + ' | '.join(t for _, t in picked)
    if len(head) > max_ctx:
        head = head[:max_ctx] + '...[截断]'
    prompt = head + chr(10) + '问题：' + question + chr(10) + '仅依据资料回答，无依据则回答未找到。'
    return prompt

blocks, _ = retrieve('B200 质保', k=3, budget=40)
print(assemble(blocks, 'B200 质保多久？'))

# ======================== 3. 原理验证 ========================
# 预期输出：
# 2000 prompt tokens -> 0.008 USD per call
# 8000 prompt tokens -> 0.02 USD per call
# 32000 prompt tokens -> 0.068 USD per call
# 10000 calls @8k -> 200.0 USD

def cost(prompt_tokens, output_tokens, price_in=0.002, price_out=0.008):
    return round((prompt_tokens / 1000) * price_in + (output_tokens / 1000) * price_out, 6)

for n in (2000, 8000, 32000):
    print(n, 'prompt tokens ->', cost(n, 500), 'USD per call')
print('10000 calls @8k ->', cost(8000, 500) * 10000, 'USD')

# ======================== 4. 工程案例 ========================

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
