"""Rejoue les cas de référence déclarés dans ``cas_reference.toml``.

Ce fichier n'a pas de contenu propre : il exécute ce que le fichier TOML
déclare. Y déposer un cas dont le résultat est connu par ailleurs suffit à
créer un test.

Deux natures de cas cohabitent, distinguées par ``reference_externe`` :

* ``true`` — le résultat attendu vient d'une source indépendante (calcul à la
  main, autre logiciel, exemple publié). Ces cas **valident** l'outil ;
* ``false`` — le résultat attendu a été produit par l'outil lui-même et figé.
  Ces cas ne valident rien ; ils détectent les régressions.

Voir ``docs/validation.md``.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from nommogramme.contexte import EUROCODE_REC, SUISSE_SIA
from nommogramme.materiaux.acier import Nuance
from nommogramme.materiaux.protection import Protection
from nommogramme.mecanique.actions import CasDeCharge
from nommogramme.nomogramme.verification import verifier
from nommogramme.profils import Exposition, charger_csv
from nommogramme.thermique.courbes import courbe as courbe_par_nom
from nommogramme.unites import kN, kNm

_FICHIER = Path(__file__).parent / "cas_reference.toml"

_EXPOSITIONS = {
    "contour4": Exposition.CONTOUR_4_FACES,
    "contour3": Exposition.CONTOUR_3_FACES,
    "caisson4": Exposition.CAISSON_4_FACES,
    "caisson3": Exposition.CAISSON_3_FACES,
}

_CONTEXTES = {"sia": SUISSE_SIA, "eurocode": EUROCODE_REC}

# Attribut du résultat → extracteur, pour les grandeurs qui ne sont pas de
# simples attributs numériques.
_EXTRACTEURS = {
    "t_fi_d_min": lambda r: r.t_fi_d_minutes,
    "verdict": lambda r: r.verdict.value,
}


def _charger_cas() -> list[dict]:
    with _FICHIER.open("rb") as fichier:
        return tomllib.load(fichier).get("cas", [])


def _identifiant(cas: dict) -> str:
    return cas.get("libelle", cas.get("profil", "cas sans libellé"))


CAS = _charger_cas()


def test_le_fichier_declare_des_cas() -> None:
    assert CAS, f"{_FICHIER.name} ne déclare aucun cas."


@pytest.mark.parametrize("cas", CAS, ids=[_identifiant(c) for c in CAS])
def test_cas_de_reference(cas: dict) -> None:
    attendu = cas.get("attendu")
    assert attendu, f"« {_identifiant(cas)} » ne déclare aucune valeur attendue."

    catalogue = charger_csv()
    profil = catalogue[cas["profil"]]

    protection = None
    if cas.get("protection"):
        epaisseur = cas.get("dp_mm")
        assert epaisseur, f"« {_identifiant(cas)} » : protection sans dp_mm."
        protection = Protection.depuis_catalogue(
            cas["protection"], d_p=epaisseur * 1e-3
        )

    beta = cas.get("beta_M", 1.3)
    charge = CasDeCharge(
        N_fi_Ed=kN(cas.get("N_fi_Ed_kN", 0.0)),
        My_fi_Ed=kNm(cas.get("My_fi_Ed_kNm", 0.0)),
        Mz_fi_Ed=kNm(cas.get("Mz_fi_Ed_kNm", 0.0)),
        L=cas.get("L", 0.0),
        l_fi_y=cas.get("l_fi_y"),
        l_fi_z=cas.get("l_fi_z"),
        L_LT=cas.get("L_LT"),
        beta_M_y=beta,
        beta_M_z=beta,
        beta_M_LT=beta,
        maintien_lateral=cas.get("maintien_lateral", False),
    )

    resultat = verifier(
        profil=profil,
        nuance=Nuance(cas.get("nuance", "S355")),
        cas=charge,
        exposition=_EXPOSITIONS[cas["exposition"]],
        duree_requise_min=cas["duree_min"],
        protection=protection,
        courbe=courbe_par_nom(cas.get("feu", "iso834")),
        contexte=_CONTEXTES[cas.get("contexte", "sia")],
        kappa_1=cas.get("kappa_1", 1.0),
        kappa_2=cas.get("kappa_2", 1.0),
        C1=cas.get("C1", 1.0),
    )

    tolerance = cas.get("tolerance", 0.02)
    for grandeur, valeur_attendue in attendu.items():
        extracteur = _EXTRACTEURS.get(grandeur)
        obtenu = extracteur(resultat) if extracteur else getattr(resultat, grandeur)

        assert obtenu is not None, (
            f"« {_identifiant(cas)} » : {grandeur} n'a pas été calculé."
        )

        if isinstance(valeur_attendue, str):
            assert obtenu == valeur_attendue, (
                f"« {_identifiant(cas)} » : {grandeur} vaut {obtenu!r}, "
                f"attendu {valeur_attendue!r}"
            )
        else:
            assert obtenu == pytest.approx(valeur_attendue, rel=tolerance), (
                f"« {_identifiant(cas)} » : {grandeur} vaut {obtenu:.4g}, "
                f"attendu {valeur_attendue:.4g} "
                f"(source : {cas.get('source', 'non précisée')})"
            )


def test_les_cas_declarent_leur_nature() -> None:
    """Un cas doit dire s'il constitue une référence externe ou un simple gel."""
    for cas in CAS:
        assert "reference_externe" in cas, (
            f"« {_identifiant(cas)} » ne précise pas reference_externe."
        )
        assert cas.get("source"), f"« {_identifiant(cas)} » ne cite pas sa source."
