---
title: 第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event
description: 用正确的原语表达协作关系
---

<StageHeader stage='L6 · 并发与异步' level='★★★☆☆' time='40 分钟' goal='用正确的原语表达协作关系' prereq='第 061 讲 · threading：线程生命周期与共享状态' />

# 第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event

上一讲亲手复现了竞态：GIL 只保单条字节码，读—改—写仍是好几条。既然多个线程要改同一份状态，就得表达它们之间的关系，而不是到处补锁。把眼光挪一挪，线程同步描述的本是协作：一个生产者往缓冲放、几个消费者取，满了要等、空了也要等；或者让一批线程都到齐了再一起出发。

从 `Lock` 与 `RLock` 起步，走到 `Condition` 的等待通知、`Semaphore` 的限流、`Event` 的一次广播和 `Barrier` 的汇合，最后谈死锁四条件与规避。需要你熟悉线程、共享变量与竞争条件；读完后能按「关系」挑对原语，按数据而非按代码定锁粒度，并用超时和可观测日志兜底。


## 缓存预热器里同一把锁被重入，进程挂住

一个缓存预热器用 `threading.Lock` 保护共享字典，回调里又调用了另一个同样要拿这把锁的函数，进程偶发卡死；有人把 Lock 换成 `RLock`，说「就不死锁了」，其实只是把回调链的设计问题盖住了。

另一次故障里生产者用 `notify()` 只唤醒一个消费者，某个消费者在 wait 里被虚假唤醒后没重新检查条件，拿了空列表直接崩。还有人拿全局 `Event` 做「一次性开闸」，却在每个请求里 `clear()`，结果后到的线程永久阻塞。这几件事都在问同一个问题：同步原语表达的是协作关系，不是「加锁」两个字。

互斥用 Lock、条件等待用 `Condition`、容量用 `Semaphore`、一次性广播用 `Event`、多方汇合用 `Barrier`；原语选错，或是漏了谓词重查，代码往往要到压测下才露出死锁与竞态。

<Callout type="warn" title='先看一个真实会出错的写法' text='在 wait 后直接用数据，不重新检查条件：wait 可能被虚假唤醒，或条件已被别的等待者消费，拿到的是旧状态或空值' />


## Lock 与 RLock 以及死锁的四个条件

`threading.Lock` 是 C 层 `_thread.lock` 的一层薄包装，`acquire` 返回 bool，`release()` 放行，`locked()` 查询状态；它不记录属主，任何线程都能 release，因此误释放别的锁会静默破坏互斥。

它是原始锁，同一线程第二次 acquire 就会死锁，必须用 `with lock:` 保证成对。RLock 可重入：内部记录属主线程与递归计数，只有属主能 release，且释放次数要与获取次数相同。Coffman 给出死锁的四个必要条件：互斥、持有并等待、不可剥夺、循环等待；

破坏任意一条即可，工程上最实用的是统一加锁顺序（破循环等待）与 `acquire(timeout=...)` 超时回退（破无限等待）。

两个高频反模式要避开：持锁时调用外部回调（对方可能反过来拿同一把锁），以及在持锁段里做 IO（把临界区拖长、放大切换概率）。用 RLock 掩盖「回调里又取同一把锁」，只是把死锁推迟到跨线程场景，正确做法是把那次调用移出临界区。

**同步原语表达的关系与默认参数**

| 原语 | 表达的关系 | 关键默认值 | 误用后果 |
| --- | --- | --- | --- |
| Lock | 互斥 | acquire(blocking=True, timeout=-1) | 同线程二次 acquire 自锁死 |
| RLock | 可重入互斥 | 记录属主线程与递归计数 | 用错 release 次数或掩盖回调死锁 |
| Condition | 条件等待 / 通知 | lock=None 时自建 RLock；notify(n=1) | 漏谓词重查被虚假唤醒击穿 |
| Semaphore | 容量 / 限流 | value=1 | 当互斥用会放过多个线程 |
| Event | 一次性状态广播 | 初始未置位 | 每请求 clear 会让后来者永久阻塞 |
| Barrier | 多方汇合 | parties；action=None；timeout=None | 任一方超时置 broken，后续抛 BrokenBarrierError |

**死锁四条件与破坏手段**

| Coffman 条件 | 含义 | 工程破坏手段 |
| --- | --- | --- |
| 互斥 | 资源一次只给一个线程 | 用不可变数据或无锁结构减少共享 |
| 持有并等待 | 拿着一把锁去等另一把 | 一次性按固定顺序申请全部锁 |
| 不可剥夺 | 已持有的锁不能被抢 | acquire(timeout=...) 超时回退 |
| 循环等待 | A 等 B、B 等 A 成环 | 全局锁编号，严格按编号递增获取 |

<Callout type="tip" title='核心心智模型' text='`threading.Lock` 是 C 层 `_thread.lock` 的一层薄包装，`acquire` 返回 bool，`release()` 放行，`locked()` 查询状态；它不记录属主，任何线程都能 release，因此误释放别的锁会静默破坏互斥。它是原始锁，同一线程第二次 acqu' />

<ConceptDiagram type='layers3' title='第 062 讲 · Lock / RLock 与死锁四个条件' labels='Lock / RLock 与死锁四个条件|Condition、Semaphore 与 |锁的粒度、超时与可观测性' caption='用正确的原语表达协作关系' />

这张图把本讲的三条线索并排放在一起：先看问题从哪里来，再看规则在哪里生效，最后看它落到工程的哪一处。建议顺着箭头走一遍，再回到主示例里找对应的实现。图可以点击放大，滚轮与双指缩放，也可以拖拽平移。


## 对照：持锁重入与 RLock 的输出

```python
import threading

cond = threading.Condition()
ready = []
out = []

def consumer():
    with cond:
        cond.wait_for(lambda: len(ready) >= 3)
        out.extend(ready)

def producer():
    for i in range(3):
        with cond:
            ready.append(i)
            cond.notify_all()

c = threading.Thread(target=consumer, name='consumer')
c.start()
producer()
c.join()
print('out', out)
print('wait_for rechecks', len(out) == 3)

lock = threading.Lock()
counter = [0]
def add():
    for _ in range(5000):
        with lock:
            counter[0] += 1
ts = [threading.Thread(target=add) for _ in range(4)]
for t in ts: t.start()
for t in ts: t.join()
print('locked', counter[0])
```

<OutputBox title='主示例运行结果' output='out [0, 1, 2]\nwait_for rechecks True\nlocked 20000' note='输出可能随 Python 版本与平台略有差异；以本机实际执行结果为准。' />

<LineByLine code='import threading\n\ncond = threading.Condition()\nready = []\nout = []\n\ndef consumer():\n    with cond:\n        cond.wait_for(lambda: len(ready) &gt;= 3)\n        out.extend(ready)\n\ndef producer():\n    for i in range(3):\n        with cond:\n            ready.append(i)\n            cond.notify_all()\n\nc = threading.Thread(target=consumer, name=&#39;consumer&#39;)\nc.start()\nproducer()\nc.join()\nprint(&#39;out&#39;, out)\nprint(&#39;wait_for rechecks&#39;, len(out) == 3)\n\nlock = threading.Lock()\ncounter = [0]\ndef add():\n    for _ in range(5000):\n        with lock:\n            counter[0] += 1\nts = [threading.Thread(target=add) for _ in range(4)]\nfor t in ts: t.start()\nfor t in ts: t.join()\nprint(&#39;locked&#39;, counter[0])' :notes='["导入 threading 使用 Condition 与 Lock", "Condition() 默认自带一把 RLock", "共享缓冲区，生产者往里放", "消费者取走的结果", "消费者先持锁再等待条件", "进入临界区，wait 会临时释放这把锁", "内部 while 谓词循环，抵御虚假唤醒", "条件满足后一次性取走全部就绪项", "生产者分三次投递", "循环三次", "每次都在持锁状态下改共享数据", "追加一项", "唤醒所有等待者，避免只叫醒一个不够", "消费者线程先启动", "启动后会在 wait 处释放锁阻塞", "主线程跑生产者", "join 等消费者收完", "三个元素按序被消费", "谓词重查保证拿到完整三项", "Lock 演示互斥保护计数器", "用可变容器承载计数值", "四线程各执行这个函数", "每线程加 5000 次", "进入互斥临界区", "读—改—写被锁整体保护", "创建四个线程", "启动", "等待全部结束", "加锁后恒为 20000，无丢失更新"]' title='第 062 讲 · 线程同步：Lock、Condition、Semaphore、Event' />

读的时候不妨顺手改一个参数再跑一次，看看输出会怎么变。能说清「为什么是变成这样」，比记住这段结果更有用；如果一时说不上来，回到左侧点开那一行，讲解就写在旁边。

```python
import threading

go = threading.Event()
seen = []
ws = [threading.Thread(target=lambda i=i: (go.wait(), seen.append(i))) for i in range(3)]
for t in ws: t.start()
print('before set', go.is_set())
go.set()
for t in ws: t.join()
print('broadcast', sorted(seen))

sem = threading.BoundedSemaphore(2)
sem.acquire()
sem.release()
try:
    sem.release()
    sem.release()
    sem.release()
except ValueError as e:
    print('overflow', type(e).__name__)

bar = threading.Barrier(2)
def peer():
    bar.wait()
t = threading.Thread(target=peer)
t.start()
print('parties', bar.parties, 'broken', bar.broken)
bar.wait()
t.join()

rl = threading.RLock()
with rl:
    with rl:
        print('rlock reentrant', True)
```

<OutputBox title='对照写法：先自己猜，再点开' output='before set False\nbroadcast [0, 1, 2]\noverflow ValueError\nparties 2 broken False\nrlock reentrant True' guess="true" />

<Compare :panels='[{"label": "主示例", "code": "import threading\n\ncond = threading.Condition()\nready = []\nout = []\n\ndef consumer():\n    with cond:\n        cond.wait_for(lambda: len(ready) &gt;= 3)\n        out.extend(ready)\n\ndef producer():\n    for i in range(3):\n        with cond:\n            ready.append(i)\n            cond.notify_all()\n\nc = threading.Thread(target=consumer, name=&#39;consumer&#39;)\nc.start()\nproducer()\nc.join()\nprint(&#39;out&#39;, out)\nprint(&#39;wait_for rechecks&#39;, len(out) == 3)\n\nlock = threading.Lock()\ncounter = [0]\ndef add():\n    for _ in range(5000):\n        with lock:\n            counter[0] += 1\nts = [threading.Thread(target=add) for _ in range(4)]\nfor t in ts: t.start()\nfor t in ts: t.join()\nprint(&#39;locked&#39;, counter[0])", "note": "Lock / RLock 与死锁四个条件"}, {"label": "对照 / 进阶", "code": "import threading\n\ngo = threading.Event()\nseen = []\nws = [threading.Thread(target=lambda i=i: (go.wait(), seen.append(i))) for i in range(3)]\nfor t in ws: t.start()\nprint(&#39;before set&#39;, go.is_set())\ngo.set()\nfor t in ws: t.join()\nprint(&#39;broadcast&#39;, sorted(seen))\n\nsem = threading.BoundedSemaphore(2)\nsem.acquire()\nsem.release()\ntry:\n    sem.release()\n    sem.release()\n    sem.release()\nexcept ValueError as e:\n    print(&#39;overflow&#39;, type(e).__name__)\n\nbar = threading.Barrier(2)\ndef peer():\n    bar.wait()\nt = threading.Thread(target=peer)\nt.start()\nprint(&#39;parties&#39;, bar.parties, &#39;broken&#39;, bar.broken)\nbar.wait()\nt.join()\n\nrl = threading.RLock()\nwith rl:\n    with rl:\n        print(&#39;rlock reentrant&#39;, True)", "note": "Condition、Semaphore 与 Event 的语义差别"}]' title='两种写法对照' note='差异集中在 Lock 与 RLock；先看输出，再找背后的规则。' />


## Condition、Semaphore、Event 各表达什么关系

`Condition(lock=None)` 默认自带一把 `RLock`，`wait(timeout=None)` 会先释放底层锁、阻塞，被唤醒后重新拿到锁才返回，所以调用 wait/notify 之前必须持锁。

`notify(n=1)` 只唤醒 n 个等待者，`notify_all()` 唤醒全部；

被唤醒之后条件可能已被别的线程改掉，所以必须配 `wait_for`，它内部是一段 `while not predicate()` 的谓词重查循环（`inspect.getsource` 能直接看到那个 while），天然抵御虚假唤醒。

`Semaphore(value=1)` 维护一个计数器，acquire 减一、release 加一，用来限流而非互斥；

`BoundedSemaphore` 在 release 超过初值时抛 `ValueError`，能抓到「放多了」的 bug。

`Event` 是「一次置位、广播所有等待者」：`set()` 之后 `is_set()` 恒为真，`wait()` 立即返回，直到显式 `clear()`；它表达的是状态闸门，不适合当成每个请求复用的开关。`Barrier` 让 parties 个线程在 `wait()` 处汇合，最后一个到达时执行 action 再一起放行；

任一方超时或调用 `abort()` 会把屏障置为 broken，后续 wait 抛 `BrokenBarrierError`。

**wait / notify 与超时接口**

| 接口 | 要求 | 边界行为 |
| --- | --- | --- |
| Condition.wait(timeout=None) | 调用前必须持锁 | 内部释放锁，被唤醒后重新获取才返回 |
| Condition.wait_for(predicate, timeout=None) | 调用前必须持锁 | while 循环重查谓词，超时返回最后结果 |
| Condition.notify(n=1) / notify_all() | 调用前必须持锁 | 只唤醒不释放锁，等待者要等锁空出 |
| Lock.acquire(timeout=...) | 无 | 返回 bool；False 表示超时，可降级 |
| Event.wait(timeout=None) | 无 | set 后立即返回；未 set 则超时返回 False |


## _thread.lock 之上的 wait 语义

threading 的同步原语都建在 C 层 `_thread.lock` 之上：`Lock` 是对它的薄包装，`RLock` 在 Python 层额外维护 _owner（线程 ident）与递归计数，`Condition` 持有一把锁加两个等待队列。

wait 的语义是「释放锁 → 挂到等待队列 → 被 notify 移到锁队列 → 重新 acquire」，因此它天然要求调用者先持锁；notify 只是把等待者从一个队列挪到另一个，并不立刻让出锁，被唤醒的线程要等当前持锁者退出 with 才能继续。

`Semaphore` 用一个计数器加 Condition：acquire 在计数为零时 wait，release 加一并 notify；

`BoundedSemaphore` 额外记住初值，release 超过就抛 `ValueError`。

`Event` 用一把锁加一个布尔标志，set 把标志置真并 notify_all，clear 只是把标志清回假、不会「唤醒」任何人——这正是每请求 clear 会漏掉后来者的原因。死锁的四个条件在 CPython 里没有自动检测，只有靠统一锁顺序与超时把它变成可诊断的失败，而不是静默挂起。

<Term word='Lock 与 RLock' text='`threading.Lock` 是 C 层 `_thread.lock` 的一层薄包装，`acquire` 返回 bool，`release()` 放行，`locked()` 查询状态；它不记录属主，任何线程都能 release，因此误释放别的锁会静默破坏互斥。它是原始锁，同一线程第二次 acquire 就会死锁，必' />

<Term word='Condition 等待通知' text='`Condition(lock=None)` 默认自带一把 `RLock`，`wait(timeout=None)` 会先释放底层锁、阻塞，被唤醒后重新拿到锁才返回，所以调用 wait/notify 之前必须持锁。`notify(n=1)` 只唤醒 n 个等待者，`notify_all()` 唤醒全部；被唤醒之后条件可' />

```python
import inspect
import sys
import threading

src = inspect.getsource(threading.Condition.wait_for)
print('has while loop', 'while' in src)
print('wait_for sig', str(inspect.signature(threading.Condition.wait_for)))
print('Semaphore value default', inspect.signature(threading.Semaphore).parameters['value'].default)
print('Event wait sig', str(inspect.signature(threading.Event.wait)))
print('switch interval', sys.getswitchinterval() == 0.005)
```

<OutputBox title='原理验证' output='has while loop True\nwait_for sig (self, predicate, timeout=None)\nSemaphore value default 1\nEvent wait sig (self, timeout=None)\nswitch interval True' />


## 锁的粒度、超时与可观测性

锁粒度要按数据而不是按代码行划分：保护同一个共享结构的读写用同一把锁，无关结构拆成不同锁以降低竞争。缩短临界区比换一把更快的锁有效得多：只在读—改—写的那几行持锁，计算、序列化、网络调用一律移出去。

所有阻塞获取都给超时（`acquire(timeout=...)`、`Condition.wait(timeout=...)`），超时后记一条带锁名、线程名与持有时长的日志并走降级，而不是无限等；

这样线上死锁至少是可诊断的。可观测性还包括：给锁命名、统计等待时长分布、在持锁超过阈值时告警。Python 层的 Lock 与 GIL 是两层东西：GIL 保护解释器的引用计数，Lock 保护你的业务数据，前者不会替后者做事。

最后，threading 模块的这些原语都基于同一个 C 层锁实现，跨线程可用但不能跨进程，跨进程要用 multiprocessing 里的同名类。


## 有界缓冲区的生产者—消费者：容量、条件与优雅收尾

一个采集端把日志批量写库，生产者快、消费者慢，既要限制在途条目数避免内存涨爆，又要在主线程发出停止信号后把队列排空。用两个 `Condition`（not_full 与 not_empty）加一个固定容量 deque 来表达：生产者在缓冲满时 wait，消费者在空时 wait，双方都用 `wait_for` 重查谓词；

停止用单独的 `Event` 置位并 `notify_all` 唤醒所有等待者，消费者在「队列空且已停止」时退出。所有 wait 都带超时，超时记一条日志，防止异常路径永久挂起。这个结构把 `Semaphore` 的容量、`Condition` 的条件、`Event` 的广播三者各归其位，是线程池有界队列的一个手写原型。

```python
import collections
import threading
import time

class BoundedBuffer:
    def __init__(self, cap):
        self.cap = cap
        self.buf = collections.deque()
        self.cv = threading.Condition()
        self.stopped = threading.Event()
    def put(self, item):
        with self.cv:
            self.cv.wait_for(lambda: len(self.buf) < self.cap or self.stopped.is_set())
            if self.stopped.is_set():
                return False
            self.buf.append(item)
            self.cv.notify_all()
        return True
    def drain(self):
        while True:
            with self.cv:
                ok = self.cv.wait_for(
                    lambda: len(self.buf) > 0 or self.stopped.is_set(), timeout=0.2)
                if self.buf:
                    item = self.buf.popleft()
                    self.cv.notify_all()
                elif self.stopped.is_set():
                    return
    def stop(self):
        with self.cv:
            self.stopped.set()
            self.cv.notify_all()

if __name__ == '__main__':
    b = BoundedBuffer(2)
    t = threading.Thread(target=b.drain, name='writer')
    t.start()
    for i in range(6):
        b.put(i)
    b.stop()
    t.join(timeout=2)
    print('stopped', b.stopped.is_set(), 'alive', t.is_alive())
```

<Callout type="idea" title='落地提示' text='锁的粒度按数据而不是按代码划分，统一获取顺序，并用超时与可观测日志兜底' />

<CheckList id='P062b' title='上线前自检' :items='["能复现并解释「在 wait 后直接用数据，不重新检查条件」", "能复现并解释「持锁时调用外部回调或做网络 IO」", "能复现并解释「每个请求都 event.clear() 复用同一个 Even」", "能用一条命令验证 Lock 与 RLock", "关键路径有自动化测试与失败分支"]' />

**错因速查**

| 现象 | 根因 | 正确写法 |
| --- | --- | --- |
| 在 wait 后直接用数据，不重新检查条件 | wait 可能被虚假唤醒，或条件已被别的等待者消费，拿到的是旧状态或空值 | 一律用 cond.wait_for(predicate)，它内部是 while not predicate(): wait() 循环 |
| 持锁时调用外部回调或做网络 IO | 回调可能反向申请同一把锁形成循环等待；长临界区放大切换与竞争 | 把计算与 IO 移出临界区，回调在释放锁后执行；确需重入再考虑 RLock |
| 每个请求都 event.clear() 复用同一个 Event | clear 只是清标志，已经越过 wait 的线程不会被通知，后到者在下一次 set 前永久阻塞 | 一次性闸门用 Event 且只 set 不 clear；需要反复开合改用 Condition + 谓词或 Barrier |

<Callout type="warn" title='本讲最容易踩的坑' text='在 wait 后直接用数据，不重新检查条件：wait 可能被虚假唤醒，或条件已被别的等待者消费，拿到的是旧状态或空值' />

<StepBox title='现象 → 根因：按这个顺序排查' :steps='[{"title": "第 1 步：在 wait 后直接用数据，不重新检查条件", "body": "wait 可能被虚假唤醒，或条件已被别的等待者消费，拿到的是旧状态或空值", "tip": "一律用 cond.wait_for(predicate)，它内部是 while not predicate(): wait() 循环"}, {"title": "第 2 步：持锁时调用外部回调或做网络 IO", "body": "回调可能反向申请同一把锁形成循环等待；长临界区放大切换与竞争", "tip": "把计算与 IO 移出临界区，回调在释放锁后执行；确需重入再考虑 RLock"}, {"title": "第 3 步：每个请求都 event.clear() 复用", "body": "clear 只是清标志，已经越过 wait 的线程不会被通知，后到者在下一次 set 前永久阻塞", "tip": "一次性闸门用 Event 且只 set 不 clear；需要反复开合改用 Condition + 谓词或 Barrier"}]' />


## 练习、自测与速记

<Exercise title='基础：用 Condition 实现「攒够三个再处理」' task='起一个消费者线程用 wait_for(lambda: len(q) &gt;= 3) 等待，主线程分三次 put 并 notify_all，打印消费结果；说明 why 必须用 wait_for 而不是裸 wait。' solution='import threading\ncond = threading.Condition()\nq = []\ndef consumer():\n    with cond:\n        cond.wait_for(lambda: len(q) &gt;= 3)\n        print(&#39;got&#39;, list(q))\nt = threading.Thread(target=consumer)\nt.start()\nfor i in range(3):\n    with cond:\n        q.append(i)\n        cond.notify_all()\nt.join()' explain='裸 wait 只等一次通知，可能被虚假唤醒或条件被别人改掉就往下跑；wait_for 内部是 while 谓词循环，保证返回时条件确实成立。' />

<Exercise title='进阶：用超时与锁顺序规避死锁' task='两把锁 a、b，两个线程按相反顺序申请会死锁；改成按 id 排序统一顺序并用 acquire(timeout=0.1) 检测失败，打印是否两线程都顺利完成。' solution='import threading\na, b = threading.Lock(), threading.Lock()\ndef work(first, second):\n    locks = sorted([first, second], key=id)\n    with locks[0]:\n        got = locks[1].acquire(timeout=0.1)\n        try:\n            if got: pass\n        finally:\n            if got: locks[1].release()\n    return got\nts = [threading.Thread(target=lambda f=f, s=s: print(&#39;ok&#39;, work(f, s))) for f, s in [(a,b),(b,a)]]\nfor t in ts: t.start()\nfor t in ts: t.join()' explain='统一按 id 递增获取破坏循环等待；acquire 带超时破坏无限等待。两个条件任一被破坏就不会形成死锁，超时失败还能记日志降级。' />

<Quiz no='062-1' q='关于 Condition.wait，下列哪项准确？' :options='["调用前必须持锁，wait 内部释放锁并在被唤醒后重新获取", "调用前不能持锁，否则死锁", "wait 会一直持有锁直到返回", "notify 会立刻把锁交给等待者"]' answer="0" explain='wait 的语义是释放底层锁 → 阻塞 → 被 notify 移回锁队列 → 重新 acquire 再返回；notify 只挪队列不释放锁，等待者要等当前持锁者退出 with。' />

<Quiz no='062-2' q='生产者用 notify() 只唤一个消费者，最稳妥的修复是？' :options='["改用 notify_all() 并让等待方用 wait_for 重查谓词", "把 notify 换成 notify(2)", "给 wait 加更长的 timeout", "把 Lock 换成 RLock"]' answer="0" explain='notify(n) 只唤醒 n 个，条件可能被别的等待者消费；wait_for 的 while 谓词循环配合 notify_all 才能保证所有等待者醒后按条件正确前进。' />

<Quiz no='062-3' q='关于死锁四个条件，工程上最常用的两个破坏手段是？' :options='["统一加锁顺序 + acquire 超时回退", "把 Lock 全部换成 RLock", "增大 sys.getswitchinterval()", "只用 Event 不用锁"]' answer="0" explain='统一锁顺序破坏循环等待，超时回退破坏无限等待；换 RLock 只是掩盖重入，调 switchinterval 与死锁无关，Event 表达不了互斥。' />

<Predict no='062-4' q='threading.BoundedSemaphore(2) 在 acquire 一次、release 一次后再连续 release 三次，会怎样？' :options='["第一次多余 release 就抛 ValueError", "三次都成功，计数器变成 5", "阻塞直到有人 acquire", "抛 RuntimeError"]' answer='0' output='ValueError' explain='BoundedSemaphore 记住初值 2，release 使计数超过初值时立即抛 ValueError，用来捕获「放多了」的 bug；普通 Semaphore 不会检查。' />

<FillBlank no='062-5' tpl='___ threading' :answers='["import"]' hint='回想本讲关于 Lock 与 RLock 的规则' explain='补回关键字后重新运行主示例，确认输出仍与上方一致；这一行正是 Lock / RLock 与死锁四个条件 的落点。' />

<KnowledgeCard :points='["同步原语表达关系：互斥 Lock、条件 Condition、容量 Semaphore、广播 Event、汇合 Barrier", "wait 前必须持锁，内部释放再重获；一律用 wait_for(predicate) 的 while 谓词循环防虚假唤醒", "notify(n=1) 只叫醒 n 个且不释放锁；notify_all + 谓词重查才是稳妥组合", "BoundedSemaphore release 超初值抛 ValueError；Event 是一次性置位，反复 clear 会漏通知", "死锁四条件：互斥、持有并等待、不可剥夺、循环等待；统一锁顺序 + acquire(timeout) 最实用", "锁粒度按数据划分，持锁段不做 IO 与外部回调；所有阻塞获取带超时并留可观测日志"]' :pitfalls='["在 wait 后直接用数据，不重新检查条件", "持锁时调用外部回调或做网络 IO", "每个请求都 event.clear() 复用同一个 Event", "用 RLock 掩盖设计问题、或在持锁时调用外部回调，是死锁最常见的两个来源"]' summary='同步原语表达的是关系而不是「加锁」：互斥用 Lock、条件等待用 Condition、容量用 Semaphore、一次性广播用 Event' />

**速记索引**

| 要记住的结论 | 用在哪一步 |
| --- | --- |
| 同步原语表达关系：互斥 Lock、条件 Condition、容量 Semaphore、广播 Event、汇合 Barrier | 建立直觉 |
| wait 前必须持锁，内部释放再重获；一律用 wait_for(predicate) 的 while 谓词循环防虚假唤醒 | 跑通示例 |
| notify(n=1) 只叫醒 n 个且不释放锁；notify_all + 谓词重查才是稳妥组合 | 深入边界 |
| BoundedSemaphore release 超初值抛 ValueError；Event 是一次性置位，反复 clear 会漏通知 | 工程落地 |
| 死锁四条件：互斥、持有并等待、不可剥夺、循环等待；统一锁顺序 + acquire(timeout) 最实用 | 随堂检测 |
| 锁粒度按数据划分，持锁段不做 IO 与外部回调；所有阻塞获取带超时并留可观测日志 | 复盘 |

1. 同步原语表达关系：互斥 Lock、条件 Condition、容量 Semaphore、广播 Event、汇合 Barrier

2. wait 前必须持锁，内部释放再重获；一律用 wait_for(predicate) 的 while 谓词循环防虚假唤醒

3. notify(n=1) 只叫醒 n 个且不释放锁；notify_all + 谓词重查才是稳妥组合

[下一讲：线程池与 Future 模式](/concurrency/threadpool)

```bash
python -c "from concurrent.futures import ThreadPoolExecutor as P; print(list(P(2).map(abs,[-1,-2])))"
```

把输入换成你自己的数据，观察结果是否仍符合 Lock 与 RLock 的规则；不一致时先核对版本与依赖，再回到主示例逐行定位。这条命令也可以加进 CI 作为回归检查。
