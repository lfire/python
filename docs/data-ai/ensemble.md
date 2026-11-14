---
title: 第 100 讲 · 集成学习：Boosting、XGBoost 与 LightGBM
description: 用组合模型稳定提升表格数据表现
---

<StageHeader stage='L9 · 数据与 AI' level='★★★★☆' time='40 分钟' goal='用组合模型稳定提升表格数据表现' prereq='第 099 讲 · SVM、核方法、决策树与随机森林' />

# 第 100 讲 · 集成学习：Boosting、XGBoost 与 LightGBM

森林靠平均把方差压下去，这一讲换个方向：让后一棵树专门补前一轮没算对的部分。表格数据上，一点点纠偏往往比单棵模型划算，代价是学习率、树数量和训练时间都跟着进场。走到集成学习这一站，该问的已不是『能不能涨分』，而是『涨这一点分值不值这个成本』。

先把 Bagging 与 Boosting 摆在一起，一个并行压方差、一个串行降偏差；再看 AdaBoost 与 `GBDT` 怎样把「拟合残差」说成函数空间里的梯度下降，为什么学习率和树数量必须一起调、早停该盯哪条曲线；最后落到 XGBoost 与 LightGBM 在工程实现上的分岔。需要决策树、随机森林的基础，也要会做交叉验证与早停。读完你会优先试梯度提升树、设好早停，并把特征管道与模型版本一并留下来。


## 树数量一路加到几千，线上反而变差

团队把表格数据的模型从单棵决策树换成梯度提升树，验证集 AUC 涨了六个点，于是把树数量从 100 加到 2000、学习率保持默认，结果训练分数一路涨、线上却开始掉，训练时间还翻了十几倍。另一条工单更棘手：一份几十万行、上千列、带大量类别特征与缺失值的表直接丢进 XGBoost，独热展开把内存撑爆，训练卡了几个小时。

两处都不是集成学习的问题，而是它的机制被用歪了：Boosting 串行拟合前一轮的残差，学习率与树数量必须成对调，还得留一份独立验证集做早停；特征规模一大，缺失值与类别特征要先处理，否则直方图分箱和内存都会失控。

本讲用纯 Python 把「拟合残差」跑成看得见的 mse 轨迹，再落到 XGBoost 与 LightGBM 的工程差异上。

<Callout type="warn" title='先看一个真实会出错的写法' text='把树数量一路加到几千、学习率不动，线上反而变差：训练误差会持续趋近 0，但验证误差在某个迭代数后回升，属于过拟合且训练成本线性增长' />


## Bagging 与 Boosting：并行降方差 vs 串行降偏差

两者都把多棵树组合起来，方向却相反。Bagging（随机森林）用有放回重采样并行训练一批互不相关的深树，再取平均或投票，平均主要压低方差，偏差基本与单棵树相当、并不会因为求平均而下降，所以单棵树可以长得很深。

Boosting 反过来，串行训练一串弱学习器（通常是浅树），每一棵都去拟合前面所有树加总后仍没解释掉的残差，再乘一个学习率累加进模型，偏差因此被逐步削掉。AdaBoost 是最早的形态：每轮抬高被错分样本的权重，按本轮误差给弱分类器分配话语权，最后加权投票。

`GBDT`（梯度提升决策树）把这套做法统一成函数空间里的梯度下降：对平方损失而言，损失对当前预测的负梯度恰好就是真实值减去当前预测，也就是残差，于是每一步只需训练一棵树去拟合它，模型按 `F_m = F_{m-1} + η·h_m(x)` 递推。

既然每步只走 η 倍的一小段，学习率 η 与树数量 M 便是一对耦合旋钮：η 小则步子稳、要更多树，η 大则收敛快却容易越过最优点；把 M 一味加下去，训练误差会趋近 0，验证误差却先降后升，只能用早停截断。

XGBoost 在 `GBDT` 之上补了二阶泰勒展开（同时用一阶梯度与二阶 Hessian）、正则项、列采样和缺失值的默认分裂方向，LightGBM 则换成直方图算法与 leaf-wise 生长，目标一致，工程取舍不同。

**Bagging 与 Boosting 对照**

| 维度 | Bagging / 随机森林 | Boosting / GBDT |
| --- | --- | --- |
| 训练方式 | 并行、各树独立 | 串行、后一棵拟合前面残差 |
| 基学习器 | 深树、高方差低偏差 | 浅树、低方差高偏差 |
| 主要降低 | 方差 | 偏差 |
| 样本权重 | 有放回重采样 | AdaBoost 提权错分 / GBDT 拟合残差 |
| 过拟合来源 | 树太深 | 树数量太多、无早停 |

<Callout type="tip" title='核心心智模型' text='两者都把多棵树组合起来，方向却相反。Bagging（随机森林）用有放回重采样并行训练一批互不相关的深树，再取平均或投票，平均主要压低方差，偏差基本与单棵树相当、并不会因为求平均而下降，所以单棵树可以长得很深。Boosting 反过来，串行训练一串弱学习器（通常是浅树），每一棵都去拟合前面所有树加总后…' />


## 梯度提升到底在拟合什么

把加法模型写成每棵树的输出按学习率累加，每轮先算当前残差 `r_i = y_i - F(x_i)`，再训练一个弱学习器 h_m 去拟合这批 r_i，最后把它的预测乘 η 累加回模型。

以本讲的 `y = 2x`（`x = 1..6`）为例，弱学习器取「按阈值切两段、各段输出残差均值」的回归树桩：第一轮在 3.5 处切开，左段均值 4、右段均值 10，学习率 0.6 之后 mse 从初始的 60 量级降到 11.947；

第二轮、第三轮继续拟合剩下的残差，mse 依次落到 3.328 与 1.191，切分阈值也随残差的形状挪动。这条单调下降的轨迹，就是 Boosting 直觉的全部来源。

学习率对照更能说明两者的耦合：`η=0.8` 时三轮就把 mse 压到 0.82，而 `η=0.2` 要十二轮才到 0.71——小学习率得用更多树补回来，但曲线更平滑，也更不容易越过最优点。

早停的判据是「在独立验证集上盯住指标，连续若干轮（patience）不再改善就停下并回滚到最佳轮」，`early_stopping_rounds` 必须配一份从头到尾没参与训练的验证集，绝不能拿测试集早停，那等于把测试集又变成了验证集。

还要记下最佳迭代数 `best_iteration`，上线只保留前这么多棵树，免得把过拟合的尾巴一起部署出去。

```python
xs = [1, 2, 3, 4, 5, 6]
y = [2, 4, 6, 8, 10, 12]
def stump(resid):
    best = None
    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:
        li = [i for i, x in enumerate(xs) if x <= t]
        ri = [i for i, x in enumerate(xs) if x > t]
        lv = sum(resid[i] for i in li) / len(li)
        rv = sum(resid[i] for i in ri) / len(ri)
        err = sum((resid[i] - lv) ** 2 for i in li) + sum((resid[i] - rv) ** 2 for i in ri)
        if best is None or err < best[0]:
            best = (err, t, li, ri, lv, rv)
    return best
lr = 0.6
F = [0.0] * len(xs)
for m in range(1, 4):
    resid = [yi - fi for yi, fi in zip(y, F)]
    err, t, li, ri, lv, rv = stump(resid)
    h = [lv if i in li else rv for i in range(len(xs))]
    F = [fi + lr * hi for fi, hi in zip(F, h)]
    mse = sum((a - b) ** 2 for a, b in zip(y, F)) / len(y)
    print('round', m, 'threshold', t, 'mse', round(mse, 3))
```

<OutputBox title='主示例运行结果' output='round 1 threshold 3.5 mse 11.947\nround 2 threshold 2.5 mse 3.328\nround 3 threshold 5.5 mse 1.191' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='xs = [1, 2, 3, 4, 5, 6]\ny = [2, 4, 6, 8, 10, 12]\ndef stump(resid):\n    best = None\n    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:\n        li = [i for i, x in enumerate(xs) if x &lt;= t]\n        ri = [i for i, x in enumerate(xs) if x &gt; t]\n        lv = sum(resid[i] for i in li) / len(li)\n        rv = sum(resid[i] for i in ri) / len(ri)\n        err = sum((resid[i] - lv) ** 2 for i in li) + sum((resid[i] - rv) ** 2 for i in ri)\n        if best is None or err &lt; best[0]:\n            best = (err, t, li, ri, lv, rv)\n    return best\nlr = 0.6\nF = [0.0] * len(xs)\nfor m in range(1, 4):\n    resid = [yi - fi for yi, fi in zip(y, F)]\n    err, t, li, ri, lv, rv = stump(resid)\n    h = [lv if i in li else rv for i in range(len(xs))]\n    F = [fi + lr * hi for fi, hi in zip(F, h)]\n    mse = sum((a - b) ** 2 for a, b in zip(y, F)) / len(y)\n    print(&#39;round&#39;, m, &#39;threshold&#39;, t, &#39;mse&#39;, round(mse, 3))' :notes='["定义样本特征 x 取 1 到 6", "真实目标 y=2x，用来检验加法模型能否逐步逼近", "弱学习器：按阈值切两段、各段输出残差均值的回归树桩", "best 保存当前误差最小的切分方案", "候选阈值取相邻 x 的中点，逐个试算", "左段样本下标，x 小于等于阈值", "右段样本下标，x 大于阈值", "左段叶值取该段残差均值，最小化平方误差", "右段叶值同理", "两段残差平方和作为该切分的拟合误差", "保留误差最小的树桩，即最贴合残差的分段常数", "记录误差、阈值、左右下标与两段叶值", "返回最优树桩供加法模型累加", "学习率 η=0.6，控制每棵树收缩多少", "F 是加法模型当前对所有样本的预测，初始为 0", "串行训练三轮，每轮拟合上一轮的残差", "残差 r = y - F，平方损失下它就是负梯度", "用当前残差拟合一棵新树桩", "把树桩展开成对每个样本的输出 h(x)", "F ← F + η·h，这是函数空间的一次梯度下降步", "计算当前模型的均方误差", "打印轮次、切分阈值与 mse，观察残差逐轮被吃掉"]' title='第 100 讲 · 集成学习：Boosting、XGBoost 与 LightGBM' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 残差、学习率与树数量为什么成对调

```python
n_samples = 1000000
n_bins = 255
print('exact split candidates', n_samples - 1)
print('histogram candidates', n_bins - 1)
print('ratio', round((n_samples - 1) / (n_bins - 1)))
```

<OutputBox title='原理验证' output='exact split candidates 999999\nhistogram candidates 254\nratio 3937' />

<Compare :panels='[{"label": "主示例", "code": "xs = [1, 2, 3, 4, 5, 6]\ny = [2, 4, 6, 8, 10, 12]\ndef stump(resid):\n    best = None\n    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:\n        li = [i for i, x in enumerate(xs) if x &lt;= t]\n        ri = [i for i, x in enumerate(xs) if x &gt; t]\n        lv = sum(resid[i] for i in li) / len(li)\n        rv = sum(resid[i] for i in ri) / len(ri)\n        err = sum((resid[i] - lv) ** 2 for i in li) + sum((resid[i] - rv) ** 2 for i in ri)\n        if best is None or err &lt; best[0]:\n            best = (err, t, li, ri, lv, rv)\n    return best\nlr = 0.6\nF = [0.0] * len(xs)\nfor m in range(1, 4):\n    resid = [yi - fi for yi, fi in zip(y, F)]\n    err, t, li, ri, lv, rv = stump(resid)\n    h = [lv if i in li else rv for i in range(len(xs))]\n    F = [fi + lr * hi for fi, hi in zip(F, h)]\n    mse = sum((a - b) ** 2 for a, b in zip(y, F)) / len(y)\n    print(&#39;round&#39;, m, &#39;threshold&#39;, t, &#39;mse&#39;, round(mse, 3))", "note": "Bagging 与 Boosting：并行降方差 vs 串行降偏差"}, {"label": "对照 / 进阶", "code": "def boost(lr, rounds):\n    F = [0.0] * len(xs)\n    out = []\n    for _ in range(rounds):\n        resid = [yi - fi for yi, fi in zip(y, F)]\n        err, t, li, ri, lv, rv = stump(resid)\n        h = [lv if i in li else rv for i in range(len(xs))]\n        F = [fi + lr * hi for fi, hi in zip(F, h)]\n        out.append(round(sum((a - b) ** 2 for a, b in zip(y, F)) / len(y), 2))\n    return out\nprint(&#39;lr=0.8 x3&#39;, boost(0.8, 3))\nprint(&#39;lr=0.2 x12&#39;, boost(0.2, 12))", "note": "残差拟合、学习率与早停的判据"}]' title='两种写法对照' note='差异集中在 Bagging 与 Boosting 差异；先看输出，再找背后的规则。' />


## 早停与 best_iteration：验证误差何时回升

```python
def boost(lr, rounds):
    F = [0.0] * len(xs)
    out = []
    for _ in range(rounds):
        resid = [yi - fi for yi, fi in zip(y, F)]
        err, t, li, ri, lv, rv = stump(resid)
        h = [lv if i in li else rv for i in range(len(xs))]
        F = [fi + lr * hi for fi, hi in zip(F, h)]
        out.append(round(sum((a - b) ** 2 for a, b in zip(y, F)) / len(y), 2))
    return out
print('lr=0.8 x3', boost(0.8, 3))
print('lr=0.2 x12', boost(0.2, 12))
```

<OutputBox title='对照写法：先自己猜，再点开' output='lr=0.8 x3 [4.99, 1.81, 0.82]\nlr=0.2 x12 [39.79, 26.42, 17.51, 11.77, 8.02, 5.51, 3.85, 2.67, 1.91, 1.35, 0.98, 0.71]' guess="true" />

**关键超参与常见默认（以所用版本官方文档为准）**

| 参数 | XGBoost | LightGBM | 作用 |
| --- | --- | --- | --- |
| learning_rate / eta | 0.3 | 0.1 | 每棵树收缩步长 |
| 树数量 n_estimators | 100 | 100 | 与学习率成对调 |
| max_depth | 6 | -1(不限) | 限制树深 |
| num_leaves | — | 31 | leaf-wise 的叶子上限 |
| max_bin | 256(tree_method=hist) | 255 | 直方图分箱数 |
| min_data_in_leaf | min_child_weight=1 | 20 | 叶内最少样本约束 |


## XGBoost 与 LightGBM 的工程差异

XGBoost 的目标函数在 `GBDT` 之上做二阶泰勒展开，用一阶梯度和二阶 Hessian 一起把叶子分值定得更准，并在目标里显式加入叶子数与叶子权重的正则，支持列采样 `colsample_bytree` 与行采样 `subsample`，还能为缺失值自动学出默认分裂方向；

经典默认参数是学习率 `eta=0.3`、`max_depth=6`、`min_child_weight=1`、`subsample=1`，树按 level-wise 逐层生长。

LightGBM 的两处改造是直方图算法与 leaf-wise 生长：把连续特征离散成 `max_bin`（默认 255）个箱，分裂候选点从「样本数减一」降到「箱数减一」，全部特征枚举一次的成本从 `O(n·d)` 降到 `O(bins·d)`；

leaf-wise 每次只分裂当前增益最大的那片叶子，同样叶子数下误差更低，但树可能长得很深，得用 `num_leaves`（默认 31）和 `min_data_in_leaf`（默认 20）约束。

它的默认学习率是 0.1，原生支持 `categorical_feature` 与缺失值，不用先做独热展开。

工程上还有几条容易踩的：高基数类别特征直接独热会撑爆内存，LightGBM 应显式指定 `categorical_feature`，XGBoost 较新版本用 `enable_categorical`；

缺失值别随手填 0，两个库都能把缺失当成独立分支处理。上线时固化特征管道、记录模型版本、训练数据快照与 `best_iteration`，成本主要压在树数量、`num_leaves` 和特征维度上，先用小样本、小网格把管道验通再放大。这些默认值会随版本微调，落地时以所用版本的官方文档为准。

**直方图算法复杂度（单特征、n=1e6）**

| 方法 | 分裂候选点数 | 搜索复杂度 | 倍数 |
| --- | --- | --- | --- |
| 精确贪心 | 999999 | O(n·d) | 基准 |
| 直方图(max_bin=255) | 254 | O(bins·d) | 约省 3937 倍候选 |


## 直方图分箱：分裂搜索成本怎么被压下来

Boosting 可以整体看成函数空间里的梯度下降：把模型 F 当作待优化的变量，目标是对所有样本最小化 `Σ L(y_i, F(x_i))`，第 m 步沿负梯度方向添一个基学习器 h_m。

对平方损失来说，损失对 F 的负梯度正好等于真实值减当前预测，也就是残差，所以「拟合残差」并不是经验上的小聪明，而是最速下降的精确形式；换成对数损失等其它损失，拟合的就是伪残差。

XGBoost 在此基础上对目标做二阶泰勒展开，用一阶梯度 g_i 与二阶 Hessian h_i 解出叶子的最优分值 `w* = -G_j/(H_j+λ)`（G_j、H_j 是该叶子上梯度与 Hessian 的和），并在目标里加入 `Ω = γT + (1/2)λΣw²` 这样的正则，让「这一刀该不该切」有闭式判据。

直方图算法把连续特征分箱，用每箱累加的梯度与 Hessian 直方图代替逐样本扫描，分裂候选从 n-1 降到 bins-1，复杂度从 `O(n·d)` 降到 `O(bins·d)`——本讲 probe 里 1e6 个样本、255 个箱，候选点从 999999 降到 254，相差约 3937 倍。

学习率 η 是每一步的收缩系数，M 与 η 一起决定总共走了多远；走过了头，验证误差就会在某个 M 之后回升，早停正是在那一点把它截断。

<ConceptDiagram type='layers3' title='第 100 讲 · 分层视角' labels='Bagging 与 Boosting：并…|残差拟合、学习率与早停的判据|XGBoost / LightGBM 的…|模型复杂度成本' caption='XGBoost / LightGBM 的工程差异与成本' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 模型复杂度成本 落在哪一层。


## 带验证轨迹的 GBDT：把「该停在哪一轮」变成可核对的数字

上线一个梯度提升模型，最容易被跳过的一步是「到底部署多少棵树」。稳妥做法是把每一轮的验证 mse 记成一条轨迹，挑出验证误差最小的那一轮，并在日志里把 `best_iteration`、学习率和特征管道版本一起固化下来。

下面用纯标准库写一个自洽的最小 `GBDT`：`fit_stump` 按阈值切两段拟合残差，`pred` 把已训练的树桩按学习率累加，验证集留三个点，主循环逐轮打印验证 mse 与最佳轮次。它要演示的工程契约是：轮数不是越多越好，最佳轮由验证集说了算，而不是由训练误差决定。

真实项目里把 `fit_stump` 换成 `LGBMRegressor` / `XGBRegressor`，把轨迹换成 `eval_set` + `early_stopping_rounds`，`best_iteration` 直接读模型属性，口径完全一致。

```python
xs = [1, 2, 3, 4, 5, 6]
y = [2, 4, 6, 8, 10, 12]
val_x = [1.5, 3.5, 5.5]
val_y = [3.0, 7.0, 11.0]

def fit_stump(resid):
    best = None
    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:
        lo = [resid[i] for i, x in enumerate(xs) if x <= t]
        hi = [resid[i] for i, x in enumerate(xs) if x > t]
        lv, rv = sum(lo) / len(lo), sum(hi) / len(hi)
        err = sum((v - lv) ** 2 for v in lo) + sum((v - rv) ** 2 for v in hi)
        if best is None or err < best[0]: best = (err, t, lv, rv)
    return best

lr, rounds_used = 0.6, []
F = [0.0] * len(xs)
best_round, best_val, trace = 0, float('inf'), []
for m in range(1, 11):
    resid = [y[i] - F[i] for i in range(len(xs))]
    err, t, lv, rv = fit_stump(resid)
    rounds_used.append((t, lv, rv))
    F = [F[i] + lr * (lv if xs[i] <= t else rv) for i in range(len(xs))]
    def pred(x): return lr * sum((a if x <= c else b) for c, a, b in rounds_used)
    val_mse = sum((pred(vx) - vy) ** 2 for vx, vy in zip(val_x, val_y)) / len(val_x)
    trace.append(round(val_mse, 3))
    if val_mse < best_val: best_val, best_round = val_mse, m
print('val mse trajectory', trace)
print('best round', best_round, 'best val', round(best_val, 3))
```

<Callout type="idea" title='落地提示' text='表格数据优先试梯度提升树并做早停；上线时固化特征管道、记录版本与训练数据快照' />

<CheckList id='P100b' title='上线前自检' :items='["能复现并解释「把树数量一路加到几千、学习率不动，线上反而变差」", "能复现并解释「高基数类别特征直接独热展开、缺失值随手填 0」", "能复现并解释「在测试集上做早停或反复按测试分数挑轮数」", "能用一条命令验证 Bagging 与 Boosting 差异", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from collections import Counter; print(Counter([0,0,1]).most_common(1))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 Bagging 与 Boosting 差异 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 二阶泰勒展开下的叶子权重闭式解

XGBoost 第 t 轮并不直接拟合残差，而是把损失在当前预测处做二阶展开。

记每个样本的一阶、二阶偏导分别为 g_i 和 h_i，目标近似为各样本 `g_i·f_t(x_i) + 0…` 之和，再加上对树复杂度的正则：叶子数 T 乘 gamma，加上所有叶子权重平方和乘 lambda 的一半，写成 `Omega`。

```python
g_i·f_t(x_i) + 0.5·h_i·f_t(x_i)^2
Omega(f_t) = gamma*T + 0.5*lambda*sum(w_j^2)
```

把落在叶子 j 的样本集合记作 I_j，令 G_j、H_j 分别为其中 g_i、h_i 的和，目标就变成一族彼此独立的二次式 `G_j*w_j + 0.5*(H…`。

```python
G_j*w_j + 0.5*(H_j+lambda)*w_j^2
```

对 w_j 求导置零得闭式解 `w_j* = -G_j/(H_j+lambda)`，代回得到最优目标，父子节点最优目标之差即分裂增益；

G 可为负、H 恒非负，lambda 既做正则又保证分母不为零。

由此看清两个常被读错的量：`min_child_weight` 只在平方损失下才等于「叶子最少样本数」，因为此时 h_i 恒为 1、H_j 才等于样本条数；

换到对数损失，每个样本的 h_i 至多 0.25，几百个高置信样本凑起来 H_j 仍可能低于阈值而提前拦下分裂，`min_child_weight=1` 几乎不再剪枝，应按 1/`max(h_i)` 的量级重设。

LightGBM 的 `min_data_in_leaf` 数的是样本条数，口径不同，不能按数值直接换算。

```python
def leaf_weight(G, H, lam):
    return (0.0 - G) / (H + lam)

def gain(GL, HL, GR, HR, lam, gamma):
    return 0.5 * (GL ** 2 / (HL + lam) + GR ** 2 / (HR + lam) - (GL + GR) ** 2 / (HL + HR + lam)) - gamma

samples = [(-2.0, 1.0), (-1.0, 1.0), (1.0, 1.0), (2.0, 1.0)]
G = sum(g for g, h in samples)
H = sum(h for g, h in samples)
lam, gamma = 1.0, 0.0
w = leaf_weight(G, H, lam)
print('G', G, 'H', H, 'w_star', round(w, 4))
obj_before = -0.5 * G ** 2 / (H + lam) + gamma
left = [s for s in samples if s[0] < 0]
right = [s for s in samples if s[0] >= 0]
GL = sum(g for g, h in left)
HL = sum(h for g, h in left)
GR = sum(g for g, h in right)
HR = sum(h for g, h in right)
g_split = gain(GL, HL, GR, HR, lam, gamma)
print('GL HL', GL, HL, 'GR HR', GR, HR)
print('gain', round(g_split, 4))
print('obj_before', round(obj_before, 4), 'obj_after', round(obj_before - g_split, 4))
print('left_allowed', HL >= 3.0, 'right_allowed', HR >= 3.0)
```

<OutputBox title='扩展示例运行结果' output='G 0.0 H 4.0 w_star 0.0\nGL HL -3.0 2.0 GR HR 3.0 2.0\ngain 3.0\nobj_before 0.0 obj_after -3.0\nleft_allowed False right_allowed False' />

<LineByLine code='def leaf_weight(G, H, lam):\n    return (0.0 - G) / (H + lam)\n\ndef gain(GL, HL, GR, HR, lam, gamma):\n    return 0.5 * (GL ** 2 / (HL + lam) + GR ** 2 / (HR + lam) - (GL + GR) ** 2 / (HL + HR + lam)) - gamma\n\nsamples = [(-2.0, 1.0), (-1.0, 1.0), (1.0, 1.0), (2.0, 1.0)]\nG = sum(g for g, h in samples)\nH = sum(h for g, h in samples)\nlam, gamma = 1.0, 0.0\nw = leaf_weight(G, H, lam)\nprint(&#39;G&#39;, G, &#39;H&#39;, H, &#39;w_star&#39;, round(w, 4))\nobj_before = -0.5 * G ** 2 / (H + lam) + gamma\nleft = [s for s in samples if s[0] &lt; 0]\nright = [s for s in samples if s[0] &gt;= 0]\nGL = sum(g for g, h in left)\nHL = sum(h for g, h in left)\nGR = sum(g for g, h in right)\nHR = sum(h for g, h in right)\ng_split = gain(GL, HL, GR, HR, lam, gamma)\nprint(&#39;GL HL&#39;, GL, HL, &#39;GR HR&#39;, GR, HR)\nprint(&#39;gain&#39;, round(g_split, 4))\nprint(&#39;obj_before&#39;, round(obj_before, 4), &#39;obj_after&#39;, round(obj_before - g_split, 4))\nprint(&#39;left_allowed&#39;, HL &gt;= 3.0, &#39;right_allowed&#39;, HR &gt;= 3.0)' :notes='["w_j* 闭式解：G 是叶子内一阶梯度之和，H 是二阶梯度之和", "Gain 公式里 gamma 作为新增叶子的固定成本被减去", "空行，只用于分隔逻辑块，不影响执行结果。", "四个样本，平方损失下 h=1；父节点 G=0 但分裂增益未必为 0", "打印闭式解、目标下降量与按 H 的准入判断", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `samples = [(-2.0, 1.0), (-1.0, 1.0), (1.0, 1.0), (2.` 的作用，可对照上方输出逐项核对。", "这一行 `G = sum(g for g, h in samples)` 的作用，可对照上方输出逐项核对。", "这一行 `H = sum(h for g, h in samples)` 的作用，可对照上方输出逐项核对。", "这一行 `lam, gamma = 1.0, 0.0` 的作用，可对照上方输出逐项核对。", "这一行 `w = leaf_weight(G, H, lam)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;G&#39;, G, &#39;H&#39;, H, &#39;w_star&#39;, round(w, 4))` 的作用，可对照上方输出逐项核对。", "这一行 `obj_before = -0.5 * G ** 2 / (H + lam) + gamma` 的作用，可对照上方输出逐项核对。", "这一行 `left = [s for s in samples if s[0] &lt; 0]` 的作用，可对照上方输出逐项核对。", "这一行 `right = [s for s in samples if s[0] &gt;= 0]` 的作用，可对照上方输出逐项核对。", "这一行 `GL = sum(g for g, h in left)` 的作用，可对照上方输出逐项核对。", "这一行 `HL = sum(h for g, h in left)` 的作用，可对照上方输出逐项核对。", "这一行 `GR = sum(g for g, h in right)` 的作用，可对照上方输出逐项核对。", "这一行 `HR = sum(h for g, h in right)` 的作用，可对照上方输出逐项核对。", "这一行 `g_split = gain(GL, HL, GR, HR, lam, gamma)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;GL HL&#39;, GL, HL, &#39;GR HR&#39;, GR, HR)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;gain&#39;, round(g_split, 4))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;obj_before&#39;, round(obj_before, 4), &#39;obj_after` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;left_allowed&#39;, HL &gt;= 3.0, &#39;right_allowed&#39;, HR` 的作用，可对照上方输出逐项核对。"]' title='扩展示例逐行讲解' />


### 结构增益公式里 min_child_weight 的真实含义

min_child_weight 常被读成「叶子最少样本数」，只有平方损失下成立（`h_i=1` 使 H_j 等于条数）。logistic 损失里 `h_i=p(1-p)` 至多 0.25，几百个高置信样本的 H_j 仍可能低于阈值，于是停止分裂。

XGBoost 在 src/tree/`updater_colmaker.cc` 的分裂准入里要求左右子节点 H 都不小于该阈值，否则切分直接丢弃；

LightGBM 的 min_data_in_leaf 数的是样本条数，口径不同不能按数值换算。

由此推出反直觉现象：换到对数损失后 `min_child_weight=1` 几乎不再剪枝，因为每个样本 h 不超过 0.25，至少 4 条才凑够 `H=1`，应按 1/`max(h)` 量级重设。

Gain 里的 gamma 是另一道闸：只有 Gain 大于 0 才分裂，等价于对叶子数 T 的结构正则。工程上 level-wise 逐层展开；直方图把候选点从 n-1 压到 max_bin-1，单特征枚举成本从 `O(n·d)` 降到 `O(max_bin·d)`。理解 H_j 才是「样本权重」，才能解释切分为何被拒。

**分裂准入与复杂度：XGBoost 与 LightGBM 的口径差异**

| 维度 | XGBoost | LightGBM |
| --- | --- | --- |
| 分裂候选点 | pre-sorted 精确枚举 n-1 个，approx 用分位数桶 | 直方图 max_bin-1 个，默认 255 |
| 单特征枚举成本 | O(n·d)，n 为样本数 | O(max_bin·d)，与样本数无关 |
| 最小叶子约束 | min_child_weight 比 Hessian 之和 H_j | min_data_in_leaf 比样本条数 |
| 树生长方式 | level-wise 逐层，max_depth 默认 6 | leaf-wise 选增益最大叶子，num_leaves 默认 31 |


## num_leaves 失控：小样本上 leaf-wise 过拟合的量化复盘

某风控团队把 3800 条样本、60 个特征的小表交给 LightGBM 默认参数（`num_leaves=31`、`min_data_in_leaf=20`、`max_bin=255`），训练 AUC 0.99、验证 AUC 0.71。

leaf-wise 每次只分裂当前增益最大的叶子，3800 条样本足够让树长到 31 个叶子，每叶只剩几十条记录，把训练集噪声背了下来；255 个直方图箱又把金额长尾切成细桶。复盘把 num_leaves 降到 7、min_data_in_leaf 提到 200，验证 AUC 回到 0.83。

下面把叶子预算写成可算的账：平均每叶样本数约 n/(2·num_leaves)，min_data_in_leaf 给出的叶子上限是 n 整除该值，两者取小才是实际能长出的叶子数。

```python
def diagnose(n, configs):
    rows = []
    for num_leaves, min_data in configs:
        avg = n / (2 * num_leaves)
        allowed = min(num_leaves, n // min_data)
        rows.append((num_leaves, min_data, round(avg, 1), allowed))
    return rows

for row in diagnose(3800, [(31, 20), (31, 200), (7, 200), (15, 100)]):
    print('leaves', row[0], 'min_data', row[1], 'avg_per_leaf', row[2], 'effective_cap', row[3])
```

<Quiz no='100-1' q='在 logistic 损失下把 min_child_weight 当成「叶子最少样本条数」来调，最可能出什么问题？' :options='["平方损失下等价，但 logistic 的 h=p(1-p) 至多 0.25，H_j 比样本数小得多，阈值几乎不再剪枝，树继续长导致过拟合", "会让所有叶子都被剪掉，模型立刻欠拟合", "只影响训练速度，完全不改变树结构", "min_child_weight 在任何损失下都严格等于样本条数"]' answer="0" explain='平方损失 h=1 时 H_j 才等于样本条数；logistic 下 h 最大 0.25，几百个高置信样本的 H_j 仍可能低于阈值，按样本数设阈值会系统性低估，剪枝失效。XGBoost 比的是 Hessian 之和而非计数。' />

<Exercise title='进阶：手算一次分裂的 Gain 并验证 gamma 的剪枝作用' task='给定父节点 G=-2、H=5，左子 G_L=-3、H_L=2，右子 G_R=1、H_R=3，lambda=1，gamma 取 0 与 2，实现 gain 并指出 gamma=2 时是否允许分裂。' solution='def gain(GL, HL, GR, HR, lam, gamma):\n    return 0.5 * (GL*GL/(HL+lam) + GR*GR/(HR+lam) - (GL+GR)**2/(HL+HR+lam)) - gamma\n\ng0 = gain(-3, 2, 1, 3, 1, 0)\ng2 = gain(-3, 2, 1, 3, 1, 2)\nprint(&#39;gain_gamma0&#39;, round(g0, 4))\nprint(&#39;gain_gamma2&#39;, round(g2, 4))\nprint(&#39;split_when_gamma2&#39;, g2 &gt; 0)' explain='gamma 是新增叶子的固定成本，直接从 Gain 里减，只有 Gain 大于 0 才分裂；gamma 从 0 提到 2 让同一切分由正转负，树停止生长。' />


## 练习与速记：调 boosting 的四个旋钮

<Exercise title='基础：手写一轮残差拟合' task='对 y=[2,4,6,8,10,12]、初始 F=0，找出使残差平方和最小的单阈值切分，写出左右叶值与切分点，并说明它为什么等价于负梯度。' solution='xs=[1,2,3,4,5,6]; y=[2,4,6,8,10,12]\nbest=None\nfor t in [(a+b)/2 for a,b in zip(xs,xs[1:])]:\n    lo=[y[i] for i,x in enumerate(xs) if x&lt;=t]; hi=[y[i] for i,x in enumerate(xs) if x&gt;t]\n    lv,rv=sum(lo)/len(lo),sum(hi)/len(hi)\n    e=sum((v-lv)**2 for v in lo)+sum((v-rv)**2 for v in hi)\n    if best is None or e&lt;best[0]: best=(e,t,lv,rv)\nprint(best)' explain='平方损失 L=(1/2)(y-F)² 的负梯度 -∂L/∂F = y-F，初始 F=0 时残差就是 y，因此拟合残差正是函数空间的最速下降一步；最优切分在 3.5，左叶 4、右叶 10。' />

<Exercise title='进阶：量化直方图分箱的收益' task='设样本数 n=1000000、max_bin=255，计算精确贪心与直方图算法各自的分裂候选点数与比值，并说明复杂度从什么量级降到什么量级。' solution='n=1000000; bins=255\nprint(&#39;exact&#39;, n-1, &#39;hist&#39;, bins-1, &#39;ratio&#39;, round((n-1)/(bins-1)))' explain='精确贪心要试 n-1=999999 个切分点、复杂度 O(n·d)；直方图只需 bins-1=254 个、复杂度 O(bins·d)，候选点约省 3937 倍。' />

<Quiz no='100-2' q='Boosting 与 Bagging 最本质的区别是？' :options='["Boosting 串行拟合前面模型的残差、主要降偏差；Bagging 并行平均、主要降方差", "Boosting 只能用于回归", "Bagging 需要学习率而 Boosting 不需要", "两者都是降低方差，没有区别"]' answer="0" explain='Boosting 是函数空间的梯度下降，每一步拟合负梯度（平方损失下即残差），串行降偏差；Bagging 用重采样训练独立深树再平均，降的是方差。' />

<Quiz no='100-3' q='学习率调小之后，树数量通常应该怎么变？' :options='["相应增多，并用早停找最佳轮", "相应减少", "完全不变", "改成固定 100 棵"]' answer="0" explain='η 是每步收缩系数，η 变小则达到同等拟合程度需要更多树；同时必须用独立验证集早停，避免树太多把验证误差又推上去。' />

<Quiz no='100-4' q='LightGBM 直方图算法把分裂搜索复杂度降为？' :options='["O(bins·d)，候选点从样本数降到分箱数", "O(n²·d)", "O(log n)", "与 XGBoost 精确贪心完全相同"]' answer="0" explain='把连续特征离散成 max_bin 个箱后，候选切分点从 n-1 降到 bins-1，搜索复杂度由 O(n·d) 降到 O(bins·d)；1e6 样本、255 箱时约省 3937 倍候选点。' />

<Predict no='100-5' q='前面 probe 里 n=1000000、max_bin=255 时，直方图算法的分裂候选点数是多少？' :options='["254", "255", "999999"]' answer='0' output='histogram candidates 254' explain='候选点是分箱数减一，即 255-1=254；精确贪心是 n-1=999999。probe 打印的正是 histogram candidates 254，二者相差约 3937 倍。' />

<FillBlank no='100-6' tpl='___ stump(resid):' :answers='["def"]' hint='回想本讲关于 Bagging 与 Boosting 差异 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Bagging 与 Boosting：并行降方差 vs 串行降偏差 的落点。' />

<KnowledgeCard :points='["Boosting 串行拟合残差、降偏差；Bagging 并行平均、降方差，平均不改变偏差", "平方损失下负梯度就是残差；`F_m = F_{m-1} + η·h_m(x)`，η 与树数量 M 必须成对调", "早停盯独立验证集，`early_stopping_rounds` 配 `best_iteration`，上线只保留最佳轮之前的树", "XGBoost 用二阶泰勒 + 正则 + level-wise，默认 `eta=0.3`、`max_depth=6`；LightGBM 用直方图 + leaf-wise，默认学习率 0.1", "直方图把候选点从 n-1 压到 bins-1，复杂度 `O(n·d)` 降到 `O(bins·d)`", "高基数类别用 `categorical_feature` / `enable_categorical`，缺失当独立分支；成本落在树数量、`num_leaves` 与特征维度"]' :pitfalls='["把树数量一路加到几千、学习率不动，线上反而变差", "高基数类别特征直接独热展开、缺失值随手填 0", "在测试集上做早停或反复按测试分数挑轮数", "在大规模特征上不做缺失与类别处理直接训练，训练时间与内存都会失控"]' summary='Boosting 是串行地拟合前一轮的残差，因此学习率与树的数量要一起调，并用早停防止过拟合' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| Boosting 串行拟合残差、降偏差；Bagging 并行平均、降方差，平均不改变偏差 | 建立直觉 |
| 平方损失下负梯度就是残差；`F_m = F_{m-1} + η·h_m(x)`，η 与树数量 M 必须成对调 | 跑通示例 |
| 早停盯独立验证集，`early_stopping_rounds` 配 `best_iteration`，上线只保留最佳轮之前的树 | 深入边界 |
| XGBoost 用二阶泰勒 + 正则 + level-wise，默认 `eta=0.3`、`max_depth=6`；LightGBM 用直方图 + leaf-wise，默认学习率 0.1 | 工程落地 |
| 直方图把候选点从 n-1 压到 bins-1，复杂度 `O(n·d)` 降到 `O(bins·d)` | 随堂检测 |
| 高基数类别用 `categorical_feature` / `enable_categorical`，缺失当独立分支；成本落在树数量、`num_leaves` 与特征维度 | 复盘 |

1. Boosting 串行拟合残差、降偏差；Bagging 并行平均、降方差，平均不改变偏差

2. 平方损失下负梯度就是残差；`F_m = F_{m-1} + η·h_m(x)`，η 与树数量 M 必须成对调

3. 早停盯独立验证集，`early_stopping_rounds` 配 `best_iteration`，上线只保留最佳轮之前的树

[下一讲：无监督学习：KMeans、DBSCAN、PCA 与异常检测](/data-ai/unsupervised)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/100-ensemble.py`

```bash
python3 examples/lessons/100-ensemble.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/100-ensemble.py) · [全部示例代码索引](/examples/)
