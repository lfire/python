---
title: 第 075 讲 · 单元测试：pytest、fixture 与参数化
description: 写出快、稳、能定位问题的测试
---

<StageHeader stage='L7 · 工程化' level='★★☆☆☆' time='40 分钟' goal='写出快、稳、能定位问题的测试' prereq='第 074 讲 · 静态检查：mypy / pyright 与渐进式类型' />

# 第 075 讲 · 单元测试：pytest、fixture 与参数化

静态检查挡住了一类错，可行为对不对还得靠真跑一遍。这一讲给代码装护栏：写出快、稳、失败时能一眼看出哪条约定破了的单元测试。有套订单测试把内部函数替身得一丝不差，重构改了实现两百个用例全红，却没有一条真正验证「下单后库存扣减」这个外部行为。

先看断言重写为什么让失败信息更清楚，再讲 fixture 的作用域与生命周期，接着用参数化与 mark 收拢相似用例，然后谈 tmp_path、monkeypatch 与替身，最后借测试金字塔和覆盖率找盲区。前置是函数、异常与断言；学完能优先测公开行为与边界，让 fixture 只准备必要状态，把慢 IO 交给替身。


## 两百个测试全红，却没一条验证「下单后库存扣减」

一个订单服务的测试套件里，每个用例都把内部私有函数 mock 得一丝不差，重构时改了实现，两百个测试全红，却没有任何一条真正验证「下单后库存扣减」这个外部行为；还有人跑测试加了 `-O`，所有 assert 被优化掉，绿灯全是假象。

另一类问题是用例失败时只抛一串 AssertionError，后面跟着一个看不懂的内部状态对象，没人知道哪条契约被破坏。pytest 的价值不在「能写 assert」，而在断言重写、fixture 作用域、参数化与替身这套机制能让失败直接指出被破坏的契约。

本讲把收集与重写、fixture 生命周期、参数化与覆盖率解读讲到能写出快、稳、可定位的测试。

<Callout type="warn" title='先看一个真实会出错的写法' text='过度 mock，把测试写成实现的镜像：每个内部私有函数都被替身锁死，重构时测试全红却没验证任何外部行为' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段七 · 工程化与质量 |
| 前置 | 第 074 讲 · 静态检查：mypy / pyright 与渐进式类型 |
| 难度 / 建议时长 | ★★☆☆☆ · 40 分钟 |
| 本讲新增 | 断言重写、fixture 作用域、参数化与 mark |
| 一句话目标 | 写出快、稳、能定位问题的测试 |
| 为下一讲铺垫 | Mock 与测试替身：时间、网络与随机 |


## 收集规则：pytest 怎么找到测试

pytest 通过 `import hook`（`pytest.register_assert_rewrite`）在导入测试模块时改写 assert 节点，把 `assert a + b == c` 拆成对每个子表达式求值并暂存结果，因此失败信息会显示哪里得到什么值；

裸 Python 的 assert 失败只抛 `AssertionError`，没有任何中间值。

代价是断言必须在 pytest 收集到的模块里才被重写，且不能用 `python -O` 跑测试——`compile` 在 `optimize=1` 下会把所有 `ast.Assert` 节点从字节码里删掉，`x=-1` 时 `optimize=0` 抛 AssertionError、`optimize=1` 却照常执行。

辅助断言有 `pytest.raises`、`pytest.approx`、`pytest.warns`。

收集约定：文件 `test_*.py` 或 `*_test.py`、函数 `test_*`、类 `Test*`（无 `__init__`），配置放 `pytest.ini` 或 `pyproject.toml` 的 `[tool.pytest.ini_options]`，`conftest.py` 里放跨文件共享的 fixture。

常用命令 `-x` 首败即停、`-k` 按名筛、`-m` 按 mark 筛、`--lf` 只跑上次失败、`-q` 精简输出。

**pytest 常用机制**

| 机制 / 命令 | 作用 | 注意 |
| --- | --- | --- |
| 断言重写 | 失败显示子表达式值 | 裸 assert 无此能力，别用 -O 跑测试 |
| @pytest.mark.parametrize | 一条断言展开多组用例 | 配 ids 让失败可定位 |
| pytest.raises / approx / warns | 异常、浮点、警告断言 | match= 校验异常消息 |
| monkeypatch / tmp_path | 自动还原的替身与临时目录 | function 级，无需手动清理 |
| conftest.py | 跨文件共享 fixture | 不要在里面写业务逻辑 |
| -x / -k / -m / --lf / -q | 运行筛选 | 自定义 mark 需注册 |


## AssertionRewritingHook：sys.meta_path 上的断言重写

pytest 的 `AssertionRewritingHook` 是 `sys.meta_path` 上的一个 finder：导入测试模块前先读源码、用 `ast` 解析，把每个 `ast.Assert` 节点替换成「先计算并暂存各子表达式、再比较、失败时抛出带中间值的 `AssertionError`」的等价语句，因此失败输出能显示 `assert 1 + 2 == 4` 里 1+2 的值；

这也是为什么测试必须由 pytest 收集而非直接 python 运行。`compile` 在 `optimize=1`（等价 `python -O`）下会在编译期删掉所有 `ast.Assert`，`dis` 可见 `optimize=0` 的指令数更多。

`FixtureManager` 按 scope 维护缓存与 setup/finalize 栈：yield fixture 把 yield 之后的代码注册为 finalizer，逆序执行保证先拆小作用域。

`coverage.py` 借助 `sys.settrace`（3.12 起可切到 `sys.monitoring`）记录被执行的行与弧，分支覆盖进一步记录跳转是否两边都走到。

<Callout type="tip" title='核心心智模型' text='pytest 通过 import hook（`pytest.register_assert_rewrite`）在导入测试模块时改写 assert 节点，把 `assert a + b == c` 拆成对每个子表达式求值并暂存结果，因此失败信息会显示哪里得到什么值；裸 Python 的 assert ' />

<ConceptDiagram type='flow3' title='第 075 讲 · 断言重写与收集规则' labels='断言重写与收集规则|fixture 作用域、yield 清理与内|参数化、mark、测试金字塔与覆盖率' caption='写出快、稳、能定位问题的测试' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 对照：裸 assert 与重写后的失败信息

```python
import tempfile, os
from contextlib import contextmanager

CASES = [(2, 3, 5), (0, 0, 0), (-1, 1, 0), (10, -3, 7)]

def add(a, b):
    return a + b

results = []
for a, b, expected in CASES:
    got = add(a, b)
    results.append((a, b, got == expected))
print('cases', len(results))
print('all passed', all(ok for *_, ok in results))

@contextmanager
def tmp_file():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, 'data.txt')
        with open(path, 'w') as f:
            f.write('seed')
        yield path

with tmp_file() as p:
    with open(p) as f:
        print('fixture content', f.read())
print('cleaned up', not os.path.exists(p))
```

<OutputBox title='主示例运行结果' output='cases 4\nall passed True\nfixture content seed\ncleaned up True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import tempfile, os\nfrom contextlib import contextmanager\n\nCASES = [(2, 3, 5), (0, 0, 0), (-1, 1, 0), (10, -3, 7)]\n\ndef add(a, b):\n    return a + b\n\nresults = []\nfor a, b, expected in CASES:\n    got = add(a, b)\n    results.append((a, b, got == expected))\nprint(&#39;cases&#39;, len(results))\nprint(&#39;all passed&#39;, all(ok for *_, ok in results))\n\n@contextmanager\ndef tmp_file():\n    with tempfile.TemporaryDirectory() as d:\n        path = os.path.join(d, &#39;data.txt&#39;)\n        with open(path, &#39;w&#39;) as f:\n            f.write(&#39;seed&#39;)\n        yield path\n\nwith tmp_file() as p:\n    with open(p) as f:\n        print(&#39;fixture content&#39;, f.read())\nprint(&#39;cleaned up&#39;, not os.path.exists(p))' :notes='["导入 tempfile/os 建临时资源，contextmanager 做 teardown", "从 contextlib 取 contextmanager 装饰生成器式 fixture", "CASES 是参数化用例：每组含两个输入与期望", "定义被测公开函数 add", "返回两数之和，行为简单可精确断言", "results 收集每个用例的通过布尔", "逐组驱动，等价于 parametrize 展开", "计算实际值", "把 (输入, 输入, 是否相等) 记入结果", "打印用例数量，确认 4 组都被跑到", "用星号解包取最后的布尔，校验全部通过", "定义 yield 式 fixture：setup 产出、退出清理", "TemporaryDirectory 在退出时自动删目录", "在临时目录里准备一个文件路径", "写入 seed 作为 fixture 状态", "yield 把路径交给用例，暂停在此", "with 块内使用 fixture 提供的资源", "读出并打印 fixture 内容", "退出 with 后目录已被清理，路径不存在", "compile(optimize=1) / python -O 删除所有 assert，测试绿灯会失真，绝不能开 -O", "fixture 作用域 function→session 复用递增，yield fixture 保证失败也 teardown，finalize 逆序", "tmp_path（function）、tmp_path_factory（session）、monkeypatch（自动还原）是内置替身"]' title='第 075 讲 · 单元测试：pytest、fixture 与参数化' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import ast
from unittest.mock import patch

tree = ast.parse('assert add(2, 3) == 6')
node = tree.body[0]
print('is Assert node', isinstance(node, ast.Assert))
print('test is Compare', isinstance(node.test, ast.Compare))
print('left is Call', isinstance(node.test.left, ast.Call))

class Config:
    DEBUG = False

with patch.object(Config, 'DEBUG', True):
    print('inside patch', Config.DEBUG)
print('after patch restored', Config.DEBUG)
```

<OutputBox title='对照写法：先自己猜，再点开' output='is Assert node True\ntest is Compare True\nleft is Call True\ninside patch True\nafter patch restored False' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import tempfile, os\nfrom contextlib import contextmanager\n\nCASES = [(2, 3, 5), (0, 0, 0), (-1, 1, 0), (10, -3, 7)]\n\ndef add(a, b):\n    return a + b\n\nresults = []\nfor a, b, expected in CASES:\n    got = add(a, b)\n    results.append((a, b, got == expected))\nprint(&#39;cases&#39;, len(results))\nprint(&#39;all passed&#39;, all(ok for *_, ok in results))\n\n@contextmanager\ndef tmp_file():\n    with tempfile.TemporaryDirectory() as d:\n        path = os.path.join(d, &#39;data.txt&#39;)\n        with open(path, &#39;w&#39;) as f:\n            f.write(&#39;seed&#39;)\n        yield path\n\nwith tmp_file() as p:\n    with open(p) as f:\n        print(&#39;fixture content&#39;, f.read())\nprint(&#39;cleaned up&#39;, not os.path.exists(p))", "note": "断言重写与收集规则"}, {"label": "对照 / 进阶", "code": "import ast\nfrom unittest.mock import patch\n\ntree = ast.parse(&#39;assert add(2, 3) == 6&#39;)\nnode = tree.body[0]\nprint(&#39;is Assert node&#39;, isinstance(node, ast.Assert))\nprint(&#39;test is Compare&#39;, isinstance(node.test, ast.Compare))\nprint(&#39;left is Call&#39;, isinstance(node.test.left, ast.Call))\n\nclass Config:\n    DEBUG = False\n\nwith patch.object(Config, &#39;DEBUG&#39;, True):\n    print(&#39;inside patch&#39;, Config.DEBUG)\nprint(&#39;after patch restored&#39;, Config.DEBUG)", "note": "fixture 作用域、yield 清理与内置替身"}]' title='两种写法切换看' />


## 用 python -O 跑测试会发生什么

```python
import ast, dis, sys

src = 'assert x > 0' + chr(10) + 'out = "passed"'
print('assert nodes', sum(isinstance(n, ast.Assert) for n in ast.walk(ast.parse(src))))
code0 = compile(src, '<s>', 'exec', optimize=0)
code1 = compile(src, '<s>', 'exec', optimize=1)
print('more instr', len(list(dis.get_instructions(code0))) > len(list(dis.get_instructions(code1))))
print('flags.optimize', sys.flags.optimize)

def run(x, code):
    ns = {'x': x}
    exec(code, ns)
    return ns['out']

try:
    run(-1, code0)
except AssertionError:
    print('optimize=0 AssertionError')
print('optimize=1', run(-1, code1))
```

<OutputBox title='原理验证' output='assert nodes 1\nmore instr True\nflags.optimize 0\noptimize=0 AssertionError\noptimize=1 passed' />

<Callout type="warn" title='本讲最容易踩的坑' text='过度 mock，把测试写成实现的镜像：每个内部私有函数都被替身锁死，重构时测试全红却没验证任何外部行为' />


## fixture 作用域、yield 清理与依赖注入

`@pytest.fixture` 用 `scope` 指定作用域，取值有 function、class、module、package、session：作用域越大复用越久，function 每用例重建、session 整轮共享，finalize 按相反顺序执行（大作用域后拆）。

yield fixture 在 yield 前 setup、之后 teardown，保证失败也清理；`autouse=True` 对本作用域内所有用例自动生效；params 让一个 fixture 产出多组值。

内置替身：`tmp_path` 是 function 级的 `pathlib.Path` 临时目录、`tmp_path_factory` 是 session 级工厂、`monkeypatch` 提供 setattr/delattr/setenv/delenv/setitem/delitem/chdir 且在用例结束自动还原。

fixture 只准备必要状态，慢 IO 用替身隔离；过度 mock 会把测试写成实现的镜像，重构时全部重写却没验证任何外部行为，应优先测公开行为与边界条件。

**fixture 作用域与生命周期**

| scope | 复用范围 | 典型用途 |
| --- | --- | --- |
| function（默认） | 每个用例重建 | 隔离状态、tmp_path |
| class | 一个类内共享 | 类级共享连接 |
| module | 一个模块内共享 | 模块级只读资源 |
| package | 一个包内共享 | 包级昂贵初始化 |
| session | 整轮测试共享 | tmp_path_factory、启动一次的服务 |
| yield fixture | yield 前 setup、之后 teardown | 保证失败也执行清理 |

<Term word='断言重写' text='pytest 通过 import hook（`pytest.register_assert_rewrite`）在导入测试模块时改写 assert 节点，把 `assert a + b == c` 拆成对每个子表达式求值并暂存结果，因此失败信息会显示哪里得到什么值；裸 Python 的 assert 失败只抛 `Asse' />

<Term word='fixture 作用域' text='`@pytest.fixture` 用 `scope` 指定作用域，取值有 function、class、module、package、session：作用域越大复用越久，function 每用例重建、session 整轮共享，finalize 按相反顺序执行（大作用域后拆）。yield fixture 在 yield' />


## 参数化、mark 与内置替身 tmp_path / monkeypatch

```bash
python -m pytest -q --disable-warnings
```

把输入换成你自己的数据，观察结果是否仍符合 断言重写 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

<CheckList id='P075a' title='学完你应当能' :items='["能讲清 断言重写与收集规则", "能讲清 fixture 作用域、yield 清理与内置替身", "能讲清 参数化、mark、测试金字塔与覆盖率", "能在工程里处理 覆盖率解读"]' />


## 测试金字塔与覆盖率怎么读

`@pytest.mark.parametrize` 把一组参数展开成多个独立用例，失败能定位到具体参数组；

`pytest.param` 给单组打标记（如 skip、xfail），自定义 mark 要在配置里注册，避免 `PytestUnknownMarkWarning`。

测试金字塔：底层大量快而稳的单元测、中层少量集成测、顶层极少量端到端测；越往上越慢越脆，比例倒置会让 CI 变成瓶颈。

覆盖率用 `pytest-cov` 的 `--cov=pkg` 与 `--cov-report=term-missing`，看行覆盖与分支覆盖（`--cov-branch`），`coverage.py` 通过 `sys.settrace`（3.12 起可切到 `sys.monitoring`）记录执行行。

覆盖率是发现盲区的线索，不是 KPI：100% 行覆盖不代表断言有效，未覆盖的分支、异常路径与边界值才是优先补的地方。把慢 IO 隔离、参数化覆盖边界、失败信息可读，三者合起来才是「快、稳、能定位」的测试。

**测试金字塔与覆盖率解读**

| 层次 / 指标 | 特征 | 定位 |
| --- | --- | --- |
| 单元测试 | 多、快、稳，替身隔离 IO | 公开行为与边界条件 |
| 集成测试 | 中量，验证组件协作 | 接口契约与真实依赖 |
| 端到端测试 | 极少、慢、脆 | 关键用户路径 |
| 行覆盖 / 分支覆盖 | coverage.py 记录执行 | 找盲区，不是 KPI |
| 100% 行覆盖 | 不代表断言有效 | 优先补未覆盖分支与异常路径 |


## 用标准库模拟 fixture 注册表与参数化

要理解 pytest 的核心机制，可以手写一个最小骨架：一个按 scope 记录 fixture 的注册表、一个把用例列表展开成多个独立调用的 parametrize 装饰器，再加一个断言即用例。

这样能看清「参数化是收集期展开」「fixture 按作用域缓存」「断言失败自带哪组参数」这三件事，而不必先记住全部 pytest API。下面片段注册一个 session 级 db fixture、参数化三组加法用例并打印结果，演示这套机制的最小可运行形态。

真实项目把装饰器换成 `@pytest.fixture` / `@pytest.mark.parametrize` 即可。

```python
FIXTURES = {}

def fixture(scope='function'):
    def deco(fn):
        FIXTURES[fn.__name__] = (scope, fn)
        return fn
    return deco

@fixture(scope='session')
def db():
    return {'users': ['ann', 'bob'], 'port': 5432}

def parametrize(cases):
    def deco(fn):
        def run():
            return [fn(*case) for case in cases]
        return run
    return deco

@parametrize([(2, 3, 5), (0, 0, 0), (-1, 1, 0)])
def test_add(a, b, expected):
    assert a + b == expected, (a, b)
    return True

print('fixtures', sorted(FIXTURES))
print('db scope', FIXTURES['db'][0])
print('db port', FIXTURES['db'][1]()['port'])
print('param results', test_add())
```

<Callout type="idea" title='落地提示' text='优先测公开行为与边界条件，fixture 只准备必要状态，慢 IO 用替身，覆盖率作为发现盲区的线索而非 KPI' />

<CheckList id='P075b' title='上线前自检' :items='["能复现并解释「过度 mock，把测试写成实现的镜像」", "能复现并解释「用 python -O 跑测试或依赖裸 assert 的报错」", "能复现并解释「把覆盖率 100% 当 KPI、fixture 准备过多共享」", "能用一条命令验证 断言重写", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 过度 mock，把测试写成实现的镜像 | 每个内部私有函数都被替身锁死，重构时测试全红却没验证任何外部行为 | 优先测公开行为与边界条件，用 fake 替身慢 IO，少用深度 assert_called_once_with 链 |
| 用 python -O 跑测试或依赖裸 assert 的报错文本 | optimize=1 编译会删掉所有 ast.Assert，绿灯全是假象 | 测试用 pytest 收集且不开 -O；靠断言重写提供的子表达式值定位契约 |
| 把覆盖率 100% 当 KPI、fixture 准备过多共享状态 | 行覆盖高不代表断言有效，共享状态让用例相互污染、变慢变脆 | 覆盖率用于发现盲区，优先补未覆盖分支；fixture 只备必要状态，慢 IO 用替身隔离 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：过度 mock，把测试写成实现的镜像", "body": "每个内部私有函数都被替身锁死，重构时测试全红却没验证任何外部行为", "tip": "优先测公开行为与边界条件，用 fake 替身慢 IO，少用深度 assert_called_once_with 链"}, {"title": "第 2 步：用 python -O 跑测试或依赖裸 as", "body": "optimize=1 编译会删掉所有 ast.Assert，绿灯全是假象", "tip": "测试用 pytest 收集且不开 -O；靠断言重写提供的子表达式值定位契约"}, {"title": "第 3 步：把覆盖率 100% 当 KPI、fixtur", "body": "行覆盖高不代表断言有效，共享状态让用例相互污染、变慢变脆", "tip": "覆盖率用于发现盲区，优先补未覆盖分支；fixture 只备必要状态，慢 IO 用替身隔离"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：把用例表展开成参数化断言' task='给定 [(1,2,3),(5,-5,0)]，逐组计算 a+b 是否等于期望并打印布尔列表。' solution='cases = [(1, 2, 3), (5, -5, 0)]\nprint([a + b == e for a, b, e in cases])' explain='参数化的本质是把一条断言展开成多组独立输入；失败时能定位到具体参数组，比在用例里手写循环更可读。' />

<Exercise title='进阶：验证 patch 上下文的自动还原' task='用 unittest.mock.patch.object 临时把类属性改成 9，退出 with 后打印原值，确认还原。' solution='from unittest.mock import patch\nclass C:\n    V = 1\nwith patch.object(C, &#39;V&#39;, 9):\n    print(&#39;inside&#39;, C.V)\nprint(&#39;restored&#39;, C.V)' explain='patch 作为上下文管理器在退出时把属性还原成保存的原值，等价于 monkeypatch 的自动 undo，保证用例之间不串状态。' />

<Quiz no='075-1' q='pytest 断言重写相比裸 assert 的关键收益是？' :options='["失败时显示各子表达式的中间值，直接指出哪条契约被破坏", "让 assert 运行更快", "在 -O 下依然生效", "自动生成测试用例"]' answer="0" explain='重写 hook 把 assert 拆成子表达式求值并暂存结果，失败消息带上中间值；裸 assert 只有一行 AssertionError，且 -O 会把断言删掉。' />

<Quiz no='075-2' q='用 python -O 运行 pytest 测试的主要风险是？' :options='["optimize=1 编译删除所有 ast.Assert，断言被跳过、绿灯失真", "测试收集变慢", "fixture 全部失效", "覆盖率无法统计"]' answer="0" explain='compile(..., optimize=1) 在编译期移除 ast.Assert；x=-1 时 optimize=0 抛 AssertionError、optimize=1 照常执行，所以测试绝不能开 -O。' />

<Quiz no='075-3' q='关于覆盖率，正确的态度是？' :options='["作为发现未覆盖分支与异常路径的线索，而非要求 100% 的 KPI", "行覆盖 100% 即代表断言有效", "覆盖率越高测试越稳", "只需统计集成测试覆盖"]' answer="0" explain='coverage.py 记录执行行/弧，100% 行覆盖不保证断言质量；应优先补未覆盖的分支、异常路径与边界值，并把慢 IO 隔离保持套件快速稳定。' />

<Predict no='075-4' q='对 &#39;assert x &gt; 0&#39; 用 compile(..., optimize=1) 后以 x=-1 执行，结果是？' :options='["不报错，断言被编译期删除", "抛 AssertionError", "抛 SyntaxError"]' answer='0' output='不报错，断言被编译期删除' explain='optimize=1（等价 python -O）在编译期删掉所有 ast.Assert，optimize=0 时 x=-1 才抛 AssertionError；这正是测试必须避免 -O 的证据。' />

<FillBlank no='075-5' tpl='___ tempfile, os' :answers='["import"]' hint='回想本讲关于 断言重写 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 断言重写与收集规则 的落点。' />

<KnowledgeCard :points='["pytest 断言重写 hook 把 ast.Assert 拆成子表达式暂存，失败输出带中间值；裸 assert 无此能力", "compile(optimize=1) / python -O 删除所有 assert，测试绿灯会失真，绝不能开 -O", "fixture 作用域 function→session 复用递增，yield fixture 保证失败也 teardown，finalize 逆序", "tmp_path（function）、tmp_path_factory（session）、monkeypatch（自动还原）是内置替身", "@pytest.mark.parametrize 在收集期展开用例，pytest.param 可给单组打 skip/xfail", "测试金字塔单元多快稳、端到端少慢脆；覆盖率找盲区不是 KPI，优先补未覆盖分支"]' :pitfalls='["过度 mock，把测试写成实现的镜像", "用 python -O 跑测试或依赖裸 assert 的报错文本", "把覆盖率 100% 当 KPI、fixture 准备过多共享状态", "过度 mock 会把测试写成实现的镜像，重构时全部重写，却没验证任何外部行为"]' summary='好的测试失败时能直接指出哪条契约被破坏，而不是抛出一串看不懂的内部状态' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| pytest 断言重写 hook 把 ast.Assert 拆成子表达式暂存，失败输出带中间值；裸 assert 无此能力 | 建立直觉 |
| compile(optimize=1) / python -O 删除所有 assert，测试绿灯会失真，绝不能开 -O | 跑通示例 |
| fixture 作用域 function→session 复用递增，yield fixture 保证失败也 teardown，finalize 逆序 | 深入边界 |
| tmp_path（function）、tmp_path_factory（session）、monkeypatch（自动还原）是内置替身 | 工程落地 |
| @pytest.mark.parametrize 在收集期展开用例，pytest.param 可给单组打 skip/xfail | 随堂检测 |
| 测试金字塔单元多快稳、端到端少慢脆；覆盖率找盲区不是 KPI，优先补未覆盖分支 | 复盘 |

1. pytest 断言重写 hook 把 ast.Assert 拆成子表达式暂存，失败输出带中间值；裸 assert 无此能力

2. compile(optimize=1) / python -O 删除所有 assert，测试绿灯会失真，绝不能开 -O

3. fixture 作用域 function→session 复用递增，yield fixture 保证失败也 teardown，finalize 逆序

[下一讲：Mock 与测试替身：时间、网络与随机](/engineering/mock)
