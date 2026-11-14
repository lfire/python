"""
第 079 讲 · 配置管理：环境变量、.env 与配置中心
与教程正文一一对应的示例代码

课程页面：/engineering/config
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/079-config.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/079-config.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# port 9100 debug True host prod
# env var prod
# bool trap True

import os

def parse_bool(v):
    return v.strip().lower() in ('1', 'true', 'yes', 'on')

def load(env, dotenv_text='', overrides=None):
    cfg = {'PORT': '8000', 'DEBUG': 'false', 'DB_HOST': 'localhost'}
    for line in dotenv_text.splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            cfg[k.strip()] = v.strip()
    for k in list(cfg):
        if k in env:
            cfg[k] = env[k]
    if overrides:
        cfg.update(overrides)
    return {'port': int(cfg['PORT']), 'debug': parse_bool(cfg['DEBUG']),
            'host': cfg['DB_HOST']}

env = {'PORT': '9100'}
dotenv = 'PORT=9000' + chr(10) + 'DEBUG=true' + chr(10)
c = load(env, dotenv, overrides={'DB_HOST': 'prod'})
print('port', c['port'], 'debug', c['debug'], 'host', c['host'])
os.environ['APP_MODE'] = 'prod'
print('env var', os.environ['APP_MODE'])
del os.environ['APP_MODE']
print('bool trap', bool('false'))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# valid port 8080
# startup fails fast PORT must be an integer
# log-safe *** real sk-live-abc123

class Secret:
    def __init__(self, value):
        self._value = value
    def reveal(self):
        return self._value
    def __str__(self):
        return '***'
    __repr__ = __str__

def load_port(env):
    raw = env.get('PORT', '8000')
    if not raw.isdigit():
        raise ValueError('PORT must be an integer')
    return int(raw)

print('valid port', load_port({'PORT': '8080'}))
try:
    load_port({'PORT': 'eighty'})
except ValueError as e:
    print('startup fails fast', str(e))
token = Secret('sk-live-abc123')
print('log-safe', str(token), 'real', token.reveal())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# env value type str
# naive bool True
# correct bool False
# toml types bool int
# argv count 1

import os, sys, tomllib

os.environ['DEMO_FLAG'] = 'False'
print('env value type', type(os.environ['DEMO_FLAG']).__name__)
print('naive bool', bool(os.environ['DEMO_FLAG']))
print('correct bool', os.environ['DEMO_FLAG'].lower() == 'true')
cfg = tomllib.loads('debug = false' + chr(10) + 'port = 8080' + chr(10))
print('toml types', type(cfg['debug']).__name__, type(cfg['port']).__name__)
print('argv count', len(sys.argv))
del os.environ['DEMO_FLAG']

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import json

DEFAULTS = {'PORT': '8000', 'DEBUG': 'false', 'WORKERS': '4'}

def coerce_bool(v):
    return v.strip().lower() in ('1', 'true', 'yes', 'on')

class Config:
    def __init__(self, env, dotenv=None, overrides=None):
        merged = dict(DEFAULTS)
        if dotenv:
            merged.update(dotenv)
        merged.update({k: v for k, v in env.items() if k in merged})
        if overrides:
            merged.update(overrides)
        self.port = int(merged['PORT'])
        self.debug = coerce_bool(merged['DEBUG'])
        self.workers = int(merged['WORKERS'])
        if self.port < 1 or self.port > 65535:
            raise ValueError('PORT out of range')
    def public(self):
        return {'port': self.port, 'debug': self.debug, 'workers': self.workers}

env = {'PORT': '9200'}
dotenv = {'DEBUG': 'true'}
cfg = Config(env, dotenv, overrides={'WORKERS': '8'})
print('config', json.dumps(cfg.public(), sort_keys=True))
try:
    Config({'PORT': '70000'})
except ValueError as e:
    print('startup rejected', str(e))
print('secret never in public', 'SECRET' not in cfg.public())
