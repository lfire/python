---
title: 第 110 讲 · 容器化与 Kubernetes 部署
description: 把 Python 服务稳定地跑在集群里
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★☆' time='45 分钟' goal='把 Python 服务稳定地跑在集群里' prereq='第 109 讲 · Raft 共识、服务发现与配置中心' />

# 第 110 讲 · 容器化与 Kubernetes 部署

一致性、分片、选主都安排好，服务终究要落到真实机器上跑。常见落差是：本地怎么跑都顺，一交到集群就起不来，或者高峰刚扩容就被悄悄重启。这一步不再谈数据怎么分，而是谈进程交给平台托管之后，凭什么判断它活着、给它多少资源、怎么让它体面退场。

先从镜像分层和多阶段构建把体积瘦下来，再看资源请求与限制怎样和 CPython 的内存脾气相处、解释反复 OOMKill 的由来，最后分开存活与就绪探针，配 `SIGTERM` 优雅退出。需要虚拟环境、进程和一点 `HTTP` 概念；读完后你能为容器化与 Kubernetes 部署写出清单，也看得懂一次驱逐卡在哪。


## 探针写成强依赖数据库，一次抖动全量重启

一个 Python Web 服务用基础镜像 `python:3.13` 直接 `COPY` 代码、`pip install` 全部依赖，构建出的镜像 1.1GB。每次发版拉取镜像要两分钟，HPA 扩容时新 Pod 迟迟起不来，流量高峰先超时再扩容，等于扩了个寂寞。

更隐蔽的是没设内存 limit：CPython 的字典缓存与某个 C 扩展在高峰期把 RSS 顶到节点上限，Pod 被 OOMKill，重启又立刻预热，形成反复重启。团队还把就绪探针写成强依赖数据库，数据库一抖动，就绪探针全量失败，K8s 把所有实例同时摘出 Service，健康实例也一起失联。

最后 `SIGTERM` 到来时进程直接退出，正在处理的请求被截断，客户端收到 502。镜像分层、资源限制、探针语义与优雅退出，四者缺一都会让 Python 服务在集群里不稳定。

<Callout type="warn" title='先看一个真实会出错的写法' text='Dockerfile 先 COPY 全部源码再 pip install：任何一行代码改动都会让缓存的依赖层失效，每次构建重装依赖，冷启动与 CI 时间被拖长' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段十 · 分布式与云原生 |
| 前置 | 第 109 讲 · Raft 共识、服务发现与配置中心 |
| 难度 / 建议时长 | ★★★★☆ · 45 分钟 |
| 本讲新增 | 镜像分层与多阶段构建、依赖与基础镜像瘦身、非 root 与只读文件系统 |
| 一句话目标 | 把 Python 服务稳定地跑在集群里 |
| 为下一讲铺垫 | GitOps、灰度发布与可观测平台 |


## 镜像分层、多阶段构建与瘦身

Docker 镜像按层叠加，每条 `RUN` / `COPY` / `ADD` 生成一层，层内容由指令与输入内容的校验和决定，未变化的层可被缓存复用。

因此 Dockerfile 应先 `COPY` 依赖清单（`requirements.txt` 或 `pyproject.toml` 加锁文件）再 `RUN pip install`，最后 `COPY` 源码，避免改一行代码就让依赖层失效重装。

`python:3.13` 这类完整镜像含编译工具链与大量头文件，体积常在 1GB 量级；多阶段构建把编译期与运行期分开：builder 阶段装 gcc、编译需要 C 扩展的依赖并产出 wheel，runtime 阶段用 `python:3.13-slim` 只装 wheel 与运行时库。

pip 用 `--no-cache-dir` 避免把缓存写进层，锁文件固定版本保证可复现。

非 root 运行要建专用用户并 chown 工作目录；容器开启 `readOnlyRootFilesystem` 时，把临时写入指向 emptyDir 挂载的 /tmp，否则任何落盘操作都会失败。

镜像体积直接决定 HPA 扩容的冷启动速度，是 SLO 的一部分。

**Python 镜像瘦身手段**

| 手段 | 作用 | 可核对信号 |
| --- | --- | --- |
| 多阶段构建 | 编译期与运行期分离 | 最终镜像层数与体积 |
| 先 COPY 锁文件再装依赖 | 改源码不触发依赖层重装 | 构建缓存命中率 |
| python:3.13-slim 基础镜像 | 去掉编译工具链与头文件 | 镜像体积从 GB 降到百 MB 量级 |
| pip --no-cache-dir | 不把 pip 缓存写入层 | 层大小与 pip cache 目录 |
| 非 root 用户 | 缩小容器内权限 | 容器 uid 与文件属主 |

<ConceptDiagram type='flow3' title='第 110 讲 · 镜像分层、多阶段构建与瘦身' labels='镜像分层、多阶段构建与瘦身|资源请求与限制、OOMKill 与 CPyt…|探针语义、preStop 与 SIGTERM…' caption='把 Python 服务稳定地跑在集群里' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## Dockerfile 先 COPY 全部源码再 pip install

<Callout type="warn" title='本讲最容易踩的坑' text='Dockerfile 先 COPY 全部源码再 pip install：任何一行代码改动都会让缓存的依赖层失效，每次构建重装依赖，冷启动与 CI 时间被拖长' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：Dockerfile 先 COPY 全部源码…", "body": "任何一行代码改动都会让缓存的依赖层失效，每次构建重装依赖，冷启动与 CI 时间被拖长", "tip": "先 COPY requirements 或锁文件、RUN pip install --no-cache-dir，最后 COPY 源码；用多阶段构建把编译依赖留在 builder"}, {"title": "第 2 步：容器不设 memory limit 或 li…", "body": "CPython 的 arena 不归还、dict 过度分配与 C 扩展原生内存使 p99 RSS 高于均值，超限时被 OOMKill 且无优雅退出", "tip": "按 p99 RSS 加余量设 limits，requests 略低于 limits；暴露 RSS 指标并配重启次数告警"}, {"title": "第 3 步：把就绪探针写成强依赖数据库，且不做 SIGT…", "body": "数据库抖动让全部实例同时被摘出 Service，故障等比放大；SIGTERM 到来进程直接退出，在途请求被截断返回 502", "tip": "就绪只反映本实例能否接流量，存活不依赖外部；注册 SIGTERM handler 置停止标志、fail readiness、drain 在途请求，preStop 等待 endpoint 摘除传播"}]' />


## 资源请求与限制、OOMKill 与 CPython 内存特征

K8s 的 `resources.requests` 决定调度与配额，`limits` 决定上限；CPU 用毫核（500m 即 0.5 核），内存用 Mi（1 Mi 等于 2 的 20 次方字节，也就是 1048576 字节）或 Gi，注意 M 与 Mi 的十进制 / 二进制差异。

CPU 超限只被限流（throttle），内存超限则触发内核 OOM Killer 直接杀容器，无法捕获、无优雅退出。

CPython 的内存特征让未设 limit 尤其危险：小对象走 `pymalloc` 的 arena / pool，释放后未必立刻归还 OS；dict / list 的过度分配、导入缓存、第三方 C 扩展的原生内存都不受 Python 堆统计约束，RSS 常高于 `tracemalloc` 看到的值。

因此 limit 要按压测 p99 RSS 加余量设定，且必须配 requests 让调度器预留；同时给应用暴露 memory 指标，而不是只看进程存活。JVM 有 `-Xmx` 这类显式堆上限，CPython 没有，容器 limit 就是事实上的堆上限。

**资源单位与配置对照**

| 配置 | 含义 | 超限行为 | Python 注意点 |
| --- | --- | --- | --- |
| cpu: 500m | 0.5 核 | 被 CFS 限流，延迟上升 | GIL 下多线程未必用满 |
| memory: 512Mi | 512 * 2^20 字节 | OOMKill，不可捕获 | pymalloc arena 与 C 扩展内存使 RSS 偏高 |
| requests | 调度与配额预留 | 节点资源不足则 Pending | 要小于 limits 留突发余量 |
| readOnlyRootFilesystem | 根文件系统只读 | 写非挂载路径即失败 | 把临时文件指向 emptyDir 挂载的 /tmp |

容器被 OOMKill 是内核 cgroup 的内存上限触发的：当容器 cgroup 的内存用量超过 `limits.memory`，内核选择其中进程发送 `SIGKILL`，用户态无法捕获，也没有 Python 层面的 `MemoryError` 兜底。

这与 CPython 的内存管理叠加出特有现象：小于 512 字节的对象由 `pymalloc` 在 256KiB 的 arena 中按 4KiB pool 分配，对象释放后 pool 只在该 arena 整体空闲时才可能归还 OS，因此即使 Python 堆里对象已回收，RSS 仍可维持高位；再叠加 C 扩展用 malloc 申请的原生内存、glibc 的分配器缓存与导入的 `__pycache__`，RSS 往往明显高于 `tracemalloc` 或 gc 统计的 Python 对象总量。

CPU 的行为不同：`limits.cpu` 通过 CFS 配额限流而非杀进程，超限时线程排队等待下一个调度周期，表现为 p99 延迟抬升。理解这两条差异，才能解释为什么内存必须留余量、为什么 CPU throttling 会拖慢延迟却不报错，以及为什么镜像拉取时间会直接决定 HPA 从触发到承载流量的滞后。


## 探针语义、preStop 与 SIGTERM 优雅退出

K8s 有三类探针：`startupProbe` 保护慢启动应用，成功后才启用另两类；`livenessProbe` 失败会重启容器，必须只检测进程自身不可恢复的状态，绝不能强依赖数据库等外部依赖；`readinessProbe` 失败只把 Pod 从 Service `endpoints` 摘除、不重启，适合反映能否接流量。

把就绪写成强依赖数据库，数据库抖动会让所有实例同时被摘，故障被等比放大。

`terminationGracePeriodSeconds` 默认 30 秒，删除 Pod 时 kubelet 先发 `SIGTERM`，到点仍未退出则 `SIGKILL`。

Python 服务必须注册 `SIGTERM` handler：置停止标志、让 readiness 立即返回失败以停止接收新请求、drain 在途请求、关闭连接池，最后退出；preStop hook 可先 sleep 几秒，等待 endpoint 摘除传播完成，避免摘除还没生效就停服、仍有新流量进来。

注意 signal handler 只在主线程的字节码检查点执行，纯 C 扩展计算期间可能延迟响应 `SIGTERM`。

```python
import signal, os

class Server:
    def __init__(self):
        self.stopping = False
        self.inflight = 3
    def handle_term(self, signum, frame):
        self.stopping = True
    def drain(self):
        while self.inflight > 0:
            self.inflight -= 1

s = Server()
signal.signal(signal.SIGTERM, s.handle_term)
print('stopping_before', s.stopping)
os.kill(os.getpid(), signal.SIGTERM)
print('stopping_after', s.stopping)
s.drain()
print('inflight_after_drain', s.inflight)
```

<OutputBox title='主示例运行结果' output='stopping_before False\nstopping_after True\ninflight_after_drain 0' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import signal, os\n\nclass Server:\n    def __init__(self):\n        self.stopping = False\n        self.inflight = 3\n    def handle_term(self, signum, frame):\n        self.stopping = True\n    def drain(self):\n        while self.inflight &gt; 0:\n            self.inflight -= 1\n\ns = Server()\nsignal.signal(signal.SIGTERM, s.handle_term)\nprint(&#39;stopping_before&#39;, s.stopping)\nos.kill(os.getpid(), signal.SIGTERM)\nprint(&#39;stopping_after&#39;, s.stopping)\ns.drain()\nprint(&#39;inflight_after_drain&#39;, s.inflight)' :notes='["导入 signal 注册处理器、os 用于给自己发信号", "空行，只用于分隔逻辑块，不影响执行结果。", "模拟持有在途请求的服务", "初始化停止标志与在途计数", "stopping 供就绪探针与主循环读取", "inflight 记录尚未处理完的请求数", "SIGTERM 处理器只置标志，不做重活", "把停止状态置真，主循环据此停止收新请求", "drain 把在途请求处理完再退出", "在途未清零时持续等待", "每处理完一个请求递减在途计数", "空行，只用于分隔逻辑块，不影响执行结果。", "创建服务实例", "把 handle_term 注册为 SIGTERM 处理器", "打印停止标志初值，正常服务为 False", "模拟 kubelet 删除 Pod 时发送 SIGTERM", "信号在字节码检查点被处理，标志变为 True", "进入 drain，等待并清空在途请求", "打印在途请求数，0 表示可安全退出"]' title='第 110 讲 · 容器化与 Kubernetes 部署' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**K8s 探针语义与失败后果**

| 探针 | 失败后果 | 应检测内容 | 禁止依赖 |
| --- | --- | --- | --- |
| startupProbe | 重启容器，期间不启用另两类 | 应用初始化是否完成 | 外部服务可用性 |
| livenessProbe | 重启容器 | 进程自身是否死锁或不可恢复 | 数据库、下游接口 |
| readinessProbe | 仅从 endpoints 摘除，不重启 | 当前能否接收流量 | 强依赖导致的全量同时失败 |


## 对照：不做 SIGTERM 处理与限时 drain

```python
class Probe:
    def __init__(self):
        self.db_ok = True
    def readiness(self):
        return self.db_ok
    def liveness(self):
        return True
p = Probe()
print('readiness_ok', p.readiness())
p.db_ok = False
print('readiness_db_down', p.readiness())
print('liveness_still_ok', p.liveness())
```

<OutputBox title='对照写法：先自己猜，再点开' output='readiness_ok True\nreadiness_db_down False\nliveness_still_ok True' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import signal, os\n\nclass Server:\n    def __init__(self):\n        self.stopping = False\n        self.inflight = 3\n    def handle_term(self, signum, frame):\n        self.stopping = True\n    def drain(self):\n        while self.inflight &gt; 0:\n            self.inflight -= 1\n\ns = Server()\nsignal.signal(signal.SIGTERM, s.handle_term)\nprint(&#39;stopping_before&#39;, s.stopping)\nos.kill(os.getpid(), signal.SIGTERM)\nprint(&#39;stopping_after&#39;, s.stopping)\ns.drain()\nprint(&#39;inflight_after_drain&#39;, s.inflight)", "note": "镜像分层、多阶段构建与瘦身"}, {"label": "对照 / 进阶", "code": "class Probe:\n    def __init__(self):\n        self.db_ok = True\n    def readiness(self):\n        return self.db_ok\n    def liveness(self):\n        return True\np = Probe()\nprint(&#39;readiness_ok&#39;, p.readiness())\np.db_ok = False\nprint(&#39;readiness_db_down&#39;, p.readiness())\nprint(&#39;liveness_still_ok&#39;, p.liveness())", "note": "资源请求与限制、OOMKill 与 CPython 内存特征"}]' title='两种写法对照' note='差异集中在 镜像分层与多阶段构建；先看输出，再找背后的规则。' />

```python
def millicores(m):
    return m / 1000
def mebibytes(mi):
    return mi * 1024 * 1024
def burst(request, limit, replicas):
    return (limit - request) * replicas

print('cpu_250m_cores', millicores(250))
print('mem_512Mi_bytes', mebibytes(512))
print('burst_200m_x4', burst(200, 500, 4))
```

<OutputBox title='原理验证' output='cpu_250m_cores 0.25\nmem_512Mi_bytes 536870912\nburst_200m_x4 1200' />


## 带优雅退出与探针分层的 Python 服务骨架

把 Pod 生命周期映射成 Python 里可断言的状态：启动后置 `ready`，`SIGTERM` 到来先让 readiness 失败以停止接收新请求，再 drain 在途请求，最后关闭资源退出；liveness 只反映进程是否卡死，不查数据库。

下面这段用标准库把这条链路写成可运行骨架，`stopping` 标志同时驱动主循环与就绪判定。

真实项目里 drain 要等待连接池归零、给在途请求设上限超时、超过 `terminationGracePeriodSeconds` 则被 `SIGKILL`，所以清理段必须限时。

重点是任何探针失败都有明确、且不放大故障的后果。

```python
import signal, threading, time

class App:
    def __init__(self):
        self.ready = False
        self.stopping = False
        self.inflight = 0
        self.lock = threading.Lock()
    def on_term(self, signum, frame):
        self.stopping = True
        self.ready = False
    def readiness(self):
        return self.ready and not self.stopping
    def liveness(self):
        return True
    def handle(self, i):
        with self.lock:
            if self.stopping:
                return 'rejected'
            self.inflight += 1
        time.sleep(0.001)
        with self.lock:
            self.inflight -= 1
        return 'ok'
    def drain(self, timeout=5):
        end = time.monotonic() + timeout
        while self.inflight > 0 and time.monotonic() < end:
            time.sleep(0.01)
        return self.inflight

app = App()
app.ready = True
signal.signal(signal.SIGTERM, app.on_term)
print('ready', app.readiness(), 'live', app.liveness())
print('req', app.handle(1))
app.on_term(signal.SIGTERM, None)
print('ready_after_term', app.readiness())
print('left_after_drain', app.drain())
```

<Callout type="idea" title='落地提示' text='多阶段构建、锁文件安装、非 root 运行、就绪与存活探针分开、preStop 配合优雅退出' />

<CheckList id='P110a' title='上线前自检' :items='["能复现并解释「Dockerfile 先 COPY 全部源码再 pip in…」", "能复现并解释「容器不设 memory limit 或 limit 贴着压测…」", "能复现并解释「把就绪探针写成强依赖数据库，且不做 SIGTERM 处理」", "能用一条命令验证 镜像分层与多阶段构建", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 镜像分层与多阶段构建 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| Dockerfile 先 COPY 全部源码再 pip install | 任何一行代码改动都会让缓存的依赖层失效，每次构建重装依赖，冷启动与 CI 时间被拖长 | 先 COPY requirements 或锁文件、RUN pip install --no-cache-dir，最后 COPY 源码；用多阶段构建把编译依赖留在 builder |
| 容器不设 memory limit 或 limit 贴着压测均值 | CPython 的 arena 不归还、dict 过度分配与 C 扩展原生内存使 p99 RSS 高于均值，超限时被 OOMKill 且无优雅退出 | 按 p99 RSS 加余量设 limits，requests 略低于 limits；暴露 RSS 指标并配重启次数告警 |
| 把就绪探针写成强依赖数据库，且不做 SIGTERM 处理 | 数据库抖动让全部实例同时被摘出 Service，故障等比放大；SIGTERM 到来进程直接退出，在途请求被截断返回 502 | 就绪只反映本实例能否接流量，存活不依赖外部；注册 SIGTERM handler 置停止标志、fail readiness、drain 在途请求，preStop 等待 endpoint 摘除传播 |


## HPA 期望副本公式与滚动更新的可用 Pod 数

HPA 控制器每个同步周期（默认 `horizontal-pod-autoscaler-sync-period=15s`）读一次指标，按每个指标算 `desiredReplicas = ceil`(currentReplicas 乘 currentMetricValue 除以 desiredMetricValue)，多指标取最大值；比值落在 1 加减 tolerance（默认 0.1）内则维持 currentReplicas。

源码在 `kubernetes/pkg/controller/podautoscaler/horizontal.go` 的 computeReplicasForMetrics 与convertDesiredReplicasWithRules，后者叠加稳定窗口：缩容取 `behavior.scaleDown.stabilizationWindowSeconds`（默认 300s）内历史建议的最大值，避免指标瞬时回落就缩掉刚扩出的 Pod；扩容受 `scaleUp.policies` 速率限制。

由公式能推出「扩容永远追不上流量」的量化条件：设流量每秒增长 r、单 Pod 容量 c、冷启动耗时 T_cold，从指标越限到新 Pod Ready 至少要 T_sync + T_schedule + T_cold 秒，容量缺口是 r 乘该延迟再减现有余量；镜像 1.1GB、拉镜像两分钟时 T_cold 远大于 RPS 爬升时间，desiredReplicas 算得再正确也已经超时。

因此镜像瘦身是把 T_cold 压进 SLO 预算，同时配 minReplicas 预留 buffer 或用并发数等指标提前扩。

滚动更新另有一条算术：maxSurge 与 maxUnavailable 决定总 Pod 上限 replicas+maxSurge 与最低可用 replicas-maxUnavailable，二者不能同时为 0，源码在 `pkg/controller/deployment/rolling.go`。

```python
import math

def desired_replicas(current, metric, target, tolerance=0.1, min_r=1, max_r=10):
    ratio = metric / target
    if abs(ratio - 1.0) <= tolerance:
        return current
    want = math.ceil(current * ratio)
    return max(min_r, min(max_r, want))

def rolling(replicas, max_surge, max_unavailable):
    return replicas + max_surge, replicas - max_unavailable

print('hpa_50_of_70', desired_replicas(4, 50, 70))
print('hpa_140_of_70', desired_replicas(4, 140, 70))
print('hpa_74_of_70', desired_replicas(4, 74, 70))
print('rolling_4_1_1', rolling(4, 1, 1))
print('rolling_8_2_1', rolling(8, 2, 1))
```

<OutputBox title='扩展示例运行结果' output='hpa_50_of_70 3\nhpa_140_of_70 8\nhpa_74_of_70 4\nrolling_4_1_1 (5, 3)\nrolling_8_2_1 (10, 7)' />

<LineByLine code='import math\n\ndef desired_replicas(current, metric, target, tolerance=0.1, min_r=1, max_r=10):\n    ratio = metric / target\n    if abs(ratio - 1.0) &lt;= tolerance:\n        return current\n    want = math.ceil(current * ratio)\n    return max(min_r, min(max_r, want))\n\ndef rolling(replicas, max_surge, max_unavailable):\n    return replicas + max_surge, replicas - max_unavailable\n\nprint(&#39;hpa_50_of_70&#39;, desired_replicas(4, 50, 70))\nprint(&#39;hpa_140_of_70&#39;, desired_replicas(4, 140, 70))\nprint(&#39;hpa_74_of_70&#39;, desired_replicas(4, 74, 70))\nprint(&#39;rolling_4_1_1&#39;, rolling(4, 1, 1))\nprint(&#39;rolling_8_2_1&#39;, rolling(8, 2, 1))' :notes='["期望副本公式：当前副本乘指标比值再向上取整", "空行，只用于分隔逻辑块，不影响执行结果。", "比值落在 1 加减 tolerance 内直接维持当前副本，抑制抖动", "滚动更新：总 Pod 上限与最低可用 Pod 两个硬边界", "74/70 的比值 1.057 落在 tolerance 内，副本数不变", "这一行 `return current` 的作用，可对照上方输出逐项核对。", "这一行 `want = math.ceil(current * ratio)` 的作用，可对照上方输出逐项核对。", "这一行 `return max(min_r, min(max_r, want))` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `def rolling(replicas, max_surge, max_unavailable):` 的作用，可对照上方输出逐项核对。", "这一行 `return replicas + max_surge, replicas - max_unavaila` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `print(&#39;hpa_50_of_70&#39;, desired_replicas(4, 50, 70))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;hpa_140_of_70&#39;, desired_replicas(4, 140, 70))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;hpa_74_of_70&#39;, desired_replicas(4, 74, 70))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;rolling_4_1_1&#39;, rolling(4, 1, 1))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;rolling_8_2_1&#39;, rolling(8, 2, 1))` 的作用，可对照上方输出逐项核对。"]' title='扩展示例逐行讲解' />


### maxSurge 与 maxUnavailable 的阶段计数

把一次滚动更新按阶段展开，4 副本、`maxSurge=1`、`maxUnavailable=1`：控制器先创建新 RS 的 1 个 Pod（总数 5），等它 Ready 后把旧 RS 缩到 3（总数 4，可用 3 不小于 4-1=3），如此交替直到新 RS 4 个。

任意时刻总 Pod 不超过 replicas+`maxSurge=5`、可用 Pod 不少于replicas-`maxUnavailable=3`，这两个不等式就是滚动策略的硬边界。

若 maxSurge 与 maxUnavailable 都设 25%，8 副本时上限 10、下限 6；控制器对百分比向上取整 surge、向下取整 unavailable，8 乘 0.25 恰为 2 与 2 没有歧义，换成 7 副本就变成 2 与 1。

容易踩坑的两点：`maxSurge=0` 且 `maxUnavailable=0` 会被 API 拒绝；maxUnavailable 等于 replicas 时控制器可能一次删光旧 Pod，可用数掉到 0。

还有一层与 Python 强相关的时序：Pod 删除时 kubelet 先发 `SIGTERM`，terminationGracePeriodSeconds 默认 30s，但 endpoint 从 Service 摘除是异步传播（kube-proxy、Ingress、CoreDNS 各有缓存），旧 Pod 已收到 `SIGTERM` 而摘除未生效时仍有新流量进入，于是出现 502。

preStop hook 先 sleep 5 到 10 秒就是给这段传播留窗口，配合 readiness 立刻失败与 drain 在途请求，才能把「删除一个 Pod」做成无损操作。


### 稳定窗口与 tolerance 如何抑制副本抖动

<Term word='期望副本公式' text='desiredReplicas = ceil(currentReplicas 乘 当前指标 / 目标指标)，比值落在 1 加减 0.1 内不动作；缩容叠加默认 300s 稳定窗口取历史建议最大值，扩容受 scaleUp 速率策略限制。源码在 horizontal.go 的 computeReplicasForMetrics。' />


### 冷启动滞后期需要预留多少容量

<Quiz no='110-1' q='某服务镜像 1.1GB、冷启动两分钟，HPA 按 CPU 目标 70% 扩容，高峰仍先超时后扩容，最准确的解释是？' :options='["从指标越限到新 Pod Ready 有同步周期、调度与冷启动延迟，容量缺口等于流量增速乘这段延迟，desiredReplicas 算得再对也晚于超时", "HPA 的 tolerance=0.1 把扩容完全屏蔽掉了", "CPU 指标不能用于 HPA，必须换成内存指标才行", "maxSurge 设置太小导致扩容动作失败"]' answer="0" explain='HPA 是周期性反馈控制，存在同步、调度与冷启动的滞后；镜像体积直接决定 T_cold。修复是瘦身镜像、设 minReplicas 预留 buffer、或用并发数与队列长度等更前置的指标提前扩，而不是调 tolerance。' />


## cgroup v2 的 memory.max 与 OOMKill 不可捕获

一个 FastAPI 服务设 memory `limit=512Mi`，压测均值 RSS 380Mi，运维按均值设成 480Mi。上线后每晚批量导入时段 Pod 反复被 OOMKill，重启后立刻预热又撞上下一批。

cgroup v2 的账本解释了原因：容器上限是 `memory.max`=480Mi，内核统计的是整个 cgroup 的 `memory.current`（含页缓存、内核栈、所有线程栈），不是 Python 进程看到的堆；CPython 的 pymalloc arena 释放后留在 usable_arenas 链表不归还 OS，dict 过度分配、导入缓存与 C 扩展的原生 malloc 都不经过 Python 分配器，tracemalloc 只看得到一部分。

导入让 RSS 冲到 520Mi，内核 OOM Killer 直接发 `SIGKILL`（信号 9，无法捕获、无 finally、无优雅退出）。修复是按压测 p99 RSS 加三成余量设 limits、requests 略低于 limits、暴露 RSS 指标并配重启次数告警。下面复现「均值安全、p99 超限」的判定。

```python
def oom_risk(samples_mi, limit_mi, headroom=0.3):
    ordered = sorted(samples_mi)
    avg = sum(samples_mi) / len(samples_mi)
    p99 = ordered[int(0.99 * (len(ordered) - 1))]
    recommended = round(p99 * (1 + headroom))
    return round(avg, 1), p99, recommended, limit_mi < recommended

samples = [370, 375, 380, 382, 385, 390, 410, 460, 500, 520]
for limit in (480, 620, 680):
    print('limit', limit, 'avg/p99/recommend/risky', oom_risk(samples, limit))
```


## 练习、选择题与速记

<Exercise title='基础：换算 K8s 资源单位' task='写函数把 250m 换算成核、把 512Mi 换算成字节，并说明 CPU 超限与内存超限分别是什么后果。' solution='def cores(m):\n    return m / 1000\ndef mib(mi):\n    return mi * 1024 * 1024\nprint(cores(250), mib(512))' explain='500m 是 0.5 核，1 Mi 是 2^20 字节。CPU 超限被 CFS 限流延迟上升，内存超限由内核 OOMKill 直接杀容器且不可捕获。' />

<Exercise title='进阶：给 drain 加超时与在途计数' task='实现 drain(timeout)，在规定时间内等待在途请求归零，超时返回剩余数量，并解释为什么清理必须限时。' solution='import time\ndef drain(count, timeout):\n    end = time.monotonic() + timeout\n    while count() &gt; 0 and time.monotonic() &lt; end:\n        time.sleep(0.01)\n    return count()\nn = [3]\nprint(drain(lambda: n[0], 0.05))' explain='terminationGracePeriodSeconds 到点 kubelet 会发 SIGKILL，清理段若不限时会被硬杀，连接与缓冲来不及刷盘；超时后应记录剩余在途数供排障。' />

<Quiz no='110-2' q='某 Python Pod 高峰期反复被 OOMKill，最可能的原因是？' :options='["memory limit 未留足余量，而 pymalloc arena 与 C 扩展原生内存使 p99 RSS 偏高", "CPU limit 设置过小导致限流", "readinessProbe 配错了路径", "镜像层数太多"]' answer="0" explain='CPU 超限只限流不杀进程；RSS 高于 Python 对象统计且 arena 不立刻归还 OS，limit 贴着均值就会在 p99 被内核 OOMKill。' />

<Quiz no='110-3' q='关于 livenessProbe 与 readinessProbe，正确的是？' :options='["liveness 失败重启容器，readiness 失败仅摘除 endpoints，前者不应强依赖数据库", "两者失败都重启容器", "readiness 应强依赖所有下游以便快速摘除", "liveness 应检查数据库连通性"]' answer="0" explain='liveness 失败触发重启，只该检测进程自身不可恢复状态；把数据库抖动接进存活或就绪，会让全部实例同时失效，放大故障。' />

<Quiz no='110-4' q='删除 Pod 时 SIGTERM 处理，下面哪项是必须的？' :options='["置停止标志、让 readiness 失败、drain 在途请求，并在宽限期内退出", "立即 os._exit(0) 最快释放", "忽略 SIGTERM 等 SIGKILL", "只打印日志不做清理"]' answer="0" explain='SIGTERM 后先停止接新流量再处理在途请求，超过 terminationGracePeriodSeconds 会被 SIGKILL；立即退出会截断在途请求产生 502。' />

<Predict no='110-5' q='注册了 SIGTERM handler 后给自己发 SIGTERM，stopping 标志会怎样？' :options='["变为 True，drain 后在途请求清零", "保持 False，信号被忽略", "进程直接退出，无输出"]' answer='0' output='stopping_after True，inflight_after_drain 0' explain='signal.signal 注册的处理器在字节码检查点执行，把 stopping 置 True；主循环据此停止接收新请求，drain 把 inflight 递减到 0 后安全退出。' />

<KnowledgeCard :points='["每条 `RUN` / `COPY` / `ADD` 生成一层，先装依赖后拷源码；多阶段用 `python:3.13-slim` + `--no-cache-dir` 瘦身", "非 root 运行 + chown，`readOnlyRootFilesystem` 时把临时写入指向 emptyDir 挂载的 /tmp", "`resources.requests` 管调度、`limits` 管上限；1 Mi 是 2^20 字节，注意 M / Mi 十进制与二进制差异", "CPU 超限只 throttle，内存超限触发 `SIGKILL`；CPython 的 `pymalloc` 与 C 扩展让 RSS 高于 `tracemalloc`", "`startupProbe` / `livenessProbe` / `readinessProbe` 语义分开，就绪别强依赖数据库；`terminationGracePeriodSeconds` 默认 30 秒", "`SIGTERM` 置 stopping、readiness 转失败、drain 在途、关连接池；preStop 留摘除传播窗口，清理段必须限时"]' :pitfalls='["Dockerfile 先 COPY 全部源码再 pip install", "容器不设 memory limit 或 limit 贴着压测均值", "把就绪探针写成强依赖数据库，且不做 SIGTERM 处理", "不设内存限制，CPython 的缓存与第三方库会让容器反复被 OOMKill；探针写成强依赖数据库则一抖动就全量重启"]' summary='Python 镜像最常见的问题是编译依赖与运行依赖混在一层，镜像动辄 1GB，拉取时间直接决定扩缩容速度' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 每条 `RUN` / `COPY` / `ADD` 生成一层，先装依赖后拷源码；多阶段用 `python:3.13-slim` + `--no-cache-dir` 瘦身 | 建立直觉 |
| 非 root 运行 + chown，`readOnlyRootFilesystem` 时把临时写入指向 emptyDir 挂载的 /tmp | 跑通示例 |
| `resources.requests` 管调度、`limits` 管上限；1 Mi 是 2^20 字节，注意 M / Mi 十进制与二进制差异 | 深入边界 |
| CPU 超限只 throttle，内存超限触发 `SIGKILL`；CPython 的 `pymalloc` 与 C 扩展让 RSS 高于 `tracemalloc` | 工程落地 |
| `startupProbe` / `livenessProbe` / `readinessProbe` 语义分开，就绪别强依赖数据库；`terminationGracePeriodSeconds` 默认 30 秒 | 随堂检测 |
| `SIGTERM` 置 stopping、readiness 转失败、drain 在途、关连接池；preStop 留摘除传播窗口，清理段必须限时 | 复盘 |

1. 每条 `RUN` / `COPY` / `ADD` 生成一层，先装依赖后拷源码；多阶段用 `python:3.13-slim` + `--no-cache-dir` 瘦身

2. 非 root 运行 + chown，`readOnlyRootFilesystem` 时把临时写入指向 emptyDir 挂载的 /tmp

3. `resources.requests` 管调度、`limits` 管上限；1 Mi 是 2^20 字节，注意 M / Mi 十进制与二进制差异

[下一讲：GitOps、灰度发布与可观测平台](/distributed/gitops)

<FillBlank no='110-6' tpl='___ signal, os' :answers='["import"]' hint='回想本讲关于 镜像分层与多阶段构建 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 镜像分层、多阶段构建与瘦身 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/110-docker-k8s.py`

```bash
python3 examples/lessons/110-docker-k8s.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/110-docker-k8s.py) · [全部示例代码索引](/examples/)
