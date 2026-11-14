---
title: 第 098 讲 · 经典算法：KNN、线性与逻辑回归
description: 从最简模型理解偏差方差与优化
---

<StageHeader stage='L9 · 数据与 AI' level='★★★☆☆' time='40 分钟' goal='从最简模型理解偏差方差与优化' prereq='第 097 讲 · 机器学习流程：特征、划分与评价' />

# 第 098 讲 · 经典算法：KNN、线性与逻辑回归

流程立住之后，终于可以往里放第一个模型。面对『这套房大概值多少』，稳妥的开场不是黑箱，而是先用几行能解释清楚的直线或近邻，把损失、优化和偏差方差看明白。经典算法值得先讲，因为每一步都摊得开，往后遇到复杂模型才有对照。

从 KNN 与距离度量入手，说清不缩放特征时量纲大的列怎样独霸结果；再到最小二乘与梯度下降，看多项式回归次数一高怎样把噪声也背下来；最后走到逻辑回归与决策边界，用 L1、L2 正则收住复杂度。需要上一讲的数据集划分、Pipeline 和 NumPy 向量化。做完这一讲，你能跑通并讲清一个可解释基线，也判断得出何时才需要更重的模型。


## 两个特征量纲差几个数量级，KNN 直接判错

一个流失预测模型用两个特征：用户年龄（20 到 70）和账户余额（0 到 50 万），KNN 上线后几乎把所有人都判成同一类，业务方说『年龄明明是最强的信号，模型却像没看见』。把距离拆开一看就明白了：欧氏距离里余额 5000 的差值是几千，年龄 5 岁的差值是 5，前者比后者大三个数量级，年龄这个真正有判别力的特征被彻底淹没。

另一处事故是有人用梯度下降拟合线性回归，学习率拍成 0.1，损失从几万涨到天文数字，最后溢出成 inf。朴素解法『把特征直接丢进模型』失败在尺度没有统一，『线性模型太简单换复杂模型』则错过了理解损失、优化与正则的最佳入口。

本讲用纯 Python 把 KNN、最小二乘、梯度下降、逻辑回归与 L1/L2 全部跑通，让每个结论都有可核对的数字。

<Callout type="warn" title='先看一个真实会出错的写法' text='KNN / 梯度下降不缩放，结果被大尺度特征主导或收敛极慢：欧氏距离与平方损失都按数值平方累加，量纲大的列贡献压倒其它列，且条件数变大' />


## KNN 与距离度量：最近邻由谁决定

KNN 是惰性学习：没有显式的训练阶段，预测时才计算测试点到所有训练点的距离，取距离最小的 k 个邻居投票（分类取多数类）或平均（回归），因此训练是 `O(1)`、单次预测是 `O(n*d)`，n 是样本数、d 是特征数，大数据要靠 KD-tree 或 Ball-tree 加速，但维度升高后这类索引会退化到接近线性扫描，这就是维度灾难。

距离度量有欧氏距离（L2，`math.dist` 默认）、曼哈顿距离（L1）、闵可夫斯基距离（Lp）与余弦相似度；除余弦外都对特征的绝对尺度敏感。k 是偏差方差的旋钮：k 太小则决策边界锯齿、被单个噪声点带偏（高方差），k 太大则边界过度平滑、把小类吞掉（高偏差），通常用交叉验证选，并取奇数避免二分类平票。

特征缩放是硬要求：标准化 `z=(x-mean)/std` 把各列变成均值 0、方差 1，归一化把值压到 [0,1]。不缩放时，量纲大的列在距离平方和里占绝对主导，同时把损失函数的等高线拉成狭长椭圆，梯度下降会在窄方向来回震荡、收敛极慢；缩放后等高线接近圆形，才能用更大的学习率。

加权 KNN 用距离倒数给近邻更大话语权，能缓解 k 固定带来的粗糙。

```python
import math

def knn_predict(train, labels, q, k=3):
    dists = []
    for row, lab in zip(train, labels):
        dists.append((math.dist(row, q), lab))
    dists.sort()
    votes = {}
    for _, lab in dists[:k]:
        votes[lab] = votes.get(lab, 0) + 1
    return max(votes, key=votes.get)

train = [[0.1, 100], [0.2, 9000], [0.15, 300], [0.9, 8000], [0.8, 200], [0.85, 9500]]
labels = ['A', 'A', 'A', 'B', 'B', 'B']
q = [0.12, 5000]
print('raw', knn_predict(train, labels, q))
cols = list(zip(*train))
means = [sum(c) / len(c) for c in cols]
stds = [(sum((x - m) ** 2 for x in c) / len(c)) ** 0.5 for m, c in zip(means, cols)]
def scale(row):
    return [(x - m) / s for x, m, s in zip(row, means, stds)]
strain = [scale(r) for r in train]
print('scaled', knn_predict(strain, labels, scale(q)))
```

<OutputBox title='主示例运行结果' output='raw B\nscaled A' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import math\n\ndef knn_predict(train, labels, q, k=3):\n    dists = []\n    for row, lab in zip(train, labels):\n        dists.append((math.dist(row, q), lab))\n    dists.sort()\n    votes = {}\n    for _, lab in dists[:k]:\n        votes[lab] = votes.get(lab, 0) + 1\n    return max(votes, key=votes.get)\n\ntrain = [[0.1, 100], [0.2, 9000], [0.15, 300], [0.9, 8000], [0.8, 200], [0.85, 9500]]\nlabels = [&#39;A&#39;, &#39;A&#39;, &#39;A&#39;, &#39;B&#39;, &#39;B&#39;, &#39;B&#39;]\nq = [0.12, 5000]\nprint(&#39;raw&#39;, knn_predict(train, labels, q))\ncols = list(zip(*train))\nmeans = [sum(c) / len(c) for c in cols]\nstds = [(sum((x - m) ** 2 for x in c) / len(c)) ** 0.5 for m, c in zip(means, cols)]\ndef scale(row):\n    return [(x - m) / s for x, m, s in zip(row, means, stds)]\nstrain = [scale(r) for r in train]\nprint(&#39;scaled&#39;, knn_predict(strain, labels, scale(q)))' :notes='["导入 math 使用 math.dist 计算欧氏距离", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 KNN 预测函数，k 默认 3，惰性学习无训练阶段", "dists 收集每个训练点到查询点的距离与标签", "逐条计算距离，特征未缩放时大尺度列主导差值", "math.dist 默认 L2 欧氏距离，对绝对尺度敏感", "按距离升序排序，最近的排在最前", "votes 统计 k 个近邻里各类别票数", "只取前 k 个近邻参与投票", "累加类别票数，多数类胜出", "返回票数最多的类别，等价于多数表决", "空行，只用于分隔逻辑块，不影响执行结果。", "第一列是有判别力的小尺度特征、第二列是大尺度噪声", "前三条为 A 类、后三条为 B 类，仅第一列真正区分类别", "查询点第一列 0.12 明显属 A，第二列 5000 却更靠 B", "未缩放时距离被第二列主导，预测被带偏成 B", "按列转置，准备逐列计算均值与标准差", "每列均值，标准化 z=(x-均值)/标准差 的分子", "每列总体标准差，作为缩放的分母", "定义标准化函数，让两列等权参与距离", "逐列做 z-score，尺度差异被消除", "对训练集整体做同样的标准化", "对查询点用训练集的参数标准化后再预测，结果回到 A"]' title='第 098 讲 · 经典算法：KNN、线性与逻辑回归' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 特征缩放：z-score 之后近邻为什么变了

```python
w, lr, lam = 0.8, 0.1, 0.5
w2 = [0.8]
w1 = [0.8]
for _ in range(10):
    w2.append(w2[-1] * (1 - lr * lam))
    v = w1[-1] - lr * lam
    w1.append(max(0.0, v) if v > 0 else 0.0)
print('L2 after 10', round(w2[-1], 4))
print('L1 after 10', round(w1[-1], 4))
```

<OutputBox title='原理验证' output='L2 after 10 0.479\nL1 after 10 0.3' />

<Compare :panels='[{"label": "主示例", "code": "import math\n\ndef knn_predict(train, labels, q, k=3):\n    dists = []\n    for row, lab in zip(train, labels):\n        dists.append((math.dist(row, q), lab))\n    dists.sort()\n    votes = {}\n    for _, lab in dists[:k]:\n        votes[lab] = votes.get(lab, 0) + 1\n    return max(votes, key=votes.get)\n\ntrain = [[0.1, 100], [0.2, 9000], [0.15, 300], [0.9, 8000], [0.8, 200], [0.85, 9500]]\nlabels = [&#39;A&#39;, &#39;A&#39;, &#39;A&#39;, &#39;B&#39;, &#39;B&#39;, &#39;B&#39;]\nq = [0.12, 5000]\nprint(&#39;raw&#39;, knn_predict(train, labels, q))\ncols = list(zip(*train))\nmeans = [sum(c) / len(c) for c in cols]\nstds = [(sum((x - m) ** 2 for x in c) / len(c)) ** 0.5 for m, c in zip(means, cols)]\ndef scale(row):\n    return [(x - m) / s for x, m, s in zip(row, means, stds)]\nstrain = [scale(r) for r in train]\nprint(&#39;scaled&#39;, knn_predict(strain, labels, scale(q)))", "note": "KNN、距离度量与特征缩放"}, {"label": "对照 / 进阶", "code": "xs = [1, 2, 3, 4, 5]\nys = [2, 4, 5, 4, 5]\ndef mse(w, b): return sum((w * x + b - y) ** 2 for x, y in zip(xs, ys)) / len(xs)\nmx, my = sum(xs) / 5, sum(ys) / 5\nw = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)\nb = my - w * mx\nprint(&#39;closed&#39;, round(w, 3), round(b, 3), round(mse(w, b), 3))\nwg, bg, lr = 0.0, 0.0, 0.05\nfor _ in range(2000):\n    dw = sum(2 * (wg * x + bg - y) * x for x, y in zip(xs, ys)) / 5\n    db = sum(2 * (wg * x + bg - y) for x, y in zip(xs, ys)) / 5\n    wg -= lr * dw; bg -= lr * db\nprint(&#39;gd&#39;, round(wg, 3), round(bg, 3), round(mse(wg, bg), 3))", "note": "最小二乘、梯度下降与多项式过拟合"}]' title='两种写法对照' note='差异集中在 KNN 与距离度量；先看输出，再找背后的规则。' />


## 最小二乘：从损失到闭式解

线性回归假设输出是各个特征的线性组合再加一个偏置，用平方损失 `L=sum((y-yhat)^2)/(2n)` 衡量误差。

它有闭式解：正规方程对 X 的转置乘 X 求逆、再乘 X 的转置与 y，一步得到全局最优，代价是求逆约 `O(d^3)` 加构造 XᵀX 的 `O(n*d^2)`；特征维度高或存在多重共线性时 XᵀX 接近奇异、解不稳定，这时改用梯度下降或加正则。

梯度下降按 w 减去学习率乘梯度迭代，梯度是 X 的转置乘 (Xw 减 y) 再除以 n；

学习率有收敛上界，平方损失下要求它小于 2 除以 (1/n)XᵀX 的最大特征值，超过就会震荡并放大误差——实测在 `xs=1..5` 这个问题上 `eta=0.1` 跑 30 轮损失就涨到 2.17e9 量级，而 `eta=0.05` 跑 2000 轮能收敛到闭式解的 `w=0.6`、`b=2.2`。

批量 GD 用全量算梯度、随机 GD 每次一个样本、小批量折中，是深度学习优化器的原型。多项式回归把 x 扩成 [x, x², …, xᵈ] 来拟合非线性，次数 d 越高训练误差越小，但验证误差先降后升：高次项把噪声也记住了，这是偏差方差权衡最直观的演示。

线性模型的价值不只在预测，更在可解释性——系数直接表示『其余特征固定时，该特征每增一个单位对 y 的影响』，是任何复杂模型之前必须建立的基线。

<Callout type="tip" title='核心心智模型' text='KNN 是惰性学习：没有显式的训练阶段，预测时才计算测试点到所有训练点的距离，取距离最小的 k 个邻居投票（分类取多数类）或平均（回归），因此训练是 `O(1)`、单次预测是 `O(n*d)`，n 是样本数、d 是特征数，大数据要靠 KD-tree 或 Ball-tree 加速，但维度升高后这类索引…' />


## 梯度下降：学习率与收敛的临界点

```python
xs = [1, 2, 3, 4, 5]
ys = [2, 4, 5, 4, 5]
def mse(w, b): return sum((w * x + b - y) ** 2 for x, y in zip(xs, ys)) / len(xs)
mx, my = sum(xs) / 5, sum(ys) / 5
w = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
b = my - w * mx
print('closed', round(w, 3), round(b, 3), round(mse(w, b), 3))
wg, bg, lr = 0.0, 0.0, 0.05
for _ in range(2000):
    dw = sum(2 * (wg * x + bg - y) * x for x, y in zip(xs, ys)) / 5
    db = sum(2 * (wg * x + bg - y) for x, y in zip(xs, ys)) / 5
    wg -= lr * dw; bg -= lr * db
print('gd', round(wg, 3), round(bg, 3), round(mse(wg, bg), 3))
```

<OutputBox title='对照写法：先自己猜，再点开' output='closed 0.6 2.2 0.48\ngd 0.6 2.2 0.48' guess="true" />

**三个模型的机制与适用边界**

| 模型 | 损失/准则 | 是否需缩放 | 可解释性 |
| --- | --- | --- | --- |
| KNN | 距离 + k 近邻投票 | 是，距离对尺度极敏感 | 低，靠邻居举例 |
| 线性回归 | 平方损失，可闭式解 | 梯度下降求解时需要 | 高，系数即边际影响 |
| 逻辑回归 | 交叉熵 + sigmoid | 建议做，利收敛 | 高，e^w 是优势比 |
| 多项式回归 | 平方损失 + 高次特征 | 是，高次项放大尺度 | 中，次数高易过拟合 |


## 多项式次数越加越高，训练集满分线上很差

**L1 与 L2 正则对照**

| 维度 | L1 (Lasso) | L2 (Ridge) |
| --- | --- | --- |
| 惩罚项 | λ·Σ\|w\| | λ·Σw² |
| 梯度附加 | λ·sign(w) | 2λ·w |
| 权重结果 | 部分恰好为 0，产生稀疏解 | 整体缩小，一般不为 0 |
| 主要用途 | 特征选择 | 抑制共线性与过拟合 |
| 10 步衰减(本讲 probe) | 0.8 线性减到 0.3 | 0.8 指数衰减到 0.479 |

<Callout type="warn" title='本讲最容易踩的坑' text='KNN / 梯度下降不缩放，结果被大尺度特征主导或收敛极慢：欧氏距离与平方损失都按数值平方累加，量纲大的列贡献压倒其它列，且条件数变大' />


## 逻辑回归与 sigmoid 决策边界

逻辑回归名字带回归，实际是二分类：把线性得分 z 送进 `sigmoid(z)=1/(1+exp(-z))` 映射到 (0,1) 当概率，损失用交叉熵（对数损失）`L=-(y*log(p)+(1-y)*log(1-p))`，不能再套平方损失，因为 sigmoid 之后平方损失对 w 非凸、且饱和区梯度趋近 0 会让训练停滞。

决策边界是令线性得分为零的超平面，默认阈值 0.5 可按业务代价下调（保召回）或上调（保精确）。

scikit-learn 的 `LogisticRegression` 默认就带 L2 正则，参数 C 是正则强度的倒数：C 越小正则越强、系数越收缩，C 越大越接近无约束拟合；

`LinearRegression` 不带正则，Ridge、Lasso、ElasticNet 是独立估计器。

L2（Ridge）在损失里加 λ 乘权重平方和，梯度多出 `2*lambda*w`，让权重按比例整体缩小但一般不为 0；L1（Lasso）加 λ 乘权重绝对值之和，绝对值在 0 处不可导，最优解容易正好落在 0，于是产生稀疏解、顺带完成特征选择；ElasticNet 用两者的线性组合兼顾稳定与稀疏。λ 由交叉验证选。

可解释性上，逻辑回归系数取指数 `exp(w)` 就是优势比（odds ratio）：某特征加一单位，事件发生的赔率乘以这个数，这是它比黑箱模型更适合风控、医疗等场景的原因。

<ConceptDiagram type='hub4' title='第 098 讲 · KNN、距离度量与特征缩放' labels='KNN、距离度量与特征缩放|最小二乘、梯度下降与多项式过拟合|逻辑回归、决策边界与 L1/L2 正则|可解释性' caption='从最简模型理解偏差方差与优化' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## L1 与 L2 正则：稀疏解还是平滑解

**学习率与收敛（xs=1..5 实测）**

| 学习率 | 轮数 | 结果 |
| --- | --- | --- |
| 0.05 | 2000 | 收敛到 w=0.6、b=2.2、mse=0.48 |
| 0.1 | 30 | 损失涨到 2.17e9 量级并继续发散 |
| 0.1 | 200 | 溢出为 inf 级别，权重达 1e27 |

平方损失对 w 是二次函数，其 Hessian 为 (2/n)XᵀX，正定且特征值决定曲率。

梯度下降的收敛条件是 0 小于 η 小于 2 除以最大特征值，一旦越过上界，沿大曲率方向的迭代矩阵 `|1-eta*lambda|>1`，误差逐轮指数放大，这就是 `eta=0.1` 在本讲数据上 30 轮涨到 2.17e9 的原因。

特征未缩放时 XᵀX 的条件数（最大特征值除以最小特征值）很大，等高线呈狭长椭圆，可取的 η 被最小的稳定步长卡住，只能配合大量迭代慢慢走；标准化把各列方差拉平、条件数接近 1，才能在较大 η 下快速收敛。KNN 的距离平方里，量纲大的列贡献与数值平方成正比，所以判别力会被尺度而非信息量决定。

正则化改写目标为损失加 λ 乘 `R(w)`：L2 的 R 是光滑二次项，最优解满足 w 等于 (XᵀX 加 λI) 求逆再乘 Xᵀy，只是把权重整体收缩；L1 的 R 在 0 处有尖点，次梯度条件使一部分系数恰好取 0，从而产生稀疏性。逻辑回归用交叉熵配合 sigmoid，是因为它给出凸的、梯度不会过早饱和的目标。


## 平方损失、条件数与优化几何

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| KNN / 梯度下降不缩放，结果被大尺度特征主导或收敛极慢 | 欧氏距离与平方损失都按数值平方累加，量纲大的列贡献压倒其它列，且条件数变大 | 训练前对每列做 z-score 标准化或 [0,1] 归一化，并把同样的参数用于验证与线上推理 |
| 学习率设得过大，损失震荡溢出成 inf | η 超过 2/λ_max 时迭代矩阵谱半径大于 1，误差逐轮指数放大 | 先用较小学习率（如 0.05）或做学习率搜索，监控损失是否单调下降；必要时先标准化特征 |
| 多项式回归次数越加越高，训练集满分线上很差 | 高次项把噪声也拟合进去，方差急剧增大，属于典型过拟合 | 用验证曲线选次数，加 L2 正则或限制次数，先与线性基线比较增益再决定 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：KNN / 梯度下降不缩放，结果被大尺度特征…", "body": "欧氏距离与平方损失都按数值平方累加，量纲大的列贡献压倒其它列，且条件数变大", "tip": "训练前对每列做 z-score 标准化或 [0,1] 归一化，并把同样的参数用于验证与线上推理"}, {"title": "第 2 步：学习率设得过大，损失震荡溢出成 inf", "body": "η 超过 2/λ_max 时迭代矩阵谱半径大于 1，误差逐轮指数放大", "tip": "先用较小学习率（如 0.05）或做学习率搜索，监控损失是否单调下降；必要时先标准化特征"}, {"title": "第 3 步：多项式回归次数越加越高，训练集满分线上很差", "body": "高次项把噪声也拟合进去，方差急剧增大，属于典型过拟合", "tip": "用验证曲线选次数，加 L2 正则或限制次数，先与线性基线比较增益再决定"}]' />


## 流失预测基线：把缩放固化进推理管道

一个二分类基线最容易被忽略的是『训练与推理用同一套缩放参数』：如果训练时标准化、线上却用原始值，或每次请求单独算均值方差，预测都会漂移。稳妥做法是把标准化函数、KNN 分类器与一组固定查询打包成一个可复跑的模块，缩放参数只在训练数据上算一次并随模型一起保存。

下面用纯标准库实现这条管道：`standardize` 返回变换后的训练集与两列参数，`knn` 做距离投票，`transform` 让每条查询复用同一组参数，最后对三条查询批量给出类别。

真实项目把 standardize 换成 sklearn 的 `StandardScaler` 并放进 `Pipeline`、把 knn 换成 `KNeighborsClassifier`，口径不变——关键是 fit 只发生在训练集，推理只做 transform。

```python
import math

def standardize(rows):
    cols = list(zip(*rows))
    means = [sum(c) / len(c) for c in cols]
    stds = [(sum((x - m) ** 2 for x in c) / len(c)) ** 0.5 or 1.0
           for m, c in zip(means, cols)]
    out = [[(x - m) / s for x, m, s in zip(r, means, stds)] for r in rows]
    return out, means, stds

def knn(train, labels, q, k=3):
    d = sorted((math.dist(row, q), lab) for row, lab in zip(train, labels))
    votes = {}
    for _, lab in d[:k]:
        votes[lab] = votes.get(lab, 0) + 1
    return max(votes, key=votes.get)

raw = [[0.1, 100], [0.2, 9000], [0.15, 300], [0.9, 8000], [0.8, 200], [0.85, 9500]]
labels = ['A', 'A', 'A', 'B', 'B', 'B']
train, means, stds = standardize(raw)
def transform(r): return [(x - m) / s for x, m, s in zip(r, means, stds)]
queries = [[0.12, 5000], [0.88, 7000], [0.5, 4500]]
print('predictions', [knn(train, labels, transform(q)) for q in queries])
```

<Callout type="idea" title='落地提示' text='先用线性模型建立基线与可解释性，复杂模型只有在指标确有增益且成本可接受时才上' />

<CheckList id='P098b' title='上线前自检' :items='["能复现并解释「KNN / 梯度下降不缩放，结果被大尺度特征主导或收敛极慢」", "能复现并解释「学习率设得过大，损失震荡溢出成 inf」", "能复现并解释「多项式回归次数越加越高，训练集满分线上很差」", "能用一条命令验证 KNN 与距离度量", "关键路径有自动化测试与失败分支"]' />


## 练习与速记：缩放、学习率与正则

<Exercise title='基础：实现标准化并验证近邻变化' task='对 code 里的 train 计算逐列均值与标准差，说明为什么未缩放时查询点 q 被判成 B、缩放后判成 A，并写出缩放后的第一列近似值。' solution='train = [[0.1,100],[0.2,9000],[0.15,300],[0.9,8000],[0.8,200],[0.85,9500]]\ncols = list(zip(*train))\nmeans = [sum(c)/len(c) for c in cols]\nstds = [(sum((x-m)**2 for x in c)/len(c))**0.5 for m,c in zip(means,cols)]\nq = [0.12, 5000]\nprint(&#39;means&#39;, [round(m,2) for m in means])\nprint(&#39;scaled q&#39;, [round((x-m)/s,2) for x,m,s in zip(q,means,stds)])' explain='未缩放时第二列差值以千计、第一列差值只有零点几，距离被余额主导；标准化后两列同量纲，第一列 0.12 明显靠近 A 类的 0.1 到 0.2，近邻改成 A 类，预测翻转为 A。' />

<Exercise title='进阶：用数值实验找出学习率发散临界点' task='对 xs=1..5、ys=[2,4,5,4,5]，分别用 lr=0.05、0.08、0.1 跑 200 轮，打印最终 mse，解释为什么 0.1 会发散。' solution='xs=[1,2,3,4,5]; ys=[2,4,5,4,5]\ndef run(lr):\n    w=b=0.0\n    for _ in range(200):\n        dw=sum(2*(w*x+b-y)*x for x,y in zip(xs,ys))/5\n        db=sum(2*(w*x+b-y) for x,y in zip(xs,ys))/5\n        w-=lr*dw; b-=lr*db\n    return round(sum((w*x+b-y)**2 for x,y in zip(xs,ys))/5,3)\nfor lr in (0.05,0.08,0.1): print(lr, run(lr))' explain='收敛上界是 η &lt; 2/λ_max，本问题约 0.0845；0.05 与 0.08 收敛，0.1 越界后迭代矩阵谱半径大于 1，误差指数放大。' />

<Quiz no='098-1' q='两个特征分别是 0 到 1 的评分与 0 到 50 万的余额，直接跑欧氏距离 KNN 会怎样？' :options='["余额主导距离，评分这个强信号几乎不起作用", "两特征等量贡献", "自动按信息量加权", "抛异常提示尺度不一致"]' answer="0" explain='欧氏距离按各维差值的平方累加，量纲大的余额贡献是评分的几个数量级，距离几乎只反映余额，因此必须先做标准化。' />

<Quiz no='098-2' q='关于逻辑回归，下面哪项准确？' :options='["用 sigmoid 映射概率、交叉熵作损失，系数取指数是优势比", "用平方损失训练最合适", "决策边界一定是曲线", "L1 正则让所有权重整体缩小且不为 0"]' answer="0" explain='逻辑回归是 sigmoid + 交叉熵的凸问题，决策边界是线性超平面；e^w 是优势比。L1 产生稀疏（部分为 0），L2 才是整体收缩。' />

<Quiz no='098-3' q='L1 与 L2 正则对权重的关键区别是？' :options='["L1 因绝对值在 0 处不可导易产生稀疏解，L2 让权重平滑缩小", "L1 一定比 L2 精度高", "L2 能做特征选择而 L1 不能", "两者数学上等价"]' answer="0" explain='L1 的惩罚在 0 处有尖点，次梯度条件使部分系数恰好取 0，可作特征选择；L2 是光滑二次项，只按比例收缩权重，一般不为 0。' />

<Predict no='098-4' q='前面 code 里对 q 做标准化后再跑 3NN，预测的类别是？' :options='["A", "B", "无法确定"]' answer='0' output='scaled A' explain='标准化消除尺度差异后，第一列这个真正有判别力的特征起作用：q 的第一列 0.12 明显落在 A 类的 0.1 到 0.2 区间，近邻变为 A 类，输出 scaled A。' />

<FillBlank no='098-5' tpl='___ math' :answers='["import"]' hint='回想本讲关于 KNN 与距离度量 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 KNN、距离度量与特征缩放 的落点。' />

<KnowledgeCard :points='["KNN 惰性学习：训练 O(1)、预测 O(n*d)；k 太小高方差、太大高偏差，取奇数避免平票", "欧氏/曼哈顿/闵氏对尺度敏感；不缩放时量纲大的列独霸距离，也把损失等高线拉成狭长椭圆", "标准化 z=(x-mean)/std 或归一化到 [0,1] 是硬要求，缩放后才能用更大学习率", "正规方程一步得全局最优但求逆 O(d^3)；梯度下降收敛要求 η 小于 2/最大特征值，越过就发散", "逻辑回归用 sigmoid 加交叉熵（平方损失非凸且饱和区梯度近 0）；决策边界是线性得分为零的超平面", "LogisticRegression 默认带 L2，C 是正则强度倒数；L2 收缩权重、L1 产生稀疏解，系数取 exp(w) 是优势比"]' :pitfalls='["KNN / 梯度下降不缩放，结果被大尺度特征主导或收敛极慢", "学习率设得过大，损失震荡溢出成 inf", "多项式回归次数越加越高，训练集满分线上很差", "不做特征缩放就跑 KNN 或梯度下降，量纲大的特征会主导结果，收敛也会变慢"]' summary='线性模型是理解机器学习的最佳入口：损失、正则、优化、偏差方差都能用闭式或几行代码看清，不必藏着黑箱里' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| KNN 惰性学习：训练 O(1)、预测 O(n*d)；k 太小高方差、太大高偏差，取奇数避免平票 | 建立直觉 |
| 欧氏/曼哈顿/闵氏对尺度敏感；不缩放时量纲大的列独霸距离，也把损失等高线拉成狭长椭圆 | 跑通示例 |
| 标准化 z=(x-mean)/std 或归一化到 [0,1] 是硬要求，缩放后才能用更大学习率 | 深入边界 |
| 正规方程一步得全局最优但求逆 O(d^3)；梯度下降收敛要求 η 小于 2/最大特征值，越过就发散 | 工程落地 |
| 逻辑回归用 sigmoid 加交叉熵（平方损失非凸且饱和区梯度近 0）；决策边界是线性得分为零的超平面 | 随堂检测 |
| LogisticRegression 默认带 L2，C 是正则强度倒数；L2 收缩权重、L1 产生稀疏解，系数取 exp(w) 是优势比 | 复盘 |

1. KNN 惰性学习：训练 O(1)、预测 O(n*d)；k 太小高方差、太大高偏差，取奇数避免平票

2. 欧氏/曼哈顿/闵氏对尺度敏感；不缩放时量纲大的列独霸距离，也把损失等高线拉成狭长椭圆

3. 标准化 z=(x-mean)/std 或归一化到 [0,1] 是硬要求，缩放后才能用更大学习率

[下一讲：SVM、核方法、决策树与随机森林](/data-ai/svm-trees)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/098-linear-models.py`

```bash
python3 examples/lessons/098-linear-models.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/098-linear-models.py) · [全部示例代码索引](/examples/)
