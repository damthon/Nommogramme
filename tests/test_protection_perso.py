"""Protection personnalisée : les données d'un produit trouvé par l'utilisateur."""

from __future__ import annotations

import pytest

from nommogramme.interface.saisie import PERSONNALISEE, Saisie, executer, produits


def test_identique_au_catalogue_a_proprietes_egales() -> None:
    """Saisir à la main les valeurs d'une fiche donne le résultat de cette fiche."""
    fiche = produits()["plaques_silicate"]
    catalogue = executer(Saisie(protection="plaques_silicate", epaisseur=20.0))
    perso = executer(Saisie(
        protection=PERSONNALISEE, epaisseur=20.0, lambda_p_perso=fiche["lambda_p"],
        rho_p_perso=fiche["rho_p"], c_p_perso=fiche["c_p"],
    ))
    assert perso.t_fi_d_minutes == pytest.approx(catalogue.t_fi_d_minutes, rel=1e-12)
    assert perso.theta_a_a_echeance == pytest.approx(catalogue.theta_a_a_echeance, rel=1e-12)


def test_un_meilleur_isolant_protege_mieux() -> None:
    base = Saisie(protection=PERSONNALISEE, epaisseur=20.0)
    moins_conducteur = executer(base.avec(lambda_p_perso=0.08))
    assert moins_conducteur.t_fi_d_minutes > executer(base).t_fi_d_minutes


def test_l_humidite_retarde_l_echauffement() -> None:
    base = Saisie(protection=PERSONNALISEE, epaisseur=20.0)
    assert (executer(base.avec(humidite_perso=10.0)).theta_a_a_echeance
            < executer(base).theta_a_a_echeance)


@pytest.mark.parametrize("champ", ["lambda_p_perso", "rho_p_perso", "c_p_perso"])
def test_une_propriete_non_positive_est_refusee(champ: str) -> None:
    with pytest.raises(ValueError, match="doit être positif"):
        executer(Saisie(protection=PERSONNALISEE, epaisseur=20.0, **{champ: 0.0}))


def test_le_nom_du_produit_passe_dans_la_note() -> None:
    r = executer(Saisie(protection=PERSONNALISEE, epaisseur=20.0, nom_perso="Plaque X"))
    assert r.protection.libelle == "Plaque X (produit personnalisé)"
    assert "Plaque X (produit personnalisé)" in r.note_de_calcul()
