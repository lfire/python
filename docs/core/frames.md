---
title: 第 051 讲 · 帧、调用栈与命名空间
description: 理解执行上下文如何被创建与销毁
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='35 分钟' goal='理解执行上下文如何被创建与销毁' prereq='第 050 讲 · 字节码、栈式虚拟机与 dis 实战' />

# 第 051 讲 · 帧、调用栈与命名空间

看过指令，接着看指令站在哪儿跑。每次函数调用都撑起一块执行上下文，放着局部变量与返回位置；函数一结束就拆掉，生成器却偏能挂起、过会儿接着用。理解这块「舞台」，报错栈和惰性求值就有着落。

一个覆盖率工具结果偏低，因为有人改了 `locals()` 却期待变量跟着变；还有服务长期开着追踪回调。本讲先讲帧对象与 `f_locals`、`f_globals`，再走到调用栈与 tracing 回调，最后说生成器帧为何被保留、`locals()` 能否写回。需要阶段三的函数作用域与第 50 讲的字节码；学完你能说清 traceback 从哪来，写 profiler 时该动哪一层。


## 一个 traceback 里 f_locals 和预期对不上的调试现场

一个覆盖率工具上线后结果明显偏低：开发者在函数里通过 `locals()['x'] = 99` 修改局部变量，期待后续逻辑读到 99，实际变量纹丝不动，覆盖到的分支自然对不上；

换成 `frame.f_locals` 又发现 3.13 上行为完全相反，老资料里的快照结论对不上了。

另一处线上事故来自递归：一个没有正确收敛的解析函数在深层输入上抛 `RecursionError`（提示超过最大递归深度），有人把 `sys.setrecursionlimit` 一路调到十万，结果解释器直接崩溃。

还有人把 `sys.settrace` 长期挂在服务里做埋点，p99 延迟涨了一截，因为每一行、每次调用都要回调 Python 函数。生成器能「暂停后继续」也常被讲成魔法，其实物理基础就是帧被挂起而没有销毁。帧、调用栈与命名空间是执行上下文的骨架。

本讲把帧对象的属性、`locals()` 与 `globals()` 的语义差异、追踪回调、递归深度、生成器帧保留与 traceback 来源逐条讲清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='在帧里改 locals() 期待改变局部变量，或把 3.12 的 f_locals 快照结论套到 3.13：locals() 始终是独立快照，写入不回写；3.13 的 PEP 667 却把 frame.f_locals 改成写透代理，写入直接改局部变量，行为随版本翻转' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段五 · 核心机制与运行时 |
| 前置 | 第 050 讲 · 字节码、栈式虚拟机与 dis 实战 |
| 难度 / 建议时长 | ★★★★☆ · 35 分钟 |
| 本讲新增 | 帧对象与 f_locals / f_globals、调用栈与递归深度、sys.setprofile 与 tracing |
| 一句话目标 | 理解执行上下文如何被创建与销毁 |
| 为下一讲铺垫 | 对象内存布局、引用计数与小对象池 |


## 帧对象：f_locals、f_globals、f_back 与属性查找

每次 Python 函数调用都会创建一个执行帧，暴露为 frame 对象。

常用属性：`f_code` 指向正在执行的 code object，`f_locals` 是局部命名空间的字典快照，`f_globals` 是模块全局字典，`f_builtins` 是内置命名空间，`f_back` 指向调用者帧（沿这条链往上就是调用栈），`f_lasti` 是上一条已执行指令的字节码偏移，`f_lineno` 是当前源码行，`f_trace` 是当前帧的局部追踪函数。

获取方式：`sys._getframe(depth)`（`depth=0` 是当前帧）或 `inspect.currentframe()`。

关键差异在 `f_globals is globals()` 通常为 `True`——它是真实模块字典，往里写会立刻影响全局名字；

而 `locals()` 是把 fast locals 数组同步出来的独立快照字典，写入不回写。

CPython 3.11 起帧数据尽量内联在解释器的 `_PyInterpreterFrame` 里，只在被 `sys._getframe`、traceback 或生成器暴露时才物化成 `PyFrameObject`，降低了调用开销。

3.13 的 PEP 667 把 `frame.f_locals` 改成写透代理：写它会直接改变局部变量，而 `locals()` 仍是独立快照；3.12 及以前两者都是快照，写入都不生效。

```python
import sys

G = 0
def probe():
    x = 1
    snap = locals()
    snap['x'] = 50
    print('locals snapshot', x == 1)
    frame = sys._getframe()
    frame.f_locals['x'] = 99
    print('f_locals writes through', x == 99)
    print('names', sorted(frame.f_code.co_varnames))
    print('globals is module', frame.f_globals is globals())
    globals()['G'] = 7
    print('G changed', G == 7)
    return frame.f_lasti >= 0
print('result', probe())
```

<OutputBox title='主示例运行结果' output='locals snapshot True\nf_locals writes through True（3.13+ PEP 667 写透代理；3.12 及以前为 False）\nnames [&#39;frame&#39;, &#39;snap&#39;, &#39;x&#39;]\nglobals is module True\nG changed True\nresult True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys\n\nG = 0\ndef probe():\n    x = 1\n    snap = locals()\n    snap[&#39;x&#39;] = 50\n    print(&#39;locals snapshot&#39;, x == 1)\n    frame = sys._getframe()\n    frame.f_locals[&#39;x&#39;] = 99\n    print(&#39;f_locals writes through&#39;, x == 99)\n    print(&#39;names&#39;, sorted(frame.f_code.co_varnames))\n    print(&#39;globals is module&#39;, frame.f_globals is globals())\n    globals()[&#39;G&#39;] = 7\n    print(&#39;G changed&#39;, G == 7)\n    return frame.f_lasti &gt;= 0\nprint(&#39;result&#39;, probe())' :notes='["导入 sys，用于取当前帧与全局字典", "空行，只用于分隔逻辑块，不影响执行结果。", "模块级全局名字，用于对比 globals() 写回效果", "定义函数，内部演示帧与命名空间语义", "局部变量 x 存进 fast locals 数组", "locals() 返回独立快照字典（PEP 667 后语义不变）", "改快照里的 x，不影响真正的局部变量", "快照写入不回写，x 仍是 1", "sys._getframe(0) 拿到当前执行帧", "3.13 起 frame.f_locals 是写透代理，写入直接改局部 x", "写透生效，x 变为 99（3.12 及以前仍是快照，结果相反）", "co_varnames 按顺序列出局部变量名", "f_globals 与 globals() 指向同一份模块字典", "globals() 返回真实字典，写入立即影响全局名字", "读到的 G 已变成 7，证明全局写回有效", "f_lasti 是当前字节码偏移，执行中恒非负", "调用并打印返回值"]' title='第 051 讲 · 帧、调用栈与命名空间' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 帧对象常用属性

**帧对象常用属性**

| 属性 | 内容 | 典型用途 |
| --- | --- | --- |
| f_code | 正在执行的 code object | 读 co_name / co_varnames |
| f_locals | 局部命名空间字典快照 | 查看而非改写局部状态 |
| f_globals | 模块全局字典 | 与 globals() 同一份，写入生效 |
| f_builtins | 内置命名空间 | 查内置名字来源 |
| f_back | 调用者帧 | 沿链还原调用栈 |
| f_lasti / f_lineno | 字节码偏移 / 源码行 | 覆盖率与调试器定位 |
| f_trace | 本帧局部追踪函数 | settrace 回调返回值决定 |


## 执行上下文在 CPython 里如何创建与销毁

CPython 每次 Python 函数调用都建立一个执行帧。3.11 之前帧是堆上的 `PyFrameObject`；

3.11 起改成尽量内联的 `_PyInterpreterFrame`，放在解释器的数据栈 chunk 里，只有在 `sys._getframe()`、traceback 或生成器需要暴露时才物化出 `PyFrameObject`，从而减少分配与间接寻址。

局部变量存在 fast locals 数组里，`LOAD_FAST` 按索引读取；`locals()` 把这份数组同步成独立快照字典返回，写入不回写，而 `globals()` 直接返回模块字典、修改立即生效。

3.13 的 PEP 667 把 `frame.f_locals` 改成写透代理（写入直达 fast locals），`locals()` 则明确保持独立快照；3.12 及以前两者都是快照。生成器不销毁帧：`gi_frame` 保留局部变量与 `f_lasti`，`next()` 从断点恢复，耗尽后释放。

递归深度由 C 层计数与 `sys.getrecursionlimit` 约束，超限抛 `RecursionError`；

调得过高会先耗尽 C 栈。traceback 是异常对象上的 tb 链，节点指向帧、行号与下一节点，traceback 模块沿链打印。

`sys.settrace` / `sys.setprofile` 在 `call` / `line` / `return` / `exception` 事件上回调 Python 函数，开销与事件密度成正比。

<ConceptDiagram type='flow4' title='第 051 讲 · 帧对象：f_locals、f_globals、f_back 与属性查找' labels='帧对象：f_locals、f_globals…|调用栈、递归深度与 tracing 回调|生成器帧保留与 locals() 语义边界|locals() 的语义' caption='理解执行上下文如何被创建与销毁' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

<Callout type="tip" title='核心心智模型' text='每次 Python 函数调用都会创建一个执行帧，暴露为 frame 对象。常用属性：`f_code` 指向正在执行的 code object，`f_locals` 是局部命名空间的字典快照，`f_globals` 是模块全局字典，`f_builtins` 是内置命名空间，`f_back` 指向调用者…' />


## 调用栈、递归深度与 tracing 回调

调用栈由帧的 `f_back` 链构成，异常对象的 `__traceback__` 也沿这条链记录每个帧与行号，traceback 模块打印的就是它。

递归深度由 C 层计数与 `sys.getrecursionlimit()`（默认 1000）共同约束，超过抛 `RecursionError`；

`sys.setrecursionlimit(n)` 可调，但盲目调极高会让 C 栈先溢出，正确做法是给递归补收敛基线或改成迭代。

`sys.settrace(fn)` 注册全局追踪函数，事件有 `'call'`、`'line'`、`'return'`、`'exception'`，局部追踪函数由 `'call'` 的返回值决定；

`sys.setprofile(fn)` 事件更粗（`call` / `return` / `c_call` / `c_return` / `c_exception`），适合做 profiler 与覆盖率。

两者只对当前线程生效，且每行、每次调用都回调 Python 函数，生产环境长期开启开销显著，用完必须 `sys.settrace(None)` / `sys.setprofile(None)` 关闭。

`sys.gettrace()` / `sys.getprofile()` 可查当前注册状态。

写覆盖率工具时，用 `'line'` 事件配合 `frame.f_lineno` 记录行号即可，不要试图通过写 `f_locals` 去改变程序状态。

```python
import sys

events = []
def profiler(frame, event, arg):
    if event in ('call', 'return'):
        events.append((event, frame.f_code.co_name))
def work(n):
    if n == 0:
        return 0
    return work(n - 1)
sys.setprofile(profiler)
work(2)
sys.setprofile(None)
print('call events present', sum(1 for e, _ in events if e == 'call') >= 3)
print('recursionlimit', sys.getrecursionlimit() > 0)
try:
    sys.setrecursionlimit(50)
    work(1000)
except RecursionError:
    print('RecursionError raised')
finally:
    sys.setrecursionlimit(1000)
```

<OutputBox title='原理验证' output='call events present True\nrecursionlimit True\nRecursionError raised' />


### 追踪、递归与生成器 API

**追踪、递归与生成器 API**

| API / 属性 | 行为 | 边界 |
| --- | --- | --- |
| sys.settrace / setprofile | call/line/return/exception 等事件回调 | 仅当前线程，长期开启开销大 |
| sys.gettrace / getprofile | 读当前注册状态 | 关闭后返回 None |
| sys.getrecursionlimit() | 默认 1000 | 超过抛 RecursionError |
| sys.setrecursionlimit(n) | 调整上限 | 调过高可能 C 栈溢出 |
| gi_frame | 生成器挂起时保留的帧 | 耗尽或关闭后置 None |
| inspect.getgeneratorstate | GEN_CREATED/RUNNING/SUSPENDED/CLOSED | 四态之一 |


## 生成器帧保留与 locals() 语义边界

普通函数返回后帧被销毁，局部变量随之消失；生成器把帧挂起而不是销毁：`gi_frame` 仍指向该帧，`f_lasti` 记住上次 `yield` 的位置，局部变量原样存活，`next()` 从断点继续。

`inspect.getgeneratorstate(g)` 返回 `GEN_CREATED` / `GEN_RUNNING` / `GEN_SUSPENDED` / `GEN_CLOSED` 四态之一，生成器耗尽或关闭后 `gi_frame` 被置为 `None`。

这正是惰性求值与协程能成立的物理基础，也解释了为什么生成器里的局部变量能跨多次 `next` 保留。`locals()` 的语义要按版本分层记：在函数里它返回独立快照字典，写入不改变局部变量；3.13 的 PEP 667 把 `frame.f_locals` 改成写透代理，写它会真正改变局部变量（3.12 及以前仍是快照）；

`globals()` 始终返回真实模块字典，修改立即生效。若业务确实需要「按名字改局部状态」，正确做法是直接赋值局部变量，或把状态放进一个可变容器（字典 / 对象属性）再改容器，不要依赖随版本翻转的 `f_locals` 行为。把 3.12 的快照结论套到 3.13，是写调试器与单测 mock 时最常见的误用。

```python
import inspect

def gen():
    a = 10
    yield a
    b = 20
    yield b
g = gen()
print('state created', inspect.getgeneratorstate(g))
print('first', next(g))
print('gi_frame kept', g.gi_frame is not None)
print('locals', sorted(g.gi_frame.f_locals))
print('state suspended', inspect.getgeneratorstate(g))
print('second', next(g))
try:
    next(g)
except StopIteration:
    print('third exhausted')
print('frame cleared', g.gi_frame is None)
```

<OutputBox title='对照写法：先自己猜，再点开' output='state created GEN_CREATED\nfirst 10\ngi_frame kept True\nlocals [&#39;a&#39;]\nstate suspended GEN_SUSPENDED\nsecond 20\nthird exhausted\nframe cleared True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import sys\n\nG = 0\ndef probe():\n    x = 1\n    snap = locals()\n    snap[&#39;x&#39;] = 50\n    print(&#39;locals snapshot&#39;, x == 1)\n    frame = sys._getframe()\n    frame.f_locals[&#39;x&#39;] = 99\n    print(&#39;f_locals writes through&#39;, x == 99)\n    print(&#39;names&#39;, sorted(frame.f_code.co_varnames))\n    print(&#39;globals is module&#39;, frame.f_globals is globals())\n    globals()[&#39;G&#39;] = 7\n    print(&#39;G changed&#39;, G == 7)\n    return frame.f_lasti &gt;= 0\nprint(&#39;result&#39;, probe())", "note": "帧对象：f_locals、f_globals、f_back 与属性查找"}, {"label": "对照 / 进阶", "code": "import inspect\n\ndef gen():\n    a = 10\n    yield a\n    b = 20\n    yield b\ng = gen()\nprint(&#39;state created&#39;, inspect.getgeneratorstate(g))\nprint(&#39;first&#39;, next(g))\nprint(&#39;gi_frame kept&#39;, g.gi_frame is not None)\nprint(&#39;locals&#39;, sorted(g.gi_frame.f_locals))\nprint(&#39;state suspended&#39;, inspect.getgeneratorstate(g))\nprint(&#39;second&#39;, next(g))\ntry:\n    next(g)\nexcept StopIteration:\n    print(&#39;third exhausted&#39;)\nprint(&#39;frame cleared&#39;, g.gi_frame is None)", "note": "调用栈、递归深度与 tracing 回调"}]' title='两种写法切换看' />

**locals() / globals() / f_locals 语义对照**

| 操作 | 对象 | 写入是否生效 | 说明 |
| --- | --- | --- | --- |
| locals()['x']=9 | 独立快照字典 | 否 | 所有版本写入都不回写 |
| frame.f_locals['x']=9 | 写透代理（3.13+） | 是（3.13+） | PEP 667 写入直达 fast locals；3.12 及以前是快照、否 |
| globals()['G']=7 | 真实模块字典 | 是 | LOAD_GLOBAL 直接读这份字典 |
| x = 9 | 局部变量绑定 | 是 | 直接改 fast locals |
| state['x']=9 | 可变容器 | 是 | 把状态放进字典再改容器 |

<Term word='帧对象与 f_locals / f_globals' text='每次 Python 函数调用都会创建一个执行帧，暴露为 frame 对象。常用属性：`f_code` 指向正在执行的 code object，`f_locals` 是局部命名空间的字典快照，`f_globals` 是模块全局字典，`f_builtins` 是内置命名空间，`f_back` 指向调用者帧（沿这条链往上就是…' />

<Term word='调用栈与递归深度' text='调用栈由帧的 `f_back` 链构成，异常对象的 `__traceback__` 也沿这条链记录每个帧与行号，traceback 模块打印的就是它。递归深度由 C 层计数与 `sys.getrecursionlimit()`（默认 1000）共同约束，超过抛 `RecursionError`…' />


## 用 sys.settrace 写一个最小行覆盖率收集器

覆盖率工具的核心不需要复杂框架：注册一个全局追踪函数，在 `'call'` 事件里为每个函数建一个行号集合并返回局部追踪函数，在 `'line'` 事件里把 `frame.f_lineno` 记进去，跑完目标函数后关闭追踪即可。

下面用标准库实现一个能区分分支的版本：`branch(x)` 根据 `x` 正负走不同 `return` 行，分别传入正负值后，检查记录到的行是否多于一行，并确认关闭后 `sys.gettrace()` 为 `None`。

要点是两个：追踪回调只在采样期间开启，以及用 `f_lineno` 而不是 `f_locals` 去观察执行状态。真实工具还会按文件过滤、合并多次运行、输出未覆盖行，但骨架就是 `'call'` 与 `'line'` 两个事件。

```python
import sys

coverage = {}
def tracer(frame, event, arg):
    if event == 'call':
        coverage.setdefault(frame.f_code.co_name, set())
        return tracer
    if event == 'line':
        coverage[frame.f_code.co_name].add(frame.f_lineno)
    return tracer

def branch(x):
    if x > 0:
        return 'positive'
    return 'non-positive'

sys.settrace(tracer)
branch(3)
branch(-1)
sys.settrace(None)
print('branch covered multiple lines', len(coverage.get('branch', ())) > 1)
print('trace disabled after', sys.gettrace() is None)
```

<Callout type="idea" title='落地提示' text='写 profiler、覆盖率工具、调试器时用 sys.setprofile / settrace；生产环境避免长期开启，开销与线程行为都要评估' />

<CheckList id='P051b' title='上线前自检' :items='["能复现并解释「在帧里改 locals() 期待改变局部变量，或把 3.12…」", "能复现并解释「生产服务长期开启 sys.settrace / setpro…」", "能复现并解释「递归爆栈后盲目把 setrecursionlimit 调到极…」", "能用一条命令验证 帧对象与 f_locals / f_globals", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import dis; dis.dis(lambda x: x+1)"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 帧对象与 f_locals / f_globals 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 在帧里改 locals() 期待改变局部变量，或把 3.12 的 f_locals 快照结论套到 3.13 | locals() 始终是独立快照，写入不回写；3.13 的 PEP 667 却把 frame.f_locals 改成写透代理，写入直接改局部变量，行为随版本翻转 | 直接赋值局部变量，或把状态放进可变容器再改容器；跨版本代码不要把 f_locals 当可写命名空间，只用于读取观察 |
| 生产服务长期开启 sys.settrace / setprofile | 每行、每次调用都要回调 Python 函数，p99 延迟上升，且只对当前线程生效 | 仅调试或覆盖率采样时短时开启，用完 settrace(None) / setprofile(None) 关闭；性能剖析改用采样 profiler |
| 递归爆栈后盲目把 setrecursionlimit 调到极高 | 上限抬高后可能先耗尽 C 栈导致解释器崩溃，而不是安全返回 | 给递归补收敛基线或改成迭代，必要时小幅上调并压测；RecursionError 应作为设计信号而非调参对象 |

<Callout type="warn" title='本讲最容易踩的坑' text='在帧里改 locals() 期待改变局部变量，或把 3.12 的 f_locals 快照结论套到 3.13：locals() 始终是独立快照，写入不回写；3.13 的 PEP 667 却把 frame.f_locals 改成写透代理，写入直接改局部变量，行为随版本翻转' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：在帧里改 locals() 期待改变局部变量…", "body": "locals() 始终是独立快照，写入不回写；3.13 的 PEP 667 却把 frame.f_locals 改成写透代理，写入直接改局部变量，行为随版本翻转", "tip": "直接赋值局部变量，或把状态放进可变容器再改容器；跨版本代码不要把 f_locals 当可写命名空间，只用于读取观察"}, {"title": "第 2 步：生产服务长期开启 sys.settrace…", "body": "每行、每次调用都要回调 Python 函数，p99 延迟上升，且只对当前线程生效", "tip": "仅调试或覆盖率采样时短时开启，用完 settrace(None) / setprofile(None) 关闭；性能剖析改用采样 profiler"}, {"title": "第 3 步：递归爆栈后盲目把 setrecursionl…", "body": "上限抬高后可能先耗尽 C 栈导致解释器崩溃，而不是安全返回", "tip": "给递归补收敛基线或改成迭代，必要时小幅上调并压测；RecursionError 应作为设计信号而非调参对象"}]' />

<FlowTimeline :steps='[{"title": "帧对象：f_locals、f_globals、f…", "desc": "每次 Python 函数调用都会创建一个执行帧，暴露为 frame 对象。常用属性…", "tone": "blue"}, {"title": "调用栈、递归深度与 tracing 回调", "desc": "调用栈由帧的 `f_back` 链构成，异常对象的 `__traceback__`…", "tone": "purple"}, {"title": "生成器帧保留与 locals() 语义边界", "desc": "普通函数返回后帧被销毁，局部变量随之消失；生成器把帧挂起而不是销毁…", "tone": "orange"}, {"title": "工程落地", "desc": "用 sys.settrace 写一个最小行覆盖率收集器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 看得见调用栈

<Exercise title='基础：验证 globals() 写回而 locals() 不写回' task='在函数里分别 globals()[&#39;G&#39;]=v 与 locals()[&#39;x&#39;]=v，打印全局 G 与局部 x，解释两者差异的底层原因。' solution='G = 0\ndef f():\n    x = 1\n    globals()[&#39;G&#39;] = 5\n    locals()[&#39;x&#39;] = 9\n    print(&#39;G&#39;, G, &#39;x&#39;, x)\nf()' explain='globals() 返回真实模块字典，写入立即被 LOAD_GLOBAL 读到；locals() 只是 fast locals 数组的快照字典，写它不影响局部绑定，x 仍为 1。' />

<Exercise title='进阶：用 getgeneratorstate 观察帧挂起与释放' task='写含两个 yield 的生成器，依次打印创建态、首次 next 后的 gi_frame 是否保留、f_locals 里的变量、挂起态、耗尽后 gi_frame 是否为 None。' solution='import inspect\ndef g():\n    a = 1\n    yield a\n    b = 2\n    yield b\nit = g()\nprint(inspect.getgeneratorstate(it), next(it))\nprint(it.gi_frame is not None, sorted(it.gi_frame.f_locals), inspect.getgeneratorstate(it))\nnext(it)\nprint(it.gi_frame is None, inspect.getgeneratorstate(it))' explain='GEN_CREATED 时还未执行；首次 next 后帧挂起保留、f_locals 含 a、状态 GEN_SUSPENDED；耗尽后 gi_frame 置 None、状态 GEN_CLOSED，局部变量随帧释放。' />

<Quiz no='051-1' q='关于 3.13 里 frame.f_locals 与 locals() 的写入语义，正确的是？' :options='["frame.f_locals 是写透代理，写入影响局部变量；locals() 仍是独立快照，写入不回写", "两者都是快照，写入都不回写", "两者都可写且都改变局部变量", "frame.f_locals 只读，locals() 可写"]' answer="0" explain='3.13 的 PEP 667 把 frame.f_locals 改成写透代理，写它等于改 fast locals；locals() 保持返回独立快照。3.12 及以前两者都是快照、写入都不生效，因此跨版本代码不要依赖 f_locals 的写入语义。' />

<Quiz no='051-2' q='关于 sys.settrace / setprofile，正确的是？' :options='["仅对当前线程生效，每行或每次调用都回调，生产不宜长期开启", "对所有线程全局生效，开销可忽略", "会自动优化掉未使用的行事件", "开启后不影响性能"]' answer="0" explain='追踪回调是逐事件触发的 Python 函数，事件密度高、开销明显，且只对当前线程有效；用完必须置 None 关闭，性能剖析宜用采样 profiler。' />

<Quiz no='051-3' q='生成器为什么能在多次 next 之间保留局部变量？' :options='["帧被挂起而非销毁，gi_frame 与 f_lasti 保留执行状态", "局部变量被复制到全局字典", "每次 next 重新执行整个函数", "闭包 cell 保存了所有值"]' answer="0" explain='生成器挂起时帧保留，gi_frame 指向该帧、f_lasti 记住断点、局部变量存活；耗尽或关闭后帧释放、gi_frame 置 None。这是惰性求值的物理基础。' />

<Predict no='051-4' q='递归超过 sys.getrecursionlimit() 后，最可能发生什么？' :options='["抛 RecursionError: maximum recursion depth exceeded", "自动改用迭代", "静默返回 0"]' answer='0' output='RecursionError: maximum recursion depth exceeded' explain='C 层递归计数达到 getrecursionlimit()（默认 1000）即抛 RecursionError。把它当设计信号补收敛基线，而不是盲目把上限调到极高导致 C 栈溢出。' />

<FillBlank no='051-5' tpl='___ sys' :answers='["import"]' hint='回想本讲关于 帧对象与 f_locals / f_globals 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 帧对象：f_locals、f_globals、f_back 与属性查找 的落点。' />

<KnowledgeCard :points='["帧属性：f_code / f_locals / f_globals / f_back / f_lasti / f_lineno / f_trace", "f_globals 与 globals() 是同一份真实字典，写入生效；locals() 是独立快照，写入不回写", "3.13 PEP 667 把 frame.f_locals 改成写透代理（写入生效），3.12 及以前仍是快照；3.11 起帧内联为 _PyInterpreterFrame", "调用栈是 f_back 链，traceback 沿链记录帧与行号；递归超限抛 RecursionError", "settrace 有 call/line/return/exception，setprofile 更粗；仅当前线程、开销大，用完置 None", "生成器挂起时 gi_frame 保留局部变量与 f_lasti，耗尽后置 None；getgeneratorstate 有四态"]' :pitfalls='["在帧里改 locals() 期待改变局部变量，或把 3.12 的 f_locals 快照结论套到 3.13", "生产服务长期开启 sys.settrace / setprofile", "递归爆栈后盲目把 setrecursionlimit 调到极高", "在帧里修改 locals() 字典期待改变局部变量，在多数实现里不会生效"]' summary='每次函数调用都创建一个帧，生成器把帧挂起而不是销毁，这是惰性求值与协程能成立的物理基础' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 帧属性：f_code / f_locals / f_globals / f_back / f_lasti / f_lineno / f_trace | 建立直觉 |
| f_globals 与 globals() 是同一份真实字典，写入生效；locals() 是独立快照，写入不回写 | 跑通示例 |
| 3.13 PEP 667 把 frame.f_locals 改成写透代理（写入生效），3.12 及以前仍是快照；3.11 起帧内联为 _PyInterpreterFrame | 深入边界 |
| 调用栈是 f_back 链，traceback 沿链记录帧与行号；递归超限抛 RecursionError | 工程落地 |
| settrace 有 call/line/return/exception，setprofile 更粗；仅当前线程、开销大，用完置 None | 随堂检测 |
| 生成器挂起时 gi_frame 保留局部变量与 f_lasti，耗尽后置 None；getgeneratorstate 有四态 | 复盘 |

1. 帧属性：f_code / f_locals / f_globals / f_back / f_lasti / f_lineno / f_trace

2. f_globals 与 globals() 是同一份真实字典，写入生效；locals() 是独立快照，写入不回写

3. 3.13 PEP 667 把 frame.f_locals 改成写透代理（写入生效），3.12 及以前仍是快照；3.11 起帧内联为 _PyInterpreterFrame

[下一讲：对象内存布局、引用计数与小对象池](/core/memory)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/051-frames.py`

```bash
python3 examples/lessons/051-frames.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/051-frames.py) · [全部示例代码索引](/examples/)
