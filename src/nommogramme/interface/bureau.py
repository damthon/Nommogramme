"""Interface de bureau, en Tkinter.

C'est la version destinée à être distribuée sous forme d'exécutable : un
fichier à télécharger, un double-clic, l'écran s'ouvre. Ni Python à installer,
ni ligne de commande, ni navigateur.

Pourquoi Tkinter plutôt que l'interface Streamlit
-------------------------------------------------

Streamlit est un serveur web. L'empaqueter donnerait un exécutable d'environ
250 Mo — pandas et pyarrow pèsent à eux seuls 230 Mo et ne servent à rien
ici — qui ouvre un navigateur sur un port local, ce qu'un pare-feu
d'entreprise remarque. Tkinter est dans la bibliothèque standard : rien à
installer, démarrage immédiat, pas de serveur, et l'exécutable tient en
43 Mo, matplotlib compris.

L'interface Streamlit reste en place et reste la plus agréable pour un poste
de travail où Python est déjà installé. Les deux partagent ``saisie.py``.

Aucun calcul ici
----------------

Même contrainte que pour les deux autres surfaces : ce module remplit une
``Saisie``, appelle ``executer()``, affiche ce qui revient. C'est
``saisie.py`` qui traduit, et la bibliothèque qui calcule.

Une note sur le rythme d'affichage
----------------------------------

``verifier()`` prend une dizaine de millisecondes, les deux figures un peu
plus d'une seconde. Les chiffres sont donc recalculés à chaque frappe, et les
figures seulement lorsqu'elles sont visibles, après une pause de saisie. Sans
cette distinction, chaque caractère tapé gèlerait la fenêtre.

Lancement :

    nommo bureau
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from nommogramme.interface.infobulle import Infobulle, infobuller, marquer_aide
from nommogramme.interface.saisie import (
    AIDES,
    BOULON,
    CAISSON_SOUDE,
    CATALOGUE,
    CONTEXTES,
    DUREES,
    EXPOSITIONS,
    H_SOUDE,
    PERSONNALISEE,
    SANS_PROTECTION,
    TYPES_SECTION,
    Saisie,
    executer,
    noms_par_famille,
    nuance_par_defaut,
    nuances_pour,
    produits,
)
from nommogramme.nomogramme.verification import ResultatVerification
from nommogramme.references import EC3_RESISTANCES, EC3_THETA_CR
from nommogramme.thermique.courbes import COURBES
from nommogramme.unites import en_minutes

__all__ = ["Application", "lancer"]


_TITRE = "Nommogramme — résistance au feu des profilés métalliques"

_DELAI_FIGURES_MS = 400
"""Pause de saisie avant de redessiner les figures [ms]."""

_FORMATS_FIGURE = {"nomogramme": (11.0, (5.4, 7.6)), "echauffement": (8.2, (4.6, 6.4))}
"""Largeur fixe et bornes de hauteur des figures affichées [po]."""

_DPI_MINIMAL = 52.0
"""En deçà, la figure cesse de rétrécir : elle ne serait plus lisible."""

# Palette « Minimalism & Swiss » (UI/UX Pro Max) : fond clair, bleu marine,
# vert et rouge réservés au verdict. Chaque texte tient 4,5:1 sur son fond.
_FOND = "#F8FAFC"
_CARTE = "#FFFFFF"
_TEXTE = "#0F172A"
_GRIS = "#475569"
_BORDURE = "#CBD5E1"
_PRIMAIRE = "#1E3A5F"
_PRIMAIRE_ACTIF = "#16304F"
_VERT = "#065F46"
_FOND_VERT = "#ECFDF5"
_ROUGE = "#B91C1C"
_FOND_ROUGE = "#FEF2F2"
_ORANGE = "#9A3412"
_FOND_ORANGE = "#FFF7ED"

_AVERTISSEMENT_COURT = (
    "Outil en développement — le déversement et l'interaction N + M ne sont pas "
    "validés. Ne constitue pas une justification de projet."
)

_AVERTISSEMENT = (
    "Outil en développement.\n\n"
    "La compression, protégée et nue, et la flexion simple sont recoupées avec "
    "la documentation SZS steeltec 02:2015 — table des températures critiques, "
    "huit exemples chiffrés — et le catalogue de profilés avec les Tables de "
    "construction SZS C5/05.\n\n"
    "Le déversement et l'interaction N + M n'ont été comparés à aucun calcul de "
    "référence externe. Cet outil ne constitue pas une justification de projet.\n\n"
    "Les propriétés des produits de protection sont des valeurs génériques de la "
    "littérature, à remplacer par celles de l'agrément technique du produit "
    "retenu (ETE, reconnaissance AEAI).\n\n"
    "Le détail de ce qui est validé, et de ce qui ne l'est pas, est dans "
    "docs/validation.md."
)


def _echelle(widget: tk.Misc) -> float:
    """Rapport entre la densité de l'écran et les 96 dpi d'un écran standard.

    Les tailles fixes en pixels (largeur du panneau, retours à la ligne) sont
    multipliées par ce facteur : sur un écran à 150 %, les polices grossissent
    d'elles-mêmes, et des largeurs restées à leur valeur nominale couperaient
    les libellés.
    """
    return max(widget.winfo_fpixels("1i") / 96.0, 1.0)


def _police(widget: tk.Misc, taille: int, gras: bool = False) -> tuple:
    """La police de l'interface, à une autre taille.

    Écrire ``("TkDefaultFont", 11)`` ne fait pas ce qu'on croit : Tk y lit un
    nom de famille inconnu et retombe sur une police quelconque, à chasse fixe
    sous Linux. On reprend donc la famille réelle de la police par défaut.
    """
    from tkinter import font

    famille = font.nametofont("TkDefaultFont", widget).actual("family")
    return (famille, taille, "bold") if gras else (famille, taille)


def _appliquer_theme(racine: tk.Misc) -> None:
    """Thème clair et sobre, posé sur « clam », le seul thème ttk recoloriable.

    Les thèmes natifs de Windows (« vista ») ignorent les couleurs de fond et
    de bordure : impossible d'y signaler un champ en erreur.
    """
    from tkinter import font

    style = ttk.Style(racine)
    style.theme_use("clam")
    if racine.tk.call("tk", "windowingsystem") == "win32":
        for nom in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont",
                    "TkCaptionFont", "TkTooltipFont"):
            font.nametofont(nom, racine).configure(family="Segoe UI", size=10)
    racine.configure(background=_FOND)

    style.configure(".", background=_FOND, foreground=_TEXTE, bordercolor=_BORDURE,
                    lightcolor=_FOND, darkcolor=_FOND, troughcolor=_FOND)
    style.configure("TLabelframe", background=_FOND, bordercolor=_BORDURE)
    style.configure("TLabelframe.Label", background=_FOND, foreground=_PRIMAIRE,
                    font=_police(racine, 10, gras=True))
    style.configure("TEntry", fieldbackground=_CARTE, padding=(4, 2))
    style.map("TEntry",
              bordercolor=[("invalid", _ROUGE), ("focus", _PRIMAIRE)],
              lightcolor=[("invalid", _ROUGE), ("focus", _PRIMAIRE)],
              fieldbackground=[("invalid", _FOND_ROUGE), ("disabled", "#E2E8F0")],
              foreground=[("disabled", _GRIS)])
    style.configure("TCombobox", fieldbackground=_CARTE, padding=(4, 2),
                    arrowcolor=_PRIMAIRE)
    style.map("TCombobox",
              fieldbackground=[("disabled", "#E2E8F0"), ("readonly", _CARTE)],
              selectbackground=[("readonly", _CARTE)],
              selectforeground=[("readonly", _TEXTE)],
              foreground=[("disabled", _GRIS)],
              bordercolor=[("focus", _PRIMAIRE)])
    style.configure("TButton", padding=(12, 5), background=_CARTE)
    style.map("TButton", background=[("active", "#EEF2F6")],
              bordercolor=[("focus", _PRIMAIRE)])
    style.configure("Primaire.TButton", background=_PRIMAIRE, foreground=_CARTE,
                    font=_police(racine, 10, gras=True))
    style.map("Primaire.TButton",
              background=[("active", _PRIMAIRE_ACTIF), ("pressed", _PRIMAIRE_ACTIF)],
              foreground=[("active", _CARTE)])
    style.configure("Lien.TButton", padding=(0, 2), background=_FOND, borderwidth=0,
                    foreground=_PRIMAIRE)
    style.map("Lien.TButton", background=[("active", _FOND)])
    # Liens d'action (ouvrir un fichier) : soulignés, pour se lire comme tels.
    souligne = _police(racine, 10) + ("underline",)
    style.configure("Action.TButton", padding=(0, 2), background=_FOND, borderwidth=0,
                    foreground="#1D4ED8", font=souligne)
    style.map("Action.TButton", background=[("active", _FOND)],
              foreground=[("active", _PRIMAIRE)])
    style.configure("TCheckbutton", background=_FOND)
    style.map("TCheckbutton", background=[("active", _FOND)])
    style.configure("TNotebook", background=_FOND, bordercolor=_BORDURE)
    style.configure("TNotebook.Tab", padding=(14, 5), background=_FOND,
                    foreground=_GRIS)
    style.map("TNotebook.Tab", background=[("selected", _CARTE)],
              foreground=[("selected", _PRIMAIRE)])
    # Le fond des figures de ``trace`` (partagé avec la note PDF), pour que le
    # graphique ne se détache pas en rectangle dans son onglet. Importé au
    # besoin : ``trace`` ne charge pas matplotlib à l'import.
    from nommogramme.nomogramme.trace import CLAIR

    style.configure("Figure.TLabel", background=CLAIR.fond)
    style.configure("Figure.TFrame", background=CLAIR.fond)

    # Les indicateurs et les flèches de « clam » sont en pixels fixes : sur un
    # écran à 150 % ils restent minuscules à côté du texte.
    e = _echelle(racine)
    style.configure("TCheckbutton", indicatorsize=int(13 * e))
    style.configure("TCombobox", arrowsize=int(13 * e))
    style.configure("TScrollbar", arrowsize=int(13 * e))


def _net_sur_ecran_haute_densite() -> None:
    """Déclare à Windows que la fenêtre gère elle-même la mise à l'échelle.

    Sans cette déclaration, sur un écran réglé à 125 % ou 150 %, Windows dessine
    la fenêtre à 100 % puis l'agrandit comme une image : textes et figures
    sortent flous. À appeler avant de créer la fenêtre.
    """
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):  # autre système, ou Windows trop ancien
        pass


def _famille_de(nom_profil: str) -> str:
    """La famille à laquelle appartient un profilé, par son nom."""
    for famille, noms in noms_par_famille().items():
        if nom_profil in noms:
            return famille
    return next(iter(noms_par_famille()))


class Application(ttk.Frame):
    """La fenêtre principale.

    Séparée de ``lancer()`` pour rester instanciable dans un test : on peut
    la construire sur une racine Tk quelconque, pousser des valeurs dans les
    champs et lire ce qu'elle affiche, sans jamais entrer dans la boucle
    d'événements.
    """

    def __init__(self, maitre: tk.Misc) -> None:
        super().__init__(maitre, padding=10)
        self.pack(fill="both", expand=True)
        self._x = _echelle(maitre)
        self.champs: dict[str, ttk.Entry] = {}
        """Les champs numériques, par nom de paramètre."""
        self._noms_champs: dict[str, str] = {}
        self.illisibles: list[str] = []
        """Les champs dont la valeur n'a pas pu être lue au dernier calcul."""
        self.hors_domaine: list[str] = []
        """Les champs lisibles mais refusés par le calcul (diamètre nul…)."""

        self.resultat: ResultatVerification | None = None
        self.erreur: str | None = None
        self._tache_figures: str | None = None
        self._figures_a_jour = False
        self._silence = False
        self._figures: dict[str, object] = {}
        self._images: dict[str, object] = {}
        self._etiquettes: dict[str, ttk.Label] = {}
        self._rendu: dict[str, tuple[object, float]] = {}
        """Ce qui est réellement affiché par onglet : (figure, densité)."""
        self.infobulles: dict[str, Infobulle] = {}
        """Les aides au survol, par nom de paramètre — lisibles en test."""

        self._construire_variables()
        self._construire_disposition()
        # Après la disposition seulement : masquer l'onglet de coupe suppose
        # que le carnet d'onglets existe, et il est construit dans la colonne
        # de droite, après les paramètres.
        self._mettre_a_jour_section()
        self.rafraichir()

    # -- état ------------------------------------------------------------

    def _construire_variables(self) -> None:
        defaut = Saisie()
        self.var: dict[str, tk.Variable] = {
            "type_section": tk.StringVar(value=defaut.type_section),
            "famille": tk.StringVar(value=_famille_de(defaut.profil)),
            "profil": tk.StringVar(value=defaut.profil),
            "nuance": tk.StringVar(value=defaut.nuance),
            "h_soudee": tk.DoubleVar(value=defaut.h_soudee),
            "b_soudee": tk.DoubleVar(value=defaut.b_soudee),
            "tf_soudee": tk.DoubleVar(value=defaut.tf_soudee),
            "tw_soudee": tk.DoubleVar(value=defaut.tw_soudee),
            "b_inf_soudee": tk.DoubleVar(value=defaut.b_inf_soudee),
            "tf_inf_soudee": tk.DoubleVar(value=defaut.tf_inf_soudee),
            "d_boulon": tk.DoubleVar(value=defaut.d_boulon),
            "N": tk.DoubleVar(value=defaut.N),
            "My": tk.DoubleVar(value=defaut.My),
            "Mz": tk.DoubleVar(value=defaut.Mz),
            "L": tk.DoubleVar(value=defaut.L),
            "l_fi": tk.DoubleVar(value=defaut.l_fi),
            "maintien": tk.BooleanVar(value=defaut.maintien),
            "beta_M": tk.DoubleVar(value=defaut.beta_M),
            "exposition": tk.StringVar(value=defaut.exposition),
            "feu": tk.StringVar(value=COURBES[defaut.feu].nom),
            "duree": tk.IntVar(value=defaut.duree),
            "protection": tk.StringVar(value=SANS_PROTECTION),
            "epaisseur": tk.DoubleVar(value=10.0),
            "nom_perso": tk.StringVar(value=defaut.nom_perso),
            "lambda_p_perso": tk.DoubleVar(value=defaut.lambda_p_perso),
            "rho_p_perso": tk.DoubleVar(value=defaut.rho_p_perso),
            "c_p_perso": tk.DoubleVar(value=defaut.c_p_perso),
            "humidite_perso": tk.DoubleVar(value=defaut.humidite_perso),
            "contexte": tk.StringVar(value=defaut.contexte),
            "kappa_2": tk.DoubleVar(value=defaut.kappa_2),
            "C1": tk.DoubleVar(value=defaut.C1),
        }
        for nom, variable in self.var.items():
            variable.trace_add("write", lambda *_, n=nom: self._sur_changement(n))

    def saisie(self) -> Saisie:
        """L'état courant des champs, sous forme de ``Saisie``.

        Un champ numérique vide ou à moitié tapé — « 8 », « -», « 1,2e » —
        fait lever ``TclError`` à la lecture. On retombe alors sur la valeur
        par défaut du champ plutôt que d'interrompre : l'utilisateur est en
        train de taper, ce n'est pas une erreur. Le champ est noté dans
        ``illisibles`` : l'écran le signale, pour qu'on ne lise pas un résultat
        calculé sur une autre valeur que celle qu'on croit avoir saisie.
        """
        defaut = Saisie()
        self.illisibles = []

        def lire(nom: str):
            try:
                return self.var[nom].get()
            except tk.TclError:
                self.illisibles.append(nom)
                return getattr(defaut, nom, 0.0)

        produit = self._cle_produit(self.var["protection"].get())
        libelle_feu = self.var["feu"].get()
        cle_feu = next(
            (cle for cle, courbe in COURBES.items() if courbe.nom == libelle_feu),
            defaut.feu,
        )
        return Saisie(
            profil=self.var["profil"].get(),
            nuance=self.var["nuance"].get(),
            type_section=self.var["type_section"].get(),
            h_soudee=lire("h_soudee"),
            b_soudee=lire("b_soudee"),
            tf_soudee=lire("tf_soudee"),
            tw_soudee=lire("tw_soudee"),
            b_inf_soudee=lire("b_inf_soudee"),
            tf_inf_soudee=lire("tf_inf_soudee"),
            d_boulon=lire("d_boulon"),
            N=lire("N"),
            My=lire("My"),
            Mz=lire("Mz"),
            L=lire("L"),
            l_fi=lire("l_fi"),
            maintien=bool(self.var["maintien"].get()),
            beta_M=lire("beta_M"),
            exposition=self.var["exposition"].get(),
            feu=cle_feu,
            duree=lire("duree"),
            protection=produit,
            epaisseur=lire("epaisseur") if produit != SANS_PROTECTION else None,
            nom_perso=self.var["nom_perso"].get(),
            lambda_p_perso=lire("lambda_p_perso"),
            rho_p_perso=lire("rho_p_perso"),
            c_p_perso=lire("c_p_perso"),
            humidite_perso=lire("humidite_perso"),
            contexte=self.var["contexte"].get(),
            kappa_2=lire("kappa_2"),
            C1=lire("C1"),
        )

    @staticmethod
    def _libelle_produit(cle: str) -> str:
        if cle in (SANS_PROTECTION, PERSONNALISEE):
            return cle
        return produits()[cle].get("libelle", cle)

    @staticmethod
    def _cle_produit(libelle: str) -> str:
        if libelle in (SANS_PROTECTION, PERSONNALISEE):
            return libelle
        for cle, fiche in produits().items():
            if fiche.get("libelle", cle) == libelle:
                return cle
        return SANS_PROTECTION

    # -- disposition -----------------------------------------------------

    def _construire_disposition(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        gauche = self._panneau_defilant(self, largeur=int(340 * self._x))
        gauche.master.master.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        self._construire_parametres(gauche)

        droite = ttk.Frame(self)
        droite.grid(row=0, column=1, sticky="nsew")
        droite.columnconfigure(0, weight=1)
        droite.rowconfigure(5, weight=1)
        self._construire_resultats(droite)
        droite.bind("<Configure>", self._ajuster_retours, add="+")

        pied = ttk.Frame(self)
        pied.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        pied.columnconfigure(0, weight=1)
        ttk.Label(
            pied, text=_AVERTISSEMENT_COURT, foreground=_GRIS,
            wraplength=int(900 * self._x), justify="left",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(pied, text="À propos…", command=self.a_propos).grid(
            row=0, column=1, sticky="e"
        )

    def _panneau_defilant(self, parent: tk.Misc, largeur: int = 300) -> ttk.Frame:
        """Un cadre à barre de défilement, et renvoie son intérieur.

        La colonne de paramètres fait dans les 800 pixels de haut. Sur un
        portable en 1366 × 768 elle ne tient pas, et sans défilement les
        derniers champs — κ₂, C₁ — deviennent purement inaccessibles : ni
        visibles, ni atteignables au clavier. C'est le genre de défaut qu'on
        ne voit qu'en regardant une capture de la fenêtre réelle.
        """
        conteneur = ttk.Frame(parent)
        conteneur.rowconfigure(0, weight=1)

        canevas = tk.Canvas(
            conteneur, borderwidth=0, highlightthickness=0, width=largeur,
            background=_FOND,
        )
        barre = ttk.Scrollbar(conteneur, orient="vertical", command=canevas.yview)
        interieur = ttk.Frame(canevas)

        canevas.configure(yscrollcommand=barre.set)
        canevas.grid(row=0, column=0, sticky="ns")
        barre.grid(row=0, column=1, sticky="ns")
        fenetre = canevas.create_window((0, 0), window=interieur, anchor="nw")

        def _sur_contenu(_=None) -> None:
            canevas.configure(scrollregion=canevas.bbox("all"))
            canevas.itemconfigure(fenetre, width=canevas.winfo_width())

        interieur.bind("<Configure>", _sur_contenu)
        canevas.bind("<Configure>", _sur_contenu)

        # La molette n'agit que quand le pointeur survole le panneau : liée à
        # la fenêtre entière, elle ferait aussi défiler pendant qu'on lit une
        # figure. Les boutons 4 et 5 sont la convention X11, <MouseWheel>
        # celle de Windows et de macOS.
        def _molette(evenement) -> None:
            pas = 1 if getattr(evenement, "num", None) == 5 else -1
            if getattr(evenement, "delta", 0):
                pas = -1 if evenement.delta > 0 else 1
            canevas.yview_scroll(pas, "units")

        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            canevas.bind_all(sequence, lambda e: _molette(e)
                             if self._survole(canevas, e) else None)

        return interieur

    @staticmethod
    def _survole(widget: tk.Misc, evenement) -> bool:
        """Le pointeur est-il au-dessus de ce widget ?"""
        try:
            sous_pointeur = widget.winfo_containing(evenement.x_root, evenement.y_root)
        except (tk.TclError, KeyError):
            return False
        while sous_pointeur is not None:
            if sous_pointeur is widget:
                return True
            sous_pointeur = getattr(sous_pointeur, "master", None)
        return False

    def _bloc(self, parent: tk.Misc, titre: str) -> ttk.Frame:
        cadre = ttk.LabelFrame(parent, text=titre, padding=(8, 6))
        cadre.pack(fill="x", pady=(0, 8), padx=(0, 4))
        cadre.columnconfigure(1, weight=1)
        return cadre

    def _champ(
        self,
        parent: ttk.Frame,
        ligne: int,
        etiquette: str,
        widget: tk.Widget,
        aide: str | None = None,
        cle: str | None = None,
    ) -> ttk.Label:
        """Une ligne étiquette + widget, avec son aide au survol.

        L'infobulle porte sur les deux : celui qui hésite sur un paramètre
        survole aussi bien son nom que son champ. Elle est conservée dans
        ``self.infobulles`` — sans référence, rien ne la retiendrait, et un
        test ne pourrait pas lire ce que l'écran dirait.
        """
        for nom, champ in self.champs.items():
            if champ is widget:  # nom lisible, pour signaler un champ illisible
                self._noms_champs[nom] = etiquette.split("[")[0].strip()
        libelle = ttk.Label(parent, text=etiquette)
        libelle.grid(row=ligne, column=0, sticky="w", pady=2)
        widget.grid(row=ligne, column=1, sticky="ew", padx=(8, 0), pady=2)
        if aide:
            marquer_aide(libelle)
            self.infobulles[cle or etiquette] = infobuller(
                libelle, widget, texte=aide
            )
        return libelle

    def _nombre(self, parent: ttk.Frame, cle: str, largeur: int = 10) -> ttk.Entry:
        champ = ttk.Entry(parent, textvariable=self.var[cle], width=largeur)
        self.champs[cle] = champ
        return champ

    @property
    def _l_texte(self) -> int:
        """Largeur de retour à la ligne des notes du panneau de gauche [px]."""
        return int(290 * self._x)

    def _liste(
        self, parent: ttk.Frame, cle: str, valeurs, largeur: int = 22
    ) -> ttk.Combobox:
        return ttk.Combobox(
            parent, textvariable=self.var[cle], values=list(valeurs),
            state="readonly", width=largeur,
        )

    def _construire_parametres(self, parent: ttk.Frame) -> None:
        element = self._bloc(parent, "Élément")
        self._champ(
            element, 0, "Type de section",
            self._liste(element, "type_section", TYPES_SECTION),
            aide=AIDES["type_section"], cle="type_section",
        )
        familles = list(noms_par_famille())
        self.liste_familles = self._liste(element, "famille", familles)
        self.etiquette_famille = self._champ(element, 1, "Famille", self.liste_familles)
        self.liste_profils = self._liste(
            element, "profil", noms_par_famille()[self.var["famille"].get()]
        )
        self.etiquette_profil = self._champ(element, 2, "Profilé", self.liste_profils)
        self.liste_nuances = self._liste(
            element, "nuance", nuances_pour(self.var["type_section"].get())
        )
        self._champ(
            element, 3, "Nuance", self.liste_nuances,
            aide=AIDES["nuance"], cle="nuance",
        )

        self.bloc_soudee = self._bloc(parent, "Section soudée  ·  cotes en mm")
        self._construire_section_soudee(self.bloc_soudee)

        self.bloc_boulon = self._bloc(parent, "Boulon  ·  tige ronde")
        self._champ(
            self.bloc_boulon, 0, "Diamètre d  [mm]", self._nombre(self.bloc_boulon, "d_boulon"),
            aide=AIDES["d_boulon"], cle="d_boulon",
        )
        self.note_boulon = ttk.Label(
            self.bloc_boulon, text="", foreground=_GRIS, wraplength=self._l_texte,
            justify="left",
        )
        self.note_boulon.grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.bloc_efforts = self._bloc(parent, "Sollicitations en incendie")
        efforts = self.bloc_efforts
        self._champ(efforts, 0, "N_fi,Ed  [kN]", self._nombre(efforts, "N"))
        self._champ(efforts, 1, "M_y,fi,Ed  [kN·m]", self._nombre(efforts, "My"))
        self._champ(efforts, 2, "M_z,fi,Ed  [kN·m]", self._nombre(efforts, "Mz"))
        ttk.Label(
            efforts, text="Combinaison accidentelle. N négatif en compression.",
            foreground=_GRIS, wraplength=self._l_texte,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(3, 0))

        geometrie = self._bloc(parent, "Géométrie")
        self._champ(
            geometrie, 0, "Longueur de l'élément L  [m]", self._nombre(geometrie, "L"),
            aide=AIDES["L"], cle="L",
        )
        self._champ(
            geometrie, 1, "Flambement l_fi  [m]", self._nombre(geometrie, "l_fi"),
            aide=AIDES["l_fi"], cle="l_fi",
        )
        self._champ(
            geometrie, 2, "β_M  [-]", self._nombre(geometrie, "beta_M"),
            aide=AIDES["beta_M"], cle="beta_M",
        )
        maintien = ttk.Checkbutton(
            geometrie, text="Semelle comprimée maintenue",
            variable=self.var["maintien"],
        )
        maintien.grid(row=3, column=0, columnspan=2, sticky="w", pady=(3, 0))
        self.infobulles["maintien"] = infobuller(maintien, texte=AIDES["maintien"])
        ttk.Label(
            geometrie, text="Poteau continu d'un contreventement : "
                            "l_fi = 0,5·L en étage courant, 0,7·L au dernier.",
            foreground=_GRIS, wraplength=self._l_texte,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(3, 0))

        feu = self._bloc(parent, "Exposition au feu")
        self._champ(
            feu, 0, "Configuration", self._liste(feu, "exposition", EXPOSITIONS),
            aide=AIDES["exposition"], cle="exposition",
        )
        self._champ(
            feu, 1, "Courbe de feu",
            self._liste(feu, "feu", [c.nom for c in COURBES.values()]),
            aide=AIDES["feu"], cle="feu",
        )
        self._champ(
            feu, 2, "Durée exigée  [min]",
            self._liste(feu, "duree", DUREES, largeur=8),
        )

        protection = self._bloc(parent, "Protection")
        libelles = [SANS_PROTECTION] + [
            self._libelle_produit(cle) for cle in sorted(produits())
        ] + [PERSONNALISEE]
        self._champ(
            protection, 0, "Produit", self._liste(protection, "protection", libelles),
            aide=AIDES["protection"], cle="protection",
        )
        self.champ_epaisseur = self._nombre(protection, "epaisseur")
        self._champ(
            protection, 1, "Épaisseur d_p  [mm]", self.champ_epaisseur,
            aide=AIDES["epaisseur"], cle="epaisseur",
        )
        self.note_produit = ttk.Label(
            protection, text="", foreground=_GRIS, wraplength=self._l_texte, justify="left"
        )
        self.note_produit.grid(row=2, column=0, columnspan=2, sticky="w", pady=(3, 0))

        # Produit personnalisé : ses propriétés, visibles seulement quand on
        # le choisit — sinon cinq champs sans effet encombreraient le bloc.
        self.lignes_perso: list[tk.Widget] = []
        nom = ttk.Entry(protection, textvariable=self.var["nom_perso"], width=10)
        for ligne, (cle, libelle, widget) in enumerate((
            ("nom_perso", "Nom du produit", nom),
            ("lambda_p_perso", "λ_p  [W/m·K]", None),
            ("rho_p_perso", "ρ_p  [kg/m³]", None),
            ("c_p_perso", "c_p  [J/kg·K]", None),
            ("humidite_perso", "Humidité  [%]", None),
        ), start=3):
            widget = widget or self._nombre(protection, cle)
            etiquette = self._champ(protection, ligne, libelle, widget,
                                    aide=AIDES["perso"], cle=cle)
            self.lignes_perso += [etiquette, widget]

        # Replié par défaut : rarement modifié, et cinq lignes de moins à
        # parcourir. Le bloc garde son titre, que le script du manuel cherche.
        self.bouton_avances = ttk.Button(
            parent, style="Lien.TButton", command=self._basculer_avances
        )
        self.bouton_avances.pack(anchor="w", pady=(0, 4))
        avances = self._bloc(parent, "Paramètres avancés")
        self.bloc_avances = avances
        self._champ(
            avances, 0, "Référentiel", self._liste(avances, "contexte", CONTEXTES),
            aide=AIDES["contexte"], cle="contexte",
        )
        # κ₁ n'est plus saisi : il découle de l'exposition et de la protection.
        self.etiquette_kappa_1 = ttk.Label(avances, text="")
        self._champ(
            avances, 1, "κ₁  [-]", self.etiquette_kappa_1,
            aide=AIDES["kappa_1"], cle="kappa_1",
        )
        self._champ(
            avances, 2, "κ₂  [-]", self._nombre(avances, "kappa_2"),
            aide=AIDES["kappa_2"], cle="kappa_2",
        )
        self._champ(
            avances, 3, "C₁  [-]", self._nombre(avances, "C1"),
            aide=AIDES["C1"], cle="C1",
        )

        self._mettre_a_jour_protection()
        self._avances_ouverts = True
        self._basculer_avances()

    def _basculer_avances(self) -> None:
        """Ouvre ou replie le bloc des paramètres avancés."""
        self._avances_ouverts = not self._avances_ouverts
        if self._avances_ouverts:
            self.bloc_avances.pack(fill="x", pady=(0, 8), padx=(0, 4),
                                   after=self.bouton_avances)
        else:
            self.bloc_avances.pack_forget()
        self._libeller_avances()

    def _libeller_avances(self) -> None:
        """Le titre du bouton, qui signale des réglages modifiés même replié.

        Un référentiel ou un κ₂ changé puis replié ne doit pas disparaître de
        la vue : le résultat en dépend.
        """
        defaut = Saisie()
        modifies = False
        try:
            modifies = (
                self.var["contexte"].get() != defaut.contexte
                or float(self.var["kappa_2"].get()) != defaut.kappa_2
                or float(self.var["C1"].get()) != defaut.C1
            )
        except (tk.TclError, ValueError):
            modifies = True
        fleche = "▾" if self._avances_ouverts else "▸"
        suffixe = "  (modifiés)" if modifies and not self._avances_ouverts else ""
        self.bouton_avances.configure(text=f"{fleche}  Paramètres avancés{suffixe}")

    def _construire_section_soudee(self, cadre: ttk.Frame) -> None:
        """Les dimensions d'une section reconstituée.

        Les mêmes six champs servent aux deux formes, mais ne désignent pas
        la même chose : ``b`` est la largeur du caisson ou celle de la semelle
        supérieure du H. Les étiquettes changent donc avec le type retenu,
        plutôt que de porter un libellé assez vague pour convenir aux deux.
        """
        self.etiquettes_soudee: dict[str, ttk.Label] = {}
        self.lignes_h: list[tk.Widget] = []

        for ligne, (cle, libelle) in enumerate(
            (("h_soudee", "h  [mm]"), ("b_soudee", "b  [mm]"),
             ("tf_soudee", "t_f  [mm]"), ("tw_soudee", "t_w  [mm]"))
        ):
            self.etiquettes_soudee[cle] = self._champ(
                cadre, ligne, libelle, self._nombre(cadre, cle)
            )

        for ligne, (cle, libelle) in enumerate(
            (("b_inf_soudee", "b_inf  [mm]"), ("tf_inf_soudee", "t_f,inf  [mm]")),
            start=4,
        ):
            etiquette = self._champ(cadre, ligne, libelle, self._nombre(cadre, cle))
            self.etiquettes_soudee[cle] = etiquette
            self.lignes_h.append(etiquette)
            self.lignes_h.append(cadre.grid_slaves(row=ligne, column=1)[0])

        self.note_soudee = ttk.Label(
            cadre, text="", foreground=_GRIS, wraplength=self._l_texte, justify="left"
        )
        self.note_soudee.grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _construire_resultats(self, parent: ttk.Frame) -> None:
        # Le verdict d'abord, en gros : c'est la réponse à la question posée.
        # Le symbole double la couleur, qui ne doit pas porter le sens seule.
        cadre_verdict = tk.Frame(parent, padx=14, pady=10)
        cadre_verdict.grid(row=0, column=0, sticky="ew")
        self.banniere = tk.Label(
            cadre_verdict, text="", font=_police(parent, 16, gras=True),
            anchor="w", justify="left",
        )
        self.banniere.pack(anchor="w")
        self.sous_banniere = tk.Label(
            cadre_verdict, text="", font=_police(parent, 10), anchor="w",
            justify="left", wraplength=int(760 * self._x),
        )
        self.sous_banniere.pack(anchor="w")
        self._fonds_verdict = (cadre_verdict, self.banniere, self.sous_banniere)

        # Quatre tuiles : grande valeur, petit libellé.
        indicateurs = ttk.Frame(parent, padding=(0, 10, 0, 6))
        indicateurs.grid(row=1, column=0, sticky="ew")
        self.indicateur: dict[str, tk.Label] = {}
        for colonne, (cle, titre) in enumerate(
            (("mu_0", "Degré d'utilisation μ₀"), ("theta_cr", "θ_cr retenue"),
             ("theta_a", "θ_a à l'échéance"), ("t_fi_d", "Résistance t_fi,d"))
        ):
            indicateurs.columnconfigure(colonne, weight=1, uniform="tuiles")
            case = tk.Frame(
                indicateurs, background=_CARTE, padx=12, pady=8,
                highlightthickness=1, highlightbackground=_BORDURE,
            )
            case.grid(row=0, column=colonne, sticky="ew",
                      padx=(0 if colonne == 0 else 8, 0))
            tk.Label(case, text=titre, background=_CARTE, foreground=_GRIS,
                     font=_police(parent, 9)).pack(anchor="w")
            valeur = tk.Label(case, text="—", background=_CARTE, foreground=_TEXTE,
                              font=_police(parent, 18, gras=True))
            valeur.pack(anchor="w")
            self.indicateur[cle] = valeur

        # Les alertes restent toujours visibles ; le détail normatif se replie.
        self.alertes = ttk.Label(parent, text="", foreground=_ORANGE,
                                 wraplength=int(760 * self._x), justify="left")
        self.alertes.grid(row=2, column=0, sticky="ew")
        self.bouton_details = ttk.Button(
            parent, style="Lien.TButton", command=self._basculer_details,
        )
        self.bouton_details.grid(row=3, column=0, sticky="w")
        self.details = ttk.Label(parent, text="", foreground=_GRIS,
                                 wraplength=int(760 * self._x), justify="left")
        self.details.grid(row=4, column=0, sticky="ew", pady=(0, 6))
        self._details_ouverts = True
        self._basculer_details()

        self.onglets = ttk.Notebook(parent)
        self.onglets.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
        self.onglets.bind("<<NotebookTabChanged>>", lambda _: self._planifier_figures())
        self.cadre_figure: dict[str, ttk.Frame] = {}
        for cle, titre in (
            ("nomogramme", "Nomogramme"),
            ("echauffement", "Échauffement"),
            ("section", "Coupe de la section"),
        ):
            cadre = ttk.Frame(self.onglets, style="Figure.TFrame")
            self.onglets.add(cadre, text=titre)
            self.cadre_figure[cle] = cadre

        # Discret, en haut à droite des onglets : la figure suit la saisie
        # avec un temps de retard, et sans ce signe elle paraît figée.
        self.etat_figures = ttk.Label(parent, text="Mise à jour des figures…",
                                      foreground=_GRIS)

        boutons = ttk.Frame(parent, padding=(0, 10, 0, 0))
        boutons.grid(row=6, column=0, sticky="ew")
        self.bouton_note = ttk.Button(
            boutons, text="Enregistrer la note de calcul…", style="Primaire.TButton",
            command=self.enregistrer_note,
        )
        self.bouton_note.pack(side="left")
        self.bouton_figures = ttk.Button(
            boutons, text="Enregistrer les figures…", command=self.enregistrer_figures
        )
        self.bouton_figures.pack(side="left", padx=8)

        # Le compte rendu d'un enregistrement réussi : un message qui s'efface
        # seul, pas une fenêtre modale qu'il faudrait fermer.
        self.statut = ttk.Label(boutons, text="", foreground=_VERT)
        self.lien_ouvrir = ttk.Button(boutons, text="Ouvrir", style="Action.TButton",
                                      cursor="hand2")
        self.lien_dossier = ttk.Button(boutons, text="Ouvrir le dossier",
                                       style="Action.TButton", cursor="hand2")
        self._tache_statut: str | None = None

    def _ajuster_retours(self, evenement) -> None:
        """Les textes de la colonne de droite reviennent à la ligne à sa largeur.

        Une largeur fixe coupait les alertes dans une fenêtre étroite, et les
        laissait sur une seule ligne trop longue dans une fenêtre large.
        """
        largeur = max(evenement.width - int(30 * self._x), 200)
        for etiquette in (self.sous_banniere, self.alertes, self.details):
            etiquette.configure(wraplength=largeur)

    def _basculer_details(self) -> None:
        """Ouvre ou referme le détail normatif sous les tuiles."""
        self._details_ouverts = not self._details_ouverts
        if self._details_ouverts:
            self.details.grid()
            self.bouton_details.configure(text="▾  Masquer le détail du calcul")
        else:
            self.details.grid_remove()
            self.bouton_details.configure(text="▸  Détail du calcul")

    # -- réactions -------------------------------------------------------

    def _sur_changement(self, nom: str) -> None:
        if self._silence:
            return
        if nom == "famille":
            self._sur_changement_famille()
            return
        if nom == "protection":
            self._mettre_a_jour_protection()
        if nom == "type_section":
            self._mettre_a_jour_section()
        self.rafraichir()

    def _mettre_a_jour_section(self) -> None:
        """Montre les champs de la forme retenue, et cache les autres.

        Trois jeux de champs se disputent la même place : le choix d'un
        profilé du catalogue, les quatre cotes d'un caisson, les six d'un H.
        Les laisser tous visibles inviterait à remplir des cases sans effet,
        et c'est le genre de faux paramètre dont on ne se méfie plus.
        """
        type_section = self.var["type_section"].get()
        du_catalogue = type_section == CATALOGUE
        soudee = type_section in (CAISSON_SOUDE, H_SOUDE)

        for bloc, visible in ((self.bloc_soudee, soudee),
                              (self.bloc_boulon, type_section == BOULON)):
            if visible:
                bloc.pack(fill="x", pady=(0, 8), padx=(0, 4), before=self.bloc_efforts)
            else:
                bloc.pack_forget()

        # Classes de boulon pour un boulon, aciers de construction sinon : la
        # nuance courante est remplacée si elle n'appartient plus à la liste.
        nuances = nuances_pour(type_section)
        self.liste_nuances.configure(values=list(nuances))
        if self.var["nuance"].get() not in nuances:
            self._silence = True
            self.var["nuance"].set(nuance_par_defaut(type_section))
            self._silence = False

        etat = "readonly" if du_catalogue else "disabled"
        self.liste_familles.configure(state=etat)
        self.liste_profils.configure(state=etat)

        for widget in self.lignes_h:
            if type_section == H_SOUDE:
                widget.grid()
            else:
                widget.grid_remove()

        if type_section == H_SOUDE:
            libelles = {
                "b_soudee": "b_sup  [mm]", "tf_soudee": "t_f,sup  [mm]",
                "tw_soudee": "t_w — âme  [mm]",
            }
        else:
            libelles = {
                "b_soudee": "b  [mm]", "tf_soudee": "t_f — semelles  [mm]",
                "tw_soudee": "t_w — âmes  [mm]",
            }
        for cle, libelle in libelles.items():
            self.etiquettes_soudee[cle].configure(text=libelle)


    def _sur_changement_famille(self) -> None:
        """Recharge la liste des profilés, et en choisit un valide."""
        noms = noms_par_famille()[self.var["famille"].get()]
        self.liste_profils.configure(values=list(noms))
        if self.var["profil"].get() not in noms:
            self._silence = True
            self.var["profil"].set(noms[len(noms) // 2])
            self._silence = False
        self.rafraichir()

    def _mettre_a_jour_protection(self) -> None:
        """Active le champ d'épaisseur et affiche la fiche du produit."""
        cle = self._cle_produit(self.var["protection"].get())
        for widget in self.lignes_perso:
            if cle == PERSONNALISEE:
                widget.grid()
            else:
                widget.grid_remove()
        if cle == SANS_PROTECTION:
            self.champ_epaisseur.configure(state="disabled")
            self.note_produit.configure(text="")
            return
        if cle == PERSONNALISEE:
            self.champ_epaisseur.configure(state="normal")
            self.note_produit.configure(
                text="Valeurs de la fiche technique ou de l'agrément du produit. "
                     "Produit incombustible, conductivité constante."
            )
            return

        fiche = produits()[cle]
        self.champ_epaisseur.configure(state="normal")
        self._silence = True
        self.var["epaisseur"].set(round(fiche["dp_min"] * 1e3, 1))
        self._silence = False
        self.note_produit.configure(
            text=(
                # Le nom complet : la liste déroulante le tronque.
                f"{fiche.get('libelle', cle)}\n"
                f"λ_p = {fiche['lambda_p']} W/m·K · ρ_p = {fiche['rho_p']:.0f} kg/m³\n"
                f"c_p = {fiche['c_p']:.0f} J/kg·K · pose {fiche['pose']}\n"
                f"épaisseurs usuelles {fiche['dp_min'] * 1e3:.0f} à "
                f"{fiche['dp_max'] * 1e3:.0f} mm"
                + (
                    f"\ncombustible : β_n = {fiche['beta_n_mm_min']} mm/min "
                    "(EN 1995-1-2 tab. 3.1)"
                    if "beta_n_mm_min" in fiche else ""
                )
            )
        )

    def rafraichir(self) -> None:
        """Recalcule les chiffres, et programme le redessin des figures."""
        saisie = self.saisie()
        self.hors_domaine = (
            ["d_boulon"] if saisie.type_section == BOULON and saisie.d_boulon <= 0 else []
        )
        try:
            self.resultat = executer(saisie)
            self.erreur = None
        except Exception as souci:  # une saisie incohérente ne doit pas fermer la fenêtre
            self.resultat = None
            self.erreur = str(souci)

        self._afficher_section(saisie)
        self.etiquette_kappa_1.configure(
            text=f"{saisie.kappa_1:.2f}  (déduit de l'exposition)".replace(".", ",")
        )
        self._afficher()
        if hasattr(self, "bouton_avances"):
            self._libeller_avances()
        self._figures_a_jour = False
        self._planifier_figures()

    def _afficher_section(self, saisie: Saisie) -> None:
        """Le résumé de la section soudée, sous ses champs de saisie.

        Une géométrie impossible — semelles plus épaisses que la hauteur — ne
        doit pas se traduire par un écran muet : le message d'erreur de la
        section vaut mieux que le silence, et il est plus précis que celui de
        la vérification qui échouera ensuite.
        """
        if hasattr(self, "note_boulon") and saisie.type_section == BOULON:
            try:
                p = saisie.profil_retenu()
            except ValueError as souci:
                self.note_boulon.configure(text=f"⚠ {souci}", foreground=_ROUGE)
            else:
                self.note_boulon.configure(
                    text=f"{p.nom} · A = {p.A * 1e6:.0f} mm² · {p.masse:.2f} kg/m\n"
                         "Section lisse : le filetage (A_s) n'est pas pris en compte.",
                    foreground=_GRIS,
                )
        if not hasattr(self, "note_soudee") or not saisie.soudee:
            return
        try:
            section = saisie.section()
        except ValueError as souci:
            self.note_soudee.configure(text=f"⚠ {souci}", foreground=_ROUGE)
            return
        profil = section.profil()
        lignes = [
            section.profil().nom,
            f"A = {profil.A * 1e4:.1f} cm² · {profil.masse:.0f} kg/m · "
            f"I_y = {profil.Iy * 1e8:.0f} cm⁴ · W_pl,y = {profil.Wply * 1e6:.0f} cm³",
        ]
        lignes.extend(f"⚠ {message}" for message in section.controles())
        self.note_soudee.configure(text="\n".join(lignes), foreground=_GRIS)

    def _colorer_verdict(self, fond: str, encre: str) -> None:
        for widget in self._fonds_verdict:
            widget.configure(background=fond)
        self.banniere.configure(foreground=encre)
        self.sous_banniere.configure(foreground=_TEXTE)

    def _signaler_illisibles(self) -> str:
        """Encadre en rouge les champs fautifs, et renvoie la phrase des illisibles.

        Fautifs : illisibles, ou lisibles mais hors domaine (un diamètre nul),
        dont le message d'erreur est déjà dans le bandeau.
        """
        fautifs = set(self.illisibles) | set(self.hors_domaine)
        for cle, champ in self.champs.items():
            champ.state(["invalid"] if cle in fautifs else ["!invalid"])
        if not self.illisibles:
            return ""
        noms = ", ".join(self._noms_champs.get(c, c) for c in self.illisibles)
        return f"\nValeur illisible : {noms} — calcul fait avec la valeur par défaut."

    def _afficher(self) -> None:
        illisibles = self._signaler_illisibles()
        if self.erreur is not None or self.resultat is None:
            self.banniere.configure(text="Saisie inexploitable")
            self.sous_banniere.configure(text=f"{self.erreur}{illisibles}")
            self._colorer_verdict(_FOND_ORANGE, _ORANGE)
            for valeur in self.indicateur.values():
                valeur.configure(text="—")
            self.details.configure(text="")
            self.alertes.configure(text="")
            return

        r = self.resultat
        duree = en_minutes(r.duree_requise)
        satisfait = bool(r.verdict)
        self.banniere.configure(
            text=f"{'✓' if satisfait else '✗'}  R{duree:.0f} {r.verdict.value}"
        )
        # La sous-ligne nomme la vraie cause. Hors des deux cas limites,
        # c'est la comparaison θ_a / θ_cr qui fait le verdict.
        if r.mu_0 >= 1.0:
            cause = (f"μ₀ = {r.mu_0:.3f} ≥ 1 : l'élément ne résiste pas, déjà à "
                     "20 °C, aux charges d'incendie.")
        elif r.mu_0 == 0.0:
            cause = "Aucun effort : rien à vérifier."
        else:
            cause = (f"θ_a = {r.theta_a_a_echeance:.0f} °C à l'échéance, "
                     f"θ_cr = {r.theta_cr:.0f} °C · marge {r.marge_temperature:+.0f} °C")
        self.sous_banniere.configure(text=f"{cause}{illisibles}")
        if satisfait:
            self._colorer_verdict(_FOND_VERT, _VERT)
        else:
            self._colorer_verdict(_FOND_ROUGE, _ROUGE)

        self.indicateur["mu_0"].configure(text=f"{r.mu_0:.3f}")
        self.indicateur["theta_cr"].configure(text=f"{r.theta_cr:.0f} °C")
        self.indicateur["theta_a"].configure(text=f"{r.theta_a_a_echeance:.0f} °C")
        self.indicateur["t_fi_d"].configure(
            text=f"{r.t_fi_d_minutes:.0f} min" if r.t_fi_d_minutes is not None
            else "non atteinte"
        )

        nomogramme = (
            f"{r.theta_cr_nomogramme:.0f} °C" if r.theta_cr_nomogramme else "—"
        )
        croisee = f"{r.theta_cr_exact:.0f} °C" if r.theta_cr_exact else "—"
        lignes = [
            f"Nomogramme, {EC3_THETA_CR.courte} : {nomogramme}",
            f"Vérification croisée, {EC3_RESISTANCES.courte} : {croisee}",
            f"Retenue : {r.source_theta_cr}",
            f"Critère gouvernant : {r.gouverne_par} · {r.classification}",
            self._ligne_massivete(r),
        ]
        alertes = []
        if r.ecart_nomogramme is not None and r.ecart_nomogramme > 10.0:
            alertes.append(
                f"⚠ L'{EC3_THETA_CR.courte} donne {r.ecart_nomogramme:.0f} °C de "
                "plus que la vérification complète : l'instabilité gouverne. "
                "C'est la valeur basse qui est retenue."
            )
        alertes.extend(f"⚠ {a}" for a in r.avertissements)
        self.details.configure(text="\n".join(lignes))
        self.alertes.configure(text="\n".join(alertes))
        if alertes:
            self.alertes.grid()
        else:
            self.alertes.grid_remove()

    @staticmethod
    def _ligne_massivete(r: ResultatVerification) -> str:
        """Facteur de massiveté, et k_sh seulement là où il a un sens.

        Le facteur d'ombre ne s'applique qu'à l'acier **nu** ; pour un élément
        protégé, ``verifier()`` renvoie k_sh = 1. L'afficher tel quel
        laisserait croire qu'il a été omis à tort. La notation change aussi :
        la norme écrit A_p/V dès qu'il y a un revêtement.
        """
        if r.protection is None:
            return f"A_m/V = {r.Am_sur_V:.1f} m⁻¹ · k_sh = {r.k_sh:.3f}"
        ligne = (
            f"A_p/V = {r.Am_sur_V:.1f} m⁻¹ · {r.protection.libelle or r.protection.nom}, "
            f"d_p = {r.protection.d_p * 1e3:.1f} mm"
        )
        t_ch = r.thermique.t_carbonisation
        if t_ch is not None:
            ligne += f" · protection perdue à {t_ch / 60.0:.0f} min"
        return ligne

    # -- figures ---------------------------------------------------------

    def _onglet_courant(self) -> str:
        """La clé de l'onglet visible.

        Repérée par le widget et non par son rang : l'onglet de coupe se
        masque, et un rang ne veut alors plus dire la même chose.
        """
        try:
            courant = str(self.onglets.select())
        except (tk.TclError, AttributeError):
            return "nomogramme"
        for cle, cadre in self.cadre_figure.items():
            if str(cadre) == courant:
                return cle
        return "nomogramme"

    def _planifier_figures(self) -> None:
        """Redessine après une pause de saisie, jamais à chaque frappe."""
        if self._tache_figures is not None:
            try:
                self.after_cancel(self._tache_figures)
            except tk.TclError:
                pass
        self._tache_figures = self.after(_DELAI_FIGURES_MS, self.dessiner_figures)
        if self.resultat is not None:
            self.etat_figures.place(in_=self.onglets, relx=1.0, x=-6, y=4, anchor="ne")

    def dessiner_figures(self) -> None:
        """Trace la figure de l'onglet visible, et elle seule."""
        self._tache_figures = None
        # Retiré avant le rendu, mais l'écran ne se repeint qu'après : la
        # mention reste visible exactement le temps du tracé.
        self.etat_figures.place_forget()
        if self.resultat is None:
            # Pas de résultat : effacer les figures plutôt que de laisser
            # celles du calcul précédent, qui se liraient comme valides.
            for etiquette in self._etiquettes.values():
                etiquette.configure(image="")
            # Et défaire le redessin au redimensionnement, qui repeindrait
            # l'ancienne figure au premier mouvement de la fenêtre.
            for cadre in self.cadre_figure.values():
                cadre.unbind("<Configure>")
            self._rendu.clear()
            return

        import matplotlib.pyplot as plt

        from nommogramme.nomogramme.trace import (
            tracer_echauffement,
            tracer_nomogramme,
            tracer_section,
        )

        cle = self._onglet_courant()
        cadre = self.cadre_figure[cle]

        # Une géométrie impossible — hauteur inférieure à ses deux semelles —
        # ne doit pas remonter jusqu'à la boucle d'événements de Tk : le
        # message est déjà affiché sous les champs de saisie, il n'y a rien à
        # dessiner et c'est tout.
        # La coupe : la section soudée tôle par tôle quand il y en a une,
        # sinon le profilé calculé lui-même — catalogue, barre ou boulon.
        section = None
        if cle == "section":
            try:
                section = self.saisie().section() or self.resultat.profil
            except ValueError:
                return

        # Refermer la figure précédente, et pas seulement son widget. Les
        # figures viennent de pyplot, qui les garde dans un registre global :
        # détruire l'affichage laisse la figure vivante. Sur une session de
        # saisie, chaque redessin en abandonnerait une.
        ancienne = self._figures.pop(cle, None)
        if ancienne is not None:
            plt.close(ancienne)

        if cle == "section":
            figure = tracer_section(
                section, exposition=self.resultat.exposition
            )
        else:
            tracer = tracer_nomogramme if cle == "nomogramme" else tracer_echauffement
            figure = tracer(self.resultat, hauteur=self._hauteur_figure(cle, cadre))
        self._figures[cle] = figure
        compose = tuple(figure.get_size_inches())

        # L'étiquette est créée une fois par onglet, puis réutilisée. La
        # détruire et la recréer à chaque redessin n'apportait rien, et créait
        # un piège : une étiquette neuve est vide, et si le contrôle de
        # redondance de « _peindre » concluait « rien à refaire », elle le
        # restait — cadre blanc jusqu'au prochain redimensionnement.
        etiquette = self._etiquettes.get(cle)
        if etiquette is None or not etiquette.winfo_exists():
            etiquette = ttk.Label(cadre, anchor="center", style="Figure.TLabel")
            etiquette.pack(fill="both", expand=True)
            self._etiquettes[cle] = etiquette

        self._peindre(cle, figure, compose, cadre, etiquette)
        cadre.bind(
            "<Configure>",
            lambda _e, k=cle, f=figure, c=compose, d=cadre, l=etiquette:
                self._peindre(k, f, c, d, l),
        )
        self._figures_a_jour = True

    @staticmethod
    def _hauteur_figure(cle: str, cadre: tk.Misc) -> float:
        """Hauteur de figure [po] qui donne au graphique les proportions du cadre.

        Avec une figure de proportions fixes, l'onglet laissait deux larges
        bandes vides. Bornée : trop basse, le nomogramme s'écrase ; trop
        haute, il s'étire sans rien montrer de plus.
        """
        largeur, (bas, haut) = _FORMATS_FIGURE[cle]
        l, h = cadre.winfo_width(), cadre.winfo_height()
        if l < 50 or h < 50:  # cadre pas encore affiché
            return bas
        return min(max(largeur * h / l, bas), haut)

    def _peindre(self, cle, figure, compose, cadre: tk.Misc, etiquette: ttk.Label) -> None:
        """Rend la figure en image, à la densité qui la fait tenir dans le cadre.

        Trois approches ont échoué avant celle-ci, et chacune ne se voyait
        qu'en regardant la fenêtre rendue.

        Laissée à sa taille de composition, la figure débordait du cadre et
        son bas passait sous les boutons. Étirée aux dimensions du cadre, elle
        se déformait : l'espacement des annotations et de la légende est
        calculé pour un rapport de forme donné, et une figure écrasée voit sa
        légende recouvrir le nom de l'axe. Réduite proportionnellement, elle
        ne se déformait plus, mais les polices sont en **points** — taille
        absolue — et occupaient alors une part croissante d'un canevas qui
        rétrécissait : les textes se chevauchaient de nouveau.

        La bonne grandeur à faire varier est donc le **DPI**, qui met tout à
        l'échelle ensemble : traits, textes et marges. Mais
        ``FigureCanvasTkAgg`` pose sa propre liaison ``<Configure>`` et
        réécrit la taille de la figure à chaque événement, ce qui défait le
        réglage — la densité finissait à 104 au lieu de 60.

        On ne passe donc plus par le canevas interactif. La figure est rendue
        hors écran par Agg, à la densité voulue, et le résultat est affiché
        comme une image. C'est exactement le PNG qu'on obtiendrait par
        ``--tracer``, à la taille du cadre.
        """
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from PIL import Image, ImageTk

        # Le cadre a nettement changé de proportions (fenêtre redimensionnée) :
        # on peint tout de suite à l'ancienne, et l'on refait la figure aux
        # nouvelles proportions après la pause habituelle.
        if cle in _FORMATS_FIGURE and cle == self._onglet_courant():
            voulue = self._hauteur_figure(cle, cadre)
            if abs(voulue - compose[1]) > 0.08 * compose[1]:
                self._planifier_figures()

        dispo_l = max(cadre.winfo_width() - 10, 1)
        dispo_h = max(cadre.winfo_height() - 10, 1)
        dpi = max(min(dispo_l / compose[0], dispo_h / compose[1]), _DPI_MINIMAL)

        # Ne rien refaire uniquement si c'est **cette figure-là** qui est déjà
        # affichée à cette densité. Le contrôle ne portait que sur la densité,
        # et laissait donc passer le cas courant : un nouveau calcul — donc une
        # nouvelle figure — dans une fenêtre qu'on n'a pas redimensionnée. Le
        # rendu était sauté et le cadre restait vide. Redimensionner changeait
        # la densité, ce qui débloquait tout : d'où un défaut qui semblait tenir
        # à la taille de la fenêtre alors qu'il tenait à la saisie.
        precedent = self._rendu.get(cle)
        if precedent is not None and precedent[0] is figure and abs(precedent[1] - dpi) < 1.0:
            return

        figure.set_size_inches(*compose, forward=False)
        figure.set_dpi(dpi)
        toile = FigureCanvasAgg(figure)
        toile.draw()

        image = ImageTk.PhotoImage(
            Image.frombytes("RGBA", toile.get_width_height(), bytes(toile.buffer_rgba()))
        )
        # Tk ne retient pas les images : sans cette référence, le ramasse-miettes
        # de Python la libère et le cadre reste vide.
        self._images[cle] = image
        self._rendu[cle] = (figure, dpi)
        etiquette.configure(image=image)

    # -- enregistrement --------------------------------------------------

    def a_propos(self) -> None:
        """L'avertissement complet, sur demande.

        Il ne tient pas en pied d'écran sans le manger, et un pavé de cinq
        lignes affiché en permanence finit par ne plus être lu. La ligne du
        pied dit l'essentiel, ce dialogue dit le reste.
        """
        messagebox.showinfo(f"{_TITRE} — à propos", _AVERTISSEMENT)

    def enregistrer_note(self) -> None:
        if self.resultat is None:
            messagebox.showwarning(_TITRE, "Rien à enregistrer : la saisie est incomplète.")
            return
        nom = self.resultat.profil.nom.replace(" ", "").replace("/", "-")
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer la note de calcul",
            defaultextension=".pdf",
            initialfile=f"note-{nom}.pdf",
            filetypes=[("PDF détaillé", "*.pdf"), ("Word, équations éditables", "*.docx"),
                       ("Markdown", "*.md")],
        )
        if not chemin:
            return

        def ecrire() -> None:
            if chemin.lower().endswith(".md"):
                Path(chemin).write_text(self.resultat.note_de_calcul(), encoding="utf-8")
            elif chemin.lower().endswith(".docx"):
                self.resultat.note_de_calcul_word(chemin, self.saisie().section())
            else:
                self.resultat.note_de_calcul_pdf(chemin, self.saisie().section())

        if self._occupe(self.bouton_note, ecrire):
            self.annoncer(f"Note enregistrée : {Path(chemin).name}", Path(chemin))

    def enregistrer_figures(self) -> None:
        if self.resultat is None:
            messagebox.showwarning(_TITRE, "Rien à enregistrer : la saisie est incomplète.")
            return
        dossier = filedialog.askdirectory(title="Où enregistrer les figures ?")
        if not dossier:
            return

        from nommogramme.nomogramme.trace import (
            tracer_echauffement,
            tracer_nomogramme,
            tracer_section,
        )

        base = self.resultat.profil.nom.replace(" ", "").replace("/", "-")
        cible = Path(dossier)
        section = self.saisie().section() or self.resultat.profil

        def ecrire() -> None:
            tracer_nomogramme(self.resultat, cible / f"nomogramme-{base}.png")
            tracer_echauffement(self.resultat, cible / f"echauffement-{base}.png")
            tracer_section(
                section, cible / f"section-{base}.png",
                exposition=self.resultat.exposition,
            )

        if self._occupe(self.bouton_figures, ecrire):
            self.annoncer(f"3 figures enregistrées dans {cible.name}", None, cible)

    # -- retour d'action ---------------------------------------------------

    def _occupe(self, bouton: ttk.Button, travail) -> bool:
        """Exécute un enregistrement en montrant qu'il est en cours.

        Une à deux secondes sans signe, et l'on clique une seconde fois. Une
        erreur d'écriture — fichier ouvert dans Word, dossier protégé — est
        dite en clair au lieu de remonter dans la boucle de Tk.
        """
        texte = bouton.cget("text")
        fenetre = self.winfo_toplevel()
        bouton.configure(text="Enregistrement…")
        bouton.state(["disabled"])
        fenetre.configure(cursor="watch")
        self.update_idletasks()
        try:
            travail()
            return True
        except OSError as souci:
            messagebox.showerror(
                _TITRE, f"Enregistrement impossible :\n{souci}\n\n"
                "Le fichier est peut-être ouvert dans une autre application."
            )
            return False
        finally:
            bouton.configure(text=texte)
            bouton.state(["!disabled"])
            fenetre.configure(cursor="")

    def annoncer(self, message: str, fichier: Path | None, dossier: Path | None = None) -> None:
        """Compte rendu discret d'un succès, avec de quoi ouvrir le résultat."""
        dossier = dossier or (fichier.parent if fichier else None)
        self.statut.configure(text=f"✓  {message}")
        self.statut.pack(side="left", padx=(12, 6))
        for lien, cible in ((self.lien_ouvrir, fichier), (self.lien_dossier, dossier)):
            if cible is None:
                lien.pack_forget()
            else:
                lien.configure(command=lambda c=cible: _ouvrir(c))
                lien.pack(side="left", padx=(0, 6))
        if self._tache_statut is not None:
            self.after_cancel(self._tache_statut)
        self._tache_statut = self.after(_DUREE_STATUT_MS, self._effacer_statut)

    def _effacer_statut(self) -> None:
        self._tache_statut = None
        for widget in (self.statut, self.lien_ouvrir, self.lien_dossier):
            widget.pack_forget()


_DUREE_STATUT_MS = 12_000
"""Durée d'affichage du compte rendu d'enregistrement [ms]."""


def _ouvrir(chemin: Path) -> None:
    """Ouvre un fichier ou un dossier avec l'application par défaut du système."""
    import os
    import subprocess
    import sys

    if sys.platform == "win32":
        os.startfile(chemin)  # noqa: S606 - chemin choisi par l'utilisateur
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(chemin)])


_TAILLE_CONFORTABLE = (1280, 880)
"""Taille visée, si l'écran le permet [px]."""


def _dimensionner(racine: tk.Tk) -> None:
    """Ouvre la fenêtre à une taille qui tient sur l'écran, et la centre.

    Une géométrie fixe est un piège : 1280 × 880 déborde d'un portable en
    1366 × 768, et le bas de la fenêtre — les boutons d'enregistrement, le
    pied de page — se retrouve hors de l'écran, sans aucun moyen d'y accéder.
    Défaut invisible sur un grand moniteur, bloquant sur une machine de
    chantier.

    La marge réservée tient compte de la barre des tâches et des décorations
    de fenêtre, dont Tk ne connaît pas la hauteur avant l'affichage.
    """
    voulue_l, voulue_h = (int(v * _echelle(racine)) for v in _TAILLE_CONFORTABLE)
    largeur = min(voulue_l, racine.winfo_screenwidth() - 60)
    hauteur = min(voulue_h, racine.winfo_screenheight() - 120)
    x = max(0, (racine.winfo_screenwidth() - largeur) // 2)
    y = max(0, (racine.winfo_screenheight() - hauteur) // 3)
    racine.geometry(f"{largeur}x{hauteur}+{x}+{y}")


def lancer() -> None:
    """Ouvre la fenêtre et rend la main à sa fermeture."""
    _net_sur_ecran_haute_densite()
    racine = tk.Tk()
    racine.title(_TITRE)
    _dimensionner(racine)
    echelle = _echelle(racine)
    racine.minsize(int(900 * echelle), int(560 * echelle))
    _appliquer_theme(racine)
    Application(racine)
    racine.mainloop()


if __name__ == "__main__":  # pragma: no cover
    lancer()
