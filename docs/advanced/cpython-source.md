---
title: 第 114 讲 · CPython 源码：对象、帧与求值循环
description: 能沿着源码读懂一条语句的执行
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='50 分钟' goal='能沿着源码读懂一条语句的执行' prereq='第 113 讲 · 安全工程：依赖、注入、序列化与密钥' />

# 第 114 讲 · CPython 源码：对象、帧与求值循环

到上一讲为止，我们一直在往外看：服务怎么协同、怎么部署、怎么守边界。从这里镜头调转，回到一台机器上，问个更里层的问题——一行代码到底怎么被执行。之前靠 dis 看字节码、靠现象推结论，遇到版本说法打架总隔着一层；现在可以去看实现，把现象对到具体结构上。

本讲先认清 CPython 源码目录的分工，再从 PyObject 出发，看 code object、帧与 3.11 后的变化，最后走进 ceval 求值循环，用 dis 对照。需要对象模型、字节码与一点读 C 的耐心；学完你能沿 CPython 源码把一次属性查找落到实处，也明白旧结论为何失效。


## 照 3.9 的博客结论优化属性访问，为什么失效

一个工程师想弄清 `self.x = 1` 到底慢在哪，翻了几篇博客，结论互相矛盾：有的说属性查找查字典，有的说 3.11 之后有内联缓存，还有的贴出 LOAD_ATTR 后面跟着一串看不懂的 CACHE。

照着旧文章去优化，把属性改成本地变量，实测却没有提升，因为那篇文章基于 3.9 的字节码，而线上跑的是 3.13，指令名、帧结构、异常处理都已经变过。另一个困惑是调试器里看到的 frame 对象，和自己用 `sys._getframe` 拿到的东西对不上，不知道 3.11 之后帧大部分不再为每次调用分配 PyObject。

读源码的目标不是背文件名，而是把一条语言现象精确映射到具体的 C 函数、数据结构与字节码指令，并且知道这个映射随哪个版本改变。本讲沿 ceval 的求值循环把对象、帧与指令三层串起来。

<Callout type="warn" title='先看一个真实会出错的写法' text='照 3.9 的博客结论优化属性访问：3.11 起有自适应特化与内联缓存、3.13 有超级指令，指令序列与开销模型都变了，旧结论失效' />

<CheckList id='P114a' title='学完你应当能' :items='["能讲清 CPython 源码布局与 PyObject / PyTypeObject", "能讲清 code object、帧与 3.11 之后的帧重构", "能讲清 ceval 求值循环、dis 与 3.13 超级指令", "能在工程里处理 调试构建与 gdb"]' />


## CPython 源码布局与 PyObject / PyTypeObject

CPython 源码按职责分目录：Include/ 放公共头文件（`object.h` 定义 PyObject 与 PyTypeObject），Objects/ 放各内置类型的实现（`dictobject.c`、`listobject.c`、`typeobject.c`），Python/ 放解释器核心（`ceval.c`、`pystate.c`、`frame.c`、`import.c`），Modules/ 放标准库 C 模块，Lib/ 是纯 Python 标准库。

所有值在 C 层都是 PyObject：结构体开头是 ob_refcnt（引用计数，Py_ssize_t）与 ob_type（指向 PyTypeObject 的指针），类型对象本身也是 PyObject，其 tp_as_number / tp_as_sequence / tp_as_mapping 三张槽表决定 +、[]、in 等操作的实际行为，这就是同一条 BINARY_OP 在运行时分派到整数加法或字符串拼接的机制。

Py_INCREF / Py_DECREF 是直接改 ob_refcnt 的宏，引用计数归零即调用 tp_dealloc。

理解对象头，才能解释为什么 `sys.getrefcount` 的返回值要比实际引用数多 1（函数调用时参数本身持有一个临时引用），以及为什么 bool 是 int 的子类、type 的类型还是 type。

**CPython 源码目录与职责**

| 路径 | 职责 | 代表文件 |
| --- | --- | --- |
| Include/ | 公共头文件与对象结构 | object.h 定义 PyObject / PyTypeObject |
| Objects/ | 内置类型实现 | dictobject.c、listobject.c、typeobject.c |
| Python/ | 解释器核心 | ceval.c、pystate.c、frame.c、bytecodes.c |
| Modules/ | C 实现的标准库模块 | _json.c、_io 等 |
| Lib/ | 纯 Python 标准库 | importlib、asyncio |

<ConceptDiagram type='layers3' title='第 114 讲 · 分层视角' labels='CPython 源码布局与 PyObje|code object、帧与 3.11 |ceval 求值循环、dis 与 3.1|调试构建与 gdb' caption='ceval 求值循环、dis 与 3.13 超级指令' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **调试构建与 gdb** 落在哪一层。


## PyObject 头里的 ob_refcnt 与 ob_type

CPython 把每个值表示为堆上的 PyObject，头部两个字段 ob_refcnt 与 ob_type 分别支撑引用计数生命周期与运行时类型分派；PyTypeObject 里的 tp_as_number 等槽表让 BINARY_OP 在 ceval 中通过类型指针间接调用具体 C 函数，这是鸭子类型在机器层的实现。

一次函数调用会创建帧并压入线程状态的帧栈，字节码在 _PyEval_EvalFrameDefault 的栈式循环里执行：LOAD_FAST 从 localsplus 数组取局部变量，BINARY_OP 弹出两个操作数、按类型分派、把结果压回，RETURN_VALUE 弹栈返回。

3.11 起帧从每次调用的 PyObject 改为内联的 _PyInterpreterFrame，按需才物化 PyFrameObject，减少堆分配；同一版本还把异常处理从基于块字节码改成 co_exceptiontable 的零成本表。3.13 进一步用超级指令把相邻的 LOAD_FAST 合并，减少分派次数。

`sys.getrefcount` 比真实引用多 1，是因为实参传入函数时形参持有一次临时引用，减去它才能看到对象自身的引用数，这正是对象头引用计数可直接观测的证据。

<Term word='源码目录结构' text='CPython 源码按职责分目录：Include/ 放公共头文件（object.h 定义 PyObject 与 PyTypeObject），Objects/ 放各内置类型的实现（dictobject.c、listobject.c、typeobject.c），Python/ 放解释器核心（ceval.c、pystate.' />

<Term word='PyObject 与类型对象' text='编译产物是 PyCodeObject，字段可通过 __code__ 读取：co_code 是字节码字节串，co_consts 是常量元组（含嵌套 code object），co_names 是全局/属性名元组，co_varnames 是局部变量名，co_stacksize 是求值栈最大深度，co_flags 编码参数与' />


## code object、帧与 3.11 之后的帧重构

编译产物是 PyCodeObject，字段可通过 `__code__` 读取：co_code 是字节码字节串，co_consts 是常量元组（含嵌套 code object），co_names 是全局/属性名元组，co_varnames 是局部变量名，co_stacksize 是求值栈最大深度，co_flags 编码参数与生成器标志，3.11 起新增 co_exceptiontable 用异常表替代旧的 SETUP_FINALLY 块实现零成本异常。

函数被调用时创建帧：3.11 之前每次调用都分配一个 PyFrameObject（含 f_back、f_locals、f_lasti），3.11 起改为内联的 _PyInterpreterFrame，存放在线程状态的帧栈上，真正的 PyFrameObject 只在 `sys._getframe` 或回溯需要时懒创建，这显著降低调用开销。

`sys._getframe(depth)` 的 `depth=0` 是当前帧，1 是调用者帧，读 `f_code.co_name` 得到函数名，f_lasti 是上一条执行指令的字节偏移，f_locals 在 3.13 起由 PEP 667 改为写时同步回局部变量，不再是 3.12 及以前那份可能过期的快照字典。

**PyCodeObject 关键字段**

| 字段 | 含义 | 示例（add 函数） |
| --- | --- | --- |
| co_code | 字节码字节串 | 3.13 下长度 10 |
| co_consts | 常量元组 | (None,) |
| co_names | 全局与属性名 | 空元组 |
| co_varnames | 局部变量名 | ('a', 'b') |
| co_stacksize | 求值栈最大深度 | 2 |
| co_exceptiontable | 3.11+ 零成本异常表 | 以字节编码的异常处理范围 |


## 用 sys.getrefcount 的原始返回值当作对象引用数

<Callout type="warn" title='本讲最容易踩的坑' text='照 3.9 的博客结论优化属性访问：3.11 起有自适应特化与内联缓存、3.13 有超级指令，指令序列与开销模型都变了，旧结论失效' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：照 3.9 的博客结论优化属性访问", "body": "3.11 起有自适应特化与内联缓存、3.13 有超级指令，指令序列与开销模型都变了，旧结论失效", "tip": "先确认解释器版本，用 dis.dis 在当前环境反汇编，必要时对预热前后分别计时，再决定改不改写法"}, {"title": "第 2 步：用 sys.getrefcount 的原始返", "body": "函数调用时实参本身持有一个临时引用，返回值比真实引用数多 1，直接解读会多算一个引用", "tip": "需要真实引用数时对结果减 1；观察别名增减用两次读数的差值更可靠"}, {"title": "第 3 步：以为每个函数调用都有一个常驻的 PyFram", "body": "3.11 起帧内联为 _PyInterpreterFrame，PyFrameObject 只在 sys._getframe 或回溯时懒创建", "tip": "读帧相关源码先确认版本；用 sys._getframe(depth) 取帧，理解 3.13 起 f_locals 由 PEP 667 改为写时同步"}]' />


## ceval 求值循环、dis 与 3.13 超级指令

字节码由 Python/`ceval.c` 的 _PyEval_EvalFrameDefault 在栈式虚拟机里逐条执行，3.11 起该函数主体实际由 Python/`bytecodes.c` 的 DSL 经生成器产出，配合专门化解释器把热点指令改写成带内联缓存的特化版本。

`dis.dis` 反汇编到的是未特化的 co_code，`show_caches=True` 会显示二进制算子后面的 CACHE 条目（内联缓存槽）。

3.13 引入超级指令把常见配对合并：例如 `add(a, b)`: return a + b 里的两个 LOAD_FAST 合并成 LOAD_FAST_LOAD_FAST，BINARY_OP 0 (+) 紧跟 RETURN_VALUE，co_code 长度相应变短。

用 compile(src, name, 'exec') 可拿到 code object 检查 co_consts，用 dis 能看到 LOAD_FAST / LOAD_CONST / BINARY_OP / RETURN_VALUE 的栈操作序列。

读源码的正确方法是拿调试构建（./`configure --with-pydebug`）加 gdb/lldb 在 _PyEval_EvalFrameDefault 下断点，单步跟踪一个小函数并对照 dis 输出，而不是通读整个文件；

版本差异必须先确认，否则旧文章的指令级结论会完全失效。

```python
import sys, dis

def add(a, b):
    return a + b

co = add.__code__
print('name', co.co_name)
print('varnames', co.co_varnames)
print('consts', co.co_consts)
print('names', co.co_names)
print('stacksize', co.co_stacksize)
print('bytecode_len', len(co.co_code))

def caller_name():
    return sys._getframe(1).f_code.co_name

print('caller', caller_name())
print('result', add(2, 3))
dis.dis(add)
```

<OutputBox title='主示例运行结果' output='name add\nvarnames (&#39;a&#39;, &#39;b&#39;)\nconsts (None,)\nnames ()\nstacksize 2\nbytecode_len 10\ncaller &lt;module&gt;\nresult 5\n  3           RESUME                   0\n\n  4           LOAD_FAST_LOAD_FAST      1 (a, b)\n              BINARY_OP                0 (+)\n              RETURN_VALUE' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys, dis\n\ndef add(a, b):\n    return a + b\n\nco = add.__code__\nprint(&#39;name&#39;, co.co_name)\nprint(&#39;varnames&#39;, co.co_varnames)\nprint(&#39;consts&#39;, co.co_consts)\nprint(&#39;names&#39;, co.co_names)\nprint(&#39;stacksize&#39;, co.co_stacksize)\nprint(&#39;bytecode_len&#39;, len(co.co_code))\n\ndef caller_name():\n    return sys._getframe(1).f_code.co_name\n\nprint(&#39;caller&#39;, caller_name())\nprint(&#39;result&#39;, add(2, 3))\ndis.dis(add)' :notes='["导入 sys 读取帧，dis 反汇编字节码", "定义最小函数用于观察 code object", "函数体只有一次加法与返回", "取出函数的 PyCodeObject", "co_name 是函数名", "co_varnames 列出局部变量名", "co_consts 只有隐式返回的 None，加法常量在指令里", "co_names 为空，函数未引用任何全局或属性名", "co_stacksize 为 2，两个操作数同时在栈上", "3.13 超级指令让 co_code 只有 10 字节", "sys._getframe(1) 取调用者帧", "返回调用者帧的函数名", "从模块级调用，调用者是 &lt;module&gt;", "执行函数确认结果为 5", "反汇编，3.13 把两个 LOAD_FAST 合成 LOAD_FAST_LOAD_FAST"]' title='第 114 讲 · CPython 源码：对象、帧与求值循环' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 对照：show_caches 与 adaptive 下的反汇编输出

```python
import dis

def f():
    return 1 + 2

def g(x):
    return x + 2

print('f_consts', f.__code__.co_consts)
print('g_consts', g.__code__.co_consts)
print('f_nbytes', len(f.__code__.co_code))
print('g_nbytes', len(g.__code__.co_code))
```

<OutputBox title='对照写法：先自己猜，再点开' output='f_consts (None, 3)\ng_consts (None, 2)\nf_nbytes 4\ng_nbytes 12' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import sys, dis\n\ndef add(a, b):\n    return a + b\n\nco = add.__code__\nprint(&#39;name&#39;, co.co_name)\nprint(&#39;varnames&#39;, co.co_varnames)\nprint(&#39;consts&#39;, co.co_consts)\nprint(&#39;names&#39;, co.co_names)\nprint(&#39;stacksize&#39;, co.co_stacksize)\nprint(&#39;bytecode_len&#39;, len(co.co_code))\n\ndef caller_name():\n    return sys._getframe(1).f_code.co_name\n\nprint(&#39;caller&#39;, caller_name())\nprint(&#39;result&#39;, add(2, 3))\ndis.dis(add)", "note": "CPython 源码布局与 PyObject / PyTypeObject"}, {"label": "对照 / 进阶", "code": "import dis\n\ndef f():\n    return 1 + 2\n\ndef g(x):\n    return x + 2\n\nprint(&#39;f_consts&#39;, f.__code__.co_consts)\nprint(&#39;g_consts&#39;, g.__code__.co_consts)\nprint(&#39;f_nbytes&#39;, len(f.__code__.co_code))\nprint(&#39;g_nbytes&#39;, len(g.__code__.co_code))", "note": "code object、帧与 3.11 之后的帧重构"}]' title='两种写法对照' note='差异集中在 源码目录结构；先看输出，再找背后的规则。' />

```python
import sys, dis

x = [1, 2, 3]
print('rc_start', sys.getrefcount(x) - 1)
y = x
print('rc_alias', sys.getrefcount(x) - 1)
y = 0
print('rc_unbind', sys.getrefcount(x) - 1)

def scale(a):
    return a * 2

print('consts', scale.__code__.co_consts)
print('names', scale.__code__.co_names)
dis.dis(scale)
```

<OutputBox title='原理验证' output='rc_start 1\nrc_alias 2\nrc_unbind 1\nconsts (None, 2)\nnames ()\n 10           RESUME                   0\n\n 11           LOAD_FAST                0 (a)\n              LOAD_CONST               1 (2)\n              BINARY_OP                5 (*)\n              RETURN_VALUE' />

**版本差异对源码阅读的影响**

| 版本 | 变化 | 对结论的影响 |
| --- | --- | --- |
| 3.10 及以前 | 每次调用分配 PyFrameObject | 旧文章的帧开销结论基于此 |
| 3.11 (PEP 659) | 自适应特化、异常表、内联 _PyInterpreterFrame | dis 与 ceval 结构大改 |
| 3.12 (PEP 684) | 每解释器 GIL | 线程与子解释器结论需区分 |
| 3.13 | 超级指令如 LOAD_FAST_LOAD_FAST、实验自由线程 | 旧反汇编输出不再匹配 |


## 把一条语句映射到 code object、帧与字节码的追踪器

排查性能或语义问题时，最可靠的做法不是看博客结论，而是在当前解释器里把函数拆成可核对的证据链：读 code object 的字段、取调用帧、反汇编指令。下面这段把这三步封装成一个 inspect_fn 工具，对任意函数打印常量池、局部变量、栈深、字节码与调用者信息。

真实调试可再加 gdb 在 _PyEval_EvalFrameDefault 下断点，把 dis 输出与单步执行对照。重点是所有结论都来自本机运行时对象，而不是记忆中的旧版本指令名。

```python
import dis, sys

def inspect_fn(fn, *args):
    co = fn.__code__
    print('fn', co.co_name)
    print('consts', co.co_consts)
    print('varnames', co.co_varnames)
    print('names', co.co_names)
    print('stacksize', co.co_stacksize)
    print('nbytes', len(co.co_code))
    print('has_exctable', hasattr(co, 'co_exceptiontable'))
    print('result', fn(*args))
    dis.dis(fn)

def compute(a, b):
    t = a * b
    return t + 1

inspect_fn(compute, 3, 4)
print('current_frame', sys._getframe().f_code.co_name)
```

<Callout type="idea" title='落地提示' text='用调试构建加 gdb / lldb 单步跟踪一个小例子，配合 dis 输出对照，效率远高于通读' />

<CheckList id='P114b' title='上线前自检' :items='["能复现并解释「照 3.9 的博客结论优化属性访问」", "能复现并解释「用 sys.getrefcount 的原始返回值当作对象引用」", "能复现并解释「以为每个函数调用都有一个常驻的 PyFrameObject」", "能用一条命令验证 源码目录结构", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import dis, sys; print(sys.version.split()[0]); dis.dis(lambda x:x)"
```

把输入换成你自己的数据，观察结果是否仍符合 **源码目录结构** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 照 3.9 的博客结论优化属性访问 | 3.11 起有自适应特化与内联缓存、3.13 有超级指令，指令序列与开销模型都变了，旧结论失效 | 先确认解释器版本，用 dis.dis 在当前环境反汇编，必要时对预热前后分别计时，再决定改不改写法 |
| 用 sys.getrefcount 的原始返回值当作对象引用数 | 函数调用时实参本身持有一个临时引用，返回值比真实引用数多 1，直接解读会多算一个引用 | 需要真实引用数时对结果减 1；观察别名增减用两次读数的差值更可靠 |
| 以为每个函数调用都有一个常驻的 PyFrameObject | 3.11 起帧内联为 _PyInterpreterFrame，PyFrameObject 只在 sys._getframe 或回溯时懒创建 | 读帧相关源码先确认版本；用 sys._getframe(depth) 取帧，理解 3.13 起 f_locals 由 PEP 667 改为写时同步 |


## BINARY_OP 到 long_add：一次整数加法的 C 分派链

把 a + b 的 BINARY_OP 在 C 层拆开，能看清鸭子类型落到哪个函数。

Python/`ceval.c` 的 _PyEval_EvalFrameDefault 弹出两个栈顶操作数，调用 Objects/`abstract.c` 的 PyNumber_Add，后者经 binary_op1 按 `Py_TYPE(v)`->tp_as_number 取 nb_add 槽，类型不同时按 PyType_IsSubtype 决定子类型优先，槽为空才抛 TypeError。

PyLong_Type 的 nb_add 指向 Objects/`longobject.c` 的 long_add，它用 x_add 处理 ob_digit[]（每位 30 bit），再经 _PyLong_New 落到 `obmalloc.c` 的 _PyObject_Malloc。

槽表是 Include/cpython/`object.h` 里 PyNumberMethods 约四十个函数指针的连续结构，PyTypeObject 只存 tp_as_number、tp_as_sequence、tp_as_mapping 三个指针；

对 Python 类，Objects/`typeobject.c` 的 update_one_slot 在 type_ready 时把 `__add__` 包装成 slot_nb_add 填槽，setattr 改类属性会触发 type_modified 让槽失效重算。

这解释了为什么 int 子类加 `__radd__` 会改变分派顺序，以及纯 Python 的 `__add__` 比内置 long 多一层 slot 包装与一次 PyObject_Call。

```python
import ctypes, sys

class Header(ctypes.Structure):
    _fields_ = [('ob_refcnt', ctypes.c_ssize_t),
                ('ob_type', ctypes.c_void_p)]

x = [1, 2, 3]
alias = x
hdr = Header.from_address(id(x))
print('refcnt_with_alias', hdr.ob_refcnt)
del alias
print('refcnt_after_del', hdr.ob_refcnt)
print('type_ptr_matches', hdr.ob_type == id(list))
print('getsizeof', sys.getsizeof(x))
```

<OutputBox title='扩展示例运行结果' output='refcnt_with_alias 2\nrefcnt_after_del 1\ntype_ptr_matches True\ngetsizeof 88' />

<LineByLine code='import ctypes, sys\n\nclass Header(ctypes.Structure):\n    _fields_ = [(&#39;ob_refcnt&#39;, ctypes.c_ssize_t),\n                (&#39;ob_type&#39;, ctypes.c_void_p)]\n\nx = [1, 2, 3]\nalias = x\nhdr = Header.from_address(id(x))\nprint(&#39;refcnt_with_alias&#39;, hdr.ob_refcnt)\ndel alias\nprint(&#39;refcnt_after_del&#39;, hdr.ob_refcnt)\nprint(&#39;type_ptr_matches&#39;, hdr.ob_type == id(list))\nprint(&#39;getsizeof&#39;, sys.getsizeof(x))' :notes='["按 Include/object.h 的 PyObject 头定义 C 结构", "ob_refcnt 是 Py_ssize_t，占据起始 8 字节", "ob_type 指向 PyTypeObject，紧随其后", "用列表对象避免小整数缓存干扰计数", "加一个别名，引用计数应为 2", "id(x) 把对象地址映射成 Header 视图，不增加引用", "删除别名后计数回落到 1", "ob_type 指针数值应等于 id(list)，证明类型也是 PyObject", "PyCodeObject 字段 co_code/co_consts/co_names/co_varnames/co_stacksize；3.11+ 有 co_exceptiontable", "3.11 起帧内联为 _PyInterpreterFrame 并懒创建 PyFrameObject；3.13 PEP 667 改 f_locals 同步语义", "3.13 引入 LOAD_FAST_LOAD_FAST 等超级指令；dis.dis 加 show_caches=True 看内联缓存", "读源码用 --with-pydebug 构建加 gdb 在 _PyEval_EvalFrameDefault 断点对照 dis，结论必须标注版本"]' title='扩展示例逐行讲解' />


### PyTypeObject 的三张槽表与 PyNumberMethods 字段布局

**PyObject / PyTypeObject / PyCodeObject 关键字段**

| 结构 | 字段 | 类型与含义 | 源码位置 |
| --- | --- | --- | --- |
| PyObject | ob_refcnt | Py_ssize_t 引用计数，归零触发 tp_dealloc | Include/object.h |
| PyObject | ob_type | PyTypeObject* 运行时类型指针 | Include/object.h |
| PyTypeObject | tp_as_number | PyNumberMethods* 数值槽表 | Include/cpython/object.h |
| PyNumberMethods | nb_add | binaryfunc，BINARY_OP 加法的落点 | Include/cpython/object.h |
| PyCodeObject | co_nlocalsplus | localsplus 数组长度，局部变量加栈 | Include/cpython/code.h |

<Quiz no='114-X' q='在 Objects/abstract.c 里，PyNumber_Add(1, 2) 最终通过哪张表找到 long_add？' :options='["PyLong_Type 的 tp_as_number-&gt;nb_add 槽", "co_consts 常量池", "sys.meta_path 的 finder", "tp_as_mapping-&gt;mp_subscript"]' answer="0" explain='PyNumber_Add 调用 binary_op1，由 Py_TYPE(v)-&gt;tp_as_number-&gt;nb_add 取槽，PyLong_Type 的该槽指向 Objects/longobject.c 的 long_add；co_consts 是编译期常量，meta_path 属导入系统，mp_subscript 是方括号下标。' />


## _PyInterpreterFrame 的 localsplus 与 datastack 帧栈

3.11 把帧改成内联结构后，读帧源码先看 Include/internal/`pycore_frame.h` 的 _PyInterpreterFrame：开头是 f_executable（3.13 起指向 PyCodeObject，之前叫 f_code）、previous、f_funcobj、f_globals、f_builtins、f_locals、懒创建的 frame_obj、stacktop、return_offset、owner，末尾是柔性数组 localsplus[]。

局部变量、cell、free 变量与求值栈共用这一块连续内存，索引由 co_nlocalsplus（co_localspluskinds 用 CO_FAST_LOCAL/CELL/FREE 标种类）与 co_stacksize 划界，LOAD_FAST 实际是 frame->localsplus`[i]` 的一次数组读。

帧内存来自 `pycore_pystate.h` 的 _PyThreadState：它持有 datastack_chunk（_PyStackChunk 链表，每块约 16 KiB）与 datastack_top、datastack_limit，_PyThreadState_PushFrame 用栈顶指针 bump 分配，返回只回退指针而不 free，省掉每次调用的堆分配与 GC 追踪。

3.13 的 PEP 667 又把 f_locals 从缓存字典换成写时同步回 localsplus 的 PyFrameLocalsProxy（Objects/`frameobject.c`），调试器改局部变量才能立即生效。

<Exercise title='用 code object 字段算出 localsplus 槽位数' task='读取 __code__ 的 co_nlocalsplus、co_stacksize 与 co_exceptiontable，打印帧内数组总槽数并解释它为何不等于 co_stacksize；再验证 f_lasti 是字节偏移。' solution='import sys\n\ndef probe(fn):\n    co = fn.__code__\n    print(&#39;nlocalsplus&#39;, co.co_nlocalsplus)\n    print(&#39;stacksize&#39;, co.co_stacksize)\n    print(&#39;slots&#39;, co.co_nlocalsplus + co.co_stacksize)\n    print(&#39;exctable_len&#39;, len(co.co_exceptiontable))\n\ndef target(a, b):\n    return a + b\n\nprobe(target)\nprint(&#39;f_lasti_is_offset&#39;, isinstance(sys._getframe().f_lasti, int))' explain='localsplus 同时容纳 co_nlocalsplus 个局部/cell/free 槽与 co_stacksize 个求值栈槽，相加才是帧内数组长度；co_stacksize 只是栈峰值。co_exceptiontable 是 3.11 起零成本异常表的字节编码，与栈深无关。f_lasti 是上一条指令在 co_code 里的字节偏移。' />


### frame_obj 懒创建与 PEP 667 的写时同步代理

<Term word='PyFrameLocalsProxy（PEP 667）' text='3.13 起 frame.f_locals 不再返回可能过期的缓存字典，而是写时同步的代理对象：读取时从 _PyInterpreterFrame 的 localsplus 现取，写入时直接回写对应槽位，让调试器与 exec 对局部变量的修改立即生效，实现位于 Objects/frameobject.c。' />


## 自测与速记

<Exercise title='基础：读出 code object 的字段' task='写一个函数打印 __code__ 的 co_varnames、co_consts、co_names、co_stacksize，并解释为什么纯算术函数 co_names 为空。' solution='def f(a, b):\n    return a + b\nco = f.__code__\nprint(co.co_varnames, co.co_consts, co.co_names, co.co_stacksize)' explain='co_names 记录全局名与属性名，纯算术只用到局部变量与常量，因此为空；co_consts 含隐式返回的 None。' />

<Exercise title='进阶：验证常量折叠' task='用 dis 分别反汇编 lambda: 1 + 2 与 lambda x: x + 2，指出 co_consts 差异并说明折叠发生在哪个阶段。' solution='import dis\nf = lambda: 1 + 2\ng = lambda x: x + 2\nprint(f.__code__.co_consts, g.__code__.co_consts)\ndis.dis(f)' explain='f 的 co_consts 里直接出现折叠后的 3，运行时只剩 RESUME / RETURN_CONST 一类指令；折叠发生在 AST 到字节码的编译期，不是 ceval 运行时。' />

<Quiz no='114-1' q='CPython 3.11 起帧结构的主要变化是？' :options='["帧内联为 _PyInterpreterFrame，PyFrameObject 按需懒创建", "彻底删除了帧对象", "帧改由 GC 分代管理", "每个线程只保留一个全局帧"]' answer="0" explain='3.11 把每次调用的堆分配帧改为线程状态栈上的内联结构，只有 sys._getframe 或回溯需要时才物化 PyFrameObject，降低调用开销。' />

<Quiz no='114-2' q='3.13 反汇编里出现 LOAD_FAST_LOAD_FAST，说明什么？' :options='["超级指令把相邻的两次局部变量加载合并，减少分派", "函数被 JIT 编译成机器码", "变量被提升为全局", "字节码出现了错误"]' answer="0" explain='3.13 用超级指令合并常见指令对，co_code 变短、分派次数减少；这是字节码层的优化，不是 JIT 编译。' />

<Quiz no='114-3' q='sys.getrefcount(x) 的返回值为什么要减 1 才是对象引用数？' :options='["实参传入函数时形参本身持有一个临时引用", "getrefcount 有 off-by-one 的 bug", "对象头多算了一次", "列表容器额外持有一份"]' answer="0" explain='调用函数时参数对象被临时引用一次，函数返回后释放；因此读数比真实引用多 1，看别名增减用两次读数差更可靠。' />

<FillBlank no='114-F' tpl='___ sys, dis' :answers='["import"]' hint='回想本讲关于 源码目录结构 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 CPython 源码布局与 PyObject / PyTypeObject 的落点。' />

<KnowledgeCard :points='["PyObject 头含 ob_refcnt 与 ob_type；PyTypeObject 的槽表决定 BINARY_OP 的运行时分派", "源码分 Include/ Objects/ Python/ Modules/ Lib/；ceval.c 与 bytecodes.c 是求值循环核心", "PyCodeObject 字段 co_code/co_consts/co_names/co_varnames/co_stacksize；3.11+ 有 co_exceptiontable", "3.11 起帧内联为 _PyInterpreterFrame 并懒创建 PyFrameObject；3.13 PEP 667 改 f_locals 同步语义", "3.13 引入 LOAD_FAST_LOAD_FAST 等超级指令；dis.dis 加 show_caches=True 看内联缓存", "读源码用 --with-pydebug 构建加 gdb 在 _PyEval_EvalFrameDefault 断点对照 dis，结论必须标注版本"]' :pitfalls='["照 3.9 的博客结论优化属性访问", "用 sys.getrefcount 的原始返回值当作对象引用数", "以为每个函数调用都有一个常驻的 PyFrameObject", "只看博客结论不看版本，CPython 3.11 之后的自适应特化会让很多旧文章完全失效"]' summary='读源码的目标不是背文件，而是把语言现象映射到具体实现：一次属性查找、一次函数调用分别落到哪个 C 函数' />

1. PyObject 头含 ob_refcnt 与 ob_type；PyTypeObject 的槽表决定 BINARY_OP 的运行时分派

2. 源码分 Include/ Objects/ Python/ Modules/ Lib/；ceval.c 与 bytecodes.c 是求值循环核心

3. PyCodeObject 字段 co_code/co_consts/co_names/co_varnames/co_stacksize；3.11+ 有 co_exceptiontable

[下一讲：内存分配器 pymalloc 与 GC 源码](/advanced/allocator)

<Predict no='114-P' q='dis.dis(add) 在 3.13 下最可能看到哪组指令？' :options='["RESUME / LOAD_FAST_LOAD_FAST / BINARY_OP / RETURN_VALUE", "LOAD_FAST / LOAD_FAST / BINARY_OP / RETURN_VALUE", "单条 JIT_ADD 指令"]' answer='0' output='RESUME / LOAD_FAST_LOAD_FAST / BINARY_OP 0 (+) / RETURN_VALUE' explain='3.13 用超级指令把两个 LOAD_FAST 合成 LOAD_FAST_LOAD_FAST，随后 BINARY_OP 0 做加法、RETURN_VALUE 返回；RESUME 是函数入口的内部指令。' />
