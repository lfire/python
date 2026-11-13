---
title: 第 048 讲 · 阶段综合：最小 ORM 与校验框架
description: 用描述符加元类交付一个可扩展的框架雏形
---

<StageHeader stage='L4 · 面向对象' level='★★★★★' time='60 分钟' goal='用描述符加元类交付一个可扩展的框架雏形' prereq='第 047 讲 · dataclass、attrs 与 pydantic 模型' />

# 第 048 讲 · 阶段综合：最小 ORM 与校验框架

描述符、特殊方法、元类、上下文协议，这几讲的能力齐了。这一讲不添新语法，而是把它们装到一起：在类里声明字段，就自动得到表结构、输入校验和写库语句。阶段综合的意义，是看这些知识怎么咬合成能跑的整体。

一个报表框架首版把校验写在 `__init__` 里，对象创建后一句赋值就绕过去；次版拼 SQL，一个引号就坏了整条语句。本讲先讲字段描述符与元类收集如何把声明翻译成运行时行为，再把校验固定到每次赋值并做错误聚合，最后用参数化查询把数据与 SQL 分开。需要第 40 讲的描述符与第 45 讲的元类；完成后你能交付可扩展的最小 ORM 雏形，作为阶段四的出口。


## 需求：交付一个可扩展的最小 ORM 雏形

一个内部报表框架要求开发者在类里声明字段就能自动生成表、校验输入、写入数据库。

第一版把校验写在 `__init__` 里，结果对象创建后业务代码直接 `obj.uid = 'abc'` 就绕过了校验，脏数据照样落库；

第二版把 SQL 用字符串拼接生成，某次字段名里带了引号，整条语句被破坏，还差点变成注入漏洞；第三版用元类收集字段，却在 `__init__` 里遍历类字典，发现拿到的顺序和声明顺序不一致，生成的列顺序全乱。这些正是把描述符、元类、校验、SQL 拼到一起时最容易踩的坑。

阶段综合这一讲不再引入新语法，而是把前几讲的能力组装成一个最小但完整的 ORM 雏形：描述符负责每次赋值都过校验，元类负责把声明翻译成映射，参数化查询负责把数据与 SQL 文本彻底分开，错误聚合负责一次返回全部问题。

<Callout type="warn" title='先看一个真实会出错的写法' text='用字符串拼接生成 INSERT 语句：值进入 SQL 语法文本，引号或分号会破坏语句甚至追加语句，形成注入面' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段四 · 面向对象与元编程 |
| 前置 | 第 047 讲 · dataclass、attrs 与 pydantic 模型 |
| 难度 / 建议时长 | ★★★★★ · 60 分钟 |
| 本讲新增 | 字段描述符、元类收集映射、实例状态存储 |
| 一句话目标 | 用描述符加元类交付一个可扩展的框架雏形 |
| 为下一讲铺垫 | CPython 编译流程：AST 到字节码 |

<CheckList id='P048a' title='学完你应当能' :items='["能讲清 声明式到运行时：描述符与元类各管一段", "能讲清 校验与错误聚合：把校验固定在 __set__ 上", "能讲清 SQL 参数化、可测试性与绕过元类的调试开关", "能在工程里处理 测试策略"]' />


## 最小 ORM 各组件与职责

**最小 ORM 各组件与职责**

| 组件 | 钩子 / 方法 | 职责 | 放在这一层的理由 |
| --- | --- | --- | --- |
| 字段描述符 | __set__ / __set_name__ | 每次赋值校验、记住列名 | 数据描述符优先于 __dict__，覆盖构造与事后修改 |
| 元类 | __new__(mcls, name, bases, ns) | 收集 Field、生成 _table | 命名空间在此尚未被后续钩子改动 |
| 实例状态 | _data 字典 | 集中存字段值 | 避免字段名与内部属性冲突 |
| 错误聚合 | Model.__init__ 循环捕获 | 一次返回全部校验错误 | 遇错即抛只能看到第一个问题 |
| SQL 生成 | statement() / params() | 列名、占位符、参数同序 | 列名来自受控映射而非用户字符串 |
| 持久化 | sqlite3.execute(sql, params) | 参数化写入 | 值与 SQL 文本分离，杜绝注入 |

<Callout type="tip" title='核心心智模型' text='框架的核心翻译是「类里写字段」→「运行时表结构与行为」，这段翻译由两个钩子分工完成。描述符（第 40 讲）管实例级：`Field` 实现 `__set__`（数据描述符，优先级高于实例 `__dict__`），因此无论 `__init__` 里赋值还是事后 `obj.x = value`，都必然经过' />


## 设计取舍：描述符存值、元类收集映射

数据描述符（定义了 `__set__` 或 `__delete__`）在 `PyObject_GenericGetAttr` 的查找链里优先级高于实例 `__dict__`，所以任何一次 `obj.x = value` 都会落到 `Field.__set__`，这是「校验不可绕过」的底层依据；

只写在 `__init__` 里的校验没有这层保障。

元类 `__new__` 运行在 `type.__new__` 分配 `PyTypeObject` 的过程中，此时 `ns` 仍是类体执行完的原样映射，`__set_name__` 与 `__init_subclass__` 也在同一阶段回调，因此在这里扫描 `ns` 得到的字段声明顺序最可靠；

晚到元类 `__init__` 时类已定型。sqlite3 的 `?` 占位符走 `sqlite3_bind_*` 系列 C API：SQL 文本先被编译成 prepared statement，值按位置绑定为数据，注入串里的引号、分号、注释符都不参与语法解析；字符串拼接则把值直接送进解析器，一个未转义引号就能改变语句结构。

错误聚合用列表收集再 join，本质是把「多个独立校验失败」从控制流异常转成一次数据返回，便于表单类调用方一次展示全部问题。

<ArchBlueprint title='第 048 讲 · 分层视角' caption='把本讲三个机制放进系统分层，点击每层看职责与失败处理' :layers='[{"name": "触发与入口", "note": "声明式到运行时：描述符与元类各管一段", "protocol": "调用 / 请求", "items": [{"label": "声明式到运行时：描述符与", "sub": "输入与前置", "detail": "框架的核心翻译是「类里写字段」→「运行时表结构与行为」，这段翻译由两个钩子分工完成。描述符（第 40 讲）管实例级：`Field` 实现 `__set__`（数据描述符，优先级高于实例 `__dict__`），因此无论 `__init__` 里赋值还是事后 `obj.x = value`，都必然经过", "tone": "blue"}]}, {"name": "核心规则", "note": "校验与错误聚合：把校验固定在 __set__ 上", "protocol": "语言 / 运行时协议", "items": [{"label": "校验与错误聚合：把校验固", "sub": "状态与边界", "detail": "把类型校验写进 `__init__` 是最常见的漏洞：它只覆盖构造时传入的值，构造之后任何一次赋值都能绕过。数据描述符 `__set__` 在属性查找链里优先级高于实例 `__dict__`，因此是唯一能覆盖「构造 + 事后修改」的入口——`Field.__set__` 里先 `isinstance", "tone": "purple"}]}, {"name": "落地与收尾", "note": "SQL 参数化、可测试性与绕过元类的调试开关", "items": [{"label": "SQL 参数化、可测试性", "sub": "工程处理", "detail": "SQL 必须参数化：sqlite3 用 `?` 占位符，值通过 `execute(sql, params)` 传给 `sqlite3_bind_*` 系列 C API，作为数据与 SQL 文本分离，注入串里的引号、分号只会当成普通字符，不参与语法解析；字符串拼接则让值进入语法树，字段名或值里带一个引", "tone": "green"}]}]' />

<FlowTimeline :steps='[{"title": "声明式到运行时：描述符与元类各管一段", "desc": "框架的核心翻译是「类里写字段」→「运行时表结构与行为」，这段翻译由两个钩子分工完成。…", "tone": "blue"}, {"title": "校验与错误聚合：把校验固定在 __set__ 上", "desc": "把类型校验写进 `__init__` 是最常见的漏洞：它只覆盖构造时传入的值，构造之…", "tone": "purple"}, {"title": "SQL 参数化、可测试性与绕过元类的调试开关", "desc": "SQL 必须参数化：sqlite3 用 `?` 占位符，值通过 `execute(s…", "tone": "orange"}, {"title": "工程落地", "desc": "可运行的最小 ORM：校验、聚合、参数化写入一气呵成", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 声明式到运行时：描述符与元类各管一段

框架的核心翻译是「类里写字段」→「运行时表结构与行为」，这段翻译由两个钩子分工完成。

描述符（第 40 讲）管实例级：`Field` 实现 `__set__`（数据描述符，优先级高于实例 `__dict__`），因此无论 `__init__` 里赋值还是事后 `obj.x = value`，都必然经过它，校验与状态写入可以固定在同一个入口；

`__set_name__`（3.6 / PEP 487）在 `type.__new__` 里被回调，让字段对象记住自己的列名，不用开发者重复写 `uid = Field('uid')`。

元类（第 45 讲）管类级：`__new__` 扫描类命名空间 `ns.items()`，把 `isinstance(v, Field)` 的项收进 `_fields` 映射，并生成 `_table`；

这一步必须在 `__new__`，因为 `__set_name__` 与 `__init_subclass__` 也在 `type.__new__` 内执行，等到了元类 `__init__`，命名空间可能已被改动、顺序也不再可靠。

实例状态统一放在一个 `_data` 字典里，避免字段名与内部属性打架。把三层分开后，声明式写法只负责表达意图，运行时行为由框架集中生成，新增模型不需要重复写 SQL 或校验代码。

```python
class Field:
    def __init__(self, typ):
        self.typ = typ
    def __set_name__(self, owner, name):
        self.name = name
    def __set__(self, obj, value):
        if not isinstance(value, self.typ):
            raise TypeError(self.name + ' needs ' + self.typ.__name__)
        obj._data[self.name] = value

class Meta(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        cls._fields = tuple(k for k, v in ns.items() if isinstance(v, Field))
        cls._table = name.lower() + 's'
        return cls

class Model(metaclass=Meta):
    def __init__(self, **kw):
        object.__setattr__(self, '_data', {})
        for k, v in kw.items():
            setattr(self, k, v)

class User(Model):
    uid = Field(int)
    name = Field(str)

u = User(uid=1, name='ann')
print('fields', sorted(u._fields))
print('values', u._data['uid'], u._data['name'])
try:
    User(uid='x', name='ann')
except TypeError as e:
    print('rejected', str(e))
```

<OutputBox title='主示例运行结果' output='fields [&#39;name&#39;, &#39;uid&#39;]\nvalues 1 ann\nrejected uid needs int' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Field:\n    def __init__(self, typ):\n        self.typ = typ\n    def __set_name__(self, owner, name):\n        self.name = name\n    def __set__(self, obj, value):\n        if not isinstance(value, self.typ):\n            raise TypeError(self.name + &#39; needs &#39; + self.typ.__name__)\n        obj._data[self.name] = value\n\nclass Meta(type):\n    def __new__(mcls, name, bases, ns):\n        cls = super().__new__(mcls, name, bases, ns)\n        cls._fields = tuple(k for k, v in ns.items() if isinstance(v, Field))\n        cls._table = name.lower() + &#39;s&#39;\n        return cls\n\nclass Model(metaclass=Meta):\n    def __init__(self, **kw):\n        object.__setattr__(self, &#39;_data&#39;, {})\n        for k, v in kw.items():\n            setattr(self, k, v)\n\nclass User(Model):\n    uid = Field(int)\n    name = Field(str)\n\nu = User(uid=1, name=&#39;ann&#39;)\nprint(&#39;fields&#39;, sorted(u._fields))\nprint(&#39;values&#39;, u._data[&#39;uid&#39;], u._data[&#39;name&#39;])\ntry:\n    User(uid=&#39;x&#39;, name=&#39;ann&#39;)\nexcept TypeError as e:\n    print(&#39;rejected&#39;, str(e))' :notes='["字段描述符，负责实例级校验与状态写入", "保存期望类型", "校验时按 self.typ 做 isinstance", "__set_name__ 由 type.__new__ 回调", "把属性名记到描述符上，省去重复声明", "__set__ 是数据描述符，构造与事后赋值都经过它", "类型不符时进入失败分支", "抛带字段名的 TypeError，供上层聚合", "校验通过才把值写进统一的 _data 字典", "元类负责把类声明翻译成运行时映射", "__new__ 在类创建期扫描 namespace，顺序可靠", "调用 super().__new__ 拿到真正的类对象", "收集所有 Field，生成字段顺序元组", "按类名推导表名", "必须 return 类对象", "模型基类统一放实例状态与构造逻辑", "接收关键字参数构造", "用 object.__setattr__ 初始化 _data，避开描述符", "逐个字段赋值", "setattr 触发 Field.__set__ 走校验", "声明式模型：类里只写字段", "uid 列要求 int", "name 列要求 str", "构造合法实例", "元类收集的字段名排序后打印", "值统一存在 _data，字段名作键", "尝试用字符串给 int 字段赋值", "User(...) 触发构造期校验", "捕获 __set__ 抛出的 TypeError", "打印校验失败的具体字段与期望类型"]' title='第 048 讲 · 阶段综合：最小 ORM 与校验框架' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 先落地 Field 描述符与 __set_name__ 命名

```python
import sqlite3

conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE logs (msg TEXT)')
def safe_insert(msg):
    conn.execute('INSERT INTO logs (msg) VALUES (?)', (msg,))
def unsafe_insert(msg):
    q = chr(39)
    conn.execute('INSERT INTO logs (msg) VALUES (' + q + msg + q + ')')
attack = 'x' + chr(39) + '); DROP TABLE logs; --'
safe_insert('plain')
safe_insert(attack)
print('safe rows:', conn.execute('SELECT COUNT(*) FROM logs').fetchone()[0])
try:
    unsafe_insert(attack)
except sqlite3.Error:
    print('unsafe SQL failed as expected')
conn.close()
```

<OutputBox title='对照写法：先自己猜，再点开' output='safe rows: 2\nunsafe SQL failed as expected' guess="true" />

<Term word='字段描述符' text='框架的核心翻译是「类里写字段」→「运行时表结构与行为」，这段翻译由两个钩子分工完成。描述符（第 40 讲）管实例级：`Field` 实现 `__set__`（数据描述符，优先级高于实例 `__dict__`），因此无论 `__init__` 里赋值还是事后 `obj.x = value`，都必然经过它，校验与状态写入可' />

<Term word='元类收集映射' text='把类型校验写进 `__init__` 是最常见的漏洞：它只覆盖构造时传入的值，构造之后任何一次赋值都能绕过。数据描述符 `__set__` 在属性查找链里优先级高于实例 `__dict__`，因此是唯一能覆盖「构造 + 事后修改」的入口——`Field.__set__` 里先 `isinstance(value, se' />


## 校验与错误聚合：把校验固定在 __set__ 上

把类型校验写进 `__init__` 是最常见的漏洞：它只覆盖构造时传入的值，构造之后任何一次赋值都能绕过。

数据描述符 `__set__` 在属性查找链里优先级高于实例 `__dict__`，因此是唯一能覆盖「构造 + 事后修改」的入口——`Field.__set__` 里先 `isinstance(value, self.typ)` 校验，通过才写 `obj._data[self.name]`，不通过抛带字段名的 `TypeError`。

错误聚合则解决「表单里五个字段错了三个，却只报第一个」的体验问题：`Model.__init__` 用一个 `errors` 列表循环构造，捕获每个 `TypeError` 追加字符串，循环结束后若非空再抛 `ValueError`，消息用 `'; '.join(errors)` 拼成一条，一次返回全部问题。

要注意 `isinstance(value, bool)` 对 `int` 字段会通过（`bool` 是 `int` 子类），金额、端口这类字段应显式排除 bool；

默认值、可空字段也要在 `Field` 上表达，而不是散落在业务代码里。校验规则属于领域层，SQL 生成属于持久化层，两者不要混在描述符里：描述符只判定「这个值合不合法」，字段名到列类型、占位符个数由 `Model` 的方法统一计算。这样单测可以分别覆盖校验与 SQL 两段。

```python
import inspect

class Field:
    def __set_name__(self, owner, name):
        self.name = name
class Meta(type):
    def __new__(mcls, name, bases, ns):
        cls = super().__new__(mcls, name, bases, ns)
        cls._fields = [k for k, v in ns.items() if isinstance(v, Field)]
        return cls
class Form(metaclass=Meta):
    a = Field()
    b = Field()
print('fields:', sorted(Form._fields))
print('metaclass:', type(Form).__name__)
print('descriptor names:', Form.a.name, Form.b.name)
print('mro:', [c.__name__ for c in inspect.getmro(Form)])
```

<OutputBox title='原理验证' output='fields: [&#39;a&#39;, &#39;b&#39;]\nmetaclass: Meta\ndescriptor names: a b\nmro: [&#39;Form&#39;, &#39;object&#39;]' />


## 再落地元类在 __new__ 里按声明顺序收集列

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用字符串拼接生成 INSERT 语句", "body": "值进入 SQL 语法文本，引号或分号会破坏语句甚至追加语句，形成注入面", "tip": "列名取自受控 _fields，值一律用 ? 占位符配 execute(sql, params) 绑定"}, {"title": "第 2 步：把类型校验只写在 __init__ 里", "body": "对象创建后 obj.uid = &#39;x&#39; 直接写进 __dict__，绕过校验，脏数据落库", "tip": "用数据描述符 Field.__set__ 做校验，构造与事后赋值共用同一入口"}, {"title": "第 3 步：在元类 __init__ 里收集字段导致列顺", "body": "__set_name__ 与 __init_subclass__ 已在 __new__ 内跑过，__init__ 拿到的是改动后的类且无法改 bases", "tip": "字段扫描放 __new__ 的 ns.items()，列名、占位符、params 都从同一个 _fields 按序生成"}]' />

<ConceptDiagram type='hub4' title='第 048 讲 · 声明式到运行时：描述符与元类各管一段' labels='声明式到运行时：描述符与元类各管一段|校验与错误聚合：把校验固定在 __set__|SQL 参数化、可测试性与绕过元类的调试开关' caption='用描述符加元类交付一个可扩展的框架雏形' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## SQL 参数化、可测试性与绕过元类的调试开关

SQL 必须参数化：sqlite3 用 `?` 占位符，值通过 `execute(sql, params)` 传给 `sqlite3_bind_*` 系列 C API，作为数据与 SQL 文本分离，注入串里的引号、分号只会当成普通字符，不参与语法解析；

字符串拼接则让值进入语法树，字段名或值里带一个引号就可能破坏语句甚至执行额外语句。

生成语句时，列名来自 `_fields` 这个受控映射（不是用户字符串），占位符个数等于字段数，params 按同一顺序组装成元组，即 `tuple`；

```python
tuple(self._data[k] for k in self._fields)
```

三者顺序必须一致，错一处就会插入错列。框架还应保持小而透明：暴露明确的注册与字段 API、每个阶段可单独单测（校验、建表、插入、查询各一个断言）、以及绕过元类的调试开关——在排查「某个字段没被收集」时，能直接打印 `ns` 与 `_fields` 比在元类里打日志高效得多。

真实项目还要处理迁移、事务（第 42 讲）、连接池与并发，但骨架就是这三层；把参数化从一开始就设计进去，比事后给所有 SQL 打补丁便宜得多。

<Compare :panels='[{"label": "主示例", "code": "class Field:\n    def __init__(self, typ):\n        self.typ = typ\n    def __set_name__(self, owner, name):\n        self.name = name\n    def __set__(self, obj, value):\n        if not isinstance(value, self.typ):\n            raise TypeError(self.name + &#39; needs &#39; + self.typ.__name__)\n        obj._data[self.name] = value\n\nclass Meta(type):\n    def __new__(mcls, name, bases, ns):\n        cls = super().__new__(mcls, name, bases, ns)\n        cls._fields = tuple(k for k, v in ns.items() if isinstance(v, Field))\n        cls._table = name.lower() + &#39;s&#39;\n        return cls\n\nclass Model(metaclass=Meta):\n    def __init__(self, **kw):\n        object.__setattr__(self, &#39;_data&#39;, {})\n        for k, v in kw.items():\n            setattr(self, k, v)\n\nclass User(Model):\n    uid = Field(int)\n    name = Field(str)\n\nu = User(uid=1, name=&#39;ann&#39;)\nprint(&#39;fields&#39;, sorted(u._fields))\nprint(&#39;values&#39;, u._data[&#39;uid&#39;], u._data[&#39;name&#39;])\ntry:\n    User(uid=&#39;x&#39;, name=&#39;ann&#39;)\nexcept TypeError as e:\n    print(&#39;rejected&#39;, str(e))", "note": "声明式到运行时：描述符与元类各管一段"}, {"label": "对照 / 进阶", "code": "import sqlite3\n\nconn = sqlite3.connect(&#39;:memory:&#39;)\nconn.execute(&#39;CREATE TABLE logs (msg TEXT)&#39;)\ndef safe_insert(msg):\n    conn.execute(&#39;INSERT INTO logs (msg) VALUES (?)&#39;, (msg,))\ndef unsafe_insert(msg):\n    q = chr(39)\n    conn.execute(&#39;INSERT INTO logs (msg) VALUES (&#39; + q + msg + q + &#39;)&#39;)\nattack = &#39;x&#39; + chr(39) + &#39;); DROP TABLE logs; --&#39;\nsafe_insert(&#39;plain&#39;)\nsafe_insert(attack)\nprint(&#39;safe rows:&#39;, conn.execute(&#39;SELECT COUNT(*) FROM logs&#39;).fetchone()[0])\ntry:\n    unsafe_insert(attack)\nexcept sqlite3.Error:\n    print(&#39;unsafe SQL failed as expected&#39;)\nconn.close()", "note": "校验与错误聚合：把校验固定在 __set__ 上"}]' title='两种写法对照' note='差异集中在 字段描述符；先看输出，再找背后的规则。' />

**SQL 拼接与参数化对照**

| 维度 | 字符串拼接 | ? 占位符参数化 |
| --- | --- | --- |
| 值的位置 | 进入 SQL 语法文本 | 作为绑定数据单独传递 |
| 引号 / 分号 | 可能破坏语句或追加语句 | 一律当普通字符 |
| 多语句 execute | 可能抛 ProgrammingError | 单条语句，行为确定 |
| 字段名来源 | 常混用用户输入 | 来自 _fields 受控映射 |
| 底层调用 | 拼接后的整串交给解析器 | sqlite3_bind_* 按位置绑定 |


## 可运行的最小 ORM：校验、聚合、参数化写入一气呵成

把前面三层组装成一个能直接跑的雏形：`Field` 是带类型校验的数据描述符，`Meta` 在 `__new__` 里收集字段与表名，`Model` 构造时聚合全部 `TypeError` 成一条 `ValueError`，`statement()` 生成带 `?` 占位符的 `INSERT`，`params()` 按同一 `_fields` 顺序取值，最后用 sqlite3 内存库真实写入并回查。

下面同时演示两件事：合法对象成功落库，以及一条含两个错误字段的输入被一次报出全部问题。真实框架还会补事务（第 42 讲）、迁移与连接池，但骨架已经把「声明 → 映射 → 校验 → 参数化 SQL」这条链路完整闭合，且每个阶段都能单独单测。

```python
import sqlite3
class Field:
    def __init__(self, typ):
        self.typ = typ
    def __set_name__(self, owner, name):
        self.name = name
    def __set__(self, obj, value):
        if not isinstance(value, self.typ):
            raise TypeError(self.name + ' expects ' + self.typ.__name__)
        obj._data[self.name] = value
class Meta(type):
    def __new__(m, name, bases, ns):
        cls = super().__new__(m, name, bases, ns)
        cls.fields = tuple(k for k, v in ns.items() if isinstance(v, Field))
        cls.table = name.lower() + 's'
        return cls
class Model(metaclass=Meta):
    def __init__(self, **kw):
        object.__setattr__(self, '_data', {})
        errors = []
        for k, v in kw.items():
            try:
                setattr(self, k, v)
            except TypeError as e:
                errors.append(str(e))
        if errors:
            raise ValueError('; '.join(errors))
    def stmt(self):
        marks = ', '.join('?' for _ in self.fields)
        return 'INSERT INTO ' + self.table + ' (' + ', '.join(self.fields) + ') VALUES (' + marks + ')'
class User(Model):
    uid = Field(int)
    name = Field(str)
conn = sqlite3.connect(':memory:')
conn.execute('CREATE TABLE users (uid INTEGER, name TEXT)')
u = User(uid=1, name='ann')
conn.execute(u.stmt(), tuple(u._data[k] for k in u.fields))
print('rows', conn.execute('SELECT * FROM users').fetchall())
try:
    User(uid='x', name=1)
except ValueError as e:
    print('errors', str(e))
conn.close()
```

<Callout type="idea" title='落地提示' text='保持框架小而透明：暴露明确的注册 API、可单测的每个阶段、以及绕过元类的调试开关' />

<CheckList id='P048b' title='上线前自检' :items='["能复现并解释「用字符串拼接生成 INSERT 语句」", "能复现并解释「把类型校验只写在 __init__ 里」", "能复现并解释「在元类 __init__ 里收集字段导致列顺序错乱」", "能用一条命令验证 字段描述符", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "print(type('Demo', (), {'x':1}).__mro__)"
```

把输入换成你自己的数据，观察结果是否仍符合 字段描述符 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 字符串拼 INSERT、只在 __init__ 校验、列顺序错乱的故障定位

**常见框架故障与定位**

| 现象 | 根因 | 修复 / 定位 |
| --- | --- | --- |
| 事后赋值绕过校验 | 校验只写在 __init__ | 改用数据描述符 __set__ 固定入口 |
| 字段收集顺序乱 | 在元类 __init__ 里遍历类字典 | 移到 __new__ 扫描 ns |
| 生成的列错位 | 列名、占位符、params 顺序不一致 | 三者都从同一个 _fields 元组按序生成 |
| 带引号的值破坏 SQL | 字符串拼接让值进入语法树 | 用 ? 占位符加 params 元组 |
| bool 通过 int 字段校验 | bool 是 int 子类 | 显式排除 isinstance(value, bool) |

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用字符串拼接生成 INSERT 语句 | 值进入 SQL 语法文本，引号或分号会破坏语句甚至追加语句，形成注入面 | 列名取自受控 _fields，值一律用 ? 占位符配 execute(sql, params) 绑定 |
| 把类型校验只写在 __init__ 里 | 对象创建后 obj.uid = 'x' 直接写进 __dict__，绕过校验，脏数据落库 | 用数据描述符 Field.__set__ 做校验，构造与事后赋值共用同一入口 |
| 在元类 __init__ 里收集字段导致列顺序错乱 | __set_name__ 与 __init_subclass__ 已在 __new__ 内跑过，__init__ 拿到的是改动后的类且无法改 bases | 字段扫描放 __new__ 的 ns.items()，列名、占位符、params 都从同一个 _fields 按序生成 |

<Callout type="warn" title='本讲最容易踩的坑' text='用字符串拼接生成 INSERT 语句：值进入 SQL 语法文本，引号或分号会破坏语句甚至追加语句，形成注入面' />


## sqlite3 的 prepare/bind 边界与语句缓存

正文把 SQL 参数化讲成数据与文本分开，再往下一层是 CPython 的 Modules/_sqlite/`statement.c`：pysqlite_statement_create 调用 SQLite 的 sqlite3_prepare_v2，把 SQL 文本编译成 sqlite3_stmt，也就是一串 `VDBE` 虚拟机指令；

问号占位符在 prepare 阶段就占好了绑定槽位，语法树此刻已经定型。

`execute(sql, params)` 走 pysqlite_statement_bind_parameters，对每个参数按类型挑 sqlite3_bind_int64 / sqlite3_bind_text / sqlite3_bind_null 之一，只往槽位里写数据，不会重新解析 SQL。

所以值里的引号、分号、注释符都只是被绑定的字节，进不了语法树；字符串拼接则让值在 prepare 之前就进入文本，多一个引号就能改变指令序列。

另一个常被漏看的数据结构是 Connection 的 cached_statements（默认 128，3.11 起可配）：它是一份 LRU，把 SQL 文本映射到已 prepare 的 sqlite3_stmt*，同语句重复执行直接跳过编译。

拼接式写法因为每条值都生成一份新文本，永远无法命中缓存，每次都要重新 prepare，这既慢又把语句缓存挤满。要分清两处边界：值可以参数化，标识符（表名、列名、`ORDER` BY 方向）不能，只能从受控映射里取并对双引号做转义；这也正是框架把列名锁在 _fields 里、只让占位符个数随字段数变化的原因。

<ConceptDiagram type='flow4' title='第 048 讲 · 扩展图解' labels='SQL 文本|sqlite3_prepare_v2|绑定槽位 sqlite3_bind|VDBE 执行' caption='参数化把值挡在语法树之外：prepare 先编译出语句对象，bind 只往预留槽位填数据，注入串里的引号与分号都成了普通字节。' />


### 字段集合沿 MRO 合并：dataclasses 的 _get_field 参照

```python
class Field:
    def __init__(self, typ):
        self.typ = typ
    def __set_name__(self, owner, name):
        self.name = name

def collect(cls):
    out = {}
    for base in reversed(cls.__mro__):
        for k, v in vars(base).items():
            if isinstance(v, Field):
                out[k] = v
            elif k in out:
                del out[k]
    return out

class Base:
    uid = Field(int)
    name = Field(str)

class User(Base):
    name = Field(str)
    age = Field(int)

fields = collect(User)
print('fields', list(fields))
print('uid name', fields['uid'].name)
print('age type', fields['age'].typ.__name__)

```

<OutputBox title='扩展示例运行结果' output='fields [&#39;uid&#39;, &#39;name&#39;, &#39;age&#39;]\nuid name uid\nage type int' />

<LineByLine code='class Field:\n    def __init__(self, typ):\n        self.typ = typ\n    def __set_name__(self, owner, name):\n        self.name = name\n\ndef collect(cls):\n    out = {}\n    for base in reversed(cls.__mro__):\n        for k, v in vars(base).items():\n            if isinstance(v, Field):\n                out[k] = v\n            elif k in out:\n                del out[k]\n    return out\n\nclass Base:\n    uid = Field(int)\n    name = Field(str)\n\nclass User(Base):\n    name = Field(str)\n    age = Field(int)\n\nfields = collect(User)\nprint(&#39;fields&#39;, list(fields))\nprint(&#39;uid name&#39;, fields[&#39;uid&#39;].name)\nprint(&#39;age type&#39;, fields[&#39;age&#39;].typ.__name__)\n' :notes='["Field 是数据描述符，__set_name__ 让字段记住自己在类里的名字", "typ 保存字段声明的类型，供校验与列类型映射使用", "把类型挂到实例上", "type_new_set_names 会在类创建期回调这个方法", "把 owner 与属性名记下来，避免开发者重复写字段名", "沿 MRO 反向遍历，基类字段先入表、子类覆盖后入表", "用有序 dict 保住字段声明顺序，它直接决定 CREATE TABLE 的列序", "reversed(__mro__) 保证最远的祖先先被收集", "vars(base) 只读该类自身的 __dict__，不混入继承来的属性", "子类同名 Field 覆盖基类字段，保留子类的类型", "子类若用非 Field 的同名属性覆盖，应从字段表里删除", "dataclasses 的 _get_field 也用同样的删除逻辑处理字段遮蔽", "返回按声明顺序排列的字段映射", "读回字段顺序，验证 uid 与 name 来自基类、age 来自子类", "校验固定在 __set__，错误聚合用列表收集后一次抛 ValueError，别遇错即抛", "列名来自受控 _fields；占位符数、params 长度、列顺序三者必须一致", "SQL 一律 ? 占位符配 execute(sql, params)，值与语法文本分离，杜绝拼接注入", "int 字段要显式排除 bool；保持框架小而透明，每阶段可单测并留绕过元类的调试开关", "描述符管实例级：__set__ 是数据描述符，覆盖构造与事后赋值；__set_name__ 记住列名", "元类管类级：__new__ 扫描 ns 收集 Field 并生成映射，顺序在此最可靠", "校验固定在 __set__，错误聚合用列表收集后一次抛 ValueError，别遇错即抛", "列名来自受控 _fields；占位符数、params 长度、列顺序三者必须一致", "SQL 一律 ? 占位符配 execute(sql, params)，值与语法文本分离，杜绝拼接注入", "int 字段要显式排除 bool；保持框架小而透明，每阶段可单测并留绕过元类的调试开关"]' title='扩展示例逐行讲解' />

<Term word='sqlite3_stmt' text='sqlite3_prepare_v2 把 SQL 文本编译出的 SQLite 虚拟机语句对象，占位符槽位在 prepare 阶段就固定；pysqlite 用 Connection.cached_statements 这份 LRU 缓存它，因此拼接式 SQL 因文本各不相同而永远无法命中缓存，每次都要重新编译。' />


### Unit of Work 与 identity map 的架构取舍

正文的 ORM 骨架是描述符管实例、元类管类，但真实框架还多一层持久化会话。SQLAlchemy 的 Session 维护四张表：identity_map 是一份以 (mapper, 主键) 为键的 WeakInstanceDict，保证同一主键在一次会话里只存在一个 Python 实例；

_new、_dirty、_deleted 分别挂着待 `INSERT`、待 `UPDATE`、待 `DELETE` 的对象。flush 时 UnitOfWork 按外键依赖对 mapper 做拓扑排序，一次性把变更按正确顺序发给数据库，而不是每次属性赋值都写库。

代价是脏检查：Session 默认给每个加载对象保存一份 committed_state 属性快照，flush 时逐属性比对，对象数量大时内存与 CPU 都随之上涨；

批量导入可改用 bulk_save_objects 绕开 identity map，或用 `expire_on_commit=False` 控制快照生命周期。

这是 Data Mapper 与 Active Record 的分水岭：Django ORM 让每个对象自己 save，接口直观但事务边界散落在业务代码、批量写入要额外封装；SQLAlchemy 把状态集中在 Session，复杂但能统一控制 flush 顺序、回滚与二级缓存。

选型看的是写入模式：交互式表单用 Active Record 省事，批量 ETL 与跨表事务用 Unit of Work 才能把 `INSERT` 顺序和一致性握在手里。

**骨架层与会话层的机制对照**

| 机制 | 所在层 | 解决的问题 | 引入的代价 |
| --- | --- | --- | --- |
| cached_statements | sqlite3 连接 | 复用 prepare 结果 | 拼接式 SQL 永远 miss |
| identity_map | Session | 同主键只存在一个实例 | 弱引用字典维护成本 |
| committed_state | Session | flush 时差量 UPDATE | 每个对象一份属性快照 |
| UnitOfWork 拓扑排序 | flush | 外键依赖顺序正确 | 依赖图构建与排序 |
| __set__ 数据描述符 | 实例 | 构造与事后赋值都校验 | 属性查找多一层 |


### 注入串的语句树差异实测

一次安全评审里，报表框架把用户填写的姓名直接拼进 `INSERT`，某条数据叫 x'); `DROP` `TABLE` users; --，拼接后的文本变成两条语句加一段注释。

在 3.13 的 sqlite3 上 execute 一次只允许一条语句，直接抛 ProgrammingError: You can only execute one statement at a time；换到允许多语句的驱动，第二条 `DROP` 就可能真的执行。

这不只是引号没转义的问题：值的字节参与了 prepare 阶段的语法解析，语句结构被改写。参数化把值挡在语法树之外，问号槽位先定型，bind 只填数据，注入串里的引号与分号都成了普通文本，读回时逐字节相等。还要注意列名与表名不能参数化，必须由 _fields 这类受控映射提供；

框架里 `CREATE` `TABLE` 的列名来自开发者声明，`INSERT` 的占位符个数等于字段数，params 按同一顺序组装，三者错一处就会插错列。下面的代码在内存库里同时跑拼接与参数化两条路径，用 ProgrammingError 与读回一致性把差异钉死；

注入串里的单引号用 `chr(39)` 拼出，避免示例源码里出现引号转义。

```python
import sqlite3

con = sqlite3.connect(':memory:')
con.execute('CREATE TABLE users (name TEXT)')
quote = chr(39)
evil = 'x' + quote + '); DROP TABLE users; --'
sql = 'INSERT INTO users VALUES (' + quote + evil + quote + ')'
try:
    con.execute(sql)
    print('concat', 'no error')
except sqlite3.Error as e:
    print('concat', type(e).__name__)
con.execute('INSERT INTO users VALUES (?)', (evil,))
row = con.execute('SELECT name FROM users').fetchone()
print('param roundtrip', row[0] == evil)
print('rows', con.execute('SELECT count(*) FROM users').fetchone()[0])

```


## 从框架雏形到交付

<Exercise title='基础：证明数据描述符能拦住事后赋值' task='用本讲的 Field 定义一个只接受 int 的模型，构造合法对象后执行 obj.uid = &#39;x&#39;，观察抛出的异常；再说明把校验写在 __init__ 为什么拦不住这一步。' solution='class F:\n    def __set_name__(self, o, n): self.n = n\n    def __set__(self, o, v):\n        if not isinstance(v, int): raise TypeError(self.n + &#39; needs int&#39;)\n        o._d[self.n] = v\nclass M:\n    def __init__(self): object.__setattr__(self, &#39;_d&#39;, {})\nclass R(M):\n    uid = F()\nr = R()\nr.uid = 1\ntry:\n    r.uid = &#39;x&#39;\nexcept TypeError as e:\n    print(&#39;caught&#39;, str(e))' explain='Field.__set__ 是数据描述符，优先级高于实例 __dict__，事后赋值也必经它；只写在 __init__ 的校验对构造后的赋值完全无效。' />

<Exercise title='进阶：给错误聚合补 bool 排除与占位符一致性断言' task='在校验里排除 bool 通过 int 字段的情况，并写一个断言检查 statement() 里 ? 的个数等于 params 长度，用一条含 True 的输入验证被拒绝。' solution='class F:\n    def __init__(self, t): self.t = t\n    def __set__(self, o, v):\n        if isinstance(v, bool) or not isinstance(v, self.t):\n            raise TypeError(&#39;bad &#39; + self.t.__name__)\n        o._d[id(self)] = v\nclass M:\n    def __init__(self): object.__setattr__(self, &#39;_d&#39;, {})\nclass R(M):\n    n = F(int)\nr = R()\ntry:\n    r.n = True\nexcept TypeError as e:\n    print(&#39;rejected&#39;, str(e))' explain='bool 是 int 子类，isinstance(True, int) 为 True，端口、金额等字段必须显式排除；占位符个数与 params 长度一致才能保证不错列，这类断言应随框架单测固化。' />

<Quiz no='048-1' q='把字段类型校验只写在 __init__ 里，最大的问题是？' :options='["对象创建后的赋值绕过校验，脏数据落库", "无法生成 __repr__", "元类无法收集字段", "SQL 无法参数化"]' answer="0" explain='__init__ 只覆盖构造时的入参；事后 obj.x = value 直接写实例字典。用数据描述符 __set__ 才能覆盖所有赋值路径。' />

<Quiz no='048-2' q='SQL 用 ? 占位符配 execute(sql, params)，值为什么不会改变语句结构？' :options='["值经 sqlite3_bind_* 绑定为数据，与 SQL 文本分离，不参与语法解析", "sqlite3 会自动转义所有引号", "参数只能是整数", "execute 会丢弃分号后的内容"]' answer="0" explain='SQL 先编译成 prepared statement，值按位置绑定为数据；引号、分号、注释符都只是普通字符。字符串拼接才会让值进入语法树。' />

<Quiz no='048-3' q='元类收集字段应放在哪个阶段？' :options='["__new__ 里扫描 ns.items()", "__init__ 里遍历类字典", "__set_name__ 里", "__init_subclass__ 里"]' answer="0" explain='__set_name__ 与 __init_subclass__ 都在 type.__new__ 内执行，等到了元类 __init__ 命名空间可能已被改动、顺序不可靠；在 __new__ 扫描 ns 最可靠。' />

<Predict no='048-4' q='User(uid=&#39;x&#39;, name=1) 经过错误聚合后会输出什么？' :options='["uid expects int; name expects str", "uid expects int", "TypeError: &#39;x&#39;"]' answer='0' output='uid expects int; name expects str' explain='Model.__init__ 循环捕获每个 TypeError 追加到 errors，循环结束后用 &#39;; &#39;.join 一次抛出 ValueError，因此两个字段的问题都会出现在同一条消息里。' />

<FillBlank no='048-5' tpl='___ __init__(self, typ):' :answers='["def"]' hint='回想本讲关于 字段描述符 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 声明式到运行时：描述符与元类各管一段 的落点。' />

<KnowledgeCard :points='["描述符管实例级：__set__ 是数据描述符，覆盖构造与事后赋值；__set_name__ 记住列名", "元类管类级：__new__ 扫描 ns 收集 Field 并生成映射，顺序在此最可靠", "校验固定在 __set__，错误聚合用列表收集后一次抛 ValueError，别遇错即抛", "列名来自受控 _fields；占位符数、params 长度、列顺序三者必须一致", "SQL 一律 ? 占位符配 execute(sql, params)，值与语法文本分离，杜绝拼接注入", "int 字段要显式排除 bool；保持框架小而透明，每阶段可单测并留绕过元类的调试开关"]' :pitfalls='["用字符串拼接生成 INSERT 语句", "把类型校验只写在 __init__ 里", "在元类 __init__ 里收集字段导致列顺序错乱", "用字符串拼接 SQL 会把注入漏洞写进框架，参数化查询必须在一开始就设计进去"]' summary='框架的核心是把声明式写法（类里写字段）翻译成运行时行为（表结构、校验、SQL），元类与描述符正好各管一段' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 描述符管实例级：__set__ 是数据描述符，覆盖构造与事后赋值；__set_name__ 记住列名 | 建立直觉 |
| 元类管类级：__new__ 扫描 ns 收集 Field 并生成映射，顺序在此最可靠 | 跑通示例 |
| 校验固定在 __set__，错误聚合用列表收集后一次抛 ValueError，别遇错即抛 | 深入边界 |
| 列名来自受控 _fields；占位符数、params 长度、列顺序三者必须一致 | 工程落地 |
| SQL 一律 ? 占位符配 execute(sql, params)，值与语法文本分离，杜绝拼接注入 | 随堂检测 |
| int 字段要显式排除 bool；保持框架小而透明，每阶段可单测并留绕过元类的调试开关 | 复盘 |

1. 描述符管实例级：__set__ 是数据描述符，覆盖构造与事后赋值；__set_name__ 记住列名

2. 元类管类级：__new__ 扫描 ns 收集 Field 并生成映射，顺序在此最可靠

3. 校验固定在 __set__，错误聚合用列表收集后一次抛 ValueError，别遇错即抛

[下一讲：CPython 编译流程：AST 到字节码](/core/compile-pipeline)
