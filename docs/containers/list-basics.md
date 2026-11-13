---
title: 第 018 讲 · list：动态数组、操作与时间复杂度
description: 能按成本选择合适操作
---

<StageHeader stage='L2 · 容器与序列' level='★☆☆☆☆' time='30 分钟' goal='能按成本选择合适操作' prereq='第 017 讲 · 序列协议与通用操作' />

# 第 018 讲 · list：动态数组、操作与时间复杂度

几乎每个程序都躲不开一串按次序排好的数据：日志、待办、最近几条记录。上一讲把序列接口讲清了，这一讲收窄到最常用的 list，看它把数据放在哪儿、不同动作各付什么代价。

一个日志脚本把六万条记录存进列表，每来一条都从头部插、尾部删，上线后处理器长期忙不过来；换成两头都省力的写法立刻平稳。我们先看列表的指针数组与预留容量，理解它存的是引用而非对象；再算尾部追加为何近乎常数、头部插入为何要搬动整排；最后把常用操作摆成复杂度对照，和双端队列一起按操作分布选容器。需要你已会索引、切片和遍历。学完你写循环前会先想数据从哪端进、哪端出，而不是凭习惯一路追加。


## 在列表头部反复 insert(0, x) 之后 CPU 打满了

一个日志消费脚本把最近 6 万条记录存进 list，每条新记录都写 `records.insert(0, rec)` 再 `records.pop()` 保持长度。

上线后 CPU 长期打满，吞吐却只有预期的十分之一。排查发现 `insert(0)` 每次都要把已有 6 万个引用整体后移一位，而 `pop()` 从尾部删几乎零成本；这两步放在一起，等于每条记录都做一次 `O(n)` 搬运，6 万条累计就是 `O(n²)`。

换成 `collections.deque(maxlen=60000)` 后两端操作都变成 `O(1)`，CPU 立刻回落。

另一个方向的坑是有人为了'少写一行'用 `a = b` 复制列表，接着 `a.append(x)` 把原列表也改了，因为赋值只复制引用。本讲把 list 的 PyObject* 指针数组布局、append 的摊还扩容、各操作的真实复杂度与容器选型拆开，目标是按操作分布选容器，而不是按习惯选。


## list 存的是引用：先看清内存布局

CPython 的 list 是 PyListObject：对象头里有 ob_size（逻辑长度）、ob_item（指向一块连续 PyObject* 数组的指针）与 allocated（已分配槽位数）。数组里存的是引用而不是对象本体，元素本体在堆上各自独立。

这解释了一串现象：一个 list 能混装 int、str、list 等任意类型；`len(a)` 直接读 ob_size 是 `O(1)`；a`[i]` 是一次指针偏移加一次解引用，也是 `O(1)`，但比 C 数组多一次间接寻址；

列表切片、`list(a)`、`a.copy()` 都只复制引用，是浅拷贝，改副本里的嵌套对象会穿透到原列表。

内存上在 64 位 CPython 3.13 实测：`sys.getsizeof([])` 为 56 字节，每增加一个元素约多 8 字节指针，(1, 2, 3) 这个 tuple 为 64 字节，而 [1, 2, 3] 为 88 字节（多出的部分就是 allocated 过度分配），空 deque 为 760 字节（要维护分块与双端指针）。

密集同构数值若想省掉指针开销与对象头，可用 `array.array`('i') 直接存 C 整数本体，代价是类型受限、不能混装。预分配 `[None]` * n 会一次性按 n 个槽位分配，比循环 append 少若干次 realloc。

```python
import sys
from collections import deque

row = [1, 'two', [3]]
print('mixed types', [type(x).__name__ for x in row])
print('stores refs', row[2] is row[2], row[1].upper())

a = []
sizes = []
for i in range(200):
    a.append(i)
    sizes.append(sys.getsizeof(a))
reallocs = sum(1 for i in range(1, len(sizes)) if sizes[i] != sizes[i - 1])
print('reallocs far fewer', reallocs < 20)
print('size never shrinks', all(sizes[i] >= sizes[i - 1] for i in range(1, len(sizes))))

b = [0, 1, 2, 3]
b.insert(0, 'head')
print('after insert(0)', b)
print('pop(0)', b.pop(0), 'now', b)
print('pop()', b.pop(), 'now', b)

d = deque([1, 2, 3])
d.appendleft(0)
d.append(4)
print('deque', list(d), d.popleft(), d.pop())
```

<OutputBox title='主示例运行结果' output='mixed types [&#39;int&#39;, &#39;str&#39;, &#39;list&#39;]\nstores refs True TWO\nreallocs far fewer True\nsize never shrinks True\nafter insert(0) [&#39;head&#39;, 0, 1, 2, 3]\npop(0) head now [0, 1, 2, 3]\npop() 3 now [0, 1, 2]\ndeque [0, 1, 2, 3, 4] 0 4' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys\nfrom collections import deque\n\nrow = [1, &#39;two&#39;, [3]]\nprint(&#39;mixed types&#39;, [type(x).__name__ for x in row])\nprint(&#39;stores refs&#39;, row[2] is row[2], row[1].upper())\n\na = []\nsizes = []\nfor i in range(200):\n    a.append(i)\n    sizes.append(sys.getsizeof(a))\nreallocs = sum(1 for i in range(1, len(sizes)) if sizes[i] != sizes[i - 1])\nprint(&#39;reallocs far fewer&#39;, reallocs &lt; 20)\nprint(&#39;size never shrinks&#39;, all(sizes[i] &gt;= sizes[i - 1] for i in range(1, len(sizes))))\n\nb = [0, 1, 2, 3]\nb.insert(0, &#39;head&#39;)\nprint(&#39;after insert(0)&#39;, b)\nprint(&#39;pop(0)&#39;, b.pop(0), &#39;now&#39;, b)\nprint(&#39;pop()&#39;, b.pop(), &#39;now&#39;, b)\n\nd = deque([1, 2, 3])\nd.appendleft(0)\nd.append(4)\nprint(&#39;deque&#39;, list(d), d.popleft(), d.pop())' :notes='["导入 sys 用 getsizeof 观察容量，deque 用于对照", "一个 list 混装 int、str、list 三种类型", "打印每个元素的实际类型，证明容器存的是任意对象引用", "row[2] 两次访问是同一对象；str.upper() 返回新字符串", "从空列表开始记录容量阶梯", "sizes 保存每次 append 后的 getsizeof 值", "连续 append 200 次，制造多次潜在扩容", "append 是摊还 O(1) 的尾部操作", "记录当前字节数，用于检测是否发生 realloc", "统计容量真正发生变化的次数", "200 次 append 只触发十几次扩容，远少于 200", "容量单调不减，getsizeof 不会变小", "构造一个小列表演示头部与尾部操作的差别", "insert(0, x) 要搬移全部 4 个引用，是 O(n)", "头部插入后的结果", "pop(0) 同样要搬移后续引用，比 pop() 贵", "pop() 只递减 ob_size，是 O(1)", "deque 从空序列构造，内部按分块组织", "appendleft 在左端 O(1) 插入", "append 在右端 O(1) 插入", "打印双端操作的结果，popleft 与 pop 各取一端", "in / index / count / remove 是 O(n) 线性扫描；+ 拼接与 * 重复要复制引用"]' title='第 018 讲 · list：动态数组、操作与时间复杂度' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 指针数组、ob_size 与 allocated

<ConceptDiagram type='hub4' title='第 018 讲 · 内存布局：指针数组、ob_size 与 allocated' labels='内存布局：指针数组、ob_size 与 al|摊还扩容：append 为什么是 O(1)，|复杂度全景与容器选型：list、deque、' caption='能按成本选择合适操作' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 摊还扩容：append 为什么是 O(1)

append 不每次都 realloc。CPython 的 list_resize 在容量不足时按 new_allocated = (newsize + (newsize >> 3) + 6) & ~3 计算新容量，大约是 1.125 倍加一个常数并按 4 对齐，然后 realloc 整块指针数组。

一次扩容能吸收后续多次 append，把 `O(n)` 的复制成本均摊掉，单次 append 摊还 `O(1)`。实测对空 list 连续 append 200 次，getsizeof 只变化 14 次，正是跳跃式扩容的证据；`sys.getsizeof` 只统计指针数组本身，不含被引用对象。

反过来 `insert(i, x)` 与 `pop(i)` 无法均摊：它们要用 memmove 把 i 之后的所有引用整体移动一位，复杂度 `O(n - i)`，因此 `insert(0)` / `pop(0)` 与 del a[0] 最贵，而 `pop()` 末尾只递减 ob_size 是 `O(1)`。

a + b 与 a * k 会构造新列表并复制全部引用，分别是 `O(n + m)` 与 `O(n·k)`；extend 则复用同一块数组，摊还 `O(k)`。`a.clear()`（3.3+）把长度置零并释放所有引用，是 `O(n)` 但只做一次减引用。判断瓶颈时先问：操作集中在尾部、头部还是中间，是否需要按下标随机访问。

CPython 的 list 是 PyListObject：头部含 ob_refcnt、ob_type、ob_size（逻辑长度），ob_item 指向一段连续的 PyObject* 数组，allocated 记录已分配槽位数。

数组元素是指针而非对象本体，所以混装任意类型、切片与浅拷贝都只复制指针，代价是每次访问多一次间接寻址、每个元素多 8 字节（64 位）指针开销。

append 触发 list_resize 时按 new_allocated = (newsize + (newsize >> 3) + 6) & ~3 计算新容量，约 1.125 倍并按 4 对齐，realloc 整块指针数组；把这次 `O(n)` 复制均摊到后续多次 append 上，得到摊还 `O(1)`。

insert 与 `pop(i)` 无法均摊：它们用 memmove 把 i 之后的引用整体平移，成本 `O(n-i)`，`pop()` 只减 ob_size 才是 `O(1)`。

每次增删引用都要配合 Py_INCREF / Py_DECREF 维护对象引用计数，这也是 `clear()` 与 del 需要 `O(n)` 逐个处理的原因。

`collections.deque` 改为分块双向链表，每块固定 64 个槽，两端操作只动块内指针故 `O(1)`，但跨块按下标定位退化为 `O(n)`，且不支持切片。


## insert(0) 为什么是 O(n)：搬移整段数组

```python
from collections import deque
from time import perf_counter

def build(mode, n):
    seq = deque() if mode == 'deque' else []
    t0 = perf_counter()
    for i in range(n):
        if mode == 'list-insert':
            seq.insert(0, i)
        elif mode == 'deque':
            seq.appendleft(i)
        else:
            seq.append(i)
    return perf_counter() - t0

n = 10000
t_insert = build('list-insert', n)
t_append = build('list-append', n)
t_deque = build('deque', n)
print('insert(0) much slower than append', t_insert > t_append * 5)
print('deque.appendleft faster than insert(0)', t_deque < t_insert)
```

<OutputBox title='对照写法：先自己猜，再点开' output='insert(0) much slower than append True\ndeque.appendleft faster than insert(0) True' guess="true" />


## 用 sys.getsizeof 实测扩容曲线


## list 常用操作的时间复杂度

**list 常用操作的时间复杂度（n 为长度，k 为插入元素数）**

| 操作 | 复杂度 | 底层原因 |
| --- | --- | --- |
| a[i] 读取与赋值 / len(a) | O(1) | 指针数组直接偏移，长度读 ob_size |
| append(x) / pop() | 摊还 O(1) / O(1) | 按约 1/8 过度分配，末尾只减长度 |
| insert(i, x) / pop(i) / del a[i] | O(n - i) | memmove 搬移 i 之后的全部引用 |
| in / index / count / remove | O(n) | 线性扫描并逐元素比较 |
| a + b / a * k / extend(b) | O(n+m) / O(nk) / 摊还 O(k) | 前者复制引用构造新列表，后者复用数组 |
| sort() | O(n log n) | TimSort，已排序输入接近 O(n) |
| clear() / 切片 a[:] | O(n) | 逐个减引用或复制全部引用 |


## 复杂度全景与容器选型：list、deque、array

把常见操作的成本列清楚，选型就不再是凭感觉：a`[i]`、`len(a)`、append、`pop()` 是 `O(1)` 或摊还 `O(1)`；`insert(i)`、`pop(i)`、del a`[i]` 是 `O(n - i)`；in、index、count、remove 是 `O(n)` 线性扫描并逐个比较；

`sort()` 最坏 `O(n log n)`。

`collections.deque` 是分块双向链表，内部按固定大小的 block（CPython 每块 64 个槽）组织，append / appendleft / pop / popleft 两端都是 `O(1)`，`deque(maxlen=n)` 在 append 时自动从另一端丢弃，特别适合队列与滑动窗口；

代价是按下标随机访问要跨块遍历，是 `O(n)`，且它不支持切片。`array.array` 用类型码（如 'i'、'd'）存 C 层数值本体，内存与数值计算都更省，但元素必须是同构数值、不能混装对象。选型结论很直接：需要按下标随机访问或切片才用 list；两端增删用 deque；

密集同构数值用 `array.array` 或 NumPy；要按键查找应规整成 dict（第 021 讲），而不是反复对 list 做 in 判断。


## 流式聚合：用 deque 做滑动窗口并用预分配 list 承接结果

一个监控脚本要维护最近若干个采样点的滑动窗口，并周期性输出窗口均值。若用 list 且每步都 `window.pop(0)` 加 append，窗口一宽就变成每步 `O(n)` 的 memmove，采集频率一高便吃掉整核；

改用 `collections.deque(maxlen=width)`，append 时自动从另一端丢弃最旧样本，两端都是 `O(1)`。

结果缓冲用 [0.0] * n 预分配再按位置写入，避免循环 append 反复扩容，最后用切片一次性把有效段交给下游。重点是按操作分布选容器：这里只需要两端增删与顺序遍历，不按下标随机访问，deque 正合适；只有下游要按下标取任意窗口才该换回 list。真实工程还要处理样本不足与异常值，但容器选型的边界在这几行里已经定死。

```python
from collections import deque
import statistics

SAMPLES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

def moving_avg(samples, width, stride):
    window = deque(maxlen=width)
    out = [0.0] * ((len(samples) - width) // stride + 1)
    k = 0
    for i, v in enumerate(samples):
        window.append(v)
        if len(window) == width and (i + 1 - width) % stride == 0:
            out[k] = round(statistics.mean(window), 2)
            k += 1
    return out[:k]

print('width 3 stride 2', moving_avg(SAMPLES, 3, 2))
print('width 4 stride 1', moving_avg(SAMPLES, 4, 1))
q = deque(maxlen=3)
for x in (1, 2, 3, 4):
    q.append(x)
print('bounded deque', list(q), len(q))
```

<Callout type="idea" title='落地提示' text='队列场景用 collections.deque，需要按下标随机访问才用 list；先想清楚操作分布再选容器' />


## 错因速查与按成本选型练习

<Exercise title='基础：用 sys.getsizeof 观察 append 的跳跃式扩容' task='对空 list 连续 append 100 次，统计 getsizeof 发生变化的次数，并说明为什么这个次数远小于 100。' solution='import sys\na = []\nprev = sys.getsizeof(a)\ngrowths = 0\nfor i in range(100):\n    a.append(i)\n    cur = sys.getsizeof(a)\n    if cur != prev:\n        growths += 1\n        prev = cur\nprint(&#39;growths&#39;, growths, &#39;stepwise&#39;, 0 &lt; growths &lt; 100)' explain='list_resize 按约 1.125 倍过度分配，一次扩容能吸收后续多次 append，因此 100 次 append 只触发十几次 realloc；这正是 append 摊还 O(1) 的来源。getsizeof 只反映指针数组，不含元素本体。' />

<Exercise title='进阶：量化 insert(0) 与 deque.appendleft 的差距' task='分别用 list.insert(0)、list.append、deque.appendleft 插入 10000 个元素并计时，验证 insert 远慢于 append、deque 快于 insert，并解释复杂度差异。' solution='from collections import deque\nfrom time import perf_counter\n\ndef bench(mode, n):\n    seq = deque() if mode == &#39;deque&#39; else []\n    t0 = perf_counter()\n    for i in range(n):\n        if mode == &#39;insert&#39;:\n            seq.insert(0, i)\n        elif mode == &#39;deque&#39;:\n            seq.appendleft(i)\n        else:\n            seq.append(i)\n    return perf_counter() - t0\n\nn = 10000\nti, ta, td = bench(&#39;insert&#39;, n), bench(&#39;append&#39;, n), bench(&#39;deque&#39;, n)\nprint(&#39;insert/append ratio &gt; 5&#39;, ti &gt; ta * 5)\nprint(&#39;deque faster than insert&#39;, td &lt; ti)' explain='insert(0) 第 i 次都要搬移 i 个引用，累计 O(n²)；append 靠过度分配摊还 O(1)；deque.appendleft 只动分块内指针恒为 O(1)。计时只输出布尔比较，避免把随机器波动的毫秒数写进断言。' />

<Quiz no='018-1' q='在长度为 n 的 list 头部反复 insert(0, x)，总时间复杂度是？' :options='["O(n)", "O(n log n)", "O(n²)", "摊还 O(1)"]' answer="2" explain='每次 insert(0) 都要把现有 n 个引用 memmove 一位，第 i 次成本 O(i)，累加为 O(n²)；头部增删应改用 collections.deque.appendleft。' />

<Quiz no='018-2' q='关于 CPython list 的 append 扩容，哪项准确？' :options='["每次 append 都 realloc 一次", "按约 1/8 的过度分配跳跃扩容，单次摊还 O(1)", "容量固定不增长", "严格按 2 倍增长"]' answer="1" explain='list_resize 用 new_allocated = (newsize + (newsize &gt;&gt; 3) + 6) &amp; ~3 计算容量，约 1.125 倍并按 4 对齐，realloc 的 O(n) 被均摊到多次 append。' />

<Quiz no='018-3' q='CPython 的 list 里存的是什么？' :options='["对象本体，连续紧凑", "指向对象的引用（PyObject* 指针）", "序列化后的字节", "值的深拷贝"]' answer="1" explain='ob_item 是 PyObject* 指针数组，元素本体在堆上各自独立；这解释了混装任意类型、间接寻址开销，以及切片与 copy 都只复制引用。' />

<Predict no='018-P' q='执行 a = [1, 2, 3]; b = a; a.append(4); print(len(b), b is a) 输出什么？' :options='["3 False", "4 True", "3 True"]' answer='1' output='4 True' explain='赋值 b = a 只复制对同一个 PyListObject 的引用，两者指向同一对象；append 原地修改该对象，所以 b 也看到 4 个元素，且 b is a 为 True。要独立副本用 a.copy()、a[:] 或 list(a)。' />

<FillBlank no='018-F' tpl='___ sys' :answers='["import"]' hint='回想本讲关于 列表的连续存储 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 内存布局：指针数组、ob_size 与 allocated 的落点。' />

<KnowledgeCard :points='["CPython list 是 PyObject* 连续指针数组：ob_size 是逻辑长度、allocated 是容量，元素本体在堆上独立", "append 摊还 O(1)，list_resize 按约 1/8 过度分配并 realloc；64 位 3.13 下 sys.getsizeof([]) 为 56 字节", "a[i] 与 len(a) 是 O(1)；insert(i) / pop(i) 因 memmove 是 O(n-i)，pop() 末尾是 O(1)", "in / index / count / remove 是 O(n) 线性扫描；+ 拼接与 * 重复要复制引用", "collections.deque 是分块双向链表，两端 append / appendleft / pop / popleft 都是 O(1)，中间索引 O(n) 且不支持切片", "需要按下标随机访问或切片才用 list；队列与滑动窗口用 deque，密集同构数值用 array.array"]' :pitfalls='["在列表头部反复 insert(0, x) 导致 CPU 打满", "a = b 后改 a，b 跟着变", "以为 sys.getsizeof(list) 是列表总内存", "在列表头部反复 insert(0, x) 会搬移整个数组，数据量大时比 deque 慢几个数量级"]' summary='list 存的是对象引用而不是对象本身，所以一个列表里能混装任意类型，代价是每次访问都要间接寻址' />

1. CPython list 是 PyObject* 连续指针数组：ob_size 是逻辑长度、allocated 是容量，元素本体在堆上独立

2. append 摊还 O(1)，list_resize 按约 1/8 过度分配并 realloc；64 位 3.13 下 sys.getsizeof([]) 为 56 字节

3. a[i] 与 len(a) 是 O(1)；insert(i) / pop(i) 因 memmove 是 O(n-i)，pop() 末尾是 O(1)

[下一讲：list 进阶：切片赋值、排序与常见陷阱](/containers/list-advanced)
