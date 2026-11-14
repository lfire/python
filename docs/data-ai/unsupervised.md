---
title: 第 101 讲 · 无监督学习：KMeans、DBSCAN、PCA 与异常检测
description: 在没有标签时从结构里找信息
---

<StageHeader stage='L9 · 数据与 AI' level='★★★☆☆' time='40 分钟' goal='在没有标签时从结构里找信息' prereq='第 100 讲 · 集成学习：Boosting、XGBoost 与 LightGBM' />

# 第 101 讲 · 无监督学习：KMeans、DBSCAN、PCA 与异常检测

到这一讲之前，手里的模型都有一列现成答案：房价、是否流失、类别标签。可换上一批用户行为记录，这一列往往并不存在，只是隐约觉得该分出几个小圈子、或者揪出几个反常账号。问题于是换了个问法：没有标准答案，还能不能单从数据的结构里读出东西——这正是无监督学习要接住的场景。

先讲聚类的假设与尺度，看 KMeans 怎样一步步挪动中心、K 该怎么定，量纲不统一时结果为什么会整个翻一遍；再走到 `DBSCAN` 的密度视角与 PCA 的方差解释，用降维把高维数据画成散点；最后把一串异常分数转成能运营的业务阈值，并拿时间做回测。需要你带着特征缩放、距离度量和 NumPy 运算的基础。读完之后，你能在无标签数据上给出一份分群或异常清单，并用业务抽样把它解释清楚。


## 同一批数据换个单位，聚类结果翻了一遍

风控团队用 KMeans 给交易分群，特征里既有「交易笔数」（个位数）又有「金额」（几十万），跑出来的簇几乎只按金额切，业务怎么解释都对不上；把金额在「元」和「万元」之间换个单位，聚类结果又整个翻了一遍。

另一份报告更省事，直接把 PCA 的第一主成分命名成「用户忠诚度」，写进结论被质疑后才承认：主成分只是方差最大的正交方向，没有天然的业务含义。还有一个团队在高维稀疏的用户标签上直接算欧氏距离做异常检测，近邻距离全挤在一起，阈值怎么调都分不出异常。无监督没有标签当裁判，结果高度依赖尺度、距离度量与业务解释这三件事；

本讲用纯 Python 把 KMeans 的迭代、K 的选择、以及尺度如何改写距离，都跑成可核对的数字。

<Callout type="warn" title='先看一个真实会出错的写法' text='不同量纲直接聚类，换单位结果就翻一遍：欧氏距离按差值平方累加，大尺度列主导，SSE 与簇归属被单位而非结构决定' />


## 聚类假设与尺度：距离由谁决定

KMeans 先把 n 个点划进 K 个簇，目标是让簇内平方和（inertia）最小，即每个点到所属簇中心的距离平方之和 `SSE = Σ||x - μ_c||²`。

它用 Lloyd 算法交替做两步：把每个点分给最近的中心，再把中心挪到该簇所有点的均值；两步都不会让 SSE 变大，于是 SSE 单调不增，并在有限步内收敛到局部最优。

一轮的代价约是 `O(n·K·d·iterations)`，n 是样本数、d 是特征数、iterations 是迭代轮数，数据一大就得靠 mini-batch 或先降维。

算法背后压着三条隐含假设：各簇大致球形、大小与方差相近、每个维度同等重要——所以动手前有三件事躲不掉，标准化消掉量纲、处理离群点（平方项会被极端值牵着走）、必要时先降维。KMeans 对初始中心很敏感，随机起手可能收进一个很差的局部解；

scikit-learn 默认改用 `k-means++` 挑分散的初始点，再用多次重启取最好（旧版 `n_init` 默认 10 次，1.2 起默认 `n_init='auto'`，由初始化策略决定重启次数）。

K 必须事先给定，常用手肘法看 SSE 随 K 下降的拐点，也可以配合轮廓系数 `s = (b-a)/max(a,b)`（a 是簇内平均距、b 是到最近其它簇的平均距，取值在 -1 到 1，越大越好）与业务可解释性一起定。

要记住 SSE 随 K 增大必然单调下降，单看它只会把 K 一路挑到最大。

```python
import math
pts = [(1, 2), (1, 4), (2, 3), (8, 8), (9, 8), (8, 9), (9, 9)]
def dist(a, b): return math.dist(a, b)
def kmeans(pts, centers, rounds=3):
    hist = []
    for r in range(rounds):
        groups = [[] for _ in centers]
        for p in pts:
            k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))
            groups[k].append(p)
        sse = sum(dist(p, centers[k]) ** 2 for k, g in enumerate(groups) for p in g)
        hist.append((r, round(sse, 2), [len(g) for g in groups]))
        centers = [(sum(x for x, y in g) / len(g), sum(y for x, y in g) / len(g)) if g else c
                   for g, c in zip(groups, centers)]
    return hist, centers
hist, centers = kmeans(pts, [(1, 2), (8, 8)])
for h in hist: print(h)
print('centers', [(round(a, 2), round(b, 2)) for a, b in centers])
```

<OutputBox title='主示例运行结果' output='(0, 10.0, [3, 4])\n(1, 4.67, [3, 4])\n(2, 4.67, [3, 4])\ncenters [(1.33, 3.0), (8.5, 8.5)]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import math\npts = [(1, 2), (1, 4), (2, 3), (8, 8), (9, 8), (8, 9), (9, 9)]\ndef dist(a, b): return math.dist(a, b)\ndef kmeans(pts, centers, rounds=3):\n    hist = []\n    for r in range(rounds):\n        groups = [[] for _ in centers]\n        for p in pts:\n            k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))\n            groups[k].append(p)\n        sse = sum(dist(p, centers[k]) ** 2 for k, g in enumerate(groups) for p in g)\n        hist.append((r, round(sse, 2), [len(g) for g in groups]))\n        centers = [(sum(x for x, y in g) / len(g), sum(y for x, y in g) / len(g)) if g else c\n                   for g, c in zip(groups, centers)]\n    return hist, centers\nhist, centers = kmeans(pts, [(1, 2), (8, 8)])\nfor h in hist: print(h)\nprint(&#39;centers&#39;, [(round(a, 2), round(b, 2)) for a, b in centers])' :notes='["导入 math 用 math.dist 计算欧氏距离", "七个二维点，明显分成左下与右上两团", "距离函数，KMeans 的分配步依赖它", "定义 Lloyd 迭代，centers 为初始簇心、rounds 为轮数", "hist 记录每轮的轮次、SSE 与各簇样本数", "外层循环交替执行分配步与更新步", "为每个簇准备一个空列表存该轮分配到的点", "把每个点分配到最近的簇心", "min 按距离选最近簇心下标，是分配步的核心", "把点加入对应簇", "距离平方求和得簇内平方和 SSE（inertia）", "记录本轮 SSE 与各簇大小，SSE 应单调不增", "更新步：簇心移到该簇所有点的均值，空簇保留原中心", "用 zip 把每簇与原中心配对，完成一次完整迭代", "返回历史轨迹与最终簇心", "用两个初始中心启动，观察三轮收敛过程", "逐轮打印 (轮次, SSE, 各簇样本数)", "打印最终簇心，读数应落在两团各自的中心附近"]' title='第 101 讲 · 无监督学习：KMeans、DBSCAN、PCA 与异常检测' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 标准化前后最近邻怎么变

```python
p, q, r = (0, 0), (1, 0), (0, 50)
print('d(p,q)', dist(p, q), 'd(p,r)', dist(p, r))
sp, sq, sr = [(x * 100, y) for x, y in (p, q, r)]
print('after x*100: d(p,q)', dist(sp, sq), 'd(p,r)', dist(sp, sr))
```

<OutputBox title='原理验证' output='d(p,q) 1.0 d(p,r) 50.0\nafter x*100: d(p,q) 100.0 d(p,r) 50.0' />

**KMeans / DBSCAN / PCA 对照**

| 方法 | 输入参数 | 输出 | 主要边界 |
| --- | --- | --- | --- |
| KMeans | K、初始中心 | K 个簇心 + 标签 | 假设球形等方差、需预设 K、怕离群点 |
| DBSCAN | eps、min_samples | 簇 + 噪声点 | 对 eps 敏感、密度不均/高维失效 |
| PCA | 保留成分数 | 低维投影 + 解释率 | 线性、组件无物理含义、需中心化 |
| 异常检测 | 分数阈值 | Top-N / 告警 | 阈值由业务容量定，需回测 |


## KMeans 的 Lloyd 迭代与 K 的选择

`DBSCAN` 换了一条路：按密度连通来划分，而不是围着一个中心转。它只要两个参数，`eps`（邻域半径）和 `min_samples`（成为核心点所需的邻域内最少样本数，计入自身）；样本因此分三类，核心点（eps 内至少 min_samples 个）、边界点（落在某个核心点邻域里、自己却不够核心）、噪声点（两者都不是）。

它不用预设 K，能认出任意形状的簇，顺手把离群点标成噪声；代价是对 `eps` 极敏感（可以用 k-distance 曲线的拐点来定），密度不均时表现差，高维下距离集中、`eps` 很难给。

PCA 走的则是有损线性降维：先把每个特征中心化（减去均值，否则第一主成分会被均值带偏），再对协方差矩阵做特征值分解，或等价地对中心化后的矩阵做 SVD，取最大特征值对应的正交方向作主成分；某个成分的方差解释率就是它的特征值占全部特征值之和的比例，累计解释率决定留几个成分，通常留到 85% 到 95%。

主成分只是原始特征的线性组合，符号还能整体翻转，本身没有天然的物理含义，把它叫成「忠诚度」「活跃度」属于越界解释；而在高维稀疏数据上直接算欧氏距离，还会因维度灾难让所有点对的距离趋同，得先标准化、降维，或改用余弦相似度。

<ConceptDiagram type='flow4' title='第 101 讲 · 聚类假设、尺度与 KMeans 迭代' labels='聚类假设、尺度与 KMeans 迭代|DBSCAN、密度与 PCA 的边界|异常检测与业务阈值|异常检测与业务阈值' caption='在没有标签时从结构里找信息' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### SSE 单调下降，手肘法与轮廓系数

```python
def sse_for_k(pts, centers):
    groups = [[] for _ in centers]
    for p in pts:
        k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))
        groups[k].append(p)
    return round(sum(dist(p, centers[k]) ** 2 for k, g in enumerate(groups) for p in g), 2)
print('K=1', sse_for_k(pts, [(4, 5)]))
print('K=2', sse_for_k(pts, [(1, 3), (8, 8)]))
print('K=3', sse_for_k(pts, [(1, 3), (8, 8), (9, 9)]))
```

<OutputBox title='对照写法：先自己猜，再点开' output='K=1 168.0\nK=2 7.0\nK=3 5.0' guess="true" />

**SSE 随 K 的变化（本讲数据）**

| K | SSE | 降幅 | 判读 |
| --- | --- | --- | --- |
| 1 | 168.0 | — | 全挤成一个簇 |
| 2 | 7.0 | -161.0 | 两团被分开，手肘在此 |
| 3 | 5.0 | -2.0 | 降幅骤减，继续加 K 收益很小 |


## DBSCAN 的密度、PCA 的方差解释与高维陷阱

无监督异常检测大致两条路：一类基于距离或密度，比如到 KMeans 簇心的最小距离、KNN 的第 k 近邻距离、`DBSCAN` 标出的噪声点、Isolation Forest 给出的异常分数；另一类基于重构误差，比如 PCA 的重构残差或自编码器。

它们吐出来的都是连续分数，不是现成标签，最后一步必须把分数翻译成能运营的阈值：取分数的分位数（如 99 分位）、用 IQR 围栏，或按「人工每天只能复核 N 条」反推 Top-N 阈值。阈值不是模型参数，而是业务复核容量与误报成本的函数——压低了告警成堆、复核成本上去，抬高了漏报变多。

评估也不能只数「检出了几个已知异常」，要抽样做人工复核看精确率、按时间回测看阈值有没有漂移，并把阈值、特征版本和分数分布一起记下来。无监督没有标准答案，最稳的流程是「标准化 → 用轮廓系数或重构误差筛出结构 → 业务抽样解释 → 把分数转成阈值并持续回测」，跳过任何一步，都可能得到一组数学上成立、业务上却没法用的簇。

<CodeTabs :tabs='[{"label": "主示例", "code": "import math\npts = [(1, 2), (1, 4), (2, 3), (8, 8), (9, 8), (8, 9), (9, 9)]\ndef dist(a, b): return math.dist(a, b)\ndef kmeans(pts, centers, rounds=3):\n    hist = []\n    for r in range(rounds):\n        groups = [[] for _ in centers]\n        for p in pts:\n            k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))\n            groups[k].append(p)\n        sse = sum(dist(p, centers[k]) ** 2 for k, g in enumerate(groups) for p in g)\n        hist.append((r, round(sse, 2), [len(g) for g in groups]))\n        centers = [(sum(x for x, y in g) / len(g), sum(y for x, y in g) / len(g)) if g else c\n                   for g, c in zip(groups, centers)]\n    return hist, centers\nhist, centers = kmeans(pts, [(1, 2), (8, 8)])\nfor h in hist: print(h)\nprint(&#39;centers&#39;, [(round(a, 2), round(b, 2)) for a, b in centers])", "note": "聚类假设、尺度与 KMeans 迭代"}, {"label": "对照 / 进阶", "code": "def sse_for_k(pts, centers):\n    groups = [[] for _ in centers]\n    for p in pts:\n        k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))\n        groups[k].append(p)\n    return round(sum(dist(p, centers[k]) ** 2 for k, g in enumerate(groups) for p in g), 2)\nprint(&#39;K=1&#39;, sse_for_k(pts, [(4, 5)]))\nprint(&#39;K=2&#39;, sse_for_k(pts, [(1, 3), (8, 8)]))\nprint(&#39;K=3&#39;, sse_for_k(pts, [(1, 3), (8, 8), (9, 9)]))", "note": "DBSCAN、密度与 PCA 的边界"}]' title='两种写法切换看' />

**尺度对最近邻的改变（本讲 probe）**

| 变换 | d(p,q) | d(p,r) | p 的最近邻 |
| --- | --- | --- | --- |
| 原始 | 1.0 | 50.0 | q |
| x 轴 ×100 | 100.0 | 50.0 | r（翻转） |

KMeans 最小化的簇内平方和，对每个簇中心 μ_k 求导并令其为零，解出来正是该簇所有点的均值，也就是 `μ_k = (1/|C_k|)Σx`；

分配步把点交给最近中心使 SSE 不增，更新步取均值又是该簇 SSE 的最小点，两步交替就是一次坐标下降，SSE 单调不增且下界为零，因此收敛到局部最优——但没人保证它是全局最优，这正是 `k-means++` 和多次 `n_init` 存在的理由。

欧氏距离按各维差值的平方累加，尺度大的那一维会主导距离：本讲 probe 把 x 轴乘 100，`d(p,q)` 从 1 变成 100、`d(p,r)` 仍是 50，p 的最近邻便从 q 翻成 r，整个聚类结构跟着变，所以标准化是聚类前绕不开的硬步骤。

PCA 对中心化后的数据矩阵 X 做 SVD，写成 `X = UΣVᵀ`，主成分是 V 的列，方差解释率等于对应奇异值平方占全部奇异值平方和的比例，几何上就是找一条让投影方差最大的正交方向；主成分是原始特征的线性组合、符号还能整体翻转，自然谈不上固定语义。

`DBSCAN` 则用密度可达来定义簇，顺带把低密度点标成噪声，异常识别是它的副产品。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 不同量纲直接聚类，换单位结果就翻一遍 | 欧氏距离按差值平方累加，大尺度列主导，SSE 与簇归属被单位而非结构决定 | 先对每列做 z-score 标准化，必要时处理离群点或先降维，再跑 KMeans/DBSCAN |
| 只按 SSE 最小挑最大的 K | SSE 随 K 增大必然单调下降，K=n 时为 0，但那只是把每个点当一簇，毫无泛化 | 用手肘法看降幅拐点，配合轮廓系数与业务抽样共同定 K |
| 把 PCA 主成分命名成业务因子、在高维稀疏数据直接算欧氏距离 | 主成分是线性组合、符号可翻转，无天然语义；高维下距离集中使近邻失效 | 主成分只作降维与可视化线索，解释回到原始特征；高维稀疏数据先标准化、降维或改余弦相似度 |


### 主成分为什么不能命名成业务因子

<Callout type="warn" title='本讲最容易踩的坑' text='不同量纲直接聚类，换单位结果就翻一遍：欧氏距离按差值平方累加，大尺度列主导，SSE 与簇归属被单位而非结构决定' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：不同量纲直接聚类，换单位结果就翻一遍", "body": "欧氏距离按差值平方累加，大尺度列主导，SSE 与簇归属被单位而非结构决定", "tip": "先对每列做 z-score 标准化，必要时处理离群点或先降维，再跑 KMeans/DBSCAN"}, {"title": "第 2 步：只按 SSE 最小挑最大的 K", "body": "SSE 随 K 增大必然单调下降，K=n 时为 0，但那只是把每个点当一簇，毫无泛化", "tip": "用手肘法看降幅拐点，配合轮廓系数与业务抽样共同定 K"}, {"title": "第 3 步：把 PCA 主成分命名成业务因子、在高维稀疏…", "body": "主成分是线性组合、符号可翻转，无天然语义；高维下距离集中使近邻失效", "tip": "主成分只作降维与可视化线索，解释回到原始特征；高维稀疏数据先标准化、降维或改余弦相似度"}]' />


## 把异常分数转成可运营的阈值

无监督异常检测里，最容易被轻视的恰恰是最后一步：模型只给一串连续分数，能不能上线，全看阈值怎么定。稳妥的做法是「标准化 → 用簇心距离算分数 → 按分位数与人工容量反推阈值 → 抽样复核并持续回测」。

下面用纯标准库写一个自洽的最小管道：`kmeans` 先得到两个簇心，每个样本到最近簇心的距离就是异常分数，取分数的上四分位乘一个系数当阈值，再把分数、阈值和被标记的样本逐项打印出来。它要说明的是，阈值不是模型参数，而是业务复核容量与误报成本的函数。

搬到真实项目时，把 `kmeans` 换成 `MiniBatchKMeans`、把距离分数换成 `IsolationForest` 的 `score_samples` 即可，但要注意后者取值越低越异常，方向与「距离越大越异常」相反，取 Top-N 时得按升序挑；

最后仍按「每天人工复核 50 条」把阈值反推成 Top-N，结构不变。

```python
import math

pts = [(1, 2), (1, 4), (2, 3), (8, 8), (9, 8), (8, 9), (9, 9), (50, 50)]
def dist(a, b): return math.dist(a, b)

def kmeans(pts, centers, rounds=5):
    for _ in range(rounds):
        groups = [[] for _ in centers]
        for p in pts:
            k = min(range(len(centers)), key=lambda i: dist(p, centers[i]))
            groups[k].append(p)
        centers = [(sum(x for x, y in g) / len(g), sum(y for x, y in g) / len(g)) if g else c
                   for g, c in zip(groups, centers)]
    return centers

centers = kmeans(pts, [(1, 2), (8, 8)])
scores = [round(min(dist(p, c) for c in centers), 2) for p in pts]
srt = sorted(scores)
q3 = srt[int(len(srt) * 0.75)]
thr = round(q3 * 1.5 + 0.5, 2)
flagged = [p for p, s in zip(pts, scores) if s > thr]
print('centers', [(round(a, 1), round(b, 1)) for a, b in centers])
print('scores', scores)
print('threshold', thr, 'flagged', flagged)
```

<Callout type="idea" title='落地提示' text='先标准化、用轮廓系数与业务抽样共同评估，异常分数转成可运营的阈值并持续回测' />

<CheckList id='P101b' title='上线前自检' :items='["能复现并解释「不同量纲直接聚类，换单位结果就翻一遍」", "能复现并解释「只按 SSE 最小挑最大的 K」", "能复现并解释「把 PCA 主成分命名成业务因子、在高维稀疏数据直接算欧氏距…」", "能用一条命令验证 聚类假设与尺度", "关键路径有自动化测试与失败分支"]' />


## 练习、自测与阈值速记

<Exercise title='基础：手算一轮 Lloyd 迭代' task='给定 pts 与初始中心 [(1,2),(8,8)]，写出分配步后各簇成员与 SSE，说明为什么更新步把中心取均值能让 SSE 不增。' solution='import math\npts=[(1,2),(1,4),(2,3),(8,8),(9,8),(8,9),(9,9)]\nc=[(1,2),(8,8)]\ng=[[],[]]\nfor p in pts:\n    k=min(range(2),key=lambda i: math.dist(p,c[i])); g[k].append(p)\nprint(&#39;sizes&#39;,[len(x) for x in g])\nprint(&#39;sse&#39;,round(sum(math.dist(p,c[k])**2 for k,x in enumerate(g) for p in x),2))' explain='分配步给最近中心使 SSE 不增；对固定分配，SSE 对 μ_k 求导为零的解正是簇均值，所以更新步取均值是该簇的最小点，两步交替保证整体单调下降。' />

<Exercise title='进阶：用轮廓系数思路评估 K' task='简述轮廓系数 s=(b-a)/max(a,b) 中 a、b 的含义，并说明为什么不能只凭 SSE 单调下降挑最大的 K。' solution='def outline_note():\n    return (&#39;a = 同簇其它点的平均距离&#39;,\n            &#39;b = 到最近其它簇所有点的平均距离&#39;,\n            &#39;s=(b-a)/max(a,b), 取值 -1..1, 越大越好&#39;)\nprint(outline_note())' explain='a 是簇内紧密度、b 是簇间分离度，s 把两者合并；SSE 随 K 增大必然单调下降、K=n 时为 0 却毫无意义，因此要用拐点、轮廓系数与业务可解释性共同选 K。' />

<Quiz no='101-1' q='两个特征量纲相差几个数量级，直接跑 KMeans 会怎样？' :options='["大尺度特征主导欧氏距离，聚类结果几乎只按它划分", "两特征等量贡献", "自动按方差归一化", "抛出异常提示尺度不一致"]' answer="0" explain='欧氏距离按各维差值平方累加，量纲大的列贡献压倒其它列；换单位结果都可能翻转，标准化是聚类前的硬要求。' />

<Quiz no='101-2' q='关于 PCA 主成分，下面哪项准确？' :options='["它是方差最大的正交方向，是原始特征的线性组合，没有天然业务含义", "每个主成分对应一个明确的业务因子", "符号固定不可翻转", "保留成分越多一定越好"]' answer="0" explain='PCA 对中心化数据做特征值分解或 SVD，主成分是使投影方差最大的正交方向、原始特征的线性组合，符号可整体翻转，因此不能直接命名成业务因子。' />

<Quiz no='101-3' q='DBSCAN 相比 KMeans 的一个关键优势是？' :options='["不必预设 K、能识别任意形状簇并把低密度点标为噪声", "一定比 KMeans 快", "完全不受 eps 影响", "在高维稀疏数据上更稳定"]' answer="0" explain='DBSCAN 按密度可达定义簇，天然输出噪声点、簇形状不限；但它对 eps 敏感、密度不均或高维距离集中时反而失效。' />

<Predict no='101-4' q='前面 probe 把 x 轴乘 100 后，p 的最近邻变成哪个点？' :options='["r", "q", "两者等距"]' answer='0' output='after x*100: d(p,q) 100.0 d(p,r) 50.0' explain='原始时 d(p,q)=1.0、d(p,r)=50.0，最近邻是 q；x 轴乘 100 后 d(p,q)=100.0、d(p,r)=50.0，最近邻翻转成 r，证明尺度会改变聚类结构。' />

<KnowledgeCard :points='["KMeans 最小化簇内平方和，Lloyd 两步交替使 SSE 单调不增，但只收敛到局部最优", "三条隐含假设：球形簇、大小与方差相近、各维同等重要；标准化与离群点处理是前置步骤", "`k-means++` 加多次 `n_init` 缓解初始中心敏感；K 用手肘法配合轮廓系数 `s = (b-a)/max(a,b)` 定", "DBSCAN 靠 `eps` 与 `min_samples` 按密度连通，不预设 K、能标噪声，但对密度与维度敏感", "PCA 主成分是方差最大的正交方向，符号可翻转、无天然语义；累计方差解释率决定保留几个成分", "异常分数要转成业务阈值，按分位数、IQR 或人工容量反推 Top-N，并抽样复核、按时间回测"]' :pitfalls='["不同量纲直接聚类，换单位结果就翻一遍", "只按 SSE 最小挑最大的 K", "把 PCA 主成分命名成业务因子、在高维稀疏数据直接算欧氏距离", "把 PCA 主成分当成有明确物理含义的因子，或在高维稀疏数据上直接算欧氏距离，结论往往站不住"]' summary='无监督结果没有「标准答案」，评价高度依赖业务解释与尺度选择；不同量纲会彻底改变聚类结果' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| KMeans 最小化簇内平方和，Lloyd 两步交替使 SSE 单调不增，但只收敛到局部最优 | 建立直觉 |
| 三条隐含假设：球形簇、大小与方差相近、各维同等重要；标准化与离群点处理是前置步骤 | 跑通示例 |
| `k-means++` 加多次 `n_init` 缓解初始中心敏感；K 用手肘法配合轮廓系数 `s = (b-a)/max(a,b)` 定 | 深入边界 |
| DBSCAN 靠 `eps` 与 `min_samples` 按密度连通，不预设 K、能标噪声，但对密度与维度敏感 | 工程落地 |
| PCA 主成分是方差最大的正交方向，符号可翻转、无天然语义；累计方差解释率决定保留几个成分 | 随堂检测 |
| 异常分数要转成业务阈值，按分位数、IQR 或人工容量反推 Top-N，并抽样复核、按时间回测 | 复盘 |

1. KMeans 最小化簇内平方和，Lloyd 两步交替使 SSE 单调不增，但只收敛到局部最优

2. 三条隐含假设：球形簇、大小与方差相近、各维同等重要；标准化与离群点处理是前置步骤

3. `k-means++` 加多次 `n_init` 缓解初始中心敏感；K 用手肘法配合轮廓系数 `s = (b-a)/max(a,b)` 定

[下一讲：模型调优：交叉验证、正则化与过拟合](/data-ai/model-tuning)

<FillBlank no='101-5' tpl='___ math' :answers='["import"]' hint='回想本讲关于 聚类假设与尺度 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 聚类假设、尺度与 KMeans 迭代 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/101-unsupervised.py`

```bash
python3 examples/lessons/101-unsupervised.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/101-unsupervised.py) · [全部示例代码索引](/examples/)
