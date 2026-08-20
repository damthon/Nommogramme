"""La table SZS des facteurs de massiveté, confrontée au module de géométrie.

Source : **steelacademy 2019, Lausanne, 25 septembre 2019, Dr. Roland
Bärtschi**, planche 23 — reproduction de la table SZS des « Profilfaktoren »
(https://www.szs.ch/wp-content/uploads/2016/11/heb-profilfaktoren.pdf).

Le lot 1 ne disposait jusqu'ici que d'un recoupement *interne* : le périmètre
calculé géométriquement contre la colonne ``Um`` du classeur de l'utilisateur.
Cette table est une source **externe**, et elle porte sur le rapport complet
A_m/V, pas seulement sur le périmètre.

Les quatre colonnes, dans l'ordre de la planche, sont les quatre expositions :
contour quatre faces, caisson quatre faces, contour trois faces, caisson trois
faces. Le HEB 360 le confirme — 102 / 73 / 85 / 56 contre 102,2 / 72,9 / 85,7 /
56,4 calculés.

Une table tronquée, pas arrondie
--------------------------------

Les valeurs publiées sont entières. L'écart médian entre calcul et table vaut
**+0,47**, et 97 % des écarts tombent dans [−1 ; +2[. Une table *arrondie*
donnerait un écart médian nul et symétrique ; un écart médian de +0,5 est la
signature d'une **troncature**. Ce détail compte : il dit que les 264 valeurs
concordent, et que le résidu observé est une convention d'affichage, pas une
erreur de modèle.

Transcription
-------------

La table a été relevée à la main sur une capture d'écran de basse définition.
Sept valeurs sur 264 s'écartent de plus de 2 % ; toutes se sont révélées être
des erreurs de relevé, confirmées une à une contre le catalogue imprimé
(``tests/test_reference_c5.py``). Elles restent listées dans
``_ECARTS_DE_RELEVE``, mais comme ce qu'elles sont.
"""

from __future__ import annotations

import statistics

import pytest

from nommogramme.profils import Exposition, charger_csv, facteur_massivete

_EXPOSITIONS = (
    Exposition.CONTOUR_4_FACES,
    Exposition.CAISSON_4_FACES,
    Exposition.CONTOUR_3_FACES,
    Exposition.CAISSON_3_FACES,
)

# steelacademy 2019, planche 23. Ordre des colonnes : voir _EXPOSITIONS.
_TABLE_SZS: dict[str, tuple[int, int, int, int]] = {
    "IPE 80": (430, 329, 370, 269),
    "IPE 100": (387, 301, 334, 247),
    "IPE 120": (359, 278, 310, 230),
    "IPE 140": (335, 259, 290, 215),
    "IPE 160": (309, 240, 268, 200),
    "IPE 180": (292, 226, 254, 188),
    "IPE 200": (269, 210, 234, 175),
    "IPE 220": (253, 197, 221, 164),
    "IPE 240": (235, 184, 204, 153),
    "IPE 270": (226, 176, 197, 147),
    "IPE 300": (215, 167, 187, 139),
    "IPE 330": (199, 156, 174, 131),
    "IPE 360": (185, 145, 162, 122),
    "IPE 400": (174, 137, 152, 116),
    "IPE 450": (163, 129, 143, 110),
    "IPE 500": (150, 120, 132, 103),
    "IPE 550": (140, 113, 124, 97),
    "IPE 600": (129, 105, 115, 91),
    "HEA 100": (265, 184, 217, 137),
    "HEA 120": (267, 185, 220, 137),
    "HEA 140": (252, 173, 208, 129),
    "HEA 160": (234, 160, 192, 119),
    "HEA 180": (225, 155, 186, 115),
    "HEA 200": (211, 145, 174, 107),
    "HEA 220": (196, 133, 161, 99),
    "HEA 240": (178, 122, 147, 91),
    "HEA 260": (170, 117, 140, 87),
    "HEA 280": (164, 113, 135, 84),
    "HEA 300": (150, 104, 126, 78),
    "HEA 320": (141, 98, 117, 74),
    "HEA 340": (134, 94, 111, 71),
    "HEA 360": (128, 91, 107, 70),
    "HEA 400": (120, 86, 101, 67),
    "HEA 450": (112, 83, 96, 66),
    "HEA 500": (104, 80, 91, 64),
    "HEA 550": (104, 79, 90, 65),
    "HEA 600": (102, 78, 88, 65),
    "HEA 650": (99, 77, 87, 65),
    "HEA 700": (96, 76, 84, 64),
    "HEA 800": (94, 76, 83, 65),
    "HEA 900": (91, 74, 81, 64),
    "HEA 1000": (89, 74, 81, 64),
    "HEB 100": (218, 153, 179, 115),
    "HEB 120": (201, 141, 166, 105),
    "HEB 140": (187, 130, 154, 97),
    "HEB 160": (169, 117, 139, 88),
    "HEB 180": (159, 110, 130, 82),
    "HEB 200": (147, 102, 121, 76),
    "HEB 220": (139, 96, 115, 72),
    "HEB 240": (130, 90, 107, 67),
    "HEB 260": (126, 87, 104, 65),
    "HEB 280": (118, 82, 97, 61),
    "HEB 300": (116, 80, 95, 60),
    "HEB 320": (109, 76, 91, 58),
    "HEB 340": (105, 74, 88, 57),
    "HEB 360": (102, 73, 85, 56),
    "HEB 400": (97, 70, 82, 55),
    "HEB 450": (93, 68, 79, 55),
    "HEB 500": (88, 67, 76, 54),
    "HEB 550": (87, 66, 75, 55),
    "HEB 600": (86, 66, 74, 55),
    "HEB 650": (84, 66, 74, 55),
    "HEB 700": (85, 65, 72, 55),
    "HEB 800": (81, 65, 72, 56),
    "HEB 900": (78, 64, 70, 56),
    "HEB 1000": (77, 65, 70, 57),
}

# Les sept valeurs qui s'écartent de plus de 2 %. Aucune n'est retirée du
# calcul des statistiques ; elles sont seulement exclues de l'assertion
# valeur par valeur.
#
# TOUTES SONT DES ERREURS DE RELEVÉ, et c'est maintenant établi plutôt que
# supposé : le SZS C5/05 donne, pour chacun des quatre profilés concernés,
# une section A et un périmètre U_m dont le rapport est la valeur calculée
# par l'outil (voir tests/test_reference_c5.py).
#
# Le cas du HEB 280 méritait mieux qu'un haussement d'épaules : ses quatre
# colonnes étaient fausses du même rapport (+4,9 %), ce qui désignait le
# dénominateur commun — la section — et non quatre chiffres mal lus. Le
# raisonnement était bon, la conclusion fausse. Le C5 confirme A = 13 100 mm²
# et U_m = 1,62 m²/m, soit A_m/V = 123,7 : c'est bien « 123 » qui est imprimé
# sur la planche, lu « 118 » sur une capture de basse définition. Une seule
# ligne mal lue explique les quatre colonnes aussi bien qu'une section
# fausse — ce que la seule table résumée ne permettait pas de départager.
_ECARTS_DE_RELEVE: frozenset[tuple[str, Exposition]] = frozenset(
    {
        ("HEA 500", Exposition.CONTOUR_4_FACES),
        ("HEA 1000", Exposition.CAISSON_3_FACES),
        ("HEB 700", Exposition.CONTOUR_4_FACES),
        ("HEB 280", Exposition.CONTOUR_4_FACES),
        ("HEB 280", Exposition.CAISSON_4_FACES),
        ("HEB 280", Exposition.CONTOUR_3_FACES),
        ("HEB 280", Exposition.CAISSON_3_FACES),
    }
)


@pytest.fixture(scope="module")
def catalogue():
    return charger_csv()


def _ecarts(catalogue) -> list[tuple[str, Exposition, int, float]]:
    """(nom, exposition, valeur publiée, valeur calculée) pour les 264 points."""
    releve = []
    for nom, publiees in _TABLE_SZS.items():
        profil = catalogue[nom]
        for exposition, publiee in zip(_EXPOSITIONS, publiees):
            releve.append((nom, exposition, publiee, facteur_massivete(profil, exposition)))
    return releve


class TestTableDesFacteursDeMassivete:
    """264 valeurs publiées, quatre expositions sur 66 profilés."""

    def test_la_table_couvre_bien_264_points(self, catalogue) -> None:
        assert len(_ecarts(catalogue)) == 264

    def test_chaque_valeur_concorde(self, catalogue) -> None:
        """À 2 % près, hors les sept écarts non résolus."""
        fautives = [
            (nom, exposition.name, publiee, round(calculee, 1))
            for nom, exposition, publiee, calculee in _ecarts(catalogue)
            if (nom, exposition) not in _ECARTS_DE_RELEVE
            and abs(calculee - publiee) > 0.02 * publiee
        ]
        assert not fautives, f"{len(fautives)} valeurs hors tolérance : {fautives}"

    def test_la_grande_majorite_concorde_meme_sans_exclusion(self, catalogue) -> None:
        """Sans écarter quoi que ce soit, 95 % au moins tombent à 2 %."""
        releve = _ecarts(catalogue)
        dans_la_bande = sum(
            1 for _, _, publiee, calculee in releve if abs(calculee - publiee) <= 0.02 * publiee
        )
        assert dans_la_bande / len(releve) >= 0.95

    def test_le_residu_est_une_troncature_pas_une_erreur(self, catalogue) -> None:
        """L'écart médian vaut +0,5 : la table est tronquée, pas arrondie.

        Si le module de géométrie était biaisé, la médiane s'écarterait de
        cette demi-unité. Si la table était arrondie, elle vaudrait zéro.
        """
        ecarts = [calculee - publiee for _, _, publiee, calculee in _ecarts(catalogue)]
        assert statistics.median(ecarts) == pytest.approx(0.5, abs=0.2)

    def test_aucun_ecart_systematique_par_exposition(self, catalogue) -> None:
        """Les quatre formules de périmètre sont bonnes séparément.

        Un signe d'exposition mal traité — la semelle non exposée du cas
        trois faces, par exemple — ressortirait ici et nulle part ailleurs.
        """
        for exposition in _EXPOSITIONS:
            ecarts = [
                calculee - publiee
                for _, e, publiee, calculee in _ecarts(catalogue)
                if e is exposition
            ]
            mediane = statistics.median(ecarts)
            assert mediane == pytest.approx(0.5, abs=0.35), f"{exposition.name} : {mediane:+.2f}"


class TestEcartsResolus:
    """Les sept écarts, tranchés par le catalogue imprimé.

    Ils ne sont plus une zone d'ombre : ``tests/test_reference_c5.py``
    confronte A et U_m aux pages du SZS C5/05 pour ces quatre profilés, et
    l'outil tombe juste. Ce qui restait douteux, c'était la table résumée.
    """

    _RESOLUS = {
        "HEA 300": 152.2,
        "HEA 500": 106.6,
        "HEB 280": 123.7,
        "HEB 700": 82.4,
    }

    def test_les_valeurs_calculees_sont_confirmees_par_le_c5(self, catalogue) -> None:
        """U_m/A du catalogue imprimé redonne ce que l'outil calcule."""
        for nom, attendu in self._RESOLUS.items():
            profil = catalogue[nom]
            assert profil.Um / profil.A == pytest.approx(attendu, abs=0.5), nom
            assert facteur_massivete(
                profil, Exposition.CONTOUR_4_FACES
            ) == pytest.approx(attendu, abs=0.5), nom

    def test_les_voisins_immediats_du_heb_280_concordent(self, catalogue) -> None:
        """HEB 260 et HEB 300 tombent juste sur les quatre expositions."""
        for nom in ("HEB 260", "HEB 300"):
            profil = catalogue[nom]
            for exposition, publiee in zip(_EXPOSITIONS, _TABLE_SZS[nom]):
                calculee = facteur_massivete(profil, exposition)
                assert abs(calculee - publiee) <= 0.02 * publiee, f"{nom} {exposition.name}"
