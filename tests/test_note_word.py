"""Note Word : équations, unités, décimales, modèle de bureau, PDF par Word."""

from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("docx")
pytest.importorskip("latex2mathml")
pytest.importorskip("matplotlib")

from nommogramme.interface.saisie import CAISSON_SOUDE, Saisie, executer  # noqa: E402
from nommogramme.note_word import (  # noqa: E402
    Projet,
    _latex,
    _point,
    exporter_pdf,
    latex_vers_omml,
    note_word,
)


def _resultat():
    saisie = Saisie(type_section=CAISSON_SOUDE, N=-3500.0, My=100.0,
                    exposition="Caisson, 4 faces", duree=90,
                    protection="plaques_silicate", epaisseur=15.0)
    return executer(saisie), saisie.section()


def _texte_docx(flux) -> str:
    flux.seek(0)
    with zipfile.ZipFile(flux) as z:
        return z.read("word/document.xml").decode("utf-8")


class TestEquations:
    def test_lambda_barre_est_un_accent_pas_un_groupement(self) -> None:
        """λ̄² se lisait « λ puissance −2 » : la barre doit être un accent."""
        omml = latex_vers_omml(r"\bar{\lambda}_\theta^2")
        assert "<m:acc>" in omml and "groupChr" not in omml

    @pytest.mark.parametrize("latex, attendu", [
        (r"206{,}40\ \mathrm{cm^2}", "\\text{\u00a0cm²}"),
        (r"613{,}9\ \mathrm{kN\cdot m}", "\\text{\u00a0kN·m}"),
        (r"104{,}9\ \mathrm{min}", "\\text{\u00a0min}"),
    ])
    def test_unites_lisibles_et_espacees(self, latex: str, attendu: str) -> None:
        converti = _latex(latex)
        assert attendu in converti and "^" not in converti and r"\cdot" not in converti
        latex_vers_omml(converti)  # et le convertisseur l'accepte

    def test_point_decimal_partout(self) -> None:
        assert _point("θ = 539,9 °C ; 100,0 ; 0,0 kN·m") == "θ = 539.9 °C ; 100.0 ; 0.0 kN·m"
        assert _point("classes 1-2, puis 3") == "classes 1-2, puis 3"


class TestSansModele:
    def test_le_projet_figure_en_tete(self) -> None:
        r, section = _resultat()
        flux = io.BytesIO()
        note_word(r, flux, section, modele=None,
                  projet=Projet(nom="Pont du Lac", numero="2417", ingenieur="Ada Lovelace"))
        xml = _texte_docx(flux)
        assert "Pont du Lac · N° 2417 · note 1.0" in xml and "Ada Lovelace" in xml

    def test_titres_de_word_et_point_decimal(self) -> None:
        r, section = _resultat()
        flux = io.BytesIO()
        note_word(r, flux, section, modele=None)
        xml = _texte_docx(flux)
        assert 'w:val="Heading1"' in xml and 'w:val="Heading2"' in xml
        assert "539,9" not in xml and "groupChr" not in xml


class TestAvecModele:
    def test_un_modele_sans_styles_ingphi_ne_casse_rien(self, tmp_path) -> None:
        """Un modèle quelconque : styles Word de repli, pas d'erreur."""
        from docx import Document

        modele = tmp_path / "modele.docx"
        doc = Document()
        doc.add_paragraph("Titre")
        doc.save(modele)
        r, section = _resultat()
        flux = io.BytesIO()
        note_word(r, flux, section, modele=modele)
        assert "Données" in _texte_docx(flux)

    def test_modele_ingphi(self, tmp_path) -> None:
        """Le modèle du bureau, s'il est sur ce poste (il n'est pas dans le dépôt)."""
        racine = Path(os.environ.get("APPDATA", Path.home()))
        candidats = [racine / "Nommogramme" / "modele-note.dotx",
                     Path(__file__).parents[1] / "template note de calcul.dotx"]
        modele = next((c for c in candidats if c.is_file()), None)
        if modele is None:
            pytest.skip("modèle INGPHI absent de ce poste")
        r, section = _resultat()
        flux = io.BytesIO()
        projet = Projet(nom="Pont du Lac", numero="2417", ingenieur="Ada Lovelace",
                        version="2.1")
        note_word(r, flux, section, modele=modele, projet=projet)
        xml = _texte_docx(flux)
        assert "Pont du Lac" in xml and "INGPHI - 2417" in xml       # cartouche
        assert ">2.1<" in xml and "Ada Lovelace" in xml              # n° et signature
        assert "Prénom Nom" not in xml
        flux.seek(0)
        with zipfile.ZipFile(flux) as z:
            entetes = "".join(z.read(n).decode() for n in z.namelist() if "header" in n)
        assert "Pont du Lac" in entetes                              # en-tête
        assert "Résistance au feu — CRS 400×300×20/12" in xml        # page de garde
        # Exemple retiré. (« Titre niveau 1 » subsiste dans l'ancien résultat
        # de la table des matières, que Word recalcule à l'ouverture.)
        assert "Lorem ipsum" not in xml
        assert "JJ mois AAAA" not in xml and "jj.mm.aaaa" not in xml   # dates remplies
        assert '\\o "1-1"' in xml                                     # sommaire des chapitres
        assert "1TitreNiv1ChapitreINGPHI" in xml and "11TitreNiv2ChapitreINGPHI" in xml


def test_sans_word_le_pdf_retombe_sur_le_moteur_interne(tmp_path) -> None:
    """Hors Word (ou désactivé), la note PDF reste produite."""
    assert os.environ.get("NOMMOGRAMME_PDF_INTERNE") == "1"
    assert exporter_pdf(tmp_path / "a.docx", tmp_path / "a.pdf") is False
    r, section = _resultat()
    flux = io.BytesIO()
    r.note_de_calcul_pdf(flux, section)
    assert flux.getvalue().startswith(b"%PDF")
