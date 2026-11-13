---
title: 第 013 讲 · 循环：for / while、range 与循环 else
description: 理解迭代的本质并写出高效循环
---

<StageHeader stage='L1 · 编程地基' level='★☆☆☆☆' time='30 分钟' goal='理解迭代的本质并写出高效循环' prereq='第 012 讲 · 分支：if / elif / else 与 match-case' />

# 第 013 讲 · 循环：for / while、range 与循环 else

会分岔之后，剩下的多是重复：一批订单、一页日志，总不能复制几十遍同样代码。交给循环看似换写法，背后是一整套『怎么一个一个取』的约定，弄清它才省心又不埋雷。

你大概写过 for i in range(len(items))，也遇过遍历时删元素跳项；还好奇 range(一百万) 是否真铺开一百万个数。先看 for 拿到的是迭代器而非下标，顺带解释遍历 dict 为何得到键；range 只存几个整数、内存恒定；最后收在 break、continue 与循环 else，以及用 enumerate、zip 取代下标。有分支印象就够；学完你能写省内存又稳当的循环。


## 遍历 list 时删元素，为什么悄悄跳过了下一项

一段清洗代码在遍历 list 的同时删除不符合条件的元素，跑完发现名单里还留着本该删掉的值：for n in nums: 判断偶数后 `nums.remove(n)`，[2, 2, 4, 5] 跑完得到 [2, 5]，第一个 2 被跳过了。

另一处为了拿下标写 for i in `range(len(items)`):，换成 dict 遍历时按位置索引直接报错；

还有人把 `range(1000000)` 当成会占一大块内存的列表，或在 for 循环后加 else 却以为它总会被执行。朴素解法是「删的时候小心点」或「多用几个 `range(len(x)`)」，两者都没抓住 for 的本质：它拿的是迭代器而不是下标，遍历过程中修改底层序列会让迭代器的内部索引与已变短的列表错位。

本讲把迭代协议、range 的惰性、break/continue/else、enumerate 与 zip 讲清，并给出「遍历副本或用推导式重建」的具体修复。


## for 基于迭代协议：拿迭代器，不拿下标

for x in obj: 的执行分两步：先调用 `iter(obj)` 拿到迭代器，再反复调用 `next(it)` 直到抛出 StopIteration，for 捕获这个异常后正常结束。对象只要实现 `__iter__` 返回迭代器（或实现 `__getitem__` 支持从 0 开始的旧式序列协议）就可迭代；

迭代器则必须同时有 `__iter__`（返回自身）与 `__next__`。因此 list 每次 `iter()` 都给出全新的迭代器、能被反复遍历，而文件对象或生成器本身就是迭代器、遍历一次就耗尽，第二次循环直接空转且不报错。

dict 实现的是键的迭代，for k in d 拿到键，要值用 `d.values()` 或 `d.items()`；

zip 在最短的输入耗尽时停止，`enumerate(iterable, start)` 给每个元素配序号、默认 start 为 0。

迭代器是一次性、带状态的对象，先 `len()` 再遍历、或遍历两次都会踩空，边界信号是「第二次循环什么都没做却没有异常」。需要复用数据时先把迭代器物化成 list 或 tuple，别对同一个迭代器跑两遍。

```python
import sys
r = range(2, 10, 3)
print('range_len', len(r))
print('range_list', list(r))
print('range_mem', sys.getsizeof(range(1000000)) == sys.getsizeof(range(1)))

words = ['a', 'b', 'c']
print('enumerate', list(enumerate(words, 1)))
print('zip', list(zip(words, [1, 2])))

for w in words:
    if w == 'x':
        break
else:
    print('no_break', 'loop completed')
```

<OutputBox title='主示例运行结果' output='range_len 3\nrange_list [2, 5, 8]\nrange_mem True\nenumerate [(1, &#39;a&#39;), (2, &#39;b&#39;), (3, &#39;c&#39;)]\nzip [(&#39;a&#39;, 1), (&#39;b&#39;, 2)]\nno_break loop completed' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys\nr = range(2, 10, 3)\nprint(&#39;range_len&#39;, len(r))\nprint(&#39;range_list&#39;, list(r))\nprint(&#39;range_mem&#39;, sys.getsizeof(range(1000000)) == sys.getsizeof(range(1)))\n\nwords = [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;]\nprint(&#39;enumerate&#39;, list(enumerate(words, 1)))\nprint(&#39;zip&#39;, list(zip(words, [1, 2])))\n\nfor w in words:\n    if w == &#39;x&#39;:\n        break\nelse:\n    print(&#39;no_break&#39;, &#39;loop completed&#39;)' :notes='["导入 sys 以用 getsizeof 观测对象内存", "range(2, 10, 3) 只存三个整数，不物化元素", "len 由算术直接算出 3，不遍历生成元素", "list(r) 才把惰性序列物化成 [2, 5, 8]", "两个不同大小的 range 对象内存相同，证明惰性", "定义一个普通 list 供后续循环使用", "enumerate 的 start 设为 1，给每项配序号", "zip 以最短输入为准，第二个列表只有两项", "for 从 iter(words) 拿迭代器逐项取", "循环体里的 if 条件永远不成立", "因此这一行的 break 从未执行", "for 的 else 只在未被 break 时执行", "没有 break 故 else 分支执行，打印完成信息"]' title='第 013 讲 · 循环：for / while、range 与循环 else' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**迭代协议对照**

| 对象 | __iter__ | __next__ | 能否重复遍历 |
| --- | --- | --- | --- |
| list / tuple / dict | 有，返回新迭代器 | 无 | 能，每次新迭代器 |
| 迭代器 / 生成器 / 文件 | 有，返回自身 | 有 | 否，一次耗尽 |
| range | 有，返回新迭代器 | 无 | 能，惰性序列 |
| 实现 __getitem__ 的类 | 旧式序列协议 | 无 | 按索引从 0 迭代 |


## range 是惰性序列：内存恒定与 O(1) 查询

`range(start, stop, step)` 返回的不是列表，而是一个只存 start、stop、step 三个整数的不可变序列对象；

`len(range(...)`) 用算术算出长度、r`[i]` 用公式 start 加 i 乘 step 直接算、in 判断也走数学判定，都是 `O(1)` 且不生成中间元素。

`sys.getsizeof(range(1000000)`) 与 `sys.getsizeof(range(1)`) 相等，正是内存恒定的证据；

`list(range(1000000)`) 才会真正分配一百万个整数引用。

range 支持负数步长（`range(10, 0, -2)`）、切片（返回新的 range）、且可哈希可作字典键；

step 不能为 0，否则抛 ValueError: `range()` arg 3 must not be zero。它是可迭代对象但不是迭代器：有 `__iter__`、没有 `__next__`，每次 for 都会新建一个 range_iterator。

循环变量的作用域也要留意：for 里的名字在循环结束后仍绑定着最后一个值，不会像推导式那样有独立作用域；while 没有迭代协议，靠条件与显式 break 控制，忘记更新条件就会死循环。

```python
nums = [2, 2, 4, 5]
for n in nums:
    if n % 2 == 0:
        nums.remove(n)
print('buggy', nums)
clean = [n for n in [2, 2, 4, 5] if n % 2 != 0]
print('fixed', clean)
```

<OutputBox title='对照写法：先自己猜，再点开' output='buggy [2, 5]\nfixed [5]' guess="true" />


## break / continue / else 与高效循环写法

break 立即结束整个循环、continue 跳过本轮剩余语句进入下一轮，两者只对最内层循环生效。for 与 while 都能带 else，且 else 只在循环「没有被 break 中断」时执行——被 continue 跳过不算中断，正常耗尽迭代器会执行 else，被 break 则不执行。

这个语义正好用来写查找失败分支：for item in items: 命中就 break，else: 处理未找到，比设一个 found 标志更清晰；但它反直觉，很多人误以为 else 总执行或属于 if，读代码时要显式确认有没有 break。

工程写法上优先 enumerate 与 zip 而不是 `range(len(x)`)：`enumerate(items)` 直接给序号与元素，`zip(a, b)` 并行迭代且以最短者为准，dict 用 .`items()`，需要反向用 `reversed()` 而非手动算下标。

要过滤或变换就遍历副本或重建：for n in nums[:] 拿切片副本后原地删，或更推荐用推导式 [n for n in nums if 条件] 一次成型——后者既不改原对象、也避免边遍历边删的跳项。边界信号：循环结果「少了几个」且不报错，八成是在遍历中改动了同一个可变序列。


## 字典遍历的是键：__iter__ 与 __next__ 的分工

for 循环在字节码层用 GET_ITER 拿到迭代器、用 FOR_ITER 反复取下一项：FOR_ITER 内部调用迭代器的 tp_iternext，返回空时抛 StopIteration，解释器把该异常当作正常结束信号捕获并跳到循环后的指令，而带 else 的循环会在未被 break 时先执行 else 块再继续。

list 的 `__iter__` 每次返回一个携带当前下标的 list_iterator，删除元素会让底层数组变短、后续元素前移，而迭代器仍按旧下标递增，于是跳过紧邻被删元素的下一项——这就是边遍历边删跳项的根因。

range 是 PyRangeObject，只保存三个整数与长度缓存，len、下标、包含判断都由整数运算完成，不物化元素，故内存恒定。zip 与 enumerate 各返回一个专用迭代器，按位置从各自输入取项，任一输入耗尽即结束。

理解「迭代器持有独立游标」，就知道为什么遍历副本或重建能修复跳项，以及为什么第二次遍历同一个迭代器会空转。

<ConceptDiagram type='hub4' title='第 013 讲 · for 基于迭代协议：拿迭代器，不拿下标' labels='for 基于迭代协议：拿迭代器，不拿下标|range 是惰性序列：内存恒定与 O(1)|break / continue / els' caption='理解迭代的本质并写出高效循环' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 大文件逐行清洗：惰性生成、重建过滤、for-else 兜底

一个日志清洗任务要过滤掉空行与注释行、给保留行编号，并统计处理行数。早期实现先把整个文件 `read()` 进一个大字符串再切分，文件一大就吃满内存；还有人边遍历边从列表里删，结果漏行。

下面这段给出工程写法：用生成器逐行产出（模拟大文件，不落盘），用 enumerate 配序号，用推导式重建而不是原地删，用 for-else 写「没有任何有效行」的失败分支，用 zip 把行与来源标签配对。全程内存只随单行大小变化，不随总行数增长。

真实系统把 generate_lines 换成对文件对象逐行迭代即可，其余结构不变。

```python
def generate_lines(n):
    for i in range(n):
        yield 'row-' + str(i) if i % 3 else ''

def is_valid(line):
    return bool(line) and not line.startswith('#')

def clean(lines):
    return [line for line in lines if is_valid(line)]

raw = list(generate_lines(10))
valid = clean(raw)
print('total', len(raw), 'kept', len(valid))
for idx, line in enumerate(valid, 1):
    if idx <= 2:
        print('first', idx, line)
for line in valid:
    if line == 'missing':
        break
else:
    print('scan', 'no break happened')
pairs = list(zip(valid, ['src'] * len(valid)))
print('pairs', len(pairs), 'first_tag', pairs[0][1])
```

<Callout type="idea" title='落地提示' text='循环 else 只在未被 break 时执行，适合写查找失败分支；优先 enumerate / zip 而不是 range(len(x))' />


## 边遍历边删与迭代器耗尽的错因速查


## 按迭代协议写循环：练习、自测与速记

<Exercise title='基础：验证 range 惰性' task='打印 len(range(2, 10, 3))、list(range(2, 10, 3))、以及 sys.getsizeof(range(1000000)) == sys.getsizeof(range(1))，并解释内存为何恒定。' solution='import sys\nr = range(2, 10, 3)\nprint(&#39;len&#39;, len(r))\nprint(&#39;list&#39;, list(r))\nprint(&#39;mem_same&#39;, sys.getsizeof(range(1000000)) == sys.getsizeof(range(1)))' explain='range 只存 start、stop、step 三个整数，len 与下标由算术算出；只有 list(r) 才物化元素，因此不同大小的 range 内存相同。' />

<Exercise title='进阶：修好边遍历边删并写 for-else' task='先用有缺陷的循环删除偶数并打印结果，再用推导式重建给出正确结果；最后写一个查找失败才执行的 for-else 分支。' solution='nums = [2, 2, 4, 5]\nfor n in nums:\n    if n % 2 == 0:\n        nums.remove(n)\nprint(&#39;buggy&#39;, nums)\nprint(&#39;fixed&#39;, [n for n in [2, 2, 4, 5] if n % 2 != 0])\nfor x in [1, 2, 3]:\n    if x == 9:\n        break\nelse:\n    print(&#39;not_found&#39;, 9)' explain='边删导致游标错位，[2, 2, 4, 5] 只剩 [2, 5]；推导式重建得 [5]。第二个循环没有 break，for-else 的 else 分支因此执行。' />

<Quiz no='013-1' q='for x in obj 实际拿到的是？' :options='["iter(obj) 返回的迭代器，靠 next 逐项取直到 StopIteration", "对象的下标序列", "对象的一份副本", "一个 range 对象"]' answer="0" explain='for 先调 iter 再反复 next，StopIteration 被当作正常结束；list 每次给新迭代器，文件与生成器本身即迭代器、一次耗尽。' />

<Quiz no='013-2' q='for 循环的 else 何时执行？' :options='["仅当循环未被 break 中断（含正常耗尽）时", "每次循环结束都执行", "仅当 break 发生时", "属于最近的 if"]' answer="0" explain='else 属于 for 而非 if，被 continue 跳过不算中断，正常耗尽会执行；只有 break 会跳过它，适合写查找失败分支。' />

<Quiz no='013-3' q='边遍历 list 边删除元素会跳项，最推荐的修复是？' :options='["用列表推导式重建，或遍历切片副本", "删除后把下标减一", "改用 while True", "先反转再删"]' answer="0" explain='重建生成新列表、不改原对象，从根本上避免迭代器游标与缩短序列错位；遍历 nums[:] 副本也能让删除不影响正在迭代的对象。' />

<Predict no='013-P' q='主示例里 print(&#39;no_break&#39;, &#39;loop completed&#39;) 会不会执行？' :options='["会，输出 no_break loop completed", "不会，因为循环体里有 if", "不会，因为 words 非空"]' answer='0' output='no_break loop completed' explain='循环遍历 words 时 w == &#39;x&#39; 从不成立，因此没有 break，for-else 的 else 分支按语义执行。else 与循环体里的 if 无关，只取决于有没有 break。' />

<FillBlank no='013-F' tpl='___ sys' :answers='["import"]' hint='回想本讲关于 for 基于迭代协议 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 for 基于迭代协议：拿迭代器，不拿下标 的落点。' />

<KnowledgeCard :points='["for 先 iter(obj) 拿迭代器、再 next 直到 StopIteration；dict 迭代键，文件与生成器是一次性迭代器", "range 只存 start/stop/step，len、下标、in 都是 O(1) 算术，内存恒定；有 __iter__ 无 __next__", "for-else 仅在未被 break 时执行（被 continue 不算中断），适合写查找失败分支", "边遍历边删会因迭代器游标与缩短序列错位而跳项，用推导式重建或遍历 nums[:] 副本", "优先 enumerate / zip / .items() / reversed()，别写 range(len(x))；循环变量在循环后仍绑定最后值", "迭代器第二次遍历会空转且无异常，需复用先 list(it) 物化"]' :pitfalls='["遍历 list 的同时删除元素", "把 range 当成列表、或认为它有 __next__", "以为 for-else 总执行，或把迭代器当列表遍历两次", "在遍历 list 的同时删除元素会跳项，应遍历副本或用列表推导式重建"]' summary='for 循环拿的是迭代器，不是下标；能遍历的对象都实现了 __iter__，这解释了为什么 dict 遍历的是键' />

1. for 先 iter(obj) 拿迭代器、再 next 直到 StopIteration；dict 迭代键，文件与生成器是一次性迭代器

2. range 只存 start/stop/step，len、下标、in 都是 O(1) 算术，内存恒定；有 __iter__ 无 __next__

3. for-else 仅在未被 break 时执行（被 continue 不算中断），适合写查找失败分支

[下一讲：输入输出与文件初识：print、input、open、with](/foundation/io)
