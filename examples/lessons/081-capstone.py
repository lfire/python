"""
第 081 讲 · 阶段综合：把脚本重构成可发布包
与教程正文一一对应的示例代码

课程页面：/engineering/capstone
GitHub：  https://github.com/lfire/python/blob/main/examples/lessons/081-capstone.py

本文件按正文顺序收录 4 段可运行代码：主示例 / 对照写法 / 原理验证 / 工程案例。
每段前面的注释里给出该段在页面上的预期输出，方便直接核对运行结果。

运行： python3 examples/lessons/081-capstone.py
"""

# ======================== 1. 主示例 ========================
# 预期输出：
# backend setuptools.build_meta
# name shortly version 0.3.0
# deps ['click>=8', 'httpx']
# entry shortly.cli:main
# legacy funcs ['shorten', 'expand']
# guarded True

import tomllib
import ast

PYPROJECT = chr(10).join([
    '[build-system]',
    "requires = ['setuptools>=68']",
    "build-backend = 'setuptools.build_meta'",
    '',
    '[project]',
    "name = 'shortly'",
    "version = '0.3.0'",
    "requires-python = '>=3.9'",
    "dependencies = ['click>=8', 'httpx']",
    '',
    '[project.scripts]',
    "shortly = 'shortly.cli:main'",
])
cfg = tomllib.loads(PYPROJECT)
print('backend', cfg['build-system']['build-backend'])
print('name', cfg['project']['name'], 'version', cfg['project']['version'])
print('deps', cfg['project']['dependencies'])
print('entry', cfg['project']['scripts']['shortly'])

LEGACY = chr(10).join([
    'import sys',
    'def shorten(url): return url[-6:]',
    "def expand(code): return 'https://x/' + code",
    "if __name__ == '__main__': print(shorten(sys.argv[1]))",
])
tree = ast.parse(LEGACY)
funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
print('legacy funcs', funcs)
print('guarded', any(isinstance(n, ast.If) for n in tree.body))

# ======================== 2. 对照写法 ========================
# 预期输出：
# pinned ['httpx==0.27.2']
# dev tools ['pytest>=8', 'ruff']
# python floor >=3.9

import tomllib

CFG = chr(10).join([
    '[project]',
    "name = 'shortly'",
    "version = '1.4.0'",
    "requires-python = '>=3.9'",
    "dependencies = ['click>=8', 'httpx==0.27.2']",
    '[project.optional-dependencies]',
    "dev = ['pytest>=8', 'ruff']",
])
p = tomllib.loads(CFG)['project']
print('pinned', [d for d in p['dependencies'] if '==' in d])
print('dev tools', p['optional-dependencies']['dev'])
print('python floor', p['requires-python'])

# ======================== 3. 原理验证 ========================
# 预期输出：
# relative import levels [1]
# top-level if count 1
# functions ['main']

import ast

SRC = chr(10).join([
    'from .core import shorten',
    'def main():',
    '    print(shorten("https://example.com"))',
    "if __name__ == '__main__':",
    '    main()',
])
tree = ast.parse(SRC)
rel = [n.level for n in ast.walk(tree)
       if isinstance(n, ast.ImportFrom) and n.level > 0]
guard = [n for n in tree.body if isinstance(n, ast.If)]
print('relative import levels', rel)
print('top-level if count', len(guard))
print('functions', [n.name for n in tree.body if isinstance(n, ast.FunctionDef)])

# ======================== 4. 工程案例 ========================

import tomllib
import ast

TREE = {
    'src/shortly/__init__.py': '',
    'src/shortly/core.py': 'def shorten(u): return u[-6:]',
    'src/shortly/cli.py': 'from .core import shorten',
    'pyproject.toml': '',
    'tests/test_core.py': '',
}

def has_src_layout(tree):
    return 'src/shortly/__init__.py' in tree and 'pyproject.toml' in tree

def parse_project(text):
    p = tomllib.loads(text)['project']
    required = ('name', 'version', 'requires-python', 'dependencies')
    missing = [k for k in required if k not in p]
    return missing, p.get('version'), len(p.get('dependencies', []))

def uses_relative_import(src):
    tree = ast.parse(src)
    return any(isinstance(n, ast.ImportFrom) and n.level > 0 for n in ast.walk(tree))

def has_main_guard(src):
    return any(isinstance(n, ast.If) for n in ast.parse(src).body)

PYPROJECT = chr(10).join([
    '[project]',
    "name = 'shortly'", "version = '1.4.0'",
    "requires-python = '>=3.9'",
    "dependencies = ['click>=8', 'httpx==0.27.2']",
])
CLI = chr(10).join([
    'from .core import shorten',
    'def main():',
    '    print(shorten("https://example.com"))',
    "if __name__ == '__main__':",
    '    main()',
])
print('src layout', has_src_layout(TREE))
print('meta', parse_project(PYPROJECT))
print('relative import', uses_relative_import(CLI))
print('main guard', has_main_guard(CLI))
