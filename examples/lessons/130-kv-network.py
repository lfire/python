"""
第 130 讲 · 实战 09 · KV 贯穿线 ② 协议帧与网络层
与教程正文一一对应的示例代码

课程页面：/projects/kv-network
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/130-kv-network.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/130-kv-network.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# frame sizes 16 14
# two in one read (['SET a 1', 'GET a'], 'complete')
# half frame ([], 'partial')
# with tail (['SET a 1'], 'partial')
# corrupt ([], 'bad checksum')
# oversize ([], 'frame too large')

import struct, zlib

MAGIC = b'KV'
VERSION = 1
MAX_FRAME = 1024

def encode(op, key, value=b''):
    parts = [op.encode(), key.encode()]
    if value:
        parts.append(value)
    body = b' '.join(parts)
    frame = MAGIC + bytes([VERSION]) + struct.pack('>H', len(body)) + body
    crc = zlib.crc32(frame) & 0xffffffff
    return frame + struct.pack('>I', crc)

def decode(stream):
    out = []
    while len(stream) >= 9:
        if stream[:2] != MAGIC:
            return out, 'bad magic'
        ver = stream[2]
        length = struct.unpack('>H', stream[3:5])[0]
        total = 5 + length + 4
        if length > MAX_FRAME:
            return out, 'frame too large'
        if len(stream) < total:
            break
        frame = stream[:5 + length]
        got = struct.unpack('>I', stream[5 + length:total])[0]
        if (zlib.crc32(frame) & 0xffffffff) != got:
            return out, 'bad checksum'
        if ver != VERSION:
            return out, 'version mismatch'
        out.append(frame[5:5 + length].decode())
        stream = stream[total:]
    return out, 'complete' if not stream else 'partial'

f1 = encode('SET', 'a', b'1')
f2 = encode('GET', 'a')
print('frame sizes', len(f1), len(f2))
print('two in one read', decode(f1 + f2))
print('half frame', decode(f1[:9]))
print('with tail', decode(f1 + f2[:-3]))
bad = bytearray(f1)
bad[-1] ^= 1
print('corrupt', decode(bytes(bad)))
print('oversize', decode(encode('SET', 'k', b'x' * 1100)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 2. 对照写法 ========================
# 预期输出：
# single [b'SET k hello']
# value with newline [b'SET k a', b'b']

def frame_newline(value):
    return b'SET k ' + value

def cut_newline(stream):
    return [p for p in stream.split(bytes([10])) if p]

one = frame_newline(b'hello')
two = frame_newline(b'a' + bytes([10]) + b'b')
print('single', cut_newline(one))
print('value with newline', cut_newline(two))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 3. 原理验证 ========================
# 预期输出：
# H size 2
# I size 4
# big endian 0102
# little endian 0201
# crc32 KV1 1051804123
# crc32 empty 0
# fsync signature (fd)

import struct, zlib, inspect, os

print('H size', struct.calcsize('>H'))
print('I size', struct.calcsize('>I'))
print('big endian', struct.pack('>H', 258).hex())
print('little endian', struct.pack('<H', 258).hex())
print('crc32 KV1', zlib.crc32(b'KV1'))
print('crc32 empty', zlib.crc32(b''))
print('fsync signature', str(inspect.signature(os.fsync)))

# —— 段间隔离：撤回上一段注册的自定义 finder，保证各段可独立运行 ——
import sys as _eg_sys
_eg_sys.meta_path[:] = [f for f in _eg_sys.meta_path if getattr(f, '__module__', None) != '__main__']

# ======================== 4. 工程案例 ========================

import asyncio, struct

async def handle(reader, writer):
    try:
        head = await reader.readexactly(4)
        length = struct.unpack('>I', head)[0]
        body = await reader.readexactly(length)
        writer.write(struct.pack('>I', len(body)) + body)
        await writer.drain()
    except asyncio.IncompleteReadError:
        pass
    finally:
        writer.close()

async def client(port, payload):
    reader, writer = await asyncio.open_connection('127.0.0.1', port)
    writer.write(struct.pack('>I', len(payload)) + payload)
    await writer.drain()
    n = struct.unpack('>I', await reader.readexactly(4))[0]
    reply = await reader.readexactly(n)
    writer.close()
    await writer.wait_closed()
    return reply

async def main():
    server = await asyncio.start_server(handle, '127.0.0.1', 0)
    port = server.sockets[0].getsockname()[1]
    out = await client(port, b'SET a 1')
    server.close()
    await server.wait_closed()
    return out

print(asyncio.run(main()))
