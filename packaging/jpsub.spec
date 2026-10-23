# PyInstaller recipe for the single-file jpsub binary. Build with ./build.sh.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent

datas = [
    (str(root / "jpsub" / "web"), "jpsub/web"),
    # Run by the system Python, so it ships as a plain file, not compiled in.
    (str(root / "jpsub" / "overlay.py"), "jpsub"),
]
binaries = []
hiddenimports = []
# Native libraries, the Sudachi dictionary and the CA certificates.
for package in ("sherpa_onnx", "sudachipy", "sudachidict_core", "certifi"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports

a = Analysis(
    [str(root / "packaging" / "jpsub_main.py")],
    pathex=[str(root)],
    datas=datas,
    binaries=binaries,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "faster_whisper", "ctranslate2", "av", "onnxruntime"],
)
# Use the system's C++ runtime: the build machine's copy would raise the
# minimum glibc to whatever the build distribution ships.
a.binaries = [b for b in a.binaries if not b[0].startswith(("libstdc++.so", "libgcc_s.so"))]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="jpsub",
    console=True,
    strip=False,
    upx=False,
)
