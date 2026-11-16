---
title: 第 119 讲 · 极致优化：从剖析到 C 扩展的十倍案例
description: 按层次系统性地压低延迟
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='55 分钟' goal='按层次系统性地压低延迟' prereq='第 118 讲 · GIL 源码、自适应解释器与无 GIL 路线' />

# 第 119 讲 · 极致优化：从剖析到 C 扩展的十倍案例

从跨服务的一致性一路沉到解释器实现，最后把这些理解收在一个很实在的问题上：接口慢了，该先动哪一层。凭感觉把循环换个写法、甚至一上来就用 C 重写热点，常常费了可维护性却没快多少——瓶颈根本不在那里。优化有顺序，也该有个停下来的理由。

本讲先用 cProfile、timeit 和 Amdahl 定律算清「哪段值得改」，再按先算法后实现、数据结构与批处理的顺序拿到数量级收益，然后才谈向量化与 NumPy、Cython 与 C 扩展，最后说清何时该停。需要复杂度、剖析工具与前面源码的底子；读完后你能做一次极致优化并留下基准与回归测试，用数据决定收工。


## 一上来用 Cython 重写热点，收益却几乎为零

一个报表接口的 p99 延迟 1.2 秒，团队第一反应是用 Cython 重写热点函数，折腾两周把一段解析循环改成 C 扩展，结果上线只快了 8%——profiling 一开才发现真正瓶颈是一次多余的数据库往返与一个 `O(n^2)` 的成员检测，网络与算法占了大头。

另一次优化把循环里的字符串拼接改成 `join` 后确实快了，却没人留下基准与回归测试，几个月后有人重构又把写法改回去，性能悄悄退化，没有任何测试拦住。优化有明确顺序：换算法通常带来数量级收益，改语法只带来常数收益；把不可读的优化隔离在小函数并写清原因。

本讲按层次系统性地压低延迟，从剖析、算法、数据结构、批处理、向量化到 C 扩展与并行，用数据决定何时停止。

<Callout type="warn" title='先看一个真实会出错的写法' text='一上来用 Cython 重写热点函数：若瓶颈其实是数据库往返或 O(n^2) 算法，被优化部分占比很低，Amdahl 定律下整体收益极小' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段十一 · 资深进阶与源码 |
| 前置 | 第 118 讲 · GIL 源码、自适应解释器与无 GIL 路线 |
| 难度 / 建议时长 | ★★★★★ · 55 分钟 |
| 本讲新增 | 先算法后实现、数据结构与批处理、向量化与 NumPy |
| 一句话目标 | 按层次系统性地压低延迟 |
| 为下一讲铺垫 | 架构设计：领域分层、演进与重构 |


## 先剖析再动手：cProfile、timeit 与 Amdahl 定律

优化前必须先定位。

cProfile 基于 C 层的 `_lsprof`，按函数统计 ncalls、tottime（函数自身耗时）、cumtime（含子调用），用 `pstats.sort_stats('cumtime')` 找累计热点；它是确定性 profiler，会给每次 Python 调用加固定开销，适合找「哪个函数」而非精确绝对耗时。

精确微基准用 `timeit`，默认关闭 gc 并重复多次取最小值，避免单次调度噪声；耗时对比用 `time.perf_counter` 而不是 `time.time`。

`tracemalloc` 定位内存分配点。

Amdahl 定律给出上限：若某部分占总耗时比例 p，把它加速 s 倍，整体加速上限是 `1 / ((1-p) + p/s)`；`p=0.2` 的部分即便优化到无限快，整体最多快 1.25 倍。

因此把两周花在占比 8% 的解析循环上，收益注定有限。剖析要在线上真实输入分布下做，构造数据与真实数据常常不同（例如热点 key 分布、对象大小），结论要写成可复现脚本随代码提交；每一层优化都留下基准与回归测试，性能数字进入 CI，才不会被后续重构悄悄吃掉。

```python
import time

data = list(range(2000))
targets = list(range(0, 2000, 3))

def naive(xs, ys):
    out = 0
    for x in xs:
        for y in ys:
            if x == y:
                out += 1
                break
    return out

def with_set(xs, ys):
    s = set(ys)
    return sum(1 for x in xs if x in s)

t0 = time.perf_counter(); a = naive(data, targets); t1 = time.perf_counter()
t2 = time.perf_counter(); b = with_set(data, targets); t3 = time.perf_counter()
print('counts', a, b)
print('equal', a == b)
print('set_is_faster', (t3 - t2) < (t1 - t0))
```

<OutputBox title='主示例运行结果' output='counts 667 667\nequal True\nset_is_faster True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import time\n\ndata = list(range(2000))\ntargets = list(range(0, 2000, 3))\n\ndef naive(xs, ys):\n    out = 0\n    for x in xs:\n        for y in ys:\n            if x == y:\n                out += 1\n                break\n    return out\n\ndef with_set(xs, ys):\n    s = set(ys)\n    return sum(1 for x in xs if x in s)\n\nt0 = time.perf_counter(); a = naive(data, targets); t1 = time.perf_counter()\nt2 = time.perf_counter(); b = with_set(data, targets); t3 = time.perf_counter()\nprint(&#39;counts&#39;, a, b)\nprint(&#39;equal&#39;, a == b)\nprint(&#39;set_is_faster&#39;, (t3 - t2) &lt; (t1 - t0))' :notes='["导入 time 用 perf_counter 计时", "空行，只用于分隔逻辑块，不影响执行结果。", "构造 2000 个整数的待查数据", "构造 667 个目标值（0 到 1999 的 3 的倍数）", "空行，只用于分隔逻辑块，不影响执行结果。", "naive 是双重循环的 O(n*m) 成员检测", "结果计数器归零", "外层遍历每个待查元素", "内层线性扫描目标列表", "逐个比较找到即计数", "命中后计数加一", "提前跳出内层，但最坏仍要扫到尾部", "返回命中总数", "空行，只用于分隔逻辑块，不影响执行结果。", "with_set 先建集合再线性扫描", "把目标列表转成 set，查找平均 O(1)", "统计待查元素中落在集合里的个数", "空行，只用于分隔逻辑块，不影响执行结果。", "测量双重循环耗时", "测量集合方案耗时", "两方案结果应一致，都是 667", "打印命中数，验证结果等价", "确认结果相等，优化不改变语义"]' title='第 119 讲 · 极致优化：从剖析到 C 扩展的十倍案例' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**剖析工具与适用**

| 工具 | 口径 | 适用 |
| --- | --- | --- |
| cProfile / pstats | 按函数 tottime / cumtime / ncalls | 找哪个函数热 |
| timeit | 重复多次取最小，默认关 gc | 精确微基准，避免单次噪声 |
| time.perf_counter | 单调高精度墙钟 | 分段计时与对比 |
| tracemalloc | 按分配点 traceback | 定位内存分配热点 |

<ConceptDiagram type='compare2' title='第 119 讲 · 先剖析再动手：cProfile、timeit 与 Amdahl 定律' labels='先剖析再动手：cProfile、timeit…|算法、数据结构与批处理：数量级收益|向量化、C 扩展、原生并行与停止条件|缓存与异构卸载' caption='按层次系统性地压低延迟' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### Amdahl 上限怎么算

**Amdahl 上限示例**

| 热点占比 p | 该部分加速 s | 整体加速上限 1/((1-p)+p/s) |
| --- | --- | --- |
| 0.20 | 无限大 | 1.25 倍 |
| 0.50 | 无限大 | 2.00 倍 |
| 0.80 | 10 倍 | 3.57 倍 |
| 0.95 | 10 倍 | 6.90 倍 |


## 算法、数据结构与批处理：数量级收益

换算法是收益最大的一层。成员检测用 list 是 `O(n)`、用 set 或 dict 是平均 `O(1)`；`n=2000` 的双重循环约 1.3e6 次比较（两个集合一个 2000、一个按步长 3 取到 667），改成一次建 set 加线性扫描降到 `O(n+m)`，数量级差异远大于任何语法微调。

字符串循环里累加要用 `''.join(list)` 而不是反复 +，避免反复分配与拷贝；频繁在序列头部插入，用 `collections.deque` 的 `appendleft`（`O(1)`）而非 `list.insert(0)`（`O(n)`）。

批处理把逐条数据库往返合并成一次 IN 查询或 `executemany`，把网络 RTT 这个常数从 n 次降到 1 次，通常比优化循环体本身有效得多。

缓存放在正确的粒度：重复计算用 `functools.lru_cache`，不变结果用预计算表，注意键要可哈希且有界（maxsize），防止内存膨胀。

内置函数把循环下沉到 C：sum、min、sorted、any、all 走 C 实现，比等价的纯 Python for 循环少掉字节码分派开销。这一层的关键是先用复杂度与调用次数估算上限，再动手改，而不是凭感觉改语法。

```python
import time

data = list(range(1000000))
t0 = time.perf_counter(); a = sum(data); t1 = time.perf_counter()
t2 = time.perf_counter()
b = 0
for x in data:
    b += x
t3 = time.perf_counter()
print('equal', a == b)
print('builtin_faster', (t1 - t0) < (t3 - t2))
print('values', a)
```

<OutputBox title='对照写法：先自己猜，再点开' output='equal True\nbuiltin_faster True\nvalues 499999500000' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import time\n\ndata = list(range(2000))\ntargets = list(range(0, 2000, 3))\n\ndef naive(xs, ys):\n    out = 0\n    for x in xs:\n        for y in ys:\n            if x == y:\n                out += 1\n                break\n    return out\n\ndef with_set(xs, ys):\n    s = set(ys)\n    return sum(1 for x in xs if x in s)\n\nt0 = time.perf_counter(); a = naive(data, targets); t1 = time.perf_counter()\nt2 = time.perf_counter(); b = with_set(data, targets); t3 = time.perf_counter()\nprint(&#39;counts&#39;, a, b)\nprint(&#39;equal&#39;, a == b)\nprint(&#39;set_is_faster&#39;, (t3 - t2) &lt; (t1 - t0))", "note": "先剖析再动手：cProfile、timeit 与 Amdahl 定律"}, {"label": "对照 / 进阶", "code": "import time\n\ndata = list(range(1000000))\nt0 = time.perf_counter(); a = sum(data); t1 = time.perf_counter()\nt2 = time.perf_counter()\nb = 0\nfor x in data:\n    b += x\nt3 = time.perf_counter()\nprint(&#39;equal&#39;, a == b)\nprint(&#39;builtin_faster&#39;, (t1 - t0) &lt; (t3 - t2))\nprint(&#39;values&#39;, a)", "note": "算法、数据结构与批处理：数量级收益"}]' title='两种写法切换看' />


### 对照：双重循环与 set 的命中统计

```python
import cProfile, pstats, io

def work():
    return sum(i * i for i in range(20000))

pr = cProfile.Profile()
pr.enable(); v = work(); pr.disable()
s = io.StringIO()
pstats.Stats(pr, stream=s).strip_dirs().sort_stats('cumtime').print_stats()
text = s.getvalue()
print('result', v)
print('has_work', 'work' in text)
print('has_genexpr', 'genexpr' in text)
```

<OutputBox title='原理验证' output='result 2666466670000\nhas_work True\nhas_genexpr True' />


## 向量化、C 扩展、原生并行与停止条件

Python 层循环无法避免时，下一层是把计算交给不逐条走字节码的执行体。NumPy 对数值数组做向量化，单次调用在 C 里处理整块连续内存，既省分派也命中 `SIMD`；list 存的是 PyObject 指针、并不连续，因此密集数值应先转成 `ndarray`。

Cython 把带类型注解的 Python 编译成 C 扩展，C 扩展可直接用 C API 操作对象或纯 C 数组；写 C 扩展时长计算要用 `Py_BEGIN_ALLOW_THREADS` 释放 GIL 才能真正并行。

多进程用 `multiprocessing` / `ProcessPoolExecutor` 绕过 GIL 用满多核，代价是 pickle 序列化与内存拷贝，数据量大时共享内存或内存映射更合适。

缓存与异构卸载（把计算推给数据库、Redis 或专用服务）能减少数据搬移。停止条件由 SLO 与数据决定：达到延迟目标就停，继续优化的边际收益要能覆盖可维护性损失；不可读的优化必须隔离在小函数、写明基准数字与原因，并配回归基准。没有测量就没有优化，只有改写。

**优化层次与典型收益**

| 层次 | 手段 | 收益量级 |
| --- | --- | --- |
| 算法与数据结构 | list 查找改 set、O(n^2) 降 O(n) | 数量级 |
| 批处理 | 逐条 DB 往返合并为 IN/executemany | 数量级（消 RTT 常数） |
| 内置与向量化 | sum/sorted、NumPy ndarray | 常数到数十倍 |
| C 扩展 / Cython | C API 或编译到 C | 常数倍，牺牲可维护性 |
| 原生并行 | 多进程、释放 GIL 的 C 扩展 | 随核数，受序列化限制 |
| 缓存与卸载 | lru_cache、推给数据库/Redis | 取决于命中率与数据搬移 |

优化收益的上限由 Amdahl 定律约束：整体加速等于 `1 / ((1-p) + p/s)`，其中 p 是被优化部分原本占总耗时的比例、s 是它获得的加速。

这解释了为什么把占比 8% 的循环改写成 C 最多带来约 1.09 倍整体提升，而先消除一次多余数据库往返、或把一个 `O(n^2)` 成员检测改成 `O(n)`，能带来数量级变化。

Python 层循环昂贵的根源，是每条字节码都要经过 ceval 分派与引用计数维护；内置函数与 NumPy 把循环下沉到 C，用连续内存与更少的分派完成同样工作，而 list 存的是 PyObject 指针且分散，密集数值必须转成 `ndarray` 才能命中 `SIMD` 与缓存局部性。

多进程绕过 GIL 用满多核，但跨进程参数与返回值要 pickle，数据量大时序列化与拷贝会吃掉并行收益，需共享内存或加大任务粒度。C 扩展里长计算要显式释放 GIL。所有层次都依赖同一前提：先剖析得到 p，再按 p 排序投入，达到 SLO 即停，并用基准与回归测试锁住成果。


### 优化后不留基准与回归测试

<Callout type="warn" title='本讲最容易踩的坑' text='一上来用 Cython 重写热点函数：若瓶颈其实是数据库往返或 O(n^2) 算法，被优化部分占比很低，Amdahl 定律下整体收益极小' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：一上来用 Cython 重写热点函数", "body": "若瓶颈其实是数据库往返或 O(n^2) 算法，被优化部分占比很低，Amdahl 定律下整体收益极小", "tip": "先用 cProfile 找 cumtime 热点并估算占比 p，优先改算法与批处理，再考虑 C 扩展"}, {"title": "第 2 步：用 time.time 单次计时做微基准，且…", "body": "系统时间可回拨、单次测量含调度噪声、3.11 起特化预热前后不同，结论不可复现", "tip": "用 time.perf_counter 或 timeit 重复多轮取最小，先预热；结论标注版本与输入分布"}, {"title": "第 3 步：优化后不留基准与回归测试", "body": "后续重构把写法改回去时没有任何测试拦截，性能悄悄退化且难以归因", "tip": "把基准脚本随代码提交，关键指标进 CI 设阈值；不可读优化隔离在小函数并写明基准数字与原因"}]' />


## 分层优化的可复现基准脚本

把一个聚合任务按层次重写并逐层计时：先记录朴素双重循环基线，再改算法用 set、再改实现用内置 sum，最后对比向量化思路，同时打印每层的相对耗时与结果一致性，确保优化不改变语义。真实项目里把这段放进 CI，任何一层退化超过阈值就失败。

下面这段用标准库把「先剖析、按层改、留基准」固化成脚本，重点是每个数字都可复现、每个改动都验证等价。

```python
import time, cProfile, pstats, io

def measure(name, fn):
    t0 = time.perf_counter()
    r = fn()
    return name, r, (time.perf_counter() - t0) * 1000

data = list(range(20000))
targets = set(range(0, 20000, 3))

def loop_version():
    return sum(1 for x in data if x in targets)

def set_version():
    return len(set(data) & targets)

results = [measure('loop', loop_version), measure('set', set_version)]
for name, r, ms in results:
    print(name, r, round(ms, 3))
print('equal', results[0][1] == results[1][1])

pr = cProfile.Profile()
pr.enable(); loop_version(); pr.disable()
s = io.StringIO()
pstats.Stats(pr, stream=s).sort_stats('cumtime').print_stats(3)
print('profile_has_loop', 'loop_version' in s.getvalue())
```

<Callout type="idea" title='落地提示' text='每一层优化都留下基准与回归测试，用数据决定何时停止；把不可读的优化隔离在小函数并写清原因' />

<CheckList id='P119a' title='上线前自检' :items='["能复现并解释「一上来用 Cython 重写热点函数」", "能复现并解释「用 time.time 单次计时做微基准，且不预热」", "能复现并解释「优化后不留基准与回归测试」", "能用一条命令验证 先算法后实现", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import cProfile; cProfile.run('sum(range(100000))', sort='cumtime')"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 先算法后实现 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 一上来用 Cython 重写热点函数 | 若瓶颈其实是数据库往返或 O(n^2) 算法，被优化部分占比很低，Amdahl 定律下整体收益极小 | 先用 cProfile 找 cumtime 热点并估算占比 p，优先改算法与批处理，再考虑 C 扩展 |
| 用 time.time 单次计时做微基准，且不预热 | 系统时间可回拨、单次测量含调度噪声、3.11 起特化预热前后不同，结论不可复现 | 用 time.perf_counter 或 timeit 重复多轮取最小，先预热；结论标注版本与输入分布 |
| 优化后不留基准与回归测试 | 后续重构把写法改回去时没有任何测试拦截，性能悄悄退化且难以归因 | 把基准脚本随代码提交，关键指标进 CI 设阈值；不可读优化隔离在小函数并写明基准数字与原因 |


## _lsprof.c 的确定性剖析钩子与测量偏差

cProfile 不是采样器，而是挂在解释器回调上的确定性 profiler。

`Modules/_lsprof.c` 的 `_lsprof.Profiler` 通过 PyEval_SetProfile 注册回调，每个函数调用与返回、C 函数调用与返回都触发一次：它记录 `PyTime_GetPerfCounter()` 的单调时钟差值，把 callcount、reccallcount、tt、ct 累加到以 (code, caller) 为键的 callers 字典，`pstats.Stats` 再按 cumtime 排序。

代价正是每次事件都要进一次回调，微基准里几十纳秒的函数会被回调开销放大数倍，cProfile 的绝对耗时不能当真实延迟，只能定位占比。3.12 起 PEP 669 的 `sys.monitoring` 提供低开销替代，它在字节码预留监控点按需插桩，未启用工具的事件几乎零成本。

timeit 走另一条路：`Lib/timeit.py` 用 `time.perf_counter`，计时前后 `gc.disable()`，`Timer.autorange()` 反复把 number 翻倍直到单次超过 0.2 秒，再对多次 repeat 取最小值——取 min 是因为调度、中断、变频只让测量变慢，最小值最接近无干扰下界。

pyperf 进一步用多进程、预热与统计模型压住 CPU 变频与 `ASLR` 抖动。结论：cProfile 找占比 p，timeit / pyperf 测加速比 s，两者口径不同不能混用。

```python
import timeit, cProfile, pstats, io

def amdahl(p, s):
    return 1.0 / ((1.0 - p) + p / s)

print('amdahl_8pct_10x', round(amdahl(0.08, 10.0), 3))
print('amdahl_8pct_ceiling', round(amdahl(0.08, 1e12), 3))

timer = timeit.Timer('sum(range(50))')
loops, _ = timer.autorange()
print('autorange_loops_ge_1', loops >= 1)

pr = cProfile.Profile()
pr.enable()
sum(range(1000))
pr.disable()
buf = io.StringIO()
pstats.Stats(pr, stream=buf).strip_dirs().sort_stats('cumtime').print_stats(2)
text = buf.getvalue()
print('cumtime_label', 'cumtime' in text)
print('builtin_sum_traced', '{built-in method builtins.sum}' in text)
```

<OutputBox title='扩展示例运行结果' output='amdahl_8pct_10x 1.078\namdahl_8pct_ceiling 1.087\nautorange_loops_ge_1 True\ncumtime_label True\nbuiltin_sum_traced True' />

<LineByLine code='import timeit, cProfile, pstats, io\n\ndef amdahl(p, s):\n    return 1.0 / ((1.0 - p) + p / s)\n\nprint(&#39;amdahl_8pct_10x&#39;, round(amdahl(0.08, 10.0), 3))\nprint(&#39;amdahl_8pct_ceiling&#39;, round(amdahl(0.08, 1e12), 3))\n\ntimer = timeit.Timer(&#39;sum(range(50))&#39;)\nloops, _ = timer.autorange()\nprint(&#39;autorange_loops_ge_1&#39;, loops &gt;= 1)\n\npr = cProfile.Profile()\npr.enable()\nsum(range(1000))\npr.disable()\nbuf = io.StringIO()\npstats.Stats(pr, stream=buf).strip_dirs().sort_stats(&#39;cumtime&#39;).print_stats(2)\ntext = buf.getvalue()\nprint(&#39;cumtime_label&#39;, &#39;cumtime&#39; in text)\nprint(&#39;builtin_sum_traced&#39;, &#39;{built-in method builtins.sum}&#39; in text)' :notes='["Amdahl 公式 S = 1 / ((1-p) + p/s)", "空行，只用于分隔逻辑块，不影响执行结果。", "占比 8%、加速 10 倍时整体只快约 1.078 倍", "即便 s 趋于无穷，上限也只有约 1.087 倍", "空行，只用于分隔逻辑块，不影响执行结果。", "autorange 自动把循环次数翻倍到样本足够", "返回次数必大于等于 1，作为校准判据", "空行，只用于分隔逻辑块，不影响执行结果。", "开启确定性 profiler 追踪一段内置求和", "按 cumtime 排序打印前两行", "cProfile 会追踪内置函数，输出 builtins.sum 一条", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `pr = cProfile.Profile()` 的作用，可对照上方输出逐项核对。", "这一行 `pr.enable()` 的作用，可对照上方输出逐项核对。", "这一行 `sum(range(1000))` 的作用，可对照上方输出逐项核对。", "这一行 `pr.disable()` 的作用，可对照上方输出逐项核对。", "这一行 `buf = io.StringIO()` 的作用，可对照上方输出逐项核对。", "这一行 `pstats.Stats(pr, stream=buf).strip_dirs().sort_stats` 的作用，可对照上方输出逐项核对。", "这一行 `text = buf.getvalue()` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;cumtime_label&#39;, &#39;cumtime&#39; in text)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;builtin_sum_traced&#39;, &#39;{built-in method builti` 的作用，可对照上方输出逐项核对。"]' title='扩展示例逐行讲解' />


### timeit.autorange 与 pyperf 的校准口径

**剖析工具的 C 层与统计口径**

| 工具 / 接口 | C 实现或机制 | 计时源 | 主要误差 |
| --- | --- | --- | --- |
| cProfile / pstats | _lsprof.c + PyEval_SetProfile | PyTime_GetPerfCounter | 每事件回调开销，绝对耗时偏高 |
| timeit.Timer | Lib/timeit.py + time.perf_counter | 单调钟 | GC 与调度噪声，靠 repeat 取 min |
| sys.monitoring (PEP 669) | 字节码监控点按需插桩 | 调用方自选 | 需 3.12+，工具 ID 与事件粒度 |
| pyperf | 多进程校准加统计模型 | perf_counter_ns | CPU 变频、ASLR、后台负载 |
| line_profiler | C 层 trace 逐行 | 单调钟 | 逐行回调比 cProfile 更重 |

<Quiz no='119-1' q='cProfile 给出的绝对耗时为什么不能直接当微基准的真实延迟？' :options='["它用 PyEval_SetProfile 对每个调用与返回事件做回调，回调本身带来可观开销", "它使用 time.time，会被系统时钟回拨影响", "它只在程序退出时采样一次", "它把 GC 时间算进了 wall clock 之外"]' answer="0" explain='_lsprof.c 的确定性 profiler 通过 PyEval_SetProfile 在每次函数调用返回与 C 调用返回时进一次回调读取 perf_counter，事件开销叠加到被调函数上，几十纳秒级函数会被显著放大；因此 cProfile 只适合找热点占比，绝对延迟要用 timeit / pyperf 测。' />


## Amdahl 之外的误差源：变频、缓存与 GC

<ConceptDiagram type='flow4' title='第 119 讲 · 扩展图解' labels='cProfile 定位占比 p|timeit/pyperf 测加速比 s|Amdahl 估算上限|基准与回归进 CI' caption='优化决策链：剖析给占比、基准给收益、Amdahl 决定是否值得，每层都留下可回放的基准' />


## METH_FASTCALL、Py_buffer 与一次装箱的 C 边界

把热点从 Python 循环搬到 C 扩展，收益来自少建 PyObject、少走分派，不是 C 语法本身更快。

调用约定先省一层：`METH_VARARGS` 要为每个参数 build 一个 tuple，而 `METH_FASTCALL` / `METH_O` 直接收到 PyObject *const *args 与 nargs，省掉元组构造；3.10 起 `METH_FASTCALL` | `METH_KEYWORDS` 还能用 kwnames 单独传关键字名。

真正的数量级收益来自数据布局：用 PEP 3118 的 Py_buffer 或 memoryview 拿到 buf、len、itemsize、strides，在 C 里用原生 double / int64 数组循环，最后只把结果 PyLong_FromLong 装箱一次；若逐元素 PyLong_AsLong 再 PyNumber_Add，就退化成 Python 语义的 C 版本。

要让多核参与，得在计算段用 Py_BEGIN_ALLOW_THREADS / Py_END_ALLOW_THREADS 临时释放 GIL，但这段里不能碰任何 Python API，自由线程构建下还要自己处理容器锁。

工程边界同样重要：扩展要按 PEP 489 多阶段初始化写，Py_LIMITED_API 换稳定 ABI 会牺牲一部分内联访问速度，换来跨小版本不用重编译；这些代价要连同收益一起写进 ADR 权衡。


### Py_BEGIN_ALLOW_THREADS 与稳定 ABI 的取舍

<Exercise title='用 timeit.repeat 的最小值替代单次 time.time' task='用 timeit.repeat 对同一语句重复 5 轮、每轮 number 由 autorange 决定，打印各轮每循环耗时并解释为什么取 min 而不是 mean；把结论写成带解释器版本号的判据。' solution='import sys, timeit\n\ntimer = timeit.Timer(&#39;sum(range(200))&#39;)\nnumber, _ = timer.autorange()\nper_loop = [r / number for r in timer.repeat(repeat=5, number=number)]\nbest = min(per_loop)\nprint(&#39;number_ge_1&#39;, number &gt;= 1)\nprint(&#39;rounds&#39;, len(per_loop))\nprint(&#39;best_le_each&#39;, all(best &lt;= r for r in per_loop))\nprint(&#39;python&#39;, sys.version.split()[0])' explain='timeit 用 perf_counter 单调钟并临时关闭 GC；repeat 的多轮里调度中断、后台负载、CPU 变频只会让某轮变慢，取最小值最接近无干扰下界，均值反而把噪声平均进结果。结论必须带解释器版本与构建，3.11 起特化预热还会让前几轮偏慢。' />

<Term word='METH_FASTCALL' text='Include/methodobject.h 定义的调用约定标志：C 函数直接收到 PyObject *const *args 与 nargs，不必像 METH_VARARGS 那样先构造参数 tuple，也不像 METH_O 只支持单参数，是 3.7 起内置函数与 C 扩展降低调用开销的常用入口。' />


## 练习与自测

<Exercise title='基础：用 Amdahl 定律估算收益上限' task='写 speedup(p, s) 返回 1/((1-p)+p/s)，打印 p=0.2 与 s=10、s=1000000 的结果，解释为什么占比低的部分不值得重写。' solution='def speedup(p, s):\n    return 1 / ((1 - p) + p / s)\nprint(round(speedup(0.2, 10), 3))\nprint(round(speedup(0.2, 1000000), 3))' explain='p=0.2 时即便把该部分加速到 10 倍或无限快，整体也只约 1.22 与 1.25 倍；占比低的部分投入产出比很差，应先找高 p 热点。' />

<Exercise title='进阶：用 cProfile 找真实热点' task='对一个含生成器与内置 sum 的函数跑 cProfile，按 cumtime 排序，指出哪个条目是累计热点并说明 tottime 与 cumtime 的区别。' solution='import cProfile, pstats, io\ndef work():\n    return sum(i * i for i in range(20000))\npr = cProfile.Profile()\npr.enable(); work(); pr.disable()\ns = io.StringIO()\npstats.Stats(pr, stream=s).sort_stats(&#39;cumtime&#39;).print_stats()\nprint(&#39;has_genexpr&#39;, &#39;genexpr&#39; in s.getvalue())' explain='tottime 是函数自身不含子调用的耗时，cumtime 含子调用；按 cumtime 排序能定位真正拖慢整体的调用链，genexpr 往往是这里的主要累计项。' />

<Quiz no='119-2' q='某热点函数只占总耗时 8%，把它用 C 重写并加速 10 倍，整体大约能快多少？' :options='["约 1.08 倍，收益很小", "约 10 倍", "约 2 倍", "无法估算"]' answer="0" explain='Amdahl 定律：1/((1-0.08)+0.08/10) ≈ 1.08。占比低的部分无论怎么优化，整体上限都被剩余 92% 锁死。' />

<Quiz no='119-3' q='优化顺序中通常收益最大的是？' :options='["换算法与数据结构、合并批处理", "把 for 改成 while", "调整变量命名", "给函数加类型注解"]' answer="0" explain='把 O(n^2) 降为 O(n)、把逐条数据库往返合并成一次，带来数量级收益；改语法或注解通常只是常数级甚至无收益。' />

<Quiz no='119-4' q='做 Python 微基准时，正确做法是？' :options='["用 timeit 重复多轮取最小并预热，结论标注版本与输入", "用 time.time 跑一次", "只看 cProfile 的绝对耗时", "关闭所有优化后再测"]' answer="0" explain='time.perf_counter/timeit 提供单调高精度计时，预热触发 3.11+ 的自适应特化，多轮取最小削掉调度噪声；cProfile 有固定开销，适合找函数而非测绝对耗时。' />

<FillBlank no='119-5' tpl='___ time' :answers='["import"]' hint='回想本讲关于 先算法后实现 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 先剖析再动手：cProfile、timeit 与 Amdahl 定律 的落点。' />

<KnowledgeCard :points='["先剖析再动手：cProfile 找 cumtime 热点，timeit 精确计时，tracemalloc 定位分配", "Amdahl 定律 1/((1-p)+p/s) 给出上限，占比低的部分不值得用 C 重写", "换算法与数据结构（list→set、O(n^2)→O(n)）、合并批处理是数量级收益", "内置函数/NumPy 把循环下沉到 C；list 存分散 PyObject，密集数值转 ndarray", "C 扩展长计算释放 GIL；多进程绕过 GIL 但要算 pickle 与内存拷贝成本", "达到 SLO 即停；不可读优化隔离小函数，写清基准数字并留回归测试进 CI"]' :pitfalls='["一上来用 Cython 重写热点函数", "用 time.time 单次计时做微基准，且不预热", "优化后不留基准与回归测试", "一上来用 C 重写热点，会牺牲可维护性，却可能发现瓶颈其实是一次多余的数据库往返"]' summary='优化有明确顺序：换算法通常带来数量级收益，改语法只带来常数收益；先剖析再动手是唯一可靠的路径' />

1. 先剖析再动手：cProfile 找 cumtime 热点，timeit 精确计时，tracemalloc 定位分配

2. Amdahl 定律 1/((1-p)+p/s) 给出上限，占比低的部分不值得用 C 重写

3. 换算法与数据结构（list→set、O(n^2)→O(n)）、合并批处理是数量级收益

[下一讲：架构设计：领域分层、演进与重构](/advanced/architecture)

<Predict no='119-6' q='naive 双重循环与 with_set 对同一批数据统计命中数，结果关系是？' :options='["两者都是 667 且 equal 为 True", "naive 更快且结果不同", "with_set 抛 TypeError"]' answer='0' output='counts 667 667，equal True，set_is_faster True' explain='两种写法统计的是同一集合关系，结果应一致；set 把成员检测从 O(n*m) 降到 O(n+m)，数量级更低，实测更快。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/119-optimization.py`

```bash
python3 examples/lessons/119-optimization.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/119-optimization.py) · [全部示例代码索引](/examples/)
