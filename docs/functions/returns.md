---
title: 第 029 讲 · 返回值、None 与多返回值
description: 理解函数边界上的数据契约
---

<StageHeader stage='L3 · 函数与抽象' level='★☆☆☆☆' time='25 分钟' goal='理解函数边界上的数据契约' prereq='第 028 讲 · 函数定义与参数形态' />

# 第 029 讲 · 返回值、None 与多返回值

参数怎么传定下来后，函数的另一半边界浮出来了：它把什么交还给调用方。这一讲说的不是语法，而是双方的默契——拿到结果的人该怎么理解它。写查询时容易顺手用 None 表示没找到，可空结果也算合法，调用方就分不清；把内部列表直接递出去，外面一次追加又改到了对象里。

我们先看多返回值只是元组打包再解包，函数始终只交出一个对象；接着谈提前返回与返回可变对象带来的松动；最后延伸到生成器里那句含义不同的 return。接着参数形态，再加元组与解包就够；读完后你能为失败路径留一个不含糊的约定。


## find() 返回 None，调用方为什么崩了

一个用户查询函数 `find(uid)` 被两个调用方复用：A 模块写 `name, age = find(uid)`，B 模块写 `if find(uid) is None` 判断用户不存在。

上线后 A 模块偶尔抛 `TypeError`（cannot unpack non-iterable NoneType object），因为没找到时函数走的是隐式 return，返回 None；而 B 模块更糟——用户记录里 age 字段本就允许为 None，于是合法的空值被当成了查询失败。

朴素解法是让失败时返回 `(None, None)` 凑够元组，A 不报错了，但 B 的 is None 判断彻底失效；再加一个 ok 布尔位变成三元组，又让每个调用点都得记牢下标含义。

本讲把函数边界上的数据契约讲清楚：函数永远只返回一个对象，所谓多返回值是元组打包加解包的语法糖，None 是单例，用同一种类型去表达成功与失败必然产生歧义。


## 函数只有一个返回对象：元组打包与解包

`return a, b` 与 `return (a, b)` 完全等价，逗号才是元组构造符，括号可省；编译后是依次压入 a、b 再 `BUILD_TUPLE` 2，栈上仍只有一个元组对象，而单个 `return a` 不生成 `BUILD_TUPLE`。

调用侧 `x, y = f()` 由 `UNPACK_SEQUENCE` 完成，要求右侧可迭代且元素个数精确匹配，否则抛 `ValueError`（too many 或 not enough values to unpack）。

PEP 3132 在 3.0 引入扩展解包 `a, *rest = seq`，星号目标收集剩余元素且恒为 list，一个解包语句里只能有一个星号目标。

无 return、单独 return、`return None` 三条路径都返回同一个 None 对象，它是 NoneType 的唯一实例，用 `is None` 判断身份而非 `==`。

提前返回（guard clause）能让失败分支先退出、减少嵌套，但代价是函数出现了多个出口，必须保证每个出口返回同一类型，否则调用方就要到处判空。交换 `a, b = b, a`、for 里解包、嵌套解包用的都是同一套机制。

```python
def stats(xs):
    if not xs:
        return None
    return min(xs), max(xs), sum(xs) / len(xs)

print(stats([2, 8, 5]))
lo, hi, avg = stats([2, 8, 5])
print(lo, hi, avg)
print(stats([]) is None)
try:
    a, b = stats([])
except TypeError as e:
    print(type(e).__name__, str(e))
first, *rest = (1, 2, 3, 4)
print(first, rest)
```

<OutputBox title='主示例运行结果' output='(2, 8, 5.0)\n2 8 5.0\nTrue\nTypeError cannot unpack non-iterable NoneType object\n1 [2, 3, 4]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def stats(xs):\n    if not xs:\n        return None\n    return min(xs), max(xs), sum(xs) / len(xs)\n\nprint(stats([2, 8, 5]))\nlo, hi, avg = stats([2, 8, 5])\nprint(lo, hi, avg)\nprint(stats([]) is None)\ntry:\n    a, b = stats([])\nexcept TypeError as e:\n    print(type(e).__name__, str(e))\nfirst, *rest = (1, 2, 3, 4)\nprint(first, rest)' :notes='["定义统计函数：空输入走失败分支，非空返回三个值", "空列表时提前返回 None，这是后面解包崩溃的来源", "返回 None 单例，函数此处结束", "逗号把 min、max、均值打包成一个三元组再返回", "空行，只用于分隔逻辑块，不影响执行结果。", "打印整个返回值，看到它是一个元组对象", "用三个目标解包同一个元组", "三个名字分别拿到最小值、最大值与均值 5.0", "确认空输入的返回值就是 None 单例", "准备捕获对 None 解包时的类型错误", "失败路径返回 None，却按两个目标解包", "捕获预期的 TypeError", "打印异常类型与消息：None 不可迭代", "用扩展解包把首元素与剩余元素分开", "星号目标 rest 收集成 list，不是元组"]' title='第 029 讲 · 返回值、None 与多返回值' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**返回形态与解包规则**

| 写法 | 实际返回对象 | 调用侧 | 出错信号 |
| --- | --- | --- | --- |
| return a, b | 2 元素元组 | x, y = f() | 元素数不符抛 ValueError |
| return a | 单个对象（不建元组） | x = f() | 无 |
| 无 return / return / return None | None 单例 | x is None | 对 None 解包抛 TypeError |
| a, *rest = seq | 首元素 + 一个 list | 批量解包 | 星号目标只能有一个 |
| 含 yield 的函数调用 | generator 对象 | next(g) / for | 耗尽抛 StopIteration |

<ConceptDiagram type='compare2' title='第 029 讲 · 函数只有一个返回对象：元组打包与解包' labels='函数只有一个返回对象：元组打包与解包|返回可变对象与契约污染|生成器函数：return 不是返回值|生成器返回' caption='理解函数边界上的数据契约' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### 多返回值其实是先打包再解包

函数只有一个出口值：`RETURN_VALUE` 弹出栈顶交回调用方。`return a, b` 里逗号才是元组构造符，编译器压入 a、b 再 `BUILD_TUPLE` 2，栈上仍是单个元组，括号可省；单个 `return a` 不生成它。

调用侧 `x, y = f()` 由 `UNPACK_SEQUENCE` 拆开，元素数不符抛 `ValueError`，带星号的 `a, *rest` 走 `UNPACK_EX`、rest 恒为 list（PEP 3132，3.0 起）。

多返回值不过是先打包成元组、再按位置解包。后面的对照把写法与返回对象并排。

<CodeTabs :tabs='[{"label": "主示例", "code": "def stats(xs):\n    if not xs:\n        return None\n    return min(xs), max(xs), sum(xs) / len(xs)\n\nprint(stats([2, 8, 5]))\nlo, hi, avg = stats([2, 8, 5])\nprint(lo, hi, avg)\nprint(stats([]) is None)\ntry:\n    a, b = stats([])\nexcept TypeError as e:\n    print(type(e).__name__, str(e))\nfirst, *rest = (1, 2, 3, 4)\nprint(first, rest)", "note": "函数只有一个返回对象：元组打包与解包"}, {"label": "对照 / 进阶", "code": "class Cart:\n    def __init__(self):\n        self.items = []\n    def raw(self):\n        return self.items\n    def snapshot(self):\n        return tuple(self.items)\n\nc = Cart()\nc.items.append(&#39;book&#39;)\nr = c.raw()\nr.append(&#39;pen&#39;)\nprint(list(c.items), r is c.items)\nprint(c.snapshot(), type(c.snapshot()).__name__)\n\ndef pages():\n    yield &#39;a&#39;\n    return &#39;end&#39;\ng = pages()\nprint(next(g))\ntry:\n    next(g)\nexcept StopIteration as e:\n    print(type(e).__name__, e.value)", "note": "返回可变对象与契约污染"}]' title='两种写法切换看' />

<Term word='隐式 return None' text='`return a, b` 与 `return (a, b)` 完全等价，逗号才是元组构造符，括号可省；编译后是依次压入 a、b 再 `BUILD_TUPLE` 2，栈上仍只有一个元组对象，而单个 `return a` 不生成 `BUILD_TUPLE`。调用侧 `x, y = f()` 由…' />

<Term word='元组打包与解包' text='直接返回 `self.items`、模块级缓存字典或任何内部可变容器，等于把对象引用交给调用方：外部一次 `append()` 就会原地改掉内部状态，而这次改动发生在函数之外、日志里看不到，封装被完全绕过。稳妥做法是返回副本 `list(self._items)`、`tuple(self._items)`，或干脆只暴露…' />


## 返回可变对象与契约污染

直接返回 `self.items`、模块级缓存字典或任何内部可变容器，等于把对象引用交给调用方：外部一次 `append()` 就会原地改掉内部状态，而这次改动发生在函数之外、日志里看不到，封装被完全绕过。

稳妥做法是返回副本 `list(self._items)`、`tuple(self._items)`，或干脆只暴露只读视图与迭代器。

另一类更常见的污染是返回类型不统一：成功返回 list、失败返回 None，会让每个调用方都写 `if result:` 判断，而空列表本身是合法的假值，于是「查到了但结果为空」被误判成「没查到」。库函数的契约应当是二选一：要么始终返回同一类型（找不到就返回空容器），要么始终用异常表达失败，让调用方一处处理。

注解上用 `-> tuple[str, int]`（PEP 585，3.9+）或 `X | None`（PEP 604，3.10+）把契约写出来，但注解默认不强制运行时检查，真正的边界校验要靠代码本身或 pydantic 这类运行时库。

```python
class Cart:
    def __init__(self):
        self.items = []
    def raw(self):
        return self.items
    def snapshot(self):
        return tuple(self.items)

c = Cart()
c.items.append('book')
r = c.raw()
r.append('pen')
print(list(c.items), r is c.items)
print(c.snapshot(), type(c.snapshot()).__name__)

def pages():
    yield 'a'
    return 'end'
g = pages()
print(next(g))
try:
    next(g)
except StopIteration as e:
    print(type(e).__name__, e.value)
```

<OutputBox title='对照写法：先自己猜，再点开' output='[&#39;book&#39;, &#39;pen&#39;] True\n(&#39;book&#39;, &#39;pen&#39;) tuple\na\nStopIteration end' guess="true" />

<Predict no='029-1' q='def f(): return 1, 2, 3 之后执行 a, *rest = f(); print(a, rest) 输出什么？' :options='["1 [2, 3]", "1 (2, 3)", "[1, 2, 3] []"]' answer='0' output='1 [2, 3]' explain='PEP 3132 的星号目标收集剩余全部元素并恒为 list，因此 a 得 1、rest 得 [2, 3]，而不是元组 (2, 3)。' />


## 生成器函数：return 不是返回值

函数体里只要出现 `yield`，它就是生成器函数：编译期在 `co_flags` 置 `CO_GENERATOR`（0x20），调用它并不执行函数体，而是创建并返回一个 generator 对象（`types.GeneratorType`），该对象实现了迭代器协议 `__iter__` / `__next__`，函数帧保存在 `gi_frame` 里，直到第一次 `next()` 才恢复执行。

正因如此，函数体里的异常、资源申请都要等到迭代时才发生，清理必须放在 `try/finally` 或依赖 `close()`。

生成器里的 `return value` 也不是把 value 交给调用方：它终止迭代，并把 value 挂到 `StopIteration.value`（PEP 380，3.3+），普通 for 循环完全看不到这个值，只有显式捕获 `StopIteration` 或用 `yield from` 接收才能拿到；

不带值的 return 则让 value 为 None。

可以用 `inspect.isgeneratorfunction(f)` 与 `inspect.isgenerator(obj)` 区分函数与对象。

这与多返回值的区别很关键：生成器产出的是一串值，而不是一次返回多个值。

CPython 里函数返回只有一个出口值：`RETURN_VALUE` 指令把栈顶对象弹出交给调用方，函数帧随即销毁。所谓多返回值是语法糖，编译器把 `return a, b` 编译成依次压入 a、b 再 `BUILD_TUPLE` 2，栈上仍只有一个元组对象；单个 `return a` 不生成 `BUILD_TUPLE`。

调用侧解包由 `UNPACK_SEQUENCE`（定长）与 `UNPACK_EX`（带星号）完成，元素数不符就在这一步抛 `ValueError`。

None 是全局唯一的 `_Py_NoneStruct` 实例，`Py_None` 的地址固定，所以无 return、return、`return None` 三条路径压栈的都是同一个对象，`is None` 判断的是身份而非值。

生成器是另一条机制：编译期见到 `yield` 就在 `co_flags` 置 `CO_GENERATOR`（0x20），调用时创建 genobject 并保存空帧而不执行，直到 `next()` 才恢复 `gi_frame`；

函数体里的 `return v` 不产生 `RETURN_VALUE` 交给调用方，而是设置 `StopIteration.value = v` 后终止迭代，PEP 380 的 `yield from` 才把这个值取出来。

理解只有一个返回对象，才能解释为什么返回类型必须统一、为什么 None 不能同时表达失败与合法空值。


### 生成器 return 与返回注解的版本演进

生成器里 return 不交值：含 `yield` 就置 `CO_GENERATOR`，调用只得到 generator 对象；

`return v` 则把 v 送进 `StopIteration.value`（PEP 380，3.3 起），`yield from` 才接得住。

3.9 起 `tuple[int, str]` 取代 `typing.Tuple`，3.10 起 `X | None` 表可选，Return 位正对应那个值；

PEP 479（3.7）把漏出的 `StopIteration` 转 `RuntimeError`。下表按 PEP 列出演进。

**返回值相关版本与 PEP**

| 来源 | 版本 | 内容 | 可核对细节 |
| --- | --- | --- | --- |
| PEP 3132 | 3.0 | 扩展可迭代解包 a, *rest | rest 恒为 list，星号目标仅一个 |
| PEP 380 | 3.3 | 生成器 return value 进 StopIteration.value | yield from 可接收该值，普通 for 看不到 |
| PEP 585 | 3.9 | 内建泛型注解 tuple[int, str] | 不再需要 typing.Tuple |
| PEP 604 | 3.10 | X \| None 与联合类型 | Optional[X] 可写成 X \| None |
| CO_GENERATOR | 长期稳定 | co_flags 的 0x20 标记生成器函数 | 调用时返回 genobject 而非执行帧 |

<Callout type="tip" title='核心心智模型' text='`return a, b` 与 `return (a, b)` 完全等价，逗号才是元组构造符，括号可省；编译后是依次压入 a、b 再 `BUILD_TUPLE` 2，栈上仍只有一个元组对象，而单个 `return a` 不生成 `BUILD_TUPLE`。调用侧 `x, y = f()` 由…' />


## 返回值常见错误与修复

最扎眼的两种都指向 None 被当成别的东西。失败路径隐式 return 交回 None 单例，`a, b = find()` 解包就抛 `TypeError`；反过来用 `if r is None` 判失败，又会把合法的 `age=None` 误删。稳妥做法是没找到抛 `LookupError` 子类；

定长解包元素数不符报 `ValueError`。

还有静默一类：直接返回内部 list，外部 `append()` 就改状态，应回 `tuple(self._items)` 副本。

下表按现象、根因、写法列成速查。

**返回值常见错误与修复（3.13 实测消息）**

| 现象 / 消息 | 根因 | 正确写法 |
| --- | --- | --- |
| ValueError: too many values to unpack (expected 2) | 右侧 3 个元素对 2 个目标 | 补一个目标或改用 a, *rest |
| ValueError: not enough values to unpack (expected 2, got 1) | 右侧元素不足 | 给默认值或保证所有路径返回同样结构 |
| TypeError: cannot unpack non-iterable NoneType object | 失败路径返回 None 却被解包 | 先 r = f() 判空再解包，或改抛异常 |
| 返回内部 list 后外部 append 悄悄改了状态 | 返回的是可变对象引用而非副本 | return tuple(self.items) 或 list(self.items) |

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 None 同时表示没找到与合法空值 | 调用方 if r is None 无法区分两种语义，容易把合法结果当失败丢弃 | 没找到抛 LookupError 子类，或返回 Result(ok=..., value=...)；字段缺省用 Optional 表达 |
| 对可能失败的返回值直接 a, b = find() | 失败路径返回 None，解包 None 抛 TypeError: cannot unpack non-iterable NoneType object | 先 r = find() 并判空，或让 find 始终返回同类型元组、失败时抛异常 |
| 函数返回内部 self.items 列表，外部 append 改了对象状态 | 返回的是可变容器引用，封装被绕过，改动在函数外扩散且不可见 | 返回 tuple(self.items) 或 list(self.items) 副本；只暴露只读视图 |

<Callout type="warn" title='本讲最容易踩的坑' text='用 None 同时表示没找到与合法空值：调用方 if r is None 无法区分两种语义，容易把合法结果当失败丢弃' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 None 同时表示没找到与合法空值", "body": "调用方 if r is None 无法区分两种语义，容易把合法结果当失败丢弃", "tip": "没找到抛 LookupError 子类，或返回 Result(ok=..., value=...)；字段缺省用 Optional 表达"}, {"title": "第 2 步：对可能失败的返回值直接 a, b = fin…", "body": "失败路径返回 None，解包 None 抛 TypeError: cannot unpack non-iterable NoneType object", "tip": "先 r = find() 并判空，或让 find 始终返回同类型元组、失败时抛异常"}, {"title": "第 3 步：函数返回内部 self.items 列表，外…", "body": "返回的是可变容器引用，封装被绕过，改动在函数外扩散且不可见", "tip": "返回 tuple(self.items) 或 list(self.items) 副本；只暴露只读视图"}]' />


## Repository 查询：把成功与失败写成一条明确契约

一个用户仓库里 age 字段允许为 None（资料未填），而 uid 不存在又是另一回事。若用 None 表示查不到，合法的 `age=None` 会和失败混淆；若用 `(None, None)` 凑元组，调用方又要额外记约定。

工程上用一个不可变的 Result 把三件事分开：ok 表示查询是否命中、value 放真实数据、error 放原因。find 始终返回 Result，display 只在一处解包 `r.value`，字段缺省再单独判 None。这样函数永远只有一个返回对象、且类型恒定，任何调用方都不需要猜测返回值结构。

下面用标准库 dataclass 实现一个可直接运行的最小版本：成功时返回二元组 `(name, age)`，失败时返回带错误串的 Result，并演示三种 uid 的输出。

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Result:
    ok: bool
    value: object
    error: str

USERS = {'u1': ('Ada', 36), 'u2': ('Lin', None)}

def find(uid):
    if uid not in USERS:
        return Result(False, None, 'not found')
    name, age = USERS[uid]
    return Result(True, (name, age), '')

def display(uid):
    r = find(uid)
    if not r.ok:
        return 'error: ' + r.error
    name, age = r.value
    return name + ' / ' + ('unknown' if age is None else str(age))

print(display('u1'))
print(display('u2'))
print(display('u9'))
print(find('u1').value)
```

<Callout type="idea" title='落地提示' text='库函数要么始终返回同类型，要么抛异常；业务层用 Result / Optional 明确表达可失败' />


## 练一练，再把返回值契约记牢

<Exercise title='基础：观察元组打包与解包错误' task='定义 def f(): return 1, 2, 3，打印返回值与其类型；用 a, *rest = f() 解包并打印；再故意用 x, y = f() 触发异常，打印异常类型与消息。' solution='def f():\n    return 1, 2, 3\n\nprint(f(), type(f()).__name__)\na, *rest = f()\nprint(a, rest)\ntry:\n    x, y = f()\nexcept ValueError as e:\n    print(type(e).__name__, str(e))' explain='return 1, 2, 3 由 BUILD_TUPLE 打包成三元组；UNPACK_EX 把 rest 收成 list；UNPACK_SEQUENCE 遇到 3 个元素对 2 个目标抛 too many values to unpack。' />

<Exercise title='进阶：让失败路径也遵守同一契约' task='对比 divide（b 为 0 时返回 None）与 divide2（b 为 0 时抛 ZeroDivisionError），分别调用并说明为什么后者让调用方只需一处处理。' solution='def divide(a, b):\n    if b == 0:\n        return None\n    return a / b, a % b\n\ndef divide2(a, b):\n    if b == 0:\n        raise ZeroDivisionError(&#39;b is zero&#39;)\n    return a / b, a % b\n\nprint(divide(7, 0) is None)\ntry:\n    divide2(7, 0)\nexcept ZeroDivisionError as e:\n    print(type(e).__name__, str(e))\nprint(divide2(7, 3))' explain='divide 混合返回 None 与元组，调用方必须到处判空；divide2 始终返回二元组或抛异常，成功路径类型恒定，失败集中在一个 except 里处理。' />

<Quiz no='029-2' q='return a, b 实际返回的是什么？' :options='["一个二元组，逗号触发 BUILD_TUPLE", "两个独立的对象", "一个 list", "一个生成器对象"]' answer="0" explain='逗号是元组构造符，编译器生成 BUILD_TUPLE 2；函数只压栈一个对象交给 RETURN_VALUE，括号可省。' />

<Quiz no='029-3' q='函数里完全没有写 return，它的返回值是？' :options='["None 单例", "整数 0", "空元组 ()", "最后一次表达式的值"]' answer="0" explain='无 return、单独 return、return None 三条路径都压入同一个 Py_None 对象；用 is None 判断身份。' />

<Quiz no='029-4' q='生成器函数里写 return &#39;x&#39; 会发生什么？' :options='["&#39;x&#39; 被放进 StopIteration.value，普通 for 看不到", "调用方直接拿到字符串 &#39;x&#39;", "抛 RuntimeError", "被无视，返回值变成 None"]' answer="0" explain='PEP 380 规定生成器 return v 把 v 设到 StopIteration.value；只有捕获 StopIteration 或用 yield from 才能取到，for 循环会静默结束。' />

<FillBlank no='029-5' tpl='___ stats(xs):' :answers='["def"]' hint='回想本讲关于 隐式 return None 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 函数只有一个返回对象：元组打包与解包 的落点。' />

<KnowledgeCard :points='["函数永远只返回一个对象；return a, b 由 BUILD_TUPLE 打包成元组，括号可省", "无 return / return / return None 都返回 None 单例（NoneType 唯一实例），用 is None 判断", "解包元素数不符抛 ValueError: too many / not enough values to unpack；带星号解包（3.0+）星号目标是 list", "含 yield 的函数返回 generator 对象，return v 的值进 StopIteration.value（3.3+），靠 yield from 接收", "返回类型要统一：要么始终同类型，要么失败抛异常；别用 None 兼表失败与合法空值", "返回内部可变容器等于暴露引用，返回 tuple(...) 或副本；注解用 -&gt; tuple[int, str] / X | None（3.9 / 3.10+）"]' :pitfalls='["用 None 同时表示没找到与合法空值", "对可能失败的返回值直接 a, b = find()", "函数返回内部 self.items 列表，外部 append 改了对象状态", "用返回 None 表示失败、又用 None 表示合法结果，会让调用方无法区分两种情况"]' summary='Python 的多返回值其实是返回一个元组再解包，所以函数永远只有一个返回对象，契约反而更统一' />

1. 函数永远只返回一个对象；return a, b 由 BUILD_TUPLE 打包成元组，括号可省

2. 无 return / return / return None 都返回 None 单例（NoneType 唯一实例），用 is None 判断

3. 解包元素数不符抛 ValueError: too many / not enough values to unpack；带星号解包（3.0+）星号目标是 list

[下一讲：作用域、LEGB 与闭包延迟绑定](/functions/scope)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/029-returns.py`

```bash
python3 examples/lessons/029-returns.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/029-returns.py) · [全部示例代码索引](/examples/)
