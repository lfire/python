---
title: 第 064 讲 · multiprocessing：进程、Pool 与共享内存
description: 绕过 GIL 处理 CPU 密集任务
---

<StageHeader stage='L6 · 并发与异步' level='★★★★☆' time='40 分钟' goal='绕过 GIL 处理 CPU 密集任务' prereq='第 063 讲 · 线程池与 Future 模式' />

# 第 064 讲 · multiprocessing：进程、Pool 与共享内存

线程池把 IO 等待用得很顺，可一遇上吃 CPU 的活，GIL 还是把吞吐按在单个核上。换个思路：让多个进程各自持一份状态，绕开这把锁。一批图像逐张变换，线程开满 CPU 也上不去，内存倒先被复制的对象占满，该换条路了。

先看 `fork`、`spawn`、`forkserver` 三种启动方式，再讲清进程间不共享内存、数据都要 pickle 序列化，再用 `Pool` 配 `chunksize` 调平粒度、用 `shared_memory` 传大数组，末了算算进程启动开销。需有线程、GIL、pickle 基础；读完能把 CPU 密集任务分给进程，也知道何时收益会被传输吃掉。


## 从 threads 改成多进程，却没吃满 12 核

团队把一段纯 Python 的图像卷积从 threads 改成 multiprocessing，指望吃满 12 核，结果只快了一点点；profiling 发现每个任务都要把一份 200MB 的列表 pickle 给子进程，序列化时间盖过了并行收益。

换到 spawn 平台后又冒出更怪的错：把 `lambda` 或打开的数据库连接当参数传进去，子进程启动时报 Can't pickle local object；

还有人忘了 `if __name__ == '`__main__`':` 守卫，子进程递归地重新导入主模块，创建出一串进程。

另一次在多线程程序里用 fork，子进程继承了别的线程持有的锁，直接卡死。这四件事分别对应四个机制：进程地址空间隔离、序列化成本、启动方法差异、fork 与线程不安全。不先把这些摆清楚，「上多进程」只会把问题从一个层搬到另一个层。

<Callout type="warn" title='先看一个真实会出错的写法' text='spawn 平台把 lambda 或打开的连接传给子进程：spawn 要 pickle 参数，lambda/闭包/连接/锁没有可引用的顶层名' />


## fork、spawn 与 forkserver 的平台默认值

`multiprocessing.get_all_start_methods()` 在 macOS 3.13 返回 ['spawn', 'fork', 'forkserver']，`get_start_method()` 默认 'spawn'；

Windows 只有 spawn，而 `POSIX` 上的 Linux 传统默认 fork。macOS 自 3.8 起把默认改成 spawn，因为 Apple 平台上的 fork 在带线程或某些系统框架时并不稳定；Linux 则在 3.14 起把默认改为 forkserver，同样是为了躲开多线程进程里 fork 的隐患。

fork 用 `fork(2)` 复制地址空间，写时复制、启动最快，但只保留调用线程，其它线程持有的锁在子进程里永远解不开——3.12 起在多线程进程里 fork 会发 `DeprecationWarning`。

spawn 起一个全新解释器并重新导入 `__main__`，因此所有传给子进程的对象都必须可 pickle、入口必须有 `if __name__ == '__main__':` 守卫，启动最慢却最安全。

forkserver 是 Unix 专属：先起一个单线程服务进程，之后由它 fork 出子进程，既避开「在多线程进程里 fork」的风险，又不像 spawn 那样重新导入全部模块。

用 `get_context(method)` 显式选方法，便于跨平台复现。

**启动方法对照与平台默认**

| 方法 | 机制 | 平台默认 | 主要风险 |
| --- | --- | --- | --- |
| fork | fork(2) 复制地址空间，COW | Linux 传统默认（3.14 拟改 forkserver） | 只留调用线程，别线程的锁永不释放；3.12 起多线程 fork 发 DeprecationWarning |
| spawn | 全新解释器、重导入 __main__ | Windows 与 macOS 3.8+ 默认 | 对象必须可 pickle，入口要有 __main__ 守卫，启动最慢 |
| forkserver | 单线程服务进程按需 fork | Unix 专属，可显式 get_context 选择 | 需要额外服务进程，Windows 不可用 |

<Callout type="tip" title='核心心智模型' text='`multiprocessing.get_all_start_methods()` 在 macOS 3.13 返回 [&#39;spawn&#39;, &#39;fork&#39;, &#39;forkserver&#39;]，`get_start_method()` 默认 &#39;spawn&#39;；Windows 只有 spawn，而 `POSIX` 上…' />

<ConceptDiagram type='compare2' title='第 064 讲 · 三种启动方法与平台默认值' labels='三种启动方法与平台默认值|进程间不共享、pickle 成本与 Pool…|共享内存、进程开销与选型阈值|进程启动开销' caption='绕过 GIL 处理 CPU 密集任务' />

这张图把两种写法并排放在一起：结果往往相近，差别更常出现在失败路径与边界条件上。建议对照主示例里的实现逐格看一遍。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 进程间不共享：pickle 边界与 Pool 参数

进程地址空间隔离，父子各有独立的 Python 堆与 GIL，所以 CPU 密集任务能真正并行；代价是任何跨进程的参数与返回值都要 pickle 序列化、再经管道传输，成本与字节数成正比。

只有模块顶层、可 import 的函数能被 pickle：`lambda`、闭包、局部函数、打开的连接、线程锁都会报 `PicklingError` 或 `AttributeError`（Can't pickle local object）。

`Pool` 提供 map、imap、imap_unordered、apply_async、starmap 等接口，map 与 imap 的 `chunksize` 把多个任务打成一包传输以减少 IPC 次数，太细则往返多、太粗则负载不均。

`Process` 有 start、join、pid、exitcode、is_alive、terminate、kill（3.7+）等成员，join 之后 exitcode 为 0 表示正常退出。

大数据优先用 `multiprocessing.shared_memory.SharedMemory`（3.8+，其 .buf 是 memoryview，用完要 `close()` 与 `unlink()`，否则 resource_tracker 会告警）或内存映射，而不是反复 pickle。

**跨进程数据方案与成本**

| 方案 | 传递方式 | 适用规模 | 代价 |
| --- | --- | --- | --- |
| Pool 参数/返回值 | pickle 经管道 | 小对象、粒度大 | 字节数越大越慢，可能吃掉并行收益 |
| Value / Array (ctypes) | 共享内存 + 默认锁 | 标量、定长数组 | 类型固定，需自己同步 |
| SharedMemory (3.8+) | 命名共享段 + memoryview | 大数组、图像缓冲 | 要 close()/unlink()，否则资源泄漏告警 |
| Manager 代理 | 服务进程 + 每次访问 IPC | 任意可 pickle 对象 | 比共享 ctypes 慢一两个量级 |

```python
import multiprocessing as mp
import os
import sys
from multiprocessing import shared_memory as shm

def square(x):
    return x * x

if __name__ == '__main__':
    print('start method', mp.get_start_method(), 'on', sys.platform)
    print('all methods', mp.get_all_start_methods())
    print('cpu count', os.cpu_count() > 0)
    with mp.Pool(processes=2) as pool:
        print('pool map', pool.map(square, [1, 2, 3, 4]))
        print('imap chunksize', list(pool.imap(square, [1, 2, 3, 4], chunksize=2)))
    p = mp.Process(target=square, args=(5,))
    p.start()
    p.join()
    print('exitcode', p.exitcode)
    sh = shm.SharedMemory(create=True, size=16)
    sh.buf[0] = 7
    print('shm byte', sh.buf[0], 'size_ge_16', sh.size >= 16)
    sh.close()
    sh.unlink()
```

<OutputBox title='主示例运行结果' output='start method spawn on darwin\nall methods [&#39;spawn&#39;, &#39;fork&#39;, &#39;forkserver&#39;]\ncpu count True\npool map [1, 4, 9, 16]\nimap chunksize [1, 4, 9, 16]\nexitcode 0\nshm byte 7 size_ge_16 True' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import multiprocessing as mp\nimport os\nimport sys\nfrom multiprocessing import shared_memory as shm\n\ndef square(x):\n    return x * x\n\nif __name__ == &#39;__main__&#39;:\n    print(&#39;start method&#39;, mp.get_start_method(), &#39;on&#39;, sys.platform)\n    print(&#39;all methods&#39;, mp.get_all_start_methods())\n    print(&#39;cpu count&#39;, os.cpu_count() &gt; 0)\n    with mp.Pool(processes=2) as pool:\n        print(&#39;pool map&#39;, pool.map(square, [1, 2, 3, 4]))\n        print(&#39;imap chunksize&#39;, list(pool.imap(square, [1, 2, 3, 4], chunksize=2)))\n    p = mp.Process(target=square, args=(5,))\n    p.start()\n    p.join()\n    print(&#39;exitcode&#39;, p.exitcode)\n    sh = shm.SharedMemory(create=True, size=16)\n    sh.buf[0] = 7\n    print(&#39;shm byte&#39;, sh.buf[0], &#39;size_ge_16&#39;, sh.size &gt;= 16)\n    sh.close()\n    sh.unlink()' :notes='["导入 multiprocessing 使用 Pool 与 Process", "读取 CPU 核数，判断并行上限", "读取平台，start method 默认值随平台变化", "导入 shared_memory 演示零拷贝共享块", "空行，只用于分隔逻辑块，不影响执行结果。", "顶层函数才能被 pickle 传给子进程", "返回平方，Process 不捕获返回值但 Pool 会", "空行，只用于分隔逻辑块，不影响执行结果。", "spawn 平台必须写守卫，否则子进程递归导入", "打印默认启动方法，macOS 3.13 为 spawn", "打印该平台可用的全部启动方法", "多核是并行收益的前提", "Pool(2) 起两个 worker 进程，各自有独立 GIL", "map 按输入顺序返回结果列表", "imap 的 chunksize=2 把任务打包减少 IPC", "Process 显式创建子进程", "start 触发 spawn 重新导入主模块", "join 回收子进程，避免僵尸", "exitcode 为 0 表示正常退出", "create=True 新建一段 16 字节共享内存", "buf 是 memoryview，可直接读写字节", "打印写入值；macOS 上 size 会向上取整到页大小，故只断言 ≥16", "close 释放本进程的映射", "unlink 删除名字，漏掉会触发 resource_tracker 告警"]' title='第 064 讲 · multiprocessing：进程、Pool 与共享内存' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import multiprocessing as mp
import pickle

def top_fn(x):
    return x + 1

if __name__ == '__main__':
    print('top-level picklable', pickle.dumps(top_fn)[0] == 128)
    try:
        pickle.dumps(lambda x: x)
    except pickle.PicklingError as e:
        print('lambda', type(e).__name__)
    ctx = mp.get_context('fork')
    print('fork context', ctx.get_start_method())
```

<OutputBox title='对照写法：先自己猜，再点开' output='top-level picklable True\nlambda PicklingError\nfork context fork' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import multiprocessing as mp\nimport os\nimport sys\nfrom multiprocessing import shared_memory as shm\n\ndef square(x):\n    return x * x\n\nif __name__ == &#39;__main__&#39;:\n    print(&#39;start method&#39;, mp.get_start_method(), &#39;on&#39;, sys.platform)\n    print(&#39;all methods&#39;, mp.get_all_start_methods())\n    print(&#39;cpu count&#39;, os.cpu_count() &gt; 0)\n    with mp.Pool(processes=2) as pool:\n        print(&#39;pool map&#39;, pool.map(square, [1, 2, 3, 4]))\n        print(&#39;imap chunksize&#39;, list(pool.imap(square, [1, 2, 3, 4], chunksize=2)))\n    p = mp.Process(target=square, args=(5,))\n    p.start()\n    p.join()\n    print(&#39;exitcode&#39;, p.exitcode)\n    sh = shm.SharedMemory(create=True, size=16)\n    sh.buf[0] = 7\n    print(&#39;shm byte&#39;, sh.buf[0], &#39;size_ge_16&#39;, sh.size &gt;= 16)\n    sh.close()\n    sh.unlink()", "note": "三种启动方法与平台默认值"}, {"label": "对照 / 进阶", "code": "import multiprocessing as mp\nimport pickle\n\ndef top_fn(x):\n    return x + 1\n\nif __name__ == &#39;__main__&#39;:\n    print(&#39;top-level picklable&#39;, pickle.dumps(top_fn)[0] == 128)\n    try:\n        pickle.dumps(lambda x: x)\n    except pickle.PicklingError as e:\n        print(&#39;lambda&#39;, type(e).__name__)\n    ctx = mp.get_context(&#39;fork&#39;)\n    print(&#39;fork context&#39;, ctx.get_start_method())", "note": "进程间不共享、pickle 成本与 Pool 参数"}]' title='两种写法对照' note='差异集中在 fork / spawn / forkserver；先看输出，再找背后的规则。' />

```python
import pickle
import sys
import multiprocessing as mp

payload = list(range(10000))
blob = pickle.dumps(payload, protocol=pickle.HIGHEST_PROTOCOL)
print('pickle bytes', len(blob))
print('protocol', pickle.HIGHEST_PROTOCOL)
print('payload bytes', sys.getsizeof(payload))
print('start method', mp.get_start_method())
```

<OutputBox title='原理验证' output='pickle bytes 29778\nprotocol 5\npayload bytes 80056\nstart method spawn' />


## fork 的写时复制快照与多线程弃用

把启动方式落到实现上看：fork 让子进程获得父进程地址空间的写时复制快照，启动极快，却只保留调用线程，其它线程持有的用户态锁在子进程里无人释放，这正是 3.12 起多线程 fork 被标记弃用的直接原因。

spawn 走 `_posixsubprocess` 起一个干净解释器，通过 preparation data 把 `sys.path`、`__main__` 的路径与 cwd 传过去，再导入主模块拿到可 pickle 的目标函数；

参数与结果用 `ForkingPickler` 序列化后经 Pipe 传输，所以只有顶层可引用的对象能过界。`Pool` 把可迭代对象切成 `chunksize` 大小的批次，每批一次 IPC，worker 完成后把结果放回结果队列；`chunksize` 越小往返越多、越大负载越不均。

`SharedMemory` 用 `shm_open` 创建命名段并 mmap 到各进程地址空间，buf 是内存视图，读写不再 pickle，但生命周期要显式 close 加 unlink，由 `resource_tracker` 兜底检测泄漏。

每个进程有独立 GIL 与独立堆，这才是 CPU 密集任务能随核数伸缩的根本，代价则是内存副本与序列化。

<Term word='fork / spawn / forkserver' text='`multiprocessing.get_all_start_methods()` 在 macOS 3.13 返回 [&#39;spawn&#39;, &#39;fork&#39;, &#39;forkserver&#39;]，`get_start_method()` 默认 &#39;spawn&#39;；Windows 只有 spawn，而 `POSIX` 上的 Linux 传统…' />

<Term word='进程间不共享内存' text='进程地址空间隔离，父子各有独立的 Python 堆与 GIL，所以 CPU 密集任务能真正并行；代价是任何跨进程的参数与返回值都要 pickle 序列化、再经管道传输，成本与字节数成正比。只有模块顶层、可 import 的函数能被 pickle：`lambda`、闭包、局部函数、打开的连接、线程锁都会报…' />


## 共享内存、进程开销与选型阈值

`SharedMemory` 在 `POSIX` 平台上用 `POSIX` 共享内存段，buf 可以直接当 memoryview 读写；`ShareableList`（3.8+）在其上封装定长列表。`Value` 与 `Array` 基于 ctypes，带一把默认锁，适合小标量或定长数组；

`Manager()` 起一个服务进程，返回 `DictProxy` / `ListProxy` 等代理，任何一次访问都是一次 IPC，比共享 ctypes 慢一两个量级，但支持任意可 pickle 对象，且代理本身还能继续传给别的进程。

进程启动有固定开销（spawn 要重新导入依赖，常是几十到数百毫秒），所以任务粒度必须够大，可以用 `chunksize` 和 `max_tasks_per_child` 调平。

选型阈值不是固定数字：先量「单任务 CPU 时间」与「序列化加启动时间」的比值，只有前者显著大才划算；数据量大时先问能不能用 `SharedMemory` 消除拷贝，而不是直接加进程数。

还有一个平台细节：macOS 上 `SharedMemory.size` 会向上取整到页大小，请求 16 字节得到的 `sh.size` 是 16384、请求 32000 得到 32768，因此应把业务长度单独存进参数，只断言 `sh.size` 不小于需求，别把 `sh.size` 当逻辑长度用。

**常见错误与定位**

| 现象 | 根因 | 修复 |
| --- | --- | --- |
| spawn 子进程递归创建进程 | 缺 if __name__ == '__main__': 守卫 | 把入口与 Process/Pool 创建放进守卫 |
| Can't pickle local object | lambda/闭包/局部函数/连接不可 pickle | 改顶层函数，或用 shared_memory 传大缓冲 |
| 多线程程序 fork 后卡死 | 子进程继承了其它线程持有的锁 | 改 spawn/forkserver，或确保 fork 时无其它线程 |
| 多进程反而更慢 | pickle 大对象 + 进程启动开销超过并行收益 | 量 CPU 时间与序列化时间之比，增大 chunksize 或共享内存 |


## 用共享内存做并行数组求和，绕开 pickle 拷贝

要对一个 400 万元素的数组分块求和，若把整块列表作为 `Pool` 的参数传，每个子进程都会收到一份 pickle 副本，内存与序列化先爆。

正确做法是把数据放进 `SharedMemory`，只把 (名字, 起止下标) 这种极小的元组传给 worker，子进程按名字 attach 到同一段内存、在 buf 上切片计算，返回各块的标量和。主进程汇总后再 close 加 unlink 释放。

下面用标准库跑通这条路径：用 `array` 把字节视图还原成定长整数，worker 只做切片 sum。真实数值计算会换 NumPy 并配 dtype，但「共享段只传句柄、结果只回标量」这一结构不变。

```python
import array
import multiprocessing as mp
from multiprocessing import shared_memory as shm

def partial_sum(args):
    name, start, end, total_len = args
    block = shm.SharedMemory(name=name)
    try:
        raw = array.array('q')
        raw.frombytes(bytes(block.buf[: total_len * 8]))
        return sum(raw[start:end])
    finally:
        block.close()

if __name__ == '__main__':
    N = 4000
    sh = shm.SharedMemory(create=True, size=N * 8)
    arr = array.array('q', range(N))
    sh.buf[: N * 8] = arr.tobytes()
    chunks = [(sh.name, i, i + 1000, N) for i in range(0, N, 1000)]
    with mp.Pool(processes=2) as pool:
        parts = pool.map(partial_sum, chunks)
    print('parts', len(parts), 'total', sum(parts))
    print('expected', sum(range(N)))
    sh.close()
    sh.unlink()
```

<Callout type="idea" title='落地提示' text='大数组用 shared_memory / 内存映射，任务粒度用 chunksize 调平，避免在进程间传大对象' />

<CheckList id='P064b' title='上线前自检' :items='["能复现并解释「spawn 平台把 lambda 或打开的连接传给子进程」", "能复现并解释「忘了 if __name__ == &#39;__main__&#39;…」", "能复现并解释「多进程传 200MB 列表却埋怨没加速」", "能用一条命令验证 fork / spawn / forkserver", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| spawn 平台把 lambda 或打开的连接传给子进程 | spawn 要 pickle 参数，lambda/闭包/连接/锁没有可引用的顶层名 | 改成模块顶层函数；大对象用 SharedMemory 或内存映射，别塞进 args |
| 忘了 if __name__ == '__main__': 守卫 | spawn 子进程会重新导入主模块，模块顶层又创建 Pool，形成递归创建进程 | 把 Process/Pool 的创建与启动全部放进守卫；模块顶层只放定义 |
| 多进程传 200MB 列表却埋怨没加速 | 跨进程参数与返回值要 pickle，序列化与内存拷贝常超过并行收益 | 用 SharedMemory / 内存映射，加大任务粒度与 chunksize，先量 CPU 时间与序列化时间之比 |

<Callout type="warn" title='本讲最容易踩的坑' text='spawn 平台把 lambda 或打开的连接传给子进程：spawn 要 pickle 参数，lambda/闭包/连接/锁没有可引用的顶层名' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：spawn 平台把 lambda 或打开的连…", "body": "spawn 要 pickle 参数，lambda/闭包/连接/锁没有可引用的顶层名", "tip": "改成模块顶层函数；大对象用 SharedMemory 或内存映射，别塞进 args"}, {"title": "第 2 步：忘了 if __name__ == &#39;__m…", "body": "spawn 子进程会重新导入主模块，模块顶层又创建 Pool，形成递归创建进程", "tip": "把 Process/Pool 的创建与启动全部放进守卫；模块顶层只放定义"}, {"title": "第 3 步：多进程传 200MB 列表却埋怨没加速", "body": "跨进程参数与返回值要 pickle，序列化与内存拷贝常超过并行收益", "tip": "用 SharedMemory / 内存映射，加大任务粒度与 chunksize，先量 CPU 时间与序列化时间之比"}]' />


## Pool._map_async 的 chunksize 推导公式

chunksize 不是拍脑袋的默认值，`Lib/multiprocessing/pool.py` 的 `Pool._map_async` 里有一段可复现的推导：chunksize, `extra = divmod`(`len(iterable)`, `len(self._pool)` * 4)，extra 非零则加一，iterable 为空时置 0。

目标是把任务切成大约进程数 4 倍的包，让负载不均时仍有足够的包做动态均衡，又不至于让 IPC 往返次数失控；向上取整保证余数里的任务不会被丢掉。12 个进程、1000 个任务算出 21，实际切成 48 包；4 个进程、100 个任务算出 7。

拿到 chunksize 后，`Pool._task_handler` 线程从 _taskqueue 取出 (job, idx, func, args) 按这个粒度打包，经 _quick_put（`Connection.send_bytes`）写进 _inqueue，worker 进程用 mapstar 展开后逐个执行，结果走 _outqueue 回到父进程。

这里能推出那次 200MB 列表工单的完整链路：序列化发生在父进程的提交侧，一个包里若有 21 个任务、每个任务都引用同一份大列表，ForkingPickler 会在同一个 buffer 里反复写这些字节，chunksize 越大单次 send_bytes 的阻塞越久。

imap / imap_unordered 默认 `chunksize=1`，适合任务耗时差异大的场景；map 的自动粒度只优化调度，不优化数据体积，两者要分开调。

```python
import multiprocessing.pool as pool_mod
import inspect

def chunksize(n, nproc):
    if n == 0:
        return 0
    size, extra = divmod(n, nproc * 4)
    return size + 1 if extra else size

print('12 workers 1000', chunksize(1000, 12))
print('12 workers 10', chunksize(10, 12))
print('4 workers 100', chunksize(100, 4))
print('empty', chunksize(0, 4))
print('formula in pool.py', 'divmod' in inspect.getsource(pool_mod.Pool._map_async))

```

<OutputBox title='扩展示例运行结果' output='12 workers 1000 21\n12 workers 10 1\n4 workers 100 7\nempty 0\nformula in pool.py True' />

<LineByLine code='import multiprocessing.pool as pool_mod\nimport inspect\n\ndef chunksize(n, nproc):\n    if n == 0:\n        return 0\n    size, extra = divmod(n, nproc * 4)\n    return size + 1 if extra else size\n\nprint(&#39;12 workers 1000&#39;, chunksize(1000, 12))\nprint(&#39;12 workers 10&#39;, chunksize(10, 12))\nprint(&#39;4 workers 100&#39;, chunksize(100, 4))\nprint(&#39;empty&#39;, chunksize(0, 4))\nprint(&#39;formula in pool.py&#39;, &#39;divmod&#39; in inspect.getsource(pool_mod.Pool._map_async))\n' :notes='["导入 pool 模块，用来核对源码里的公式", "inspect.getsource 可以直接读回 _map_async 的源码文本", "空行，只用于分隔逻辑块，不影响执行结果。", "复现 Pool._map_async 里的 chunksize 推导", "空的可迭代对象按源码置 0", "divmod 把任务数除以进程数的 4 倍", "余数非零就向上取整，保证任务不丢", "12 进程 1000 任务：1000 除 48 余 40，得 21", "空行，只用于分隔逻辑块，不影响执行结果。", "任务数小于进程数 4 倍时，chunksize 退化为 1", "4 进程 100 任务：100 除 16 余 4，得 7", "空输入不产生任何任务包", "在真实源码里确认 divmod 确实存在，而不是凭记忆", "这一行 `print(&#39;formula in pool.py&#39;, &#39;divmod&#39; in inspect.gets` 的作用，可对照上方输出逐项核对。", "空行，只用于分隔逻辑块，不影响执行结果。"]' title='扩展示例逐行讲解' />


## ForkingPickler 与 reduction.py 的跨进程对象注册

跨进程传对象不走普通 `pickle.Pickler`，而是 `Lib/multiprocessing/reduction.py` 里的 ForkingPickler：它是 `pickle.Pickler` 的子类，类方法 register 维护一张 _extra_reducers 表，给 socket、Connection、文件描述符、同步原语等注册专用的 `__reduce__` 实现。

核心数据结构是 DupFd：父进程把待传的 fd 交给后台的 resource_sharer 服务进程登记，pickle 时只序列化一个取回句柄的 reducer；

子进程 unpickle 时 `DupFd.detach()` 通过 Unix socket 的 `SCM_RIGHTS` 把 fd 副本接收回来，于是子进程拿到的是指向同一资源的独立描述符，而不是一个被复制的对象。

Queue 的 _FeederThread 因此很关键：put 时先在调用线程里 `ForkingPickler.dumps` 成字节 buffer，再由管道 send_bytes 发出，序列化成本全部记在提交侧而非子进程；

manager 代理、Pool 的任务与结果也都经过这同一个入口。spawn 平台上的报错要分两类：lambda、闭包、局部函数的 `__reduce__` 指向一个子进程里查不到的名字，报 PicklingError 或 Can't pickle local object；

打开的数据库连接、线程锁带着不可复制的内核状态，即便有 reducer 也传不过去，只能在 initializer 里于子进程重新建立。这也解释了正文里数据量大时序列化盖过并行收益：不是进程慢，是父进程在提交前就把 bytes 写了一遍。

**对象在普通 pickle 与 ForkingPickler 下的可传性**

| 对象 | 普通 pickle | ForkingPickler | 传递途径或失败原因 |
| --- | --- | --- | --- |
| 模块顶层函数 | 按名字引用 | 同样可行 | 无需 reducer |
| socket / Connection | 不支持 | 支持 | resource_sharer 经 SCM_RIGHTS 传 fd |
| lambda / 闭包 | 不支持 | 不支持 | __reduce__ 指向子进程查不到的局部名 |
| 打开的数据库连接 | 不支持 | 不支持 | 应在 initializer 里于子进程重建 |
| pool 的任务元组 | 可行 | 可行 | _FeederThread 在提交侧序列化 |

<Term word='resource_sharer' text='multiprocessing 在后台起的一个服务进程，专门保管待跨进程传递的文件描述符；ForkingPickler 序列化的是它的注册句柄而不是 fd 本身，子进程 unpickle 时再通过 Unix socket 的 SCM_RIGHTS 取回描述符副本。' />


### spawn 的 preparation_data 与 spawn_main 握手

spawn 平台那次报错值得按提交链路复盘：Pool 提交任务时，_task_handler 在父进程把 (func, args, kwds) 交给 `ForkingPickler.dumps`，一旦 args 里塞了 lambda 或打开的连接，报的就是 PicklingError 或 Can't pickle local object，而且错在父进程的提交阶段，还没轮到子进程启动。

另一半问题是体积：一份 20000 个整数的列表序列化后接近 6 万字节、两万多条 pickle opcode，若每个任务都引用它，chunksize 打包出的一个 buffer 会被反复填充，父进程的 send_bytes 阻塞时间直接叠加到端到端延迟上。

修复顺序应该是先减数据，把大数组放进 `shared_memory.SharedMemory`，任务里只传 name 与切片范围，再调 chunksize，最后才考虑加进程数；

把函数提到模块顶层、连接放进 initializer 是另两条独立的前置条件。下面这段代码用 ForkingPickler 直接量化一份列表的序列化字节数与 opcode 数，并让 lambda 的失败以确定类型落在输出里，便于在 CI 里当作回归断言：提交侧的体积一旦翻倍，先怀疑数据而不是进程数。

注意 dumps 返回的是 memoryview，交给 pickletools 前要先转成 bytes。

```python
import multiprocessing.reduction as red
import pickletools

payload = list(range(20000))
buf = bytes(red.ForkingPickler.dumps(payload))
print('payload items', len(payload))
print('pickled bytes', len(buf))
print('opcodes', len(list(pickletools.genops(buf))))
try:
    red.ForkingPickler.dumps(lambda x: x)
    print('lambda picklable', True)
except Exception as e:
    print('lambda error', type(e).__name__)

```


## 练习、自测与速记

<Exercise title='基础：对比 fork / spawn / forkserver 的启动方法' task='打印 get_all_start_methods() 与 get_start_method()，再对每个可用方法用 get_context(name).get_start_method() 确认可创建；说明为何 macOS 默认不是 fork。' solution='import multiprocessing as mp\nprint(&#39;all&#39;, mp.get_all_start_methods())\nprint(&#39;default&#39;, mp.get_start_method())\nfor name in mp.get_all_start_methods():\n    print(name, &#39;-&gt;&#39;, mp.get_context(name).get_start_method())' explain='macOS 自 3.8 起默认 spawn，避免带线程/系统框架时 fork 的不稳定；get_context 可显式选方法以便跨平台复现，forkserver 仅 Unix 可用。' />

<Exercise title='进阶：量化 pickle 成本并改用共享句柄' task='对 list(range(10000)) 用 pickle.dumps 量字节数，与 sys.getsizeof 对比；再说明把大数组换成「SharedMemory 名 + 下标」后传给 worker 的字节数变化。' solution='import pickle, sys\ndata = list(range(10000))\nblob = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)\nprint(&#39;pickle&#39;, len(blob), &#39;shallow size&#39;, sys.getsizeof(data))\nsmall = pickle.dumps((&#39;psm_name&#39;, 0, 1000, 10000))\nprint(&#39;handle bytes&#39;, len(small), &#39;smaller&#39;, len(small) &lt; len(blob))' explain='一万个整数的 pickle 接近 3 万字节，而 (名字, 下标区间, 长度) 只有几十字节；把大对象留在共享段、只传句柄，能消除绝大部分 IPC 拷贝。' />

<Quiz no='064-1' q='关于 macOS 上 multiprocessing 的默认启动方法，正确的是？' :options='["3.8+ 默认 spawn，需要 __main__ 守卫且参数可 pickle", "默认 fork，无需守卫", "默认 forkserver", "默认由 os.cpu_count() 决定"]' answer="0" explain='macOS 自 3.8 起把默认改为 spawn 以规避带线程时 fork 的不稳定；Windows 也只有 spawn，Linux 传统默认 fork（3.14 拟改 forkserver）。' />

<Quiz no='064-2' q='把 lambda 作为 Process 的 target 在 spawn 平台上会怎样？' :options='["pickle 报 PicklingError / Can&#39;t pickle local object", "正常运行，lambda 被复制到子进程", "自动转成顶层函数", "只在 fork 平台报错"]' answer="0" explain='spawn 要 pickle 参数与 target，lambda 没有可 import 的顶层引用名；应改成模块顶层函数。fork 不序列化所以不报，但语义仍不该依赖。' />

<Quiz no='064-3' q='多进程处理 200MB 数组却几乎没加速，最该先查什么？' :options='["pickle 序列化与内存拷贝是否吃掉了并行收益", "是否用了 RLock", "线程名是否重复", "sys.getswitchinterval 是否太大"]' answer="0" explain='进程间不共享内存，大对象要 pickle；先量「单任务 CPU 时间」与「序列化 + 启动时间」之比，再考虑 SharedMemory 或加大 chunksize。' />

<Predict no='064-4' q='在 spawn 平台把 list(range(10000)) 交给 Pool.map，每个 worker 会收到什么？' :options='["一份经 pickle 序列化后再反序列化的独立副本", "父进程列表的共享引用", "同一块共享内存视图", "空列表"]' answer='0' output='独立副本（pickle 约 29778 字节）' explain='参数经 ForkingPickler 序列化、通过 Pipe 传给子进程再还原，父子各有独立堆；这也是大对象让并行收益被序列化吃光的原因，应改用 SharedMemory。' />

<FillBlank no='064-5' tpl='___ multiprocessing as mp' :answers='["import"]' hint='回想本讲关于 fork / spawn / forkserver 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 三种启动方法与平台默认值 的落点。' />

<KnowledgeCard :points='["进程各有独立 GIL 与堆，CPU 密集才能真正并行；代价是地址空间隔离与 pickle 序列化", "启动方法：fork 快但多线程不安全（3.12 起告警）、spawn 安全但需 __main__ 守卫且参数可 pickle、forkserver 折中且仅 Unix", "macOS 3.8+ / Windows 默认 spawn；Linux 传统默认 fork，3.14 起改为 forkserver", "Pool 的 chunksize 把任务打包减少 IPC；map 按序、imap/imap_unordered 可流式", "大数组用 SharedMemory（3.8+）传名字句柄，用完 close + unlink；Value/Array 带 ctypes 锁，Manager 代理每次访问一次 IPC", "先量单任务 CPU 时间与序列化加启动时间之比；任务粒度太小或对象太大，加进程只会更慢"]' :pitfalls='["spawn 平台把 lambda 或打开的连接传给子进程", "忘了 if __name__ == &#39;__main__&#39;: 守卫", "多进程传 200MB 列表却埋怨没加速", "在 spawn 平台把不可 pickle 的对象（lambda、打开的连接）传给子进程，会在启动时报莫名其妙的错误"]' summary='进程之间地址空间隔离，所有跨进程数据都要序列化；数据量大时，序列化成本可能超过并行收益' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 进程各有独立 GIL 与堆，CPU 密集才能真正并行；代价是地址空间隔离与 pickle 序列化 | 建立直觉 |
| 启动方法：fork 快但多线程不安全（3.12 起告警）、spawn 安全但需 __main__ 守卫且参数可 pickle、forkserver 折中且仅 Unix | 跑通示例 |
| macOS 3.8+ / Windows 默认 spawn；Linux 传统默认 fork，3.14 起改为 forkserver | 深入边界 |
| Pool 的 chunksize 把任务打包减少 IPC；map 按序、imap/imap_unordered 可流式 | 工程落地 |
| 大数组用 SharedMemory（3.8+）传名字句柄，用完 close + unlink；Value/Array 带 ctypes 锁，Manager 代理每次访问一次 IPC | 随堂检测 |
| 先量单任务 CPU 时间与序列化加启动时间之比；任务粒度太小或对象太大，加进程只会更慢 | 复盘 |

1. 进程各有独立 GIL 与堆，CPU 密集才能真正并行；代价是地址空间隔离与 pickle 序列化

2. 启动方法：fork 快但多线程不安全（3.12 起告警）、spawn 安全但需 __main__ 守卫且参数可 pickle、forkserver 折中且仅 Unix

3. macOS 3.8+ / Windows 默认 spawn；Linux 传统默认 fork，3.14 起改为 forkserver

[下一讲：进程间通信：Queue、Pipe 与信号](/concurrency/ipc)

```bash
python -c "from concurrent.futures import ThreadPoolExecutor as P; print(list(P(2).map(abs,[-1,-2])))"
```

在仓库根目录跑一遍上面这条命令，可以复现本讲与 fork / spawn / forkserver 相关的一次检查；改动实现后重跑，若输出与页面上的预期不符，再回到主示例逐行定位。把它加进 CI 就能在依赖或版本变化时及时发现偏差。


---

<Callout type="tip" title="配套示例代码可直接运行" text="把仓库 clone 到本地后执行下面的命令，就能依次复现正文里的四段示例；文件中按主示例、对照写法、原理验证、工程案例分段，并附预期输出注释。" />

**本讲示例代码** · 仓内路径 `examples/lessons/064-multiprocessing.py`

```bash
python3 examples/lessons/064-multiprocessing.py
```

[在 GitHub 查看 / 下载源码](https://github.com/lfire/python/blob/main/examples/lessons/064-multiprocessing.py) · [全部示例代码索引](/examples/)
