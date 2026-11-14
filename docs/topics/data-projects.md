---
title: 数据分析实战：Jupyter 到报告导出
description: 把 Notebook 流水线、Pandas 透视、Scipy 检验与报告导出串成可复核的分析闭环
---

# 数据分析实战：Jupyter 到报告导出

站点正文把标签对齐、`groupby` 的三种返回形状、统计里的分布与检验、以及图表选型分别放在第 093 到 096 讲里讲过，知识点是拆开的。可一旦手里是一份真实的科室费用表，或逐日疫情与一线城市房价的 CSV，问题会一起冒出来：空着的费用格是没上报还是零元、两张表按哪个键合并才不会让行数翻倍、门诊和住院的次均费用能不能放进同一张透视表、图画给谁看、导出的报告别人怎么复核。这一篇把这些分散的动作收成一条从 Notebook 到导出结果的流水线，代码都自带内联的小数据，装好依赖就能整段跑；也会给出纯标准库 `csv` 的等价写法，说明没有第三方库时同一套口径怎么落地。

<Callout type='tip' title='空着的格子不等于零' text='CSV 里空费用格读入后是缺失值，直接填 0 会同时改掉分子与分母，次均费用随之偏低' />

## 装好依赖与固定随机种子

这条流水线用到 `pandas`、`numpy`、`scipy`、`seaborn`、`matplotlib`，报告转成 PDF 时再按需追加转换工具。一次性装齐：

```bash
python3 -m pip install pandas numpy scipy seaborn matplotlib
# 需要把 Notebook 或 HTML 转成 PDF 时再装其中一种
python3 -m pip install nbconvert weasyprint
```

装完在 Notebook 第一个单元格里打印版本，写进报告末尾，读者才知道结果是在哪套库上跑出来的。

```python
import pandas as pd, numpy as np, scipy, matplotlib
print('pandas', pd.__version__, 'numpy', np.__version__,
      'scipy', scipy.__version__, 'matplotlib', matplotlib.__version__)
```

### 内核、执行顺序与 Restart & Run All

Notebook 的状态藏在内核里：某个单元格被跳过或重复执行过，变量就停留在中间态，从上到下肉眼看到的顺序和内存里的顺序未必一致。判断一份分析能不能复现，最省事的办法是点 `Kernel → Restart & Run All`，让内核从空状态按单元格顺序重跑一遍，再比对关键数字有没有变。常用的魔术命令里，`%matplotlib inline` 让图嵌进页面，`%run other.py` 复用另一份脚本，`%timeit` 量一段运算的耗时；它们属于交互式外壳，导出成 `.py` 脚本前要替换成对应的普通调用。

### 数据快照、种子与版本锁定

可复现至少锁四样：原始数据、随机种子、依赖版本、时间口径。原始 CSV 读入后立刻记录 `df.shape`、列名和文件哈希，报告里写明数据截止到哪一天；抽样或检验用到随机数时，用 `np.random.default_rng(7)` 这样的具名生成器而不是全局 `np.random.seed`，避免别处的代码悄悄改掉序列；依赖用 `pip freeze > requirements.txt` 固化。相对路径按 Notebook 所在目录解析，用 `pathlib.Path` 拼，换台机器才不会因为工作目录不同而读不到文件。

## 用 read_csv 读入并定位缺失值

读入这一步就要定列类型，别等算完再回头查。`read_csv` 的 `dtype` 显式声明数值列，`parse_dates` 把日期列直接转成时间类型，能挡掉大量后续的类型错误；字符串列统一 `str.strip()` 去掉首尾空格，否则「内科」和「内科 」会被当成两个科室。读入后先打印 `isna().sum()` 与 `duplicated().sum()`，把缺失行数和重复行数摊在明面上。

| 操作 | 入口 | 作用 | 易错点 |
| --- | --- | --- | --- |
| 读入并定类型 | `read_csv(path, dtype=..., parse_dates=...)` | 数值列与日期列一步到位 | 不声明 `dtype` 时前导零、混合类型会被猜错 |
| 查缺失 | `isna()` 与 `isna().sum()` | 逐列统计缺失数量 | 空字符串默认不算缺失，要配合 `na_values` |
| 去重 | `duplicated()` 与 `drop_duplicates()` | 去掉整行重复上报 | 没定业务主键时会误删合法的两笔同额记录 |
| 规整字符串 | `str.strip()` 与 `astype('category')` | 统一空格、压缩低基数列 | 规整前分组会把同一科室拆成多组 |
| 处理缺失 | `dropna(subset=...)` 与 `fillna(0)` | 丢弃或填充 | 费用列填 0 会把没上报伪装成零元 |

### 纯标准库 csv 的等价管道

不装 `pandas` 也能跑通同一套口径。下面这段用 `csv.DictReader` 读内联 CSV，把空费用串记成 `None` 而不是 0，再按「科室 + 口径」分组算合计、例数和次均费用。它和后面的 DataFrame 版本做的是同一件事，方便在没有第三方库的环境里核对结论。

```python
import csv, io
from collections import defaultdict

RAW = """dept,channel,day,fee
内科,门诊,2024-03-01,320
内科,门诊,2024-03-01,
内科,住院,2024-03-01,8600
外科,门诊,2024-03-01,410
外科,住院,2024-03-01,12000
外科,住院,2024-03-02,9800
"""

def load(text):
    for row in csv.DictReader(io.StringIO(text)):
        fee = row['fee'].strip()
        yield row['dept'].strip(), row['channel'].strip(), (float(fee) if fee else None)

rows = list(load(RAW))
clean = [r for r in rows if r[2] is not None]
print('原始行', len(rows), '有效行', len(clean))

total, count = defaultdict(float), defaultdict(int)
for dept, channel, fee in clean:
    total[(dept, channel)] += fee
    count[(dept, channel)] += 1
for key in sorted(total):
    print(key, '合计', round(total[key], 2), '例数', count[key],
          '次均', round(total[key] / count[key], 2))
```

### Pandas 版本的读取与清洗

换成 DataFrame 后，同样的动作收敛成几行。注意 `drop_duplicates()` 放在字符串规整之后，规整前「外科 」和「外科」不算重复；分组汇总用一次 `groupby().agg()` 出齐计数、合计与均值，比逐行循环快得多。

```python
import pandas as pd
import io

RAW = """dept,channel,day,fee
内科,门诊,2024-03-01,320
内科,门诊,2024-03-01,
内科,住院,2024-03-01,8600
外科,门诊,2024-03-01,410
外科,住院,2024-03-01,12000
外科,住院,2024-03-02,9800
"""
df = pd.read_csv(io.StringIO(RAW), parse_dates=['day'], na_values=[''])
print('列类型', {k: str(v) for k, v in df.dtypes.items()})
print('缺失费用', int(df['fee'].isna().sum()), '重复行', int(df.duplicated().sum()))
df['dept'] = df['dept'].str.strip()
df = df.drop_duplicates()
clean = df.dropna(subset=['fee']).copy()
print(clean.groupby('channel')['fee'].agg(['count', 'sum', 'mean']).round(2))
```

`na_values=['']` 让空串直接变成缺失值，`dropna(subset=['fee'])` 只在费用列上丢弃行，其它列仍保留。聚合结果里 `count` 不含缺失、`sum` 默认跳过缺失，两者分母一致，次均费用才可信。

## 多表联合、分组聚合与 pivot_table

明细表往往只是一半：科室维表另有所在楼栋、床位数字段，把它拼进来才能按院区分组。拼接用 `pd.merge`，关键是先确认维表里的科室键唯一。`validate='many_to_one'` 会在运行期检查「明细多行对维表一行」，键不唯一就直接报错，避免行数悄悄膨胀；`indicator=True` 加一列 `_merge`，能数出有多少行没匹配上维表。

| 需求 | 入口 | 返回形状 | 用途 |
| --- | --- | --- | --- |
| 拼接维表 | `merge(..., on='dept', validate='many_to_one')` | 按 `how` 决定行数 | 补院区、床位等属性 |
| 每组一个标量 | `groupby(key).agg(['sum', 'mean'])` | 长度等于组数 | 出汇总表 |
| 广播回原行 | `groupby(key).transform('mean')` | 与原行等长 | 算每行相对组均值的偏差 |
| 长表转宽表 | `pivot_table(index, columns, values)` | 行列都是维度 | 科室 × 口径费用矩阵 |
| 交叉计数 | `crosstab(index, columns)` | 频数矩阵 | 口径与科室的记录分布 |

### 从 merge 到透视与合计复核

下面把明细和维表合并，再按「科室 × 口径」透视出费用合计。透视表出来后别急着用，先用 `sum(axis=0)` 和 `sum(axis=1)` 求行列合计，和原始明细的总数对一遍，数字对得上才说明拼接没丢行也没重复。次均费用必须在最细的「科室 + 口径」分组上算，再决定要不要展示成宽表。

```python
import pandas as pd

visits = pd.DataFrame({
    'dept': ['内科', '内科', '外科', '外科'],
    'channel': ['门诊', '住院', '门诊', '住院'],
    'fee': [320.0, 8600.0, 410.0, 12000.0],
})
meta = pd.DataFrame({'dept': ['内科', '外科'], 'building': ['A', 'B']})
merged = pd.merge(visits, meta, on='dept', how='left',
                  validate='many_to_one', indicator=True)
print('匹配来源', merged['_merge'].value_counts().to_dict())

pt = merged.pivot_table(index='dept', columns='channel', values='fee',
                        aggfunc='sum', fill_value=0)
print(pt)
print('列合计', pt.sum(axis=0).to_dict(), '行合计', pt.sum(axis=1).to_dict())
print('明细总额', float(visits['fee'].sum()))

g = merged.groupby(['dept', 'channel'])['fee'].agg(['sum', 'count'])
g['avg'] = (g['sum'] / g['count']).round(2)
print(g)
```

`pivot_table` 和 `pivot` 的区别正在于前者带 `aggfunc`，能处理重复的「科室 + 口径」组合；若误用 `pivot` 遇到重复键会直接抛错。`fill_value=0` 只影响显示，不改动参与计算的原始值。

## 医院科室费用透视：门诊与住院分开算

医院费用分析最容易出错的地方不是代码，是口径。门诊按人次计费、金额多在几百元，住院按床日和项目计费、动辄上万元，两者的次均费用差一个数量级。把它们混在一张表里求「平均费用」，得到的数字既不代表门诊也不代表住院，没有业务含义。正确做法是先按口径分组，分别算合计、例数和次均，再决定怎么并列展示。

| 口径 | 分子 | 分母 | 次均费用含义 | 能否与他口径相加 |
| --- | --- | --- | --- | --- |
| 门诊 | 门诊费用合计 | 门诊人次 | 每门诊人次平均费用 | 合计可加，次均不可加 |
| 住院 | 住院费用合计 | 出院人次 | 每出院人次平均费用 | 合计可加，次均不可加 |
| 全口径合计 | 两类费用合计 | 不定义 | 无对应均值 | 仅合计有意义 |

另外要区分「费用合计」和「例数」这两个可加指标与「次均费用」这个比值指标：前两者可以跨科室、跨口径相加，比值必须先各自算完再比较。透视表里若出现「科室总次均」这样的列，多半是把两类人次直接相加当分母，复核时要拦下来。报告里还应写明退费、跨科转诊、当日未结算的记录怎么归属，这些边界不写清，同一份数据两个人能算出两个结果。

## 疫情与一线城市房价的时间序列分析

两类数据都带时间列，处理顺序相近：先把日期转成 `datetime64[ns]` 并设为索引，再按需要重采样。疫情逐日数据用 `resample('D').sum()` 对齐到自然日，`diff()` 得到每日新增，`rolling(7).mean()` 抹掉周末上报波动；累计确诊是 `cumsum()` 的结果，和每日新增不是一个量纲，别画在同一根纵轴上，用 `subplots` 分成两张子图比 `twinx()` 双轴更少误导。环比用 `pct_change()`，基期为零或缺失时会得到 `inf` 或 `NaN`，画之前先替换掉。

一线城市房价按「城市 + 季度」组织，先统一口径再比较：链家式的「元 / 平米」和「套均总价」不能直接放一张图，均价易被豪宅成交拉高，偏态分布下用中位数更稳，这一点和第 096 讲的结论一致。分组用 `pivot_table(index='quarter', columns='city', values='price', aggfunc='median')`，同比在季度数据上相当于 `pct_change(4)`，算完检查基期是否为零。城市间比较还要对齐统计区间，一个用成交价、一个用挂牌价，结论就不可比。

## Scipy 概率分布与假设检验

图形和描述统计回答「差了多少」，假设检验回答「这点差异能不能排除抽样偶然」。用 `scipy.stats` 时先立原假设和显著性水平，再挑检验，最后才读 p 值。挑检验之前要验前提：`shapiro` 看样本是否偏离正态，`levene` 看两组方差是否齐；方差不齐就别用默认 `equal_var=True` 的 `ttest_ind`，改 `equal_var=False` 走 Welch 检验，或直接用不依赖分布的 `mannwhitneyu`。置信区间用 `stats.norm.interval` 或 t 分布的 `stats.t.interval` 配 `stats.sem`，它比一个孤零零的 p 值更能说明效应范围。

| 问题 | 入口 | 前提 | 读什么 |
| --- | --- | --- | --- |
| 样本是否近似正态 | `stats.shapiro(x)` | 样本量适中 | p 值小于阈值说明偏离正态 |
| 两组方差是否齐 | `stats.levene(a, b)` | 无 | p 值决定用哪种 t 检验 |
| 两组均值是否有差异 | `stats.ttest_ind(a, b, equal_var=False)` | 近似正态、独立 | 统计量与双尾 p 值 |
| 不假定分布的两组比较 | `stats.mannwhitneyu(a, b)` | 独立样本 | 秩和检验的 p 值 |
| 均值的区间估计 | `stats.t.interval(0.95, df, loc, scale)` | 小样本用 t | 区间是否跨过零 |

```python
import numpy as np
from scipy import stats

rng = np.random.default_rng(7)
a = rng.normal(loc=320, scale=45, size=40)   # 改版前门诊费用
b = rng.normal(loc=348, scale=50, size=38)   # 改版后门诊费用

print('shapiro a', round(stats.shapiro(a).pvalue, 4))
print('levene', round(stats.levene(a, b).pvalue, 4))
t = stats.ttest_ind(a, b, equal_var=False)
print('welch t', round(t.statistic, 3), 'p', round(t.pvalue, 4))
print('mannwhitney p', round(stats.mannwhitneyu(a, b, alternative='two-sided').pvalue, 4))
ci = stats.t.interval(0.95, len(a) - 1, loc=a.mean(), scale=stats.sem(a))
print('ci95', tuple(round(v, 2) for v in ci))
print('chi2 拟合优度', round(stats.chisquare([18, 22, 20, 25]).pvalue, 4))
```

门诊费用和住院费用不要合在一起做两样本检验：它们来自不同的计费机制，混成一个样本等于把两种分布硬拼，检验前提从一开始就不成立。每天检验一次、连查二十天直到 p 值显著，也会把假阳性累积到约 0.64，这些边界在第 096 讲里已经算过，报告里要预先固定假设与样本量并标注数据来源。

## Matplotlib 与 Seaborn 的图表选型

选图先看分析目的，而不是看哪种图好看。趋势用折线、类别比较用柱状、分布用直方图或箱线、两变量关系用散点、矩阵用热力图。Seaborn 的优势是「长表 + 语义映射」：把 `x`、`y`、`hue` 指到列上，`sns.lineplot` 自动分组画多条线；Matplotlib 负责精确控制子图、刻度和导出。中文标题要先设字体，否则导出的是方框，Linux 服务器上没有中文字体时要么装字体、要么改用英文标题。

| 分析目的 | 推荐图 | Matplotlib 入口 | Seaborn 入口 | 适用数据 |
| --- | --- | --- | --- | --- |
| 随时间变化 | 折线图 | `plt.plot` | `sns.lineplot` | 逐日新增、季度均价 |
| 类别间比较 | 柱状图 | `plt.bar` | `sns.barplot` | 各城市均值、科室合计 |
| 分布与离群点 | 箱线图 | `plt.boxplot` | `sns.boxplot` | 费用分布、偏态检查 |
| 单变量形状 | 直方图 | `plt.hist` | `sns.histplot` | 房价、费用频数 |
| 两变量关系 | 散点图 | `plt.scatter` | `sns.scatterplot` | 面积与总价 |
| 交叉矩阵 | 热力图 | `plt.imshow` | `sns.heatmap` | 科室 × 口径透视 |

```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

sns.set_theme(style='whitegrid')
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

df = pd.DataFrame({
    'city': ['北京', '上海', '广州', '深圳'] * 3,
    'quarter': ['Q1'] * 4 + ['Q2'] * 4 + ['Q3'] * 4,
    'price': [61, 58, 32, 54, 62, 59, 33, 55, 63, 60, 34, 56],
})
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
sns.lineplot(data=df, x='quarter', y='price', hue='city', marker='o', ax=axes[0])
axes[0].set_title('一线城市季度均价走势')
sns.barplot(data=df, x='city', y='price', ax=axes[1])
axes[1].set_title('各城市季度均值')
fig.tight_layout()
fig.savefig('price_report.png', dpi=150, bbox_inches='tight')
print('图片尺寸', fig.get_size_inches())
```

无界面环境里显式 `matplotlib.use('Agg')`，图只写文件不弹窗口。`dpi=150` 保证报告里放大不糊，`bbox_inches='tight'` 裁掉多余白边；图注要写清单位与统计口径，光有图没有口径，读者没法复核。

## CSV 与 SQL 查询工具的最小实现

第 127 讲做过日志 ETL 与 CSV / SQL 查询工具，这里补一个能直接跑的最小版本：用 `csv.DictReader` 把 CSV 灌进 `sqlite3` 内存库，再用参数化 SQL 出汇总。CSV 里的值全是字符串，入库前显式转 `float`，否则 `SUM` 会按文本拼接；查询条件一律用 `?` 占位传参，绝不把外部输入拼进 SQL 字符串，这是防注入的底线。对外只暴露 `SELECT`，或用 `PRAGMA query_only=ON` 把连接设成只读。

```python
import csv, io, sqlite3

RAW = """dept,channel,fee
内科,门诊,320
内科,住院,8600
外科,门诊,410
外科,住院,12000
"""
con = sqlite3.connect(':memory:')
con.execute('CREATE TABLE fees (dept TEXT, channel TEXT, fee REAL)')
con.executemany('INSERT INTO fees VALUES (?, ?, ?)',
                [(r['dept'], r['channel'], float(r['fee']))
                 for r in csv.DictReader(io.StringIO(RAW))])
con.commit()
con.execute('PRAGMA query_only=ON')

sql = ('SELECT dept, SUM(fee) AS total FROM fees '
       'WHERE channel = ? GROUP BY dept ORDER BY total DESC')
print('住院合计', con.execute(sql, ('住院',)).fetchall())
print('全院合计', con.execute('SELECT ROUND(SUM(fee), 2) FROM fees').fetchone()[0])
con.close()
```

数据量上去后给 `dept`、`channel` 建索引，或把内存库换成落地的 `.db` 文件；查询工具的输出再交给 `to_csv` 或 `to_html`，就和前面的报告环节接上了。工具层保持只读、参数化、类型显式转换这三点，比堆功能更重要。

## 报告导出为 HTML / PDF 与结果复核

导出不是把图贴进文档就结束。`DataFrame.to_html` 生成表格片段，外面要补一层带 `<meta charset="utf-8">` 的页面骨架，中文才不会乱码；PDF 有三条常见路径：`jupyter nbconvert --to webpdf` 把整个 Notebook 连同图一起转，`weasyprint report.html -o report.pdf` 走 HTML / CSS 排版，`reportlab` 或 `fpdf2` 直接画版式。命令行转换放在最后一步，别和计算代码混在一个单元格里。

```bash
jupyter nbconvert --to webpdf analysis.ipynb
weasyprint report.html -o report.pdf
```

| 格式 | 生成方式 | 额外依赖 | 复核手段 |
| --- | --- | --- | --- |
| CSV | `to_csv(index=False)` | 无 | 回读比较行数与合计 |
| HTML | `to_html` 加页面骨架 | 无 | 浏览器打开看编码与表格 |
| PDF | `nbconvert --to webpdf` | Chromium | 页数、图表是否齐全 |
| PDF | `weasyprint` 转 HTML | weasyprint | 中文字体是否嵌入 |
| PNG | `savefig(dpi=150)` | matplotlib | 放大看刻度与单位 |

```python
import pandas as pd
import io

df = pd.DataFrame({
    '科室': ['内科', '外科'],
    '门诊次均': [320.0, 410.0],
    '住院次均': [8600.0, 12000.0],
})
page = ('<!doctype html><html><head><meta charset="utf-8">'
        '<title>费用报告</title></head><body><h1>科室费用汇总</h1>')
page += df.to_html(index=False, border=1)
page += '<p>口径：门诊与住院分别统计，缺失费用不计入分子与分母。</p></body></html>'
with open('report.html', 'w', encoding='utf-8') as f:
    f.write(page)

buf = io.StringIO()
df.to_csv(buf, index=False)
buf.seek(0)
back = pd.read_csv(buf)
print('导出前后合计一致',
      round(back['门诊次均'].sum(), 2) == round(df['门诊次均'].sum(), 2))
print('HTML 字节数', len(page.encode('utf-8')))
```

结果复核至少走四项：把导出的 CSV 回读，核对行数与合计和原表一致；透视表的行列合计与明细总数对齐；报告正文写明数据来源、截止日期、依赖版本和每个比值的口径；检验结论附样本量、检验前提与置信区间，而不是只写一个 p 值。能让人按报告重算一遍，导出才算完成。

## 常见坑 / 口径与边界

### 把缺失费用当成零元

空费用格表示未上报或尚未结算，不等于花了零元。`fillna(0)` 会把这笔记录算进分母，次均费用被拉低；费用列按 `dropna(subset=...)` 丢弃，或单独统计缺失行数写进报告，二选一且前后一致。

### 门诊与住院混算次均费用

两类费用量级差一个数量级，合并求均值得到的数字没有业务对应。合计可以相加，次均必须在「科室 + 口径」最细分组上分别算；透视表里出现「总次均」列时要回查分母是不是把两类人次直接相加了。

### 维表拼接让行数悄悄膨胀

科室维表里一个科室若有两行，`merge` 会把明细复制成两倍，透视合计跟着翻倍。`validate='many_to_one'` 在运行期拦下这种键不唯一的情况，`indicator=True` 再数一遍没匹配上的行；拼接后比较 `len(merged)` 与 `len(visits)` 是最省事的复核。

### 检验前提没验就套 t 检验

用 `ttest_ind` 前先看正态性与方差齐，偏离明显就换 Welch 检验或 `mannwhitneyu`；把门诊样本和住院样本混作一组、或反复检验直到 p 值显著，结论都站不住。业务报告里只写「相关」与「差异」，不写因果，并标注样本量和数据窗口。

### 导出后不回读、报告里不写口径

HTML 少了 `utf-8` 声明会中文乱码，PDF 没嵌字体会掉字，数字对不上往往要等到读者发现才暴露。导出后回读 CSV 核对合计，报告里写清每个比值怎么算、缺失与退费怎么处理，别人才能照着重算。

## 练习

::: details 练习 1 · 用标准库 csv 算住院次均费用

给一份含空值、重复行和门诊记录的 CSV，用纯标准库 `csv` 计算各科室的住院次均费用。空费用行不计入分子也不计入分母，门诊行整行跳过，结果保留两位小数。

```python
import csv, io
from collections import defaultdict

raw = """dept,channel,fee
内科,住院,8600
内科,住院,9400
外科,住院,12000
内科,住院,
外科,门诊,410
"""
total, count = defaultdict(float), defaultdict(int)
for r in csv.DictReader(io.StringIO(raw)):
    fee = r['fee'].strip()
    if r['channel'] != '住院' or not fee:
        continue
    total[r['dept']] += float(fee)
    count[r['dept']] += 1
result = {d: round(total[d] / count[d], 2) for d in sorted(total)}
print(result)   # 内科 9000.0，外科 12000.0
```
:::

::: details 练习 2 · 透视费用并用 Scipy 判断两组差异

用 `pivot_table` 把长表转成分科室、分口径的费用合计宽表，再用 `scipy.stats.ttest_ind` 比较门诊与住院费用；说明为什么不能把两类费用合并后做一次检验，以及方差不齐时该改哪个参数。

```python
import pandas as pd
from scipy import stats

df = pd.DataFrame({
    'dept': ['内科'] * 3 + ['外科'] * 3,
    'channel': ['门诊', '门诊', '住院'] * 2,
    'fee': [300, 340, 8600, 400, 420, 12000],
})
pt = df.pivot_table(index='dept', columns='channel', values='fee', aggfunc='sum')
print(pt)
out = df[df['channel'] == '门诊']['fee']
inn = df[df['channel'] == '住院']['fee']
t = stats.ttest_ind(out, inn, equal_var=False)
print('welch p', round(t.pvalue, 4))
# 两类费用计费机制不同、量级差一个数量级，合并样本没有共同分布；
# 方差明显不齐时把 equal_var 设为 False 走 Welch 检验。
```
:::


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能跑通本专题按正文顺序整理的标准库示例；需要第三方库的片段会自动跳过并打印安装提示，不装任何库也能看到核心结果。" />

**本专题示例代码** · 仓内路径 `examples/topics/data-projects.py`

```bash
python3 examples/topics/data-projects.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/topics/data-projects.py) · [全部示例代码索引](/examples/)
