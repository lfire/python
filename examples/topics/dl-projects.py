"""深度学习项目：CNN、RNN、迁移学习与部署 —— 专题补遗示例

课程页：/topics/dl-projects
GitHub：https://github.com/lfire/python/blob/main/examples/topics/dl-projects.py

依赖安装（可选，仅真实框架片段需要；纯标准库等价演示无需安装）：
    pip install torch torchvision

运行：
    python3 examples/topics/dl-projects.py

说明：每个依赖 torch / torchvision 的真实框架片段都用 try/except ImportError 包成可选段，
未安装时打印跳过提示；纯标准库等价演示（洗牌分批、SGD 早停、conv2d/maxpool、门控梯度、
冻结与微调、序列化等）在纯净环境里直接跑出结果。可选段即使装了依赖，也只用本地随机
张量做一次前向，绝不下载数据集或模型权重、不训练大模型、不访问外网、不写仓库文件。
"""

# == 段 1 == 对应节：张量、Dataset 与 DataLoader：数据怎么按批喂进去
# 演示（纯标准库）：按批取样、固定种子可复现洗牌、先划分再只用训练集标准化以防数据泄漏。
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


# == 段 2 == 对应节：nn.Module 与训练／验证循环：MNIST 分类实战
# 演示（可选，需 torch/torchvision）：nn.Module 搭卷积网络、run_epoch 训练与验证两套分支。
# 安全说明：源文 main 用 datasets.MNIST(download=True) 下载数据并训练 5 轮；本可选段改用
# 本地随机张量做一次前向与一次验证态 run_epoch（不更新权重），绝不下载、不训练、不联网。
try:
    import torch
    import torch.nn.functional as F
    from torch import nn
    from torch.utils.data import DataLoader, TensorDataset
    from torchvision import datasets, transforms
except ImportError:
    print("跳过：需要 pip install torch torchvision")
else:
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

    torch.manual_seed(0)
    model = MnistNet()
    x = torch.randn(2, 1, 28, 28)
    y = torch.tensor([1, 7])
    logits = model(x)
    loss = F.cross_entropy(logits, y)
    print("MNIST 前向 logits 形状:", tuple(logits.shape), "loss:", round(loss.item(), 4))
    ds = TensorDataset(torch.randn(8, 1, 28, 28), torch.randint(0, 10, (8,)))
    acc = run_epoch(model, DataLoader(ds, batch_size=4), torch.device("cpu"))
    print("run_epoch 验证态准确率(本地随机数据):", round(acc, 3))


# == 段 3 == 对应节：nn.Module 与训练／验证循环：MNIST 分类实战
# 演示（纯标准库）：损失、SGD、每轮从零累加梯度（等价 zero_grad）、patience 早停。
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


# == 段 4 == 对应节：CNN：局部感受野、权值共享与池化
# 演示（纯标准库）：单通道二维互相关与最大池化前向，输出尺寸可核对。
# 卷积输出边长 = (输入边长 + 2*pad - 卷积核边长) / stride + 1，通道数 = 卷积核个数。
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


# == 段 5 == 对应节：RNN 与 LSTM：门控怎么留住长程序列信息
# 演示（纯标准库）：普通 RNN 反传到首步是 w 的连乘（梯度消失），门控细胞状态近似加法可保住梯度。
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


# == 段 6 == 对应节：预训练 ResNet：冻结骨干与微调
# 演示（可选，需 torch/torchvision）：冻结全部骨干、替换 fc 分类头、只解冻 layer4、只把
# requires_grad=True 的参数交给优化器。
# 安全说明：源文 weights=ResNet18_Weights.DEFAULT 会联网下载 ImageNet 权重，这里改为
# weights=None 不加载权重，仅演示冻结与参数筛选机制，知识点不变。
try:
    import torch
    from torch import nn
    from torchvision import models
except ImportError:
    print("跳过：需要 pip install torch torchvision")
else:
    def build(num_classes=2, fine_tune=False):
        model = models.resnet18(weights=None)
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


# == 段 7 == 对应节：预训练 ResNet：冻结骨干与微调
# 演示（纯标准库）：把骨干学习率置零参数便不再变化，给一个很小的值才缓慢调整。
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


# == 段 8 == 对应节：GAN：生成器与判别器的对抗目标
# 演示（纯标准库）：标量玩具，一个想骗、一个想识破的交替梯度更新动态，不是真 GAN。
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


# == 段 9 == 对应节：医学影像端到端：标注、CT 可视化、训练与推理
# 演示（纯标准库）：按窗宽窗位把 CT 的 HU 值截断并归一化到 0-255 灰度。
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


# == 段 10 == 对应节：模型导出与上线：TorchScript、ONNX 与 state_dict
# 演示（可选，需 torch）：state_dict 存权重、jit.trace 生成 TorchScript、onnx.export 导出，
# 并用同一输入比对原模型与导出文件输出。
# 安全说明：源文把 .pth / .pt / .onnx 直接写到仓库，这里改写进 tempfile 临时目录；
# onnx.export 若缺可选依赖 onnx 会单独兜底跳过，不影响其余结果。
try:
    import torch
    from torch import nn
except ImportError:
    print("跳过：需要 pip install torch")
else:
    import os
    import tempfile

    class Tiny(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(nn.Linear(4, 8), nn.ReLU(), nn.Linear(8, 2))
        def forward(self, x):
            return self.net(x)

    model = Tiny().eval()
    dummy = torch.randn(1, 4)
    with tempfile.TemporaryDirectory() as td:
        torch.save(model.state_dict(), os.path.join(td, "tiny_weights.pth"))
        scripted = torch.jit.trace(model, dummy)
        scripted.save(os.path.join(td, "tiny_ts.pt"))
        with torch.no_grad():
            diff = (model(dummy) - scripted(dummy)).abs().max().item()
        print("state_dict / TorchScript 写入临时目录，trace max diff:", round(diff, 6))
        try:
            opath = os.path.join(td, "tiny.onnx")
            torch.onnx.export(model, dummy, opath, input_names=["input"],
                              output_names=["logits"], opset_version=13)
            print("ONNX 写入临时目录，字节数:", os.path.getsize(opath))
        except Exception as exc:
            print("跳过 ONNX 导出(需可选依赖 onnx):", type(exc).__name__)


# == 段 11 == 对应节：模型导出与上线：TorchScript、ONNX 与 state_dict
# 演示（纯标准库）：state_dict 只存参数、按名字序列化与回填，不产生任何文件。
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


# == 段 12 == 对应节：练习 1 · 手算卷积与池化后的形状
# 演示（纯标准库）：按 conv_out / pool_out 逐层推算输出边长，得出全连接层输入维度。
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


# == 段 13 == 对应节：练习 2 · 给训练循环补上早停与最佳权重回滚
# 演示（纯标准库）：连续五轮验证损失不下降就停止，并返回最好那轮的参数。
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
