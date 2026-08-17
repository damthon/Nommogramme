"""Vérification complète de la résistance au feu d'un élément.

Assemble les deux voies décrites au §4 du plan de conception :

* voie mécanique — degré d'utilisation μ₀, puis température critique par
  l'équation (4.22) ;
* voie thermique — évolution θ_a(t) sous la courbe de feu retenue.

Le verdict compare la durée avant d'atteindre θ_cr à la durée exigée.

La température critique de l'équation (4.22) est doublée d'une **vérification
croisée** : la température à laquelle le taux d'utilisation complet, avec
χ_fi et l'interaction N + M, atteint 1,0. Les deux ne coïncident que si la
ruine est gouvernée par la résistance de section ; dès que le flambement pèse,
l'équation (4.22) surestime la température admissible. La plus défavorable
des deux est retenue.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..contexte import SUISSE_SIA, ContexteNormatif
from ..materiaux.acier import Nuance, limite_elasticite
from ..materiaux.protection import Protection
from ..mecanique.actions import CasDeCharge
from ..mecanique.classification import ClassificationSection, classifier
from ..mecanique.interaction import TauxUtilisation, taux
from ..mecanique.resistances import (
    elancement_reduit,
    elancement_reduit_LT,
    resistances_a,
)
from ..profils.geometrie import Exposition, facteur_massivete
from ..profils.modele import Profil
from ..thermique.courbes import ISO834, CourbeFeu
from ..thermique.evolution import ResultatThermique, echauffement
from ..unites import en_minutes, minutes
from .temperature_critique import MU_0_MINIMAL, temperature_critique

__all__ = ["Verdict", "ResultatVerification", "verifier"]


_THETA_AMBIANTE = 20.0
_THETA_MAX = 1200.0
_TOLERANCE_BISSECTION = 0.05
_ITERATIONS_MAX = 200


class Verdict(str, Enum):
    SATISFAIT = "satisfait"
    NON_SATISFAIT = "non satisfait"

    def __bool__(self) -> bool:
        return self is Verdict.SATISFAIT


@dataclass(frozen=True, slots=True)
class ResultatVerification:
    """Résultat complet, avec tous les intermédiaires pour la traçabilité."""

    profil: Profil
    nuance: Nuance
    cas: CasDeCharge
    exposition: Exposition
    protection: Protection | None
    courbe: CourbeFeu
    contexte: ContexteNormatif
    duree_requise: float
    """Durée exigée [s]."""

    classification: ClassificationSection
    mu_0: float
    """Degré d'utilisation à 20 °C [-]. EN 1993-1-2 éq. (4.23)."""
    utilisation_initiale: TauxUtilisation

    theta_cr: float
    """Température critique retenue [°C], la plus défavorable des deux."""
    theta_cr_nomogramme: float | None
    """Température critique de l'éq. (4.22) [°C]. ``None`` en classe 4."""
    theta_cr_exact: float | None
    """Température annulant la marge du taux complet [°C]."""
    source_theta_cr: str

    thermique: ResultatThermique
    theta_a_a_echeance: float
    """Température de l'acier à la durée exigée [°C]."""
    t_fi_d: float | None
    """Durée avant d'atteindre θ_cr [s]. ``None`` si non atteinte."""

    verdict: Verdict
    gouverne_par: str
    avertissements: tuple[str, ...] = field(default=())

    @property
    def Am_sur_V(self) -> float:
        return self.thermique.Am_sur_V

    @property
    def k_sh(self) -> float:
        return self.thermique.k_sh

    @property
    def t_fi_d_minutes(self) -> float | None:
        return None if self.t_fi_d is None else en_minutes(self.t_fi_d)

    @property
    def marge_temperature(self) -> float:
        """θ_cr − θ_a à l'échéance [°C]. Positive si l'élément tient."""
        return self.theta_cr - self.theta_a_a_echeance

    def note_de_calcul(self) -> str:
        """Note de calcul détaillée au format Markdown."""
        from ..rapport import note_de_calcul

        return note_de_calcul(self)

    @property
    def ecart_nomogramme(self) -> float | None:
        """θ_cr,nomogramme − θ_cr,exact [°C].

        Positif quand l'équation (4.22) est optimiste, ce qui arrive dès que
        le flambement gouverne.
        """
        if self.theta_cr_nomogramme is None or self.theta_cr_exact is None:
            return None
        return self.theta_cr_nomogramme - self.theta_cr_exact

    def __str__(self) -> str:
        duree = (
            f"{self.t_fi_d_minutes:.1f} min"
            if self.t_fi_d_minutes is not None
            else f"> {en_minutes(self.thermique.duree):.0f} min"
        )
        return (
            f"{self.profil.nom} — μ₀ = {self.mu_0:.3f}, "
            f"θ_cr = {self.theta_cr:.0f} °C, t_fi,d = {duree} : "
            f"{self.verdict.value} pour R{en_minutes(self.duree_requise):.0f}"
        )


def _elancements(profil: Profil, nuance: Nuance, cas: CasDeCharge, C1: float):
    fy = limite_elasticite(nuance, profil.tf)
    lambda_y = (
        elancement_reduit(cas.longueur_flambement_y(), profil.iy, fy)
        if cas.longueur_flambement_y() > 0.0
        else 0.0
    )
    lambda_z = (
        elancement_reduit(cas.longueur_flambement_z(), profil.iz, fy)
        if cas.longueur_flambement_z() > 0.0
        else 0.0
    )
    lambda_LT = (
        elancement_reduit_LT(profil, fy, cas.longueur_deversement(), C1)
        if cas.longueur_deversement() > 0.0 and cas.My_fi_Ed > 0.0
        else 0.0
    )
    return fy, lambda_y, lambda_z, lambda_LT


def _taux_a(
    theta: float,
    profil: Profil,
    nuance: Nuance,
    cas: CasDeCharge,
    contexte: ContexteNormatif,
    lambda_y: float,
    lambda_z: float,
    lambda_LT: float,
    classe: ClassificationSection,
    kappa_1: float,
    kappa_2: float,
) -> TauxUtilisation:
    """Taux d'utilisation de l'élément à la température θ."""
    module_y = profil.Wply if classe.plastique else profil.Wely
    module_z = profil.Wplz if classe.plastique else profil.Welz

    resistances = resistances_a(
        profil=profil,
        nuance=nuance,
        theta=theta,
        lambda_y=lambda_y,
        lambda_z=lambda_z,
        lambda_LT=lambda_LT,
        gamma_M_fi=contexte.gamma_M_fi,
        comprime=cas.comprime,
        kappa_1=kappa_1,
        kappa_2=kappa_2,
        module_y=module_y,
        module_z=module_z,
    )
    return taux(
        N_Ed=cas.N_fi_Ed,
        My_Ed=cas.My_fi_Ed,
        Mz_Ed=cas.Mz_fi_Ed,
        resistances=resistances,
        aire=profil.A,
        beta_M_y=cas.beta_M_y,
        beta_M_z=cas.beta_M_z,
        beta_M_LT=cas.beta_M_LT,
        deversement_possible=not cas.maintien_lateral,
    )


def _temperature_critique_exacte(evaluer, mu_0: float) -> float | None:
    """Température annulant la marge du taux d'utilisation complet [°C].

    Le taux croît de façon monotone avec la température ; la dichotomie
    converge donc sans ambiguïté. Renvoie ``None`` si l'élément ne tient déjà
    pas à 20 °C.
    """
    if mu_0 >= 1.0:
        return None
    if evaluer(_THETA_MAX) <= 1.0:
        return _THETA_MAX

    bas, haut = _THETA_AMBIANTE, _THETA_MAX
    for _ in range(_ITERATIONS_MAX):
        milieu = 0.5 * (bas + haut)
        if evaluer(milieu) > 1.0:
            haut = milieu
        else:
            bas = milieu
        if haut - bas < _TOLERANCE_BISSECTION:
            break
    return 0.5 * (bas + haut)


def verifier(
    profil: Profil,
    nuance: Nuance,
    cas: CasDeCharge,
    exposition: Exposition,
    duree_requise_min: float,
    protection: Protection | None = None,
    courbe: CourbeFeu = ISO834,
    contexte: ContexteNormatif = SUISSE_SIA,
    kappa_1: float = 1.0,
    kappa_2: float = 1.0,
    C1: float = 1.0,
    duree_simulee_min: float | None = None,
) -> ResultatVerification:
    """Vérifie la résistance au feu d'un élément sollicité en N + M.

    ``duree_requise_min`` est la durée exigée en minutes (30 pour R30, etc.).
    ``kappa_1`` et ``kappa_2`` sont les facteurs d'adaptation de flexion du
    §4.2.3.3, ``C1`` le facteur de forme du diagramme de moment pour le calcul
    du moment critique de déversement.
    """
    avertissements: list[str] = []
    duree_requise = minutes(duree_requise_min)
    duree_simulee = minutes(
        duree_simulee_min if duree_simulee_min is not None else max(duree_requise_min * 2, 240)
    )

    fy, lambda_y, lambda_z, lambda_LT = _elancements(profil, nuance, cas, C1)
    classe = classifier(profil, fy, N_Ed=cas.N_fi_Ed, My_Ed=cas.My_fi_Ed)

    def evaluer(theta: float) -> float:
        return _taux_a(
            theta, profil, nuance, cas, contexte,
            lambda_y, lambda_z, lambda_LT, classe, kappa_1, kappa_2,
        ).valeur

    utilisation_initiale = _taux_a(
        _THETA_AMBIANTE, profil, nuance, cas, contexte,
        lambda_y, lambda_z, lambda_LT, classe, kappa_1, kappa_2,
    )
    mu_0 = utilisation_initiale.valeur

    if mu_0 >= 1.0:
        avertissements.append(
            f"μ₀ = {mu_0:.3f} ≥ 1 : l'élément ne tient pas à 20 °C sous les charges "
            "d'incendie. Vérifier le chargement et les conditions d'appui."
        )

    # --- température critique, deux voies ------------------------------------
    theta_cr_nomogramme: float | None = None
    if classe.elancee:
        theta_cr_nomogramme = None
        avertissements.append(
            f"Section de {classe} à chaud : l'éq. (4.22) ne s'applique pas. "
            f"Température conventionnelle de {contexte.theta_cr_classe_4:.0f} °C "
            "retenue (EN 1993-1-2 annexe E)."
        )
    elif MU_0_MINIMAL <= mu_0 < 1.0:
        theta_cr_nomogramme = temperature_critique(mu_0)
    elif mu_0 < MU_0_MINIMAL:
        avertissements.append(
            f"μ₀ = {mu_0:.4f} sous la borne de validité de l'éq. (4.22) : "
            "élément très peu sollicité, la vérification croisée fait foi."
        )

    theta_cr_exact = _temperature_critique_exacte(evaluer, mu_0)

    candidats: list[tuple[float, str]] = []
    if classe.elancee:
        candidats.append((contexte.theta_cr_classe_4, "classe 4 — annexe E"))
    else:
        if theta_cr_nomogramme is not None:
            candidats.append((theta_cr_nomogramme, "éq. (4.22) — nomogramme"))
        if theta_cr_exact is not None:
            candidats.append((theta_cr_exact, "vérification croisée §4.2.3"))

    if not candidats:
        theta_cr, source = _THETA_AMBIANTE, "élément déjà en ruine à 20 °C"
    else:
        theta_cr, source = min(candidats, key=lambda couple: couple[0])

    if theta_cr_nomogramme is not None and theta_cr_exact is not None:
        ecart = theta_cr_nomogramme - theta_cr_exact
        if ecart > 10.0:
            avertissements.append(
                f"L'éq. (4.22) donne {theta_cr_nomogramme:.0f} °C contre "
                f"{theta_cr_exact:.0f} °C par la vérification croisée, soit "
                f"{ecart:.0f} °C d'écart : l'instabilité gouverne et le "
                "nomogramme seul serait non conservatif."
            )

    # --- voie thermique -------------------------------------------------------
    thermique = echauffement(
        profil=profil,
        exposition=exposition,
        duree=duree_simulee,
        courbe=courbe,
        protection=protection,
    )
    avertissements.extend(thermique.avertissements)

    theta_a_echeance = thermique.temperature_a(duree_requise)
    t_fi_d = thermique.temps_pour_atteindre(theta_cr)

    satisfait = theta_a_echeance <= theta_cr and mu_0 < 1.0
    verdict = Verdict.SATISFAIT if satisfait else Verdict.NON_SATISFAIT

    return ResultatVerification(
        profil=profil,
        nuance=nuance,
        cas=cas,
        exposition=exposition,
        protection=protection,
        courbe=courbe,
        contexte=contexte,
        duree_requise=duree_requise,
        classification=classe,
        mu_0=mu_0,
        utilisation_initiale=utilisation_initiale,
        theta_cr=theta_cr,
        theta_cr_nomogramme=theta_cr_nomogramme,
        theta_cr_exact=theta_cr_exact,
        source_theta_cr=source,
        thermique=thermique,
        theta_a_a_echeance=theta_a_echeance,
        t_fi_d=t_fi_d,
        verdict=verdict,
        gouverne_par=utilisation_initiale.critere,
        avertissements=tuple(avertissements),
    )
