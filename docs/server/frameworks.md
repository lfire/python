---
title: 第 083 讲 · FastAPI / Flask / Django 选型
description: 按团队与场景选框架而不是按热度
---

<StageHeader stage='L8 · 服务端与数据' level='★★☆☆☆' time='30 分钟' goal='按团队与场景选框架而不是按热度' prereq='第 082 讲 · HTTP 协议与 WSGI / ASGI' />

# 第 083 讲 · FastAPI / Flask / Django 选型

上一讲弄清了请求怎么穿过 `WSGI` 或 `ASGI` 落到处理函数，这层契约得有框架承接。挑框架容易凭热度拍板；本讲给一把尺子——不记 API，只看分界在「替你决定多少」。

设想一周交两样东西：给算法团队带类型化入参、自动出文档的接口，给运营一个内容站点。统一用最顺手的那套，前者校验与序列化得手写装饰器、文档和代码很快对不上，后者又得补插件凑齐用户与迁移。我们摆出三者定位差异，再比路由与依赖注入、校验与序列化，接着看 ORM 与迁移，最后落到团队成本。需要同步异步之分、函数注解与装饰器；读完能说清为何选 FastAPI、Flask 还是 Django。


## 微服务里硬套 Django 整套 ORM 之后

一个五人小组要在一周内交付两个东西：一个是给算法团队用的、带类型化入参与自动生成文档的模型推理接口，另一个是给运营用的、带后台管理与权限的内容站点。有人提议统一用最熟悉的框架，理由是少学一套。结果推理接口为了凑校验与文档，手写了一堆装饰器与 `JSON Schema`，文档和代码很快不同步；

内容站点为了后台、用户与迁移，又补装了一堆插件，启动依赖比业务代码还多。两次别扭都来自同一个误判：把框架当成语法风格的差别，而没看见它们真正的分界是「替你决定多少」。Flask 只给路由内核，FastAPI 把类型注解翻译成校验与 `OpenAPI`，Django 自带从 ORM 到 admin 的全套约定。

本讲用可运行的签名分析把这条分界量出来，让选型落在团队与场景上。

<Callout type="warn" title='先看一个真实会出错的写法' text='FastAPI 路径函数参数写成字符串注解或 Any，文档里没有校验规则：框架在启动时用 get_type_hints 解析注解，字符串或 Any 无法生成具体 JSON Schema' />


## 三者定位：内核、类型化校验到全栈约定

Flask 是微框架，核心只依赖 `Werkzeug`（`WSGI` 工具与路由）与 `Jinja2`（模板），请求上下文靠 `flask.request` 这个代理对象，视图函数通常无参数，参数从 `request.args` / `request.get_json()` 里自己取；

校验、序列化、ORM、迁移、后台都要选插件（`marshmallow` / `pydantic`、`SQLAlchemy`、`Alembic`、`Flask-Admin`），灵活但每个决定都留给你。

FastAPI 建在 `Starlette`（`ASGI`）与 `Pydantic` 之上，把函数签名里的类型注解直接变成请求校验、序列化与 `OpenAPI` 文档：路径函数用 `uid: int`、`q: str = ''` 这样的类型注解声明入参，框架在启动时读 `inspect.signature` 与 `get_type_hints` 生成参数模型，校验失败返回 `422`，文档在 `/openapi.json` 与 `/docs` 自动产出。

Django 是全栈框架，自带 ORM、迁移、认证、session、admin、表单与模板，采用 MTV 约定，`views.py` 接一个 `request` 对象、返回 `HttpResponse`；项目骨架、目录名、`settings.py` 都由框架规定。三者不是快慢之分，而是「框架替你做的决定」从少到多排成一条线。

**三种框架的定位与内置能力**

| 能力 | Flask | FastAPI | Django |
| --- | --- | --- | --- |
| 底层协议 | Werkzeug / WSGI | Starlette / ASGI | WSGI 为主，含 ASGI 支持 |
| 请求入口 | 视图无参，读 flask.request 代理 | 类型化路径函数参数 | 视图接 request 对象 |
| 校验与序列化 | 需 marshmallow / pydantic 插件 | 内置 Pydantic 模型 | forms / DRF serializer |
| 自动 API 文档 | 需 flask-smorest 等扩展 | 内置 OpenAPI + Swagger UI | 需 DRF + drf-spectacular |
| ORM 与迁移 | 需 SQLAlchemy + Alembic | 不内置，常配 SQLAlchemy | 内置 ORM 与 makemigrations |
| admin / 认证 | 需扩展 | 需自行实现 | 内置 admin、auth、session |

<Callout type="tip" title='核心心智模型' text='Flask 是微框架，核心只依赖 `Werkzeug`（WSGI 工具与路由）与 `Jinja2`（模板），请求上下文靠 `flask.request` 这个代理对象，视图函数通常无参数，参数从 `request.args` / `request.get_json()` 里自己取；校验、序列化、OR' />

<ConceptDiagram type='hub4' title='第 083 讲 · 三者定位：从内核、类型化到全栈约定' labels='三者定位：从内核、类型化到全栈约定|版本与生态：哪些结论会随版本变|选型判据：把决定项列成可评分的表' caption='按团队与场景选框架而不是按热度' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 版本与生态：哪些结论会随版本变

具体版本号决定能不能用某些能力，选型时必须对齐。Flask 3.0（2023 年）要求 Python 3.8 及以上，移除了大量对旧版 `Werkzeug` / `itsdangerous` 的兼容 shim，并把部分扩展迁到 `flask` 命名空间之外；

它自 2.0 起支持 `async def` 视图，但底层仍是 `WSGI`，异步视图实际在线程池里跑，不具备 `ASGI` 的长连接能力。

FastAPI 0.100（2023 年）起全面支持 Pydantic v2，后者用 Rust 编写核心，校验性能显著提升，且模型方法从 `parse_obj` / `dict` 迁到 `model_validate` / `model_dump`；

`OpenAPI` 也从 3.0 升到 3.1（对齐 `JSON Schema 2020-12`）。

Django 4.2 是 LTS，社区支持到 2026 年 4 月；Django 5.0 要求 Python 3.10 及以上并引入生成字段，Django 3.1 起有异步视图、4.1 起有异步 ORM 接口，但 ORM 主体仍是同步设计。生态上，内容型后台、需要快速交付 admin 的场景 Django 省事最多；

类型化 API、要客户端 SDK 生成的场景 FastAPI 最省；小工具、脚本包装、已有同步栈的场景 Flask 最轻。

**关键版本与结论影响**

| 版本 | 变化 | 选型时要注意 |
| --- | --- | --- |
| Flask 2.0 / 3.0 | 2.0 起支持 async 视图；3.0 要求 Python>=3.8 | async 视图仍跑在 WSGI 线程池，不支持长连接 |
| FastAPI 0.100+ | 支持 Pydantic v2，OpenAPI 升到 3.1 | model_validate / model_dump 取代 parse_obj / dict |
| Pydantic v2 | 核心用 Rust 重写，校验更快 | 旧代码的 Validator 写法需迁移 |
| Django 4.2 LTS | 社区支持到 2026-04 | 长期维护项目优先 LTS |
| Django 5.0 | 要求 Python>=3.10，新增生成字段 | 升级前核对解释器版本 |

```python
from typing import get_type_hints
import inspect

def parse(fn, raw):
    hints = get_type_hints(fn)
    sig = inspect.signature(fn)
    out = {}
    for name, p in sig.parameters.items():
        t = hints.get(name)
        if name not in raw:
            if p.default is not inspect.Parameter.empty:
                out[name] = p.default
            else:
                raise ValueError('missing field ' + name)
        else:
            v = raw[name]
            if t is int:
                try:
                    out[name] = int(v)
                except (ValueError, TypeError):
                    raise ValueError('int coercion failed for ' + name)
            elif t is bool:
                out[name] = v if isinstance(v, bool) else str(v).lower() in ('1', 'true')
            else:
                out[name] = str(v)
    return out

def handler(name: str, age: int, active: bool = True):
    return (name, age, active)
print(parse(handler, {'name': 'ada', 'age': '36'}))
print(parse(handler, {'name': 'ada', 'age': '36', 'active': 'false'}))
try:
    parse(handler, {'name': 'ada', 'age': 'abc'})
except ValueError as e:
    print('error', str(e))
```

<OutputBox title='对照写法：先自己猜，再点开' output='{&#39;name&#39;: &#39;ada&#39;, &#39;age&#39;: 36, &#39;active&#39;: True}\n{&#39;name&#39;: &#39;ada&#39;, &#39;age&#39;: 36, &#39;active&#39;: False}\nerror int coercion failed for age' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import inspect\nfrom typing import get_type_hints\n\ndef create_user(name: str, age: int, active: bool = True):\n    return {&#39;name&#39;: name, &#39;age&#39;: age, &#39;active&#39;: active}\n\nsig = inspect.signature(create_user)\nhints = get_type_hints(create_user)\nfor pname, p in sig.parameters.items():\n    ann = hints.get(pname)\n    default = &#39;required&#39; if p.default is inspect.Parameter.empty else str(p.default)\n    print(pname, ann.__name__, default)", "note": "三者定位：从内核、类型化到全栈约定"}, {"label": "对照 / 进阶", "code": "from typing import get_type_hints\nimport inspect\n\ndef parse(fn, raw):\n    hints = get_type_hints(fn)\n    sig = inspect.signature(fn)\n    out = {}\n    for name, p in sig.parameters.items():\n        t = hints.get(name)\n        if name not in raw:\n            if p.default is not inspect.Parameter.empty:\n                out[name] = p.default\n            else:\n                raise ValueError(&#39;missing field &#39; + name)\n        else:\n            v = raw[name]\n            if t is int:\n                try:\n                    out[name] = int(v)\n                except (ValueError, TypeError):\n                    raise ValueError(&#39;int coercion failed for &#39; + name)\n            elif t is bool:\n                out[name] = v if isinstance(v, bool) else str(v).lower() in (&#39;1&#39;, &#39;true&#39;)\n            else:\n                out[name] = str(v)\n    return out\n\ndef handler(name: str, age: int, active: bool = True):\n    return (name, age, active)\nprint(parse(handler, {&#39;name&#39;: &#39;ada&#39;, &#39;age&#39;: &#39;36&#39;}))\nprint(parse(handler, {&#39;name&#39;: &#39;ada&#39;, &#39;age&#39;: &#39;36&#39;, &#39;active&#39;: &#39;false&#39;}))\ntry:\n    parse(handler, {&#39;name&#39;: &#39;ada&#39;, &#39;age&#39;: &#39;abc&#39;})\nexcept ValueError as e:\n    print(&#39;error&#39;, str(e))", "note": "版本与生态：哪些结论会随版本变"}]' title='两种写法切换看' />


## 按场景打分：把决定项列成可评分的表

```python
import inspect
from typing import get_type_hints

def create_user(name: str, age: int, active: bool = True):
    return {'name': name, 'age': age, 'active': active}

sig = inspect.signature(create_user)
hints = get_type_hints(create_user)
for pname, p in sig.parameters.items():
    ann = hints.get(pname)
    default = 'required' if p.default is inspect.Parameter.empty else str(p.default)
    print(pname, ann.__name__, default)
```

<OutputBox title='主示例运行结果' output='name str required\nage int required\nactive bool True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import inspect\nfrom typing import get_type_hints\n\ndef create_user(name: str, age: int, active: bool = True):\n    return {&#39;name&#39;: name, &#39;age&#39;: age, &#39;active&#39;: active}\n\nsig = inspect.signature(create_user)\nhints = get_type_hints(create_user)\nfor pname, p in sig.parameters.items():\n    ann = hints.get(pname)\n    default = &#39;required&#39; if p.default is inspect.Parameter.empty else str(p.default)\n    print(pname, ann.__name__, default)' :notes='["导入 inspect，用来读取函数签名对象", "导入 get_type_hints，把注解字符串解析为真实类型对象", "定义一个带类型注解的业务函数，模拟 FastAPI 路径操作", "函数体不参与签名分析，仅示意返回结构", "inspect.signature 返回含参数名、默认值、种类的 Signature", "get_type_hints 得到 {参数名: 类型对象} 的字典", "遍历每个参数，框架在启动时正是这样生成参数模型", "取出该参数的类型对象，如 str、int、bool", "无默认值标记为 required，有默认值则转成字符串", "打印参数名、类型名与默认值，构成校验规则的最小来源"]' title='第 083 讲 · FastAPI / Flask / Django 选型' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**按场景打分（1-5，越高越契合）**

| 场景 | Flask | FastAPI | Django |
| --- | --- | --- | --- |
| 类型化 API + 自动生成客户端 | 2 | 5 | 3 |
| 内容后台 / 需要 admin | 2 | 2 | 5 |
| 大量 WebSocket 长连接 | 1 | 5 | 3 |
| 轻量脚本包装 / 已有同步栈 | 5 | 3 | 2 |
| 业务要与框架解耦 | 5 | 4 | 2 |
| 团队新手快速交付 CRUD | 3 | 4 | 5 |


## 选型判据：框架到底替你决定多少

把「用哪个框架」拆成六个可回答的问题，比争论热度有效：是否需要服务端渲染与 admin（是 → Django）；接口是否需要严格类型化契约与自动文档（是 → FastAPI）；是否要维持大量长连接或 WebSocket（是 → `ASGI` 栈的 FastAPI / Starlette）；

团队是否已有一套同步 ORM 与部署栈（是 → Flask 迁移成本最低）；是否需要把业务做成框架无关、方便替换（微框架更易解耦）；发布节奏是否要求框架替你兜住迁移与权限（Django 内置最全）。同一仓库里不要混两套范式：把 Django 的 ORM 与 admin 塞进微服务，会背上用不到的启动与依赖成本；

把 FastAPI 项目里所有校验再手写一遍，等于放弃了它最大的价值。还要算团队成本：Pydantic v2 的类型系统与异步调试有学习曲线，Django 的约定多但文档与人事供给充足，Flask 灵活却要求团队自己守住结构纪律。选型的产出应是一张带权重的评分表，而不是一句结论。

FastAPI 的自动化来自「把运行时的函数签名当作声明」：路由注册时并不立即处理请求，而是先调用 `inspect.signature` 拿到每个参数的名称、默认值与 `kind`，再用 `typing.get_type_hints` 把注解解析成类型对象；

对 `Pydantic` 的 `BaseModel` 子类生成 `JSON Schema`，对标量参数生成 query / path / body 的位置规则，最后汇总成 `OpenAPI` 的 `paths` 与 `components`。

请求到达时，框架按这张预生成的表抽取并校验数据，失败抛 `RequestValidationError` 并映射为 `422`，成功则把强类型值传入路径函数。

这解释了为什么注解必须写真实类型而非字符串、为什么 `response_model` 能同时约束输出与文档、以及为什么改了签名文档会同步变化——文档不是另写的，而是签名的投影。Flask 没有这层反射，`request` 是一个绑定到当前上下文的 `LocalProxy`，参数靠开发者手动取；

Django 则把约定固化在 `settings.py` 与 MTV 目录结构里，靠框架自带的反射与注册表把模型、admin、`URLconf` 串起来。三者开销的差异，本质是「反射与约定放在哪一层」的差异。

<Term word='三者定位差异' text='Flask 是微框架，核心只依赖 `Werkzeug`（WSGI 工具与路由）与 `Jinja2`（模板），请求上下文靠 `flask.request` 这个代理对象，视图函数通常无参数，参数从 `request.args` / `request.get_json()` 里自己取；校验、序列化、ORM、迁移、后台都要选' />

<Term word='路由与依赖注入' text='具体版本号决定能不能用某些能力，选型时必须对齐。Flask 3.0（2023 年）要求 Python 3.8 及以上，移除了大量对旧版 `Werkzeug` / `itsdangerous` 的兼容 shim，并把部分扩展迁到 `flask` 命名空间之外；它自 2.0 起支持 `async def` 视图，但底层仍是' />

<FlowTimeline :steps='[{"title": "三者定位：从内核、类型化到全栈约定", "desc": "Flask 是微框架，核心只依赖 `Werkzeug`（WSGI 工具与路由）与 `…", "tone": "blue"}, {"title": "版本与生态：哪些结论会随版本变", "desc": "具体版本号决定能不能用某些能力，选型时必须对齐。Flask 3.0（2023 年）要…", "tone": "purple"}, {"title": "选型判据：把决定项列成可评分的表", "desc": "把「用哪个框架」拆成六个可回答的问题，比争论热度有效：是否需要服务端渲染与 admi…", "tone": "orange"}, {"title": "工程落地", "desc": "把选型写成可复算的评分脚本", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 把选型写成可复算的评分脚本

架构评审里争「用哪个框架」常停在印象，下面把它变成一张能跑的评分表：每个框架在六个维度上预置契合度分数，每个候选项目带一组权重，脚本按权重算加权总分并输出排序。样例一给「类型化推理接口」高权重放在类型契约与文档，样例二给「运营内容后台」高权重放在 admin 与快速交付。

这样结论可复算、可复盘：换权重就换结论，而不是换个人就换结论。真实项目把维度替换成团队实际约束（现有栈、招聘、部署平台、SLA），分数由团队共同校准；脚本本身不替你做决定，它保证决定依据被显式写出来。这段代码只用标准库，方便嵌进 `ADR` 文档一起提交。

```python
SCORES = {
    'Flask':   {'api': 2, 'admin': 2, 'realtime': 1, 'light': 5, 'decouple': 5, 'speed': 3},
    'FastAPI': {'api': 5, 'admin': 2, 'realtime': 5, 'light': 3, 'decouple': 4, 'speed': 4},
    'Django':  {'api': 3, 'admin': 5, 'realtime': 3, 'light': 2, 'decouple': 2, 'speed': 5},
}

def rank(weights):
    total = {}
    for name, dims in SCORES.items():
        total[name] = sum(dims[d] * w for d, w in weights.items())
    return sorted(total.items(), key=lambda kv: -kv[1])

typed_api = {'api': 5, 'admin': 1, 'realtime': 2, 'light': 2, 'decouple': 3, 'speed': 2}
cms = {'api': 1, 'admin': 5, 'realtime': 1, 'light': 1, 'decouple': 1, 'speed': 5}
print('typed api', rank(typed_api))
print('cms', rank(cms))
best_api = rank(typed_api)[0][0]
best_cms = rank(cms)[0][0]
print('different winners', best_api != best_cms)
```

<Callout type="idea" title='落地提示' text='小工具用 Flask、类型化 API 用 FastAPI、内容型后台与快速交付用 Django；同一仓里不要混两套范式' />

<CheckList id='P083b' title='上线前自检' :items='["能复现并解释「FastAPI 路径函数参数写成字符串注解或 Any，文档里」", "能复现并解释「从 Pydantic v1 升到 v2 后 obj.dict」", "能复现并解释「在 Flask 里用 async def 视图却期待并发长连」", "能用一条命令验证 三者定位差异", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from urllib.parse import urlencode; print(urlencode({'page':2}))"
```

把输入换成你自己的数据，观察结果是否仍符合 三者定位差异 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| FastAPI 路径函数参数写成字符串注解或 Any，文档里没有校验规则 | 框架在启动时用 get_type_hints 解析注解，字符串或 Any 无法生成具体 JSON Schema | 写真实类型如 uid: int、q: str = ''，复杂入参用 Pydantic BaseModel，并用 response_model 约束输出 |
| 从 Pydantic v1 升到 v2 后 obj.dict() 与 parse_obj 报警告或报错 | Pydantic v2 把数据转换入口改为 model_dump / model_validate，旧方法仅作兼容保留 | 统一改用 model.model_dump() 与 Model.model_validate(raw)，并核对 Field 的约束写法 |
| 在 Flask 里用 async def 视图却期待并发长连接 | Flask 底层是 WSGI，async 视图被丢进线程池执行，不具备 ASGI 的双工消息能力 | 需要 WebSocket 或海量长连接时换 ASGI 栈（FastAPI / Starlette），不要靠 async 关键字伪装 |

<Callout type="warn" title='本讲最容易踩的坑' text='FastAPI 路径函数参数写成字符串注解或 Any，文档里没有校验规则：框架在启动时用 get_type_hints 解析注解，字符串或 Any 无法生成具体 JSON Schema' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：FastAPI 路径函数参数写成字符串注解或", "body": "框架在启动时用 get_type_hints 解析注解，字符串或 Any 无法生成具体 JSON Schema", "tip": "写真实类型如 uid: int、q: str = &#39;&#39;，复杂入参用 Pydantic BaseModel，并用 response_model 约束输出"}, {"title": "第 2 步：从 Pydantic v1 升到 v2 后 ", "body": "Pydantic v2 把数据转换入口改为 model_dump / model_validate，旧方法仅作兼容保留", "tip": "统一改用 model.model_dump() 与 Model.model_validate(raw)，并核对 Field 的约束写法"}, {"title": "第 3 步：在 Flask 里用 async def 视", "body": "Flask 底层是 WSGI，async 视图被丢进线程池执行，不具备 ASGI 的双工消息能力", "tip": "需要 WebSocket 或海量长连接时换 ASGI 栈（FastAPI / Starlette），不要靠 async 关键字伪装"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：从签名生成参数清单' task='写一个函数 describe(fn)，用 inspect.signature 与 get_type_hints 输出每个参数的名字、类型名、是否必填，并对 def search(q: str, page: int = 1, size: int = 20) 打印结果。' solution='import inspect\nfrom typing import get_type_hints\n\ndef describe(fn):\n    hints = get_type_hints(fn)\n    out = []\n    for name, p in inspect.signature(fn).parameters.items():\n        t = hints.get(name)\n        required = p.default is inspect.Parameter.empty\n        out.append((name, getattr(t, &#39;__name__&#39;, &#39;any&#39;), &#39;required&#39; if required else &#39;default=&#39; + str(p.default)))\n    return out\n\ndef search(q: str, page: int = 1, size: int = 20):\n    return (q, page, size)\nprint(describe(search))' explain='这正是 FastAPI 启动时做的事：签名给出参数名与默认值，get_type_hints 给出类型；required 由 default 是否为 inspect.Parameter.empty 判定。' />

<Exercise title='进阶：为不同项目算加权选型' task='在评分脚本基础上增加『已有同步栈』维度并给三个框架补分，构造一个让 Flask 胜出的权重组合，打印三组不同权重下的冠军，解释为何没有唯一最优框架。' solution='SCORES = {\n    &#39;Flask&#39;:   {&#39;api&#39;: 2, &#39;admin&#39;: 2, &#39;sync&#39;: 5},\n    &#39;FastAPI&#39;: {&#39;api&#39;: 5, &#39;admin&#39;: 2, &#39;sync&#39;: 2},\n    &#39;Django&#39;:  {&#39;api&#39;: 3, &#39;admin&#39;: 5, &#39;sync&#39;: 3},\n}\ndef winner(w):\n    return max(SCORES, key=lambda n: sum(SCORES[n][d] * v for d, v in w.items()))\nprint(winner({&#39;api&#39;: 5, &#39;admin&#39;: 1, &#39;sync&#39;: 1}))\nprint(winner({&#39;api&#39;: 1, &#39;admin&#39;: 5, &#39;sync&#39;: 1}))\nprint(winner({&#39;api&#39;: 1, &#39;admin&#39;: 1, &#39;sync&#39;: 5}))' explain='权重变化会让 FastAPI、Django、Flask 各自胜出，说明框架优劣是相对场景的；把权重显式写出来，评审才有可复盘的依据。' />

<Quiz no='083-1' q='FastAPI 能自动生成 OpenAPI 文档，根本机制是？' :options='["启动时用 inspect.signature 与 get_type_hints 读函数签名和类型注解，投影成参数模型与 JSON Schema", "运行期扫描注释里的 YAML 片段", "读取独立的 swagger.yaml 文件", "由前端 SDK 反向生成"]' answer="0" explain='路径函数签名与注解是唯一来源：框架据它生成校验规则与 OpenAPI 的 paths/components，文档是签名的投影，因此改签名文档同步变化。' />

<Quiz no='083-2' q='关于三框架的 ORM 与 admin，下面哪项准确？' :options='["Django 内置 ORM、迁移与 admin，Flask 与 FastAPI 需要另配", "三者都内置完全相同的 ORM", "FastAPI 内置 Django ORM", "Flask 自带 admin 而 Django 不带"]' answer="0" explain='Django 是全栈约定，自带 ORM/migrations/auth/admin；Flask 与 FastAPI 把这些决定留给开发者，常配 SQLAlchemy 与 Alembic。' />

<Quiz no='083-3' q='Flask 2.0+ 的 async def 视图意味着什么？' :options='["它仍在 WSGI 模型下跑，异步视图被丢进线程池，不支持 ASGI 长连接", "底层自动切换成 ASGI，可原生跑 WebSocket", "所有同步库自动变为非阻塞", "不再需要 WSGI 服务器"]' answer="0" explain='Flask 的异步支持是为兼容 async 库提供的桥接，底层仍是一请求一响应的 WSGI；要长连接与双工消息必须换 ASGI 栈。' />

<Predict no='083-4' q='对一个 Flask 风格无参视图、一个带注解的 FastAPI 视图、一个接 request 的 Django 视图分别取签名，最可能看到哪组参数？' :options='["[]、[&#39;name&#39;, &#39;age&#39;]、[&#39;request&#39;]", "三者都是 [&#39;request&#39;]", "[&#39;environ&#39;, &#39;start_response&#39;] 三次"]' answer='0' output='flask_view params [] ann {}; fastapi_view params [&#39;name&#39;, &#39;age&#39;] ann {&#39;name&#39;: &#39;str&#39;, &#39;age&#39;: &#39;int&#39;}; django_view params [&#39;request&#39;] ann {}' explain='Flask 靠 request 上下文代理取参故视图无参，FastAPI 把参数与注解写在签名上，Django 约定接一个 request 对象——签名差异正是『替你决定多少』的直接证据。' />

<FillBlank no='083-5' tpl='___ inspect' :answers='["import"]' hint='回想本讲关于 三者定位差异 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 三者定位：从内核、类型化到全栈约定 的落点。' />

<KnowledgeCard :points='["分界是『替你决定多少』：Flask 只给内核、FastAPI 把注解变成校验与文档、Django 自带全栈约定", "FastAPI 启动时读 inspect.signature + get_type_hints 生成参数模型与 OpenAPI，校验失败返 422", "Pydantic v2 用 Rust 核心，model_validate / model_dump 取代 parse_obj / dict", "Flask 3.0 需 Python&gt;=3.8；async 视图仍跑 WSGI 线程池，长连接要 ASGI 栈", "Django 4.2 是 LTS（支持到 2026-04），5.0 需 Python&gt;=3.10；内置 ORM/迁移/admin/auth", "同仓不要混两套范式；选型产出应是带权重的评分表，而非热度结论"]' :pitfalls='["FastAPI 路径函数参数写成字符串注解或 Any，文档里没有校验规则", "从 Pydantic v1 升到 v2 后 obj.dict() 与 parse_obj 报警告或报错", "在 Flask 里用 async def 视图却期待并发长连接", "微服务里硬套 Django 的整套 ORM 与 admin，会背上用不到的启动与依赖成本"]' summary='框架差异主要在「替你决定多少」：Flask 只给内核、FastAPI 把类型注解变成校验与文档、Django 自带全栈约定' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 分界是『替你决定多少』：Flask 只给内核、FastAPI 把注解变成校验与文档、Django 自带全栈约定 | 建立直觉 |
| FastAPI 启动时读 inspect.signature + get_type_hints 生成参数模型与 OpenAPI，校验失败返 422 | 跑通示例 |
| Pydantic v2 用 Rust 核心，model_validate / model_dump 取代 parse_obj / dict | 深入边界 |
| Flask 3.0 需 Python>=3.8；async 视图仍跑 WSGI 线程池，长连接要 ASGI 栈 | 工程落地 |
| Django 4.2 是 LTS（支持到 2026-04），5.0 需 Python>=3.10；内置 ORM/迁移/admin/auth | 随堂检测 |
| 同仓不要混两套范式；选型产出应是带权重的评分表，而非热度结论 | 复盘 |

1. 分界是『替你决定多少』：Flask 只给内核、FastAPI 把注解变成校验与文档、Django 自带全栈约定

2. FastAPI 启动时读 inspect.signature + get_type_hints 生成参数模型与 OpenAPI，校验失败返 422

3. Pydantic v2 用 Rust 核心，model_validate / model_dump 取代 parse_obj / dict

[下一讲：路由、依赖注入与请求校验](/server/routing)
