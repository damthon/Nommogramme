"""Note de calcul au format Word (.docx), à équations Word natives.

Même contenu que la note PDF : les mêmes ``etapes_de_calcul``, donc les mêmes
valeurs, lues dans le résultat. Seule la mise en forme change :

* chaque calcul est un titre de niveau 2, suivi de sa phrase de guidage ;
* chaque ligne de calcul devient une **équation Word** éditable, une par
  paragraphe : LaTeX → MathML (``latex2mathml``) → OMML (``mathml2omml``) ;
* point décimal partout, équations comme texte et tableaux.

Modèle de bureau
----------------

Avec un modèle Word (.dotx ou .docx) aux styles INGPHI, la note en reprend
tout : page de garde et cartouche, table des matières, en-têtes et pieds de
page, titres numérotés, styles de texte, de tableau et de légende, bloc de
signature. Le modèle n'est **pas** livré avec le programme — il appartient au
bureau : ``modele_par_defaut()`` le cherche dans la variable d'environnement
``NOMMOGRAMME_MODELE_WORD``, puis dans ``%APPDATA%/Nommogramme/modele-note.dotx``.
Sans modèle, la note reste sobre, avec les titres intégrés de Word.

Dépendances : ``python-docx``, ``latex2mathml``, ``mathml2omml`` (extra
``word``).
"""

from __future__ import annotations

import copy
import datetime
import io
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .note_pdf import Bloc, etapes_de_calcul
from .unites import en_minutes

__all__ = ["Projet", "exporter_pdf", "latex_vers_omml", "modele_par_defaut",
           "note_pdf_par_word", "note_word"]


@dataclass(frozen=True, slots=True)
class Projet:
    """Ce que la note dit de l'affaire, et que le calcul ignore.

    Un champ vide laisse l'emplacement du modèle (« XXXX », « Prénom Nom ») :
    on le complète alors dans Word. La date est toujours celle du jour.
    """

    nom: str = ""
    numero: str = ""
    ingenieur: str = ""
    """Prénom et nom de l'ingénieur, pour le bloc de signature."""
    version: str = "1.0"
    """Numéro de la note — le « N° » du cartouche."""

_NS_M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

_EXPOSANTS = (("^{-1}", "⁻¹"), ("^{-2}", "⁻²"), ("^{-4}", "⁻⁴"), ("^{-8}", "⁻⁸"),
              ("^2", "²"), ("^3", "³"), ("^4", "⁴"), ("^6", "⁶"))
"""Exposants d'unités, en caractères : ils restent lisibles dans un \\text."""

_MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
         "septembre", "octobre", "novembre", "décembre")


# --- texte et équations --------------------------------------------------------


def _point(texte: str) -> str:
    """Virgule décimale → point : « 539,9 °C » devient « 539.9 °C ».

    Les textes de la note sont partagés avec la note PDF, qui écrit la virgule ;
    la note Word suit la préférence du bureau, le point, jusque dans les
    tableaux. Seule une virgule entre deux chiffres est touchée.
    """
    return re.sub(r"(?<=\d),(?=\d)", ".", texte)


def _latex(ligne: str) -> str:
    """Ligne mathtext de la note PDF → LaTeX accepté par ``latex2mathml``."""
    ligne = ligne.replace("{,}", ".").replace(r"\dfrac", r"\frac")
    ligne = ligne.replace(r"\acute{e}", "é").replace(r"\hat{a}", "â")

    # \mathrm{texte avec\ espaces} et \mathbf{Phrase\ en\ gras} → \text{…} :
    # sinon les mots deviennent des variables en italique, collées. Les unités
    # passent aussi en texte, exposants et point médian en caractères :
    # \mathrm{cm^2} → « cm² », \mathrm{kN\cdot m} → « kN·m ». Laissés en
    # commandes, Word écrivait « cm^2 » ou « \cdot » en toutes lettres.
    def texte(m: re.Match) -> str:
        contenu = re.sub(r"\s*\\cdot\s*", "·", m.group(1).replace(r"\ ", " "))
        for motif, exposant in _EXPOSANTS:
            contenu = contenu.replace(motif, exposant)
        if "\\" in contenu or "^" in contenu or "_" in contenu:
            return m.group(0)  # vraie expression : on la laisse au convertisseur
        return r"\text{" + contenu.replace("  ", " ") + "}"

    ligne = re.sub(r"\\mathrm\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", texte, ligne)
    ligne = re.sub(r"\\mathbf\{((?:[\w,.;:]|\\ )+\\ [^{}\\]*)\}", texte, ligne)
    # Une espace « \ » est perdue entre MathML et Word : « 206.40cm² »,
    # « 104.9min ». Collée au texte qui suit, elle tient.
    ligne = ligne.replace(r"\ \text{", "\\text{\u00a0")
    return ligne.replace(r"\ ", "\\text{\u00a0}")


def _equations(ligne: str) -> list[str]:
    r"""Une ligne de la note → ses équations : ``\qquad`` sépare deux équations."""
    return [morceau.strip() for morceau in _latex(ligne).split(r"\qquad") if morceau.strip()]


def latex_vers_omml(latex: str) -> str:
    """Équation LaTeX → élément ``<m:oMath>`` (texte XML, espace de noms m)."""
    import latex2mathml.converter
    import mathml2omml

    omml = mathml2omml.convert(latex2mathml.converter.convert(latex))
    # shortcut: défauts de mathml2omml 0.0.2, réparés ici ; à retirer quand le
    # paquet sera corrigé. (1) <m:groupChrPr> est fermé par </m:groupChr>.
    # (2) <m:rad> n'a pas de <m:deg> : Word prend alors le contenu de la
    # racine pour son degré.
    omml = re.sub(
        r"(<m:groupChrPr>(?:(?!</?m:groupChr).)*?)</m:groupChr>",
        r"\1</m:groupChrPr>", omml,
    )
    omml = omml.replace(
        "<m:rad><m:e>",
        '<m:rad><m:radPr><m:degHide m:val="on"/></m:radPr><m:deg/><m:e>',
    )
    # (3) \bar devient un « caractère de groupement » <m:groupChr>, que Word
    # dessine à côté du symbole : λ̄² se lisait « λ puissance −2 ». Un accent
    # <m:acc> pose la barre sur la lettre, comme l'écrit la norme.
    return re.sub(
        r'<m:groupChr><m:groupChrPr><m:chr m:val="[¯‾]"/><m:pos m:val="top"/>'
        r"</m:groupChrPr><m:e>((?:(?!</?m:groupChr).)*?)</m:e></m:groupChr>",
        '<m:acc><m:accPr><m:chr m:val="\u0305"/></m:accPr><m:e>\\1</m:e></m:acc>',
        omml,
    )


# --- modèle ---------------------------------------------------------------------


def dossier_utilisateur() -> Path:
    """Le dossier propre à l'utilisateur : modèle Word, préférences.

    ``%APPDATA%/Nommogramme`` sous Windows, ``~/.config/Nommogramme`` ailleurs ;
    ``NOMMOGRAMME_DOSSIER`` le déplace (les tests l'envoient dans un dossier
    temporaire, pour ne jamais toucher aux réglages réels).
    """
    if os.environ.get("NOMMOGRAMME_DOSSIER"):
        return Path(os.environ["NOMMOGRAMME_DOSSIER"])
    racine = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(racine) / "Nommogramme"


def modele_par_defaut() -> Path | None:
    """Le modèle Word du bureau, s'il est installé sur ce poste.

    ``NOMMOGRAMME_SANS_MODELE=1`` l'ignore (tests reproductibles).
    """
    if os.environ.get("NOMMOGRAMME_SANS_MODELE") == "1":
        return None
    candidats = [os.environ.get("NOMMOGRAMME_MODELE_WORD", ""),
                 str(dossier_utilisateur() / "modele-note.dotx")]
    return next((Path(c) for c in candidats if c and Path(c).is_file()), None)


def _ouvrir_modele(modele: Path):
    """Ouvre un .dotx comme un document : python-docx refuse le type « modèle »."""
    from docx import Document

    brut = io.BytesIO()
    with zipfile.ZipFile(modele) as source, zipfile.ZipFile(brut, "w") as cible:
        for element in source.infolist():
            donnees = source.read(element.filename)
            if element.filename == "[Content_Types].xml":
                donnees = donnees.replace(b"template.main+xml", b"document.main+xml")
            cible.writestr(element, donnees)
    brut.seek(0)
    return Document(brut)


# Styles du modèle INGPHI, et leurs équivalents intégrés de Word sans modèle.
_STYLES = {
    "titre1": ("1_Titre_Niv1_Chapitre_INGPHI", "Heading 1"),
    "titre2": ("1.1_Titre_Niv2_Chapitre_INGPHI", "Heading 2"),
    "premier": ("02a_Texte_Premier_Paragraphe_INGPHI", "Normal"),
    "suivant": ("02b_Texte_Paragraphes_Suivants_INGPHI", "Normal"),
    "tableau": ("05_Texte_Tableaux_INGPHI", "Normal"),
    "legende": ("07_Légende_Images_INGPHI", "Caption"),
}


class _Document:
    """Le document en construction, avec ou sans modèle de bureau."""

    def __init__(self, modele: Path | None) -> None:
        from docx import Document
        from docx.shared import Pt

        self.Pt = Pt
        self.avec_modele = modele is not None
        self.projet = Projet()
        self.signature: list = []
        self._apres_titre = True
        if modele is None:
            self.doc = Document()
            normal = self.doc.styles["Normal"]
            normal.font.name = "Arial"
            normal.font.size = Pt(10)
            normal.element.rPr.rFonts.set(f"{_NS_W}eastAsia", "Arial")
            return
        self.doc = _ouvrir_modele(modele)
        self._vider_modele()

    def _vider_modele(self) -> None:
        """Garde la page de garde et la table des matières, retire l'exemple.

        Le bloc de signature — à partir de « … SA, le … » — est mis de côté
        pour être remis en fin de note.
        """
        corps = self.doc.element.body
        elements = [e for e in corps.iterchildren() if not e.tag.endswith("sectPr")]
        debut = next(
            (i for i, e in enumerate(elements) if self._style(e).startswith("1TitreNiv1")),
            len(elements),
        )
        signature = next(
            (i for i, e in enumerate(elements) if i > debut and ", le " in self._texte(e)),
            None,
        )
        if signature is not None:
            # Les paragraphes vides qui précèdent la date l'écartent du texte.
            while signature > debut and not self._texte(elements[signature - 1]).strip() \
                    and self._style(elements[signature - 1]).startswith("02"):
                signature -= 1
            self.signature = [copy.deepcopy(e) for e in elements[signature:]]
        for element in elements[debut:]:
            corps.remove(element)
        # Table des matières limitée aux chapitres : chaque calcul y figurerait
        # sinon, et elle s'étendrait sur deux pages pour une note de quinze.
        for instruction in corps.iter(f"{_NS_W}instrText"):
            if instruction.text and "TOC" in instruction.text:
                instruction.text = re.sub(r'\\o "\d-\d"', r'\\o "1-1"', instruction.text)
                instruction.text = re.sub(r'\\t "[^"]*"', "", instruction.text)

    @staticmethod
    def _style(element) -> str:
        style = element.find(f"{_NS_W}pPr/{_NS_W}pStyle")
        return style.get(f"{_NS_W}val", "") if style is not None else ""

    @staticmethod
    def _texte(element) -> str:
        return "".join(t.text or "" for t in element.iter(f"{_NS_W}t"))

    def _style_de(self, cle: str) -> str:
        """Le style INGPHI s'il existe dans le modèle, sinon l'équivalent Word."""
        ingphi, integre = _STYLES[cle]
        if self.avec_modele:
            noms = {s.name for s in self.doc.styles}
            if ingphi in noms:
                return ingphi
            if integre not in noms:
                return "Normal"
        return integre

    # -- page de garde -------------------------------------------------------

    def garde(self, titre: str, sous_titre: str, sujet: str, image, projet: Projet) -> None:
        """Remplit la page de garde, le cartouche et l'en-tête du modèle."""
        self.projet = projet
        date = datetime.date.today().strftime("%d.%m.%Y")
        if not self.avec_modele:
            self.doc.add_heading(titre, level=0)
            self.paragraphe(sous_titre, gras=True)
            entete = " · ".join(v for v in (
                projet.nom, projet.numero and f"N° {projet.numero}",
                f"note {projet.version}" if projet.version else "", date,
                projet.ingenieur) if v)
            self.paragraphe(entete)
            return
        remplacements = {
            "Titre": titre, "Sous-titre": sous_titre, "Type de document": "Note de calcul",
        }
        for paragraphe in self.doc.paragraphs[:4]:
            texte = paragraphe.text.strip()
            if texte in remplacements:
                self._remplacer(paragraphe, remplacements[texte])
        # Le cartouche : chaque libellé remplit la cellule qui le suit. Une
        # valeur vide laisse « XXXX », à compléter dans Word ; le mandant et la
        # distribution, que le programme ne connaît pas, aussi.
        valeurs = {
            "Projet": projet.nom, "N° de projet": projet.numero, "Sujet": sujet,
            "Date": date, "N°": projet.version,
        }
        for table in self.doc.tables[:1]:
            for rangee in table.rows:
                cellules, vues = [], set()
                for cellule in rangee.cells:  # une cellule fusionnée revient plusieurs fois
                    if id(cellule._tc) not in vues:
                        vues.add(id(cellule._tc))
                        cellules.append(cellule)
                for libelle, valeur in zip(cellules, cellules[1:]):
                    nouvelle = valeurs.get(libelle.text.strip())
                    if not nouvelle:
                        continue
                    # « INGPHI - XXXX » : seul l'emplacement est remplacé, et le
                    # préfixe du bureau reste — sauf si on l'a déjà saisi.
                    ancienne = valeur.text.strip()
                    prefixe = ancienne.partition("XXXX")[0].strip() if "XXXX" in ancienne else ""
                    if prefixe and not nouvelle.startswith(prefixe):
                        nouvelle = ancienne.replace("XXXX", nouvelle)
                    self._remplacer(valeur.paragraphs[0], nouvelle)
        # L'image de garde : la coupe de la section, à la place de l'emplacement
        # réservé de 170 × 100 mm — bornée en hauteur et centrée, une coupe
        # étant souvent plus haute que large.
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        for paragraphe in self.doc.paragraphs[:6]:
            dessins = paragraphe._p.findall(f".//{_NS_W}drawing")
            if dessins:
                for dessin in dessins:
                    dessin.getparent().remove(dessin)
                paragraphe.alignment = WD_ALIGN_PARAGRAPH.CENTER
                self._image(paragraphe.add_run(), image, hauteur_cm=10.0)
                break
        # L'en-tête des pages suivantes : « Nom du projet – Titre – Type ».
        for section in self.doc.sections:
            for entete in (section.header, section.first_page_header, section.even_page_header):
                for paragraphe in entete.paragraphs:
                    for run in paragraphe.runs:
                        if run.text.strip() == "– Titre –":
                            run.text = f"– {titre} –"
                        elif run.text.strip() == "Type de document":
                            run.text = "Note de calcul"
                        elif run.text.strip() == "Nom du projet" and projet.nom:
                            run.text = projet.nom

    @staticmethod
    def _remplacer(paragraphe, texte: str) -> None:
        """Remplace le texte d'un paragraphe en gardant la mise en forme du 1er run."""
        runs = paragraphe.runs
        if not runs:
            paragraphe.add_run(texte)
            return
        runs[0].text = texte
        for run in runs[1:]:
            run.text = ""

    # -- contenu --------------------------------------------------------------

    def titre(self, texte: str, niveau: int) -> None:
        if self.avec_modele:
            paragraphe = self.doc.add_paragraph(texte, style=self._style_de(f"titre{niveau}"))
        else:
            paragraphe = self.doc.add_heading(texte, level=niveau)
        # Jamais seul en bas de page : un titre suit son contenu.
        paragraphe.paragraph_format.keep_with_next = True
        self._apres_titre = True

    def paragraphe(self, texte: str, gras: bool = False, discret: str = "") -> None:
        style = self._style_de("premier" if self._apres_titre else "suivant")
        paragraphe = self.doc.add_paragraph(style=style)
        paragraphe.add_run(_point(texte)).bold = gras
        if discret:
            paragraphe.add_run(f"  ({_point(discret)})").italic = True
        self._apres_titre = False

    def equation(self, latex: str) -> None:
        """Une équation, seule dans son paragraphe."""
        from docx.oxml import parse_xml

        paragraphe = self.doc.add_paragraph(style=self._style_de("suivant"))
        paragraphe._p.append(parse_xml(
            f'<m:oMathPara xmlns:m="{_NS_M}">{latex_vers_omml(latex)}</m:oMathPara>'
        ))
        self._apres_titre = False

    def tableau(self, bloc: Bloc) -> None:
        table = self.doc.add_table(rows=1, cols=len(bloc.entetes))
        table.style = "Table Grid"
        style = self._style_de("tableau")
        for cellule, entete in zip(table.rows[0].cells, bloc.entetes):
            cellule.paragraphs[0].style = style
            cellule.paragraphs[0].add_run(_point(entete)).bold = True
        for rangee in bloc.rangees:
            for cellule, valeur in zip(table.add_row().cells, rangee):
                cellule.paragraphs[0].style = style
                cellule.paragraphs[0].add_run(_point(str(valeur)))
        self._apres_titre = False

    def figure(self, figure, legende: str, largeur_cm: float = 16.5) -> None:
        from docx.enum.text import WD_ALIGN_PARAGRAPH

        paragraphe = self.doc.add_paragraph(style=self._style_de("suivant"))
        paragraphe.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraphe.paragraph_format.keep_with_next = True
        self._image(paragraphe.add_run(), figure, largeur_cm)
        self.doc.add_paragraph(legende, style=self._style_de("legende"))

    @staticmethod
    def _image(run, figure, largeur_cm: float | None = None,
               hauteur_cm: float | None = None) -> None:
        from docx.shared import Cm

        tampon = io.BytesIO()
        figure.savefig(tampon, format="png", dpi=200, bbox_inches="tight", facecolor="white")
        tampon.seek(0)
        run.add_picture(
            tampon,
            width=Cm(largeur_cm) if largeur_cm else None,
            height=Cm(hauteur_cm) if hauteur_cm else None,
        )

    def terminer(self) -> None:
        """Remet le bloc de signature, daté du jour."""
        if not self.signature:
            return
        aujourdhui = datetime.date.today()
        date = f"{aujourdhui.day} {_MOIS[aujourdhui.month - 1]} {aujourdhui.year}"
        corps = self.doc.element.body
        fin = corps.find(f"{_NS_W}sectPr")
        for element in self.signature:
            # « JJ mois AAAA » est découpé en plusieurs runs : on remplace au
            # niveau du paragraphe, le texte entier dans le premier run.
            morceaux = list(element.iter(f"{_NS_W}t"))
            texte = "".join(t.text or "" for t in morceaux)
            nouveau = texte.replace("JJ mois AAAA", date)
            if self.projet.ingenieur and texte.strip() == "Prénom Nom":
                nouveau = self.projet.ingenieur
            if nouveau != texte:
                morceaux[0].text = nouveau
                for t in morceaux[1:]:
                    t.text = ""
            if fin is not None:
                fin.addprevious(element)
            else:
                corps.append(element)
        if not self.avec_modele:
            return
        # La table des matières est un champ : Word la recalcule à l'ouverture.
        reglages = self.doc.settings.element
        if reglages.find(f"{_NS_W}updateFields") is None:
            from docx.oxml import OxmlElement

            maj = OxmlElement("w:updateFields")
            maj.set(f"{_NS_W}val", "true")
            reglages.append(maj)


_SCRIPT_PDF = (
    "$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
    "try { $d = $w.Documents.Open($env:NOMMO_DOCX, $false, $true); "
    "foreach ($t in $d.TablesOfContents) { $t.Update() }; $d.Fields.Update() | Out-Null; "
    "$d.SaveAs2($env:NOMMO_PDF, 17); $d.Close($false) } finally { $w.Quit() }"
)


def exporter_pdf(docx: Path, pdf: Path) -> bool:
    """Fait convertir un .docx en PDF par Word lui-même ; ``False`` sans Word.

    C'est ce qui rend le PDF identique à la note Word : même moteur de mise en
    page, table des matières et numéros de page recalculés. Word est piloté
    par PowerShell, sans dépendance Python ; les chemins passent par
    l'environnement, ce qui épargne tout problème de guillemets.
    ``NOMMOGRAMME_PDF_INTERNE=1`` désactive la voie Word (tests, poste lent).
    """
    import subprocess
    import sys

    if sys.platform != "win32" or os.environ.get("NOMMOGRAMME_PDF_INTERNE") == "1":
        return False
    environnement = {**os.environ, "NOMMO_DOCX": str(docx), "NOMMO_PDF": str(pdf)}
    try:
        execution = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCRIPT_PDF],
            env=environnement, capture_output=True, timeout=240,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return execution.returncode == 0 and Path(pdf).is_file()


def note_pdf_par_word(r, chemin, section=None, projet: Projet | None = None) -> bool:
    """La note PDF, convertie par Word depuis la note Word ; ``False`` sans Word."""
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as dossier:
        docx, pdf = Path(dossier) / "note.docx", Path(dossier) / "note.pdf"
        note_word(r, docx, section, projet=projet)
        if not exporter_pdf(docx, pdf):
            return False
        if isinstance(chemin, (str, Path)):
            Path(chemin).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf, chemin)
        else:
            chemin.write(pdf.read_bytes())
    return True


def note_word(r, chemin, section=None, modele: Path | str | None = "defaut",
              projet: Projet | None = None):
    """Écrit la note de calcul détaillée en .docx, figures comprises.

    ``chemin`` : chemin de fichier ou flux binaire. ``section`` : la section
    soudée d'origine, facultative, pour le détail des tôles et la coupe.
    ``modele`` : le modèle Word du bureau ; « defaut » le cherche avec
    ``modele_par_defaut()``, ``None`` produit une note sans modèle.
    """
    from .nomogramme.trace import tracer_echauffement, tracer_nomogramme, tracer_section
    from .note_pdf import _fermer_figure

    if modele == "defaut":
        modele = modele_par_defaut()
    d = _Document(Path(modele) if modele else None)

    duree = en_minutes(r.duree_requise)
    titre = f"Résistance au feu — {r.profil.nom}"
    sous_titre = (f"{r.nuance.value} · R{duree:.0f} · "
                  f"{r.protection.libelle or r.protection.nom if r.protection else 'sans protection'}")
    verdict = (f"{r.verdict.value.upper()} pour R{duree:.0f} — θ_cr = {r.theta_cr:.0f} °C, "
               f"θ_a = {r.theta_a_a_echeance:.0f} °C à {duree:.0f} min")
    garde = tracer_section(section or r.profil, exposition=r.exposition)
    d.garde(titre, sous_titre, f"Résistance au feu — {r.profil.nom}", garde,
            projet or Projet())
    _fermer_figure(garde)
    if not d.avec_modele:
        d.paragraphe(f"{r.exposition.value} · {r.courbe.nom} · {r.contexte.nom}")
    d.paragraphe(verdict, gras=True)

    for bloc in etapes_de_calcul(r, section):
        if bloc.genre == "titre":
            d.titre(re.sub(r"^\d+\.\s*", "", bloc.texte), 1)
        elif bloc.genre == "texte":
            d.paragraphe(bloc.texte)
        elif bloc.genre == "calcul":
            d.titre(_point(bloc.texte), 2)
            if bloc.guide:
                d.paragraphe(bloc.guide, discret=bloc.reference)
            elif bloc.reference:
                d.paragraphe("", discret=bloc.reference)
            for ligne in bloc.lignes:
                for equation in _equations(ligne):
                    if re.fullmatch(r"\\text\{[^{}]*\}", equation):
                        d.paragraphe(equation[6:-1])  # une remarque, pas une équation
                    else:
                        d.equation(equation)
        elif bloc.genre == "tableau":
            d.tableau(bloc)

    d.titre("Figures", 1)
    figures = [
        (tracer_nomogramme(r), "Nomogramme : μ₀ → θ_cr (gauche), échauffement (droite)."),
        (tracer_echauffement(r), "Échauffement de l'acier et des gaz."),
        (tracer_section(section or r.profil, exposition=r.exposition),
         "Coupe de la section, à l'échelle."),
    ]
    for numero, (figure, legende) in enumerate(figures, start=1):
        d.figure(figure, f"Figure {numero} : {legende}",
                 largeur_cm=12.0 if numero == 3 else 16.5)
        _fermer_figure(figure)
    d.terminer()

    if isinstance(chemin, (str, Path)):
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
    d.doc.save(chemin)
    return chemin
