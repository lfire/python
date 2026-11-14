---
title: 深度学习项目：CNN、RNN、迁移学习与部署
description: 从数据管道与训练循环，到 CNN、RNN、预训练 ResNet 迁移、GAN、MNIST 与医学影像端到端流程，再到模型导出、早停与可复现性的项目落地清单。
---

# 深度学习项目：CNN、RNN、迁移学习与部署

第 103 讲已经用手写 autograd 与 toy 数据把训练循环跑通了，能盯住 `forward`、`backward`、`step` 的顺序，也能解释为什么要 `zero_grad()`，但没有用真实数据集，没有搭 CNN / RNN 网络结构，权重也始终留在内存里。真正做图像或序列项目时，会立刻撞上一串没被覆盖的问题：几万张样本怎么按批喂进去且不把验证集信息漏进缩放参数，卷积层凭什么比全连接省下几十倍参数，预训练模型换掉最后一层为什么就能识别新类别，训好的网络又怎么离开 notebook 到线上进程里被加载。这一篇按一条项目动线把这些缺口补上：先落数据管道与 `nn.Module` 的训练／验证循环，再讲 CNN 与 RNN 的结构动机，接着做预训练 ResNet 的冻结与微调，补一类 GAN 生成任务，然后走 MNIST 分类与医学影像两个端到端流程，最后处理导出、过拟合早停与可复现性。每个依赖 `torch` 的真实示例都配一段纯标准库的最小等价演示，没有 GPU、没装框架也能先把核心机制跑通。

真实框架示例统一依赖下面这条安装命令，CPU 版足够复现本文所有张量运算：

```bash
# 有 NVIDIA GPU 时可换成对应 CUDA 版本的安装命令
pip install torch torchvision
```

## 张量、Dataset 与 DataLoader：数据怎么按批喂进去

PyTorch 里一张灰度图不是二维列表，而是形状为 `1 x 28 x 28` 的三维张量，批处理后变成 `N x C x H x W` 的四维张量，其中 `N` 是批大小、`C` 是通道数、`H` 与 `W` 是高宽。`torch.Tensor` 带 `dtype`、`device`、`shape` 三个属性，默认是 `float32`；模型与输入必须落在同一设备，否则会报设备不一致的错误。`Dataset` 负责定义单条样本：实现 `__len__` 返回总数、`__getitem__` 按下标取回一条 `(x, y)`；`DataLoader` 负责把它们攒成批，`batch_size` 控每批条数，`shuffle=True` 每轮打乱顺序，`num_workers` 开子进程并行读盘，`collate_fn` 处理变长样本。

缩放要格外小心。均值和标准差必须只用训练集统计，再套到训练集与验证集上；若先对全量数据算好均值再划分，验证集的分布信息就渗进了训练用的缩放参数，属于典型的数据泄漏。下面这段纯标准库演示把「按批取样、固定种子洗牌、先划分再标准化」三件事一次说清，不需要装任何库。

```python
import random

def make_batches(items, batch_size, seed=0, shuffle=True):
    """纯标准库等价演示：DataLoader 的按批取样与可复现洗牌。"""
    idx = list(range(len(items)))
    rng = random.Random(seed)          # 独立随机源，不污染全局状态
    if shuffle:
        rng.shuffle(idx)
    for start in range(0, len(idx), batch_size):
        yield [items[i] for i in idx[start:start + batch_size]]

def split_and_normalize(rows, val_ratio=0.2, seed=0):
    """先划分，再只用训练集算均值与标准差，避免缩放参数泄漏。"""
    rng = random.Random(seed)
    order = list(range(len(rows)))
    rng.shuffle(order)
    cut = int(len(rows) * (1 - val_ratio))
    train_idx, val_idx = order[:cut], order[cut:]
    xs = [rows[i][0] for i in train_idx]
    mean = sum(xs) / len(xs)
    std = (sum((x - mean) ** 2 for x in xs) / len(xs)) ** 0.5 or 1.0
    def norm(i):
        return ((rows[i][0] - mean) / std, rows[i][1])
    return [norm(i) for i in train_idx], [norm(i) for i in val_idx]

rows = [(float(i), i % 3) for i in range(20)]
train, val = split_and_normalize(rows)
print("train / val size:", len(train), len(val))
print("same seed, same first batch:",
      next(make_batches(train, 4, seed=42)),
      next(make_batches(train, 4, seed=42)))
```

## `nn.Module` 与训练／验证循环：MNIST 分类实战

自定义网络继承 `nn.Module`，在 `__init__` 里登记层，在 `forward` 里写前向。`nn.Sequential` 把连续的层串起来，`Conv2d`、`MaxPool2d`、`Linear` 都在构造时自动初始化权重并注册进 `parameters()`，优化器才知道该更新谁。十分类用 `cross_entropy`：它吃的是原始 logits，内部合并了 log-softmax 与负对数似然，并用减去最大值再取指数的技巧保证数值稳定，所以千万别先手动 `softmax` 再传进去，那样会重复归一化还容易在极端值上溢出。优化器常用 `Adam`，配一个小的 `weight_decay` 做权重衰减。

训练循环每批固定五步：`optimizer.zero_grad()` 清零、前向算 logits、`loss.backward()` 反传、`optimizer.step()` 更新、累加指标。验证循环必须切 `model.eval()` 关掉 dropout 与批归一化的训练态，并用 `torch.no_grad()` 或 `set_grad_enabled(False)` 不建计算图，否则显存会随批次数悄悄涨满、指标还会抖动。下面是一份能直接跑的 MNIST 端到端代码，依赖开头的安装命令。

```python
# 依赖开头 bash 块安装的 torch / torchvision
import torch
import torch.nn.functional as F
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

class MnistNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.classifier = nn.Linear(32 * 7 * 7, 10)

    def forward(self, x):
        x = self.features(x)
        return self.classifier(x.flatten(1))

def run_epoch(model, loader, device, optimizer=None):
    training = optimizer is not None
    model.train(training)                       # 验证时切 eval
    correct = total = 0
    for x, y in loader:
        x, y = x.to(device), y.to(device)
        with torch.set_grad_enabled(training):  # 验证不建图
            logits = model(x)
            loss = F.cross_entropy(logits, y)
        if training:
            optimizer.zero_grad()               # 每批清零，防梯度累加
            loss.backward()
            optimizer.step()
        correct += (logits.argmax(1) == y).sum().item()
        total += y.size(0)
    return correct / total

def main():
    torch.manual_seed(0)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tfm = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.1307,), (0.3081,)),
    ])
    train_ds = datasets.MNIST("./data", train=True, download=True, transform=tfm)
    val_ds = datasets.MNIST("./data", train=False, download=True, transform=tfm)
    train_dl = DataLoader(train_ds, batch_size=64, shuffle=True, num_workers=2)
    val_dl = DataLoader(val_ds, batch_size=256)
    model = MnistNet().to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    for epoch in range(5):
        tr = run_epoch(model, train_dl, device, opt)
        va = run_epoch(model, val_dl, device)
        print(f"epoch {epoch} train {tr:.4f} val {va:.4f}")

if __name__ == "__main__":
    main()
```

没装框架时，用纯标准库把「前向、损失、梯度累加、参数更新、早停」跑一遍，能核对每个环节到底在算什么。下面这段里 `dw`、`db` 每轮从零累加，正是 `zero_grad()` 的等价动作；`patience` 连续不降就停，对应早停。

```python
def train_loop(points, lr=0.05, epochs=300, patience=12, min_delta=1e-4):
    """纯标准库等价演示：损失、SGD、梯度清零与早停。"""
    w, b = 0.0, 0.0
    best, best_state, stale = float("inf"), (w, b), 0
    for epoch in range(epochs):
        dw = db = 0.0           # 每轮显式从 0 累加，等价于 zero_grad()
        loss = 0.0
        for x, y in points:
            err = (w * x + b) - y
            loss += err ** 2
            dw += err * x
            db += err
        n = len(points)
        loss /= n
        w -= lr * dw / n       # 等价于 optimizer.step()
        b -= lr * db / n
        if loss < best - min_delta:   # 改善不足阈值就算停滞
            best, best_state, stale = loss, (w, b), 0
        else:
            stale += 1
            if stale >= patience:
                return epoch, best, best_state
    return epochs - 1, best, best_state

points = [(x, 2.0 * x + 1.0) for x in range(10)]
epoch, loss, (w, b) = train_loop(points)
print("stop at", epoch, "loss", round(loss, 5), "w", round(w, 2), "b", round(b, 2))
```

<Callout type='warn' title='验证阶段最容易漏的两行' text='验证循环前要调用 model.eval 切换到推理态，并用 torch.no_grad 或 set_grad_enabled 关闭计算图构建；两者缺一，dropout 与批归一化会按训练模式继续更新，指标抖动且显存逐批累积。' />

## 损失函数、优化器与任务选型

任务决定损失与最后一层的搭配，配错会直接让训练发散。回归用 `MSELoss`，输出层一个神经元不加激活；二分类用 `BCEWithLogitsLoss`，同样吃 logits 内建数值稳定；多分类用 `CrossEntropyLoss`，输出维度等于类别数。优化器方面，`SGD` 配动量稳但收敛慢，`Adam` 自适应学习率、默认参数就能起步，微调预训练模型时往往换成小学习率的 `SGD` 以免破坏已有特征。

| 任务 | 最后一层 | 损失函数 | 优化器起点 | 监控指标 |
| --- | --- | --- | --- | --- |
| 房价回归 | `Linear(d, 1)` | `MSELoss` | `Adam(lr=1e-3)` | MAE / RMSE |
| 垃圾邮件二分类 | `Linear(d, 1)` | `BCEWithLogitsLoss` | `Adam(lr=1e-3)` | AUC / F1 |
| MNIST 十分类 | `Linear(d, 10)` | `CrossEntropyLoss` | `Adam(lr=1e-3)` | 准确率 |
| ResNet 微调 | 替换后的分类头 | `CrossEntropyLoss` | `SGD(lr=1e-4, momentum=0.9)` | 验证准确率 |

## CNN：局部感受野、权值共享与池化

把 `28 x 28` 的图拉平成一维接全连接，第一层就要 `784 x 256` 约二十万个权重；而一个 `3 x 3` 卷积核只有九个权重，在整张图上滑动复用，这叫权值共享。每个输出像素只看输入的一小块，叫局部感受野，正好对应图像的局部相关性：边缘、纹理先被检出，深层再组合成形状。卷积输出的边长等于（输入边长加两倍填充减卷积核边长）除以步长再加一，通道数等于卷积核个数。池化不学参数，只在窗口里取最大值或平均值，作用是降采样、扩大后续层的感受野，并带来一点平移不变性。

下面用嵌套列表把单通道卷积与最大池化算一遍，输出尺寸和数值都能核对，不需要 `torch`。

```python
def conv2d(image, kernel, stride=1, pad=0):
    """单通道二维互相关：纯标准库等价演示卷积前向与输出尺寸。"""
    if pad:
        h, w = len(image), len(image[0])
        buf = [[0.0] * (w + 2 * pad) for _ in range(h + 2 * pad)]
        for r in range(h):
            for c in range(w):
                buf[r + pad][c + pad] = image[r][c]
        image = buf
    kh, kw = len(kernel), len(kernel[0])
    oh = (len(image) - kh) // stride + 1
    ow = (len(image[0]) - kw) // stride + 1
    out = []
    for i in range(0, oh * stride, stride):
        row = []
        for j in range(0, ow * stride, stride):
            row.append(sum(image[i + r][j + c] * kernel[r][c]
                           for r in range(kh) for c in range(kw)))
        out.append(row)
    return out

def maxpool(feature, size=2, stride=2):
    oh = (len(feature) - size) // stride + 1
    ow = (len(feature[0]) - size) // stride + 1
    return [[max(feature[i * stride + r][j * stride + c]
                 for r in range(size) for c in range(size))
             for j in range(ow)] for i in range(oh)]

image = [[1, 2, 3, 0], [4, 5, 6, 1], [7, 8, 9, 2], [0, 1, 2, 3]]
edge = [[1, 0, -1], [1, 0, -1], [1, 0, -1]]
fm = conv2d(image, edge, pad=1)
print("feature map:", len(fm), "x", len(fm[0]), "-> pooled:", maxpool(fm))
```

一个 MNIST 用的卷积网络，各层参数与形状可以这样核对：

| 层 | 卷积核 / 池化 | 输出形状 | 可训练参数量 |
| --- | --- | --- | --- |
| 输入 | 无 | `1 x 28 x 28` | 0 |
| `Conv2d(1,16,3)` | `3x3`，`padding=1` | `16 x 28 x 28` | 160 |
| `MaxPool2d(2)` | `2x2`，步长 2 | `16 x 14 x 14` | 0 |
| `Conv2d(16,32,3)` | `3x3`，`padding=1` | `32 x 14 x 14` | 4640 |
| `MaxPool2d(2)` | `2x2`，步长 2 | `32 x 7 x 7` | 0 |
| `Linear(1568,10)` | 全连接 | `10` | 15690 |

## RNN 与 LSTM：门控怎么留住长程序列信息

处理序列时，RNN 把上一时刻的隐状态乘一个权重矩阵再加当前输入，逐步向后传。问题出在反传：最早时刻收到的梯度里含有这个权重的连乘，序列一长，小于一的连乘迅速趋近零，梯度消失，模型记不住句首。LSTM 加了一条近似加法的细胞状态通道，用遗忘门、输入门、输出门控制写入与读出；当遗忘门接近一时，梯度沿细胞状态稳定回传，长程依赖因此保得住。`GRU` 是它的精简版，把门减到两个，参数更少、训练更快。

下面这段用标量观察同一现象：普通 RNN 八步后回到首步的梯度几乎为零，门控版仍有可观数值。

```python
def rnn_grad(seq, w=0.5):
    h = 0.0
    for x in seq:
        h = w * h + x          # 隐状态乘性更新
    return w ** (len(seq) - 1)  # 反传到首步是 w 的连乘

def gated_grad(seq, forget=0.9):
    cell = 0.0
    for x in seq:
        cell = forget * cell + x   # 近似加法的细胞状态
    return forget ** (len(seq) - 1)

seq = [1.0, 0, 0, 0, 0, 0, 0, 0]
print("vanilla rnn grad to step 1:", round(rnn_grad(seq), 6))
print("gated grad to step 1:", round(gated_grad(seq), 6))
```

## 预训练 ResNet：冻结骨干与微调

ImageNet 上训好的 `resnet18` 已经学会了边缘、纹理、部件等通用特征，做猫狗或病灶分类时不必从零训。做法是把最后的 `fc` 全连接层换成输出新类别数的层，然后分两阶段：先冻结卷积骨干，只训练新头，让随机初始化的头先对齐已有特征；再解冻靠近输出的若干层，用一个比头部小十倍左右的学习率整体微调。冻结的实现就是把这些参数的 `requires_grad` 设为 `False`，并记得传给优化器的只有 `requires_grad=True` 的参数，否则白算梯度。

```python
# 依赖开头 bash 块安装的 torch / torchvision
import torch
from torch import nn
from torchvision import models

def build(num_classes=2, fine_tune=False):
    model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
    for p in model.parameters():
        p.requires_grad = False                    # 先冻结全部骨干
    model.fc = nn.Linear(model.fc.in_features, num_classes)
    if fine_tune:
        for p in model.layer4.parameters():        # 只解冻最后一组残差块
            p.requires_grad = True
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.SGD(params, lr=1e-3 if not fine_tune else 1e-4,
                          momentum=0.9)
    return model, opt

head_only, opt_head = build(fine_tune=False)
tuned, opt_tuned = build(fine_tune=True)
print("trainable params (head only):",
      sum(p.numel() for p in head_only.parameters() if p.requires_grad))
print("trainable params (fine tune):",
      sum(p.numel() for p in tuned.parameters() if p.requires_grad))
```

冻结与微调的差别，用纯标准库也能看清：把骨干参数的学习率置零，它就不再变化；给一个很小的学习率，它才缓慢跟着调整。

```python
def freeze_demo(lr_backbone=0.0, steps=80):
    """冻结等价于把骨干学习率设为 0；微调是给一个很小的值。"""
    backbone, head, target = 0.2, 0.1, 1.0
    for _ in range(steps):
        pred = backbone * head
        grad = pred - target
        gb, gh = grad * head, grad * backbone
        head -= 0.1 * gh
        backbone -= lr_backbone * gb
    return round(backbone, 4), round(head, 4)

print("frozen backbone:", freeze_demo(0.0))
print("fine tuned backbone:", freeze_demo(0.01))
```

| 策略 | 可训练部分 | 适用数据量 | 学习率 | 主要风险 |
| --- | --- | --- | --- | --- |
| 只训头部 | 替换后的 `fc` | 几百张 | `1e-3` | 特征与新域差太远时欠拟合 |
| 顶层微调 | `layer4` 加头部 | 几千张 | 头部 `1e-3`、骨干 `1e-4` | 学习率过大破坏已有特征 |
| 全网微调 | 全部层 | 上万张 | 统一 `1e-4` | 小数据上过拟合、训练不稳 |
| 从零训练 | 全部层 | 十万张以上 | `1e-2` 起步 | 算力成本高、收敛慢 |

## GAN：生成器与判别器的对抗目标

GAN 不像分类那样最小化一个固定损失，而是让两个网络博弈：生成器把随机噪声映射成假样本，判别器判断输入是真样本还是伪造品，生成器的目标是让判别器把假样本判成真。二者交替更新，理想状态下生成器分布逐渐贴近真实分布，判别器准确率落到二分之一附近。风格生成、漫画脸、图像超分辨都沿用这个思路，只是把网络换成卷积、把目标换成带梯度惩罚或感知损失的变体。训练 GAN 出了名地不稳，常见模式崩塌指生成器只产出少数几种样本，需要靠小批量判别、谱归一化或改用扩散类模型来缓解。

下面这个标量玩具不是真 GAN，只用来演示「一个想骗、一个想识破」的交替更新动态：

```python
import math
import random

def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))

def gan_toy(target=0.7, steps=600, seed=0, lr=0.1):
    """纯标准库演示：生成器与判别器交替沿各自梯度更新的对抗动态。"""
    rng = random.Random(seed)
    g, w, b = 0.1, 0.0, 0.0
    for _ in range(steps):
        fake = g + rng.uniform(-0.05, 0.05)
        real = target + rng.uniform(-0.05, 0.05)
        dr, df = sigmoid(w * real + b), sigmoid(w * fake + b)
        w += lr * ((1 - dr) * real - df * fake)    # 判别器想把真假分开
        b += lr * ((1 - dr) - df)
        g += lr * w * df * (1 - df)                # 生成器想让假样本被判真
    return round(g, 3), round(sigmoid(w * g + b), 3)

print("fake center / judged-real prob:", gan_toy())
```

## 医学影像端到端：标注、CT 可视化、训练与推理

医学影像项目比 MNIST 多出三件工程活。第一是标注数据：CT 或 MRI 与报告、勾画掩膜要按病人编号对齐，划分训练／验证／测试时必须按病人分组而非按切片分组，否则同一病人的相邻切片会同时出现在两侧，指标虚高。第二是可视化预处理：CT 存的是 HU 值，范围从负一千到上千，直接喂网络没有意义，要按窗宽窗位压到零到二百五十五的灰度，例如软组织窗取中心四十、宽度四百。第三是训练与推理：类别往往极不平衡，需要加权采样或加权损失，输出还要给医生可解释的热图或概率，而不是一个硬标签。

| 阶段 | 输入 | 关键动作 | 产物 |
| --- | --- | --- | --- |
| 数据整理 | 原始 DICOM 与标注表 | 按病人编号去重、按病人分组划分 | 训练／验证／测试清单 |
| 标注对齐 | 切片与掩膜 | 重采样到同一间距、校验形状一致 | 成对的张量样本 |
| CT 可视化 | HU 体数据 | 窗宽窗位截断、归一化 | 灰度切片 |
| 训练 | 灰度切片与标签 | 加权损失、数据增强、早停 | 权重文件 |
| 推理 | 单例新扫描 | 同样窗宽、`eval` + `no_grad` | 概率与热力图 |

窗宽窗位这步用纯标准库就能验证：

```python
def ct_window(slice_hu, center=40, width=400):
    """把 CT 的 HU 值按窗宽窗位压到 0-255 灰度。"""
    low, high = center - width / 2, center + width / 2
    out = []
    for row in slice_hu:
        line = []
        for hu in row:
            if hu <= low:
                v = 0
            elif hu >= high:
                v = 255
            else:
                v = int((hu - low) / (high - low) * 255)
            line.append(v)
        out.append(line)
    return out

slice_hu = [[-1000, -80, 40, 120], [0, 35, 60, 300], [50, 55, 70, 1000]]
print("windowed gray:", ct_window(slice_hu))
```

## 模型导出与上线：TorchScript、ONNX 与 state_dict

`torch.save(model.state_dict(), path)` 只存权重，加载时要先重建同样的网络结构再 `load_state_dict`，适合自己项目内部续训。要脱离 Python 部署，得把模型结构也固化下来：`torch.jit.trace` 或 `torch.jit.script` 生成 TorchScript，得到一个可被 C++ 的 LibTorch 加载的 `.pt` 文件；`torch.onnx.export` 导出 ONNX 计算图，交给 ONNX Runtime、TensorRT 等推理引擎做跨框架加速。导出前务必 `model.eval()`，并用一个固定形状的输入张量当样例；导出后要用同一输入比对原模型与导出文件的输出，数值误差在容忍范围内才算成功。

```python
# 依赖开头 bash 块安装的 torch
import torch
from torch import nn

class Tiny(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Linear(8, 2))
    def forward(self, x):
        return self.net(x)

model = Tiny().eval()
dummy = torch.randn(1, 4)
torch.save(model.state_dict(), "tiny_weights.pth")
scripted = torch.jit.trace(model, dummy)
scripted.save("tiny_ts.pt")
torch.onnx.export(model, dummy, "tiny.onnx", input_names=["input"],
                  output_names=["logits"], opset_version=13)
with torch.no_grad():
    print("trace max diff:", (model(dummy) - scripted(dummy)).abs().max().item())
```

| 格式 | 存了什么 | 加载方 | 适用 |
| --- | --- | --- | --- |
| `state_dict` | 仅权重张量 | 同结构 Python 代码 | 续训、实验归档 |
| TorchScript `.pt` | 结构加权重 | LibTorch / C++ | 服务端脱离 Python |
| ONNX `.onnx` | 标准计算图 | ONNX Runtime / TensorRT | 跨框架、硬件加速 |

`state_dict` 那一路的核心机制只是「把参数按名字存下来、加载时按同名填回去」，用纯标准库把字典序列化成字符串就能先跑通，不产生任何文件：

```python
import json

def dump_state(state):
    """纯标准库等价演示：state_dict 只存参数，不存网络结构。"""
    return json.dumps(state)

def load_state(blob):
    return json.loads(blob)

weights = {"features.0.weight": [0.1, -0.2, 0.3], "classifier.bias": [0.01]}
blob = dump_state(weights)
restored = load_state(blob)
print("serialized keys:", sorted(restored))
print("roundtrip equal:", restored == weights)
```

## 过拟合、早停与可复现性

过拟合的信号很直白：训练准确率继续升，验证准确率掉头向下，两者差距越拉越大。应对按代价从低到高排：先在数据侧加归一化与增强，再在模型侧加 `Dropout` 与 `weight_decay`，最后用早停——每个 epoch 记验证损失，连续若干轮不刷新最好值就停止并回滚到最佳权重，前面纯标准库演示里的 `patience` 就是这套逻辑。

可复现性要同时管住几处随机源：`random.seed`、`numpy.random.seed`、`torch.manual_seed`，GPU 上还要 `torch.cuda.manual_seed_all`。追求严格确定性时设 `torch.use_deterministic_algorithms(True)` 并给 cuDNN 关掉 benchmark，代价是某些算子变慢或没有确定性实现。固定种子后先用一小撮样本过拟合到接近满分，是验证整条管道没接错的最快手段；管道通了再换全量数据。

| 现象 | 可能原因 | 修复动作 |
| --- | --- | --- |
| 训练升、验证降 | 过拟合 | 早停、增强、`Dropout`、`weight_decay` |
| 两次同代码指标差两点 | 种子未固定 | 固定全部随机源，关 cuDNN benchmark |
| 验证显存逐批涨 | 没关计算图 | `no_grad` + `eval`，别把 logits 留到列表里 |
| 小样本也训不动 | 管道接错 | 先在小样本过拟合验管道，再查缩放与标签对齐 |

## 常见坑 / 边界

1. **缩放参数泄漏**：先对全量算均值方差再划分，验证集分布渗进训练缩放。修复动作：按病人或样本先划分，只在训练集 `fit` 统计量，再统一套用，医学影像尤其要按病人分组。
2. **验证没切模式、没关梯度**：漏掉 `model.eval()` 与 `torch.no_grad()`，dropout 和批归一化继续更新、指标抖动且显存涨满。修复动作：验证循环前切 `eval`，用 `set_grad_enabled(False)` 包住前向，指标只取 `.item()` 标量别存张量。
3. **忘 `zero_grad()` 或显存溢出**：梯度跨批累加导致更新方向失真；批太大或验证留图导致 OOM。修复动作：每批开头 `optimizer.zero_grad()`，减小 `batch_size`，必要时用梯度累积或混合精度。
4. **迁移时解冻过头**：小数据上全网微调、学习率又偏大，把预训练特征冲掉反而更差。修复动作：先只训头部，再以头部十分之一的学习率解冻顶层，并核对传入优化器的确实只有 `requires_grad=True` 的参数。
5. **导出输入形状写死**：用批大小一的样例导出后，线上换批就报错或结果错位。修复动作：导出时声明动态轴，导出后用同一输入比对原模型与导出文件输出，误差超阈值不发布。

## 练习

::: details 练习 1 · 手算卷积与池化后的形状
输入形状是 `1 x 1 x 28 x 28`，依次经过 `Conv2d(1, 8, 3, padding=1)`、`MaxPool2d(2)`、`Conv2d(8, 16, 3, padding=1)`、`MaxPool2d(2)`，写出每层输出形状与最后全连接层的输入维度。用纯标准库验证，不装 `torch`。

```python
# 参考解
def conv_out(h, k=3, pad=1, stride=1):
    return (h + 2 * pad - k) // stride + 1
def pool_out(h, size=2, stride=2):
    return (h - size) // stride + 1

h = 28
h = conv_out(h)       # 28
h = pool_out(h)       # 14
h = conv_out(h)       # 14
h = pool_out(h)       # 7
print("shapes: 8x28x28 -> 8x14x14 -> 16x14x14 -> 16x7x7")
print("flatten dim to Linear:", 16 * h * h)
```
:::

::: details 练习 2 · 给训练循环补上早停与最佳权重回滚
基于前面的纯标准库训练循环，要求连续五轮验证损失不下降就停止，并返回最好那轮的参数。用一段可运行代码实现。

```python
# 参考解
def train_with_stop(train, valid, lr=0.05, epochs=300, patience=5, min_delta=1e-4):
    def mse(w, b, data):
        return sum(((w * x + b) - y) ** 2 for x, y in data) / len(data)
    w, b = 0.0, 0.0
    best, best_state, stale = float("inf"), (w, b), 0
    for epoch in range(epochs):
        dw = sum(((w * x + b) - y) * x for x, y in train) / len(train)
        db = sum(((w * x + b) - y) for x, y in train) / len(train)
        w -= lr * dw
        b -= lr * db
        v = mse(w, b, valid)
        if v < best - min_delta:   # 改善不足最小阈值即计一次停滞
            best, best_state, stale = v, (w, b), 0
        else:
            stale += 1
            if stale >= patience:
                return epoch, round(best, 6), tuple(round(t, 3) for t in best_state)
    return epochs - 1, round(best, 6), tuple(round(t, 3) for t in best_state)

train = [(x, 2.0 * x + 1.0) for x in range(8)]
valid = [(x + 0.5, 2.0 * (x + 0.5) + 1.0) for x in range(4)]
print("stop epoch / best val / state:", train_with_stop(train, valid))
```
:::

回到 [专题补遗](/topics/) · [课程总目录](/guide/curriculum)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能跑通本专题按正文顺序整理的标准库示例；需要第三方库的片段会自动跳过并打印安装提示，不装任何库也能看到核心结果。" />

**本专题示例代码** · 仓内路径 `examples/topics/dl-projects.py`

```bash
python3 examples/topics/dl-projects.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/topics/dl-projects.py) · [全部示例代码索引](/examples/)
