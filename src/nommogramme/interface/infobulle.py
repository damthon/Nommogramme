"""Infobulles de l'interface de bureau.

Tkinter n'en fournit pas, et l'interface en a besoin pour une raison précise :
les paramètres avancés — κ₁, κ₂, C₁, β_M — ne se comprennent pas sans leur
clause normative, et cette clause ne tient pas sur une étiquette de formulaire.
L'écrire en permanence à côté de chaque champ noierait l'écran ; la taire
oblige à sortir la norme.

L'infobulle est le compromis : rien à l'écran tant qu'on ne demande pas,
le texte complet au survol.

Trois détails qui n'en sont pas
-------------------------------

* **Le délai.** Sans lui, l'infobulle clignote au moindre passage de souris
  vers un autre champ. Un demi-battement suffit à distinguer « je passe » de
  « je m'arrête ».
* **Le clavier.** L'infobulle apparaît aussi à la prise de focus : un
  utilisateur qui tabule d'un champ à l'autre a droit à la même information
  que celui qui survole.
* **Le placement.** La bulle est décalée sous le pointeur, et ramenée dans
  l'écran si elle en sortait — sur un champ situé en bas de fenêtre, elle
  s'afficherait sinon hors de vue.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

__all__ = ["Infobulle", "infobuller"]


_DELAI_MS = 450
"""Temps de survol avant apparition [ms]."""

_DECALAGE = (14, 22)
"""Décalage de la bulle par rapport au pointeur [px]."""

_FOND = "#fbfbe8"
_BORDURE = "#b8b6a8"
_ENCRE = "#20201e"


class Infobulle:
    """Un texte qui apparaît au survol d'un ou plusieurs widgets.

    Les widgets partagent une même bulle : l'étiquette d'un champ et le champ
    lui-même décrivent la même chose, et les survoler l'un après l'autre ne
    doit pas faire disparaître puis réapparaître le texte.
    """

    def __init__(
        self,
        *widgets: tk.Misc,
        texte: str,
        delai_ms: int = _DELAI_MS,
        largeur: int = 360,
    ) -> None:
        if not widgets:
            raise ValueError("Une infobulle doit porter sur au moins un widget.")
        self.widgets = widgets
        self.texte = texte
        self.delai_ms = delai_ms
        self.largeur = largeur
        self._fenetre: tk.Toplevel | None = None
        self._tache: str | None = None
        self._pointeur = (0, 0)

        for widget in widgets:
            widget.bind("<Enter>", self._sur_entree, add="+")
            widget.bind("<Motion>", self._suivre, add="+")
            widget.bind("<Leave>", self._sur_sortie, add="+")
            widget.bind("<ButtonPress>", self._sur_sortie, add="+")
            widget.bind("<FocusIn>", self._sur_entree, add="+")
            widget.bind("<FocusOut>", self._sur_sortie, add="+")

    # -- réactions --------------------------------------------------------

    def _suivre(self, evenement) -> None:
        self._pointeur = (evenement.x_root, evenement.y_root)

    def _sur_entree(self, evenement=None) -> None:
        if evenement is not None and hasattr(evenement, "x_root"):
            self._pointeur = (evenement.x_root, evenement.y_root)
        self._annuler()
        self._tache = self.widgets[0].after(self.delai_ms, self.montrer)

    def _sur_sortie(self, _evenement=None) -> None:
        self._annuler()
        self.cacher()

    def _annuler(self) -> None:
        if self._tache is None:
            return
        try:
            self.widgets[0].after_cancel(self._tache)
        except tk.TclError:  # pragma: no cover - fenêtre déjà détruite
            pass
        self._tache = None

    # -- affichage ---------------------------------------------------------

    @property
    def visible(self) -> bool:
        return self._fenetre is not None

    def montrer(self) -> None:
        """Affiche la bulle. Publique, pour que les tests puissent la lire."""
        self._tache = None
        if self._fenetre is not None:
            return
        ancre = self.widgets[0]
        try:
            fenetre = tk.Toplevel(ancre)
        except tk.TclError:  # pragma: no cover - pas de serveur graphique
            return
        fenetre.wm_overrideredirect(True)
        fenetre.configure(background=_BORDURE)
        etiquette = tk.Label(
            fenetre, text=self.texte, justify="left", background=_FOND,
            foreground=_ENCRE, wraplength=self.largeur, padx=8, pady=6,
            font=("TkTooltipFont",),
        )
        etiquette.pack(padx=1, pady=1)
        self._fenetre = fenetre
        self._placer(fenetre)

    def _placer(self, fenetre: tk.Toplevel) -> None:
        """Sous le pointeur, mais jamais hors de l'écran."""
        fenetre.update_idletasks()
        x = self._pointeur[0] + _DECALAGE[0]
        y = self._pointeur[1] + _DECALAGE[1]
        largeur, hauteur = fenetre.winfo_width(), fenetre.winfo_height()
        x = min(x, fenetre.winfo_screenwidth() - largeur - 8)
        y = min(y, fenetre.winfo_screenheight() - hauteur - 8)
        fenetre.wm_geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def cacher(self) -> None:
        if self._fenetre is None:
            return
        try:
            self._fenetre.destroy()
        except tk.TclError:  # pragma: no cover - fenêtre déjà détruite
            pass
        self._fenetre = None


def infobuller(*widgets: tk.Misc, texte: str, largeur: int = 360) -> Infobulle:
    """Attache une infobulle à des widgets, et la renvoie.

    Le retour sert à deux choses : garder une référence — sans quoi rien ne
    retient l'objet — et permettre à un test de lire ce que l'écran dirait.
    """
    return Infobulle(*widgets, texte=texte, largeur=largeur)


def marquer_aide(etiquette: ttk.Label) -> None:
    """Signale visuellement qu'une étiquette porte une aide.

    Une infobulle qu'on ne soupçonne pas n'est jamais lue. Le curseur change
    au survol, ce qui est la convention la plus discrète pour le dire.
    """
    try:
        etiquette.configure(cursor="question_arrow")
    except tk.TclError:  # pragma: no cover - curseur absent de la plateforme
        pass
