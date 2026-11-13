---
title: 第 035 讲 · 模块与包：import 机制与循环导入
description: 能诊断导入失败与命名冲突
---

<StageHeader stage='L3 · 函数与抽象' level='★★★☆☆' time='35 分钟' goal='能诊断导入失败与命名冲突' prereq='第 034 讲 · 偏函数、可调用对象与函数式工具' />

# 第 035 讲 · 模块与包：import 机制与循环导入

函数这一层搭得差不多，代码一多，问题就转到它们该放在哪、又怎样被找到。模块与包决定名字的可见范围与加载次序，是从单文件走向可协作工程的门槛：一个配置模块本该只放常量，却在顶层连了库、起了线程，别的测试只想导入一下就卡住；两个文件互相引用，报错又指向一个还没初始化完的模块。

我们先跟着一次 `import` 走一遍：缓存、搜索路径与加载器怎样配合，模块为何天然是单例；再看包内相对导入与 `__init__` 的导出约定；最后归结到循环导入的成因，以及把共享部分下沉到独立模块的办法。需要你已经习惯把函数分文件存放；走完你能判断是哪一步出了岔，而不是靠挪动 `import` 碰运气。


## 只是 import 一下，进程却连了库、起了线程

一个配置模块 `config.py` 里除了定义常量，还在顶层连了数据库、起了个后台线程，结果单元测试只是 `import config` 就把连接建起来、进程卡住不退出。

更头疼的是 `a.py` 顶层 `from b import B`、`b.py` 顶层 `from a import A` 互相导入，一运行就报 `partially initia…` 和 `most likely due…`，团队只能把 `import` 挪来挪去碰运气。

```text
partially initialized module
most likely due to a circular import
```

有人图省事，在每个函数里到处重复导入，或往 `sys.path` 里乱塞路径，反而制造出同一模块被加载两份的新问题。

本讲把 `import` 的真实流程讲清楚：`sys.modules` 缓存、`finder` 与 `loader` 的分工、搜索路径、`__init__` 与 `__all__`、命名空间包，以及循环导入的成因和四种根治办法。

<Callout type="warn" title='先看一个真实会出错的写法' text='只是 import 一下配置模块，却连了库、起了线程、进程不退出：模块顶层代码在导入时执行一次，副作用不受 main 守卫保护' />


## import 的执行链路与模块单例

`import X` 先查 `sys.modules`（一张以完整模块名为键的 dict），命中就直接返回同一个 module 对象；

未命中才交给 `sys.meta_path` 里的 finder 依次尝试（`BuiltinImporter`、`FrozenImporter`、`PathFinder`），`PathFinder` 沿 `sys.path` 搜索，loader 创建 module 对象、执行顶层代码，再存回 `sys.modules`。

正因为有缓存，模块天然是单例：第二次 `import` 不会重新执行顶层代码，要重跑得用 `importlib.reload(mod)`。

模块对象的属性来自它的顶层命名空间 `__dict__`，`__name__`、`__file__`、`__package__`、`__spec__` 由 loader 填充，包还额外带 `__path__` 供继续搜索子模块。

`sys.path` 的顺序是入口脚本所在目录（或空字符串表示当前工作目录）→ `PYTHONPATH` → 标准库 → `site-packages`，`sys.path[0]` 是脚本目录，这也是随手写一个 `random.py` 就能把标准库 `random` 遮蔽掉的根因。

顶层代码在导入时执行一次，所以连接、线程、打印这类副作用，仅仅 `import` 一下就会触发；

把可执行入口收进 `if __name__ == '__main__':` 守卫是基本纪律。

需要动态导入时用 `importlib.import_module('pkg.mod')`，它的底层函数是 `__import__`。

```python
import sys, importlib, types

first = importlib.import_module('json')
second = importlib.import_module('json')
print(first is second, 'json' in sys.modules)
print(type(first).__name__, first.__name__)
print(first.__spec__.name, hasattr(first, '__file__'))

m = types.ModuleType('demo')
m.value = 42
sys.modules['demo'] = m
import demo
print(demo.value, demo is m, demo.__name__)
print(demo.__dict__ is m.__dict__)
```

<OutputBox title='主示例运行结果' output='True True\nmodule json\njson True\n42 True demo\nTrue' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sys, importlib, types\n\nfirst = importlib.import_module(&#39;json&#39;)\nsecond = importlib.import_module(&#39;json&#39;)\nprint(first is second, &#39;json&#39; in sys.modules)\nprint(type(first).__name__, first.__name__)\nprint(first.__spec__.name, hasattr(first, &#39;__file__&#39;))\n\nm = types.ModuleType(&#39;demo&#39;)\nm.value = 42\nsys.modules[&#39;demo&#39;] = m\nimport demo\nprint(demo.value, demo is m, demo.__name__)\nprint(demo.__dict__ is m.__dict__)' :notes='["导入 sys 读缓存、importlib 做动态导入、types 造模块对象", "第一次导入 json 并触发加载", "第二次导入同名的 json", "两次拿到同一个对象，且 json 已在 sys.modules 里", "模块对象的类型是 module，__name__ 为 json", "__spec__.name 是 json，普通模块有 __file__", "手动造一个名为 demo 的模块对象", "给它写一个自定义属性 value", "提前把对象放进 sys.modules 模拟已被加载", "import demo 直接命中缓存、绑定到本地名字", "取到 value，且 demo 就是我们放进去的那个对象", "模块对象的 __dict__ 与手动对象完全相同"]' title='第 035 讲 · 模块与包：import 机制与循环导入' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**import 的执行链路与关键对象**

| 步骤 | 对象 / 字段 | 作用 |
| --- | --- | --- |
| 查缓存 | sys.modules（dict） | 命中直接返回同一 module 对象，保证单例 |
| 找 finder | sys.meta_path 列表 | BuiltinImporter / FrozenImporter / PathFinder 依次尝试 |
| 搜路径 | sys.path | 脚本目录 → PYTHONPATH → 标准库 → site-packages |
| 加载执行 | loader.exec_module | 创建 module 对象、执行顶层代码、填 __dict__ |
| 填元数据 | __name__ / __file__ / __package__ / __spec__ | 包才有 __path__；命名空间包 __file__ 为 None |


### sys.modules、finder 与 loader 的分工

`import` 的核心是 `sys.modules` 这个全局字典加上一套 finder / loader 协议。

执行 `import X` 时，`_bootstrap._find_and_load` 先查 `sys.modules['X']`；

命中就直接返回，未命中则在把占位 module 对象插入 `sys.modules` 之后才调用 loader 执行顶层代码，这个先入缓存再执行的顺序正是循环导入能拿到半成品模块的根本原因。

loader 把顶层名字写进 `module.__dict__`，`__spec__`（`ModuleSpec`）记录 name、loader、origin、submodule_search_locations，`__package__` 决定相对导入的解析基准，包还会带 `__path__` 供继续搜索子模块。

`PathFinder` 依次遍历 `sys.path` 的每个条目，用 `FileFinder` 找 `.py` / `.pyc` / 目录；PEP 420 的命名空间包在没有 `__init__.py` 时把多个匹配目录收集成 `_NamespacePath`，因而 `__file__` 为 `None`。

第二次 `import` 不重新执行，除非 `importlib.reload` 明确要求。

理解缓存与执行顺序，就知道为什么顶层副作用危险、为什么循环导入报 `partially initialized`。

<ConceptDiagram type='layers3' title='第 035 讲 · 分层视角' labels='import 的执行链路与模块单例|包、相对导入与命名空间包|循环导入的成因与根治|命名空间包' caption='循环导入的成因与根治' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 命名空间包 落在哪一层。


## 模块对象为什么是天然单例

<Callout type="tip" title='核心心智模型' text='`import X` 先查 `sys.modules`（一张以完整模块名为键的 dict），命中就直接返回同一个 module 对象；未命中才交给 `sys.meta_path` 里的 finder 依次尝试（`BuiltinImporter`、`FrozenImporter`、`PathFinde' />

```python
import sys, importlib

mod = importlib.import_module('json')
print(type(mod.__loader__).__name__, mod.__spec__.name)
print(mod.__spec__.origin is not None)
print('PathFinder' in [m.__name__ for m in sys.meta_path])
print(sys.modules['json'] is mod, importlib.import_module('json') is mod)
```

<OutputBox title='原理验证' output='SourceFileLoader json\nTrue\nTrue\nTrue True' />

<FlowTimeline :steps='[{"title": "import 的执行链路与模块单例", "desc": "`import X` 先查 `sys.modules`（一张以完整模块名为键的 di…", "tone": "blue"}, {"title": "包、相对导入与命名空间包", "desc": "常规包是含 `__init__.py` 的目录，导入包时先执行 `__init__.…", "tone": "purple"}, {"title": "循环导入的成因与根治", "desc": "循环导入是 a 与 b 互相 `import`，且至少一方在顶层就要用到对方尚未定义…", "tone": "orange"}, {"title": "工程落地", "desc": "复现循环导入，并把共享类型下沉到独立模块", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />

<Term word='模块对象与 sys.modules' text='`import X` 先查 `sys.modules`（一张以完整模块名为键的 dict），命中就直接返回同一个 module 对象；未命中才交给 `sys.meta_path` 里的 finder 依次尝试（`BuiltinImporter`、`FrozenImporter`、`PathFinder`），`PathF' />

<Term word='搜索路径与 finder' text='常规包是含 `__init__.py` 的目录，导入包时先执行 `__init__.py`，它的顶层名字成为包的属性；`__all__` 是一个字符串列表，控制 `from pkg import *` 导出哪些名字，不定义时导出所有不以单下划线开头的名字。绝对导入 `import pkg.mod` 从 `sys.pat' />


## 包、相对导入与命名空间包

常规包是含 `__init__.py` 的目录，导入包时先执行 `__init__.py`，它的顶层名字成为包的属性；

`__all__` 是一个字符串列表，控制 `from pkg import *` 导出哪些名字，不定义时导出所有不以单下划线开头的名字。

绝对导入 `import pkg.mod` 从 `sys.path` 顶层开始找；

相对导入 `from . import x`、`from ..pkg import y` 基于当前模块的 `__package__` 解析，只能在包内使用，直接运行的脚本里用相对导入会报 `ImportError: att…`。

```python
ImportError: attempted relative import with no known parent package
```

PEP 420（3.3+）引入命名空间包：没有 `__init__.py` 的目录也能成为包，用来把同名包分散到多个分发单元，它的 `__path__` 是 `_NamespacePath`、`__file__` 为 `None`。常见陷阱有三个：包内混用绝对与相对导入，导致同一模块以两个名字各加载一份；

把测试脚本放进包目录却直接运行；随意往 `sys.path` 插入路径，导入到错误的副本。用 `python -m` 运行包内模块会正确设置 `__package__`，相对导入才能生效，这和直接执行 `pkg/mod.py` 的差别就在这里。

**包、相对导入与命名空间包**

| 形式 | 规则 | 常见错误 |
| --- | --- | --- |
| 常规包 | 目录含 __init__.py，导入时先执行它 | __init__.py 顶层副作用在导入时触发 |
| __all__ | 字符串列表，控制 from pkg import * | 未定义时导出所有不以 _ 开头的名字 |
| 相对导入 from . import x | 基于 __package__ 解析，仅包内可用 | 脚本直接运行报 ImportError: attempted relative import with no known parent package |
| 命名空间包（PEP 420, 3.3+） | 无 __init__.py 也能成包，__path__ 是 _NamespacePath | __file__ 为 None，靠多路径拼接 |
| 绝对导入 | 从 sys.path 顶层开始找 | 本地同名文件会遮蔽标准库 |

```python
import sys, tempfile, pathlib, importlib

root = tempfile.mkdtemp()
p = pathlib.Path(root)
(p / 'pkg').mkdir()
(p / 'pkg' / '__init__.py').write_text('from .mod import VALUE' + chr(10) + '__all__ = ' + str(['VALUE']) + chr(10))
(p / 'pkg' / 'mod.py').write_text('VALUE = 99' + chr(10))
sys.path.insert(0, root)
import pkg
print(pkg.VALUE, pkg.__all__)
print(pkg.__file__ is not None, 'pkg.mod' in sys.modules)
sys.path.remove(root)
```

<OutputBox title='对照写法：先自己猜，再点开' output='99 [&#39;VALUE&#39;]\nTrue True' guess="true" />

<Predict no='035-1' q='print(importlib.import_module(&#39;json&#39;) is importlib.import_module(&#39;json&#39;)) 输出什么？' :options='["True", "False", "抛 TypeError"]' answer='0' output='True' explain='两次调用命中 sys.modules 里同一个 json 模块对象，身份比较为真，这正是模块天然单例的直接证据。' />


### __init__、__all__ 与相对导入的解析

<CodeTabs :tabs='[{"label": "主示例", "code": "import sys, importlib, types\n\nfirst = importlib.import_module(&#39;json&#39;)\nsecond = importlib.import_module(&#39;json&#39;)\nprint(first is second, &#39;json&#39; in sys.modules)\nprint(type(first).__name__, first.__name__)\nprint(first.__spec__.name, hasattr(first, &#39;__file__&#39;))\n\nm = types.ModuleType(&#39;demo&#39;)\nm.value = 42\nsys.modules[&#39;demo&#39;] = m\nimport demo\nprint(demo.value, demo is m, demo.__name__)\nprint(demo.__dict__ is m.__dict__)", "note": "import 的执行链路与模块单例"}, {"label": "对照 / 进阶", "code": "import sys, tempfile, pathlib, importlib\n\nroot = tempfile.mkdtemp()\np = pathlib.Path(root)\n(p / &#39;pkg&#39;).mkdir()\n(p / &#39;pkg&#39; / &#39;__init__.py&#39;).write_text(&#39;from .mod import VALUE&#39; + chr(10) + &#39;__all__ = &#39; + str([&#39;VALUE&#39;]) + chr(10))\n(p / &#39;pkg&#39; / &#39;mod.py&#39;).write_text(&#39;VALUE = 99&#39; + chr(10))\nsys.path.insert(0, root)\nimport pkg\nprint(pkg.VALUE, pkg.__all__)\nprint(pkg.__file__ is not None, &#39;pkg.mod&#39; in sys.modules)\nsys.path.remove(root)", "note": "包、相对导入与命名空间包"}]' title='两种写法切换看' />


## 循环导入的成因与根治

循环导入是 a 与 b 互相 `import`，且至少一方在顶层就要用到对方尚未定义完成的名字。关键在于 `_find_and_load` 会先把占位 module 对象放进 `sys.modules`、之后才执行顶层代码：于是另一方拿到的是属性还没填齐的半成品模块。

写法不同报错也不同：`from a import A` 在 `A` 未就绪时报 `ImportError: can…`；

```python
ImportError: cannot import name 'A' from partially initialized module 'a' (most likely due to a circular import)
```

而先 `import a` 再取 `a.A` 则报 `AttributeError…`。

```python
AttributeError: partially initialized module 'a' ... has no attribute 'A' (most likely due to a circular import)
```

若只 import 模块对象、把属性访问推迟到运行时，通常不会立刻报错，因为等属性补齐后引用自然可用。

诊断时看 Traceback 里的 `partially initia…` 与 `most likely due…`，再打印 `sys.modules` 的键确认加载顺序。

```text
partially initialized module
most likely due to a circular import
```

四种根治手段：把共享类型与常量下沉到第三个独立模块让依赖变单向；把 `import` 延迟到函数内部、用到时才导入；

仅类型注解需要的导入放进 `typing.TYPE_CHECKING` 配合延迟注解，运行时不发生；

统一包内相对导入加 src 布局（源码放 `src/`，避免包目录被直接塞进 `sys.path` 造成同名双加载）。

**循环导入的成因、信号与根治**

| 项 | 内容 | 可核对细节 |
| --- | --- | --- |
| 触发条件 | 两模块互相 import，且一方在顶层就要对方未完成的名字 | 模块对象先入 sys.modules 再执行，属性尚未填齐 |
| from 形式报错 | ImportError: cannot import name 'A' from partially initialized module 'a' (most likely due to a circular import) | 3.8+ 文案，Traceback 里 circular import 是强信号 |
| 取属性形式报错 | AttributeError: partially initialized module 'a' has no attribute 'A' (most likely due to a circular import) | 先 import 模块对象、再访问 a.A 时触发 |
| 修复一 | 共享类型下沉到第三个独立模块 | 让依赖关系变成单向 |
| 修复二 / 三 / 四 | 函数内延迟导入 / TYPE_CHECKING / 相对导入 + src 布局 | src 布局避免同名包被加载两份 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：只是 import 一下配置模块，却连了库、", "body": "模块顶层代码在导入时执行一次，副作用不受 main 守卫保护", "tip": "把可执行逻辑放进 if __name__ == &#39;__main__&#39;: 或函数里，顶层只留类、函数与常量定义"}, {"title": "第 2 步：a 与 b 互相导入，报 partially", "body": "模块对象先入 sys.modules 再执行，顶层取对方属性时对方还没定义完", "tip": "共享类型下沉到第三模块、把 import 延迟到函数内、仅类型用 TYPE_CHECKING，并用 src 布局统一相对导入"}, {"title": "第 3 步：包内脚本直接运行，相对导入报 attempt", "body": "直接运行时 __package__ 为空，相对导入没有解析基准", "tip": "用 python -m pkg.mod 运行以设置包上下文，或改成绝对导入"}]' />


## 复现循环导入，并把共享类型下沉到独立模块

两个服务模块互相引用对方的类：`m_a.py` 顶层 `import m_b` 后在类体里取 `m_b.B`，`m_b.py` 又回头 `import m_a` 并立刻取 `m_a.A`。

导入 `m_a` 时，`m_a` 的模块对象已进 `sys.modules` 但 `class A` 还没定义，`m_b` 取 `m_a.A` 就报 `partially initia…`，这就是典型的循环导入。

```text
partially initialized module has no attribute
```

修复思路不是调整 import 顺序，而是把双方都依赖的类型下沉到第三个模块 `m_types`，让依赖图变成单向：`m_a2` 只依赖 `m_types`，`m_types` 不依赖任何人。下面用 `tempfile` 造出真实文件、先捕获异常确认信号，再导入修复后的模块验证 loaded。

真实工程还应配合 src 布局与包内相对导入，避免同名包被加载成两份。

```python
import sys, tempfile, pathlib, importlib

root = tempfile.mkdtemp()
d = pathlib.Path(root)
(d / 'm_a.py').write_text('import m_b' + chr(10) + 'class A:' + chr(10) + '    peer = m_b.B' + chr(10))
(d / 'm_b.py').write_text('import m_a' + chr(10) + 'X = m_a.A' + chr(10) + 'class B:' + chr(10) + '    pass' + chr(10))
sys.path.insert(0, root)
try:
    importlib.import_module('m_a')
except AttributeError as e:
    print(type(e).__name__, 'circular' in str(e))

(d / 'm_types.py').write_text('class B:' + chr(10) + '    pass' + chr(10))
(d / 'm_a2.py').write_text('from m_types import B' + chr(10) + 'class A2:' + chr(10) + '    peer = B' + chr(10))
print(importlib.import_module('m_a2').A2.peer.__name__)
```

<Callout type="idea" title='落地提示' text='用 src 布局、把共享类型下沉到独立模块、在包内用相对导入，可根治绝大多数导入问题' />

```bash
python -c "import importlib.util; print(importlib.util.find_spec('json').origin)"
```

把输入换成你自己的数据，观察结果是否仍符合 模块对象与 `sys.modules` 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

<CheckList id='P035b' title='上线前自检' :items='["能复现并解释「只是 import 一下配置模块，却连了库、起了线程、进程不」", "能复现并解释「a 与 b 互相导入，报 partially initial」", "能复现并解释「包内脚本直接运行，相对导入报 attempted relat」", "能用一条命令验证 模块对象与 sys.modules", "关键路径有自动化测试与失败分支"]' />


## 导入副作用与相对导入错因速查

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 只是 import 一下配置模块，却连了库、起了线程、进程不退出 | 模块顶层代码在导入时执行一次，副作用不受 main 守卫保护 | 把可执行逻辑放进 if __name__ == '__main__': 或函数里，顶层只留类、函数与常量定义 |
| a 与 b 互相导入，报 partially initialized module ... most likely due to a circular import | 模块对象先入 sys.modules 再执行，顶层取对方属性时对方还没定义完 | 共享类型下沉到第三模块、把 import 延迟到函数内、仅类型用 TYPE_CHECKING，并用 src 布局统一相对导入 |
| 包内脚本直接运行，相对导入报 attempted relative import with no known parent package | 直接运行时 __package__ 为空，相对导入没有解析基准 | 用 python -m pkg.mod 运行以设置包上下文，或改成绝对导入 |

<Callout type="warn" title='本讲最容易踩的坑' text='只是 import 一下配置模块，却连了库、起了线程、进程不退出：模块顶层代码在导入时执行一次，副作用不受 main 守卫保护' />

<CheckList id='P035a' title='学完你应当能' :items='["能讲清 import 的执行链路与模块单例", "能讲清 包、相对导入与命名空间包", "能讲清 循环导入的成因与根治", "能在工程里处理 命名空间包"]' />


## 复现导入错误并自测

<Exercise title='基础：验证模块单例' task='用 importlib.import_module 连续导入两次 math，打印两个对象是否相同、模块名是否在 sys.modules、以及对象类型名。' solution='import sys, importlib\n\na = importlib.import_module(&#39;math&#39;)\nb = importlib.import_module(&#39;math&#39;)\nprint(a is b, &#39;math&#39; in sys.modules, type(a).__name__)' explain='第二次导入命中 sys.modules 缓存，返回同一个 module 对象，顶层代码不会重跑；类型名是 module。' />

<Exercise title='进阶：证明顶层代码在导入时执行' task='用 types.ModuleType 造一个模块对象，把一段含 print 与赋值的源码 compile 后在它的 __dict__ 里 exec，观察顶层副作用并读出属性。' solution='import types\n\nsrc = &#39;print(&#39; + repr(&#39;loading&#39;) + &#39;)&#39; + chr(10) + &#39;VALUE = 1&#39;\nm = types.ModuleType(&#39;side&#39;)\nexec(compile(src, &#39;side.py&#39;, &#39;exec&#39;), m.__dict__)\nprint(m.VALUE)' explain='exec 相当于导入时执行顶层代码，print 会立即触发；这正是把副作用收进 if __name__ == &#39;__main__&#39; 守卫的原因。' />

<Quiz no='035-2' q='对同一模块第二次执行 import X 会发生什么？' :options='["直接返回 sys.modules 里同一个模块对象，不重跑顶层代码", "重新执行一遍顶层代码", "抛 ImportError", "生成一个新的模块对象"]' answer="0" explain='sys.modules 以完整模块名为键缓存 module 对象，命中即返回；要重新执行必须显式调用 importlib.reload。' />

<Quiz no='035-3' q='循环导入在 3.8+ 的 Traceback 里最典型的信号是？' :options='["partially initialized module 与 most likely due to a circular import", "SyntaxError: invalid syntax", "KeyError: module", "RecursionError: maximum recursion depth exceeded"]' answer="0" explain='模块对象先入 sys.modules 再执行顶层代码，取属性时对方尚未定义完，解释器据此给出 partially initialized 与 circular import 提示。' />

<Quiz no='035-4' q='根治循环导入最稳妥的一组做法是？' :options='["共享类型下沉到第三模块、延迟导入、TYPE_CHECKING、包内相对导入 + src 布局", "把所有 import 语句删掉", "一律改用 from X import *", "把包内所有模块合并成一个大文件"]' answer="0" explain='前四者让依赖图变单向或把导入推迟到运行时；删 import 与 import * 只会制造新问题，合并大文件牺牲可维护性。' />

<FillBlank no='035-5' tpl='___ sys, importlib, types' :answers='["import"]' hint='回想本讲关于 模块对象与 sys.modules 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 import 的执行链路与模块单例 的落点。' />

<KnowledgeCard :points='["import 先查 sys.modules，命中返回同一 module 对象；模块天然单例，重跑用 importlib.reload", "sys.meta_path 里 BuiltinImporter / FrozenImporter / PathFinder 依次尝试；PathFinder 沿 sys.path 搜索，loader 执行顶层代码", "顶层代码在导入时执行一次，副作用要收进 if __name__ == &#39;__main__&#39;；sys.path[0] 是入口脚本目录，同名文件会遮蔽标准库", "常规包含 __init__.py；__all__ 控制 from pkg import *；相对导入基于 __package__，脚本直接运行报 attempted relative import with no known parent package", "PEP 420（3.3+）命名空间包无 __init__.py，__file__ 为 None、__path__ 是 _NamespacePath", "循环导入根因是模块对象先入 sys.modules 再执行；靠下沉共享类型、延迟导入、TYPE_CHECKING、src 布局根治"]' :pitfalls='["只是 import 一下配置模块，却连了库、起了线程、进程不退出", "a 与 b 互相导入，报 partially initialized module ... most likely due to a circular import", "包内脚本直接运行，相对导入报 attempted relative import with no known parent package", "把可执行逻辑写在模块顶层，会在「只是导入一下」时触发副作用；循环导入也随之而来"]' summary='import 会执行模块顶层代码并把结果缓存进 sys.modules，第二次导入拿的是同一个对象，所以模块天然是单例' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| import 先查 sys.modules，命中返回同一 module 对象；模块天然单例，重跑用 importlib.reload | 建立直觉 |
| sys.meta_path 里 BuiltinImporter / FrozenImporter / PathFinder 依次尝试；PathFinder 沿 sys.path 搜索，loader 执行顶层代码 | 跑通示例 |
| 顶层代码在导入时执行一次，副作用要收进 if __name__ == '__main__'；sys.path[0] 是入口脚本目录，同名文件会遮蔽标准库 | 深入边界 |
| 常规包含 __init__.py；__all__ 控制 from pkg import *；相对导入基于 __package__，脚本直接运行报 attempted relative import with no known parent package | 工程落地 |
| PEP 420（3.3+）命名空间包无 __init__.py，__file__ 为 None、__path__ 是 _NamespacePath | 随堂检测 |
| 循环导入根因是模块对象先入 sys.modules 再执行；靠下沉共享类型、延迟导入、TYPE_CHECKING、src 布局根治 | 复盘 |

1. import 先查 sys.modules，命中返回同一 module 对象；模块天然单例，重跑用 importlib.reload

2. sys.meta_path 里 BuiltinImporter / FrozenImporter / PathFinder 依次尝试；PathFinder 沿 sys.path 搜索，loader 执行顶层代码

3. 顶层代码在导入时执行一次，副作用要收进 if __name__ == '__main__'；sys.path[0] 是入口脚本目录，同名文件会遮蔽标准库

[下一讲：类型注解、typing 与渐进式类型](/functions/typing)
