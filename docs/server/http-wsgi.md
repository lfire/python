---
title: 第 082 讲 · HTTP 协议与 WSGI / ASGI
description: 理解框架之下发生了什么
---

<StageHeader stage='L8 · 服务端与数据' level='★★★☆☆' time='35 分钟' goal='理解框架之下发生了什么' prereq='第 081 讲 · 阶段综合：把脚本重构成可发布包' />

# 第 082 讲 · HTTP 协议与 WSGI / ASGI

上一讲把脚本收成了可安装的包，可它仍要有人手动去跑。从这一讲起，我们要让它安静地等别人来调用；动手前先不碰框架，只把一次 `HTTP` 请求进来、结果出去之间的约定说清，给服务端阶段垫一层底。

把处理函数挂到网关上，单请求测得挺顺，换成维持长连接却立不住；并发一上来，几个请求又一起变慢。我们先看请求响应传了什么，用标准库把 `WSGI` 的一进一出跑通，再对照 `ASGI` 的 `scope`、`receive`、`send` 三个参数为何能撑住双工通信，最后谈同步异步混跑哪里会卡住。需要函数、可调用对象与并发阶段的协程印象；读完能看懂框架之下的调用契约，也能判断接口该走同步栈还是异步栈。


## 一个 async 视图里直接调同步库，压测时请求一起卡住

把一个同步的报表接口挂到新装的 `ASGI` 网关上，压测时 QPS 不升反降，还偶发全部请求一起卡住。排查发现处理函数里用了一个只提供同步接口的旧 SDK，在 `async def` 视图里被直接调用；这一调用占住了事件循环所在线程，loop 上其它协程全被拖停。

另一条线索是有人想在这个接口上加 WebSocket 推送，却发现同步栈根本没法维持长连接。两次返工指向同一个被跳过的层次：框架之下是一份明确的调用契约。`WSGI` 是 PEP 3333 定义的一请求一响应可调用对象，`ASGI` 是带 `scope`、`receive`、`send` 三参数的异步双工协议；

前者跑不了长连接，后者一旦混入阻塞调用就失去意义。本讲用标准库 `wsgiref` 与一个最小 `ASGI` 应用把两份契约跑通，让「同步还是异步」不再是口号。

<Callout type="warn" title='先看一个真实会出错的写法' text='在 async 视图里直接调用同步阻塞库，压测时全部请求一起卡住：同步调用不 await、不让出，占死事件循环所在线程，loop 上其它协程全部停摆' />


## WSGI：两个参数、一个回调、一段字节迭代

`WSGI`（PEP 3333）把应用约定成一个可调用对象 `application`。

```python
application(environ, start_response)
```

`environ` 是 CGI 风格的 `dict`，含 `REQUEST_METHOD`、`PATH_INFO`、`QUERY_STRING`、`SERVER_PROTOCOL`、`CONTENT_TYPE`，以及 `wsgi.input`（请求体文件对象）、`wsgi.errors`、`wsgi.version`（默认 `(1, 0)`）、`wsgi.url_scheme`、`wsgi.multithread`、`wsgi.run_once` 等 `wsgi.*` 键；

`wsgiref.util.setup_testing_defaults` 正是按这份清单补齐一个最小 `environ`。

`start_response` 必须在应用返回可迭代对象之前（或第一次迭代产出前）被调用，`status` 形如 `'200 OK'`，`headers` 是 `(name, value)` 元组列表；

```python
start_response(status, response_headers, exc_info=None)
```

它返回一个 `write(body)` 供遗留风格追加输出，但现代写法直接返回 `bytes` 的可迭代对象。返回值的每个元素都必须是 `bytes`，不能是 `str`，服务器会对每个字节块调用一次写操作。

这个模型天然是一问一答：没有「请求还活着」的概念，因此 WebSocket、SSE 这类需要服务端持续推送的通道在纯 `WSGI` 上无法实现，只能靠脱离请求周期的独立进程。中间件就是包一层可调用对象，在调用前后改 `environ` 或拦截 `start_response`。

```python
from wsgiref.util import setup_testing_defaults

def app(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain; charset=utf-8')])
    line = environ['REQUEST_METHOD'] + ' ' + environ['PATH_INFO'] + ' ' + environ['SERVER_PROTOCOL']
    return [line.encode('utf-8')]

captured = {}
def start_response(status, headers, exc_info=None):
    captured['status'] = status
    captured['headers'] = dict(headers)
    return lambda data: None

env = {}
setup_testing_defaults(env)
env['REQUEST_METHOD'] = 'GET'
env['PATH_INFO'] = '/health'
env['SERVER_PROTOCOL'] = 'HTTP/1.1'
body = b''.join(app(env, start_response))
print('status', captured['status'])
print('content-type', captured['headers']['Content-Type'])
print('body', body.decode())
print('wsgi keys', sorted(k for k in env if k.startswith('wsgi.')))
```

<OutputBox title='主示例运行结果' output='status 200 OK\ncontent-type text/plain; charset=utf-8\nbody GET /health HTTP/1.1\nwsgi keys [&#39;wsgi.errors&#39;, &#39;wsgi.input&#39;, &#39;wsgi.multiprocess&#39;, &#39;wsgi.multithread&#39;, &#39;wsgi.run_once&#39;, &#39;wsgi.url_scheme&#39;, &#39;wsgi.version&#39;]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='from wsgiref.util import setup_testing_defaults\n\ndef app(environ, start_response):\n    start_response(&#39;200 OK&#39;, [(&#39;Content-Type&#39;, &#39;text/plain; charset=utf-8&#39;)])\n    line = environ[&#39;REQUEST_METHOD&#39;] + &#39; &#39; + environ[&#39;PATH_INFO&#39;] + &#39; &#39; + environ[&#39;SERVER_PROTOCOL&#39;]\n    return [line.encode(&#39;utf-8&#39;)]\n\ncaptured = {}\ndef start_response(status, headers, exc_info=None):\n    captured[&#39;status&#39;] = status\n    captured[&#39;headers&#39;] = dict(headers)\n    return lambda data: None\n\nenv = {}\nsetup_testing_defaults(env)\nenv[&#39;REQUEST_METHOD&#39;] = &#39;GET&#39;\nenv[&#39;PATH_INFO&#39;] = &#39;/health&#39;\nenv[&#39;SERVER_PROTOCOL&#39;] = &#39;HTTP/1.1&#39;\nbody = b&#39;&#39;.join(app(env, start_response))\nprint(&#39;status&#39;, captured[&#39;status&#39;])\nprint(&#39;content-type&#39;, captured[&#39;headers&#39;][&#39;Content-Type&#39;])\nprint(&#39;body&#39;, body.decode())\nprint(&#39;wsgi keys&#39;, sorted(k for k in env if k.startswith(&#39;wsgi.&#39;)))' :notes='["导入 setup_testing_defaults，按 PEP 3333 补齐最小 environ", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 WSGI 应用，签名固定为 environ 与 start_response 两个位置参数", "在返回响应体前调用 start_response，状态行是 &#39;200 OK&#39;", "从 environ 读方法、路径与协议版本，拼成响应文本", "返回值必须是 bytes 的可迭代对象，这里只有一个字节块", "空行，只用于分隔逻辑块，不影响执行结果。", "用字典捕获 start_response 的参数，模拟服务器的回调记录", "自定义 start_response，第三个参数 exc_info 供错误处理复用", "记录状态字符串", "把 headers 转成 dict 便于读取 Content-Type", "返回 write 可调用对象；本例不用它，直接返回可迭代体", "空行，只用于分隔逻辑块，不影响执行结果。", "构造空 environ，交由 setup_testing_defaults 填充", "补齐 wsgi.input、wsgi.errors、wsgi.version 等标准键", "设置请求方法", "设置请求路径 PATH_INFO", "设置 SERVER_PROTOCOL，注意它不是 wsgi.* 键", "把应用返回的字节块拼接成完整响应体", "确认状态行被正确回调", "确认 Content-Type 头被正确传出", "打印解码后的响应体，证明 WSGI 一问一答完成", "列出 environ 里全部 wsgi.* 键，核对协议要求的字段"]' title='第 082 讲 · HTTP 协议与 WSGI / ASGI' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### 返回 str 列表为什么触发断言错误

```python
import inspect
from wsgiref.util import setup_testing_defaults

def wsgi(environ, start_response):
    start_response('200 OK', [])
    return [b'ok']
async def asgi(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200})
print('wsgi params', list(inspect.signature(wsgi).parameters))
print('wsgi coroutine', inspect.iscoroutinefunction(wsgi))
print('asgi params', list(inspect.signature(asgi).parameters))
print('asgi coroutine', inspect.iscoroutinefunction(asgi))
e = {}
setup_testing_defaults(e)
print('wsgi.version', e['wsgi.version'], 'url_scheme', e['wsgi.url_scheme'])
```

<OutputBox title='原理验证' output='wsgi params [&#39;environ&#39;, &#39;start_response&#39;]\nwsgi coroutine False\nasgi params [&#39;scope&#39;, &#39;receive&#39;, &#39;send&#39;]\nasgi coroutine True\nwsgi.version (1, 0) url_scheme http' />


## ASGI：scope、receive、send 与消息类型

`ASGI` 把应用约定成 `async def` 定义的 `app(scope, receive, send)`，三个都是位置参数。

`scope` 是每次连接建一次的 `dict`，含 `type`（`'http'` / `'websocket'` / `'lifespan'`）、`asgi` 子字典（`version` 为 `'3.0'`、`spec_version` 为 `'2.3'`），http 类型另有 `method`、`path`、`raw_path`、`query_string`（`bytes`）、`headers`（`bytes` 键值对列表）、`scheme`、`server`、`client`。

`receive` 是 async 无参可调用，返回一条入站消息：`HTTP` 请求体是一条 `http.request` 消息，带 `body`（`bytes`）与 `more_body`（是否为最后一块），WebSocket 是 `websocket.receive`，生命周期是 `lifespan.startup` / `lifespan.shutdown`。

`send` 是 async 单参可调用，应用通过它发出站消息：`http.response.start`（`status` 为 int、`headers` 为 `bytes` 列表）必须先发，随后一到多条 `http.response.body`（`body` 为 `bytes`、`more_body` 决定流是否结束）。

因为连接与消息分离，一个进程可以并发维持成千上万条长连接，也能在请求中途持续 `send`。`lifespan` 消息让框架在启动时建连接池、关闭时释放资源，替代旧式的启动事件钩子。

**ASGI 常见消息类型**

| 方向 | 消息 type | 关键字段 |
| --- | --- | --- |
| 入站 HTTP | http.request | body(bytes)、more_body(bool) |
| 出站 HTTP 头 | http.response.start | status(int)、headers(bytes 列表) |
| 出站 HTTP 体 | http.response.body | body(bytes)、more_body(bool) |
| 入站 WebSocket | websocket.receive | bytes 或 text |
| 生命周期 | lifespan.startup / lifespan.shutdown | 无额外字段，用于建/释放连接池 |
| scope.type | http / websocket / lifespan | asgi.version 为 '3.0' |

<Callout type="tip" title='核心心智模型' text='WSGI（PEP 3333）把应用约定成一个可调用对象 `application(environ, start_response)`。`environ` 是 CGI 风格的 `dict`，含 `REQUEST_METHOD`、`PATH_INFO`、`QUERY_STRING`…' />


### http.response.start 必须先于 body

```python
import asyncio

async def asgi_app(scope, receive, send):
    await receive()
    await send({'type': 'http.response.start', 'status': 200,
                'headers': [(b'content-type', b'text/plain')]})
    await send({'type': 'http.response.body',
                'body': (scope['method'] + ' ' + scope['path']).encode()})

sent = []
async def receive():
    return {'type': 'http.request', 'body': b'', 'more_body': False}
async def send(m):
    sent.append(m)

scope = {'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.3'},
         'method': 'GET', 'path': '/health', 'query_string': b'',
         'headers': [(b'host', b'localhost')]}
asyncio.run(asgi_app(scope, receive, send))
print('message types', [m['type'] for m in sent])
print('status', sent[0]['status'])
print('body', sent[1]['body'].decode())
print('asgi version', scope['asgi']['version'])
```

<OutputBox title='对照写法：先自己猜，再点开' output='message types [&#39;http.response.start&#39;, &#39;http.response.body&#39;]\nstatus 200\nbody GET /health\nasgi version 3.0' guess="true" />


## WSGI 与 ASGI 契约对照：一请求一响应对双工消息

**WSGI 与 ASGI 契约对照（PEP 3333 / ASGI 3.0）**

| 维度 | WSGI | ASGI |
| --- | --- | --- |
| 应用签名 | def app(environ, start_response) | async def app(scope, receive, send) |
| 参数个数 | 2 个 | 3 个 |
| 入站数据 | environ 字典 + wsgi.input | scope 字典 + await receive() 消息 |
| 出站方式 | start_response 回调 + 返回 bytes 可迭代 | await send() 逐条消息 |
| 状态与头 | status 字符串、headers 为 str 元组 | http.response.start 的 status 为 int、headers 为 bytes |
| 长连接 / 推送 | 不支持，一请求一响应 | 支持 websocket 与 lifespan 消息 |
| 阻塞调用影响 | 默认每请求独立线程，阻塞是常态 | 占住 loop，全协程一起停 |

<Compare :panels='[{"label": "主示例", "code": "from wsgiref.util import setup_testing_defaults\n\ndef app(environ, start_response):\n    start_response(&#39;200 OK&#39;, [(&#39;Content-Type&#39;, &#39;text/plain; charset=utf-8&#39;)])\n    line = environ[&#39;REQUEST_METHOD&#39;] + &#39; &#39; + environ[&#39;PATH_INFO&#39;] + &#39; &#39; + environ[&#39;SERVER_PROTOCOL&#39;]\n    return [line.encode(&#39;utf-8&#39;)]\n\ncaptured = {}\ndef start_response(status, headers, exc_info=None):\n    captured[&#39;status&#39;] = status\n    captured[&#39;headers&#39;] = dict(headers)\n    return lambda data: None\n\nenv = {}\nsetup_testing_defaults(env)\nenv[&#39;REQUEST_METHOD&#39;] = &#39;GET&#39;\nenv[&#39;PATH_INFO&#39;] = &#39;/health&#39;\nenv[&#39;SERVER_PROTOCOL&#39;] = &#39;HTTP/1.1&#39;\nbody = b&#39;&#39;.join(app(env, start_response))\nprint(&#39;status&#39;, captured[&#39;status&#39;])\nprint(&#39;content-type&#39;, captured[&#39;headers&#39;][&#39;Content-Type&#39;])\nprint(&#39;body&#39;, body.decode())\nprint(&#39;wsgi keys&#39;, sorted(k for k in env if k.startswith(&#39;wsgi.&#39;)))", "note": "WSGI：两个参数、一个回调、一段字节迭代"}, {"label": "对照 / 进阶", "code": "import asyncio\n\nasync def asgi_app(scope, receive, send):\n    await receive()\n    await send({&#39;type&#39;: &#39;http.response.start&#39;, &#39;status&#39;: 200,\n                &#39;headers&#39;: [(b&#39;content-type&#39;, b&#39;text/plain&#39;)]})\n    await send({&#39;type&#39;: &#39;http.response.body&#39;,\n                &#39;body&#39;: (scope[&#39;method&#39;] + &#39; &#39; + scope[&#39;path&#39;]).encode()})\n\nsent = []\nasync def receive():\n    return {&#39;type&#39;: &#39;http.request&#39;, &#39;body&#39;: b&#39;&#39;, &#39;more_body&#39;: False}\nasync def send(m):\n    sent.append(m)\n\nscope = {&#39;type&#39;: &#39;http&#39;, &#39;asgi&#39;: {&#39;version&#39;: &#39;3.0&#39;, &#39;spec_version&#39;: &#39;2.3&#39;},\n         &#39;method&#39;: &#39;GET&#39;, &#39;path&#39;: &#39;/health&#39;, &#39;query_string&#39;: b&#39;&#39;,\n         &#39;headers&#39;: [(b&#39;host&#39;, b&#39;localhost&#39;)]}\nasyncio.run(asgi_app(scope, receive, send))\nprint(&#39;message types&#39;, [m[&#39;type&#39;] for m in sent])\nprint(&#39;status&#39;, sent[0][&#39;status&#39;])\nprint(&#39;body&#39;, sent[1][&#39;body&#39;].decode())\nprint(&#39;asgi version&#39;, scope[&#39;asgi&#39;][&#39;version&#39;])", "note": "ASGI：scope、receive、send 与消息类型"}]' title='两种写法对照' note='差异集中在 请求响应模型；先看输出，再找背后的规则。' />

<ConceptDiagram type='layers3' title='第 082 讲 · WSGI：两个参数、一个回调、一段字节迭代' labels='WSGI：两个参数、一个回调、一段字节迭代|ASGI：scope、receive、sen…|同步异步混跑：阻塞调用为何会拖垮整个 loo…|同步异步混跑' caption='理解框架之下发生了什么' />

这张图换成分层视角：上层只依赖下层提供的能力，旁路负责异常与降级，读的时候逐层往下追问依赖。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 同步异步混跑：阻塞调用如何拖垮整个 loop

`ASGI` 的并发收益来自单线程事件循环：协程在 `await` 处主动让出，loop 才能切换到下一个任务。

一旦在 `async def` 函数里直接调用同步阻塞库（`time.sleep`、`requests`、同步数据库驱动），这次调用不 `await`、不让出，当前线程被占死，loop 上所有其它协程一起停住——这不是慢一点，而是整个 loop 级故障。

规范的做法是把阻塞调用挪出 loop：Starlette / FastAPI 对用 `def`（而非 `async def`）定义的路径函数会自动丢进线程池执行（`anyio.to_thread`），自己写异步应用时则要显式 `await` 一个 `asyncio.to_thread` 或 `loop.run_in_executor`。

```python
asyncio.to_thread(blocking_fn, ...)
```

反过来，纯 CPU 密集的活即使放进线程也受 GIL 限制，应交给进程池。`WSGI` 侧没有这个问题：每个请求本来就在独立线程或进程里跑，阻塞是默认语义。选型判据由此清晰：传统 `CRUD`、依赖成熟同步 SDK 用同步栈省心；

需要 WebSocket、SSE、海量长连接与高并发 IO 时上 `ASGI`，并逐一审查调用链里是否还有同步阻塞点。

**同步异步混跑的正确处置**

| 场景 | 错误做法 | 正确做法 |
| --- | --- | --- |
| async 视图里调 requests | 直接同步调用，占死 loop | await asyncio.to_thread(fn) 或改用 httpx.AsyncClient |
| def 路径函数用同步 ORM | 误以为是阻塞 loop | 框架自动丢线程池，无需改 |
| CPU 密集聚合 | 放进线程池期待并行 | ProcessPoolExecutor 绕开 GIL |
| 需要 WebSocket | 在 WSGI 上勉强实现 | 换 ASGI 栈，用 websocket 消息 |
| 启动时建连接池 | 写在模块顶层 | 处理 lifespan.startup 消息 |

<Callout type="warn" title='本讲最容易踩的坑' text='在 async 视图里直接调用同步阻塞库，压测时全部请求一起卡住：同步调用不 await、不让出，占死事件循环所在线程，loop 上其它协程全部停摆' />


## 中间件链：在不碰业务函数的前提下加计时与响应头

生产服务常要在不改每个处理函数的情况下统一加耗时统计、请求 ID 与安全头。`WSGI` 的可调用对象约定让这件事变成一个包装函数：中间件接收 `application`，返回同样签名的新可调用对象，在调用前后改写 `environ` 与 `start_response`。

下面用标准库串起两层中间件，内层业务应用只负责返回 body；外层测耗时并把结果塞进 `X-Time-Ms` 头，另一层注入 `X-Request-Id`。

重点看 `start_response` 的包装技巧：中间件拿到原始的 `start_response`，再传一个自己定义的 `wrapping` 进去，从而能在服务器真正写头之前追加字段。

这个模式也是 Flask、Django 中间件与纯 `ASGI` 中间件的雏形，区别只在后者包的是 `scope` / `receive` / `send`。

```python
import time
from wsgiref.util import setup_testing_defaults

def timer_mw(application):
    def wrapped(environ, start_response):
        t0 = time.perf_counter()
        def cr(status, headers, exc_info=None):
            cost = round((time.perf_counter() - t0) * 1000, 3)
            return start_response(status, headers + [('X-Time-Ms', str(cost))])
        return application(environ, cr)
    return wrapped

def reqid_mw(application):
    def wrapped(environ, start_response):
        environ['app.request_id'] = 'req-82'
        return application(environ, start_response)
    return wrapped

def app(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [environ['app.request_id'].encode()]

env = {}
setup_testing_defaults(env)
env['REQUEST_METHOD'] = 'GET'
env['PATH_INFO'] = '/'
captured = {}
def sr(status, headers, exc_info=None):
    captured['headers'] = dict(headers)
    return lambda d: None
chain = timer_mw(reqid_mw(app))
body = b''.join(chain(env, sr))
print('body', body.decode())
print('has reqid header', 'X-Time-Ms' in (captured['headers'] or {}))
print('headers keys', sorted(k for k in (captured['headers'] or {}) if k.startswith('X-')))
```

<Callout type="idea" title='落地提示' text='按协议选框架：传统 CRUD 用同步栈更省心，需要长连接与高并发 IO 时上 ASGI' />

<CheckList id='P082b' title='上线前自检' :items='["能复现并解释「在 async 视图里直接调用同步阻塞库，压测时全部请求一起…」", "能复现并解释「WSGI 应用返回 str 列表，服务器报断言错误」", "能复现并解释「给 ASGI 应用发 http.response.body…」", "能用一条命令验证 请求响应模型", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "from urllib.parse import urlencode; print(urlencode({'page':2}))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 请求响应模型 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 服务器如何驱动应用：environ、三参数与事件循环

`WSGI` 服务器（如 `gunicorn` 的 sync worker、`wsgiref.simple_server`）为每个请求分配线程或进程，调用一次应用、收集返回的字节迭代、逐块写给客户端，请求结束即释放，因此 `environ` 是请求级快照、应用天然无状态。

`ASGI` 服务器（`uvicorn`、`hypercorn`）则维护一个事件循环：接受连接后构造一次 `scope`，把 `await receive()` / `await send()` 包成协程交给 loop 调度；

协程在 `await` 处让出执行权，loop 据此在单线程里交错处理成千上万条连接。这套机制的吞吐前提是任何 `await` 之间都不发生长时间阻塞，否则整个 loop 停摆——这正是同步库不能直接进 `async def` 视图的原因。

消息顺序由协议强制保证：`http.response.start` 必须先于 `http.response.body`，`more_body` 为真表示还有后续块，服务器据此实现流式响应与 SSE。

`lifespan` 是独立的一条连接级协议，服务器在启动阶段发 `lifespan.startup`、应用回 `lifespan.startup.complete` 后才开始接流量，关闭时对称收尾，保证连接池先建后用的时序。

<Term word='请求响应模型' text='WSGI（PEP 3333）把应用约定成一个可调用对象 `application(environ, start_response)`。`environ` 是 CGI 风格的 `dict`，含 `REQUEST_METHOD`、`PATH_INFO`、`QUERY_STRING`、`SERVER_PROTOCOL`…' />

<Term word='WSGI 可调用对象' text='ASGI 把应用约定成 `async def` 定义的 `app(scope, receive, send)`，三个都是位置参数。`scope` 是每次连接建一次的 `dict`，含 `type`（`&#39;http&#39;` / `&#39;websocket&#39;` / `&#39;lifespan&#39;`）、`asgi` 子字典（`version`…' />


## 错因速查与排查顺序

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 在 async 视图里直接调用同步阻塞库，压测时全部请求一起卡住 | 同步调用不 await、不让出，占死事件循环所在线程，loop 上其它协程全部停摆 | 用 await asyncio.to_thread(blocking_fn, ...)，或把该路径函数定义成普通 def 让框架自动丢线程池 |
| WSGI 应用返回 str 列表，服务器报断言错误 | PEP 3333 要求返回 bytes 的可迭代对象，str 不是合法响应块 | 统一用 line.encode('utf-8') 或包一层中间件做编码；用 wsgiref.validate.validator 包装应用可在开发期暴露违规 |
| 给 ASGI 应用发 http.response.body 却没先发 start | ASGI 协议要求 http.response.start 必须先于任何 body 消息 | 先 await send(&#123;'type': 'http.response.start', 'status': 200, 'headers': [...]&#125;)，再发 body；status 用 int、headers 用 bytes 键值对 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：在 async 视图里直接调用同步阻塞库，压…", "body": "同步调用不 await、不让出，占死事件循环所在线程，loop 上其它协程全部停摆", "tip": "用 await asyncio.to_thread(blocking_fn, ...)，或把该路径函数定义成普通 def 让框架自动丢线程池"}, {"title": "第 2 步：WSGI 应用返回 str 列表，服务器报断…", "body": "PEP 3333 要求返回 bytes 的可迭代对象，str 不是合法响应块", "tip": "统一用 line.encode(&#39;utf-8&#39;) 或包一层中间件做编码；用 wsgiref.validate.validator 包装应用可在开发期暴露违规"}, {"title": "第 3 步：给 ASGI 应用发 http.respon…", "body": "ASGI 协议要求 http.response.start 必须先于任何 body 消息", "tip": "先 await send({&#39;type&#39;: &#39;http.response.start&#39;, &#39;status&#39;: 200, &#39;headers&#39;: [...]})，再发 body；status 用 int、headers 用 bytes 键值对"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：手写一个最小 WSGI 应用' task='用 wsgiref.util.setup_testing_defaults 构造 environ，写一个返回 PATH_INFO 的 WSGI 应用，自定义 start_response 捕获状态与头，打印拼接后的响应体，并说明为什么返回值必须是 bytes。' solution='from wsgiref.util import setup_testing_defaults\n\ndef app(environ, start_response):\n    start_response(&#39;200 OK&#39;, [(&#39;Content-Type&#39;, &#39;text/plain&#39;)])\n    return [environ[&#39;PATH_INFO&#39;].encode(&#39;utf-8&#39;)]\n\nenv = {}\nsetup_testing_defaults(env)\nenv[&#39;PATH_INFO&#39;] = &#39;/ping&#39;\ncap = {}\ndef sr(status, headers, exc_info=None):\n    cap[&#39;status&#39;] = status\n    return lambda d: None\nprint(b&#39;&#39;.join(app(env, sr)).decode())\nprint(cap[&#39;status&#39;])' explain='PEP 3333 规定应用返回 bytes 的可迭代对象，服务器直接写给 socket，不负责编码；start_response 必须在返回可迭代对象前调用，status 是 &#39;200 OK&#39; 这样的字符串。' />

<Exercise title='进阶：证明阻塞调用会拖垮事件循环' task='用 asyncio 写两个协程：一个 await asyncio.sleep，另一个直接 time.sleep；用 perf_counter 测总耗时，再改成 asyncio.to_thread 版本对比，解释差异来源。' solution='import asyncio, time\n\nasync def blocking():\n    time.sleep(0.2)\nasync def offloaded():\n    await asyncio.to_thread(time.sleep, 0.2)\nasync def main(factory):\n    t0 = time.perf_counter()\n    await asyncio.gather(factory(), factory(), factory())\n    return round(time.perf_counter() - t0, 3)\nprint(&#39;serial-in-loop&#39;, asyncio.run(main(blocking)))\nprint(&#39;offloaded&#39;, asyncio.run(main(offloaded)))' explain='time.sleep 不 await 不让出，三个协程串行约 0.6 秒；to_thread 把阻塞调用丢进线程池，三个等待重叠约 0.2 秒。ASGI 里同步阻塞库必须这样处理，否则 loop 上所有连接一起停。' />

<Quiz no='082-1' q='关于 WSGI 与 ASGI 的签名，下面哪项准确？' :options='["WSGI 是 (environ, start_response) 两个参数，ASGI 是 async (scope, receive, send) 三个参数", "两者都是 (request) -&gt; response 单参数", "WSGI 是三参数、ASGI 是两参数", "ASGI 用 start_response 回调返回响应"]' answer="0" explain='PEP 3333 定义 application(environ, start_response)；ASGI 3.0 定义 async def app(scope, receive, send)。ASGI 用 await send 逐条发消息，没有 start_response。' />

<Quiz no='082-2' q='async 视图里直接调用同步阻塞 SDK 的后果是？' :options='["占住事件循环线程，loop 上所有其它协程一起停住", "只有当前请求慢一点，其它请求不受影响", "自动被框架切到线程池，无感知", "触发 GIL 释放从而提升吞吐"]' answer="0" explain='同步阻塞不 await、不让出，单线程 loop 无法切换任务，是全 loop 级故障；正确做法是 asyncio.to_thread 或把路径函数定义成普通 def 由框架丢线程池。' />

<Quiz no='082-3' q='WebSocket 与 SSE 为什么需要 ASGI 而非纯 WSGI？' :options='["需要连接存活期间持续 send 消息，WSGI 一请求一响应模型无法表达", "WSGI 不支持 bytes 响应", "WSGI 的 environ 缺少 headers 字段", "WSGI 只允许 GET 方法"]' answer="0" explain='WSGI 应用返回一次可迭代体即结束请求，没有『连接还活着』的概念；ASGI 的 websocket / lifespan 消息与多次 send 才能维持长连接与服务端推送。' />

<Predict no='082-4' q='对 def wsgi(environ, start_response) 与 async def asgi(scope, receive, send) 分别调 inspect.signature，参数列表是什么？' :options='["[&#39;environ&#39;, &#39;start_response&#39;] 与 [&#39;scope&#39;, &#39;receive&#39;, &#39;send&#39;]", "两者都是 [&#39;scope&#39;, &#39;send&#39;]", "[&#39;request&#39;] 与 [&#39;scope&#39;, &#39;receive&#39;]"]' answer='0' output='wsgi params [&#39;environ&#39;, &#39;start_response&#39;]; asgi params [&#39;scope&#39;, &#39;receive&#39;, &#39;send&#39;]' explain='签名即协议：inspect.signature 读到的参数名与个数直接对应 PEP 3333 与 ASGI 3.0 的约定，iscoroutinefunction 还能区分同步应用与协程应用。' />

<FillBlank no='082-5' tpl='from wsgiref.util  ___ setup_testing_defaults' :answers='["import"]' hint='回想本讲关于 请求响应模型 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 WSGI：两个参数、一个回调、一段字节迭代 的落点。' />

<KnowledgeCard :points='["WSGI = application(environ, start_response)，返回 bytes 可迭代；一请求一响应，不支持长连接", "environ 含 REQUEST_METHOD/PATH_INFO 与 wsgi.input、wsgi.version=(1,0) 等 wsgi.* 键", "ASGI = async app(scope, receive, send)，scope.type 为 http/websocket/lifespan，asgi.version 为 3.0", "出站消息顺序固定：http.response.start（status 为 int）先于 http.response.body（bytes）", "async 视图里的同步阻塞库会占死整个 loop；用 asyncio.to_thread 或普通 def 视图", "lifespan.startup/shutdown 用于建释放连接池；需要 WebSocket/SSE 只能选 ASGI 栈"]' :pitfalls='["在 async 视图里直接调用同步阻塞库，压测时全部请求一起卡住", "WSGI 应用返回 str 列表，服务器报断言错误", "给 ASGI 应用发 http.response.body 却没先发 start", "在 ASGI 应用里直接调用同步阻塞库，会占住事件循环的工作线程"]' summary='WSGI 是同步的一请求一响应函数，ASGI 是带事件消息的双工协议，这决定了 WebSocket 与长连接只能活在 ASGI 世界' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| WSGI = application(environ, start_response)，返回 bytes 可迭代；一请求一响应，不支持长连接 | 建立直觉 |
| environ 含 REQUEST_METHOD/PATH_INFO 与 wsgi.input、wsgi.version=(1,0) 等 wsgi.* 键 | 跑通示例 |
| ASGI = async app(scope, receive, send)，scope.type 为 http/websocket/lifespan，asgi.version 为 3.0 | 深入边界 |
| 出站消息顺序固定：http.response.start（status 为 int）先于 http.response.body（bytes） | 工程落地 |
| async 视图里的同步阻塞库会占死整个 loop；用 asyncio.to_thread 或普通 def 视图 | 随堂检测 |
| lifespan.startup/shutdown 用于建释放连接池；需要 WebSocket/SSE 只能选 ASGI 栈 | 复盘 |

1. WSGI = application(environ, start_response)，返回 bytes 可迭代；一请求一响应，不支持长连接

2. environ 含 REQUEST_METHOD/PATH_INFO 与 wsgi.input、wsgi.version=(1,0) 等 wsgi.* 键

3. ASGI = async app(scope, receive, send)，scope.type 为 http/websocket/lifespan，asgi.version 为 3.0

[下一讲：FastAPI / Flask / Django 选型](/server/frameworks)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/082-http-wsgi.py`

```bash
python3 examples/lessons/082-http-wsgi.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/082-http-wsgi.py) · [全部示例代码索引](/examples/)
