"""Tracés du nomogramme et de l'échauffement.

Un test ne peut pas juger qu'une figure est lisible — cela a demandé de la
regarder. Ce qu'il peut vérifier : que la figure se produit sans erreur pour
les cas de figure qui diffèrent structurellement (protégé ou non,
vérification croisée mordante ou non, élément qui ne tient pas), que les
séries et annotations attendues y sont, et que les couleurs employées sont
bien celles de la palette validée.
"""

from __future__ import annotations

import pytest

matplotlib = pytest.importorskip(
    "matplotlib", reason="le tracé demande l'extra [trace]"
)

from nommogramme.materiaux.acier import Nuance
from nommogramme.materiaux.protection import Protection
from nommogramme.mecanique.actions import CasDeCharge
from nommogramme.nomogramme.trace import (
    CLAIR,
    SOMBRE,
    Palette,
    tracer_abaque,
    tracer_echauffement,
    tracer_nomogramme,
)
from nommogramme.nomogramme.verification import verifier
from nommogramme.profils import Exposition, charger_csv


@pytest.fixture(scope="module")
def cat():
    return charger_csv()


def _verification(cat, **remplacements):
    parametres = dict(
        profil=cat["HEB 300"],
        nuance=Nuance.S355,
        cas=CasDeCharge(
            N_fi_Ed=850e3, My_fi_Ed=120e3, L=4.0,
            l_fi_y=2.0, l_fi_z=2.0, beta_M_y=1.4,
        ),
        exposition=Exposition.CONTOUR_4_FACES,
        duree_requise_min=60,
    )
    parametres.update(remplacements)
    return verifier(**parametres)


@pytest.fixture(scope="module")
def nu(cat):
    return _verification(cat)


@pytest.fixture(scope="module")
def protege(cat):
    return _verification(
        cat, protection=Protection.depuis_catalogue("flocage_fibreux", d_p=0.025)
    )


@pytest.fixture(scope="module")
def elance(cat):
    """Cas où la vérification croisée abaisse nettement la température."""
    return _verification(
        cat,
        cas=CasDeCharge(
            N_fi_Ed=850e3, My_fi_Ed=120e3, L=8.0,
            l_fi_y=8.0, l_fi_z=8.0, beta_M_y=1.4,
        ),
    )


class TestProduction:
    @pytest.mark.parametrize("theme", ["clair", "sombre"])
    def test_nomogramme_ecrit_un_fichier(self, nu, tmp_path, theme: str) -> None:
        destination = tmp_path / f"nomo_{theme}.png"
        assert tracer_nomogramme(nu, destination, theme=theme) == destination
        assert destination.stat().st_size > 10_000

    def test_echauffement_ecrit_un_fichier(self, protege, tmp_path) -> None:
        destination = tmp_path / "ech.png"
        assert tracer_echauffement(protege, destination) == destination
        assert destination.stat().st_size > 10_000

    def test_abaque_sans_verification(self, cat, tmp_path) -> None:
        destination = tmp_path / "abaque.png"
        assert tracer_abaque(cat["IPE 300"], destination) == destination

    def test_repertoire_cree_au_besoin(self, nu, tmp_path) -> None:
        destination = tmp_path / "sous" / "dossier" / "nomo.png"
        tracer_nomogramme(nu, destination)
        assert destination.exists()

    def test_sans_chemin_renvoie_la_figure(self, nu) -> None:
        figure = tracer_nomogramme(nu)
        assert hasattr(figure, "savefig")

    @pytest.mark.parametrize("cas", ["nu", "protege", "elance"])
    def test_tous_les_cas_de_figure(self, request, cas: str, tmp_path) -> None:
        resultat = request.getfixturevalue(cas)
        tracer_nomogramme(resultat, tmp_path / f"{cas}.png")
        tracer_echauffement(resultat, tmp_path / f"{cas}_ech.png")

    def test_element_qui_ne_tient_pas_a_froid(self, cat, tmp_path) -> None:
        """μ₀ ≥ 1 : ni θ_cr nomogramme ni θ_cr exacte, le tracé doit tenir."""
        resultat = _verification(
            cat,
            profil=cat["IPE 200"],
            nuance=Nuance.S235,
            cas=CasDeCharge(N_fi_Ed=2000e3, L=6.0),
        )
        assert resultat.mu_0 >= 1.0
        tracer_nomogramme(resultat, tmp_path / "surcharge.png")


class TestContenu:
    def test_les_deux_series_sont_tracees(self, protege) -> None:
        figure = tracer_nomogramme(protege)
        droite = figure.axes[1]
        couleurs = {ligne.get_color() for ligne in droite.get_lines()}
        assert CLAIR.acier in couleurs
        assert CLAIR.gaz in couleurs

    def test_legende_nomme_les_series(self, protege) -> None:
        figure = tracer_nomogramme(protege)
        textes = [t.get_text() for t in figure.legends[0].get_texts()]
        assert any("HEB300" in t for t in textes)
        assert any("ISO 834" in t for t in textes)

    def test_etiquetage_direct_en_plus_de_la_legende(self, protege) -> None:
        figure = tracer_nomogramme(protege)
        annotations = _annotations(figure)
        assert "acier" in annotations
        assert "gaz" in annotations

    def test_le_decrochement_est_annote(self, elance) -> None:
        """L'écart entre les deux voies est le fait marquant de la figure."""
        assert elance.ecart_nomogramme > 50.0
        annotations = " ".join(_annotations(tracer_nomogramme(elance)))
        assert "vérification croisée" in annotations
        assert "retenus" in annotations

    def test_pas_de_decrochement_quand_les_voies_concordent(self, nu) -> None:
        assert abs(nu.ecart_nomogramme) < 10.0
        annotations = " ".join(_annotations(tracer_nomogramme(nu)))
        assert "vérification croisée" not in annotations

    def test_le_verdict_colore_le_point_de_croisement(self, cat) -> None:
        satisfait = _verification(
            cat, protection=Protection.depuis_catalogue("flocage_fibreux", d_p=0.025)
        )
        rate = _verification(cat)
        assert bool(satisfait.verdict) and not bool(rate.verdict)

        for resultat, attendue in ((satisfait, CLAIR.favorable), (rate, CLAIR.critique)):
            figure = tracer_echauffement(resultat)
            marqueurs = [
                ligne.get_color()
                for ligne in figure.axes[0].get_lines()
                if ligne.get_marker() == "o"
            ]
            assert marqueurs == [attendue], (
                "le repère de verdict doit être présent et de la bonne couleur"
            )

    def test_axe_des_temperatures_partage(self, protege) -> None:
        figure = tracer_nomogramme(protege)
        gauche, droite = figure.axes[0], figure.axes[1]
        assert gauche.get_ylim() == droite.get_ylim()
        # Une seule graduation de température, portée par le quadrant gauche.
        assert gauche.get_yticklabels()
        assert not droite.get_yticklabels()

    def test_axe_mu_0_inverse(self, protege) -> None:
        """μ₀ croît vers la gauche pour que l'axe θ reste au centre."""
        gauche = tracer_nomogramme(protege).axes[0]
        debut, fin = gauche.get_xlim()
        assert debut > fin


class TestPalette:
    def test_deux_themes_disponibles(self) -> None:
        assert CLAIR.fond != SOMBRE.fond
        assert CLAIR.encre != SOMBRE.encre

    def test_couleurs_de_serie_de_la_palette_validee(self) -> None:
        """Emplacements 1 et 2, validés pour la déficience de vision des couleurs."""
        assert (CLAIR.acier, CLAIR.gaz) == ("#2a78d6", "#eb6834")
        assert (SOMBRE.acier, SOMBRE.gaz) == ("#3987e5", "#d95926")

    def test_theme_inconnu_refuse(self, nu) -> None:
        with pytest.raises(ValueError, match="Thème"):
            tracer_nomogramme(nu, theme="fluo")

    def test_palette_personnalisee_acceptee(self, nu, tmp_path) -> None:
        from dataclasses import replace

        perso = replace(CLAIR, acier="#123456")
        figure = tracer_nomogramme(nu, theme=perso)
        couleurs = {ligne.get_color() for ligne in figure.axes[1].get_lines()}
        assert "#123456" in couleurs


def _annotations(figure) -> list[str]:
    textes: list[str] = []
    for axes in figure.axes:
        textes.extend(
            enfant.get_text()
            for enfant in axes.texts
            if hasattr(enfant, "get_text")
        )
    return textes
