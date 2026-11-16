---
title: 第 023 讲 · set / frozenset：哈希、集合运算与去重
description: 用集合把成员判断与去重做到 O(1)
---

<StageHeader stage='L2 · 容器与序列' level='★☆☆☆☆' time='25 分钟' goal='用集合把成员判断与去重做到 O(1)' prereq='第 022 讲 · dict 进阶：默认字典、计数器与合并' />

# 第 023 讲 · set / frozenset：哈希、集合运算与去重

有时我们并不关心次序，只想知道「在不在」：编号见过没有、两组标签有哪些交集。上一讲把按名字存取讲透了，这一讲把键单独拿出来用，看看判重和去重到底要付多少成本。

一个日志脚本拿列表配 `in` 过滤十万行重复请求，跑几分钟没完；换成集合几秒就结束。可又有人抱怨顺序乱了，不同进程跑出来还不一样。我们先看集合的哈希表实现与 dict 同源在哪，摸清增删与并交差的边界；再讲 frozenset 为何可哈希、哈希随机化为何让顺序不可依赖；最后算一笔判重去重的成本账。需要你熟悉字典、哈希与成员判断。学完你能把反复扫描换成一次规整，也知道哪些场合不能拿 set 直接当结果交出去。


## 对 list 反复用 in 判重，数据量一上来就卡死

一个日志去重脚本用 `seen = []` 配合 `if rid in seen` 过滤 10 万行重复请求，跑了几分钟还没结束；把 `seen` 换成 set 后同样的输入几秒就跑完。原因是 list 的 `in` 是线性扫描，n 次判重累计 `O(n²)`，而 set 的成员判断平均 `O(1)`。

但换过去又冒出新问题：有人直接把 `set(seq)` 的结果写进报告，抱怨顺序乱了，甚至不同进程跑出的顺序不一样；有人想把一组标签当 dict 的键，用可变 set 时抛 `TypeError`（set 不可哈希）；还有人写 `empty = {}` 以为得到空集合，结果拿了个 dict，`empty.add(4)` 直接抛 `AttributeError`。

这些现象都指向同一套机制：set 是与 dict 同源的哈希表，顺序不由插入决定，且只有不可变版本才可哈希。这一讲把集合运算、frozenset、哈希随机化与保序去重一条条摆清楚。


## 哈希表实现与集合运算：O(1) 的边界

CPython 的 set 与 dict 同源，都是开放寻址哈希表，只是表项只存 `(hash, key)` 而不存 value。

`add` / `remove` / `in` 平均 `O(1)`、最坏 `O(n)`（哈希冲突严重时会退化成线性探测），负载因子超过约 2/3 就扩容并 rehash；删除同样写墓碑标记，到扩容时才清理。

运算符与方法名是两套等价写法：并集用 `|` 或 `union()`、交集用 `&` 或 `intersection()`、差集（在左不在右）用 `-` 或 `difference()`、对称差用 `^` 或 `symmetric_difference()`；原地版本 `|=`、`&=`、`-=`、`^=` 对应 `update()`、`intersection_update()` 等，会直接改左操作数。

判断关系用 `<=` 判子集、`<` 判真子集、`>=` 判超集、`>` 判真超集，再用 `isdisjoint()` 确认两组没有公共元素。

增删上，`add(x)` 新增一个元素，`remove(x)` 缺失时抛 `KeyError`，`discard(x)` 缺失时静默忽略，`pop()` 返回并移除任意一个元素（空集合抛 `KeyError`），`clear()` 清空。

空集合必须写 `set()`，因为 `{}` 是空 dict；集合推导式 `{expr for x in iterable}` 与字面量 `{1, 2, 3}` 都受「元素必须可哈希」这条约束。

```python
s = {1, 2, 3}
s.add(4)
s.discard(10)
print('after add', sorted(s), len(s))
try:
    s.remove(10)
except KeyError as e:
    print('remove missing', type(e).__name__)

a = {1, 2, 3}
b = {3, 4, 5}
print('union', sorted(a | b))
print('intersection', sorted(a & b))
print('difference', sorted(a - b))
print('symmetric', sorted(a ^ b))
print('subset', {1, 2} <= a, {1, 2} < a, a.isdisjoint({9}))

squares = {x * x for x in range(6)}
print('comprehension', sorted(squares))

fs = frozenset([1, 2, 3])
print('frozenset hashable', {fs: 'value'}[frozenset([3, 2, 1])])
print('frozenset ops', sorted(fs | {4}), type(fs | {4}).__name__)

seq = ['b', 'a', 'b', 'c', 'a']
print('set dedup', sorted(set(seq)))
print('ordered dedup', list(dict.fromkeys(seq)))
print('empty set is dict?', isinstance({}, dict))
```

<OutputBox title='主示例运行结果' output='after add [1, 2, 3, 4] 4\nremove missing KeyError\nunion [1, 2, 3, 4, 5]\nintersection [3]\ndifference [1, 2]\nsymmetric [1, 2, 4, 5]\nsubset True True True\ncomprehension [0, 1, 4, 9, 16, 25]\nfrozenset hashable value\nfrozenset ops [1, 2, 3, 4] frozenset\nset dedup [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;]\nordered dedup [&#39;b&#39;, &#39;a&#39;, &#39;c&#39;]\nempty set is dict? True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='s = {1, 2, 3}\ns.add(4)\ns.discard(10)\nprint(&#39;after add&#39;, sorted(s), len(s))\ntry:\n    s.remove(10)\nexcept KeyError as e:\n    print(&#39;remove missing&#39;, type(e).__name__)\n\na = {1, 2, 3}\nb = {3, 4, 5}\nprint(&#39;union&#39;, sorted(a | b))\nprint(&#39;intersection&#39;, sorted(a &amp; b))\nprint(&#39;difference&#39;, sorted(a - b))\nprint(&#39;symmetric&#39;, sorted(a ^ b))\nprint(&#39;subset&#39;, {1, 2} &lt;= a, {1, 2} &lt; a, a.isdisjoint({9}))\n\nsquares = {x * x for x in range(6)}\nprint(&#39;comprehension&#39;, sorted(squares))\n\nfs = frozenset([1, 2, 3])\nprint(&#39;frozenset hashable&#39;, {fs: &#39;value&#39;}[frozenset([3, 2, 1])])\nprint(&#39;frozenset ops&#39;, sorted(fs | {4}), type(fs | {4}).__name__)\n\nseq = [&#39;b&#39;, &#39;a&#39;, &#39;b&#39;, &#39;c&#39;, &#39;a&#39;]\nprint(&#39;set dedup&#39;, sorted(set(seq)))\nprint(&#39;ordered dedup&#39;, list(dict.fromkeys(seq)))\nprint(&#39;empty set is dict?&#39;, isinstance({}, dict))' :notes='["字面量构造一个整数集合", "add 平均 O(1) 新增元素", "discard 对缺失元素静默忽略，不抛异常", "用 sorted 输出以消除集合顺序的不确定性", "remove 对缺失元素会抛异常", "尝试删除不存在的 10", "捕获 KeyError，对比 discard 的行为", "构造两个有交集的集合用于演示四种运算", "空行，只用于分隔逻辑块，不影响执行结果。", "并集 |，用 sorted 得到可复现结果", "交集 &amp;，只保留两集合共有的 3", "差集 -，保留在 a 但不在 b 的元素", "对称差 ^，保留只出现在其中一侧的元素", "子集、真子集与 isdisjoint 三个关系判断", "集合推导式生成 0 到 5 的平方集合", "sorted 后输出，避免依赖哈希顺序", "空行，只用于分隔逻辑块，不影响执行结果。", "frozenset 不可变且可哈希", "用它作 dict 键，顺序不同的同一组合命中同一值", "空行，只用于分隔逻辑块，不影响执行结果。", "frozenset 与 set 做运算结果仍是 frozenset", "含重复元素的序列，用于对比两种去重", "set 去重不保序，故用 sorted 得到字母序", "空行，只用于分隔逻辑块，不影响执行结果。", "dict.fromkeys 按首次出现顺序保序去重", "{} 是空 dict，空集合必须显式写 set()", "{} 是空 dict，空集合必须写 set()；s.pop() 返回任意元素，空集合抛 KeyError", "保序去重写 list(dict.fromkeys(seq))；高频判重先规整成 set，别对 list 反复用 in"]' title='第 023 讲 · set / frozenset：哈希、集合运算与去重' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='hub4' title='第 023 讲 · 哈希表实现与集合运算：O(1) 的边界' labels='哈希表实现与集合运算：O(1) 的边界|frozenset、哈希随机化与保序去重|选型：判重、去重、成员判断的成本账|哈希随机化' caption='用集合把成员判断与去重做到 O(1)' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 集合运算对照

**集合运算对照**

| 运算符 | 等价方法 | 含义 | 备注 |
| --- | --- | --- | --- |
| a \| b | a.union(b) | 并集 | frozenset 参与时结果为 frozenset |
| a & b | a.intersection(b) | 交集 | 只保留两侧共有元素 |
| a - b | a.difference(b) | 差集 | 在 a 但不在 b |
| a ^ b | a.symmetric_difference(b) | 对称差 | 只出现在一侧 |
| <= | a.issubset(b) | 子集判断 | < 为真子集 |
| isdisjoint | a.isdisjoint(b) | 无公共元素 | 返回 bool，不构造新集合 |


## frozenset、哈希随机化与保序去重

set 是可变对象，所以不可哈希，既不能作 dict 键也不能塞进另一个 set；`frozenset(iterable)` 把表冻结后允许求 hash，于是能表达「顺序无关的一组标签」这类键：`frozenset(['a','b'])` 与 `frozenset(['b','a'])` 相等且哈希相同，会命中同一条规则；它与 set 做 `|` `&` `-` `^` 时，结果仍是 frozenset。

顺序不保证是哈希表结构的直接后果：遍历按表槽位走，而 str / bytes 的哈希从 3.3 起默认带 `PYTHONHASHSEED` 随机盐（用来防哈希碰撞攻击），同一份字符串集合在不同进程里遍历顺序可能不同；整数哈希等于自身（`-1` 被保留作错误码，故映射为 `-2`），纯整数集合看起来顺序稳定，但仍不该依赖它，输出前一律 `sorted()` 或按业务字段排序。

去重有两条路：`list(set(seq))` 是 `O(n)` 但不保序；`list(dict.fromkeys(seq))` 借助 3.7 起 dict 的插入顺序，按首次出现保序去重，是报表与流水线的首选。

真要依赖顺序，先确认手上用的是哪一种结构。

```python
from time import perf_counter

data = list(range(4000))
probes = list(range(4000))
def bench(seq):
    t0 = perf_counter()
    for x in probes:
        x in seq
    return perf_counter() - t0
t_list = bench(data)
t_set = bench(set(data))
print('set much faster than list', t_list > t_set * 5)

s = set('abc')
print('pop returns arbitrary', isinstance(s.pop(), str), len(s))
s2 = {1, 2, 3}
s2 |= {3, 4}
print('in-place union', sorted(s2))
print('int hash stable', hash(7) == 7, hash(-1) == -2)
print('str hash is int', isinstance(hash('python'), int))
```

<OutputBox title='对照写法：先自己猜，再点开' output='set much faster than list True\npop returns arbitrary True 2\nin-place union [1, 2, 3, 4]\nint hash stable True True\nstr hash is int True' guess="true" />


### 增删方法与失效信号

往集合里改元素，先看方法在元素缺失时怎么反应：`remove(x)` 抛 `KeyError`，适合断言元素存在；`discard(x)` 静默忽略，适合清理可选项；`pop()` 在空集合上同样抛 `KeyError`。

`add(x)` 要求元素可哈希，塞进 list 会抛 `TypeError`（list 不可哈希）；要当键得先冻成 `frozenset()`。

两个高频误会：`{}` 是空 dict（空集合得写 `set()`），遍历中改大小会抛 `RuntimeError`（Set changed size during iteration），改前先复制一份快照。下表按方法列出缺失时的行为。

**增删方法与失效信号**

| 方法 / 写法 | 缺失元素时的行为 | 备注 |
| --- | --- | --- |
| s.add(x) | 新增元素 | 元素必须可哈希 |
| s.remove(x) | 抛 KeyError | 需要严格断言元素存在时用 |
| s.discard(x) | 静默忽略 | 清理可选元素时用 |
| s.pop() | 空集合抛 KeyError | 返回任意元素，顺序不确定 |
| &#123;&#125; | 得到空 dict | 空集合必须写 set() |
| frozenset(iterable) | 不可增删 | 可哈希，可作 dict 键或 set 元素 |

<Callout type="warn" title='本讲最容易踩的坑' text='对 list 反复用 in 判重，数据量一大就卡死：list 的 in 是 O(n) 线性扫描，n 次判重整体是 O(n²)' />


## 去重与哈希随机化的实测

顺序飘不飘得实测。

3.3 起 str、bytes 的哈希带 `PYTHONHASHSEED` 随机盐，同一段 `list(set(words))` 在两个进程里顺序可能不同；设 `PYTHONHASHSEED=0` 重跑即固定，证明乱序来自哈希。

整数不受影响：`hash(7)` 恒为 7，`hash(-1)` 为 -2（-1 留作错误码）。把十万个 id 分别喂给 list 与 set 的 `in` 计时，能量出 `O(n²)` 与平均 `O(1)` 的差距。后面的探针给出可复现计时，实测表把规则归位。

```python
import sys

s = set()
sizes = []
for i in range(100):
    s.add(i)
    sizes.append(sys.getsizeof(s))
changes = sum(1 for i in range(1, len(sizes)) if sizes[i] != sizes[i - 1])
print('set resize stepwise', 0 < changes < 100)

print('frozenset hashable', isinstance(hash(frozenset([1, 2])), int))
try:
    hash({1, 2})
except TypeError as e:
    print('set unhashable', type(e).__name__)

print('hash stable in process', hash('abc') == hash('abc'))
print('empty literal is dict', isinstance({}, dict), 'empty set', type(set()).__name__)
```

<OutputBox title='原理验证' output='set resize stepwise True\nfrozenset hashable True\nset unhashable TypeError\nhash stable in process True\nempty literal is dict True empty set set' />

**去重与哈希随机化**

| 需求 / 规则 | 写法 | 复杂度或说明 |
| --- | --- | --- |
| 判重 n 次（list） | x in list | O(n²)，数据量大时卡死 |
| 判重 n 次（set） | x in set | 平均 O(1)，先规整成 set |
| 去重不保序 | list(set(seq)) | O(n)，顺序由哈希决定 |
| 去重且保序 (3.7+) | list(dict.fromkeys(seq)) | O(n)，按首次出现顺序 |
| str / bytes 哈希 | PYTHONHASHSEED 随机盐 | 3.3 起默认开启，跨进程顺序不同 |
| 整数哈希 | hash(7) 为 7，hash(-1) 为 -2 | -1 被保留作错误码，故映射为 -2 |


## 选型：判重、去重、成员判断的成本账

选容器前先算操作分布。判断某个值在不在里面，set 平均 `O(1)`、list 是 `O(n)`，因此高频判重必须先把数据规整成 set 或 dict，绝不能对 list 反复用 `in`；一次判重的差距不明显，n 次判重就是 `O(n²)` 与 `O(n)` 的量级差。

需要去重又不关心顺序时用 `set(seq)`，需要保序时用 `dict.fromkeys`；需要把一组值当作不可变键时用 frozenset；需要集合代数（并交差）时直接用运算符，而不是手写双层循环。

还有几处边界要留意：`s.pop()` 的返回值是任意的，不能拿来实现「取最小」；`remove` 与 `discard` 对缺失元素的行为不同，清理可选元素用后者；遍历 set 时增删会与 dict 一样抛 `RuntimeError`，应遍历副本。

哈希随机化是安全设计而非 bug，跨进程的顺序差异要靠 `sorted()` 消除，不能靠固定 `PYTHONHASHSEED` 来掩盖——那会重新暴露哈希碰撞攻击面。

set 在 CPython 里是与 dict 同源的哈希表：表项只存 `(hash, key)` 而不存 value，查找时对元素求 hash、用 mask 取模定位槽位，冲突时按扰动序列开放寻址探测，因此 `add` / `remove` / `in` 平均 `O(1)`、最坏 `O(n)`，负载因子超过约 2/3 就扩容并 rehash。

删除同样写墓碑标记而不是立即压缩，扩容时才清理。元素必须可哈希，set 本身是可变对象所以不可哈希，`frozenset()` 则把表冻结并允许求 hash，能作 dict 键或嵌套进另一个 set。

顺序不保证是这套结构的直接后果：遍历按表槽位顺序走，而 str / bytes 的哈希从 3.3 起默认带 `PYTHONHASHSEED` 随机盐（防哈希碰撞攻击），同一份字符串集合在不同进程里遍历顺序可能不同；整数哈希等于自身（`-1` 被保留作错误码故映射为 `-2`），纯整数集合看起来顺序稳定但仍不该依赖它。

`dict.fromkeys` 能保序去重，是因为 3.7 起 dict 按插入顺序遍历，它把首次出现编码成了键顺序，这与 set 的去重语义正好互补。


### 保序去重用 dict.fromkeys

既去重又留原顺序，`dict.fromkeys` 是 3.7 之后最省事的：`list(dict.fromkeys(seq))` 借 dict 的插入顺序，把每个值首次出现编码成键顺序，整体 `O(n)`，比 set 再 `sorted()` 更贴「保序」而非「排序」。

它和 `set(seq)` 的差别只在顺序——后者按哈希槽位遍历、跨进程还会变。

有个坑：`dict.fromkeys(keys, [])` 的第二参数只求值一次，所有键共享同一列表，改一个全变，要独立写 `{k: [] for k in keys}`。

后面的术语卡收这组关系。

<Term word='集合的哈希实现' text='CPython 的 set 与 dict 同源，都是开放寻址哈希表，只是表项只存 `(hash, key)` 而不存 value。`add` / `remove` / `in` 平均 `O(1)`、最坏 `O(n)`（哈希冲突严重时会退化成线性探测），负载因子超过约 2/3 就扩容并 rehash；删除同样写墓碑标记…' />

<Term word='增删与运算' text='set 是可变对象，所以不可哈希，既不能作 dict 键也不能塞进另一个 set；`frozenset(iterable)` 把表冻结后允许求 hash，于是能表达「顺序无关的一组标签」这类键：`frozenset([&#39;a&#39;,&#39;b&#39;])` 与 `frozenset([&#39;b&#39;,&#39;a&#39;])` 相等且哈希相同，会命中同一条规…' />


## 日志去重与标签过滤：set 判重、frozenset 规则键与保序输出

一个日志分析器要在大量记录里过滤掉重复的请求 ID，并按首次出现顺序输出，同时把标签组合当作规则缓存的键。直接写成「若 `rid` 不在 `seen_list` 就追加」会退化成 `O(n²)`；正确做法是维护一个 set 做 `O(1)` 判重，再用一个保序列表记录首次出现的 ID。

规则缓存的键是一组标签，用 `frozenset(labels)` 表达顺序无关、可哈希的语义，这样不同顺序的同一组标签能命中同一条规则。

最后用集合运算求同时带 a 与 b、带 a 不带 b 的请求，并用 `sorted()` 得到可复现输出，避免把 set 遍历顺序写进日志或断言。重点是 `O(1)` 判重、可哈希规则键、保序输出三件事分别用对结构。

```python
RECORDS = [
    ('r1', frozenset(['a', 'b'])),
    ('r2', frozenset(['a'])),
    ('r1', frozenset(['a', 'b'])),
    ('r3', frozenset(['b', 'c'])),
    ('r4', frozenset([])),
]

seen = set()
ordered = []
for rid, tags in RECORDS:
    if rid not in seen:
        seen.add(rid)
        ordered.append((rid, tags))
print('unique count', len(ordered), 'order', [r for r, _ in ordered])

rule_cache = {frozenset(['a', 'b']): 'rule-AB'}
print('rule hit', rule_cache.get(frozenset(['b', 'a'])))

with_a = {rid for rid, tags in RECORDS if 'a' in tags}
with_b = {rid for rid, tags in RECORDS if 'b' in tags}
print('both', sorted(with_a & with_b))
print('a not b', sorted(with_a - with_b))
print('symmetric', sorted(with_a ^ with_b))
```

<Callout type="idea" title='落地提示' text='需要保序去重时用 dict.fromkeys；需要可哈希集合做键时用 frozenset' />


## 集合误用速查与自测

<Exercise title='基础：对比 list 与 set 的判重复杂度' task='对 4000 个元素分别用 list 与 set 做 4000 次成员判断并计时，验证 set 明显更快；再用 list(dict.fromkeys(seq)) 保序去重。' solution='from time import perf_counter\ndata = list(range(4000))\nprobes = list(range(4000))\ndef bench(seq):\n    t0 = perf_counter()\n    for x in probes:\n        x in seq\n    return perf_counter() - t0\nprint(&#39;set faster&#39;, bench(data) &gt; bench(set(data)) * 5)\nseq = [&#39;b&#39;, &#39;a&#39;, &#39;b&#39;, &#39;c&#39;, &#39;a&#39;]\nprint(&#39;ordered dedup&#39;, list(dict.fromkeys(seq)))\nprint(&#39;unordered dedup&#39;, sorted(set(seq)))' explain='list 的 in 是线性扫描，n 次判重是 O(n²)；set 平均 O(1)。dict.fromkeys 借助 3.7+ 的插入顺序得到按首次出现保序的去重结果，set 去重则顺序不定，需用 sorted 才能稳定输出。' />

<Exercise title='进阶：用 frozenset 做可哈希的规则键并实现集合运算' task='把若干标签组合构造成 frozenset 当作 dict 键，验证不同顺序的同一组合命中同一规则；再实现并、交、差、对称差与子集判断，并对结果排序保证可复现。' solution='rules = {frozenset([&#39;vip&#39;, &#39;cn&#39;]): &#39;discount&#39;, frozenset([&#39;vip&#39;]): &#39;base&#39;}\nprint(&#39;order independent&#39;, rules[frozenset([&#39;cn&#39;, &#39;vip&#39;])])\na = frozenset([1, 2, 3])\nb = {3, 4}\nprint(&#39;union&#39;, sorted(a | b), &#39;type&#39;, type(a | b).__name__)\nprint(&#39;inter&#39;, sorted(a &amp; b), &#39;diff&#39;, sorted(a - b), &#39;sym&#39;, sorted(a ^ b))\nprint(&#39;subset&#39;, frozenset([1, 2]) &lt;= a, &#39;disjoint&#39;, a.isdisjoint({9}))' explain='frozenset 不可变且可哈希，且相等性与元素顺序无关，适合做顺序无关的规则键；它与 set 做 | &amp; - ^ 时结果仍是 frozenset。对结果排序是为了让输出可复现，而不是假定集合有顺序。' />

<Quiz no='023-1' q='为什么集合的遍历顺序不该被依赖？' :options='["因为 set 按哈希表槽位遍历，且 str/bytes 哈希带随机盐，跨进程可能不同", "因为 Python 每次都主动打乱集合", "因为 set 内部是排序的二叉树", "因为只有 frozenset 才无序"]' answer="0" explain='set 是哈希表，顺序由元素哈希与表大小决定；3.3 起 str/bytes 哈希默认带 PYTHONHASHSEED 随机盐，同一份数据在不同进程里顺序可能不同。' />

<Quiz no='023-2' q='需要去重且保留首次出现顺序，正确写法是？' :options='["list(set(seq))", "list(dict.fromkeys(seq))", "sorted(set(seq))", "set(seq)"]' answer="1" explain='3.7 起 dict 按插入顺序遍历，dict.fromkeys 把首次出现编码成键顺序；list(set(seq)) 顺序不定，sorted 是按值排序而非保序。' />

<Quiz no='023-3' q='把一组标签当作 dict 键且要求顺序无关，应该用？' :options='["list(tags)", "set(tags)", "frozenset(tags)", "tuple(tags)"]' answer="2" explain='list 与 set 都不可哈希，tuple 顺序敏感；frozenset 不可变、可哈希、相等性与顺序无关，正好表达标签组合。' />

<Predict no='023-4' q='seq = [&#39;b&#39;, &#39;a&#39;, &#39;b&#39;, &#39;c&#39;, &#39;a&#39;]; print(list(dict.fromkeys(seq)), sorted(set(seq))) 输出什么？' :options='["[&#39;b&#39;, &#39;a&#39;, &#39;c&#39;] [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;]", "[&#39;a&#39;, &#39;b&#39;, &#39;c&#39;] [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;]", "[&#39;b&#39;, &#39;a&#39;, &#39;c&#39;] [&#39;b&#39;, &#39;a&#39;, &#39;c&#39;]"]' answer='0' output='[&#39;b&#39;, &#39;a&#39;, &#39;c&#39;] [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;]' explain='dict.fromkeys 按首次出现顺序保留键，得到 b、a、c；set 去重后顺序由哈希决定，用 sorted 才得到按字母排序的 a、b、c。两者分别对应保序去重与不保序但可排序输出两种需求。' />

<FillBlank no='023-5' tpl='___  KeyError as e:' :answers='["except"]' hint='回想本讲关于 集合的哈希实现 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 哈希表实现与集合运算：O(1) 的边界 的落点。' />

<KnowledgeCard :points='["set 与 dict 同源，都是只存 (hash, key) 的开放寻址哈希表；add / remove / in 平均 O(1)、最坏 O(n)，负载因子约 2/3 时扩容并 rehash", "集合不保证顺序；3.3 起 str / bytes 哈希带 PYTHONHASHSEED 随机盐，跨进程遍历顺序可能不同", "| &amp; - ^ 分别是并、交、差、对称差，|= &amp;= -= ^= 是原地版本；remove 缺失抛 KeyError，discard 静默忽略", "frozenset 不可变且可哈希，可作 dict 键与 set 元素；与 set 做运算结果仍是 frozenset", "{} 是空 dict，空集合必须写 set()；s.pop() 返回任意元素，空集合抛 KeyError", "保序去重写 list(dict.fromkeys(seq))；高频判重先规整成 set，别对 list 反复用 in"]' :pitfalls='["对 list 反复用 in 判重，数据量一大就卡死", "用 set(seq) 去重后抱怨顺序乱了", "把可变 set 当 dict 键或塞进另一个 set", "对 list 反复用 in 判重会让整体复杂度变成 O(n²)，数据一上来就卡死"]' summary='集合不保证顺序，且字符串哈希带随机盐，跨进程遍历顺序可能不同；这不是 bug，是安全设计' />

1. set 与 dict 同源，都是只存 (hash, key) 的开放寻址哈希表；add / remove / in 平均 O(1)、最坏 O(n)，负载因子约 2/3 时扩容并 rehash

2. 集合不保证顺序；3.3 起 str / bytes 哈希带 PYTHONHASHSEED 随机盐，跨进程遍历顺序可能不同

3. | & - ^ 分别是并、交、差、对称差，|= &= -= ^= 是原地版本；remove 缺失抛 KeyError，discard 静默忽略

[下一讲：推导式：四种写法与可读性边界](/containers/comprehension)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/023-set.py`

```bash
python3 examples/lessons/023-set.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/023-set.py) · [全部示例代码索引](/examples/)
