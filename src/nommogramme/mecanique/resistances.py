"""Résistances de l'élément en situation d'incendie.

Référence : EN 1993-1-2 §4.2.3.

Deux effets se superposent quand la température monte :

* la limite d'élasticité efficace décroît, par k_y,θ ;
* l'élancement réduit **augmente**, par λ̄_θ = λ̄·√(k_y,θ/k_E,θ), le module
  chutant plus vite que la limite d'élasticité. À 600 °C, √(0,470/0,310) =
  1,23, soit 23 % d'élancement en plus.

C'est ce second effet que l'équation (4.22) ne capte pas, et la raison pour
laquelle la vérification par les résistances complètes n'est pas optionnelle
dès que le flambement gouverne.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..materiaux.acier import E_A, Nuance, k_E, k_y, limite_elasticite
from ..profils.modele import Forme, Profil

__all__ = [
    "G_ACIER",
    "alpha_flambement_feu",
    "elancement_reduit",
    "elancement_reduit_theta",
    "chi_fi",
    "elancement_reduit_LT",
    "chi_LT_fi",
    "moment_critique_elastique",
    "N_fi_Rd_traction",
    "N_b_fi_Rd",
    "M_fi_Rd",
    "M_b_fi_Rd",
    "V_fi_Rd",
    "Resistances",
]


G_ACIER = 81e9
"""Module de cisaillement de l'acier [Pa], E/(2(1+ν)) avec ν = 0,3."""

_NU = 0.3


def alpha_flambement_feu(fy: float) -> float:
    """Facteur d'imperfection à chaud [-].

    EN 1993-1-2 éq. (4.8) : α = 0,65·√(235/f_y).

    Une courbe de flambement unique remplace à chaud les courbes a, b, c et d
    de l'EN 1993-1-1.
    """
    return 0.65 * math.sqrt(235e6 / fy)


def elancement_reduit(longueur_flambement: float, rayon_giration: float, fy: float) -> float:
    """Élancement réduit à 20 °C [-].

    λ̄ = (L_cr / i) / λ₁ avec λ₁ = π·√(E/f_y).
    """
    if rayon_giration <= 0.0:
        raise ValueError("Rayon de giration nul ou négatif.")
    lambda_1 = math.pi * math.sqrt(E_A / fy)
    return (longueur_flambement / rayon_giration) / lambda_1


def elancement_reduit_theta(lambda_barre: float, theta: float) -> float:
    """Élancement réduit à la température θ [-].

    EN 1993-1-2 éq. (4.9) : λ̄_θ = λ̄ · √(k_y,θ / k_E,θ).
    """
    ke = k_E(theta)
    if ke <= 0.0:
        return float("inf")
    return lambda_barre * math.sqrt(k_y(theta) / ke)


def chi_fi(lambda_barre_theta: float, fy: float) -> float:
    """Coefficient de réduction pour le flambement par flexion [-].

    EN 1993-1-2 éq. (4.6) et (4.7) :

        φ_θ  = ½·[1 + α·λ̄_θ + λ̄_θ²]
        χ_fi = 1 / (φ_θ + √(φ_θ² − λ̄_θ²))
    """
    if not math.isfinite(lambda_barre_theta):
        return 0.0
    alpha = alpha_flambement_feu(fy)
    phi = 0.5 * (1.0 + alpha * lambda_barre_theta + lambda_barre_theta**2)
    racine = phi**2 - lambda_barre_theta**2
    if racine <= 0.0:
        return min(1.0 / phi, 1.0)
    return min(1.0 / (phi + math.sqrt(racine)), 1.0)


def moment_critique_elastique(
    profil: Profil, longueur: float, C1: float = 1.0
) -> float:
    """Moment critique élastique de déversement [N·m].

    Section doublement symétrique, charge appliquée au centre de cisaillement,
    appuis à fourche :

        M_cr = C1 · (π²·E·I_z / L²) · √( I_w/I_z + L²·G·I_t / (π²·E·I_z) )

    Le catalogue SZS ne tabule pas la constante de gauchissement I_w ; elle est
    approchée par la relation classique des sections en I doublement
    symétriques, I_w ≈ I_z·(h − t_f)²/4.

    ``C1`` dépend du diagramme de moment ; sa valeur par défaut de 1,0
    correspond au moment constant, le cas le plus défavorable.
    """
    if longueur <= 0.0:
        return float("inf")
    if profil.forme is Forme.PROFIL_CREUX:
        # La rigidité de torsion d'un profil creux rend le déversement
        # inopérant en pratique.
        return float("inf")

    I_t = profil.It if profil.It is not None else 0.0
    I_w = profil.Iz * (profil.h - profil.tf) ** 2 / 4.0

    terme_euler = math.pi**2 * E_A * profil.Iz / longueur**2
    sous_racine = I_w / profil.Iz + (
        longueur**2 * G_ACIER * I_t / (math.pi**2 * E_A * profil.Iz)
    )
    return C1 * terme_euler * math.sqrt(sous_racine)


def elancement_reduit_LT(
    profil: Profil, fy: float, longueur: float, C1: float = 1.0, W: float | None = None
) -> float:
    """Élancement réduit de déversement à 20 °C [-].

    λ̄_LT = √(W_pl,y · f_y / M_cr).
    """
    M_cr = moment_critique_elastique(profil, longueur, C1)
    if not math.isfinite(M_cr) or M_cr <= 0.0:
        return 0.0
    module = W if W is not None else profil.Wply
    return math.sqrt(module * fy / M_cr)


def chi_LT_fi(lambda_barre_LT: float, theta: float, fy: float) -> float:
    """Coefficient de réduction pour le déversement à chaud [-].

    EN 1993-1-2 §4.2.3.3(4). Même forme que χ_fi, avec l'élancement de
    déversement corrigé de la température :

        λ̄_LT,θ,com = λ̄_LT · √(k_y,θ,com / k_E,θ,com)

    En température uniforme, la semelle comprimée est à la température de la
    section, donc k_y,θ,com = k_y,θ.
    """
    if lambda_barre_LT <= 0.0:
        return 1.0
    return chi_fi(elancement_reduit_theta(lambda_barre_LT, theta), fy)


# --- résistances de section et d'élément -------------------------------------


def N_fi_Rd_traction(profil: Profil, fy: float, theta: float, gamma_M_fi: float) -> float:
    """Résistance à la traction [N].

    EN 1993-1-2 éq. (4.3) : N_fi,θ,Rd = k_y,θ · A · f_y / γ_M,fi.
    """
    return k_y(theta) * profil.A * fy / gamma_M_fi


def N_b_fi_Rd(
    profil: Profil,
    fy: float,
    theta: float,
    lambda_barre: float,
    gamma_M_fi: float,
) -> float:
    """Résistance au flambement par flexion [N].

    EN 1993-1-2 éq. (4.5) : N_b,fi,t,Rd = χ_fi · A · k_y,θ · f_y / γ_M,fi.
    """
    chi = chi_fi(elancement_reduit_theta(lambda_barre, theta), fy)
    return chi * profil.A * k_y(theta) * fy / gamma_M_fi


def M_fi_Rd(
    module_plastique: float,
    fy: float,
    theta: float,
    gamma_M_fi: float,
    kappa_1: float = 1.0,
    kappa_2: float = 1.0,
) -> float:
    """Moment résistant de section [N·m].

    EN 1993-1-2 §4.2.3.3, classes 1 et 2 :

        M_fi,t,Rd = (W_pl · k_y,θ · f_y / γ_M,fi) · 1/(κ₁·κ₂)

    Les facteurs d'adaptation traduisent le fait qu'une section partiellement
    protégée par une dalle est plus froide que ne le suppose l'hypothèse de
    température uniforme :

    * κ₁ = 1,00 exposée sur quatre faces ; 0,70 sur trois faces avec dalle
      béton ; 0,85 sur trois faces avec dalle mixte ;
    * κ₂ = 0,85 aux appuis d'une poutre hyperstatique ; 1,00 sinon.
    """
    if kappa_1 <= 0.0 or kappa_2 <= 0.0:
        raise ValueError("Les facteurs d'adaptation doivent être positifs.")
    return module_plastique * k_y(theta) * fy / (gamma_M_fi * kappa_1 * kappa_2)


def M_b_fi_Rd(
    profil: Profil,
    fy: float,
    theta: float,
    lambda_barre_LT: float,
    gamma_M_fi: float,
    module_plastique: float | None = None,
) -> float:
    """Moment résistant au déversement [N·m].

    EN 1993-1-2 éq. (4.11) :
        M_b,fi,t,Rd = χ_LT,fi · W_pl,y · k_y,θ · f_y / γ_M,fi
    """
    module = module_plastique if module_plastique is not None else profil.Wply
    return (
        chi_LT_fi(lambda_barre_LT, theta, fy)
        * module
        * k_y(theta)
        * fy
        / gamma_M_fi
    )


def V_fi_Rd(profil: Profil, fy: float, theta: float, gamma_M_fi: float) -> float | None:
    """Résistance à l'effort tranchant [N].

    EN 1993-1-2 §4.2.3.3(6) : V_fi,t,Rd = k_y,θ · A_v · f_y / (√3 · γ_M,fi).

    Renvoie ``None`` si l'aire de cisaillement n'est pas tabulée — le
    catalogue SZS ne la donne pas pour les profils creux.
    """
    if profil.Av is None:
        return None
    return k_y(theta) * profil.Av * fy / (math.sqrt(3.0) * gamma_M_fi)


@dataclass(frozen=True, slots=True)
class Resistances:
    """Jeu complet de résistances à une température donnée."""

    theta: float
    fy: float
    gamma_M_fi: float
    k_y_theta: float
    k_E_theta: float

    N_Rd: float
    """Résistance axiale [N] : flambement en compression, section en traction.

    En compression, χ_min = min(χ_y, χ_z) est retenu, comme au dénominateur du
    premier terme de l'éq. (4.21a).
    """
    N_Rd_z: float
    """Résistance axiale sur le seul χ_z [N], dénominateur de l'éq. (4.21b)."""
    My_Rd: float
    Mz_Rd: float
    """Moments résistants de section [N·m]."""
    Mb_Rd: float
    """Moment résistant au déversement [N·m]."""
    V_Rd: float | None

    chi_y_fi: float
    chi_z_fi: float
    chi_LT_fi: float
    lambda_y_theta: float
    lambda_z_theta: float
    lambda_LT_theta: float


def resistances_a(
    profil: Profil,
    nuance: Nuance,
    theta: float,
    lambda_y: float,
    lambda_z: float,
    lambda_LT: float,
    gamma_M_fi: float,
    comprime: bool,
    kappa_1: float = 1.0,
    kappa_2: float = 1.0,
    module_y: float | None = None,
    module_z: float | None = None,
) -> Resistances:
    """Assemble toutes les résistances de l'élément à la température θ."""
    fy = limite_elasticite(nuance, profil.tf)
    Wy = module_y if module_y is not None else profil.Wply
    Wz = module_z if module_z is not None else profil.Wplz

    l_y_theta = elancement_reduit_theta(lambda_y, theta)
    l_z_theta = elancement_reduit_theta(lambda_z, theta)
    l_LT_theta = elancement_reduit_theta(lambda_LT, theta)

    chi_y = chi_fi(l_y_theta, fy)
    chi_z = chi_fi(l_z_theta, fy)
    chi_LT = chi_fi(l_LT_theta, fy) if lambda_LT > 0.0 else 1.0

    resistance_plastique = profil.A * k_y(theta) * fy / gamma_M_fi
    if comprime:
        N_Rd = min(chi_y, chi_z) * resistance_plastique
    else:
        N_Rd = N_fi_Rd_traction(profil, fy, theta, gamma_M_fi)

    return Resistances(
        theta=theta,
        fy=fy,
        gamma_M_fi=gamma_M_fi,
        k_y_theta=k_y(theta),
        k_E_theta=k_E(theta),
        N_Rd=N_Rd,
        N_Rd_z=chi_z * resistance_plastique,
        My_Rd=M_fi_Rd(Wy, fy, theta, gamma_M_fi, kappa_1, kappa_2),
        Mz_Rd=M_fi_Rd(Wz, fy, theta, gamma_M_fi, kappa_1, kappa_2),
        Mb_Rd=chi_LT * Wy * k_y(theta) * fy / gamma_M_fi,
        V_Rd=V_fi_Rd(profil, fy, theta, gamma_M_fi),
        chi_y_fi=chi_y,
        chi_z_fi=chi_z,
        chi_LT_fi=chi_LT,
        lambda_y_theta=l_y_theta,
        lambda_z_theta=l_z_theta,
        lambda_LT_theta=l_LT_theta,
    )
