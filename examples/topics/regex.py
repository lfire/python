"""正则表达式 re：从字符类到回溯 —— 专题补遗可运行示例。

课程页：/topics/regex
GitHub：https://github.com/lfire/python/blob/main/examples/topics/regex.py
依赖：标准库 re、time；最后一节的超时示例需要可选第三方库 regex（pip install regex），
      未安装时会自动跳过并给出提示，不影响整文件运行。
运行：python3 examples/topics/regex.py
说明：本文件按专题正文出现的顺序，把 tools/course/topics/regex.md 中的全部 python
      代码块整理到一个脚本里；每段前的方括号标明对应章节与演示内容。
"""

import re
import time

# [1. 字符类与预定义类] 用字符类、预定义类与取反类抽取订单里的字段
line = "订单 A-1392 金额 88.50 元，编号 b_007 作废"
print(re.findall(r"[A-Z]-\d+", line))        # ['A-1392']
print(re.findall(r"\d+\.\d+", line))         # ['88.50']
print(re.findall(r"\b[a-z]_\d+\b", line))    # ['b_007']
print(re.findall(r"[^0-9.\s]+", "88.50 元"))  # ['元']

# [2. 量词与贪婪] 对比贪婪、懒惰与取反字符类三种写法的匹配结果
s = 'name="alice" age="30" city="x"'
print(re.findall(r'"(.*)"', s))     # ['alice" age="30" city="x']
print(re.findall(r'"(.*?)"', s))    # ['alice', '30', 'x']
print(re.findall(r'"([^"]*)"', s))  # ['alice', '30', 'x']

# [3. 分组、命名捕获与反向引用] 用 groupdict() 把命中结果变成字典
# (?P=quote) 要求收尾引号与起始引号一致，避免跨字段误配
pat = re.compile(r'(?P<key>\w+)=(?P<quote>["\'])(?P<value>.*?)(?P=quote)')
text = 'user="alice" role="admin" level="3"'
for m in pat.finditer(text):
    print(m.groupdict(), m.span())
# {'key': 'user', 'quote': '"', 'value': 'alice'} (0, 12)
# {'key': 'role', 'quote': '"', 'value': 'admin'} (13, 25)
# {'key': 'level', 'quote': '"', 'value': '3'} (26, 35)

# [4. 零宽断言与锚点] 叠加前瞻校验密码、在间隙插逗号、带条件提取价格
# 1) 密码复杂度：多个前瞻从同一位置分别检查，互不消费字符
pwd = re.compile(r'(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[\w!@#]{8,}\Z')
print([bool(pwd.match(s)) for s in ("abc12345", "Abc12345", "Abc1!xyz")])
# [False, True, True]

# 2) 千分位：只在左边是数字、右边剩 3 的倍数个数字的间隙插入逗号
print(re.sub(r'(?<=\d)(?=(\d{3})+\b)', ',', '1234567890'))
# 1,234,567,890

# 3) 前瞻取价格，但不把单位带进结果
print(re.findall(r'\d+\.\d{2}(?= 元)', '小计 88.50 元，共 128.00 元'))
# ['88.50', '128.00']

# [5. re 模块六个 API 的分工] match/search/findall/finditer/sub/compile 的返回差异
log = "WARN 2026-11-13 disk=91% host=db-2"
print(re.match(r'WARN', log) is not None)        # True
print(re.match(r'disk', log) is not None)        # False
print(re.search(r'disk=(\d+)%', log).group(1))   # 91
print(re.findall(r'(\w+)=(\S+)', log))           # [('disk', '91%'), ('host', 'db-2')]
print([(m.group(), m.span()) for m in re.finditer(r'\d+%', log)])
# [('91%', (21, 24))]
print(re.sub(r'(?P<k>\w+)=(?P<v>\S+)', r'\g<k>:\g<v>', log))
# WARN 2026-11-13 disk:91% host:db-2
pat = re.compile(r'\b[A-Z]{3,}\b')
print(pat.findall(log))                          # ['WARN']

# [6. 回溯与灾难性匹配] 嵌套量词 (a+)+ 面对失败输入时耗时呈指数增长
bad = re.compile(r'(a+)+$')
for n in (10, 14, 18, 22):
    s = 'a' * n + 'b'          # 末尾的 b 让整体必然失败，逼出全部回溯
    t = time.perf_counter()
    bad.search(s)
    print(n, round(time.perf_counter() - t, 4))
# 10 0.0001
# 14 0.002
# 18 0.028
# 22 0.28   ← 长度每 +4，耗时约翻十几倍（示意，数值随机器变化）

# [7. 用占有量词与原子组锁死回退] 原子组与占有量词把同样输入压回线性时间
evil = 'a' * 20 + 'b'
for label, pat in (("嵌套量词", r'(a+)+$'), ("原子组", r'(?>a+)+$'), ("占有量词", r'a++$')):
    t = time.perf_counter()
    re.search(pat, evil)
    print(label, round(time.perf_counter() - t, 4))
# 嵌套量词 0.06xx   ← 示意：呈指数增长，长度再往上会迅速失控
# 原子组 0.0
# 占有量词 0.0

# [8. 正则与字符串方法] 固定分隔符用 split，可变空白与任意空白才交给正则
row = "  alice , 30 ,  admin  "
print([c.strip() for c in row.split(',')])       # ['alice', '30', 'admin']
print(re.split(r'\s*,\s*', row.strip()))         # ['alice', '30', 'admin']
print(re.findall(r'\S+', "a   b\tc\nd"))         # ['a', 'b', 'c', 'd']

# [9. 日志、表单与数据清洗的常用模式] 命名组解析日志、中间四位脱敏、折叠空白
# 应用日志：时间、级别、消息、耗时，长模式按字段分段拼接更可读
LINE = (r'(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) '
        r'\[(?P<level>\w+)\] (?P<msg>.*?) '
        r'cost=(?P<cost>\d+)ms')
pat = re.compile(LINE)
rows = [
    "2026-11-13 09:12:03 [INFO] GET /api/user cost=18ms",
    "2026-11-13 09:12:05 [WARN] GET /api/order cost=240ms",
]
for line in rows:
    m = pat.match(line)
    print(m.group('level'), m.group('msg'), m.groupdict()['cost'])
# INFO GET /api/user 18
# WARN GET /api/order 240
# 手机号中间四位脱敏，保留前 3 后 4
print(re.sub(r'(?<=\d{3})\d{4}(?=\d{4})', '****', '联系 13812345678'))
# 联系 138****5678
# 折叠任意空白，清洗表单输入
print(re.sub(r'\s+', ' ', '  张\t三 \n 备注  ').strip())
# 张 三 备注

# [10. 可维护性：命名组、re.VERBOSE 与超时] 用 re.VERBOSE 写带注释的长模式
PHONE = re.compile(r'''
    \A                 # 从整串开头
    1[3-9]             # 号段：1 开头，第二位 3 到 9
    \d{9}              # 后 9 位
    \Z                 # 到整串结尾
''', re.VERBOSE | re.ASCII)
for s in ("13812345678", "12812345678", "1381234567", "138123456789"):
    print(s, bool(PHONE.fullmatch(s)))
# 13812345678 True
# 12812345678 False
# 1381234567 False
# 138123456789 False

# [10. 可维护性：命名组、re.VERBOSE 与超时] 第三方 regex 库的 timeout 兜底（可选依赖）
# 本示例文件与第三方库同名，import 会命中自身并重跑全文；导入前临时移开脚本目录，
# 让 import 回到已安装的第三方库，未安装时则正常触发 ImportError 跳过。
import os as _os
import sys as _sys
_self_dir = _os.path.dirname(_os.path.abspath(__file__))
_saved_path = _sys.path[:]
_sys.path[:] = [p for p in _sys.path if _os.path.abspath(p or ".") != _self_dir]
try:
    import regex
except ImportError:
    print("跳过：需要 pip install regex")
else:
    # 交替分支 + 嵌套量词会枚举指数种划分，用 timeout（秒）兜底
    try:
        regex.search(r'(a|aa)+$', 'a' * 30 + 'b', timeout=0.2)
        print('匹配结束')
    except TimeoutError:
        print('超时，已放弃该输入')
    # 超时，已放弃该输入
finally:
    _sys.path[:] = _saved_path

# [练习 1 · 参考解] 用命名组解析 nginx combined 日志
LINE = (r'(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
        r'"(?P<method>GET|POST|PUT|DELETE) (?P<path>\S+) [^"]+" '
        r'(?P<status>\d{3}) (?P<bytes>\d+|-)')
log = '10.0.0.7 - - [13/Nov/2026:09:12:03 +0800] "GET /api/user?id=7 HTTP/1.1" 200 1532'
m = re.match(LINE, log)
print(m.groupdict())
# {'ip': '10.0.0.7', 'time': '13/Nov/2026:09:12:03 +0800',
#  'method': 'GET', 'path': '/api/user?id=7', 'status': '200', 'bytes': '1532'}
print(m.group('status'), m.group('bytes'))  # 200 1532

# [练习 2 · 参考解] 用正反例证明 (a+)+ 与 a+ 对正常输入判定一致
danger = re.compile(r'(a+)+')
safe = re.compile(r'a+')
cases = ["a", "aaaa", "aaaab", "", "baaa"]
print([bool(danger.fullmatch(s)) for s in cases])
# [True, True, False, False, False]
print([bool(safe.fullmatch(s)) for s in cases])
# [True, True, False, False, False]
print([bool(danger.fullmatch(s)) == bool(safe.fullmatch(s)) for s in cases])
# [True, True, True, True, True]
# danger 的外层 + 把同一串 a 切成若干段，段与段之间有多种划分，
# 失败输入要把这些划分全试一遍；safe 只有一次 a+，没有可回退的分段点。
