"""
第 097 讲 · 机器学习流程：特征、划分与评价
与教程正文一一对应的示例代码

课程页面：/data-ai/ml-workflow
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/097-ml-workflow.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/097-ml-workflow.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# all-negative {'accuracy': 0.99, 'precision': 0.0, 'recall': 0.0, 'f1': 0.0}
# a-model {'accuracy': 0.975, 'precision': 0.2, 'recall': 0.5, 'f1': 0.286}

def metrics(tp, fp, fn, tn):
    acc = (tp + tn) / (tp + fp + fn + tn)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return dict(accuracy=round(acc, 3), precision=round(prec, 3),
                recall=round(rec, 3), f1=round(f1, 3))

print('all-negative', metrics(0, 0, 10, 990))
print('a-model', metrics(5, 20, 5, 970))

# ======================== 2. 对照写法 ========================
# 预期输出：
# leak [1.16, 1.28, 1.39]
# clean [12.02, 12.73, 13.44]

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

# ======================== 3. 原理验证 ========================
# 预期输出：
# fold 0 val [0, 5] train_n 8
# fold 1 val [1, 6] train_n 8
# fold 2 val [2, 7] train_n 8
# fold 3 val [3, 8] train_n 8
# fold 4 val [4, 9] train_n 8
# each sample validated once? True

def kfold(n, k):
    idx = list(range(n))
    folds = [idx[i::k] for i in range(k)]
    return [([j for j in idx if j not in f], f) for f in folds]

cover = []
for i, (tr, va) in enumerate(kfold(10, 5)):
    cover.extend(va)
    print('fold', i, 'val', va, 'train_n', len(tr))
print('each sample validated once?', sorted(cover) == list(range(10)))

# ======================== 4. 工程案例 ========================

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
