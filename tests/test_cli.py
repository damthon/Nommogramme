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


class TestVerifier:
    def test_verification_complete(self, capsys) -> None:
        code = main(
            [
                "verifier", "HEB 300", "--nuance", "S355",
                "--N", "850", "--My", "120", "--L", "4", "--lfi", "2",
                "--duree", "R60",
            ]
        )
        sortie = capsys.readouterr().out
        assert "μ₀" in sortie
        assert "θ_cr éq. (4.22)" in sortie
        assert "θ_cr vérif. croisée" in sortie
        assert code in (0, 2)

    def test_code_de_sortie_signale_l_echec(self, capsys) -> None:
        """Un élément nu sous forte charge ne tient pas R90 : code 2."""
        code = main(
            ["verifier", "HEB 300", "--N", "850", "--My", "120",
             "--L", "4", "--lfi", "2", "--duree", "R90"]
        )
        assert code == 2
        assert "NON SATISFAIT" in capsys.readouterr().out

    def test_la_protection_fait_passer(self, capsys) -> None:
        code = main(
            ["verifier", "HEB 300", "--N", "850", "--My", "120",
             "--L", "4", "--lfi", "2", "--duree", "R60",
             "--protection", "flocage_fibreux", "--dp", "25"]
        )
        assert code == 0
        assert "SATISFAIT" in capsys.readouterr().out

    def test_avertissement_si_le_nomogramme_est_optimiste(self, capsys) -> None:
        main(
            ["verifier", "HEB 300", "--N", "850", "--My", "120",
             "--L", "8", "--lfi", "8", "--duree", "R60"]
        )
        assert "non conservatif" in capsys.readouterr().out

    def test_maintien_lateral(self, capsys) -> None:
        main(
            ["verifier", "IPE 300", "--nuance", "S235", "--My", "60",
             "--L", "6", "--duree", "R30", "--maintien-lateral"]
        )
        assert "4.21a" in capsys.readouterr().out

    def test_choix_du_referentiel(self, capsys) -> None:
        main(["verifier", "HEB 300", "--N", "500", "--L", "4",
              "--duree", "R30", "--contexte", "eurocode"])
        assert "Eurocode" in capsys.readouterr().out

    def test_ecriture_de_la_note(self, tmp_path, capsys) -> None:
        destination = tmp_path / "note.md"
        main(
            ["verifier", "HEB 300", "--N", "850", "--My", "120",
             "--L", "4", "--lfi", "2", "--duree", "R60",
             "--rapport", str(destination)]
        )
        capsys.readouterr()
        contenu = destination.read_text(encoding="utf-8")
        assert contenu.startswith("# Vérification au feu — HEB300")
        assert "éq. (4.22)" in contenu
        assert "## Verdict" in contenu


class TestSection:
    """La commande ``section`` et les sections soudées de ``verifier``."""

    _CAISSON = [
        "--section", "caisson", "--h", "400", "--b", "300",
        "--tf", "20", "--tw", "12",
    ]
    _PRS = [
        "--section", "h", "--h", "600", "--b", "300", "--tf", "20",
        "--tw", "10", "--b-inf", "200", "--tf-inf", "15",
    ]

    def test_caracteristiques_d_un_caisson(self, capsys) -> None:
        assert main(["section", *self._CAISSON]) == 0
        sortie = capsys.readouterr().out
        assert "CRS 400×300×20/12" in sortie
        assert "206.4 cm²" in sortie          # 2·300·20 + 2·360·12
        assert "A_m/V" in sortie

    def test_caracteristiques_d_un_prs(self, capsys) -> None:
        assert main(["section", *self._PRS]) == 0
        sortie = capsys.readouterr().out
        assert "PRS 600×300×20+200×15/10" in sortie
        assert "monosymétrique" in sortie, "la réserve doit être dite"

    def test_les_semelles_du_H_sont_egales_par_defaut(self, capsys) -> None:
        """Le cas courant ne doit pas demander de répéter les cotes."""
        assert main(
            ["section", "--section", "h", "--h", "600", "--b", "300",
             "--tf", "20", "--tw", "10"]
        ) == 0
        assert "PRS 600×300×20/10" in capsys.readouterr().out

    def test_la_face_couverte_change_le_perimetre(self, capsys) -> None:
        perimetres = []
        for face in ("superieure", "inferieure"):
            main(["section", *self._PRS, "--exposition", "contour3",
                  "--face-couverte", face])
            sortie = capsys.readouterr().out
            ligne = next(
                l for l in sortie.splitlines() if l.startswith("Périmètre exposé")
            )
            perimetres.append(float(ligne.split(":")[1].strip().removesuffix(" mm")))
        # Semelle supérieure de 300 mm, inférieure de 200 : couvrir la petite
        # laisse 100 mm de plus exposés.
        assert perimetres[1] - perimetres[0] == pytest.approx(100.0, abs=1.0)

    def test_une_cote_manquante_est_signalee(self, capsys) -> None:
        assert main(["section", "--section", "caisson", "--h", "400"]) == 1
        assert "--b est requis" in capsys.readouterr().err

    def test_sans_forme_la_commande_refuse(self, capsys) -> None:
        assert main(["section"]) == 1
        assert "Précisez la forme" in capsys.readouterr().err

    def test_une_geometrie_impossible_est_refusee(self, capsys) -> None:
        assert main(
            ["section", "--section", "caisson", "--h", "30", "--b", "300",
             "--tf", "20", "--tw", "12"]
        ) == 1
        assert "insuffisante" in capsys.readouterr().err

    def test_le_trace_ecrit_un_fichier(self, tmp_path, capsys) -> None:
        pytest.importorskip("matplotlib", reason="le tracé demande l'extra [trace]")
        destination = tmp_path / "coupe.png"
        assert main(["section", *self._CAISSON, "--tracer", str(destination)]) == 0
        capsys.readouterr()
        assert destination.stat().st_size > 5_000

    def test_verifier_accepte_une_section_soudee(self, capsys) -> None:
        code = main(
            ["verifier", *self._CAISSON, "--N", "800", "--My", "120",
             "--L", "4", "--lfi", "2", "--duree", "R30"]
        )
        sortie = capsys.readouterr().out
        assert "CRS 400×300×20/12" in sortie
        assert "(soudé)" in sortie
        assert code in (0, 2)

    def test_verifier_sans_profil_ni_section(self, capsys) -> None:
        assert main(["verifier", "--duree", "R30"]) == 1
        assert "--section" in capsys.readouterr().err

    def test_la_note_decrit_la_section(self, tmp_path, capsys) -> None:
        destination = tmp_path / "note.md"
        main(
            ["verifier", *self._PRS, "--N", "400", "--My", "80", "--L", "5",
             "--duree", "R60", "--exposition", "contour3",
             "--rapport", str(destination)]
        )
        capsys.readouterr()
        contenu = destination.read_text(encoding="utf-8")
        assert "Section reconstituée soudée" in contenu
        assert "Largeur masquée par la dalle" in contenu

    def test_tracer_section_exige_une_section(self, tmp_path, capsys) -> None:
        pytest.importorskip("matplotlib", reason="le tracé demande l'extra [trace]")
        assert main(
            ["verifier", "HEB 300", "--N", "500", "--L", "4", "--duree", "R30",
             "--tracer-section", str(tmp_path / "x.png")]
        ) == 1
        assert "section soudée" in capsys.readouterr().err


class TestProtections:
    def test_liste(self, capsys) -> None:
        assert main(["protections"]) == 0
        sortie = capsys.readouterr().out
        assert "flocage_fibreux" in sortie
        assert "AEAI" in sortie
