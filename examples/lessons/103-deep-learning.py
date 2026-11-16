"""
第 103 讲 · 深度学习与 PyTorch：张量、自动微分与训练循环
与教程正文一一对应的示例代码

课程页面：/data-ai/deep-learning
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/103-deep-learning.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/103-deep-learning.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# y 7.0
# dy/dw 3.0 dy/dx 2.0 dy/db 1.0

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

# ======================== 2. 对照写法 ========================
# 预期输出：
# epoch 0 loss 0.3319 w 2.267 b 1.0
# epoch 1 loss 0.0053 w 2.018 b 0.893
# epoch 2 loss 0.0013 w 2.044 b 0.908

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

# ======================== 3. 原理验证 ========================
# 预期输出：
# x 0.0 analytic 3.0 numerical 3.0
# x 2.0 analytic 7.0 numerical 7.0
# x -3.0 analytic -3.0 numerical -3.0

def f(x): return x ** 2 + 3 * x + 1
def analytic(x): return 2 * x + 3
def numerical(x, h=1e-5): return (f(x + h) - f(x - h)) / (2 * h)
for x in (0.0, 2.0, -3.0):
    print('x', x, 'analytic', round(analytic(x), 4), 'numerical', round(numerical(x), 4))

# ======================== 4. 工程案例 ========================

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
