"""
第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频
与教程正文一一对应的示例代码

课程页面：/projects/office-docs
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/124-office-docs.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/124-office-docs.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# rendered Hi Zhang, your 6 bill is 128.50 CNY.
# multipart multipart/alternative
# html part text/html
# subject encoded True
# send enabled True
# send disabled False
# pdf accept
# exe reject type
# big reject size

import os
from email.message import EmailMessage
from email import policy
from string import Template

tpl = Template('Hi ${name}, your ${month} bill is ${amount} CNY.')
body = tpl.substitute(name='Zhang', month='6', amount='128.50')
msg = EmailMessage(policy=policy.SMTP)
msg['Subject'] = '账单通知'
msg['From'] = 'billing@example.com'
msg['To'] = 'user@example.com'
msg.set_content(body)
msg.add_alternative('<p>bill 128.50 CNY</p>', subtype='html')

def check_attachment(name, data, allowed, max_bytes):
    ext = '.' + name.rsplit('.', 1)[-1].lower()
    if ext not in allowed:
        return 'reject type'
    if len(data) > max_bytes:
        return 'reject size'
    return 'accept'

def send_enabled():
    return bool(os.environ.get('SMTP_APP_PASSWORD'))

print('rendered', body)
print('multipart', msg.get_content_type())
print('html part', msg.get_payload()[1].get_content_type())
print('subject encoded', b'=?utf-8?' in msg.as_bytes())
os.environ['SMTP_APP_PASSWORD'] = 'token'
print('send enabled', send_enabled())
os.environ.pop('SMTP_APP_PASSWORD', None)
print('send disabled', send_enabled())
print('pdf', check_attachment('bill.pdf', b'x' * 100, {'.pdf'}, 1024))
print('exe', check_attachment('setup.exe', b'x', {'.pdf'}, 1024))
print('big', check_attachment('big.pdf', b'x' * 2048, {'.pdf'}, 1024))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# substitute missing KeyError 'amount'
# safe substitute Hi Zhang, amount ${amount}
# naive concat Hi Zhang, amount ${amount}

from string import Template

tpl = Template('Hi ${name}, amount ${amount}')
try:
    tpl.substitute(name='Zhang')
except KeyError as e:
    print('substitute missing', type(e).__name__, str(e))
print('safe substitute', tpl.safe_substitute(name='Zhang'))
print('naive concat', 'Hi ' + 'Zhang' + ', amount ' + '${amount}')

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# parsed type multipart/alternative
# parts ['text/plain', 'text/html']
# subject roundtrip Test
# crlf present True

from email import policy
from email.message import EmailMessage
from email.parser import BytesParser

msg = EmailMessage(policy=policy.SMTP)
msg['Subject'] = 'Test'
msg['From'] = 'a@b.com'
msg['To'] = 'c@d.com'
msg.set_content('plain text')
msg.add_alternative('<p>html</p>', subtype='html')
raw = msg.as_bytes()
parsed = BytesParser(policy=policy.default).parsebytes(raw)
print('parsed type', parsed.get_content_type())
parts = [p.get_content_type() for p in parsed.iter_parts()]
print('parts', parts)
print('subject roundtrip', str(parsed['Subject']))
print('crlf present', bytes([13, 10]) in raw)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

from email.message import EmailMessage
from email import policy
from string import Template

ALLOWED = {'.pdf'}
MAX_BYTES = 1024

def render(tpl, row):
    return Template(tpl).substitute(**row)

def check(name, data):
    ext = '.' + name.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED:
        return 'type'
    if len(data) > MAX_BYTES:
        return 'size'
    return ''

def build(row):
    msg = EmailMessage(policy=policy.SMTP)
    msg['Subject'] = 'Bill'
    msg['From'] = 'billing@example.com'
    msg['To'] = row['email']
    msg.set_content(render('Hi ${name}, ${amount} CNY', row))
    return msg

def run(rows, limit):
    sent, failed = [], []
    for i, row in enumerate(rows):
        if i >= limit:
            failed.append((row['email'], 'rate limit'))
            continue
        reason = check(row['file'], row['data'])
        if reason:
            failed.append((row['email'], reason))
            continue
        sent.append(str(build(row)['To']))
    return sent, failed

rows = [
    {'name': 'A', 'amount': '10', 'email': 'a@x.com', 'file': 'a.pdf', 'data': b'x'},
    {'name': 'B', 'amount': '20', 'email': 'b@x.com', 'file': 'b.exe', 'data': b'x'},
    {'name': 'C', 'amount': '30', 'email': 'c@x.com', 'file': 'c.pdf', 'data': b'x' * 2048},
]
sent, failed = run(rows, limit=2)
print('sent', sent)
print('failed', failed)
