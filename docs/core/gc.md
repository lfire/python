---
title: 第 053 讲 · 分代 GC、循环引用与 weakref
description: 诊断并修复内存泄漏
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='40 分钟' goal='诊断并修复内存泄漏' prereq='第 052 讲 · 对象内存布局、引用计数与小对象池' />

# 第 053 讲 · 分代 GC、循环引用与 weakref

上一讲说引用计数归零就能立刻回收，行为可预测；但也留了个口子：两个对象互相指着对方，计数就永远降不到零。长驻服务跑几天内存悄悄涨、重启才回落，多半卡在这里。这一讲把计数兜不住的部分补齐。

先看一个常见场景：父子双向引用的节点、或拿普通 `dict` 当缓存，外部早不引用了，对象却一直活着。本讲先讲循环引用为何让计数失效、分代 GC 的三代阈值与 `gc.collect` 的时机，再说 `__del__` 的陷阱，最后落到 `weakref` 家族与用对象增量定位泄漏。需要第 52 讲的引用计数与第 43 讲的弱引用；学完你能诊断并修复内存泄漏，知道缓存该改用哪种引用。


## 一个缓存跑几天内存就涨到告警的线上服务

一个长驻服务跑了几天后内存持续上涨，重启才回落。

团队先看进程常驻内存，怀疑第三方库泄漏，折腾一周没结论；换用 `gc.get_objects()` 观察对象数量增量，才发现是父子双向引用的节点对象一直没被回收——两个对象互相指着对方，引用计数永远不为零。

另一处坑在缓存：用普通 `dict` 存会话对象，外部早就不引用了，字典里的强引用却让它们一直活着，缓存越积越大。还有人给对象定义了 `__del__` 做清理，按老资料以为「带析构的循环垃圾回收不了」，在 3.4 之后的环境里结论已经变了，却据此写了一套复杂的手动断开逻辑。

分代 GC、循环引用与 `weakref` 是诊断内存泄漏的核心工具。本讲把三代的触发阈值、`gc.collect` 的时机、PEP 442 之后的 `__del__` 行为、弱引用容器与泄漏定位方法逐条讲清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='用普通 dict 做对象缓存导致内存持续上涨：字典对每个值持有强引用，外部引用消失后对象仍被缓存挂着，计数不归零' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段五 · 核心机制与运行时 |
| 前置 | 第 052 讲 · 对象内存布局、引用计数与小对象池 |
| 难度 / 建议时长 | ★★★★☆ · 40 分钟 |
| 本讲新增 | 循环引用为何计数失效、三代与阈值、gc.collect 的时机 |
| 一句话目标 | 诊断并修复内存泄漏 |
| 为下一讲铺垫 | GIL 真相：存在原因、切换与影响边界 |

<CheckList id='P053a' title='学完你应当能' :items='["能讲清 循环引用为何让计数失效，以及三代 GC 的触发规则", "能讲清 __del__ 的陷阱与 PEP 442 之后的行为", "能讲清 weakref 家族与泄漏定位方法", "能在工程里处理 objgraph 定位"]' />


## 循环引用为何让计数失效，以及三代 GC 的触发规则

引用计数只在计数归零时释放，A 持有 B、B 又持有 A 时两者 `ob_refcnt` 至少为 1，即便外部已无任何引用也永不归零，这就是循环垃圾。分代 GC 专门补这个缺口：它只跟踪可能参与循环的容器对象（`list`、`dict`、自定义实例等），在每个对象上维护 gc 链表与 `gc_refs` 计数。

收集时先把 `gc_refs` 减去对象之间的内部引用，剩下的 `gc_refs` 大于 0 的是可达根，从根出发标记，未标记者即为不可达循环垃圾。

为压低扫描成本，采用「多数对象死得早」的经验假设分三代：新对象进 gen0，gen0 的净分配数（分配减释放）超过阈值（3.12 及以前 700、3.13 起 2000）就触发一次 gen0 收集，存活者晋升 gen1；gen1 每累计 10 次 gen0 收集触发一次；gen2 每累计 10 次 gen1 收集触发一次。

这三个数由 `gc.get_threshold()` 返回，3.13 起默认 `(2000, 10, 10)`、3.12 及以前为 `(700, 10, 10)`，可用 `gc.set_threshold` 调整；`gc.get_count()` 返回各代当前计数，`gc.isenabled()` / `enable()` / `disable()` 控制开关，`gc.collect(generation=2)` 手动做全量收集并返回不可达对象数。

排查看的是 `gc.get_objects()` 的数量增量，而不是常驻内存总量——后者受 pymalloc 与分配器碎片影响，不能区分泄漏与缓存。

```python
import gc, weakref

class Node:
    pass
a = Node()
b = Node()
a.peer = b
b.peer = a
wr = weakref.ref(a)
print('weak alive', wr() is a)
del a, b
collected = gc.collect()
print('collected', collected > 0)
print('weak dead', wr() is None)
cache = weakref.WeakValueDictionary()
obj = Node()
cache['k'] = obj
print('cache size', len(cache))
del obj
gc.collect()
print('cache size after', len(cache))
```

<OutputBox title='主示例运行结果' output='weak alive True\ncollected True\nweak dead True\ncache size 1\ncache size after 0' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import gc, weakref\n\nclass Node:\n    pass\na = Node()\nb = Node()\na.peer = b\nb.peer = a\nwr = weakref.ref(a)\nprint(&#39;weak alive&#39;, wr() is a)\ndel a, b\ncollected = gc.collect()\nprint(&#39;collected&#39;, collected &gt; 0)\nprint(&#39;weak dead&#39;, wr() is None)\ncache = weakref.WeakValueDictionary()\nobj = Node()\ncache[&#39;k&#39;] = obj\nprint(&#39;cache size&#39;, len(cache))\ndel obj\ngc.collect()\nprint(&#39;cache size after&#39;, len(cache))' :notes='["导入 gc 与 weakref，分别管收集与弱引用", "空行，只用于分隔逻辑块，不影响执行结果。", "空行分隔导入与类定义", "普通类默认带 __weakref__，可被弱引用", "创建第一个节点", "创建第二个节点", "a 引用 b，建立一条强引用", "b 反向引用 a，构成循环，计数不会归零", "对 a 建弱引用，不增加它的引用计数", "此时 a 还活着，弱引用能取回对象", "删掉外部两个名字，只剩循环引用", "手动全量收集，返回不可达对象数", "循环垃圾被回收，数量大于 0", "a 消亡后弱引用返回 None", "改用 WeakValueDictionary 做缓存，值是弱引用", "新建一个会话对象", "放进缓存，此时仍有 obj 这个强引用", "缓存里有一个条目", "删掉唯一的外部强引用", "再次收集，让弱引用回调生效", "条目自动移除，缓存不持有对象"]' title='第 053 讲 · 分代 GC、循环引用与 weakref' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='引用计数只在计数归零时释放，A 持有 B、B 又持有 A 时两者 `ob_refcnt` 至少为 1，即便外部已无任何引用也永不归零，这就是循环垃圾。分代 GC 专门补这个缺口：它只跟踪可能参与循环的容器对象（`list`、`dict`、自定义实例等），在每个对象上维护 gc 链表与…' />


### 三代 GC 的默认阈值与触发规则

**三代 GC 的默认阈值与触发规则**

| 代 | 触发条件 | 存活后 |
| --- | --- | --- |
| gen0 | 净分配数超过阈值（3.13 起 2000 / 旧版 700） | 晋升 gen1 |
| gen1 | 每累计 10 次 gen0 收集 | 晋升 gen2 |
| gen2 | 每累计 10 次 gen1 收集 | 全量扫描，成本最高 |
| gc.get_threshold() | 3.13 返回 (2000, 10, 10)；旧版 (700, 10, 10) | 可用 set_threshold 调整 |
| gc.get_count() | 返回各代当前计数三元组 | 排查自动收集是否触发 |
| gc.collect(2) | 手动全量收集 | 返回不可达对象数 |


## 可达性分析与分代回收器的 C 层实现

引用计数的盲区是循环：互相引用的对象 `ob_refcnt` 始终大于 0，永远等不到归零。分代 GC 只为可能成环的容器对象维护 gc 链表与 `gc_refs` 计数：收集时先把 `gc_refs` 减去对象间的内部引用，剩余 `gc_refs` 大于 0 的作为可达根做标记，未标记的整批就是不可达循环垃圾。

为摊薄扫描成本，它按「多数对象死得早」把对象分三代，gen0 净分配超过阈值（3.13 起 2000、旧版 700）就收集、存活者逐级晋升，gen1 / gen2 的触发频率由阈值的后两个数控制。

3.4 的 PEP 442 之前，带 finalizer 的循环垃圾因可能被复活而无法安全回收，被塞进 `gc.garbage`；之后改为先调用 finalizer 再回收，这类循环也能清理。

`weakref` 完全不增加 `ob_refcnt`，只登记一个回调链表：对象归零时把弱引用标记为 dead、触发回调，`WeakValueDictionary` 借此删除对应条目。

因此泄漏排查要先分清「对象还被强引用活着」与「内存只是没归还分配器」，前者用 `gc.get_objects()` 增量与 `get_referrers` 定位，后者属于正常的分配器行为。

<ConceptDiagram type='hub4' title='第 053 讲 · 循环引用为何让计数失效，以及三代 GC 的触发规则' labels='循环引用为何让计数失效，以及三代 GC 的触…|__del__ 的陷阱与 PEP 442 之…|weakref 家族与泄漏定位方法|objgraph 定位' caption='诊断并修复内存泄漏' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### 分代链表与 gc_generation 结构

<ConceptDiagram type='layers3' title='第 053 讲 · 分层视角' labels='循环引用为何让计数失效，以及三代 GC…|__del__ 的陷阱与 PEP 442…|weakref 家族与泄漏定位方法|objgraph 定位' caption='weakref 家族与泄漏定位方法' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 objgraph 定位 落在哪一层。


## __del__ 的陷阱与 PEP 442 之后的行为

历史上带 `__del__`（finalizer）的对象参与循环时，CPython 无法安全决定析构顺序，因为 finalizer 可能把对象重新复活；3.4 之前这类循环垃圾不可回收，会被放进 `gc.garbage` 列表，需要人工处理。

PEP 442（3.4 起）重新设计了终结流程：先调用所有不可达对象的 finalizer，再真正回收，带 `__del__` 的循环垃圾也能被正常清理，`gc.garbage` 不再是堆积点。

由此得到两条工程结论：不要把「带 `__del__` 一定泄漏」的老结论套到现代解释器上；也不要把关键释放逻辑放在 `__del__` 里——finalizer 抛出的异常无法向外传播，只会被打印到 stderr，调用顺序在循环里也不直观，且对象复活会让生命周期难以推理。

更可靠的做法是显式 `close()` / 上下文管理器（第 42 讲），或 `weakref.finalize`（3.4+）把清理回调注册到弱引用上，它只在对象真正消亡时触发一次，语义清晰且可取消。

`__del__` 适合做轻量兜底，比如打一条调试日志，而不是承担事务提交、连接关闭这类必须成功的动作。

```python
import gc, sys

gc.collect()
before = len(gc.get_objects())
temp = [object() for _ in range(5000)]
during = len(gc.get_objects())
del temp
gc.collect()
after = len(gc.get_objects())
print('objects grow', during > before)
print('objects reclaimed', after < during)
print('tracemalloc available', hasattr(sys, 'getallocatedblocks'))
print('refcount positive', sys.getrefcount(gc) > 0)
```

<OutputBox title='原理验证' output='objects grow True\nobjects reclaimed True\ntracemalloc available True\nrefcount positive True' />


### 循环引用、__del__ 与泄漏定位

**循环引用、__del__ 与泄漏定位**

| 现象 / 版本 | 根因 | 处理 |
| --- | --- | --- |
| A 与 B 互相引用，外部已删 | ob_refcnt 至少为 1，计数不归零 | 分代 GC 收集或断环 / 用 weakref |
| 缓存用普通 dict | 强引用让对象永生 | 改 WeakValueDictionary |
| 3.4 之前带 __del__ 的循环 | finalizer 可能复活对象，回收不安全 | 旧版进 gc.garbage，需人工断开 |
| 3.4+ PEP 442 | 先调 finalizer 再回收 | 循环可被正常清理，用 weakref.finalize 更清晰 |
| 对 int/str/tuple 弱引用 | 对象无 __weakref__ 槽 | 抛 TypeError: cannot create weak reference，只对支持者使用 |
| 常驻内存不降 | pymalloc 未归还或正常缓存占用 | 看 gc.get_objects() 增量与 get_referrers 引用链 |


## weakref 家族与泄漏定位方法

弱引用不增加 `ob_refcnt`，只在一个回调链表里登记；对象引用计数归零时把弱引用置为 dead 并执行回调，之后 `weakref.ref(obj)()` 返回 `None`。

常用工具：`weakref.ref` 拿单个弱引用，`weakref.proxy(obj)` 拿到代理，`WeakValueDictionary` 的值、`WeakKeyDictionary` 的键、`WeakSet` 的元素都是弱引用，`weakref.finalize` 注册清理回调。

缓存、观察者、父子双向引用都应优先用弱引用容器：外部强引用一消失，条目自动移除，对象随即可被回收，不会因缓存本身而永生。

限制要记牢：不是所有对象都支持弱引用，`int`、`str`、`tuple` 以及多数内置不可变类型会抛 `TypeError`，提示不能创建弱引用；自定义类默认带 `__weakref__` 槽可弱引用，但声明了 `__slots__` 且没把 `'__weakref__'` 写进去的类不行（第 43 讲）。

定位泄漏的推荐顺序：先用 `gc.get_objects()` 在稳定负载下看对象数增量，再用 `gc.get_referrers(obj)` 查是谁还引用着它，配合 `gc.set_debug(gc.DEBUG_SAVEALL)` 或第三方 `objgraph` 画出引用链；区分「引用还活着」与「分配器没归还内存」这两类完全不同的现象，再决定是断环、换弱引用容器还是接受缓存占用。

```python
import gc

print('threshold', gc.get_threshold())
print('enabled', gc.isenabled())
class WithDel:
    def __del__(self):
        pass
x = WithDel()
x.self = x
del x
n = gc.collect()
print('collected with del', n > 0)
print('garbage list', isinstance(gc.garbage, list))
print('count', len(gc.get_count()) == 3)
```

<OutputBox title='对照写法：先自己猜，再点开' output='threshold (2000, 10, 10)（3.13 起；3.12 及以前为 (700, 10, 10)）\nenabled True\ncollected with del True\ngarbage list True\ncount True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import gc, weakref\n\nclass Node:\n    pass\na = Node()\nb = Node()\na.peer = b\nb.peer = a\nwr = weakref.ref(a)\nprint(&#39;weak alive&#39;, wr() is a)\ndel a, b\ncollected = gc.collect()\nprint(&#39;collected&#39;, collected &gt; 0)\nprint(&#39;weak dead&#39;, wr() is None)\ncache = weakref.WeakValueDictionary()\nobj = Node()\ncache[&#39;k&#39;] = obj\nprint(&#39;cache size&#39;, len(cache))\ndel obj\ngc.collect()\nprint(&#39;cache size after&#39;, len(cache))", "note": "循环引用为何让计数失效，以及三代 GC 的触发规则"}, {"label": "对照 / 进阶", "code": "import gc\n\nprint(&#39;threshold&#39;, gc.get_threshold())\nprint(&#39;enabled&#39;, gc.isenabled())\nclass WithDel:\n    def __del__(self):\n        pass\nx = WithDel()\nx.self = x\ndel x\nn = gc.collect()\nprint(&#39;collected with del&#39;, n &gt; 0)\nprint(&#39;garbage list&#39;, isinstance(gc.garbage, list))\nprint(&#39;count&#39;, len(gc.get_count()) == 3)", "note": "__del__ 的陷阱与 PEP 442 之后的行为"}]' title='两种写法切换看' />


## weakref 工具对照

**weakref 工具对照**

| 工具 | 弱引用位置 | 适用场景 |
| --- | --- | --- |
| weakref.ref(obj[, cb]) | 单个对象的引用 | 观察单个对象是否消亡 |
| weakref.proxy(obj) | 代理对象 | 像原对象一样用，消亡后抛 ReferenceError |
| WeakValueDictionary | 值是弱引用 | 缓存：外部引用消失即移除条目 |
| WeakKeyDictionary | 键是弱引用 | 按对象做元数据映射 |
| WeakSet | 元素是弱引用 | 观察者集合 |
| weakref.finalize（3.4+） | 注册消亡回调 | 替代 __del__ 做可取消的清理 |

<Term word='循环引用为何计数失效' text='引用计数只在计数归零时释放，A 持有 B、B 又持有 A 时两者 `ob_refcnt` 至少为 1，即便外部已无任何引用也永不归零，这就是循环垃圾。分代 GC 专门补这个缺口：它只跟踪可能参与循环的容器对象（`list`、`dict`、自定义实例等），在每个对象上维护 gc 链表与 `gc_refs` 计数。收集时先…' />

<Term word='三代与阈值' text='历史上带 `__del__`（finalizer）的对象参与循环时，CPython 无法安全决定析构顺序，因为 finalizer 可能把对象重新复活；3.4 之前这类循环垃圾不可回收，会被放进 `gc.garbage` 列表，需要人工处理。PEP 442（3.4 起）重新设计了终结流程：先调用所有不可达对象的 fin…' />


## 版本与调优：gc.collect 的时机和阈值调整

<FlowTimeline :steps='[{"title": "循环引用为何让计数失效，以及三代 GC 的触发规…", "desc": "引用计数只在计数归零时释放，A 持有 B、B 又持有 A 时两者…", "tone": "blue"}, {"title": "__del__ 的陷阱与 PEP 442 之后的…", "desc": "历史上带 `__del__`（finalizer）的对象参与循环时，CPython…", "tone": "purple"}, {"title": "weakref 家族与泄漏定位方法", "desc": "弱引用不增加 `ob_refcnt`，只在一个回调链表里登记；对象引用计数归零时把弱…", "tone": "orange"}, {"title": "工程落地", "desc": "缓存泄漏诊断：强引用 dict 与 WeakValueDiction…", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用普通 dict 做对象缓存导致内存持续上涨", "body": "字典对每个值持有强引用，外部引用消失后对象仍被缓存挂着，计数不归零", "tip": "改用 weakref.WeakValueDictionary / WeakSet，或给缓存加容量与过期淘汰"}, {"title": "第 2 步：把关键释放逻辑写进 __del__ 并套用旧…", "body": "PEP 442（3.4+）后带 finalizer 的循环可被回收，但 __del__ 抛出的异常只打印到 stderr、调用顺序不直观、对象还可能复活", "tip": "用显式 close() 或上下文管理器（第 42 讲），或 weakref.finalize 注册可取消的清理回调；__del__ 只做轻量兜底"}, {"title": "第 3 步：对 int、str、tuple 或无 __w…", "body": "这些对象没有弱引用支持槽，weakref.ref 抛 TypeError: cannot create weak reference to &#39;int&#39; object", "tip": "只对支持弱引用的自定义类使用；slots 类把 &#39;__weakref__&#39; 显式写进 __slots__（第 43 讲）"}]' />


## 缓存泄漏诊断：强引用 dict 与 WeakValueDictionary 对照

会话缓存里同时放了两份索引：一份用普通 `dict` 强引用，一份用 `WeakValueDictionary` 弱引用，都指向同一批 `Session` 对象。

批量创建后做一次 `gc.collect`，强引用那份仍把全部对象挂着，弱引用那份在外部引用消失时会自动清空。

用 `gc.get_objects()` 的对象数增量确认「确实有对象没被回收」，再对比两个缓存的长度，就能把「缓存持有强引用导致泄漏」从猜测变成可核对的证据。

下面用标准库跑通，输出强缓存条目数、弱缓存条目数与对象增量布尔值。

真实系统还应打印按类型统计的对象分布，并用 `gc.get_referrers` 查具体是谁在引用；但骨架就是强引用与弱引用容器的对照。

```python
import gc, weakref

class Session:
    def __init__(self, uid):
        self.uid = uid
strong_cache = {}
weak_cache = weakref.WeakValueDictionary()

def fill(caches, n):
    for i in range(n):
        s = Session(i)
        caches[0]['s' + str(i)] = s
        caches[1]['s' + str(i)] = s

gc.collect()
base = len(gc.get_objects())
fill((strong_cache, weak_cache), 500)
gc.collect()
print('strong cache alive', len(strong_cache))
print('weak cache alive', len(weak_cache))
print('objects grew', len(gc.get_objects()) > base)
print('weak cache emptied', len(weak_cache) == 0)
```

<Callout type="idea" title='落地提示' text='缓存、观察者、父子双向引用优先用 weakref；泄漏排查先看 gc.get_objects 的增量而非总内存' />

<CheckList id='P053b' title='上线前自检' :items='["能复现并解释「用普通 dict 做对象缓存导致内存持续上涨」", "能复现并解释「把关键释放逻辑写进 __del__ 并套用旧版不可回收结论」", "能复现并解释「对 int、str、tuple 或无 __weakref__…」", "能用一条命令验证 循环引用为何计数失效", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import sys, gc; print(sys.getsizeof([1,2,3]), gc.get_count())"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 循环引用为何计数失效 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用普通 dict 做对象缓存导致内存持续上涨 | 字典对每个值持有强引用，外部引用消失后对象仍被缓存挂着，计数不归零 | 改用 weakref.WeakValueDictionary / WeakSet，或给缓存加容量与过期淘汰 |
| 把关键释放逻辑写进 __del__ 并套用旧版不可回收结论 | PEP 442（3.4+）后带 finalizer 的循环可被回收，但 __del__ 抛出的异常只打印到 stderr、调用顺序不直观、对象还可能复活 | 用显式 close() 或上下文管理器（第 42 讲），或 weakref.finalize 注册可取消的清理回调；__del__ 只做轻量兜底 |
| 对 int、str、tuple 或无 __weakref__ 的 slots 类建弱引用 | 这些对象没有弱引用支持槽，weakref.ref 抛 TypeError: cannot create weak reference to 'int' object | 只对支持弱引用的自定义类使用；slots 类把 '__weakref__' 显式写进 __slots__（第 43 讲） |

<Callout type="warn" title='本讲最容易踩的坑' text='用普通 dict 做对象缓存导致内存持续上涨：字典对每个值持有强引用，外部引用消失后对象仍被缓存挂着，计数不归零' />


## 查得动一次真实泄漏

<Exercise title='基础：让循环引用稳定复现并被 gc.collect 回收' task='构造两个互相引用的实例，对其中一个建弱引用，删掉外部名字后打印 gc.collect() 返回值与 weakref 是否变 None，解释为什么引用计数单独做不到。' solution='import gc, weakref\nclass N: pass\na, b = N(), N()\na.p, b.p = b, a\nw = weakref.ref(a)\ndel a, b\nprint(&#39;collected&#39;, gc.collect() &gt; 0, &#39;dead&#39;, w() is None)' explain='a.p 与 b.p 互相指向，删掉外部名字后两对象 ob_refcnt 仍为 1，引用计数无法归零；gc.collect() 把它们判为不可达循环垃圾并回收，弱引用随之返回 None。' />

<Exercise title='进阶：把普通缓存改造成弱引用缓存并验证自动清理' task='用 WeakValueDictionary 存对象，构造一批后删除外部强引用并 gc.collect，打印清理前后的条目数；再尝试对 int 建弱引用并捕获 TypeError。' solution='import gc, weakref\nclass O: pass\nc = weakref.WeakValueDictionary()\nitems = [O() for _ in range(10)]\nfor i, o in enumerate(items): c[i] = o\nprint(&#39;before&#39;, len(c))\ndel items\ngc.collect()\nprint(&#39;after&#39;, len(c))\ntry:\n    weakref.ref(42)\nexcept TypeError as e:\n    print(type(e).__name__, &#39;int not weakref-able&#39;)' explain='外部强引用消失后 WeakValueDictionary 的值只剩弱引用，条目自动移除，长度归零；int 无 __weakref__ 槽，weakref.ref 抛 TypeError: cannot create weak reference to &#39;int&#39; object。' />

<Quiz no='053-1' q='两个对象互相引用、外部引用已删除，为什么不会被引用计数回收？' :options='["彼此持有强引用，ob_refcnt 至少为 1，归零条件永不满足", "引用计数对自定义类失效", "对象被 gc.garbage 保护", "GIL 阻止了释放"]' answer="0" explain='循环引用让双方计数都大于 0，纯引用计数无能为力；分代 GC 通过 gc_refs 减内部引用、从可达根标记来识别并回收不可达循环垃圾。' />

<Quiz no='053-2' q='关于 gc.get_threshold() 的默认阈值，正确的是？' :options='["3.13 起为 (2000, 10, 10)，3.12 及以前为 (700, 10, 10)；后两数控制 gen1/gen2 频率", "(100, 5, 5)：固定每 100 个对象收集一次", "(1000, 0, 0)：只按对象总数收集", "(700, 10, 10)：每 700 毫秒收集一次"]' answer="0" explain='3.13 把 gen0 默认阈值从 700 提高到 2000，后两个数仍为 10：gen1 每累计 10 次 gen0 收集触发，gen2 每累计 10 次 gen1 收集触发，体现「多数对象死得早」。跨版本代码应读 gc.get_threshold() 而不是写死数字。' />

<Quiz no='053-3' q='关于现代 CPython 里带 __del__ 的循环垃圾，正确的是？' :options='["3.4 起 PEP 442 先调用 finalizer 再回收，这类循环可被正常清理", "一定进 gc.garbage 且永不回收", "__del__ 抛出的异常会向上传播给调用方", "必须手动断开 self 引用才能回收"]' answer="0" explain='3.4 之前的旧结论是带 finalizer 的循环不可回收、进 gc.garbage；PEP 442 改为先调 finalizer 再回收。但 __del__ 异常只打印到 stderr、顺序不直观，关键释放应改用 close() 或 weakref.finalize。' />

<Predict no='053-4' q='WeakValueDictionary 里的对象在外部强引用删除并 gc.collect 后，会怎样？' :options='["对应条目自动移除，len 变为 0", "条目保留但值变成 None", "抛 ReferenceError"]' answer='0' output='cache size after 0' explain='弱引用不增加 ob_refcnt；对象归零时被标记 dead 并触发回调，WeakValueDictionary 据此删除条目。所以外部强引用一消失、收集一跑，缓存长度就归零，对象不会因缓存而永生。' />

<FillBlank no='053-5' tpl='___ gc, weakref' :answers='["import"]' hint='回想本讲关于 循环引用为何计数失效 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 循环引用为何让计数失效，以及三代 GC 的触发规则 的落点。' />

<KnowledgeCard :points='["循环引用让 ob_refcnt 永不归零，纯引用计数回收不了，由分代 GC 兜底", "gc 默认阈值 3.13 起 (2000, 10, 10)、3.12 及以前 (700, 10, 10)；gen0 超阈值收集，存活者逐级晋升", "gc.collect(2) 返回不可达对象数；gc.get_count / get_threshold / get_objects 用于排查", "PEP 442（3.4+）先调 finalizer 再回收，带 __del__ 的循环也能清理；关键释放用 close 或 weakref.finalize", "weakref 不增加引用计数；WeakValueDictionary / WeakKeyDictionary / WeakSet 让缓存不持有强引用", "int/str/tuple 与未加 __weakref__ 的 slots 类不可弱引用；泄漏排查看 get_objects 增量与 get_referrers 引用链"]' :pitfalls='["用普通 dict 做对象缓存导致内存持续上涨", "把关键释放逻辑写进 __del__ 并套用旧版不可回收结论", "对 int、str、tuple 或无 __weakref__ 的 slots 类建弱引用", "定义了 __del__ 的对象参与循环时旧版本无法回收；缓存里用普通 dict 持有对象会让它们永远活着"]' summary='分代 GC 基于「多数对象死得早」的经验假设：新对象检查频繁、老对象很少扫描，用较低成本回收循环垃圾' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 循环引用让 ob_refcnt 永不归零，纯引用计数回收不了，由分代 GC 兜底 | 建立直觉 |
| gc 默认阈值 3.13 起 (2000, 10, 10)、3.12 及以前 (700, 10, 10)；gen0 超阈值收集，存活者逐级晋升 | 跑通示例 |
| gc.collect(2) 返回不可达对象数；gc.get_count / get_threshold / get_objects 用于排查 | 深入边界 |
| PEP 442（3.4+）先调 finalizer 再回收，带 __del__ 的循环也能清理；关键释放用 close 或 weakref.finalize | 工程落地 |
| weakref 不增加引用计数；WeakValueDictionary / WeakKeyDictionary / WeakSet 让缓存不持有强引用 | 随堂检测 |
| int/str/tuple 与未加 __weakref__ 的 slots 类不可弱引用；泄漏排查看 get_objects 增量与 get_referrers 引用链 | 复盘 |

1. 循环引用让 ob_refcnt 永不归零，纯引用计数回收不了，由分代 GC 兜底

2. gc 默认阈值 3.13 起 (2000, 10, 10)、3.12 及以前 (700, 10, 10)；gen0 超阈值收集，存活者逐级晋升

3. gc.collect(2) 返回不可达对象数；gc.get_count / get_threshold / get_objects 用于排查

[下一讲：GIL 真相：存在原因、切换与影响边界](/core/gil)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/053-gc.py`

```bash
python3 examples/lessons/053-gc.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/053-gc.py) · [全部示例代码索引](/examples/)
