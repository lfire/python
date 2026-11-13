---
title: 术语表
description: 全站 780 个知识点术语按阶段索引。
---

# 术语表

按首次出现的阶段分组，共收录 780 个知识点。点开对应讲次可看定义、示例与工程边界。

### 导学 · 建立地图

`Python 的诞生与设计哲学` · `动态强类型与解释执行` · `适用边界与典型场景` · `与编译型语言的取舍` · `版本生态与社区` · `CPython 与 PyPy 等实现` · `pyenv / uv 的版本管理` · `venv 与依赖隔离` · `pip 与国内镜像` · `编辑器与 Jupyter / Cursor 选型` · `脚本与交互式解释器` · `词法分析与语法树` · `compile 与 code object` · `dis 反汇编字节码` · `__pycache__ 与 pyc 缓存` · `python -m 的正确用法` · `pip / uv 依赖操作` · `ruff 与 black 格式化` · `pytest 与 mypy 初识` · `IPython / pdb 调试` · `认知负担与阶段顺序` · `语言基础到运行时的跃迁` · `并发与工程化的分界` · `多领域应用与实战` · `如何使用打卡与自检`

### 阶段一 · 编程地基

`对象的三要素` · `id 与 is 的语义` · `type 与 isinstance` · `可变与不可变对象` · `小整数缓存与驻留` · `赋值即绑定` · `链式与解包赋值` · `星号解包` · `增强赋值的原地语义` · `PEP 8 命名与作用域初识` · `int 的任意精度实现` · `float 与 IEEE 754` · `浮点误差与 math.isclose` · `Decimal 与 Fraction` · `bool 是 int 的子类` · `复数与位运算` · `Unicode 码点与编码` · `str 与 bytes 的边界` · `encode / decode` · `UTF-8 与 BOM` · `raw 字符串与转义` · `多行字符串` · `索引与切片规则` · `f-string 与格式规范` · `str 常用方法` · `join 与拼接性能` · `split / partition / strip` · `正则初识` · `算术与整除` · `比较链` · `布尔短路与返回值` · `海象运算符` · `真值测试规则` · `运算符重载入口` · `条件表达式与嵌套` · `match-case 结构模式` · `守卫与捕获` · `映射表替代长分支` · `早返回与卫语句` · `for 基于迭代协议` · `range 是惰性序列` · `break / continue / else` · `enumerate 与 zip` · `循环变量作用域` · `避免索引循环` · `print 的 sep / end / file` · `input 与类型转换` · `open 的模式与编码` · `with 与上下文管理` · `路径 pathlib` · `标准输入输出重定向` · `异常层级与 BaseException` · `try / except / else / finally` · `raise from 与异常链` · `自定义异常类` · `EAFP 与 LBYL` · `异常的性能开销` · `需求拆解与输入循环` · `表达式求值的安全边界` · `异常驱动的重试` · `函数拆分与单一职责` · `命令行参数与帮助`

### 阶段二 · 容器与序列

`序列与可迭代的区别` · `__len__ 与 __getitem__` · `索引与切片协议` · `序列运算与拼接` · `abc.Sequence` · `不可变序列` · `列表的连续存储` · `append 与扩容摊还` · `insert / pop 的代价` · `索引访问 O(1)` · `常用方法` · `内存布局` · `切片赋值与步长` · `sort 与 sorted` · `key 函数与稳定性` · `列表乘法与嵌套引用` · `遍历时修改` · `内存预分配` · `元组与单元素写法` · `不可变是浅层的` · `具名元组 NamedTuple` · `元组解包与模式匹配` · `可作为字典键` · `与 list 的取舍` · `哈希与开放寻址` · `键的可哈希要求` · `插入顺序保证` · `keys / values / items 视图` · `get 与 setdefault` · `冲突与负载因子` · `defaultdict 工厂` · `Counter 计数` · `ChainMap 分层配置` · `字典合并与` · `运算符` · `OrderedDict 的差异` · `映射协议` · `集合的哈希实现` · `增删与运算` · `frozenset 可哈希` · `去重与保序` · `集合推导式` · `哈希随机化` · `列表 / 集合 / 字典推导式` · `生成器表达式` · `多重 for 与过滤` · `推导式作用域` · `海象在推导式中` · `何时退回循环` · `__iter__ 与 __next__` · `iter() 的两个参数形式` · `StopIteration` · `迭代器一次性` · `itertools 常用工具` · `惰性求值的价值` · `生成器函数与 yield` · `执行暂停与恢复` · `send 与双向通信` · `yield from 委托` · `throw / close 与清理` · `生成器实现管道` · `文本规整与分词` · `Counter 与排序` · `生成器管道` · `KV 接口抽象` · `命令分发与持久化` · `基准测量`

### 阶段三 · 函数与抽象

`位置与关键字参数` · `默认值与仅位置 / 仅关键字` · `*args 与 **kwargs` · `参数解包` · `函数是一等对象` · `签名与 inspect` · `隐式 return None` · `元组打包与解包` · `提前返回` · `返回可变对象的风险` · `注解里的返回类型` · `生成器返回` · `LEGB 查找顺序` · `global 与 nonlocal` · `闭包与自由变量` · `延迟绑定陷阱` · `默认参数捕获` · `cell 与闭包字节码` · `函数作为值` · `map / filter 的惰性` · `functools.reduce` · `lambda 的适用边界` · `operator 模块` · `partial 与组合` · `装饰器即函数替换` · `@ 语法的求值时机` · `wraps 保留元数据` · `带状态装饰器` · `装饰器与闭包` · `常见应用` · `三层函数结构` · `叠加顺序由近及远` · `类作为装饰器` · `__call__ 与描述符` · `用类保存状态` · `装饰器与类型注解` · `functools.partial` · `lru_cache 与缓存策略` · `singledispatch 分派` · `cached_property` · `可调用协议` · `工具函数组合` · `模块对象与 sys.modules` · `搜索路径与 finder` · `绝对与相对导入` · `__init__ 与 __all__` · `循环导入成因` · `命名空间包` · `注解不强制运行时检查` · `泛型与 TypeVar` · `Optional / Union` · `Protocol 与结构化子类型` · `TypedDict / Literal` · `mypy 与 pyright` · `装饰器组合设计` · `注册表与入口点` · `TTL 与淘汰策略` · `元数据与文档` · `单元测试策略` · `打包配置`

### 阶段四 · 面向对象与元编程

`类对象与实例对象` · `__init__ 不是构造函数` · `实例字典 __dict__` · `类属性与实例属性` · `方法绑定` · `self 的本质` · `__mro__ 与 C3 线性化` · `super 的真实语义` · `菱形继承` · `协作式多继承` · `实例属性查找链` · `__getattribute__ 入口` · `名称改写与私有约定` · `property 的 getter / setter` · `数据描述符与非数据描述符` · `__get__ / __set__ / __delete__` · `优先级规则` · `__set_name__` · `__repr__ 与 __str__` · `__eq__ 与 __hash__ 联动` · `functools.total_ordering` · `数值运算与反向方法` · `__len__ / __contains__` · `__bool__` · `__enter__ / __exit__` · `异常三参数与抑制` · `contextlib.contextmanager` · `ExitStack 组合` · `异步上下文` · `事务与计时场景` · `__dict__ 的开销` · `__slots__ 的约束` · `weakref 与 __weakref__` · `继承中的槽合并` · `tracemalloc 观测` · `与 dataclass 组合` · `鸭子类型与 EAFP` · `abc.ABC 与 abstractmethod` · `虚拟子类 register` · `typing.Protocol 结构化子类型` · `运行时检查的代价` · `接口隔离` · `类也是对象` · `type 的三参数形式` · `__new__ 与 __init__ 分工` · `__init_subclass__` · `__set_name__ 回调` · `元类冲突` · `getattr / setattr / hasattr` · `inspect.signature 与 getmembers` · `__dict__ 与 vars` · `动态导入 importlib` · `函数注解读取` · `反射的边界` · `dataclass 生成了什么` · `field 与 default_factory` · `frozen 与 order` · `slots 参数` · `pydantic 运行时校验` · `与 ORM 的边界` · `字段描述符` · `元类收集映射` · `实例状态存储` · `类型校验与错误聚合` · `SQL 生成与参数化` · `测试策略`

### 阶段五 · 核心机制与运行时

`词法与语法分析` · `ast 模块与 ast.dump` · `compile 内置函数` · `code object 结构` · `dis 反汇编` · `常量折叠` · `栈式指令与 LOAD / STORE` · `常见指令速查` · `闭包与 LOAD_DEREF` · `推导式的独立帧` · `异常表` · `版本间指令变化` · `帧对象与 f_locals / f_globals` · `调用栈与递归深度` · `sys.setprofile 与 tracing` · `traceback 的来源` · `生成器帧的保留` · `locals() 的语义` · `PyObject 头与 ob_refcnt` · `引用计数增减时机` · `小整数与字符串驻留` · `pymalloc 与 arena` · `sys.getsizeof 的局限` · `tracemalloc` · `循环引用为何计数失效` · `三代与阈值` · `gc.collect 的时机` · `__del__ 的陷阱` · `weakref 与 WeakValueDictionary` · `objgraph 定位` · `GIL 保护什么` · `切换间隔与字节码边界` · `IO 释放 GIL` · `C 扩展与释放` · `对多核 CPU 的影响` · `自由线程化路线` · `sys.meta_path 与 path_hooks` · `Finder / Loader 协议` · `sys.modules 缓存` · `__pycache__ 与失效` · `循环导入的加载时序` · `__getattribute__ 总入口` · `数据描述符优先` · `实例字典` · `非数据描述符` · `__getattr__ 兜底` · `性能与递归风险` · `赋值 / 浅拷贝 / 深拷贝` · `copy 与 deepcopy 协议` · `循环结构处理` · `不可变的好处` · `函数返回值的所有权` · `防御性拷贝` · `测量优先于猜测` · `timeit 的正确姿势` · `cProfile / pstats 火焰数据` · `line_profiler` · `tracemalloc 快照对比` · `基准的可复现性` · `sys.setprofile 采集` · `调用树与自耗时` · `tracemalloc 快照` · `阈值告警` · `报告生成` · `开销量化`

### 阶段六 · 并发与异步

`并发与并行的区别` · `CPU 密集 / IO 密集` · `同步异步与阻塞非阻塞` · `GIL 下的三条路线` · `吞吐量与延迟` · `C10K 问题` · `Thread 与 daemon` · `线程局部存储` · `共享变量的可见性` · `Queue 是线程安全的` · `竞争条件复现` · `线程异常不冒泡` · `Lock 与 RLock` · `Condition 等待通知` · `Semaphore 限流` · `Event 广播` · `Barrier 汇合` · `死锁四条件与规避` · `Executor 抽象` · `submit / map / as_completed` · `Future 状态机` · `并发度与队列` · `取消语义` · `异常传播` · `fork / spawn / forkserver` · `进程间不共享内存` · `序列化 pickle 成本` · `Pool 与 chunksize` · `shared_memory` · `进程启动开销` · `Queue 与 Pipe 语义` · `Manager 代理对象` · `共享 ctypes 值` · `Event 跨进程` · `优雅退出与 SIGTERM` · `僵尸进程回收` · `阻塞与非阻塞 IO` · `select / poll / epoll 对比` · `水平与边缘触发` · `selectors 标准库` · `回调地狱的由来` · `反应器模式` · `生成器双向通信` · `用生成器写调度器` · `状态机与栈-less 协程` · `与回调写法对照` · `PEP 380 / 492` · `coroutine 与 async function` · `await 只能用在 async 内` · `awaitable 协议` · `asyncio.run 做了什么` · `常见阻塞误用` · `同步异步边界` · `loop 与策略` · `create_task 与 gather` · `Future 状态` · `call_soon / call_later` · `TaskGroup 结构化并发` · `取消与 CancelledError` · `串行基线` · `线程池版本` · `asyncio + 连接池` · `去重与限流` · `失败重试与断点` · `监控与合规`

### 阶段七 · 工程化与质量

`src 与扁平布局对比` · `包与模块命名` · `内部模块分层` · `配置与密钥隔离` · `README 与文档入口` · `单仓多包` · `pyproject.toml 规范` · `直接与传递依赖` · `约束文件与锁` · `uv / poetry / pip-tools` · `哈希校验` · `供应链安全` · `PEP 8 的取舍` · `ruff 规则集` · `格式化与 lint 分工` · `import 排序` · `pre-commit 钩子` · `渐进式接入 legacy` · `检查器配置与严格度` · `stub 与第三方库` · `泛型与不变性` · `Any 的传播` · `ignore 的治理` · `与运行时校验互补` · `断言重写` · `fixture 作用域` · `参数化与 mark` · `tmp_path 与 monkeypatch` · `测试金字塔` · `覆盖率解读` · `unittest.mock 与 patch 位置` · `monkeypatch` · `freezegun 与时钟注入` · `HTTP MockTransport` · `假对象与桩` · `依赖注入` · `hypothesis 策略` · `收缩到最小反例` · `状态机测试` · `pytest-benchmark` · `fuzz 与输入边界` · `种子与可复现` · `Logger / Handler / Formatter` · `级别与传播` · `结构化 JSON` · `trace_id 注入` · `采样与脱敏` · `与 OpenTelemetry 关联` · `十二要素与环境变量` · `pydantic-settings 校验` · `分层覆盖` · `密钥与轮换` · `启动期失败` · `配置漂移` · `构建后端与 PEP 517` · `wheel / sdist 差别` · `入口点 console_scripts` · `版本与变更日志` · `元数据与依赖标记` · `发布流水线` · `目录重构` · `依赖锁定` · `类型与规范` · `测试补齐` · `CI 矩阵` · `发布与回滚`

### 阶段八 · 服务端与数据

`请求响应模型` · `WSGI 可调用对象` · `ASGI 与 async 三参数` · `中间件链` · `生命周期与启动事件` · `同步异步混跑` · `三者定位差异` · `路由与依赖注入` · `校验与序列化` · `ORM 与迁移内置程度` · `生态与插件` · `团队成本` · `路径与查询参数` · `请求体与 Pydantic 模型` · `依赖树与缓存` · `响应模型与状态码` · `错误统一处理` · `版本化路由` · `资源与动词` · `状态码语义` · `分页与过滤` · `幂等键与重试` · `版本策略` · `OpenAPI 文档与客户端生成` · `三种通道对比` · `握手与帧` · `SSE 与断线重连` · `连接管理与广播` · `心跳与背压` · `水平扩展与粘性会话` · `Engine / Session / Unit of Work` · `连接池参数` · `事务边界与隔离级别` · `N+1 查询` · `懒加载与预加载` · `Alembic 迁移` · `五种数据结构与选型` · `缓存模式与失效` · `穿透 / 击穿 / 雪崩` · `TTL 抖动` · `分布式锁的正确实现` · `缓存一致性` · `队列与发布订阅` · `至少一次与恰好一次的真相` · `确认与重试` · `死信队列` · `任务幂等` · `顺序与分区` · `认证与授权的区别` · `Session 与 JWT 取舍` · `令牌刷新与撤销` · `密码哈希与加盐` · `OAuth2 授权码流程` · `RBAC / ABAC` · `上传与断点续传` · `预签名 URL` · `对象存储一致性` · `倒排索引与 ES` · `gRPC 与 Protobuf` · `跨服务错误传播` · `发号与 Base62` · `路由与重定向` · `缓存与限流` · `数据模型与索引` · `埋点与监控` · `压测与容量`

### 阶段九 · 数据科学与 AI 工程

`ndarray 与 dtype` · `shape / stride 与视图` · `广播规则` · `向量化代替循环` · `副本与视图` · `ufunc 与聚合` · `Series 与 DataFrame 索引` · `缺失值与重复` · `groupby / agg / transform` · `merge 与 join` · `透视与重采样` · `类型与内存优化` · `图表类型与数据关系` · `Figure / Axes 对象模型` · `配色与可读性` · `统计图形与置信区间` · `交互图与大屏` · `导出与可复现` · `描述统计与离群点` · `常见分布` · `抽样与中心极限定理` · `假设检验与 p 值` · `置信区间` · `相关不等于因果` · `训练集 / 验证集 / 测试集` · `数据泄漏` · `特征工程与缩放` · `交叉验证` · `分类与回归指标` · `基线模型` · `KNN 与距离度量` · `最小二乘与梯度下降` · `多项式回归与过拟合` · `逻辑回归与决策边界` · `正则化 L1 / L2` · `可解释性` · `间隔最大化与核技巧` · `软间隔与 C` · `树的划分准则` · `剪枝与深度控制` · `Bagging 与随机森林` · `特征重要性` · `Bagging 与 Boosting 差异` · `AdaBoost / GBDT 思路` · `梯度提升的残差拟合` · `学习率与树数量` · `早停与特征工程` · `模型复杂度成本` · `聚类假设与尺度` · `KMeans 与 K 的选择` · `DBSCAN 与密度` · `PCA 与方差解释` · `降维可视化` · `异常检测与业务阈值` · `偏差方差分解` · `学习曲线与验证曲线` · `网格 / 随机 / 贝叶斯搜索` · `正则与早停` · `类别不平衡处理` · `模型选择陷阱` · `张量与设备` · `计算图与 autograd` · `Dataset / DataLoader` · `损失与优化器` · `训练 / 验证循环` · `CNN 与 RNN 直觉` · `Prompt 与结构化输出` · `Embedding 与向量检索` · `RAG 分块与召回评估` · `工具调用与 Agent 循环` · `流式输出与超时` · `Token 成本与降级`

### 阶段十 · 分布式与云原生

`CAP 的正确表述` · `强一致与最终一致` · `读写一致性` · `版本与向量时钟` · `BASE 与补偿` · `业务可接受窗口` · `幂等键设计` · `去重表与唯一索引` · `分布式锁实现` · `租约与看门狗` · `令牌桶与漏桶` · `分布式限流` · `本地事务边界` · `2PC 的阻塞问题` · `TCC 三阶段` · `Saga 与补偿事务` · `事务消息与 outbox` · `对账与人工兜底` · `自增 ID 的局限` · `雪花算法与时钟回拨` · `范围与哈希分片` · `一致性哈希与虚拟节点` · `热点与倾斜` · `扩容与再平衡` · `Leader 选举与日志复制` · `多数派与任期` · `成员变更` · `etcd / Consul 定位` · `健康检查` · `配置推送与灰度` · `镜像分层与多阶段构建` · `依赖与基础镜像瘦身` · `非 root 与只读文件系统` · `资源请求与限制` · `探针与优雅退出` · `HPA 与冷启动` · `声明式与期望状态` · `Helm / Kustomize` · `金丝雀与蓝绿` · `指标驱动自动回滚` · `Trace / Metrics / Log 三支柱` · `SLO 与错误预算` · `定时与依赖调度` · `Airflow / Temporal 选型` · `重试与补数` · `SLI / SLO / 错误预算` · `告警降噪与值班` · `故障注入与演练` · `依赖漏洞与 SBOM` · `注入与参数化` · `不安全的反序列化` · `密钥与凭证轮换` · `权限最小化` · `审计与应急响应`

### 阶段十一 · 资深进阶与源码

`源码目录结构` · `PyObject 与类型对象` · `ceval.c 主循环` · `帧与解释器状态` · `引用计数宏` · `调试构建与 gdb` · `arena / pool / block 三级` · `小对象分配路径` · `分代 GC 触发逻辑` · `gcmodule 收集过程` · `内存碎片与归还` · `与 glibc malloc 关系` · `importlib._bootstrap` · `find_spec / exec_module` · `路径钩子` · `延迟导入` · `启动时间剖析` · `插件安全模型` · `BaseEventLoop 与 selector` · `Handle / TimerHandle` · `Task.__step` · `Future 回调链` · `取消与 uncancel` · `调试模式与慢回调` · `GIL 的获取与释放点` · `切换请求与 eval breaker` · `3.11 自适应特化` · `内联缓存` · `PEP 703 自由线程化` · `对扩展的影响` · `先算法后实现` · `数据结构与批处理` · `向量化与 NumPy` · `Cython / C 扩展` · `多进程与原生并行` · `缓存与异构卸载` · `变化方向与边界` · `依赖倒置与端口适配器` · `模块化单体到服务拆分` · `契约与版本` · `技术债的量化` · `渐进式重构` · `能力矩阵与短板` · `选型评估维度` · `读源码与写技术提案` · `故障复盘方法` · `影响力与协作` · `持续学习路径`

### 阶段十二 · 工程实战

`命令解析 argparse / click` · `数据模型与 JSON 持久化` · `原子写入` · `退出码与错误` · `入口点打包` · `端到端测试` · `pathlib 遍历与 glob` · `os.walk 与元数据` · `按类型容量统计` · `logging 落盘` · `datetime 与调度` · `批量重命名安全` · `smtplib / yagmail 与授权码` · `pypdf 拆分合并` · `openpyxl / pandas 读写表格` · `python-docx 模板渲染` · `Pillow 与二维码` · `moviepy 批处理` · `WebDriver 与等待策略` · `元素定位 XPath / CSS` · `显式等待与隐式等待` · `定时任务与 APScheduler` · `异常截图` · `合规与频率` · `301 / 302 语义` · `缓存与防刷` · `图片上传与缩略图` · `ETag 与预签名 URL` · `监控与容量` · `生成器管道与背压` · `解析与脏数据隔离` · `窗口聚合` · `批量写入与事务` · `增量水位` · `数据质量校验` · `串行基线到 asyncio` · `连接池与限流` · `URL 去重与优先级` · `任务队列分发` · `断点续爬` · `命令模型与协议设计` · `存储引擎接口` · `内存实现与过期` · `并发安全` · `基准测试` · `错误语义` · `TCP 粘包与长度前缀` · `序列化选型` · `asyncio start_server` · `连接管理与超时` · `客户端 SDK` · `协议兼容与版本` · `追加写与 fsync` · `WAL 记录格式` · `重放与检查点` · `快照与压缩` · `崩溃一致性` · `锁分片与并发` · `分片与路由` · `副本与读写 quorum` · `故障转移` · `流式推理网关` · `成本与限流` · `项目复盘与能力图谱`

