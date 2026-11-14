"""
第 123 讲 · 实战 02 · 文件检索、日志与自动化办公
与教程正文一一对应的示例代码

课程页面：/projects/office-files
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/123-office-files.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/123-office-files.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# by ext [('.png', 2, 400), ('.txt', 2, 160)]
# rename plan [('report.TXT', 'report.txt'), ('pic2.PNG', 'pic2.png')]
# applied 0
# audit ['INFO|rename report.TXT -> report.txt', 'INFO|rename pic2.PNG -> pic2.png']

import logging, tempfile
from pathlib import Path
from collections import defaultdict

root = Path(tempfile.mkdtemp())
(root / 'docs').mkdir()
(root / 'docs' / 'report.TXT').write_bytes(b'x' * 120)
(root / 'notes.txt').write_bytes(b'x' * 40)
(root / 'pic.png').write_bytes(b'x' * 300)
(root / 'pic2.PNG').write_bytes(b'x' * 100)

stat = defaultdict(lambda: [0, 0])
for p in sorted(root.rglob('*')):
    if p.is_file():
        stat[p.suffix.lower()][0] += 1
        stat[p.suffix.lower()][1] += p.stat().st_size
print('by ext', sorted((k, v[0], v[1]) for k, v in stat.items()))

plan = [(p.name, p.stem + p.suffix.lower())
        for p in sorted(root.rglob('*'))
        if p.is_file() and p.suffix != p.suffix.lower()]
print('rename plan', plan)
print('applied', 0)

log_path = root / 'audit.log'
logging.basicConfig(filename=str(log_path), level=logging.INFO, filemode='w',
                    format='%(levelname)s|%(message)s', force=True)
for old, new in plan:
    logging.info('rename %s -> %s', old, new)
print('audit', log_path.read_text(encoding='utf-8').splitlines())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# naive join escapes True
# resolve inside base True
# dry-run would act on ['keep.txt']
# actually removed 0
# still exists True

import os, tempfile
from pathlib import Path

base = Path(tempfile.mkdtemp())
target = base / 'safe'
target.mkdir()
(base / 'safe' / 'keep.txt').write_text('keep')
bad = os.path.join(str(base), '..', 'safe', 'keep.txt')
print('naive join escapes', Path(bad).resolve() != (target / 'keep.txt').resolve())
resolved = (target / 'keep.txt').resolve()
print('resolve inside base', resolved.is_relative_to(base.resolve()))
plan = [p.name for p in sorted(target.iterdir()) if p.is_file()]
print('dry-run would act on', plan)
print('actually removed', 0)
print('still exists', (target / 'keep.txt').exists())

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# walk files 2
# rglob files 2
# same set True
# suffix .txt

import os, tempfile
from pathlib import Path

root = Path(tempfile.mkdtemp())
(root / 'a').mkdir()
(root / 'a' / 'b').mkdir()
(root / 'a' / 'b' / 'c.txt').write_text('x')
(root / 'top.txt').write_text('y')
walk_files = []
for dirpath, dirnames, filenames in os.walk(root):
    for f in filenames:
        walk_files.append(os.path.join(dirpath, f))
glob_files = [str(p) for p in root.rglob('*') if p.is_file()]
print('walk files', len(walk_files))
print('rglob files', len(glob_files))
print('same set', set(walk_files) == set(glob_files))
print('suffix', Path('a/b/c.txt').suffix)

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import logging, tempfile
from datetime import datetime
from pathlib import Path

def build_plan(root):
    root = Path(root).resolve()
    out = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or not p.suffix or p.suffix == p.suffix.lower():
            continue
        dst = p.with_name(p.stem + p.suffix.lower())
        if dst.resolve().parent != root:
            raise ValueError('target escapes root')
        out.append((p, dst))
    return out

def apply_plan(plan, dry_run):
    for src, dst in plan:
        stamp = datetime.now().isoformat(timespec='seconds')
        if dry_run:
            logging.info('%s DRY-RUN %s -> %s', stamp, src.name, dst.name)
        else:
            src.rename(dst)
            logging.info('%s RENAMED %s -> %s', stamp, src.name, dst.name)
    return 0 if dry_run else len(plan)

root = Path(tempfile.mkdtemp())
for n in ('A.TXT', 'B.PNG', 'c.txt'):
    (root / n).write_text('x')
log_path = root / 'plan.log'
logging.basicConfig(filename=str(log_path), level=logging.INFO,
                    filemode='w', format='%(message)s', force=True)
plan = build_plan(root)
print('planned', len(plan))
print('applied', apply_plan(plan, dry_run=True))
print('unchanged', sorted(p.name for p in root.iterdir()))
