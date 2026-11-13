---
title: 第 059 讲 · 阶段综合：简易性能分析器与内存哨兵
description: 把运行时机制做成一个可用工具
---

<StageHeader stage='L5 · 核心机制' level='★★★★★' time='60 分钟' goal='把运行时机制做成一个可用工具' prereq='第 058 讲 · 性能剖析：timeit、cProfile 与 tracemalloc' />

# 第 059 讲 · 阶段综合：简易性能分析器与内存哨兵

前面几讲分别给了查找、访问、拷贝和测量这几件工具，都只在一条执行流里打转。进入并发之前，适合做一次阶段综合，把它们收拢成一件能跑的工具，检验自己是不是真懂了。设想一个线上脚本内存一路往上爬，没人说得清是哪段在涨、涨到多少该有人知道。

由简到繁：从 sys.setprofile 采集事件起步，拼出调用树与自耗时，用 tracemalloc 快照记下增量，接着加阈值告警和报告生成，末了量化自身开销与采样间隔。前置是前几讲的剖析手段、函数与异常处理；做完后你得到能按函数过滤、可在灰度环境开启的性能分析器，也为下一阶段的并发观察留好底子。


## 想加哨兵，却把吞吐和内存都拖垮

生产服务偶发内存涨到 OOM，团队想加一个「慢调用 + 内存增长」的哨兵，但直接用 cProfile 全量采集会拖垮吞吐，用 tracemalloc 常驻又多出两倍内存。有人写了个 `sys.setprofile` 的采集器，灰度时报告里却混进了别的线程事件，调用树对不上；

还有人把每个函数进出都记一条日志，结果分析器自身的开销比业务还高，测出来的耗时全是噪声。更麻烦的是阈值告警：按总内存设阈值会被正常缓存误报，按单次增量设阈值又漏掉缓慢泄漏。这些矛盾不是调参能绕过去的：采样精度与侵入性是一对必须显式量化的取舍。

本讲把运行时机制真正做成一个可用工具——用 setprofile 建调用树、用 tracemalloc 快照差值做阈值、用开关与采样间隔把开销关进笼子，并解释 3.12+ 为什么该换成 `sys.monitoring`。

<Callout type="warn" title='先看一个真实会出错的写法' text='多线程里用全局 setprofile，调用树对不上：setprofile 只作用于当前线程，但 profile 状态可被 threading.setprofile 传播到新线程，事件混在一起' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段五 · 核心机制与运行时 |
| 前置 | 第 058 讲 · 性能剖析：timeit、cProfile 与 tracemalloc |
| 难度 / 建议时长 | ★★★★★ · 60 分钟 |
| 本讲新增 | sys.setprofile 采集、调用树与自耗时、tracemalloc 快照 |
| 一句话目标 | 把运行时机制做成一个可用工具 |
| 为下一讲铺垫 | 并发、并行与 IO 模型全景 |


## sys.setprofile 的 call 与 return 事件

`sys.setprofile(func)` 给当前线程装一个回调，签名是 (frame, event, arg)：Python 函数进出发 'call' / 'return'，C 函数发 'c_call' / 'c_return' / 'c_exception'，arg 在 return 时是返回值、在异常时是三元组。

`sys.getprofile()` 读回，`sys.setprofile(None)` 关闭。

它只对设置它的那个线程生效，其他线程要 `threading.setprofile`；

因此在多线程程序里用全局回调会把无关线程的事件也算进当前调用树，必须按 `threading.get_ident()` 分桶。

重建调用树的标准做法是维护一个栈：'call' 时压入 (函数名, perf_counter 起点, 子耗时累加器)，'return' 时弹出并算 `dt = now` - t0，本帧 `self = dt` - child_time，`cumulative = dt`，并把 dt 累加到父帧的 child_time。

这样一次遍历就能同时得到每个函数的调用次数、自耗时与累计耗时。注意 setprofile 看不到行级事件（那是 `sys.settrace` 的 'line' / 'opcode'），且回调里任何 Python 调用本身都可能产生新事件，回调必须短、只做入栈出栈与累加。

**sys.setprofile 事件类型与 arg 含义**

| event | 触发时机 | arg | 建树用途 |
| --- | --- | --- | --- |
| call | 进入 Python 函数 | None | 压栈并记录起点 |
| return | 离开 Python 函数 | 返回值 | 弹栈、算 self 与 cumtime |
| c_call | 调用 C 函数 | C 函数对象 | 可跳过或单独计数 |
| c_return / c_exception | C 调用返回或抛异常 | 返回值 / 异常三元组 | 标记外部耗时 |


## 用栈重建父子调用关系与自耗时

```python
import sys
import time

class MiniProfiler:
    def __init__(self):
        self.stack = []
        self.stats = {}
    def __call__(self, frame, event, arg):
        name = frame.f_code.co_name
        if event == 'call':
            self.stack.append([name, time.perf_counter(), 0.0])
        elif event == 'return' and self.stack:
            key, t0, child = self.stack.pop()
            dt = time.perf_counter() - t0
            rec = self.stats.setdefault(key, [0, 0.0, 0.0])
            rec[0] += 1
            rec[1] += dt - child
            rec[2] += dt
            if self.stack:
                self.stack[-1][2] += dt
        return self

def leaf(n):
    return sum(i * i for i in range(n))

def middle():
    return leaf(2000) + leaf(2000)

def top():
    return middle()

sys.setprofile(MiniProfiler())
top()
prof = sys.getprofile()
sys.setprofile(None)
print('top calls', prof.stats['top'][0])
print('middle calls', prof.stats['middle'][0])
print('leaf calls', prof.stats['leaf'][0])
print('top cum > self', prof.stats['top'][2] > prof.stats['top'][1])
```

<OutputBox title='主示例运行结果' output='top calls 1\nmiddle calls 1\nleaf calls 2\ntop cum &gt; self True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys\nimport time\n\nclass MiniProfiler:\n    def __init__(self):\n        self.stack = []\n        self.stats = {}\n    def __call__(self, frame, event, arg):\n        name = frame.f_code.co_name\n        if event == &#39;call&#39;:\n            self.stack.append([name, time.perf_counter(), 0.0])\n        elif event == &#39;return&#39; and self.stack:\n            key, t0, child = self.stack.pop()\n            dt = time.perf_counter() - t0\n            rec = self.stats.setdefault(key, [0, 0.0, 0.0])\n            rec[0] += 1\n            rec[1] += dt - child\n            rec[2] += dt\n            if self.stack:\n                self.stack[-1][2] += dt\n        return self\n\ndef leaf(n):\n    return sum(i * i for i in range(n))\n\ndef middle():\n    return leaf(2000) + leaf(2000)\n\ndef top():\n    return middle()\n\nsys.setprofile(MiniProfiler())\ntop()\nprof = sys.getprofile()\nsys.setprofile(None)\nprint(&#39;top calls&#39;, prof.stats[&#39;top&#39;][0])\nprint(&#39;middle calls&#39;, prof.stats[&#39;middle&#39;][0])\nprint(&#39;leaf calls&#39;, prof.stats[&#39;leaf&#39;][0])\nprint(&#39;top cum &gt; self&#39;, prof.stats[&#39;top&#39;][2] &gt; prof.stats[&#39;top&#39;][1])' :notes='["导入 sys，使用 setprofile / getprofile", "导入 time，用 perf_counter 量每个帧的耗时", "把事件折叠成调用树的分析器", "初始化栈与统计表", "stack 保存 名称/起点/子耗时 三元组", "stats 按函数名累计 次数/自耗时/累计耗时", "回调签名固定为 (frame, event, arg)", "从 code object 取函数名作统计键", "只在 call 事件压栈", "记录高精度起点，第三位随后累加子耗时", "return 事件且栈非空才结算", "取出 名称、起点、已累计的子耗时", "dt 是本帧从进入到退出的墙钟", "每函数一条记录：调用数、self、cumulative", "累计调用次数", "self = dt 减去子帧耗时", "cumulative 直接累加 dt", "若还有父帧，把本帧耗时记到父账上", "父帧的 child 增加，父才算得出 self", "返回 self 对 setprofile 无害，返回值被丢弃", "定义最内层计算函数，制造两次子调用", "生成器求和，消耗真实 CPU", "中间层", "调用 leaf 两次", "顶层作为调用树根", "只委托给 middle", "安装 profiler，本线程调用都会触发回调", "执行被测调用树", "取回 profiler 实例以读取统计", "先关钩子再读结果，避免把读取本身计入", "top 只被调用一次", "middle 一次", "leaf 两次", "top 的 cumtime 含全部子调用，必大于其 self"]' title='第 059 讲 · 阶段综合：简易性能分析器与内存哨兵' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='layers3' title='第 059 讲 · 分层视角' labels='sys.setprofile 事件与调用|tracemalloc 快照差值与阈值告|开销量化与 sys.monitoring|开销量化' caption='开销量化与 sys.monitoring 迁移' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **开销量化** 落在哪一层。


### 多线程事件为何会张冠李戴

```python
import sys
import time

def add(a, b):
    return a + b

def busy():
    total = 0
    for i in range(30000):
        total = add(total, i)
    return total

def timed(fn):
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0

plain = min(timed(busy) for _ in range(3))
def nop(frame, event, arg):
    return None
sys.setprofile(nop)
profiled = min(timed(busy) for _ in range(3))
sys.setprofile(None)
print('profiled >= plain', profiled >= plain)
print('overhead ratio > 1', profiled / plain > 1.0)
```

<OutputBox title='原理验证' output='profiled &gt;= plain True\noverhead ratio &gt; 1 True' />


## tracemalloc 快照差值与阈值告警

`tracemalloc.start(nframe)` 的 nframe 决定保留几层回溯，越深信息越全、开销越大；

典型取 1 到 3。

哨兵在基线点 `take_snapshot()`，在检查点再 `take_snapshot()`，用 `snap_now.compare_to`(snap_base, 'lineno') 得到 StatisticDiff 列表，按 size_diff 降序取前几行，累加正增量作为「本次净增长」。

阈值应按增量而非 `get_traced_memory()` 的绝对值来设：缓存预热、常量池都会让绝对值上升，但稳定后快照差值应趋近于零。

可设两级阈值：单窗口增量超过 N 字节发告警，连续 K 个窗口持续增长判为可疑泄漏。`reset_peak()`（3.9+）只重置峰值计数器，不影响快照；`stop()` 释放追踪数据。报告要带 trace_id、窗口时长、Top-N 分配行与当前/峰值字节，格式固定便于 CI 解析。

千万记住 tracemalloc 只统计 Python 层分配，C 扩展里 malloc 的缓冲区不在账上，怀疑第三方库泄漏要配 jemalloc / valgrind 等外部工具。

**哨兵阈值与误报对照**

| 信号 | 计算方式 | 误报来源 | 建议处置 |
| --- | --- | --- | --- |
| 单窗净增长 | compare_to 正 size_diff 求和 | 缓存预热、一次性常量池 | 设两级阈值 + 连续 K 窗确认 |
| 绝对 current 字节 | get_traced_memory()[0] | 正常缓存增长即误报 | 只作趋势，不作告警 |
| 峰值 peak | get_traced_memory()[1] | 一次性大对象 | 配合 reset_peak (3.9+) 分窗 |
| Top-N 分配行 | statistics('lineno') 或 compare_to | nframe 过浅定位不准 | nframe 取 1-3，报告带完整 traceback 摘要 |

<Callout type="tip" title='核心心智模型' text='sys.setprofile(func) 给当前线程装一个回调，签名是 (frame, event, arg)：Python 函数进出发 &#39;call&#39; / &#39;return&#39;，C 函数发 &#39;c_call&#39; / &#39;c_return&#39; / &#39;c_exception&#39;，arg 在 return 时是返回值、' />


## 按绝对内存设阈值为什么天天误报

<Callout type="warn" title='本讲最容易踩的坑' text='多线程里用全局 setprofile，调用树对不上：setprofile 只作用于当前线程，但 profile 状态可被 threading.setprofile 传播到新线程，事件混在一起' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：多线程里用全局 setprofile，调用树", "body": "setprofile 只作用于当前线程，但 profile 状态可被 threading.setprofile 传播到新线程，事件混在一起", "tip": "按 threading.get_ident() 给每个线程单独建栈与 stats，报告时按线程分桶"}, {"title": "第 2 步：按 get_traced_memory() ", "body": "缓存预热、常量池、一次性大对象都会抬高绝对值，稳定后不再增长", "tip": "改用 compare_to 的 size_diff 增量，并要求连续 K 个窗口持续增长才告警"}, {"title": "第 3 步：在 profile 回调里做日志、格式化或加", "body": "回调本身是 Python 调用，会触发新事件、形成递归或把分析器自身耗时算进业务", "tip": "回调只做压栈/出栈与数值累加，日志与报告在 setprofile(None) 之后统一输出"}]' />


## 采样精度与侵入性：开销量化

任何 profiler 都在改变被测对象。量化方法是同一段纯 Python 热点分别在「无钩子」与「装回调」下各跑若干轮，取 min 计时并算比值；函数越小、调用越密，setprofile 的相对开销越大，因为每个 call/return 都要穿过 Python 回调。

工程上必须提供三个开关：按函数名过滤（只追踪关心的前缀）、采样间隔（每 N 次事件记一次）、上下文开关（灰度时临时开启）。

3.12 起 `sys.monitoring`（PEP 669）给出更轻的路径：`use_tool_id(tool_id, name)` 占一个工具槽，`set_events(tool_id, 事件位)` 订阅 PY_START / PY_RETURN / PY_UNWIND 等，register_callback 注册回调，事件在解释器指令流里就地检查、不构造 frame 对象，开销比 setprofile 低一个量级；

用 free_tool_id 释放。工具 ID 有上限（常用 0-5，其中 0/1 留给调试器与优化器），同一事件位只能被一个工具占用，冲突时 set_events 会抛 ValueError。

3.13 沿用这套接口并加入实验性 JIT 骨架，跨版本采集脚本要在启动时探测 hasattr(sys, 'monitoring') 再决定走哪条路径。

**setprofile 与 sys.monitoring 对照**

| 维度 | sys.setprofile | sys.monitoring (3.12+ PEP 669) | 说明 |
| --- | --- | --- | --- |
| 安装方式 | sys.setprofile(func) | use_tool_id + set_events + register_callback | 后者按工具槽隔离 |
| 回调参数 | (frame, event, arg) | (code, offset) 视事件而定 | 后者不构造 frame 对象 |
| 事件位 | 固定几类 | PY_START / PY_RETURN / PY_UNWIND 等可订阅 | 只订阅所需，开销更低 |
| 线程作用域 | 仅当前线程，需 threading.setprofile | 全局工具槽，按事件位 | 多线程要按 ident 分桶 |
| 并发占用 | 可被覆盖无提示 | 同一事件位被占用时 set_events 抛 ValueError | 工具 ID 常用 0-5 |


### sys.monitoring 为何能低一个量级

```python
import sys

events = []
def on_start(code, offset):
    events.append(code.co_name)

def work():
    return sum(i for i in range(50))

if hasattr(sys, 'monitoring'):
    mon = sys.monitoring
    mon.use_tool_id(2, 'sentinel')
    mon.set_events(2, mon.events.PY_START)
    mon.register_callback(2, mon.events.PY_START, on_start)
    work()
    mon.set_events(2, 0)
    mon.register_callback(2, mon.events.PY_START, None)
    mon.free_tool_id(2)
    print('monitoring available', True)
    print('saw work', 'work' in events)
    print('event count > 0', len(events) > 0)
else:
    print('monitoring available', False)
```

<OutputBox title='对照写法：先自己猜，再点开' output='monitoring available True\nsaw work True\nevent count &gt; 0 True' guess="true" />


## 对照：两种采集口径的开销差

<CodeTabs :tabs='[{"label": "主示例", "code": "import sys\nimport time\n\nclass MiniProfiler:\n    def __init__(self):\n        self.stack = []\n        self.stats = {}\n    def __call__(self, frame, event, arg):\n        name = frame.f_code.co_name\n        if event == &#39;call&#39;:\n            self.stack.append([name, time.perf_counter(), 0.0])\n        elif event == &#39;return&#39; and self.stack:\n            key, t0, child = self.stack.pop()\n            dt = time.perf_counter() - t0\n            rec = self.stats.setdefault(key, [0, 0.0, 0.0])\n            rec[0] += 1\n            rec[1] += dt - child\n            rec[2] += dt\n            if self.stack:\n                self.stack[-1][2] += dt\n        return self\n\ndef leaf(n):\n    return sum(i * i for i in range(n))\n\ndef middle():\n    return leaf(2000) + leaf(2000)\n\ndef top():\n    return middle()\n\nsys.setprofile(MiniProfiler())\ntop()\nprof = sys.getprofile()\nsys.setprofile(None)\nprint(&#39;top calls&#39;, prof.stats[&#39;top&#39;][0])\nprint(&#39;middle calls&#39;, prof.stats[&#39;middle&#39;][0])\nprint(&#39;leaf calls&#39;, prof.stats[&#39;leaf&#39;][0])\nprint(&#39;top cum &gt; self&#39;, prof.stats[&#39;top&#39;][2] &gt; prof.stats[&#39;top&#39;][1])", "note": "sys.setprofile 事件与调用树重建"}, {"label": "对照 / 进阶", "code": "import sys\n\nevents = []\ndef on_start(code, offset):\n    events.append(code.co_name)\n\ndef work():\n    return sum(i for i in range(50))\n\nif hasattr(sys, &#39;monitoring&#39;):\n    mon = sys.monitoring\n    mon.use_tool_id(2, &#39;sentinel&#39;)\n    mon.set_events(2, mon.events.PY_START)\n    mon.register_callback(2, mon.events.PY_START, on_start)\n    work()\n    mon.set_events(2, 0)\n    mon.register_callback(2, mon.events.PY_START, None)\n    mon.free_tool_id(2)\n    print(&#39;monitoring available&#39;, True)\n    print(&#39;saw work&#39;, &#39;work&#39; in events)\n    print(&#39;event count &gt; 0&#39;, len(events) &gt; 0)\nelse:\n    print(&#39;monitoring available&#39;, False)", "note": "tracemalloc 快照差值与阈值告警"}]' title='两种写法切换看' />


## ceval 主循环里的 profile 回调代价

setprofile 的回调由 ceval 主循环在 _PyEval_SetProfile 之后于函数调用/返回处触发，解释器把当前 PyFrameObject、事件类型与参数打包成一个 Python 层调用；这意味着每个事件都要构造参数元组、跨越 C/Python 边界，函数越小、调用越密，相对开销越大。

调用树重建依赖一个不变量：call 与 return 严格嵌套，因此用栈即可还原父子关系，父帧的 `self = 自身墙钟` - 各子帧墙钟之和，`cumulative = 自身墙钟`。

多线程下各线程有独立的 profile 状态，全局回调看到的事件来自所有线程，若不按 `threading.get_ident()` 分桶就会出现「张冠李戴」的调用树。

tracemalloc 在 _PyObject_Malloc 层把分配大小与回溯压进哈希表，compare_to 对两次聚合表做差，故 size_diff 是净增长而非瞬时占用。

`sys.monitoring` 把事件检查内联进指令分派：解释器查「当前工具是否订阅了这一位」，命中才调用轻量回调，省去 frame 构造与通用事件分发，因此能低一个量级的开销；事件位被独占的设计则避免多个工具互相踩踏。

<Term word='sys.setprofile 采集' text='sys.setprofile(func) 给当前线程装一个回调，签名是 (frame, event, arg)：Python 函数进出发 &#39;call&#39; / &#39;return&#39;，C 函数发 &#39;c_call&#39; / &#39;c_return&#39; / &#39;c_exception&#39;，arg 在 return 时是返回值、在异常时是三元组。s' />

<Term word='调用树与自耗时' text='tracemalloc.start(nframe) 的 nframe 决定保留几层回溯，越深信息越全、开销越大；典型取 1 到 3。哨兵在基线点 take_snapshot()，在检查点再 take_snapshot()，用 snap_now.compare_to(snap_base, &#39;lineno&#39;) 得到 Sta' />


## 可灰度开启的简易性能分析器与内存哨兵

给一个内部服务加观测能力，要求默认零成本、灰度时临时开启、报告能直接进日志管道。实现思路是把「调用树采集」和「内存快照」合成一个类：构造时接收关心函数名前缀、采样间隔与内存阈值；start 里按探测结果选择 `sys.monitoring` 或回退到 `sys.setprofile`，并 start tracemalloc；

每次检查点做 compare_to 求净增长，超阈值就生成一条带 Top-N 分配行的告警；stop 输出按 cumtime 排序的调用树并释放所有钩子。

开关采用上下文管理器，保证异常路径也会 `setprofile(None)` 与 `tracemalloc.stop()`，避免把钩子永久留在进程里。

真实部署再把报告改成结构化日志并接告警系统，这里的片段重点是可运行、可关、开销量化三件事。

```python
import io
import pstats
import sys
import time
import tracemalloc

class Sentinel:
    def __init__(self, prefix='', byte_limit=1 << 20):
        self.prefix = prefix
        self.byte_limit = byte_limit
        self.events = 0
        self.base = None
    def __enter__(self):
        tracemalloc.start(1)
        self.base = tracemalloc.take_snapshot()
        sys.setprofile(self._on_event)
        return self
    def _on_event(self, frame, event, arg):
        if event == 'call' and frame.f_code.co_name.startswith(self.prefix):
            self.events += 1
        return self._on_event
    def checkpoint(self):
        now = tracemalloc.take_snapshot()
        diff = now.compare_to(self.base, 'lineno')
        grown = sum(d.size_diff for d in diff if d.size_diff > 0)
        top = sorted(diff, key=lambda d: -d.size_diff)[:3]
        return grown, [d.size_diff for d in top]
    def __exit__(self, *exc):
        sys.setprofile(None)
        grown, top = self.checkpoint()
        print('events', self.events, 'grown', grown, 'alert', grown > self.byte_limit)
        print('top diffs', top, 'peak', tracemalloc.get_traced_memory()[1] > 0)
        tracemalloc.stop()

def hot(n):
    return [dict(i=i) for i in range(n)]

if __name__ == '__main__':
    with Sentinel(prefix='hot', byte_limit=1 << 30) as s:
        hot(3000)

```

<Callout type="idea" title='落地提示' text='提供按函数过滤、采样间隔与上下文开关，让工具能在生产灰度环境里安全开启' />

<CheckList id='P059b' title='上线前自检' :items='["能复现并解释「多线程里用全局 setprofile，调用树对不上」", "能复现并解释「按 get_traced_memory() 的绝对值设内存告」", "能复现并解释「在 profile 回调里做日志、格式化或加锁」", "能用一条命令验证 sys.setprofile 采集", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import cProfile; cProfile.run('sum(range(100000))', sort='cumtime')"
```

把输入换成你自己的数据，观察结果是否仍符合 **sys.setprofile 采集** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 多线程里用全局 setprofile，调用树对不上 | setprofile 只作用于当前线程，但 profile 状态可被 threading.setprofile 传播到新线程，事件混在一起 | 按 threading.get_ident() 给每个线程单独建栈与 stats，报告时按线程分桶 |
| 按 get_traced_memory() 的绝对值设内存告警，天天误报 | 缓存预热、常量池、一次性大对象都会抬高绝对值，稳定后不再增长 | 改用 compare_to 的 size_diff 增量，并要求连续 K 个窗口持续增长才告警 |
| 在 profile 回调里做日志、格式化或加锁 | 回调本身是 Python 调用，会触发新事件、形成递归或把分析器自身耗时算进业务 | 回调只做压栈/出栈与数值累加，日志与报告在 setprofile(None) 之后统一输出 |


## sys_setprofile 到 _PyEval_SetProfile：frame 物化的开销根源

`sys.setprofile(f)` 落到 Python/`sysmodule.c` 的 sys_setprofile，再调 _PyEval_SetProfile 把回调挂在 PyThreadState 的 c_profilefunc / cprofileobj 上；

之后 `ceval.c` 在每次 CALL 分派前后经 Python/`legacy_tracing.c` 触发 call / return / c_call / c_return 事件。

真正的开销不在回调里的几行 Python，而在回调签名要求一个 frame 对象。

3.11 起解释器帧不再是常驻的 PyFrameObject：_PyInterpreterFrame 直接放在线程的数据栈 chunk 里（Python/`frame.c` 的 _PyThreadState_PushFrame），只有谁真正需要 frame 对象时才由 _PyFrame_MakeAndSetFrameObject 物化一次，顺带填 f_locals、f_back 链与 f_lineno。

setprofile 每个 call/return 都强制走这一步，于是函数越小、调用越密，物化占整段时间的比重越高，这就是分析器自身开销比业务还高的结构性原因。由此还能推出两条：回调里再调用任何 Python 函数都会被解释器暂时屏蔽事件分发（本机实测 cb 自己不会出现在采集列表里），否则会无限递归；

而 setprofile 只看当前线程，多线程要配合 `threading.setprofile` 并按 `threading.get_ident` 分桶。

3.12 把这套旧 tracing 单独抽到 Python/`legacy_tracing.c`，本身就是为了给新机制让路。

```python
import sys

print('has monitoring', hasattr(sys, 'monitoring'))
print('has setprofile', hasattr(sys, 'setprofile'))
seen = []
def cb(frame, event, arg):
    if event == 'call':
        seen.append(frame.f_code.co_name)
    return cb

sys.setprofile(cb)
def leaf(x):
    return x + 1
leaf(1)
sys.setprofile(None)
print('captured leaf', 'leaf' in seen)
print('captured cb', 'cb' in seen)
print('tool ids', [sys.monitoring.DEBUGGER_ID, sys.monitoring.PROFILER_ID, sys.monitoring.OPTIMIZER_ID])

```

<OutputBox title='扩展示例运行结果' output='has monitoring True\nhas setprofile True\ncaptured leaf True\ncaptured cb False\ntool ids [0, 2, 5]' />

<LineByLine code='import sys\n\nprint(&#39;has monitoring&#39;, hasattr(sys, &#39;monitoring&#39;))\nprint(&#39;has setprofile&#39;, hasattr(sys, &#39;setprofile&#39;))\nseen = []\ndef cb(frame, event, arg):\n    if event == &#39;call&#39;:\n        seen.append(frame.f_code.co_name)\n    return cb\n\nsys.setprofile(cb)\ndef leaf(x):\n    return x + 1\nleaf(1)\nsys.setprofile(None)\nprint(&#39;captured leaf&#39;, &#39;leaf&#39; in seen)\nprint(&#39;captured cb&#39;, &#39;cb&#39; in seen)\nprint(&#39;tool ids&#39;, [sys.monitoring.DEBUGGER_ID, sys.monitoring.PROFILER_ID, sys.monitoring.OPTIMIZER_ID])\n' :notes='["3.12 起 sys.monitoring 可用，旧 setprofile 仍保留", "setprofile 是历代都有的接口", "用列表收集 call 事件里的函数名", "回调签名固定为 frame、event、arg", "只记 call 事件，return 与 C 事件不进列表", "frame.f_code.co_name 就是被调函数的名字", "返回自身以维持回调，某些实现里可不写", "安装回调到当前线程", "定义一个极小函数，放大回调的相对开销", "调用一次 leaf，触发一次 call 与一次 return", "关闭回调，避免后续打印继续产生事件", "leaf 被采集到，证明回调确实看到了用户函数", "cb 自身没被采集，解释器在回调期间屏蔽了事件分发", "3.13 的保留槽位是 0 调试器、2 分析器、5 优化器", "tracemalloc 用 compare_to 的 size_diff 净增量告警，比 current 绝对值少误报；nframe 取 1-3 控开销", "分析器自身有侵入性：回调里只做压栈与累加，日志在 setprofile(None) 之后输出，并用比值量化开销"]' title='扩展示例逐行讲解' />

<ConceptDiagram type='flow4' title='第 059 讲 · 扩展图解' labels='_PyInterpreterFrame 在数据栈|setprofile 回调|强制物化 PyFrameObject|f_back 链与 f_locals 填充' caption='旧式 profile 的开销不在回调逻辑，而在每次调用边界把轻量解释器帧物化成完整 frame 对象。' />


### instrumentation.c 与 specializing interpreter 的反优化代价

PEP 669 把事件检查搬到指令层：Python/`instrumentation.c` 在 `sys.monitoring.set_events(tool_id, event_set)` 之后，直接改写 code object 的 co_code_adaptive，在 PY_START / PY_RETURN / PY_UNWIND 等位置插入 INSTRUMENTED_* 变体指令；

回调收到的是 code 对象、指令偏移与若干参数，不构造 frame，因此少了一整层物化。

代价与 specializing interpreter 直接冲突：3.11 起热点指令会被 quicken 成 ADAPTIVE 家族并特化成具体类型，开启 instrumentation 时这些已特化的指令要 deopt 回通用形式，因为插入的监控点会破坏指令替换的前提；

也就是说，即便工具一次回调都不干活，热路径也会因为失去特化而固定回退几个百分点。工具槽位有限且按用途保留，本机 3.13 实测 `DEBUGGER_ID=0`、`PROFILER_ID=2`、`OPTIMIZER_ID=5`，用户可用的是剩余编号；

同一事件位只能被一个工具订阅，冲突时 set_events 抛 ValueError。

回调还可以返回 `sys.monitoring.DISABLE`，让某个 (code, offset) 位置永久关闭该事件，实现采几次就不采的零成本采样。

架构上的取舍因此很清楚：插桩式给的是精确调用树但要付 deopt 与回调成本，采样式（如 py-spy 用 process_vm_readv 读栈）几乎不侵入但只能给统计近似；灰度环境里应当先固定过滤前缀与采样间隔，再决定要不要开全量事件。

**两代事件机制的结构性差异**

| 维度 | sys.setprofile | sys.monitoring | 差异根源 |
| --- | --- | --- | --- |
| 回调参数 | 完整 frame 对象 | code 与指令偏移 | 是否物化 PyFrameObject |
| 检查位置 | CALL 分派前后插入 | 指令流就地检查 | 分派成本不同 |
| 与 specializing | 关闭热路径特化 | 一次性 deopt | ADAPTIVE 指令需回退 |
| 工具冲突 | 每线程仅一个回调 | 事件位独占 | 槽位仲裁会抛 ValueError |
| 可用版本 | 历代都有 | 3.12 起（PEP 669） | 解释器改造范围 |


### 生成器 resume 让 call/return 重复计数的调用树失真

灰度报告里出现一个怪现象：某个只定义了一次、也只被 `list()` 消费一次的生成器，在调用树里被记成四次调用，自耗时累加到父帧后明显虚高。

根因是 `sys.setprofile` 的粒度：生成器每次被 next 或 send 恢复执行，解释器都按一次 call 分派处理，yield 时再按一次 return 分派，所以 3 个 yield 加最后一次 StopIteration 一共产生 4 组 call/return。

按 call 压栈、return 弹栈重建调用树的实现，会把这 4 组当成 4 次独立调用，把同一帧的自耗时重复计入。

修复不是丢弃这些事件，而是在栈帧记录里带上 `frame.f_code` 与 frame 身份，把同一个生成器对象的多次 resume 合并到一个节点，并把 yield 期间的挂起时间从 self time 里剔除；事件本身没有错，是调用树的建模假设（一次 call 对应一次完整执行）对生成器不成立。

下面这段代码把事件逐条抓下来，打印 gen 的 call 与 return 次数：都是 4，而不是直觉里的 1。同样的坑也出现在协程 await 与 async generator 上，凡是有暂停点的函数，都必须按帧的生命周期而不是事件对来聚合。

```python
import sys

events = []
def cb(frame, event, arg):
    if event in ('call', 'return'):
        events.append((event, frame.f_code.co_name))
    return cb

def gen(n):
    for i in range(n):
        yield i

sys.setprofile(cb)
g = gen(3)
list(g)
sys.setprofile(None)
calls = [e for e in events if e[0] == 'call' and e[1] == 'gen']
returns = [e for e in events if e[0] == 'return' and e[1] == 'gen']
print('gen call events', len(calls))
print('gen return events', len(returns))
print('more calls than definition', len(calls) > 1)

```

<Quiz no='059-X' q='在 3.13 上用 sys.setprofile 采集一个含 3 个 yield 的生成器，list() 消费完毕后，关于该生成器函数的 call 事件数量，哪项正确？' :options='["1 次，整个生成器只在首次 next 时触发一次 call", "3 次，与 yield 出的元素个数相同", "4 次，每次 resume 都按一次 call 分派，含最后触发 StopIteration 的那次", "0 次，生成器恢复走的是专用字节码，不触发 profile 事件"]' answer="2" explain='3.11 起生成器每次被 next / send 恢复都走一次 call 分派，yield 与最终 return 各走一次 return 分派；3 个 yield 加最后一次耗尽共 4 组 call/return。这正是按事件对建调用树会把生成器 self time 重复累加的原因。选项 A 把帧的生命周期与事件次数混淆，B 漏了耗尽那一次，D 也不成立：生成器恢复仍经过 profile 钩子，只是 3.12 起有 SEND 等专用指令，事件照常触发。' />


## 练习、自测与速记

<Exercise title='基础：用 setprofile 统计某个函数的调用次数' task='装一个回调，只统计名字以 calc 开头的函数的 call 事件，跑三个 calc_a/calc_b/other，打印计数；说明为何回调里不能再用 print。' solution='import sys\ncount = [0]\ndef cb(frame, event, arg):\n    if event == &#39;call&#39; and frame.f_code.co_name.startswith(&#39;calc&#39;):\n        count[0] += 1\n    return cb\ndef calc_a(): return 1\ndef calc_b(): return calc_a()\ndef other(): return 2\nsys.setprofile(cb)\ncalc_a(); calc_b(); other()\nsys.setprofile(None)\nprint(&#39;calc calls&#39;, count[0])' explain='calc_a 一次、calc_b 一次、calc_b 内再调 calc_a 一次，共 3 次。回调里若用 print 会触发新的 call 事件并可能递归，累加宜用列表或计数器这类最小操作。' />

<Exercise title='进阶：量化 profile 回调带来的开销' task='对含 3 万次小函数调用的热点，分别在无钩子与 nop 回调下各跑三轮取 min，打印比值大于 1；解释为什么函数越小开销比越大。' solution='import sys, time\ndef add(a, b): return a + b\ndef busy():\n    t = 0\n    for i in range(30000): t = add(t, i)\n    return t\ndef run():\n    s = time.perf_counter(); busy(); return time.perf_counter() - s\na = min(run() for _ in range(3))\nsys.setprofile(lambda f, e, arg: None)\nb = min(run() for _ in range(3))\nsys.setprofile(None)\nprint(&#39;ratio &gt; 1&#39;, b / a &gt; 1.0)' explain='每次 call/return 都要穿过 Python 回调并构造参数元组；当函数体极短时，事件开销在总耗时里占比最高，比值明显大于 1。这正是生产要采样与过滤的原因。' />

<Quiz no='059-1' q='在多线程程序里直接用 sys.setprofile 收集调用树，最可能出什么问题？' :options='["事件来自多个线程的 profile 状态，混进同一棵树，父子关系错乱", "自动抛 RuntimeError", "只能采到主线程，其它线程完全没数据", "结果比 cProfile 更精确"]' answer="0" explain='setprofile 是每线程状态，threading.setprofile 会把钩子传播给新建线程；全局回调会收到多线性事件，必须按 threading.get_ident() 分桶重建各线程独立的栈。' />

<Quiz no='059-2' q='用 tracemalloc 做泄漏告警，按什么量设阈值最不容易误报？' :options='["快照 compare_to 的 size_diff 净增量，并要求连续多个窗口持续增长", "get_traced_memory() 的 current 绝对值", "进程 RSS", "peak 一次性峰值"]' answer="0" explain='绝对值会被缓存预热与一次性大对象抬高；增量趋近于零才是稳态。连续 K 窗确认能过滤偶发分配，nframe 取 1-3 控制开销。' />

<Quiz no='059-3' q='关于 3.12+ sys.monitoring，正确的是？' :options='["按工具 ID 订阅事件位、不构造 frame 对象，开销低于 setprofile", "它是 setprofile 的别名", "同一事件位可被多个工具同时订阅", "只能用于单线程程序"]' answer="0" explain='PEP 669 把事件检查内联进指令分派，回调参数精简；工具 ID 与事件位是独占资源，冲突时 set_events 抛 ValueError，常用 ID 0-5。' />

<Predict no='059-P' q='用 setprofile 建调用树，top 调用 middle 一次、middle 调用 leaf 两次，统计里 leaf 的调用次数是多少？' :options='["2", "1", "4"]' answer='0' output='2' explain='每次进入 leaf 都触发一个 call 事件并压栈，middle 里显式调用了 leaf 两次，因此 stats[&#39;leaf&#39;][0] 为 2；cumtime 与 self 的差额则来自子调用时间。' />

<FillBlank no='059-F' tpl='___ sys' :answers='["import"]' hint='回想本讲关于 sys.setprofile 采集 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 sys.setprofile 事件与调用树重建 的落点。' />

<KnowledgeCard :points='["sys.setprofile 回调是 (frame, event, arg)，call/return 建栈；self = dt - 子耗时，cumtime = dt", "setprofile 是每线程状态，多线程必须按 threading.get_ident() 分桶，否则调用树串线", "tracemalloc 用 compare_to 的 size_diff 净增量告警，比 current 绝对值少误报；nframe 取 1-3 控开销", "分析器自身有侵入性：回调里只做压栈与累加，日志在 setprofile(None) 之后输出，并用比值量化开销", "3.12+ sys.monitoring (PEP 669) 用 use_tool_id / set_events / register_callback，事件位独占、不构造 frame", "工具要提供函数名过滤、采样间隔与上下文开关，保证灰度可开、异常路径也能卸载钩子"]' :pitfalls='["多线程里用全局 setprofile，调用树对不上", "按 get_traced_memory() 的绝对值设内存告警，天天误报", "在 profile 回调里做日志、格式化或加锁", "在多线程程序里用全局 profile 回调，会把别的线程事件也算进当前调用树"]' summary='分析器本身也在消耗 CPU，采样精度与侵入性是一对必须显式 trade-off 的参数' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| sys.setprofile 回调是 (frame, event, arg)，call/return 建栈；self = dt - 子耗时，cumtime = dt | 建立直觉 |
| setprofile 是每线程状态，多线程必须按 threading.get_ident() 分桶，否则调用树串线 | 跑通示例 |
| tracemalloc 用 compare_to 的 size_diff 净增量告警，比 current 绝对值少误报；nframe 取 1-3 控开销 | 深入边界 |
| 分析器自身有侵入性：回调里只做压栈与累加，日志在 setprofile(None) 之后输出，并用比值量化开销 | 工程落地 |
| 3.12+ sys.monitoring (PEP 669) 用 use_tool_id / set_events / register_callback，事件位独占、不构造 frame | 随堂检测 |
| 工具要提供函数名过滤、采样间隔与上下文开关，保证灰度可开、异常路径也能卸载钩子 | 复盘 |

1. sys.setprofile 回调是 (frame, event, arg)，call/return 建栈；self = dt - 子耗时，cumtime = dt

2. setprofile 是每线程状态，多线程必须按 threading.get_ident() 分桶，否则调用树串线

3. tracemalloc 用 compare_to 的 size_diff 净增量告警，比 current 绝对值少误报；nframe 取 1-3 控开销

[下一讲：并发、并行与 IO 模型全景](/concurrency/concurrency-intro)
