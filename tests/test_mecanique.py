"""Résistances et interaction en situation d'incendie — EN 1993-1-2 §4.2.2/4.2.3."""

from __future__ import annotations

import math

import pytest

from nommogramme.materiaux.acier import Nuance, k_E, k_y, limite_elasticite
from nommogramme.mecanique.actions import (
    BETA_M_CHARGE_REPARTIE,
    CasDeCharge,
    beta_M_lineaire,
    combinaison_accidentelle,
    eta_fi,
)
from nommogramme.mecanique.classification import classifier, epsilon_feu
from nommogramme.mecanique.interaction import facteurs_interaction, taux
from nommogramme.mecanique.resistances import (
    alpha_flambement_feu,
    chi_fi,
    elancement_reduit,
    elancement_reduit_LT,
    elancement_reduit_theta,
    moment_critique_elastique,
    resistances_a,
)
from nommogramme.profils import charger_csv


@pytest.fixture(scope="module")
def cat():
    return charger_csv()


class TestActions:
    def test_combinaison_accidentelle(self) -> None:
        """EN 1991-1-2 §4.3.1 : G + ψ·Q, sans les facteurs γ de l'ELU."""
        assert combinaison_accidentelle(100.0, 50.0, psi_dominante=0.3) == pytest.approx(115.0)
        assert combinaison_accidentelle(
            100.0, 50.0, psi_dominante=0.3, autres=((20.0, 0.3),)
        ) == pytest.approx(121.0)

    def test_eta_fi(self) -> None:
        """EN 1993-1-2 éq. (2.5)."""
        valeur = eta_fi(G_k=100.0, Q_k_1=100.0, psi_fi=0.3)
        assert valeur == pytest.approx(130.0 / 285.0, rel=1e-6)
        assert 0.0 < valeur < 1.0

    def test_eta_fi_croit_avec_psi(self) -> None:
        faible = eta_fi(100.0, 100.0, psi_fi=0.3)
        fort = eta_fi(100.0, 100.0, psi_fi=0.7)
        assert fort > faible

    def test_beta_M_lineaire(self) -> None:
        """EN 1993-1-2 figure 4.2 : β_M,ψ = 1,8 − 0,7·ψ."""
        assert beta_M_lineaire(1.0) == pytest.approx(1.1)
        assert beta_M_lineaire(0.0) == pytest.approx(1.8)
        assert beta_M_lineaire(-1.0) == pytest.approx(2.5)

    def test_beta_M_hors_domaine(self) -> None:
        with pytest.raises(ValueError, match="−1 et \\+1"):
            beta_M_lineaire(1.5)

    def test_convention_de_signe(self) -> None:
        assert CasDeCharge(N_fi_Ed=100.0).comprime
        assert CasDeCharge(N_fi_Ed=-100.0).tendu
        assert not CasDeCharge(N_fi_Ed=0.0).comprime

    def test_moment_negatif_refuse(self) -> None:
        with pytest.raises(ValueError, match="valeur absolue"):
            CasDeCharge(My_fi_Ed=-10.0)

    def test_longueur_de_flambement_par_defaut(self) -> None:
        cas = CasDeCharge(L=4.0)
        assert cas.longueur_flambement_y() == 4.0
        assert CasDeCharge(L=4.0, l_fi_y=2.0).longueur_flambement_y() == 2.0

    def test_deversement_reprend_le_plan_faible(self) -> None:
        cas = CasDeCharge(L=6.0, l_fi_z=3.0)
        assert cas.longueur_deversement() == 3.0
        assert CasDeCharge(L=6.0, l_fi_z=3.0, L_LT=6.0).longueur_deversement() == 6.0


class TestClassification:
    def test_epsilon_feu(self) -> None:
        """EN 1993-1-2 §4.2.2 : le facteur 0,85 durcit les limites à chaud."""
        assert epsilon_feu(235e6) == pytest.approx(0.85)
        assert epsilon_feu(355e6) == pytest.approx(0.85 * math.sqrt(235 / 355), rel=1e-6)

    def test_epsilon_plus_severe_qu_a_froid(self) -> None:
        froid = math.sqrt(235e6 / 355e6)
        assert epsilon_feu(355e6) < froid

    def test_ipe300_flexion_pure_classe_1(self, cat) -> None:
        resultat = classifier(cat["IPE 300"], 355e6, N_Ed=0.0, My_Ed=100e3)
        assert resultat.classe == 1

    def test_compression_degrade_la_classe(self, cat) -> None:
        """Plus l'axe neutre plastique remonte, plus l'âme est pénalisée."""
        profil = cat["IPE 600"]
        fy = 355e6
        sans_N = classifier(profil, fy, N_Ed=0.0, My_Ed=500e3)
        avec_N = classifier(profil, fy, N_Ed=3000e3, My_Ed=500e3)
        assert avec_N.classe >= sans_N.classe
        assert avec_N.alpha > sans_N.alpha

    def test_alpha_borne(self, cat) -> None:
        for N in (-1e7, 0.0, 1e7):
            resultat = classifier(cat["HEB 300"], 355e6, N_Ed=N, My_Ed=50e3)
            assert 0.0 <= resultat.alpha <= 1.0

    def test_nuance_elevee_plus_severe(self, cat) -> None:
        profil = cat["IPE 600"]
        s235 = classifier(profil, 235e6, N_Ed=0.0, My_Ed=500e3)
        s460 = classifier(profil, 460e6, N_Ed=0.0, My_Ed=500e3)
        assert s460.classe >= s235.classe

    def test_profils_creux_classes(self, cat) -> None:
        resultat = classifier(cat["RRW 200/200/10"], 355e6, N_Ed=500e3)
        assert 1 <= resultat.classe <= 4

    def test_catalogue_majoritairement_plastique(self, cat) -> None:
        """En flexion pure S235, la grande majorité du catalogue est en classe 1 ou 2."""
        plastiques = sum(
            1 for p in cat if classifier(p, 235e6, My_Ed=p.Wply * 235e6 * 0.5).plastique
        )
        assert plastiques / len(cat) > 0.9


class TestFlambement:
    def test_alpha_feu(self) -> None:
        """EN 1993-1-2 éq. (4.8) : courbe unique, α = 0,65·√(235/f_y)."""
        assert alpha_flambement_feu(235e6) == pytest.approx(0.65)
        assert alpha_flambement_feu(355e6) == pytest.approx(0.529, abs=0.001)

    def test_elancement_croit_avec_la_temperature(self) -> None:
        """λ̄_θ = λ̄·√(k_y,θ/k_E,θ) : +23 % à 600 °C."""
        assert elancement_reduit_theta(1.0, 20.0) == pytest.approx(1.0)
        rapport_600 = math.sqrt(k_y(600) / k_E(600))
        assert elancement_reduit_theta(1.0, 600.0) == pytest.approx(rapport_600)
        assert rapport_600 == pytest.approx(1.231, abs=0.005)

    def test_chi_decroit_avec_l_elancement(self) -> None:
        valeurs = [chi_fi(lam, 355e6) for lam in (0.0, 0.5, 1.0, 1.5, 2.0)]
        assert valeurs[0] == pytest.approx(1.0)
        assert valeurs == sorted(valeurs, reverse=True)
        assert all(0.0 < v <= 1.0 for v in valeurs)

    def test_chi_decroit_avec_la_temperature(self) -> None:
        chaud = chi_fi(elancement_reduit_theta(1.0, 700.0), 355e6)
        froid = chi_fi(elancement_reduit_theta(1.0, 20.0), 355e6)
        assert chaud < froid

    def test_elancement_reduit(self, cat) -> None:
        profil = cat["HEB 300"]
        fy = 355e6
        lam = elancement_reduit(6.0, profil.iz, fy)
        lambda_1 = math.pi * math.sqrt(210e9 / fy)
        assert lam == pytest.approx((6.0 / profil.iz) / lambda_1)
        assert 0.5 < lam < 2.0


class TestDeversement:
    def test_moment_critique_decroit_avec_la_longueur(self, cat) -> None:
        profil = cat["IPE 300"]
        valeurs = [moment_critique_elastique(profil, L) for L in (2.0, 4.0, 6.0, 8.0)]
        assert valeurs == sorted(valeurs, reverse=True)

    def test_profil_creux_insensible_au_deversement(self, cat) -> None:
        assert moment_critique_elastique(cat["RRW 200/200/10"], 6.0) == math.inf
        assert elancement_reduit_LT(cat["RRW 200/200/10"], 355e6, 6.0) == 0.0

    def test_elancement_LT_croit_avec_la_longueur(self, cat) -> None:
        profil = cat["IPE 300"]
        valeurs = [elancement_reduit_LT(profil, 355e6, L) for L in (2.0, 4.0, 8.0)]
        assert valeurs == sorted(valeurs)

    def test_C1_reduit_l_elancement(self, cat) -> None:
        profil = cat["IPE 300"]
        uniforme = elancement_reduit_LT(profil, 355e6, 6.0, C1=1.0)
        favorable = elancement_reduit_LT(profil, 355e6, 6.0, C1=1.77)
        assert favorable < uniforme


class TestResistances:
    def _res(self, cat, theta: float, comprime: bool = True):
        profil = cat["HEB 300"]
        fy = limite_elasticite(Nuance.S355, profil.tf)
        return profil, resistances_a(
            profil=profil,
            nuance=Nuance.S355,
            theta=theta,
            lambda_y=elancement_reduit(4.0, profil.iy, fy),
            lambda_z=elancement_reduit(4.0, profil.iz, fy),
            lambda_LT=elancement_reduit_LT(profil, fy, 4.0),
            gamma_M_fi=1.0,
            comprime=comprime,
        )

    def test_resistances_decroissent_avec_la_temperature(self, cat) -> None:
        _, froid = self._res(cat, 20.0)
        _, chaud = self._res(cat, 700.0)
        assert chaud.N_Rd < froid.N_Rd
        assert chaud.My_Rd < froid.My_Rd
        assert chaud.Mb_Rd < froid.Mb_Rd

    def test_moment_resistant_a_20_degres(self, cat) -> None:
        """M_Rd = W_pl·f_y à 20 °C avec γ_M,fi = 1."""
        profil, res = self._res(cat, 20.0)
        assert res.My_Rd == pytest.approx(profil.Wply * 355e6, rel=1e-9)

    def test_traction_ignore_le_flambement(self, cat) -> None:
        profil, tendu = self._res(cat, 20.0, comprime=False)
        _, comprime = self._res(cat, 20.0, comprime=True)
        assert tendu.N_Rd == pytest.approx(profil.A * 355e6)
        assert comprime.N_Rd < tendu.N_Rd

    def test_kappa_augmente_le_moment_resistant(self, cat) -> None:
        """κ₁ < 1 traduit une section plus froide, donc plus résistante."""
        profil = cat["IPE 300"]
        fy = 355e6
        base = resistances_a(
            profil=profil, nuance=Nuance.S355, theta=500.0,
            lambda_y=0.5, lambda_z=0.5, lambda_LT=0.0,
            gamma_M_fi=1.0, comprime=False,
        )
        adapte = resistances_a(
            profil=profil, nuance=Nuance.S355, theta=500.0,
            lambda_y=0.5, lambda_z=0.5, lambda_LT=0.0,
            gamma_M_fi=1.0, comprime=False, kappa_1=0.70,
        )
        del fy
        assert adapte.My_Rd == pytest.approx(base.My_Rd / 0.70)

    def test_resistance_nulle_a_1200_degres(self, cat) -> None:
        _, res = self._res(cat, 1200.0)
        assert res.N_Rd == pytest.approx(0.0)
        assert res.My_Rd == pytest.approx(0.0)

    def test_effort_tranchant(self, cat) -> None:
        profil, res = self._res(cat, 20.0)
        assert res.V_Rd == pytest.approx(profil.Av * 355e6 / math.sqrt(3.0))

    def test_effort_tranchant_absent_pour_profils_creux(self, cat) -> None:
        profil = cat["RRW 200/200/10"]
        res = resistances_a(
            profil=profil, nuance=Nuance.S355, theta=20.0,
            lambda_y=0.5, lambda_z=0.5, lambda_LT=0.0,
            gamma_M_fi=1.0, comprime=True,
        )
        assert res.V_Rd is None


class TestInteraction:
    def _res(self, cat, theta: float = 20.0):
        profil = cat["HEB 300"]
        fy = limite_elasticite(Nuance.S355, profil.tf)
        return profil, resistances_a(
            profil=profil, nuance=Nuance.S355, theta=theta,
            lambda_y=elancement_reduit(6.0, profil.iy, fy),
            lambda_z=elancement_reduit(6.0, profil.iz, fy),
            lambda_LT=elancement_reduit_LT(profil, fy, 6.0),
            gamma_M_fi=1.0, comprime=True,
        )

    def test_facteurs_dans_leurs_bornes(self, cat) -> None:
        profil, res = self._res(cat)
        f = facteurs_interaction(1000e3, res, profil.A, 1.3, 1.3, 1.3)
        assert f.k_y <= 3.0
        assert f.k_z <= 3.0
        assert f.k_LT <= 1.0
        assert f.mu_y <= 0.8
        assert f.mu_z <= 0.8
        assert f.mu_LT <= 0.9

    def test_compression_seule(self, cat) -> None:
        """Sans moment, le taux se réduit à N/N_Rd."""
        profil, res = self._res(cat)
        t = taux(1000e3, 0.0, 0.0, res, profil.A)
        assert t.valeur == pytest.approx(1000e3 / res.N_Rd, rel=1e-6)

    def test_flexion_seule(self, cat) -> None:
        profil, res = self._res(cat)
        t = taux(0.0, 200e3, 0.0, res, profil.A)
        assert t.valeur == pytest.approx(200e3 / res.Mb_Rd, rel=1e-6)

    def test_interaction_penalise(self, cat) -> None:
        """La somme sous N + M dépasse chacune des sollicitations isolées."""
        profil, res = self._res(cat)
        seul_N = taux(1000e3, 0.0, 0.0, res, profil.A).valeur
        seul_M = taux(0.0, 200e3, 0.0, res, profil.A).valeur
        ensemble = taux(1000e3, 200e3, 0.0, res, profil.A).valeur
        assert ensemble > seul_N
        assert ensemble > seul_M

    def test_taux_croit_avec_la_temperature(self, cat) -> None:
        profil_froid, res_froid = self._res(cat, 20.0)
        _, res_chaud = self._res(cat, 600.0)
        froid = taux(1000e3, 200e3, 0.0, res_froid, profil_froid.A).valeur
        chaud = taux(1000e3, 200e3, 0.0, res_chaud, profil_froid.A).valeur
        assert chaud > froid

    def test_critere_gouvernant_identifie(self, cat) -> None:
        profil, res = self._res(cat)
        t = taux(1000e3, 200e3, 0.0, res, profil.A)
        assert "4.21" in t.critere
        assert t.valeur == pytest.approx(max(t.taux_flambement, t.taux_deversement))

    def test_traction_hors_du_champ_du_paragraphe(self, cat) -> None:
        profil, res = self._res(cat)
        t = taux(-1000e3, 100e3, 0.0, res, profil.A)
        assert "hors §4.2.3.5" in t.critere
        assert t.facteurs is None
