"""
第 122 讲 · 实战 01 · 待办清单 CLI 与命令分发
与教程正文一一对应的示例代码

课程页面：/projects/cli-todo
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/122-cli-todo.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/122-cli-todo.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# added 1
# added 2
# add 0 0
# done 0 missing 1
# rows [{'id': 1, 'title': '写精讲', 'done': True}, {'id': 2, 'title': '跑自检', 'done': False}]

import argparse, json, os, tempfile

def load(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save(path, rows):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path) or '.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

def add(path, title):
    rows = load(path)
    rows.append({'id': len(rows) + 1, 'title': title, 'done': False})
    save(path, rows)
    return rows[-1]['id']

def done(path, tid):
    rows = load(path)
    hit = [r for r in rows if r['id'] == tid]
    if not hit:
        return 1
    hit[0]['done'] = True
    save(path, rows)
    return 0

def main(argv=None):
    p = argparse.ArgumentParser(prog='todo')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('add').add_argument('title')
    sub.add_parser('done').add_argument('tid', type=int)
    ns = p.parse_args(argv)
    path = os.environ.get('TASK_PATH', 'todos.json')
    if ns.cmd == 'add':
        print('added', add(path, ns.title))
        return 0
    return done(path, ns.tid)

with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, 'todos.json')
    os.environ['TASK_PATH'] = path
    print('add', main(['add', '写精讲']), main(['add', '跑自检']))
    print('done', main(['done', '1']), 'missing', main(['done', '99']))
    print('rows', json.load(open(path, encoding='utf-8')))
os.environ.pop('TASK_PATH', None)

# ======================== 2. 对照写法 ========================
# 预期输出：
# direct-write corrupt JSONDecodeError
# atomic restore [{'id': 1, 'done': False}]

import json, os, tempfile

target = os.path.join(tempfile.mkdtemp(), 'todos.json')
old = json.dumps([{'id': 1, 'done': False}])
with open(target, 'w', encoding='utf-8') as f:
    f.write(old)
with open(target, 'w', encoding='utf-8') as f:
    f.write(old[:8])
try:
    json.loads(open(target, encoding='utf-8').read())
except json.JSONDecodeError as e:
    print('direct-write corrupt', type(e).__name__)
tmp = target + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    f.write(old)
os.replace(tmp, target)
print('atomic restore', json.loads(open(target, encoding='utf-8').read()))

# ======================== 3. 原理验证 ========================
# 预期输出：
# content new
# inode changed True
# tmp gone True
# same dir True

import os, tempfile

d = tempfile.mkdtemp()
a = os.path.join(d, 'a.json')
b = os.path.join(d, 'b.tmp')
open(a, 'w').write('old')
open(b, 'w').write('new')
ino_before = os.stat(a).st_ino
os.replace(b, a)
print('content', open(a).read())
print('inode changed', os.stat(a).st_ino != ino_before)
print('tmp gone', not os.path.exists(b))
print('same dir', os.path.dirname(a) == os.path.dirname(b))

# ======================== 4. 工程案例 ========================

import argparse, json, os, tempfile

class JsonTodoRepo:
    def __init__(self, path):
        self.path = path
    def load(self):
        if not os.path.exists(self.path):
            return []
        return json.load(open(self.path, encoding='utf-8'))
    def save(self, rows):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or '.')
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(rows, f)
        os.replace(tmp, self.path)
    def add(self, title):
        rows = self.load()
        rows.append({'title': title, 'done': False})
        self.save(rows)
        return len(rows)

def build_parser():
    p = argparse.ArgumentParser(prog='todo')
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('add').add_argument('title')
    return p

def dispatch(argv, repo):
    ns = build_parser().parse_args(argv)
    if ns.cmd == 'add':
        return 0, 'added ' + str(repo.add(ns.title))
    return 2, 'unknown command'

def e2e_test():
    with tempfile.TemporaryDirectory() as d:
        repo = JsonTodoRepo(os.path.join(d, 't.json'))
        rc, msg = dispatch(['add', 'task-a'], repo)
        assert rc == 0
        assert repo.load() == [{'title': 'task-a', 'done': False}]
        return msg

print(e2e_test())
