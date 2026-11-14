---
title: 第 120 讲 · 架构设计：领域分层、演进与重构
description: 为长期演进的系统做结构决策
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='50 分钟' goal='为长期演进的系统做结构决策' prereq='第 119 讲 · 极致优化：从剖析到 C 扩展的十倍案例' />

# 第 120 讲 · 架构设计：领域分层、演进与重构

上一讲把热点代码压到极致，盯的是单个函数还能快多少；可代码再快，改一次促销折扣仍要动六个文件。本讲把视角抬到长期系统的结构决策：让最常变的部分留在最小边界里，而不是画更多方框。

想象一个跑了三年的电商单体，定价函数直连数据库，谁都不敢单独改；拆成服务后一次下单要串几次远程调用，一个超时就留下扣了款没占库存的半成品。我们先用提交历史把「哪些文件总一起改」量成边界，再借依赖倒置与端口适配器让领域层不认识存储，最后谈拆分的判据与渐进式重构。需要你熟悉函数、类与模块导入；学完能用窄接口和行为保持测试，给重构留条可回退的路。


## 改一次折扣要动六个文件

一个跑了三年的电商单体，改一次促销折扣要动六个文件：定价函数里直接 import 了 pymysql 连接、Redis 客户端和下单模块的常量，谁都不敢单独改。团队决定拆微服务，把定价、库存、订单各拆成独立进程，结果创建一笔订单要串起四次 RPC，库存服务一次 800 毫秒超时就留下「已扣款、未占库存」的半成品，回滚要人工补单。

两种朴素解法都失败了：按技术职责分 controller、service、dao 三层，业务一变化照样横切多层；按「一个服务一个库」提前拆分，则把一次进程内函数调用放大成跨网络的分布式故障。真正的判据是变化方向——把因同一理由一起改动的代码圈进同一个边界，让依赖朝向稳定侧，而不是画更多方框。

本讲把领域分层、依赖倒置、契约与渐进式重构成能验证的结构。

<Callout type="warn" title='先看一个真实会出错的写法' text='领域层 import pymysql/redis，换个存储要改几十处调用点：高层策略直接依赖低层实现，违反依赖倒置；测试必须连真实库' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段十一 · 资深进阶与源码 |
| 前置 | 第 119 讲 · 极致优化：从剖析到 C 扩展的十倍案例 |
| 难度 / 建议时长 | ★★★★★ · 50 分钟 |
| 本讲新增 | 变化方向与边界、依赖倒置与端口适配器、模块化单体到服务拆分 |
| 一句话目标 | 为长期演进的系统做结构决策 |
| 为下一讲铺垫 | 资深能力图谱、技术选型与持续精进 |


## 变化方向与边界：用提交历史把耦合量化

Robert C. Martin 的稳定依赖原则（SDP）与共同闭包原则（CCP）给的是可计算判据，不是口号。CCP 说：会因同一原因、在同一时间改动的类应聚在同一组件；把过去半年每次提交里一起被修改的文件对做共现统计，共现频率高的文件就是事实上的内聚边界，若它们散落在四个包里，说明边界画错了。

SDP 说依赖方向要指向更稳定的组件，用不稳定性 `I = Ce / (Ce + Ca)` 度量：Ce 是该组件向外依赖的类数（扇出），Ca 是依赖它的类数（扇入），I 越接近 0 越稳定，越难被改动、也越不该依赖别人。

分层架构按技术职责切，一次「VIP 折扣」需求要同时改 controller 的参数校验、service 的规则、dao 的字段，改动扇出常大于三；领域分层按业务能力切（定价、库存、结算），同一需求只落在定价边界内。

三个可观测的失效信号：改一个需求平均触及超过三个包、单测必须启动真实数据库才能跑、以及 PR 平均改动文件数逐月上升。把这三项打进 CI 报表，技术债才有具体数字，而不是评审会上的形容词。

<Callout type="tip" title='核心心智模型' text='Robert C. Martin 的稳定依赖原则（SDP）与共同闭包原则（CCP）给的是可计算判据，不是口号。CCP 说：会因同一原因、在同一时间改动的类应聚在同一组件；把过去半年每次提交里一起被修改的文件对做共现统计，共现频率高的文件就是事实上的内聚边界，若它们散落在四个包里，说明边界画错了。SD…' />

<ConceptDiagram type='flow3' title='第 120 讲 · 变化方向与边界：用提交历史把耦合量化出来' labels='变化方向与边界：用提交历史把耦合量化出来|依赖倒置与端口适配器：让领域层不认识基础设施|模块化单体到服务拆分：判据、契约与渐进式重构' caption='为长期演进的系统做结构决策' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 依赖倒置与端口适配器：让领域层不认识基础设施

依赖倒置原则（DIP）要求高层策略不依赖低层细节，二者都依赖抽象。

Python 里最轻量的抽象是 `typing.Protocol`（PEP 544，3.8 起）：端口由领域层定义为结构化子类型，方法体写 `...`，实现类无需继承，只要方法名与签名匹配即被视为满足协议，这叫结构化子类型。

加上 `@runtime_checkable`（同样 3.8 起）后 `isinstance(obj, Port)` 才可用，但它只检查成员是否存在、不校验类型注解与签名；

3.12 起非方法成员的运行时检查才被放宽，早期版本对数据协议会抛 `TypeError`。

需要强制实现时用 `abc.ABC` 配 `@abstractmethod`，未实现的方法在实例化阶段就报 TypeError。

领域服务通过构造函数接收端口实例（构造注入），装配工作集中到 composition root：换 MySQL 到 Postgres 只替换一个适配器类，领域代码与它的单测一行不动。单元测试注入内存 Fake 或 JsonAdapter，不需要 `mock.patch` 深层路径。

失效信号很具体：领域模块的顶层出现第三方 import、测试文件里满是 `mock.patch('pymysql.connect')`、以及换存储时要改超过一处调用点。

```python
import json
from typing import Protocol, runtime_checkable

@runtime_checkable
class RatePort(Protocol):
    def get(self, key: str) -> float: ...
    def put(self, key: str, value: float) -> None: ...

class MemoryAdapter:
    def __init__(self):
        self._d = {}
    def get(self, key):
        return self._d.get(key, 1.0)
    def put(self, key, value):
        self._d[key] = value

class JsonAdapter:
    def __init__(self):
        self._blob = '{}'
    def get(self, key):
        return json.loads(self._blob).get(key, 1.0)
    def put(self, key, value):
        d = json.loads(self._blob)
        d[key] = value
        self._blob = json.dumps(d)

class Pricing:
    def __init__(self, port: RatePort):
        self.port = port
    def total(self, base, key):
        return round(base * self.port.get(key), 2)

def contract(port, label):
    assert isinstance(port, RatePort), label
    port.put('vip', 0.8)
    svc = Pricing(port)
    assert svc.total(100.0, 'vip') == 80.0, label
    assert svc.total(100.0, 'guest') == 100.0, label
    return label + ' pass'

for label, port in [('memory', MemoryAdapter()), ('json', JsonAdapter())]:
    print(label, isinstance(port, RatePort), contract(port, label))
print('annotation', list(Pricing.__init__.__annotations__))
```

<OutputBox title='主示例运行结果' output='memory True memory pass\njson True json pass\nannotation [&#39;port&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import json\nfrom typing import Protocol, runtime_checkable\n\n@runtime_checkable\nclass RatePort(Protocol):\n    def get(self, key: str) -&gt; float: ...\n    def put(self, key: str, value: float) -&gt; None: ...\n\nclass MemoryAdapter:\n    def __init__(self):\n        self._d = {}\n    def get(self, key):\n        return self._d.get(key, 1.0)\n    def put(self, key, value):\n        self._d[key] = value\n\nclass JsonAdapter:\n    def __init__(self):\n        self._blob = &#39;{}&#39;\n    def get(self, key):\n        return json.loads(self._blob).get(key, 1.0)\n    def put(self, key, value):\n        d = json.loads(self._blob)\n        d[key] = value\n        self._blob = json.dumps(d)\n\nclass Pricing:\n    def __init__(self, port: RatePort):\n        self.port = port\n    def total(self, base, key):\n        return round(base * self.port.get(key), 2)\n\ndef contract(port, label):\n    assert isinstance(port, RatePort), label\n    port.put(&#39;vip&#39;, 0.8)\n    svc = Pricing(port)\n    assert svc.total(100.0, &#39;vip&#39;) == 80.0, label\n    assert svc.total(100.0, &#39;guest&#39;) == 100.0, label\n    return label + &#39; pass&#39;\n\nfor label, port in [(&#39;memory&#39;, MemoryAdapter()), (&#39;json&#39;, JsonAdapter())]:\n    print(label, isinstance(port, RatePort), contract(port, label))\nprint(&#39;annotation&#39;, list(Pricing.__init__.__annotations__))' :notes='["导入 json，JsonAdapter 用它把状态序列化成字符串模拟文件持久化", "从 typing 取 Protocol 与 runtime_checkable，构造运行时可检查的端口协议", "空行，只用于分隔逻辑块，不影响执行结果。", "@runtime_checkable 让 isinstance(obj, RatePort) 可用，否则协议只能静态检查", "领域层定义 RatePort：只声明 get/put，不依赖任何具体存储", "get 契约：接收键返回浮点数，方法体用省略号表示为纯声明", "put 契约：写入键值对返回 None，实现方必须同名同参", "空行，只用于分隔逻辑块，不影响执行结果。", "内存适配器，不继承 RatePort，靠结构化子类型满足协议", "构造时建一个空字典作为存储", "把字典挂到实例上", "get 缺省返回 1.0，保证未命中键时定价不被打折", "用 dict.get 取值并给缺省，缺省值本身属于契约的一部分", "put 直接写字典", "写操作只有一条赋值，体现适配器可以极薄", "空行，只用于分隔逻辑块，不影响执行结果。", "第二个适配器：同样两个方法，但用 JSON 字符串存储，证明实现可替换", "初始状态是空对象字面量", "把持久化介质表示成一个字符串字段", "get 先反序列化再取值，缺省同样是 1.0", "json.loads 把字符串还原成字典后再查键", "put 需要读出、修改、写回三步", "把当前状态解析成字典", "写入新键值", "重新序列化为字符串，模拟落盘后的持久化介质", "空行，只用于分隔逻辑块，不影响执行结果。", "领域服务：只认识 RatePort，不认识 dict 也不认识 json", "构造注入端口，参数标注为协议类型而非具体类", "把端口保存为实例属性", "total 的业务规则：基准价乘折扣率后保留两位小数", "调用端口的 get，领域逻辑与存储解耦", "空行，只用于分隔逻辑块，不影响执行结果。", "契约测试：对任意实现跑同一组断言，锁住跨实现的行为不变", "运行时校验实现满足协议，缺方法会立刻暴露", "写入 VIP 折扣 0.8", "用待测端口装配领域服务", "断言命中 VIP 时 100 乘 0.8 等于 80.0", "断言未命中键时走缺省 1.0，结果仍是 100.0", "全部通过返回标签加 pass 字符串", "空行，只用于分隔逻辑块，不影响执行结果。", "遍历两个实现，打印协议检查与契约结果", "同一组用例分别作用于内存版与 JSON 版，输出应一致", "打印构造参数的注解名，证明依赖被标注为抽象端口"]' title='第 120 讲 · 架构设计：领域分层、演进与重构' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### Protocol 与 ABC：结构化子类型能检查到什么

```python
class CompliantStore:
    def get(self, key):
        return 0.9

class ViolatingStore:
    def get(self, key):
        return 0.0

def verify(store):
    v = store.get('x')
    if v != 0.9:
        return 'contract violated: got ' + str(v)
    return 'pass'

print('compliant', verify(CompliantStore()))
print('violating', verify(ViolatingStore()))
```

<OutputBox title='对照写法：先自己猜，再点开' output='compliant pass\nviolating contract violated: got 0.0' guess="true" />

```python
def pure_domain(base, rate):
    return round(base * rate, 2)

def coupled(base):
    import json
    import sqlite3
    return round(base * 1.0, 2)

print('domain names', sorted(pure_domain.__code__.co_names))
print('coupled names', sorted(coupled.__code__.co_names))
print('fan-out delta', len(set(coupled.__code__.co_names)) - len(set(pure_domain.__code__.co_names)))
```

<OutputBox title='原理验证' output='domain names [&#39;round&#39;]\ncoupled names [&#39;json&#39;, &#39;round&#39;, &#39;sqlite3&#39;]\nfan-out delta 2' />


## 架构风格选型：按故障边界与团队结构决定

拆服务的触发条件是团队规模、独立伸缩、发布节奏差异与故障隔离，不是代码行数；康威定律提醒组织沟通结构会复刻进系统边界，边界没理清时拆得越碎，分布式故障越多。

跨边界行为靠消费者驱动契约测试（consumer-driven contract，Pact 的思想）锁定：消费方把期望的请求与响应写成一份契约文件，提供方在自己的 CI 里回放，两侧即可独立发布而不互相等。接口版本用 semver：`MAJOR` 用于不兼容变更、`MINOR` 向后兼容新增、`PATCH` 修 bug；

不兼容变更必须升 `MAJOR` 并保留 `/v1` 与 `/v2` 并存窗口。演进用绞杀者模式（strangler fig）：在旧系统前加一层门面路由，新实现按路由逐条接管，旧路径保留到流量归零，配合特性开关与影子流量（shadow traffic）双跑比对结果。

重构前先补行为保持测试（characterization test，也叫 Golden Master）：把旧实现的一组输入与输出录成黄金样本，重构后逐字节回放必须一致，这是「行为不变」的唯一证据。技术债用圈复杂度、改动耦合率、测试覆盖率、构建时长与平均恢复时间 `MTTR` 五个量跟踪；

没有契约测试就拆服务、大爆炸式重写、没有回退开关，是三种最典型的失败模式。

**架构风格选型：按故障边界与团队结构决定**

| 风格 | 部署单元 | 跨边界调用 | 数据一致性 | 适用信号 |
| --- | --- | --- | --- | --- |
| 分层架构 controller/service/dao | 单体进程 | 进程内函数调用 | 单库本地事务 | 业务变化横切多层是主要痛点 |
| 端口适配器（六边形） | 单体进程 | 经端口的进程内调用 | 单库本地事务 | 需要频繁替换存储/外部依赖且要求可单测 |
| 模块化单体 | 单体进程 + 强模块边界 | 模块接口 + 契约测试 | 单库，按 schema 隔离 | 团队中小、发布节奏一致、尚未需要独立伸缩 |
| 微服务 | 多进程多机 | 网络 RPC，存在部分失败 | 最终一致 / Saga 补偿 | 团队大、模块需独立伸缩与独立发布 |

<FlowTimeline :steps='[{"title": "变化方向与边界：用提交历史把耦合量化出来", "desc": "Robert C. Martin 的稳定依赖原则（SDP）与共同闭包原则（CCP）给…", "tone": "blue"}, {"title": "依赖倒置与端口适配器：让领域层不认识基础设施", "desc": "依赖倒置原则（DIP）要求高层策略不依赖低层细节，二者都依赖抽象。Python 里最…", "tone": "purple"}, {"title": "模块化单体到服务拆分：判据、契约与渐进式重构", "desc": "拆服务的触发条件是团队规模、独立伸缩、发布节奏差异与故障隔离，不是代码行数；康威定律…", "tone": "orange"}, {"title": "工程落地", "desc": "模块化单体：装配根 + 契约测试 + 可替换适配器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 拆服务的代价：一次进程内调用变成四次 RPC

<Callout type="warn" title='本讲最容易踩的坑' text='领域层 import pymysql/redis，换个存储要改几十处调用点：高层策略直接依赖低层实现，违反依赖倒置；测试必须连真实库' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：领域层 import pymysql/red…", "body": "高层策略直接依赖低层实现，违反依赖倒置；测试必须连真实库", "tip": "领域层定义 Protocol 端口，实现放适配器层，构造注入；单测用内存 Fake，装配集中在 composition root"}, {"title": "第 2 步：没有清晰边界就按「一个服务一个库」提前拆微服…", "body": "把进程内函数调用换成 RPC，引入网络分区、部分失败与分布式事务", "tip": "先做模块化单体 + 契约测试守住边界，按团队规模、伸缩与发布节奏的真实痛点再拆"}, {"title": "第 3 步：大爆炸式重写，上线后行为漂移且无法回退", "body": "没有行为保持测试，也没有渐进替换与开关，旧行为无法对照", "tip": "重构前录 Golden Master 黄金样本，绞杀者逐路由接管 + 特性开关，回放不一致即回滚"}]' />


## 契约测试、semver 与 /v1 /v2 并存窗口

<Compare :panels='[{"label": "主示例", "code": "import json\nfrom typing import Protocol, runtime_checkable\n\n@runtime_checkable\nclass RatePort(Protocol):\n    def get(self, key: str) -&gt; float: ...\n    def put(self, key: str, value: float) -&gt; None: ...\n\nclass MemoryAdapter:\n    def __init__(self):\n        self._d = {}\n    def get(self, key):\n        return self._d.get(key, 1.0)\n    def put(self, key, value):\n        self._d[key] = value\n\nclass JsonAdapter:\n    def __init__(self):\n        self._blob = &#39;{}&#39;\n    def get(self, key):\n        return json.loads(self._blob).get(key, 1.0)\n    def put(self, key, value):\n        d = json.loads(self._blob)\n        d[key] = value\n        self._blob = json.dumps(d)\n\nclass Pricing:\n    def __init__(self, port: RatePort):\n        self.port = port\n    def total(self, base, key):\n        return round(base * self.port.get(key), 2)\n\ndef contract(port, label):\n    assert isinstance(port, RatePort), label\n    port.put(&#39;vip&#39;, 0.8)\n    svc = Pricing(port)\n    assert svc.total(100.0, &#39;vip&#39;) == 80.0, label\n    assert svc.total(100.0, &#39;guest&#39;) == 100.0, label\n    return label + &#39; pass&#39;\n\nfor label, port in [(&#39;memory&#39;, MemoryAdapter()), (&#39;json&#39;, JsonAdapter())]:\n    print(label, isinstance(port, RatePort), contract(port, label))\nprint(&#39;annotation&#39;, list(Pricing.__init__.__annotations__))", "note": "变化方向与边界：用提交历史把耦合量化出来"}, {"label": "对照 / 进阶", "code": "class CompliantStore:\n    def get(self, key):\n        return 0.9\n\nclass ViolatingStore:\n    def get(self, key):\n        return 0.0\n\ndef verify(store):\n    v = store.get(&#39;x&#39;)\n    if v != 0.9:\n        return &#39;contract violated: got &#39; + str(v)\n    return &#39;pass&#39;\n\nprint(&#39;compliant&#39;, verify(CompliantStore()))\nprint(&#39;violating&#39;, verify(ViolatingStore()))", "note": "依赖倒置与端口适配器：让领域层不认识基础设施"}]' title='两种写法对照' note='差异集中在 变化方向与边界；先看输出，再找背后的规则。' />

<CheckList id='P120b' title='上线前自检' :items='["能复现并解释「领域层 import pymysql/redis，换个存储要…」", "能复现并解释「没有清晰边界就按「一个服务一个库」提前拆微服务」", "能复现并解释「大爆炸式重写，上线后行为漂移且无法回退」", "能用一条命令验证 变化方向与边界", "关键路径有自动化测试与失败分支"]' />


## 绞杀者模式、影子流量与技术决策的回退路径

**重构手法、触发信号与回退手段**

| 手法 | 触发信号 | 回退手段 |
| --- | --- | --- |
| 绞杀者模式（门面路由逐条接管） | 旧模块无法停机但需逐步替换 | 路由切回旧实现，旧路径保留到流量归零 |
| 特性开关 + 影子流量 | 新旧行为需要在真实流量下比对 | 关闭开关即恢复旧路径 |
| 行为保持测试（Golden Master） | 重构前缺少应有的行为基线 | 回放不一致即判定重构引入回归 |
| 消费者驱动契约测试 | 两侧发布节奏不同、需独立上线 | 契约文件版本化，旧契约并行保留 |

<ArchBlueprint title='第 120 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "变化方向与边界：用提交历史把耦合量化出来", "protocol": "调用 / 请求", "items": [{"label": "变化方向与边界：用提交历…", "sub": "输入与前置", "detail": "Robert C. Martin 的稳定依赖原则（SDP）与共同闭包原则（CCP）给的是可计算判据，不是口号。CCP 说：会因同一原因、在同一时间改动的类应聚在同一组件；把过去半年每次提交里一起被修改的文件对做共现统计，共现频率高的文件就是事实上的内聚边界，若它们散落在四个包里，说明边界画错了。SD…", "tone": "blue"}]}, {"name": "核心规则", "note": "依赖倒置与端口适配器：让领域层不认识基础设施", "protocol": "语言 / 运行时协议", "items": [{"label": "依赖倒置与端口适配器：让…", "sub": "状态与边界", "detail": "依赖倒置原则（DIP）要求高层策略不依赖低层细节，二者都依赖抽象。Python 里最轻量的抽象是 `typing.Protocol`（PEP 544，3.8 起）：端口由领域层定义为结构化子类型，方法体写 `...`，实现类无需继承，只要方法名与签名匹配即被视为满足协议，这叫结构化子类型。加上…", "tone": "purple"}]}, {"name": "落地与收尾", "note": "模块化单体到服务拆分：判据、契约与渐进式重构", "items": [{"label": "模块化单体到服务拆分：判…", "sub": "工程处理", "detail": "拆服务的触发条件是团队规模、独立伸缩、发布节奏差异与故障隔离，不是代码行数；康威定律提醒组织沟通结构会复刻进系统边界，边界没理清时拆得越碎，分布式故障越多。跨边界行为靠消费者驱动契约测试（consumer-driven contract，Pact 的思想）锁定：消费方把期望的请求与响应写成一份契约文…", "tone": "green"}]}]' />


## 依赖倒置的运行期多态分派

依赖倒置的底层机制，是把「编译期或导入期的具体依赖」换成「运行期的多态分派」。

Protocol 在类创建时由 typing 的元类收集成员名构成 `_ProtocolMeta`，isinstance 走的是 `__instancecheck__` 的运行时成员探测，因此不要求实现类继承任何基类，只需在 MRO 或实例字典里能找到同名可调用属性；

这让它既能被静态检查器（mypy）静态使用，也能在 runtime_checkable 下被动态检查。构造函数注入把「谁来 new 具体实现」推迟到 composition root，于是对象图在启动时一次装配完成，运行期领域对象只持有抽象的引用，在 C 级别看就是一次普通的属性查表。

契约测试之所以能替代集成测试守住边界，是因为它把跨组件的隐含假设显式化为可回放的输入输出对；绞杀者模式依赖的则是路由层对请求的分派，本质是策略模式作用在流量入口。拆成微服务后，本地事务变成跨网络的 Saga，CAP 约束下只能用补偿换可用性，这正是「一次函数调用变一次分布式故障」在系统层的根因。

<Term word='变化方向与边界' text='Robert C. Martin 的稳定依赖原则（SDP）与共同闭包原则（CCP）给的是可计算判据，不是口号。CCP 说：会因同一原因、在同一时间改动的类应聚在同一组件；把过去半年每次提交里一起被修改的文件对做共现统计，共现频率高的文件就是事实上的内聚边界，若它们散落在四个包里，说明边界画错了。SDP 说依赖方向要指向…' />

<Term word='依赖倒置与端口适配器' text='依赖倒置原则（DIP）要求高层策略不依赖低层细节，二者都依赖抽象。Python 里最轻量的抽象是 `typing.Protocol`（PEP 544，3.8 起）：端口由领域层定义为结构化子类型，方法体写 `...`，实现类无需继承，只要方法名与签名匹配即被视为满足协议，这叫结构化子类型。加上…' />


## 技术债的量化指标与行为保持测试

**技术债的量化指标**

| 指标 | 测量方式 | 恶化阈值参考 |
| --- | --- | --- |
| 改动扇出 | 单个需求平均触及的包/文件数 | 持续大于 3 说明边界未圈住变化 |
| 不稳定性 I = Ce/(Ce+Ca) | 统计组件的扇入 Ca 与扇出 Ce | 核心领域层 I 应接近 0 |
| 圈复杂度 | radon / 静态分析统计分支数 | 单函数大于 10 需拆分 |
| 测试覆盖率与构建时长 | coverage.py、CI 计时 | 覆盖率下降或构建时长翻倍即还债 |
| 平均恢复时间 MTTR | 从告警到恢复的时长中位数 | 拆服务后上升说明分布式复杂度失控 |


## 模块化单体：装配根 + 可替换适配器

一个订单服务要同时支持本地开发与云端持久化：本地用内存折扣表便于调试，云端用 `JSON` 文件适配器，但定价规则必须完全一致。做法是领域层只定义 RatePort 协议与 PricingService，两个适配器各实现 get 与 put；composition root 按配置名装配具体实现；

一组 `contract_suite` 对两个实现跑同样断言，任何适配器违约都会被拦在合并前。这样未来把 `JSON` 换成 PostgreSQL 时，只新增一个适配器、在映射表里登记，领域代码与契约测试一行不改。真实项目还会给适配器加连接池、超时、指标埋点，并把契约文件随版本库提交，让跨团队发布不必互相等待。

下面片段可直接运行，重点看装配根如何把变化挡在领域层之外。

```python
import json
from typing import Protocol

class RatePort(Protocol):
    def get(self, key: str) -> float: ...
    def put(self, key: str, value: float) -> None: ...

class MemoryRate:
    def __init__(self):
        self.d = {}
    def get(self, key):
        return self.d.get(key, 1.0)
    def put(self, key, value):
        self.d[key] = value

class JsonRate:
    def __init__(self):
        self.blob = '{}'
    def get(self, key):
        return json.loads(self.blob).get(key, 1.0)
    def put(self, key, value):
        d = json.loads(self.blob)
        d[key] = value
        self.blob = json.dumps(d)

class PricingService:
    def __init__(self, rates: RatePort):
        self.rates = rates
    def quote(self, base, tier):
        return round(base * self.rates.get(tier), 2)

REGISTRY = {'memory': MemoryRate, 'json': JsonRate}

def contract_suite(make):
    svc = PricingService(make())
    svc.rates.put('vip', 0.8)
    assert svc.quote(100.0, 'vip') == 80.0
    assert svc.quote(100.0, 'new') == 100.0
    return type(svc.rates).__name__

def compose(impl):
    return PricingService(REGISTRY[impl]())

for name in REGISTRY:
    print(name, contract_suite(REGISTRY[name]))
print('quote', compose('json').quote(200.0, 'vip'))
```

<Callout type="idea" title='落地提示' text='从模块化单体起步，用契约测试守住边界，按真实痛点（团队、伸缩、发布节奏）再拆；重构以行为保持测试为前提' />

```bash
python -c "import dis, sys; print(sys.version.split()[0]); dis.dis(lambda x:x)"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 变化方向与边界 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 领域层 import pymysql/redis，换个存储要改几十处调用点 | 高层策略直接依赖低层实现，违反依赖倒置；测试必须连真实库 | 领域层定义 Protocol 端口，实现放适配器层，构造注入；单测用内存 Fake，装配集中在 composition root |
| 没有清晰边界就按「一个服务一个库」提前拆微服务 | 把进程内函数调用换成 RPC，引入网络分区、部分失败与分布式事务 | 先做模块化单体 + 契约测试守住边界，按团队规模、伸缩与发布节奏的真实痛点再拆 |
| 大爆炸式重写，上线后行为漂移且无法回退 | 没有行为保持测试，也没有渐进替换与开关，旧行为无法对照 | 重构前录 Golden Master 黄金样本，绞杀者逐路由接管 + 特性开关，回放不一致即回滚 |


## 练习、自测与一页纸速记

<Exercise title='基础：给协议加运行时检查并捕获违约实现' task='定义一个含 get/put 的 @runtime_checkable Protocol，写一个缺少 put 的类，用 isinstance 验证它不满足协议；再写一个契约函数，对缺省返回值不是 1.0 的实现返回违约信息。' solution='from typing import Protocol, runtime_checkable\n\n@runtime_checkable\nclass P(Protocol):\n    def get(self, k): ...\n    def put(self, k, v): ...\n\nclass Bad:\n    def get(self, k):\n        return 0.0\n\nprint(&#39;missing put&#39;, isinstance(Bad(), P))\nprint(&#39;bad default&#39;, &#39;ok&#39; if Bad().get(&#39;x&#39;) == 1.0 else &#39;violation&#39;)' explain='runtime_checkable 的 isinstance 只查成员名，缺 put 直接判 False；契约还要校验缺省值这类行为假设，单靠 isinstance 不够，两者要叠加。' />

<Exercise title='进阶：用 co_names 量化改动扇出' task='写两个函数：一个只做纯计算，一个在函数体内 import 三个模块并调用全局函数；用 __code__.co_names 统计各自依赖的全局名数量，解释扇出与可测试性的关系。' solution='def pure(x):\n    return round(x * 1.2, 2)\n\ndef coupled(x):\n    import json, sqlite3, socket\n    return round(x * 1.2, 2)\n\nprint(&#39;pure&#39;, sorted(pure.__code__.co_names))\nprint(&#39;coupled&#39;, sorted(coupled.__code__.co_names))\nprint(&#39;delta&#39;, len(set(coupled.__code__.co_names)) - len(set(pure.__code__.co_names)))' explain='co_names 记录函数引用的全局/属性名；coupled 多出三个 import 名，扇出更高、绑定了更多外部模块，替换与单测成本随之上升。这是把技术债变成可测数字的入口。' />

<Quiz no='120-1' q='关于 typing.Protocol 与 @runtime_checkable，哪一项准确？' :options='["实现类无需继承协议，满足结构化子类型即可；isinstance 需加 @runtime_checkable 且只检查成员存在", "实现类必须显式继承 Protocol 子类", "isinstance 会完整校验方法签名与类型注解", "Protocol 从 Python 3.13 才引入"]' answer="0" explain='PEP 544 在 3.8 引入 Protocol；结构化子类型不要求继承。runtime_checkable 让 isinstance 可用，但实现只检查成员名是否存在，不校验签名，数据协议的运行时检查在 3.12 才放宽。' />

<Quiz no='120-2' q='在没有清晰领域边界时提前拆微服务，最可能的后果是？' :options='["把进程内调用放大为跨网络的部分失败与分布式事务，MTTR 上升", "编译速度显著提升", "单测不再需要 mock", "数据库事务自动变成强一致"]' answer="0" explain='拆分引入网络分区、超时与部分失败，本地事务退化为需补偿的最终一致；边界没理清时这些成本没有带来伸缩收益，反而拉长恢复时间。' />

<Predict no='120-3' q='对同一个 Pricing 分别注入 MemoryAdapter 与 JsonAdapter 跑同一组契约用例，最可能的结果是？' :options='["两者都通过，输出 memory pass 与 json pass", "只有 MemoryAdapter 通过，JsonAdapter 因 json 往返丢精度而违约", "两者都失败，因为 isinstance 对 Protocol 恒为 False"]' answer='0' output='memory True memory pass 与 json True json pass' explain='两个适配器都实现了 get/put 且缺省返回 1.0，0.8 经 json.dumps/loads 往返不丢精度，VIP 折扣 80.0 与缺省 100.0 两条断言都成立，契约测试对实现不敏感。' />

<FillBlank no='120-4' tpl='___ json' :answers='["import"]' hint='回想本讲关于 变化方向与边界 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 变化方向与边界：用提交历史把耦合量化出来 的落点。' />

<KnowledgeCard :points='["CCP 按「同一原因一起改」圈边界，SDP 让依赖指向不稳定度 I=Ce/(Ce+Ca) 更低的组件", "typing.Protocol（PEP 544，3.8）是结构化子类型；@runtime_checkable 的 isinstance 只查成员存在、不查签名", "领域层定义端口、适配器层实现、composition root 装配；构造函数注入让单测可用内存 Fake", "跨边界行为用消费者驱动契约测试锁定；不兼容变更升 semver MAJOR 并保留版本并存窗口", "演进用绞杀者模式 + 特性开关 + 影子流量，重构前先补行为保持测试（Golden Master）", "拆服务的触发条件是团队规模、独立伸缩与发布节奏，不是代码行数；拆后本地事务退化为 Saga 补偿"]' :pitfalls='["领域层 import pymysql/redis，换个存储要改几十处调用点", "没有清晰边界就按「一个服务一个库」提前拆微服务", "大爆炸式重写，上线后行为漂移且无法回退", "在没有清晰领域边界时拆微服务，会把一次函数调用变成一次分布式故障"]' summary='架构的核心是让「最常变化的部分」被隔离在最小的边界内，而不是画更多方框' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| CCP 按「同一原因一起改」圈边界，SDP 让依赖指向不稳定度 I=Ce/(Ce+Ca) 更低的组件 | 建立直觉 |
| typing.Protocol（PEP 544，3.8）是结构化子类型；@runtime_checkable 的 isinstance 只查成员存在、不查签名 | 跑通示例 |
| 领域层定义端口、适配器层实现、composition root 装配；构造函数注入让单测可用内存 Fake | 深入边界 |
| 跨边界行为用消费者驱动契约测试锁定；不兼容变更升 semver MAJOR 并保留版本并存窗口 | 工程落地 |
| 演进用绞杀者模式 + 特性开关 + 影子流量，重构前先补行为保持测试（Golden Master） | 随堂检测 |
| 拆服务的触发条件是团队规模、独立伸缩与发布节奏，不是代码行数；拆后本地事务退化为 Saga 补偿 | 复盘 |

1. CCP 按「同一原因一起改」圈边界，SDP 让依赖指向不稳定度 I=Ce/(Ce+Ca) 更低的组件

2. typing.Protocol（PEP 544，3.8）是结构化子类型；@runtime_checkable 的 isinstance 只查成员存在、不查签名

3. 领域层定义端口、适配器层实现、composition root 装配；构造函数注入让单测可用内存 Fake

[下一讲：资深能力图谱、技术选型与持续精进](/advanced/senior-path)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/120-architecture.py`

```bash
python3 examples/lessons/120-architecture.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/120-architecture.py) · [全部示例代码索引](/examples/)
