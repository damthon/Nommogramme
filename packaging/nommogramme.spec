# -*- mode: python ; coding: utf-8 -*-
"""Recette PyInstaller de l'exécutable de bureau.

    pyinstaller packaging/nommogramme.spec

Elle produit un fichier unique, sans console, d'environ 45 Mo. À compiler sur
la plateforme visée : PyInstaller ne sait pas produire un .exe depuis Linux.
L'intégration continue s'en charge — voir .github/workflows/executable.yml.

Ce qui est écarté, et pourquoi
------------------------------

``streamlit`` et sa chaîne — pandas, pyarrow, altair, uvicorn — ne servent
qu'à l'autre interface. pyarrow pèse à lui seul 161 Mo et pandas 72. Les
exclure fait passer l'exécutable de ~250 Mo à ~45. Ils sont listés
explicitement plutôt que laissés à l'analyse automatique : matplotlib sait
utiliser pandas s'il le trouve, et l'embarquerait donc silencieusement.

Les backends Qt et GTK de matplotlib sont écartés pour la même raison — seul
TkAgg est utilisé, et il est déclaré en import caché parce que
``bureau.dessiner_figures`` ne l'importe qu'au moment de tracer.
"""

from pathlib import Path

_RACINE = Path(SPECPATH).parent

_INUTILES = [
    "streamlit", "pandas", "pyarrow", "altair", "uvicorn", "starlette",
    "protobuf", "pydeck", "watchdog", "tornado", "IPython", "jedi",
    "PyQt5", "PyQt6", "PySide2", "PySide6", "wx", "gi",
    "matplotlib.backends.backend_qtagg",
    "matplotlib.backends.backend_gtk3agg",
    "matplotlib.backends.backend_webagg",
    "pytest", "setuptools", "pip",
]

analyse = Analysis(
    ["lanceur.py"],
    pathex=["../src"],
    binaries=[],
    # Le catalogue de profilés et la base de produits de protection sont des
    # fichiers de données du paquet : sans eux l'exécutable démarre et échoue
    # au premier calcul. Le chemin est donné en dur plutôt que déduit par
    # ``collect_data_files`` : celui-ci passe par le système d'import et place
    # les fichiers ailleurs quand le paquet est vu depuis ``pathex`` sans être
    # installé. La panne est silencieuse à la compilation et ne se voit qu'au
    # lancement — d'où aussi le « --autotest » du lanceur.
    datas=[(str(_RACINE / "src" / "nommogramme" / "data"), "nommogramme/data")],
    # Imports que l'analyse statique ne voit pas, parce qu'ils sont différés
    # ou résolus par nom au moment de l'exécution.
    #
    # « PIL._tkinter_finder » est le cas d'école : Pillow le charge
    # dynamiquement quand ImageTk a besoin de parler à Tcl/Tk. Absent du
    # paquet, tout marche jusqu'à la première figure, puis la fenêtre reste
    # vide sans message. C'est ce que le mode « --autotest » vérifie.
    hiddenimports=[
        "matplotlib.backends.backend_agg",
        "matplotlib.backends.backend_tkagg",
        "PIL.ImageTk",
        "PIL._tkinter_finder",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_INUTILES,
    noarchive=False,
)

pyz = PYZ(analyse.pure)

exe = EXE(
    pyz,
    analyse.scripts,
    analyse.binaries,
    analyse.datas,
    [],
    name="Nommogramme",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # Pas de fenêtre de console derrière l'application : sous Windows, une
    # console noire qui s'ouvre en même temps que l'interface fait douter de
    # ce qu'on vient de lancer.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
