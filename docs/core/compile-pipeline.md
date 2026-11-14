---
title: 第 049 讲 · CPython 编译流程：AST 到字节码
description: 能读懂并操作 Python 的编译中间产物
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='40 分钟' goal='能读懂并操作 Python 的编译中间产物' prereq='第 048 讲 · 阶段综合：最小 ORM 与校验框架' />

# 第 049 讲 · CPython 编译流程：AST 到字节码

阶段四收在「类是怎么被创建出来的」，从这里换一层视角：不看我们写的代码，看解释器拿到源码后先做了什么。第 3 讲只说源码会先变成字节码；这一讲把中间摊开，看有哪些可检查的产物。

一个配置解析器把上传字符串直接当字典求值，另有人改完代码报错却指到不相干的行，都落在同一条链上。本讲先从词法与语法分析生成的 AST 和 `ast` 模块讲起，再用 `compile` 看清 code object 结构，最后说常量折叠与 AST 改写该守住的行号边界。需要第 3 讲的执行模型与函数；学完你能操作编译中间产物，把 lint 与代码生成建立在 AST 而非字符串替换上。


## 一段外部配置触发 eval 注入的工单

一个配置解析器把用户上传的字符串用 `eval()` 当字典求值，某天有人传了一段构造系统命令的表达式，服务直接被拿到执行入口——`eval` 会执行任意代码，不只是解析字面量。

另一处更隐蔽：团队写了个 AST 改写工具给所有常量加前缀，改完却忘了给新建节点补 `lineno` 与 `col_offset`，`compile` 之后报错栈指向完全不相干的行，排查花了半天。

还有人在编译期优化里把 `1 + 2` 当成运行时加法，看到 `co_consts` 里直接是 3 时很困惑：源码明明有加法，反汇编却只剩一条 `LOAD_CONST`。这些现象都指向同一条链路：Python 不逐行解释源码，而是先做词法与语法分析生成 AST，再编译成字节码 code object，最后交给虚拟机执行。

本讲把 `ast` 模块、`compile` 内置函数、code object 结构、常量折叠与 AST 改写的安全边界逐一讲清楚，让每个中间产物都能被检查和验证。

<Callout type="warn" title='先看一个真实会出错的写法' text='用 eval / exec 解析外部传入的字符串当数据：eval 会执行任意表达式，等于把上传内容变成代码执行入口' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段五 · 核心机制与运行时 |
| 前置 | 第 048 讲 · 阶段综合：最小 ORM 与校验框架 |
| 难度 / 建议时长 | ★★★★☆ · 40 分钟 |
| 本讲新增 | 词法与语法分析、ast 模块与 ast.dump、compile 内置函数 |
| 一句话目标 | 能读懂并操作 Python 的编译中间产物 |
| 为下一讲铺垫 | 字节码、栈式虚拟机与 dis 实战 |


## 从源码到 AST：ast.parse、ast.dump 与字面量安全求值

`ast.parse` 返回 `ast.Module`（`mode='eval'` 时返回 `Expression`，`mode='single'` 用于交互式单句），它只做解析，不执行任何代码；

`mode`、`type_comments`、`feature_version` 等参数控制解析细节。

`ast.dump` 把树打成可读字符串，`indent` 参数（3.9+）可缩进，`include_attributes=True` 会带上 `lineno`、`col_offset`、`end_lineno`、`end_col_offset`，调试改写后的节点时很有用。

3.8 起 `Constant` 节点统一表示数字与字符串字面量（旧版是 `Num` / `Str` / `NameConstant`），写跨版本工具时要按版本兼容。

`ast.literal_eval` 只接受字面量节点（数字、字符串、元组、列表、字典、集合、布尔、`None`），遇到 `Call`、`Name`、属性访问会抛 `ValueError`，因此解析外部数据必须用它而不是 `eval`。

`ast.unparse`（3.9+）把 AST 还原成源码，`ast.walk` 与 `ast.NodeVisitor` 做遍历。

检查产物最简单的方式是打印 `type(tree).__name__` 与 `tree.body` 里每个节点的类型名，确认结构符合预期再往下走。

```python
import ast

src = 'x = 1 + 2' + chr(10) + 'print(x)'
tree = ast.parse(src)
print('type', type(tree).__name__)
print('body', [type(n).__name__ for n in tree.body])
print('target', tree.body[0].targets[0].id)
print('op', type(tree.body[0].value.op).__name__)
code = compile(src, 'demo.py', 'exec')
print('consts', code.co_consts)
print('names', code.co_names)
folded = compile('1 + 2', 'f', 'eval')
print('folded consts', folded.co_consts)
print('mode eval returns', eval(folded))
```

<OutputBox title='主示例运行结果' output='type Module\nbody [&#39;Assign&#39;, &#39;Expr&#39;]\ntarget x\nop Add\nconsts (3, None)\nnames (&#39;x&#39;, &#39;print&#39;)\nfolded consts (3,)\nmode eval returns 3' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import ast\n\nsrc = &#39;x = 1 + 2&#39; + chr(10) + &#39;print(x)&#39;\ntree = ast.parse(src)\nprint(&#39;type&#39;, type(tree).__name__)\nprint(&#39;body&#39;, [type(n).__name__ for n in tree.body])\nprint(&#39;target&#39;, tree.body[0].targets[0].id)\nprint(&#39;op&#39;, type(tree.body[0].value.op).__name__)\ncode = compile(src, &#39;demo.py&#39;, &#39;exec&#39;)\nprint(&#39;consts&#39;, code.co_consts)\nprint(&#39;names&#39;, code.co_names)\nfolded = compile(&#39;1 + 2&#39;, &#39;f&#39;, &#39;eval&#39;)\nprint(&#39;folded consts&#39;, folded.co_consts)\nprint(&#39;mode eval returns&#39;, eval(folded))' :notes='["导入 ast 模块，全程只做解析与编译", "空行，只用于分隔逻辑块，不影响执行结果。", "空行分隔导入与代码", "用 chr(10) 拼出两行源码，避免字符串里出现反斜杠转义", "ast.parse 默认 mode=&#39;exec&#39;，返回 ast.Module", "确认顶层节点类型", "打印 body 里每个语句节点的类型名", "取出 Assign 的目标名，验证结构可读", "取出右侧二元运算的运算符节点类型", "compile 以 &#39;exec&#39; 模式编成 code object，filename 进 traceback", "co_consts 里 1+2 已被折叠成 3，另含 None", "co_names 记录模块里用到的全局名字", "单独编译一个表达式，观察常量折叠", "折叠后 co_consts 只含结果 3，没有加法指令"]' title='第 049 讲 · CPython 编译流程：AST 到字节码' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**compile 参数与效果**

| 参数 | 取值 / 默认 | 作用 |
| --- | --- | --- |
| source | str 或 ast.AST | 源码、AST 均可编译 |
| filename | 如 'demo.py' | 进 co_filename 与 traceback，别留空 |
| mode | 'exec' / 'eval' / 'single' | 模块语句 / 单表达式 / 交互式单句 |
| flags | 默认 0，可含 ast.PyCF_ONLY_AST | 带 ONLY_AST 时直接返回 AST |
| dont_inherit | 默认 False | True 时不继承调用点的 __future__ 设置 |
| optimize | -1 / 0 / 1 / 2 | -1 跟随 -O；1 移除 assert；2 再移除 docstring |

<Callout type="tip" title='核心心智模型' text='`ast.parse` 返回 `ast.Module`（`mode=&#39;eval&#39;` 时返回 `Expression`，`mode=&#39;single&#39;` 用于交互式单句），它只做解析，不执行任何代码；`mode`、`type_comments`、`feature_version` 等参数控制解析细节。…' />

**ast 模块 API 与安全边界**

| API | 作用 | 边界 |
| --- | --- | --- |
| ast.parse / ast.dump | 解析与打印树 | dump 的 indent 参数 3.9+ |
| ast.literal_eval | 只求值字面量节点 | 非字面量抛 ValueError: malformed node or string |
| eval / exec | 执行任意代码 | 解析外部数据绝不能用 |
| ast.NodeTransformer | 改写 AST | 新节点需 copy_location 或 fix_missing_locations |
| ast.unparse | AST 还原源码 | 3.9+，改写后用来核对 |
| ast.PyCF_ONLY_AST | 让 compile 返回 AST | 等价于 ast.parse |

<Term word='词法与语法分析' text='`ast.parse` 返回 `ast.Module`（`mode=&#39;eval&#39;` 时返回 `Expression`，`mode=&#39;single&#39;` 用于交互式单句），它只做解析，不执行任何代码；`mode`、`type_comments`、`feature_version` 等参数控制解析细节。`ast.dump`…' />

<Term word='ast 模块与 ast.dump' text='`compile` 把源码或 AST 编成 code object，`filename` 会进 traceback 与 `co_filename`，别写成空串。`mode` 三选一：`&#39;exec&#39;` 编译模块语句、`&#39;eval&#39;` 编译单个表达式并返回值、`&#39;single&#39;` 编译交互式单句（会打印表达式结果）。…' />


## 编译器入口：词法、语法分析与 CPython 的 PEG parser

CPython 的执行链路是 tokenizer → 语法分析 → AST → 编译器 → code object → ceval 虚拟机。3.9 起语法分析改用 PEG parser（此前是 `LL(1)`），生成的 AST 再交给 `compile.c`：先建符号表确定作用域，再遍历做常量折叠与窥孔优化，最后发射字节码。

常量折叠把 `1 + 2` 这类编译期可算的 `BinOp` 直接替换为 `Constant(3)` 写入 `co_consts`，所以运行时没有 `BINARY_OP`；`optimize` 级别在同一阶段生效，`1` 丢弃 `assert` 与 `if __debug__` 分支，`2` 再丢弃 docstring。

code object 是编译产物的不可变容器，`co_code` 存指令、`co_linetable`（3.10+）存字节码偏移到源码行的映射、`co_exceptiontable`（3.11+）存异常处理区间。

改写 AST 时新建节点若没有 `lineno` / `col_offset`，编译器无法填行号表，轻则抛错、重则 traceback 指向错误行，因此 `fix_missing_locations` 是必需步骤。

`ast.literal_eval` 只递归处理字面量节点，遇到 `Call` / `Name` 抛 `ValueError`，从而在协议层杜绝代码执行。

<ConceptDiagram type='compare2' title='第 049 讲 · 从源码到 AST：ast.parse、ast.dump 与字面量安全求值' labels='从源码到 AST：ast.parse、ast…|compile 与 code object…|常量折叠与 AST 改写：优化发生在编译期…|常量折叠' caption='能读懂并操作 Python 的编译中间产物' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## compile 与 code object：mode、flags、optimize 三个维度

`compile` 把源码或 AST 编成 code object，`filename` 会进 traceback 与 `co_filename`，别写成空串。`mode` 三选一：`'exec'` 编译模块语句、`'eval'` 编译单个表达式并返回值、`'single'` 编译交互式单句（会打印表达式结果）。

`flags` 可用 `ast.PyCF_ONLY_AST` 让 `compile` 直接返回 AST（等价于 `ast.parse`），还可叠加 `__future__` 相关标志；

`dont_inherit=True` 阻止继承调用点的 future 设置。

`optimize` 默认 `-1` 跟随解释器的 `-O` 级别，显式 `0` / `1` / `2` 三档：`1` 移除 `assert` 与 `if __debug__` 分支，`2` 再移除文档字符串。

code object 的关键属性：`co_code` 是字节码字节串，`co_consts` 是常量元组，`co_names` 是全局名字元组，`co_varnames` 是局部变量名，`co_stacksize` 是求值栈最大深度，`co_flags` 记录参数与生成器标志；

3.10 起 `co_linetable` 取代 `co_lnotab` 记录行号，3.11 起新增 `co_exceptiontable`（异常表）与 `co_qualname`。

`dis.dis(code)` 把这些指令翻译成可读形式。注入或动态生成代码时，优先用 AST 而非字符串拼接，产物才可控。

```python
import dis, sys

lit = compile('1 + 2', 'c', 'eval')
ops = [i.opname for i in dis.get_instructions(lit)]
print('no binary op', not any(o in ops for o in ('BINARY_OP', 'BINARY_ADD')))
print('has return', any(o in ops for o in ('RETURN_VALUE', 'RETURN_CONST')))
print('folded consts', lit.co_consts)
print('co_names', lit.co_names)
print('opt2 removes assert', len(compile('assert False', 'a', 'exec', optimize=2).co_code) < len(compile('assert False', 'a', 'exec', optimize=0).co_code))
print('sys module ok', hasattr(sys, 'getsizeof'))
```

<OutputBox title='原理验证' output='no binary op True\nhas return True\nfolded consts (3,)\nco_names ()\nopt2 removes assert True\nsys module ok True' />


### code object 关键属性与版本

**code object 关键属性与版本**

| 属性 | 内容 | 版本说明 |
| --- | --- | --- |
| co_code | 字节码字节串 | 3.11 起指令集大改，需按版本读 |
| co_consts | 常量元组，折叠结果在此 | 长期可用 |
| co_names / co_varnames | 全局名 / 局部名元组 | 长期可用 |
| co_stacksize | 求值栈最大深度 | 长期可用 |
| co_lnotab → co_linetable | 行号映射 | 3.10 起由 co_linetable 取代 |
| co_exceptiontable / co_qualname | 异常表 / 限定名 | 3.11 新增 |


## 常量折叠与 AST 改写：优化发生在编译期，行号信息要保住

常量折叠是 AST 到字节码阶段的编译期优化：`1 + 2` 的 `BinOp` 会被直接折成 `Constant(3)` 塞进 `co_consts`，运行时只剩一条常量相关指令（3.11 及以前是 `LOAD_CONST` 加 `RETURN_VALUE`，3.12 起对常量返回改用 `RETURN_CONST`），完全没有 `BINARY_OP`。

用 `compile('1 + 2', 'f', 'eval').co_consts` 得到 `(3,)`，再用 `dis` 看指令，就能把「源码里有加法」和「字节码里没有加法」这一对看似矛盾的现象变成可验证的证据。

这也意味着性能结论要看字节码而不是源码行数。

`ast.NodeTransformer` 配合 `visit_Constant` / `visit_BinOp` 等方法改写树，但它不会自动给新建节点补位置：要么用 `ast.copy_location` 从旧节点复制位置，要么在整棵树改写后调用 `ast.fix_missing_locations`，否则 `compile` 可能因缺 `lineno` 报错，或生成的 traceback 行号全错。

改坏行号是自定义 lint、自动插桩、代码生成里最典型的隐蔽故障。改写后用 `ast.unparse` 打印结果、`compile` 试编、`dis` 抽查指令，三步就能确认改写既正确又保留了调试信息。产物一旦要给用户看，`lineno` 与 `col_offset` 就是契约的一部分。

```python
import ast

tree = ast.parse('10 + 5', mode='eval')
class Double(ast.NodeTransformer):
    def visit_Constant(self, node):
        if isinstance(node.value, int):
            return ast.copy_location(ast.Constant(value=node.value * 2), node)
        return node
new = Double().visit(tree)
ast.fix_missing_locations(new)
print('rewritten', ast.unparse(new))
print('result', eval(compile(new, 'r', 'eval')))
```

<OutputBox title='对照写法：先自己猜，再点开' output='rewritten 20 + 10\nresult 30' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import ast\n\nsrc = &#39;x = 1 + 2&#39; + chr(10) + &#39;print(x)&#39;\ntree = ast.parse(src)\nprint(&#39;type&#39;, type(tree).__name__)\nprint(&#39;body&#39;, [type(n).__name__ for n in tree.body])\nprint(&#39;target&#39;, tree.body[0].targets[0].id)\nprint(&#39;op&#39;, type(tree.body[0].value.op).__name__)\ncode = compile(src, &#39;demo.py&#39;, &#39;exec&#39;)\nprint(&#39;consts&#39;, code.co_consts)\nprint(&#39;names&#39;, code.co_names)\nfolded = compile(&#39;1 + 2&#39;, &#39;f&#39;, &#39;eval&#39;)\nprint(&#39;folded consts&#39;, folded.co_consts)\nprint(&#39;mode eval returns&#39;, eval(folded))", "note": "从源码到 AST：ast.parse、ast.dump 与字面量安全求值"}, {"label": "对照 / 进阶", "code": "import ast\n\ntree = ast.parse(&#39;10 + 5&#39;, mode=&#39;eval&#39;)\nclass Double(ast.NodeTransformer):\n    def visit_Constant(self, node):\n        if isinstance(node.value, int):\n            return ast.copy_location(ast.Constant(value=node.value * 2), node)\n        return node\nnew = Double().visit(tree)\nast.fix_missing_locations(new)\nprint(&#39;rewritten&#39;, ast.unparse(new))\nprint(&#39;result&#39;, eval(compile(new, &#39;r&#39;, &#39;eval&#39;)))", "note": "compile 与 code object：mode、flags、optimize 三个维度"}]' title='两种写法切换看' />


## 版本演进：co_code 与优化结论不能跨版本照搬

<FlowTimeline :steps='[{"title": "从源码到 AST：ast.parse、ast.d…", "desc": "`ast.parse` 返回 `ast.Module`（`mode=&#39;eval&#39;`…", "tone": "blue"}, {"title": "compile 与 code object：mo…", "desc": "`compile` 把源码或 AST 编成 code object…", "tone": "purple"}, {"title": "常量折叠与 AST 改写：优化发生在编译期，行号…", "desc": "常量折叠是 AST 到字节码阶段的编译期优化：`1 + 2` 的 `BinOp` 会…", "tone": "orange"}, {"title": "工程落地", "desc": "用 AST 写一个「禁用 eval」的最小 lint", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 eval / exec 解析外部传入的字…", "body": "eval 会执行任意表达式，等于把上传内容变成代码执行入口", "tip": "解析字面量数据一律用 ast.literal_eval，它遇到非字面量节点抛 ValueError: malformed node or string"}, {"title": "第 2 步：NodeTransformer 改写后直接…", "body": "新建节点没有 lineno / col_offset，行号表无法正确生成", "tip": "对替换节点用 ast.copy_location(new, old)，并在整棵树改写后调用 ast.fix_missing_locations(tree)"}, {"title": "第 3 步：把某一版本的 co_code 指令或优化结论…", "body": "3.9 换 PEG parser、3.10 换行号表、3.11 换指令集与异常表，字节码持续变化", "tip": "在目标解释器上用 dis 现场验证，输出里注明版本范围，别把字节码写进跨版本断言"}]' />


## 用 AST 写一个「禁用 eval」的最小 lint

团队要在 CI 里拦住源码里直接调用 `eval` 的写法。基于字符串替换的正则容易漏掉重命名、嵌套调用与多行写法；基于 AST 的检查只看节点类型，稳定且能报出精确行号与列偏移。

下面用标准库 `ast` 实现：`NodeVisitor` 遍历所有 `Call` 节点，命中 `func` 为 `Name` 且 `id` 是 `eval` 时记下它的 `(lineno, col_offset)`，再用 `ast.literal_eval` 演示对字面量安全、对函数调用抛 `ValueError`。

整个片段可直接运行，输出命中位置与被拒绝的表达式。要点有两个：遍历的是语法结构而非文本，以及保留 `lineno` / `col_offset` 让报告能指回源码。真实 lint 还会加载文件、按规则编号输出并接入预提交钩子，但骨架就是 `visit_Call` 加位置信息。

```python
import ast

SOURCE = 'def load(raw):' + chr(10) + '    return eval(raw)' + chr(10) + 'def ok(x):' + chr(10) + '    return int(x)'
class EvalFinder(ast.NodeVisitor):
    def __init__(self):
        self.hits = []
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'eval':
            self.hits.append(('eval', node.lineno, node.col_offset))
        self.generic_visit(node)

tree = ast.parse(SOURCE)
finder = EvalFinder()
finder.visit(tree)
print('functions', [n.name for n in tree.body if isinstance(n, ast.FunctionDef)])
print('unsafe calls', finder.hits)
print('literal_eval safe', ast.literal_eval('[1, 2, 3]'))
try:
    ast.literal_eval('__import__(' + chr(34) + 'os' + chr(34) + ')')
except ValueError:
    print('rejected by literal_eval')
```

<Callout type="idea" title='落地提示' text='自定义 lint、代码生成、自动插桩都应基于 AST；产物要保留 lineno 与 col_offset' />

<CheckList id='P049b' title='上线前自检' :items='["能复现并解释「用 eval / exec 解析外部传入的字符串当数据」", "能复现并解释「NodeTransformer 改写后直接 compile…」", "能复现并解释「把某一版本的 co_code 指令或优化结论当语言规范」", "能用一条命令验证 词法与语法分析", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import dis; dis.dis(lambda x: x+1)"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 词法与语法分析 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 eval / exec 解析外部传入的字符串当数据 | eval 会执行任意表达式，等于把上传内容变成代码执行入口 | 解析字面量数据一律用 ast.literal_eval，它遇到非字面量节点抛 ValueError: malformed node or string |
| NodeTransformer 改写后直接 compile，traceback 行号错乱 | 新建节点没有 lineno / col_offset，行号表无法正确生成 | 对替换节点用 ast.copy_location(new, old)，并在整棵树改写后调用 ast.fix_missing_locations(tree) |
| 把某一版本的 co_code 指令或优化结论当语言规范 | 3.9 换 PEG parser、3.10 换行号表、3.11 换指令集与异常表，字节码持续变化 | 在目标解释器上用 dis 现场验证，输出里注明版本范围，别把字节码写进跨版本断言 |

<Callout type="warn" title='本讲最容易踩的坑' text='用 eval / exec 解析外部传入的字符串当数据：eval 会执行任意表达式，等于把上传内容变成代码执行入口' />


## 读得懂编译产物

<Exercise title='基础：用 co_consts 证明常量折叠' task='分别编译 &#39;1 + 2&#39; 与 &#39;a + 2&#39;（后者 a 未定义也能编译），打印两者 co_consts，说明为什么前者只剩常量 3 而后者含名字 a 且需要运行时加法。' solution='c1 = compile(&#39;1 + 2&#39;, &#39;f&#39;, &#39;eval&#39;)\nc2 = compile(&#39;a + 2&#39;, &#39;f&#39;, &#39;eval&#39;)\nprint(&#39;folded&#39;, c1.co_consts)\nprint(&#39;runtime&#39;, c2.co_consts, c2.co_names)' explain='1+2 在编译期可算，被折成 Constant(3) 写入 co_consts；a+2 依赖运行时名字 a，编译器保留 BINARY_OP 与 LOAD_NAME，co_names 里出现 &#39;a&#39;。' />

<Exercise title='进阶：改写 AST 并保留行号信息' task='用 NodeTransformer 把表达式里所有整数字面量乘以 3，改写后调用 fix_missing_locations，打印 ast.unparse 结果与每个 Constant 的 lineno，再 compile 并 eval 验证结果。' solution='import ast\nt = ast.parse(&#39;4 * (2 + 3)&#39;, mode=&#39;eval&#39;)\nclass Triple(ast.NodeTransformer):\n    def visit_Constant(self, n):\n        if isinstance(n.value, int):\n            return ast.copy_location(ast.Constant(value=n.value * 3), n)\n        return n\nt = Triple().visit(t)\nast.fix_missing_locations(t)\nprint(ast.unparse(t), eval(compile(t, &#39;r&#39;, &#39;eval&#39;)))' explain='copy_location 把原节点的 lineno/col_offset 复制给新节点，fix_missing_locations 兜底补齐；unparse 可核对改写内容，compile 后 eval 得到 12 * (6 + 9) 的折叠结果。' />

<Quiz no='049-1' q='解析外部传入的 &#39;[1, 2, 3]&#39; 之类字面量数据，正确工具是？' :options='["ast.literal_eval，只求值字面量节点", "eval，方便直接得到对象", "compile 后 exec", "ast.dump 后字符串切割"]' answer="0" explain='ast.literal_eval 遇到 Call、Name、属性访问等非字面量节点抛 ValueError: malformed node or string，因此在协议层就挡住代码执行；eval 会执行任意表达式。' />

<Quiz no='049-2' q='compile(&#39;1 + 2&#39;, &#39;f&#39;, &#39;eval&#39;).co_consts 为什么是 (3,)？' :options='["常量折叠在编译期把 BinOp 折成 Constant(3)", "运行时算完再把结果写回", "eval 模式自动优化", "co_consts 只存整数"]' answer="0" explain='常量折叠发生在 AST 到字节码的编译阶段，编译期可算的表达式直接替换为常量对象存入 co_consts，运行时只剩 LOAD_CONST，源码里的加号不产生 BINARY_OP。' />

<Quiz no='049-3' q='AST 改写后 traceback 行号错乱，最可能漏了哪一步？' :options='["没给新节点补 lineno/col_offset，即 copy_location 或 fix_missing_locations", "没调用 ast.unparse", "用了 mode=&#39;exec&#39;", "没打印 ast.dump"]' answer="0" explain='新建节点不带位置属性时，编译器无法生成正确行号表；copy_location 复制原位置、fix_missing_locations 兜底补齐，二者至少做其一。unparse 只是查看，不影响行号。' />

<Predict no='049-4' q='optimize=2 编译含 assert 的源码，和 optimize=0 相比 co_code 长度如何？' :options='["更短，assert 与 docstring 都被移除", "更长，会插入更多检查", "完全相同"]' answer='0' output='optimize=2 的 co_code 更短' explain='optimize=1 移除 assert 与 if __debug__ 分支，optimize=2 再移除 docstring；因此 2 档生成的字节码比 0 档短。这条差异可用 len(co_code) 直接量化。' />

<FillBlank no='049-5' tpl='___ ast' :answers='["import"]' hint='回想本讲关于 词法与语法分析 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 从源码到 AST：ast.parse、ast.dump 与字面量安全求值 的落点。' />

<KnowledgeCard :points='["链路：源码 → tokenizer → PEG parser → AST → 编译器 → code object → ceval 虚拟机", "ast.parse 只解析不执行；ast.literal_eval 只求值字面量，遇非字面量抛 ValueError，替代 eval", "compile 的 mode 三选 exec/eval/single；optimize 1 移除 assert、2 再移除 docstring", "code object 存 co_code/co_consts/co_names/co_stacksize；3.10 换 co_linetable、3.11 加 co_exceptiontable", "常量折叠在编译期完成，co_consts 里直接出现结果，运行时没有 BINARY_OP", "NodeTransformer 改写后必须 copy_location 或 fix_missing_locations，否则行号表失真"]' :pitfalls='["用 eval / exec 解析外部传入的字符串当数据", "NodeTransformer 改写后直接 compile，traceback 行号错乱", "把某一版本的 co_code 指令或优化结论当语言规范", "把 ast.literal_eval 写成 eval，或在编译期优化里改坏行号信息，会让调试栈失去意义"]' summary='解释器执行的是编译后的字节码，源码只参与最前面一步；用 ast 改写代码结构比字符串替换可靠得多' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 链路：源码 → tokenizer → PEG parser → AST → 编译器 → code object → ceval 虚拟机 | 建立直觉 |
| ast.parse 只解析不执行；ast.literal_eval 只求值字面量，遇非字面量抛 ValueError，替代 eval | 跑通示例 |
| compile 的 mode 三选 exec/eval/single；optimize 1 移除 assert、2 再移除 docstring | 深入边界 |
| code object 存 co_code/co_consts/co_names/co_stacksize；3.10 换 co_linetable、3.11 加 co_exceptiontable | 工程落地 |
| 常量折叠在编译期完成，co_consts 里直接出现结果，运行时没有 BINARY_OP | 随堂检测 |
| NodeTransformer 改写后必须 copy_location 或 fix_missing_locations，否则行号表失真 | 复盘 |

1. 链路：源码 → tokenizer → PEG parser → AST → 编译器 → code object → ceval 虚拟机

2. ast.parse 只解析不执行；ast.literal_eval 只求值字面量，遇非字面量抛 ValueError，替代 eval

3. compile 的 mode 三选 exec/eval/single；optimize 1 移除 assert、2 再移除 docstring

[下一讲：字节码、栈式虚拟机与 dis 实战](/core/bytecode)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/049-compile-pipeline.py`

```bash
python3 examples/lessons/049-compile-pipeline.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/049-compile-pipeline.py) · [全部示例代码索引](/examples/)
