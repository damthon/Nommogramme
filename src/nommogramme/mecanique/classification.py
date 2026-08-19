"""Classification des sections en situation d'incendie.

Référence : EN 1993-1-2 §4.2.2 pour le coefficient ε, EN 1993-1-1 tableau 5.2
pour les élancements limites de parois.

Le coefficient 0,85 de l'éq. du §4.2.2 vaut approximativement √(k_E,θ/k_y,θ) :
le module chutant plus vite que la limite d'élasticité, une paroi voile plus
facilement à chaud. Une section de classe 3 à froid peut donc passer en
classe 4 à chaud, ce qui écarte l'équation (4.22) au profit de la température
critique conventionnelle de 350 °C.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..profils.modele import Forme, Profil

__all__ = ["Classe", "ClassificationSection", "epsilon_feu", "classifier"]


def epsilon_feu(fy: float) -> float:
    """Coefficient ε en situation d'incendie [-].

    EN 1993-1-2 §4.2.2 : ε = 0,85·√(235/f_y), avec f_y en pascals.
    """
    return 0.85 * math.sqrt(235e6 / fy)


class Classe(int):
    """Classe de section, de 1 à 4."""

    def __str__(self) -> str:
        return f"classe {int(self)}"


@dataclass(frozen=True, slots=True)
class ClassificationSection:
    """Résultat de la classification d'une section."""

    classe: int
    classe_ame: int
    classe_semelle: int
    epsilon: float
    elancement_ame: float
    """c/t de l'âme [-]."""
    elancement_semelle: float
    """c/t de la semelle comprimée [-]."""
    alpha: float
    """Position de l'axe neutre plastique dans l'âme [-], entre 0 et 1."""

    @property
    def plastique(self) -> bool:
        """Classes 1 et 2 : le module plastique est mobilisable."""
        return self.classe <= 2

    @property
    def elancee(self) -> bool:
        """Classe 4 : voilement local avant plastification."""
        return self.classe == 4

    def __str__(self) -> str:
        return (
            f"classe {self.classe} "
            f"(âme {self.classe_ame}, semelle {self.classe_semelle})"
        )


def _classe_semelle_comprimee(c_sur_t: float, eps: float) -> int:
    """Paroi en console, comprimée. EN 1993-1-1 tableau 5.2, feuille 2."""
    if c_sur_t <= 9.0 * eps:
        return 1
    if c_sur_t <= 10.0 * eps:
        return 2
    if c_sur_t <= 14.0 * eps:
        return 3
    return 4


def _classe_ame(c_sur_t: float, eps: float, alpha: float, psi: float) -> int:
    """Paroi interne fléchie et comprimée. EN 1993-1-1 tableau 5.2, feuille 1.

    ``alpha`` est la proportion comprimée de l'âme sous distribution plastique,
    ``psi`` le rapport des contraintes aux bords sous distribution élastique.
    """
    # Classes 1 et 2 : distribution plastique, pilotée par α.
    if alpha > 0.5:
        limite_1 = 396.0 * eps / (13.0 * alpha - 1.0)
        limite_2 = 456.0 * eps / (13.0 * alpha - 1.0)
    else:
        alpha_sur = max(alpha, 1e-6)
        limite_1 = 36.0 * eps / alpha_sur
        limite_2 = 41.5 * eps / alpha_sur

    if c_sur_t <= limite_1:
        return 1
    if c_sur_t <= limite_2:
        return 2

    # Classe 3 : distribution élastique, pilotée par ψ.
    if psi > -1.0:
        limite_3 = 42.0 * eps / (0.67 + 0.33 * psi)
    else:
        limite_3 = 62.0 * eps * (1.0 - psi) * math.sqrt(-psi)

    return 3 if c_sur_t <= limite_3 else 4


def _alpha_et_psi(
    profil: Profil, fy: float, N_Ed: float, M_Ed: float, c_ame: float
) -> tuple[float, float]:
    """Position de l'axe neutre plastique et rapport des contraintes élastiques.

    ``alpha`` : sous effort normal de compression, l'axe neutre plastique se
    déplace dans l'âme de N_Ed/(2·t_w·f_y). Rapporté à la hauteur d'âme
    comprimée, cela donne α = ½·(1 + N_Ed/(c·t_w·f_y)), borné à [0, 1].

    ``psi`` : rapport des contraintes élastiques aux deux bords de l'âme,
    σ = N/A ± M/W_el.
    """
    resistance_ame = c_ame * profil.tw * fy
    if resistance_ame <= 0.0:
        return 1.0, 1.0

    alpha = 0.5 * (1.0 + N_Ed / resistance_ame)
    alpha = min(max(alpha, 0.0), 1.0)

    sigma_N = N_Ed / profil.A
    sigma_M = M_Ed / profil.Wely if profil.Wely > 0.0 else 0.0
    sigma_max = sigma_N + sigma_M
    sigma_min = sigma_N - sigma_M

    if abs(sigma_max) < 1e-9:
        psi = 1.0
    else:
        psi = sigma_min / sigma_max
    psi = min(max(psi, -3.0), 1.0)

    return alpha, psi


def classifier(
    profil: Profil,
    fy: float,
    N_Ed: float = 0.0,
    My_Ed: float = 0.0,
) -> ClassificationSection:
    """Classe de la section en situation d'incendie.

    ``N_Ed`` positif en compression. La classification dépend du chargement :
    une même section peut être de classe 1 en flexion pure et de classe 4 sous
    compression dominante.
    """
    eps = epsilon_feu(fy)

    if profil.forme is Forme.PROFIL_CREUX:
        return _classifier_profil_creux(profil, eps, fy, N_Ed, My_Ed)

    # Semelle en console : c mesuré depuis le congé jusqu'au bord libre.
    c_semelle = (profil.b - profil.tw - 2.0 * profil.r) / 2.0
    elancement_semelle = c_semelle / profil.tf
    classe_semelle = _classe_semelle_comprimee(elancement_semelle, eps)

    # Âme : hauteur droite entre congés.
    c_ame = profil.h - 2.0 * profil.tf - 2.0 * profil.r
    elancement_ame = c_ame / profil.tw
    alpha, psi = _alpha_et_psi(profil, fy, N_Ed, My_Ed, c_ame)
    classe_ame = _classe_ame(elancement_ame, eps, alpha, psi)

    return ClassificationSection(
        classe=max(classe_ame, classe_semelle),
        classe_ame=classe_ame,
        classe_semelle=classe_semelle,
        epsilon=eps,
        elancement_ame=elancement_ame,
        elancement_semelle=elancement_semelle,
        alpha=alpha,
    )


def _classifier_profil_creux(
    profil: Profil, eps: float, fy: float, N_Ed: float, My_Ed: float
) -> ClassificationSection:
    """Section creuse : les deux parois sont des parois internes.

    La largeur droite conventionnelle d'une paroi de profil creux formé à
    chaud vaut c = largeur − 3t, le rayon extérieur étant pris à 2t.
    """
    c_ame = profil.h - 3.0 * profil.tw
    c_semelle = profil.b - 3.0 * profil.tf
    elancement_ame = c_ame / profil.tw
    elancement_semelle = c_semelle / profil.tf

    alpha, psi = _alpha_et_psi(profil, fy, N_Ed, My_Ed, c_ame)
    classe_ame = _classe_ame(elancement_ame, eps, alpha, psi)

    # Semelle d'un profil creux : paroi interne uniformément comprimée.
    if elancement_semelle <= 33.0 * eps:
        classe_semelle = 1
    elif elancement_semelle <= 38.0 * eps:
        classe_semelle = 2
    elif elancement_semelle <= 42.0 * eps:
        classe_semelle = 3
    else:
        classe_semelle = 4

    return ClassificationSection(
        classe=max(classe_ame, classe_semelle),
        classe_ame=classe_ame,
        classe_semelle=classe_semelle,
        epsilon=eps,
        elancement_ame=elancement_ame,
        elancement_semelle=elancement_semelle,
        alpha=alpha,
    )
