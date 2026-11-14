---
title: 第 024 讲 · 推导式：四种写法与可读性边界
description: 写出简洁且不过度的推导式
---

<StageHeader stage='L2 · 容器与序列' level='★★☆☆☆' time='25 分钟' goal='写出简洁且不过度的推导式' prereq='第 023 讲 · set / frozenset：哈希、集合运算与去重' />

# 第 024 讲 · 推导式：四种写法与可读性边界

把一批数据逐个过一遍、挑一挑、换个形状，是日常最常写的动作。前面已把列表、字典、集合摸熟，这一讲给这种「过一遍」一个更紧凑的写法，也划一条别写过头的线。

一个清洗脚本把每行转数字、滤空行、再平方，四步各写一段循环，小样本好好的，换到两百万行内存就吃紧；改成生成器表达式串联后稳了，却有人建好后重新绑定源数据，消费到的还是旧值。我们先把三种推导式与生成器表达式摆齐，说清推导式作用域与变量不泄漏；再讲多重循环与过滤的次序；最后给可读性边界，判断何时退回普通循环。需要你熟悉循环、条件与三种容器。学完你能把清洗管道写得短而不挤，也知道何时短反而害了读的人。


## 推导式里的循环变量，为什么没留在外面

一个数据清洗脚本要把每行转成数字、过滤空行、再平方，工程师把四步各写成一段列表推导串在一起：先 `int(s.strip())` 转数字并滤掉空行，再把结果平方，最后又过滤一次。小样本跑得好好的，换到 200 万行就 OOM——每一步都物化一份完整列表，中间结果和原始数据同时压在内存里。

改成生成器表达式串联后内存恒定，却又踩了另一处坑：`g = (x*x for x in data)` 建好后把 `data` 重新绑定成新列表，消费 `g` 拿到的还是旧数据，因为最外层 iterable 在创建时就绑定了。

还有人写 `[i for i in range(3)]` 之后直接 `print(i)`，以为能拿到 2，结果拿到的是外层旧值，甚至 `NameError`。

这一讲把四种写法、独立作用域、生成器惰性与海象运算符的边界一条条理清。

<Callout type="warn" title='先看一个真实会出错的写法' text='以为推导式的循环变量会像 for 一样留在外面：Python 3 推导式有独立作用域，循环变量不泄漏；外层同名变量不会被覆盖' />

推导式有四种写法：列表 `[expr for ...]`、集合 `{expr for ...}`、字典 `{k: v for ...}` 与生成器表达式 `(expr for ...)`。多重 `for` 从左到右按嵌套顺序执行，等价于外层变量先走、内层变量后走的双层循环；

多个 `if` 子句等价于 `and`，而值表达式里的三元 `x if cond else y` 放在 `for` 之前，两种位置不能混。

Python 3 的列表、集合、字典推导式会编译成一个隐式函数并在其中执行，因此有独立作用域、循环变量不会泄漏到外层；普通 `for` 循环的变量则留在当前作用域，Python 2 的列表推导还会泄漏，这是迁移时常被忽略的差异。

3.12 起 PEP 709 把推导式内联到外层作用域，省掉一次函数调用，但靠临时保存外层同名变量、执行后恢复来保持隔离语义，所以循环变量依旧不泄漏。

列表推导内部用专用的 `LIST_APPEND`（集合、字典对应 `SET_ADD` / `MAP_ADD`）直接向结果容器追加，省掉等价 `for` 循环里每轮查找 `append` 与函数调用的开销，通常更快。

生成器表达式根本不构造容器，返回 generator 对象，只有被 `next()` / `for` / `sum()` 消费时才逐条产出。

```python
nums = [1, 2, 3, 4, 5]
squares = [x * x for x in nums]
uniq = {x % 3 for x in nums}
mapping = {x: x * x for x in nums}
gen = (x * x for x in nums)
print('list', squares)
print('set', sorted(uniq), 'dict', mapping)
print('gen type', type(gen).__name__, 'sum', sum(gen))

i = 'outer'
comp = [i for i in range(3)]
print('no leak', i, comp)

pairs = [(a, b) for a in range(2) for b in range(3)]
print('nested for', pairs[:4], 'len', len(pairs))
filtered = [x for x in nums if x % 2 == 0 if x > 2]
print('two ifs', filtered)
labels = ['even' if x % 2 == 0 else 'odd' for x in nums]
print('conditional expr', labels)

data = [1, 2, 3]
g = (x for x in data)
data = [9, 9]
print('outer iterable captured', list(g))

doubled = [y for x in [1, 2, 3] if (y := x * 2) > 2]
print('walrus', doubled)
```

<OutputBox title='主示例运行结果' output='list [1, 4, 9, 16, 25]\nset [0, 1, 2] dict {1: 1, 2: 4, 3: 9, 4: 16, 5: 25}\ngen type generator sum 55\nno leak outer [0, 1, 2]\nnested for [(0, 0), (0, 1), (0, 2), (1, 0)] len 6\ntwo ifs [4]\nconditional expr [&#39;odd&#39;, &#39;even&#39;, &#39;odd&#39;, &#39;even&#39;, &#39;odd&#39;]\nouter iterable captured [1, 2, 3]\nwalrus [4, 6]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='nums = [1, 2, 3, 4, 5]\nsquares = [x * x for x in nums]\nuniq = {x % 3 for x in nums}\nmapping = {x: x * x for x in nums}\ngen = (x * x for x in nums)\nprint(&#39;list&#39;, squares)\nprint(&#39;set&#39;, sorted(uniq), &#39;dict&#39;, mapping)\nprint(&#39;gen type&#39;, type(gen).__name__, &#39;sum&#39;, sum(gen))\n\ni = &#39;outer&#39;\ncomp = [i for i in range(3)]\nprint(&#39;no leak&#39;, i, comp)\n\npairs = [(a, b) for a in range(2) for b in range(3)]\nprint(&#39;nested for&#39;, pairs[:4], &#39;len&#39;, len(pairs))\nfiltered = [x for x in nums if x % 2 == 0 if x &gt; 2]\nprint(&#39;two ifs&#39;, filtered)\nlabels = [&#39;even&#39; if x % 2 == 0 else &#39;odd&#39; for x in nums]\nprint(&#39;conditional expr&#39;, labels)\n\ndata = [1, 2, 3]\ng = (x for x in data)\ndata = [9, 9]\nprint(&#39;outer iterable captured&#39;, list(g))\n\ndoubled = [y for x in [1, 2, 3] if (y := x * 2) &gt; 2]\nprint(&#39;walrus&#39;, doubled)' :notes='["构造一组数字作为四种推导式的共同输入", "列表推导立即构造 list", "集合推导立即构造 set，自动去重", "字典推导立即构造 dict", "生成器表达式返回惰性 generator，创建时不计算", "打印列表推导结果", "集合用 sorted 消除顺序不确定性，字典按插入顺序", "类型为 generator，sum 消费它得到平方和", "空行，只用于分隔逻辑块，不影响执行结果。", "在外层定义一个同名变量 i", "推导式内的 i 是独立作用域的循环变量", "外层 i 仍是 &#39;outer&#39;，证明循环变量不泄漏", "空行，只用于分隔逻辑块，不影响执行结果。", "多重 for 按 a 外 b 内的顺序嵌套", "打印前四项与总数，验证嵌套顺序", "两个 if 子句等价于 and，只保留偶数且大于 2 的", "值表达式里的三元条件放在 for 之前", "按奇偶生成标签列表", "构造数据后创建生成器表达式", "空行，只用于分隔逻辑块，不影响执行结果。", "此时最外层 iterable 已绑定为原列表的迭代器", "重新绑定 data 到新列表，不影响已创建的生成器", "消费后仍是旧数据的 1、2、3", "3.8 起 := 在 if 里复用中间结果，避免重复计算", "空行，只用于分隔逻辑块，不影响执行结果。", "只保留 2 倍后大于 2 的结果，得到 4 与 6", "3.8 起 := 可在值表达式与 if 里复用中间结果，但禁止在最外层 iterable 赋值"]' title='第 024 讲 · 推导式：四种写法与可读性边界' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='推导式有四种写法：列表 `[expr for ...]`、集合 `{expr for ...}`、字典 `{k: v for ...}` 与生成器表达式 `(expr for ...)`。多重 `for` 从左到右按嵌套顺序执行，等价于外层变量先走、内层变量后走的双层循环；多个 `if` 子句等价于…' />

<ConceptDiagram type='compare2' title='第 024 讲 · 四种推导式、作用域与专用字节码' labels='四种推导式、作用域与专用字节码|惰性求值的边界与海象运算符|可读性边界与退回循环的判据|何时退回循环' caption='写出简洁且不过度的推导式' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 四种推导式对照：列表、集合、字典与生成器表达式

**四种推导式对照**

| 写法 | 结果类型 | 是否立即计算 | 典型用途 |
| --- | --- | --- | --- |
| [expr for x in xs] | list | 立即 | 需要可索引、可复用的结果 |
| &#123;expr for x in xs&#125; | set | 立即 | 去重后的集合 |
| &#123;k: v for x in xs&#125; | dict | 立即 | 从序列构造映射 |
| (expr for x in xs) | generator | 惰性，消费时才算 | 串联管道、内存恒定 |
| sum(expr for x in xs) | 标量 | 惰性且省一层括号 | 单参数时可省生成器括号 |

<Compare :panels='[{"label": "主示例", "code": "nums = [1, 2, 3, 4, 5]\nsquares = [x * x for x in nums]\nuniq = {x % 3 for x in nums}\nmapping = {x: x * x for x in nums}\ngen = (x * x for x in nums)\nprint(&#39;list&#39;, squares)\nprint(&#39;set&#39;, sorted(uniq), &#39;dict&#39;, mapping)\nprint(&#39;gen type&#39;, type(gen).__name__, &#39;sum&#39;, sum(gen))\n\ni = &#39;outer&#39;\ncomp = [i for i in range(3)]\nprint(&#39;no leak&#39;, i, comp)\n\npairs = [(a, b) for a in range(2) for b in range(3)]\nprint(&#39;nested for&#39;, pairs[:4], &#39;len&#39;, len(pairs))\nfiltered = [x for x in nums if x % 2 == 0 if x &gt; 2]\nprint(&#39;two ifs&#39;, filtered)\nlabels = [&#39;even&#39; if x % 2 == 0 else &#39;odd&#39; for x in nums]\nprint(&#39;conditional expr&#39;, labels)\n\ndata = [1, 2, 3]\ng = (x for x in data)\ndata = [9, 9]\nprint(&#39;outer iterable captured&#39;, list(g))\n\ndoubled = [y for x in [1, 2, 3] if (y := x * 2) &gt; 2]\nprint(&#39;walrus&#39;, doubled)", "note": "四种推导式、作用域与专用字节码"}, {"label": "对照 / 进阶", "code": "import sys\n\ndef pipeline(rows):\n    cleaned = (int(r.strip()) for r in rows if r.strip())\n    squared = (x * x for x in cleaned)\n    return (x for x in squared if x &gt; 10)\n\nrows = [&#39; 1 &#39;, &#39;2&#39;, &#39;&#39;, &#39; 4 &#39;, &#39;5&#39;]\nprint(&#39;pipeline&#39;, list(pipeline(rows)))\nprint(&#39;gen size constant&#39;, sys.getsizeof((x for x in range(10**6))) &lt; 1000)\n\nmapped = list(map(lambda x: x * 2, [1, 2, 3]))\nfiltered = list(filter(lambda x: x &gt; 2, [1, 2, 3, 4]))\nprint(&#39;map filter&#39;, mapped, filtered)\n\ntry:\n    code = &#39;[y for x in (n := 3) for y in range(n)]&#39;\n    compile(code, &#39;&lt;s&gt;&#39;, &#39;eval&#39;)\nexcept SyntaxError as e:\n    print(&#39;walrus in iterable&#39;, type(e).__name__)", "note": "惰性求值的边界与海象运算符"}]' title='两种写法对照' note='差异集中在 列表 / 集合 / 字典推导式；先看输出，再找背后的规则。' />


## 惰性求值的边界与海象运算符

生成器表达式的惰性有一个关键例外：最外层 iterable 在**创建时**就被求值并绑定（编译成 `LOAD_FAST` 后立刻 `GET_ITER`），之后的中间步骤才延迟执行。

所以 `data = [1, 2]`、`g = (x for x in data)`、`data = [9]` 依次执行之后，`list(g)` 仍是 `[1, 2]`，重新绑定同名变量不改变已构造的生成器；

要换输入得重新构造，或把数据源作为参数传进函数。

生成器表达式作为函数唯一参数时可省掉一层括号，`sum(x*x for x in xs)` 就是惯用写法。

3.8 的 PEP 572 引入海象运算符 `:=`，可在值表达式与 `if` 子句里把昂贵计算的结果存进变量复用，例如把 `f(x)` 的结果写成 `(y := f(x))` 后，在 `if` 判断里直接用，让 `f(x)` 只算一次；

但它不能写在最外层 `for` 的 iterable 里，compile 会抛 `SyntaxError`，因为绑定目标的作用域会产生歧义。另外 `for` 目标不泄漏到外层，而 `:=` 的目标按 PEP 572 绑定到包含作用域，两条作用域规则不同，别混为一谈。

```python
import sys

def pipeline(rows):
    cleaned = (int(r.strip()) for r in rows if r.strip())
    squared = (x * x for x in cleaned)
    return (x for x in squared if x > 10)

rows = [' 1 ', '2', '', ' 4 ', '5']
print('pipeline', list(pipeline(rows)))
print('gen size constant', sys.getsizeof((x for x in range(10**6))) < 1000)

mapped = list(map(lambda x: x * 2, [1, 2, 3]))
filtered = list(filter(lambda x: x > 2, [1, 2, 3, 4]))
print('map filter', mapped, filtered)

try:
    code = '[y for x in (n := 3) for y in range(n)]'
    compile(code, '<s>', 'eval')
except SyntaxError as e:
    print('walrus in iterable', type(e).__name__)
```

<OutputBox title='对照写法：先自己猜，再点开' output='pipeline [16, 25]\ngen size constant True\nmap filter [2, 4, 6] [3, 4]\nwalrus in iterable SyntaxError' guess="true" />


## 推导式的作用域边界与版本差异

**版本与作用域差异**

| 版本 / 规则 | 行为 | 影响 |
| --- | --- | --- |
| Python 2 列表推导 | 循环变量会泄漏到外层作用域 | 迁移到 3 时该行为改变 |
| Python 3 推导式 | 独立作用域，循环变量不泄漏 | 外层同名变量不被覆盖 |
| 3.8 PEP 572 | := 可用于值表达式与 if，禁止在最外层 iterable | 复用中间结果，避免重复计算 |
| 3.12 PEP 709 | 推导式内联到外层作用域提速，但保持变量隔离语义 | 性能提升，语义不变 |
| 普通 for 循环 | 循环变量留在当前作用域 | 与推导式的隔离语义相反 |

```python
import dis
from time import perf_counter

def with_comp():
    x = 'outer'
    return x, [x for x in range(3)]
print('scope isolated', with_comp())

g = (x for x in range(3))
print('frame exists', g.gi_frame is not None)
print('first value', next(g))
print('generator protocol', hasattr(g, 'send'), hasattr(g, 'throw'), hasattr(g, 'close'))

def loop(n):
    out = []
    for i in range(n):
        out.append(i * i)
    return out
n = 100000
t0 = perf_counter(); loop(n); t_loop = perf_counter() - t0
t0 = perf_counter(); [i * i for i in range(n)]; t_comp = perf_counter() - t0
print('comprehension faster', t_comp < t_loop)
print('LIST_APPEND present', 'LIST_APPEND' in dis.Bytecode(lambda: [i for i in range(3)]).dis())
```

<OutputBox title='原理验证' output='scope isolated (&#39;outer&#39;, [0, 1, 2])\nframe exists True\nfirst value 0\ngenerator protocol True True True\ncomprehension faster True\nLIST_APPEND present True' />

CPython 把列表、集合、字典推导式编译成一个隐式函数并在其中执行（3.12 起 PEP 709 改为内联到外层作用域以省一次函数调用，但通过临时保存外层同名变量、执行后恢复来保持隔离语义），因此推导式的循环变量不会泄漏到外层，而普通 `for` 循环的变量会留在当前作用域。

列表推导内部用专用的 `LIST_APPEND` / `SET_ADD` / `MAP_ADD` 字节码直接向结果容器追加，避免了等价 `for` 循环里每次查找 `append` 与函数调用的开销，所以通常比 `for` 加 `append` 更快。

生成器表达式则根本不构造容器：它返回一个 generator 对象，帧里保存指令指针与局部变量，只有 `next()` / `for` / `sum()` 消费时才逐条产出，内存占用与输入规模无关。

但最外层 iterable 在创建时就被求值并绑定（编译成 `LOAD_FAST` 后立即 `GET_ITER`），之后重新绑定同名变量不影响已生成的生成器，这是惰性求值里最容易踩的例外。

3.8 的 PEP 572 允许 `:=` 在值表达式与 `if` 里复用中间结果，却禁止在最外层 iterable 里赋值，避免绑定目标作用域歧义。


## 可读性边界与退回循环的判据

推导式的优势是紧凑与意图清晰，但不是写得越短越好。单重变换加单个过滤、两层嵌套 `for` 都还在可读范围；一旦嵌套三层以上、堆多个 `if`，或需要 `break` 提前终止、按条件走不同分支、做异常处理，可读性会急转直下，且推导式本身无法中断、无法局部捕获异常，此时普通循环配合早返回更清楚、也更好测。

有副作用的操作（写日志、改外部状态、发请求）同样不该塞进推导式，它应当只做纯变换。数据清洗管道的正确形状是把每步写成生成器表达式或小的生成器函数，用 `yield from` 串起来，只有最终聚合（`sum()` / `list()` / `most_common()`）才真正消费；

这样内存占用与单个元素相关，能处理远超内存的数据。map / filter 在已有具名函数时比等价推导式更直接，但 Python 3 里它们返回迭代器而非列表，需要 `list()` 才会物化。把「是否要物化、是否要中断、是否有副作用」先问一遍，就知道该用推导式还是循环。

**可读性边界与选型**

| 场景 | 推荐写法 | 原因 |
| --- | --- | --- |
| 单重变换加单个过滤 | 推导式 | 紧凑且意图清晰 |
| 两层嵌套 for | 推导式（保持左外右内） | 执行顺序仍可读 |
| 三层以上嵌套或多个 if | 退回普通循环 | 可读性急转直下，难测难改 |
| 需要 break、早返回或异常处理 | 普通循环 | 推导式无法中断或抛自定义分支 |
| 有副作用（写日志、改外部状态） | 普通循环 | 推导式应只做纯变换 |
| 远超内存的数据流 | 生成器表达式串联 | 惰性求值，内存恒定 |


## 数据清洗管道：用生成器表达式串联处理大文本流

一个 ETL 任务要从远超内存的文本流里抽取数字、过滤无效行、换算并聚合。若每一步都写成列表推导，中间结果会把内存撑爆；正确做法是把每步写成生成器表达式，串成惰性管道，只有最终聚合才真正消费。下面用标准库模拟一个可迭代的行源，定义去空白、转整数、过滤阈值、平方四级阶段，证明中间没有物化整份数据。

再演示把统计逻辑与 IO 分开：核心只接受可迭代对象，测试时传 list、生产时传文件迭代器都不用改，命令分发与聚合也各自独立。重点是内存恒定与可测性，而不是把表达式写得多短。

```python
import io

def make_source(text):
    return io.StringIO(text)

def pipeline(lines):
    stripped = (line.strip() for line in lines)
    nonempty = (s for s in stripped if s)
    numbers = (int(s) for s in nonempty)
    big = (n for n in numbers if n >= 10)
    squared = (n * n for n in big)
    return squared

rows = ' 1' + chr(10) + '20' + chr(10) + '' + chr(10) + '5' + chr(10) + '30'
result = list(pipeline(make_source(rows)))
print('filtered squares', result)
print('count', len(result), 'sum', sum(result))

def aggregate(lines):
    total = 0
    count = 0
    for value in pipeline(lines):
        total += value
        count += 1
    return {'count': count, 'total': total}

print('aggregate from list', aggregate(['12', ' 40 ', '3']))
print('aggregate from file', aggregate(make_source('11' + chr(10) + '25')))
```

<Callout type="idea" title='落地提示' text='数据清洗管道里用生成器表达式串起来，可在不落盘的前提下处理远超内存的数据' />

<CheckList id='P024b' title='上线前自检' :items='["能复现并解释「以为推导式的循环变量会像 for 一样留在外面」", "能复现并解释「生成器表达式创建后改了源列表，消费结果没变」", "能复现并解释「嵌套三层还硬塞推导式，代码没人看得懂」", "能用一条命令验证 列表 / 集合 / 字典推导式", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "xs=[3,1,2]; print(sorted(xs), xs[::-1], len(xs))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 列表 / 集合 / 字典推导式 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 推导式练习与可读性复盘

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 以为推导式的循环变量会像 for 一样留在外面 | Python 3 推导式有独立作用域，循环变量不泄漏；外层同名变量不会被覆盖 | 需要结果就用推导式的返回值，别依赖循环后的变量；确实要副作用就退回普通 for |
| 生成器表达式创建后改了源列表，消费结果没变 | 最外层 iterable 在生成器创建时就被求值并绑定，只有后续部分延迟 | 把数据源作为参数传进函数，或重新构造生成器；别靠重新绑定同名变量改输入 |
| 嵌套三层还硬塞推导式，代码没人看得懂 | 多 for 加多 if 叠加后执行顺序与短路关系难读，且无法 break 或做异常处理 | 退回普通循环配合早返回，或拆成命名清晰的生成器函数分阶段处理 |

<Callout type="warn" title='本讲最容易踩的坑' text='以为推导式的循环变量会像 for 一样留在外面：Python 3 推导式有独立作用域，循环变量不泄漏；外层同名变量不会被覆盖' />

<Exercise title='基础：写四种推导式并验证作用域隔离' task='对同一组数字分别写列表、集合、字典推导式与生成器表达式，打印各自类型与结果；用一个外层同名变量验证推导式不会覆盖它。' solution='nums = [1, 2, 2, 3]\nx = &#39;outer&#39;\nlst = [n * n for n in nums]\nst = {n for n in nums}\nd = {n: n * n for n in nums}\ng = (n * n for n in nums)\nprint(&#39;types&#39;, type(lst).__name__, type(st).__name__, type(d).__name__, type(g).__name__)\nprint(&#39;values&#39;, lst, sorted(st), d, list(g))\nprint(&#39;outer intact&#39;, x)' explain='四种写法对应四种结果类型；生成器表达式惰性、只有 list() 消费时才产出。推导式的循环变量 n 有独立作用域，不会污染外层的 x。' />

<Exercise title='进阶：用海象避免重复计算并识别禁止位置' task='写一个推导式，用 := 把昂贵计算的结果存进变量、在 if 与值表达式里复用；再尝试把 := 放进最外层 iterable，用 compile 捕获 SyntaxError。' solution='def score(x):\n    return x * x - 3\n\ndata = [1, 2, 3, 4]\nkept = [s for x in data if (s := score(x)) &gt; 0]\nprint(&#39;walrus reuse&#39;, kept)\n\ntry:\n    compile(&#39;[y for y in (n := [1, 2])]&#39;, &#39;&lt;s&gt;&#39;, &#39;eval&#39;)\nexcept SyntaxError as e:\n    print(&#39;iterable forbidden&#39;, type(e).__name__)' explain='3.8 起 := 可在 if 与值表达式里复用中间结果，避免把 score(x) 算两次；但禁止放在最外层 iterable，compile 会抛 SyntaxError。另外 for 目标不泄漏到外层，而 := 的目标按 PEP 572 绑定到包含作用域，两者规则不同。' />

<Quiz no='024-1' q='关于推导式的作用域，哪项准确？' :options='["循环变量会像 for 一样留在外层", "Python 3 推导式有独立作用域、循环变量不泄漏；普通 for 会泄漏", "Python 2 与 3 行为相同", "3.12 起循环变量开始泄漏"]' answer="1" explain='Python 3 推导式编译为独立作用域（3.12 PEP 709 内联后仍用临时变量保持隔离），循环变量不泄漏；Python 2 的列表推导会泄漏，普通 for 循环的变量一直留在当前作用域。' />

<Quiz no='024-2' q='关于生成器表达式，哪个说法正确？' :options='["创建时就计算完所有值", "惰性求值、内存恒定，但最外层 iterable 在创建时就被求值绑定", "返回 list", "可以多次完整遍历"]' answer="1" explain='生成器表达式返回 generator，消费时才逐个产出；最外层 iterable 在构造时即 GET_ITER 绑定，之后重新绑定同名变量不影响它；生成器是一次性的。' />

<Quiz no='024-3' q='3.8 的海象 := 在推导式里，哪种用法会抛 SyntaxError？' :options='["在值表达式里复用结果", "在 if 过滤条件里复用结果", "放在最外层 for 的 iterable 里", "在嵌套函数里"]' answer="2" explain='PEP 572 禁止在 comprehension iterable expression 里用 :=，避免绑定目标作用域歧义；但值表达式与 if 子句里可以正常使用。' />

<KnowledgeCard :points='["列表 / 集合 / 字典推导式立即构造容器；生成器表达式返回惰性 generator，内存恒定", "Python 3 推导式有独立作用域、循环变量不泄漏；3.12 PEP 709 内联提速但保持隔离语义", "生成器表达式最外层 iterable 在创建时求值绑定，重新绑定同名变量不影响它", "多重 for 按从左到右嵌套、多个 if 等价 and；值表达式可用三元条件，过滤用 for 后的 if", "3.8 起 := 可在值表达式与 if 里复用中间结果，但禁止在最外层 iterable 赋值", "嵌套三层以上、需要 break 或早返回、异常处理或有副作用时退回普通循环；列表推导通常比 for + append 快"]' :pitfalls='["以为推导式的循环变量会像 for 一样留在外面", "生成器表达式创建后改了源列表，消费结果没变", "嵌套三层还硬塞推导式，代码没人看得懂", "嵌套三层以上还硬塞推导式，可读性会急转直下，此时普通循环配合早返回更清楚"]' summary='推导式有独立作用域，不会泄漏循环变量；生成器表达式则把计算推迟到消费时，内存占用恒定' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 列表 / 集合 / 字典推导式立即构造容器；生成器表达式返回惰性 generator，内存恒定 | 建立直觉 |
| Python 3 推导式有独立作用域、循环变量不泄漏；3.12 PEP 709 内联提速但保持隔离语义 | 跑通示例 |
| 生成器表达式最外层 iterable 在创建时求值绑定，重新绑定同名变量不影响它 | 深入边界 |
| 多重 for 按从左到右嵌套、多个 if 等价 and；值表达式可用三元条件，过滤用 for 后的 if | 工程落地 |
| 3.8 起 := 可在值表达式与 if 里复用中间结果，但禁止在最外层 iterable 赋值 | 随堂检测 |
| 嵌套三层以上、需要 break 或早返回、异常处理或有副作用时退回普通循环；列表推导通常比 for + append 快 | 复盘 |

1. 列表 / 集合 / 字典推导式立即构造容器；生成器表达式返回惰性 generator，内存恒定

2. Python 3 推导式有独立作用域、循环变量不泄漏；3.12 PEP 709 内联提速但保持隔离语义

3. 生成器表达式最外层 iterable 在创建时求值绑定，重新绑定同名变量不影响它

[下一讲：迭代协议：iterable、iterator 与惰性求值](/containers/iterator)

<Predict no='024-4' q='data = [1, 2, 3]; g = (x * x for x in data); data = [9]; print(list(g)) 输出什么？' :options='["[1, 4, 9]", "[81]", "[]"]' answer='0' output='[1, 4, 9]' explain='生成器表达式创建时最外层 iterable 已被求值并绑定为原列表的迭代器，之后把 data 重新绑定到新列表不影响生成器；消费时仍产出 1、4、9。惰性只针对后续计算，不针对最外层数据源的绑定。' />

<FillBlank no='024-5' tpl='squares = [x * x for x ___ nums]' :answers='["in"]' hint='回想本讲关于 列表 / 集合 / 字典推导式 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 四种推导式、作用域与专用字节码 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/024-comprehension.py`

```bash
python3 examples/lessons/024-comprehension.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/024-comprehension.py) · [全部示例代码索引](/examples/)
