---
title: 第 016 讲 · 阶段综合：交互式命令行计算器
description: 把语法地基串成一个能用的小程序
---

<StageHeader stage='L1 · 编程地基' level='★★☆☆☆' time='45 分钟' goal='把语法地基串成一个能用的小程序' prereq='第 015 讲 · 异常：捕获、异常链与自定义异常' />

# 第 016 讲 · 阶段综合：交互式命令行计算器

到上一讲为止，对象、变量、类型、流程、输入输出和异常都露过面，却还停在一行行小例子里。这一讲是地基阶段的收束：第一次把它们装成能反复打开、能测试的小东西。

设想一个交互式计算器，敲一行算式回一个结果，输错不让程序停下，按 `Ctrl+C` 也能体面退出，金额不差那一分钱。我们先把需求拆成输入循环、求值、提示与重试几块，再给表达式求值划一条安全边界，不把解释器交到用户手上；最后做函数拆分与单一职责，给每步留可自动跑的测试入口。需要你带着条件循环、函数、字符串与数值类型，以及异常捕获和输入输出来。做完你会有一个带帮助、能优雅退出的命令行工具。


## 一个能被输入反噬的交互式计算器

一个内部工具让用户在网页里输入算式，后端直接 `eval(request.form['expr'])`。

上线第三天安全扫描就报了命令注入：有人输入 `__import__('os').system(...)` 一类表达式，`eval` 老老实实编译并执行，把服务器当成了跳板。

团队第一反应是给 `eval` 传入 `{'__builtins__': {}}` 限制内建，结果 `().__class__.__bases__[0].__subclasses__()` 这条属性链照样能绕到文件相关类——CPython 里一切皆对象，限制 `globals` 从来不是安全边界。

第二版改用 `ast.parse` 配合 `mode='eval'` 只生成语法树，再递归只放行数字字面量与加减乘除节点，安全了却冒出新问题：金额用 `float` 算 `0.1 + 0.2` 得到 `0.30000000000000004`，对账差一分钱；管道输入结束时 `input()` 抛 `EOFError`、`Ctrl+C` 抛 `KeyboardInterrupt`，两个分支都没接，CLI 甩出一堆栈 `Traceback`。

本讲把求值、精度、输入循环与重试拆成四个可单测的函数，并说明为什么安全边界必须落在语法层而不是 `globals` 层。


## eval 为什么不能当沙箱：属性链逃逸与 compile 链路

`eval(expr)` 的实质是把字符串交给编译器生成 code object，再交给 `ceval` 执行，因此表达式里出现的任何名字、调用、属性访问都会真的运行。

给 `eval` 传一个把内建名字表清空的 `globals`（`{'__builtins__': {}}`）只是切断了内建查找，挡不住语法本身：CPython 里每个值都是对象，从空元组出发 `().__class__` 拿到 `type`，`.__bases__[0]` 拿到 `object`，再调 `__subclasses__()` 就能列出进程里所有已加载的子类，其中常有与文件、`os` 模块相关的类，进而读文件或执行命令，这就是著名的沙箱逃逸。

把 `globals` 换成自定义 dict、用正则过滤关键字、限制字符串长度，都是在同一层打补丁，无法给出可证明的边界。

可靠的做法是把边界放在语法层：`ast.parse(s, mode='eval')` 只做词法与语法分析，返回 `Expression` 节点而不执行任何代码；随后由我们自己的解释器递归遍历，只放行 `ast.Constant`（数字）、`ast.BinOp` 配白名单运算符、`ast.UnaryOp` 配正负号，遇到 `ast.Call` / `ast.Name` / `ast.Attribute` / `ast.Subscript` 立即抛 `ValueError`。

`ast.literal_eval` 是同一思路的内置实现，但它只接受字面量与容器，遇到 `1 + 2` 这类 `BinOp` 会抛 `ValueError`，因此适合读配置、不适合做计算器。

```python
import ast, operator

OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def evaluate(expr):
    tree = ast.parse(expr, mode='eval')
    return _eval(tree.body)

def _eval(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPS:
        return OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](_eval(node.operand))
    raise ValueError('unsupported syntax')

for s in ('1 + 2 * 3', '(4 + 6) / 2', '-3 ** 2', '2 ** 10'):
    print(s, '=', evaluate(s))
for bad in ('abs(-2)', '1 / 0', 'x + 1'):
    try:
        evaluate(bad)
    except (ValueError, ZeroDivisionError) as e:
        print('reject', repr(bad), type(e).__name__)
```

<OutputBox title='主示例运行结果' output='1 + 2 * 3 = 7\n(4 + 6) / 2 = 5.0\n-3 ** 2 = -9\n2 ** 10 = 1024\nreject &#39;abs(-2)&#39; ValueError\nreject &#39;1 / 0&#39; ZeroDivisionError\nreject &#39;x + 1&#39; ValueError' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import ast, operator\n\nOPS = {\n    ast.Add: operator.add,\n    ast.Sub: operator.sub,\n    ast.Mult: operator.mul,\n    ast.Div: operator.truediv,\n    ast.Pow: operator.pow,\n    ast.Mod: operator.mod,\n}\nUNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}\n\ndef evaluate(expr):\n    tree = ast.parse(expr, mode=&#39;eval&#39;)\n    return _eval(tree.body)\n\ndef _eval(node):\n    if isinstance(node, ast.Constant) and type(node.value) in (int, float):\n        return node.value\n    if isinstance(node, ast.BinOp) and type(node.op) in OPS:\n        return OPS[type(node.op)](_eval(node.left), _eval(node.right))\n    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:\n        return UNARY[type(node.op)](_eval(node.operand))\n    raise ValueError(&#39;unsupported syntax&#39;)\n\nfor s in (&#39;1 + 2 * 3&#39;, &#39;(4 + 6) / 2&#39;, &#39;-3 ** 2&#39;, &#39;2 ** 10&#39;):\n    print(s, &#39;=&#39;, evaluate(s))\nfor bad in (&#39;abs(-2)&#39;, &#39;1 / 0&#39;, &#39;x + 1&#39;):\n    try:\n        evaluate(bad)\n    except (ValueError, ZeroDivisionError) as e:\n        print(&#39;reject&#39;, repr(bad), type(e).__name__)' :notes='["导入 ast 做语法分析、operator 把运算符节点映射成函数，全程不调用 eval", "空行，只用于分隔逻辑块，不影响执行结果。", "用字典把二元运算 AST 节点类型映射到 operator 的算术函数", "加法节点对应 operator.add", "减法节点对应 operator.sub", "乘法节点对应 operator.mul", "除法用 truediv，返回 float 与 Python 语义一致", "乘方映射到 pow，-3 ** 2 的优先级由语法树决定", "取模映射到 mod", "字典结束；不在白名单里的运算符会走到后面的拒绝分支", "一元正负号单独一张表，映射到 operator.pos 与 operator.neg", "空行，只用于分隔逻辑块，不影响执行结果。", "对外入口：接收字符串，返回数值", "mode=&#39;eval&#39; 只解析单个表达式，返回 Expression 而非 Module", "把表达式主体交给递归求值器", "空行，只用于分隔逻辑块，不影响执行结果。", "递归遍历语法树，只对白名单节点求值", "3.8 起字面量统一为 ast.Constant；按 value 实际类型放行 int 与 float，排除 bool", "字面量直接返回，不执行任何代码", "二元运算且运算符在白名单内才处理", "查表取函数，递归求值左右子树，绝不 eval 字符串", "一元运算同样查表", "对操作数递归求值后取正或取负", "Call / Name / Attribute 等一律拒绝，这是安全边界的核心", "空行，只用于分隔逻辑块，不影响执行结果。", "四个合法表达式，覆盖优先级、括号、一元负号与乘方", "逐个求值并打印", "三个危险或非法输入：函数调用、除零、名字引用", "把求值包在 try 里，异常转成可读的拒绝信息", "触发白名单拒绝或算术异常", "只捕获预期两类异常，不用裸 except", "打印被拒输入与异常类型，作为可测的输出"]' title='第 016 讲 · 阶段综合：交互式命令行计算器' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

`eval` 与 `exec` 的本质是把字符串交给编译器生成 code object 再交给 `ceval` 执行，因此能触达任意名字与内建；把 `__builtins__` 设为空字典只切断了内建查找，但 CPython 里所有值都是对象，`().__class__.__bases__[0].__subclasses__()` 这条属性链能从任意字面量走到 `object` 的全部子类并找到文件与 `os` 相关类，这就是沙箱逃逸，所以限制 `globals` 从来不是可证明的安全边界。

可靠做法是限制语法本身：`ast.parse(s, mode='eval')` 只做词法与语法分析生成抽象语法树，不执行任何代码；解释器只递归处理白名单节点，遇到 `ast.Call` / `ast.Name` / `ast.Attribute` / `ast.Subscript` 立即抛错。

3.8 起字面量统一为 `ast.Constant`，旧 `ast.Num` 等变成兼容别名，判断时要用 `isinstance` 并检查 `node.value` 的实际类型，`bool` 是 `int` 的子类必须显式排除。

精度是另一条独立轴：`float` 用二进制 `IEEE 754` 表示，0.1 无法精确存储；`decimal.Decimal` 以十进制整数加指数保存，配合 `getcontext().prec`（默认 28）做可控舍入。

把解析、求值、渲染、输入循环拆开，正因为这四件事的失败模式与测试手段完全不同。

<ConceptDiagram type='flow4' title='第 016 讲 · eval 为什么不能当沙箱：属性链逃逸与 compile 链路' labels='eval 为什么不能当沙箱：属性链逃逸与 c…|AST 白名单与字面量判断的版本细节|输入循环、精度与函数拆分|命令行参数与帮助' caption='把语法地基串成一个能用的小程序' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 表达式求值方式对照：别把解释器交给用户

**表达式求值方式对照**

| 方式 | 能做什么 | 安全边界 | 适用场景 |
| --- | --- | --- | --- |
| eval(expr) | 执行任意 Python 表达式 | 无：可调用 __import__ 等任意内建 | 仅完全可信的输入 |
| eval(expr, &#123;'__builtins__': &#123;&#125;&#125;, &#123;&#125;) | 执行表达式但内建表被清空 | 仍可经对象属性链逃逸，不构成边界 | 不足以作为安全边界 |
| ast.literal_eval(expr) | 只求值字面量与容器 | 拒绝 BinOp / Call / Name | 读取配置里的列表、字典字面量 |
| ast.parse + 节点白名单 | 在白名单内解释运算 | 只放行 Constant / BinOp / UnaryOp 与指定运算符 | 计算器一类受限表达式求值 |


## AST 白名单与字面量判断的版本细节

写白名单求值器有两个容易出错的点。

第一是节点类：Python 3.8 起 `ast.Num` / `ast.Str` / `ast.Bytes` / `ast.NameConstant` 被统一的 `ast.Constant` 取代，旧类退化为兼容别名（3.12 起访问会触发 `DeprecationWarning`），所以判断要用 `isinstance` 检查节点是不是 `ast.Constant`，而不是写 `type(node) is ast.Num` 这种硬比较。

第二是值类型：`bool` 是 `int` 的子类，若只写 `isinstance(node.value, int)`，`True` 与 `False` 会被当成 1 与 0 参与运算；正确写法是判断 `type(node.value)` 落在 `(int, float)` 里，显式把 `bool` 排除。

运算符不要用一长串 `if/elif`，直接建一张 `OPS` 映射表，把 `ast.Add`、`ast.Sub` 这些节点对应到 `operator.add`、`operator.sub`，递归时用 `OPS[type(node.op)]` 取函数，既短又能保证白名单之外的节点必然走到拒绝分支。

优先级完全不用自己实现：`-3 ** 2` 的语法树外层是 `UnaryOp`、内层才是乘方 `BinOp`，递归结构天然体现「乘方先于一元负号」，结果是 -9；写成 `(-3) ** 2` 才是 9。切片式越权、函数调用、名字引用、属性访问都在默认拒绝分支里被拦下，这个默认拒绝而不是默认放行，是整段代码的安全关键。

```python
import ast
from decimal import Decimal, getcontext

getcontext().prec = 28
print('float', 0.1 + 0.2)
print('decimal', Decimal('0.1') + Decimal('0.2'))
print('literal_eval', ast.literal_eval('[1, 2, 3]'))
try:
    print(ast.literal_eval('1 + 2'))
except ValueError as e:
    print('literal_eval reject', type(e).__name__)
print('eval runs call', eval('len([1, 2, 3])'))
print('restricted eval', eval('40 + 2', {'__builtins__': {}}, {}))
```

<OutputBox title='对照写法：先自己猜，再点开' output='float 0.30000000000000004\ndecimal 0.3\nliteral_eval [1, 2, 3]\nliteral_eval reject ValueError\neval runs call 3\nrestricted eval 42' guess="true" />


## 输入循环、精度与函数拆分

把计算器做成能用的 CLI，还要处理三类与求值无关但同样致命的边界。

输入循环里 `input()` 遇到 EOF（`Ctrl+D` 或管道结束）抛 `EOFError`，遇到 `Ctrl+C` 抛 `KeyboardInterrupt`；后者继承 `BaseException` 而非 `Exception`，必须单独捕获，否则 `except Exception` 拦不住它，程序会带栈退出。

空行与非法语法让 `ast.parse` 抛 `SyntaxError`，除零让 `operator.truediv` 抛 `ZeroDivisionError`，这些应转成一行提示后 `continue`，而不是终止进程。

精度是独立的第二条轴：`float` 用二进制 `IEEE 754` 表示，0.1 无法精确存储，金额场景要改用 `decimal.Decimal`，`Decimal(str(0.1))` 才是精确的 0.1（直接 `Decimal(0.1)` 会把二进制误差带进来），有效位数由 `getcontext().prec` 控制、默认 28，除零时 `decimal.DivisionByZero` 作为 `ZeroDivisionError` 的子类被一并捕获。

工程上把 `parse`、`compute`、`render`、`main_loop` 拆开：前两个是纯函数，单元测试直接对字符串断言返回值，不必 monkeypatch `stdin` 或捕获 `stdout`；命令行层用 `argparse.ArgumentParser` 提供 `--precision` 与自动生成的 `--help`，把可配参数与业务逻辑隔开。


## 交互式计算器：输入循环、AST 白名单、Decimal 精度与可测函数拆分

把这个小 CLI 拆成四个互不耦合的函数：`compute` 在 `Decimal` 上递归求值，`evaluate` 负责 `ast.parse` 生成语法树，`render` 只管把结果或异常格式化成字符串，`main` 处理参数与这一轮示范输入。

这样 `compute` 与 `evaluate` 是纯函数，单元测试可以直接对表达式字符串断言返回值，不需要模拟 `stdin` 或捕获 `stdout`。

精度用 `decimal.Decimal` 而不是 `float`：`Decimal(str(node.value))` 把 0.1 精确转成十进制 0.1，`getcontext().prec` 设为 28 决定有效位数，除零时 `decimal.DivisionByZero` 作为 `ZeroDivisionError` 的子类被转成提示。

命令行层用 `argparse.ArgumentParser` 提供 `--precision` 与自动生成的 `--help`，把用户可配参数与求值逻辑隔开；真实工程再把每轮异常与耗时写进日志，但核心边界在这四个函数里已经定死。

```python
import argparse, ast, operator
from decimal import Decimal, getcontext

BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub,
          ast.Mult: operator.mul, ast.Div: operator.truediv,
          ast.Pow: operator.pow}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def compute(node):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return Decimal(str(node.value))
    if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
        return BINOPS[type(node.op)](compute(node.left), compute(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](compute(node.operand))
    raise ValueError('unsupported node: ' + type(node).__name__)

def evaluate(expr):
    return compute(ast.parse(expr, mode='eval').body)

def render(expr):
    try:
        return str(evaluate(expr))
    except (ValueError, SyntaxError, ZeroDivisionError) as e:
        return 'error: ' + type(e).__name__

def main():
    p = argparse.ArgumentParser(description='safe calculator')
    p.add_argument('--precision', type=int, default=28)
    args = p.parse_args([])
    getcontext().prec = args.precision
    for expr in ('1 + 2 * 3', '0.1 + 0.2', '1 / 0', 'abs(-2)'):
        print(expr, '=', render(expr))

main()
```

<Callout type="idea" title='落地提示' text='真实 CLI 要处理 EOF、Ctrl+C、非数字输入与精度需求，并为每一步留可自动化的测试入口' />


## 失败模式与上线前自检

eval 传 &#123;'__builtins__': &#123;&#125;&#125; 挡不住沙箱逃逸：().`__class__.__bases__[0].__subclasses__()` 照样摸到文件类，所以白名单只放行 `ast.Constant`、BinOp、UnaryOp，遇 Call、Name 抛 ValueError。

3.8 起字面量统一 `ast.Constant`，判断 value 要排除 bool（int 子类）；输入侧 EOFError、KeyboardInterrupt 单独捕，除零转成提示。下表按失败模式、根因、防线列出。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 eval 直接算用户输入的表达式，服务被植入任意命令 | eval 会编译并执行任意表达式，__import__('os').system(...) 一类调用能读写文件与发起网络请求 | 改为 ast.parse(mode='eval') 加节点白名单递归求值；只放行 Constant / BinOp / UnaryOp，遇 Call 与 Name 抛 ValueError |
| 以为清空 __builtins__ 就安全了 | CPython 一切皆对象，通过 ().__class__.__bases__[0].__subclasses__() 属性链可绕过空内建表找到敏感类 | 不要试图给 eval 做沙箱；从语法层用 AST 白名单杜绝一切可执行节点 |
| EOF 或 Ctrl+C 时计算器抛一堆栈 Traceback 或卡死 | input() 遇 EOF 抛 EOFError、遇 Ctrl+C 抛 KeyboardInterrupt，后者不在 Exception 之下，容易被漏掉 | 循环里分别捕获 EOFError 与 KeyboardInterrupt 做优雅退出；SyntaxError / ZeroDivisionError / ValueError 转提示后 continue |

<Callout type="warn" title='本讲最容易踩的坑' text='用 eval 直接算用户输入的表达式，服务被植入任意命令：eval 会编译并执行任意表达式，__import__(&#39;os&#39;).system(...) 一类调用能读写文件与发起网络请求' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 eval 直接算用户输入的表达式，服务被…", "body": "eval 会编译并执行任意表达式，__import__(&#39;os&#39;).system(...) 一类调用能读写文件与发起网络请求", "tip": "改为 ast.parse(mode=&#39;eval&#39;) 加节点白名单递归求值；只放行 Constant / BinOp / UnaryOp，遇 Call 与 Name 抛 ValueError"}, {"title": "第 2 步：以为清空 __builtins__ 就安全了", "body": "CPython 一切皆对象，通过 ().__class__.__bases__[0].__subclasses__() 属性链可绕过空内建表找到敏感类", "tip": "不要试图给 eval 做沙箱；从语法层用 AST 白名单杜绝一切可执行节点"}, {"title": "第 3 步：EOF 或 Ctrl+C 时计算器抛一堆栈…", "body": "input() 遇 EOF 抛 EOFError、遇 Ctrl+C 抛 KeyboardInterrupt，后者不在 Exception 之下，容易被漏掉", "tip": "循环里分别捕获 EOFError 与 KeyboardInterrupt 做优雅退出；SyntaxError / ZeroDivisionError / ValueError 转提示后 continue"}]' />


## 练习题与交付验收

<Exercise title='基础：给白名单求值器补上乘方与取模' task='在安全求值器里补上 ** 与 % 两个运算符，验证 -3 ** 2 得到 -9（Python 中乘方优先级高于一元负号），并确认 abs(-2) 仍被拒绝。' solution='import ast, operator\nOPS = {ast.Add: operator.add, ast.Sub: operator.sub,\n       ast.Mult: operator.mul, ast.Div: operator.truediv,\n       ast.Pow: operator.pow, ast.Mod: operator.mod}\n\ndef ev(n):\n    if isinstance(n, ast.Constant) and type(n.value) in (int, float):\n        return n.value\n    if isinstance(n, ast.BinOp) and type(n.op) in OPS:\n        return OPS[type(n.op)](ev(n.left), ev(n.right))\n    if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):\n        return -ev(n.operand)\n    raise ValueError(&#39;reject&#39;)\n\nfor s in (&#39;-3 ** 2&#39;, &#39;2 ** 10&#39;, &#39;7 % 3&#39;, &#39;abs(-2)&#39;):\n    try:\n        print(s, &#39;=&#39;, ev(ast.parse(s, mode=&#39;eval&#39;).body))\n    except ValueError:\n        print(s, &#39;= rejected&#39;)' explain='AST 白名单把运算映射到 operator 函数，乘方优先级由语法树结构天然保证，不需要自己写优先级解析；遇到 Call 节点走默认拒绝分支。用 operator 查表而不是一长串 if/elif，既短又能保证白名单之外的节点必定被拒。' />

<Exercise title='进阶：给计算器写不依赖 stdin 与 stdout 的单元测试' task='把 evaluate 与输入循环解耦，写一组断言覆盖正常运算、非法节点、除零与 EOF 分支；说明为什么求值做成纯函数后测试不需要 monkeypatch。' solution='import ast, unittest\n\ndef evaluate(expr):\n    n = ast.parse(expr, mode=&#39;eval&#39;).body\n    def ev(x):\n        if isinstance(x, ast.Constant) and type(x.value) in (int, float):\n            return x.value\n        if isinstance(x, ast.BinOp) and isinstance(x.op, ast.Add):\n            return ev(x.left) + ev(x.right)\n        if isinstance(x, ast.BinOp) and isinstance(x.op, ast.Div):\n            return ev(x.left) / ev(x.right)\n        raise ValueError(&#39;reject&#39;)\n    return ev(n)\n\ndef classify(expr):\n    if expr is None:\n        return &#39;eof&#39;\n    try:\n        return &#39;ok:&#39; + str(evaluate(expr))\n    except SyntaxError:\n        return &#39;syntax&#39;\n    except ZeroDivisionError:\n        return &#39;divzero&#39;\n    except ValueError:\n        return &#39;reject&#39;\n\nclass T(unittest.TestCase):\n    def test_cases(self):\n        self.assertEqual(classify(&#39;1 + 2&#39;), &#39;ok:3&#39;)\n        self.assertEqual(classify(None), &#39;eof&#39;)\n        self.assertEqual(classify(&#39;abs(1)&#39;), &#39;reject&#39;)\n        self.assertEqual(classify(&#39;1 / 0&#39;), &#39;divzero&#39;)\n\nsuite = unittest.TestLoader().loadTestsFromTestCase(T)\nresult = unittest.TextTestRunner(verbosity=0).run(suite)\nprint(&#39;tests&#39;, result.wasSuccessful(), result.testsRun, &#39;run&#39;)' explain='把求值做成纯函数、输入循环只负责 IO，测试就能直接对字符串断言返回值；classify 把异常翻译成可断言的标签，EOF 用 None 表示，四分支都不需要 patch 标准输入输出。' />

<Quiz no='016-1' q='为什么 eval(expr, {&#39;__builtins__&#39;: {}}, {}) 仍不算安全边界？' :options='["因为 eval 仍会执行任意语法节点", "可通过对象属性链 __class__.__bases__ 逃逸到内置类", "因为 __builtins__ 会被解释器自动补回", "因为空字典会抛 TypeError"]' answer="1" explain='CPython 一切皆对象，().__class__.__bases__[0].__subclasses__() 能从字面量走到所有子类并触达文件相关类；限制 globals 挡不住属性访问。显式给空 __builtins__ 时解释器并不会补回。' />

<Quiz no='016-2' q='用 AST 白名单求值时，对字面量节点最稳妥的判断是？' :options='["isinstance(node, ast.Num)", "type(node.value) is int", "isinstance(node, ast.Constant) 且检查 value 实际类型并排除 bool", "直接 int(node.value)"]' answer="2" explain='3.8 起字面量统一为 ast.Constant，ast.Num 只是废弃别名；且 bool 是 int 子类，若不排除 True 会被当成 1 参与运算。' />

<Quiz no='016-3' q='交互式计算器里，Ctrl+C 触发的是哪个异常？' :options='["EOFError", "KeyboardInterrupt，直接继承 BaseException", "SyntaxError", "ValueError"]' answer="1" explain='input() 遇 EOF 抛 EOFError，遇 Ctrl+C 抛 KeyboardInterrupt；后者继承 BaseException 而非 Exception，必须单独捕获，否则 except Exception 拦不住。' />

<KnowledgeCard :points='["eval / exec 会把字符串编译成 code object 并执行；清空 __builtins__ 挡不住 __class__.__bases__ 属性链逃逸", "安全边界在语法层：ast.parse(mode=&#39;eval&#39;) 只生成语法树，递归只放行 Constant / BinOp / UnaryOp 白名单节点", "3.8 起字面量统一 ast.Constant；判断 value 类型时排除 bool（它是 int 子类）", "float 存不下十进制 0.1，精度敏感用 decimal.Decimal 加 getcontext().prec（默认 28）", "input() 的 EOFError 与 KeyboardInterrupt 要分别捕获；后者不在 Exception 之下", "把 parse / compute / render / main_loop 拆开，求值做成纯函数才能不 patch stdin 就单测"]' :pitfalls='["用 eval 直接算用户输入的表达式，服务被植入任意命令", "以为清空 __builtins__ 就安全了", "EOF 或 Ctrl+C 时计算器抛一堆栈 Traceback 或卡死", "用 eval 直接执行用户输入的表达式等于把解释器交给用户，是典型的命令注入入口"]' summary='综合项目的重点不是算式多复杂，而是把输入、解析、计算、报错、重试拆成各自可测的函数' />

1. eval / exec 会把字符串编译成 code object 并执行；清空 __builtins__ 挡不住 __class__.__bases__ 属性链逃逸

2. 安全边界在语法层：ast.parse(mode='eval') 只生成语法树，递归只放行 Constant / BinOp / UnaryOp 白名单节点

3. 3.8 起字面量统一 ast.Constant；判断 value 类型时排除 bool（它是 int 子类）

[下一讲：序列协议与通用操作](/containers/sequence)

<Predict no='016-4' q='对表达式 -3 ** 2 用 AST 白名单求值（USub 取负、Pow 求幂），结果是多少？' :options='["9", "-9", "报错，因为一元负号不能被求值"]' answer='1' output='-9' explain='Python 语法里 ** 优先级高于一元负号，语法树是 UnaryOp(USub, BinOp(3, Pow, 2))；先算 3 ** 2 得 9 再取负得到 -9。写成 (-3) ** 2 才是 9，语法树结构直接编码了优先级。' />

<FillBlank no='016-5' tpl='___ ast, operator' :answers='["import"]' hint='回想本讲关于 需求拆解与输入循环 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 eval 为什么不能当沙箱：属性链逃逸与 compile 链路 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/016-capstone.py`

```bash
python3 examples/lessons/016-capstone.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/016-capstone.py) · [全部示例代码索引](/examples/)
