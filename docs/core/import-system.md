---
title: 第 055 讲 · 导入系统源码级：finder、loader 与缓存
description: 能编写 import hook 并解决复杂导入问题
---

<StageHeader stage='L5 · 核心机制' level='★★★★☆' time='40 分钟' goal='能编写 import hook 并解决复杂导入问题' prereq='第 054 讲 · GIL 真相：存在原因、切换与影响边界' />

# 第 055 讲 · 导入系统源码级：finder、loader 与缓存

上一讲量清了 GIL 的影响边界，但那还在说线程排队，没回答更靠前一问：一行 `import` 之前，模块怎么被找出来、又被记住。先别让多条执行流掺和，把单个执行流的状态从哪来弄清，才谈得上几个人同时改它。常见的是同一脚本在测试机正常，进容器却偶发找不到模块。

从导入的查找顺序起步，看清 `sys.meta_path` 上 finder 依次询问、loader 建模块的分工，再走到 `sys.modules` 缓存与 `__pycache__` 何时失效，末了处理循环导入与命名空间包。需熟悉模块、包与函数作用域；读完能写出导入系统钩子，说得清这类时灵时不灵的成因。


## 一个偶发 ModuleNotFoundError 与半初始化模块

上线脚本里有个 `import config` 在测试环境正常，进容器后偶发 `ModuleNotFoundError`，另一个模块又报『无法从半初始化的模块里导入名字』。

团队先怀疑路径写错，反复改 `sys.path` 却时好时坏；再怀疑打包漏文件，把源码又拷了一遍。

真正原因是两层机制都没对齐：一是 `sys.meta_path` 上的 finder 按固定顺序询问、`sys.modules` 有缓存，运行时生成的配置文件必须先注册 finder 或调 `importlib.invalidate_caches()`；

二是包 `__init__.py` 里反向导入子模块时撞上半初始化状态。只靠「把文件放到能找到的地方」这种朴素解法，解释不了为什么同一个 `import` 有时成功、有时抛属性错误，也说不清 `__pycache__` 何时失效。要修好这类问题，得把导入当成一次可拦截、可缓存、有明确时序的查找过程。

<Callout type="warn" title='先看一个真实会出错的写法' text='运行时生成新模块后 import 仍报 ModuleNotFoundError：PathFinder 缓存了目录清单与 FileFinder 实例，新文件不会自动进入视野' />


## sys.meta_path 上的三类 finder

`import x` 会编译成 `IMPORT_NAME` 字节码，运行时调内建 `__import__`，落到 `importlib._bootstrap._find_and_load`：先以模块名查 `sys.modules`，命中且值非 `None` 就直接返回。

未命中则按序遍历 `sys.meta_path`，默认是三个类 `BuiltinImporter`、`FrozenImporter`、`PathFinder`，依次调用 `find_spec`。

第一个返回非 `None` 的 `ModuleSpec` 胜出，返回 `None` 表示「不归我管」；

全部返回 `None` 才抛 `ModuleNotFoundError`。

参数 `path` 只在导入子模块时传入父包的 `__path__`，顶层模块为 `None`；

`target` 供 `importlib.reload` 复用同一个模块对象。

自定义 finder 不必继承 `MetaPathFinder`，协议是鸭子类型，但继承能拿到 `invalidate_caches` 的默认实现。

`sys.meta_path` 的下标就是优先级，插到 0 会先于内建模块被询问，因此既能覆盖标准库，也意味着一个写错的 finder 会拖慢此后每一次导入。

**sys.meta_path 默认 finder 与职责**

| 顺序 | Finder 类 | 负责范围 | 未命中时行为 |
| --- | --- | --- | --- |
| 1 | BuiltinImporter | sys.builtin_module_names 里的 C 内建模块 | 返回 None 交给下一个 |
| 2 | FrozenImporter | 冻结进解释器的模块，如 importlib._bootstrap | 返回 None 交给下一个 |
| 3 | PathFinder | sys.path 上的 .py / 包 / zip / 命名空间包 | 全部落空则抛 ModuleNotFoundError |
| 自定义 | 插入 sys.meta_path[0] 的对象 | 注册表名、加密源码、远程模块 | 返回 None 让默认链路兜底 |

<Callout type="tip" title='核心心智模型' text='`import x` 会编译成 `IMPORT_NAME` 字节码，运行时调内建 `__import__`，落到 `importlib._bootstrap._find_and_load`：先以模块名查 `sys.modules`，命中且值非 `None` 就直接返回。未命中则按序遍历…' />


### sys.modules 命中即返回的代价

```python
import sys
import importlib.util
import inspect

print('py', sys.version_info[0], sys.version_info[1])
print('meta_path', [f.__name__ for f in sys.meta_path])
print('finder_sig', str(inspect.signature(sys.meta_path[2].find_spec)))
print('pyc', importlib.util.cache_from_source('demo.py').split('/')[-1])
print('json_is_package', importlib.util.find_spec('json').submodule_search_locations is not None)
```

<OutputBox title='原理验证' output='py 3 13\nmeta_path [&#39;BuiltinImporter&#39;, &#39;FrozenImporter&#39;, &#39;PathFinder&#39;]\nfinder_sig (fullname, path=None, target=None)\npyc demo.cpython-313.pyc\njson_is_package True' />


## ModuleSpec、Loader 与 exec_module 的加载时序

`ModuleSpec` 自 3.4 引入，字段含 `name`、`loader`、`origin`、`submodule_search_locations`（包非 `None`）、`has_location`、`cached`。

loader 实现两个方法：`create_module(spec)` 返回模块对象或 `None`，`None` 表示用 `module_from_spec` 走默认创建；

`exec_module(module)` 在模块的 `__dict__` 命名空间里执行代码，这是 3.4+ 的正式入口，旧 `load_module()` 自 3.4 起被弃用、只留作遗留兼容。

`origin` 只是给人看与给调试器定位的字符串，可写成 `memory:xxx` 之类的自定义值。

字节码缓存落在 `__pycache__/m.cpython-313.pyc`，标签来自 `sys.implementation.cache_tag`；

默认按源文件 mtime 加大小校验（PEP 552 另支持 checked-hash / unchecked-hash 的 hash-based pyc），所以同一秒内改动且字节数不变可能不触发重编。

`sys.dont_write_bytecode` 默认 `False`，`PYTHONDONTWRITEBYTECODE=1` 或 `-B` 可关写入，`sys.pycache_prefix` 能把缓存重定向。

`find_spec` 与目录清单都有缓存，动态新建文件后要 `importlib.invalidate_caches()`。

**ModuleSpec 关键字段（3.4+）**

| 字段 | 含义 | 典型值 |
| --- | --- | --- |
| name | 完整模块名 | pkg.sub |
| loader | 实现 exec_module 的对象 | SourceFileLoader 或自定义 Loader |
| origin | 来源标识，供定位与展示 | 绝对路径或 memory:xxx |
| submodule_search_locations | 包的搜索路径；非包为 None | 包的 list，命名空间包为 _NamespacePath |
| has_location | origin 是否可作文件系统的路径 | 普通 .py 为 True |
| cached | 字节码缓存位置 | __pycache__/m.cpython-313.pyc |


## 用自定义 finder 拦下虚拟模块

```python
import sys
import importlib.abc
import importlib.util

class MemoryLoader(importlib.abc.Loader):
    def __init__(self, source):
        self.source = source
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        exec(self.source, module.__dict__)

class MemoryFinder(importlib.abc.MetaPathFinder):
    def __init__(self, sources):
        self.sources = sources
    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.sources:
            return importlib.util.spec_from_loader(
                fullname, MemoryLoader(self.sources[fullname]),
                origin='memory:' + fullname)
        return None

SOURCES = {'virtual_cfg': 'TIMEOUT = 3' + chr(10) + 'RETRIES = 2'}
sys.meta_path.insert(0, MemoryFinder(SOURCES))

import virtual_cfg
print(virtual_cfg.TIMEOUT, virtual_cfg.RETRIES)
print(virtual_cfg.__spec__.origin, type(virtual_cfg.__loader__).__name__)
print('virtual_cfg' in sys.modules)
```

<OutputBox title='主示例运行结果' output='3 2\nmemory:virtual_cfg MemoryLoader\nTrue' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys\nimport importlib.abc\nimport importlib.util\n\nclass MemoryLoader(importlib.abc.Loader):\n    def __init__(self, source):\n        self.source = source\n    def create_module(self, spec):\n        return None\n    def exec_module(self, module):\n        exec(self.source, module.__dict__)\n\nclass MemoryFinder(importlib.abc.MetaPathFinder):\n    def __init__(self, sources):\n        self.sources = sources\n    def find_spec(self, fullname, path=None, target=None):\n        if fullname in self.sources:\n            return importlib.util.spec_from_loader(\n                fullname, MemoryLoader(self.sources[fullname]),\n                origin=&#39;memory:&#39; + fullname)\n        return None\n\nSOURCES = {&#39;virtual_cfg&#39;: &#39;TIMEOUT = 3&#39; + chr(10) + &#39;RETRIES = 2&#39;}\nsys.meta_path.insert(0, MemoryFinder(SOURCES))\n\nimport virtual_cfg\nprint(virtual_cfg.TIMEOUT, virtual_cfg.RETRIES)\nprint(virtual_cfg.__spec__.origin, type(virtual_cfg.__loader__).__name__)\nprint(&#39;virtual_cfg&#39; in sys.modules)' :notes='["导入 sys，读取与改写 meta_path 和 modules", "导入 importlib.abc，取 Loader 与 MetaPathFinder 基类", "导入 importlib.util，用 spec_from_loader 构造 ModuleSpec", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 Loader：exec_module 负责执行模块代码", "构造时保存源码字符串", "把源码挂到实例上，供 exec_module 取用", "create_module 是 3.4+ 的可选钩子", "返回 None 让解释器用 module_from_spec 建空模块", "exec_module 取代旧 load_module，是正式加载入口", "在模块的 __dict__ 命名空间里执行源码", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 MetaPathFinder，实例挂到 sys.meta_path", "保存 模块名到源码 的映射", "注册表内容存到实例", "find_spec 由导入机按 meta_path 顺序逐一调用", "只接管注册表里登记过的名字", "spec_from_loader 构造 ModuleSpec", "把源码包进自定义 Loader 一并交给 spec", "origin 标成 memory:，说明不是磁盘文件", "未登记的名字返回 None，交给后续 finder", "空行，只用于分隔逻辑块，不影响执行结果。", "源码用 chr(10) 拼换行，规避反斜杠转义", "插到 meta_path[0]，优先于 BuiltinImporter", "空行，只用于分隔逻辑块，不影响执行结果。", "import 先查 sys.modules 未命中，才走 finder 链", "模块代码已被 exec_module 执行，两个常量可用", "__spec__.origin 与 __loader__ 类型证明走自定义链路", "导入结束后名字写入 sys.modules，重复 import 不再执行"]' title='第 055 讲 · 导入系统源码级：finder、loader 与缓存' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 对照：手动塞 sys.modules 与 reload

```python
import sys
import types
import importlib

name = '_cfg_demo_55'
m = types.ModuleType(name)
m.VALUE = 1
sys.modules[name] = m
print('manual', importlib.import_module(name) is m, m.VALUE)
m.VALUE = 99
print('cached', importlib.import_module(name).VALUE)
sys.modules['_blocked_55'] = None
try:
    importlib.import_module('_blocked_55')
except ModuleNotFoundError as e:
    print(type(e).__name__, 'halted' in str(e))
```

<OutputBox title='对照写法：先自己猜，再点开' output='manual True 1\ncached 99\nModuleNotFoundError True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import sys\nimport importlib.abc\nimport importlib.util\n\nclass MemoryLoader(importlib.abc.Loader):\n    def __init__(self, source):\n        self.source = source\n    def create_module(self, spec):\n        return None\n    def exec_module(self, module):\n        exec(self.source, module.__dict__)\n\nclass MemoryFinder(importlib.abc.MetaPathFinder):\n    def __init__(self, sources):\n        self.sources = sources\n    def find_spec(self, fullname, path=None, target=None):\n        if fullname in self.sources:\n            return importlib.util.spec_from_loader(\n                fullname, MemoryLoader(self.sources[fullname]),\n                origin=&#39;memory:&#39; + fullname)\n        return None\n\nSOURCES = {&#39;virtual_cfg&#39;: &#39;TIMEOUT = 3&#39; + chr(10) + &#39;RETRIES = 2&#39;}\nsys.meta_path.insert(0, MemoryFinder(SOURCES))\n\nimport virtual_cfg\nprint(virtual_cfg.TIMEOUT, virtual_cfg.RETRIES)\nprint(virtual_cfg.__spec__.origin, type(virtual_cfg.__loader__).__name__)\nprint(&#39;virtual_cfg&#39; in sys.modules)", "note": "sys.meta_path 的三段查找与 Finder 协议"}, {"label": "对照 / 进阶", "code": "import sys\nimport types\nimport importlib\n\nname = &#39;_cfg_demo_55&#39;\nm = types.ModuleType(name)\nm.VALUE = 1\nsys.modules[name] = m\nprint(&#39;manual&#39;, importlib.import_module(name) is m, m.VALUE)\nm.VALUE = 99\nprint(&#39;cached&#39;, importlib.import_module(name).VALUE)\nsys.modules[&#39;_blocked_55&#39;] = None\ntry:\n    importlib.import_module(&#39;_blocked_55&#39;)\nexcept ModuleNotFoundError as e:\n    print(type(e).__name__, &#39;halted&#39; in str(e))", "note": "ModuleSpec、Loader 与 pyc 失效规则"}]' title='两种写法切换看' />


## 循环导入与命名空间包的加载时序

循环导入报错的根因是加载时序：模块 a 执行到 `import b` 时被挂起，此时 a 已写入 `sys.modules` 但只初始化了一部分；

b 反向 `from a import NAME`，拿到的正是这个半初始化模块，若 `NAME` 定义在 `import b` 之后，就抛 `ImportError`，提示无法从未完成初始化的模块导入名字。

三种修复：把导入挪进函数体延迟到调用时、把公共依赖抽到第三个模块、或改成 `import a` 后以 `a.NAME` 访问（只读模块对象，不要求属性此刻就绪）。

命名空间包（PEP 420）是没有 `__init__.py` 的目录，`spec.origin` 为 `None`，`submodule_search_locations` 是运行时重算的 `_NamespacePath`，因此运行时往 `sys.path` 追加目录也能发现新子模块；

3.11+ 由 `_NamespaceLoader` 接管。

自定义 `import hook` 对加密模块、远程模块、插件注册表很有用，代价是进入每次导入的关键路径，增加冷启动耗时，还会让静态分析器与 `find_spec` 的结果不一致，生产上必须配日志与降级路径。


## 从 3.4 到 3.13 的导入系统版本线

**导入系统版本差异与排查提示**

| 版本 | 变化 | 对写法的影响 |
| --- | --- | --- |
| 3.4 | 引入 ModuleSpec 与 exec_module，load_module 弃用 | 新 hook 只写 create_module / exec_module |
| 3.4 | PEP 420 命名空间包（可无 __init__.py） | spec.origin 为 None，路径运行时重算 |
| 3.7 | importlib.resources 读取包内资源 | 不要用 __file__ 拼资源路径 |
| 3.8 | importlib.metadata 读发行包元数据 | 替代 pkg_resources 查版本 |
| 3.11 | 命名空间包改由 _NamespaceLoader 接管 | 自定义 finder 要正确处理 origin=None |
| 3.13 | cache_tag 为 cpython-313，pyc 名随之变化 | 多版本解释器共用目录须清 __pycache__ |

<FlowTimeline :steps='[{"title": "sys.meta_path 的三段查找与 Fin…", "desc": "`import x` 会编译成 `IMPORT_NAME` 字节码，运行时调内建…", "tone": "blue"}, {"title": "ModuleSpec、Loader 与 pyc…", "desc": "`ModuleSpec` 自 3.4 引入，字段含 `name`、`loader`…", "tone": "purple"}, {"title": "循环导入、命名空间包与 hook 的代价", "desc": "循环导入报错的根因是加载时序：模块 a 执行到 `import b` 时被挂起，此时…", "tone": "orange"}, {"title": "工程落地", "desc": "配置插件注册表：把字典加载成可 import 的模块", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## _find_and_load 为什么先写缓存再执行

CPython 的导入逻辑由冻结进解释器的 `importlib._bootstrap` 实现，核心是 `_find_and_load_unlocked`：先以模块名为键查 `sys.modules`，命中即返回，这正是 `importlib.reload` 必须显式绕过缓存重新执行的原因；

未命中则遍历 `sys.meta_path` 调 `find_spec`，拿到 `ModuleSpec` 后用 `module_from_spec` 建空模块、先写入 `sys.modules`、再调 `loader.exec_module` 填充，最后从缓存取值返回。

先把模块对象写进缓存再执行，是为了让循环导入能拿到「已存在但可能半初始化」的模块而不是无限递归，这恰好是 partially initialized module 报错的根源。每条 `import` 语句编译为 `IMPORT_NAME` 字节码，运行时调内建 `__import__`。

`PathFinder` 借助 `sys.path_hooks`（默认 `zipimporter` 与 `FileFinder.path_hook`）把每个 `sys.path` 条目映射成 finder，结果缓存在 `sys.path_importer_cache`；

`FileFinder` 在目录内按扩展名探测并生成带 `SourceFileLoader` 的 spec。

pyc 用 `marshal` 序列化 code object，头部记 magic number、标志位与源 mtime / 大小，加载时比对决定是否复用。

<Term word='sys.meta_path 与 path_hooks' text='`import x` 会编译成 `IMPORT_NAME` 字节码，运行时调内建 `__import__`，落到 `importlib._bootstrap._find_and_load`：先以模块名查 `sys.modules`，命中且值非 `None` 就直接返回。未命中则按序遍历 `sys.meta_path`…' />

<Term word='Finder / Loader 协议' text='`ModuleSpec` 自 3.4 引入，字段含 `name`、`loader`、`origin`、`submodule_search_locations`（包非 `None`）、`has_location`、`cached`。loader 实现两个方法：`create_module(spec)` 返回模块对象或…' />


## 配置插件注册表：把字典加载成可 import 的模块

一个灰度系统希望把规则以源码字符串形式存在配置中心，进程启动后注册成模块供业务代码 `import`，而不是往镜像里塞一堆 `.py` 文件。直接写文件再 `append` 到 `sys.path` 有缓存失效与并发写同一目录的问题；

用 `import hook` 更干净：一个 `MetaPathFinder` 只认注册表里的名字，一个 `Loader` 在 `exec_module` 里取源码并 `compile` 到模块的 `__dict__`。因为 `find_spec` 会被多个导入线程调用，注册表读取用 `Lock` 保护；

`origin` 写成 `registry:` 前缀，日志里一眼能看出模块不是来自磁盘。这个结构也就是插件系统、加密模块分发、远程模块的最小骨架，真实项目再加签名校验、版本字段与加载失败降级。

```python
import sys
import importlib.abc
import importlib.util
import threading

class RegistryLoader(importlib.abc.Loader):
    def __init__(self, registry, lock):
        self.registry = registry
        self.lock = lock
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        with self.lock:
            source = self.registry[module.__spec__.name]
        exec(compile(source, module.__spec__.origin, 'exec'), module.__dict__)

class RegistryFinder(importlib.abc.MetaPathFinder):
    def __init__(self, registry, lock):
        self.registry = registry
        self.lock = lock
    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.registry:
            return importlib.util.spec_from_loader(
                fullname, RegistryLoader(self.registry, self.lock),
                origin='registry:' + fullname)
        return None

def install(registry):
    lock = threading.Lock()
    sys.meta_path.insert(0, RegistryFinder(registry, lock))

if __name__ == '__main__':
    reg = {
        'cfg_limit': 'LIMIT = 10' + chr(10) + 'def allow(n): return n <= LIMIT',
        'cfg_tags': "TAGS = ('a', 'b')",
    }
    install(reg)
    import cfg_limit
    import cfg_tags
    print(cfg_limit.allow(7), cfg_limit.allow(99))
    print(cfg_tags.TAGS, 'cached', 'cfg_tags' in sys.modules)
```

<Callout type="idea" title='落地提示' text='插件式加载、加密模块、远程模块可用 import hook 实现；但要先评估对启动时间与可调试性的影响' />

<CheckList id='P055b' title='上线前自检' :items='["能复现并解释「运行时生成新模块后 import 仍报 ModuleNotF…」", "能复现并解释「包 __init__.py 里 from . import…」", "能复现并解释「改了 .py 但进程里行为没变」", "能用一条命令验证 sys.meta_path 与 path_hooks", "关键路径有自动化测试与失败分支"]' />

```bash
python -X importtime -c "import json" 2>&1 | tail -4
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 `sys.meta_path` 与 path_hooks 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

<SequenceDiagram title='第 055 讲 · 调用时序' caption='从触发到收尾，标出最可能失败的两个位置' :actors='["调用方", "核心逻辑", "外部依赖"]' :steps='[{"from": "调用方", "to": "核心逻辑", "label": "发起调用", "note": "sys.meta_path…", "kind": "call"}, {"from": "核心逻辑", "to": "核心逻辑", "label": "检查前置", "note": "ModuleSpec、Loa…", "kind": "self"}, {"from": "核心逻辑", "to": "外部依赖", "label": "读取资源", "note": "可能超时", "kind": "call"}, {"from": "外部依赖", "to": "核心逻辑", "label": "返回结果", "note": "或抛异常", "kind": "return"}, {"from": "核心逻辑", "to": "调用方", "label": "返回或降级", "note": "清理资源", "kind": "return"}]' />


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 运行时生成新模块后 import 仍报 ModuleNotFoundError | PathFinder 缓存了目录清单与 FileFinder 实例，新文件不会自动进入视野 | 调用 importlib.invalidate_caches() 再导入；或把自定义 finder 插入 sys.meta_path[0] 直接接管 |
| 包 __init__.py 里 from . import sub 偶发 partially initialized 报错 | 循环导入时模块已进 sys.modules，但被需要的属性还没定义到 | 把子模块导入挪进函数体、抽公共依赖到第三模块，或改成 import pkg 后按 pkg.attr 访问 |
| 改了 .py 但进程里行为没变 | pyc 按 mtime 加大小校验，同秒同大小改动不失效；且进程内 sys.modules 不会重新执行 | 核对 __pycache__ 时间戳，用 importlib.invalidate_caches() 与 importlib.reload()，部署前清理旧 pyc |

<Callout type="warn" title='本讲最容易踩的坑' text='运行时生成新模块后 import 仍报 ModuleNotFoundError：PathFinder 缓存了目录清单与 FileFinder 实例，新文件不会自动进入视野' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：运行时生成新模块后 import 仍报 Mo…", "body": "PathFinder 缓存了目录清单与 FileFinder 实例，新文件不会自动进入视野", "tip": "调用 importlib.invalidate_caches() 再导入；或把自定义 finder 插入 sys.meta_path[0] 直接接管"}, {"title": "第 2 步：包 __init__.py 里 from .…", "body": "循环导入时模块已进 sys.modules，但被需要的属性还没定义到", "tip": "把子模块导入挪进函数体、抽公共依赖到第三模块，或改成 import pkg 后按 pkg.attr 访问"}, {"title": "第 3 步：改了 .py 但进程里行为没变", "body": "pyc 按 mtime 加大小校验，同秒同大小改动不失效；且进程内 sys.modules 不会重新执行", "tip": "核对 __pycache__ 时间戳，用 importlib.invalidate_caches() 与 importlib.reload()，部署前清理旧 pyc"}]' />


## import.c 与 _bootstrap._find_and_load 的模块锁时序

`import x` 编译成 `IMPORT_NAME`，`ceval.c` 的 import_name 调 Python/`import.c` 的 PyImport_ImportModuleLevelObject，处理相对导入的 level 与 fromlist 后转入冻结模块 `importlib._bootstrap` 的 _find_and_load（源码在 `Lib/importlib/_bootstrap.py`，解释器启动时已冻结进可执行文件）。

时序里有两处数据结构决定行为。第一是模块锁：_bootstrap 用 _module_locks 这个字典给每个模块名配一把 _ModuleLock，外加一把全局 _module_locks_lock 保护字典本身；

_find_and_load 先取锁再加载，同一模块被两个线程同时导入时后到者阻塞，避免 exec_module 跑两遍，并在检测到循环等待时抛 _DeadlockError 而不是挂死。

第二是 `sys.modules` 的写入时机：_load_unlocked 在 module_from_spec 建好空模块后立刻执行 `sys.modules[name] = module`，然后才 `spec.loader.exec_module(module)`。

先登记再执行，是为了让循环导入里的反向 import 能拿到一个已存在的模块对象，从而不触发对该模块的重复加锁；

代价正是正文里那个 partially initialized module，拿到的对象只跑了一半，`from a import NAME` 若 `NAME` 定义在 import 之后就会失败。

exec 抛异常时 except 分支会把该键从 `sys.modules` 删掉，这解释了导入失败后重试能重新加载。_call_with_frames_removed 则让 importlib 自己的帧不出现在 traceback 里。

<Term word='_ModuleLock' text='importlib._bootstrap 为每个模块名分配的一把可重入锁，存在 _module_locks 字典里；并发导入同一模块时后到者等待而非重复执行 exec_module，并通过死锁检测在循环等待时抛 RuntimeError 而不是让解释器挂起。' />


## pyc 文件头 16 字节的 PEP 552 标志

```python
import py_compile
import struct
import tempfile
import os

src = os.path.join(tempfile.mkdtemp(), 'probe_mod.py')
with open(src, 'w') as f:
    f.write('value = 42' + chr(10))
cached = py_compile.compile(src, doraise=True)
with open(cached, 'rb') as f:
    head = f.read(16)
magic, flags, mtime, size = struct.unpack('<4sIII', head)
print('flag bits', flags)
print('mtime nonzero', mtime > 0)
print('source size', size)

```

<OutputBox title='扩展示例运行结果' output='flag bits 0\nmtime nonzero True\nsource size 11' />

<LineByLine code='import py_compile\nimport struct\nimport tempfile\nimport os\n\nsrc = os.path.join(tempfile.mkdtemp(), &#39;probe_mod.py&#39;)\nwith open(src, &#39;w&#39;) as f:\n    f.write(&#39;value = 42&#39; + chr(10))\ncached = py_compile.compile(src, doraise=True)\nwith open(cached, &#39;rb&#39;) as f:\n    head = f.read(16)\nmagic, flags, mtime, size = struct.unpack(&#39;&lt;4sIII&#39;, head)\nprint(&#39;flag bits&#39;, flags)\nprint(&#39;mtime nonzero&#39;, mtime &gt; 0)\nprint(&#39;source size&#39;, size)\n' :notes='["py_compile 负责把源码编译成 __pycache__ 下的 pyc", "struct 用来按小端布局拆开头部 16 字节", "tempfile 造一个隔离目录，避免污染工程目录", "os.path 拼出源文件路径", "空行，只用于分隔逻辑块，不影响执行结果。", "在临时目录里写一个最小源文件", "用 chr(10) 拼换行，示例源码里不出现反斜杠转义", "compile 返回 pyc 路径，doraise=True 让失败直接抛异常", "以二进制读回 pyc，只取头部 16 字节", "read(16) 正好覆盖 magic 加三个 uint32 字段", "按 4sIII 解出 magic、flags、mtime、source size", "flags 为 0 表示 timestamp-based，而非 hash-based", "timestamp 模式下 mtime 必为非零", "source size 是源文件字节数，这里是 11", "这一行 `print(&#39;source size&#39;, size)` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />

**pyc 文件头 16 字节的字段布局**

| 偏移 | 字段 | 字节数 | 含义与失效条件 |
| --- | --- | --- | --- |
| 0-3 | magic number | 4 | importlib.util.MAGIC_NUMBER，版本或字节码格式不符就重编 |
| 4-7 | flags | 4 | PEP 552：bit0 为 hash-based，bit1 为 checked-hash |
| 8-11 | mtime | 4 | timestamp 模式下源文件修改时间，秒级精度 |
| 12-15 | source size | 4 | 源文件字节数，与 mtime 一起做失效校验 |
| 16+ | marshalled code | 变长 | code object 的 marshal 序列化结果 |


## sys.path_importer_cache 与 FileFinder 的目录缓存

PathFinder 并不每次都去读目录。

`Lib/importlib/_bootstrap_external.py` 里 `PathFinder._path_importer_cache(path)` 先查全局的 `sys.path_importer_cache`：键是 `sys.path` 里的条目字符串，值是一个 finder 对象或 None（None 表示这条路径不可用，也会被缓存，避免反复试探）。

未命中时它按 `sys.path_hooks` 依次尝试，默认链里最后是 `FileFinder.path_hook` 构造出的源码、字节码、扩展三类 loader 组合，构造完就写回缓存。

FileFinder 自己还带一层：_path_mtime 记着目录的修改时间，_path_cache 是上一次 `os.listdir` 的结果；只有发现 mtime 变了才重新扫描目录，否则直接在缓存集合里判断 `m.py` 存不存在。

两层缓存叠加正是文件明明写好了却偶发 ModuleNotFoundError 的根因，目录 mtime 在秒级或某些网络文件系统上没变，缓存就认为文件仍不存在。

`importlib.invalidate_caches()` 会遍历 `sys.meta_path` 与 `sys.path_importer_cache`，调用每个 finder 的 `invalidate_caches()`，把 FileFinder 的 mtime 置为 -1，强制下次重新 listdir；

zipimport 的 zip_directory_cache 也走同一套约定。工程上的结论：动态生成模块、插件热加载、sidecar 写配置这几类场景，必须在 import 之前显式调一次，并且给 `sys.path` 追加目录时最好同时清掉该目录在缓存里的旧条目。


### 动态生成模块时 invalidate_caches 的失败复盘

容器里的配置文件由 sidecar 在进程启动后写入 /`etc/app/config.py`，脚本 `import config` 偶发 ModuleNotFoundError，改 `sys.path` 与重拷源码都时好时坏。

复盘发现两条缓存都在起作用：进程在处理更早的 import 时已经为 /etc/app 构造过 FileFinder 并缓存了当时的空目录清单；sidecar 写入太快，目录 mtime 的秒级值没变，FileFinder 便跳过重新 listdir，直接判定文件不存在。

修复不是在业务代码里 sleep 等文件，而是在读取配置前显式 `importlib.invalidate_caches()`，让 FileFinder 把 mtime 置为 -1 后重扫；

更稳妥的做法是给配置注册一个自定义的 MetaPathFinder，把配置的读取完全从路径扫描里摘出来。

下面这段代码把一个临时目录插进 `sys.path`，导入其中的模块，然后检查 `sys.path_importer_cache`：键就是那个目录字符串，值是 FileFinder 实例而不是模块对象。

理解这一点，才能明白 invalidate_caches 清的是 finder 的状态，不是 `sys.modules` 里的模块缓存，两者根本不是一张表。

```python
import importlib
import importlib.machinery
import os
import sys
import tempfile

folder = tempfile.mkdtemp()
with open(os.path.join(folder, 'demo_pkg.py'), 'w') as f:
    f.write('VALUE = 1' + chr(10))
sys.path.insert(0, folder)
importlib.invalidate_caches()
import demo_pkg
print('imported', demo_pkg.VALUE)
finder = sys.path_importer_cache.get(folder)
print('finder type', type(finder).__name__)
print('is FileFinder', isinstance(finder, importlib.machinery.FileFinder))
print('cache key present', folder in sys.path_importer_cache)

```


## 动手练习、自测与一页纸速记

<Exercise title='基础：写一个最小内存模块加载器' task='用 importlib.abc.Loader 与 spec_from_loader 把字符串 &#39;X = 7&#39; 加载成模块 mem_x，打印 X 与 __spec__.origin，并说明 create_module 返回 None 时谁来创建模块对象。' solution='import sys\nimport importlib.abc\nimport importlib.util\n\nclass L(importlib.abc.Loader):\n    def create_module(self, spec):\n        return None\n    def exec_module(self, module):\n        exec(&#39;X = 7&#39;, module.__dict__)\n\nclass F(importlib.abc.MetaPathFinder):\n    def find_spec(self, fullname, path=None, target=None):\n        if fullname == &#39;mem_x&#39;:\n            return importlib.util.spec_from_loader(fullname, L(), origin=&#39;mem:mem_x&#39;)\n        return None\n\nsys.meta_path.insert(0, F())\nimport mem_x\nprint(mem_x.X, mem_x.__spec__.origin)' explain='create_module 返回 None 时，导入机用 module_from_spec 依据 spec 建空模块，再调 exec_module 填充 __dict__；origin 是自定义字符串，不要求是磁盘路径。' />

<Exercise title='进阶：复现并修复循环导入' task='建两个临时模块 a、b：a 在顶层先定义 LATE 再 import b 之外，故意把 LATE 定义放在 import b 之后；b 里 from a import LATE。用 spec_from_loader 注入，观察错误信息，再把导入改成函数内延迟导入验证修复。' solution='import sys\nimport importlib.abc\nimport importlib.util\n\nsrc = {\n    &#39;a&#39;: &#39;import b&#39; + chr(10) + &#39;LATE = 1&#39;,\n    &#39;b&#39;: &#39;from a import LATE&#39;,\n}\nclass L(importlib.abc.Loader):\n    def __init__(self, s): self.s = s\n    def create_module(self, spec): return None\n    def exec_module(self, m): exec(self.s, m.__dict__)\nclass F(importlib.abc.MetaPathFinder):\n    def find_spec(self, fullname, path=None, target=None):\n        if fullname in src:\n            return importlib.util.spec_from_loader(fullname, L(src[fullname]))\n        return None\nsys.meta_path.insert(0, F())\ntry:\n    import a\nexcept ImportError as e:\n    print(type(e).__name__, &#39;partially initialized&#39; in str(e))' explain='a 执行 import b 时已进 sys.modules，但 LATE 那行还没轮到；b 的 from a import LATE 读到半初始化模块，报 ImportError。把 import b 移到函数体或抽公共模块即可消除。' />

<Quiz no='055-1' q='import 一个模块时，sys.meta_path 上的 finder 按什么规则决定胜负？' :options='["按列表顺序逐个调 find_spec，第一个返回非 None 的 ModuleSpec 胜出", "按模块名字母序选择 finder", "所有 finder 都执行 exec_module，最后合并结果", "只调用 sys.meta_path[0]，其余跳过"]' answer="0" explain='默认顺序是 BuiltinImporter、FrozenImporter、PathFinder；某个 finder 返回 None 表示不接管，交给下一个，全部落空才抛 ModuleNotFoundError。' />

<Quiz no='055-2' q='关于 sys.modules，下面哪项准确？' :options='["命中且值非 None 会直接返回缓存模块，不再执行任何加载代码", "每次 import 都会重新执行模块顶层代码", "值为 None 的条目会被当作空模块正常返回", "reload 会先删除 sys.modules 条目再走完整查找"]' answer="0" explain='_find_and_load 先查缓存；把条目设为 None 会让导入抛 ModuleNotFoundError（消息含 halted; None in sys.modules）；reload 是绕过缓存重新 exec，不删除条目。' />

<Quiz no='055-3' q='默认 pyc 失效校验依据是什么？' :options='["源文件 mtime 加大小，二者都变才判定失效", "只比对文件内容的哈希", "每次启动无条件重编", "按进程启动时间判断"]' answer="0" explain='默认 timestamp-based pyc 记录源 mtime 与大小；同秒同大小改动可能不触发重编。PEP 552 另提供 checked-hash / unchecked-hash 模式。' />

<Predict no='055-4' q='把某模块名在 sys.modules 里手动设为 None，再 importlib.import_module 它，会发生什么？' :options='["抛 ModuleNotFoundError，消息含 halted; None in sys.modules", "返回一个空模块对象", "正常从磁盘重新加载该模块", "抛 AttributeError"]' answer='0' output='ModuleNotFoundError: import of _blocked_55 halted; None in sys.modules' explain='_find_and_load_unlocked 发现缓存值是 None 时主动抛 ModuleNotFoundError 阻止加载，这是导入锁与循环导入防护的一部分，常被用作「禁止导入」的占位技巧。' />

<FillBlank no='055-5' tpl='___ sys' :answers='["import"]' hint='回想本讲关于 sys.meta_path 与 path_hooks 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 sys.meta_path 的三段查找与 Finder 协议 的落点。' />

<KnowledgeCard :points='["导入链路：IMPORT_NAME → __import__ → _find_and_load → 查 sys.modules → 遍历 sys.meta_path 的 find_spec", "默认 meta_path 顺序：BuiltinImporter / FrozenImporter / PathFinder；返回 None 表示交给下一个", "ModuleSpec 自 3.4 起承载 name/loader/origin/submodule_search_locations；exec_module 取代 load_module", "模块对象先写入 sys.modules 再执行，是循环导入能拿到半初始化模块、也是 partially initialized 报错的根源", "pyc 默认按 mtime+大小校验，文件名含 cache_tag（3.13 为 cpython-313）；动态文件要 invalidate_caches()", "命名空间包（PEP 420）无 __init__.py、origin 为 None；import hook 会拖慢每次导入，须配降级"]' :pitfalls='["运行时生成新模块后 import 仍报 ModuleNotFoundError", "包 __init__.py 里 from . import sub 偶发 partially initialized 报错", "改了 .py 但进程里行为没变", "在包 __init__ 里反向导入子模块，很容易撞上半初始化状态，报出看似无关的 AttributeError"]' summary='导入不是简单的文件读取：meta_path 上的 finder 依次尝试，loader 负责创建并执行模块，全过程围绕 sys.modules 做缓存' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 导入链路：IMPORT_NAME → __import__ → _find_and_load → 查 sys.modules → 遍历 sys.meta_path 的 find_spec | 建立直觉 |
| 默认 meta_path 顺序：BuiltinImporter / FrozenImporter / PathFinder；返回 None 表示交给下一个 | 跑通示例 |
| ModuleSpec 自 3.4 起承载 name/loader/origin/submodule_search_locations；exec_module 取代 load_module | 深入边界 |
| 模块对象先写入 sys.modules 再执行，是循环导入能拿到半初始化模块、也是 partially initialized 报错的根源 | 工程落地 |
| pyc 默认按 mtime+大小校验，文件名含 cache_tag（3.13 为 cpython-313）；动态文件要 invalidate_caches() | 随堂检测 |
| 命名空间包（PEP 420）无 __init__.py、origin 为 None；import hook 会拖慢每次导入，须配降级 | 复盘 |

1. 导入链路：IMPORT_NAME → __import__ → _find_and_load → 查 sys.modules → 遍历 sys.meta_path 的 find_spec

2. 默认 meta_path 顺序：BuiltinImporter / FrozenImporter / PathFinder；返回 None 表示交给下一个

3. ModuleSpec 自 3.4 起承载 name/loader/origin/submodule_search_locations；exec_module 取代 load_module

[下一讲：属性访问链路与 __getattribute__](/core/attribute-lookup)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/055-import-system.py`

```bash
python3 examples/lessons/055-import-system.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/055-import-system.py) · [全部示例代码索引](/examples/)
