---
title: 第 007 讲 · 变量是名字绑定：赋值、引用与命名规范
description: 能解释赋值语句到底做了什么
---

<StageHeader stage='L1 · 编程地基' level='★☆☆☆☆' time='25 分钟' goal='能解释赋值语句到底做了什么' prereq='第 006 讲 · 一切皆对象：id、type、value 与可变性' />

# 第 007 讲 · 变量是名字绑定：赋值、引用与命名规范

把每个值都还原成对象后，还有一侧没看：等号左边的名字。很多人仍把变量想成装值的盒子，于是别名、传参、默认参数处处别扭。说穿了就一句：变量是名字，赋值即绑定，是贴标签而不是复制。在函数里给列表 append 一项，下次调用它竟还在；想交换两个变量，又怕多出副本——都指向同一个误会。我们先把绑定放进名字空间里看，再顺着链式赋值、解包与星号解包写利落；接着对比增强赋值的两条路；最后借 `__defaults__` 看清默认值只求值一次、为何跨调用共享。带着第 6 讲的对象与可变性就够；学完你能写干净的数据交换与多返回值，躲开共享状态的幽灵结果。


## a = b 为什么不是复制：名字空间里的键

一个批处理函数写成 `def add(item, bucket=[]):`，第一次调用返回 ['a']，第二次返回 ['a', 'b']，测试单条用例全过、连起来跑就串数据；

排查时发现那个空列表不是每次调用新建的，而是函数定义时就创建、被所有调用共享。另一处代码用 for 循环往同一个 list 里累加每轮结果，忘了每轮清空，导致第 N 轮带着前 N-1 轮的残留；还有人写 `x = y = []` 以为得到两个独立列表，往 x 里 append 后 y 也变了。

这些「幽灵状态」看起来像并发问题，其实是没弄清赋值到底做了什么。朴素解法是「加个判断、用完清一下」，但如果不理解 `a = b` 只让两个名字指向同一处、不理解 += 对 list 是原地改而对 int 是重新绑定，补丁只会从一处挪到另一处。

本讲拆开解包赋值、星号解包、链式赋值与增强赋值的确切语义，并用 `inspect.signature` 与 `__defaults__` 把「默认值定义时求值一次」变成可核对的证据。

Python 的赋值语句从不复制对象。`a = obj` 做的是把名字 a 写入当前名字空间（模块级是 globals 字典，函数内是 locals 快速数组），让它的值指向 obj 这个 PyObject 的指针；`a = b` 不复制 b 指向的对象，只是让 a 指向同一个对象，因此两个名字互为别名。

链式赋值 `x = y = []` 从右往左求值：先创建一个空 list，再依次把 y 与 x 都绑定到它，于是 `x.append(1)` 之后 y 也是 [1]，用 `x is y` 可证。

这个模型还解释了 del：del a 删除的是名字空间里的键、并把对象引用计数减一，只有当引用计数归零时对象才被回收，删掉一个名字不会影响其他别名。

作用域初识：函数内给名字赋值会把它标记为本局部变量（编译期由符号表决定），因此「先读全局再赋值」会抛 UnboundLocalError，想改全局须用 global、改外层闭包变量用 nonlocal。

命名规范上 PEP 8 建议用 `snake_case` 表达业务含义（`user_count` 而非 n 或 `int_var`），常量用全大写，类名用 CapWords；让名字表达「是什么」而不是「什么类型」，因为类型属于对象，写进名字反而在类型变化时变成误导。


## 最小示例：一次赋值里名字与对象各发生了什么

```python
a, b = 1, 2
a, b = b, a
print('swapped', a, b)

first, *middle, last = [10, 20, 30, 40]
print('first', first, 'middle', middle, 'last', last)

x = y = []
x.append(1)
print('chain_alias', y)

n = 5
n += 1
print('int_aug', n)
```

<OutputBox title='主示例运行结果' output='swapped 2 1\nfirst 10 middle [20, 30] last 40\nchain_alias [1]\nint_aug 6' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='a, b = 1, 2\na, b = b, a\nprint(&#39;swapped&#39;, a, b)\n\nfirst, *middle, last = [10, 20, 30, 40]\nprint(&#39;first&#39;, first, &#39;middle&#39;, middle, &#39;last&#39;, last)\n\nx = y = []\nx.append(1)\nprint(&#39;chain_alias&#39;, y)\n\nn = 5\nn += 1\nprint(&#39;int_aug&#39;, n)' :notes='["把 1 与 2 分别绑定到 a 与 b", "右侧先打包成元组 (2, 1)，再按位置赋回左侧，实现原子交换", "打印交换结果，无需临时变量", "星号解包：first 收首项、last 收末项、middle 收中间全部", "middle 得到 list 类型的 [20, 30]，不是元组", "链式赋值从右往左：先建一个空 list，再把 y 与 x 都绑到它", "对 x 原地 append，修改的是 x 与 y 共同指向的对象", "y 作为别名看到同一份内容，打印 [1]", "把 n 绑定到整数 5", "int 不可变，+= 退回 __add__ 算出 6 再重新绑定 n", "打印重新绑定后的值 6"]' title='第 007 讲 · 变量是名字绑定：赋值、引用与命名规范' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**赋值形式对照**

| 写法 | 实际动作 | 是否产生副本 |
| --- | --- | --- |
| a = obj | 名字空间写键指向 obj | 否 |
| a = b | a 指向 b 的同一对象 | 否 |
| x = y = [] | 两个名字绑定同一新建 list | 否 |
| a, b = b, a | 右打包元组后按位置绑定 | 否（值交换） |
| first, *mid, last = seq | 星号收剩余项为 list | 否 |


## 解包、星号与增强赋值：三种写法的确切语义

解包赋值把右侧可迭代对象逐项绑定到左侧名字：`a, b = b, a` 先由右侧元组打包出当前值，再按位置赋给左侧，因此是原子交换、不需要临时变量；函数 return x, y 其实是返回一个元组，调用方 `a, b = f()` 再解包，所以「多返回值」只是元组打包解包的语法糖。

星号解包 `first, *middle, last = seq` 让带星号的名字收下中间所有剩余项，类型是 list 而非元组，且一个解包语句里只能有一个带星号的目标；

`a, *rest = [1]` 时 rest 得到空列表 []，这是合法边界而非错误。链式与解包都只做绑定，不产生副本。增强赋值 `x += y` 的语义与 `x = x + y` 不同：它先尝试调用 `x.__iadd__(y)`，若返回 NotImplemented 或类型未实现，才退回 `__add__` 再重新绑定。

list 实现 `__iadd__` 因而原地扩展、身份不变；int、str、tuple 不可变，只能退回重新绑定、身份改变。这条差别既是 `a += b` 与 `a = a + b` 在别名场景下结果不同的原因，也是可变默认参数与循环复用 list 产生跨调用幽灵状态的根：同一对象被反复原地修改，却没有任何报错。

```python
def collect(item, bucket=[]):
    bucket.append(item)
    return bucket

r1 = collect('a')
print('r1', r1)
r2 = collect('b')
print('r2', r2)
print('shared', r1 is r2)

def fixed(item, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(item)
    return bucket

print('fixed', fixed('a'), fixed('b'))
```

<OutputBox title='对照写法：先自己猜，再点开' output='r1 [&#39;a&#39;]\nr2 [&#39;a&#39;, &#39;b&#39;]\nshared True\nfixed [&#39;a&#39;] [&#39;b&#39;]' guess="true" />


## 默认值只求值一次：__defaults__ 与 inspect 的证据

函数定义是一条可执行语句：def 执行时会创建函数对象，并把默认参数按从左到右求值一次，结果存进函数对象的 `__defaults__` 元组（仅关键字默认值存进 `__kwdefaults__` 字典）。之后每次调用若不传该参数，取用的都是 `__defaults__` 里那个早已存在的对象，不会重新求值。

于是 `def f(x, acc=[]):` 里的空列表在函数定义时创建一次，所有调用共享；

`acc.append` 原地修改后，下一次调用看到的还是被改过的同一个列表。

用 `inspect.signature(f).parameters['acc'].default` 能拿到同一个对象，`f.__defaults__[0]` 与它做 is 比较为 True，`f(1)` 之后 `__defaults__` 打印成 ([1],)，这些都是直接证据。

正确写法是用 None 占位：下面这段代码，把创建动作挪到函数体内、每次调用各建一份。

```python
def f(x, acc=None):
    if acc is None:
        acc = []
```

同理，循环里复用同一个 list 累加每轮结果会留下残留，应每轮新建或用列表推导式一次成型。把这条规则与 PEP 8 命名合起来用，就得到清晰的接口约定：不修改传入的可变对象，需要修改时先复制，并在文档里写明，避免调用方拿到被悄悄改过的数据。


## 名字绑定的底层：引用、别名与 PEP 8 命名

赋值语句在字节码层面是 `STORE_NAME`、`STORE_FAST` 或 `STORE_GLOBAL` 之一：先由右侧表达式算出一个对象引用压栈，再把栈顶弹出写入名字空间对应的槽位。

函数内部的局部变量在编译期就由符号表分配了 `co_varnames` 里的固定下标，因此运行时用 `LOAD_FAST` 与 `STORE_FAST` 直接按索引访问数组，比查字典快；

这也是「赋值即局部变量声明」的由来——只要函数体某处给名字赋值，编译器就把它全程当局部变量，读取发生在赋值之前会抛 UnboundLocalError。

解包由 `UNPACK_SEQUENCE` 与 `UNPACK_EX` 指令实现，后者处理带星号的目标，把多余元素收集成 list。

增强赋值编译成带就地语义的操作，运行时查类型的 `nb_inplace_add` 槽位：list 实现了它便原地改 PyListObject 的 `ob_item` 数组，不可变类型没有则退回普通加法并把结果重新 `STORE`。

函数对象的 `func_defaults`（即 `__defaults__`）在 `MAKE_FUNCTION` 时由栈顶元组填入，之后每次调用把缺省值直接压栈，不再求值。于是「默认值只算一次」不是约定，而是对象生命周期的必然结果。

<ConceptDiagram type='layers3' title='第 007 讲 · 赋值即绑定：名字空间里的键，不是装值的盒子' labels='赋值即绑定：名字空间里的键，不是装值的盒子|解包、星号与增强赋值：三种写法的确切语义|默认值只求值一次：__defaults__ ' caption='能解释赋值语句到底做了什么' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 报表汇总：用解包与 None 占位写出不串数据的接口

一个报表服务要按地区汇总订单，早期实现把累计用的 list 写成默认参数，导致不同地区的行互相串；改成每轮新建后又发现函数既要返回总数又要返回明细，调用方写成 `result[0]`、`result[1]` 很难读。

下面这段给出工程写法：用 None 占位保证每次调用独立，用元组打包返回 (total, rows) 让调用方解包，用星号解包把表头、数据行与表尾分开，再统计行数。最后验证两次调用返回的明细对象身份不同。重点是让赋值语义显式化：不共享可变默认值、不依赖下标猜返回值含义、命名直接表达业务对象。

```python
def summarize(rows, acc=None):
    if acc is None:
        acc = []
    for name, amount in rows:
        acc.append((name, amount))
    total = sum(amount for _, amount in acc)
    return total, acc

def render(report):
    head, *body, tail = report
    return {'head': head, 'rows': len(body), 'tail': tail}

batch1 = [('north', 10), ('south', 20)]
batch2 = [('east', 5)]
t1, r1 = summarize(batch1)
t2, r2 = summarize(batch2)
print('totals', t1, t2)
print('isolated', r1 is not r2)
print('r2_len', len(r2))
lines = ['HEAD', 'r1', 'r2', 'FOOT']
print('render', render(lines))
```

<Callout type="idea" title='落地提示' text='解包赋值能写出可读性极高的数据交换与函数多返回；命名上让名字表达业务含义而不是类型' />


## 串数据的错因速查

跨调用冒出脏数据，先定位那个被共享的对象。

函数侧看 `f.__defaults__` 与 `inspect.signature(f)` 是否 is 同一个列表，调用一次后变成 ([1],) 就是铁证，关键字默认值查 `__kwdefaults__`；

循环侧用 `id()` 确认 list 是否被每轮复用，+= 走 `__iadd__` 原地改是帮凶。断开共享：默认参数用 None 占位进函数体再建，副本用 `list(y)` 或 `copy.deepcopy`，过滤用推导式重建。下表按现象、根因、写法列出，配排查顺序。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用可变对象作默认参数 | 默认值在 def 执行时求值一次并存入 __defaults__，所有调用共享，append 会跨调用累积 | 改用 acc=None 占位，进入函数后再 acc = []；需要保留调用方传入的容器时先复制 |
| 把 a = b 当成复制、把连等号当成建两个对象 | 赋值只做名字绑定，x = y = [] 让两个名字指向同一 list，原地修改互相可见 | 需要独立副本时显式用 list(y)、y.copy() 或 copy.deepcopy |
| 循环里复用同一个 list 累加每轮结果 | 上一轮 append 的内容留到下一轮，产生跨迭代的幽灵状态且不报错 | 每轮新建列表，或用列表推导式一次成型，避免共享可变状态 |

<Callout type="warn" title='本讲最容易踩的坑' text='用可变对象作默认参数：默认值在 def 执行时求值一次并存入 __defaults__，所有调用共享，append 会跨调用累积' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用可变对象作默认参数", "body": "默认值在 def 执行时求值一次并存入 __defaults__，所有调用共享，append 会跨调用累积", "tip": "改用 acc=None 占位，进入函数后再 acc = []；需要保留调用方传入的容器时先复制"}, {"title": "第 2 步：把 a = b 当成复制、把连等号当成建两个", "body": "赋值只做名字绑定，x = y = [] 让两个名字指向同一 list，原地修改互相可见", "tip": "需要独立副本时显式用 list(y)、y.copy() 或 copy.deepcopy"}, {"title": "第 3 步：循环里复用同一个 list 累加每轮结果", "body": "上一轮 append 的内容留到下一轮，产生跨迭代的幽灵状态且不报错", "tip": "每轮新建列表，或用列表推导式一次成型，避免共享可变状态"}]' />


## 绑定与命名：练习、自测与速记

<Exercise title='基础：用解包交换与星号收集' task='写两行用解包交换 a 与 b 的值；再用 first, *rest = [1, 2, 3, 4] 打印 first 与 rest，并说明星号目标的类型。' solution='a, b = 1, 2\na, b = b, a\nprint(&#39;swapped&#39;, a, b)\nfirst, *rest = [1, 2, 3, 4]\nprint(&#39;first&#39;, first, &#39;rest&#39;, rest, &#39;type&#39;, type(rest).__name__)' explain='右侧先打包元组再按位置赋回，交换是原子的；星号目标由 UNPACK_EX 收集剩余元素，结果总是 list。' />

<Exercise title='进阶：证明默认值共享并修复' task='定义 def f(x, acc=[]):，打印 __defaults__，调用一次观察累积；再写 g(x, acc=None) 版本，验证两次调用返回的对象身份不同。' solution='import inspect\ndef f(x, acc=[]):\n    acc.append(x)\n    return acc\nprint(&#39;defaults_before&#39;, f.__defaults__)\nf(1)\nprint(&#39;defaults_after&#39;, f.__defaults__)\nprint(&#39;same_as_sig&#39;, f.__defaults__[0] is inspect.signature(f).parameters[&#39;acc&#39;].default)\ndef g(x, acc=None):\n    if acc is None: acc = []\n    acc.append(x)\n    return acc\nprint(&#39;isolated&#39;, g(1) is not g(2))' explain='__defaults__ 里的 list 与 signature 拿到的 default 是同一对象，f(1) 原地修改后下次调用继续用；None 占位把创建挪进函数体，每次各建一份。' />

<Quiz no='007-1' q='关于 a = b，哪项描述准确？' :options='["a 与 b 指向同一对象，赋值不复制", "a 得到 b 的一份拷贝", "b 被移动到 a 后 b 失效", "分配新内存装了 b 的值"]' answer="0" explain='赋值只把名字写入名字空间指向对象，不复制对象本身；两个名字互为别名，对可变对象的原地修改互相可见。' />

<Quiz no='007-2' q='list 的 += 与 int 的 += 差别在于？' :options='["list 走 __iadd__ 原地改、id 不变；int 退回 __add__ 重新绑定、id 变", "两者都重新绑定", "int 原地改、list 重新绑定", "取决于是否有别名"]' answer="0" explain='增强赋值优先查 nb_inplace_add：list 提供 __iadd__ 返回自身，int 等不可变类型没有该协议，只能算新值再重新绑定。' />

<Quiz no='007-3' q='函数默认参数 acc=[] 的求值时机是？' :options='["def 语句执行时一次，结果存入 __defaults__ 并被所有调用共享", "每次调用时", "第一次调用时", "解释器启动时"]' answer="0" explain='def 是可执行语句，默认值在定义时求值填入 func_defaults；之后调用直接取用同一对象，所以可变默认值会跨调用累积。' />

<Predict no='007-4' q='主示例里 print(&#39;chain_alias&#39;, y) 在 x = y = [] 且 x.append(1) 之后输出什么？' :options='["chain_alias [1]", "chain_alias []", "抛出 NameError"]' answer='0' output='chain_alias [1]' explain='链式赋值从右往左把 x 与 y 绑定到同一个新建 list，append 是原地修改该对象，y 作为别名看到相同内容。' />

<FillBlank no='007-5' tpl='___ b = 1, 2' :answers='["a,"]' hint='回想本讲关于 赋值即绑定 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 赋值即绑定：名字空间里的键，不是装值的盒子 的落点。' />

<KnowledgeCard :points='["赋值即绑定：名字写入名字空间指向对象，a = b 与 x = y = [] 都只产生别名、不复制", "解包 a, b = b, a 是原子交换；函数多返回值是元组打包再解包；星号目标收成 list", "+= 先试 __iadd__：list 原地改、身份不变；int/str/tuple 退回 __add__ 重新绑定", "默认值在 def 执行时求值一次存入 __defaults__，可变默认值被所有调用共享，用 None 占位修复", "循环里复用同一可变容器会跨迭代残留，应每轮新建或用推导式一次成型", "PEP 8 让名字表达业务含义（snake_case、常量大写），类型属于对象不应写进名字"]' :pitfalls='["用可变对象作默认参数", "把 a = b 当成复制、把连等号当成建两个对象", "循环里复用同一个 list 累加每轮结果", "把可变对象当默认参数、或在循环里复用同一个 list，会产生跨调用/跨迭代的幽灵状态"]' summary='a = b 不复制对象，只让两个名字指向同一处；+= 对 list 是原地改，对 int 是重新绑定，差别来自对象是否可变' />

1. 赋值即绑定：名字写入名字空间指向对象，a = b 与 x = y = [] 都只产生别名、不复制

2. 解包 a, b = b, a 是原子交换；函数多返回值是元组打包再解包；星号目标收成 list

3. += 先试 __iadd__：list 原地改、身份不变；int/str/tuple 退回 __add__ 重新绑定

[下一讲：数值体系：int 任意精度、float、Decimal 与 bool](/foundation/numeric)
