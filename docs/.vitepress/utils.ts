/** 由 tools/course/gen_course.py 生成；进度相关的函数保持手写。 */
/** 学习进度：全部保存在浏览器本地，SSR 安全 */
import { withBase } from 'vitepress'

export type Stage = 'L0' | 'L1' | 'L2' | 'L3' | 'L4' | 'L5' | 'L6' | 'L7' | 'L8' | 'L9' | 'L10' | 'L11' | 'L12'

export interface Lesson { path: string; title: string; stage: Stage }

/** 可打卡页面清单：13 个阶段导览 + 132 讲 + 课程总目录 + 附录页。 */
export const LESSONS: Lesson[] = [
  { path: '/guide/', title: '阶段导览 · 导学', stage: 'L0' },
  { path: '/foundation/', title: '阶段导览 · 编程地基', stage: 'L1' },
  { path: '/containers/', title: '阶段导览 · 容器与序列', stage: 'L2' },
  { path: '/functions/', title: '阶段导览 · 函数与抽象', stage: 'L3' },
  { path: '/oop/', title: '阶段导览 · 面向对象', stage: 'L4' },
  { path: '/core/', title: '阶段导览 · 核心机制', stage: 'L5' },
  { path: '/concurrency/', title: '阶段导览 · 并发与异步', stage: 'L6' },
  { path: '/engineering/', title: '阶段导览 · 工程化', stage: 'L7' },
  { path: '/server/', title: '阶段导览 · 服务端与数据', stage: 'L8' },
  { path: '/data-ai/', title: '阶段导览 · 数据与 AI', stage: 'L9' },
  { path: '/distributed/', title: '阶段导览 · 分布式云原生', stage: 'L10' },
  { path: '/advanced/', title: '阶段导览 · 资深进阶', stage: 'L11' },
  { path: '/projects/', title: '阶段导览 · 工程实战', stage: 'L12' },
  { path: '/guide/opening', title: '第 001 讲 · 开篇：Python 是什么，为什么值得学', stage: 'L0' },
  { path: '/guide/setup', title: '第 002 讲 · 环境与工具链：解释器、虚拟环境与编辑器', stage: 'L0' },
  { path: '/guide/hello', title: '第 003 讲 · 第一行 Python：从源码到字节码再到执行', stage: 'L0' },
  { path: '/guide/toolchain', title: '第 004 讲 · 工具链全景：写代码、查问题、验质量', stage: 'L0' },
  { path: '/guide/roadmap', title: '第 005 讲 · 学习路线：十三个阶段如何递进', stage: 'L0' },
  { path: '/foundation/object-model', title: '第 006 讲 · 一切皆对象：id、type、value 与可变性', stage: 'L1' },
  { path: '/foundation/variables', title: '第 007 讲 · 变量是名字绑定：赋值、引用与命名规范', stage: 'L1' },
  { path: '/foundation/numeric', title: '第 008 讲 · 数值体系：int 任意精度、float、Decimal 与 bool', stage: 'L1' },
  { path: '/foundation/strings', title: '第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义', stage: 'L1' },
  { path: '/foundation/string-ops', title: '第 010 讲 · 字符串操作：切片、f-string 与常用方法', stage: 'L1' },
  { path: '/foundation/operators', title: '第 011 讲 · 运算符与表达式：优先级、短路与真值', stage: 'L1' },
  { path: '/foundation/control-flow', title: '第 012 讲 · 分支：if / elif / else 与 match-case', stage: 'L1' },
  { path: '/foundation/loops', title: '第 013 讲 · 循环：for / while、range 与循环 else', stage: 'L1' },
  { path: '/foundation/io', title: '第 014 讲 · 输入输出与文件初识：print、input、open、with', stage: 'L1' },
  { path: '/foundation/exceptions', title: '第 015 讲 · 异常：捕获、异常链与自定义异常', stage: 'L1' },
  { path: '/foundation/capstone', title: '第 016 讲 · 阶段综合：交互式命令行计算器', stage: 'L1' },
  { path: '/containers/sequence', title: '第 017 讲 · 序列协议与通用操作', stage: 'L2' },
  { path: '/containers/list-basics', title: '第 018 讲 · list：动态数组、操作与时间复杂度', stage: 'L2' },
  { path: '/containers/list-advanced', title: '第 019 讲 · list 进阶：切片赋值、排序与常见陷阱', stage: 'L2' },
  { path: '/containers/tuple', title: '第 020 讲 · tuple 与具名元组：不可变性的价值', stage: 'L2' },
  { path: '/containers/dict-basics', title: '第 021 讲 · dict：哈希表、视图与插入顺序', stage: 'L2' },
  { path: '/containers/dict-advanced', title: '第 022 讲 · dict 进阶：默认字典、计数器与合并', stage: 'L2' },
  { path: '/containers/set', title: '第 023 讲 · set / frozenset：哈希、集合运算与去重', stage: 'L2' },
  { path: '/containers/comprehension', title: '第 024 讲 · 推导式：四种写法与可读性边界', stage: 'L2' },
  { path: '/containers/iterator', title: '第 025 讲 · 迭代协议：iterable、iterator 与惰性求值', stage: 'L2' },
  { path: '/containers/generator', title: '第 026 讲 · 生成器与 yield：send / throw / close', stage: 'L2' },
  { path: '/containers/capstone', title: '第 027 讲 · 阶段综合：词频统计与内存版 KV', stage: 'L2' },
  { path: '/functions/function-basics', title: '第 028 讲 · 函数定义与参数形态', stage: 'L3' },
  { path: '/functions/returns', title: '第 029 讲 · 返回值、None 与多返回值', stage: 'L3' },
  { path: '/functions/scope', title: '第 030 讲 · 作用域、LEGB 与闭包延迟绑定', stage: 'L3' },
  { path: '/functions/higher-order', title: '第 031 讲 · 高阶函数、lambda 与 map / filter / reduce', stage: 'L3' },
  { path: '/functions/decorator', title: '第 032 讲 · 装饰器原理与 functools.wraps', stage: 'L3' },
  { path: '/functions/decorator-params', title: '第 033 讲 · 带参装饰器、叠加顺序与类装饰器', stage: 'L3' },
  { path: '/functions/partial', title: '第 034 讲 · 偏函数、可调用对象与函数式工具', stage: 'L3' },
  { path: '/functions/modules', title: '第 035 讲 · 模块与包：import 机制与循环导入', stage: 'L3' },
  { path: '/functions/typing', title: '第 036 讲 · 类型注解、typing 与渐进式类型', stage: 'L3' },
  { path: '/functions/capstone', title: '第 037 讲 · 阶段综合：缓存装饰器库与插件注册表', stage: 'L3' },
  { path: '/oop/class-basics', title: '第 038 讲 · 类与实例：__init__、self 与属性', stage: 'L4' },
  { path: '/oop/mro', title: '第 039 讲 · 属性查找、MRO 与 super', stage: 'L4' },
  { path: '/oop/property', title: '第 040 讲 · 访问控制、property 与描述符协议', stage: 'L4' },
  { path: '/oop/special-methods', title: '第 041 讲 · 特殊方法：repr、比较、算术与容器协议', stage: 'L4' },
  { path: '/oop/context', title: '第 042 讲 · 上下文管理器与 with 协议', stage: 'L4' },
  { path: '/oop/slots', title: '第 043 讲 · __slots__、弱引用与对象内存布局', stage: 'L4' },
  { path: '/oop/abc', title: '第 044 讲 · 鸭子类型、抽象基类与 Protocol', stage: 'L4' },
  { path: '/oop/metaclass', title: '第 045 讲 · 元类：__new__、type 与类创建过程', stage: 'L4' },
  { path: '/oop/introspection', title: '第 046 讲 · 反射与自省：getattr、inspect 与 __dict__', stage: 'L4' },
  { path: '/oop/dataclass', title: '第 047 讲 · dataclass、attrs 与 pydantic 模型', stage: 'L4' },
  { path: '/oop/capstone', title: '第 048 讲 · 阶段综合：最小 ORM 与校验框架', stage: 'L4' },
  { path: '/core/compile-pipeline', title: '第 049 讲 · CPython 编译流程：AST 到字节码', stage: 'L5' },
  { path: '/core/bytecode', title: '第 050 讲 · 字节码、栈式虚拟机与 dis 实战', stage: 'L5' },
  { path: '/core/frames', title: '第 051 讲 · 帧、调用栈与命名空间', stage: 'L5' },
  { path: '/core/memory', title: '第 052 讲 · 对象内存布局、引用计数与小对象池', stage: 'L5' },
  { path: '/core/gc', title: '第 053 讲 · 分代 GC、循环引用与 weakref', stage: 'L5' },
  { path: '/core/gil', title: '第 054 讲 · GIL 真相：存在原因、切换与影响边界', stage: 'L5' },
  { path: '/core/import-system', title: '第 055 讲 · 导入系统源码级：finder、loader 与缓存', stage: 'L5' },
  { path: '/core/attribute-lookup', title: '第 056 讲 · 属性访问链路与 __getattribute__', stage: 'L5' },
  { path: '/core/copy', title: '第 057 讲 · 可变性、深浅拷贝与共享状态', stage: 'L5' },
  { path: '/core/profiling', title: '第 058 讲 · 性能剖析：timeit、cProfile 与 tracemalloc', stage: 'L5' },
  { path: '/core/capstone', title: '第 059 讲 · 阶段综合：简易性能分析器与内存哨兵', stage: 'L5' },
  { path: '/concurrency/concurrency-intro', title: '第 060 讲 · 并发、并行与 IO 模型全景', stage: 'L6' },
  { path: '/concurrency/threading', title: '第 061 讲 · threading：线程生命周期与共享状态', stage: 'L6' },
  { path: '/concurrency/sync-primitives', title: '第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event', stage: 'L6' },
  { path: '/concurrency/threadpool', title: '第 063 讲 · 线程池与 Future 模式', stage: 'L6' },
  { path: '/concurrency/multiprocessing', title: '第 064 讲 · multiprocessing：进程、Pool 与共享内存', stage: 'L6' },
  { path: '/concurrency/ipc', title: '第 065 讲 · 进程间通信：Queue、Pipe 与信号', stage: 'L6' },
  { path: '/concurrency/io-multiplex', title: '第 066 讲 · IO 多路复用：select / poll / epoll', stage: 'L6' },
  { path: '/concurrency/generator-coroutine', title: '第 067 讲 · 生成器协程：send、yield from 与调度器', stage: 'L6' },
  { path: '/concurrency/async-await', title: '第 068 讲 · async / await 与协程对象', stage: 'L6' },
  { path: '/concurrency/asyncio', title: '第 069 讲 · asyncio 深入：Task、Future 与事件循环', stage: 'L6' },
  { path: '/concurrency/capstone', title: '第 070 讲 · 阶段综合：并发爬虫四级演进', stage: 'L6' },
  { path: '/engineering/layout', title: '第 071 讲 · 项目结构与 src 布局', stage: 'L7' },
  { path: '/engineering/deps', title: '第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建', stage: 'L7' },
  { path: '/engineering/style', title: '第 073 讲 · 代码规范：PEP 8、ruff、black 与 pre-commit', stage: 'L7' },
  { path: '/engineering/typecheck', title: '第 074 讲 · 静态检查：mypy / pyright 与渐进式类型', stage: 'L7' },
  { path: '/engineering/pytest', title: '第 075 讲 · 单元测试：pytest、fixture 与参数化', stage: 'L7' },
  { path: '/engineering/mock', title: '第 076 讲 · Mock 与测试替身：时间、网络与随机', stage: 'L7' },
  { path: '/engineering/property-testing', title: '第 077 讲 · 属性测试、基准测试与模糊测试', stage: 'L7' },
  { path: '/engineering/logging', title: '第 078 讲 · 日志：logging、结构化日志与追踪关联', stage: 'L7' },
  { path: '/engineering/config', title: '第 079 讲 · 配置管理：环境变量、.env 与配置中心', stage: 'L7' },
  { path: '/engineering/packaging', title: '第 080 讲 · 打包与发布：pyproject、wheel 与 PyPI', stage: 'L7' },
  { path: '/engineering/capstone', title: '第 081 讲 · 阶段综合：把脚本重构成可发布包', stage: 'L7' },
  { path: '/server/http-wsgi', title: '第 082 讲 · HTTP 协议与 WSGI / ASGI', stage: 'L8' },
  { path: '/server/frameworks', title: '第 083 讲 · FastAPI / Flask / Django 选型', stage: 'L8' },
  { path: '/server/routing', title: '第 084 讲 · 路由、依赖注入与请求校验', stage: 'L8' },
  { path: '/server/rest-api', title: '第 085 讲 · REST API 设计、OpenAPI 与幂等', stage: 'L8' },
  { path: '/server/websocket', title: '第 086 讲 · WebSocket / SSE / 长轮询与实时推送', stage: 'L8' },
  { path: '/server/orm', title: '第 087 讲 · SQLAlchemy、连接池、事务与迁移', stage: 'L8' },
  { path: '/server/redis', title: '第 088 讲 · Redis 缓存：穿透、击穿、雪崩与分布式锁', stage: 'L8' },
  { path: '/server/mq', title: '第 089 讲 · 消息队列：Celery / RabbitMQ / Kafka', stage: 'L8' },
  { path: '/server/auth', title: '第 090 讲 · 认证授权：Session、JWT、OAuth2 与 RBAC', stage: 'L8' },
  { path: '/server/storage', title: '第 091 讲 · 文件、对象存储、搜索与 gRPC', stage: 'L8' },
  { path: '/server/capstone', title: '第 092 讲 · 阶段综合：生产级短链服务', stage: 'L8' },
  { path: '/data-ai/numpy', title: '第 093 讲 · NumPy 向量化、广播与内存布局', stage: 'L9' },
  { path: '/data-ai/pandas', title: '第 094 讲 · Pandas 清洗、分组、透视与时间序列', stage: 'L9' },
  { path: '/data-ai/visualization', title: '第 095 讲 · 可视化：Matplotlib / Seaborn / Plotly 与图表选型', stage: 'L9' },
  { path: '/data-ai/statistics', title: '第 096 讲 · 统计基础：分布、检验与相关性', stage: 'L9' },
  { path: '/data-ai/ml-workflow', title: '第 097 讲 · 机器学习流程：特征、划分与评价', stage: 'L9' },
  { path: '/data-ai/linear-models', title: '第 098 讲 · 经典算法：KNN、线性与逻辑回归', stage: 'L9' },
  { path: '/data-ai/svm-trees', title: '第 099 讲 · SVM、核方法、决策树与随机森林', stage: 'L9' },
  { path: '/data-ai/ensemble', title: '第 100 讲 · 集成学习：Boosting、XGBoost 与 LightGBM', stage: 'L9' },
  { path: '/data-ai/unsupervised', title: '第 101 讲 · 无监督学习：KMeans、DBSCAN、PCA 与异常检测', stage: 'L9' },
  { path: '/data-ai/model-tuning', title: '第 102 讲 · 模型调优：交叉验证、正则化与过拟合', stage: 'L9' },
  { path: '/data-ai/deep-learning', title: '第 103 讲 · 深度学习与 PyTorch：张量、自动微分与训练循环', stage: 'L9' },
  { path: '/data-ai/llm-engineering', title: '第 104 讲 · LLM 应用工程：Prompt、RAG、Agent 与成本', stage: 'L9' },
  { path: '/distributed/cap-base', title: '第 105 讲 · CAP / BASE 与一致性模型', stage: 'L10' },
  { path: '/distributed/idempotency', title: '第 106 讲 · 幂等、分布式锁与限流', stage: 'L10' },
  { path: '/distributed/dist-tx', title: '第 107 讲 · 分布式事务：2PC / TCC / Saga / 消息最终一致', stage: 'L10' },
  { path: '/distributed/sharding', title: '第 108 讲 · 分布式 ID、一致性哈希与分片', stage: 'L10' },
  { path: '/distributed/consensus', title: '第 109 讲 · Raft 共识、服务发现与配置中心', stage: 'L10' },
  { path: '/distributed/docker-k8s', title: '第 110 讲 · 容器化与 Kubernetes 部署', stage: 'L10' },
  { path: '/distributed/gitops', title: '第 111 讲 · GitOps、灰度发布与可观测平台', stage: 'L10' },
  { path: '/distributed/scheduling', title: '第 112 讲 · 任务调度、SRE 与混沌工程', stage: 'L10' },
  { path: '/distributed/security', title: '第 113 讲 · 安全工程：依赖、注入、序列化与密钥', stage: 'L10' },
  { path: '/advanced/cpython-source', title: '第 114 讲 · CPython 源码：对象、帧与求值循环', stage: 'L11' },
  { path: '/advanced/allocator', title: '第 115 讲 · 内存分配器 pymalloc 与 GC 源码', stage: 'L11' },
  { path: '/advanced/import-source', title: '第 116 讲 · 导入系统源码与 import hook', stage: 'L11' },
  { path: '/advanced/asyncio-source', title: '第 117 讲 · asyncio 事件循环与 Task 源码', stage: 'L11' },
  { path: '/advanced/gil-source', title: '第 118 讲 · GIL 源码、自适应解释器与无 GIL 路线', stage: 'L11' },
  { path: '/advanced/optimization', title: '第 119 讲 · 极致优化：从剖析到 C 扩展的十倍案例', stage: 'L11' },
  { path: '/advanced/architecture', title: '第 120 讲 · 架构设计：领域分层、演进与重构', stage: 'L11' },
  { path: '/advanced/senior-path', title: '第 121 讲 · 资深能力图谱、技术选型与持续精进', stage: 'L11' },
  { path: '/projects/cli-todo', title: '第 122 讲 · 实战 01 · 待办清单 CLI 与命令分发', stage: 'L12' },
  { path: '/projects/office-files', title: '第 123 讲 · 实战 02 · 文件检索、日志与自动化办公', stage: 'L12' },
  { path: '/projects/office-docs', title: '第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频', stage: 'L12' },
  { path: '/projects/browser-auto', title: '第 125 讲 · 实战 04 · Selenium 表单自动化与定时任务', stage: 'L12' },
  { path: '/projects/net-shortlink', title: '第 126 讲 · 实战 05 · 短链与图片服务', stage: 'L12' },
  { path: '/projects/data-etl', title: '第 127 讲 · 实战 06 · 日志 ETL 与 CSV / SQL 查询工具', stage: 'L12' },
  { path: '/projects/concurrent-crawler', title: '第 128 讲 · 实战 07 · 并发爬虫与分布式调度', stage: 'L12' },
  { path: '/projects/kv-memory', title: '第 129 讲 · 实战 08 · KV 贯穿线 ① 内存版与接口抽象', stage: 'L12' },
  { path: '/projects/kv-network', title: '第 130 讲 · 实战 09 · KV 贯穿线 ② 协议帧与网络层', stage: 'L12' },
  { path: '/projects/kv-wal', title: '第 131 讲 · 实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制', stage: 'L12' },
  { path: '/projects/kv-distributed', title: '第 132 讲 · 实战 11 · 分片复制、AI 网关与能力收束', stage: 'L12' },
  { path: '/guide/before-you-start', title: '开始之前 · 教程使用说明', stage: 'L0' },
  { path: '/guide/curriculum', title: '课程总目录（132 讲）', stage: 'L0' },
  { path: '/practice/', title: '练习与速查', stage: 'L0' },
  { path: '/practice/cheatsheet', title: '语法与标准库速查表', stage: 'L0' },
  { path: '/practice/pitfalls', title: '常见坑与反模式', stage: 'L0' },
  { path: '/practice/faq', title: '零基础常见问题', stage: 'L0' },
  { path: '/practice/interview', title: '面试与能力自评', stage: 'L0' },
  { path: '/practice/ecosystem', title: 'Python 生态与选型地图', stage: 'L0' },
  { path: '/practice/glossary', title: '术语表', stage: 'L0' },
  { path: '/examples/', title: '示例代码索引', stage: 'L0' },
  { path: '/topics/', title: '专题补遗 · 参考课程查漏补缺', stage: 'L0' },
  { path: '/topics/regex', title: '正则表达式 re：从字符类到回溯', stage: 'L1' },
  { path: '/topics/scrapy-antibot', title: 'Scrapy 与反爬合规：从 Spider 到生产采集', stage: 'L6' },
  { path: '/topics/testing-automation', title: '接口与 Web UI 自动化测试', stage: 'L7' },
  { path: '/topics/office-advanced', title: '办公自动化进阶：PPT、GUI 与批处理', stage: 'L2' },
  { path: '/topics/dl-projects', title: '深度学习项目：CNN、RNN、迁移学习与部署', stage: 'L9' },
  { path: '/topics/rag-frameworks', title: 'RAG 框架与大模型 API 实战', stage: 'L9' },
  { path: '/topics/web-frameworks', title: 'Flask 实操：路由、模板与会话', stage: 'L8' },
  { path: '/topics/data-projects', title: '数据分析实战：Jupyter 到报告导出', stage: 'L9' },
  { path: '/topics/toolchain-foundation', title: '工程底座：Linux、Git、SQL 与多版本', stage: 'L7' },
  { path: '/topics/reference-map', title: '参考课程对照与学习路线', stage: 'L0' },
]

export const STAGE_LABEL: Record<Stage, string> = { L0: '导学', L1: '编程地基', L2: '容器与序列', L3: '函数与抽象', L4: '面向对象', L5: '核心机制', L6: '并发与异步', L7: '工程化', L8: '服务端与数据', L9: '数据与 AI', L10: '分布式云原生', L11: '资深进阶', L12: '工程实战' }
export const STAGE_COLOR: Record<Stage, string> = { L0: '#868e96', L1: '#2b8a3e', L2: '#1c7ed6', L3: '#7048e8', L4: '#e8590c', L5: '#495057', L6: '#e8590c', L7: '#0ca678', L8: '#1c7ed6', L9: '#7048e8', L10: '#c92a2a', L11: '#495057', L12: '#c92a2a' }

// 与同一域名下的其它教程站点共用 localStorage，键名必须区分，避免进度互相串数据。
const KEY = 'python-course-done-v1'
const CHECK_KEY = 'python-course-checks-v1'

// 内部事件名沿用框架命名空间（与教程语言无关），组件里监听的是同一个字符串。
const PROGRESS_EVENT = 'go-progress-change'

/** useRoute().path 会带部署 base（如 /python/guide/），LESSONS 里记的是 /guide/。 */
function basePrefix(): string {
  try {
    const b = withBase('/')
    return b === '/' ? '' : b.replace(/\/$/, '')
  } catch { return '' }
}

export function normPath(path: string): string {
  let p = String(path || '').replace(/\.html$/, '')
  const base = basePrefix()
  if (base && p.startsWith(base + '/')) p = p.slice(base.length)
  else if (base && p === base) p = '/'
  return p
}

export function readDone(): string[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '[]')
    return (Array.isArray(raw) ? raw : []).map((p) => normPath(String(p)))
  } catch { return [] }
}

export function isDone(path: string) { return readDone().includes(normPath(path)) }

export function setDone(path: string, done: boolean) {
  if (typeof window === 'undefined') return
  const key = normPath(path)
  const cur = new Set(readDone())
  done ? cur.add(key) : cur.delete(key)
  localStorage.setItem(KEY, JSON.stringify([...cur]))
  window.dispatchEvent(new CustomEvent(PROGRESS_EVENT))
}

export function readChecks(id: string): boolean[] {
  if (typeof window === 'undefined') return []
  try {
    const all = JSON.parse(localStorage.getItem(CHECK_KEY) || '{}')
    return all[id] || []
  } catch { return [] }
}

export function setChecks(id: string, arr: boolean[]) {
  if (typeof window === 'undefined') return
  let all: Record<string, boolean[]> = {}
  try { all = JSON.parse(localStorage.getItem(CHECK_KEY) || '{}') } catch { /* ignore */ }
  all[id] = arr
  localStorage.setItem(CHECK_KEY, JSON.stringify(all))
}
