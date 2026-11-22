"""Build using: uv run --with pyinstaller pyinstaller --clean --noconfirm pokemon-card-merger.spec"""

# PyInstaller supplies Analysis, PYZ, and EXE when executing this spec.
# ruff: noqa: F821

from pathlib import Path
from runpy import run_path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

deduplicate_dlls = run_path(str(Path(SPECPATH) / "build_support.py"))["deduplicate_dlls"]

datas = [
    ("assets/app-icon.ico", "assets"),
    ("findCard.pt", "."),
]
datas += collect_data_files("ultralytics")
datas += collect_data_files("tcg_card_recognizer", includes=["*.db"])
datas += copy_metadata("ultralytics")

a = Analysis(
    ["windows_entry.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["recognize_image", "tcg_card_recognizer", "scipy.fft"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Inference never calls dataframe export, plotting, or training geometry.
    excludes=[
        "easyocr", "PyQt5", "PyQt6", "PySide2", "tkinter", "pytest",
        "polars", "_polars_runtime_32", "pandas", "matplotlib", "shapely",
        "tensorboard", "IPython", "notebook",
    ],
    noarchive=False,
)
a.binaries = deduplicate_dlls(a.binaries)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PokemonCardMerger",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/app-icon.ico",
)
