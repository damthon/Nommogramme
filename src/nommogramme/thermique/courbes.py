"""Courbes de feu nominales.

Référence : EN 1991-1-2 §3.2, équations (3.4) à (3.6).

Le coefficient de transfert par convection α_c est porté par la courbe
elle-même, la norme lui donnant une valeur différente selon l'action de feu
considérée.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["CourbeFeu", "ISO834", "HYDROCARBURE", "FEU_EXTERIEUR", "COURBES", "courbe"]


TEMPERATURE_INITIALE = 20.0
"""Température ambiante au début de l'incendie [°C]."""


@dataclass(frozen=True, slots=True)
class CourbeFeu:
    """Une courbe température-temps des gaz.

    ``temperature`` prend le temps en **secondes** et renvoie des degrés
    Celsius, conformément à la convention SI interne ; les formules normatives
    sont écrites en minutes, la conversion est faite sur place.
    """

    nom: str
    alpha_c: float
    """Coefficient de transfert par convection [W/m²·K]."""
    nominale: bool = True
    """Une courbe nominale ouvre droit au coefficient 0,9 de l'éq. (4.26a)."""

    _forme: str = "iso834"

    def temperature(self, t: float) -> float:
        """Température des gaz [°C] à l'instant ``t`` [s]."""
        minutes = max(t, 0.0) / 60.0
        if self._forme == "iso834":
            return 20.0 + 345.0 * math.log10(8.0 * minutes + 1.0)
        if self._forme == "hydrocarbure":
            return (
                1080.0
                * (
                    1.0
                    - 0.325 * math.exp(-0.167 * minutes)
                    - 0.675 * math.exp(-2.5 * minutes)
                )
                + 20.0
            )
        if self._forme == "exterieur":
            return (
                660.0
                * (
                    1.0
                    - 0.687 * math.exp(-0.32 * minutes)
                    - 0.313 * math.exp(-3.8 * minutes)
                )
                + 20.0
            )
        raise ValueError(f"Forme de courbe inconnue : {self._forme!r}")

    def __call__(self, t: float) -> float:
        return self.temperature(t)

    def __str__(self) -> str:
        return self.nom


ISO834 = CourbeFeu(
    nom="ISO 834 (feu normalisé)",
    alpha_c=25.0,
    nominale=True,
    _forme="iso834",
)
"""Courbe normalisée, EN 1991-1-2 éq. (3.4). α_c = 25 W/m²·K, §3.2.1(2)."""

HYDROCARBURE = CourbeFeu(
    nom="Hydrocarbures",
    alpha_c=50.0,
    nominale=True,
    _forme="hydrocarbure",
)
"""EN 1991-1-2 éq. (3.6). α_c = 50 W/m²·K, §3.2.3(2)."""

FEU_EXTERIEUR = CourbeFeu(
    nom="Feu extérieur",
    alpha_c=25.0,
    nominale=True,
    _forme="exterieur",
)
"""EN 1991-1-2 éq. (3.5). α_c = 25 W/m²·K, §3.2.2(2)."""


COURBES: dict[str, CourbeFeu] = {
    "iso834": ISO834,
    "hydrocarbure": HYDROCARBURE,
    "exterieur": FEU_EXTERIEUR,
}


def courbe(nom: str) -> CourbeFeu:
    """Retrouve une courbe par son identifiant court."""
    cle = nom.strip().lower().replace(" ", "").replace("-", "")
    if cle in COURBES:
        return COURBES[cle]
    raise KeyError(
        f"Courbe de feu {nom!r} inconnue. Disponibles : {', '.join(sorted(COURBES))}"
    )
