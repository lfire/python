---
title: 第 058 讲 · 性能剖析：timeit、cProfile 与 tracemalloc
description: 用数据而不是直觉做优化
---

<StageHeader stage='L5 · 核心机制' level='★★★☆☆' time='40 分钟' goal='用数据而不是直觉做优化' prereq='第 057 讲 · 可变性、深浅拷贝与共享状态' />

# 第 058 讲 · 性能剖析：timeit、cProfile 与 tracemalloc

状态从哪来、归谁、怎么复制都摸清了，接下来常有人急着把循环换种写法、把结构换个实现，好让程序快一点。但仍在单线程里，动手之前更该先拿数据代替直觉。凭一次计时下结论很容易翻车：缓存预热、磁盘预读和输入规模一变，原本「快了一截」的改法换台机器就反了过来。

本讲按测量的颗粒度往前走：先用 `timeit` 隔离解释器启动与预热，再用 `cProfile` 把耗时拆到函数级，接着用 `tracemalloc` 做快照对比看内存，最后谈基准怎样才可复现。需要你会写函数与循环、理解基本的时间与内存概念；学完能用数据判断该换算法、换数据结构还是换实现层，而不是拍脑袋优化。


## 把列表推导当成热点，只快了 3%

一个批处理脚本变慢，开发者凭「感觉」把最显眼的 for 循环改成列表推导，压测后只快了 3%，而真正吃掉 70% 时间的是一个每次迭代都做 `json.loads` 的小函数。

另一处，团队用 `time.perf_counter` 包住一段含 `time.sleep` 的逻辑，得出「CPU 很重、要上多进程」的结论，实际那段几乎全在等网络。

还有人把微基准写在 `REPL` 里跑一次就下结论，结果被缓存预热、GC 与哈希随机化搅得忽快忽慢。三件事的共同错误是：把直觉当数据，把墙钟时间当 CPU 时间，把一次运行当基准。优化的第一步永远是把耗时拆到函数级，再决定换算法、换数据结构还是换实现层；

而要做到这一点，得先弄清 timeit 怎么隔离噪声、cProfile 的 `tottime` 与 `cumtime` 各代表什么、`tracemalloc` 的快照差值能证明什么，以及 3.12 起 `sys.monitoring` 为何能把采样开销降下来。

<Callout type="warn" title='先看一个真实会出错的写法' text='用 perf_counter 量含 sleep 的逻辑，得出「该上多进程」：墙钟把等待时间也算进去，误判成 CPU 密集' />


## 测量先定口径：墙钟、CPU 时间与 timeit

`time.perf_counter()` 是单调、最高分辨率的墙钟，包含 sleep 与等待 IO；

`time.process_time()` 只累计当前进程的 CPU 时间，不含睡眠；

3.7+ 另有 `perf_counter_ns` 与 `process_time_ns` 返回整数纳秒，避免浮点误差。

判断任务类型要看两者之差：`wall` 减去 `cpu` 近似等待时长，占比高就是 IO 密集。

`timeit.timeit` 默认 `number=1000000`，`timeit.repeat` 默认 `repeat=5`，`Timer.autorange()` 会自动挑一个 number，使单次总时长不小于 0.2 秒。

微基准要守四条：取 `min(samples)` 而不是均值（最小值受偶发调度干扰最小）、把 import 与数据构造放进 setup、用 `-S` 或同进程内预热排除解释器启动、必要时 `gc.disable()` 并固定 `PYTHONHASHSEED`。

timeit 内部把 stmt 编译成函数循环执行，所以多行语句要正确缩进，且它默认关闭 GC，每轮结束后再恢复。

**计时函数口径对照**

| 函数 / 版本 | 计量内容 | 是否含 sleep | 典型用途 |
| --- | --- | --- | --- |
| time.perf_counter() | 单调墙钟，最高分辨率 | 含 | 端到端耗时、延迟百分位 |
| time.process_time() | 当前进程 CPU 时间 | 不含 | 区分 CPU 密集与等待密集 |
| time.perf_counter_ns() 3.7+ | 同上，整数纳秒 | 含 | 避免浮点累计误差 |
| timeit.repeat(...) | 固定 number 下多轮总耗时 | 含 | 微基准，取 min(samples) |

<Callout type="tip" title='核心心智模型' text='`time.perf_counter()` 是单调、最高分辨率的墙钟，包含 sleep 与等待 IO；`time.process_time()` 只累计当前进程的 CPU 时间，不含睡眠；3.7+ 另有 `perf_counter_ns` 与 `process_time_ns` 返回整数纳秒，避免浮…' />

<ConceptDiagram type='hub4' title='第 058 讲 · 计时口径：墙钟、CPU 时间与 timeit 的正确姿势' labels='计时口径：墙钟、CPU 时间与 timeit…|cProfile / pstats：把耗时拆…|tracemalloc 快照与可复现基准|基准的可复现性' caption='用数据而不是直觉做优化' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 微基准：正确姿势与被带偏的对照

```python
import time
import timeit

def mixed():
    time.sleep(0.05)
    return sum(range(1000))

t0 = time.perf_counter()
c0 = time.process_time()
mixed()
wall = time.perf_counter() - t0
cpu = time.process_time() - c0
print('wall > cpu', wall > cpu)
print('sleep dominates', wall - cpu > cpu)
samples = timeit.repeat('sum(range(1000))', number=500, repeat=5)
print('rounds', len(samples), 'min_le_mean', min(samples) <= sum(samples) / len(samples))
```

<OutputBox title='主示例运行结果' output='wall &gt; cpu True\nsleep dominates True\nrounds 5 min_le_mean True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import time\nimport timeit\n\ndef mixed():\n    time.sleep(0.05)\n    return sum(range(1000))\n\nt0 = time.perf_counter()\nc0 = time.process_time()\nmixed()\nwall = time.perf_counter() - t0\ncpu = time.process_time() - c0\nprint(&#39;wall &gt; cpu&#39;, wall &gt; cpu)\nprint(&#39;sleep dominates&#39;, wall - cpu &gt; cpu)\nsamples = timeit.repeat(&#39;sum(range(1000))&#39;, number=500, repeat=5)\nprint(&#39;rounds&#39;, len(samples), &#39;min_le_mean&#39;, min(samples) &lt;= sum(samples) / len(samples))' :notes='["导入 time，使用 perf_counter 与 process_time 两种口径", "导入 timeit 做可重复微基准", "空行，只用于分隔逻辑块，不影响执行结果。", "构造一个含休眠与少量计算的函数", "time.sleep 会释放 GIL 但不消耗 CPU 时间", "少量计算用于体现 CPU 时间不为零", "空行，只用于分隔逻辑块，不影响执行结果。", "记录墙钟起点", "记录 CPU 时间起点", "执行被测函数", "墙钟增量包含全部休眠等待", "CPU 增量只含真正占用处理器的时间", "墙钟必然大于 CPU 时间", "差值远大于 CPU 时间，判定为 IO/等待主导", "timeit.repeat 返回 5 轮各自的总耗时", "校验轮数，并用 min &lt;= mean 说明取最小值的意义"]' title='第 058 讲 · 性能剖析：timeit、cProfile 与 tracemalloc' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import cProfile
import pstats
import io

def hot(n):
    return sum(i * i for i in range(n))

def driver():
    return hot(5000) + hot(5000)

pr = cProfile.Profile()
pr.enable()
driver()
pr.disable()
buf = io.StringIO()
st = pstats.Stats(pr, stream=buf)
st.strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE)
st.print_stats()
text = buf.getvalue()
print('driver tracked', 'driver' in text)
print('hot tracked', 'hot' in text)
print('genexpr tracked', 'genexpr' in text)
print('total_calls_positive', st.total_calls > 0)
print('sort key', pstats.SortKey.CUMULATIVE.value)
```

<OutputBox title='对照写法：先自己猜，再点开' output='driver tracked True\nhot tracked True\ngenexpr tracked True\ntotal_calls_positive True\nsort key cumulative' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import time\nimport timeit\n\ndef mixed():\n    time.sleep(0.05)\n    return sum(range(1000))\n\nt0 = time.perf_counter()\nc0 = time.process_time()\nmixed()\nwall = time.perf_counter() - t0\ncpu = time.process_time() - c0\nprint(&#39;wall &gt; cpu&#39;, wall &gt; cpu)\nprint(&#39;sleep dominates&#39;, wall - cpu &gt; cpu)\nsamples = timeit.repeat(&#39;sum(range(1000))&#39;, number=500, repeat=5)\nprint(&#39;rounds&#39;, len(samples), &#39;min_le_mean&#39;, min(samples) &lt;= sum(samples) / len(samples))", "note": "计时口径：墙钟、CPU 时间与 timeit 的正确姿势"}, {"label": "对照 / 进阶", "code": "import cProfile\nimport pstats\nimport io\n\ndef hot(n):\n    return sum(i * i for i in range(n))\n\ndef driver():\n    return hot(5000) + hot(5000)\n\npr = cProfile.Profile()\npr.enable()\ndriver()\npr.disable()\nbuf = io.StringIO()\nst = pstats.Stats(pr, stream=buf)\nst.strip_dirs().sort_stats(pstats.SortKey.CUMULATIVE)\nst.print_stats()\ntext = buf.getvalue()\nprint(&#39;driver tracked&#39;, &#39;driver&#39; in text)\nprint(&#39;hot tracked&#39;, &#39;hot&#39; in text)\nprint(&#39;genexpr tracked&#39;, &#39;genexpr&#39; in text)\nprint(&#39;total_calls_positive&#39;, st.total_calls &gt; 0)\nprint(&#39;sort key&#39;, pstats.SortKey.CUMULATIVE.value)", "note": "cProfile / pstats：把耗时拆到函数级"}]' title='两种写法对照' note='差异集中在 测量优先于猜测；先看输出，再找背后的规则。' />

```python
import tracemalloc

def build(n):
    return [dict(i=i, sq=i * i) for i in range(n)]

tracemalloc.start(1)
snap0 = tracemalloc.take_snapshot()
cache = build(2000)
snap1 = tracemalloc.take_snapshot()
current, peak = tracemalloc.get_traced_memory()
print('peak >= current', peak >= current)
diff = snap1.compare_to(snap0, 'lineno')
print('diff rows > 0', len(diff) > 0)
print('top size_diff >= 0', diff[0].size_diff >= 0)
print('traced bytes > 0', current > 0)
tracemalloc.stop()
```

<OutputBox title='原理验证' output='peak &gt;= current True\ndiff rows &gt; 0 True\ntop size_diff &gt;= 0 True\ntraced bytes &gt; 0 True' />


## cProfile 把耗时拆到函数级

`cProfile.Profile()` 是 C 扩展实现的确定性 profiler，通过 `sys.setprofile` 接收每个 Python 函数的 call/return 事件，开销远低于纯 Python 的 `profile` 模块。

常用 `pr.enable()` 跑代码再用 `pr.disable()` 收尾，或直接 `cProfile.run` 把结果写文件。

`pstats.Stats` 的列含义必须分清：`ncalls` 是调用次数（含 3/2 形式的递归标记），`tottime` 是本函数自身消耗、不含子调用，`cumtime` 是含所有子调用的累计，`percall` 为二者之商，最后一列是 `filename:lineno(function)`。

排序用 `sort_stats(pstats.SortKey.CUMULATIVE)`，也可以写字符串 'cumtime'、'tottime'、'calls'；

3.7+ 推荐 `SortKey` 枚举。cProfile 看不到 C 函数内部，也不区分行级耗时——`line_profiler`（第三方，`kernprof -l -v`）按行统计但侵入更大。确定性 profiler 本身会扭曲结果：函数越多、调用越碎，附加事件越多，所以结论要看相对占比而非绝对毫秒数。

**cProfile / pstats 列与排序键**

| 项 | 含义 | 误读后果 |
| --- | --- | --- |
| ncalls | 调用次数，递归显示为 3/2 形式 | 把递归标记当两次独立调用 |
| tottime | 函数自身耗时，不含子调用 | 以为它等于整个请求的耗时 |
| cumtime | 含所有子调用的累计耗时 | 与 tottime 混淆会找错热点 |
| SortKey.CUMULATIVE (3.7+) | 按累计耗时排序，值为 cumulative | 按 tottime 排会漏掉包装层 |
| pstats.Stats.print_stats(10) | 只打印前 10 行 | 不看 strip_dirs 会让路径刷屏 |

<Term word='测量优先于猜测' text='`time.perf_counter()` 是单调、最高分辨率的墙钟，包含 sleep 与等待 IO；`time.process_time()` 只累计当前进程的 CPU 时间，不含睡眠；3.7+ 另有 `perf_counter_ns` 与 `process_time_ns` 返回整数纳秒，避免浮点误差。判断任务类型…' />

<Term word='timeit 的正确姿势' text='`cProfile.Profile()` 是 C 扩展实现的确定性 profiler，通过 `sys.setprofile` 接收每个 Python 函数的 call/return 事件，开销远低于纯 Python 的 `profile` 模块。常用 `pr.enable()` 跑代码再用 `pr.disable()`…' />


## tracemalloc 快照差值与可复现基线

`tracemalloc.start(nframe=1)` 在 Python 对象分配器（pymalloc）层挂钩，记录每块分配的回溯；

`take_snapshot()` 生成快照，`statistics('lineno')` 一类调用按维度聚合，`compare_to(other, 'lineno')` 返回 `StatisticDiff` 列表，含 `size_diff` 与 `count_diff`，是定位「哪一行多分配了内存」的直接证据。

`get_traced_memory()` 返回 (current, peak) 字节数，`reset_peak()`（3.9+）可重置峰值，`stop()` 关闭追踪。

它只统计 Python 层分配，NumPy 的 C 缓冲区不计入，且开启后内存与 CPU 有明显开销，适合测试环境或短时灰度。基准要可复现：同一台机器、同一组输入、同一解释器版本、关闭后台负载、把关键基准写进 CI 并设回归阈值。

3.12 起 `sys.monitoring`（PEP 669）提供按工具 ID 注册回调的低开销事件（`PY_START` / `PY_RETURN` 等），可替代 setprofile 做采样，且不需要构造 frame 对象；3.13 沿用并扩展。优化前后必须保留同一组数据与同一测量脚本，否则数字不可比。

**剖析工具能力与开销**

| 工具 | 统计粒度 | 主要开销 | 版本/依赖 |
| --- | --- | --- | --- |
| cProfile | 函数级确定性事件 | 每次 call/return 一个回调 | 标准库 |
| profile | 函数级，纯 Python | 比 cProfile 高一个量级 | 标准库 |
| line_profiler | 行级 | 逐行计时，侵入大 | 第三方，kernprof -l -v |
| tracemalloc 3.4+ | 分配点与字节数 | 挂钩 pymalloc，内存/CPU 明显 | 标准库，reset_peak 3.9+ |
| sys.monitoring 3.12+ (PEP 669) | 按工具 ID 的低开销事件 | 无需构造 frame | 标准库，替代 setprofile 采样 |


## 剖析钩子底层：setprofile 与 sys.monitoring

cProfile 基于 CPython 的 `PyEval_SetProfile` 钩子：解释器在每次进入或离开 Python 函数、以及调用 C 函数时发出事件，C 层把它们累计进一张以 code object 为键的表，因此它统计的是「事件次数加两次事件间的墙钟」，而不是采样。

`tottime` 只把当前帧两次事件之间的时间记到自己名下，子调用的时间单独记入子帧，`cumtime` 则是当前帧及其所有后代之和——这也是为什么包装函数 `tottime` 很小、`cumtime` 却很大。`profile` 纯 Python 版对每个事件都走 Python 回调，开销高得多。

tracemalloc 在 `_PyObject_Malloc` / `_PyObject_Free` 层插入钩子，把分配大小与回溯栈存进哈希表，`take_snapshot` 只是把当前表按维度聚合，`compare_to` 对两次聚合做差，故 `size_diff` 直接对应「这一行多分配了多少字节」。

`sys.monitoring` 让工具用 `use_tool_id` 注册回调并只订阅需要的事件位，解释器在指令流里就地检查，无需为每个事件构造 frame 对象，开销比 setprofile 低一个量级；3.11 的自适应特化解释器、3.13 的 JIT 骨架也会改变字节码执行时间，因此跨版本的性能数字必须重测。


## 给批处理加一条可回归的性能基线

一个 ETL 脚本每次上线都被抱怨变慢，但没人说得清慢在哪。工程做法是写一段独立基准：用同一份固定输入，先分别测总墙钟与 CPU 时间判明负载类型，再用 cProfile 把耗时拆到函数级、按 `cumtime` 排序打印前几名，最后用 tracemalloc 的 `compare_to` 看新版本有没有引入额外分配。

脚本把三项结果打印成结构化文本随代码提交，CI 里设 `tottime` 与峰值内存的回归阈值；超阈值就失败，而不是靠人凭感觉评审。这样优化前后用的是同一组数据与同一测量脚本，数字才可比；也避免把缓存预热或某次 GC 抖动当成趋势。

```python
import cProfile
import io
import pstats
import time
import tracemalloc

def parse(rows):
    return [r.strip().split(',') for r in rows]

def aggregate(rows):
    total = 0
    for parts in parse(rows):
        total += len(parts)
    return total

ROWS = ['a,b,c', 'd,e', 'f,g,h,i'] * 4000

if __name__ == '__main__':
    t0 = time.perf_counter()
    c0 = time.process_time()
    result = aggregate(ROWS)
    print('result', result, 'wall', round(time.perf_counter() - t0, 4),
          'cpu', round(time.process_time() - c0, 4))
    pr = cProfile.Profile()
    pr.enable()
    aggregate(ROWS)
    pr.disable()
    buf = io.StringIO()
    pstats.Stats(pr, stream=buf).sort_stats('cumulative').print_stats(3)
    print('top funcs', [ln.strip().split()[-1] for ln in buf.getvalue().splitlines()
                      if 'function calls' not in ln and ln.strip()][-3:])
    tracemalloc.start()
    s0 = tracemalloc.take_snapshot()
    aggregate(ROWS)
    s1 = tracemalloc.take_snapshot()
    print('alloc rows', len(s1.compare_to(s0, 'lineno')) > 0)
    tracemalloc.stop()
```

<Callout type="idea" title='落地提示' text='把关键基准写进 CI 并设回归阈值；优化前后保留同一组数据与同一台机器' />

<CheckList id='P058b' title='上线前自检' :items='["能复现并解释「用 perf_counter 量含 sleep 的逻辑，得出…」", "能复现并解释「微基准只跑一次、且把数据构造写在被测语句里」", "能复现并解释「看 cProfile 的 tottime 找热点，结果优化了…」", "能用一条命令验证 测量优先于猜测", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 perf_counter 量含 sleep 的逻辑，得出「该上多进程」 | 墙钟把等待时间也算进去，误判成 CPU 密集 | 同时测 process_time，用 wall - cpu 估等待占比；IO 主导用线程池或 asyncio |
| 微基准只跑一次、且把数据构造写在被测语句里 | 缓存预热、GC、哈希随机化与构造开销混进结果，数字不可复现 | 用 timeit.repeat 取 min，数据放 setup，固定 PYTHONHASHSEED，必要时 gc.disable() |
| 看 cProfile 的 tottime 找热点，结果优化了只占 3% 的函数 | tottime 不含子调用，真正的耗时常集中在被调用的下层或被 cumtime 掩盖 | 先按 SortKey.CUMULATIVE 排序定位调用树，再对具体函数看 tottime 与 ncalls |

<Callout type="warn" title='本讲最容易踩的坑' text='用 perf_counter 量含 sleep 的逻辑，得出「该上多进程」：墙钟把等待时间也算进去，误判成 CPU 密集' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 perf_counter 量含 slee…", "body": "墙钟把等待时间也算进去，误判成 CPU 密集", "tip": "同时测 process_time，用 wall - cpu 估等待占比；IO 主导用线程池或 asyncio"}, {"title": "第 2 步：微基准只跑一次、且把数据构造写在被测语句里", "body": "缓存预热、GC、哈希随机化与构造开销混进结果，数字不可复现", "tip": "用 timeit.repeat 取 min，数据放 setup，固定 PYTHONHASHSEED，必要时 gc.disable()"}, {"title": "第 3 步：看 cProfile 的 tottime 找…", "body": "tottime 不含子调用，真正的耗时常集中在被调用的下层或被 cumtime 掩盖", "tip": "先按 SortKey.CUMULATIVE 排序定位调用树，再对具体函数看 tottime 与 ncalls"}]' />


## 练习、自测与速记

<Exercise title='基础：用两种时钟判定负载类型' task='写一个函数先 sleep 0.03 再做 10 万次整数加法，分别打印 wall 与 cpu，以及 wall-cpu 是否大于 cpu；说明为什么前者大就说明是等待主导。' solution='import time\ndef task():\n    time.sleep(0.03)\n    return sum(range(100000))\nt0 = time.perf_counter(); c0 = time.process_time()\ntask()\nwall = time.perf_counter() - t0\ncpu = time.process_time() - c0\nprint(&#39;wall&#39;, round(wall, 4), &#39;cpu&#39;, round(cpu, 4), &#39;waiting&#39;, wall - cpu &gt; cpu)' explain='perf_counter 含 sleep，process_time 只累计 CPU；wall 明显大于 cpu 且差值显著时，说明时间主要花在等待而非计算，应优先排查 IO 与锁。' />

<Exercise title='进阶：用 cProfile 与 pstats 找出真正的热点' task='构造 outer() 调用两次 inner()，inner() 里跑一个生成器求和；用 cProfile 采集并按 cumtime 排序打印，解释为何 outer 的 cumtime 远大于 tottime。' solution='import cProfile, pstats, io\ndef inner(n):\n    return sum(i * i for i in range(n))\ndef outer():\n    return inner(20000) + inner(20000)\npr = cProfile.Profile()\npr.enable(); outer(); pr.disable()\nbuf = io.StringIO()\npstats.Stats(pr, stream=buf).sort_stats(&#39;cumulative&#39;).print_stats()\nprint([ln for ln in buf.getvalue().splitlines() if &#39;outer&#39; in ln or &#39;inner&#39; in ln][:3])' explain='outer 自身几乎不做计算，tottime 接近 0，但 cumtime 含两次 inner 与生成器耗时，因此按累计排序时排在前面；优化要落到 inner 或数据结构上。' />

<Quiz no='058-1' q='某函数 wall=0.52s、cpu=0.04s，最合理的判断是？' :options='["等待主导，约 0.48s 花在 IO/锁/休眠，应查线程池与异步", "CPU 密集，应上多进程", "解释器启动太慢", "GC 占了大头"]' answer="0" explain='wall - cpu 近似等待时间；0.48s 远大于 0.04s 说明几乎不在算，加进程只会浪费内存，应排查阻塞调用与锁竞争。' />

<Quiz no='058-2' q='关于 cProfile 的 tottime 与 cumtime，正确的是？' :options='["tottime 不含子调用，cumtime 含所有后代；找热点先按 cumtime 排", "tottime 含子调用，cumtime 不含", "两者恒等", "cumtime 只对递归函数有意义"]' answer="0" explain='tottime 是当前帧两次事件之间的自身耗时；cumtime 累加当前帧及所有子调用。包装函数常 tottime 极小、cumtime 很大，只按 tottime 会找错地方。' />

<Quiz no='058-3' q='关于 tracemalloc，下列哪项准确？' :options='["它在 pymalloc 层挂钩，compare_to 的 size_diff 能定位哪行多分配", "它统计包括 NumPy C 缓冲区在内的全部进程内存", "开启后几乎没有开销，可常驻生产", "它按函数计时，可替代 cProfile"]' answer="0" explain='tracemalloc 只追踪 Python 层分配，NumPy 的 C 缓冲区不计入；开启有明显内存/CPU 开销。它是内存工具，不是计时工具，不能替代 cProfile。' />

<Predict no='058-4' q='timeit.repeat(&#39;pass&#39;, number=100, repeat=7) 返回的列表长度是多少，且 min(samples) 与均值关系如何？' :options='["长度 7，且 min &lt;= mean", "长度 100，且 min &gt; mean", "长度 1，返回总秒数", "长度 7，且每项都相等"]' answer='0' output='7 个元素，min(samples) &lt;= sum(samples)/7' explain='repeat 的 repeat 参数决定轮数，每轮是 number 次执行的总耗时；最小值不大于算术平均是恒等性质，微基准取 min 正是为压低偶发调度噪声。' />

<FillBlank no='058-5' tpl='___ time' :answers='["import"]' hint='回想本讲关于 测量优先于猜测 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 计时口径：墙钟、CPU 时间与 timeit 的正确姿势 的落点。' />

<KnowledgeCard :points='["perf_counter 含等待，process_time 只算 CPU；wall 减 cpu 的占比决定线程/进程/异步的选型", "timeit.repeat 默认 repeat=5、number=1000000；微基准取 min，构造放 setup，固定 PYTHONHASHSEED 并预热", "cProfile 是 setprofile 之上的 C 实现；tottime 不含子调用、cumtime 含全部后代，按 SortKey.CUMULATIVE 定位热点", "tracemalloc 在 pymalloc 层挂钩，compare_to 的 size_diff 定位多分配的行；不含 C 扩展缓冲区", "3.12+ sys.monitoring (PEP 669) 按工具 ID 注册低开销事件，替代 setprofile 采样；3.13 有实验性 JIT 骨架", "基准要同机器、同输入、同版本、写进 CI 设回归阈值；只跑一次或凭直觉优化几乎一定优化错地方"]' :pitfalls='["用 perf_counter 量含 sleep 的逻辑，得出「该上多进程」", "微基准只跑一次、且把数据构造写在被测语句里", "看 cProfile 的 tottime 找热点，结果优化了只占 3% 的函数", "缓存命中、JIT、磁盘预读都会让单次计时失真，凭一次运行下结论常常优化错地方"]' summary='优化的第一步是把耗时拆到函数级，再决定是否换算法、换数据结构或换实现层；微基准必须隔离解释器启动与缓存预热' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| perf_counter 含等待，process_time 只算 CPU；wall 减 cpu 的占比决定线程/进程/异步的选型 | 建立直觉 |
| timeit.repeat 默认 repeat=5、number=1000000；微基准取 min，构造放 setup，固定 PYTHONHASHSEED 并预热 | 跑通示例 |
| cProfile 是 setprofile 之上的 C 实现；tottime 不含子调用、cumtime 含全部后代，按 SortKey.CUMULATIVE 定位热点 | 深入边界 |
| tracemalloc 在 pymalloc 层挂钩，compare_to 的 size_diff 定位多分配的行；不含 C 扩展缓冲区 | 工程落地 |
| 3.12+ sys.monitoring (PEP 669) 按工具 ID 注册低开销事件，替代 setprofile 采样；3.13 有实验性 JIT 骨架 | 随堂检测 |
| 基准要同机器、同输入、同版本、写进 CI 设回归阈值；只跑一次或凭直觉优化几乎一定优化错地方 | 复盘 |

1. perf_counter 含等待，process_time 只算 CPU；wall 减 cpu 的占比决定线程/进程/异步的选型

2. timeit.repeat 默认 repeat=5、number=1000000；微基准取 min，构造放 setup，固定 PYTHONHASHSEED 并预热

3. cProfile 是 setprofile 之上的 C 实现；tottime 不含子调用、cumtime 含全部后代，按 SortKey.CUMULATIVE 定位热点

[下一讲：阶段综合：简易性能分析器与内存哨兵](/core/capstone)

```bash
python -c "import cProfile; cProfile.run('sum(range(100000))', sort='cumtime')"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 测量优先于猜测 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/058-profiling.py`

```bash
python3 examples/lessons/058-profiling.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/058-profiling.py) · [全部示例代码索引](/examples/)
