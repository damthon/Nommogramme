"""Note de calcul traçable.

Restitue tous les intermédiaires d'une vérification avec la clause normative
correspondante, de façon qu'un tiers puisse refaire le calcul à la main.
"""

from __future__ import annotations

from .nomogramme.verification import ResultatVerification
from .unites import en_kN, en_kNm, en_minutes

__all__ = ["note_de_calcul"]


def _ligne(libelle: str, valeur: str, clause: str = "") -> str:
    return f"| {libelle} | {valeur} | {clause} |"


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
    lignes.append(_ligne("Profilé", f"{r.profil.nom} ({r.profil.famille.value})", "SZS C5"))
    lignes.append(_ligne("Nuance", r.nuance.value, "EN 10025 / SIA 263 tab. 1"))
    lignes.append(
        _ligne("Limite d'élasticité", f"{r.utilisation_initiale.resistances.fy / 1e6:.0f} N/mm²",
               "épaisseur de semelle")
    )
    lignes.append(_ligne("Exposition", r.exposition.value, "EN 1993-1-2 tab. 4.2/4.3"))
    lignes.append(_ligne("Courbe de feu", r.courbe.nom, "EN 1991-1-2 §3.2"))
    lignes.append(
        _ligne("Protection", str(r.protection) if r.protection else "aucune", "")
    )
    lignes.append(_ligne("γ_M,fi", f"{r.contexte.gamma_M_fi:.2f}", "EN 1993-1-2 §2.3(1)P"))
    lignes.append("")

    # --- sollicitations ------------------------------------------------------
    lignes.append("## Sollicitations en situation d'incendie")
    lignes.append("")
    lignes.append("| Grandeur | Valeur |")
    lignes.append("|---|---|")
    signe = "compression" if r.cas.comprime else ("traction" if r.cas.tendu else "—")
    lignes.append(f"| N_fi,Ed | {abs(en_kN(r.cas.N_fi_Ed)):.0f} kN ({signe}) |")
    lignes.append(f"| M_y,fi,Ed | {en_kNm(r.cas.My_fi_Ed):.1f} kN·m |")
    lignes.append(f"| M_z,fi,Ed | {en_kNm(r.cas.Mz_fi_Ed):.1f} kN·m |")
    lignes.append(f"| Longueur d'épure | {r.cas.L:.2f} m |")
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
               "EN 1993-1-2 §4.2.2, ε = 0,85·√(235/f_y)")
    )
    lignes.append(_ligne("ε", f"{r.classification.epsilon:.3f}", "§4.2.2"))
    lignes.append(_ligne("λ̄_y,θ / λ̄_z,θ à 20 °C",
                         f"{res.lambda_y_theta:.3f} / {res.lambda_z_theta:.3f}", "éq. (4.9)"))
    lignes.append(_ligne("χ_y,fi / χ_z,fi à 20 °C",
                         f"{res.chi_y_fi:.3f} / {res.chi_z_fi:.3f}", "éq. (4.6)"))
    lignes.append(_ligne("χ_LT,fi à 20 °C", f"{res.chi_LT_fi:.3f}", "§4.2.3.3(4)"))
    lignes.append(_ligne("Critère gouvernant", r.gouverne_par, "§4.2.3.5"))
    lignes.append(_ligne("**μ₀**", f"**{r.mu_0:.3f}**", "éq. (4.23)"))
    lignes.append("")

    lignes.append("| Température critique | Valeur | Référence |")
    lignes.append("|---|---|---|")
    if r.theta_cr_nomogramme is not None:
        lignes.append(
            _ligne("Nomogramme", f"{r.theta_cr_nomogramme:.0f} °C", "éq. (4.22)")
        )
    if r.theta_cr_exact is not None:
        lignes.append(
            _ligne("Vérification croisée", f"{r.theta_cr_exact:.0f} °C",
                   "§4.2.3, taux complet = 1")
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
    lignes.append(_ligne("A_m/V", f"{r.Am_sur_V:.1f} m⁻¹", "§4.2.5.1, tab. 4.2/4.3"))
    lignes.append(_ligne("k_sh", f"{r.k_sh:.3f}", "éq. (4.26a/b)"))
    if r.thermique.phi is not None:
        lignes.append(_ligne("φ", f"{r.thermique.phi:.3f}", "éq. (4.28)"))
    equation = "éq. (4.27)" if r.protection else "éq. (4.25)"
    lignes.append(_ligne("Équation d'échauffement", equation, "§4.2.5"))
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

    lignes.append("---")
    lignes.append("")
    lignes.append(
        "Note produite par *nommogramme*. Les clauses citées sont à recouper "
        "avec les exemplaires officiels des normes. Cet outil n'a pas encore "
        "été confronté à des exemples normatifs complets et ne constitue pas "
        "une justification de projet."
    )

    return "\n".join(lignes)
