"""
第 078 讲 · 日志：logging、结构化日志与追踪关联
与教程正文一一对应的示例代码

课程页面：/engineering/logging
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/078-logging.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/078-logging.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# INFO shop.order t-123 order created A100
# WARNING shop.order t-123 stock low 3
# ERROR shop.order t-456 payment failed card-xxxx

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

# ======================== 2. 对照写法 ========================
# 预期输出：
# {"level": "INFO", "event": "idcard 110101********1234 approved"}

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

# ======================== 3. 原理验证 ========================
# 预期输出：
# getEffectiveLevel 30
# getLevelName(30) WARNING
# lastResort level 30
# captured 'ROOT WARNING app.db'
# isEnabledFor(INFO) False
# Filter.filter sig (self, record)

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

# ======================== 4. 工程案例 ========================

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
