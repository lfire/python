---
title: 第 031 讲 · 高阶函数、lambda 与 map / filter / reduce
description: 用函数组合代替重复循环
---

<StageHeader stage='L3 · 函数与抽象' level='★★☆☆☆' time='30 分钟' goal='用函数组合代替重复循环' prereq='第 030 讲 · 作用域、LEGB 与闭包延迟绑定' />

# 第 031 讲 · 高阶函数、lambda 与 map / filter / reduce

知道了名字怎么被捕获，函数就不只是一段被调用的代码，而能像数据一样递来递去，高阶函数从概念变成了顺手的工具。这一步把变化的逻辑从固定的遍历里抽出来，让策略当作值传递。面对一批数据，过滤、换算、汇总往往只差中间一小步，却要为每种需求各写一个循环。

起步先看 map 与 filter 的惰性，明白结果为何一次性；顺着往下是 reduce、operator 与 lambda 各自的边界；收尾把函数作为值放进回调、排序键和分派表，看组合怎样代替堆叠的循环。要用到迭代器与生成器那几讲，以及刚熟悉的闭包；读完你能把做什么写成参数，把怎么遍历交给工具。


## 一个数据清洗脚本，循环套循环越写越乱

一个数据清洗管道要把一批字符串转成整数、过滤掉非正数、再求乘积。朴素写法是三个连续的 for 循环加临时列表，每个循环里重复写 append 与条件判断，改一步规则要动三处；

有人改成一行超长 lambda 套 map、filter、reduce，结果调试时既没有行号也看不到中间值，reduce 遇到空输入直接抛 `TypeError`（of empty iterable with no initial value），而线上空批次恰恰是常态。

更隐蔽的是把 map 的结果当列表用了两次，第二次拿到空列表却查不出原因。

本讲把三类工具讲清楚：map / filter 是惰性迭代器（Python 3 起），reduce 在 functools 里且必须给 initializer 兜底，operator 模块用 C 实现替代 lambda 更快，以及什么时候推导式与命名函数反而是更好的选择。

<Callout type="warn" title='先看一个真实会出错的写法' text='reduce 对空批次抛 TypeError: reduce() of empty iterable with no initial value：没给 initializer 时 reduce 需要至少一个元素作起点，而线上空输入是常态' />

<Callout type="tip" title='核心心智模型' text='Python 2 的 map、filter 返回 list，Python 3 起返回迭代器（map 对象 / filter 对象），惰性求值、只能消费一次；只有 `list(...)` 或 `for` 循环才真正物化结果。时间复杂度 `O(n)`、额外空间 `O(1)`（不含输出），而列表推导式立即…' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段三 · 函数与抽象 |
| 前置 | 第 030 讲 · 作用域、LEGB 与闭包延迟绑定 |
| 难度 / 建议时长 | ★★☆☆☆ · 30 分钟 |
| 本讲新增 | 函数作为值、map / filter 的惰性、functools.reduce |
| 一句话目标 | 用函数组合代替重复循环 |
| 为下一讲铺垫 | 装饰器原理与 functools.wraps |


## map / filter 的惰性与一次性

Python 2 的 map、filter 返回 list，Python 3 起返回迭代器（map 对象 / filter 对象），惰性求值、只能消费一次；只有 `list(...)` 或 `for` 循环才真正物化结果。

时间复杂度 `O(n)`、额外空间 `O(1)`（不含输出），而列表推导式立即构造完整 list，空间是 `O(n)`。

`map(func, *iterables)` 可传多个可迭代对象，func 按位置接收多个参数，迭代长度以最短的那个为准，与内置 `zip` 一致，而不像 `itertools.zip_longest` 会补齐；

`filter(func, iterable)` 在 func 为 None 时退化为过滤真值元素，`filter(None, seq)` 等价于取所有真值。

迭代器一次性是最常见的踩坑点：先 `list(m)` 消费完，再 `list(m)` 得到空列表，因为 `__next__` 已经抛过 `StopIteration`。惰性还带来时序边界：func 里的异常、副作用甚至读取外部状态，都要等到消费时才发生，传入生成器时尤其明显。

判定方式很直接：`iter(m) is m` 为真说明它自身就是迭代器，`type(m).__name__` 给出 map 或 filter。

```python
from functools import reduce
from operator import mul

raw = ['3', '-2', '0', '4']
nums = list(map(int, raw))
pos = list(filter(lambda x: x > 0, nums))
print(nums, pos)
m = map(int, raw)
print(list(m), list(m))
print(reduce(mul, [3, 4], 1))
print(reduce(mul, [], 1))
try:
    print(reduce(mul, []))
except TypeError as e:
    print(type(e).__name__, str(e))
```

<OutputBox title='主示例运行结果' output='[3, -2, 0, 4] [3, 4]\n[3, -2, 0, 4] []\n12\n1\nTypeError reduce() of empty iterable with no initial value' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from functools import reduce\nfrom operator import mul\n\nraw = [&#39;3&#39;, &#39;-2&#39;, &#39;0&#39;, &#39;4&#39;]\nnums = list(map(int, raw))\npos = list(filter(lambda x: x &gt; 0, nums))\nprint(nums, pos)\nm = map(int, raw)\nprint(list(m), list(m))\nprint(reduce(mul, [3, 4], 1))\nprint(reduce(mul, [], 1))\ntry:\n    print(reduce(mul, []))\nexcept TypeError as e:\n    print(type(e).__name__, str(e))' :notes='["从 functools 导入 reduce：Python 3 起它不再是内建", "从 operator 导入 C 实现的乘法函数 mul", "空行，只用于分隔逻辑块，不影响执行结果。", "准备含负数、零与非数字字符的原始批次", "map(int, raw) 惰性转换，list 才物化成整数列表", "filter 配合短 lambda 只保留正数", "打印转换结果与过滤结果", "再次构造一个 map 迭代器，用于验证一次性", "第一次 list 消费完，第二次 list 得到空列表", "带 initializer=1 的累积：1*3*4 得 12", "空序列带 initializer 时直接返回 1，不报错", "准备捕获不带初值的空序列异常", "无 initializer 且序列为空，reduce 找不到起点", "捕获预期的 TypeError", "打印异常类型与消息"]' title='第 031 讲 · 高阶函数、lambda 与 map / filter / reduce' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import dis

calls = []
def twice(x):
    calls.append(x)
    return x * 2

m = map(twice, [1, 2, 3])
print(type(m).__name__, iter(m) is m, len(calls))
print(list(m), len(calls))
print(list(m), len(calls))
print(twice.__name__, (lambda x: x).__name__)
ops = [i.opname for i in dis.get_instructions(twice)]
print('RETURN_VALUE' in ops, 'BUILD_TUPLE' in ops)
```

<OutputBox title='原理验证' output='map True 0\n[2, 4, 6] 3\n[] 3\ntwice &lt;lambda&gt;\nTrue False' />


## 三个高阶工具的行为对照

**三个高阶工具的行为对照**

| 工具 | 返回 | 惰性 | 空输入 | 复杂度 |
| --- | --- | --- | --- | --- |
| map(f, *its) | map 迭代器 | 是，消费时才调用 f | 产出空迭代器 | 时间 O(n)，额外空间 O(1) |
| filter(f, it) | filter 迭代器 | 是 | 产出空迭代器 | 时间 O(n)，额外空间 O(1) |
| reduce(f, it[, init]) | 单个累积值 | 否，立即消费 | 无 init 抛 TypeError，有 init 返回 init | 时间 O(n)，空间 O(1) |
| 列表推导式 | list | 否，立即构造 | 空 list | 时间 O(n)，空间 O(n) |

<CodeTabs :tabs='[{"label": "主示例", "code": "from functools import reduce\nfrom operator import mul\n\nraw = [&#39;3&#39;, &#39;-2&#39;, &#39;0&#39;, &#39;4&#39;]\nnums = list(map(int, raw))\npos = list(filter(lambda x: x &gt; 0, nums))\nprint(nums, pos)\nm = map(int, raw)\nprint(list(m), list(m))\nprint(reduce(mul, [3, 4], 1))\nprint(reduce(mul, [], 1))\ntry:\n    print(reduce(mul, []))\nexcept TypeError as e:\n    print(type(e).__name__, str(e))", "note": "map / filter 的惰性与一次性"}, {"label": "对照 / 进阶", "code": "from operator import itemgetter, add, mul\nfrom functools import reduce\n\nrows = [(&#39;a&#39;, 3), (&#39;b&#39;, 1), (&#39;c&#39;, 2)]\nprint(sorted(rows, key=itemgetter(1)))\nprint(list(map(itemgetter(1), rows)))\n\nOPS = {&#39;add&#39;: add, &#39;mul&#39;: mul}\ndef apply(op, a, b):\n    return OPS[op](a, b)\nprint(apply(&#39;mul&#39;, 3, 4), apply(&#39;add&#39;, 3, 4))\n\nf = filter(lambda x: x &gt; 1, [1, 2, 3])\nprint(list(f), list(f))\nprint(reduce(add, (1, 2, 3)))", "note": "reduce、operator 与 lambda 的适用边界"}]' title='两种写法切换看' />

<Term word='函数作为值' text='Python 2 的 map、filter 返回 list，Python 3 起返回迭代器（map 对象 / filter 对象），惰性求值、只能消费一次；只有 `list(...)` 或 `for` 循环才真正物化结果。时间复杂度 `O(n)`、额外空间 `O(1)`（不含输出），而列表推导式立即构造完整 list…' />

<Term word='map / filter 的惰性' text='`functools.reduce` 从左到右把二元函数累积到一个值：`reduce(add, [1, 2, 3], 0)` 得到 6。Python 3 把 reduce 移出内建、放进 functools，调用前要从 `functools` 里取出 `reduce`。无 initializer 时它取第一个元素作起点…' />


## reduce、operator 与 lambda 的适用边界

`functools.reduce` 从左到右把二元函数累积到一个值：`reduce(add, [1, 2, 3], 0)` 得到 6。

Python 3 把 reduce 移出内建、放进 functools，调用前要从 `functools` 里取出 `reduce`。无 initializer 时它取第一个元素作起点，空序列直接抛 `TypeError`（of empty iterable with no initial value）；

单元素序列无 initializer 则直接返回该元素且不调用 function。initializer 的工程价值就是给空批次一个单位元（加法的 0、乘法的 1、字符串拼接的空串），让空输入不报错又不改变非空结果。

operator 模块提供 `add`、`mul`、`itemgetter`、`attrgetter`、`methodcaller` 等 C 实现的可调用对象，`itemgetter(1)` 比 `lambda x: x[1]` 更快、可 pickle，作为 `sorted(key=)` 与 `max(key=)` 的键函数尤其合适。

lambda 只能含单个表达式、不能有语句与注解（参数可带默认值），且 `__name__` 恒为字符串 `<lambda>`，traceback 里难以定位；逻辑一复杂就应写命名 def。

```python
from operator import itemgetter, add, mul
from functools import reduce

rows = [('a', 3), ('b', 1), ('c', 2)]
print(sorted(rows, key=itemgetter(1)))
print(list(map(itemgetter(1), rows)))

OPS = {'add': add, 'mul': mul}
def apply(op, a, b):
    return OPS[op](a, b)
print(apply('mul', 3, 4), apply('add', 3, 4))

f = filter(lambda x: x > 1, [1, 2, 3])
print(list(f), list(f))
print(reduce(add, (1, 2, 3)))
```

<OutputBox title='对照写法：先自己猜，再点开' output='[(&#39;b&#39;, 1), (&#39;c&#39;, 2), (&#39;a&#39;, 3)]\n[3, 1, 2]\n12 7\n[2, 3] []\n6' guess="true" />

<Predict no='031-1' q='m = map(str, [1, 2]); print(list(m), list(m)) 输出什么？' :options='["[&#39;1&#39;, &#39;2&#39;] []", "[&#39;1&#39;, &#39;2&#39;] [&#39;1&#39;, &#39;2&#39;]", "&lt;map object at ...&gt; []"]' answer='0' output='[&#39;1&#39;, &#39;2&#39;] []' explain='map 是一次性迭代器：第一次 list 消费完所有元素，迭代器随即耗尽，第二次 list 只能得到空列表。' />


## 函数作为值：回调、键函数与分派表

高阶函数的价值是把变化的部分（做什么）从固定的部分（怎么遍历）里抽出来，让处理逻辑像数据一样传递。`sorted` 对每个元素调用一次 key 函数，CPython 先把所有键算好再比较（decorate-sort-undecorate 思路），因此 key 的调用次数恰为 n，比旧式 cmp 两两比较高效；

max、min 同理。

分派表是 `dict[str, callable]`，把一长串 `if/elif` 分派换成一次查表，插件注册、回调、依赖注入都建立在这之上。

`functools.partial`（第 034 讲展开）与函数组合能把多参数函数适配成回调接口要求的单参数可调用对象。

要注意开销：每次回调都是一次 Python 层函数调用与字节码分派，密集数值循环里会被放大，此时内置的 `sum`、`min`、`sorted` 走 C 实现更快。选型判据也在这里：需要过滤加变换一步完成、或要复用中间结果时，列表/生成器推导式通常更可读；已有命名函数、或要保留惰性管道时，map / filter 更合适。

CPython 里 map 与 filter 返回的是专用的迭代器对象，内部只保存函数引用与底层迭代器，`__next__` 被调用时才取出一个元素、执行 func 并返回结果，因此构造阶段完全不触碰数据、func 一次都不会调用；

迭代器自身实现 `__iter__` 返回 self，耗尽后 `__next__` 抛 `StopIteration`，再 list 便得到空列表，这就是一次性的来源。

reduce 走的是另一条路径：它在 C 层维护一个累加器，若给了 initializer 就以它为起点，否则先取第一个元素作起点（空序列此时抛 `TypeError`），随后对每个剩余元素调用一次二元 function。

operator 模块的 `add`、`mul`、`itemgetter` 等是 C 层对 PyObject 操作的封装，省去了 Python 层 lambda 的帧创建与字节码分派；用作 `sorted` 的 key 时，CPython 先遍历一次把所有键算好再排序，所以 key 函数对每个元素只调用一次。

lambda 编译出的仍是标准 function 对象，只是 `co_name` 被写成 `<lambda>`、且语法层限定函数体为单表达式，这解释了它在 traceback 里缺乏可定位的名字。

<ConceptDiagram type='flow4' title='第 031 讲 · map / filter 的惰性与一次性' labels='map / filter 的惰性与一次性|reduce、operator 与 lamb…|函数作为值：回调、键函数与分派表|partial 与组合' caption='用函数组合代替重复循环' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 版本迁移差异与场景选型决策

**版本与迁移差异**

| 变化 | 版本 | 细节 |
| --- | --- | --- |
| map / filter 返回迭代器 | 3.0 | Python 2 返回 list，迁移需显式 list(...) |
| reduce 移入 functools | 3.0 | 不再是内建，须 from functools import reduce |
| 列表推导式独立作用域 | 3.0 | 循环变量不泄漏到外层，影响 lambda 捕获 |
| operator.itemgetter / attrgetter | 长期稳定 | C 实现，可作 key，比等价 lambda 快且可 pickle |

**场景选型：推导式、命名函数还是 lambda**

| 场景 | 首选 | 原因 |
| --- | --- | --- |
| 过滤加变换一步完成 | 列表 / 生成器推导式 | 一次遍历、可读、中间值可见 |
| 已有命名函数、要惰性管道 | map / filter | 避免重复循环，保留惰性 |
| 按字段或属性排序取键 | operator.itemgetter / attrgetter | C 实现更快，可 pickle，语义明确 |
| 累积聚合且输入可能为空 | reduce(f, it, init) 或内置 sum | init 兜底空输入；内置 sum / min 走 C |
| 逻辑超过一个表达式 | 命名函数 def | lambda 只能单表达式、__name__ 为 &lt;lambda>，难调试 |

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| reduce 对空批次抛 TypeError: reduce() of empty iterable with no initial value | 没给 initializer 时 reduce 需要至少一个元素作起点，而线上空输入是常态 | 始终传单位元 initializer：加法 0、乘法 1、拼接空串；或改用 sum 等内置聚合 |
| 把 map / filter 结果当列表复用，第二次得到空 | Python 3 的 map / filter 是一次性迭代器，消费完就耗尽 | 需要复用就 list(...) 物化一次，或每次重新构造迭代器 |
| 长 lambda 塞进 sorted key 或 map，出错时无从定位 | lambda 只能单表达式、__name__ 恒为 &lt;lambda>，traceback 与日志里没有有意义的名字 | 复杂逻辑写命名 def 并用 __name__ 打日志；取字段或属性用 operator.itemgetter / attrgetter |

<CheckList id='P031a' title='学完你应当能' :items='["能讲清 map / filter 的惰性与一次性", "能讲清 reduce、operator 与 lambda 的适用边界", "能讲清 函数作为值：回调、键函数与分派表", "能在工程里处理 partial 与组合"]' />


## 可配置的数据管道：变换链、过滤与空批次兜底

一个日志聚合器每天要处理几百个批次，每批的字段变换规则不同、且允许整批为空。把变换写成可传入的函数列表、用 map 串成惰性链，再用 filter 过滤，能把「做什么」与「怎么遍历」彻底分开：新增一条规则只需往列表里加一个函数，不必改动循环骨架。空批次则靠 reduce 的单位元兜底，避免半夜因为一个空文件把任务打挂。

下面用标准库实现 pipeline：它接收变换函数列表与一个谓词，串接 map 后过滤并物化；再演示用 `operator.add` 累加、以及给空输入传初值 1 的乘法 reduce 不报错。真实工程还应把每批的输入行数、过滤后行数与耗时记进日志。

```python
from functools import reduce
from operator import add, mul

def pipeline(rows, transforms, predicate):
    stream = rows
    for t in transforms:
        stream = map(t, stream)
    kept = filter(predicate, stream)
    return list(kept)

data = ['3', '4', 'x', '5']

def to_int(s):
    try:
        return int(s)
    except ValueError:
        return 0

good = pipeline(data, [to_int], lambda x: x > 0)
print(good)
print(reduce(add, good, 0))
print(reduce(mul, [], 1))
```

<Callout type="idea" title='落地提示' text='回调、排序键、策略表、插件注册本质都是高阶函数，框架里的依赖注入也建立在这之上' />

<CheckList id='P031b' title='上线前自检' :items='["能复现并解释「reduce 对空批次抛 TypeError: reduce…」", "能复现并解释「把 map / filter 结果当列表复用，第二次得到空」", "能复现并解释「长 lambda 塞进 sorted key 或 map，出…」", "能用一条命令验证 函数作为值", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import inspect; print(inspect.signature(print))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 函数作为值 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：reduce 对空批次抛 TypeError…", "body": "没给 initializer 时 reduce 需要至少一个元素作起点，而线上空输入是常态", "tip": "始终传单位元 initializer：加法 0、乘法 1、拼接空串；或改用 sum 等内置聚合"}, {"title": "第 2 步：把 map / filter 结果当列表复用…", "body": "Python 3 的 map / filter 是一次性迭代器，消费完就耗尽", "tip": "需要复用就 list(...) 物化一次，或每次重新构造迭代器"}, {"title": "第 3 步：长 lambda 塞进 sorted key…", "body": "lambda 只能单表达式、__name__ 恒为 &lt;lambda&gt;，traceback 与日志里没有有意义的名字", "tip": "复杂逻辑写命名 def 并用 __name__ 打日志；取字段或属性用 operator.itemgetter / attrgetter"}]' />

<Callout type="warn" title='本讲最容易踩的坑' text='reduce 对空批次抛 TypeError: reduce() of empty iterable with no initial value：没给 initializer 时 reduce 需要至少一个元素作起点，而线上空输入是常态' />


## 动手：把循环改写成管道

<Exercise title='基础：验证迭代器一次性与 reduce 初值' task='构造 map 迭代器消费两次观察差异；再分别用带初值、不带初值的 reduce 处理空序列，打印结果与异常。' solution='from functools import reduce\nfrom operator import mul\n\nm = map(lambda x: x * 2, [1, 2, 3])\nprint(list(m))\nprint(list(m))\nprint(reduce(mul, [2, 3, 4], 1))\ntry:\n    reduce(mul, [])\nexcept TypeError as e:\n    print(type(e).__name__, str(e))' explain='map 是一次性迭代器，第二次 list 为空；initializer 让空序列返回单位元，不带初值则抛 TypeError。' />

<Exercise title='进阶：operator 作键函数与字典分派' task='用 operator.itemgetter(1) 给一组元组按第二项排序、求最大，再用一个 dict 映射表把字符串分派到 sum 与 len，打印结果。' solution='from operator import itemgetter\n\nrows = [(&#39;a&#39;, 2), (&#39;b&#39;, 1), (&#39;c&#39;, 2)]\nprint(sorted(rows, key=itemgetter(1)))\nprint(max(rows, key=itemgetter(1)))\nOPS = {&#39;sum&#39;: sum, &#39;len&#39;: len}\nprint(OPS[&#39;sum&#39;]([1, 2, 3]), OPS[&#39;len&#39;]([1, 2, 3]))' explain='itemgetter 是 C 实现且语义明确；映射表把一串条件分派变成一次字典查表，新增操作只需注册一个可调用对象。' />

<Quiz no='031-2' q='Python 3 里 map(f, seq) 返回的是什么？' :options='["一次性惰性迭代器 map 对象", "list", "tuple", "generator 对象"]' answer="0" explain='Python 3 起 map 返回专用的 map 迭代器（不是 generator），构造时不调用 f，只有 list() 或 for 才消费，且只能消费一次。' />

<Quiz no='031-3' q='reduce(f, [], init) 与 reduce(f, []) 的区别是？' :options='["前者返回 init，后者抛 TypeError", "两者都返回 init", "两者都抛 TypeError", "前者抛 TypeError，后者返回 None"]' answer="0" explain='initializer 充当累加起点，空序列时直接返回它；没有 initializer 时 reduce 需要至少一个元素作起点，空序列抛 reduce() of empty iterable with no initial value。' />

<Quiz no='031-4' q='给 sorted 取元组的第二项作键，更合适的写法是？' :options='["operator.itemgetter(1)", "lambda r: r[1] 总是更快", "filter(None, ...)", "map(int, ...)"]' answer="0" explain='itemgetter 是 C 实现、可 pickle、语义明确，作 key 时每元素只调一次；等价 lambda 未必更快且 __name__ 为 &lt;lambda&gt; 难调试。' />

<FillBlank no='031-5' tpl='from functools  ___ reduce' :answers='["import"]' hint='回想本讲关于 函数作为值 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 map / filter 的惰性与一次性 的落点。' />

<KnowledgeCard :points='["Python 3 起 map / filter 返回一次性惰性迭代器（不是 generator），构造时不调用 func，list() 才消费", "reduce 在 functools（3.0 移出内建，用前 from functools import reduce）；无 initializer 且空序列抛 TypeError，工程上传单位元兜底", "map(f, *iterables) 多可迭代以最短为准；filter(None, seq) 过滤掉所有假值元素", "operator.itemgetter / attrgetter / add / mul 是 C 实现，作 key 更快且可 pickle；sorted 的 key 对每元素只调一次", "lambda 只能单表达式、__name__ 恒为 &lt;lambda&gt;；复杂逻辑用命名 def，过滤加变换优先推导式", "回调、排序键、分派表、插件注册本质都是把函数当值传递"]' :pitfalls='["reduce 对空批次抛 TypeError: reduce() of empty iterable with no initial value", "把 map / filter 结果当列表复用，第二次得到空", "长 lambda 塞进 sorted key 或 map，出错时无从定位", "为了炫技写长 lambda，可调试性与可读性都会变差；命名函数配合推导式往往更好"]' summary='高阶函数的价值是把变化的部分（做什么）从固定的部分（怎么遍历）里抽出来，让策略可以像数据一样传递' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| Python 3 起 map / filter 返回一次性惰性迭代器（不是 generator），构造时不调用 func，list() 才消费 | 建立直觉 |
| reduce 在 functools（3.0 移出内建，用前 from functools import reduce）；无 initializer 且空序列抛 TypeError，工程上传单位元兜底 | 跑通示例 |
| map(f, *iterables) 多可迭代以最短为准；filter(None, seq) 过滤掉所有假值元素 | 深入边界 |
| operator.itemgetter / attrgetter / add / mul 是 C 实现，作 key 更快且可 pickle；sorted 的 key 对每元素只调一次 | 工程落地 |
| lambda 只能单表达式、__name__ 恒为 &lt;lambda>；复杂逻辑用命名 def，过滤加变换优先推导式 | 随堂检测 |
| 回调、排序键、分派表、插件注册本质都是把函数当值传递 | 复盘 |

1. Python 3 起 map / filter 返回一次性惰性迭代器（不是 generator），构造时不调用 func，list() 才消费

2. reduce 在 functools（3.0 移出内建，用前 from functools import reduce）；无 initializer 且空序列抛 TypeError，工程上传单位元兜底

3. map(f, *iterables) 多可迭代以最短为准；filter(None, seq) 过滤掉所有假值元素

[下一讲：装饰器原理与 functools.wraps](/functions/decorator)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/031-higher-order.py`

```bash
python3 examples/lessons/031-higher-order.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/031-higher-order.py) · [全部示例代码索引](/examples/)
