---
title: 第 025 讲 · 迭代协议：iterable、iterator 与惰性求值
description: 能自己实现一个惰性数据源
---

<StageHeader stage='L2 · 容器与序列' level='★★★☆☆' time='30 分钟' goal='能自己实现一个惰性数据源' prereq='第 024 讲 · 推导式：四种写法与可读性边界' />

# 第 025 讲 · 迭代协议：iterable、iterator 与惰性求值

前面所有容器都能被 for 走一遍，背后藏着同一个约定。上一讲的推导式把它用得很顺，这一讲掀开盖子：分清“能被遍历”和“记住走到哪”，也弄懂为何有的东西只能读一次。

一个同步脚本拿到同事给的数据源，循环一遍就空，再读仍不声不响。另一处把大文件整份读进内存，机器吃紧，逐行读就平稳。我们先分清迭代协议里可迭代对象与迭代器两层角色，看清两个魔术方法各自的责任；再讲取迭代器的两种形式与迭代器一次性为何让文件不能重读；最后走到常用工具，算清惰性求值省下的内存。需要你熟悉循环、函数与文件逐行读取。学完你能自己写一个带状态的惰性数据源，也明白二次遍历为何空掉。


## 遍历两次的文件，第二次什么都没有

一个数据同步脚本拿到同事封装好的'数据源'对象，先 `len(data)` 想打印进度，再 for x in data 遍历，结果长度函数报错、循环一次就读空；换了个写法先 `list(data)` 物化，再遍历两次，第二次却是空列表且不报任何错。

排查发现对方返回的是一个迭代器（比如 map 或文件对象），不是列表：它一次性、带状态，消耗完就永久耗尽。另一处事故是把一个大文件用 `readlines()` 全读进内存做统计，文件几百 MB 时直接 OOM；改成逐行迭代文件对象后内存立刻平稳。这两类问题都源自没分清可迭代对象与迭代器。

本讲把 `__iter__` / `__next__` 协议、`iter()` 的两种形式、迭代器一次性、itertools 工具与惰性求值的价值讲清楚。

<Callout type="warn" title='先看一个真实会出错的写法' text='把迭代器当列表用，第二次遍历拿到空结果：迭代器一次性、带状态，耗尽后 next 一直抛 StopIteration，for 与 list 会静默得到空' />


## 两层协议：iterable 产出 iterator，iterator 记住位置

可迭代对象实现 `__iter__()`，调用后返回一个迭代器；迭代器必须实现 `__next__()`，每次返回一个元素，耗尽时抛 StopIteration，并按约定实现 `__iter__()` 返回 self。

for x in obj 的等价展开是：`it = iter`(obj); while True: try: `x = next`(it) except StopIteration: break，编译后对应 GET_ITER 与 FOR_ITER 字节码，因此'遍历结束'是一个异常信号，而不是长度判断。

`collections.abc.Iterator` 只把 `__next__` 声明为抽象方法，mixin 免费提供返回 self 的 `__iter__`；

Iterable 只抽象 `__iter__`。关键差别在状态归属：迭代器把游标放在自己对象里，消耗一次前进一步，耗尽后 next 持续抛 StopIteration，所以 `list(it)` 第二次得到 [] 且不报错——这是把迭代器当列表用最隐蔽的坑。

可迭代对象与迭代器可以分离：list 的 `__iter__` 每次返回一个新的 list_iterator，因此能反复遍历；文件对象 TextIOWrapper 的 `__iter__` 返回 self，本身就是迭代器，`iter(f)` is f 为真，只能读一遍，重读要 reopen 或 `seek(0)`。

```python
import io
from collections.abc import Iterator, Iterable
import itertools

class Countdown:
    def __init__(self, n):
        self.n = n
    def __iter__(self):
        return self
    def __next__(self):
        if self.n <= 0:
            raise StopIteration
        self.n -= 1
        return self.n

c = Countdown(3)
print('is iterator', isinstance(c, Iterator), isinstance(c, Iterable))
print('first pass', list(c))
print('second pass', list(c))

f = io.StringIO('a' + chr(10) + 'b' + chr(10))
print('file is its own iterator', iter(f) is f)
lst = [1, 2]
print('list iter gives new', iter(lst) is not iter(lst))

def chunks(text, size):
    src = io.StringIO(text)
    return iter(lambda: src.read(size), '')
print('read chunks', list(chunks('abcdef', 2)))

print('islice', list(itertools.islice(itertools.count(10), 4)))
print('chain', list(itertools.chain([1, 2], [3])))
print('takewhile', list(itertools.takewhile(lambda x: x < 4, [1, 3, 5, 2])))
try:
    print(list(zip([1, 2], [3], strict=True)))
except ValueError as e:
    print('zip strict', type(e).__name__)
```

<OutputBox title='主示例运行结果' output='is iterator True True\nfirst pass [2, 1, 0]\nsecond pass []\nfile is its own iterator True\nlist iter gives new True\nread chunks [&#39;ab&#39;, &#39;cd&#39;, &#39;ef&#39;]\nislice [10, 11, 12, 13]\nchain [1, 2, 3]\ntakewhile [1, 3]\nzip strict ValueError' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import io\nfrom collections.abc import Iterator, Iterable\nimport itertools\n\nclass Countdown:\n    def __init__(self, n):\n        self.n = n\n    def __iter__(self):\n        return self\n    def __next__(self):\n        if self.n &lt;= 0:\n            raise StopIteration\n        self.n -= 1\n        return self.n\n\nc = Countdown(3)\nprint(&#39;is iterator&#39;, isinstance(c, Iterator), isinstance(c, Iterable))\nprint(&#39;first pass&#39;, list(c))\nprint(&#39;second pass&#39;, list(c))\n\nf = io.StringIO(&#39;a&#39; + chr(10) + &#39;b&#39; + chr(10))\nprint(&#39;file is its own iterator&#39;, iter(f) is f)\nlst = [1, 2]\nprint(&#39;list iter gives new&#39;, iter(lst) is not iter(lst))\n\ndef chunks(text, size):\n    src = io.StringIO(text)\n    return iter(lambda: src.read(size), &#39;&#39;)\nprint(&#39;read chunks&#39;, list(chunks(&#39;abcdef&#39;, 2)))\n\nprint(&#39;islice&#39;, list(itertools.islice(itertools.count(10), 4)))\nprint(&#39;chain&#39;, list(itertools.chain([1, 2], [3])))\nprint(&#39;takewhile&#39;, list(itertools.takewhile(lambda x: x &lt; 4, [1, 3, 5, 2])))\ntry:\n    print(list(zip([1, 2], [3], strict=True)))\nexcept ValueError as e:\n    print(&#39;zip strict&#39;, type(e).__name__)' :notes='["导入 io 构造内存文件，itertools 提供惰性工具", "导入抽象基类用于 isinstance 检查", "导入 itertools 工具集", "自定义一个倒计数迭代器", "记录当前剩余值", "__iter__ 返回 self，说明它本身就是迭代器", "__next__ 必须给出下一个值或抛 StopIteration", "n 归零时发出结束信号", "先自减再返回，产出 2、1、0", "返回本次的值", "构造实例，此时尚未消费", "两个 isinstance 都成立，Iterator 只抽象 __next__", "第一次 list 消耗全部三个值", "迭代器耗尽后第二次 list 得到空，且不报错", "内存文件对象模拟真实文件", "文件对象的 __iter__ 返回 self，只能读一遍", "同一个 list 每次 iter 都给出新的迭代器", "两次 iter 不是同一对象，故可反复遍历", "用两参数 iter 按固定大小读块", "lambda 每次读 size 个字符，返回空串时停止", "读到 &#39;ab&#39;、&#39;cd&#39;、&#39;ef&#39; 后遇空串结束", "count(10) 是无限迭代器，用 islice 只取 4 个", "chain 把两个列表串成一个迭代流", "takewhile 遇第一个不满足的元素即停，不再看后面的 2", "3.10+ 的 zip(strict=True) 对长度不等会抛异常", "长度不等，捕获 ValueError 而不是静默截断", "打印异常类型，验证严格对齐", "itertools 的 chain / islice / takewhile / groupby / tee 全部返回惰性迭代器，内存与单个元素相关", "3.7 起 PEP 479 把生成器内的 StopIteration 转成 RuntimeError；3.10 起 zip(strict=True) 长度不等抛 ValueError", "大文件、游标、分页 API 包成迭代器让调用方决定消费量；文件对象 iter(f) is f 只能读一遍", "迭代协议：iterable 实现 __iter__ 返回迭代器；iterator 实现 __next__，耗尽抛 StopIteration", "迭代器一次性带状态，耗尽后 list(it) 返回空且不报错；可迭代对象每次 iter 给新迭代器"]' title='第 025 讲 · 迭代协议：iterable、iterator 与惰性求值' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='可迭代对象实现 __iter__()，调用后返回一个迭代器；迭代器必须实现 __next__()，每次返回一个元素，耗尽时抛 StopIteration，并按约定实现 __iter__() 返回 self。for x in obj 的等价展开是：it = iter(obj); while True:' />


## Iterable 与 Iterator 对照

**Iterable 与 Iterator 对照**

| 维度 | 可迭代对象 Iterable | 迭代器 Iterator |
| --- | --- | --- |
| 必须实现 | __iter__ 返回迭代器 | __next__（__iter__ 由 mixin 返回 self） |
| 状态 | 通常无状态，可反复遍历 | 带状态、一次性，耗尽后产出空 |
| iter(obj) | 每次给出新的迭代器 | 通常返回 self |
| len() 支持 | 序列型可支持 | 不支持，需先物化或查 length_hint |
| 典型 | list / tuple / dict / range / 自定义容器 | 文件对象 / 生成器 / map / zip / enumerate |

<CodeTabs :tabs='[{"label": "主示例", "code": "import io\nfrom collections.abc import Iterator, Iterable\nimport itertools\n\nclass Countdown:\n    def __init__(self, n):\n        self.n = n\n    def __iter__(self):\n        return self\n    def __next__(self):\n        if self.n &lt;= 0:\n            raise StopIteration\n        self.n -= 1\n        return self.n\n\nc = Countdown(3)\nprint(&#39;is iterator&#39;, isinstance(c, Iterator), isinstance(c, Iterable))\nprint(&#39;first pass&#39;, list(c))\nprint(&#39;second pass&#39;, list(c))\n\nf = io.StringIO(&#39;a&#39; + chr(10) + &#39;b&#39; + chr(10))\nprint(&#39;file is its own iterator&#39;, iter(f) is f)\nlst = [1, 2]\nprint(&#39;list iter gives new&#39;, iter(lst) is not iter(lst))\n\ndef chunks(text, size):\n    src = io.StringIO(text)\n    return iter(lambda: src.read(size), &#39;&#39;)\nprint(&#39;read chunks&#39;, list(chunks(&#39;abcdef&#39;, 2)))\n\nprint(&#39;islice&#39;, list(itertools.islice(itertools.count(10), 4)))\nprint(&#39;chain&#39;, list(itertools.chain([1, 2], [3])))\nprint(&#39;takewhile&#39;, list(itertools.takewhile(lambda x: x &lt; 4, [1, 3, 5, 2])))\ntry:\n    print(list(zip([1, 2], [3], strict=True)))\nexcept ValueError as e:\n    print(&#39;zip strict&#39;, type(e).__name__)", "note": "两层协议：iterable 产出 iterator，iterator 记住位置"}, {"label": "对照 / 进阶", "code": "import itertools\n\ndata = [(&#39;a&#39;, 1), (&#39;a&#39;, 2), (&#39;b&#39;, 3), (&#39;b&#39;, 4)]\nfor key, group in itertools.groupby(data, key=lambda r: r[0]):\n    print(&#39;group&#39;, key, [r[1] for r in group])\n\na, b = itertools.tee([1, 2, 3], 2)\nprint(&#39;tee independent&#39;, list(a), list(b))\nprint(&#39;accumulate&#39;, list(itertools.accumulate([1, 2, 3, 4])))\nprint(&#39;zip_longest&#39;, list(itertools.zip_longest([1, 2], [&#39;a&#39;], fillvalue=&#39;-&#39;)))\n\nclass Bag:\n    def __init__(self, items): self.items = list(items)\n    def __iter__(self): return iter(self.items)\n\nbag = Bag([1, 2])\nprint(&#39;bag reusable&#39;, list(bag), list(bag))", "note": "iter() 的两种形式与 StopIteration 的版本约束"}]' title='两种写法切换看' />


## 迭代器为什么是一次性的：状态存在哪

<ConceptDiagram type='flow3' title='第 025 讲 · 两层协议：iterable 产出 iterator，iterator 记住位置' labels='两层协议：iterable 产出 itera|iter() 的两种形式与 StopIter|itertools、惰性求值与工程判据' caption='能自己实现一个惰性数据源' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

CPython 的迭代分两层：`iter(obj)` 先查 tp_iter 槽调用 `__iter__`，拿到的迭代器必须有 tp_iternext 槽（`__next__`）；for 循环编译出的 FOR_ITER 指令每次调用 next，捕获 StopIteration 后跳出，因此遍历结束是一个异常信号而不是长度判断。

迭代器把状态放在自身对象里（生成器还有 gi_frame 保存指令指针与局部变量），消耗一次就前进一步，耗尽后再次 next 仍抛 StopIteration，所以 `list(it)` 第二次得到空列表且不会报错，这正是把迭代器当列表用的静默陷阱。

可迭代对象与迭代器可以分离：list 的 `__iter__` 每次返回一个新的 list_iterator，因此能反复遍历；文件对象 TextIOWrapper 的 `__iter__` 返回 self，本身就是迭代器，所以只能读一遍。

`iter(callable, sentinel)` 是另一条构造路径：反复调用无参 callable，返回值等于 sentinel 时停止，不关心长度。

itertools 的工具全部基于这套协议在 C 层实现、返回迭代器而不物化结果，因此 chain / islice / takewhile 串起来后内存只与单个元素有关。3.7 起 PEP 479 把生成器内部意外抛出的 StopIteration 转成 RuntimeError，防止它伪装成正常结束。


## iter() 的两种形式与 StopIteration 的版本约束

`iter(obj)` 是单参数形式，调用 `obj.__iter__()`；

`iter(callable, sentinel)` 是两参数形式，反复调用一个无参 callable，返回值等于 sentinel 时停止，常用于按块读文件或读输入：`iter(lambda: f.read(64)`, '') 会一直读到空串为止，完全不需要知道总共有多少字节。

手动调用 `next(it)` 时，耗尽抛出的 StopIteration 要自己处理，而 for 循环帮你捕获了它。版本上有两条要记：Python 2 的 map / filter / zip 返回 list，Python 3 改为返回迭代器，需要 `list()` 才物化；

3.7 起 PEP 479 把生成器内部意外抛出的 StopIteration 转成 RuntimeError（generator raised StopIteration），防止它伪装成正常结束、悄悄截断循环，结束生成器应该用 return 而不是 raise StopIteration。

3.10 起 `zip(..., strict=True)` 会在各可迭代对象长度不等时抛 ValueError，避免静默截断。

迭代器还可以实现可选的 `__length_hint__`，`list(it)` 会用它预估容量，但那只是提示，不是真实长度。

```python
import itertools

data = [('a', 1), ('a', 2), ('b', 3), ('b', 4)]
for key, group in itertools.groupby(data, key=lambda r: r[0]):
    print('group', key, [r[1] for r in group])

a, b = itertools.tee([1, 2, 3], 2)
print('tee independent', list(a), list(b))
print('accumulate', list(itertools.accumulate([1, 2, 3, 4])))
print('zip_longest', list(itertools.zip_longest([1, 2], ['a'], fillvalue='-')))

class Bag:
    def __init__(self, items): self.items = list(items)
    def __iter__(self): return iter(self.items)

bag = Bag([1, 2])
print('bag reusable', list(bag), list(bag))
```

<OutputBox title='对照写法：先自己猜，再点开' output='group a [1, 2]\ngroup b [3, 4]\ntee independent [1, 2, 3] [1, 2, 3]\naccumulate [1, 3, 6, 10]\nzip_longest [(1, &#39;a&#39;), (2, &#39;-&#39;)]\nbag reusable [1, 2] [1, 2]' guess="true" />


### 手动 raise StopIteration 为什么变成 RuntimeError

**版本差异与失效信号**

| 版本 / 规则 | 行为 | 影响 |
| --- | --- | --- |
| Python 2 的 map / filter / zip | 返回 list | Py3 改为返回迭代器，需显式 list() |
| 3.7+ PEP 479 | 生成器内意外抛出的 StopIteration 转成 RuntimeError | 避免静默截断循环，便于排查 |
| 3.10+ zip(strict=True) | 长度不等抛 ValueError | 对齐数据前先校验，不静默截断 |
| iter(callable, sentinel) | 反复调用无参 callable 直到返回 sentinel | 读文件块、读输入流的惯用写法 |
| StopIteration | next() 耗尽时的信号 | for 循环捕获它结束，手动 next 要自己处理 |

<Callout type="warn" title='本讲最容易踩的坑' text='把迭代器当列表用，第二次遍历拿到空结果：迭代器一次性、带状态，耗尽后 next 一直抛 StopIteration，for 与 list 会静默得到空' />


## itertools 常用工具

**itertools 常用工具**

| 工具 | 作用 | 是否惰性或注意 |
| --- | --- | --- |
| chain(*iterables) | 串联多个可迭代对象 | 惰性 |
| islice(it, start, stop, step) | 对迭代器做切片 | 惰性，不支持负索引 |
| count / cycle / repeat | 无限或重复序列 | 无限，必须配 islice 或 takewhile |
| takewhile / dropwhile / filterfalse | 按谓词截取或过滤 | 惰性，takewhile 遇假即停 |
| groupby(it, key) | 按相邻相同 key 分组 | 需先按 key 排序，分组要及时消费 |
| tee(it, n) | 克隆 n 个独立迭代器 | 内部缓存，消费速度差大时内存增长 |
| accumulate / zip_longest / starmap | 累积、补长对齐、参数展开 | 惰性 |

```python
import io, inspect
from collections.abc import Iterator, Iterable

print('Iterator abstract', sorted(Iterator.__abstractmethods__))
print('Iterable abstract', sorted(Iterable.__abstractmethods__))
print('Iterator isabstract', inspect.isabstract(Iterator))
print('mixin iter', Iterator.__iter__.__qualname__)

f = io.StringIO('x')
print('file is Iterator', isinstance(f, Iterator))
it = iter([1, 2])
print('list_iterator type', type(it).__name__)
print('first', list(it), 'second', list(it))

def gen():
    yield 1
    raise StopIteration('boom')
try:
    list(gen())
except RuntimeError as e:
    print('PEP 479 wraps', type(e).__name__)
```

<OutputBox title='原理验证' output='Iterator abstract [&#39;__next__&#39;]\nIterable abstract [&#39;__iter__&#39;]\nIterator isabstract True\nmixin iter Iterator.__iter__\nfile is Iterator True\nlist_iterator type list_iterator\nfirst [1, 2] second []\nPEP 479 wraps RuntimeError' />


## 惰性求值省下的是哪部分内存

<FlowTimeline :steps='[{"title": "两层协议：iterable 产出 iterator，iterator 记住位置", "desc": "可迭代对象实现 __iter__()，调用后返回一个迭代器；迭代器必须实现 __ne…", "tone": "blue"}, {"title": "iter() 的两种形式与 StopIteration 的版本约束", "desc": "iter(obj) 是单参数形式，调用 obj.__iter__()；iter(ca…", "tone": "purple"}, {"title": "itertools、惰性求值与工程判据", "desc": "itertools 里几乎所有工具都基于迭代协议在 C 层实现、返回迭代器而不物化结…", "tone": "orange"}, {"title": "工程落地", "desc": "分页 API 客户端：把远端数据包装成惰性迭代器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

<Term word='__iter__ 与 __next__' text='可迭代对象实现 __iter__()，调用后返回一个迭代器；迭代器必须实现 __next__()，每次返回一个元素，耗尽时抛 StopIteration，并按约定实现 __iter__() 返回 self。for x in obj 的等价展开是：it = iter(obj); while True: try: x = ' />

<Term word='iter() 的两个参数形式' text='iter(obj) 是单参数形式，调用 obj.__iter__()；iter(callable, sentinel) 是两参数形式，反复调用一个无参 callable，返回值等于 sentinel 时停止，常用于按块读文件或读输入：iter(lambda: f.read(64), &#39;&#39;) 会一直读到空串为止，完全不需' />


## 惰性求值与工程判据

itertools 里几乎所有工具都基于迭代协议在 C 层实现、返回迭代器而不物化结果：`chain(*iterables)` 串联多个数据源，`islice(it, start, stop, step)` 对迭代器做惰性切片（不支持负索引），count / cycle / repeat 造无限序列（必须配 islice 或 takewhile 限制消费），takewhile / dropwhile / filterfalse 按谓词截取，`groupby(it, key)` 按相邻相同 key 分组（数据要先按 key 排序，且分组迭代器共享底层、要及时消费），`tee(it, n)` 克隆出 n 个独立迭代器（内部有缓存，分叉消费速度差大时内存会涨），accumulate / zip_longest / starmap 做累积、补长对齐与参数展开。

惰性求值的价值不是'更快'，而是内存占用与单个元素相关：大文件、数据库游标、分页 API 都应该包成迭代器，让调用方用 islice 决定消费多少，而不是一次性 `read()` 或 `fetchall()`。判据很简单：数据能不能反复遍历、要不要按下标访问、总规模是否远超内存——答完这三问再决定物化还是惰性。


## 分页 API 客户端：把远端数据包装成惰性迭代器

一个同步客户端要拉取分页接口的全量订单，直接写一个函数把所有页读进 list 再返回，页数一多内存就爆，且调用方只想取前 100 条也要等全量拉完。正确做法是把按页取数据封装成实现 `__iter__` / `__next__` 的迭代器：只在缓冲耗尽时才请求下一页，调用方用 islice 决定消费多少，内存恒定且与总页数无关。

下面用标准库模拟分页源，实现 PagedOrders 迭代器，并演示 `itertools.islice` 只取前 N 条、以及同一实例耗尽后再遍历得到空结果。

重点是把 IO 边界藏在迭代器里、把消费量交给调用方，测试时替换 fetch 函数即可，不必真发网络请求。

```python
import itertools

PAGES = [
    [101, 102],
    [103, 104],
    [105],
    [],
]

def fetch(page_no):
    return PAGES[page_no] if page_no < len(PAGES) else []

class PagedOrders:
    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.page = 0
        self.buffer = []
        self.pos = 0
    def __iter__(self):
        return self
    def __next__(self):
        while self.pos >= len(self.buffer):
            rows = self.fetcher(self.page)
            self.page += 1
            if not rows:
                raise StopIteration
            self.buffer = rows
            self.pos = 0
        value = self.buffer[self.pos]
        self.pos += 1
        return value

orders = PagedOrders(fetch)
print('all', list(orders))
print('first three', list(itertools.islice(PagedOrders(fetch), 3)))
print('exhausted again', list(orders))
```

<Callout type="idea" title='落地提示' text='大文件、数据库游标、分页 API 都该包成迭代器，让调用方决定消费多少，内存才不会随数据量线性增长' />

<CheckList id='P025b' title='上线前自检' :items='["能复现并解释「把迭代器当列表用，第二次遍历拿到空结果」", "能复现并解释「对文件对象遍历两次，第二次什么都没有」", "能复现并解释「在生成器里手动 raise StopIteration 想结」", "能用一条命令验证 __iter__ 与 __next__", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import itertools; print(list(itertools.islice(itertools.count(), 3)))"
```

把输入换成你自己的数据，观察结果是否仍符合 **__iter__ 与 __next__** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 迭代器一次性之后的练习

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把迭代器当列表用，第二次遍历拿到空结果 | 迭代器一次性、带状态，耗尽后 next 一直抛 StopIteration，for 与 list 会静默得到空 | 需要多次遍历就重新 iter(容器) 或用 itertools.tee；要长度先 list(it) 物化或查 __length_hint__ |
| 对文件对象遍历两次，第二次什么都没有 | 文件对象的 __iter__ 返回 self，本身就是迭代器，读完就耗尽 | 重新打开文件或先 seek(0)；要反复用就把行读进 list（注意内存） |
| 在生成器里手动 raise StopIteration 想结束迭代 | 3.7 起 PEP 479 把生成器内意外抛出的 StopIteration 转成 RuntimeError，避免静默截断 | 结束生成器用 return，不要用 raise StopIteration；需要提前终止就让循环自然结束或 return |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把迭代器当列表用，第二次遍历拿到空结果", "body": "迭代器一次性、带状态，耗尽后 next 一直抛 StopIteration，for 与 list 会静默得到空", "tip": "需要多次遍历就重新 iter(容器) 或用 itertools.tee；要长度先 list(it) 物化或查 __length_hint__"}, {"title": "第 2 步：对文件对象遍历两次，第二次什么都没有", "body": "文件对象的 __iter__ 返回 self，本身就是迭代器，读完就耗尽", "tip": "重新打开文件或先 seek(0)；要反复用就把行读进 list（注意内存）"}, {"title": "第 3 步：在生成器里手动 raise StopIter", "body": "3.7 起 PEP 479 把生成器内意外抛出的 StopIteration 转成 RuntimeError，避免静默截断", "tip": "结束生成器用 return，不要用 raise StopIteration；需要提前终止就让循环自然结束或 return"}]' />

<Exercise title='基础：自己实现一个可反复遍历的迭代器容器' task='定义一个类，__iter__ 每次返回新的迭代器（而不是 self），验证它能被 list() 遍历两次；再定义一个返回 self 的类，验证第二次为空。' solution='class Reusable:\n    def __init__(self, xs): self.xs = list(xs)\n    def __iter__(self): return iter(self.xs)\n\nclass OneShot:\n    def __init__(self, xs): self.it = iter(xs)\n    def __iter__(self): return self\n    def __next__(self): return next(self.it)\n\nr = Reusable([1, 2])\nprint(&#39;reusable&#39;, list(r), list(r))\no = OneShot([1, 2])\nprint(&#39;one shot&#39;, list(o), list(o))' explain='__iter__ 返回新迭代器时容器可反复遍历；返回 self 时对象本身就是迭代器、一次性。文件对象属于后一种，list 属于前一种。' />

<Exercise title='进阶：用 iter(callable, sentinel) 与 islice 处理无限流' task='用 itertools.count 造无限序列，用 islice 取前 5 个偶数；再用 iter(callable, sentinel) 读取固定大小的数据块直到空串，打印块列表。' solution='import io, itertools\nevens = (x for x in itertools.count(0) if x % 2 == 0)\nprint(&#39;first five evens&#39;, list(itertools.islice(evens, 5)))\n\ndef chunks(text, size):\n    src = io.StringIO(text)\n    return iter(lambda: src.read(size), &#39;&#39;)\nprint(&#39;chunks&#39;, list(chunks(&#39;abcdefg&#39;, 3)))' explain='count 是无限迭代器，必须配 islice 或 takewhile 限制消费量；iter(callable, sentinel) 反复调用无参 callable，直到返回 sentinel 才停，是读块与读输入的惯用写法。两者都不物化全量数据。' />

<Quiz no='025-1' q='为什么 list 能反复遍历而文件对象只能读一遍？' :options='["list 实现了 __len__", "list 的 __iter__ 每次返回新迭代器，文件对象的 __iter__ 返回 self", "文件对象没有 __iter__", "list 会缓存内容"]' answer="1" explain='可迭代对象与迭代器分离时每次 iter 给新迭代器；文件对象本身就是迭代器（iter(f) is f），读完即耗尽，要重读需 reopen 或 seek(0)。' />

<Quiz no='025-2' q='对已耗尽的迭代器再调用 list(it) 会？' :options='["抛 StopIteration", "返回空列表且不报错", "重新产出一遍元素", "抛 RuntimeError"]' answer="1" explain='迭代器一次性、带状态，耗尽后 next 持续抛 StopIteration；list() 把这个信号当作正常结束，于是静默返回空列表且不报错，这是最易踩的坑。' />

<Quiz no='025-3' q='3.7 起在生成器内部手动 raise StopIteration 会？' :options='["正常结束生成器", "被 PEP 479 转成 RuntimeError", "被忽略", "返回 None"]' answer="1" explain='PEP 479 把生成器内意外抛出的 StopIteration 转成 RuntimeError: generator raised StopIteration，防止它伪装成正常迭代结束；结束生成器应用 return。' />

<Predict no='025-P' q='it = iter([1, 2]); print(list(it), list(it)) 输出什么？' :options='["[1, 2] [1, 2]", "[1, 2] []", "抛 StopIteration"]' answer='1' output='[1, 2] []' explain='第一次 list(it) 消耗掉两个元素，迭代器耗尽；第二次 list(it) 立刻遇到 StopIteration，被当作正常结束，返回空列表且不报错。需要多次遍历应重新 iter(容器) 或先把结果存成 list。' />

<FillBlank no='025-F' tpl='___ io' :answers='["import"]' hint='回想本讲关于 __iter__ 与 __next__ 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 两层协议：iterable 产出 iterator，iterator 记住位置 的落点。' />

<KnowledgeCard :points='["迭代协议：iterable 实现 __iter__ 返回迭代器；iterator 实现 __next__，耗尽抛 StopIteration", "迭代器一次性带状态，耗尽后 list(it) 返回空且不报错；可迭代对象每次 iter 给新迭代器", "iter(callable, sentinel) 反复调用无参 callable 直到返回 sentinel，用于读文件块", "itertools 的 chain / islice / takewhile / groupby / tee 全部返回惰性迭代器，内存与单个元素相关", "3.7 起 PEP 479 把生成器内的 StopIteration 转成 RuntimeError；3.10 起 zip(strict=True) 长度不等抛 ValueError", "大文件、游标、分页 API 包成迭代器让调用方决定消费量；文件对象 iter(f) is f 只能读一遍"]' :pitfalls='["把迭代器当列表用，第二次遍历拿到空结果", "对文件对象遍历两次，第二次什么都没有", "在生成器里手动 raise StopIteration 想结束迭代", "把迭代器当列表用（先 len 再遍历、或遍历两次），第二次会拿到空结果，且不会报错"]' summary='迭代器是一次性、带状态的对象；可迭代对象每次 iter() 都给出新的迭代器，这就是列表能反复遍历而文件不能的原因' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 迭代协议：iterable 实现 __iter__ 返回迭代器；iterator 实现 __next__，耗尽抛 StopIteration | 建立直觉 |
| 迭代器一次性带状态，耗尽后 list(it) 返回空且不报错；可迭代对象每次 iter 给新迭代器 | 跑通示例 |
| iter(callable, sentinel) 反复调用无参 callable 直到返回 sentinel，用于读文件块 | 深入边界 |
| itertools 的 chain / islice / takewhile / groupby / tee 全部返回惰性迭代器，内存与单个元素相关 | 工程落地 |
| 3.7 起 PEP 479 把生成器内的 StopIteration 转成 RuntimeError；3.10 起 zip(strict=True) 长度不等抛 ValueError | 随堂检测 |
| 大文件、游标、分页 API 包成迭代器让调用方决定消费量；文件对象 iter(f) is f 只能读一遍 | 复盘 |

1. 迭代协议：iterable 实现 __iter__ 返回迭代器；iterator 实现 __next__，耗尽抛 StopIteration

2. 迭代器一次性带状态，耗尽后 list(it) 返回空且不报错；可迭代对象每次 iter 给新迭代器

3. iter(callable, sentinel) 反复调用无参 callable 直到返回 sentinel，用于读文件块

[下一讲：生成器与 yield：send / throw / close](/containers/generator)
