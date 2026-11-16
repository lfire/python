"""
第 054 讲 · GIL 真相：存在原因、切换与影响边界
与教程正文一一对应的示例代码

课程页面：/core/gil
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/054-gil.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

注意：工程案例使用「事件循环 + 进程池」，在 spawn 启动方式或受限沙箱中
可能失败；文件已加环境兜底，会打印跳过原因而不是中断。

运行： python3 examples/lessons/054-gil.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# single 0.052 threads 0.211
# switchinterval 0.005

import threading, time

def cpu(n):
    s = 0
    for i in range(n):
        s += i * i
    return s

N = 1_000_000
t0 = time.perf_counter(); cpu(N); single = time.perf_counter() - t0

ts = [threading.Thread(target=cpu, args=(N,)) for _ in range(4)]
t0 = time.perf_counter()
for t in ts: t.start()
for t in ts: t.join()
multi = time.perf_counter() - t0
print('single', round(single, 3), 'threads', round(multi, 3))
print('switchinterval', __import__('sys').getswitchinterval())

# ======================== 2. 对照写法 ========================
# 预期输出：
# serial 0.402 threads 0.051

import threading, time

def io_bound():
    time.sleep(0.05)   # 进入系统调用前释放 GIL

def run(n, use_thread):
    t0 = time.perf_counter()
    if use_thread:
        ts = [threading.Thread(target=io_bound) for _ in range(n)]
        for t in ts: t.start()
        for t in ts: t.join()
    else:
        for _ in range(n): io_bound()
    return time.perf_counter() - t0

print('serial', round(run(8, False), 3), 'threads', round(run(8, True), 3))

# ======================== 3. 原理验证 ========================
# 预期输出：
# switchinterval 0.005
#   LOAD_GLOBAL 0 (counter)
#   LOAD_CONST 1 (1)
#   BINARY_OP 13 (+=)
#   STORE_GLOBAL 0 (counter)
#   RETURN_CONST 0 (None)

import dis, sys

counter = 0
def bump():
    global counter
    counter += 1

print('switchinterval', sys.getswitchinterval())
dis.dis(bump)

# ======================== 4. 工程案例 ========================

try:
    import asyncio, concurrent.futures, time

    def heavy(n):
        return sum(i * i for i in range(n))

    async def fetch(i):
        await asyncio.sleep(0.01)      # 模拟网络等待
        return i

    async def main(loop, pool, sem):
        async def one(i):
            async with sem:
                v = await fetch(i)
                return await loop.run_in_executor(pool, heavy, 20000 + v)
        return await asyncio.gather(*(one(i) for i in range(20)))

    with concurrent.futures.ProcessPoolExecutor(2) as pool:
        loop = asyncio.new_event_loop()
        sem = asyncio.Semaphore(8)
        t0 = time.perf_counter()
        out = loop.run_until_complete(main(loop, pool, sem))
        print(len(out), 'tasks done in', round(time.perf_counter() - t0, 3), 's')
        loop.close()
except Exception as _eg_e:
    print('跳过：当前环境不支持「事件循环 + 进程池」组合，'
          f'原因 {type(_eg_e).__name__}: {_eg_e}')
