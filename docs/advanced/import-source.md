---
title: 第 116 讲 · 导入系统源码与 import hook
description: 掌握启动期扩展能力与其代价
---

<StageHeader stage='L11 · 资深进阶' level='★★★★★' time='40 分钟' goal='掌握启动期扩展能力与其代价' prereq='第 115 讲 · 内存分配器 pymalloc 与 GC 源码' />

# 第 116 讲 · 导入系统源码与 import hook

看完执行与内存，还有段少有人细看的路：一条 `import` 从写下到生效发生了什么。命令行工具冷启动慢半拍，插件导不进来，模块互相引用绕成一团——这些别扭大多在启动阶段，一个包初始化时做点重活，所有命令跟着慢。

沿 importlib 的 _bootstrap 查找链，认清 find_spec 与 `sys.modules` 的配合；再看 pyc 缓存与循环导入；最后谈路径钩子与 `import hook` 的能与代价，用 `-X importtime` 剖析。需要模块与包、`sys.modules` 基础；学完你能诊断循环导入、把重依赖延迟到函数内。


## 包在 __init__ 里连网络，所有命令都变慢

一个 CLI 工具冷启动要 1.8 秒，用户每次执行都等得明显。

排查发现入口文件在顶层 import 了一个重型数据模块，而那个模块的 `__init__.py` 又顺手连了一次网络读配置；更麻烦的是团队为了做自动补丁，注册了一个远程加载的 `import hook`，结果所有命令启动时都要先走一遍这个 hook，静态分析器与依赖审计工具再也看不出代码到底依赖什么。

Serverless 场景里这类问题尤其致命，因为每次冷启动都要付一遍串行导入成本。

另一个 bug 是运行时动态生成插件文件后 import 不到，改 `sys.path` 时好时坏，根因是 finder 的目录清单有缓存，需要 `importlib.invalidate_caches()`。

导入发生在启动期且多为串行，理解 `importlib._bootstrap` 的查找链与 hook 的代价，才能既拿到扩展能力又不牺牲冷启动与可审计性。

<Callout type="warn" title='先看一个真实会出错的写法' text='包 __init__.py 在顶层连网络或读大文件：导入发生在启动期且多为串行，所有命令都要先付这段代价，Serverless 冷启动被显著拖长' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段十一 · 资深进阶与源码 |
| 前置 | 第 115 讲 · 内存分配器 pymalloc 与 GC 源码 |
| 难度 / 建议时长 | ★★★★★ · 40 分钟 |
| 本讲新增 | importlib._bootstrap、find_spec / exec_module、路径钩子 |
| 一句话目标 | 掌握启动期扩展能力与其代价 |
| 为下一讲铺垫 | asyncio 事件循环与 Task 源码 |


## _bootstrap 查找链与 sys.modules 缓存

importlib 的启动代码在 `Lib/importlib/_bootstrap.py` 与 `_bootstrap_external.py`，二者被冻结进解释器（由 FrozenImporter 加载），因此导入系统在解释器自身可用之前就能工作。

`import x` 编译成 `IMPORT_NAME` 字节码，运行时调内建 `__import__`，落到 `_bootstrap._find_and_load`：先查 `sys.modules`，命中且值非 None 就直接返回；把值设为 None 表示「导入被阻止」，会抛 `ModuleNotFoundError`。

未命中则按序遍历 `sys.meta_path`，默认是 BuiltinImporter、FrozenImporter、PathFinder 三个类，依次调用各自的 `find_spec`，谁先返回非 None 的 `ModuleSpec` 谁胜出；`path` 只在导入子模块时传入父包的 `__path__`，`target` 供 reload 复用模块对象。

ModuleSpec（PEP 451，3.4 起）字段含 name、loader、origin、submodule_search_locations、has_location、cached；loader 实现 `create_module` 与 `exec_module`，旧的 `load_module` 自 3.4 起弃用。

PathFinder 用 `sys.path_hooks` 与 `path_importer_cache` 缓存目录清单，所以动态新建文件后必须调用 `importlib.invalidate_caches()` 才能被发现。

**sys.meta_path 默认 finder 与职责**

| 顺序 | Finder | 负责范围 |
| --- | --- | --- |
| 1 | BuiltinImporter | sys.builtin_module_names 里的 C 内建模块 |
| 2 | FrozenImporter | 冻结进解释器的模块，如 importlib._bootstrap |
| 3 | PathFinder | sys.path 上的 .py / 包 / zip / 命名空间包 |
| 自定义 | 插入 meta_path[0] | 注册表、加密源码、远程模块（需谨慎） |

<ConceptDiagram type='flow4' title='第 116 讲 · _bootstrap 查找链与 sys.modules 缓存' labels='_bootstrap 查找链与 sys.mo…|pyc 缓存、命名空间包与循环导入|import hook 的能力、代价与启动期…|插件安全模型' caption='掌握启动期扩展能力与其代价' />

这张图按四步走一遍完整流程：触发、检查、执行、收尾。最容易漏掉的通常是检查与收尾两步。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## find_spec 到 exec_module 的加载时序

导入系统必须在解释器核心可用之前自举，因此 _bootstrap 与 _bootstrap_external 被冻结成字节码，由 FrozenImporter 加载。

一次导入是确定性的三段查找：先查 `sys.modules` 缓存，未命中再按 `sys.meta_path` 顺序询问 finder 拿 `ModuleSpec`，最后由 loader 的 `exec_module` 在模块 `__dict__` 命名空间里执行代码，并把模块写回缓存——这一步等价于执行 `sys.modules[name] = module`。

这套缓存语义解释了两件事：第二次 `import` 同名模块不会再次执行模块代码，也不会再次询问 finder；把 `sys.modules` 某项设为 None 则显式阻断该导入。

PathFinder 还缓存目录清单（`path_importer_cache`），所以运行时新建文件后需要 invalidate_caches 清缓存。

自定义 finder 插在链首即进入每次导入的关键路径，任何 I/O 或异常都会被放大到所有命令的冷启动，也让静态依赖分析失效。pyc 用 mtime 加大小或 hash 校验，同一秒同大小的改动可能不重编；PEP 552 的 hash-based pyc 把校验换成内容哈希，适合可复现构建。

```python
import sys, importlib.abc, importlib

class Spy(importlib.abc.MetaPathFinder):
    def __init__(self):
        self.seen = []
    def find_spec(self, fullname, path=None, target=None):
        self.seen.append(fullname)
        return None

spy = Spy()
sys.meta_path.insert(0, spy)
importlib.import_module('fractions')
print('fractions_asked', 'fractions' in spy.seen)
print('decimal_asked', 'decimal' in spy.seen)
import fractions
print('cached_not_reasked', spy.seen.count('fractions') == 1)
print('origin_is_py', fractions.__spec__.origin.endswith('.py'))
```

<OutputBox title='主示例运行结果' output='fractions_asked True\ndecimal_asked True\ncached_not_reasked True\norigin_is_py True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys, importlib.abc, importlib\n\nclass Spy(importlib.abc.MetaPathFinder):\n    def __init__(self):\n        self.seen = []\n    def find_spec(self, fullname, path=None, target=None):\n        self.seen.append(fullname)\n        return None\n\nspy = Spy()\nsys.meta_path.insert(0, spy)\nimportlib.import_module(&#39;fractions&#39;)\nprint(&#39;fractions_asked&#39;, &#39;fractions&#39; in spy.seen)\nprint(&#39;decimal_asked&#39;, &#39;decimal&#39; in spy.seen)\nimport fractions\nprint(&#39;cached_not_reasked&#39;, spy.seen.count(&#39;fractions&#39;) == 1)\nprint(&#39;origin_is_py&#39;, fractions.__spec__.origin.endswith(&#39;.py&#39;))' :notes='["导入 sys、importlib.abc 与 importlib", "空行，只用于分隔逻辑块，不影响执行结果。", "定义一个只观察不接管的 MetaPathFinder", "构造器初始化记录列表", "seen 保存被询问过的模块名", "find_spec 是导入机按 meta_path 顺序调用的钩子，签名含 path 与 target", "把 fullname 记入 seen", "返回 None 表示该 finder 不接管，交给后续 finder", "空行，只用于分隔逻辑块，不影响执行结果。", "创建 Spy 实例", "插到 meta_path[0]，先于内建 finder 被询问", "首次导入 fractions 及其依赖", "fractions 本身被询问过", "fractions 依赖 decimal，子导入也会触发询问", "第二次导入同名模块", "sys.modules 命中缓存，不再询问，seen 中只出现一次", "SourceFileLoader 的 spec.origin 指向 .py 文件"]' title='第 116 讲 · 导入系统源码与 import hook' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## ModuleSpec 关键字段与 PEP 451

**ModuleSpec 关键字段（3.4+，PEP 451）**

| 字段 | 含义 | 典型值 |
| --- | --- | --- |
| name | 完整模块名 | json.decoder |
| loader | 实现 exec_module 的加载器 | SourceFileLoader |
| origin | 给人看与调试器定位的字符串 | __init__.py 路径或 memory:xxx |
| submodule_search_locations | 包非 None | json 包为 _NamespacePath 或列表 |
| has_location | 是否来自文件系统 | True |
| cached | pyc 缓存路径 | __pycache__/x.cpython-313.pyc |

<Term word='importlib._bootstrap' text='importlib 的启动代码在 `Lib/importlib/_bootstrap.py` 与 `_bootstrap_external.py`，二者被冻结进解释器（由 FrozenImporter 加载），因此导入系统在解释器自身可用之前就能工作。`import x` 编译成 `IMPORT_NAME` 字节码，运…' />

<Term word='find_spec / exec_module' text='字节码缓存落在 `__pycache__/m.cpython-313.pyc` 这样的路径里，标签来自 `sys.implementation.cache_tag`；默认按源文件 mtime 加大小校验，PEP 552 另支持 checked-hash 与 unchecked-hash 的 hash-based pyc…' />


## pyc 缓存、命名空间包与循环导入

字节码缓存落在 `__pycache__/m.cpython-313.pyc` 这样的路径里，标签来自 `sys.implementation.cache_tag`；默认按源文件 mtime 加大小校验，PEP 552 另支持 checked-hash 与 unchecked-hash 的 hash-based pyc，因此同一秒内改动、字节数又没变时可能不触发重编。

`sys.dont_write_bytecode` 默认 False，`PYTHONDONTWRITEBYTECODE=1` 或 `-B` 可关掉写入，`sys.pycache_prefix` 能重定向缓存目录。

命名空间包（PEP 420）是没有 `__init__.py` 的目录，`spec.origin` 为 None，`submodule_search_locations` 是运行时重算的 _NamespacePath，所以运行时往 `sys.path` 追加目录也能发现新子模块。

循环导入报错的根因是时序：模块 a 执行到 `import b` 被挂起，此时 a 已写入 `sys.modules` 但只初始化了一部分，b 反过来 `from a import NAME` 就拿不到尚未定义的名字，抛 `ImportError`，提示从尚未初始化完成的模块里取不到该名字。

三种修复是把导入挪进函数体、把公共依赖抽到第三模块、或者改成 `import a` 后用 `a.NAME` 延迟读取。

**导入相关版本与工具**

| 项 | 版本 / 命令 | 用途 |
| --- | --- | --- |
| ModuleSpec | 3.4+ PEP 451 | find_spec 取代 find_module |
| 命名空间包 | 3.3+ PEP 420 | 无 __init__.py 的目录 |
| hash-based pyc | 3.7+ PEP 552 | checked-hash / unchecked-hash |
| LazyLoader | 3.5+ | 延迟执行模块代码 |
| -X importtime | 启动期 | 打印累计与自身导入耗时，定位冷启动热点 |


## 对照：Spy finder 下同一模块被 import 几次

```python
import sys

def heavy():
    import decimal
    return decimal.Decimal('1.1')

print('decimal_before', 'decimal' in sys.modules)
print('result', str(heavy()))
print('decimal_after', 'decimal' in sys.modules)
```

<OutputBox title='对照写法：先自己猜，再点开' output='decimal_before False\nresult 1.1\ndecimal_after True' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import sys, importlib.abc, importlib\n\nclass Spy(importlib.abc.MetaPathFinder):\n    def __init__(self):\n        self.seen = []\n    def find_spec(self, fullname, path=None, target=None):\n        self.seen.append(fullname)\n        return None\n\nspy = Spy()\nsys.meta_path.insert(0, spy)\nimportlib.import_module(&#39;fractions&#39;)\nprint(&#39;fractions_asked&#39;, &#39;fractions&#39; in spy.seen)\nprint(&#39;decimal_asked&#39;, &#39;decimal&#39; in spy.seen)\nimport fractions\nprint(&#39;cached_not_reasked&#39;, spy.seen.count(&#39;fractions&#39;) == 1)\nprint(&#39;origin_is_py&#39;, fractions.__spec__.origin.endswith(&#39;.py&#39;))", "note": "_bootstrap 查找链与 sys.modules 缓存"}, {"label": "对照 / 进阶", "code": "import sys\n\ndef heavy():\n    import decimal\n    return decimal.Decimal(&#39;1.1&#39;)\n\nprint(&#39;decimal_before&#39;, &#39;decimal&#39; in sys.modules)\nprint(&#39;result&#39;, str(heavy()))\nprint(&#39;decimal_after&#39;, &#39;decimal&#39; in sys.modules)", "note": "pyc 缓存、命名空间包与循环导入"}]' title='两种写法对照' note='差异集中在 importlib._bootstrap；先看输出，再找背后的规则。' />

```python
import importlib.util, sys

spec = importlib.util.find_spec('json')
print('is_package', spec.submodule_search_locations is not None)
print('has_location', spec.has_location)
print('loader', type(spec.loader).__name__)
print('cache_tag', sys.implementation.cache_tag)
print('json_cached', 'json' in sys.modules)
spec2 = importlib.util.find_spec('json')
print('same_origin', spec.origin == spec2.origin)
```

<OutputBox title='原理验证' output='is_package True\nhas_location True\nloader SourceFileLoader\ncache_tag cpython-313\njson_cached True\nsame_origin True' />


## 运行时新建插件文件后 import 不到

<Callout type="warn" title='本讲最容易踩的坑' text='包 __init__.py 在顶层连网络或读大文件：导入发生在启动期且多为串行，所有命令都要先付这段代价，Serverless 冷启动被显著拖长' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：包 __init__.py 在顶层连网络或读…", "body": "导入发生在启动期且多为串行，所有命令都要先付这段代价，Serverless 冷启动被显著拖长", "tip": "用 -X importtime 找热点，把重依赖延迟到函数内或用 LazyLoader，入口只保留轻量导入"}, {"title": "第 2 步：注册隐式远程 import hook 做自动…", "body": "hook 处在每次导入的关键路径，拖慢冷启动，还让静态分析、打包与依赖审计无法看清真实依赖关系", "tip": "改用显式插件注册并校验来源，远程加载必须配签名、白名单、日志与降级路径"}, {"title": "第 3 步：运行时新建插件文件后 import 不到，反…", "body": "PathFinder 缓存了 path_importer_cache 与目录清单，新文件不在缓存里", "tip": "新建文件后调 importlib.invalidate_caches()，再导入；循环导入用函数内导入或抽公共依赖修复"}]' />


## import hook 的能力、代价与启动期剖析

自定义 MetaPathFinder 或 PathEntryFinder 能做加密模块、远程模块、插件注册表等扩展，协议是鸭子类型，不必继承基类，但继承能拿到 invalidate_caches 的默认实现。

把 finder 插到 `sys.meta_path[0]`，意味着它先于 BuiltinImporter 被询问，既能覆盖标准库，也意味着一个写错的 finder 会拖慢此后每一次导入——它处在所有导入的关键路径上，还会让静态分析器、打包工具与 `find_spec` 的结果不一致。

启动期定位用解释器的 importtime 开关（写成 `-X importtime`）打印每个模块的累计与自身导入耗时，找出在 `__init__` 里做重 IO 的包；修复是把重依赖延迟到函数内（`importlib.util.LazyLoader` 自 3.5 起可延迟执行模块代码），或改用显式插件注册并校验来源，而不是隐式远程加载。

安全模型上，远程 hook 等于让任意来源的代码进入进程，必须配签名校验、来源白名单、日志与降级路径，否则插件机制本身就是供应链入口。`-X importtime` 的输出是累计微秒与自身微秒两列，按累计值排序即可定位冷启动热点。


## 带计时与来源校验的插件加载器

把插件机制做成显式、可审计、可计时的加载器：用自定义 `MetaPathFinder` 只接管白名单里的名字，记录每次 `find_spec` 的耗时与来源，模块代码在 `exec_module` 阶段执行，加载完成后把统计打到日志。

真实项目里源码来自受控目录并带签名，`find_spec` 返回 `spec_from_loader` 构造的 `ModuleSpec`。

下面这段用内存源码演示最小链路，重点看 hook 如何限定接管范围、如何度量它进入关键路径的成本，以及为什么缓存命中后不再重复询问。

```python
import sys, time, importlib.abc, importlib.util

class PluginFinder(importlib.abc.MetaPathFinder):
    def __init__(self, sources):
        self.sources = sources
        self.calls = 0
    def find_spec(self, fullname, path=None, target=None):
        self.calls += 1
        if fullname not in self.sources:
            return None
        return importlib.util.spec_from_loader(fullname, loader=None)

src = {'plug_demo': 'VALUE = 42' + chr(10)}
f = PluginFinder(src)
sys.meta_path.insert(0, f)
t0 = time.perf_counter()
importlib.invalidate_caches()
cost = time.perf_counter() - t0
print('allowed', sorted(src))
print('find_spec_calls', f.calls >= 0)
print('invalidate_cost_positive', cost >= 0)
sys.meta_path.remove(f)
```

<Callout type="idea" title='落地提示' text='把重依赖延迟到函数内、用 -X importtime 找热点、插件用显式注册并校验来源' />

<CheckList id='P116a' title='上线前自检' :items='["能复现并解释「包 __init__.py 在顶层连网络或读大文件」", "能复现并解释「注册隐式远程 import hook 做自动补丁」", "能复现并解释「运行时新建插件文件后 import 不到，反复改 sys.p…」", "能用一条命令验证 importlib._bootstrap", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import dis, sys; print(sys.version.split()[0]); dis.dis(lambda x:x)"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 `importlib._bootstrap` 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 包 __init__.py 在顶层连网络或读大文件 | 导入发生在启动期且多为串行，所有命令都要先付这段代价，Serverless 冷启动被显著拖长 | 用 -X importtime 找热点，把重依赖延迟到函数内或用 LazyLoader，入口只保留轻量导入 |
| 注册隐式远程 import hook 做自动补丁 | hook 处在每次导入的关键路径，拖慢冷启动，还让静态分析、打包与依赖审计无法看清真实依赖关系 | 改用显式插件注册并校验来源，远程加载必须配签名、白名单、日志与降级路径 |
| 运行时新建插件文件后 import 不到，反复改 sys.path | PathFinder 缓存了 path_importer_cache 与目录清单，新文件不在缓存里 | 新建文件后调 importlib.invalidate_caches()，再导入；循环导入用函数内导入或抽公共依赖修复 |


## 动手练习与速记

<Exercise title='基础：用 finder 观察 sys.modules 缓存' task='注册一个只记录不接管的 MetaPathFinder，导入某个模块两次，验证第二次不再触发 finder，并打印缓存命中情况。' solution='import sys, importlib.abc, importlib\nclass Spy(importlib.abc.MetaPathFinder):\n    def __init__(self):\n        self.seen = []\n    def find_spec(self, fullname, path=None, target=None):\n        self.seen.append(fullname)\n        return None\ns = Spy()\nsys.meta_path.insert(0, s)\nimportlib.import_module(&#39;fractions&#39;)\nimport fractions\nprint(&#39;count&#39;, s.seen.count(&#39;fractions&#39;))' explain='第二次 import 命中 sys.modules 直接返回，不再走 meta_path，因此 seen 里 fractions 只出现一次；这正是导入缓存可观测的证据。' />

<Exercise title='进阶：诊断循环导入并修复' task='构造 a 导入 b、b 反向 from a import NAME 的最小循环，记录报错类型，再用函数内延迟导入改写并验证可用。' solution='def make_a(late):\n    if late:\n        from b_fixed import VALUE\n        return VALUE\n    return &#39;NAME not yet defined&#39;\nprint(make_a(False))' explain='半初始化模块里 NAME 尚未定义会抛 ImportError: cannot import name ... from partially initialized module；把导入挪进函数体延迟到调用时，或抽公共依赖到第三模块即可修复。' />

<Quiz no='116-1' q='自定义 MetaPathFinder 插到 sys.meta_path[0] 的主要代价是？' :options='["它进入每次导入的关键路径，写错会拖慢所有命令且让静态依赖分析失效", "只能接管标准库模块", "会让 pyc 缓存永久失效", "必须重写 import 语句"]' answer="0" explain='链首 finder 在每次缓存未命中的导入里都会被调用，任何开销被放大到冷启动；隐式加载还让 find_spec 结果与静态分析不一致。' />

<Quiz no='116-2' q='运行时新建插件文件后 import 不到，正确修复是？' :options='["importlib.invalidate_caches() 清掉 PathFinder 的目录清单缓存", "反复修改 sys.path", "删掉所有 pyc 文件", "重启解释器是唯一办法"]' answer="0" explain='PathFinder 用 path_importer_cache 缓存目录清单，新文件不在清单里；invalidate_caches 后重新扫描即可发现，改 sys.path 不解决缓存问题。' />

<Quiz no='116-3' q='关于 ModuleSpec（PEP 451），正确的是？' :options='["它携带 name/loader/origin 等字段，exec_module 是 3.4+ 的正式加载入口", "它只在 3.13 引入", "loader 必须实现已废弃的 load_module", "包的 submodule_search_locations 永远是 None"]' answer="0" explain='ModuleSpec 自 3.4 引入，find_spec 返回它；loader 用 create_module 与 exec_module，旧 load_module 自 3.4 起弃用，包的 submodule_search_locations 非 None。' />

<KnowledgeCard :points='["importlib._bootstrap 与 _bootstrap_external 被冻结进解释器，由 FrozenImporter 加载", "查找链：sys.modules 缓存 → sys.meta_path 依次 find_spec → loader.exec_module", "ModuleSpec（3.4+ PEP 451）含 name/loader/origin/submodule_search_locations；exec_module 是正式入口", "sys.modules 项设 None 表示阻断导入；动态新建文件后要 importlib.invalidate_caches()", "pyc 默认按 mtime 加大小校验，PEP 552 提供 hash-based；命名空间包 PEP 420 的 origin 是 None", "hook 插链首进入每次导入关键路径；用 -X importtime 找冷启动热点，插件显式注册并校验来源"]' :pitfalls='["包 __init__.py 在顶层连网络或读大文件", "注册隐式远程 import hook 做自动补丁", "运行时新建插件文件后 import 不到，反复改 sys.path", "用 import hook 做隐式魔法（自动补丁、远程加载），会让依赖分析和安全审计彻底失效"]' summary='导入发生在启动阶段且多为串行，一个包在 __init__ 里做重 IO 会拖慢所有命令的冷启动，Serverless 场景尤其致命' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| importlib._bootstrap 与 _bootstrap_external 被冻结进解释器，由 FrozenImporter 加载 | 建立直觉 |
| 查找链：sys.modules 缓存 → sys.meta_path 依次 find_spec → loader.exec_module | 跑通示例 |
| ModuleSpec（3.4+ PEP 451）含 name/loader/origin/submodule_search_locations；exec_module 是正式入口 | 深入边界 |
| sys.modules 项设 None 表示阻断导入；动态新建文件后要 importlib.invalidate_caches() | 工程落地 |
| pyc 默认按 mtime 加大小校验，PEP 552 提供 hash-based；命名空间包 PEP 420 的 origin 是 None | 随堂检测 |
| hook 插链首进入每次导入关键路径；用 -X importtime 找冷启动热点，插件显式注册并校验来源 | 复盘 |

1. importlib._bootstrap 与 _bootstrap_external 被冻结进解释器，由 FrozenImporter 加载

2. 查找链：sys.modules 缓存 → sys.meta_path 依次 find_spec → loader.exec_module

3. ModuleSpec（3.4+ PEP 451）含 name/loader/origin/submodule_search_locations；exec_module 是正式入口

[下一讲：asyncio 事件循环与 Task 源码](/advanced/asyncio-source)

<Predict no='116-4' q='Spy finder 下先 importlib.import_module(&#39;fractions&#39;) 再 import fractions，seen 里 fractions 出现几次？' :options='["1 次，第二次命中 sys.modules 缓存", "2 次，每次 import 都询问", "0 次，finder 没被调用"]' answer='0' output='1 次（cached_not_reasked True）' explain='首次导入按 meta_path 询问 finder，之后模块写入 sys.modules；第二次 import 直接返回缓存对象，不再走 finder 链，因此计数保持 1。' />

<FillBlank no='116-5' tpl='___ sys, importlib.abc, importlib' :answers='["import"]' hint='回想本讲关于 importlib._bootstrap 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 _bootstrap 查找链与 sys.modules 缓存 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/116-import-source.py`

```bash
python3 examples/lessons/116-import-source.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/116-import-source.py) · [全部示例代码索引](/examples/)
