---
title: 第 102 讲 · 模型调优：交叉验证、正则化与过拟合
description: 系统性地提升泛化能力
---

<StageHeader stage='L9 · 数据与 AI' level='★★★★☆' time='40 分钟' goal='系统性地提升泛化能力' prereq='第 101 讲 · 无监督学习：KMeans、DBSCAN、PCA 与异常检测' />

# 第 102 讲 · 模型调优：交叉验证、正则化与过拟合

从直线到森林、从有标签到无标签，模型算见了一圈。同一算法调与不调，表现常差一截；报告写着 0.93、上线只有 0.7，多半不是模型不行，是拿测试集反复调到满意，把它变成了验证集。本讲不新增模型，专心把泛化做扎实。

先用偏差方差分解打底，看学习曲线与验证曲线的形状：两条线挨得近还是裂得开，告诉你该加数据还是降复杂度；接着比较网格 / 随机 / 贝叶斯搜索适合多少参数；最后收在正则与早停、类别不平衡处理，以及嵌套交叉验证如何避开选择陷阱。需要前面任一模型的评估、Pipeline 和交叉验证。学完能设计一次可复现调参，留出一份从不参与决策的测试集。


## 测试集上调出来的 0.93，上线只有 0.7

一个分类模型在测试集上反复调了几十轮参数，最终报告 0.93 的准确率，评审通过；上线两周真实流量只有 0.7。复盘发现测试集被反复用来挑超参、挑阈值、挑特征，它早已退化成验证集，那个 0.93 是「在测试集上调优」的结果，不再是对泛化能力的无偏估计。

另一处问题藏在数据本身：正样本只占几个百分点，团队却一直用 accuracy 汇报，全预测多数类就能拿高分；交叉验证也没分层，某几折里正样本几乎为零，分数波动大得离谱。调参的本质不是「把网格开大、把分数刷高」，而是在模型容量与数据量之间找平衡，并守住「测试集只用一次」这条底线。

本讲用纯 Python 把验证曲线、偏差方差分解与搜索流程跑成可核对的数字。

<Callout type="warn" title='先看一个真实会出错的写法' text='在测试集上反复调参，报告 0.93 上线只有 0.7：测试集参与决策后退化为验证集，最优分数带选择偏差，不再无偏' />


## 偏差方差分解：误差由哪几部分组成

对回归问题，把期望泛化误差分解可得 E[(y - f̂)²] = `Bias(f̂)`² + `Var(f̂)` + σ²：偏差是模型平均预测与真实函数的差，衡量欠拟合；方差是模型对训练集扰动的敏感度，衡量过拟合；σ² 是数据本身不可约的噪声。

模型越复杂（次数越高、树越深、k 越小），偏差越小而方差越大，两者之和通常呈 U 型，最优点在中间。学习曲线以训练样本数 n 为横轴，画训练误差与验证误差：随着 n 增大，训练误差一般上升（更难记住所有样本）、验证误差下降并逐渐收敛到训练误差附近。两条曲线的间距就是方差的可视化——间距大说明高方差，加数据确实有用；

两者都高且几乎贴在一起说明高偏差，加数据没用，该加特征、减正则或换更强模型。验证曲线以某个超参（k、树深、正则强度）为横轴：训练误差随容量单调下降，验证误差先降后升，最低点就是该超参的合理取值。

本讲 code 里 `k=1` 训练误差 0、验证误差 0.333（过拟合），`k=5` 验证误差降到 0，`k=9` 又升到 0.5（把两类平均掉、欠拟合），这条 U 型就是偏差方差权衡最直接的证据。看曲线要用趋势与多次平均，而不是盯着单个点。

<Callout type="tip" title='核心心智模型' text='对回归问题，把期望泛化误差分解可得 E[(y - f̂)²] = Bias(f̂)² + Var(f̂) + σ²：偏差是模型平均预测与真实函数的差，衡量欠拟合；方差是模型对训练集扰动的敏感度，衡量过拟合；σ² 是数据本身不可约的噪声。模型越复杂（次数越高、树越深、k 越小），偏差越小而方差越大，两' />


## 学习曲线与验证曲线：形态决定动作

```python
import math
train = [(1, 0), (2, 0), (3, 1), (4, 0), (5, 0), (6, 1), (7, 1), (8, 1), (9, 1)]
valid = [(2.5, 0), (3.5, 0), (4.5, 0), (5.5, 1), (6.5, 1), (8.5, 1)]
def knn_err(train, data, k):
    wrong = 0
    for x, lab in data:
        near = sorted(train, key=lambda r: abs(r[0] - x))[:k]
        votes = sum(1 for _, l in near if l == 1)
        pred = 1 if votes > k / 2 else 0
        wrong += int(pred != lab)
    return round(wrong / len(data), 3)
for k in (1, 3, 5, 7, 9):
    print('k', k, 'train_err', knn_err(train, train, k), 'valid_err', knn_err(train, valid, k))
```

<OutputBox title='主示例运行结果' output='k 1 train_err 0.0 valid_err 0.333\nk 3 train_err 0.111 valid_err 0.167\nk 5 train_err 0.222 valid_err 0.0\nk 7 train_err 0.222 valid_err 0.0\nk 9 train_err 0.444 valid_err 0.5' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import math\ntrain = [(1, 0), (2, 0), (3, 1), (4, 0), (5, 0), (6, 1), (7, 1), (8, 1), (9, 1)]\nvalid = [(2.5, 0), (3.5, 0), (4.5, 0), (5.5, 1), (6.5, 1), (8.5, 1)]\ndef knn_err(train, data, k):\n    wrong = 0\n    for x, lab in data:\n        near = sorted(train, key=lambda r: abs(r[0] - x))[:k]\n        votes = sum(1 for _, l in near if l == 1)\n        pred = 1 if votes &gt; k / 2 else 0\n        wrong += int(pred != lab)\n    return round(wrong / len(data), 3)\nfor k in (1, 3, 5, 7, 9):\n    print(&#39;k&#39;, k, &#39;train_err&#39;, knn_err(train, train, k), &#39;valid_err&#39;, knn_err(train, valid, k))' :notes='["导入 math 备用，本例用绝对值做一维距离", "9 个训练点，x=3 与 x=5 是故意标反的噪声点", "6 个验证点，标签按 x 小于 5 为 0、大于等于 5 为 1 的规律", "定义以 kNN 的 k 作为模型容量超参的误差函数", "累计预测错的样本数", "逐条计算验证/训练样本的预测", "按一维距离取最近的 k 个邻居，k 越小模型越复杂", "统计 k 个近邻里正类的票数", "过半判 1、否则判 0，平票倾向负类", "预测与标签不符就记一次错误", "返回错误率并保留三位小数，便于核对", "遍历 5 个 k 值，构造验证曲线", "同一 k 分别算训练误差与验证误差，观察 U 型"]' title='第 102 讲 · 模型调优：交叉验证、正则化与过拟合' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import statistics as st
preds = [11.2, 9.5, 10.8, 12.1, 8.9]
truth = 10.0
bias = st.mean(preds) - truth
var = st.variance(preds)
print('mean pred', round(st.mean(preds), 3))
print('bias^2', round(bias ** 2, 3))
print('variance', round(var, 3))
print('MSE approx', round(bias ** 2 + var, 3))
```

<OutputBox title='原理验证' output='mean pred 10.5\nbias^2 0.25\nvariance 1.675\nMSE approx 1.925' />

**偏差方差诊断：按曲线形态决定动作**

| 曲线形态 | 诊断 | 该做的动作 |
| --- | --- | --- |
| 训练误差低、验证高、间隙大 | 高方差 / 过拟合 | 加数据、加正则、降复杂度、早停 |
| 训练与验证都高且贴近 | 高偏差 / 欠拟合 | 加特征、减正则、换更强模型 |
| 验证误差随容量先降后升 | 存在最优容量 | 取 U 型最低点的超参 |
| 验证误差随 n 增大仍下降 | 数据仍不够 | 继续加数据 |

<ConceptDiagram type='layers3' title='第 102 讲 · 偏差方差分解、学习曲线与验证曲线' labels='偏差方差分解、学习曲线与验证曲线|网格、随机、贝叶斯搜索与交叉验证|正则、早停、类别不平衡与选择陷阱' caption='系统性地提升泛化能力' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 网格、随机与贝叶斯搜索的取舍

选超参的标准工具是搜索加交叉验证。GridSearchCV 对给定网格穷举：d 个参数各取 m 个值就有 m^d 组，每组再乘 k 折训练，维度一高组合数爆炸（3 个参数各 10 个值就是 1000 组 × 5 `折 = 5000` 次拟合）。

RandomizedSearchCV 从参数的分布里随机采样固定预算的组合，Bergstra 与 Bengio 的实证与理论都表明：当只有少数参数真正重要、或搜索空间维度较高时，随机搜索比网格搜索更高效，因为网格会在不重要的维度上浪费大量重复取值。

贝叶斯优化（TPE、高斯过程、SMAC）用已评估点的分数建一个代理模型，再按采集函数（EI / UCB）挑「最值得试」的下一个点，样本效率最高、适合单次训练很贵的场景，代价是序列依赖、并行度低且实现更复杂。

三者都要配交叉验证：分类用 StratifiedKFold（默认 5 折，保持各类比例，时序数据必须用 TimeSeriesSplit 禁止用未来折训练过去），分数取 k 折均值与标准差，既稳又给出波动。最关键的架构是嵌套交叉验证：外层折负责评估、内层折负责选超参，把「选择」与「评估」彻底隔离。

搜索空间、随机种子、每折分数、数据快照与库版本都要记录，否则最优结果无法复现。

**超参搜索方法对照**

| 方法 | 采样方式 | 复杂度 | 适用 |
| --- | --- | --- | --- |
| GridSearchCV | 穷举笛卡尔积 | m^d 组 × k 折 | 参数少、取值离散 |
| RandomizedSearchCV | 从分布随机采样 | 固定预算 | 高维、少数参数重要 |
| 贝叶斯优化 | 代理模型 + 采集函数 | 序列、样本效率高 | 单次训练昂贵 |
| 嵌套交叉验证 | 外层评估 / 内层搜索 | 两层 k 折相乘 | 需要无偏报告 |


## 嵌套交叉验证：内层选参、外层评估

```python
grid = [(k, knn_err(train, valid, k)) for k in (1, 3, 5, 7, 9)]
best_k = min(grid, key=lambda t: t[1])[0]
print('grid', grid)
print('best_k', best_k)
```

<OutputBox title='对照写法：先自己猜，再点开' output='grid [(1, 0.333), (3, 0.167), (5, 0.0), (7, 0.0), (9, 0.5)]\nbest_k 5' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import math\ntrain = [(1, 0), (2, 0), (3, 1), (4, 0), (5, 0), (6, 1), (7, 1), (8, 1), (9, 1)]\nvalid = [(2.5, 0), (3.5, 0), (4.5, 0), (5.5, 1), (6.5, 1), (8.5, 1)]\ndef knn_err(train, data, k):\n    wrong = 0\n    for x, lab in data:\n        near = sorted(train, key=lambda r: abs(r[0] - x))[:k]\n        votes = sum(1 for _, l in near if l == 1)\n        pred = 1 if votes &gt; k / 2 else 0\n        wrong += int(pred != lab)\n    return round(wrong / len(data), 3)\nfor k in (1, 3, 5, 7, 9):\n    print(&#39;k&#39;, k, &#39;train_err&#39;, knn_err(train, train, k), &#39;valid_err&#39;, knn_err(train, valid, k))", "note": "偏差方差分解、学习曲线与验证曲线"}, {"label": "对照 / 进阶", "code": "grid = [(k, knn_err(train, valid, k)) for k in (1, 3, 5, 7, 9)]\nbest_k = min(grid, key=lambda t: t[1])[0]\nprint(&#39;grid&#39;, grid)\nprint(&#39;best_k&#39;, best_k)", "note": "网格、随机、贝叶斯搜索与交叉验证"}]' title='两种写法对照' note='差异集中在 偏差方差分解；先看输出，再找背后的规则。' />


## 正则与早停：给容量装刹车

控制过拟合的手段各有适用点：L2 正则把权重整体收缩、L1 产生稀疏，dropout 在训练时随机失活神经元，早停则在独立验证集指标连续 patience 轮不改善时停止并回滚到最佳迭代。

数据层面的类别不平衡要单独处理：过采样（SMOTE 在特征空间插值生成少数类样本，须只在训练折内做，否则泄漏）、欠采样多数类、class_weight='balanced' 按类别频率反比加权、或按业务代价调整决策阈值；

指标相应换成 PR-AUC、F1、recall，别再只看 accuracy，也不要用对不平衡过于乐观的 ROC-AUC 单独下结论。阈值本身是一个待调超参，但必须在验证集上调、在测试集上只评估一次。最常见的模型选择陷阱有两类：一是在测试集上反复调参、反复看分数，把它变成验证集，最终报告虚高；

二是多重比较——试了上百组配置后汇报最好的那组，最优分数本身带选择偏差，应保留一份从未参与任何决策的测试集做一次性最终报告。此外还要防「先在全量上做特征选择 / 标准化再交叉验证」这类泄漏：所有会学习的预处理都要放进 Pipeline，只在训练折 fit。

失效信号很明确——离线分数远高于线上，优先查泄漏、分布漂移与指标口径，而不是继续加大模型。

**类别不平衡处理对照**

| 手段 | 做法 | 风险 |
| --- | --- | --- |
| 过采样 SMOTE | 少数类插值造样本 | 必须在训练折内做，否则泄漏 |
| class_weight='balanced' | 按频率反比加权 | 可能放大噪声样本权重 |
| 调整阈值 | 按业务代价下移/上移 | 须在验证集调、测试集只评估一次 |
| 换指标 | PR-AUC / F1 / recall | accuracy 与 ROC-AUC 会偏乐观 |


## 类别不平衡：StratifiedKFold 与 PR-AUC

<Callout type="warn" title='本讲最容易踩的坑' text='在测试集上反复调参，报告 0.93 上线只有 0.7：测试集参与决策后退化为验证集，最优分数带选择偏差，不再无偏' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 在测试集上反复调参，报告 0.93 上线只有 0.7 | 测试集参与决策后退化为验证集，最优分数带选择偏差，不再无偏 | 用嵌套交叉验证内层选参、外层评估；固定一份从未参与决策的测试集只做一次性最终报告 |
| 极不平衡数据用 accuracy、交叉验证不分层 | accuracy 被多数类主导，未分层的折里正类可能几乎为零、分数剧烈波动 | 用 StratifiedKFold，指标换 PR-AUC/F1/recall，配合 class_weight 或阈值调整 |
| 先在全量做特征选择/标准化再交叉验证 | 预处理参数在全量 fit，测试折信息泄进训练，分数虚高 | 把预处理放进 Pipeline 只在训练折 fit；SMOTE 等重采样也只在训练折内做 |


## 超参搜索的选择偏差从哪里来

把模型预测 f̂(x) 看作依赖训练集 D 的随机变量，对 E_D[(y - f̂)²] 做代数展开可得 (E_D[f̂] - f)² + E_D[(f̂ - E_D[f̂])²] + σ²，即偏差平方、方差与不可约噪声三项。

模型容量增大时偏差单调降、方差单调升，二者之和的极小值决定最优复杂度，这正是验证曲线呈 U 型的数学来源。kNN 的 k 提供了直观旋钮：`k=1` 时预测完全跟随最近样本（方差最大、偏差最小），k 接近 n 时预测退化为常数先验（偏差最大、方差最小）。交叉验证把数据轮流留一份验证，给出 k 个分数的均值与标准差；

但只要同一份测试集被用于挑选超参，它就带上了选择偏差——试 m 组配置取最大值，max 的期望严格大于任一单组的期望，报告分数系统性偏高，这就是嵌套交叉验证与「测试集只用一次」必须存在的理由。随机搜索之所以常优于网格，是因为在 d 维空间里网格对每个重要维度只取到 m 个不同值，而随机采样能让每个维度都覆盖到更多不同取值。

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：在测试集上反复调参，报告 0.93 上线只有", "body": "测试集参与决策后退化为验证集，最优分数带选择偏差，不再无偏", "tip": "用嵌套交叉验证内层选参、外层评估；固定一份从未参与决策的测试集只做一次性最终报告"}, {"title": "第 2 步：极不平衡数据用 accuracy、交叉验证不", "body": "accuracy 被多数类主导，未分层的折里正类可能几乎为零、分数剧烈波动", "tip": "用 StratifiedKFold，指标换 PR-AUC/F1/recall，配合 class_weight 或阈值调整"}, {"title": "第 3 步：先在全量做特征选择/标准化再交叉验证", "body": "预处理参数在全量 fit，测试折信息泄进训练，分数虚高", "tip": "把预处理放进 Pipeline 只在训练折 fit；SMOTE 等重采样也只在训练折内做"}]' />


## 用学习曲线决定「加数据」还是「降复杂度」

线上指标不达标时，最贵的错误是盲目加模型复杂度。可复用的判据是学习曲线：把训练量从小到大分几档，每档记录训练误差与验证误差，看两条曲线是间距大（高方差、加数据有效）还是都高且贴近（高偏差、该改模型）。下面用纯标准库把这条流程写成可复跑的脚本：base 是可用的全部样本，逐个比例切出前 n 条训练，验证集固定，打印每档的验证误差。

它要说明的是决策依据来自曲线趋势而非单点分数，且验证误差随数据量会有小幅波动，需结合多档趋势判断。

真实项目把 knn_err 换成 cross_val_score 的 k 折均值，把 n 档换成 `sklearn.model_selection.learning_curve`，口径一致——关键是验证集全程固定、不参与训练。

```python
def knn_err(train, data, k):
    wrong = 0
    for x, lab in data:
        near = sorted(train, key=lambda r: abs(r[0] - x))[:k]
        votes = sum(1 for _, l in near if l == 1)
        wrong += int((1 if votes > k / 2 else 0) != lab)
    return wrong / len(data)

base = [(1, 0), (2, 0), (3, 0), (4, 1), (6, 0), (7, 1), (8, 1), (9, 1),
        (5, 0), (10, 1), (11, 1), (12, 0)]
valid = [(2.5, 0), (5.5, 1), (8.5, 1), (3.5, 0), (6.5, 1)]
for frac in (0.3, 0.6, 1.0):
    n = max(3, int(len(base) * frac))
    tr = base[:n]
    print('n', n, 'valid_err(k=3)', round(knn_err(tr, valid, 3), 3))
```

<Callout type="idea" title='落地提示' text='嵌套交叉验证或固定一份从未参与决策的测试集；搜索空间与结果全部记录，保证可复现' />

<CheckList id='P102b' title='上线前自检' :items='["能复现并解释「在测试集上反复调参，报告 0.93 上线只有 0.7」", "能复现并解释「极不平衡数据用 accuracy、交叉验证不分层」", "能复现并解释「先在全量做特征选择/标准化再交叉验证」", "能用一条命令验证 偏差方差分解", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from collections import Counter; print(Counter([0,0,1]).most_common(1))"
```

把输入换成你自己的数据，观察结果是否仍符合 **偏差方差分解** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 偏差方差等式的逐项推导：交叉项为什么归零

设真实关系 `y = f`(x) + eps，eps 与 x 独立、E`[eps]`=0、`Var(eps)`=sigma^2；训练集 D 随机抽出，`f_D(x)` 是在 D 上拟合的预测，记 `f_bar(x)` = E_D[`f_D(x)`]。

把期望泛化误差展开：E[(y - f_D)^2] = E[(f + eps - f_bar + f_bar - f_D)^2]。按 eps 与 D 独立拆：E[eps^2] = sigma^2，且 E`[eps]`=0 让含 eps 的交叉项消失，剩下 E_D[(f - f_D)^2]。

再把 f - f_D 写成 (f - f_bar) + (f_bar - f_D)，平方得三项；对 D 取期望时 f 与 f_bar 是常数，E_D[f_bar - f_D] = 0，交叉项归零。

第一项即 Bias^2 = (f - f_bar)^2，第二项即 `Var = E_D`[(f_D - f_bar)^2]，最终 E[(y - f_D)^2] = Bias^2 + Var + sigma^2。关键前提有三个：噪声均值为零且与训练集独立、期望是对「反复重抽训练集」而非单次划分、f_bar 定义在这族数据集上。

若在同一份固定划分上反复调参，f_D 之间不再独立，Var 的估计被压低，交叉项也不再严格为零——这正是「在测试集上刷分」让公式失效的机制。sigma^2 是噪声地板；容量增大时 Bias^2 降、Var 升，U 型最优点由此而来。

<ConceptDiagram type='flow4' title='第 102 讲 · 扩展图解' labels='y=f+eps|f_D 随 D 波动|Bias^2|Var+sigma^2' caption='偏差方差分解的三项来源：噪声地板 sigma^2 不可约，模型容量只改变前两项之和；交叉项因 E[f_bar-f_D]=0 归零' />


## winner's curse：试 N 组配置后最优分数的乐观偏差

```python
def lcg(seed, n):
    out, x = [], seed
    for _ in range(n):
        x = (1103515245 * x + 12345) % (1 << 31)
        out.append(x / (1 << 31))
    return out

def optimism(n_configs, trials, seed):
    us = lcg(seed, n_configs * trials)
    total = 0.0
    for t in range(trials):
        chunk = us[t * n_configs:(t + 1) * n_configs]
        best = max(0.80 + (u - 0.5) * 0.06 for u in chunk)
        total += best - 0.80
    return round(total / trials, 4)

for n in (1, 5, 20, 100):
    print('n', n, 'mean_optimism', optimism(n, 200, 20240607))
```

<OutputBox title='扩展示例运行结果' output='n 1 mean_optimism 0.0006\nn 5 mean_optimism 0.0203\nn 20 mean_optimism 0.0269\nn 100 mean_optimism 0.0294' />

<LineByLine code='def lcg(seed, n):\n    out, x = [], seed\n    for _ in range(n):\n        x = (1103515245 * x + 12345) % (1 &lt;&lt; 31)\n        out.append(x / (1 &lt;&lt; 31))\n    return out\n\ndef optimism(n_configs, trials, seed):\n    us = lcg(seed, n_configs * trials)\n    total = 0.0\n    for t in range(trials):\n        chunk = us[t * n_configs:(t + 1) * n_configs]\n        best = max(0.80 + (u - 0.5) * 0.06 for u in chunk)\n        total += best - 0.80\n    return round(total / trials, 4)\n\nfor n in (1, 5, 20, 100):\n    print(&#39;n&#39;, n, &#39;mean_optimism&#39;, optimism(n, 200, 20240607))' :notes='["确定性线性同余发生器，避免依赖 random 模块的版本差异", "每组真实分数统一设为 0.80，best 减 0.80 纯粹是选择偏差", "对固定 N 重复 200 次实验估计 E[max eta]，输出随 N 单调上升", "Grid 组合 m^d 爆炸；高维少数参数重要时随机/贝叶斯搜索更高效", "嵌套交叉验证内层选参、外层评估；测试集只用一次，防选择偏差", "不平衡用 StratifiedKFold + PR-AUC/F1/recall + class_weight/阈值；预处理进 Pipeline 只 fit 训练折", "MSE = Bias² + Variance + σ²；模型越复杂偏差越小、方差越大，最优容量在 U 型底部", "学习曲线看 n：间隙大=高方差（加数据），都高且贴近=高偏差（加特征/减正则）", "验证曲线看超参：训练误差单调降、验证误差先降后升，取最低点", "Grid 组合 m^d 爆炸；高维少数参数重要时随机/贝叶斯搜索更高效", "嵌套交叉验证内层选参、外层评估；测试集只用一次，防选择偏差", "不平衡用 StratifiedKFold + PR-AUC/F1/recall + class_weight/阈值；预处理进 Pipeline 只 fit 训练折", "MSE = Bias² + Variance + σ²；模型越复杂偏差越小、方差越大，最优容量在 U 型底部", "学习曲线看 n：间隙大=高方差（加数据），都高且贴近=高偏差（加特征/减正则）", "验证曲线看超参：训练误差单调降、验证误差先降后升，取最低点", "Grid 组合 m^d 爆炸；高维少数参数重要时随机/贝叶斯搜索更高效"]' title='扩展示例逐行讲解' />

把「试了 N 组超参、汇报最好的那组」写成概率问题：设每组真实泛化分数都是 mu，验证分数是 mu + eta，eta 是零均值噪声（来自验证集有限、折划分与随机种子）。

汇报量是 mu + `max(eta_1..eta_N)`，其期望比 mu 高 E[max eta]。

eta 近似正态、标准差 sigma 时，N 个独立样本最大值的期望约按 sigma·`sqrt(2 ln N)` 增长：N 从 10 涨到 200 偏差翻一倍以上，且与 sigma 成正比——验证集越小、类别越不平衡，虚高越严重。这不是运气好，而是最大次序统计量自带的正向偏置，叫 winner's curse 或选择偏差。

它解释了离线 0.93、线上 0.70：那 0.23 里有一大块是把验证噪声当成模型能力买下来了。修复不是少试几组，而是把选择与评估隔离：外层折只做一次性评估，内层折负责选超参，即嵌套交叉验证；

scikit-learn 1.x 的 `BaseSearchCV.fit` 与 _run_search 在 sklearn/model_selection/`_search.py`，cross_val_score 在 `_validation.py`，外层再包一层即可。

Optuna 的 optuna/samplers/_tpe/`sampler.py` 用 TPE 按 `l(x)`/`g(x)` 分组最大化期望改进，同样放大选择偏差，测试集仍须一次未用。


## 随机搜索的低有效维度论证与嵌套 CV 的无偏估计

**选择偏差量级：E[max eta] 近似 sigma·sqrt(2 ln N)**

| 配置数 N | 验证噪声 sigma | 乐观偏差近似 | 所需隔离手段 |
| --- | --- | --- | --- |
| 1 | 0.02 | 0.000 | 单次划分即可，不存在选择 |
| 10 | 0.02 | 0.043 | 固定验证集，记录全部结果 |
| 50 | 0.02 | 0.056 | 嵌套 CV 或独立测试集 |
| 200 | 0.05 | 0.163 | 先扩大验证集或降 sigma 再选 |

一次信贷评分上线复盘：团队在 1.2 万条样本上做 180 组网格搜索，用同一份 20% 验证集挑出 `AUC=0.891` 的最优组合，又在这份验证集上把阈值从 0.5 调到 0.43，分数涨到 0.902 遂以 0.90 立项，上线首月真实 AUC 只有 0.812。

事后重跑 180 组发现最优组比中位数高 0.061，用 5000 条独立测试集评估时差距只有 0.004——0.057 几乎全是验证噪声被 max 选中。阈值 0.43 更糟：按「让 F1 最大」在同一批样本上挑，等于把验证集的类别比例也拟合了进去。

下面复现「同一批数据既选又评」与「外层折独立评估」的差值，外层样本固定取自不参与内层选择的段落，估计值不随 N 漂移。

```python
def lcg(seed, n):
    out, x = [], seed
    for _ in range(n):
        x = (1103515245 * x + 12345) % (1 << 31)
        out.append(x / (1 << 31))
    return out

def report(n_configs, us):
    inner = [0.80 + (u - 0.5) * 0.06 for u in us[:n_configs]]
    outer = [0.80 + (u - 0.5) * 0.06 for u in us[1000:1100]]
    best = max(inner)
    nested = sum(outer) / len(outer)
    return round(best, 4), round(nested, 4), round(best - nested, 4)

us = lcg(20240607, 2000)
for n in (10, 60, 180):
    print('configs', n, 'selected_vs_nested', report(n, us))
```

<Quiz no='102-X' q='把 180 组超参在同一份验证集上取最优后直接汇报该分数，主要问题是什么？' :options='["max 是次序统计量，会把验证噪声的正尾部一起选中，汇报值带正向选择偏差，与真实泛化能力无关", "验证集分数总是系统性低于测试集分数", "配置数越多模型本身越复杂，必然导致过拟合", "只要用 GridSearchCV 封装搜索就不会产生偏差"]' answer="0" explain='每组验证分数是真实能力加零均值噪声，N 组取 max 的期望约以 sigma·sqrt(2 ln N) 偏离 mu；这是最大次序统计量的偏置，不是模型变差。隔离办法是嵌套 CV 或一份从未参与决策的独立测试集。' />

<Exercise title='进阶：实现期望改进 EI 的解析式并解释探索项' task='实现 EI = (mu - f*)·Phi(z) + sigma·phi(z)，z=(mu-f*)/sigma、Phi 由 erf 给出、phi 是标准正态密度；对 f*=0.81 比较三个候选点的 EI。' solution='import math\n\ndef ei(mu, sigma, f_best):\n    if sigma &lt;= 0:\n        return max(0.0, mu - f_best)\n    z = (mu - f_best) / sigma\n    Phi = 0.5 * (1 + math.erf(z / math.sqrt(2)))\n    phi = math.exp(-0.5 * z * z) / math.sqrt(2 * math.pi)\n    return (mu - f_best) * Phi + sigma * phi\n\nfor mu, sigma in [(0.82, 0.02), (0.80, 0.05), (0.78, 0.10)]:\n    print(&#39;mu&#39;, mu, &#39;sigma&#39;, sigma, &#39;EI&#39;, round(ei(mu, sigma, 0.81), 4))' explain='EI 由 exploitation 项 (mu-f*)·Phi(z) 与 exploration 项 sigma·phi(z) 组成；mu 低于当前最优但 sigma 大时 EI 仍可能为正，代理模型会自动在不确定区域投点。' />


## 练习与速记：调参不越界

<Exercise title='基础：读出验证曲线的最优 k' task='用 code 的 train/valid 与 knn_err，打印 k=1,3,5,7,9 的验证误差，说明为什么最优 k 在中间而不是最小的 1 或最大的 9。' solution='def knn_err(train, data, k):\n    wrong=0\n    for x,lab in data:\n        near=sorted(train,key=lambda r:abs(r[0]-x))[:k]\n        votes=sum(1 for _,l in near if l==1)\n        wrong+=int((1 if votes&gt;k/2 else 0)!=lab)\n    return round(wrong/len(data),3)\ntrain=[(1,0),(2,0),(3,1),(4,0),(5,0),(6,1),(7,1),(8,1),(9,1)]\nvalid=[(2.5,0),(3.5,0),(4.5,0),(5.5,1),(6.5,1),(8.5,1)]\nfor k in (1,3,5,7,9): print(k, knn_err(train,valid,k))' explain='k=1 记下噪声点、方差大导致验证误差 0.333；k=9 把两类平均成常数、偏差大升到 0.5；k=5 兼顾两者验证误差降到 0，最优点在中间，正是偏差方差权衡。' />

<Exercise title='进阶：手算偏差方差分解' task='对 preds=[11.2,9.5,10.8,12.1,8.9]、真值 10.0，用 statistics 计算 bias²、variance 与二者之和，说明第三项 σ² 为什么无法消除。' solution='import statistics as st\np=[11.2,9.5,10.8,12.1,8.9]; t=10.0\nb=st.mean(p)-t; v=st.variance(p)\nprint(&#39;bias^2&#39;,round(b**2,3),&#39;var&#39;,round(v,3),&#39;sum&#39;,round(b**2+v,3))' explain='bias²=0.25、variance=1.675、二者之和 1.925；第三项 σ² 是数据本身的观测噪声与不可约随机性，任何模型都无法把它降为零，只能减小前两项。' />

<Quiz no='102-1' q='学习曲线显示训练误差很低、验证误差高且两者间隙很大，该优先做什么？' :options='["加数据、加正则或降复杂度（高方差过拟合）", "继续加大模型容量", "换更强的特征一定有用", "提高 learning_rate"]' answer="0" explain='间隙大是高方差的典型信号，模型把训练集记住了却泛化差；加数据、正则、降复杂度或早停对症。若两者都高且贴近才是高偏差，需要加特征或换模型。' />

<Quiz no='102-2' q='关于在测试集上调参，下面哪项准确？' :options='["测试集一旦参与决策就退化为验证集，最终分数失去无偏性", "只要调参次数少于 10 次就没问题", "分数会更保守", "用更大网格就能抵消"]' answer="0" explain='反复在测试集挑超参等于把它当验证集，且取多组配置的最大值本身带选择偏差，报告分数系统性偏高。应保留一份只用一次的测试集，或做嵌套交叉验证。' />

<Quiz no='102-3' q='参数维度高、只有少数参数真正重要时，更高效的搜索通常是？' :options='["随机搜索或贝叶斯优化", "更密的网格搜索", "只调一个参数其余取默认", "不搜索直接用默认值"]' answer="0" explain='网格在不重要维度上浪费大量重复取值；随机搜索让每个维度覆盖更多不同值，贝叶斯优化进一步用代理模型挑值得试的点，样本效率更高。' />

<Predict no='102-P' q='前面 alt 的网格搜索里，best_k 会取到哪个值？' :options='["5", "1", "9"]' answer='0' output='best_k 5' explain='grid 里 k=5 与 k=7 的 valid_err 都是最小的 0.0，min 按稳定顺序取第一个最小值得到 5；k=1 过拟合(0.333)、k=9 欠拟合(0.5)，最优点落在中间。' />

<FillBlank no='102-F' tpl='___ math' :answers='["import"]' hint='回想本讲关于 偏差方差分解 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 偏差方差分解、学习曲线与验证曲线 的落点。' />

<KnowledgeCard :points='["MSE = Bias² + Variance + σ²；模型越复杂偏差越小、方差越大，最优容量在 U 型底部", "学习曲线看 n：间隙大=高方差（加数据），都高且贴近=高偏差（加特征/减正则）", "验证曲线看超参：训练误差单调降、验证误差先降后升，取最低点", "Grid 组合 m^d 爆炸；高维少数参数重要时随机/贝叶斯搜索更高效", "嵌套交叉验证内层选参、外层评估；测试集只用一次，防选择偏差", "不平衡用 StratifiedKFold + PR-AUC/F1/recall + class_weight/阈值；预处理进 Pipeline 只 fit 训练折"]' :pitfalls='["在测试集上反复调参，报告 0.93 上线只有 0.7", "极不平衡数据用 accuracy、交叉验证不分层", "先在全量做特征选择/标准化再交叉验证", "在测试集上反复调参，等于把测试集变成验证集，最终报告的分数毫无意义"]' summary='调参的本质是在「模型容量」与「数据量」之间找平衡，学习曲线能直接告诉你该加数据还是该降复杂度' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| MSE = Bias² + Variance + σ²；模型越复杂偏差越小、方差越大，最优容量在 U 型底部 | 建立直觉 |
| 学习曲线看 n：间隙大=高方差（加数据），都高且贴近=高偏差（加特征/减正则） | 跑通示例 |
| 验证曲线看超参：训练误差单调降、验证误差先降后升，取最低点 | 深入边界 |
| Grid 组合 m^d 爆炸；高维少数参数重要时随机/贝叶斯搜索更高效 | 工程落地 |
| 嵌套交叉验证内层选参、外层评估；测试集只用一次，防选择偏差 | 随堂检测 |
| 不平衡用 StratifiedKFold + PR-AUC/F1/recall + class_weight/阈值；预处理进 Pipeline 只 fit 训练折 | 复盘 |

1. MSE = Bias² + Variance + σ²；模型越复杂偏差越小、方差越大，最优容量在 U 型底部

2. 学习曲线看 n：间隙大=高方差（加数据），都高且贴近=高偏差（加特征/减正则）

3. 验证曲线看超参：训练误差单调降、验证误差先降后升，取最低点

[下一讲：深度学习与 PyTorch：张量、自动微分与训练循环](/data-ai/deep-learning)
