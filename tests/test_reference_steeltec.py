"""Les huit exemples chiffrés de la documentation SZS — la source primaire.

Source : **SZS steeltec 02:2015, « Protection incendie des structures »,
chapitre 3 « Application du nomogramme », pages 31 à 33**, exemples A à H.
Planches fournies par l'utilisateur.

C'est le document dont les supports steelacademy 2019 sont tirés : l'exemple A
est mot pour mot celui des planches de Horw déjà reproduites dans
``test_reference_szs.py``. Le reste est nouveau, et couvre bien plus large :

===  =========================================  ===================================
Ex.  Cas                                        Ce qu'il met en jeu
===  =========================================  ===================================
A    HEA 300 revêtu, caisson silicate 20 mm     éq. (4.27), φ, délai d'évaporation
B    Solive IPE 300 revêtue, R90                **flexion**, κ, dimensionnement d_p
C    Poutre âme mince classe 4, R60             θ_crit conventionnel SIA 263
D    Rond plein ⌀280 continu, l_fi = 0,5·L      élément nu très massif
E    Rond plein ⌀280 articulé, l_fi = 1,0·L     idem, autre longueur de flambement
F    Poutre mixte IPE 270, R60                  **flexion**, κ, φ, peinture mince
G    HEB 340 nu, l_fi = 0,7·L                   **facteur d'ombre**, durée nue
H    Le même, peinture intumescente             A_m/V brut pour les tables produit
===  =========================================  ===================================

Deux acquis majeurs
-------------------

**1. La flexion est enfin couverte.** Les exemples B et F entrent dans le
nomogramme avec μ_fi,t et κ, et le document donne θ_crit à l'unité. Jusqu'ici
aucune référence externe ne touchait à autre chose que la compression.

Ils fixent aussi la **convention** : le nomogramme se lit avec le produit
μ₀ = μ_fi,t · κ. L'exemple F l'écrit noir sur blanc — « pour
μ₀ = μ_fi,t · κ = 0,49 · 0,7 = 0,34 cette formule donne Θ_crit = 643 °C ».

**2. Le facteur d'ombre est tranché.** Le support steelacademy de Lausanne lit
le nomogramme sans appliquer k_sh (voir ``test_reference_bartschi.py``), ce qui
laissait ouverte la question de savoir si la SZS l'intègre déjà dans ses
courbes. Elle ne l'intègre pas : l'exemple G calcule explicitement

    [A_m/V]_sh = [A_m/V] · k_sh    avec    k_sh = 0,9 · [A_m/V]_b / [A_m/V]

soit [A_m/V]_sh = 0,9 · [A_m/V]_b = 0,9 · 74 = 67 m⁻¹ pour le HEB 340, et lit
la durée sur cette valeur. C'est exactement ce que fait cet outil. La planche
de Lausanne simplifiait, du côté sûr.

Une coquille du document
------------------------

L'exemple A écrit le délai d'évaporation
t_v = 3·600·0,025²/(5·0,15) = 1 minute, alors que son propre énoncé porte
d_p = 20 mm. Avec 0,025 le résultat serait 1,5 min ; avec 0,020 il vaut
0,96 min, soit bien la minute annoncée. C'est le 0,025 imprimé qui est faux.
"""

from __future__ import annotations

import math

import pytest

from nommogramme.materiaux.acier import RHO_A, Nuance, k_y
from nommogramme.materiaux.protection import Protection
from nommogramme.mecanique.actions import CasDeCharge
from nommogramme.mecanique.resistances import chi_fi, elancement_reduit_theta
from nommogramme.nomogramme.temperature_critique import temperature_critique
from nommogramme.nomogramme.verification import Verdict, verifier
from nommogramme.profils import Exposition, charger_csv, facteur_massivete
from nommogramme.profils.geometrie import facteur_massivete_caisson
from nommogramme.thermique import echauffement
from nommogramme.thermique.evolution import _delai_evaporation
from nommogramme.unites import minutes

_FY = 235e6
_E_ACIER = 210e9


@pytest.fixture(scope="module")
def catalogue():
    return charger_csv()


def _lambda_0(longueur_flambement: float, rayon_giration: float) -> float:
    return longueur_flambement / (rayon_giration * math.pi * math.sqrt(_E_ACIER / _FY))


def _theta_par_verification_croisee(mu_0: float, lambda_fi: float, chi_0: float) -> float:
    """θ où χ_fi(λ̄_θ)·k_y(θ) tombe à μ₀·χ_fi(λ̄₀) — le §4.2.3 pris à l'envers."""
    cible = mu_0 * chi_0
    bas, haut = 20.0, 1200.0
    for _ in range(200):
        milieu = 0.5 * (bas + haut)
        if chi_fi(elancement_reduit_theta(lambda_fi, milieu), _FY) * k_y(milieu) < cible:
            haut = milieu
        else:
            bas = milieu
    return 0.5 * (bas + haut)


def _duree_nue(catalogue, profil_nom: str, exposition: Exposition, cible: float) -> float:
    profil = catalogue[profil_nom]
    resultat = echauffement(profil, exposition, minutes(240))
    duree = resultat.minutes_pour_atteindre(cible)
    assert duree is not None
    return duree


# ---------------------------------------------------------------------------
# Lecture de l'axe « profilés protégés »
# ---------------------------------------------------------------------------

_PROFIL_ETALON = "HEB 300"
_EXPO_ETALON = Exposition.CAISSON_4_FACES


def _theta_protege(
    catalogue, massivete_thermique: float, duree_min: float, lambda_p: float = 0.15
) -> float:
    """θ_a à l'échéance pour un (A_p/V)·(λ_p/d_p) donné, à φ = 0.

    Le nomogramme lit les profilés protégés sur ce seul nombre : à φ nul,
    l'éq. (4.27) n'en dépend d'aucun autre. Le profilé porteur est donc
    indifférent, et φ est annulé par une masse volumique d'isolant négligeable.
    """
    profil = catalogue[_PROFIL_ETALON]
    Ap_sur_V = facteur_massivete(profil, _EXPO_ETALON)
    protection = Protection(
        nom="étalon",
        lambda_p=lambda_p,
        rho_p=1e-6,
        c_p=1200.0,
        d_p=lambda_p * Ap_sur_V / massivete_thermique,
        pose="caisson",
    )
    return echauffement(
        profil, _EXPO_ETALON, minutes(duree_min), protection=protection
    ).temperature_finale


def _massivete_thermique_max(
    catalogue, cible: float, duree_min: float, lambda_p: float = 0.15
) -> float:
    bas, haut = 10.0, 30000.0
    for _ in range(70):
        milieu = 0.5 * (bas + haut)
        if _theta_protege(catalogue, milieu, duree_min, lambda_p) > cible:
            haut = milieu
        else:
            bas = milieu
    return 0.5 * (bas + haut)


class TestExempleA_PoteauRevetu:
    """HEA 300 S235, caisson silicate 20 mm, N_Ed,fi = 1205 kN.

    Le détail de cet exemple est déjà couvert par ``test_reference_szs.py``,
    qui l'aborde par les planches steelacademy. Seuls sont repris ici les deux
    points que la source primaire apporte en plus.
    """

    def test_massivete_thermique_a_phi_nul(self, catalogue) -> None:
        """(A_p/V)·(λ_p/d_p) = 104·0,15/0,020 = 780 W/(m³·K), lu à 100 min."""
        assert 104 * 0.15 / 0.020 == pytest.approx(780, abs=1)
        assert _theta_protege(catalogue, 780.0, 100.0) == pytest.approx(580, abs=10)

    def test_massivete_thermique_corrigee_de_phi(self) -> None:
        """φ = 0,318 ramène 780 à 673 W/(m³·K), et 100 min deviennent 111."""
        phi = (1200 * 0.020 * 600) / (600 * RHO_A) * 104
        assert phi == pytest.approx(0.318, abs=0.005)
        assert 780 / (1 + 0.5 * phi) == pytest.approx(673, abs=5)

    def test_delai_d_evaporation(self) -> None:
        """t_v = p·ρ_p·d_p²/(5·λ_p) = 1 minute pour p = 3 %.

        Première confrontation externe de cette formule, jusqu'ici marquée
        « à recouper » dans docs/validation.md. Elle est bien celle de la SZS,
        avec p exprimé **en pourcent** et non en fraction.
        """
        protection = Protection(
            nom="silicate", lambda_p=0.15, rho_p=600.0, c_p=1200.0,
            d_p=0.020, pose="caisson", humidite=3.0,
        )
        assert _delai_evaporation(protection) / 60.0 == pytest.approx(1.0, abs=0.1)


class TestExempleB_SoliveRevetue:
    """IPE 300 S235 fléchie, déversement empêché par la dalle, R90.

    Première référence externe du projet portant sur la **flexion**.
    """

    def test_moment_plastique(self, catalogue) -> None:
        """M_fi,t=0,Rd = W_pl,y·f_y/γ_M,fi = 148 kNm, γ_M,fi = 1,0."""
        profil = catalogue["IPE 300"]
        assert profil.Wply * _FY / 1e3 == pytest.approx(148, rel=0.01)

    def test_temperature_critique(self) -> None:
        """μ_fi,t = 0,456 et κ = 0,7 donnent θ_crit = 654 °C.

        Le nomogramme s'entre avec le produit μ₀ = μ_fi,t·κ = 0,319.
        """
        assert 67.5 / 148 == pytest.approx(0.456, abs=0.001)
        assert temperature_critique(0.456 * 0.7) == pytest.approx(654, abs=2)

    def test_facteur_de_massivete(self, catalogue) -> None:
        """A_p/V = 139 m⁻¹ — caisson, dalle sur la semelle supérieure."""
        profil = catalogue["IPE 300"]
        assert facteur_massivete(profil, Exposition.CAISSON_3_FACES) == pytest.approx(
            139, abs=1
        )

    def test_de_bout_en_bout(self, catalogue) -> None:
        """L'exemple complet passé à ``verifier()``, tel qu'un utilisateur l'écrirait.

        Les tests précédents interrogent les briques une à une ; celui-ci
        vérifie que la chaîne assemblée retrouve les mêmes nombres — μ₀, la
        température critique et le facteur de massiveté — et que les 18 mm du
        document satisfont bien le R90.
        """
        cas = CasDeCharge(My_fi_Ed=67.5e3, L=9.0, maintien_lateral=True)
        resultat = verifier(
            profil=catalogue["IPE 300"], nuance=Nuance.S235, cas=cas,
            exposition=Exposition.CAISSON_3_FACES, duree_requise_min=90,
            protection=Protection.depuis_catalogue("plaques_silicate", d_p=0.018),
            kappa_1=0.7,
        )
        assert resultat.mu_0 == pytest.approx(0.456 * 0.7, abs=0.005)
        assert resultat.theta_cr_nomogramme == pytest.approx(654, abs=2)
        assert resultat.Am_sur_V == pytest.approx(139, abs=1)
        assert resultat.t_fi_d_minutes >= 90.0
        assert resultat.verdict is Verdict.SATISFAIT

    def test_epaisseur_de_revetement(self, catalogue) -> None:
        """Le nomogramme plafonne à 1150 W/(m³·K), d'où d_p ≥ 18 mm."""
        plafond = _massivete_thermique_max(catalogue, 654.0, 90.0)
        assert plafond == pytest.approx(1150, rel=0.03)
        assert 0.15 * 139 / plafond * 1000 == pytest.approx(18, abs=1)


class TestExempleC_AmeMinceClasse4:
    """Poutre composée à âme mince, section de classe 4, R60.

    Confirme la valeur conventionnelle suisse θ_crit = 350 °C pour la classe 4
    et son renvoi — **SIA 263, chiffre 4.8.5.9** —, tous deux marqués
    « à recouper » jusqu'ici.
    """

    def test_epaisseur_de_revetement(self, catalogue) -> None:
        """θ_crit = 350 °C et A_p/V = 200 m⁻¹ donnent d_p ≥ 50 mm."""
        plafond = _massivete_thermique_max(catalogue, 350.0, 60.0)
        assert plafond == pytest.approx(610, rel=0.03)
        assert 0.15 * 200 / plafond * 1000 == pytest.approx(50, abs=2)


class TestExemplesDetE_RondsPleins:
    """Rond plein ⌀ 280 mm, S235, N_Ed,fi = 3000 kN, nu.

    Deux fois le même barreau, deux longueurs de flambement différentes. Le
    couple est instructif : les deux cas ont pratiquement le même effort
    relatif μ₀·χ_fi (0,207), et pourtant θ_crit diffère de 17 °C. Seul
    l'élancement les sépare — c'est précisément ce que la vérification croisée
    capte et que l'équation (4.22), qui ignore λ̄, ne peut pas voir.

    Le profilé n'est pas au catalogue SZS : la géométrie est reprise de
    l'énoncé, A = π·d²/4 et i = d/4.
    """

    A = math.pi * 0.280**2 / 4
    I = 0.280 / 4
    AM_SUR_V = 4 / 0.280

    def test_section_et_rayon_de_giration(self) -> None:
        assert self.A * 1e6 == pytest.approx(61600, rel=0.001)
        assert self.I * 1e3 == pytest.approx(70, abs=0.1)
        assert self.AM_SUR_V == pytest.approx(14, abs=0.3)

    def test_D_poteau_continu(self) -> None:
        """L = 4,0 m, l_fi = 0,5·L : λ̄₀ = 0,609, μ₀ = 0,315, θ_crit = 684 °C."""
        lambda_0 = _lambda_0(4.0, self.I)
        chi_0 = chi_fi(lambda_0, _FY)
        assert lambda_0 == pytest.approx(0.609, abs=0.002)
        assert chi_0 == pytest.approx(0.657, abs=0.002)
        assert chi_0 * self.A * _FY / 1e3 == pytest.approx(9511, rel=0.005)

        mu_0 = 3000e3 / (chi_0 * self.A * _FY)
        assert mu_0 == pytest.approx(0.315, abs=0.002)
        assert _theta_par_verification_croisee(
            mu_0, 0.5 * lambda_0, chi_0
        ) == pytest.approx(684, abs=3)

    def test_E_poteau_articule(self) -> None:
        """L = 3,0 m, l_fi = 1,0·L : λ̄₀ = 0,456, μ₀ = 0,28, θ_crit = 667 °C."""
        lambda_0 = _lambda_0(3.0, self.I)
        chi_0 = chi_fi(lambda_0, _FY)
        assert lambda_0 == pytest.approx(0.456, abs=0.002)
        assert chi_0 == pytest.approx(0.741, abs=0.002)
        assert chi_0 * self.A * _FY / 1e3 == pytest.approx(10726, rel=0.005)

        mu_0 = 3000e3 / (chi_0 * self.A * _FY)
        assert mu_0 == pytest.approx(0.28, abs=0.005)
        assert _theta_par_verification_croisee(mu_0, lambda_0, chi_0) == pytest.approx(
            667, abs=3
        )

    def test_l_elancement_seul_separe_les_deux_cas(self) -> None:
        """Même effort relatif, 17 °C d'écart : la signature du §4.2.3."""
        lambda_D = _lambda_0(4.0, self.I)
        lambda_E = _lambda_0(3.0, self.I)
        effort_D = 3000e3 / (self.A * _FY)
        effort_E = 3000e3 / (self.A * _FY)
        assert effort_D == pytest.approx(effort_E)
        assert _theta_par_verification_croisee(
            effort_D / chi_fi(lambda_D, _FY), 0.5 * lambda_D, chi_fi(lambda_D, _FY)
        ) - _theta_par_verification_croisee(
            effort_E / chi_fi(lambda_E, _FY), lambda_E, chi_fi(lambda_E, _FY)
        ) == pytest.approx(17, abs=4)


class TestExempleF_PoutreMixte:
    """IPE 270 S235, dalle béton, exposée sur trois côtés, R60."""

    def test_temperature_critique(self) -> None:
        """μ_fi,t = 0,49 et κ = 0,7 donnent θ_crit = 643 °C.

        Le document explicite ici la convention d'entrée du nomogramme :
        μ₀ = μ_fi,t · κ = 0,49 · 0,7 = 0,343.
        """
        assert temperature_critique(0.49 * 0.7) == pytest.approx(643, abs=2)

    def test_facteur_de_massivete(self, catalogue) -> None:
        """A_m/V = 197 m⁻¹ pour l'IPE 270 exposé sur trois côtés."""
        profil = catalogue["IPE 270"]
        assert facteur_massivete(profil, Exposition.CONTOUR_3_FACES) == pytest.approx(
            197, abs=1
        )

    def test_sans_protection_la_poutre_tient_15_minutes(self, catalogue) -> None:
        """« Sans peinture intumescente, cette poutre mixte atteint 15 min. »"""
        duree = _duree_nue(catalogue, "IPE 270", Exposition.CONTOUR_3_FACES, 643.0)
        assert duree == pytest.approx(15, abs=1.5)

    def test_epaisseur_de_spray_a_phi_nul(self, catalogue) -> None:
        """Plafond 2000 W/(m³·K) pour λ_p = 0,12, d'où d_p = 12 mm."""
        plafond = _massivete_thermique_max(catalogue, 643.0, 60.0, lambda_p=0.12)
        assert plafond == pytest.approx(2000, rel=0.05)
        assert 0.12 * 197 / plafond * 1000 == pytest.approx(12, abs=1)

    def test_epaisseur_de_spray_corrigee_de_phi(self) -> None:
        """φ = 0,18 relève le plafond à 2180, et d_p tombe à 11 mm."""
        phi = (1200 * 0.012 * 300) / (600 * RHO_A) * 197
        assert phi == pytest.approx(0.18, abs=0.005)
        assert 2000 * (1 + 0.5 * phi) == pytest.approx(2180, abs=10)
        assert 0.12 * 197 / (2000 * (1 + 0.5 * phi)) * 1000 == pytest.approx(11, abs=0.5)


class TestExemplesGetH_HEB340Nu:
    """HEB 340 S235, L = 4,0 m, l_fi = 0,7·L, poteau de rez-de-chaussée.

    N_Gk = 400 kN, N_Qk = 1200 kN, bureaux : N_Ed,fi = 1,0·400 + 0,3·1200 = 760 kN.
    """

    def test_combinaison_d_actions(self) -> None:
        """ψ₂ = 0,3 pour les bureaux : 760 kN en incendie contre 2340 à froid."""
        assert 1.35 * 400 + 1.5 * 1200 == pytest.approx(2340)
        assert 1.0 * 400 + 0.3 * 1200 == pytest.approx(760)

    def test_resistance_au_flambement_a_froid(self, catalogue) -> None:
        """λ̄₀ = 0,57, χ_fi = 0,678, N_b,fi,0,Rd = 2725 kN."""
        profil = catalogue["HEB 340"]
        assert profil.A * 1e6 == pytest.approx(17100, rel=0.005)
        assert profil.iz * 1e3 == pytest.approx(75.3, abs=0.2)

        lambda_0 = _lambda_0(4.0, profil.iz)
        assert lambda_0 == pytest.approx(0.57, abs=0.005)
        chi_0 = chi_fi(lambda_0, _FY)
        assert chi_0 == pytest.approx(0.678, abs=0.003)
        assert chi_0 * profil.A * _FY / 1e3 == pytest.approx(2725, rel=0.01)

    def test_temperature_critique(self, catalogue) -> None:
        """μ_fi,0 = 0,28 et l_fi = 0,7·L donnent θ_crit = 683 °C."""
        profil = catalogue["HEB 340"]
        lambda_0 = _lambda_0(4.0, profil.iz)
        chi_0 = chi_fi(lambda_0, _FY)
        mu_0 = 760e3 / (chi_0 * profil.A * _FY)
        assert mu_0 == pytest.approx(0.28, abs=0.005)
        assert _theta_par_verification_croisee(
            mu_0, 0.7 * lambda_0, chi_0
        ) == pytest.approx(683, abs=4)

    def test_le_facteur_d_ombre_est_bien_applique(self, catalogue) -> None:
        """[A_m/V]_sh = 0,9·[A_m/V]_b = 0,9·74 = 67 m⁻¹.

        Le point qui tranche : la SZS applique k_sh, elle ne l'intègre pas dans
        ses courbes. L'identité k_sh·[A_m/V] = 0,9·[A_m/V]_b est écrite telle
        quelle dans le document.
        """
        profil = catalogue["HEB 340"]
        brut = facteur_massivete(profil, Exposition.CONTOUR_4_FACES)
        caisson = facteur_massivete_caisson(profil, Exposition.CONTOUR_4_FACES)
        assert brut == pytest.approx(105, abs=1)
        assert caisson == pytest.approx(74, abs=1)
        assert 0.9 * caisson == pytest.approx(67, abs=1)

    def test_duree_de_resistance_au_feu(self, catalogue) -> None:
        """25 minutes — la valeur de l'outil livré, k_sh compris."""
        duree = _duree_nue(catalogue, "HEB 340", Exposition.CONTOUR_4_FACES, 683.0)
        assert duree == pytest.approx(25, abs=1.5)

    def test_H_les_tables_produit_se_lisent_sur_le_A_m_V_brut(self, catalogue) -> None:
        """L'exemple H cherche 105 m⁻¹, pas 67 : k_sh ne concerne que l'acier nu.

        Une nuance facile à manquer : le facteur d'ombre corrige le
        rayonnement reçu par un profilé **nu**. Les tables d'épaisseur de
        peinture intumescente s'indexent sur le facteur de massiveté brut.
        """
        profil = catalogue["HEB 340"]
        assert facteur_massivete(profil, Exposition.CONTOUR_4_FACES) == pytest.approx(
            105, abs=1
        )
