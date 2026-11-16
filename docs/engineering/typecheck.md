---
title: 第 074 讲 · 静态检查：mypy / pyright 与渐进式类型
description: 让类型契约在 CI 中真正生效
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='35 分钟' goal='让类型契约在 CI 中真正生效' prereq='第 073 讲 · 代码规范：PEP 8、ruff、black 与 pre-commit' />

# 第 074 讲 · 静态检查：mypy / pyright 与渐进式类型

风格统一之后，仍有一类错它管不着：把字符串当成数字传进计费逻辑，外表一样平静。一个公共函数没写返回类型，又调了没标注的第三方库，调用链上十几处都被推成 Any；赶进度加了一堆忽略注释，检查器从此一片绿，直到夜里才出事。

从检查器的配置与严格度起步，走到 stub 与第三方库的标注，再看泛型不变性和 Any 怎样沿调用链扩散，接着谈忽略注释的治理，最后说清静态检查与运行时校验如何互补。带着类型注解、函数与泛型的基础来；学完能从公共 API 与数据边界逐步加类型，把未覆盖的文件列成清单慢慢清零。


## 一个没写返回类型的函数，让十几处调用全被推断成 Any

一个数据平台的公共函数 `read_config()` 没写返回类型，内部调用了某个没有类型标注的第三方 SDK，调用链上十几处地方全被推断成 Any。有人为赶进度在几十个文件里加了 `# type: ignore`，mypy 从此一片绿，直到某次把字符串当 int 传进计费逻辑才在夜里炸——静态检查早被这些口子架空了。

另一类事故是误以为注解会在运行时校验：`add('x', 'y')` 照样返回 'xy'，而 `isinstance(x, list[int])` 直接抛 TypeError。

静态类型的收益与覆盖率成正比，Any 会像漏洞一样沿调用链传播。本讲把检查器配置、stub 与 `py.typed`、泛型不变性、ignore 治理，以及与运行时校验的互补关系讲成能落地的 CI 契约。

<Callout type="warn" title='先看一个真实会出错的写法' text='为赶进度满仓 # type: ignore：抑制口子越开越多，检查器变装饰，缺陷集中躲在最难查处' />


## mypy 与 pyright：配置项与严格度怎么选

mypy 配置在 `mypy.ini` 或 `pyproject.toml` 的 `[tool.mypy]`：`strict = True` 一次打开 `disallow_untyped_defs`、`check_untyped_defs`、`warn_return_any`、`no_implicit_optional`、`warn_unused_ignores` 等一组开关；`ignore_missing_imports` 与 `follow_imports = 'skip'` 用来处理无标注的第三方库；`[tool.mypy.overrides]` 下把某个模块设成 `ignore_errors = True`，可对老代码按模块降严格度。

命令行等价写法是 `mypy --strict`。

pyright（Pylance 的底层）读 `pyrightconfig.json` 或 `[tool.pyright]`，核心是 `typeCheckingMode='strict'`（也可取 basic、off）与 `reportUnknownMemberType`、`reportMissingTypeStubs` 等细粒度开关。

两者都提供 `reveal_type(x)`：这是检查器的特殊内建，只在静态分析时打印推断类型，运行时并不存在，不能当普通函数调用。渐进式接入的正确顺序是从公开 API 与数据边界（IO、配置、DB 行）开始加类型，按目录逐步提高严格度，把未覆盖文件列成清单逐步清零，而不是一上来全仓 strict 后满仓 ignore。

**mypy / pyright 配置项与严格度**

| 配置 / 命令 | 作用 | 开启后的效果 |
| --- | --- | --- |
| mypy --strict pkg/ | 一次打开一组严格开关 | 未标注函数、返回 Any、隐式 Optional 都报错 |
| [tool.mypy] strict = True | 等价命令行 --strict | 配置随仓库提交，CI 一致 |
| disallow_untyped_defs | 禁止无注解函数 | 堵住 Any 的源头 |
| warn_return_any / disallow_any_generics | 治理 Any 传播 | 返回 Any 或裸泛型即告警 |
| [[tool.mypy.overrides]] module='legacy.*' | 按模块降严格度 | 老代码渐进接入，不污染新代码 |
| pyright typeCheckingMode='strict' | pyright 总严格度 | 逐项 report* 开关可细调 |
| reveal_type(x) | 静态分析内建 | 打印推断类型，运行时不存在 |

<Callout type="tip" title='核心心智模型' text='mypy 配置在 `mypy.ini` 或 `pyproject.toml` 的 `[tool.mypy]`：`strict = True` 一次打开 `disallow_untyped_defs`、`check_untyped_defs`、`warn_return_any`…' />

<ConceptDiagram type='compare2' title='第 074 讲 · 检查器配置与严格度：mypy 与 pyright' labels='检查器配置与严格度：mypy 与 pyrig…|stub、py.typed 与 Any 的传…|泛型不变性、协议与运行时互补|与运行时校验互补' caption='让类型契约在 CI 中真正生效' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### strict 与渐进加严的目录级策略

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段七 · 工程化与质量 |
| 前置 | 第 073 讲 · 代码规范：PEP 8、ruff、black 与 pre-commit |
| 难度 / 建议时长 | ★★★☆☆ · 35 分钟 |
| 本讲新增 | 检查器配置与严格度、stub 与第三方库、泛型与不变性 |
| 一句话目标 | 让类型契约在 CI 中真正生效 |
| 为下一讲铺垫 | 单元测试：pytest、fixture 与参数化 |


## 注解在 CPython 里只是 __annotations__ 元数据

注解在 CPython 里只是函数对象 `__annotations__` 字典里的元数据：默认在定义时求值成类型对象（到 3.13 仍如此，3.14 起 PEP 649 改为惰性求值），PEP 563 的 future 导入则把它们编译成字符串常量，`typing.get_type_hints` 再在函数的 `__globals__` 与局部命名空间里 eval 还原，所以用 exec 动态定义的函数也能被解析。

`list[int]` 在运行时是 `types.GenericAlias`，其 `__instancecheck__` 未实现，isinstance 检测到第二参数是参数化泛型就抛 TypeError。

静态检查器不走运行时：它解析 AST 建符号表与类型图，做约束求解与子类型判定；Any 被定义成同时是格顶与格底（与任意类型双向兼容），因此一旦进入表达式就短路后续检查并沿返回值传播，这正是 `warn_return_any` 要卡的点。

PEP 561 的 `py.typed` 是个空标记文件，检查器据此决定是否读取该包的行内注解；没有它，stub（`.pyi`）或 Any 就是唯一出路。

<Term word='检查器配置与严格度' text='mypy 配置在 `mypy.ini` 或 `pyproject.toml` 的 `[tool.mypy]`：`strict = True` 一次打开 `disallow_untyped_defs`、`check_untyped_defs`、`warn_return_any`…' />

<Term word='stub 与第三方库' text='PEP 561 规定：一个包只有在自身里带上 `py.typed` 标记文件，检查器才会使用它的内联注解；缺了这个标记，即便源码写了类型，第三方项目 import 它时也会被当成无类型，名字全部退化成 Any。无标注的库靠 stub 文件（`.pyi`）补：typeshed 随检查器附带标准库与常见第三方库的 stub…' />


## 对照：isinstance(x, list[int]) 与运行时校验

```python
import typing, inspect

def add(a: int, b: int) -> int:
    return a + b

print('hints', {k: v.__name__ for k, v in typing.get_type_hints(add).items()})
print('signature', str(inspect.signature(add)))
try:
    isinstance([1, 2], list[int])
except TypeError as e:
    print('isinstance generic raises TypeError', 'generic' in str(e).lower())
x: typing.Any = 'not an int'
y: int = x
print('Any to int at runtime', y)
```

<OutputBox title='主示例运行结果' output='hints {&#39;a&#39;: &#39;int&#39;, &#39;b&#39;: &#39;int&#39;, &#39;return&#39;: &#39;int&#39;}\nsignature (a: int, b: int) -&gt; int\nisinstance generic raises TypeError True\nAny to int at runtime not an int' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import typing, inspect\n\ndef add(a: int, b: int) -&gt; int:\n    return a + b\n\nprint(&#39;hints&#39;, {k: v.__name__ for k, v in typing.get_type_hints(add).items()})\nprint(&#39;signature&#39;, str(inspect.signature(add)))\ntry:\n    isinstance([1, 2], list[int])\nexcept TypeError as e:\n    print(&#39;isinstance generic raises TypeError&#39;, &#39;generic&#39; in str(e).lower())\nx: typing.Any = &#39;not an int&#39;\ny: int = x\nprint(&#39;Any to int at runtime&#39;, y)' :notes='["导入 typing 读类型、inspect 读运行时签名", "空行，只用于分隔逻辑块，不影响执行结果。", "定义带完整注解的函数，注解默认只是元数据", "函数体不校验类型，直接相加", "空行，只用于分隔逻辑块，不影响执行结果。", "get_type_hints 解析出参数与返回值的真实类型对象", "inspect.signature 显示注解串，证明注解随函数保存", "准备验证参数化泛型能否用于 isinstance", "list[int] 是参数化泛型，不能作 isinstance 第二参数", "捕获预期的 TypeError", "错误信息含 generic，确认是参数化泛型被拒", "把字符串赋给 Any 类型变量，静态检查不拦截", "再赋给声明为 int 的名字，运行时毫无检查", "打印证明注解不强制：y 实际是字符串"]' title='第 074 讲 · 静态检查：mypy / pyright 与渐进式类型' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import typing

ns = {}
exec('from __future__ import annotations' + chr(10)
     + 'def f(x: int) -> str:' + chr(10)
     + '    return str(x)', ns)
f = ns['f']
print('stored as string', isinstance(f.__annotations__['x'], str))
print('resolved hints', {k: getattr(v, '__name__', str(v)) for k, v in typing.get_type_hints(f).items()})
```

<OutputBox title='对照写法：先自己猜，再点开' output='stored as string True\nresolved hints {&#39;x&#39;: &#39;int&#39;, &#39;return&#39;: &#39;str&#39;}' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import typing, inspect\n\ndef add(a: int, b: int) -&gt; int:\n    return a + b\n\nprint(&#39;hints&#39;, {k: v.__name__ for k, v in typing.get_type_hints(add).items()})\nprint(&#39;signature&#39;, str(inspect.signature(add)))\ntry:\n    isinstance([1, 2], list[int])\nexcept TypeError as e:\n    print(&#39;isinstance generic raises TypeError&#39;, &#39;generic&#39; in str(e).lower())\nx: typing.Any = &#39;not an int&#39;\ny: int = x\nprint(&#39;Any to int at runtime&#39;, y)", "note": "检查器配置与严格度：mypy 与 pyright"}, {"label": "对照 / 进阶", "code": "import typing\n\nns = {}\nexec(&#39;from __future__ import annotations&#39; + chr(10)\n     + &#39;def f(x: int) -&gt; str:&#39; + chr(10)\n     + &#39;    return str(x)&#39;, ns)\nf = ns[&#39;f&#39;]\nprint(&#39;stored as string&#39;, isinstance(f.__annotations__[&#39;x&#39;], str))\nprint(&#39;resolved hints&#39;, {k: getattr(v, &#39;__name__&#39;, str(v)) for k, v in typing.get_type_hints(f).items()})", "note": "stub、py.typed 与 Any 的传播"}]' title='两种写法对照' note='差异集中在 检查器配置与严格度；先看输出，再找背后的规则。' />

```python
import typing, sys

print('origin list[int]', typing.get_origin(list[int]).__name__)
print('args list[int]', [a.__name__ for a in typing.get_args(list[int])])
print('Literal args', typing.get_args(typing.Literal['a', 'b']))
print('Union pipe equals', (int | str) == typing.Union[int, str])
print('python', sys.version_info[0], sys.version_info[1])
```

<OutputBox title='原理验证' output='origin list[int] list\nargs list[int] [&#39;int&#39;]\nLiteral args (&#39;a&#39;, &#39;b&#39;)\nUnion pipe equals True\npython 3 13' />


## stub、py.typed 与 Any 沿调用链的传播

PEP 561 规定：一个包只有在自身里带上 `py.typed` 标记文件，检查器才会使用它的内联注解；缺了这个标记，即便源码写了类型，第三方项目 import 它时也会被当成无类型，名字全部退化成 Any。

无标注的库靠 stub 文件（`.pyi`）补：typeshed 随检查器附带标准库与常见第三方库的 stub，`stubgen` 可从源码生成草稿，`stubtest` 校验 stub 与运行时签名一致。

Any 的特殊之处在于它与任何类型双向兼容：一旦某个值被标成 Any，对它的每一次属性访问、函数调用、运算都不再检查，并会把 Any 沿返回值继续传给下游，等于整片代码失去保护。

对策是开 `warn_return_any` 与 `disallow_any_generics`、给第三方库补 stub 或局部隔离。

行内抑制用 `# type: ignore` 或精确到码的写法，pyright 用 `# pyright: ignore`；配合 `warn_unused_ignores` 清掉过时抑制，否则检查器会被慢慢掏空。

**typing 构造与运行时可查性**

| 构造 / API | 运行时结果 | 说明 |
| --- | --- | --- |
| typing.get_type_hints(add) | &#123;'a': int, 'b': int, 'return': int&#125; | 解析注解为类型对象 |
| typing.get_origin(list[int]) | list | PEP 585 泛型别名取原始容器 |
| typing.get_args(list[int]) | (int,) | 取类型参数 |
| typing.get_args(Literal['a','b']) | ('a', 'b') | PEP 586 字面量枚举 |
| int \| str == Union[int, str] | True | PEP 604 与 typing.Union 等价 |
| isinstance(x, list[int]) | TypeError | 参数化泛型不能作 isinstance 第二参数 |
| from __future__ import annotations | __annotations__ 存字符串 | PEP 563 延迟求值，get_type_hints 再解析 |


### # type: ignore 为什么等于把检查器变装饰

<Callout type="warn" title='本讲最容易踩的坑' text='为赶进度满仓 # type: ignore：抑制口子越开越多，检查器变装饰，缺陷集中躲在最难查处' />


## 泛型不变性、Protocol 与运行时互补

PEP 585（3.9 起）让内置容器可直接下标：`list[int]`、`dict[str, int]` 是 `types.GenericAlias`；PEP 604（3.10 起）让 `int | str` 等价于 `typing.Union[int, str]`，`typing.get_origin(list[int])` 返回 list、`get_args(list[int])` 返回 (int,)。

可变容器是不变的：`list[int]` 不能赋给 `list[object]`，因为后者允许 append 一个 str 破坏前者；只读的 `Sequence[int]` 才协变，用 `TypeVar(covariant=True)` 声明。

还有 `Literal`（PEP 586）、`Annotated`（PEP 593）、`Protocol`（PEP 544 结构化子类型，配 `@runtime_checkable` 才能做 isinstance）、`TypeGuard`（PEP 647）、3.12 的 PEP 695 type 参数语法。

关键边界：注解默认只是元数据，运行时不强制——`typing.get_type_hints` 能读出类型，PEP 563 的 future 导入把注解存成字符串，`isinstance(x, list[int])` 会抛 TypeError，只能判未参数化的 list。

所以静态检查负责开发期约束，运行期校验交给 `pydantic` 这类校验库、attrs 的验证器或手写的 validate；`dataclasses` 只提供带注解的结构、并不校验类型，别把它当成运行时守卫。两者互补而非替代。

**版本 / PEP 与能力**

| 版本 / PEP | 能力 | 对检查的影响 |
| --- | --- | --- |
| 3.5 PEP 484 | 函数注解与 typing | 类型检查的起点 |
| 3.7 PEP 561 / 563 | py.typed 标记、延迟注解 | 缺 py.typed 的库退化为 Any |
| 3.8 PEP 544 / 586 | Protocol、Literal | 结构化子类型、字面量类型 |
| 3.9 PEP 585 / 593 | list[int]、Annotated | 内置泛型无需 typing.List |
| 3.10 PEP 604 / 647 | X \| Y、TypeGuard | 联合与类型 narrowing |
| 3.12 PEP 695 | type 参数语法 | 泛型类/函数新写法 |


## 静态注解与运行时校验互补的边界守卫

类型检查只能覆盖有注解的代码路径，外部输入（`HTTP` 参数、配置、DB 行）在运行时仍是未校验的裸值。

稳妥做法是在数据边界放一层轻量 validate：用 `typing.get_type_hints` 读出函数声明的契约，逐项 isinstance 校验后再调用核心函数；核心函数保留注解供 mypy/pyright 在开发期检查，两者各管一段。

下面片段用标准库演示这层守卫：合法输入正常通过、类型不符的输入在边界被拦下、同时打印「注解本身不强制」的证据，说明静态与运行时不是二选一而是分层防御。

```python
import typing

def add(a: int, b: int) -> int:
    return a + b

def validate(func, data):
    hints = typing.get_type_hints(func)
    for name, value in data.items():
        expected = hints.get(name)
        if expected is int and not isinstance(value, int):
            raise TypeError(name + ' must be int, got ' + type(value).__name__)
    return func(**data)

print('static hints', {k: v.__name__ for k, v in typing.get_type_hints(add).items()})
print('valid call', validate(add, {'a': 2, 'b': 3}))
try:
    validate(add, {'a': '2', 'b': 3})
except TypeError as e:
    print('runtime guard', str(e))
print('annotation not enforced', add('x', 'y'))
```

<Callout type="idea" title='落地提示' text='从公共 API 与数据边界开始加类型，按目录逐步提高严格度，把未覆盖文件列成清单逐步清零' />

<CheckList id='P074a' title='上线前自检' :items='["能复现并解释「为赶进度满仓 # type: ignore」", "能复现并解释「公共函数返回 Any 且不治理」", "能复现并解释「以为注解运行时会校验、或写 isinstance(x, li…」", "能用一条命令验证 检查器配置与严格度", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 为赶进度满仓 # type: ignore | 抑制口子越开越多，检查器变装饰，缺陷集中躲在最难查处 | 精确到码 # type: ignore[arg-type]，开 warn_unused_ignores，按目录逐步提高严格度并清零忽略清单 |
| 公共函数返回 Any 且不治理 | Any 与任意类型双向兼容，沿调用链传播使整片代码失去保护 | 开 warn_return_any / disallow_any_generics，补返回类型或为第三方库加 stub / py.typed |
| 以为注解运行时会校验、或写 isinstance(x, list[int]) | 注解默认不强制，add('x','y') 照常返回；参数化泛型作 isinstance 参数抛 TypeError | 运行期用 pydantic/dataclasses/手写 validate 校验，isinstance 只判未参数化的 list/dict |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：为赶进度满仓 # type: ignore", "body": "抑制口子越开越多，检查器变装饰，缺陷集中躲在最难查处", "tip": "精确到码 # type: ignore[arg-type]，开 warn_unused_ignores，按目录逐步提高严格度并清零忽略清单"}, {"title": "第 2 步：公共函数返回 Any 且不治理", "body": "Any 与任意类型双向兼容，沿调用链传播使整片代码失去保护", "tip": "开 warn_return_any / disallow_any_generics，补返回类型或为第三方库加 stub / py.typed"}, {"title": "第 3 步：以为注解运行时会校验、或写 isinstan…", "body": "注解默认不强制，add(&#39;x&#39;,&#39;y&#39;) 照常返回；参数化泛型作 isinstance 参数抛 TypeError", "tip": "运行期用 pydantic/dataclasses/手写 validate 校验，isinstance 只判未参数化的 list/dict"}]' />

```bash
python -m compileall -q . && python -m pytest -q
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 检查器配置与严格度 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

<FlowTimeline :steps='[{"title": "检查器配置与严格度：mypy 与 pyright", "desc": "mypy 配置在 `mypy.ini` 或 `pyproject.toml` 的…", "tone": "blue"}, {"title": "stub、py.typed 与 Any 的传播", "desc": "PEP 561 规定：一个包只有在自身里带上 `py.typed` 标记文件，检查器…", "tone": "purple"}, {"title": "泛型不变性、协议与运行时互补", "desc": "PEP 585（3.9 起）让内置容器可直接下标：`list[int]`…", "tone": "orange"}, {"title": "工程落地", "desc": "静态注解与运行时校验互补的边界守卫", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 练习、自测与一页纸速记

<Exercise title='基础：读出函数的类型契约' task='定义 def f(x: int, y: str) -&gt; bool，用 typing.get_type_hints 打印各名字的类型名。' solution='import typing\ndef f(x: int, y: str) -&gt; bool:\n    return True\nprint(&#39;hints&#39;, {k: v.__name__ for k, v in typing.get_type_hints(f).items()})' explain='get_type_hints 把 __annotations__ 解析成真实类型对象；这是检查器与运行时守卫共用的元数据来源。' />

<Exercise title='进阶：用 get_origin / get_args 拆解泛型' task='对 dict[str, int] 与 Literal[&#39;r&#39;,&#39;w&#39;] 分别取 origin 与 args，打印结果并说明 PEP 585/586。' solution='import typing\nprint(&#39;origin&#39;, typing.get_origin(dict[str, int]).__name__)\nprint(&#39;args&#39;, [getattr(a, &#39;__name__&#39;, str(a)) for a in typing.get_args(dict[str, int])])\nprint(&#39;Literal&#39;, typing.get_args(typing.Literal[&#39;r&#39;, &#39;w&#39;]))' explain='PEP 585 让内置容器可下标成 GenericAlias，get_origin 取原始容器、get_args 取参数；Literal 的 args 是允许的字面量元组。' />

<Quiz no='074-1' q='关于 Any，下面哪项准确？' :options='["与任意类型双向兼容，一旦进入表达式就沿调用链传播，使检查失效", "只与 object 兼容", "运行时会强制校验取值", "等价于 list[Any]"]' answer="0" explain='Any 同时是类型格的顶与底，读写它都不触发检查，返回值继续把 Any 传给下游；用 warn_return_any、disallow_any_generics 与补 stub 收敛。' />

<Quiz no='074-2' q='PEP 561 的 py.typed 标记作用是？' :options='["告知检查器该包带内联注解，可直接使用；缺失则退化为 Any", "声明包版本号", "让 pip 跳过哈希校验", "启用运行时类型强制"]' answer="0" explain='带 py.typed 的包其注解才被下游检查器采信；没有标记时即便源码有注解也被视为无类型，导入的名字全部退化成 Any。' />

<Quiz no='074-3' q='isinstance(x, list[int]) 的结果是？' :options='["抛 TypeError，参数化泛型不能作 isinstance 第二参数", "返回 True", "返回 False", "等价于 isinstance(x, list)"]' answer="0" explain='list[int] 是参数化 GenericAlias，未实现针对下标的 __instancecheck__；isinstance 只接受未参数化的 list，运行期校验要另写。' />

<Predict no='074-4' q='执行 isinstance([1, 2], list[int]) 最可能的输出是？' :options='["TypeError: isinstance() argument 2 cannot be a parameterized generic", "True", "False"]' answer='0' output='TypeError: isinstance() argument 2 cannot be a parameterized generic' explain='3.13 对参数化泛型作 isinstance 第二参数明确报这条 TypeError；这是「注解是静态元数据、运行时不识下标泛型」的直接证据，校验要改用未参数化的 list 加逐元素判断。' />

<FillBlank no='074-5' tpl='___ typing, inspect' :answers='["import"]' hint='回想本讲关于 检查器配置与严格度 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 检查器配置与严格度：mypy 与 pyright 的落点。' />

<KnowledgeCard :points='["mypy --strict / pyright typeCheckingMode=&#39;strict&#39; 从公开 API 与数据边界起步，按目录渐进提高严格度", "PEP 561 py.typed 决定内联注解是否被采信；缺标记的库靠 .pyi stub 或退化成 Any", "Any 与任意类型双向兼容并沿调用链传播，用 warn_return_any / disallow_any_generics 治理", "PEP 585 list[int]（3.9+）、PEP 604 int | str（3.10+）；可变容器不变、Sequence 协变", "注解默认不强制运行时校验，isinstance(x, list[int]) 抛 TypeError；dataclasses 不校验，运行时交给 pydantic/手写", "# type: ignore 要精确到码并开 warn_unused_ignores，reveal_type 只在静态分析时存在"]' :pitfalls='["为赶进度满仓 # type: ignore", "公共函数返回 Any 且不治理", "以为注解运行时会校验、或写 isinstance(x, list[int])", "为赶进度满仓 # type: ignore，等于把检查器变成装饰；技术债会集中在最难查的地方"]' summary='静态类型的收益与覆盖率成正比，Any 会像漏洞一样沿调用链传播，让一片代码失去保护' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| mypy --strict / pyright typeCheckingMode='strict' 从公开 API 与数据边界起步，按目录渐进提高严格度 | 建立直觉 |
| PEP 561 py.typed 决定内联注解是否被采信；缺标记的库靠 .pyi stub 或退化成 Any | 跑通示例 |
| Any 与任意类型双向兼容并沿调用链传播，用 warn_return_any / disallow_any_generics 治理 | 深入边界 |
| PEP 585 list[int]（3.9+）、PEP 604 int \| str（3.10+）；可变容器不变、Sequence 协变 | 工程落地 |
| 注解默认不强制运行时校验，isinstance(x, list[int]) 抛 TypeError；dataclasses 不校验，运行时交给 pydantic/手写 | 随堂检测 |
| # type: ignore 要精确到码并开 warn_unused_ignores，reveal_type 只在静态分析时存在 | 复盘 |

1. mypy --strict / pyright typeCheckingMode='strict' 从公开 API 与数据边界起步，按目录渐进提高严格度

2. PEP 561 py.typed 决定内联注解是否被采信；缺标记的库靠 .pyi stub 或退化成 Any

3. Any 与任意类型双向兼容并沿调用链传播，用 warn_return_any / disallow_any_generics 治理

[下一讲：单元测试：pytest、fixture 与参数化](/engineering/pytest)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/074-typecheck.py`

```bash
python3 examples/lessons/074-typecheck.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/074-typecheck.py) · [全部示例代码索引](/examples/)
