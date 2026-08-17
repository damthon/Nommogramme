"""Interface en ligne de commande."""

from __future__ import annotations

import pytest

from nommogramme.cli import main


class TestProfils:
    def test_liste_une_famille(self, capsys) -> None:
        assert main(["profils", "--famille", "IPE"]) == 0
        sortie = capsys.readouterr().out
        assert "IPE300" in sortie
        assert "22 profilés" in sortie

    def test_filtre_par_nom(self, capsys) -> None:
        assert main(["profils", "--nom", "HEB 300"]) == 0
        assert "HEB300" in capsys.readouterr().out

    def test_sortie_csv(self, capsys) -> None:
        assert main(["profils", "--famille", "HEA", "--format", "csv"]) == 0
        lignes = capsys.readouterr().out.strip().splitlines()
        assert lignes[0].startswith("nom,masse_kg_m")
        assert len(lignes) == 25  # en-tête + 24 HEA

    def test_famille_inconnue(self, capsys) -> None:
        assert main(["profils", "--famille", "XYZ"]) == 1
        assert "Erreur" in capsys.readouterr().err

    def test_aucun_resultat(self, capsys) -> None:
        assert main(["profils", "--nom", "inexistant"]) == 1


class TestEchauffement:
    def test_element_nu(self, capsys) -> None:
        assert main(["echauffement", "IPE 300", "--duree", "R30"]) == 0
        sortie = capsys.readouterr().out
        assert "Am/V" in sortie
        assert "k_sh" in sortie

    def test_temperature_critique_atteinte(self, capsys) -> None:
        assert main(
            ["echauffement", "IPE 300", "--duree", "R60", "--theta-cr", "600"]
        ) == 0
        assert "atteinte à" in capsys.readouterr().out

    def test_avec_protection(self, capsys) -> None:
        assert main(
            [
                "echauffement", "HEB 300", "--duree", "R90",
                "--protection", "flocage_fibreux", "--dp", "20",
            ]
        ) == 0
        sortie = capsys.readouterr().out
        assert "Flocage fibreux" in sortie
        assert "φ (éq. 4.28)" in sortie

    def test_protection_sans_epaisseur(self, capsys) -> None:
        assert main(
            ["echauffement", "IPE 300", "--protection", "flocage_fibreux"]
        ) == 1
        assert "--dp" in capsys.readouterr().err

    def test_profil_inconnu(self, capsys) -> None:
        assert main(["echauffement", "IPE 999"]) == 1
        assert "Erreur" in capsys.readouterr().err

    @pytest.mark.parametrize("duree", ["60", "R60", "60min", "r60"])
    def test_formats_de_duree(self, duree: str, capsys) -> None:
        assert main(["echauffement", "IPE 300", "--duree", duree]) == 0
        assert "60 min" in capsys.readouterr().out

    def test_duree_illisible(self) -> None:
        with pytest.raises(SystemExit):
            main(["echauffement", "IPE 300", "--duree", "bientôt"])


class TestDimensionner:
    def test_epaisseur_requise(self, capsys) -> None:
        assert main(
            [
                "dimensionner", "IPE 300", "--theta-cr", "550",
                "--duree", "R90", "--protection", "flocage_fibreux",
            ]
        ) == 0
        sortie = capsys.readouterr().out
        assert "Épaisseur requise" in sortie
        assert "arrondi commercial" in sortie

    def test_produit_inconnu(self, capsys) -> None:
        assert main(
            [
                "dimensionner", "IPE 300", "--theta-cr", "550",
                "--duree", "R60", "--protection", "poudre_de_perlimpinpin",
            ]
        ) == 1
        assert "inconnue" in capsys.readouterr().err


class TestBalayer:
    def test_balayage_famille(self, capsys) -> None:
        assert main(["balayer", "--famille", "HEM", "--theta-cr", "550"]) == 0
        sortie = capsys.readouterr().out
        assert "HEM1000" in sortie
        assert "Am/V" in sortie

    def test_les_profils_trapus_tiennent_plus_longtemps(self, capsys) -> None:
        """La durée décroît avec le facteur de massiveté.

        L'ordre du catalogue n'est pas celui des A_m/V — la série HEM garde
        une épaisseur de semelle constante au-delà du HEM 320 — donc on trie
        sur A_m/V plutôt que de supposer l'ordre des lignes. La monotonie
        n'est pas exacte non plus, le facteur d'ombre variant d'un profilé à
        l'autre : on compare les extrêmes.
        """
        assert main(
            ["balayer", "--famille", "HEM", "--theta-cr", "550", "--format", "csv"]
        ) == 0
        lignes = capsys.readouterr().out.strip().splitlines()[1:]
        couples = sorted(
            (float(ligne.split(",")[1]), float(ligne.split(",")[2]))
            for ligne in lignes
        )
        (_, duree_plus_massif) = couples[-1]
        (_, duree_plus_trapu) = couples[0]
        assert duree_plus_trapu > duree_plus_massif


class TestProtections:
    def test_liste(self, capsys) -> None:
        assert main(["protections"]) == 0
        sortie = capsys.readouterr().out
        assert "flocage_fibreux" in sortie
        assert "AEAI" in sortie
