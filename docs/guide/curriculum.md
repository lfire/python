---
title: 课程总目录（132 讲）
description: 13 个递进阶段、132 讲的完整目录，含难度与建议时长。
---

# 课程总目录

第一次来，建议先花几分钟读[开始之前](/guide/before-you-start)：那里说明了这套教程写给谁、需要什么基础、有三条怎样的学习路线，以及站点里各个交互组件怎么用。已经清楚自己该从哪切入的读者，直接用下面的目录跳转即可。

这是一套从零基础到资深的交互式 Python 教程：**13 个阶段 · 132 讲 · 50 个工程场景**。
阶段顺序按认知负担设计：先能对，再能快；先单进程，再并发；先会写，再会发布；最后才谈架构与源码。每一讲的篇幅也随主题变化，单一概念的讲次短一些，核心机制、源码与贯穿式实战会明显更长。

<Callout type="tip" title="怎么读这份目录" text="每讲都包含可运行示例、逐行拆解、猜输出、填空、随堂测验、动手练习与一页纸速记；难度用 ★ 表示，时长是独立完成阅读与练习的估计值。" />

<ProgressTracker />

## 导学 · 建立地图

> 先看见整张地图：Python 是什么、怎么跑起来、这套教程怎么学

语言定位、环境与工具链、第一行代码、执行模型与学习路线。共 5 讲 · 约 120 分钟。

- **001** [开篇：Python 是什么，为什么值得学](/guide/opening) · ★☆☆☆☆ · 20 分钟
- **002** [环境与工具链：解释器、虚拟环境与编辑器](/guide/setup) · ★☆☆☆☆ · 30 分钟
- **003** [第一行 Python：从源码到字节码再到执行](/guide/hello) · ★☆☆☆☆ · 25 分钟
- **004** [工具链全景：写代码、查问题、验质量](/guide/toolchain) · ★☆☆☆☆ · 25 分钟
- **005** [学习路线：十三个阶段如何递进](/guide/roadmap) · ★☆☆☆☆ · 20 分钟

## 阶段一 · 编程地基

> 不假设任何编程基础，补齐对象、值、类型、流程、异常这些地基

对象模型、变量绑定、数值与字符串、运算符、控制流、IO 与异常。共 11 讲 · 约 320 分钟。

- **006** [一切皆对象：id、type、value 与可变性](/foundation/object-model) · ★☆☆☆☆ · 25 分钟
- **007** [变量是名字绑定：赋值、引用与命名规范](/foundation/variables) · ★☆☆☆☆ · 25 分钟
- **008** [数值体系：int 任意精度、float、Decimal 与 bool](/foundation/numeric) · ★★☆☆☆ · 30 分钟
- **009** [字符串与编码：Unicode、str / bytes 与转义](/foundation/strings) · ★★☆☆☆ · 30 分钟
- **010** [字符串操作：切片、f-string 与常用方法](/foundation/string-ops) · ★☆☆☆☆ · 30 分钟
- **011** [运算符与表达式：优先级、短路与真值](/foundation/operators) · ★★☆☆☆ · 25 分钟
- **012** [分支：if / elif / else 与 match-case](/foundation/control-flow) · ★★☆☆☆ · 25 分钟
- **013** [循环：for / while、range 与循环 else](/foundation/loops) · ★☆☆☆☆ · 30 分钟
- **014** [输入输出与文件初识：print、input、open、with](/foundation/io) · ★☆☆☆☆ · 25 分钟
- **015** [异常：捕获、异常链与自定义异常](/foundation/exceptions) · ★★☆☆☆ · 30 分钟
- **016** [阶段综合：交互式命令行计算器](/foundation/capstone) · ★★☆☆☆ · 45 分钟

## 阶段二 · 容器与序列

> 把 Python 最常用的内置容器用到知其所以然

序列协议、list / tuple / dict / set、推导式、迭代器与生成器。共 11 讲 · 约 325 分钟。

- **017** [序列协议与通用操作](/containers/sequence) · ★★☆☆☆ · 25 分钟
- **018** [list：动态数组、操作与时间复杂度](/containers/list-basics) · ★☆☆☆☆ · 30 分钟
- **019** [list 进阶：切片赋值、排序与常见陷阱](/containers/list-advanced) · ★★☆☆☆ · 30 分钟
- **020** [tuple 与具名元组：不可变性的价值](/containers/tuple) · ★☆☆☆☆ · 25 分钟
- **021** [dict：哈希表、视图与插入顺序](/containers/dict-basics) · ★★☆☆☆ · 30 分钟
- **022** [dict 进阶：默认字典、计数器与合并](/containers/dict-advanced) · ★★☆☆☆ · 25 分钟
- **023** [set / frozenset：哈希、集合运算与去重](/containers/set) · ★☆☆☆☆ · 25 分钟
- **024** [推导式：四种写法与可读性边界](/containers/comprehension) · ★★☆☆☆ · 25 分钟
- **025** [迭代协议：iterable、iterator 与惰性求值](/containers/iterator) · ★★★☆☆ · 30 分钟
- **026** [生成器与 yield：send / throw / close](/containers/generator) · ★★★☆☆ · 35 分钟
- **027** [阶段综合：词频统计与内存版 KV](/containers/capstone) · ★★☆☆☆ · 45 分钟

## 阶段三 · 函数与抽象

> 用函数、装饰器、模块与类型注解搭出可复用的抽象

参数形态、作用域闭包、高阶函数、装饰器、模块包与类型系统。共 10 讲 · 约 325 分钟。

- **028** [函数定义与参数形态](/functions/function-basics) · ★☆☆☆☆ · 30 分钟
- **029** [返回值、None 与多返回值](/functions/returns) · ★☆☆☆☆ · 25 分钟
- **030** [作用域、LEGB 与闭包延迟绑定](/functions/scope) · ★★★☆☆ · 35 分钟
- **031** [高阶函数、lambda 与 map / filter / reduce](/functions/higher-order) · ★★☆☆☆ · 30 分钟
- **032** [装饰器原理与 functools.wraps](/functions/decorator) · ★★★☆☆ · 35 分钟
- **033** [带参装饰器、叠加顺序与类装饰器](/functions/decorator-params) · ★★★☆☆ · 30 分钟
- **034** [偏函数、可调用对象与函数式工具](/functions/partial) · ★★☆☆☆ · 25 分钟
- **035** [模块与包：import 机制与循环导入](/functions/modules) · ★★★☆☆ · 35 分钟
- **036** [类型注解、typing 与渐进式类型](/functions/typing) · ★★★☆☆ · 35 分钟
- **037** [阶段综合：缓存装饰器库与插件注册表](/functions/capstone) · ★★★☆☆ · 45 分钟

## 阶段四 · 面向对象与元编程

> 从会写类到能设计对象协议、描述符与元类驱动的框架

类与实例、MRO、描述符、特殊方法、ABC、元类、dataclass 与 ORM 雏形。共 11 讲 · 约 410 分钟。

- **038** [类与实例：__init__、self 与属性](/oop/class-basics) · ★☆☆☆☆ · 30 分钟
- **039** [属性查找、MRO 与 super](/oop/mro) · ★★★☆☆ · 35 分钟
- **040** [访问控制、property 与描述符协议](/oop/property) · ★★★★☆ · 40 分钟
- **041** [特殊方法：repr、比较、算术与容器协议](/oop/special-methods) · ★★★☆☆ · 35 分钟
- **042** [上下文管理器与 with 协议](/oop/context) · ★★☆☆☆ · 30 分钟
- **043** [__slots__、弱引用与对象内存布局](/oop/slots) · ★★★★☆ · 35 分钟
- **044** [鸭子类型、抽象基类与 Protocol](/oop/abc) · ★★★☆☆ · 35 分钟
- **045** [元类：__new__、type 与类创建过程](/oop/metaclass) · ★★★★★ · 45 分钟
- **046** [反射与自省：getattr、inspect 与 __dict__](/oop/introspection) · ★★★☆☆ · 30 分钟
- **047** [dataclass、attrs 与 pydantic 模型](/oop/dataclass) · ★★★☆☆ · 35 分钟
- **048** [阶段综合：最小 ORM 与校验框架](/oop/capstone) · ★★★★★ · 60 分钟

## 阶段五 · 核心机制与运行时

> 从会用升级到能从解释器行为推导结论

编译流程、字节码、帧与命名空间、引用计数 GC、GIL、导入系统、性能剖析。共 11 讲 · 约 445 分钟。

- **049** [CPython 编译流程：AST 到字节码](/core/compile-pipeline) · ★★★★☆ · 40 分钟
- **050** [字节码、栈式虚拟机与 dis 实战](/core/bytecode) · ★★★★☆ · 40 分钟
- **051** [帧、调用栈与命名空间](/core/frames) · ★★★★☆ · 35 分钟
- **052** [对象内存布局、引用计数与小对象池](/core/memory) · ★★★★☆ · 40 分钟
- **053** [分代 GC、循环引用与 weakref](/core/gc) · ★★★★☆ · 40 分钟
- **054** [GIL 真相：存在原因、切换与影响边界](/core/gil) · ★★★★★ · 45 分钟
- **055** [导入系统源码级：finder、loader 与缓存](/core/import-system) · ★★★★☆ · 40 分钟
- **056** [属性访问链路与 __getattribute__](/core/attribute-lookup) · ★★★★☆ · 35 分钟
- **057** [可变性、深浅拷贝与共享状态](/core/copy) · ★★★☆☆ · 30 分钟
- **058** [性能剖析：timeit、cProfile 与 tracemalloc](/core/profiling) · ★★★☆☆ · 40 分钟
- **059** [阶段综合：简易性能分析器与内存哨兵](/core/capstone) · ★★★★★ · 60 分钟

## 阶段六 · 并发与异步

> 写出正确、可诊断、可扩展的并发程序

线程与同步、进程与 IPC、IO 多路复用、生成器协程、asyncio 与并发模式。共 11 讲 · 约 430 分钟。

- **060** [并发、并行与 IO 模型全景](/concurrency/concurrency-intro) · ★★☆☆☆ · 30 分钟
- **061** [threading：线程生命周期与共享状态](/concurrency/threading) · ★★★☆☆ · 35 分钟
- **062** [线程同步：Lock、Condition、Semaphore、Event](/concurrency/sync-primitives) · ★★★☆☆ · 40 分钟
- **063** [线程池与 Future 模式](/concurrency/threadpool) · ★★★☆☆ · 35 分钟
- **064** [multiprocessing：进程、Pool 与共享内存](/concurrency/multiprocessing) · ★★★★☆ · 40 分钟
- **065** [进程间通信：Queue、Pipe 与信号](/concurrency/ipc) · ★★★☆☆ · 30 分钟
- **066** [IO 多路复用：select / poll / epoll](/concurrency/io-multiplex) · ★★★★☆ · 40 分钟
- **067** [生成器协程：send、yield from 与调度器](/concurrency/generator-coroutine) · ★★★★☆ · 40 分钟
- **068** [async / await 与协程对象](/concurrency/async-await) · ★★★☆☆ · 35 分钟
- **069** [asyncio 深入：Task、Future 与事件循环](/concurrency/asyncio) · ★★★★☆ · 45 分钟
- **070** [阶段综合：并发爬虫四级演进](/concurrency/capstone) · ★★★★☆ · 60 分钟

## 阶段七 · 工程化与质量

> 把脚本变成可维护、可测试、可发布、可诊断的工程

项目结构、依赖与锁、规范与类型、测试与 Mock、日志配置、打包与 CI/CD。共 11 讲 · 约 410 分钟。

- **071** [项目结构与 src 布局](/engineering/layout) · ★★☆☆☆ · 30 分钟
- **072** [依赖管理：venv、uv、锁文件与可复现构建](/engineering/deps) · ★★★☆☆ · 40 分钟
- **073** [代码规范：PEP 8、ruff、black 与 pre-commit](/engineering/style) · ★★☆☆☆ · 30 分钟
- **074** [静态检查：mypy / pyright 与渐进式类型](/engineering/typecheck) · ★★★☆☆ · 35 分钟
- **075** [单元测试：pytest、fixture 与参数化](/engineering/pytest) · ★★☆☆☆ · 40 分钟
- **076** [Mock 与测试替身：时间、网络与随机](/engineering/mock) · ★★★☆☆ · 35 分钟
- **077** [属性测试、基准测试与模糊测试](/engineering/property-testing) · ★★★★☆ · 35 分钟
- **078** [日志：logging、结构化日志与追踪关联](/engineering/logging) · ★★★☆☆ · 35 分钟
- **079** [配置管理：环境变量、.env 与配置中心](/engineering/config) · ★★☆☆☆ · 30 分钟
- **080** [打包与发布：pyproject、wheel 与 PyPI](/engineering/packaging) · ★★★☆☆ · 40 分钟
- **081** [阶段综合：把脚本重构成可发布包](/engineering/capstone) · ★★★☆☆ · 60 分钟

## 阶段八 · 服务端与数据

> 独立交付一个生产可用的服务与数据访问层

HTTP / ASGI、FastAPI / Flask / Django、ORM、Redis、MQ、认证、对象存储与可观测性。共 11 讲 · 约 440 分钟。

- **082** [HTTP 协议与 WSGI / ASGI](/server/http-wsgi) · ★★★☆☆ · 35 分钟
- **083** [FastAPI / Flask / Django 选型](/server/frameworks) · ★★☆☆☆ · 30 分钟
- **084** [路由、依赖注入与请求校验](/server/routing) · ★★★☆☆ · 35 分钟
- **085** [REST API 设计、OpenAPI 与幂等](/server/rest-api) · ★★★☆☆ · 35 分钟
- **086** [WebSocket / SSE / 长轮询与实时推送](/server/websocket) · ★★★★☆ · 35 分钟
- **087** [SQLAlchemy、连接池、事务与迁移](/server/orm) · ★★★★☆ · 45 分钟
- **088** [Redis 缓存：穿透、击穿、雪崩与分布式锁](/server/redis) · ★★★★☆ · 40 分钟
- **089** [消息队列：Celery / RabbitMQ / Kafka](/server/mq) · ★★★★☆ · 45 分钟
- **090** [认证授权：Session、JWT、OAuth2 与 RBAC](/server/auth) · ★★★★☆ · 40 分钟
- **091** [文件、对象存储、搜索与 gRPC](/server/storage) · ★★★☆☆ · 40 分钟
- **092** [阶段综合：生产级短链服务](/server/capstone) · ★★★★☆ · 60 分钟

## 阶段九 · 数据科学与 AI 工程

> 从数据处理到机器学习、深度学习与大模型应用工程

NumPy / Pandas、可视化与统计、经典算法、集成学习、PyTorch、LLM / RAG / Agent。共 12 讲 · 约 500 分钟。

- **093** [NumPy 向量化、广播与内存布局](/data-ai/numpy) · ★★★☆☆ · 40 分钟
- **094** [Pandas 清洗、分组、透视与时间序列](/data-ai/pandas) · ★★★☆☆ · 45 分钟
- **095** [可视化：Matplotlib / Seaborn / Plotly 与图表选型](/data-ai/visualization) · ★★☆☆☆ · 35 分钟
- **096** [统计基础：分布、检验与相关性](/data-ai/statistics) · ★★★☆☆ · 40 分钟
- **097** [机器学习流程：特征、划分与评价](/data-ai/ml-workflow) · ★★★☆☆ · 40 分钟
- **098** [经典算法：KNN、线性与逻辑回归](/data-ai/linear-models) · ★★★☆☆ · 40 分钟
- **099** [SVM、核方法、决策树与随机森林](/data-ai/svm-trees) · ★★★☆☆ · 40 分钟
- **100** [集成学习：Boosting、XGBoost 与 LightGBM](/data-ai/ensemble) · ★★★★☆ · 40 分钟
- **101** [无监督学习：KMeans、DBSCAN、PCA 与异常检测](/data-ai/unsupervised) · ★★★☆☆ · 40 分钟
- **102** [模型调优：交叉验证、正则化与过拟合](/data-ai/model-tuning) · ★★★★☆ · 40 分钟
- **103** [深度学习与 PyTorch：张量、自动微分与训练循环](/data-ai/deep-learning) · ★★★★☆ · 50 分钟
- **104** [LLM 应用工程：Prompt、RAG、Agent 与成本](/data-ai/llm-engineering) · ★★★★☆ · 50 分钟

## 阶段十 · 分布式与云原生

> 从单机思维升级到分布式与云原生思维，能担责稳定性

一致性、幂等、分布式事务、分片、容器与 K8s、调度、SRE、安全。共 9 讲 · 约 375 分钟。

- **105** [CAP / BASE 与一致性模型](/distributed/cap-base) · ★★★★☆ · 40 分钟
- **106** [幂等、分布式锁与限流](/distributed/idempotency) · ★★★★☆ · 40 分钟
- **107** [分布式事务：2PC / TCC / Saga / 消息最终一致](/distributed/dist-tx) · ★★★★★ · 45 分钟
- **108** [分布式 ID、一致性哈希与分片](/distributed/sharding) · ★★★★☆ · 40 分钟
- **109** [Raft 共识、服务发现与配置中心](/distributed/consensus) · ★★★★★ · 45 分钟
- **110** [容器化与 Kubernetes 部署](/distributed/docker-k8s) · ★★★★☆ · 45 分钟
- **111** [GitOps、灰度发布与可观测平台](/distributed/gitops) · ★★★★☆ · 40 分钟
- **112** [任务调度、SRE 与混沌工程](/distributed/scheduling) · ★★★★☆ · 40 分钟
- **113** [安全工程：依赖、注入、序列化与密钥](/distributed/security) · ★★★★☆ · 40 分钟

## 阶段十一 · 资深进阶与源码

> 具备源码级理解、极致性能调优与架构演进能力

CPython 源码、内存分配器与 GC、导入与事件循环源码、 specializing interpreter、架构与成长。共 8 讲 · 约 375 分钟。

- **114** [CPython 源码：对象、帧与求值循环](/advanced/cpython-source) · ★★★★★ · 50 分钟
- **115** [内存分配器 pymalloc 与 GC 源码](/advanced/allocator) · ★★★★★ · 45 分钟
- **116** [导入系统源码与 import hook](/advanced/import-source) · ★★★★★ · 40 分钟
- **117** [asyncio 事件循环与 Task 源码](/advanced/asyncio-source) · ★★★★★ · 45 分钟
- **118** [GIL 源码、自适应解释器与无 GIL 路线](/advanced/gil-source) · ★★★★★ · 50 分钟
- **119** [极致优化：从剖析到 C 扩展的十倍案例](/advanced/optimization) · ★★★★★ · 55 分钟
- **120** [架构设计：领域分层、演进与重构](/advanced/architecture) · ★★★★★ · 50 分钟
- **121** [资深能力图谱、技术选型与持续精进](/advanced/senior-path) · ★★★★★ · 40 分钟

## 阶段十二 · 工程实战

> 把前十一个阶段的知识在十二类真实场景中反复用熟

CLI、办公自动化、Web、爬虫、数据、AI、存储、分布式与贯穿式 KV 演进线。共 11 讲 · 约 575 分钟。

- **122** [实战 01 · 待办清单 CLI 与命令分发](/projects/cli-todo) · ★★☆☆☆ · 45 分钟
- **123** [实战 02 · 文件检索、日志与自动化办公](/projects/office-files) · ★★☆☆☆ · 45 分钟
- **124** [实战 03 · 邮件、PDF、Excel、Word 与图像视频](/projects/office-docs) · ★★★☆☆ · 55 分钟
- **125** [实战 04 · Selenium 表单自动化与定时任务](/projects/browser-auto) · ★★★☆☆ · 45 分钟
- **126** [实战 05 · 短链与图片服务](/projects/net-shortlink) · ★★★☆☆ · 50 分钟
- **127** [实战 06 · 日志 ETL 与 CSV / SQL 查询工具](/projects/data-etl) · ★★★☆☆ · 55 分钟
- **128** [实战 07 · 并发爬虫与分布式调度](/projects/concurrent-crawler) · ★★★★☆ · 55 分钟
- **129** [实战 08 · KV 贯穿线 ① 内存版与接口抽象](/projects/kv-memory) · ★★★☆☆ · 50 分钟
- **130** [实战 09 · KV 贯穿线 ② 协议帧与网络层](/projects/kv-network) · ★★★★☆ · 55 分钟
- **131** [实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制](/projects/kv-wal) · ★★★★★ · 60 分钟
- **132** [实战 11 · 分片复制、AI 网关与能力收束](/projects/kv-distributed) · ★★★★★ · 60 分钟

## 附录与工具

- [练习与速查](/practice/) · 综合自测、速查表、易错点、常见问题与能力地图的入口
- [语法与标准库速查表](/practice/cheatsheet) · 按主题整理的语法、内置函数、标准库与命令行速查
- [常见坑与反模式](/practice/pitfalls) · 可变默认参数、延迟绑定、浮点精度、GIL 误解等高频事故
- [零基础常见问题](/practice/faq) · 环境、版本、编码、性能、依赖与调试的常见疑问
- [面试与能力自评](/practice/interview) · 分阶段能力矩阵、高频考点与自测题
- [Python 生态与选型地图](/practice/ecosystem) · 按领域整理的主流库、选型维度与版本现状
- [术语表](/practice/glossary) · 全站出现的术语按字母与主题索引

- [本地运行与 GitHub Pages 部署](/about/deploy)
- [关于本站](/about/)

<Callout type="idea" title="已经学过一部分？" text="可以先做练习与速查里的能力自评，按短板直接跳到对应阶段；每讲顶部都标了难度与前置，侧栏按阶段分组，随时能跳回来补齐。" />
