"""Solutions de référence indépendantes, pour la validation.

Ce module ne fait pas partie de la bibliothèque : il contient des solutions
du **même problème physique**, obtenues par des voies volontairement
différentes de celles du code testé, de façon qu'une erreur d'implémentation
ne puisse pas se reproduire à l'identique des deux côtés.

Trois voies indépendantes :

* ``enthalpie`` — intégration **analytique en forme fermée** des équations
  (3.2a) à (3.2d) de la chaleur spécifique, alors que le code n'en évalue que
  la valeur ponctuelle ;
* ``temps_par_quadrature`` — résolution de l'équation différentielle par
  **séparation des variables et quadrature de Simpson**, alors que le code
  applique le schéma d'Euler explicite imposé par la norme ;
* ``chaleur_absorbee`` — accumulation du flux entrant, à confronter à la
  variation d'enthalpie.
"""

from __future__ import annotations

import math
from collections.abc import Callable

__all__ = [
    "enthalpie",
    "temps_par_quadrature",
    "CourbeConstante",
]


# --- enthalpie massique de l'acier, en forme fermée --------------------------
#
# Primitives des équations (3.2a) à (3.2d) de l'EN 1993-1-2. Le raccordement
# entre morceaux se fait par continuité, l'origine étant prise à 20 °C.


def _primitive_polynomiale(t: float) -> float:
    """∫(425 + 7,73·10⁻¹·θ − 1,69·10⁻³·θ² + 2,22·10⁻⁶·θ³) dθ"""
    return (
        425.0 * t
        + 7.73e-1 / 2.0 * t**2
        - 1.69e-3 / 3.0 * t**3
        + 2.22e-6 / 4.0 * t**4
    )


def _primitive_montante(t: float) -> float:
    """∫(666 + 13002/(738 − θ)) dθ"""
    return 666.0 * t - 13002.0 * math.log(738.0 - t)


def _primitive_descendante(t: float) -> float:
    """∫(545 + 17820/(θ − 731)) dθ"""
    return 545.0 * t + 17820.0 * math.log(t - 731.0)


def _primitive_constante(t: float) -> float:
    """∫650 dθ"""
    return 650.0 * t


_H_20 = _primitive_polynomiale(20.0)
_H_600 = _primitive_polynomiale(600.0) - _H_20
_H_735 = _H_600 + _primitive_montante(735.0) - _primitive_montante(600.0)
_H_900 = _H_735 + _primitive_descendante(900.0) - _primitive_descendante(735.0)


def enthalpie(theta: float) -> float:
    """Enthalpie massique de l'acier [J/kg], origine à 20 °C.

    Primitive exacte de ``chaleur_specifique``. Sa dérivée doit redonner
    c_a(θ) — ce que vérifie ``test_validation``.
    """
    if theta <= 20.0:
        return 0.0
    if theta < 600.0:
        return _primitive_polynomiale(theta) - _H_20
    if theta < 735.0:
        return _H_600 + _primitive_montante(theta) - _primitive_montante(600.0)
    if theta < 900.0:
        return _H_735 + _primitive_descendante(theta) - _primitive_descendante(735.0)
    return _H_900 + _primitive_constante(theta) - _primitive_constante(900.0)


# --- résolution par séparation des variables ---------------------------------


def temps_par_quadrature(
    theta_debut: float,
    theta_fin: float,
    vitesse: Callable[[float], float],
    intervalles: int = 20000,
) -> float:
    """Temps [s] pour passer de ``theta_debut`` à ``theta_fin``.

    Résout dθ/dt = v(θ) par séparation des variables :

        t = ∫ dθ / v(θ)

    par quadrature de Simpson composite. Cette voie n'a rien de commun avec le
    pas-à-pas d'Euler du code testé : elle intègre en température au lieu
    d'intégrer en temps.

    Ne vaut que pour une vitesse ne dépendant que de θ, donc pour une
    température de gaz constante.
    """
    if theta_fin <= theta_debut:
        raise ValueError("La température finale doit dépasser l'initiale.")
    if intervalles % 2:
        intervalles += 1

    pas = (theta_fin - theta_debut) / intervalles

    def integrande(theta: float) -> float:
        v = vitesse(theta)
        if v <= 0.0:
            raise ValueError(
                f"Vitesse d'échauffement nulle ou négative à {theta:.1f} °C : "
                "la température visée n'est pas atteignable."
            )
        return 1.0 / v

    total = integrande(theta_debut) + integrande(theta_fin)
    for indice in range(1, intervalles):
        poids = 4.0 if indice % 2 else 2.0
        total += poids * integrande(theta_debut + indice * pas)
    return total * pas / 3.0


# --- four isotherme ----------------------------------------------------------


class CourbeConstante:
    """Four à température constante.

    Aucune courbe normative n'est isotherme, mais c'est la seule condition
    sous laquelle la vitesse d'échauffement ne dépend que de la température de
    l'acier — donc la seule qui autorise la résolution par quadrature
    ci-dessus. Implémente l'interface attendue par ``echauffement``.
    """

    nominale = True

    def __init__(self, theta_g: float, alpha_c: float = 25.0) -> None:
        self.theta_g = theta_g
        self.alpha_c = alpha_c
        self.nom = f"four isotherme à {theta_g:.0f} °C"

    def temperature(self, t: float) -> float:
        del t
        return self.theta_g

    def __call__(self, t: float) -> float:
        return self.temperature(t)

    def __str__(self) -> str:
        return self.nom
