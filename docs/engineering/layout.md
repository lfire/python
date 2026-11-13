---
title: 第 071 讲 · 项目结构与 src 布局
description: 设计一个不会引发导入歧义的仓库
---

<StageHeader stage='L7 · 工程化' level='★★☆☆☆' time='30 分钟' goal='设计一个不会引发导入歧义的仓库' prereq='第 070 讲 · 阶段综合：并发爬虫四级演进' />

# 第 071 讲 · 项目结构与 src 布局

并发那套能跑通了，可代码还摊在一个脚本里。从这里起节奏换一换：先把程序写对，再让它站得住、可维护。第一件事是给这些文件一个不会引起导入歧义的家。本地跑测试全绿，推到流水线装完再跑却找不到那个包，反复改路径都没根治，这种落差往往出在仓库怎么摆。

先对照扁平布局与 src 布局，看清导入解析为何偏向前者，再谈包与模块命名、按领域分层，接着把公开 API 收敛到 `__init__`，最后把配置与密钥隔到代码之外。带着模块、包、import 与函数的基础来；读完能设计一个「本地能跑、发布也不坏」的仓库结构，也知道测试该放在哪一侧。


## 本地 pytest 全绿，pip install . 之后却报 ModuleNotFoundError

一个包在本地 pytest 全绿，推到 CI 里安装成包之后再跑，却报 ModuleNotFoundError: No module named 'mypkg.core'。团队反复改 `sys.path` 都没根治。

真正原因是扁平布局：项目根里有 mypkg/ 目录，而 pytest 从项目根启动时会把根目录放进 `sys.path[0]`，测试里 `import mypkg` 直接命中源码目录，打包缺文件、`__init__` 里漏导出这类问题全被掩盖；一旦装到 site-packages 才暴露。

另一个隐藏坑是包内写 `import sibling`（隐式相对导入），Python 3 起默认绝对导入，这行会去顶层找 sibling 而报 No module named 'sibling'。src 布局逼你只能用安装后的包来测试，把这些「本地能跑、发布就坏」的问题提前引爆。

本讲把导入解析、包与命名空间包、公开 API 收敛讲到能设计仓库结构。

<Callout type="warn" title='先看一个真实会出错的写法' text='包内写 import a 想引用同包模块：Python 3 默认绝对导入，会去 sys.path 顶层找 a，报 ModuleNotFoundError: No module named &#39;a&#39;' />


## src 布局 vs 扁平布局：sys.path 决定命中谁

扁平布局把包目录直接放项目根：`project/mypkg/__init__.py`。

从项目根运行 pytest 或 `python -m` 时，根目录进入 `sys.path`，`import mypkg` 命中本地源码，哪怕 `pyproject.toml` 里 package-dir 配错、漏打了子模块，测试也照样通过。

src 布局是 `project/src/mypkg/__init__.py`，项目根不在包搜索路径上，只有先做一次可编辑安装、或把 src 加进 `sys.path`，才能 `import mypkg`——等价地说，测试跑的是「安装产物」。

配置上在 `pyproject.toml` 写 `[tool.setuptools]` 下的 `package-dir`，把根映射到 src 目录（或填 build 后端相应的字段），`README`、测试、配置放根，密钥一律走环境变量不进仓库。

PEP 420（3.3 起）还允许没有 `__init__.py` 的命名空间包：这种包 `__file__` 为 None、`__spec__.origin` 为 None，可把同名包拆分到多个分发里，但普通项目应显式写 `__init__.py` 以明确边界。

**src 布局与扁平布局对照**

| 维度 | 扁平布局 project/mypkg/ | src 布局 project/src/mypkg/ |
| --- | --- | --- |
| 根目录在 sys.path | pytest 从根跑即命中本地源码 | 默认不在，须安装或加 src |
| 测试对象 | 可能是未打包的源码 | 安装后的产物，提前暴露打包错误 |
| pyproject 配置 | package-dir 易漏配也能过测 | 须显式 package-dir = &#123;'' = 'src'&#125; |
| 泄漏内部文件 | tests/ 易被打进 wheel | tests/ 在包外，天然隔离 |
| 干净环境可重现 | 弱，依赖工作目录 | 强，pip install . 后任意目录可 import |

<Callout type="tip" title='核心心智模型' text='扁平布局把包目录直接放项目根：`project/mypkg/__init__.py`。从项目根运行 pytest 或 `python -m` 时，根目录进入 `sys.path`，`import mypkg` 命中本地源码，哪怕 `pyproject.toml` 里 package-dir 配错、漏' />

<ConceptDiagram type='flow4' title='第 071 讲 · src 布局 vs 扁平布局：sys.path 决定命中谁' labels='src 布局 vs 扁平布局：sys.pat|包内导入规则：显式相对、__init__ 与|配置隔离、文档入口与单仓多包' caption='设计一个不会引发导入歧义的仓库' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 包内导入规则：显式相对、__init__ 与 __all__

Python 3 默认绝对导入（PEP 328），包内 `import a` 会去 `sys.path` 顶层找 a，而不是同包的 `a.py`；

命中不到就报 ModuleNotFoundError: No module named 'a'，想引用同包模块必须写 `from . import a` 或 `from .core import add`。

`__init__.py` 有三个作用：把目录标记为包、执行包级初始化、收敛公开 API；

在 `__init__.py` 里 `from .core import add` 再用 `__all__ = ['add']` 声明，`from mypkg import *` 就只导出 add，而不会把内部实现名泄漏出去。

命名遵循 PEP 8：模块与包用小写加下划线，避免与标准库同名（`json.py`、`test` 会遮蔽），类名用 CapWords，不要含连字符——带连字符的目录无法被 import。

内部模块按领域分层（如 domain/、io/、api/）而不是按技术堆一层，公开 API 只在 `__init__.py` 暴露，调用方不该依赖内部路径。

**包导入规则与命名**

| 规则 / 名称 | 含义 | 误用后果 |
| --- | --- | --- |
| PEP 328 绝对导入 | import a 去 sys.path 顶层找 | 包内隐式相对报 No module named 'a' |
| from .core import add | 显式相对导入同包模块 | 写错会 ImportError: attempted relative import |
| __init__.py | 标记包、初始化、收敛 API | 缺失时变 PEP 420 命名空间包 |
| __all__ = ['add'] | 控制 from pkg import * 的导出 | 不写会泄漏内部实现名 |
| PEP 420 命名空间包 | __file__ 与 __spec__.origin 均为 None | 同名包跨分发合并，边界模糊 |
| 小写下划线命名 | 模块名可被 import | 含连字符或撞标准库名 json.py 会遮蔽 |

import 解析由 `sys.meta_path` 上的 finder 按固定顺序完成：`BuiltinImporter`、`FrozenImporter`、`PathFinder`。

`PathFinder` 遍历 `sys.path` 的每个条目，用 `FileFinder` 在该目录下查 `<name>/__init__.py` 或 `<name>.py`，命中后构造 `ModuleSpec`（含 origin、submodule_search_locations）交给 loader 执行。

`sys.path[0]` 通常是脚本所在目录或当前工作目录，这正是扁平布局「从项目根跑就命中本地包」的根因；命中结果缓存在 `sys.modules`，第二次 import 不再查找。

所以想让改动生效，得删掉 `sys.modules[name]` 再重新导入（或用 `importlib.reload`）；

若是新增了文件却找不到，那是 finder 的目录缓存没刷新，用 `importlib.invalidate_caches()` 让新文件可见——两者管的不是同一层缓存。

PEP 420 的命名空间包没有 `__init__.py`，`FileFinder` 返回 origin 为 None、submodule_search_locations 为 `_NamespacePath` 的 spec，允许多个分发往同一个包名贡献子模块。

src 布局通过「项目根不在 `sys.path`」把这条解析链强制导向安装产物。

<Term word='src 与扁平布局对比' text='扁平布局把包目录直接放项目根：`project/mypkg/__init__.py`。从项目根运行 pytest 或 `python -m` 时，根目录进入 `sys.path`，`import mypkg` 命中本地源码，哪怕 `pyproject.toml` 里 package-dir 配错、漏打了子模块，测试也照' />

<Term word='包与模块命名' text='Python 3 默认绝对导入（PEP 328），包内 `import a` 会去 `sys.path` 顶层找 a，而不是同包的 `a.py`；命中不到就报 ModuleNotFoundError: No module named &#39;a&#39;，想引用同包模块必须写 `from . import a` 或 `from .c' />


## 对照：从项目根跑测试与装进 site-packages 跑测试

```python
import sys, os, tempfile

with tempfile.TemporaryDirectory() as root:
    flat_pkg = os.path.join(root, 'myapp')
    src_pkg = os.path.join(root, 'src', 'myapp')
    os.makedirs(flat_pkg)
    os.makedirs(src_pkg)
    for p in (flat_pkg, src_pkg):
        with open(os.path.join(p, '__init__.py'), 'w') as f:
            f.write('ORIGIN = ' + repr(os.path.dirname(p)) + chr(10))
    sys.path.insert(0, root)
    import myapp
    print('flat layout resolves to root', myapp.ORIGIN == root)
    del sys.modules['myapp']
    sys.path.remove(root)
    sys.path.insert(0, os.path.join(root, 'src'))
    import myapp
    print('src layout resolves to src', myapp.ORIGIN == os.path.join(root, 'src'))
    del sys.modules['myapp']
    sys.path.remove(os.path.join(root, 'src'))
```

<OutputBox title='主示例运行结果' output='flat layout resolves to root True\nsrc layout resolves to src True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys, os, tempfile\n\nwith tempfile.TemporaryDirectory() as root:\n    flat_pkg = os.path.join(root, &#39;myapp&#39;)\n    src_pkg = os.path.join(root, &#39;src&#39;, &#39;myapp&#39;)\n    os.makedirs(flat_pkg)\n    os.makedirs(src_pkg)\n    for p in (flat_pkg, src_pkg):\n        with open(os.path.join(p, &#39;__init__.py&#39;), &#39;w&#39;) as f:\n            f.write(&#39;ORIGIN = &#39; + repr(os.path.dirname(p)) + chr(10))\n    sys.path.insert(0, root)\n    import myapp\n    print(&#39;flat layout resolves to root&#39;, myapp.ORIGIN == root)\n    del sys.modules[&#39;myapp&#39;]\n    sys.path.remove(root)\n    sys.path.insert(0, os.path.join(root, &#39;src&#39;))\n    import myapp\n    print(&#39;src layout resolves to src&#39;, myapp.ORIGIN == os.path.join(root, &#39;src&#39;))\n    del sys.modules[&#39;myapp&#39;]\n    sys.path.remove(os.path.join(root, &#39;src&#39;))' :notes='["导入 sys 操作模块路径与缓存，os/tempfile 建临时目录", "临时根目录下建两种布局做对照", "扁平布局：包目录直接位于项目根", "src 布局：包目录位于 src/ 之下", "创建扁平包目录", "创建 src 包目录", "给两个包写同一个标记变量，记录父目录", "__init__.py 里 ORIGIN 保存当前包的父路径", "把项目根加入 sys.path，模拟从根目录跑 pytest", "import myapp 会命中根目录里的扁平包", "ORIGIN 等于 root，证明命中本地源码而非安装产物", "删掉 sys.modules 缓存以便重新解析", "移除项目根，清掉扁平布局的搜索路径", "把 src 加入 sys.path，等价于 pip install -e .", "再次 import myapp，这次命中 src 下的包", "ORIGIN 等于 src，证明只有 src 在路径上才命中", "清理模块缓存，保持环境干净", "移除 src 路径，退出临时环境", "src 布局让项目根不在 sys.path，测试跑的是安装产物，提前暴露打包与导出缺陷"]' title='第 071 讲 · 项目结构与 src 布局' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import sys, os, tempfile

with tempfile.TemporaryDirectory() as root:
    pkg = os.path.join(root, 'webapp')
    os.makedirs(pkg)
    open(os.path.join(pkg, '__init__.py'), 'w').write(
        'from .core import add' + chr(10) + '__all__ = ["add"]' + chr(10))
    open(os.path.join(pkg, 'core.py'), 'w').write(
        'def add(a, b):' + chr(10) + '    return a + b' + chr(10))
    sys.path.insert(0, root)
    import webapp
    print('add via package', webapp.add(4, 5))
    print('__all__', webapp.__all__)
    ns = {}
    exec('from webapp import *', ns)
    print('star imports', sorted(k for k in ns if not k.startswith('__')))
    sys.path.remove(root)
    del sys.modules['webapp']
```

<OutputBox title='对照写法：先自己猜，再点开' output='add via package 9\n__all__ [&#39;add&#39;]\nstar imports [&#39;add&#39;]' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import sys, os, tempfile\n\nwith tempfile.TemporaryDirectory() as root:\n    flat_pkg = os.path.join(root, &#39;myapp&#39;)\n    src_pkg = os.path.join(root, &#39;src&#39;, &#39;myapp&#39;)\n    os.makedirs(flat_pkg)\n    os.makedirs(src_pkg)\n    for p in (flat_pkg, src_pkg):\n        with open(os.path.join(p, &#39;__init__.py&#39;), &#39;w&#39;) as f:\n            f.write(&#39;ORIGIN = &#39; + repr(os.path.dirname(p)) + chr(10))\n    sys.path.insert(0, root)\n    import myapp\n    print(&#39;flat layout resolves to root&#39;, myapp.ORIGIN == root)\n    del sys.modules[&#39;myapp&#39;]\n    sys.path.remove(root)\n    sys.path.insert(0, os.path.join(root, &#39;src&#39;))\n    import myapp\n    print(&#39;src layout resolves to src&#39;, myapp.ORIGIN == os.path.join(root, &#39;src&#39;))\n    del sys.modules[&#39;myapp&#39;]\n    sys.path.remove(os.path.join(root, &#39;src&#39;))", "note": "src 布局 vs 扁平布局：sys.path 决定命中谁"}, {"label": "对照 / 进阶", "code": "import sys, os, tempfile\n\nwith tempfile.TemporaryDirectory() as root:\n    pkg = os.path.join(root, &#39;webapp&#39;)\n    os.makedirs(pkg)\n    open(os.path.join(pkg, &#39;__init__.py&#39;), &#39;w&#39;).write(\n        &#39;from .core import add&#39; + chr(10) + &#39;__all__ = [\"add\"]&#39; + chr(10))\n    open(os.path.join(pkg, &#39;core.py&#39;), &#39;w&#39;).write(\n        &#39;def add(a, b):&#39; + chr(10) + &#39;    return a + b&#39; + chr(10))\n    sys.path.insert(0, root)\n    import webapp\n    print(&#39;add via package&#39;, webapp.add(4, 5))\n    print(&#39;__all__&#39;, webapp.__all__)\n    ns = {}\n    exec(&#39;from webapp import *&#39;, ns)\n    print(&#39;star imports&#39;, sorted(k for k in ns if not k.startswith(&#39;__&#39;)))\n    sys.path.remove(root)\n    del sys.modules[&#39;webapp&#39;]", "note": "包内导入规则：显式相对、__init__ 与 __all__"}]' title='两种写法切换看' />

```python
import sys, os, tempfile, importlib

with tempfile.TemporaryDirectory() as root:
    pkg = os.path.join(root, 'legacy')
    os.makedirs(pkg)
    open(os.path.join(pkg, '__init__.py'), 'w').write('')
    open(os.path.join(pkg, 'a.py'), 'w').write('VALUE = 7' + chr(10))
    open(os.path.join(pkg, 'b.py'), 'w').write('import a' + chr(10) + 'RESULT = a.VALUE' + chr(10))
    sys.path.insert(0, root)
    try:
        m = importlib.import_module('legacy.b')
        print('unexpected success', m.RESULT)
    except ModuleNotFoundError as e:
        print('implicit relative fails', "No module named 'a'" in str(e))
    sys.path.remove(root)
```

<OutputBox title='原理验证' output='implicit relative fails True' />


## 配置隔离、文档入口与单仓多包

配置与密钥必须与代码分离：`pyproject.toml` 放构建与工具配置，`.env` / 环境变量放运行期密钥且进 `.gitignore`，`.env.example` 提交占位键，`README.md` 作为文档入口写清安装、CLI 与最小示例。

`tests/` 放在包外（src 布局强约束），避免把测试打进 wheel。

单仓多包（monorepo）时，每个包各自 `src/<pkg>/` 与独立 `pyproject.toml`，用 path 依赖或工作区（uv workspace / PEP 735 dependency-groups）串起来，共享代码抽成独立包而不是靠相对路径跨包 import。

判断结构是否合理有个可测标准：在干净虚拟环境里安装之后，从任意非仓库目录 import 并跑通公开 API；做不到就说明导入解析还依赖了工作目录。把这条检查写进 CI，比人工评审目录树可靠。

**版本与结构要点**

| 版本 / 项 | 行为 | 对结构的影响 |
| --- | --- | --- |
| 3.3+ PEP 420 | 无 __init__.py 也可作命名空间包 | 普通项目仍应显式写 __init__.py |
| 3.3+ 隐式相对导入 | 已移除，默认绝对导入 | 包内引用一律显式相对 |
| PEP 621 [project] | 元数据集中在 pyproject.toml | 取代零散 setup.py 配置 |
| PEP 735 / uv workspace | 单仓多包与依赖组 | 共享代码抽包，不靠相对路径跨包 |
| pip install -e . | 可编辑安装把 src 映射进环境 | 本地开发与 CI 使用同一份导入路径 |

<FlowTimeline :steps='[{"title": "src 布局 vs 扁平布局：sys.path 决定命中谁", "desc": "扁平布局把包目录直接放项目根：`project/mypkg/__init__.py`…", "tone": "blue"}, {"title": "包内导入规则：显式相对、__init__ 与 __all__", "desc": "Python 3 默认绝对导入（PEP 328），包内 `import a` 会去 …", "tone": "purple"}, {"title": "配置隔离、文档入口与单仓多包", "desc": "配置与密钥必须与代码分离：`pyproject.toml` 放构建与工具配置，`.e…", "tone": "orange"}, {"title": "工程落地", "desc": "生成一个标准 src 布局骨架并验证导入", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 生成一个标准 src 布局骨架并验证导入

新项目落地时，最容易在第一天埋下导入歧义。

可靠的做法是用脚本一次性生成 src 布局骨架：`src/<pkg>/__init__.py` 里用显式相对导入收敛公开 API 并声明 `__all__`，`core.py` 放实现，根目录放 `pyproject.toml`（声明 build-system 与 build-backend）与 `README.md`，测试放包外。

生成后把 src 加入 `sys.path`（等价一次可编辑安装）再 import，验证公开 API 可用且 `__all__` 正确，保证「安装产物」与「本地源码」是同一份解析路径。下面片段用 pathlib 与 tempfile 完成这套骨架并做冒烟验证。

```python
import pathlib, tempfile, sys, importlib

ROOT = pathlib.Path(tempfile.mkdtemp())
SRC = ROOT / 'src'
PKG = SRC / 'orderapp'
PKG.mkdir(parents=True)
(PKG / '__init__.py').write_text('from .core import total' + chr(10) + '__all__ = ["total"]' + chr(10))
(PKG / 'core.py').write_text('def total(xs):' + chr(10) + '    return sum(xs)' + chr(10))
(ROOT / 'pyproject.toml').write_text(
    '[build-system]' + chr(10) + 'requires = ["setuptools>=68"]' + chr(10)
    + 'build-backend = "setuptools.build_meta"' + chr(10))
(ROOT / 'README.md').write_text('# orderapp' + chr(10))

sys.path.insert(0, str(SRC))
pkg = importlib.import_module('orderapp')
print('import from src ok', pkg.total([1, 2, 3]))
print('public api', pkg.__all__)
print('layout files', sorted(p.name for p in ROOT.iterdir()))
sys.path.remove(str(SRC))
```

<Callout type="idea" title='落地提示' text='按领域而不是按技术分层，公开 API 收敛到 __init__，配置全部走环境变量' />

<CheckList id='P071b' title='上线前自检' :items='["能复现并解释「包内写 import a 想引用同包模块」", "能复现并解释「用扁平布局且从项目根跑测试」", "能复现并解释「给包或模块名加连字符、或叫 json.py / test」", "能用一条命令验证 src 与扁平布局对比", "关键路径有自动化测试与失败分支"]' />

```bash
python -m compileall -q . && python -m pytest -q
```

把输入换成你自己的数据，观察结果是否仍符合 src 与扁平布局对比 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 包内写 import a 想引用同包模块 | Python 3 默认绝对导入，会去 sys.path 顶层找 a，报 ModuleNotFoundError: No module named 'a' | 改 from . import a 或 from .core import add 显式相对导入 |
| 用扁平布局且从项目根跑测试 | 根目录进 sys.path[0]，import 命中未打包源码，掩盖打包缺文件与 __init__ 漏导出 | 改 src 布局、配 package-dir = &#123;'' = 'src'&#125;，CI 里 pip install . 后从非仓库目录验证 |
| 给包或模块名加连字符、或叫 json.py / test | 含连字符无法被 import，与标准库同名会遮蔽内置模块 | 一律小写下划线，避免标准库保留名；公开 API 收敛到 __init__.py 的 __all__ |

<Callout type="warn" title='本讲最容易踩的坑' text='包内写 import a 想引用同包模块：Python 3 默认绝对导入，会去 sys.path 顶层找 a，报 ModuleNotFoundError: No module named &#39;a&#39;' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：包内写 import a 想引用同包模块", "body": "Python 3 默认绝对导入，会去 sys.path 顶层找 a，报 ModuleNotFoundError: No module named &#39;a&#39;", "tip": "改 from . import a 或 from .core import add 显式相对导入"}, {"title": "第 2 步：用扁平布局且从项目根跑测试", "body": "根目录进 sys.path[0]，import 命中未打包源码，掩盖打包缺文件与 __init__ 漏导出", "tip": "改 src 布局、配 package-dir = {&#39;&#39; = &#39;src&#39;}，CI 里 pip install . 后从非仓库目录验证"}, {"title": "第 3 步：给包或模块名加连字符、或叫 json.py ", "body": "含连字符无法被 import，与标准库同名会遮蔽内置模块", "tip": "一律小写下划线，避免标准库保留名；公开 API 收敛到 __init__.py 的 __all__"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：识别命名空间包' task='建一个只有子模块、没有 __init__.py 的目录，加进 sys.path 后 import，打印其 __file__ 是否为 None 与 __spec__.origin。' solution='import sys, os, tempfile, importlib\nwith tempfile.TemporaryDirectory() as d:\n    os.makedirs(os.path.join(d, &#39;nsp&#39;))\n    open(os.path.join(d, &#39;nsp&#39;, &#39;m.py&#39;), &#39;w&#39;).write(&#39;X = 9&#39; + chr(10))\n    sys.path.insert(0, d)\n    pkg = importlib.import_module(&#39;nsp&#39;)\n    print(&#39;namespace __file__&#39;, getattr(pkg, &#39;__file__&#39;, &#39;missing&#39;) is None)\n    print(&#39;origin&#39;, pkg.__spec__.origin)\n    sys.path.remove(d)' explain='PEP 420 命名空间包没有 __init__.py，__file__ 为 None、__spec__.origin 为 None，可跨多个分发合并同名包；普通项目应显式写 __init__.py。' />

<Exercise title='进阶：验证显式相对导入可用' task='建包 pkg，a.py 定义 VALUE=5，b.py 用 from . import a 计算 RESULT=a.VALUE*2，import pkg.b 后打印 RESULT。' solution='import sys, os, tempfile, importlib\nwith tempfile.TemporaryDirectory() as d:\n    p = os.path.join(d, &#39;pkg&#39;)\n    os.makedirs(p)\n    open(os.path.join(p, &#39;__init__.py&#39;), &#39;w&#39;).write(&#39;&#39;)\n    open(os.path.join(p, &#39;a.py&#39;), &#39;w&#39;).write(&#39;VALUE = 5&#39; + chr(10))\n    open(os.path.join(p, &#39;b.py&#39;), &#39;w&#39;).write(&#39;from . import a&#39; + chr(10) + &#39;RESULT = a.VALUE * 2&#39; + chr(10))\n    sys.path.insert(0, d)\n    m = importlib.import_module(&#39;pkg.b&#39;)\n    print(&#39;explicit relative&#39;, m.RESULT)\n    sys.path.remove(d)' explain='显式相对导入 from . import a 在当前包内解析，成功取到 a.VALUE 并算出 10；写成 import a 则会去顶层查找而失败。' />

<Quiz no='071-1' q='扁平布局「本地能跑、发布就坏」的根因是？' :options='["项目根进 sys.path[0]，测试 import 命中未打包源码，掩盖打包缺陷", "src 布局性能更差", "pip 不识别 __init__.py", "Python 3 禁止从根目录 import"]' answer="0" explain='从项目根运行 pytest 时根目录进入 sys.path，import 直接命中本地包目录；只有装到 site-packages 后才暴露漏打文件或漏导出，src 布局把根移出搜索路径即可提前暴露。' />

<Quiz no='071-2' q='包内模块 b.py 写 import a 想引用同包 a.py，Python 3 会？' :options='["按绝对导入去 sys.path 顶层找 a，通常报 No module named &#39;a&#39;", "自动当成相对导入成功", "报 SyntaxError", "把 a 升级为命名空间包"]' answer="0" explain='PEP 328 起默认绝对导入，隐式相对导入已移除；必须写 from . import a 或 from .a import X，否则去顶层找同名模块。' />

<Quiz no='071-3' q='关于 __init__.py 与 __all__，正确的是？' :options='["__init__.py 标记包并可收敛 API，__all__ 控制 from pkg import * 的导出", "__all__ 决定包能否被 import", "命名空间包必须写 __all__", "__init__.py 在 Python 3 已被废弃"]' answer="0" explain='__init__.py 把目录标记为包并执行初始化，配合 from .core import add 与 __all__ = [&#39;add&#39;] 可只暴露公开 API；PEP 420 下没有它也能形成命名空间包。' />

<Predict no='071-4' q='包内 b.py 写 import a（同包有 a.py），import pkg.b 的结果最可能是？' :options='["ModuleNotFoundError: No module named &#39;a&#39;", "成功且 a.VALUE 可用", "ImportError: attempted relative import with no known parent package"]' answer='0' output='ModuleNotFoundError: No module named &#39;a&#39;' explain='Python 3 默认绝对导入，import a 只在 sys.path 顶层查找；顶层没有 a.py，于是抛 No module named &#39;a&#39;。改为 from . import a 才会在包内解析。' />

<FillBlank no='071-5' tpl='___ sys, os, tempfile' :answers='["import"]' hint='回想本讲关于 src 与扁平布局对比 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 src 布局 vs 扁平布局：sys.path 决定命中谁 的落点。' />

<KnowledgeCard :points='["src 布局让项目根不在 sys.path，测试跑的是安装产物，提前暴露打包与导出缺陷", "pyproject.toml 配 package-dir 把根映射到 src；tests 放包外，密钥走环境变量", "Python 3 默认绝对导入（PEP 328），包内引用必须 from . import a 显式相对", "__init__.py 标记包、初始化、用 __all__ 收敛公开 API；PEP 420 命名空间包 __file__ 与 origin 均为 None", "模块名小写下划线，避免连字符与 json.py / test 这类标准库同名", "验收标准：干净虚拟环境安装后从非仓库目录 import 并跑通公开 API"]' :pitfalls='["包内写 import a 想引用同包模块", "用扁平布局且从项目根跑测试", "给包或模块名加连字符、或叫 json.py / test", "把测试放在包内一起发布，或用隐式相对导入，都会让安装后的行为与本地不一致"]' summary='src 布局逼迫你只能用安装后的包来测试，因而能提前暴露「本地能跑、发布就坏」的导入问题' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| src 布局让项目根不在 sys.path，测试跑的是安装产物，提前暴露打包与导出缺陷 | 建立直觉 |
| pyproject.toml 配 package-dir 把根映射到 src；tests 放包外，密钥走环境变量 | 跑通示例 |
| Python 3 默认绝对导入（PEP 328），包内引用必须 from . import a 显式相对 | 深入边界 |
| __init__.py 标记包、初始化、用 __all__ 收敛公开 API；PEP 420 命名空间包 __file__ 与 origin 均为 None | 工程落地 |
| 模块名小写下划线，避免连字符与 json.py / test 这类标准库同名 | 随堂检测 |
| 验收标准：干净虚拟环境安装后从非仓库目录 import 并跑通公开 API | 复盘 |

1. src 布局让项目根不在 sys.path，测试跑的是安装产物，提前暴露打包与导出缺陷

2. pyproject.toml 配 package-dir 把根映射到 src；tests 放包外，密钥走环境变量

3. Python 3 默认绝对导入（PEP 328），包内引用必须 from . import a 显式相对

[下一讲：依赖管理：venv、uv、锁文件与可复现构建](/engineering/deps)
