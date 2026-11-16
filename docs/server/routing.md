---
title: 第 084 讲 · 路由、依赖注入与请求校验
description: 把入口层做成可测试、可复用的薄层
---

<StageHeader stage='L8 · 服务端与数据' level='★★★☆☆' time='35 分钟' goal='把入口层做成可测试、可复用的薄层' prereq='第 083 讲 · FastAPI / Flask / Django 选型' />

# 第 084 讲 · 路由、依赖注入与请求校验

框架定下来，最先动手写的就是那些接请求的函数。它们看着简单，却最容易越长越胖：本讲把入口收回成薄薄一层，只做校验、编排与响应映射，业务逻辑留在框架之外，好让测试不必惊动整个服务。

常见场面：下单函数里取当前用户、开数据库连接、查库存各写一遍，六十行里有二十行是重复样板；想补个参数校验的单测，才发现要先起服务、拼请求。我们看路径与查询参数怎么读进来，再用请求体与模型把校验挪出函数体，接着让依赖被声明、复用、也能整体替换，最后落到响应模型、状态码与统一错误处理。需要函数、装饰器、类型注解与依赖注入的印象；学完能把路由层写得可单测、可替换。


## 同一请求里 get_db 被解析三次，连接池被占满

一个下单接口最初把「解析 token 拿当前用户」「开数据库连接」「校验库存」三段逻辑全写在路由函数里，六十行代码里有二十行是重复的样板。等要补单元测试时才发现：测一个参数校验分支都得先起服务、造数据库连接、构造完整 `HTTP` 请求，跑一轮要几百毫秒，失败信息还指向框架内部。

更麻烦的是同一个请求里 `get_db` 被调用了三次，连接池被无谓占满。有人把它改成全局单例连接，并发下又串了数据。这些症状的根都在入口层没有分层：依赖该被声明、被复用、被整体替换，而不是在函数体里手工拼。本讲用标准库实现一个最小的依赖注入容器与参数校验器，把路由层还原成可测试的薄层。

<Callout type="warn" title='先看一个真实会出错的写法' text='同一请求里 get_db 被解析三次，连接池被占满：把 use_cache 关掉或在函数体里手工调用依赖函数，绕过了请求级缓存' />


## 把依赖写成声明：Depends 与依赖树

依赖注入的核心不是「自动传参」，而是把「我需要什么」与「怎么拿到」分开。

FastAPI 用 `Depends` 表达依赖：路径函数把 `user=Depends(get_user)`、`db=Depends(get_db)` 写成默认参数，`Depends` 对象就挂在函数的 `__defaults__` 里，框架启动时读 `inspect.signature` 与这些默认值，递归构建一棵依赖树。

关键规则是同一请求内依赖默认被缓存：`use_cache=True` 时，`get_db` 无论被 `endpoint` 直接依赖还是被 `get_user` 间接依赖，都只执行一次，结果存进请求级的缓存字典按 `(callable, security_scopes)` 取用；这是连接池不被重复占用的原因，也是「同一请求里拿到同一个 session」的保证。

把 `use_cache=False` 可强制每次重算，但会放大资源开销。

依赖树还能整体替换：测试里用 `dependency_overrides` 把 `get_db` 指向返回内存 sqlite 的假实现，路由函数一行不改。

生成器形式的依赖用 `yield` 交出资源，在响应后触发 `finally` 里的清理，正好用来提交或回滚事务、归还连接。

```python
import inspect

class Depends:
    def __init__(self, fn):
        self.fn = fn

def get_db():
    print('  open db')
    return {'conn': 'db-1'}

def get_user(db=Depends(get_db)):
    return {'uid': 7, 'db': db['conn']}

CACHE = {}
def resolve(callable_):
    if callable_ in CACHE:
        return CACHE[callable_]
    sig = inspect.signature(callable_)
    kwargs = {}
    for name, p in sig.parameters.items():
        if isinstance(p.default, Depends):
            kwargs[name] = resolve(p.default.fn)
    value = callable_(**kwargs)
    CACHE[callable_] = value
    return value

def endpoint(user=Depends(get_user), db=Depends(get_db)):
    return (user['uid'], db['conn'])

CACHE.clear()
print('result', resolve(endpoint))
print('cache keys', [f.__name__ for f in CACHE])
```

<OutputBox title='主示例运行结果' output='  open db\nresult (7, &#39;db-1&#39;)\ncache keys [&#39;get_db&#39;, &#39;get_user&#39;, &#39;endpoint&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import inspect\n\nclass Depends:\n    def __init__(self, fn):\n        self.fn = fn\n\ndef get_db():\n    print(&#39;  open db&#39;)\n    return {&#39;conn&#39;: &#39;db-1&#39;}\n\ndef get_user(db=Depends(get_db)):\n    return {&#39;uid&#39;: 7, &#39;db&#39;: db[&#39;conn&#39;]}\n\nCACHE = {}\ndef resolve(callable_):\n    if callable_ in CACHE:\n        return CACHE[callable_]\n    sig = inspect.signature(callable_)\n    kwargs = {}\n    for name, p in sig.parameters.items():\n        if isinstance(p.default, Depends):\n            kwargs[name] = resolve(p.default.fn)\n    value = callable_(**kwargs)\n    CACHE[callable_] = value\n    return value\n\ndef endpoint(user=Depends(get_user), db=Depends(get_db)):\n    return (user[&#39;uid&#39;], db[&#39;conn&#39;])\n\nCACHE.clear()\nprint(&#39;result&#39;, resolve(endpoint))\nprint(&#39;cache keys&#39;, [f.__name__ for f in CACHE])' :notes='["导入 inspect，用于读取每个可调用对象的参数表", "空行，只用于分隔逻辑块，不影响执行结果。", "定义依赖标记类，实例作为默认值挂在函数上", "构造方法是依赖实例的初始化入口", "把被依赖的函数对象保存到实例", "空行，只用于分隔逻辑块，不影响执行结果。", "定义资源型依赖，模拟开启数据库连接", "打印标记，便于观察它究竟执行了几次", "返回连接描述对象", "空行，只用于分隔逻辑块，不影响执行结果。", "定义依赖另一个依赖的函数，形成依赖树第二层", "组合出当前用户对象，db 由框架注入", "空行，只用于分隔逻辑块，不影响执行结果。", "请求级缓存字典，键是被依赖的函数对象", "resolve 是最小依赖解析器，递归解析整棵树", "命中缓存直接返回，保证同一请求只建一次连接", "把缓存值作为解析结果返回", "未命中则读取该函数的签名", "准备注入给它的关键字参数", "遍历参数，找出声明了 Depends 的项", "只接管标记过的参数，普通参数不处理", "递归解析子依赖，深度优先构建依赖树", "用解析好的参数调用目标函数", "把结果写回缓存，供后续共享", "返回解析值", "空行，只用于分隔逻辑块，不影响执行结果。", "定义端点，直接依赖 get_db、间接经 get_user 依赖它", "返回用户 id 与连接名，用于验证注入结果", "空行，只用于分隔逻辑块，不影响执行结果。", "清空缓存，模拟一个新请求开始", "解析端点；get_db 只打印一次即证明缓存生效", "列出被解析过的函数，看到完整的三层依赖树"]' title='第 084 讲 · 路由、依赖注入与请求校验' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<Callout type="tip" title='核心心智模型' text='依赖注入的核心不是「自动传参」，而是把「我需要什么」与「怎么拿到」分开。FastAPI 用 `Depends` 表达依赖：路径函数把 `user=Depends(get_user)`、`db=Depends(get_db)` 写成默认参数，`Depends` 对象就挂在函数的…' />

<ConceptDiagram type='compare2' title='第 084 讲 · 把依赖写成声明：默认参数里的 Depends 与依赖树' labels='把依赖写成声明：默认参数里的 Depends…|参数校验：类型强制、约束与 422 的来源|薄路由层：编排、可测试与失效信号|版本化路由' caption='把入口层做成可测试、可复用的薄层' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 依赖缓存：同一请求内为何只解析一次


### yield 依赖里的 close 为什么必须放进 finally

**依赖缓存与可测试性**

| 机制 | 默认行为 | 失效 / 风险信号 |
| --- | --- | --- |
| use_cache=True | 同一请求内同依赖只解析一次 | 被置 False 时连接被重复创建 |
| dependency_overrides | 测试里整体替换依赖实现 | 未替换则测试必须连真库 |
| yield 依赖 | 响应后执行 finally 清理 | 清理不在 finally 时异常路径泄漏连接 |
| def 同步依赖 | async 路由里自动丢线程池 | 在同步路由里 await 会拿到协程对象 |
| 薄路由层 | 只做校验/鉴权/编排/映射 | 出现 SQL 或业务分支说明分层被破坏 |

```python
import inspect

class Depends:
    def __init__(self, fn):
        self.fn = fn

def get_db():
    return 'db'
def get_user(db=Depends(get_db)):
    return 'uid'
def endpoint(user=Depends(get_user), db=Depends(get_db)):
    return user

print('endpoint defaults', [type(d).__name__ for d in endpoint.__defaults__])
print('resolves to', [d.fn.__name__ for d in endpoint.__defaults__])
print('get_user param', list(inspect.signature(get_user).parameters))
```

<OutputBox title='原理验证' output='endpoint defaults [&#39;Depends&#39;, &#39;Depends&#39;]\nresolves to [&#39;get_user&#39;, &#39;get_db&#39;]\nget_user param [&#39;db&#39;]' />


## 参数校验：类型强制、约束与 422 的来源

入口参数分三类：路径参数（`/users/{uid}`）、查询参数（`?page=1&size=20`）、请求体（`JSON`）。

Pydantic v2 的 `BaseModel` 用 `Field` 声明约束：`Field(gt=0)`、`Field(ge=1, le=100)`、`Field(min_length=1, max_length=64)`、`Field(default=...)`，还支持 `EmailStr`、`conint` 等类型。

请求到达时框架按签名把原始字符串或 `JSON` 喂给模型，`model_validate` 做类型强制（`'36'` 转成 `int` 的 `36`），任一约束不满足就收集所有错误抛 `ValidationError`，FastAPI 统一映射成 `422 Unprocessable Entity`，响应体带 `loc`、`msg`、`type` 字段定位到具体参数。

手写校验往往要自己写成分支，例如下面这段代码；参数一多，判断就散落各处。

```python
def check(x):
    if x < 0:
        raise ValueError(x)
```

结构化的差别不只是代码量：错误是结构化、可枚举、可测试的。响应侧用 `response_model` 约束出参与文档，`status_code` 声明成功状态（`POST` 常用 `201`），统一异常处理器把领域异常映射成一致的错误结构。

版本化路由有两种常见做法：路径前缀 `/v1`、`/v2`，或按 `Accept` / 自定义头协商；前者最直观，后者对 URL 更干净但缓存键要带上版本头。

**入口参数三类与校验手段**

| 类别 | 来源 | 声明方式 | 失败状态码 |
| --- | --- | --- | --- |
| 路径参数 | /users/&#123;uid&#125; | 函数参数 uid: int | 422（类型/约束不符） |
| 查询参数 | ?page=1&size=20 | 带默认值的标量参数 | 422 |
| 请求体 | JSON body | Pydantic BaseModel 参数 | 422，带 loc/msg/type |
| 请求头 | Idempotency-Key | Header(...) 参数 | 422 |
| 依赖 | Depends(get_user) | 默认值里的 Depends 对象 | 依赖内部异常按类型映射 |

**Pydantic v2 常用约束与默认值**

| 写法 | 含义 | 越界表现 |
| --- | --- | --- |
| Field(gt=0) | 严格大于 0 | ValidationError → 422 |
| Field(ge=1, le=100) | 闭区间 [1,100] | ValidationError → 422 |
| Field(min_length=1, max_length=64) | 字符串长度约束 | ValidationError → 422 |
| Field(default=...) | 必填字段 | 缺失即 422 |
| model_validate(raw) | v2 的数据转换入口 | 返回模型或抛 ValidationError |
| model_dump() | 导出为 dict | 替代 v1 的 dict() |


## 对照：字符串注解与 Pydantic 模型的校验差异

```python
import inspect
from typing import get_type_hints

def coerce(fn, raw):
    hints = get_type_hints(fn)
    out = {}
    for name, p in inspect.signature(fn).parameters.items():
        t = hints.get(name)
        if name not in raw:
            raise KeyError('missing ' + name)
        v = raw[name]
        if t is int:
            if not isinstance(v, int):
                raise ValueError(name + ' must be int')
            if v <= 0:
                raise ValueError(name + ' must be > 0')
            out[name] = v
        elif t is bool:
            out[name] = bool(v)
        else:
            out[name] = str(v)
    return out

def endpoint(page: int, size: int, q: str):
    return (page, size, q)

print(coerce(endpoint, {'page': 2, 'size': 20, 'q': 'py'}))
for bad in ({'page': 0, 'size': 20, 'q': 'py'}, {'page': 1, 'size': 'x', 'q': 'py'}):
    try:
        coerce(endpoint, bad)
    except ValueError as e:
        print('reject', str(e))
```

<OutputBox title='对照写法：先自己猜，再点开' output='{&#39;page&#39;: 2, &#39;size&#39;: 20, &#39;q&#39;: &#39;py&#39;}\nreject page must be &gt; 0\nreject size must be int' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import inspect\n\nclass Depends:\n    def __init__(self, fn):\n        self.fn = fn\n\ndef get_db():\n    print(&#39;  open db&#39;)\n    return {&#39;conn&#39;: &#39;db-1&#39;}\n\ndef get_user(db=Depends(get_db)):\n    return {&#39;uid&#39;: 7, &#39;db&#39;: db[&#39;conn&#39;]}\n\nCACHE = {}\ndef resolve(callable_):\n    if callable_ in CACHE:\n        return CACHE[callable_]\n    sig = inspect.signature(callable_)\n    kwargs = {}\n    for name, p in sig.parameters.items():\n        if isinstance(p.default, Depends):\n            kwargs[name] = resolve(p.default.fn)\n    value = callable_(**kwargs)\n    CACHE[callable_] = value\n    return value\n\ndef endpoint(user=Depends(get_user), db=Depends(get_db)):\n    return (user[&#39;uid&#39;], db[&#39;conn&#39;])\n\nCACHE.clear()\nprint(&#39;result&#39;, resolve(endpoint))\nprint(&#39;cache keys&#39;, [f.__name__ for f in CACHE])", "note": "把依赖写成声明：默认参数里的 Depends 与依赖树"}, {"label": "对照 / 进阶", "code": "import inspect\nfrom typing import get_type_hints\n\ndef coerce(fn, raw):\n    hints = get_type_hints(fn)\n    out = {}\n    for name, p in inspect.signature(fn).parameters.items():\n        t = hints.get(name)\n        if name not in raw:\n            raise KeyError(&#39;missing &#39; + name)\n        v = raw[name]\n        if t is int:\n            if not isinstance(v, int):\n                raise ValueError(name + &#39; must be int&#39;)\n            if v &lt;= 0:\n                raise ValueError(name + &#39; must be &gt; 0&#39;)\n            out[name] = v\n        elif t is bool:\n            out[name] = bool(v)\n        else:\n            out[name] = str(v)\n    return out\n\ndef endpoint(page: int, size: int, q: str):\n    return (page, size, q)\n\nprint(coerce(endpoint, {&#39;page&#39;: 2, &#39;size&#39;: 20, &#39;q&#39;: &#39;py&#39;}))\nfor bad in ({&#39;page&#39;: 0, &#39;size&#39;: 20, &#39;q&#39;: &#39;py&#39;}, {&#39;page&#39;: 1, &#39;size&#39;: &#39;x&#39;, &#39;q&#39;: &#39;py&#39;}):\n    try:\n        coerce(endpoint, bad)\n    except ValueError as e:\n        print(&#39;reject&#39;, str(e))", "note": "参数校验：类型强制、约束与 422 的来源"}]' title='两种写法对照' note='差异集中在 路径与查询参数；先看输出，再找背后的规则。' />


## 薄路由层：编排、失效信号与统一错误映射

把路由层职责收窄成四件事：校验入参、鉴权、编排领域服务、映射响应。领域逻辑放进独立的、不 `import` 框架的模块，这样单元测试可以直接调函数，不必起 `HTTP` 服务；接口测试只验证薄的编排与状态码。依赖注入让「取当前用户」「拿连接」这些横切关注点从每个处理函数里消失，既能复用也能在测试里整体替换。

失效信号很具体：路由函数超过几十行、出现 SQL 或业务分支、同一个依赖在一次请求里被解析多次、测试必须起服务才能覆盖一个校验分支、错误响应在不同接口里格式不一，都说明分层被破坏。

还要注意同步与异步依赖混跑：在 `async` 路由里声明一个同步阻塞的 `def` 依赖，框架会把它丢进线程池；反过来在同步路由里 `await` 异步依赖是不允许的，会直接得到协程对象而非结果。生成器依赖的清理代码必须放在 `finally`，否则异常路径下连接不会归还。

<Callout type="warn" title='本讲最容易踩的坑' text='同一请求里 get_db 被解析三次，连接池被占满：把 use_cache 关掉或在函数体里手工调用依赖函数，绕过了请求级缓存' />


## 请求校验在 Pydantic v2 里的执行链

依赖注入在运行期是一张有向无环图：节点是可调用对象，边由参数默认值里的 `Depends` 标记给出，解析从端点函数出发做深度优先遍历。

缓存的关键是把「一次请求」映射成一个共享的字典作用域——框架在请求进入时新建 `cache`、把 `(callable, security_scopes)` 作键存解析结果，响应结束后整个字典丢弃，因此 `get_db` 无论出现在树的哪个位置都只解析一次，而不同请求之间不会串数据。

若依赖写成 `yield` 生成器，框架用上下文管理协议：请求前推进到 `yield` 取值注入，响应发送后把生成器再推进一次触发 `finally` 完成提交或回滚与连接归还。

校验侧，Pydantic v2 把每个字段的类型与 `Field` 约束编译成核心 schema，`model_validate` 在 Rust 核心里做类型强制与约束检查，一次性收集全部错误，FastAPI 再把这些错误序列化成带 `loc` 的 `422` 响应。

参数抽取按 `kind` 分派：`PATH`、`QUERY`、`BODY`、`HEADER` 各有固定的取值来源，这正是同一注解能自动区分路径参数与查询参数的原因。

<Term word='路径与查询参数' text='依赖注入的核心不是「自动传参」，而是把「我需要什么」与「怎么拿到」分开。FastAPI 用 `Depends` 表达依赖：路径函数把 `user=Depends(get_user)`、`db=Depends(get_db)` 写成默认参数，`Depends` 对象就挂在函数的 `__defaults__` 里，框架启动…' />

<Term word='请求体与 Pydantic 模型' text='入口参数分三类：路径参数（`/users/{uid}`）、查询参数（`?page=1&amp;size=20`）、请求体（`JSON`）。Pydantic v2 的 `BaseModel` 用 `Field` 声明约束：`Field(gt=0)`、`Field(ge=1, le=100)`…' />


## 可测试的薄路由层：不启服务也能测校验分支

下面把入口层做成一个不依赖 Web 框架的最小运行时：一个注册表把路径模板映射到处理函数，一个依赖解析器按 `Depends` 声明注入参数并做请求级缓存，一个调度器负责参数校验与把领域异常翻译成统一的状态码结构。

领域函数 `place_order` 完全不知道 `HTTP` 与数据库来自哪里，只接收已校验的强类型值，因此单元测试可以直接调它。

测试时用 `dependency_overrides` 把 `get_db` 换成返回内存字典的假实现，整条链路零网络、零真实连接。

这个骨架对应真实项目里的三件事：路由层只做编排、依赖可整体替换、错误响应格式全局一致。

```python
import inspect

class Depends:
    def __init__(self, fn):
        self.fn = fn

def get_repo():
    return {'orders': [], 'next_id': 1}

ROUTES = {}
OVERRIDES = {}

def route(path):
    def deco(fn):
        ROUTES[path] = fn
        return fn
    return deco

def resolve(fn, cache):
    if fn in cache:
        return cache[fn]
    kwargs = {}
    for name, p in inspect.signature(fn).parameters.items():
        if isinstance(p.default, Depends):
            dep = OVERRIDES.get(p.default.fn, p.default.fn)
            kwargs[name] = resolve(dep, cache)
    cache[fn] = fn(**kwargs)
    return cache[fn]

def place_order(uid, amount, repo):
    if amount <= 0:
        raise ValueError('amount must be positive')
    oid = repo['next_id']
    repo['next_id'] += 1
    repo['orders'].append((oid, uid, amount))
    return {'id': oid}

@route('/orders')
def create(amount: int, uid: int, repo=Depends(get_repo)):
    return (201, place_order(uid, amount, repo))

def dispatch(path, params):
    fn = ROUTES[path]
    try:
        params = {k: int(v) for k, v in params.items()}
        return resolve_with_params(fn, params)
    except ValueError as e:
        return (422, {'error': 'validation_error', 'detail': str(e)})

def resolve_with_params(fn, params):
    cache = {}
    deps = {}
    for name, p in inspect.signature(fn).parameters.items():
        if isinstance(p.default, Depends):
            deps[name] = resolve(OVERRIDES.get(p.default.fn, p.default.fn), cache)
    return fn(**params, **deps)

fake = {'orders': [], 'next_id': 100}
OVERRIDES[get_repo] = lambda: fake
print(dispatch('/orders', {'amount': 50, 'uid': 7}))
print(dispatch('/orders', {'amount': 0, 'uid': 7}))
print('orders', fake['orders'])
```

<Callout type="idea" title='落地提示' text='路由层只做校验、鉴权、编排与响应映射，领域逻辑放独立模块并保持框架无关' />

<CheckList id='P084a' title='上线前自检' :items='["能复现并解释「同一请求里 get_db 被解析三次，连接池被占满」", "能复现并解释「yield 依赖里的 session.close() 没放在…」", "能复现并解释「测试一个校验分支也要起 HTTP 服务造完整请求」", "能用一条命令验证 路径与查询参数", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from urllib.parse import urlencode; print(urlencode({'page':2}))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 路径与查询参数 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 同一请求里 get_db 被解析三次，连接池被占满 | 把 use_cache 关掉或在函数体里手工调用依赖函数，绕过了请求级缓存 | 保持依赖默认 use_cache=True，并把数据库获取统一声明成 Depends；需要强制重算时才对单个依赖设 use_cache=False |
| yield 依赖里的 session.close() 没放在 finally，异常后连接泄漏 | 发生异常时生成器被提前关闭，yield 之后的普通语句不会执行 | 把提交/回滚与 close 写进 finally 块：try: yield session finally: session.close() |
| 测试一个校验分支也要起 HTTP 服务造完整请求 | 业务逻辑堆在路由函数里，校验与领域逻辑无法脱离框架调用 | 把领域逻辑移到不 import 框架的独立模块，用 dependency_overrides 替换依赖；接口测试只覆盖薄的编排与状态码 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：同一请求里 get_db 被解析三次，连接池…", "body": "把 use_cache 关掉或在函数体里手工调用依赖函数，绕过了请求级缓存", "tip": "保持依赖默认 use_cache=True，并把数据库获取统一声明成 Depends；需要强制重算时才对单个依赖设 use_cache=False"}, {"title": "第 2 步：yield 依赖里的 session.clo…", "body": "发生异常时生成器被提前关闭，yield 之后的普通语句不会执行", "tip": "把提交/回滚与 close 写进 finally 块：try: yield session finally: session.close()"}, {"title": "第 3 步：测试一个校验分支也要起 HTTP 服务造完整…", "body": "业务逻辑堆在路由函数里，校验与领域逻辑无法脱离框架调用", "tip": "把领域逻辑移到不 import 框架的独立模块，用 dependency_overrides 替换依赖；接口测试只覆盖薄的编排与状态码"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：写一个最小依赖解析器' task='实现 resolve(fn, cache)，递归解析默认值里的 Depends，命中缓存直接返回；构造 get_db → get_user → endpoint 三层依赖，打印被解析过的函数名列表。' solution='import inspect\nclass Depends:\n    def __init__(self, fn): self.fn = fn\ndef get_db(): return &#39;db&#39;\ndef get_user(db=Depends(get_db)): return &#39;u:&#39; + db\ndef endpoint(user=Depends(get_user)): return user\ndef resolve(fn, cache):\n    if fn in cache: return cache[fn]\n    kw = {n: resolve(p.default.fn, cache) for n, p in inspect.signature(fn).parameters.items() if isinstance(p.default, Depends)}\n    cache[fn] = fn(**kw)\n    return cache[fn]\nc = {}\nprint(resolve(endpoint, c))\nprint([f.__name__ for f in c])' explain='深度优先解析，缓存以函数对象为键；get_db 被 get_user 依赖，解析一次后写入缓存，列表里应出现 get_db、get_user、endpoint 三个名字。' />

<Exercise title='进阶：给参数校验加约束并统一错误结构' task='扩展 coerce，让 int 参数支持 gt 约束（从 Field 风格的字典读取），校验失败时返回 {&#39;error&#39;: &#39;validation_error&#39;, &#39;loc&#39;: [...]} 结构，并验证多个错误能一次性收集。' solution='def coerce(raw, spec):\n    errors, out = [], {}\n    for name, (t, lo, default) in spec.items():\n        v = raw.get(name, default)\n        if v is None:\n            errors.append({&#39;loc&#39;: [name], &#39;msg&#39;: &#39;missing&#39;})\n        elif not isinstance(v, t):\n            errors.append({&#39;loc&#39;: [name], &#39;msg&#39;: &#39;type&#39;})\n        elif lo is not None and v &lt;= lo:\n            errors.append({&#39;loc&#39;: [name], &#39;msg&#39;: &#39;gt&#39;})\n        else:\n            out[name] = v\n    return {&#39;error&#39;: &#39;validation_error&#39;, &#39;detail&#39;: errors} if errors else out\nspec = {&#39;page&#39;: (int, 0, 1), &#39;size&#39;: (int, 0, 20)}\nprint(coerce({&#39;page&#39;: 0, &#39;size&#39;: &#39;x&#39;}, spec))' explain='一次性收集全部字段错误而非遇错即停，是 Pydantic 的行为；loc 指向具体参数，映射到 FastAPI 就是 422 响应体。' />

<Quiz no='084-1' q='关于 FastAPI 依赖缓存，下面哪项准确？' :options='["默认 use_cache=True，同一请求内同一依赖只解析一次，结果存在请求级缓存里", "依赖每次被调用都重新执行", "缓存跨请求共享，能复用连接", "只有 async 依赖才会被缓存"]' answer="0" explain='请求进入时新建 cache 字典、响应结束即丢弃，按 (callable, scopes) 存结果；因此同请求共享、跨请求隔离，get_db 不会被重复调用。' />

<Quiz no='084-2' q='Pydantic v2 里把一个 dict 转成模型实例的正确方法是？' :options='["Model.model_validate(raw)", "Model.parse_obj(raw)", "Model(**raw) 且自动校验", "Model.from_dict(raw)"]' answer="0" explain='Pydantic v2 用 model_validate / model_dump 作为数据转换入口，parse_obj / dict 是 v1 的旧名，仅作兼容保留并会告警。' />

<Quiz no='084-3' q='请求体字段不满足 Field(gt=0) 时，FastAPI 返回什么？' :options='["422，响应体带 loc/msg/type 定位到具体字段", "400，只有一行文本说明", "500，因为校验器抛了未捕获异常", "200，字段被静默置为 0"]' answer="0" explain='校验失败抛 RequestValidationError（由 ValidationError 包装），框架统一映射成 422 Unprocessable Entity，结构化列出每个错误的位置与原因。' />

<Predict no='084-4' q='对 def endpoint(user=Depends(get_user), db=Depends(get_db)) 读取 __defaults__，最可能得到什么？' :options='["两个元素，类型名都是 Depends", "两个 None", "一个 dict 与一个 list"]' answer='0' output='endpoint defaults [&#39;Depends&#39;, &#39;Depends&#39;]' explain='Depends 实例作为默认值挂在函数的 __defaults__ 元组里，框架靠 inspect.signature 读到 p.default 再识别它，这就是『依赖是声明而非调用』的证据。' />

<FillBlank no='084-5' tpl='___ inspect' :answers='["import"]' hint='回想本讲关于 路径与查询参数 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 把依赖写成声明：默认参数里的 Depends 与依赖树 的落点。' />

<KnowledgeCard :points='["依赖是声明：Depends 实例藏在函数 __defaults__ 里，框架读签名递归建依赖树", "use_cache=True 默认按请求级缓存共享解析结果；dependency_overrides 让测试整体替换依赖", "yield 依赖在响应后触发 finally，用来提交/回滚与归还连接；清理必须写进 finally", "Pydantic v2 用 model_validate / model_dump；Field(gt/ge/le/min_length) 声明约束", "校验失败统一映射 422，响应体带 loc/msg/type；response_model 同时约束出参与文档", "路由层只做校验/鉴权/编排/响应映射；领域逻辑放不 import 框架的独立模块"]' :pitfalls='["同一请求里 get_db 被解析三次，连接池被占满", "yield 依赖里的 session.close() 没放在 finally，异常后连接泄漏", "测试一个校验分支也要起 HTTP 服务造完整请求", "把业务逻辑堆在路由函数里，接口测试就必须起服务、造 HTTP，速度慢且难定位"]' summary='依赖注入把「取当前用户」「拿数据库连接」从每个处理函数里抽出来，既不重复也方便在测试里整体替换' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 依赖是声明：Depends 实例藏在函数 __defaults__ 里，框架读签名递归建依赖树 | 建立直觉 |
| use_cache=True 默认按请求级缓存共享解析结果；dependency_overrides 让测试整体替换依赖 | 跑通示例 |
| yield 依赖在响应后触发 finally，用来提交/回滚与归还连接；清理必须写进 finally | 深入边界 |
| Pydantic v2 用 model_validate / model_dump；Field(gt/ge/le/min_length) 声明约束 | 工程落地 |
| 校验失败统一映射 422，响应体带 loc/msg/type；response_model 同时约束出参与文档 | 随堂检测 |
| 路由层只做校验/鉴权/编排/响应映射；领域逻辑放不 import 框架的独立模块 | 复盘 |

1. 依赖是声明：Depends 实例藏在函数 __defaults__ 里，框架读签名递归建依赖树

2. use_cache=True 默认按请求级缓存共享解析结果；dependency_overrides 让测试整体替换依赖

3. yield 依赖在响应后触发 finally，用来提交/回滚与归还连接；清理必须写进 finally

[下一讲：REST API 设计、OpenAPI 与幂等](/server/rest-api)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/084-routing.py`

```bash
python3 examples/lessons/084-routing.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/084-routing.py) · [全部示例代码索引](/examples/)
