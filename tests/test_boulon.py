"""Boulon : tige ronde de diamètre libre, classes de boulon.

La tige est calculée comme un rond plein. On la recoupe de trois façons :
avec les ronds RND du catalogue (mêmes diamètres, mêmes valeurs), avec les
valeurs imprimées des Stahlbau-Tabellen SZS, et par un calcul à la main de la
résistance à la traction.
"""

from __future__ import annotations

import dataclasses
import math

import pytest

from nommogramme import Nuance, catalogue, verifier
from nommogramme.interface.saisie import (
    BOULON,
    CATALOGUE,
    NUANCES_ACIER,
    NUANCES_BOULON,
    Saisie,
    executer,
    nuances_pour,
)
from nommogramme.profils import Famille
from nommogramme.profils.barres import boulon

_CHAMPS = [f.name for f in dataclasses.fields(boulon(20.0))
           if isinstance(getattr(boulon(20.0), f.name), float)]


@pytest.mark.parametrize("rnd", catalogue.famille(Famille.RND), ids=lambda p: p.nom)
def test_boulon_identique_au_rond_du_catalogue(rnd) -> None:
    """Pour chaque RND du catalogue, le boulon de même diamètre a les mêmes valeurs."""
    tige = boulon(rnd.h * 1e3)
    for champ in _CHAMPS:
        assert getattr(tige, champ) == pytest.approx(getattr(rnd, champ), rel=1e-12), champ
    assert tige.nom.startswith("Boulon Ø") and tige.famille is Famille.RND


# nom, masse [kg/m], A [mm²], I [10⁶ mm⁴], W_el [10³ mm³], W_pl [10³ mm³],
# i [mm], U_m [m²/m] — valeurs imprimées des Stahlbau-Tabellen SZS (p. 54).
@pytest.mark.parametrize("d, m, A, I, Wel, Wpl, i, Um", [
    (20, 2.47, 314, 0.00785, 0.785, 1.33, 5.00, 0.0628),
    (100, 61.7, 7850, 4.91, 98.2, 167, 25.0, 0.314),
])
def test_boulon_recoupe_les_valeurs_imprimees(d, m, A, I, Wel, Wpl, i, Um) -> None:
    p = boulon(float(d))
    assert p.masse == pytest.approx(m, rel=0.01)
    assert p.A * 1e6 == pytest.approx(A, rel=0.01)
    assert p.Iy * 1e12 / 1e6 == pytest.approx(I, rel=0.01)
    assert p.Wely * 1e9 / 1e3 == pytest.approx(Wel, rel=0.01)
    assert p.Wply * 1e9 / 1e3 == pytest.approx(Wpl, rel=0.01)
    assert p.iy * 1e3 == pytest.approx(i, rel=0.01)
    assert p.Um == pytest.approx(Um, rel=0.01)


def _tige(d: float = 24.0, **champs) -> Saisie:
    return Saisie(type_section=BOULON, d_boulon=d, nuance="8.8", N=60.0, My=0.0,
                  Mz=0.0, L=3.0, l_fi=0.0, duree=30, **champs)


def test_verification_identique_au_rond_du_catalogue() -> None:
    """Toute la chaîne donne le même résultat pour Ø24 et pour le RND 24."""
    r = executer(_tige(24.0))
    reference = verifier(
        catalogue["RND 24"], Nuance.B8_8, r.cas, r.exposition, 30.0,
        courbe=r.courbe, contexte=r.contexte,
    )
    assert r.profil.nom == "Boulon Ø24"
    assert r.mu_0 == pytest.approx(reference.mu_0, rel=1e-12)
    assert r.theta_cr == pytest.approx(reference.theta_cr, rel=1e-12)
    assert r.theta_a_a_echeance == pytest.approx(reference.theta_a_a_echeance, rel=1e-12)


def test_traction_a_la_main() -> None:
    """μ₀ = N / (A·f_yb/γ_M,fi) : 60 kN sur un Ø20 en 8.8 (f_yb = 640 MPa)."""
    r = executer(_tige(20.0))
    A = math.pi * 0.020**2 / 4.0
    assert r.mu_0 == pytest.approx(60e3 / (A * 640e6 / r.contexte.gamma_M_fi), rel=1e-9)


def test_diametre_quelconque() -> None:
    """Un diamètre absent du catalogue se calcule aussi."""
    r = executer(_tige(27.0))
    assert r.profil.A == pytest.approx(math.pi * 0.027**2 / 4.0)


class TestNuances:
    def test_listes_separees(self) -> None:
        assert set(NUANCES_BOULON) == {"4.6", "5.6", "8.8", "10.9"}
        assert "S355" in NUANCES_ACIER and "8.8" not in NUANCES_ACIER
        assert nuances_pour(BOULON) == NUANCES_BOULON
        assert nuances_pour(CATALOGUE) == NUANCES_ACIER

    def test_boulon_en_acier_de_construction_refuse(self) -> None:
        with pytest.raises(ValueError, match="classe de boulon"):
            executer(_tige().avec(nuance="S355"))

    def test_classe_de_boulon_hors_boulon_refusee(self) -> None:
        with pytest.raises(ValueError, match="réservées"):
            executer(Saisie(nuance="8.8"))
