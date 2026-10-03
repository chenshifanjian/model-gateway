# -*- mode: python ; coding: utf-8 -*-
import os
import re
import sys

# 从 app.py 读取版本号，自动生成带版本号的 exe 名（如 v1.5.0-网关客户端）
with open('app.py', encoding='utf-8') as _f:
    _ver = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', _f.read()).group(1)
EXE_NAME = f'v{_ver}-网关客户端'

IS_WIN = sys.platform == "win32"

# 跨平台：数据文件与隐藏导入按平台裁剪
_datas = [('templates', 'templates'), ('models_meta.json', '.')]
if IS_WIN and os.path.exists('MicrosoftEdgeWebview2Setup.exe'):
    _datas.append(('MicrosoftEdgeWebview2Setup.exe', '.'))

_hiddenimports = ['PIL', 'PIL._tkinter_finder']
if IS_WIN:
    _hiddenimports.append('pystray._win32')
elif sys.platform == "darwin":
    _hiddenimports.append('pystray._darwin')
else:
    _hiddenimports.append('pystray._appindicator')


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6', 'shiboken6', 'numpy', 'matplotlib', 'scipy', 'pandas', 'PIL._tkinter_finder', 'tkinter', 'unittest', 'test', 'pytest', 'setuptools', 'pkg_resources', 'xmlrpc', 'ensurepip', 'lib2to3'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=EXE_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="ModelGateway.app",
        icon=None,
        bundle_identifier="com.modelgateway.client",
    )
