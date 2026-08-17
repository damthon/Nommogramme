"""Cadre normatif — ce qui change entre la pratique suisse et les Eurocodes.

Le moteur de calcul est commun : la SIA 263 renvoie à l'EN 1993-1-2 pour les
méthodes détaillées. Ce qui diffère relève de l'encadrement — combinaison
d'actions, facteurs partiels, valeurs conventionnelles — et se concentre donc
dans un objet unique que le reste du code reçoit en paramètre.

Deux jeux préconfigurés : ``SUISSE_SIA`` (par défaut) et ``EUROCODE_REC``, ce
qui permet de comparer les deux voies sur un même cas.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ContexteNormatif", "SUISSE_SIA", "EUROCODE_REC"]


@dataclass(frozen=True, slots=True)
class ContexteNormatif:
    """Paramètres dépendant du référentiel normatif retenu."""

    nom: str

    gamma_M_fi: float = 1.0
    """Facteur partiel en situation d'incendie [-].

    EN 1993-1-2 §2.3(1)P, valeur recommandée 1,0 — retenue aussi en Suisse.
    """

    gamma_M0: float = 1.0
    """Facteur partiel de résistance de section à froid [-]."""

    gamma_M1: float = 1.0
    """Facteur partiel de résistance à l'instabilité à froid [-].

    La SIA 263 retient 1,05 là où l'Eurocode recommande 1,00. Le passage à
    γ_M,fi = 1,0 en situation d'incendie apporte donc, en Suisse, 5 % de
    résistance supplémentaire — en plus de la baisse des charges.
    """

    psi_action_dominante: str = "psi_1"
    """Coefficient appliqué à l'action variable dominante.

    ``"psi_1"`` suit la recommandation de l'EN 1991-1-2 §4.3.1 ;
    ``"psi_2"`` suit la SIA 260, qui retient la valeur quasi permanente pour
    toutes les actions variables.
    """

    eta_fi_defaut: float = 0.65
    """Niveau de charge par défaut si les charges ne sont pas détaillées [-].

    EN 1993-1-2 §2.4.2(3). Vaut 0,70 pour les aires de stockage (catégorie E).
    """

    theta_cr_classe_4: float = 350.0
    """Température critique conventionnelle des sections de classe 4 [°C].

    EN 1993-1-2 annexe E, valeur recommandée. L'équation (4.22) ne s'applique
    pas à ces sections.
    """

    def __str__(self) -> str:
        return self.nom


SUISSE_SIA = ContexteNormatif(
    nom="Suisse — SIA 263 / SIA 260",
    gamma_M_fi=1.0,
    gamma_M0=1.05,
    gamma_M1=1.05,
    psi_action_dominante="psi_2",
    eta_fi_defaut=0.65,
    theta_cr_classe_4=350.0,
)
"""Pratique suisse : γ_M1 = 1,05 à froid, ψ₂ pour toutes les actions variables."""

EUROCODE_REC = ContexteNormatif(
    nom="Eurocode — valeurs recommandées",
    gamma_M_fi=1.0,
    gamma_M0=1.0,
    gamma_M1=1.0,
    psi_action_dominante="psi_1",
    eta_fi_defaut=0.65,
    theta_cr_classe_4=350.0,
)
"""Valeurs recommandées de l'EN, hors annexe nationale."""
