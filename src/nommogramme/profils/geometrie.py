"""Périmètres exposés, facteurs de massiveté et facteur d'ombre.

Référence : EN 1993-1-2 §4.2.5, tableaux 4.2 (sections ouvertes) et 4.3
(profils creux), équations (4.26a) et (4.26b) pour le facteur d'ombre.

Deux sources sont disponibles pour le périmètre du contour :

* la colonne ``Um`` du catalogue SZS, qui est la surface développée réelle du
  profilé, congés compris — c'est la source primaire ;
* une formule géométrique, utilisée en repli lorsque ``Um`` est absent et,
  surtout, comme contrôle croisé systématique à la lecture du catalogue.

Les deux concordent à 0,55 % en moyenne sur les 169 profilés I/H du catalogue.
"""

from __future__ import annotations

import math
from enum import Enum

from .modele import Forme, Profil

__all__ = [
    "Exposition",
    "perimetre_expose",
    "perimetre_caisson",
    "perimetre_contour_geometrique",
    "facteur_massivete",
    "facteur_massivete_caisson",
    "facteur_ombre",
    "ecart_relatif_um",
    "AM_SUR_V_MINIMAL",
]


# Excès de longueur d'un angle vif par rapport au quart de cercle qui le
# remplace réellement : 2r (deux segments droits) − πr/2 (l'arc).
_EXCES_ANGLE_VIF = 8.0 - 2.0 * math.pi  # ≈ 1,7168, à multiplier par le rayon

_PENTE_AILE_INP = 0.14
"""Pente des faces intérieures d'aile des profilés INP (DIN 1025-1)."""

_RATIO_CONGE_INP = 2.0
"""Rapport r1/r2 retenu pour les INP.

La colonne ``r`` du catalogue SZS donne, pour les INP, le rayon de bout d'aile
r2 et non le congé de raccordement r1. Le rapport r1 = 2·r2 a été calibré sur
les vingt profilés INP du catalogue : il ramène l'écart moyen à ``Um`` de
2,3 % à 0,32 %, sans biais résiduel. Cette valeur n'intervient que dans la
formule de repli, ``Um`` restant la source primaire.
"""

AM_SUR_V_MINIMAL = 10.0
"""Borne inférieure de validité de la méthode simplifiée [m⁻¹].

EN 1993-1-2 §4.2.5.1(1). Le catalogue SZS la respecte, mais de justesse dans
le cas le plus défavorable (11,5 m⁻¹ pour un HHD 400.1086 encaissé sur trois
faces).
"""


class Exposition(str, Enum):
    """Configuration d'exposition au feu.

    « Contour » désigne une protection ou une exposition qui suit la forme du
    profilé (profilé nu, flocage, peinture). « Caisson » désigne un
    encaissement rectangulaire (plaques, panneaux).

    Trois faces correspond à une poutre dont la semelle supérieure est
    couverte par une dalle.
    """

    CONTOUR_4_FACES = "contour, 4 faces"
    CONTOUR_3_FACES = "contour, 3 faces"
    CAISSON_4_FACES = "caisson, 4 faces"
    CAISSON_3_FACES = "caisson, 3 faces"

    @property
    def est_caisson(self) -> bool:
        return self in (Exposition.CAISSON_4_FACES, Exposition.CAISSON_3_FACES)

    @property
    def trois_faces(self) -> bool:
        return self in (Exposition.CONTOUR_3_FACES, Exposition.CAISSON_3_FACES)


def perimetre_contour_geometrique(profil: Profil) -> float:
    """Périmètre du contour réel, calculé depuis les dimensions [m].

    Sert de repli et de contrôle croisé de la colonne ``Um``.

    Pour une section en I à ailes parallèles, le développement du contour fait
    disparaître les termes en ``tf`` :

        P = 2h + 4b − 2tw − (8 − 2π)·r

    Le dernier terme retranche l'excès des quatre angles vifs par rapport aux
    quatre congés réels.
    """
    h, b, tw, tf, r = profil.h, profil.b, profil.tw, profil.tf, profil.r

    if profil.forme is Forme.PROFIL_CREUX:
        # Le rayon extérieur d'un profil creux formé à chaud vaut environ deux
        # fois l'épaisseur de paroi (EN 10210).
        return 2.0 * (h + b) - _EXCES_ANGLE_VIF * r

    if profil.forme is Forme.I_AILES_INCLINEES:
        # Faces intérieures d'aile inclinées : leur longueur développée est
        # allongée du facteur √(1 + p²), et l'épaisseur au bout d'aile est
        # réduite de la pente sur la distance b/4 depuis le point de mesure.
        p = _PENTE_AILE_INP
        epaisseur_bout = tf - p * (b / 4.0)
        face_interieure = (b - tw) * math.sqrt(1.0 + p * p)
        par_semelle = b + 2.0 * epaisseur_bout + face_interieure
        r2 = r
        r1 = _RATIO_CONGE_INP * r2
        return (
            2.0 * par_semelle
            + 2.0 * (h - 2.0 * tf)
            - _EXCES_ANGLE_VIF * (r1 + r2)
        )

    # I et H à ailes parallèles.
    return 2.0 * h + 4.0 * b - 2.0 * tw - _EXCES_ANGLE_VIF * r


def _perimetre_contour(profil: Profil) -> float:
    """Périmètre du contour, en préférant la valeur tabulée [m]."""
    if profil.Um is not None and profil.Um > 0.0:
        return profil.Um
    return perimetre_contour_geometrique(profil)


def perimetre_caisson(profil: Profil, trois_faces: bool = False) -> float:
    """Périmètre de l'encaissement rectangulaire [m].

    EN 1993-1-2 tableau 4.2 : le caisson est le rectangle circonscrit, à
    angles vifs. Pour un profil creux, il n'y a pas d'encaissement distinct
    du profilé lui-même : la valeur caisson est confondue avec le contour.
    """
    if profil.forme is Forme.PROFIL_CREUX:
        p = _perimetre_contour(profil)
        return p - profil.b if trois_faces else p

    if trois_faces:
        return 2.0 * profil.h + profil.b
    return 2.0 * (profil.h + profil.b)


def perimetre_expose(profil: Profil, exposition: Exposition) -> float:
    """Périmètre exposé au feu [m] pour la configuration donnée.

    En exposition sur trois faces, la face supérieure de la semelle haute est
    couverte par la dalle : le périmètre du contour est diminué de ``b``.
    """
    if exposition.est_caisson:
        return perimetre_caisson(profil, trois_faces=exposition.trois_faces)

    contour = _perimetre_contour(profil)
    return contour - profil.b if exposition.trois_faces else contour


def facteur_massivete(profil: Profil, exposition: Exposition) -> float:
    """Facteur de massiveté A_m/V [m⁻¹].

    EN 1993-1-2 §4.2.5.1. Rapport de la surface exposée par unité de longueur
    au volume d'acier par unité de longueur.
    """
    return perimetre_expose(profil, exposition) / profil.A


def facteur_massivete_caisson(profil: Profil, exposition: Exposition) -> float:
    """Valeur caisson [A_m/V]_b du facteur de massiveté [m⁻¹].

    Utilisée au numérateur du facteur d'ombre, pour la même configuration
    d'exposition (trois ou quatre faces) que la valeur de référence.
    """
    return perimetre_caisson(profil, trois_faces=exposition.trois_faces) / profil.A


def facteur_ombre(
    profil: Profil,
    exposition: Exposition,
    feu_nominal: bool = True,
) -> float:
    """Facteur d'ombre k_sh [-].

    EN 1993-1-2 équations (4.26a) et (4.26b).

    Les parties concaves d'une section ouverte se font mutuellement écran et
    reçoivent moins de rayonnement net que ne le suppose le périmètre du
    contour. Le coefficient 0,9 de l'équation (4.26a) est réservé aux sections
    en I sous action de feu nominale ; tous les autres cas relèvent de
    l'équation (4.26b).

    Un profil creux n'ayant aucune partie concave, son facteur d'ombre vaut 1.
    Le facteur d'ombre ne s'applique qu'à l'acier non protégé.
    """
    if profil.forme is Forme.PROFIL_CREUX:
        return 1.0

    rapport = facteur_massivete_caisson(profil, exposition) / facteur_massivete(
        profil, exposition
    )
    ksh = 0.9 * rapport if feu_nominal else rapport
    return min(ksh, 1.0)


def ecart_relatif_um(profil: Profil) -> float | None:
    """Écart relatif entre périmètre calculé et ``Um`` tabulé [-].

    Renvoie ``None`` si le profilé n'a pas de valeur tabulée. Un écart
    supérieur à quelques pour-cent signale une incohérence de données ou une
    famille dont la formule de contour n'est pas adaptée.
    """
    if profil.Um is None or profil.Um <= 0.0:
        return None
    return (perimetre_contour_geometrique(profil) - profil.Um) / profil.Um
