---
title: 第 078 讲 · 日志：logging、结构化日志与追踪关联
description: 让线上问题可检索、可关联、可告警
---

<StageHeader stage='L7 · 工程化' level='★★★☆☆' time='35 分钟' goal='让线上问题可检索、可关联、可告警' prereq='第 077 讲 · 属性测试、基准测试与模糊测试' />

# 第 078 讲 · 日志：logging、结构化日志与追踪关联

前面几讲把输入校验与异常边界这些上线前的护栏补齐了，可真出了线上故障，光有护栏不够，还得查得动。一次支付排障翻遍记录，只看到满屏「处理中」和一句笼统的失败，既没有订单号也没有请求标识，二十个服务的记录串不成一条链；更麻烦的是有人把完整账号打了进去，差点成了合规事故。

从 `Logger`、`Handler`、`Formatter` 三者怎么配合说起，走到级别与传播为什么会重复打印，再把记录改成结构化 `JSON` 并注入 `trace_id` 把一次请求串起来，接着谈采样与脱敏，最后关联到分布式追踪。带着函数、异常与模块的基础来；学完能统一日志格式、按级别采样、让敏感字段默认脱敏，异常也带上上下文而不是一句失败。


## 满屏 INFO: processing 和一句 failed，二十个服务串不成一条链

一次支付故障排查，翻遍日志只看到满屏 `INFO: processing` 和一句 `failed`，既没有订单号也没有请求标识，二十个服务的日志串不成一条链；

更糟的是有人把完整卡号和密钥打进了 `INFO`，差点变成合规事故。根子在于把日志当成给人读的散文，而不是给机器检索的数据：只有结构化字段加上 `trace_id`，才能把一次请求跨服务关联起来。另有两个反复出现的坑：子 logger 自己挂了 handler 又没关 `propagate`，同一条记录被打印两遍；

多进程共写同一个 `RotatingFileHandler`，轮转时互相覆盖。

本讲把 `Logger` / `Handler` / `Formatter`、级别传播、结构化 `JSON`、`trace_id` 注入与采样脱敏讲到能支撑线上排障。

<Callout type="warn" title='先看一个真实会出错的写法' text='循环里打 INFO、把卡号/密钥写进日志：磁盘被洪泛压垮且制造合规事故，异常只打一句 failed 无上下文' />


## Logger / Handler / Formatter 与级别传播

logging 的级别是整数常量：`NOTSET=0`、`DEBUG=10`、`INFO=20`、`WARNING=30`、`ERROR=40`、`CRITICAL=50`，`logging.getLevelName(30)` 返回字符串 `'WARNING'`。

Logger 按点分名字形成层级，`app.db` 的祖先依次是 `app` 再到 root，`propagate=True` 是默认值，会把记录继续交给祖先的 handlers；

若子 logger 与 root 都挂了 handler，同一条日志就会打印两次，此时应设 `logger.propagate = False`，或者统一只在 root 上挂 handler。

`logging.basicConfig` 常用 `level`、`format`、`handlers` 等参数，默认只在 root 还没有 handler 时生效；

Python 3.8 起加入的 `force=True` 会先移除已有的 root handler 再重新配置，适合需要覆盖旧配置的场景。

未设 level 的 logger 通过 `getEffectiveLevel()` 沿祖先上溯，root 默认是 `WARNING=30`，所以子 logger 上的 `child.info(...)` 会被丢弃、`child.warning(...)` 才输出。

常见 Handler 有 `StreamHandler`、`FileHandler`、`RotatingFileHandler`（按 `maxBytes` 切割、保留 `backupCount` 份）、`TimedRotatingFileHandler` 与 `QueueHandler`；

库代码应加一个 `NullHandler`，避免「No handlers could be found」告警。

Formatter 的格式串由 `%(asctime)s`、`%(levelname)s`、`%(name)s`、`%(message)s`、`%(lineno)d` 这类占位符组成，可配 `datefmt` 与 `style`；

在拼接昂贵消息前用 `logger.isEnabledFor(logging.DEBUG)` 先判断，能省下这次开销。

**日志级别与传播**

| 级别 / 机制 | 值 / 行为 | 说明 |
| --- | --- | --- |
| NOTSET / DEBUG / INFO | 0 / 10 / 20 | 低于阈值不输出 |
| WARNING / ERROR / CRITICAL | 30 / 40 / 50 | root 默认 WARNING=30 |
| getLevelName(30) | 'WARNING' | 级别数值转名称 |
| logger.propagate | 默认 True | 子与祖先都挂 handler 会重复输出 |
| getEffectiveLevel() | 沿祖先上溯 | 未设 level 的子 logger 继承 |
| basicConfig(force=True) | 3.8+ 先清 root handler | 重复调用不再静默失效 |
| NullHandler | 库代码添加 | 避免 No handlers could be found 告警 |

<Callout type="tip" title='核心心智模型' text='logging 的级别是整数常量：`NOTSET=0`、`DEBUG=10`、`INFO=20`、`WARNING=30`、`ERROR=40`、`CRITICAL=50`，`logging.getLevelName(30)` 返回字符串 `&#39;WARNING&#39;`。Logger 按点分名字形成层级…' />

**Handler 与 Formatter 选型**

| 组件 | 适用 | 注意 |
| --- | --- | --- |
| StreamHandler | 控制台 / StringIO | emit 受 handler 内 RLock 保护 |
| RotatingFileHandler(maxBytes, backupCount) | 按大小轮转 | 多进程共写轮转不安全 |
| TimedRotatingFileHandler | 按时间轮转 | 跨时区需统一 |
| QueueHandler + QueueListener | 多进程单写者 | 规避文件轮转竞态 |
| Formatter 的 %(name)s/%(lineno)d | 格式字段 | extra 可加自定义字段 |
| 自定义 Formatter / Filter | JSON、trace_id、脱敏 | filter 返回 bool 决定是否输出 |

记录是怎么产生的：`Logger.makeRecord`（或 `logging.setLogRecordFactory` 指定的工厂）构造 `LogRecord`，属性来自固定字段、`extra` 字典与 `Filter` 的注入。

`Logger.handle` 再调 `callHandlers`，沿当前 logger 及其祖先逐级找 handler；

每个 handler 先比较 `level`、再过自身的过滤器、最后在 `self.lock`（一把 `threading.RLock`）保护下 `emit`，而 `propagate` 决定要不要继续上溯——「子 logger 与 root 都挂 handler 就打印两遍」正是从这里来的。

`logging.basicConfig` 默认给 root 加一个 `StreamHandler`；

未设 level 的 logger 由 `getEffectiveLevel` 上溯到 root 的 `WARNING(30)`，所以 `INFO` 被丢弃。

`contextvars.ContextVar` 把值存在上下文局部映射里，`asyncio` 在 `create_task` 时复制当前 context，因此 `trace_id` 在同一请求的多个协程里一致，而线程级的 `threading.local` 做不到。

最后，自定义 `JSON` `Formatter` 覆盖 `format()` 生成结构化字段，脱敏则在 `format` / `filter` 阶段对长数字串做掩码，避免敏感值落地。

<Term word='Logger / Handler / Formatter' text='logging 的级别是整数常量：`NOTSET=0`、`DEBUG=10`、`INFO=20`、`WARNING=30`、`ERROR=40`、`CRITICAL=50`，`logging.getLevelName(30)` 返回字符串 `&#39;WARNING&#39;`。Logger 按点分名字形成层级，`app.db` 的祖…' />

<Term word='级别与传播' text='结构化日志把一行记录做成可解析的 `JSON` 对象——`level`、`msg`、`trace`、`event` 这类字段各自独立——而不是一句自然语言。做法大致三种：在自定义 `Formatter` 里对一条 `dict` 调 `json.dumps`；用 `extra={&#39;order_id&#39;: ...}` 给…' />


### 子 logger 挂了 handler 为什么还会打两遍

```python
import logging, io, inspect

buf = io.StringIO()
root = logging.getLogger()
root.setLevel(logging.WARNING)
rh = logging.StreamHandler(buf)
rh.setFormatter(logging.Formatter('ROOT %(levelname)s %(name)s'))
root.handlers = [rh]
child = logging.getLogger('app.db')
print('getEffectiveLevel', child.getEffectiveLevel())
print('getLevelName(30)', logging.getLevelName(30))
print('lastResort level', logging.lastResort.level)
child.info('hidden')
child.warning('shown')
print('captured', repr(buf.getvalue().strip()))
print('isEnabledFor(INFO)', child.isEnabledFor(logging.INFO))
print('Filter.filter sig', str(inspect.signature(logging.Filter.filter)))
```

<OutputBox title='原理验证' output='getEffectiveLevel 30\ngetLevelName(30) WARNING\nlastResort level 30\ncaptured &#39;ROOT WARNING app.db&#39;\nisEnabledFor(INFO) False\nFilter.filter sig (self, record)' />


## 对照：散文日志与带字段的 JSON 日志

```python
import logging, io, json, contextvars

trace_id = contextvars.ContextVar('trace_id', default='-')

class ContextFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id.get()
        return True

stream = io.StringIO()
handler = logging.StreamHandler(stream)
handler.setFormatter(logging.Formatter('%(levelname)s %(name)s %(trace_id)s %(message)s'))
handler.addFilter(ContextFilter())

logger = logging.getLogger('shop.order')
logger.setLevel(logging.DEBUG)
logger.handlers = [handler]
logger.propagate = False

trace_id.set('t-123')
logger.info('order created %s', 'A100')
logger.warning('stock low %d', 3)
trace_id.set('t-456')
logger.error('payment failed %s', 'card-xxxx')
print(stream.getvalue().strip())
```

<OutputBox title='主示例运行结果' output='INFO shop.order t-123 order created A100\nWARNING shop.order t-123 stock low 3\nERROR shop.order t-456 payment failed card-xxxx' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import logging, io, json, contextvars\n\ntrace_id = contextvars.ContextVar(&#39;trace_id&#39;, default=&#39;-&#39;)\n\nclass ContextFilter(logging.Filter):\n    def filter(self, record):\n        record.trace_id = trace_id.get()\n        return True\n\nstream = io.StringIO()\nhandler = logging.StreamHandler(stream)\nhandler.setFormatter(logging.Formatter(&#39;%(levelname)s %(name)s %(trace_id)s %(message)s&#39;))\nhandler.addFilter(ContextFilter())\n\nlogger = logging.getLogger(&#39;shop.order&#39;)\nlogger.setLevel(logging.DEBUG)\nlogger.handlers = [handler]\nlogger.propagate = False\n\ntrace_id.set(&#39;t-123&#39;)\nlogger.info(&#39;order created %s&#39;, &#39;A100&#39;)\nlogger.warning(&#39;stock low %d&#39;, 3)\ntrace_id.set(&#39;t-456&#39;)\nlogger.error(&#39;payment failed %s&#39;, &#39;card-xxxx&#39;)\nprint(stream.getvalue().strip())' :notes='["导入 logging、StringIO 捕获、json 备用、contextvars 存 trace_id", "空行，只用于分隔逻辑块，不影响执行结果。", "定义 ContextVar，默认值为占位符", "空行，只用于分隔逻辑块，不影响执行结果。", "自定义 Filter 为每条记录注入当前 trace_id", "从 ContextVar 取当前请求标识写进 record", "返回 True 表示记录继续被处理", "用 StringIO 作为内存输出流，便于断言", "空行，只用于分隔逻辑块，不影响执行结果。", "StreamHandler 绑定到该流", "Formatter 里引用 %(trace_id)s 这个注入字段", "把 Filter 挂到 handler 上", "取名为 shop.order 的子 logger", "空行，只用于分隔逻辑块，不影响执行结果。", "级别设 DEBUG，允许所有级别通过", "直接指定 handlers，避免 root 重复", "propagate=False 阻止向 root 再传一份", "设置第一个请求的 trace_id", "空行，只用于分隔逻辑块，不影响执行结果。", "%-style 惰性格式化，消息带订单号", "同一 trace 下再记一条 WARNING", "切换到另一个请求上下文", "错误日志自动带上 t-456 标识", "打印捕获到的三行结构化日志", "Logger 按点分层级，propagate=True 会把记录传给祖先；子与 root 都挂 handler 会重复输出"]' title='第 078 讲 · 日志：logging、结构化日志与追踪关联' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import logging, io, json

def mask_digits(text):
    out, i, n = [], 0, len(text)
    while i < n:
        if text[i].isdigit():
            j = i
            while j < n and text[j].isdigit():
                j += 1
            run = text[i:j]
            out.append(run[:6] + '*' * (len(run) - 10) + run[-4:] if len(run) >= 10 else run)
            i = j
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)

class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {'level': record.levelname, 'event': mask_digits(record.getMessage())}
        return json.dumps(payload, ensure_ascii=False)

buf = io.StringIO()
h = logging.StreamHandler(buf)
h.setFormatter(JsonFormatter())
log = logging.getLogger('secure')
log.setLevel(logging.INFO)
log.handlers = [h]
log.propagate = False
log.info('idcard 110101199003071234 approved')
print(buf.getvalue().strip())
```

<OutputBox title='对照写法：先自己猜，再点开' output='{"level": "INFO", "event": "idcard 110101********1234 approved"}' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import logging, io, json, contextvars\n\ntrace_id = contextvars.ContextVar(&#39;trace_id&#39;, default=&#39;-&#39;)\n\nclass ContextFilter(logging.Filter):\n    def filter(self, record):\n        record.trace_id = trace_id.get()\n        return True\n\nstream = io.StringIO()\nhandler = logging.StreamHandler(stream)\nhandler.setFormatter(logging.Formatter(&#39;%(levelname)s %(name)s %(trace_id)s %(message)s&#39;))\nhandler.addFilter(ContextFilter())\n\nlogger = logging.getLogger(&#39;shop.order&#39;)\nlogger.setLevel(logging.DEBUG)\nlogger.handlers = [handler]\nlogger.propagate = False\n\ntrace_id.set(&#39;t-123&#39;)\nlogger.info(&#39;order created %s&#39;, &#39;A100&#39;)\nlogger.warning(&#39;stock low %d&#39;, 3)\ntrace_id.set(&#39;t-456&#39;)\nlogger.error(&#39;payment failed %s&#39;, &#39;card-xxxx&#39;)\nprint(stream.getvalue().strip())", "note": "Logger / Handler / Formatter 与级别传播"}, {"label": "对照 / 进阶", "code": "import logging, io, json\n\ndef mask_digits(text):\n    out, i, n = [], 0, len(text)\n    while i &lt; n:\n        if text[i].isdigit():\n            j = i\n            while j &lt; n and text[j].isdigit():\n                j += 1\n            run = text[i:j]\n            out.append(run[:6] + &#39;*&#39; * (len(run) - 10) + run[-4:] if len(run) &gt;= 10 else run)\n            i = j\n        else:\n            out.append(text[i])\n            i += 1\n    return &#39;&#39;.join(out)\n\nclass JsonFormatter(logging.Formatter):\n    def format(self, record):\n        payload = {&#39;level&#39;: record.levelname, &#39;event&#39;: mask_digits(record.getMessage())}\n        return json.dumps(payload, ensure_ascii=False)\n\nbuf = io.StringIO()\nh = logging.StreamHandler(buf)\nh.setFormatter(JsonFormatter())\nlog = logging.getLogger(&#39;secure&#39;)\nlog.setLevel(logging.INFO)\nlog.handlers = [h]\nlog.propagate = False\nlog.info(&#39;idcard 110101199003071234 approved&#39;)\nprint(buf.getvalue().strip())", "note": "结构化日志、trace_id 与上下文注入"}]' title='两种写法对照' note='差异集中在 Logger / Handler / Formatter；先看输出，再找背后的规则。' />


## 结构化日志、trace_id 与上下文注入

结构化日志把一行记录做成可解析的 `JSON` 对象——`level`、`msg`、`trace`、`event` 这类字段各自独立——而不是一句自然语言。做法大致三种：在自定义 `Formatter` 里对一条 `dict` 调 `json.dumps`；

用 `extra={'order_id': ...}` 给 `LogRecord` 追加字段；

或写一个 `Filter`，在 `filter(record)` 里 `setattr` 注入字段后返回 `True`。

`trace_id` 要能在异步任务与多个服务之间正确传递，标准库给的是 `contextvars.ContextVar`（Python 3.7 起）：`asyncio` 在 `create_task` 时复制当前上下文，于是在 `logging.Filter` 里用 `trace_id.get()` 取到的就是本次请求的值；

`threading.local` 是线程级的，分不清同一线程里的多个协程，不适合 asyncio。

想让每条记录自出生就带 `trace_id`，可以用 `logging.setLogRecordFactory`（3.2 起）替换记录工厂。

跨服务则靠 W3C Trace Context 的 `traceparent` 头传递，与 OpenTelemetry 的 `trace_id` / `span_id` 对齐，日志和链路追踪才能互相跳转。

字段一旦结构化，「按 `trace_id` 聚合、按 `level` 过滤、按 `event` 计数」就是一次查询，而不是全文 `grep`。

**结构化、采样、脱敏与追踪**

| 机制 | 实现 | 收益 |
| --- | --- | --- |
| JSON 行 | Formatter 里 json.dumps | 按字段检索而非 grep |
| contextvars.ContextVar | 随 asyncio Task 复制 | trace_id 跨协程正确传播 |
| setLogRecordFactory (3.2+) | 记录出生即带字段 | 全局注入 trace_id |
| Filter 采样 | 按 level / trace_id 哈希放行 | 压住循环里的 INFO 洪泛 |
| 掩码 / SecretStr | 保留前 6 后 4、中间打星 | 避免卡号、密钥合规事故 |
| W3C traceparent / OpenTelemetry | 跨服务传 trace_id/span_id | 日志与链路追踪互跳 |

<ConceptDiagram type='layers3' title='第 078 讲 · 分层视角' labels='Logger / Handler / F…|结构化日志、trace_id 与上下文注…|采样、脱敏、性能与并发安全|与 OpenTelemetry 关联' caption='采样、脱敏、性能与并发安全' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 与 OpenTelemetry 关联 落在哪一层。


### trace_id 怎么跨服务串起一次请求

<FlowTimeline :steps='[{"title": "Logger / Handler / Forma…", "desc": "logging 的级别是整数常量：`NOTSET=0`、`DEBUG=10`…", "tone": "blue"}, {"title": "结构化日志、trace_id 与上下文注入", "desc": "结构化日志把一行记录做成可解析的 `JSON` 对象——`level`、`msg`…", "tone": "purple"}, {"title": "采样、脱敏、性能与并发安全", "desc": "采样与分级可以放在 `Filter.filter` 里：返回 `bool` 丢掉生产…", "tone": "orange"}, {"title": "工程落地", "desc": "带 trace_id、采样与脱敏的结构化日志装配", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 采样、脱敏、性能与多进程并发安全

采样与分级可以放在 `Filter.filter` 里：返回 `bool` 丢掉生产环境的 `DEBUG`，或按 `trace_id` 取哈希只保留固定比例，避免循环里刷 `INFO` 把磁盘压垮。

异常要用 `logger.exception()`，且只在 `except` 块内调用，它会自动带上 `exc_info` 堆栈。

脱敏是硬要求：手机号、身份证、卡号、token 默认不该进日志，要在 `Formatter` 或 `Filter` 阶段做掩码（比如保留前 6 后 4、中间打星）；

密钥则用自定义包装类重写 `__str__` / `__repr__`，让它们只返回掩码——Pydantic 的 `SecretStr` 就是现成例子，能避免敏感值被格式化函数取到。

性能上，每个 `Handler` 的 `emit` 都由一把 `threading.RLock` 保护，线程安全；

但多进程共写同一个 `RotatingFileHandler` 时轮转不是进程安全的，正确做法是 `QueueHandler` 配一个独立的 `QueueListener` 进程统一写文件，或换用进程安全的 `concurrent-log-handler`。

日志用 `%s` 这类占位符做惰性格式化，`logger.info('x=%s', val)` 会把字符串拼接推迟到真正需要输出时；

构造昂贵参数前先拿 `isEnabledFor` 包一层更稳妥。

异常路径要 `logger.exception` 带上下文，而不是只打一句 `failed`；

库代码一律不 `print`，统一交给 logger。

<Callout type="warn" title='本讲最容易踩的坑' text='循环里打 INFO、把卡号/密钥写进日志：磁盘被洪泛压垮且制造合规事故，异常只打一句 failed 无上下文' />

```bash
python -c "import logging; logging.basicConfig(level=logging.INFO); logging.info('hello')"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 Logger / Handler / Formatter 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


## 带 trace_id、采样与脱敏的结构化日志装配

线上排障对一条日志有三条要求：能按 `trace_id` 聚合到一次请求、是机器可解析的 `JSON`、且不泄漏敏感值。

做法是先把 `ContextVar` 里当前请求的 `trace_id` 经 `Filter` 注入每条记录，再用一个返回 `bool` 的 `Filter` 丢掉生产环境的 `DEBUG`，最后让自定义 `Formatter` 输出 `JSON` 并对长数字串做掩码。

下面片段装配这套 handler，模拟两个请求共四次调用，最后把输出解析回 `JSON` 验证字段；

`ts` 取自 `LogRecord.created` 时间戳，只出现在结构里、不参与比对，重点看 `trace_id` 切换是否正确，以及 `DEBUG` 是否被采样丢掉。

```python
import logging, io, json, contextvars

trace_id = contextvars.ContextVar('trace_id', default='-')

class TraceFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id.get()
        return record.levelno >= logging.INFO

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({'ts': int(record.created), 'lvl': record.levelname,
                           'trace': record.trace_id, 'msg': record.getMessage()},
                          sort_keys=True)

buf = io.StringIO()
handler = logging.StreamHandler(buf)
handler.setFormatter(JsonFormatter())
handler.addFilter(TraceFilter())
log = logging.getLogger('api')
log.setLevel(logging.DEBUG)
log.handlers = [handler]
log.propagate = False

trace_id.set('req-42')
log.info('request in')
log.debug('cache hit')
log.warning('slow query %d ms', 830)
trace_id.set('req-43')
log.info('request in')
lines = buf.getvalue().strip().splitlines()
print('lines', len(lines))
for line in lines:
    d = json.loads(line)
    print(d['trace'], d['lvl'], d['msg'])
```

<Callout type="idea" title='落地提示' text='统一日志格式、按级别采样、敏感字段默认脱敏，异常必须带上下文而不是只打一句 failed' />

<CheckList id='P078b' title='上线前自检' :items='["能复现并解释「循环里打 INFO、把卡号/密钥写进日志」", "能复现并解释「子 logger 挂 handler 且 propagate…」", "能复现并解释「多进程共写同一个 RotatingFileHandler」", "能用一条命令验证 Logger / Handler / Formatter", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 循环里打 INFO、把卡号/密钥写进日志 | 磁盘被洪泛压垮且制造合规事故，异常只打一句 failed 无上下文 | 按 level 采样、敏感字段默认掩码、logger.exception 在 except 内带堆栈与上下文字段 |
| 子 logger 挂 handler 且 propagate 仍为 True | 记录先经子 handler 再传给 root handler，同一行打印两遍 | 设 logger.propagate = False，或统一只在 root 挂 handler |
| 多进程共写同一个 RotatingFileHandler | 轮转时多个进程同时 rename/切割，日志被覆盖或丢失 | 改 QueueHandler + 单一 QueueListener 进程写文件，或用 concurrent-log-handler 这类进程安全实现 |

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：循环里打 INFO、把卡号/密钥写进日志", "body": "磁盘被洪泛压垮且制造合规事故，异常只打一句 failed 无上下文", "tip": "按 level 采样、敏感字段默认掩码、logger.exception 在 except 内带堆栈与上下文字段"}, {"title": "第 2 步：子 logger 挂 handler 且 p…", "body": "记录先经子 handler 再传给 root handler，同一行打印两遍", "tip": "设 logger.propagate = False，或统一只在 root 挂 handler"}, {"title": "第 3 步：多进程共写同一个 RotatingFileH…", "body": "轮转时多个进程同时 rename/切割，日志被覆盖或丢失", "tip": "改 QueueHandler + 单一 QueueListener 进程写文件，或用 concurrent-log-handler 这类进程安全实现"}]' />


## 练习、自测与一页纸速记

<Exercise title='基础：读出日志级别常量' task='打印 DEBUG/INFO/WARNING/ERROR/CRITICAL 五个整数值，说明 root 默认阈值。' solution='import logging\nprint(&#39;levels&#39;, logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR, logging.CRITICAL)' explain='五个级别分别是 10/20/30/40/50；root 默认 WARNING=30，故未设 level 的子 logger 里 INFO 不会输出。' />

<Exercise title='进阶：用自定义 Formatter 输出定长格式' task='给 StreamHandler 装 &#39;级别:消息&#39; Formatter，写一条 WARNING 并用 repr 打印捕获内容。' solution='import logging, io\nbuf = io.StringIO()\nh = logging.StreamHandler(buf)\nh.setFormatter(logging.Formatter(&#39;%(levelname)s:%(message)s&#39;))\nlog = logging.getLogger(&#39;x&#39;)\nlog.setLevel(logging.INFO)\nlog.handlers = [h]\nlog.propagate = False\nlog.warning(&#39;low %d&#39;, 3)\nprint(repr(buf.getvalue().strip()))' explain='Formatter 用 %(levelname)s/%(message)s 取记录字段，%-style 惰性格式化把 3 拼进消息；propagate=False 避免重复输出。' />

<Quiz no='078-1' q='子 logger app.db 未设 level、root 设 WARNING，其 getEffectiveLevel() 是？' :options='["30", "20", "0", "10"]' answer="0" explain='未设 level 的 logger 沿祖先上溯取第一个非 NOTSET 的级别；root 默认 WARNING=30，因此 INFO(20) 被丢弃、WARNING(30) 才输出。' />

<Quiz no='078-2' q='关于 trace_id 跨异步任务传播，正确的是？' :options='["用 contextvars.ContextVar，它在 create_task 时随 context 复制进 Task", "用 threading.local 即可", "只能写进全局变量", "必须每次手动传参给 logger"]' answer="0" explain='asyncio 在 create_task 时复制当前 context，ContextVar 的值随 Task 走；threading.local 是线程级，无法区分同一线程里的多个协程，故日志关联要用 ContextVar + Filter。' />

<Quiz no='078-3' q='多进程共写同一个 RotatingFileHandler 的风险是？' :options='["轮转时多进程同时切割文件，日志覆盖或丢失", "级别自动被改成 DEBUG", "JSON 格式失效", "trace_id 无法注入"]' answer="0" explain='Handler 的 RLock 只保证单进程内线程安全，跨进程轮转没有协调；应改 QueueHandler + 单一 QueueListener 写者或进程安全实现。' />

<Predict no='078-4' q='logging.getLevelName(30) 的输出是？' :options='["WARNING", "INFO", "30"]' answer='0' output='WARNING' explain='级别常量里 WARNING=30，getLevelName 把数值映射回名称；NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL 对应 0/10/20/30/40/50。' />

<FillBlank no='078-5' tpl='___ logging, io, json, contextvars' :answers='["import"]' hint='回想本讲关于 Logger / Handler / Formatter 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Logger / Handler / Formatter 与级别传播 的落点。' />

<KnowledgeCard :points='["级别 NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL = 0/10/20/30/40/50，root 默认 WARNING", "Logger 按点分层级，propagate=True 会把记录传给祖先；子与 root 都挂 handler 会重复输出", "结构化日志用 JSON Formatter + extra/Filter 字段；trace_id 用 contextvars.ContextVar 跨协程传播", "logging.setLogRecordFactory（3.2+）让每条记录出生带 trace_id；W3C traceparent 对齐 OpenTelemetry", "采样用 Filter.filter 返回 bool、脱敏在 Formatter/Filter 做掩码、logger.exception 带 exc_info", "Handler 用 RLock 保证线程安全，但多进程轮转不安全；改 QueueHandler + QueueListener 单写者"]' :pitfalls='["循环里打 INFO、把卡号/密钥写进日志", "子 logger 挂 handler 且 propagate 仍为 True", "多进程共写同一个 RotatingFileHandler", "在循环里打 INFO、把密钥或身份证写进日志，既压垮磁盘又制造合规事故"]' summary='日志是给机器检索的数据，不是给人看的散文；结构化字段加 trace_id 才能把一次请求跨服务串起来' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 级别 NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL = 0/10/20/30/40/50，root 默认 WARNING | 建立直觉 |
| Logger 按点分层级，propagate=True 会把记录传给祖先；子与 root 都挂 handler 会重复输出 | 跑通示例 |
| 结构化日志用 JSON Formatter + extra/Filter 字段；trace_id 用 contextvars.ContextVar 跨协程传播 | 深入边界 |
| logging.setLogRecordFactory（3.2+）让每条记录出生带 trace_id；W3C traceparent 对齐 OpenTelemetry | 工程落地 |
| 采样用 Filter.filter 返回 bool、脱敏在 Formatter/Filter 做掩码、logger.exception 带 exc_info | 随堂检测 |
| Handler 用 RLock 保证线程安全，但多进程轮转不安全；改 QueueHandler + QueueListener 单写者 | 复盘 |

1. 级别 NOTSET/DEBUG/INFO/WARNING/ERROR/CRITICAL = 0/10/20/30/40/50，root 默认 WARNING

2. Logger 按点分层级，propagate=True 会把记录传给祖先；子与 root 都挂 handler 会重复输出

3. 结构化日志用 JSON Formatter + extra/Filter 字段；trace_id 用 contextvars.ContextVar 跨协程传播

[下一讲：配置管理：环境变量、.env 与配置中心](/engineering/config)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/078-logging.py`

```bash
python3 examples/lessons/078-logging.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/078-logging.py) · [全部示例代码索引](/examples/)
