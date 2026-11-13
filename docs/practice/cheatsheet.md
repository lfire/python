---
title: 语法与标准库速查表
description: 按 13 个阶段索引 132 讲的语法、标准库与命令行速查。
---

# 语法与标准库速查表

按阶段反查知识点；点标题可跳回对应讲次看完整示例与逐行拆解。

## 常用命令

| 目的 | 命令 |
| --- | --- |
| 创建隔离环境 | `python -m venv .venv` |
| 安装依赖 | `python -m pip install -r requirements.txt` |
| 运行单测 | `python -m pytest -q` |
| 格式化与检查 | `ruff check . && ruff format .` |
| 类型检查 | `mypy src` 或 `pyright` |
| 反汇编 | `python -m dis demo.py` |
| 导入耗时 | `python -X importtime demo.py` |
| 性能剖析 | `python -m cProfile -s cumtime demo.py` |
| 构建发布包 | `python -m build && twine check dist/*` |
| 本地预览站点 | `npm run dev`（本教程站点） |

## 高频内置函数与协议

| 分类 | 成员 |
| --- | --- |
| 容器 | `list` / `dict` / `set` / `tuple` / `deque` / `Counter` / `defaultdict` |
| 迭代 | `iter` / `next` / `enumerate` / `zip` / `itertools` / `yield` |
| 函数 | `map` / `filter` / `functools.partial` / `lru_cache` / `wraps` / `singledispatch` |
| 对象 | `property` / `__get__` / `__slots__` / `__init_subclass__` / `dataclass` |
| 运行时 | `dis` / `inspect` / `gc` / `weakref` / `tracemalloc` / `sys.modules` |
| 并发 | `threading` / `concurrent.futures` / `multiprocessing` / `asyncio` |
| 工程 | `logging` / `pathlib` / `argparse` / `tomllib` / `importlib` |

### 导学 · 建立地图

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 001 | [开篇：Python 是什么，为什么值得学](/guide/opening) | Python 的诞生与设计哲学 / 动态强类型与解释执行 / 适用边界与典型场景 |
| 002 | [环境与工具链：解释器、虚拟环境与编辑器](/guide/setup) | CPython 与 PyPy 等实现 / pyenv / uv 的版本管理 / venv 与依赖隔离 |
| 003 | [第一行 Python：从源码到字节码再到执行](/guide/hello) | 脚本与交互式解释器 / 词法分析与语法树 / compile 与 code object |
| 004 | [工具链全景：写代码、查问题、验质量](/guide/toolchain) | python -m 的正确用法 / pip / uv 依赖操作 / ruff 与 black 格式化 |
| 005 | [学习路线：十三个阶段如何递进](/guide/roadmap) | 认知负担与阶段顺序 / 语言基础到运行时的跃迁 / 并发与工程化的分界 |

### 阶段一 · 编程地基

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 006 | [一切皆对象：id、type、value 与可变性](/foundation/object-model) | 对象的三要素 / id 与 is 的语义 / type 与 isinstance |
| 007 | [变量是名字绑定：赋值、引用与命名规范](/foundation/variables) | 赋值即绑定 / 链式与解包赋值 / 星号解包 |
| 008 | [数值体系：int 任意精度、float、Decimal 与 bool](/foundation/numeric) | int 的任意精度实现 / float 与 IEEE 754 / 浮点误差与 math.isclose |
| 009 | [字符串与编码：Unicode、str / bytes 与转义](/foundation/strings) | Unicode 码点与编码 / str 与 bytes 的边界 / encode / decode |
| 010 | [字符串操作：切片、f-string 与常用方法](/foundation/string-ops) | 索引与切片规则 / f-string 与格式规范 / str 常用方法 |
| 011 | [运算符与表达式：优先级、短路与真值](/foundation/operators) | 算术与整除 / 比较链 / 布尔短路与返回值 |
| 012 | [分支：if / elif / else 与 match-case](/foundation/control-flow) | 条件表达式与嵌套 / match-case 结构模式 / 守卫与捕获 |
| 013 | [循环：for / while、range 与循环 else](/foundation/loops) | for 基于迭代协议 / range 是惰性序列 / break / continue / else |
| 014 | [输入输出与文件初识：print、input、open、with](/foundation/io) | print 的 sep / end / file / input 与类型转换 / open 的模式与编码 |
| 015 | [异常：捕获、异常链与自定义异常](/foundation/exceptions) | 异常层级与 BaseException / try / except / else / finally / raise from 与异常链 |
| 016 | [阶段综合：交互式命令行计算器](/foundation/capstone) | 需求拆解与输入循环 / 表达式求值的安全边界 / 异常驱动的重试 |

### 阶段二 · 容器与序列

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 017 | [序列协议与通用操作](/containers/sequence) | 序列与可迭代的区别 / __len__ 与 __getitem__ / 索引与切片协议 |
| 018 | [list：动态数组、操作与时间复杂度](/containers/list-basics) | 列表的连续存储 / append 与扩容摊还 / insert / pop 的代价 |
| 019 | [list 进阶：切片赋值、排序与常见陷阱](/containers/list-advanced) | 切片赋值与步长 / sort 与 sorted / key 函数与稳定性 |
| 020 | [tuple 与具名元组：不可变性的价值](/containers/tuple) | 元组与单元素写法 / 不可变是浅层的 / 具名元组 NamedTuple |
| 021 | [dict：哈希表、视图与插入顺序](/containers/dict-basics) | 哈希与开放寻址 / 键的可哈希要求 / 插入顺序保证 |
| 022 | [dict 进阶：默认字典、计数器与合并](/containers/dict-advanced) | defaultdict 工厂 / Counter 计数 / ChainMap 分层配置 |
| 023 | [set / frozenset：哈希、集合运算与去重](/containers/set) | 集合的哈希实现 / 增删与运算 / frozenset 可哈希 |
| 024 | [推导式：四种写法与可读性边界](/containers/comprehension) | 列表 / 集合 / 字典推导式 / 生成器表达式 / 多重 for 与过滤 |
| 025 | [迭代协议：iterable、iterator 与惰性求值](/containers/iterator) | __iter__ 与 __next__ / iter() 的两个参数形式 / StopIteration |
| 026 | [生成器与 yield：send / throw / close](/containers/generator) | 生成器函数与 yield / 执行暂停与恢复 / send 与双向通信 |
| 027 | [阶段综合：词频统计与内存版 KV](/containers/capstone) | 文本规整与分词 / Counter 与排序 / 生成器管道 |

### 阶段三 · 函数与抽象

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 028 | [函数定义与参数形态](/functions/function-basics) | 位置与关键字参数 / 默认值与仅位置 / 仅关键字 / *args 与 **kwargs |
| 029 | [返回值、None 与多返回值](/functions/returns) | 隐式 return None / 元组打包与解包 / 提前返回 |
| 030 | [作用域、LEGB 与闭包延迟绑定](/functions/scope) | LEGB 查找顺序 / global 与 nonlocal / 闭包与自由变量 |
| 031 | [高阶函数、lambda 与 map / filter / reduce](/functions/higher-order) | 函数作为值 / map / filter 的惰性 / functools.reduce |
| 032 | [装饰器原理与 functools.wraps](/functions/decorator) | 装饰器即函数替换 / @ 语法的求值时机 / wraps 保留元数据 |
| 033 | [带参装饰器、叠加顺序与类装饰器](/functions/decorator-params) | 三层函数结构 / 叠加顺序由近及远 / 类作为装饰器 |
| 034 | [偏函数、可调用对象与函数式工具](/functions/partial) | functools.partial / lru_cache 与缓存策略 / singledispatch 分派 |
| 035 | [模块与包：import 机制与循环导入](/functions/modules) | 模块对象与 sys.modules / 搜索路径与 finder / 绝对与相对导入 |
| 036 | [类型注解、typing 与渐进式类型](/functions/typing) | 注解不强制运行时检查 / 泛型与 TypeVar / Optional / Union |
| 037 | [阶段综合：缓存装饰器库与插件注册表](/functions/capstone) | 装饰器组合设计 / 注册表与入口点 / TTL 与淘汰策略 |

### 阶段四 · 面向对象与元编程

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 038 | [类与实例：__init__、self 与属性](/oop/class-basics) | 类对象与实例对象 / __init__ 不是构造函数 / 实例字典 __dict__ |
| 039 | [属性查找、MRO 与 super](/oop/mro) | __mro__ 与 C3 线性化 / super 的真实语义 / 菱形继承 |
| 040 | [访问控制、property 与描述符协议](/oop/property) | 名称改写与私有约定 / property 的 getter / setter / 数据描述符与非数据描述符 |
| 041 | [特殊方法：repr、比较、算术与容器协议](/oop/special-methods) | __repr__ 与 __str__ / __eq__ 与 __hash__ 联动 / functools.total_ordering |
| 042 | [上下文管理器与 with 协议](/oop/context) | __enter__ / __exit__ / 异常三参数与抑制 / contextlib.contextmanager |
| 043 | [__slots__、弱引用与对象内存布局](/oop/slots) | __dict__ 的开销 / __slots__ 的约束 / weakref 与 __weakref__ |
| 044 | [鸭子类型、抽象基类与 Protocol](/oop/abc) | 鸭子类型与 EAFP / abc.ABC 与 abstractmethod / 虚拟子类 register |
| 045 | [元类：__new__、type 与类创建过程](/oop/metaclass) | 类也是对象 / type 的三参数形式 / __new__ 与 __init__ 分工 |
| 046 | [反射与自省：getattr、inspect 与 __dict__](/oop/introspection) | getattr / setattr / hasattr / inspect.signature 与 getmembers / __dict__ 与 vars |
| 047 | [dataclass、attrs 与 pydantic 模型](/oop/dataclass) | dataclass 生成了什么 / field 与 default_factory / frozen 与 order |
| 048 | [阶段综合：最小 ORM 与校验框架](/oop/capstone) | 字段描述符 / 元类收集映射 / 实例状态存储 |

### 阶段五 · 核心机制与运行时

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 049 | [CPython 编译流程：AST 到字节码](/core/compile-pipeline) | 词法与语法分析 / ast 模块与 ast.dump / compile 内置函数 |
| 050 | [字节码、栈式虚拟机与 dis 实战](/core/bytecode) | 栈式指令与 LOAD / STORE / 常见指令速查 / 闭包与 LOAD_DEREF |
| 051 | [帧、调用栈与命名空间](/core/frames) | 帧对象与 f_locals / f_globals / 调用栈与递归深度 / sys.setprofile 与 tracing |
| 052 | [对象内存布局、引用计数与小对象池](/core/memory) | PyObject 头与 ob_refcnt / 引用计数增减时机 / 小整数与字符串驻留 |
| 053 | [分代 GC、循环引用与 weakref](/core/gc) | 循环引用为何计数失效 / 三代与阈值 / gc.collect 的时机 |
| 054 | [GIL 真相：存在原因、切换与影响边界](/core/gil) | GIL 保护什么 / 切换间隔与字节码边界 / IO 释放 GIL |
| 055 | [导入系统源码级：finder、loader 与缓存](/core/import-system) | sys.meta_path 与 path_hooks / Finder / Loader 协议 / sys.modules 缓存 |
| 056 | [属性访问链路与 __getattribute__](/core/attribute-lookup) | __getattribute__ 总入口 / 数据描述符优先 / 实例字典 |
| 057 | [可变性、深浅拷贝与共享状态](/core/copy) | 赋值 / 浅拷贝 / 深拷贝 / copy 与 deepcopy 协议 / 循环结构处理 |
| 058 | [性能剖析：timeit、cProfile 与 tracemalloc](/core/profiling) | 测量优先于猜测 / timeit 的正确姿势 / cProfile / pstats 火焰数据 |
| 059 | [阶段综合：简易性能分析器与内存哨兵](/core/capstone) | sys.setprofile 采集 / 调用树与自耗时 / tracemalloc 快照 |

### 阶段六 · 并发与异步

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 060 | [并发、并行与 IO 模型全景](/concurrency/concurrency-intro) | 并发与并行的区别 / CPU 密集 / IO 密集 / 同步异步与阻塞非阻塞 |
| 061 | [threading：线程生命周期与共享状态](/concurrency/threading) | Thread 与 daemon / 线程局部存储 / 共享变量的可见性 |
| 062 | [线程同步：Lock、Condition、Semaphore、Event](/concurrency/sync-primitives) | Lock 与 RLock / Condition 等待通知 / Semaphore 限流 |
| 063 | [线程池与 Future 模式](/concurrency/threadpool) | Executor 抽象 / submit / map / as_completed / Future 状态机 |
| 064 | [multiprocessing：进程、Pool 与共享内存](/concurrency/multiprocessing) | fork / spawn / forkserver / 进程间不共享内存 / 序列化 pickle 成本 |
| 065 | [进程间通信：Queue、Pipe 与信号](/concurrency/ipc) | Queue 与 Pipe 语义 / Manager 代理对象 / 共享 ctypes 值 |
| 066 | [IO 多路复用：select / poll / epoll](/concurrency/io-multiplex) | 阻塞与非阻塞 IO / select / poll / epoll 对比 / 水平与边缘触发 |
| 067 | [生成器协程：send、yield from 与调度器](/concurrency/generator-coroutine) | 生成器双向通信 / yield from 委托 / 用生成器写调度器 |
| 068 | [async / await 与协程对象](/concurrency/async-await) | coroutine 与 async function / await 只能用在 async 内 / awaitable 协议 |
| 069 | [asyncio 深入：Task、Future 与事件循环](/concurrency/asyncio) | loop 与策略 / create_task 与 gather / Future 状态 |
| 070 | [阶段综合：并发爬虫四级演进](/concurrency/capstone) | 串行基线 / 线程池版本 / asyncio + 连接池 |

### 阶段七 · 工程化与质量

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 071 | [项目结构与 src 布局](/engineering/layout) | src 与扁平布局对比 / 包与模块命名 / 内部模块分层 |
| 072 | [依赖管理：venv、uv、锁文件与可复现构建](/engineering/deps) | pyproject.toml 规范 / 直接与传递依赖 / 约束文件与锁 |
| 073 | [代码规范：PEP 8、ruff、black 与 pre-commit](/engineering/style) | PEP 8 的取舍 / ruff 规则集 / 格式化与 lint 分工 |
| 074 | [静态检查：mypy / pyright 与渐进式类型](/engineering/typecheck) | 检查器配置与严格度 / stub 与第三方库 / 泛型与不变性 |
| 075 | [单元测试：pytest、fixture 与参数化](/engineering/pytest) | 断言重写 / fixture 作用域 / 参数化与 mark |
| 076 | [Mock 与测试替身：时间、网络与随机](/engineering/mock) | unittest.mock 与 patch 位置 / monkeypatch / freezegun 与时钟注入 |
| 077 | [属性测试、基准测试与模糊测试](/engineering/property-testing) | hypothesis 策略 / 收缩到最小反例 / 状态机测试 |
| 078 | [日志：logging、结构化日志与追踪关联](/engineering/logging) | Logger / Handler / Formatter / 级别与传播 / 结构化 JSON |
| 079 | [配置管理：环境变量、.env 与配置中心](/engineering/config) | 十二要素与环境变量 / pydantic-settings 校验 / 分层覆盖 |
| 080 | [打包与发布：pyproject、wheel 与 PyPI](/engineering/packaging) | 构建后端与 PEP 517 / wheel / sdist 差别 / 入口点 console_scripts |
| 081 | [阶段综合：把脚本重构成可发布包](/engineering/capstone) | 目录重构 / 依赖锁定 / 类型与规范 |

### 阶段八 · 服务端与数据

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 082 | [HTTP 协议与 WSGI / ASGI](/server/http-wsgi) | 请求响应模型 / WSGI 可调用对象 / ASGI 与 async 三参数 |
| 083 | [FastAPI / Flask / Django 选型](/server/frameworks) | 三者定位差异 / 路由与依赖注入 / 校验与序列化 |
| 084 | [路由、依赖注入与请求校验](/server/routing) | 路径与查询参数 / 请求体与 Pydantic 模型 / 依赖树与缓存 |
| 085 | [REST API 设计、OpenAPI 与幂等](/server/rest-api) | 资源与动词 / 状态码语义 / 分页与过滤 |
| 086 | [WebSocket / SSE / 长轮询与实时推送](/server/websocket) | 三种通道对比 / 握手与帧 / SSE 与断线重连 |
| 087 | [SQLAlchemy、连接池、事务与迁移](/server/orm) | Engine / Session / Unit of Work / 连接池参数 / 事务边界与隔离级别 |
| 088 | [Redis 缓存：穿透、击穿、雪崩与分布式锁](/server/redis) | 五种数据结构与选型 / 缓存模式与失效 / 穿透 / 击穿 / 雪崩 |
| 089 | [消息队列：Celery / RabbitMQ / Kafka](/server/mq) | 队列与发布订阅 / 至少一次与恰好一次的真相 / 确认与重试 |
| 090 | [认证授权：Session、JWT、OAuth2 与 RBAC](/server/auth) | 认证与授权的区别 / Session 与 JWT 取舍 / 令牌刷新与撤销 |
| 091 | [文件、对象存储、搜索与 gRPC](/server/storage) | 上传与断点续传 / 预签名 URL / 对象存储一致性 |
| 092 | [阶段综合：生产级短链服务](/server/capstone) | 发号与 Base62 / 路由与重定向 / 缓存与限流 |

### 阶段九 · 数据科学与 AI 工程

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 093 | [NumPy 向量化、广播与内存布局](/data-ai/numpy) | ndarray 与 dtype / shape / stride 与视图 / 广播规则 |
| 094 | [Pandas 清洗、分组、透视与时间序列](/data-ai/pandas) | Series 与 DataFrame 索引 / 缺失值与重复 / groupby / agg / transform |
| 095 | [可视化：Matplotlib / Seaborn / Plotly 与图表选型](/data-ai/visualization) | 图表类型与数据关系 / Figure / Axes 对象模型 / 配色与可读性 |
| 096 | [统计基础：分布、检验与相关性](/data-ai/statistics) | 描述统计与离群点 / 常见分布 / 抽样与中心极限定理 |
| 097 | [机器学习流程：特征、划分与评价](/data-ai/ml-workflow) | 训练集 / 验证集 / 测试集 / 数据泄漏 / 特征工程与缩放 |
| 098 | [经典算法：KNN、线性与逻辑回归](/data-ai/linear-models) | KNN 与距离度量 / 最小二乘与梯度下降 / 多项式回归与过拟合 |
| 099 | [SVM、核方法、决策树与随机森林](/data-ai/svm-trees) | 间隔最大化与核技巧 / 软间隔与 C / 树的划分准则 |
| 100 | [集成学习：Boosting、XGBoost 与 LightGBM](/data-ai/ensemble) | Bagging 与 Boosting 差异 / AdaBoost / GBDT 思路 / 梯度提升的残差拟合 |
| 101 | [无监督学习：KMeans、DBSCAN、PCA 与异常检测](/data-ai/unsupervised) | 聚类假设与尺度 / KMeans 与 K 的选择 / DBSCAN 与密度 |
| 102 | [模型调优：交叉验证、正则化与过拟合](/data-ai/model-tuning) | 偏差方差分解 / 学习曲线与验证曲线 / 网格 / 随机 / 贝叶斯搜索 |
| 103 | [深度学习与 PyTorch：张量、自动微分与训练循环](/data-ai/deep-learning) | 张量与设备 / 计算图与 autograd / Dataset / DataLoader |
| 104 | [LLM 应用工程：Prompt、RAG、Agent 与成本](/data-ai/llm-engineering) | Prompt 与结构化输出 / Embedding 与向量检索 / RAG 分块与召回评估 |

### 阶段十 · 分布式与云原生

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 105 | [CAP / BASE 与一致性模型](/distributed/cap-base) | CAP 的正确表述 / 强一致与最终一致 / 读写一致性 |
| 106 | [幂等、分布式锁与限流](/distributed/idempotency) | 幂等键设计 / 去重表与唯一索引 / 分布式锁实现 |
| 107 | [分布式事务：2PC / TCC / Saga / 消息最终一致](/distributed/dist-tx) | 本地事务边界 / 2PC 的阻塞问题 / TCC 三阶段 |
| 108 | [分布式 ID、一致性哈希与分片](/distributed/sharding) | 自增 ID 的局限 / 雪花算法与时钟回拨 / 范围与哈希分片 |
| 109 | [Raft 共识、服务发现与配置中心](/distributed/consensus) | Leader 选举与日志复制 / 多数派与任期 / 成员变更 |
| 110 | [容器化与 Kubernetes 部署](/distributed/docker-k8s) | 镜像分层与多阶段构建 / 依赖与基础镜像瘦身 / 非 root 与只读文件系统 |
| 111 | [GitOps、灰度发布与可观测平台](/distributed/gitops) | 声明式与期望状态 / Helm / Kustomize / 金丝雀与蓝绿 |
| 112 | [任务调度、SRE 与混沌工程](/distributed/scheduling) | 定时与依赖调度 / Airflow / Temporal 选型 / 重试与补数 |
| 113 | [安全工程：依赖、注入、序列化与密钥](/distributed/security) | 依赖漏洞与 SBOM / 注入与参数化 / 不安全的反序列化 |

### 阶段十一 · 资深进阶与源码

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 114 | [CPython 源码：对象、帧与求值循环](/advanced/cpython-source) | 源码目录结构 / PyObject 与类型对象 / ceval.c 主循环 |
| 115 | [内存分配器 pymalloc 与 GC 源码](/advanced/allocator) | arena / pool / block 三级 / 小对象分配路径 / 分代 GC 触发逻辑 |
| 116 | [导入系统源码与 import hook](/advanced/import-source) | importlib._bootstrap / find_spec / exec_module / 路径钩子 |
| 117 | [asyncio 事件循环与 Task 源码](/advanced/asyncio-source) | BaseEventLoop 与 selector / Handle / TimerHandle / Task.__step |
| 118 | [GIL 源码、自适应解释器与无 GIL 路线](/advanced/gil-source) | GIL 的获取与释放点 / 切换请求与 eval breaker / 3.11 自适应特化 |
| 119 | [极致优化：从剖析到 C 扩展的十倍案例](/advanced/optimization) | 先算法后实现 / 数据结构与批处理 / 向量化与 NumPy |
| 120 | [架构设计：领域分层、演进与重构](/advanced/architecture) | 变化方向与边界 / 依赖倒置与端口适配器 / 模块化单体到服务拆分 |
| 121 | [资深能力图谱、技术选型与持续精进](/advanced/senior-path) | 能力矩阵与短板 / 选型评估维度 / 读源码与写技术提案 |

### 阶段十二 · 工程实战

| 讲次 | 主题 | 关键知识点 |
| --- | --- | --- |
| 122 | [实战 01 · 待办清单 CLI 与命令分发](/projects/cli-todo) | 命令解析 argparse / click / 数据模型与 JSON 持久化 / 原子写入 |
| 123 | [实战 02 · 文件检索、日志与自动化办公](/projects/office-files) | pathlib 遍历与 glob / os.walk 与元数据 / 按类型容量统计 |
| 124 | [实战 03 · 邮件、PDF、Excel、Word 与图像视频](/projects/office-docs) | smtplib / yagmail 与授权码 / pypdf 拆分合并 / openpyxl / pandas 读写表格 |
| 125 | [实战 04 · Selenium 表单自动化与定时任务](/projects/browser-auto) | WebDriver 与等待策略 / 元素定位 XPath / CSS / 显式等待与隐式等待 |
| 126 | [实战 05 · 短链与图片服务](/projects/net-shortlink) | 发号与 Base62 / 301 / 302 语义 / 缓存与防刷 |
| 127 | [实战 06 · 日志 ETL 与 CSV / SQL 查询工具](/projects/data-etl) | 生成器管道与背压 / 解析与脏数据隔离 / 窗口聚合 |
| 128 | [实战 07 · 并发爬虫与分布式调度](/projects/concurrent-crawler) | 串行基线到 asyncio / 连接池与限流 / URL 去重与优先级 |
| 129 | [实战 08 · KV 贯穿线 ① 内存版与接口抽象](/projects/kv-memory) | 命令模型与协议设计 / 存储引擎接口 / 内存实现与过期 |
| 130 | [实战 09 · KV 贯穿线 ② 协议帧与网络层](/projects/kv-network) | TCP 粘包与长度前缀 / 序列化选型 / asyncio start_server |
| 131 | [实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制](/projects/kv-wal) | 追加写与 fsync / WAL 记录格式 / 重放与检查点 |
| 132 | [实战 11 · 分片复制、AI 网关与能力收束](/projects/kv-distributed) | 分片与路由 / 副本与读写 quorum / 故障转移 |

