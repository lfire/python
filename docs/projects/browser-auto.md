---
title: 第 125 讲 · 实战 04 · Selenium 表单自动化与定时任务
description: 让浏览器完成可重复的网页操作
---

<StageHeader stage='L12 · 工程实战' level='★★★☆☆' time='45 分钟' goal='让浏览器完成可重复的网页操作' prereq='第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频' />

# 第 125 讲 · 实战 04 · Selenium 表单自动化与定时任务

上一讲面对不会动的文件；这一讲要操作会异步加载、时常改版的网页，难就难在判断「什么时候才算可以点」。让浏览器替人做可重复的网页操作，力气大多花在等待上。

一个定时填表脚本用 `time.sleep` 死等页面加载，测试环境三秒就好、线上偶发超时，每天不是白等就是扑空；把等待加长后，一天的任务窗口又不够用。我们先把隐式等待、显式等待与固定 `sleep` 摆在一起比清轮询上界，再用元素定位与 Page Object 收拢选择器，最后借 APScheduler 给定时任务加频率闸门、退避和凭证注入。需要你熟悉异常处理与一点 CSS 选择器；学完能让网页任务无人值守也跑得稳。


## 页面异步加载时，固定 sleep 只是把偶发失败变成变慢

一个定时填表脚本用 `time.sleep(5)` 等页面加载，测试环境三秒就好、线上偶发超过五秒，于是每天有几十次 `NoSuchElementException`；

把 sleep 加到 15 秒后失败少了，但每次都白等十几秒，一天的任务窗口被拖到超时。运维排查还发现账号密码写在脚本里，失败截图把登录页也存进了共享目录。朴素解法「固定 `sleep` + 硬编码凭证 + 无限重试」失败在三点：等待不感知真实状态，早出现浪费、晚出现失败；凭证随脚本泄漏；

没有重试上限与频率约束，任务重叠会把目标站点打疼甚至触发合规问题。这一讲把 `WebDriver` 的显式等待、隐式等待与轮询上界拆成可验证的模型，再用标准库实现带超时、退避、限速与审计的调度封装。

<Callout type="warn" title='先看一个真实会出错的写法' text='用 time.sleep 硬等页面加载：不感知真实状态，只能按最坏情况设值，早出现白等、晚出现直接失败' />


## WebDriver 协议与等待策略：隐式、显式与固定 sleep

W3C `WebDriver` 是客户端—服务器协议，浏览器驱动暴露一组 `HTTP` 端点，`find_element`、`click`、`get_attribute` 每次都是一次 `POST` 往返，元素由服务端生成的 element id 引用。

隐式等待用 `driver.implicitly_wait` 设置，是会话级全局值，只在 `find_element` 找不到时让服务端内部重试，且只针对「元素存在」这一个条件。

显式等待用 `WebDriverWait`，在客户端按间隔反复调用 `expected_conditions` 谓词（`presence_of_element_located`、`element_to_be_clickable`、`text_to_be_present_in_element`），条件满足立刻返回，超时抛 `TimeoutException`。

默认 `poll_frequency` 是 0.5 秒，因此最多约 `timeout/poll` 次往返。两者混用会让服务端的内部重试与客户端轮询叠加，等待时间不可预测，Selenium 官方文档明确警告不要混用；

要用显式等待就把 `implicitly_wait` 设为 0。

固定 `time.sleep` 完全不感知状态，只能按最坏情况设值：元素早出现就白等，晚出现就直接失败，把偶发失败变成偶发变慢。

**等待策略对照**

| 策略 | 判定方 | 默认参数 | 失效信号 |
| --- | --- | --- | --- |
| driver.implicitly_wait(秒) | 服务端 find_element 内部重试 | 会话级全局，默认 0 秒 | 只等元素存在，等不到可点击状态 |
| WebDriverWait(显式) | 客户端轮询 expected_conditions | poll_frequency=0.5，超时抛 TimeoutException | 与隐式等待混用导致时长叠加 |
| time.sleep(固定) | 完全不判定状态 | 按最坏情况手写秒数 | 早出现白等、晚出现直接失败 |
| 轮询上界 | 由 timeout 与 poll 决定 | 最多约 timeout/poll 次往返 | poll 过小会让往返次数暴涨 |

```python
class Page:
    def __init__(self, ready_at):
        self.tick = 0
        self.ready_at = ready_at
    def poll(self):
        self.tick += 1
    def is_ready(self):
        return self.tick >= self.ready_at

def wait_for(page, timeout, poll):
    waited = 0
    while waited < timeout:
        if page.is_ready():
            return 'found', waited
        for _ in range(poll):
            page.poll()
        waited += poll
    return 'timeout', waited

def fixed_wait(page, sleep):
    for _ in range(sleep):
        page.poll()
    return page.is_ready(), sleep

print('explicit early', wait_for(Page(ready_at=3), timeout=10, poll=1))
print('explicit late', wait_for(Page(ready_at=9), timeout=10, poll=1))
print('explicit never', wait_for(Page(ready_at=99), timeout=4, poll=1))
print('fixed on early', fixed_wait(Page(ready_at=3), 10))
print('fixed on late', fixed_wait(Page(ready_at=9), 2))
```

<OutputBox title='主示例运行结果' output='explicit early (&#39;found&#39;, 3)\nexplicit late (&#39;found&#39;, 9)\nexplicit never (&#39;timeout&#39;, 4)\nfixed on early (True, 10)\nfixed on late (False, 2)' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='class Page:\n    def __init__(self, ready_at):\n        self.tick = 0\n        self.ready_at = ready_at\n    def poll(self):\n        self.tick += 1\n    def is_ready(self):\n        return self.tick &gt;= self.ready_at\n\ndef wait_for(page, timeout, poll):\n    waited = 0\n    while waited &lt; timeout:\n        if page.is_ready():\n            return &#39;found&#39;, waited\n        for _ in range(poll):\n            page.poll()\n        waited += poll\n    return &#39;timeout&#39;, waited\n\ndef fixed_wait(page, sleep):\n    for _ in range(sleep):\n        page.poll()\n    return page.is_ready(), sleep\n\nprint(&#39;explicit early&#39;, wait_for(Page(ready_at=3), timeout=10, poll=1))\nprint(&#39;explicit late&#39;, wait_for(Page(ready_at=9), timeout=10, poll=1))\nprint(&#39;explicit never&#39;, wait_for(Page(ready_at=99), timeout=4, poll=1))\nprint(&#39;fixed on early&#39;, fixed_wait(Page(ready_at=3), 10))\nprint(&#39;fixed on late&#39;, fixed_wait(Page(ready_at=9), 2))' :notes='["Page 模拟异步页面：tick 是逻辑时钟，ready_at 是元素出现的时刻", "构造接收 ready_at，表示元素在第几个 tick 就绪", "把逻辑时钟归零", "保存元素何时变为可用，模拟不同加载耗时", "poll 推进一个轮询间隔，对应一次 WebDriver 往返", "逻辑时钟加一", "谓词：显式等待每次轮询就检查它是否满足条件", "到达 ready_at 即视为元素已就绪", "空行，只用于分隔逻辑块，不影响执行结果。", "wait_for 是显式等待模型：带 timeout 与 poll 两个参数", "已等待的逻辑 tick 计数", "循环上界由 timeout 决定，保证不会无限等待", "每轮先判条件再推进，条件满足立即返回", "返回状态与实际等待量，早出现就少等", "按 poll 推进逻辑时钟，模拟轮询间隔", "推进一 tick，等价于发一次 find_element 命令", "累计已等待 tick", "超过 timeout 仍未就绪，返回 timeout 而非抛未捕获异常", "空行，只用于分隔逻辑块，不影响执行结果。", "fixed_wait 模拟固定 sleep：不管状态先等满", "无条件循环 sleep 次", "每次循环推进一 tick，不做条件判断", "返回是否满足与实际等待量，暴露白等成本", "空行，只用于分隔逻辑块，不影响执行结果。", "元素第 3 tick 出现，显式等待只等 3 就返回", "元素第 9 tick 出现，同一超时下自动等到 9", "元素永不出现时，4 tick 超时后明确返回 timeout", "固定等 10 tick 虽成功，但比需要多等 7 个 tick", "固定只等 2 tick 而元素要 9 tick，直接失败"]' title='第 125 讲 · 实战 04 · Selenium 表单自动化与定时任务' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

<ConceptDiagram type='flow3' title='第 125 讲 · WebDriver 协议与等待策略：隐式、显式与固定 sleep' labels='WebDriver 协议与等待策略：隐式、显…|定位器、Page Object 与异常截图|定时任务、凭证、频率与合规' caption='让浏览器完成可重复的网页操作' />

这张图把本讲串成三段：先看输入从哪里来，再看规则在哪一步生效，最后看输出带了什么代价。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 定位器、Page Object 与异常截图

定位器优先选稳定的 `data-testid` 或 `id`：`By.CSS_SELECTOR` 用浏览器原生选择器、简洁且快，`By.XPATH` 支持文本匹配与轴（ancestor、following-sibling）但依赖 DOM 结构，`/html/body/div[3]` 这类绝对路径改一个区块就失效。

Page Object 模式把定位器与操作封进类，测试用例只调用 `login_as`、`submit_form` 这类语义方法，页面改版时只改一处。

异步页面的典型异常各有根因：`NoSuchElementException` 是等待策略没覆盖加载窗口；

`StaleElementReferenceException` 是 DOM 节点被重建后、服务端持有的旧 element id 已失效，必须重新定位；

`ElementClickInterceptedException` 是被遮罩或浮动层挡住，要等遮罩消失。

失败现场至少留三样：`driver.save_screenshot(path)` 截图、`driver.page_source` 页面源码、`driver.current_url` 当前地址；

日志里再带上选择器与超时值，才能区分是「没等到」还是「定位器写错」。截图里可能含登录态与个人信息，存放目录与保留期要按合规要求限制。

```python
import os

def can_run(last_ts, now, min_interval):
    return now - last_ts >= min_interval

def retry_budget(max_retries):
    return [2 ** i for i in range(max_retries)]

print('rate gate', can_run(last_ts=0, now=5, min_interval=10), can_run(last_ts=0, now=10, min_interval=10))
print('backoff ticks', retry_budget(4))
os.environ['LOGIN_PASSWORD'] = 'from-vault'
print('credential injected', os.environ.get('LOGIN_PASSWORD') == 'from-vault')
os.environ.pop('LOGIN_PASSWORD', None)
```

<OutputBox title='对照写法：先自己猜，再点开' output='rate gate False True\nbackoff ticks [1, 2, 4, 8]\ncredential injected True' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "class Page:\n    def __init__(self, ready_at):\n        self.tick = 0\n        self.ready_at = ready_at\n    def poll(self):\n        self.tick += 1\n    def is_ready(self):\n        return self.tick &gt;= self.ready_at\n\ndef wait_for(page, timeout, poll):\n    waited = 0\n    while waited &lt; timeout:\n        if page.is_ready():\n            return &#39;found&#39;, waited\n        for _ in range(poll):\n            page.poll()\n        waited += poll\n    return &#39;timeout&#39;, waited\n\ndef fixed_wait(page, sleep):\n    for _ in range(sleep):\n        page.poll()\n    return page.is_ready(), sleep\n\nprint(&#39;explicit early&#39;, wait_for(Page(ready_at=3), timeout=10, poll=1))\nprint(&#39;explicit late&#39;, wait_for(Page(ready_at=9), timeout=10, poll=1))\nprint(&#39;explicit never&#39;, wait_for(Page(ready_at=99), timeout=4, poll=1))\nprint(&#39;fixed on early&#39;, fixed_wait(Page(ready_at=3), 10))\nprint(&#39;fixed on late&#39;, fixed_wait(Page(ready_at=9), 2))", "note": "WebDriver 协议与等待策略：隐式、显式与固定 sleep"}, {"label": "对照 / 进阶", "code": "import os\n\ndef can_run(last_ts, now, min_interval):\n    return now - last_ts &gt;= min_interval\n\ndef retry_budget(max_retries):\n    return [2 ** i for i in range(max_retries)]\n\nprint(&#39;rate gate&#39;, can_run(last_ts=0, now=5, min_interval=10), can_run(last_ts=0, now=10, min_interval=10))\nprint(&#39;backoff ticks&#39;, retry_budget(4))\nos.environ[&#39;LOGIN_PASSWORD&#39;] = &#39;from-vault&#39;\nprint(&#39;credential injected&#39;, os.environ.get(&#39;LOGIN_PASSWORD&#39;) == &#39;from-vault&#39;)\nos.environ.pop(&#39;LOGIN_PASSWORD&#39;, None)", "note": "定位器、Page Object 与异常截图"}]' title='两种写法切换看' />


## 定时任务、凭证、频率与合规默认值

APScheduler 常用 `BackgroundScheduler` 配 `CronTrigger`（cron 表达式）或 `IntervalTrigger`（固定间隔）；

三个参数决定稳定性：`max_instances` 限制同一任务并发实例数，防止上一轮未结束又触发；`coalesce=True` 把错过的多次触发合并成一次；

`misfire_grace_time` 给出触发错过后仍允许补跑的时间窗口，超时就丢弃。

`jobstores` 可把任务持久化到数据库，进程重启不丢。凭证走 `os.environ` 或密钥服务注入，绝不写进脚本、命令行参数或失败截图。执行频率要有硬约束：`min_interval` 控制两次运行的最小间隔、按域名限速、并发连接数上限、User-Agent 标识清楚，并尊重 `robots.txt` 与服务条款。

重试只对幂等步骤生效，带指数退避（1、2、4、8 个间隔）与最大次数；每次运行记录日志、耗时、失败清单与截图路径。没有频率约束、账号写死、无限重试是最常见的三类事故来源。

**常见异常与修复**

| 异常 | 根因 | 修复 |
| --- | --- | --- |
| NoSuchElementException | 等待窗口没覆盖异步加载 | 改用显式等待等特定条件 |
| StaleElementReferenceException | DOM 重建后旧 element id 失效 | 重新定位元素，不复用旧引用 |
| ElementClickInterceptedException | 遮罩或浮动层挡住点击 | 等遮罩消失或滚动到可见区域 |
| TimeoutException | 条件在超时内未满足 | 记录选择器与超时值，区分定位错与真没出现 |

<CheckList id='P125b' title='上线前自检' :items='["能复现并解释「用 time.sleep 硬等页面加载」", "能复现并解释「同时设隐式等待与显式等待」", "能复现并解释「账号密码写进脚本、失败无限重试、任务无频率约束」", "能用一条命令验证 WebDriver 与等待策略", "关键路径有自动化测试与失败分支"]' />


## WebDriver 的 element id 引用表与显式等待底层

W3C `WebDriver` 把浏览器能力暴露成 `HTTP` 端点，服务端为每个 DOM 节点分配 element id 并维护一张引用表；

`find_element` 找不到时若设了隐式等待，服务端会在内部轮询 DOM 直到超时，而显式等待把轮询放到客户端，每 `poll_frequency` 秒发一次命令去求值 `expected_conditions`。

二者叠加会让服务端每次内部重试又被客户端再轮询一遍，总时长接近两者乘积，这就是官方要求不要混用的原因。

`StaleElementReferenceException` 来自引用表：节点被重新渲染后旧 id 指向已废弃对象，客户端必须重新发一次定位命令。

固定 `sleep` 不读取任何状态，其期望等待时间只能取加载耗时的上界，因此平均值必然远大于实际需要。轮询循环在字节码层是一条后向跳转（3.11 起叫 `JUMP_BACKWARD`），循环回边也是解释器检查切换请求的点；没有 `timeout` 的轮询会永久占住这条回边，所以超时不是可选项而是结构约束。

定时任务的 `max_instances`、`coalesce` 与 `misfire_grace_time` 共同决定错过触发与重叠时的行为。

```python
import dis

def wait_loop(timeout, ready_at):
    waited = 0
    while waited < timeout:
        if waited >= ready_at:
            return waited
        waited += 1
    return -1

print('found at 3', wait_loop(10, 3))
print('found at 9', wait_loop(10, 9))
print('timeout at 99', wait_loop(10, 99))
ops = [i.opname for i in dis.get_instructions(wait_loop)]
print('has jump backward', any(o.startswith('JUMP_BACKWARD') for o in ops))
```

<OutputBox title='原理验证' output='found at 3 3\nfound at 9 9\ntimeout at 99 -1\nhas jump backward True' />

<Term word='WebDriver 与等待策略' text='W3C `WebDriver` 是客户端—服务器协议，浏览器驱动暴露一组 `HTTP` 端点，`find_element`、`click`、`get_attribute` 每次都是一次 `POST` 往返，元素由服务端生成的 element id 引用。隐式等待用 `driver.implicitly_wait` 设置…' />

<Term word='元素定位 XPath / CSS' text='定位器优先选稳定的 `data-testid` 或 `id`：`By.CSS_SELECTOR` 用浏览器原生选择器、简洁且快，`By.XPATH` 支持文本匹配与轴（ancestor、following-sibling）但依赖 DOM 结构，`/html/body/div[3]` 这类绝对路径改一个区块就失效。Pag…' />


## 带限速、重试上限与审计的定时填表任务

一个每天跑的填表任务要同时满足三件事：两次运行之间至少隔十个逻辑 tick（频率约束）、单次最多重试三次且逐次退避（重试上限）、每次动作都留审计记录（可追溯）。

下面把三者编进一个最小调度封装：`allowed` 用 `last_run` 与 `min_interval` 守住频率，`job` 在频率不达标时直接跳过并记 `skip`，通过后才按 `MAX_RETRIES` 调 `fill_form`；

`fill_form` 用 `timeout` 限制轮询次数，元素迟迟不出现就返回 `False`，让重试兜底而不是无限等。`events` 列表充当审计日志，记录每次尝试与跳过，便于复盘是「被限速」还是「真的没等到」。

真实项目把 `now` 换成 `time.monotonic`、把 `events` 换成 `logging`、把 `fill_form` 换成 `WebDriverWait` 加 Page Object，并补 `save_screenshot` 与失败清单。

片段可直接运行，重点看每个失败分支都有明确出口。

```python
MIN_INTERVAL = 10
MAX_RETRIES = 3
last_run = -MIN_INTERVAL
events = []

def allowed(now):
    return now - last_run >= MIN_INTERVAL

def fill_form(ready_at, timeout):
    for tick in range(timeout):
        if tick >= ready_at:
            return True
    return False

def job(now, ready_at, timeout):
    global last_run
    if not allowed(now):
        events.append('skip')
        return 'skipped by rate limit'
    last_run = now
    for attempt in range(MAX_RETRIES):
        events.append('attempt ' + str(attempt + 1))
        if fill_form(ready_at, timeout):
            return 'success on attempt ' + str(attempt + 1)
    return 'failed after retries'

print('job 0', job(0, ready_at=3, timeout=10))
print('job 5', job(5, ready_at=3, timeout=10))
print('job 10', job(10, ready_at=99, timeout=4))
print('audit events', events)
```

<Callout type="idea" title='落地提示' text='一律用 WebDriverWait 等特定状态，凭证外部注入，任务加日志、截图、重试上限与执行频率约束' />

**调度参数与含义**

| 参数 | 作用 | 缺失后果 |
| --- | --- | --- |
| max_instances | 限制同一任务并发实例数 | 上一轮未结束又触发，任务重叠 |
| coalesce=True | 把错过的多次触发合并为一次 | 进程恢复后瞬间补跑一大批 |
| misfire_grace_time | 触发错过后仍允许补跑的窗口 | 过期的老任务被无限延迟执行 |
| min_interval | 两次运行最小间隔 | 对目标站点高频请求，触发限流或合规问题 |
| 指数退避 1/2/4/8 | 重试前逐级拉长间隔 | 失败后立即重试，放大故障 |

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用 time.sleep 硬等页面加载 | 不感知真实状态，只能按最坏情况设值，早出现白等、晚出现直接失败 | 改用 WebDriverWait 配 expected_conditions 等特定状态，并把 implicitly_wait 设为 0 避免混用 |
| 同时设隐式等待与显式等待 | 服务端内部重试与客户端轮询叠加，等待时间不可预测地变长 | 只保留显式等待一种，隐式等待归零，用 timeout 单独控制上界 |
| 账号密码写进脚本、失败无限重试、任务无频率约束 | 凭证随代码与截图泄漏，重叠任务放大请求量触发限流与合规风险 | 凭证走 os.environ 注入，重试带指数退避与最大次数，min_interval 加 max_instances 限制频率与重叠 |

<Callout type="warn" title='本讲最容易踩的坑' text='用 time.sleep 硬等页面加载：不感知真实状态，只能按最坏情况设值，早出现白等、晚出现直接失败' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用 time.sleep 硬等页面加载", "body": "不感知真实状态，只能按最坏情况设值，早出现白等、晚出现直接失败", "tip": "改用 WebDriverWait 配 expected_conditions 等特定状态，并把 implicitly_wait 设为 0 避免混用"}, {"title": "第 2 步：同时设隐式等待与显式等待", "body": "服务端内部重试与客户端轮询叠加，等待时间不可预测地变长", "tip": "只保留显式等待一种，隐式等待归零，用 timeout 单独控制上界"}, {"title": "第 3 步：账号密码写进脚本、失败无限重试、任务无频率约…", "body": "凭证随代码与截图泄漏，重叠任务放大请求量触发限流与合规风险", "tip": "凭证走 os.environ 注入，重试带指数退避与最大次数，min_interval 加 max_instances 限制频率与重叠"}]' />


## 动手练一练与自测

<Exercise title='基础：实现带超时的显式等待并对比固定 sleep' task='写一个 wait_for(pred, timeout, poll) 每轮先判谓词再推进，返回 (状态, 已等待)，分别验证元素第 3 tick 出现与永不出现两种情况。' solution='def wait_for(ready_at, timeout):\n    waited = 0\n    while waited &lt; timeout:\n        if waited &gt;= ready_at:\n            return &#39;found&#39;, waited\n        waited += 1\n    return &#39;timeout&#39;, waited\nprint(wait_for(3, 10))\nprint(wait_for(99, 4))' explain='输出 (&#39;found&#39;, 3) 与 (&#39;timeout&#39;, 4)：条件满足立即返回且带回真实等待量，超时也有明确上界，这是固定 sleep 做不到的。' />

<Exercise title='进阶：给调度加频率闸门与指数退避' task='实现 can_run(last_ts, now, min_interval) 与 retry_budget(n)，打印间隔不足/刚好时的闸门结果及前四次退避间隔。' solution='def can_run(last_ts, now, min_interval):\n    return now - last_ts &gt;= min_interval\ndef retry_budget(n):\n    return [2 ** i for i in range(n)]\nprint(can_run(0, 5, 10), can_run(0, 10, 10))\nprint(retry_budget(4))' explain='输出 False True 与 [1, 2, 4, 8]：频率闸门挡住过早的重复触发，退避让失败后的重试间隔逐级拉长，避免瞬时重试放大故障。' />

<Quiz no='125-1' q='关于隐式等待与显式等待，哪一项准确？' :options='["二者不要混用：隐式是服务端 find_element 内部重试，显式是客户端轮询条件", "两者叠加会让等待更精确，应同时设大值", "隐式等待能等 element_to_be_clickable", "显式等待的 poll_frequency 默认 5 秒"]' answer="0" explain='隐式等待是会话级全局、只针对元素存在；显式等待用 WebDriverWait 的默认 poll_frequency=0.5 秒在客户端轮询条件。混用会叠加等待时长，官方文档明确反对。' />

<Quiz no='125-2' q='WebDriverWait 的默认轮询间隔与超时行为是？' :options='["poll_frequency=0.5 秒，超时抛 TimeoutException", "poll_frequency=5 秒，超时返回 None", "poll_frequency=0.05 秒，超时静默继续", "没有超时，一直轮询到条件满足"]' answer="0" explain='WebDriverWait(driver, timeout, poll_frequency=0.5, ignored_exceptions=None)，最多约 timeout/0.5 次往返，条件未满足则抛 TimeoutException。' />

<Quiz no='125-3' q='定时任务里防止上一轮未结束又触发的参数是？' :options='["max_instances", "coalesce", "misfire_grace_time", "poll_frequency"]' answer="0" explain='max_instances 限制同一任务的并发实例数；coalesce 合并错过的触发，misfire_grace_time 给补跑窗口，三者职责不同，poll_frequency 属于等待侧参数。' />

```bash
python -m compileall -q . && python -m pytest -q
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 WebDriver 与等待策略 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。

<KnowledgeCard :points='["W3C WebDriver 每个命令一次 HTTP 往返，元素由服务端 element id 引用", "隐式等待是会话级全局、只等元素存在；显式等待 WebDriverWait 默认 poll_frequency=0.5，超时抛 TimeoutException", "隐式与显式混用会让等待时长叠加，要用显式就把 implicitly_wait 设为 0", "固定 time.sleep 不感知状态：早出现白等、晚出现失败，只能按最坏情况设值", "StaleElementReferenceException 源于 DOM 重建后旧 element id 失效，需重新定位；失败留截图、page_source、current_url", "调度用 max_instances 防重叠、coalesce 合并错过触发、misfire_grace_time 设补跑窗口；凭证走环境变量，重试带退避与频率约束"]' :pitfalls='["用 time.sleep 硬等页面加载", "同时设隐式等待与显式等待", "账号密码写进脚本、失败无限重试、任务无频率约束", "用 sleep 硬等、或把账号密码写进脚本，既不稳定也不安全"]' summary='浏览器自动化最容易挂在选择器上：页面异步加载时元素尚未出现，固定 sleep 只是把偶发失败变成偶发变慢' />

1. W3C WebDriver 每个命令一次 HTTP 往返，元素由服务端 element id 引用

2. 隐式等待是会话级全局、只等元素存在；显式等待 WebDriverWait 默认 poll_frequency=0.5，超时抛 TimeoutException

3. 隐式与显式混用会让等待时长叠加，要用显式就把 implicitly_wait 设为 0

[下一讲：实战 05 · 短链与图片服务](/projects/net-shortlink)

<Predict no='125-4' q='元素在第 3 个轮询 tick 出现、timeout=10、poll=1 时，显式等待 wait_for 返回什么？' :options='["(&#39;found&#39;, 3)", "(&#39;timeout&#39;, 10)", "(&#39;found&#39;, 10)"]' answer='0' output='(&#39;found&#39;, 3)' explain='显式等待每轮先判条件再推进，条件一满足就立刻返回并把实际等待量带出；固定 sleep 只能按最坏情况设成 10，元素早出现时白白多等 7 个 tick。' />

<FillBlank no='125-5' tpl='___ __init__(self, ready_at):' :answers='["def"]' hint='回想本讲关于 WebDriver 与等待策略 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 WebDriver 协议与等待策略：隐式、显式与固定 sleep 的落点。' />


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/125-browser-auto.py`

```bash
python3 examples/lessons/125-browser-auto.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/125-browser-auto.py) · [全部示例代码索引](/examples/)
