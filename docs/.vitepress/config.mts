import { defineConfig } from 'vitepress'

// 由 tools/course/gen_course.py 生成；结构变更请改数据源后重新运行。
// GitHub 项目页部署在子路径下，base 与仓库名一致。
// 改用自定义域名 / 用户主页仓库时，构建时传 VP_BASE=/ 即可，无需改代码。
const BASE = process.env.VP_BASE || '/python/'

const SITE_TITLE = 'Python 零基础通关'
const SITE_DESC = '一套从零基础到资深的交互式 Python 中文教程：13 个递进阶段、132 讲、12 类工程场景与贯穿式实战。'

export default defineConfig({
  lang: 'zh-CN',
  title: SITE_TITLE,
  description: SITE_DESC,
  base: BASE,
  outDir: '.vitepress/dist',
  cacheDir: '.vitepress/cache',
  lastUpdated: true,
  cleanUrls: true,
  ignoreDeadLinks: true,
  metaChunk: true,
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${BASE}favicon.svg` }],
    ['meta', { name: 'theme-color', content: '#3776ab' }],
    ['meta', { name: 'og:title', content: `${SITE_TITLE} · 从零到资深` }],
    ['meta', { name: 'og:description', content: SITE_DESC }],
  ],
  vite: {
    build: {
      // 本地全文搜索索引只在打开搜索框时懒加载；提高阈值避免构建时输出无害的体积提示。
      chunkSizeWarningLimit: 5000,
    },
  },
  markdown: {
    lineNumbers: true,
    container: {
      tipLabel: '小贴士',
      warningLabel: '注意',
      dangerLabel: '当心',
      infoLabel: '说明',
      detailsLabel: '展开查看详情',
    },
    // 允许组件属性里的 < 与 > 原样输出（组件用法讲解会用到）
    html: true,
  },
  themeConfig: {
    logo: '/favicon.svg',
    siteTitle: SITE_TITLE,
    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一节', next: '下一节' },
    darkModeSwitchLabel: '外观',
    lightModeSwitchTitle: '切换到浅色模式',
    darkModeSwitchTitle: '切换到深色模式',
    sidebarMenuLabel: '课程目录',
    returnToTopLabel: '回到顶部',
    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索课程', buttonAriaLabel: '搜索课程' },
          modal: {
            noResultsText: '没有找到相关内容',
            resetButtonTitle: '清除搜索',
            backButtonTitle: '返回',
            displayDetails: '展开详情',
            footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
          },
        },
      },
    },
    nav: [
      { text: '开始之前', link: '/guide/before-you-start' },
      { text: '课程总目录', link: '/guide/curriculum' },
      { text: '学习路线', link: '/guide/' },
      {
        text: '阶段课程',
        items: [
          { text: '导学', link: '/guide/' },
          { text: '编程地基', link: '/foundation/' },
          { text: '容器与序列', link: '/containers/' },
          { text: '函数与抽象', link: '/functions/' },
          { text: '面向对象', link: '/oop/' },
          { text: '核心机制', link: '/core/' },
          { text: '并发与异步', link: '/concurrency/' },
          { text: '工程化', link: '/engineering/' },
          { text: '服务端与数据', link: '/server/' },
          { text: '数据与 AI', link: '/data-ai/' },
          { text: '分布式云原生', link: '/distributed/' },
          { text: '资深进阶', link: '/advanced/' },
          { text: '工程实战', link: '/projects/' }
        ],
      },
      { text: '工程实战', link: '/projects/' },
      { text: '数据与 AI', link: '/data-ai/' },
      { text: '练习与速查', link: '/practice/' },
      { text: '关于', link: '/about/' },
    ],
    sidebar: {
      '/guide/': [
        { text: '导学 · 建立地图', collapsed: false, items: [
          { text: '阶段导览 · 导学', link: '/guide/' },
          { text: '开始之前 · 教程使用说明', link: '/guide/before-you-start' },
          { text: '课程总目录（132 讲）', link: '/guide/curriculum' },
          { text: '001 开篇：Python 是什么，为什么值得学', link: '/guide/opening' },
          { text: '002 环境与工具链：解释器、虚拟环境与编辑器', link: '/guide/setup' },
          { text: '003 第一行 Python：从源码到字节码再到执行', link: '/guide/hello' },
          { text: '004 工具链全景：写代码、查问题、验质量', link: '/guide/toolchain' },
          { text: '005 学习路线：十三个阶段如何递进', link: '/guide/roadmap' }
        ] },
      ],
      '/foundation/': [
        { text: '阶段一 · 编程地基', collapsed: false, items: [
          { text: '阶段导览 · 编程地基', link: '/foundation/' },
          { text: '006 一切皆对象：id、type、value 与可变性', link: '/foundation/object-model' },
          { text: '007 变量是名字绑定：赋值、引用与命名规范', link: '/foundation/variables' },
          { text: '008 数值体系：int 任意精度、float、Decimal 与 bool', link: '/foundation/numeric' },
          { text: '009 字符串与编码：Unicode、str / bytes 与转义', link: '/foundation/strings' },
          { text: '010 字符串操作：切片、f-string 与常用方法', link: '/foundation/string-ops' },
          { text: '011 运算符与表达式：优先级、短路与真值', link: '/foundation/operators' },
          { text: '012 分支：if / elif / else 与 match-case', link: '/foundation/control-flow' },
          { text: '013 循环：for / while、range 与循环 else', link: '/foundation/loops' },
          { text: '014 输入输出与文件初识：print、input、open、with', link: '/foundation/io' },
          { text: '015 异常：捕获、异常链与自定义异常', link: '/foundation/exceptions' },
          { text: '016 阶段综合：交互式命令行计算器', link: '/foundation/capstone' }
        ] },
      ],
      '/containers/': [
        { text: '阶段二 · 容器与序列', collapsed: false, items: [
          { text: '阶段导览 · 容器与序列', link: '/containers/' },
          { text: '017 序列协议与通用操作', link: '/containers/sequence' },
          { text: '018 list：动态数组、操作与时间复杂度', link: '/containers/list-basics' },
          { text: '019 list 进阶：切片赋值、排序与常见陷阱', link: '/containers/list-advanced' },
          { text: '020 tuple 与具名元组：不可变性的价值', link: '/containers/tuple' },
          { text: '021 dict：哈希表、视图与插入顺序', link: '/containers/dict-basics' },
          { text: '022 dict 进阶：默认字典、计数器与合并', link: '/containers/dict-advanced' },
          { text: '023 set / frozenset：哈希、集合运算与去重', link: '/containers/set' },
          { text: '024 推导式：四种写法与可读性边界', link: '/containers/comprehension' },
          { text: '025 迭代协议：iterable、iterator 与惰性求值', link: '/containers/iterator' },
          { text: '026 生成器与 yield：send / throw / close', link: '/containers/generator' },
          { text: '027 阶段综合：词频统计与内存版 KV', link: '/containers/capstone' }
        ] },
      ],
      '/functions/': [
        { text: '阶段三 · 函数与抽象', collapsed: false, items: [
          { text: '阶段导览 · 函数与抽象', link: '/functions/' },
          { text: '028 函数定义与参数形态', link: '/functions/function-basics' },
          { text: '029 返回值、None 与多返回值', link: '/functions/returns' },
          { text: '030 作用域、LEGB 与闭包延迟绑定', link: '/functions/scope' },
          { text: '031 高阶函数、lambda 与 map / filter / reduce', link: '/functions/higher-order' },
          { text: '032 装饰器原理与 functools.wraps', link: '/functions/decorator' },
          { text: '033 带参装饰器、叠加顺序与类装饰器', link: '/functions/decorator-params' },
          { text: '034 偏函数、可调用对象与函数式工具', link: '/functions/partial' },
          { text: '035 模块与包：import 机制与循环导入', link: '/functions/modules' },
          { text: '036 类型注解、typing 与渐进式类型', link: '/functions/typing' },
          { text: '037 阶段综合：缓存装饰器库与插件注册表', link: '/functions/capstone' }
        ] },
      ],
      '/oop/': [
        { text: '阶段四 · 面向对象与元编程', collapsed: false, items: [
          { text: '阶段导览 · 面向对象', link: '/oop/' },
          { text: '038 类与实例：__init__、self 与属性', link: '/oop/class-basics' },
          { text: '039 属性查找、MRO 与 super', link: '/oop/mro' },
          { text: '040 访问控制、property 与描述符协议', link: '/oop/property' },
          { text: '041 特殊方法：repr、比较、算术与容器协议', link: '/oop/special-methods' },
          { text: '042 上下文管理器与 with 协议', link: '/oop/context' },
          { text: '043 __slots__、弱引用与对象内存布局', link: '/oop/slots' },
          { text: '044 鸭子类型、抽象基类与 Protocol', link: '/oop/abc' },
          { text: '045 元类：__new__、type 与类创建过程', link: '/oop/metaclass' },
          { text: '046 反射与自省：getattr、inspect 与 __dict__', link: '/oop/introspection' },
          { text: '047 dataclass、attrs 与 pydantic 模型', link: '/oop/dataclass' },
          { text: '048 阶段综合：最小 ORM 与校验框架', link: '/oop/capstone' }
        ] },
      ],
      '/core/': [
        { text: '阶段五 · 核心机制与运行时', collapsed: false, items: [
          { text: '阶段导览 · 核心机制', link: '/core/' },
          { text: '049 CPython 编译流程：AST 到字节码', link: '/core/compile-pipeline' },
          { text: '050 字节码、栈式虚拟机与 dis 实战', link: '/core/bytecode' },
          { text: '051 帧、调用栈与命名空间', link: '/core/frames' },
          { text: '052 对象内存布局、引用计数与小对象池', link: '/core/memory' },
          { text: '053 分代 GC、循环引用与 weakref', link: '/core/gc' },
          { text: '054 GIL 真相：存在原因、切换与影响边界', link: '/core/gil' },
          { text: '055 导入系统源码级：finder、loader 与缓存', link: '/core/import-system' },
          { text: '056 属性访问链路与 __getattribute__', link: '/core/attribute-lookup' },
          { text: '057 可变性、深浅拷贝与共享状态', link: '/core/copy' },
          { text: '058 性能剖析：timeit、cProfile 与 tracemalloc', link: '/core/profiling' },
          { text: '059 阶段综合：简易性能分析器与内存哨兵', link: '/core/capstone' }
        ] },
      ],
      '/concurrency/': [
        { text: '阶段六 · 并发与异步', collapsed: false, items: [
          { text: '阶段导览 · 并发与异步', link: '/concurrency/' },
          { text: '060 并发、并行与 IO 模型全景', link: '/concurrency/concurrency-intro' },
          { text: '061 threading：线程生命周期与共享状态', link: '/concurrency/threading' },
          { text: '062 线程同步：Lock、Condition、Semaphore、Event', link: '/concurrency/sync-primitives' },
          { text: '063 线程池与 Future 模式', link: '/concurrency/threadpool' },
          { text: '064 multiprocessing：进程、Pool 与共享内存', link: '/concurrency/multiprocessing' },
          { text: '065 进程间通信：Queue、Pipe 与信号', link: '/concurrency/ipc' },
          { text: '066 IO 多路复用：select / poll / epoll', link: '/concurrency/io-multiplex' },
          { text: '067 生成器协程：send、yield from 与调度器', link: '/concurrency/generator-coroutine' },
          { text: '068 async / await 与协程对象', link: '/concurrency/async-await' },
          { text: '069 asyncio 深入：Task、Future 与事件循环', link: '/concurrency/asyncio' },
          { text: '070 阶段综合：并发爬虫四级演进', link: '/concurrency/capstone' }
        ] },
      ],
      '/engineering/': [
        { text: '阶段七 · 工程化与质量', collapsed: false, items: [
          { text: '阶段导览 · 工程化', link: '/engineering/' },
          { text: '071 项目结构与 src 布局', link: '/engineering/layout' },
          { text: '072 依赖管理：venv、uv、锁文件与可复现构建', link: '/engineering/deps' },
          { text: '073 代码规范：PEP 8、ruff、black 与 pre-commit', link: '/engineering/style' },
          { text: '074 静态检查：mypy / pyright 与渐进式类型', link: '/engineering/typecheck' },
          { text: '075 单元测试：pytest、fixture 与参数化', link: '/engineering/pytest' },
          { text: '076 Mock 与测试替身：时间、网络与随机', link: '/engineering/mock' },
          { text: '077 属性测试、基准测试与模糊测试', link: '/engineering/property-testing' },
          { text: '078 日志：logging、结构化日志与追踪关联', link: '/engineering/logging' },
          { text: '079 配置管理：环境变量、.env 与配置中心', link: '/engineering/config' },
          { text: '080 打包与发布：pyproject、wheel 与 PyPI', link: '/engineering/packaging' },
          { text: '081 阶段综合：把脚本重构成可发布包', link: '/engineering/capstone' }
        ] },
      ],
      '/server/': [
        { text: '阶段八 · 服务端与数据', collapsed: false, items: [
          { text: '阶段导览 · 服务端与数据', link: '/server/' },
          { text: '082 HTTP 协议与 WSGI / ASGI', link: '/server/http-wsgi' },
          { text: '083 FastAPI / Flask / Django 选型', link: '/server/frameworks' },
          { text: '084 路由、依赖注入与请求校验', link: '/server/routing' },
          { text: '085 REST API 设计、OpenAPI 与幂等', link: '/server/rest-api' },
          { text: '086 WebSocket / SSE / 长轮询与实时推送', link: '/server/websocket' },
          { text: '087 SQLAlchemy、连接池、事务与迁移', link: '/server/orm' },
          { text: '088 Redis 缓存：穿透、击穿、雪崩与分布式锁', link: '/server/redis' },
          { text: '089 消息队列：Celery / RabbitMQ / Kafka', link: '/server/mq' },
          { text: '090 认证授权：Session、JWT、OAuth2 与 RBAC', link: '/server/auth' },
          { text: '091 文件、对象存储、搜索与 gRPC', link: '/server/storage' },
          { text: '092 阶段综合：生产级短链服务', link: '/server/capstone' }
        ] },
      ],
      '/data-ai/': [
        { text: '阶段九 · 数据科学与 AI 工程', collapsed: false, items: [
          { text: '阶段导览 · 数据与 AI', link: '/data-ai/' },
          { text: '093 NumPy 向量化、广播与内存布局', link: '/data-ai/numpy' },
          { text: '094 Pandas 清洗、分组、透视与时间序列', link: '/data-ai/pandas' },
          { text: '095 可视化：Matplotlib / Seaborn / Plotly 与图表选型', link: '/data-ai/visualization' },
          { text: '096 统计基础：分布、检验与相关性', link: '/data-ai/statistics' },
          { text: '097 机器学习流程：特征、划分与评价', link: '/data-ai/ml-workflow' },
          { text: '098 经典算法：KNN、线性与逻辑回归', link: '/data-ai/linear-models' },
          { text: '099 SVM、核方法、决策树与随机森林', link: '/data-ai/svm-trees' },
          { text: '100 集成学习：Boosting、XGBoost 与 LightGBM', link: '/data-ai/ensemble' },
          { text: '101 无监督学习：KMeans、DBSCAN、PCA 与异常检测', link: '/data-ai/unsupervised' },
          { text: '102 模型调优：交叉验证、正则化与过拟合', link: '/data-ai/model-tuning' },
          { text: '103 深度学习与 PyTorch：张量、自动微分与训练循环', link: '/data-ai/deep-learning' },
          { text: '104 LLM 应用工程：Prompt、RAG、Agent 与成本', link: '/data-ai/llm-engineering' }
        ] },
      ],
      '/distributed/': [
        { text: '阶段十 · 分布式与云原生', collapsed: false, items: [
          { text: '阶段导览 · 分布式云原生', link: '/distributed/' },
          { text: '105 CAP / BASE 与一致性模型', link: '/distributed/cap-base' },
          { text: '106 幂等、分布式锁与限流', link: '/distributed/idempotency' },
          { text: '107 分布式事务：2PC / TCC / Saga / 消息最终一致', link: '/distributed/dist-tx' },
          { text: '108 分布式 ID、一致性哈希与分片', link: '/distributed/sharding' },
          { text: '109 Raft 共识、服务发现与配置中心', link: '/distributed/consensus' },
          { text: '110 容器化与 Kubernetes 部署', link: '/distributed/docker-k8s' },
          { text: '111 GitOps、灰度发布与可观测平台', link: '/distributed/gitops' },
          { text: '112 任务调度、SRE 与混沌工程', link: '/distributed/scheduling' },
          { text: '113 安全工程：依赖、注入、序列化与密钥', link: '/distributed/security' }
        ] },
      ],
      '/advanced/': [
        { text: '阶段十一 · 资深进阶与源码', collapsed: false, items: [
          { text: '阶段导览 · 资深进阶', link: '/advanced/' },
          { text: '114 CPython 源码：对象、帧与求值循环', link: '/advanced/cpython-source' },
          { text: '115 内存分配器 pymalloc 与 GC 源码', link: '/advanced/allocator' },
          { text: '116 导入系统源码与 import hook', link: '/advanced/import-source' },
          { text: '117 asyncio 事件循环与 Task 源码', link: '/advanced/asyncio-source' },
          { text: '118 GIL 源码、自适应解释器与无 GIL 路线', link: '/advanced/gil-source' },
          { text: '119 极致优化：从剖析到 C 扩展的十倍案例', link: '/advanced/optimization' },
          { text: '120 架构设计：领域分层、演进与重构', link: '/advanced/architecture' },
          { text: '121 资深能力图谱、技术选型与持续精进', link: '/advanced/senior-path' }
        ] },
      ],
      '/projects/': [
        { text: '阶段十二 · 工程实战', collapsed: false, items: [
          { text: '阶段导览 · 工程实战', link: '/projects/' },
          { text: '122 实战 01 · 待办清单 CLI 与命令分发', link: '/projects/cli-todo' },
          { text: '123 实战 02 · 文件检索、日志与自动化办公', link: '/projects/office-files' },
          { text: '124 实战 03 · 邮件、PDF、Excel、Word 与图像视频', link: '/projects/office-docs' },
          { text: '125 实战 04 · Selenium 表单自动化与定时任务', link: '/projects/browser-auto' },
          { text: '126 实战 05 · 短链与图片服务', link: '/projects/net-shortlink' },
          { text: '127 实战 06 · 日志 ETL 与 CSV / SQL 查询工具', link: '/projects/data-etl' },
          { text: '128 实战 07 · 并发爬虫与分布式调度', link: '/projects/concurrent-crawler' },
          { text: '129 实战 08 · KV 贯穿线 ① 内存版与接口抽象', link: '/projects/kv-memory' },
          { text: '130 实战 09 · KV 贯穿线 ② 协议帧与网络层', link: '/projects/kv-network' },
          { text: '131 实战 10 · KV 贯穿线 ③ WAL、持久化与并发控制', link: '/projects/kv-wal' },
          { text: '132 实战 11 · 分片复制、AI 网关与能力收束', link: '/projects/kv-distributed' }
        ] },
      ],
      '/practice/': [
        { text: '练习与速查', collapsed: false, items: [
          { text: '练习与速查', link: '/practice/' },
          { text: '语法与标准库速查表', link: '/practice/cheatsheet' },
          { text: '常见坑与反模式', link: '/practice/pitfalls' },
          { text: '零基础常见问题', link: '/practice/faq' },
          { text: '面试与能力自评', link: '/practice/interview' },
          { text: 'Python 生态与选型地图', link: '/practice/ecosystem' },
          { text: '术语表', link: '/practice/glossary' }
        ] },
      ],
      '/about/': [
        { text: '关于本站', collapsed: false, items: [
          { text: '关于本站', link: '/about/' },
          { text: '本地运行与 Pages 部署', link: '/about/deploy' },
        ] },
      ],
    },
    socialLinks: [{ icon: 'github', link: 'https://github.com/lfire/python' }],
    footer: {
      message: '为完全零基础的学习者而写 · 从第一行代码到源码级理解与工程架构',
      copyright: '© 2026 Python 零基础通关',
    },
  },
})
