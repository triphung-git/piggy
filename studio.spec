# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

base_dir = Path.cwd()

# 1. Các thư mục tĩnh cần thiết cho ứng dụng
datas = [
    (str(base_dir / 'Web Overlay' / 'dist'), 'Web Overlay/dist'),
    (str(base_dir / 'templates'), 'templates'),
    (str(base_dir / 'assets'), 'assets'),
]

binaries = []
hiddenimports = [
    'webview',
    'webview.platforms.winforms',
    'webview.platforms.edgechromium',
    'clr',
    'fastapi',
    'fastapi.responses',
    'fastapi.staticfiles',
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespans',
    'uvicorn.lifespans.on',
    'starlette',
    'websockets',
    'requests',
    'dotenv',
    'rich',
    'PIL',
    'tft_studio',
    'tft_studio.core',
    'tft_studio.core.paths',
    'tft_studio.core.config',
    'tft_studio.riot',
    'tft_studio.riot.client',
    'tft_studio.data',
    'tft_studio.data.parser',
    'tft_studio.render',
    'tft_studio.render.generator',
    'tft_studio.render.exporter',
    'tft_studio.service',
    'tft_studio.service.match_service',
    'tft_studio.service.file_watcher',
    'tft_studio.api',
    'tft_studio.api.hub',
]

# Thu thập đầy đủ các submodules của uvicorn
try:
    u_datas, u_binaries, u_hidden = collect_all('uvicorn')
    datas += u_datas
    binaries += u_binaries
    hiddenimports += u_hidden
except Exception:
    pass

block_cipher = None

a = Analysis(
    ['desktop/app.py'],
    pathex=[str(base_dir), str(base_dir / 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    excludes=[
        'scipy', 'pandas', 'matplotlib', 'numpy', 'IPython', 'jupyter', 'torch',
        'tensorboard', 'tkinter', 'pytest', 'sphinx', 'docutils', 'black', 'tables',
        'sqlalchemy', 'botocore', 'boto3', 'lxml', 'openpyxl', 'zmq', 'tornado',
        'nbformat', 'nbconvert', 'mypy', 'astroid', 'jedi', 'parso', 'babel',
        'numba', 'llvmlite', 'pyarrow', 'fsspec', 'dask', 'cloudpickle', 'dateutil',
        'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'qtpy', 'shiboken6'
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Icon ứng dụng từ Logo NEC đã được chuyển đổi sang .ico
icon_path = str(base_dir / 'assets' / 'app_icon.ico')

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='TFT_PostMatch_Studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if os.path.exists(icon_path) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TFT_PostMatch_Studio',
)
