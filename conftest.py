"""Réglages de collecte communs à toute la suite.

``pytest`` explore aussi ``src/`` — voir ``testpaths`` et ``--doctest-modules``
dans ``pyproject.toml`` — ce qui suppose de pouvoir *importer* chaque module.
Deux d'entre eux ne s'importent pas partout, et sans cette exclusion c'est la
collecte entière qui s'interrompt, pas seulement le module concerné.

* ``interface/bureau.py`` demande ``tkinter``. Il est dans la bibliothèque
  standard sous Windows et macOS, mais les distributions Linux le livrent
  dans un paquet système séparé (``python3-tk``) que ``pip`` ne peut pas
  installer.
* ``interface/app.py`` demande ``streamlit``, qui est un extra.

Les deux restent testés par ``tests/test_bureau.py`` et
``tests/test_interface.py``, qui savent s'écarter proprement.
"""

from __future__ import annotations

import importlib.util

collect_ignore = []


def _absent(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is None
    except (ImportError, ValueError):  # pragma: no cover - dépend de l'environnement
        return True


if _absent("tkinter"):
    collect_ignore.append("src/nommogramme/interface/bureau.py")

if _absent("streamlit"):  # pragma: no cover - dépend de l'installation
    collect_ignore.append("src/nommogramme/interface/app.py")
