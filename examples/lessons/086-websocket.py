"""
第 086 讲 · WebSocket / SSE / 长轮询与实时推送
与教程正文一一对应的示例代码

课程页面：/server/websocket
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/086-websocket.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/086-websocket.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# Sec-WebSocket-Accept s3pPLMBiTxaQ9kYGzzhZRbK+xOo=
# GUID len 36

import hashlib
import base64

GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'
client_key = 'dGhlIHNhbXBsZSBub25jZQ=='
accept = base64.b64encode(hashlib.sha1((client_key + GUID).encode()).digest()).decode()
print('Sec-WebSocket-Accept', accept)
print('GUID len', len(GUID))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# frame lines ['id: 3', 'event: tick', 'retry: 3000', 'data: c', '', '']
# replay after id 1 [{'id': 2, 'data': 'b'}, {'id': 3, 'data': 'c'}]

def sse_frame(event_id, event, data, retry_ms=3000):
    lines = ['id: ' + str(event_id), 'event: ' + event,
             'retry: ' + str(retry_ms), 'data: ' + data, '', '']
    return chr(10).join(lines)

def resume(events, last_event_id):
    return [e for e in events if e['id'] > last_event_id]

events = [{'id': 1, 'data': 'a'}, {'id': 2, 'data': 'b'}, {'id': 3, 'data': 'c'}]
frame = sse_frame(3, 'tick', 'c')
print('frame lines', frame.split(chr(10)))
print('replay after id 1', resume(events, 1))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# 5 -> 2 header bytes
# 125 -> 2 header bytes
# 126 -> 4 header bytes
# 70000 -> 10 header bytes

import struct

OPCODE = {'text': 0x1, 'binary': 0x2, 'close': 0x8, 'ping': 0x9, 'pong': 0xA}
def header(n):
    if n < 126:
        return bytes([0x80 | OPCODE['text'], n])
    elif n < 65536:
        return bytes([0x80 | OPCODE['text'], 126]) + struct.pack('!H', n)
    return bytes([0x80 | OPCODE['text'], 127]) + struct.pack('!Q', n)
for n in (5, 125, 126, 70000):
    print(n, '->', len(header(n)), 'header bytes')

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import collections
import time

class Hub:
    def __init__(self, max_queue=3, idle_limit=30):
        self.conns = {}
        self.log = []
        self.next_id = 1
        self.max_queue = max_queue
        self.idle_limit = idle_limit
        self.dropped = 0
    def connect(self, cid, topics, now):
        self.conns[cid] = {'queue': collections.deque(), 'topics': set(topics), 'last': now}
    def publish(self, topic, payload, source='local'):
        msg = {'id': self.next_id, 'topic': topic, 'data': payload, 'source': source}
        self.next_id += 1
        self.log.append(msg)
        self.fanout(msg)
        return msg['id']
    def fanout(self, msg):
        for cid, c in self.conns.items():
            if msg['topic'] not in c['topics'] or msg['source'] == cid:
                continue
            if len(c['queue']) >= self.max_queue:
                c['queue'].popleft()
                self.dropped += 1
            c['queue'].append(msg)
    def resume(self, last_id):
        return [m for m in self.log if m['id'] > last_id]
    def tick(self, now):
        dead = [cid for cid, c in self.conns.items() if now - c['last'] > self.idle_limit]
        for cid in dead:
            del self.conns[cid]
        return dead

hub = Hub(max_queue=2, idle_limit=10)
hub.connect('c1', ('price',), now=0)
hub.connect('c2', ('news',), now=0)
for i in range(3):
    hub.publish('price', i)
print('c1 queued', len(hub.conns['c1']['queue']))
print('c2 queued', len(hub.conns['c2']['queue']))
print('dropped', hub.dropped)
print('resume from 1', [m['id'] for m in hub.resume(1)])
print('dead after tick', hub.tick(now=11))
