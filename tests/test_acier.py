"""Propriétés de l'acier à chaud — EN 1993-1-2 §3."""

from __future__ import annotations

import pytest

from nommogramme.materiaux.acier import (
    RHO_A,
    TABLEAU_3_1,
    Nuance,
    chaleur_specifique,
    conductivite,
    k_E,
    k_p,
    k_y,
    limite_elasticite,
    temperature_pour_k_y,
)


class TestTableau31:
    """Les treize lignes du tableau 3.1 doivent être reproduites exactement."""

    @pytest.mark.parametrize("theta", sorted(TABLEAU_3_1))
    def test_valeurs_tabulees(self, theta: int) -> None:
        attendu_ky, attendu_kp, attendu_kE = TABLEAU_3_1[theta]
        assert k_y(theta) == pytest.approx(attendu_ky)
        assert k_p(theta) == pytest.approx(attendu_kp)
        assert k_E(theta) == pytest.approx(attendu_kE)

    def test_interpolation_lineaire(self) -> None:
        # À 550 °C, à mi-chemin entre k_y(500) = 0,780 et k_y(600) = 0,470.
        assert k_y(550) == pytest.approx(0.625)
        assert k_E(550) == pytest.approx(0.455)

    def test_palier_jusqu_a_400_degres(self) -> None:
        """La limite d'élasticité efficace n'est pas réduite avant 400 °C."""
        for theta in (20, 100, 250, 399, 400):
            assert k_y(theta) == pytest.approx(1.0)

    def test_saturation_hors_bornes(self) -> None:
        assert k_y(-50) == pytest.approx(1.0)
        assert k_y(1500) == pytest.approx(0.0)
        assert k_E(0) == pytest.approx(1.0)

    def test_decroissance_monotone(self) -> None:
        precedent_y, precedent_E = 1.0, 1.0
        for theta in range(20, 1201, 10):
            assert k_y(theta) <= precedent_y + 1e-12
            assert k_E(theta) <= precedent_E + 1e-12
            precedent_y, precedent_E = k_y(theta), k_E(theta)

    def test_module_chute_plus_vite_que_limite_elastique(self) -> None:
        """C'est ce qui fait croître l'élancement réduit à chaud."""
        for theta in (500, 600, 700, 800):
            assert k_E(theta) < k_y(theta)


class TestInverseKy:
    def test_aller_retour(self) -> None:
        for theta in (450, 500, 550, 600, 650, 700, 800):
            assert temperature_pour_k_y(k_y(theta)) == pytest.approx(theta, abs=0.5)

    def test_palier_renvoie_400(self) -> None:
        assert temperature_pour_k_y(1.0) == pytest.approx(400.0)
        assert temperature_pour_k_y(1.5) == pytest.approx(400.0)


class TestChaleurSpecifique:
    """EN 1993-1-2 éq. (3.2a) à (3.2d)."""

    def test_valeur_a_20_degres(self) -> None:
        assert chaleur_specifique(20.0) == pytest.approx(439.8, abs=0.5)

    def test_continuite_a_600(self) -> None:
        assert chaleur_specifique(599.999) == pytest.approx(
            chaleur_specifique(600.0), rel=1e-3
        )

    def test_continuite_a_900(self) -> None:
        assert chaleur_specifique(899.999) == pytest.approx(650.0, rel=1e-2)

    def test_pic_a_735_degres(self) -> None:
        """La transformation de phase produit un pic, pas une discontinuité douce."""
        pic = chaleur_specifique(734.99)
        assert pic > 4000.0
        assert chaleur_specifique(600.0) < 1000.0
        assert chaleur_specifique(900.0) == pytest.approx(650.0)

    def test_toujours_positive(self) -> None:
        for theta in range(20, 1201, 5):
            assert chaleur_specifique(theta) > 0.0

    def test_plateau_haute_temperature(self) -> None:
        assert chaleur_specifique(1000.0) == pytest.approx(650.0)
        assert chaleur_specifique(1200.0) == pytest.approx(650.0)


class TestConductivite:
    """EN 1993-1-2 éq. (3.3a) et (3.3b)."""

    def test_valeur_a_20_degres(self) -> None:
        assert conductivite(20.0) == pytest.approx(53.3, abs=0.1)

    def test_continuite_a_800(self) -> None:
        """La norme elle-même laisse un léger saut : 27,36 contre 27,3.

        La branche linéaire de l'éq. (3.3a) vaut 54 − 3,33·10⁻²·800 = 27,36
        W/m·K en 800 °C, alors que l'éq. (3.3b) impose 27,3 au-delà. L'écart de
        0,06 vient de l'arrondi du coefficient dans le texte normatif ; il est
        reproduit tel quel plutôt que lissé.
        """
        assert conductivite(799.999) == pytest.approx(27.36, abs=0.01)
        assert conductivite(800.0) == pytest.approx(27.3)

    def test_plateau_au_dela_de_800(self) -> None:
        assert conductivite(900.0) == pytest.approx(27.3)
        assert conductivite(1200.0) == pytest.approx(27.3)


class TestNuances:
    def test_masse_volumique_constante(self) -> None:
        assert RHO_A == 7850.0

    def test_reduction_par_epaisseur(self) -> None:
        assert limite_elasticite(Nuance.S355, 0.020) == pytest.approx(355e6)
        assert limite_elasticite(Nuance.S355, 0.040) == pytest.approx(355e6)
        assert limite_elasticite(Nuance.S355, 0.041) == pytest.approx(335e6)

    def test_toutes_les_nuances_definies(self) -> None:
        for nuance in Nuance:
            assert limite_elasticite(nuance, 0.010) > 0.0
            assert limite_elasticite(nuance, 0.060) < limite_elasticite(nuance, 0.010)
