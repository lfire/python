---
title: 第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频
description: 串起办公文档的全套自动化流水线
---

<StageHeader stage='L12 · 工程实战' level='★★★☆☆' time='55 分钟' goal='串起办公文档的全套自动化流水线' prereq='第 123 讲 · 实战 02 · 文件检索、日志与自动化办公' />

# 第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频

上一讲把本地文件整理成可回退的流程；这一讲把「磁盘里的字节」换成「要发给人的文档」，多了收件人这一层。办公文档流水线有一条朴素的主线：模板留住不变的部分，代码只填变化字段。

运营给两千名客户发账单，授权码写死在源码、随一次提交进了公开仓库；正文用字符串拼 `HTML`，姓名里的 `&` 截断了标签；附件没校验，一个改了后缀的大文件把整批拖住。我们先用 `EmailMessage` 构造合规的 `MIME`、用 `string.Template` 把模板与数据分开，再扩到 `pypdf`、`openpyxl` 等库的批处理，最后补附件白名单与失败清单。用到的基础是文件读写与字符串模板；学完能把一份数据渲染成邮件与表格。


## 两千封账单要在十分钟内发完，还不能发错附件

运营要给两千名客户发月度账单邮件，脚本把 `SMTP` 授权码直接写死在源码里，一次提交把凭证带进了公开仓库；正文用字符串拼 `HTML`，某个客户姓名里带 `&`，渲染出的标签被截断，还有几封把 `${amount}` 占位符原样发了出去。

更要命的是附件没做校验，一个 30MB 的 `.exe` 被当成账单塞进队列，`SMTP` 服务器直接拒收整批。朴素解法「拼 `HTML` + 硬编码密码 + 循环 `sendmail`」失败在三处：凭证随代码泄漏、模板与数据混在一起导致内容错乱、批量发送没有类型与大小校验及限速。

这一讲用标准库 `email.message.EmailMessage` 构造合规的 `MIME` 邮件、用 `string.Template` 做模板渲染、用环境变量注入凭证，并把附件白名单、大小上限、限速与失败清单做成一条可运行的最小流水线。

<Callout type="tip" title='核心心智模型' text='`email.message.EmailMessage` 自 3.6 起提供现代 API，构造时传 `policy=policy.SMTP` 会用 `CRLF` 作行分隔（`policy.default` 用 LF，发送场景要前者）。`msg.set_content(text)` 自动设 `Cont' />


## MIME 与 EmailMessage：把邮件构造交给协议实现

`email.message.EmailMessage` 自 3.6 起提供现代 API，构造时传 `policy=policy.SMTP` 会用 `CRLF` 作行分隔（`policy.default` 用 LF，发送场景要前者）。

`msg.set_content(text)` 自动设 `Content-Type` 为 `text/plain` 并按内容挑 `Content-Transfer-Encoding`（文本通常 quoted-printable），`msg.add_alternative` 会把容器升级成 `multipart/alternative` 并追加 `text/html` part；

再调用 `add_attachment` 则进一步变成 `multipart/mixed` 用于附件。

非 `ASCII` 头字段（如中文 Subject）在 `msg.as_bytes()` 序列化时才按 RFC 2047 编码成 `=?utf-8?b?...?=`，因为 `SMTP` 头只允许 `ASCII`；

直接读 `msg['Subject']` 得到的是原始 `str`，这一点常被误判。

回解析用 `email.parser.BytesParser(policy=policy.default).parsebytes(raw)`，`iter_parts()` 可遍历各 part 的 `get_content_type()`。

发送侧用 `smtplib.SMTP_SSL(host, 465)` 或 `SMTP(host, 587)` 加 `starttls(context=ssl.create_default_context())`，最后 `send_message(msg)` 由库负责 `DATA` 命令、点号转义与 `CRLF`；

手工拼字符串既容易破坏转义，也会残留 `${...}` 占位符，还可能把用户输入拼进 `HTML` 造成内容错乱甚至 XSS。

**邮件构造 API 与 MIME 结构**

| API | 产生的结构 / 头 | 默认值 / 注意 |
| --- | --- | --- |
| EmailMessage(policy=policy.SMTP) | 行分隔 CRLF | policy.default 用 LF，发送用前者 |
| set_content(text) | text/plain part | 自动选 quoted-printable 等传输编码 |
| add_alternative(html, subtype='html') | 容器升为 multipart/alternative | HTML part 放最后，客户端优先渲染 |
| add_attachment(maintype, subtype, data) | 容器升为 multipart/mixed | 附件用 base64 编码 |
| as_bytes() / as_string() | 序列化为线路字节 | 此时才把中文头编码成 =?utf-8?b?...?= |
| BytesParser(policy=...).parsebytes(raw) | 回解析为消息树 | iter_parts() 遍历各 part |

```python
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
```

<OutputBox title='主示例运行结果' output='rendered Hi Zhang, your 6 bill is 128.50 CNY.\nmultipart multipart/alternative\nhtml part text/html\nsubject encoded True\nsend enabled True\nsend disabled False\npdf accept\nexe reject type\nbig reject size' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import os\nfrom email.message import EmailMessage\nfrom email import policy\nfrom string import Template\n\ntpl = Template(&#39;Hi ${name}, your ${month} bill is ${amount} CNY.&#39;)\nbody = tpl.substitute(name=&#39;Zhang&#39;, month=&#39;6&#39;, amount=&#39;128.50&#39;)\nmsg = EmailMessage(policy=policy.SMTP)\nmsg[&#39;Subject&#39;] = &#39;账单通知&#39;\nmsg[&#39;From&#39;] = &#39;billing@example.com&#39;\nmsg[&#39;To&#39;] = &#39;user@example.com&#39;\nmsg.set_content(body)\nmsg.add_alternative(&#39;&lt;p&gt;bill 128.50 CNY&lt;/p&gt;&#39;, subtype=&#39;html&#39;)\n\ndef check_attachment(name, data, allowed, max_bytes):\n    ext = &#39;.&#39; + name.rsplit(&#39;.&#39;, 1)[-1].lower()\n    if ext not in allowed:\n        return &#39;reject type&#39;\n    if len(data) &gt; max_bytes:\n        return &#39;reject size&#39;\n    return &#39;accept&#39;\n\ndef send_enabled():\n    return bool(os.environ.get(&#39;SMTP_APP_PASSWORD&#39;))\n\nprint(&#39;rendered&#39;, body)\nprint(&#39;multipart&#39;, msg.get_content_type())\nprint(&#39;html part&#39;, msg.get_payload()[1].get_content_type())\nprint(&#39;subject encoded&#39;, b&#39;=?utf-8?&#39; in msg.as_bytes())\nos.environ[&#39;SMTP_APP_PASSWORD&#39;] = &#39;token&#39;\nprint(&#39;send enabled&#39;, send_enabled())\nos.environ.pop(&#39;SMTP_APP_PASSWORD&#39;, None)\nprint(&#39;send disabled&#39;, send_enabled())\nprint(&#39;pdf&#39;, check_attachment(&#39;bill.pdf&#39;, b&#39;x&#39; * 100, {&#39;.pdf&#39;}, 1024))\nprint(&#39;exe&#39;, check_attachment(&#39;setup.exe&#39;, b&#39;x&#39;, {&#39;.pdf&#39;}, 1024))\nprint(&#39;big&#39;, check_attachment(&#39;big.pdf&#39;, b&#39;x&#39; * 2048, {&#39;.pdf&#39;}, 1024))' :notes='["导入 os，凭证只从环境变量读，不写进源码", "取 EmailMessage（3.6 起）构造现代 MIME 邮件", "policy.SMTP 让行分隔用 CRLF，符合线路协议", "string.Template 做占位符渲染，替代手写字符串拼接", "模板里 ${name} 等是变化字段，模板本身保持不变", "substitute 缺键会抛 KeyError，避免占位符漏填", "以 SMTP policy 建消息对象", "中文主题是非 ASCII 头，序列化时会按 RFC 2047 编码", "From 用 ASCII 地址，避免头字段解析歧义", "To 头显式声明收件人", "set_content 自动设 text/plain 与传输编码", "add_alternative 把容器升级成 multipart/alternative 并加 HTML part", "附件校验函数：白名单、大小、类型三道判断", "按最后一个点取扩展名并归一为小写", "扩展名不在白名单时进入拒绝分支", "类型不符返回 reject type，供失败清单区分原因", "len(data) 与上限比较，判断字节数是否超标", "超出上限返回 reject size，与类型拒绝区分开", "三项都通过才接受", "凭证可用性函数：只有环境变量存在才允许发送", "bool 判断把缺失凭证映射成 False，不发送", "打印渲染结果，确认占位符已被真实数据替换", "打印容器类型，验证确实是 multipart/alternative", "取第二个 part 的 Content-Type，应是 text/html", "as_bytes() 序列化时才生成 encoded-word，故在字节流里检查", "注入一个占位凭证模拟密钥管理系统", "凭证存在时允许发送", "用完立即从环境移除，避免污染同进程其它片段", "凭证缺失时不发送，这是默认的安全状态", "合法 PDF 且小于上限，返回 accept", "伪装成 .exe 的附件被扩展名白名单拦下", "超过 1024 字节上限的 PDF 被大小校验拦下"]' title='第 124 讲 · 实战 03 · 邮件、PDF、Excel、Word 与图像视频' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


### set_content 与 add_alternative 怎么把容器升级成 multipart

```python
from string import Template

tpl = Template('Hi ${name}, amount ${amount}')
try:
    tpl.substitute(name='Zhang')
except KeyError as e:
    print('substitute missing', type(e).__name__, str(e))
print('safe substitute', tpl.safe_substitute(name='Zhang'))
print('naive concat', 'Hi ' + 'Zhang' + ', amount ' + '${amount}')
```

<OutputBox title='对照写法：先自己猜，再点开' output='substitute missing KeyError &#39;amount&#39;\nsafe substitute Hi Zhang, amount ${amount}\nnaive concat Hi Zhang, amount ${amount}' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import os\nfrom email.message import EmailMessage\nfrom email import policy\nfrom string import Template\n\ntpl = Template(&#39;Hi ${name}, your ${month} bill is ${amount} CNY.&#39;)\nbody = tpl.substitute(name=&#39;Zhang&#39;, month=&#39;6&#39;, amount=&#39;128.50&#39;)\nmsg = EmailMessage(policy=policy.SMTP)\nmsg[&#39;Subject&#39;] = &#39;账单通知&#39;\nmsg[&#39;From&#39;] = &#39;billing@example.com&#39;\nmsg[&#39;To&#39;] = &#39;user@example.com&#39;\nmsg.set_content(body)\nmsg.add_alternative(&#39;&lt;p&gt;bill 128.50 CNY&lt;/p&gt;&#39;, subtype=&#39;html&#39;)\n\ndef check_attachment(name, data, allowed, max_bytes):\n    ext = &#39;.&#39; + name.rsplit(&#39;.&#39;, 1)[-1].lower()\n    if ext not in allowed:\n        return &#39;reject type&#39;\n    if len(data) &gt; max_bytes:\n        return &#39;reject size&#39;\n    return &#39;accept&#39;\n\ndef send_enabled():\n    return bool(os.environ.get(&#39;SMTP_APP_PASSWORD&#39;))\n\nprint(&#39;rendered&#39;, body)\nprint(&#39;multipart&#39;, msg.get_content_type())\nprint(&#39;html part&#39;, msg.get_payload()[1].get_content_type())\nprint(&#39;subject encoded&#39;, b&#39;=?utf-8?&#39; in msg.as_bytes())\nos.environ[&#39;SMTP_APP_PASSWORD&#39;] = &#39;token&#39;\nprint(&#39;send enabled&#39;, send_enabled())\nos.environ.pop(&#39;SMTP_APP_PASSWORD&#39;, None)\nprint(&#39;send disabled&#39;, send_enabled())\nprint(&#39;pdf&#39;, check_attachment(&#39;bill.pdf&#39;, b&#39;x&#39; * 100, {&#39;.pdf&#39;}, 1024))\nprint(&#39;exe&#39;, check_attachment(&#39;setup.exe&#39;, b&#39;x&#39;, {&#39;.pdf&#39;}, 1024))\nprint(&#39;big&#39;, check_attachment(&#39;big.pdf&#39;, b&#39;x&#39; * 2048, {&#39;.pdf&#39;}, 1024))", "note": "MIME 与 EmailMessage：把邮件构造交给协议实现"}, {"label": "对照 / 进阶", "code": "from string import Template\n\ntpl = Template(&#39;Hi ${name}, amount ${amount}&#39;)\ntry:\n    tpl.substitute(name=&#39;Zhang&#39;)\nexcept KeyError as e:\n    print(&#39;substitute missing&#39;, type(e).__name__, str(e))\nprint(&#39;safe substitute&#39;, tpl.safe_substitute(name=&#39;Zhang&#39;))\nprint(&#39;naive concat&#39;, &#39;Hi &#39; + &#39;Zhang&#39; + &#39;, amount &#39; + &#39;${amount}&#39;)", "note": "模板渲染：string.Template 与 Jinja2 的分工"}]' title='两种写法对照' note='差异集中在 smtplib / yagmail 与授权码；先看输出，再找背后的规则。' />

```python
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
```

<OutputBox title='原理验证' output='parsed type multipart/alternative\nparts [&#39;text/plain&#39;, &#39;text/html&#39;]\nsubject roundtrip Test\ncrlf present True' />


## 模板渲染：string.Template 与 Jinja2 的分工

模板 + 数据 + 批量渲染是文档自动化的通用套路：不变的部分留在模板里，代码只填变化字段。

标准库 `string.Template` 用 `$name` 或 `${name}` 作占位符，`$$` 表示字面量 `$`；

`substitute(**row)` 用字典一次填满，缺键会抛 `KeyError`，`safe_substitute` 则把缺失占位符原样保留——两者差别正是「宁可失败也不要把 `${amount}` 发给客户」的关键。

它只做标识符替换、不求值表达式，因此比 `eval` 或把用户输入当模板编译安全；相较之下 `str.format` 能访问属性与索引，模板来自用户输入时有信息泄漏风险。

Jinja2 用 `{{ name }}`、`{% for %}` 与模板继承，`HTML` 场景必须开 `autoescape=True` 防止注入。

同一套思路延伸到办公文档：`openpyxl` 在单元格里放占位、`python-docx` 用模板段落、`pypdf` 做拆分合并、`Pillow` 生成缩略图与二维码、`moviepy` 做分段转码，这些 CPU 或 IO 较重的步骤应放进 worker 异步化，不要堵在发送循环里。

三个失效信号：正文出现 `${...}`、姓名带 `&` 或 `<` 时标签被截断、模板字符串直接来自用户输入。

**模板与转义对照**

| 写法 | 缺占位符时 | 安全风险 |
| --- | --- | --- |
| string.Template.substitute | 抛 KeyError | 低：只替换标识符，不求值表达式 |
| string.Template.safe_substitute | 保留 $&#123;name&#125; 原样 | 中：会把占位符发给客户 |
| str.format | 抛 KeyError | 中：可访问属性与索引 |
| Jinja2 且 autoescape=True | 渲染为 Undefined | 低：HTML 自动转义 |
| Jinja2 且 autoescape=False | 渲染为 Undefined | 高：用户输入拼进 HTML 造成注入 |
| 手写字符串拼接 | 残留 $&#123;amount&#125; | 高：转义错乱、标签截断、XSS |


## 凭证外部注入与附件类型、大小校验

`SMTP` 授权码（app password）是邮箱服务商为第三方客户端单独生成的串，不等于账号登录密码；QQ 邮箱、163、Gmail 都要求开启 `SMTP` 服务后单独生成。凭证走 `os.environ.get` 或 `.env`（必须加入 `.gitignore`）或密钥管理服务，绝不写进源码常量与截图。

附件校验要三重叠加：扩展名白名单（如 `{'.pdf'}`）、`len(data)` 大小上限、以及 magic bytes（PDF 以 `b'%PDF-'` 开头），因为文件名与客户端声明的 `Content-Type` 都可伪造，只信其中一项就会放进伪装的 `.exe` 或超大附件。

批量发送要限速（每秒 N 封或 `min_interval`）、把失败项落进失败清单供重试、用幂等键保证同一账单不重复发、给每次调用设超时；拆成小批交给异步 worker，让 `Pillow` 缩略图、`pypdf` 合并、`moviepy` 转码这类重活不阻塞主循环。

整批被拒、重复投递、凭证出现在 `git diff`、超大附件打满队列，都是缺少这些约束的典型信号。

<Term word='smtplib / yagmail 与授权码' text='`email.message.EmailMessage` 自 3.6 起提供现代 API，构造时传 `policy=policy.SMTP` 会用 `CRLF` 作行分隔（`policy.default` 用 LF，发送场景要前者）。`msg.set_content(text)` 自动设 `Content-Type` ' />

<Term word='pypdf 拆分合并' text='模板 + 数据 + 批量渲染是文档自动化的通用套路：不变的部分留在模板里，代码只填变化字段。标准库 `string.Template` 用 `$name` 或 `${name}` 作占位符，`$$` 表示字面量 `$`；`substitute(**row)` 用字典一次填满，缺键会抛 `KeyError`，`safe_' />

<Callout type="warn" title='本讲最容易踩的坑' text='把 SMTP 授权码写死在脚本里并随代码提交：凭证进入版本库与日志，任何能看到仓库的人都能发信，且难以只吊销单个客户端' />


## 批量发送的限速、重试与失败清单

<CheckList id='P124b' title='上线前自检' :items='["能复现并解释「把 SMTP 授权码写死在脚本里并随代码提交」", "能复现并解释「用字符串拼 HTML 邮件正文」", "能复现并解释「只按文件名或客户端声明的 Content-Type 判附件」", "能用一条命令验证 smtplib / yagmail 与授权码", "关键路径有自动化测试与失败分支"]' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：把 SMTP 授权码写死在脚本里并随代码提交", "body": "凭证进入版本库与日志，任何能看到仓库的人都能发信，且难以只吊销单个客户端", "tip": "用 os.environ.get 或 .env（加入 .gitignore）读取，用后可轮换；缺失凭证时直接禁用发送"}, {"title": "第 2 步：用字符串拼 HTML 邮件正文", "body": "转义被破坏、姓名里的 &amp; 与 &lt; 截断标签、${amount} 占位符残留发给客户", "tip": "用 EmailMessage.set_content 与 add_alternative 构造 MIME，正文交给 string.Template.substitute 渲染，HTML 场景开 autoescape"}, {"title": "第 3 步：只按文件名或客户端声明的 Content-T", "body": "伪装的 .exe 或超大附件被放进队列，SMTP 拒收整批或带来存储型风险", "tip": "扩展名白名单 + len(data) 上限 + magic bytes（PDF 为 b&#39;%PDF-&#39;）三重校验，并给批量发送设限速与失败清单"}]' />


## MIME 是一棵树：为什么 HTML part 必须放最后

`MIME` 把一封邮件表示成树：`multipart/alternative` 里每个 part 是同一内容的不同表示，客户端按由先到后的优先级选最后一个能渲染的类型，所以 `HTML` 必须放在 `text/plain` 之后；

`multipart/mixed` 才用于挂载附件。

`Content-Transfer-Encoding` 把 8-bit 内容编码成 7-bit 以适配 `SMTP` 线路（文本用 quoted-printable、二进制用 base64），RFC 2047 的 encoded-word 则在 `as_bytes()` 序列化阶段把非 `ASCII` 头折成 `=?charset?b?...?=`，因为 RFC 5322 头字段只允许 `ASCII`。

`SMTP` 的 `DATA` 命令以单独一行的点号结束、行分隔固定 `CRLF`，`send_message` 负责点填充与这些细节。

`string.Template` 用正则匹配 `$` 标识符、只做替换不求值，因此把用户输入当数据传是安全的，把用户输入当模板编译才会引入注入。

授权码机制把主密码与第三方客户端隔离，泄漏时可单独吊销而不影响账号本身。

<ConceptDiagram type='compare2' title='第 124 讲 · MIME 与 EmailMessage：把邮件构造交给协议实现' labels='MIME 与 EmailMessage：把邮|模板渲染：string.Template 与|凭证、附件校验、限速与失败清单' caption='串起办公文档的全套自动化流水线' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 办公文档批处理库、用途与风险

**办公文档批处理库、用途与风险**

| 库 | 典型用途 | 主要风险 / 约束 |
| --- | --- | --- |
| pypdf | PDF 拆分与合并 | 加密 PDF 需先 decrypt，大文件勿全量载入 |
| openpyxl / pandas | Excel 读写与透视 | 公式不计算、样式易丢，注意 dtype |
| python-docx | Word 模板渲染 | 复杂模板用占位段落，别拼 XML |
| Pillow | 缩略图与二维码 | 大图解码占内存，需限尺寸 |
| moviepy | 视频分段与拼接 | CPU 密集，放进 worker 异步化 |
| smtplib | 发送 MIME 邮件 | 授权码非登录密码，必须设超时 |


## 错因速查：凭证泄漏、HTML 拼接与附件误判

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 把 SMTP 授权码写死在脚本里并随代码提交 | 凭证进入版本库与日志，任何能看到仓库的人都能发信，且难以只吊销单个客户端 | 用 os.environ.get 或 .env（加入 .gitignore）读取，用后可轮换；缺失凭证时直接禁用发送 |
| 用字符串拼 HTML 邮件正文 | 转义被破坏、姓名里的 & 与 < 截断标签、$&#123;amount&#125; 占位符残留发给客户 | 用 EmailMessage.set_content 与 add_alternative 构造 MIME，正文交给 string.Template.substitute 渲染，HTML 场景开 autoescape |
| 只按文件名或客户端声明的 Content-Type 判附件 | 伪装的 .exe 或超大附件被放进队列，SMTP 拒收整批或带来存储型风险 | 扩展名白名单 + len(data) 上限 + magic bytes（PDF 为 b'%PDF-'）三重校验，并给批量发送设限速与失败清单 |


## 带校验、限速与失败清单的批量账单流水线

两千封账单要在十分钟内发完，又要保证不重发、不发错附件、不被 `SMTP` 拒收。

把流程拆成四步：`render` 用 `string.Template.substitute` 把行数据填进固定模板，缺字段直接抛 `KeyError` 而不是把占位符发出去；

`check` 对附件做扩展名白名单与 `len(data)` 大小上限校验；`build` 用 `EmailMessage` 生成一封合规邮件；`run` 按 `limit` 限速，把失败原因（type / size / rate limit）连同收件人记进失败清单供重试。

真实项目把 `limit` 换成每秒令牌、给每封加幂等键、把 `Pillow` 缩略图与 `pypdf` 合并放进后台 worker，并用 `smtplib.SMTP_SSL` 配超时发送。

下面片段可直接运行，重点看每个拒绝分支都有明确、可重试的出口。

```python
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
```

<Callout type="idea" title='落地提示' text='凭证走环境变量、模板用 Jinja2、附件做类型与大小校验、批量发送加限速与失败清单' />

```bash
python -m compileall -q . && python -m pytest -q
```

把输入换成你自己的数据，观察结果是否仍符合 smtplib / yagmail 与授权码 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。


## 练习、自测与一页纸速记

<Exercise title='基础：用 EmailMessage 构造并回解析一封多部分邮件' task='用 set_content 加 add_alternative 构造邮件，as_bytes() 后用 BytesParser 回解析，打印容器类型与各 part 的 Content-Type。' solution='from email import policy\nfrom email.message import EmailMessage\nfrom email.parser import BytesParser\nm = EmailMessage(policy=policy.SMTP)\nm[&#39;Subject&#39;] = &#39;T&#39;\nm[&#39;From&#39;] = &#39;a@b.com&#39;\nm[&#39;To&#39;] = &#39;c@d.com&#39;\nm.set_content(&#39;plain&#39;)\nm.add_alternative(&#39;&lt;p&gt;h&lt;/p&gt;&#39;, subtype=&#39;html&#39;)\np = BytesParser(policy=policy.default).parsebytes(m.as_bytes())\nprint(&#39;type&#39;, p.get_content_type())\nprint(&#39;parts&#39;, [x.get_content_type() for x in p.iter_parts()])' explain='set_content 放 text/plain，add_alternative 把容器升级成 multipart/alternative 并追加 text/html；回解析后两个 part 的顺序与类型都可核对。' />

<Exercise title='进阶：给附件校验补上 magic bytes' task='在扩展名白名单与大小上限之外，加一条按文件头判断 PDF 的规则（b&#39;%PDF-&#39;），构造三个附件验证只有合法且大小合规的通过。' solution='ALLOWED = {&#39;.pdf&#39;}\ndef check(name, data, max_bytes):\n    ext = &#39;.&#39; + name.rsplit(&#39;.&#39;, 1)[-1].lower()\n    if ext not in ALLOWED: return &#39;type&#39;\n    if len(data) &gt; max_bytes: return &#39;size&#39;\n    if not data.startswith(b&#39;%PDF-&#39;): return &#39;magic&#39;\n    return &#39;accept&#39;\nprint(check(&#39;a.pdf&#39;, b&#39;%PDF-1.4 x&#39;, 1024))\nprint(check(&#39;b.pdf&#39;, b&#39;MZ fake&#39;, 1024))\nprint(check(&#39;c.exe&#39;, b&#39;%PDF-&#39;, 1024))' explain='文件名可伪装，magic bytes 提供第二重证据；输出依次是 accept、magic、type。生产还要把三种拒绝原因分别记进失败清单供排查。' />

<Quiz no='124-1' q='关于 string.Template.substitute 与 safe_substitute，哪一项准确？' :options='["substitute 缺键抛 KeyError，safe_substitute 保留 ${name} 原样", "两者缺键都抛 KeyError", "safe_substitute 会求值表达式", "substitute 把缺键替换成空串"]' answer="0" explain='批量发信应选 substitute：缺字段立刻失败，不会把 ${amount} 发给客户；safe_substitute 保留占位符看似温和，实际会把模板泄漏出去。' />

<Quiz no='124-2' q='EmailMessage 里非 ASCII 的中文 Subject 何时被编码成 RFC 2047 encoded-word？' :options='["调用 as_bytes() 或 as_string() 序列化时", "给 msg[&#39;Subject&#39;] 赋值时立即编码", "由 SMTP 服务器在投递时编码", "永远不编码，直接发 UTF-8 字节"]' answer="0" explain='头字段只允许 ASCII，编码发生在序列化阶段，结果是 =?utf-8?b?...?=；直接读 msg[&#39;Subject&#39;] 仍是原始 str，所以要在字节流里检查才看得到。' />

<Quiz no='124-3' q='批量邮件附件校验最稳妥的组合是？' :options='["扩展名白名单 + len(data) 上限 + magic bytes", "只检查客户端声明的 Content-Type", "只检查文件名后缀", "只限制总发送数量"]' answer="0" explain='文件名与 Content-Type 都可伪造；三重校验分别挡住伪装类型、超大附件与内容不符。再叠加限速、失败清单与幂等键才算完整。' />

<Predict no='124-4' q='EmailMessage 先 set_content 再 add_alternative(subtype=&#39;html&#39;) 后，msg.get_content_type() 返回什么？' :options='["multipart/alternative", "text/plain", "multipart/mixed"]' answer='0' output='multipart/alternative' explain='set_content 先放入 text/plain part；add_alternative 把容器升级成 multipart/alternative 并追加 text/html part。只有再调用 add_attachment 才会变成 multipart/mixed。' />

<FillBlank no='124-5' tpl='___ os' :answers='["import"]' hint='回想本讲关于 smtplib / yagmail 与授权码 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 MIME 与 EmailMessage：把邮件构造交给协议实现 的落点。' />

<KnowledgeCard :points='["EmailMessage（3.6 起）配 policy=policy.SMTP 用 CRLF；set_content / add_alternative / add_attachment 逐层构造 MIME 树", "multipart/alternative 里 HTML part 放最后；multipart/mixed 才挂附件；as_bytes() 时才生成 RFC 2047 encoded-word", "string.Template 用 $name / ${name}；substitute 缺键抛 KeyError、safe_substitute 保留占位符，发信选前者", "SMTP 授权码不是登录密码，走 os.environ 读取、不入库、可单独吊销；Jinja2 的 HTML 场景开 autoescape", "附件校验三重：扩展名白名单 + len(data) 上限 + magic bytes（PDF 为 b&#39;%PDF-&#39;）", "批量发送要限速、失败清单、幂等键与超时；Pillow / pypdf / moviepy 等重活放进 worker 异步化"]' :pitfalls='["把 SMTP 授权码写死在脚本里并随代码提交", "用字符串拼 HTML 邮件正文", "只按文件名或客户端声明的 Content-Type 判附件", "把邮箱授权码写死在脚本里、或用字符串拼 HTML 邮件正文，都会带来凭证泄漏与内容错乱"]' summary='文档自动化的通用套路是「模板 + 数据 + 批量渲染」，把不变的部分留给模板，只让代码填变化字段' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| EmailMessage（3.6 起）配 policy=policy.SMTP 用 CRLF；set_content / add_alternative / add_attachment 逐层构造 MIME 树 | 建立直觉 |
| multipart/alternative 里 HTML part 放最后；multipart/mixed 才挂附件；as_bytes() 时才生成 RFC 2047 encoded-word | 跑通示例 |
| string.Template 用 $name / $&#123;name&#125;；substitute 缺键抛 KeyError、safe_substitute 保留占位符，发信选前者 | 深入边界 |
| SMTP 授权码不是登录密码，走 os.environ 读取、不入库、可单独吊销；Jinja2 的 HTML 场景开 autoescape | 工程落地 |
| 附件校验三重：扩展名白名单 + len(data) 上限 + magic bytes（PDF 为 b'%PDF-'） | 随堂检测 |
| 批量发送要限速、失败清单、幂等键与超时；Pillow / pypdf / moviepy 等重活放进 worker 异步化 | 复盘 |

1. EmailMessage（3.6 起）配 policy=policy.SMTP 用 CRLF；set_content / add_alternative / add_attachment 逐层构造 MIME 树

2. multipart/alternative 里 HTML part 放最后；multipart/mixed 才挂附件；as_bytes() 时才生成 RFC 2047 encoded-word

3. string.Template 用 $name / $&#123;name&#125;；substitute 缺键抛 KeyError、safe_substitute 保留占位符，发信选前者

[下一讲：实战 04 · Selenium 表单自动化与定时任务](/projects/browser-auto)
