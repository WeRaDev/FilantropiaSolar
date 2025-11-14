# -*- mode: python ; coding: utf-8 -*-
"""
FilantropiaSolar v1.2.2 - PyInstaller Specification
Creates standalone Windows executable with all dependencies bundled.

Build with: pyinstaller --clean --noconfirm filantropia_solar.spec

Note: data/ and weather_files/ are bundled but NSIS installer can also
install them separately to Program Files for easier updates.
"""

block_cipher = None

import os
import sys
from pathlib import Path

# Signal to application code that this is a frozen build
os.environ['PYINSTALLER_BUILD'] = '1'

from PyInstaller.utils.hooks import collect_submodules

# Get base directory
base_dir = Path.cwd()

# Hidden imports - comprehensive coverage
hidden = []
# Scikit-learn core modules
hidden += [
    'sklearn.utils._cython_blas',
    'sklearn.neighbors.typedefs',
    'sklearn.neighbors.quad_tree',
    'sklearn.tree._utils',
    'sklearn.utils._weight_vector',
    'sklearn.ensemble._hist_gradient_boosting',
    'sklearn.metrics._pairwise_distances_reduction',
    'sklearn.utils._heap',
    'sklearn.utils._sorting',
    'sklearn.utils._vector_sentinel',
]
# Ensure SciPy core is bundled (required by scikit-learn)
hidden += [
    'scipy',
]
# Pandas and NumPy internals
hidden += [
    'pandas._libs.tslibs.timedeltas',
    'pandas._libs.tslibs.nattype',
    'pandas._libs.tslibs.np_datetime',
    'pandas._libs.tslibs.offsets',
    'pandas._libs.join',
    'numpy.random._pickle',
    'numpy.random.bit_generator',
]
# Matplotlib and Tkinter
hidden += [
    'matplotlib.backends.backend_tkagg',
    'matplotlib.figure',
    'matplotlib.pyplot',
    'tkinter',
    'tkinter.ttk',
    'tkinter.messagebox',
    'tkinter.filedialog',
]
# Application modules
hidden += [
    'filantropia_solar.utils',
    'filantropia_solar.utils.paths',
    'utils.paths',
    'openpyxl',
    'openpyxl.cell._writer',
    'openpyxl.worksheet._writer',
    'pathlib',
    'sqlite3',
    'pickle',
    'joblib',
    'datetime',
    'logging',
    'queue',
    'threading',
]


# Files to exclude from bundle (reduce size)
excludes = [
    'pytest', 'sphinx', 'setuptools', 'wheel', 'pip',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_gtk3agg',
    'matplotlib.backends.backend_webagg',
    'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
    'sympy', 'IPython', 'jupyter',
    'tests', 'test', '.github',
]

# Data files to bundle (optional - NSIS can install separately)
# Note: average_values.csv is used for Lisbon 4-year baseline overlay in charts
# and must live at the resource base so get_resource_path('average_values.csv') works.
datas = [
    ('data', 'data'),
    ('weather_files', 'weather_files'),
    ('average_values.csv', '.'),
]

a = Analysis(
    ['main.py'],
    pathex=[os.path.abspath('src')],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Optional icon path
icon_path = base_dir / 'windows_installer' / 'resources' / 'icon.ico'
icon_str = str(icon_path) if icon_path.exists() else None

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FilantropiaSolar',
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
    icon=icon_str,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FilantropiaSolar')