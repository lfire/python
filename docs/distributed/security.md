---
title: 第 113 讲 · 安全工程：依赖、注入、序列化与密钥
description: 把安全做成默认行为而不是事后补丁
---

<StageHeader stage='L10 · 分布式云原生' level='★★★★☆' time='40 分钟' goal='把安全做成默认行为而不是事后补丁' prereq='第 112 讲 · 任务调度、SRE 与混沌工程' />

# 第 113 讲 · 安全工程：依赖、注入、序列化与密钥

调度、告警、演练都齐了，还有一层常被排到最后：服务对外开的口子结不结实。很多高危问题不在语法，而藏在一段看着无害的功能里——输入来自用户表单、上传文件，或一条被顺手拼进语句的字符串。等功能上线再补往往已经晚了；把它做成默认行为，是这一讲想挪动的位置。

先从 SQL 与命令两条入口看注入与参数化，认清拼接为什么挡不住；再谈不安全的反序列化，划清 pickle 与 eval 的边界；最后落到依赖漏洞、密钥轮换与权限最小化。需要函数、序列化、依赖安装和一点 SQL 基础；读完后你能把拼接查询改成参数化，也能给安全工程定下几条不靠自觉也生效的规矩。


## 一条带着 OR 条件的输入拖走了整张表

一个内部报表接口把用户传入的名字直接拼进 SQL：先把查询骨架写成字符串，再用 `repr(name)` 把输入接在后面，凑成一条完整语句交给 `execute`。上线后有人提交了一个带引号的输入，整张用户表被拖走；

同一份代码还把 `pickle.loads` 用在缓存反序列化上，而缓存内容可由外部接口写入，等于把任意对象构造能力交给了调用方。另一处事故是运维把 `.env` 打进镜像、又在异常日志里打印完整请求头，密钥跟着进了日志系统。

这些都不是语法层的 bug：`eval`、pickle 处理不可信数据、字符串拼接 SQL、密钥落进交付物，任意一条都能直接导致失陷。团队想靠代码评审拦住，但评审会漏，第三方依赖里的 CVE 更不在评审视野内。这一讲把安全做成默认行为：参数化查询、禁止对不可信数据反序列化、密钥托管与轮换、CI 做依赖与镜像扫描。

<Callout type="warn" title='先看一个真实会出错的写法' text='用字符串拼接构造 WHERE 条件：输入里的引号与 OR 会改变 SQL 语法树，条件恒真导致拖库或越权' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段十 · 分布式与云原生 |
| 前置 | 第 112 讲 · 任务调度、SRE 与混沌工程 |
| 难度 / 建议时长 | ★★★★☆ · 40 分钟 |
| 本讲新增 | 依赖漏洞与 SBOM、注入与参数化、不安全的反序列化 |
| 一句话目标 | 把安全做成默认行为而不是事后补丁 |
| 为下一讲铺垫 | CPython 源码：对象、帧与求值循环 |


## 注入与参数化：SQL 与命令两条入口

SQL 注入的根因，是把数据与代码拼进同一个字符串：`sqlite3` 的 `execute` 收到一整条已拼好的语句，输入里的引号、OR、注释符会改变语法树。

参数化查询用占位符把语句结构与值分开：sqlite3 用 `?` 占位、把值作为绑定参数传入，psycopg 与 PyMySQL 用 `%s`，驱动在协议层把值当数据处理、不再经过 SQL 解析，因此输入里的引号只是普通字符。要注意参数只能代值，代替不了表名、列名或排序方向，这些得靠白名单映射。

命令注入同理：`subprocess.run` 传 `shell=True` 又拼接字符串，分号、管道就会被 shell 解释；正确做法是传列表参数，并保持默认的 `shell=False`。

其它入口还有 `eval`、`exec` 处理外部字符串，模板里的 `SSTI`，`yaml.load` 用了不安全的 Loader（应换成 `yaml.safe_load`），以及路径拼接导致的目录穿越（用 `os.path.basename` 或路径白名单）。

这些修复的共同点，是把不可信数据限制在数据通道里，永不进入代码或命令的解析通道。

```python
import sqlite3

db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE users (name TEXT, role TEXT)')
db.executemany('INSERT INTO users VALUES (?, ?)', [('alice', 'admin'), ('bob', 'user')])

def unsafe(uid):
    q = 'SELECT name, role FROM users WHERE name = ' + chr(39) + uid + chr(39)
    return db.execute(q).fetchall()

def safe(uid):
    q = 'SELECT name, role FROM users WHERE name = ?'
    return db.execute(q, (uid,)).fetchall()

print('normal', safe('alice'))
inj = 'x' + chr(39) + ' OR ' + chr(39) + '1' + chr(39) + '=' + chr(39) + '1'
print('unsafe_rows', len(unsafe(inj)))
print('safe_rows', len(safe(inj)))
db.close()
```

<OutputBox title='主示例运行结果' output='normal [(&#39;alice&#39;, &#39;admin&#39;)]\nunsafe_rows 2\nsafe_rows 0' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE users (name TEXT, role TEXT)&#39;)\ndb.executemany(&#39;INSERT INTO users VALUES (?, ?)&#39;, [(&#39;alice&#39;, &#39;admin&#39;), (&#39;bob&#39;, &#39;user&#39;)])\n\ndef unsafe(uid):\n    q = &#39;SELECT name, role FROM users WHERE name = &#39; + chr(39) + uid + chr(39)\n    return db.execute(q).fetchall()\n\ndef safe(uid):\n    q = &#39;SELECT name, role FROM users WHERE name = ?&#39;\n    return db.execute(q, (uid,)).fetchall()\n\nprint(&#39;normal&#39;, safe(&#39;alice&#39;))\ninj = &#39;x&#39; + chr(39) + &#39; OR &#39; + chr(39) + &#39;1&#39; + chr(39) + &#39;=&#39; + chr(39) + &#39;1&#39;\nprint(&#39;unsafe_rows&#39;, len(unsafe(inj)))\nprint(&#39;safe_rows&#39;, len(safe(inj)))\ndb.close()' :notes='["导入 sqlite3，用内存库演示参数化", "创建仅存在于内存的数据库", "建表，含名字与角色两列", "用参数化 executemany 插入两条基线数据", "unsafe 演示拼接式查询", "用 chr(39) 拼单引号把 uid 直接嵌进语句，改变语法结构", "执行拼好的整条语句并返回所有行", "safe 使用占位符", "问号是值占位，不参与 SQL 解析", "把值作为绑定参数单独传入", "正常查询返回 alice 一条记录", "构造注入串 x&#39; OR &#39;1&#39;=&#39;1，chr(39) 规避引号转义", "拼接版条件恒真，泄漏全部 2 行", "参数化版把注入串当普通名字，匹配 0 行", "关闭数据库连接"]' title='第 113 讲 · 安全工程：依赖、注入、序列化与密钥' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

**注入入口与正确写法**

| 入口 | 危险写法 | 正确写法 |
| --- | --- | --- |
| SQL | 字符串拼接 WHERE name = '...' | 占位符 ? 或 %s 加绑定参数 |
| 命令 | subprocess.run(s, shell=True) | 传列表参数且 shell=False |
| YAML | yaml.load(s) | yaml.safe_load(s) |
| 表达式 | eval / exec 处理外部串 | ast.literal_eval 或显式解析 |
| 路径 | os.path.join(base, 用户输入) | 白名单或 basename 加前缀校验 |

<ConceptDiagram type='hub4' title='第 113 讲 · 注入与参数化：SQL 与命令两条入口' labels='注入与参数化：SQL 与命令两条入口|不安全的反序列化与 Python 特有风险|依赖漏洞、密钥管理与纵深防御' caption='把安全做成默认行为而不是事后补丁' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


### 对照：字符串拼接与占位符绑定的输出

```python
import pickle

SIDE_EFFECT = []
def boom():
    SIDE_EFFECT.append('executed')
    return 1

class Payload:
    def __reduce__(self):
        return (boom, ())

blob = pickle.dumps(Payload())
print('before', list(SIDE_EFFECT))
out = pickle.loads(blob)
print('out', out)
print('after', list(SIDE_EFFECT))
```

<OutputBox title='对照写法：先自己猜，再点开' output='before []\nout 1\nafter [&#39;executed&#39;]' guess="true" />

<CodeTabs :tabs='[{"label": "主示例", "code": "import sqlite3\n\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE users (name TEXT, role TEXT)&#39;)\ndb.executemany(&#39;INSERT INTO users VALUES (?, ?)&#39;, [(&#39;alice&#39;, &#39;admin&#39;), (&#39;bob&#39;, &#39;user&#39;)])\n\ndef unsafe(uid):\n    q = &#39;SELECT name, role FROM users WHERE name = &#39; + chr(39) + uid + chr(39)\n    return db.execute(q).fetchall()\n\ndef safe(uid):\n    q = &#39;SELECT name, role FROM users WHERE name = ?&#39;\n    return db.execute(q, (uid,)).fetchall()\n\nprint(&#39;normal&#39;, safe(&#39;alice&#39;))\ninj = &#39;x&#39; + chr(39) + &#39; OR &#39; + chr(39) + &#39;1&#39; + chr(39) + &#39;=&#39; + chr(39) + &#39;1&#39;\nprint(&#39;unsafe_rows&#39;, len(unsafe(inj)))\nprint(&#39;safe_rows&#39;, len(safe(inj)))\ndb.close()", "note": "注入与参数化：SQL 与命令两条入口"}, {"label": "对照 / 进阶", "code": "import pickle\n\nSIDE_EFFECT = []\ndef boom():\n    SIDE_EFFECT.append(&#39;executed&#39;)\n    return 1\n\nclass Payload:\n    def __reduce__(self):\n        return (boom, ())\n\nblob = pickle.dumps(Payload())\nprint(&#39;before&#39;, list(SIDE_EFFECT))\nout = pickle.loads(blob)\nprint(&#39;out&#39;, out)\nprint(&#39;after&#39;, list(SIDE_EFFECT))", "note": "不安全的反序列化与 Python 特有风险"}]' title='两种写法切换看' />

```python
import hashlib, secrets, hmac

token = secrets.token_hex(16)
digest = hashlib.sha256(token.encode()).hexdigest()
print('token_len', len(token))
print('digest_len', len(digest))
def redact(s):
    return s[:4] + '****' if len(s) > 4 else '****'
print('redacted', redact('abcdefghijk'))
print('hmac_equal', hmac.compare_digest(digest, hashlib.sha256(token.encode()).hexdigest()))
```

<OutputBox title='原理验证' output='token_len 32\ndigest_len 64\nredacted abcd****\nhmac_equal True' />


## 用字符串拼接构造 WHERE 条件

<Callout type="warn" title='本讲最容易踩的坑' text='用字符串拼接构造 WHERE 条件：输入里的引号与 OR 会改变 SQL 语法树，条件恒真导致拖库或越权' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：用字符串拼接构造 WHERE 条件", "body": "输入里的引号与 OR 会改变 SQL 语法树，条件恒真导致拖库或越权", "tip": "一律用占位符加绑定参数；表名列名排序方向用白名单映射，不能靠参数代值"}, {"title": "第 2 步：对来自缓存或接口的字节直接 pickle.l", "body": "__reduce__ 可指定任意可调用对象，反序列化即执行构造逻辑，造成远程代码执行", "tip": "跨系统改用 json；必须用 pickle 时保证来源不可被外部写、对 blob 做 HMAC 签名并校验大小与深度"}, {"title": "第 3 步：把 .env 与 token 打进镜像或异常", "body": "镜像层与日志系统可被更广的人群读取，凭证长期泄露且难以轮换", "tip": "运行时注入密钥并支持轮换，日志打印前脱敏，CI 做镜像与依赖扫描，非 root 运行且权限最小化"}]' />


## 不安全的反序列化与 Python 特有风险

pickle 不是数据格式，而是对象构造协议：`pickle.loads` 会执行 `__reduce__` 指定的可调用对象，攻击者构造一个 `__reduce__` 返回 `os.system` 加一串参数、或等价的可调用类，反序列化即触发任意代码执行，这正是 CPython 文档明确警告的「绝不对不可信数据 unpickle」。

json 才是数据格式，跨系统交换一律用它，需要带类型时用显式 schema 校验，而不是 pickle。同类风险还有 `marshal`、`shelve`，以及某些缓存客户端默认用 pickle 编解码；

若必须用 pickle 做内部缓存，要保证数据来源不可被外部写入，并对 blob 做 `HMAC` 签名校验，签名比对用 `hmac.compare_digest` 做常量时间比较，防时序侧信道。

`eval` 与 `exec` 即便配了空的 `globals` 也不安全，内置对象能沿类继承链被重新拿到，应改用 `ast.literal_eval` 解析字面量。

反序列化的深度与大小也要限流，防止深层嵌套把栈或内存耗尽。CPython 的 pickle 协议 0 到 5 都不改变这个结论：版本号只影响序列化格式，不提供安全边界。

**序列化格式的安全边界**

| 格式 | 是否执行代码 | 适用 |
| --- | --- | --- |
| json | 否，纯数据 | 跨系统交换、外部输入 |
| pickle | 是，__reduce__ 可调用任意对象 | 仅可信的内部缓存且签名校验 |
| marshal | 不执行但版本耦合、非安全契约 | 仅 CPython 内部 .pyc |
| shelve | 底层 pickle，同风险 | 本地可信数据 |

SQL 注入与 pickle RCE 是同一个根因的两种表现：把不可信数据送进了会解析或执行它的通道。SQL 驱动在参数化模式下，先把语句编译成带绑定点的模板，值通过独立通道传入，数据库协议层按类型写入而不再经过词法与语法分析，引号、注释符、OR 因此都失去改变语义的能力。

pickle 正相反，它是一套栈式对象构造虚拟机，opcode 里的 `REDUCE`、`GLOBAL` 会按名导入并调用可调用对象，`__reduce__` 正是给类自定义这个构造过程，于是反序列化等价于执行一段由数据描述的程序——这是设计使然，不是实现缺陷。

CPython 明确把 pickle 标为不安全，协议 0 到 5 都保留 opcode 调用能力，版本号只改编码格式。防御只能靠边界：对外一律用 json 这类纯数据格式，内部若用 pickle 就对 blob 做 `HMAC` 校验，并用 `compare_digest` 常量时间比对，杜绝篡改。

`eval` 即便限制 `globals` 也不构成沙箱，因为内置类型能通过对象继承链被重新取得。


### __reduce__ 为什么等于远程代码执行

<Term word='依赖漏洞与 SBOM' text='SQL 注入的根因，是把数据与代码拼进同一个字符串：`sqlite3` 的 `execute` 收到一整条已拼好的语句，输入里的引号、OR、注释符会改变语法树。参数化查询用占位符把语句结构与值分开：sqlite3 用 `?` 占位、把值作为绑定参数传入，psycopg 与 PyMySQL 用 `%s`，驱动在协议层把值' />

<Term word='注入与参数化' text='pickle 不是数据格式，而是对象构造协议：`pickle.loads` 会执行 `__reduce__` 指定的可调用对象，攻击者构造一个 `__reduce__` 返回 `os.system` 加一串参数、或等价的可调用类，反序列化即触发任意代码执行，这正是 CPython 文档明确警告的「绝不对不可信数据 un' />


## 依赖漏洞、密钥管理与纵深防御

第三方依赖是供应链入口：requirements 不锁版本，不同时间的构建就会拉到不同代码，CI 要用锁文件固定版本，用 pip-audit、safety 对照 CVE 库扫描，并产出 `SBOM`（软件物料清单）记录组件与版本，出现新 CVE 时能快速定位受影响的服务。

镜像层同样要扫，而且别把 `.env`、私钥、token 打进镜像或日志；密钥由托管服务或环境变量在运行时注入，支持轮换（新旧密钥并存一段时间），日志里打印令牌前先脱敏（只留前几位）。`secrets` 模块提供 `token_hex`、`token_urlsafe` 这类密码学安全随机源，不要用 `random` 生成令牌；

口令存储用 `hashlib.pbkdf2_hmac` 或 bcrypt、argon2 加盐，别用裸 sha256。

比较摘要一律用 `hmac.compare_digest`。

权限最小化落到容器非 root、数据库账号只授所需表、服务间用短期凭证。审计与应急响应还要求记录关键操作、保留可追溯日志，并预演凭证泄露后的轮换与吊销流程。

**依赖与密钥检查清单**

| 项目 | 做法 | 可核对信号 |
| --- | --- | --- |
| 依赖锁版本 | 锁文件固定版本 | 构建产物与锁文件一致 |
| 漏洞扫描 | pip-audit / safety 对照 CVE | 高危 CVE 数 |
| SBOM | 记录组件与版本 | 新 CVE 时受影响服务定位耗时 |
| 密钥注入 | 运行时环境变量或托管服务 | 镜像与日志中无明文密钥 |
| 令牌生成 | secrets.token_hex | 不用 random 生成凭证 |
| 摘要比较 | hmac.compare_digest | 常量时间，避免时序侧信道 |


## 带参数化、脱敏与幂等令牌的安全数据访问层

把一次用户查询写成默认安全的访问层：查询一律走参数化，外部输入先做白名单校验，返回的令牌与摘要在日志里脱敏，写操作带幂等令牌避免重放。真实项目里还要加最小权限的数据库账号、密钥运行时注入、依赖扫描与审计日志。下面这段用标准库把参数化、常量时间比较、脱敏与幂等去重串在一起，重点看每个外部数据入口都有明确约束，而不是靠调用方自觉；

任何一条越过边界的路径，都应在这里被挡下并留日志可查。

```python
import sqlite3, hashlib, hmac, secrets

class Repo:
    def __init__(self):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE users (name TEXT, role TEXT)')
        self.db.execute('INSERT INTO users VALUES (?, ?)', ('alice', 'admin'))
        self.seen = set()
    def find(self, name):
        cur = self.db.execute('SELECT name, role FROM users WHERE name = ?', (name,))
        return cur.fetchall()
    def redact(self, token):
        return token[:4] + '****' if len(token) > 4 else '****'
    def token(self):
        return secrets.token_hex(16)
    def verify(self, a, b):
        return hmac.compare_digest(a, b)
    def write_once(self, idem, name):
        if idem in self.seen:
            return 'duplicate'
        self.seen.add(idem)
        return 'applied'

r = Repo()
t = r.token()
print('find', r.find('alice'))
print('log_token', r.redact(t))
print('same_token', r.verify(t, t))
print(r.write_once('k1', 'alice'), r.write_once('k1', 'alice'))
```

<Callout type="idea" title='落地提示' text='用参数化查询、禁止对不可信数据 pickle/eval、密钥托管与轮换、CI 做依赖与镜像扫描' />

<CheckList id='P113b' title='上线前自检' :items='["能复现并解释「用字符串拼接构造 WHERE 条件」", "能复现并解释「对来自缓存或接口的字节直接 pickle.loads」", "能复现并解释「把 .env 与 token 打进镜像或异常日志」", "能用一条命令验证 依赖漏洞与 SBOM", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import uuid, hashlib; print(hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:8])"
```

把输入换成你自己的数据，观察结果是否仍符合 依赖漏洞与 `SBOM` 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 用字符串拼接构造 WHERE 条件 | 输入里的引号与 OR 会改变 SQL 语法树，条件恒真导致拖库或越权 | 一律用占位符加绑定参数；表名列名排序方向用白名单映射，不能靠参数代值 |
| 对来自缓存或接口的字节直接 pickle.loads | __reduce__ 可指定任意可调用对象，反序列化即执行构造逻辑，造成远程代码执行 | 跨系统改用 json；必须用 pickle 时保证来源不可被外部写、对 blob 做 HMAC 签名并校验大小与深度 |
| 把 .env 与 token 打进镜像或异常日志 | 镜像层与日志系统可被更广的人群读取，凭证长期泄露且难以轮换 | 运行时注入密钥并支持轮换，日志打印前脱敏，CI 做镜像与依赖扫描，非 root 运行且权限最小化 |


## pickle 栈式虚拟机：REDUCE 如何变成任意调用

pickle 是栈式虚拟机，pickletools 能反汇编 blob，关键是 `GLOBAL` / `STACK_GLOBAL` 与 `REDUCE`。

前者从 `module.name` 解析全局对象（钩子是 `Unpickler.find_class`），后者弹出栈顶 (callable, args) 执行 `callable(*args)`。

`__reduce__` 的 (f, args) 序列化后编译成「解析 f、构造 args、`REDUCE`、调用」；f 可以是 `builtins.len` 或任意可调用对象——危险在「反序列化即执行构造逻辑」。CPython 文档禁止对不可信数据 unpickle，协议 0 到 5 都保留该机制。

源码在 `Lib/pickle.py` 的 load_reduce 与 find_class、Modules/`_pickle.c` 的 load_stack_global、`pickletools.py` 的 genops。

加固是覆写 find_class 白名单：只放行已知模块与类，`STACK_GLOBAL` 阶段即被拦下，`REDUCE` 无从执行；但 `BUILD`、`NEWOBJ_EX` 仍能触发 `__setstate__`，白名单不能替代「跨系统一律用 json」。

```python
import io, pickle, pickletools

class Payload:
    def __reduce__(self):
        return (sum, ([1, 2, 3],))

blob = pickle.dumps(Payload(), protocol=4)
ops = [op[0].name for op in pickletools.genops(blob) if op[0].name in ('GLOBAL', 'STACK_GLOBAL', 'REDUCE', 'BUILD')]
print('opcodes', ops)

class OnlyLen(pickle.Unpickler):
    def find_class(self, module, name):
        if module == 'builtins' and name == 'len':
            return len
        raise pickle.UnpicklingError('blocked ' + module + '.' + name)

try:
    OnlyLen(io.BytesIO(blob)).load()
    print('safe', 'loaded')
except pickle.UnpicklingError:
    print('safe', 'blocked')
print('native', pickle.loads(blob))
```

<OutputBox title='扩展示例运行结果' output='opcodes [&#39;STACK_GLOBAL&#39;, &#39;REDUCE&#39;]\nsafe blocked\nnative 6' />

<LineByLine code='import io, pickle, pickletools\n\nclass Payload:\n    def __reduce__(self):\n        return (sum, ([1, 2, 3],))\n\nblob = pickle.dumps(Payload(), protocol=4)\nops = [op[0].name for op in pickletools.genops(blob) if op[0].name in (&#39;GLOBAL&#39;, &#39;STACK_GLOBAL&#39;, &#39;REDUCE&#39;, &#39;BUILD&#39;)]\nprint(&#39;opcodes&#39;, ops)\n\nclass OnlyLen(pickle.Unpickler):\n    def find_class(self, module, name):\n        if module == &#39;builtins&#39; and name == &#39;len&#39;:\n            return len\n        raise pickle.UnpicklingError(&#39;blocked &#39; + module + &#39;.&#39; + name)\n\ntry:\n    OnlyLen(io.BytesIO(blob)).load()\n    print(&#39;safe&#39;, &#39;loaded&#39;)\nexcept pickle.UnpicklingError:\n    print(&#39;safe&#39;, &#39;blocked&#39;)\nprint(&#39;native&#39;, pickle.loads(blob))' :notes='["genops 产出 (opcode, arg, pos) 三元组，op[0].name 才是 opcode 名", "白名单 Unpickler 只放行 builtins.len，解析阶段即拦下未知名字", "原生 Unpickler 执行 sum([1,2,3]) 得到 6，印证反序列化即调用", "依赖用锁文件固定版本，CI 做 pip-audit 与镜像扫描，并产出 SBOM 记录组件版本", "密钥运行时注入、支持轮换、日志脱敏；令牌用 secrets，口令用 pbkdf2_hmac 加盐", "权限最小化：容器非 root、数据库最小授权、服务间短期凭证，并保留审计与应急轮换流程", "注入的根因是数据进入解析通道；SQL 用占位符、命令用列表参数且 shell=False", "pickle 是对象构造协议，__reduce__ 可致 RCE；外部数据一律用 json，eval 用 ast.literal_eval", "内部 pickle 需 HMAC 签名 + hmac.compare_digest 常量时间比较，并限制 blob 大小与嵌套深度", "依赖用锁文件固定版本，CI 做 pip-audit 与镜像扫描，并产出 SBOM 记录组件版本", "密钥运行时注入、支持轮换、日志脱敏；令牌用 secrets，口令用 pbkdf2_hmac 加盐", "权限最小化：容器非 root、数据库最小授权、服务间短期凭证，并保留审计与应急轮换流程", "注入的根因是数据进入解析通道；SQL 用占位符、命令用列表参数且 shell=False", "pickle 是对象构造协议，__reduce__ 可致 RCE；外部数据一律用 json，eval 用 ast.literal_eval", "内部 pickle 需 HMAC 签名 + hmac.compare_digest 常量时间比较，并限制 blob 大小与嵌套深度", "依赖用锁文件固定版本，CI 做 pip-audit 与镜像扫描，并产出 SBOM 记录组件版本", "密钥运行时注入、支持轮换、日志脱敏；令牌用 secrets，口令用 pbkdf2_hmac 加盐", "权限最小化：容器非 root、数据库最小授权、服务间短期凭证，并保留审计与应急轮换流程"]' title='扩展示例逐行讲解' />


### find_class 白名单能挡住 STACK_GLOBAL 吗

把注入与时序放到「解析阶段」看：sqlite3 参数化免疫注入，因 sqlite3_prepare_v2 先把 SQL 编译成 `VDBE` 字节码，此阶段只看到占位符 ?，输入值不参与语法分析；随后 sqlite3_bind_text 把值绑到变量槽，执行时只作为操作数，引号、OR、注释符无法改变语法树。

CPython 的 sqlite3 扩展在 Modules/_sqlite/`statement.c` 里调 prepare、bind；psycopg、PyMySQL 的 %s 同样两阶段。由此推出占位符不能代表表名、列名、排序方向：它们要在语法分析阶段确定，晚到执行阶段的值无法变成标识符，只能靠白名单。

另一条线：== 早退，耗时随共同前缀增长；若写成 if provided == expected，固定前缀猜下一字节，正确字节让比较多走一字符、耗时略长，恢复 n 字节令牌只需约 256·n 次请求，暴力枚举则是 256^n。

修复是 `hmac.compare_digest`：CPython 在 Modules/`_operator.c` 的 _tscmp 里做固定时长按位比较，不论首个不同字节在哪都扫描完整长度。

但它只保证比较恒定时间，前面的长度早退判断仍泄漏长度。

**pickle opcode 与防御边界**

| opcode | 作用 | 风险 | find_class 白名单能否拦下 |
| --- | --- | --- | --- |
| STACK_GLOBAL / GLOBAL | 解析 module.name 得到任意全局对象 | 拿到任意可调用对象 | 能，find_class 是唯一解析入口 |
| REDUCE | 弹出 (callable, args) 并调用 | 反序列化即执行 | 解析已被拦则不会到达 |
| BUILD / NEWOBJ_EX | 调用 __setstate__ 或 __new__ 构造对象 | 触发自定义构造逻辑 | 部分，需把允许的类一并覆盖 |


### sqlite3 的 prepare 与 bind 两阶段为何免疫注入

<Term word='prepared statement 两阶段' text='sqlite3_prepare_v2 先把 SQL 编译成 VDBE 字节码，sqlite3_bind_* 再绑值；语法分析在绑定前完成，值里的引号、OR、注释符只作为数据。' />


## 早退比较的时序侧信道与逐字节爆破

一个内部网关用 32 字节令牌鉴权，验证写成 == 比较，还把耗时打进日志。攻击者先测基线，再逐字节枚举：固定已猜中前缀、对当前字节试 00 到 ff，重复 200 遍取耗时中位数，正确字节让比较多走一字符、耗时略高。32·256·200 约 160 万请求可恢复令牌，暴力枚举 16^32 不可行；

轮换后仍走同一路径，每次轮换都重新泄漏。复盘换 compare_digest、统一错误响应、移除耗时日志并限速。下面把早退步数与恒定步数对照。

```python
def early_exit_steps(a, b):
    steps = 0
    for x, y in zip(a, b):
        steps += 1
        if x != y:
            return steps
    return steps

def constant_steps(a, b):
    n = max(len(a), len(b))
    diff = 0
    for i in range(n):
        x = a[i] if i < len(a) else 0
        y = b[i] if i < len(b) else 0
        diff |= x ^ y
    return n, diff != 0

secret = [7, 3, 9, 1]
for guess in ([0,0,0,0], [7,0,0,0], [7,3,0,0], [7,3,9,0], [7,3,9,1]):
    print('guess', guess, 'early', early_exit_steps(guess, secret), 'const', constant_steps(guess, secret))
```

<Quiz no='113-1' q='关于 pickle 与参数化查询，下面哪项准确？' :options='["pickle 的 REDUCE 会调用 __reduce__ 指定的可调用对象；覆写 find_class 白名单能在解析阶段拦下未知对象", "pickle 协议 5 已经移除 REDUCE，因此对不可信数据是安全的", "覆写 find_class 之后 BUILD 与 NEWOBJ_EX 也一定无法触发构造逻辑", "sqlite3 的 ? 占位符是把值转义后再拼回 SQL，所以注入无效"]' answer="0" explain='REDUCE 在所有协议版本都保留；find_class 是解析全局对象的唯一入口，白名单可挡 STACK_GLOBAL，但 BUILD 仍能触发 __setstate__。占位符靠 prepare 与 bind 让值不入语法分析。' />


## compare_digest 在 CPython 里的常量时间实现

<Exercise title='进阶：审计一段 pickle blob 的 opcode 并写白名单' task='用 genops 列出 blob 的 GLOBAL / STACK_GLOBAL / REDUCE，实现只放行 builtins.len 的 find_class，验证含 builtins.sum 的 blob 被拦截。' solution='import io, pickle, pickletools\n\nclass Payload:\n    def __reduce__(self):\n        return (sum, ([1, 2],))\n\nblob = pickle.dumps(Payload(), protocol=4)\nprint(&#39;ops&#39;, [o[0].name for o in pickletools.genops(blob) if o[0].name in (&#39;GLOBAL&#39;, &#39;STACK_GLOBAL&#39;, &#39;REDUCE&#39;)])\n\nclass OnlyLen(pickle.Unpickler):\n    def find_class(self, module, name):\n        if module == &#39;builtins&#39; and name == &#39;len&#39;:\n            return len\n        raise pickle.UnpicklingError(&#39;blocked&#39;)\n\ntry:\n    OnlyLen(io.BytesIO(blob)).load()\n    print(&#39;verdict&#39;, &#39;loaded&#39;)\nexcept pickle.UnpicklingError:\n    print(&#39;verdict&#39;, &#39;blocked&#39;)' explain='genops 产出三元组，op[0].name 才是 opcode 名；find_class 是解析唯一钩子，拒绝白名单外名字即挡住 REDUCE。' />


## 练习、自测与速记卡

<Exercise title='基础：把拼接 SQL 改成参数化' task='给定 users 表，写一个 find(name) 用 ? 占位符，并用注入串验证它不会返回额外行。' solution='import sqlite3\ndb = sqlite3.connect(&#39;:memory:&#39;)\ndb.execute(&#39;CREATE TABLE u (n TEXT)&#39;)\ndb.execute(&#39;INSERT INTO u VALUES (?)&#39;, (&#39;alice&#39;,))\ndef find(n):\n    return db.execute(&#39;SELECT n FROM u WHERE n = ?&#39;, (n,)).fetchall()\nprint(find(&#39;x&#39; + chr(39) + &#39; OR 1=1&#39;))' explain='占位符让注入串成为普通名字参与匹配，查询返回空列表；值不经过 SQL 解析，引号与 OR 不再改变语义。' />

<Exercise title='进阶：给内部 pickle 缓存加 HMAC 校验' task='写 dump(obj, key) 与 load(blob, key)，用 hmac + sha256 签名，篡改一个字节后 load 抛错，并说明为什么签名不能替代禁止不可信来源。' solution='import pickle, hmac, hashlib\ndef dump(o, k):\n    b = pickle.dumps(o)\n    return hmac.new(k, b, hashlib.sha256).digest() + b\ndef load(blob, k):\n    mac, b = blob[:32], blob[32:]\n    if not hmac.compare_digest(mac, hmac.new(k, b, hashlib.sha256).digest()):\n        raise ValueError(&#39;bad signature&#39;)\n    return pickle.loads(b)\nk = b&#39;secret&#39;\nd = dump([1, 2], k)\nprint(load(d, k))' explain='签名能检测篡改，但持有合法 blob 的构造者仍可在签名前嵌入恶意 __reduce__；因此 pickle 只允许来源完全可信，签名是纵深防御而非安全边界。' />

<Quiz no='113-2' q='关于 pickle，下面哪项描述准确？' :options='["pickle.loads 会执行 __reduce__ 指定的可调用对象，绝不能用于不可信数据", "pickle 协议 5 加入了安全检查，可安全反序列化外部数据", "pickle 只是数据格式，与 json 等价", "只要用 eval 的 globals 限制住就安全"]' answer="0" explain='pickle 是对象构造协议，REDUCE 与 GLOBAL opcode 会按名调用对象，所有协议版本都不提供安全边界；CPython 文档明确警告不要 unpickle 不可信数据。' />

<Quiz no='113-3' q='防止 SQL 注入的正确做法是？' :options='["用占位符把值作为绑定参数传入，结构由预编译模板固定", "对输入里的单引号做转义替换", "用 repr() 包住输入再拼接", "限制输入长度即可"]' answer="0" explain='手工转义容易被多字节编码或不同数据库方言绕过；参数化让值走独立通道不参与解析，才是针对根因的修复。表名列名用白名单。' />

<Quiz no='113-4' q='生成会话令牌应优先用哪个模块？' :options='["secrets.token_hex", "random.random", "hashlib.md5(time)", "uuid.uuid1"]' answer="0" explain='secrets 使用操作系统提供的密码学安全随机源；random 是 Mersenne Twister，可预测，uuid1 含时间与 MAC 也不适合作为凭证。' />

<Predict no='113-5' q='对参数化查询传入 x&#39; OR &#39;1&#39;=&#39;1，safe(uid) 会返回几行？' :options='["0 行，注入串被当作普通名字", "2 行，与拼接版相同", "抛 sqlite3.OperationalError"]' answer='0' output='0 行（safe_rows 0）' explain='占位符把整个注入串绑定成一个字符串值，去匹配 name 列，没有叫这个名字的用户，返回空结果；拼接版才让 OR 恒真拖出全部行。' />

<KnowledgeCard :points='["注入的根因是数据进入解析通道；SQL 用占位符、命令用列表参数且 shell=False", "pickle 是对象构造协议，__reduce__ 可致 RCE；外部数据一律用 json，eval 用 ast.literal_eval", "内部 pickle 需 HMAC 签名 + hmac.compare_digest 常量时间比较，并限制 blob 大小与嵌套深度", "依赖用锁文件固定版本，CI 做 pip-audit 与镜像扫描，并产出 SBOM 记录组件版本", "密钥运行时注入、支持轮换、日志脱敏；令牌用 secrets，口令用 pbkdf2_hmac 加盐", "权限最小化：容器非 root、数据库最小授权、服务间短期凭证，并保留审计与应急轮换流程"]' :pitfalls='["用字符串拼接构造 WHERE 条件", "对来自缓存或接口的字节直接 pickle.loads", "把 .env 与 token 打进镜像或异常日志", "依赖不锁版本、镜像里留 .env、日志里打印 token，等于把入口写进交付物"]' summary='Python 应用最常见的高危问题不在语法层：eval / pickle 处理外部数据、拼接 SQL、把密钥打进镜像或日志，任意一条都能直接导致失陷' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 注入的根因是数据进入解析通道；SQL 用占位符、命令用列表参数且 shell=False | 建立直觉 |
| pickle 是对象构造协议，__reduce__ 可致 RCE；外部数据一律用 json，eval 用 ast.literal_eval | 跑通示例 |
| 内部 pickle 需 HMAC 签名 + hmac.compare_digest 常量时间比较，并限制 blob 大小与嵌套深度 | 深入边界 |
| 依赖用锁文件固定版本，CI 做 pip-audit 与镜像扫描，并产出 SBOM 记录组件版本 | 工程落地 |
| 密钥运行时注入、支持轮换、日志脱敏；令牌用 secrets，口令用 pbkdf2_hmac 加盐 | 随堂检测 |
| 权限最小化：容器非 root、数据库最小授权、服务间短期凭证，并保留审计与应急轮换流程 | 复盘 |

1. 注入的根因是数据进入解析通道；SQL 用占位符、命令用列表参数且 shell=False

2. pickle 是对象构造协议，__reduce__ 可致 RCE；外部数据一律用 json，eval 用 ast.literal_eval

3. 内部 pickle 需 HMAC 签名 + hmac.compare_digest 常量时间比较，并限制 blob 大小与嵌套深度

[下一讲：CPython 源码：对象、帧与求值循环](/advanced/cpython-source)

<FillBlank no='113-6' tpl='___ sqlite3' :answers='["import"]' hint='回想本讲关于 依赖漏洞与 SBOM 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 注入与参数化：SQL 与命令两条入口 的落点。' />
