"""Interface graphique Streamlit.

Le module ``app`` importe ``streamlit`` au chargement ; il n'est donc pas
importé ici, pour que ``import nommogramme`` reste possible sans l'extra
``[ui]``. Utilisez ``chemin_application()`` pour localiser le fichier à passer
à ``streamlit run``.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["chemin_application", "lancer"]


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
