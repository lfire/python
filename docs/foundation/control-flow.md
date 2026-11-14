---
title: 第 012 讲 · 分支：if / elif / else 与 match-case
description: 写出层次清晰、可维护的条件逻辑
---

<StageHeader stage='L1 · 编程地基' level='★★☆☆☆' time='25 分钟' goal='写出层次清晰、可维护的条件逻辑' prereq='第 011 讲 · 运算符与表达式：优先级、短路与真值' />

# 第 012 讲 · 分支：if / elif / else 与 match-case

一个式子再绕都能算准了，可程序不该一条道走到黑：输入不同，走的路就不一样。分支于是绕不开——难不在写下第一个 `if`，而在条件一多还能让人一眼看明白、改一处不漏三处。

想想越堆越高的判断：先判类型、再判范围、又判标志位，十几层缩进测着都费劲；或收到一条命令，想按它『长什么样』分流。我们从条件表达式与嵌套起步，再说 `match-case` 做结构模式匹配、并非别的语言里那种 `switch`，能解包序列、绑定子结构；接着谈守卫与捕获、匹配顺序，规则常变就改用分派表；最后用卫语句把嵌套压平。带着第 11 讲的表达式与真值就够；学完你能判断该用 `if`、模式匹配还是分派表。


## 十几层 elif 里改一个条件，为什么总漏分支

一个订单状态机写了十几层 `if/elif`：先判类型、再判子类型、又判金额区间，新增一种状态要往这堆分支里插一行，测试时总漏掉某个组合。有人提议「换成 `switch`」，可 Python 3.10 之前并没有这个语句，硬拿字典或 `elif` 链兜着，维护起来一样费劲。

另一处把 `match-case` 当成值相等判断，写 `case 1` 想匹配列表 `[1]`，怎么都匹配不上；还有人把十几个 `case` 顺序写反，守卫条件永远进不去。两种最直觉的补救——继续加 `elif`，或把所有条件塞进一个布尔表达式——前者让分支结构埋进层层缩进，后者把不同维度揉成一团、出错时无从定位。

`match-case` 不是 `switch`：它做结构模式匹配，能解包序列、匹配映射、绑定子结构、加守卫，能力远超值相等。本讲把模式类别、匹配顺序、守卫与捕获、字典分派表和卫语句讲清，让分支一眼看得明白、改起来只动一处，还能按开关逐步放量。


## match-case 是结构模式匹配，不是 switch

`match-case` 从 3.10 起可用（PEP 634、635、636），它把 `subject` 与一系列 `case` 的模式做结构匹配，而不是拿 `==` 逐个比值。字面量模式 `case 1` 才用相等比较；捕获模式 `case x` 把 `subject` 绑到名字 `x`，因为能兜住任何值，必须排在最后；

序列模式 `case [a, b]` 要求 `subject` 是长度恰好为 2 的序列并解包，`str`、`bytes`、`bytearray` 虽是序列却被刻意排除在序列模式之外；

映射模式 `case {'type': kind}` 只要求字典含 `'type'` 键并把对应值绑到 `kind`，多余的键不影响命中，多个键可以并排写；

类模式按属性或 `__match_args__` 匹配；OR 模式用竖线 `|` 把几个模式并成一个；通配符 `case _` 兜底且必须放最后。匹配自上而下按书写顺序进行，第一个命中的 `case` 执行完整个 `match` 就结束，不会像 C 的 `switch` 那样贯穿到下一支。

映射模式还能用 `**rest` 把剩余键值收进一个字典，守卫 `case [x] if x > 0` 则在模式绑定之后才求值。

判断依据很朴素：分支依赖的是值相等还是数据的结构形状，前者更适合字典分派，后者才轮到 `match-case`。

```python
def describe(cmd):
    match cmd:
        case ['go', x, y]:
            return 'move ' + str(x) + ' ' + str(y)
        case {'type': 'stop', 'reason': r}:
            return 'stop ' + str(r)
        case [x] if x > 0:
            return 'positive ' + str(x)
        case _:
            return 'unknown'

print(describe(['go', 3, 4]))
print(describe({'type': 'stop', 'reason': 'done'}))
print(describe([9]))
print(describe([-1]))
print(describe('anything'))
```

<OutputBox title='主示例运行结果' output='move 3 4\nstop done\npositive 9\nunknown\nunknown' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='def describe(cmd):\n    match cmd:\n        case [&#39;go&#39;, x, y]:\n            return &#39;move &#39; + str(x) + &#39; &#39; + str(y)\n        case {&#39;type&#39;: &#39;stop&#39;, &#39;reason&#39;: r}:\n            return &#39;stop &#39; + str(r)\n        case [x] if x &gt; 0:\n            return &#39;positive &#39; + str(x)\n        case _:\n            return &#39;unknown&#39;\n\nprint(describe([&#39;go&#39;, 3, 4]))\nprint(describe({&#39;type&#39;: &#39;stop&#39;, &#39;reason&#39;: &#39;done&#39;}))\nprint(describe([9]))\nprint(describe([-1]))\nprint(describe(&#39;anything&#39;))' :notes='["定义按结构分流的函数，subject 是 cmd", "match 开始按书写顺序尝试各模式", "序列模式：长度 3 且首项为 go，解包绑定 x 与 y", "把坐标拼成返回串", "映射模式：dict 含 type 为 stop 的键，并绑定 reason 到 r", "把原因拼成返回串", "序列模式加守卫：单元素且值大于 0 才命中", "返回正数描述", "通配符兜底，必须放最后", "未命中任何具体模式时返回 unknown", "空行，只用于分隔逻辑块，不影响执行结果。", "长度 3 的列表命中第一个模式，解包出 3 与 4", "含 type 与 reason 的 dict 命中映射模式", "单元素正数命中带守卫的模式", "单元素 -1 使守卫为假，落到通配符", "字符串不匹配序列与映射模式，落到通配符"]' title='第 012 讲 · 分支：if / elif / else 与 match-case' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**match-case 模式类别**

| 模式 | 例子 | 匹配条件 |
| --- | --- | --- |
| 字面量 | case 1 | subject 等于 1 |
| 捕获 | case x | 绑定任意 subject，须放最后 |
| 序列 | case [a, b] | 长度 2 的序列并解包，str/bytes 不匹配 |
| 映射 | case &#123;'k': v&#125; | dict 含键 k 并绑定值，多余键无妨 |
| OR | case [x] \| (x,) | 任一模式命中 |
| 通配符 | case _ | 兜底，必须最后 |
| 守卫 | case [x] if x > 0 | 模式命中且守卫为真 |


### 序列模式、映射模式与字面量模式各管什么

选哪种模式，看数据的形状与要不要绑出子结构。序列模式 case [a, b] 要求恰好两项，[a, *rest] 才收剩余，匹配 list、tuple 却排除 str 与 bytes，写成 case (x, y) 也仍是序列模式。

映射模式 case &#123;'op': 'stop', **rest&#125; 只查键存在并绑定值，多余键不影响命中。字面量模式用 == 比值，None、True、False 按 is 特判，case 1 与 case 1.0 会都命中。下表按输入形状、绑定什么、长度或键约束分列。

**分支结构选型**

| 场景 | 推荐写法 | 原因 |
| --- | --- | --- |
| 按单个值选处理函数 | 字典分派表 handlers.get(op)() | 新增操作只改数据，便于灰度 |
| 按数据结构分流 | match-case 结构模式 | 能解包、匹配映射、绑定子结构 |
| 二选一取值 | 条件表达式 x if c else y | 表达式级、简洁 |
| 多层前置校验 | 卫语句早返回 | 主流程保持最外层缩进 |
| 规则频繁变化 | 数据驱动规则表 | 扩展只加数据 |


## 守卫、捕获与匹配顺序：把分支写成数据

守卫 `if` 挂在模式之后，只有模式已成功匹配、捕获变量已绑定时才求值，所以 `case [x] if x > 0` 里的 `x` 一定存在；

守卫为假会继续试下一个 `case`，而不是直接落到通配符。

捕获模式不能在同一模式里重复绑定一个名字（`case [x, x]` 会抛 `SyntaxError`，应改用守卫比较），也可以用 `case [a, b] as whole` 在解包的同时留下整段引用。

匹配顺序要分两种情形看：把 `case _` 或 `case x` 这类兜底模式搁在中间，编译器直接抛 `SyntaxError` 说后续分支不可达，程序根本跑不起来；

真正安静的坑是相对顺序——`case [x] if x > 0` 若排在 `case [x]` 之后，前者永远轮不上，代码照常运行也不报错，只能靠测试或分支覆盖率发现。

所以具体模式、带守卫的模式往前放，通配与无守卫兜底往后放。`match` 是语句不返回值，但每个 `case` 里可以 `return`，比层层嵌套的 `elif` 更利于早返回。

至于「按某个键挑一个处理函数」这类扁平分支，字典分派表往往更省事：`handlers` 存名字到可调用对象的映射，用 `handlers.get(op, default)()` 调用，新增操作只改一处数据；

而 `match-case` 更擅长按数据结构分流，比如解析语法树、协议消息、不同形状的事件。

```python
def apply(op, a, b):
    table = {
        'add': lambda: a + b,
        'mul': lambda: a * b,
        'max': lambda: a if a > b else b,
    }
    return table.get(op, lambda: None)()

print(apply('add', 2, 3))
print(apply('mul', 2, 3))
print(apply('max', 2, 3))
print(apply('mod', 2, 3))
print('ternary', 'even' if 4 % 2 == 0 else 'odd')
```

<OutputBox title='对照写法：先自己猜，再点开' output='5\n6\n3\nNone\nternary even' guess="true" />


### case _ 为什么必须放在最后

麻烦不在放错会崩，而在多半不报错。匹配自上而下、首个命中即结束，case _ 不绑定名字又永远成立，搁在中间后面所有 case 就成不可达分支；case x 捕获模式同样兜底，排前面会吞掉后续。CPython 到 3.11 才对明显不可达模式给 SyntaxWarning，3.10 静默，所以顺序错只能靠测试或分支覆盖率发现。

守卫不受影响：case [x] if x > 0 里守卫为假会继续往下试，只要 _ 在最后就不抢。下表把版本差异与顺序规则列清。

**版本与顺序规则**

| 项 | 行为 | 出错信号 |
| --- | --- | --- |
| 3.10 起引入 | PEP 634/635/636 结构模式匹配 | 3.9 及以下语法错误 |
| 自上而下匹配 | 首个命中即结束，无贯穿 | 具体模式放在通配之后会永远不可达 |
| 守卫求值时机 | 模式绑定后、执行体前 | 守卫引用未绑定名字会报 NameError |
| case _ 位置 | 必须最后 | 放中间会让后续 case 不可达 |


## 卫语句与可读性边界：少嵌套、早返回

复杂条件最常见的坏味道是层层嵌套：先 `if` 校验、再 `if` 看状态、又在 `for` 里嵌 `if`，真正要做的事藏在最深处，读代码得一路缩进到底，测试要凑齐所有前置条件才能碰到核心分支。

卫语句（guard clause）把失败路径提前 `return` 或 `continue`：参数非法、权限不足、缓存命中都先放出去，主流程留在最外层缩进，圈复杂度随之下降。

条件表达式 `x if cond else y` 适合二选一取值，嵌套两层以上就该换成普通 `if` 或分派表；

长布尔表达式按维度拆成有名字的中间变量，例如把是否合格写成 `is_eligible`，由 `paid`、`not refunded`、`in_range` 组合，比把五个 `and` 塞进一个 `if` 好排查得多。

`match-case` 里也要管住单个分支的体量：模式只负责分流，具体业务交给被调用的函数，别在一个 `case` 里铺几十行。业务规则频繁变化时，把规则写成数据（分派表或规则列表）而不是硬编码分支，新增规则只加一条数据、配合配置开关做灰度，回归测试也能遍历整张表。

什么时候该重构，有两个信号：改一个条件要同时动好几处，或某个分支始终测不到。


## 匹配自上而下、首个命中即结束的底层

`match-case` 在编译期被拆成一组匹配指令：`MATCH_SEQUENCE` 先检查 `subject` 是否为序列并校验长度，`MATCH_MAPPING` 检查键集合，随后取键、解包，把子结构绑到捕获变量；

字面量模式走比较与条件跳转，守卫则是模式成功后再执行的一段普通表达式，为假就跳到下一个 `case` 的匹配块。整个结构是一串按书写顺序排好的条件跳转，命中第一个后直接跳出 `match`，自然没有 C 里 `switch` 的贯穿。

`str`、`bytes`、`bytearray` 被序列模式排除，是因为按字符解包几乎总是误用。字典分派表的底层更简单：一次哈希查找拿到可调用对象再调用，把判断压缩成 `O(1)` 的键查找，分支变多时结构不变；代价是键必须可哈希、且所有处理函数签名要一致。

卫语句降低的是控制流嵌套深度，让失败路径在字节码里提前返回，主路径不再被多层跳转裹住。把结构匹配理解成一串条件跳转，顺序、守卫时机与不可达分支为什么会出问题就都串起来了。

<ConceptDiagram type='layers3' title='第 012 讲 · match-case 是结构模式匹配，不是 switch' labels='match-case 是结构模式匹配，不是…|守卫、捕获与匹配顺序：把分支写成数据|卫语句与可读性边界：少嵌套、早返回|早返回与卫语句' caption='写出层次清晰、可维护的条件逻辑' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 运维命令路由：结构匹配管形状、分派表管扁平值

一个内部运维工具要处理几类命令：移动（带坐标）、停止（带原因）、单个正数、以及认不出的命令。早期用一长串 `isinstance` 配 `if/elif` 判断完类型再取值，新增一种命令要改三四处，测试组合还总漏。

下面这段改用 `match-case` 按结构分流：序列模式解包坐标，映射模式取 `type` 与 `reason`，守卫处理正数，通配符 `case _` 兜底；再用字典分派表处理扁平的算术操作，两种写法各管一类分支。最后打印各分支结果，并验证未知命令确实落到兜底。

真实系统里每个 `case` 只做分发，具体动作交给独立函数，方便单独测试、也方便按开关放量。

```python
def route(cmd):
    match cmd:
        case ['go', x, y]:
            return 'move ' + str(x) + ' ' + str(y)
        case {'type': 'stop', 'reason': why}:
            return 'stop ' + str(why)
        case [x] if x > 0:
            return 'positive ' + str(x)
        case _:
            return 'unknown'

OPS = {
    'add': lambda a, b: a + b,
    'mul': lambda a, b: a * b,
    'max': lambda a, b: a if a > b else b,
}

def compute(op, a, b):
    fn = OPS.get(op)
    return fn(a, b) if fn else None

for cmd in (['go', 3, 4], {'type': 'stop', 'reason': 'done'}, [9], [-1], 'x'):
    print(route(cmd))
print('add', compute('add', 2, 3), 'max', compute('max', 2, 3))
print('missing', compute('mod', 2, 3))
```

<Callout type="idea" title='落地提示' text='业务规则频繁变化时，用数据驱动的分派表比硬编码分支更容易扩展与灰度' />


## 分支结构的错因速查与速记

<Exercise title='基础：用结构模式匹配解析命令' task='写 describe(cmd)，对 [&#39;go&#39;, x, y] 返回格式化坐标、对含 type 键的 dict 返回类型、其余返回 unknown，并打印三个样例。' solution='def describe(cmd):\n    match cmd:\n        case [&#39;go&#39;, x, y]:\n            return f&#39;go {x} {y}&#39;\n        case {&#39;type&#39;: t}:\n            return &#39;type &#39; + str(t)\n        case _:\n            return &#39;unknown&#39;\nprint(describe([&#39;go&#39;, 1, 2]))\nprint(describe({&#39;type&#39;: &#39;stop&#39;}))\nprint(describe(7))' explain='序列模式解包坐标、映射模式按键取值、通配符兜底；三个样例分别命中前两种模式与兜底，验证结构匹配而非值相等。' />

<Exercise title='进阶：给分派表加默认值并写守卫' task='把两种算术操作放进字典，用 get 提供默认处理；再写一个 match-case 用守卫只接受正数单元素序列，打印合法与非法输入的结果。' solution='OPS = {&#39;add&#39;: lambda a, b: a + b, &#39;mul&#39;: lambda a, b: a * b}\ndef calc(op, a, b):\n    return OPS.get(op, lambda a, b: None)(a, b)\ndef positive(x):\n    match x:\n        case [v] if v &gt; 0:\n            return v\n        case _:\n            return -1\nprint(&#39;calc&#39;, calc(&#39;add&#39;, 2, 3), calc(&#39;div&#39;, 2, 3))\nprint(&#39;positive&#39;, positive([5]), positive([-5]), positive([1, 2]))' explain='字典 get 用默认 lambda 兜住未知键；守卫为假时继续到 case _，因此 -5 与长度 2 的序列都返回 -1，不会误命中。' />

<Quiz no='012-1' q='关于 match-case，哪项描述准确？' :options='["它是结构模式匹配，能解包序列、匹配映射、绑定子结构，首个命中即结束", "它就是 switch，按值相等贯穿执行", "3.8 起即可使用", "str 可以匹配序列模式"]' answer="0" explain='match-case 由 PEP 634 在 3.10 引入，按结构匹配且无贯穿；字符串被序列模式刻意排除，值相等判断更适合字典分派。' />

<Quiz no='012-2' q='case _ 为什么必须放在最后？' :options='["匹配自上而下、首个命中即结束，放中间会让后续 case 永远不可达", "只是语法风格约定，不影响行为", "为了提升性能", "放中间一定抛 SyntaxError"]' answer="0" explain='通配模式能匹配任何 subject，一旦出现在中间，其后所有 case 都不会被尝试；解释器未必报错，只能靠测试发现不可达。' />

<Quiz no='012-3' q='按一个键选处理函数、且规则频繁新增，哪种写法最合适？' :options='["字典分派表 handlers.get(op)()，新增只改数据", "十几层 if/elif", "match-case 的字面量模式", "嵌套条件表达式"]' answer="0" explain='扁平值分派用一次哈希查找即可，新增操作只往表里加一条数据，便于灰度与插件注册；结构形状的分流才用 match-case。' />

<Predict no='012-4' q='主示例里 describe([-1]) 输出什么？' :options='["unknown", "positive -1", "move -1"]' answer='0' output='unknown' explain='case [x] if x &gt; 0 的守卫要求 x 为正，[-1] 解包得 x=-1 使守卫为假，继续尝试下一个 case，最终命中通配符返回 unknown。' />

<FillBlank no='012-5' tpl='___ describe(cmd):' :answers='["def"]' hint='回想本讲关于 条件表达式与嵌套 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 match-case 是结构模式匹配，不是 switch 的落点。' />

<KnowledgeCard :points='["match-case 是结构模式匹配（PEP 634，3.10 起）：字面量、捕获、序列、映射、OR、通配、守卫", "匹配自上而下、首个命中即结束且无贯穿；case _ 必须最后，具体模式放前面", "序列模式不匹配 str/bytes/bytearray；守卫在模式绑定后求值，为假继续下一个 case", "扁平值分派用字典表 handlers.get(op, default)()，按结构分流才用 match-case", "卫语句早返回把主流程拉到最外层，减少嵌套与圈复杂度", "规则频繁变化时把分支写成数据（分派表或规则表），便于扩展与灰度"]' :pitfalls='["把 match-case 当 switch，用 case 1 想匹配列表或字符串", "把 case _ 放在中间，或把具体模式排在通配之后", "十几层 if/elif 里反复改同一个条件", "把十几层 if 叠在一起，既难测又容易漏分支；模式匹配与字典分派能让分支结构显式化"]' summary='match-case 不是 switch：它做的是结构模式匹配，能解包序列、匹配映射、绑定子结构，能力远超值相等判断' />

1. match-case 是结构模式匹配（PEP 634，3.10 起）：字面量、捕获、序列、映射、OR、通配、守卫

2. 匹配自上而下、首个命中即结束且无贯穿；case _ 必须最后，具体模式放前面

3. 序列模式不匹配 str/bytes/bytearray；守卫在模式绑定后求值，为假继续下一个 case

[下一讲：循环：for / while、range 与循环 else](/foundation/loops)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/012-control-flow.py`

```bash
python3 examples/lessons/012-control-flow.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/012-control-flow.py) · [全部示例代码索引](/examples/)
