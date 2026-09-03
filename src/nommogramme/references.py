"""Registre des références normatives citées par l'outil.

Pourquoi un registre plutôt que des chaînes dispersées
------------------------------------------------------

Une équation citée « éq. (4.22) » ne se retrouve pas : il faut déjà savoir de
quelle norme elle vient, puis feuilleter jusqu'au bon chapitre. Une référence
utile porte les trois éléments — **norme, paragraphe, équation** — et elle les
porte partout de la même façon : à l'écran, dans les infobulles, dans la note
de calcul et dans les figures.

Les rassembler ici a une seconde raison, plus importante. Les clauses citées
dans ce projet proviennent de la connaissance du corpus normatif et **n'ont
pas toutes été recoupées avec un exemplaire officiel des normes**. Tant
qu'elles étaient éparpillées dans une vingtaine de fichiers, cette réserve
était invérifiable. Chaque référence porte désormais un drapeau
``confirmee`` ; ``python -m nommogramme.references`` liste ce qui reste à
contrôler, et ``docs/references.md`` en est la copie lisible.

Ce module ne contient aucun calcul et ne dépend d'aucun autre module du
paquet : il peut être importé de partout sans risque de cycle.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "Reference",
    "REFERENCES",
    "a_recouper",
]


@dataclass(frozen=True, slots=True)
class Reference:
    """Une clause normative, citable sous trois longueurs.

    >>> print(EC3_THETA_CR)
    EN 1993-1-2 §4.2.4, éq. (4.22)
    >>> print(EC3_THETA_CR.complete)
    EN 1993-1-2 §4.2.4, éq. (4.22) — température critique de l'acier
    """

    norme: str
    """Nom exact de la norme, par exemple ``"EN 1993-1-2"``."""
    clause: str
    """Numéro de paragraphe, avec son signe : ``"§4.2.4"``, ``"annexe E"``."""
    equation: str = ""
    """Numéro d'équation entre parenthèses, ``"(4.22)"``, ou vide."""
    objet: str = ""
    """Ce que la clause établit, en quelques mots."""
    confirmee: bool = True
    """La clause a-t-elle été recoupée avec un exemplaire officiel ?"""
    remarque: str = ""
    """Réserve ou précision, affichée dans les infobulles."""

    @property
    def courte(self) -> str:
        """« EN 1993-1-2 §4.2.4, éq. (4.22) » — pour un tableau ou une figure."""
        base = f"{self.norme} {self.clause}"
        return f"{base}, éq. {self.equation}" if self.equation else base

    @property
    def complete(self) -> str:
        """La forme courte, suivie de l'objet de la clause."""
        return f"{self.courte} — {self.objet}" if self.objet else self.courte

    def infobulle(self, entete: str = "") -> str:
        """Texte multiligne d'une infobulle : l'aide, puis la référence.

        ``entete`` porte l'explication du paramètre ; la référence vient
        ensuite, et la réserve en dernier s'il y en a une.
        """
        lignes = [entete.strip()] if entete.strip() else []
        lignes.append(self.courte)
        if self.remarque:
            lignes.append(self.remarque)
        if not self.confirmee:
            lignes.append("Référence à recouper avec l'exemplaire officiel.")
        return "\n".join(lignes)

    def __str__(self) -> str:
        return self.courte


# --- EN 1993-1-2 : calcul des structures en acier, situation d'incendie -------

EC3_GAMMA_M_FI = Reference(
    "EN 1993-1-2", "§2.3(1)P", objet="facteur partiel γ_M,fi en situation d'incendie"
)
EC3_ETA_FI = Reference(
    "EN 1993-1-2", "§2.4.2", "(2.5)", "niveau de charge η_fi"
)
EC3_TABLEAU_3_1 = Reference(
    "EN 1993-1-2", "§3.2.1, tab. 3.1", objet="facteurs de réduction k_y,θ, k_p,θ et k_E,θ"
)
EC3_EPSILON = Reference(
    "EN 1993-1-2", "§4.2.2", objet="coefficient ε = 0,85·√(235/f_y) à chaud"
)
EC3_TRACTION = Reference(
    "EN 1993-1-2", "§4.2.3.1", "(4.3)", "résistance à la traction"
)
EC3_FLAMBEMENT = Reference(
    "EN 1993-1-2", "§4.2.3.2", "(4.5)", "résistance au flambement par flexion"
)
EC3_CHI_FI = Reference(
    "EN 1993-1-2", "§4.2.3.2", "(4.6)", "coefficient de réduction χ_fi"
)
EC3_PHI_THETA = Reference(
    "EN 1993-1-2", "§4.2.3.2", "(4.7)", "terme φ_θ de la courbe de flambement"
)
EC3_ALPHA = Reference(
    "EN 1993-1-2", "§4.2.3.2", "(4.8)", "facteur d'imperfection α = 0,65·√(235/f_y)"
)
EC3_ELANCEMENT_THETA = Reference(
    "EN 1993-1-2", "§4.2.3.2", "(4.9)", "élancement réduit à chaud λ̄_θ"
)
EC3_LONGUEUR_FLAMBEMENT = Reference(
    "EN 1993-1-2",
    "§4.2.3.2(4)",
    objet="longueur de flambement d'un poteau continu d'un contreventement",
    remarque="0,5·L en étage courant, 0,7·L au dernier étage.",
)
EC3_MOMENT_SECTION = Reference(
    "EN 1993-1-2", "§4.2.3.3", objet="moment résistant de section en classes 1 et 2"
)
EC3_KAPPA = Reference(
    "EN 1993-1-2",
    "§4.2.3.3(7)",
    objet="facteurs d'adaptation κ₁ et κ₂ pour température non uniforme",
    confirmee=False,
    remarque=(
        "κ₁ = 1,00 quatre faces exposées · 0,70 poutre non protégée sur trois "
        "faces sous dalle · 0,85 poutre protégée sur trois faces sous dalle. "
        "κ₂ = 0,85 aux appuis d'une poutre hyperstatique, 1,00 sinon. "
        "La documentation SZS steeltec 02:2015 retient 0,70 dans ses exemples B "
        "et F, tous deux protégés : écart signalé dans docs/validation.md."
    ),
)
EC3_DEVERSEMENT = Reference(
    "EN 1993-1-2", "§4.2.3.3(4)", "(4.11)", "moment résistant au déversement"
)
EC3_CISAILLEMENT = Reference(
    "EN 1993-1-2", "§4.2.3.3(6)", objet="résistance à l'effort tranchant"
)
EC3_INTERACTION_FLAMBEMENT = Reference(
    "EN 1993-1-2", "§4.2.3.5", "(4.21a)", "interaction N + M, flambement par flexion"
)
EC3_INTERACTION_DEVERSEMENT = Reference(
    "EN 1993-1-2", "§4.2.3.5", "(4.21b)", "interaction N + M, déversement"
)
EC3_FACTEURS_INTERACTION = Reference(
    "EN 1993-1-2",
    "§4.2.3.5",
    objet="facteurs d'interaction k_y, k_z, k_LT et μ_y, μ_z, μ_LT",
    confirmee=False,
    remarque="La numérotation exacte de ces six expressions reste à confirmer.",
)
EC3_BETA_M = Reference(
    "EN 1993-1-2",
    "fig. 4.2",
    objet="facteur de moment uniforme équivalent β_M",
    remarque=(
        "1,3 moment de charge répartie · 1,4 moment de charge concentrée · "
        "1,8 − 0,7·ψ diagramme linéaire, ψ étant le rapport des moments "
        "d'extrémité, de −1 (double courbure) à +1 (moment constant)."
    ),
)
EC3_THETA_CR = Reference(
    "EN 1993-1-2", "§4.2.4", "(4.22)", "température critique de l'acier"
)
EC3_MU_0 = Reference(
    "EN 1993-1-2", "§4.2.4", "(4.23)", "degré d'utilisation μ₀ à 20 °C"
)
EC3_RESISTANCES = Reference(
    "EN 1993-1-2",
    "§4.2.3",
    objet="résistances complètes à chaud — la vérification croisée",
    remarque=(
        "Température à laquelle le taux d'utilisation complet atteint 1, "
        "χ_fi et interaction N + M compris. Contrairement à l'éq. (4.22), "
        "elle voit la chute du module et donc l'instabilité."
    ),
)
EC3_CLASSE_4 = Reference(
    "EN 1993-1-2", "annexe E", objet="température critique conventionnelle de classe 4"
)
EC3_MASSIVETE = Reference(
    "EN 1993-1-2",
    "§4.2.5.1, tab. 4.2 et 4.3",
    objet="facteur de massiveté A_m/V et périmètres exposés",
)
EC3_ECHAUFFEMENT_NU = Reference(
    "EN 1993-1-2", "§4.2.5.1", "(4.25)", "échauffement d'un élément non protégé"
)
EC3_OMBRE = Reference(
    "EN 1993-1-2", "§4.2.5.1", "(4.26a) et (4.26b)", "facteur d'ombre k_sh"
)
EC3_ECHAUFFEMENT_PROTEGE = Reference(
    "EN 1993-1-2", "§4.2.5.2", "(4.27)", "échauffement d'un élément protégé"
)
EC3_PHI_PROTECTION = Reference(
    "EN 1993-1-2", "§4.2.5.2", "(4.28)", "rapport des capacités thermiques φ"
)

# --- EN 1991-1-2 : actions sur les structures exposées au feu -----------------

EC1_COURBES = Reference(
    "EN 1991-1-2", "§3.2", objet="courbes de feu nominales ISO 834, hydrocarbure, extérieur"
)
EC1_COMBINAISON = Reference(
    "EN 1991-1-2", "§4.3.1", objet="combinaison d'actions en situation d'incendie"
)

# --- EN 1993-1-1 : règles générales, à froid ----------------------------------

EC3_1_1_CLASSES = Reference(
    "EN 1993-1-1", "§5.5.2, tab. 5.2", objet="élancements limites de parois, classes 1 à 4"
)
EC3_1_1_CISAILLEMENT = Reference(
    "EN 1993-1-1", "§6.2.6", objet="aire de cisaillement A_v"
)

# --- hors Eurocodes -----------------------------------------------------------

MCR_C1 = Reference(
    "ENV 1993-1-1",
    "annexe F",
    objet="moment critique élastique de déversement et facteur C₁",
    confirmee=False,
    remarque=(
        "Ni l'EN 1993-1-1:2005 ni l'EN 1993-1-2 ne donnent M_cr : la formule "
        "vient de l'ENV, reprise par le NCCI SN003a-FR. Valeurs usuelles de "
        "C₁ : 1,00 moment constant · 1,13 charge répartie · 1,35 charge "
        "concentrée à mi-portée · 1,88 double courbure symétrique."
    ),
)
SIA_263 = Reference(
    "SIA 263",
    "chapitre « Résistance au feu »",
    objet="cadre suisse — renvoi à l'EN 1993-1-2 pour les méthodes détaillées",
    confirmee=False,
    remarque=(
        "La SIA 263 ne redonne pas les équations : elle renvoie à "
        "l'EN 1993-1-2, dont toutes les clauses citées ici proviennent. Le "
        "numéro de chiffre SIA n'a pas été recoupé."
    ),
)
SIA_260 = Reference(
    "SIA 260",
    "situations de projet accidentelles",
    objet="combinaison d'actions, ψ₂ pour toutes les actions variables",
    confirmee=False,
    remarque="Le numéro de chiffre SIA n'a pas été recoupé.",
)
SZS_C5 = Reference(
    "SZS C5/05",
    "tables de construction",
    objet="catalogue de profilés laminés",
)


REFERENCES: dict[str, Reference] = {
    nom: valeur
    for nom, valeur in list(globals().items())
    if isinstance(valeur, Reference)
}
"""Toutes les références du module, indexées par leur nom de constante."""


def a_recouper() -> list[Reference]:
    """Les références qui n'ont pas encore été confrontées à un exemplaire.

    >>> all(not r.confirmee for r in a_recouper())
    True
    """
    return [r for r in REFERENCES.values() if not r.confirmee]


def _lister() -> None:  # pragma: no cover - utilitaire de mise au point
    """Affiche le registre, les clauses à recouper en dernier."""
    for reference in sorted(REFERENCES.values(), key=lambda r: (not r.confirmee, r.norme)):
        marque = " " if reference.confirmee else "?"
        print(f"[{marque}] {reference.complete}")
    restantes = a_recouper()
    print(f"\n{len(REFERENCES)} références, dont {len(restantes)} à recouper.")


if __name__ == "__main__":  # pragma: no cover
    _lister()
