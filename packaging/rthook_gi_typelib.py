# PyInstaller 运行时钩子（Linux GUI）：onefile 启动时把解压出的 gi 类型库目录
# 加进 GI_TYPELIB_PATH，否则 g_irepository 找不到 Gtk/WebKit2 类型库，
# gi.require_version('Gtk', '3.0') 会直接抛 ValueError。
import os
import sys

_base = os.path.join(getattr(sys, '_MEIPASS', ''), 'gi', 'girepository-1.0')
if os.path.isdir(_base):
    _old = os.environ.get('GI_TYPELIB_PATH', '')
    os.environ['GI_TYPELIB_PATH'] = _base + ((':' + _old) if _old else '')
