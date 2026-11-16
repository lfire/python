"""
第 066 讲 · IO 多路复用：select / poll / epoll
与教程正文一一对应的示例代码

课程页面：/concurrency/io-multiplex
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/066-io-multiplex.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/066-io-multiplex.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# selector KqueueSelector
# registered 1
# event peerA True
# payload b'hello'

import socket
import selectors

sel = selectors.DefaultSelector()
a, b = socket.socketpair()
a.setblocking(False)
b.setblocking(False)
sel.register(a, selectors.EVENT_READ, data='peerA')
print('selector', type(sel).__name__)
print('registered', len(sel.get_map()))
b.send(b'hello')
events = sel.select(timeout=1)
for key, mask in events:
    print('event', key.data, mask == selectors.EVENT_READ)
    print('payload', key.fileobj.recv(64))
a.close()
b.close()
sel.close()

# ======================== 2. 对照写法 ========================
# 预期输出：
# nonblocking raises BlockingIOError
# select readable True
# poll available True
# epoll available False
# EVENT_READ/WRITE 1 2
# platform darwin

import socket
import select
import selectors
import sys

a, b = socket.socketpair()
b.setblocking(False)
try:
    b.recv(64)
except BlockingIOError as e:
    print('nonblocking raises', type(e).__name__)
a.send(b'x')
r, w, x = select.select([b], [], [b], 1)
print('select readable', len(r) == 1)
print('poll available', hasattr(select, 'poll'))
print('epoll available', hasattr(select, 'epoll'))
print('EVENT_READ/WRITE', selectors.EVENT_READ, selectors.EVENT_WRITE)
print('platform', sys.platform)
a.close()
b.close()

# ======================== 3. 原理验证 ========================
# 预期输出：
# DefaultSelector KqueueSelector
# EVENT_READ 1 EVENT_WRITE 2
# select sig (rlist, wlist, xlist, timeout=None, /)
# epoll on this host False
# kqueue on this host True

import inspect
import selectors
import select

print('DefaultSelector', selectors.DefaultSelector.__name__)
print('EVENT_READ', selectors.EVENT_READ, 'EVENT_WRITE', selectors.EVENT_WRITE)
print('select sig', str(inspect.signature(select.select)))
print('epoll on this host', hasattr(select, 'epoll'))
print('kqueue on this host', hasattr(select, 'kqueue'))

# ======================== 4. 工程案例 ========================

import socket
import selectors

sel = selectors.DefaultSelector()

def on_read(conn, mask):
    data = conn.recv(4096)
    if data:
        conn.sendall(data)
    else:
        sel.unregister(conn)
        conn.close()

def on_accept(server, mask):
    conn, _ = server.accept()
    conn.setblocking(False)
    sel.register(conn, selectors.EVENT_READ, on_read)

def serve(host, port, ticks=20):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(128)
    server.setblocking(False)
    sel.register(server, selectors.EVENT_READ, on_accept)
    for _ in range(ticks):
        for key, mask in sel.select(timeout=0.05):
            key.data(key.fileobj, mask)
    sel.unregister(server)
    server.close()
    sel.close()

if __name__ == '__main__':
    serve('127.0.0.1', 0)
