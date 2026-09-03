"""Note de calcul traçable.

Restitue tous les intermédiaires d'une vérification avec la clause normative
correspondante, de façon qu'un tiers puisse refaire le calcul à la main.

Les références viennent toutes de ``references.py`` et portent la norme, le
paragraphe et le numéro d'équation : une note qui citerait « éq. (4.22) » sans
dire de quelle norme il s'agit obligerait son lecteur à le deviner.
"""

from __future__ import annotations

from .nomogramme.verification import ResultatVerification
from .references import (
    EC1_COURBES,
    EC3_1_1_CLASSES,
    EC3_CHI_FI,
    EC3_DEVERSEMENT,
    EC3_ECHAUFFEMENT_NU,
    EC3_ECHAUFFEMENT_PROTEGE,
    EC3_ELANCEMENT_THETA,
    EC3_EPSILON,
    EC3_GAMMA_M_FI,
    EC3_INTERACTION_FLAMBEMENT,
    EC3_MASSIVETE,
    EC3_MU_0,
    EC3_OMBRE,
    EC3_PHI_PROTECTION,
    EC3_RESISTANCES,
    EC3_THETA_CR,
    SZS_C5,
    a_recouper,
)
from .unites import en_kN, en_kNm, en_minutes

__all__ = ["note_de_calcul"]


def _ligne(libelle: str, valeur: str, clause: str = "") -> str:
    return f"| {libelle} | {valeur} | {clause} |"


def _section_soudee(r: ResultatVerification) -> list[str]:
    """Les caractéristiques d'une section reconstituée, et leur origine.

    Un profilé du catalogue se retrouve dans les tables SZS ; une section
    soudée n'existe nulle part ailleurs que dans cette note. Elle doit donc y
    figurer assez complètement pour être refaite à la main.
    """
    p = r.profil
    lignes = ["## Section reconstituée soudée", ""]
    lignes.append(
        "Caractéristiques calculées depuis les tôles, gorges de soudure et "
        "congés négligés. Aucune valeur tabulée ne vient les recouper."
    )
    lignes.append("")
    lignes.append("| Grandeur | Valeur |")
    lignes.append("|---|---|")
    lignes.append(f"| Hauteur h | {p.h * 1e3:.0f} mm |")
    lignes.append(f"| Largeur hors tout b | {p.b * 1e3:.0f} mm |")
    lignes.append(f"| Épaisseur d'âme t_w | {p.tw * 1e3:.1f} mm |")
    lignes.append(f"| Épaisseur de semelle t_f | {p.tf * 1e3:.1f} mm |")
    lignes.append(f"| Hauteur d'âme h_w | {p.hw * 1e3:.0f} mm |")
    lignes.append(f"| Aire A | {p.A * 1e4:.1f} cm² |")
    lignes.append(f"| Masse | {p.masse:.1f} kg/m |")
    lignes.append(f"| I_y / I_z | {p.Iy * 1e8:.0f} / {p.Iz * 1e8:.0f} cm⁴ |")
    lignes.append(f"| W_pl,y / W_pl,z | {p.Wply * 1e6:.0f} / {p.Wplz * 1e6:.0f} cm³ |")
    lignes.append(f"| i_y / i_z | {p.iy * 1e3:.1f} / {p.iz * 1e3:.1f} mm |")
    if p.It is not None:
        lignes.append(f"| I_t | {p.It * 1e8:.1f} cm⁴ |")
    if p.Iw is not None:
        lignes.append(f"| I_w | {p.Iw * 1e12:.0f} cm⁶ |")
    lignes.append(f"| Périmètre développé U_m | {p.Um * 1e3:.0f} mm |")
    # Toujours donnée, même quand elle vaut b : sur une section à semelles
    # inégales, c'est le nombre qui dit laquelle des deux la dalle recouvre,
    # et il n'apparaît nulle part ailleurs.
    lignes.append(
        f"| Largeur masquée par la dalle | {p.largeur_couverte * 1e3:.0f} mm "
        "(exposition sur trois faces) |"
    )
    lignes.append("")
    return lignes


def note_de_calcul(r: ResultatVerification) -> str:
    """Note de calcul au format Markdown."""
    duree_min = en_minutes(r.duree_requise)
    lignes: list[str] = []

    lignes.append(f"# Vérification au feu — {r.profil.nom}")
    lignes.append("")
    lignes.append(
        f"**{r.verdict.value.upper()}** pour R{duree_min:.0f} "
        f"({r.contexte.nom})"
    )
    lignes.append("")

    # --- données ------------------------------------------------------------
    lignes.append("## Données")
    lignes.append("")
    lignes.append("| Grandeur | Valeur | Référence |")
    lignes.append("|---|---|---|")
    origine = "section reconstituée soudée" if r.profil.soudee else SZS_C5.courte
    lignes.append(
        _ligne("Profilé", f"{r.profil.nom} ({r.profil.famille.value})", origine)
    )
    lignes.append(_ligne("Nuance", r.nuance.value, "EN 10025 / SIA 263 tab. 1"))
    lignes.append(
        _ligne("Limite d'élasticité", f"{r.utilisation_initiale.resistances.fy / 1e6:.0f} N/mm²",
               "épaisseur de semelle")
    )
    lignes.append(_ligne("Exposition", r.exposition.value, EC3_MASSIVETE.courte))
    lignes.append(_ligne("Courbe de feu", r.courbe.nom, EC1_COURBES.courte))
    lignes.append(
        _ligne("Protection", str(r.protection) if r.protection else "aucune", "")
    )
    lignes.append(_ligne("γ_M,fi", f"{r.contexte.gamma_M_fi:.2f}", EC3_GAMMA_M_FI.courte))
    lignes.append("")

    if r.profil.soudee:
        lignes.extend(_section_soudee(r))

    # --- sollicitations ------------------------------------------------------
    lignes.append("## Sollicitations en situation d'incendie")
    lignes.append("")
    lignes.append("| Grandeur | Valeur |")
    lignes.append("|---|---|")
    signe = "compression" if r.cas.comprime else ("traction" if r.cas.tendu else "—")
    lignes.append(f"| N_fi,Ed | {abs(en_kN(r.cas.N_fi_Ed)):.0f} kN ({signe}) |")
    lignes.append(f"| M_y,fi,Ed | {en_kNm(r.cas.My_fi_Ed):.1f} kN·m |")
    lignes.append(f"| M_z,fi,Ed | {en_kNm(r.cas.Mz_fi_Ed):.1f} kN·m |")
    lignes.append(f"| Vide d'étage (longueur d'épure) | {r.cas.L:.2f} m |")
    lignes.append(f"| l_fi,y / l_fi,z | {r.cas.longueur_flambement_y():.2f} / "
                  f"{r.cas.longueur_flambement_z():.2f} m |")
    lignes.append(f"| Longueur de déversement | {r.cas.longueur_deversement():.2f} m |")
    lignes.append("")

    # --- voie mécanique ------------------------------------------------------
    res = r.utilisation_initiale.resistances
    lignes.append("## Voie mécanique — degré d'utilisation et température critique")
    lignes.append("")
    lignes.append("| Grandeur | Valeur | Référence |")
    lignes.append("|---|---|---|")
    lignes.append(
        _ligne("Classification à chaud", str(r.classification),
               f"{EC3_EPSILON.courte} et {EC3_1_1_CLASSES.courte}")
    )
    lignes.append(_ligne("ε", f"{r.classification.epsilon:.3f}", EC3_EPSILON.courte))
    lignes.append(_ligne("λ̄_y,θ / λ̄_z,θ à 20 °C",
                         f"{res.lambda_y_theta:.3f} / {res.lambda_z_theta:.3f}",
                         EC3_ELANCEMENT_THETA.courte))
    lignes.append(_ligne("χ_y,fi / χ_z,fi à 20 °C",
                         f"{res.chi_y_fi:.3f} / {res.chi_z_fi:.3f}",
                         EC3_CHI_FI.courte))
    lignes.append(
        _ligne("χ_LT,fi à 20 °C", f"{res.chi_LT_fi:.3f}", EC3_DEVERSEMENT.courte)
    )
    lignes.append(
        _ligne("Critère gouvernant", r.gouverne_par, EC3_INTERACTION_FLAMBEMENT.clause)
    )
    lignes.append(_ligne("**μ₀**", f"**{r.mu_0:.3f}**", EC3_MU_0.courte))
    lignes.append("")

    lignes.append("| Température critique | Valeur | Référence |")
    lignes.append("|---|---|---|")
    if r.theta_cr_nomogramme is not None:
        lignes.append(
            _ligne("Nomogramme", f"{r.theta_cr_nomogramme:.0f} °C",
                   EC3_THETA_CR.courte)
        )
    if r.theta_cr_exact is not None:
        lignes.append(
            _ligne("Vérification croisée", f"{r.theta_cr_exact:.0f} °C",
                   f"{EC3_RESISTANCES.courte}, taux complet = 1")
        )
    if r.ecart_nomogramme is not None:
        lignes.append(_ligne("Écart", f"{r.ecart_nomogramme:+.0f} °C", ""))
    lignes.append(_ligne("**θ_cr retenue**", f"**{r.theta_cr:.0f} °C**", r.source_theta_cr))
    lignes.append("")

    # --- voie thermique ------------------------------------------------------
    lignes.append("## Voie thermique — diffusion de chaleur")
    lignes.append("")
    lignes.append("| Grandeur | Valeur | Référence |")
    lignes.append("|---|---|---|")
    lignes.append(_ligne("A_m/V", f"{r.Am_sur_V:.1f} m⁻¹", EC3_MASSIVETE.courte))
    lignes.append(_ligne("k_sh", f"{r.k_sh:.3f}", EC3_OMBRE.courte))
    if r.thermique.phi is not None:
        lignes.append(_ligne("φ", f"{r.thermique.phi:.3f}", EC3_PHI_PROTECTION.courte))
    echauffement = (
        EC3_ECHAUFFEMENT_PROTEGE if r.protection else EC3_ECHAUFFEMENT_NU
    )
    lignes.append(
        _ligne("Équation d'échauffement", f"éq. {echauffement.equation}",
               echauffement.courte)
    )
    lignes.append("")

    lignes.append("| t [min] | θ_a [°C] | θ_g [°C] |")
    lignes.append("|---:|---:|---:|")
    pas = max(duree_min / 6.0, 5.0)
    for minute, theta in r.thermique.echantillons(pas):
        if minute > duree_min * 1.5:
            break
        theta_g = r.courbe.temperature(minute * 60.0)
        lignes.append(f"| {minute:.0f} | {theta:.0f} | {theta_g:.0f} |")
    lignes.append("")

    # --- verdict -------------------------------------------------------------
    lignes.append("## Verdict")
    lignes.append("")
    lignes.append("| Grandeur | Valeur |")
    lignes.append("|---|---|")
    lignes.append(f"| θ_a à {duree_min:.0f} min | {r.theta_a_a_echeance:.0f} °C |")
    lignes.append(f"| θ_cr | {r.theta_cr:.0f} °C |")
    lignes.append(f"| Marge | {r.marge_temperature:+.0f} °C |")
    if r.t_fi_d_minutes is not None:
        lignes.append(f"| Durée atteinte t_fi,d | {r.t_fi_d_minutes:.1f} min |")
    else:
        lignes.append(
            f"| Durée atteinte t_fi,d | > {en_minutes(r.thermique.duree):.0f} min |"
        )
    lignes.append(f"| **Exigence R{duree_min:.0f}** | **{r.verdict.value}** |")
    lignes.append("")

    if r.avertissements:
        lignes.append("## Avertissements")
        lignes.append("")
        for avertissement in r.avertissements:
            lignes.append(f"- {avertissement}")
        lignes.append("")

    restantes = a_recouper()
    if restantes:
        lignes.append("## Clauses restant à recouper")
        lignes.append("")
        lignes.append(
            "Ces références proviennent de la connaissance du corpus normatif "
            "et n'ont pas été confrontées à un exemplaire officiel."
        )
        lignes.append("")
        for reference in restantes:
            lignes.append(f"- {reference.complete}")
        lignes.append("")

    lignes.append("---")
    lignes.append("")
    lignes.append(
        "Note produite par *nommogramme*. Cet outil n'a pas encore été "
        "confronté à des exemples normatifs complets et ne constitue pas une "
        "justification de projet."
    )

    return "\n".join(lignes)
