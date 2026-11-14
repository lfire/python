---
title: 第 093 讲 · NumPy 向量化、广播与内存布局
description: 写出比纯 Python 快一个量级的数值代码
---

<StageHeader stage='L9 · 数据与 AI' level='★★★☆☆' time='40 分钟' goal='写出比纯 Python 快一个量级的数值代码' prereq='第 092 讲 · 阶段综合：生产级短链服务' />

# 第 093 讲 · NumPy 向量化、广播与内存布局

上一阶段的短链服务上线后，埋点记下每天的点击与耗时。你想问的变成：哪天访问最多、平均响应多久。拿 Python 列表配 for 循环逐条累加，几十万行就开始等结果。本讲是数据与 AI 阶段的起点，先不谈模型，只把数字摆成适合整批运算的样子。

从 ndarray 讲起，看清连续内存带来的速度；再看 shape、stride 如何让切片零成本，然后讲广播规则与向量化代替循环，最后用副本与视图收尾。需要函数、列表、循环和切片。学完能用一两行算完一列日志的统计，也说得出它为何比 Python 循环快一个量级，为后面清洗与建模打底。


## 一批像素加 20，循环为什么比向量化慢两个量级

图像服务里有个批量调亮度的任务：对 1000 乘 1000 的像素矩阵逐元素加 20，用两层 Python for 循环写了 8 秒还没跑完，换成一行向量化表达式 0.02 秒结束。团队照着改快了，却踩到第二个坑：有人用 `sub=a[a>0]` 取出正像素后对 sub 赋零，原矩阵 a 一个都没变；

另有人写 `b=a[:,0]` 之后 `b+=1`，结果整列之外的数据也被悄悄改了。朴素解法有两层想当然：一是『循环最直观、逐个元素处理最稳』，却忽略了每个元素在 CPython 里都是带引用计数的 PyObject、每次加法都走一遍字节码分派；

二是『切片当然会复制一份数据』，而 ndarray 的基本切片返回的是共享同一块内存的视图。要解释为什么快、什么时候改得动原数组，必须落到 dtype、连续内存、stride 寻址与广播规则这四件事上，而不是记住『NumPy 快』这个标签。

<Callout type="warn" title='先看一个真实会出错的写法' text='布尔索引取出后赋值，原数组纹丝不动：sub = a[a &gt; 0]; sub[:] = 0 里的 sub 是布尔索引产生的副本，改动落在副本上' />


## ndarray、dtype 与连续内存：裸值而非 PyObject

ndarray 是一块固定元素类型、地址连续的内存，外加 shape、strides、dtype 三个元数据；数据区里存的是裸值，不是 PyObject。

dtype 决定每个元素的字节数 itemsize：`np.int64`、`np.float64` 都是 8 字节，`np.float32`、`np.int32` 是 4 字节，`np.uint8` 与 bool 是 1 字节，`np.int16` 是 2 字节。

因为整块内存元素等长且类型已知，C 层的循环可以一条指令接着一条指令扫过去，不需要像 Python list 那样先解引用指针、再判断对象类型、再增减引用计数。

对比之下，Python 的 list 存的是指向各对象的指针数组，每个 float 是约 24 字节的独立 PyObject 加一个 8 字节指针，同样一百万个数，内存与寻址成本都高一个量级。`np.empty` 只分配不初始化，`np.zeros` 填零，`np.arange` 按步长生成；

`astype` 会分配一块新数组做类型转换，绝不原地改写 dtype。混合类型运算会按类型提升规则向上转型，例如 int64 数组与 float64 标量相加得到 float64 数组。

所谓 ufunc（`np.add`、`np.exp`、`np.sqrt`、`np.multiply`）是在 C 里对整个 buffer 跑的循环，一次 Python 层调用就完成整批计算，`np.sum`、`np.mean` 这类归约也是把累加放到 C 层，Python 只付一次调用开销——这正是『写出 Python for 循环就丢掉优势』的根本原因。

```python
def broadcast_shape(a, b):
    out = []
    i, j = len(a) - 1, len(b) - 1
    while i >= 0 or j >= 0:
        da = a[i] if i >= 0 else 1
        db = b[j] if j >= 0 else 1
        if da == db or da == 1 or db == 1:
            out.append(max(da, db))
        else:
            return None
        i -= 1; j -= 1
    return tuple(reversed(out))

pairs = [((3, 1), (1, 4)), ((2, 3), (3,)), ((2, 3), (2,)), ((5, 4), (3, 4))]
for a, b in pairs:
    print(a, '+', b, '->', broadcast_shape(a, b))
```

<OutputBox title='主示例运行结果' output='(3, 1) + (1, 4) -&gt; (3, 4)\n(2, 3) + (3,) -&gt; (2, 3)\n(2, 3) + (2,) -&gt; None\n(5, 4) + (3, 4) -&gt; None' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def broadcast_shape(a, b):\n    out = []\n    i, j = len(a) - 1, len(b) - 1\n    while i &gt;= 0 or j &gt;= 0:\n        da = a[i] if i &gt;= 0 else 1\n        db = b[j] if j &gt;= 0 else 1\n        if da == db or da == 1 or db == 1:\n            out.append(max(da, db))\n        else:\n            return None\n        i -= 1; j -= 1\n    return tuple(reversed(out))\n\npairs = [((3, 1), (1, 4)), ((2, 3), (3,)), ((2, 3), (2,)), ((5, 4), (3, 4))]\nfor a, b in pairs:\n    print(a, &#39;+&#39;, b, &#39;-&gt;&#39;, broadcast_shape(a, b))' :notes='["定义函数模拟 NumPy 的广播形状推导，输入是两个 shape 元组", "out 按从右到左的顺序收集每一维的结果，最后再反转", "i、j 分别指向两个 shape 当前待比较的维度下标", "只要还有任一数组没比完就继续，缺失维度用 1 补齐", "a 该维越界就视为 1，对应短数组在左侧被补 1", "b 同理，缺失维度视为 1", "兼容条件：相等、或 a 为 1、或 b 为 1，三者满足其一即可", "结果维度取两者较大值，这就是广播的目标形状", "有一维既不相等又都不为 1，判定不兼容", "返回 None 代表真实 NumPy 里会抛的 ValueError", "两个下标同时左移一位，进入下一维比较", "out 是从右往左攒的，反转后才是正常的维度顺序", "空行，只用于分隔逻辑块，不影响执行结果。", "四组测试覆盖：双向扩展、尾部补齐、维度冲突、首维冲突", "逐组打印，把抽象规则变成可核对的结果", "调用推导函数并输出目标形状或不兼容标记"]' title='第 093 讲 · NumPy 向量化、广播与内存布局' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## shape、stride 与视图：切片几乎不搬数据

strides 记录『某维度索引加 1 时，指针要跳过多少字节』。一个 float64 的 (3, 4) C 连续数组 strides 是 (32, 8)：跨一行跳 4 乘 8 等于 32 字节，跨一列跳 8 字节；元素 (i, j) 的地址就是 base 加 i 乘 32 再加 j 乘 8。

`reshape` 在多数情况下只改写 shape 与 strides、完全不搬数据，因此是 `O(1)` 的视图；`a[1:,::2]` 这类基本切片通过改动起始 offset 与步长返回视图，步长甚至可以为负；`a.T` 只是把 strides 顺序交换，于是原本 C 连续的数组变成 F 序视图。

判断一个数组是否拥有数据看 `a.flags.owndata`，看它是否指向别的数据块看 `a.base`，想确认两个数组是否共享内存用 `np.shares_memory(a,b)`。

关键分界在这里：基本切片（整数、切片、newaxis）返回视图，改视图会写回原数组；而布尔索引 `a[a>0]` 与花式索引 `a[[1,3,5]]` 返回的是副本，对新数组赋值不会影响原数组。

`a[a>0]=0` 能生效，是因为这是一条赋值语法，解释器走 `__setitem__` 并用掩码原地写回，而不是『先取出副本再赋值』。需要独立数据就显式用 `.copy()`，需要强制按另一种视图解释就用 `.view()`。

C 序与 F 序还会影响遍历时的缓存命中率，`np.ravel(order='C'/'F')` 与 `np.ascontiguousarray` 就是用来控制这一点的。

```python
import sys, array
lst = [float(i) for i in range(6)]
arr = array.array('d', lst)
print('list container', sys.getsizeof(lst), 'one float', sys.getsizeof(lst[0]))
print('array container', sys.getsizeof(arr), 'itemsize', arr.itemsize)
print('list per element', (sys.getsizeof(lst) + 6 * sys.getsizeof(lst[0])) // 6)
```

<OutputBox title='原理验证' output='list container 120 one float 24\narray container 128 itemsize 8\nlist per element 44' />


### 视图与副本在哪一步分道扬镳

**广播形状对照（右对齐逐维比较）**

| 形状 A | 形状 B | 结果 / 现象 | 原因 |
| --- | --- | --- | --- |
| (3, 1) | (1, 4) | (3, 4) | 两维各为 1，被扩展到对方大小 |
| (2, 3) | (3,) | (2, 3) | B 左侧补 1，尾部 3 相等 |
| (2, 3) | (2,) | ValueError | 尾部 3 与 2 不相等且都不为 1 |
| (5, 4) | (3, 4) | ValueError | 首维 5 与 3 冲突 |
| (3,) | (3, 1) | 需增维配合 | 直接算会因 3 与 1 之外的维度错位 |

<CodeTabs :tabs='[{"label": "主示例", "code": "def broadcast_shape(a, b):\n    out = []\n    i, j = len(a) - 1, len(b) - 1\n    while i &gt;= 0 or j &gt;= 0:\n        da = a[i] if i &gt;= 0 else 1\n        db = b[j] if j &gt;= 0 else 1\n        if da == db or da == 1 or db == 1:\n            out.append(max(da, db))\n        else:\n            return None\n        i -= 1; j -= 1\n    return tuple(reversed(out))\n\npairs = [((3, 1), (1, 4)), ((2, 3), (3,)), ((2, 3), (2,)), ((5, 4), (3, 4))]\nfor a, b in pairs:\n    print(a, &#39;+&#39;, b, &#39;-&gt;&#39;, broadcast_shape(a, b))", "note": "ndarray、dtype 与连续内存：快在哪里"}, {"label": "对照 / 进阶", "code": "class View:\n    def __init__(self, data, shape, strides, offset=0):\n        self.data, self.shape, self.strides, self.offset = data, shape, strides, offset\n    def get(self, idx):\n        addr = self.offset + sum(i * s for i, s in zip(idx, self.strides))\n        return self.data[addr]\n\nbase = list(range(12))\nrow = View(base, (4,), (1,), offset=4)\nprint(&#39;row&#39;, [row.get((j,)) for j in range(4)])\nbase[5] = 99\nprint(&#39;after&#39;, [row.get((j,)) for j in range(4)])", "note": "shape、stride 与视图：为什么切片几乎零成本"}]' title='两种写法切换看' />


## 广播规则：右对齐逐维比较

广播让形状不同的数组逐元素运算，规则是：先把两个 shape 右对齐，从最右边的维度逐个比较，两个维度相等、或其中一个为 1、或某数组该维度缺失（视为 1）就兼容，结果取两者中较大的值；

任何一维既不相等又都不为 1，就抛 `ValueError: oper…`。

```python
ValueError: operands could not be broadcast together with shapes
```

因此 (3, 1) 加 (1, 4) 得 (3, 4)，(2, 3) 加 (3,) 得 (2, 3)，而 (2, 3) 加 (2,) 会因 3 与 2 不兼容直接报错。广播几乎零内存成本：实现上把被扩展那一维的 stride 置为 0，读取时反复指向同一个值，并没有真的复制出一份大数组。

想手动控制就用 `a[:,np.newaxis]` 或 `a.reshape` 增维，让 (3,) 变成 (3, 1)。

向量化的判据是『用一套形状表达批量运算，把循环留在 C 层』，写完再用 timeit 验证收益，别凭感觉。

还要看清边界：`a*b+c` 会先产生一个临时数组再相加，超大数组时应写成 `np.multiply(a,b,out=tmp)` 再 `np.add(tmp,c,out=tmp)`，或用 `+=` 之类就地运算省下中间内存；

聚合要指定 axis 并用 `keepdims=True` 保住维度以便后续广播。向量化省的是解释器开销，不改变算法本身的算术次数，遇到需要顺序依赖的递推仍得换思路。

**常见 dtype 与每元素字节数（itemsize）**

| dtype | 含义 | itemsize(字节) | 典型风险 |
| --- | --- | --- | --- |
| np.int64 | 64 位有符号整数 | 8 | 与 uint64 混用会提升到 float64 |
| np.float64 | 双精度浮点 | 8 | 默认浮点类型，累加有小误差 |
| np.float32 | 单精度浮点 | 4 | 深度学习省显存但精度较低 |
| np.uint8 | 无符号 8 位整数 | 1 | 加法超过 255 会回绕，不是报错 |
| bool | 布尔 | 1 | 常被用作掩码，本身只占 1 字节 |

<ConceptDiagram type='hub4' title='第 093 讲 · ndarray、dtype 与连续内存：快在哪里' labels='ndarray、dtype 与连续内存：快在…|shape、stride 与视图：为什么切片…|广播规则与向量化的边界|ufunc 与聚合' caption='写出比纯 Python 快一个量级的数值代码' />

这张图把本讲的核心机制放在中心，四周是它同时影响的可读性、性能与正确性，适合用来检查取舍有没有漏项。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 布尔索引取出后赋值，原数组为何纹丝不动

```python
class View:
    def __init__(self, data, shape, strides, offset=0):
        self.data, self.shape, self.strides, self.offset = data, shape, strides, offset
    def get(self, idx):
        addr = self.offset + sum(i * s for i, s in zip(idx, self.strides))
        return self.data[addr]

base = list(range(12))
row = View(base, (4,), (1,), offset=4)
print('row', [row.get((j,)) for j in range(4)])
base[5] = 99
print('after', [row.get((j,)) for j in range(4)])
```

<OutputBox title='对照写法：先自己猜，再点开' output='row [4, 5, 6, 7]\nafter [4, 99, 6, 7]' guess="true" />

<Callout type="warn" title='本讲最容易踩的坑' text='布尔索引取出后赋值，原数组纹丝不动：sub = a[a &gt; 0]; sub[:] = 0 里的 sub 是布尔索引产生的副本，改动落在副本上' />


## ufunc 为什么只在 Python 层付一次调用

CPython 的 PyObject 头里有引用计数与类型指针，list 的每个元素都是独立分配的堆对象，指针数组只存地址，运算时虚拟机要逐条执行 `BINARY_OP`、动态分派类型并增减计数。

ndarray 反其道而行：PyArrayObject 只持有一个指向连续裸内存的 data 指针、ndim、dimensions、strides 和一个 dtype 描述符，数据区不是 PyObject，因此不受引用计数与 GIL 内层循环的拖累，C 层可以用紧凑循环甚至 `SIMD` 一次处理一段。

元素 (i0, i1, …) 的地址由 offset 加各维索引乘对应 stride 之和算出，`reshape` 与切片只是改写这几个元数据而不搬字节，所以是 `O(1)`。广播的实现更巧：把被扩展维度的 stride 设为 0，读取时指针原地不动，制造『无限复制』的假象却零拷贝。

ufunc 内层循环只认固定 dtype，把类型判断提前到分发阶段一次完成。理解这套『元数据加裸内存加 stride』模型，就能推出为什么 dtype 固定、为什么视图廉价、为什么布尔索引必须复制、以及为什么 Python 层 for 循环会毁掉全部收益。

<Term word='ndarray 与 dtype' text='ndarray 是一块固定元素类型、地址连续的内存，外加 shape、strides、dtype 三个元数据；数据区里存的是裸值，不是 PyObject。dtype 决定每个元素的字节数 itemsize：`np.int64`、`np.float64` 都是 8 字节，`np.float32`、`np.int32` 是…' />

<Term word='shape / stride 与视图' text='strides 记录『某维度索引加 1 时，指针要跳过多少字节』。一个 float64 的 (3, 4) C 连续数组 strides 是 (32, 8)：跨一行跳 4 乘 8 等于 32 字节，跨一列跳 8 字节；元素 (i, j) 的地址就是 base 加 i 乘 32 再加 j 乘 8。`reshape` 在多数…' />


### dtype 提升与 uint8 溢出回绕

**视图与副本操作对照**

| 操作 | 返回类型 | 是否共享内存 | 改它是否写回原数组 |
| --- | --- | --- | --- |
| a[1:3] | 视图 | 是 | 会 |
| a[:, 0] | 视图 | 是 | 会 |
| a.T / a.reshape(...) | 视图(通常) | 是 | 会 |
| a[a > 0] | 副本 | 否 | 不会 |
| a[[0, 2]] | 副本 | 否 | 不会 |
| a.copy() | 副本 | 否 | 不会 |

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 布尔索引取出后赋值，原数组纹丝不动 | sub = a[a > 0]; sub[:] = 0 里的 sub 是布尔索引产生的副本，改动落在副本上 | 用赋值语法 a[a > 0] = 0 走 __setitem__ 原地写回，或先算 mask 再用 np.copyto / mask 定位 |
| uint8 像素加 20 后数值反而变小 | 同 dtype 运算不会自动提升类型，200 加 100 溢出后按 256 取模回绕成 44 | 先 a.astype(np.int16) 或 astype(np.float32) 再运算，或用 np.add 指定 dtype |
| 本想拿一份独立数据，改 b 却把 a 也改了 | a[:, 0]、a[1:] 等基本切片返回共享内存的视图，b += 1 是原地写 | 需要独立副本就显式 a[:, 0].copy()；用 np.shares_memory(a, b) 提前确认是否共享 |


## 批量像素变换：把循环留在 C 层的等价结构

一个批处理服务要把每批 24 万像素做『减均值、乘增益、加偏置、裁剪到 0 到 255』四步。用 Python 逐元素 for 循环，解释器要为每步做类型分派与引用计数，四步叠起来是接近百万次字节码；换成 NumPy 就是四次 ufunc，循环全在 C 层。

下面用标准库写一份等价的骨架：把变换表达成对整批数据的逐元素映射，用列表推导模拟『一次调用处理一批』，并统计每步产出的元素数与裁剪命中数，让管道的正确性与规模都能核对。

真实工程把 `transform` 换成 `np.clip(gain*(pixels-mean)+bias,0,255)` 即可，注意用 `out=` 复用缓冲区避免大中间数组，并用 `astype` 先把 uint8 提升防止回绕。

```python
def transform(batch, mean, gain, bias):
    scaled = [gain * (x - mean) + bias for x in batch]
    clipped = [0 if v < 0 else 255 if v > 255 else v for v in scaled]
    return clipped

def summarize(batch, mean=100.0, gain=1.2, bias=10.0):
    out = transform(batch, mean, gain, bias)
    low = sum(1 for v in out if v == 0)
    high = sum(1 for v in out if v == 255)
    return {'count': len(out), 'low_clip': low, 'high_clip': high,
            'first': round(out[0], 1), 'mean': round(sum(out) / len(out), 1)}

pixels = [float((i * 7) % 256) for i in range(600)]
print(summarize(pixels))
print('same length', len(transform(pixels, 100, 1.2, 10)) == len(pixels))
```

<Callout type="idea" title='落地提示' text='先确认 dtype 与内存布局（C / F order），用 broadcasting 表达批量运算，再用 timeit 验证收益' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：布尔索引取出后赋值，原数组纹丝不动", "body": "sub = a[a &gt; 0]; sub[:] = 0 里的 sub 是布尔索引产生的副本，改动落在副本上", "tip": "用赋值语法 a[a &gt; 0] = 0 走 __setitem__ 原地写回，或先算 mask 再用 np.copyto / mask 定位"}, {"title": "第 2 步：uint8 像素加 20 后数值反而变小", "body": "同 dtype 运算不会自动提升类型，200 加 100 溢出后按 256 取模回绕成 44", "tip": "先 a.astype(np.int16) 或 astype(np.float32) 再运算，或用 np.add 指定 dtype"}, {"title": "第 3 步：本想拿一份独立数据，改 b 却把 a 也改了", "body": "a[:, 0]、a[1:] 等基本切片返回共享内存的视图，b += 1 是原地写", "tip": "需要独立副本就显式 a[:, 0].copy()；用 np.shares_memory(a, b) 提前确认是否共享"}]' />

<CheckList id='P093b' title='上线前自检' :items='["能复现并解释「布尔索引取出后赋值，原数组纹丝不动」", "能复现并解释「uint8 像素加 20 后数值反而变小」", "能复现并解释「本想拿一份独立数据，改 b 却把 a 也改了」", "能用一条命令验证 ndarray 与 dtype", "关键路径有自动化测试与失败分支"]' />


## PyArrayObject 的字段布局与 ufunc 内层循环分发

ndarray 在 C 层是 PyArrayObject（定义在 `numpy/_core/include/numpy/ndarraytypes.h`）：字段有 char 指针 data、int nd、npy_intp 数组 dimensions 与 strides、PyObject 指针 base、PyArray_Descr 指针 descr、int flags。

注意 descr 不是 Python 层看到的 `np.dtype` 对象本身，而是它的 C 描述子，持有 elsize、kind、byteorder 与一组函数指针（getitem、setitem、cast）。

ufunc（实现在 `numpy/_core/src/umath/ufunc_object.c`）调用时先做 type resolution：PyUFunc_DefaultTypeResolver 按输入 dtype 查一张类型提升表（即 `np.result_type` 的 C 实现），确定唯一的内层循环函数指针（在 `numpy/_core/src/umath/loops.c` 里为每种 dtype 组合预编译好的 DOUBLE_add 一类），再构造 NpyIter 把任意 stride 与广播的输入规整成连续块喂给内层循环，这一步正是广播 stride 置 0 与 F 序数组仍能复用同一份 C 循环的原因。

内层循环里没有 Python 对象操作，可对连续块发 `SIMD`，flags 里的 `NPY_ARRAY_ALIGNED` 决定是否走对齐加载指令。

`np.add` 的 `types` 属性列出全部已注册签名（如 dd->d、ff->f），而 `np.add.reduce` 走另一条 reduce 内层循环。这层『一次分发加连续块循环』才是正文『写出 Python for 循环就丢掉优势』的源码根据：丢掉的不是算术次数，而是把类型判断提前到分发阶段一次完成的机会。

朴素顺序累加的误差界：每步 (s + x) 的相对误差不超过 u，float64 下 u 取 2 的 -53 次方、约 1.1e-16，n 步后最坏误差约 n 乘 u 乘绝对值之和，即 `O(n*u)`，且同号数累加时误差单向漂移。

`np.sum` 对连续一维浮点数组用 pairwise summation（见 `numpy/_core/src/umath/loops_utils.h.src` 的 pairwise_sum）：递归二分求和，树深 `log2(n)`，每层误差只乘一次 u，误差界降到 `O(u*log(n)*sum|x|)`。

实测很直观：十万个 0.1 朴素累加误差约 1.885e-08，两两求和为 0；更极端的 1e16 加十个 1.0 再减 1e16，朴素累加得 0.0（十个 1.0 全被大数吞掉）、两两求和得 4.0、`math.fsum` 用 Shewchuk 补偿算法给出精确的 10.0。

触发条件要记牢：pairwise 只在数组内存连续且 dtype 为浮点时启用，非连续切片或 object dtype 会退回朴素循环，误差又回到 `O(n*u)`。架构权衡是 pairwise 比朴素多约两倍加法换精度、fsum 精确却慢数倍且要额外存部分和；

金融累加不能靠 `np.sum` 的 pairwise 兜底，仍要 `Decimal` 或 Kahan 补偿。正文只说『聚合放到 C 层』，这里把 C 层里选了哪种求和算法讲清楚。

```python
import math

def naive_sum(xs):
    s = 0.0
    for x in xs:
        s += x
    return s

def pairwise_sum(xs, block=8):
    if len(xs) <= block:
        s = 0.0
        for x in xs:
            s += x
        return s
    mid = len(xs) // 2
    return pairwise_sum(xs[:mid], block) + pairwise_sum(xs[mid:], block)

xs = [0.1] * 100000
exact = 10000.0
print('exact', exact)
print('naive', repr(naive_sum(xs)))
print('pairwise', repr(pairwise_sum(xs)))
print('math.fsum', repr(math.fsum(xs)))
print('naive abs err', format(abs(naive_sum(xs) - exact), '.3e'))
print('pairwise abs err', format(abs(pairwise_sum(xs) - exact), '.3e'))

xs2 = [1e16] + [1.0] * 10 + [-1e16]
print('cancellation naive', naive_sum(xs2))
print('cancellation pairwise', pairwise_sum(xs2))
print('cancellation fsum', math.fsum(xs2))

def byte_offset(idx, strides):
    return sum(i * s for i, s in zip(idx, strides))

print('C (2,1)', byte_offset((2, 1), (32, 8)))
print('F (2,1)', byte_offset((2, 1), (8, 24)))

```

<OutputBox title='扩展示例运行结果' output='exact 10000.0\nnaive 10000.000000018848\npairwise 10000.0\nmath.fsum 10000.0\nnaive abs err 1.885e-08\npairwise abs err 0.000e+00\ncancellation naive 0.0\ncancellation pairwise 4.0\ncancellation fsum 10.0\nC (2,1) 72\nF (2,1) 40' />

<LineByLine code='import math\n\ndef naive_sum(xs):\n    s = 0.0\n    for x in xs:\n        s += x\n    return s\n\ndef pairwise_sum(xs, block=8):\n    if len(xs) &lt;= block:\n        s = 0.0\n        for x in xs:\n            s += x\n        return s\n    mid = len(xs) // 2\n    return pairwise_sum(xs[:mid], block) + pairwise_sum(xs[mid:], block)\n\nxs = [0.1] * 100000\nexact = 10000.0\nprint(&#39;exact&#39;, exact)\nprint(&#39;naive&#39;, repr(naive_sum(xs)))\nprint(&#39;pairwise&#39;, repr(pairwise_sum(xs)))\nprint(&#39;math.fsum&#39;, repr(math.fsum(xs)))\nprint(&#39;naive abs err&#39;, format(abs(naive_sum(xs) - exact), &#39;.3e&#39;))\nprint(&#39;pairwise abs err&#39;, format(abs(pairwise_sum(xs) - exact), &#39;.3e&#39;))\n\nxs2 = [1e16] + [1.0] * 10 + [-1e16]\nprint(&#39;cancellation naive&#39;, naive_sum(xs2))\nprint(&#39;cancellation pairwise&#39;, pairwise_sum(xs2))\nprint(&#39;cancellation fsum&#39;, math.fsum(xs2))\n\ndef byte_offset(idx, strides):\n    return sum(i * s for i, s in zip(idx, strides))\n\nprint(&#39;C (2,1)&#39;, byte_offset((2, 1), (32, 8)))\nprint(&#39;F (2,1)&#39;, byte_offset((2, 1), (8, 24)))\n' :notes='["导入 math，用 fsum 作精确基准", "空行，只用于分隔逻辑块，不影响执行结果。", "naive_sum 复刻顺序累加，对应误差界 O(n u)", "pairwise_sum 递归二分，树深 log2(n) 对应 O(u log n)", "block=8 时退化为朴素小段，整棵树仍是对数深度", "构造十万个 0.1，真值恰为 10000.0", "打印三种累加结果，观察朴素值的尾数漂移", "空行，只用于分隔逻辑块，不影响执行结果。", "用科学计数法对比朴素与两两求和的绝对误差", "构造 1e16 加十个 1.0 再减的相消场景", "朴素累加把十个 1.0 全部吞掉得到 0.0", "两两求和保住部分精度得到 4.0", "math.fsum 用补偿算法给出精确 10.0", "byte_offset 实现 offset 等于索引与 strides 的点积", "C 序 (3,4) float64 的 strides 是 (32, 8)，元素 (2,1) 落在 72 字节", "F 序 strides 是 (8, 24)，同一逻辑元素落在 40 字节", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `xs = [0.1] * 100000` 的作用，可对照上方输出逐项核对。", "这一行 `exact = 10000.0` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;exact&#39;, exact)` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;naive&#39;, repr(naive_sum(xs)))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;pairwise&#39;, repr(pairwise_sum(xs)))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;math.fsum&#39;, repr(math.fsum(xs)))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;naive abs err&#39;, format(abs(naive_sum(xs) - ex` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;pairwise abs err&#39;, format(abs(pairwise_sum(xs` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `xs2 = [1e16] + [1.0] * 10 + [-1e16]` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;cancellation naive&#39;, naive_sum(xs2))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;cancellation pairwise&#39;, pairwise_sum(xs2))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;cancellation fsum&#39;, math.fsum(xs2))` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `def byte_offset(idx, strides):` 的作用，可对照上方输出逐项核对。", "这一行 `return sum(i * s for i, s in zip(idx, strides))` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。", "这一行 `print(&#39;C (2,1)&#39;, byte_offset((2, 1), (32, 8)))` 的作用，可对照上方输出逐项核对。", "这一行 `print(&#39;F (2,1)&#39;, byte_offset((2, 1), (8, 24)))` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />


### np.sum 两两求和的误差界推导

朴素顺序累加的误差界：每步 (s + x) 的相对误差不超过 u，float64 下 u 取 2 的 -53 次方、约 1.1e-16，n 步后最坏误差约 n 乘 u 乘绝对值之和，即 `O(n*u)`，且同号数累加时误差单向漂移。

`np.sum` 对连续一维浮点数组用 pairwise summation（见 `numpy/_core/src/umath/loops_utils.h.src` 的 pairwise_sum）：递归二分求和，树深 `log2(n)`，每层误差只乘一次 u，误差界降到 `O(u*log(n)*sum|x|)`。

实测很直观：十万个 0.1 朴素累加误差约 1.885e-08，两两求和为 0；更极端的 1e16 加十个 1.0 再减 1e16，朴素累加得 0.0（十个 1.0 全被大数吞掉）、两两求和得 4.0、`math.fsum` 用 Shewchuk 补偿算法给出精确的 10.0。

触发条件要记牢：pairwise 只在数组内存连续且 dtype 为浮点时启用，非连续切片或 object dtype 会退回朴素循环，误差又回到 `O(n*u)`。架构权衡是 pairwise 比朴素多约两倍加法换精度、fsum 精确却慢数倍且要额外存部分和；

金融累加不能靠 `np.sum` 的 pairwise 兜底，仍要 `Decimal` 或 Kahan 补偿。正文只说『聚合放到 C 层』，这里把 C 层里选了哪种求和算法讲清楚。

**NumPy 源码组件与数值行为**

| 源码位置 | 结构 / 算法 | 触发条件与代价 |
| --- | --- | --- |
| numpy/_core/include/numpy/ndarraytypes.h | PyArrayObject：data、dimensions、strides、descr、flags | 所有 ndarray 的 C 层表示，descr 带 elsize 与函数指针 |
| numpy/_core/src/umath/ufunc_object.c | PyUFunc_DefaultTypeResolver 查类型提升表 | 调用时一次分发，确定唯一内层循环 |
| numpy/_core/src/umath/loops.c | DOUBLE_add 等按 dtype 预编译的 C 循环 | 连续块可发 SIMD，无 Python 对象操作 |
| numpy/_core/src/multiarray/nditer | NpyIter 缓冲与广播 stride 置 0 的规整 | 让 F 序与非连续输入复用同一内层循环 |
| numpy/_core/src/umath/loops_utils.h.src | pairwise_sum 二分递归累加 | 仅连续浮点数组启用，误差 O(u log n) |


### SIMD 向量宽度与 C/F 序的缓存行命中

<Quiz no='093-1' q='关于 np.sum 的累加精度，下面哪项准确？' :options='["连续浮点数组走两两求和，误差界约 O(u log n)；朴素顺序累加是 O(n u)，都会被大数相消放大", "np.sum 与 math.fsum 一样用补偿算法，任何 dtype 都精确", "非连续切片仍走两两求和，精度与连续数组完全一致", "float64 的机器精度 u 是 2 的 -16 次方，故一万次累加误差约 0.15"]' answer="0" explain='np.sum 的两两求和只对连续浮点数组启用，把误差从 O(n u) 降到 O(u log n)；非连续切片或 object dtype 退回朴素循环。float64 的 u 是 2 的 -53 次方约 1.1e-16，不是 2 的 -16 次方。math.fsum 用 Shewchuk 补偿算法才保证精确，代价是额外存部分和与更慢的速度，三者不是同一档。' />

<Term word='缓存行' text='CPU 与主存之间一次交换的最小单位，x86 常见 64 字节，正好装 8 个 float64。C 序数组按行遍历时相邻元素落在同一缓存行、一次 miss 能供 8 个数；F 序数组按行跳着读会每行都 miss，同样的算术次数却多出数倍内存停顿。这解释了为什么 reshape 与转置不改数据、只改 strides，却可能显著改变实测耗时。' />


## 练习、预测题与一页纸速记

<Exercise title='基础：实现并验证广播形状推导' task='补全 broadcast_shape，使 (4, 1, 3) 与 (2, 3) 能推导出 (4, 2, 3)，并说明为什么 (2, 3) 要被左侧补 1 而不是右对齐后丢弃维度。' solution='def broadcast_shape(a, b):\n    out = []\n    for i in range(1, max(len(a), len(b)) + 1):\n        da = a[-i] if i &lt;= len(a) else 1\n        db = b[-i] if i &lt;= len(b) else 1\n        if da == db or da == 1 or db == 1:\n            out.append(max(da, db))\n        else:\n            return None\n    return tuple(reversed(out))\n\nprint(broadcast_shape((4, 1, 3), (2, 3)))' explain='从最右维起逐位取 a[-i] / b[-i]，缺失就当 1，因此 (2, 3) 相当于 (1, 2, 3)，三对维度 (4/1、1/2、3/3) 全部兼容，结果是 (4, 2, 3)。' />

<Exercise title='进阶：用 stride 公式判断 reshape 是否零拷贝' task='给定 float64 的 (3, 4) C 连续数组 strides=(32, 8)，写出元素 (2, 1) 的字节偏移；说明 reshape(4, 3) 与 a[:, ::2] 各自是否搬数据，并给出判定依据。' solution='def offset(idx, strides):\n    return sum(i * s for i, s in zip(idx, strides))\n\nprint(&#39;offset(2,1)&#39;, offset((2, 1), (32, 8)))\n# reshape 只需连续且元素总数不变 -&gt; 改写元数据，零拷贝\n# a[:, ::2] 把列步长从 8 改成 16、起始不变 -&gt; 仍是视图，零拷贝' explain='offset = 2*32 + 1*8 = 72 字节。reshape 只要数组内存连续、元素总数不变就能只改 shape/strides；带步长的切片改的是 strides 而非数据，两者都不搬字节，而转置后不再 C 连续，reshape 才会触发复制。' />

<Quiz no='093-2' q='a = np.arange(12).reshape(3, 4); b = a[:, 0]; b += 100 之后 a 会怎样？' :options='["a 的第 0 列被加了 100，因为基本切片返回共享内存的视图", "a 完全不变，切片总是复制一份", "抛出 ValueError，视图不允许原地修改", "只有第一行变化"]' answer="0" explain='基本切片返回视图，b 与 a 共享同一块数据；b += 100 是原地运算，直接写回底层 buffer，所以 a[:, 0] 全部加 100。想要独立数据必须用 .copy()。' />

<Quiz no='093-3' q='关于广播，(2, 3) 与 (2,) 相加的结果是？' :options='["报错，尾部维度 3 与 2 既不相等也都不为 1", "得到 (2, 3)", "得到 (2, 2)", "自动把 (2,) 补成 (1, 2) 后得 (2, 3)"]' answer="0" explain='右对齐后比较尾维：3 对 2，二者不相等且都不为 1，违反广播规则，NumPy 抛 ValueError。(3,) 才能与 (2, 3) 广播，(2,) 不行。' />

<Quiz no='093-4' q='为什么 ndarray 的逐元素运算比 Python list 循环快一个量级？' :options='["数据是固定 dtype 的连续裸内存，循环在 C 层执行，不逐元素做类型分派与引用计数", "NumPy 用多线程并行了每个元素", "list 不能存数字", "ndarray 把数据缓存进了 CPU 寄存器"]' answer="0" explain='list 存的是指向独立 PyObject 的指针，每个元素运算都要过字节码、动态类型判断与引用计数；ndarray 把值连续存放、dtype 固定，C 层紧凑循环一次扫完。' />

<Predict no='093-5' q='调用前面 code 的 broadcast_shape((2, 3), (2,)) 会返回什么？' :options='["None", "(2, 3)", "(2, 2)"]' answer='0' output='None' explain='尾维 3 与 2 冲突，函数走 else 分支返回 None，对应真实 NumPy 抛出的 ValueError: operands could not be broadcast together。' />

<FillBlank no='093-6' tpl='___ broadcast_shape(a, b):' :answers='["def"]' hint='回想本讲关于 ndarray 与 dtype 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 ndarray、dtype 与连续内存：快在哪里 的落点。' />

<KnowledgeCard :points='["ndarray = 连续裸内存 + shape/strides/dtype；int64/float64 8 字节、float32/int32 4 字节、uint8/bool 1 字节", "ufunc 与归约把循环放 C 层，一次调用处理整批；写出 Python for 循环就丢掉全部优势", "strides 记录每维加 1 跳过的字节数；reshape/基本切片/a.T 只改元数据、是 O(1) 视图", "基本切片返回视图、改了写回原数组；布尔与花式索引返回副本；a[a&gt;0]=0 是 __setitem__ 赋值语法才生效", "广播右对齐逐维比较：相等或为 1 或缺失即兼容，stride 置 0 零拷贝；不兼容抛 ValueError", "用 a*b+c 会生临时数组，大数组改 np.multiply(...,out=) 与就地 +=；keepdims=True 保住维度"]' :pitfalls='["布尔索引取出后赋值，原数组纹丝不动", "uint8 像素加 20 后数值反而变小", "本想拿一份独立数据，改 b 却把 a 也改了", "用 arr[arr &gt; 0] 返回的副本做赋值，改动不会落回原数组，这类静默失败很难查"]' summary='NumPy 的快来自连续内存加 C 级循环，而视图机制让切片几乎零成本；一旦写出 Python for 循环，优势立刻消失' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| ndarray = 连续裸内存 + shape/strides/dtype；int64/float64 8 字节、float32/int32 4 字节、uint8/bool 1 字节 | 建立直觉 |
| ufunc 与归约把循环放 C 层，一次调用处理整批；写出 Python for 循环就丢掉全部优势 | 跑通示例 |
| strides 记录每维加 1 跳过的字节数；reshape/基本切片/a.T 只改元数据、是 O(1) 视图 | 深入边界 |
| 基本切片返回视图、改了写回原数组；布尔与花式索引返回副本；a[a>0]=0 是 __setitem__ 赋值语法才生效 | 工程落地 |
| 广播右对齐逐维比较：相等或为 1 或缺失即兼容，stride 置 0 零拷贝；不兼容抛 ValueError | 随堂检测 |
| 用 a*b+c 会生临时数组，大数组改 np.multiply(...,out=) 与就地 +=；keepdims=True 保住维度 | 复盘 |

1. ndarray = 连续裸内存 + shape/strides/dtype；int64/float64 8 字节、float32/int32 4 字节、uint8/bool 1 字节

2. ufunc 与归约把循环放 C 层，一次调用处理整批；写出 Python for 循环就丢掉全部优势

3. strides 记录每维加 1 跳过的字节数；reshape/基本切片/a.T 只改元数据、是 O(1) 视图

[下一讲：Pandas 清洗、分组、透视与时间序列](/data-ai/pandas)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/093-numpy.py`

```bash
python3 examples/lessons/093-numpy.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/093-numpy.py) · [全部示例代码索引](/examples/)
