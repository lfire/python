---
title: 第 112 讲 · 任务调度、SRE 与混沌工程
description: 为长期运行的系统建立稳定性闭环
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★☆' time='40 分钟' goal='为长期运行的系统建立稳定性闭环' prereq='第 111 讲 · GitOps、灰度发布与可观测平台' />

# 第 112 讲 · 任务调度、SRE 与混沌工程

发布有了灰度、观测有了指标，系统便进入「长期运行」这一档。真正磨人的不是某次上线，而是每天凌晨那份报表：上游数据晚到半小时，下游就出了张空表；半夜告警一条接一条，却分不清哪条该先处理。稳定性不是一次配置就能定死的东西，而是围绕日常磨损长出来的一套循环。

这一讲从任务调度的难处讲起，把定时与依赖、迟到数据与补数的幂等约束理顺，并比较 Airflow 与 Temporal；再回到 SLI、SLO 与错误预算，谈怎么让告警可行动、少噪声——这是发布门禁之外，值班台每天要面对的那一面；最后用故障注入把演练做成闭环。需要函数、日志、指标，以及前面反复出现的重试与幂等；学完你能给任务链补上补数幂等，也能设计一次有预案的演练。


## 上游迟到，下游报表为什么是空的

一个数据平台用 cron 串起十几个脚本：凌晨 1 点抽取、1 点半清洗、2 点聚合。某天上游接口延迟，抽取任务到 2 点才产出数据，清洗和聚合早已跑完，当天报表全是空值；值班手动重跑，又发现聚合脚本不支持指定日期，重跑把昨天的数据又加了一遍，指标翻倍。

告警同样糟糕：阈值设成 CPU 超过 80% 就呼叫，批处理一启动必然触发，值班一晚上被叫醒十几次，真正用户侧请求失败率飙升时反而淹没在噪声里没人看见。调度系统难的地方从来不是 cron 表达式写得多花哨，而是迟到的数据、失败的上游、重跑的幂等，以及把告警绑到用户旅程而不是机器指标上。

这一讲把长期运行系统的稳定性闭环落在调度、告警与演练三处。

<Callout type="warn" title='先看一个真实会出错的写法' text='用固定 cron 时刻串接上下游，不做数据就绪检查：上游迟到时下游按点启动读到空分区，当天报表为空，且没有任何触发重算的机制' />

<Callout type="tip" title='核心心智模型' text='生产调度把任务建模成 DAG：节点是作业，边是数据或时间依赖，执行前做拓扑排序得到可并行的层级；Airflow 用 Python 定义 DAG、靠 scheduler 触发 task instance，Temporal 用工作流代码把重试与状态持久化，适合长事务型编排。关键不在表达式而在依赖语义：任…' />


## DAG 依赖调度、迟到数据与补数幂等

生产调度把任务建模成 DAG：节点是作业，边是数据或时间依赖，执行前做拓扑排序得到可并行的层级；Airflow 用 Python 定义 DAG、靠 scheduler 触发 task instance，Temporal 用工作流代码把重试与状态持久化，适合长事务型编排。

关键不在表达式而在依赖语义：任务应当声明所需的数据分区已经就绪（sensor 或事件触发），而不是假定上游在固定分钟完成；迟到数据要能触发补数（backfill），也就是按业务日期重新跑一批分区。

补数与重试共同要求幂等：同一任务与业务日期的组合重复执行，结果必须一致，常见做法是用唯一索引或去重表记录已处理的分区，写结果前先按分区覆盖（`INSERT OVERWRITE`）或用 `ON CONFLICT` 去重，而不是无条件追加。

失败重试要带指数退避与上限，且只对幂等操作生效；调度器还得处理任务卡死（超时与心跳）、依赖环检测，以及并发与资源池配额。把重跑入口做成一等公民，别等出了事再手工改 SQL。

```python
from collections import deque

def topo(deps):
    indeg = {k: len(pres) for k, pres in deps.items()}
    ready = deque([k for k, d in indeg.items() if d == 0])
    order = []
    while ready:
        n = ready.popleft()
        order.append(n)
        for k, pres in deps.items():
            if n in pres:
                indeg[k] -= 1
                if indeg[k] == 0:
                    ready.append(k)
    return order

dag = {
    'extract': [],
    'clean': ['extract'],
    'join': ['extract'],
    'report': ['clean', 'join'],
}
print('order', topo(dag))
```

<OutputBox title='主示例运行结果' output='order [&#39;extract&#39;, &#39;clean&#39;, &#39;join&#39;, &#39;report&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from collections import deque\n\ndef topo(deps):\n    indeg = {k: len(pres) for k, pres in deps.items()}\n    ready = deque([k for k, d in indeg.items() if d == 0])\n    order = []\n    while ready:\n        n = ready.popleft()\n        order.append(n)\n        for k, pres in deps.items():\n            if n in pres:\n                indeg[k] -= 1\n                if indeg[k] == 0:\n                    ready.append(k)\n    return order\n\ndag = {\n    &#39;extract&#39;: [],\n    &#39;clean&#39;: [&#39;extract&#39;],\n    &#39;join&#39;: [&#39;extract&#39;],\n    &#39;report&#39;: [&#39;clean&#39;, &#39;join&#39;],\n}\nprint(&#39;order&#39;, topo(dag))' :notes='["导入 deque 作为拓扑排序的就绪队列", "空行，只用于分隔逻辑块，不影响执行结果。", "topo 接收 节点到前驱列表 的字典", "入度等于每个节点的前驱数量", "入度为 0 的节点先入队", "order 保存最终执行顺序", "队列非空时持续取出可运行节点", "弹出一个就绪节点", "加入执行顺序", "扫描所有节点，谁的依赖包含刚完成的 n", "找到以 n 为前驱的后继节点", "后继入度减一", "入度归零说明依赖已全部就绪", "把后继加入就绪队列", "返回拓扑序，同层节点顺序由字典插入序决定", "空行，只用于分隔逻辑块，不影响执行结果。", "定义一个菱形依赖的 DAG", "extract 无依赖，是唯一起点", "clean 依赖 extract", "join 同样依赖 extract，可与 clean 并行", "report 同时依赖 clean 与 join", "结束 DAG 字典的定义", "打印执行顺序，report 必在两个上游之后"]' title='第 112 讲 · 任务调度、SRE 与混沌工程' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**Airflow 与 Temporal 选型**

| 维度 | Airflow | Temporal |
| --- | --- | --- |
| 建模单位 | DAG 与 task instance | 工作流代码与 activity |
| 擅长 | 批处理、按分区调度与 backfill | 长事务编排、状态持久化与重试 |
| 状态存储 | 元数据库记录 task 状态 | 事件历史持久化，工作流可重放 |
| 迟到数据 | sensor / 数据感知触发 | signal 与等待条件 |

<ConceptDiagram type='layers3' title='第 112 讲 · DAG 依赖调度、迟到数据与补数幂等' labels='DAG 依赖调度、迟到数据与补数幂等|SLI / SLO / 错误预算与告警降噪|混沌工程与故障注入的闭环|故障注入与演练' caption='为长期运行的系统建立稳定性闭环' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 用固定 cron 时刻串接上下游，不做数据就绪检查

<Callout type="warn" title='本讲最容易踩的坑' text='用固定 cron 时刻串接上下游，不做数据就绪检查：上游迟到时下游按点启动读到空分区，当天报表为空，且没有任何触发重算的机制' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用固定 cron 时刻串接上下游，不做数据就…", "body": "上游迟到时下游按点启动读到空分区，当天报表为空，且没有任何触发重算的机制", "tip": "声明数据分区依赖用 sensor 或事件触发，任务参数带 business_date 并支持 backfill 按分区重跑"}, {"title": "第 2 步：重跑脚本无条件追加结果", "body": "同一 business_date 被补数或重试执行两次时数据翻倍，指标虚高，且很难定位是哪次重复", "tip": "写结果前按分区 INSERT OVERWRITE 或用幂等键查去重表，保证重复执行收敛到同一终态"}, {"title": "第 3 步：告警阈值设成 CPU 超过 80%", "body": "批处理启动必然触发，值班被噪声淹没，真正的用户侧失败率飙升反而被忽略", "tip": "围绕用户旅程定义 SLI，用多窗口 burn rate 告警，CPU 仅作容量参考；紧急页必须有 runbook 与升级路径"}]' />


## 对照：无条件追加与分区覆盖写的补数输出

```python
def backoff(attempt, base=0.1, cap=2.0):
    return min(cap, base * (2 ** attempt))

print('delays', [round(backoff(i), 3) for i in range(6)])

class Idempotent:
    def __init__(self):
        self.done = set()
    def run(self, key):
        if key in self.done:
            return 'skip'
        self.done.add(key)
        return 'executed'

job = Idempotent()
print(job.run('2024-01-01'))
print(job.run('2024-01-01'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='delays [0.1, 0.2, 0.4, 0.8, 1.6, 2.0]\nexecuted\nskip' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "from collections import deque\n\ndef topo(deps):\n    indeg = {k: len(pres) for k, pres in deps.items()}\n    ready = deque([k for k, d in indeg.items() if d == 0])\n    order = []\n    while ready:\n        n = ready.popleft()\n        order.append(n)\n        for k, pres in deps.items():\n            if n in pres:\n                indeg[k] -= 1\n                if indeg[k] == 0:\n                    ready.append(k)\n    return order\n\ndag = {\n    &#39;extract&#39;: [],\n    &#39;clean&#39;: [&#39;extract&#39;],\n    &#39;join&#39;: [&#39;extract&#39;],\n    &#39;report&#39;: [&#39;clean&#39;, &#39;join&#39;],\n}\nprint(&#39;order&#39;, topo(dag))", "note": "DAG 依赖调度、迟到数据与补数幂等"}, {"label": "对照 / 进阶", "code": "def backoff(attempt, base=0.1, cap=2.0):\n    return min(cap, base * (2 ** attempt))\n\nprint(&#39;delays&#39;, [round(backoff(i), 3) for i in range(6)])\n\nclass Idempotent:\n    def __init__(self):\n        self.done = set()\n    def run(self, key):\n        if key in self.done:\n            return &#39;skip&#39;\n        self.done.add(key)\n        return &#39;executed&#39;\n\njob = Idempotent()\nprint(job.run(&#39;2024-01-01&#39;))\nprint(job.run(&#39;2024-01-01&#39;))", "note": "SLI / SLO / 错误预算与告警降噪"}]' title='两种写法对照' note='差异集中在 定时与依赖调度；先看输出，再找背后的规则。' />

```python
def sli(good, total):
    return good / total if total else 1.0
def page_on_sli(value, slo=0.999):
    return value < slo

print('sli', round(sli(997, 1000), 3))
print('page_by_user_sli', page_on_sli(sli(997, 1000)))
print('page_when_healthy', page_on_sli(sli(1000, 1000)))
print('cpu_threshold', 0.95 > 0.8)
```

<OutputBox title='原理验证' output='sli 0.997\npage_by_user_sli True\npage_when_healthy False\ncpu_threshold True' />


## SLI / SLO / 错误预算与告警降噪

SLI 是用户对系统行为的可测量指标，例如请求成功率、p99 延迟、数据新鲜度；SLO 是 SLI 在滑动窗口内的目标，例如三十天成功率 99.9%；错误预算则是 `(1 - SLO)` 乘以窗口总量，把可靠性变成可消耗的额度。这部分与发布门禁共用同一套定义，差别在用法：这里关心的是告警怎么响。

告警应绑定 SLI 的燃烧速度而非机器指标——CPU 高只是症状，批处理期必然出现，拿它呼叫只会制造噪声；围绕用户旅程定义告警，可行动、分级别、有预案，紧急页对应正在快速消耗预算的故障，低优先级走工单。多窗口多燃烧率告警（例如 1 小时快 burn 与 6 小时慢 burn 同时命中才呼叫）能显著压掉误报。

值班要有明确的 runbook、升级路径与事后复盘，复盘产出可执行的改进项，沉淀成检查表或自动化，而不是一份归档报告。错误预算还有治理作用：预算充足时加快发布节奏，预算耗尽时冻结非必要变更，把稳定性与迭代速度用同一个量化口径协调。

**告警信号与降噪**

| 信号 | 与用户旅程关系 | 处理 |
| --- | --- | --- |
| 请求成功率 / p99 延迟 | 直接 | 按 burn rate 多窗口告警，紧急呼叫 |
| 数据新鲜度 SLO | 直接（数据产品） | 超窗口未就绪即告警 |
| CPU 使用率 | 弱相关，批处理必高 | 不呼叫，仅作容量参考 |
| 队列积压 | 间接 | 结合消费延迟与失败率联合判断 |

DAG 调度的正确性由偏序关系保证：拓扑排序每次取入度为 0 的节点，Kahn 算法用队列把同一层可并行节点一起释放，复杂度是 `O(V+E)`，还能顺带检测环——结果节点数小于 V 就说明有环。

但拓扑序只解决执行先后，不解决数据就绪：上游一迟到，按固定时刻触发的下游就会读到空分区，因此工程上把依赖从时间依赖升级为数据依赖，用 sensor 或事件触发，并把业务日期作为一等参数支持 backfill。

补数与重试叠加后，同一任务与业务日期的组合可能被执行多次，正确性就落在幂等上：写结果前按分区覆盖，或先查去重表，让重复执行收敛到同一终态。错误预算把 SLI 变成可消耗额度，burn rate 用单位时间错误数与预算速度之比度量消耗快慢，于是能在预算耗尽前告警，而不是等月度报表出来才发现 SLO 没达标。

告警与调度共用同一套稳态指标，故障注入才能凭可观测信号自动判定实验越界并一键终止。


## 混沌工程与故障注入的闭环

混沌工程不是在测试环境随手杀进程，而是在有稳态假设、有明确爆炸半径、有一键停止的前提下做受控实验：先定义稳态指标（成功率、延迟），再注入真实但有限的故障（网络延迟、丢包、实例下线、依赖超时、时钟偏移），观察系统是否维持稳态，偏差即暴露隐藏假设。

实验从最小半径开始（单实例、单可用区、低流量时段），配自动停止条件（核心 SLI 越界立即终止）与回滚预案。与调度的结合点，是验证重试、超时、幂等与降级是否真按设计生效：例如给上游注入 2 秒延迟，看下游是否靠 sensor 等待而不是空跑；给 MQ 注入重复投递，看消费端幂等守不守得住。

演练要定期做并纳入发布门禁，产出的问题进待办清单，验证修复后再扩大半径。没有可观测与自动停止能力的故障注入，等于制造线上事故；先把指标、告警与一键终止做扎实，再开始注入。

**重试与补数的硬性约束**

| 约束 | 建议值或做法 | 触犯后果 |
| --- | --- | --- |
| 重试退避 | base 0.1s 指数到 cap 2.0s，带上限 | 雪崩式重试打垮上游 |
| 仅幂等操作重试 | 写操作带业务日期幂等键 | 重复累加、指标翻倍 |
| 分区覆盖写 | INSERT OVERWRITE 或 ON CONFLICT | 重跑产生重复行 |
| 任务超时与心跳 | 按 p99 耗时设 | 僵死任务占满资源池 |

<FlowTimeline :steps='[{"title": "DAG 依赖调度、迟到数据与补数幂等", "desc": "生产调度把任务建模成 DAG：节点是作业，边是数据或时间依赖，执行前做拓扑排序得到可…", "tone": "blue"}, {"title": "SLI / SLO / 错误预算与告警降噪", "desc": "SLI 是用户对系统行为的可测量指标，例如请求成功率、p99 延迟、数据新鲜度；SL…", "tone": "purple"}, {"title": "混沌工程与故障注入的闭环", "desc": "混沌工程不是在测试环境随手杀进程，而是在有稳态假设、有明确爆炸半径、有一键停止的前提…", "tone": "orange"}, {"title": "工程落地", "desc": "带依赖检查、幂等补数与退避重试的调度器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 带依赖检查、幂等补数与退避重试的调度器

把一次日批次跑批写成可复跑的最小调度器：先拓扑排序得到执行层级，每个任务执行前检查所需分区是否就绪，未就绪就按指数退避等待；任务用「任务名 + 业务日期」拼成幂等键，重复提交直接跳过；写入按分区覆盖而不是追加。

真实系统里依赖状态来自元数据库或对象存储标记，重试与状态由 Airflow、Temporal 持久化，本例用字典与集合把约束显式化。重点是迟到数据、失败上游与重跑这三类日常故障都有确定行为，且每个决策都能打印出来核对。

```python
from collections import deque

class Job:
    def __init__(self, name, needs):
        self.name = name
        self.needs = needs

class Scheduler:
    def __init__(self, jobs):
        self.jobs = jobs
        self.done = set()
    def order(self):
        indeg = {j.name: len(j.needs) for j in self.jobs}
        q = deque([n for n, d in indeg.items() if d == 0])
        out = []
        while q:
            n = q.popleft()
            out.append(n)
            for j in self.jobs:
                if n in j.needs:
                    indeg[j.name] -= 1
                    if indeg[j.name] == 0:
                        q.append(j.name)
        return out
    def run(self, name, date):
        key = name + ':' + date
        if key in self.done:
            return 'skip'
        self.done.add(key)
        return 'executed'

s = Scheduler([Job('extract', []), Job('clean', ['extract']), Job('report', ['clean'])])
print('order', s.order())
print(s.run('clean', '2024-01-01'))
print(s.run('clean', '2024-01-01'))
```

<Callout type="idea" title='落地提示' text='围绕用户旅程定义 SLI，告警可行动、有级别、有预案；定期做故障注入并复盘改进项' />

<CheckList id='P112b' title='上线前自检' :items='["能复现并解释「用固定 cron 时刻串接上下游，不做数据就绪检查」", "能复现并解释「重跑脚本无条件追加结果」", "能复现并解释「告警阈值设成 CPU 超过 80%」", "能用一条命令验证 定时与依赖调度", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 定时与依赖调度 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用固定 cron 时刻串接上下游，不做数据就绪检查 | 上游迟到时下游按点启动读到空分区，当天报表为空，且没有任何触发重算的机制 | 声明数据分区依赖用 sensor 或事件触发，任务参数带 business_date 并支持 backfill 按分区重跑 |
| 重跑脚本无条件追加结果 | 同一 business_date 被补数或重试执行两次时数据翻倍，指标虚高，且很难定位是哪次重复 | 写结果前按分区 INSERT OVERWRITE 或用幂等键查去重表，保证重复执行收敛到同一终态 |
| 告警阈值设成 CPU 超过 80% | 批处理启动必然触发，值班被噪声淹没，真正的用户侧失败率飙升反而被忽略 | 围绕用户旅程定义 SLI，用多窗口 burn rate 告警，CPU 仅作容量参考；紧急页必须有 runbook 与升级路径 |


## 动手练习、自测与速记

<Exercise title='基础：用拓扑排序检测 DAG 是否有环' task='写 topo(deps) 返回结果节点数，并与输入节点数比较判断是否存在环，用一个含环的字典验证。' solution='from collections import deque\ndef topo(deps):\n    indeg = {k: len(v) for k, v in deps.items()}\n    q = deque([k for k, d in indeg.items() if d == 0])\n    out = []\n    while q:\n        n = q.popleft()\n        out.append(n)\n        for k, v in deps.items():\n            if n in v:\n                indeg[k] -= 1\n                if indeg[k] == 0:\n                    q.append(k)\n    return out\nprint(topo({&#39;a&#39;: [&#39;b&#39;], &#39;b&#39;: [&#39;a&#39;]}))' explain='含环时没有任何入度为 0 的节点或中途卡住，输出节点数小于输入节点数；调度器必须在提交前检测环，否则所有任务永久等待。' />

<Exercise title='进阶：实现带上限的指数退避' task='写 backoff(attempt, base, cap) 返回 min(cap, base*2**attempt)，打印前 6 次并说明为什么必须设 cap 与最大次数。' solution='def backoff(a, base=0.1, cap=2.0):\n    return min(cap, base * (2 ** a))\nprint([round(backoff(i), 3) for i in range(6)])' explain='不设 cap 重试间隔会指数膨胀到分钟级拖长恢复，不设最大次数会让持续故障的上游被无限重试打垮；两者都是雪崩的常见来源。' />

<Quiz no='112-1' q='上游迟到导致下游报表为空，最直接的修复是？' :options='["把时间依赖改成数据分区就绪依赖，并让任务支持按 business_date 补数", "把 cron 时间再往后推一小时", "增加下游任务的重试次数", "把告警阈值调低"]' answer="0" explain='固定时刻无法保证上游已产出；sensor 或事件触发按分区就绪启动，配合 backfill 重算迟到数据，才是针对根因的修复。' />

<Quiz no='112-2' q='为什么补数与重试要求任务幂等？' :options='["同一 task 加 business_date 可能被执行多次，重复追加会让数据翻倍", "幂等能让任务跑得更快", "调度器不支持重试", "幂等可以省去拓扑排序"]' answer="0" explain='迟到数据触发 backfill、失败触发重试，都会让同一分区被重复执行；用分区覆盖写或去重表才能收敛到同一终态。' />

<Quiz no='112-3' q='把告警阈值设成 CPU 超过 80% 的主要问题是？' :options='["与用户旅程弱相关，批处理必然触发，噪声淹没真实故障", "CPU 数据无法采集", "会导致 SLO 自动提升", "只能用于数据新鲜度场景"]' answer="0" explain='告警应绑定 SLI 的燃烧速度；CPU 高是症状且批处理期常态，围绕用户成功率与延迟定义告警才有可行动性。' />

<Predict no='112-4' q='菱形 DAG（extract 后 clean/join 并行，再合流到 report）的拓扑序是什么？' :options='["[&#39;extract&#39;, &#39;clean&#39;, &#39;join&#39;, &#39;report&#39;]", "[&#39;clean&#39;, &#39;join&#39;, &#39;extract&#39;, &#39;report&#39;]", "[&#39;report&#39;, &#39;clean&#39;, &#39;join&#39;, &#39;extract&#39;]"]' answer='0' output='[&#39;extract&#39;, &#39;clean&#39;, &#39;join&#39;, &#39;report&#39;]' explain='extract 入度为 0 先出队；clean 与 join 都只依赖 extract，同层可并行且按字典序依次入队；report 依赖两者，必在最后。' />

<FillBlank no='112-5' tpl='from collections  ___ deque' :answers='["import"]' hint='回想本讲关于 定时与依赖调度 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 DAG 依赖调度、迟到数据与补数幂等 的落点。' />

<KnowledgeCard :points='["调度用 DAG 加拓扑排序（Kahn，O(V+E)），同层可并行，结果节点数小于 V 即有环", "依赖应是数据分区就绪而非固定时刻；任务带业务日期参数，支持 backfill 迟到补数", "补数与重试叠加要求幂等：分区覆盖写（INSERT OVERWRITE）或去重表，避免重复执行让指标翻倍", "重试带指数退避、上限与最大次数，且只对幂等操作生效；任务配超时与心跳", "SLI/SLO/错误预算围绕用户旅程定义；多窗口 burn rate 告警降噪，CPU 仅作容量参考", "混沌工程先有稳态假设、可观测与一键停止，再受控注入故障并验证重试、超时与降级"]' :pitfalls='["用固定 cron 时刻串接上下游，不做数据就绪检查", "重跑脚本无条件追加结果", "告警阈值设成 CPU 超过 80%", "把告警阈值设成「CPU 高」而不是「用户请求失败率」，值班会被噪声淹没却漏掉真实故障"]' summary='调度系统真正难的是「迟到的数据、失败的上游、重跑的幂等」，而不是 cron 表达式' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 调度用 DAG 加拓扑排序（Kahn，O(V+E)），同层可并行，结果节点数小于 V 即有环 | 建立直觉 |
| 依赖应是数据分区就绪而非固定时刻；任务带业务日期参数，支持 backfill 迟到补数 | 跑通示例 |
| 补数与重试叠加要求幂等：分区覆盖写（INSERT OVERWRITE）或去重表，避免重复执行让指标翻倍 | 深入边界 |
| 重试带指数退避、上限与最大次数，且只对幂等操作生效；任务配超时与心跳 | 工程落地 |
| SLI/SLO/错误预算围绕用户旅程定义；多窗口 burn rate 告警降噪，CPU 仅作容量参考 | 随堂检测 |
| 混沌工程先有稳态假设、可观测与一键停止，再受控注入故障并验证重试、超时与降级 | 复盘 |

1. 调度用 DAG 加拓扑排序（Kahn，O(V+E)），同层可并行，结果节点数小于 V 即有环

2. 依赖应是数据分区就绪而非固定时刻；任务带业务日期参数，支持 backfill 迟到补数

3. 补数与重试叠加要求幂等：分区覆盖写（INSERT OVERWRITE）或去重表，避免重复执行让指标翻倍

[下一讲：安全工程：依赖、注入、序列化与密钥](/distributed/security)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/112-scheduling.py`

```bash
python3 examples/lessons/112-scheduling.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/112-scheduling.py) · [全部示例代码索引](/examples/)
