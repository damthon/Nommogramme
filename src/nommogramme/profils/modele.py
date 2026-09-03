"""Modèle de données d'un profilé laminé.

Toutes les grandeurs sont en unités SI (m, m², m³, m⁴, kg/m). La conversion
depuis les millimètres du catalogue SZS est faite par le chargeur.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Famille(str, Enum):
    """Familles de profilés — catalogue SZS C5, et sections reconstituées.

    La valeur `forme` associée détermine la stratégie de calcul du périmètre
    exposé au feu, qui diffère selon que les ailes sont parallèles, inclinées,
    ou qu'il s'agit d'un profil creux.

    Les deux dernières familles ne sont pas tabulées : elles désignent les
    sections soudées que l'utilisateur décrit lui-même, et dont
    ``profils.composes`` calcule les caractéristiques. Elles restent absentes
    du catalogue, ce qui les fait disparaître d'elles-mêmes des listes de
    profilés.
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
    PRS = "PRS"
    """Profilé reconstitué soudé, en H, semelles éventuellement inégales."""
    CRS = "CRS"
    """Caisson rectangulaire soudé, quatre tôles."""

    @property
    def forme(self) -> "Forme":
        if self is Famille.INP:
            return Forme.I_AILES_INCLINEES
        if self in (Famille.RRW, Famille.CRS):
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

    # --- ce qui ne se déduit pas des dimensions d'un profilé laminé -----------
    #
    # Les six champs qui suivent restent à ``None`` pour tout profilé du
    # catalogue : leurs valeurs se calculent alors depuis h, b, t_w, t_f et r.
    # Une section reconstituée soudée les renseigne, parce qu'aucune de ces
    # formules ne tient pour elle : ses semelles peuvent être inégales, elle
    # n'a pas de congé, et sa constante de gauchissement n'est pas celle d'une
    # section doublement symétrique.

    Iw: float | None = None
    """Constante de gauchissement [m⁶].

    Absente du catalogue SZS ; ``moment_critique_elastique`` l'approche alors
    par la relation des sections en I doublement symétriques.
    """
    b_couverte: float | None = None
    """Largeur masquée par la dalle en exposition sur trois faces [m].

    Vaut ``b`` pour une section symétrique. Une section en H à semelles
    inégales ne présente pas la même largeur selon la semelle que la dalle
    recouvre — c'est ce que ce champ retient.
    """
    c_sur_t_semelle: float | None = None
    """Élancement de paroi de la semelle comprimée [-], pour la classification."""
    c_sur_t_ame: float | None = None
    """Élancement de paroi de l'âme [-], pour la classification."""
    hw_impose: float | None = None
    """Hauteur d'âme entre semelles [m], quand ``h − 2·t_f`` ne la donne pas."""
    soudee: bool = False
    """Section reconstituée soudée, décrite par l'utilisateur."""

    @property
    def forme(self) -> Forme:
        return self.famille.forme

    @property
    def hw(self) -> float:
        """Hauteur d'âme entre semelles [m]."""
        if self.hw_impose is not None:
            return self.hw_impose
        return self.h - 2.0 * self.tf

    @property
    def largeur_couverte(self) -> float:
        """Largeur masquée par la dalle en exposition sur trois faces [m]."""
        return self.b_couverte if self.b_couverte is not None else self.b

    def __str__(self) -> str:
        return self.nom
