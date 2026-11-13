---
title: 第 050 讲 · 字节码、栈式虚拟机与 dis 实战
description: 通过字节码验证语言层面的结论
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='40 分钟' goal='通过字节码验证语言层面的结论' prereq='第 049 讲 · CPython 编译流程：AST 到字节码' />

# 第 050 讲 · 字节码、栈式虚拟机与 dis 实战

上一讲把源码送到 code object，这一讲钻进去看指令怎么被执行。源码层说不清的「为什么」，到这层往往一眼明白；但离机器更近，结论会跟着解释器版本走，不能当成不变的规矩。

有团队把某版本的反汇编结论写成规范，升级后断言接连失败；也有人按局部变量去查闭包里读到的值，怎么都对不上。本讲先讲栈式指令里值怎么在栈上流动、LOAD 与 STORE 这类常见指令，再看闭包自由变量、推导式独立帧与异常表，最后谈版本演进与用 dis 现场验证。需要第 49 讲的编译流程、阶段三的闭包与第 3 讲的 dis；学完遇到诡异行为会先反汇编一小段，而不是背指令名。


## 一个「源码更短却更慢」的热路径争议

一段看似等价的代码，有人把 3.10 上的反汇编结论写成团队规范：说「加法一定对应 BINARY_ADD、调用一定对应 CALL_FUNCTION」，升级到 3.11 后所有断言全挂，CI 里报了一堆看不懂的指令名。

另一处排查更费时：闭包里读外部变量，有人按 LOAD_FAST 去找，怎么都对不上帧里的局部变量表，实际那条指令是 LOAD_DEREF，值存在 cell 里。还有人想在推导式里访问循环变量，按 Python 2 的经验以为变量会泄漏到外层，结果 3.x 里推导式有自己的作用域；

到了 3.12 又变了，推导式被内联、连独立帧都没有了。字节码是「为什么」最直接的证据层，但它随版本演进。本讲把栈式指令、闭包与自由变量、推导式帧、异常表以及 3.10 到 3.13 的关键变化逐条对齐，并给出用 dis 现场验证而不是背指令名的方法。

<Callout type="warn" title='先看一个真实会出错的写法' text='把 3.10 的 BINARY_ADD / CALL_FUNCTION 写成跨版本断言：3.11 起改为 BINARY_OP 与 CALL，3.12 又移除 PRECALL，指令集持续变化' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段五 · 核心机制与运行时 |
| 前置 | 第 049 讲 · CPython 编译流程：AST 到字节码 |
| 难度 / 建议时长 | ★★★★☆ · 40 分钟 |
| 本讲新增 | 栈式指令与 LOAD / STORE、常见指令速查、闭包与 LOAD_DEREF |
| 一句话目标 | 通过字节码验证语言层面的结论 |
| 为下一讲铺垫 | 帧、调用栈与命名空间 |


## 栈式虚拟机与常见指令：值在栈上流动

CPython 的 ceval 是基于栈的求值循环：每条指令从栈顶取操作数、把结果压回栈，函数名里的 LOAD / STORE / BINARY 就是这个意思。局部变量存在帧的 fast locals 数组里，LOAD_FAST / STORE_FAST 用数组索引直接读写，比查字典快；

全局与内置名字走 LOAD_GLOBAL，3.11 起指令带一个标志位，打印成 LOAD_GLOBAL 1 (NULL + print)，表示同时压入 NULL 与函数对象供 CALL 使用。常量走 LOAD_CONST，结果用 RETURN_VALUE 返回，表达式语句用 POP_TOP 丢弃。

二元运算在 3.11 起统一为 BINARY_OP 并带操作码参数（如 BINARY_OP 0 (+) 表示加），此前是 BINARY_ADD / BINARY_MULTIPLY 等分散指令；

函数调用在 3.11 起由 PRECALL + CALL 承担（3.12 移除 PRECALL，只留 CALL），此前是 CALL_FUNCTION / CALL_METHOD。

查指令不要靠记忆，用 `dis.dis(fn)`、`dis.get_instructions(fn)`、`dis.Bytecode(fn)` 与 `dis.show_code(fn)` 现场看；

co_stacksize 给出这帧需要的最大栈深度，能解释为什么某些表达式更费栈。

```python
import dis

def add(a, b):
    c = a + b
    return c
print('argcount', add.__code__.co_argcount)
print('varnames', add.__code__.co_varnames)
ops = [i.opname for i in dis.get_instructions(add)]
print('has load_fast', 'LOAD_FAST' in ops)
print('has store_fast', 'STORE_FAST' in ops)
print('has binary', any(o in ops for o in ('BINARY_OP', 'BINARY_ADD')))
print('has return', 'RETURN_VALUE' in ops)
def outer():
    x = 10
    def inner():
        return x
    return inner
inner = outer()
print('freevars', inner.__code__.co_freevars)
print('has LOAD_DEREF', 'LOAD_DEREF' in [i.opname for i in dis.get_instructions(inner)])
```

<OutputBox title='主示例运行结果' output='argcount 2\nvarnames (&#39;a&#39;, &#39;b&#39;, &#39;c&#39;)\nhas load_fast True\nhas store_fast True\nhas binary True\nhas return True\nfreevars (&#39;x&#39;,)\nhas LOAD_DEREF True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import dis\n\ndef add(a, b):\n    c = a + b\n    return c\nprint(&#39;argcount&#39;, add.__code__.co_argcount)\nprint(&#39;varnames&#39;, add.__code__.co_varnames)\nops = [i.opname for i in dis.get_instructions(add)]\nprint(&#39;has load_fast&#39;, &#39;LOAD_FAST&#39; in ops)\nprint(&#39;has store_fast&#39;, &#39;STORE_FAST&#39; in ops)\nprint(&#39;has binary&#39;, any(o in ops for o in (&#39;BINARY_OP&#39;, &#39;BINARY_ADD&#39;)))\nprint(&#39;has return&#39;, &#39;RETURN_VALUE&#39; in ops)\ndef outer():\n    x = 10\n    def inner():\n        return x\n    return inner\ninner = outer()\nprint(&#39;freevars&#39;, inner.__code__.co_freevars)\nprint(&#39;has LOAD_DEREF&#39;, &#39;LOAD_DEREF&#39; in [i.opname for i in dis.get_instructions(inner)])' :notes='["导入 dis，结论一律现场反汇编验证", "空行分隔导入与函数定义", "双参数函数，局部变量 c 也进 co_varnames", "加法是栈式二元运算，结果压回栈", "返回局部变量，触发 LOAD_FAST 与 RETURN_VALUE", "co_argcount 记录位置参数个数", "co_varnames 按参数与局部变量顺序排列", "取出该函数所有指令的 opname 列表", "局部变量读取对应 LOAD_FAST", "局部变量写入对应 STORE_FAST", "3.11 起是 BINARY_OP，3.10 及以前是 BINARY_ADD，故两者取其一判断", "函数以 RETURN_VALUE 结束", "定义外层函数制造闭包", "x 被内层引用，编译成 cell 变量", "内层函数读取自由变量 x", "返回内层函数对象，__closure__ 带上 cell", "拿到闭包函数", "co_freevars 列出自由变量名", "读自由变量走 LOAD_DEREF 而非 LOAD_FAST"]' title='第 050 讲 · 字节码、栈式虚拟机与 dis 实战' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='CPython 的 ceval 是基于栈的求值循环：每条指令从栈顶取操作数、把结果压回栈，函数名里的 LOAD / STORE / BINARY 就是这个意思。局部变量存在帧的 fast locals 数组里，LOAD_FAST / STORE_FAST 用数组索引直接读写，比查字典快；全局与内置名' />


## 常见栈式指令速查（含 3.11 变化）

**常见栈式指令速查（含 3.11 变化）**

| 指令 | 作用 | 版本说明 |
| --- | --- | --- |
| LOAD_FAST / STORE_FAST | 按索引读写 fast locals 数组 | 长期可用 |
| LOAD_CONST | 从 co_consts 取常量压栈 | 长期可用 |
| LOAD_GLOBAL | 查全局与内置字典 | 3.11 起带 NULL 标志位 |
| BINARY_OP n (op) | 二元运算，n 为操作码 | 3.11 起取代 BINARY_ADD 等 |
| CALL / PRECALL | 函数调用 | 3.11 起引入，3.12 移除 PRECALL |
| RETURN_VALUE / POP_TOP | 返回 / 丢弃栈顶 | 长期可用 |

<Term word='栈式指令与 LOAD / STORE' text='CPython 的 ceval 是基于栈的求值循环：每条指令从栈顶取操作数、把结果压回栈，函数名里的 LOAD / STORE / BINARY 就是这个意思。局部变量存在帧的 fast locals 数组里，LOAD_FAST / STORE_FAST 用数组索引直接读写，比查字典快；全局与内置名字走 LOAD_GL' />

<Term word='常见指令速查' text='闭包变量不在 fast locals 而在 cell 对象里：外层函数的局部变量被内层引用时，编译器把它标成 cell，函数对象的 __closure__ 持有这些 cell，内层读写走 LOAD_DEREF / STORE_DEREF，3.11 起还会在入口用 MAKE_CELL、COPY_FREE_VARS 准备。' />


## ceval 主循环如何逐条取指与压栈

ceval 是一个基于栈的大循环：每条字节码指令从求值栈取参数、把结果压回，帧里的 fast locals 数组让 LOAD_FAST 用整数索引直取局部变量，全局与内置则经 LOAD_GLOBAL 查字典。

3.11 的 PEP 659 让热点指令在运行时被替换为带内联缓存的特化版本（如针对两个 int 的 BINARY_OP），默认 dis 打印非特化形式，`adaptive=True` 才展开 QUICKEN 结果。

闭包变量的物理载体是 cell 对象：编译器把被内层引用的外层局部变量标为 cell，函数对象 `__closure__` 持有它，读写走 LOAD_DEREF/STORE_DEREF；co_freevars / co_cellvars 是这份映射的静态记录。

异常表把 try/except 的保护区间与处理器入口编码成 code object 里的跳转表，异常发生时按表跳转，正常路径不再执行 SETUP_FINALLY 之类指令，这就是「零成本异常」。推导式在 3.12 前是独立 code object 与独立帧，PEP 709 把它内联进外层函数以省掉建帧开销。

三类结构都落在编译器产物上，所以版本升级会直接改变可观测的字节码。

<ConceptDiagram type='flow3' title='第 050 讲 · 栈式虚拟机与常见指令：值在栈上流动' labels='栈式虚拟机与常见指令：值在栈上流动|闭包、推导式与异常表：三条容易看错的结构|版本演进与自适应特化：别把某个版本的字节码当' caption='通过字节码验证语言层面的结论' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 闭包、推导式与异常表：三条容易看错的结构

闭包变量不在 fast locals 而在 cell 对象里：外层函数的局部变量被内层引用时，编译器把它标成 cell，函数对象的 `__closure__` 持有这些 cell，内层读写走 LOAD_DEREF / STORE_DEREF，3.11 起还会在入口用 MAKE_CELL、COPY_FREE_VARS 准备。

co_freevars 与 co_cellvars 两个元组分别列出自由变量与 cell 变量，是判断闭包结构最省事的属性。

推导式在 3.12 之前会编译成独立的 code object（co_name 为 &lt;listcomp> / &lt;genexpr> / &lt;dictcomp>），运行时创建单独帧，因此循环变量不会泄漏到外层作用域；

3.12 的 PEP 709 把推导式内联进外层函数，消除帧创建开销，也不再有独立 code object，但变量仍不泄漏。异常处理在 3.11 之前靠 SETUP_FINALLY / SETUP_EXCEPT 块指令，无异常也要执行额外指令；

3.11 起改为 co_exceptiontable 里的「受保护区间 → 处理器」跳转表，实现零成本异常，dis 会额外打印一段 ExceptionTable。这三条结构在不同版本长得很不一样，读反汇编时先确认解释器版本。

```python
import dis, sys, inspect

def f(x):
    return x + 1
ins = [i.opname for i in dis.get_instructions(f)]
print('stack ins', [o for o in ins if o in ('LOAD_FAST', 'LOAD_CONST', 'RETURN_VALUE')])
print('has binary op', any(o in ins for o in ('BINARY_OP', 'BINARY_ADD')))
print('dis has adaptive', 'adaptive' in inspect.signature(dis.dis).parameters)
print('int bits positive', sys.int_info.bits_per_digit > 0)
print('stacksize positive', f.__code__.co_stacksize > 0)
```

<OutputBox title='原理验证' output='stack ins [&#39;LOAD_FAST&#39;, &#39;LOAD_CONST&#39;, &#39;RETURN_VALUE&#39;]\nhas binary op True\ndis has adaptive True（3.11+；3.10 为 False）\nint bits positive True\nstacksize positive True' />

```python
import dis

def comp(n):
    return [i * i for i in range(n)]
nested = [c.co_name for c in comp.__code__.co_consts if hasattr(c, 'co_name')]
print('nested code objects', nested)
print('has exceptiontable', hasattr(comp.__code__, 'co_exceptiontable'))
try:
    with open('nope-not-exist', 'r'):
        pass
except FileNotFoundError:
    print('caught in python')
```

<OutputBox title='对照写法：先自己猜，再点开' output='nested code objects []（3.12+ PEP 709 内联；3.11 及以前为 [&#39;&lt;listcomp&gt;&#39;]）\nhas exceptiontable True（3.11+；3.10 及以前为 False）\ncaught in python' guess="true" />


## 闭包 / 推导式 / 异常的 code 属性

**闭包 / 推导式 / 异常的 code 属性**

| 属性或现象 | 含义 | 判据 |
| --- | --- | --- |
| co_freevars | 本 code 引用的自由变量名元组 | 非空说明存在闭包 |
| co_cellvars | 被内层引用的 cell 变量名元组 | 外层函数上可查 |
| __closure__ | 函数持有的 cell 元组 | LOAD_DEREF 从这里取值 |
| co_consts 含 &lt;listcomp> | 推导式独立 code object | 3.12+ 内联后消失 |
| co_exceptiontable | 异常区间到处理器的跳转表 | 3.11+ 存在，替代 SETUP_FINALLY |
| co_stacksize | 求值栈最大深度 | 恒为正，表达式越复杂越大 |

<Compare :panels='[{"label": "主示例", "code": "import dis\n\ndef add(a, b):\n    c = a + b\n    return c\nprint(&#39;argcount&#39;, add.__code__.co_argcount)\nprint(&#39;varnames&#39;, add.__code__.co_varnames)\nops = [i.opname for i in dis.get_instructions(add)]\nprint(&#39;has load_fast&#39;, &#39;LOAD_FAST&#39; in ops)\nprint(&#39;has store_fast&#39;, &#39;STORE_FAST&#39; in ops)\nprint(&#39;has binary&#39;, any(o in ops for o in (&#39;BINARY_OP&#39;, &#39;BINARY_ADD&#39;)))\nprint(&#39;has return&#39;, &#39;RETURN_VALUE&#39; in ops)\ndef outer():\n    x = 10\n    def inner():\n        return x\n    return inner\ninner = outer()\nprint(&#39;freevars&#39;, inner.__code__.co_freevars)\nprint(&#39;has LOAD_DEREF&#39;, &#39;LOAD_DEREF&#39; in [i.opname for i in dis.get_instructions(inner)])", "note": "栈式虚拟机与常见指令：值在栈上流动"}, {"label": "对照 / 进阶", "code": "import dis\n\ndef comp(n):\n    return [i * i for i in range(n)]\nnested = [c.co_name for c in comp.__code__.co_consts if hasattr(c, &#39;co_name&#39;)]\nprint(&#39;nested code objects&#39;, nested)\nprint(&#39;has exceptiontable&#39;, hasattr(comp.__code__, &#39;co_exceptiontable&#39;))\ntry:\n    with open(&#39;nope-not-exist&#39;, &#39;r&#39;):\n        pass\nexcept FileNotFoundError:\n    print(&#39;caught in python&#39;)", "note": "闭包、推导式与异常表：三条容易看错的结构"}]' title='两种写法对照' note='差异集中在 栈式指令与 LOAD / STORE；先看输出，再找背后的规则。' />


## 版本演进与自适应特化：别把某个版本的字节码当规范

3.11 的 PEP 659 引入自适应特化解释器：热点指令（BINARY_OP、LOAD_GLOBAL、LOAD_ATTR、CALL 等）在运行时被替换为针对具体类型的特化版本并附带内联缓存，默认 dis 显示的是非特化形式，传 `dis.dis(fn, adaptive=True)` 才能看到 QUICKEN 后的特化指令与缓存条目。

3.12 继续调整 CALL 相关指令并内联推导式，3.13 在自由线程与 JIT 骨架方向上继续演进。因此同一段源码在 3.10、3.11、3.12、3.13 上的指令序列可能完全不同，把某个版本的 BINARY_ADD / CALL_FUNCTION 写进断言或文档，升级就会失效。

正确做法是三条：结论尽量落在跨版本稳定的事实（是否存在 LOAD_FAST / RETURN_VALUE、co_freevars 内容、co_stacksize 为正），把版本敏感的差异放进表格并注明范围，排查诡异行为时先对最小片段 dis 一下再决定是语言规则、编译优化还是库实现的问题。

性能热点也常在字节码层显形：Python 层循环对应大量指令，换成内置函数后帧里只剩一次 CALL。

<FlowTimeline :steps='[{"title": "栈式虚拟机与常见指令：值在栈上流动", "desc": "CPython 的 ceval 是基于栈的求值循环：每条指令从栈顶取操作数、把结果压…", "tone": "blue"}, {"title": "闭包、推导式与异常表：三条容易看错的结构", "desc": "闭包变量不在 fast locals 而在 cell 对象里：外层函数的局部变量被内…", "tone": "purple"}, {"title": "版本演进与自适应特化：别把某个版本的字节码当规范", "desc": "3.11 的 PEP 659 引入自适应特化解释器：热点指令（BINARY_OP、L…", "tone": "orange"}, {"title": "工程落地", "desc": "用 dis 证明「源码短不等于指令少」", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

**版本间字节码与结构差异**

| 版本 | 变化 | 排查提示 |
| --- | --- | --- |
| 3.10 及以前 | BINARY_ADD、CALL_FUNCTION、SETUP_FINALLY、co_lnotab | 老文章的指令结论多基于这一版 |
| 3.11 | BINARY_OP、CALL、异常表 co_exceptiontable、MAKE_CELL/COPY_FREE_VARS、自适应特化 PEP 659 | dis 默认不显示特化，需 adaptive=True |
| 3.12 | PEP 709 内联推导式、移除 PRECALL | co_consts 里不再有 &lt;listcomp> 独立 code object |
| 3.13 | 自由线程构建与 JIT 骨架继续演进 | 性能与指令结论按构建分别测 |
| 推导式作用域 | 3.x 起变量不泄漏到外层 | 3.12 前后帧结构不同但作用域规则一致 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把 3.10 的 BINARY_ADD / ", "body": "3.11 起改为 BINARY_OP 与 CALL，3.12 又移除 PRECALL，指令集持续变化", "tip": "结论落在跨版本稳定的事实上（co_freevars、co_stacksize 为正、是否存在 LOAD_FAST），版本敏感项在输出里注明范围，用目标版本 dis 现场验证"}, {"title": "第 2 步：按 Python 2 经验以为推导式变量会泄", "body": "3.x 推导式有自己的作用域；3.12 的 PEP 709 又把它内联、去掉 &lt;listcomp&gt; 独立帧", "tip": "用 co_consts 里是否含 &lt;listcomp&gt; 与 dis 结果判断具体版本行为，别把帧结构当语言规则"}, {"title": "第 3 步：只看源码行数评估热路径性能", "body": "源码短不等于指令少，Python 层循环对应大量字节码，内置函数常只剩一次 CALL", "tip": "先 dis 最小片段，再用 perf_counter 计时；把循环下沉到 C 实现或内置聚合才是有效优化"}]' />


## 用 dis 证明「源码短不等于指令少」

聚合函数有两种写法：Python 层 for 循环累加，与直接调用内置 sum。源码行数差不多，但前者每轮迭代都要执行一批 LOAD_FAST / BINARY_OP / STORE_FAST 加跳转，后者帧里基本只剩一次对 sum 的调用。

用 `dis.get_instructions` 统计过滤掉 CACHE、RESUME 等噪声后的指令数做对比，并顺带检查该 code object 用的是异常表还是旧行号表，就能把「为什么内置更快」从印象变成证据。

下面用标准库跑通，只打印布尔结论与 co_names，避免把随版本变化的指令数字写死。要点是：性能判断要落到字节码与计时，而不是源码长度；这类结论在排查诡异行为与热路径优化时都可复用。

```python
import dis

def loop_sum(xs):
    total = 0
    for x in xs:
        total += x
    return total

def builtin_sum(xs):
    return sum(xs)

def count(fn):
    return len([i for i in dis.get_instructions(fn) if i.opname not in ('CACHE', 'RESUME')])

print('loop heavier', count(loop_sum) > count(builtin_sum))
print('loop names', loop_sum.__code__.co_names)
print('builtin names', builtin_sum.__code__.co_names)
print('has line table', hasattr(loop_sum.__code__, 'co_linetable') or hasattr(loop_sum.__code__, 'co_lnotab'))
```

<Callout type="idea" title='落地提示' text='排查诡异行为时先 dis 一小段，再决定是语言规则、优化还是库的问题；性能热点也常在这里显形' />

<CheckList id='P050b' title='上线前自检' :items='["能复现并解释「把 3.10 的 BINARY_ADD / CALL_FUN」", "能复现并解释「按 Python 2 经验以为推导式变量会泄漏到外层，或以为」", "能复现并解释「只看源码行数评估热路径性能」", "能用一条命令验证 栈式指令与 LOAD / STORE", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import dis; dis.dis(lambda x: x+1)"
```

把输入换成你自己的数据，观察结果是否仍符合 **栈式指令与 LOAD / STORE** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把 3.10 的 BINARY_ADD / CALL_FUNCTION 写成跨版本断言 | 3.11 起改为 BINARY_OP 与 CALL，3.12 又移除 PRECALL，指令集持续变化 | 结论落在跨版本稳定的事实上（co_freevars、co_stacksize 为正、是否存在 LOAD_FAST），版本敏感项在输出里注明范围，用目标版本 dis 现场验证 |
| 按 Python 2 经验以为推导式变量会泄漏到外层，或以为 3.12 仍有独立帧 | 3.x 推导式有自己的作用域；3.12 的 PEP 709 又把它内联、去掉 &lt;listcomp> 独立帧 | 用 co_consts 里是否含 &lt;listcomp> 与 dis 结果判断具体版本行为，别把帧结构当语言规则 |
| 只看源码行数评估热路径性能 | 源码短不等于指令少，Python 层循环对应大量字节码，内置函数常只剩一次 CALL | 先 dis 最小片段，再用 perf_counter 计时；把循环下沉到 C 实现或内置聚合才是有效优化 |

<Callout type="warn" title='本讲最容易踩的坑' text='把 3.10 的 BINARY_ADD / CALL_FUNCTION 写成跨版本断言：3.11 起改为 BINARY_OP 与 CALL，3.12 又移除 PRECALL，指令集持续变化' />


## 靠字节码下结论

<Exercise title='基础：用 co_freevars 与 dis 定位闭包变量' task='写一个外层函数返回引用其局部变量的内层函数，打印内层 __code__.co_freevars 与外层 co_cellvars，并用 dis 确认内层用的是 LOAD_DEREF 而非 LOAD_FAST。' solution='import dis\ndef outer():\n    x = 7\n    def inner():\n        return x + 1\n    return inner\nf = outer()\nprint(f.__code__.co_freevars, outer.__code__.co_cellvars)\nprint(&#39;LOAD_DEREF&#39; in [i.opname for i in dis.get_instructions(f)])' explain='被内层引用的 x 成为 cell 变量：外层 co_cellvars 含 &#39;x&#39;，内层 co_freevars 含 &#39;x&#39;，读它走 LOAD_DEREF，值来自函数对象的 __closure__。' />

<Exercise title='进阶：对比 3.11 前后指令名并做跨版本稳定断言' task='对同一函数分别检查 BINARY_OP / BINARY_ADD、CALL / CALL_FUNCTION 是否存在，把结果整理成「任一命中即通过」的布尔断言，说明为什么这样写升级解释器后不会挂。' solution='import dis\ndef g(a, b):\n    return a * b + len([])\nops = [i.opname for i in dis.get_instructions(g)]\nprint(&#39;binary present&#39;, any(o in ops for o in (&#39;BINARY_OP&#39;, &#39;BINARY_ADD&#39;, &#39;BINARY_MULTIPLY&#39;)))\nprint(&#39;call present&#39;, any(o in ops for o in (&#39;CALL&#39;, &#39;CALL_FUNCTION&#39;, &#39;CALL_METHOD&#39;)))\nprint(&#39;returns&#39;, &#39;RETURN_VALUE&#39; in ops)' explain='把结论写成「一组等价指令任一命中」，3.10 的 BINARY_ADD/CALL_FUNCTION 与 3.11+ 的 BINARY_OP/CALL 都能通过；RETURN_VALUE 跨版本稳定，适合做硬断言。' />

<Quiz no='050-1' q='闭包里读取外层变量对应哪条指令？' :options='["LOAD_DEREF，值来自 __closure__ 的 cell", "LOAD_FAST，值在 fast locals 数组", "LOAD_GLOBAL，值在模块字典", "LOAD_CONST，值在 co_consts"]' answer="0" explain='被内层引用的外层局部变量被编译成 cell，函数对象 __closure__ 持有它，内层读写走 LOAD_DEREF/STORE_DEREF；co_freevars 列出这些自由变量名。' />

<Quiz no='050-2' q='关于 3.12 的推导式，正确的是？' :options='["PEP 709 把推导式内联进外层函数，co_consts 里不再有 &lt;listcomp&gt; 独立 code object", "推导式变量开始泄漏到外层", "推导式改用 CALL_FUNCTION", "推导式不再支持 if 过滤"]' answer="0" explain='3.12 的 PEP 709 内联推导式以省掉建帧开销，独立 code object 消失，但循环变量仍不泄漏到外层作用域；3.11 及以前 co_consts 里可见 &lt;listcomp&gt;。' />

<Quiz no='050-3' q='3.11 起异常处理的机制是？' :options='["co_exceptiontable 里的区间到处理器跳转表，正常路径零额外指令", "SETUP_FINALLY 块指令，每条路径都执行", "try 语句被编译成函数调用", "异常由 GIL 统一捕获"]' answer="0" explain='3.11 用异常表实现零成本异常处理：正常路径不执行 SETUP_FINALLY 之类指令，异常发生时按表跳转；dis 会额外打印一段 ExceptionTable。' />

<Predict no='050-P' q='dis.dis(lambda: 1 + 2) 最可能看到哪组指令？' :options='["LOAD_CONST 加 RETURN_VALUE（3.12 起为 RETURN_CONST），总之没有加法指令", "LOAD_FAST 加 BINARY_OP 加 RETURN_VALUE", "BINARY_ADD 加 STORE_FAST 加 RETURN_VALUE"]' answer='0' output='3.11 及以前：LOAD_CONST 0 (3) / RETURN_VALUE（另含 RESUME）；3.12 起：RETURN_CONST 0 (3)' explain='1+2 在编译期被常量折叠成 3 存进 co_consts，运行时没有加法指令；3.12 起对常量返回还会改用 RETURN_CONST 直接返回结果。这正是常量折叠发生在编译期而非运行期的直接证据。' />

<FillBlank no='050-F' tpl='___ dis' :answers='["import"]' hint='回想本讲关于 栈式指令与 LOAD / STORE 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 栈式虚拟机与常见指令：值在栈上流动 的落点。' />

<KnowledgeCard :points='["ceval 是基于栈的求值循环；LOAD_FAST 走 fast locals 数组，LOAD_GLOBAL 查全局与内置字典", "3.11 起二元运算统一为 BINARY_OP 带操作码参数，调用改 CALL，取代 BINARY_ADD/CALL_FUNCTION", "闭包变量存 cell：co_freevars / co_cellvars 记录映射，读写走 LOAD_DEREF，值来自 __closure__", "推导式 3.12 前是独立 &lt;listcomp&gt; 帧；PEP 709（3.12）内联后不再有独立 code object", "3.11 起用 co_exceptiontable 异常表实现零成本异常，取代 SETUP_FINALLY 块指令", "PEP 659 自适应特化需 dis(..., adaptive=True) 才可见；结论落在跨版本稳定事实上，别背指令名"]' :pitfalls='["把 3.10 的 BINARY_ADD / CALL_FUNCTION 写成跨版本断言", "按 Python 2 经验以为推导式变量会泄漏到外层，或以为 3.12 仍有独立帧", "只看源码行数评估热路径性能", "拿某一版本的字节码当语言规范，升级解释器后结论可能失效"]' summary='很多「为什么」在字节码层面一眼就能看清：闭包变量走 LOAD_DEREF、推导式有自己的帧、+= 先做 BINARY_OP 再 STORE' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| ceval 是基于栈的求值循环；LOAD_FAST 走 fast locals 数组，LOAD_GLOBAL 查全局与内置字典 | 建立直觉 |
| 3.11 起二元运算统一为 BINARY_OP 带操作码参数，调用改 CALL，取代 BINARY_ADD/CALL_FUNCTION | 跑通示例 |
| 闭包变量存 cell：co_freevars / co_cellvars 记录映射，读写走 LOAD_DEREF，值来自 __closure__ | 深入边界 |
| 推导式 3.12 前是独立 &lt;listcomp> 帧；PEP 709（3.12）内联后不再有独立 code object | 工程落地 |
| 3.11 起用 co_exceptiontable 异常表实现零成本异常，取代 SETUP_FINALLY 块指令 | 随堂检测 |
| PEP 659 自适应特化需 dis(..., adaptive=True) 才可见；结论落在跨版本稳定事实上，别背指令名 | 复盘 |

1. ceval 是基于栈的求值循环；LOAD_FAST 走 fast locals 数组，LOAD_GLOBAL 查全局与内置字典

2. 3.11 起二元运算统一为 BINARY_OP 带操作码参数，调用改 CALL，取代 BINARY_ADD/CALL_FUNCTION

3. 闭包变量存 cell：co_freevars / co_cellvars 记录映射，读写走 LOAD_DEREF，值来自 __closure__

[下一讲：帧、调用栈与命名空间](/core/frames)
