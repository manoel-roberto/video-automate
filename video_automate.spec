# -*- mode: python ; coding: utf-8 -*-
"""
video_automate.spec
===================
Arquivo de especificação PyInstaller multiplataforma (Linux e Windows)
para compilar a versão Desktop do Gerador de Vídeos Tutoriais com IA.
"""

import sys
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

block_cipher = None

# Coleta de arquivos de dados essenciais
datas = []
datas += collect_data_files('imageio_ffmpeg')
datas += collect_data_files('certifi')

# Coleta de metadados para evitar PackageNotFoundError em bibliotecas modernas
for pkg in ['imageio', 'moviepy', 'edge_tts', 'proglog', 'numpy', 'pillow', 'certifi', 'tqdm']:
    try:
        datas += copy_metadata(pkg)
    except Exception:
        pass


# Inclui arquivos de exemplo se existirem
if os.path.exists('config_exemplo.json'):
    datas.append(('config_exemplo.json', '.'))

# Submódulos ocultos para garantir empacotamento completo de bibliotecas dinâmicas
hiddenimports = [
    'edge_tts',
    'moviepy',
    'moviepy.audio',
    'moviepy.video',
    'moviepy.video.fx',
    'moviepy.audio.fx',
    'imageio',
    'imageio_ffmpeg',
    'proglog',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'numpy',
    'aiohttp',
    'certifi',
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'shiboken6',
]
hiddenimports += collect_submodules('edge_tts')
hiddenimports += collect_submodules('moviepy')

a = Analysis(
    ['desktop_app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['streamlit', 'tornado', 'altair', 'pydeck'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='VideoAutomate',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Sem console/cmd (aplicação puramente GUI)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
