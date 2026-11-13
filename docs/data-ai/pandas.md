---
title: 第 094 讲 · Pandas 清洗、分组、透视与时间序列
description: 把脏数据变成可分析的数据集
---

<StageHeader stage='L9 · 数据与 AI' level='★★★☆☆' time='45 分钟' goal='把脏数据变成可分析的数据集' prereq='第 093 讲 · NumPy 向量化、广播与内存布局' />

# 第 094 讲 · Pandas 清洗、分组、透视与时间序列

上一讲把一列数字算得飞快，可导出的记录不止一列：时间、地区、状态码混着，有的空着，同一个用户重复几行。直接求平均，结果会悄悄偏掉。本讲把带毛边的行收拢成能对齐、能分组的表，从『算得快』走到『摆得整齐』。

先定好 Series 与 DataFrame 的索引——不少 NaN 并非数据缺失，而是标签没对上；接着处理缺失值与重复，再用 groupby、agg、transform 一次成型；往后是 merge 与 join、透视与重采样。需要上一讲的 ndarray、布尔索引和字典基础。这一讲结束，你能把乱表收成可分析的 DataFrame，按维度出汇总。


## 两列相加凭空多出 NaN 的工单

两份销售报表合并后对不上账：A 表按北京、上海、广州排列，B 表按上海、深圳、北京排列，同事直接把两列数值相加，结果北京变成上海的、广州被配到深圳，还凭空多出 NaN。

另一个工单更隐蔽：分析师想用一行链式索引把华东地区的价格清零，运行没报错，价格却一点没动，只在终端留下一行 `SettingWithCopyWarning`。

还有人把整段清洗写成 iterrows 循环逐行赋值，十万行跑了四分钟。这些故障都不是『数据脏』，而是没吃透 Pandas 的心智模型：Series 与 DataFrame 的一切运算都按标签对齐，而不是按位置对齐；链式索引可能返回一个临时副本，赋值落在副本上就静默丢失。

把索引、缺失策略、分组聚合与写回时机定清楚，比事后对账省事得多。

<Callout type="warn" title='先看一个真实会出错的写法' text='对布尔索引结果赋值不生效还伴随 SettingWithCopyWarning：df[df.region == &#39;华东&#39;][&#39;price&#39;] = 0 里的第一层索引可能返回临时副本，赋值落到副本上' />

<Callout type="tip" title='核心心智模型' text='Series 与 DataFrame 的算术运算先按 index 做并集对齐，再逐标签计算；某个标签只在一边出现，结果里该位置就是 NaN，而不是『跳过』或『补 0』。这与 NumPy 严格按位置逐元素运算完全相反：两个长度相同但顺序不同的 Series 相加，位置对不上不会报错，而是按标签求和。举' />


## 标签对齐：多数 NaN 不是缺失而是索引没对上

Series 与 DataFrame 的算术运算先按 index 做并集对齐，再逐标签计算；某个标签只在一边出现，结果里该位置就是 NaN，而不是『跳过』或『补 0』。这与 NumPy 严格按位置逐元素运算完全相反：两个长度相同但顺序不同的 Series 相加，位置对不上不会报错，而是按标签求和。

举个例子，构造两个 `Series`：s1 的索引是北京、上海、广州，值 10、20、30；s2 的索引是上海、深圳、北京，值 5、8、1。两者相加得到四个标签，其中广州、深圳为 NaN，北京为 11、上海为 25。

要『某边缺失按 0 补齐再相加』，必须用 `s1.add(s2, fill_value=0)`，这才得到广州 30、深圳 8；

`fill_value` 只补一边缺失，两边都缺仍为 NaN。`reindex` 按给定标签重排并引入缺失，`align` 返回对齐后的两份副本，对称于运算前的隐式对齐。DataFrame 之间运算会同时对行索引与列索引做对齐，join 的 how 参数（left、right、inner、outer）决定并集还是交集。

排查诡异 NaN 的第一步永远是打印两边的 `.index` 与 `.columns`，看是不是顺序或标签不一致，而不是急着 `df.fillna(0)`——后者会把『没对齐』的真实问题掩盖成一个看似干净的错误结果。

```python
def align_add(a, b, fill=None):
    keys = list(dict.fromkeys(list(a) + list(b)))
    out = {}
    for k in keys:
        if k in a and k in b:
            out[k] = a[k] + b[k]
        elif fill is None:
            out[k] = None
        else:
            out[k] = a.get(k, fill) + b.get(k, fill)
    return out

s1 = {'北京': 10, '上海': 20, '广州': 30}
s2 = {'上海': 5, '深圳': 8, '北京': 1}
print('add', align_add(s1, s2))
print('fill0', align_add(s1, s2, fill=0))
```

<OutputBox title='主示例运行结果' output='add {&#39;北京&#39;: 11, &#39;上海&#39;: 25, &#39;广州&#39;: None, &#39;深圳&#39;: None}\nfill0 {&#39;北京&#39;: 11, &#39;上海&#39;: 25, &#39;广州&#39;: 30, &#39;深圳&#39;: 8}' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def align_add(a, b, fill=None):\n    keys = list(dict.fromkeys(list(a) + list(b)))\n    out = {}\n    for k in keys:\n        if k in a and k in b:\n            out[k] = a[k] + b[k]\n        elif fill is None:\n            out[k] = None\n        else:\n            out[k] = a.get(k, fill) + b.get(k, fill)\n    return out\n\ns1 = {&#39;北京&#39;: 10, &#39;上海&#39;: 20, &#39;广州&#39;: 30}\ns2 = {&#39;上海&#39;: 5, &#39;深圳&#39;: 8, &#39;北京&#39;: 1}\nprint(&#39;add&#39;, align_add(s1, s2))\nprint(&#39;fill0&#39;, align_add(s1, s2, fill=0))' :notes='["用字典模拟两个 Series 按标签相加，fill 对应 Pandas 的 fill_value", "取两边标签的并集，dict.fromkeys 去重且保留首次出现顺序", "out 存放逐标签的运算结果", "遍历并集里的每个标签，模拟按标签对齐而非按位置对齐", "标签两边都存在：直接相加，对应 s1+s2", "标签只在单边且未给 fill_value：结果记为 None，即 NaN", "把单边缺失写成 None，对应 Pandas 产生的 NaN", "给了 fill_value：缺失的一边按填充值补齐", "两边都用 get(缺省 fill) 取值再相加，广州补 0、深圳补 0", "返回对齐后的字典，键顺序由并集决定", "s1 索引为 北京/上海/广州，顺序与 s2 不同", "s2 索引为 上海/深圳/北京，故意打乱顺序制造错位", "不带 fill_value，等价于 s1 + s2，单边标签变 None", "带 fill_value=0，等价于 s1.add(s2, fill_value=0)", "打印带填充值的结果，验证广州得 30、深圳得 8"]' title='第 094 讲 · Pandas 清洗、分组、透视与时间序列' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**对齐、分组、合并的核心 API 对照**

| API | 对齐/操作依据 | 返回形状 | 典型用途 |
| --- | --- | --- | --- |
| s1 + s2 | 按 index 标签并集 | 长度为并集，单边为 NaN | 两列求和 |
| s1.add(s2, fill_value=0) | 按标签并集并补值 | 同上但缺边补 0 | 缺失按 0 参与的求和 |
| groupby().agg('mean') | 分组键 | 每组一个标量 | 出分组汇总表 |
| groupby().transform('mean') | 分组键 | 与原行等长 | 组内标准化、加回原表 |
| merge(validate=...) | 指定键列 | 按 how 决定行数 | 校验连接基数防膨胀 |

<ConceptDiagram type='compare2' title='第 094 讲 · 标签对齐：NaN 大多不是缺失，而是索引没对上' labels='标签对齐：NaN 大多不是缺失，而是索引没对|groupby / agg / transf|合并、透视、时间序列与内存' caption='把脏数据变成可分析的数据集' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## groupby、agg 与 transform 的三种返回形状

groupby 的本质是 split-apply-combine：先按 key 把行拆成若干组，对每组应用函数，再把结果合并。

agg（或 aggregate）对每组返回一个标量，结果索引是分组 key，长度等于组数，例如 `df.groupby('region').price.mean()` 得到每个地区一个均值；

可以一次传多个聚合 `['sum','mean','count']`，或用字典对不同列指定不同函数。

transform 则必须返回与输入等长、且索引与原行一一对应的结果，最典型的用法是 `df.groupby('region')['price'].transform('mean')` 得到『每行所属组的均值』，从而写 `df['dev']=df['price']-df.groupby('region')['price'].transform('mean')` 做组内标准化，这是 agg 做不到的。

apply 最灵活也最慢，返回形状由函数决定；过滤用 filter 保留满足条件的整组。还要注意分组键里的 NaN 默认被丢弃（`dropna=True`），分类键用 `observed` 参数控制是否列出未出现的类别。

性能上，逐行 iterrows 会把每行构造成一个 Series、走 Python 层循环，十万行以上通常慢一个数量级；

应优先用向量化的列运算、`.loc` 批量赋值，或 `groupby().transform` 一次成型。

```python
from collections import defaultdict
rows = [('A', 10), ('A', 20), ('B', 5), ('B', 7), ('B', 9)]
g = defaultdict(list)
for k, v in rows: g[k].append(v)
means = {k: sum(v) / len(v) for k, v in g.items()}
print('agg', means)
print('transform', [v - means[k] for k, v in rows])
print('lengths', len(means), len(rows))
```

<OutputBox title='对照写法：先自己猜，再点开' output='agg {&#39;A&#39;: 15.0, &#39;B&#39;: 7.0}\ntransform [-5.0, 5.0, -2.0, 0.0, 2.0]\nlengths 2 5' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "def align_add(a, b, fill=None):\n    keys = list(dict.fromkeys(list(a) + list(b)))\n    out = {}\n    for k in keys:\n        if k in a and k in b:\n            out[k] = a[k] + b[k]\n        elif fill is None:\n            out[k] = None\n        else:\n            out[k] = a.get(k, fill) + b.get(k, fill)\n    return out\n\ns1 = {&#39;北京&#39;: 10, &#39;上海&#39;: 20, &#39;广州&#39;: 30}\ns2 = {&#39;上海&#39;: 5, &#39;深圳&#39;: 8, &#39;北京&#39;: 1}\nprint(&#39;add&#39;, align_add(s1, s2))\nprint(&#39;fill0&#39;, align_add(s1, s2, fill=0))", "note": "标签对齐：NaN 大多不是缺失，而是索引没对上"}, {"label": "对照 / 进阶", "code": "from collections import defaultdict\nrows = [(&#39;A&#39;, 10), (&#39;A&#39;, 20), (&#39;B&#39;, 5), (&#39;B&#39;, 7), (&#39;B&#39;, 9)]\ng = defaultdict(list)\nfor k, v in rows: g[k].append(v)\nmeans = {k: sum(v) / len(v) for k, v in g.items()}\nprint(&#39;agg&#39;, means)\nprint(&#39;transform&#39;, [v - means[k] for k, v in rows])\nprint(&#39;lengths&#39;, len(means), len(rows))", "note": "groupby / agg / transform：三种返回形状要分清"}]' title='两种写法对照' note='差异集中在 Series 与 DataFrame 索引；先看输出，再找背后的规则。' />


## merge 行数膨胀与 validate 防线

merge 按一列或多列的键做关系型连接，`pd.merge(a,b,on='id',how='left',validate='many_to_one')` 里的 `validate` 能在运行期检查连接基数，提前发现『本该一对一却膨胀成多行』的隐性错误；

`indicator=True` 会加一列 `_merge` 标明每行来自左、右还是两边，便于核对。join 默认按索引连接，concat 按轴堆叠，三者别混用。

透视用 `pivot_table(index=...,columns=...,values=...,aggfunc='mean')`，它比 `pivot` 多了聚合步骤，因此能处理重复的 (index, columns) 组合；

`melt` 是它的逆操作，把宽表拉成长表。时间序列的关键是先把列转成 `datetime64[ns]` 再 set_index，之后 `resample('W')` 按周、`resample('M')` 按月重采样，配合 `.mean()`、`.sum()` 聚合；

`rolling(7).mean()` 做滑动窗口；

缺的日期用 `asfreq` 补齐。采样规则里 'M' 是月末、'MS' 是月初，混用会让对齐差一整期；较新的 pandas 版本把月末别名写成 'ME'、'M' 会告警，迁移时要留意。

`memory_usage(deep=True)` 逐列看真实占用，比 `df.info()` 的估算更准；

内存优化上，低基数字符串列应转成 `category`（重复值只存一份类别表加整数编码），数值列从 int64/float64 向下转成 int32/float32 或用 nullable 的 `Int32` 支持缺失，布尔列用 bool。

大表则可分块 `read_csv(chunksize=...)` 或改用 Polars。

```python
import sys, array
n = 1000
cells = ['region-' + str(i % 4) for i in range(n)]
str_bytes = sum(sys.getsizeof(c) for c in cells)
codes = array.array('i', [i % 4 for i in range(n)])
cat_raw = codes.buffer_info()[1] * codes.itemsize
cat_bytes = cat_raw + sum(sys.getsizeof('region-' + str(k)) for k in range(4))
print('distinct str objects', len({id(c) for c in cells}))
print('object approx bytes', str_bytes)
print('codes raw bytes', cat_raw, 'itemsize', codes.itemsize)
print('category total approx', cat_bytes, 'ratio', round(str_bytes / cat_bytes, 1))
```

<OutputBox title='原理验证' output='distinct str objects 1000\nobject approx bytes 49000\ncodes raw bytes 4000 itemsize 4\ncategory total approx 4196 ratio 11.7' />

**诡异 NaN 的成因与定位**

| 现象 | 真实根因 | 定位手段 |
| --- | --- | --- |
| 两列相加多出 NaN | index 标签不对齐而非数据缺失 | 打印两边 .index 求差集 |
| merge 后行数暴涨 | 键非唯一，many_to_many 连接 | 设 validate 与 indicator=True |
| resample 结果错位一期 | 把 'M' 月末与 'MS' 月初规则混用 | 打印重采样后的 index |
| 链式赋值不生效 | 对临时副本写入 | 改用 .loc 一次定位 |


## 对齐按标签而非位置：SettingWithCopy 从何而来

Pandas 建立在『带标签的数组』之上：每个 Series 或 DataFrame 都带一个 Index 对象，运算前先对参与双方的 index 求并集并重排，这个对齐步骤发生在数值计算之前，是它区别于 NumPy 纯位置语义的根本设计。

底层数据按列存在 BlockManager（新版本逐步迁向 Arrow 后端）里，同 dtype 的列尽量合成连续的块，因此列式向量运算能落到 C 层；而 iterrows 会把每一行额外封装成一个 Series，代价随行数线性放大且产生大量临时对象。

groupby 先对分组键做哈希分解得到每组的行位置索引，agg 把每组约简成标量、transform 则把组结果按行位置广播回原长度，这解释了二者形状差异。

链式索引 `df[cond].col = v` 之所以危险，是因为 `df[cond]` 可能返回视图也可能返回副本，取决于底层块是否连续，解释器无法保证；

`loc[cond, 'col'] = v` 把定位与写入合成一次调用，才绕过这个不确定性。

理解『标签对齐、列式存储、索引可能返回副本』这三层，绝大多数诡异 NaN 与静默失败都能推导出来。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 对布尔索引结果赋值不生效还伴随 SettingWithCopyWarning | df[df.region == '华东']['price'] = 0 里的第一层索引可能返回临时副本，赋值落到副本上 | 合并成一次 .loc：df.loc[df.region == '华东', 'price'] = 0；需要子集先 .copy() |
| 两列相加凭空多出 NaN 与错配 | 两边 index 顺序或标签不同，运算按标签对齐，单边标签补 NaN | 先打印 .index 核对；确实要按位置相加就用 .to_numpy() 或 reset_index(drop=True) |
| merge 后行数比左表还多 | 连接键在右表不唯一，many_to_many 连接让行膨胀 | pd.merge(..., validate='many_to_one', indicator=True) 在膨胀时直接报错并标出来源 |

<Callout type="warn" title='本讲最容易踩的坑' text='对布尔索引结果赋值不生效还伴随 SettingWithCopyWarning：df[df.region == &#39;华东&#39;][&#39;price&#39;] = 0 里的第一层索引可能返回临时副本，赋值落到副本上' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：对布尔索引结果赋值不生效还伴随 Settin", "body": "df[df.region == &#39;华东&#39;][&#39;price&#39;] = 0 里的第一层索引可能返回临时副本，赋值落到副本上", "tip": "合并成一次 .loc：df.loc[df.region == &#39;华东&#39;, &#39;price&#39;] = 0；需要子集先 .copy()"}, {"title": "第 2 步：两列相加凭空多出 NaN 与错配", "body": "两边 index 顺序或标签不同，运算按标签对齐，单边标签补 NaN", "tip": "先打印 .index 核对；确实要按位置相加就用 .to_numpy() 或 reset_index(drop=True)"}, {"title": "第 3 步：merge 后行数比左表还多", "body": "连接键在右表不唯一，many_to_many 连接让行膨胀", "tip": "pd.merge(..., validate=&#39;many_to_one&#39;, indicator=True) 在膨胀时直接报错并标出来源"}]' />


## 日报清洗：先定索引与 schema，再做聚合

某电商每天收到一份分区销售明细，字段含 order_id、region、amount、ts，常见问题是地区名前后不一致、时间列是字符串、同一订单重复上报。

可靠的清洗顺序是：先把 ts 转成 datetime 并设为索引，地区列规范后转 `category`，按 order_id 去重，再用一次 groupby 出『各地区日销售额』，最后用 transform 给每行打上『相对所属区域均值的偏差』标签。

下面用纯标准库模拟这条管道的关键步骤，重点看对齐、去重、分组聚合与组内广播如何一次成型，以及每步都保留可核对的记录数。

真实项目把字典换成 DataFrame、groups 换成 groupby，其余结构不变，记得用 `memory_usage(deep=True)` 复核 category 的收益。

```python
from collections import defaultdict
from datetime import datetime

raw = [
    ('o1', '华东 ', '2024-03-01', 120),
    ('o2', '华北', '2024-03-01', 80),
    ('o1', '华东 ', '2024-03-01', 120),
    ('o3', '华东', '2024-03-02', 200),
]

def clean(rows):
    seen, out = set(), []
    for oid, region, day, amount in rows:
        key = oid
        if key in seen: continue
        seen.add(key)
        out.append((oid, region.strip(), datetime.strptime(day, '%Y-%m-%d').date(), amount))
    return out

def report(rows):
    g = defaultdict(int)
    for _, region, _, amount in rows: g[region] += amount
    means = {r: g[r] / max(1, sum(1 for x in rows if x[1] == r)) for r in g}
    dev = [(oid, amount - means[region]) for oid, region, _, amount in rows]
    return dict(g), len(rows), dev

cleaned = clean(raw)
totals, n, dev = report(cleaned)
print('rows after dedup', n, 'totals', totals)
print('deviation', [(o, round(d, 1)) for o, d in dev])
```

<Callout type="idea" title='落地提示' text='先定 schema 与索引，再做缺失策略，分组聚合一次成型；大表用 category / 分块 / Polars' />

**类型与内存优化对照**

| 列类型 | 存储方式 | 优化手段 | 注意 |
| --- | --- | --- | --- |
| 低基数字符串 | 每值一个 PyObject | 转 category 存整数编码 | 类别数远小于行数才划算 |
| int64 数值 | 8 字节/值 | 转 int32 / Int32 | Int32 可承载缺失 |
| float64 数值 | 8 字节/值 | 转 float32 | 精度下降需评估 |
| object 布尔 | 指针 + 对象 | 转 bool 或 nullable boolean | 含缺失时用 BooleanDtype |

<CheckList id='P094b' title='上线前自检' :items='["能复现并解释「对布尔索引结果赋值不生效还伴随 SettingWithCop」", "能复现并解释「两列相加凭空多出 NaN 与错配」", "能复现并解释「merge 后行数比左表还多」", "能用一条命令验证 Series 与 DataFrame 索引", "关键路径有自动化测试与失败分支"]' />


## 练习与速记：把对齐规则背下来

<Exercise title='基础：模拟带 fill_value 的标签对齐' task='实现 align_add 的姊妹函数，返回「两边都存在」「只在左边」「只在右边」三类标签各自的和，并解释为什么 Pandas 对只在单边的标签默认给 NaN。' solution='def align_report(a, b):\n    both = {k: a[k] + b[k] for k in a if k in b}\n    only_a = {k: a[k] for k in a if k not in b}\n    only_b = {k: b[k] for k in b if k not in a}\n    return both, only_a, only_b\n\na = {&#39;北京&#39;: 10, &#39;广州&#39;: 30}\nb = {&#39;北京&#39;: 1, &#39;深圳&#39;: 8}\nprint(align_report(a, b))' explain='运算先取标签并集，只在单边的标签缺一个操作数，无法给出确定的和，Pandas 用 NaN 表示「未定义」而不是擅自用 0 顶替；要补 0 得显式 add(fill_value=0)。' />

<Exercise title='进阶：用 transform 思路做组内标准化' task='给定 (分组, 值) 列表，写一份代码同时输出「每组均值」与「每行减去所属组均值」两个结果，并说明为什么后者不能用 agg 的返回值直接相减。' solution='from collections import defaultdict\nrows = [(&#39;A&#39;, 10), (&#39;A&#39;, 20), (&#39;B&#39;, 5), (&#39;B&#39;, 7), (&#39;B&#39;, 9)]\ng = defaultdict(list)\nfor k, v in rows: g[k].append(v)\nmeans = {k: sum(v)/len(v) for k, v in g.items()}\nprint(&#39;agg&#39;, means)\nprint(&#39;transform&#39;, [v - means[k] for k, v in rows])' explain='agg 结果按组索引、长度等于组数，与原行无法逐位置对齐；transform 把组结果按行位置广播回原长度，才能做逐行减法。这正是 groupby().transform 与 .agg 的形状区别。' />

<Quiz no='094-1' q='两个长度相同、index 顺序不同的 Series 相加会怎样？' :options='["按标签对齐后相加，只在单边出现的标签得到 NaN", "按位置逐元素相加，顺序不同导致错位但不报错", "直接抛 ValueError 要求索引一致", "自动排序后按位置相加"]' answer="0" explain='Pandas 算术先对 index 求并集并按标签对齐，标签只在一边出现时结果为 NaN。它不会按位置相加，也不会因顺序不同而报错——这正是诡异 NaN 的主要来源。' />

<Quiz no='094-2' q='df[df.x &gt; 0][&#39;y&#39;] = 1 有时不生效，稳妥写法是？' :options='["df.loc[df.x &gt; 0, &#39;y&#39;] = 1", "先 df[df.x &gt; 0].copy() 再赋值", "在末尾加 inplace=True", "改用 df.y.where(...)"]' answer="0" explain='链式索引的第一层可能返回副本，赋值落在副本上会静默丢失。.loc[cond, &#39;y&#39;] = 1 把定位与写入合成一次调用，绕过视图/副本的不确定性。' />

<Quiz no='094-3' q='想把每行数值减去它所在组的均值，应该用？' :options='["groupby(key).transform(&#39;mean&#39;) 后再做减法", "groupby(key).agg(&#39;mean&#39;) 后直接相减", "groupby(key).apply(lambda g: g - g.mean()) 一定最快", "rolling(3).mean()"]' answer="0" explain='transform 返回与原行等长、索引对齐的结果，可逐行做减法；agg 只返回每组一个标量、长度是组数，无法与原行逐位置相减。apply 灵活但通常更慢。' />

<KnowledgeCard :points='["Series/DataFrame 运算先按 index 并集对齐再算，标签只在一边就出 NaN；与 NumPy 的按位置相反", "要缺失按 0 补齐用 s1.add(s2, fill_value=0)；fill_value 只补一边，两边都缺仍为 NaN", "agg 每组返回标量、长度等于组数；transform 返回等长结果，可做组内标准化；apply 最灵活也最慢", "链式索引 df[cond].col = v 可能落在副本上静默失败，改用 loc[cond, &#39;col&#39;] = v 一次定位写入", "merge 的 validate 与 indicator 检查连接基数与来源；pivot_table 带聚合、能处理重复组合", "时间序列先转 datetime64[ns] 再 set_index；&#39;M&#39; 月末、&#39;MS&#39; 月初（新版用 &#39;ME&#39;）；category 与 memory_usage(deep=True) 省内存"]' :pitfalls='["对布尔索引结果赋值不生效还伴随 SettingWithCopyWarning", "两列相加凭空多出 NaN 与错配", "merge 后行数比左表还多", "用 inplace 链式操作、或在循环里逐行 iterrows，既慢又容易产生 SettingWithCopy 警告下的静默错误"]' summary='Pandas 的核心心智模型是「带标签的对齐运算」：很多诡异的 NaN 都来自索引没对齐而不是数据缺失' />

1. Series/DataFrame 运算先按 index 并集对齐再算，标签只在一边就出 NaN；与 NumPy 的按位置相反

2. 要缺失按 0 补齐用 s1.add(s2, fill_value=0)；fill_value 只补一边，两边都缺仍为 NaN

3. agg 每组返回标量、长度等于组数；transform 返回等长结果，可做组内标准化；apply 最灵活也最慢

[下一讲：可视化：Matplotlib / Seaborn / Plotly 与图表选型](/data-ai/visualization)

<Predict no='094-4' q='前面 code 里 align_add(s1, s2, fill=0) 对「广州」这一标签返回什么？' :options='["30", "None", "0"]' answer='0' output='30' explain='广州只在 s1 有值 30，s2 缺失。fill=0 时走 else 分支，a.get(&#39;广州&#39;, 0) 得 30、b.get(&#39;广州&#39;, 0) 得 0，相加为 30，对应 add(fill_value=0) 用 0 补齐单边缺失。' />

<FillBlank no='094-5' tpl='___ align_add(a, b, fill=None):' :answers='["def"]' hint='回想本讲关于 Series 与 DataFrame 索引 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 标签对齐：NaN 大多不是缺失，而是索引没对上 的落点。' />
