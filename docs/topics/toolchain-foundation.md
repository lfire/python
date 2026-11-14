---
title: 工程底座：Linux、Git、SQL 与多版本
description: 把代码放到别人机器与流水线之前要补齐的权限、Shell、协作、数据库、解释器版本与锁版本功夫。
---

# 工程底座：Linux、Git、SQL 与多版本

072 讲把依赖管理讲透了，但依赖装好只代表代码能在本机跑。一旦交给同事、丢上服务器、塞进流水线，绕不开的是另一层：文件读权限、日志汇总、分支合并时不把密钥带上去、数据落到哪张表、查询会不会被注入、以及同一份代码凭什么在另一台机器上行为一致。这些场景在「生态地图」里列了名字，正文一直没落地。这一篇按一台机器从里到外补齐：先摸清权限与常用命令，再用管道和重定向串起文本处理，接着把协作与防泄漏立成规矩（Git 与 `.gitignore`），然后给数据找个可靠去处（表设计、多表 JOIN、索引与参数化），最后解决多版本、镜像与锁版本，汇到一个能直接抄的 CI 示例里。

## 文件权限、属主与常用命令

Linux 里每个文件都带三组权限位，分别给属主、属组、其他人，每组是读、写、执行三位。`ls -l` 打出的 `-rw-r-----` 要拆成四段读：首位是类型（`-` 普通文件、`d` 目录、`l` 链接），后面三个字符一组。`r` 是 4、`w` 是 2、`x` 是 1，所以 `rw-r-----` 对应 `640`。目录的 `x` 不是「能运行」，而是「能进入」；想列出目录内容，得同时有 `r` 和 `x`。`chmod` 改权限，`chown` 改属主，`umask` 决定新建文件的默认权限。

| 八进制 | 符号 | 对普通文件 | 对目录 |
| --- | --- | --- | --- |
| `4` | `r--` | 读内容 | 列出目录项（还需 `x`） |
| `2` | `-w-` | 改写内容 | 增删目录项（还需 `x`） |
| `1` | `--x` | 作为程序执行 | 进入目录、访问其中元数据 |
| `6` | `rw-` | 读写 | 通常不单独用于目录 |
| `7` | `rwx` | 读写执行 | 完整进入、列、改 |

| 命令 | 用途 | 常见组合 |
| --- | --- | --- |
| `ls -l` `stat` | 看权限、属主、大小、时间 | `ls -la` 连隐藏文件一起看 |
| `chmod` `chown` | 改权限与属主 | `chmod 640 app.env`、`chown -R app:app /srv/app` |
| `find` | 按名字、时间、大小找文件 | `find . -name "*.log" -mtime +7` |
| `grep` | 在文本里筛行 | `grep -R "ERROR" /var/log` |
| `du` `df` | 目录占用与磁盘余量 | `du -sh *`、`df -h` |
| `ps` `kill` `top` | 查进程、发信号、看负载 | `ps aux \| grep python` |
| `tar` `curl` | 打包与下载 | `tar -czf app.tgz app/`、`curl -fsSL URL` |
| `ss` `lsof` | 看监听端口与打开文件 | `ss -ltnp` |

```bash
# 看权限、改权限、按条件找文件
ls -l app.env                       # -rw-r--r-- ... app.env
chmod 640 app.env                   # 属主可读写，属组只读，其他人无权
stat -c "%a %U:%G %n" app.env       # 640 app:app app.env（GNU/Linux 写法）
find . -name "*.log" -mtime +7 -delete
```

```python
import os
import stat
from pathlib import Path

p = Path("demo.txt")
p.write_text("hello\n", encoding="utf-8")
os.chmod(p, 0o640)

st = p.stat()
mode = stat.S_IMODE(st.st_mode)
print(oct(mode))                       # 0o640
print(stat.filemode(st.st_mode))       # -rw-r-----
print(bool(mode & stat.S_IRUSR), bool(mode & stat.S_IRGRP), bool(mode & stat.S_IWOTH))
# True True False
print(st.st_size)                      # 6
p.unlink()
```

`stat.S_IMODE` 把 `st_mode` 里的类型位剥掉，只留权限九位，再用 `stat.S_IRUSR` 这类常量做按位与，就能精确判断「属主能否读」「其他人能否写」。这套位运算在写部署检查脚本时比解析 `ls -l` 的字符串可靠得多。生产环境里给配置文件 `600`、给目录 `750`，比图省事上 `777` 安全。

## 管道、重定向与文本处理

Shell 的核心思路是「每个命令只做一件事，用 `|` 把上一个的标准输出接到下一个的标准输入」。`>` 覆盖写文件，`>>` 追加，`<` 从文件读，`2>` 单独接错误输出，`2>&1` 把错误并进标准输出，`/dev/null` 丢弃。`&&` 只有前一条成功才继续，`;` 无论成败都往下走。配合 `grep`、`sort`、`uniq -c`、`awk`、`wc -l`、`head`、`tail`，一条命令就能完成日志汇总，不用先把文件读进 Python。

```bash
# 统计 access.log 里各级别出现次数，从多到少排前 5
grep -oE "\[(INFO|WARN|ERROR)\]" access.log | sort | uniq -c | sort -rn | head -5
# 等价的拆分：先抽字段，再排序去重计数，最后按次数倒序

# 标准输出进文件、错误输出也进同一文件、后台任务不挂终端
python -m app.worker > worker.log 2>&1 &

# 只看末尾新增行，常用于盯线上日志
tail -f /var/log/app/error.log | grep --line-buffered "Traceback"
```

```python
from collections import Counter

lines = [
    "2026-11-13 [INFO] started",
    "2026-11-13 [WARN] slow query",
    "2026-11-13 [INFO] ok",
    "2026-11-13 [ERROR] timeout",
    "2026-11-13 [WARN] retry",
]
levels = [ln.split("[")[1].split("]")[0] for ln in lines]
print(Counter(levels))
# Counter({'INFO': 2, 'WARN': 2, 'ERROR': 1})
print(sorted(Counter(levels).items()))
# [('ERROR', 1), ('INFO', 2), ('WARN', 2)]
```

上面这段 Python 复刻了 `sort | uniq -c` 的效果。取舍很清楚：一次性统计、数据已经在内存里，用 `Counter` 更好读；数据是一个还在增长的日志文件、要边写边看，交给 `tail -f` 和管道更合适。`grep -oE`、`sort`、`uniq -c` 这些命令里的花括号和方括号是参数的一部分，写进代码块就不用担心被当成模板语法。

## 分支、合并、回滚与 .gitignore 防泄漏

日常协作的最小闭环是：从主干切分支、在分支上提交、合回主干、发现问题时回滚。`git switch -c` 建并切到新分支，`git merge` 把一条分支合进当前分支，`git rebase` 把提交重放到目标分支之上、得到线性历史但改写了提交号，所以只适合还没推给别人共享的分支。回滚要分清两种：`git revert` 新增一个「反向提交」来抵消某次改动，历史继续向前，适合已经推送的共享分支；`git reset` 直接把分支指针挪回去，配合 `--hard` 还会丢掉工作区改动，只适合本地未推送的提交。`git restore` 只动工作区、不动历史，用来撤销误改的文件。

| 操作 | 是否改写历史 | 能否用于已推送的共享分支 | 适用场景 |
| --- | --- | --- | --- |
| `git revert <commit>` | 否，新增反向提交 | 可以 | 线上回滚、多人协作分支 |
| `git reset --hard <commit>` | 是，移动分支指针 | 禁止 | 本地未推送的错误提交 |
| `git restore <file>` | 否 | 可以 | 丢弃单个文件的未提交改动 |
| `git rebase main` | 是，重写提交号 | 不建议 | 自己的特性分支整理提交 |
| `git merge --no-ff` | 否 | 可以 | 保留一次合并的边界 |

```bash
git switch -c feature/rate-limit
git add src/limit.py && git commit -m "add token bucket"
git push -u origin feature/rate-limit
# 评审通过后合回主干
git switch main && git merge --no-ff feature/rate-limit
# 上线后发现这次合并有问题：用 revert 回滚，不动历史
git revert -m 1 HEAD
git push origin main
```

`.gitignore` 要在第一次提交之前就建好，规则是按行匹配的：`*.pyc` 忽略所有编译产物，`__pycache__/` 忽略目录，`.env` 忽略本地密钥，`venv/` 忽略虚拟环境，前置 `!` 表示例外放行。已经提交过的文件不会因为补一条规则就自动从仓库消失，得先 `git rm --cached`，而且这只删索引、不清历史，密钥一旦进过历史就必须轮换。

```bash
# 项目根 .gitignore 的常见骨架
cat > .gitignore <<'EOF'
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.env
.env.*
!.env.example
*.log
dist/
build/
.coverage
EOF
git rm --cached .env                    # 只从索引移除，文件仍留在本地
git add .gitignore && git commit -m "chore: ignore local secrets"
```

```python
from fnmatch import fnmatch
from pathlib import PurePosixPath

IGNORE = ["*.pyc", "__pycache__", ".env", "*.log", "secrets*", "*.egg-info"]
KEEP = [".env.example"]

def ignored(path):
    name = PurePosixPath(path).name
    parts = set(PurePosixPath(path).parts)
    hit = (any(fnmatch(name, pat) for pat in IGNORE)
           or bool(parts & {"__pycache__", ".venv", "venv"}))
    if name in KEEP:
        hit = False
    return hit

cases = [".env", ".env.example", "mod/__pycache__/x.pyc", "app.log",
         "src/main.py", "venv/bin/python", "secrets.toml"]
for p in cases:
    print(p, ignored(p))
# .env True
# .env.example False
# mod/__pycache__/x.pyc True
# app.log True
# src/main.py False
# venv/bin/python True
# secrets.toml True
```

这个迷你判断器演示了忽略规则的两层逻辑：文件名通配匹配，外加目录名命中与白名单豁免。真实 `.gitignore` 还支持 `**`、`/` 锚定和逐目录继承，逻辑更复杂，但「先判断命中、再处理 `!` 例外」这个顺序是一致的。上线前可以用它扫一遍待提交清单，拦住 `.env` 和私钥文件。

## MySQL 表设计：主外键、字段类型与范式

关系型设计的第一步是把实体拆成表、给每行一个稳定主键，再用外键表达「谁属于谁」。字段类型要按数据特性选：整数用 `INT` 或 `BIGINT`，金额绝不用 `FLOAT` 而用 `DECIMAL(10, 2)`，变长短文本用 `VARCHAR(n)`，长文本用 `TEXT`，时间用 `DATETIME` 并统一时区口径，字符集一律 `utf8mb4` 以支持完整的中文与 emoji。主键用 `BIGINT AUTO_INCREMENT` 或业务无关的雪花 ID，外键列加 `NOT NULL` 并建索引，`ON DELETE` 行为要显式写出来。

| 字段 | 类型 | 选择与理由 |
| --- | --- | --- |
| 主键 `id` | `BIGINT UNSIGNED AUTO_INCREMENT` | 无业务含义、不会被改动 |
| 金额 | `DECIMAL(12, 2)` | 定点数，避免浮点累加误差 |
| 用户名 | `VARCHAR(64)` | 有长度上限，可建索引 |
| 详情文本 | `TEXT` | 不定长、不参与频繁检索 |
| 状态 | `TINYINT` 或枚举 | 取值有限，配注释说明每个值 |
| 创建时间 | `DATETIME(3)` | 精确到毫秒，统一存 UTC |
| 字符集 | `utf8mb4` / `utf8mb4_0900_ai_ci` | 完整 Unicode 与排序规则 |

```sql
CREATE TABLE users (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(64) NOT NULL,
    city VARCHAR(32),
    created_at DATETIME(3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE orders (
    id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT UNSIGNED NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    status TINYINT NOT NULL DEFAULT 0,
    CONSTRAINT fk_orders_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE RESTRICT,
    INDEX idx_orders_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

上面的语法以 MySQL 8 为例。为了让这些关系能在不装服务端的情况下亲手跑通，下面用标准库 `sqlite3` 建同样的两张表：外键约束要显式 `PRAGMA foreign_keys = ON`，插入不存在的 `user_id` 会被拒绝，`LEFT JOIN` 能把没有订单的用户也留在结果里，空聚合自然得到 `None`。

```python
import sqlite3

con = sqlite3.connect(":memory:")
con.execute("PRAGMA foreign_keys = ON")
con.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
""")
con.executemany("INSERT INTO users VALUES (?, ?, ?)",
                [(1, "alice", "北京"), (2, "bob", "上海"), (3, "carol", "北京")])
con.executemany("INSERT INTO orders VALUES (?, ?, ?)",
                [(101, 1, 88.50), (102, 1, 240.00), (103, 2, 19.90)])
con.commit()

rows = con.execute("""
    SELECT u.name, COUNT(o.id), SUM(o.amount)
    FROM users u LEFT JOIN orders o ON o.user_id = u.id
    GROUP BY u.id ORDER BY u.name
""").fetchall()
print(rows)
# [('alice', 2, 328.5), ('bob', 1, 19.9), ('carol', 0, None)]

try:
    con.execute("INSERT INTO orders VALUES (?, ?, ?)", (104, 999, 1.0))
except sqlite3.IntegrityError as e:
    print(type(e).__name__)     # IntegrityError
```

## 多表 JOIN、索引与执行计划

JOIN 的本质是把两张表按某个条件拼成一张临时表再筛选。`INNER JOIN` 只留两边都命中的行，`LEFT JOIN` 保留左表全部行、右表没配上就填 `NULL`，`RIGHT JOIN` 反之（MySQL 没有 `FULL OUTER JOIN`）。`ON` 写连接条件、`WHERE` 写结果过滤，把过滤条件错放进 `ON` 会改变 `LEFT JOIN` 的语义。多表关联时先想清楚「以哪张表为主」，比事后调 SQL 更省事。

| JOIN 类型 | 保留哪些行 | 未匹配侧 | 典型用途 |
| --- | --- | --- | --- |
| `INNER JOIN` | 两表都命中 | 丢弃 | 只统计有订单的用户 |
| `LEFT JOIN` | 左表全部 | 右表填 `NULL` | 列出所有用户及其订单数（含 0） |
| `RIGHT JOIN` | 右表全部 | 左表填 `NULL` | 以明细表为主反查维度 |
| 自连接 | 同一张表的两个别名 | 视条件 | 上下级、相邻记录比较 |

索引让数据库不必全表扫描。最常用的是 B+ 树索引，适合等值、范围和排序；联合索引遵循最左前缀，`INDEX(a, b)` 能加速 `WHERE a=?` 和 `WHERE a=? AND b=?`，但帮不上只按 `b` 查的语句。区分度低的列（如性别）建索引收益很小，写多读少的表也要控制索引数量，因为每次写入都要维护索引。判断有没有走上索引，用 `EXPLAIN` 看执行计划，别凭感觉。

```python
import sqlite3

con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, level TEXT, msg TEXT)")
levels = ["INFO", "WARN", "ERROR"]
con.executemany("INSERT INTO events (level, msg) VALUES (?, ?)",
                [(levels[i % 3], "m%d" % i) for i in range(3000)])
con.commit()

q = "SELECT msg FROM events WHERE level = 'WARN'"
def plan_detail():
    return con.execute("EXPLAIN QUERY PLAN " + q).fetchall()[0][-1]

before = plan_detail()
print(before)                            # 示意：SCAN events
con.execute("CREATE INDEX idx_events_level ON events(level)")
after = plan_detail()
print(after)                             # 示意：SEARCH events USING INDEX idx_events_level (level=?)
print("USING INDEX" in before, "USING INDEX" in after)   # False True
```

建索引前 `EXPLAIN QUERY PLAN` 给出全表扫描，建完同一条查询变成按索引检索。最后一行是确定输出，两段计划文本标了「示意」，因为不同 SQLite 版本的描述文案略有差异，重点看「有没有用到索引」这个结论。

## SQL 注入与参数化查询

把用户输入用字符串拼接进 SQL，等于让输入自己决定语句结构。经典 payload 是用户名填 `alice' --`：拼出来的语句里后面的密码校验被注释掉，于是无需密码就能查到记录。更狠的输入还能闭合引号后追加删除语句。修复只有一条原则：值永远走占位符，让驱动把参数当数据而不是 SQL 片段；表名、列名、排序方向这类不能参数化的标识符，用代码里的白名单枚举，绝不接受客户端原样传入。

| 场景 | 危险写法 | 正确写法 |
| --- | --- | --- |
| 登录校验 | `f"... name='{name}' ..."` | `execute("... name=? ...", (name,))` |
| 批量插入 | 循环里逐条拼 `VALUES` | `executemany(sql, rows)` |
| MySQL 驱动 | `%s` 手拼 | 游标 `execute(sql, (v,))` 传 `%s` |
| 动态排序 | 直接拼 `ORDER BY {col}` | 从 `{"time", "amount"}` 白名单取值 |
| `LIKE` 模糊查询 | 拼 `%` 与输入 | 参数里拼好 `f"%{kw}%"` 再绑定 |

```python
import sqlite3

con = sqlite3.connect(":memory:")
con.execute("CREATE TABLE users (name TEXT, password TEXT)")
con.executemany("INSERT INTO users VALUES (?, ?)",
                [("alice", "s3cret"), ("bob", "pwd")])
con.commit()

def login_bad(name, password):
    sql = f"SELECT name FROM users WHERE name='{name}' AND password='{password}'"
    return con.execute(sql).fetchone()

def login_ok(name, password):
    return con.execute("SELECT name FROM users WHERE name=? AND password=?",
                       (name, password)).fetchone()

attack = "alice' --"
print(login_bad(attack, "anything"))    # ('alice',)  被注入绕过
print(login_ok(attack, "anything"))     # None        整串被当成普通用户名
print(login_bad("alice", "s3cret"))     # ('alice',)
print(login_ok("alice", "s3cret"))      # ('alice',)
```

<Callout type='tip' title='占位符风格由驱动决定' text='sqlite3 用问号，mysqlclient 与 PyMySQL 用百分号 s，psycopg 也用百分号 s；无论哪种，值都作为第二个参数传给 execute，而不是拼进第一个字符串' />

注意 `LIKE` 那一行：`%` 通配符要拼进参数值里，绑定仍由驱动完成，这不算拼接 SQL。ORM 的过滤方法底层同样是参数化，但一旦动用「原生 SQL 片段」接口，就又回到了手工转义的老路上。

## 多版本取舍：pyenv、Anaconda 与 venv

这三者管的不是同一层东西，混用是环境错乱的主要来源。`pyenv` 切换的是「系统里有哪些 Python 解释器、当前目录用哪个版本」，只管解释器不管依赖；`venv` 用标准库给单个项目建一个隔离的 `site-packages`，是服务部署和 CI 的默认选择；Anaconda 与 `conda` 同时管解释器、依赖和一批编译好的数值二进制包，适合数据科学，但体积大、和 `pip` 混装时容易把依赖树搞乱。一个务实的组合是：用 `pyenv` 选版本，每个项目用 `python -m venv` 隔离依赖，把 `.venv/` 写进 `.gitignore`，只在需要大量科学计算库时才单开 conda 环境。

| 工具 | 管什么 | 隔离粒度 | 典型命令 | 主要坑 |
| --- | --- | --- | --- | --- |
| `pyenv` | 解释器版本 | 全局或按目录 | `pyenv install 3.12.7`、`pyenv local 3.11.9` | 不隔离依赖，`shim` 未生效会用到系统 Python |
| `venv` | 项目依赖 | 单项目一个目录 | `python -m venv .venv`、`source .venv/bin/activate` | 目录别提交、别移动，移动后脚本里的路径失效 |
| Anaconda / `conda` | 解释器加依赖加二进制包 | 命名的环境 | `conda create -n py312 python=3.12`、`conda activate py312` | 与 `pip` 混装易冲突，镜像和 channel 要统一 |

```bash
pyenv install 3.12.7
pyenv local 3.12.7                      # 写入 .python-version
python -m venv .venv
source .venv/bin/activate               # Windows 用 .venv\Scripts\activate
python -m pip install -U pip
python -m pip install requests flask
python -m pip freeze > requirements.txt
```

```python
import sys
import sysconfig

print(sys.version_info[:3])                  # 示意：(3, 12, 7)
print(sys.prefix != sys.base_prefix)         # 示意：True（已激活 venv）
print(sysconfig.get_path("purelib"))         # 示意：.../.venv/lib/python3.12/site-packages
print("site-packages" in sysconfig.get_path("purelib"))   # True
```

`sys.prefix` 与 `sys.base_prefix` 不相等，就是「当前跑在某个虚拟环境里」的可靠判据，比检查环境变量 `VIRTUAL_ENV` 更直接；最后一行是确定输出，可以用来在启动脚本里断言「必须运行在隔离环境中」。前三行数值随机器变化，看的是比较逻辑而不是具体版本。

## 国内镜像、锁版本与可复现安装

「在我机器上是好的」多半不是代码问题，而是依赖没锁死：`requirements.txt` 只写 `requests>=2.28`，某天上游发版，CI 装到的就是另一个传递依赖组合。可复现安装需要三件事——精确版本的锁文件、区分运行依赖与开发依赖、以及安装时校验哈希。国内网络下再配一层镜像，把下载速度和不稳定连接的问题一起解决。

| 做法 | 命令或文件 | 解决什么 | 注意 |
| --- | --- | --- | --- |
| 冻结当前环境 | `pip freeze > requirements.txt` | 快速记录已装版本 | 混入开发依赖、没有哈希 |
| 编译锁文件 | `uv pip compile`、`pip-compile`、`poetry lock` | 固定传递依赖的精确版本 | 必须提交进仓库 |
| 哈希校验 | `pip install --require-hashes -r requirements.txt` | 防解析漂移与包被替换 | 每条依赖都要带 `--hash` |
| 配置镜像 | `pip config set global.index-url ...` | 国内下载加速 | 镜像可能滞后官方源几小时 |
| 分离依赖组 | `requirements.txt` 与 `requirements-dev.txt` | 生产镜像不装测试工具 | CI 里分别安装 |

```bash
# 国内镜像（以镜像站当前文档为准）
python -m pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
# 单次临时指定
python -m pip install -i https://mirrors.aliyun.com/pypi/simple/ requests
# 生成锁文件并提交；CI 里按锁文件严格安装
uv pip compile pyproject.toml -o requirements.lock
python -m pip install --require-hashes -r requirements.lock
```

```python
import re

text = "requests>=2.28\nflask==3.0.2\nnumpy\nclick==8.1.7\npytest>=7.0,<8.0\n"
LOCKED = re.compile(r"^[A-Za-z0-9_.-]+==[0-9][A-Za-z0-9.+-]*$")

for line in text.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    print(line, "已锁定" if LOCKED.fullmatch(line) else "待锁定")
# requests>=2.28 待锁定
# flask==3.0.2 已锁定
# numpy 待锁定
# click==8.1.7 已锁定
# pytest>=7.0,<8.0 待锁定
```

这个检查把「写死了精确版本」和「只写了范围或干脆没写版本」分开，可以在提交前当预检脚本用：只要出现「待锁定」，就说明这份依赖清单还不具备可复现性。真正的锁文件还会把传递依赖和哈希一并固定，比逐行手写的 `==` 更严格。

## 把底座接进 CI 的最小示例

把前面所有零件串起来，最小可用的流水线只做五步：拉代码、装一个确定的 Python 版本、按锁文件装依赖、跑静态检查与测试、连一个真实数据库服务跑集成用例。密钥通过平台的 secrets 注入环境变量，绝不写进仓库；数据库用临时容器，测完即弃。

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: ci_test
          MYSQL_DATABASE: app_test
        ports: ["3306:3306"]
        options: --health-cmd="mysqladmin ping" --health-retries=10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - name: 建虚拟环境并按锁文件安装
        run: |
          python -m venv .venv
          . .venv/bin/activate
          pip install --require-hashes -r requirements.lock
          pip install -r requirements-dev.txt
      - name: 静态检查与测试
        run: |
          . .venv/bin/activate
          ruff check . && python -m pytest -q
        env:
          DATABASE_URL: mysql+pymysql://root:ci_test@127.0.0.1:3306/app_test
```

```bash
# 本地复现同一套动作，避免 CI 成为唯一能跑的地方
python -m venv .venv && source .venv/bin/activate
pip install --require-hashes -r requirements.lock
pip install -r requirements-dev.txt
ruff check . && python -m pytest -q
```

这里每一步都对应前面某一节：`setup-python` 固定解释器版本、虚拟环境隔离依赖、`--require-hashes` 消费锁文件、`DATABASE_URL` 从环境变量读而不是硬编码、`.gitignore` 保证 `.venv` 和 `.env` 从来没进过仓库。CI 只是把本地已经成立的规矩自动执行一遍。

## 常见坑 / 边界与合规

1. **密钥提交后才补 `.gitignore`**：规则只对未跟踪文件生效，`git rm --cached` 也只删索引、历史里的密钥仍可检出。修复：立刻轮换该密钥与所有派生令牌，把 `.gitignore` 和 `.env.example` 一起提交，历史清理交给 `git filter-repo` 一类工具，且以「已轮换」为完成标准。
2. **在共享分支上 `reset --hard` 加强推**：会抹掉别人已经拉取的提交。修复：线上回滚一律用 `git revert`，把 `--hard` 和 `push -f` 限制在本地未推送的分支，并在仓库里配分支保护。
3. **用 f-string 拼 SQL 或把用户输入拼进 Shell 命令**：前者是注入，后者是命令注入。修复：SQL 值全部参数化、标识符走白名单；调外部程序用 `subprocess.run` 传参数列表而不是拼一整条字符串，绝不启用 `shell=True` 接用户输入。
4. **生产环境图省事用 `chmod 777` 或数据库 root 账号**：一旦某个进程被攻破，横向扩散没有阻力。修复：按最小权限建专用系统账号与数据库账号，配置文件 `600`、目录 `750`，只授予应用需要的库表权限。
5. **日志里落完整身份证、手机号、卡号**：属于合规事故，脱敏补在事后也洗不掉已写出的磁盘与备份。修复：写入前统一做字段级掩码，密钥类信息一律不进日志，并给「应被脱敏」的格式配反向用例，防止新加的字段绕过掩码。

::: details 练习 1 · 手写权限串转换
不调用 `stat.filemode`，写一个函数把八进制权限位（如 `0o754`）转成 `ls -l` 风格的十字符权限串，并验证三个输入。提示：把九位权限每三位一组，按 `rwx` 与按位与逐位拼。

```python
# 参考解
def perm_str(mode):
    out = "-"
    for shift in (6, 3, 0):
        bits = (mode >> shift) & 0b111
        out += "".join(ch if bits & (1 << (2 - i)) else "-"
                       for i, ch in enumerate("rwx"))
    return out

for m in (0o754, 0o640, 0o600):
    print(oct(m), perm_str(m))
# 0o754 -rwxr-xr--
# 0o640 -rw-r-----
# 0o600 -rw-------
```
:::

::: details 练习 2 · 参数化插入后按城市汇总
用 `sqlite3` 建 `users` 与 `orders` 两张表，用 `executemany` 参数化插入数据，再用 `JOIN` 与 `GROUP BY` 统计每个城市的消费总额，按城市排序输出。要求所有数据写入都走占位符。

```python
# 参考解
import sqlite3

con = sqlite3.connect(":memory:")
con.executescript("""
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, city TEXT);
CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL);
""")
con.executemany("INSERT INTO users VALUES (?, ?, ?)",
                [(1, "alice", "北京"), (2, "bob", "上海"), (3, "carol", "北京")])
con.executemany("INSERT INTO orders VALUES (?, ?, ?)",
                [(1, 1, 88.5), (2, 1, 11.5), (3, 2, 200.0), (4, 3, 50.0)])
con.commit()
q = ("SELECT u.city, SUM(o.amount) FROM users u "
     "JOIN orders o ON o.user_id = u.id "
     "GROUP BY u.city ORDER BY u.city")
print(con.execute(q).fetchall())
# [('上海', 200.0), ('北京', 150.0)]
```
:::

回到 [专题补遗](/topics/) · [课程总目录](/guide/curriculum)


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能跑通本专题按正文顺序整理的标准库示例；需要第三方库的片段会自动跳过并打印安装提示，不装任何库也能看到核心结果。" />

**本专题示例代码** · 仓内路径 `examples/topics/toolchain-foundation.py`

```bash
python3 examples/topics/toolchain-foundation.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/topics/toolchain-foundation.py) · [全部示例代码索引](/examples/)
