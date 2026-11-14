---
title: 示例代码
description: 132 讲与专题补遗的配套示例代码索引，可直接 clone 仓库运行。
---

# 示例代码

教程里出现的每一段代码，在仓库里都有对应的可运行文件。把仓库 clone 到本地后，
按下面的路径直接执行，就能复现页面上的输出；每个讲次文件按正文顺序收录主示例、
对照写法、原理验证与工程案例四段，并附预期输出注释。

```bash
git clone https://github.com/lfire/python.git
cd python
python3 examples/lessons/007-variables.py
```

<Callout type="tip" title="代码与内容严格对应" text="讲次文件由该讲的精讲数据直接生成，不是另写一套示例；专题文件按专题正文整理，依赖第三方库的部分在文件头注明安装命令。" />

## 132 讲

| 讲次 | 课程页面 | 示例文件 |
| --- | --- | --- |
| 001 | [开篇：Python 是什么，为什么值得学](/guide/opening) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/001-opening.py) |
| 002 | [环境与工具链：解释器、虚拟环境与编辑器](/guide/setup) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/002-setup.py) |
| 003 | [第一行 Python：从源码到字节码再到执行](/guide/hello) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/003-hello.py) |
| 004 | [工具链全景：写代码、查问题、验质量](/guide/toolchain) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/004-toolchain.py) |
| 005 | [学习路线：十三个阶段如何递进](/guide/roadmap) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/005-roadmap.py) |
| 006 | [一切皆对象：id、type、value 与可变性](/foundation/object-model) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/006-object-model.py) |
| 007 | [变量是名字绑定：赋值、引用与命名规范](/foundation/variables) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/007-variables.py) |
| 008 | [数值体系：int 任意精度、float、Decimal 与 bool](/foundation/numeric) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/008-numeric.py) |
| 009 | [字符串与编码：Unicode、str / bytes 与转义](/foundation/strings) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/009-strings.py) |
| 010 | [字符串操作：切片、f-string 与常用方法](/foundation/string-ops) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/010-string-ops.py) |
| 011 | [运算符与表达式：优先级、短路与真值](/foundation/operators) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/011-operators.py) |
| 012 | [分支：if / elif / else 与 match-case](/foundation/control-flow) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/012-control-flow.py) |
| 013 | [循环：for / while、range 与循环 else](/foundation/loops) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/013-loops.py) |
| 014 | [输入输出与文件初识：print、input、open、with](/foundation/io) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/014-io.py) |
| 015 | [异常：捕获、异常链与自定义异常](/foundation/exceptions) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/015-exceptions.py) |
| 016 | [阶段综合：交互式命令行计算器](/foundation/capstone) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/016-capstone.py) |
| 017 | [序列协议与通用操作](/containers/sequence) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/017-sequence.py) |
| 018 | [list：动态数组、操作与时间复杂度](/containers/list-basics) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/018-list-basics.py) |
| 019 | [list 进阶：切片赋值、排序与常见陷阱](/containers/list-advanced) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/019-list-advanced.py) |
| 020 | [tuple 与具名元组：不可变性的价值](/containers/tuple) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/020-tuple.py) |
| 021 | [dict：哈希表、视图与插入顺序](/containers/dict-basics) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/021-dict-basics.py) |
| 022 | [dict 进阶：默认字典、计数器与合并](/containers/dict-advanced) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/022-dict-advanced.py) |
| 023 | [set / frozenset：哈希、集合运算与去重](/containers/set) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/023-set.py) |
| 024 | [推导式：四种写法与可读性边界](/containers/comprehension) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/024-comprehension.py) |
| 025 | [迭代协议：iterable、iterator 与惰性求值](/containers/iterator) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/025-iterator.py) |
| 026 | [生成器与 yield：send / throw / close](/containers/generator) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/026-generator.py) |
| 027 | [阶段综合：词频统计与内存版 KV](/containers/capstone) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/027-capstone.py) |
| 028 | [函数定义与参数形态](/functions/function-basics) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/028-function-basics.py) |
| 029 | [返回值、None 与多返回值](/functions/returns) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/029-returns.py) |
| 030 | [作用域、LEGB 与闭包延迟绑定](/functions/scope) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/030-scope.py) |
| 031 | [高阶函数、lambda 与 map / filter / reduce](/functions/higher-order) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/031-higher-order.py) |
| 032 | [装饰器原理与 functools.wraps](/functions/decorator) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/032-decorator.py) |
| 033 | [带参装饰器、叠加顺序与类装饰器](/functions/decorator-params) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/033-decorator-params.py) |
| 034 | [偏函数、可调用对象与函数式工具](/functions/partial) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/034-partial.py) |
| 035 | [模块与包：import 机制与循环导入](/functions/modules) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/035-modules.py) |
| 036 | [类型注解、typing 与渐进式类型](/functions/typing) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/036-typing.py) |
| 037 | [阶段综合：缓存装饰器库与插件注册表](/functions/capstone) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/037-capstone.py) |
| 038 | [类与实例：__init__、self 与属性](/oop/class-basics) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/038-class-basics.py) |
| 039 | [属性查找、MRO 与 super](/oop/mro) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/039-mro.py) |
| 040 | [访问控制、property 与描述符协议](/oop/property) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/040-property.py) |
| 041 | [特殊方法：repr、比较、算术与容器协议](/oop/special-methods) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/041-special-methods.py) |
| 042 | [上下文管理器与 with 协议](/oop/context) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/042-context.py) |
| 043 | [__slots__、弱引用与对象内存布局](/oop/slots) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/043-slots.py) |
| 044 | [鸭子类型、抽象基类与 Protocol](/oop/abc) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/044-abc.py) |
| 045 | [元类：__new__、type 与类创建过程](/oop/metaclass) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/045-metaclass.py) |
| 046 | [反射与自省：getattr、inspect 与 __dict__](/oop/introspection) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/046-introspection.py) |
| 047 | [dataclass、attrs 与 pydantic 模型](/oop/dataclass) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/047-dataclass.py) |
| 048 | [阶段综合：最小 ORM 与校验框架](/oop/capstone) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/048-capstone.py) |
| 049 | [CPython 编译流程：AST 到字节码](/core/compile-pipeline) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/049-compile-pipeline.py) |
| 050 | [字节码、栈式虚拟机与 dis 实战](/core/bytecode) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/050-bytecode.py) |
| 051 | [帧、调用栈与命名空间](/core/frames) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/051-frames.py) |
| 052 | [对象内存布局、引用计数与小对象池](/core/memory) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/052-memory.py) |
| 053 | [分代 GC、循环引用与 weakref](/core/gc) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/053-gc.py) |
| 054 | [GIL 真相：存在原因、切换与影响边界](/core/gil) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/054-gil.py) |
| 055 | [导入系统源码级：finder、loader 与缓存](/core/import-system) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/055-import-system.py) |
| 056 | [属性访问链路与 __getattribute__](/core/attribute-lookup) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/056-attribute-lookup.py) |
| 057 | [可变性、深浅拷贝与共享状态](/core/copy) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/057-copy.py) |
| 058 | [性能剖析：timeit、cProfile 与 tracemalloc](/core/profiling) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/058-profiling.py) |
| 059 | [阶段综合：简易性能分析器与内存哨兵](/core/capstone) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/059-capstone.py) |
| 060 | [并发、并行与 IO 模型全景](/concurrency/concurrency-intro) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/060-concurrency-intro.py) |
| 061 | [threading：线程生命周期与共享状态](/concurrency/threading) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/061-threading.py) |
| 062 | [线程同步：Lock、Condition、Semaphore、Event](/concurrency/sync-primitives) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/062-sync-primitives.py) |
| 063 | [线程池与 Future 模式](/concurrency/threadpool) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/063-threadpool.py) |
| 064 | [multiprocessing：进程、Pool 与共享内存](/concurrency/multiprocessing) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/064-multiprocessing.py) |
| 065 | [进程间通信：Queue、Pipe 与信号](/concurrency/ipc) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/065-ipc.py) |
| 066 | [IO 多路复用：select / poll / epoll](/concurrency/io-multiplex) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/066-io-multiplex.py) |
| 067 | [生成器协程：send、yield from 与调度器](/concurrency/generator-coroutine) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/067-generator-coroutine.py) |
| 068 | [async / await 与协程对象](/concurrency/async-await) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/068-async-await.py) |
| 069 | [asyncio 深入：Task、Future 与事件循环](/concurrency/asyncio) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/069-asyncio.py) |
| 070 | [阶段综合：并发爬虫四级演进](/concurrency/capstone) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/070-capstone.py) |
| 071 | [项目结构与 src 布局](/engineering/layout) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/071-layout.py) |
| 072 | [依赖管理：venv、uv、锁文件与可复现构建](/engineering/deps) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/072-deps.py) |
| 073 | [代码规范：PEP 8、ruff、black 与 pre-commit](/engineering/style) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/073-style.py) |
| 074 | [静态检查：mypy / pyright 与渐进式类型](/engineering/typecheck) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/074-typecheck.py) |
| 075 | [单元测试：pytest、fixture 与参数化](/engineering/pytest) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/075-pytest.py) |
| 076 | [Mock 与测试替身：时间、网络与随机](/engineering/mock) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/076-mock.py) |
| 077 | [属性测试、基准测试与模糊测试](/engineering/property-testing) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/077-property-testing.py) |
| 078 | [日志：logging、结构化日志与追踪关联](/engineering/logging) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/078-logging.py) |
| 079 | [配置管理：环境变量、.env 与配置中心](/engineering/config) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/079-config.py) |
| 080 | [打包与发布：pyproject、wheel 与 PyPI](/engineering/packaging) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/080-packaging.py) |
| 081 | [阶段综合：把脚本重构成可发布包](/engineering/capstone) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/081-capstone.py) |
| 082 | [HTTP 协议与 WSGI / ASGI](/server/http-wsgi) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/082-http-wsgi.py) |
| 083 | [FastAPI / Flask / Django 选型](/server/frameworks) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/083-frameworks.py) |
| 084 | [路由、依赖注入与请求校验](/server/routing) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/084-routing.py) |
| 085 | [REST API 设计、OpenAPI 与幂等](/server/rest-api) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/085-rest-api.py) |
| 086 | [WebSocket / SSE / 长轮询与实时推送](/server/websocket) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/086-websocket.py) |
| 087 | [SQLAlchemy、连接池、事务与迁移](/server/orm) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/087-orm.py) |
| 088 | [Redis 缓存：穿透、击穿、雪崩与分布式锁](/server/redis) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/088-redis.py) |
| 089 | [消息队列：Celery / RabbitMQ / Kafka](/server/mq) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/089-mq.py) |
| 090 | [认证授权：Session、JWT、OAuth2 与 RBAC](/server/auth) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/090-auth.py) |
| 091 | [文件、对象存储、搜索与 gRPC](/server/storage) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/091-storage.py) |
| 092 | [阶段综合：生产级短链服务](/server/capstone) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/092-capstone.py) |
| 093 | [NumPy 向量化、广播与内存布局](/data-ai/numpy) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/093-numpy.py) |
| 094 | [Pandas 清洗、分组、透视与时间序列](/data-ai/pandas) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/094-pandas.py) |
| 095 | [可视化：Matplotlib / Seaborn / Plotly 与图表选型](/data-ai/visualization) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/095-visualization.py) |
| 096 | [统计基础：分布、检验与相关性](/data-ai/statistics) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/096-statistics.py) |
| 097 | [机器学习流程：特征、划分与评价](/data-ai/ml-workflow) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/097-ml-workflow.py) |
| 098 | [经典算法：KNN、线性与逻辑回归](/data-ai/linear-models) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/098-linear-models.py) |
| 099 | [SVM、核方法、决策树与随机森林](/data-ai/svm-trees) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/099-svm-trees.py) |
| 100 | [集成学习：Boosting、XGBoost 与 LightGBM](/data-ai/ensemble) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/100-ensemble.py) |
| 101 | [无监督学习：KMeans、DBSCAN、PCA 与异常检测](/data-ai/unsupervised) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/101-unsupervised.py) |
| 102 | [模型调优：交叉验证、正则化与过拟合](/data-ai/model-tuning) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/102-model-tuning.py) |
| 103 | [深度学习与 PyTorch：张量、自动微分与训练循环](/data-ai/deep-learning) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/103-deep-learning.py) |
| 104 | [LLM 应用工程：Prompt、RAG、Agent 与成本](/data-ai/llm-engineering) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/104-llm-engineering.py) |
| 105 | [CAP / BASE 与一致性模型](/distributed/cap-base) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/105-cap-base.py) |
| 106 | [幂等、分布式锁与限流](/distributed/idempotency) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/106-idempotency.py) |
| 107 | [分布式事务：2PC / TCC / Saga / 消息最终一致](/distributed/dist-tx) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/107-dist-tx.py) |
| 108 | [分布式 ID、一致性哈希与分片](/distributed/sharding) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/108-sharding.py) |
| 109 | [Raft 共识、服务发现与配置中心](/distributed/consensus) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/109-consensus.py) |
| 110 | [容器化与 Kubernetes 部署](/distributed/docker-k8s) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/110-docker-k8s.py) |
| 111 | [GitOps、灰度发布与可观测平台](/distributed/gitops) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/111-gitops.py) |
| 112 | [任务调度、SRE 与混沌工程](/distributed/scheduling) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/112-scheduling.py) |
| 113 | [安全工程：依赖、注入、序列化与密钥](/distributed/security) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/113-security.py) |
| 114 | [CPython 源码：对象、帧与求值循环](/advanced/cpython-source) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/114-cpython-source.py) |
| 115 | [内存分配器 pymalloc 与 GC 源码](/advanced/allocator) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/115-allocator.py) |
| 116 | [导入系统源码与 import hook](/advanced/import-source) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/116-import-source.py) |
| 117 | [asyncio 事件循环与 Task 源码](/advanced/asyncio-source) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/117-asyncio-source.py) |
| 118 | [GIL 源码、自适应解释器与无 GIL 路线](/advanced/gil-source) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/118-gil-source.py) |
| 119 | [极致优化：从剖析到 C 扩展的十倍案例](/advanced/optimization) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/119-optimization.py) |
| 120 | [架构设计：领域分层、演进与重构](/advanced/architecture) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/120-architecture.py) |
| 121 | [资深能力图谱、技术选型与持续精进](/advanced/senior-path) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/121-senior-path.py) |
| 122 | [实战 01 · 待办清单 CLI 与命令分发](/projects/cli-todo) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/122-cli-todo.py) |
| 123 | [实战 02 · 文件检索、日志与自动化办公](/projects/office-files) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/123-office-files.py) |
| 124 | [实战 03 · 邮件、PDF、Excel、Word 与图像视频](/projects/office-docs) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/124-office-docs.py) |
| 125 | [实战 04 · Selenium 表单自动化与定时任务](/projects/browser-auto) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/125-browser-auto.py) |
| 126 | [实战 05 · 短链与图片服务](/projects/net-shortlink) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/126-net-shortlink.py) |
| 127 | [实战 06 · 日志 ETL 与 CSV / SQL 查询工具](/projects/data-etl) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/127-data-etl.py) |
| 128 | [实战 07 · 并发爬虫与分布式调度](/projects/concurrent-crawler) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/128-concurrent-crawler.py) |
| 129 | [实战 08 · KV 贯穿线 ① 内存版与接口抽象](/projects/kv-memory) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/129-kv-memory.py) |
| 130 | [实战 09 · KV 贯穿线 ② 协议帧与网络层](/projects/kv-network) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/130-kv-network.py) |
| 131 | [实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制](/projects/kv-wal) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/131-kv-wal.py) |
| 132 | [实战 11 · 分片复制、AI 网关与能力收束](/projects/kv-distributed) | [查看源码](https://github.com/lfire/python/blob/main/examples/lessons/132-kv-distributed.py) |

## 专题补遗

| 专题 | 示例文件 | 说明 |
| --- | --- | --- |
| [正则表达式 re：从字符类到回溯](/topics/regex) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/regex.py) | 字符类、量词与贪婪、分组与命名捕获、零宽断言、re 模块 API、回溯与灾难性匹配、常见模式库。 |
| [Scrapy 与反爬合规：从 Spider 到生产采集](/topics/scrapy-antibot) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/scrapy-antibot.py) | Scrapy 架构、Spider / 中间件 / Pipeline、Scrapyd 部署、robots 与限速、登录态与 Ajax 接口、验证码/代理池/字体加密的边界与合规。 |
| [接口与 Web UI 自动化测试](/topics/testing-automation) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/testing-automation.py) | Postman 接口调试、requests 用例层、pytest 参数化与数据驱动、Allure 报告、Selenium Page Object、失败截图与重试、CI 里的测试门禁。 |
| [办公自动化进阶：PPT、GUI 与批处理](/topics/office-advanced) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/office-advanced.py) | python-pptx 生成演示文稿、dotenv 与模板映射、Tkinter 最小 GUI 与多线程、Pillow 图片/二维码、moviepy 视频分段拼接、批量任务与错误隔离。 |
| [深度学习项目：CNN、RNN、迁移学习与部署](/topics/dl-projects) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/dl-projects.py) | 张量与 DataLoader、CNN 卷积动机、RNN/LSTM 序列建模、预训练 ResNet 与迁移学习、GAN 风格生成、MNIST 分类、医学影像端到端流程、模型导出与上线。 |
| [RAG 框架与大模型 API 实战](/topics/rag-frameworks) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/rag-frameworks.py) | PDF 解析与分块、Embedding 与向量库、LlamaIndex/语义检索、DeepSeek 等 API 调用与流式响应、Token 成本核算、溯源与拒答、Agent 工具调用与预算。 |
| [Flask 实操：路由、模板与会话](/topics/web-frameworks) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/web-frameworks.py) | 应用工厂与蓝图、jinja2 模板、请求与响应、Cookie/Session、表单与验证码、SQLAlchemy 集成、错误处理、生产部署与 HTTPS。 |
| [数据分析实战：Jupyter 到报告导出](/topics/data-projects) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/data-projects.py) | Jupyter 工作流、Pandas 多表联合与透视、Scipy 假设检验、Matplotlib/Seaborn 图表选型、疫情/房价分析、医院科室费用口径校验、报告导出与复现。 |
| [工程底座：Linux、Git、SQL 与多版本](/topics/toolchain-foundation) | [查看源码](https://github.com/lfire/python/blob/main/examples/topics/toolchain-foundation.py) | Linux 文件权限与常用命令、Shell 管道、Git 分支与协作、.gitignore 防泄漏、MySQL 表设计与多表查询、pyenv/Anaconda 多版本、venv 与国内镜像。 |
| [参考课程对照与学习路线](/topics/reference-map) | —（对照索引页） | 对照索引页，无独立示例代码；见各专题文件 |

## 其它入口

- [课程总目录](/guide/curriculum)
- [专题补遗](/topics/)
- [练习与速查](/practice/)
