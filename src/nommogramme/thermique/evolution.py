"""Évolution de la température de l'acier — diffusion de chaleur.

Référence : EN 1993-1-2 §4.2.5.

* §4.2.5.1, éq. (4.25) : acier non protégé, pas de temps ≤ 5 s ;
* §4.2.5.2, éq. (4.27) et (4.28) : acier protégé, pas de temps ≤ 30 s.

Les deux formulations sont des schémas d'Euler explicites, imposés par la
norme. La chaleur spécifique de l'acier étant fortement non linéaire — pic à
735 °C dû à la transformation de phase — elle est réévaluée à chaque pas.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field

from ..materiaux.acier import RHO_A, chaleur_specifique
from ..materiaux.protection import Protection
from ..profils.geometrie import (
    AM_SUR_V_MINIMAL,
    Exposition,
    facteur_massivete,
    facteur_ombre,
)
from ..profils.modele import Profil
from ..unites import en_minutes
from .courbes import ISO834, TEMPERATURE_INITIALE, CourbeFeu
from .flux import EPSILON_ACIER_CARBONE, EPSILON_FEU, PHI_DEFAUT, flux_net

__all__ = [
    "DT_NON_PROTEGE",
    "DT_PROTEGE",
    "DT_MAX_NON_PROTEGE",
    "DT_MAX_PROTEGE",
    "ResultatThermique",
    "echauffement",
]


DT_MAX_NON_PROTEGE = 5.0
"""Pas de temps maximal pour l'éq. (4.25) [s]. EN 1993-1-2 §4.2.5.1(4)."""

DT_MAX_PROTEGE = 30.0
"""Pas de temps maximal pour l'éq. (4.27) [s]. EN 1993-1-2 §4.2.5.2(2)."""

DT_NON_PROTEGE = 2.0
"""Pas retenu par défaut pour l'acier nu [s] — marge sur la borne normative."""

DT_PROTEGE = 5.0
"""Pas retenu par défaut pour l'acier protégé [s]."""


@dataclass(frozen=True, slots=True)
class ResultatThermique:
    """Historique température-temps de l'acier, et son contexte de calcul."""

    temps: tuple[float, ...]
    """Instants [s], croissants, à pas constant."""
    temperatures: tuple[float, ...]
    """Températures de l'acier [°C], au même indice que ``temps``."""
    temperatures_gaz: tuple[float, ...]
    """Températures des gaz [°C], au même indice."""

    profil: Profil
    exposition: Exposition
    courbe: CourbeFeu
    protection: Protection | None

    Am_sur_V: float
    """Facteur de massiveté retenu [m⁻¹]."""
    k_sh: float
    """Facteur d'ombre appliqué [-]. Vaut 1 pour un élément protégé."""
    phi: float | None = None
    """Paramètre φ de l'éq. (4.28) [-], pour un élément protégé."""

    avertissements: tuple[str, ...] = field(default=())

    @property
    def protege(self) -> bool:
        return self.protection is not None

    @property
    def temperature_finale(self) -> float:
        return self.temperatures[-1]

    @property
    def duree(self) -> float:
        """Durée simulée [s]."""
        return self.temps[-1]

    def temperature_a(self, t: float) -> float:
        """Température de l'acier [°C] à l'instant ``t`` [s], par interpolation.

        Saturée aux bornes de la simulation.
        """
        if t <= self.temps[0]:
            return self.temperatures[0]
        if t >= self.temps[-1]:
            return self.temperatures[-1]

        indice = bisect_left(self.temps, t)
        t0, t1 = self.temps[indice - 1], self.temps[indice]
        v0, v1 = self.temperatures[indice - 1], self.temperatures[indice]
        return v0 + (v1 - v0) * (t - t0) / (t1 - t0)

    def temperature_a_minute(self, minute: float) -> float:
        """Température de l'acier [°C] à l'instant donné [min]."""
        return self.temperature_a(minute * 60.0)

    def temps_pour_atteindre(self, theta_cible: float) -> float | None:
        """Premier instant [s] où l'acier atteint ``theta_cible`` [°C].

        Renvoie ``None`` si la température n'est pas atteinte dans la durée
        simulée — ce qui, pour une vérification, signifie que l'élément tient
        au moins cette durée.
        """
        for indice in range(1, len(self.temperatures)):
            precedente = self.temperatures[indice - 1]
            courante = self.temperatures[indice]
            if precedente < theta_cible <= courante:
                t0, t1 = self.temps[indice - 1], self.temps[indice]
                if courante == precedente:
                    return t1
                return t0 + (t1 - t0) * (theta_cible - precedente) / (
                    courante - precedente
                )
        if self.temperatures[0] >= theta_cible:
            return self.temps[0]
        return None

    def minutes_pour_atteindre(self, theta_cible: float) -> float | None:
        """Idem, exprimé en minutes."""
        instant = self.temps_pour_atteindre(theta_cible)
        return None if instant is None else en_minutes(instant)

    def echantillons(self, pas_minutes: float = 5.0) -> list[tuple[float, float]]:
        """Couples (minute, température) à intervalle régulier, pour affichage."""
        sortie: list[tuple[float, float]] = []
        minute = 0.0
        limite = en_minutes(self.duree)
        while minute <= limite + 1e-9:
            sortie.append((minute, self.temperature_a_minute(minute)))
            minute += pas_minutes
        return sortie


def echauffement(
    profil: Profil,
    exposition: Exposition,
    duree: float,
    courbe: CourbeFeu = ISO834,
    protection: Protection | None = None,
    dt: float | None = None,
    epsilon_m: float = EPSILON_ACIER_CARBONE,
    epsilon_f: float = EPSILON_FEU,
    phi_forme: float = PHI_DEFAUT,
    delai_evaporation: float | None = None,
) -> ResultatThermique:
    """Calcule l'échauffement de l'acier sur ``duree`` secondes.

    Aiguille vers l'éq. (4.25) ou l'éq. (4.27) selon qu'une protection est
    fournie. ``dt`` vaut par défaut 2 s sans protection et 5 s avec, dans les
    deux cas en deçà de la borne normative.
    """
    if duree <= 0.0:
        raise ValueError(f"Durée non positive : {duree} s")

    avertissements: list[str] = []

    Am_sur_V = facteur_massivete(profil, exposition)
    if Am_sur_V < AM_SUR_V_MINIMAL:
        avertissements.append(
            f"A_m/V = {Am_sur_V:.1f} m⁻¹ est sous la borne de validité de "
            f"{AM_SUR_V_MINIMAL:.0f} m⁻¹ de la méthode simplifiée "
            f"(EN 1993-1-2 §4.2.5.1(1))."
        )
    elif Am_sur_V < 15.0:
        avertissements.append(
            f"A_m/V = {Am_sur_V:.1f} m⁻¹ est proche de la borne de validité de "
            f"{AM_SUR_V_MINIMAL:.0f} m⁻¹ ; résultat à confirmer par un calcul détaillé."
        )

    if protection is None:
        return _non_protege(
            profil=profil,
            exposition=exposition,
            duree=duree,
            courbe=courbe,
            dt=dt if dt is not None else DT_NON_PROTEGE,
            Am_sur_V=Am_sur_V,
            epsilon_m=epsilon_m,
            epsilon_f=epsilon_f,
            phi_forme=phi_forme,
            avertissements=avertissements,
        )

    return _protege(
        profil=profil,
        exposition=exposition,
        duree=duree,
        courbe=courbe,
        protection=protection,
        dt=dt if dt is not None else DT_PROTEGE,
        Ap_sur_V=Am_sur_V,
        delai_evaporation=delai_evaporation,
        avertissements=avertissements,
    )


def _non_protege(
    *,
    profil: Profil,
    exposition: Exposition,
    duree: float,
    courbe: CourbeFeu,
    dt: float,
    Am_sur_V: float,
    epsilon_m: float,
    epsilon_f: float,
    phi_forme: float,
    avertissements: list[str],
) -> ResultatThermique:
    """Acier non protégé — EN 1993-1-2 §4.2.5.1, éq. (4.25).

        Δθ_a,t = k_sh · (A_m/V) / (c_a · ρ_a) · ḣ_net · Δt
    """
    if dt > DT_MAX_NON_PROTEGE:
        raise ValueError(
            f"Pas de temps {dt} s supérieur à la borne de {DT_MAX_NON_PROTEGE} s "
            "de l'EN 1993-1-2 §4.2.5.1(4)."
        )

    k_sh = facteur_ombre(profil, exposition, feu_nominal=courbe.nominale)

    temps: list[float] = [0.0]
    acier: list[float] = [TEMPERATURE_INITIALE]
    gaz: list[float] = [courbe.temperature(0.0)]

    theta_a = TEMPERATURE_INITIALE
    t = 0.0
    while t < duree - 1e-9:
        pas = min(dt, duree - t)
        theta_g = courbe.temperature(t)

        h_net = flux_net(
            theta_g=theta_g,
            theta_m=theta_a,
            alpha_c=courbe.alpha_c,
            epsilon_m=epsilon_m,
            epsilon_f=epsilon_f,
            phi=phi_forme,
        )
        theta_a += k_sh * Am_sur_V / (chaleur_specifique(theta_a) * RHO_A) * h_net * pas

        t += pas
        temps.append(t)
        acier.append(theta_a)
        gaz.append(courbe.temperature(t))

    return ResultatThermique(
        temps=tuple(temps),
        temperatures=tuple(acier),
        temperatures_gaz=tuple(gaz),
        profil=profil,
        exposition=exposition,
        courbe=courbe,
        protection=None,
        Am_sur_V=Am_sur_V,
        k_sh=k_sh,
        avertissements=tuple(avertissements),
    )


def _protege(
    *,
    profil: Profil,
    exposition: Exposition,
    duree: float,
    courbe: CourbeFeu,
    protection: Protection,
    dt: float,
    Ap_sur_V: float,
    delai_evaporation: float | None,
    avertissements: list[str],
) -> ResultatThermique:
    """Acier protégé — EN 1993-1-2 §4.2.5.2, éq. (4.27) et (4.28).

        Δθ_a,t = [λ_p·(A_p/V) / (d_p·c_a·ρ_a)] · [(θ_g,t − θ_a,t) / (1 + φ/3)] · Δt
                 − (e^(φ/10) − 1) · Δθ_g,t

        φ = (c_p·ρ_p / (c_a·ρ_a)) · d_p · (A_p/V)

    Le second terme peut rendre l'incrément négatif au tout début, quand
    l'isolant absorbe une part importante de la chaleur. La norme impose alors
    de le ramener à zéro — sans quoi la température de l'acier descendrait
    sous l'ambiante.
    """
    if dt > DT_MAX_PROTEGE:
        raise ValueError(
            f"Pas de temps {dt} s supérieur à la borne de {DT_MAX_PROTEGE} s "
            "de l'EN 1993-1-2 §4.2.5.2(2)."
        )

    d_p = protection.d_p
    if delai_evaporation is None:
        delai_evaporation = _delai_evaporation(protection)

    temps: list[float] = [0.0]
    acier: list[float] = [TEMPERATURE_INITIALE]
    gaz: list[float] = [courbe.temperature(0.0)]

    theta_a = TEMPERATURE_INITIALE
    t = 0.0
    phi_dernier = 0.0
    reste_palier = delai_evaporation

    while t < duree - 1e-9:
        pas = min(dt, duree - t)
        theta_g = courbe.temperature(t)
        delta_theta_g = courbe.temperature(t + pas) - theta_g

        c_a = chaleur_specifique(theta_a)
        lambda_p = protection.conductivite(theta_a)

        phi = (protection.c_p * protection.rho_p) / (c_a * RHO_A) * d_p * Ap_sur_V
        phi_dernier = phi

        delta = (
            lambda_p * Ap_sur_V / (d_p * c_a * RHO_A)
            * (theta_g - theta_a) / (1.0 + phi / 3.0)
            * pas
        ) - (math.exp(phi / 10.0) - 1.0) * delta_theta_g

        # EN 1993-1-2 §4.2.5.2(1) : un incrément négatif alors que les gaz
        # continuent de monter est ramené à zéro.
        if delta_theta_g > 0.0 and delta < 0.0:
            delta = 0.0

        if reste_palier > 0.0 and theta_a + delta > 100.0 >= theta_a:
            # Palier d'évaporation de l'eau contenue dans l'isolant.
            theta_a = 100.0
            reste_palier -= pas
        elif reste_palier > 0.0 and theta_a >= 100.0:
            reste_palier -= pas
        else:
            theta_a += delta

        t += pas
        temps.append(t)
        acier.append(theta_a)
        gaz.append(courbe.temperature(t))

    return ResultatThermique(
        temps=tuple(temps),
        temperatures=tuple(acier),
        temperatures_gaz=tuple(gaz),
        profil=profil,
        exposition=exposition,
        courbe=courbe,
        protection=protection,
        Am_sur_V=Ap_sur_V,
        k_sh=1.0,
        phi=phi_dernier,
        avertissements=tuple(avertissements),
    )


def _delai_evaporation(protection: Protection) -> float:
    """Délai de palier à 100 °C dû à l'humidité de l'isolant [s].

    EN 1993-1-2 §4.2.5.2(6) autorise à tenir compte de la teneur en eau par un
    délai pendant lequel la température de l'acier reste bloquée à 100 °C.

    L'expression retenue ici, ``t_v = p·ρ_p·d_p² / (5·λ_p)`` en minutes, est
    celle usuellement citée dans la littérature technique et reprise de
    l'EN 1994-1-2. Elle est à confirmer sur l'exemplaire de la norme avant tout
    usage en projet. Comme ``humidite`` vaut zéro par défaut, le délai est nul
    et le calcul reste sécuritaire tant que l'utilisateur ne l'active pas.
    """
    if protection.humidite <= 0.0:
        return 0.0
    minutes = (
        protection.humidite
        * protection.rho_p
        * protection.d_p**2
        / (5.0 * protection.lambda_p)
    )
    return minutes * 60.0
