"""工程底座：Linux、Git、SQL 与多版本 —— 专题补遗可运行示例。

课程页：/topics/toolchain-foundation
GitHub：https://github.com/lfire/python/blob/main/examples/topics/toolchain-foundation.py
依赖：全部使用 Python 标准库（os、stat、pathlib、collections、fnmatch、sqlite3、
      sys、sysconfig、re）；sqlite3 用内存数据库，无第三方包、无需外部服务。
运行：python3 examples/topics/toolchain-foundation.py
说明：本文件按专题正文出现的顺序，把 tools/course/topics/toolchain-foundation.md
      中的全部 python 代码块整理到一个脚本里；每段前的方括号标明对应章节与演示内容。
      源文里的 bash、sql、yaml 命令示例不属于 python 代码块，故不收录、也不执行。
"""

import os
import re
import stat
import sys
import sysconfig
import sqlite3
from collections import Counter
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

# [1. 文件权限、属主与常用命令] 用 stat.S_IMODE 与权限常量精确判断读写位
# demo.txt 是本段自建、自删的临时演练文件
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

# [2. 管道、重定向与文本处理] 用 Counter 复刻 sort | uniq -c 的日志级别统计
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

# [3. 分支、合并、回滚与 .gitignore 防泄漏] 迷你忽略规则判断器
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

# [4. MySQL 表设计：主外键、字段类型与范式] 用 sqlite3 跑主外键、LEFT JOIN 与外键拒绝
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

# [5. 多表 JOIN、索引与执行计划] 用 EXPLAIN QUERY PLAN 看建索引前后的变化
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

# [6. SQL 注入与参数化查询] 对比拼接 SQL 被注入绕过与参数化查询
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

# [7. 多版本取舍：pyenv、Anaconda 与 venv] 用 sys 判断是否处在虚拟环境
print(sys.version_info[:3])                  # 示意：(3, 12, 7)
print(sys.prefix != sys.base_prefix)         # 示意：True（已激活 venv）
print(sysconfig.get_path("purelib"))         # 示意：.../.venv/lib/python3.12/site-packages
print("site-packages" in sysconfig.get_path("purelib"))   # True

# [8. 国内镜像、锁版本与可复现安装] 用正则区分已锁定与待锁定的依赖行
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

# [练习 1 · 参考解] 手写把八进制权限位转成 ls -l 风格十字符权限串
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

# [练习 2 · 参考解] 参数化插入后按城市汇总消费总额
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
