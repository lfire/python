---
title: 第 030 讲 · 作用域、LEGB 与闭包延迟绑定
description: 能解释并修复闭包捕获的经典 bug
---

<StageHeader stage='L3 · 函数与抽象' level='★★★☆☆' time='35 分钟' goal='能解释并修复闭包捕获的经典 bug' prereq='第 029 讲 · 返回值、None 与多返回值' />

# 第 030 讲 · 作用域、LEGB 与闭包延迟绑定

函数的进与出理清了，接下来往里走一层：同一个名字在哪里被找到。它解释为何同名在不同位置读到的值不一样，也是装饰器成立的地基。常见一幕是在循环里批量生成几个小函数，本以为各自记住当次值，运行起来却整齐返回循环结束后的最后一个数，安静得连提示都没有。

我们先从 LEGB 顺序和「赋值即局部」这条编译期规则说起，再看闭包抓住的是变量本身而非当时的数值，最后把延迟绑定放回循环与装饰器，试几种当场固定的写法。需要嵌套函数、默认参数与变量赋值；弄明白后你能一眼看出那类全都一样的结果从哪来，也为写装饰器备好底子。


## 循环里造的五个函数，为什么全打印 4

给一批阈值批量生成校验函数，代码写成 fs = [lambda x: x > i for i in `range(4)`]，本以为四个函数分别用 0、1、2、3 作阈值，结果全部用 3，而且没有任何异常，排查时打印四个函数对象也长得一模一样。

有人试着在循环体里先写 `j = i` 再让 lambda 引用 j，照样全看最终值——因为 j 和 i 同属一层函数作用域，每轮只是被重新赋值，仍是同一个变量。另一处坑更突兀：函数里先 `print(x)` 想读全局的 x，下一行才写 `x = 1`，运行却抛 UnboundLocalError，明明全局 x 是存在的。

这两个现象指向同一套机制：名字的作用域在编译期就定型，闭包捕获的是变量本身而非当时的值。本讲用 LEGB、global / nonlocal、cell 与 dis 把边界讲透，并给出默认参数捕获、工厂函数、partial 三种可验证的修复。

<Callout type="warn" title='先看一个真实会出错的写法' text='循环里 lambda 引用 i，全部返回最终值：闭包共享同一个 cell，读到的是循环结束后的值，且没有任何报错' />


## 先建立模型：名字、作用域与 cell

<Callout type="tip" title='核心心智模型' text='名字查找顺序是 Local → Enclosing → Global → Built-in，四层都找不到才抛 NameError。关键在于作用域不是运行时逐行判断，而是编译期由符号表决定：只要函数体内任何地方给某名字赋值（含 +=、for 目标、with as、import、def / class ' />

<ConceptDiagram type='flow3' title='第 030 讲 · LEGB 与赋值即局部：名字在编译期定型' labels='LEGB 与赋值即局部：名字在编译期定型|闭包与 cell：捕获的是变量不是值|边界、失效信号与装饰器里的延迟绑定' caption='能解释并修复闭包捕获的经典 bug' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段三 · 函数与抽象 |
| 前置 | 第 029 讲 · 返回值、None 与多返回值 |
| 难度 / 建议时长 | ★★★☆☆ · 35 分钟 |
| 本讲新增 | LEGB 查找顺序、global 与 nonlocal、闭包与自由变量 |
| 一句话目标 | 能解释并修复闭包捕获的经典 bug |
| 为下一讲铺垫 | 高阶函数、lambda 与 map / filter / reduce |


## LEGB 与赋值即局部：名字在编译期定型

名字查找顺序是 Local → Enclosing → Global → Built-in，四层都找不到才抛 NameError。

关键在于作用域不是运行时逐行判断，而是编译期由符号表决定：只要函数体内任何地方给某名字赋值（含 +=、for 目标、with as、import、def / class 绑定），编译器就把它标记为局部并放进 co_varnames，于是整个函数体对它的读取都走 LOAD_FAST；

在赋值之前读取该槽位就抛 UnboundLocalError，3.11 及以后的文案是 cannot access local variable 'x' where it is not associated with a value，3.10 及以前是 local variable 'x' referenced before assignment。

global x 把名字绑定到模块命名空间，读写走 LOAD_GLOBAL / STORE_GLOBAL；

nonlocal x（PEP 3104，3.0+）绑定到最近一层非全局的闭包 cell，读写走 LOAD_DEREF / STORE_DEREF，且要求该名字确实存在于外层函数作用域，否则编译期就报 SyntaxError: no binding for nonlocal 'x' found。

只读名字沿 LEGB 逐层回退，dis 里能看到 LOAD_GLOBAL；内建名如 len 属 Built-in 层，一旦被同名局部变量遮蔽就优先取局部。

**编译期名字定型规则与失效信号**

| 函数体特征 | 名字被判为 | 读取 / 写入指令 | 失效信号 |
| --- | --- | --- | --- |
| 任意处对 x 赋值（含 +=、for、import） | 局部 Local | LOAD_FAST / STORE_FAST | 赋值前读取抛 UnboundLocalError |
| 只读取、从不赋值 | 沿 LEGB 逐层找 | LOAD_GLOBAL 或 LOAD_DEREF | 四层都无则 NameError |
| 声明 global x | 全局 Global | LOAD_GLOBAL / STORE_GLOBAL | 遮蔽同名内建与闭包 |
| 声明 nonlocal x | 外层闭包 cell | LOAD_DEREF / STORE_DEREF | 外层无该名字则 SyntaxError |
| class 体内引用外层函数局部 | 不形成闭包 | 走 LOAD_GLOBAL | 方法里读不到 make() 的局部变量 |


### UnboundLocalError 是编译期就定下的判决

```python
def make(n):
    def reader():
        return n
    return reader

fs = [make(i) for i in range(3)]
print([f() for f in fs])

def counter():
    c = 0
    def bump():
        nonlocal c
        c += 1
        return c
    return bump

b = counter()
print(b(), b(), b())

def broken():
    print(x)
    x = 1
try:
    broken()
except UnboundLocalError as e:
    print(type(e).__name__, str(e))
```

<OutputBox title='对照写法：先自己猜，再点开' output='[0, 1, 2]\n1 2 3\nUnboundLocalError cannot access local variable &#39;x&#39; where it is not associated with a value' guess="true" />

<Predict no='030-P' q='print(inner.__code__.co_freevars, inner.__closure__[0].cell_contents) 对 outer 里的 inner 输出什么？' :options='["(&#39;x&#39;,) 10", "(&#39;x&#39;,) (&#39;x&#39;,)", "() 10"]' answer='0' output='(&#39;x&#39;,) 10' explain='co_freevars 是自由变量名元组；__closure__ 存的是 cell 对象，取 cell_contents 才得到当前值 10，而不是名字元组或 None。' />


## 闭包与 cell：捕获的是变量不是值

闭包等于函数加上它引用的自由变量环境。被内层函数引用的外层局部名字叫自由变量，编译器把它们放进 cell 对象：外层 code object 的 co_cellvars 列出自己创建供内层使用的 cell，内层的 co_freevars 列出引用的自由变量名；

运行时 `function.__closure__` 是与 co_freevars 顺序对应的 cell 元组，`cell.cell_contents` 是当前值，3.7 起还可写。

cell 是引用语义，内外层共用同一个 cell，内层读到的始终是此刻的 cell_contents，而不是定义那一刻的快照，这正是延迟绑定的根源。循环里创建的一批 lambda 引用同一个循环变量，共享同一个 cell，循环结束时 cell_contents 是最终值，于是所有函数行为一致，且没有任何运行时报错，排查成本很高。

修复有三条：默认参数捕获 `i=i`，因为默认表达式在每次 lambda 定义时求值，把当前值固化进一个新的 function 对象的 `__defaults__`，不再走 cell；工厂函数 `make(i)` 每调用一次就新建一层局部作用域与独立 cell；

`functools.partial(f, i)` 把值作为已绑定参数存进对象。

三者都把值从共享变量里复制出来。

```python
def build_bad():
    return [lambda: i for i in range(4)]

def build_good():
    return [lambda i=i: i for i in range(4)]

print([f() for f in build_bad()])
print([f() for f in build_good()])
print(build_bad()[0].__code__.co_freevars)
print(build_bad()[0].__closure__[0].cell_contents)
```

<OutputBox title='主示例运行结果' output='[3, 3, 3, 3]\n[0, 1, 2, 3]\n(&#39;i&#39;,)\n3' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def build_bad():\n    return [lambda: i for i in range(4)]\n\ndef build_good():\n    return [lambda i=i: i for i in range(4)]\n\nprint([f() for f in build_bad()])\nprint([f() for f in build_good()])\nprint(build_bad()[0].__code__.co_freevars)\nprint(build_bad()[0].__closure__[0].cell_contents)' :notes='["定义用推导式批量造 lambda 的函数", "四个 lambda 都读取同一个自由变量 i", "定义用默认参数捕获当前值的版本", "i=i 把每轮的 i 固化进各自 function 的 __defaults__", "坏版本四个函数都读到循环结束后的 i，全是 3", "好版本各自拿到 0、1、2、3", "坏版本 lambda 的 co_freevars 显示它捕获了自由变量 i", "__closure__[0].cell_contents 是共享 cell 的当前值 3"]' title='第 030 讲 · 作用域、LEGB 与闭包延迟绑定' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import dis, inspect

def outer():
    x = 10
    def inner():
        return x
    return inner

fn = outer()
cd = fn.__code__
print(cd.co_freevars, len(fn.__closure__))
print(fn.__closure__[0].cell_contents)
ops = [i.opname for i in dis.get_instructions(fn)]
print('LOAD_DEREF' in ops)
print(inspect.getclosurevars(fn).nonlocals)
```

<OutputBox title='原理验证' output='(&#39;x&#39;,) 1\n10\nTrue\n{&#39;x&#39;: 10}' />


### 从 co_freevars 到 cell 内容

CPython 里闭包靠 cell 对象实现。

编译阶段的符号表分析决定每个名字是 local、free 还是 global：若某名字在外层函数作用域被赋值、且被内层函数引用，编译器就为它分配一个 cell，外层 code object 的 co_cellvars 记录、内层 co_freevars 记录，并在 co_flags 置 CO_NESTED 标记嵌套函数。

运行时外层帧为这些 cell 分配 PyCellObject，内层 function 对象创建时把同一批 cell 打包进 `__closure__`（元组，顺序与 co_freevars 对应）；LOAD_DEREF 通过 cell 间接取值，STORE_DEREF 改写 cell_contents。

因为内外共享 cell 而非复制值，内层看到的始终是变量的最新状态，这就是延迟绑定。名字定型在编译期完成还解释了 UnboundLocalError：只要符号表把 x 判为局部，读取就编译成 LOAD_FAST，帧里该槽位尚未写入时触发异常，而不会退回去查全局。

默认参数捕获之所以有效，是它把当前值复制进了新函数的 `__defaults__`，与 cell 完全无关；工厂函数则是每次调用都新建帧与独立 cell。

<ConceptDiagram type='layers3' title='第 030 讲 · 分层视角' labels='LEGB 与赋值即局部：名字在编译期定型|闭包与 cell：捕获的是变量不是值|边界、失效信号与装饰器里的延迟绑定|cell 与闭包字节码' caption='边界、失效信号与装饰器里的延迟绑定' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **cell 与闭包字节码** 落在哪一层。


## 边界、失效信号与装饰器里的延迟绑定

写装饰器最易踩这一层：若在 for 循环里批量注册或包装函数，wrapper 引用的循环变量同样被共享，必须按上一节的思路固化。作用域还有两个容易误判的边界。其一，Python 3 的列表推导式有独立作用域，循环变量不泄漏到外层，而普通 for 循环没有独立作用域，这是延迟绑定在两类写法里表现不同的原因。

其二，class 语句体不参与外层函数的闭包：方法里引用外层函数的局部变量不会走 enclosing，而是按 global 查找，于是明明在 `make()` 里定义的变量，在类方法里却读不到，这是经典的失效信号。

判定工具很直接：`dis.dis` 看 LOAD_FAST / LOAD_GLOBAL / LOAD_DEREF / STORE_DEREF 就能判断名字被定型到哪一层；

`inspect.getclosurevars(fn)` 返回 nonlocals、globals、builtins、unbound 四个映射，一眼看清函数到底捕获了什么；

把 co_freevars 与 `__closure__` 对照还能读出每个 cell 的当前值。global 的代价是引入模块级可变状态、难以隔离测试，计数器这类封装状态更适合 nonlocal。

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：循环里 lambda 引用 i，全部返回最终", "body": "闭包共享同一个 cell，读到的是循环结束后的值，且没有任何报错", "tip": "用 lambda i=i: ... 把当前值固化，或用工厂函数 make(i) 造独立作用域"}, {"title": "第 2 步：函数里先 print(x) 再 x = 1 ", "body": "x 因函数内赋值被编译期判为局部，赋值前读取的槽位还是空的", "tip": "要改全局先声明 global x；要读外层用 nonlocal 或把值当参数传入；或先初始化再读取"}, {"title": "第 3 步：声明了 nonlocal 却报 Syntax", "body": "nonlocal 要求名字确实存在于某个外层函数作用域，模块全局或压根不存在都不行", "tip": "确认外层有该局部变量；模块级变量改用 global；或重构为传参与类属性"}]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 循环里 lambda 引用 i，全部返回最终值 | 闭包共享同一个 cell，读到的是循环结束后的值，且没有任何报错 | 用 lambda i=i: ... 把当前值固化，或用工厂函数 make(i) 造独立作用域 |
| 函数里先 print(x) 再 x = 1 抛 UnboundLocalError | x 因函数内赋值被编译期判为局部，赋值前读取的槽位还是空的 | 要改全局先声明 global x；要读外层用 nonlocal 或把值当参数传入；或先初始化再读取 |
| 声明了 nonlocal 却报 SyntaxError | nonlocal 要求名字确实存在于某个外层函数作用域，模块全局或压根不存在都不行 | 确认外层有该局部变量；模块级变量改用 global；或重构为传参与类属性 |

<Callout type="warn" title='本讲最容易踩的坑' text='循环里 lambda 引用 i，全部返回最终值：闭包共享同一个 cell，读到的是循环结束后的值，且没有任何报错' />


## 作用域机制的版本差异

**作用域机制的版本差异**

| 机制 | 版本 | 行为 | 对延迟绑定的影响 |
| --- | --- | --- | --- |
| nonlocal 关键字（PEP 3104） | 3.0 | 声明后写入最近的非全局外层 cell | 没有它时内层赋值只会新建局部变量 |
| 列表推导式独立作用域 | 3.0 | 推导式循环变量不泄漏到外层 | 普通 for 无独立作用域，是批量建函数的高发区 |
| UnboundLocalError 文案 | 3.11+ | cannot access local variable ... where it is not associated with a value | 3.10 及以前是 referenced before assignment |
| cell.cell_contents 可写 | 3.7+ | 可直接改写 cell 内容 | 早期只读；可用于测试注入 |
| inspect.getclosurevars | 3.3+ | 返回 nonlocals / globals / builtins / unbound | 一眼看清函数到底捕获了什么 |

<Term word='LEGB 查找顺序' text='名字查找顺序是 Local → Enclosing → Global → Built-in，四层都找不到才抛 NameError。关键在于作用域不是运行时逐行判断，而是编译期由符号表决定：只要函数体内任何地方给某名字赋值（含 +=、for 目标、with as、import、def / class 绑定），编译器就把它' />

<Term word='global 与 nonlocal' text='闭包等于函数加上它引用的自由变量环境。被内层函数引用的外层局部名字叫自由变量，编译器把它们放进 cell 对象：外层 code object 的 co_cellvars 列出自己创建供内层使用的 cell，内层的 co_freevars 列出引用的自由变量名；运行时 function.__closure__ 是与 co' />

<FlowTimeline :steps='[{"title": "LEGB 与赋值即局部：名字在编译期定型", "desc": "名字查找顺序是 Local → Enclosing → Global → Built…", "tone": "blue"}, {"title": "闭包与 cell：捕获的是变量不是值", "desc": "闭包等于函数加上它引用的自由变量环境。被内层函数引用的外层局部名字叫自由变量，编译器…", "tone": "purple"}, {"title": "边界、失效信号与装饰器里的延迟绑定", "desc": "写装饰器最易踩这一层：若在 for 循环里批量注册或包装函数，wrapper 引用的…", "tone": "orange"}, {"title": "工程落地", "desc": "工厂函数造闭包：带状态的校验器与计数器", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 循环里批量创建函数的三种写法

**循环里批量创建函数的三种写法**

| 写法 | 结果 | 原因 | 适用场景 |
| --- | --- | --- | --- |
| [lambda: i for i in range(4)] | [3, 3, 3, 3] | 四个函数共享同一个 cell，读到循环结束后的值 | 错误示范 |
| [lambda i=i: i for i in range(4)] | [0, 1, 2, 3] | 默认参数每次定义时求值并固化进新 function | 最简洁，回调允许额外参数 |
| [make(i) for i in range(4)] | [0, 1, 2, 3] | 每次调用工厂函数新建一层局部作用域与独立 cell | 回调签名必须固定 |
| [functools.partial(f, i) ...] | 各自固化 i | partial 把值作为已绑定位置参数存进对象 | 已有命名函数、需可 pickle 的回调 |

<Compare :panels='[{"label": "主示例", "code": "def build_bad():\n    return [lambda: i for i in range(4)]\n\ndef build_good():\n    return [lambda i=i: i for i in range(4)]\n\nprint([f() for f in build_bad()])\nprint([f() for f in build_good()])\nprint(build_bad()[0].__code__.co_freevars)\nprint(build_bad()[0].__closure__[0].cell_contents)", "note": "LEGB 与赋值即局部：名字在编译期定型"}, {"label": "对照 / 进阶", "code": "def make(n):\n    def reader():\n        return n\n    return reader\n\nfs = [make(i) for i in range(3)]\nprint([f() for f in fs])\n\ndef counter():\n    c = 0\n    def bump():\n        nonlocal c\n        c += 1\n        return c\n    return bump\n\nb = counter()\nprint(b(), b(), b())\n\ndef broken():\n    print(x)\n    x = 1\ntry:\n    broken()\nexcept UnboundLocalError as e:\n    print(type(e).__name__, str(e))", "note": "闭包与 cell：捕获的是变量不是值"}]' title='两种写法对照' note='差异集中在 LEGB 查找顺序；先看输出，再找背后的规则。' />


## 工厂函数造闭包：带状态的校验器与计数器

配置中心要按不同上限生成一批校验函数，还要给每个数据源配一个自增序号生成器。若在循环里直接写 lambda 引用 cap，所有校验器会用同一个最终上限；

正确做法是写一个工厂 `make_validator(limit)`，每次调用都新建一层局部作用域，limit 成为该层独立的 cell，返回的内层函数各自绑定自己的上限。

计数器同理：make_counter 里用 nonlocal 让内层 bump 改写外层 cell，状态被封装在闭包里而不污染模块全局。下面这段用标准库实现并验证：打印三个校验器对同一个值的判断、读出一个校验器 cell 的内容、以及计数器的连续调用结果和 co_cellvars，把捕获了什么变成可核对的证据。

```python
def make_validator(limit):
    def check(value):
        return 0 <= value <= limit
    return check

rules = {}
for name, cap in [('cpu', 100), ('mem', 512), ('disk', 2048)]:
    rules[name] = make_validator(cap)

print([(k, rules[k](50)) for k in rules])
print(rules['cpu'].__closure__[0].cell_contents)

def make_counter():
    n = 0
    def inc():
        nonlocal n
        n += 1
        return n
    return inc

calls = make_counter()
print(calls(), calls(), calls())
print(make_counter.__code__.co_cellvars)
```

<Callout type="idea" title='落地提示' text='用默认参数把值当场绑定，或用工厂函数制造新的作用域；写装饰器时尤其要注意这一层' />

<CheckList id='P030b' title='上线前自检' :items='["能复现并解释「循环里 lambda 引用 i，全部返回最终值」", "能复现并解释「函数里先 print(x) 再 x = 1 抛 Unboun」", "能复现并解释「声明了 nonlocal 却报 SyntaxError」", "能用一条命令验证 LEGB 查找顺序", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import inspect; print(inspect.signature(print))"
```

把输入换成你自己的数据，观察结果是否仍符合 **LEGB 查找顺序** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 用练习把 LEGB 刻进直觉

<Exercise title='基础：修复循环里的延迟绑定' task='分别实现 build_bad 与 build_fix，都返回 5 个计算 i*i 的函数，打印各自调用结果，解释差异来自 cell 还是 __defaults__。' solution='def build_bad():\n    return [lambda: i * i for i in range(5)]\n\ndef build_fix():\n    return [lambda i=i: i * i for i in range(5)]\n\nprint([f() for f in build_bad()])\nprint([f() for f in build_fix()])' explain='bad 的两个函数共享同一 cell、全返回 16；fix 用默认参数把每轮 i 复制进 __defaults__，得到 [0, 1, 4, 9, 16]。' />

<Exercise title='进阶：用 dis 区分三种名字定型' task='定义读局部变量、读全局变量、读闭包自由变量的三个函数，用 dis.get_instructions 打印各自涉及的 LOAD 类指令名集合，说明 LOAD_FAST / LOAD_GLOBAL / LOAD_DEREF 分别对应哪一层。' solution='import dis\nG = 1\n\ndef f_local():\n    x = 1\n    return x\n\ndef f_global():\n    return G\n\ndef outer():\n    x = 1\n    def inner():\n        return x\n    return inner\n\nfor fn in (f_local, f_global, outer()):\n    ops = sorted(set(i.opname for i in dis.get_instructions(fn) if i.opname.startswith(&#39;LOAD&#39;)))\n    print(fn.__code__.co_freevars, ops)' explain='局部名走 LOAD_FAST、模块名走 LOAD_GLOBAL、自由变量走 LOAD_DEREF（3.13 可能把相邻加载融合成 LOAD_FAST_LOAD_FAST，但定型层级不变）。' />

<Quiz no='030-1' q='[lambda: i for i in range(3)] 里三个函数的返回值是？' :options='["2, 2, 2（循环结束后的最终值）", "0, 1, 2", "抛 NameError", "0, 0, 0"]' answer="0" explain='三个 lambda 共享同一个 cell，读到的是循环结束后的 i=2；闭包捕获变量而非值，且没有任何异常。' />

<Quiz no='030-2' q='关于函数里先读后赋值触发 UnboundLocalError，正确解释是？' :options='["名字因函数内赋值被编译期判为局部，赋值前槽位为空", "全局变量被删除了", "LEGB 四层都查不到", "闭包 cell 被垃圾回收了"]' answer="0" explain='符号表在编译期就把 x 定型为局部并生成 LOAD_FAST，帧里该槽位未写入时就抛异常，不会回退去查全局。' />

<Quiz no='030-3' q='下面哪种修复能真正造出独立作用域？' :options='["每次调用工厂函数新建一层局部作用域与独立 cell", "把 j = i 放在同一个循环体里再引用 j", "用 global i 声明", "把 for 改成 while"]' answer="0" explain='同一作用域里的 j 每轮被重新赋值、仍是同一个变量；global 更糟。只有新作用域或把值复制进 __defaults__ / partial 才能固化。' />

<FillBlank no='030-F' tpl='___ build_bad():' :answers='["def"]' hint='回想本讲关于 LEGB 查找顺序 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 LEGB 与赋值即局部：名字在编译期定型 的落点。' />

<KnowledgeCard :points='["LEGB：Local → Enclosing → Global → Built-in；名字作用域由编译期符号表定型，不是运行时决定", "函数内任意处赋值就把名字判为局部，赋值前读取抛 UnboundLocalError（3.11+ 文案 cannot access local variable ...）", "global 走 LOAD_GLOBAL / STORE_GLOBAL；nonlocal（3.0+）走 LOAD_DEREF / STORE_DEREF，要求外层确有该绑定", "闭包自由变量存 cell：外层 co_cellvars、内层 co_freevars，__closure__ 是与 co_freevars 对应的 cell 元组", "延迟绑定根因是内外共享 cell 而非复制值；修复用默认参数 i=i、工厂函数或 functools.partial 固化当前值", "inspect.getclosurevars 返回 nonlocals / globals / builtins / unbound；class 作用域不参与外层函数闭包"]' :pitfalls='["循环里 lambda 引用 i，全部返回最终值", "函数里先 print(x) 再 x = 1 抛 UnboundLocalError", "声明了 nonlocal 却报 SyntaxError", "在循环里定义 lambda 直接引用循环变量，会得到一批行为完全相同的函数，且没有任何报错"]' summary='闭包捕获的是变量本身而不是当时的值，循环里创建的一批函数会一起看到循环结束后的最终值' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| LEGB：Local → Enclosing → Global → Built-in；名字作用域由编译期符号表定型，不是运行时决定 | 建立直觉 |
| 函数内任意处赋值就把名字判为局部，赋值前读取抛 UnboundLocalError（3.11+ 文案 cannot access local variable ...） | 跑通示例 |
| global 走 LOAD_GLOBAL / STORE_GLOBAL；nonlocal（3.0+）走 LOAD_DEREF / STORE_DEREF，要求外层确有该绑定 | 深入边界 |
| 闭包自由变量存 cell：外层 co_cellvars、内层 co_freevars，__closure__ 是与 co_freevars 对应的 cell 元组 | 工程落地 |
| 延迟绑定根因是内外共享 cell 而非复制值；修复用默认参数 i=i、工厂函数或 functools.partial 固化当前值 | 随堂检测 |
| inspect.getclosurevars 返回 nonlocals / globals / builtins / unbound；class 作用域不参与外层函数闭包 | 复盘 |

<CheckList id='P030a' title='学完你应当能' :items='["能讲清 LEGB 与赋值即局部：名字在编译期定型", "能讲清 闭包与 cell：捕获的是变量不是值", "能讲清 边界、失效信号与装饰器里的延迟绑定", "能在工程里处理 cell 与闭包字节码"]' />

1. LEGB：Local → Enclosing → Global → Built-in；名字作用域由编译期符号表定型，不是运行时决定

2. 函数内任意处赋值就把名字判为局部，赋值前读取抛 UnboundLocalError（3.11+ 文案 cannot access local variable ...）

3. global 走 LOAD_GLOBAL / STORE_GLOBAL；nonlocal（3.0+）走 LOAD_DEREF / STORE_DEREF，要求外层确有该绑定

[下一讲：高阶函数、lambda 与 map / filter / reduce](/functions/higher-order)
