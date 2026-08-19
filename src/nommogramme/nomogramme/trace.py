"""Tracés : le nomogramme et la courbe d'échauffement.

Deux figures, pour deux usages :

* ``tracer_nomogramme`` reproduit l'instrument graphique du §11 du plan de
  conception — deux quadrants partageant l'axe des températures, et le chemin
  de lecture du cas traité ;
* ``tracer_echauffement`` montre θ_a(t) confrontée à la température critique,
  ce qui se lit plus vite pour juger d'une marge.

``matplotlib`` est une dépendance facultative : ``pip install
'nommogramme[trace]'``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..materiaux.protection import Protection
from ..profils.geometrie import Exposition
from ..profils.modele import Profil
from ..thermique.courbes import ISO834, CourbeFeu
from ..thermique.evolution import echauffement
from ..unites import en_minutes, minutes
from .temperature_critique import MU_0_MINIMAL, temperature_critique
from .verification import ResultatVerification

__all__ = ["Palette", "CLAIR", "SOMBRE", "tracer_nomogramme", "tracer_echauffement"]


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
    axes.annotate(
        f"θ_cr = {resultat.theta_cr:.0f} °C",
        xy=(instants[-1], resultat.theta_cr),
        xytext=(-6, 7), textcoords="offset points",
        ha="right", va="bottom", fontsize=8.5, color=p.encre_secondaire,
    )

    echeance = en_minutes(resultat.duree_requise)
    if echeance <= instants[-1]:
        axes.axvline(
            echeance, color=p.encre_attenuee, linewidth=1.0,
            linestyle=(0, (2, 3)), zorder=2,
        )
        axes.annotate(
            f"R{echeance:.0f}",
            xy=(echeance, axes.get_ylim()[1]),
            xytext=(4, -12), textcoords="offset points",
            fontsize=8.5, color=p.encre_attenuee,
        )

    # Le verdict se lit à l'échéance, pas au croisement : sur un élément
    # confortablement satisfait, le croisement tombe hors fenêtre et la figure
    # resterait sans repère.
    couleur = p.favorable if resultat.verdict else p.critique
    if echeance <= instants[-1]:
        axes.plot(
            [echeance], [resultat.theta_a_a_echeance],
            marker="o", markersize=8, color=couleur,
            markeredgecolor=p.fond, markeredgewidth=2, zorder=6,
        )
        axes.annotate(
            f"{resultat.theta_a_a_echeance:.0f} °C à R{echeance:.0f}"
            f"  ·  marge {resultat.marge_temperature:+.0f} °C",
            xy=(echeance, resultat.theta_a_a_echeance),
            xytext=(10, -6), textcoords="offset points",
            va="top", fontsize=9, color=couleur, fontweight="semibold",
        )

    if resultat.t_fi_d_minutes is not None and resultat.t_fi_d_minutes <= instants[-1]:
        axes.annotate(
            f"t_fi,d = {resultat.t_fi_d_minutes:.0f} min",
            xy=(resultat.t_fi_d_minutes, resultat.theta_cr),
            xytext=(6, 10), textcoords="offset points",
            ha="left", va="bottom", fontsize=8.5, color=p.encre_secondaire,
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

    figure.tight_layout()
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

    Quadrant gauche : la relation μ₀ → θ_a,cr de l'équation (4.22). Quadrant
    droit : l'échauffement de l'élément sous la courbe de feu retenue. Les
    deux quadrants partagent l'axe vertical des températures, qui matérialise
    le couplage : c'est par lui que la voie mécanique et la voie thermique se
    rejoignent.

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
        bbox_to_anchor=(0.5, -0.04),
    )

    figure.suptitle(
        _titre(resultat), fontsize=11.5, color=p.encre, x=0.02, ha="left", y=1.06
    )
    figure.text(
        0.02, 1.005, _sous_titre(resultat),
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
    # Sous la courbe : au-dessus et de part et d'autre, elle passe trop près.
    axes.annotate(
        "éq. (4.22)", xy=courbe[len(courbe) // 3],
        xytext=(12, -12), textcoords="offset points",
        ha="left", va="top", fontsize=8.5, color=p.acier,
    )

    # Le zéro du quadrant gauche tomberait sur celui du quadrant droit.
    axes.set_xticks([0.8, 0.6, 0.4, 0.2])
    axes.set_xlabel("μ₀  ·  degré d'utilisation", fontsize=9, color=p.encre_secondaire)
    axes.set_ylabel("Température [°C]", fontsize=9, color=p.encre_secondaire)

    _chemin_gauche(axes, resultat, p)


def _chemin_gauche(axes, resultat, p: Palette) -> None:
    if resultat.theta_cr_nomogramme is None or resultat.mu_0 >= 1.0:
        return
    mu = resultat.mu_0
    theta = resultat.theta_cr_nomogramme

    axes.plot(
        [mu, mu, 0.0], [0.0, theta, theta],
        color=p.encre_secondaire, linewidth=1.2,
        linestyle=(0, (4, 3)), zorder=5, clip_on=False,
    )
    for x, y in ((mu, 0.0), (mu, theta)):
        axes.plot(
            [x], [y], marker="o", markersize=6, color=p.encre_secondaire,
            markeredgecolor=p.fond, markeredgewidth=2, zorder=6,
        )
    axes.annotate(
        f"μ₀ = {mu:.2f}", xy=(mu, 0.0),
        xytext=(10, 12), textcoords="offset points",
        ha="left", fontsize=9, color=p.encre_secondaire,
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
    axes.annotate(
        "", xy=(0.0, exact), xytext=(0.0, theta),
        arrowprops={
            "arrowstyle": "-|>", "color": p.critique,
            "linewidth": 1.6, "shrinkA": 0, "shrinkB": 0,
        },
        annotation_clip=False, zorder=7,
    )
    axes.annotate(
        f"vérification croisée\n−{ecart:.0f} °C",
        xy=(0.0, 0.5 * (theta + exact)),
        xytext=(-10, 0), textcoords="offset points",
        ha="right", va="center", fontsize=8.5, color=p.critique,
        linespacing=1.35,
    )
    axes.annotate(
        f"{exact:.0f} °C retenus", xy=(0.0, exact),
        xytext=(-10, -14), textcoords="offset points",
        ha="right", va="top", fontsize=8.5, color=p.critique,
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

    # Étiquetage direct : le lecteur n'a pas à faire l'aller-retour vers la
    # légende pour savoir laquelle des deux courbes est l'acier.
    # Sur un élément nu les deux courbes se rejoignent en haut à droite : y
    # étiqueter les deux les ferait se chevaucher. Les gaz sont donc nommés
    # tôt, dans leur montée, où l'écart à l'acier est maximal ; l'acier l'est
    # à son dernier point visible.
    indice_gaz = max(1, len(instants) // 10)
    axes.annotate(
        "gaz", xy=(instants[indice_gaz], gaz[indice_gaz]),
        xytext=(6, -2), textcoords="offset points",
        ha="left", va="top", fontsize=8.5, color=p.gaz,
    )
    # L'acier est nommé là où il s'écarte le plus des gaz : au bord droit pour
    # un élément protégé, à mi-montée pour un élément nu, dont les deux courbes
    # se rejoignent ensuite.
    indice_acier = max(
        range(len(acier)), key=lambda i: gaz[i] - acier[i]
    )
    axes.annotate(
        "acier", xy=(instants[indice_acier], acier[indice_acier]),
        xytext=(4, -6), textcoords="offset points",
        ha="left", va="top", fontsize=8.5, color=p.acier,
    )

    _echeance(axes, resultat, p)
    _chemin_droit(axes, resultat, p)


def _echeance(axes, resultat, p: Palette) -> None:
    echeance = en_minutes(resultat.duree_requise)
    if echeance > axes.get_xlim()[1]:
        return
    axes.axvline(
        echeance, color=p.encre_attenuee, linewidth=1.0,
        linestyle=(0, (2, 3)), zorder=3,
    )
    axes.annotate(
        f"R{echeance:.0f}", xy=(echeance, axes.get_ylim()[1]),
        xytext=(4, -12), textcoords="offset points",
        fontsize=8.5, color=p.encre_attenuee,
    )


def _chemin_droit(axes, resultat, p: Palette) -> None:
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
    couleur = p.favorable if resultat.verdict else p.critique
    axes.plot(
        [instant], [theta], marker="o", markersize=7, color=couleur,
        markeredgecolor=p.fond, markeredgewidth=2, zorder=7,
    )
    # Au bord droit : à gauche, la montée des gaz occupe tout l'espace.
    axes.annotate(
        f"θ_cr = {theta:.0f} °C", xy=(axes.get_xlim()[1], theta),
        xytext=(-6, 7), textcoords="offset points",
        ha="right", fontsize=9, color=p.encre_secondaire,
    )
    axes.annotate(
        f"t_fi,d = {instant:.0f} min", xy=(instant, 0.0),
        xytext=(6, 10), textcoords="offset points",
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
