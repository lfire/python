"""Flask 实操：路由、模板与会话 —— 专题补遗可运行示例。

课程页：/topics/web-frameworks
GitHub：https://github.com/lfire/python/blob/main/examples/topics/web-frameworks.py
依赖安装（可选，第三方段缺库时会自动跳过）：
    python3 -m pip install Flask Flask-SQLAlchemy pytest gunicorn
运行命令：
    python3 examples/topics/web-frameworks.py
说明：本文件按 tools/course/topics/web-frameworks.md 中 python 代码块的出现顺序整理。
纯标准库段（应用工厂配置字典、路由规则匹配、签名 Session 编解码、错误码映射、
模板占位符替换、表单校验）在纯净环境直接跑出结果；依赖 flask / flask_sqlalchemy /
pytest 的可选段用 try/except ImportError 包住，缺库时打印跳过提示，全程不启动服务、
不监听端口、不访问外网。写文件片段一律写入 tempfile.TemporaryDirectory() 自动清理。
"""

import base64
import hashlib
import hmac
import html
import json
import os
import re
import secrets
import tempfile

print('=== Flask 实操：路由、模板与会话 ===')


# ===== 01 · 源文节 先跑一个最小应用：app.py 与 flask run · 代码块 1 app.py（可选 flask） =====
def demo_01_minimal_app():
    try:
        from flask import Flask

        app = Flask(__name__)

        @app.route('/')
        def index():
            return '你好，Flask'

        # 源文 if __name__ == '__main__': app.run(debug=True) 会启动开发服务器，
        # 按可运行性要求不执行，仅保留应用定义。
        print('  代码块 1 最小应用 index 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_01_minimal_app()


# ===== 02 · 源文节 应用工厂与配置类 · 代码块 2 web/__init__.py（可选 flask） =====
def demo_02_app_factory():
    try:
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

        print('  代码块 2 应用工厂 Config / create_app 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_02_app_factory()


# ===== 03 · 源文节 应用工厂与配置类 · 标准库 应用工厂配置字典 =====
def demo_03_config_dict_stdlib():
    # 对应 app.config.from_object 读取全大写属性：用标准库等价演示
    class Config:
        SECRET_KEY = 'dev-only-change-me'
        SQLALCHEMY_DATABASE_URI = 'sqlite:///app.db'
        TESTING = False

    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

    def config_dict(cls):
        return {k: getattr(cls, k) for k in dir(cls) if k.isupper()}

    print('  应用工厂配置字典 Config =', config_dict(Config))
    print('  应用工厂配置字典 TestConfig =', config_dict(TestConfig))


demo_03_config_dict_stdlib()


# ===== 04 · 源文节 路由与变量规则 · 代码块 3 路由示例（可选 flask） =====
def demo_04_routes():
    try:
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
            print('  url_for(show_post, post_id=7) =', url_for('show_post', post_id=7))
            print('  url_for(search, q=python) =', url_for('search', q='python'))

        print('  代码块 3 路由与变量规则 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_04_routes()


# ===== 05 · 源文节 路由与变量规则 · 标准库 路由规则匹配与转换器 =====
def demo_05_route_match_stdlib():
    # 对应「路由转换器对照表」：把变量规则编译成正则并按类型转型
    CONVERTERS = {
        'str': (r'[^/]+', str),
        'int': (r'[0-9]+', int),
        'float': (r'[0-9]+[.][0-9]+', float),
        'path': (r'.+', str),
        'uuid': (r'[0-9a-fA-F-]+', str),
    }

    def compile_rule(rule):
        regex, types, pos = [], [], 0
        for m in re.finditer(r'<([a-z]+:)?([a-z_]+)>', rule):
            regex.append(re.escape(rule[pos:m.start()]))
            conv = (m.group(1) or 'str:').rstrip(':')
            name = m.group(2)
            pat, cast = CONVERTERS[conv]
            regex.append('(' + pat + ')')
            types.append((name, cast))
            pos = m.end()
        regex.append(re.escape(rule[pos:]))
        return re.compile('^' + ''.join(regex) + '$'), types

    cases = [
        ('/post/<int:post_id>', '/post/7'),
        ('/user/<name>', '/user/alice'),
        ('/files/<path:subpath>', '/files/a/b/c'),
        ('/price/<float:v>', '/price/3.14'),
        ('/post/<int:post_id>', '/post/abc'),
    ]
    for rule, url in cases:
        rx, types = compile_rule(rule)
        m = rx.match(url)
        if m:
            params = {name: cast(v) for (name, cast), v in zip(types, m.groups())}
            print('  路由匹配', rule, '<-', url, '->', params)
        else:
            print('  路由不匹配', rule, '<-', url)


demo_05_route_match_stdlib()


# ===== 06 · 源文节 request、response 与常见状态码 · 代码块 4 echo（可选 flask） =====
def demo_06_echo():
    try:
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

        print('  代码块 4 echo 视图 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_06_echo()


# ===== 07 · 源文节 request、response 与常见状态码 · 标准库 错误码映射 =====
def demo_07_status_codes_stdlib():
    # 对应正文「路由里常返回的状态码」表
    STATUS = {
        200: '正常返回', 201: '创建资源成功', 204: '删除成功、无响应体',
        302: '重定向', 400: '参数格式或校验不通过',
        401: '未认证', 403: '已认证但无权限',
        404: '资源不存在', 405: '方法不被该路由允许', 500: '未捕获的服务端异常',
    }
    for code in (200, 201, 400, 404, 500):
        print('  错误码映射', code, '->', STATUS[code])


demo_07_status_codes_stdlib()


# ===== 08 · 源文节 Jinja2 模板与模板继承 · 代码块 5 render_template index（可选 flask） =====
def demo_08_render_template():
    try:
        from flask import Flask, render_template

        app = Flask(__name__)

        @app.route('/')
        def index():
            posts = [{'title': '第一篇', 'created_at': '2026-01-01'}]
            return render_template('index.html', heading='最新文章', posts=posts)

        print('  代码块 5 render_template index 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_08_render_template()


# ===== 09 · 源文节 Jinja2 模板与模板继承 · 标准库 模板占位符替换 + tempfile 写文件 =====
def demo_09_template_stdlib():
    # 对应 base.html / index.html 的双花括号插值、|e 转义与 {% for %} 块
    tpl = (
        '<h1>{{ heading }}</h1>'
        '<ul>{% for post in posts %}<li>{{ post|e }}</li>{% endfor %}</ul>'
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'index.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(tpl)
        with open(path, encoding='utf-8') as f:
            text = f.read()

        def render(tpl_text, ctx):
            def loop_sub(m):
                body = m.group(1)
                return ''.join(body.replace('{{ post|e }}', html.escape(p))
                               for p in ctx['posts'])
            tpl_text = re.sub(r'{% for post in posts %}(.*?){% endfor %}',
                              loop_sub, tpl_text, flags=re.S)
            return tpl_text.replace('{{ heading }}', html.escape(ctx['heading']))

        rendered = render(text, {'heading': '最新文章', 'posts': ['第一篇', '<b>第二篇</b>']})
        print('  模板占位符替换（tempfile 写入并读回）=', rendered)


demo_09_template_stdlib()


# ===== 10 · 源文节 静态资源与蓝图模块化 · 代码块 6 blog.py Blueprint（可选 flask） =====
def demo_10_blueprint():
    try:
        from flask import Blueprint, render_template

        bp = Blueprint('blog', __name__, url_prefix='/blog',
                       template_folder='templates')

        @bp.route('/')
        def index():
            return render_template('blog/index.html')

        @bp.route('/<int:post_id>')
        def detail(post_id):
            return f'blog post {post_id}'

        print('  代码块 6 blog 蓝图 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_10_blueprint()


# ===== 11 · 源文节 静态资源与蓝图模块化 · 代码块 7 create_app 注册蓝图（可选 flask） =====
def demo_11_create_app_blueprints():
    try:
        from flask import Flask

        def create_app(config=None):
            app = Flask(__name__)
            app.config.from_object(config or Config)
            # 函数体内导入，避开与子模块的循环依赖（源文说明）
            from .blog import bp as blog_bp
            from .auth import bp as auth_bp
            app.register_blueprint(blog_bp)
            app.register_blueprint(auth_bp)
            return app

        print('  代码块 7 create_app 注册蓝图 定义完成（依赖 flask，不调用）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_11_create_app_blueprints()


# ===== 12 · 源文节 Cookie、Session 与 SECRET_KEY · 代码块 8 Session（可选 flask） =====
def demo_12_session():
    try:
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

        print('  代码块 8 签名 Session 视图 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_12_session()


# ===== 13 · 源文节 Cookie、Session 与 SECRET_KEY · 标准库 签名 Session 编解码 =====
def demo_13_signed_session_stdlib():
    # 对应「内容做 base64 编码后加 HMAC 签名，带回来时先验签」
    SECRET_KEY = b'dev-only-change-me'

    def encode(data):
        payload = base64.urlsafe_b64encode(
            json.dumps(data, sort_keys=True).encode('utf-8')).decode('ascii')
        sig = hmac.new(SECRET_KEY, payload.encode('ascii'), hashlib.sha256).hexdigest()
        return payload + '.' + sig

    def decode(token):
        payload, sig = token.rsplit('.', 1)
        expected = hmac.new(SECRET_KEY, payload.encode('ascii'), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError('签名不匹配，Cookie 可能被篡改')
        return json.loads(base64.urlsafe_b64decode(payload.encode('ascii')).decode('utf-8'))

    token = encode({'user': 'alice'})
    print('  签名 Session 编码 =', token)
    print('  签名 Session 验签后解码 =', decode(token))
    tampered = token[:-1] + ('0' if token[-1] != '0' else '1')
    try:
        decode(tampered)
    except ValueError as exc:
        print('  签名 Session 篡改检测 =', exc)


demo_13_signed_session_stdlib()


# ===== 14 · 源文节 表单校验与 CSRF 概念 · 代码块 9 表单校验（可选 flask）与标准库 validate =====
def demo_14_form_csrf():
    # 源文 validate 是纯标准库逻辑，先直接跑出结果（补最小调用）
    def validate(form):
        errors = {}
        name = form.get('name', '').strip()
        if not 1 <= len(name) <= 32:
            errors['name'] = '昵称需 1 到 32 个字符'
        age = form.get('age', '')
        if not age.isdigit() or not 0 < int(age) < 150:
            errors['age'] = '年龄需为 1 到 149 的整数'
        return errors

    print('  表单校验 validate(合法) =', validate({'name': 'alice', 'age': '30'}))
    print('  表单校验 validate(非法) =', validate({'name': '', 'age': 'x'}))
    print('  CSRF token(secrets.token_urlsafe) 长度 =', len(secrets.token_urlsafe(16)))

    # 源文 signup 视图依赖 flask，包成可选段
    try:
        from flask import Flask, request, render_template, session, abort

        app = Flask(__name__)
        app.secret_key = 'dev-only-change-me'

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

        print('  代码块 9 signup 视图 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_14_form_csrf()


# ===== 15 · 源文节 错误处理与自定义错误页 · 代码块 10（可选 flask） =====
def demo_15_error_handlers():
    try:
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

        print('  代码块 10 错误处理视图 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_15_error_handlers()


# ===== 16 · 源文节 SQLAlchemy 集成的增删查改 · 代码块 11（可选 flask_sqlalchemy） =====
def demo_16_sqlalchemy():
    try:
        from flask import Flask, request
        from flask_sqlalchemy import SQLAlchemy

        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db = SQLAlchemy(app)

        class Post(db.Model):
            id = db.Column(db.Integer, primary_key=True)
            title = db.Column(db.String(120), nullable=False)

        # 源文的 with app.app_context(): db.create_all() 会写库文件，
        # 按可运行性要求不执行，仅保留模型与路由定义。

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

        print('  代码块 11 SQLAlchemy 增删查改 定义完成（依赖 flask_sqlalchemy）')
    except ImportError:
        print("跳过：需要 pip install Flask Flask-SQLAlchemy")


demo_16_sqlalchemy()


# ===== 17 · 源文节 测试客户端 · 代码块 12（可选 pytest 与 web 包） =====
def demo_17_test_client():
    try:
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

        print('  代码块 12 测试客户端用例 定义完成（依赖 pytest 与 web 包，不执行）')
    except ImportError:
        print("跳过：需要 pip install pytest 及 web 包")


demo_17_test_client()


# ===== 18 · 源文节 练习 1 · 代码块 13 参考解（可选 flask） =====
def demo_18_exercise1():
    try:
        from flask import Flask, Blueprint, render_template_string

        bp = Blueprint('note', __name__, url_prefix='/note')

        @bp.route('/')
        def index():
            notes = [{'title': '第一条'}, {'title': '第二条'}]
            tpl = ('<ul>{% for n in notes %}<li>{{ n.title }}</li>'
                   '{% endfor %}</ul>')
            return render_template_string(tpl, notes=notes)

        def create_app():
            app = Flask(__name__)
            app.register_blueprint(bp)
            return app

        # 源文 if __name__ == '__main__': create_app().run(debug=True) 会启动开发服务器，
        # 按可运行性要求不执行，仅保留工厂定义。
        print('  代码块 13 练习 1 参考解 定义完成（依赖 flask）')
    except ImportError:
        print("跳过：需要 pip install Flask")


demo_18_exercise1()


# ===== 19 · 源文节 练习 2 · 代码块 14 参考解（可选 flask_sqlalchemy） =====
def demo_19_exercise2():
    try:
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

        # 源文末尾的 test_crud() 调用此处不执行，避免依赖真实数据库环境。
        print('  代码块 14 练习 2 参考解 定义完成（依赖 flask_sqlalchemy，不执行 test_crud）')
    except ImportError:
        print("跳过：需要 pip install Flask Flask-SQLAlchemy")


demo_19_exercise2()


print('=== 全部段落执行完毕 ===')
