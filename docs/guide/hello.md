---
title: 第 003 讲 · 第一行 Python：从源码到字节码再到执行
description: 亲手验证解释执行的完整链路
---

<StageHeader stage='L0 · 导学' level='★☆☆☆☆' time='25 分钟' goal='亲手验证解释执行的完整链路' prereq='第 002 讲 · 环境与工具链：解释器、虚拟环境与编辑器' />

# 第 003 讲 · 第一行 Python：从源码到字节码再到执行

环境稳了，可以敲下第一行打印语句。可在添语法之前，先弄明白：按下回车后，一行文本经历了什么才变成结果。它不增加新语法，却让往后许多『为什么』有了落点。

你大概注意过，改了 .py 偶尔没生效，或目录里多出 __pycache__，都是同一条链路的痕迹。我们先把脚本与交互式解释器各跑一遍，再用 compile 把源码编成 code object、借 dis 读一眼字节码，最后说清 __pycache__ 与 pyc 只是缓存，而非可执行文件。能运行 .py、见过 import 就够；学完你能讲出解释执行的完整路径，碰到『改了没变』也知道从哪层查。


## 改了源码却跑出旧值，if False 里的语法错误也能拦住启动

你改了一个工具模块里的常量，保存后重新跑主程序，输出却还是旧值；反复确认文件确实改了、甚至重启了编辑器，结果依旧。更诡异的是，把文件名从 `util.py` 改成 `util2.py` 再导入，新值立刻生效。

另一个常见现场：给脚本加了一行语法错误，明明写在 if False: 分支里，程序却连启动都启动不了，报错直接指向那行永远不会执行的代码。这两个现象用「Python 逐行解释源码」的直觉完全解释不通。朴素解法是反复清缓存、删文件、重启，却说不清到底哪一步起了作用。

真相是 CPython 根本不逐行翻译源码：它先把整个模块编译成字节码 code object，再由栈式虚拟机执行；导入时还会把字节码写进 `__pycache__` 下的 pyc 缓存，靠源文件 mtime 与大小决定是否重编。语法检查发生在编译整个模块阶段，与那行是否会被执行无关。

本讲用 compile、dis、code object 属性与 pyc 路径规则，把这条链路变成能亲手验证的证据。


## 不是逐行翻译：源码、code object 与栈式虚拟机

`compile(source, filename, mode, flags=0, dont_inherit=False)` 把源码字符串编译成 code object，是「源码到字节码」这一步的公开入口。

mode 三选一且行为完全不同：exec 编译语句序列，末尾补一条 return None，因此 `exec(code)` 返回 None、co_consts 里多出一个 None；eval 只接受单个表达式，编译出的 code object 不含那条收尾 None，`eval(code)` 返回表达式的值；

single 面向交互式解释器，表达式语句会额外触发 PRINT_EXPR 把结果打印出来，REPL 里敲 1+1 立刻看到 2 就是它。filename 只用于回溯与报错，不是真实文件路径，通常写成用尖括号包住的占位名。

生成的 code object 有一批只读属性：co_consts 是字面量元组（还会包含常量折叠后的结果，如 6 * 7 变成 42），co_names 是全局名字元组，co_varnames 是局部变量名，co_code 是原始字节码字节串，co_filename 与 co_firstlineno 供 traceback 定位，co_flags 标出是否含生成器或协程。

用 `dis.dis(code)` 或 `dis.get_instructions(code)` 能把 co_code 反汇编成人能读的指令。

关键边界：编译以整个字符串或模块为单位，语法错误在生成任何字节码之前就抛出，哪怕那行位于 if False 分支。

<ConceptDiagram type='hub4' title='第 003 讲 · compile()：三种 mode 与 code object 的字段' labels='compile()：三种 mode 与 co|常量折叠与名字绑定：co_consts 里藏|__pycache__ 与 pyc：缓存判据' caption='亲手验证解释执行的完整链路' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## compile() 的三种 mode 与 code object 的字段

编译器在 AST 到字节码阶段会做常量折叠：只由字面量构成的表达式会直接算出结果写进 co_consts，运行时不再做运算。

compile('6 * 7', fname, 'eval').co_consts 得到 (42,)，compile('1 + 2 * 3', fname, 'eval').co_consts 得到 (7,)，源码里的乘法根本不出现在字节码里。

一旦表达式含名字，就无法折叠：compile('a + b', fname, 'eval').co_consts 是空元组 ()，名字进 co_names 变成 ('a', 'b')，运行时靠 BINARY_OP 动态求值。

这个差别是判断「这段代码是编译期确定还是运行期计算」的直接证据，也解释了为什么改了某个常量值却看起来没生效——若那处参与的是折叠后的字面量，改的其实是被缓存的旧 pyc。

同一编译单元里相同的字面量通常只保留一份常量对象，所以两个 257 字面量可能 is 相等，但那是编译器去重，不是语言保证（第 006 讲会拆小整数缓存与驻留的差别）。

flags 参数可传 `ast.PyCF_ONLY_AST` 让 compile 直接返回 AST 而非字节码，配合 `ast.dump` 能看到语法树结构；

future 语句也是通过影响编译标志改变生成的字节码，而非运行时开关。

```python
src = 'x = 6 * 7' + chr(10) + 'print(x)'
code_obj = compile(src, '<demo>', 'exec')
print('type', type(code_obj).__name__)
print('consts', code_obj.co_consts)
print('names', code_obj.co_names)
print('nbytes', len(code_obj.co_code) > 0)
exec(code_obj)
```

<OutputBox title='主示例运行结果' output='type code\nconsts (42, None)\nnames (&#39;x&#39;, &#39;print&#39;)\nnbytes True\n42' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='src = &#39;x = 6 * 7&#39; + chr(10) + &#39;print(x)&#39;\ncode_obj = compile(src, &#39;&lt;demo&gt;&#39;, &#39;exec&#39;)\nprint(&#39;type&#39;, type(code_obj).__name__)\nprint(&#39;consts&#39;, code_obj.co_consts)\nprint(&#39;names&#39;, code_obj.co_names)\nprint(&#39;nbytes&#39;, len(code_obj.co_code) &gt; 0)\nexec(code_obj)' :notes='["把两行源码拼成一个字符串，用 chr(10) 生成换行，示例里不写反斜杠转义", "compile 以 exec 模式把整段源码编译为 code object，filename 只用于报错定位", "type(...).__name__ 是 code，说明产物是字节码对象而非源码字符串", "co_consts 出现 42：6 * 7 被常量折叠，末尾 None 是 exec 模式补的返回值", "co_names 记录全局名字：x 被赋值、print 被调用", "co_code 是原始字节码字节串，长度大于 0 说明确实生成了指令", "exec 把 code object 交给虚拟机执行，等价于运行 x = 42 后 print(x)，打印 42"]' title='第 003 讲 · 第一行 Python：从源码到字节码再到执行' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**compile 的三种 mode 对照**

| mode | 接受的输入 | co_consts 收尾 | 执行与返回 |
| --- | --- | --- | --- |
| exec | 语句序列或整个模块 | 补一个 None | exec() 返回 None |
| eval | 单个表达式 | 无收尾 None | eval() 返回表达式值 |
| single | 单条交互语句 | 含 PRINT_EXPR | exec() 会打印表达式结果，仍返回 None |


### code object 常用属性速查


## 常量折叠：co_consts 里藏着的 42

包导入时，CPython 把编译结果写进源文件同级的 `__pycache__` 目录，文件名形如 `module.cpython`-313.pyc，其中 313 是解释器版本标签；

可以用 `importlib.util.cache_from_source`('pkg/mod.py') 直接算出这个路径，返回值里一定含 `__pycache__` 且以 .pyc 结尾。

pyc 文件头部记录源文件 mtime 与大小（时间戳模式）或源文件内容的哈希（校验模式，PEP 552，3.7 起），导入时二者比对：一致就跳过编译直接反序列化 code object，不一致才重新编译并覆写。

由此得到两个反直觉结论：一是「改了 .py 一定重新执行」不成立——import 先看 `sys.modules` 缓存，命中就直接复用进程内的模块对象，连 pyc 都不读；二是同一秒内把文件改回同样大小，时间戳模式可能判为未变而继续用旧 pyc。

pyc 与解释器版本绑定，3.12 的 pyc 不能被 3.13 用，也不是可独立分发的可执行文件，它不含源码、不含依赖。部署只需源码与依赖，pyc 可丢弃；但在只读文件系统或冷启动敏感的容器里，用 python -m compileall -q 预生成 pyc 能省去每次编译的开销。

想彻底绕开缓存做实验，用 `PYTHONDONTWRITEBYTECODE=1` 或把 `sys.dont_write_bytecode` 设为 True。


## exec 与 eval 的产物差在哪

```python
exec_code = compile('1 + 2', '<x>', 'exec')
eval_code = compile('1 + 2', '<y>', 'eval')
print('exec_returns', exec(exec_code))
print('eval_returns', eval(eval_code))
print('exec_has_none_const', None in exec_code.co_consts)
print('eval_consts', eval_code.co_consts)
print('eval_names', eval_code.co_names)
```

<OutputBox title='对照写法：先自己猜，再点开' output='exec_returns None\neval_returns 3\nexec_has_none_const True\neval_consts (3,)\neval_names ()' guess="true" />


## 语法检查为什么发生在整个模块编译阶段

CPython 前端把源码变成一棵 AST，编译器遍历 AST 生成符号表与字节码，最终封进 PyCodeObject：它保存 co_code（指令字节串）、co_consts（常量元组，其中嵌套函数会存另一个 code object）、co_names、co_varnames，以及运行所需的栈大小与标志位。

执行时 ceval 用一个基于栈的循环逐条取出指令，LOAD_CONST 从 co_consts 取常量压栈，LOAD_NAME 或 LOAD_FAST 从名字空间取对象，BINARY_OP 弹栈做运算再压回，RETURN_VALUE 把栈顶作为结果返回。

这套结构解释了三件事：语法错误在 AST 生成与编译阶段就报，因为整个模块要先被完整解析；常量折叠之所以可能，是因为编译器在写 co_consts 前就能对纯字面量子树求值；而 import 的加速靠的是把序列化后的 PyCodeObject 存进 pyc，省掉重新走词法、语法、编译三遍。

pyc 头部的 magic number 与 CPython 字节码版本绑定，一旦指令集变化（几乎每个 minor 版本都会），旧 pyc 立即作废重编。理解 code object 是「编译产物」而非「可执行二进制」，就知道它必须依赖对应版本的解释器与源码才能跑。


## __pycache__ 与 pyc：缓存判据与失效信号


### 部署时 pyc 该留还是该删


## 部署前自检：给字节码缓存留下可核对的证据

线上排障最怕「我明明改了却没变」这类说不清的问题。一个可靠的做法是给部署脚本加一段自检：在真正 import 业务模块之前，先算出模块的预期 pyc 路径，用 compile 的 AST 模式统计语法树节点，再确认关键常量确实出现在 co_consts 里、字节码指令确实生成，并把这几项打进启动日志。

这样一旦出现「跑的是旧字节码」或「常量被折叠成旧值」，日志里会留下可核对的证据，而不是靠人反复重启碰运气。

下面这段只用标准库：用 `ast.PyCF_ONLY_AST` 让 compile 返回语法树并 `ast.walk` 统计节点，用 `dis.get_instructions` 数出指令条数，用 `importlib.util.cache_from_source` 定位缓存路径，用 `importlib.util.MAGIC_NUMBER` 的长度核对 pyc 头部标记。

真实部署还应比对生成 pyc 的解释器版本与运行解释器是否一致，避免跨版本复用。

```python
import os, dis, importlib.util, ast, tempfile

def audit(src, filename, key_const):
    tree = compile(src, filename, 'exec', ast.PyCF_ONLY_AST)
    node_count = sum(1 for _ in ast.walk(tree))
    code_obj = compile(src, filename, 'exec')
    ops = [i.opname for i in dis.get_instructions(code_obj)]
    return {
        'nodes': node_count,
        'const_ok': key_const in code_obj.co_consts,
        'instrs': len(ops),
        'pyc': importlib.util.cache_from_source(filename),
        'magic_len': len(importlib.util.MAGIC_NUMBER),
    }

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, 'demo_mod.py')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('LIMIT = 6 * 7' + chr(10))
    r = audit('LIMIT = 6 * 7' + chr(10), path, 42)
    print('const_ok', r['const_ok'])
    print('instrs_positive', r['instrs'] > 0)
    print('pyc_in_cache', '__pycache__' in r['pyc'])
    print('magic_len', r['magic_len'])
```

<Callout type="idea" title='落地提示' text='部署时只需要源码与依赖，pyc 可丢弃；但在只读文件系统上预编译 pyc 能明显缩短冷启动' />


## 改了 .py 没生效：错因速查


## 从 compile 到 pyc：练习、自测与速记

<Exercise title='基础：对比 exec 与 eval 模式的 code object' task='分别用 compile 的 exec 与 eval 模式编译同一表达式 2 ** 10，打印两者 co_consts 与执行结果，解释为什么 exec 模式的 co_consts 多一个 None。' solution='e = compile(&#39;2 ** 10&#39;, &#39;&lt;x&gt;&#39;, &#39;exec&#39;)\nv = compile(&#39;2 ** 10&#39;, &#39;&lt;y&gt;&#39;, &#39;eval&#39;)\nprint(&#39;exec_consts&#39;, e.co_consts)\nprint(&#39;eval_consts&#39;, v.co_consts)\nprint(&#39;exec_ret&#39;, exec(e))\nprint(&#39;eval_ret&#39;, eval(v))' explain='2 ** 10 被常量折叠成 1024；exec 模式补一条 return None，故 co_consts 为 (1024, None) 且 exec 返回 None；eval 模式为 (1024,) 且返回 1024。' />

<Exercise title='进阶：用 dis 与 cache_from_source 定位缓存路径' task='写函数 inspect_module(path)，返回该模块预期 pyc 路径、是否含 __pycache__、以及把 a + b 编译后是否含 BINARY_OP 指令；解释 pyc 为何带解释器版本标签。' solution='import dis, importlib.util\ndef inspect_module(path):\n    c = importlib.util.cache_from_source(path)\n    code = compile(&#39;a + b&#39;, &#39;&lt;s&gt;&#39;, &#39;eval&#39;)\n    return {&#39;pyc&#39;: c, &#39;in_cache&#39;: &#39;__pycache__&#39; in c,\n            &#39;has_binop&#39;: any(i.opname == &#39;BINARY_OP&#39; for i in dis.get_instructions(code))}\nprint(inspect_module(&#39;pkg/util.py&#39;))' explain='含名字的表达式无法常量折叠，必然生成 BINARY_OP；pyc 文件名带 cpython-313 标签是因为字节码指令集随 minor 版本变化，magic number 不符时解释器会重编而非复用。' />

<Quiz no='003-1' q='关于 compile 的 mode，哪项描述准确？' :options='["eval 模式的 code object 不含收尾 None，eval() 返回表达式值", "exec 与 eval 生成的 co_consts 完全相同", "single 模式不打印表达式结果", "语法错误只在对应分支被执行时才报"]' answer="0" explain='eval 面向单表达式、无隐式 return None；exec 会补 None；single 通过 PRINT_EXPR 把结果打印出来；语法检查在编译整个模块时完成，与分支是否执行无关。' />

<Quiz no='003-2' q='compile(&#39;6 * 7&#39;, fname, &#39;eval&#39;).co_consts 最可能是什么？' :options='["(42,)", "(6, 7, 42)", "(6, 7)", "()"]' answer="0" explain='常量折叠在编译期把纯字面量表达式求值并写进 co_consts，运行期不再做乘法；含名字的表达式才会把名字放进 co_names 并保留 BINARY_OP。' />

<Quiz no='003-3' q='导入时 pyc 缓存靠什么判断是否重编？' :options='["源文件 mtime 与大小，或内容哈希（PEP 552，3.7 起）", "仅看文件名是否变化", "每次导入都重新编译", "看 PYTHONPATH 是否变化"]' answer="0" explain='pyc 头部记录 mtime 加大小或源文件内容哈希，与当前源文件比对决定复用还是重编；进程内还要先查 sys.modules，命中则连 pyc 都不读。' />

<Predict no='003-P' q='exec(compile(&#39;x = 6 * 7&#39; + chr(10) + &#39;print(x)&#39;, &#39;&lt;demo&gt;&#39;, &#39;exec&#39;)) 会输出什么？' :options='["42", "6 * 7", "先打印 6 再打印 7"]' answer='0' output='42' explain='6 * 7 被常量折叠成 42 存进 co_consts，运行时 x 被赋值为 42，print(x) 打印 42；源码里的乘法指令根本不出现在字节码里。' />

<FillBlank no='003-F' tpl='___ = &#39;x = 6 * 7&#39; + chr(10) + &#39;print(x)&#39;' :answers='["src"]' hint='回想本讲关于 脚本与交互式解释器 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 compile()：三种 mode 与 code object 的字段 的落点。' />

<KnowledgeCard :points='["执行链路是 源码 → AST → 字节码 code object → ceval 栈式虚拟机；语法检查发生在编译整个模块阶段", "compile 三 mode：exec 补 None 且返回 None、eval 返回表达式值、single 打印表达式结果（REPL 用）", "co_consts 含常量折叠结果（6 * 7 变 42）、co_names 放全局名、co_code 是字节码字节串", "pyc 位于 __pycache__/module.cpython-313.pyc，用 mtime 加大小或内容哈希判重编（PEP 552）", "import 先查 sys.modules，进程内模块是单例；改磁盘文件需重启进程或 importlib.reload", "pyc 不是可分发产物：绑定解释器 magic number、不含源码与依赖"]' :pitfalls='["改了 .py 文件，重新导入后新代码没生效", "把语法错误写进 if False 分支里，以为不会执行就没事", "把 pyc 当成可独立分发的编译产物", "以为改了 .py 一定会重新执行，却忽略了导入缓存与 pyc 时间戳，是调试时最常见的错觉"]' summary='Python 不是逐行边读边翻译：源码先编译成字节码，再由虚拟机执行；pyc 只是缓存，不是编译型语言的可执行文件' />

1. 执行链路是 源码 → AST → 字节码 code object → ceval 栈式虚拟机；语法检查发生在编译整个模块阶段

2. compile 三 mode：exec 补 None 且返回 None、eval 返回表达式值、single 打印表达式结果（REPL 用）

3. co_consts 含常量折叠结果（6 * 7 变 42）、co_names 放全局名、co_code 是字节码字节串

[下一讲：工具链全景：写代码、查问题、验质量](/guide/toolchain)
