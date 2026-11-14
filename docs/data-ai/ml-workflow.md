---
title: 第 097 讲 · 机器学习流程：特征、划分与评价
description: 建立不会自欺的建模与评估流程
---

<StageHeader stage='L9 · 数据与 AI' level='★★★☆☆' time='40 分钟' goal='建立不会自欺的建模与评估流程' prereq='第 096 讲 · 统计基础：分布、检验与相关性' />

# 第 097 讲 · 机器学习流程：特征、划分与评价

描述、画图、判断都过了一遍，数据这头算摆整齐了。从这里转向模型，但第一步不是挑算法，而是先搭一套不会自欺的流程：先在全量上标准化再切分，或拿 99% 准确率去评欺诈检测，分数漂亮，上线却会垮。机器学习里最贵的错误常出在评估口径上。

先讲训练集、验证集、测试集怎么切，数据泄漏藏在哪，并把预处理放进 Pipeline 只在训练折拟合；接着从混淆矩阵推出分类该盯哪个指标；最后用交叉验证与一个朴素基线收口。需要 Pandas 整理功夫、NumPy 运算，以及函数、字典和上一讲的统计判断。学完能把预测任务切成可信的评估流程，交出不被虚高分数骗到的基线。


## 在测试集上反复调参，0.93 上线只剩 0.7

一个欺诈检测模型离线报告准确率 99.4%，评审一片叫好，上线后一周却几乎没拦住任何一笔欺诈。复盘发现数据里正样本只占 0.6%，模型把所有交易都判成『正常』就能拿到 99.4%；而真正该看的召回率其实是 0。

第二个坑更隐蔽：团队先在全量数据上做特征选择、算好标准化参数，再切训练集与测试集，测试分数一路虚高，因为测试集的分布信息已经渗进了预处理。还有人把类别不平衡的测试集也用 accuracy 汇报，把『全部预测多数类』当成强基线。这些都不是算法不够复杂，而是评估流程本身在自欺。

本讲把『不会自欺的建模流程』落到划分、指标与基线三件可核对的事上。

<Callout type="warn" title='先看一个真实会出错的写法' text='先在全量数据上标准化或做特征选择再划分：预处理的均值/方差/入选列也是从数据学到的参数，全量 fit 会把测试折信息泄进训练' />


## 训练集、验证集与测试集各自的职责

标准流程把数据切成三份：训练集用于拟合模型参数，验证集用于选超参与早停，测试集只在最终评估时用一次，绝不参与任何决策。常见比例是 6/2/2 或 7/1.5/1.5，分类任务要用 stratify 保持各类比例，时间序列必须按时间切而不能随机打乱，否则未来的信息会泄进训练。

数据泄漏指本该只在训练阶段获得的信息被提前用到全量或测试：先在全量上 fit 标准化器（均值、标准差）、先在全量上做特征选择、用含目标信息的特征、或把同一用户的多条记录随机分到训练与测试两侧，都会让分数虚高却无法泛化。

根因是『预处理也是从数据里学到的参数』，scaler 的均值与方差、特征选择的入选列、目标编码的映射，都必须只在训练折上 fit，再 transform 到验证/测试折。

scikit-learn 的 Pipeline 把这一切固化：`make_pipeline(StandardScaler(),SelectKBest(...),LogisticRegression())` 配合 `cross_val_score` 或 `GridSearchCV`，保证每一次交叉验证都只在对应训练折内 fit 预处理，测试折永远只是被动 transform。

把『先划分、后 fit、预处理进 Pipeline』写成铁律，是评估可信的前提。

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段九 · 数据科学与 AI 工程 |
| 前置 | 第 096 讲 · 统计基础：分布、检验与相关性 |
| 难度 / 建议时长 | ★★★☆☆ · 40 分钟 |
| 本讲新增 | 训练集 / 验证集 / 测试集、数据泄漏、特征工程与缩放 |
| 一句话目标 | 建立不会自欺的建模与评估流程 |
| 为下一讲铺垫 | 经典算法：KNN、线性与逻辑回归 |


## 数据泄漏：先标准化再划分为什么分数虚高

二分类的全部指标都能从混淆矩阵四个数推出：TP 真正例、FP 假正例、FN 假反例、TN 真反例。

准确率 `accuracy=(TP+TN)/N`（N 为样本总数），精确率 `precision=TP/(TP+FP)` 衡量『报出来的有多少是真的』，召回率 `recall=TP/(TP+FN)` 衡量『真的里抓到了多少』，F1 是二者的调和平均 `2*P*R/(P+R)`。

极不平衡数据里，全预测负类可让 accuracy 高达 0.99 却 `recall=0`，所以不能用 accuracy 单指标；要按业务代价选：欺诈、疾病筛查漏报代价高，优先 recall 或 PR-AUC；垃圾邮件误拦代价高，优先 precision。

ROC-AUC 衡量把正样本排在负样本前的概率，对类别不平衡相对稳健，但正样本极少时 PR-AUC 更敏感。阈值不是固定的 0.5：降低阈值会提高 recall、牺牲 precision，要按代价画 PR 曲线选工作点。

多分类要说明 macro（各类等权）、micro（按样本数加权）、weighted 平均的区别，macro 在小类上更诚实。回归指标则是 MAE（对离群点稳健）、MSE/`RMSE`（对大误差惩罚更重）、R²（相对基线的解释方差），选择同样取决于业务对大误差的容忍度。

```python
def metrics(tp, fp, fn, tn):
    acc = (tp + tn) / (tp + fp + fn + tn)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return dict(accuracy=round(acc, 3), precision=round(prec, 3),
                recall=round(rec, 3), f1=round(f1, 3))

print('all-negative', metrics(0, 0, 10, 990))
print('a-model', metrics(5, 20, 5, 970))
```

<OutputBox title='主示例运行结果' output='all-negative {&#39;accuracy&#39;: 0.99, &#39;precision&#39;: 0.0, &#39;recall&#39;: 0.0, &#39;f1&#39;: 0.0}\na-model {&#39;accuracy&#39;: 0.975, &#39;precision&#39;: 0.2, &#39;recall&#39;: 0.5, &#39;f1&#39;: 0.286}' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def metrics(tp, fp, fn, tn):\n    acc = (tp + tn) / (tp + fp + fn + tn)\n    prec = tp / (tp + fp) if tp + fp else 0.0\n    rec = tp / (tp + fn) if tp + fn else 0.0\n    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0\n    return dict(accuracy=round(acc, 3), precision=round(prec, 3),\n                recall=round(rec, 3), f1=round(f1, 3))\n\nprint(&#39;all-negative&#39;, metrics(0, 0, 10, 990))\nprint(&#39;a-model&#39;, metrics(5, 20, 5, 970))' :notes='["定义从混淆矩阵四数推导全部指标的函数", "准确率是判对样本占总数的比例", "精确率衡量报出的正例里有多少是真的，分母为 TP+FP", "召回率衡量真实正例里抓到多少，分母为 TP+FN", "F1 是精确率与召回率的调和平均，任一项低就整体低", "返回四个指标并四舍五入，便于核对", "构造 1000 样本、10 个正例的不平衡场景，模型全预测负例", "空行，只用于分隔逻辑块，不影响执行结果。", "全预测多数类时 TP=0、FP=0、FN=10、TN=990", "打印基线：准确率 0.99 但召回与 F1 全为 0"]' title='第 097 讲 · 机器学习流程：特征、划分与评价' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**分类指标公式与侧重**

| 指标 | 公式 | 回答的问题 | 适用 |
| --- | --- | --- | --- |
| accuracy | (TP+TN)/N | 整体判对比例 | 类别均衡 |
| precision | TP/(TP+FP) | 报出的正例有多准 | 误报代价高 |
| recall | TP/(TP+FN) | 正例抓到了多少 | 漏报代价高 |
| F1 | 2PR/(P+R) | 精确与召回的平衡 | 不平衡单指标 |
| ROC-AUC | 正例排在负例前的概率 | 排序质量 | 对不平衡较稳 |


### 把预处理放进 Pipeline，只在训练折 fit

```python
def mean(a): return sum(a) / len(a)
def pstd(a):
    m = mean(a)
    return (sum((x - m) ** 2 for x in a) / len(a)) ** 0.5
def zscore(xs, m, s): return [round((x - m) / s, 2) for x in xs]

train = [1, 2, 3, 4, 5]
test = [20, 21, 22]
all_ = train + test
print('leak', zscore(test, mean(all_), pstd(all_)))
print('clean', zscore(test, mean(train), pstd(train)))
```

<OutputBox title='对照写法：先自己猜，再点开' output='leak [1.16, 1.28, 1.39]\nclean [12.02, 12.73, 13.44]' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "def metrics(tp, fp, fn, tn):\n    acc = (tp + tn) / (tp + fp + fn + tn)\n    prec = tp / (tp + fp) if tp + fp else 0.0\n    rec = tp / (tp + fn) if tp + fn else 0.0\n    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0\n    return dict(accuracy=round(acc, 3), precision=round(prec, 3),\n                recall=round(rec, 3), f1=round(f1, 3))\n\nprint(&#39;all-negative&#39;, metrics(0, 0, 10, 990))\nprint(&#39;a-model&#39;, metrics(5, 20, 5, 970))", "note": "划分、数据泄漏与 Pipeline"}, {"label": "对照 / 进阶", "code": "def mean(a): return sum(a) / len(a)\ndef pstd(a):\n    m = mean(a)\n    return (sum((x - m) ** 2 for x in a) / len(a)) ** 0.5\ndef zscore(xs, m, s): return [round((x - m) / s, 2) for x in xs]\n\ntrain = [1, 2, 3, 4, 5]\ntest = [20, 21, 22]\nall_ = train + test\nprint(&#39;leak&#39;, zscore(test, mean(all_), pstd(all_)))\nprint(&#39;clean&#39;, zscore(test, mean(train), pstd(train)))", "note": "分类指标：从混淆矩阵推导出该看哪一个"}]' title='两种写法切换看' />


## 分类指标：从混淆矩阵推导出该看哪一个

单次划分的分数受随机性影响大，k 折交叉验证把数据均分成 k 份，轮流用 k-1 份训练、1 份验证，得到 k 个分数取均值与标准差，既更稳又给出波动范围；

分类用 `StratifiedKFold` 保持比例，时间序列用 `TimeSeriesSplit` 禁止未来折训练过去。

嵌套交叉验证把『选超参』与『评估』再分两层：外层评估、内层网格搜索，避免在测试集上反复调参把它退化成验证集。

任何复杂模型之前必须先做可解释的基线：分类用 `DummyClassifier(strategy='most_frequent')` 或先验概率，回归用 `DummyRegressor(strategy='mean')`。

基线的意义是给出『不看特征也能达到的地板』，如果复杂模型只比基线好一点，就要怀疑特征、泄漏或指标口径。还要固定随机种子、记录数据快照与版本，让评估可复现。最典型的失效信号是『离线分数远高于线上』：优先查泄漏（预处理是否只在训练折 fit）、分布漂移、以及指标是否匹配业务代价，而不是急着换更大的模型。

```python
def kfold(n, k):
    idx = list(range(n))
    folds = [idx[i::k] for i in range(k)]
    return [([j for j in idx if j not in f], f) for f in folds]

cover = []
for i, (tr, va) in enumerate(kfold(10, 5)):
    cover.extend(va)
    print('fold', i, 'val', va, 'train_n', len(tr))
print('each sample validated once?', sorted(cover) == list(range(10)))
```

<OutputBox title='原理验证' output='fold 0 val [0, 5] train_n 8\nfold 1 val [1, 6] train_n 8\nfold 2 val [2, 7] train_n 8\nfold 3 val [3, 8] train_n 8\nfold 4 val [4, 9] train_n 8\neach sample validated once? True' />

**数据泄漏对照**

| 做法 | 是否泄漏 | 后果 |
| --- | --- | --- |
| 全量 fit StandardScaler 再划分 | 是 | 测试分布渗入，分数虚高 |
| 全量做特征选择再划分 | 是 | 用到测试折的目标/分布信息 |
| Pipeline 内每折 fit 预处理 | 否 | 预处理只学训练折 |
| 时间序列随机打乱划分 | 是 | 未来信息泄进训练 |


### 极不平衡数据里准确率为什么骗人

**数据集与切分职责**

| 集合 | 用途 | 可否调参 | 典型比例 |
| --- | --- | --- | --- |
| 训练集 | 拟合模型参数 | 否 | 60-70% |
| 验证集 | 选超参、早停 | 是 | 10-20% |
| 测试集 | 最终一次性评估 | 禁止 | 10-20% |

<Callout type="warn" title='本讲最容易踩的坑' text='先在全量数据上标准化或做特征选择再划分：预处理的均值/方差/入选列也是从数据学到的参数，全量 fit 会把测试折信息泄进训练' />


## 交叉验证与 DummyClassifier 基线

<ConceptDiagram type='layers3' title='第 097 讲 · 划分、数据泄漏与 Pipeline' labels='划分、数据泄漏与 Pipeline|分类指标：从混淆矩阵推导出该看哪一个|交叉验证与基线模型|基线模型' caption='建立不会自欺的建模与评估流程' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

<Callout type="tip" title='核心心智模型' text='标准流程把数据切成三份：训练集用于拟合模型参数，验证集用于选超参与早停，测试集只在最终评估时用一次，绝不参与任何决策。常见比例是 6/2/2 或 7/1.5/1.5，分类任务要用 stratify 保持各类比例，时间序列必须按时间切而不能随机打乱，否则未来的信息会泄进训练。数据泄漏指本该只在训练阶段…' />


## 一次划分如何决定评估的无偏性

评估可信度的核心是『信息隔离』：任何从数据里估计出来的量——scaler 的均值方差、特征选择的得分、目标编码的映射、甚至阈值——一旦在全量上计算，就把测试折的统计信息编码进了训练过程，模型相当于偷看了答案。

交叉验证把这种隔离写成机制：k 折轮流留一份验证，预处理必须放进 Pipeline，使 fit 只发生在当前训练折，验证折仅调用 transform。

指标层面，混淆矩阵是充分统计量，accuracy 在类别先验极偏时由多数类主导：当正例比例 p 很小，全预测负类的 accuracy 就是 1-p，仍可逼近 1，而 recall 恒为 0，所以指标必须由业务代价（漏报损失对误报损失）决定，而非默认 0.5 阈值或默认 accuracy。

F1 用调和平均而非算术平均，是因为调和平均对较小项敏感，能防止『precision 很高但 recall 极低』被平均成好看的分数。基线模型给出贝叶斯式地板：不利用任何特征的先验预测，是判断复杂模型是否真有增益的参照。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 先在全量数据上标准化或做特征选择再划分 | 预处理的均值/方差/入选列也是从数据学到的参数，全量 fit 会把测试折信息泄进训练 | 把 StandardScaler、特征选择全部放进 Pipeline，只在训练折 fit，用 cross_val_score 验证 |
| 用 accuracy 评价极不平衡的欺诈数据 | 正例占 0.6% 时全预测多数类就有 99.4% 准确率，掩盖 recall 为 0 | 按业务代价选 recall / precision / PR-AUC / F1，并先跑 DummyClassifier 基线 |
| 在测试集上反复调参直到满意 | 测试集被反复用于决策，等于退化成验证集，最终报告分数失去无偏性 | 用嵌套交叉验证：内层选超参、外层评估；固定一份从未参与决策的测试集只用一次 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：先在全量数据上标准化或做特征选择再划分", "body": "预处理的均值/方差/入选列也是从数据学到的参数，全量 fit 会把测试折信息泄进训练", "tip": "把 StandardScaler、特征选择全部放进 Pipeline，只在训练折 fit，用 cross_val_score 验证"}, {"title": "第 2 步：用 accuracy 评价极不平衡的欺诈数据", "body": "正例占 0.6% 时全预测多数类就有 99.4% 准确率，掩盖 recall 为 0", "tip": "按业务代价选 recall / precision / PR-AUC / F1，并先跑 DummyClassifier 基线"}, {"title": "第 3 步：在测试集上反复调参直到满意", "body": "测试集被反复用于决策，等于退化成验证集，最终报告分数失去无偏性", "tip": "用嵌套交叉验证：内层选超参、外层评估；固定一份从未参与决策的测试集只用一次"}]' />


## 可复现的评估脚本：Pipeline 式的隔离与基线对照

一个二分类任务要给出可信的离线结论，最少需要四件事：划分时保持类别比例、预处理参数只在训练折估计、同时汇报多个指标、以及一个多数类基线作地板。下面用纯标准库把这条流程写成可复跑的函数：它把样本按分层思路切成训练与测试两段，标准化参数只从训练段计算，再对测试段应用；

随后用一个『全预测多数类』的基线和一个『按阈值打分』的简易模型分别算混淆矩阵，打印各自的 accuracy 与 recall。

真实工程把 scaler 与模型换成 sklearn 的 `Pipeline`、`StratifiedKFold` 负责分层，指标口径不变；

关键是别让任何 fit 越过训练折边界。

```python
def split_stratified(rows, frac=0.7):
    pos = [r for r in rows if r[1] == 1]
    neg = [r for r in rows if r[1] == 0]
    cut = int(len(rows) * frac)
    np = int(cut * len(pos) / len(rows))
    return pos[:np] + neg[:cut - np], pos[np:] + neg[cut - np:]

def mean(a): return sum(a) / len(a)
def pstd(a):
    m = mean(a)
    return (sum((x - m) ** 2 for x in a) / len(a)) ** 0.5 or 1.0

def evaluate(train, test, threshold):
    m, s = mean([x for x, _ in train]), pstd([x for x, _ in train])
    tp = fp = fn = tn = 0
    for x, y in test:
        pred = 1 if (x - m) / s > threshold else 0
        tp += int(pred == 1 and y == 1)
        fp += int(pred == 1 and y == 0)
        fn += int(pred == 0 and y == 1)
        tn += int(pred == 0 and y == 0)
    rec = tp / (tp + fn) if tp + fn else 0.0
    acc = (tp + tn) / len(test)
    return {'acc': round(acc, 3), 'recall': round(rec, 3), 'tp': tp}

rows = [(float(i), 1 if i % 17 == 0 else 0) for i in range(100)]
tr, te = split_stratified(rows)
print('baseline', evaluate(tr, te, 1e9))
print('model', evaluate(tr, te, 1.5))
```

<Callout type="idea" title='落地提示' text='先做可解释的基线，按业务代价选指标（召回、AUC、MAE），所有预处理放进 Pipeline 并只在训练折拟合' />

<CheckList id='P097b' title='上线前自检' :items='["能复现并解释「先在全量数据上标准化或做特征选择再划分」", "能复现并解释「用 accuracy 评价极不平衡的欺诈数据」", "能复现并解释「在测试集上反复调参直到满意」", "能用一条命令验证 训练集 / 验证集 / 测试集", "关键路径有自动化测试与失败分支"]' />


## ROC-AUC 就是 Mann-Whitney U 统计量

二分类排序分数 `s(x)` 下，ROC-AUC 的定义是『随机取一个正样本与一个负样本，正样本分数高于负样本的概率』，平局记 0.5。把全部正负样本对枚举一遍，满足『正样本分数更高』的对数记为 U（Mann-Whitney U 统计量），则 AUC 等于 U 除以正样本数乘负样本数，含平局时每个平局给 U 加 0.5。

这也解释了为什么 ROC 曲线下梯形面积恰好等于这个概率：按分数从高到低扫描，每遇到一个正样本 TPR 上升 1 除以正样本数、每遇到一个负样本 FPR 前进 1 除以负样本数，累加的小矩形正是 U 除以正负样本数之积。推导带来三个判据：AUC 与阈值无关、只依赖排序；

它对类别先验不敏感，正样本占比从 1% 变到 10% 只要排序不变 AUC 不动；但正样本极少时负样本对数量巨大，AUC 会被大量『容易的负样本』稀释，PR-AUC 才对少数类敏感。

源码上 `sklearn/metrics/_ranking.py` 的 `roc_auc_score` 先由 `roc_curve` 生成 (fpr, tpr) 再走梯形积分的 `auc()`，而 `average_precision_score` 走 `_binary_uninterpolated_average_precision` 的阶梯求和，两者故意用不同插值口径，数值不能直接互相比较大小。

Bengio 与 Grandvalet 在 2004 年证明：k 折交叉验证估计的方差不存在无偏估计量，根因是 k 个训练集两两重叠。`k=10` 时任意两折训练集共享 (k-2)/(k-1)=8/9 的样本，k 个验证分数高度正相关。

数学上设每折误差为 e_i，均值的方差等于 1 除以 k 的平方，再乘上各折方差之和与所有两两协方差之和；重叠让协方差项为正且很大，而样本方差只估计了各折相对均值偏差平方之和再除以 k-1、又除以 k，相当于假装协方差全为零，系统性偏小。

工程后果很直接：用 5 折 CV 报出『正负 0.3%』的误差棒并据此宣称模型 A 优于 B，往往是假显著。正确做法是把 CV 当点估计，比较模型时改用同一折划分的配对检验（paired t 或 Wilcoxon）、重复 k 折、或在外层做 bootstrap 重采样；

嵌套 CV 的成本是外层折数乘内层折数乘网格大小的训练次数，网格一大就爆炸，这是『评估无偏』与『算力预算』之间真实的架构权衡。正文说 k 折给均值与标准差，标准差确实能算，但把它当独立样本的置信区间用就是错的。

一个团队在 40 条样本的验证集上网格搜索 50 组超参，报告最佳 AUC 0.975 并据此上线，线上只有 0.80 左右。这不是数据泄漏，而是赢家诅咒：当每组超参真实效果相同、只是验证集采样带来噪声时，取 50 个带噪估计的最大值，期望上必然高于真值，搜索空间越大、验证集越小，乐观偏差越大。

下例用 0.80 的真实分数造 50 组无关超参，每组在 40 个伯努利样本上估一次，最佳值冲到 0.975、高估 0.175，而全网格均值仍贴近 0.807。修复不是换更大的模型，而是把『选超参』放进内层 CV、用从未参与决策的外层测试集报告最终分数，或直接报告多次重复划分的分布而不是单点最大值。

```python
import random

random.seed(3)

def auc_u(pos, neg):
    u = 0.0
    for p in pos:
        for q in neg:
            u += 1.0 if p > q else 0.5 if p == q else 0.0
    return u / (len(pos) * len(neg))

def auc_trapezoid(scores, labels):
    pairs = sorted(zip(scores, labels), key=lambda t: -t[0])
    npos = sum(labels)
    nneg = len(labels) - npos
    fpr = [0.0]
    tpr = [0.0]
    tp = fp = 0
    for s, y in pairs:
        if y == 1:
            tp += 1
        else:
            fp += 1
        fpr.append(fp / nneg)
        tpr.append(tp / npos)
    area = 0.0
    for i in range(1, len(fpr)):
        area += (fpr[i] - fpr[i - 1]) * (tpr[i] + tpr[i - 1]) / 2
    return area

pos = [0.9, 0.8, 0.7, 0.6, 0.4]
neg = [0.5, 0.3, 0.2, 0.1, 0.05]
scores = pos + neg
labels = [1] * len(pos) + [0] * len(neg)
print('Mann-Whitney AUC', auc_u(pos, neg))
print('trapezoid AUC', round(auc_trapezoid(scores, labels), 4))

def bootstrap_auc(pos, neg, b=400):
    vals = []
    for _ in range(b):
        p = [random.choice(pos) for _ in pos]
        q = [random.choice(neg) for _ in neg]
        vals.append(auc_u(p, q))
    vals.sort()
    return round(vals[int(b * 0.025)], 4), round(vals[int(b * 0.975)], 4)

print('bootstrap 95% CI', bootstrap_auc(pos, neg))

```

<OutputBox title='扩展示例运行结果' output='Mann-Whitney AUC 0.96\ntrapezoid AUC 0.96\nbootstrap 95% CI (0.84, 1.0)' />

<LineByLine code='import random\n\nrandom.seed(3)\n\ndef auc_u(pos, neg):\n    u = 0.0\n    for p in pos:\n        for q in neg:\n            u += 1.0 if p &gt; q else 0.5 if p == q else 0.0\n    return u / (len(pos) * len(neg))\n\ndef auc_trapezoid(scores, labels):\n    pairs = sorted(zip(scores, labels), key=lambda t: -t[0])\n    npos = sum(labels)\n    nneg = len(labels) - npos\n    fpr = [0.0]\n    tpr = [0.0]\n    tp = fp = 0\n    for s, y in pairs:\n        if y == 1:\n            tp += 1\n        else:\n            fp += 1\n        fpr.append(fp / nneg)\n        tpr.append(tp / npos)\n    area = 0.0\n    for i in range(1, len(fpr)):\n        area += (fpr[i] - fpr[i - 1]) * (tpr[i] + tpr[i - 1]) / 2\n    return area\n\npos = [0.9, 0.8, 0.7, 0.6, 0.4]\nneg = [0.5, 0.3, 0.2, 0.1, 0.05]\nscores = pos + neg\nlabels = [1] * len(pos) + [0] * len(neg)\nprint(&#39;Mann-Whitney AUC&#39;, auc_u(pos, neg))\nprint(&#39;trapezoid AUC&#39;, round(auc_trapezoid(scores, labels), 4))\n\ndef bootstrap_auc(pos, neg, b=400):\n    vals = []\n    for _ in range(b):\n        p = [random.choice(pos) for _ in pos]\n        q = [random.choice(neg) for _ in neg]\n        vals.append(auc_u(p, q))\n    vals.sort()\n    return round(vals[int(b * 0.025)], 4), round(vals[int(b * 0.975)], 4)\n\nprint(&#39;bootstrap 95% CI&#39;, bootstrap_auc(pos, neg))\n' :notes='["固定随机种子，让 bootstrap 区间可复现", "空行，只用于分隔逻辑块，不影响执行结果。", "auc_u 枚举全部正负对，统计量 U 除以 n 正 n 负", "空行，只用于分隔逻辑块，不影响执行结果。", "平局记 0.5，对应 ROC 定义里的半分", "auc_trapezoid 按分数降序构造 FPR 与 TPR 序列", "逐段用梯形公式累加面积", "5 个正样本与 5 个负样本，只有 0.4 输给 0.5", "25 个正负对里 24 个正分更高，AUC 为 0.96", "梯形积分给出同一数值，印证两种定义等价", "空行，只用于分隔逻辑块，不影响执行结果。", "bootstrap_auc 有放回重采样正负样本各 b 次", "排序后取 2.5% 与 97.5% 分位得经验置信区间", "小样本下区间宽到 (0.84, 1.0)，单点 AUC 不足以判优劣", "这一行 `nneg = len(labels) - npos` 的作用，可对照上方输出逐项核对。", "这一行 `fpr = [0.0]` 的作用，可对照上方输出逐项核对。", "这一行 `tpr = [0.0]` 的作用，可对照上方输出逐项核对。", "这一行 `tp = fp = 0` 的作用，可对照上方输出逐项核对。", "这一行 `for s, y in pairs:` 的作用，可对照上方输出逐项核对。", "这一行 `if y == 1:` 的作用，可对照上方输出逐项核对。", "这一行 `tp += 1` 的作用，可对照上方输出逐项核对。", "这一行 `else:` 的作用，可对照上方输出逐项核对。", "这一行 `fp += 1` 的作用，可对照上方输出逐项核对。", "这一行 `fpr.append(fp / nneg)` 的作用，可对照上方输出逐项核对。", "这一行 `tpr.append(tp / npos)` 的作用，可对照上方输出逐项核对。", "这一行 `area = 0.0` 的作用，可对照上方输出逐项核对。", "这一行 `for i in range(1, len(fpr)):` 的作用，可对照上方输出逐项核对。", "这一行 `area += (fpr[i] - fpr[i - 1]) * (tpr[i] + tpr[i - 1]` 的作用，可对照上方输出逐项核对。", "这一行 `return area` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `pos = [0.9, 0.8, 0.7, 0.6, 0.4]` 的作用，可对照上方输出逐项核对。", "这一行 `neg = [0.5, 0.3, 0.2, 0.1, 0.05]` 的作用，可对照上方输出逐项核对。", "这一行 `scores = pos + neg` 的作用，可对照上方输出逐项核对。", "这一行 `labels = [1] * len(pos) + [0] * len(neg)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;Mann-Whitney AUC&#39;, auc_u(pos, neg))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;trapezoid AUC&#39;, round(auc_trapezoid(scores, l` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `def bootstrap_auc(pos, neg, b=400):` 的作用，可对照上方输出逐项核对。", "这一行 `vals = []` 的作用，可对照上方输出逐项核对。", "这一行 `for _ in range(b):` 的作用，可对照上方输出逐项核对。", "这一行 `p = [random.choice(pos) for _ in pos]` 的作用，可对照上方输出逐项核对。", "这一行 `q = [random.choice(neg) for _ in neg]` 的作用，可对照上方输出逐项核对。", "这一行 `vals.append(auc_u(p, q))` 的作用，可对照上方输出逐项核对。", "这一行 `vals.sort()` 的作用，可对照上方输出逐项核对。", "这一行 `return round(vals[int(b * 0.025)], 4), round(vals[in` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `print(&#39;bootstrap 95% CI&#39;, bootstrap_auc(pos, neg))` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />


### PR 曲线阶梯插值与 average precision 的面积口径

**指标口径与 scikit-learn 源码**

| 指标 | 等价形式 | 源码函数 / 插值 | 对不平衡的敏感性 |
| --- | --- | --- | --- |
| ROC-AUC | U 除以 (n 正 n 负)，U 是 Mann-Whitney 统计量 | _ranking.py roc_auc_score 走梯形 auc | 较稳，但被大量易分负样本稀释 |
| AP / PR-AUC | 各阈值处 (R 变化量) 乘 P 的累加 | _binary_uninterpolated_average_precision 阶梯求和 | 正样本极少时比 ROC-AUC 敏感 |
| accuracy | (TP + TN) 除以 N | _classification.py accuracy_score | 先验极偏时被多数类主导 |
| F1 | 2PR 除以 (P + R) | 调和平均，对较小项敏感 | 单指标看不平衡 |
| Brier / log-loss | 概率与标签的平方差或对数损失 | 衡量校准而非排序质量 | 评估概率数值是否可信 |


### k 折交叉验证方差被低估的结构原因

Bengio 与 Grandvalet 在 2004 年证明：k 折交叉验证估计的方差不存在无偏估计量，根因是 k 个训练集两两重叠。`k=10` 时任意两折训练集共享 (k-2)/(k-1)=8/9 的样本，k 个验证分数高度正相关。

数学上设每折误差为 e_i，均值的方差等于 1 除以 k 的平方，再乘上各折方差之和与所有两两协方差之和；重叠让协方差项为正且很大，而样本方差只估计了各折相对均值偏差平方之和再除以 k-1、又除以 k，相当于假装协方差全为零，系统性偏小。

工程后果很直接：用 5 折 CV 报出『正负 0.3%』的误差棒并据此宣称模型 A 优于 B，往往是假显著。正确做法是把 CV 当点估计，比较模型时改用同一折划分的配对检验（paired t 或 Wilcoxon）、重复 k 折、或在外层做 bootstrap 重采样；

嵌套 CV 的成本是外层折数乘内层折数乘网格大小的训练次数，网格一大就爆炸，这是『评估无偏』与『算力预算』之间真实的架构权衡。正文说 k 折给均值与标准差，标准差确实能算，但把它当独立样本的置信区间用就是错的。


## 嵌套交叉验证的成本与超参搜索的赢家诅咒

一个团队在 40 条样本的验证集上网格搜索 50 组超参，报告最佳 AUC 0.975 并据此上线，线上只有 0.80 左右。这不是数据泄漏，而是赢家诅咒：当每组超参真实效果相同、只是验证集采样带来噪声时，取 50 个带噪估计的最大值，期望上必然高于真值，搜索空间越大、验证集越小，乐观偏差越大。

下例用 0.80 的真实分数造 50 组无关超参，每组在 40 个伯努利样本上估一次，最佳值冲到 0.975、高估 0.175，而全网格均值仍贴近 0.807。修复不是换更大的模型，而是把『选超参』放进内层 CV、用从未参与决策的外层测试集报告最终分数，或直接报告多次重复划分的分布而不是单点最大值。

```python
import random

random.seed(11)

truth = 0.80
grid = [round(random.uniform(0.6, 0.9), 3) for _ in range(50)]
n_val = 40

def estimate(true_auc, n):
    hits = sum(1 for _ in range(n) if random.random() < true_auc)
    return hits / n

scores = [(g, estimate(truth, n_val)) for g in grid]
best_g, best_val = max(scores, key=lambda t: t[1])
print('grid size', len(grid))
print('best val score', round(best_val, 3))
print('true score', truth)
print('optimism', round(best_val - truth, 3))
print('mean grid score', round(sum(s for _, s in scores) / len(scores), 3))

```

<Quiz no='097-1' q='关于 k 折交叉验证分数的误差棒，下面哪项准确？' :options='["各折训练集大量重叠、分数正相关，把样本标准差除以根号 k 会系统性低估真实方差，且不存在无偏估计量", "k 折分数相互独立，s 除以根号 k 就是无偏标准误", "折数越多方差估计越准，k 等于 n 时误差棒最可信", "只要改用 StratifiedKFold，各折就统计独立"]' answer="0" explain='Bengio 与 Grandvalet 2004 证明 k 折 CV 估计的方差没有无偏估计量：k = 10 时任意两折训练集共享 8/9 样本，验证分数的协方差为正且很大，naive 的 s 除以根号 k 假装协方差为零而偏小。分层只保证类别比例，不消除训练集重叠。比较模型应改用同一划分的配对检验或嵌套交叉验证。' />


### bootstrap 与 Wilson 区间的指标不确定性

<Exercise title='从零计算 AUC 并给出 Wilson 区间' task='用正负样本分数枚举所有正负对实现 auc_u，与梯形法对照；再对 recall 用 Wilson 区间公式给出 95% 上下界，说明它比 recall 加减一个固定值更合理。' solution='import math\n\ndef auc_u(pos, neg):\n    u = 0.0\n    for p in pos:\n        for q in neg:\n            u += 1.0 if p &gt; q else 0.5 if p == q else 0.0\n    return u / (len(pos) * len(neg))\n\ndef wilson(tp, n, z=1.96):\n    p = tp / n\n    d = 1 + z * z / n\n    c = (p + z * z / (2 * n)) / d\n    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d\n    return round(c - h, 3), round(c + h, 3)\n\nprint(&#39;AUC&#39;, auc_u([0.9, 0.7, 0.4], [0.5, 0.3, 0.1]))\nprint(&#39;recall 8/10 Wilson 95%&#39;, wilson(8, 10))\n' explain='枚举 9 个正负对里有 8 个正样本分数更高（0.4 只输给 0.5），AUC 为 8 除以 9 约 0.889；梯形法按 FPR 分段积分给出同一数值，印证二者等价。Wilson 区间在小样本与接近 0 或 1 的比例上仍保持覆盖概率，recall 为 8/10 时给出约 (0.49, 0.943)，而加减固定值会越界或给出负宽度，正样本本来就少时不适用。' />

<Term word='赢家诅咒' text='在同一份验证集上搜索大量超参并只报告最优那一个时，被选中的分数是多个带噪估计的最大值，期望上高于其真实泛化能力；搜索空间越大、验证集越小，乐观偏差越大。它解释「离线调参涨点、上线不动」，与数据泄漏是两类不同病因，修复靠嵌套交叉验证与独立测试集，而不是再搜一轮更大的网格。' />


## 练习、自测与评估口径速记

<Exercise title='基础：从混淆矩阵算全套指标' task='给定 TP=5、FP=20、FN=5、TN=970，计算 accuracy、precision、recall、F1，并解释为什么 accuracy 0.975 仍不能说明模型好用。' solution='tp, fp, fn, tn = 5, 20, 5, 970\nacc = (tp+tn)/(tp+fp+fn+tn)\nprec = tp/(tp+fp); rec = tp/(tp+fn)\nf1 = 2*prec*rec/(prec+rec)\nprint(round(acc,3), round(prec,3), round(rec,3), round(f1,3))' explain='accuracy=0.975 被 970 个真负例主导；正例只抓到一半（recall=0.5）、报出的正例里仅 20% 准确（precision=0.2），漏报代价高的场景该模型并不好用。' />

<Exercise title='进阶：用数值实验证明泄漏' task='对训练段 [1,2,3,4,5] 与测试段 [20,21,22]，分别用「全量均值方差」与「仅训练均值方差」标准化测试段，打印两组结果并说明为何前者是泄漏。' solution='train=[1,2,3,4,5]; test=[20,21,22]; all_=train+test\ndef mean(a): return sum(a)/len(a)\ndef pstd(a):\n    m=mean(a); return (sum((x-m)**2 for x in a)/len(a))**0.5\ndef z(xs,m,s): return [round((x-m)/s,2) for x in xs]\nprint(&#39;leak&#39;, z(test, mean(all_), pstd(all_)))\nprint(&#39;clean&#39;, z(test, mean(train), pstd(train)))' explain='全量 fit 把测试段三个大值纳入均值与方差，标准化结果被压到 1.3 附近；仅用训练参数时测试段明显偏离（9 以上）。前者让模型提前感知了测试分布，属于泄漏。' />

<Quiz no='097-2' q='正样本占 0.6% 的欺诈检测，全预测「正常」的准确率和召回率约为？' :options='["准确率约 99.4%，召回率 0", "准确率 0，召回率 0", "两者都约 50%", "准确率 99.4%，召回率 99.4%"]' answer="0" explain='全预测多数类时真负例占比 1-0.006=0.994，accuracy 约 99.4%；但一个正例都没抓到，TP=0，recall=0。这说明 accuracy 在极不平衡数据上会骗人。' />

<Quiz no='097-3' q='防止标准化过程数据泄漏，正确做法是？' :options='["把 StandardScaler 放进 Pipeline，只在训练折 fit，验证/测试折只 transform", "先对全量 fit 再划分，省事且等价", "只对测试集做标准化", "标准化不涉及学习参数，无所谓顺序"]' answer="0" explain='scaler 的均值与方差是从数据估计出来的参数，全量 fit 会把测试折分布泄进训练；Pipeline 保证每次交叉验证只在对应训练折 fit。' />

<Quiz no='097-4' q='在测试集上反复调参直到分数满意，后果是？' :options='["测试集退化为验证集，最终报告分数不再无偏", "分数更可信", "只是稍微乐观一点，无伤大雅", "让模型自动泛化更好"]' answer="0" explain='测试集一旦参与任何决策就失去「从未见过」的性质，等于把评估集当验证集用，报告的分数系统性偏高。应改用嵌套交叉验证并保留一份只用一次的测试集。' />

<Predict no='097-5' q='前面 code 里 metrics(0, 0, 10, 990) 的 recall 是多少？' :options='["0.0", "0.99", "0.5"]' answer='0' output='0.0' explain='recall = TP/(TP+FN) = 0/(0+10) = 0.0。模型全预测负例，虽然 accuracy 高达 0.99，却一个正例都没抓到，正是 accuracy 在不平衡数据上失效的证据。' />

<FillBlank no='097-6' tpl='___ metrics(tp, fp, fn, tn):' :answers='["def"]' hint='回想本讲关于 训练集 / 验证集 / 测试集 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 划分、数据泄漏与 Pipeline 的落点。' />

<KnowledgeCard :points='["训练/验证/测试三份：测试集只在最终用一次；分类用 stratify，时间序列按时间切不能打乱", "数据泄漏根因是预处理也是学到的参数：scaler/特征选择/目标编码只在训练折 fit，放进 Pipeline", "混淆矩阵四数推全部指标：precision=TP/(TP+FP)、recall=TP/(TP+FN)、F1 用调和平均", "极不平衡下 accuracy 由多数类主导、recall 可为 0；按业务代价选 recall、precision、PR-AUC 或 ROC-AUC", "k 折 CV 取均值与波动，StratifiedKFold/TimeSeriesSplit 各管一类；嵌套 CV 把选超参与评估分层", "复杂模型前先立 DummyClassifier/DummyRegressor 基线作地板；离线远高于线上先查泄漏与漂移"]' :pitfalls='["先在全量数据上标准化或做特征选择再划分", "用 accuracy 评价极不平衡的欺诈数据", "在测试集上反复调参直到满意", "只用准确率评价极不平衡的数据集，全预测多数类就能拿到 99 分"]' summary='评估的可信度取决于划分：先在全量数据上做特征选择或标准化再划分，就是典型的数据泄漏，分数虚高' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 训练/验证/测试三份：测试集只在最终用一次；分类用 stratify，时间序列按时间切不能打乱 | 建立直觉 |
| 数据泄漏根因是预处理也是学到的参数：scaler/特征选择/目标编码只在训练折 fit，放进 Pipeline | 跑通示例 |
| 混淆矩阵四数推全部指标：precision=TP/(TP+FP)、recall=TP/(TP+FN)、F1 用调和平均 | 深入边界 |
| 极不平衡下 accuracy 由多数类主导、recall 可为 0；按业务代价选 recall、precision、PR-AUC 或 ROC-AUC | 工程落地 |
| k 折 CV 取均值与波动，StratifiedKFold/TimeSeriesSplit 各管一类；嵌套 CV 把选超参与评估分层 | 随堂检测 |
| 复杂模型前先立 DummyClassifier/DummyRegressor 基线作地板；离线远高于线上先查泄漏与漂移 | 复盘 |

1. 训练/验证/测试三份：测试集只在最终用一次；分类用 stratify，时间序列按时间切不能打乱

2. 数据泄漏根因是预处理也是学到的参数：scaler/特征选择/目标编码只在训练折 fit，放进 Pipeline

3. 混淆矩阵四数推全部指标：precision=TP/(TP+FP)、recall=TP/(TP+FN)、F1 用调和平均

[下一讲：经典算法：KNN、线性与逻辑回归](/data-ai/linear-models)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/097-ml-workflow.py`

```bash
python3 examples/lessons/097-ml-workflow.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/097-ml-workflow.py) · [全部示例代码索引](/examples/)
