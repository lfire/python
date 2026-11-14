---
title: Scrapy 与反爬合规：从 Spider 到生产采集
description: 从 Engine、Scheduler、Downloader、Spider、Pipeline 的数据流，到选择器与 Item、中间件重试、Scrapyd 定时部署、限速并发与 robots、登录态与 Ajax 接口、去重增量与失败隔离，以及采集合规的边界。
---

# Scrapy 与反爬合规：从 Spider 到生产采集

正文用 `asyncio` 加 `aiohttp` 手写过抓取循环：起一批协程、拿 `asyncio.Queue` 当待抓队列、每个请求自己 `try/except` 重试、结果手动写进文件。盯一两个页面没问题，一旦要同时盯多个站点、每天定时重跑、中途失败能续跑、还得控制别把对方打疼，这些散在脚本里的调度、去重、限速、持久化就开始打架：队列重启即空、重试各写一份、限速靠 `sleep` 拍脑袋。Scrapy 把这些横切关注点固定成组件，你只往里填业务规则。本专题按数据流动的顺序展开：先看 `Engine` 到 `Item Pipeline` 的五个组件与请求如何穿过它们，再落到 Spider 选择器、Item 与 Pipeline 写库，接着是下载器中间件与重试、限速并发与 `robots.txt`、登录态与 Ajax 接口，然后是 Scrapyd 部署与定时、去重增量与失败隔离，最后把合规底线讲清楚——哪些采集能做、哪些防护不该碰。

## 从手写抓取循环到五大组件的数据流

一次抓取在五个组件间流转。`Spider` 的 `start_requests` 产出 `Request`，`Engine` 先交给 `Scheduler` 入队并算指纹去重；出队后 `Engine` 经下载器中间件把请求送给 `Downloader`，拿到 `Response` 再沿中间件回到 `Engine`，转交 `Spider` 的回调解析。回调 `yield` 出的 `Item` 依次穿过 `Item Pipeline`，`yield` 出的新 `Request` 回到 `Scheduler` 继续循环。`Engine` 不解析内容、不落库，只负责搬运与触发信号，所以任何组件抛异常都会被收敛成日志或 `errback`，不至于让整个爬虫崩掉。把这条链路记住，后面每个配置项挂在哪一环就清楚了。

**五个组件各管一段**

| 组件 | 职责 | 通常在哪里改 |
| --- | --- | --- |
| `Engine` | 总控数据流，在其余组件间搬运 `Request`、`Response`、`Item`，触发信号 | 一般不动 |
| `Scheduler` | 维护待抓队列与去重指纹，决定下一个出队的请求 | 换调度器、配优先级与持久化 |
| `Downloader` | 真正发 HTTP 请求拿响应，受并发、超时与中间件约束 | 调并发、超时、加中间件 |
| `Spiders` | 你写的解析类，产出 `Request` 或 `Item` | 业务解析规则全在这里 |
| `Item Pipeline` | 清洗、校验、去重、写库 | 落库与清洗逻辑 |

`Scheduler` 与 `Downloader` 之间夹着下载器中间件，`Downloader` 与 `Engine` 之间也过一遍，这个夹层是限速、代理、重试、Cookie 的落点。`Spider` 与 `Engine` 之间有爬虫中间件，处理 `Spider` 的输入输出与异常，用得少一些。

## 装 Scrapy、建项目与目录结构

用虚拟环境隔离依赖，再用 `startproject` 生成骨架。生成器只给目录和空文件，爬虫类要么用 `genspider` 起个模板，要么自己在 `spiders/` 下新建。

```bash
python -m venv .venv
source .venv/bin/activate
pip install scrapy
scrapy startproject demo
cd demo
scrapy genspider books books.example.org
scrapy shell "https://books.example.org/latest"
```

生成的目录里，`scrapy.cfg` 是部署描述文件，`demo/settings.py` 放全局配置，`demo/items.py` 声明数据结构，`demo/pipelines.py` 写落库，`demo/middlewares.py` 放钩子，`demo/spiders/` 存爬虫。`scrapy shell` 会起一个带 `response` 对象的交互环境，用来现场试选择器最省事。

```text
demo/
├── scrapy.cfg
└── demo/
    ├── __init__.py
    ├── items.py
    ├── middlewares.py
    ├── pipelines.py
    ├── settings.py
    └── spiders/
        ├── __init__.py
        └── books.py
```

### Spider、start_requests 与选择器

一个 Spider 至少要有 `name` 和起始请求。用 `start_urls` 时框架默认调 `start_requests` 逐个发 `GET`；要带请求头、走 `POST`、或先登录，就自己覆写 `start_requests`。解析靠 `response.css()` 与 `response.xpath()`，两者都返回选择器列表，`get()` 取首个文本、`getall()` 取全部、`attrib` 取属性，查不到时返回 `None` 而不是抛异常。

```python
import scrapy

class BookSpider(scrapy.Spider):
    name = 'books'
    allowed_domains = ['books.example.org']
    start_urls = ['https://books.example.org/latest']

    custom_settings = {
        'DOWNLOAD_DELAY': 1.0,
        'ROBOTSTXT_OBEY': True,
    }

    def parse(self, response):
        for card in response.css('article.book'):
            yield {
                'title': card.css('h2::text').get(default='').strip(),
                'price': card.css('span.price::text').re_first(r'[\d.]+'),
                'url': response.urljoin(card.css('a::attr(href)').get()),
            }
        next_page = response.css('a.next::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)
```

`response.follow` 会自动把相对链接补成绝对地址，比手动 `urljoin` 再构造 `Request` 稳；`allowed_domains` 把意外的外链请求挡在队列外，避免爬着爬着跑到别的站点。翻页也是 `yield` 一个带 `callback` 的请求，于是同一套解析逻辑能一直复用下去。

**CSS 与 XPath 常用对照**

| 目标 | CSS 写法 | XPath 写法 |
| --- | --- | --- |
| 取某标签文本 | `h2::text` | `//h2/text()` |
| 取链接地址 | `a::attr(href)` | `//a/@href` |
| 按类名筛选 | `article.book` | `//article[@class="book"]` |
| 取首个结果 | `get()` | `get()` |
| 取全部结果 | `getall()` | `getall()` |

写选择器时优先用稳定的语义类名或 `data-` 属性，别依赖「第几个 `div`」这种随改版就失效的位置路径。字段缺失用 `get(default='')` 兜底，比在 Pipeline 里到处判 `None` 干净。

### Item 定义与 Pipeline 落库

上例直接 `yield` 字典，字段一多就容易写错键名。把字段声明成 `scrapy.Item`，后面清洗和校验能按名取值，配合 `itemadapter` 还能让同一套 Pipeline 同时吃 `Item`、`dict` 与 `dataclass`。

```python
# items.py
import scrapy

class BookItem(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()
    url = scrapy.Field()
    source = scrapy.Field()
```

```python
# pipelines.py
from itemadapter import ItemAdapter
import sqlite3

class PricePipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        raw = adapter.get('price')
        adapter['price'] = float(raw) if raw else 0.0
        adapter['source'] = spider.name
        return item

class SqlitePipeline:
    def open_spider(self, spider):
        self.conn = sqlite3.connect('books.db')
        self.conn.execute(
            'CREATE TABLE IF NOT EXISTS books '
            '(title TEXT, price REAL, url TEXT UNIQUE, source TEXT)'
        )

    def close_spider(self, spider):
        self.conn.close()

    def process_item(self, item, spider):
        a = ItemAdapter(item)
        self.conn.execute(
            'INSERT OR IGNORE INTO books VALUES (?, ?, ?, ?)',
            (a['title'], a['price'], a['url'], a['source']),
        )
        self.conn.commit()
        return item
```

`open_spider` 与 `close_spider` 是爬虫生命周期钩子，适合开连接、建表、最后关连接。`process_item` 必须 `return item`，否则后续 Pipeline 收不到数据；要丢掉某条数据就抛 `DropItem`。注册靠 `ITEM_PIPELINES` 字典，数值越小越先执行。

```python
# settings.py
ITEM_PIPELINES = {
    'demo.pipelines.PricePipeline': 300,
    'demo.pipelines.SqlitePipeline': 800,
}
```

**Pipeline 的执行顺序与职责**

| 数值 | 组件 | 对 Item 做的事 |
| --- | --- | --- |
| 300 | `PricePipeline` | 把价格字符串转成 `float`、缺失置 `0.0`、补来源字段 |
| 800 | `SqlitePipeline` | 用 `INSERT OR IGNORE` 配合 `url` 唯一键幂等写库 |

把清洗放在写库之前是有意的：写库组件拿到的一定是规范值。唯一键 + `INSERT OR IGNORE` 让整段爬虫重跑也不会插重复行，这是最便宜的幂等保障。

## 下载器中间件、重试与请求指纹

中间件分请求方向与响应方向两趟：`process_request` 按数值从小到大依次改写请求，`process_response` 再按数值从大到小倒着处理响应。想覆盖默认 `User-Agent`，数值就得排在内置 `UserAgentMiddleware` 之后；想让自定义重试先看到失败，就得排在 `RetryMiddleware` 附近。

```python
# middlewares.py
import random
from scrapy import signals

class RotateUserAgentMiddleware:
    def __init__(self, agents):
        self.agents = agents

    @classmethod
    def from_crawler(cls, crawler):
        mw = cls(crawler.settings.getlist('USER_AGENT_CHOICES'))
        crawler.signals.connect(mw.spider_opened, signal=signals.spider_opened)
        return mw

    def process_request(self, request, spider):
        request.headers.setdefault('User-Agent', random.choice(self.agents))

    def spider_opened(self, spider):
        spider.logger.info('spider opened: %s', spider.name)
```

`from_crawler` 是拿到 `settings` 与 `signals` 的标准入口。内置 `RetryMiddleware` 已经处理连接超时、`500`、`502`、`503`、`504`、`408` 这类抖动，用 `RETRY_TIMES` 与 `RETRY_HTTP_CODES` 调；默认去重指纹由 `request_fingerprint` 按方法、规范化后的 URL、请求体算出，想重复抓同一地址就给请求加 `dont_filter=True`。

**下载器中间件顺序（请求方向，数值小的先执行）**

| 数值 | 中间件 | 作用 |
| --- | --- | --- |
| 100 | `RobotsTxtMiddleware` | 拉取并缓存 `robots.txt`，拒绝被禁的 URL |
| 400 | `DefaultHeadersMiddleware` | 补 `DEFAULT_REQUEST_HEADERS` |
| 500 | `UserAgentMiddleware` | 设置默认 `User-Agent` |
| 550 | `RetryMiddleware` | 超时与 `RETRY_HTTP_CODES` 触发重试 |
| 590 | `HttpCompressionMiddleware` | 解压 gzip / deflate 响应 |
| 600 | `RedirectMiddleware` | 处理 3xx 跳转 |
| 700 | `CookiesMiddleware` | 维护会话 Cookie |
| 710 | `HttpProxyMiddleware` | 应用代理设置 |

不同版本数值略有出入，用 `scrapy settings --get DOWNLOADER_MIDDLEWARES_BASE` 能核对本机实际值。自定义中间件注册进 `DOWNLOADER_MIDDLEWARES` 时给一个不冲突的数字；设为 `None` 可关掉某个内置中间件。

## 限速、并发与 robots.txt 开关

采集对站点是否友好，几乎全由这一组参数决定。全局并发与单域名并发要分开看：前者管总量，后者才决定你瞬间打到同一个站点几条连接。`AUTOTHROTTLE` 会依据实测响应延迟自动把间隔拉长，对方变慢时你也跟着变慢，比写死一个 `DOWNLOAD_DELAY` 稳妥。

```python
# settings.py —— 对站点友好的默认值
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS = 8
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 1.0
RANDOMIZE_DOWNLOAD_DELAY = True
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 2.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
DOWNLOAD_TIMEOUT = 20
RETRY_TIMES = 2
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]
```

`ROBOTSTXT_OBEY` 默认其实是 `False`，模板不会替你打开，得手动设成 `True`。把 `429` 放进 `RETRY_HTTP_CODES` 是为了让退避有依据，但重试次数必须封顶，遇到持续限流应当停止而不是一直试。

**关键限速参数**

| 参数 | 默认值 | 含义与建议 |
| --- | --- | --- |
| `ROBOTSTXT_OBEY` | `False` | 是否遵守 `robots.txt`，生产建议置为 `True` |
| `CONCURRENT_REQUESTS` | `16` | 全局并发上限 |
| `CONCURRENT_REQUESTS_PER_DOMAIN` | `8` | 单域名并发，压低它对站点更友好 |
| `DOWNLOAD_DELAY` | `0` | 同域名两次请求的最小间隔秒数 |
| `RANDOMIZE_DOWNLOAD_DELAY` | `True` | 把间隔在 0.5 到 1.5 倍间打散，避免整齐的机械节奏 |
| `AUTOTHROTTLE_ENABLED` | `False` | 按往返延迟动态调速 |
| `RETRY_TIMES` | `2` | 单请求最大重试次数，不含首次 |
| `DOWNLOAD_TIMEOUT` | `180` | 单次请求超时秒数，生产调小便于快速失败 |

<Callout type='warn' title='采集前先确认授权' text='遵守目标站点的 robots.txt 与服务条款，只抓取允许公开访问、且你有合法使用依据的数据；对明确禁止爬取、需要授权或涉及个人信息的内容，不采集、不绕过。技术能力不等于授权。' />

<Callout type='warn' title='重试不是无限重试' text='RETRY_TIMES 只兜住偶发抖动；对持续出现的 403、429 或验证码，正确动作是降低频率并停止该目标，而不是加大重试或换一批出口地址，后者只是把压力转嫁给对方站点。' />

## 登录态 Cookie、Ajax 接口与请求头

需要登录才能看的数据，前提是账号属于你自己、且站点条款允许以这种方式访问。Scrapy 用 `FormRequest.from_response` 自动带上登录表单里的隐藏字段和 Cookie，`meta` 里的 `cookiejar` 用来隔离不同会话。很多列表页的数据其实来自一个返回 JSON 的 Ajax 接口，直接解析 `json.loads(response.text)` 比抠 DOM 稳得多，也更省请求。

```python
import scrapy
import json

class AccountSpider(scrapy.Spider):
    name = 'account'

    def start_requests(self):
        yield scrapy.Request(
            'https://example.org/login',
            callback=self.after_login,
            meta={'cookiejar': 1},
        )

    def after_login(self, response):
        token = response.css('input[name=csrf]::attr(value)').get()
        return scrapy.FormRequest.from_response(
            response,
            formdata={'username': 'demo', 'password': 'secret', 'csrf': token or ''},
            meta={'cookiejar': response.meta['cookiejar']},
            callback=self.parse_api,
        )

    def parse_api(self, response):
        if response.status != 200:
            self.logger.warning('login failed or blocked: %s', response.status)
            return
        data = json.loads(response.text)
        for row in data.get('items', []):
            yield {'id': row['id'], 'title': row.get('title', '')}
        next_url = data.get('next')
        if next_url:
            yield response.follow(
                next_url,
                callback=self.parse_api,
                headers={'Accept': 'application/json'},
                meta={'cookiejar': response.meta['cookiejar']},
            )
```

关键动作有三个：解析前先判 `response.status`，别把拦截页当成空数据；隐藏字段交给 `from_response` 提取，别手抄；`cookiejar` 在整条请求链上保持一致，翻页时别丢。凭据从环境变量或密钥文件读，不要硬编码进仓库，更不要用他人的账号或批量共享的账号池。接口若要求 `X-Requested-With` 一类请求头，用 `headers` 如实声明即可，别去伪造与真实浏览器不一致的指纹组合。

## 字体加密、验证码与代理 IP 的原理边界

现实中会碰到几类让自动化变难的机制，先弄清它们为什么存在，才知道该退到哪里。字体加密是站点用自定义字体把数字或汉字的码位与字形重新映射，页面看到的是乱码、渲染后才是正常文字；验证码用一道人机区分题挡住脚本；频率与 IP 封禁根据请求节奏和来源地址判断异常；代理池则常被用来分摊出口。这些机制的共性是抬高自动化的成本，而不是给你一道待解的题。

合规的应对顺序很固定：先查有没有官方开放接口、数据导出或申请授权的通道；再核对 `robots.txt` 与服务条款是否允许该路径与频率；然后把自己的并发和间隔压到对方能承受的范围；碰到验证码、字体映射或封禁，就停下该字段或该目标。本站只讲这些机制的成因与边界，不提供字体映射还原、验证码批量识别、用代理池规避封禁等绕过防护的具体手法。

**防护手段、成因与合规应对**

| 手段 | 站点为什么做 | 能做的合规动作 | 不碰的红线 |
| --- | --- | --- | --- |
| `robots.txt` 与服务条款 | 声明可抓范围 | 抓取前读取并遵守，对禁止路径直接过滤 | 无视声明继续抓 |
| 限速与 `429`、`403` | 保护容量 | 降并发、退避、必要时停止 | 轮换大量出口地址顶着抓 |
| 登录态与 Cookie | 区分身份与授权 | 用自己合法账号、低频率访问 | 盗用凭据、共享账号池 |
| 验证码 | 区分人与脚本 | 遇到就停下，或改走官方接口 | 接打码平台、训练识别模型批量破 |
| 字体加密与动态混淆 | 抬高解析成本 | 找官方数据源或授权导出 | 逆向字体映射批量还原 |
| 代理 IP 池 | 隐藏来源、分摊压力 | 仅用于自己多机房出口的容灾 | 靠换 IP 规避封禁继续采 |

## Scrapyd 部署、调度 API 与定时任务

本地用 `scrapy crawl books` 只是开发态。长期跑要有个常驻服务托管项目、记录每次任务、暴露调度接口，Scrapyd 就做这件事：它监听一个 HTTP 端口，接收打好的 egg 包，按项目名与爬虫名启动进程，把日志和任务状态落到磁盘。`scrapy.cfg` 里写明部署目标。

```ini
[settings]
default = demo.settings

[deploy:local]
url = http://127.0.0.1:6800/
project = demo
```

```bash
pip install scrapyd scrapyd-client
scrapyd
# 在含 scrapy.cfg 的一层打 egg 并部署
scrapyd-deploy local -p demo
# 触发一次抓取，返回 jobid
curl -s http://127.0.0.1:6800/schedule.json \
  -d project=demo -d spider=books
# 按 jobid 查看或取消
curl -s "http://127.0.0.1:6800/listjobs.json?project=demo"
curl -s http://127.0.0.1:6800/cancel.json \
  -d project=demo -d job=此处填返回的jobid
```

定时交给系统 `cron` 即可，任务本身仍由 Scrapyd 记录，日志追加到文件便于事后排查。

```bash
# 每天 02:15 调度一次，输出与错误都追加到日志
15 2 * * * curl -s http://127.0.0.1:6800/schedule.json -d project=demo -d spider=books >> /var/log/demo-crawl.log 2>&1
```

**Scrapyd 常用调度端点**

| 端点 | 方法 | 作用 |
| --- | --- | --- |
| `/schedule.json` | POST | 启动一次抓取，返回 `jobid` |
| `/cancel.json` | POST | 按 `jobid` 取消运行中的任务 |
| `/listjobs.json` | GET | 列出 pending、running、finished 任务 |
| `/listprojects.json` | GET | 已部署的项目列表 |
| `/delversion.json` | POST | 删除某个项目版本 |
| `/logs/` | GET | 按项目、爬虫、`jobid` 查日志 |

把 `scrapyd` 只绑在 `127.0.0.1`、由反向代理或内网访问，别把 `6800` 端口直接暴露到公网；部署凭据与调度接口都要加访问控制，否则等于把一台能随时发起外连的机器公开出去。

## 去重、增量采集、日志与失败隔离

默认去重由 `RFPDupeFilter` 完成，它把 `request_fingerprint` 存进内存集合，进程一退出就清空。要断点续爬，用 `JOBDIR` 把队列与指纹持久化到目录；要跨天增量，则把已抓指纹或业务主键落库，下次启动先加载再跳过。失败不该扩散：给单个请求挂 `errback`，异常只记日志，其余请求照常进行。

```python
import scrapy
from scrapy.utils.request import request_fingerprint

class DeltaSpider(scrapy.Spider):
    name = 'delta'
    start_urls = ['https://books.example.org/latest']

    def __init__(self, seen=None, **kwargs):
        super().__init__(**kwargs)
        self.seen = set(seen or [])       # 上次已抓的指纹，来自外部存储

    custom_settings = {
        'LOG_LEVEL': 'INFO',
        'LOG_FILE': 'delta.log',
        'DOWNLOAD_TIMEOUT': 15,
        'RETRY_TIMES': 2,
    }

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                callback=self.parse,
                errback=self.on_error,
                dont_filter=True,
            )

    def parse(self, response):
        for card in response.css('article.book'):
            url = response.urljoin(card.css('a::attr(href)').get())
            fp = request_fingerprint(scrapy.Request(url))
            if fp in self.seen:
                continue
            self.seen.add(fp)
            yield {'url': url, 'status': response.status}

    def on_error(self, failure):
        # 单个请求失败只记日志，不影响其它请求
        self.logger.error('request failed: %s', failure.value)
```

续跑命令把状态目录挂上即可，重启后 `Scheduler` 会接着未完成的队列走。

```bash
scrapy crawl delta -s JOBDIR=crawls/delta-1
```

日志用 `LOG_LEVEL` 与 `LOG_FILE` 分级落盘，`failure.value` 里带着具体异常。还可以用 `CLOSESPIDER_ERRORCOUNT` 在错误数达到阈值时熔断，`CLOSESPIDER_ITEMCOUNT` 限制单次产出量，避免一次误配把目标站点刷上一整夜。增量比对除了指纹，也能用响应头的 `Last-Modified` 与 `ETag`，让 `304` 直接跳过未变更的页面。

## 常见坑 / 边界与合规

**关掉 `ROBOTSTXT_OBEY` 图快，上线就被封。** 本地能抓、换到固定 IP 的服务器立刻 `403`，多半是因为默认模板没替你打开这个开关。修复动作：把 `ROBOTSTXT_OBEY` 设为 `True`，在 Spider 里据 `robots.txt` 过滤禁止路径，需要更广范围时先向站点申请授权或改走官方接口。

**把并发拉满，换来一片 `429`。** `CONCURRENT_REQUESTS` 调到大几十、又不设域名级限制，最容易触发对方限流。修复动作：`CONCURRENT_REQUESTS_PER_DOMAIN` 压到 2、`DOWNLOAD_DELAY` 至少 1 秒、开启 `AUTOTHROTTLE`，遇到 `429` 退避或停止，不靠更换出口地址继续抓。

**Pipeline 不幂等，重跑写出一堆重复行。** 表上没唯一键、也没在 `process_item` 里 `return item`。修复动作：给 `url` 加唯一约束并用 `INSERT OR IGNORE`，或先查指纹再写；清洗组件务必 `return item`，丢弃时用 `DropItem` 而不是静默返回 `None`。

**登录失效或 Ajax 被拦，被当成空数据。** 拦截页状态码未必是 `200`，直接 `json.loads` 会抛异常。修复动作：解析前判 `response.status`，登录走 `FormRequest.from_response` 带隐藏字段并全程保持 `cookiejar`，凭据从环境变量读取、只使用自己合法的账号。

**一看验证码或字体加密就想着破解。** 这是越界信号，不是技术难题。修复动作：停下该字段，改用官方开放接口、申请数据授权或放弃采集；不接打码平台、不逆向字体映射、不用代理池规避封禁。

合规底线单独说清楚：只做合规范围内的采集——公开可访问、站点规则允许、有合法使用依据的数据；尊重 `robots.txt`、服务条款与 `429` 等限流响应；不批量留存个人信息与受版权保护的内容；识别到防护就退让而非对抗。技术能力不等于授权，本专题不提供任何绕过防护的具体攻击手法，也不鼓励把采集压力转嫁给他人站点。

## 练习

::: details 练习 1 · 给 Spider 加限速并用一个 Pipeline 清洗价格
把 `BookSpider` 改成遵守 `robots.txt`、单域名并发为 2、间隔 1 秒，并写一个 `PricePipeline` 把价格字符串转成 `float`、缺失时置 `0.0`。写出 `custom_settings` 与 `process_item`。

```python
# 参考解
import scrapy
from itemadapter import ItemAdapter

class BookSpider(scrapy.Spider):
    name = 'books_ex'
    start_urls = ['https://books.example.org/latest']
    custom_settings = {
        'ROBOTSTXT_OBEY': True,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DOWNLOAD_DELAY': 1.0,
        'ITEM_PIPELINES': {'demo.pipelines.PricePipeline': 300},
    }

    def parse(self, response):
        for card in response.css('article.book'):
            yield {
                'title': card.css('h2::text').get(default='').strip(),
                'price': card.css('span.price::text').re_first(r'[\d.]+'),
            }

class PricePipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        raw = adapter.get('price')
        adapter['price'] = float(raw) if raw else 0.0
        return item
```
:::

::: details 练习 2 · 用 errback 隔离失败并统计成功数
给一批 URL 发请求，失败的请求走 `errback` 只记 `WARNING` 日志、不中断其它请求，成功的请求解析标题；统计成功与失败数量并在 `closed` 里打印。

```python
# 参考解
import scrapy
import logging

class RobustSpider(scrapy.Spider):
    name = 'robust'
    start_urls = [
        'https://books.example.org/ok',
        'https://books.example.org/maybe-404',
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ok = 0
        self.fail = 0

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse,
                                 errback=self.on_error, dont_filter=True)

    def parse(self, response):
        self.ok += 1
        yield {'url': response.url,
               'title': response.css('title::text').get(default='')}

    def on_error(self, failure):
        self.fail += 1
        self.logger.warning('failed: %s %s',
                            failure.request.url, failure.value)

    def closed(self, reason):
        logging.info('done ok=%d fail=%d reason=%s',
                     self.ok, self.fail, reason)
```
:::

回到 [专题补遗](/topics/) · [课程总目录](/guide/curriculum)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能跑通本专题按正文顺序整理的标准库示例；需要第三方库的片段会自动跳过并打印安装提示，不装任何库也能看到核心结果。" />

**本专题示例代码** · 仓内路径 `examples/topics/scrapy-antibot.py`

```bash
python3 examples/topics/scrapy-antibot.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/topics/scrapy-antibot.py) · [全部示例代码索引](/examples/)
