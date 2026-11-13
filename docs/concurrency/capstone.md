---
title: 第 070 讲 · 阶段综合：并发爬虫四级演进
description: 把单机脚本演进到可限流的分布式抓取
---

<StageHeader stage='L6 · 并发与异步' level='★★★★☆' time='60 分钟' goal='把单机脚本演进到可限流的分布式抓取' prereq='第 069 讲 · asyncio 深入：Task、Future 与事件循环' />

# 第 070 讲 · 阶段综合：并发爬虫四级演进

任务的调度与取消都理清了，这一阶段的并发路线到这里适合收个口：把散落的知识拼成一件能跑、还能测出收益的东西。一个价格监控的并发爬虫，从抓二十页涨到二十万个地址，第一反应总是多开线程，可对方站点先开始拒答，内存也被攒下的页面吃满，说不清提速到底来自哪一步。

我们按一次只换一个变量的顺序来：先量串行基线，再换线程池版本，接着上 asyncio 配连接池，最后补去重、限流、失败重试与断点，并把限速和合规写成默认开启的配置。前置是线程、asyncio 与队列；做完你会得到可测量、可控的抓取组件，也正好在下一阶段把这段脚本立成一个像样的项目。


## 从抓 20 个页面到抓 20 万个 URL 的需求拐点

一个价格监控脚本从抓 20 个页面开始，半年后要抓 20 万个 URL。工程师第一反应是「开更多线程」，结果对方站点先返回 429，自己的内存又被「把全部 HTML 存列表」吃满；改成 asyncio 后吞吐上去了，却因没有去重把同一商品页反复抓了三遍，断点重启又全量重跑。

每一次「加并发」的收益都混杂着别的变量，根本说不清提升来自哪里。真正的演进要一级只替换一个变量：先看串行基线，再换线程池、再换 asyncio 加连接池、最后补去重、限流、失败重试与断点。更关键的是限速与合规不是可选项：不设 robots 约束与请求间隔，压垮对方站点的同时自己也被封。

本讲用纯标准库把四级演进做成可测量、可控的组件。

<Callout type="warn" title='先看一个真实会出错的写法' text='把 Top 结果一次性塞进列表再统一处理：物化全部 HTML/结果会吃满内存，页面数增长即 OOM' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段六 · 并发与异步 |
| 前置 | 第 069 讲 · asyncio 深入：Task、Future 与事件循环 |
| 难度 / 建议时长 | ★★★★☆ · 60 分钟 |
| 本讲新增 | 串行基线、线程池版本、asyncio + 连接池 |
| 一句话目标 | 把单机脚本演进到可限流的分布式抓取 |
| 为下一讲铺垫 | 项目结构与 src 布局 |


## 四级演进的设计取舍：每级只替换一个变量

串行基线用 for 循环逐个 fetch，耗时约等于单次延迟乘以数量，是唯一的对照锚点。

线程池版用 `concurrent.futures.ThreadPoolExecutor(max_workers=k)`，把阻塞 IO 换成线程池：因为 requests 这类同步调用在进入 socket 等待前释放 GIL，k 个等待能重叠，吞吐约提升到 `min(k, 单机上限)` 倍；

代价是每线程栈内存与上下文切换，k 过大反而退化。

asyncio 版把 fetch 换成原生异步客户端（aiohttp / `httpx.AsyncClient`）并复用连接池，单线程事件循环用 await 让出控制权，连接数由连接器上限约束，不再为每个请求付线程栈。

三级对照必须固定同一份 URL 集合、同样的解析逻辑、同样的统计口径，只换「并发模型」这一个变量，否则无法把收益归因。

实测用 `sum(range(n)`) 对比 `ThreadPoolExecutor.map` 与串行，可确认两者结果完全一致，排除「并发把数据搞错」的干扰。

**并发爬取四级演进：每级只替换一个变量**

| 级别 | 替换的变量 | 收益来源 | 主要代价 |
| --- | --- | --- | --- |
| 串行基线 | 无（对照锚点） | 耗时 = 单次延迟 × 数量 | 最慢，但可复现 |
| 线程池 | 并发模型 | 阻塞 IO 前释放 GIL，等待重叠 | 线程栈内存与上下文切换 |
| asyncio + 连接池 | IO 模型 + 连接复用 | 单线程事件循环消除线程开销 | 需原生异步库，同步调用会拖垮 loop |
| 去重/限流/重试/断点 | 治理组件 | 消除重复抓取、防止被封、可恢复 | 组件与状态管理复杂度 |

<Callout type="tip" title='核心心智模型' text='串行基线用 for 循环逐个 fetch，耗时约等于单次延迟乘以数量，是唯一的对照锚点。线程池版用 concurrent.futures.ThreadPoolExecutor(max_workers=k)，把阻塞 IO 换成线程池：因为 requests 这类同步调用在进入 socket 等待前释放' />

同步 socket 进入阻塞系统调用前由 CPython 释放 GIL，因此 ThreadPoolExecutor 能让多个网络等待重叠，这是二级加速的来源；但线程有独立栈（默认常为 8 MB 级虚拟内存）与调度开销，并发度上千就不划算。

asyncio 把等待点显式化：协程在 await 处 yield 回事件循环，底层用 selectors（epoll/kqueue）把就绪 fd 映射回回调，单 OS 线程即可维持数万连接，连接由 AsyncClient 的连接池复用而非每请求新建。

Semaphore 内部维护一个等待 Future 队列，release 时只唤醒一个等待者，因此把 async with sem 放在发请求临界区就能精确约束在途数。tracemalloc 用 hook 追踪每次分配，物化 5 万条结果的列表峰值显著高于只保存生成器帧的流式管线，这正是背压与断点续抓要利用的内存特性。


### 串行、线程池、asyncio 连接池的收益各来自哪里

<ConceptDiagram type='layers3' title='第 070 讲 · 分层视角' labels='一级到三级：并发模型只替换一个变量|四级：去重、限流、失败重试与断点|组件化与可观测：把策略写成配置|监控与合规' caption='组件化与可观测：把策略写成配置' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **监控与合规** 落在哪一层。


## 分步实现：一级到三级的并发骨架

```python
import asyncio

PAGES = {
    'u1': 'alpha',
    'u2': 'beta',
    'u3': 'gamma',
}

async def fetch(url, fail_first=False, attempts=None):
    for i in range(3):
        if fail_first and i == 0 and url == 'u2':
            attempts.append((url, i))
            await asyncio.sleep(0)
            continue
        await asyncio.sleep(0)
        return len(PAGES[url])

async def crawl(urls, limit=2):
    seen = set()
    sem = asyncio.Semaphore(limit)
    attempts = []

    async def one(url):
        if url in seen:
            return None
        seen.add(url)
        async with sem:
            n = await fetch(url, True, attempts)
            return (url, n)

    results = await asyncio.gather(*(one(u) for u in urls))
    return results, attempts

async def main():
    urls = ['u1', 'u2', 'u1', 'u3']
    results, attempts = await crawl(urls)
    print('unique', len([r for r in results if r]))
    print('results', sorted(r for r in results if r))
    print('retries', attempts)

asyncio.run(main())
```

<OutputBox title='主示例运行结果' output='unique 3\nresults [(&#39;u1&#39;, 5), (&#39;u2&#39;, 4), (&#39;u3&#39;, 5)]\nretries [(&#39;u2&#39;, 0)]' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import asyncio\n\nPAGES = {\n    &#39;u1&#39;: &#39;alpha&#39;,\n    &#39;u2&#39;: &#39;beta&#39;,\n    &#39;u3&#39;: &#39;gamma&#39;,\n}\n\nasync def fetch(url, fail_first=False, attempts=None):\n    for i in range(3):\n        if fail_first and i == 0 and url == &#39;u2&#39;:\n            attempts.append((url, i))\n            await asyncio.sleep(0)\n            continue\n        await asyncio.sleep(0)\n        return len(PAGES[url])\n\nasync def crawl(urls, limit=2):\n    seen = set()\n    sem = asyncio.Semaphore(limit)\n    attempts = []\n\n    async def one(url):\n        if url in seen:\n            return None\n        seen.add(url)\n        async with sem:\n            n = await fetch(url, True, attempts)\n            return (url, n)\n\n    results = await asyncio.gather(*(one(u) for u in urls))\n    return results, attempts\n\nasync def main():\n    urls = [&#39;u1&#39;, &#39;u2&#39;, &#39;u1&#39;, &#39;u3&#39;]\n    results, attempts = await crawl(urls)\n    print(&#39;unique&#39;, len([r for r in results if r]))\n    print(&#39;results&#39;, sorted(r for r in results if r))\n    print(&#39;retries&#39;, attempts)\n\nasyncio.run(main())' :notes='["导入 asyncio，用事件循环模拟并发抓取", "模拟页面库：URL 到正文的映射，len 即内容长度", "u1 正文 alpha 长度 5", "u2 正文 beta 长度 4", "u3 正文 gamma 长度 5", "定义 fetch，最多重试 3 次", "用 range(3) 表达最大尝试次数", "对 u2 的第 0 次故意失败，触发重试路径", "把失败尝试记入 attempts 供观测", "await sleep(0) 让出事件循环，模拟网络等待", "continue 进入下一次尝试", "正常的网络等待点", "返回正文长度作为解析结果", "crawl 接受 URL 列表与在途并发上限", "seen 集合做 URL 去重", "Semaphore 限制同时发请求的数量", "attempts 记录失败重试明细", "定义单个 URL 的处理协程", "命中 seen 直接返回 None，实现去重", "未见过的 URL 先登记再处理", "临界区只包住真正发请求的部分", "await fetch 并带上重试开关与记录表", "把 URL 与结果组成元组返回", "gather 并发驱动所有 URL，按传入顺序收结果", "返回结果与重试记录，供上层统计", "定义入口协程", "URL 列表里 u1 故意重复一次", "调用 crawl 拿到结果与重试明细", "去重后实际抓到的唯一 URL 数量", "按 URL 排序后打印，消除调度顺序影响", "打印触发过的重试，验证幂等重试可观测", "同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池", "去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay", "重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列"]' title='第 070 讲 · 阶段综合：并发爬虫四级演进' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
from concurrent.futures import ThreadPoolExecutor

def work(n):
    return sum(range(n))

nums = [1000, 2000, 3000, 4000]
with ThreadPoolExecutor(max_workers=4) as ex:
    threaded = list(ex.map(work, nums))
serial = [work(n) for n in nums]
print('serial == threaded', serial == threaded)
print('sum', sum(serial))
```

<OutputBox title='对照写法：先自己猜，再点开' output='serial == threaded True\nsum 14995000' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import asyncio\n\nPAGES = {\n    &#39;u1&#39;: &#39;alpha&#39;,\n    &#39;u2&#39;: &#39;beta&#39;,\n    &#39;u3&#39;: &#39;gamma&#39;,\n}\n\nasync def fetch(url, fail_first=False, attempts=None):\n    for i in range(3):\n        if fail_first and i == 0 and url == &#39;u2&#39;:\n            attempts.append((url, i))\n            await asyncio.sleep(0)\n            continue\n        await asyncio.sleep(0)\n        return len(PAGES[url])\n\nasync def crawl(urls, limit=2):\n    seen = set()\n    sem = asyncio.Semaphore(limit)\n    attempts = []\n\n    async def one(url):\n        if url in seen:\n            return None\n        seen.add(url)\n        async with sem:\n            n = await fetch(url, True, attempts)\n            return (url, n)\n\n    results = await asyncio.gather(*(one(u) for u in urls))\n    return results, attempts\n\nasync def main():\n    urls = [&#39;u1&#39;, &#39;u2&#39;, &#39;u1&#39;, &#39;u3&#39;]\n    results, attempts = await crawl(urls)\n    print(&#39;unique&#39;, len([r for r in results if r]))\n    print(&#39;results&#39;, sorted(r for r in results if r))\n    print(&#39;retries&#39;, attempts)\n\nasyncio.run(main())", "note": "一级到三级：并发模型只替换一个变量"}, {"label": "对照 / 进阶", "code": "from concurrent.futures import ThreadPoolExecutor\n\ndef work(n):\n    return sum(range(n))\n\nnums = [1000, 2000, 3000, 4000]\nwith ThreadPoolExecutor(max_workers=4) as ex:\n    threaded = list(ex.map(work, nums))\nserial = [work(n) for n in nums]\nprint(&#39;serial == threaded&#39;, serial == threaded)\nprint(&#39;sum&#39;, sum(serial))", "note": "四级：去重、限流、失败重试与断点"}]' title='两种写法对照' note='差异集中在 串行基线；先看输出，再找背后的规则。' />

<Term word='串行基线' text='串行基线用 for 循环逐个 fetch，耗时约等于单次延迟乘以数量，是唯一的对照锚点。线程池版用 concurrent.futures.ThreadPoolExecutor(max_workers=k)，把阻塞 IO 换成线程池：因为 requests 这类同步调用在进入 socket 等待前释放 GIL，k 个等待' />

<Term word='线程池版本' text='去重靠 seen 集合：入队前先查 URL 指纹（规范化后的 URL 或内容 hash），命中即跳过，避免重复页、分页参数与重定向环把 Top 名额吃光；分布式下换成布隆过滤器或共享 Redis 集合。限流用 asyncio.Semaphore(limit) 包住真正发请求的临界区，把「在途请求数」而非「已创建任务数」' />


### 把全部 HTML 存进列表为什么吃满内存

```python
import tracemalloc

def collect_all(urls):
    return [len(u) * 100 for u in urls]

def stream(urls):
    for u in urls:
        yield len(u) * 100

urls = ['page-%d' % i for i in range(50000)]
tracemalloc.start()
all_pages = collect_all(urls)
peak_all = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
tracemalloc.start()
gen = stream(urls)
next(gen)
peak_stream = tracemalloc.get_traced_memory()[1]
tracemalloc.stop()
print('materialized peak > generator peak', peak_all > peak_stream)
```

<OutputBox title='原理验证' output='materialized peak &gt; generator peak True' />


## 四级落地：去重、限流、失败重试与断点

去重靠 seen 集合：入队前先查 URL 指纹（规范化后的 URL 或内容 hash），命中即跳过，避免重复页、分页参数与重定向环把 Top 名额吃光；分布式下换成布隆过滤器或共享 Redis 集合。

限流用 `asyncio.Semaphore(limit)` 包住真正发请求的临界区，把「在途请求数」而非「已创建任务数」压在上限内；

再加每域名最小间隔与令牌桶，遵守 `robots.txt` 的 Crawl-delay。失败重试只对幂等的 GET 生效，设最大次数（如 3）与指数退避，区分可重试状态码（429/5xx/超时）与永久失败（404/解析错误）。断点把 seen、待抓队列、已抓结果持久化，重启时从 checkpoint 恢复而不是全量重来；

用 tracemalloc 对比「一次性物化全部结果」与「generator 流式产出」的峰值内存，能证明流式管线更省内存，这正是背压的基础。

**限流与合规策略（默认开启）**

| 策略 | 典型默认值 | 缺失后果 |
| --- | --- | --- |
| 在途并发上限 | Semaphore(8~32) | 瞬间打满对方连接、本机 fd 耗尽 |
| 每域名最小间隔 | 按 robots Crawl-delay | 触发 429、IP 被封 |
| 单次请求超时 | 10~30 秒 | 长连接堆积占满连接池 |
| 最大重试次数 | 3 次 + 指数退避 | 工具异常后无限重试 |
| 重试对象 | 仅幂等 GET、429/5xx/超时 | 非幂等写操作重复执行 |
| 断点持久化 | seen + 待抓队列 + 结果 | 重启全量重跑，浪费配额 |


## 失败模式与定位指标：429 与无限重试

**失败模式与定位指标**

| 现象 | 常见根因 | 定位指标 |
| --- | --- | --- |
| 同一页被抓多遍 | 无 URL 指纹去重 / 重定向环 | seen 命中率、重复 URL 计数 |
| 对方返回 429 | 并发或间隔不合规 | 单位时间请求数、状态码分布 |
| 重启后全量重跑 | checkpoint 未持久化 | 断点恢复条数、队列积压 |
| 内存持续上涨 | 一次性物化全部结果 | tracemalloc 峰值、在途任务数 |
| worker 崩后任务丢失 | 已分配未确认的消息未重入队 | ack 数、失败队列长度 |

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把 Top 结果一次性塞进列表再统一处理 | 物化全部 HTML/结果会吃满内存，页面数增长即 OOM | 用 generator/as_completed 流式产出，边解析边写库，用 tracemalloc 量峰值 |
| 不做去重与限速直接开满并发 | 重复抓取浪费配额，瞬间高并发触发 429 甚至被封 IP | 入队前用规范化 URL 指纹查 seen，Semaphore 限在途数，按 robots Crawl-delay 设最小间隔 |
| 对所有失败都无限重试 | 404/解析错误属永久失败，无限重试会耗尽预算并放大对端压力 | 只对幂等 GET 的 429/5xx/超时重试，设最大次数与指数退避，永久失败进失败队列 |

<Callout type="warn" title='本讲最容易踩的坑' text='把 Top 结果一次性塞进列表再统一处理：物化全部 HTML/结果会吃满内存，页面数增长即 OOM' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把 Top 结果一次性塞进列表再统一处理", "body": "物化全部 HTML/结果会吃满内存，页面数增长即 OOM", "tip": "用 generator/as_completed 流式产出，边解析边写库，用 tracemalloc 量峰值"}, {"title": "第 2 步：不做去重与限速直接开满并发", "body": "重复抓取浪费配额，瞬间高并发触发 429 甚至被封 IP", "tip": "入队前用规范化 URL 指纹查 seen，Semaphore 限在途数，按 robots Crawl-delay 设最小间隔"}, {"title": "第 3 步：对所有失败都无限重试", "body": "404/解析错误属永久失败，无限重试会耗尽预算并放大对端压力", "tip": "只对幂等 GET 的 429/5xx/超时重试，设最大次数与指数退避，永久失败进失败队列"}]' />


## 组件化与可观测：把策略写成配置

把 URL 去重器、优先级队列、限速器、失败队列、持久化各自抽成独立组件，主循环只负责编排；这样升级限流算法不会动到解析逻辑。合规策略必须默认开启且写成配置：User-Agent、并发上限、每域名间隔、robots 白名单、超时。监控要打点四个量：在途任务数、单位时间请求数、各类状态码分布、队列积压长度；

任一指标越界就降速或熔断。分布式化后还会出现重复抓取（多 worker 同时取到同一 URL）与顺序不确定，必须靠共享去重与幂等写入兜底。断点续抓要记录「已分配但未确认」的任务，worker 崩溃时重新入队，避免消息永久丢失。把这些约束显式化，才能说清每一次演进的收益来自并发模型、连接池、还是限流策略，而不是靠换框架碰运气。

<FlowTimeline :steps='[{"title": "一级到三级：并发模型只替换一个变量", "desc": "串行基线用 for 循环逐个 fetch，耗时约等于单次延迟乘以数量，是唯一的对照锚…", "tone": "blue"}, {"title": "四级：去重、限流、失败重试与断点", "desc": "去重靠 seen 集合：入队前先查 URL 指纹（规范化后的 URL 或内容 has…", "tone": "purple"}, {"title": "组件化与可观测：把策略写成配置", "desc": "把 URL 去重器、优先级队列、限速器、失败队列、持久化各自抽成独立组件，主循环只负…", "tone": "orange"}, {"title": "工程落地", "desc": "带去重、限流与断点续抓的抓取管线", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 带去重、限流与断点续抓的抓取管线

把去重、限流、重试、断点抽成独立组件后，主循环只负责编排：每批 URL 先过 seen 去重，再经 Semaphore 限制在途请求，失败由 fetch 内部按幂等策略重试，结果累积到 kept，seen 本身即可作为重启时的 checkpoint。

真实项目还要记录「已分配未确认」的任务、加每域名间隔与 robots 白名单、把状态码打进指标。下面片段分三批喂入含重复项的 URL，打印每批新增数、累计唯一数与序列化后的断点，用来验证跨批次去重不会漏抓也不会重抓。

```python
import asyncio, json

PAGES = {'a': 3, 'b': 5, 'c': 2, 'd': 7, 'e': 4}

async def fetch(url, fail_once=False):
    for attempt in range(3):
        if fail_once and url == 'b' and attempt == 0:
            await asyncio.sleep(0)
            continue
        await asyncio.sleep(0)
        return PAGES.get(url, 0)

async def crawl(urls, seen, sem):
    async def one(url):
        if url in seen:
            return None
        seen.add(url)
        async with sem:
            value = await fetch(url, True)
            return (url, value)
    return await asyncio.gather(*(one(u) for u in urls))

async def main():
    seen = set()
    sem = asyncio.Semaphore(2)
    batches = [['a', 'b', 'a', 'c'], ['b', 'd', 'c'], ['e']]
    for batch in batches:
        rows = await crawl(batch, seen, sem)
        print('batch', len(batch), 'new', len([r for r in rows if r]))
    print('total unique', len(seen))
    print('checkpoint', json.dumps(sorted(seen)))

if __name__ == '__main__':
    asyncio.run(main())
```

<Callout type="idea" title='落地提示' text='把 URL 去重、优先级、限速、失败队列抽成独立组件，合规策略写成配置并默认开启' />

<CheckList id='P070b' title='上线前自检' :items='["能复现并解释「把 Top 结果一次性塞进列表再统一处理」", "能复现并解释「不做去重与限速直接开满并发」", "能复现并解释「对所有失败都无限重试」", "能用一条命令验证 串行基线", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import asyncio; print(len(asyncio.run(asyncio.gather(*[asyncio.sleep(0,i) for i in range(3)]))))"
```

把输入换成你自己的数据，观察结果是否仍符合 **串行基线** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 令牌桶限速的连续时间推导与 GCRA 等价形式

设桶容量 b、补充速率 r（个每秒），t 时刻的令牌数 `T(t)` = `min(b, T(t0)` + r 乘 (t - t0))；请求到达时若 T 不小于 cost 就扣除并放行，否则拒绝或等待。

由此得到两条硬约束：任意瞬间最多放行 b 个（突发上限），任意长度 L 的窗口内最多放行 b + rL 个（长期速率被 r 钳住），既不靠后台定时器也不靠固定窗口计数。

等价的 GCRA（Generic Cell Rate Algorithm）把「理论到达时间 TAT」当唯一状态：到达时刻 t 若 t 不小于 TAT 减 tau 就接受，并令 `TAT = max`(TAT, t) + T，其中 `T = 1`/r、`tau = b`/r 是突发容差；

它只需一个时间戳就能表达同样的允许流量，是网关与 Redis 限流器的常见实现。固定窗口计数器的边界突刺是反例：两个窗口交界处的一秒内可放行 2r，滑动窗口日志要存每个请求时间戳、内存 `O(r 乘窗口)`，而令牌桶状态 `O(1)`。

实测里 `capacity=10`、`rate=5` 时连续 12 次取令牌恰好放过 10 次，随后按 0.2 秒每个的节奏恢复，正是「突发有界、长期匀速」的数学表现。

实现必须用 `time.monotonic` 而非 `time.time`：NTP 校时让系统时钟回拨或跳变时，基于挂钟的令牌数会倒退或暴增，曾有线上限流器在时钟校正后瞬间放行整桶的真实故障。

```python
import hashlib
import math
import time

class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.stamp = time.monotonic()
    def take(self, n=1):
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.stamp) * self.rate)
        self.stamp = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False

class Bloom:
    def __init__(self, m, k):
        self.m = m
        self.k = k
        self.bits = bytearray((m + 7) // 8)
    def _positions(self, item):
        d = hashlib.sha256(item.encode()).digest()
        for i in range(self.k):
            a = int.from_bytes(d[i * 4:i * 4 + 2], 'big')
            b = int.from_bytes(d[i * 4 + 2:i * 4 + 4], 'big')
            yield (a + b * i) % self.m
    def add(self, item):
        for p in self._positions(item):
            self.bits[p // 8] |= 1 << (p % 8)
    def contains(self, item):
        return all(self.bits[p // 8] & (1 << (p % 8)) for p in self._positions(item))

def theory_p(m, n, k):
    return (1 - math.exp(-k * n / m)) ** k

n = 2000
m = 20000
k = round(m / n * math.log(2))
bloom = Bloom(m, k)
for i in range(n):
    bloom.add('url-' + str(i))
fp = sum(1 for i in range(n, n + 5000) if bloom.contains('url-' + str(i)))
print('m/n', m // n, 'k', k)
print('theoretical p', round(theory_p(m, n, k), 4))
print('measured fp / 5000', fp, 'rate', round(fp / 5000, 4))

bucket = TokenBucket(rate=5, capacity=10)
allowed = sum(1 for _ in range(12) if bucket.take())
print('burst allowed with capacity 10', allowed)

```

<OutputBox title='扩展示例运行结果' output='m/n 10 k 7\ntheoretical p 0.0082\nmeasured fp / 5000 41 rate 0.0082\nburst allowed with capacity 10 10' />

<LineByLine code='import hashlib\nimport math\nimport time\n\nclass TokenBucket:\n    def __init__(self, rate, capacity):\n        self.rate = rate\n        self.capacity = capacity\n        self.tokens = capacity\n        self.stamp = time.monotonic()\n    def take(self, n=1):\n        now = time.monotonic()\n        self.tokens = min(self.capacity, self.tokens + (now - self.stamp) * self.rate)\n        self.stamp = now\n        if self.tokens &gt;= n:\n            self.tokens -= n\n            return True\n        return False\n\nclass Bloom:\n    def __init__(self, m, k):\n        self.m = m\n        self.k = k\n        self.bits = bytearray((m + 7) // 8)\n    def _positions(self, item):\n        d = hashlib.sha256(item.encode()).digest()\n        for i in range(self.k):\n            a = int.from_bytes(d[i * 4:i * 4 + 2], &#39;big&#39;)\n            b = int.from_bytes(d[i * 4 + 2:i * 4 + 4], &#39;big&#39;)\n            yield (a + b * i) % self.m\n    def add(self, item):\n        for p in self._positions(item):\n            self.bits[p // 8] |= 1 &lt;&lt; (p % 8)\n    def contains(self, item):\n        return all(self.bits[p // 8] &amp; (1 &lt;&lt; (p % 8)) for p in self._positions(item))\n\ndef theory_p(m, n, k):\n    return (1 - math.exp(-k * n / m)) ** k\n\nn = 2000\nm = 20000\nk = round(m / n * math.log(2))\nbloom = Bloom(m, k)\nfor i in range(n):\n    bloom.add(&#39;url-&#39; + str(i))\nfp = sum(1 for i in range(n, n + 5000) if bloom.contains(&#39;url-&#39; + str(i)))\nprint(&#39;m/n&#39;, m // n, &#39;k&#39;, k)\nprint(&#39;theoretical p&#39;, round(theory_p(m, n, k), 4))\nprint(&#39;measured fp / 5000&#39;, fp, &#39;rate&#39;, round(fp / 5000, 4))\n\nbucket = TokenBucket(rate=5, capacity=10)\nallowed = sum(1 for _ in range(12) if bucket.take())\nprint(&#39;burst allowed with capacity 10&#39;, allowed)\n' :notes='["导入 hashlib 造哈希、math 算公式、time 取单调时钟", "TokenBucket 在取令牌时按时间差惰性补充，无需后台定时器", "stamp 用 monotonic，避免系统时钟回拨让令牌数失真", "tokens 上限被 capacity 钳住，这就是突发上限 b", "Bloom 用 bytearray 存 m 位，每字节装 8 个标志位", "_positions 从 SHA-256 摘要切出 k 对双字节，拼出 k 个位置", "取模 m 把哈希值压进位数组下标", "add 把对应位或上 1，共享位正是不能删除的原因", "contains 全部位为 1 才判存在，故不存在一定被判否", "theory_p 实现 (1 - e 的 -kn/m 次方) 的 k 次方", "m/n = 10 位每元素，最优 k 取 (m/n)ln2 约 7", "插入 2000 个 URL 后统计 5000 个未见 URL 的误判数", "实测误判率 0.0082 与理论值吻合，验证公式可用", "capacity 10 的桶连续 12 次取令牌只放过前 10 次", "去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay", "重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列", "断点持久化 seen + 待抓队列 + 结果，记录已分配未确认任务以便崩溃后重入队", "流式产出比物化全部结果更省内存（tracemalloc 可证）；监控在途数、QPS、状态码分布、队列积压", "四级演进每次只替换一个变量：并发模型 → 连接池/IO 模型 → 去重限流 → 断点与可观测", "同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池", "去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay", "重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列", "断点持久化 seen + 待抓队列 + 结果，记录已分配未确认任务以便崩溃后重入队", "流式产出比物化全部结果更省内存（tracemalloc 可证）；监控在途数、QPS、状态码分布、队列积压", "四级演进每次只替换一个变量：并发模型 → 连接池/IO 模型 → 去重限流 → 断点与可观测", "同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池", "去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay", "重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列", "断点持久化 seen + 待抓队列 + 结果，记录已分配未确认任务以便崩溃后重入队", "流式产出比物化全部结果更省内存（tracemalloc 可证）；监控在途数、QPS、状态码分布、队列积压", "四级演进每次只替换一个变量：并发模型 → 连接池/IO 模型 → 去重限流 → 断点与可观测", "同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池", "去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay", "重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列", "断点持久化 seen + 待抓队列 + 结果，记录已分配未确认任务以便崩溃后重入队", "流式产出比物化全部结果更省内存（tracemalloc 可证）；监控在途数、QPS、状态码分布、队列积压", "四级演进每次只替换一个变量：并发模型 → 连接池/IO 模型 → 去重限流 → 断点与可观测", "同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池", "去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay", "重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列", "断点持久化 seen + 待抓队列 + 结果，记录已分配未确认任务以便崩溃后重入队", "流式产出比物化全部结果更省内存（tracemalloc 可证）；监控在途数、QPS、状态码分布、队列积压", "四级演进每次只替换一个变量：并发模型 → 连接池/IO 模型 → 去重限流 → 断点与可观测", "同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池", "去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay", "重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列", "断点持久化 seen + 待抓队列 + 结果，记录已分配未确认任务以便崩溃后重入队", "流式产出比物化全部结果更省内存（tracemalloc 可证）；监控在途数、QPS、状态码分布、队列积压"]' title='扩展示例逐行讲解' />


## 布隆过滤器的误判率与位数组参数求解

布隆过滤器用 m 位数组、n 个元素、k 个独立哈希。插入后某一位仍是 0 的概率是 (1 - 1/m) 的 kn 次方，约等于 e 的 -kn/m 次方，于是不存在的元素被误判为存在的概率 p = (1 - e 的 -kn/m 次方) 的 k 次方。

对 k 求导并令导数为零，得最优 k* = (m/n) 乘 ln2，代回得 `m = -n` 乘 ln p 除以 (ln2) 的平方，约等于 -2.08 乘 n 乘 ln p，即每元素约需 -ln p 除以 (ln2) 平方 位：p 取 1% 时约 9.6 位每元素，p 取 0.1% 时约 14.4 位。

工程含义很具体：100 万 URL 压到 1% 误判只需约 1.2 MB，用 set 存字符串则要几十 MB；代价是「判存在」可能误判，把没抓过的 URL 当成抓过而漏抓，所以布隆只做「一定不存在」的前置拦截，命中之后还得回查权威去重表。另一个边界是标准布隆不支持删除，因为多个元素共享同一位，清零会毁掉别人；

计数布隆用每格 4 位计数器换删除能力但要防溢出。分布式下换成 Redis 的 SETBIT 或布隆模块时，网络往返必须算进收益账。正文只提了布隆这个名字，这里把位数组参数推导与实测误判率补齐。

**限流与去重的参数、公式与失效边界**

| 机制 | 关键公式 / 参数 | 数据结构 | 失效边界 |
| --- | --- | --- | --- |
| 令牌桶 | T(t)=min(b, T0+r(t-t0)) | 时间戳加浮点令牌数 | 挂钟回拨会放大或倒退令牌 |
| GCRA | T=1/r、tau=b/r、TAT 单时间戳 | 一个理论到达时间 | 空闲后 TAT 需回退处理 |
| 布隆过滤器 | p=(1-e 的 -kn/m 次方) 的 k 次方，k*=(m/n)ln2 | m 位数组加 k 哈希 | 误判只把不存在判成存在，且不能删除 |
| 计数布隆 | 每格 4 位计数器 | 字节数组 | 计数器溢出需扩容或重建 |
| 固定窗口 | count 小于 r 即放行 | 计数器加窗口起点 | 两窗口交界一秒可放行 2r |

<Term word='GCRA 理论到达时间' text='Generic Cell Rate Algorithm 用一个 TAT 时间戳代替令牌桶的连续补充：请求到达时若 t 不小于 TAT 减 tau 就接受，并令 TAT = max(TAT, t) + T，其中 T = 1/r、tau = b/r 是突发容差。它无需后台定时器、状态 O(1)，在允许流量上与令牌桶等价，是网关与 Redis 限流器的常见实现。' />


## 断点续抓的 WAL 与幂等确认

一次 20 万 URL 的抓取跑到 70% 时 worker 被 OOM kill，重启后运维发现 checkpoint 里只有「已完成」集合，数十万「已分配但未确认」的 URL 既不在 done 也不在待抓队列里，永远丢了。

根因是把 checkpoint 当成结果快照而不是操作日志：只在 ack 时写一条记录，崩溃前的 claim 没有落盘。

修复借鉴数据库的 WAL：每次 claim 与 ack 都追加一条 append-only 事件，重放时 `done = 所有` ack、`inflight = claim` 减 ack，把 inflight 重新入队即可，代价是日志量翻倍、需要定期 compact。

幂等写入兜底重复抓取：结果表以 url 为唯一键，ack 重放时 upsert 覆盖而非追加。下面用纯标准库复现 claim/ack 重放与崩溃后的 requeue 判定，能直接数出「崩溃前 1 个在途、重启后 2 个待抓」。

```python
class CrawlLog:
    def __init__(self):
        self.events = []
    def append(self, kind, url):
        self.events.append((kind, url))
    def replay(self):
        done = set()
        inflight = set()
        for kind, url in self.events:
            if kind == 'claim':
                inflight.add(url)
            elif kind == 'ack':
                inflight.discard(url)
                done.add(url)
        return done, inflight

log = CrawlLog()
for u in ['u1', 'u2', 'u3']:
    log.append('claim', u)
log.append('ack', 'u1')
log.append('ack', 'u2')
d, i = log.replay()
print('before crash', sorted(d), sorted(i))
log.append('claim', 'u4')
print('after restart, requeue', sorted(log.replay()[1]))
print('wal events', len(log.events))

```

<Exercise title='按目标误判率反推布隆过滤器参数' task='给定 n = 100000、目标 p 不大于 0.01，用 m = -n 乘 ln p 除以 (ln2) 的平方 与 k = (m/n) 乘 ln2 求 m 与 k，并说明为什么标准布隆过滤器不能删除单个元素。' solution='import math\n\nn = 100000\np = 0.01\nm = math.ceil(-n * math.log(p) / (math.log(2) ** 2))\nk = round(m / n * math.log(2))\nprint(&#39;m bits&#39;, m, &#39;k&#39;, k)\nprint(&#39;bits per item&#39;, round(m / n, 2))\nprint(&#39;MB&#39;, round(m / 8 / 1024 / 1024, 2))\n' explain='p 取 0.01 时每元素约需 9.6 位，10 万 URL 约 120 KB，k 取 (m/n)ln2 约 7 个哈希。标准布隆的位数组被多个元素共享，删一个元素把某位清零可能同时毁掉别的元素，故只能用计数布隆（每格 4 位计数器）或整表重建；误判率公式里的 k 偏离最优值时 p 会上升，这正是参数需要推导而非拍脑袋的原因。' />


### AIMD 自适应并发与 429 退避的成本

<Quiz no='070-X' q='关于令牌桶与布隆过滤器，下面哪项准确？' :options='["令牌桶用 O(1) 状态约束长期速率 r 与突发上限 b；布隆误判率随位数组 m 增大按公式下降", "令牌桶必须后台定时器每秒补充令牌，否则无法工作", "布隆过滤器判定存在时一定存在，判定不存在时可能误判", "布隆过滤器支持直接删除单个元素，把对应位清零即可"]' answer="0" explain='令牌桶在取令牌时按时间差惰性补充，无需定时器，突发上限恰为 b、长期速率被 r 钳住。布隆的方向相反：判「不存在」一定不存在，判「存在」可能误判，且共享位数组不支持直接删除。误判率 p = (1 - e 的 -kn/m 次方) 的 k 次方，在 k* = (m/n)ln2 时取得最小，这与正文只提「用布隆去重」相比才是可核算的参数依据。' />


## 练习、自测与一页纸速记

<Exercise title='基础：给 URL 列表做稳定去重' task='对含重复项的 URL 列表用 seen 集合去重，保持首次出现顺序，打印去重后列表与集合大小。' solution='seen = set()\nout = []\nfor u in [&#39;a&#39;, &#39;b&#39;, &#39;a&#39;, &#39;c&#39;, &#39;b&#39;]:\n    if u not in seen:\n        seen.add(u)\n        out.append(u)\nprint(out, len(seen))' explain='入队前先查 seen 再登记，命中即跳过；这样既去掉重复抓取，又保留首次出现顺序供优先级队列使用。' />

<Exercise title='进阶：用 Semaphore 量在途并发峰值' task='起 6 个任务、Semaphore(2) 限制在途数，在临界区内维护 active 计数与 peak，await sleep(0) 让出，gather 后打印 peak。' solution='import asyncio\nasync def main():\n    active = 0\n    peak = 0\n    sem = asyncio.Semaphore(2)\n    async def job():\n        nonlocal active, peak\n        async with sem:\n            active += 1\n            peak = max(peak, active)\n            await asyncio.sleep(0)\n            active -= 1\n    await asyncio.gather(*(job() for _ in range(6)))\n    print(&#39;peak&#39;, peak)\nasyncio.run(main())' explain='Semaphore 保证同一时刻最多 2 个任务进入临界区，故 peak 恒为 2；约束的是在途请求数而非已创建的 Task 数。' />

<Quiz no='070-1' q='把 20 个串行抓取改成 4 线程池后吞吐上升，主要机制是？' :options='["同步 socket 等待前释放 GIL，多个 IO 等待得以重叠", "GIL 被彻底去掉了", "线程池让纯 Python 解析代码并行执行", "操作系统把 URL 自动分片"]' answer="0" explain='阻塞式 IO 在进入系统调用前由 Py_BEGIN_ALLOW_THREADS 释放 GIL，多个等待可重叠；纯 Python 计算仍受 GIL 串行限制，线程池收益只在等待型任务上。' />

<Quiz no='070-2' q='爬虫里 Semaphore 应该包住哪一段？' :options='["真正发起网络请求的临界区，约束在途请求数", "整个 main 函数，约束创建了多少 Task", "结果写库的纯 CPU 段", "日志打印语句"]' answer="0" explain='Semaphore 要限制的是并发在途请求，而不是已创建的协程数量；把 async with sem 放在 fetch 调用外，才能精确控制对端压力与本机连接数。' />

<Quiz no='070-3' q='关于失败重试，稳妥的策略是？' :options='["只对幂等 GET 的 429/5xx/超时重试，设上限与指数退避", "所有异常都立即重试三次", "由模型自决重试次数", "不设超时，交给网关兜底"]' answer="0" explain='404/解析错误是永久失败，重试无意义；非幂等写操作重试会重复执行。只重试可恢复错误、带上界与退避，并把永久失败送进失败队列。' />

<Predict no='070-P' q='用 gather 并发跑 6 个任务、Semaphore(2) 限流，peak 计数器的值是？' :options='["2", "6", "1"]' answer='0' output='2' explain='Semaphore(2) 只放行 2 个任务进入临界区，其余在 acquire 处等待；active 在进入时加一、退出时减一，其峰值被上限钉死为 2，与总任务数 6 无关。' />

<FillBlank no='070-F' tpl='import  ___ io' :answers='["async"]' hint='回想本讲关于 串行基线 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 一级到三级：并发模型只替换一个变量 的落点。' />

<KnowledgeCard :points='["四级演进每次只替换一个变量：并发模型 → 连接池/IO 模型 → 去重限流 → 断点与可观测", "同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池", "去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay", "重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列", "断点持久化 seen + 待抓队列 + 结果，记录已分配未确认任务以便崩溃后重入队", "流式产出比物化全部结果更省内存（tracemalloc 可证）；监控在途数、QPS、状态码分布、队列积压"]' :pitfalls='["把 Top 结果一次性塞进列表再统一处理", "不做去重与限速直接开满并发", "对所有失败都无限重试", "不做限速与 robots 约束，压垮对方站点同时也让自己被封；分布式化后还会有重复抓取问题"]' summary='每一级演进只替换一个变量：并发模型、连接池、限流策略、持久化，才能清楚看到收益来自哪里' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 四级演进每次只替换一个变量：并发模型 → 连接池/IO 模型 → 去重限流 → 断点与可观测 | 建立直觉 |
| 同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池 | 跑通示例 |
| 去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay | 深入边界 |
| 重试只对幂等 GET 的 429/5xx/超时生效，最大次数 + 指数退避；永久失败进失败队列 | 工程落地 |
| 断点持久化 seen + 待抓队列 + 结果，记录已分配未确认任务以便崩溃后重入队 | 随堂检测 |
| 流式产出比物化全部结果更省内存（tracemalloc 可证）；监控在途数、QPS、状态码分布、队列积压 | 复盘 |

1. 四级演进每次只替换一个变量：并发模型 → 连接池/IO 模型 → 去重限流 → 断点与可观测

2. 同步 IO 释放 GIL 使线程池能重叠等待；asyncio 单线程事件循环消除线程栈开销并复用连接池

3. 去重靠规范化 URL 指纹 + seen；限流用 Semaphore 约束在途数，另设每域名最小间隔与 robots Crawl-delay

[下一讲：项目结构与 src 布局](/engineering/layout)
