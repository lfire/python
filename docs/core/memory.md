---
title: 第 052 讲 · 对象内存布局、引用计数与小对象池
description: 能估算对象开销并定位内存问题
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='40 分钟' goal='能估算对象开销并定位内存问题' prereq='第 051 讲 · 帧、调用栈与命名空间' />

# 第 052 讲 · 对象内存布局、引用计数与小对象池

上一讲看执行上下文，这一讲把镜头对准对象内存布局：整数、列表、实例占多少内存，又凭什么被及时回收。这是第 6 讲「一切皆对象」轻轻带过、现在该补的一笔。

一个图服务用 `sys.getsizeof` 乘节点数做容量规划，结果比线上小了近一半。本讲先从 `PyObject` 头与引用计数归零即释放讲起，再看小整数池与字符串驻留怎样让身份比较不稳，最后说 `sys.getsizeof` 与 `tracemalloc` 的观测边界。需要第 6 讲的对象模型、`id` 与 `is` 及第 43 讲的 `__slots__`；学完你能估算对象开销，也为下一讲埋好线索。


## 一个 getsizeof 加起来和监控对不上的内存报告

一个图服务把节点存成普通 `dict`，容量规划时用 `sys.getsizeof(dict)` 乘节点数，估算结果比线上实际占用小了近一半，扩容方案直接做错——`getsizeof` 只看对象结构体本身，算不到字典里字符串键、值对象与哈希表的真实分配。

另一处 bug 更典型：代码里用 `is` 判断两个运行时计算出的整数是否相等，测试环境偶尔通过、上线后某些数据分支判等失败，因为小整数被缓存复用、大整数每次新建，身份比较结果随创建方式变化。还有人给缓存做优化，把字符串键用 `sys.intern` 驻留，却说不清它到底省了什么。

CPython 的对象内存布局、引用计数与小对象池决定了这些行为。本讲把 `PyObject` 头、引用计数增减时机、小整数池与字符串驻留、pymalloc 分级分配，以及 `getsizeof` 与 `tracemalloc` 的观测边界逐条对齐，让内存结论能被算出来也能被测出来。

<Callout type="warn" title='先看一个真实会出错的写法' text='用 sys.getsizeof 估算容器加全部元素的总内存：getsizeof 只返回浅层对象大小加 GC 头，算不到列表/字典里引用的元素对象与 pymalloc 碎片' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段五 · 核心机制与运行时 |
| 前置 | 第 051 讲 · 帧、调用栈与命名空间 |
| 难度 / 建议时长 | ★★★★☆ · 40 分钟 |
| 本讲新增 | PyObject 头与 ob_refcnt、引用计数增减时机、小整数与字符串驻留 |
| 一句话目标 | 能估算对象开销并定位内存问题 |
| 为下一讲铺垫 | 分代 GC、循环引用与 weakref |


## PyObject 头、引用计数与归零即释放

CPython 里每个对象都以 `PyObject` 开头：`ob_refcnt`（`Py_ssize_t`，64 位下 8 字节）记录引用数，`ob_type` 指针（8 字节）指向类型对象；变长对象（`PyVarObject`）再加 `ob_size`。

被 GC 跟踪的容器对象前面还有 `PyGC_Head`（双向链表指针加状态，通常 16 字节），`sys.getsizeof` 会把它算进去。

引用计数是最主要的回收机制：`Py_INCREF` / `Py_DECREF` 在赋值、传参、容器存取、属性绑定、名字离开作用域、`del` 时被大量调用，计数归零立刻触发 `tp_dealloc` 释放对象，并可能级联释放它引用的其它对象。

好处是回收时机可预测、无长时间停顿；代价是每次绑定都要改计数，为使这些操作不加细粒度锁，解释器用一把 GIL 保护整个执行状态（第 54 讲），且纯引用计数无法回收循环引用（第 53 讲由分代 GC 兜底）。

`sys.getrefcount(obj)` 可读当前计数，但返回值比实际多 1，因为作为参数传入时临时增加了一个引用；用它做增减趋势对比即可，别把绝对值当精确值。

```python
import sys

a = 256
b = 256
print('small int pooled', a is b)
x = int('257')
y = int('257')
print('runtime int distinct', x is y)
print('getrefcount extra', sys.getrefcount(x) > 0)
s1 = sys.intern('cache_key_12345')
s2 = sys.intern('cache_key_12345')
print('interned same', s1 is s2)
print('sizeof empty list', sys.getsizeof([]) > 0)
```

<OutputBox title='主示例运行结果' output='small int pooled True\nruntime int distinct False\ngetrefcount extra True\ninterned same True\nsizeof empty list True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys\n\na = 256\nb = 256\nprint(&#39;small int pooled&#39;, a is b)\nx = int(&#39;257&#39;)\ny = int(&#39;257&#39;)\nprint(&#39;runtime int distinct&#39;, x is y)\nprint(&#39;getrefcount extra&#39;, sys.getrefcount(x) &gt; 0)\ns1 = sys.intern(&#39;cache_key_12345&#39;)\ns2 = sys.intern(&#39;cache_key_12345&#39;)\nprint(&#39;interned same&#39;, s1 is s2)\nprint(&#39;sizeof empty list&#39;, sys.getsizeof([]) &gt; 0)' :notes='["导入 sys，读取引用计数与对象大小", "空行，只用于分隔逻辑块，不影响执行结果。", "空行分隔导入与验证代码", "256 落在 CPython 小整数池 -5..256 内", "同名常量还会在 co_consts 里复用", "池内对象被复用，身份比较为 True", "用 int() 在运行时创建大整数，绕开小整数池", "第二次调用生成另一个独立对象", "大整数不池化，is 比较为 False", "getrefcount 含参数临时引用，这里只验证可读取", "sys.intern 把字符串放进全局驻留表", "同一内容再次驻留返回同一对象", "驻留成功，身份比较为 True"]' title='第 052 讲 · 对象内存布局、引用计数与小对象池' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='CPython 里每个对象都以 `PyObject` 开头：`ob_refcnt`（`Py_ssize_t`，64 位下 8 字节）记录引用数，`ob_type` 指针（8 字节）指向类型对象；变长对象（`PyVarObject`）再加 `ob_size`。被 GC 跟踪的容器对象前面还有…' />

**PyObject 头与常见浅层大小来源（64 位 CPython）**

| 组成 | 内容 | 是否计入 getsizeof |
| --- | --- | --- |
| ob_refcnt | Py_ssize_t 引用计数，8 字节 | 计入对象基础头 |
| ob_type | 指向类型对象的指针，8 字节 | 计入对象基础头 |
| ob_size | PyVarObject 的元素个数 | 变长对象计入 |
| PyGC_Head | GC 链表指针与状态，约 16 字节 | 被 GC 跟踪的对象计入 |
| 容器元素 | 列表/字典里引用的其它对象 | 不计入，需另算 |
| pymalloc 碎片 | arena/pool 中未归还的空闲 block | 完全不计入 |

CPython 把每个值表示为堆上的 `PyObject`：头部 `ob_refcnt` 与 `ob_type` 分别承担引用计数与类型分派，变长对象再加 `ob_size`，被 GC 跟踪的容器还带 `PyGC_Head`。

引用计数通过 `Py_INCREF` / `Py_DECREF` 在赋值、传参、容器存取与作用域退出时增减，归零立即调用 `tp_dealloc`，行为可预测但挡不住循环引用，且这些计数操作需要 GIL 保护。

为降低小对象分配成本，pymalloc 把 ≤512 字节请求按 size class 从 arena（256KB）→ pool（4KB）→ block 三级结构分配并复用，释放后内存常留在 pool 里不立刻归还系统。

小整数池（-5..256）与字符串驻留都是这套对象模型上的复用优化：前者启动时预分配，后者把常量与标识符放进全局表以加速字典键比较。

`sys.getsizeof` 走 `__sizeof__` 加 GC 头，只反映浅层结构；`tracemalloc` 在 PyMem 分配器层记账，能测到容器元素、字符串内容与真实增量，因此「估算内存」必须区分这两层。

<ConceptDiagram type='layers3' title='第 052 讲 · PyObject 头、引用计数与归零即释放' labels='PyObject 头、引用计数与归零即释放|小整数池、字符串驻留与 is 的正确用法|pymalloc、getsizeof 的局限…|tracemalloc' caption='能估算对象开销并定位内存问题' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 小整数池、字符串驻留与 is 的正确用法

CPython 在启动时预分配 -5 到 256 的小整数对象并复用，因此 `a = 256; b = 256` 时 `a is b` 为 `True`；这是实现细节，不是语言规范，PyPy 等实现不保证。

编译期常量还会被合并进同一个 `co_consts` 槽，进一步让字面量复用。运行时通过 `int('257')` 之类创建的大整数不在池里，两次调用得到不同对象，`is` 比较为 `False`。

字符串驻留（intern）把标识符样式的字符串与编译期常量放进全局驻留表，字典键比较时可先比指针再比内容，省掉逐字符比较；`sys.intern(s)` 手动驻留，适合大量重复的键（如日志字段名、枚举值）。但驻留表本身持有强引用，滥驻留用户输入的任意字符串会让它们一直存活，反而造成内存问题。

由此得出明确规则：值相等一律用 `==`，只有判断 `None` / `True` / `False` 这类单例，或确实要验证「是不是同一个对象」时才用 `is`。把 `is` 用在整数或运行时字符串上，结果会随池化、驻留、常量合并与创建方式飘移，是典型的偶发 bug。

```python
import sys, tracemalloc

items = [str(i) for i in range(1000)]
print('list header', sys.getsizeof(items) > 0)
print('element size', sys.getsizeof(items[0]) > 0)
tracemalloc.start()
before = tracemalloc.take_snapshot()
more = [str(i) for i in range(1000)]
after = tracemalloc.take_snapshot()
diff = sum(s.size_diff for s in after.compare_to(before, 'filename') if s.size_diff > 0)
print('tracemalloc sees growth', diff > 0)
tracemalloc.stop()
```

<OutputBox title='对照写法：先自己猜，再点开' output='list header True\nelement size True\ntracemalloc sees growth True' guess="true" />

```python
import sys

obj = object()
before = sys.getrefcount(obj)
holder = [obj]
during = sys.getrefcount(obj)
del holder
after = sys.getrefcount(obj)
print('alias increments', during > before)
print('del decrements', after < during)
print('back to base', after == before)
```

<OutputBox title='原理验证' output='alias increments True\ndel decrements True\nback to base True' />


## pymalloc、getsizeof 的局限与 tracemalloc 的正确观测

pymalloc 是 CPython 针对小对象的专用分配器：不超过 512 字节的请求不走通用 `malloc`，而是按 size class 从 arena（256KB）→ pool（4KB）→ block 三级结构里取，减少系统调用与内存碎片，同规格对象还能复用刚释放的 block。

这意味着「释放一个对象」不一定把内存立刻还给操作系统，resident 内存短期不降并不等于泄漏。`sys.getsizeof` 调用对象的 `__sizeof__` 并加上 GC 头，返回的是浅层大小：列表只算列表结构体与其指针数组，不含列表里引用的元素对象；字符串因为字符数据内联，这一项会含字符内容。

用它估算「容器加全部元素」几乎一定偏小。

`tracemalloc` 挂钩到 PyMem 分配器层，`start()` 后用 `get_traced_memory()` 取当前净分配与峰值两个量，用 `take_snapshot()` 与 `compare_to()` 按文件名、行号看增量，才是可核对的真实分配。

工程结论：容量规划与泄漏排查用 `tracemalloc` 或进程常驻内存，`getsizeof` 只用于说明单个对象的结构开销；海量小对象用 `__slots__`、`array` 或列式存储换布局（第 43 讲）。

<Compare :panels='[{"label": "主示例", "code": "import sys\n\na = 256\nb = 256\nprint(&#39;small int pooled&#39;, a is b)\nx = int(&#39;257&#39;)\ny = int(&#39;257&#39;)\nprint(&#39;runtime int distinct&#39;, x is y)\nprint(&#39;getrefcount extra&#39;, sys.getrefcount(x) &gt; 0)\ns1 = sys.intern(&#39;cache_key_12345&#39;)\ns2 = sys.intern(&#39;cache_key_12345&#39;)\nprint(&#39;interned same&#39;, s1 is s2)\nprint(&#39;sizeof empty list&#39;, sys.getsizeof([]) &gt; 0)", "note": "PyObject 头、引用计数与归零即释放"}, {"label": "对照 / 进阶", "code": "import sys, tracemalloc\n\nitems = [str(i) for i in range(1000)]\nprint(&#39;list header&#39;, sys.getsizeof(items) &gt; 0)\nprint(&#39;element size&#39;, sys.getsizeof(items[0]) &gt; 0)\ntracemalloc.start()\nbefore = tracemalloc.take_snapshot()\nmore = [str(i) for i in range(1000)]\nafter = tracemalloc.take_snapshot()\ndiff = sum(s.size_diff for s in after.compare_to(before, &#39;filename&#39;) if s.size_diff &gt; 0)\nprint(&#39;tracemalloc sees growth&#39;, diff &gt; 0)\ntracemalloc.stop()", "note": "小整数池、字符串驻留与 is 的正确用法"}]' title='两种写法对照' note='差异集中在 PyObject 头与 ob_refcnt；先看输出，再找背后的规则。' />

**引用计数增减时机**

| 时机 | 计数变化 | 说明 |
| --- | --- | --- |
| 赋值 name = obj | +1 | 名字绑定到对象 |
| 传参 / 返回 | +1 后 -1 | 调用期间临时引用 |
| 容器 append / 字典存值 | +1 | 容器持有强引用 |
| del name / 离开作用域 | -1 | 最后一个引用消失即释放 |
| sys.getrefcount(obj) | 临时 +1 | 返回值比实际多 1 |
| 循环引用 | 不归零 | 需分代 GC 兜底 |

**小整数池 / 驻留 / 观测工具对照**

| 机制或工具 | 行为 | 适用 / 边界 |
| --- | --- | --- |
| 小整数池 -5..256 | 预先分配并复用 | CPython 实现细节，值比较仍用 == |
| 字符串驻留 | 标识符与常量进全局表 | sys.intern 手动驻留，别驻留任意用户输入 |
| sys.getsizeof | 浅层对象大小加 GC 头 | 不含容器元素与碎片 |
| tracemalloc | 挂钩 PyMem 的净分配与快照差分 | 容量规划与泄漏定位 |
| pymalloc | ≤512 字节走 arena/pool/block | 释放后内存可能暂不归还 OS |
| __slots__ / array | 改布局省掉字典或对象开销 | 海量小对象优先 |

<Term word='PyObject 头与 ob_refcnt' text='CPython 里每个对象都以 `PyObject` 开头：`ob_refcnt`（`Py_ssize_t`，64 位下 8 字节）记录引用数，`ob_type` 指针（8 字节）指向类型对象；变长对象（`PyVarObject`）再加 `ob_size`。被 GC 跟踪的容器对象前面还有 `PyGC_Head`（双向…' />

<Term word='引用计数增减时机' text='CPython 在启动时预分配 -5 到 256 的小整数对象并复用，因此 `a = 256; b = 256` 时 `a is b` 为 `True`；这是实现细节，不是语言规范，PyPy 等实现不保证。编译期常量还会被合并进同一个 `co_consts` 槽，进一步让字面量复用。运行时通过 `int(&#39;257&#39;)`…' />


## 用 tracemalloc 量化 list-of-dict 与 NamedTuple 的真实占用

事件流水常有两种建模：每条记录一个字典，或用 `NamedTuple` / slots 类做固定字段。字典灵活但每个元素都带一张哈希表与字符串键，`NamedTuple` 是紧凑元组，字段共享一份名字。

用 `sys.getsizeof` 只能看到列表头，看不出元素差异；用 `tracemalloc` 分别构造两万条记录并比较净分配字节，才能得出可核对的结论。

下面用标准库跑通：构造 `dict` 版与 `NamedTuple` 版，比较两次 `get_traced_memory` 的当前值，并打印 `Point._fields` 确认字段定义。

要点是观测工具要落在分配器层，且结论用相对比较而非写死随版本变化的字节数。真实系统还可进一步换成 `array` 或列式存储。

```python
import tracemalloc
from collections import namedtuple

Point = namedtuple('Point', 'x y')
tracemalloc.start()
def build_dict(n):
    return [{'x': i, 'y': i * 2} for i in range(n)]
def build_tuple(n):
    return [Point(i, i * 2) for i in range(n)]

d = build_dict(20000)
dict_mem = tracemalloc.get_traced_memory()[0]
del d
t = build_tuple(20000)
tuple_mem = tracemalloc.get_traced_memory()[0]
print('dict heavier', dict_mem > tuple_mem)
print('both positive', dict_mem > 0 and tuple_mem > 0)
print('point fields', Point._fields)
tracemalloc.stop()
```

<Callout type="idea" title='落地提示' text='做容量规划用 tracemalloc 看真实分配，海量小对象用 slots / array / NumPy 换布局' />

<CheckList id='P052a' title='上线前自检' :items='["能复现并解释「用 sys.getsizeof 估算容器加全部元素的总内存」", "能复现并解释「用 is 比较大整数或运行时字符串」", "能复现并解释「以为引用计数能回收循环引用」", "能用一条命令验证 PyObject 头与 ob_refcnt", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import sys, gc; print(sys.getsizeof([1,2,3]), gc.get_count())"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 PyObject 头与 ob_refcnt 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 sys.getsizeof 估算容器加全部元素的总内存 | getsizeof 只返回浅层对象大小加 GC 头，算不到列表/字典里引用的元素对象与 pymalloc 碎片 | 用 tracemalloc.start() 后 get_traced_memory() 或 take_snapshot().compare_to() 看真实分配与增量 |
| 用 is 比较大整数或运行时字符串 | 小整数池、常量合并与字符串驻留会让身份随创建方式变化，结果不稳定 | 值相等一律用 ==；只有判断 None / True / False 单例，或确实要验证对象身份时才用 is |
| 以为引用计数能回收循环引用 | 互相引用的对象 ob_refcnt 至少为 1，归零条件永不满足 | 用 weakref 断开环或由分代 GC 兜底（第 53 讲）；缓存不要长期持有强引用 |

<Callout type="warn" title='本讲最容易踩的坑' text='用 sys.getsizeof 估算容器加全部元素的总内存：getsizeof 只返回浅层对象大小加 GC 头，算不到列表/字典里引用的元素对象与 pymalloc 碎片' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 sys.getsizeof 估算容器加全…", "body": "getsizeof 只返回浅层对象大小加 GC 头，算不到列表/字典里引用的元素对象与 pymalloc 碎片", "tip": "用 tracemalloc.start() 后 get_traced_memory() 或 take_snapshot().compare_to() 看真实分配与增量"}, {"title": "第 2 步：用 is 比较大整数或运行时字符串", "body": "小整数池、常量合并与字符串驻留会让身份随创建方式变化，结果不稳定", "tip": "值相等一律用 ==；只有判断 None / True / False 单例，或确实要验证对象身份时才用 is"}, {"title": "第 3 步：以为引用计数能回收循环引用", "body": "互相引用的对象 ob_refcnt 至少为 1，归零条件永不满足", "tip": "用 weakref 断开环或由分代 GC 兜底（第 53 讲）；缓存不要长期持有强引用"}]' />

<FlowTimeline :steps='[{"title": "PyObject 头、引用计数与归零即释放", "desc": "CPython 里每个对象都以 `PyObject` 开头：`ob_refcnt`…", "tone": "blue"}, {"title": "小整数池、字符串驻留与 is 的正确用法", "desc": "CPython 在启动时预分配 -5 到 256 的小整数对象并复用，因此…", "tone": "purple"}, {"title": "pymalloc、getsizeof 的局限与…", "desc": "pymalloc 是 CPython 针对小对象的专用分配器：不超过 512 字节的…", "tone": "orange"}, {"title": "工程落地", "desc": "用 tracemalloc 量化 list-of-dict 与 Na…", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## Include/object.h 与 PEP 683 的 immortal 对象

正文讲 PyObject 头里 ob_refcnt 会因赋值与传参频繁增减，3.12 起这条规律被 PEP 683 改写了一半。

`Include/object.h` 里 PyObject 仍是 ob_refcnt（Py_ssize_t）加 ob_type 指针，但解释器给静态分配的单例设了一个哨兵值 _Py_IMMORTAL_REFCNT；`Include/internal/pycore_object.h` 的 _Py_IsImmortal 用引用计数的低位标记判断，Py_INCREF / Py_DECREF 命中就整段跳过，不再做写操作。

被标记的对象包括 None、True、False、小整数池、编译期驻留的字符串与静态类型对象，本机 3.13 实测 `sys.getrefcount(None)` 返回 4294967295，而运行时新建的 1000 只有几个引用，两者一眼可分。

这个改动的动机不是省几条指令：多核上几十个线程同时给 None 加引用会让同一缓存行反复失效，immortal 把这类写彻底消除，是 PEP 703 自由线程构建能拆掉 GIL 的前置条件之一。

推导出的副作用有两条：tp_dealloc 遇到 immortal 直接返回，归零即释放对这批对象不成立；`sys.getrefcount` 对它们返回的是一个固定的大数而不是真实引用数，做引用计数趋势分析时要先把单例排除。

驻留字符串也因此更该谨慎：`sys.intern` 把用户串塞进全局表，在 3.12+ 还可能被顺带标记，生命周期直接拉到进程结束。

<Term word='_Py_IMMORTAL_REFCNT' text='PEP 683 给静态单例（None、True、小整数、驻留字符串、静态类型）设的引用计数哨兵；Py_INCREF / Py_DECREF 命中该标记就跳过写操作，从而消除多线程对同一单例的缓存行争用，也是自由线程构建能去掉 GIL 的前提之一。' />


## 紧凑字典的 split table 与 getsizeof 台阶

```python
import sys

prev = None
steps = []
for n in range(0, 33):
    size = sys.getsizeof([None] * n)
    if size != prev:
        steps.append((n, size))
        prev = size
print('list steps', steps[:6])
print('dict empty', sys.getsizeof({}))
print('dict 6', sys.getsizeof(dict.fromkeys(range(6))))
print('immortal None', sys.getrefcount(None) > 1000000)
print('mortal 1000', sys.getrefcount(1000) < 100)

```

<OutputBox title='扩展示例运行结果' output='list steps [(0, 56), (1, 64), (2, 72), (3, 80), (4, 88), (5, 96)]\ndict empty 64\ndict 6 352\nimmortal None True\nmortal 1000 True' />

<LineByLine code='import sys\n\nprev = None\nsteps = []\nfor n in range(0, 33):\n    size = sys.getsizeof([None] * n)\n    if size != prev:\n        steps.append((n, size))\n        prev = size\nprint(&#39;list steps&#39;, steps[:6])\nprint(&#39;dict empty&#39;, sys.getsizeof({}))\nprint(&#39;dict 6&#39;, sys.getsizeof(dict.fromkeys(range(6))))\nprint(&#39;immortal None&#39;, sys.getrefcount(None) &gt; 1000000)\nprint(&#39;mortal 1000&#39;, sys.getrefcount(1000) &lt; 100)\n' :notes='["导入 sys，后面用 getsizeof 看浅层结构、用 getrefcount 看引用计数。", "空行，只用于分隔逻辑块，不影响执行结果。", "记录上一次的尺寸，起点设 None 保证第一次一定被记下。", "用列表收集尺寸发生变化的「台阶」。", "逐个检查 0 到 32 个元素的 list，观察指针数组何时扩容。", "sys.getsizeof 只返回 list 结构体加指针数组的浅层大小，不含元素对象。", "只在新尺寸与上次不同时记录，跳过重复值。", "把 (元素数, 字节数) 存成元组，一个台阶一条。", "更新上一次尺寸，供下一轮比较。", "打印前六个台阶，3.13 上大致是每多一个指针加 8 字节，也说明扩容按块而不是逐个。", "空 dict 的浅层尺寸，不含任何键值对象。", "六个键的 dict 尺寸，紧凑表的索引数组与条目数组都算在内，与空 dict 拉开差距。", "PEP 683 把 None 标成 immortal，getrefcount 返回一个固定大数，用大于一百万判断即可。", "运行时新建的 1000 仍是普通引用计数，数值很小，与上一条形成对照。", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />

**getsizeof 的观测边界按对象布局分类**

| 对象 | 内联数据 | 是否计入元素对象 | 结构定义位置 |
| --- | --- | --- | --- |
| list | ob_item 指针数组 | 否 | Include/cpython/listobject.h |
| dict | 紧凑表 ma_keys 与 ma_values | 否 | Include/cpython/dictobject.h |
| str | 字符数据内联在对象尾部 | 是 | Include/cpython/unicodeobject.h |
| int | ob_digit 数组内联 | 是 | Include/cpython/longintrepr.h |
| set | setentry 数组 | 否 | Include/cpython/setobject.h |
| tuple | ob_item 指针数组内联 | 否 | Include/cpython/tupleobject.h |


## obmalloc.c 的 size class 与 freelist 双层缓存

`Objects/obmalloc.c` 把不超过 `SMALL_REQUEST_THRESHOLD`（512 字节）的请求按 `ALIGNMENT` 向上取整成 size class，从 arena（256 KiB）切成 pool（4 KiB）再切成 block：闲置 pool 挂在 usable_pools 链表，全空的 arena 可以被单独 free 归还操作系统（3.8 起）。

所以释放了对象往往只是把 block 还给 pool，进程 RSS 短期不降是常态而非泄漏。

更上面还有第二层缓存：`Objects/listobject.c` 的 PyList_MAXFREELIST（80 个）、tuple 的 PyTuple_MAXFREELIST（按长度分桶共 2000 个）、float 的 PyFloat_MAXFREELIST（100 个）以及 dict、生成器对象，它们的 tp_dealloc 不把内存交回分配器，而是把空壳挂进类型级 free list，下一次 PyList_New / PyTuple_New 直接复用。

两层叠加解释了两个观测现象：tracemalloc 挂在 PyMem 层，free list 里的空闲对象不算已分配，快照看不到它们，但它们确实占着 RSS；`PYTHONMALLOC=malloc` 关掉 pymalloc 后 RSS 曲线会明显不同，这本身就是验证分配器行为的手段。

工程结论：查泄漏看 RSS 与 tracemalloc 快照的行号增量，别用 getsizeof 或引用计数推断；想让内存尽快回落到系统，要么减少短命小对象，要么把布局换成 `__slots__` / array / 列式缓冲，让分配落在少数大块上。

<ConceptDiagram type='flow4' title='第 052 讲 · 扩展图解' labels='PyObject 头|size class 的 block|pool 4KiB|arena 256KiB' caption='小对象从 arena 逐级切到 block；对象释放后先回 pool，再可能进类型 freelist，最后才可能整块 arena 归还操作系统。' />

图服务那次扩容事故值得完整复算一遍：容量规划用 `sys.getsizeof(nodes)` 乘以节点数，其中 nodes 是一个装着 2000 个字典的 dict，getsizeof 只返回顶层字典的哈希表结构体，既不算 2000 个键字符串，也不算每个值字典、里面的整数与 tags 列表，估算因此比真实占用小了近一半。

tracemalloc 挂钩在 PyMem 分配器上，`start()` 后用 `get_traced_memory()` 取净分配字节，在同一批次前后取差值，才是这次分配真正向分配器要走的量。

下面这段代码在 2000 个节点上同时给出浅层大小与实际增长的对照：浅层约 5 万字节，实际增长约 70 万字节，量级差到十几倍。这里的判据不是某个固定倍数，而是浅层大小是否覆盖元素对象，只要容器里还引用着别的对象，getsizeof 就必然偏低。

报告里应同时记录 `tracemalloc.start(nframe)` 的回溯层数、窗口时长与 Top-N 分配行，让下次扩容能按行号定位是哪一层结构在涨，而不是拿一个结构体的尺寸去乘节点数。

```python
import sys, tracemalloc

def make_nodes(n):
    return {'node:%d' % i: {'id': i, 'tags': ['a', 'b']} for i in range(n)}

tracemalloc.start()
base = tracemalloc.get_traced_memory()[0]
nodes = make_nodes(2000)
cur = tracemalloc.get_traced_memory()[0]
shallow = sys.getsizeof(nodes)
print('shallow dict bytes', shallow)
print('traced exceeds shallow', (cur - base) > shallow)
print('traced exceeds 8x', (cur - base) > 8 * shallow)
tracemalloc.stop()

```


## 把内存估算练准

<Exercise title='基础：区分小整数池与运行时大整数' task='分别验证 256 与 int(&#39;257&#39;) 两次创建后的 is 结果，用 sys.getrefcount 观察把对象放进列表再删除时计数的增减趋势。' solution='import sys\na, b = 256, 256\nprint(&#39;pooled&#39;, a is b)\nx, y = int(&#39;257&#39;), int(&#39;257&#39;)\nprint(&#39;distinct&#39;, x is y)\no = object()\nbase = sys.getrefcount(o)\nl = [o]\nprint(&#39;more&#39;, sys.getrefcount(o) &gt; base)\ndel l\nprint(&#39;back&#39;, sys.getrefcount(o) == base)' explain='256 在 -5..256 池内被复用，is 为 True；int(&#39;257&#39;) 运行时新建大整数，is 为 False。放进列表使 refcount 增加，del 后回落到基线。' />

<Exercise title='进阶：用 tracemalloc 快照定位增量分配' task='构造一批字符串对象前后各取一次 take_snapshot，用 compare_to 按 filename 汇总正的 size_diff，打印增量是否大于 0 且大于列表头大小。' solution='import sys, tracemalloc\ntracemalloc.start()\ns0 = tracemalloc.take_snapshot()\nrows = [str(i) * 4 for i in range(2000)]\ns1 = tracemalloc.take_snapshot()\ndiff = sum(s.size_diff for s in s1.compare_to(s0, &#39;filename&#39;) if s.size_diff &gt; 0)\nprint(&#39;growth&#39;, diff &gt; 0, &#39;over header&#39;, diff &gt; sys.getsizeof(rows))\ntracemalloc.stop()' explain='compare_to 按分配位置汇总 size_diff，能测到字符串对象等真实分配；这个增量通常远大于列表头，说明 getsizeof 只覆盖浅层结构。' />

<Quiz no='052-1' q='关于 sys.getsizeof，准确的说法是？' :options='["只返回浅层对象大小加 GC 头，算不到容器元素与碎片", "返回对象及其递归引用的全部内存", "等价于 tracemalloc 的当前净分配", "只统计 Python 层对象不含 C 结构体"]' answer="0" explain='getsizeof 走 __sizeof__ 并加 GC 头，反映单个对象结构体；列表只含指针数组，元素对象另算。真实分配与增量要用 tracemalloc。' />

<Quiz no='052-2' q='CPython 里 a = 256; b = 256; a is b 为 True，主要原因是？' :options='["256 落在 -5..256 的小整数池且编译期常量复用", "所有整数都驻留", "is 对整数按值比较", "解释器每次新建但恰好地址相同"]' answer="0" explain='CPython 启动时预分配 -5..256 的小整数并复用，编译期常量也会合并进 co_consts；这是实现细节，值比较仍应用 ==，运行时大整数不池化。' />

<Quiz no='052-3' q='对象引用计数归零时会发生什么？' :options='["立即调用 tp_dealloc 释放，并可能级联释放其引用的对象", "等待下一次分代 GC 统一回收", "只把对象标记为可回收，内存不释放", "总是立刻把内存还给操作系统"]' answer="0" explain='引用计数归零立即触发 tp_dealloc，行为可预测、可能级联；但 pymalloc 释放的 block 常留在 pool 里不立刻归还 OS，且循环引用需分代 GC 兜底。' />

<Predict no='052-4' q='x = int(&#39;257&#39;); y = int(&#39;257&#39;); x is y 的结果最可能是？' :options='["False，两次运行时创建得到不同大整数对象", "True，所有整数都池化", "抛 TypeError"]' answer='0' output='False' explain='小整数池只覆盖 -5..256，int(&#39;257&#39;) 在运行时新建对象且不做池化，两次调用得到不同对象。is 比的是身份，故为 False；比较值应写 x == y。' />

<FillBlank no='052-5' tpl='___ sys' :answers='["import"]' hint='回想本讲关于 PyObject 头与 ob_refcnt 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 PyObject 头、引用计数与归零即释放 的落点。' />

<KnowledgeCard :points='["PyObject 头含 ob_refcnt 与 ob_type；变长对象加 ob_size，GC 对象加 PyGC_Head", "引用计数在赋值、传参、容器存取、作用域退出时增减，归零立即释放；getrefcount 多算一个参数引用", "小整数池 -5..256 与字符串驻留是复用优化；值相等用 ==，单例才用 is", "pymalloc 对 ≤512 字节对象走 arena(256KB)/pool(4KB)/block 三级分配，释放后内存可能暂不归还", "getsizeof 是浅层大小，算不到容器元素；tracemalloc 在分配器层看真实净分配与快照增量", "纯引用计数无法回收循环引用，由分代 GC 兜底；海量小对象用 slots/array 换布局"]' :pitfalls='["用 sys.getsizeof 估算容器加全部元素的总内存", "用 is 比较大整数或运行时字符串", "以为引用计数能回收循环引用", "用 sys.getsizeof 只看对象本身，容器里元素、字符串内容、字典哈希表的开销都算不到"]' summary='引用计数让对象在失去最后一个引用时立刻回收，行为可预测；代价是需要 GC 兜底循环引用，也是 GIL 存在的历史原因之一' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| PyObject 头含 ob_refcnt 与 ob_type；变长对象加 ob_size，GC 对象加 PyGC_Head | 建立直觉 |
| 引用计数在赋值、传参、容器存取、作用域退出时增减，归零立即释放；getrefcount 多算一个参数引用 | 跑通示例 |
| 小整数池 -5..256 与字符串驻留是复用优化；值相等用 ==，单例才用 is | 深入边界 |
| pymalloc 对 ≤512 字节对象走 arena(256KB)/pool(4KB)/block 三级分配，释放后内存可能暂不归还 | 工程落地 |
| getsizeof 是浅层大小，算不到容器元素；tracemalloc 在分配器层看真实净分配与快照增量 | 随堂检测 |
| 纯引用计数无法回收循环引用，由分代 GC 兜底；海量小对象用 slots/array 换布局 | 复盘 |

1. PyObject 头含 ob_refcnt 与 ob_type；变长对象加 ob_size，GC 对象加 PyGC_Head

2. 引用计数在赋值、传参、容器存取、作用域退出时增减，归零立即释放；getrefcount 多算一个参数引用

3. 小整数池 -5..256 与字符串驻留是复用优化；值相等用 ==，单例才用 is

[下一讲：分代 GC、循环引用与 weakref](/core/gc)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/052-memory.py`

```bash
python3 examples/lessons/052-memory.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/052-memory.py) · [全部示例代码索引](/examples/)
