"""Propriétés de l'acier de construction à température élevée.

Référence : EN 1993-1-2 §3. Les facteurs de réduction du tableau 3.1 sont
indépendants de la nuance ; seule la limite d'élasticité de référence change.
"""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from enum import Enum

__all__ = [
    "RHO_A",
    "E_A",
    "TABLEAU_3_1",
    "Nuance",
    "k_y",
    "k_p",
    "k_E",
    "chaleur_specifique",
    "conductivite",
    "limite_elasticite",
    "temperature_pour_k_y",
]


RHO_A = 7850.0
"""Masse volumique de l'acier [kg/m³], indépendante de la température.

EN 1993-1-2 §3.2.2.
"""

E_A = 210e9
"""Module d'élasticité à 20 °C [Pa]."""


# EN 1993-1-2 tableau 3.1 : θ_a [°C] → (k_y,θ, k_p,θ, k_E,θ)
TABLEAU_3_1: dict[int, tuple[float, float, float]] = {
    20: (1.000, 1.000, 1.0000),
    100: (1.000, 1.000, 1.0000),
    200: (1.000, 0.807, 0.9000),
    300: (1.000, 0.613, 0.8000),
    400: (1.000, 0.420, 0.7000),
    500: (0.780, 0.360, 0.6000),
    600: (0.470, 0.180, 0.3100),
    700: (0.230, 0.075, 0.1300),
    800: (0.110, 0.050, 0.0900),
    900: (0.060, 0.0375, 0.0675),
    1000: (0.040, 0.0250, 0.0450),
    1100: (0.020, 0.0125, 0.0225),
    1200: (0.000, 0.000, 0.0000),
}

_TEMPERATURES = sorted(TABLEAU_3_1)
_K_Y = [TABLEAU_3_1[t][0] for t in _TEMPERATURES]
_K_P = [TABLEAU_3_1[t][1] for t in _TEMPERATURES]
_K_E = [TABLEAU_3_1[t][2] for t in _TEMPERATURES]

TEMPERATURE_MIN = float(_TEMPERATURES[0])
TEMPERATURE_MAX = float(_TEMPERATURES[-1])


def _interpoler(theta: float, valeurs: list[float]) -> float:
    """Interpolation linéaire dans le tableau 3.1, avec saturation aux bornes."""
    if theta <= TEMPERATURE_MIN:
        return valeurs[0]
    if theta >= TEMPERATURE_MAX:
        return valeurs[-1]

    indice = bisect_left(_TEMPERATURES, theta)
    t0, t1 = _TEMPERATURES[indice - 1], _TEMPERATURES[indice]
    v0, v1 = valeurs[indice - 1], valeurs[indice]
    return v0 + (v1 - v0) * (theta - t0) / (t1 - t0)


def k_y(theta: float) -> float:
    """Facteur de réduction de la limite d'élasticité efficace [-].

    EN 1993-1-2 tableau 3.1. Vaut 1 jusqu'à 400 °C, puis chute rapidement.
    """
    return _interpoler(theta, _K_Y)


def k_p(theta: float) -> float:
    """Facteur de réduction de la limite de proportionnalité [-]."""
    return _interpoler(theta, _K_P)


def k_E(theta: float) -> float:
    """Facteur de réduction de la pente du domaine élastique linéaire [-].

    Décroît plus vite que ``k_y``, ce qui augmente l'élancement réduit à chaud.
    """
    return _interpoler(theta, _K_E)


def temperature_pour_k_y(valeur: float) -> float:
    """Inverse de ``k_y`` : température à laquelle k_y,θ atteint ``valeur`` [°C].

    ``k_y`` est constant à 1 jusqu'à 400 °C ; l'inverse renvoie donc 400 °C
    pour toute valeur supérieure ou égale à 1. Au-delà, la fonction est
    strictement décroissante et l'inverse est unique.
    """
    if valeur >= 1.0:
        return 400.0
    if valeur <= 0.0:
        return TEMPERATURE_MAX

    for indice in range(1, len(_TEMPERATURES)):
        haut, bas = _K_Y[indice - 1], _K_Y[indice]
        if bas <= valeur <= haut:
            t0, t1 = _TEMPERATURES[indice - 1], _TEMPERATURES[indice]
            if haut == bas:
                return float(t1)
            return t0 + (t1 - t0) * (haut - valeur) / (haut - bas)
    return TEMPERATURE_MAX


def chaleur_specifique(theta: float) -> float:
    """Chaleur spécifique de l'acier au carbone [J/kg·K].

    EN 1993-1-2 §3.4.1.2, équations (3.2a) à (3.2d).

    La singularité à 735 °C traduit la transformation de phase : la chaleur
    spécifique y passe par un pic, ce qui produit le palier caractéristique
    des courbes d'échauffement.
    """
    if theta < 20.0:
        theta = 20.0
    if theta < 600.0:
        return (
            425.0
            + 7.73e-1 * theta
            - 1.69e-3 * theta**2
            + 2.22e-6 * theta**3
        )
    if theta < 735.0:
        return 666.0 + 13002.0 / (738.0 - theta)
    if theta < 900.0:
        return 545.0 + 17820.0 / (theta - 731.0)
    return 650.0


def conductivite(theta: float) -> float:
    """Conductivité thermique de l'acier au carbone [W/m·K].

    EN 1993-1-2 §3.4.1.3, équations (3.3a) et (3.3b).

    N'intervient pas dans le modèle à température uniforme, mais permet de
    justifier cette hypothèse par le nombre de Biot.
    """
    if theta < 800.0:
        return 54.0 - 3.33e-2 * max(theta, 20.0)
    return 27.3


@dataclass(frozen=True, slots=True)
class _Bandes:
    """Limite d'élasticité par bande d'épaisseur [Pa]."""

    jusqu_a_40mm: float
    au_dela: float


class Nuance(str, Enum):
    """Nuances d'acier de construction (EN 10025-2, reprises en SIA 263).

    La limite d'élasticité décroît avec l'épaisseur du produit — effet non
    négligeable sur les profilés lourds des familles HHD et HL.
    """

    S235 = "S235"
    S275 = "S275"
    S355 = "S355"
    S420 = "S420"
    S460 = "S460"

    @property
    def _bandes(self) -> _Bandes:
        return _BANDES[self]

    @property
    def fy_nominal(self) -> float:
        """Limite d'élasticité nominale, épaisseur ≤ 40 mm [Pa]."""
        return self._bandes.jusqu_a_40mm


_BANDES: dict[Nuance, _Bandes] = {
    Nuance.S235: _Bandes(235e6, 215e6),
    Nuance.S275: _Bandes(275e6, 255e6),
    Nuance.S355: _Bandes(355e6, 335e6),
    Nuance.S420: _Bandes(420e6, 390e6),
    Nuance.S460: _Bandes(460e6, 430e6),
}


def limite_elasticite(nuance: Nuance, epaisseur: float) -> float:
    """Limite d'élasticité pour une épaisseur de produit donnée [Pa].

    EN 1993-1-1 tableau 3.1, repris par SIA 263 tableau 1. ``epaisseur`` en
    mètres — pour un profilé, l'épaisseur déterminante est celle de la
    semelle.
    """
    bandes = _BANDES[nuance]
    return bandes.jusqu_a_40mm if epaisseur <= 0.040 else bandes.au_dela
