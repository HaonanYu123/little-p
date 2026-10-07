# -*- mode: python ; coding: utf-8 -*-

datas = [
    ('VERSION', '.'),
    ('distribution.json', '.'),
    ('assets', 'assets'),
    ('desktop', 'desktop'),
    ('engine', 'engine'),
    ('site/robot.js', 'site'),
]

a = Analysis(
    ['littlep_app.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['PyQt5.QtWebEngineWidgets', 'PyQt5.QtWebChannel'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='LittleP',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='LittleP',
)
