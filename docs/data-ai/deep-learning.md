---
title: 第 103 讲 · 深度学习与 PyTorch：张量、自动微分与训练循环
description: 从零跑通一个神经网络训练
---

<StageHeader stage='L9 · 数据与 AI' level='★★★★☆' time='50 分钟' goal='从零跑通一个神经网络训练' prereq='第 102 讲 · 模型调优：交叉验证、正则化与过拟合' />

# 第 103 讲 · 深度学习与 PyTorch：张量、自动微分与训练循环

经典模型调得再细，特征仍要人想；碰到图像文本，让结构自己学表示。深度学习这一讲只求从零把训练跑通。费心的不是反向传播（前向加一行 backward 就够），而是数据怎么喂、每轮怎么验。

先认张量与设备、计算图与 autograd，看梯度怎么记下；再搭 Dataset / DataLoader，挑好损失与优化器；最后串起训练 / 验证循环，顺带说 CNN 与 RNN 的结构动机和 zero_grad、eval 的小动作。需要 NumPy 广播、函数与类的写法，以及前面的训练 / 验证划分。跑完这一讲，你能盯住一个小网络的训练，先在小样本上过拟合验管道。


## 忘了 zero_grad，loss 越训越怪

手写的训练循环 loss 一路下降，验证指标却来回跳，显存还一轮比一轮高，最后 OOM。

查了半天才发现两处低级错误：每轮 backward 之前忘了 `optimizer.zero_grad()`，梯度被累加到上一轮；

验证阶段没有包 no_grad、也没切 eval，dropout 和 BatchNorm 仍在按训练模式更新，还给验证批次白建了一堆计算图。另一组同事更隐蔽：随机种子没固定，同一份代码两次跑出的指标差两个点，根本判断不了某次改动是不是真的有效。

自动微分把反向传播变成了「普通前向代码加一行 backward」，看似省事，真正需要自己设计的却是数据管道、损失口径与评估纪律。本讲用纯标准库实现一个极简自动微分，把梯度累加、链式法则与训练循环都变成能核对的数字。

<Callout type="warn" title='先看一个真实会出错的写法' text='每轮忘 zero_grad，梯度被累加到上一轮：PyTorch 的 .grad 是累加语义，支持多损失分支，但训练循环默认不会自动清零' />


## 张量、设备与计算图：autograd 记了什么

PyTorch 的核心对象是 `torch.Tensor`：一个带 dtype、shape、device、requires_grad 等属性的多维数组。dtype 默认 `torch.float32`，混合精度用 float16 / bfloat16 省显存；

device 决定张量在 cpu 还是 cuda（或 mps），模型与输入必须在同一设备，否则报 Expected all tensors to be on the same device。

`requires_grad=True` 时，PyTorch 采用动态图（eager）：前向每做一次运算就动态记录一个 Function 节点，形成一张有向无环图，节点里存了反向所需的输入与反向函数。

对标量 loss 调用 `loss.backward()`，autograd 从根反向拓扑遍历，按链式法则把梯度累加到每个叶子张量的 .grad；

若 loss 不是标量，必须传 gradient 参数指定初始梯度。

`tensor.detach()` 得到共享存储但不建图的新张量，with `torch.no_grad()` 在上下文里彻底关闭图构建，.`item()` 把单元素张量取成 Python 标量。

计算图在 backward 后默认释放（保留需 `retain_graph=True`），所以同一个 loss 不能无参二次 backward。

最关键的设计是「梯度累加」而非覆盖：多个损失分支共享参数时各分支的梯度要相加，正因为如此每轮更新前必须显式 `zero_grad()`，否则上一轮的梯度会混进本轮。

```python
class Value:
    def __init__(self, data, children=()):
        self.data = data
        self.grad = 0.0
        self._prev = set(children)
        self._backward = lambda: None
    def __add__(self, o):
        o = o if isinstance(o, Value) else Value(o)
        out = Value(self.data + o.data, (self, o))
        def _b():
            self.grad += out.grad
            o.grad += out.grad
        out._backward = _b
        return out
    def __mul__(self, o):
        o = o if isinstance(o, Value) else Value(o)
        out = Value(self.data * o.data, (self, o))
        def _b():
            self.grad += o.data * out.grad
            o.grad += self.data * out.grad
        out._backward = _b
        return out
    def backward(self):
        topo, seen = [], set()
        def build(v):
            if v not in seen:
                seen.add(v)
                for c in v._prev: build(c)
                topo.append(v)
        build(self)
        self.grad = 1.0
        for v in reversed(topo): v._backward()

w = Value(2.0); x = Value(3.0); b = Value(1.0)
y = w * x + b
y.backward()
print('y', y.data)
print('dy/dw', w.grad, 'dy/dx', x.grad, 'dy/db', b.grad)
```

<OutputBox title='主示例运行结果' output='y 7.0\ndy/dw 3.0 dy/dx 2.0 dy/db 1.0' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Value:\n    def __init__(self, data, children=()):\n        self.data = data\n        self.grad = 0.0\n        self._prev = set(children)\n        self._backward = lambda: None\n    def __add__(self, o):\n        o = o if isinstance(o, Value) else Value(o)\n        out = Value(self.data + o.data, (self, o))\n        def _b():\n            self.grad += out.grad\n            o.grad += out.grad\n        out._backward = _b\n        return out\n    def __mul__(self, o):\n        o = o if isinstance(o, Value) else Value(o)\n        out = Value(self.data * o.data, (self, o))\n        def _b():\n            self.grad += o.data * out.grad\n            o.grad += self.data * out.grad\n        out._backward = _b\n        return out\n    def backward(self):\n        topo, seen = [], set()\n        def build(v):\n            if v not in seen:\n                seen.add(v)\n                for c in v._prev: build(c)\n                topo.append(v)\n        build(self)\n        self.grad = 1.0\n        for v in reversed(topo): v._backward()\n\nw = Value(2.0); x = Value(3.0); b = Value(1.0)\ny = w * x + b\ny.backward()\nprint(&#39;y&#39;, y.data)\nprint(&#39;dy/dw&#39;, w.grad, &#39;dy/dx&#39;, x.grad, &#39;dy/db&#39;, b.grad)' :notes='["定义极简标量自动微分对象，模拟 autograd 的核心机制", "构造时记录数值、子节点集合，children 默认空元组", "data 存前向的数值", "grad 初始为 0，反向传播会把梯度累加到这里", "_prev 保存产生该节点的子节点，构成计算图的边", "_backward 默认空函数，叶子节点无需反向", "重载加法，模拟前向运算并登记反向函数", "把标量操作数统一包装成 Value，支持与常数相加", "加法结果节点，子节点是参与运算的两个 Value", "定义加法的反向：导数按 1 分派，用 += 累加而非覆盖", "加法的局部导数为 1，两侧各加 out.grad", "同侧也要累加，体现梯度可来自多个分支", "把反向函数挂到结果节点上", "返回前向结果", "重载乘法", "同样把常数包装成 Value", "乘法结果节点", "定义乘法的反向闭包", "d(out)/d(self) = o.data，乘上游梯度累加", "d(out)/d(o) = self.data，乘上游梯度累加", "挂载反向函数", "返回前向结果", "backward 从当前节点出发做一次完整反向传播", "topo 存拓扑序，seen 防重复访问", "递归构建从叶到根的计算图顺序", "只处理未访问过的节点，避免环与重复", "标记为已访问", "先递归子节点，保证子节点排在父节点之前", "子节点处理完再把当前节点加入拓扑序列", "从根节点启动拓扑构建", "标量损失的种子梯度设为 1.0（dy/dy）", "逆序遍历拓扑序列，逐个触发反向函数就是链式法则", "构造三个叶子张量 w、x、b", "前向：y = w*x + b，动态建图", "从 y 反向，计算各叶子节点的梯度", "打印前向结果 2*3+1 = 7.0", "打印梯度：dy/dw=x=3、dy/dx=w=2、dy/db=1"]' title='第 103 讲 · 深度学习与 PyTorch：张量、自动微分与训练循环' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 用中心差分校验 backward 的梯度

```python
def f(x): return x ** 2 + 3 * x + 1
def analytic(x): return 2 * x + 3
def numerical(x, h=1e-5): return (f(x + h) - f(x - h)) / (2 * h)
for x in (0.0, 2.0, -3.0):
    print('x', x, 'analytic', round(analytic(x), 4), 'numerical', round(numerical(x), 4))
```

<OutputBox title='原理验证' output='x 0.0 analytic 3.0 numerical 3.0\nx 2.0 analytic 7.0 numerical 7.0\nx -3.0 analytic -3.0 numerical -3.0' />

<CodeTabs :tabs='[{"label": "主示例", "code": "class Value:\n    def __init__(self, data, children=()):\n        self.data = data\n        self.grad = 0.0\n        self._prev = set(children)\n        self._backward = lambda: None\n    def __add__(self, o):\n        o = o if isinstance(o, Value) else Value(o)\n        out = Value(self.data + o.data, (self, o))\n        def _b():\n            self.grad += out.grad\n            o.grad += out.grad\n        out._backward = _b\n        return out\n    def __mul__(self, o):\n        o = o if isinstance(o, Value) else Value(o)\n        out = Value(self.data * o.data, (self, o))\n        def _b():\n            self.grad += o.data * out.grad\n            o.grad += self.data * out.grad\n        out._backward = _b\n        return out\n    def backward(self):\n        topo, seen = [], set()\n        def build(v):\n            if v not in seen:\n                seen.add(v)\n                for c in v._prev: build(c)\n                topo.append(v)\n        build(self)\n        self.grad = 1.0\n        for v in reversed(topo): v._backward()\n\nw = Value(2.0); x = Value(3.0); b = Value(1.0)\ny = w * x + b\ny.backward()\nprint(&#39;y&#39;, y.data)\nprint(&#39;dy/dw&#39;, w.grad, &#39;dy/dx&#39;, x.grad, &#39;dy/db&#39;, b.grad)", "note": "张量、设备、计算图与 autograd"}, {"label": "对照 / 进阶", "code": "xs = [1, 2, 3]\nys = [3, 5, 7]\nw, b, lr = 0.0, 0.0, 0.1\nfor epoch in range(3):\n    grad_w = grad_b = 0.0\n    for x, y in zip(xs, ys):\n        pred = w * x + b\n        grad_w += 2 * (pred - y) * x\n        grad_b += 2 * (pred - y)\n    w -= lr * grad_w / len(xs); b -= lr * grad_b / len(xs)\n    loss = sum((w * x + b - y) ** 2 for x, y in zip(xs, ys)) / len(xs)\n    print(&#39;epoch&#39;, epoch, &#39;loss&#39;, round(loss, 4), &#39;w&#39;, round(w, 3), &#39;b&#39;, round(b, 3))", "note": "Dataset / DataLoader / 损失 / 优化器"}]' title='两种写法切换看' />


## Dataset 与 DataLoader：数据怎么进管道

数据管道决定训练能否稳定跑起来。

Dataset 实现 `__len__` 与 `__getitem__` 定义「如何取一条样本」，DataLoader 在其上负责 batch_size、shuffle（每轮打乱顺序）、num_workers 多进程并行加载、collate_fn 把单条样本拼成批、pin_memory 锁页内存加速主机到 GPU 的拷贝；

图像任务把 Resize / Normalize / 随机增强放进 transform，且归一化用的均值方差只能在训练集上统计。

损失函数按任务选：回归用 MSELoss，多分类用 CrossEntropyLoss（内部已含 LogSoftmax + NLLLoss，输入应是原始 logits 而非 softmax 概率，重复 softmax 会破坏数值稳定），二分类用 BCEWithLogitsLoss（把 sigmoid 与 BCE 合并，用 log-sum-exp 技巧避免溢出）。

优化器 SGD 带 momentum、Adam 自适应一阶二阶矩估计，学习率 lr 是最敏感的超参，配合 StepLR / CosineAnnealingLR 等 scheduler 衰减；

更新动作是 `optimizer.step()`，梯度裁剪用 clip_grad_norm_ 防爆炸。

可复现要把 `torch.manual_seed`、`numpy.random.seed`、`random.seed` 一起固定，必要时设 `torch.backends.cudnn.deterministic=True`，并把 DataLoader 的 worker 初始化也固定。

<ConceptDiagram type='layers3' title='第 103 讲 · 分层视角' labels='张量、设备、计算图与 autograd|Dataset / DataLoader|训练/验证循环、CNN 与 RNN 的结|CNN 与 RNN 直觉' caption='训练/验证循环、CNN 与 RNN 的结构动机' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **CNN 与 RNN 直觉** 落在哪一层。


## 损失函数与优化器的选型

**张量属性与常见取值**

| 属性 | 含义 | 常见取值 | 典型错误 |
| --- | --- | --- | --- |
| dtype | 元素类型 | float32 / float16 / bfloat16 | 输入与模型 dtype 不一致 |
| device | 所在设备 | cpu / cuda / mps | 跨设备运算报错 |
| requires_grad | 是否建图 | True / False | 验证阶段忘关，显存上涨 |
| shape | 各维大小 | 如 (B, C, H, W) | batch 维漏掉 |

<Callout type="tip" title='核心心智模型' text='PyTorch 的核心对象是 torch.Tensor：一个带 dtype、shape、device、requires_grad 等属性的多维数组。dtype 默认 torch.float32，混合精度用 float16 / bfloat16 省显存；device 决定张量在 cpu 还是 cuda' />


## 训练循环：forward、backward、step 的顺序

一个可靠的 epoch 循环顺序固定：`model.train()` 开训练模式 → 遍历 DataLoader → `optimizer.zero_grad()` → forward 得 logits → 计算 loss → `loss.backward()` → `optimizer.step()`。

验证阶段必须 `model.eval()` 把 dropout 关闭、BatchNorm 切到用 running 统计量，并包 with `torch.no_grad()` 不建图，既省显存又避免指标抖动；

验证完回到训练态要再 `model.train()`。每个 epoch 同时记录训练与验证的 loss 和指标，而不是只看训练 loss 下降。工程上有两条高性价比纪律：先固定随机种子、拿几十条样本让模型过拟合到接近零误差，能记住就说明数据管道、损失与反向链路是通的，再放大数据量；

训练中监控梯度范数与显存，梯度消失/爆炸、显存悄悄涨满往往是忘记 zero_grad 或验证没关梯度的信号。CNN 的结构动机是用局部感受野、权值共享与池化提取平移不变的空间特征，同样层数的参数量远小于全连接，适合图像；

RNN 用隐状态在序列间传递信息，但朴素 RNN 存在长程梯度消失，LSTM / GRU 用门控缓解，Transformer 干脆用自注意力替代循环来并行建模长依赖。理解这些结构为什么被设计出来，比记住层名更有用。

```python
xs = [1, 2, 3]
ys = [3, 5, 7]
w, b, lr = 0.0, 0.0, 0.1
for epoch in range(3):
    grad_w = grad_b = 0.0
    for x, y in zip(xs, ys):
        pred = w * x + b
        grad_w += 2 * (pred - y) * x
        grad_b += 2 * (pred - y)
    w -= lr * grad_w / len(xs); b -= lr * grad_b / len(xs)
    loss = sum((w * x + b - y) ** 2 for x, y in zip(xs, ys)) / len(xs)
    print('epoch', epoch, 'loss', round(loss, 4), 'w', round(w, 3), 'b', round(b, 3))
```

<OutputBox title='对照写法：先自己猜，再点开' output='epoch 0 loss 0.3319 w 2.267 b 1.0\nepoch 1 loss 0.0053 w 2.018 b 0.893\nepoch 2 loss 0.0013 w 2.044 b 0.908' guess="true" />


### eval 与 no_grad：验证阶段的两个开关

**损失函数选型**

| 任务 | 推荐损失 | 输入要求 | 注意 |
| --- | --- | --- | --- |
| 回归 | MSELoss | 预测与标签同形 | 对离群点敏感 |
| 多分类 | CrossEntropyLoss | 原始 logits | 内部已含 LogSoftmax，别先 softmax |
| 二分类 | BCEWithLogitsLoss | 原始 logits | 合并 sigmoid 更数值稳定 |

<Callout type="warn" title='本讲最容易踩的坑' text='每轮忘 zero_grad，梯度被累加到上一轮：PyTorch 的 .grad 是累加语义，支持多损失分支，但训练循环默认不会自动清零' />


## 动态图、叶子张量与梯度累加语义

autograd 的本质是反向模式自动微分：把前向计算记成一张由基本运算构成的 DAG，每个节点保存局部导数规则。对复合函数 `y = f`(`g(x)`)，链式法则 dy/dx = (dy/dg)·(dg/dx) 在图上体现为：从根节点（损失）出发，逆拓扑序把上游传来的梯度乘以本节点局部导数、累加到子节点。

实现上用拓扑排序保证「父节点的梯度先算完再传给子节点」，用 += 累加是因为一个节点可能通过多条路径影响输出（多分支损失），覆盖会丢掉其它路径的贡献——这正是 PyTorch 不自动清零、要求显式 zero_grad 的原因。

数值梯度校验用中心差分 (`f(x+h)`-`f(x-h)`)/(2h)，截断误差 `O(h²)`，可与 autograd 结果互证：本讲 probe 里 `f(x)`=x²+3x+1 的解析导数 2x+3 与中心差分在 `x=0`、2、-3 三点完全一致，证明反向传播不是近似而是精确的链式法则。

CrossEntropyLoss 把 log-sum-exp 稳定技巧内建，避免直接算 softmax 时的上溢。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 每轮忘 zero_grad，梯度被累加到上一轮 | PyTorch 的 .grad 是累加语义，支持多损失分支，但训练循环默认不会自动清零 | 每个 batch 的 forward 之前调用 optimizer.zero_grad()，或设 set_to_none=True |
| 验证阶段没关梯度也没 eval，指标抖动、显存涨满 | dropout/BatchNorm 仍按训练模式工作，且验证批次仍构建计算图占显存 | 验证用 model.eval() + with torch.no_grad():，验证结束回到 model.train() |
| 随机种子未固定，无法判断改动是否真的有效 | 参数初始化、数据打乱、dropout 都依赖随机源，两次运行不可比 | 固定 torch.manual_seed / numpy / random 种子，必要时设 cudnn.deterministic=True |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：每轮忘 zero_grad，梯度被累加到上一", "body": "PyTorch 的 .grad 是累加语义，支持多损失分支，但训练循环默认不会自动清零", "tip": "每个 batch 的 forward 之前调用 optimizer.zero_grad()，或设 set_to_none=True"}, {"title": "第 2 步：验证阶段没关梯度也没 eval，指标抖动、显", "body": "dropout/BatchNorm 仍按训练模式工作，且验证批次仍构建计算图占显存", "tip": "验证用 model.eval() + with torch.no_grad():，验证结束回到 model.train()"}, {"title": "第 3 步：随机种子未固定，无法判断改动是否真的有效", "body": "参数初始化、数据打乱、dropout 都依赖随机源，两次运行不可比", "tip": "固定 torch.manual_seed / numpy / random 种子，必要时设 cudnn.deterministic=True"}]' />


## 先在小样本上过拟合，验证整条训练管道

调试深度学习代码最省时的纪律是：先别上全量数据，拿几条样本让模型过拟合到接近零误差。能做到就说明数据管道、损失、反向与更新链路都通，再放大数据；做不到就先查管道。

下面用纯标准库把这条纪律写成一个最小训练循环：forward / loss / step 三个函数封装前向、损失与一步参数更新，主循环跑 5 个 epoch 打印 loss 单调下降。它要强调的是循环顺序（清零等价物在这里是每轮重新计算梯度 → 更新 → 再算 loss）与可核对的收敛轨迹。

真实项目把 step 换成 `loss.backward()` + `optimizer.step()`、在每轮开头补 `optimizer.zero_grad()`，并在验证段包 no_grad，结构不变。

```python
xs = [1.0, 2.0, 3.0]
ys = [3.0, 5.0, 7.0]
w = b = 0.0
lr = 0.1
def forward(x): return w * x + b
def loss():
    return sum((forward(x) - y) ** 2 for x, y in zip(xs, ys)) / len(xs)
def step():
    global w, b
    gw = sum(2 * (forward(x) - y) * x for x, y in zip(xs, ys)) / len(xs)
    gb = sum(2 * (forward(x) - y) for x, y in zip(xs, ys)) / len(xs)
    w -= lr * gw
    b -= lr * gb
for epoch in range(5):
    step()
    print('epoch', epoch, 'loss', round(loss(), 4))
```

<Callout type="idea" title='落地提示' text='固定随机种子、先在小样本上过拟合验证管道正确性，再放大数据量；记录每个 epoch 的训练与验证指标' />

<CheckList id='P103b' title='上线前自检' :items='["能复现并解释「每轮忘 zero_grad，梯度被累加到上一轮」", "能复现并解释「验证阶段没关梯度也没 eval，指标抖动、显存涨满」", "能复现并解释「随机种子未固定，无法判断改动是否真的有效」", "能用一条命令验证 张量与设备", "关键路径有自动化测试与失败分支"]' />


## 反向模式自动微分：一次 backward 拿全部梯度

对计算图 f: R^n 到 R^m，链式法则的整体是 Jacobian `J = dy`/dx（m 行 n 列）。前向模式沿一条输入方向 v 计算 Jv，一次传播得到「所有输出对某一个输入方向」的导数，要拿完整 J 需要 n 次传播。

反向模式从输出种子 u（标量损失时 `u=1`）出发回传 u^T J，一次传播就得到「所有输入对这一个输出组合」的梯度——训练里 n 是百万级参数、`m=1`，于是反向模式只需一次 backward，成本约为前向的 2 到 3 倍，而前向模式要 n 次，这才是 PyTorch 选 reverse-mode 的根本原因，与动态图还是静态图无关。

实现上每个节点存局部雅可比向量积 VJP，按拓扑逆序把上游梯度累加进子节点，累加用 += 而非覆盖，故共享节点的梯度来自多个分支之和，`optimizer.zero_grad()` 必须每轮清空。

源码路径（PyTorch 2.x）：torch/csrc/autograd/`engine.cpp` 的 Engine::execute 用 ready queue 做拓扑调度、torch/csrc/autograd/functions/`accumulate_grad.h` 把梯度写回叶子 .grad、torch/csrc/autograd/`autograd_meta.cpp` 维护 version counter。

推论：输出维度远大于输入（求完整 Jacobian、灵敏度分析）时反向模式反而吃亏，这时才该用 forward-mode。

<Term word='反向模式自动微分' text='从标量输出的种子梯度出发，按计算图拓扑逆序回传雅可比向量积，一次传播得到全部输入梯度，成本约为前向的 2 到 3 倍；输出维度大、输入维度小时才该改用前向模式。梯度累加而非覆盖，故每轮更新前必须 zero_grad。' />


### CrossEntropyLoss 的 log-sum-exp 与 p 减 y 梯度

交叉熵的数值稳定不是技巧而是必须：对 logits z，softmax 分母是各 `exp(z_i)` 之和，z 里有一个 1000，float32 的 exp 就上溢成 inf，随后 `log(0)` 得 -inf，梯度全线崩掉。

log-sum-exp 令 `m = max`(z)，把 log sum `exp(z_i)` 改写成 m + log sum `exp(z_i - m)`，最大指数项恒为 `exp(0)`=1，所有项落在 (0,1]，既不上溢又保留可导。

PyTorch 的 CrossEntropyLoss 把 LogSoftmax 与 NLLLoss 合并成一步，aten/src/ATen/native/`SoftMax.cpp` 的 log_softmax 先减最大值再算 exp；

合并后对 logits 的梯度化简成 dL/`dz_i = p_i` - y_i，一次前向一次反传，无需单独对 softmax 求导。由此推出三个结论：输入必须是原始 logits，手动再 softmax 会把概率重新归一化、梯度不再是 p-y；

BCEWithLogitsLoss 用 `log(1+exp(-|x|)`) + `max(x,0)` 合并 sigmoid 与 BCE，梯度是 `sigmoid(z)`-y；

loss 非标量时 backward 必须传 gradient 指定初始种子。

```python
import math

def softmax_naive(z):
    e = [math.exp(v) for v in z]
    s = sum(e)
    return [v / s for v in e]

def softmax_stable(z):
    m = max(z)
    e = [math.exp(v - m) for v in z]
    s = sum(e)
    return [v / s for v in e]

def ce_loss_grad(z, y_idx):
    p = softmax_stable(z)
    loss = -math.log(p[y_idx])
    grad = [p[i] - (1 if i == y_idx else 0) for i in range(len(z))]
    return round(loss, 4), [round(g, 4) for g in grad]

z = [2.0, 1.0, 0.1]
print('naive', [round(v, 4) for v in softmax_naive(z)])
print('stable', [round(v, 4) for v in softmax_stable(z)])
loss, grad = ce_loss_grad(z, 0)
print('loss', loss, 'grad', grad)
big = [1000.0, 1.0, 0.1]
try:
    softmax_naive(big)
    print('naive_big', 'no-overflow')
except OverflowError:
    print('naive_big', 'OverflowError')
print('stable_big', [round(v, 4) for v in softmax_stable(big)])
```

<OutputBox title='扩展示例运行结果' output='naive [0.659, 0.2424, 0.0986]\nstable [0.659, 0.2424, 0.0986]\nloss 0.417 grad [-0.341, 0.2424, 0.0986]\nnaive_big OverflowError\nstable_big [1.0, 0.0, 0.0]' />

<LineByLine code='import math\n\ndef softmax_naive(z):\n    e = [math.exp(v) for v in z]\n    s = sum(e)\n    return [v / s for v in e]\n\ndef softmax_stable(z):\n    m = max(z)\n    e = [math.exp(v - m) for v in z]\n    s = sum(e)\n    return [v / s for v in e]\n\ndef ce_loss_grad(z, y_idx):\n    p = softmax_stable(z)\n    loss = -math.log(p[y_idx])\n    grad = [p[i] - (1 if i == y_idx else 0) for i in range(len(z))]\n    return round(loss, 4), [round(g, 4) for g in grad]\n\nz = [2.0, 1.0, 0.1]\nprint(&#39;naive&#39;, [round(v, 4) for v in softmax_naive(z)])\nprint(&#39;stable&#39;, [round(v, 4) for v in softmax_stable(z)])\nloss, grad = ce_loss_grad(z, 0)\nprint(&#39;loss&#39;, loss, &#39;grad&#39;, grad)\nbig = [1000.0, 1.0, 0.1]\ntry:\n    softmax_naive(big)\n    print(&#39;naive_big&#39;, &#39;no-overflow&#39;)\nexcept OverflowError:\n    print(&#39;naive_big&#39;, &#39;OverflowError&#39;)\nprint(&#39;stable_big&#39;, [round(v, 4) for v in softmax_stable(big)])' :notes='["朴素 softmax 直接对每个 logits 取 exp，大值处会上溢", "稳定版先减最大值 m，使最大指数项恒为 1", "合并交叉熵后梯度化简为 p-y，打印验证链式法则结果", "z=1000 时朴素版抛 OverflowError，稳定版收敛到 [1,0,0]", "CrossEntropyLoss 吃 logits（内含 LogSoftmax），二分类用 BCEWithLogitsLoss", "固定 torch/numpy/random 种子，先在小样本过拟合验证管道；loss.backward + step 是标准循环", "Tensor 带 dtype/device/requires_grad；模型与输入必须同设备，float32 是默认", "autograd 用动态图记录 Function 节点，backward 逆拓扑按链式法则累加 .grad", "梯度是累加语义（支持多分支），所以每轮必须 optimizer.zero_grad()", "验证用 model.eval() + torch.no_grad()；训练前回到 model.train()", "CrossEntropyLoss 吃 logits（内含 LogSoftmax），二分类用 BCEWithLogitsLoss", "固定 torch/numpy/random 种子，先在小样本过拟合验证管道；loss.backward + step 是标准循环", "Tensor 带 dtype/device/requires_grad；模型与输入必须同设备，float32 是默认", "autograd 用动态图记录 Function 节点，backward 逆拓扑按链式法则累加 .grad", "梯度是累加语义（支持多分支），所以每轮必须 optimizer.zero_grad()", "验证用 model.eval() + torch.no_grad()；训练前回到 model.train()", "CrossEntropyLoss 吃 logits（内含 LogSoftmax），二分类用 BCEWithLogitsLoss", "固定 torch/numpy/random 种子，先在小样本过拟合验证管道；loss.backward + step 是标准循环", "Tensor 带 dtype/device/requires_grad；模型与输入必须同设备，float32 是默认", "autograd 用动态图记录 Function 节点，backward 逆拓扑按链式法则累加 .grad", "梯度是累加语义（支持多分支），所以每轮必须 optimizer.zero_grad()", "验证用 model.eval() + torch.no_grad()；训练前回到 model.train()", "CrossEntropyLoss 吃 logits（内含 LogSoftmax），二分类用 BCEWithLogitsLoss", "固定 torch/numpy/random 种子，先在小样本过拟合验证管道；loss.backward + step 是标准循环", "Tensor 带 dtype/device/requires_grad；模型与输入必须同设备，float32 是默认", "autograd 用动态图记录 Function 节点，backward 逆拓扑按链式法则累加 .grad", "梯度是累加语义（支持多分支），所以每轮必须 optimizer.zero_grad()"]' title='扩展示例逐行讲解' />

**数值稳定与梯度口径：三种写法对照**

| 写法 | z=1000 时 | 梯度表达式 | 代价 |
| --- | --- | --- | --- |
| 先 softmax 再取 log | exp(1000) 上溢，log(0) 得 -inf | 需额外一次 softmax 反向 | 数值失效 |
| softmax 与 NLL 分开算 | 同样在 exp 处上溢 | 两步链式，易重复 softmax | 已不推荐 |
| log-sum-exp 合并 CE | 减 max 后 exp 不超过 1，稳定 | dL/dz_i = p_i - y_i | 一次前向一次反传 |
| BCEWithLogitsLoss | log(1+exp(-\|x\|))+max(x,0) | dL/dz = sigmoid(z) - y | 二分类首选 |


### 验证阶段未关 no_grad 时显存随 epoch 增长

一个图像分类服务在第 12 个 epoch 后显存每轮涨约 80MB，第 20 轮 OOM。

排查发现验证函数写成 def `validate(model, loader)`: return `sum(loss_fn(model(x)`, y) for x, y in loader)，既没 with `torch.no_grad()` 也没 `model.eval()`：每个验证批次都建了完整计算图，中间特征被 autograd 历史引用挂住，峰值显存随批次数线性叠加；

BatchNorm 还用当前批统计量更新 running_mean，验证指标随批次顺序抖动。

补上 `model.eval()` 与 with `torch.no_grad()` 后显存回落到训练峰值的三分之一。

下面用纯标准库模拟「建图 / 不建图」两条路径下峰值存活的中间张量数。

```python
class Tensor:
    def __init__(self, tracked):
        self.tracked = tracked

def validate(n_batches, no_grad):
    live, peak = [], 0
    for b in range(n_batches):
        feats = [Tensor(not no_grad) for _ in range(3)]
        live.extend(feats)
        peak = max(peak, len(live))
        if no_grad:
            live = []
    return peak

for epoch in (1, 4, 8, 12):
    print('epoch', epoch, 'with_grad_peak', validate(epoch * 4, False), 'no_grad_peak', validate(epoch * 4, True))
```

<Quiz no='103-X' q='关于 CrossEntropyLoss 的输入与数值稳定，下面哪项准确？' :options='["应传原始 logits；内部用 log-sum-exp 合并 LogSoftmax 与 NLL，梯度化简为 p-y", "应先手动 softmax 再传概率，这样梯度更稳定", "z=1000 时朴素 exp 不会溢出，因为 float32 范围足够", "重复 softmax 只是多一次归一化，不影响概率校准"]' answer="0" explain='CrossEntropyLoss 期望 logits；log_softmax 内部先减 max 再 exp 避免上溢，合并后 dL/dz = p - y。手动 softmax 会在 exp(1000) 溢出，重复 softmax 会让概率再归一化、改变梯度与校准。' />


## 练习、自测与训练循环速记

<Exercise title='基础：用中心差分校验解析梯度' task='对 f(x)=x³-2x 在 x=1.5 处，分别计算解析导数 3x²-2 与中心差分，说明为什么 h 不能取太大或太小。' solution='def f(x): return x**3 - 2*x\ndef analytic(x): return 3*x**2 - 2\ndef numerical(x,h=1e-5): return (f(x+h)-f(x-h))/(2*h)\nx=1.5\nprint(&#39;analytic&#39;, round(analytic(x),4), &#39;numerical&#39;, round(numerical(x),4))' explain='中心差分截断误差 O(h²)：h 太大截断误差大，h 太小则浮点相减的舍入误差放大，通常取 1e-5 量级；两者吻合即说明 autograd 的链式法则是精确的。' />

<Exercise title='进阶：从计算图推出各叶子梯度' task='对 y = w*x + b（w=2、x=3、b=1），按链式法则写出 dy/dw、dy/dx、dy/db，并说明为什么实现里用 += 累加。' solution='w,x,b=2.0,3.0,1.0\ny=w*x+b\nprint(&#39;dy/dw&#39;, x, &#39;dy/dx&#39;, w, &#39;dy/db&#39;, 1)' explain='由链式法则 dy/dw=x=3、dy/dx=w=2、dy/db=1。用 += 是因为同一节点可能通过多条路径影响输出（多分支损失），覆盖会丢掉其它路径的梯度，这也是必须显式 zero_grad 的原因。' />

<Quiz no='103-1' q='训练循环里每个 batch 前必须调用 optimizer.zero_grad()，原因是？' :options='["PyTorch 的 .grad 是累加语义，不清零会把上一轮梯度混进本轮", "不清零会报显存错误", "不清零学习率会失效", "只是代码风格，无实际影响"]' answer="0" explain='梯度累加支持多损失分支共享参数，但默认不会自动清零；训练循环若不显式 zero_grad，上一轮梯度会叠加到本轮，更新方向失真。' />

<Quiz no='103-2' q='验证阶段正确写法是？' :options='["model.eval() 配合 with torch.no_grad()", "model.train() 配合 no_grad", "只调用 loss.backward()", "把 batch_size 调成 1"]' answer="0" explain='eval 关闭 dropout、让 BatchNorm 用 running 统计量；no_grad 不建计算图省显存。两者缺一，验证指标会抖动或显存悄悄涨满。' />

<Quiz no='103-3' q='关于 CrossEntropyLoss 的输入，下面哪项准确？' :options='["应传原始 logits，它内部已含 LogSoftmax", "应先对输出做 softmax 再传入", "必须传 one-hot 标签", "只能用于二分类"]' answer="0" explain='CrossEntropyLoss 内部合并了 LogSoftmax 与 NLLLoss，并用 log-sum-exp 保证数值稳定；先做一次 softmax 再传会重复计算且破坏稳定性。' />

<Predict no='103-P' q='前面 code 里 y = w*x + b 反向传播后，dy/dw 的值是多少？' :options='["3.0", "2.0", "7.0"]' answer='0' output='dy/dw 3.0 dy/dx 2.0 dy/db 1.0' explain='乘法的局部导数 dy/dw = x = 3.0，dy/dx = w = 2.0，加法的 dy/db = 1.0；code 的第三行梯度正是 3.0 2.0 1.0。' />

<FillBlank no='103-F' tpl='___ __init__(self, data, children=()):' :answers='["def"]' hint='回想本讲关于 张量与设备 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 张量、设备、计算图与 autograd 的落点。' />

<KnowledgeCard :points='["Tensor 带 dtype/device/requires_grad；模型与输入必须同设备，float32 是默认", "autograd 用动态图记录 Function 节点，backward 逆拓扑按链式法则累加 .grad", "梯度是累加语义（支持多分支），所以每轮必须 optimizer.zero_grad()", "验证用 model.eval() + torch.no_grad()；训练前回到 model.train()", "CrossEntropyLoss 吃 logits（内含 LogSoftmax），二分类用 BCEWithLogitsLoss", "固定 torch/numpy/random 种子，先在小样本过拟合验证管道；loss.backward + step 是标准循环"]' :pitfalls='["每轮忘 zero_grad，梯度被累加到上一轮", "验证阶段没关梯度也没 eval，指标抖动、显存涨满", "随机种子未固定，无法判断改动是否真的有效", "忘记 zero_grad、或验证阶段没关梯度，会出现梯度累积与显存悄悄涨满"]' summary='自动微分把反向传播变成普通的前向代码加一行 backward，真正需要自己设计的是数据管道、损失与评估口径' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| Tensor 带 dtype/device/requires_grad；模型与输入必须同设备，float32 是默认 | 建立直觉 |
| autograd 用动态图记录 Function 节点，backward 逆拓扑按链式法则累加 .grad | 跑通示例 |
| 梯度是累加语义（支持多分支），所以每轮必须 optimizer.zero_grad() | 深入边界 |
| 验证用 model.eval() + torch.no_grad()；训练前回到 model.train() | 工程落地 |
| CrossEntropyLoss 吃 logits（内含 LogSoftmax），二分类用 BCEWithLogitsLoss | 随堂检测 |
| 固定 torch/numpy/random 种子，先在小样本过拟合验证管道；loss.backward + step 是标准循环 | 复盘 |

1. Tensor 带 dtype/device/requires_grad；模型与输入必须同设备，float32 是默认

2. autograd 用动态图记录 Function 节点，backward 逆拓扑按链式法则累加 .grad

3. 梯度是累加语义（支持多分支），所以每轮必须 optimizer.zero_grad()

[下一讲：LLM 应用工程：Prompt、RAG、Agent 与成本](/data-ai/llm-engineering)
