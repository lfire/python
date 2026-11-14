---
title: Flask 实操：路由、模板与会话
description: 从能直接 flask run 的最小应用出发，讲应用工厂与配置、路由变量规则、请求响应、Jinja2 模板继承、蓝图、Cookie 与 Session、表单与 CSRF、错误处理、SQLAlchemy 增删查改、测试客户端，以及 gunicorn、反向代理与 HTTPS 的生产配置。
---

# Flask 实操：路由、模板与会话

正文第 083 讲停在框架选型：知道 Flask 是只给路由内核的微框架，却没真正用起来。服务端阶段更多讲协议与架构，真要交一个能登录、能查库、能上线的站点时，路由怎么组织、模板怎么复用、Cookie 与 Session 怎么签、SQLAlchemy 怎么接、部署时哪里最容易配错，全得自己趟一遍。本专题从一个能直接 `flask run` 的最小应用起步，按功能真正长出来的顺序推进：应用工厂与配置、路由变量规则、`request` 与 `response`、Jinja2 模板继承与静态资源、蓝图模块化、Cookie 与 Session、表单校验与 CSRF、错误处理与自定义错误页，再到 SQLAlchemy 增删查改、测试客户端，最后落到 gunicorn、反向代理与 HTTPS 的生产配置。每个环节给一段能放进项目就跑的代码，配一张对照表收口。

## 先跑一个最小应用：app.py 与 flask run

先用虚拟环境装依赖，写一个单文件应用。`app = Flask(__name__)` 让框架按当前模块定位模板与静态目录，`@app.route('/')` 把 URL 规则绑到视图函数，返回值就是要送回浏览器的响应体。

```bash
python -m venv .venv
source .venv/bin/activate
pip install Flask
flask --app app run --debug
```

```python
# app.py —— 最小的可运行应用
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return '你好，Flask'

if __name__ == '__main__':
    app.run(debug=True)
```

`flask --app app run` 会去 `app.py` 里找名为 `app` 的对象；装了 `--debug` 后改代码会自动重载，并在浏览器里给出交互式调试器。浏览器打开 `http://127.0.0.1:5000/` 就能看到返回文本。`app.run` 与 `flask run` 启动的是同一个开发服务器，只用于本机，不要拿它接公网流量。

## 应用工厂与配置类

单文件一写成项目就会遇到问题：测试想换一个内存数据库、要多起几个不同配置的实例、全局变量在导入时就被定死。应用工厂把这些延迟到调用时——`create_app` 每次返回一个全新、配置独立的 `app` 对象。配置用类组织，再按环境覆盖。

```python
# web/__init__.py
from flask import Flask

class Config:
    SECRET_KEY = 'dev-only-change-me'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
    TESTING = False

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(config or Config)
    register_routes(app)
    return app

def register_routes(app):
    @app.route('/health')
    def health():
        return {'status': 'ok'}
```

工厂写法下启动命令要把调用写进目标表达式。

```bash
flask --app 'web:create_app()' run
```

返回字典会被 Flask 自动转成 JSON 响应，`/health` 这类探针路由这样写最省事。`app.config.from_object` 读类里的全大写属性，`app.config.from_envvar` 或 `app.config.from_prefixed_env` 则能从环境变量注入生产值。

**几个必须盯住的配置项**

| 配置项 | 作用 | 生产注意 |
| --- | --- | --- |
| `SECRET_KEY` | 给 Session Cookie 与 CSRF token 做签名 | 从环境变量读，绝不硬编码进仓库 |
| `TESTING` | 关闭错误捕获，让异常直接冒泡给测试 | 只在测试配置里置为 `True` |
| `SQLALCHEMY_DATABASE_URI` | 数据库连接串 | 用环境变量注入，别写进代码 |
| `DEBUG` | 开启重载与调试器 | 生产必须为 `False` |

<Callout type='warn' title='别把调试器带上线' text='生产环境 DEBUG 必须为 False，且 SECRET_KEY 要从环境变量读取固定值：开着调试器等于把可执行代码的入口暴露在公网，密钥每次变化则会让所有已登录用户的 Session 立即失效。' />

## 路由与变量规则

URL 里可变的部分写成变量规则，尖括号里的名字与视图参数同名，还能加转换器约束类型。规则里没写转换器时按字符串处理，遇到斜杠就断开；`path` 转换器才允许吃掉斜杠。

```python
from flask import Flask, url_for
from markupsafe import escape

app = Flask(__name__)

@app.route('/post/<int:post_id>')
def show_post(post_id):
    return f'post {post_id}'

@app.route('/user/<name>')
def greet(name):
    return f'hello {escape(name)}'

@app.route('/files/<path:subpath>')
def files(subpath):
    return f'path {escape(subpath)}'

@app.route('/search', methods=['GET'])
def search():
    return 'search page'

with app.test_request_context():
    print(url_for('show_post', post_id=7))
    print(url_for('search', q='python'))
```

`url_for` 按视图函数名反推 URL，路由以后改了路径也不用满项目改链接；多出来的参数会进查询串。`escape` 来自 `markupsafe`，把用户输入里的尖括号转义掉，避免把内容拼进响应时造成 XSS。`methods` 不写时默认只接受 `GET`，外加自动的 `HEAD` 与 `OPTIONS`；需要提交数据就显式列出 `POST`。

**路由转换器对照**

| 写法 | 匹配范围 | 传给视图的类型 |
| --- | --- | --- |
| `<name>` | 不含斜杠的一段 | `str` |
| `<int:post_id>` | 十进制整数 | `int` |
| `<float:v>` | 浮点数 | `float` |
| `<path:subpath>` | 含斜杠的任意路径 | `str` |
| `<uuid:uid>` | 标准 UUID 串 | `UUID` |

两个视图函数若起了同名端点，启动时会直接抛 `AssertionError`，所以函数名别重复；蓝图里则会带上前缀，下一节会看到区别。

## request、response 与常见状态码

视图函数不接参数，请求数据从一个上下文代理 `request` 取。它只在请求处理期间有效，出了视图再访问就会报错——这正是工厂与测试要显式造请求上下文的原因。响应可以只返回字符串，也可以自己造出来改状态码、响应头和 Cookie。

```python
from flask import Flask, request, jsonify, make_response

app = Flask(__name__)

@app.route('/echo', methods=['POST'])
def echo():
    q = request.args.get('q', '')
    body = request.get_json(silent=True) or {}
    name = request.form.get('name')
    resp = make_response(jsonify(q=q, body=body, name=name), 201)
    resp.headers['X-App'] = 'demo'
    resp.set_cookie('last', q or 'none', max_age=3600, httponly=True)
    return resp
```

`request.args` 是查询参数，`request.form` 是表单字段，`request.get_json()` 解析 JSON 请求体，`request.files` 收上传文件，`request.headers` 读请求头。`jsonify` 负责序列化并设好 `Content-Type`，`make_response` 允许你包一层自定义状态码与响应头，`set_cookie` 在这里给 Cookie 加了 `httponly`，让脚本读不到它。

**请求与响应的常用入口**

| 入口 | 作用 |
| --- | --- |
| `request.args` | 查询字符串，类型是 `MultiDict` |
| `request.form` | 表单字段 |
| `request.get_json()` | 解析 JSON 请求体，`silent=True` 时不抛异常 |
| `request.method` / `request.path` | 当前方法与路径 |
| `jsonify(...)` | 构造 JSON 响应 |
| `make_response(body, 201)` | 自定义状态码与响应头 |
| `abort(404)` | 抛出对应的 HTTP 异常 |

**路由里常返回的状态码**

| 状态码 | 用在什么场景 |
| --- | --- |
| `200` | 正常返回 |
| `201` | 创建资源成功 |
| `204` | 删除成功、无响应体 |
| `302` | 重定向，`redirect` 的默认码 |
| `400` | 参数格式或校验不通过 |
| `401` / `403` | 未认证 / 已认证但无权限 |
| `404` | 资源不存在 |
| `405` | 方法不被该路由允许 |
| `500` | 未捕获的服务端异常 |

## Jinja2 模板与模板继承

把 HTML 拼在字符串里很快就不可维护。Flask 用 `render_template` 渲染 `templates/` 目录下的文件，变量用双花括号插值，逻辑用 `for` / `if` 这类块标签，且默认对变量做 HTML 自动转义。先看目录：

```text
web/
├── __init__.py
├── blog.py
├── templates/
│   ├── base.html
│   ├── index.html
│   └── 404.html
└── static/
    └── style.css
```

父模板定义骨架和可覆盖的块，子模板用 `extends` 继承、只填自己那几块。

```html
<!-- base.html -->
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{% block title %}站点{% endblock %}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head>
<body>
  {% block content %}{% endblock %}
</body>
</html>
```

```html
<!-- index.html -->
{% extends "base.html" %}
{% block title %}文章列表{% endblock %}
{% block content %}
  <h1>{{ heading }}</h1>
  <ul>
  {% for post in posts %}
    <li>{{ post.title|e }} · {{ post.created_at }}</li>
  {% else %}
    <li>暂无内容</li>
  {% endfor %}
  </ul>
{% endblock %}
```

```python
from flask import render_template

@app.route('/')
def index():
    posts = [{'title': '第一篇', 'created_at': '2026-01-01'}]
    return render_template('index.html', heading='最新文章', posts=posts)
```

`block` 是子模板能替换的占位，`for` 与 `if` 管循环和条件，`for` 还能带 `else` 处理空列表，这些标签的完整写法见上方模板文件。`|e` 是显式转义过滤器，虽然自动转义已经开着，拼接了富文本时再写一次更保险。父模板里用 `url_for` 生成静态资源地址，别把路径写死。

**模板语法速查**

| 语法 | 含义 |
| --- | --- |
| 双花括号变量插值 | 输出变量，默认做 HTML 转义 |
| `extends` 标签 | 继承父模板 |
| `block` 标签 | 可被覆盖的占位块 |
| `for` / `if` 标签 | 循环与条件分支 |
| `e` 过滤器 | 对单个变量显式做 HTML 转义 |

模板语法里的花括号与标签都只在代码块里出现，正文不要裸写这类以左花括号开头的片段，否则会被模板引擎或前端框架当成插值提前解析。

## 静态资源与蓝图模块化

`static/` 下的文件由 Flask 自动挂在 `/static/` 路径上，`url_for('static', filename='style.css')` 生成地址；生产时这段通常交给 nginx 直接发，应用只处理动态请求。项目一大，把所有路由塞进一个 `create_app` 就乱了，用 `Blueprint` 按业务切块，各自带路由、模板目录和 URL 前缀。

```python
# web/blog.py
from flask import Blueprint, render_template

bp = Blueprint('blog', __name__, url_prefix='/blog',
               template_folder='templates')

@bp.route('/')
def index():
    return render_template('blog/index.html')

@bp.route('/<int:post_id>')
def detail(post_id):
    return f'blog post {post_id}'
```

```python
# web/__init__.py
from flask import Flask

def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object(config or Config)
    from .blog import bp as blog_bp
    from .auth import bp as auth_bp
    app.register_blueprint(blog_bp)
    app.register_blueprint(auth_bp)
    return app
```

`Blueprint` 的第一个参数是名字，注册后端点变成 `blog.index` 这种带前缀的形式，`url_for` 也要写成 `url_for('blog.index')`。`url_prefix` 让该蓝图下所有路由共用前缀，改一处就全改。注册放在函数体内导入，是为了避开 `web/__init__.py` 与子模块互相 import 的循环依赖；蓝图模板若与全局同名，可以把文件放进子目录再用路径区分。

## Cookie、Session 与 SECRET_KEY

Flask 的 `session` 是签名 Cookie：内容做 base64 编码后加 HMAC 签名，浏览器带回来时先验签。它能防篡改，但不保密，所以别往里放密码或身份证号。`SECRET_KEY` 就是这把签名密钥，泄露它等于别人能伪造任意身份。

```python
from flask import Flask, session, request, redirect, url_for

app = Flask(__name__)
app.secret_key = 'dev-only-change-me'

@app.route('/login', methods=['POST'])
def login():
    session['user'] = request.form['username']
    session.permanent = False
    return redirect(url_for('profile'))

@app.route('/profile')
def profile():
    user = session.get('user')
    return f'hello {user}' if user else 'not logged in'

@app.route('/logout')
def logout():
    session.clear()
    return 'logged out'
```

`session` 用起来像字典，赋值即写入、改动后框架自动在响应里带回新的签名 Cookie；`session.clear()` 清空即退出登录。要真正把数据放服务端，用 `Flask-Session` 扩展把存储换到 Redis 或数据库。Cookie 相关的几个开关直接决定安全性。

**Cookie 与 Session 的关键参数**

| 参数 | 作用 | 建议取值 |
| --- | --- | --- |
| `SECRET_KEY` | 签名密钥 | 环境变量注入、足够随机、定期轮换 |
| `session.permanent` | 是否持久 | 配合 `PERMANENT_SESSION_LIFETIME` 控制寿命 |
| `set_cookie` 的 `httponly` | 禁止脚本读取 | 会话 Cookie 建议置为 `True` |
| `secure` | 仅 HTTPS 传输 | 生产置为 `True` |
| `samesite` | 限制跨站携带 | 常用 `Lax` |

## 表单校验与 CSRF 概念

前端的 `required`、`type` 只改善体验，请求完全可以绕开页面直接发，所以类型和范围必须在服务端重算一遍。CSRF 说的是：攻击者诱导已登录的浏览器代发一条改数据的请求，浏览器会自动带上 Cookie，服务端若只认 Cookie 就会误以为是本人操作。防御办法是给每个表单发一个与会话绑定的一次性 token，提交时比对。

```python
from flask import Flask, request, render_template, session, abort
import secrets

app = Flask(__name__)
app.secret_key = 'dev-only-change-me'

def validate(form):
    errors = {}
    name = form.get('name', '').strip()
    if not 1 <= len(name) <= 32:
        errors['name'] = '昵称需 1 到 32 个字符'
    age = form.get('age', '')
    if not age.isdigit() or not 0 < int(age) < 150:
        errors['age'] = '年龄需为 1 到 149 的整数'
    return errors

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        token = secrets.token_urlsafe(16)
        session['csrf'] = token
        return render_template('signup.html', csrf=token)
    if request.form.get('csrf') != session.get('csrf'):
        abort(400)
    errors = validate(request.form)
    if errors:
        return render_template('signup.html', errors=errors), 400
    return 'ok'
```

`request.form.get` 比直接用下标安全，字段缺失时不会抛 `BadRequestKeyError`；`secrets.token_urlsafe` 生成不可预测的 token，藏进表单隐藏字段再与 `session` 里的值比对。校验失败返回 `400` 并把错误回显给模板。真实项目用 `Flask-WTF` 的 `CSRFProtect` 全局保护更省事，也少踩「某个写操作漏加校验」的坑。

**校验要分四层做**

| 层次 | 做什么 | 漏掉会怎样 |
| --- | --- | --- |
| 前端 | `required`、`type` 提示 | 可被绕过，只影响体验 |
| 服务端类型与范围 | `isdigit`、长度、上下界 | 脏数据直接入库 |
| CSRF token | 表单隐藏字段与会话比对 | 跨站请求被冒用身份 |
| 输出转义 | 模板自动转义或 `e` 过滤 | 存储型 XSS |

## 错误处理与自定义错误页

`abort(404)` 抛出一个 `HTTPException`，框架会去找对应的处理函数。用 `@app.errorhandler` 按状态码或异常类注册，就能把冷冰冰的默认页换成自己的模板。

```python
from flask import Flask, render_template, abort

app = Flask(__name__)

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return '服务端异常，请稍后再试', 500

@app.route('/item/<int:item_id>')
def item(item_id):
    row = None
    if row is None:
        abort(404)
    return 'item'
```

处理函数必须返回带状态码的元组，否则自定义 `404` 页会以 `200` 送出去，搜索引擎和监控都会被误导。`500` 页只在 `DEBUG` 关闭时生效，开着调试器会优先显示调试界面；处理函数里也别再抛异常，否则会退化成默认错误页。

## SQLAlchemy 集成的增删查改

用 `Flask-SQLAlchemy` 把 ORM 接进工厂，`db.Model` 声明表结构，`db.session` 是一个工作单元：改动先攒着，`commit` 才真正写库。建表需要应用上下文，所以放在 `app.app_context()` 里。

```bash
pip install Flask-SQLAlchemy
```

```python
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)

with app.app_context():
    db.create_all()

@app.route('/posts', methods=['POST'])
def add_post():
    p = Post(title=request.form['title'])
    db.session.add(p)
    db.session.commit()
    return {'id': p.id, 'title': p.title}, 201

@app.route('/posts')
def list_posts():
    rows = Post.query.order_by(Post.id).all()
    return {'items': [{'id': r.id, 'title': r.title} for r in rows]}

@app.route('/posts/<int:pid>', methods=['PUT'])
def edit_post(pid):
    p = db.session.get(Post, pid)
    if p is None:
        return {'error': 'not found'}, 404
    p.title = request.form['title']
    db.session.commit()
    return {'id': p.id, 'title': p.title}

@app.route('/posts/<int:pid>', methods=['DELETE'])
def del_post(pid):
    p = db.session.get(Post, pid)
    if p is None:
        return {'error': 'not found'}, 404
    db.session.delete(p)
    db.session.commit()
    return '', 204
```

`db.session.get(Post, pid)` 按主键查，比旧的 `query.get` 更直白；改和删都要先处理「记录不存在」分支，别对 `None` 取属性。`nullable=False` 在数据库层兜住空标题。生产别每次启动都 `create_all`，用 `Flask-Migrate` 配合 `Alembic` 管理表结构变更。

**增删查改与路由的对应**

| 操作 | SQLAlchemy 写法 | 典型路由与状态码 |
| --- | --- | --- |
| 增 | `db.session.add(p)` 加 `commit` | `POST /posts` 返回 `201` |
| 查 | `Post.query.all()` 或 `db.session.get` | `GET /posts` 返回 `200` |
| 改 | 改属性后 `commit` | `PUT /posts/<int:pid>` 返回 `200` |
| 删 | `db.session.delete(p)` 加 `commit` | `DELETE` 返回 `204` |

## 测试客户端

`app.test_client()` 直接走 WSGI，不发真实网络请求，配合 `TESTING=True` 让异常冒泡，断言起来又快又稳。用 `TestConfig` 指向内存库，每个用例都从干净状态开始。

```python
import pytest
from web import create_app, TestConfig, db

@pytest.fixture()
def client():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
    return app.test_client()

def test_index(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'hello' in resp.data

def test_add_post(client):
    resp = client.post('/posts', data={'title': '测试'})
    assert resp.status_code == 201
    assert resp.get_json()['title'] == '测试'

def test_404(client):
    assert client.get('/nope').status_code == 404
```

`resp.get_json()` 直接拿回字典，比比对页面文本可靠；要预置登录态，用 `with client.session_transaction() as sess:` 往里写 `session`。测试断言状态码、JSON 结构与数据库结果，别去断言 HTML 里的排版文字。

## 生产部署：gunicorn、反向代理与 HTTPS

Flask 内置服务器单进程、不做进程管理，只配开发用。生产用 gunicorn 起多个 WSGI worker，前面挡一层 nginx：nginx 终止 TLS、直接发静态文件、把动态请求反代给 gunicorn。

```bash
pip install gunicorn
gunicorn -w 4 -b 127.0.0.1:8000 'web:create_app()'
```

```nginx
server {
    listen 443 ssl;
    server_name example.org;
    ssl_certificate     /etc/letsencrypt/live/example.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.org/privkey.pem;

    location /static/ {
        alias /srv/myapp/web/static/;
    }
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

`-w` 按 CPU 核数给 worker 数，gunicorn 只绑 `127.0.0.1`，由 nginx 对外。反代之后应用看到的请求是明文的 http，靠 `X-Forwarded-Proto` 才能知道原始是 HTTPS；用 `ProxyFix` 中间件修正 `request.scheme`，否则 `url_for` 会生成 http 开头的链接。全站 HTTPS 后把 `SESSION_COOKIE_SECURE` 打开，Session Cookie 才只在加密连接里带。`SECRET_KEY` 从环境变量读固定值，所有 worker 必须一致，否则用户请求落到不同进程会反复掉登录。

**上线最常见的配置错误**

| 现象 | 根因 | 修复动作 |
| --- | --- | --- |
| 上线还在用 `flask run` | 内置服务器单线程、无进程守护 | 换 gunicorn 加 systemd 托管 |
| `url_for` 生成 http 链接 | 反代后应用只看到 http | 传 `X-Forwarded-Proto` 并加 `ProxyFix` |
| 静态文件 404 | 生产没配静态路由或路径写错 | nginx 用 `alias` 指向 `static/` |
| Session 每次都丢 | 密钥随机或多个 worker 不一致 | 固定从环境变量读同一 `SECRET_KEY` |
| HTTPS 下 Cookie 不带 | 没设 `secure` 或 `samesite` 过严 | 设 `SESSION_COOKIE_SECURE` 与 `SESSION_COOKIE_SAMESITE` |
| 报错页能执行代码 | `DEBUG` 忘了关 | 生产确保 `DEBUG=False` |

## 常见坑 / 边界与合规

**`SECRET_KEY` 写进代码仓库。** 密钥进版本库等于把伪造 Session 的能力公开，多 worker 各读各的还会让登录反复失效。修复动作：用 `os.environ['SECRET_KEY']` 从环境变量读，所有实例共用同一值；一旦泄露就轮换，并接受现有 Session 全部失效。

**响应里拼了未转义的用户输入。** 用 `f-string` 直接把 `request.form` 的内容塞进 HTML，存储型 XSS 就跟着来了。修复动作：交给模板自动转义，或在拼接前用 `markupsafe.escape` 处理；富文本需求单独用白名单过滤，别整段放行。

**写操作漏了 CSRF 与服务端校验。** 只靠前端 `required`、改数据的路由又不比对 token，等于把身份交给浏览器自动带上的 Cookie。修复动作：所有 `POST`、`PUT`、`DELETE` 都校验一次性 token，服务端重算类型与范围，前端校验只当辅助。

**忘了 `db.session.commit()` 或在请求里 `create_all()`。** 前者让改动静默丢失，后者每次请求都撞一次建表、并发下还可能报错。修复动作：增删改后显式 `commit`，表结构变更交给 `Flask-Migrate`，建表只在启动或迁移脚本里做一次。

**反代后 scheme 判错、Cookie 没设 `secure`。** 应用生成 http 链接、HTTPS 下会话 Cookie 不下发，登录看着像时好时坏。修复动作：传 `X-Forwarded-Proto`、加 `ProxyFix`、设 `SESSION_COOKIE_SECURE=True`，全站强制 HTTPS。

边界上说一句：涉及用户数据时按最小必要收集，密码用 `werkzeug.security` 的 `generate_password_hash` 做哈希、绝不明文存储，对外接口别回显口令、令牌等敏感字段；日志里也不要记录完整请求体。功能跑通只是第一步，把这些默认关掉的开关逐个打开，才算能对外提供服务。

## 练习

::: details 练习 1 · 用工厂注册蓝图并用模板渲染列表
写一个 `create_app` 工厂，注册一个前缀为 `/note` 的 `Blueprint`，让 `/note/` 路由用 `render_template_string` 渲染一个带循环与变量插值的列表。要求整段是能直接运行的 Python。

```python
# 参考解
from flask import Flask, Blueprint, render_template_string

bp = Blueprint('note', __name__, url_prefix='/note')

@bp.route('/')
def index():
    notes = [{'title': '第一条'}, {'title': '第二条'}]
    tpl = '''
    <ul>{% for n in notes %}<li>{{ n.title }}</li>{% endfor %}</ul>
    '''
    return render_template_string(tpl, notes=notes)

def create_app():
    app = Flask(__name__)
    app.register_blueprint(bp)
    return app

if __name__ == '__main__':
    create_app().run(debug=True)
```
:::

::: details 练习 2 · 用测试客户端验证增删查与 404
给出 `create_app` 的最小实现（内存 SQLite、一个 `Post` 模型、新增与列表与删除路由），再用 `test_client` 断言新增返回 `201`、列表能查到该条、删除不存在的记录返回 `404`。

```python
# 参考解
from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)

def create_app():
    app = Flask(__name__)
    app.config.update(
        SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        TESTING=True,
    )
    db.init_app(app)
    with app.app_context():
        db.create_all()

    @app.route('/posts', methods=['POST'])
    def add():
        p = Post(title=request.form['title'])
        db.session.add(p)
        db.session.commit()
        return {'id': p.id}, 201

    @app.route('/posts')
    def listing():
        return {'titles': [p.title for p in Post.query.all()]}

    @app.route('/posts/<int:pid>', methods=['DELETE'])
    def remove(pid):
        p = db.session.get(Post, pid)
        if p is None:
            return {'error': 'not found'}, 404
        db.session.delete(p)
        db.session.commit()
        return '', 204
    return app

def test_crud():
    client = create_app().test_client()
    assert client.post('/posts', data={'title': 'hi'}).status_code == 201
    assert client.get('/posts').get_json() == {'titles': ['hi']}
    assert client.delete('/posts/999').status_code == 404

test_crud()
print('all passed')
```
:::

回到 [专题补遗](/topics/) · [课程总目录](/guide/curriculum)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能跑通本专题按正文顺序整理的标准库示例；需要第三方库的片段会自动跳过并打印安装提示，不装任何库也能看到核心结果。" />

**本专题示例代码** · 仓内路径 `examples/topics/web-frameworks.py`

```bash
python3 examples/topics/web-frameworks.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/topics/web-frameworks.py) · [全部示例代码索引](/examples/)
