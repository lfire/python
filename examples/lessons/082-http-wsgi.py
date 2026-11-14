"""
第 082 讲 · HTTP 协议与 WSGI / ASGI
与教程正文一一对应的示例代码

课程页面：/server/http-wsgi
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/082-http-wsgi.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/082-http-wsgi.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# status 200 OK
# content-type text/plain; charset=utf-8
# body GET /health HTTP/1.1
# wsgi keys ['wsgi.errors', 'wsgi.input', 'wsgi.multiprocess', 'wsgi.multithread', 'wsgi.run_once', 'wsgi.url_scheme', 'wsgi.version']

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# message types ['http.response.start', 'http.response.body']
# status 200
# body GET /health
# asgi version 3.0

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# wsgi params ['environ', 'start_response']
# wsgi coroutine False
# asgi params ['scope', 'receive', 'send']
# asgi coroutine True
# wsgi.version (1, 0) url_scheme http

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

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

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
