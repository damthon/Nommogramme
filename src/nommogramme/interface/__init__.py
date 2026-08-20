"""Les deux interfaces graphiques.

* ``bureau`` — Tkinter, celle qui est distribuée sous forme d'exécutable ;
* ``app`` — Streamlit, dans le navigateur.

Elles partagent ``saisie.py``, qui porte le jeu de paramètres et sa traduction
en appel de bibliothèque. Aucune des deux ne calcule quoi que ce soit.

Ni ``app`` ni ``bureau`` ne sont importés ici : le premier demande
``streamlit``, le second ``tkinter`` et ``matplotlib``. Les importer au
chargement rendrait ``import nommogramme`` impossible sans les extras.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["chemin_application", "lancer", "lancer_bureau"]


def chemin_application() -> Path:
    """Chemin du script Streamlit, à passer à ``streamlit run``."""
    return Path(__file__).resolve().parent / "app.py"


def lancer(arguments: list[str] | None = None) -> int:
    """Démarre le serveur Streamlit sur l'application.

    Équivaut à ``streamlit run <chemin_application()>``. Les arguments
    supplémentaires sont transmis tels quels à Streamlit.
    """
    try:
        from streamlit.web import cli
    except ImportError as erreur:  # pragma: no cover - dépend de l'installation
        raise ImportError(
            "L'interface graphique demande streamlit : "
            "pip install 'nommogramme[ui]'"
        ) from erreur

    import sys

    sys.argv = ["streamlit", "run", str(chemin_application()), *(arguments or [])]
    return cli.main()  # type: ignore[no-any-return]


def lancer_bureau() -> int:
    """Ouvre l'interface de bureau, et rend la main à sa fermeture.

    C'est le point d'entrée de l'exécutable distribué.
    """
    try:
        from .bureau import lancer as ouvrir
    except ImportError as erreur:  # pragma: no cover - dépend de l'installation
        raise ImportError(
            "L'interface de bureau demande tkinter et matplotlib : "
            "pip install 'nommogramme[bureau]'. Sous Linux, tkinter est un "
            "paquet système séparé (python3-tk)."
        ) from erreur

    ouvrir()
    return 0
