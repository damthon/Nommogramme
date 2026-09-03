"""Registre des références normatives.

Ces tests ne peuvent pas dire si une clause est *juste* — cela demande un
exemplaire de la norme, et c'est exactement pourquoi ``Reference.confirmee``
existe. Ce qu'ils garantissent est plus modeste et plus vérifiable : que
chaque référence est complète et bien formée, qu'elle apparaît réellement là
où le code prétend la citer, et que les clauses non confirmées sont visibles
plutôt que noyées.
"""

from __future__ import annotations

import re

import pytest

from nommogramme.references import REFERENCES, Reference, a_recouper

_NORMES_CONNUES = {
    "EN 1993-1-2", "EN 1993-1-1", "EN 1991-1-2", "ENV 1993-1-1",
    "SIA 263", "SIA 260", "SZS C5/05",
}


class TestFormeDesReferences:
    @pytest.mark.parametrize("nom", sorted(REFERENCES))
    def test_chaque_reference_est_complete(self, nom: str) -> None:
        reference = REFERENCES[nom]
        assert reference.norme in _NORMES_CONNUES, f"norme inattendue : {reference.norme}"
        assert reference.clause, "une référence sans paragraphe ne sert à rien"
        assert reference.objet, "une référence doit dire ce qu'elle établit"

    @pytest.mark.parametrize("nom", sorted(REFERENCES))
    def test_le_numero_d_equation_est_parenthese(self, nom: str) -> None:
        """« (4.22) », jamais « 4.22 » : c'est la forme des Eurocodes."""
        equation = REFERENCES[nom].equation
        if equation:
            assert re.fullmatch(r"\(\d+\.\d+[ab]?\)( et \(\d+\.\d+[ab]?\))*", equation), (
                f"numérotation inattendue : {equation!r}"
            )

    def test_la_forme_courte_porte_les_trois_elements(self) -> None:
        reference = Reference("EN 1993-1-2", "§4.2.4", "(4.22)", "essai")
        assert reference.courte == "EN 1993-1-2 §4.2.4, éq. (4.22)"
        assert str(reference) == reference.courte
        assert reference.complete.endswith("— essai")

    def test_sans_equation_la_forme_courte_s_arrete_au_paragraphe(self) -> None:
        assert Reference("EN 1993-1-2", "annexe E").courte == "EN 1993-1-2 annexe E"

    def test_l_infobulle_empile_aide_puis_reference(self) -> None:
        reference = Reference(
            "EN 1993-1-2", "§4.2.4", "(4.22)", "essai", remarque="une précision"
        )
        lignes = reference.infobulle("ce que fait le paramètre").splitlines()
        assert lignes == [
            "ce que fait le paramètre",
            "EN 1993-1-2 §4.2.4, éq. (4.22)",
            "une précision",
        ]

    def test_une_reference_a_recouper_le_dit_dans_son_infobulle(self) -> None:
        """L'utilisateur doit savoir ce qui n'a pas été vérifié."""
        reference = Reference("SIA 263", "chiffre X", objet="essai", confirmee=False)
        assert "à recouper" in reference.infobulle("aide")

    def test_les_references_sont_gelees(self) -> None:
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            REFERENCES["EC3_THETA_CR"].clause = "§9.9"


class TestClausesARecouper:
    def test_il_en_reste_et_elles_sont_nommees(self) -> None:
        """Le registre doit rester honnête sur ce qui n'est pas vérifié.

        Si cette liste devient vide, c'est que quelqu'un a coché les cases
        sans ouvrir les normes — ou qu'il les a vraiment recoupées, auquel cas
        ce test doit être mis à jour en connaissance de cause.
        """
        restantes = a_recouper()
        assert restantes, "au moins κ₁/κ₂ et C₁ restent à confirmer"
        assert all(not reference.confirmee for reference in restantes)
        assert all(reference.remarque for reference in restantes), (
            "une clause non confirmée doit expliquer ce qui reste à vérifier"
        )

    def test_les_clauses_sensibles_y_figurent(self) -> None:
        noms = {
            nom for nom, reference in REFERENCES.items() if not reference.confirmee
        }
        assert "EC3_KAPPA" in noms
        assert "MCR_C1" in noms


class TestUsageDansLeCode:
    """Les références doivent être citées, pas seulement déclarées."""

    def test_la_temperature_critique_est_citee_avec_sa_norme(self, ) -> None:
        from nommogramme import CasDeCharge, Exposition, Nuance, catalogue, verifier

        resultat = verifier(
            profil=catalogue["HEB 300"], nuance=Nuance.S355,
            cas=CasDeCharge(N_fi_Ed=850e3, My_fi_Ed=120e3, L=4.0,
                            l_fi_y=2.0, l_fi_z=2.0),
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60,
        )
        assert "EN 1993-1-2" in resultat.source_theta_cr
        assert "EN 1993-1-2 §4.2.3.5" in resultat.gouverne_par

    def test_les_aides_de_l_interface_citent_leur_clause(self) -> None:
        """Le but du travail : κ₁, κ₂, C₁ et β_M ne se comprennent pas sans elle."""
        from nommogramme.interface.saisie import AIDES

        for parametre, attendu in (
            ("kappa_1", "§4.2.3.3(7)"),
            ("kappa_2", "§4.2.3.3(7)"),
            ("C1", "ENV 1993-1-1 annexe F"),
            ("beta_M", "EN 1993-1-2 fig. 4.2"),
            ("l_fi", "EN 1993-1-2 §4.2.3.2(4)"),
            ("maintien", "éq. (4.21b)"),
        ):
            assert attendu in AIDES[parametre], (
                f"l'aide de « {parametre} » ne cite pas {attendu}"
            )
