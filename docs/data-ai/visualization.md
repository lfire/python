---
title: 第 095 讲 · 可视化：Matplotlib / Seaborn / Plotly 与图表选型
description: 用图准确表达数据而不是装饰数据
---

<StageHeader stage='L9 · 数据与 AI' level='★★☆☆☆' time='35 分钟' goal='用图准确表达数据而不是装饰数据' prereq='第 094 讲 · Pandas 清洗、分组、透视与时间序列' />

# 第 095 讲 · 可视化：Matplotlib / Seaborn / Plotly 与图表选型

表理得整整齐齐，可几万行摊在屏幕上，趋势和离群的那几笔仍要靠盯。周会上想说明销量只是小幅回升，若柱状图纵轴不从零起，几个百分点会被画成翻倍，听的人容易得出相反结论。本讲要让图准确替数据说话，而不是装饰好看。

先按数据关系把图表类型定下来，比较、趋势、分布、关系各对应什么，选错图结论就偏；再弄清 Figure 与 Axes 的对象模型，画图不再被隐式当前子图绕住；最后细看配色与可读性、统计图形里的置信区间和纵轴截断。需要上一讲干净的 DataFrame 和基本的函数概念。学完能为一份数据挑对图、标清单位与样本量，让图和代码一起留档。


## 一张把 8% 差距画成悬殊结论的柱状图

季度汇报里两张图结论完全相反：一张柱状图把纵轴从 92 起画，A 产品 96、B 产品 100 看起来差了四倍；另一张从 0 起画，两根柱子几乎齐平。运营据此砍了 A 的预算，月底才发现真实差距只有 4%。另一处事故是把 3D 饼图塞进大屏，占比最小的那块因透视变形反而最显眼。

还有同事把时间序列画成散点、把两个量纲不同的指标叠在双轴上，读者根本无法判断谁在涨。问题不在『画得不好看』，而在图表类型与数据关系没匹配、纵轴被截断、对象模型没弄清导致样式改到错误的图层上。选错图会让人得出错误结论，这比配色难看严重得多；本讲把『用图准确表达数据』拆成可核对的规则。

<Callout type="warn" title='先看一个真实会出错的写法' text='柱状图纵轴不从 0 起，结论被夸大：长度编码被减去一个基线后放大，92 与 100 看起来差好几倍' />


## 按数据关系选图：比较、趋势、分布、关系

图型由你要回答的问题决定。

比较少量类别的大小用条形图（bar），且条形必须从 0 起，因为长度是编码通道；看随时间变化的趋势用折线图（line），横轴是有序的时间，强调斜率与拐点；看单变量的分布用直方图（hist）或箱线图（boxplot），前者靠分箱计数看形状、后者用四分位数与须线标出离群点；看两个数值变量的关系用散点图（scatter），可加回归线与置信带；看占比用堆叠条形或普通饼图，但类别一多就该换成条形排序；看多变量相关用热力图。

把分类比较画成折线，会暗示并不存在的连续趋势；把占比画成 3D 饼图，透视会让近处扇区被夸大。

Matplotlib 里对应的是 `ax.bar`、`ax.plot`、`ax.hist`、`ax.boxplot`、`ax.scatter`；Seaborn 在此之上提供面向 DataFrame 的 `sns.barplot`、`sns.lineplot`、`sns.histplot`、`sns.boxplot` 并默认带置信区间估计；Plotly 用 `go.Figure` 生成可缩放、可悬停的交互图，适合大屏与网页嵌入。

选型错误无法靠后期美化弥补，所以第一步永远是写下『这张图要比较什么、样本量多少、时间范围是什么』。

**数据关系与图表选型**

| 要回答的问题 | 推荐图型 | Matplotlib API | 编码通道 |
| --- | --- | --- | --- |
| 类别之间比大小 | 条形图(从 0 起) | ax.bar | 长度 |
| 随时间看趋势 | 折线图 | ax.plot | 斜率/位置 |
| 看单变量分布 | 直方图 / 箱线图 | ax.hist / ax.boxplot | 面积 / 四分位 |
| 看两变量关系 | 散点图 | ax.scatter | 二维位置 |
| 看构成占比 | 堆叠条 / 饼图 | ax.bar(stacked) / ax.pie | 面积/角度 |


## Figure 与 Axes：对象模型与 pyplot 状态机

Matplotlib 分两层：Figure 是整张画布（含尺寸 figsize、dpi、背景），Axes 是画布上真正画图的一个坐标系（含 x/y 轴、刻度、标题、图例、数据）。

`plt.subplots(nrows,ncols)` 一次返回 (fig, axes)，多子图时 axes 是 ndarray，用 `axes[i,j]` 定位；`plt.subplots_adjust` 或 `fig.tight_layout()` 处理子图间距。

pyplot 是一层『状态机』：`plt.plot()` 隐式作用于『当前 Axes』，脚本短时方便，但函数一多就不知道画到哪张图上了；工程代码应显式用面向对象接口 `ax.plot(...)`、`ax.set_xlabel(...)`、`ax.set_title(...)`、`ax.legend()`，把每个操作绑定到确定的 Axes。

`ax.twinx()` 生成共享 x 轴的第二 y 轴，双轴极易误导读者以为两条线可比，除非确有必要并明确标注单位，否则不叠加。

导出用 `fig.savefig('out.png',dpi=150,bbox_inches='tight')`，`bbox_inches` 会裁掉多余白边，dpi 决定位图分辨率，矢量场景导出 .svg 或 .pdf 更清晰。

可复现要求把绘图脚本、随机种子、数据快照与库版本一起纳入版本管理，并在图上或图注里写明单位、样本量 n 与时间范围，否则同一张图换批数据就得不出同一结论。

```python
def bars(values, labels, width=20):
    top = max(values)
    out = []
    for lab, v in zip(labels, values):
        n = round(v / top * width)
        out.append(lab + ' | ' + '#' * n + ' ' + str(v))
    return chr(10).join(out)

data = [('一季度', 120), ('二季度', 180), ('三季度', 95)]
print(bars([v for _, v in data], [l for l, _ in data]))
```

<OutputBox title='主示例运行结果' output='一季度 | ############# 120\n二季度 | #################### 180\n三季度 | ########### 95' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def bars(values, labels, width=20):\n    top = max(values)\n    out = []\n    for lab, v in zip(labels, values):\n        n = round(v / top * width)\n        out.append(lab + &#39; | &#39; + &#39;#&#39; * n + &#39; &#39; + str(v))\n    return chr(10).join(out)\n\ndata = [(&#39;一季度&#39;, 120), (&#39;二季度&#39;, 180), (&#39;三季度&#39;, 95)]\nprint(bars([v for _, v in data], [l for l, _ in data]))' :notes='["定义把数值映射成条形长度的函数，模拟 bar 图的长度编码", "以最大值作为满格的基准，保证最长条恰好占满 width", "out 收集每一行的文本条形", "按标签与数值一一配对遍历", "把数值按比例折算成 &#39;#&#39; 的个数，这是零基线的长度编码", "直接拼出标签、条形与原始数值，便于核对", "用 chr(10) 连接多行，避免在示例代码里写换行转义", "空行，只用于分隔逻辑块，不影响执行结果。", "三组季度数据，模拟分类比较场景", "分别取出数值列与标签列传入 bars，输出三行条形"]' title='第 095 讲 · 可视化：Matplotlib / Seaborn / Plotly 与图表选型' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 多子图里样式为什么串到别处

```python
data = [1, 2, 2, 3, 3, 3, 4, 5, 5, 7, 8, 9, 9, 10]
bins = [0] * 4
for v in data:
    bins[min(3, (v - 1) // 3)] += 1
print('bins 1-3/4-6/7-9/10-12', bins)
print('total', sum(bins), 'n', len(data))
```

<OutputBox title='对照写法：先自己猜，再点开' output='bins 1-3/4-6/7-9/10-12 [6, 3, 4, 1]\ntotal 14 n 14' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "def bars(values, labels, width=20):\n    top = max(values)\n    out = []\n    for lab, v in zip(labels, values):\n        n = round(v / top * width)\n        out.append(lab + &#39; | &#39; + &#39;#&#39; * n + &#39; &#39; + str(v))\n    return chr(10).join(out)\n\ndata = [(&#39;一季度&#39;, 120), (&#39;二季度&#39;, 180), (&#39;三季度&#39;, 95)]\nprint(bars([v for _, v in data], [l for l, _ in data]))", "note": "按数据关系选图，而不是按习惯选图"}, {"label": "对照 / 进阶", "code": "data = [1, 2, 2, 3, 3, 3, 4, 5, 5, 7, 8, 9, 9, 10]\nbins = [0] * 4\nfor v in data:\n    bins[min(3, (v - 1) // 3)] += 1\nprint(&#39;bins 1-3/4-6/7-9/10-12&#39;, bins)\nprint(&#39;total&#39;, sum(bins), &#39;n&#39;, len(data))", "note": "Figure / Axes 对象模型与状态机的区别"}]' title='两种写法切换看' />


## 截断纵轴与 3D 饼图：误导是如何产生的

```python
vals = [92, 96, 100]
print('from zero', [round(v / 100, 2) for v in vals])
print('truncated at 90', [round((v - 90) / 10, 2) for v in vals])
print('ratio gap zero', round((100 - 92) / 100, 2), 'gap truncated', round((100 - 92) / 10, 2))
```

<OutputBox title='原理验证' output='from zero [0.92, 0.96, 1.0]\ntruncated at 90 [0.2, 0.6, 1.0]\nratio gap zero 0.08 gap truncated 0.8' />

<Callout type="warn" title='本讲最容易踩的坑' text='柱状图纵轴不从 0 起，结论被夸大：长度编码被减去一个基线后放大，92 与 100 看起来差好几倍' />


## 误差条、置信区间与样本量标注

柱状图的长度编码必须以 0 为基线：`ax.set_ylim(90, 100)` 会让 92 与 100 的视觉比从 0.92 变成 0.2 到 1.0，把 8% 差异放大成五倍；折线图在特定场景可以合理收窄纵轴以突出波动，但必须标注轴断点并说明，不能默认截断。

误差条与置信区间比单点更能表达不确定性：Seaborn 的 `sns.barplot` 默认用自助法（bootstrap）估计 95% 置信区间并画误差线，样本量小时间隔会很宽，忽略它会把噪声当成结论；误差条要明确标注是标准差、标准误还是置信区间，三者含义不同。

配色上要给色觉缺陷（约 8% 男性有红绿色觉障碍）留余地，避免只靠红绿区分两组，优先用亮度或形状双编码；连续量用感知均匀的 colormap（viridis）而非彩虹 jet，因为 jet 的亮度非线性会制造不存在的边界。

图内标注样本量 n、单位、时间范围与数据来源；把『结论』写进标题（如『B 比 A 高 4%』）而不是『销售对比』这种无信息标题，读者才不会自行脑补。这些约束都与绘图库无关，属于数据表达的契约。

**三大库的定位差异**

| 库 | 抽象层级 | 交互性 | 典型场景 |
| --- | --- | --- | --- |
| Matplotlib | Figure/Axes 底层对象 | 静态为主 | 论文图、精确控制导出 |
| Seaborn | 面向 DataFrame 的统计封装 | 静态 | 带置信区间的统计图 |
| Plotly | 声明式 go.Figure | 缩放/悬停 | 网页、大屏、交互探索 |


## Matplotlib、Seaborn、Plotly 的分工

**常见误导性画法与修正**

| 画法 | 误导后果 | 正确做法 |
| --- | --- | --- |
| 柱状图纵轴从 90 起 | 8% 差异被放大成 5 倍视觉差 | 柱状图一律从 0 起 |
| 3D 饼图展示占比 | 透视夸大近处扇区 | 改堆叠条或排序条形 |
| 双 y 轴叠两条线 | 读者误以为量纲可比 | 分面画或明确标单位 |
| 只画均值不画误差 | 把噪声当显著结论 | 加 95% 置信区间并标 n |

<Term word='图表类型与数据关系' text='图型由你要回答的问题决定。比较少量类别的大小用条形图（bar），且条形必须从 0 起，因为长度是编码通道；看随时间变化的趋势用折线图（line），横轴是有序的时间，强调斜率与拐点；看单变量的分布用直方图（hist）或箱线图（boxplot），前者靠分箱计数看形状、后者用四分位数与须线标出离群点；看两个数值变量的关系用散…' />

<Term word='Figure / Axes 对象模型' text='Matplotlib 分两层：Figure 是整张画布（含尺寸 figsize、dpi、背景），Axes 是画布上真正画图的一个坐标系（含 x/y 轴、刻度、标题、图例、数据）。`plt.subplots(nrows,ncols)` 一次返回 (fig, axes)，多子图时 axes 是 ndarray，用…' />


## 长度编码与视觉通道：误差是怎么被放大的

图本质上是把数据维度映射到视觉通道：位置、长度、角度、面积、亮度、色相。人对长度与位置的比较精度远高于面积与角度，这就是条形图比饼图更可靠、折线图适合有序时间轴的感知基础。柱状图用长度编码，长度必须与数值成正比，因此基线必须是 0；把轴截断到 90 起，等价于把数值先减去 90 再线性放大十倍，视觉差被系统性放大。

Matplotlib 的分层来自出版级排版需求：Figure 管画布物理尺寸与 dpi，Axes 管一个坐标系内的数据变换（data 坐标经 transform 映射到 display 像素），Artist 是画在 Axes 上的一切对象。

pyplot 状态机只是为这套 OO 模型提供便捷入口，隐式『当前 Axes』在多图场景正是样式错位的来源。置信区间来自对统计量的抽样分布估计（如 bootstrap 重采样或标准误乘临界值），它量化的是估计不确定性而非数据离散度，所以标注时必须写明类型与 n。

<ConceptDiagram type='flow3' title='第 095 讲 · 按数据关系选图，而不是按习惯选图' labels='按数据关系选图，而不是按习惯选图|Figure / Axes 对象模型与状态机…|可读性陷阱：截断纵轴、置信区间与配色' caption='用图准确表达数据而不是装饰数据' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 配色、导出与可复现的绘图脚本

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 柱状图纵轴不从 0 起，结论被夸大 | 长度编码被减去一个基线后放大，92 与 100 看起来差好几倍 | ax.set_ylim(bottom=0)，柱状图一律零基线；折线需收窄时明确标注轴断点 |
| 样式改了却作用到另一张子图 | 用 pyplot 状态机时 plt.plot 作用于隐式当前 Axes，多子图下容易错位 | fig, axes = plt.subplots(...)，之后全部用 axes[i].plot / .set_title 等 OO 接口 |
| 只画均值不标不确定性与样本量 | 小样本下均值波动大，读者把噪声当成确定性结论 | 加误差条或 sns.barplot 的 95% 置信区间，标注 n、单位、时间范围与区间类型 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：柱状图纵轴不从 0 起，结论被夸大", "body": "长度编码被减去一个基线后放大，92 与 100 看起来差好几倍", "tip": "ax.set_ylim(bottom=0)，柱状图一律零基线；折线需收窄时明确标注轴断点"}, {"title": "第 2 步：样式改了却作用到另一张子图", "body": "用 pyplot 状态机时 plt.plot 作用于隐式当前 Axes，多子图下容易错位", "tip": "fig, axes = plt.subplots(...)，之后全部用 axes[i].plot / .set_title 等 OO 接口"}, {"title": "第 3 步：只画均值不标不确定性与样本量", "body": "小样本下均值波动大，读者把噪声当成确定性结论", "tip": "加误差条或 sns.barplot 的 95% 置信区间，标注 n、单位、时间范围与区间类型"}]' />


## 可复现的季报图：把规模、单位与结论一起固化

一份要进季度评审的图，评审最常问三个问题：样本量多少、纵轴是不是从 0 起、结论能不能复现。稳妥做法是把绘图逻辑写成函数，入参是数据与标题，函数内部统一零基线、把数值标签与 n 写进图注、导出时固定 dpi 与 `bbox_inches`，并把脚本、数据快照与库版本一起提交。

下面用标准库实现其中『数据 → 零基线条形 → 标注』的部分：它计算各柱的归一化长度、显式验证基线为 0、打印总样本量与最大最小比，让每个结论都有可核对的数字。真实工程把 `build_bars` 换成 `ax.bar`、把 annotate 换成 `ax.text` 与 `ax.set_title`，绘图口径不变。

```python
def build_bars(records, width=40):
    values = [v for _, v in records]
    top = max(values)
    assert min(values) >= 0, 'bar baseline must be zero'
    lines = []
    for label, v in records:
        length = round(v / top * width)
        lines.append(label + ' | ' + '#' * length + ' ' + str(v))
    return lines

def caption(records):
    vals = [v for _, v in records]
    n = sum(vals)
    ratio = round(max(vals) / min(vals), 2)
    return 'n=' + str(len(vals)) + ' total=' + str(n) + ' max/min=' + str(ratio)

records = [('A 产品', 96), ('B 产品', 100), ('C 产品', 98)]
for line in build_bars(records):
    print(line)
print(caption(records))
```

<Callout type="idea" title='落地提示' text='图表带单位、样本量与时间范围，分析结果与绘图代码一起版本化，保证可复现' />

<CheckList id='P095a' title='上线前自检' :items='["能复现并解释「柱状图纵轴不从 0 起，结论被夸大」", "能复现并解释「样式改了却作用到另一张子图」", "能复现并解释「只画均值不标不确定性与样本量」", "能用一条命令验证 图表类型与数据关系", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import statistics as s; print(s.mean([1,2,3,100]), s.median([1,2,3,100]))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 图表类型与数据关系 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 练习、自测与速记卡

<Exercise title='基础：按数据关系选图' task='给定四种分析目标（比较 5 个品类销量、看一年 12 个月趋势、看订单金额分布、看广告费与销量关系），写出各自应选的图型与 Matplotlib API，并说明为什么比较类不能用饼图。' solution='picks = {\n    &#39;compare 5 categories&#39;: (&#39;bar&#39;, &#39;ax.bar&#39;),\n    &#39;12-month trend&#39;: (&#39;line&#39;, &#39;ax.plot&#39;),\n    &#39;amount distribution&#39;: (&#39;hist&#39;, &#39;ax.hist&#39;),\n    &#39;ads vs sales&#39;: (&#39;scatter&#39;, &#39;ax.scatter&#39;),\n}\nfor k, v in picks.items(): print(k, &#39;-&gt;&#39;, v)' explain='比较用长度编码、趋势用有序横轴的斜率、分布用分箱计数、关系用二维位置。饼图用角度/面积编码，人眼比较精度低且类别一多就分不清，不适合精确比较。' />

<Exercise title='进阶：量化截断纵轴的误导' task='对 [92, 96, 100] 分别计算「从 0 起」与「从 90 起」两组的归一化视觉高度与最大最小差，说明为什么前者才是诚实的表达。' solution='vals = [92, 96, 100]\nzero = [v/100 for v in vals]\ncut = [(v-90)/10 for v in vals]\nprint(&#39;zero&#39;, [round(x,2) for x in zero], &#39;spread&#39;, round(max(zero)-min(zero),2))\nprint(&#39;cut&#39;, [round(x,2) for x in cut], &#39;spread&#39;, round(max(cut)-min(cut),2))' explain='从 0 起时三者是 0.92/0.96/1.0、极差 0.08；从 90 起变成 0.2/0.6/1.0、极差 0.8，视觉差被放大十倍。柱状图是长度编码，必须从 0 起。' />

<Quiz no='095-1' q='比较 5 个品类的销量，最稳妥的图是？' :options='["从 0 起的条形图", "3D 饼图", "双 y 轴折线图", "不带刻度的散点图"]' answer="0" explain='条形图用长度编码、人眼比较精度最高，且必须从 0 起；饼图靠角度/面积、3D 透视还会夸大近处扇区，都不适合精确比较。' />

<Quiz no='095-2' q='关于截断纵轴，下面哪项准确？' :options='["柱状图必须从 0 起，截断会把微小差异成倍放大", "任何图都不能收窄纵轴", "截断纵轴会让折线图更诚实", "只要标了单位，截断多少都无所谓"]' answer="0" explain='柱状图是长度编码，基线非 0 会把差值系统性放大；折线图在分析波动时可合理收窄但须标注轴断点。「任何图都不能收窄」过于绝对。' />

<Quiz no='095-3' q='plt.subplots(2, 2) 返回的 axes 是什么，工程上应如何画图？' :options='["是 Axes 数组，应用 axes[i, j].plot() 等 OO 接口绑定到确定子图", "是一个 Figure，直接 plt.plot 即可", "是四个画布，需要四次 savefig", "是标量，只能用 plt 状态机"]' answer="0" explain='subplots 返回 (fig, axes)，多子图时 axes 是 ndarray。显式用 axes[i, j].plot / .set_title 把每个操作绑定到具体 Axes，避免状态机隐式当前 Axes 导致的样式错位。' />

<Predict no='095-4' q='前面 probe 里 vals=[92,96,100] 从 90 起截断后的归一化值是？' :options='["[0.2, 0.6, 1.0]", "[0.92, 0.96, 1.0]", "[2.0, 6.0, 10.0]"]' answer='0' output='[0.2, 0.6, 1.0]' explain='截断后每个值先减 90 再除以 10：92 变 0.2、96 变 0.6、100 变 1.0，极差从 0.08 放大到 0.8，正是柱状图截断纵轴会误导读者的数值证据。' />

<KnowledgeCard :points='["图型由问题定：比较用条形、趋势用折线、分布用直方图/箱线、关系用散点、占比用堆叠条、相关用热力图", "条形长度编码必须从 0 起；ax.set_ylim(90,100) 会把 8% 差异放大成五倍，折线收窄纵轴要标断点", "Figure 管画布、Axes 管一个坐标系；pyplot 是状态机，工程代码用 ax.plot/set_title 的 OO 接口绑定到确定 Axes", "误差条要写明是标准差、标准误还是置信区间；sns.barplot 默认 bootstrap 估 95% CI，小样本间隔会很宽", "配色给色觉缺陷留余地、用亮度或形状双编码，连续量用 viridis 而非 jet", "图内标注单位、样本量 n、时间范围与来源，标题写结论；脚本、种子、数据快照、库版本一起版本化"]' :pitfalls='["柱状图纵轴不从 0 起，结论被夸大", "样式改了却作用到另一张子图", "只画均值不标不确定性与样本量", "截断纵轴、双轴叠加、用 3D 饼图展示占比，都会把微小差异放大成显著结论"]' summary='图的选择由问题决定：比较用条形、趋势用折线、分布用直方图/箱线、关系用散点，选错图会得出错误结论' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 图型由问题定：比较用条形、趋势用折线、分布用直方图/箱线、关系用散点、占比用堆叠条、相关用热力图 | 建立直觉 |
| 条形长度编码必须从 0 起；ax.set_ylim(90,100) 会把 8% 差异放大成五倍，折线收窄纵轴要标断点 | 跑通示例 |
| Figure 管画布、Axes 管一个坐标系；pyplot 是状态机，工程代码用 ax.plot/set_title 的 OO 接口绑定到确定 Axes | 深入边界 |
| 误差条要写明是标准差、标准误还是置信区间；sns.barplot 默认 bootstrap 估 95% CI，小样本间隔会很宽 | 工程落地 |
| 配色给色觉缺陷留余地、用亮度或形状双编码，连续量用 viridis 而非 jet | 随堂检测 |
| 图内标注单位、样本量 n、时间范围与来源，标题写结论；脚本、种子、数据快照、库版本一起版本化 | 复盘 |

1. 图型由问题定：比较用条形、趋势用折线、分布用直方图/箱线、关系用散点、占比用堆叠条、相关用热力图

2. 条形长度编码必须从 0 起；ax.set_ylim(90,100) 会把 8% 差异放大成五倍，折线收窄纵轴要标断点

3. Figure 管画布、Axes 管一个坐标系；pyplot 是状态机，工程代码用 ax.plot/set_title 的 OO 接口绑定到确定 Axes

[下一讲：统计基础：分布、检验与相关性](/data-ai/statistics)

<FillBlank no='095-5' tpl='___ bars(values, labels, width=20):' :answers='["def"]' hint='回想本讲关于 图表类型与数据关系 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 按数据关系选图，而不是按习惯选图 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/095-visualization.py`

```bash
python3 examples/lessons/095-visualization.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/095-visualization.py) · [全部示例代码索引](/examples/)
