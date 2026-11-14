"""Scrapy 与反爬合规：从 Spider 到生产采集 —— 专题补遗可运行示例。

课程页：/topics/scrapy-antibot
GitHub：https://github.com/lfire/python/blob/main/examples/topics/scrapy-antibot.py
依赖安装（可选，第三方段缺库时会自动跳过）：
    python3 -m pip install scrapy itemadapter
    # 部署相关再按需追加
    python3 -m pip install scrapyd scrapyd-client
运行命令：
    python3 examples/topics/scrapy-antibot.py
说明：本文件按 tools/course/topics/scrapy-antibot.md 中 python 代码块的出现顺序整理。
纯标准库段（选择器解析、URL 去重与规范化、限速令牌桶、Cookie/请求头、
配置字典、sqlite 幂等落库）在纯净环境直接跑出结果；依赖 scrapy / itemadapter
的可选段用 try/except ImportError 包住，缺库时打印跳过提示，全程不启动服务、
不监听端口、不访问外网。写文件片段一律写入 tempfile.TemporaryDirectory() 自动清理。
"""

import hashlib
import os
import random
import re
import sqlite3
import tempfile
import time
from html.parser import HTMLParser
from http.cookies import SimpleCookie
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

print('=== Scrapy 与反爬合规：从 Spider 到生产采集 ===')


# ===== 01 · 源文节 Spider、start_requests 与选择器 · 代码块 1 BookSpider（可选 scrapy） =====
def demo_01_book_spider():
    try:
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
                        'price': card.css('span.price::text').re_first(r'[0-9.]+'),
                        'url': response.urljoin(card.css('a::attr(href)').get()),
                    }
                next_page = response.css('a.next::attr(href)').get()
                if next_page:
                    yield response.follow(next_page, callback=self.parse)

        print('  代码块 1 BookSpider 定义完成（依赖 scrapy）')
    except ImportError:
        print("跳过：需要 pip install scrapy")


demo_01_book_spider()


# ===== 02 · 源文节 CSS 与 XPath 常用对照 / BookSpider.parse · 标准库 选择器解析逻辑 =====
def demo_02_selector_stdlib():
    # 对应正文的 css('article.book')、get()、re_first、urljoin：用标准库等价演示
    class CardParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.cards = []
            self._card = None
            self._capture = None

        def handle_starttag(self, tag, attrs):
            attr = dict(attrs)
            classes = attr.get('class', '').split()
            if tag == 'article' and 'book' in classes:
                self._card = {'title': '', 'price': '', 'url': ''}
            elif self._card is not None:
                if tag == 'h2':
                    self._capture = 'title'
                elif tag == 'span' and 'price' in classes:
                    self._capture = 'price'
                elif tag == 'a':
                    self._capture = None
                    self._card['url'] = attr.get('href', '')

        def handle_data(self, data):
            if self._card is not None and self._capture:
                self._card[self._capture] += data

        def handle_endtag(self, tag):
            if tag in ('h2', 'span'):
                self._capture = None
            elif tag == 'article' and self._card is not None:
                self.cards.append(self._card)
                self._card = None

    html_text = (
        '<article class="book"><h2>Python 入门</h2>'
        '<span class="price">59.00 元</span><a href="/p/1">详情</a></article>'
        '<article class="book"><h2>Flask 实操</h2>'
        '<span class="price">79.50 元</span><a href="p/2">详情</a></article>'
    )
    parser = CardParser()
    parser.feed(html_text)
    base = 'https://books.example.org/latest'
    for card in parser.cards:
        m = re.findall(r'[0-9.]+', card['price'])
        price = m[0] if m else ''
        print('  选择器 get(h2::text) =', card['title'].strip())
        print('  选择器 re_first(price) =', price)
        print('  选择器 urljoin(a::attr(href)) =', urljoin(base, card['url']))


demo_02_selector_stdlib()


# ===== 03 · 源文节 Item 定义与 Pipeline 落库 · 代码块 2 items.py BookItem（可选 scrapy） =====
def demo_03_item():
    try:
        import scrapy

        class BookItem(scrapy.Item):
            title = scrapy.Field()
            price = scrapy.Field()
            url = scrapy.Field()
            source = scrapy.Field()

        print('  代码块 2 BookItem 定义完成（依赖 scrapy）')
    except ImportError:
        print("跳过：需要 pip install scrapy")


demo_03_item()


# ===== 04 · 源文节 Item 定义与 Pipeline 落库 · 代码块 3 pipelines.py（可选 itemadapter） =====
def demo_04_pipelines():
    try:
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

        print('  代码块 3 PricePipeline / SqlitePipeline 定义完成（依赖 itemadapter）')
    except ImportError:
        print("跳过：需要 pip install scrapy itemadapter")


demo_04_pipelines()


# ===== 05 · 源文节 Item 定义与 Pipeline 落库 · 标准库 sqlite 幂等落库 + tempfile 写文件 =====
def demo_05_sqlite_stdlib():
    # 对应 PricePipeline 的清洗与 SqlitePipeline 的 INSERT OR IGNORE 幂等写库
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, 'books.db')
        conn = sqlite3.connect(db_path)
        conn.execute(
            'CREATE TABLE IF NOT EXISTS books '
            '(title TEXT, price REAL, url TEXT UNIQUE, source TEXT)'
        )
        items = [
            {'title': 'Python 入门', 'price': '59.00', 'url': '/p/1', 'source': 'books'},
            {'title': 'Flask 实操', 'price': '', 'url': '/p/2', 'source': 'books'},
            {'title': 'Python 入门', 'price': '59.00', 'url': '/p/1', 'source': 'books'},
        ]
        for item in items:
            price = float(item['price']) if item['price'] else 0.0
            conn.execute(
                'INSERT OR IGNORE INTO books VALUES (?, ?, ?, ?)',
                (item['title'], price, item['url'], item['source']),
            )
        conn.commit()
        rows = conn.execute('SELECT title, price, url FROM books ORDER BY url').fetchall()
        conn.close()
        print('  Pipeline 标准库等价（tempfile 自动清理）写入 3 条，幂等后剩', len(rows), '条')
        for row in rows:
            print('    ', row)


demo_05_sqlite_stdlib()


# ===== 06 · 源文节 Item 定义与 Pipeline 落库 · 代码块 4 settings.py ITEM_PIPELINES（标准库直接跑） =====
def demo_06_pipeline_settings():
    ITEM_PIPELINES = {
        'demo.pipelines.PricePipeline': 300,
        'demo.pipelines.SqlitePipeline': 800,
    }
    order = sorted(ITEM_PIPELINES.items(), key=lambda kv: kv[1])
    print('  代码块 4 ITEM_PIPELINES（数值越小越先执行）=', order)


demo_06_pipeline_settings()


# ===== 07 · 源文节 下载器中间件、重试与请求指纹 · 代码块 5 middlewares.py（可选 scrapy） =====
def demo_07_middleware():
    try:
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

        print('  代码块 5 RotateUserAgentMiddleware 定义完成（依赖 scrapy）')
    except ImportError:
        print("跳过：需要 pip install scrapy")


demo_07_middleware()


# ===== 08 · 源文节 登录态 Cookie、Ajax 接口与请求头 · 标准库 Cookie/请求头与 UA 轮换 =====
def demo_08_cookie_headers_stdlib():
    ua_pool = ['Mozilla/5.0 (demo-a)', 'Mozilla/5.0 (demo-b)']
    headers = {'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
    headers['User-Agent'] = random.choice(ua_pool)
    cookie = SimpleCookie()
    cookie['sessionid'] = 'abc123'
    cookie['sessionid']['httponly'] = True
    cookie['sessionid']['path'] = '/'
    print('  请求头 User-Agent（UA 轮换）=', headers['User-Agent'])
    print('  请求头 Accept =', headers['Accept'])
    print('  Cookie set_cookie(httponly) =', cookie.output().strip())


demo_08_cookie_headers_stdlib()


# ===== 09 · 源文节 限速、并发与 robots.txt 开关 · 代码块 6 settings.py 限速默认值（标准库直接跑） =====
def demo_09_throttle_settings():
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
    print('  代码块 6 限速默认值 ROBOTSTXT_OBEY =', ROBOTSTXT_OBEY)
    print('  并发 全局/单域名 =', CONCURRENT_REQUESTS, '/', CONCURRENT_REQUESTS_PER_DOMAIN)
    print('  间隔 DOWNLOAD_DELAY =', DOWNLOAD_DELAY, ' AUTOTHROTTLE =', AUTOTHROTTLE_ENABLED)
    print('  重试 RETRY_TIMES =', RETRY_TIMES, ' RETRY_HTTP_CODES =', RETRY_HTTP_CODES)
    print('  错误码映射（429 放进退避依据）=', {c: '重试' for c in RETRY_HTTP_CODES})


demo_09_throttle_settings()


# ===== 10 · 源文节 限速、并发与 robots.txt 开关 · 标准库 限速令牌桶 =====
def demo_10_token_bucket():
    # 对应正文 DOWNLOAD_DELAY / AUTOTHROTTLE 的间隔控制，用标准库演示放行判断
    class TokenBucket:
        def __init__(self, rate, capacity):
            self.rate = rate
            self.capacity = capacity
            self.tokens = float(capacity)
            self.last = time.monotonic()

        def allow(self):
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

    bucket = TokenBucket(rate=2.0, capacity=2)
    result = ['放行' if bucket.allow() else '等待' for _ in range(5)]
    print('  限速令牌桶（rate=2 capacity=2）连续 5 次请求 =', result)


demo_10_token_bucket()


# ===== 11 · 源文节 登录态 Cookie、Ajax 接口与请求头 · 代码块 7 AccountSpider（可选 scrapy） =====
def demo_11_account_spider():
    try:
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

        print('  代码块 7 AccountSpider 定义完成（依赖 scrapy）')
    except ImportError:
        print("跳过：需要 pip install scrapy")


demo_11_account_spider()


# ===== 12 · 源文节 去重、增量采集、日志与失败隔离 · 代码块 8 DeltaSpider（可选 scrapy） =====
def demo_12_delta_spider():
    try:
        import scrapy
        from scrapy.utils.request import request_fingerprint

        class DeltaSpider(scrapy.Spider):
            name = 'delta'
            start_urls = ['https://books.example.org/latest']

            def __init__(self, seen=None, **kwargs):
                super().__init__(**kwargs)
                self.seen = set(seen or [])

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
                self.logger.error('request failed: %s', failure.value)

        print('  代码块 8 DeltaSpider 定义完成（依赖 scrapy）')
    except ImportError:
        print("跳过：需要 pip install scrapy")


demo_12_delta_spider()


# ===== 13 · 源文节 去重、增量采集、日志与失败隔离 · 标准库 URL 去重与规范化 =====
def demo_13_url_dedup_stdlib():
    # 对应 request_fingerprint / RFPDupeFilter / urljoin：规范化后按指纹去重
    def normalize(url):
        parts = urlparse(url)
        query = urlencode(sorted(parse_qsl(parts.query)))
        return urlunparse((parts.scheme.lower(), parts.netloc.lower(),
                           parts.path, parts.params, query, ''))

    def fingerprint(url):
        return hashlib.sha256(normalize(url).encode('utf-8')).hexdigest()[:12]

    seen = set()
    urls = [
        'https://Books.Example.org/a?b=2&a=1#top',
        'https://books.example.org/a?a=1&b=2',
        'https://books.example.org/b',
        'https://books.example.org/a?a=1&b=2',
    ]
    for url in urls:
        fp = fingerprint(url)
        if fp in seen:
            print('  去重：重复指纹', fp, '跳过', url)
        else:
            seen.add(fp)
            print('  规范化并登记指纹', fp, '->', normalize(url))


demo_13_url_dedup_stdlib()


# ===== 14 · 源文节 练习 1 · 代码块 9 参考解（可选 scrapy itemadapter） =====
def demo_14_exercise1():
    try:
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
                        'price': card.css('span.price::text').re_first(r'[0-9.]+'),
                    }

        class PricePipeline:
            def process_item(self, item, spider):
                adapter = ItemAdapter(item)
                raw = adapter.get('price')
                adapter['price'] = float(raw) if raw else 0.0
                return item

        print('  代码块 9 练习 1 参考解 定义完成（依赖 scrapy itemadapter）')
    except ImportError:
        print("跳过：需要 pip install scrapy itemadapter")


demo_14_exercise1()


# ===== 15 · 源文节 练习 2 · 代码块 10 参考解（可选 scrapy） =====
def demo_15_exercise2():
    try:
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

        print('  代码块 10 练习 2 参考解 定义完成（依赖 scrapy）')
    except ImportError:
        print("跳过：需要 pip install scrapy")


demo_15_exercise2()


print('=== 全部段落执行完毕 ===')
