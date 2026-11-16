---
title: 第 111 讲 · GitOps、灰度发布与可观测平台
description: 让发布可追溯、可灰度、可回滚
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★☆' time='40 分钟' goal='让发布可追溯、可灰度、可回滚' prereq='第 110 讲 · 容器化与 Kubernetes 部署' />

# 第 111 讲 · GitOps、灰度发布与可观测平台

服务已经稳稳跑在集群里，接下来的问题换成「怎么改它」。一次全量更新把失败率推高，值班的人盯着屏幕手动回滚，等反应过来往往已经波及所有实例。要让变更可追溯、可小步验证、可自动退回，靠的不是发布那一刻更专心，而是一套事先定好、以 GitOps 为骨架的机制。

这一讲先看声明式的期望状态，以及 Helm、Kustomize 怎么管清单；再用金丝雀与蓝绿把流量按比例分桶放量；最后接上 Metrics、Logging、Tracing 三支柱，用 SLO 与错误预算算清该不该自动回滚。需要上一讲的部署清单、Git 基本操作和一点指标概念；学完你能设计一次灰度发布，也能说清 99.9% 的 SLO 在三十天窗口里留了多少余地。


## 全量滚动更新把失败率抬到全量，缺的是什么

一个团队用流水线直接执行 `kubectl apply` 做全量滚动更新，发布时有人盯着大屏看错误率。某次新版本把 `/pay` 接口的失败率从 0.1% 抬到 8%，滚动更新几分钟内把全部实例换成新版，等值班发现并手工回滚，故障已经扩散到全量用户，错误预算一次烧掉大半。

复盘找出三个缺口：变更没有可对比的版本清单、放量没有按比例的中间态、回滚条件没和指标绑定而全靠人判断。还有一次配置文件被直接改在集群里，Git 里的清单与线上不一致，下次发布把改动覆盖掉，问题又冒了出来。

GitOps、灰度与可观测平台其实在处理同一件事：让每次发布有版本、有对比、有分阶段暴露、有能自动触发的回退路径，并把 SLO 与错误预算变成发布门禁，而不是事后才翻的报表。

<Callout type="warn" title='先看一个真实会出错的写法' text='用随机数或轮询给灰度流量分桶：同一用户刷新一次就切换版本，指标被混合稀释，会话状态在新旧实现间跳变，错误率差异无法归因' />

<CheckList id='P111a' title='学完你应当能' :items='["能讲清 声明式期望状态、Helm 与 Kustomize", "能讲清 金丝雀、蓝绿与流量比例的确定性分桶", "能讲清 三支柱、SLO 与指标驱动的自动回滚", "能在工程里处理 SLO 与错误预算"]' />


## 声明式期望状态、Helm 与 Kustomize

GitOps 的核心是把集群的期望状态以声明式清单存在 Git 里，由控制器（Argo CD、Flux）持续比对实际状态并调和，任何漂移都会被发现或自动纠正；变更走 pull request，天然留下评审、版本与回滚记录。这种调和是幂等的：控制器反复应用同一份清单，结果始终一致，而不是每次追加操作。

Helm 用模板加 values 渲染清单，适合把同一套应用分发到多环境，代价是模板层多了一层抽象、values 也容易漂移；Kustomize 用 base 加 overlay 打补丁，不引入模板语法，更适合按环境叠加差异。

两者最终都该渲染成可审查的清单文件，CI 里用 `helm template` 或 `kustomize build` 渲染之后做 diff 与策略检查。

关键约束是别在集群里手工执行 `kubectl edit`：手工改动不在 Git 中，下次调和会被覆盖，也审计不出谁改了什么。镜像标签要固定成不可变摘要（digest），不要用 latest 这种会浮动的标签，否则同一份清单在不同时间拉到不同内容，回滚就失去确定性。

**Helm 与 Kustomize 取舍**

| 维度 | Helm | Kustomize |
| --- | --- | --- |
| 组织方式 | 模板 + values 渲染 | base + overlay 补丁 |
| 多环境 | 一套 chart 配多份 values | overlay 叠加差异 |
| 抽象代价 | 模板语法与 values 漂移 | 无模板，输出更贴近原生 YAML |
| CI 检查 | helm template 后 diff | kustomize build 后 diff |


### CI 渲染清单后的 diff 与策略检查

<CheckList id='P111b' title='上线前自检' :items='["能复现并解释「用随机数或轮询给灰度流量分桶」", "能复现并解释「金丝雀放量没有样本量下限就做回滚判断」", "能复现并解释「集群里直接 kubectl edit 改配置，镜像用 lat…」", "能用一条命令验证 声明式与期望状态", "关键路径有自动化测试与失败分支"]' />


## 金丝雀、蓝绿与流量比例的确定性分桶

灰度发布按流量比例逐步放量：先放 5% 观察核心指标，再 20%、50%，最后 100%。分桶必须确定性且无状态：对稳定的用户标识（`user_id` 或设备 id）做哈希取模，同一用户在一次发布中始终落到同一版本，避免来回切换把会话状态弄乱；用随机数分桶则要不得，刷新一次就换版本。

实现上用稳定哈希把标识映射成整数再取模，例如用 md5 取十六进制前缀转成整数后对 1000 取模，落进千分桶，canary 占前 pct×10 个桶；这里的关键是哈希对同一输入恒定，Python 内置的 `hash()` 对字符串带随机化、跨进程重启会变，不能拿它分桶。

蓝绿部署准备两套完整环境，靠切流量一次性切换，回滚快，代价是资源翻倍、切换瞬间风险集中；金丝雀省资源、暴露可控，却要求流量染色、指标按版本拆分与自动决策。网关或 Service Mesh 按请求头、cookie 染色，可以支持内部灰度。

放量前要定好判定窗口（如连续 5 分钟）、样本量下限（避免小流量噪声误判）与核心指标（错误率、p99 延迟、业务转化率），样本不足时只观察、不做回滚判断。

```python
import hashlib

def bucket(user, mod=1000):
    return int(hashlib.md5(user.encode()).hexdigest()[:8], 16) % mod

def route(user, canary_pct):
    return 'canary' if bucket(user) < canary_pct * 10 else 'stable'

users = ['u' + str(i) for i in range(1000)]
for pct in (5, 20, 50):
    c = sum(1 for u in users if route(u, pct) == 'canary')
    print('pct', pct, 'canary_users', c)

def should_rollback(errors, total, threshold=0.02):
    return total > 0 and errors / total > threshold

print('rollback_when_high', should_rollback(8, 100))
print('keep_when_low', should_rollback(1, 100))
```

<OutputBox title='主示例运行结果' output='pct 5 canary_users 59\npct 20 canary_users 191\npct 50 canary_users 487\nrollback_when_high True\nkeep_when_low False' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import hashlib\n\ndef bucket(user, mod=1000):\n    return int(hashlib.md5(user.encode()).hexdigest()[:8], 16) % mod\n\ndef route(user, canary_pct):\n    return &#39;canary&#39; if bucket(user) &lt; canary_pct * 10 else &#39;stable&#39;\n\nusers = [&#39;u&#39; + str(i) for i in range(1000)]\nfor pct in (5, 20, 50):\n    c = sum(1 for u in users if route(u, pct) == &#39;canary&#39;)\n    print(&#39;pct&#39;, pct, &#39;canary_users&#39;, c)\n\ndef should_rollback(errors, total, threshold=0.02):\n    return total &gt; 0 and errors / total &gt; threshold\n\nprint(&#39;rollback_when_high&#39;, should_rollback(8, 100))\nprint(&#39;keep_when_low&#39;, should_rollback(1, 100))' :notes='["导入 hashlib 做稳定散列，保证同一用户落点固定", "空行，只用于分隔逻辑块，不影响执行结果。", "把用户标识映射到 0 到 999 的千分桶", "md5 前 8 位十六进制转整数后取模，mod 默认 1000", "空行，只用于分隔逻辑块，不影响执行结果。", "route 按灰度百分比决定版本", "桶号小于 pct*10 进金丝雀，否则进稳定版", "空行，只用于分隔逻辑块，不影响执行结果。", "构造 1000 个用户用于统计实际放量比例", "依次观察 5%、20%、50% 三档", "统计落入金丝雀的用户数", "打印档位与实际人数，验证接近目标比例", "空行，只用于分隔逻辑块，不影响执行结果。", "should_rollback 把错误率与阈值比较", "样本为 0 时不做判断，避免除零误判", "空行，只用于分隔逻辑块，不影响执行结果。", "8/100 错误率 8% 超过 2% 阈值，应回滚", "1/100 错误率 1% 低于阈值，继续放量"]' title='第 111 讲 · GitOps、灰度发布与可观测平台' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：随机分桶与稳定 user_id 哈希分桶

```python
def error_budget(slo, requests):
    return (1 - slo) * requests
def burned(allowed, errors):
    return round(errors / allowed, 3)

budget = error_budget(0.999, 1000000)
print('budget_requests', int(budget))
print('burned_500', burned(budget, 500))
print('burned_1500', burned(budget, 1500))
```

<OutputBox title='对照写法：先自己猜，再点开' output='budget_requests 1000\nburned_500 0.5\nburned_1500 1.5' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import hashlib\n\ndef bucket(user, mod=1000):\n    return int(hashlib.md5(user.encode()).hexdigest()[:8], 16) % mod\n\ndef route(user, canary_pct):\n    return &#39;canary&#39; if bucket(user) &lt; canary_pct * 10 else &#39;stable&#39;\n\nusers = [&#39;u&#39; + str(i) for i in range(1000)]\nfor pct in (5, 20, 50):\n    c = sum(1 for u in users if route(u, pct) == &#39;canary&#39;)\n    print(&#39;pct&#39;, pct, &#39;canary_users&#39;, c)\n\ndef should_rollback(errors, total, threshold=0.02):\n    return total &gt; 0 and errors / total &gt; threshold\n\nprint(&#39;rollback_when_high&#39;, should_rollback(8, 100))\nprint(&#39;keep_when_low&#39;, should_rollback(1, 100))", "note": "声明式期望状态、Helm 与 Kustomize"}, {"label": "对照 / 进阶", "code": "def error_budget(slo, requests):\n    return (1 - slo) * requests\ndef burned(allowed, errors):\n    return round(errors / allowed, 3)\n\nbudget = error_budget(0.999, 1000000)\nprint(&#39;budget_requests&#39;, int(budget))\nprint(&#39;burned_500&#39;, burned(budget, 500))\nprint(&#39;burned_1500&#39;, burned(budget, 1500))", "note": "金丝雀、蓝绿与流量比例的确定性分桶"}]' title='两种写法切换看' />

```python
desired = {'replicas': 4, 'image': 'app:v2'}
current = {'replicas': 2, 'image': 'app:v1'}
diff = {k: (current.get(k), desired[k]) for k in desired if current.get(k) != desired[k]}
print('diff', diff)
print('need_apply', len(diff) > 0)
```

<OutputBox title='原理验证' output='diff {&#39;replicas&#39;: (2, 4), &#39;image&#39;: (&#39;app:v1&#39;, &#39;app:v2&#39;)}\nneed_apply True' />


## 发布策略对照

**发布策略对照**

| 策略 | 资源开销 | 回滚速度 | 主要风险 |
| --- | --- | --- | --- |
| 全量滚动更新 | 低 | 慢，需重新回滚全部实例 | 故障等比放大到全量用户 |
| 蓝绿 | 翻倍 | 快，切流量即可 | 切换瞬间风险集中、需双份资源 |
| 金丝雀按比例 | 低 | 快，切回稳定版 | 需版本拆分指标与自动决策 |
| 按 header 染色 | 低 | 快 | 仅覆盖带染色的内部或特定流量 |


## 用随机数或轮询给灰度流量分桶

<Callout type="warn" title='本讲最容易踩的坑' text='用随机数或轮询给灰度流量分桶：同一用户刷新一次就切换版本，指标被混合稀释，会话状态在新旧实现间跳变，错误率差异无法归因' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用随机数或轮询给灰度流量分桶", "body": "同一用户刷新一次就切换版本，指标被混合稀释，会话状态在新旧实现间跳变，错误率差异无法归因", "tip": "对稳定 user_id 做哈希取模落到千分桶，同一发布内映射恒定；内部灰度用 header 染色"}, {"title": "第 2 步：金丝雀放量没有样本量下限就做回滚判断", "body": "5% 流量初期样本极少，偶发几个错误就让错误率飙升，触发误回滚，发布反复失败", "tip": "设定最小样本量与连续观察窗口，样本不足时只观察不决策；用 burn rate 而非瞬时错误率"}, {"title": "第 3 步：集群里直接 kubectl edit 改配置…", "body": "手工改动不在 Git 里，下次调和被覆盖且无法审计；latest 让同一份清单在不同时间拉到不同镜像，回滚失去确定性", "tip": "所有变更走 PR 由控制器调和，镜像固定为 digest，CI 渲染清单后做 diff 与策略检查"}]' />


## 可观测三支柱、SLO 与指标驱动的自动回滚

可观测性三支柱是 Metrics（聚合指标与告警）、Logging（离散事件）、Tracing（跨服务调用链）；发布期间尤其要按版本标签把指标拆开，否则新旧版本混在一起看不出差异。

SLO 用 SLI 表达，例如三十天窗口内成功请求占比 99.9%，对应错误预算是总请求数的 0.1%，100 万请求允许 1000 次失败；burn rate 是当前错误消耗速度与预算允许速度的比值，等于 1 表示刚好用满，超过阈值（如 6 倍持续 5 分钟）就应触发告警或暂停发布。

自动回滚把放量决策与指标绑在一起：金丝雀版本的错误率越过阈值或 p99 超限时，控制器自动把流量切回稳定版并标记发布失败，比人工盯屏快一个数量级。回滚要能一键执行且经过演练，在 Git 里把清单回退到上一个版本，控制器调和之后即完成回滚。告警本身应当可行动、分级别、带预案，别用 CPU 高这类与用户体验弱相关的信号刷屏。

**SLO 与错误预算换算（30 天窗口）**

| SLO | 允许失败比例 | 100 万请求的预算 | burn rate 含义 |
| --- | --- | --- | --- |
| 99.0% | 1% | 10000 次 | 当前消耗速度与预算速度之比 |
| 99.9% | 0.1% | 1000 次 | 1 为刚好用满，6 倍持续 5 分钟应告警 |
| 99.99% | 0.01% | 100 次 | 预算极窄，发布需更小步长 |


### 错误预算与 burn rate 的换算

确定性分桶是灰度可分析的前提：对稳定标识做哈希取模后，同一请求在整次发布中恒定映射到同一版本，新旧版本的指标便能按标签聚合比较，用户也不会因为刷新在两套状态间跳变。换成随机数或轮询分桶，同一用户多次请求落在不同版本，错误率与延迟被混合稀释，判断不出差异来自版本还是分桶噪声。

错误预算把可靠性变成可消耗的量化资源：SLO 是滑动窗口内 SLI 的目标，预算等于 `(1 - SLO)` 乘以窗口总请求数，burn rate 则是单位时间实际错误数与预算允许速度之比，用速率而非累计值，才能在预算耗尽前提前告警。

自动回滚把这两者接成闭环：控制器周期性读取金丝雀版本按标签拆分的错误率与 p99，达到最小样本量之后才开始判定，一旦超过阈值就判失败，直接把流量比例调回 0 并回退清单；由于 GitOps 的调和幂等且版本化，回滚就是应用一个已知的旧版本，不需要发布时有人守在屏幕前。


## 金丝雀放量没有样本量下限就做回滚判断

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用随机数或轮询给灰度流量分桶 | 同一用户刷新一次就切换版本，指标被混合稀释，会话状态在新旧实现间跳变，错误率差异无法归因 | 对稳定 user_id 做哈希取模落到千分桶，同一发布内映射恒定；内部灰度用 header 染色 |
| 金丝雀放量没有样本量下限就做回滚判断 | 5% 流量初期样本极少，偶发几个错误就让错误率飙升，触发误回滚，发布反复失败 | 设定最小样本量与连续观察窗口，样本不足时只观察不决策；用 burn rate 而非瞬时错误率 |
| 集群里直接 kubectl edit 改配置，镜像用 latest tag | 手工改动不在 Git 里，下次调和被覆盖且无法审计；latest 让同一份清单在不同时间拉到不同镜像，回滚失去确定性 | 所有变更走 PR 由控制器调和，镜像固定为 digest，CI 渲染清单后做 diff 与策略检查 |


## 指标驱动的金丝雀发布控制器

把一次发布建模成一个带状态机的最小控制器：按稳定哈希分桶决定每个用户走哪个版本，累计各版本的请求数与错误数，达到最小样本量后计算金丝雀错误率，与阈值比较决定继续放量还是自动回滚，并把每一步决策写进审计日志。

真实实现里流量比例由网关或 Service Mesh 下发，指标来自 Prometheus 按版本标签的时间序列，回滚靠回退 Git 清单触发控制器调和。下面这段用标准库把分桶、指标累计、阈值判定与审计串成闭环，重点看每个决策都有可核对的输入与输出，而不是靠人盯屏。

```python
import hashlib

class Canary:
    def __init__(self, pct, threshold=0.02, min_samples=30):
        self.pct = pct
        self.threshold = threshold
        self.min_samples = min_samples
        self.stats = {'canary': [0, 0], 'stable': [0, 0]}
        self.audit = []
    def bucket(self, uid):
        return int(hashlib.md5(uid.encode()).hexdigest()[:8], 16) % 1000
    def version(self, uid):
        return 'canary' if self.bucket(uid) < self.pct * 10 else 'stable'
    def observe(self, uid, failed):
        v = self.version(uid)
        self.stats[v][0] += 1
        self.stats[v][1] += int(failed)
    def decide(self):
        n, e = self.stats['canary']
        if n < self.min_samples:
            return 'observing'
        if e / n > self.threshold:
            self.audit.append('rollback at pct ' + str(self.pct))
            return 'rollback'
        self.audit.append('promote')
        return 'promote'

c = Canary(20)
for i in range(200):
    c.observe('u' + str(i), failed=(i % 3 == 0))
print('decision', c.decide())
print('stats', c.stats)
print('audit', c.audit)
```

<Callout type="idea" title='落地提示' text='把清单放 Git 由流水线同步，灰度按流量比例逐步放量，绑定核心指标自动回滚，并保留一键回退' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 声明式与期望状态 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 集群里直接 kubectl edit 改配置，镜像用 latest tag

<SequenceDiagram title='第 111 讲 · 调用时序' caption='从触发到收尾，标出最可能失败的两个位置' :actors='["调用方", "核心逻辑", "外部依赖"]' :steps='[{"from": "调用方", "to": "核心逻辑", "label": "发起调用", "note": "声明式期望状态、Helm 与…", "kind": "call"}, {"from": "核心逻辑", "to": "核心逻辑", "label": "检查前置", "note": "金丝雀、蓝绿与流量比例的确定…", "kind": "self"}, {"from": "核心逻辑", "to": "外部依赖", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "外部依赖", "to": "核心逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "核心逻辑", "to": "调用方", "label": "返回或降级", "note": "清理资源", "kind": "return"}]' />

<FlowTimeline :steps='[{"title": "声明式期望状态、Helm 与 Kustomize", "desc": "GitOps 的核心是把集群的期望状态以声明式清单存在 Git 里，由控制器（Arg…", "tone": "blue"}, {"title": "金丝雀、蓝绿与流量比例的确定性分桶", "desc": "灰度发布按流量比例逐步放量：先放 5% 观察核心指标，再 20%、50%，最后 10…", "tone": "purple"}, {"title": "三支柱、SLO 与指标驱动的自动回滚", "desc": "可观测性三支柱是 Metrics（聚合指标与告警）、Logging（离散事件）、Tr…", "tone": "orange"}, {"title": "工程落地", "desc": "指标驱动的金丝雀发布控制器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 练习与一页纸速记

<Exercise title='基础：计算给定 SLO 的错误预算与 burn' task='写函数 error_budget(slo, requests) 与 burn(allowed, errors)，对 99.9% SLO、100 万请求打印预算与 500、1500 次错误的 burn 值。' solution='def budget(slo, n):\n    return (1 - slo) * n\ndef burn(allowed, errors):\n    return round(errors / allowed, 3)\nb = budget(0.999, 1000000)\nprint(int(b), burn(b, 500), burn(b, 1500))' explain='99.9% SLO 在 100 万请求里允许 1000 次失败；500 次用掉 0.5 倍预算，1500 次已达 1.5 倍，应触发告警或暂停发布。' />

<Exercise title='进阶：实现确定性分桶并验证映射稳定' task='写 version(uid, pct) 用 md5 取模千分桶，验证同一 uid 在不同 pct 下只会在达到阈值时从 stable 切到 canary，不会来回跳变。' solution='import hashlib\ndef b(uid):\n    return int(hashlib.md5(uid.encode()).hexdigest()[:8], 16) % 1000\ndef version(uid, pct):\n    return &#39;canary&#39; if b(uid) &lt; pct * 10 else &#39;stable&#39;\nu = &#39;user:42&#39;\nprint(b(u), [version(u, p) for p in (5, 20, 50, 100)])' explain='桶号固定，随 pct 单调扩大：小比例时为 stable，越过自身桶号对应阈值后才变 canary，不会反复横跳，这正是灰度指标可拆分的前提。' />

<Quiz no='111-1' q='某次全量滚动更新把失败率抬到 8%，值班几分钟后手工回滚，故障仍放大到全量，主要缺什么？' :options='["按流量比例的中间态与指标绑定的自动回滚", "更大的镜像仓库带宽", "更多副本数", "更长的观察窗口但不设阈值"]' answer="0" explain='全量滚动没有小比例暴露阶段，回滚靠人判断必然滞后；金丝雀放量加指标阈值自动切回，才能把影响限制在已放量的那部分用户。' />

<Quiz no='111-2' q='关于灰度分桶，下面哪项做法正确？' :options='["对稳定 user_id 做哈希取模，同一用户映射恒定", "每次请求用 random.random() 决定版本", "按请求到达顺序轮询分配", "按响应耗时动态分配版本"]' answer="0" explain='随机或轮询会让同一用户多次请求落在不同版本，指标被稀释且会话错乱；稳定哈希分桶让新旧版本指标可按标签聚合比较。' />

<Quiz no='111-3' q='99.9% SLO、30 天 100 万请求，错误预算是多少？' :options='["1000 次失败", "10000 次失败", "100 次失败", "0 次失败"]' answer="0" explain='(1 - 0.999) * 1000000 = 1000。预算是允许失败的请求数，用 burn rate 衡量消耗速度可在耗尽前告警。' />

<KnowledgeCard :points='["GitOps 把期望状态存 Git，控制器幂等调和；集群内改动一律回 Git，手工 edit 会在下次调和被覆盖", "Helm 用模板 + values，Kustomize 用 base + overlay；CI 渲染清单后做 diff 与策略检查，镜像标签固定 digest", "灰度按稳定标识的 md5 哈希取模分桶，同一用户映射恒定；蓝绿回滚快但资源翻倍", "放量需最小样本量、连续观察窗口与按版本拆分的错误率/p99，样本不足只观察不决策", "SLO 的预算 = (1-SLO)*请求数；burn rate 用消耗速度提前告警，而非等累计值超标", "自动回滚把指标阈值与流量切换绑定；告警要可行动、有级别、有预案，不用 CPU 高这类弱相关信号"]' :pitfalls='["用随机数或轮询给灰度流量分桶", "金丝雀放量没有样本量下限就做回滚判断", "集群里直接 kubectl edit 改配置，镜像用 latest tag", "只做全量滚动更新、又没有与指标联动的回滚条件，故障会等比放大到全部实例"]' summary='发布的安全性来自「任何变更都有版本、有对比、有回退路径」，而不是发布时有人盯着屏幕' />

1. GitOps 把期望状态存 Git，控制器幂等调和；集群内改动一律回 Git，手工 edit 会在下次调和被覆盖

2. Helm 用模板 + values，Kustomize 用 base + overlay；CI 渲染清单后做 diff 与策略检查，镜像标签固定 digest

3. 灰度按稳定标识的 md5 哈希取模分桶，同一用户映射恒定；蓝绿回滚快但资源翻倍

[下一讲：任务调度、SRE 与混沌工程](/distributed/scheduling)

<Predict no='111-4' q='1000 个用户按 20% 灰度分桶，落入 canary 的人数最可能是？' :options='["约 191，接近 200 但因哈希分布略有偏差", "恰好 200", "0，20% 需要 2000 用户才生效"]' answer='0' output='191' explain='千分桶里 20% 对应前 200 个桶；md5 散列在有限样本上并非绝对均匀，实测 1000 个用户有 191 个落入，接近但不等于理论值 200。' />

<FillBlank no='111-5' tpl='___ hashlib' :answers='["import"]' hint='回想本讲关于 声明式与期望状态 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 声明式期望状态、Helm 与 Kustomize 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/111-gitops.py`

```bash
python3 examples/lessons/111-gitops.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/111-gitops.py) · [全部示例代码索引](/examples/)
