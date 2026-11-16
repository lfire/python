"""
第 009 讲 · 字符串与编码：Unicode、str / bytes 与转义
与教程正文一一对应的示例代码

课程页面：/foundation/strings
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/009-strings.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/009-strings.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# str_len 2
# bytes_len 6
# hex e4b8ade69687
# roundtrip True
# codepoint 20013

s = '中文'
b = s.encode('utf-8')
print('str_len', len(s))
print('bytes_len', len(b))
print('hex', b.hex())
print('roundtrip', b.decode('utf-8') == s)
print('codepoint', ord('中'))

# ======================== 2. 对照写法 ========================
# 预期输出：
# decoded 中
# encoded_len 3
# strict_error UnicodeDecodeError
# ignore_len 0
# bom efbbbf
# utf16_hex 4100

import codecs
raw = bytes([0xe4, 0xb8, 0xad])
print('decoded', raw.decode('utf-8'))
print('encoded_len', len('中'.encode('utf-8')))
try:
    bytes([0xff]).decode('utf-8')
except UnicodeDecodeError as e:
    print('strict_error', type(e).__name__)
print('ignore_len', len(bytes([0xff]).decode('utf-8', errors='ignore')))
print('bom', codecs.BOM_UTF8.hex())
print('utf16_hex', 'A'.encode('utf-16-le').hex())

# ======================== 3. 原理验证 ========================
# 预期输出：
# default_encoding utf-8
# fs_encoding_utf8 True
# bom_utf8 efbbbf
# codepoint_hex 0x4e2d
# ascii_of_A 41

import sys, codecs
print('default_encoding', sys.getdefaultencoding())
print('fs_encoding_utf8', 'utf' in sys.getfilesystemencoding().lower())
print('bom_utf8', codecs.BOM_UTF8.hex())
print('codepoint_hex', hex(ord('中')))
print('ascii_of_A', 'A'.encode('ascii').hex())

# ======================== 4. 工程案例 ========================

import codecs

def decode_once(blob, enc):
    return blob.decode(enc)

def summarize(blob):
    return blob[:6].hex()

def encode_once(text):
    return text.encode('utf-8')

bom_blob = codecs.BOM_UTF8 + 'name,city'.encode('utf-8')
plain_blob = 'name,city'.encode('ascii')
for enc, blob in [('utf-8-sig', bom_blob), ('ascii', plain_blob)]:
    text = decode_once(blob, enc)
    out = encode_once(text)
    print('hex', summarize(blob))
    print('first', text.split(',')[0])
    print('clean', text == 'name,city')
    print('roundtrip', out.decode('utf-8') == text)
