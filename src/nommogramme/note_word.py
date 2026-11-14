"""Note de calcul au format Word (.docx), à équations Word natives.

Même contenu que la note PDF : les mêmes ``etapes_de_calcul``, donc les mêmes
valeurs, lues dans le résultat. Seule la mise en forme change :

* chaque calcul est précédé de sa phrase de guidage, droite, 12 pt avant ;
* chaque ligne de calcul devient une **équation Word** éditable, une par
  paragraphe : LaTeX → MathML (``latex2mathml``) → OMML (``mathml2omml``) ;
* point décimal, tout en Arial 10, sans titre numéroté — préférences de la
  note de calcul de l'utilisateur.

Dépendances : ``python-docx``, ``latex2mathml``, ``mathml2omml`` (extra
``word``).
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from .note_pdf import Bloc, etapes_de_calcul
from .unites import en_minutes

__all__ = ["latex_vers_omml", "note_word"]

_NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def _latex(ligne: str) -> str:
    """Ligne mathtext de la note PDF → LaTeX accepté par ``latex2mathml``."""
    ligne = ligne.replace("{,}", ".").replace(r"\dfrac", r"\frac")
    ligne = ligne.replace(r"\acute{e}", "é").replace(r"\hat{a}", "â")
    # \mathrm{texte avec\ espaces} et \mathbf{Phrase\ en\ gras} → \text{…} :
    # sinon les mots deviennent des variables en italique, collées.
    def texte(m: re.Match) -> str:
        return r"\text{" + m.group(1).replace(r"\ ", " ") + "}"

    ligne = re.sub(r"\\mathrm\{([^{}]*)\}", texte, ligne)
    return re.sub(r"\\mathbf\{((?:[\w,.;:]|\\ )+\\ [^{}\\]*)\}", texte, ligne)


def _equations(ligne: str) -> list[str]:
    r"""Une ligne de la note → ses équations : ``\qquad`` sépare deux équations."""
    return [morceau.strip() for morceau in _latex(ligne).split(r"\qquad") if morceau.strip()]


def latex_vers_omml(latex: str) -> str:
    """Équation LaTeX → élément ``<m:oMath>`` (texte XML, espace de noms m)."""
    import latex2mathml.converter
    import mathml2omml

    omml = mathml2omml.convert(latex2mathml.converter.convert(latex))
    # shortcut: deux défauts de mathml2omml 0.0.2, réparés ici ; à retirer quand
    # le paquet sera corrigé. (1) <m:groupChrPr> (barres \bar) est fermé par
    # </m:groupChr>. (2) <m:rad> n'a pas de <m:deg> : Word et LibreOffice
    # prennent alors le contenu de la racine pour son degré.
    omml = re.sub(
        r"(<m:groupChrPr>(?:(?!</?m:groupChr).)*?)</m:groupChr>",
        r"\1</m:groupChrPr>", omml,
    )
    return omml.replace(
        "<m:rad><m:e>",
        '<m:rad><m:radPr><m:degHide m:val="on"/></m:radPr><m:deg/><m:e>',
    )


class _Document:
    def __init__(self) -> None:
        from docx import Document
        from docx.shared import Pt

        self.doc = Document()
        normal = self.doc.styles["Normal"]
        normal.font.name = "Arial"
        normal.font.size = Pt(10)
        # Arial aussi pour les caractères est-asiatiques, sinon Word garde sa police.
        normal.element.rPr.rFonts.set(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia", "Arial"
        )
        self.Pt = Pt

    def h(self, phrase: str) -> None:
        """Phrase de guidage : droite, 12 pt avant."""
        self.doc.add_paragraph(phrase).paragraph_format.space_before = self.Pt(12)

    def t(self, texte: str, gras: bool = False, discret: str = "") -> None:
        paragraphe = self.doc.add_paragraph()
        paragraphe.add_run(texte).bold = gras
        if discret:
            paragraphe.add_run(f"  ({discret})").italic = True

    def e(self, latex: str) -> None:
        """Une équation, seule dans son paragraphe."""
        from docx.oxml import parse_xml

        omml = latex_vers_omml(latex)
        paragraphe = self.doc.add_paragraph()
        paragraphe._p.append(parse_xml(
            f'<m:oMathPara xmlns:m="{_NS_M}">{omml}</m:oMathPara>'
        ))

    def tableau(self, bloc: Bloc) -> None:
        table = self.doc.add_table(rows=1, cols=len(bloc.entetes))
        table.style = "Table Grid"
        for cellule, entete in zip(table.rows[0].cells, bloc.entetes):
            cellule.text = entete
            cellule.paragraphs[0].runs[0].bold = True
        for rangee in bloc.rangees:
            for cellule, valeur in zip(table.add_row().cells, rangee):
                cellule.text = str(valeur)

    def figure(self, figure, legende: str) -> None:
        from docx.shared import Cm

        tampon = io.BytesIO()
        figure.savefig(tampon, format="png", dpi=200, bbox_inches="tight", facecolor="white")
        tampon.seek(0)
        self.doc.add_picture(tampon, width=Cm(16))
        self.doc.add_paragraph(legende).runs[0].italic = True


def note_word(r, chemin, section=None):
    """Écrit la note de calcul détaillée en .docx, figures comprises.

    ``chemin`` : chemin de fichier ou flux binaire. ``section`` : la section
    soudée d'origine, facultative, pour le détail des tôles et la coupe.
    """
    from .note_pdf import _fermer_figure
    from .nomogramme.trace import tracer_echauffement, tracer_nomogramme, tracer_section

    duree = en_minutes(r.duree_requise)
    d = _Document()
    d.t(f"Vérification au feu — {r.profil.nom}", gras=True)
    d.t(f"{r.nuance.value} · {r.exposition.value} · {r.courbe.nom} · "
        f"{r.protection or 'sans protection'} · {r.contexte.nom}")
    d.t(f"{r.verdict.value.upper()} pour R{duree:.0f} — θ_cr = {r.theta_cr:.0f} °C, "
        f"θ_a = {r.theta_a_a_echeance:.0f} °C à {duree:.0f} min", gras=True)

    for bloc in etapes_de_calcul(r, section):
        if bloc.genre == "titre":
            d.h(re.sub(r"^\d+\.\s*", "", bloc.texte))
        elif bloc.genre == "texte":
            d.t(bloc.texte)
        elif bloc.genre == "calcul":
            if bloc.guide:
                d.h(bloc.guide)
            d.t(bloc.texte, discret=bloc.reference)
            for ligne in bloc.lignes:
                for equation in _equations(ligne):
                    if re.fullmatch(r"\\text\{[^{}]*\}", equation):
                        d.t(equation[6:-1])  # une remarque, pas une équation
                    else:
                        d.e(equation)
        elif bloc.genre == "tableau":
            d.tableau(bloc)

    d.h("Figures")
    figures = [
        (tracer_nomogramme(r), "Nomogramme : μ₀ → θ_cr (gauche), échauffement (droite)."),
        (tracer_echauffement(r), "Échauffement de l'acier et des gaz."),
    ]
    figures.append((tracer_section(section or r.profil, exposition=r.exposition),
                    "Coupe de la section, à l'échelle."))
    for figure, legende in figures:
        d.figure(figure, legende)
        _fermer_figure(figure)

    if isinstance(chemin, (str, Path)):
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
    d.doc.save(chemin)
    return chemin
