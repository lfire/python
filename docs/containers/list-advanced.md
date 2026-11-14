---
title: 第 019 讲 · list 进阶：切片赋值、排序与常见陷阱
description: 写出正确且高效的列表处理代码
---

<StageHeader stage='L2 · 容器与序列' level='★★☆☆☆' time='30 分钟' goal='写出正确且高效的列表处理代码' prereq='第 018 讲 · list：动态数组、操作与时间复杂度' />

# 第 019 讲 · list 进阶：切片赋值、排序与常见陷阱

能装、能取之后，接着就是怎么摆弄这串数据：改一段、排个序、按条件删几项。上一讲算清了动作成本，这一讲专治那些不报错、结果却不对的写法，它们多半来自对引用和默认行为的误判。

有人初始化一张棋盘，改左上角一格，整列却跟着变；想删掉所有偶数，遍历一遍剩下一半；把排序结果赋给变量，拿到的始终是个空值。我们先说切片赋值里普通切片能变长、带步长必须等量，再看原地排序与返回新列表的差别、排序键只算一次；最后把列表乘法、遍历时修改这几处坑钉实。需要你熟悉列表的增删改查与循环。学完你能写出正确又省力的批量处理，也知道何时该让推导式接手。


## 改一格，二维列表整行都变了

一个后台任务要初始化 3×3 的棋盘，工程师写了 `board = [[0] * 3] * 3`，随后 `board[0][0] = 1`，界面上却整列都变成了 1；

排查两小时才发现 `*` 重复的是同一行的引用，三行指向同一个 `list`。同一个迭代里还有第二处事故：为了删掉所有偶数，写 `for x in nums:` 若 x 为偶数就 `nums.remove(x)`，结果列表里留下一半偶数，因为 `for` 的内部下标在删除后跨过了前移的元素。

第三处是把 `sort()` 的返回值赋给 `result` 就拿去用，`result` 恒为 `None`，下游直接崩。这三处都不是语法错误，而是对「引用、迭代下标、返回值约定」三个默认行为的误判。本讲把切片赋值、`TimSort` 的稳定性与 `key` 求值次数、列表乘法、遍历修改这四组规则逐条钉死。

<Callout type="warn" title='先看一个真实会出错的写法' text='[[0] * 3] * 3 改一格变成改一整行：* 对 list 做的是引用重复，三行指向同一个 list 对象' />


## 切片赋值：普通切片可变长，扩展切片必须等长

切片不只是读取，写在赋值号左边就是原地替换。`a[i:j] = seq` 会把 i 到 j 这一段整体换成 `seq` 的元素，左右长度可以不同，因此能同时完成删除、插入与替换，列表长度随之改变；

`a[:] = []` 等价于 `a.clear()`（3.3+），是原地清空且所有指向该列表的别名都能看到变化，而 `a = []` 只是重新绑定名字。

带步长的扩展切片 `a[::2] = seq` 规则更严：右侧序列长度必须与切片选中的元素个数严格相等，否则抛 `ValueError`，提示两边长度对不上——因为步长大于 1 时无法靠移动后续元素来吸收长度差。`del a[::2]` 同样按步长删除。切片赋值右侧可以是任意可迭代对象，CPython 会先把它物化成序列再写入。

另一个相关约定是 `list.sort` 与 `sorted`：`key=None`、`reverse=False` 都是仅关键字参数，前者原地排序并按 API 约定返回 `None`，后者接受任意可迭代对象并构造新 `list`——把 `sort()` 的返回值赋给变量是最高频的误用。

```python
from operator import itemgetter

pairs = [('b', 2), ('a', 1), ('a', 3), ('b', 1)]
print('sort returns', pairs.sort(key=itemgetter(0)))
print('after sort', pairs)
print('stable for equal keys', [p[1] for p in pairs if p[0] == 'a'])

src = [('x', 3), ('y', 1), ('z', 2)]
new = sorted(src, key=itemgetter(1))
print('sorted new list', new, 'src intact', src)

calls = []
def key_count(record):
    calls.append(record)
    return record[1]
sorted(src, key=key_count)
print('key calls', len(calls), 'equals len', len(calls) == len(src))

a = [0, 1, 2, 3, 4]
a[1:3] = ['a', 'b', 'c']
print('slice assign changes length', a)
try:
    a[::2] = [1, 2]
except ValueError as e:
    print('extended slice error', type(e).__name__)

grid = [[0] * 3] * 3
grid[0][0] = 9
print('shared rows', grid[0] is grid[1], grid)
fixed = [[0] * 3 for _ in range(3)]
fixed[0][0] = 9
print('fixed rows', fixed[0] is fixed[1], fixed[0])

nums = [1, 2, 3, 4, 5]
for x in nums[:]:
    if x % 2 == 0:
        nums.remove(x)
print('safe removal', nums)
```

<OutputBox title='主示例运行结果' output='sort returns None\nafter sort [(&#39;a&#39;, 1), (&#39;a&#39;, 3), (&#39;b&#39;, 2), (&#39;b&#39;, 1)]\nstable for equal keys [1, 3]\nsorted new list [(&#39;y&#39;, 1), (&#39;z&#39;, 2), (&#39;x&#39;, 3)] src intact [(&#39;x&#39;, 3), (&#39;y&#39;, 1), (&#39;z&#39;, 2)]\nkey calls 3 equals len True\nslice assign changes length [0, &#39;a&#39;, &#39;b&#39;, &#39;c&#39;, 3, 4]\nextended slice error ValueError\nshared rows True [[9, 0, 0], [9, 0, 0], [9, 0, 0]]\nfixed rows False [9, 0, 0]\nsafe removal [1, 3, 5]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from operator import itemgetter\n\npairs = [(&#39;b&#39;, 2), (&#39;a&#39;, 1), (&#39;a&#39;, 3), (&#39;b&#39;, 1)]\nprint(&#39;sort returns&#39;, pairs.sort(key=itemgetter(0)))\nprint(&#39;after sort&#39;, pairs)\nprint(&#39;stable for equal keys&#39;, [p[1] for p in pairs if p[0] == &#39;a&#39;])\n\nsrc = [(&#39;x&#39;, 3), (&#39;y&#39;, 1), (&#39;z&#39;, 2)]\nnew = sorted(src, key=itemgetter(1))\nprint(&#39;sorted new list&#39;, new, &#39;src intact&#39;, src)\n\ncalls = []\ndef key_count(record):\n    calls.append(record)\n    return record[1]\nsorted(src, key=key_count)\nprint(&#39;key calls&#39;, len(calls), &#39;equals len&#39;, len(calls) == len(src))\n\na = [0, 1, 2, 3, 4]\na[1:3] = [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;]\nprint(&#39;slice assign changes length&#39;, a)\ntry:\n    a[::2] = [1, 2]\nexcept ValueError as e:\n    print(&#39;extended slice error&#39;, type(e).__name__)\n\ngrid = [[0] * 3] * 3\ngrid[0][0] = 9\nprint(&#39;shared rows&#39;, grid[0] is grid[1], grid)\nfixed = [[0] * 3 for _ in range(3)]\nfixed[0][0] = 9\nprint(&#39;fixed rows&#39;, fixed[0] is fixed[1], fixed[0])\n\nnums = [1, 2, 3, 4, 5]\nfor x in nums[:]:\n    if x % 2 == 0:\n        nums.remove(x)\nprint(&#39;safe removal&#39;, nums)' :notes='["导入 itemgetter，C 层按位置取字段作为排序键", "空行，只用于分隔逻辑块，不影响执行结果。", "四组记录，两组 key 相同用于检验稳定性", "list.sort 是原地方法，按约定返回 None", "排序结果按第一个字段升序，同 key 保持原相对顺序", "同为 &#39;a&#39; 的两条记录仍保持 1、3 的原始次序", "空行，只用于分隔逻辑块，不影响执行结果。", "构造另一组记录，对比 sort 与 sorted 的差别", "sorted 返回新列表，按第二个字段升序", "原 src 未被修改，证明 sorted 不改动输入", "空行，只用于分隔逻辑块，不影响执行结果。", "用列表记录 key 函数被调用的元素", "自定义 key 函数，每次调用留痕", "把当前元素追加到 calls", "返回第二个字段作为排序键", "对 3 个元素排序，观察 key 调用次数", "key 对每个元素恰好求值一次，次数等于元素数", "空行，只用于分隔逻辑块，不影响执行结果。", "构造长度为 5 的列表演示切片赋值", "普通切片赋值右侧长度可不同，列表变长", "打印替换后的结果，长度由 5 变为 6", "扩展切片赋值长度不符会抛异常", "a[::2] 选中 3 个元素却只给 2 个值", "捕获预期的 ValueError 并打印类型", "用 * 重复同一个行对象三次", "空行，只用于分隔逻辑块，不影响执行结果。", "只改第一行的第一格", "三行是同一对象，改一格等于改三行", "列表推导每次迭代新建一个独立的行 list", "只改第一行第一格", "各行 id 不同，只有第一行变成 9", "演示遍历时修改的安全写法", "空行，只用于分隔逻辑块，不影响执行结果。", "遍历副本 nums[:]，原列表可安全删除", "删除偶数元素", "副本迭代不会跳项，结果为 [1, 3, 5]", "list.sort 原地返回 None；sorted 返回新列表且接受任意可迭代对象，两者 key / reverse 都是仅关键字参数", "TimSort 稳定、最坏 O(n log n)、已排序输入近 O(n)、minrun 取 32；reverse 不破坏稳定性"]' title='第 019 讲 · list 进阶：切片赋值、排序与常见陷阱' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='compare2' title='第 019 讲 · 切片赋值：普通切片可变长，扩展切片必须等长' labels='切片赋值：普通切片可变长，扩展切片必须等长|TimSort：稳定性、key 只算一次与…|引用陷阱：列表乘法、遍历修改与内存预分配|内存预分配' caption='写出正确且高效的列表处理代码' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### sort 原地排序，sorted 返回新列表

```python
from operator import itemgetter
from functools import cmp_to_key

data = [(1, 'b'), (1, 'a'), (2, 'c'), (1, 'd')]
print('reverse keeps stability', sorted(data, key=lambda r: r[0], reverse=True))

rows = [('amy', 30), ('bob', 25), ('cy', 30)]
print('by score then name', sorted(rows, key=itemgetter(1, 0)))

def by_abs(a, b):
    return (abs(a) > abs(b)) - (abs(a) < abs(b))
print('cmp_to_key', sorted([-3, 1, -2, 2], key=cmp_to_key(by_abs)))
```

<OutputBox title='对照写法：先自己猜，再点开' output='reverse keeps stability [(2, &#39;c&#39;), (1, &#39;b&#39;), (1, &#39;a&#39;), (1, &#39;d&#39;)]\nby score then name [(&#39;bob&#39;, 25), (&#39;amy&#39;, 30), (&#39;cy&#39;, 30)]\ncmp_to_key [1, -2, 2, -3]' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "from operator import itemgetter\n\npairs = [(&#39;b&#39;, 2), (&#39;a&#39;, 1), (&#39;a&#39;, 3), (&#39;b&#39;, 1)]\nprint(&#39;sort returns&#39;, pairs.sort(key=itemgetter(0)))\nprint(&#39;after sort&#39;, pairs)\nprint(&#39;stable for equal keys&#39;, [p[1] for p in pairs if p[0] == &#39;a&#39;])\n\nsrc = [(&#39;x&#39;, 3), (&#39;y&#39;, 1), (&#39;z&#39;, 2)]\nnew = sorted(src, key=itemgetter(1))\nprint(&#39;sorted new list&#39;, new, &#39;src intact&#39;, src)\n\ncalls = []\ndef key_count(record):\n    calls.append(record)\n    return record[1]\nsorted(src, key=key_count)\nprint(&#39;key calls&#39;, len(calls), &#39;equals len&#39;, len(calls) == len(src))\n\na = [0, 1, 2, 3, 4]\na[1:3] = [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;]\nprint(&#39;slice assign changes length&#39;, a)\ntry:\n    a[::2] = [1, 2]\nexcept ValueError as e:\n    print(&#39;extended slice error&#39;, type(e).__name__)\n\ngrid = [[0] * 3] * 3\ngrid[0][0] = 9\nprint(&#39;shared rows&#39;, grid[0] is grid[1], grid)\nfixed = [[0] * 3 for _ in range(3)]\nfixed[0][0] = 9\nprint(&#39;fixed rows&#39;, fixed[0] is fixed[1], fixed[0])\n\nnums = [1, 2, 3, 4, 5]\nfor x in nums[:]:\n    if x % 2 == 0:\n        nums.remove(x)\nprint(&#39;safe removal&#39;, nums)", "note": "切片赋值：普通切片可变长，扩展切片必须等长"}, {"label": "对照 / 进阶", "code": "from operator import itemgetter\nfrom functools import cmp_to_key\n\ndata = [(1, &#39;b&#39;), (1, &#39;a&#39;), (2, &#39;c&#39;), (1, &#39;d&#39;)]\nprint(&#39;reverse keeps stability&#39;, sorted(data, key=lambda r: r[0], reverse=True))\n\nrows = [(&#39;amy&#39;, 30), (&#39;bob&#39;, 25), (&#39;cy&#39;, 30)]\nprint(&#39;by score then name&#39;, sorted(rows, key=itemgetter(1, 0)))\n\ndef by_abs(a, b):\n    return (abs(a) &gt; abs(b)) - (abs(a) &lt; abs(b))\nprint(&#39;cmp_to_key&#39;, sorted([-3, 1, -2, 2], key=cmp_to_key(by_abs)))", "note": "TimSort：稳定性、key 只算一次与 reverse 的实现"}]' title='两种写法切换看' />

**list 操作与规则对照**

| 写法 | 结果 | 约束 |
| --- | --- | --- |
| a[1:3] = [x, y, z] | 替换切片并改变列表长度 | 普通切片左右长度可不同 |
| a[:] = [] | 原地清空，所有别名可见 | 等价于 a.clear()（3.3+） |
| a[::2] = [1, 2] | 抛 ValueError | 扩展切片要求右侧长度严格等于选中元素数 |
| a.sort(key=...) | 原地排序并返回 None | 仅关键字参数 key / reverse |
| sorted(iterable, key=...) | 返回新 list | 输入可为任意可迭代对象 |
| [[0]*3]*3 | 三行共享同一 list 引用 | 应改为列表推导生成独立行 |


## TimSort：稳定性、key 只算一次与 reverse 的实现

CPython 的排序是 `TimSort`：先扫描输入找出连续有序的 natural run，短 run 用二分插入排序补到 minrun（CPython 取 32），再把相邻 run 按规则压栈合并。最坏 `O(n log n)`，已排序或部分有序输入接近 `O(n)`，空间 `O(n)`。

归并时相等元素优先取左侧 run 的元素，因此排序稳定：`key` 相同的记录保持输入相对顺序，这让「先按时间排、再按级别稳定排」这类多级排序可以分步完成。

`key` 函数通过 decorate-sort-undecorate 实现，对每个元素恰好求值一次并把结果缓存，所以 `key` 里做昂贵计算（解析日期、查字典）不会在比较时反复执行；用计数器函数能直接断言调用次数等于元素个数。

`reverse=True` 不是排完再整体反转（那样会破坏稳定性），而是在比较时翻转结果，因此相等 `key` 的记录仍保序。

多列排序用 `operator.itemgetter(1, 0)` 或 `attrgetter`，它们在 C 层取字段，比等价 `lambda` 少一次 Python 函数调用且意图更清楚。

Python 3 移除了 Python 2 的 `sort(cmp=...)`，需要旧式比较函数时用 `functools.cmp_to_key` 适配。

CPython 的排序用 `TimSort`：先线性扫描切出连续有序的 natural run，短于 minrun（取 32）的段用二分插入补齐，再维护一个 run 栈按合并规则两两归并，最坏 `O(n log n)`、对已有顺序的数据接近 `O(n)`，额外空间 `O(n)`。

归并时当两侧 `key` 相等优先取左 run 的元素，因此排序是稳定的，多级排序可以分步做而不打乱前一级结果。`key` 通过 decorate-sort-undecorate 实现：先对每个元素求一次 `key` 并与元素打包，排序时只比较缓存的 `key`，结束后拆包，所以昂贵 `key` 只执行一次；

`reverse` 通过翻转比较结果实现而非排序后整体反转，稳定性不受影响。

切片赋值走 `PyList_SetSlice`：普通切片允许左右长度不同，会按需 `memmove` 后续元素并调整 `ob_size`；

步长大于 1 的扩展切片无法靠平移吸收长度差，因此强制要求右侧长度等于选中元素数，否则抛 `ValueError`。列表乘法 `[x] * k` 复制的是已求值对象的引用，这是共享行问题的根源；`for` 迭代 `list` 使用内部递增索引，循环体内改变长度会让索引与内容错位。

<Callout type="tip" title='核心心智模型' text='切片不只是读取，写在赋值号左边就是原地替换。`a[i:j] = seq` 会把 i 到 j 这一段整体换成 `seq` 的元素，左右长度可以不同，因此能同时完成删除、插入与替换，列表长度随之改变；`a[:] = []` 等价于 `a.clear()`（3.3+），是原地清空且所有指向该列表的别名都能…' />


## 排序规则与可验证结论

**排序规则与可验证结论**

| 规则 | 结论 | 验证方式 |
| --- | --- | --- |
| key 调用次数 | 每个元素恰好一次，结果被缓存（DSU） | 计数函数断言 calls == len(data) |
| reverse=True 与稳定性 | 相等 key 仍保持输入相对顺序 | 对同 key 元组排序后比对次序 |
| TimSort 复杂度 | 最坏 O(n log n)，已排序输入近 O(n)，minrun 取 32 | 对有序与乱序输入分别计时 |
| operator.itemgetter | C 层取字段，比 lambda 少一次 Python 调用 | sorted(rows, key=itemgetter(1, 0)) |
| sort(cmp=...) | Python 3 已移除，改用 key 或 cmp_to_key | functools.cmp_to_key(by_abs) |

```python
from operator import itemgetter
import sys

hit = {'n': 0}
def key(record):
    hit['n'] += 1
    return record[1]

rows = [('a', 3), ('b', 1), ('c', 2), ('d', 1)]
sorted(rows, key=key)
print('key called once per item', hit['n'] == len(rows), hit['n'])

nums = [1, 2, 3, 4, 5, 6]
kept = []
for x in nums:
    if x % 2 == 0:
        nums.remove(x)
    kept.append(x)
print('iterated values', kept)
print('skipped item 3?', 3 not in kept)

a = [None] * 1000
b = []
for _ in range(1000):
    b.append(None)
print('prealloc no larger', sys.getsizeof(a) <= sys.getsizeof(b))
```

<OutputBox title='原理验证' output='key called once per item True 4\niterated values [1, 2, 4, 6]\nskipped item 3? True\nprealloc no larger True' />


## 引用陷阱：列表乘法、遍历修改与内存预分配

`[expr] * k` 复制的是表达式求值结果的引用，不是重新求值 k 次。

`[[0] * 3] * 3` 里 `[0] * 3` 先算出一个行 `list`，外层 `* 3` 把同一个行对象的引用放三份，于是 `board[0][0] = 1` 会改到三行；

正确写法是 `[[0] * 3 for _ in range(3)]`，列表推导每次迭代都新建一个行。

判断依据是看两行的 `id` 是否相同，或数一数 `len({id(r) for r in board})` 去重后还剩几个。

`for` 循环对 `list` 用内部递增下标迭代，在循环体里 `remove` / `insert` 会改变长度与元素位置，导致某些元素被跳过（删干净的例子里依次访问的是 1、3、5，剩下的 2、4、6 从未被检查）；修复方式是遍历副本 `for x in a[:]`、用列表推导重建、或从后往前删。

内存方面，列表推导与 `[None] * n` 一次成型，比先建空列表再循环 `append` 少若干次 `realloc`；大列表处理优先用生成器与推导式一次成型，而不是边遍历边改。

<Term word='切片赋值与步长' text='切片不只是读取，写在赋值号左边就是原地替换。`a[i:j] = seq` 会把 i 到 j 这一段整体换成 `seq` 的元素，左右长度可以不同，因此能同时完成删除、插入与替换，列表长度随之改变；`a[:] = []` 等价于 `a.clear()`（3.3+），是原地清空且所有指向该列表的别名都能看到变化，而…' />

<Term word='sort 与 sorted' text='CPython 的排序是 `TimSort`：先扫描输入找出连续有序的 natural run，短 run 用二分插入排序补到 minrun（CPython 取 32），再把相邻 run 按规则压栈合并。最坏 `O(n log n)`，已排序或部分有序输入接近 `O(n)`，空间 `O(n)`。归并时相等元素优先取左侧…' />


### 遍历时删除为什么跳过元素

**常见错因与修复**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 改二维列表一格变一整行 | * 重复的是同一行对象引用 | [[0]*3 for _ in range(3)] |
| 遍历列表删除元素后仍有残留 | for 用递增下标，删除使后续元素前移被跳过 | 遍历副本 a[:] 或列表推导重建 |
| 把 a.sort() 结果赋给变量得 None | sort 原地排序按约定返回 None | 用 sorted(a) 或先 sort 再用 a |
| a[::2] = [1, 2] 抛 ValueError | 扩展切片赋值要求长度严格相等 | 先 len(a[::2]) 再构造等长序列 |
| 反复 insert(0, x) 很慢 | 每次搬移整个数组 O(n²) | 改用 collections.deque.appendleft |

<Callout type="warn" title='本讲最容易踩的坑' text='[[0] * 3] * 3 改一格变成改一整行：* 对 list 做的是引用重复，三行指向同一个 list 对象' />


## 日志流水线：按级别与时间戳稳定排序并安全过滤

一批日志元组 `(level, ts, msg)` 需要先过滤掉 `DEBUG`，再按级别、同级别按时间排，且同级别的相对顺序不能被打乱，因为下游依赖这个顺序做因果追踪。

用 `sorted` 配 `operator.itemgetter(0, 1)` 一次成型，`key` 在 C 层求值、每个元素只算一次；

过滤用列表推导重建而不是在原列表上 `remove`，避免跳项。再演示用 `[None] * n` 预分配结果缓冲、用切片赋值整体写回，以及普通切片赋值把一段占位替换成更短的序列（长度可变）。重点是把排序、过滤、切片替换、预分配四种操作各自的成本与失效信号分开处理，而不是塞进一个循环里全做完。

真实工程还会加时间戳解析与异常记录解析，但排序稳定性与引用安全这两条边界在这里已经定死。

```python
from operator import itemgetter

LOGS = [
    ('INFO', 3, 'started'),
    ('DEBUG', 1, 'cache warm'),
    ('INFO', 2, 'connected'),
    ('ERROR', 4, 'timeout'),
    ('DEBUG', 5, 'retry'),
    ('INFO', 6, 'done'),
]

def pipeline(records):
    kept = [r for r in records if r[0] != 'DEBUG']
    ordered = sorted(kept, key=itemgetter(0, 1))
    out = [None] * len(ordered)
    out[:] = ordered
    return out

result = pipeline(LOGS)
print('count', len(result))
print('first', result[0], 'last', result[-1])
print('info order', [r[1] for r in result if r[0] == 'INFO'])
print('stable within level', result[1][0] == result[2][0])

buf = [0, 0, 0, 0, 0]
buf[1:4] = [10, 20]
print('slice shrink', len(buf), buf)
```

<Callout type="idea" title='落地提示' text='大列表优先用生成器与推导式一次成型；排序键用 operator.itemgetter / attrgetter 比 lambda 更快更清晰' />

<CheckList id='P019b' title='上线前自检' :items='["能复现并解释「[[0] * 3] * 3 改一格变成改一整行」", "能复现并解释「遍历列表时删除元素，某些项被跳过」", "能复现并解释「result = a.sort(key=...) 后 res…」", "能用一条命令验证 切片赋值与步长", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "xs=[3,1,2]; print(sorted(xs), xs[::-1], len(xs))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 切片赋值与步长 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 错因速查与修复

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| [[0] * 3] * 3 改一格变成改一整行 | * 对 list 做的是引用重复，三行指向同一个 list 对象 | 用列表推导 [[0] * 3 for _ in range(3)] 生成独立行；用 id 集合大小断言各行不同 |
| 遍历列表时删除元素，某些项被跳过 | for 循环维护递增下标，删除当前项后后面元素整体前移，下一次迭代跨过一个元素 | 遍历副本 for x in a[:]、用列表推导重建，或从后往前删除 |
| result = a.sort(key=...) 后 result 是 None | list.sort 原地排序并返回 None，这是刻意的 API 约定，避免调用方误以为得到新列表 | 需要新列表用 sorted(a)；要么先 a.sort() 再直接使用 a 本身 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：[[0] * 3] * 3 改一格变成改一整…", "body": "* 对 list 做的是引用重复，三行指向同一个 list 对象", "tip": "用列表推导 [[0] * 3 for _ in range(3)] 生成独立行；用 id 集合大小断言各行不同"}, {"title": "第 2 步：遍历列表时删除元素，某些项被跳过", "body": "for 循环维护递增下标，删除当前项后后面元素整体前移，下一次迭代跨过一个元素", "tip": "遍历副本 for x in a[:]、用列表推导重建，或从后往前删除"}, {"title": "第 3 步：result = a.sort(key=..…", "body": "list.sort 原地排序并返回 None，这是刻意的 API 约定，避免调用方误以为得到新列表", "tip": "需要新列表用 sorted(a)；要么先 a.sort() 再直接使用 a 本身"}]' />


## 列表处理练习与自测

<Exercise title='基础：修复二维列表的共享行并验证' task='修复 [[0] * 3] * 3 的共享引用问题，用 id 断言三行互不相同，并把错误版与修复版的结果都打印出来对比。' solution='bad = [[0] * 3] * 3\nbad[0][0] = 9\nprint(&#39;bad&#39;, bad, &#39;shared&#39;, bad[0] is bad[1])\n\ngood = [[0] * 3 for _ in range(3)]\ngood[0][0] = 9\nprint(&#39;good&#39;, good, &#39;shared&#39;, good[0] is good[1])\nprint(&#39;distinct ids&#39;, len({id(r) for r in good}) == 3)' explain='* 重复的是引用，列表推导每次迭代都会新建一个 list，因此三行独立。用 id 集合的大小可以稳定断言，不依赖具体元素值。' />

<Exercise title='进阶：写一个多列稳定排序并证明 key 只求一次' task='给定 (部门, 工龄, 姓名) 记录，按部门升序、部门内按工龄降序排序，用计数 key 证明每个元素只调用一次，并说明 reverse 为什么不破坏稳定性。' solution='rows = [(&#39;dev&#39;, 3, &#39;amy&#39;), (&#39;ops&#39;, 5, &#39;bob&#39;), (&#39;dev&#39;, 1, &#39;cy&#39;), (&#39;dev&#39;, 3, &#39;dot&#39;)]\nhits = []\ndef counted(r):\n    hits.append(r)\n    return (r[0], -r[1])\nout = sorted(rows, key=counted)\nprint(&#39;calls&#39;, len(hits), &#39;one per row&#39;, len(hits) == len(rows))\nprint(&#39;dev group&#39;, [r[2] for r in out if r[0] == &#39;dev&#39;])\nprint(&#39;equal key stable&#39;, out[0][2] == &#39;amy&#39; and out[1][2] == &#39;dot&#39;)' explain='sorted 用 DSU 对每个元素求值一次并缓存 key，计数器断言 calls == len(rows)；复合 key 用元组表达多列，降序用 -工龄。reverse 是翻转比较结果而非排序后整体反转，因此 key 相等的记录仍保持输入相对顺序。' />

<Quiz no='019-1' q='执行 b = [[0] * 3] * 3; b[0][0] = 9 后，b 的值是？' :options='["只有第一行变成 [9, 0, 0]", "三行都变成 [9, 0, 0]", "抛 TypeError", "只有最后一行变"]' answer="1" explain='* 对 list 重复的是同一个行对象的引用，三行指向同一 list，改一格等于改三行；应改用列表推导生成独立行。' />

<Quiz no='019-2' q='关于 list.sort() 与 sorted()，哪项正确？' :options='["sort 返回排序后的新列表", "sort 原地排序返回 None，sorted 返回新列表且接受任意可迭代对象", "两者都返回 None", "sorted 只能用于 list"]' answer="1" explain='list.sort(*, key, reverse) 是原地方法并按约定返回 None；sorted(iterable, *, key, reverse) 接受任意可迭代对象并构造新 list。' />

<Quiz no='019-3' q='a = [0, 1, 2, 3, 4]; a[::2] = [9, 8] 会怎样？' :options='["正常赋值", "抛 ValueError，因为扩展切片要求右侧长度等于被选中元素数", "抛 IndexError", "把 a 变成 [9, 8]"]' answer="1" explain='a[::2] 选中 3 个元素（下标 0、2、4），扩展切片赋值要求右侧序列长度严格相等，给 2 个值会抛 ValueError。' />

<Predict no='019-4' q='nums = [1, 2, 3, 4, 5, 6]，执行 for x in nums: nums.remove(x) 后 nums 是？' :options='["[]", "[2, 4, 6]", "[1, 3, 5]"]' answer='1' output='[2, 4, 6]' explain='for 用递增下标迭代，每删一个元素后面的就整体前移，下一次迭代跨过一个。依次删掉的是 1、3、5，剩下的 2、4、6 从未被访问。要删干净应遍历副本 for x in nums[:] 或用 nums.clear()。' />

<FillBlank no='019-5' tpl='from operator  ___ itemgetter' :answers='["import"]' hint='回想本讲关于 切片赋值与步长 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 切片赋值：普通切片可变长，扩展切片必须等长 的落点。' />

<KnowledgeCard :points='["list.sort 原地返回 None；sorted 返回新列表且接受任意可迭代对象，两者 key / reverse 都是仅关键字参数", "TimSort 稳定、最坏 O(n log n)、已排序输入近 O(n)、minrun 取 32；reverse 不破坏稳定性", "key 对每个元素只求值一次（DSU 缓存）；itemgetter / attrgetter 在 C 层实现，多列排序比 lambda 少一次 Python 调用", "[[0]*3]*3 重复的是同一行引用，用列表推导 [[0]*3 for _ in range(3)] 生成独立行", "扩展切片赋值 a[::2] = seq 要求长度严格相等否则 ValueError；普通切片赋值可改变列表长度", "遍历时删除会跳项，遍历副本或用推导式重建；头部插入用 deque.appendleft 而不是 insert(0, x)"]' :pitfalls='["[[0] * 3] * 3 改一格变成改一整行", "遍历列表时删除元素，某些项被跳过", "result = a.sort(key=...) 后 result 是 None", "用 [[0]*3]*3 创建二维列表会得到三个指向同一行的引用，改一格变成改一行"]' summary='sort 是原地排序且返回 None，sorted 返回新列表；TimSort 稳定且对部分有序数据极快，key 函数只算一次' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| list.sort 原地返回 None；sorted 返回新列表且接受任意可迭代对象，两者 key / reverse 都是仅关键字参数 | 建立直觉 |
| TimSort 稳定、最坏 O(n log n)、已排序输入近 O(n)、minrun 取 32；reverse 不破坏稳定性 | 跑通示例 |
| key 对每个元素只求值一次（DSU 缓存）；itemgetter / attrgetter 在 C 层实现，多列排序比 lambda 少一次 Python 调用 | 深入边界 |
| [[0]*3]*3 重复的是同一行引用，用列表推导 [[0]*3 for _ in range(3)] 生成独立行 | 工程落地 |
| 扩展切片赋值 a[::2] = seq 要求长度严格相等否则 ValueError；普通切片赋值可改变列表长度 | 随堂检测 |
| 遍历时删除会跳项，遍历副本或用推导式重建；头部插入用 deque.appendleft 而不是 insert(0, x) | 复盘 |

1. list.sort 原地返回 None；sorted 返回新列表且接受任意可迭代对象，两者 key / reverse 都是仅关键字参数

2. TimSort 稳定、最坏 O(n log n)、已排序输入近 O(n)、minrun 取 32；reverse 不破坏稳定性

3. key 对每个元素只求值一次（DSU 缓存）；itemgetter / attrgetter 在 C 层实现，多列排序比 lambda 少一次 Python 调用

[下一讲：tuple 与具名元组：不可变性的价值](/containers/tuple)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/019-list-advanced.py`

```bash
python3 examples/lessons/019-list-advanced.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/019-list-advanced.py) · [全部示例代码索引](/examples/)
