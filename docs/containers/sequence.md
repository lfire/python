---
title: 第 017 讲 · 序列协议与通用操作
description: 理解所有序列共享的一套接口
---

<StageHeader stage='L2 · 容器与序列' level='★★☆☆☆' time='25 分钟' goal='理解所有序列共享的一套接口' prereq='第 016 讲 · 阶段综合：交互式命令行计算器' />

# 第 017 讲 · 序列协议与通用操作

你大概已经顺手用过切片，从一串记录里截一段。可不同容器切出来的并不都一样，有的改了原物不动，有的改一处就写坏整块。这一讲退一步，去看它们共同遵守的序列协议。

一个数据面板把几条记录切给前端，前端标了已读，刷新后原数据纹丝不动；另一处却因以为切片总是副本，把整块缓冲写坏。我们先弄清序列与可迭代的区别，看清两个魔术方法怎样撑起索引、切片和迭代；再走到抽象基类给的现成方法与版本迁移；最后借 slice 对象说清切片何时给副本、何时是视图。需要你熟悉 list、str、索引和循环。学完你能自己写一个行为规矩的序列类，也能判断某次切片动没动到原对象。


## 改了半天切片，原列表却一动不动

一个数据面板要展示最近若干条记录，工程师把内部 list 直接切成 `view = records`[1:4] 交给前端组件，组件里做了 view[0] = '已读'，刷新后发现原 records 纹丝不动，状态标记全丢了；反过来另一个模块以为切片一定是副本，对 memoryview 的切片原地改字节，结果把整块缓冲区写坏。

两处 bug 都来自把'切片'当成一个笼统动作，没区分谁返回副本、谁返回视图。更深一层是：有人手写了一个只实现 `__getitem__` 的容器，发现 for x in obj 和 'Wed' in obj 居然能用，而 obj[1:3] 却抛 TypeError，于是给每个方法都补一份样板代码。

实际上 CPython 的序列协议只要求 `__len__` 与 `__getitem__` 两个方法，迭代、成员判断、reversed 都由固定回退规则或 `collections.abc.Sequence` 的 mixin 免费提供。

本讲把这套协议、slice 对象如何传给 `__getitem__`、以及 3.10 移除顶层 collections 别名的迁移点讲清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='改了切片得到的子序列，原列表却没变：list / tuple / str 的切片返回同类型新对象（浅拷贝副本），只有 memoryview 切片是共享内存的视图' />


## 序列协议：两个方法撑起一整套操作

CPython 对序列的操作分两条独立通道。`len(obj)` 走 PyObject_Size 对应的 sq_length 槽（即 `__len__`），返回值必须能用 `__index__` 转成 Py_ssize_t，负数抛 ValueError、超过 `sys.maxsize` 抛 OverflowError。

下标 obj`[i]` 走 mp_subscript 或 sq_item 槽，最终调用 `__getitem__`；

编译器把 obj[a:b:c] 编译成 BUILD_SLICE 加 BINARY_SUBSCR，因此自定义 `__getitem__` 收到的是单个 slice 对象，而不是三个整数，是否支持切片完全取决于实现里有没有处理 `isinstance(index, slice)`。

'序列'与'可迭代'不是一回事：可迭代只要求 `__iter__` 返回一个迭代器；而序列要求 `__len__` 加 `__getitem__`，能按整数下标随机访问。

有趣的是 `iter(obj)` 会先查 tp_iter（`__iter__`），缺失时回退到 C 层的 PySeqIter_New，它持有从 0 开始的自增计数器，反复调 `__getitem__(i)` 直到抛 IndexError 才停——这就是'只写 __getitem__ 就能 for'的全部原因，也是老式容器仍能工作的底层机制。

in 的查找顺序则是 `__contains__`，其次 `__iter__` 迭代，最后才回退到 `__getitem__` 序列协议。

```python
from collections.abc import Sequence

class Week(Sequence):
    def __init__(self, names):
        self._names = tuple(names)
    def __len__(self):
        return len(self._names)
    def __getitem__(self, index):
        if isinstance(index, slice):
            return Week(self._names[index])
        return self._names[index]

w = Week(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
print(len(w), w[0], w[-1])
print(list(w), 'Wed' in w)
s = w[1:4:2]
print(type(s).__name__, list(s))
print(w.index('Thu'), w.count('Mon'), list(reversed(w)))

a = ['x', 'y', 'z']
b = a[1:]
b[0] = 'Y'
print(a, b)
```

<OutputBox title='主示例运行结果' output='5 Mon Fri\n[&#39;Mon&#39;, &#39;Tue&#39;, &#39;Wed&#39;, &#39;Thu&#39;, &#39;Fri&#39;] True\nWeek [&#39;Tue&#39;, &#39;Thu&#39;]\n3 1 [&#39;Fri&#39;, &#39;Thu&#39;, &#39;Wed&#39;, &#39;Tue&#39;, &#39;Mon&#39;]\n[&#39;x&#39;, &#39;y&#39;, &#39;z&#39;] [&#39;Y&#39;, &#39;z&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from collections.abc import Sequence\n\nclass Week(Sequence):\n    def __init__(self, names):\n        self._names = tuple(names)\n    def __len__(self):\n        return len(self._names)\n    def __getitem__(self, index):\n        if isinstance(index, slice):\n            return Week(self._names[index])\n        return self._names[index]\n\nw = Week([&#39;Mon&#39;, &#39;Tue&#39;, &#39;Wed&#39;, &#39;Thu&#39;, &#39;Fri&#39;])\nprint(len(w), w[0], w[-1])\nprint(list(w), &#39;Wed&#39; in w)\ns = w[1:4:2]\nprint(type(s).__name__, list(s))\nprint(w.index(&#39;Thu&#39;), w.count(&#39;Mon&#39;), list(reversed(w)))\n\na = [&#39;x&#39;, &#39;y&#39;, &#39;z&#39;]\nb = a[1:]\nb[0] = &#39;Y&#39;\nprint(a, b)' :notes='["3.10 起必须从 collections.abc 导入，顶层 collections.Sequence 已移除", "继承抽象基类，只需补两个抽象方法即可获得整套序列行为", "构造时把输入固化成 tuple，保证视图只读", "底层用不可变 tuple 存储元素", "实现第一个抽象方法：len() 走 sq_length 槽", "把长度委托给底层 tuple", "实现第二个抽象方法，同时处理整数下标与 slice 对象", "切片语法传入的是 slice 对象而不是三个整数", "切片结果包装回 Week，保持返回类型一致", "整数下标含负数交给 tuple 处理，越界由它抛 IndexError", "构造五个工作日的序列", "验证 len、正向索引与负向索引", "for 迭代与 in 判断由 mixin 基于 __getitem__ 免费提供", "带步长的切片，__getitem__ 收到 slice(1, 4, 2)", "返回类型是 Week，内容是隔一个取一个", "index / count / reversed 都是 Sequence 的 mixin 方法", "对照内置 list 的切片语义", "切片返回同类型新列表，是浅拷贝副本", "只修改副本的第一个元素", "原列表不变，证明 list 切片不是视图"]' title='第 017 讲 · 序列协议与通用操作' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='CPython 对序列的操作分两条独立通道。len(obj) 走 PyObject_Size 对应的 sq_length 槽（即 __len__），返回值必须能用 __index__ 转成 Py_ssize_t，负数抛 ValueError、超过 sys.maxsize 抛 OverflowErro' />

<ConceptDiagram type='layers3' title='第 017 讲 · 序列协议：两个方法撑起一整套操作' labels='序列协议：两个方法撑起一整套操作|collections.abc.Sequen|切片语义：副本、视图与 slice.indi' caption='理解所有序列共享的一套接口' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 可迭代协议与序列协议对照

**可迭代协议与序列协议对照**

| 协议 | 必须实现 | 获得的能力 | 典型类型 |
| --- | --- | --- | --- |
| 可迭代 Iterable | __iter__ 返回迭代器 | for / in / 解包 | 生成器、文件对象、dict |
| 旧式序列迭代 | __getitem__ 从 0 递增到 IndexError | for / in / iter() 自动回退 | 只实现 __getitem__ 的自定义类 |
| 序列 Sequence | __len__ 加 __getitem__（含 slice） | 索引、切片、len、in、迭代、reversed | list / tuple / str / range |
| collections.abc.Sequence | __len__ 与 __getitem__ 两个抽象方法 | mixin 免费给 __iter__ / __contains__ / __reversed__ / index / count | 自定义序列基类 |

<CodeTabs :tabs='[{"label": "主示例", "code": "from collections.abc import Sequence\n\nclass Week(Sequence):\n    def __init__(self, names):\n        self._names = tuple(names)\n    def __len__(self):\n        return len(self._names)\n    def __getitem__(self, index):\n        if isinstance(index, slice):\n            return Week(self._names[index])\n        return self._names[index]\n\nw = Week([&#39;Mon&#39;, &#39;Tue&#39;, &#39;Wed&#39;, &#39;Thu&#39;, &#39;Fri&#39;])\nprint(len(w), w[0], w[-1])\nprint(list(w), &#39;Wed&#39; in w)\ns = w[1:4:2]\nprint(type(s).__name__, list(s))\nprint(w.index(&#39;Thu&#39;), w.count(&#39;Mon&#39;), list(reversed(w)))\n\na = [&#39;x&#39;, &#39;y&#39;, &#39;z&#39;]\nb = a[1:]\nb[0] = &#39;Y&#39;\nprint(a, b)", "note": "序列协议：两个方法撑起一整套操作"}, {"label": "对照 / 进阶", "code": "class Legacy:\n    def __getitem__(self, i):\n        if i &gt;= 3:\n            raise IndexError(i)\n        return &#39;v&#39; + str(i)\n\nx = Legacy()\nprint(hasattr(x, &#39;__iter__&#39;))\nprint(list(iter(x)))\nprint(&#39;v2&#39; in x, &#39;v9&#39; in x)\n\nprint(slice(None, None, -1).indices(3))\nprint(slice(1, 10, 2).indices(5))", "note": "collections.abc.Sequence 的 mixin 与版本迁移"}]' title='两种写法切换看' />


## collections.abc.Sequence 的 mixin 与版本迁移

手写容器时重复实现 `__iter__` / `__contains__` / `__reversed__` / index / count 纯属样板。

`collections.abc.Sequence` 把这套约定固化：它只把 `__len__` 与 `__getitem__` 声明为抽象方法（继承自 Sized / Collection 的契约被 mixin 具体化），其余五个方法都用纯 Python 基于这两个方法实现——`__iter__` 用自增下标迭代，`__contains__` 用迭代比较，`__reversed__` 从 len-1 递减，index 与 count 线性扫描。

所以继承它只需补两个方法，isinstance 判断也为真，协议一致性由抽象基类保证。要注意 mixin 不提供 + 拼接与 * 重复，这两个运算符由 `__add__` / `__mul__` 单独实现，`abc.Sequence` 里没有；需要它们就得自己写或用 tuple / list 组合。

版本上有一条真实迁移：ABC 在 3.3 从 collections 顶层迁到 `collections.abc`，顶层别名 `collections.Sequence` / Mapping / Iterable 在 3.9 弃用、3.10 正式移除，今天必须写 from `collections.abc` import Sequence。

range 是标准库里序列协议的范本：实现 `__len__` 与 `__getitem__` 却不存全部元素，内存恒定，切片仍返回一个 range。

```python
class Legacy:
    def __getitem__(self, i):
        if i >= 3:
            raise IndexError(i)
        return 'v' + str(i)

x = Legacy()
print(hasattr(x, '__iter__'))
print(list(iter(x)))
print('v2' in x, 'v9' in x)

print(slice(None, None, -1).indices(3))
print(slice(1, 10, 2).indices(5))
```

<OutputBox title='对照写法：先自己猜，再点开' output='False\n[&#39;v0&#39;, &#39;v1&#39;, &#39;v2&#39;]\nTrue False\n(2, -1, -1)\n(1, 5, 2)' guess="true" />


### __getitem__ 收到的参数与义务

**__getitem__ 收到的参数与义务**

| 调用 | 传入 index | 应返回或应抛出 | 边界信号 |
| --- | --- | --- | --- |
| obj[2] | int 2 | 对应元素 | 越界抛 IndexError |
| obj[-1] | int -1 | 倒数第一个元素 | 内置序列由 C 层规范化 |
| obj[1:4:2] | slice(1, 4, 2) | 同类型新序列，自定义类自行包装 | 用 slice.indices(len) 规范化 |
| obj['k'] | str | 抛 TypeError | 非 int 非 slice 一律拒绝 |
| for x in obj | 依次 0, 1, 2 ... | 抛 IndexError 终止迭代 | 仅当未定义 __iter__ 时回退 |

<Term word='序列与可迭代的区别' text='CPython 对序列的操作分两条独立通道。len(obj) 走 PyObject_Size 对应的 sq_length 槽（即 __len__），返回值必须能用 __index__ 转成 Py_ssize_t，负数抛 ValueError、超过 sys.maxsize 抛 OverflowError。下标 obj[i' />

<Term word='__len__ 与 __getitem__' text='手写容器时重复实现 __iter__ / __contains__ / __reversed__ / index / count 纯属样板。collections.abc.Sequence 把这套约定固化：它只把 __len__ 与 __getitem__ 声明为抽象方法（继承自 Sized / Collection ' />


## 切片语义：副本、视图与 slice.indices

内置序列的切片返回同类型的浅拷贝副本：list 切片得到 list、tuple 得到 tuple、str 得到 str，改副本不影响原对象；唯一的例外是 memoryview 的切片返回共享同一块内存的视图，原地写会改到缓冲区。

自定义类要自己决定切片返回什么：把底层 tuple 的切片结果包装回本类，就能保持类型一致并继续享受 mixin 方法。

规范化边界不要手写负步长逻辑，用 `slice.indices(length)` 一步拿到 (start, stop, step) 三个具体整数：`slice(None, None, -1)`.`indices(3)` 得到 (2, -1, -1)，`slice(1, 10, 2)`.`indices(5)` 得到 (1, 5, 2)，把它展开给 range 就能同时正确处理负数、越界与负步长。

`__getitem__` 收到非 int 非 slice 的下标（如字符串）应抛 TypeError，越界应抛 IndexError，这两个信号是迭代回退与 reversed 能停下来的依据。负索引 obj[-1] 由内置序列在 C 层规范化，自定义类要么自己加 len，要么委托给底层容器，否则会得到错误元素。

```python
from collections.abc import Sequence
import inspect

class Week(Sequence):
    def __init__(self, names):
        self._names = tuple(names)
    def __len__(self):
        return len(self._names)
    def __getitem__(self, index):
        return self._names[index]

print('abstract', sorted(Sequence.__abstractmethods__))
print('isabstract', inspect.isabstract(Sequence))
for m in ('__iter__', '__contains__', '__reversed__', 'index', 'count'):
    print(m, m in Sequence.__dict__)
print('isinstance', isinstance(Week(['a']), Sequence))
print('mixin owner', Sequence.__iter__.__qualname__)
```

<OutputBox title='原理验证' output='abstract [&#39;__getitem__&#39;, &#39;__len__&#39;]\nisabstract True\n__iter__ True\n__contains__ True\n__reversed__ True\nindex True\ncount True\nisinstance True\nmixin owner Sequence.__iter__' />

CPython 对序列的操作分成两条独立通道。`len(obj)` 走 PyObject_Size 对应的 sq_length 槽，返回值必须能用 `__index__` 转成 Py_ssize_t，负数或超过 `sys.maxsize` 分别抛 ValueError 与 OverflowError。

下标 obj`[i]` 走 mp_subscript 或 sq_item 槽，最终调用 `__getitem__`；

编译器把 obj[a:b:c] 编译成 BUILD_SLICE 加 BINARY_SUBSCR，因此自定义 `__getitem__` 收到的是 slice 对象而非三个整数，是否支持切片完全取决于实现里有没有处理 `isinstance(index, slice)`。

迭代更微妙：`iter(obj)` 先查 tp_iter（`__iter__`），缺失时回退到 PySeqIter_New，它持有从 0 开始的自增计数器，反复调用 `__getitem__(i)` 直到 IndexError——这就是只写 `__getitem__` 也能 for 的底层机制。

in 的查找顺序是 `__contains__`，其次 `__iter__`，最后才是 `__getitem__` 序列回退。

`collections.abc.Sequence` 把这套约定固化：只声明 `__len__` 与 `__getitem__` 为抽象方法，其余 `__iter__` / `__contains__` / `__reversed__` / index / count 用纯 Python mixin 基于这两个方法实现，所以继承它能免费拿到一批方法，但 + 拼接与 * 重复不在 mixin 里，需要自己实现。


## 给日志环形缓冲区实现只读序列视图

一个实时面板要展示最近 N 条日志，底层是一个不断覆盖写入的固定容量缓冲区。直接把内部 list 暴露出去，调用方一个 append 就破坏了容量约束；每次返回 list 副本又浪费内存且拿不到实时变化。

做法是实现一个继承 `collections.abc.Sequence` 的 RingView：只存底层 list 与一个写指针，用 `__len__` 返回有效长度，用 `__getitem__` 把逻辑下标映射成环形物理下标，并对 slice 用 `slice.indices(len(self)`) 规范化后返回 tuple 快照。

这样 for、in、reversed、index、count 全部由 mixin 免费提供，切片拿到的是副本不会误以为是视图，调用方也无法通过视图修改缓冲区。重点是把'只读、有序、可切片'这组语义用两个方法表达清楚，而不是复制一批样板方法；当第 N+1 条写入时最老的条目被覆盖，视图长度始终不超过容量。

```python
from collections.abc import Sequence

class RingView(Sequence):
    def __init__(self, capacity):
        self._buf = [None] * capacity
        self._start = 0
        self._size = 0
    def push(self, item):
        cap = len(self._buf)
        idx = (self._start + self._size) % cap
        self._buf[idx] = item
        if self._size == cap:
            self._start = (self._start + 1) % cap
        else:
            self._size += 1
    def __len__(self):
        return self._size
    def __getitem__(self, index):
        if isinstance(index, slice):
            return tuple(self[i] for i in range(*index.indices(self._size)))
        if index < 0:
            index += self._size
        if not 0 <= index < self._size:
            raise IndexError(index)
        return self._buf[(self._start + index) % len(self._buf)]

v = RingView(3)
for n in (10, 20, 30, 40):
    v.push(n)
print(len(v), list(v), v[0], v[-1])
print('30 in view', 30 in v, '10 in view', 10 in v)
print('slice', v[1:3], 'reversed', list(reversed(v)))
```

<Callout type="idea" title='落地提示' text='自定义集合类型优先继承 collections.abc 的抽象基类，能免费获得一批 mixin 方法并保持协议一致' />

**版本差异与切片选型**

| 版本 / API | 行为 | 迁移或选型提示 |
| --- | --- | --- |
| collections.Sequence (3.9 及以前) | 顶层别名可用，3.9 起弃用 | 3.10 已移除，改用 collections.abc.Sequence |
| collections.abc.Sequence (3.3+) | 抽象基类加 mixin 方法 | 自定义序列优先继承它，且不提供 + 与 * |
| slice.indices(length) | 把 start / stop / step 规范成整数三元组 | 负步长与越界由它一次处理 |
| range | 实现 __len__ 与 __getitem__ 的惰性序列 | 内存恒定，不存全部元素 |
| memoryview 切片 | 返回共享内存的视图 | 与 list / tuple / str 的切片副本语义相反 |

<CheckList id='P017b' title='上线前自检' :items='["能复现并解释「改了切片得到的子序列，原列表却没变」", "能复现并解释「自定义类只写了 __getitem__，obj[a:b] 抛」", "能复现并解释「from collections import Sequen」", "能用一条命令验证 序列与可迭代的区别", "关键路径有自动化测试与失败分支"]' />


## 错因速查与动手自测

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 改了切片得到的子序列，原列表却没变 | list / tuple / str 的切片返回同类型新对象（浅拷贝副本），只有 memoryview 切片是共享内存的视图 | 要把修改写回原对象就用切片赋值 a[1:3] = [...]；要视图就用 memoryview |
| 自定义类只写了 __getitem__，obj[a:b] 抛 TypeError | 切片会传入 slice 对象，未处理 slice 的实现会把它当成非法下标 | 在 __getitem__ 里先判断 isinstance(index, slice)，用 slice.indices(len(self)) 规范化后再取值 |
| from collections import Sequence 报 ImportError | 3.9 弃用顶层别名，3.10 起 collections.Sequence / Mapping 等别名被移除 | 一律写 from collections.abc import Sequence |

<Callout type="warn" title='本讲最容易踩的坑' text='改了切片得到的子序列，原列表却没变：list / tuple / str 的切片返回同类型新对象（浅拷贝副本），只有 memoryview 切片是共享内存的视图' />

<Exercise title='基础：给自定义序列补上切片支持' task='下面的类只实现了整数下标，obj[1:3] 会失败。补一段对 slice 的处理，用 slice.indices 规范化，并验证负步长切片也能倒序返回。' solution='class Squares:\n    def __init__(self, n):\n        self.n = n\n    def __len__(self):\n        return self.n\n    def __getitem__(self, index):\n        if isinstance(index, slice):\n            return [self[i] for i in range(*index.indices(self.n))]\n        if not 0 &lt;= index &lt; self.n:\n            raise IndexError(index)\n        return index * index\n\ns = Squares(5)\nprint(list(s), s[1:4], s[::-1])' explain='切片传入的是 slice 对象，slice.indices(length) 一次性把 start / stop / step（含负步长与 None）规范成可交给 range 的整数三元组，避免自己处理负数与越界。继承 abc.Sequence 还能额外拿到 index / count / reversed。' />

<Exercise title='进阶：证明 in 与 iter 的协议回退顺序' task='构造三个类分别只实现 __contains__、只实现 __iter__、只实现 __getitem__，验证 &#39;x&#39; in obj 各走哪条路径，并观察旧式序列回退产生的迭代器类型名。' solution='class OnlyContains:\n    def __contains__(self, x):\n        return x == &#39;c&#39;\nclass OnlyIter:\n    def __iter__(self):\n        return iter([&#39;i&#39;])\nclass OnlyGetitem:\n    def __getitem__(self, i):\n        if i &gt;= 2:\n            raise IndexError(i)\n        return [&#39;g0&#39;, &#39;g1&#39;][i]\n\nprint(&#39;contains&#39;, &#39;c&#39; in OnlyContains(), &#39;i&#39; in OnlyIter(), &#39;g0&#39; in OnlyGetitem())\nprint(&#39;iter types&#39;, type(iter(OnlyIter())).__name__, type(iter(OnlyGetitem())).__name__)\nprint(&#39;getitem seq&#39;, list(OnlyGetitem()))' explain='in 的查找顺序是 __contains__，其次 __iter__，最后 __getitem__ 序列回退；三类各自命中一条。iter() 对只有 __getitem__ 的类返回 C 层的 iterator（序列迭代器），靠自增下标直到 IndexError 终止；只有 __contains__ 的类不可迭代，对它调 iter() 会抛 TypeError。' />

<Quiz no='017-1' q='一个类只实现了 __getitem__ 与 __len__，下列哪项是它自动获得的？' :options='["for 循环与 in 判断（经序列协议回退）", "+ 拼接与 * 重复", "append / extend 原地修改", "可作为 dict 键的哈希能力"]' answer="0" explain='iter() 在无 __iter__ 时回退到 PySeqIter_New 从 0 递增调 __getitem__，in 也回退到这条路径，abc.Sequence 的 mixin 同样基于此；+ / * 与原地修改不在协议里，哈希还要求 __hash__。' />

<Quiz no='017-2' q='obj[1:4:2] 传给 __getitem__ 的是什么？' :options='["三个整数 1, 4, 2", "slice(1, 4, 2) 对象", "range(1, 4, 2)", "list [1, 4, 2]"]' answer="1" explain='编译器把切片编译成 BUILD_SLICE 加 BINARY_SUBSCR，__getitem__ 收到单个 slice 对象；要用 slice.indices(len) 把它规范化成 range 参数。' />

<Quiz no='017-3' q='从 collections 顶层导入 Sequence，在 3.10+ 会怎样？' :options='["正常可用", "ImportError，别名已在 3.10 移除", "触发 DeprecationWarning 但仍可用", "返回 list 的别名"]' answer="1" explain='3.3 起 ABC 迁到 collections.abc，顶层别名 3.9 弃用、3.10 正式删除；应写 from collections.abc import Sequence。' />

<Predict no='017-P' q='对 a = [&#39;x&#39;, &#39;y&#39;, &#39;z&#39;] 执行 b = a[1:]; b[0] = &#39;Y&#39; 后，print(a, b) 输出什么？' :options='["[&#39;x&#39;, &#39;y&#39;, &#39;z&#39;] [&#39;Y&#39;, &#39;z&#39;]", "[&#39;x&#39;, &#39;Y&#39;, &#39;z&#39;] [&#39;Y&#39;, &#39;z&#39;]", "[&#39;x&#39;, &#39;y&#39;, &#39;z&#39;] [&#39;y&#39;, &#39;z&#39;]"]' answer='0' output='[&#39;x&#39;, &#39;y&#39;, &#39;z&#39;] [&#39;Y&#39;, &#39;z&#39;]' explain='list 切片返回同类型的浅拷贝副本，b 与原列表不共享存储，改 b[0] 不影响 a；只有 memoryview 的切片是共享内存的视图。要把修改写回原列表应使用切片赋值 a[1:] = [...].' />

<KnowledgeCard :points='["序列协议的核心只有 __len__ 与 __getitem__；索引、切片、len、迭代、in、reversed 都建立在它们之上", "iter() 优先 __iter__，缺失时回退 PySeqIter_New 从 0 调 __getitem__ 直到 IndexError；in 的顺序是 __contains__ 到 __iter__ 到序列回退", "切片传入 slice 对象，用 slice.indices(length) 规范化 start / stop / step（含负步长）", "collections.abc.Sequence 只抽象 __len__ 与 __getitem__，mixin 免费提供迭代、contains、reversed、index、count，但不提供 + 与 *", "list / tuple / str 切片是副本，memoryview 切片是视图；3.10 起顶层 collections.Sequence 别名已移除", "自定义序列继承 abc.Sequence 能保持协议一致并少写一批样板方法"]' :pitfalls='["改了切片得到的子序列，原列表却没变", "自定义类只写了 __getitem__，obj[a:b] 抛 TypeError", "from collections import Sequence 报 ImportError", "把切片得到的副本当成原对象的视图，改了半天发现没生效，是初学者最常见的误会"]' summary='Python 的容器不是各自为政：只要实现 __len__ 与 __getitem__，索引、切片、in、迭代就基本可用' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 序列协议的核心只有 __len__ 与 __getitem__；索引、切片、len、迭代、in、reversed 都建立在它们之上 | 建立直觉 |
| iter() 优先 __iter__，缺失时回退 PySeqIter_New 从 0 调 __getitem__ 直到 IndexError；in 的顺序是 __contains__ 到 __iter__ 到序列回退 | 跑通示例 |
| 切片传入 slice 对象，用 slice.indices(length) 规范化 start / stop / step（含负步长） | 深入边界 |
| collections.abc.Sequence 只抽象 __len__ 与 __getitem__，mixin 免费提供迭代、contains、reversed、index、count，但不提供 + 与 * | 工程落地 |
| list / tuple / str 切片是副本，memoryview 切片是视图；3.10 起顶层 collections.Sequence 别名已移除 | 随堂检测 |
| 自定义序列继承 abc.Sequence 能保持协议一致并少写一批样板方法 | 复盘 |

1. 序列协议的核心只有 __len__ 与 __getitem__；索引、切片、len、迭代、in、reversed 都建立在它们之上

2. iter() 优先 __iter__，缺失时回退 PySeqIter_New 从 0 调 __getitem__ 直到 IndexError；in 的顺序是 __contains__ 到 __iter__ 到序列回退

3. 切片传入 slice 对象，用 slice.indices(length) 规范化 start / stop / step（含负步长）

[下一讲：list：动态数组、操作与时间复杂度](/containers/list-basics)

<FillBlank no='017-F' tpl='from collections.abc  ___ Sequence' :answers='["import"]' hint='回想本讲关于 序列与可迭代的区别 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 序列协议：两个方法撑起一整套操作 的落点。' />
