---
title: 第 036 讲 · 类型注解、typing 与渐进式类型
description: 为大型代码库建立可检查的接口契约
---

<StageHeader stage='L3 · 函数与抽象' level='★★★☆☆' time='35 分钟' goal='为大型代码库建立可检查的接口契约' prereq='第 035 讲 · 模块与包：import 机制与循环导入' />

# 第 036 讲 · 类型注解、typing 与渐进式类型

模块拆清楚后，跨服务的接口靠什么说明这里该传什么，就绕不开了。类型注解给的是一份能被工具读到的契约，补上动态语言在大型代码库里最缺的那层提示。文档写着某字段是整数，上游真传成字符串，服务一路没吭声，直到写库才露出来；有人以为注解加齐就安全，其实运行时并不替你检查。

先弄清注解存在哪、为何默认只是元数据，约束来自静态检查器；再看联合、泛型、Protocol 与 Literal 能把契约说到多细；最后谈渐进式落地——先在公共接口加，再往里铺，以及注解和运行时校验各管哪一段。会用到函数定义与模块导入；读完后你能给关键路径配上让 mypy 生效的接口说明。


## 加了类型注解，传错类型照样跑

一个跨服务的数据结构，接口文档里写着 user 是 dict、含 `id(int)` 与 `tags(list[str])`，结果上游某次把 id 传成字符串，服务一直没报错，直到写库时才失败，排查了半天。

团队给所有函数加了类型注解，以为从此类型安全，线上依旧跑出同样的错——因为注解默认只是 `__annotations__` 里的元数据，CPython 运行时根本不检查。

另一个极端是有人为了过 mypy，到处写 Any，检查器被关掉却浑然不觉。

本讲讲清注解与静态检查的分工：注解存在哪、get_type_hints 做什么、Union / Optional / Protocol / TypedDict / Literal 各解决什么问题、渐进式类型怎么落地，以及为什么注解替代不了 pydantic 这类运行时校验。

<Callout type="warn" title='先看一个真实会出错的写法' text='以为加了类型注解运行时就会校验，传错类型照样跑：注解只是 __annotations__ 元数据，CPython 不生成检查字节码' />


## 注解只是元数据：存储与求值

函数注解存在 `fn.__annotations__` 这个字典里，类与模块级的注解写在各自的 `__annotations__`；

变量注解 x: int 只登记注解、并不会创建名字绑定，随后读 x 会抛 NameError: name 'x' is not defined。注解默认在定义时求值并存为对象，CPython 3.13 仍是这个行为；

from `__future__` import annotations（PEP 563，3.7+）会把所有注解变成字符串延迟求值，用来解决前向引用与循环类型依赖，代价是运行时读到的不再是类型对象，需要 `typing.get_type_hints` 按 globalns / localns 解析回真实类型（它还会合并基类注解）。

最关键的结论是：CPython 的字节码里没有任何基于注解的类型检查指令，传错类型照样执行，直到具体操作失败才报错，注解也不影响运行速度。真正的约束力来自 mypy、pyright 这类静态检查器，它们在 CI 或编辑器里读注解构建类型图、做推断与控制流收窄。因此加注解不等于运行时安全，这是最容易误判的一层。

```python
import typing
from typing import get_type_hints

def distance(a: int, b: int = 0) -> float:
    return float(a - b)

h = get_type_hints(distance)
print(sorted(h))
print([h[k].__name__ for k in ('a', 'b', 'return')])
print(distance.__annotations__['a'] is int)
print(str(int | None))
print(get_type_hints(distance) == distance.__annotations__)
```

<OutputBox title='主示例运行结果' output='[&#39;a&#39;, &#39;b&#39;, &#39;return&#39;]\n[&#39;int&#39;, &#39;int&#39;, &#39;float&#39;]\nTrue\nint | None\nTrue' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import typing\nfrom typing import get_type_hints\n\ndef distance(a: int, b: int = 0) -&gt; float:\n    return float(a - b)\n\nh = get_type_hints(distance)\nprint(sorted(h))\nprint([h[k].__name__ for k in (&#39;a&#39;, &#39;b&#39;, &#39;return&#39;)])\nprint(distance.__annotations__[&#39;a&#39;] is int)\nprint(str(int | None))\nprint(get_type_hints(distance) == distance.__annotations__)' :notes='["导入 typing 用于类型相关工具", "导入 get_type_hints，把注解解析成真实类型对象", "定义带参数与返回值注解的函数", "函数体只是普通运算，注解不参与执行", "解析注解，得到名字到类型的字典", "打印注解里登记的字段名", "读出各字段类型的 __name__", "注解值就是 int 类型对象本身", "3.10+ 的联合写法 X | None", "解析结果与 __annotations__ 一致，说明没有延迟字符串"]' title='第 036 讲 · 类型注解、typing 与渐进式类型' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import dis

def f(a: int) -> int:
    return a

print(f.__annotations__)
print('a' in f.__code__.co_varnames)
src = 'x: int'
ns = {}
exec(compile(src, '<s>', 'exec'), ns)
print('x' in ns, '__annotations__' in ns, ns['__annotations__'])
print([i.opname for i in dis.get_instructions(f) if i.opname == 'RETURN_VALUE'])
```

<OutputBox title='原理验证' output='{&#39;a&#39;: &lt;class &#39;int&#39;&gt;, &#39;return&#39;: &lt;class &#39;int&#39;&gt;}\nTrue\nFalse True {&#39;x&#39;: &lt;class &#39;int&#39;&gt;}\n[&#39;RETURN_VALUE&#39;]' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段三 · 函数与抽象 |
| 前置 | 第 035 讲 · 模块与包：import 机制与循环导入 |
| 难度 / 建议时长 | ★★★☆☆ · 35 分钟 |
| 本讲新增 | 注解不强制运行时检查、泛型与 TypeVar、Optional / Union |
| 一句话目标 | 为大型代码库建立可检查的接口契约 |
| 为下一讲铺垫 | 阶段综合：缓存装饰器库与插件注册表 |

<ConceptDiagram type='flow4' title='第 036 讲 · 注解只是元数据：存储与求值' labels='注解只是元数据：存储与求值|联合、泛型与结构化子类型|渐进式类型落地与运行时校验的分界' caption='为大型代码库建立可检查的接口契约' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 联合、泛型与结构化子类型

Optional`[X]` 等价于 X | None，PEP 604 在 3.10 引入 X | Y 后 Union[X, Y] 也能直接写成联合；

内建泛型 list`[int]`、dict[str, int]、tuple[int, ...] 由 PEP 585 在 3.9 落地，3.8 及以前要用 `typing.List` / Dict / Tuple。

泛型方面，3.12 的 PEP 695 允许 def first`[T]`(xs: list`[T]`) -> T 与 type 别名语句，之前要写 `T = TypeVar`('T') 再配合 Generic`[T]`。

Protocol（PEP 544，3.8+）是结构化子类型：只要对象实现了协议要求的方法与属性就算满足，不需要显式继承；

加 @runtime_checkable 才能用 `isinstance(obj, Proto)`，且它只检查成员是否存在、不校验签名，含非方法成员的协议在运行时做 isinstance 还会受限。

TypedDict 给 dict 的键与值类型建模，字段类型存在 `__annotations__`，可用 `__required_keys__` / `__optional_keys__` 查必填与可选键；

Literal（3.8+）把取值限定成几个字面量，适合状态码与模式开关。这些构造让注解能表达远比 int / str 丰富的契约。

```python
from typing import Protocol, runtime_checkable, TypedDict, Literal, TYPE_CHECKING

@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...

class Config(TypedDict):
    host: str
    port: int

Mode = Literal['r', 'w']

class File:
    def close(self) -> None:
        pass

print(isinstance(File(), Closeable))
print(Config.__annotations__)
print(sorted(Config.__required_keys__))
print(Mode)
print(TYPE_CHECKING)
```

<OutputBox title='对照写法：先自己猜，再点开' output='True\n{&#39;host&#39;: &lt;class &#39;str&#39;&gt;, &#39;port&#39;: &lt;class &#39;int&#39;&gt;}\n[&#39;host&#39;, &#39;port&#39;]\ntyping.Literal[&#39;r&#39;, &#39;w&#39;]\nFalse' guess="true" />

**typing 常用构造与用途**

| 构造 | 版本 | 用途 | 边界 |
| --- | --- | --- | --- |
| Protocol（PEP 544） | 3.8+ | 结构化子类型，按方法 / 属性判定 | 加 @runtime_checkable 才能 isinstance，且不校验签名 |
| TypedDict | 3.8+ | 给 dict 的键与值类型建模 | __required_keys__ / __optional_keys__ 可查 |
| Literal | 3.8+ | 把取值限定为若干字面量 | 适合状态码、模式开关 |
| get_type_hints | 长期稳定 | 解析字符串注解、返回真实类型 | 前向引用与延迟注解必需 |
| TYPE_CHECKING | 长期稳定 | 运行时为 False，仅类型检查时为真 | 配合延迟注解打破循环导入 |


## 注解与 typing 的版本 / PEP

**注解与 typing 的版本 / PEP**

| 特性 | 版本 | 写法 | 可核对细节 |
| --- | --- | --- | --- |
| 变量注解 | 3.6 | x: int | 只写 __annotations__，不绑定变量，读 x 抛 NameError |
| from __future__ import annotations | 3.7+（PEP 563） | 注解延迟为字符串 | 需 get_type_hints 解析；解决前向引用 |
| 内建泛型（PEP 585） | 3.9 | list[int] / dict[str, int] | 3.8 及以前用 typing.List / Dict |
| 联合类型（PEP 604） | 3.10 | X \| None / X \| Y | Optional[X] 等价于 X \| None |
| 类型参数语法（PEP 695） | 3.12 | def f[T](x: T) -> T / type A = ... | 之前用 TypeVar('T') 与 Generic[T] |

<Term word='注解不强制运行时检查' text='函数注解存在 fn.__annotations__ 这个字典里，类与模块级的注解写在各自的 __annotations__；变量注解 x: int 只登记注解、并不会创建名字绑定，随后读 x 会抛 NameError: name &#39;x&#39; is not defined。注解默认在定义时求值并存为对象，CPython 3.' />

<Term word='泛型与 TypeVar' text='Optional[X] 等价于 X | None，PEP 604 在 3.10 引入 X | Y 后 Union[X, Y] 也能直接写成联合；内建泛型 list[int]、dict[str, int]、tuple[int, ...] 由 PEP 585 在 3.9 落地，3.8 及以前要用 typing.List /' />

<FlowTimeline :steps='[{"title": "注解只是元数据：存储与求值", "desc": "函数注解存在 fn.__annotations__ 这个字典里，类与模块级的注解写在…", "tone": "blue"}, {"title": "联合、泛型与结构化子类型", "desc": "Optional[X] 等价于 X | None，PEP 604 在 3.10 引入…", "tone": "purple"}, {"title": "渐进式类型落地与运行时校验的分界", "desc": "渐进式类型的做法是先在收益最大的地方加注解：公共 API、跨服务数据结构、配置模型，…", "tone": "orange"}, {"title": "工程落地", "desc": "跨服务 payload：注解给静态检查，运行时校验另写一层", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 渐进式类型落地与运行时校验的分界

渐进式类型的做法是先在收益最大的地方加注解：公共 API、跨服务数据结构、配置模型，再逐步铺开，未注解部分检查器按 Any 处理而不阻断。

Any 是逃生舱也是陷阱：它会让静态检查器在该处停止推断与报错，等于局部关掉检查，宁可用 object 加显式 isinstance 收窄、具体联合或 TypeVar，把 Any 控制在真正的动态边界。

注解与运行时校验是两件事：注解服务静态检查器与 IDE 的补全跳转，pydantic、attrs、marshmallow 则在运行时按模型解析、转换并拒绝外部输入；跨服务边界、用户表单、配置加载必须做运行时校验，不能指望注解。

工具链上把 mypy / pyright 放进 CI，逐步收紧配置（如 disallow_untyped_defs），让契约自动生效。

循环导入时仅类型注解需要的导入可放进 `typing.TYPE_CHECKING`（运行时为 False），配合延迟注解打破真实导入环，这与第 035 讲的诊断直接呼应。

注解在 CPython 里就是元数据：编译 def 时把参数与返回值注解表达式求值后的对象收进一个字典，执行 MAKE_FUNCTION 时挂到 `function.__annotations__`；

模块级与类级变量注解则写进各自的 `__annotations__` 字典，且不会为名字创建绑定，所以 x: int 之后读 x 会 NameError。

加 from `__future__` import annotations 后编译器把注解当作字符串常量存进去（PEP 563），避免前向引用与循环类型依赖在定义时求值失败，`typing.get_type_hints` 再按 globalns / localns 把字符串 eval 回类型对象。

关键是 CPython 的字节码里没有任何基于注解的类型检查指令：传错类型照样执行，直到具体操作失败才报错。真正的约束力来自静态检查器，它们读注解构建类型图、做推断与控制流收窄，Any 会让检查器在该处停止报错。

Protocol 走结构化子类型，检查的是对象是否具备协议成员而非继承关系，因此 isinstance 需要 @runtime_checkable 且只验证成员存在。注解与运行时校验因此是两个不同层次的契约。

**注解与运行时校验的分工**

| 维度 | 类型注解 | pydantic / 运行时校验 |
| --- | --- | --- |
| 执行者 | mypy / pyright 静态检查器 | 程序运行时执行 |
| 失败时机 | CI 或编辑器里报错 | 外部输入进入时抛校验错误 |
| 对 CPython | 只是 __annotations__ 元数据，不强制 | 会真实解析、转换、拒绝数据 |
| 适用边界 | 内部 API、函数签名、IDE 补全 | 跨服务 / 用户输入 / 配置加载 |
| 误用 | 到处写 Any 等于关掉检查器 | 拿它替代注解则失去静态补全 |

<Compare :panels='[{"label": "主示例", "code": "import typing\nfrom typing import get_type_hints\n\ndef distance(a: int, b: int = 0) -&gt; float:\n    return float(a - b)\n\nh = get_type_hints(distance)\nprint(sorted(h))\nprint([h[k].__name__ for k in (&#39;a&#39;, &#39;b&#39;, &#39;return&#39;)])\nprint(distance.__annotations__[&#39;a&#39;] is int)\nprint(str(int | None))\nprint(get_type_hints(distance) == distance.__annotations__)", "note": "注解只是元数据：存储与求值"}, {"label": "对照 / 进阶", "code": "from typing import Protocol, runtime_checkable, TypedDict, Literal, TYPE_CHECKING\n\n@runtime_checkable\nclass Closeable(Protocol):\n    def close(self) -&gt; None: ...\n\nclass Config(TypedDict):\n    host: str\n    port: int\n\nMode = Literal[&#39;r&#39;, &#39;w&#39;]\n\nclass File:\n    def close(self) -&gt; None:\n        pass\n\nprint(isinstance(File(), Closeable))\nprint(Config.__annotations__)\nprint(sorted(Config.__required_keys__))\nprint(Mode)\nprint(TYPE_CHECKING)", "note": "联合、泛型与结构化子类型"}]' title='两种写法对照' note='差异集中在 注解不强制运行时检查；先看输出，再找背后的规则。' />

<Callout type="tip" title='核心心智模型' text='函数注解存在 fn.__annotations__ 这个字典里，类与模块级的注解写在各自的 __annotations__；变量注解 x: int 只登记注解、并不会创建名字绑定，随后读 x 会抛 NameError: name &#39;x&#39; is not defined。注解默认在定义时求值并存为对象，' />


## 跨服务 payload：注解给静态检查，运行时校验另写一层

一个事件接入层收到的 dict 来自外部服务，注解能告诉 IDE 与 mypy 每个键应该是什么类型，却拦不住上游真的传一个字符串 id。工程上必须分两层：用 TypedDict 加 Literal 把结构写成可被静态检查的契约，再写一个显式 validate 在入口处检查键集合、枚举取值与字段类型，拒绝不合格的输入。

下面用标准库实现这两层：Event 声明 kind 只能是 click 或 view、user_id 是 int、ts 是 float；validate 逐一核对并给出可读的错误原因；最后用三条不同的 payload 演示放行与两类拒绝。

真实项目把 validate 换成 pydantic 模型即可，但分层思想不变：注解不替代运行时校验。

```python
from typing import TypedDict, Literal, get_type_hints

class Event(TypedDict):
    kind: Literal['click', 'view']
    user_id: int
    ts: float

def validate(raw):
    hints = get_type_hints(Event)
    if set(raw) != set(hints):
        return 'bad keys'
    if raw['kind'] not in ('click', 'view'):
        return 'bad kind'
    if not isinstance(raw['user_id'], int):
        return 'bad user_id'
    return 'ok'

print(validate({'kind': 'click', 'user_id': 7, 'ts': 1.0}))
print(validate({'kind': 'buy', 'user_id': 7, 'ts': 1.0}))
print(validate({'kind': 'click', 'user_id': '7', 'ts': 1.0}))
print(sorted(get_type_hints(Event)))
```

<Callout type="idea" title='落地提示' text='公共 API、跨服务数据结构、配置模型优先加注解，并在 CI 里跑 mypy / pyright 让契约自动生效' />

<CheckList id='P036b' title='上线前自检' :items='["能复现并解释「以为加了类型注解运行时就会校验，传错类型照样跑」", "能复现并解释「为过检查器到处写 Any，错误被悄悄放过」", "能复现并解释「注解里引用后面才定义的类，定义时抛 NameError」", "能用一条命令验证 注解不强制运行时检查", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import importlib.util; print(importlib.util.find_spec('json').origin)"
```

把输入换成你自己的数据，观察结果是否仍符合 **注解不强制运行时检查** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 以为加了类型注解运行时就会校验，传错类型照样跑 | 注解只是 __annotations__ 元数据，CPython 不生成检查字节码 | 在 CI 里跑 mypy / pyright 让注解产生约束力；跨服务输入另用 pydantic 做运行时校验 |
| 为过检查器到处写 Any，错误被悄悄放过 | Any 让静态检查器在该处停止推断与报错，等于局部关掉检查 | 用 object 加 isinstance 收窄、具体联合或 TypeVar；把 Any 控制在真正的动态边界 |
| 注解里引用后面才定义的类，定义时抛 NameError | 注解默认在定义时求值，前向引用的名字此刻还不存在 | 加 from __future__ import annotations 把注解字符串化，或用引号写成前向引用字符串 |

<Callout type="warn" title='本讲最容易踩的坑' text='以为加了类型注解运行时就会校验，传错类型照样跑：注解只是 __annotations__ 元数据，CPython 不生成检查字节码' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：以为加了类型注解运行时就会校验，传错类型照样", "body": "注解只是 __annotations__ 元数据，CPython 不生成检查字节码", "tip": "在 CI 里跑 mypy / pyright 让注解产生约束力；跨服务输入另用 pydantic 做运行时校验"}, {"title": "第 2 步：为过检查器到处写 Any，错误被悄悄放过", "body": "Any 让静态检查器在该处停止推断与报错，等于局部关掉检查", "tip": "用 object 加 isinstance 收窄、具体联合或 TypeVar；把 Any 控制在真正的动态边界"}, {"title": "第 3 步：注解里引用后面才定义的类，定义时抛 Name", "body": "注解默认在定义时求值，前向引用的名字此刻还不存在", "tip": "加 from __future__ import annotations 把注解字符串化，或用引号写成前向引用字符串"}]' />


## 给关键路径加注解：练习与自测

<Exercise title='基础：读注解并验证运行时不校验' task='定义带注解的函数，打印 __annotations__ 的键与 get_type_hints 解析出的类型名，再故意传入错误类型观察是否报错。' solution='from typing import get_type_hints\n\ndef f(a: int, b: str = &#39;x&#39;) -&gt; bool:\n    return True\n\nprint(sorted(f.__annotations__))\nh = get_type_hints(f)\nprint(h[&#39;a&#39;].__name__, h[&#39;return&#39;].__name__)\nprint(f(&#39;not-an-int&#39;, 3))' explain='注解只是元数据，CPython 不检查类型；传错参数函数仍返回 True，约束力要靠 mypy / pyright。' />

<Exercise title='进阶：Protocol 结构化子类型' task='用 @runtime_checkable 定义一个只含方法 close 的 Protocol，给两个类分别实现与不实现它，打印 isinstance 结果。' solution='from typing import Protocol, runtime_checkable\n\n@runtime_checkable\nclass Closable(Protocol):\n    def close(self) -&gt; None: ...\n\nclass A:\n    def close(self) -&gt; None:\n        pass\n\nclass B:\n    def run(self) -&gt; None:\n        pass\nprint(isinstance(A(), Closable), isinstance(B(), Closable))' explain='Protocol 按成员判定而非继承：A 有 close 方法所以满足，B 没有则不满足；runtime_checkable 只检查成员是否存在、不校验签名。' />

<Quiz no='036-1' q='关于类型注解的运行时行为，下面哪项准确？' :options='["只是 __annotations__ 元数据，CPython 不强制检查", "运行时会自动做 isinstance 校验", "会改变字节码从而提速", "必须配 pydantic 才能书写"]' answer="0" explain='注解默认是元数据，字节码里没有类型检查指令；约束力来自静态检查器，运行时校验是另一层的事。' />

<Quiz no='036-2' q='Optional[int] 在 3.10 及以后等价于？' :options='["int | None", "Union[int, str]", "list[int]", "Any"]' answer="0" explain='PEP 604 引入 X | Y 后 Optional[X] 就等价于 X | None，isinstance 与联合类型对象也可据此判断。' />

<Quiz no='036-3' q='要让 Protocol 支持 isinstance 判断，需要？' :options='["加 @runtime_checkable，且它只校验方法成员存在", "让类显式继承该 Protocol", "给类加 @dataclass", "调用 get_type_hints"]' answer="0" explain='结构化子类型本不需要继承；@runtime_checkable 让 isinstance 可用，但只检查成员是否存在、不校验方法签名。' />

<FillBlank no='036-F' tpl='___ typing' :answers='["import"]' hint='回想本讲关于 注解不强制运行时检查 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 注解只是元数据：存储与求值 的落点。' />

<KnowledgeCard :points='["注解只是 __annotations__ 元数据，CPython 运行时不校验、不提速；约束力来自 mypy / pyright", "变量注解 x: int 只写 __annotations__、不绑定名字，随后读 x 抛 NameError: name &#39;x&#39; is not defined", "from __future__ import annotations（PEP 563, 3.7+）把注解字符串化，get_type_hints 再解析回类型对象", "PEP 585（3.9）内建泛型 list[int]；PEP 604（3.10）X | None；PEP 695（3.12）def f[T] 与 type 别名", "Protocol（3.8+）结构化子类型需 @runtime_checkable 才能 isinstance（只查方法成员）；TypedDict / Literal 约束 dict 字段与字面量", "Any 等于局部关掉检查器；注解与 pydantic 运行时校验是两件事，跨服务输入必须运行时验证；TYPE_CHECKING 打破类型导入的循环"]' :pitfalls='["以为加了类型注解运行时就会校验，传错类型照样跑", "为过检查器到处写 Any，错误被悄悄放过", "注解里引用后面才定义的类，定义时抛 NameError", "用 Any 到处灭火，等于把检查器关掉；类型注解与运行时校验（pydantic）是两件事，不要互相代替"]' summary='注解默认只是元数据，真正的约束力来自静态检查器；渐进式类型允许先给关键路径加注解，再逐步铺开' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 注解只是 __annotations__ 元数据，CPython 运行时不校验、不提速；约束力来自 mypy / pyright | 建立直觉 |
| 变量注解 x: int 只写 __annotations__、不绑定名字，随后读 x 抛 NameError: name 'x' is not defined | 跑通示例 |
| from __future__ import annotations（PEP 563, 3.7+）把注解字符串化，get_type_hints 再解析回类型对象 | 深入边界 |
| PEP 585（3.9）内建泛型 list[int]；PEP 604（3.10）X \| None；PEP 695（3.12）def f[T] 与 type 别名 | 工程落地 |
| Protocol（3.8+）结构化子类型需 @runtime_checkable 才能 isinstance（只查方法成员）；TypedDict / Literal 约束 dict 字段与字面量 | 随堂检测 |
| Any 等于局部关掉检查器；注解与 pydantic 运行时校验是两件事，跨服务输入必须运行时验证；TYPE_CHECKING 打破类型导入的循环 | 复盘 |

<CheckList id='P036a' title='学完你应当能' :items='["能讲清 注解只是元数据：存储与求值", "能讲清 联合、泛型与结构化子类型", "能讲清 渐进式类型落地与运行时校验的分界", "能在工程里处理 mypy 与 pyright"]' />

1. 注解只是 __annotations__ 元数据，CPython 运行时不校验、不提速；约束力来自 mypy / pyright

2. 变量注解 x: int 只写 __annotations__、不绑定名字，随后读 x 抛 NameError: name 'x' is not defined

3. from __future__ import annotations（PEP 563, 3.7+）把注解字符串化，get_type_hints 再解析回类型对象

[下一讲：阶段综合：缓存装饰器库与插件注册表](/functions/capstone)

<Predict no='036-P' q='def f(a: int) -&gt; int: return a；print(f.__annotations__[&#39;a&#39;] is int, &#39;a&#39; in f.__code__.co_varnames) 输出什么？' :options='["True True", "True False", "False True"]' answer='0' output='True True' explain='注解在 3.13 默认求值，值就是 int 类型对象；a 同时是形参名，会登记进 code object 的 co_varnames。' />
