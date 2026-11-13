---
title: 第 118 讲 · GIL 源码、自适应解释器与无 GIL 路线
description: 理解性能演进方向并做技术判断
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='50 分钟' goal='理解性能演进方向并做技术判断' prereq='第 117 讲 · asyncio 事件循环与 Task 源码' />

# 第 118 讲 · GIL 源码、自适应解释器与无 GIL 路线

事件循环读到源码这一层，有个老问题能正面回答：为什么加了线程，CPU 上的活反而更慢。还有个更近的困惑——同一段代码预热前后数字对不上；听人说「无 GIL 已经可用」，又不确定自己的服务能不能直接换。这些判断不能靠印象，得看解释器这几版改了什么。

先看 GIL 的获取与释放点，以及切换请求和 eval breaker 怎么让出执行权；再读 3.11 起的自适应特化与内联缓存，解释预热为何改变结果；最后落到 PEP 703 自由线程化，给出按构建与负载判断的框架。需要线程与字节码基础；学完你能说清标准构建里 GIL 的状态，也能判断依赖会不会踩坑。


## 微基准只跑一次就下结论，数字为什么对不上

一个团队把一组纯 Python 微基准的结论直接写进容量规划：他们只跑一次就记录耗时，没预热也没区分解释器构建，结果 3.11 之前测的数字与线上 3.13 差出一截，因为 3.11 起解释器会在运行时把热点指令特化并缓存，同一段代码预热前后性能并不一样。

另一组人更激进，听说 3.13 有无 GIL 版本，就默认线上构建已经去掉 GIL，在 C 扩展里假设执行期间一直持有 GIL，结果在自由线程构建下出现难复现的崩溃。还有人把「多线程一定慢」当成定理，却没意识到某些 C 扩展会主动释放 GIL。

GIL 的获取释放点、eval breaker、自适应特化与自由线程化是四条不同的演进线，性能结论必须按解释器版本与构建分别测，本讲把源码层的机制与判断框架对齐。

<Callout type="warn" title='先看一个真实会出错的写法' text='微基准只跑一次就下性能结论：3.11 起热点指令预热后才特化，未预热走通用分派，单次测量把 quickening 噪声算进结果' />

<Callout type="tip" title='核心心智模型' text='GIL 是保护解释器共享状态（引用计数、模块字典、类型系统）的互斥锁，不是语言规范，PyPy/Jython 没有，CPython 3.13 的自由线程构建可以关掉它。在 ceval.c 的求值循环里，线程必须持有 GIL 才能执行字节码；阻塞式 IO、time.sleep 与释放 GIL 的 C 扩' />


## GIL 的获取释放点与 eval breaker

GIL 是保护解释器共享状态（引用计数、模块字典、类型系统）的互斥锁，不是语言规范，PyPy/Jython 没有，CPython 3.13 的自由线程构建可以关掉它。在 `ceval.c` 的求值循环里，线程必须持有 GIL 才能执行字节码；

阻塞式 IO、`time.sleep` 与释放 GIL 的 C 扩展在进入系统调用前用 Py_BEGIN_ALLOW_THREADS 临时释放、完成后 Py_END_ALLOW_THREADS 重新获取，期间不得触碰任何 Python 对象。

切换由 `sys.getswitchinterval()` 控制，默认 0.005 秒：到点设置 eval_breaker 让出请求，持有者在检查点（3.10 之后主要收敛到循环回边与函数调用处，不再每若干条指令检查）释放 GIL 并唤醒等待者。

3.12 的 PEP 684 把 GIL 改为每解释器一份，子解释器可各自持锁，但 C 扩展仍需配合才能安全并行。

注意 GIL 只保证单条字节码层面的原子性，counter += 1 编译成 LOAD_GLOBAL / BINARY_OP / STORE_GLOBAL 多条指令，业务侧读改写仍要加 `threading.Lock`。

`sys.setswitchinterval` 可调，但调小只加剧切换与锁竞争，生产不要随意改。

**GIL 与自由线程相关版本**

| 版本 / PEP | 变化 | 排查提示 |
| --- | --- | --- |
| sys.getswitchinterval() 0.005 | 每 5ms 发起让出请求 | 调小加剧竞态，生产勿随意改 |
| 3.10+ eval breaker | 检查点收敛到循环回边与调用处 | 旧文章的指令级切换结论会变化 |
| 3.11 PEP 659 | 自适应特化与内联缓存 | 微基准必须预热 |
| 3.12 PEP 684 | 每解释器 GIL | 子解释器仍需 C 扩展配合 |
| 3.13 PEP 703 | 实验性 --disable-gil 自由线程 | 单线程回退，扩展逐个验证 |

<ConceptDiagram type='hub4' title='第 118 讲 · GIL 的获取释放点与 eval breaker' labels='GIL 的获取释放点与 eval break|3.11 自适应特化、内联缓存与预热|PEP 703 自由线程化与技术判断框架' caption='理解性能演进方向并做技术判断' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 引用计数、解释器状态与 switchinterval

ceval 的求值循环假定当前线程持有 GIL：引用计数宏 Py_INCREF / Py_DECREF 直接改 PyObject 头里的 ob_refcnt，若没有这把大锁，两个线程并发增减同一对象就会丢更新、提前释放仍被引用的对象。

C 扩展跑长计算时用 Py_BEGIN_ALLOW_THREADS 临时释放 GIL、结束后重新获取，期间禁止触碰 Python 对象，这是 IO 密集与部分 C 扩展能靠线程重叠的根本原因。切换由 eval_breaker 标志位驱动：到 switchinterval 设置让出请求，持有者在循环回边与调用处检查并释放锁。

3.11 的 PEP 659 把热点指令改写成带内联缓存的特化版本，缓存槽以 CACHE 条目排在 co_code 之后，自适应字节码存在 _co_code_adaptive；类型变化会去优化回退，因此同一段代码预热前后耗时不同。

PEP 703 的自由线程构建把引用计数改为偏向线程局部加延迟合并、容器访问加细粒度同步，代价是单线程回退与巨大的扩展适配工作，所以它不是开关，而是一次需要按构建分别验证的全生态迁移。

<Term word='GIL 的获取与释放点' text='GIL 是保护解释器共享状态（引用计数、模块字典、类型系统）的互斥锁，不是语言规范，PyPy/Jython 没有，CPython 3.13 的自由线程构建可以关掉它。在 ceval.c 的求值循环里，线程必须持有 GIL 才能执行字节码；阻塞式 IO、time.sleep 与释放 GIL 的 C 扩展在进入系统调用前用' />

<Term word='切换请求与 eval breaker' text='PEP 659（3.11）引入 specializing adaptive interpreter：解释器在运行时统计指令执行次数，代码对象预热（quickening）后把通用指令改写为带内联缓存的特化版本，缓存放在 co_code 后面的 CACHE 条目里，自适应字节码存于 code object 的 _co_co' />


## 自适应特化、内联缓存与预热

PEP 659（3.11）引入 specializing adaptive interpreter：解释器在运行时统计指令执行次数，代码对象预热（quickening）后把通用指令改写为带内联缓存的特化版本，缓存放在 co_code 后面的 CACHE 条目里，自适应字节码存于 code object 的 _co_code_adaptive。

例如 BINARY_OP 对两个 int 特化、LOAD_ATTR 对同一类型与属性版本特化为实例取值，命中缓存就跳过通用查找；若类型变化则去优化回退。

`dis.dis(fn, show_caches=True)` 能看到 CACHE 槽，`adaptive=True` 在预热后可显示 LOAD_ATTR_INSTANCE_VALUE 一类特化指令；

本机 3.13 实测一个属性读取带 9 个 CACHE 条目。直接后果是微基准必须先预热：未预热走通用分派，预热后走特化路径，单次测量会把「是否触发 quickening」的噪声算进结论。timeit 的 number/repeat 参数正是为此提供重复执行；用 perf_counter 手测时也要丢弃前几轮。

3.13 还叠加了超级指令与实验性 JIT 骨架，指令级结论更要绑定具体版本。

```python
import sys, dis, time

print('gil_enabled', sys._is_gil_enabled())
print('switch_interval', sys.getswitchinterval())

def hot(x):
    return x + x + x + x

print('has_adaptive', hasattr(hot.__code__, '_co_code_adaptive'))
print('co_code_len', len(hot.__code__.co_code))

def bench():
    t0 = time.perf_counter()
    for i in range(200000):
        hot(i)
    return time.perf_counter() - t0

a = bench(); b = bench()
print('both_run', a > 0 and b > 0)
dis.dis(hot, show_caches=True)
```

<OutputBox title='主示例运行结果' output='gil_enabled True\nswitch_interval 0.005\nhas_adaptive True\nco_code_len 22\nboth_run True\n  6           RESUME                   0\n\n  7           LOAD_FAST_LOAD_FAST      0 (x, x)\n              BINARY_OP                0 (+)\n              CACHE                    0 (counter: 0)\n              LOAD_FAST                0 (x)\n              BINARY_OP                0 (+)\n              CACHE                    0 (counter: 0)\n              LOAD_FAST                0 (x)\n              BINARY_OP                0 (+)\n              CACHE                    0 (counter: 0)\n              RETURN_VALUE' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys, dis, time\n\nprint(&#39;gil_enabled&#39;, sys._is_gil_enabled())\nprint(&#39;switch_interval&#39;, sys.getswitchinterval())\n\ndef hot(x):\n    return x + x + x + x\n\nprint(&#39;has_adaptive&#39;, hasattr(hot.__code__, &#39;_co_code_adaptive&#39;))\nprint(&#39;co_code_len&#39;, len(hot.__code__.co_code))\n\ndef bench():\n    t0 = time.perf_counter()\n    for i in range(200000):\n        hot(i)\n    return time.perf_counter() - t0\n\na = bench(); b = bench()\nprint(&#39;both_run&#39;, a &gt; 0 and b &gt; 0)\ndis.dis(hot, show_caches=True)' :notes='["导入 sys 查构建状态，dis 反汇编，time 计时", "查询当前构建是否启用 GIL", "读取线程切换请求间隔，默认 0.005 秒", "定义热点函数，用于观察内联缓存与预热", "多次加法制造可特化的 BINARY_OP", "3.11+ 的 code object 带自适应字节码", "打印未特化 co_code 的字节长度", "定义一轮基准，重复调用触发 quickening", "记录起点", "循环调用热点函数", "连续执行让指令达到特化阈值", "返回本轮耗时", "跑两轮，前一轮兼作预热", "两轮都记录到耗时，基准可用", "show_caches=True 显示 BINARY_OP 后的 CACHE 内联缓存槽"]' title='第 118 讲 · GIL 源码、自适应解释器与无 GIL 路线' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**自适应特化可观测项**

| 项 | 本机 3.13 实测 | 含义 |
| --- | --- | --- |
| _co_code_adaptive | 存在 | code object 保存自适应字节码 |
| dis show_caches | BINARY_OP 后跟 CACHE | 内联缓存槽 |
| LOAD_ATTR 的 CACHE | 9 个条目 | 类型版本、键版本、描述符等缓存 |
| 预热后 adaptive | 显示 INSTANCE_VALUE 类特化 | 绕过通用属性查找 |


## 对照：预热前后的特化指令与计时

```python
import sys, threading

result = []
def worker():
    result.append(sys._is_gil_enabled())

t = threading.Thread(target=worker)
t.start(); t.join()
print('main_gil', sys._is_gil_enabled())
print('worker_gil', result[0])
sys.setswitchinterval(0.001)
print('switch_set', sys.getswitchinterval())
sys.setswitchinterval(0.005)
print('switch_restored', sys.getswitchinterval())
```

<OutputBox title='对照写法：先自己猜，再点开' output='main_gil True\nworker_gil True\nswitch_set 0.001\nswitch_restored 0.005' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import sys, dis, time\n\nprint(&#39;gil_enabled&#39;, sys._is_gil_enabled())\nprint(&#39;switch_interval&#39;, sys.getswitchinterval())\n\ndef hot(x):\n    return x + x + x + x\n\nprint(&#39;has_adaptive&#39;, hasattr(hot.__code__, &#39;_co_code_adaptive&#39;))\nprint(&#39;co_code_len&#39;, len(hot.__code__.co_code))\n\ndef bench():\n    t0 = time.perf_counter()\n    for i in range(200000):\n        hot(i)\n    return time.perf_counter() - t0\n\na = bench(); b = bench()\nprint(&#39;both_run&#39;, a &gt; 0 and b &gt; 0)\ndis.dis(hot, show_caches=True)", "note": "GIL 的获取释放点与 eval breaker"}, {"label": "对照 / 进阶", "code": "import sys, threading\n\nresult = []\ndef worker():\n    result.append(sys._is_gil_enabled())\n\nt = threading.Thread(target=worker)\nt.start(); t.join()\nprint(&#39;main_gil&#39;, sys._is_gil_enabled())\nprint(&#39;worker_gil&#39;, result[0])\nsys.setswitchinterval(0.001)\nprint(&#39;switch_set&#39;, sys.getswitchinterval())\nsys.setswitchinterval(0.005)\nprint(&#39;switch_restored&#39;, sys.getswitchinterval())", "note": "3.11 自适应特化、内联缓存与预热"}]' title='两种写法对照' note='差异集中在 GIL 的获取与释放点；先看输出，再找背后的规则。' />

```python
import dis, io

def read_attr(o):
    return o.value

class C:
    def __init__(self):
        self.value = 7

obj = C()
for _ in range(200):
    read_attr(obj)

buf = io.StringIO()
dis.dis(read_attr, file=buf, show_caches=True, adaptive=True)
text = buf.getvalue()
print('specialized_load_attr', 'INSTANCE_VALUE' in text or 'LOAD_ATTR_SLOT' in text)
print('cache_lines', text.count('CACHE'))
print('has_adaptive', hasattr(read_attr.__code__, '_co_code_adaptive'))
```

<OutputBox title='原理验证' output='specialized_load_attr True\ncache_lines 9\nhas_adaptive True' />


## 把「多线程一定慢」当成定理

<Callout type="warn" title='本讲最容易踩的坑' text='微基准只跑一次就下性能结论：3.11 起热点指令预热后才特化，未预热走通用分派，单次测量把 quickening 噪声算进结果' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：微基准只跑一次就下性能结论", "body": "3.11 起热点指令预热后才特化，未预热走通用分派，单次测量把 quickening 噪声算进结果", "tip": "用 timeit 的 repeat 或先丢弃前几轮预热；结论标注解释器版本与构建"}, {"title": "第 2 步：默认 3.13 已无 GIL，在 C 扩展里", "body": "标准构建仍启用 GIL，自由线程是实验性 --disable-gil 构建，且扩展假设持锁会在自由线程下崩溃", "tip": "用 sys._is_gil_enabled() 查询构建，按构建分别跑基准，逐个验证 C 扩展的线程安全"}, {"title": "第 3 步：把「多线程一定慢」当成定理", "body": "阻塞 IO 与释放 GIL 的 C 扩展能让线程真正重叠，纯 Python 计算才被 GIL 串行", "tip": "先分类热点是字节码、C 扩展还是 IO，再选进程、线程或 C 扩展路线，并实测而非套结论"}]' />


## PEP 659 到 PEP 703：自由线程化与技术判断框架

PEP 703 让 3.13 提供 --disable-gil 的实验性自由线程构建，`sys._is_gil_enabled()` 可查询当前构建是否启用 GIL（标准 GIL 构建返回 True）。

去掉 GIL 的代价落在实现：引用计数改为偏向线程局部加延迟合并，对象访问、字典与列表等容器需要细粒度锁或乐观读，单线程有可测的性能回退，依赖 C API 的扩展必须逐个验证线程安全，生态适配是长期迁移而非开关。

因此「无 GIL」不等于默认可用，更不等于所有多线程程序自动加速：纯 Python 计算在自由线程构建下能否并行还取决于对象访问的同步开销与扩展是否释放假设。

技术判断要按四步：先确认解释器版本与构建（`sys.version_info`、`sys.implementation.cache_tag`、`sys._is_gil_enabled`）；

再按构建与版本分别跑基准并预热；然后确认热点是在 Python 字节码、释放 GIL 的 C 扩展还是阻塞 IO；最后才选线程、进程或 C 扩展路线，并把结论写成带版本与构建标注的可复现脚本，而不是一句「Python 多线程慢」。

**并发选型按构建与负载判断**

| 热点类型 | 标准 GIL 构建 | 自由线程构建 |
| --- | --- | --- |
| 纯 Python 字节码计算 | 进程池 / C 扩展 | 需实测同步开销，未必线性加速 |
| 释放 GIL 的 C 扩展 | 线程池可并行 | 同样有效，且不再依赖释放假设 |
| 阻塞 IO | 线程池 / asyncio | 两者仍适用 |
| 依赖 C API 的旧扩展 | 假设持锁可用 | 必须验证线程安全，否则可能崩溃 |

<FlowTimeline :steps='[{"title": "GIL 的获取释放点与 eval breaker", "desc": "GIL 是保护解释器共享状态（引用计数、模块字典、类型系统）的互斥锁，不是语言规范，…", "tone": "blue"}, {"title": "3.11 自适应特化、内联缓存与预热", "desc": "PEP 659（3.11）引入 specializing adaptive inte…", "tone": "purple"}, {"title": "PEP 703 自由线程化与技术判断框架", "desc": "PEP 703 让 3.13 提供 --disable-gil 的实验性自由线程构建…", "tone": "orange"}, {"title": "工程落地", "desc": "带构建探测与预热的基准封装", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 默认 3.13 已无 GIL，在 C 扩展里假设一直持锁

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 微基准只跑一次就下性能结论 | 3.11 起热点指令预热后才特化，未预热走通用分派，单次测量把 quickening 噪声算进结果 | 用 timeit 的 repeat 或先丢弃前几轮预热；结论标注解释器版本与构建 |
| 默认 3.13 已无 GIL，在 C 扩展里假设一直持锁 | 标准构建仍启用 GIL，自由线程是实验性 --disable-gil 构建，且扩展假设持锁会在自由线程下崩溃 | 用 sys._is_gil_enabled() 查询构建，按构建分别跑基准，逐个验证 C 扩展的线程安全 |
| 把「多线程一定慢」当成定理 | 阻塞 IO 与释放 GIL 的 C 扩展能让线程真正重叠，纯 Python 计算才被 GIL 串行 | 先分类热点是字节码、C 扩展还是 IO，再选进程、线程或 C 扩展路线，并实测而非套结论 |


## 带构建探测与预热的基准封装

把性能结论写成可复现的脚本：入口先打印版本、cache_tag 与 GIL 状态，基准函数先预热再计时多轮取最小值，并对热点函数检查自适应字节码与内联缓存是否存在。真实容量规划里还要标注机器、编译选项与依赖版本，避免把某次构建的数字当成通用结论。

下面这段用标准库把「按版本与构建分别测」这条纪律固化成工具，重点看每个数字都带上了可核对的上下文。

```python
import sys, time, timeit

def context():
    print('py', sys.version_info[0], sys.version_info[1])
    print('tag', sys.implementation.cache_tag)
    print('gil_enabled', sys._is_gil_enabled())
    print('switch', sys.getswitchinterval())

def hot(x):
    return x + x + x + x

def bench(repeat=5, number=50000):
    for _ in range(2):
        timeit.timeit(lambda: hot(3), number=number)
    ts = [timeit.timeit(lambda: hot(3), number=number) for _ in range(repeat)]
    print('has_adaptive', hasattr(hot.__code__, '_co_code_adaptive'))
    print('min_seconds', round(min(ts), 6))

context()
bench()
```

<Callout type="idea" title='落地提示' text='关注自由线程化对扩展与依赖的兼容进度，性能结论按解释器版本与构建分别测' />

<CheckList id='P118b' title='上线前自检' :items='["能复现并解释「微基准只跑一次就下性能结论」", "能复现并解释「默认 3.13 已无 GIL，在 C 扩展里假设一直持锁」", "能复现并解释「把「多线程一定慢」当成定理」", "能用一条命令验证 GIL 的获取与释放点", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import dis, sys; print(sys.version.split()[0]); dis.dis(lambda x:x)"
```

把输入换成你自己的数据，观察结果是否仍符合 **GIL 的获取与释放点** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## ceval_gil.c 的 _gil_runtime_state 与 take_gil / drop_gil

GIL 是 Python/`ceval_gil.c` 里一套带定时等待的状态机。

核心结构 Include/internal/`pycore_gil.h` 的 _gil_runtime_state：_Py_atomic_int locked 表示是否被持有，interval 是默认 5ms 切换间隔（`sys.getswitchinterval()`），mutex 保护状态，cond 与 switch_number 用于等待唤醒，last_holder 记录上次持锁线程，自由线程构建下整条 take_gil/drop_gil 路径被旁路。

另一半是原子标志 gil_drop_request 与 eval_breaker 位掩码。等待线程在 take_gil 里用带 interval 超时的条件变量等待，超时即置 gil_drop_request 并设 _PY_EVAL_DROP_GIL_BIT；

执行线程通过 `CHECK_EVAL_BREAKER()` 查看 tstate->eval_breaker，看到该位后 drop_gil 并重新竞争。

轮询点不是每条指令，而是 JUMP_BACKWARD 回边、CALL、RESUME 这些插了检查的位置，所以没有调用与回边的纯计算会长时间占住 GIL。

_Py_HandlePending 同时处理信号、异步异常与 Py_MakePendingCalls，位定义见 `pycore_pystate.h`。

这解释了为什么调小 switchinterval 只增加切换开销，却不会让 CPU 密集的纯 Python 线程并行。

```python
import dis, sys

print('switch_ms', round(sys.getswitchinterval() * 1000, 1))
print('gil_enabled', sys._is_gil_enabled())

def read_attr(obj):
    return obj.value

class Box:
    def __init__(self):
        self.value = 42

box = Box()
co = read_attr.__code__
print('adaptive_len', len(co._co_code_adaptive))
print('co_code_len', len(co.co_code))
for _ in range(20000):
    read_attr(box)
ops = [i.opname for i in dis.get_instructions(read_attr, adaptive=True)]
print('load_attr_ops', sorted(set(o for o in ops if o.startswith('LOAD_ATTR'))))
```

<OutputBox title='扩展示例运行结果' output='switch_ms 5.0\ngil_enabled True\nadaptive_len 26\nco_code_len 26\nload_attr_ops [&#39;LOAD_ATTR_INSTANCE_VALUE&#39;]' />

<LineByLine code='import dis, sys\n\nprint(&#39;switch_ms&#39;, round(sys.getswitchinterval() * 1000, 1))\nprint(&#39;gil_enabled&#39;, sys._is_gil_enabled())\n\ndef read_attr(obj):\n    return obj.value\n\nclass Box:\n    def __init__(self):\n        self.value = 42\n\nbox = Box()\nco = read_attr.__code__\nprint(&#39;adaptive_len&#39;, len(co._co_code_adaptive))\nprint(&#39;co_code_len&#39;, len(co.co_code))\nfor _ in range(20000):\n    read_attr(box)\nops = [i.opname for i in dis.get_instructions(read_attr, adaptive=True)]\nprint(&#39;load_attr_ops&#39;, sorted(set(o for o in ops if o.startswith(&#39;LOAD_ATTR&#39;))))' :notes='["默认切换间隔 5ms，标准 3.13 构建仍启用 GIL", "定义只做属性读取的函数作为特化样本", "Box 实例字典里放一个 value 字段", "_co_code_adaptive 是 quickening 后的缓冲区", "co_code 是未特化原始字节码，两者长度相同", "循环两万次让 adaptive_counter 越过预热阈值", "adaptive=True 读取快速化后的指令名", "预热后 LOAD_ATTR 特化为带版本守卫的 INSTANCE_VALUE 变体", "3.11 PEP 659 自适应特化 + 内联缓存（_co_code_adaptive / CACHE），微基准必须预热", "dis.dis 用 show_caches=True 看缓存槽、adaptive=True 看预热后的特化指令", "3.12 PEP 684 每解释器 GIL；3.13 PEP 703 实验性自由线程，sys._is_gil_enabled() 可查", "性能结论按版本与构建分别测：先确认构建、再预热计时、再分类热点、最后选并发模型", "GIL 保护引用计数与解释器状态；阻塞 IO、sleep、释放 GIL 的 C 扩展能让线程重叠", "默认 switchinterval 0.005 秒，3.10+ 由 eval_breaker 在循环回边与调用处检查让出", "3.11 PEP 659 自适应特化 + 内联缓存（_co_code_adaptive / CACHE），微基准必须预热", "dis.dis 用 show_caches=True 看缓存槽、adaptive=True 看预热后的特化指令"]' title='扩展示例逐行讲解' />


## eval_breaker 位掩码与 CHECK_EVAL_BREAKER 的轮询点

**GIL 与 eval_breaker 的源码字段**

| 字段 / 宏 | 类型 | 含义 | 源码位置 |
| --- | --- | --- | --- |
| _gil_runtime_state.locked | _Py_atomic_int | GIL 是否被持有 | Include/internal/pycore_gil.h |
| _gil_runtime_state.interval | unsigned long | 默认 5ms 切换间隔 | Include/internal/pycore_gil.h |
| gil_drop_request | 原子标志 | 等待线程超时后置位 | Python/ceval_gil.c |
| eval_breaker | uintptr_t 位掩码 | 聚合放锁、信号、异步异常 | Include/internal/pycore_pystate.h |
| CHECK_EVAL_BREAKER() | 宏 | 在回边与调用处轮询 | Python/ceval_macros.h |

<Quiz no='118-X' q='3.10 起 CPython 请求当前线程释放 GIL 的主要机制是？' :options='["等待线程超时置 gil_drop_request，执行线程在 eval_breaker 轮询点自行放锁", "操作系统信号强制剥夺 GIL", "每条字节码执行完无条件切换", "由分代 GC 在收集前抢占"]' answer="0" explain='take_gil 用带 interval 超时的条件变量等待，超时置 gil_drop_request 并设 _PY_EVAL_DROP_GIL_BIT；执行线程只在 CHECK_EVAL_BREAKER 的轮询点看到该位才 drop_gil，属于协作式切换而非信号抢占。' />


## specialize.c 的内联缓存守卫与 3.13 的 uop 追踪

团队把一个用 C 写的指标聚合扩展从标准构建迁到 3.13t 自由线程构建，压测十分钟后进程 segfault，堆栈停在 PyList_GET_ITEM 与 Py_DECREF 之间。复盘发现扩展把一份共享 list 当作有 GIL 就安全，直接读元素、原地 PyList_SET_ITEM 且没有临界区；

GIL 构建下调用被串行化，问题被掩盖，自由线程构建下两个线程同时改 list 与元素引用计数，出现 use-after-free。

修复分三步：用 PEP 703 的 Py_mod_gil 槽声明 Py_MOD_GIL_NOT_USED，把共享容器读写收进 Py_BEGIN_CRITICAL_SECTION / Py_END_CRITICAL_SECTION，跨线程可见对象改用带锁 API。

下面是复盘脚本：先按 `sys._is_gil_enabled()` 判定构建，再用显式锁把读—改—写整段包成临界区。

```python
import sys, threading

gil_enabled = sys._is_gil_enabled() if hasattr(sys, '_is_gil_enabled') else True
print('build', 'gil' if gil_enabled else 'free-threaded')
shared = []
lock = threading.Lock()

def writer(tid):
    for i in range(1000):
        with lock:
            shared.append((tid, i))

ts = [threading.Thread(target=writer, args=(k,)) for k in range(4)]
for t in ts:
    t.start()
for t in ts:
    t.join()
print('items', len(shared))
print('no_corruption', len(shared) == 4000)
```


### tp_version_tag 失效如何让特化回退到通用指令

3.11 的自适应特化由 Python/`specialize.c` 驱动：把通用指令改写成带内联缓存的专用版本，用类型版本号做廉价守卫。

热点指令在 co_code 后预留若干 CACHE 条目（dis 的 `show_caches=True` 可见），quickening 阶段把 LOAD_ATTR 换成 ADAPTIVE 版本；

adaptive_counter 计数达阈值后 `specialize()` 按运行时类型挑实现，例如 LOAD_ATTR_INSTANCE_VALUE 把取实例字典固化成一次带 tp_version_tag 与 keys_version 校验的偏移读取。

守卫的 `PyTypeObject.tp_version_tag` 由 type_new 分配全局递增版本号，缓存记下当时的值，每次命中只比一次整数；

setattr 改类属性会经 Objects/`typeobject.c` 的 type_modified 让该类型及子类失效，下一次 DEOPT_IF 失败即回退通用分派并重新计数。缓存槽数由 inline_cache_entries`[opcode]` 表给出。

3.13 的 Python/`optimizer.c` 又引入第二层 uop 解释器，把热字节码翻译成微操作追踪，实验性 JIT 构建（--enable-experimental-jit）可把追踪编译成机器码；默认解释器仍停在特化字节码层，微基准必须按版本与构建分别测。


## 练习、选择题与速记卡

<Exercise title='基础：查询解释器构建与 GIL 状态' task='打印 sys.version_info[:2]、sys.implementation.cache_tag、sys._is_gil_enabled() 与 sys.getswitchinterval()，说明为什么结论要带这些字段。' solution='import sys\nprint(sys.version_info[0], sys.version_info[1])\nprint(sys.implementation.cache_tag)\nprint(sys._is_gil_enabled())\nprint(sys.getswitchinterval())' explain='版本决定特化与超级指令行为，cache_tag 区分实现与构建，_is_gil_enabled 区分标准与自由线程构建；同一数字换构建可能完全不同。' />

<Exercise title='进阶：证明预热会触发特化' task='循环调用一个属性读取函数多次后，用 dis.dis(adaptive=True) 检查是否出现特化指令，并与未预热版本对比 CACHE 行数。' solution='import dis, io\nclass C:\n    def __init__(self):\n        self.value = 7\ndef f(o):\n    return o.value\no = C()\nfor _ in range(200):\n    f(o)\nb = io.StringIO()\ndis.dis(f, file=b, adaptive=True, show_caches=True)\nprint(&#39;INSTANCE_VALUE&#39; in b.getvalue())' explain='执行达到 quickening 阈值后，LOAD_ATTR 被特化为实例取值并带内联缓存；adaptive=True 能看到特化名，未预热时只显示通用指令。' />

<Quiz no='118-1' q='3.11 起同一段代码预热前后性能可能不同，原因是？' :options='["热点指令被自适应特化并写入内联缓存，命中缓存跳过通用分派", "解释器把代码编译成机器码", "GIL 在预热后被释放", "gc 被自动关闭"]' answer="0" explain='PEP 659 让热点指令 quickening 后改写成特化版本并缓存类型信息；未预热走通用分派，因此微基准必须预热并多轮取最小值。' />

<Quiz no='118-2' q='关于 3.13 自由线程构建，准确的说法是？' :options='["它是实验性 --disable-gil 构建，单线程有回退且 C 扩展需逐个验证", "所有 3.13 安装默认无 GIL", "去掉 GIL 后所有多线程程序自动加速", "sys._is_gil_enabled 在所有版本都存在"]' answer="0" explain='标准 GIL 构建仍启用 GIL，自由线程需专门构建；引用计数与容器同步改造带来单线程回退，依赖 C API 的扩展必须验证线程安全。' />

<Quiz no='118-3' q='关于 GIL 与业务数据竞争，正确的是？' :options='["counter += 1 跨多条字节码，仍需 threading.Lock", "有 GIL 就无需任何锁", "只有多进程才需要锁", "用 dis 看过字节码就不用加锁"]' answer="0" explain='GIL 只保证单条字节码原子；读改写由多条指令组成，切换可发生在指令之间造成丢失更新，业务侧复合操作必须加锁。' />

<Predict no='118-P' q='标准 3.13 构建里 sys._is_gil_enabled() 与 sys.getswitchinterval() 最可能返回什么？' :options='["True 与 0.005", "False 与 0.005", "True 与 0.5"]' answer='0' output='True 与 0.005' explain='标准构建仍启用 GIL，故 _is_gil_enabled() 返回 True；切换请求间隔默认 0.005 秒。只有 --disable-gil 自由线程构建才会返回 False。' />

<KnowledgeCard :points='["GIL 保护引用计数与解释器状态；阻塞 IO、sleep、释放 GIL 的 C 扩展能让线程重叠", "默认 switchinterval 0.005 秒，3.10+ 由 eval_breaker 在循环回边与调用处检查让出", "3.11 PEP 659 自适应特化 + 内联缓存（_co_code_adaptive / CACHE），微基准必须预热", "dis.dis 用 show_caches=True 看缓存槽、adaptive=True 看预热后的特化指令", "3.12 PEP 684 每解释器 GIL；3.13 PEP 703 实验性自由线程，sys._is_gil_enabled() 可查", "性能结论按版本与构建分别测：先确认构建、再预热计时、再分类热点、最后选并发模型"]' :pitfalls='["微基准只跑一次就下性能结论", "默认 3.13 已无 GIL，在 C 扩展里假设一直持锁", "把「多线程一定慢」当成定理", "把「无 GIL」当成默认可用的现有能力，或在 C 扩展里假设持有 GIL，都会在自由线程构建下崩溃"]' summary='3.11 起解释器会在运行时把热点指令特化并缓存，因此同一段代码在预热前后性能可能差很多，微基准必须预热' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| GIL 保护引用计数与解释器状态；阻塞 IO、sleep、释放 GIL 的 C 扩展能让线程重叠 | 建立直觉 |
| 默认 switchinterval 0.005 秒，3.10+ 由 eval_breaker 在循环回边与调用处检查让出 | 跑通示例 |
| 3.11 PEP 659 自适应特化 + 内联缓存（_co_code_adaptive / CACHE），微基准必须预热 | 深入边界 |
| dis.dis 用 show_caches=True 看缓存槽、adaptive=True 看预热后的特化指令 | 工程落地 |
| 3.12 PEP 684 每解释器 GIL；3.13 PEP 703 实验性自由线程，sys._is_gil_enabled() 可查 | 随堂检测 |
| 性能结论按版本与构建分别测：先确认构建、再预热计时、再分类热点、最后选并发模型 | 复盘 |

1. GIL 保护引用计数与解释器状态；阻塞 IO、sleep、释放 GIL 的 C 扩展能让线程重叠

2. 默认 switchinterval 0.005 秒，3.10+ 由 eval_breaker 在循环回边与调用处检查让出

3. 3.11 PEP 659 自适应特化 + 内联缓存（_co_code_adaptive / CACHE），微基准必须预热

[下一讲：极致优化：从剖析到 C 扩展的十倍案例](/advanced/optimization)

<FillBlank no='118-F' tpl='___ sys, dis, time' :answers='["import"]' hint='回想本讲关于 GIL 的获取与释放点 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 GIL 的获取释放点与 eval breaker 的落点。' />
