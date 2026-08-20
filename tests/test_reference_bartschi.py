"""Deuxième référence externe : un poteau **non protégé**.

Source : **steelacademy 2019, Lausanne, 25 septembre 2019, Dr. Roland
Bärtschi** — « Exemple d'application : poteau en acier non revêtu »,
planches 22, 23 et suivantes.

La première référence du projet (``test_reference_szs.py``) portait sur un
poteau *protégé*. Celle-ci comble le trou complémentaire : elle valide la
chaîne de l'élément **nu**, c'est-à-dire l'équation (4.25) et le flux net de
l'EN 1991-1-2, que le cas protégé ne sollicitait pas.

L'énoncé
--------

HEB 360 en S355, longueur 4,00 m, bi-articulé donc l_fi = 4,00 m. Quelle
capacité portante reste-t-il après 30 minutes de feu ISO ?

La planche lit θ_crit = 770 °C sur le nomogramme SZS, puis en déduit
N_b,fi,t,Rd = 537 kN.

Le facteur d'ombre, seul point de divergence
--------------------------------------------

La lecture du nomogramme se fait à A_m/V = 102 m⁻¹, la valeur géométrique
brute du HEB 360 sous exposition sur quatre faces. Le facteur d'ombre du
§4.2.5.1(2) n'est pas appliqué : avec lui, l'entrée serait
k_sh · A_m/V = 0,642 · 102 = 65,6 m⁻¹.

C'est une différence de convention, et elle n'est pas anodine :

===========================  ==========  =============
entrée                       θ à 30 min  N_b,fi,t,Rd
===========================  ==========  =============
102 m⁻¹ (planche)              770 °C      537 kN
65,6 m⁻¹ (§4.2.5.1(2))         730 °C      676 kN
===========================  ==========  =============

La planche est donc **conservative de 20 %** sur la capacité résiduelle. Cet
outil applique k_sh, conformément au texte de la norme. Les tests ci-dessous
vérifient les deux voies : que le modèle thermique reproduit la lecture de la
planche quand on lui donne la même entrée, et que l'outil tel qu'il est livré
produit bien l'autre valeur.
"""

from __future__ import annotations

import math

import pytest

from nommogramme.materiaux.acier import k_E, k_y
from nommogramme.mecanique.resistances import (
    alpha_flambement_feu,
    chi_fi,
    elancement_reduit,
    elancement_reduit_theta,
)
from nommogramme.profils import Exposition, charger_csv, facteur_massivete
from nommogramme.profils.geometrie import facteur_ombre
from nommogramme.thermique import echauffement
from nommogramme.unites import minutes

_FY = 355e6
_L_FI = 4.0
_THETA_PLANCHE = 770.0


@pytest.fixture(scope="module")
def profil():
    return charger_csv()["HEB360"]


class TestGeometrieEtElancement:
    """Les grandeurs d'entrée de la planche, avant tout calcul de feu."""

    def test_section_et_inertie(self, profil) -> None:
        """A = 18 060 mm², I_z = 1,01·10⁸ mm⁴, i_z = 74,8 mm."""
        assert profil.A * 1e6 == pytest.approx(18060, rel=0.005)
        assert profil.Iz * 1e12 == pytest.approx(1.01e8, rel=0.005)
        assert profil.iz * 1e3 == pytest.approx(74.8, abs=0.2)

    def test_elancement_reduit(self, profil) -> None:
        """λ̄₀ = 0,70 pour l_fi = 4,00 m."""
        assert elancement_reduit(_L_FI, profil.iz, _FY) == pytest.approx(0.70, abs=0.005)

    def test_elancement_de_reference(self) -> None:
        """λ_E = π·√(E/f_y) = 76,4."""
        assert math.pi * math.sqrt(210e9 / _FY) == pytest.approx(76.4, abs=0.1)

    def test_facteur_alpha(self) -> None:
        """α = 0,65·√(235/355) = 0,529."""
        assert alpha_flambement_feu(_FY) == pytest.approx(0.529, abs=0.001)

    def test_facteur_de_massivete(self, profil) -> None:
        """A_m/V = 102 m⁻¹, valeur de la table SZS de la planche 23."""
        Am_sur_V = facteur_massivete(profil, Exposition.CONTOUR_4_FACES)
        assert Am_sur_V == pytest.approx(102, abs=1)


class TestReductionsAChaud:
    """Le tableau 3.1 reproduit sur la planche, interpolé à 770 °C."""

    def test_k_y(self) -> None:
        assert k_y(_THETA_PLANCHE) == pytest.approx(0.146, abs=0.001)

    def test_k_E(self) -> None:
        assert k_E(_THETA_PLANCHE) == pytest.approx(0.102, abs=0.001)


class TestFlambementA770:
    """χ_fi et la capacité résiduelle, à la température lue par la planche."""

    def test_elancement_a_chaud(self, profil) -> None:
        """λ̄_θ = λ̄₀·√(k_y/k_E) = 0,838."""
        lambda_0 = elancement_reduit(_L_FI, profil.iz, _FY)
        assert elancement_reduit_theta(lambda_0, _THETA_PLANCHE) == pytest.approx(
            0.838, abs=0.003
        )

    def test_chi_fi(self, profil) -> None:
        """χ_fi = 0,574 — donc φ_θ = 1,072."""
        lambda_0 = elancement_reduit(_L_FI, profil.iz, _FY)
        lambda_theta = elancement_reduit_theta(lambda_0, _THETA_PLANCHE)
        chi = chi_fi(lambda_theta, _FY)
        assert chi == pytest.approx(0.574, abs=0.002)

        alpha = alpha_flambement_feu(_FY)
        phi = 0.5 * (1.0 + alpha * lambda_theta + lambda_theta**2)
        assert phi == pytest.approx(1.072, abs=0.005)

    def test_capacite_portante_residuelle(self, profil) -> None:
        """N_b,fi,t,Rd = χ_fi·A·k_y,θ·f_y/γ_M,fi = 537 kN, γ_M,fi = 1,0."""
        lambda_0 = elancement_reduit(_L_FI, profil.iz, _FY)
        lambda_theta = elancement_reduit_theta(lambda_0, _THETA_PLANCHE)
        N = chi_fi(lambda_theta, _FY) * profil.A * k_y(_THETA_PLANCHE) * _FY
        assert N / 1e3 == pytest.approx(537, rel=0.01), (
            f"{N / 1e3:.0f} kN contre 537 kN sur la planche"
        )


class TestEchauffementNonProtege:
    """L'équation (4.25) confrontée à la lecture du nomogramme."""

    def test_la_lecture_de_la_planche_est_reproduite(self, profil, monkeypatch) -> None:
        """À l'entrée de la planche — k_sh écarté — on retrouve 770 °C.

        Le facteur d'ombre est neutralisé ici pour reproduire *exactement* la
        convention de la planche. C'est la seule manière de comparer le modèle
        thermique lui-même, sans que la différence de convention ne masque le
        résultat.
        """
        monkeypatch.setattr(
            "nommogramme.thermique.evolution.facteur_ombre",
            lambda *a, **k: 1.0,
        )
        resultat = echauffement(profil, Exposition.CONTOUR_4_FACES, minutes(30))
        assert resultat.k_sh == 1.0
        assert resultat.temperature_finale == pytest.approx(770, abs=3), (
            f"{resultat.temperature_finale:.0f} °C contre 770 °C lus sur le nomogramme"
        )

    def test_le_facteur_d_ombre_vaut_bien_0_64(self, profil) -> None:
        """k_sh = 0,9·(A_m/V)_caisson/(A_m/V) = 0,9·73/102."""
        k = facteur_ombre(profil, Exposition.CONTOUR_4_FACES)
        assert k == pytest.approx(0.642, abs=0.005)

    def test_l_outil_livre_applique_le_facteur_d_ombre(self, profil) -> None:
        """Sans neutralisation, l'outil donne 730 °C : 40 °C de moins.

        Ce n'est pas un désaccord avec la référence mais l'application du
        §4.2.5.1(2), que la planche ne fait pas. Le test fige l'écart pour
        qu'il reste visible.
        """
        resultat = echauffement(profil, Exposition.CONTOUR_4_FACES, minutes(30))
        assert resultat.temperature_finale == pytest.approx(730, abs=3)
        assert _THETA_PLANCHE - resultat.temperature_finale == pytest.approx(40, abs=5)

    def test_l_ecart_de_convention_coute_20_pourcent_de_capacite(self, profil) -> None:
        """730 °C au lieu de 770 °C, c'est 676 kN au lieu de 537 kN."""
        resultat = echauffement(profil, Exposition.CONTOUR_4_FACES, minutes(30))
        theta = resultat.temperature_finale
        lambda_0 = elancement_reduit(_L_FI, profil.iz, _FY)
        N = chi_fi(elancement_reduit_theta(lambda_0, theta), _FY) * profil.A * k_y(theta) * _FY
        assert N / 1e3 == pytest.approx(676, rel=0.02)
        assert N / 537e3 == pytest.approx(1.26, abs=0.05)
