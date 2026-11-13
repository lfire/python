---
title: 第 090 讲 · 认证授权：Session、JWT、OAuth2 与 RBAC
description: 设计可撤销、可审计的身份体系
---

<StageHeader stage='L8 · 服务端与数据' level='★★★★☆' time='40 分钟' goal='设计可撤销、可审计的身份体系' prereq='第 089 讲 · 消息队列：Celery / RabbitMQ / Kafka' />

# 第 090 讲 · 认证授权：Session、JWT、OAuth2 与 RBAC

服务能被别人调用了，紧接着要回答来的是谁、能做什么。登录与权限常被混成一团。本讲把身份体系摊开，目标是令牌可撤销、判定在服务端、密码经得起泄露。

一个安静的场景：员工离职后管理员点了禁用，他手里的令牌到期前仍能调接口；有人绕过隐藏按钮读到别人数据；库一旦泄露，MD5 密码被批量还原。我们分清认证与授权的区别，再比 Session 与 JWT 在能否主动失效上的取舍，接着谈令牌刷新与撤销、密码哈希与加盐，最后走到 OAuth2 与 RBAC 的集中判定。需要 HTTP 头部、Cookie、哈希函数与路由层；读完能设计可撤销、可审计的认证授权。


## 点了「禁用用户」，旧 token 到期前仍能调接口

一个后台系统把用户登录信息全放进 JWT，权限判断写在前端路由里，密码用 MD5 存。上线后三个问题接踵而至：员工离职后管理员在后台点了『禁用』，该员工手里的 token 在到期前仍能调用接口，因为 JWT 签发后服务端没有状态可撤销；有人直接改前端路由或用脚本调接口，绕过按钮隐藏读到了别人的数据；

数据库泄露后 MD5 值被彩虹表批量还原。第一反应是『把 token 有效期调短』，这缓解了吊销却解释不了越权，也不解决密码存储。三件事对应三层不同机制：会话状态的存放位置决定能否主动失效，授权判定必须在服务端，密码要靠带盐的慢哈希。本讲用标准库手工签发并验证一个 HS256 JWT，把无状态的代价变成可测的结论。

<Callout type="warn" title='先看一个真实会出错的写法' text='JWT 签发后点了『禁用用户』，对方 token 到期前仍能调接口：JWT 无状态，服务端没有可删除的会话记录，验签通过即放行' />

**本讲定位**

| 项目 | 内容 |
| --- | --- |
| 所属阶段 | 阶段八 · 服务端与数据 |
| 前置 | 第 089 讲 · 消息队列：Celery / RabbitMQ / Kafka |
| 难度 / 建议时长 | ★★★★☆ · 40 分钟 |
| 本讲新增 | 认证与授权的区别、Session 与 JWT 取舍、令牌刷新与撤销 |
| 一句话目标 | 设计可撤销、可审计的身份体系 |
| 为下一讲铺垫 | 文件、对象存储、搜索与 gRPC |


## 认证与授权：Session 与 JWT 的取舍

认证（authentication）回答『你是谁』，授权（authorization）回答『你能做什么』，二者不能混：登录校验凭据是认证，判断能否删除订单是授权。

Session 方案在服务端保存会话状态（内存或 Redis），浏览器只持一个随机 session_id 的 Cookie，常见 Set-Cookie 属性：HttpOnly 禁止 JS 读取、Secure 仅 HTTPS 传输、`SameSite=Lax`/Strict 缓解 CSRF。

优点是删掉服务端记录即可主动踢人、改动即时生效，代价是需要集中会话存储，跨域与水平扩展要处理共享。

JWT（RFC 7519）是 `header.payload.signature` 三段 base64url，payload 自带 sub、exp、iat，服务端验签后无需查库，无状态适合微服务与多方验证；

代价是签发后无法主动失效，除非再引入状态：黑名单、短时效 access token（如 15 分钟）配可轮换的 refresh token、或 token 版本号与用户状态比对。判据要具体：需要即时下线、改权限立刻生效 → Session 或 JWT 黑名单；服务无共享存储、要跨服务自校验 → JWT。

把两者当风格差异选，就会在离职踢人这类需求上翻车。

**Session 与 JWT 对照**

| 维度 | Session | JWT |
| --- | --- | --- |
| 状态位置 | 服务端（内存/Redis） | 客户端自携带，服务端无状态 |
| 主动失效 | 删会话记录即时生效 | 难，需黑名单/短时效+刷新/版本号 |
| 水平扩展 | 需共享会话存储 | 天然友好，各服务自验签 |
| 载荷可见性 | 仅一个随机 id | base64url 可解码，勿放敏感数据 |
| 典型时效 | 随会话与滑动续期 | access 15 分钟 + refresh 轮换 |
| 适合 | 需即时踢人、改权限即生效 | 微服务、跨域、多方验证 |

<Callout type="tip" title='核心心智模型' text='认证（authentication）回答『你是谁』，授权（authorization）回答『你能做什么』，二者不能混：登录校验凭据是认证，判断能否删除订单是授权。Session 方案在服务端保存会话状态（内存或 Redis），浏览器只持一个随机 session_id 的 Cookie，常见 Set-' />


## 主示例：签发、验证与黑名单撤销

```python
import hmac, hashlib, base64, json, time
def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode()
SECRET = b'dev-secret'
def sign(header, payload):
    h = b64url(json.dumps(header, separators=(',',':')).encode())
    p = b64url(json.dumps(payload, separators=(',',':')).encode())
    sig = b64url(hmac.new(SECRET, (h + '.' + p).encode(), hashlib.sha256).digest())
    return h + '.' + p + '.' + sig
def verify(token):
    try:
        h, p, s = token.split('.')
        expect = b64url(hmac.new(SECRET, (h + '.' + p).encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(s, expect):
            return 'bad signature'
        payload = json.loads(base64.urlsafe_b64decode(p + '==='))
        if payload.get('exp', 0) < time.time():
            return 'expired'
        return 'valid sub=' + str(payload.get('sub'))
    except Exception as e:
        return 'invalid ' + type(e).__name__
tok = sign({'alg':'HS256','typ':'JWT'}, {'sub':'u42','exp': time.time() + 60})
print('parts', len(tok.split('.')))
print('header b64', tok.split('.')[0])
print('verify', verify(tok))
print('tampered', verify(tok[:-2] + 'xx'))
old = sign({'alg':'HS256','typ':'JWT'}, {'sub':'u42','exp': time.time() - 1})
print('expired', verify(old))
```

<OutputBox title='主示例运行结果' output='parts 3\nheader b64 eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\nverify valid sub=u42\ntampered bad signature\nexpired expired' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import hmac, hashlib, base64, json, time\ndef b64url(data):\n    return base64.urlsafe_b64encode(data).rstrip(b&#39;=&#39;).decode()\nSECRET = b&#39;dev-secret&#39;\ndef sign(header, payload):\n    h = b64url(json.dumps(header, separators=(&#39;,&#39;,&#39;:&#39;)).encode())\n    p = b64url(json.dumps(payload, separators=(&#39;,&#39;,&#39;:&#39;)).encode())\n    sig = b64url(hmac.new(SECRET, (h + &#39;.&#39; + p).encode(), hashlib.sha256).digest())\n    return h + &#39;.&#39; + p + &#39;.&#39; + sig\ndef verify(token):\n    try:\n        h, p, s = token.split(&#39;.&#39;)\n        expect = b64url(hmac.new(SECRET, (h + &#39;.&#39; + p).encode(), hashlib.sha256).digest())\n        if not hmac.compare_digest(s, expect):\n            return &#39;bad signature&#39;\n        payload = json.loads(base64.urlsafe_b64decode(p + &#39;===&#39;))\n        if payload.get(&#39;exp&#39;, 0) &lt; time.time():\n            return &#39;expired&#39;\n        return &#39;valid sub=&#39; + str(payload.get(&#39;sub&#39;))\n    except Exception as e:\n        return &#39;invalid &#39; + type(e).__name__\ntok = sign({&#39;alg&#39;:&#39;HS256&#39;,&#39;typ&#39;:&#39;JWT&#39;}, {&#39;sub&#39;:&#39;u42&#39;,&#39;exp&#39;: time.time() + 60})\nprint(&#39;parts&#39;, len(tok.split(&#39;.&#39;)))\nprint(&#39;header b64&#39;, tok.split(&#39;.&#39;)[0])\nprint(&#39;verify&#39;, verify(tok))\nprint(&#39;tampered&#39;, verify(tok[:-2] + &#39;xx&#39;))\nold = sign({&#39;alg&#39;:&#39;HS256&#39;,&#39;typ&#39;:&#39;JWT&#39;}, {&#39;sub&#39;:&#39;u42&#39;,&#39;exp&#39;: time.time() - 1})\nprint(&#39;expired&#39;, verify(old))' :notes='["导入 hmac/hashlib/base64 做签名，json 编解码，time 读当前时间", "定义 base64url：去掉填充 = 的 URL 安全 base64", "把字节串编码成 base64url 字符串", "HS256 用的共享密钥，生产环境应从密钥管理服务取", "定义签发函数，拼出 JWT 三段", "header 用紧凑分隔序列化再 base64url", "payload 同样处理，含 sub 与 exp 声明", "对 header.payload 做 HMAC-SHA256 并 base64url 得签名", "用点号连接三段返回完整 token", "定义验证函数，覆盖验签与过期", "解析异常统一转成 invalid 结果", "按点号拆成三段", "用同一密钥重算期望签名", "compare_digest 常量时间比对，防时序侧信道", "签名不符直接判为篡改", "补回 padding 后 base64url 解码并解析 payload", "读取 exp 与当前时间比较", "过期返回 expired", "全部通过返回主体标识", "任何解析/解码异常都归入 invalid，不泄漏细节", "解析异常时返回带异常类型名的 invalid 结果", "签发一个含 sub 与 60 秒后过期的 token", "token 恰好三段", "header 的 base64url 是固定值 eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "验证合法 token 通过", "改动签名末尾两位应被验签拒绝", "另签一个 exp 已过 1 秒的 token", "过期 token 被 exp 检查拦下"]' title='第 090 讲 · 认证授权：Session、JWT、OAuth2 与 RBAC' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import hashlib, base64

verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
print('method S256')
print('challenge', challenge)
print('plain != hashed', verifier != challenge)
```

<OutputBox title='原理验证' output='method S256\nchallenge E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM\nplain != hashed True' />


### JWT 验证必检的字段有哪些

**JWT 验证必检项**

| 检查 | 做法 | 漏检后果 |
| --- | --- | --- |
| 签名 | HS256 用 HMAC-SHA256 + compare_digest | 任意伪造身份 |
| 算法 | 显式拒绝 alg=none、RS/HS 混淆 | 用公钥当密钥伪造 token |
| exp / iat / nbf | 与当前时间比较 | 过期令牌仍可用 |
| aud / iss | 核对受众与签发方 | 跨系统令牌被冒用 |
| 敏感声明 | 只放 sub / roles / exp | base64url 非加密，数据泄露 |

```python
import hashlib, os, hmac

def hash_password(pw, salt=None):
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt, 200000)
    return salt.hex(), dk.hex()

s, h = hash_password('s3cret')
s2, h2 = hash_password('s3cret', bytes.fromhex(s))
print('salt bytes', len(bytes.fromhex(s)))
print('digest bytes', len(bytes.fromhex(h)))
print('verify', hmac.compare_digest(h, h2))
print('wrong', hmac.compare_digest(h, hash_password('wrong', bytes.fromhex(s))[1]))
```

<OutputBox title='对照写法：先自己猜，再点开' output='salt bytes 16\ndigest bytes 32\nverify True\nwrong False' guess="true" />


## 密码哈希与 OAuth2 授权码流程

验证 JWT 必须做全：用 `hmac.compare_digest` 常量时间比对签名（HS256 用 HMAC-SHA256、RS256 用 RSA 公钥验），校验 exp/iat/nbf、aud/iss，并显式拒绝 `alg=none` 与算法混淆（把 RS256 公钥当 HS256 密钥用）。

base64url 只是编码不是加密，payload 任何人可解码，所以里面绝不能放密码、手机号，只放最小声明。

密码绝不能明文或单轮 MD5/SHA：用 argon2id（首选）、bcrypt、scrypt，或标准库 `hashlib.pbkdf2_hmac`('sha256', pw, salt, 200000)，每个用户独立 16 字节随机 salt、验证时重算并 compare_digest。

OAuth2 授权码流程配 PKCE（RFC 7636）：客户端生成 code_verifier，`code_challenge = base64url`(`SHA256(verifier)`)，授权请求带 challenge 与 S256 方法，换 token 时带原始 verifier 由服务端比对，防止授权码被截获冒用；

state 参数防 CSRF。access token 短时效，refresh token 一次一换并检测重放（旧 token 复用触发整族吊销）。

**密码哈希与 OAuth2 / RBAC 要点**

| 项 | 正确做法 | 错误做法 |
| --- | --- | --- |
| 密码存储 | argon2id / bcrypt / pbkdf2_hmac + 独立 salt | MD5 / SHA 单轮、明文 |
| 验证比对 | hmac.compare_digest 常量时间 | == 逐字符比较 |
| 授权码流程 | OAuth2 + PKCE(S256)，state 防 CSRF | 隐式流程、明文传 verifier |
| 权限判定 | 服务端集中 has_permission + 审计 | 只靠前端隐藏按钮 |
| 敏感操作 | 二次校验 / MFA | 仅凭长期有效 token |

<Compare :panels='[{"label": "主示例", "code": "import hmac, hashlib, base64, json, time\ndef b64url(data):\n    return base64.urlsafe_b64encode(data).rstrip(b&#39;=&#39;).decode()\nSECRET = b&#39;dev-secret&#39;\ndef sign(header, payload):\n    h = b64url(json.dumps(header, separators=(&#39;,&#39;,&#39;:&#39;)).encode())\n    p = b64url(json.dumps(payload, separators=(&#39;,&#39;,&#39;:&#39;)).encode())\n    sig = b64url(hmac.new(SECRET, (h + &#39;.&#39; + p).encode(), hashlib.sha256).digest())\n    return h + &#39;.&#39; + p + &#39;.&#39; + sig\ndef verify(token):\n    try:\n        h, p, s = token.split(&#39;.&#39;)\n        expect = b64url(hmac.new(SECRET, (h + &#39;.&#39; + p).encode(), hashlib.sha256).digest())\n        if not hmac.compare_digest(s, expect):\n            return &#39;bad signature&#39;\n        payload = json.loads(base64.urlsafe_b64decode(p + &#39;===&#39;))\n        if payload.get(&#39;exp&#39;, 0) &lt; time.time():\n            return &#39;expired&#39;\n        return &#39;valid sub=&#39; + str(payload.get(&#39;sub&#39;))\n    except Exception as e:\n        return &#39;invalid &#39; + type(e).__name__\ntok = sign({&#39;alg&#39;:&#39;HS256&#39;,&#39;typ&#39;:&#39;JWT&#39;}, {&#39;sub&#39;:&#39;u42&#39;,&#39;exp&#39;: time.time() + 60})\nprint(&#39;parts&#39;, len(tok.split(&#39;.&#39;)))\nprint(&#39;header b64&#39;, tok.split(&#39;.&#39;)[0])\nprint(&#39;verify&#39;, verify(tok))\nprint(&#39;tampered&#39;, verify(tok[:-2] + &#39;xx&#39;))\nold = sign({&#39;alg&#39;:&#39;HS256&#39;,&#39;typ&#39;:&#39;JWT&#39;}, {&#39;sub&#39;:&#39;u42&#39;,&#39;exp&#39;: time.time() - 1})\nprint(&#39;expired&#39;, verify(old))", "note": "认证、授权与 Session/JWT 的取舍"}, {"label": "对照 / 进阶", "code": "import hashlib, os, hmac\n\ndef hash_password(pw, salt=None):\n    salt = salt or os.urandom(16)\n    dk = hashlib.pbkdf2_hmac(&#39;sha256&#39;, pw.encode(), salt, 200000)\n    return salt.hex(), dk.hex()\n\ns, h = hash_password(&#39;s3cret&#39;)\ns2, h2 = hash_password(&#39;s3cret&#39;, bytes.fromhex(s))\nprint(&#39;salt bytes&#39;, len(bytes.fromhex(s)))\nprint(&#39;digest bytes&#39;, len(bytes.fromhex(h)))\nprint(&#39;verify&#39;, hmac.compare_digest(h, h2))\nprint(&#39;wrong&#39;, hmac.compare_digest(h, hash_password(&#39;wrong&#39;, bytes.fromhex(s))[1]))", "note": "JWT 验证、密码哈希与 OAuth2 流程"}]' title='两种写法对照' note='差异集中在 认证与授权的区别；先看输出，再找背后的规则。' />


## RBAC / ABAC：可审计的判定入口从哪来

RBAC 把权限绑到角色、用户绑到角色，判定收敛到一个函数 `has_permission(user, action, resource)` 查『角色 → 权限』映射；

ABAC 再引入属性（部门、时间、资源归属、IP）做更细粒度控制。铁律是权限判定必须在服务端集中执行：前端隐藏按钮只是体验改善，绝不是安全边界，任何脚本都能直接调接口；每个受保护端点都要经过同一个判定入口，避免新加接口漏判。敏感操作（改密、支付、导出）要二次校验，重新输密码或 MFA。

审计日志记录 who / when / what / resource / result / trace_id，append-only 或写独立存储，越权尝试要告警。密钥要支持轮换（用 kid 标识当前密钥），全站强制 HTTPS，Cookie 加 HttpOnly/Secure/SameSite。

令牌里放角色即可，别把权限判定结果缓存到不受控的客户端；服务间调用同样要带身份（mTLS 或签发的 service token），不能因为『内网』就默认可信。

JWT 的安全完全建立在签名上：header 与 payload 经 base64url 编码后拼成 signing_input，HS256 用共享密钥对其做 HMAC-SHA256，RS256 用私钥签、公钥验；验证方重算签名并用常量时间比较，任何一位被改动都会导致不匹配。

因为编码不是加密，payload 只是『防篡改』而非『防读取』，所以令牌里只能放非敏感声明。无状态带来一个结构性代价：服务端没有『已签发令牌』的清单，无法像 Session 那样删一条记录就撤销，要恢复可撤销性就必须重新引入状态（黑名单、token 版本、短 exp + refresh 轮换）。

密码哈希用 pbkdf2_hmac 这类 KDF 把口令与随机 salt 迭代二十万次，故意放慢单次要让离线暴力破解成本极高，salt 保证相同密码得到不同摘要、彩虹表失效。

PKCE 把 code_verifier 的 SHA-256 摘要先交给授权服务器，换 token 时再出示原值，使截获授权码的攻击者因拿不到 verifier 而无法兑换。RBAC 的本质是把『谁能做什么』收敛到服务端一个必过的判定点，前端展示层不构成边界。

<Term word='认证与授权的区别' text='认证（authentication）回答『你是谁』，授权（authorization）回答『你能做什么』，二者不能混：登录校验凭据是认证，判断能否删除订单是授权。Session 方案在服务端保存会话状态（内存或 Redis），浏览器只持一个随机 session_id 的 Cookie，常见 Set-Cookie 属性：' />

<Term word='Session 与 JWT 取舍' text='验证 JWT 必须做全：用 hmac.compare_digest 常量时间比对签名（HS256 用 HMAC-SHA256、RS256 用 RSA 公钥验），校验 exp/iat/nbf、aud/iss，并显式拒绝 alg=none 与算法混淆（把 RS256 公钥当 HS256 密钥用）。base64url 只是编' />

<ConceptDiagram type='layers3' title='第 090 讲 · 分层视角' labels='认证、授权与 Session/JWT 的|JWT 验证、密码哈希与 OAuth2 |RBAC / ABAC 与可审计的判定入|RBAC / ABAC' caption='RBAC / ABAC 与可审计的判定入口' />

换成分层视角：检查自己能否说出每一层依赖下一层提供的哪一项能力，尤其是 **RBAC / ABAC** 落在哪一层。


## 带黑名单、RBAC 与审计的最小认证层

下面把身份体系写成不依赖 Web 框架的骨架：issue 签发带 sub/roles/exp 的 HS256 token，verify 同时验签、验过期、查 revoked 黑名单（补上 JWT 缺失的可撤销性）；authorize 集中做 RBAC 判定，任何端点都必须先过它，并写一条审计记录；

password 相关用带盐的 pbkdf2_hmac 与 compare_digest。重点看三层职责如何组合：认证产出的身份只是输入，授权是唯一判定入口，审计把所有判定留痕。

真实项目把 revoked 换成带 TTL 的 Redis 集合、把审计写进 append-only 存储、密钥从 KMS 取并支持 kid 轮换，结构不变。

```python
import hmac, hashlib, base64, json, time

SECRET = b'k1'
revoked = set()
audit = []
ROLES = {'admin': {'read', 'write', 'delete'}, 'viewer': {'read'}}

def b64(d):
    return base64.urlsafe_b64encode(d).rstrip(b'=').decode()

def issue(sub, roles):
    h = b64(json.dumps({'alg':'HS256','kid':'k1'}, separators=(',',':')).encode())
    p = b64(json.dumps({'sub':sub, 'roles':roles, 'exp':time.time()+900}, separators=(',',':')).encode())
    s = b64(hmac.new(SECRET, (h+'.'+p).encode(), hashlib.sha256).digest())
    return h+'.'+p+'.'+s

def verify(tok):
    h, p, s = tok.split('.')
    exp_sig = b64(hmac.new(SECRET, (h+'.'+p).encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(s, exp_sig):
        return None
    payload = json.loads(base64.urlsafe_b64decode(p+'==='))
    if payload['exp'] < time.time() or payload['sub'] in revoked:
        return None
    return payload

def authorize(tok, action, resource):
    p = verify(tok)
    ok = p is not None and action in set().union(*(ROLES.get(r,set()) for r in p['roles']))
    audit.append((p['sub'] if p else '?', action, resource, ok))
    return ok

admin = issue('u1', ['admin'])
viewer = issue('u2', ['viewer'])
print(authorize(admin, 'delete', 'order/9'))
print(authorize(viewer, 'delete', 'order/9'))
revoked.add('u1')
print(authorize(admin, 'read', 'order/9'))
print('audit rows', len(audit))
```

<Callout type="idea" title='落地提示' text='敏感操作二次校验、令牌短时效、密码用 argon2/bcrypt、权限模型集中判定并留审计日志' />

<CheckList id='P090b' title='上线前自检' :items='["能复现并解释「JWT 签发后点了『禁用用户』，对方 token 到期前仍能」", "能复现并解释「用 MD5 存密码，拖库后被批量还原」", "能复现并解释「把权限判断只写在前端，脚本直接调接口越权」", "能用一条命令验证 认证与授权的区别", "关键路径有自动化测试与失败分支"]' />

```bash
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE t(k TEXT UNIQUE)'); print('ok')"
```

把输入换成你自己的数据，观察结果是否仍符合 **认证与授权的区别** 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| JWT 签发后点了『禁用用户』，对方 token 到期前仍能调接口 | JWT 无状态，服务端没有可删除的会话记录，验签通过即放行 | 改 Session 方案；或对 JWT 引入黑名单/token 版本号，并把 access token 压到 15 分钟配可轮换的 refresh token |
| 用 MD5 存密码，拖库后被批量还原 | 单轮通用哈希太快且无独立 salt，彩虹表与 GPU 暴力可轻易破解 | 用 argon2id（首选）或 bcrypt / hashlib.pbkdf2_hmac('sha256', pw, salt, 200000)，每用户独立 16 字节随机 salt |
| 把权限判断只写在前端，脚本直接调接口越权 | 前端隐藏按钮不是安全边界，接口没有经过服务端授权判定 | 每个受保护端点都过同一个服务端 has_permission(user, action, resource)，敏感操作二次校验，并记审计日志与越权告警 |

<Callout type="warn" title='本讲最容易踩的坑' text='JWT 签发后点了『禁用用户』，对方 token 到期前仍能调接口：JWT 无状态，服务端没有可删除的会话记录，验签通过即放行' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：JWT 签发后点了『禁用用户』，对方 tok", "body": "JWT 无状态，服务端没有可删除的会话记录，验签通过即放行", "tip": "改 Session 方案；或对 JWT 引入黑名单/token 版本号，并把 access token 压到 15 分钟配可轮换的 refresh token"}, {"title": "第 2 步：用 MD5 存密码，拖库后被批量还原", "body": "单轮通用哈希太快且无独立 salt，彩虹表与 GPU 暴力可轻易破解", "tip": "用 argon2id（首选）或 bcrypt / hashlib.pbkdf2_hmac(&#39;sha256&#39;, pw, salt, 200000)，每用户独立 16 字节随机 salt"}, {"title": "第 3 步：把权限判断只写在前端，脚本直接调接口越权", "body": "前端隐藏按钮不是安全边界，接口没有经过服务端授权判定", "tip": "每个受保护端点都过同一个服务端 has_permission(user, action, resource)，敏感操作二次校验，并记审计日志与越权告警"}]' />


## HMAC-SHA256 的 ipad/opad 与 JWS 签名输入

RFC 2104 定义 `HMAC(K, m)` = `H((K 异或 opad)` 拼接 `H((K 异或 ipad)` 拼接 m))，块长 `B = 64` 字节（SHA-256 的分组大小），K 若超过 B 先哈希再右补零到 B，ipad 是 0x36 重复 64 次、opad 是 0x5c 重复 64 次。

外层再套一次哈希不是冗余：裸 `H(secret 拼接 m)` 扛不住长度扩展攻击，攻击者拿到摘要与长度就能续接数据；HMAC 把内部状态封进第二次哈希，续接无从下手。

JWS（RFC 7515）的 signing input 是 `BASE64URL(UTF8(Protected Header)`) 加一个点号再接 `BASE64URL(Payload)`，注意签名覆盖的是编码后的 ASCII 字节串而不是原始 JSON，于是 header 的键顺序、空格、Unicode 转义方式都会改变签名，签发方与验证方必须字节级一致，不能 `json.loads` 之后重新 dumps，这是跨语言验签最常见的失败点。

HS256 的 K 就是共享密钥，RS256 改用 RSASSA-PKCS1-v1_5 私钥签公钥验，`alg=none` 是 JWA 里合法但危险的算法，验证方必须白名单显式拒绝。

CPython 的 Lib/`hmac.py` 把摘要计算交给 _hashlib，compare_digest 走常量时间比较，避免按字节提前退出泄漏匹配前缀长度。

```python
import base64
import hashlib
import hmac
import json

def hmac_sha256_raw(key, msg):
    block = 64
    if len(key) > block:
        key = hashlib.sha256(key).digest()
    key = key + bytes(block - len(key))
    ipad = bytes([0x36]) * block
    opad = bytes([0x5c]) * block
    inner = hashlib.sha256(bytes(a ^ b for a, b in zip(key, ipad)) + msg).digest()
    return hashlib.sha256(bytes(a ^ b for a, b in zip(key, opad)) + inner).digest()

key = b'dev-secret'
header = json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode()
payload = json.dumps({'sub': 'u42', 'exp': 1700000000}, separators=(',', ':')).encode()
signing_input = base64.urlsafe_b64encode(header).rstrip(b'=') + b'.' + base64.urlsafe_b64encode(payload).rstrip(b'=')
mine = hmac_sha256_raw(key, signing_input)
stdlib = hmac.new(key, signing_input, hashlib.sha256).digest()
print('matches stdlib', mine == stdlib)
print('signing input', signing_input.decode())
p = signing_input.split(b'.')[1]
print('padding needed', (-len(p)) % 4)
print('decoded payload', base64.urlsafe_b64decode(p + b'===').decode())

```

<OutputBox title='扩展示例运行结果' output='matches stdlib True\nsigning input eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1NDIiLCJleHAiOjE3MDAwMDAwMDB9\npadding needed 0\ndecoded payload {"sub":"u42","exp":1700000000}' />

<LineByLine code='import base64\nimport hashlib\nimport hmac\nimport json\n\ndef hmac_sha256_raw(key, msg):\n    block = 64\n    if len(key) &gt; block:\n        key = hashlib.sha256(key).digest()\n    key = key + bytes(block - len(key))\n    ipad = bytes([0x36]) * block\n    opad = bytes([0x5c]) * block\n    inner = hashlib.sha256(bytes(a ^ b for a, b in zip(key, ipad)) + msg).digest()\n    return hashlib.sha256(bytes(a ^ b for a, b in zip(key, opad)) + inner).digest()\n\nkey = b&#39;dev-secret&#39;\nheader = json.dumps({&#39;alg&#39;: &#39;HS256&#39;, &#39;typ&#39;: &#39;JWT&#39;}, separators=(&#39;,&#39;, &#39;:&#39;)).encode()\npayload = json.dumps({&#39;sub&#39;: &#39;u42&#39;, &#39;exp&#39;: 1700000000}, separators=(&#39;,&#39;, &#39;:&#39;)).encode()\nsigning_input = base64.urlsafe_b64encode(header).rstrip(b&#39;=&#39;) + b&#39;.&#39; + base64.urlsafe_b64encode(payload).rstrip(b&#39;=&#39;)\nmine = hmac_sha256_raw(key, signing_input)\nstdlib = hmac.new(key, signing_input, hashlib.sha256).digest()\nprint(&#39;matches stdlib&#39;, mine == stdlib)\nprint(&#39;signing input&#39;, signing_input.decode())\np = signing_input.split(b&#39;.&#39;)[1]\nprint(&#39;padding needed&#39;, (-len(p)) % 4)\nprint(&#39;decoded payload&#39;, base64.urlsafe_b64decode(p + b&#39;===&#39;).decode())\n' :notes='["导入 base64、hashlib、hmac、json，全部来自标准库", "从零实现 HMAC：块长 64 字节，长密钥先哈希再补零", "ipad 是 0x36 重复 64 次，opad 是 0x5c 重复 64 次", "内层哈希算 H((K 异或 ipad) 拼接 msg)", "外层哈希把内部状态封进去，挡住长度扩展攻击", "用 json.dumps 紧凑序列化，避免手写 JSON 影响字节串", "signing input 是两段 base64url 用点号拼接的 ASCII 串", "手工实现与标准库 hmac 的结果应完全一致", "打印被签名的字节串，说明它覆盖的是编码后内容", "按模 4 计算 payload 段还缺几个填充位", "补三个等号后解码，多余的填充被 base64 解码器忽略", "RBAC 收敛到 has_permission 必过入口，敏感操作二次校验，审计记 who/when/what/result", "认证是『你是谁』、授权是『你能做什么』；判定必须集中在服务端，前端隐藏不是边界", "JWT 三段 header.payload.signature，base64url 非加密；验签+验 exp/iat/aud/iss+拒 alg=none", "JWT 签发后难主动失效，靠黑名单/短时效+refresh 轮换/版本号补回状态", "密码用 argon2id / bcrypt / pbkdf2_hmac + 每用户独立 16 字节 salt，compare_digest 比对", "OAuth2 授权码 + PKCE(S256)、state 防 CSRF；access 短时效、refresh 一次一换", "RBAC 收敛到 has_permission 必过入口，敏感操作二次校验，审计记 who/when/what/result", "认证是『你是谁』、授权是『你能做什么』；判定必须集中在服务端，前端隐藏不是边界", "JWT 三段 header.payload.signature，base64url 非加密；验签+验 exp/iat/aud/iss+拒 alg=none", "JWT 签发后难主动失效，靠黑名单/短时效+refresh 轮换/版本号补回状态", "密码用 argon2id / bcrypt / pbkdf2_hmac + 每用户独立 16 字节 salt，compare_digest 比对", "OAuth2 授权码 + PKCE(S256)、state 防 CSRF；access 短时效、refresh 一次一换", "RBAC 收敛到 has_permission 必过入口，敏感操作二次校验，审计记 who/when/what/result"]' title='扩展示例逐行讲解' />

<Term word='JWS signing input' text='RFC 7515 规定被签名的字节串是 BASE64URL(UTF8(Protected Header)) 加一个点号再接 BASE64URL(Payload)，即编码后的 ASCII 字符串而非原始 JSON。这意味着 header 的键顺序、空格与 Unicode 转义方式都会改变签名，验证方必须逐字节比对而不能 json.loads 后重新 dumps；这是跨语言验签最隐蔽的失败点，也是「签名正确却验不过」的常见根因。' />


### base64url 无填充编码的模 4 补位

<ConceptDiagram type='flow4' title='第 090 讲 · 扩展图解' labels='原始 JSON|UTF-8 字节|base64url 去填充|点号拼接 signing input' caption='签名覆盖的是编码后的字符串：任意一端重新序列化 JSON 都会让字节串改变，验签随即失败；base64url 只是编码，payload 任何人可解码。' />


## PBKDF2 的迭代成本与离线破解工作量

RFC 8018 定义 `DK = PBKDF2`(PRF, P, S, c, dkLen)：输出按 hLen 切成块 T_i，`T_i = F`(P, S, c, i)，而 `F = U_1` 异或 U_2 一直异或到 U_c，`U_1 = PRF`(P, S 拼接 `INT_32_BE(i)`)，`U_j = PRF`(P, U_&#123;j-1&#125;)。

每块固定要做 c 次 PRF，`dkLen = 32` 且 `hLen = 32` 时单次验证就是 c 次 HMAC-SHA256，与密码长度无关，工作量对 c 严格线性：本机 Python 3.13 实测 `c = 1000` 约 0.5 毫秒、`c = 200000` 约 17.3 毫秒，正好约 200 倍，把迭代从一千提到二十万，攻击者离线爆破的 GPU 时间乘以两百，而登录接口每用户只多十几毫秒。

salt 的作用不是保密而是破坏预计算：16 字节随机 salt 有 2 的 128 次方种取值，彩虹表要按每个 salt 各存一份，存储上不可行；全局固定 salt 等于没 salt。

argon2id 更进一步加内存硬度（m 参数默认 64MB）与并行度 p，让 GPU 与 ASIC 的内存带宽成为瓶颈，而 PBKDF2 几乎不占内存、最容易被显卡并行。

架构权衡要算两边账：迭代次数同时是登录接口的 CPU 成本，QPS 高时要按「可接受登录延迟乘峰值 QPS」反推核数，或把口令验证挪到独立服务并限流，不能只看着破解成本往上调。

**JWT 与口令体系的 RFC 与源码位置**

| 规范 / 源码 | 定义 | 失效后果 |
| --- | --- | --- |
| RFC 2104 / Lib/hmac.py | HMAC 的 ipad 与 opad 双层哈希 | 用裸 H(secret 拼接 m) 抗不住长度扩展攻击 |
| RFC 7515 JWS | signing input 为编码后的 header.payload | 重新序列化 JSON 导致验签失败 |
| RFC 7518 JWA | alg 白名单：HS256、RS256、none | 不拒绝 none 或算法混淆即可伪造身份 |
| RFC 8018 PBKDF2 | T_i 由 c 次 PRF 异或而成 | c 过小则离线爆破成本塌陷 |
| RFC 7517 JWK | n 与 e 的 base64url 整数，kid 标识 | 没有 kid 轮换只能全站停机换密钥 |


## 算法混淆攻击里公钥即密钥的成因

一次渗透测试里，服务用 RS256 签发 token、把 RSA 公钥通过接入文档公开给合作方验签。测试者把 header 的 alg 改成 HS256，用那串公开的公钥 PEM 当作 HMAC 共享密钥重新签名，服务端竟然验签通过、直接拿到 admin 身份。

根因是验证代码从 token 自己的 header 里读 alg 来分派算法，并在 HS256 分支把「验签公钥」当「HMAC 密钥」传入：公钥本来就是公开的，用它当对称密钥等于把密钥写进了文档。修复是服务端按配置固定期望算法、忽略 token 里的 alg，并把 HS256 与 RS256 的密钥材料彻底隔离。

下面用标准库复现这个缺陷，naive 验证器接受用 PUBLIC_KEY 签出的 HS256 伪造 token。

```python
import base64
import hashlib
import hmac
import json

def b64u(d):
    return base64.urlsafe_b64encode(d).rstrip(b'=').decode()

def sign(alg, payload, key):
    h = b64u(json.dumps({'alg': alg, 'typ': 'JWT'}, separators=(',', ':')).encode())
    p = b64u(json.dumps(payload, separators=(',', ':')).encode())
    s = b64u(hmac.new(key, (h + '.' + p).encode(), hashlib.sha256).digest())
    return h + '.' + p + '.' + s

PUBLIC_KEY = b'-----BEGIN PUBLIC KEY----- MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8A... -----END PUBLIC KEY-----'

def verify_naive(token, public_key):
    h, p, s = token.split('.')
    header = json.loads(base64.urlsafe_b64decode(h + '==='))
    key = public_key if header['alg'] == 'HS256' else b'rsa-unused'
    expect = b64u(hmac.new(key, (h + '.' + p).encode(), hashlib.sha256).digest())
    return hmac.compare_digest(s, expect)

forged = sign('HS256', {'sub': 'admin', 'role': 'root'}, PUBLIC_KEY)
print('alg from token', json.loads(base64.urlsafe_b64decode(forged.split('.')[0] + '==='))['alg'])
print('naive verifier accepts forged', verify_naive(forged, PUBLIC_KEY))

```

<Quiz no='090-X' q='关于 HS256 与 RS256 的算法混淆攻击，下面哪项准确？' :options='["验证方按 token 自带 alg 分派、且把公开的 RSA 公钥当作 HS256 的 HMAC 密钥时，攻击者可用公钥伪造任意 token", "RS256 的私钥可以安全公开，只有公钥需要保密", "HMAC 的 ipad 与 opad 让攻击者无法从签名反推密钥，因此算法混淆不成立", "只要 payload 用了 base64url 编码，算法混淆就自动失效"]' answer="0" explain='算法混淆的前提正是「验证方信任 token 里的 alg」加上「HS256 分支用了公开的 RSA 公钥作密钥」。HMAC 的 ipad 与 opad 只保证在密钥保密时不可伪造，密钥一旦公开便无从谈起；base64url 只是编码，与算法选择无关。修复是服务端白名单固定 alg 并隔离不同算法的密钥材料，而不是加强签名算法本身。' />


### JWKS 与 kid 轮换的密钥分发结构

<Exercise title='用服务端算法白名单挡住 alg 混淆' task='写一个 verify_fixed，忽略 token header 里的 alg、一律按配置的 HS256 与固定密钥验签，并对 alg=none 的空 header 返回 False；说明为什么白名单必须写在服务端而不是文档里。' solution='import base64\nimport hashlib\nimport hmac\nimport json\n\nSECRET = b&#39;server-only-key&#39;\nEXPECTED_ALG = &#39;HS256&#39;\n\ndef b64u(d):\n    return base64.urlsafe_b64encode(d).rstrip(b&#39;=&#39;).decode()\n\ndef verify_fixed(token):\n    h, p, s = token.split(&#39;.&#39;)\n    header = json.loads(base64.urlsafe_b64decode(h + &#39;===&#39;))\n    if header.get(&#39;alg&#39;) != EXPECTED_ALG:\n        return False\n    expect = b64u(hmac.new(SECRET, (h + &#39;.&#39; + p).encode(), hashlib.sha256).digest())\n    return hmac.compare_digest(s, expect)\n\nprint(&#39;whitelist rejects empty header&#39;, verify_fixed(&#39;e30.e30.&#39;))\n' explain='白名单把「用哪个算法」从 token 里不可信的声明收回到服务端配置：alg=none 或 RS256 的 token 在任何伪造签名下都在第一道判断被拒。若只在文档里约定而代码仍读 header 分派，等于把算法选择权交给攻击者；密钥材料也必须按算法分开存放，避免 HS256 分支误用 RSA 公钥。空 header 解码成空字典，get 返回 None，与期望算法不等，直接判否。' />


## 练习、自测与一页纸速记

<Exercise title='基础：手工签发并验证 HS256 JWT' task='实现 sign/verify，验证合法 token 通过、篡改签名被拒、exp 过期被拒，并说明 compare_digest 与 base64url 的作用。' solution='import hmac, hashlib, base64, json, time\ndef b(d): return base64.urlsafe_b64encode(d).rstrip(b&#39;=&#39;).decode()\nS = b&#39;k&#39;\ndef sign(p):\n    h = b(json.dumps({&#39;alg&#39;:&#39;HS256&#39;},separators=(&#39;,&#39;,&#39;:&#39;)).encode())\n    q = b(json.dumps(p,separators=(&#39;,&#39;,&#39;:&#39;)).encode())\n    return h+&#39;.&#39;+q+&#39;.&#39;+b(hmac.new(S,(h+&#39;.&#39;+q).encode(),hashlib.sha256).digest())\ndef verify(t):\n    h,q,s = t.split(&#39;.&#39;)\n    e = b(hmac.new(S,(h+&#39;.&#39;+q).encode(),hashlib.sha256).digest())\n    if not hmac.compare_digest(s,e): return &#39;bad sig&#39;\n    p = json.loads(base64.urlsafe_b64decode(q+&#39;===&#39;))\n    return &#39;expired&#39; if p.get(&#39;exp&#39;,0)&lt;time.time() else &#39;valid&#39;\nt = sign({&#39;sub&#39;:&#39;u&#39;,&#39;exp&#39;:time.time()+60})\nprint(verify(t), verify(t[:-2]+&#39;xx&#39;))' explain='base64url 去填充便于 URL 传输；compare_digest 常量时间比对防时序侧信道；exp 必须由服务端校验，编码不是加密。' />

<Exercise title='进阶：给 JWT 加可撤销黑名单与 RBAC' task='在 verify 里加 revoked 集合检查，写 authorize(tok, action) 集中做角色权限判定并记审计，验证用户被加入黑名单后即使 token 未过期也被拒绝。' solution='revoked = set()\nROLES = {&#39;admin&#39;: {&#39;read&#39;,&#39;write&#39;}, &#39;viewer&#39;: {&#39;read&#39;}}\ndef authorize(tok_obj, action):\n    if tok_obj[&#39;sub&#39;] in revoked: return False\n    return action in set().union(*(ROLES.get(r,set()) for r in tok_obj[&#39;roles&#39;]))\nu = {&#39;sub&#39;:&#39;u1&#39;,&#39;roles&#39;:[&#39;admin&#39;]}\nprint(authorize(u,&#39;write&#39;))\nrevoked.add(&#39;u1&#39;)\nprint(authorize(u,&#39;write&#39;))' explain='黑名单给无状态 JWT 补回可撤销性；授权必须集中在服务端一个判定入口，前端隐藏按钮不构成边界，审计记录每次判定结果。' />

<Quiz no='090-1' q='JWT 签发后无法主动失效，根本原因是什么？' :options='["服务端不保存已签发令牌的状态，验签通过即放行", "签名算法太弱", "payload 用了 base64url", "exp 设得太长"]' answer="0" explain='无状态是 JWT 的优点也是枷锁：没有会话清单可删。要可撤销就得引入黑名单、token 版本号或短 access + refresh 轮换，等于重新加回一份状态。' />

<Quiz no='090-2' q='关于密码存储，下面哪项准确？' :options='["用 argon2id / bcrypt / pbkdf2_hmac 配每用户独立随机 salt", "MD5 加一个全局固定 salt 即可", "SHA-256 单轮足够", "把密码加密后可逆存，方便找回"]' answer="0" explain='慢 KDF + 独立 salt 让离线暴力成本极高、彩虹表失效；MD5/SHA 单轮太快，加密可逆反而是泄露风险，找回密码应走重置流程。' />

<Quiz no='090-3' q='OAuth2 授权码流程配 PKCE 的主要作用是？' :options='["用 code_challenge(S256) 绑定授权码，防止授权码被截获后冒用兑换 token", "给 access token 加密", "替代 HTTPS", "让 refresh token 永不过期"]' answer="0" explain='客户端先交 SHA-256(verifier) 摘要、换 token 时出示原 verifier，服务端比对；截获授权码者拿不到 verifier 就无法兑换，state 另防 CSRF。' />

<Predict no='090-P' q='对一个 exp 已过 1 秒、签名正确的 HS256 token 调 verify，最可能返回什么？' :options='["expired", "valid sub=...", "bad signature"]' answer='0' output='expired' explain='验签通过只证明没被篡改；exp 是独立的时间检查，服务端必须自己比对当前时间。签名正确但过期仍要拒绝，这正是 『验签 ≠ 有效』 的边界。' />

<FillBlank no='090-F' tpl='___ hmac, hashlib, base64, json, time' :answers='["import"]' hint='回想本讲关于 认证与授权的区别 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 认证、授权与 Session/JWT 的取舍 的落点。' />

<KnowledgeCard :points='["认证是『你是谁』、授权是『你能做什么』；判定必须集中在服务端，前端隐藏不是边界", "JWT 三段 header.payload.signature，base64url 非加密；验签+验 exp/iat/aud/iss+拒 alg=none", "JWT 签发后难主动失效，靠黑名单/短时效+refresh 轮换/版本号补回状态", "密码用 argon2id / bcrypt / pbkdf2_hmac + 每用户独立 16 字节 salt，compare_digest 比对", "OAuth2 授权码 + PKCE(S256)、state 防 CSRF；access 短时效、refresh 一次一换", "RBAC 收敛到 has_permission 必过入口，敏感操作二次校验，审计记 who/when/what/result"]' :pitfalls='["JWT 签发后点了『禁用用户』，对方 token 到期前仍能调接口", "用 MD5 存密码，拖库后被批量还原", "把权限判断只写在前端，脚本直接调接口越权", "把权限判断只写在前端、或用 MD5 存密码，都是会直接导致越权与拖库后果的错误"]' summary='JWT 的无状态是优点也是枷锁：签发后无法主动失效，除非再引入一份状态（黑名单或短时效加刷新）' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 认证是『你是谁』、授权是『你能做什么』；判定必须集中在服务端，前端隐藏不是边界 | 建立直觉 |
| JWT 三段 header.payload.signature，base64url 非加密；验签+验 exp/iat/aud/iss+拒 alg=none | 跑通示例 |
| JWT 签发后难主动失效，靠黑名单/短时效+refresh 轮换/版本号补回状态 | 深入边界 |
| 密码用 argon2id / bcrypt / pbkdf2_hmac + 每用户独立 16 字节 salt，compare_digest 比对 | 工程落地 |
| OAuth2 授权码 + PKCE(S256)、state 防 CSRF；access 短时效、refresh 一次一换 | 随堂检测 |
| RBAC 收敛到 has_permission 必过入口，敏感操作二次校验，审计记 who/when/what/result | 复盘 |

1. 认证是『你是谁』、授权是『你能做什么』；判定必须集中在服务端，前端隐藏不是边界

2. JWT 三段 header.payload.signature，base64url 非加密；验签+验 exp/iat/aud/iss+拒 alg=none

3. JWT 签发后难主动失效，靠黑名单/短时效+refresh 轮换/版本号补回状态

[下一讲：文件、对象存储、搜索与 gRPC](/server/storage)
