"""Le catalogue confronté page à page au SZS C5/05 — la source du classeur.

Source : **SZS, « Tables de construction C5/05 », 9ᵉ édition, réimpression
actualisée 2012**, tables des profilés — IPE et PEA p. 26/27, INP p. 28/29,
HEA p. 34/35, HEB p. 36/37, HEM p. 38/39, HHD et HL p. 40/41, RRW carrés
p. 60/61. Document fourni par l'utilisateur.

Le lot 1 ne reposait jusqu'ici que sur un recoupement interne : le périmètre
recalculé géométriquement contre la colonne ``Um`` du classeur de
l'utilisateur. Mais le classeur est lui-même une transcription — c'est *lui*
qu'il fallait vérifier, et cette source est son original.

Trois colonnes sont confrontées, celles dont l'outil dépend vraiment : la
section **A**, le rayon de giration faible **i_z** qui pilote le flambement,
et le périmètre **U_m** qui pilote le facteur de massiveté.

Ce que l'audit a établi
-----------------------

**Le classeur est fidèle.** 561 valeurs sur 187 profilés, aucun écart. Les
deux anomalies connues ne sont donc pas des fautes de transcription :

* les **RRW** — le classeur fusionne les tables SZS des tubes carrés (une
  seule colonne ``i``, puisque I_y = I_z) et des tubes rectangulaires (i_y et
  i_z distincts). Dans le bloc carré, l'unique valeur du premier tube,
  RRW 40/40/3, s'est propagée aux 108 lignes : c'est le 15,0018 mm figé. Le
  catalogue SZS donne bien 15,0 mm pour ce tube-là. La correction du chargeur
  reproduit les valeurs officielles à moins de 1 % sur tout l'échantillon.
* le **HHD 320.74** — l'I_z fautif est **dans le SZS C5/05 lui-même**. Le
  classeur le recopie fidèlement. Voir ``chargeur._corriger_inertie_faible``.

**Le HEB 280 n'a jamais eu d'anomalie.** ``test_reference_massivete`` avait
relevé un écart de 4,9 % sur ses quatre facteurs de massiveté, attribué à la
section. Le C5 donne A = 13 100 mm² et U_m = 1,62 m²/m, soit A_m/V = 123,7 —
la valeur calculée par l'outil. C'est la lecture de la table sur une capture
d'écran de basse définition qui était fausse : 118 pour 123.
"""

from __future__ import annotations

import math

import pytest

from nommogramme.profils import Exposition, charger_csv, facteur_massivete

# ---------------------------------------------------------------------------
# Relevé manuel du SZS C5/05. Pour chaque profilé : (A [mm²], i_z [mm], U_m).
# ---------------------------------------------------------------------------

REF_OUVERTS: dict[str, tuple[float, float, float]] = {
# IPE  p.26 / p.27
"IPE 80":(764,10.5,0.328),"IPE 100":(1030,12.4,0.400),"IPE 120":(1320,14.5,0.475),
"IPE 140":(1640,16.5,0.551),"IPE 160":(2010,18.4,0.623),"IPE 180":(2390,20.5,0.698),
"IPE 200":(2850,22.4,0.768),"IPE 220":(3340,24.8,0.848),"IPE 240":(3910,26.9,0.922),
"IPE 270":(4590,30.2,1.04),"IPE 300":(5380,33.5,1.16),"IPE 330":(6260,35.5,1.25),
"IPE 360":(7270,37.9,1.35),"IPE 400":(8450,39.5,1.47),"IPE 450":(9880,41.2,1.61),
"IPE 500":(11600,43.1,1.74),"IPE 550":(13400,44.5,1.88),"IPE 600":(15600,46.6,2.02),
# PEA  p.26 / p.27
"PEA 120":(1100,14.2,0.472),"PEA 140":(1340,16.5,0.547),"PEA 160":(1620,18.3,0.619),
"PEA 180":(1960,20.5,0.694),"PEA 200":(2350,22.3,0.764),"PEA 220":(2830,24.6,0.843),
"PEA 240":(3330,26.8,0.918),"PEA 270":(3920,30.2,1.04),"PEA 300":(4650,33.4,1.16),
"PEA 330":(5470,35.4,1.25),"PEA 360":(6400,38.4,1.35),"PEA 400":(7310,40.0,1.46),
"PEA 450":(8560,41.9,1.60),"PEA 500":(10100,43.8,1.74),"PEA 550":(11700,45.5,1.88),
"PEA 600":(13700,47.7,2.01),
# INP  p.28 / p.29
"INP 80":(757,9.1,0.304),"INP 100":(1060,10.7,0.370),"INP 120":(1420,12.3,0.439),
"INP 140":(1820,14.0,0.502),"INP 160":(2280,15.5,0.575),"INP 180":(2790,17.1,0.640),
"INP 200":(3340,18.7,0.709),"INP 220":(3950,20.2,0.775),"INP 240":(4610,22.0,0.844),
"INP 260":(5330,23.2,0.906),"INP 280":(6100,24.5,0.966),"INP 300":(6900,25.6,1.03),
"INP 320":(7770,26.7,1.09),"INP 340":(8670,28.0,1.15),"INP 360":(9700,29.0,1.21),
"INP 380":(10700,30.2,1.27),"INP 400":(11800,31.3,1.33),"INP 450":(14700,34.3,1.48),
"INP 500":(17900,37.2,1.63),"INP 550":(21200,40.2,1.80),
# HEA  p.34 / p.35
"HEA 100":(2120,25.1,0.561),"HEA 120":(2530,30.2,0.677),"HEA 140":(3140,35.2,0.794),
"HEA 160":(3880,39.8,0.906),"HEA 180":(4530,45.2,1.02),"HEA 200":(5380,49.8,1.14),
"HEA 220":(6430,55.1,1.26),"HEA 240":(7680,60.0,1.37),"HEA 260":(8680,65.0,1.48),
"HEA 280":(9730,70.0,1.60),"HEA 300":(11300,74.9,1.72),"HEA 320":(12400,74.9,1.76),
"HEA 340":(13300,74.6,1.79),"HEA 360":(14300,74.3,1.83),"HEA 400":(15900,73.4,1.91),
"HEA 450":(17800,72.9,2.01),"HEA 500":(19800,72.4,2.11),"HEA 550":(21200,71.5,2.21),
"HEA 600":(22600,70.5,2.31),"HEA 650":(24200,69.7,2.41),"HEA 700":(26000,68.4,2.50),
"HEA 800":(28600,66.5,2.70),"HEA 900":(32100,65.0,2.90),"HEA 1000":(34700,63.5,3.10),
# HEB  p.36 / p.37
"HEB 100":(2600,25.3,0.567),"HEB 120":(3400,30.6,0.686),"HEB 140":(4300,35.8,0.805),
"HEB 160":(5430,40.5,0.918),"HEB 180":(6530,45.7,1.04),"HEB 200":(7810,50.7,1.15),
"HEB 220":(9100,55.9,1.27),"HEB 240":(10600,60.8,1.38),"HEB 260":(11800,65.8,1.50),
"HEB 280":(13100,70.9,1.62),"HEB 300":(14900,75.8,1.73),"HEB 320":(16100,75.7,1.77),
"HEB 340":(17100,75.3,1.81),"HEB 360":(18100,74.9,1.85),"HEB 400":(19800,74.0,1.93),
"HEB 450":(21800,73.3,2.03),"HEB 500":(23900,72.7,2.12),"HEB 550":(25400,71.7,2.22),
"HEB 600":(27000,70.8,2.32),"HEB 650":(28600,69.9,2.42),"HEB 700":(30600,68.7,2.52),
"HEB 800":(33400,66.8,2.71),"HEB 900":(37100,65.3,2.91),"HEB 1000":(40000,63.8,3.11),
# HEM  p.38 / p.39
"HEM 100":(5320,27.4,0.619),"HEM 120":(6640,32.5,0.738),"HEM 140":(8060,37.7,0.857),
"HEM 160":(9710,42.6,0.970),"HEM 180":(11300,47.7,1.09),"HEM 200":(13100,52.7,1.20),
"HEM 220":(14900,57.9,1.32),"HEM 240":(20000,63.9,1.46),"HEM 260":(22000,69.0,1.57),
"HEM 280":(24000,74.0,1.69),"HEM 300":(30300,80.0,1.83),"HEM 320":(31200,79.5,1.87),
"HEM 340":(31600,79.0,1.90),"HEM 360":(31900,78.3,1.93),"HEM 400":(32600,77.0,2.00),
"HEM 450":(33500,75.9,2.10),"HEM 500":(34400,74.6,2.18),"HEM 550":(35400,73.5,2.28),
"HEM 600":(36400,72.2,2.37),"HEM 650":(37400,71.3,2.47),"HEM 700":(38300,70.1,2.56),
"HEM 800":(40400,67.9,2.75),"HEM 900":(42400,66.0,2.93),"HEM 1000":(44400,64.5,3.13),
}

REF_HHD: dict[str, tuple[float, float, float]] = {
"HHD260.54":(6900,63.6,1.47),"HHD260.114":(14600,66.6,1.52),"HHD260.142":(18000,67.6,1.54),
"HHD320.74":(9460,72.4,1.74),"HHD320.158":(20100,76.7,1.80),"HHD320.198":(25200,77.9,1.83),
"HHD360.134":(17100,94.0,2.14),"HHD360.147":(18800,94.3,2.15),"HHD360.162":(20600,94.9,2.16),
"HHD360.179":(22800,95.2,2.17),"HHD360.196":(25000,95.6,2.18),
"HHD400.187":(23800,100.,2.24),"HHD400.216":(27500,101.,2.27),"HHD400.237":(30100,102.,2.29),
"HHD400.262":(33400,102.,2.30),"HHD400.287":(36600,103.,2.31),"HHD400.314":(40000,104.,2.33),
"HHD400.347":(44200,104.,2.35),"HHD400.382":(48800,105.,2.37),"HHD400.421":(53700,106.,2.39),
"HHD400.463":(59000,107.,2.42),"HHD400.509":(65200,108.,2.45),"HHD400.551":(70300,108.,2.47),
"HHD400.592":(75500,109.,2.50),"HHD400.634":(80600,110.,2.52),"HHD400.677":(86500,111.,2.55),
"HHD400.744":(94800,112.,2.59),"HHD400.818":(105000,114.,2.63),"HHD400.900":(115000,115.,2.68),
"HHD400.990":(126000,117.,2.72),"HHD400.1086":(139000,119.,2.77),
"HL1000x":(37700,87.5,3.48),"HL1000A":(40900,90.0,3.50),"HL1000B":(47200,90.3,3.51),
"HL1000M":(52400,91.0,3.53),"HL1100A":(43600,87.1,3.71),"HL1100B":(49700,88.0,3.73),
"HL1100M":(55100,88.7,3.75),"HL1100R":(63500,88.7,3.77),
}

# RRW p. 60/61 : les tubes carrés n'ont qu'une colonne « i », I_y valant I_z.
# Échantillon réparti sur toute la gamme, de 40×40 à 400×400.
REF_RRW: dict[str, tuple[float, float, float]] = {
    "RRW 40/40/3": (434, 15.0, 0.152),
    "RRW 50/50/5": (873, 18.2, 0.187),
    "RRW 60/60/5": (1073, 22.3, 0.227),
    "RRW 70/70/8": (1915, 25.0, 0.259),
    "RRW 80/80/8": (2235, 29.1, 0.299),
    "RRW 90/90/6.3": (2067, 34.0, 0.344),
    "RRW 100/100/10": (3493, 36.4, 0.374),
    "RRW 110/110/8": (3195, 41.4, 0.419),
    "RRW 120/120/12.5": (5207, 43.4, 0.448),
    "RRW 140/140/8": (4155, 53.6, 0.539),
    "RRW 150/150/16": (8301, 54.1, 0.559),
    "RRW 160/160/10": (5893, 60.9, 0.614),
    "RRW 180/180/12.5": (8207, 68.0, 0.688),
    "RRW 200/200/5": (3873, 79.5, 0.787),
    "RRW 200/200/10": (7493, 77.2, 0.774),
    "RRW 200/200/16": (11501, 74.6, 0.759),
    "RRW 220/220/6.3": (5343, 87.1, 0.864),
    "RRW 250/250/10": (9493, 97.7, 0.974),
    "RRW 300/300/12.5": (14207, 117.0, 1.17),
    "RRW 350/350/10": (13493, 139.0, 1.37),
    "RRW 400/400/10": (15493, 159.0, 1.57),
    "RRW 400/400/16": (24301, 156.0, 1.56),
}

_TOLERANCE = 0.01


@pytest.fixture(scope="module")
def catalogue():
    return charger_csv()


def _confronter(catalogue, reference: dict[str, tuple[float, float, float]]):
    """(profilé, colonne, publiée, retenue) pour tout écart au-delà de 1 %."""
    fautives = []
    for nom, (A_ref, iz_ref, Um_ref) in reference.items():
        profil = catalogue[nom]
        for colonne, retenue, publiee in (
            ("A", profil.A * 1e6, A_ref),
            ("i_z", profil.iz * 1e3, iz_ref),
            ("U_m", profil.Um, Um_ref),
        ):
            if abs(retenue / publiee - 1) > _TOLERANCE:
                fautives.append((nom, colonne, publiee, round(retenue, 3)))
    return fautives


class TestProfilsOuverts:
    """IPE, PEA, INP, HEA, HEB, HEM — 126 profilés, 378 valeurs."""

    def test_le_releve_couvre_bien_les_six_familles(self, catalogue) -> None:
        assert len(REF_OUVERTS) == 126
        familles = {catalogue[nom].famille.value for nom in REF_OUVERTS}
        assert familles == {"IPE", "PEA", "INP", "HEA", "HEB", "HEM"}

    def test_chaque_valeur_concorde(self, catalogue) -> None:
        fautives = _confronter(catalogue, REF_OUVERTS)
        assert not fautives, f"{len(fautives)} écarts : {fautives}"


class TestHHDetHL:
    """HHD et HL — 39 profilés, 117 valeurs."""

    def test_chaque_valeur_concorde(self, catalogue) -> None:
        fautives = _confronter(catalogue, REF_HHD)
        assert not fautives, f"{len(fautives)} écarts : {fautives}"

    def test_l_inertie_fautive_du_hhd_320_74_vient_bien_du_szs(self, catalogue) -> None:
        """Le C5 publie 45,59·10⁶ mm⁴ ; le classeur ne fait que le recopier.

        L'erreur n'est donc pas une faute de saisie de l'utilisateur. Elle est
        dans la source, et trois colonnes de la même page la contredisent.
        """
        profil = catalogue["HHD320.74"]
        assert profil.Iz_tabule * 1e12 == pytest.approx(45.59e6, rel=0.001)

        A, b = profil.A, profil.b
        depuis_iz = profil.iz**2 * A
        depuis_welz = profil.Welz * b / 2
        assert depuis_iz * 1e12 == pytest.approx(49.6e6, rel=0.01)
        assert depuis_welz * 1e12 == pytest.approx(49.6e6, rel=0.01)
        assert profil.Iz == pytest.approx(depuis_iz, rel=0.01)

    def test_les_hhd_320_voisins_sont_coherents(self, catalogue) -> None:
        """L'erreur porte sur une cellule, pas sur la série."""
        for nom in ("HHD320.158", "HHD320.198"):
            profil = catalogue[nom]
            assert profil.Iz_tabule is None
            assert math.sqrt(profil.Iz / profil.A) == pytest.approx(profil.iz, rel=0.005)
            assert profil.Welz == pytest.approx(profil.Iz / (profil.b / 2), rel=0.005)


class TestTubesRRW:
    """RRW — échantillon de 22 tubes sur les 108, 66 valeurs."""

    def test_les_valeurs_corrigees_sont_celles_du_szs(self, catalogue) -> None:
        """La colonne « i » officielle, retrouvée par i_z = √(I_z/A)."""
        fautives = _confronter(catalogue, REF_RRW)
        assert not fautives, f"{len(fautives)} écarts : {fautives}"

    def test_la_valeur_figee_est_celle_du_premier_tube(self, catalogue) -> None:
        """15,0018 mm est le i du RRW 40/40/3, première ligne du bloc carré.

        C'est l'explication du gel : le C5 sépare tubes carrés et tubes
        rectangulaires, et le bloc carré n'a qu'une colonne « i ». La fusion
        des deux tables dans le classeur a recopié la première valeur.
        """
        premier = catalogue["RRW 40/40/3"]
        assert premier.iz_tabule * 1e3 == pytest.approx(15.0, abs=0.05)
        assert REF_RRW["RRW 40/40/3"][1] == pytest.approx(premier.iz_tabule * 1e3, abs=0.05)

        for nom in REF_RRW:
            assert catalogue[nom].iz_tabule == pytest.approx(premier.iz_tabule)


class TestFacteursDeMassivete:
    """A_m/V recalculé depuis les colonnes officielles A et U_m.

    ``test_reference_massivete`` confronte l'outil à la table SZS des
    « Profilfaktoren » relevée sur une capture d'écran. Ce contrôle-ci est
    plus sûr : il repart des deux colonnes du catalogue imprimé, sans passer
    par une table résumée de basse définition.
    """

    def test_le_contour_quatre_faces_vaut_bien_U_m_sur_A(self, catalogue) -> None:
        ecarts = []
        for nom, (A_ref, _, Um_ref) in {**REF_OUVERTS, **REF_HHD}.items():
            attendu = Um_ref / (A_ref * 1e-6)
            calcule = facteur_massivete(catalogue[nom], Exposition.CONTOUR_4_FACES)
            ecarts.append(abs(calcule / attendu - 1))
        assert max(ecarts) < 0.01, f"écart maximal {max(ecarts):.1%}"
        assert sum(ecarts) / len(ecarts) < 0.003

    def test_le_heb_280_n_a_jamais_eu_d_anomalie(self, catalogue) -> None:
        """A = 13 100 mm² et U_m = 1,62 donnent 123,7 m⁻¹, pas 118.

        C'est le contre-exemple qui clôt la fausse piste ouverte par la
        lecture de la table résumée.
        """
        profil = catalogue["HEB 280"]
        assert profil.A * 1e6 == pytest.approx(13100, rel=0.001)
        assert profil.Um == pytest.approx(1.62, rel=0.001)
        assert facteur_massivete(profil, Exposition.CONTOUR_4_FACES) == pytest.approx(
            123.7, abs=0.5
        )
