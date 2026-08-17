"""Catalogue SZS et géométrie d'exposition — EN 1993-1-2 §4.2.5, tab. 4.2/4.3."""

from __future__ import annotations

import pytest

from nommogramme.profils import (
    AM_SUR_V_MINIMAL,
    Exposition,
    Famille,
    Forme,
    charger_csv,
    ecart_relatif_um,
    facteur_massivete,
    facteur_ombre,
    perimetre_expose,
)


@pytest.fixture(scope="module")
def cat():
    return charger_csv()


class TestCatalogue:
    def test_effectif_et_familles(self, cat) -> None:
        assert len(cat) == 277
        effectifs = {famille: len(cat.famille(famille)) for famille in Famille}
        assert effectifs == {
            Famille.IPE: 22,
            Famille.PEA: 16,
            Famille.INP: 20,
            Famille.HEA: 24,
            Famille.HEB: 24,
            Famille.HEM: 24,
            Famille.HHD: 31,
            Famille.HL: 8,
            Famille.RRW: 108,
        }

    def test_recherche_insensible_a_la_forme_du_nom(self, cat) -> None:
        reference = cat["HEB300"]
        for variante in ("HEB 300", "heb300", "heb-300", " HEB_300 "):
            assert cat[variante] is reference

    def test_profil_absent(self, cat) -> None:
        with pytest.raises(KeyError, match="IPE 999"):
            cat["IPE 999"]

    def test_dimensions_en_unites_si(self, cat) -> None:
        """IPE 300 : h = 300 mm, A = 53,8 cm², W_pl,y = 628 cm³."""
        ipe = cat["IPE 300"]
        assert ipe.h == pytest.approx(0.300)
        assert ipe.b == pytest.approx(0.150)
        assert ipe.tw == pytest.approx(0.0071)
        assert ipe.A == pytest.approx(53.8e-4, rel=1e-3)
        assert ipe.Iy == pytest.approx(8360e-8, rel=2e-3)
        assert ipe.Wply == pytest.approx(628e-6, rel=5e-3)
        # Le SZS tabule i_y à 125 mm ; les tables de profilés donnent 124,6 mm.
        assert ipe.iy == pytest.approx(0.1246, rel=5e-3)

    def test_masse_coherente_avec_la_section(self, cat) -> None:
        """m = ρ·A doit retrouver la masse tabulée à 2 % près."""
        for profil in cat:
            assert profil.masse == pytest.approx(7850.0 * profil.A, rel=0.02)

    def test_profils_creux_ont_un_rayon_reconstruit(self, cat) -> None:
        tube = cat["RRW 200/200/10"]
        assert tube.forme is Forme.PROFIL_CREUX
        assert tube.r == pytest.approx(2.0 * tube.tw)

    def test_geometrie_toujours_positive(self, cat) -> None:
        for profil in cat:
            assert profil.A > 0.0
            assert profil.h > 0.0 and profil.b > 0.0
            assert profil.tw > 0.0 and profil.tf > 0.0
            assert profil.Wply >= profil.Wely > 0.0
            assert profil.Iy >= profil.Iz > 0.0


class TestPerimetres:
    def test_concordance_avec_um_tabule(self, cat) -> None:
        """La formule géométrique doit retrouver la surface développée du SZS."""
        ecarts = [abs(e) for p in cat if (e := ecart_relatif_um(p)) is not None]
        assert len(ecarts) == 277
        assert sum(ecarts) / len(ecarts) < 0.01, "écart moyen supérieur à 1 %"
        assert max(ecarts) < 0.04, "un profilé dévie de plus de 4 %"

    def test_trois_faces_retranche_une_semelle(self, cat) -> None:
        ipe = cat["IPE 300"]
        quatre = perimetre_expose(ipe, Exposition.CONTOUR_4_FACES)
        trois = perimetre_expose(ipe, Exposition.CONTOUR_3_FACES)
        assert quatre - trois == pytest.approx(ipe.b)

    def test_caisson_est_le_rectangle_circonscrit(self, cat) -> None:
        heb = cat["HEB 300"]
        assert perimetre_expose(heb, Exposition.CAISSON_4_FACES) == pytest.approx(
            2.0 * (heb.h + heb.b)
        )
        assert perimetre_expose(heb, Exposition.CAISSON_3_FACES) == pytest.approx(
            2.0 * heb.h + heb.b
        )

    def test_caisson_toujours_inferieur_au_contour(self, cat) -> None:
        """Encaisser un profilé ouvert réduit toujours la surface exposée."""
        for profil in cat:
            if profil.forme is Forme.PROFIL_CREUX:
                continue
            contour = perimetre_expose(profil, Exposition.CONTOUR_4_FACES)
            caisson = perimetre_expose(profil, Exposition.CAISSON_4_FACES)
            assert caisson < contour


class TestFacteurMassivete:
    @pytest.mark.parametrize(
        "nom, attendu",
        [
            ("IPE 300", 216.0),
            ("HEB 300", 116.0),
            ("HEA 200", 211.0),
            ("HEM 400", 61.5),
        ],
    )
    def test_valeurs_publiees(self, cat, nom: str, attendu: float) -> None:
        """Comparaison aux tables A_m/V publiées, contour quatre faces."""
        obtenu = facteur_massivete(cat[nom], Exposition.CONTOUR_4_FACES)
        assert obtenu == pytest.approx(attendu, rel=0.01)

    def test_hierarchie_des_expositions(self, cat) -> None:
        """Contour 4 faces est toujours le cas le plus sévère."""
        ipe = cat["IPE 300"]
        valeurs = {e: facteur_massivete(ipe, e) for e in Exposition}
        assert (
            valeurs[Exposition.CAISSON_3_FACES]
            < valeurs[Exposition.CAISSON_4_FACES]
            < valeurs[Exposition.CONTOUR_4_FACES]
        )
        assert (
            valeurs[Exposition.CAISSON_3_FACES]
            < valeurs[Exposition.CONTOUR_3_FACES]
            < valeurs[Exposition.CONTOUR_4_FACES]
        )

    def test_profil_lourd_moins_massif(self, cat) -> None:
        """Plus le profilé est trapu, plus il chauffe lentement."""
        leger = facteur_massivete(cat["IPE 300"], Exposition.CONTOUR_4_FACES)
        lourd = facteur_massivete(cat["HHD 400.421"], Exposition.CONTOUR_4_FACES)
        assert lourd < leger / 4.0

    def test_domaine_de_validite_du_catalogue(self, cat) -> None:
        """Le catalogue reste au-dessus de la borne de 10 m⁻¹, mais de justesse."""
        minimum = min(
            facteur_massivete(p, Exposition.CAISSON_3_FACES) for p in cat
        )
        assert minimum > AM_SUR_V_MINIMAL
        assert minimum < 15.0, "la marge attendue sur le cas le plus trapu a changé"


class TestFacteurOmbre:
    def test_sections_en_i_sous_feu_nominal(self, cat) -> None:
        """Éq. (4.26a) : k_sh = 0,9 · [A_m/V]_caisson / [A_m/V]."""
        ipe = cat["IPE 300"]
        assert facteur_ombre(ipe, Exposition.CONTOUR_4_FACES) == pytest.approx(
            0.698, abs=0.005
        )

    def test_profil_creux_sans_effet_d_ombre(self, cat) -> None:
        """Éq. (4.26b) : un profil creux n'a aucune partie concave, k_sh = 1."""
        tube = cat["RRW 200/200/10"]
        assert facteur_ombre(tube, Exposition.CONTOUR_4_FACES) == pytest.approx(1.0)
        assert facteur_ombre(tube, Exposition.CONTOUR_3_FACES) == pytest.approx(1.0)

    def test_borne_superieure(self, cat) -> None:
        for profil in cat:
            for exposition in Exposition:
                assert 0.0 < facteur_ombre(profil, exposition) <= 1.0

    def test_sans_coefficient_09_hors_feu_nominal(self, cat) -> None:
        ipe = cat["IPE 300"]
        nominal = facteur_ombre(ipe, Exposition.CONTOUR_4_FACES, feu_nominal=True)
        autre = facteur_ombre(ipe, Exposition.CONTOUR_4_FACES, feu_nominal=False)
        assert nominal == pytest.approx(0.9 * autre)
