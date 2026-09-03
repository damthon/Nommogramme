"""Tracés : le nomogramme, la courbe d'échauffement, la coupe de section.

Trois figures, pour trois usages :

* ``tracer_nomogramme`` reproduit l'instrument graphique du §11 du plan de
  conception — deux quadrants partageant l'axe des températures, et le chemin
  de lecture du cas traité ;
* ``tracer_echauffement`` montre θ_a(t) confrontée à la température critique,
  ce qui se lit plus vite pour juger d'une marge ;
* ``tracer_section`` dessine à l'échelle une section reconstituée soudée, avec
  ses cotes et la face que la dalle recouvre.

``matplotlib`` est une dépendance facultative : ``pip install
'nommogramme[trace]'``.

Lisibilité des annotations
--------------------------

Ces figures portent une dizaine de textes ancrés à des points de données —
θ_cr, t_fi,d, μ₀, les étiquettes directes des courbes. Placés à un décalage
fixe, ils finissent immanquablement par se croiser : sur un élément protégé de
longue durée, « 674 °C à R180 » tombait pile sur la ligne de θ_cr et sur son
étiquette ; sur un caisson tenant 169 minutes, « t_fi,d » sortait du cadre.
Ces collisions ne dépendent pas du code mais des chiffres, et il n'existe pas
de décalage fixe qui convienne à tous les cas.

``Placeur`` traite le problème là où il se pose : il mesure ce qu'il vient de
poser, et le repousse tant qu'il croise une courbe, un texte déjà en place ou
le bord du cadre. Chaque texte porte en plus un liseré de la couleur du fond,
qui le détache de ce qui passe dessous quand aucune position n'est libre.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..materiaux.protection import Protection
from ..profils.composes import (
    FaceCouverte,
    SectionCaisson,
    SectionSoudee,
    caracteristiques,
)
from ..profils.geometrie import Exposition, facteur_massivete, perimetre_expose
from ..profils.modele import Profil
from ..references import EC3_MASSIVETE, EC3_THETA_CR
from ..thermique.courbes import ISO834, CourbeFeu
from ..thermique.evolution import echauffement
from ..unites import en_minutes, minutes
from .temperature_critique import MU_0_MINIMAL, temperature_critique
from .verification import ResultatVerification

__all__ = [
    "Palette",
    "CLAIR",
    "SOMBRE",
    "Placeur",
    "tracer_nomogramme",
    "tracer_echauffement",
    "tracer_section",
]


_MESSAGE_MATPLOTLIB = (
    "Le tracé demande matplotlib : pip install 'nommogramme[trace]'"
)


@dataclass(frozen=True, slots=True)
class Palette:
    """Jeu de couleurs d'une figure.

    Les deux teintes de série proviennent des emplacements 1 et 2 d'une
    palette catégorielle validée pour la déficience de vision des couleurs :
    séparation ΔE 24,7 en mode clair et 26,8 en mode sombre, bien au-delà du
    seuil de 8. L'acier occupe l'emplacement 1 parce qu'il est le sujet ; les
    gaz suivent.
    """

    fond: str
    encre: str
    encre_secondaire: str
    encre_attenuee: str
    grille: str
    axe: str
    acier: str
    gaz: str
    favorable: str
    critique: str
    matiere: str = "#c9d8ec"
    """Remplissage d'une tôle, sur la coupe de section."""


CLAIR = Palette(
    fond="#fcfcfb",
    encre="#0b0b0b",
    encre_secondaire="#52514e",
    encre_attenuee="#898781",
    grille="#e1e0d9",
    axe="#c3c2b7",
    acier="#2a78d6",
    gaz="#eb6834",
    favorable="#0ca30c",
    critique="#d03b3b",
    matiere="#cfe0f5",
)

SOMBRE = Palette(
    fond="#1a1a19",
    encre="#ffffff",
    encre_secondaire="#c3c2b7",
    encre_attenuee="#898781",
    grille="#2c2c2a",
    axe="#383835",
    acier="#3987e5",
    gaz="#d95926",
    favorable="#0ca30c",
    critique="#d03b3b",
    matiere="#26364a",
)

_THEMES = {"clair": CLAIR, "sombre": SOMBRE}


def _palette(theme: str | Palette) -> Palette:
    if isinstance(theme, Palette):
        return theme
    try:
        return _THEMES[theme]
    except KeyError:
        raise ValueError(
            f"Thème {theme!r} inconnu. Disponibles : {', '.join(_THEMES)}"
        ) from None


def _pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as erreur:  # pragma: no cover - dépend de l'installation
        raise ImportError(_MESSAGE_MATPLOTLIB) from erreur
    return plt


def _rendu(figure):
    """Le moteur de rendu de la figure, seul capable de mesurer un texte.

    Une figure fraîchement créée n'en a pas encore : il faut le lui demander,
    ce que seul le canevas sait faire. On passe par Agg, qui est le dos de
    tous les tracés de ce module.
    """
    try:
        return figure.canvas.get_renderer()
    except AttributeError:  # pragma: no cover - canevas non Agg
        from matplotlib.backends.backend_agg import FigureCanvasAgg

        FigureCanvasAgg(figure)
        return figure.canvas.get_renderer()


def _habiller(axes, p: Palette) -> None:
    """Chrome commun : grille en filet, axes discrets, pas de cadre."""
    axes.set_facecolor(p.fond)
    axes.grid(True, color=p.grille, linewidth=0.6, zorder=0)
    axes.set_axisbelow(True)
    for bord in ("top", "right"):
        axes.spines[bord].set_visible(False)
    for bord in ("left", "bottom"):
        axes.spines[bord].set_color(p.axe)
        axes.spines[bord].set_linewidth(0.8)
    axes.tick_params(colors=p.encre_attenuee, labelsize=8, length=3, width=0.8)


def _enregistrer(figure, chemin: Path | str | None, p: Palette):
    if chemin is None:
        return figure
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(
        chemin, dpi=150, bbox_inches="tight", facecolor=p.fond, edgecolor="none"
    )
    # La figure est refermée : l'appelant a son fichier, la garder ouverte
    # ferait fuir la mémoire à chaque appel.
    _pyplot().close(figure)
    return chemin


# --- placement des annotations ------------------------------------------------


def _segment_traverse(boite, x0: float, y0: float, x1: float, y1: float) -> bool:
    """Le segment coupe-t-il le rectangle ? Découpage de Liang–Barsky.

    Un test point par point laisserait passer les segments raides, dont deux
    points consécutifs peuvent enjamber tout un texte.
    """
    dx, dy = x1 - x0, y1 - y0
    debut, fin = 0.0, 1.0
    for pente, marge in (
        (-dx, x0 - boite.x0),
        (dx, boite.x1 - x0),
        (-dy, y0 - boite.y0),
        (dy, boite.y1 - y0),
    ):
        if pente == 0.0:
            if marge < 0.0:
                return False
            continue
        rapport = marge / pente
        if pente < 0.0:
            if rapport > fin:
                return False
            debut = max(debut, rapport)
        else:
            if rapport < debut:
                return False
            fin = min(fin, rapport)
    return debut <= fin


_CANDIDATS_USUELS: tuple[tuple[float, float, str, str], ...] = (
    (8, 8, "left", "bottom"),
    (8, -8, "left", "top"),
    (-8, 8, "right", "bottom"),
    (-8, -8, "right", "top"),
    (8, 22, "left", "bottom"),
    (-8, -22, "right", "top"),
    (0, 16, "center", "bottom"),
    (0, -16, "center", "top"),
    (24, 34, "left", "bottom"),
    (-24, -34, "right", "top"),
)
"""Positions essayées par défaut, de la plus proche à la plus lointaine."""


class Placeur:
    """Pose les annotations d'un axe sans qu'elles deviennent illisibles.

    Trois choses rendent un texte illisible sur ces figures, et les trois se
    sont produites : il croise une courbe, il recouvre un texte voisin, ou il
    déborde du cadre. Le placeur essaie les positions proposées dans l'ordre
    et retient la première qui n'en subit aucune.

    Il faut pour cela **mesurer** le texte, donc le poser puis le retirer si
    la position ne convient pas. C'est le seul moyen : la largeur d'un texte
    dépend de la police, du corps et du rendu, qu'aucun calcul a priori ne
    reproduit.

    Deux précautions rendent la mesure fidèle :

    * l'axe doit avoir ses limites et sa position définitives — un
      ``tight_layout`` ou un ``subplots_adjust`` postérieur déplacerait tout
      ce qui a été mesuré ;
    * la densité de rendu peut changer ensuite sans dommage, puisqu'elle met
      textes et traits à la même échelle. C'est ce qui permet à l'interface de
      bureau de redimensionner ses figures sans rouvrir la question.
    """

    marge = 2.0
    """Distance minimale entre deux textes, en pixels de rendu."""

    def __init__(self, axes, palette: Palette) -> None:
        self.axes = axes
        self.palette = palette
        self._occupe: list = []
        self._traits: list[tuple[float, float, float, float]] = []

    # -- ce qu'il faut éviter ---------------------------------------------

    def eviter_courbe(self, abscisses, ordonnees) -> None:
        """Enregistre une courbe tracée en coordonnées de données."""
        points = self.axes.transData.transform(list(zip(abscisses, ordonnees)))
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            self._traits.append((float(x0), float(y0), float(x1), float(y1)))

    def eviter_horizontale(self, ordonnee: float) -> None:
        """Enregistre une ligne de repère horizontale, sur toute la largeur."""
        gauche, droite = self.axes.get_xlim()
        self.eviter_courbe([gauche, droite], [ordonnee, ordonnee])

    def eviter_verticale(self, abscisse: float) -> None:
        """Enregistre une ligne de repère verticale, sur toute la hauteur."""
        bas, haut = self.axes.get_ylim()
        self.eviter_courbe([abscisse, abscisse], [bas, haut])

    # -- pose ---------------------------------------------------------------

    def poser(
        self,
        texte: str,
        xy: tuple[float, float],
        candidats=_CANDIDATS_USUELS,
        *,
        halo: bool = True,
        confiner: bool = True,
        **style,
    ):
        """Pose un texte à la première position libre, et le renvoie.

        ``candidats`` est une suite de ``(dx, dy, ha, va)`` en points
        typographiques, du placement préféré au plus lointain. Si aucun ne
        convient, le premier est retenu malgré tout : mieux vaut un texte un
        peu serré que pas de texte, et le liseré le garde lisible.
        """
        import matplotlib.patheffects as effets

        if halo:
            style.setdefault(
                "path_effects",
                [effets.withStroke(linewidth=3.0, foreground=self.palette.fond)],
            )
        style.setdefault("annotation_clip", False)
        style.setdefault("zorder", 8)

        rendu = _rendu(self.axes.figure)
        cadre = self.axes.get_window_extent(rendu)
        repli = None
        for dx, dy, ha, va in candidats:
            annotation = self.axes.annotate(
                texte, xy=xy, xytext=(dx, dy), textcoords="offset points",
                ha=ha, va=va, **style,
            )
            boite = annotation.get_window_extent(rendu)
            if self._convient(boite, cadre, confiner):
                if repli is not None:
                    repli.remove()
                self._occupe.append(boite.padded(self.marge))
                return annotation
            if repli is None:
                # La première position essayée est la plus proche du point
                # désigné : on la garde en réserve au cas où aucune ne
                # conviendrait.
                repli = annotation
            else:
                annotation.remove()

        self._occupe.append(repli.get_window_extent(rendu).padded(self.marge))
        return repli

    def _convient(self, boite, cadre, confiner: bool) -> bool:
        if confiner and not _dedans(boite, cadre):
            return False
        if any(boite.overlaps(occupee) for occupee in self._occupe):
            return False
        elargie = boite.padded(self.marge)
        return not any(_segment_traverse(elargie, *trait) for trait in self._traits)

    def reserver(self, artiste) -> None:
        """Déclare un texte déjà posé, pour que les suivants l'évitent."""
        self._occupe.append(
            artiste.get_window_extent(_rendu(self.axes.figure)).padded(self.marge)
        )


def _dedans(boite, cadre) -> bool:
    """La boîte tient-elle dans le cadre ?"""
    return (
        boite.x0 >= cadre.x0 - 1.0
        and boite.x1 <= cadre.x1 + 1.0
        and boite.y0 >= cadre.y0 - 1.0
        and boite.y1 <= cadre.y1 + 1.0
    )


# --- courbe d'échauffement ----------------------------------------------------


def tracer_echauffement(
    resultat: ResultatVerification,
    chemin: Path | str | None = None,
    theme: str | Palette = "clair",
    titre: str | None = None,
):
    """Trace θ_a(t) et θ_g(t), avec la température critique et l'échéance.

    Renvoie le chemin écrit, ou la figure si ``chemin`` vaut ``None``.
    """
    plt = _pyplot()
    p = _palette(theme)

    thermique = resultat.thermique
    duree_affichee = min(
        thermique.duree, max(minutes(120), resultat.duree_requise * 1.6)
    )
    instants = [
        en_minutes(t) for t in thermique.temps if t <= duree_affichee
    ]
    acier = list(thermique.temperatures[: len(instants)])
    gaz = list(thermique.temperatures_gaz[: len(instants)])

    figure, axes = plt.subplots(figsize=(8.2, 4.6), facecolor=p.fond)
    _habiller(axes, p)

    axes.plot(instants, gaz, color=p.gaz, linewidth=2.0, label="Gaz du foyer", zorder=3)
    axes.plot(
        instants, acier, color=p.acier, linewidth=2.0,
        label="Acier", zorder=4,
    )

    # Température critique : c'est bien un seuil, le tireté le dit.
    axes.axhline(
        resultat.theta_cr, color=p.encre_secondaire, linewidth=1.4,
        linestyle=(0, (6, 4)), zorder=2,
    )

    echeance = en_minutes(resultat.duree_requise)
    visible = echeance <= instants[-1]
    if visible:
        axes.axvline(
            echeance, color=p.encre_attenuee, linewidth=1.0,
            linestyle=(0, (2, 3)), zorder=2,
        )

    couleur = p.favorable if resultat.verdict else p.critique
    if visible:
        axes.plot(
            [echeance], [resultat.theta_a_a_echeance],
            marker="o", markersize=8, color=couleur,
            markeredgecolor=p.fond, markeredgewidth=2, zorder=6,
        )

    axes.set_xlabel("Durée d'exposition [min]", fontsize=9, color=p.encre_secondaire)
    axes.set_ylabel("Température [°C]", fontsize=9, color=p.encre_secondaire)
    axes.set_xlim(0, instants[-1])
    axes.set_ylim(0, max(max(gaz), resultat.theta_cr) * 1.12)

    legende = axes.legend(
        loc="lower right", frameon=False, fontsize=8.5, labelcolor=p.encre_secondaire
    )
    legende.set_zorder(7)

    axes.set_title(
        titre or _titre(resultat),
        fontsize=11, color=p.encre, loc="left", pad=26,
    )
    axes.annotate(
        _sous_titre(resultat),
        xy=(0, 1), xycoords="axes fraction",
        xytext=(0, 9), textcoords="offset points",
        fontsize=8.5, color=p.encre_attenuee,
    )

    # La mise en page vient **avant** les annotations : elle déplace l'axe, et
    # tout ce qui aurait été mesuré avant elle le serait au mauvais endroit.
    figure.tight_layout()

    placeur = Placeur(axes, p)
    placeur.eviter_courbe(instants, gaz)
    placeur.eviter_courbe(instants, acier)
    placeur.eviter_horizontale(resultat.theta_cr)
    if visible:
        placeur.eviter_verticale(echeance)
        # La légende occupe le coin inférieur droit : rien n'a le droit d'y
        # aller. Elle est déclarée comme un texte déjà posé.
        placeur.reserver(legende)

    placeur.poser(
        f"θ_cr = {resultat.theta_cr:.0f} °C",
        xy=(instants[-1], resultat.theta_cr),
        candidats=(
            (-6, 7, "right", "bottom"),
            (-6, -9, "right", "top"),
            (-6, 20, "right", "bottom"),
            (-6, -22, "right", "top"),
        ),
        fontsize=8.5, color=p.encre_secondaire,
    )

    if visible:
        placeur.poser(
            f"R{echeance:.0f}",
            xy=(echeance, axes.get_ylim()[1]),
            candidats=((4, -12, "left", "top"), (-4, -12, "right", "top")),
            fontsize=8.5, color=p.encre_attenuee,
        )

    # Le verdict se lit à l'échéance, pas au croisement : sur un élément
    # confortablement satisfait, le croisement tombe hors fenêtre et la figure
    # resterait sans repère.
    if visible:
        placeur.poser(
            f"{resultat.theta_a_a_echeance:.0f} °C à R{echeance:.0f}"
            f"  ·  marge {resultat.marge_temperature:+.0f} °C",
            xy=(echeance, resultat.theta_a_a_echeance),
            candidats=(
                (10, -6, "left", "top"),
                (10, 8, "left", "bottom"),
                (-10, -6, "right", "top"),
                (-10, 8, "right", "bottom"),
                (10, -26, "left", "top"),
                (-10, 24, "right", "bottom"),
            ),
            fontsize=9, color=couleur, fontweight="semibold",
        )

    if resultat.t_fi_d_minutes is not None and resultat.t_fi_d_minutes <= instants[-1]:
        placeur.poser(
            f"t_fi,d = {resultat.t_fi_d_minutes:.0f} min",
            xy=(resultat.t_fi_d_minutes, resultat.theta_cr),
            candidats=(
                (6, 10, "left", "bottom"),
                (-6, 10, "right", "bottom"),
                (6, -12, "left", "top"),
                (-6, -12, "right", "top"),
                (6, 26, "left", "bottom"),
                (-6, -30, "right", "top"),
            ),
            fontsize=8.5, color=p.encre_secondaire,
        )

    return _enregistrer(figure, chemin, p)


def _titre(resultat: ResultatVerification) -> str:
    verdict = "satisfait" if resultat.verdict else "non satisfait"
    return (
        f"{resultat.profil.nom} — R{en_minutes(resultat.duree_requise):.0f} "
        f"{verdict}"
    )


def _sous_titre(resultat: ResultatVerification) -> str:
    morceaux = [
        f"{resultat.nuance.value}",
        f"A_m/V = {resultat.Am_sur_V:.0f} m⁻¹",
        f"μ₀ = {resultat.mu_0:.2f}",
        str(resultat.protection) if resultat.protection else "sans protection",
    ]
    return "  ·  ".join(morceaux)


# --- nomogramme ---------------------------------------------------------------


def tracer_nomogramme(
    resultat: ResultatVerification,
    chemin: Path | str | None = None,
    theme: str | Palette = "clair",
):
    """Trace le nomogramme à deux quadrants, avec le chemin de lecture.

    Quadrant gauche : la relation μ₀ → θ_a,cr de l'équation (4.22),
    EN 1993-1-2 §4.2.4. Quadrant droit : l'échauffement de l'élément sous la
    courbe de feu retenue. Les deux quadrants partagent l'axe vertical des
    températures, qui matérialise le couplage : c'est par lui que la voie
    mécanique et la voie thermique se rejoignent.

    Le chemin de lecture part de μ₀ sur l'axe inférieur gauche, remonte à la
    courbe (4.22), traverse l'axe partagé et redescend sur l'axe des temps.

    La figure ne montre que le cas traité. Une famille de courbes de massiveté
    en fond de carte a été essayée puis retirée : elle n'aurait de sens que
    pour un élément nu, et juxtaposer des courbes d'acier nu à un cas protégé
    invite à une comparaison fausse.
    """
    plt = _pyplot()
    p = _palette(theme)

    duree_max = max(minutes(120), resultat.duree_requise * 1.5)
    theta_max = 1000.0

    figure, (gauche, droite) = plt.subplots(
        1, 2, figsize=(11.0, 5.4), facecolor=p.fond, sharey=True,
        gridspec_kw={"width_ratios": [1.0, 1.3], "wspace": 0.0},
    )

    # Titre, sous-titre et légende sont placés **dans** le canevas, et les
    # marges réservées en conséquence.
    #
    # Les poser à l'extérieur — y = 1,06 pour le titre, y = −0,04 pour la
    # légende — fonctionne à l'enregistrement, où « bbox_inches="tight" »
    # agrandit le canevas pour les rattraper. Mais une figure affichée n'est
    # jamais recadrée : dans un canevas Tk ou une page web, tout ce qui
    # dépasse est simplement absent. Le titre et la légende disparaissaient
    # sans que rien ne le signale.
    #
    # Cet ajustement vient **avant** le tracé des quadrants : il déplace les
    # axes, et le placement des annotations mesure des positions à l'écran.
    figure.subplots_adjust(top=0.855, bottom=0.155, left=0.06, right=0.985)

    _quadrant_gauche(gauche, resultat, p, theta_max)
    _quadrant_droit(droite, resultat, p, theta_max, duree_max)

    # L'axe partagé : la jonction des deux quadrants est l'échelle de
    # température, on la trace comme un axe et non comme une simple bordure.
    gauche.spines["right"].set_visible(True)
    gauche.spines["right"].set_color(p.encre_secondaire)
    gauche.spines["right"].set_linewidth(1.2)
    droite.spines["left"].set_visible(False)

    poignees, etiquettes = droite.get_legend_handles_labels()
    figure.legend(
        poignees, etiquettes, loc="lower center", ncol=len(etiquettes),
        frameon=False, fontsize=8.5, labelcolor=p.encre_secondaire,
        bbox_to_anchor=(0.5, 0.005),
    )

    figure.suptitle(
        _titre(resultat), fontsize=11.5, color=p.encre, x=0.02, ha="left", y=0.975
    )
    figure.text(
        0.02, 0.925, _sous_titre(resultat),
        fontsize=8.5, color=p.encre_attenuee, ha="left",
    )
    return _enregistrer(figure, chemin, p)


def _quadrant_gauche(axes, resultat, p: Palette, theta_max: float) -> None:
    """μ₀ → θ_a,cr : la courbe de l'équation (4.22), lue de droite à gauche."""
    _habiller(axes, p)

    # μ₀ croît vers la gauche pour que l'axe des températures reste au centre.
    axes.set_xlim(0.95, 0.0)
    axes.set_ylim(0, theta_max)

    courbe = [
        (mu, temperature_critique(mu))
        for i in range(301)
        if (mu := MU_0_MINIMAL + i * (0.95 - MU_0_MINIMAL) / 300)
        and temperature_critique(mu) <= theta_max
    ]
    axes.plot(
        [c[0] for c in courbe], [c[1] for c in courbe],
        color=p.acier, linewidth=2.0, zorder=4,
    )

    # Le zéro du quadrant gauche tomberait sur celui du quadrant droit.
    axes.set_xticks([0.8, 0.6, 0.4, 0.2])
    axes.set_xlabel("μ₀  ·  degré d'utilisation", fontsize=9, color=p.encre_secondaire)
    axes.set_ylabel("Température [°C]", fontsize=9, color=p.encre_secondaire)

    placeur = Placeur(axes, p)
    placeur.eviter_courbe([c[0] for c in courbe], [c[1] for c in courbe])

    _chemin_gauche(axes, resultat, p, placeur)

    # L'étiquette de la courbe vient en dernier : elle est la moins
    # importante, et doit céder le passage au chemin de lecture.
    ancre = courbe[len(courbe) // 3]
    placeur.poser(
        EC3_THETA_CR.courte,
        xy=ancre,
        candidats=(
            (12, -12, "left", "top"),
            (12, 12, "left", "bottom"),
            (-12, -12, "right", "top"),
            (-12, 14, "right", "bottom"),
            (12, -34, "left", "top"),
            (-12, 34, "right", "bottom"),
        ),
        fontsize=8.5, color=p.acier,
    )


def _chemin_gauche(axes, resultat, p: Palette, placeur: Placeur) -> None:
    if resultat.theta_cr_nomogramme is None or resultat.mu_0 >= 1.0:
        return
    mu = resultat.mu_0
    theta = resultat.theta_cr_nomogramme

    axes.plot(
        [mu, mu, 0.0], [0.0, theta, theta],
        color=p.encre_secondaire, linewidth=1.2,
        linestyle=(0, (4, 3)), zorder=5, clip_on=False,
    )
    placeur.eviter_courbe([mu, mu, 0.0], [0.0, theta, theta])
    for x, y in ((mu, 0.0), (mu, theta)):
        axes.plot(
            [x], [y], marker="o", markersize=6, color=p.encre_secondaire,
            markeredgecolor=p.fond, markeredgewidth=2, zorder=6,
        )
    placeur.poser(
        f"μ₀ = {mu:.2f}", xy=(mu, 0.0),
        candidats=(
            (10, 12, "left", "bottom"),
            (-10, 12, "right", "bottom"),
            (10, 30, "left", "bottom"),
            (-10, 30, "right", "bottom"),
        ),
        fontsize=9, color=p.encre_secondaire,
    )

    # Quand la vérification croisée mord, le chemin de lecture entre dans
    # l'axe partagé à la température du nomogramme et en ressort plus bas. Ce
    # décrochement est le fait marquant de la figure : sans le tracer, il
    # passerait pour une erreur de tracé.
    exact = resultat.theta_cr_exact
    ecart = resultat.ecart_nomogramme
    if exact is None or ecart is None or ecart <= 5.0:
        return

    axes.axhline(
        exact, color=p.critique, linewidth=1.4,
        linestyle=(0, (6, 4)), zorder=5,
    )
    placeur.eviter_horizontale(exact)
    axes.annotate(
        "", xy=(0.0, exact), xytext=(0.0, theta),
        arrowprops={
            "arrowstyle": "-|>", "color": p.critique,
            "linewidth": 1.6, "shrinkA": 0, "shrinkB": 0,
        },
        annotation_clip=False, zorder=7,
    )
    placeur.poser(
        f"vérification croisée\n−{ecart:.0f} °C",
        xy=(0.0, 0.5 * (theta + exact)),
        candidats=(
            (-10, 0, "right", "center"),
            (-10, 16, "right", "bottom"),
            (-10, -16, "right", "top"),
            (-34, 0, "right", "center"),
        ),
        fontsize=8.5, color=p.critique, linespacing=1.35,
    )
    placeur.poser(
        f"{exact:.0f} °C retenus", xy=(0.0, exact),
        candidats=(
            (-10, -14, "right", "top"),
            (-10, 12, "right", "bottom"),
            (-10, -32, "right", "top"),
            (-60, -14, "right", "top"),
        ),
        fontsize=8.5, color=p.critique,
    )


def _quadrant_droit(
    axes, resultat, p: Palette, theta_max: float, duree_max: float
) -> None:
    """θ_a(t) : l'échauffement du cas traité, sous la courbe de feu retenue."""
    _habiller(axes, p)

    thermique = resultat.thermique
    instants = [en_minutes(t) for t in thermique.temps if t <= duree_max]
    acier = list(thermique.temperatures[: len(instants)])
    gaz = list(thermique.temperatures_gaz[: len(instants)])

    axes.plot(
        instants, gaz, color=p.gaz, linewidth=1.8, zorder=4,
        label=resultat.courbe.nom,
    )
    axes.plot(
        instants, acier, color=p.acier, linewidth=2.2, zorder=5,
        label=f"{resultat.profil.nom} · A_m/V = {resultat.Am_sur_V:.0f} m⁻¹",
    )

    axes.set_xlim(0, en_minutes(duree_max))
    axes.set_ylim(0, theta_max)
    axes.set_xlabel(
        "t  ·  durée d'exposition [min]", fontsize=9, color=p.encre_secondaire
    )
    axes.tick_params(labelleft=False, left=False)

    placeur = Placeur(axes, p)
    placeur.eviter_courbe(instants, gaz)
    placeur.eviter_courbe(instants, acier)

    # Le chemin de lecture d'abord : c'est lui qui porte le résultat, les
    # étiquettes de courbe s'écarteront s'il le faut.
    _echeance(axes, resultat, p, placeur)
    _chemin_droit(axes, resultat, p, placeur)

    # Étiquetage direct : le lecteur n'a pas à faire l'aller-retour vers la
    # légende pour savoir laquelle des deux courbes est l'acier.
    # Sur un élément nu les deux courbes se rejoignent en haut à droite : y
    # étiqueter les deux les ferait se chevaucher. Les gaz sont donc nommés
    # tôt, dans leur montée, où l'écart à l'acier est maximal ; l'acier l'est
    # là où il s'écarte le plus des gaz.
    indice_gaz = max(1, len(instants) // 10)
    placeur.poser(
        "gaz", xy=(instants[indice_gaz], gaz[indice_gaz]),
        candidats=(
            (6, -2, "left", "top"),
            (6, 6, "left", "bottom"),
            (-6, 6, "right", "bottom"),
            (10, -18, "left", "top"),
            (-10, 18, "right", "bottom"),
        ),
        fontsize=8.5, color=p.gaz,
    )
    indice_acier = max(
        range(len(acier)), key=lambda i: gaz[i] - acier[i]
    )
    placeur.poser(
        "acier", xy=(instants[indice_acier], acier[indice_acier]),
        candidats=(
            (4, -6, "left", "top"),
            (4, 8, "left", "bottom"),
            (-4, -6, "right", "top"),
            (-4, 8, "right", "bottom"),
            (8, -24, "left", "top"),
            (-8, 24, "right", "bottom"),
        ),
        fontsize=8.5, color=p.acier,
    )


def _echeance(axes, resultat, p: Palette, placeur: Placeur) -> None:
    echeance = en_minutes(resultat.duree_requise)
    if echeance > axes.get_xlim()[1]:
        return
    axes.axvline(
        echeance, color=p.encre_attenuee, linewidth=1.0,
        linestyle=(0, (2, 3)), zorder=3,
    )
    placeur.eviter_verticale(echeance)
    placeur.poser(
        f"R{echeance:.0f}", xy=(echeance, axes.get_ylim()[1]),
        candidats=(
            (4, -12, "left", "top"),
            (-4, -12, "right", "top"),
            (4, -28, "left", "top"),
            (-4, -28, "right", "top"),
        ),
        fontsize=8.5, color=p.encre_attenuee,
    )


def _chemin_droit(axes, resultat, p: Palette, placeur: Placeur) -> None:
    if resultat.t_fi_d_minutes is None:
        return
    theta = resultat.theta_cr
    instant = resultat.t_fi_d_minutes
    if instant > axes.get_xlim()[1]:
        return

    axes.plot(
        [0.0, instant, instant], [theta, theta, 0.0],
        color=p.encre_secondaire, linewidth=1.2,
        linestyle=(0, (4, 3)), zorder=5,
    )
    placeur.eviter_courbe([0.0, instant, instant], [theta, theta, 0.0])
    couleur = p.favorable if resultat.verdict else p.critique
    axes.plot(
        [instant], [theta], marker="o", markersize=7, color=couleur,
        markeredgecolor=p.fond, markeredgewidth=2, zorder=7,
    )
    # Au bord droit : à gauche, la montée des gaz occupe tout l'espace.
    placeur.poser(
        f"θ_cr = {theta:.0f} °C", xy=(axes.get_xlim()[1], theta),
        candidats=(
            (-6, 7, "right", "bottom"),
            (-6, -9, "right", "top"),
            (-6, 22, "right", "bottom"),
            (-6, -24, "right", "top"),
        ),
        fontsize=9, color=p.encre_secondaire,
    )
    # « t_fi,d » suit le point de lecture, qui peut tomber tout au bord droit :
    # le placeur y bascule le texte vers la gauche plutôt que de le laisser
    # sortir du cadre, où il serait tronqué à l'affichage.
    placeur.poser(
        f"t_fi,d = {instant:.0f} min", xy=(instant, 0.0),
        candidats=(
            (6, 10, "left", "bottom"),
            (-6, 10, "right", "bottom"),
            (6, 26, "left", "bottom"),
            (-6, 26, "right", "bottom"),
            (0, 42, "center", "bottom"),
        ),
        fontsize=9, color=couleur, fontweight="semibold",
    )


def tracer_abaque(
    profil: Profil,
    chemin: Path | str | None = None,
    theme: str | Palette = "clair",
    courbe: CourbeFeu = ISO834,
    protection: Protection | None = None,
    exposition: Exposition = Exposition.CONTOUR_4_FACES,
    duree_min: float = 120.0,
):
    """Trace le seul échauffement d'un profilé, sans vérification mécanique.

    Utile quand la température critique n'est pas encore connue.
    """
    plt = _pyplot()
    p = _palette(theme)

    trace = echauffement(
        profil=profil, exposition=exposition, duree=minutes(duree_min),
        courbe=courbe, protection=protection,
    )
    instants = [en_minutes(t) for t in trace.temps]

    figure, axes = plt.subplots(figsize=(8.2, 4.6), facecolor=p.fond)
    _habiller(axes, p)
    axes.plot(
        instants, trace.temperatures_gaz, color=p.gaz, linewidth=1.8,
        label=courbe.nom, zorder=3,
    )
    axes.plot(
        instants, trace.temperatures, color=p.acier, linewidth=2.2,
        label=f"{profil.nom}, A_m/V = {trace.Am_sur_V:.0f} m⁻¹", zorder=4,
    )
    axes.set_xlim(0, duree_min)
    axes.set_ylim(0, max(trace.temperatures_gaz) * 1.1)
    axes.set_xlabel("Durée d'exposition [min]", fontsize=9, color=p.encre_secondaire)
    axes.set_ylabel("Température [°C]", fontsize=9, color=p.encre_secondaire)
    axes.legend(loc="lower right", frameon=False, fontsize=8.5,
                labelcolor=p.encre_secondaire)
    axes.set_title(
        f"{profil.nom} — échauffement sous {courbe.nom}",
        fontsize=11, color=p.encre, loc="left", pad=10,
    )
    figure.tight_layout()
    return _enregistrer(figure, chemin, p)


# --- coupe d'une section soudée -----------------------------------------------


_CORPS_COTE = 8.0
"""Corps des textes de cote [pt]."""


def _cote_horizontale(axes, p: Palette, y0: float, y1: float, z: float, texte: str) -> None:
    """Une cote horizontale entre deux abscisses, texte au milieu."""
    axes.annotate(
        "", xy=(y0, z), xytext=(y1, z),
        arrowprops={"arrowstyle": "<|-|>", "color": p.encre_attenuee,
                    "linewidth": 0.8, "shrinkA": 0.0, "shrinkB": 0.0,
                    "mutation_scale": 8},
        annotation_clip=False, zorder=6,
    )
    axes.text(
        0.5 * (y0 + y1), z, texte, ha="center", va="center",
        fontsize=_CORPS_COTE, color=p.encre_secondaire, zorder=7,
        bbox={"facecolor": p.fond, "edgecolor": "none", "pad": 1.5},
    )


def _cote_verticale(axes, p: Palette, y: float, z0: float, z1: float, texte: str) -> None:
    """Une cote verticale entre deux ordonnées, texte tourné le long du trait."""
    axes.annotate(
        "", xy=(y, z0), xytext=(y, z1),
        arrowprops={"arrowstyle": "<|-|>", "color": p.encre_attenuee,
                    "linewidth": 0.8, "shrinkA": 0.0, "shrinkB": 0.0,
                    "mutation_scale": 8},
        annotation_clip=False, zorder=6,
    )
    axes.text(
        y, 0.5 * (z0 + z1), texte, ha="center", va="center", rotation=90,
        fontsize=_CORPS_COTE, color=p.encre_secondaire, zorder=7,
        bbox={"facecolor": p.fond, "edgecolor": "none", "pad": 1.5},
    )


_COLONNE_RENVOIS = 0.995
"""Abscisse de la colonne des épaisseurs, en fraction de l'axe."""


def _renvoi(axes, p: Palette, cible, texte: str) -> None:
    """Une ligne de renvoi vers une tôle, avec son épaisseur au bout.

    Les épaisseurs ne se cotent pas comme les dimensions hors tout : sur une
    âme de 10 mm dans une section de 600, la flèche et son texte seraient plus
    larges que la pièce cotée. Le renvoi les sort de l'encombrement.

    Le texte est aligné en **fraction d'axe** horizontalement et en données
    verticalement : tous les renvois forment ainsi une colonne, à droite,
    quelles que soient les proportions de la section. Un décalage en points
    typographiques ne le donnerait pas — sa longueur en millimètres dépend de
    l'échelle du dessin, qui change à chaque saisie.
    """
    axes.annotate(
        texte, xy=cible, xytext=(_COLONNE_RENVOIS, cible[1]),
        textcoords=("axes fraction", "data"),
        ha="right", va="center",
        fontsize=_CORPS_COTE, color=p.encre_secondaire, zorder=7,
        arrowprops={"arrowstyle": "-", "color": p.encre_attenuee,
                    "linewidth": 0.7, "shrinkA": 2.0, "shrinkB": 1.0},
        bbox={"facecolor": p.fond, "edgecolor": "none", "pad": 1.5},
        annotation_clip=False,
    )


def tracer_section(
    section: SectionSoudee,
    chemin: Path | str | None = None,
    theme: str | Palette = "clair",
    exposition: Exposition | None = None,
    titre: str | None = None,
):
    """Dessine une section soudée **à l'échelle**, cotée, avec sa face couverte.

    L'échelle est respectée — ``set_aspect("equal")`` — et c'est tout
    l'intérêt du dessin : une saisie fautive d'un facteur dix se voit d'un
    coup d'œil sur une coupe à l'échelle, et pas du tout dans un tableau de
    nombres. Les cotes sont en millimètres, comme la saisie.

    Chaque tôle est dessinée séparément, avec son contour : c'est ce qu'est
    une section reconstituée, et cela montre du même coup où passent les
    soudures.

    Quand ``exposition`` désigne une exposition sur trois faces, la dalle est
    figurée sur la semelle qu'elle recouvre, et le sous-titre dit laquelle.
    C'est le seul moyen de vérifier d'un regard qu'on protège bien la face
    qu'on croit : sur une section à semelles inégales, se tromper de face
    fausse le périmètre exposé, donc l'échauffement.
    """
    from matplotlib.patches import Rectangle

    plt = _pyplot()
    p = _palette(theme)

    profil = section.profil()
    plaques = section.plaques()
    carac = caracteristiques(plaques)

    h = section.h * 1e3
    b = section.b * 1e3
    z_g = carac.z_g * 1e3

    figure, axes = plt.subplots(figsize=(6.6, 5.8), facecolor=p.fond)
    axes.set_facecolor(p.fond)
    axes.set_aspect("equal", adjustable="box")
    axes.axis("off")

    # --- la dalle, quand il y en a une ------------------------------------
    couverte = exposition is not None and exposition.trois_faces
    face = getattr(section, "face_couverte", FaceCouverte.SUPERIEURE)
    en_haut = face is FaceCouverte.SUPERIEURE
    epaisseur_dalle = max(0.16 * h, 0.26 * b) if couverte else 0.0
    decalage_haut = epaisseur_dalle if couverte and en_haut else 0.0
    decalage_bas = epaisseur_dalle if couverte and not en_haut else 0.0

    if couverte:
        largeur_dalle = 1.5 * b
        base = h if en_haut else -epaisseur_dalle
        axes.add_patch(
            Rectangle(
                (-largeur_dalle / 2.0, base), largeur_dalle, epaisseur_dalle,
                facecolor="none", edgecolor=p.encre_attenuee, linewidth=1.0,
                hatch="///", zorder=2,
            )
        )
        axes.text(
            -largeur_dalle / 2.0 + 0.03 * b, base + epaisseur_dalle / 2.0,
            "dalle — face non exposée", ha="left", va="center",
            fontsize=_CORPS_COTE, color=p.encre_secondaire, zorder=3,
            bbox={"facecolor": p.fond, "edgecolor": "none", "pad": 2.0},
        )

    # --- les tôles ---------------------------------------------------------
    for plaque in plaques:
        axes.add_patch(
            Rectangle(
                ((plaque.y - plaque.largeur / 2.0) * 1e3,
                 (plaque.z - plaque.hauteur / 2.0) * 1e3),
                plaque.largeur * 1e3, plaque.hauteur * 1e3,
                facecolor=p.matiere, edgecolor=p.acier, linewidth=1.2, zorder=4,
            )
        )

    # --- axes principaux et centre de gravité -------------------------------
    axes.plot([-0.62 * b, 0.62 * b], [z_g, z_g], color=p.encre_attenuee,
              linewidth=0.8, linestyle=(0, (7, 3, 1, 3)), zorder=5)
    axes.plot([0.0, 0.0], [-0.08 * h, 1.08 * h], color=p.encre_attenuee,
              linewidth=0.8, linestyle=(0, (7, 3, 1, 3)), zorder=5)
    axes.plot([0.0], [z_g], marker="+", markersize=10, color=p.encre,
              markeredgewidth=1.4, zorder=8)
    axes.text(
        0.035 * b, z_g + 0.012 * h, "G", ha="left", va="bottom",
        fontsize=_CORPS_COTE, color=p.encre, zorder=8,
        bbox={"facecolor": p.fond, "edgecolor": "none", "pad": 1.0},
    )

    # --- cotes --------------------------------------------------------------
    #
    # Les dimensions hors tout à gauche, les épaisseurs à droite : les unes ne
    # peuvent alors plus croiser les autres, quelles que soient les
    # proportions de la section.
    _cote_verticale(axes, p, -0.82 * b, 0.0, h, f"h = {h:.0f}")
    ligne_b = -0.22 * h - decalage_bas
    _cote_horizontale(axes, p, -b / 2.0, b / 2.0, ligne_b, f"b = {b:.0f}")
    _coter_les_toles(axes, p, section, h, b, decalage_haut, decalage_bas)

    axes.set_xlim(-1.05 * b, 1.35 * b)
    axes.set_ylim(ligne_b - 0.10 * h, h + decalage_haut + 0.18 * h)

    # Le sous-titre fait trois lignes et monte depuis le haut de l'axe : la
    # marge du titre doit les laisser passer, sans quoi il les recouvre.
    axes.set_title(
        titre or profil.nom, fontsize=11, color=p.encre, loc="left", pad=52,
    )
    axes.annotate(
        _sous_titre_section(section, profil, exposition),
        xy=(0, 1), xycoords="axes fraction",
        xytext=(0, 8), textcoords="offset points",
        fontsize=8.0, color=p.encre_attenuee, linespacing=1.6,
    )
    figure.tight_layout()
    return _enregistrer(figure, chemin, p)


def _coter_les_toles(
    axes,
    p: Palette,
    section: SectionSoudee,
    h: float,
    b: float,
    decalage_haut: float,
    decalage_bas: float,
) -> None:
    """Épaisseurs, et largeurs de semelle quand elles diffèrent.

    Les deux formes ne se cotent pas de la même façon : un caisson n'a que
    deux épaisseurs à donner, un H en a trois et, quand ses semelles sont
    inégales, deux largeurs de plus. Écrire les deux cas séparément vaut mieux
    qu'un parcours générique des tôles, qui poserait sur le caisson deux cotes
    d'âme superposées.
    """
    if isinstance(section, SectionCaisson):
        _renvoi(axes, p, (0.0, (section.h - section.tf / 2.0) * 1e3),
                f"t_f = {section.tf * 1e3:.0f}")
        _renvoi(axes, p,
                ((section.b - section.tw) / 2.0 * 1e3, section.h * 1e3 / 2.0),
                f"t_w = {section.tw * 1e3:.0f}")
        return

    _renvoi(axes, p, (0.0, (section.h - section.tf_sup / 2.0) * 1e3),
            f"t_f,sup = {section.tf_sup * 1e3:.0f}")
    _renvoi(axes, p, (0.0, section.tf_inf * 1e3 / 2.0),
            f"t_f,inf = {section.tf_inf * 1e3:.0f}")
    _renvoi(axes, p,
            (section.tw * 1e3 / 2.0, (section.tf_inf + section.hw / 2.0) * 1e3),
            f"t_w = {section.tw * 1e3:.0f}")

    if section.symetrique:
        return
    # Semelles inégales : c'est la particularité de la section, elle se cote.
    _cote_horizontale(
        axes, p, -section.b_sup * 1e3 / 2.0, section.b_sup * 1e3 / 2.0,
        h + decalage_haut + 0.07 * h, f"b_sup = {section.b_sup * 1e3:.0f}",
    )
    _cote_horizontale(
        axes, p, -section.b_inf * 1e3 / 2.0, section.b_inf * 1e3 / 2.0,
        -decalage_bas - 0.09 * h, f"b_inf = {section.b_inf * 1e3:.0f}",
    )


def _sous_titre_section(
    section: SectionSoudee, profil: Profil, exposition: Exposition | None
) -> str:
    """Les grandeurs qu'on veut lire à côté du dessin, en deux ou trois lignes."""
    lignes = [
        f"A = {profil.A * 1e4:.1f} cm²  ·  I_y = {profil.Iy * 1e8:.0f} cm⁴  ·  "
        f"W_pl,y = {profil.Wply * 1e6:.0f} cm³  ·  {profil.masse:.0f} kg/m"
    ]
    if exposition is not None:
        detail = (
            f"{exposition.value}  ·  périmètre exposé "
            f"{perimetre_expose(profil, exposition) * 1e3:.0f} mm  ·  "
            f"A_m/V = {facteur_massivete(profil, exposition):.0f} m⁻¹"
        )
        if exposition.trois_faces:
            face = getattr(section, "face_couverte", FaceCouverte.SUPERIEURE)
            detail += f"  ·  dalle sur la {face.value}"
        lignes.append(detail)
    lignes.append(f"{EC3_MASSIVETE.courte}  ·  cotes en millimètres")
    return "\n".join(lignes)
