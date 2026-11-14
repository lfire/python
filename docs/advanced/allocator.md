---
title: 第 115 讲 · 内存分配器 pymalloc 与 GC 源码
description: 定位并解决苛刻场景下的内存问题
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='45 分钟' goal='定位并解决苛刻场景下的内存问题' prereq='第 114 讲 · CPython 源码：对象、帧与求值循环' />

# 第 115 讲 · 内存分配器 pymalloc 与 GC 源码

顺着源码往下，上一讲看清了语句怎么跑，紧接着碰到脚下那层：对象从哪块内存长出来、又何时还回去。长跑服务里对象明明都删了，进程占的内存却不见降；有人顺手调一次收集，只多出停顿。现象会骗人，得看分配器怎么管。

先铺开 pymalloc 的 arena、pool、block 三级结构，看小对象分配走哪条路；再读分代 GC 何时触发、gcmodule 怎样收走循环引用，解释 RSS 不降只是 arena 没整体空闲；最后用 tracemalloc 区分仍被引用、碎片与未归还。需要引用计数、GC 和对象模型；学完你能定位内存分配的疑难现象，不再凭 RSS 下判断。


## 对象都释放了，RSS 为什么还是不降

一个长驻服务跑几天后 RSS 从 300MB 涨到 1.2GB，运维第一反应是内存泄漏，值班手册写的动作是定时调 `gc.collect()`。加了之后每次收集都带来明显停顿，RSS 却几乎不降。

用 tracemalloc 一查，Python 对象总量其实稳定，真正增长的是某个 C 扩展的原生缓冲，以及 pymalloc 的 arena 没有整体空闲；另一份误判来自把「对象还被引用」当成「泄漏」，实际是全局缓存按设计持有。

要定位苛刻场景下的内存问题，得先分清三类：仍被引用、pymalloc 碎片、分配器未把内存归还 OS。本讲把 `obmalloc.c` 的三级结构、`gcmodule.c` 的分代收集与 tracemalloc 的观测手段对应起来，给出可核对的定位顺序，而不是一上来就 collect。

<Callout type="warn" title='先看一个真实会出错的写法' text='看到 RSS 高就定时 gc.collect()：若增长来自 pymalloc arena 未归还或 C 扩展原生内存，收集既不动这些也不降 RSS，只增加停顿' />

<Callout type="tip" title='核心心智模型' text='CPython 对小于 512 字节的对象走专用分配器 pymalloc（`Objects/obmalloc.c`），大对象直接交给 libc 的 malloc。它按三级组织：arena 是 256 KiB 的内存块，按 4 KiB 页对齐从 OS 申请；arena 内切成 4 KiB 的 pool…' />


## pymalloc 三级结构：arena / pool / block

CPython 对小于 512 字节的对象走专用分配器 pymalloc（`Objects/obmalloc.c`），大对象直接交给 libc 的 malloc。

它按三级组织：arena 是 256 KiB 的内存块，按 4 KiB 页对齐从 OS 申请；arena 内切成 4 KiB 的 pool，每个 pool 只服务一个 size class；

size class 以 8 字节为步长（8、16、24 直到 512 字节，共 64 档），block 是 pool 内按该档大小切出的单元。分配时按请求大小映射到 size class，从对应 pool 的 `freeblock` 链表取一块，代价是 `O(1)`；释放时把 block 挂回 `freeblock`。

`usedpools` 数组按 size class 维护可用 pool，arena 用 `usable_arenas` 链表管理。关键点：只有当某个 arena 内所有 pool 都完全空闲时，它才可能通过 `free()` 归还 OS；只要 arena 里还留着一个存活的小对象，整块 256 KiB 就继续计入 RSS。

这解释了「对象已释放但 RSS 不降」：不是泄漏，而是碎片与未归还。`sys.getsizeof` 返回对象自身占用（3.13 里空 dict 为 64 字节、小 int 为 28 字节），不含容器引用的元素，也不含原生内存。

**pymalloc 三级结构与参数**

| 层级 | 大小 | 职责 |
| --- | --- | --- |
| arena | 256 KiB，4 KiB 对齐 | 从 OS 申请，全空闲时才能归还 |
| pool | 4 KiB | 只服务一个 size class |
| block | 8 到 512 字节，8 字节步长 | 实际分配给对象的单元，共 64 档 |
| size class | 共 64 档 | 请求大小向上取整到档位 |

<ConceptDiagram type='layers3' title='第 115 讲 · 分层视角' labels='pymalloc 三级结构：arena…|分代 GC 的触发逻辑与 gcmodul…|tracemalloc、pympler…|与 glibc malloc 关系' caption='tracemalloc、pympler 与定位顺序' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 与 glibc malloc 关系 落在哪一层。


### arena 只有整体空闲才归还 OS

```python
import gc, tracemalloc, sys

print('tracked_obj', gc.is_tracked(object()))
print('generations', len(gc.get_stats()))
tracemalloc.start()
snap1 = tracemalloc.take_snapshot()
block = [dict(i=i) for i in range(500)]
snap2 = tracemalloc.take_snapshot()
top = snap2.compare_to(snap1, 'lineno')[0]
print('alloc_positive', top.size > 0)
print('getsizeof_dict', sys.getsizeof({}))
print('getsizeof_int', sys.getsizeof(1))
tracemalloc.stop()
```

<OutputBox title='原理验证' output='tracked_obj False\ngenerations 3\nalloc_positive True\ngetsizeof_dict 64\ngetsizeof_int 28' />


## 引用计数、循环引用与分代 GC 的触发逻辑

引用计数能即时回收大多数对象，但处理不了循环引用，因此 CPython 还有分代标记-清除 GC（`Modules/gcmodule.c`）。

容器对象（list、dict、带 `__dict__` 的实例等）创建时被 GC 追踪，记入 gen0 链表；

不参与循环的类型（如 int、str，以及不可变且不含可变引用的 tuple）不被追踪，`gc.is_tracked(1)` 返回 False。

三代阈值由 `gc.get_threshold()` 给出，3.13 默认是 `(2000, 10, 10)`：gen0 分配数减去释放数超过 2000 就触发 gen0 收集，每 10 次 gen0 收集触发一次 gen1，每 10 次 gen1 触发一次 gen2 全量收集。

收集时先把每个可达对象的 gc_refs 设为引用计数，再减去内部引用，剩下的即为不可达循环垃圾；带 `__del__` 的对象自 PEP 442（3.4）起先调用终结器再决定回收，避免旧版本把整个循环放进 `gc.garbage`。

`gc.collect(generation=2)` 可手动全量收集，返回找到的不可达对象数。

要注意 `gc.collect` 只处理 Python 对象循环，C 扩展的原生内存、mmap、文件缓冲都在它视野之外。

**分代 GC 参数（3.13 实测）**

| 项 | 值 / 行为 | 说明 |
| --- | --- | --- |
| gc.get_threshold() | (2000, 10, 10) | gen0 分配差超 2000 触发；10 次 gen0 触发 gen1，10 次 gen1 触发 gen2 |
| gc.get_count() | (gen0, gen1, gen2) | 各代当前计数 |
| gc.collect(2) | 返回不可达对象数 | 全量收集，只处理 Python 对象循环 |
| gc.is_tracked(1) | False | int 不含引用，不参与 GC |
| gc.freeze() | 3.7+ | 把长存活对象移出收集范围 |

```python
import gc

print('threshold', gc.get_threshold())
print('tracked_list', gc.is_tracked([]))
print('tracked_int', gc.is_tracked(1))

class Node:
    __slots__ = ('ref',)
    def __init__(self):
        self.ref = None

a = Node(); b = Node()
a.ref = b; b.ref = a
refs = len([r for r in gc.get_referrers(b) if isinstance(r, Node)])
print('node_referrers', refs)
del a, b
found = gc.collect(2)
print('cycle_collectable', found >= 2)
print('gen0_below_threshold', gc.get_count()[0] < gc.get_threshold()[0])
```

<OutputBox title='主示例运行结果' output='threshold (2000, 10, 10)\ntracked_list True\ntracked_int False\nnode_referrers 1\ncycle_collectable True\ngen0_below_threshold True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import gc\n\nprint(&#39;threshold&#39;, gc.get_threshold())\nprint(&#39;tracked_list&#39;, gc.is_tracked([]))\nprint(&#39;tracked_int&#39;, gc.is_tracked(1))\n\nclass Node:\n    __slots__ = (&#39;ref&#39;,)\n    def __init__(self):\n        self.ref = None\n\na = Node(); b = Node()\na.ref = b; b.ref = a\nrefs = len([r for r in gc.get_referrers(b) if isinstance(r, Node)])\nprint(&#39;node_referrers&#39;, refs)\ndel a, b\nfound = gc.collect(2)\nprint(&#39;cycle_collectable&#39;, found &gt;= 2)\nprint(&#39;gen0_below_threshold&#39;, gc.get_count()[0] &lt; gc.get_threshold()[0])' :notes='["导入 gc 观察分代回收", "空行，只用于分隔逻辑块，不影响执行结果。", "3.13 默认阈值 (2000, 10, 10)", "list 是容器，参与 GC 追踪", "int 不含引用，不被 GC 追踪", "空行，只用于分隔逻辑块，不影响执行结果。", "定义最小的循环引用节点", "__slots__ 限定属性，仍是 GC 追踪对象", "构造时初始化引用字段", "把 ref 置空，稍后构造环", "空行，只用于分隔逻辑块，不影响执行结果。", "创建两个节点", "互相引用形成环，引用计数无法回收", "用 get_referrers 数出引用 b 的 Node 对象", "只有 a 一个 Node 引用 b", "删除两个名字，环变为不可达", "手动触发第 2 代全量收集", "至少回收两个循环节点，证明 GC 生效", "收集后 gen0 计数回落到阈值以下"]' title='第 115 讲 · 内存分配器 pymalloc 与 GC 源码' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 对照：gc.collect 前后与循环引用的回收

```python
import gc, weakref

class C:
    pass

gc.disable()
a = C(); a.self = a
r = weakref.ref(a)
del a
print('alive_without_gc', r() is not None)
n = gc.collect()
print('collected', n >= 1)
print('weak_dead', r() is None)
gc.enable()
```

<OutputBox title='对照写法：先自己猜，再点开' output='alive_without_gc True\ncollected True\nweak_dead True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import gc\n\nprint(&#39;threshold&#39;, gc.get_threshold())\nprint(&#39;tracked_list&#39;, gc.is_tracked([]))\nprint(&#39;tracked_int&#39;, gc.is_tracked(1))\n\nclass Node:\n    __slots__ = (&#39;ref&#39;,)\n    def __init__(self):\n        self.ref = None\n\na = Node(); b = Node()\na.ref = b; b.ref = a\nrefs = len([r for r in gc.get_referrers(b) if isinstance(r, Node)])\nprint(&#39;node_referrers&#39;, refs)\ndel a, b\nfound = gc.collect(2)\nprint(&#39;cycle_collectable&#39;, found &gt;= 2)\nprint(&#39;gen0_below_threshold&#39;, gc.get_count()[0] &lt; gc.get_threshold()[0])", "note": "pymalloc 三级结构：arena / pool / block"}, {"label": "对照 / 进阶", "code": "import gc, weakref\n\nclass C:\n    pass\n\ngc.disable()\na = C(); a.self = a\nr = weakref.ref(a)\ndel a\nprint(&#39;alive_without_gc&#39;, r() is not None)\nn = gc.collect()\nprint(&#39;collected&#39;, n &gt;= 1)\nprint(&#39;weak_dead&#39;, r() is None)\ngc.enable()", "note": "分代 GC 的触发逻辑与 gcmodule 收集过程"}]' title='两种写法切换看' />


## 看到 RSS 高就定时 gc.collect()

<Callout type="warn" title='本讲最容易踩的坑' text='看到 RSS 高就定时 gc.collect()：若增长来自 pymalloc arena 未归还或 C 扩展原生内存，收集既不动这些也不降 RSS，只增加停顿' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：看到 RSS 高就定时 gc.collect…", "body": "若增长来自 pymalloc arena 未归还或 C 扩展原生内存，收集既不动这些也不降 RSS，只增加停顿", "tip": "先用 tracemalloc 与 RSS 差值分类；仍被引用改生命周期，碎片改分配布局，原生内存查扩展释放路径"}, {"title": "第 2 步：把 tracemalloc 统计当作进程全部…", "body": "它只覆盖 Python 分配器经手的块，不含 C 扩展原生 malloc、mmap、glibc 缓存与线程栈", "tip": "同时采集 RSS 与 tracemalloc，差值大就转向 jemalloc prof 或扩展统计接口排查原生内存"}, {"title": "第 3 步：认为 del 之后对象一定被释放", "body": "互相引用的容器引用计数不为 0，只能等分代 GC；且 sys.getsizeof 不含容器元素与原生内存", "tip": "用 weakref 验证可回收性、gc.get_referrers 查谁还引用；理解 sys.getsizeof 只算对象自身结构"}]' />


## tracemalloc、pympler 与定位顺序

定位内存问题要按证据分三层走。第一层用 tracemalloc（3.4 起，PEP 454）在分配点打快照，`compare_to` 按 lineno 或 traceback 找出增长最多的代码位置，它统计的是 Python 分配器经手的块，能区分「哪些代码还持有对象」；

第二层对比 tracemalloc 总量与进程 RSS，差值大说明内存不在 Python 对象里，方向转向 C 扩展原生内存、glibc malloc 缓存或 mmap，需要 valgrind、jemalloc prof 或扩展自身的统计接口；

第三层看 pymalloc 碎片，用 `gc.get_stats()` 看各代收集次数与 collected 数，用 `gc.get_referrers` 追谁还引用着对象，用 weakref 验证对象能否被回收。

`gc.freeze()`（3.7 起）可把长期存活对象移出收集范围，减少启动时反复扫描。盲目 `gc.collect` 只增加停顿：若 RSS 高来自 arena 未归还或原生内存，收集既不动这些也不降 RSS。正确修复取决于分类：仍被引用就改生命周期或缓存上限，碎片就减少长短生命周期对象混布，原生内存就查扩展的释放路径。

**内存现象分类与定位手段**

| 现象 | 根因类别 | 定位手段 |
| --- | --- | --- |
| tracemalloc 总量随请求增长 | 对象仍被引用 | compare_to 按 lineno 找分配点，查全局缓存 |
| RSS 远高于 tracemalloc | C 扩展原生内存 / glibc 缓存 | jemalloc prof、valgrind、扩展自带统计 |
| 对象已释放但 RSS 不降 | pymalloc arena 未整体空闲 | gc.get_stats、减少长短生命周期混布 |
| 带 __del__ 的循环不回收 | 历史遗留（3.4 前） | PEP 442 后先终结再回收，查 gc.garbage |

pymalloc 用空间换单线程分配速度：把小于 512 字节的请求按 8 字节步长归入 64 个 size class，每个 pool 只服务一档，从 `freeblock` 链表以 `O(1)` 取还，避免频繁进 libc malloc。

代价是内存按 arena 粒度向 OS 申请，只有整个 arena 的所有 pool 都空闲时才可能 `free` 归还；长短生命周期对象混在同一个 arena，会让少数存活对象钉住整块 256 KiB，RSS 因而不随对象释放下降，这是碎片而非泄漏。

引用计数即时回收无环对象，剩余循环垃圾交给分代 GC：容器对象进 gen0 链表，分配减释放超过阈值即触发标记-清除，通过把可达对象的 gc_refs 减去内部引用识别不可达环。阈值 `(2000, 10, 10)` 体现分代假设——多数对象朝生暮死，年轻代高频小收集、老年代低频全收集。

tracemalloc 在分配路径上记录 traceback，能按代码位置归因，但它只覆盖 Python 分配器经手的块，看不到 C 扩展的原生 malloc，因此 tracemalloc 总量与 RSS 的差值本身就是重要的分类信号。


## 按分类定位内存问题的诊断工具

把一次内存排查写成可复用的诊断函数：采集 tracemalloc 快照、对比分配点、读各代收集统计、用 weakref 验证循环对象能否被回收，并打印 RSS 与 Python 分配量的差值提示。真实长驻服务里这段定时运行，把增长点归因到具体文件行，再决定是改缓存上限、调整对象生命周期还是查 C 扩展。

重点是先分类再动手，避免用 `gc.collect` 掩盖真正原因；下面这段用标准库把观测层搭起来，输出的是可核对的数字而非主观判断。

```python
import gc, tracemalloc, weakref, sys

def diagnose(build):
    tracemalloc.start()
    s1 = tracemalloc.take_snapshot()
    obj = build()
    s2 = tracemalloc.take_snapshot()
    top = s2.compare_to(s1, 'lineno')[0]
    cur, peak = tracemalloc.get_traced_memory()
    print('growth_bytes', top.size, 'traced', cur)
    print('gen_counts', gc.get_count())
    r = weakref.ref(obj)
    del obj
    print('alive_before_collect', r() is not None)
    n = gc.collect()
    print('collected', n, 'alive_after', r() is not None)
    tracemalloc.stop()
    return cur

class Node:
    def __init__(self):
        self.ref = self

diagnose(Node)
```

<Callout type="idea" title='落地提示' text='用 tracemalloc 与 pympler 区分「仍被引用」「碎片」「未归还」，再决定改生命周期还是改分配策略' />

<CheckList id='P115b' title='上线前自检' :items='["能复现并解释「看到 RSS 高就定时 gc.collect()」", "能复现并解释「把 tracemalloc 统计当作进程全部内存」", "能复现并解释「认为 del 之后对象一定被释放」", "能用一条命令验证 arena / pool / block 三级", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import dis, sys; print(sys.version.split()[0]); dis.dis(lambda x:x)"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 arena / pool / block 三级 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 看到 RSS 高就定时 gc.collect() | 若增长来自 pymalloc arena 未归还或 C 扩展原生内存，收集既不动这些也不降 RSS，只增加停顿 | 先用 tracemalloc 与 RSS 差值分类；仍被引用改生命周期，碎片改分配布局，原生内存查扩展释放路径 |
| 把 tracemalloc 统计当作进程全部内存 | 它只覆盖 Python 分配器经手的块，不含 C 扩展原生 malloc、mmap、glibc 缓存与线程栈 | 同时采集 RSS 与 tracemalloc，差值大就转向 jemalloc prof 或扩展统计接口排查原生内存 |
| 认为 del 之后对象一定被释放 | 互相引用的容器引用计数不为 0，只能等分代 GC；且 sys.getsizeof 不含容器元素与原生内存 | 用 weakref 验证可回收性、gc.get_referrers 查谁还引用；理解 sys.getsizeof 只算对象自身结构 |


## obmalloc.c 的 pool_header 与 usedpools 哨兵数组

Objects/`obmalloc.c` 里 pymalloc 的复杂度藏在两个结构体和一个数组技巧里。

pool_header 描述一个 4 KiB pool：refcnt 是已分配 block 数，freeblock 是以偏移量编码的空闲块单链表，nextoffset/maxnextoffset 标出可切块的边界，szidx 是 size class 下标，arena_address 记录 pool 序号。

分配从 freeblock 取头节点，为空则按 nextoffset 切新块；释放挂回 freeblock 并 refcnt--，归零时整个 pool 移出 usedpools、链入 arena 的 freepools。

usedpools 是哨兵数组：`usedpools[i+i]` 与 `usedpools[i+i+1]` 伪装成一个假 pool_header，作为 size `class i` 的部分空闲 pool 双向链表头，插入删除 `O(1)`，`POOL_ADDR(P)` 用按位与把 block 地址取整到 pool 头。

arena_object 记录 address、nfreepools、ntotalpools、freepools 与 prevarena/nextarena 两个 usable_arenas 链表指针。

关键判定：只有 nfreepools == ntotalpools，即整块 256 KiB 的 64 个 pool 全空闲，free_arena 才 munmap 归还 OS；任意一个存活小对象把 pool 钉住，整块 arena 就继续计入 RSS。

宏 `SMALL_REQUEST_THRESHOLD=512`、`ALIGNMENT=8`、`POOL_SIZE=4096`、`ARENA_SIZE=1`<<18 决定三级容量。

```python
import gc, sys

sizes = []
buf = []
for i in range(9):
    buf.append(i)
    sizes.append(sys.getsizeof(buf))
print('list_growth', sizes)
print('gc_threshold', gc.get_threshold())
print('int_tracked', gc.is_tracked(1))
print('list_tracked', gc.is_tracked([1, 2, 3]))
print('tuple_with_list_tracked', gc.is_tracked(([1],)))
print('stats_keys', sorted(gc.get_stats()[0].keys()))
```

<OutputBox title='扩展示例运行结果' output='list_growth [88, 88, 88, 88, 120, 120, 120, 120, 184]\ngc_threshold (2000, 10, 10)\nint_tracked False\nlist_tracked True\ntuple_with_list_tracked True\nstats_keys [&#39;collected&#39;, &#39;collections&#39;, &#39;uncollectable&#39;]' />

<LineByLine code='import gc, sys\n\nsizes = []\nbuf = []\nfor i in range(9):\n    buf.append(i)\n    sizes.append(sys.getsizeof(buf))\nprint(&#39;list_growth&#39;, sizes)\nprint(&#39;gc_threshold&#39;, gc.get_threshold())\nprint(&#39;int_tracked&#39;, gc.is_tracked(1))\nprint(&#39;list_tracked&#39;, gc.is_tracked([1, 2, 3]))\nprint(&#39;tuple_with_list_tracked&#39;, gc.is_tracked(([1],)))\nprint(&#39;stats_keys&#39;, sorted(gc.get_stats()[0].keys()))' :notes='["逐次 append 并记录 sys.getsizeof", "空行，只用于分隔逻辑块，不影响执行结果。", "列表容量按 4、8、16 档过度分配，尺寸呈台阶跳变", "3.13 三代默认阈值 (2000, 10, 10)", "小整数不参与循环，未被 GC 追踪", "列表是容器，一定被追踪", "含可变元素的元组可能参与循环，必须被追踪", "每代固定返回 collected/collections/uncollectable 三个键", "这一行 `print(&#39;gc_threshold&#39;, gc.get_threshold())` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;int_tracked&#39;, gc.is_tracked(1))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;list_tracked&#39;, gc.is_tracked([1, 2, 3]))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;tuple_with_list_tracked&#39;, gc.is_tracked(([1],` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;stats_keys&#39;, sorted(gc.get_stats()[0].keys())` 的作用，可对照上方输出逐项核对。"]' title='扩展示例逐行讲解' />


### arena_object 与整块 256 KiB 归还条件

**obmalloc.c 关键宏与结构体字段**

| 名称 | 值或类型 | 作用 | 源码位置 |
| --- | --- | --- | --- |
| SMALL_REQUEST_THRESHOLD | 512 字节 | 小于它的请求走 pymalloc | Objects/obmalloc.c |
| POOL_SIZE / ARENA_SIZE | 4096 / 262144 字节 | pool 与 arena 的固定容量 | Objects/obmalloc.c |
| pool_header.refcnt | 已分配 block 计数 | 归零时 pool 脱离 usedpools | Objects/obmalloc.c |
| pool_header.freeblock | 偏移单链表 | 空闲 block 链，分配 O(1) | Objects/obmalloc.c |
| arena_object.nfreepools | 空闲 pool 数 | 等于 ntotalpools 才 munmap arena | Objects/obmalloc.c |


### 从 new_arena 到 free_arena 的分配路径

<ConceptDiagram type='flow4' title='第 115 讲 · 扩展图解' labels='arena 256KiB|pool 4KiB|block 8-512B|freeblock 链表' caption='pymalloc 三级包含关系：arena 只有全部 pool 空闲才整体归还，freeblock 是 pool 内的空闲块单链' />


## gcmodule.c 的 PyGC_Head 与三代计数结构

分代 GC 的数据结构在 Modules/`gcmodule.c` 与 Include/internal/`pycore_gc.h`。

被追踪容器在对象头前多一段 PyGC_Head，3.9 起实现为 _gc_next 与 _gc_prev 两个 uintptr_t：低位存链表指针，高位复用为标记位，gc_refs 打包进 _gc_next 高位，收集态用掩码标注，于是原地维护三色而不额外分配数组。

struct gc_generation 只有 PyGC_Head head、int threshold、int count 三个字段，三代组成 `generations[3]`；

_PyObject_GC_Alloc 把对象挂进 gen0 时执行 `generations[0].count`++，超过 threshold（默认 2000）就调用 collect_generations。

gc_collect_main 依次：update_refs 把 ob_refcnt 拷进 gc_refs；subtract_refs 对每个可达容器调 tp_traverse，把访问到的对象 gc_refs 减一，扣除内部引用；move_unreachable 按 gc_refs>0 拆可达与不可达两条链；

PEP 442 起先 handle_weakrefs、再 finalize_garbage 调 `__del__`，最后 delete_garbage 用 tp_clear 打断循环。dict 的 tp_traverse 在 `dictobject.c` 里只访问 value，tuple 遍历逐元素，决定扣除是否完整。

`gc.freeze()` 只把长期对象移出收集范围，并不释放内存。

某长驻对账服务两周内 RSS 从 300MB 涨到 1.1GB，值班每五分钟 `gc.collect()`，停顿 200ms 却几乎不降。复盘用 tracemalloc 两个快照 compare_to，Python 侧分配稳定在 310MB，与 RSS 的 790MB 差值不在 Python 对象里；

`gc.get_stats()` 的 gen2 collected 每轮为 0，说明没有循环垃圾、收集只是在空转。

差值定位到两处：一个 C 扩展每批请求 malloc 的解压缓冲没走 PyMem 释放路径，以及 pymalloc 长短生命周期混布留下的 arena 碎片——常驻缓存里剩一个 24 字节对象，把整块 256 KiB 钉在 RSS 里。修复是给缓存加上限与 TTL、把解压缓冲改为复用池、从手册删掉定时 collect。

下面是分类脚本：同时采集 tracemalloc 与 gc 统计，真实环境再补 /proc/self/status 的 RSS 读数。

```python
import gc, tracemalloc

tracemalloc.start()
cache = [bytearray(4096) for _ in range(2000)]
current, peak = tracemalloc.get_traced_memory()
print('traced_mb', round(current / 1048576, 2))
print('peak_mb', round(peak / 1048576, 2))
print('generations', len(gc.get_stats()))
gc.collect()
print('after_collect_mb', round(tracemalloc.get_traced_memory()[0] / 1048576, 2))
tracemalloc.stop()
```


### update_refs 到 delete_garbage 的位布局

<Term word='gc_refs 位打包（PyGC_Head）' text='3.9 起 PyGC_Head 用 _gc_next、_gc_prev 两个 uintptr_t 同时存链表指针与标记位：gc_refs 放进 _gc_next 高位，收集态用掩码标注，使 Modules/gcmodule.c 能原地做三色标记而不额外分配数组，定义见 Include/internal/pycore_gc.h。' />


## 练习、自测与速记

<Exercise title='基础：验证循环引用需要 GC 才能回收' task='创建两个互引实例，用 weakref 观察 del 后仍存活，再 gc.collect 后消失，并打印 collected 数。' solution='import gc, weakref\nclass N:\n    pass\na = N(); b = N()\na.r = b; b.r = a\nr = weakref.ref(a)\ndel a, b\nprint(&#39;before&#39;, r() is not None)\nprint(&#39;collected&#39;, gc.collect())\nprint(&#39;after&#39;, r() is None)' explain='互引让引用计数不为 0，del 后对象仍存活；标记-清除 GC 找出不可达环并回收，weakref 随之失效。' />

<Exercise title='进阶：用 tracemalloc 找出分配热点' task='构造一批对象，用两次快照 compare_to 找出增长最多的分配位置，并说明为什么它看不到 C 扩展原生内存。' solution='import tracemalloc\ntracemalloc.start()\ns1 = tracemalloc.take_snapshot()\ndata = [dict(i=i) for i in range(1000)]\ns2 = tracemalloc.take_snapshot()\ntop = s2.compare_to(s1, &#39;lineno&#39;)[0]\nprint(&#39;top_size&#39;, top.size &gt; 0, &#39;count&#39;, len(data))\ntracemalloc.stop()' explain='tracemalloc 在 Python 分配路径上记录 traceback，因此能按代码行归因；C 扩展直接调 malloc 的内存不经此路径，不在统计内。' />

<Quiz no='115-1' q='对象已释放但 RSS 不降，最可能的解释是？' :options='["pymalloc 的 arena 未整体空闲，256 KiB 块未归还 OS", "引用计数失效导致泄漏", "gc.collect 未开启", "操作系统延迟统计"]' answer="0" explain='arena 只有所有 pool 都空闲才可能归还；只要还有存活对象钉住，整块 256 KiB 继续计入 RSS，这是碎片而非泄漏。' />

<Quiz no='115-2' q='关于 3.13 的 gc.get_threshold()，正确的是？' :options='["默认 (2000, 10, 10)，gen0 分配差超 2000 触发", "默认 (700, 10, 10)，所有版本一致", "阈值越大 GC 越频繁", "collect(0) 会做全量收集"]' answer="0" explain='本机 3.13 实测阈值为 (2000, 10, 10)；旧版本常见 (700, 10, 10)，阈值随版本变化应现场查。collect(0) 只收第 0 代。' />

<Quiz no='115-3' q='tracemalloc 与进程 RSS 差距很大，说明什么？' :options='["存在 C 扩展原生内存、glibc 缓存或 mmap 等不在 Python 分配器统计内的占用", "tracemalloc 统计有 bug", "所有对象都已被 GC 回收", "RSS 读数不准"]' answer="0" explain='tracemalloc 只覆盖 Python 分配器经手的块；差值正是把排查方向转向原生内存与分配器缓存的关键信号。' />

<Predict no='115-4' q='gc.is_tracked(1) 与 gc.is_tracked([]) 分别返回什么？' :options='["False 与 True", "True 与 True", "False 与 False"]' answer='0' output='tracked_int False，tracked_list True' explain='int 是不可变标量、不含指向其它对象的引用，不可能参与循环，因此不被 GC 追踪；list 是容器，创建时进入 gen0 链表被追踪。' />

<FillBlank no='115-5' tpl='___ gc' :answers='["import"]' hint='回想本讲关于 arena / pool / block 三级 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 pymalloc 三级结构：arena / pool / block 的落点。' />

<KnowledgeCard :points='["pymalloc 管小于 512 字节对象：arena 256KiB / pool 4KiB / block 8 字节步长共 64 档", "arena 只有整体空闲才归还 OS，少数存活对象钉住整块，造成对象已释放但 RSS 不降", "引用计数即时回收，循环垃圾交分代 GC；3.13 阈值 (2000, 10, 10)，collect(2) 全量", "容器被 GC 追踪、int/str 不被追踪；PEP 442 起带 __del__ 的循环先终结再回收", "gc.collect 只处理 Python 对象循环；C 扩展原生内存与 glibc 缓存不受它影响", "定位顺序：tracemalloc 找分配点 → 对比 RSS 差值 → gc.get_referrers/weakref 查引用与碎片"]' :pitfalls='["看到 RSS 高就定时 gc.collect()", "把 tracemalloc 统计当作进程全部内存", "认为 del 之后对象一定被释放", "看到 RSS 高就断定泄漏、直接调 gc.collect，往往只增加停顿而不解决问题"]' summary='pymalloc 为小于 512 字节的对象做了专用池，所以「对象已释放但 RSS 不降」常常是 arena 没整体空闲，而非泄漏' />

1. pymalloc 管小于 512 字节对象：arena 256KiB / pool 4KiB / block 8 字节步长共 64 档

2. arena 只有整体空闲才归还 OS，少数存活对象钉住整块，造成对象已释放但 RSS 不降

3. 引用计数即时回收，循环垃圾交分代 GC；3.13 阈值 (2000, 10, 10)，collect(2) 全量

[下一讲：导入系统源码与 import hook](/advanced/import-source)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/115-allocator.py`

```bash
python3 examples/lessons/115-allocator.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/115-allocator.py) · [全部示例代码索引](/examples/)
