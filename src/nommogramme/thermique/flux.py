"""Flux thermique net à la surface exposée.

Référence : EN 1991-1-2 §3.1, équations (3.1) à (3.3). C'est la condition aux
limites de tout le calcul de diffusion.
"""

from __future__ import annotations

__all__ = [
    "SIGMA",
    "EPSILON_ACIER_CARBONE",
    "EPSILON_ACIER_INOX",
    "EPSILON_FEU",
    "PHI_DEFAUT",
    "flux_net",
    "flux_convectif",
    "flux_radiatif",
]


SIGMA = 5.67e-8
"""Constante de Stefan-Boltzmann [W/m²·K⁴]."""

EPSILON_ACIER_CARBONE = 0.7
"""Émissivité de surface de l'acier au carbone [-]. EN 1993-1-2 §2.2(2)."""

EPSILON_ACIER_INOX = 0.4
"""Émissivité de surface de l'acier inoxydable [-]. EN 1993-1-2 annexe C."""

EPSILON_FEU = 1.0
"""Émissivité du feu [-]. EN 1991-1-2 §3.1(6)."""

PHI_DEFAUT = 1.0
"""Facteur de forme [-]. EN 1991-1-2 §3.1(7), valeur par défaut."""

_ZERO_ABSOLU = 273.0
"""Décalage Celsius → Kelvin retenu par l'EN 1991-1-2 éq. (3.3)."""


def flux_convectif(theta_g: float, theta_m: float, alpha_c: float) -> float:
    """Composante convective du flux net [W/m²].

    EN 1991-1-2 éq. (3.2) : ḣ_net,c = α_c · (θ_g − θ_m).
    """
    return alpha_c * (theta_g - theta_m)


def flux_radiatif(
    theta_r: float,
    theta_m: float,
    epsilon_m: float = EPSILON_ACIER_CARBONE,
    epsilon_f: float = EPSILON_FEU,
    phi: float = PHI_DEFAUT,
) -> float:
    """Composante radiative du flux net [W/m²].

    EN 1991-1-2 éq. (3.3) :
        ḣ_net,r = Φ · ε_m · ε_f · σ · [(θ_r + 273)⁴ − (θ_m + 273)⁴]
    """
    return (
        phi
        * epsilon_m
        * epsilon_f
        * SIGMA
        * ((theta_r + _ZERO_ABSOLU) ** 4 - (theta_m + _ZERO_ABSOLU) ** 4)
    )


def flux_net(
    theta_g: float,
    theta_m: float,
    alpha_c: float,
    epsilon_m: float = EPSILON_ACIER_CARBONE,
    epsilon_f: float = EPSILON_FEU,
    phi: float = PHI_DEFAUT,
    theta_r: float | None = None,
) -> float:
    """Flux thermique net à la surface [W/m²].

    EN 1991-1-2 §3.1(3) : ḣ_net = ḣ_net,c + ḣ_net,r.

    ``theta_r`` est la température de rayonnement ; pour un élément entouré de
    flammes elle est prise égale à la température des gaz, ce qui est le cas
    par défaut.
    """
    if theta_r is None:
        theta_r = theta_g
    return flux_convectif(theta_g, theta_m, alpha_c) + flux_radiatif(
        theta_r, theta_m, epsilon_m, epsilon_f, phi
    )
