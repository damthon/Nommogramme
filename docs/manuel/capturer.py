"""Régénère les captures d'écran du manuel d'utilisation.

Pilote l'application de bureau sur le cas du manuel — caisson soudé
400 × 300 × 20/12 protégé par plaques — et photographie la fenêtre à chaque
étape, le bloc concerné encadré et numéroté. Produit aussi la note PDF du cas
et en extrait quelques pages en image.

Demande un écran : sous Linux sans affichage,

    xvfb-run -s "-screen 0 1600x1300x24 -fp ~/.fonts,built-ins" \\
        python docs/manuel/capturer.py

où ``~/.fonts`` contient les polices DejaVu indexées par ``mkfontscale`` et
``mkfontdir`` : sans elles, un Tk sans Xft n'affiche pas les lettres grecques.
Il faut aussi ``pdftoppm`` (poppler) pour les pages de la note.
"""

from __future__ import annotations

import subprocess
import sys
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageGrab

from nommogramme.interface.bureau import Application
from nommogramme.interface.saisie import CAISSON_SOUDE

ICI = Path(__file__).resolve().parent
IMAGES = ICI / "images"
ACCENT = (180, 74, 22)


def _polices_unicode(racine: tk.Tk) -> None:
    """Bascule les polices de Tk sur DejaVu si elle est disponible.

    Sous Windows, Tk trouve seul une police qui couvre θ, κ, μ ; sous un écran
    virtuel Linux, il faut la lui désigner.
    """
    from tkinter import font

    familles = {f.lower(): f for f in font.families(racine)}
    if "dejavu sans" not in familles:
        return
    for nom in font.names(racine):
        mono = nom in ("TkFixedFont",)
        font.nametofont(nom, racine).configure(
            family=familles["dejavu sans mono" if mono else "dejavu sans"]
        )


def _bloc(racine: tk.Misc, titre: str) -> tk.Misc:
    """Le cadre titré ``titre``, où qu'il soit dans la fenêtre."""
    for enfant in racine.winfo_children():
        try:
            if enfant.cget("text") == titre:
                return enfant
        except tk.TclError:
            pass
        trouve = _bloc(enfant, titre)
        if trouve is not None:
            return trouve
    return None


def _photo(racine: tk.Tk, app, nom: str, cibles=(), numero: str | None = None) -> None:
    """Capture la fenêtre, encadre ``cibles`` et y pose le numéro d'étape."""
    racine.update()
    app.dessiner_figures()
    racine.update()
    racine.after(300)
    racine.update()
    x0, y0 = racine.winfo_rootx(), racine.winfo_rooty()
    image = ImageGrab.grab(
        bbox=(x0, y0, x0 + racine.winfo_width(), y0 + racine.winfo_height())
    ).convert("RGB")
    dessin = ImageDraw.Draw(image)
    try:
        police = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
    except OSError:
        police = ImageFont.load_default()
    for widget in cibles:
        gauche = widget.winfo_rootx() - x0 - 4
        haut = widget.winfo_rooty() - y0 - 4
        droite = gauche + widget.winfo_width() + 8
        bas = haut + widget.winfo_height() + 8
        dessin.rectangle((gauche, haut, droite, bas), outline=ACCENT, width=4)
        if numero:
            dessin.ellipse((droite - 40, haut + 6, droite - 8, haut + 38), fill=ACCENT)
            dessin.text((droite - 24, haut + 22), numero, fill="white", font=police,
                        anchor="mm")
    image.save(IMAGES / f"{nom}.png", optimize=True)
    print(f"  {nom}.png")


def main() -> int:
    IMAGES.mkdir(parents=True, exist_ok=True)
    racine = tk.Tk()
    _polices_unicode(racine)
    racine.geometry("1500x1180+0+0")
    app = Application(racine)
    racine.update()
    app.dessiner_figures()
    _photo(racine, app, "01-demarrage")

    v = app.var
    v["type_section"].set(CAISSON_SOUDE)
    racine.update()
    for cle, valeur in (("h_soudee", 400.0), ("b_soudee", 300.0),
                        ("tf_soudee", 20.0), ("tw_soudee", 12.0)):
        v[cle].set(valeur)
    v["nuance"].set("S355")
    racine.update()
    _photo(racine, app, "02-section", (_bloc(racine, "Élément"),
                                  _bloc(racine, "Section soudée  ·  cotes en mm")), "1")

    for cle, valeur in (("N", -3500.0), ("My", 100.0), ("Mz", 0.0), ("L", 4.0),
                        ("l_fi", 2.0), ("beta_M", 1.4)):
        v[cle].set(valeur)
    racine.update()
    _photo(racine, app, "03-sollicitations", (_bloc(racine, "Sollicitations en incendie"),
                                         _bloc(racine, "Géométrie")), "2")

    v["exposition"].set("Caisson, 4 faces")
    v["duree"].set(90)
    v["protection"].set(app._libelle_produit("plaques_silicate"))
    racine.update()
    v["epaisseur"].set(15.0)
    racine.update()
    _photo(racine, app, "04-feu-protection", (_bloc(racine, "Exposition au feu"),
                                        _bloc(racine, "Protection"),
                                        _bloc(racine, "Paramètres avancés")), "3")

    app.onglets.select(app.cadre_figure["nomogramme"])
    racine.update()
    app.dessiner_figures()
    _photo(racine, app, "05-resultats", (app.details.master,), "4")
    _photo(racine, app, "06-nomogramme", (app.onglets,), "5")

    app.onglets.select(app.cadre_figure["echauffement"])
    racine.update()
    app.dessiner_figures()
    _photo(racine, app, "07-echauffement", (app.onglets,), "5")

    app.onglets.select(app.cadre_figure["section"])
    racine.update()
    app.dessiner_figures()
    _photo(racine, app, "08-coupe", (app.onglets,), "5")

    note = IMAGES / "note-exemple.pdf"
    app.resultat.note_de_calcul_pdf(note, app.saisie().section())
    print(f"  {note.name} — {app.resultat}")
    racine.destroy()

    subprocess.run(
        ["pdftoppm", "-r", "70", "-png", str(note), str(IMAGES / "note-page")],
        check=True,
    )
    for page in sorted(IMAGES.glob("note-page-*.png")):
        Image.open(page).convert("RGB").save(page, optimize=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
