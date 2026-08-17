"""Interaction effort normal – flexion en situation d'incendie.

Référence : EN 1993-1-2 §4.2.3.5, équations (4.21a) et (4.21b).

Deux critères doivent être satisfaits simultanément : le flambement par
flexion et le déversement. Le taux d'utilisation retenu est le plus
défavorable des deux.

Le cas de la traction combinée à la flexion n'est pas couvert par le §4.2.3.5,
qui traite les éléments comprimés et fléchis. Il est traité ici par la somme
linéaire des taux, conservative et d'usage courant.
"""

from __future__ import annotations

from dataclasses import dataclass

from .resistances import Resistances

__all__ = ["FacteursInteraction", "TauxUtilisation", "facteurs_interaction", "taux"]


@dataclass(frozen=True, slots=True)
class FacteursInteraction:
    """Facteurs k et μ des équations (4.21a) et (4.21b)."""

    k_y: float
    k_z: float
    k_LT: float
    mu_y: float
    mu_z: float
    mu_LT: float


def facteurs_interaction(
    N_Ed: float,
    resistances: Resistances,
    aire: float,
    beta_M_y: float,
    beta_M_z: float,
    beta_M_LT: float,
) -> FacteursInteraction:
    """Facteurs d'interaction du §4.2.3.5.

        k_LT = 1 − μ_LT·N_fi,Ed / (χ_z,fi·A·k_y,θ·f_y/γ_M,fi)   ≤ 1
        μ_LT = 0,15·λ̄_z,θ·β_M,LT − 0,15                          ≤ 0,9

        k_y  = 1 − μ_y·N_fi,Ed / (χ_y,fi·A·k_y,θ·f_y/γ_M,fi)     ≤ 3
        μ_y  = (1,2·β_M,y − 3)·λ̄_y,θ + 0,44·β_M,y − 0,29         ≤ 0,8

        k_z  = 1 − μ_z·N_fi,Ed / (χ_z,fi·A·k_y,θ·f_y/γ_M,fi)     ≤ 3
        μ_z  = (2·β_M,z − 5)·λ̄_z,θ + 0,44·β_M,z − 0,29           ≤ 0,8

    L'élancement λ̄_z,θ est plafonné à 1,1 dans l'expression de μ_z.

    La numérotation exacte de ces six équations dans le texte normatif reste à
    confirmer sur un exemplaire de la norme ; leur contenu, lui, est celui du
    §4.2.3.5.
    """
    resistance_plastique = (
        aire * resistances.k_y_theta * resistances.fy / resistances.gamma_M_fi
    )

    mu_LT = min(0.15 * resistances.lambda_z_theta * beta_M_LT - 0.15, 0.9)
    mu_y = min(
        (1.2 * beta_M_y - 3.0) * resistances.lambda_y_theta + 0.44 * beta_M_y - 0.29,
        0.8,
    )
    lambda_z_plafonnee = min(resistances.lambda_z_theta, 1.1)
    mu_z = min(
        (2.0 * beta_M_z - 5.0) * lambda_z_plafonnee + 0.44 * beta_M_z - 0.29,
        0.8,
    )

    def _k(mu: float, chi: float, plafond: float) -> float:
        if chi <= 0.0 or resistance_plastique <= 0.0:
            return plafond
        return min(1.0 - mu * N_Ed / (chi * resistance_plastique), plafond)

    return FacteursInteraction(
        k_y=_k(mu_y, resistances.chi_y_fi, 3.0),
        k_z=_k(mu_z, resistances.chi_z_fi, 3.0),
        k_LT=_k(mu_LT, resistances.chi_z_fi, 1.0),
        mu_y=mu_y,
        mu_z=mu_z,
        mu_LT=mu_LT,
    )


@dataclass(frozen=True, slots=True)
class TauxUtilisation:
    """Taux d'utilisation de l'élément à une température donnée."""

    valeur: float
    """Taux le plus défavorable [-]. La ruine correspond à 1,0."""
    critere: str
    """Équation qui gouverne."""
    taux_flambement: float
    """Membre de gauche de l'éq. (4.21a) [-]."""
    taux_deversement: float
    """Membre de gauche de l'éq. (4.21b) [-]."""
    facteurs: FacteursInteraction | None
    resistances: Resistances

    @property
    def satisfait(self) -> bool:
        return self.valeur <= 1.0

    def __str__(self) -> str:
        return f"{self.valeur:.3f} ({self.critere})"


def taux(
    N_Ed: float,
    My_Ed: float,
    Mz_Ed: float,
    resistances: Resistances,
    aire: float,
    beta_M_y: float = 1.3,
    beta_M_z: float = 1.3,
    beta_M_LT: float = 1.3,
    deversement_possible: bool = True,
) -> TauxUtilisation:
    """Taux d'utilisation sous N + M_y + M_z.

    ``N_Ed`` positif en compression. Renvoie le plus défavorable des critères
    de flambement (4.21a) et de déversement (4.21b).

    ``deversement_possible`` à ``False`` écarte l'éq. (4.21b), le §4.2.3.5 ne
    l'imposant qu'aux éléments pour lesquels le déversement est un mode de
    ruine potentiel. C'est le cas d'une poutre dont la semelle comprimée est
    maintenue latéralement sur toute sa longueur.
    """
    if N_Ed < 0.0:
        return _taux_traction_flexion(
            abs(N_Ed), My_Ed, Mz_Ed, resistances
        )

    facteurs = facteurs_interaction(
        N_Ed, resistances, aire, beta_M_y, beta_M_z, beta_M_LT
    )

    def _part(effort: float, resistance: float) -> float:
        if resistance <= 0.0:
            return float("inf") if effort > 0.0 else 0.0
        return effort / resistance

    # Éq. (4.21a) — flambement par flexion.
    flambement = (
        _part(N_Ed, resistances.N_Rd)
        + facteurs.k_y * _part(My_Ed, resistances.My_Rd)
        + facteurs.k_z * _part(Mz_Ed, resistances.Mz_Rd)
    )

    # Éq. (4.21b) — déversement. Le terme axial est rapporté à χ_z seul.
    if deversement_possible:
        deversement = (
            _part(N_Ed, resistances.N_Rd_z)
            + facteurs.k_LT * _part(My_Ed, resistances.Mb_Rd)
            + facteurs.k_z * _part(Mz_Ed, resistances.Mz_Rd)
        )
    else:
        deversement = 0.0

    if flambement >= deversement:
        valeur, critere = flambement, "éq. (4.21a) — flambement par flexion"
    else:
        valeur, critere = deversement, "éq. (4.21b) — déversement"

    return TauxUtilisation(
        valeur=valeur,
        critere=critere,
        taux_flambement=flambement,
        taux_deversement=deversement,
        facteurs=facteurs,
        resistances=resistances,
    )


def _taux_traction_flexion(
    N_traction: float, My_Ed: float, Mz_Ed: float, resistances: Resistances
) -> TauxUtilisation:
    """Traction combinée à la flexion.

    Le §4.2.3.5 ne couvre que la compression. La somme linéaire des taux
    retenue ici est conservative : la traction stabilise l'élément vis-à-vis
    du déversement, effet favorable qui n'est pas exploité.
    """

    def _part(effort: float, resistance: float) -> float:
        if resistance <= 0.0:
            return float("inf") if effort > 0.0 else 0.0
        return effort / resistance

    valeur = (
        _part(N_traction, resistances.N_Rd)
        + _part(My_Ed, resistances.My_Rd)
        + _part(Mz_Ed, resistances.Mz_Rd)
    )
    return TauxUtilisation(
        valeur=valeur,
        critere="traction et flexion — somme linéaire (hors §4.2.3.5)",
        taux_flambement=valeur,
        taux_deversement=valeur,
        facteurs=None,
        resistances=resistances,
    )
