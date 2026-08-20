"""Confrontation à un exemple de calcul publié.

Source : **steelacademy 2019, Horw, 12 septembre 2019, Dr. Patrick Roman
Schulthess** — « Beispiel: Durchlaufende HEA Stütze », planches 36 à 39, et la
table de températures critiques pour éléments comprimés à l_k,fi = 0,5·L_k0
qui l'accompagne.

C'est la première référence **externe** du projet : jusqu'ici la validation ne
reposait que sur des recoupements internes (voir ``docs/validation.md``).

Deux conventions différentes pour le degré d'utilisation
--------------------------------------------------------

L'exemple suisse et l'EN 1993-1-2 n'entrent pas par la même porte :

* la **table SZS** se lit avec μ₀ et λ̄₀ calculés à **température ambiante**,
  donc avec la longueur de flambement L_k0 ; le facteur 0,5 de la longueur
  d'incendie est incorporé dans la table elle-même ;
* l'**EN 1993-1-2 §4.2.4** définit μ₀ = E_fi,d / R_fi,d,0 où R_fi,d,0 est la
  résistance à t = 0 **avec les conditions d'appui de l'incendie**, donc avec
  l_fi.

Sur l'exemple, la première voie donne μ₀ = 0,60 et la seconde μ₀ = 0,52. Les
deux conduisent pourtant à la même température critique, à 1 °C près : la
table est construite pour cela. C'est une différence de convention, pas de
résultat, et il faut le savoir avant de comparer un μ₀ affiché par cet outil à
celui d'une note de calcul suisse.
"""

from __future__ import annotations

import pytest

from nommogramme.materiaux.acier import RHO_A, Nuance, k_y
from nommogramme.materiaux.protection import Protection
from nommogramme.mecanique.actions import CasDeCharge
from nommogramme.mecanique.resistances import (
    alpha_flambement_feu,
    chi_fi,
    elancement_reduit,
    elancement_reduit_theta,
)
from nommogramme.nomogramme.temperature_critique import temperature_critique
from nommogramme.nomogramme.verification import verifier
from nommogramme.profils import Exposition, charger_csv, facteur_massivete
from nommogramme.thermique import echauffement
from nommogramme.unites import minutes

_FY = 235e6

# Table SZS : θ_crit [°C] pour éléments comprimés, l_k,fi = 0,5·L_k0.
# Lignes : μ_fi,0 à température ambiante. Colonnes : λ̄₀ à température ambiante.
_ELANCEMENTS = (0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0)
_TABLE_SZS: dict[float, tuple[int, ...]] = {
    0.20: (732, 741, 752, 764, 778, 791, 805, 827, 845, 859),
    0.25: (696, 701, 713, 728, 744, 759, 773, 784, 793, 802),
    0.30: (676, 682, 689, 695, 709, 726, 741, 753, 763, 771),
    0.35: (656, 663, 672, 681, 690, 698, 710, 724, 734, 743),
    0.40: (636, 645, 654, 665, 676, 685, 692, 697, 703, 712),
    0.45: (617, 626, 637, 650, 662, 673, 681, 687, 691, 694),
    0.50: (597, 607, 620, 634, 648, 660, 669, 676, 681, 685),
    0.55: (582, 591, 603, 619, 634, 647, 658, 665, 671, 675),
    0.60: (567, 577, 589, 603, 620, 635, 646, 655, 661, 666),
    0.65: (552, 563, 576, 591, 606, 622, 635, 644, 651, 656),
    0.70: (537, 549, 563, 579, 594, 609, 623, 633, 641, 647),
}


def _mu_0_incendie(mu_0_ambiant: float, lambda_0: float) -> float:
    """Convertit un μ₀ « ambiant » en μ₀ au sens du §4.2.4.

    Le même effort rapporté à la résistance calculée avec l_fi = 0,5·L au lieu
    de L : μ₀,fi = μ₀,ambiant · χ(λ̄₀) / χ(0,5·λ̄₀).
    """
    return mu_0_ambiant * chi_fi(lambda_0, _FY) / chi_fi(0.5 * lambda_0, _FY)


def _theta_par_verification_croisee(mu_0_ambiant: float, lambda_0: float) -> float:
    """Température annulant la marge du taux complet, avec l_fi = 0,5·L.

    Reproduit ce que fait ``verification._temperature_critique_exacte`` sur un
    élément purement comprimé, sans passer par un profilé réel : l'effort est
    exprimé en fraction de A·f_y, ce qui rend le résultat indépendant de la
    section.
    """
    effort_relatif = mu_0_ambiant * chi_fi(lambda_0, _FY)
    lambda_fi = 0.5 * lambda_0

    bas, haut = 20.0, 1200.0
    for _ in range(200):
        milieu = 0.5 * (bas + haut)
        resistance = chi_fi(elancement_reduit_theta(lambda_fi, milieu), _FY) * k_y(milieu)
        if resistance < effort_relatif:
            haut = milieu
        else:
            bas = milieu
        if haut - bas < 0.05:
            break
    return 0.5 * (bas + haut)


@pytest.fixture(scope="module")
def profil():
    return charger_csv()["HEA300"]


@pytest.fixture(scope="module")
def protection():
    return Protection.depuis_catalogue("plaques_silicate", d_p=0.020)


def _points_exploitables():
    for mu_0, temperatures in _TABLE_SZS.items():
        for lambda_0, reference in zip(_ELANCEMENTS, temperatures):
            if 0.013 <= _mu_0_incendie(mu_0, lambda_0) < 1.0:
                yield mu_0, lambda_0, reference


class TestTableDesTemperaturesCritiques:
    """60 points de la table SZS, confrontés aux deux voies de l'outil."""

    def test_la_verification_croisee_reproduit_la_table(self) -> None:
        ecarts = [
            abs(_theta_par_verification_croisee(mu_0, lambda_0) - reference)
            for mu_0, lambda_0, reference in _points_exploitables()
        ]
        assert len(ecarts) >= 55, "trop peu de points exploitables"
        assert max(ecarts) < 5.0, f"écart maximal de {max(ecarts):.0f} °C"
        assert sum(ecarts) / len(ecarts) < 2.0

    def test_l_equation_422_derive_avec_l_elancement(self) -> None:
        """Le défaut connu de l'éq. (4.22), mesuré contre une référence externe.

        Elle suppose que la résistance décroît comme k_y,θ seul. Aux faibles
        élancements c'est vrai et l'accord est bon ; dès que le flambement
        pèse, χ_fi chute en plus et l'équation devient optimiste.

        Ce n'est pas un seuil qui décrit ce comportement, mais une tendance :
        l'écart moyen croît de façon **monotone** avec λ̄₀, de −2 °C à +35 °C
        sur les dix colonnes de la table. C'est cette monotonie qu'on teste,
        elle porte le mécanisme ; un seuil unique n'aurait fait que constater
        une valeur.
        """
        par_elancement: dict[float, list[float]] = {}
        for mu_0, lambda_0, reference in _points_exploitables():
            ecart = temperature_critique(_mu_0_incendie(mu_0, lambda_0)) - reference
            par_elancement.setdefault(lambda_0, []).append(ecart)

        moyennes = [
            sum(par_elancement[lambda_0]) / len(par_elancement[lambda_0])
            for lambda_0 in sorted(par_elancement)
        ]
        assert moyennes == sorted(moyennes), (
            "l'écart devrait croître avec l'élancement, obtenu : "
            + ", ".join(f"{m:+.0f}" for m in moyennes)
        )
        assert moyennes[0] < 0.0, "l'éq. (4.22) devrait être neutre à faible élancement"
        assert moyennes[-1] > 30.0, "la dérive attendue aux grands élancements a disparu"

    @pytest.mark.parametrize("mu_0", sorted(_TABLE_SZS))
    def test_ligne_par_ligne(self, mu_0: float) -> None:
        for lambda_0, reference in zip(_ELANCEMENTS, _TABLE_SZS[mu_0]):
            if not 0.013 <= _mu_0_incendie(mu_0, lambda_0) < 1.0:
                continue
            obtenu = _theta_par_verification_croisee(mu_0, lambda_0)
            assert obtenu == pytest.approx(reference, abs=5.0), (
                f"μ₀ = {mu_0}, λ̄₀ = {lambda_0} : {obtenu:.0f} °C "
                f"contre {reference} °C dans la table SZS"
            )


class TestExempleHEA300:
    """« Durchlaufende HEA Stütze », planches 36 à 39.

    HEA 300 en S235, encaissée de plaques fibres-silicate de calcium de 20 mm,
    N_Ed,fi = 1205 kN, L_k0 = 3,0 m, l_k,fi = 0,5·L_k0.
    """

    def test_dimensions_du_catalogue(self, profil) -> None:
        assert profil.A == pytest.approx(11300e-6, rel=1e-3)
        assert profil.h == pytest.approx(0.290)
        assert profil.b == pytest.approx(0.300)
        assert profil.iz == pytest.approx(0.0749, rel=1e-3)

    def test_facteur_d_imperfection(self) -> None:
        assert alpha_flambement_feu(_FY) == pytest.approx(0.65, abs=0.005)

    def test_elancement_reduit(self, profil) -> None:
        """λ̄₀ = 0,427, avec la longueur à température ambiante."""
        assert elancement_reduit(3.0, profil.iz, _FY) == pytest.approx(0.427, abs=0.002)

    def test_resistance_au_flambement_a_20_degres(self, profil) -> None:
        """χ_fi = 0,756 et N_b,fi,0,Rd ≅ 2010 kN."""
        lambda_0 = elancement_reduit(3.0, profil.iz, _FY)
        assert chi_fi(lambda_0, _FY) == pytest.approx(0.756, abs=0.002)
        resistance = chi_fi(lambda_0, _FY) * profil.A * _FY
        assert resistance / 1e3 == pytest.approx(2010, rel=0.005)

    def test_degre_utilisation_convention_szs(self, profil) -> None:
        """μ_fi = 1205 / 2010 = 0,60, convention à température ambiante."""
        lambda_0 = elancement_reduit(3.0, profil.iz, _FY)
        resistance = chi_fi(lambda_0, _FY) * profil.A * _FY
        assert 1205e3 / resistance == pytest.approx(0.60, abs=0.005)

    def test_facteur_de_massivete(self, profil) -> None:
        """A_p/V = 2(b+h)/A = 104 m⁻¹ pour un encaissement sur quatre faces."""
        assert facteur_massivete(profil, Exposition.CAISSON_4_FACES) == pytest.approx(
            104, abs=1
        )

    def test_proprietes_de_la_protection(self, protection) -> None:
        """steeldoc tec 02, Abb. 50."""
        assert protection.lambda_p == pytest.approx(0.15)
        assert protection.c_p == pytest.approx(1200.0)
        assert protection.rho_p == pytest.approx(600.0)

    def test_parametre_phi(self, profil, protection) -> None:
        """φ = 0,318 dans l'exemple, avec c_a pris à 600 J/kg·K.

        Le nomogramme graphique fige c_a à une valeur conventionnelle, là où
        l'intégration pas à pas la réévalue à chaque instant. L'écart entre
        les deux φ n'est donc pas une erreur, mais la trace de cette
        différence de méthode.
        """
        Ap_sur_V = facteur_massivete(profil, Exposition.CAISSON_4_FACES)
        phi_convention = (
            protection.c_p * protection.d_p * protection.rho_p / (600.0 * RHO_A)
        ) * Ap_sur_V
        assert phi_convention == pytest.approx(0.318, abs=0.005)

    def test_temperature_critique(self, profil, protection) -> None:
        """θ_crit = 580 °C lu dans la table."""
        cas = CasDeCharge(N_fi_Ed=1205e3, L=3.0, l_fi_y=1.5, l_fi_z=1.5)
        resultat = verifier(
            profil=profil, nuance=Nuance.S235,
            cas=cas, exposition=Exposition.CAISSON_4_FACES,
            duree_requise_min=90, protection=protection,
        )
        assert resultat.theta_cr == pytest.approx(580, abs=5)

    def test_duree_de_resistance_au_feu(self, profil, protection) -> None:
        """111 min lus sur le nomogramme, φ pris en compte.

        L'exemple donne deux lectures : 100 min en négligeant φ, 111 min en en
        tenant compte. L'intégration de l'éq. (4.27) doit retrouver la
        seconde.
        """
        resultat = echauffement(
            profil, Exposition.CAISSON_4_FACES, minutes(240), protection=protection
        )
        duree = resultat.minutes_pour_atteindre(580.0)
        assert duree is not None
        assert duree == pytest.approx(111, abs=5), (
            f"{duree:.0f} min contre 111 min lus sur le nomogramme"
        )
