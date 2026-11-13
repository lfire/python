---
title: 第 081 讲 · 阶段综合：把脚本重构成可发布包
description: 完整走一遍工程化闭环
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='60 分钟' goal='完整走一遍工程化闭环' prereq='第 080 讲 · 打包与发布：pyproject、wheel 与 PyPI' />

# 第 081 讲 · 阶段综合：把脚本重构成可发布包

前几讲把测试、日志、配置、打包补齐，上一讲讲完 pyproject 与 wheel。手上还留着只在自己机器跑得顺的单文件脚本：路径写死、依赖随缘，改完没人敢说结果没变。这一讲是工程化阶段的阶段综合，把规矩合进一次交付。

设想同事想复用这份脚本，你发去文件和依赖清单，对方却导入不进来——本地能跑，只是仓库根目录恰好在搜索路径里。我们从目录重构起步，接着依赖锁定、补上守住旧行为的测试，最后把 CI 与可回滚的发布连成一条链。需要包与模块、pytest、pyproject.toml；做完后别人一条命令就能装、能测、能用，也为让人调用它留好入口。


## 一份两千行的脚本，交给三个团队就翻车

运维交给你一个跑了两年、两千行的 `report.py`：读固定路径的 CSV、连内网数据库、把结果发到群里，配置全写死在顶层，末尾用 if `__name__` == '__main__' 拉起。

现在要交给三个团队复用，最朴素的做法是把文件复制过去再附一份 `requirements.txt`。

第一次交付就翻车：对方装完依赖后 import report 报 ModuleNotFoundError，因为单文件从未打成包，本地能跑靠的是仓库根目录恰好在 `sys.path` 里；有人机器上是 httpx 0.27、CI 解析到 0.28，接口行为变了；

重构把发消息的函数挪了位置，没有测试，谁也说不清金额统计是否和昨天一致；发版时才发现上一个版本号已经在 PyPI 上，覆盖不了，只能临时改版本号救火。这些不是四个独立故障，而是同一条工程化闭环缺了四段：可安装的目录结构、锁定的依赖、行为保持的测试、可重复且能回滚的发布。本讲按小步把四段补齐，并让每一步都有可运行的判据。

<Callout type="warn" title='先看一个真实会出错的写法' text='本机 pytest 全绿，别处 pip install 后 import 报 ModuleNotFoundError：flat layout 下测试从仓库根启动，sys.path[0] 恰好是源码所在目录，import 命中的是未安装的源码而非发行产物' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段七 · 工程化与质量 |
| 前置 | 第 080 讲 · 打包与发布：pyproject、wheel 与 PyPI |
| 难度 / 建议时长 | ★★★☆☆ · 60 分钟 |
| 本讲新增 | 目录重构、依赖锁定、类型与规范 |
| 一句话目标 | 完整走一遍工程化闭环 |
| 为下一讲铺垫 | HTTP 协议与 WSGI / ASGI |


## src layout 与 flat layout：能 import 到底是不是事实

单文件脚本重构的第一步是目录布局。flat layout 把包目录直接放在仓库根（`report.py` 与 tests/ 同级），pytest 从根目录启动时 `sys.path`[0] 就是仓库根，于是测试里 import report 总能成功——哪怕这个包根本没被安装。

src layout 把源码收进 src/pkgname/，根目录不再有可导入的包，必须先 pip install 才能 import，测试跑的正是安装后的产物，假通过当场暴露。

PEP 517 把构建拆成前端（pip、build）与后端（setuptools、hatchling、flit_core），由 `pyproject.toml` 的 `[build-system]` 声明 requires 与 build-backend；

setuptools 从 61 版起支持在 `pyproject.toml` 里写 `[project]` 元数据，不必再维护 `setup.py`。PEP 660 定义可编辑安装，pip install -e . 会把源码目录挂进解释器路径，改代码即时生效。

自动发现包时要把 tests、docs 排除，否则它们会被打进 wheel；用 python -I 隔离模式启动（忽略 PYTHONPATH 与当前目录）复验 import，才是可信的安装检查。带类型注解的库还要按 PEP 561 放一个 `py.typed` 标记文件，下游 mypy 才会读取。

**flat layout 与 src layout 对照**

| 维度 | flat layout（包在仓库根） | src layout（包在 src/ 下） |
| --- | --- | --- |
| 测试时 import 来源 | sys.path[0] 是仓库根，直接命中源码 | 根目录无包，必须安装后才可 import |
| 未安装能否跑通测试 | 能，容易假通过 | 不能，缺安装立刻报错 |
| 自动发现打包风险 | tests/、conftest.py 可能被误打进 wheel | 只从 src/ 发现，天然隔离 |
| 验证命令 | pytest 可能掩盖问题 | python -I -c 'import pkg' 隔离复验 |
| 可编辑安装 | pip install -e . 可做但不易察觉打包错误 | PEP 660 把 src 挂进路径，改码即生效 |

```python
import tomllib
import ast

PYPROJECT = chr(10).join([
    '[build-system]',
    "requires = ['setuptools>=68']",
    "build-backend = 'setuptools.build_meta'",
    '',
    '[project]',
    "name = 'shortly'",
    "version = '0.3.0'",
    "requires-python = '>=3.9'",
    "dependencies = ['click>=8', 'httpx']",
    '',
    '[project.scripts]',
    "shortly = 'shortly.cli:main'",
])
cfg = tomllib.loads(PYPROJECT)
print('backend', cfg['build-system']['build-backend'])
print('name', cfg['project']['name'], 'version', cfg['project']['version'])
print('deps', cfg['project']['dependencies'])
print('entry', cfg['project']['scripts']['shortly'])

LEGACY = chr(10).join([
    'import sys',
    'def shorten(url): return url[-6:]',
    "def expand(code): return 'https://x/' + code",
    "if __name__ == '__main__': print(shorten(sys.argv[1]))",
])
tree = ast.parse(LEGACY)
funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
print('legacy funcs', funcs)
print('guarded', any(isinstance(n, ast.If) for n in tree.body))
```

<OutputBox title='主示例运行结果' output='backend setuptools.build_meta\nname shortly version 0.3.0\ndeps [&#39;click&gt;=8&#39;, &#39;httpx&#39;]\nentry shortly.cli:main\nlegacy funcs [&#39;shorten&#39;, &#39;expand&#39;]\nguarded True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import tomllib\nimport ast\n\nPYPROJECT = chr(10).join([\n    &#39;[build-system]&#39;,\n    "requires = [&#39;setuptools&gt;=68&#39;]",\n    "build-backend = &#39;setuptools.build_meta&#39;",\n    &#39;&#39;,\n    &#39;[project]&#39;,\n    "name = &#39;shortly&#39;",\n    "version = &#39;0.3.0&#39;",\n    "requires-python = &#39;&gt;=3.9&#39;",\n    "dependencies = [&#39;click&gt;=8&#39;, &#39;httpx&#39;]",\n    &#39;&#39;,\n    &#39;[project.scripts]&#39;,\n    "shortly = &#39;shortly.cli:main&#39;",\n])\ncfg = tomllib.loads(PYPROJECT)\nprint(&#39;backend&#39;, cfg[&#39;build-system&#39;][&#39;build-backend&#39;])\nprint(&#39;name&#39;, cfg[&#39;project&#39;][&#39;name&#39;], &#39;version&#39;, cfg[&#39;project&#39;][&#39;version&#39;])\nprint(&#39;deps&#39;, cfg[&#39;project&#39;][&#39;dependencies&#39;])\nprint(&#39;entry&#39;, cfg[&#39;project&#39;][&#39;scripts&#39;][&#39;shortly&#39;])\n\nLEGACY = chr(10).join([\n    &#39;import sys&#39;,\n    &#39;def shorten(url): return url[-6:]&#39;,\n    "def expand(code): return &#39;https://x/&#39; + code",\n    "if __name__ == &#39;__main__&#39;: print(shorten(sys.argv[1]))",\n])\ntree = ast.parse(LEGACY)\nfuncs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]\nprint(&#39;legacy funcs&#39;, funcs)\nprint(&#39;guarded&#39;, any(isinstance(n, ast.If) for n in tree.body))' :notes='["导入 tomllib，3.11 起进入标准库的 TOML 解析器", "导入 ast，对重构前的源码做静态分析", "用 chr(10).join 构造 TOML 文本，源码里不出现反斜杠换行转义", "[build-system] 是 PEP 518 表，声明构建时依赖", "requires 指定 PEP 517 后端所需包及最低版本", "build-backend 指向可调用的构建后端入口", "空行分隔两个 TOML 表", "[project] 是 PEP 621 标准化的项目元数据表", "name 是发行名，pip 安装后由它索引", "version 遵循 PEP 440，发布后同版本不可覆盖", "requires-python 让 pip 拒绝不兼容的解释器", "dependencies 写兼容范围，精确值留给锁文件", "空行", "[project.scripts] 声明控制台入口点", "shortly 命令映射到 shortly.cli 模块的 main 函数", "join 结束，得到完整 TOML 字符串", "tomllib.loads 把 TOML 解析成嵌套 dict", "读出构建后端，确认是 setuptools.build_meta", "读出发行名与版本", "读出依赖列表，供锁文件生成", "读出入口点，安装后会生成可执行脚本", "用同样方式构造重构前的单文件脚本", "顶层 import，说明脚本依赖全局环境", "第一个业务函数，单文件里靠定义顺序组织", "第二个业务函数", "__main__ guard 让脚本既能直接运行又可被导入", "join 结束，得到脚本源码字符串", "ast.parse 把源码解析成 Module 节点树", "从顶层节点抽取函数定义名，作为迁移清单", "打印待迁移函数，重构时逐一搬进包模块", "检查顶层是否有 if 分支，即 __main__ guard 存在"]' title='第 081 讲 · 阶段综合：把脚本重构成可发布包' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='单文件脚本重构的第一步是目录布局。flat layout 把包目录直接放在仓库根（report.py 与 tests/ 同级），pytest 从根目录启动时 sys.path[0] 就是仓库根，于是测试里 import report 总能成功——哪怕这个包根本没被安装。src layout 把源码收' />

<ConceptDiagram type='flow4' title='第 081 讲 · src layout：让『能 import』成为被验证过的事实' labels='src layout：让『能 import』|依赖锁定与入口点：把『我这儿能跑』写成机器可|测试先行与 CI 矩阵：让重构可验证、发布可' caption='完整走一遍工程化闭环' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 依赖锁定、控制台入口点与发布产物

`[project]` 表是 PEP 621 标准化的元数据：name 是发行名（可与 import 包名不同，含连字符时 import 名用下划线），version 遵循 PEP 440（如 1.4.0、2.0rc1、1.0.dev3），发布到 PyPI 后同名同版本不可覆盖；

requires-python = '>=3.9' 让 pip 在不兼容解释器上直接拒绝安装；dependencies 写兼容范围，锁文件里才 pin 精确值。

范围与锁定是两件事：pip-compile 或 uv pip compile 读 pyproject 解析出 `requirements.lock`，带 --generate-hashes 后每条都附摘要，CI 用 pip install -c `constraints.txt` 或 `pip install --require-hashes 复现同一依赖集合`，杜绝解析漂移。

开发依赖放 `[project.optional-dependencies]` 的 dev 组，避免测试框架进生产镜像。

`[project.scripts]` 声明控制台入口点，形如 shortly = 'shortly.cli:main'，pip 安装 wheel 时会在 bin 目录生成一个调用该函数的可执行脚本，这是把脚本变成命令的关键。

产物分两种：wheel（PEP 427）是已构建的 zip，安装只解压写 .dist-info，不执行构建代码；sdist 是源码包，安装时要现场跑后端。python -m build 会同时产出两者，twine check 校验 METADATA 的 long_description 与 content-type 是否合法。

**pyproject.toml 关键表与字段**

| 表 / 字段 | 作用 | 常见取值或约束 |
| --- | --- | --- |
| [build-system] requires | PEP 518 构建依赖 | setuptools>=68、hatchling、flit_core>=3.2 |
| [build-system] build-backend | PEP 517 后端入口 | setuptools.build_meta |
| [project] version | PEP 440 版本，发布后不可覆盖 | 1.4.0、2.0rc1、1.0.dev3 |
| [project] requires-python | 解释器版本门槛 | >=3.9；pip 会据此拒绝安装 |
| [project.scripts] | 控制台入口点 | cmd = 'pkg.mod:func' |
| [project.optional-dependencies] | 可选依赖组 | dev = ['pytest>=8', 'ruff'] |

**发布产物与命令**

| 命令 / 产物 | 行为 | 用途 |
| --- | --- | --- |
| python -m build | 隔离环境里同时产出 sdist 与 wheel | 发布前构建 |
| wheel (.whl) | PEP 427 已构建 zip，安装只解压 | 首选上传产物 |
| sdist (.tar.gz) | 源码包，安装时现场跑后端 | 兜底与审计 |
| twine check dist/* | 校验 METADATA 渲染合法性 | 上传前检查 |
| twine upload dist/* | 上传到索引，同名同版本拒绝重传 | 发布 |
| yank (PEP 592) | 阻止新解析命中该版本，不删文件 | 问题版本降级 |


## 对照：只写包名与带摘要锁文件的解析漂移

```python
import tomllib

CFG = chr(10).join([
    '[project]',
    "name = 'shortly'",
    "version = '1.4.0'",
    "requires-python = '>=3.9'",
    "dependencies = ['click>=8', 'httpx==0.27.2']",
    '[project.optional-dependencies]',
    "dev = ['pytest>=8', 'ruff']",
])
p = tomllib.loads(CFG)['project']
print('pinned', [d for d in p['dependencies'] if '==' in d])
print('dev tools', p['optional-dependencies']['dev'])
print('python floor', p['requires-python'])
```

<OutputBox title='对照写法：先自己猜，再点开' output='pinned [&#39;httpx==0.27.2&#39;]\ndev tools [&#39;pytest&gt;=8&#39;, &#39;ruff&#39;]\npython floor &gt;=3.9' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import tomllib\nimport ast\n\nPYPROJECT = chr(10).join([\n    &#39;[build-system]&#39;,\n    \"requires = [&#39;setuptools&gt;=68&#39;]\",\n    \"build-backend = &#39;setuptools.build_meta&#39;\",\n    &#39;&#39;,\n    &#39;[project]&#39;,\n    \"name = &#39;shortly&#39;\",\n    \"version = &#39;0.3.0&#39;\",\n    \"requires-python = &#39;&gt;=3.9&#39;\",\n    \"dependencies = [&#39;click&gt;=8&#39;, &#39;httpx&#39;]\",\n    &#39;&#39;,\n    &#39;[project.scripts]&#39;,\n    \"shortly = &#39;shortly.cli:main&#39;\",\n])\ncfg = tomllib.loads(PYPROJECT)\nprint(&#39;backend&#39;, cfg[&#39;build-system&#39;][&#39;build-backend&#39;])\nprint(&#39;name&#39;, cfg[&#39;project&#39;][&#39;name&#39;], &#39;version&#39;, cfg[&#39;project&#39;][&#39;version&#39;])\nprint(&#39;deps&#39;, cfg[&#39;project&#39;][&#39;dependencies&#39;])\nprint(&#39;entry&#39;, cfg[&#39;project&#39;][&#39;scripts&#39;][&#39;shortly&#39;])\n\nLEGACY = chr(10).join([\n    &#39;import sys&#39;,\n    &#39;def shorten(url): return url[-6:]&#39;,\n    \"def expand(code): return &#39;https://x/&#39; + code\",\n    \"if __name__ == &#39;__main__&#39;: print(shorten(sys.argv[1]))\",\n])\ntree = ast.parse(LEGACY)\nfuncs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]\nprint(&#39;legacy funcs&#39;, funcs)\nprint(&#39;guarded&#39;, any(isinstance(n, ast.If) for n in tree.body))", "note": "src layout：让『能 import』成为被验证过的事实"}, {"label": "对照 / 进阶", "code": "import tomllib\n\nCFG = chr(10).join([\n    &#39;[project]&#39;,\n    \"name = &#39;shortly&#39;\",\n    \"version = &#39;1.4.0&#39;\",\n    \"requires-python = &#39;&gt;=3.9&#39;\",\n    \"dependencies = [&#39;click&gt;=8&#39;, &#39;httpx==0.27.2&#39;]\",\n    &#39;[project.optional-dependencies]&#39;,\n    \"dev = [&#39;pytest&gt;=8&#39;, &#39;ruff&#39;]\",\n])\np = tomllib.loads(CFG)[&#39;project&#39;]\nprint(&#39;pinned&#39;, [d for d in p[&#39;dependencies&#39;] if &#39;==&#39; in d])\nprint(&#39;dev tools&#39;, p[&#39;optional-dependencies&#39;][&#39;dev&#39;])\nprint(&#39;python floor&#39;, p[&#39;requires-python&#39;])", "note": "依赖锁定与入口点：把『我这儿能跑』写成机器可校验的约束"}]' title='两种写法切换看' />

```python
import ast

SRC = chr(10).join([
    'from .core import shorten',
    'def main():',
    '    print(shorten("https://example.com"))',
    "if __name__ == '__main__':",
    '    main()',
])
tree = ast.parse(SRC)
rel = [n.level for n in ast.walk(tree)
       if isinstance(n, ast.ImportFrom) and n.level > 0]
guard = [n for n in tree.body if isinstance(n, ast.If)]
print('relative import levels', rel)
print('top-level if count', len(guard))
print('functions', [n.name for n in tree.body if isinstance(n, ast.FunctionDef)])
```

<OutputBox title='原理验证' output='relative import levels [1]\ntop-level if count 1\nfunctions [&#39;main&#39;]' />


## 测试先行、CI 矩阵与可回滚发布

顺序决定成败：先补 characterization test（特征测试），锁住当前可观察行为，哪怕其中藏着旧 bug 也照实记录，再动结构；这样每次小步重构后跑一遍，就能证明行为保持，而不是把重构做成重写。pytest 靠 rootdir 与 `conftest.py` 组织夹具，把被测包以可编辑安装方式装进同一环境；

覆盖率用 `coverage.py` 或 pytest-cov 量化，但覆盖率是发现盲区的工具，不是行为正确的证明。

CI 矩阵用 tox、nox 或 GitHub Actions 的 matrix 覆盖 Python 3.9 到 3.13 与 Linux/macOS/Windows，每格都从锁文件安装后跑同一组命令，本地能过线上才能过。

发布流水线把 git tag、版本号、构建、上传串起来：版本只能有一个来源，用 `importlib.metadata.version`('shortly') 从 .dist-info 读，而不是在源码里再写一份 `__version__`；

上传用 twine upload dist/*，仓库凭据走 OIDC 或 token 而不落盘。回滚不是覆盖：PyPI 拒绝同名同版本重传，紧急修复要发新版本；对已发布但有问题的版本可用 yank（PEP 592）阻止新解析命中，已 pin 的依赖仍能装。

回滚路径是让下游 pin 回上一版本号，并在流水线里保留上一版产物与回滚脚本，发布后跑一次 python -I -c 'import pkg; print(pkg.__file__)' 冒烟。

<FlowTimeline :steps='[{"title": "src layout：让『能 import』成为被验证过的事实", "desc": "单文件脚本重构的第一步是目录布局。flat layout 把包目录直接放在仓库根（r…", "tone": "blue"}, {"title": "依赖锁定与入口点：把『我这儿能跑』写成机器可校验的约束", "desc": "[project] 表是 PEP 621 标准化的元数据：name 是发行名（可与 …", "tone": "purple"}, {"title": "测试先行与 CI 矩阵：让重构可验证、发布可回滚", "desc": "顺序决定成败：先补 characterization test（特征测试），锁住当前…", "tone": "orange"}, {"title": "工程落地", "desc": "发布前门禁：把目录、元数据、导入写法做成可跑的检查", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## PEP 517 前后端解耦与 wheel 为何可复现

PEP 517 把『怎么构建』与『谁来驱动构建』解耦：pip 或 build 作为前端，先创建隔离虚拟环境、装入 `[build-system]`.requires 声明的后端，再调用后端约定的 build_wheel / build_sdist 钩子。

wheel 本质是 zip，内含包代码与一份 .dist-info（METADATA、RECORD、`entry_points.txt`、WHEEL），pip 安装 wheel 时只做解压、按 entry_points 生成脚本、写 RECORD 清单，不执行任何项目构建代码，因此安装快且可复现；

sdist 则要求目标机器具备编译器与后端，失败率更高。pip 解析依赖时读 METADATA 的 Requires-Dist，按 requires-python 与版本范围挑候选，这一步每次运行都可能得到不同结果，正是锁文件要消掉的不确定性。

`importlib.metadata` 从已安装的 .dist-info 读版本与入口点，与源码里的 `__version__` 没有关联，所以版本必须收敛到单一来源。

可编辑安装（PEP 660）由后端写一个 .pth 或自定义 MetaPathFinder，把 src 目录挂进 `sys.path`，让改动无需重装即可见，这也是 src layout 下本地开发的常规姿势。

<Term word='目录重构' text='单文件脚本重构的第一步是目录布局。flat layout 把包目录直接放在仓库根（report.py 与 tests/ 同级），pytest 从根目录启动时 sys.path[0] 就是仓库根，于是测试里 import report 总能成功——哪怕这个包根本没被安装。src layout 把源码收进 src/pkgn' />

<Term word='依赖锁定' text='[project] 表是 PEP 621 标准化的元数据：name 是发行名（可与 import 包名不同，含连字符时 import 名用下划线），version 遵循 PEP 440（如 1.4.0、2.0rc1、1.0.dev3），发布到 PyPI 后同名同版本不可覆盖；requires-python = &#39;&gt;=3' />


## 发布前门禁：把目录、元数据、导入写成可跑的检查

一个团队把脚本拆成包后，最容易在发布当天才发现打错了目录或漏了字段。

把发布前的判据写成一个不依赖第三方库的检查器，随代码提交、在 CI 里执行：先确认仓库里存在 src/shortly/`__init__.py` 与 `pyproject.toml`（src layout 的最低证据），再用 tomllib 解析元数据，检查 name、version、requires-python、dependencies 四个必需字段是否齐全，顺便确认依赖里确实有精确 pin；

接着用 ast 检查包内模块是否用相对导入（from .core import ...）而不是硬编码顶层包名，并确认 `__main__` guard 仍保留。这段检查把『工程化做没做对』从口头约定变成布尔结果，任何一项为假就卡住发布。

真实项目再接 wheel 内容扫描与 twine check，但骨架就是这个：每一项失败都必须能指向具体文件与具体字段。

```python
import tomllib
import ast

TREE = {
    'src/shortly/__init__.py': '',
    'src/shortly/core.py': 'def shorten(u): return u[-6:]',
    'src/shortly/cli.py': 'from .core import shorten',
    'pyproject.toml': '',
    'tests/test_core.py': '',
}

def has_src_layout(tree):
    return 'src/shortly/__init__.py' in tree and 'pyproject.toml' in tree

def parse_project(text):
    p = tomllib.loads(text)['project']
    required = ('name', 'version', 'requires-python', 'dependencies')
    missing = [k for k in required if k not in p]
    return missing, p.get('version'), len(p.get('dependencies', []))

def uses_relative_import(src):
    tree = ast.parse(src)
    return any(isinstance(n, ast.ImportFrom) and n.level > 0 for n in ast.walk(tree))

def has_main_guard(src):
    return any(isinstance(n, ast.If) for n in ast.parse(src).body)

PYPROJECT = chr(10).join([
    '[project]',
    "name = 'shortly'", "version = '1.4.0'",
    "requires-python = '>=3.9'",
    "dependencies = ['click>=8', 'httpx==0.27.2']",
])
CLI = chr(10).join([
    'from .core import shorten',
    'def main():',
    '    print(shorten("https://example.com"))',
    "if __name__ == '__main__':",
    '    main()',
])
print('src layout', has_src_layout(TREE))
print('meta', parse_project(PYPROJECT))
print('relative import', uses_relative_import(CLI))
print('main guard', has_main_guard(CLI))
```

<Callout type="idea" title='落地提示' text='按小步推进：行为保持的测试先行，再动结构，最后接 CI 与发布；保留回滚路径' />

<CheckList id='P081b' title='上线前自检' :items='["能复现并解释「本机 pytest 全绿，别处 pip install 后 」", "能复现并解释「依赖只写 requirements.txt 里的包名，CI 」", "能复现并解释「线上出了 bug 想用同一版本号重新上传修复包」", "能用一条命令验证 目录重构", "关键路径有自动化测试与失败分支"]' />

```bash
python -m compileall -q . && python -m pytest -q
```

把输入换成你自己的数据，观察结果是否仍符合 **目录重构** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 本机 pytest 全绿，别处 pip install 后 import 报 ModuleNotFoundError | flat layout 下测试从仓库根启动，sys.path[0] 恰好是源码所在目录，import 命中的是未安装的源码而非发行产物 | 改 src layout，把源码收进 src/pkgname/；CI 里先 pip install -e .，再用 python -I -c 'import pkg; print(pkg.__file__)' 验证安装路径 |
| 依赖只写 requirements.txt 里的包名，CI 与本地行为不一致 | pip 每次按版本范围解析最新兼容版，httpx、pydantic 这类库的小版本也会改变行为 | 用 uv pip compile 或 pip-compile --generate-hashes 生成带摘要的锁文件，CI 用 pip install --require-hashes -r requirements.lock 固定集合 |
| 线上出了 bug 想用同一版本号重新上传修复包 | PyPI 拒绝同名同版本重复上传，版本号只增不退 | 发递增的新版本修复；对问题版本执行 yank 阻止新解析命中，回滚时让下游 pin 回上一个可用版本号 |

<Callout type="warn" title='本讲最容易踩的坑' text='本机 pytest 全绿，别处 pip install 后 import 报 ModuleNotFoundError：flat layout 下测试从仓库根启动，sys.path[0] 恰好是源码所在目录，import 命中的是未安装的源码而非发行产物' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：本机 pytest 全绿，别处 pip in", "body": "flat layout 下测试从仓库根启动，sys.path[0] 恰好是源码所在目录，import 命中的是未安装的源码而非发行产物", "tip": "改 src layout，把源码收进 src/pkgname/；CI 里先 pip install -e .，再用 python -I -c &#39;import pkg; print(pkg.__file__)&#39; 验证安装路径"}, {"title": "第 2 步：依赖只写 requirements.txt ", "body": "pip 每次按版本范围解析最新兼容版，httpx、pydantic 这类库的小版本也会改变行为", "tip": "用 uv pip compile 或 pip-compile --generate-hashes 生成带摘要的锁文件，CI 用 pip install --require-hashes -r requirements.lock 固定集合"}, {"title": "第 3 步：线上出了 bug 想用同一版本号重新上传修复", "body": "PyPI 拒绝同名同版本重复上传，版本号只增不退", "tip": "发递增的新版本修复；对问题版本执行 yank 阻止新解析命中，回滚时让下游 pin 回上一个可用版本号"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：解析一份真实的项目元数据' task='写一段代码，用 tomllib.loads 解析含 [build-system]、[project]、[project.scripts] 的 TOML 字符串，打印 build-backend、version、入口点，并判断 requires-python 是否为 &gt;=3.9。' solution='import tomllib\n\nSRC = chr(10).join([\n    &#39;[build-system]&#39;,\n    "requires = [&#39;setuptools&gt;=68&#39;]",\n    "build-backend = &#39;setuptools.build_meta&#39;",\n    &#39;[project]&#39;,\n    "name = &#39;demo&#39;", "version = &#39;0.1.0&#39;",\n    "requires-python = &#39;&gt;=3.9&#39;", "dependencies = []",\n    &#39;[project.scripts]&#39;, "demo = &#39;demo.cli:main&#39;",\n])\ncfg = tomllib.loads(SRC)\nprint(cfg[&#39;build-system&#39;][&#39;build-backend&#39;])\nprint(cfg[&#39;project&#39;][&#39;version&#39;])\nprint(cfg[&#39;project&#39;][&#39;scripts&#39;][&#39;demo&#39;])\nprint(cfg[&#39;project&#39;][&#39;requires-python&#39;] == &#39;&gt;=3.9&#39;)' explain='tomllib 把 TOML 表映射成嵌套 dict；[project.scripts] 的键是命令名、值是 模块:函数。requires-python 是字符串，需按 PEP 440 规则另行比较，不能直接用 Python 版本号比较。' />

<Exercise title='进阶：用 ast 生成重构迁移清单' task='给定一个单文件脚本源码，用 ast 找出所有顶层函数、顶层 import 与 __main__ guard，输出一份『哪些函数搬进 core.py、哪些依赖写进 pyproject、guard 是否保留』的清单。' solution='import ast\n\nSRC = chr(10).join([\n    &#39;import httpx&#39;,\n    &#39;def load(p): return open(p).read()&#39;,\n    &#39;def send(x): return httpx.post("http://x", data=x)&#39;,\n    "if __name__ == &#39;__main__&#39;:", &#39;    print(send(load("a")))&#39;,\n])\nt = ast.parse(SRC)\nfuncs = [n.name for n in t.body if isinstance(n, ast.FunctionDef)]\nimports = [a.name for n in t.body if isinstance(n, ast.Import) for a in n.names]\nguards = [n for n in t.body if isinstance(n, ast.If)]\nprint(&#39;to core.py&#39;, funcs)\nprint(&#39;to pyproject deps&#39;, imports)\nprint(&#39;keep guard&#39;, bool(guards))' explain='顶层 FunctionDef 是领域逻辑，迁进包模块；顶层 import 里的第三方名要写进 [project].dependencies；if 分支通常就是 __main__ guard，重构后应保留在 cli.py 里，保证模块导入时无副作用。' />

<Quiz no='081-1' q='src layout 最主要的工程价值是什么？' :options='["测试只能 import 到安装后的包，避免仓库根恰好在 sys.path 造成的假通过", "让源码文件数量更少", "让 pip 安装速度翻倍", "允许不写 pyproject.toml"]' answer="0" explain='flat layout 下 pytest 从根目录启动，sys.path[0] 命中未安装源码；src layout 把包收进 src/，根目录无可导入包，必须先安装，测试对象与交付对象一致。' />

<Quiz no='081-2' q='关于 wheel 与 sdist，下面哪项准确？' :options='["wheel 是已构建产物，安装只解压不跑构建代码；sdist 要现场构建", "sdist 是二进制产物，wheel 是源码", "两者都要在目标机执行 setup.py", "wheel 不能包含 .dist-info"]' answer="0" explain='PEP 427 的 wheel 是带 .dist-info 的 zip，安装即解压并写 RECORD；sdist 是源码包，安装时需调用 PEP 517 后端现场构建，依赖编译工具链，失败率更高。' />

<Quiz no='081-3' q='线上 1.4.0 有 bug，正确的处理顺序是？' :options='["发 1.4.1 修复，必要时 yank 1.4.0，并让下游 pin 回上一可用版本", "重新上传一份同名同版本的 1.4.0 覆盖", "直接删掉 PyPI 上的 1.4.0 文件", "把版本号改回 1.3.9 重新发布"]' answer="0" explain='PyPI 拒绝同名同版本重传，版本号只增不退；yank（PEP 592）只阻止新解析命中、不删文件也不影响已 pin 的依赖，回滚靠下游 pin 到上一可用版本。' />

<Predict no='081-P' q='对一段含 from .core import shorten 的模块取 ast.walk，筛 ImportFrom 且 level &gt; 0，最可能得到什么？' :options='["[1]，表示一层相对导入", "[0]，表示绝对导入", "空列表，因为 ast 不解析相对导入"]' answer='0' output='relative import levels [1]' explain='from .core import ... 的 ImportFrom 节点 level 为 1（每多一个点加 1），module 为 &#39;core&#39;；level 为 0 才是绝对导入。用 ast 检查 level 能机器化地守住包内必须用相对导入的约定。' />

<FillBlank no='081-F' tpl='___ tomllib' :answers='["import"]' hint='回想本讲关于 目录重构 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 src layout：让『能 import』成为被验证过的事实 的落点。' />

<KnowledgeCard :points='["src layout 把包收进 src/，让测试只能 import 到已安装产物；用 python -I 隔离复验", "PEP 517 由 pyproject.toml 的 [build-system] 声明后端；PEP 660 可编辑安装把源码挂进 sys.path", "[project] 的 version 遵循 PEP 440 且发布后不可覆盖；requires-python 让 pip 拒绝不兼容解释器", "范围写在 dependencies、精确值锁在 lock 文件；CI 用 --require-hashes 复现同一依赖集合", "wheel 是已构建 zip（安装只解压），sdist 现场构建；python -m build 同产两者，twine check 校验元数据", "重构先补特征测试锁行为；回滚靠发新版本 + pin 上一版，yank 只阻止新解析命中"]' :pitfalls='["本机 pytest 全绿，别处 pip install 后 import 报 ModuleNotFoundError", "依赖只写 requirements.txt 里的包名，CI 与本地行为不一致", "线上出了 bug 想用同一版本号重新上传修复包", "先重构完再补测试，改动面太大时无法判断行为是否保持，重构很容易变成重写"]' summary='工程化的价值在交付那一刻体现：一条命令构建、一条命令测试、一条命令发布，且每一步可重复' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| src layout 把包收进 src/，让测试只能 import 到已安装产物；用 python -I 隔离复验 | 建立直觉 |
| PEP 517 由 pyproject.toml 的 [build-system] 声明后端；PEP 660 可编辑安装把源码挂进 sys.path | 跑通示例 |
| [project] 的 version 遵循 PEP 440 且发布后不可覆盖；requires-python 让 pip 拒绝不兼容解释器 | 深入边界 |
| 范围写在 dependencies、精确值锁在 lock 文件；CI 用 --require-hashes 复现同一依赖集合 | 工程落地 |
| wheel 是已构建 zip（安装只解压），sdist 现场构建；python -m build 同产两者，twine check 校验元数据 | 随堂检测 |
| 重构先补特征测试锁行为；回滚靠发新版本 + pin 上一版，yank 只阻止新解析命中 | 复盘 |

1. src layout 把包收进 src/，让测试只能 import 到已安装产物；用 python -I 隔离复验

2. PEP 517 由 pyproject.toml 的 [build-system] 声明后端；PEP 660 可编辑安装把源码挂进 sys.path

3. [project] 的 version 遵循 PEP 440 且发布后不可覆盖；requires-python 让 pip 拒绝不兼容解释器

[下一讲：HTTP 协议与 WSGI / ASGI](/server/http-wsgi)
