---
title: 第 073 讲 · 代码规范：PEP 8、ruff、black 与 pre-commit
description: 把风格争论交给工具
---

<StageHeader stage='L7 · 工程化' level='★★☆☆☆' time='30 分钟' goal='把风格争论交给工具' prereq='第 072 讲 · 依赖管理：venv、uv、锁文件与可复现构建' />

# 第 073 讲 · 代码规范：PEP 8、ruff、black 与 pre-commit

环境可复现了，接下来是几个人写同一份代码，别把精力耗在空格和引号上。一个五年老仓库决定接入规范，有人一次性打开全量规则，结果改动里冒出上万行纯格式调整，真正的逻辑变更被淹没，评审只能草草带过；还有人在列宽和引号上反复拉扯。

顺序从分责开始：先讲 PEP 8 里哪些建议可以商量，再把格式化与 lint 分开，接着落 ruff 规则集、black 与 import 分组，然后用 pre-commit 把命令固化，末了对旧代码按修改行渐进接入。需要你熟悉函数、模块与基本的版本控制；读完后能把风格交给工具，评审只谈逻辑。


## 一次开全量规则，diff 里冒出上万行纯格式改动

一个 5 年老仓库决定接入代码规范，工程师一次性打开 ruff 全量规则并跑 black，结果 diff 里冒出上万行纯格式改动，真正的逻辑变更被彻底淹没，评审只能草草通过；有人还在 PR 里为「79 还是 88 列」「单引号还是双引号」反复拉扯。

这类争论的根源是把两件事混在一起：格式化工具决定「长什么样」，lint 决定「有没有问题」，二者该交给工具、分开执行。PEP 8 建议 79 列，black 默认 88、ruff 也默认 88；import 该按标准库/第三方/本地分组排序，这些都不该由人眼判断。

更稳妥的接入方式是新代码严格、旧代码按修改行增量检查，把同一套命令固化进 `pyproject.toml`、pre-commit 与 CI。本讲把规则集、import 排序与渐进接入讲到能直接落地。


## 格式化管长相，lint 管对错：PEP 8 的取舍

格式化工具（black、ruff format）只改空白、换行、引号、尾逗号，不改语义；ruff format 以 black 兼容为目标（0.1.2 起稳定），默认 `line-length=88`、把字符串规范化成双引号、保留 magic trailing comma。

lint（ruff check、flake8）查的是疑似缺陷与风格违规：F 系列来自 Pyflakes（未使用导入 F401、未定义名 F821）、E/W 来自 pycodestyle（E501 行过长）、N 是 pep8-naming（N802 函数名应小写）、I 是 isort（I001 导入未排序）、UP 是 pyupgrade（旧写法升级）、B 是 flake8-bugbear、S 是 bandit 安全检查、RUF 是 ruff 自有规则。

PEP 8 规定 4 空格缩进、顶层定义间 2 空行、行宽 79（文档/注释 72）、导入置顶分组；工程上普遍采用 88 列折中，关键是全仓统一并写进配置，而不是逐行争论。

**格式化器与 lint 的职责分工**

| 工具 | 负责 | 典型命令 / 默认值 |
| --- | --- | --- |
| black | 外观：缩进、换行、引号、尾逗号 | line-length=88，双引号 |
| ruff format | black 兼容格式化（0.1.2 起稳定） | ruff format . |
| ruff check | 规则：缺陷、命名、导入、安全 | ruff check --fix . |
| isort / ruff I | 导入分组与排序 | profile='black'，I001 |
| pre-commit | 提交前按暂存文件触发钩子 | pre-commit install / run --all-files |
| PEP 8 | 风格建议基线 | 4 空格、79 列、顶层定义间 2 空行 |

<ConceptDiagram type='hub4' title='第 073 讲 · 格式化与 lint 分工，以及 PEP 8 的取舍' labels='格式化与 lint 分工，以及 PEP 8 |ruff 配置、规则集与 import 排序|pre-commit 与渐进式接入 lega' caption='把风格争论交给工具' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## ruff 快速上手与规则集、import 排序

ruff 用 Rust 实现，把 lint、格式化、import 排序合进一个二进制，配置集中在 `pyproject.toml` 的 `[tool.ruff]`（line-length、target-version = 'py311'、exclude）与 `[tool.ruff.lint]`（select、ignore、per-file-ignores、fixable）。

select = ['E','F','I','N','UP','B'] 是常见起点，ignore = ['E501'] 把行宽交给格式化器；per-file-ignores = &#123;'tests/*' = ['S101']&#125; 允许测试用 assert。

逐行抑制用 # noqa 或精确到码的 # noqa: E501，文件级用 # ruff: noqa: F401，但要配合 --warn-unused-ignores 治理。I001 要求导入分三组：标准库、第三方、本地，每组内按字典序排列、组间空一行；isort 用 profile = 'black' 与格式化器对齐。

`ruff check --fix .` 只自动修可安全修复的规则，ruff format . 负责外观，二者分开跑才不会在评审里混进无关改动。

```python
import ast, tomllib

cfg = tomllib.loads(chr(10).join([
    '[tool.ruff]',
    'line-length = 88',
    'target-version = "py311"',
    '[tool.ruff.lint]',
    'select = ["E", "F", "I", "N", "UP"]',
]))
limit = cfg['tool']['ruff']['line-length']
print('line-length', limit)
print('selected', cfg['tool']['ruff']['lint']['select'])

source = [
    'def CalcTotal(a,b):',
    '    return a+b  # ' + 'x' * 90,
]
tree = ast.parse(chr(10).join(source))
names = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
long_lines = [i + 1 for i, ln in enumerate(source) if len(ln) > limit]
print('defs', names)
print('naming N802', any(n != n.lower() for n in names))
print('too long E501 lines', long_lines)
```

<OutputBox title='主示例运行结果' output='line-length 88\nselected [&#39;E&#39;, &#39;F&#39;, &#39;I&#39;, &#39;N&#39;, &#39;UP&#39;]\ndefs [&#39;CalcTotal&#39;]\nnaming N802 True\ntoo long E501 lines [2]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import ast, tomllib\n\ncfg = tomllib.loads(chr(10).join([\n    &#39;[tool.ruff]&#39;,\n    &#39;line-length = 88&#39;,\n    &#39;target-version = "py311"&#39;,\n    &#39;[tool.ruff.lint]&#39;,\n    &#39;select = ["E", "F", "I", "N", "UP"]&#39;,\n]))\nlimit = cfg[&#39;tool&#39;][&#39;ruff&#39;][&#39;line-length&#39;]\nprint(&#39;line-length&#39;, limit)\nprint(&#39;selected&#39;, cfg[&#39;tool&#39;][&#39;ruff&#39;][&#39;lint&#39;][&#39;select&#39;])\n\nsource = [\n    &#39;def CalcTotal(a,b):&#39;,\n    &#39;    return a+b  # &#39; + &#39;x&#39; * 90,\n]\ntree = ast.parse(chr(10).join(source))\nnames = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]\nlong_lines = [i + 1 for i, ln in enumerate(source) if len(ln) &gt; limit]\nprint(&#39;defs&#39;, names)\nprint(&#39;naming N802&#39;, any(n != n.lower() for n in names))\nprint(&#39;too long E501 lines&#39;, long_lines)' :notes='["导入 ast 做语法级检查、tomllib 解析 pyproject 配置", "用 tomllib.loads 读取 ruff 的 TOML 配置片段", "声明 [tool.ruff] 段", "行宽上限设为 88（ruff/black 默认）", "目标语法版本 py311，决定可用的 UP 升级规则", "声明 [tool.ruff.lint] 段", "select 启用 E/F/I/N/UP 五组规则", "从配置读出 line-length，作为 E501 判据", "打印行宽，确认配置被结构化读取", "打印启用的规则集前缀", "构造待测源码：函数名违规 + 超长行", "CalcTotal 首字母大写，命中 N802", "行尾注释把第二行撑到超过 88 列", "ast.parse 把源码转成语法树", "收集所有 FunctionDef 的名字", "逐行比对长度，记录超出行号", "打印识别到的函数名", "命名违规：名字不等于其全小写形式", "E501 命中第 2 行，格式化器会重排它", "PEP 8 建议 79 列，black/ruff 默认 line-length=88；全仓统一并写进 pyproject.toml", "ruff 规则码：F401 未用导入、F821 未定义名、E501 行过长、N802 函数名、I001 导入排序"]' title='第 073 讲 · 代码规范：PEP 8、ruff、black 与 pre-commit' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 对照：black 重排前后 AST 不变

```python
import ast

STDLIB = {'os', 'sys', 'collections'}
source = chr(10).join([
    'import sys',
    'from myapp import core',
    'import requests',
    'import os',
])

def top(module):
    return module.split('.')[0]

tree = ast.parse(source)
mods = []
for n in tree.body:
    if isinstance(n, ast.Import):
        mods += [a.name for a in n.names]
    elif isinstance(n, ast.ImportFrom):
        mods.append(n.module or '')

groups = {'stdlib': [], 'third': [], 'local': []}
for m in mods:
    root = top(m)
    key = 'stdlib' if root in STDLIB else ('local' if root == 'myapp' else 'third')
    groups[key].append(m)
for k in ('stdlib', 'third', 'local'):
    groups[k] = sorted(groups[k])
print('stdlib', groups['stdlib'])
print('third', groups['third'])
print('local', groups['local'])
print('I001 needs reorder', mods != groups['stdlib'] + groups['third'] + groups['local'])
```

<OutputBox title='对照写法：先自己猜，再点开' output='stdlib [&#39;os&#39;, &#39;sys&#39;]\nthird [&#39;requests&#39;]\nlocal [&#39;myapp&#39;]\nI001 needs reorder True' guess="true" />

black/ruff 这类格式化器先把源码 parse 成具体语法树再按统一规则重新打印，输出只改变空白、括号与引号，不改变 AST 结构——用 `ast.dump` 对比 'x=1+2' 与 'x = 1 + 2' 完全一致，正是「格式化不改语义」的可验证证据。

ruff 的 lint 则在同一份 AST/Token 流上跑数百条规则：F 系列做名字绑定分析（发现 F401/F821），E501 按 line-length 量每行字符数，N802 比对 `FunctionDef.name` 与其 `lower()` 形式，I001 把 Import/ImportFrom 归到标准库/第三方/本地三组并检查组内字典序。

规则码前缀对应来源工具，select/ignore 决定启用集合，per-file-ignores 按路径覆盖。pre-commit 把钩子注册到 .git/hooks，提交时以暂存文件列表为参数调用钩子，所以「只查改动行」是文件级机制而非工具特性；把 rev 与配置提交，保证每个开发者与 CI 跑的是同一版本规则。


## pre-commit 钩子与渐进式接入 legacy

pre-commit 用 `.pre-commit-config.yaml` 声明 repos/rev/hooks：pre-commit install 把钩子装进 .git/hooks，`pre-commit run --all-files 全量跑`，提交时默认只对暂存文件执行（pass_filenames: true 把文件名传给钩子），因此新代码天然按增量检查；

stages 可选 pre-commit、pre-push、commit-msg。把 ruff、ruff-format、以及 trailing-whitespace/end-of-file-fixer 等 hook 固定 rev 并提交配置，开发者与 CI 用同一套命令。

老仓库一次性开全量规则会产生海量无关 diff，正确路径是：先用 `ruff check --diff 看影响面`，把 legacy 目录放进 exclude 或 per-file-ignores，只对新代码和改动行逐步提高严格度，按目录把忽略清单清零；

用 tomllib 读配置、用 ast 判定 N802/E501，能证明「检查器读的是结构化配置、格式化不改 AST」。把命令写进 Makefile/justfile 与编辑器设置，评审里就只剩逻辑讨论。


## 增量检查器：按路径应用 per-file-ignores

老仓库接入规范时，最实用的中间层是一个「按路径决定严格度」的检查器：从 `pyproject.toml` 读出 select 与 per-file-ignores，对 legacy/ 下的文件跳过命名类规则、对新代码全查，用 ast 判定 N802 与 E501。这样既能在提交钩子中只查改动文件，又能把忽略清单逐步收敛。

下面片段用 tomllib 读配置、ast 检查两段源码，演示同一条规则在不同路径下得到不同结论，说明为什么「隔离旧代码、严查新代码」能避免海量无关改动。

```python
import ast, tomllib

CONFIG = tomllib.loads(chr(10).join([
    '[tool.ruff.lint]',
    'select = ["N", "E501"]',
    '[tool.ruff.lint.per-file-ignores]',
    '"legacy/*" = ["N"]',
]))

def check(path, source, limit=88):
    ignored = CONFIG['tool']['ruff']['lint']['per-file-ignores']
    skip_naming = any(path.startswith(k.rstrip('*')) for k in ignored)
    violations = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != node.name.lower() and not skip_naming:
            violations.append('N802:' + node.name)
    for i, line in enumerate(source.splitlines(), 1):
        if len(line) > limit:
            violations.append('E501:' + str(i))
    return violations

FILES = {
    'app/service.py': 'def fetch(x):' + chr(10) + '    return x' + chr(10),
    'legacy/old.py': 'def BadName(x):' + chr(10) + '    return x' + chr(10),
}
for name, src in FILES.items():
    print(name, check(name, src))
```

<Callout type="idea" title='落地提示' text='新代码严格、旧代码按修改行增量检查；把同一套命令固化进 CI 与编辑器配置' />


## 练习、自测与一页纸速记

<Exercise title='基础：用 ast 找出命名违规的函数' task='解析含 good_name 与 Bad 两个函数的源码，收集 FunctionDef 名字，打印全部名字与命中 N802 的名字。' solution='import ast\ntree = ast.parse(&#39;def good_name(x):&#39; + chr(10) + &#39;    return x&#39; + chr(10) + &#39;def Bad(x):&#39; + chr(10) + &#39;    return x&#39;)\nnames = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]\nprint(&#39;names&#39;, names)\nprint(&#39;N802&#39;, [n for n in names if n != n.lower()])' explain='N802 判定 FunctionDef.name 是否等于其全小写形式；这是 lint 在 AST 上做规则检查的最小例子，与格式化无关。' />

<Exercise title='进阶：读取格式化器配置' task='用 tomllib 解析 [tool.black] 的 line-length，打印出来，说明为何配置应由工具读取而非人工记忆。' solution='import tomllib\ncfg = tomllib.loads(&#39;[tool.black]&#39; + chr(10) + &#39;line-length = 88&#39; + chr(10))\nprint(&#39;black line length&#39;, cfg[&#39;tool&#39;][&#39;black&#39;][&#39;line-length&#39;])' explain='pyproject.toml 是结构化配置，tomllib（3.11+）可解析；把行宽写进配置后 black/ruff/CI 读同一份值，消除评审里的风格争论。' />

<Quiz no='073-1' q='关于格式化与 lint 的分工，正确的是？' :options='["格式化器改外观（空白/引号/换行），lint 查缺陷与规则，二者分开跑", "black 负责查未使用导入", "ruff check 负责重排引号", "两者必须合并成一次执行才不会冲突"]' answer="0" explain='black/ruff format 只重排空白与引号且不改 AST；ruff check 跑 F/E/N/I 等规则查问题。分开执行才能避免评审里混入无关格式改动。' />

<Quiz no='073-2' q='ruff 的 per-file-ignores 最适合解决什么？' :options='["老仓库按路径跳过部分规则，实现新代码严格、旧代码增量接入", "全局关闭所有规则", "提升格式化速度", "自动生成锁文件"]' answer="0" explain='per-file-ignores 按路径覆盖规则集（如 &#39;tests/*&#39; = [&#39;S101&#39;]），配合 pre-commit 只查暂存文件，可把 legacy 隔离出来逐步收敛。' />

<Quiz no='073-3' q='证据 ast.dump(ast.parse(&#39;x=1+2&#39;)) == ast.dump(ast.parse(&#39;x = 1 + 2&#39;)) 说明？' :options='["格式化只改空白不改语法树，故不改语义", "两种写法语义不同", "ast.dump 会忽略所有运算符", "ruff 会拒绝第二种写法"]' answer="0" explain='ast.dump 对两份仅空白不同的源码输出一致，证明格式化器在语法树等价的前提下重排外观；这也是把风格交给工具、评审只谈逻辑的依据。' />

<Predict no='073-P' q='用 ast 检查 def CalcTotal(a,b): 这个名字，N802 结果是？' :options='["True，命中命名违规", "False，名字合法", "抛 SyntaxError"]' answer='0' output='True，命中命名违规' explain='N802 要求函数名小写；CalcTotal 的全小写形式是 calctotal，两者不等，故判定违规。这是 lint 在 FunctionDef.name 上做的纯结构检查。' />

<FillBlank no='073-F' tpl='___ ast, tomllib' :answers='["import"]' hint='回想本讲关于 PEP 8 的取舍 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 格式化与 lint 分工，以及 PEP 8 的取舍 的落点。' />

<KnowledgeCard :points='["格式化器（black/ruff format）改外观不改 AST；lint（ruff check）查 F/E/N/I/UP/B/S 等规则", "PEP 8 建议 79 列，black/ruff 默认 line-length=88；全仓统一并写进 pyproject.toml", "ruff 规则码：F401 未用导入、F821 未定义名、E501 行过长、N802 函数名、I001 导入排序", "select/ignore/per-file-ignores 控制启用集合；精确抑制用 # noqa: E501，配 --warn-unused-ignores 治理", "isort 三组（标准库/第三方/本地）组内字典序，profile=&#39;black&#39; 与格式化器对齐", "pre-commit 提交时按暂存文件触发钩子；legacy 用 exclude/per-file-ignores 隔离，按改动行渐进接入"]' :pitfalls='["一次性对老仓库开全量规则并全量格式化", "在评审里争论 79 还是 88 列、单双引号", "满仓写 # noqa 或文件级 # ruff: noqa", "一次性对老仓库开全量规则，会产生上万行无关改动，掩盖真正的逻辑变更"]' summary='格式化工具负责「长什么样」，lint 负责「有没有问题」，二者分开才不会在评审里反复讨论空格' />

1. 格式化器（black/ruff format）改外观不改 AST；lint（ruff check）查 F/E/N/I/UP/B/S 等规则

2. PEP 8 建议 79 列，black/ruff 默认 line-length=88；全仓统一并写进 pyproject.toml

3. ruff 规则码：F401 未用导入、F821 未定义名、E501 行过长、N802 函数名、I001 导入排序

[下一讲：静态检查：mypy / pyright 与渐进式类型](/engineering/typecheck)
