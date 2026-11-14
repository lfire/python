---
title: 第 021 讲 · dict：哈希表、视图与插入顺序
description: 理解字典为什么快、什么时候会退化
---

<StageHeader stage='L2 · 容器与序列' level='★★☆☆☆' time='30 分钟' goal='理解字典为什么快、什么时候会退化' prereq='第 020 讲 · tuple 与具名元组：不可变性的价值' />

# 第 021 讲 · dict：哈希表、视图与插入顺序

按下标找东西很快，可现实里更常按“名字”找：给编号找画像。上一讲讲了定住的元组，这一讲转向按名字存取、处处都在用的 `dict`，弄清它为什么快、何时会悄悄失灵。

一个推荐服务在二十万条记录里按编号查画像，起初每次从头扫，请求一多处理器就吃紧；规整成字典后立刻轻快，却又冒出怪事：存下的键列表自己变了、自定义对象一当键就报错。我们先看哈希与开放寻址怎么换来平均常数级查找、新版为何保序；再讲三种视图是动态反映而非快照，以及取值的返回约定；最后落到键的可哈希要求。需要你熟悉哈希、元组与遍历。学完你能把反复扫描改成按键直取，也说得清一次查找为何静默失效。


## 定义了 __eq__ 之后，对象突然做不了字典键

一个推荐服务要在 20 万条用户记录里按 `user_id` 反复查画像，最初是拿 `for` 逐条比对 `r['id']` 与 `uid`、命中才 `return`，每次查询都线性扫一遍，QPS 刚上来 CPU 就打满。

改成用字典推导 `{r['id']: r}` 对每条记录建索引后，单次查找降到平均 `O(1)`，问题看似解决，却接连冒出三类新故障：有人把 `d.keys()` 存起来当某一时刻的快照，之后字典增删了键，报表里的用户数自己变了；

有人在 `for k in d:` 循环里给字典加键，直接抛 `RuntimeError`，提示迭代期间字典大小变了；还有人自定义的类写了 `__eq__` 却没写 `__hash__`，拿它作键时抛 `TypeError`，提示类型不可哈希。这些都不是语法问题，而是对哈希表、动态视图与可哈希契约的默认行为缺一张清晰的账。

本讲把 `dict` 的紧凑布局、视图语义、版本差异与键的约束逐条钉死。

<Callout type="warn" title='先看一个真实会出错的写法' text='自定义类定义了 __eq__ 后无法作 dict 键：定义 __eq__ 而不定义 __hash__ 时，解释器把 __hash__ 设为 None，实例不可哈希' />


## 紧凑哈希表：平均 O(1) 从哪来

CPython 3.6 起 `dict` 用紧凑哈希表，分两块：一块连续的 entries 数组按插入顺序存 `(hash, key, value)` 三元组，另一块稀疏的 indices 数组只存 entry 的下标，下标宽度随表规模取 1 / 2 / 4 字节。

查找时对 key 求 `hash`，用 `i = hash & mask` 定位 indices 槽，冲突时按扰动序列更新探测下标 `i`：`i = (i * 5 + perturb + 1) & mask`，反复找下一个空槽（开放寻址），所以平均 `O(1)`、最坏 `O(n)`（大量冲突时退化为线性探测），负载因子超过约 2/3 就扩容并 `rehash`。

删除不立即搬移条目，只写墓碑标记，扩容时才清理，因此频繁增删后最好重建字典。紧凑布局把内存降到旧版约一半，还顺带让「按 entries 顺序遍历」天然等于插入顺序：3.6 只是 CPython 的实现细节，3.7 起才写进语言规范，同时 `popitem()` 从弹出任意项改为 `LIFO` 弹出最后插入项。

3.8 起 `dict` 与它的视图支持 `reversed()` 按键逆序；3.9 的 PEP 584 加入 `|` 与 `|=` 合并运算符。理解这两块数组，才能解释为什么遍历顺序稳定、为什么迭代中改大小会出事。

```python
d = {'a': 1, 'b': 2}
print('get', d.get('a'), d.get('z'), d.get('z', 99))
print('setdefault new', d.setdefault('c', 3), 'existing', d.setdefault('a', 100))
print('order', list(d), d['c'])

keys = d.keys()
values = d.values()
items = d.items()
d['d'] = 4
print('view live', list(keys), len(values), ('d', 4) in items)
print('view set ops', sorted(keys & {'a', 'd'}))

merged = d | {'b': 20, 'e': 5}
print('merge new', merged['b'], merged['e'], 'original b', d['b'])
d.update({'f': 6})
print('update returns', d.update({'g': 7}), 'has g', 'g' in d)

class NoHash:
    def __eq__(self, other):
        return True
try:
    {NoHash(): 1}
except TypeError as e:
    print('unhashable', type(e).__name__)
print('reversed keys', list(reversed(d)))
```

<OutputBox title='主示例运行结果' output='get 1 None 99\nsetdefault new 3 existing 1\norder [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;] 3\nview live [&#39;a&#39;, &#39;b&#39;, &#39;c&#39;, &#39;d&#39;] 4 True\nview set ops [&#39;a&#39;, &#39;d&#39;]\nmerge new 20 5 original b 2\nupdate returns None has g True\nunhashable TypeError\nreversed keys [&#39;g&#39;, &#39;f&#39;, &#39;d&#39;, &#39;c&#39;, &#39;b&#39;, &#39;a&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='d = {&#39;a&#39;: 1, &#39;b&#39;: 2}\nprint(&#39;get&#39;, d.get(&#39;a&#39;), d.get(&#39;z&#39;), d.get(&#39;z&#39;, 99))\nprint(&#39;setdefault new&#39;, d.setdefault(&#39;c&#39;, 3), &#39;existing&#39;, d.setdefault(&#39;a&#39;, 100))\nprint(&#39;order&#39;, list(d), d[&#39;c&#39;])\n\nkeys = d.keys()\nvalues = d.values()\nitems = d.items()\nd[&#39;d&#39;] = 4\nprint(&#39;view live&#39;, list(keys), len(values), (&#39;d&#39;, 4) in items)\nprint(&#39;view set ops&#39;, sorted(keys &amp; {&#39;a&#39;, &#39;d&#39;}))\n\nmerged = d | {&#39;b&#39;: 20, &#39;e&#39;: 5}\nprint(&#39;merge new&#39;, merged[&#39;b&#39;], merged[&#39;e&#39;], &#39;original b&#39;, d[&#39;b&#39;])\nd.update({&#39;f&#39;: 6})\nprint(&#39;update returns&#39;, d.update({&#39;g&#39;: 7}), &#39;has g&#39;, &#39;g&#39; in d)\n\nclass NoHash:\n    def __eq__(self, other):\n        return True\ntry:\n    {NoHash(): 1}\nexcept TypeError as e:\n    print(&#39;unhashable&#39;, type(e).__name__)\nprint(&#39;reversed keys&#39;, list(reversed(d)))' :notes='["构造一个按插入顺序保存的 dict", "get 对缺失键返回 None 或给定默认值，不抛 KeyError", "setdefault 对缺失键插入并返回默认值，对已有键返回现值", "list(d) 按插入顺序给出键，c 已被上一步插入", "空行，只用于分隔逻辑块，不影响执行结果。", "创建 keys 动态视图，此时只有三个键", "创建 values 动态视图", "创建 items 动态视图，元素是键值对元组", "创建视图之后再插入新键 d", "三个视图立即反映新键，证明它们不是快照", "keys 视图可与 set 做交集运算，用 sorted 保证输出可复现", "空行，只用于分隔逻辑块，不影响执行结果。", "用 3.9+ 的 | 生成新字典，右侧的 b 覆盖左侧", "新字典里 b 被覆盖、e 被加入，原字典的 b 仍是 2", "update 是原地方法，返回 None", "再次 update 返回 None，新键 g 已写入原字典", "空行，只用于分隔逻辑块，不影响执行结果。", "定义一个只实现 __eq__ 的类", "写 __eq__ 会把 __hash__ 自动置为 None", "恒返回 True 只为演示可哈希性检查", "尝试把该实例用作 dict 键", "触发 TypeError，实例不可哈希", "捕获并打印异常类型", "3.8 起 dict 可 reversed，按键逆序（即插入顺序反过来）", "keys / values / items 是动态视图不是快照；迭代中改变大小抛 RuntimeError"]' title='第 021 讲 · dict：哈希表、视图与插入顺序' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='CPython 3.6 起 `dict` 用紧凑哈希表，分两块：一块连续的 entries 数组按插入顺序存 `(hash, key, value)` 三元组，另一块稀疏的 indices 数组只存 entry 的下标，下标宽度随表规模取 1 / 2 / 4 字节。查找时对 key 求 `hash`…' />


## 为什么 3.7 起 dict 保证插入顺序

<ConceptDiagram type='flow4' title='第 021 讲 · 紧凑哈希表：平均 O(1) 从哪来，为什么 3.7 起保序' labels='紧凑哈希表：平均 O(1) 从哪来，为什么…|视图、get / setdefault 与合…|可哈希契约：__eq__、__hash__…|冲突与负载因子' caption='理解字典为什么快、什么时候会退化' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

CPython 3.6 起 `dict` 用紧凑哈希表：一块连续的 entries 数组按插入顺序存 `(hash, key, value)` 三元组，另一块稀疏的 indices 数组只存 entry 下标，下标宽度随表规模取 1 / 2 / 4 字节。

查找时对 key 求 `hash`，用 `i = hash & mask` 定位 indices 槽，冲突时按扰动序列反复探测（开放寻址），因此平均 `O(1)`、最坏 `O(n)`。

紧凑布局把内存降到旧版约一半，同时让按 entries 顺序遍历天然等于插入顺序——3.6 只是 CPython 实现细节，3.7 起才写进语言规范，`popitem()` 也随之从任意项改为 `LIFO` 弹出最后插入项。

键必须同时实现 `__hash__` 与 `__eq__`：若类定义了 `__eq__` 却没定义 `__hash__`，解释器把 `__hash__` 置为 `None`，实例不可哈希；哈希值在对象生命周期内必须不变，否则插入后查找会静默失败。删除不立即搬移条目，只写墓碑标记，扩容时才清理。

`str` / `bytes` 的哈希带随机盐用来抵御哈希碰撞攻击，`dict` 顺序不受它影响，`set` 顺序会。


## dict 操作与时间复杂度

**dict 操作与时间复杂度**

| 操作 | 平均复杂度 | 说明 |
| --- | --- | --- |
| d[k] / d[k] = v / len(d) | O(1) | 哈希定位加开放寻址探测 |
| k in d / get / setdefault | O(1) | get 缺失返回 default 不抛异常 |
| d.pop(k) / del d[k] | O(1) | 删除留墓碑标记，扩容时才压缩 |
| keys() / values() / items() | O(1) 创建视图 | 动态反映后续变化，不是快照 |
| d \| other / d.update(other) | O(n + m) | 前者 3.9+ 返回新 dict，后者原地返回 None |
| 最坏情况查找 | O(n) | 大量哈希冲突时退化为线性探测 |


## 视图、get / setdefault 与合并的返回约定

`d.keys()`、`d.values()`、`d.items()` 返回的不是 `list` 快照，而是 `dict_keys` / `dict_values` / `dict_items` 动态视图：它们直接指向底层字典，创建之后再增删键，视图的 `len`、`in` 与迭代结果立即反映变化；

视图支持 `len()` 与迭代，keys 与 items 视图还支持 `& | - ^` 集合运算（items 的元素是 `(key, value)` 元组），values 视图因值可能不可哈希而不支持集合运算。

代价是在迭代视图或字典的过程中改变字典大小，会抛 `RuntimeError`，提示迭代期间字典大小变了，修复是遍历 `list(d)` 或 `list(d.items())` 的副本。

取值上 `d[k]` 缺失抛 `KeyError`，`d.get(k, default=None)` 缺失返回 `default` 且不抛异常，`d.setdefault(k, default)` 缺失时插入 `default` 再返回、存在时返回现有值——注意 `default` 表达式每次调用都会被求值，即使键已存在，别把昂贵计算放进去。

合并有三种写法：`d | other`（3.9+）返回新 `dict` 且右侧键覆盖左侧，`{**d, **other}`（3.5+）同样是新字典，而 `d.update(other)` 是原地修改并返回 `None`；

`dict.fromkeys` 是类方法，value 若为可变对象会被所有键共享，这点与列表乘法同源。

```python
d = {'a': 1, 'b': 2}
try:
    for k in d:
        d[k * 2] = 1
except RuntimeError as e:
    print('resize during iteration', type(e).__name__)

shared = dict.fromkeys(['x', 'y'], [])
shared['x'].append(9)
print('fromkeys shared', shared)

print('hash seed differs', type(hash('a')).__name__)
print('keys view type', type(d.keys()).__name__)
print('values has set ops', hasattr(d.values(), '__and__'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='resize during iteration RuntimeError\nfromkeys shared {&#39;x&#39;: [9], &#39;y&#39;: [9]}\nhash seed differs int\nkeys view type dict_keys\nvalues has set ops False' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "d = {&#39;a&#39;: 1, &#39;b&#39;: 2}\nprint(&#39;get&#39;, d.get(&#39;a&#39;), d.get(&#39;z&#39;), d.get(&#39;z&#39;, 99))\nprint(&#39;setdefault new&#39;, d.setdefault(&#39;c&#39;, 3), &#39;existing&#39;, d.setdefault(&#39;a&#39;, 100))\nprint(&#39;order&#39;, list(d), d[&#39;c&#39;])\n\nkeys = d.keys()\nvalues = d.values()\nitems = d.items()\nd[&#39;d&#39;] = 4\nprint(&#39;view live&#39;, list(keys), len(values), (&#39;d&#39;, 4) in items)\nprint(&#39;view set ops&#39;, sorted(keys &amp; {&#39;a&#39;, &#39;d&#39;}))\n\nmerged = d | {&#39;b&#39;: 20, &#39;e&#39;: 5}\nprint(&#39;merge new&#39;, merged[&#39;b&#39;], merged[&#39;e&#39;], &#39;original b&#39;, d[&#39;b&#39;])\nd.update({&#39;f&#39;: 6})\nprint(&#39;update returns&#39;, d.update({&#39;g&#39;: 7}), &#39;has g&#39;, &#39;g&#39; in d)\n\nclass NoHash:\n    def __eq__(self, other):\n        return True\ntry:\n    {NoHash(): 1}\nexcept TypeError as e:\n    print(&#39;unhashable&#39;, type(e).__name__)\nprint(&#39;reversed keys&#39;, list(reversed(d)))", "note": "紧凑哈希表：平均 O(1) 从哪来，为什么 3.7 起保序"}, {"label": "对照 / 进阶", "code": "d = {&#39;a&#39;: 1, &#39;b&#39;: 2}\ntry:\n    for k in d:\n        d[k * 2] = 1\nexcept RuntimeError as e:\n    print(&#39;resize during iteration&#39;, type(e).__name__)\n\nshared = dict.fromkeys([&#39;x&#39;, &#39;y&#39;], [])\nshared[&#39;x&#39;].append(9)\nprint(&#39;fromkeys shared&#39;, shared)\n\nprint(&#39;hash seed differs&#39;, type(hash(&#39;a&#39;)).__name__)\nprint(&#39;keys view type&#39;, type(d.keys()).__name__)\nprint(&#39;values has set ops&#39;, hasattr(d.values(), &#39;__and__&#39;))", "note": "视图、get / setdefault 与合并的返回约定"}]' title='两种写法切换看' />


### keys() 不是快照：动态视图的失效信号

**dict 关键版本差异**

| 版本 | 变化 | 对代码的影响 |
| --- | --- | --- |
| 3.6 | CPython 紧凑 dict：entries 按插入顺序存，indices 为稀疏下标 | 仅实现细节，顺序还不是语言保证 |
| 3.7 | 插入顺序正式成为语言规范；popitem() 改为 LIFO 弹出最后插入项 | 遍历与序列化顺序可依赖 |
| 3.8 | dict 与 dict 视图支持 reversed() | 可按键逆序遍历 |
| 3.9 PEP 584 | 新增 \| 与 \|= 合并运算符 | d \| e 返回新字典，d \|= e 原地修改 |
| 3.9 之前 | 合并用 &#123;**d, **e&#125; 或 d.copy() 加 update() | 右侧键覆盖左侧 |

<Callout type="warn" title='本讲最容易踩的坑' text='自定义类定义了 __eq__ 后无法作 dict 键：定义 __eq__ 而不定义 __hash__ 时，解释器把 __hash__ 设为 None，实例不可哈希' />


## 可哈希契约：__eq__、__hash__ 与失效信号

`dict` 的键必须可哈希：对象要同时提供 `__hash__` 与 `__eq__`，且哈希值在对象生命周期内保持不变。最典型的坑是自定义类只写了 `__eq__`：解释器会把 `__hash__` 自动置为 `None`，实例变成不可哈希，作键时抛 `TypeError`，提示类型不可哈希；

正确做法是同步实现基于不可变字段的 `__hash__`，比如返回 `hash((self.a, self.b))`，或干脆用不可变字段组成的 `tuple` 作键。

哈希值还必须稳定：若把对象插入 `dict` 后改了参与哈希的字段，再查同一个键会静默查不到，因为新哈希定位到另一个槽，且不报任何错——这是最难排查的一类 bug。

`str` 与 `bytes` 的哈希带 `PYTHONHASHSEED` 随机盐（3.3 起默认开启，防哈希碰撞攻击），所以 `hash('k')` 跨进程不同，但 `dict` 的遍历顺序按插入顺序、不受盐影响；不要把 `hash()` 的结果持久化或当作稳定 ID。

`collections.abc.Mapping` 只抽象 `__getitem__` / `__iter__` / `__len__`，mixin 免费提供 `get` / `keys` / `items` / `values` / `in`，自定义映射实现这三个方法即可接入同一套协议。

```python
import sys

class NoHash:
    def __eq__(self, other):
        return True
print('hash slot is None', NoHash.__hash__ is None)

d = {}
sizes = []
for i in range(200):
    d[i] = i
    sizes.append(sys.getsizeof(d))
changes = sum(1 for i in range(1, len(sizes)) if sizes[i] != sizes[i - 1])
print('resize is stepwise', 0 < changes < 200)

v = d.keys()
print('view reflects size', len(v) == len(d))
print('view type', type(v).__name__)
print('hash is int', isinstance(hash('k'), int))
```

<OutputBox title='原理验证' output='hash slot is None True\nresize is stepwise True\nview reflects size True\nview type dict_keys\nhash is int True' />


## dict 关键版本差异

**常见错因与修复**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 自定义对象作键抛 TypeError | 定义 __eq__ 却没定义 __hash__，__hash__ 被自动置 None | 同步实现 __hash__，或改用不可变字段的 tuple 作键 |
| 把 keys() 当快照，结果莫名变多 | 返回的是动态视图，字典增删立即反映 | 需要快照用 list(d.keys()) 或 list(d.items()) |
| 迭代 dict 时增删键 | 改变大小触发 dictionary changed size during iteration | 迭代 list(d) 或 list(d.items()) 的副本 |
| dict.fromkeys(keys, []) 改一个值全变 | value 参数是同一个可变对象，被所有键共享 | 用字典推导 &#123;k: [] for k in keys&#125; |
| 跨进程假设哈希值固定 | str / bytes 哈希带 PYTHONHASHSEED 随机盐 | 不要把 hash() 结果持久化，顺序依赖用 sorted |

<FlowTimeline :steps='[{"title": "紧凑哈希表：平均 O(1) 从哪来，为什么 3.…", "desc": "CPython 3.6 起 `dict` 用紧凑哈希表，分两块：一块连续的 entr…", "tone": "blue"}, {"title": "视图、get / setdefault 与合并的…", "desc": "`d.keys()`、`d.values()`、`d.items()` 返回的不是…", "tone": "purple"}, {"title": "可哈希契约：__eq__、__hash__ 与失…", "desc": "`dict` 的键必须可哈希：对象要同时提供 `__hash__` 与…", "tone": "orange"}, {"title": "工程落地", "desc": "用户画像索引：从线性扫描改造成 dict 并保留视图做增量更新", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 用户画像索引：从线性扫描改造成 dict 并保留视图做增量更新

一个推荐服务要在大量用户记录里按 `user_id` 反复查画像，最初写成逐条比对列表，每次查询 `O(n)`，QPS 一上来就打满 CPU。正确做法是启动时把列表规整成 `{r['id']: r}` 的 `dict`，把单次查找降到平均 `O(1)`；

再保留一个 `keys()` 视图做在线监控，统计当前在线用户数不必每次复制一份列表。更新阶段用 `d | batch` 生成新字典做无锁切换，避免在原字典上 `update` 时与正在迭代的视图冲突（那会抛 `RuntimeError`）；

最后演示 `setdefault` 把缺省画像补进字典，以及用 `sorted` 得到稳定顺序输出。重点是一次规整多次查找，与迭代期不改大小这两条工程约束。

```python
RECORDS = [
    {'id': 1001, 'tier': 'vip'},
    {'id': 1002, 'tier': 'free'},
    {'id': 1003, 'tier': 'vip'},
]

def build_index(rows):
    return {r['id']: r for r in rows}

index = build_index(RECORDS)
online = index.keys()
print('lookup 1002', index.get(1002), 'missing', index.get(9999))
print('online count', len(online))

batch = {1004: {'id': 1004, 'tier': 'free'}, 1002: {'id': 1002, 'tier': 'vip'}}
new_index = index | batch
print('merge overrides', new_index[1002]['tier'], 'original', index[1002]['tier'])

new_index.setdefault(1005, {'id': 1005, 'tier': 'free'})
print('after setdefault', len(new_index), sorted(new_index)[:3])
print('vip ids', [k for k in sorted(new_index) if new_index[k]['tier'] == 'vip'])
```

<Callout type="idea" title='落地提示' text='高频查找先把数据规整成 dict，不要反复线性扫描列表；合并用 | 或 update，注意后者是原地修改' />

<CheckList id='P021b' title='上线前自检' :items='["能复现并解释「自定义类定义了 __eq__ 后无法作 dict 键」", "能复现并解释「把 d.keys() 当快照存起来，之后结果莫名变多」", "能复现并解释「遍历 dict 时插入新键抛 RuntimeError」", "能用一条命令验证 哈希与开放寻址", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from collections import Counter; print(Counter('a b a'.split()))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 哈希与开放寻址 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 键失效信号与哈希自测

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 自定义类定义了 __eq__ 后无法作 dict 键 | 定义 __eq__ 而不定义 __hash__ 时，解释器把 __hash__ 设为 None，实例不可哈希 | 同步实现 __hash__（如 return hash((self.a, self.b))），或改用不可变字段组成的 tuple 作键 |
| 把 d.keys() 当快照存起来，之后结果莫名变多 | keys / values / items 返回动态视图，字典增删后立即反映，不是独立列表 | 需要快照用 list(d.keys()) 或 list(d.items())，再传给下游 |
| 遍历 dict 时插入新键抛 RuntimeError | 迭代过程中改变字典大小会触发 dictionary changed size during iteration | 遍历 list(d) 或 list(d.items()) 的副本，或先把要加的键收集到列表、循环结束后再写 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：自定义类定义了 __eq__ 后无法作 di…", "body": "定义 __eq__ 而不定义 __hash__ 时，解释器把 __hash__ 设为 None，实例不可哈希", "tip": "同步实现 __hash__（如 return hash((self.a, self.b))），或改用不可变字段组成的 tuple 作键"}, {"title": "第 2 步：把 d.keys() 当快照存起来，之后结果…", "body": "keys / values / items 返回动态视图，字典增删后立即反映，不是独立列表", "tip": "需要快照用 list(d.keys()) 或 list(d.items())，再传给下游"}, {"title": "第 3 步：遍历 dict 时插入新键抛 Runtime…", "body": "迭代过程中改变字典大小会触发 dictionary changed size during iteration", "tip": "遍历 list(d) 或 list(d.items()) 的副本，或先把要加的键收集到列表、循环结束后再写"}]' />

<Exercise title='基础：验证视图是动态的不是快照' task='创建 keys 与 items 视图后修改字典，打印视图内容变化；再演示迭代字典时新增键抛 RuntimeError，并给出安全写法。' solution='d = {&#39;a&#39;: 1}\nkeys = d.keys()\nitems = d.items()\nd[&#39;b&#39;] = 2\nprint(&#39;keys live&#39;, list(keys), &#39;items live&#39;, (&#39;b&#39;, 2) in items)\ntry:\n    for k in d:\n        d[k + &#39;x&#39;] = 0\nexcept RuntimeError as e:\n    print(&#39;resize error&#39;, type(e).__name__)\nfor k in list(d):\n    d[k + &#39;y&#39;] = 0\nprint(&#39;safe iteration&#39;, len(d))' explain='keys 与 items 是动态视图，字典变化立即反映；迭代中改变字典大小会抛 RuntimeError，因为哈希表可能已扩容。用 list(d) 或 list(d.items()) 做快照后再写是标准修复。' />

<Exercise title='进阶：给自定义类补 __hash__ 让它能作 dict 键' task='定义一个只写了 __eq__ 的类，验证它不可哈希；再补上基于不可变字段的 __hash__，用作 dict 键并成功取回值；说明为什么哈希值必须在对象生命周期内不变。' solution='class Bad:\n    def __init__(self, k): self.k = k\n    def __eq__(self, o): return isinstance(o, Bad) and self.k == o.k\n\nclass Good:\n    def __init__(self, k): self.k = k\n    def __eq__(self, o): return isinstance(o, Good) and self.k == o.k\n    def __hash__(self): return hash(self.k)\n\nprint(&#39;bad hash&#39;, Bad.__hash__)\ntry:\n    {Bad(1): &#39;x&#39;}\nexcept TypeError as e:\n    print(&#39;bad unhashable&#39;, type(e).__name__)\ng = Good(7)\nd = {g: &#39;value&#39;}\nprint(&#39;good lookup&#39;, d[Good(7)], &#39;hash stable&#39;, hash(g) == hash(Good(7)))' explain='定义 __eq__ 会把 __hash__ 置 None，必须显式补回；__hash__ 应基于不可变字段，保证相等对象哈希相等、且对象插入 dict 后哈希值不变，否则查找会静默失败。' />

<Quiz no='021-1' q='关于 d.keys() / d.values() / d.items()，哪项正确？' :options='["返回三个独立的 list 快照", "返回动态视图，字典变化立即反映，且 keys 与 items 支持集合运算", "每次调用都复制全部键值", "values() 也支持 &amp; 集合运算"]' answer="1" explain='三者都是动态视图对象，len 与 in 直接作用于当前字典；keys 与 items 视图支持 &amp; | - ^，values 视图因值可能不可哈希而不支持集合运算。' />

<Quiz no='021-2' q='类里定义了 __eq__ 却没定义 __hash__，用它作 dict 键会？' :options='["正常，哈希退化为对象 id", "抛 TypeError: unhashable type", "永远命中同一个槽", "自动用 __eq__ 结果当哈希"]' answer="1" explain='定义 __eq__ 会把 __hash__ 置为 None，实例不可哈希；必须同步实现基于不可变字段的 __hash__，或改用 tuple 作键。' />

<Quiz no='021-3' q='d | other 与 d.update(other) 的区别是？' :options='["两者都原地修改并返回 None", "d | other 返回新 dict（3.9+），update 原地修改且返回 None", "d | other 是 3.7 引入的", "update 返回合并后的新 dict"]' answer="1" explain='PEP 584 在 3.9 加入 | 与 |=：| 构造新字典、右侧键覆盖左侧；update 是原地方法、返回 None，且任意版本可用。' />

<Predict no='021-4' q='d = {&#39;a&#39;: 1}; v = d.keys(); d[&#39;b&#39;] = 2; print(list(v), len(v)) 输出什么？' :options='["[&#39;a&#39;] 1", "[&#39;a&#39;, &#39;b&#39;] 2", "抛 RuntimeError"]' answer='1' output='[&#39;a&#39;, &#39;b&#39;] 2' explain='keys() 返回的是动态视图而不是快照，插入 b 后视图立即包含新键、len 变为 2。只有在迭代视图的过程中改变字典大小才会抛 RuntimeError，创建视图后、迭代开始前插入是安全的。' />

<FillBlank no='021-5' tpl='print(&#39;view live&#39;, list(keys), len(values), (&#39;d&#39;, 4) ___ items)' :answers='["in"]' hint='回想本讲关于 哈希与开放寻址 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 紧凑哈希表：平均 O(1) 从哪来，为什么 3.7 起保序 的落点。' />

<KnowledgeCard :points='["dict 平均 O(1) 来自哈希加开放寻址探测；最坏 O(n)；负载因子约 2/3 时扩容", "3.6 紧凑布局（entries 按插入顺序 + 稀疏 indices），3.7 起插入顺序成为语言规范，popitem() 改为 LIFO", "3.8 起 dict 与视图支持 reversed()；3.9 PEP 584 加入 | 与 |= 合并", "keys / values / items 是动态视图不是快照；迭代中改变大小抛 RuntimeError", "键必须可哈希：定义 __eq__ 不写 __hash__ 会把 __hash__ 置 None；哈希值在生命周期内必须不变", "get 缺失返回 default 不抛异常；setdefault 会插入缺失键；update 原地返回 None，| 返回新字典"]' :pitfalls='["自定义类定义了 __eq__ 后无法作 dict 键", "把 d.keys() 当快照存起来，之后结果莫名变多", "遍历 dict 时插入新键抛 RuntimeError", "用可变对象做键、或假设哈希值永不变化，会让查找静默失败；自定义 __eq__ 必须同步 __hash__"]' summary='dict 的平均 O(1) 来自哈希加开放寻址，Python 3.7 起还保证插入顺序；视图对象动态反映字典变化，不是快照' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| dict 平均 O(1) 来自哈希加开放寻址探测；最坏 O(n)；负载因子约 2/3 时扩容 | 建立直觉 |
| 3.6 紧凑布局（entries 按插入顺序 + 稀疏 indices），3.7 起插入顺序成为语言规范，popitem() 改为 LIFO | 跑通示例 |
| 3.8 起 dict 与视图支持 reversed()；3.9 PEP 584 加入 \| 与 \|= 合并 | 深入边界 |
| keys / values / items 是动态视图不是快照；迭代中改变大小抛 RuntimeError | 工程落地 |
| 键必须可哈希：定义 __eq__ 不写 __hash__ 会把 __hash__ 置 None；哈希值在生命周期内必须不变 | 随堂检测 |
| get 缺失返回 default 不抛异常；setdefault 会插入缺失键；update 原地返回 None，\| 返回新字典 | 复盘 |

1. dict 平均 O(1) 来自哈希加开放寻址探测；最坏 O(n)；负载因子约 2/3 时扩容

2. 3.6 紧凑布局（entries 按插入顺序 + 稀疏 indices），3.7 起插入顺序成为语言规范，popitem() 改为 LIFO

3. 3.8 起 dict 与视图支持 reversed()；3.9 PEP 584 加入 | 与 |= 合并

[下一讲：dict 进阶：默认字典、计数器与合并](/containers/dict-advanced)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/021-dict-basics.py`

```bash
python3 examples/lessons/021-dict-basics.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/021-dict-basics.py) · [全部示例代码索引](/examples/)
