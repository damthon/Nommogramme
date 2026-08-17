"""Catalogue de profilés et géométrie d'exposition au feu."""

from .chargeur import Catalogue, charger_csv, ecrire_csv, lire_xlsx
from .coherence import Anomalie, Gravite, auditer, auditer_catalogue
from .geometrie import (
    AM_SUR_V_MINIMAL,
    Exposition,
    ecart_relatif_um,
    facteur_massivete,
    facteur_massivete_caisson,
    facteur_ombre,
    perimetre_caisson,
    perimetre_contour_geometrique,
    perimetre_expose,
)
from .modele import Famille, Forme, Profil

__all__ = [
    "AM_SUR_V_MINIMAL",
    "Anomalie",
    "Catalogue",
    "Exposition",
    "Famille",
    "Forme",
    "Gravite",
    "Profil",
    "auditer",
    "auditer_catalogue",
    "charger_csv",
    "ecart_relatif_um",
    "ecrire_csv",
    "facteur_massivete",
    "facteur_massivete_caisson",
    "facteur_ombre",
    "lire_xlsx",
    "perimetre_caisson",
    "perimetre_contour_geometrique",
    "perimetre_expose",
]
