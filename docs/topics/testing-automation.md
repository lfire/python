---
title: 接口与 Web UI 自动化测试
description: 从 Postman 调试到 pytest 数据驱动，再到 Selenium 显式等待、Page Object 与 CI 测试门禁，补齐跨进程接口与浏览器页面的回归验证。
---

# 接口与 Web UI 自动化测试

前面 075、076 讲把单元测试与 Mock 讲透了：验证进程内一个函数、类的行为，快、稳、失败能定位到具体行。可真实交付物常常不是一个函数，而是一个 HTTP 接口、一个登录后的浏览器页面——请求要过网络、带会话、读数据库，页面还得等元素渲染完。用 Postman 点几下只能确认「此刻通了」，留不下可反复跑的回归用例；靠人肉点检 UI，前端改一次就得从头再点一遍。这一篇把这两类跨进程验证补齐：先划清接口测试与单元测试各管哪一段，再从 Postman 调试落到 `requests` 会话与断言，接着用 pytest 的 fixture、参数化和 CSV / JSON / YAML 用例表把一次调试扩成一批用例；后半程转向 Web UI，讲 Selenium 显式等待、Page Object、失败截图与重试，最后收在报告、Mock 隔离与 CI 门禁及 flaky 治理上。接口示例自带本地服务，不依赖外网。

## 接口测试与单元测试各管哪一段

单元测试把依赖替身掉，只盯着公开行为与边界条件；接口测试恰恰相反，它要保留网络、鉴权、数据库这些真实环节，验证的是「一个请求打进去，系统对外给出的契约有没有变」。两者不是替代关系，而是分层：底层用大量快而稳的单测覆盖分支，中层用接口测试守住服务之间的契约，顶层只留极少量端到端用例走关键用户路径。把接口用例写得太像单测（处处深度替换内部函数），重构一来照样全红，却没验证任何外部行为；把单元测试搬去连真实数据库，套件又会慢到没人愿意跑。

| 维度 | 单元测试 | 接口测试 |
| --- | --- | --- |
| 被测对象 | 进程内的函数、类 | 跨进程的 HTTP 端点 |
| 依赖处理 | 用替身隔离 IO，不碰网络 | 保留或近似真实的鉴权、数据库、缓存 |
| 运行速度 | 毫秒级，可跑成百上千条 | 百毫秒到秒级，通常几十到几百条 |
| 失败定位 | 断言重写直接指到某一行 | 先看状态码与响应体，再查服务端日志 |
| 断言重心 | 返回值、异常、边界条件 | 契约：状态码、字段、结构、副作用 |
| 典型工具 | `pytest`、`unittest.mock` | `requests`、`pytest`、Postman |

### 一次接口请求要断言哪些东西

新手最容易只写 `assert resp.status_code == 200`。可不少服务把业务错误包在 200 的响应体里，或者字段悄悄改名、类型从整数变成字符串，单看状态码一路绿灯。稳妥的做法是把断言分层：传输层看状态码和 `Content-Type`，结构层用 schema 校验必填字段与类型，业务层核对具体值与列表约束，再往外一层查副作用与非功能约束。断言越靠外层越慢越脆，所以契约测试里通常把副作用检查留给少量关键用例，不逐条都查库。

| 断言层 | 具体检查 | 漏掉之后的后果 |
| --- | --- | --- |
| 传输层 | 状态码、`Content-Type`、关键响应头 | 只判 200 会放过 200 包装的错误 body |
| 结构层 | JSON schema、必填字段、字段类型 | 字段改名或类型漂移悄悄溜过回归 |
| 业务层 | 字段值、列表长度、排序、枚举取值 | 接口返回了数据，值却不对 |
| 副作用 | 数据库落库、缓存更新、消息投递 | 响应说成功，数据其实没写进去 |
| 非功能 | 耗时上限、幂等性、并发安全 | 超时或重复提交把线上拖垮 |

## 把 Postman 里的调试固化成用例

Postman 适合做探路：在图形界面里填好 URL、请求头和 body，点发送，用 `Tests` 标签里几行 `pm.test` 先看返回值。它的 `Collection` 能把一组请求存成文件，`Environment` 把域名、token 抽成变量，`Pre-request Script` 能在发送前算签名或取时间戳。问题在于，这些脚本跑在 Postman 自己的沙箱里，变量和断言逻辑无法直接被 CI 调度，也很难做复杂的数据驱动与分支覆盖。所以合理的分工是：Postman 用来确认接口长什么样、把请求要素抄下来，随后迁到代码里沉淀成可版本控制、可参数化、可被门禁拦截的用例。

迁移时有三样能直接搬：请求方法与路径、请求头与 body 模板、以及环境变量里的域名和凭据名。三样要重写：沙箱里的 `pm.*` API 换成 Python 的断言与 `requests`，`Pre-request Script` 里的签名计算换成普通函数，动态 token 的获取换成 fixture 里的一次登录并缓存。尤其要留意，别把真实 token 连同 `Collection` 一起提交进仓库——变量值留在 `.env`，仓库里只放变量名和占位文件。

## 用 requests.Session 收敛公共行为

拿到接口要素后，第一件事不是逐条写用例，而是把公共行为收进一个 `requests.Session`：基址、`Accept` 头、鉴权头、默认超时都挂到会话上，用例里只写差异部分。这样既少写重复代码，也让「所有请求都带超时」成为一条硬约束，而不是靠每个人自觉。下面这段自带一个本地 `HTTPServer`，`expect` 把状态码与若干字段合并成一条断言，失败时能直接打印出是哪个字段对不上。

用到 `requests`，安装命令见下方。

```bash
pip install requests
```

```python
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests


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


server = HTTPServer(('127.0.0.1', 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
BASE = 'http://127.0.0.1:{}'.format(server.server_port)


def expect(resp, status, **fields):
    assert resp.status_code == status, (resp.status_code, status)
    assert 'json' in resp.headers.get('Content-Type', ''), resp.headers
    data = resp.json()
    for key, value in fields.items():
        assert data[key] == value, (key, data.get(key), value)
    return data


with requests.Session() as session:
    session.headers.update({'Accept': 'application/json'})
    expect(session.get(BASE + '/api/user', timeout=3), 200, id=7, name='ann')
    missing = session.get(BASE + '/missing', timeout=3)
    assert missing.status_code == 404
    print('接口断言通过')

server.shutdown()
```

真实项目里把 `BASE` 换成环境里的域名，把 `timeout=3` 提到会话级的适配器上。断言辅助函数值得单独放进 `helpers.py`：一旦契约改动，只改一处校验规则，不必翻遍所有用例。

## pytest 的 fixture 与参数化收拢用例

`requests` 解决「怎么发请求」，pytest 解决「怎么把很多请求管起来」。`@pytest.fixture` 负责准备一次用例所需的状态：登录拿 token、建一个会话、塞一份测试数据，并用 `yield` 保证用例结束无论成败都清理。`@pytest.mark.parametrize` 负责把一条断言展开成多组独立用例，`ids` 让失败信息能直接指出是哪组参数。两者配合，用例文件里几乎不出现循环，新增一组边界数据只是往 `CASES` 里加一行。

安装 `pytest` 并把它当作测试运行器，命令如下。

```bash
pip install pytest
python -m pytest test_api.py -q
```

把下面内容存成 `test_api.py`。`fake_get` 是替身，真实项目里换成上一节的 `session.get` 即可；fixture 返回一份每用例独立的配置，避免登录态在用例之间串味。

```python
import pytest


@pytest.fixture
def api_client():
    return {'base': 'http://127.0.0.1:8000', 'timeout': 3, 'token': None}


CASES = [
    ('/api/user/7', 200, {'id': 7, 'name': 'ann'}),
    ('/api/user/0', 404, {'error': 'not found'}),
    ('/api/user/-1', 400, {'error': 'bad id'}),
]


@pytest.mark.parametrize('path,status,payload', CASES,
                         ids=['found', 'missing', 'bad-id'])
def test_get_user(api_client, path, status, payload):
    got_status, got_body = fake_get(path, api_client)
    assert got_status == status
    assert got_body == payload


def fake_get(path, cfg):
    table = {
        '/api/user/7': (200, {'id': 7, 'name': 'ann'}),
        '/api/user/0': (404, {'error': 'not found'}),
        '/api/user/-1': (400, {'error': 'bad id'}),
    }
    return table[path]
```

`@pytest.mark.parametrize` 在收集期就把三组参数展开成三个独立用例，其中一个失败不会影响另外两个；`@pytest.mark.slow`、`-m` 这类标记还能把慢接口用例单独分组，让冒烟测试只跑 `p0` 标签。

## CSV / JSON / YAML 用例表驱动同一套断言

当边界值多到几十组时，把数据塞进 `CASES` 列表就不合适了：产品和测试更愿意改一张表，而不是改 Python 源码。做法是把用例抽成「用例表」，每行是一条用例，包含编号、请求要素和期望结果；加载器把 CSV、JSON、YAML 统一解析成字典列表，再交给同一套 `run_case`。这样新增用例不动代码，测试逻辑也只有一份。

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `id` | 用例唯一编号，失败时定位 | `TC-012` |
| `method` / `path` | 请求方法与路径 | `GET /api/user/7` |
| `headers` / `body` | 鉴权头与请求体 | `Authorization: Bearer ...` |
| `expect_status` | 期望状态码 | `200` |
| `expect_json` | 期望字段子集 | `id=7, role=member` |
| `timeout` | 单次超时秒数 | `3` |
| `tags` | 分组与门禁标签 | `smoke, p0` |

三种载体的取舍很直接：CSV 用 Excel 就能维护、适合大批量表格；JSON 能表达嵌套 body、和接口天然同构；YAML 写多行与注释更省心，适合人手写。下面这段把三者都解析出来并驱动同一个函数；YAML 分支用到 PyYAML，安装命令见下方，没装时会优雅跳过该分支，其余照跑。

```bash
pip install PyYAML
```

```python
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
```

`int(case['status'])` 这种归一化很关键：CSV 读出来全是字符串，JSON 读出来是整数，YAML 又可能带引号，加载器负责把它们抹平，断言函数才不用到处判断类型。真实场景里 `run_case` 内部换成 `session.request`，并把 `expect_json` 里的键值对交给上一节的 `expect` 校验。

## 报告、日志与失败现场

用例一多，「哪条挂了、为什么挂」比「通过率多少」更重要。`pytest` 加 `--junitxml=report.xml` 会产出 JUnit XML，几乎所有 CI 都能直接吃；`--tb=short` 精简堆栈，`-q` 压掉冗余输出，配 `pytest-html` 或 Allure 能生成带步骤、附件和趋势的网页报告。日志方面，把每次请求的方法、路径、耗时和响应摘要写进 `logging`，但不要记录完整响应体和鉴权头——接口测试跑在生产同构环境时，日志本身也可能泄漏数据。失败现场要留三样：断言里的实际值与期望值、服务端相关时间段的日志片段、以及 UI 用例的屏幕截图。下面这段解析 JUnit XML，算出失败率并做一个最简单的合并门禁判断。

```python
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
```

<Callout type='tip' title='报告里要留什么' text='失败现场至少保留实际值与期望值、相关时间段的服务端日志、以及浏览器截图，日志不要记录完整响应体和鉴权头' />

## Selenium 显式等待与 Page Object

接口层稳了，再往上就是浏览器。Selenium 通过 WebDriver 驱动真实浏览器，`webdriver.Chrome` 拿到驱动后，`find_element` 定位元素、`.click()` 与 `.send_keys()` 模拟操作。最大的坑来自「时间差」：页面是异步渲染的，脚本执行往往比元素出现更快，于是 `NoSuchElementException` 时有时无。固定 `time.sleep` 是最脆的解法——网络快时白等，网络慢时照样失败，还把套件拖长。正确姿势是显式等待：`WebDriverWait` 针对某个条件轮询，`expected_conditions` 提供可见、可点击、存在等常用判定，超时才抛错。

| 策略 | 写法 | 适用与问题 |
| --- | --- | --- |
| 固定等待 | `time.sleep(3)` | 最脆，网快白等、网慢仍失败 |
| 隐式等待 | `implicitly_wait(10)` | 全局生效，仅对查找生效，与显式混用会叠加超时 |
| 显式等待 | `WebDriverWait` + `expected_conditions` | 针对具体条件轮询，推荐做法 |
| Fluent 等待 | 自定义 `poll_frequency` 与忽略异常列表 | 需要吞掉特定异常时用 |

界面一多，选择器散落在各个用例里，前端改个 class 就得全局搜索替换。Page Object 把每个页面封成一个类：元素定位器是类属性，操作是方法，用例只调用 `page.login(...)` 这样语义化的动作，完全不碰 `By.CSS_SELECTOR`。这样定位器变更只改一处，用例读起来也像业务流程。下面给一个最小可运行骨架，登录页封装成一个类，等待统一走 `WebDriverWait`，异常时留截图，`finally` 里一定 `quit()` 释放浏览器。

用到 `selenium`，安装命令见下方；无界面环境用 `Options` 里的 `--headless=new`，本机没有浏览器时可退回到上一节的接口契约测试，或在 CI 上用 Xvfb 提供虚拟显示。

```bash
pip install selenium
```

```python
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
```

`ignored_exceptions` 这里为求骨架简洁传了 `Exception`，真实项目应收窄到 `NoSuchElementException` 一类，否则会把断言错误也吞掉。Selenium 4 起自带 Selenium Manager，能自动匹配下载驱动，不必再手工放 `chromedriver`。

## 失败截图、重试与 Mock 外部依赖

`save_screenshot('failure.png')` 放在 `except` 里，是 UI 用例最省事的现场留存：配合 JUnit XML 的附件或 Allure 的 `attach`，失败报告里能直接看到当时页面长什么样。重试要克制：`pytest-rerunfailures` 的 `--reruns 2` 适合吸收偶发网络抖动，但一律绿灯会掩盖真缺陷，所以重试用例必须在报告里标注，并设上限。至于外部依赖——支付网关、短信、第三方天气接口——不该在测试里真调，用 `unittest.mock.patch` 或 `responses` 把它们替身成可控的返回，既能造超时、造错误码，也不会产生真实扣费。下面用 `patch.object` 模拟一个前两次超时、第三次成功的网关，再套一个带上限的重试函数。

```python
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
```

替身要装得像：返回值结构、异常类型、甚至超时的节奏都得贴近真实契约，否则测试通过只说明替身写得对。`patch` 作为上下文管理器退出后会自动还原，用例之间不残留状态，这一点和 `monkeypatch` 的自动 undo 是同一个意思。

## CI 里的测试门禁与 flaky 用例治理

把上面几块搬进 CI，一条典型的流水线是：装依赖、起被测服务、跑 `pytest --junitxml=report.xml`、上传报告与截图、最后按失败率决定是否放行合并。GitHub Actions 里可以写成下面这样，接口冒烟用例单独用 `-m smoke` 跑，失败即阻断。

```yaml
name: api-tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt pytest
      - run: python -m pytest -m smoke --junitxml=report.xml -q
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: report
          path: |
            report.xml
            failure.png
```

门禁真正的敌人是 flaky 用例：同一份代码，这次红、下次绿，久了没人再信红灯。治理动作按性质分开，不能一律靠重跑压下去。

| 现象 | 常见根因 | 修复动作 |
| --- | --- | --- |
| 偶发超时 | 固定 `sleep`、未设 `timeout` | 改显式等待，给所有请求统一超时 |
| 元素失效 | 页面重渲染后仍用旧引用 | Page Object 方法内每次重新定位，不缓存 `WebElement` |
| 用例串味 | 共享登录态、用例顺序依赖 | fixture 每用例独立，数据自带清理 |
| 重试掩盖真缺陷 | 无差别 `--reruns` 全过 | 先入 quarantine、标注 flaky、定位根因后再决定去留 |
| 红灯长期无人修 | 无门禁、无负责人 | 失败率门禁阻断合并，按 `tags` 指派归属 |

一个可持续的约定是：发现 flaky 先打 `xfail(strict=True)` 或 `quarantine` 标记移出阻断集，同时建一条跟踪项；根因修复、连续若干次稳定通过后再放回主套件。严格模式能保证真修好了不会忘记摘标记。覆盖率与通过率一样，只当发现盲区的线索，别拿 100% 当目标。

## 常见坑 / 边界

1. **只断言 `status_code == 200`，不看响应体**：不少服务把业务错误包在 200 里，字段改名也照样绿灯。修复：用 `expect` 一类辅助函数合并状态码、`Content-Type` 与字段断言，关键结构用 `jsonschema` 校验必填字段和类型。
2. **用 `time.sleep` 等页面元素**：网络快白等、网络慢仍失败，套件被拖长且随机红。修复：换成 `WebDriverWait` 加 `expected_conditions`，按需设 `poll_frequency`，只忽略该忽略的异常。
3. **`requests` 调用不设 `timeout`**：CI 里一个挂起的连接能让整轮测试卡死到超时被杀。修复：每次调用都带 `timeout`，或把默认值挂到会话适配器上，配合重试上限。
4. **把重试当万能药**：`--reruns 3` 让所有偶发失败变绿，真 bug 被埋起来。修复：先 quarantine 并标注 flaky，定位根因，重试只留次数上限且必须在报告里可见。
5. **`StaleElementReferenceException` 反复出现**：DOM 重渲染后复用了旧的元素引用。修复：Page Object 的方法里每次操作前重新 `find_element`，不要把 `WebElement` 存成实例属性跨步骤复用。

## 两道练习

::: details 练习 1 · 给用例表加超时字段
在 CSV 用例表里新增一列 `timeout`，写出读取该列、做一次类型归一化、并把它作为超时参数传给断言函数的参考解。想清楚为什么 CSV 读出来的值要先转换。

```python
# 参考解
import csv
import io

TABLE = "id,path,status,timeout\n1,/ping,200,2\n2,/slow,200,5\n"


def check(row):
    # 真实场景里是 requests.get(url, timeout=float(row['timeout']))
    timeout = float(row['timeout'])
    return timeout > 0 and row['status'] == '200'


rows = list(csv.DictReader(io.StringIO(TABLE)))
print([(r['id'], check(r)) for r in rows])
```
:::

::: details 练习 2 · 用显式等待替换固定 sleep
把等待提示条出现的 `time.sleep(2)` 改成 `WebDriverWait` 等待元素可见，写出可复用的最小参考解，并说明超时参数放在哪一层更合适。

```python
# 参考解
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def wait_visible(driver, selector, timeout=10):
    return WebDriverWait(driver, timeout, poll_frequency=0.2).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
    )


# 调用：wait_visible(driver, '.flash').text
# 超时值由调用方按页面特性传入，封装里只给默认值
```
:::

回到 [专题补遗](/topics/) · [课程总目录](/guide/curriculum)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能跑通本专题按正文顺序整理的标准库示例；需要第三方库的片段会自动跳过并打印安装提示，不装任何库也能看到核心结果。" />

**本专题示例代码** · 仓内路径 `examples/topics/testing-automation.py`

```bash
python3 examples/topics/testing-automation.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/topics/testing-automation.py) · [全部示例代码索引](/examples/)
