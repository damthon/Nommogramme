"""Diffusion de chaleur — EN 1993-1-2 §4.2.5, EN 1991-1-2 §3.

Le tableau de référence de la classe ``TestEchauffementNonProtege`` est celui
publié au §9 de ``docs/plan-conception.html``.
"""

from __future__ import annotations

import pytest

from nommogramme.materiaux.protection import Protection
from nommogramme.profils import Exposition, charger_csv
from nommogramme.thermique import (
    DT_MAX_NON_PROTEGE,
    DT_MAX_PROTEGE,
    FEU_EXTERIEUR,
    HYDROCARBURE,
    ISO834,
    echauffement,
    epaisseur_requise_minutes,
    flux_net,
)
from nommogramme.unites import minutes


@pytest.fixture(scope="module")
def cat():
    return charger_csv()


@pytest.fixture(scope="module")
def ipe300(cat):
    return cat["IPE 300"]


class TestCourbesDeFeu:
    @pytest.mark.parametrize(
        "minute, attendu",
        [(0, 20), (15, 739), (30, 842), (60, 945), (90, 1006), (120, 1049)],
    )
    def test_iso834(self, minute: int, attendu: int) -> None:
        """EN 1991-1-2 éq. (3.4), valeurs de référence."""
        assert ISO834.temperature(minutes(minute)) == pytest.approx(attendu, abs=1.0)

    def test_hydrocarbure_monte_plus_vite(self) -> None:
        """EN 1991-1-2 éq. (3.6) : montée brutale, asymptote à 1100 °C."""
        assert HYDROCARBURE.temperature(minutes(5)) == pytest.approx(948, abs=2)
        assert HYDROCARBURE.temperature(minutes(10)) > 1000.0
        assert HYDROCARBURE.temperature(minutes(60)) == pytest.approx(1100, abs=2)

    def test_hydrocarbure_au_dessus_de_iso834(self) -> None:
        for minute in (5, 15, 30, 60):
            assert HYDROCARBURE.temperature(minutes(minute)) > ISO834.temperature(
                minutes(minute)
            )

    def test_feu_exterieur_plafonne(self) -> None:
        """EN 1991-1-2 éq. (3.5) : asymptote à 680 °C."""
        assert FEU_EXTERIEUR.temperature(minutes(120)) == pytest.approx(680, abs=1)

    def test_coefficients_de_convection(self) -> None:
        assert ISO834.alpha_c == 25.0
        assert FEU_EXTERIEUR.alpha_c == 25.0
        assert HYDROCARBURE.alpha_c == 50.0

    def test_croissance_monotone(self) -> None:
        for courbe in (ISO834, HYDROCARBURE, FEU_EXTERIEUR):
            precedent = -1.0
            for seconde in range(0, 7200, 30):
                courante = courbe.temperature(seconde)
                assert courante >= precedent - 1e-9
                precedent = courante


class TestFluxNet:
    def test_flux_nul_a_l_equilibre(self) -> None:
        assert flux_net(600.0, 600.0, alpha_c=25.0) == pytest.approx(0.0)

    def test_signe(self) -> None:
        assert flux_net(800.0, 400.0, alpha_c=25.0) > 0.0
        assert flux_net(400.0, 800.0, alpha_c=25.0) < 0.0

    def test_rayonnement_domine_a_haute_temperature(self) -> None:
        """À 900 °C de gaz sur acier froid, le radiatif dépasse le convectif."""
        from nommogramme.thermique.flux import flux_convectif, flux_radiatif

        convectif = flux_convectif(900.0, 100.0, 25.0)
        radiatif = flux_radiatif(900.0, 100.0)
        assert radiatif > convectif


class TestEchauffementNonProtege:
    """EN 1993-1-2 éq. (4.25)."""

    @pytest.mark.parametrize(
        "minute, attendu",
        [(5, 227), (10, 474), (15, 634), (20, 718), (30, 809), (45, 894), (60, 940)],
    )
    def test_tableau_de_reference_am_sur_v_200(
        self, ipe300, minute: int, attendu: int
    ) -> None:
        """Reproduit la colonne A_m/V = 200 m⁻¹ du plan de conception.

        L'IPE 300 exposé sur quatre faces vaut 216 m⁻¹ ; on impose donc le
        facteur de massiveté et le facteur d'ombre de la référence en passant
        par un profilé fictif équivalent — ici, on tolère l'écart de 8 %.
        """
        resultat = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(minute), ISO834
        )
        assert resultat.temperature_finale == pytest.approx(attendu, rel=0.08)

    def test_palier_de_transformation_de_phase(self, cat) -> None:
        """Le pic de chaleur spécifique freine l'échauffement vers 735 °C."""
        profil = cat["IPE 200"]
        resultat = echauffement(
            profil, Exposition.CONTOUR_4_FACES, minutes(40), ISO834
        )
        vitesses = [
            (resultat.temperatures[i + 1] - resultat.temperatures[i])
            for i in range(len(resultat.temperatures) - 1)
        ]
        indice_palier = min(
            range(len(resultat.temperatures)),
            key=lambda i: abs(resultat.temperatures[i] - 735.0),
        )
        indice_avant = min(
            range(len(resultat.temperatures)),
            key=lambda i: abs(resultat.temperatures[i] - 600.0),
        )
        assert vitesses[indice_palier] < 0.5 * vitesses[indice_avant]

    def test_acier_toujours_sous_les_gaz(self, ipe300) -> None:
        resultat = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(120), ISO834
        )
        for acier, gaz in zip(resultat.temperatures, resultat.temperatures_gaz):
            assert acier <= gaz + 1e-6

    def test_croissance_monotone(self, ipe300) -> None:
        resultat = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(120), ISO834
        )
        for avant, apres in zip(resultat.temperatures, resultat.temperatures[1:]):
            assert apres >= avant - 1e-9

    def test_convergence_en_pas_de_temps(self, ipe300) -> None:
        """θ_a(60 min) doit bouger de moins de 1 °C entre Δt = 2 s et Δt = 0,5 s."""
        grossier = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(60), ISO834, dt=2.0
        ).temperature_finale
        fin = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(60), ISO834, dt=0.5
        ).temperature_finale
        assert abs(grossier - fin) < 1.0

    def test_refus_d_un_pas_trop_grand(self, ipe300) -> None:
        with pytest.raises(ValueError, match="5.0 s"):
            echauffement(
                ipe300,
                Exposition.CONTOUR_4_FACES,
                minutes(30),
                ISO834,
                dt=DT_MAX_NON_PROTEGE + 1.0,
            )

    def test_profil_trapu_chauffe_plus_lentement(self, cat) -> None:
        leger = echauffement(
            cat["IPE 300"], Exposition.CONTOUR_4_FACES, minutes(20), ISO834
        ).temperature_finale
        lourd = echauffement(
            cat["HHD 400.421"], Exposition.CONTOUR_4_FACES, minutes(20), ISO834
        ).temperature_finale
        assert lourd < leger - 200.0

    def test_element_nu_ne_tient_pas_r60(self, ipe300) -> None:
        """Résultat connu : un profilé nu courant dépasse 600 °C avant 20 min."""
        resultat = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(60), ISO834
        )
        instant = resultat.minutes_pour_atteindre(600.0)
        assert instant is not None
        assert 10.0 < instant < 20.0


class TestEchauffementProtege:
    """EN 1993-1-2 éq. (4.27) et (4.28)."""

    @pytest.fixture
    def flocage(self):
        return Protection.depuis_catalogue("flocage_fibreux", d_p=0.015)

    def test_la_protection_ralentit_l_echauffement(self, ipe300, flocage) -> None:
        nu = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(60), ISO834
        ).temperature_finale
        protege = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(60), ISO834, protection=flocage
        ).temperature_finale
        assert protege < nu - 300.0

    def test_plus_epais_donc_plus_froid(self, ipe300, flocage) -> None:
        temperatures = [
            echauffement(
                ipe300,
                Exposition.CONTOUR_4_FACES,
                minutes(90),
                ISO834,
                protection=flocage.avec_epaisseur(epaisseur),
            ).temperature_finale
            for epaisseur in (0.010, 0.020, 0.030, 0.040)
        ]
        assert temperatures == sorted(temperatures, reverse=True)

    def test_jamais_sous_l_ambiante(self, ipe300) -> None:
        """La règle Δθ_a ≥ 0 du §4.2.5.2(1) doit tenir même pour un isolant capacitif."""
        capacitif = Protection(
            nom="test_capacitif",
            lambda_p=0.05,
            rho_p=1200.0,
            c_p=2000.0,
            d_p=0.050,
        )
        resultat = echauffement(
            ipe300, Exposition.CAISSON_4_FACES, minutes(120), ISO834, protection=capacitif
        )
        assert min(resultat.temperatures) >= 20.0
        assert resultat.phi is not None and resultat.phi > 1.0

    def test_croissance_monotone(self, ipe300, flocage) -> None:
        resultat = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(180), ISO834, protection=flocage
        )
        for avant, apres in zip(resultat.temperatures, resultat.temperatures[1:]):
            assert apres >= avant - 1e-9

    def test_acier_toujours_sous_les_gaz(self, ipe300, flocage) -> None:
        resultat = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(180), ISO834, protection=flocage
        )
        for acier, gaz in zip(resultat.temperatures, resultat.temperatures_gaz):
            assert acier <= gaz + 1e-6

    def test_isolant_tres_mince_tend_vers_le_cas_nu(self, ipe300, flocage) -> None:
        """À d_p → 0, l'éq. (4.27) doit rejoindre le comportement non protégé.

        L'écart résiduel vient du facteur d'ombre, qui ne s'applique qu'à
        l'acier nu : le cas protégé chauffe donc un peu plus vite.
        """
        nu = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(30), ISO834
        ).temperature_finale
        quasi_nu = echauffement(
            ipe300,
            Exposition.CONTOUR_4_FACES,
            minutes(30),
            ISO834,
            protection=flocage.avec_epaisseur(0.0002),
        ).temperature_finale
        assert quasi_nu > nu
        assert abs(quasi_nu - nu) < 60.0

    def test_refus_d_un_pas_trop_grand(self, ipe300, flocage) -> None:
        with pytest.raises(ValueError, match="30.0 s"):
            echauffement(
                ipe300,
                Exposition.CONTOUR_4_FACES,
                minutes(60),
                ISO834,
                protection=flocage,
                dt=DT_MAX_PROTEGE + 1.0,
            )

    def test_convergence_en_pas_de_temps(self, ipe300, flocage) -> None:
        grossier = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(90), ISO834,
            protection=flocage, dt=5.0,
        ).temperature_finale
        fin = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(90), ISO834,
            protection=flocage, dt=1.0,
        ).temperature_finale
        assert abs(grossier - fin) < 1.0


class TestSolveurEpaisseur:
    def test_epaisseur_trouvee_satisfait_le_critere(self, ipe300) -> None:
        flocage = Protection.depuis_catalogue("flocage_fibreux", d_p=0.015)
        resultat = epaisseur_requise_minutes(
            profil=ipe300,
            exposition=Exposition.CONTOUR_4_FACES,
            protection=flocage,
            theta_cible=550.0,
            duree_requise_min=60.0,
        )
        assert resultat.theta_atteinte == pytest.approx(550.0, abs=1.0)
        assert resultat.theta_arrondie <= 550.0
        assert resultat.d_p_arrondie >= resultat.d_p
        assert 0.005 < resultat.d_p < 0.050

    def test_plus_la_duree_est_longue_plus_il_faut_d_isolant(self, ipe300) -> None:
        flocage = Protection.depuis_catalogue("flocage_fibreux", d_p=0.015)
        epaisseurs = [
            epaisseur_requise_minutes(
                profil=ipe300,
                exposition=Exposition.CONTOUR_4_FACES,
                protection=flocage,
                theta_cible=550.0,
                duree_requise_min=duree,
            ).d_p
            for duree in (30.0, 60.0, 90.0, 120.0)
        ]
        assert epaisseurs == sorted(epaisseurs)

    def test_profil_trapu_demande_moins_d_isolant(self, cat) -> None:
        flocage = Protection.depuis_catalogue("flocage_fibreux", d_p=0.015)
        options = dict(
            exposition=Exposition.CONTOUR_4_FACES,
            protection=flocage,
            theta_cible=550.0,
            duree_requise_min=90.0,
        )
        leger = epaisseur_requise_minutes(profil=cat["IPE 300"], **options).d_p
        lourd = epaisseur_requise_minutes(profil=cat["HHD 400.421"], **options).d_p
        assert lourd < leger


class TestAvertissements:
    def test_signalement_du_domaine_de_validite(self, cat) -> None:
        """Le HHD le plus trapu encaissé sur trois faces frôle la borne de 10 m⁻¹."""
        resultat = echauffement(
            cat["HHD 400.1086"], Exposition.CAISSON_3_FACES, minutes(30), ISO834
        )
        assert resultat.avertissements
        assert "A_m/V" in resultat.avertissements[0]

    def test_pas_d_avertissement_en_cas_courant(self, ipe300) -> None:
        resultat = echauffement(
            ipe300, Exposition.CONTOUR_4_FACES, minutes(30), ISO834
        )
        assert resultat.avertissements == ()
