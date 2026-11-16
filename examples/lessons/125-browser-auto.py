"""
第 125 讲 · 实战 04 · Selenium 表单自动化与定时任务
与教程正文一一对应的示例代码

课程页面：/projects/browser-auto
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/125-browser-auto.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/125-browser-auto.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# explicit early ('found', 3)
# explicit late ('found', 9)
# explicit never ('timeout', 4)
# fixed on early (True, 10)
# fixed on late (False, 2)

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

# ======================== 2. 对照写法 ========================
# 预期输出：
# rate gate False True
# backoff ticks [1, 2, 4, 8]
# credential injected True

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

# ======================== 3. 原理验证 ========================
# 预期输出：
# found at 3 3
# found at 9 9
# timeout at 99 -1
# has jump backward True

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

# ======================== 4. 工程案例 ========================

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
