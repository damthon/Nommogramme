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

from nommogramme.interface.saisie import (
    CONTEXTES,
    DUREES,
    EXPOSITIONS,
    SANS_PROTECTION,
    Saisie,
    executer,
    noms_par_famille,
    produits,
)
from nommogramme.nomogramme.verification import ResultatVerification
from nommogramme.thermique.courbes import COURBES
from nommogramme.unites import en_minutes

__all__ = ["Application", "lancer"]


_TITRE = "Nommogramme — résistance au feu des profilés métalliques"

_DELAI_FIGURES_MS = 400
"""Pause de saisie avant de redessiner les figures [ms]."""

_DPI_MINIMAL = 52.0
"""En deçà, la figure cesse de rétrécir : elle ne serait plus lisible."""

_VERT = "#1a7f37"
_ROUGE = "#c1121f"
_GRIS = "#57606a"

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
        super().__init__(maitre, padding=8)
        self.pack(fill="both", expand=True)

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

        self._construire_variables()
        self._construire_disposition()
        self.rafraichir()

    # -- état ------------------------------------------------------------

    def _construire_variables(self) -> None:
        defaut = Saisie()
        self.var: dict[str, tk.Variable] = {
            "famille": tk.StringVar(value=_famille_de(defaut.profil)),
            "profil": tk.StringVar(value=defaut.profil),
            "nuance": tk.StringVar(value=defaut.nuance),
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
            "contexte": tk.StringVar(value=defaut.contexte),
            "kappa_1": tk.DoubleVar(value=defaut.kappa_1),
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
        train de taper, ce n'est pas une erreur.
        """
        defaut = Saisie()

        def lire(nom: str):
            try:
                return self.var[nom].get()
            except tk.TclError:
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
            contexte=self.var["contexte"].get(),
            kappa_1=lire("kappa_1"),
            kappa_2=lire("kappa_2"),
            C1=lire("C1"),
        )

    @staticmethod
    def _libelle_produit(cle: str) -> str:
        if cle == SANS_PROTECTION:
            return SANS_PROTECTION
        return produits()[cle].get("libelle", cle)

    @staticmethod
    def _cle_produit(libelle: str) -> str:
        if libelle == SANS_PROTECTION:
            return SANS_PROTECTION
        for cle, fiche in produits().items():
            if fiche.get("libelle", cle) == libelle:
                return cle
        return SANS_PROTECTION

    # -- disposition -----------------------------------------------------

    def _construire_disposition(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        gauche = self._panneau_defilant(self)
        gauche.master.master.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        self._construire_parametres(gauche)

        droite = ttk.Frame(self)
        droite.grid(row=0, column=1, sticky="nsew")
        droite.columnconfigure(0, weight=1)
        droite.rowconfigure(3, weight=1)
        self._construire_resultats(droite)

        pied = ttk.Frame(self)
        pied.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        pied.columnconfigure(0, weight=1)
        ttk.Label(
            pied, text=_AVERTISSEMENT_COURT, foreground=_GRIS,
            wraplength=900, justify="left",
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
            conteneur, borderwidth=0, highlightthickness=0, width=largeur
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
        cadre = ttk.LabelFrame(parent, text=titre, padding=6)
        cadre.pack(fill="x", pady=(0, 6))
        cadre.columnconfigure(1, weight=1)
        return cadre

    def _champ(self, parent: ttk.Frame, ligne: int, etiquette: str, widget: tk.Widget) -> None:
        ttk.Label(parent, text=etiquette).grid(row=ligne, column=0, sticky="w", pady=1)
        widget.grid(row=ligne, column=1, sticky="ew", padx=(6, 0), pady=1)

    def _nombre(self, parent: ttk.Frame, cle: str, largeur: int = 10) -> ttk.Entry:
        return ttk.Entry(parent, textvariable=self.var[cle], width=largeur)

    def _liste(
        self, parent: ttk.Frame, cle: str, valeurs, largeur: int = 22
    ) -> ttk.Combobox:
        return ttk.Combobox(
            parent, textvariable=self.var[cle], values=list(valeurs),
            state="readonly", width=largeur,
        )

    def _construire_parametres(self, parent: ttk.Frame) -> None:
        element = self._bloc(parent, "Élément")
        familles = list(noms_par_famille())
        self.liste_familles = self._liste(element, "famille", familles)
        self._champ(element, 0, "Famille", self.liste_familles)
        self.liste_profils = self._liste(
            element, "profil", noms_par_famille()[self.var["famille"].get()]
        )
        self._champ(element, 1, "Profilé", self.liste_profils)
        self._champ(element, 2, "Nuance", self._liste(element, "nuance", ("S235", "S355")))

        efforts = self._bloc(parent, "Sollicitations en incendie")
        self._champ(efforts, 0, "N_fi,Ed  [kN]", self._nombre(efforts, "N"))
        self._champ(efforts, 1, "M_y,fi,Ed  [kN·m]", self._nombre(efforts, "My"))
        self._champ(efforts, 2, "M_z,fi,Ed  [kN·m]", self._nombre(efforts, "Mz"))
        ttk.Label(
            efforts, text="Combinaison accidentelle. N positif en compression.",
            foreground=_GRIS, wraplength=250,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(3, 0))

        geometrie = self._bloc(parent, "Géométrie")
        self._champ(geometrie, 0, "Longueur d'épure L  [m]", self._nombre(geometrie, "L"))
        self._champ(geometrie, 1, "Flambement l_fi  [m]", self._nombre(geometrie, "l_fi"))
        self._champ(geometrie, 2, "β_M  [-]", self._nombre(geometrie, "beta_M"))
        ttk.Checkbutton(
            geometrie, text="Semelle comprimée maintenue",
            variable=self.var["maintien"],
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(3, 0))
        ttk.Label(
            geometrie, text="Poteau continu : l_fi = 0,5·L en étage courant, "
                            "0,7·L au dernier (§4.2.3.2(4)).",
            foreground=_GRIS, wraplength=250,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(3, 0))

        feu = self._bloc(parent, "Exposition au feu")
        self._champ(feu, 0, "Configuration", self._liste(feu, "exposition", EXPOSITIONS))
        self._champ(
            feu, 1, "Courbe de feu",
            self._liste(feu, "feu", [c.nom for c in COURBES.values()]),
        )
        self._champ(
            feu, 2, "Durée exigée  [min]",
            self._liste(feu, "duree", DUREES, largeur=8),
        )

        protection = self._bloc(parent, "Protection")
        libelles = [SANS_PROTECTION] + [
            self._libelle_produit(cle) for cle in sorted(produits())
        ]
        self._champ(protection, 0, "Produit", self._liste(protection, "protection", libelles))
        self.champ_epaisseur = self._nombre(protection, "epaisseur")
        self._champ(protection, 1, "Épaisseur d_p  [mm]", self.champ_epaisseur)
        self.note_produit = ttk.Label(
            protection, text="", foreground=_GRIS, wraplength=250, justify="left"
        )
        self.note_produit.grid(row=2, column=0, columnspan=2, sticky="w", pady=(3, 0))

        avances = self._bloc(parent, "Paramètres avancés")
        self._champ(avances, 0, "Référentiel", self._liste(avances, "contexte", CONTEXTES))
        self._champ(avances, 1, "κ₁  [-]", self._nombre(avances, "kappa_1"))
        self._champ(avances, 2, "κ₂  [-]", self._nombre(avances, "kappa_2"))
        self._champ(avances, 3, "C₁  [-]", self._nombre(avances, "C1"))

        self._mettre_a_jour_protection()

    def _construire_resultats(self, parent: ttk.Frame) -> None:
        self.banniere = tk.Label(
            parent, text="", font=("TkDefaultFont", 11, "bold"),
            anchor="w", padx=10, pady=8, justify="left",
        )
        self.banniere.grid(row=0, column=0, sticky="ew")

        indicateurs = ttk.Frame(parent, padding=(0, 8))
        indicateurs.grid(row=1, column=0, sticky="ew")
        self.indicateur: dict[str, ttk.Label] = {}
        for colonne, (cle, titre) in enumerate(
            (("mu_0", "μ₀"), ("theta_cr", "θ_cr retenue"),
             ("theta_a", "θ_a à l'échéance"), ("t_fi_d", "t_fi,d"))
        ):
            indicateurs.columnconfigure(colonne, weight=1)
            case = ttk.Frame(indicateurs)
            case.grid(row=0, column=colonne, sticky="ew", padx=2)
            ttk.Label(case, text=titre, foreground=_GRIS).pack(anchor="w")
            valeur = ttk.Label(case, text="—", font=("TkDefaultFont", 14, "bold"))
            valeur.pack(anchor="w")
            self.indicateur[cle] = valeur

        self.details = ttk.Label(parent, text="", wraplength=680, justify="left")
        self.details.grid(row=2, column=0, sticky="ew", pady=(0, 6))

        self.onglets = ttk.Notebook(parent)
        self.onglets.grid(row=3, column=0, sticky="nsew")
        self.onglets.bind("<<NotebookTabChanged>>", lambda _: self._planifier_figures())
        self.cadre_figure: dict[str, ttk.Frame] = {}
        for cle, titre in (("nomogramme", "Nomogramme"), ("echauffement", "Échauffement")):
            cadre = ttk.Frame(self.onglets)
            self.onglets.add(cadre, text=titre)
            self.cadre_figure[cle] = cadre

        boutons = ttk.Frame(parent, padding=(0, 8, 0, 0))
        boutons.grid(row=4, column=0, sticky="ew")
        ttk.Button(
            boutons, text="Enregistrer la note de calcul…", command=self.enregistrer_note
        ).pack(side="left")
        ttk.Button(
            boutons, text="Enregistrer les figures…", command=self.enregistrer_figures
        ).pack(side="left", padx=6)

    # -- réactions -------------------------------------------------------

    def _sur_changement(self, nom: str) -> None:
        if self._silence:
            return
        if nom == "famille":
            self._sur_changement_famille()
            return
        if nom == "protection":
            self._mettre_a_jour_protection()
        self.rafraichir()

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
        if cle == SANS_PROTECTION:
            self.champ_epaisseur.configure(state="disabled")
            self.note_produit.configure(text="")
            return

        fiche = produits()[cle]
        self.champ_epaisseur.configure(state="normal")
        self._silence = True
        self.var["epaisseur"].set(round(fiche["dp_min"] * 1e3, 1))
        self._silence = False
        self.note_produit.configure(
            text=(
                f"λ_p = {fiche['lambda_p']} W/m·K · ρ_p = {fiche['rho_p']:.0f} kg/m³\n"
                f"c_p = {fiche['c_p']:.0f} J/kg·K · pose {fiche['pose']}\n"
                f"épaisseurs usuelles {fiche['dp_min'] * 1e3:.0f} à "
                f"{fiche['dp_max'] * 1e3:.0f} mm"
            )
        )

    def rafraichir(self) -> None:
        """Recalcule les chiffres, et programme le redessin des figures."""
        try:
            self.resultat = executer(self.saisie())
            self.erreur = None
        except Exception as souci:  # une saisie incohérente ne doit pas fermer la fenêtre
            self.resultat = None
            self.erreur = str(souci)

        self._afficher()
        self._figures_a_jour = False
        self._planifier_figures()

    def _afficher(self) -> None:
        if self.erreur is not None or self.resultat is None:
            self.banniere.configure(
                text=f"Saisie inexploitable — {self.erreur}", background="#fff4e5",
                foreground=_GRIS,
            )
            for valeur in self.indicateur.values():
                valeur.configure(text="—")
            self.details.configure(text="")
            return

        r = self.resultat
        duree = en_minutes(r.duree_requise)
        satisfait = bool(r.verdict)
        self.banniere.configure(
            text=(
                f"R{duree:.0f} {r.verdict.value} — θ_a = {r.theta_a_a_echeance:.0f} °C "
                f"à l'échéance contre θ_cr = {r.theta_cr:.0f} °C, "
                f"marge {r.marge_temperature:+.0f} °C"
            ),
            background="#e6f4ea" if satisfait else "#fdecea",
            foreground=_VERT if satisfait else _ROUGE,
        )

        self.indicateur["mu_0"].configure(text=f"{r.mu_0:.3f}")
        self.indicateur["theta_cr"].configure(text=f"{r.theta_cr:.0f} °C")
        self.indicateur["theta_a"].configure(text=f"{r.theta_a_a_echeance:.0f} °C")
        self.indicateur["t_fi_d"].configure(
            text=f"{r.t_fi_d_minutes:.0f} min" if r.t_fi_d_minutes is not None
            else "non atteinte"
        )

        lignes = [
            f"Nomogramme, éq. (4.22) : "
            f"{r.theta_cr_nomogramme:.0f} °C" if r.theta_cr_nomogramme else
            "Nomogramme, éq. (4.22) : —",
            f"Vérification croisée, §4.2.3 : "
            f"{r.theta_cr_exact:.0f} °C" if r.theta_cr_exact else
            "Vérification croisée, §4.2.3 : —",
            f"Retenue : {r.source_theta_cr}",
            f"Critère gouvernant : {r.gouverne_par} · {r.classification}",
            self._ligne_massivete(r),
        ]
        if r.ecart_nomogramme is not None and r.ecart_nomogramme > 10.0:
            lignes.append(
                f"⚠ L'équation (4.22) donne {r.ecart_nomogramme:.0f} °C de plus que "
                "la vérification complète : l'instabilité gouverne. C'est la valeur "
                "basse qui est retenue."
            )
        lignes.extend(f"⚠ {a}" for a in r.avertissements)
        self.details.configure(text="\n".join(lignes))

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
        return (
            f"A_p/V = {r.Am_sur_V:.1f} m⁻¹ · {r.protection.libelle or r.protection.nom}, "
            f"d_p = {r.protection.d_p * 1e3:.1f} mm"
        )

    # -- figures ---------------------------------------------------------

    def _onglet_courant(self) -> str:
        try:
            index = self.onglets.index(self.onglets.select())
        except (tk.TclError, AttributeError):
            return "nomogramme"
        return ("nomogramme", "echauffement")[index]

    def _planifier_figures(self) -> None:
        """Redessine après une pause de saisie, jamais à chaque frappe."""
        if self._tache_figures is not None:
            try:
                self.after_cancel(self._tache_figures)
            except tk.TclError:
                pass
        self._tache_figures = self.after(_DELAI_FIGURES_MS, self.dessiner_figures)

    def dessiner_figures(self) -> None:
        """Trace la figure de l'onglet visible, et elle seule."""
        self._tache_figures = None
        if self.resultat is None:
            return

        import matplotlib.pyplot as plt

        from nommogramme.nomogramme.trace import tracer_echauffement, tracer_nomogramme

        cle = self._onglet_courant()
        cadre = self.cadre_figure[cle]

        # Refermer la figure précédente, et pas seulement son widget. Les
        # figures viennent de pyplot, qui les garde dans un registre global :
        # détruire l'affichage laisse la figure vivante. Sur une session de
        # saisie, chaque redessin en abandonnerait une.
        ancienne = self._figures.pop(cle, None)
        if ancienne is not None:
            plt.close(ancienne)

        tracer = tracer_nomogramme if cle == "nomogramme" else tracer_echauffement
        figure = tracer(self.resultat)
        self._figures[cle] = figure
        compose = tuple(figure.get_size_inches())

        # L'étiquette est créée une fois par onglet, puis réutilisée. La
        # détruire et la recréer à chaque redessin n'apportait rien, et créait
        # un piège : une étiquette neuve est vide, et si le contrôle de
        # redondance de « _peindre » concluait « rien à refaire », elle le
        # restait — cadre blanc jusqu'au prochain redimensionnement.
        etiquette = self._etiquettes.get(cle)
        if etiquette is None or not etiquette.winfo_exists():
            etiquette = ttk.Label(cadre, anchor="center")
            etiquette.pack(fill="both", expand=True)
            self._etiquettes[cle] = etiquette

        self._peindre(cle, figure, compose, cadre, etiquette)
        cadre.bind(
            "<Configure>",
            lambda _e, k=cle, f=figure, c=compose, d=cadre, l=etiquette:
                self._peindre(k, f, c, d, l),
        )
        self._figures_a_jour = True

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
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer la note de calcul",
            defaultextension=".md",
            initialfile=f"note-{self.resultat.profil.nom.replace(' ', '')}.md",
            filetypes=[("Markdown", "*.md"), ("Tous les fichiers", "*.*")],
        )
        if not chemin:
            return
        Path(chemin).write_text(self.resultat.note_de_calcul(), encoding="utf-8")
        messagebox.showinfo(_TITRE, f"Note enregistrée :\n{chemin}")

    def enregistrer_figures(self) -> None:
        if self.resultat is None:
            messagebox.showwarning(_TITRE, "Rien à enregistrer : la saisie est incomplète.")
            return
        dossier = filedialog.askdirectory(title="Où enregistrer les deux figures ?")
        if not dossier:
            return

        from nommogramme.nomogramme.trace import tracer_echauffement, tracer_nomogramme

        base = self.resultat.profil.nom.replace(" ", "")
        cible = Path(dossier)
        tracer_nomogramme(self.resultat, cible / f"nomogramme-{base}.png")
        tracer_echauffement(self.resultat, cible / f"echauffement-{base}.png")
        messagebox.showinfo(_TITRE, f"Deux figures enregistrées dans :\n{dossier}")


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
    voulue_l, voulue_h = _TAILLE_CONFORTABLE
    largeur = min(voulue_l, racine.winfo_screenwidth() - 60)
    hauteur = min(voulue_h, racine.winfo_screenheight() - 120)
    x = max(0, (racine.winfo_screenwidth() - largeur) // 2)
    y = max(0, (racine.winfo_screenheight() - hauteur) // 3)
    racine.geometry(f"{largeur}x{hauteur}+{x}+{y}")


def lancer() -> None:
    """Ouvre la fenêtre et rend la main à sa fermeture."""
    racine = tk.Tk()
    racine.title(_TITRE)
    _dimensionner(racine)
    racine.minsize(900, 560)
    try:
        ttk.Style().theme_use("vista" if racine.tk.call("tk", "windowingsystem") == "win32" else "clam")
    except tk.TclError:
        pass
    Application(racine)
    racine.mainloop()


if __name__ == "__main__":  # pragma: no cover
    lancer()
