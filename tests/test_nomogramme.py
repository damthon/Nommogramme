"""Méthode du nomogramme et vérification d'ensemble — EN 1993-1-2 §4.2.4."""

from __future__ import annotations

import pytest

from nommogramme.contexte import EUROCODE_REC, SUISSE_SIA
from nommogramme.materiaux.acier import Nuance
from nommogramme.materiaux.protection import Protection
from nommogramme.mecanique.actions import CasDeCharge
from nommogramme.nomogramme.temperature_critique import (
    MU_0_MINIMAL,
    degre_utilisation_pour,
    temperature_critique,
)
from nommogramme.nomogramme.verification import Verdict, verifier
from nommogramme.profils import Exposition, charger_csv


@pytest.fixture(scope="module")
def cat():
    return charger_csv()


class TestEquation422:
    @pytest.mark.parametrize(
        "mu_0, attendu",
        [
            (0.10, 829),
            (0.20, 725),
            (0.30, 664),
            (0.40, 620),
            (0.50, 585),
            (0.60, 554),
            (0.70, 526),
            (0.80, 496),
        ],
    )
    def test_valeurs_de_reference(self, mu_0: float, attendu: int) -> None:
        """θ_a,cr = 39,19·ln[1/(0,9674·μ₀^3,833) − 1] + 482."""
        assert temperature_critique(mu_0) == pytest.approx(attendu, abs=1.0)

    def test_decroissance_monotone(self) -> None:
        precedent = 2000.0
        for centieme in range(2, 100):
            courante = temperature_critique(centieme / 100.0)
            assert courante < precedent
            precedent = courante

    def test_inversion(self) -> None:
        for mu_0 in (0.05, 0.2, 0.45, 0.65, 0.9):
            assert degre_utilisation_pour(temperature_critique(mu_0)) == pytest.approx(
                mu_0, rel=1e-6
            )

    def test_domaine_courant(self) -> None:
        """Les degrés d'utilisation usuels donnent 480 à 700 °C."""
        for mu_0 in (0.25, 0.5, 0.85):
            assert 470.0 < temperature_critique(mu_0) < 700.0

    def test_refus_hors_domaine(self) -> None:
        with pytest.raises(ValueError, match="non positif"):
            temperature_critique(0.0)
        with pytest.raises(ValueError, match="ne tient déjà pas"):
            temperature_critique(1.0)
        with pytest.raises(ValueError, match="borne de validité"):
            temperature_critique(MU_0_MINIMAL / 2.0)


class TestVerificationCroisee:
    """La raison d'être du garde-fou : l'éq. (4.22) ignore la chute de χ_fi."""

    def _verifier(self, cat, nom: str, **kw):
        defauts = dict(beta_M_y=1.4, beta_M_z=1.4, beta_M_LT=1.4)
        return verifier(
            profil=cat[nom],
            nuance=Nuance.S355,
            cas=CasDeCharge(**{**defauts, **kw}),
            exposition=Exposition.CONTOUR_4_FACES,
            duree_requise_min=60,
        )

    def test_element_trapu_les_deux_voies_concordent(self, cat) -> None:
        resultat = self._verifier(
            cat, "HEB 300", N_fi_Ed=850e3, My_fi_Ed=120e3, L=4.0, l_fi_y=2.0, l_fi_z=2.0
        )
        assert abs(resultat.ecart_nomogramme) < 10.0

    def test_element_elance_le_nomogramme_est_optimiste(self, cat) -> None:
        """C'est le cas que le plan annonce et que le garde-fou doit rattraper."""
        resultat = self._verifier(
            cat, "HEB 300", N_fi_Ed=850e3, My_fi_Ed=120e3, L=8.0, l_fi_y=8.0, l_fi_z=8.0
        )
        assert resultat.ecart_nomogramme > 50.0
        assert resultat.theta_cr == pytest.approx(resultat.theta_cr_exact)
        assert "non conservatif" in " ".join(resultat.avertissements)

    def test_la_plus_defavorable_est_retenue(self, cat) -> None:
        compares = 0
        for longueur in (2.0, 4.0, 6.0, 8.0, 10.0):
            resultat = self._verifier(
                cat, "HEA 200", N_fi_Ed=250e3, My_fi_Ed=20e3,
                L=longueur, l_fi_y=longueur, l_fi_z=longueur,
            )
            if resultat.mu_0 >= 1.0:
                # L'élément ne tient pas à froid : aucune des deux voies ne
                # produit de température critique, il n'y a rien à comparer.
                assert resultat.theta_cr_nomogramme is None
                assert resultat.theta_cr_exact is None
                continue
            candidats = [
                t for t in (resultat.theta_cr_nomogramme, resultat.theta_cr_exact)
                if t is not None
            ]
            assert resultat.theta_cr == pytest.approx(min(candidats))
            compares += 1
        assert compares >= 3, "trop peu de cas exploitables dans ce balayage"

    def test_traction_les_deux_voies_concordent(self, cat) -> None:
        """Sans instabilité, l'éq. (4.22) est rigoureuse."""
        resultat = self._verifier(cat, "IPE 300", N_fi_Ed=-400e3, L=6.0)
        assert abs(resultat.ecart_nomogramme) < 5.0


class TestVerification:
    def _cas_poteau(self):
        return CasDeCharge(
            N_fi_Ed=850e3, My_fi_Ed=120e3, L=4.0,
            l_fi_y=2.0, l_fi_z=2.0, beta_M_y=1.4,
        )

    def test_chaine_complete(self, cat) -> None:
        resultat = verifier(
            profil=cat["HEB 300"], nuance=Nuance.S355, cas=self._cas_poteau(),
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
        )
        assert 0.0 < resultat.mu_0 < 1.0
        assert 400.0 < resultat.theta_cr < 700.0
        assert resultat.Am_sur_V == pytest.approx(116.1, rel=0.01)
        assert resultat.classification.classe == 1

    def test_element_nu_ne_tient_pas_r60(self, cat) -> None:
        resultat = verifier(
            profil=cat["HEB 300"], nuance=Nuance.S355, cas=self._cas_poteau(),
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
        )
        assert resultat.verdict is Verdict.NON_SATISFAIT
        assert resultat.marge_temperature < 0.0

    def test_la_protection_renverse_le_verdict(self, cat) -> None:
        flocage = Protection.depuis_catalogue("flocage_fibreux", d_p=0.025)
        resultat = verifier(
            profil=cat["HEB 300"], nuance=Nuance.S355, cas=self._cas_poteau(),
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
            protection=flocage,
        )
        assert resultat.verdict is Verdict.SATISFAIT
        assert resultat.marge_temperature > 0.0

    def test_verdict_coherent_avec_la_marge(self, cat) -> None:
        for epaisseur in (0.005, 0.010, 0.020, 0.030, 0.040):
            resultat = verifier(
                profil=cat["HEB 300"], nuance=Nuance.S355, cas=self._cas_poteau(),
                exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
                protection=Protection.depuis_catalogue("flocage_fibreux", d_p=epaisseur),
            )
            assert bool(resultat.verdict) == (resultat.marge_temperature >= 0.0)

    def test_plus_de_charge_donne_moins_de_temperature_critique(self, cat) -> None:
        temperatures = []
        for effort in (200e3, 600e3, 1000e3, 1400e3):
            resultat = verifier(
                profil=cat["HEB 300"], nuance=Nuance.S355,
                cas=CasDeCharge(N_fi_Ed=effort, L=4.0, l_fi_y=2.0, l_fi_z=2.0),
                exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
            )
            temperatures.append(resultat.theta_cr)
        assert temperatures == sorted(temperatures, reverse=True)

    def test_element_surcharge_signale(self, cat) -> None:
        resultat = verifier(
            profil=cat["IPE 200"], nuance=Nuance.S235,
            cas=CasDeCharge(N_fi_Ed=2000e3, L=6.0),
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=30,
        )
        assert resultat.mu_0 >= 1.0
        assert resultat.verdict is Verdict.NON_SATISFAIT
        assert any("ne tient pas à 20 °C" in a for a in resultat.avertissements)

    def test_exposition_trois_faces_plus_favorable(self, cat) -> None:
        commun = dict(
            profil=cat["IPE 300"], nuance=Nuance.S235,
            cas=CasDeCharge(My_fi_Ed=60e3, L=6.0, L_LT=2.0),
            duree_requise_min=30,
        )
        quatre = verifier(exposition=Exposition.CONTOUR_4_FACES, **commun)
        trois = verifier(exposition=Exposition.CONTOUR_3_FACES, **commun)
        assert trois.theta_a_a_echeance < quatre.theta_a_a_echeance

    def test_contexte_normatif_transmis(self, cat) -> None:
        for contexte in (SUISSE_SIA, EUROCODE_REC):
            resultat = verifier(
                profil=cat["HEB 300"], nuance=Nuance.S355, cas=self._cas_poteau(),
                exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
                contexte=contexte,
            )
            assert resultat.contexte is contexte

    def test_kappa_ameliore_la_temperature_critique(self, cat) -> None:
        """Une poutre sous dalle béton est plus froide : κ₁ = 0,70.

        Le facteur d'adaptation porte sur la résistance de section de
        l'éq. (4.21a). Il faut donc que le déversement soit écarté, ce que
        traduit ``maintien_lateral`` : l'éq. (4.11) du déversement n'admet pas
        de κ, la norme y passant par la température de la semelle comprimée.
        """
        commun = dict(
            profil=cat["IPE 300"], nuance=Nuance.S235,
            cas=CasDeCharge(My_fi_Ed=60e3, L=6.0, maintien_lateral=True),
            exposition=Exposition.CONTOUR_3_FACES, duree_requise_min=30,
        )
        sans = verifier(**commun)
        avec = verifier(kappa_1=0.70, **commun)
        assert avec.mu_0 < sans.mu_0
        assert avec.theta_cr > sans.theta_cr

    def test_maintien_lateral_ecarte_le_deversement(self, cat) -> None:
        commun = dict(
            profil=cat["IPE 300"], nuance=Nuance.S235,
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=30,
        )
        libre = verifier(cas=CasDeCharge(My_fi_Ed=60e3, L=6.0), **commun)
        maintenu = verifier(
            cas=CasDeCharge(My_fi_Ed=60e3, L=6.0, maintien_lateral=True), **commun
        )
        assert "4.21b" in libre.gouverne_par
        assert "4.21a" in maintenu.gouverne_par
        assert maintenu.mu_0 < libre.mu_0


class TestNoteDeCalcul:
    def test_contenu(self, cat) -> None:
        resultat = verifier(
            profil=cat["HEB 300"], nuance=Nuance.S355,
            cas=CasDeCharge(N_fi_Ed=850e3, My_fi_Ed=120e3, L=4.0, l_fi_y=2.0, l_fi_z=2.0),
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
        )
        note = resultat.note_de_calcul()
        for attendu in (
            "HEB300", "μ₀", "éq. (4.22)", "éq. (4.23)", "A_m/V", "k_sh",
            "Verdict", "SIA", "éq. (4.26a/b)",
        ):
            assert attendu in note, f"« {attendu} » absent de la note"

    def test_mentionne_l_equation_de_protection(self, cat) -> None:
        resultat = verifier(
            profil=cat["HEB 300"], nuance=Nuance.S355,
            cas=CasDeCharge(N_fi_Ed=850e3, L=4.0, l_fi_y=2.0, l_fi_z=2.0),
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
            protection=Protection.depuis_catalogue("flocage_fibreux", d_p=0.020),
        )
        note = resultat.note_de_calcul()
        assert "éq. (4.27)" in note
        assert "éq. (4.28)" in note
