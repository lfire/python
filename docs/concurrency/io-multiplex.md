---
title: 第 066 讲 · IO 多路复用：select / poll / epoll
description: 理解事件循环在系统调用层的样子
---

<StageHeader stage='L6 · 并发与异步' level='★★★★☆' time='40 分钟' goal='理解事件循环在系统调用层的样子' prereq='第 065 讲 · 进程间通信：Queue、Pipe 与信号' />

# 第 066 讲 · IO 多路复用：select / poll / epoll

进程把多核用上了，可面对成百上千个连接，为每个配一条执行流还是太重，等待的时间大多闲着。往下沉一层：IO 多路复用回答的正是「一个执行流盯住一批连接、谁就绪处理谁」在系统调用层长什么样。一个 echo 服务，连接一多要么线程堆满，要么慢连接堵路。

先对照阻塞与非阻塞 IO，再比 `select`、`poll`、`epoll`，再讲水平与边缘触发，用 `selectors` 标准库写个最小 echo server，最后收束到反应器模式与回调地狱的由来。前置是文件描述符、socket、阻塞概念与第 60 讲全景；读完能看清事件循环底下那层，明白框架替你扛了哪些复杂度。


## 非阻塞 socket 上 recv 一次，连接卡死

用 `selectors` 写 echo server 时，有人把 socket 设成非阻塞却仍用 recv 一次就返回，边缘触发下内核只通知一次，剩余数据再没事件，连接永久卡住；

另一个版本用 `select.select` 传了上千个 fd，每次调用都把 fd_set 在用户态与内核态之间来回拷贝并线性扫描，CPU 全耗在扫描上——这正是 `C10K` 要解决的问题。还有人分不清水平触发与边缘触发，把 epoll 的 `EPOLLET` 当成默认行为；

或在 macOS 上照抄 Linux 教程直接调用 `select.epoll()`，启动时就抛 `AttributeError`。更根本的困惑是：asyncio 明明叫异步，为什么底层还是 select？答案是事件循环本质就是「把一批 fd 交给内核，谁就绪就处理谁」，asyncio 只是在这之上叠了协程与任务调度。

用标准库 `selectors` 写一个最小反应器，能看清框架替你承担了哪些系统调用细节。

<Callout type="warn" title='先看一个真实会出错的写法' text='边缘触发下 recv 只读一次，连接卡死：ET 只在状态跃迁时通知一次，缓冲区残留数据不会再触发事件' />


## 阻塞、非阻塞 fd 与三种就绪通知

socket 默认阻塞，recv 无数据时会挂起线程；

`setblocking(False)`（等价于 `settimeout(0.0)`）之后，无数据立刻抛 `BlockingIOError`，errno 为 `EAGAIN` / `EWOULDBLOCK`（两者常是同一个值）。

`select.select` 用 fd_set 位图，跨平台最好却有三个硬伤：`FD_SETSIZE` 上限（常见 1024）、每次调用把整个集合在用户态与内核态之间拷贝、返回后还要线性扫描全部 fd 才知道谁就绪，复杂度是 `O(n)`。

`poll()` 改用数组登记 (fd, events)，没有 `FD_SETSIZE` 限制，事件位含 `POLLIN` / `POLLOUT` / `POLLERR` / `POLLHUP`，但每次仍要把整个数组传进内核并线性扫描就绪项，复杂度还是 `O(n)`。

epoll 是 Linux 2.6+ 的接口：`epoll_create1` 建实例，`epoll_ctl` 用 ADD/MOD/DEL 把兴趣集合维护在内核红黑树里，`epoll_wait` 只返回就绪链表，复杂度与就绪数相关而非总 fd 数，适合海量连接；

macOS/BSD 对应 kqueue，Windows 是 `IOCP`（前摄器而非反应器），select 模块在这台 macOS 上有 kqueue 与 poll，没有 epoll。

**select / poll / epoll / kqueue 对照**

| 接口 | 就绪探测复杂度 | fd 上限 | 平台 |
| --- | --- | --- | --- |
| select.select | O(n) 线性扫描 + 每次拷贝 fd_set | FD_SETSIZE 常见 1024 | 全平台（Windows 仅 socket） |
| poll / PollSelector | O(n) 扫描数组，无位图上限 | 受系统 fd 限制 | POSIX |
| epoll / EpollSelector | O(就绪数)，内核维护红黑树 + 就绪链表 | 受系统 fd 限制 | Linux 2.6+ |
| kqueue / KqueueSelector | O(就绪数)，内核事件队列 | 受系统 fd 限制 | macOS / BSD |
| IOCP | 完成端口，内核完成操作后通知 | 受系统限制 | Windows，前摄器非反应器 |

<ConceptDiagram type='flow4' title='第 066 讲 · 阻塞 / 非阻塞 fd 与 select / poll / epoll' labels='阻塞 / 非阻塞 fd 与 select /|水平触发、边缘触发与 reactors 模式|selectors 标准库与可移植写法' caption='理解事件循环在系统调用层的样子' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。

<Callout type="tip" title='核心心智模型' text='socket 默认阻塞，recv 无数据时会挂起线程；`setblocking(False)`（等价于 `settimeout(0.0)`）之后，无数据立刻抛 `BlockingIOError`，errno 为 `EAGAIN` / `EWOULDBLOCK`（两者常是同一个值）。`select.s' />


## 用 select 写一次事件循环

```python
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
```

<OutputBox title='主示例运行结果' output='selector KqueueSelector\nregistered 1\nevent peerA True\npayload b&#39;hello&#39;' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import socket\nimport selectors\n\nsel = selectors.DefaultSelector()\na, b = socket.socketpair()\na.setblocking(False)\nb.setblocking(False)\nsel.register(a, selectors.EVENT_READ, data=&#39;peerA&#39;)\nprint(&#39;selector&#39;, type(sel).__name__)\nprint(&#39;registered&#39;, len(sel.get_map()))\nb.send(b&#39;hello&#39;)\nevents = sel.select(timeout=1)\nfor key, mask in events:\n    print(&#39;event&#39;, key.data, mask == selectors.EVENT_READ)\n    print(&#39;payload&#39;, key.fileobj.recv(64))\na.close()\nb.close()\nsel.close()' :notes='["导入 socket 建本机 socketpair 做自测", "导入 selectors 使用跨平台抽象", "macOS 上选 KqueueSelector", "一对已连接的 socket", "读端非阻塞，无数据 recv 会抛 BlockingIOError", "写端同样非阻塞", "注册读事件，data 携带上下文标签", "打印实际选择器类型，证明平台差异", "get_map 里恰好一个已注册 fd", "从 b 写入，使 a 变为可读", "select 带超时，避免无事件时永久挂住", "遍历就绪事件列表", "key.data 是注册时的标签，mask 为 EVENT_READ", "读一次数据；LT 下若有剩余还会再次就绪", "关闭读端 socket", "关闭写端 socket", "关闭选择器释放内核资源"]' title='第 066 讲 · IO 多路复用：select / poll / epoll' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。


## 对照：边缘触发只读一次与读到 EAGAIN

```python
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
```

<OutputBox title='对照写法：先自己猜，再点开' output='nonblocking raises BlockingIOError\nselect readable True\npoll available True\nepoll available False\nEVENT_READ/WRITE 1 2\nplatform darwin' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import socket\nimport selectors\n\nsel = selectors.DefaultSelector()\na, b = socket.socketpair()\na.setblocking(False)\nb.setblocking(False)\nsel.register(a, selectors.EVENT_READ, data=&#39;peerA&#39;)\nprint(&#39;selector&#39;, type(sel).__name__)\nprint(&#39;registered&#39;, len(sel.get_map()))\nb.send(b&#39;hello&#39;)\nevents = sel.select(timeout=1)\nfor key, mask in events:\n    print(&#39;event&#39;, key.data, mask == selectors.EVENT_READ)\n    print(&#39;payload&#39;, key.fileobj.recv(64))\na.close()\nb.close()\nsel.close()", "note": "阻塞 / 非阻塞 fd 与 select / poll / epoll"}, {"label": "对照 / 进阶", "code": "import socket\nimport select\nimport selectors\nimport sys\n\na, b = socket.socketpair()\nb.setblocking(False)\ntry:\n    b.recv(64)\nexcept BlockingIOError as e:\n    print(&#39;nonblocking raises&#39;, type(e).__name__)\na.send(b&#39;x&#39;)\nr, w, x = select.select([b], [], [b], 1)\nprint(&#39;select readable&#39;, len(r) == 1)\nprint(&#39;poll available&#39;, hasattr(select, &#39;poll&#39;))\nprint(&#39;epoll available&#39;, hasattr(select, &#39;epoll&#39;))\nprint(&#39;EVENT_READ/WRITE&#39;, selectors.EVENT_READ, selectors.EVENT_WRITE)\nprint(&#39;platform&#39;, sys.platform)\na.close()\nb.close()", "note": "水平触发、边缘触发与 reactors 模式"}]' title='两种写法对照' note='差异集中在 阻塞与非阻塞 IO；先看输出，再找背后的规则。' />

```python
import inspect
import selectors
import select

print('DefaultSelector', selectors.DefaultSelector.__name__)
print('EVENT_READ', selectors.EVENT_READ, 'EVENT_WRITE', selectors.EVENT_WRITE)
print('select sig', str(inspect.signature(select.select)))
print('epoll on this host', hasattr(select, 'epoll'))
print('kqueue on this host', hasattr(select, 'kqueue'))
```

<OutputBox title='原理验证' output='DefaultSelector KqueueSelector\nEVENT_READ 1 EVENT_WRITE 2\nselect sig (rlist, wlist, xlist, timeout=None, /)\nepoll on this host False\nkqueue on this host True' />


## 水平触发、边缘触发与反应器模式

水平触发（LT，epoll 默认，select/poll 也是）只要 fd 仍处于就绪状态（接收缓冲区还有数据），每次 wait 都会再次报告；

边缘触发（ET，需显式 `EPOLLET`）只在状态发生跃迁时报告一次，因此必须在一个循环里把缓冲区读到 `BlockingIOError` / `EAGAIN` 为止，漏读就会永久失去该 fd 的后续事件。

`EPOLLONESHOT` 则要在处理完之后用 `epoll_ctl(MOD)` 重新武装。反应器模式的骨架是：把 fd 设为非阻塞、注册到 demultiplexer、事件循环调 select 拿就绪列表、按事件分派到对应的 handler；handler 内不能阻塞，否则整个 loop 停摆。

回调层层嵌套就是「回调地狱」的由来，协程把它改写成看起来同步的 await，但底层的 register / select / dispatch 一步没少。

asyncio 的 `BaseSelectorEventLoop` 正是用 `selectors.DefaultSelector`，`loop.add_reader` / `loop.add_writer` 最终落到 register 与 modify。

**水平触发与边缘触发**

| 模式 | 通知时机 | 读取要求 | 漏读后果 |
| --- | --- | --- | --- |
| 水平触发 LT（epoll 默认、select/poll） | 只要缓冲区仍有数据就重复报告 | 可读一次，剩余数据下次还会通知 | 相对宽容，但每次仍要拷贝到内核 |
| 边缘触发 ET（EPOLLET） | 仅状态跃迁时报告一次 | 必须循环读到 BlockingIOError/EAGAIN | 连接永久卡住，事件不再来 |
| EPOLLONESHOT | 只报告一次后自动失活 | 处理后 epoll_ctl(MOD) 重新武装 | 忘记重新武装则该 fd 再无事件 |

<FlowTimeline :steps='[{"title": "阻塞 / 非阻塞 fd 与 select / poll / epoll", "desc": "socket 默认阻塞，recv 无数据时会挂起线程；`setblocking(Fa…", "tone": "blue"}, {"title": "水平触发、边缘触发与 reactors 模式", "desc": "水平触发（LT，epoll 默认，select/poll 也是）只要 fd 仍处于就…", "tone": "purple"}, {"title": "selectors 标准库与可移植写法", "desc": "`selectors`（3.4+）提供一层统一抽象：`DefaultSelector…", "tone": "orange"}, {"title": "工程落地", "desc": "用 selectors 写一个最小 echo server（反应器骨", "tone": "red"}]' direction="horizontal" title='本讲的知识推进' />


## 内核如何替进程监视一批 fd

IO 多路复用的核心，是让内核替进程监视一批 fd，进程只在「有就绪」时被唤醒。select 把三个 fd_set 位图从用户态拷进内核，内核线性设置就绪位再整体拷回，调用方还得再扫一遍全表，故成本随总连接数按 `O(n)` 增长，还受 `FD_SETSIZE` 约束。

poll 用 (fd, events) 数组去掉了位图上限，但仍每轮传全量、扫全量。epoll 把注册与等待拆开：`epoll_ctl` 把 fd 挂进内核红黑树，网卡收包触发回调把就绪 fd 挂到就绪链表，`epoll_wait` 只取链表，因此与总 fd 数无关；

kqueue 用内核事件队列与 changelist 达到类似效果。LT 与 ET 的区别在「就绪状态持续」还是「状态变化」：ET 少一次唤醒，但要求一次读空。

`selectors.DefaultSelector` 在模块导入时按 `sys.platform` 选好具体类，register 把 (fd, events, data) 存进字典并对 epoll/kqueue 调 ctl，select 再把内核返回的事件翻译回 `SelectorKey`。

asyncio 的 `BaseSelectorEventLoop` 用的正是这套 register/select 循环，add_reader/add_writer 只是往 data 里挂回调。

<Term word='阻塞与非阻塞 IO' text='socket 默认阻塞，recv 无数据时会挂起线程；`setblocking(False)`（等价于 `settimeout(0.0)`）之后，无数据立刻抛 `BlockingIOError`，errno 为 `EAGAIN` / `EWOULDBLOCK`（两者常是同一个值）。`select.select` 用 f' />

<Term word='select / poll / epoll 对比' text='水平触发（LT，epoll 默认，select/poll 也是）只要 fd 仍处于就绪状态（接收缓冲区还有数据），每次 wait 都会再次报告；边缘触发（ET，需显式 `EPOLLET`）只在状态发生跃迁时报告一次，因此必须在一个循环里把缓冲区读到 `BlockingIOError` / `EAGAIN` 为止，漏读就' />


## selectors 标准库、可移植写法与 echo server 骨架

`selectors`（3.4+）提供一层统一抽象：`DefaultSelector` 在支持的平台上挑最优实现——Linux 是 `EpollSelector`、macOS/BSD 是 `KqueueSelector`，否则依次退到 `DevpollSelector` / `PollSelector` / `SelectSelector`。

`register` 返回 `SelectorKey`，events 取 `EVENT_READ`（值 1）或 `EVENT_WRITE`（值 2）；unregister、modify、`get_map`、close 管理注册表；

`select(timeout=None)` 返回 [(key, events), ...]，`key.data` 可以携带 handler 或连接上下文。

Key 里的 fileobj 可以是 fd 整数，也可以是带 `fileno()` 方法的对象。

写可移植代码应一律用 `DefaultSelector`，而不是直接去碰平台专属的 epoll 接口；

用 `socket.socketpair()` 做自测，能在本机无网络权限时验证注册、就绪与读写。

生产环境不要手写这套循环去替代成熟框架：还要处理 `EINTR`、半关闭、写缓冲背压、定时器和跨线程唤醒，这些 asyncio 与网络框架已经替你解决。

**selectors API 与默认实现**

| API / 常量 | 含义 | 取值 / 默认 |
| --- | --- | --- |
| DefaultSelector | 按平台选最优实现 | Linux=EpollSelector，macOS=KqueueSelector |
| register(fileobj, events, data=None) | 登记 fd 返回 SelectorKey | events 用 EVENT_READ / EVENT_WRITE |
| select(timeout=None) | 返回就绪 [(key, events)] 列表 | timeout=None 表示无限等待 |
| EVENT_READ / EVENT_WRITE | 事件位 | 1 / 2 |
| get_map() / modify() / unregister() | 查看 / 改事件 / 注销 | key.data 可带 handler |

要理解 asyncio 替我们做了什么，最直接的办法是手写一个反应器：监听 socket 设为非阻塞并注册 `EVENT_READ`，accept 到的连接也设非阻塞、注册读回调；

事件循环反复调用 `sel.select(timeout)`，把就绪 key 的 data 当 handler 调用；

读到数据就回写、读到空就注销关闭。下面片段用有界的 ticks 让它在无人连接时也能自行结束，便于直接运行观察；生产版会去掉 ticks，补上 `EINTR` 处理、写缓冲背压与定时器。重点是三件事：注册 / 就绪 / 分派这三段结构、非阻塞 fd 的必要性、以及一个 handler 阻塞就拖垮全 loop 的事实。

```python
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
```

<Callout type="idea" title='落地提示' text='用 selectors 写一个最小 echo server，能帮你看清框架替你承担了哪些复杂度；生产环境直接用成熟框架' />

<CheckList id='P066b' title='上线前自检' :items='["能复现并解释「边缘触发下 recv 只读一次，连接卡死」", "能复现并解释「在 macOS 直接 import select.epoll」", "能复现并解释「事件循环 handler 里做同步阻塞调用」", "能用一条命令验证 阻塞与非阻塞 IO", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 边缘触发下 recv 只读一次，连接卡死 | ET 只在状态跃迁时通知一次，缓冲区残留数据不会再触发事件 | 循环 recv 直到 BlockingIOError/EAGAIN，或改用默认 LT 并接受每轮拷贝 |
| 在 macOS 直接 import select.epoll | epoll 是 Linux 专属，macOS 提供 kqueue 与 poll | 用 selectors.DefaultSelector 写可移植代码，它会自动选 KqueueSelector |
| 事件循环 handler 里做同步阻塞调用 | select 之后的 dispatch 仍在单线程，一个阻塞 recv/requests 会停住整个 loop | handler 内全部非阻塞读写，阻塞工作丢进线程池或换 asyncio 原生异步库 |

<Callout type="warn" title='本讲最容易踩的坑' text='边缘触发下 recv 只读一次，连接卡死：ET 只在状态跃迁时通知一次，缓冲区残留数据不会再触发事件' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：边缘触发下 recv 只读一次，连接卡死", "body": "ET 只在状态跃迁时通知一次，缓冲区残留数据不会再触发事件", "tip": "循环 recv 直到 BlockingIOError/EAGAIN，或改用默认 LT 并接受每轮拷贝"}, {"title": "第 2 步：在 macOS 直接 import sele", "body": "epoll 是 Linux 专属，macOS 提供 kqueue 与 poll", "tip": "用 selectors.DefaultSelector 写可移植代码，它会自动选 KqueueSelector"}, {"title": "第 3 步：事件循环 handler 里做同步阻塞调用", "body": "select 之后的 dispatch 仍在单线程，一个阻塞 recv/requests 会停住整个 loop", "tip": "handler 内全部非阻塞读写，阻塞工作丢进线程池或换 asyncio 原生异步库"}]' />


## 练习、自测与速记

<Exercise title='基础：验证非阻塞 recv 抛 BlockingIOError' task='用 socketpair 把一端设为非阻塞，无数据时 recv 应抛 BlockingIOError 且 errno 属 EAGAIN/EWOULDBLOCK；另一端 send 后应读到数据。' solution='import socket, errno\na, b = socket.socketpair()\nb.setblocking(False)\ntry:\n    b.recv(64)\nexcept BlockingIOError as e:\n    print(&#39;eagain&#39;, e.errno in (errno.EAGAIN, errno.EWOULDBLOCK))\na.send(b&#39;x&#39;)\nprint(&#39;data&#39;, b.recv(64))\na.close(); b.close()' explain='非阻塞 fd 无数据时不挂起而抛 BlockingIOError，errno 为 EAGAIN（与 EWOULDBLOCK 常同值）；事件循环正是靠这个信号把 fd 交给 selector 等待就绪。' />

<Exercise title='进阶：用 selectors 同时监控两个 socketpair' task='建两对 socketpair，都注册 EVENT_READ 且 data 标记来源；只往其中一对写数据，select 后打印就绪的 data，证明只返回就绪 fd。' solution='import socket, selectors\nsel = selectors.DefaultSelector()\npairs = [socket.socketpair() for _ in range(2)]\nfor i, (a, b) in enumerate(pairs):\n    a.setblocking(False)\n    sel.register(a, selectors.EVENT_READ, data=&#39;ch&#39; + str(i))\npairs[1][1].send(b&#39;z&#39;)\nprint([k.data for k, _ in sel.select(timeout=1)])\nfor a, b in pairs: a.close(); b.close()\nsel.close()' explain='select 只返回就绪 fd 对应的 SelectorKey；key.data 把上下文带回分派处。这正是 epoll/kqueue 相对 select 线性扫描的优势：成本与就绪数相关。' />

<Quiz no='066-1' q='关于 epoll 与 select 的复杂度，正确的是？' :options='["epoll 用内核红黑树维护注册、只返回就绪链表；select 每轮拷贝并线性扫描全部 fd", "两者都是 O(1)", "select 比 epoll 更适合 C10K", "epoll 在所有平台可用"]' answer="0" explain='select 每轮把 fd_set 在用户/内核间拷贝并线性扫描，且有 FD_SETSIZE 上限；epoll 把注册留在内核、wait 只取就绪链表，Linux 专属，macOS 对应 kqueue。' />

<Quiz no='066-2' q='边缘触发（EPOLLET）下必须怎么做？' :options='["循环读到 BlockingIOError/EAGAIN 为止", "只读一次即可，剩余数据下次会再通知", "每次 wait 后重新 register", "把 socket 改回阻塞"]' answer="0" explain='ET 只在状态跃迁时通知一次，缓冲区残留数据不会再产生事件；漏读会让连接永久卡住。LT 才会对持续就绪状态反复报告。' />

<Quiz no='066-3' q='关于 selectors.DefaultSelector，正确的是？' :options='["在 macOS 选 KqueueSelector、Linux 选 EpollSelector，是可移植写法", "它永远是 SelectSelector", "它会自动把 handler 改成多线程", "只有 Linux 才有这个模块"]' answer="0" explain='DefaultSelector 在模块导入时按平台挑最优实现；register/select/modify 是统一 API。直接 import select.epoll 在 macOS 会 AttributeError。' />

<Predict no='066-4' q='socket 设为 setblocking(False) 且无数据时调用 recv(64)，结果是？' :options='["抛 BlockingIOError，errno 为 EAGAIN/EWOULDBLOCK", "返回 b&#39;&#39;", "阻塞直到有数据", "返回 None"]' answer='0' output='BlockingIOError(EAGAIN)' explain='非阻塞 fd 在数据未就绪时不挂起线程，而是立刻抛 BlockingIOError；事件循环把这个信号交给 selector，等 fd 就绪再回调读逻辑。' />

<FillBlank no='066-5' tpl='___ socket' :answers='["import"]' hint='回想本讲关于 阻塞与非阻塞 IO 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 阻塞 / 非阻塞 fd 与 select / poll / epoll 的落点。' />

<KnowledgeCard :points='["非阻塞 fd 无数据抛 BlockingIOError(EAGAIN)；setblocking(False) 等价 settimeout(0.0)", "select 是 O(n) 且受 FD_SETSIZE 约束；poll 去掉位图上限仍 O(n)；epoll/kqueue 只返回就绪集合", "LT（默认）对持续就绪反复通知；ET(EPOLLET) 只在跃迁时通知一次，必须读空到 EAGAIN", "selectors.DefaultSelector 按平台选实现；EVENT_READ=1 / EVENT_WRITE=2，key.data 带上下文", "反应器 = 注册 → select 就绪 → 分派 handler；任一 handler 阻塞都会拖垮整个 loop", "asyncio 的 BaseSelectorEventLoop 底层就是 selectors，add_reader/add_writer 落到 register/modify"]' :pitfalls='["边缘触发下 recv 只读一次，连接卡死", "在 macOS 直接 import select.epoll", "事件循环 handler 里做同步阻塞调用", "边缘触发模式下没一次性读完缓冲区，事件不会再来，连接会永久卡住"]' summary='事件循环本质就是「把一批 fd 交给内核，谁就绪就处理谁」，asyncio 只是在这之上加了协程与任务调度' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 非阻塞 fd 无数据抛 BlockingIOError(EAGAIN)；setblocking(False) 等价 settimeout(0.0) | 建立直觉 |
| select 是 O(n) 且受 FD_SETSIZE 约束；poll 去掉位图上限仍 O(n)；epoll/kqueue 只返回就绪集合 | 跑通示例 |
| LT（默认）对持续就绪反复通知；ET(EPOLLET) 只在跃迁时通知一次，必须读空到 EAGAIN | 深入边界 |
| selectors.DefaultSelector 按平台选实现；EVENT_READ=1 / EVENT_WRITE=2，key.data 带上下文 | 工程落地 |
| 反应器 = 注册 → select 就绪 → 分派 handler；任一 handler 阻塞都会拖垮整个 loop | 随堂检测 |
| asyncio 的 BaseSelectorEventLoop 底层就是 selectors，add_reader/add_writer 落到 register/modify | 复盘 |

1. 非阻塞 fd 无数据抛 BlockingIOError(EAGAIN)；setblocking(False) 等价 settimeout(0.0)

2. select 是 O(n) 且受 FD_SETSIZE 约束；poll 去掉位图上限仍 O(n)；epoll/kqueue 只返回就绪集合

3. LT（默认）对持续就绪反复通知；ET(EPOLLET) 只在跃迁时通知一次，必须读空到 EAGAIN

[下一讲：生成器协程：send、yield from 与调度器](/concurrency/generator-coroutine)

```bash
python -c "import asyncio; print(len(asyncio.run(asyncio.gather(*[asyncio.sleep(0,i) for i in range(3)]))))"
```

把输入换成你自己的数据，观察结果是否仍符合 阻塞与非阻塞 IO 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。
