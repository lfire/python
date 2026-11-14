---
title: 第 022 讲 · dict 进阶：默认字典、计数器与合并
description: 用标准库容器消灭样板代码
---

<StageHeader stage='L2 · 容器与序列' level='★★☆☆☆' time='25 分钟' goal='用标准库容器消灭样板代码' prereq='第 021 讲 · dict：哈希表、视图与插入顺序' />

# 第 022 讲 · dict 进阶：默认字典、计数器与合并

`dict` 用熟后，有些循环每次都要重写：按字段分组、数词频、把几层配置叠起来。标准库早把这些套路收成现成容器，这一讲看它们省掉哪些样板，又各自改写了什么默认行为。

一个配置服务合并默认、环境与用户三层，换成按层回退后清爽了，压测却发现下游配置会随底层改动悄悄变化。词频那边有人把计数加成当覆盖用，数字翻倍；还有只读一个不存在的键，就把空记录插了进去。我们先看默认字典的工厂与计数器的累加语义，再讲分层映射的查找与写入落点；最后把字典合并与几种容器摆在一起选型。需要你熟悉字典、`get` 与循环累计。学完你能用现成容器替掉样板，也知道哪处读操作会反过来改数据。


## 只读了一个不存在的键，字典却被悄悄改了

一个配置服务把默认配置、环境变量与用户覆盖三层合并，最初的写法是先把默认配置拷一份，再依次用 `env`、`user` 调两遍 `update()`，每次热更新都要重新构造一遍，且无法回答「这个值到底来自哪一层」。

换成 `ChainMap` 后查找按层回退、写入只落用户层，看似完美，却在压测里发现下游拿到的配置对象会随着 `defaults` 改动悄悄变化——因为 `ChainMap` 是活视图不是快照。同一迭代还有两处事故：词频统计把 `Counter.update` 当成 `dict.update` 用，计数翻倍；

`defaultdict` 仅仅读一个不存在的键就把空列表插了进去，读路径污染了数据，导致「在线用户数」凭空多出一批空记录。这些容器把常见循环固化成了 C 级实现，短且快，但各自重写了关键语义。

本讲把 `defaultdict` 的 `__missing__`、`Counter` 的累加、`ChainMap` 的视图与合并方式的快照差异逐条拆开。


## collections 容器对照：把常见循环固化成 C 实现

**collections 容器对照**

| 容器 | 替代的样板 | 关键差异 | 注意 |
| --- | --- | --- | --- |
| defaultdict(list) | 分组前先判断键是否存在再 append | 重写 __missing__，缺键调用工厂并插入 | 读不存在键也会创建，用 get 或 dict() 冻结 |
| Counter | 手写 d[k] = d.get(k, 0) + 1 | dict 子类，缺键返回 0，most_common 排序 | update 是累加不是覆盖，与 dict.update 不同 |
| ChainMap | 多层配置逐层 get 再回退 | 视图式组合，查找按 maps 顺序，写入只落第一层 | 底层 dict 变化会反映，不是复制 |
| OrderedDict | 需要 move_to_end 与 FIFO popitem | 顺序敏感相等，popitem(last=False) | 3.7 起普通 dict 也保序，仅在需要这些操作时才用 |
| dict \| other | 合并两个字典 | 3.9+ 返回新字典快照 | 右侧键覆盖左侧，update 是原地方法 |


## defaultdict 与 Counter：被重写的 __missing__ 与 update

`collections.defaultdict(default_factory=None)` 是 `dict` 子类，重写了 `__missing__(key)`：当 `d[key]` 找不到键时，若 `default_factory` 不为 `None` 就调用它生成值、把 `(key, value)` 真正插入字典再返回。

工厂只在下标访问时触发，`get()` 与 `in` 不会调用 `__missing__`，这正是「读路径也污染数据」的来源——一次 `d[missing]` 就会永久多出一个键。

工程上读完用 `dict(d)` 转成普通 `dict`，或把 `d.default_factory` 置 `None` 来冻结；

需要嵌套分组时用 `lambda: defaultdict(...)`，但更要小心读路径。

`Counter` 同样继承 `dict`，把 `__missing__` 改成返回 0，于是缺键计数天然为 0 且不抛 `KeyError`。

它最容易被误用的是 `update`：`Counter.update(iterable)` 是累加计数，而不是 `dict.update` 的覆盖；

`subtract()` 做减法且允许负数；`most_common(n)` 按计数降序返回列表，计数相等时按首次出现顺序，`n` 为 `None` 返回全部；`elements()` 按计数展开并忽略非正值；`+ - & |` 做多重集运算，`-` 与 `&` 分别丢弃非正结果、取 min；

`total()` 返回计数总和，是 3.10 才加入的。访问不存在的键返回 0，别把它和 `defaultdict` 的「插入默认值」混为一谈。

```python
from collections import defaultdict, Counter, ChainMap

groups = defaultdict(list)
for word in ('a', 'bb', 'c', 'dd', 'ee'):
    groups[len(word)].append(word)
print('groups', dict(groups))
before = len(groups)
_ = groups[99]
print('read created key', len(groups) == before + 1)
print('get avoids factory', groups.get(98), 98 in groups)

c = Counter('banana')
print('counts', c['a'], c['z'], c.most_common(2))
c.update(['a', 'x'])
print('update adds', c['a'], c['x'], c.total())

defaults = {'debug': False, 'port': 8080}
env = {'port': 9000}
user = {'debug': True}
cfg = ChainMap(user, env, defaults)
print('layered', cfg['debug'], cfg['port'])
cfg['timeout'] = 5
print('writes to first', list(user), 'env untouched', env)

a = {'x': 1}
b = {'x': 2, 'y': 3}
print('pipe merge', a | b)
print('unpack merge', {**a, **b})
view = ChainMap(b, {'z': 9})
b['x'] = 20
print('chainmap is live', view['x'])
```

<OutputBox title='主示例运行结果' output='groups {1: [&#39;a&#39;, &#39;c&#39;], 2: [&#39;bb&#39;, &#39;dd&#39;, &#39;ee&#39;]}\nread created key True\nget avoids factory None False\ncounts 3 0 [(&#39;a&#39;, 3), (&#39;n&#39;, 2)]\nupdate adds 4 1 8\nlayered True 9000\nwrites to first [&#39;debug&#39;, &#39;timeout&#39;] env untouched {&#39;port&#39;: 9000}\npipe merge {&#39;x&#39;: 2, &#39;y&#39;: 3}\nunpack merge {&#39;x&#39;: 2, &#39;y&#39;: 3}\nchainmap is live 20' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from collections import defaultdict, Counter, ChainMap\n\ngroups = defaultdict(list)\nfor word in (&#39;a&#39;, &#39;bb&#39;, &#39;c&#39;, &#39;dd&#39;, &#39;ee&#39;):\n    groups[len(word)].append(word)\nprint(&#39;groups&#39;, dict(groups))\nbefore = len(groups)\n_ = groups[99]\nprint(&#39;read created key&#39;, len(groups) == before + 1)\nprint(&#39;get avoids factory&#39;, groups.get(98), 98 in groups)\n\nc = Counter(&#39;banana&#39;)\nprint(&#39;counts&#39;, c[&#39;a&#39;], c[&#39;z&#39;], c.most_common(2))\nc.update([&#39;a&#39;, &#39;x&#39;])\nprint(&#39;update adds&#39;, c[&#39;a&#39;], c[&#39;x&#39;], c.total())\n\ndefaults = {&#39;debug&#39;: False, &#39;port&#39;: 8080}\nenv = {&#39;port&#39;: 9000}\nuser = {&#39;debug&#39;: True}\ncfg = ChainMap(user, env, defaults)\nprint(&#39;layered&#39;, cfg[&#39;debug&#39;], cfg[&#39;port&#39;])\ncfg[&#39;timeout&#39;] = 5\nprint(&#39;writes to first&#39;, list(user), &#39;env untouched&#39;, env)\n\na = {&#39;x&#39;: 1}\nb = {&#39;x&#39;: 2, &#39;y&#39;: 3}\nprint(&#39;pipe merge&#39;, a | b)\nprint(&#39;unpack merge&#39;, {**a, **b})\nview = ChainMap(b, {&#39;z&#39;: 9})\nb[&#39;x&#39;] = 20\nprint(&#39;chainmap is live&#39;, view[&#39;x&#39;])' :notes='["导入三个 collections 容器，分别对应分组、计数与分层", "空行，只用于分隔逻辑块，不影响执行结果。", "defaultdict(list) 让缺失键自动对应一个空列表", "按单词长度分组，首次访问某长度会自动建空列表", "转成普通 dict 打印，可见两个长度组", "记录当前键数，用于检验读操作是否插入新键", "下标读一个不存在的键 99，触发工厂并插入", "键数加一，证明读路径也会污染数据", "get 不触发 __missing__，返回 None 且不插入", "Counter 直接从可迭代对象统计字符频次", "空行，只用于分隔逻辑块，不影响执行结果。", "a 出现 3 次，缺失的 z 返回 0，most_common(2) 取前两名", "update 是累加语义，a 再加 1、并新增 x", "total() 是 3.10+ 的方法，返回所有计数之和", "默认配置层，debug 与 port 的兜底值", "空行，只用于分隔逻辑块，不影响执行结果。", "环境层覆盖 port", "用户层覆盖 debug", "ChainMap 按 user、env、defaults 顺序回退查找", "debug 命中 user，port 命中 env", "写入只作用于第一个 map，即 user 层", "user 多了 timeout，env 保持原样", "构造两个普通字典用于对比合并语义", "空行，只用于分隔逻辑块，不影响执行结果。", "3.9+ 的 | 生成新字典，右侧 x 覆盖左侧", "3.5+ 的字典解包同样生成新字典", "ChainMap 只保存 b 的引用，不复制", "修改底层 b 的 x", "活视图立即读到 20，而 | 与解包的结果仍是旧快照", "Counter 缺键返回 0；update 是累加不是覆盖；most_common(n) 按计数降序，相等按首次出现顺序", "Counter 的 + - &amp; | 是多重集运算，- 丢弃非正结果、&amp; 取 min；total() 在 3.10 加入"]' title='第 022 讲 · dict 进阶：默认字典、计数器与合并' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='layers3' title='第 022 讲 · defaultdict 与 Counter：被重写的 __missing__ 与 update' labels='defaultdict 与 Counter…|ChainMap：活视图的分层查找与写入落点|合并方式、OrderedDict 与选型|映射协议' caption='用标准库容器消灭样板代码' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## ChainMap：活视图的分层查找与写入落点

`collections.ChainMap(*maps)` 不复制任何字典，只把各层 map 的引用存在 `maps` 列表里。

查找时从左到右逐层调用 `__getitem__`，第一个命中即返回；keys / values / items 返回所有层的并集视图；写入、删除与 `clear` 只作用于 `maps[0]`，不会改到后面的层。

`new_child(m=None)` 返回一个新 `ChainMap` 并在最前面加一层（常用于请求级覆盖），`parents` 属性返回去掉第一层的链。

因为不复制，底层字典后续的任何改动都会立即被活视图看到——这是它相对 `dict | other`、`{**a, **b}` 的根本差异：后两者求值时就生成了快照，之后与源字典解耦。配置场景要分清两种需求：热更新希望改动立刻生效就用 `ChainMap`；发布给下游、要求稳定不变就用 `dict(cfg)` 或 `|` 做快照。

它能这样逐层查找，靠的正是上一讲 `collections.abc.Mapping` 那套协议。

```python
from collections import OrderedDict, Counter, defaultdict

o = OrderedDict([('a', 1), ('b', 2)])
o.move_to_end('a')
print('moved', list(o), 'popitem FIFO', o.popitem(last=False))

d = {'a': 1, 'b': 2}
print('dict eq ignores order', d == {'b': 2, 'a': 1})
print('ordered eq is strict', OrderedDict(a=1, b=2) == OrderedDict(b=2, a=1))

c1 = Counter(a=3, b=1)
c2 = Counter(a=1, b=2)
print('add', c1 + c2)
print('subtract drops nonpositive', c1 - c2)
print('intersection min', c1 & c2)

g = defaultdict(list, {'x': [1]})
frozen = dict(g)
print('frozen is plain dict', type(frozen).__name__, hasattr(frozen, 'default_factory'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='moved [&#39;b&#39;, &#39;a&#39;] popitem FIFO (&#39;b&#39;, 2)\ndict eq ignores order True\nordered eq is strict False\nadd Counter({&#39;a&#39;: 4, &#39;b&#39;: 3})\nsubtract drops nonpositive Counter({&#39;a&#39;: 2})\nintersection min Counter({&#39;a&#39;: 1, &#39;b&#39;: 1})\nfrozen is plain dict dict False' guess="true" />


## 合并方式、OrderedDict 与选型

合并字典至少有四条路，语义各不相同：`d | other`（PEP 584，3.9+）返回新 `dict` 且右侧键覆盖左侧；`{**a, **b}`（PEP 448，3.5+）同样是新字典字面量；`a.update(b)` 是原地修改 a 并返回 `None`；`ChainMap(a, b)` 不复制、只存引用。

前三条是快照，`ChainMap` 是活视图。

`collections.OrderedDict` 在 3.7 普通 `dict` 也保序之后，独特价值剩三点：`move_to_end(key, last=True)` 能把键移到首尾、`popitem(last=False)` 支持 `FIFO` 弹出、以及它的 `__eq__` 是顺序敏感的（普通 `dict` 的相等比较忽略顺序）。

因此只有需要显式重排、`FIFO` 淘汰或把顺序写进相等判断时才该用它，其余场景普通 `dict` 更轻。

选型上：分组用 `defaultdict(list)` 但记得冻结，计数用 `Counter` 但记住 `update` 累加，配置分层用 `ChainMap` 但发布时转快照，需要 `LRU` 式顺序操作才用 `OrderedDict`。

把「是否复制、是否累加、是否保序」这三个问题先答清楚，就不会用错容器。

`defaultdict` 是 `dict` 子类，重写了 `__missing__(key)`：当 `d[key]` 找不到键时，若 `default_factory` 不为 `None` 就调用它生成值、把 `(key, value)` 真正插入字典再返回。

因此工厂只在下标访问时触发，`get()` 与 `in` 不会调用它，这正是读路径也污染数据的来源，工程上读完用 `dict(d)` 转成普通 `dict` 或把 `default_factory` 置 `None` 来冻结。

`Counter` 同样继承 `dict`，把 `__missing__` 改成返回 0，于是缺键计数天然为 0；它的 `update` 被重写为累加（`dict.update` 是覆盖），`most_common` 按计数降序、相等时按首次出现顺序，`+ - & |` 做多重集运算，`total()` 在 3.10 加入。

`ChainMap` 不复制任何字典，只把多个 map 的引用存在 `maps` 列表里，查找从左到右逐层调 `__getitem__`、第一个命中即返回，写入与删除只作用于 `maps[0]`，因此底层字典后续变化会立即反映，这与 `|` / 解包的快照语义相反。


## 配置中心：ChainMap 分层、快照发布与 Counter 命中统计

一个服务要合并默认配置、环境变量与用户覆盖，还要在运行时热更新默认层，并统计各配置项被读取的次数。用 `ChainMap` 把用户层、环境层、默认层依次叠起来做分层查找：读时按层回退、写只落用户层、热更新 `defaults` 后所有读取立即看到新值。

发布配置给下游时用 `dict(cfg)` 生成快照，避免下游持有活视图被后续改动影响；再用 `Counter` 累计每次命中的层名，验证哪一层承担了大多数读取。

最后用 `defaultdict(list)` 收集变更日志，并在收尾用 `dict()` 冻结，防止收尾阶段的只读判断意外插入空记录。

重点是把活视图、快照、累加计数三种语义分清，而不是所有地方都用同一个 `dict`。

```python
from collections import ChainMap, Counter, defaultdict

defaults = {'port': 8080, 'debug': False, 'retries': 3}
env = {'port': 9000}
user = {'debug': True}
cfg = ChainMap(user, env, defaults)
hits = Counter()
changes = defaultdict(list)

def layer_name(layer):
    if layer is user: return 'user'
    if layer is env: return 'env'
    return 'defaults'

def read(key, tag):
    for layer in cfg.maps:
        if key in layer:
            hits[layer_name(layer)] += 1
            changes[key].append((tag, layer[key]))
            return layer[key]
    raise KeyError(key)

print('port', read('port', 'boot'))
print('debug', read('debug', 'boot'))
defaults['retries'] = 5
print('retries after hot update', read('retries', 'hot'))
snapshot = dict(cfg)
print('snapshot debug', snapshot['debug'])
print('hits', dict(hits))
print('log frozen', type(dict(changes)).__name__)
```

<Callout type="idea" title='落地提示' text='配置分层用 ChainMap 组合默认配置、环境配置与用户覆盖；词频统计用 Counter 而不是手写自增' />


## 容器落地的排错与练习

<Exercise title='基础：用 defaultdict 分组并冻结结果' task='把一批单词按长度分组，验证下标读不存在的键会插入空列表、而 get 不会；最后用 dict() 冻结成普通 dict。' solution='from collections import defaultdict\ng = defaultdict(list)\nfor w in (&#39;a&#39;, &#39;bb&#39;, &#39;cc&#39;, &#39;d&#39;):\n    g[len(w)].append(w)\nprint(&#39;groups&#39;, dict(g))\n_ = g[9]\nprint(&#39;subscript inserted&#39;, 9 in g)\ng2 = defaultdict(list)\nprint(&#39;get safe&#39;, g2.get(9), 9 in g2)\nfrozen = dict(g)\nprint(&#39;frozen type&#39;, type(frozen).__name__, hasattr(frozen, &#39;default_factory&#39;))' explain='defaultdict 的工厂只在下标访问触发，get 与 in 不触发；dict(dd) 生成普通 dict 快照，之后不再有自动插入行为，适合把结果交给下游。' />

<Exercise title='进阶：用 ChainMap 实现可热更新的分层配置并给快照' task='构造默认层、环境层、用户层三级 ChainMap，验证查找回退与写入只落第一层；修改默认层后读到新值，再用 dict() 生成不受后续改动影响的快照。' solution='from collections import ChainMap\ndefaults = {&#39;a&#39;: 1, &#39;b&#39;: 2}\nenv = {&#39;b&#39;: 20}\nuser = {}\ncfg = ChainMap(user, env, defaults)\nprint(&#39;lookup a&#39;, cfg[&#39;a&#39;], &#39;lookup b&#39;, cfg[&#39;b&#39;])\ncfg[&#39;c&#39;] = 3\nprint(&#39;write lands in user&#39;, user, &#39;env&#39;, env)\ndefaults[&#39;a&#39;] = 100\nprint(&#39;live update&#39;, cfg[&#39;a&#39;])\nsnap = dict(cfg)\ndefaults[&#39;a&#39;] = 999\nprint(&#39;snapshot stable&#39;, snap[&#39;a&#39;], &#39;live now&#39;, cfg[&#39;a&#39;])' explain='ChainMap 不复制、按 maps 顺序回退查找，写入只改第一层；底层 dict 变化会被活视图看到，而 dict(cfg) 是求值时的快照，之后与底层解耦。配置发布用快照，热更新用活视图。' />

<Quiz no='022-1' q='关于 defaultdict，下列哪项准确？' :options='["get() 也会触发工厂", "下标访问不存在的键会调用工厂并把结果插入字典", "default_factory 默认是 list", "它不能转成普通 dict"]' answer="1" explain='defaultdict 重写 __missing__，只在 d[key] 找不到时触发工厂并真正插入；get() 与 in 不调用 __missing__，default_factory 默认是 None，dict(d) 可冻结成普通 dict。' />

<Quiz no='022-2' q='Counter(&#39;aab&#39;).update([&#39;a&#39;]) 之后 c[&#39;a&#39;] 是？' :options='["1", "2", "3", "抛 KeyError"]' answer="2" explain='Counter.update 是累加语义而非覆盖：初始 a 为 2，update 加 1 得 3。要覆盖应重新构造 Counter 或先 clear()。' />

<Quiz no='022-3' q='ChainMap(a, b) 与 a | b 的关键区别是？' :options='["两者都复制数据", "ChainMap 是活视图不复制且写入只落第一层，| 返回快照新 dict", "ChainMap 要求 3.9+", "| 写入会修改 a"]' answer="1" explain='PEP 584 的 | 在 3.9+ 返回新字典快照；ChainMap(3.3+) 只保存各 map 引用，底层变化会反映，赋值只作用于 maps[0]。' />

<KnowledgeCard :points='["defaultdict 重写 __missing__：下标缺键触发工厂并插入，get / in 不触发；读完用 dict(d) 冻结", "Counter 缺键返回 0；update 是累加不是覆盖；most_common(n) 按计数降序，相等按首次出现顺序", "Counter 的 + - &amp; | 是多重集运算，- 丢弃非正结果、&amp; 取 min；total() 在 3.10 加入", "ChainMap 不复制、按 maps 顺序回退查找，写入只落第一层；它是活视图，底层变化会反映", "dict | other (3.9+) 与 {**a, **b} (3.5+) 是快照式复制；ChainMap 是视图式组合", "OrderedDict 的独特价值是 move_to_end、popitem(last=False) 与顺序敏感相等；3.7 起普通 dict 已保序"]' :pitfalls='["defaultdict 仅仅读一个不存在的键，字典就被改了", "用 Counter.update 想覆盖计数，结果数值翻倍", "以为 ChainMap 合并出了一份独立配置", "defaultdict 在嵌套层级深时会悄悄创建不存在的键，读路径也可能污染数据"]' summary='collections 里的容器本质是把常见循环模式固化成 C 级实现，既短又快，还少一类边界 bug' />

1. defaultdict 重写 __missing__：下标缺键触发工厂并插入，get / in 不触发；读完用 dict(d) 冻结

2. Counter 缺键返回 0；update 是累加不是覆盖；most_common(n) 按计数降序，相等按首次出现顺序

3. Counter 的 + - & | 是多重集运算，- 丢弃非正结果、& 取 min；total() 在 3.10 加入

[下一讲：set / frozenset：哈希、集合运算与去重](/containers/set)

<Predict no='022-4' q='c = Counter(&#39;banana&#39;); c.update([&#39;a&#39;]); print(c[&#39;a&#39;], c.most_common(1)) 输出什么？' :options='["3 [(&#39;a&#39;, 3)]", "4 [(&#39;a&#39;, 4)]", "4 [(&#39;a&#39;, 4), (&#39;n&#39;, 2)]"]' answer='1' output='4 [(&#39;a&#39;, 4)]' explain='&#39;banana&#39; 里 a 出现 3 次，Counter.update 累加而非覆盖，加 1 得 4；most_common(1) 只返回计数最高的 1 项，故为 [(&#39;a&#39;, 4)]。传 None 才返回全部。' />

<FillBlank no='022-5' tpl='from collections  ___ defaultdict, Counter, ChainMap' :answers='["import"]' hint='回想本讲关于 defaultdict 工厂 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 defaultdict 与 Counter：被重写的 __missing__ 与 update 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/022-dict-advanced.py`

```bash
python3 examples/lessons/022-dict-advanced.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/022-dict-advanced.py) · [全部示例代码索引](/examples/)
