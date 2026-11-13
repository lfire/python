---
title: 第 046 讲 · 反射与自省：getattr、inspect 与 __dict__
description: 构建可插拔的框架式代码
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='30 分钟' goal='构建可插拔的框架式代码' prereq='第 045 讲 · 元类：__new__、type 与类创建过程' />

# 第 046 讲 · 反射与自省：getattr、inspect 与 __dict__

类怎么被创建已经清楚，换个方向：运行时连具体类型都不知道，框架怎么发现一个对象能做什么？这套反射与自省的本事，插件系统与命令行路由都靠它，让代码按名字去找。

一个运维平台允许在配置里写方法名，后端照名字调用，结果一段无害字符串碰到了清理缓存的私有方法；另一个框架用 `hasattr` 判断插件就绪，却把属性内部的错误当成「不存在」。本讲先从属性查找链与 `getattr` 讲起，再看 `inspect.signature` 与注解读取，最后落到动态导入与白名单注册表。需要类与属性、函数与模块导入；学完你能搭出可插拔的框架式代码，也知道反射入口该配哪道边界。


## 一个把用户输入直接喂给 getattr 的远程调用漏洞

一个内部运维平台允许用户在配置里写方法名，后端直接 `getattr(service, name)()` 调用。

上线后被传入一个看似无害的字符串，触发了对象内部用于清理缓存的私有方法，删掉了整站的热数据——反射入口变成了任意方法执行入口。

另一处排查更耗时间：框架用 `hasattr(obj, 'ready')` 判断插件是否就绪，某插件的 `ready` 是个 `property`，内部访问依赖未初始化的资源时抛了 `AttributeError`，`hasattr` 直接返回 `False`，插件被静默跳过，日志里毫无异常。

还有人读函数 `__annotations__` 做参数绑定，遇到启用了 PEP 563 延迟注解的项目，拿到的是字符串 `'int'` 而不是类型对象，绑定逻辑全错。

自省是框架能力的基础，但每条 API 都有明确的边界与陷阱。

本讲把属性查找链、`getattr` / `hasattr` 的真实语义、`inspect.signature` 与 `get_type_hints`、动态导入与白名单注册表逐一对上，给出可复现的错因与修复。

<Callout type="warn" title='先看一个真实会出错的写法' text='对用户传入的字符串直接 getattr(obj, name)() 调用：getattr 能取到对象任意公开方法，等于把清理、删除、重置等私有能力暴露成调用面' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 045 讲 · 元类：__new__、type 与类创建过程 |
| 难度 / 建议时长 | ★★★☆☆ · 30 分钟 |
| 本讲新增 | getattr / setattr / hasattr、inspect.signature 与 getmembers、__dict__ 与 vars |
| 一句话目标 | 构建可插拔的框架式代码 |
| 为下一讲铺垫 | dataclass、attrs 与 pydantic 模型 |

<Callout type="tip" title='核心心智模型' text='`getattr` 本质是调用类型的 `tp_getattro`，也就是 `PyObject_GenericGetAttr` 那条查找链：先按 MRO 在类的字典里找同名描述符，数据描述符（定义了 `__set__` 或 `__delete__`）优先于实例 `__dict__`，非数据描述符次之，' />


## 属性查找链与 getattr / hasattr 的真实语义

`getattr` 本质是调用类型的 `tp_getattro`，也就是 `PyObject_GenericGetAttr` 那条查找链：先按 MRO 在类的字典里找同名描述符，数据描述符（定义了 `__set__` 或 `__delete__`）优先于实例 `__dict__`，非数据描述符次之，最后才回退实例字典；

都没找到且未提供 `default` 时抛 `AttributeError`。

`setattr` / `delattr` / `hasattr` / `vars` 是同一套机制的封装：`vars(obj)` 直接返回 `obj.__dict__`，对象没有 `__dict__`（如 `__slots__` 类或内置类型）时 `vars()` 会抛 `TypeError`，提示缺少 `__dict__` 属性。

`hasattr` 在 Python 3 里的实现是调用 `getattr` 并只捕获 `AttributeError`（Python 2 曾捕获所有异常），因此 `property` 里抛出的 `AttributeError` 会被当成「属性不存在」吞掉，返回 `False`——这是最隐蔽的误判。

修复方式是用 `inspect.getattr_static`（不触发描述符、沿 MRO 静态查找）或显式 `try` / `except` 访问并区分异常来源。

`dir(obj)` 返回排序后的名字列表，类可实现 `__dir__` 定制；`callable(obj)` 判断能否调用。`getattr` 允许点号之外的任意字符串名，这正是它能被滥用成任意方法入口的原因。

```python
import inspect

class Service:
    version = '1.0'
    def run(self, n: int, flag: bool = False) -> str:
        return 'ok'

svc = Service()
print('getattr', getattr(svc, 'version'), getattr(svc, 'missing', 'default'))
print('hasattr', hasattr(svc, 'run'), hasattr(svc, 'missing'))
print('sig', str(inspect.signature(svc.run)))
print('annotations', svc.run.__annotations__)
print('members', sorted(k for k, _ in inspect.getmembers(svc) if k == 'run'))
print('dict keys', sorted(vars(svc).keys()))
```

<OutputBox title='主示例运行结果' output='getattr 1.0 default\nhasattr True False\nsig (n: int, flag: bool = False) -&gt; str\nannotations {&#39;n&#39;: &lt;class &#39;int&#39;&gt;, &#39;flag&#39;: &lt;class &#39;bool&#39;&gt;, &#39;return&#39;: &lt;class &#39;str&#39;&gt;}\nmembers [&#39;run&#39;]\ndict keys []' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import inspect\n\nclass Service:\n    version = &#39;1.0&#39;\n    def run(self, n: int, flag: bool = False) -&gt; str:\n        return &#39;ok&#39;\n\nsvc = Service()\nprint(&#39;getattr&#39;, getattr(svc, &#39;version&#39;), getattr(svc, &#39;missing&#39;, &#39;default&#39;))\nprint(&#39;hasattr&#39;, hasattr(svc, &#39;run&#39;), hasattr(svc, &#39;missing&#39;))\nprint(&#39;sig&#39;, str(inspect.signature(svc.run)))\nprint(&#39;annotations&#39;, svc.run.__annotations__)\nprint(&#39;members&#39;, sorted(k for k, _ in inspect.getmembers(svc) if k == &#39;run&#39;))\nprint(&#39;dict keys&#39;, sorted(vars(svc).keys()))' :notes='["导入 inspect，用于签名与成员自省", "空行分隔导入与类定义", "定义服务类，集中演示反射入口", "类属性 version，实例属性查找时会回退到类字典", "带注解与默认值的方法，供 signature 与 __annotations__ 读取", "方法体返回固定值，本例聚焦元信息", "空行分隔定义与验证", "构造实例，注意 version 是类属性而非实例属性", "getattr 命中共读版本；未命中时返回提供的 default", "hasattr 对存在与不存在的名字分别给 True / False", "signature 对绑定方法自动去掉 self，展示剩余参数与注解", "__annotations__ 在无 future 注解时是真实类型对象"]' title='第 046 讲 · 反射与自省：getattr、inspect 与 __dict__' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import importlib

ALLOWED = {'dumps': 'json', 'loads': 'json'}
def call(name, *args):
    if name not in ALLOWED:
        raise ValueError('not allowed: ' + name)
    mod = importlib.import_module(ALLOWED[name])
    return getattr(mod, name)(*args)

print(call('dumps', {'a': 1}))
try:
    call('rmtree', '/tmp')
except ValueError as e:
    print('blocked:', str(e))
```

<OutputBox title='对照写法：先自己猜，再点开' output='{"a": 1}\nblocked: not allowed: rmtree' guess="true" />

**反射与自省 API 对照**

| API | 作用 | 失败 / 边界 |
| --- | --- | --- |
| getattr(obj, name[, default]) | 走 tp_getattro 查找链取属性 | 无 default 时抛 AttributeError |
| hasattr(obj, name) | 等同 getattr 并只捕获 AttributeError | property 抛 AttributeError 会被误判为不存在 |
| vars(obj) | 返回 obj.__dict__ | 无 __dict__ 抛 TypeError: vars() argument must have __dict__ attribute |
| inspect.signature(fn) | 重建 Signature，绑定方法去掉 self | 部分 builtin 抛 ValueError: no signature found for builtin |
| inspect.getmembers(obj) | 返回按名排序的 (名字, 值) 列表 | 会触发描述符求值，重对象有副作用 |
| inspect.getattr_static(obj, name) | 沿 MRO 静态查找，不触发描述符 | 拿不到动态计算出的属性 |
| importlib.import_module(name) | 按字符串导入模块 | 会执行模块顶层代码，名字必须可信 |


## inspect 与注解：signature、getmembers、get_type_hints

`inspect.signature` 返回一个 `Signature` 对象，它的 `parameters` 是按定义顺序排列的映射，每个 `Parameter` 带 `name`、`kind`（`POSITIONAL_ONLY` / `POSITIONAL_OR_KEYWORD` / `VAR_POSITIONAL` / `KEYWORD_ONLY` / `VAR_KEYWORD`）、`default` 与 `annotation`；

想读某个参数的默认值，顺着映射一路取到 `inspect.signature(f).parameters['acc'].default` 即可。

绑定方法会自动去掉 `self`，所以 `inspect.signature(obj.method)` 看不到它。

`Signature.bind` / `Signature.bind_partial` 能按签名预先校验参数，是写路由分发时的可靠工具；

对部分 C 实现的 builtin（如某些内置类型的方法）没有 `__code__`，`signature` 会抛 `ValueError`，提示找不到签名。

`inspect.getmembers` 返回按名字排序的 `(name, value)` 元组列表，可传 `predicate` 过滤，配合 `inspect.isfunction` / `ismethod` / `isclass` / `ismodule` 判定函数使用；

`inspect.getsource`、`inspect.getmodule`、`inspect.getmro` 分别取源码、所属模块与方法解析顺序。

注解读取有两个层次：直接读 `func.__annotations__` 拿到的是原样值，未启用 PEP 563 延迟注解时是真实类型对象，启用后全是字符串；

`typing.get_type_hints(func)` 会解析字符串、前向引用与 `Optional` / `Union`，给出可用的类型对象，3.10 起还提供 `inspect.get_annotations` 做更细的控制。

把 `__annotations__` 直接当类型用，是跨项目复用框架代码时最常见的类型错误来源。

```python
from typing import get_type_hints
import inspect

class Trap:
    @property
    def broken(self):
        raise AttributeError('boom')

t = Trap()
print('hasattr broken:', hasattr(t, 'broken'))
print('in dict:', 'broken' in vars(t))

def f(x: 'int', y: list = None) -> 'dict':
    pass
print('isfunction:', inspect.isfunction(f))
print('raw:', f.__annotations__)
print('hints:', get_type_hints(f))
```

<OutputBox title='原理验证' output='hasattr broken: False\nin dict: False\nisfunction: True\nraw: {&#39;x&#39;: &#39;int&#39;, &#39;y&#39;: &lt;class &#39;list&#39;&gt;, &#39;return&#39;: &#39;dict&#39;}\nhints: {&#39;x&#39;: &lt;class &#39;int&#39;&gt;, &#39;y&#39;: &lt;class &#39;list&#39;&gt;, &#39;return&#39;: &lt;class &#39;dict&#39;&gt;}' />

<Compare :panels='[{"label": "主示例", "code": "import inspect\n\nclass Service:\n    version = &#39;1.0&#39;\n    def run(self, n: int, flag: bool = False) -&gt; str:\n        return &#39;ok&#39;\n\nsvc = Service()\nprint(&#39;getattr&#39;, getattr(svc, &#39;version&#39;), getattr(svc, &#39;missing&#39;, &#39;default&#39;))\nprint(&#39;hasattr&#39;, hasattr(svc, &#39;run&#39;), hasattr(svc, &#39;missing&#39;))\nprint(&#39;sig&#39;, str(inspect.signature(svc.run)))\nprint(&#39;annotations&#39;, svc.run.__annotations__)\nprint(&#39;members&#39;, sorted(k for k, _ in inspect.getmembers(svc) if k == &#39;run&#39;))\nprint(&#39;dict keys&#39;, sorted(vars(svc).keys()))", "note": "属性查找链与 getattr / hasattr 的真实语义"}, {"label": "对照 / 进阶", "code": "import importlib\n\nALLOWED = {&#39;dumps&#39;: &#39;json&#39;, &#39;loads&#39;: &#39;json&#39;}\ndef call(name, *args):\n    if name not in ALLOWED:\n        raise ValueError(&#39;not allowed: &#39; + name)\n    mod = importlib.import_module(ALLOWED[name])\n    return getattr(mod, name)(*args)\n\nprint(call(&#39;dumps&#39;, {&#39;a&#39;: 1}))\ntry:\n    call(&#39;rmtree&#39;, &#39;/tmp&#39;)\nexcept ValueError as e:\n    print(&#39;blocked:&#39;, str(e))", "note": "inspect 与注解：signature、getmembers、get_type_hints"}]' title='两种写法对照' note='差异集中在 getattr / setattr / hasattr；先看输出，再找背后的规则。' />

**注解读取的两种层次**

| 场景 | __annotations__ 内容 | get_type_hints 结果 |
| --- | --- | --- |
| 无 future，注解写 int | &lt;class 'int'> | &lt;class 'int'> |
| from __future__ import annotations | 字符串 'int' 等 | 解析成真实类型对象 |
| 前向引用 'Node' | 字符串 'Node' | 按命名空间解析，失败抛 NameError |
| Optional[int] | typing.Optional[int] | 展开为 typing.Optional[int] |
| 3.10+ inspect.get_annotations | 可控制是否 eval 字符串 | 按 eval_str 参数决定 |

<Term word='getattr / setattr / hasattr' text='`getattr` 本质是调用类型的 `tp_getattro`，也就是 `PyObject_GenericGetAttr` 那条查找链：先按 MRO 在类的字典里找同名描述符，数据描述符（定义了 `__set__` 或 `__delete__`）优先于实例 `__dict__`，非数据描述符次之，最后才回退实例字典；' />

<Term word='inspect.signature 与 getmembers' text='`inspect.signature` 返回一个 `Signature` 对象，它的 `parameters` 是按定义顺序排列的映射，每个 `Parameter` 带 `name`、`kind`（`POSITIONAL_ONLY` / `POSITIONAL_OR_KEYWORD` / `VAR_POSITIONAL' />


## 动态导入与反射的安全边界：白名单注册表

`importlib.import_module('pkg.mod')` 按字符串动态导入模块并返回模块对象，是插件加载、CLI 命令发现与配置驱动架构的基础；

它执行的是真实导入（会跑模块顶层代码），因此模块名必须来自可信配置而非原始用户输入。

反射的安全边界不在 API 上，而在「允许被调用什么」有没有被收敛：对用户传入的字符串直接 `getattr(obj, name)()` 等于把对象所有公开方法暴露成远程调用面，私有清理、删除、重置方法都可能被触发。

正确做法是显式注册表：在代码里用装饰器或字典把允许的名字映射到具体函数，`dispatch` 时先查表、不在表内直接拒绝；确实需要按名字取属性时，也要配合前缀白名单（如只允许 `cmd_` 开头）与类型检查（`callable` 且是注册过的绑定方法）。

此外要区分「发现能力」与「执行能力」：`inspect.getmembers` 用来发现插件有哪些方法是可以的，但真正调用前必须过注册表。

CLI 路由是这套模式的典型：命令名到函数的字典、用 `Signature.bind` 预先校验参数、用 `try` / `except` 把 `TypeError` 转成友好的参数错误。把反射入口收窄到可控集合，框架才既能扩展又不被滥用。

CPython 的属性读取由 `PyObject_GenericGetAttr` 驱动：按类型 MRO 查 `tp_dict`，若找到的是数据描述符（`tp_descr_set` 非空，即定义了 `__set__` 或 `__delete__`）就优先调用其 `__get__`，否则再看实例 `__dict__`，最后才回退非数据描述符或类属性。

`getattr` / `hasattr` / `vars` 都落在这一条链上；

`hasattr` 的实现调用 `PyObject_GetAttr` 后用 `PyErr_ExceptionMatches(PyExc_AttributeError)` 判断是否吞异常，所以 `property` 内部抛的 `AttributeError` 与「属性不存在」无法区分。

`inspect.signature` 从函数的 `__code__`（`co_varnames`、`co_argcount` 等）、`__defaults__`、`__kwdefaults__`、`__annotations__` 重建 `Signature`，绑定方法先剥离已绑定的 `self`，C 函数没有 `__code__` 因而可能失败。

`typing.get_type_hints` 对字符串注解调用 `eval`（在 `func` 的全局命名空间里）解析前向引用；

PEP 563 的延迟注解把所有注解存成字符串，正是它让直接读 `__annotations__` 的代码失效。

`importlib.import_module` 走完整的查找器—加载器流程并执行模块顶层代码，因此它既是扩展点也是执行入口。

**反射入口的风险与收敛**

| 风险 | 根因 | 正确做法 |
| --- | --- | --- |
| 任意方法执行 | 对用户字符串直接 getattr(obj, name)() | 显式注册表把名字映射到具体函数，未登记直接拒绝 |
| hasattr 静默跳过插件 | property 抛 AttributeError 被 hasattr 吞掉 | 用 inspect.getattr_static 或显式 try/except 区分来源 |
| 注解当类型用出错 | future 下 __annotations__ 全是字符串 | 用 typing.get_type_hints 解析后再绑定 |
| 导入不可信模块 | import_module 会执行模块顶层代码 | 模块名来自可信配置，配合白名单 |
| 命令参数报错难定位 | 直接调用才在深处抛 TypeError | 先用 Signature.bind 预校验并转成友好错误 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：对用户传入的字符串直接 getattr(ob", "body": "getattr 能取到对象任意公开方法，等于把清理、删除、重置等私有能力暴露成调用面", "tip": "用显式注册表把允许的名字映射到具体函数，dispatch 先查表；必要时再加前缀白名单与 callable 检查"}, {"title": "第 2 步：用 hasattr 判断 property ", "body": "hasattr 只捕获 AttributeError，property 内部抛出的 AttributeError 会被当成属性不存在，返回 False", "tip": "改用 inspect.getattr_static(obj, name) 做静态查找，或显式访问并用 try/except 区分异常来源"}, {"title": "第 3 步：把 func.__annotations__", "body": "from __future__ import annotations（PEP 563）下注解全是字符串，前向引用也需解析", "tip": "用 typing.get_type_hints(func) 或 3.10+ inspect.get_annotations 拿到可用的类型对象再绑定"}]' />

<ConceptDiagram type='flow4' title='第 046 讲 · 属性查找链与 getattr / hasattr 的真实语义' labels='属性查找链与 getattr / hasat|inspect 与注解：signature、|动态导入与反射的安全边界：白名单注册表' caption='构建可插拔的框架式代码' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## CLI 路由：注册表 + signature.bind 做安全分发

运维 CLI 要支持按名字调用命令，又不能把服务对象上的任意方法暴露出去。做法是显式路由表：`ROUTE` 字典把命令名收敛到具体函数，`dispatch` 先查表、未登记直接抛 `KeyError`；

再用 `inspect.signature(fn).bind` 按方法签名预校验参数，把缺参数、多参数这类错误在入口处转成清晰的 `TypeError`，而不是让它们流到业务深处。

下面用标准库跑通：`add` 正常求和、`echo` 回显、缺参数与未知命令分别被拦下并打印异常类型。要点是「发现能力」与「执行能力」分离——反射只用于读签名，真正调用永远经过白名单。真实项目还会在这层加权限校验、参数类型转换与审计日志。

```python
import inspect

class Commands:
    def add(self, a: int, b: int) -> int:
        return a + b
    def echo(self, text: str) -> str:
        return text

ROUTER = Commands()
ROUTE = {'add': Commands.add, 'echo': Commands.echo}
def dispatch(name, **kwargs):
    if name not in ROUTE:
        raise KeyError('unknown command: ' + name)
    fn = ROUTE[name]
    sig = inspect.signature(fn)
    bound = sig.bind(ROUTER, **kwargs)
    return fn(*bound.args, **bound.kwargs)

print('add:', dispatch('add', a=2, b=3))
print('echo:', dispatch('echo', text='hi'))
try:
    dispatch('add', a=1)
except TypeError as e:
    print(type(e).__name__, 'missing arg')
try:
    dispatch('delete', a=1)
except KeyError:
    print('KeyError', 'rejected')
```

<Callout type="idea" title='落地提示' text='反射入口要配白名单与显式注册表，把「能被调用什么」收敛到可控集合' />

<CheckList id='P046b' title='上线前自检' :items='["能复现并解释「对用户传入的字符串直接 getattr(obj, name)」", "能复现并解释「用 hasattr 判断 property 是否存在」", "能复现并解释「把 func.__annotations__ 直接当类型对象」", "能用一条命令验证 getattr / setattr / hasattr", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import importlib.util; print(importlib.util.find_spec('json').origin)"
```

把输入换成你自己的数据，观察结果是否仍符合 getattr / setattr / hasattr 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 对用户传入的字符串直接 getattr(obj, name)() 调用 | getattr 能取到对象任意公开方法，等于把清理、删除、重置等私有能力暴露成调用面 | 用显式注册表把允许的名字映射到具体函数，dispatch 先查表；必要时再加前缀白名单与 callable 检查 |
| 用 hasattr 判断 property 是否存在 | hasattr 只捕获 AttributeError，property 内部抛出的 AttributeError 会被当成属性不存在，返回 False | 改用 inspect.getattr_static(obj, name) 做静态查找，或显式访问并用 try/except 区分异常来源 |
| 把 func.__annotations__ 直接当类型对象使用 | from __future__ import annotations（PEP 563）下注解全是字符串，前向引用也需解析 | 用 typing.get_type_hints(func) 或 3.10+ inspect.get_annotations 拿到可用的类型对象再绑定 |

<Callout type="warn" title='本讲最容易踩的坑' text='对用户传入的字符串直接 getattr(obj, name)() 调用：getattr 能取到对象任意公开方法，等于把清理、删除、重置等私有能力暴露成调用面' />

<FlowTimeline :steps='[{"title": "属性查找链与 getattr / hasattr 的真实语义", "desc": "`getattr` 本质是调用类型的 `tp_getattro`，也就是 `PyOb…", "tone": "blue"}, {"title": "inspect 与注解：signature、getmembers、get_type_hints", "desc": "`inspect.signature` 返回一个 `Signature` 对象，它的…", "tone": "purple"}, {"title": "动态导入与反射的安全边界：白名单注册表", "desc": "`importlib.import_module(&#39;pkg.mod&#39;)` 按字符串动…", "tone": "orange"}, {"title": "工程落地", "desc": "CLI 路由：注册表 + signature.bind 做安全分发", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 练到手熟

<Exercise title='基础：复现 hasattr 吞掉 property 的 AttributeError' task='定义一个 property，访问时抛 AttributeError；分别打印 hasattr(obj, name) 与 inspect.getattr_static 的结果，说明为什么框架会静默跳过这个对象。' solution='import inspect\nclass P:\n    @property\n    def ready(self):\n        raise AttributeError(&#39;not initialized&#39;)\np = P()\nprint(&#39;hasattr:&#39;, hasattr(p, &#39;ready&#39;))\nprint(&#39;static:&#39;, inspect.getattr_static(p, &#39;ready&#39;, None) is not None)' explain='hasattr 调用 getattr 并只捕获 AttributeError，property 抛出的正好是它，于是返回 False 且异常消失；getattr_static 沿 MRO 静态查找不触发描述符，能确认属性其实存在。' />

<Exercise title='进阶：用 signature.bind 预校验命令参数' task='给定函数 def run(host, port=80, *, timeout=5)，用 inspect.signature 打印各参数 kind 与 default，再用 bind 分别验证合法与非法调用，把 TypeError 转成可读信息。' solution='import inspect\ndef run(host, port=80, *, timeout=5):\n    return (host, port, timeout)\nsig = inspect.signature(run)\nprint([(p.name, str(p.kind), p.default) for p in sig.parameters.values()])\nprint(sig.bind(&#39;h&#39;, 8080, timeout=9).arguments)\ntry:\n    sig.bind(&#39;h&#39;, 1, 2, 3)\nexcept TypeError as e:\n    print(&#39;bad args:&#39;, type(e).__name__)' explain='parameters 按定义顺序给出 POSITIONAL_OR_KEYWORD、KEYWORD_ONLY 及默认值；bind 按签名组装 arguments，多给位置参数时抛 TypeError，可在路由入口提前拦截。' />

<Quiz no='046-1' q='hasattr(obj, name) 在什么情况下会误判？' :options='["name 是 property 且内部抛 AttributeError 时返回 False", "对象实现了 __slots__ 时恒为 True", "属性名带下划线时抛异常", "只读属性一定返回 True"]' answer="0" explain='Python 3 的 hasattr 调用 getattr 并只捕获 AttributeError；property 内部抛的 AttributeError 与属性不存在无法区分，因此被吞成 False。可用 inspect.getattr_static 规避。' />

<Quiz no='046-2' q='from __future__ import annotations 下，func.__annotations__ 里是什么？' :options='["全是字符串，需要用 typing.get_type_hints 解析", "真实类型对象", "空字典", "typing.ForwardRef 对象"]' answer="0" explain='PEP 563 把所有注解延迟为字符串存储，避免前向引用与导入开销；直接读 __annotations__ 得到 &#39;int&#39; 这类字符串，get_type_hints 才 eval 出真实类型。' />

<Quiz no='046-3' q='关于 importlib.import_module，正确的是？' :options='["会执行目标模块的顶层代码，模块名必须来自可信配置", "只返回模块对象，不执行任何代码", "只能导入标准库模块", "等价于直接读文件内容"]' answer="0" explain='import_module 走完整查找器—加载器流程并执行模块顶层代码，是真实的导入。把用户输入直接当模块名等于开放任意代码执行，必须配合白名单。' />

<Predict no='046-4' q='某对象只有类属性 version，vars(obj) 与 getattr(obj, &#39;version&#39;) 分别得到什么？' :options='["vars 为空字典，getattr 返回类属性值", "vars 含 version，getattr 报错", "两者都为空"]' answer='0' output='dict keys [] / getattr 1.0' explain='vars(obj) 只看实例 __dict__，类属性不在其中；getattr 沿查找链回退到类字典，能读到 version。这正是「实例字典」与「属性可见集合」的区别。' />

<FillBlank no='046-5' tpl='___ inspect' :answers='["import"]' hint='回想本讲关于 getattr / setattr / hasattr 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 属性查找链与 getattr / hasattr 的真实语义 的落点。' />

<KnowledgeCard :points='["getattr 走 tp_getattro：数据描述符 &gt; 实例 __dict__ &gt; 非数据描述符 &gt; 类属性", "hasattr 在 Py3 只捕获 AttributeError，property 抛的会被吞掉；用 inspect.getattr_static 规避", "vars(obj) 即 __dict__；无 __dict__ 抛 TypeError，__slots__ 类与内置类型常见", "inspect.signature 对绑定方法去掉 self，Signature.bind 可预校验参数；部分 builtin 抛 ValueError", "__annotations__ 在 PEP 563 下全是字符串，类型绑定要用 typing.get_type_hints", "反射入口必须配显式注册表或前缀白名单；import_module 会执行模块顶层代码，名字要可信"]' :pitfalls='["对用户传入的字符串直接 getattr(obj, name)() 调用", "用 hasattr 判断 property 是否存在", "把 func.__annotations__ 直接当类型对象使用", "对用户传入的字符串直接 getattr 并调用，等于开了一个任意方法执行入口"]' summary='自省让框架可以在不知道具体类型的前提下发现能力，插件系统、序列化器与 CLI 路由都依赖它' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| getattr 走 tp_getattro：数据描述符 > 实例 __dict__ > 非数据描述符 > 类属性 | 建立直觉 |
| hasattr 在 Py3 只捕获 AttributeError，property 抛的会被吞掉；用 inspect.getattr_static 规避 | 跑通示例 |
| vars(obj) 即 __dict__；无 __dict__ 抛 TypeError，__slots__ 类与内置类型常见 | 深入边界 |
| inspect.signature 对绑定方法去掉 self，Signature.bind 可预校验参数；部分 builtin 抛 ValueError | 工程落地 |
| __annotations__ 在 PEP 563 下全是字符串，类型绑定要用 typing.get_type_hints | 随堂检测 |
| 反射入口必须配显式注册表或前缀白名单；import_module 会执行模块顶层代码，名字要可信 | 复盘 |

1. getattr 走 tp_getattro：数据描述符 > 实例 __dict__ > 非数据描述符 > 类属性

2. hasattr 在 Py3 只捕获 AttributeError，property 抛的会被吞掉；用 inspect.getattr_static 规避

3. vars(obj) 即 __dict__；无 __dict__ 抛 TypeError，__slots__ 类与内置类型常见

[下一讲：dataclass、attrs 与 pydantic 模型](/oop/dataclass)
