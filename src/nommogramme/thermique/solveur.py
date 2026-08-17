"""Inversions du calcul thermique.

Deux questions se posent en pratique, symétriques l'une de l'autre :

* combien de temps un élément donné tient-il avant d'atteindre sa température
  critique ?
* quelle épaisseur de protection faut-il pour tenir une durée exigée ?

La seconde se résout par dichotomie : à durée fixée, la température atteinte
par l'acier décroît strictement avec l'épaisseur d'isolant, ce qui garantit
l'unicité de la solution.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..materiaux.protection import Protection
from ..profils.geometrie import Exposition
from ..profils.modele import Profil
from ..unites import en_minutes, minutes
from .courbes import ISO834, CourbeFeu
from .evolution import ResultatThermique, echauffement

__all__ = [
    "EPAISSEURS_COMMERCIALES",
    "EpaisseurRequise",
    "duree_avant_temperature",
    "epaisseur_requise",
]


EPAISSEURS_COMMERCIALES: tuple[float, ...] = (
    0.005, 0.008, 0.010, 0.0125, 0.015, 0.018, 0.020, 0.025,
    0.030, 0.035, 0.040, 0.045, 0.050, 0.060, 0.070, 0.080,
)
"""Épaisseurs d'arrondi par défaut [m], indicatives.

À remplacer par la gamme réelle du produit retenu.
"""

_DP_MIN = 0.0001
"""Borne basse de la dichotomie [m] — 0,1 mm."""
_DP_MAX = 0.200
"""Borne haute de la dichotomie [m] — 200 mm."""

_TOLERANCE_THETA = 0.5
"""Tolérance sur la température atteinte [°C]."""

_ITERATIONS_MAX = 60


def duree_avant_temperature(
    profil: Profil,
    exposition: Exposition,
    theta_cible: float,
    courbe: CourbeFeu = ISO834,
    protection: Protection | None = None,
    duree_max: float = 14400.0,
    dt: float | None = None,
) -> tuple[float | None, ResultatThermique]:
    """Instant [s] où l'acier atteint ``theta_cible``, et l'historique complet.

    ``duree_max`` vaut quatre heures par défaut. Un premier élément ``None``
    signifie que la température n'est pas atteinte sur cette durée : l'élément
    tient donc au moins ``duree_max``.
    """
    resultat = echauffement(
        profil=profil,
        exposition=exposition,
        duree=duree_max,
        courbe=courbe,
        protection=protection,
        dt=dt,
    )
    return resultat.temps_pour_atteindre(theta_cible), resultat


@dataclass(frozen=True, slots=True)
class EpaisseurRequise:
    """Résultat d'une recherche d'épaisseur de protection."""

    d_p: float
    """Épaisseur exacte satisfaisant tout juste le critère [m]."""
    d_p_arrondie: float
    """Épaisseur commerciale immédiatement supérieure [m]."""
    theta_atteinte: float
    """Température de l'acier à l'échéance, avec ``d_p`` [°C]."""
    theta_arrondie: float
    """Température de l'acier à l'échéance, avec ``d_p_arrondie`` [°C]."""
    theta_cible: float
    duree_requise: float
    """Durée exigée [s]."""
    iterations: int
    protection: Protection
    """Protection à l'épaisseur exacte trouvée."""

    @property
    def d_p_mm(self) -> float:
        return self.d_p * 1e3

    @property
    def d_p_arrondie_mm(self) -> float:
        return self.d_p_arrondie * 1e3

    def __str__(self) -> str:
        return (
            f"{self.protection.libelle or self.protection.nom} : "
            f"{self.d_p_mm:.1f} mm requis → {self.d_p_arrondie_mm:.1f} mm retenus "
            f"(θ_a = {self.theta_arrondie:.0f} °C ≤ {self.theta_cible:.0f} °C "
            f"à {en_minutes(self.duree_requise):.0f} min)"
        )


def epaisseur_requise(
    profil: Profil,
    exposition: Exposition,
    protection: Protection,
    theta_cible: float,
    duree_requise: float,
    courbe: CourbeFeu = ISO834,
    dt: float | None = None,
    epaisseurs_commerciales: tuple[float, ...] = EPAISSEURS_COMMERCIALES,
) -> EpaisseurRequise:
    """Épaisseur d'isolant nécessaire pour rester sous ``theta_cible``.

    ``duree_requise`` en secondes. La protection fournie sert de gabarit :
    seules ses propriétés matériau sont utilisées, son épaisseur est le point
    de départ et non une contrainte.

    Lève ``ValueError`` si même l'épaisseur maximale explorée (200 mm) ne
    suffit pas — signe qu'il faut changer de produit ou de profilé.
    """

    def theta_finale(d_p: float) -> float:
        resultat = echauffement(
            profil=profil,
            exposition=exposition,
            duree=duree_requise,
            courbe=courbe,
            protection=protection.avec_epaisseur(d_p),
            dt=dt,
        )
        return resultat.temperature_finale

    if theta_finale(_DP_MAX) > theta_cible:
        raise ValueError(
            f"Même {_DP_MAX * 1e3:.0f} mm de « {protection.libelle or protection.nom} » "
            f"ne ramènent pas {profil.nom} sous {theta_cible:.0f} °C à "
            f"{en_minutes(duree_requise):.0f} min "
            f"(θ_a = {theta_finale(_DP_MAX):.0f} °C). "
            "Changer de produit, de profilé, ou revoir le chargement."
        )

    bas, haut = _DP_MIN, _DP_MAX
    iterations = 0
    for iterations in range(1, _ITERATIONS_MAX + 1):
        milieu = 0.5 * (bas + haut)
        theta = theta_finale(milieu)
        if abs(theta - theta_cible) <= _TOLERANCE_THETA:
            break
        if theta > theta_cible:
            bas = milieu  # trop chaud : il faut plus d'isolant
        else:
            haut = milieu

    d_p = 0.5 * (bas + haut)
    theta_exacte = theta_finale(d_p)

    d_p_arrondie = _arrondir(d_p, epaisseurs_commerciales)
    theta_arrondie = theta_finale(d_p_arrondie)

    return EpaisseurRequise(
        d_p=d_p,
        d_p_arrondie=d_p_arrondie,
        theta_atteinte=theta_exacte,
        theta_arrondie=theta_arrondie,
        theta_cible=theta_cible,
        duree_requise=duree_requise,
        iterations=iterations,
        protection=protection.avec_epaisseur(d_p),
    )


def epaisseur_requise_minutes(
    profil: Profil,
    exposition: Exposition,
    protection: Protection,
    theta_cible: float,
    duree_requise_min: float,
    **options,
) -> EpaisseurRequise:
    """Variante prenant la durée exigée en minutes (R30, R60, R90…)."""
    return epaisseur_requise(
        profil=profil,
        exposition=exposition,
        protection=protection,
        theta_cible=theta_cible,
        duree_requise=minutes(duree_requise_min),
        **options,
    )


def _arrondir(d_p: float, gamme: tuple[float, ...]) -> float:
    """Épaisseur commerciale immédiatement supérieure [m]."""
    for epaisseur in sorted(gamme):
        if epaisseur >= d_p:
            return epaisseur
    return d_p
