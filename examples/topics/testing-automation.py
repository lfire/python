"""testing-automation 专题示例：接口与 Web UI 自动化测试

对应课程页：/topics/testing-automation
GitHub 源文件：https://github.com/lfire/python/blob/main/examples/topics/testing-automation.py

依赖安装（可选，第三方段缺库时会自动跳过）：
    python3 -m pip install requests pytest PyYAML selenium

运行命令：
    python3 examples/topics/testing-automation.py

说明：本文件按源专题 tools/course/topics/testing-automation.md 中 python 代码块的出现顺序整理。
标准库段（数据驱动断言、csv/json/xml 解析、unittest.mock 重试、本地 http.server）
在纯净环境直接跑出结果；用到 requests / pytest / PyYAML / selenium 的段用 try/except
包成可选段，缺库时打印跳过提示。本地服务只绑定 127.0.0.1 随机端口并在 finally 里
shutdown，selenium 段只保留定义、不启动浏览器也不访问外网；全程不写仓库文件、
不使用交互式输入或无限循环。
"""


# ===== 01 · 源文节 用 requests.Session 收敛公共行为 · 演示 本地 http.server 打桩、expect 合并断言、会话公共头与超时 =====
def demo_01_session():
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/api/user'):
                body = json.dumps({'id': 7, 'name': 'ann', 'role': 'member'}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass

    def expect(resp, status, **fields):
        assert resp.status_code == status, (resp.status_code, status)
        assert 'json' in resp.headers.get('Content-Type', ''), resp.headers
        data = resp.json()
        for key, value in fields.items():
            assert data[key] == value, (key, data.get(key), value)
        return data

    # 本地服务只绑定 127.0.0.1，端口 0 由系统随机分配，绝不连外网
    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    BASE = 'http://127.0.0.1:{}'.format(server.server_port)
    try:
        import requests
        with requests.Session() as session:
            session.headers.update({'Accept': 'application/json'})
            expect(session.get(BASE + '/api/user', timeout=3), 200, id=7, name='ann')
            missing = session.get(BASE + '/missing', timeout=3)
            assert missing.status_code == 404
        print('接口断言通过（本地服务端口 {}）'.format(server.server_port))
    except ImportError:
        print('跳过：需要 pip install requests（本地服务与 expect 断言封装已就绪）')
    finally:
        server.shutdown()
        server.server_close()


demo_01_session()


# ===== 02 · 源文节 pytest 的 fixture 与参数化收拢用例 · 演示 fixture 独立配置、parametrize 展开、fake_get 替身 =====
def demo_02_pytest():
    CASES = [
        ('/api/user/7', 200, {'id': 7, 'name': 'ann'}),
        ('/api/user/0', 404, {'error': 'not found'}),
        ('/api/user/-1', 400, {'error': 'bad id'}),
    ]

    def fake_get(path, cfg):
        table = {
            '/api/user/7': (200, {'id': 7, 'name': 'ann'}),
            '/api/user/0': (404, {'error': 'not found'}),
            '/api/user/-1': (400, {'error': 'bad id'}),
        }
        return table[path]

    # 最小调用：不依赖 pytest 运行器，用标准库循环跑同一套数据驱动断言
    cfg = {'base': 'http://127.0.0.1:8000', 'timeout': 3, 'token': None}
    for path, status, payload in CASES:
        got_status, got_body = fake_get(path, cfg)
        assert got_status == status
        assert got_body == payload
        print('用例', path, '期望', status, '实际', got_status, got_body)

    try:
        import pytest

        @pytest.fixture
        def api_client():
            return {'base': 'http://127.0.0.1:8000', 'timeout': 3, 'token': None}

        @pytest.mark.parametrize('path,status,payload', CASES,
                                 ids=['found', 'missing', 'bad-id'])
        def test_get_user(api_client, path, status, payload):
            got_status, got_body = fake_get(path, api_client)
            assert got_status == status
            assert got_body == payload

        print('pytest 可用：fixture 与参数化用例已定义，由 python -m pytest 收集执行')
    except ImportError:
        print('跳过：需要 pip install pytest（数据驱动断言已用标准库循环跑通）')


demo_02_pytest()


# ===== 03 · 源文节 CSV / JSON / YAML 用例表驱动同一套断言 · 演示 三种载体统一解析、int 归一化、同一 run_case =====
def demo_03_case_table():
    import csv
    import io
    import json

    CSV_TABLE = """id,path,status,name
1,/api/user/7,200,ann
2,/api/user/8,200,bob
3,/api/user/0,404,
"""

    JSON_TABLE = [
        {'id': '4', 'path': '/api/user/7', 'status': 200, 'name': 'ann'},
        {'id': '5', 'path': '/api/user/8', 'status': 200, 'name': 'bob'},
    ]

    YAML_TEXT = """- id: '6'
  path: /api/user/7
  status: 200
  name: ann
"""

    def run_case(case):
        status = 200 if case['path'] != '/api/user/0' else 404
        return int(case['status']) == status

    def load_csv(text):
        return list(csv.DictReader(io.StringIO(text)))

    def load_yaml(text):
        try:
            import yaml
            return yaml.safe_load(text)
        except ImportError:
            print('未装 PyYAML，跳过 YAML 分支')
            return []

    cases = load_csv(CSV_TABLE) + JSON_TABLE + load_yaml(YAML_TEXT)
    results = [(c['id'], run_case(c)) for c in cases]
    for cid, ok in results:
        print('case', cid, 'pass' if ok else 'fail')
    print('total', len(results), 'passed', sum(ok for _, ok in results))


demo_03_case_table()


# ===== 04 · 源文节 报告、日志与失败现场 · 演示 解析 JUnit XML、算失败率、合并门禁判断 =====
def demo_04_junit():
    import xml.etree.ElementTree as ET

    SAMPLE = '''<testsuites><testsuite tests="3" failures="1" errors="0">
  <testcase classname="api" name="test_ok"/>
  <testcase classname="api" name="test_flaky"><failure message="boom"/></testcase>
  <testcase classname="api" name="test_ok2"/>
</testsuite></testsuites>'''

    root = ET.fromstring(SAMPLE)
    suite = root.find('testsuite')
    total = int(suite.get('tests'))
    failed = [tc.get('name') for tc in suite.findall('testcase')
              if tc.find('failure') is not None or tc.find('error') is not None]
    rate = len(failed) / total if total else 0.0
    print('用例数', total, '失败', failed, '失败率', '{:.0%}'.format(rate))
    print('门禁', '通过' if rate == 0 else '拦截合并')


demo_04_junit()


# ===== 05 · 源文节 Selenium 显式等待与 Page Object · 演示 登录页封装、WebDriverWait、失败截图与 finally quit =====
def demo_05_selenium_po():
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        class LoginPage:
            URL = 'https://example.com/login'
            USER = (By.ID, 'username')
            PWD = (By.ID, 'password')
            SUBMIT = (By.ID, 'submit')
            FLASH = (By.CSS_SELECTOR, '.flash')

            def __init__(self, driver, wait):
                self.driver = driver
                self.wait = wait

            def open(self):
                self.driver.get(self.URL)

            def login(self, user, pwd):
                self.wait.until(EC.visibility_of_element_located(self.USER)).send_keys(user)
                self.driver.find_element(*self.PWD).send_keys(pwd)
                self.driver.find_element(*self.SUBMIT).click()

            def message(self):
                return self.wait.until(EC.visibility_of_element_located(self.FLASH)).text

        def run_login_demo():
            opts = Options()
            opts.add_argument('--headless=new')
            opts.add_argument('--no-sandbox')
            driver = webdriver.Chrome(options=opts)
            try:
                wait = WebDriverWait(driver, 10, poll_frequency=0.2,
                                     ignored_exceptions=[Exception])
                page = LoginPage(driver, wait)
                page.open()
                page.login('ann', 'secret')
                print('登录后提示：', page.message())
            except Exception:
                driver.save_screenshot('failure.png')
                raise
            finally:
                driver.quit()

        print('selenium 可用：LoginPage 与 run_login_demo 骨架已定义')
        print('按约束不启动浏览器、不访问外网，故不调用 run_login_demo()')
    except ImportError:
        print('跳过：需要 pip install selenium')


demo_05_selenium_po()


# ===== 06 · 源文节 失败截图、重试与 Mock 外部依赖 · 演示 patch.object 造超时网关、带上限重试 =====
def demo_06_mock_retry():
    import time
    from unittest.mock import patch

    class Gateway:
        def charge(self, order_id):
            raise RuntimeError('真实网关不可在测试里调用')

    attempts = {'n': 0}

    def flaky_charge(self, order_id):
        attempts['n'] += 1
        if attempts['n'] < 3:
            raise TimeoutError('网关超时')
        return {'order': order_id, 'paid': True}

    def retry(fn, times=3, delay=0.01):
        for i in range(times):
            try:
                return fn()
            except TimeoutError:
                if i == times - 1:
                    raise
                time.sleep(delay)

    with patch.object(Gateway, 'charge', flaky_charge):
        gateway = Gateway()
        result = retry(lambda: gateway.charge('A-1001'))
        print('结果', result, '尝试次数', attempts['n'])


demo_06_mock_retry()


# ===== 07 · 源文节 练习 1 · 给用例表加超时字段 · 演示 读 timeout 列、float 归一化、作为断言参数 =====
def demo_07_exercise1():
    import csv
    import io

    TABLE = "id,path,status,timeout\n1,/ping,200,2\n2,/slow,200,5\n"

    def check(row):
        # 真实场景里是 requests.get(url, timeout=float(row['timeout']))
        timeout = float(row['timeout'])
        return timeout > 0 and row['status'] == '200'

    rows = list(csv.DictReader(io.StringIO(TABLE)))
    print([(r['id'], check(r)) for r in rows])


demo_07_exercise1()


# ===== 08 · 源文节 练习 2 · 用显式等待替换固定 sleep · 演示 可复用的 wait_visible 封装 =====
def demo_08_exercise2():
    try:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import WebDriverWait

        def wait_visible(driver, selector, timeout=10):
            return WebDriverWait(driver, timeout, poll_frequency=0.2).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
            )

        print('selenium 可用：wait_visible 显式等待封装已定义（需真实 driver，示例不调用）')
    except ImportError:
        print('跳过：需要 pip install selenium')


demo_08_exercise2()
