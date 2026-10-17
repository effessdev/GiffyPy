# -*- mode: python ; coding: utf-8 -*-

import shutil

# Fail fast: the app bundles ffmpeg/ffprobe at build time so the dist runs
# without a user-installed system copy. If they are missing, building would
# otherwise create a broken app that can only crash at runtime.
ffmpeg_files = []
missing = []
for _name in ("ffmpeg", "ffprobe"):
    _src = shutil.which(_name)
    if _src:
        ffmpeg_files.append((_src, "."))
    else:
        missing.append(_name)

if missing:
    raise RuntimeError(
        "Missing required build-time binaries: "
        + ", ".join(missing)
        + ". Install ffmpeg/ffprobe or add them to PATH before building."
    )

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
