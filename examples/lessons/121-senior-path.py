"""
第 121 讲 · 资深能力图谱、技术选型与持续精进
与教程正文一一对应的示例代码

课程页面：/advanced/senior-path
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/121-senior-path.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/121-senior-path.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# es eligible True score 3.4
# clickhouse eligible True score 4.05
# sqlite eligible False score 3.05
# winner clickhouse

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# base ['clickhouse', 'es', 'sqlite']
# ops-heavy ['sqlite', 'clickhouse', 'es']

O = {'es': (4, 3, 2, 5, 3), 'clickhouse': (5, 5, 3, 2, 4), 'sqlite': (1, 2, 5, 5, 5)}

def rank(weights):
    def sc(v):
        return round(sum(w * x for w, x in zip(weights, v)) / sum(weights), 3)
    return sorted(O, key=lambda k: -sc(O[k]))

print('base', rank([0.30, 0.25, 0.20, 0.15, 0.10]))
print('ops-heavy', rank([0.10, 0.10, 0.60, 0.10, 0.10]))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# obj kind POSITIONAL_OR_KEYWORD
# keyword-only params ['skipkeys', 'ensure_ascii', 'check_circular', 'allow_nan', 'cls', 'indent', 'separators', 'default', 'sort_keys']
# param count 11

import inspect, json

sig = inspect.signature(json.dumps)
kw = [p.name for p in sig.parameters.values() if p.kind is p.KEYWORD_ONLY]
print('obj kind', sig.parameters['obj'].kind.name)
print('keyword-only params', kw)
print('param count', len(sig.parameters))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

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
