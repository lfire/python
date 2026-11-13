---
title: 第 099 讲 · SVM、核方法、决策树与随机森林
description: 掌握非线性模型与其适用边界
---

<StageHeader stage='L9 · 数据与 AI' level='★★★☆☆' time='40 分钟' goal='掌握非线性模型与其适用边界' prereq='第 098 讲 · 经典算法：KNN、线性与逻辑回归' />

# 第 099 讲 · SVM、核方法、决策树与随机森林

线性模型和近邻都讲得通，可一旦边界是弯的，或一列是评分、一列是几十万的余额，直线就分不开了。这一讲往非线性走：树几乎不用缩放，代价是外推差、边界一格一格；SVM 在小样本高维上依旧稳，各有地界。

先说 SVM 的间隔最大化、核技巧与软间隔 C 各管什么；再换到树的划分准则，看不设深度、忽略剪枝时训练集怎样轻易满分而线上失手；最后用 Bagging 并成随机森林，并提醒特征重要性只能当线索、不能当因果。需要上一讲的特征缩放与正则、常用的交叉验证。学完面对一份表格数据，你能在核方法、单棵树和森林之间选得出。


## 不设树深，训练集 100% 而线上很差

一棵决策树在训练集上做到 100% 准确，上线后准确率掉到六成，团队却还在加特征、加深度。复盘发现树从没设 max_depth，也没做交叉验证，它把每个训练样本都长成了一片纯叶子，等于把整张表背了下来；换个更贴切的场景，SVM 同事把带 RBF 核的模型直接喂了未缩放的特征，gamma 又用了默认值，训练出的边界全是碎块。

这两类问题的分界线很清楚：树几乎不需要缩放、能吞吐混合类型，代价是外推能力差、决策边界呈阶梯状；SVM 靠间隔最大化在小样本高维上很强，却对尺度与 C / gamma 极敏感。本讲用纯 Python 把基尼划分、核技巧、软间隔与 Bagging 降方差都变成能实跑核对的结论。

<Callout type="warn" title='先看一个真实会出错的写法' text='不设 max_depth / min_samples_leaf，训练集 100% 线上很差：树会一直分裂到每片叶子都纯，把噪声与个别样本也背下来，方差极大' />


## 间隔最大化、核技巧与软间隔 C

线性 SVM 的目标不是「把点分开」，而是找一条使两类间隔 2/||w|| 最大的超平面，约束 `y_i(wᵀx_i + b)` ≥ 1，落在间隔边界上的点叫支持向量——最终模型只由这些点决定，删掉远离边界的样本不会改变结果，这是它小样本高维仍稳的原因。

现实数据不可分，于是引入软间隔：允许部分点越界，用 hinge loss 加惩罚，目标变为 min (1/2)||w||² + C·Σξ_i。参数 C 是误分类惩罚的强度：C 越大越不肯放过错分点、间隔变窄、边界扭曲、易过拟合；C 越小间隔越宽、容许更多错分、更平滑。

核技巧解决非线性：把样本隐式映射到高维特征空间，在那个空间里做线性分隔，而不显式计算映射 φ(x)，只需一个核函数 `K(x,z)`=φ(x)·φ(z)。常用核有线性 `K=xᵀz`、多项式 K=(γ·xᵀz + r)^d、RBF（高斯）`K=exp`(-γ·||x-z||²)。

RBF 的 gamma 控制单个样本的影响半径：gamma 大则影响范围小、边界碎、易过拟合，gamma 小则边界平滑、可能欠拟合。RBF 对特征尺度极敏感（指数里是距离平方），因此必须先标准化，否则大尺度维度主导核值。

scikit-learn 里 SVC 的 C 默认 1.0、kernel 默认 'rbf'、gamma 默认 'scale'（按 1/(d·`Var(X)`) 缩放），这个默认已经依赖特征方差，未缩放时仍会失真。

```python
def gini(labels):
    n = len(labels)
    if n == 0: return 0.0
    counts = {}
    for l in labels: counts[l] = counts.get(l, 0) + 1
    return 1 - sum((c / n) ** 2 for c in counts.values())

def best_split(rows):
    xs = sorted(set(r[0] for r in rows))
    best_w, best_t, best_left, best_right = None, None, 0, 0
    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:
        left = [l for x, l in rows if x <= t]
        right = [l for x, l in rows if x > t]
        w = (len(left) * gini(left) + len(right) * gini(right)) / len(rows)
        if best_w is None or w < best_w:
            best_w, best_t = w, t
            best_left, best_right = len(left), len(right)
    return (round(best_w, 4), best_t, best_left, best_right)

data = [(1, 'N'), (2, 'N'), (3, 'N'), (4, 'P'), (5, 'P'), (6, 'P')]
print('root gini', round(gini([l for _, l in data]), 4))
print('best split', best_split(data))
```

<OutputBox title='主示例运行结果' output='root gini 0.5\nbest split (0.0, 3.5, 3, 3)' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def gini(labels):\n    n = len(labels)\n    if n == 0: return 0.0\n    counts = {}\n    for l in labels: counts[l] = counts.get(l, 0) + 1\n    return 1 - sum((c / n) ** 2 for c in counts.values())\n\ndef best_split(rows):\n    xs = sorted(set(r[0] for r in rows))\n    best_w, best_t, best_left, best_right = None, None, 0, 0\n    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:\n        left = [l for x, l in rows if x &lt;= t]\n        right = [l for x, l in rows if x &gt; t]\n        w = (len(left) * gini(left) + len(right) * gini(right)) / len(rows)\n        if best_w is None or w &lt; best_w:\n            best_w, best_t = w, t\n            best_left, best_right = len(left), len(right)\n    return (round(best_w, 4), best_t, best_left, best_right)\n\ndata = [(1, &#39;N&#39;), (2, &#39;N&#39;), (3, &#39;N&#39;), (4, &#39;P&#39;), (5, &#39;P&#39;), (6, &#39;P&#39;)]\nprint(&#39;root gini&#39;, round(gini([l for _, l in data]), 4))\nprint(&#39;best split&#39;, best_split(data))' :notes='["定义基尼不纯度，值越小节点越纯", "样本总数作为各类占比的分母", "空节点不纯度定义为 0，避免除零", "counts 统计每个类别的样本数", "逐条累计类别计数，得到 p_k = c/n", "Gini = 1 - Σp_k²，二分类各半时为 0.5", "定义最佳切分搜索，rows 为 (特征, 标签) 列表", "候选阈值取相邻不同特征值的中点，先排序去重", "四个变量分别记录最小加权不纯度、最佳阈值、左右样本数", "遍历每个候选阈值，逐个试算划分质量", "左子节点收集特征小于等于阈值的标签", "右子节点收集特征大于阈值的标签", "按左右样本数加权求和，得到该切分的加权不纯度", "保留加权不纯度最小的切分，即信息增益最大处", "更新最佳阈值与最小不纯度", "同时记下左右子节点的样本数便于核对", "返回 (加权不纯度, 阈值, 左样本数, 右样本数)", "构造 3 个 N、3 个 P、特征取 1 到 6 的可分数据", "打印根节点基尼，两类各半应为 0.5", "在 3.5 处切开左右各纯一类，加权不纯度降到 0"]' title='第 099 讲 · SVM、核方法、决策树与随机森林' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 树的划分准则：基尼、熵与最佳切分

分类树递归地选一个特征与切分点，把节点里的样本分到左右子节点，目标是让子节点更「纯」。纯度用不纯度度量：基尼 `Gini = 1` - Σ p_k²（p_k 是该节点第 k 类占比），熵 `Entropy = -Σ` p_k·`log2(p_k)`，`信息增益 = 父不纯度` - 按样本数加权的子不纯度之和。

CART 分类默认用基尼、回归用平方误差最小，ID3/C4.5 用信息增益 / 增益率；基尼不含对数、计算更快，二者在多数数据集上选出的切分很接近。对连续特征，候选切分点取相邻不同取值的中点，逐个试算加权不纯度、取最小者，复杂度约为 `O(d·n·log n)`（先对每列排序）。

树必须限制复杂度：max_depth 限深度、min_samples_leaf 限叶节点最少样本、min_samples_split 限可分裂的最小样本数、max_leaf_nodes 限叶子数，也可以在长成全树后按代价复杂度剪枝（ccp_alpha）。不设这些约束，树会一直分到每片叶子都纯，训练集必然满分而线上很差。

树的两个固有边界要记住：决策边界是轴平行的阶梯状，做不了平滑斜边界；且它只能在训练数据的取值范围内做分段常数预测，超出范围不能外推，回归到新区间会系统性失真。

```python
import statistics as st
trees = [[10.5, 9.2, 11.1, 8.7, 10.8],
         [9.8, 11.5, 9.1, 10.6, 9.9],
         [12.0, 8.5, 10.2, 11.3, 9.4]]
single = trees[0]
avg = [st.mean(col) for col in zip(*trees)]
print('single var', round(st.variance(single), 3))
print('bagged var', round(st.variance(avg), 3))
```

<OutputBox title='原理验证' output='single var 1.103\nbagged var 0.142' />

**划分准则与不纯度**

| 准则 | 公式 | 使用者 | 特点 |
| --- | --- | --- | --- |
| 基尼 Gini | 1 - Σp_k² | CART 分类 | 无对数、计算快 |
| 熵 Entropy | -Σp_k·log2(p_k) | ID3 / C4.5 | 信息增益需增益率校正 |
| 平方误差 | Σ(y - ȳ)² | CART 回归 | 叶输出取该叶均值 |
| 加权不纯度 | (n_L·G_L + n_R·G_R)/n | 选切分点 | 取最小者即增益最大 |


### 深度、叶样本数与代价复杂度剪枝

```python
def poly_kernel(x, z, degree=2, c=1):
    return (x * z + c) ** degree
pts = [(-1, 1), (0, -1), (1, 1)]
print('mapped', [(x, x * x, lab) for x, lab in pts])
print('K(-1,1)', poly_kernel(-1, 1), 'K(-1,0)', poly_kernel(-1, 0))
```

<OutputBox title='对照写法：先自己猜，再点开' output='mapped [(-1, 1, 1), (0, 0, -1), (1, 1, 1)]\nK(-1,1) 0 K(-1,0) 1' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "def gini(labels):\n    n = len(labels)\n    if n == 0: return 0.0\n    counts = {}\n    for l in labels: counts[l] = counts.get(l, 0) + 1\n    return 1 - sum((c / n) ** 2 for c in counts.values())\n\ndef best_split(rows):\n    xs = sorted(set(r[0] for r in rows))\n    best_w, best_t, best_left, best_right = None, None, 0, 0\n    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:\n        left = [l for x, l in rows if x &lt;= t]\n        right = [l for x, l in rows if x &gt; t]\n        w = (len(left) * gini(left) + len(right) * gini(right)) / len(rows)\n        if best_w is None or w &lt; best_w:\n            best_w, best_t = w, t\n            best_left, best_right = len(left), len(right)\n    return (round(best_w, 4), best_t, best_left, best_right)\n\ndata = [(1, &#39;N&#39;), (2, &#39;N&#39;), (3, &#39;N&#39;), (4, &#39;P&#39;), (5, &#39;P&#39;), (6, &#39;P&#39;)]\nprint(&#39;root gini&#39;, round(gini([l for _, l in data]), 4))\nprint(&#39;best split&#39;, best_split(data))", "note": "间隔最大化、核技巧与软间隔 C"}, {"label": "对照 / 进阶", "code": "def poly_kernel(x, z, degree=2, c=1):\n    return (x * z + c) ** degree\npts = [(-1, 1), (0, -1), (1, 1)]\nprint(&#39;mapped&#39;, [(x, x * x, lab) for x, lab in pts])\nprint(&#39;K(-1,1)&#39;, poly_kernel(-1, 1), &#39;K(-1,0)&#39;, poly_kernel(-1, 0))", "note": "树的划分准则、剪枝与深度控制"}]' title='两种写法切换看' />


## Bagging、随机森林与降方差

单棵深树方差大、对训练样本扰动敏感，Bagging（Bootstrap Aggregating）用「有放回重采样出多份训练集、各训一棵树、再平均或投票」来压方差：设单棵树方差 σ²、两两相关系数 ρ，B 棵平均后的方差约为 ρ·σ² + (1-ρ)·σ²/B，树越多第二项越小，但相关项 ρ·σ² 是下限，所以还要降低树与树之间的相关性。

随机森林在 Bagging 之上再加一层随机：每个节点分裂时只从随机选出的 mtry 个特征子集里挑最优（分类常用 `sqrt(d)`、回归常用 d/3），进一步压低 ρ。随机森林几乎不需要特征缩放、能处理混合类型与缺失、抗过拟合，代价是模型体积大、单条预测要过所有树、且同样不能外推。

袋外样本（OOB，约 36.8% 未被某棵树抽到）可直接当验证集估泛化误差，省一次划分。特征重要性有两种口径：基于不纯度下降（impurity-based，倾向于高基数特征、有偏）与基于置换（permutation，打乱某列后看验证分数掉多少，更可信）。

无论哪种都只是「模型用到它的程度」，不是因果结论——把重要性排第一的特征写成业务原因，是常见越界。

<ConceptDiagram type='compare2' title='第 099 讲 · 间隔最大化、核技巧与软间隔 C' labels='间隔最大化、核技巧与软间隔 C|树的划分准则、剪枝与深度控制|Bagging、随机森林与特征重要性' caption='掌握非线性模型与其适用边界' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

**SVM 关键参数（scikit-learn SVC）**

| 参数 | 默认值 | 调大的效果 | 风险 |
| --- | --- | --- | --- |
| C | 1.0 | 更不容忍错分、间隔变窄 | 过大过拟合 |
| kernel | 'rbf' | 换成非线性边界 | 线性可分数据用线性核更稳 |
| gamma | 'scale' = 1/(d·Var(X)) | 影响半径变小、边界变碎 | 过大严重过拟合 |
| degree | 3（poly 核） | 多项式次数升高 | 高次易过拟合 |


## RBF 核为什么怕未缩放特征

SVM 的原始问题是带约束的凸二次规划：min (1/2)||w||² `s.t`. `y_i(wᵀx_i+b)` ≥ 1。

通过拉格朗日对偶可化为只依赖样本内积 x_iᵀx_j 的形式，于是把内积替换成核函数 `K(x_i,x_j)`=φ(x_i)·φ(x_j) 就得到高维空间的线性分隔，而不必显式构造 φ——只要 K 满足 Mercer 条件（对应的 Gram 矩阵半正定）即为合法核，这就是核技巧。

RBF 核 `exp(-γ||x-z||²)` 对应无限维特征空间，γ 控制距离衰减速度。

软间隔引入松弛变量 ξ_i 与惩罚 C，对偶后拉格朗日乘子被 C 截断（0 ≤ α_i ≤ C），C 同时决定支持向量的数量与边界复杂度。决策树的划分是贪心的：对每个特征排序后枚举相邻取值中点，选使加权不纯度下降最多的切分，本质是局部最优而非全局最优。

Bagging 的方差公式 ρ·σ² + (1-ρ)·σ²/B 说明「平均」只能消掉不相关部分，随机森林再用特征子采样降低树间相关 ρ，才把方差进一步压下去；这也是为什么单棵深树方差大、森林却稳。

**树 / SVM / 随机森林选型**

| 维度 | 决策树 | RBF SVM | 随机森林 |
| --- | --- | --- | --- |
| 特征缩放 | 基本不需要 | 必须 | 基本不需要 |
| 外推能力 | 差，阶梯边界 | 中 | 差 |
| 高维小样本 | 一般 | 强 | 较好 |
| 训练/预测成本 | 低 / 低 | 中 / 中 | 高（多棵树） |
| 可解释性 | 高，可画路径 | 低 | 中，靠特征重要性 |

<Callout type="warn" title='本讲最容易踩的坑' text='不设 max_depth / min_samples_leaf，训练集 100% 线上很差：树会一直分裂到每片叶子都纯，把噪声与个别样本也背下来，方差极大' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 不设 max_depth / min_samples_leaf，训练集 100% 线上很差 | 树会一直分裂到每片叶子都纯，把噪声与个别样本也背下来，方差极大 | 设 max_depth、min_samples_leaf 并配合交叉验证；或用 ccp_alpha 做代价复杂度剪枝 |
| RBF SVM 直接喂未缩放特征，边界全是碎块 | RBF 核用距离平方的指数，大尺度列主导核值；gamma='scale' 又依赖各列方差 | 先用 StandardScaler 标准化，再用网格搜索在 C 与 gamma 的对数网格上调参 |
| 把特征重要性排名当成业务因果结论 | 不纯度下降型重要性偏向高基数特征，且只反映「模型用到它」，不反映因果 | 改用 permutation_importance 在验证集上度量，并把结论限定为「预测贡献」而非因果 |


## 深度受限的树：把「背下训练集」变成可核对的叶数

一个二分类任务里，深度不受限的树会把每个样本都分到纯叶，训练集误差为零却毫无泛化能力。工程上把 max_depth 当成一等参数，与叶节点数、叶内基尼一起记录，就能在日志里看出模型是不是长得过细。

下面用纯标准库实现一个按基尼递归划分的小型分类树：build 在达到 max_depth、节点已纯、或特征值不足两个时停止，leaves 数出叶节点个数，最后对比 `max_depth=1` 与 `max_depth=3` 两棵树的结构。

真实项目把 gini / split 换成 DecisionTreeClassifier 的 criterion='gini'，把 max_depth 直接传给构造器，并用 GridSearchCV 在 2 到 10 的深度上做交叉验证，口径一致。

```python
from collections import Counter

def gini(labels):
    n = len(labels)
    if not n: return 0.0
    c = Counter(labels)
    return 1 - sum((v / n) ** 2 for v in c.values())

def split(rows):
    xs = sorted(set(r[0] for r in rows))
    best = None
    for t in [(a + b) / 2 for a, b in zip(xs, xs[1:])]:
        L = [r for r in rows if r[0] <= t]
        R = [r for r in rows if r[0] > t]
        w = (len(L) * gini([l for _, l in L]) + len(R) * gini([l for _, l in R])) / len(rows)
        if best is None or w < best[0]: best = (w, t, L, R)
    return best

def build(rows, depth, max_depth):
    labels = [l for _, l in rows]
    if depth >= max_depth or gini(labels) == 0 or len(set(r[0] for r in rows)) < 2:
        return ('leaf', len(rows), round(gini(labels), 3))
    w, t, L, R = split(rows)
    return ('split', round(t, 1), build(L, depth + 1, max_depth), build(R, depth + 1, max_depth))

def leaves(node):
    return 1 if node[0] == 'leaf' else leaves(node[2]) + leaves(node[3])

data = [(1, 'N'), (2, 'N'), (3, 'N'), (4, 'P'), (5, 'P'), (6, 'P'), (7, 'P'), (8, 'N')]
print('depth1 leaves', leaves(build(data, 0, 1)))
print('depth3 leaves', leaves(build(data, 0, 3)))
print('depth3 tree', build(data, 0, 1))
```

<Callout type="idea" title='落地提示' text='用网格搜索配合交叉验证调关键参数，特征重要性只作线索不做因果解释' />

<CheckList id='P099b' title='上线前自检' :items='["能复现并解释「不设 max_depth / min_samples_lea」", "能复现并解释「RBF SVM 直接喂未缩放特征，边界全是碎块」", "能复现并解释「把特征重要性排名当成业务因果结论」", "能用一条命令验证 间隔最大化与核技巧", "关键路径有自动化测试与失败分支"]' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：不设 max_depth / min_sam", "body": "树会一直分裂到每片叶子都纯，把噪声与个别样本也背下来，方差极大", "tip": "设 max_depth、min_samples_leaf 并配合交叉验证；或用 ccp_alpha 做代价复杂度剪枝"}, {"title": "第 2 步：RBF SVM 直接喂未缩放特征，边界全是碎", "body": "RBF 核用距离平方的指数，大尺度列主导核值；gamma=&#39;scale&#39; 又依赖各列方差", "tip": "先用 StandardScaler 标准化，再用网格搜索在 C 与 gamma 的对数网格上调参"}, {"title": "第 3 步：把特征重要性排名当成业务因果结论", "body": "不纯度下降型重要性偏向高基数特征，且只反映「模型用到它」，不反映因果", "tip": "改用 permutation_importance 在验证集上度量，并把结论限定为「预测贡献」而非因果"}]' />


## 软间隔 SVM 的拉格朗日对偶与 KKT 条件

软间隔原始问题是 min (1/2) 乘 w 范数平方 加 C 乘求和 xi_i，约束 `y_i(w 点乘 phi(x_i)` 加 b) 不小于 1 减 xi_i 且 xi_i 不小于 0。

构造拉格朗日函数 L = (1/2)||w|| 平方 + C 求和 xi_i - 求和 alpha_i 乘 [`y_i(w 点乘 phi(x_i)` + b) - 1 + xi_i] - 求和 mu_i 乘 xi_i，其中 alpha_i 与 mu_i 均不小于 0。

对 w、b、xi 求偏导置零：对 w 得 `w = 求和` alpha_i y_i `phi(x_i)`，这就是表示定理——最优 w 只是训练样本的线性组合；对 b 得 求和 alpha_i `y_i = 0`；

对 xi_i 得 C 减 alpha_i 减 `mu_i = 0`，配合 mu_i 不小于 0 才有 alpha_i 不大于 C。

代回消去原始变量得到对偶：max 求和 alpha_i - (1/2) 求和 alpha_i alpha_j y_i y_j `K(x_i, x_j)`，约束 0 不大于 alpha_i 不大于 C 与 求和 alpha_i `y_i = 0`。

注意对偶里样本只以内积 K 出现，把 K 换成核函数就是核技巧，且目标是 alpha 的凹二次型、全局最优无局部极小。KKT 互补松弛给出三类点：`alpha_i = 0` 是间隔外的点，删掉不影响模型；0 小于 alpha_i 小于 C 是恰在间隔边界上的点，xi_i 为 0，用来定 b；

`alpha_i = C` 是越界或落在间隔内的点。决策函数 `f(x)` = 求和 alpha_i y_i `K(x_i, x)` + b 只对 alpha_i 大于 0 的样本求和，这是正文「模型只由支持向量决定」的严格来源，而 C 截断 alpha 的来由只有走完这条推导链才看得见。

```python
import math

def rbf_direct(x, z, g=0.5):
    d2 = sum((a - b) ** 2 for a, b in zip(x, z))
    return math.exp(-g * d2)

def rbf_series(x, z, g=0.5, terms=12):
    dot = sum(a * b for a, b in zip(x, z))
    nx = sum(a * a for a in x)
    nz = sum(b * b for b in z)
    s = 0.0
    coef = 1.0
    for k in range(terms):
        s += coef * (dot ** k) / math.factorial(k)
        coef *= 2 * g
    return math.exp(-g * nx) * math.exp(-g * nz) * s

x = [1.0, 0.5]
z = [0.8, 0.3]
print('rbf direct', round(rbf_direct(x, z), 6))
print('rbf series 12 terms', round(rbf_series(x, z), 6))
print('series 3 terms', round(rbf_series(x, z, terms=3), 6))

def gini(labels):
    n = len(labels)
    if not n:
        return 0.0
    c = {}
    for l in labels:
        c[l] = c.get(l, 0) + 1
    return 1 - sum((v / n) ** 2 for v in c.values())

def weighted_gini(groups):
    total = sum(len(g) for g in groups)
    return sum(len(g) * gini(g) for g in groups) / total

labels = [0, 1] * 6
print('gini(id, 12 levels)', round(weighted_gini([[labels[i]] for i in range(12)]), 4))
print('gini(binary split)', round(weighted_gini([labels[:6], labels[6:]]), 4))
print('gini(root)', round(gini(labels), 4))

```

<OutputBox title='扩展示例运行结果' output='rbf direct 0.960789\nrbf series 12 terms 0.960789\nseries 3 terms 0.892249\ngini(id, 12 levels) 0.0\ngini(binary split) 0.5\ngini(root) 0.5' />

<LineByLine code='import math\n\ndef rbf_direct(x, z, g=0.5):\n    d2 = sum((a - b) ** 2 for a, b in zip(x, z))\n    return math.exp(-g * d2)\n\ndef rbf_series(x, z, g=0.5, terms=12):\n    dot = sum(a * b for a, b in zip(x, z))\n    nx = sum(a * a for a in x)\n    nz = sum(b * b for b in z)\n    s = 0.0\n    coef = 1.0\n    for k in range(terms):\n        s += coef * (dot ** k) / math.factorial(k)\n        coef *= 2 * g\n    return math.exp(-g * nx) * math.exp(-g * nz) * s\n\nx = [1.0, 0.5]\nz = [0.8, 0.3]\nprint(&#39;rbf direct&#39;, round(rbf_direct(x, z), 6))\nprint(&#39;rbf series 12 terms&#39;, round(rbf_series(x, z), 6))\nprint(&#39;series 3 terms&#39;, round(rbf_series(x, z, terms=3), 6))\n\ndef gini(labels):\n    n = len(labels)\n    if not n:\n        return 0.0\n    c = {}\n    for l in labels:\n        c[l] = c.get(l, 0) + 1\n    return 1 - sum((v / n) ** 2 for v in c.values())\n\ndef weighted_gini(groups):\n    total = sum(len(g) for g in groups)\n    return sum(len(g) * gini(g) for g in groups) / total\n\nlabels = [0, 1] * 6\nprint(&#39;gini(id, 12 levels)&#39;, round(weighted_gini([[labels[i]] for i in range(12)]), 4))\nprint(&#39;gini(binary split)&#39;, round(weighted_gini([labels[:6], labels[6:]]), 4))\nprint(&#39;gini(root)&#39;, round(gini(labels), 4))\n' :notes='["导入 math，用 exp 与 factorial 构造级数", "rbf_direct 按距离平方的指数直接算核值", "rbf_series 拆成单样本因子与 exp(2g 乘点积) 的幂级数", "coef 逐项乘 2g，实现 (2gamma) 的 k 次方", "除以 k 阶乘，即泰勒展开的系数", "12 项截断已收敛到直接公式的 6 位小数", "3 项截断丢掉高次项，数值明显偏低", "gini 实现 1 减各类占比平方和", "weighted_gini 按子节点样本数加权", "12 个样本标签各半，根节点基尼 0.5", "把 id 类特征切成 12 个单样本纯叶，加权基尼降到 0", "二分切法加权基尼仍是 0.5，说明高基数切分是虚假增益", "SVM 最大化间隔 2/||w||，模型只由支持向量决定；软间隔用 C 权衡误分类惩罚", "核技巧用 K(x,z)=φ(x)·φ(z) 隐式算高维内积；RBF 核 K=exp(-γ||x-z||²) 对应无限维", "C 大间隔窄易过拟合，gamma 大影响半径小边界碎；SVC 默认 C=1.0、gamma=&#39;scale&#39;", "树用基尼 1-Σp² 或熵选切分，取加权不纯度最小处；连续特征候选点是相邻取值中点", "树必须限 max_depth / min_samples_leaf / ccp_alpha；边界是阶梯状且不能外推", "随机森林 = Bagging + 特征子采样，方差约 ρσ²+(1-ρ)σ²/B；特征重要性不是因果", "SVM 最大化间隔 2/||w||，模型只由支持向量决定；软间隔用 C 权衡误分类惩罚", "核技巧用 K(x,z)=φ(x)·φ(z) 隐式算高维内积；RBF 核 K=exp(-γ||x-z||²) 对应无限维", "C 大间隔窄易过拟合，gamma 大影响半径小边界碎；SVC 默认 C=1.0、gamma=&#39;scale&#39;", "树用基尼 1-Σp² 或熵选切分，取加权不纯度最小处；连续特征候选点是相邻取值中点", "树必须限 max_depth / min_samples_leaf / ccp_alpha；边界是阶梯状且不能外推", "随机森林 = Bagging + 特征子采样，方差约 ρσ²+(1-ρ)σ²/B；特征重要性不是因果", "SVM 最大化间隔 2/||w||，模型只由支持向量决定；软间隔用 C 权衡误分类惩罚", "核技巧用 K(x,z)=φ(x)·φ(z) 隐式算高维内积；RBF 核 K=exp(-γ||x-z||²) 对应无限维", "C 大间隔窄易过拟合，gamma 大影响半径小边界碎；SVC 默认 C=1.0、gamma=&#39;scale&#39;", "树用基尼 1-Σp² 或熵选切分，取加权不纯度最小处；连续特征候选点是相邻取值中点", "树必须限 max_depth / min_samples_leaf / ccp_alpha；边界是阶梯状且不能外推", "随机森林 = Bagging + 特征子采样，方差约 ρσ²+(1-ρ)σ²/B；特征重要性不是因果", "SVM 最大化间隔 2/||w||，模型只由支持向量决定；软间隔用 C 权衡误分类惩罚", "核技巧用 K(x,z)=φ(x)·φ(z) 隐式算高维内积；RBF 核 K=exp(-γ||x-z||²) 对应无限维", "C 大间隔窄易过拟合，gamma 大影响半径小边界碎；SVC 默认 C=1.0、gamma=&#39;scale&#39;", "树用基尼 1-Σp² 或熵选切分，取加权不纯度最小处；连续特征候选点是相邻取值中点"]' title='扩展示例逐行讲解' />


### SMO 的双变量解析更新与工作集选择

**SVM 推导链与 scikit-learn 源码**

| 步骤 | 数学形式 | 结论 / 源码 |
| --- | --- | --- |
| 原始问题 | min 1/2 乘 \|\|w\|\| 平方 + C 求和 xi_i | 软间隔凸二次规划，alpha_i 被 C 截断 |
| 表示定理 | w = 求和 alpha_i y_i phi(x_i) | 最优 w 只是训练样本的线性组合 |
| 对偶目标 | max 求和 alpha_i - 1/2 求和 alpha_i alpha_j y_i y_j K_ij | 样本只以内积出现，换 K 即核技巧 |
| KKT 互补松弛 | alpha_i = 0 / 0 小于 alpha_i 小于 C / alpha_i = C | 分别对应间隔外、边界上、越界三类点 |
| SMO 工作集 | libsvm svm.cpp 的两变量解析解 | 每步只优化两个 alpha，避开 O(n 立方) 通用 QP |


## RBF 核的泰勒展开与无限维特征映射

把 `K(x,z)` = `exp(-gamma 乘 ||x - z|| 平方)` 展开：||x - z|| 平方 = ||x|| 平方 + ||z|| 平方 - 2 乘 x 点乘 z，于是 `K = exp`(-gamma||x|| 平方) 乘 `exp(-gamma||z|| 平方)` 乘 `exp(2gamma 乘 x 点乘 z)`。

前两项只依赖单个样本，可吸收进缩放；

关键在 `exp(2gamma 乘 x 点乘 z)` = 从 `k = 0` 到无穷 求和 (2gamma) 的 k 次方 除以 k 阶乘 再乘 (x 点乘 z) 的 k 次方，而 (x 点乘 z) 的 k 次方正是 k 次多项式核，展开后是所有次数不超过 k 的单项式 `phi(x)` 乘 `phi(z)` 之和。

所以 RBF 对应的 `phi(x)` 落在无穷维空间，含从常数、一次到任意高次单项式的加权和，权重 (2gamma) 的 k 次方 除以 k 阶乘 随 k 快速衰减。

这解释两件事：RBF 能表达任意复杂边界（无限维里做线性分隔），以及 gamma 控制衰减——gamma 大则高次项相对权重变大、边界碎，gamma 等价于高斯宽度 sigma 满足 `gamma = 1` 除以 (2 sigma 平方)。

实测上用 12 项截断的级数重建 RBF 值能与直接公式吻合到 6 位小数，3 项截断就明显偏低，直观看到「无限维」不是比喻而是收敛的级数。Mercer 条件要求 Gram 矩阵半正定，正是这串非负系数 (2gamma) 的 k 次方 除以 k 阶乘 不小于 0 保证的；正文只说 RBF 对应无限维，这里给出级数与系数。

<Term word='弱连接剪枝' text='Breiman 的 CART 代价复杂度剪枝把每个内部节点 t 的剪枝阈值定义为 g(t) = (R(t) - R(T_t)) 除以 (叶数 T_t 减 1)，R 是误分代价；取 g 最小的节点先剪，得到一串递增的 alpha 与嵌套子树序列，再用独立验证集或交叉验证在序列里选一棵。它保证每步剪掉的都是「单位叶数换来的代价增量最小」的子树，比一次性拍一个 ccp_alpha 更可解释。' />


### 基尼增益对高基数特征的偏置实测

一棵在训练集上长到 200 片叶子的树，直接用 `ccp_alpha=0.01` 剪完只剩 12 片，团队说不清这个数拍得对不对。

代价复杂度剪枝其实不该猜单个 alpha：先自底向上算每个内部节点的 `g(t)`，按 g 从小到大依次剪，得到一串嵌套子树与对应的 alpha 序列，再用验证集误差在这串子树里挑，比一次性拍 alpha 可解释得多。

下例给出三个内部节点的 `R(t)`、子树 R 与叶数，算出 g 并排序，能看到 t1 的 g 等于 0.1 最小、应最先被剪，alpha 到 0.15 才轮到 t2。

真实项目把这套序列换成 `DecisionTreeClassifier.cost_complexity_pruning_path`，再对每棵候选树做交叉验证。

```python
def g(R_leaf, R_subtree, n_leaves):
    return (R_leaf - R_subtree) / (n_leaves - 1)

nodes = [
    ('t1', g(0.30, 0.10, 3)),
    ('t2', g(0.20, 0.05, 2)),
    ('t3', g(0.40, 0.00, 4)),
]
seq = sorted(nodes, key=lambda t: t[1])
print('weakest-link alpha order', [(n, round(a, 4)) for n, a in seq])
print('first prune', seq[0][0], 'at alpha', round(seq[0][1], 4))

```


## 代价复杂度剪枝的 alpha 序列与弱连接消除

<Quiz no='099-X' q='关于软间隔 SVM 的对偶与 RBF 核，下面哪项准确？' :options='["对偶里 0 不大于 alpha_i 不大于 C 由 C 减 alpha_i 减 mu_i = 0 推出；RBF 展开为 exp(2gamma 点积) 的幂级数，对应无限维特征空间", "alpha_i 没有上界，C 只影响偏置 b 的取值", "RBF 核对应有限三维特征空间，泰勒展开取三项就精确", "KKT 条件里 alpha_i 大于 0 的样本都是噪声点，删掉能提升效果"]' answer="0" explain='对拉格朗日函数求 xi_i 偏导得 C 减 alpha_i 减 mu_i = 0，配合 mu_i 不小于 0 才有 alpha_i 不大于 C，这正是软间隔在支持向量数量上的体现。RBF 的 exp(2gamma 乘 x 点乘 z) 级数含所有次数的多项式核，系数非负且随 k 衰减，故对应无限维且满足 Mercer 条件。alpha_i 大于 0 的是支持向量，恰是决定模型的点，删掉会改变边界。' />

<Exercise title='用 RBF 泰勒级数验证无限维映射' task='实现 rbf_series(x, z, g, terms)，用不同 terms 重建 exp(-gamma 乘 ||x-z|| 平方)，观察 12 项与 3 项的误差，并说明系数 (2gamma) 的 k 次方 除以 k 阶乘 为何保证核矩阵半正定。' solution='import math\n\ndef rbf_series(x, z, g=0.5, terms=12):\n    dot = sum(a * b for a, b in zip(x, z))\n    nx = sum(a * a for a in x)\n    nz = sum(b * b for b in z)\n    s = 0.0\n    coef = 1.0\n    for k in range(terms):\n        s += coef * (dot ** k) / math.factorial(k)\n        coef *= 2 * g\n    return math.exp(-g * nx) * math.exp(-g * nz) * s\n\nx, z = [1.0, 0.5], [0.8, 0.3]\ndirect = math.exp(-0.5 * sum((a - b) ** 2 for a, b in zip(x, z)))\nprint(&#39;direct&#39;, round(direct, 6))\nprint(&#39;3 terms&#39;, round(rbf_series(x, z, terms=3), 6))\nprint(&#39;12 terms&#39;, round(rbf_series(x, z), 6))\n' explain='exp(-gamma 乘 ||x-z|| 平方) 拆成单样本因子与 exp(2gamma 乘 x 点乘 z)，后者是 求和 (2gamma) 的 k 次方 乘 (x 点乘 z) 的 k 次方 除以 k 阶乘；每一项 (x 点乘 z) 的 k 次方 都是合法多项式核且系数非负，非负线性组合仍半正定，故 RBF 满足 Mercer 条件。三项截断丢掉高次项会明显偏低，12 项才收敛到直接公式，直观看到无限维不是修辞而是收敛的级数。' />


### libsvm 核缓存与一对一多分类的计算成本

<ConceptDiagram type='flow4' title='第 099 讲 · 扩展图解' labels='n 个训练样本|n 乘 n 的 Gram 矩阵|LRU 核缓存|支持向量子集' caption='libsvm 把 K(x_i, x_j) 缓存在 LRU 里避免重复计算，但核矩阵本身是 O(n 平方)；一对一多分类要训 k(k-1)/2 个二分类器，类别数一多成本迅速上升。' />


## 练习、自测与选型速记

<Exercise title='基础：手算基尼与最佳切分' task='对 data=[(1,&#39;N&#39;),(2,&#39;N&#39;),(3,&#39;N&#39;),(4,&#39;P&#39;),(5,&#39;P&#39;),(6,&#39;P&#39;)] 手算每个候选阈值的加权基尼，说明为什么 3.5 是最优切分。' solution='def gini(ls):\n    n=len(ls); c={}\n    for l in ls: c[l]=c.get(l,0)+1\n    return 1-sum((v/n)**2 for v in c.values())\ndata=[(1,&#39;N&#39;),(2,&#39;N&#39;),(3,&#39;N&#39;),(4,&#39;P&#39;),(5,&#39;P&#39;),(6,&#39;P&#39;)]\nfor t in (1.5,2.5,3.5,4.5,5.5):\n    L=[l for x,l in data if x&lt;=t]; R=[l for x,l in data if x&gt;t]\n    w=(len(L)*gini(L)+len(R)*gini(R))/len(data)\n    print(t, round(w,3))' explain='t=3.5 时左 3 个全 N、右 3 个全 P，两边基尼都是 0，加权不纯度为 0，是全局最小；其它阈值都会混入异类、加权不纯度大于 0。' />

<Exercise title='进阶：用数值实验验证 Bagging 降方差' task='构造三棵树对同一批样本的预测，比较单棵方差与三棵逐样本平均后的方差，并说明随机森林为何还要做特征子采样。' solution='import statistics as st\ntrees=[[10.5,9.2,11.1,8.7,10.8],[9.8,11.5,9.1,10.6,9.9],[12.0,8.5,10.2,11.3,9.4]]\nprint(&#39;single&#39;, round(st.variance(trees[0]),3))\nprint(&#39;bagged&#39;, round(st.variance([st.mean(c) for c in zip(*trees)]),3))' explain='平均把不相关的扰动抵消，方差从 1.103 降到 0.142。但树间相关项 ρ·σ² 是平均消不掉的下限，随机森林再随机选特征子集来降低 ρ。' />

<Quiz no='099-1' q='一棵决策树训练集 100% 准确、验证集很差，最直接的修复是？' :options='["限制 max_depth / min_samples_leaf 并做交叉验证或剪枝", "增加更多训练特征", "换更大的C（对SVM而言）", "把树改成不纯度更高的准则"]' answer="0" explain='不受限的树会分到每叶都纯、把噪声背下来，方差极大；限制深度、叶内最少样本或用 ccp_alpha 剪枝才是针对过拟合的修复。' />

<Quiz no='099-2' q='关于 RBF 核 SVM 的 C 与 gamma，下面哪项准确？' :options='["C 越大越不容忍错分、间隔越窄；gamma 越大影响半径越小、边界越碎", "C 越大模型越简单", "gamma 越大边界越平滑", "两者都不影响结果，只影响训练速度"]' answer="0" explain='C 是误分类惩罚强度，大 C 逼模型少犯错、间隔变窄易过拟合；gamma 控制 RBF 的衰减，大 gamma 让单样本影响范围变小、边界碎片化。' />

<Quiz no='099-3' q='核技巧的核心收益是？' :options='["用核函数隐式计算高维内积，无需显式构造映射 φ(x)", "把数据量减少一半", "让所有数据线性可分且不用调参", "去掉支持向量"]' answer="0" explain='对偶形式只依赖内积，用满足 Mercer 条件的 K(x,z) 替换内积即等价于高维空间的线性分隔，避免显式计算高维甚至无限维特征。' />

<Predict no='099-P' q='前面 code 的 best_split(data) 返回的加权基尼是多少？' :options='["0.0", "0.5", "0.25"]' answer='0' output='best split (0.0, 3.5, 3, 3)' explain='在 t=3.5 处切开，左 3 个 N、右 3 个 P，两个子节点基尼都是 0，加权不纯度为 0.0，因此最佳切分返回 (0.0, 3.5, 3, 3)。' />

<KnowledgeCard :points='["SVM 最大化间隔 2/||w||，模型只由支持向量决定；软间隔用 C 权衡误分类惩罚", "核技巧用 K(x,z)=φ(x)·φ(z) 隐式算高维内积；RBF 核 K=exp(-γ||x-z||²) 对应无限维", "C 大间隔窄易过拟合，gamma 大影响半径小边界碎；SVC 默认 C=1.0、gamma=&#39;scale&#39;", "树用基尼 1-Σp² 或熵选切分，取加权不纯度最小处；连续特征候选点是相邻取值中点", "树必须限 max_depth / min_samples_leaf / ccp_alpha；边界是阶梯状且不能外推", "随机森林 = Bagging + 特征子采样，方差约 ρσ²+(1-ρ)σ²/B；特征重要性不是因果"]' :pitfalls='["不设 max_depth / min_samples_leaf，训练集 100% 线上很差", "RBF SVM 直接喂未缩放特征，边界全是碎块", "把特征重要性排名当成业务因果结论", "不限制树深又不做交叉验证，训练集必然满分而线上表现很差"]' summary='树模型几乎不需要特征缩放、能处理混合类型，代价是外推能力差、边界呈阶梯状；SVM 在小样本高维上依然很强' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| SVM 最大化间隔 2/\|\|w\|\|，模型只由支持向量决定；软间隔用 C 权衡误分类惩罚 | 建立直觉 |
| 核技巧用 K(x,z)=φ(x)·φ(z) 隐式算高维内积；RBF 核 K=exp(-γ\|\|x-z\|\|²) 对应无限维 | 跑通示例 |
| C 大间隔窄易过拟合，gamma 大影响半径小边界碎；SVC 默认 C=1.0、gamma='scale' | 深入边界 |
| 树用基尼 1-Σp² 或熵选切分，取加权不纯度最小处；连续特征候选点是相邻取值中点 | 工程落地 |
| 树必须限 max_depth / min_samples_leaf / ccp_alpha；边界是阶梯状且不能外推 | 随堂检测 |
| 随机森林 = Bagging + 特征子采样，方差约 ρσ²+(1-ρ)σ²/B；特征重要性不是因果 | 复盘 |

1. SVM 最大化间隔 2/||w||，模型只由支持向量决定；软间隔用 C 权衡误分类惩罚

2. 核技巧用 K(x,z)=φ(x)·φ(z) 隐式算高维内积；RBF 核 K=exp(-γ||x-z||²) 对应无限维

3. C 大间隔窄易过拟合，gamma 大影响半径小边界碎；SVC 默认 C=1.0、gamma='scale'

[下一讲：集成学习：Boosting、XGBoost 与 LightGBM](/data-ai/ensemble)

<FillBlank no='099-F' tpl='___ gini(labels):' :answers='["def"]' hint='回想本讲关于 间隔最大化与核技巧 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 间隔最大化、核技巧与软间隔 C 的落点。' />
