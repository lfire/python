# 示例代码

本目录是教程的配套示例代码，与课程正文一一对应。

```bash
git clone https://github.com/lfire/python.git
cd python
python3 examples/lessons/007-variables.py   # 换成想跑的那一讲
```

## 组织方式

- `lessons/`：132 讲，每讲一个 `.py`，按正文顺序收录「主示例 / 对照写法 / 原理验证 / 工程案例」4 段代码，并在每段前注释预期输出。代码直接取自该讲的精讲数据，因此与页面展示的内容完全一致。
- `topics/`：专题补遗的示例代码。涉及第三方库的专题在文件头注明依赖与安装命令，无需装库也能先跑通的核心机制用标准库单独给出。

站内另有[示例代码索引](../docs/examples/index.md)，可以从课程页面直接跳转。

## 132 讲索引

| 讲次 | 课程 | 示例文件 |
| --- | --- | --- |
| 001 | [开篇：Python 是什么，为什么值得学](../docs/guide/opening.md) | [`001-opening.py`](lessons/001-opening.py) |
| 002 | [环境与工具链：解释器、虚拟环境与编辑器](../docs/guide/setup.md) | [`002-setup.py`](lessons/002-setup.py) |
| 003 | [第一行 Python：从源码到字节码再到执行](../docs/guide/hello.md) | [`003-hello.py`](lessons/003-hello.py) |
| 004 | [工具链全景：写代码、查问题、验质量](../docs/guide/toolchain.md) | [`004-toolchain.py`](lessons/004-toolchain.py) |
| 005 | [学习路线：十三个阶段如何递进](../docs/guide/roadmap.md) | [`005-roadmap.py`](lessons/005-roadmap.py) |
| 006 | [一切皆对象：id、type、value 与可变性](../docs/foundation/object-model.md) | [`006-object-model.py`](lessons/006-object-model.py) |
| 007 | [变量是名字绑定：赋值、引用与命名规范](../docs/foundation/variables.md) | [`007-variables.py`](lessons/007-variables.py) |
| 008 | [数值体系：int 任意精度、float、Decimal 与 bool](../docs/foundation/numeric.md) | [`008-numeric.py`](lessons/008-numeric.py) |
| 009 | [字符串与编码：Unicode、str / bytes 与转义](../docs/foundation/strings.md) | [`009-strings.py`](lessons/009-strings.py) |
| 010 | [字符串操作：切片、f-string 与常用方法](../docs/foundation/string-ops.md) | [`010-string-ops.py`](lessons/010-string-ops.py) |
| 011 | [运算符与表达式：优先级、短路与真值](../docs/foundation/operators.md) | [`011-operators.py`](lessons/011-operators.py) |
| 012 | [分支：if / elif / else 与 match-case](../docs/foundation/control-flow.md) | [`012-control-flow.py`](lessons/012-control-flow.py) |
| 013 | [循环：for / while、range 与循环 else](../docs/foundation/loops.md) | [`013-loops.py`](lessons/013-loops.py) |
| 014 | [输入输出与文件初识：print、input、open、with](../docs/foundation/io.md) | [`014-io.py`](lessons/014-io.py) |
| 015 | [异常：捕获、异常链与自定义异常](../docs/foundation/exceptions.md) | [`015-exceptions.py`](lessons/015-exceptions.py) |
| 016 | [阶段综合：交互式命令行计算器](../docs/foundation/capstone.md) | [`016-capstone.py`](lessons/016-capstone.py) |
| 017 | [序列协议与通用操作](../docs/containers/sequence.md) | [`017-sequence.py`](lessons/017-sequence.py) |
| 018 | [list：动态数组、操作与时间复杂度](../docs/containers/list-basics.md) | [`018-list-basics.py`](lessons/018-list-basics.py) |
| 019 | [list 进阶：切片赋值、排序与常见陷阱](../docs/containers/list-advanced.md) | [`019-list-advanced.py`](lessons/019-list-advanced.py) |
| 020 | [tuple 与具名元组：不可变性的价值](../docs/containers/tuple.md) | [`020-tuple.py`](lessons/020-tuple.py) |
| 021 | [dict：哈希表、视图与插入顺序](../docs/containers/dict-basics.md) | [`021-dict-basics.py`](lessons/021-dict-basics.py) |
| 022 | [dict 进阶：默认字典、计数器与合并](../docs/containers/dict-advanced.md) | [`022-dict-advanced.py`](lessons/022-dict-advanced.py) |
| 023 | [set / frozenset：哈希、集合运算与去重](../docs/containers/set.md) | [`023-set.py`](lessons/023-set.py) |
| 024 | [推导式：四种写法与可读性边界](../docs/containers/comprehension.md) | [`024-comprehension.py`](lessons/024-comprehension.py) |
| 025 | [迭代协议：iterable、iterator 与惰性求值](../docs/containers/iterator.md) | [`025-iterator.py`](lessons/025-iterator.py) |
| 026 | [生成器与 yield：send / throw / close](../docs/containers/generator.md) | [`026-generator.py`](lessons/026-generator.py) |
| 027 | [阶段综合：词频统计与内存版 KV](../docs/containers/capstone.md) | [`027-capstone.py`](lessons/027-capstone.py) |
| 028 | [函数定义与参数形态](../docs/functions/function-basics.md) | [`028-function-basics.py`](lessons/028-function-basics.py) |
| 029 | [返回值、None 与多返回值](../docs/functions/returns.md) | [`029-returns.py`](lessons/029-returns.py) |
| 030 | [作用域、LEGB 与闭包延迟绑定](../docs/functions/scope.md) | [`030-scope.py`](lessons/030-scope.py) |
| 031 | [高阶函数、lambda 与 map / filter / reduce](../docs/functions/higher-order.md) | [`031-higher-order.py`](lessons/031-higher-order.py) |
| 032 | [装饰器原理与 functools.wraps](../docs/functions/decorator.md) | [`032-decorator.py`](lessons/032-decorator.py) |
| 033 | [带参装饰器、叠加顺序与类装饰器](../docs/functions/decorator-params.md) | [`033-decorator-params.py`](lessons/033-decorator-params.py) |
| 034 | [偏函数、可调用对象与函数式工具](../docs/functions/partial.md) | [`034-partial.py`](lessons/034-partial.py) |
| 035 | [模块与包：import 机制与循环导入](../docs/functions/modules.md) | [`035-modules.py`](lessons/035-modules.py) |
| 036 | [类型注解、typing 与渐进式类型](../docs/functions/typing.md) | [`036-typing.py`](lessons/036-typing.py) |
| 037 | [阶段综合：缓存装饰器库与插件注册表](../docs/functions/capstone.md) | [`037-capstone.py`](lessons/037-capstone.py) |
| 038 | [类与实例：__init__、self 与属性](../docs/oop/class-basics.md) | [`038-class-basics.py`](lessons/038-class-basics.py) |
| 039 | [属性查找、MRO 与 super](../docs/oop/mro.md) | [`039-mro.py`](lessons/039-mro.py) |
| 040 | [访问控制、property 与描述符协议](../docs/oop/property.md) | [`040-property.py`](lessons/040-property.py) |
| 041 | [特殊方法：repr、比较、算术与容器协议](../docs/oop/special-methods.md) | [`041-special-methods.py`](lessons/041-special-methods.py) |
| 042 | [上下文管理器与 with 协议](../docs/oop/context.md) | [`042-context.py`](lessons/042-context.py) |
| 043 | [__slots__、弱引用与对象内存布局](../docs/oop/slots.md) | [`043-slots.py`](lessons/043-slots.py) |
| 044 | [鸭子类型、抽象基类与 Protocol](../docs/oop/abc.md) | [`044-abc.py`](lessons/044-abc.py) |
| 045 | [元类：__new__、type 与类创建过程](../docs/oop/metaclass.md) | [`045-metaclass.py`](lessons/045-metaclass.py) |
| 046 | [反射与自省：getattr、inspect 与 __dict__](../docs/oop/introspection.md) | [`046-introspection.py`](lessons/046-introspection.py) |
| 047 | [dataclass、attrs 与 pydantic 模型](../docs/oop/dataclass.md) | [`047-dataclass.py`](lessons/047-dataclass.py) |
| 048 | [阶段综合：最小 ORM 与校验框架](../docs/oop/capstone.md) | [`048-capstone.py`](lessons/048-capstone.py) |
| 049 | [CPython 编译流程：AST 到字节码](../docs/core/compile-pipeline.md) | [`049-compile-pipeline.py`](lessons/049-compile-pipeline.py) |
| 050 | [字节码、栈式虚拟机与 dis 实战](../docs/core/bytecode.md) | [`050-bytecode.py`](lessons/050-bytecode.py) |
| 051 | [帧、调用栈与命名空间](../docs/core/frames.md) | [`051-frames.py`](lessons/051-frames.py) |
| 052 | [对象内存布局、引用计数与小对象池](../docs/core/memory.md) | [`052-memory.py`](lessons/052-memory.py) |
| 053 | [分代 GC、循环引用与 weakref](../docs/core/gc.md) | [`053-gc.py`](lessons/053-gc.py) |
| 054 | [GIL 真相：存在原因、切换与影响边界](../docs/core/gil.md) | [`054-gil.py`](lessons/054-gil.py) |
| 055 | [导入系统源码级：finder、loader 与缓存](../docs/core/import-system.md) | [`055-import-system.py`](lessons/055-import-system.py) |
| 056 | [属性访问链路与 __getattribute__](../docs/core/attribute-lookup.md) | [`056-attribute-lookup.py`](lessons/056-attribute-lookup.py) |
| 057 | [可变性、深浅拷贝与共享状态](../docs/core/copy.md) | [`057-copy.py`](lessons/057-copy.py) |
| 058 | [性能剖析：timeit、cProfile 与 tracemalloc](../docs/core/profiling.md) | [`058-profiling.py`](lessons/058-profiling.py) |
| 059 | [阶段综合：简易性能分析器与内存哨兵](../docs/core/capstone.md) | [`059-capstone.py`](lessons/059-capstone.py) |
| 060 | [并发、并行与 IO 模型全景](../docs/concurrency/concurrency-intro.md) | [`060-concurrency-intro.py`](lessons/060-concurrency-intro.py) |
| 061 | [threading：线程生命周期与共享状态](../docs/concurrency/threading.md) | [`061-threading.py`](lessons/061-threading.py) |
| 062 | [线程同步：Lock、Condition、Semaphore、Event](../docs/concurrency/sync-primitives.md) | [`062-sync-primitives.py`](lessons/062-sync-primitives.py) |
| 063 | [线程池与 Future 模式](../docs/concurrency/threadpool.md) | [`063-threadpool.py`](lessons/063-threadpool.py) |
| 064 | [multiprocessing：进程、Pool 与共享内存](../docs/concurrency/multiprocessing.md) | [`064-multiprocessing.py`](lessons/064-multiprocessing.py) |
| 065 | [进程间通信：Queue、Pipe 与信号](../docs/concurrency/ipc.md) | [`065-ipc.py`](lessons/065-ipc.py) |
| 066 | [IO 多路复用：select / poll / epoll](../docs/concurrency/io-multiplex.md) | [`066-io-multiplex.py`](lessons/066-io-multiplex.py) |
| 067 | [生成器协程：send、yield from 与调度器](../docs/concurrency/generator-coroutine.md) | [`067-generator-coroutine.py`](lessons/067-generator-coroutine.py) |
| 068 | [async / await 与协程对象](../docs/concurrency/async-await.md) | [`068-async-await.py`](lessons/068-async-await.py) |
| 069 | [asyncio 深入：Task、Future 与事件循环](../docs/concurrency/asyncio.md) | [`069-asyncio.py`](lessons/069-asyncio.py) |
| 070 | [阶段综合：并发爬虫四级演进](../docs/concurrency/capstone.md) | [`070-capstone.py`](lessons/070-capstone.py) |
| 071 | [项目结构与 src 布局](../docs/engineering/layout.md) | [`071-layout.py`](lessons/071-layout.py) |
| 072 | [依赖管理：venv、uv、锁文件与可复现构建](../docs/engineering/deps.md) | [`072-deps.py`](lessons/072-deps.py) |
| 073 | [代码规范：PEP 8、ruff、black 与 pre-commit](../docs/engineering/style.md) | [`073-style.py`](lessons/073-style.py) |
| 074 | [静态检查：mypy / pyright 与渐进式类型](../docs/engineering/typecheck.md) | [`074-typecheck.py`](lessons/074-typecheck.py) |
| 075 | [单元测试：pytest、fixture 与参数化](../docs/engineering/pytest.md) | [`075-pytest.py`](lessons/075-pytest.py) |
| 076 | [Mock 与测试替身：时间、网络与随机](../docs/engineering/mock.md) | [`076-mock.py`](lessons/076-mock.py) |
| 077 | [属性测试、基准测试与模糊测试](../docs/engineering/property-testing.md) | [`077-property-testing.py`](lessons/077-property-testing.py) |
| 078 | [日志：logging、结构化日志与追踪关联](../docs/engineering/logging.md) | [`078-logging.py`](lessons/078-logging.py) |
| 079 | [配置管理：环境变量、.env 与配置中心](../docs/engineering/config.md) | [`079-config.py`](lessons/079-config.py) |
| 080 | [打包与发布：pyproject、wheel 与 PyPI](../docs/engineering/packaging.md) | [`080-packaging.py`](lessons/080-packaging.py) |
| 081 | [阶段综合：把脚本重构成可发布包](../docs/engineering/capstone.md) | [`081-capstone.py`](lessons/081-capstone.py) |
| 082 | [HTTP 协议与 WSGI / ASGI](../docs/server/http-wsgi.md) | [`082-http-wsgi.py`](lessons/082-http-wsgi.py) |
| 083 | [FastAPI / Flask / Django 选型](../docs/server/frameworks.md) | [`083-frameworks.py`](lessons/083-frameworks.py) |
| 084 | [路由、依赖注入与请求校验](../docs/server/routing.md) | [`084-routing.py`](lessons/084-routing.py) |
| 085 | [REST API 设计、OpenAPI 与幂等](../docs/server/rest-api.md) | [`085-rest-api.py`](lessons/085-rest-api.py) |
| 086 | [WebSocket / SSE / 长轮询与实时推送](../docs/server/websocket.md) | [`086-websocket.py`](lessons/086-websocket.py) |
| 087 | [SQLAlchemy、连接池、事务与迁移](../docs/server/orm.md) | [`087-orm.py`](lessons/087-orm.py) |
| 088 | [Redis 缓存：穿透、击穿、雪崩与分布式锁](../docs/server/redis.md) | [`088-redis.py`](lessons/088-redis.py) |
| 089 | [消息队列：Celery / RabbitMQ / Kafka](../docs/server/mq.md) | [`089-mq.py`](lessons/089-mq.py) |
| 090 | [认证授权：Session、JWT、OAuth2 与 RBAC](../docs/server/auth.md) | [`090-auth.py`](lessons/090-auth.py) |
| 091 | [文件、对象存储、搜索与 gRPC](../docs/server/storage.md) | [`091-storage.py`](lessons/091-storage.py) |
| 092 | [阶段综合：生产级短链服务](../docs/server/capstone.md) | [`092-capstone.py`](lessons/092-capstone.py) |
| 093 | [NumPy 向量化、广播与内存布局](../docs/data-ai/numpy.md) | [`093-numpy.py`](lessons/093-numpy.py) |
| 094 | [Pandas 清洗、分组、透视与时间序列](../docs/data-ai/pandas.md) | [`094-pandas.py`](lessons/094-pandas.py) |
| 095 | [可视化：Matplotlib / Seaborn / Plotly 与图表选型](../docs/data-ai/visualization.md) | [`095-visualization.py`](lessons/095-visualization.py) |
| 096 | [统计基础：分布、检验与相关性](../docs/data-ai/statistics.md) | [`096-statistics.py`](lessons/096-statistics.py) |
| 097 | [机器学习流程：特征、划分与评价](../docs/data-ai/ml-workflow.md) | [`097-ml-workflow.py`](lessons/097-ml-workflow.py) |
| 098 | [经典算法：KNN、线性与逻辑回归](../docs/data-ai/linear-models.md) | [`098-linear-models.py`](lessons/098-linear-models.py) |
| 099 | [SVM、核方法、决策树与随机森林](../docs/data-ai/svm-trees.md) | [`099-svm-trees.py`](lessons/099-svm-trees.py) |
| 100 | [集成学习：Boosting、XGBoost 与 LightGBM](../docs/data-ai/ensemble.md) | [`100-ensemble.py`](lessons/100-ensemble.py) |
| 101 | [无监督学习：KMeans、DBSCAN、PCA 与异常检测](../docs/data-ai/unsupervised.md) | [`101-unsupervised.py`](lessons/101-unsupervised.py) |
| 102 | [模型调优：交叉验证、正则化与过拟合](../docs/data-ai/model-tuning.md) | [`102-model-tuning.py`](lessons/102-model-tuning.py) |
| 103 | [深度学习与 PyTorch：张量、自动微分与训练循环](../docs/data-ai/deep-learning.md) | [`103-deep-learning.py`](lessons/103-deep-learning.py) |
| 104 | [LLM 应用工程：Prompt、RAG、Agent 与成本](../docs/data-ai/llm-engineering.md) | [`104-llm-engineering.py`](lessons/104-llm-engineering.py) |
| 105 | [CAP / BASE 与一致性模型](../docs/distributed/cap-base.md) | [`105-cap-base.py`](lessons/105-cap-base.py) |
| 106 | [幂等、分布式锁与限流](../docs/distributed/idempotency.md) | [`106-idempotency.py`](lessons/106-idempotency.py) |
| 107 | [分布式事务：2PC / TCC / Saga / 消息最终一致](../docs/distributed/dist-tx.md) | [`107-dist-tx.py`](lessons/107-dist-tx.py) |
| 108 | [分布式 ID、一致性哈希与分片](../docs/distributed/sharding.md) | [`108-sharding.py`](lessons/108-sharding.py) |
| 109 | [Raft 共识、服务发现与配置中心](../docs/distributed/consensus.md) | [`109-consensus.py`](lessons/109-consensus.py) |
| 110 | [容器化与 Kubernetes 部署](../docs/distributed/docker-k8s.md) | [`110-docker-k8s.py`](lessons/110-docker-k8s.py) |
| 111 | [GitOps、灰度发布与可观测平台](../docs/distributed/gitops.md) | [`111-gitops.py`](lessons/111-gitops.py) |
| 112 | [任务调度、SRE 与混沌工程](../docs/distributed/scheduling.md) | [`112-scheduling.py`](lessons/112-scheduling.py) |
| 113 | [安全工程：依赖、注入、序列化与密钥](../docs/distributed/security.md) | [`113-security.py`](lessons/113-security.py) |
| 114 | [CPython 源码：对象、帧与求值循环](../docs/advanced/cpython-source.md) | [`114-cpython-source.py`](lessons/114-cpython-source.py) |
| 115 | [内存分配器 pymalloc 与 GC 源码](../docs/advanced/allocator.md) | [`115-allocator.py`](lessons/115-allocator.py) |
| 116 | [导入系统源码与 import hook](../docs/advanced/import-source.md) | [`116-import-source.py`](lessons/116-import-source.py) |
| 117 | [asyncio 事件循环与 Task 源码](../docs/advanced/asyncio-source.md) | [`117-asyncio-source.py`](lessons/117-asyncio-source.py) |
| 118 | [GIL 源码、自适应解释器与无 GIL 路线](../docs/advanced/gil-source.md) | [`118-gil-source.py`](lessons/118-gil-source.py) |
| 119 | [极致优化：从剖析到 C 扩展的十倍案例](../docs/advanced/optimization.md) | [`119-optimization.py`](lessons/119-optimization.py) |
| 120 | [架构设计：领域分层、演进与重构](../docs/advanced/architecture.md) | [`120-architecture.py`](lessons/120-architecture.py) |
| 121 | [资深能力图谱、技术选型与持续精进](../docs/advanced/senior-path.md) | [`121-senior-path.py`](lessons/121-senior-path.py) |
| 122 | [实战 01 · 待办清单 CLI 与命令分发](../docs/projects/cli-todo.md) | [`122-cli-todo.py`](lessons/122-cli-todo.py) |
| 123 | [实战 02 · 文件检索、日志与自动化办公](../docs/projects/office-files.md) | [`123-office-files.py`](lessons/123-office-files.py) |
| 124 | [实战 03 · 邮件、PDF、Excel、Word 与图像视频](../docs/projects/office-docs.md) | [`124-office-docs.py`](lessons/124-office-docs.py) |
| 125 | [实战 04 · Selenium 表单自动化与定时任务](../docs/projects/browser-auto.md) | [`125-browser-auto.py`](lessons/125-browser-auto.py) |
| 126 | [实战 05 · 短链与图片服务](../docs/projects/net-shortlink.md) | [`126-net-shortlink.py`](lessons/126-net-shortlink.py) |
| 127 | [实战 06 · 日志 ETL 与 CSV / SQL 查询工具](../docs/projects/data-etl.md) | [`127-data-etl.py`](lessons/127-data-etl.py) |
| 128 | [实战 07 · 并发爬虫与分布式调度](../docs/projects/concurrent-crawler.md) | [`128-concurrent-crawler.py`](lessons/128-concurrent-crawler.py) |
| 129 | [实战 08 · KV 贯穿线 ① 内存版与接口抽象](../docs/projects/kv-memory.md) | [`129-kv-memory.py`](lessons/129-kv-memory.py) |
| 130 | [实战 09 · KV 贯穿线 ② 协议帧与网络层](../docs/projects/kv-network.md) | [`130-kv-network.py`](lessons/130-kv-network.py) |
| 131 | [实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制](../docs/projects/kv-wal.md) | [`131-kv-wal.py`](lessons/131-kv-wal.py) |
| 132 | [实战 11 · 分片复制、AI 网关与能力收束](../docs/projects/kv-distributed.md) | [`132-kv-distributed.py`](lessons/132-kv-distributed.py) |

## 专题补遗索引

| 专题 | 示例文件 | 说明 |
| --- | --- | --- |
| [正则表达式 re：从字符类到回溯](../docs/topics/regex.md) | [`regex.py`](topics/regex.py) | 字符类、量词与贪婪、分组与命名捕获、零宽断言、re 模块 API、回溯与灾难性匹配、常见模式库。 |
| [Scrapy 与反爬合规：从 Spider 到生产采集](../docs/topics/scrapy-antibot.md) | [`scrapy-antibot.py`](topics/scrapy-antibot.py) | Scrapy 架构、Spider / 中间件 / Pipeline、Scrapyd 部署、robots 与限速、登录态与 Ajax 接口、验证码/代理池/字体加密的边界与合规。 |
| [接口与 Web UI 自动化测试](../docs/topics/testing-automation.md) | [`testing-automation.py`](topics/testing-automation.py) | Postman 接口调试、requests 用例层、pytest 参数化与数据驱动、Allure 报告、Selenium Page Object、失败截图与重试、CI 里的测试门禁。 |
| [办公自动化进阶：PPT、GUI 与批处理](../docs/topics/office-advanced.md) | [`office-advanced.py`](topics/office-advanced.py) | python-pptx 生成演示文稿、dotenv 与模板映射、Tkinter 最小 GUI 与多线程、Pillow 图片/二维码、moviepy 视频分段拼接、批量任务与错误隔离。 |
| [深度学习项目：CNN、RNN、迁移学习与部署](../docs/topics/dl-projects.md) | [`dl-projects.py`](topics/dl-projects.py) | 张量与 DataLoader、CNN 卷积动机、RNN/LSTM 序列建模、预训练 ResNet 与迁移学习、GAN 风格生成、MNIST 分类、医学影像端到端流程、模型导出与上线。 |
| [RAG 框架与大模型 API 实战](../docs/topics/rag-frameworks.md) | [`rag-frameworks.py`](topics/rag-frameworks.py) | PDF 解析与分块、Embedding 与向量库、LlamaIndex/语义检索、DeepSeek 等 API 调用与流式响应、Token 成本核算、溯源与拒答、Agent 工具调用与预算。 |
| [Flask 实操：路由、模板与会话](../docs/topics/web-frameworks.md) | [`web-frameworks.py`](topics/web-frameworks.py) | 应用工厂与蓝图、jinja2 模板、请求与响应、Cookie/Session、表单与验证码、SQLAlchemy 集成、错误处理、生产部署与 HTTPS。 |
| [数据分析实战：Jupyter 到报告导出](../docs/topics/data-projects.md) | [`data-projects.py`](topics/data-projects.py) | Jupyter 工作流、Pandas 多表联合与透视、Scipy 假设检验、Matplotlib/Seaborn 图表选型、疫情/房价分析、医院科室费用口径校验、报告导出与复现。 |
| [工程底座：Linux、Git、SQL 与多版本](../docs/topics/toolchain-foundation.md) | [`toolchain-foundation.py`](topics/toolchain-foundation.py) | Linux 文件权限与常用命令、Shell 管道、Git 分支与协作、.gitignore 防泄漏、MySQL 表设计与多表查询、pyenv/Anaconda 多版本、venv 与国内镜像。 |
| [参考课程对照与学习路线](../docs/topics/reference-map.md) | —（对照索引页） | 对照索引页，无独立示例代码；见各专题文件 |
