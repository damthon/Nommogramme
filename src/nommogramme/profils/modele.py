"""Modèle de données d'un profilé laminé.

Toutes les grandeurs sont en unités SI (m, m², m³, m⁴, kg/m). La conversion
depuis les millimètres du catalogue SZS est faite par le chargeur.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Famille(str, Enum):
    """Familles de profilés du catalogue SZS C5.

    La valeur `forme` associée détermine la stratégie de calcul du périmètre
    exposé au feu, qui diffère selon que les ailes sont parallèles, inclinées,
    ou qu'il s'agit d'un profil creux.
    """

    IPE = "IPE"
    PEA = "PEA"
    INP = "INP"
    HEA = "HEA"
    HEB = "HEB"
    HEM = "HEM"
    HHD = "HHD"
    HL = "HL"
    RRW = "RRW"

    @property
    def forme(self) -> "Forme":
        if self is Famille.INP:
            return Forme.I_AILES_INCLINEES
        if self is Famille.RRW:
            return Forme.PROFIL_CREUX
        return Forme.I_AILES_PARALLELES


class Forme(str, Enum):
    """Forme géométrique, au sens du calcul du périmètre exposé."""

    I_AILES_PARALLELES = "I à ailes parallèles"
    I_AILES_INCLINEES = "I à ailes inclinées"
    PROFIL_CREUX = "profil creux"


@dataclass(frozen=True, slots=True)
class Profil:
    """Un profilé laminé du catalogue, en unités SI.

    Les attributs optionnels sont ceux que le catalogue SZS ne renseigne pas
    pour toutes les familles : `Av` et `Aw` manquent pour les profils creux,
    `It` également.
    """

    nom: str
    famille: Famille

    masse: float
    """Masse linéique [kg/m]."""

    A: float
    """Aire de la section [m²]."""

    h: float
    """Hauteur totale [m]."""
    b: float
    """Largeur de semelle [m]."""
    tw: float
    """Épaisseur d'âme [m]. Pour un profil creux : épaisseur de paroi."""
    tf: float
    """Épaisseur de semelle [m]. Pour un profil creux : épaisseur de paroi."""
    r: float
    """Rayon de congé (I/H) ou rayon extérieur (profil creux) [m]."""

    Iy: float
    """Moment d'inertie fort [m⁴]."""
    Iz: float
    """Moment d'inertie faible [m⁴]."""
    Wely: float
    Wply: float
    Welz: float
    Wplz: float
    """Modules de flexion [m³]."""

    iy: float
    iz: float
    """Rayons de giration [m]."""

    Um: float
    """Surface développée tabulée par le SZS [m²/m].

    Correspond au périmètre du contour réel du profilé, congés compris. Sert
    de source primaire pour le périmètre exposé « contour » et de contrôle
    croisé pour la formule géométrique.
    """

    iz_tabule: float | None = None
    """Rayon de giration faible tel que tabulé par le SZS [m].

    Renseigné uniquement lorsque la valeur retenue dans ``iz`` a dû être
    recalculée : voir ``chargeur._corriger_rayon_giration_profils_creux``.
    """

    Iz_tabule: float | None = None
    """Moment d'inertie faible tel que tabulé par le SZS [m⁴].

    Renseigné uniquement lorsque la valeur retenue dans ``Iz`` a dû être
    corrigée : voir ``chargeur._corriger_inertie_faible``.
    """

    It: float | None = None
    """Moment d'inertie de torsion uniforme [m⁴]."""
    Av: float | None = None
    """Aire de cisaillement [m²]."""
    Aw: float | None = None
    """Aire d'âme [m²]."""

    @property
    def forme(self) -> Forme:
        return self.famille.forme

    @property
    def hw(self) -> float:
        """Hauteur d'âme entre semelles [m]."""
        return self.h - 2.0 * self.tf

    def __str__(self) -> str:
        return self.nom
