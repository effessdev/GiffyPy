# -*- mode: python ; coding: utf-8 -*-

import shutil

# Bundle ffmpeg/ffprobe from the build machine so the dist runs with no system
# install. They go in datas (not binaries) so PyInstaller never UPX-compresses
# them; constants.py prefers the bundled copy over PATH at runtime.
ffmpeg_files = []
for _name in ("ffmpeg", "ffprobe"):
    _src = shutil.which(_name)
    if _src:
        ffmpeg_files.append((_src, "."))
    else:
        print(f"WARNING: {_name}.exe not found on PATH at build time — "
              f"the dist will require the user to have it installed.")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('icon.ico', '.')] + ffmpeg_files,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GiffyPy',
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
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GiffyPy',
)
