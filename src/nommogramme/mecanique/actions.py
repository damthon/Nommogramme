"""Actions en situation d'incendie.

Référence : EN 1991-1-2 §4.3.1 pour la combinaison accidentelle,
EN 1993-1-2 §2.4.2 pour le niveau de charge η_fi.

L'incendie est une situation de projet accidentelle : les charges y sont
nettement plus faibles qu'à l'ELU fondamental, ce qui constitue le premier
levier de la vérification.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contexte import SUISSE_SIA, ContexteNormatif

__all__ = [
    "CasDeCharge",
    "beta_M_lineaire",
    "BETA_M_CHARGE_REPARTIE",
    "BETA_M_CHARGE_CONCENTREE",
    "combinaison_accidentelle",
    "eta_fi",
]


BETA_M_CHARGE_REPARTIE = 1.3
"""Facteur de moment uniforme équivalent, moment de charge répartie [-].

EN 1993-1-2 figure 4.2.
"""

BETA_M_CHARGE_CONCENTREE = 1.4
"""Facteur de moment uniforme équivalent, moment de charge concentrée [-]."""


def beta_M_lineaire(psi: float) -> float:
    """Facteur de moment uniforme équivalent d'un diagramme linéaire [-].

    EN 1993-1-2 figure 4.2 : β_M,ψ = 1,8 − 0,7·ψ, où ``psi`` est le rapport du
    moment de la plus petite extrémité à celui de la plus grande, compris
    entre −1 (double courbure symétrique) et +1 (moment constant).
    """
    if not -1.0 <= psi <= 1.0:
        raise ValueError(f"ψ doit être compris entre −1 et +1, reçu {psi}")
    return 1.8 - 0.7 * psi


@dataclass(frozen=True, slots=True)
class CasDeCharge:
    """Sollicitations et conditions d'appui en situation d'incendie.

    Convention de signe : ``N_fi_Ed`` est **positif en compression**, négatif
    en traction, conformément à l'usage des vérifications de flambement.

    Les longueurs de flambement sont celles de la situation d'incendie, pas
    celles de l'ELU : un poteau continu d'un contreventement est bridé par les
    étages froids adjacents, ce qui autorise l_fi = 0,5·L en étage courant et
    0,7·L au dernier étage (EN 1993-1-2 §4.2.3.2(4)).
    """

    N_fi_Ed: float = 0.0
    """Effort normal [N], positif en compression."""
    My_fi_Ed: float = 0.0
    """Moment de flexion autour de l'axe fort [N·m], en valeur absolue."""
    Mz_fi_Ed: float = 0.0
    """Moment de flexion autour de l'axe faible [N·m], en valeur absolue."""
    V_fi_Ed: float = 0.0
    """Effort tranchant [N], en valeur absolue."""

    L: float = 0.0
    """Longueur d'épure de l'élément [m]."""
    l_fi_y: float | None = None
    """Longueur de flambement en situation d'incendie, plan fort [m]."""
    l_fi_z: float | None = None
    """Longueur de flambement en situation d'incendie, plan faible [m]."""
    L_LT: float | None = None
    """Longueur entre maintiens latéraux, pour le déversement [m]."""

    beta_M_y: float = 1.3
    beta_M_z: float = 1.3
    beta_M_LT: float = 1.3
    """Facteurs de moment uniforme équivalent [-]. EN 1993-1-2 figure 4.2."""

    maintien_lateral: bool = False
    """La semelle comprimée est-elle maintenue latéralement sur sa longueur ?

    Le critère de déversement de l'éq. (4.21b) ne s'applique qu'aux éléments
    « pour lesquels le déversement est un mode de ruine potentiel »
    (EN 1993-1-2 §4.2.3.5). Une poutre dont la semelle comprimée est bloquée
    par une dalle solidaire en est dispensée : seule l'éq. (4.21a) est alors
    vérifiée, ce qui permet aux facteurs d'adaptation κ₁ et κ₂ de jouer.
    """

    def __post_init__(self) -> None:
        if self.L < 0.0:
            raise ValueError(f"Longueur négative : {self.L} m")
        for nom in ("My_fi_Ed", "Mz_fi_Ed", "V_fi_Ed"):
            if getattr(self, nom) < 0.0:
                raise ValueError(
                    f"{nom} doit être donné en valeur absolue, reçu "
                    f"{getattr(self, nom)}"
                )

    @property
    def comprime(self) -> bool:
        return self.N_fi_Ed > 0.0

    @property
    def tendu(self) -> bool:
        return self.N_fi_Ed < 0.0

    @property
    def flechi(self) -> bool:
        return self.My_fi_Ed > 0.0 or self.Mz_fi_Ed > 0.0

    def longueur_flambement_y(self) -> float:
        """Longueur de flambement retenue dans le plan fort [m]."""
        return self.l_fi_y if self.l_fi_y is not None else self.L

    def longueur_flambement_z(self) -> float:
        """Longueur de flambement retenue dans le plan faible [m]."""
        return self.l_fi_z if self.l_fi_z is not None else self.L

    def longueur_deversement(self) -> float:
        """Longueur retenue pour le déversement [m].

        À défaut de maintiens latéraux déclarés, on retient la longueur de
        flambement dans le plan faible.
        """
        if self.L_LT is not None:
            return self.L_LT
        return self.longueur_flambement_z()


def combinaison_accidentelle(
    G_k: float,
    Q_k_dominante: float = 0.0,
    psi_dominante: float = 0.5,
    autres: tuple[tuple[float, float], ...] = (),
    A_d: float = 0.0,
) -> float:
    """Effet des actions en situation d'incendie.

    EN 1991-1-2 §4.3.1 :

        E_fi,d = Σ G_k,j + P + A_d + ψ_1,1·Q_k,1 + Σ ψ_2,i·Q_k,i

    ``autres`` est une suite de couples ``(Q_k,i, ψ_2,i)``. ``A_d`` est nulle
    dans une analyse par élément isolé où les effets indirects du feu sont
    négligés, ce qui est l'hypothèse retenue par cet outil.

    Le choix ψ₁ ou ψ₂ pour l'action dominante appartient à l'annexe nationale
    et se traduit ici par la valeur passée en ``psi_dominante`` ; voir
    ``ContexteNormatif.psi_action_dominante``.
    """
    return (
        G_k
        + A_d
        + psi_dominante * Q_k_dominante
        + sum(psi * Q for Q, psi in autres)
    )


def eta_fi(
    G_k: float,
    Q_k_1: float,
    psi_fi: float,
    gamma_G: float = 1.35,
    gamma_Q: float = 1.5,
    gamma_GA: float = 1.0,
) -> float:
    """Niveau de charge en situation d'incendie [-].

    EN 1993-1-2 éq. (2.5) :

        η_fi = (γ_GA·G_k + ψ_fi·Q_k,1) / (γ_G·G_k + γ_Q,1·Q_k,1)

    Rapport de l'effet des actions en incendie à celui de l'ELU fondamental.
    """
    denominateur = gamma_G * G_k + gamma_Q * Q_k_1
    if denominateur <= 0.0:
        raise ValueError("Les charges à l'ELU fondamental sont nulles ou négatives.")
    return (gamma_GA * G_k + psi_fi * Q_k_1) / denominateur


def eta_fi_par_defaut(contexte: ContexteNormatif = SUISSE_SIA) -> float:
    """Niveau de charge conservatif, faute de charges détaillées [-].

    EN 1993-1-2 §2.4.2(3).
    """
    return contexte.eta_fi_defaut
