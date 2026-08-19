"""Température critique — l'équation du nomogramme.

Référence : EN 1993-1-2 §4.2.4, équations (4.22) à (4.24).

L'équation (4.22) est l'inversion analytique de la courbe k_y,θ(θ) du tableau
3.1. Elle est rigoureuse pour les éléments dont la ruine est gouvernée par la
résistance de section — traction, flexion sans déversement. Dès que le
flambement ou le déversement gouverne, χ_fi décroît **en plus** de k_y,θ, par
l'élancement qui croît avec √(k_y,θ/k_E,θ) : l'équation (4.22) devient alors
non conservative, d'où la vérification croisée du module ``verification``.
"""

from __future__ import annotations

import math

__all__ = [
    "MU_0_MINIMAL",
    "temperature_critique",
    "degre_utilisation_pour",
    "temperature_critique_classe_4",
]


MU_0_MINIMAL = 0.013
"""Borne inférieure de validité de l'éq. (4.22) [-].

En deçà, l'argument du logarithme diverge et la formule perd son sens : la
température critique dépasserait de toute façon le domaine du tableau 3.1.
"""


def temperature_critique(mu_0: float) -> float:
    """Température critique de l'acier [°C].

    EN 1993-1-2 éq. (4.22) :

        θ_a,cr = 39,19 · ln[ 1 / (0,9674 · μ₀^3,833) − 1 ] + 482

    ``mu_0`` est le degré d'utilisation à l'instant t = 0, c'est-à-dire le taux
    de travail de l'élément à 20 °C sous les charges d'incendie et avec les
    conditions d'appui de l'incendie.

    Quelques repères : μ₀ = 0,3 → 664 °C ; 0,5 → 585 °C ; 0,7 → 526 °C.
    """
    if mu_0 <= 0.0:
        raise ValueError(f"Degré d'utilisation non positif : {mu_0}")
    if mu_0 >= 1.0:
        raise ValueError(
            f"Degré d'utilisation de {mu_0:.3f} : l'élément ne tient déjà pas "
            "à froid sous les charges d'incendie."
        )
    if mu_0 < MU_0_MINIMAL:
        raise ValueError(
            f"Degré d'utilisation de {mu_0:.4f} inférieur à la borne de "
            f"validité {MU_0_MINIMAL} de l'éq. (4.22)."
        )

    return 39.19 * math.log(1.0 / (0.9674 * mu_0**3.833) - 1.0) + 482.0


def degre_utilisation_pour(theta_cr: float) -> float:
    """Inverse de l'éq. (4.22) : degré d'utilisation donnant ``theta_cr`` [-].

    Utile pour lire le nomogramme dans l'autre sens — quel taux de travail
    maximal accepter pour viser une température critique donnée.
    """
    exposant = (theta_cr - 482.0) / 39.19
    denominateur = 0.9674 * (math.exp(exposant) + 1.0)
    return (1.0 / denominateur) ** (1.0 / 3.833)


def temperature_critique_classe_4(theta_conventionnelle: float = 350.0) -> float:
    """Température critique conventionnelle d'une section de classe 4 [°C].

    EN 1993-1-2 annexe E, valeur recommandée de 350 °C. L'équation (4.22) ne
    s'applique pas à ces sections : le voilement local précède la
    plastification, et la corrélation entre k_y,θ et la résistance disparaît.
    """
    return theta_conventionnelle
