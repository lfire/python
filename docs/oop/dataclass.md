---
title: 第 047 讲 · dataclass、attrs 与 pydantic 模型
description: 选对数据建模工具并理解校验边界
---

<StageHeader stage='L4 · 面向对象' level='★★★☆☆' time='35 分钟' goal='选对数据建模工具并理解校验边界' prereq='第 046 讲 · 反射与自省：getattr、inspect 与 __dict__' />

# 第 047 讲 · dataclass、attrs 与 pydantic 模型

能定制类、能自省之后，还有个实际的累赘：为只装数据的类，`__init__`、`__repr__`、`__eq__` 要手写一大段，外部数据又未必干净。生成样板方法与在入口挡住脏数据，其实是两层不同的事。

一个接口服务把外部 `JSON` 喂给写了类型注解的请求模型，以为能拦住格式不对的值，脏数据却一路流到扣款才暴露。本讲先拆开 `dataclass` 在类创建期生成了什么，再看 `field`、`frozen` 与哈希的联动，最后把边界层的运行时校验和内部对象分开摆。需要类与实例、类型注解与第 41 讲的特殊方法；学完你能选对建模工具，也明白注解只是元数据、校验该放哪一层。


## 一份外部配置直接塞进 dataclass 后类型全错了

一个接口服务把外部 `JSON` 直接喂给一个 `@dataclass` 的请求模型，开发同学以为写了 `amount: int` 就会拦住脏数据，结果字符串 `'12'` 和负数原样进了领域层，直到扣款时才爆出类型错误，异常栈离入口已经隔了五层。

另一处工单来自缓存：有人给 dataclass 字段写了 `tags: list = []`，所有实例共享同一个列表，一个请求 `append` 之后，后续请求全带着别人的标签；

这个写法只要 `@dataclass` 真正生效，类创建期就会抛 `ValueError`、提示可变默认值要改用 `default_factory`，是旧代码绕过了装饰器，才让这份共享状态留到线上。

还有人给 dataclass 加了 `frozen=True` 就宣称对象「不可变」，字段里却装着 `list`，内容照样被改。`dataclass`、`attrs`、`pydantic` 解决的是三层不同的问题：样板方法生成、可选的数据类增强、以及运行时校验。

本讲把 `dataclass` 到底生成了什么、`field` 与 `frozen` / `order` 的联动、以及边界层的校验职责讲清楚，避免把注解当成校验器。

<Callout type="warn" title='先看一个真实会出错的写法' text='可变默认值写成 tags: list = []：类创建期 dataclass 检测到可变默认值会抛 ValueError: mutable default ... use default_factory；绕过装饰器时则所有实例共享同一个列表' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 046 讲 · 反射与自省：getattr、inspect 与 __dict__ |
| 难度 / 建议时长 | ★★★☆☆ · 35 分钟 |
| 本讲新增 | dataclass 生成了什么、field 与 default_factory、frozen 与 order |
| 一句话目标 | 选对数据建模工具并理解校验边界 |
| 为下一讲铺垫 | 阶段综合：最小 ORM 与校验框架 |


## @dataclass 主要参数、默认值与引入版本

**@dataclass 主要参数、默认值与引入版本**

| 参数 | 默认值 | 作用 | 版本 |
| --- | --- | --- | --- |
| init | True | 生成 __init__ | 3.7 |
| repr | True | 生成 __repr__ | 3.7 |
| eq | True | 生成 __eq__ | 3.7 |
| order | False | 生成四个比较方法，要求 eq=True | 3.7 |
| frozen | False | 冻结字段绑定，抛 FrozenInstanceError | 3.7 |
| unsafe_hash | False | 可变实例上强制生成 __hash__ | 3.7 |
| match_args | True | 生成 __match_args__ | 3.10 |
| kw_only | False | 全部字段改为仅关键字 | 3.10 |
| slots | False | 重建类并加 __slots__ | 3.10 |
| weakref_slot | False | 给 slots 类加 __weakref__ | 3.11 |

<Callout type="tip" title='核心心智模型' text='`@dataclass` 是类装饰器，在类创建之后读取 `__annotations__` 与类属性，用动态生成的函数源码补齐样板方法，再挂回类上。它的默认取值是 `init=True`、`repr=True`、`eq=True`、`order=False`、`unsafe_hash=False`…' />


## dataclass 在类创建期生成了什么，不生成什么

`@dataclass` 是类装饰器，在类创建之后读取 `__annotations__` 与类属性，用动态生成的函数源码补齐样板方法，再挂回类上。

它的默认取值是 `init=True`、`repr=True`、`eq=True`、`order=False`、`unsafe_hash=False`、`frozen=False`、`match_args=True`、`kw_only=False`、`slots=False`、`weakref_slot=False`。

默认生成 `__init__`、`__repr__`、`__eq__`；`order=True` 时额外生成 `__lt__` / `__le__` / `__gt__` / `__ge__`（要求 `eq=True`，否则抛 `ValueError`），按字段定义顺序组装元组比较；

`unsafe_hash=True` 在 `eq=True` 且未冻结时强制生成一个 `__hash__`（之所以叫 unsafe，是因为字段可变会破坏哈希契约）。

它不生成任何运行时类型校验：注解只是元数据，构造时把 `'12'` 赋给 `amount: int` 完全合法；也不做事后赋值拦截，普通实例可随时改字段。`__post_init__` 在 `__init__` 末尾被调用，是放显式校验或派生字段的钩子。

`dataclasses.asdict` / `astuple` / `replace` / `fields` / `is_dataclass` 提供转换与内省，`asdict` 会递归把嵌套 dataclass 转成字典。

`slots=True`（3.10+）因 `__slots__` 必须在类创建期确定，会重新创建一个类对象返回，类装饰器与注册表里引用的旧类需重新绑定。

```python
from dataclasses import dataclass, field, FrozenInstanceError

@dataclass(frozen=True, order=True)
class Item:
    name: str
    qty: int = 0
    tags: list = field(default_factory=list, repr=False, compare=False)

a = Item('pen', 2)
b = Item('pen', 2)
print('eq', a == b, 'lt', Item('pen', 1) < a)
print('hash', hash(a) == hash(b))
print('repr', repr(a))
print('post', a.tags, a.qty)
try:
    a.qty = 9
except FrozenInstanceError as e:
    print(type(e).__name__)
```

<OutputBox title='主示例运行结果' output='eq True lt True\nhash True\nrepr Item(name=&#39;pen&#39;, qty=2)\npost [] 2\nFrozenInstanceError' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from dataclasses import dataclass, field, FrozenInstanceError\n\n@dataclass(frozen=True, order=True)\nclass Item:\n    name: str\n    qty: int = 0\n    tags: list = field(default_factory=list, repr=False, compare=False)\n\na = Item(&#39;pen&#39;, 2)\nb = Item(&#39;pen&#39;, 2)\nprint(&#39;eq&#39;, a == b, &#39;lt&#39;, Item(&#39;pen&#39;, 1) &lt; a)\nprint(&#39;hash&#39;, hash(a) == hash(b))\nprint(&#39;repr&#39;, repr(a))\nprint(&#39;post&#39;, a.tags, a.qty)\ntry:\n    a.qty = 9\nexcept FrozenInstanceError as e:\n    print(type(e).__name__)' :notes='["导入 dataclass、field 与 FrozenInstanceError", "空行，只用于分隔逻辑块，不影响执行结果。", "空行分隔导入与类定义", "frozen=True 且 order=True，同时开启哈希生成与比较方法", "非默认字段 name 排在最前", "带默认值的 qty，参与比较与哈希", "可变默认值用 default_factory，repr/compare 都关掉", "空行，只用于分隔逻辑块，不影响执行结果。", "空行分隔定义与验证", "构造第一个实例，tags 由工厂生成空列表", "构造字段相同的第二个实例", "eq 按参与 compare 的字段判等；order 生成 __lt__", "frozen+eq 时自动生成 __hash__，相等者哈希相等", "repr 排除 repr=False 的 tags，只显示 name 与 qty", "default_factory 生效，tags 是独立的空列表", "尝试给冻结实例的字段重新赋值", "frozen 把 __setattr__ 换成抛 FrozenInstanceError 的版本", "打印异常类型，它是 AttributeError 的子类"]' title='第 047 讲 · dataclass、attrs 与 pydantic 模型' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### _process_class 如何拼出 __init__ 与 __repr__

`dataclass` 装饰器在类创建完成后运行：它读 `__annotations__` 与类属性，按字段顺序用 `exec` 生成 `__init__` 等方法的源码，再 `setattr` 到类上，因此注解从头到尾都只是元数据，不参与任何赋值检查。

`frozen=True` 时生成的方法把 `__setattr__` / `__delattr__` 替换成抛 `FrozenInstanceError` 的版本，而生成的 `__init__` 内部改用 `object.__setattr__` 绕过限制完成初始赋值；

它只冻结字段绑定，不改字段值对象本身。哈希联动直接复用第 41 讲的规则：`eq=True` 且未冻结时把 `__hash__` 设为 `None`，`frozen=True` 时按参与 `compare` 的字段生成哈希，这正是值对象可直接进 `set` 的原因。

`slots=True` 之所以要重建类，是因为 `__slots__` 必须由 `type.__new__` 在类创建期处理，装饰器介入太晚，只能新建一个类对象返回。

`pydantic` 则完全不同：它在 `__init__` 里按字段类型做解析与强制转换，把字符串 `'12'` 变成 `int`，逐字段收集错误后抛 `ValidationError`，属于运行时校验层而非代码生成层。

<ConceptDiagram type='layers3' title='第 047 讲 · dataclass 在类创建期生成了什么，不生成什么' labels='dataclass 在类创建期生成了什么，不…|field、frozen、order 与哈希…|校验边界：dataclass、attrs、p…|与 ORM 的边界' caption='选对数据建模工具并理解校验边界' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## field、frozen、order 与哈希联动的具体规则

`field()` 控制单个字段：`default` 给默认值，`default_factory` 给可变默认值的工厂，`list`、`dict`、`set` 都必须用它，否则类创建期抛 `ValueError`；

`init` 决定是否进 `__init__` 参数，`repr` / `compare` / `hash` 分别控制是否进 repr、是否参与比较与哈希，`metadata` 挂自定义元信息。默认值之后不能再放无默认值字段，否则 `__init__` 签名非法；

3.10 起可用 `KW_ONLY` 哨兵或 `kw_only=True` 把后续字段改成仅关键字参数。

这和普通函数避开可变默认参数是同一个道理，通常写成下面这段代码，用 `None` 作哨兵、把建列表推迟到每次调用；

```python
def f(x, acc=None):
    if acc is None:
        acc = []
```

`default_factory` 只是把这件事交给 `dataclass` 在每个实例上各做一次。

`frozen=True` 把 `__setattr__` / `__delattr__` 换成抛 `dataclasses.FrozenInstanceError` 的版本（它是 `AttributeError` 的子类），生成 `__init__` 时内部用 `object.__setattr__` 绕过这个限制；

它冻结的是「字段绑定」，字段值本身若是 `list` / `dict` 仍可被原地修改，真正不可变要把字段换成 `tuple` 或 `frozenset`。哈希联动与第 41 讲一致：`eq=True` 且 `frozen=False` 时 `__hash__` 被设为 `None`；

`eq=True` 且 `frozen=True` 时按参与 `compare` 的字段自动生成 `__hash__`；

`eq=False` 则保留 `object.__hash__`。

`order=True` 生成的比较方法在字段多时是 Python 层元组比较，热路径不如直接实现。

```python
from dataclasses import dataclass, field, asdict, replace

@dataclass
class Bag:
    items: list = field(default_factory=list)

b = Bag()
b.items.append('x')
print('asdict', asdict(b))
print('replace', replace(b, items=['y']))
try:
    @dataclass
    class Bad:
        items: list = []
except ValueError as e:
    print(type(e).__name__, 'mutable default')
```

<OutputBox title='对照写法：先自己猜，再点开' output='asdict {&#39;items&#39;: [&#39;x&#39;]}\nreplace Bag(items=[&#39;y&#39;])\nValueError mutable default' guess="true" />


### eq / frozen / unsafe_hash 组合下的 __hash__

**eq / frozen / unsafe_hash 组合下的 __hash__**

| 组合 | __hash__ 结果 | 能否哈希 |
| --- | --- | --- |
| eq=True, frozen=False | 被设为 None | 不能 |
| eq=True, frozen=True | 按 compare 字段自动生成 | 能 |
| eq=False | 保留 object.__hash__ | 能，按 id |
| eq=True, frozen=False, unsafe_hash=True | 强制生成 | 能，但字段可变会破坏契约 |
| 显式自定义 __hash__ | 保留自定义函数 | 能 |

<Term word='dataclass 生成了什么' text='`@dataclass` 是类装饰器，在类创建之后读取 `__annotations__` 与类属性，用动态生成的函数源码补齐样板方法，再挂回类上。它的默认取值是 `init=True`、`repr=True`、`eq=True`、`order=False`、`unsafe_hash=False`…' />

<Term word='field 与 default_factory' text='`field()` 控制单个字段：`default` 给默认值，`default_factory` 给可变默认值的工厂，`list`、`dict`、`set` 都必须用它，否则类创建期抛 `ValueError`；`init` 决定是否进 `__init__` 参数，`repr` / `compare`…' />


## 校验边界：dataclass、attrs、pydantic 分层使用

三者不在同一层竞争。`dataclass` 是标准库，只在类创建期生成样板方法，零运行时校验、零第三方依赖，适合内部领域对象与配置快照。`attrs` 是第三方库，功能与 `dataclass` 相近但提供更细的转换器 `converter` 与校验器 `validator`，可在赋值时跑校验，适合需要更丰富声明式能力的老项目。

`pydantic`（v2 用 Rust 核心重写）在实例化时按字段类型做解析、强制转换与验证：字符串 `'12'` 会被转成 `int` 12，缺失必填字段或类型完全不符会抛 `ValidationError` 并附带逐字段错误位置，它是边界层（接口请求体、消息队列、配置文件）的正确工具。

工程上的分层是：外部输入先经 `pydantic` 校验并转成干净值，再构造 `frozen` 的 `dataclass` 作为内部领域对象在业务层流转，ORM 映射与数据库校验又是另一层。把脏数据直接交给 `dataclass`，错误会推迟到业务深处才暴露；

反过来给所有内部对象套 `pydantic`，则把校验开销带进了不需要它的热路径。认清「生成样板 / 赋值校验 / 实例化解析」三条职责，选型就不会摇摆。

```python
from dataclasses import dataclass, fields
import inspect

@dataclass
class Plain:
    x: int
@dataclass(frozen=True)
class Frozen:
    x: int

print('generated:', [n for n in ('__init__', '__repr__', '__eq__') if n in Plain.__dict__])
print('hash plain:', Plain.__hash__)
print('hash frozen:', Frozen.__hash__ is not None)
print('field names:', [f.name for f in fields(Plain)])
print('params:', [p for p in inspect.signature(dataclass).parameters if p in ('init', 'repr', 'eq')])
```

<OutputBox title='原理验证' output='generated: [&#39;__init__&#39;, &#39;__repr__&#39;, &#39;__eq__&#39;]\nhash plain: None\nhash frozen: True\nfield names: [&#39;x&#39;]\nparams: [&#39;init&#39;, &#39;repr&#39;, &#39;eq&#39;]' />

<CodeTabs :tabs='[{"label": "主示例", "code": "from dataclasses import dataclass, field, FrozenInstanceError\n\n@dataclass(frozen=True, order=True)\nclass Item:\n    name: str\n    qty: int = 0\n    tags: list = field(default_factory=list, repr=False, compare=False)\n\na = Item(&#39;pen&#39;, 2)\nb = Item(&#39;pen&#39;, 2)\nprint(&#39;eq&#39;, a == b, &#39;lt&#39;, Item(&#39;pen&#39;, 1) &lt; a)\nprint(&#39;hash&#39;, hash(a) == hash(b))\nprint(&#39;repr&#39;, repr(a))\nprint(&#39;post&#39;, a.tags, a.qty)\ntry:\n    a.qty = 9\nexcept FrozenInstanceError as e:\n    print(type(e).__name__)", "note": "dataclass 在类创建期生成了什么，不生成什么"}, {"label": "对照 / 进阶", "code": "from dataclasses import dataclass, field, asdict, replace\n\n@dataclass\nclass Bag:\n    items: list = field(default_factory=list)\n\nb = Bag()\nb.items.append(&#39;x&#39;)\nprint(&#39;asdict&#39;, asdict(b))\nprint(&#39;replace&#39;, replace(b, items=[&#39;y&#39;]))\ntry:\n    @dataclass\n    class Bad:\n        items: list = []\nexcept ValueError as e:\n    print(type(e).__name__, &#39;mutable default&#39;)", "note": "field、frozen、order 与哈希联动的具体规则"}]' title='两种写法切换看' />


## dataclass / attrs / pydantic 分层

**dataclass / attrs / pydantic 分层**

| 工具 | 校验时机 | 第三方依赖 | 适用层 |
| --- | --- | --- | --- |
| dataclass | 不校验，仅生成样板方法 | 标准库 | 内部领域对象、配置快照 |
| attrs | converter / validator 可在赋值时校验 | 第三方 | 需要声明式增强的老项目 |
| pydantic v2 | 实例化时按类型解析、转换、验证 | 第三方（Rust 核心） | HTTP / MQ / 配置等边界层 |
| ORM 层 | 持久化时按列约束校验 | 取决于框架 | 数据库写入前 |

<FlowTimeline :steps='[{"title": "dataclass 在类创建期生成了什么，不生成…", "desc": "`@dataclass` 是类装饰器，在类创建之后读取…", "tone": "blue"}, {"title": "field、frozen、order 与哈希联动…", "desc": "`field()` 控制单个字段：`default` 给默认值…", "tone": "purple"}, {"title": "校验边界：dataclass、attrs、pyd…", "desc": "三者不在同一层竞争。`dataclass` 是标准库，只在类创建期生成样板方法，零运…", "tone": "orange"}, {"title": "工程落地", "desc": "配置边界层：显式校验后再构造 frozen 领域对象", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 配置边界层：显式校验后再构造 frozen 领域对象

服务启动时读一份配置字典，端口可能是字符串、越界数字，主机可能为空。直接把这些值塞进 `dataclass`，注解 `int` 不会拦任何东西，错误会推迟到建立连接时才暴露。

正确的分层是：边界层用标准库显式做类型与范围校验，并把多个问题聚合成一条错误（这正是 `pydantic` 的职责，本例为可运行用标准库实现），校验通过后才构造 `frozen` 的 `dataclass` 作为内部不可变配置在业务层流转。下面跑通合法配置、空主机、越界端口、字符串端口四种输入，打印被拒绝的原因与成功构造的对象。

要点：校验发生在构造之前、领域对象冻结之后不再被改动、错误聚合一次返回全部问题。

真实项目把 `validate` 换成 `pydantic.BaseModel` 即可，分层保持不变。

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    host: str
    port: int
    retries: int = 3

def validate(raw):
    errors = []
    port = raw.get('port')
    if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
        errors.append('port must be int in 1..65535')
    host = raw.get('host')
    if not isinstance(host, str) or not host:
        errors.append('host must be non-empty str')
    if errors:
        raise ValueError('; '.join(errors))
    return Config(host=host, port=port, retries=raw.get('retries', 3))

print(validate({'host': 'db.local', 'port': 5432}))
for bad in [{'host': '', 'port': 5432}, {'host': 'x', 'port': 70000}, {'host': 'x', 'port': '80'}]:
    try:
        validate(bad)
    except ValueError as e:
        print('rejected:', str(e))
print('frozen value:', validate({'host': 'h', 'port': 80}).port)
```

<Callout type="idea" title='落地提示' text='边界层（HTTP、消息队列、配置文件）用 pydantic 校验，内部领域对象用 frozen dataclass' />

<CheckList id='P047b' title='上线前自检' :items='["能复现并解释「可变默认值写成 tags: list = []」", "能复现并解释「把外部输入直接交给 dataclass 以为注解会校验」", "能复现并解释「以为 frozen=True 让对象彻底不可变」", "能用一条命令验证 dataclass 生成了什么", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "print(type('Demo', (), {}).__mro__)"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 dataclass 生成了什么 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 可变默认值写成 tags: list = [] | 类创建期 dataclass 检测到可变默认值会抛 ValueError: mutable default ... use default_factory；绕过装饰器时则所有实例共享同一个列表 | 用 field(default_factory=list)，每次实例化调用工厂生成独立对象 |
| 把外部输入直接交给 dataclass 以为注解会校验 | 注解只是元数据，dataclass 不生成运行时类型检查，脏数据会流到业务深处才爆 | 边界层用 pydantic 做解析与校验，或在 __post_init__ 里显式检查；内部对象再用 frozen dataclass |
| 以为 frozen=True 让对象彻底不可变 | frozen 只冻结字段绑定（替换 __setattr__），字段值若是 list/dict 仍可原地修改 | 把可变字段换成 tuple / frozenset，或在 __post_init__ 里做防御性拷贝后再存 |

<Callout type="warn" title='本讲最容易踩的坑' text='可变默认值写成 tags: list = []：类创建期 dataclass 检测到可变默认值会抛 ValueError: mutable default ... use default_factory；绕过装饰器时则所有实例共享同一个列表' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：可变默认值写成 tags: list = […", "body": "类创建期 dataclass 检测到可变默认值会抛 ValueError: mutable default ... use default_factory；绕过装饰器时则所有实例共享同一个列表", "tip": "用 field(default_factory=list)，每次实例化调用工厂生成独立对象"}, {"title": "第 2 步：把外部输入直接交给 dataclass 以为…", "body": "注解只是元数据，dataclass 不生成运行时类型检查，脏数据会流到业务深处才爆", "tip": "边界层用 pydantic 做解析与校验，或在 __post_init__ 里显式检查；内部对象再用 frozen dataclass"}, {"title": "第 3 步：以为 frozen=True 让对象彻底不可…", "body": "frozen 只冻结字段绑定（替换 __setattr__），字段值若是 list/dict 仍可原地修改", "tip": "把可变字段换成 tuple / frozenset，或在 __post_init__ 里做防御性拷贝后再存"}]' />


## 选对工具再动手

<Exercise title='基础：用 field 与 frozen 构造可哈希值对象' task='定义 frozen dataclass Point，字段 x、y 为 int，另加一个 default_factory=list 且不参与 compare 的 labels；验证两个相同 Point 相等且哈希相等，并说明 labels 为何不进哈希。' solution='from dataclasses import dataclass, field\n@dataclass(frozen=True)\nclass Point:\n    x: int\n    y: int\n    labels: list = field(default_factory=list, compare=False)\na, b = Point(1, 2), Point(1, 2)\nprint(a == b, hash(a) == hash(b), a.labels is b.labels)' explain='compare=False 的字段既不参与 __eq__ 也不参与自动生成的 __hash__，因此相等判定只看 x、y；default_factory 让每个实例拿到独立列表，labels is 比较为 False。' />

<Exercise title='进阶：给边界层写错误聚合校验' task='写一个 validate(raw) 校验 name 为非空 str、age 为 0..150 的 int，收集全部错误后一次抛出；对三条脏数据分别打印错误信息，并说明为什么比遇错即抛更适合表单场景。' solution='def validate(raw):\n    errors = []\n    name, age = raw.get(&#39;name&#39;), raw.get(&#39;age&#39;)\n    if not isinstance(name, str) or not name.strip():\n        errors.append(&#39;name required&#39;)\n    if not isinstance(age, int) or isinstance(age, bool) or not 0 &lt;= age &lt;= 150:\n        errors.append(&#39;age must be int 0..150&#39;)\n    if errors:\n        raise ValueError(&#39;; &#39;.join(errors))\n    return (name, age)\nfor d in [{&#39;name&#39;: &#39;&#39;, &#39;age&#39;: -1}, {&#39;name&#39;: &#39;a&#39;, &#39;age&#39;: 200}, {&#39;name&#39;: &#39;a&#39;, &#39;age&#39;: 20}]:\n    try:\n        print(&#39;ok&#39;, validate(d))\n    except ValueError as e:\n        print(&#39;errors&#39;, str(e))' explain='错误聚合一次返回所有字段问题，用户可一次改完；遇错即抛只能看到第一个。isinstance(age, bool) 排除 bool 是因为它是 int 子类，否则 True 会被当成 1 通过。' />

<Quiz no='047-1' q='给 dataclass 写 tags: list = [] 会怎样？' :options='["类创建期抛 ValueError，提示 use default_factory", "正常运行，每个实例有独立列表", "所有实例共享一个列表但不报错", "自动生成 default_factory=list"]' answer="0" explain='dataclass 检测到 list/dict/set 这类可变默认值时在类创建期就抛 ValueError: mutable default ... use default_factory，避免实例间共享可变状态。' />

<Quiz no='047-2' q='eq=True 且 frozen=True 的 dataclass，其 __hash__ 是？' :options='["按参与 compare 的字段自动生成，实例可进 set", "被设为 None", "继承 object.__hash__ 按 id", "需要 unsafe_hash=True 才有"]' answer="0" explain='冻结后字段不再变，满足哈希契约，dataclass 按 compare=True 的字段生成 __hash__；未冻结的 eq=True 类则把 __hash__ 设 None。unsafe_hash 是给可变类强行开哈希的逃生口。' />

<Quiz no='047-3' q='外部 HTTP 请求体的类型校验应放在哪一层？' :options='["边界层用 pydantic 解析校验，再转内部 frozen dataclass", "直接交给 dataclass 让注解拦", "全部用 object 类型跳过校验", "只在数据库写入时校验"]' answer="0" explain='dataclass 注解不产生运行时校验，脏数据会流进业务深处；pydantic 在实例化时解析、转换并聚合逐字段错误，适合 HTTP/MQ/配置等边界，内部领域对象再用 frozen dataclass。' />

<Predict no='047-4' q='frozen dataclass 的字段里放一个 list，调用 a.labels.append(&#39;x&#39;) 会怎样？' :options='["成功修改，frozen 只冻结字段绑定不冻结值对象", "抛 FrozenInstanceError", "抛 AttributeError"]' answer='0' output='成功修改，a.labels 仍是那个 list' explain='frozen=True 替换的是 __setattr__，拦的是 a.labels = ... 这种重新绑定；对已有 list 的原地 append 不经过 __setattr__，因此内容可变。要真正不可变得把字段换成 tuple。' />

<FillBlank no='047-5' tpl='from dataclasses  ___ dataclass, field, FrozenInstanceError' :answers='["import"]' hint='回想本讲关于 dataclass 生成了什么 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 dataclass 在类创建期生成了什么，不生成什么 的落点。' />

<KnowledgeCard :points='["dataclass 只在类创建期生成 __init__/__repr__/__eq__ 等样板，注解不产生运行时校验", "可变默认值必须 field(default_factory=list)，否则 ValueError: mutable default", "order=True 要求 eq=True；unsafe_hash 是给可变类强行开哈希的逃生口", "frozen=True 只冻结字段绑定（抛 FrozenInstanceError），字段值若是 list/dict 仍可变", "eq+frozen 自动生成按 compare 字段的 __hash__；eq 且未冻结则 __hash__ = None", "边界层用 pydantic 解析校验，内部用 frozen dataclass；@dataclass(slots=True) 3.10+ 会重建类"]' :pitfalls='["可变默认值写成 tags: list = []", "把外部输入直接交给 dataclass 以为注解会校验", "以为 frozen=True 让对象彻底不可变", "把外部输入直接交给 dataclass，类型注解不会拦住任何脏数据，错误会推迟到业务深处才爆"]' summary='dataclass 只在类创建时生成样板方法，不做事后校验；pydantic 在实例化时按类型强制转换与验证，两者解决的是不同层的问题' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| dataclass 只在类创建期生成 __init__/__repr__/__eq__ 等样板，注解不产生运行时校验 | 建立直觉 |
| 可变默认值必须 field(default_factory=list)，否则 ValueError: mutable default | 跑通示例 |
| order=True 要求 eq=True；unsafe_hash 是给可变类强行开哈希的逃生口 | 深入边界 |
| frozen=True 只冻结字段绑定（抛 FrozenInstanceError），字段值若是 list/dict 仍可变 | 工程落地 |
| eq+frozen 自动生成按 compare 字段的 __hash__；eq 且未冻结则 __hash__ = None | 随堂检测 |
| 边界层用 pydantic 解析校验，内部用 frozen dataclass；@dataclass(slots=True) 3.10+ 会重建类 | 复盘 |

1. dataclass 只在类创建期生成 __init__/__repr__/__eq__ 等样板，注解不产生运行时校验

2. 可变默认值必须 field(default_factory=list)，否则 ValueError: mutable default

3. order=True 要求 eq=True；unsafe_hash 是给可变类强行开哈希的逃生口

[下一讲：阶段综合：最小 ORM 与校验框架](/oop/capstone)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/047-dataclass.py`

```bash
python3 examples/lessons/047-dataclass.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/047-dataclass.py) · [全部示例代码索引](/examples/)
