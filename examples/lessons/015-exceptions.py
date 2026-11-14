"""
第 015 讲 · 异常：捕获、异常链与自定义异常
与教程正文一一对应的示例代码

课程页面：/foundation/exceptions
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/015-exceptions.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/015-exceptions.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# 9090 8080
# ConfigError ('port', 'not an integer') port
# ValueError True
# False False

class ConfigError(Exception):
    def __init__(self, key, reason):
        super().__init__(key, reason)
        self.key = key

def read_port(cfg):
    try:
        return int(cfg['port'])
    except KeyError:
        return 8080
    except ValueError as e:
        raise ConfigError('port', 'not an integer') from e

print(read_port({'port': '9090'}), read_port({}))
try:
    read_port({'port': 'abc'})
except ConfigError as e:
    print(type(e).__name__, e.args, e.key)
    print(type(e.__cause__).__name__, e.__suppress_context__)
print(issubclass(KeyboardInterrupt, Exception), issubclass(SystemExit, Exception))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# from-finally from-finally
# 6 bad ['done', 'done']

def swallow(flag):
    try:
        if flag:
            return 'from-try'
        raise ZeroDivisionError
    except ZeroDivisionError:
        return 'from-except'
    finally:
        return 'from-finally'

def clean(flag):
    try:
        value = int(flag)
    except ValueError:
        return 'bad'
    else:
        return value * 2
    finally:
        log.append('done')

log = []
print(swallow(True), swallow(False))
print(clean('3'), clean('x'), log)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# ValueError True
# capture
# ValueError None False
# has exceptiontable True
# SETUP_FINALLY False

import sys, dis

def capture():
    try:
        return int('x')
    except ValueError:
        return sys.exc_info()

t, v, tb = capture()
print(t.__name__, isinstance(v, ValueError))
print(tb.tb_frame.f_code.co_name)

def implicit():
    try:
        int('y')
    except ValueError:
        raise KeyError('second')

try:
    implicit()
except KeyError as e:
    print(type(e.__context__).__name__, e.__cause__, e.__suppress_context__)

print('has exceptiontable', len(capture.__code__.co_exceptiontable) > 0)
print('SETUP_FINALLY', 'SETUP_FINALLY' in dis.Bytecode(capture).dis())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import json, logging, os, tempfile

logging.basicConfig(level=logging.ERROR, format='%(levelname)s %(message)s')

class ConfigError(Exception):
    def __init__(self, key, reason):
        super().__init__(key, reason)
        self.key = key

def parse_config(path):
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    try:
        port = int(raw['port'])
        timeout = float(raw['timeout'])
    except KeyError as e:
        raise ConfigError(e.args[0], 'missing key') from e
    except ValueError as e:
        raise ConfigError('port/timeout', 'not numeric') from e
    if not (0 < port < 65536):
        raise ConfigError('port', 'out of range')
    return {'port': port, 'timeout': timeout}

DEFAULTS = {'port': 8080, 'timeout': 3.0}

def load_or_default(path):
    try:
        return parse_config(path)
    except (ConfigError, OSError) as e:
        logging.error('config fallback key=%s cause=%s', getattr(e, 'key', '-'), getattr(e, '__cause__', None))
        return dict(DEFAULTS)

p = os.path.join(tempfile.gettempdir(), 'depth15.json')
with open(p, 'w', encoding='utf-8') as f:
    json.dump({'port': 'abc', 'timeout': '2.5'}, f)
print(load_or_default(p))
os.remove(p)
