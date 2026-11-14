"""
第 110 讲 · 容器化与 Kubernetes 部署
与教程正文一一对应的示例代码

课程页面：/distributed/docker-k8s
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/110-docker-k8s.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/110-docker-k8s.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# stopping_before False
# stopping_after True
# inflight_after_drain 0

import signal, os

class Server:
    def __init__(self):
        self.stopping = False
        self.inflight = 3
    def handle_term(self, signum, frame):
        self.stopping = True
    def drain(self):
        while self.inflight > 0:
            self.inflight -= 1

s = Server()
signal.signal(signal.SIGTERM, s.handle_term)
print('stopping_before', s.stopping)
os.kill(os.getpid(), signal.SIGTERM)
print('stopping_after', s.stopping)
s.drain()
print('inflight_after_drain', s.inflight)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# readiness_ok True
# readiness_db_down False
# liveness_still_ok True

class Probe:
    def __init__(self):
        self.db_ok = True
    def readiness(self):
        return self.db_ok
    def liveness(self):
        return True
p = Probe()
print('readiness_ok', p.readiness())
p.db_ok = False
print('readiness_db_down', p.readiness())
print('liveness_still_ok', p.liveness())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# cpu_250m_cores 0.25
# mem_512Mi_bytes 536870912
# burst_200m_x4 1200

def millicores(m):
    return m / 1000
def mebibytes(mi):
    return mi * 1024 * 1024
def burst(request, limit, replicas):
    return (limit - request) * replicas

print('cpu_250m_cores', millicores(250))
print('mem_512Mi_bytes', mebibytes(512))
print('burst_200m_x4', burst(200, 500, 4))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import signal, threading, time

class App:
    def __init__(self):
        self.ready = False
        self.stopping = False
        self.inflight = 0
        self.lock = threading.Lock()
    def on_term(self, signum, frame):
        self.stopping = True
        self.ready = False
    def readiness(self):
        return self.ready and not self.stopping
    def liveness(self):
        return True
    def handle(self, i):
        with self.lock:
            if self.stopping:
                return 'rejected'
            self.inflight += 1
        time.sleep(0.001)
        with self.lock:
            self.inflight -= 1
        return 'ok'
    def drain(self, timeout=5):
        end = time.monotonic() + timeout
        while self.inflight > 0 and time.monotonic() < end:
            time.sleep(0.01)
        return self.inflight

app = App()
app.ready = True
signal.signal(signal.SIGTERM, app.on_term)
print('ready', app.readiness(), 'live', app.liveness())
print('req', app.handle(1))
app.on_term(signal.SIGTERM, None)
print('ready_after_term', app.readiness())
print('left_after_drain', app.drain())
