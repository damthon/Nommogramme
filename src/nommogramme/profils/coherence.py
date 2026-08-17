"""Audit de cohérence du catalogue.

Les grandeurs tabulées par le SZS sont liées entre elles : i = √(I/A),
W_el,y = I_y/(h/2), m = ρ·A. Les confronter les unes aux autres détecte une
erreur de saisie, de recopie ou de conversion sans qu'aucune source externe
soit nécessaire.

C'est ainsi qu'a été trouvée l'anomalie des tubes RRW décrite dans
``chargeur._corriger_rayon_giration_profils_creux``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .geometrie import ecart_relatif_um
from .modele import Forme, Profil

__all__ = ["Gravite", "Anomalie", "auditer", "auditer_catalogue"]


_SEUIL_ARRONDI = 0.01
"""Au-delà, un écart ne s'explique plus par l'arrondi de tabulation [-]."""

_SEUIL_GRAVE = 0.05
"""Au-delà, l'écart traduit une erreur de donnée et non une imprécision [-]."""


class Gravite(str, Enum):
    AVERTISSEMENT = "avertissement"
    ERREUR = "erreur"


@dataclass(frozen=True, slots=True)
class Anomalie:
    profil: str
    grandeur: str
    tabule: float
    attendu: float
    ecart: float
    """Écart relatif [-]."""
    gravite: Gravite
    commentaire: str = ""

    def __str__(self) -> str:
        return (
            f"{self.profil} — {self.grandeur} : tabulé {self.tabule:.4g}, "
            f"attendu {self.attendu:.4g} ({self.ecart:+.1%})"
            + (f" · {self.commentaire}" if self.commentaire else "")
        )


def _comparer(
    profil: Profil,
    grandeur: str,
    tabule: float,
    attendu: float,
    seuil: float = _SEUIL_ARRONDI,
    commentaire: str = "",
) -> Anomalie | None:
    if tabule == 0.0:
        return None
    ecart = (tabule - attendu) / tabule
    if abs(ecart) <= seuil:
        return None
    return Anomalie(
        profil=profil.nom,
        grandeur=grandeur,
        tabule=tabule,
        attendu=attendu,
        ecart=ecart,
        gravite=Gravite.ERREUR if abs(ecart) > _SEUIL_GRAVE else Gravite.AVERTISSEMENT,
        commentaire=commentaire,
    )


def auditer(profil: Profil) -> list[Anomalie]:
    """Contrôles de redondance interne sur un profilé."""
    anomalies: list[Anomalie] = []

    for axe, rayon, inertie in (
        ("i_y", profil.iy, profil.Iy),
        ("i_z", profil.iz, profil.Iz),
    ):
        anomalie = _comparer(
            profil, axe, rayon, math.sqrt(inertie / profil.A),
            commentaire="i doit valoir √(I/A)",
        )
        if anomalie is not None:
            anomalies.append(anomalie)

    anomalie = _comparer(
        profil, "m", profil.masse, 7850.0 * profil.A, seuil=0.02,
        commentaire="m doit valoir ρ·A",
    )
    if anomalie is not None:
        anomalies.append(anomalie)

    anomalie = _comparer(
        profil, "W_el,y", profil.Wely, profil.Iy / (profil.h / 2.0), seuil=0.02,
        commentaire="W_el,y doit valoir I_y/(h/2)",
    )
    if anomalie is not None:
        anomalies.append(anomalie)

    for axe, plastique, elastique in (
        ("W_pl,y/W_el,y", profil.Wply, profil.Wely),
        ("W_pl,z/W_el,z", profil.Wplz, profil.Welz),
    ):
        facteur = plastique / elastique
        if not 1.0 <= facteur < 1.75:
            anomalies.append(
                Anomalie(
                    profil=profil.nom, grandeur=axe, tabule=facteur, attendu=1.15,
                    ecart=facteur - 1.15, gravite=Gravite.ERREUR,
                    commentaire="facteur de forme hors du domaine plausible",
                )
            )

    if profil.forme is not Forme.PROFIL_CREUX and profil.Iy < profil.Iz:
        anomalies.append(
            Anomalie(
                profil=profil.nom, grandeur="I_y vs I_z", tabule=profil.Iy,
                attendu=profil.Iz, ecart=0.0, gravite=Gravite.ERREUR,
                commentaire="l'axe fort doit porter la plus grande inertie",
            )
        )

    ecart_um = ecart_relatif_um(profil)
    if ecart_um is not None and abs(ecart_um) > 0.04:
        anomalies.append(
            Anomalie(
                profil=profil.nom, grandeur="U_m", tabule=profil.Um,
                attendu=profil.Um * (1.0 + ecart_um), ecart=-ecart_um,
                gravite=Gravite.AVERTISSEMENT,
                commentaire="périmètre calculé éloigné de la surface développée",
            )
        )

    return anomalies


def auditer_catalogue(profils) -> list[Anomalie]:
    """Audite un catalogue entier, anomalies les plus graves en tête."""
    toutes: list[Anomalie] = []
    for profil in profils:
        toutes.extend(auditer(profil))
    toutes.sort(key=lambda a: (a.gravite is not Gravite.ERREUR, -abs(a.ecart)))
    return toutes
