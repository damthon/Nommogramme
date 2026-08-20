"""Interface graphique Streamlit.

Ce que ces tests garantissent : que l'application démarre, qu'elle réagit aux
saisies, et surtout **qu'elle n'invente rien**. Le contrôle central est celui
de cohérence : pour un même jeu de paramètres, l'écran doit afficher très
exactement ce que ``verifier()`` renvoie. C'est la traduction en test de la
contrainte de conception — l'interface est une couche de présentation, pas un
second moteur de calcul.

Ils ne disent rien de l'ergonomie ni de la lisibilité, qui demandent de
regarder l'écran.
"""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit", reason="l'interface demande l'extra [ui]")
pytest.importorskip("matplotlib", reason="les figures demandent l'extra [trace]")

from streamlit.testing.v1 import AppTest

from nommogramme.interface import chemin_application, lancer
from nommogramme.materiaux.acier import Nuance
from nommogramme.materiaux.protection import Protection
from nommogramme.mecanique.actions import CasDeCharge
from nommogramme.nomogramme.verification import verifier
from nommogramme.profils import Exposition, charger_csv

_DELAI = 300


def _application() -> AppTest:
    application = AppTest.from_file(str(chemin_application()), default_timeout=_DELAI)
    application.run()
    return application


@pytest.fixture(scope="module")
def app() -> AppTest:
    """Application au démarrage, partagée — **à ne pas modifier**.

    Tout test qui agit sur un widget doit se créer sa propre instance avec
    ``_application()`` : la portée « module » fait que la mutation fuiterait
    vers les tests suivants.
    """
    return _application()


def _metrique(application: AppTest, libelle: str) -> str:
    for element in application.metric:
        if element.label == libelle:
            return element.value
    raise AssertionError(
        f"Métrique « {libelle} » absente. Présentes : "
        f"{[e.label for e in application.metric]}"
    )


def _alertes(application: AppTest) -> str:
    return " ".join(
        [e.value for e in application.success]
        + [e.value for e in application.error]
        + [e.value for e in application.warning]
    )


class TestDemarrage:
    def test_l_application_demarre_sans_erreur(self, app: AppTest) -> None:
        assert not app.exception, app.exception

    def test_le_titre_est_present(self, app: AppTest) -> None:
        assert [e.value for e in app.title] == ["Nommogramme"]

    def test_le_chemin_designe_un_fichier_existant(self) -> None:
        assert chemin_application().is_file()
        assert chemin_application().suffix == ".py"

    def test_lancer_est_exportee(self) -> None:
        assert callable(lancer)


class TestSaisie:
    def test_tous_les_parametres_sont_saisissables(self, app: AppTest) -> None:
        """Chaque paramètre de verifier() doit avoir son widget."""
        attendus = {
            "famille", "profil", "nuance", "N", "My", "Mz", "L", "l_fi",
            "maintien", "beta_M", "exposition", "feu", "duree", "produit",
            "contexte", "kappa_1", "kappa_2", "C1",
        }
        presents = set(app.session_state.filtered_state)
        assert attendus <= presents, f"widgets manquants : {attendus - presents}"

    def test_le_profil_par_defaut_est_raisonnable(self, app: AppTest) -> None:
        """Le premier profilé d'une famille est le plus petit : sous les charges
        par défaut, il donnerait un μ₀ absurde dès l'ouverture."""
        assert app.session_state["profil"] == "HEB300"
        assert float(_metrique(app, "μ₀")) < 1.0

    def test_l_epaisseur_n_apparait_qu_avec_une_protection(self) -> None:
        # Instance propre : la fixture « app » est partagée par tout le module,
        # et la modifier ici fausserait les tests de cohérence qui suivent.
        application = _application()
        assert "dp" not in application.session_state.filtered_state
        application.sidebar.selectbox(key="produit").set_value("flocage_fibreux").run()
        assert "dp" in application.session_state.filtered_state


class TestCoherenceAvecLaBibliotheque:
    """L'écran doit afficher ce que verifier() renvoie, sans écart."""

    def test_cas_par_defaut(self, app: AppTest) -> None:
        attendu = verifier(
            profil=charger_csv()["HEB300"],
            nuance=Nuance.S355,
            cas=CasDeCharge(
                N_fi_Ed=850e3, My_fi_Ed=120e3, L=4.0,
                l_fi_y=2.0, l_fi_z=2.0,
                beta_M_y=1.4, beta_M_z=1.4, beta_M_LT=1.4,
            ),
            exposition=Exposition.CONTOUR_4_FACES,
            duree_requise_min=60.0,
        )
        assert _metrique(app, "μ₀") == f"{attendu.mu_0:.3f}"
        assert _metrique(app, "θ_cr retenue") == f"{attendu.theta_cr:.0f} °C"
        assert _metrique(app, "θ_a à R60") == f"{attendu.theta_a_a_echeance:.0f} °C"

    def test_cas_protege(self) -> None:
        application = _application()
        application.sidebar.selectbox(key="produit").set_value("flocage_fibreux").run()
        application.sidebar.number_input(key="dp").set_value(25.0).run()

        attendu = verifier(
            profil=charger_csv()["HEB300"],
            nuance=Nuance.S355,
            cas=CasDeCharge(
                N_fi_Ed=850e3, My_fi_Ed=120e3, L=4.0,
                l_fi_y=2.0, l_fi_z=2.0,
                beta_M_y=1.4, beta_M_z=1.4, beta_M_LT=1.4,
            ),
            exposition=Exposition.CONTOUR_4_FACES,
            duree_requise_min=60.0,
            protection=Protection.depuis_catalogue("flocage_fibreux", d_p=0.025),
        )
        assert attendu.verdict, "le cas de contrôle devrait être satisfait"
        assert _metrique(application, "θ_a à R60") == (
            f"{attendu.theta_a_a_echeance:.0f} °C"
        )
        assert "satisfait" in _alertes(application)


class TestReactions:
    def test_la_protection_renverse_le_verdict(self) -> None:
        application = _application()
        assert "non satisfait" in _alertes(application)

        application.sidebar.selectbox(key="produit").set_value("flocage_fibreux").run()
        application.sidebar.number_input(key="dp").set_value(25.0).run()
        alertes = _alertes(application)
        assert "satisfait" in alertes and "non satisfait" not in alertes

    def test_allonger_le_flambement_declenche_l_avertissement(self) -> None:
        """Le nomogramme devient non conservatif : l'écran doit le dire."""
        application = _application()
        application.sidebar.number_input(key="L").set_value(8.0).run()
        application.sidebar.number_input(key="l_fi").set_value(8.0).run()
        assert "non conservatif" in _alertes(application)

    def test_element_surcharge_signale_sans_planter(self) -> None:
        application = _application()
        application.sidebar.number_input(key="N").set_value(9000.0).run()
        assert not application.exception
        assert "ne tient pas à 20 °C" in _alertes(application)

    def test_changer_de_referentiel(self) -> None:
        application = _application()
        application.sidebar.selectbox(key="contexte").set_value(
            "Eurocode — valeurs recommandées"
        ).run()
        assert not application.exception

    def test_changer_de_famille_change_la_liste_des_profiles(self) -> None:
        application = _application()
        application.sidebar.selectbox(key="famille").set_value("IPE").run()
        assert application.session_state["profil"].startswith("IPE")
        assert not application.exception


class TestRestitution:
    def test_les_deux_figures_sont_presentes(self, app: AppTest) -> None:
        assert len(app.tabs) == 2

    def test_les_deux_temperatures_critiques_sont_affichees(self, app: AppTest) -> None:
        assert _metrique(app, "Nomogramme — éq. (4.22)").endswith("°C")
        assert _metrique(app, "Vérification croisée — §4.2.3").endswith("°C")

    def test_la_note_de_calcul_est_telechargeable(self, app: AppTest) -> None:
        boutons = app.get("download_button")
        assert len(boutons) == 1
        assert "note de calcul" in boutons[0].label.lower()

    def test_l_avertissement_de_validation_est_affiche(self, app: AppTest) -> None:
        """La validation est partielle : l'écran doit dire où elle s'arrête.

        L'avertissement a changé de contenu à mesure que la validation
        avançait ; ce qu'il doit toujours porter, c'est le statut de l'outil,
        le nom de ce qui n'est pas validé, et le renvoi au rapport.
        """
        legendes = " ".join(e.value for e in app.caption)
        assert "développement" in legendes
        assert "déversement" in legendes
        assert "N + M" in legendes
        assert "validation.md" in legendes
