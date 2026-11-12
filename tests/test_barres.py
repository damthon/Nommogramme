"""Barres et tubes (RND, VKT, ROR, FLA, FLB), classes de boulons, note Word.

Les caractéristiques des barres sont calculées depuis leurs cotes ; on les
recoupe ici avec les valeurs imprimées des Stahlbau-Tabellen SZS (pages 54,
55, 60, 61 et 74), relevées sur les scans fournis.
"""

from __future__ import annotations

import io
import zipfile

import pytest

from nommogramme import CasDeCharge, Exposition, Nuance, catalogue, verifier
from nommogramme.materiaux import k_b
from nommogramme.mecanique.classification import classifier
from nommogramme.profils import Famille, facteur_ombre, perimetre_expose


class TestCatalogue:
    def test_effectifs(self) -> None:
        effectifs = {f: len(catalogue.famille(f)) for f in
                     (Famille.RND, Famille.VKT, Famille.ROR, Famille.FLA, Famille.FLB)}
        assert effectifs == {Famille.RND: 45, Famille.VKT: 39, Famille.ROR: 115,
                             Famille.FLA: 315, Famille.FLB: 608}

    # nom, masse [kg/m], A [mm²], I [10⁶ mm⁴], W_el [10³ mm³], W_pl [10³ mm³],
    # i [mm], U_m [m²/m] — valeurs imprimées.
    @pytest.mark.parametrize("nom, m, A, I, Wel, Wpl, i, Um", [
        ("RND 20", 2.47, 314, 0.00785, 0.785, 1.33, 5.00, 0.0628),
        ("RND 100", 61.7, 7850, 4.91, 98.2, 167, 25.0, 0.314),
        ("RND 500", 1540, 196000, 3070, 12300, 20800, 125, 1.57),
        ("VKT 30", 7.07, 900, 0.0675, 4.50, 6.75, 8.66, 0.120),
        ("VKT 200", 314, 40000, 133, 1330, 2000, 57.6, 0.800),
        ("ROR 21.3/2", 0.95, 121, 0.00571, 0.54, 0.75, 6.9, 0.067),
        ("ROR 60.3/5", 6.82, 869, 0.335, 11.1, 15.3, 19.6, 0.189),
        ("ROR 101.6/12.5", 27.5, 3500, 3.54, 69.7, 99.3, 31.8, 0.319),
        ("ROR 152.4/16", 53.8, 6860, 16.16, 212, 299, 48.6, 0.479),
    ])
    def test_valeurs_tabulees(self, nom, m, A, I, Wel, Wpl, i, Um) -> None:
        p = catalogue[nom]
        assert p.masse == pytest.approx(m, rel=0.01)
        assert p.A * 1e6 == pytest.approx(A, rel=0.01)
        assert p.Iy * 1e12 / 1e6 == pytest.approx(I, rel=0.01)
        assert p.Wely * 1e9 / 1e3 == pytest.approx(Wel, rel=0.01)
        assert p.Wply * 1e9 / 1e3 == pytest.approx(Wpl, rel=0.01)
        assert p.iz * 1e3 == pytest.approx(i, rel=0.01)
        assert p.Um == pytest.approx(Um, rel=0.01)

    @pytest.mark.parametrize("nom, masse", [
        ("FLA 20/4", 0.63), ("FLA 100/10", 7.85), ("FLA 150/100", 118),
    ])
    def test_masse_des_plats(self, nom, masse) -> None:
        assert catalogue[nom].masse == pytest.approx(masse, rel=0.01)

    def test_un_plat_est_debout(self) -> None:
        """Axe fort parallèle à t : h = largeur, b = épaisseur."""
        p = catalogue["FLA 100/10"]
        assert (p.h, p.b, p.tf) == pytest.approx((0.100, 0.010, 0.010))
        assert p.Iy > p.Iz


class TestGeometrie:
    def test_convexes_sans_facteur_d_ombre(self) -> None:
        for nom in ("RND 50", "VKT 50", "ROR 60.3/5", "FLA 100/10"):
            assert facteur_ombre(catalogue[nom], Exposition.CONTOUR_4_FACES) == 1.0

    def test_tube_rond_encaisse_dans_un_carre(self) -> None:
        p = catalogue["ROR 60.3/5"]
        assert perimetre_expose(p, Exposition.CAISSON_4_FACES) == pytest.approx(4 * 0.0603)

    def test_massivete_basse_signalee(self) -> None:
        """Un rond de 500 mm passe sous 10 m⁻¹ : la méthode simplifiée le signale."""
        r = verifier(catalogue["RND 500"], Nuance.S235,
                     CasDeCharge(N_fi_Ed=1e6, L=3.0), Exposition.CONTOUR_4_FACES, 30)
        assert any("10 m⁻¹" in a for a in r.avertissements)


class TestClassification:
    def test_barre_pleine_classe_1(self) -> None:
        assert classifier(catalogue["FLB 2000/4"], 355e6, N_Ed=1e6).classe == 1

    @pytest.mark.parametrize("nom, classe", [
        # EN 1993-1-1 tab. 5.2 : d/t ≤ 50·ε², 70·ε², 90·ε² ; à chaud en S355,
        # ε² = 0,85²·235/355 = 0,478.
        ("ROR 60.3/5", 1),    # (d/t)/ε² = 25,2
        ("ROR 133/4", 2),     # 69,5
        ("ROR 159/4", 3),     # 83,1
    ])
    def test_tube_rond_d_sur_t(self, nom, classe) -> None:
        assert classifier(catalogue[nom], 355e6).classe == classe

    def test_tube_rond_classe_4(self) -> None:
        """Aucun tube du catalogue n'est de classe 4 en S355 ; un tube mince, si."""
        from nommogramme.profils.barres import tube

        assert classifier(tube(200.0, 4.0), 355e6).classe == 4  # 104,6


class TestBoulons:
    """Une tige, vérifiée avec un rond RND et une classe de boulon."""

    @pytest.mark.parametrize("classe, f_yb", [
        ("4.6", 240e6), ("5.6", 300e6), ("8.8", 640e6), ("10.9", 900e6),
    ])
    def test_tige_tendue(self, classe, f_yb) -> None:
        """En traction, θ_cr est la température où k_b,θ tombe à μ₀."""
        tige = catalogue["RND 24"]
        N = 0.5 * tige.A * f_yb  # μ₀ = 0,5 avec γ_M,fi = 1
        r = verifier(tige, Nuance(classe), CasDeCharge(N_fi_Ed=N, L=3.0),
                     Exposition.CONTOUR_4_FACES, 30)
        assert r.mu_0 == pytest.approx(0.5, abs=1e-6)
        assert r.theta_cr_nomogramme is None
        assert any("k_b,θ" in a for a in r.avertissements)
        # k_b = 0,5 entre 500 °C (0,55) et 600 °C (0,22) : θ = 515,2 °C.
        assert r.theta_cr == pytest.approx(500 + 100 * 0.05 / 0.33, abs=0.2)
        assert k_b(r.theta_cr) == pytest.approx(0.5, abs=1e-3)

    def test_boulon_plus_severe_que_l_acier(self) -> None:
        """À μ₀ égal, k_b,θ chute avant k_y,θ : θ_cr plus basse."""
        tige = catalogue["RND 24"]
        temperatures = {}
        for nuance in (Nuance.S235, Nuance.B4_6):
            N = 0.5 * tige.A * {Nuance.S235: 235e6, Nuance.B4_6: 240e6}[nuance]
            temperatures[nuance] = verifier(
                tige, nuance, CasDeCharge(N_fi_Ed=N, L=3.0),
                Exposition.CONTOUR_4_FACES, 30,
            ).theta_cr
        assert temperatures[Nuance.B4_6] < temperatures[Nuance.S235] - 60

    def test_tige_comprimee_flambe(self) -> None:
        """En compression, le flambement abaisse θ_cr sous la valeur de section.

        Section seule : k_b,θ = N/(A·f_yb) = 0,0442, soit θ = 868 °C entre
        800 °C (0,067) et 900 °C (0,033). Avec χ_fi, nettement moins.
        """
        tige = catalogue["RND 30"]
        r = verifier(tige, Nuance.B8_8, CasDeCharge(N_fi_Ed=-20e3, L=1.0),
                     Exposition.CONTOUR_4_FACES, 30)
        assert r.theta_cr_nomogramme is None
        assert 20e3 / (tige.A * 640e6) == pytest.approx(0.0442, abs=1e-4)
        assert r.theta_cr < 868 - 100


@pytest.fixture(scope="module")
def document():
    pytest.importorskip("docx")
    pytest.importorskip("matplotlib")
    r = verifier(catalogue["HEB 300"], Nuance.S355,
                 CasDeCharge(N_fi_Ed=-850e3, My_fi_Ed=40e3, L=4.0),
                 Exposition.CONTOUR_4_FACES, 60)
    flux = io.BytesIO()
    r.note_de_calcul_word(flux)
    with zipfile.ZipFile(flux) as archive:
        return archive.read("word/document.xml").decode("utf-8")


class TestNoteWord:
    def test_equations_natives(self, document) -> None:
        assert document.count("<m:oMath>") > 50

    def test_phrases_de_guidage(self, document) -> None:
        assert "On lit la température critique sur le nomogramme" in document

    def test_point_decimal_et_arial(self, document) -> None:
        assert "{,}" not in document

    def test_figures(self, document) -> None:
        assert document.count("<pic:pic") >= 2

    def test_toutes_les_equations_sont_du_xml_valide(self) -> None:
        """Chaque ligne de calcul de plusieurs cas devient un OMML bien formé."""
        pytest.importorskip("latex2mathml")
        from lxml import etree

        from nommogramme.note_pdf import etapes_de_calcul
        from nommogramme.note_word import _equations, latex_vers_omml

        cas = [
            verifier(catalogue["IPE 300"], Nuance.S235, CasDeCharge(My_fi_Ed=60e3, L=6.0),
                     Exposition.CONTOUR_3_FACES, 30),
            verifier(catalogue["RND 24"], Nuance.B8_8, CasDeCharge(N_fi_Ed=100e3, L=3.0),
                     Exposition.CONTOUR_4_FACES, 30),
            verifier(catalogue["ROR 114.3/10"], Nuance.S355,
                     CasDeCharge(N_fi_Ed=-200e3, My_fi_Ed=5e3, L=3.0),
                     Exposition.CONTOUR_4_FACES, 30),
        ]
        ns = "http://schemas.openxmlformats.org/officeDocument/2006/math"
        for r in cas:
            for bloc in etapes_de_calcul(r):
                for ligne in bloc.lignes:
                    for equation in _equations(ligne):
                        etree.fromstring(f'<x xmlns:m="{ns}">{latex_vers_omml(equation)}</x>')


def test_nomogramme_d_un_boulon_lit_k_b() -> None:
    """Le quadrant gauche d'une classe de boulon suit k_b,θ, pas l'éq. (4.22)."""
    pytest.importorskip("matplotlib")
    from nommogramme.nomogramme.trace import _lecture, tracer_nomogramme

    r = verifier(catalogue["RND 24"], Nuance.B8_8, CasDeCharge(N_fi_Ed=60e3, L=3.0),
                 Exposition.CONTOUR_4_FACES, 30)
    assert k_b(_lecture(r)) == pytest.approx(r.mu_0, abs=1e-6)
    assert _lecture(r) == pytest.approx(r.theta_cr, abs=0.1)  # traction : même valeur
    tracer_nomogramme(r)
