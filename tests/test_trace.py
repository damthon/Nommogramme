"""Tracés du nomogramme, de l'échauffement et de la coupe de section.

Un test ne peut pas juger qu'une figure est *belle* — cela a demandé de la
regarder. Il peut vérifier qu'elle se produit sans erreur pour les cas de
figure qui diffèrent structurellement (protégé ou non, vérification croisée
mordante ou non, élément qui ne tient pas), que les séries et annotations
attendues y sont, et que les couleurs employées sont bien celles de la palette
validée.

Il peut aussi, et c'est nouveau, vérifier qu'elle est **lisible** au sens
mesurable du terme : deux textes qui se recouvrent forment deux rectangles qui
s'intersectent, et un texte qui déborde du cadre en sort. Ces deux défauts
s'étaient produits — « 674 °C à R180 » posé sur la ligne de θ_cr, « t_fi,d =
169 min » sorti du cadre — et ils ne dépendaient pas du code mais des chiffres,
donc du cas traité. C'est pourquoi ``TestLisibilite`` balaie une dizaine de cas
plutôt qu'un seul.
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
    tracer_section,
)
from nommogramme.nomogramme.verification import verifier
from nommogramme.profils import (
    Exposition,
    FaceCouverte,
    SectionCaisson,
    SectionH,
    charger_csv,
)

_CAISSON = SectionCaisson(h=0.400, b=0.300, tf=0.020, tw=0.012)
_H_SYMETRIQUE = SectionH(
    h=0.600, tw=0.010, b_sup=0.300, tf_sup=0.020, b_inf=0.300, tf_inf=0.020
)
_H_ASYMETRIQUE = SectionH(
    h=0.600, tw=0.010, b_sup=0.300, tf_sup=0.020, b_inf=0.200, tf_inf=0.015
)


@pytest.fixture(scope="module")
def cat():
    return charger_csv()


@pytest.fixture(autouse=True)
def _fermer_les_figures():
    """Referme les figures laissées ouvertes par un test.

    ``tracer_*`` appelé sans chemin rend la figure sans la fermer — c'est ce
    qu'attendent les interfaces graphiques, qui l'affichent. Dans une suite de
    tests, cela accumule des dizaines de figures dans le registre de pyplot,
    jusqu'à l'avertissement de fuite de mémoire.
    """
    yield
    import matplotlib.pyplot as plt

    plt.close("all")


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


class TestCoupeDeSection:
    """Le dessin d'une section soudée.

    Son intérêt tient entièrement à l'échelle : une saisie fautive d'un
    facteur dix doit sauter aux yeux. Un dessin étiré ne le montrerait pas,
    d'où le contrôle explicite du rapport d'aspect.
    """

    def test_echelle_respectee(self) -> None:
        figure = tracer_section(_CAISSON)
        axes = figure.axes[0]
        assert axes.get_aspect() == 1.0

    def test_une_tole_par_plaque(self) -> None:
        """Chaque tôle est dessinée séparément : c'est ce qu'est un assemblage."""
        from matplotlib.patches import Rectangle

        figure = tracer_section(_CAISSON)
        rectangles = [
            forme for forme in figure.axes[0].patches
            if isinstance(forme, Rectangle)
        ]
        assert len(rectangles) == len(_CAISSON.plaques())

    def test_les_dimensions_sont_cotees(self) -> None:
        figure = tracer_section(_H_ASYMETRIQUE)
        textes = " ".join(
            t.get_text() for axes in figure.axes for t in axes.texts
        )
        assert "h = 600" in textes
        assert "t_w = 10" in textes
        assert "t_f,sup = 20" in textes
        assert "t_f,inf = 15" in textes

    def test_les_semelles_inegales_sont_cotees_separement(self) -> None:
        textes = " ".join(
            t.get_text() for axes in tracer_section(_H_ASYMETRIQUE).axes
            for t in axes.texts
        )
        assert "b_sup = 300" in textes
        assert "b_inf = 200" in textes

    def test_les_semelles_egales_ne_le_sont_pas(self) -> None:
        """Une cote qui ne distingue rien encombre le dessin pour rien."""
        textes = " ".join(
            t.get_text() for axes in tracer_section(_H_SYMETRIQUE).axes
            for t in axes.texts
        )
        assert "b_sup" not in textes
        assert "b = 300" in textes

    @pytest.mark.parametrize(
        "face,attendu",
        [(FaceCouverte.SUPERIEURE, "supérieure"), (FaceCouverte.INFERIEURE, "inférieure")],
    )
    def test_la_dalle_est_figuree_sur_la_bonne_face(self, face, attendu: str) -> None:
        """La question que l'utilisateur doit pouvoir trancher d'un regard."""
        from dataclasses import replace

        section = replace(_H_ASYMETRIQUE, face_couverte=face)
        figure = tracer_section(section, exposition=Exposition.CONTOUR_3_FACES)
        axes = figure.axes[0]
        textes = " ".join(t.get_text() for t in axes.texts)
        assert "dalle" in textes
        assert f"dalle sur la semelle {attendu}" in textes

        # La dalle est du bon côté de la section, et pas seulement nommée.
        hauteurs = [
            forme.get_y() for forme in axes.patches
            if forme.get_hatch()
        ]
        assert len(hauteurs) == 1
        if face is FaceCouverte.SUPERIEURE:
            assert hauteurs[0] >= section.h * 1e3
        else:
            assert hauteurs[0] < 0.0

    def test_sans_exposition_pas_de_dalle(self) -> None:
        axes = tracer_section(_H_ASYMETRIQUE).axes[0]
        assert not [forme for forme in axes.patches if forme.get_hatch()]

    def test_sur_quatre_faces_pas_de_dalle(self) -> None:
        axes = tracer_section(
            _H_ASYMETRIQUE, exposition=Exposition.CONTOUR_4_FACES
        ).axes[0]
        assert not [forme for forme in axes.patches if forme.get_hatch()]

    @pytest.mark.parametrize("theme", ["clair", "sombre"])
    def test_ecrit_un_fichier(self, tmp_path, theme: str) -> None:
        destination = tmp_path / f"section_{theme}.png"
        assert tracer_section(_CAISSON, destination, theme=theme) == destination
        assert destination.stat().st_size > 5_000

    @pytest.mark.parametrize(
        "section",
        [
            SectionCaisson(h=0.250, b=0.600, tf=0.025, tw=0.015),   # plus large que haut
            SectionCaisson(h=1.200, b=0.200, tf=0.020, tw=0.010),   # très élancé
            SectionH(h=1.500, tw=0.012, b_sup=0.400, tf_sup=0.030,
                     b_inf=0.250, tf_inf=0.020),
        ],
        ids=["aplati", "elance", "grand_monosymetrique"],
    )
    def test_proportions_extremes(self, section, tmp_path) -> None:
        """Le dessin doit tenir quelles que soient les proportions saisies."""
        destination = tmp_path / "extreme.png"
        tracer_section(section, destination, exposition=Exposition.CONTOUR_3_FACES)
        assert destination.exists()


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


# --- lisibilité ---------------------------------------------------------------


def _boites(figure) -> list[tuple[str, object]]:
    """Les rectangles occupés par les annotations, en pixels de rendu.

    Seules les annotations posées par le code sont retenues : les graduations
    et les titres sont placés par matplotlib, qui gère lui-même leur
    encombrement.
    """
    from matplotlib.text import Annotation

    rendu = figure.canvas.get_renderer()
    boites = []
    for axes in figure.axes:
        for texte in axes.texts:
            if not isinstance(texte, Annotation) or not texte.get_text().strip():
                continue
            boites.append((texte.get_text(), texte.get_window_extent(rendu)))
    return boites


def _paires_qui_se_recouvrent(figure) -> list[tuple[str, str]]:
    boites = _boites(figure)
    fautives = []
    for indice, (texte, boite) in enumerate(boites):
        for autre_texte, autre in boites[indice + 1 :]:
            if boite.overlaps(autre):
                fautives.append((texte, autre_texte))
    return fautives


def _debordements(figure) -> list[str]:
    """Les annotations qui sortent du canevas — invisibles à l'affichage.

    Un enregistrement en « bbox_inches="tight" » les rattraperait en
    agrandissant l'image ; un canevas Tk ou une page web, non. C'est donc au
    cadre de la figure qu'on les compare, et pas à celui des axes.
    """
    from matplotlib.transforms import Bbox

    largeur, hauteur = figure.canvas.get_width_height()
    cadre = Bbox.from_bounds(0.0, 0.0, largeur, hauteur)
    dehors = []
    for texte, boite in _boites(figure):
        if not (
            boite.x0 >= cadre.x0 - 1.0 and boite.x1 <= cadre.x1 + 1.0
            and boite.y0 >= cadre.y0 - 1.0 and boite.y1 <= cadre.y1 + 1.0
        ):
            dehors.append(texte)
    return dehors


# Les cas se distinguent par la position des annotations, pas par la physique :
# un élément qui tient longtemps pousse « t_fi,d » au bord droit, un élément
# très protégé fait passer la marge sur la ligne de θ_cr, un élément surchargé
# empile « acier » et « t_fi,d » à l'origine.
_CAS_DE_LISIBILITE = {
    "courant": {},
    "peu_sollicite": {"cas": CasDeCharge(N_fi_Ed=50e3, My_fi_Ed=5e3, L=4.0,
                                         l_fi_y=2.0, l_fi_z=2.0)},
    "surcharge": {"profil_nom": "IPE 200", "cas": CasDeCharge(
        N_fi_Ed=400e3, My_fi_Ed=60e3, L=6.0, l_fi_y=6.0, l_fi_z=6.0)},
    "elance": {"cas": CasDeCharge(N_fi_Ed=850e3, My_fi_Ed=120e3, L=8.0,
                                  l_fi_y=8.0, l_fi_z=8.0, beta_M_y=1.4)},
    "traction": {"cas": CasDeCharge(N_fi_Ed=-300e3, My_fi_Ed=30e3, L=5.0,
                                    l_fi_y=5.0, l_fi_z=5.0)},
    "protege_long": {
        "protection": lambda: Protection.depuis_catalogue("flocage_fibreux", d_p=0.025),
        "duree_requise_min": 180,
    },
    "protege_court": {
        "profil_nom": "HEA 100",
        "protection": lambda: Protection.depuis_catalogue("plaques_platre", d_p=0.015),
        "duree_requise_min": 15,
        "cas": CasDeCharge(N_fi_Ed=100e3, My_fi_Ed=5e3, L=3.0, l_fi_y=3.0, l_fi_z=3.0),
    },
    "tres_protege": {
        "profil_nom": "HEB 400",
        "protection": lambda: Protection.depuis_catalogue("plaques_silicate", d_p=0.020),
        "duree_requise_min": 120,
        "exposition": Exposition.CAISSON_4_FACES,
        "cas": CasDeCharge(N_fi_Ed=1200e3, My_fi_Ed=150e3, L=4.0,
                           l_fi_y=2.0, l_fi_z=2.0, beta_M_y=1.4),
    },
    "profil_creux": {
        "profil_nom": "RRW 200/200/8",
        "cas": CasDeCharge(N_fi_Ed=600e3, My_fi_Ed=40e3, L=4.0,
                           l_fi_y=4.0, l_fi_z=4.0),
    },
    "classe_4": {
        "profil_nom": "HEA 1000",
        "cas": CasDeCharge(N_fi_Ed=2000e3, L=3.0, l_fi_y=3.0, l_fi_z=3.0),
    },
    "hydrocarbure": {"profil_nom": "HEM 300", "feu": "hydrocarbure"},
}


def _cas_de_lisibilite(cat, nom: str):
    from nommogramme.thermique.courbes import COURBES

    reglages = dict(_CAS_DE_LISIBILITE[nom])
    remplacements = {}
    if "profil_nom" in reglages:
        remplacements["profil"] = cat[reglages.pop("profil_nom")]
    if "feu" in reglages:
        remplacements["courbe"] = COURBES[reglages.pop("feu")]
    if "protection" in reglages:
        remplacements["protection"] = reglages.pop("protection")()
    remplacements.update(reglages)
    return _verification(cat, **remplacements)


class TestLisibilite:
    """Aucune annotation ne doit en recouvrir une autre, ni sortir du cadre.

    Le placeur essaie plusieurs positions et retient la première qui convient.
    Ces tests vérifient qu'il en trouve toujours une, sur des cas choisis pour
    la difficulté de leur mise en page — pas pour leur intérêt mécanique.
    """

    @pytest.mark.parametrize("nom", sorted(_CAS_DE_LISIBILITE))
    def test_nomogramme(self, cat, nom: str) -> None:
        import matplotlib.pyplot as plt

        figure = tracer_nomogramme(_cas_de_lisibilite(cat, nom))
        figure.canvas.draw()
        try:
            assert _paires_qui_se_recouvrent(figure) == []
            assert _debordements(figure) == []
        finally:
            plt.close(figure)

    @pytest.mark.parametrize("nom", sorted(_CAS_DE_LISIBILITE))
    def test_echauffement(self, cat, nom: str) -> None:
        import matplotlib.pyplot as plt

        figure = tracer_echauffement(_cas_de_lisibilite(cat, nom))
        figure.canvas.draw()
        try:
            assert _paires_qui_se_recouvrent(figure) == []
            assert _debordements(figure) == []
        finally:
            plt.close(figure)

    def test_les_annotations_portent_un_lisere(self, nu) -> None:
        """Le dernier recours quand aucune position n'est libre.

        Sans lui, un texte posé faute de mieux sur une courbe en devient
        illisible — c'est exactement ce qui se passait pour « t_fi,d » sur la
        courbe d'acier.
        """
        from matplotlib.text import Annotation

        figure = tracer_nomogramme(nu)
        annotations = [
            texte for axes in figure.axes for texte in axes.texts
            if isinstance(texte, Annotation) and texte.get_text().strip()
        ]
        assert annotations
        assert all(texte.get_path_effects() for texte in annotations)

    def test_le_placeur_ecarte_un_texte_d_une_courbe(self, cat) -> None:
        """Contrôle direct du mécanisme, indépendamment d'une figure entière."""
        import matplotlib.pyplot as plt

        from nommogramme.nomogramme.trace import CLAIR, Placeur

        figure, axes = plt.subplots(figsize=(4.0, 3.0))
        axes.set_xlim(0.0, 1.0)
        axes.set_ylim(0.0, 1.0)
        placeur = Placeur(axes, CLAIR)
        # Un trait vertical un peu à droite du point d'ancrage : la première
        # position, qui écrit vers la droite, tombe dessus ; la seconde, qui
        # écrit vers la gauche, doit être retenue.
        placeur.eviter_verticale(0.6)
        annotation = placeur.poser(
            "un texte assez long", xy=(0.5, 0.5),
            candidats=((10, 0, "left", "center"), (-10, 0, "right", "center")),
        )
        assert annotation.get_position() == (-10, 0)
        plt.close(figure)

    def test_le_placeur_garde_la_premiere_position_si_elle_convient(self) -> None:
        import matplotlib.pyplot as plt

        from nommogramme.nomogramme.trace import CLAIR, Placeur

        figure, axes = plt.subplots(figsize=(4.0, 3.0))
        axes.set_xlim(0.0, 1.0)
        axes.set_ylim(0.0, 1.0)
        placeur = Placeur(axes, CLAIR)
        annotation = placeur.poser(
            "essai", xy=(0.5, 0.5),
            candidats=((10, 0, "left", "center"), (-10, 0, "right", "center")),
        )
        assert annotation.get_position() == (10, 0)
        plt.close(figure)
