"""Note de calcul détaillée, au format PDF.

La note Markdown de ``rapport`` donne les résultats ; celle-ci donne en plus
**l'application numérique** de chaque formule : la formule littérale, la même
avec les valeurs substituées, puis le résultat, et la clause qui la fonde. Un
tiers doit pouvoir refaire le calcul à la calculatrice, ligne par ligne.

Les valeurs affichées ne sont pas recalculées à part : elles sont lues dans le
``ResultatVerification`` et dans les fonctions mêmes qui l'ont produit. Seules
les étapes intermédiaires que le résultat ne conserve pas (φ_θ, λ₁, un pas de
l'échauffement) sont réévaluées, par les fonctions du paquet et non par une
copie des formules.

Le PDF est produit par matplotlib, déjà requis par les figures : les formules
sont composées en mathtext, sans dépendance supplémentaire. La mise en page
passe par ``matplotlib.figure.Figure`` et non par pyplot, qui ouvrirait des
fenêtres sous l'interface de bureau.
"""

from __future__ import annotations

import io
import math
import textwrap
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .materiaux.acier import E_A, RHO_A, chaleur_specifique, k_E, k_y
from .mecanique.resistances import (
    G_ACIER,
    alpha_flambement_feu,
    kappa_1_pour,
    moment_critique_elastique,
)
from .nomogramme.verification import ResultatVerification, _taux_a
from .profils.geometrie import (
    facteur_massivete_caisson,
    perimetre_expose,
)
from .profils.modele import Forme
from .references import (
    EC1_COURBES,
    EC3_1_1_CLASSES,
    EC3_ALPHA,
    EC3_CHI_FI,
    EC3_DEVERSEMENT,
    EC3_ECHAUFFEMENT_NU,
    EC3_ECHAUFFEMENT_PROTEGE,
    EC3_ELANCEMENT_THETA,
    EC3_EPSILON,
    EC3_FACTEURS_INTERACTION,
    EC3_FLAMBEMENT,
    EC3_GAMMA_M_FI,
    EC3_INTERACTION_DEVERSEMENT,
    EC3_KAPPA,
    EC3_INTERACTION_FLAMBEMENT,
    EC3_MASSIVETE,
    EC3_MOMENT_SECTION,
    EC3_MU_0,
    EC3_OMBRE,
    EC3_PHI_PROTECTION,
    EC3_PHI_THETA,
    EC3_RESISTANCES,
    EC3_TABLEAU_3_1,
    EC3_THETA_CR,
    EC5_BETA_N,
    EC5_CARBONISATION,
    MCR_C1,
    SZS_C5,
    a_recouper,
)
from .thermique.evolution import EPAISSEUR_SAINE_MIN
from .thermique.flux import (
    EPSILON_ACIER_CARBONE,
    EPSILON_FEU,
    PHI_DEFAUT,
    SIGMA,
    flux_convectif,
    flux_radiatif,
)
from .unites import en_kN, en_kNm, en_minutes

__all__ = ["etapes_de_calcul", "note_pdf"]


# --- mise en forme des nombres ------------------------------------------------


def n(valeur: float, decimales: int = 3) -> str:
    """Nombre au format mathtext, virgule décimale : ``0{,}342``."""
    if not math.isfinite(valeur):
        return r"\infty"
    texte = f"{valeur:.{decimales}f}"
    return texte.replace(".", "{,}")


def _txt(valeur: float, decimales: int = 3) -> str:
    """Nombre en texte courant, virgule décimale."""
    return f"{valeur:.{decimales}f}".replace(".", ",")


# --- blocs du document ---------------------------------------------------------


@dataclass
class Bloc:
    """Un élément de la note : titre, paragraphe, calcul, tableau ou figure."""

    genre: str
    texte: str = ""
    reference: str = ""
    lignes: list[str] = field(default_factory=list)
    entetes: list[str] = field(default_factory=list)
    rangees: list[list[str]] = field(default_factory=list)
    figure: object = None


def _titre(texte: str) -> Bloc:
    return Bloc("titre", texte)


def _para(texte: str) -> Bloc:
    return Bloc("texte", texte)


def _calcul(intitule: str, reference: str, *lignes: str) -> Bloc:
    """Un calcul : la formule, puis l'application numérique et le résultat.

    Chaque ligne est une expression mathtext, sans les ``$`` qui l'encadrent.
    """
    return Bloc("calcul", intitule, reference=reference, lignes=list(lignes))


def _tableau(entetes: list[str], rangees: list[list[str]]) -> Bloc:
    return Bloc("tableau", entetes=entetes, rangees=rangees)


# --- contenu -------------------------------------------------------------------


def etapes_de_calcul(r: ResultatVerification, section=None) -> list[Bloc]:
    """Toutes les étapes de la vérification, avec leur application numérique.

    ``section`` est la section soudée d'origine, si l'élément en est une : elle
    seule permet de dessiner la coupe et de détailler l'aire tôle par tôle.
    """
    blocs: list[Bloc] = []
    blocs += _donnees(r, section)
    blocs += _materiau_et_classe(r)
    blocs += _elancements(r)
    blocs += _resistances_froid(r)
    blocs += _interaction(r)
    blocs += _temperature_critique(r)
    blocs += _thermique(r)
    blocs += _verdict(r)
    return blocs


def _donnees(r: ResultatVerification, section) -> list[Bloc]:
    p, cas = r.profil, r.cas
    origine = "section reconstituée soudée" if p.soudee else SZS_C5.courte
    blocs = [
        _titre("1. Données"),
        _tableau(
            ["Grandeur", "Valeur", "Origine"],
            [
                ["Profilé", f"{p.nom} ({p.famille.value})", origine],
                ["Nuance d'acier", r.nuance.value, "EN 10025"],
                ["Exposition", r.exposition.value, EC3_MASSIVETE.courte],
                ["Courbe de feu", r.courbe.nom, EC1_COURBES.courte],
                ["Durée exigée", f"R{en_minutes(r.duree_requise):.0f}", ""],
                ["Protection", str(r.protection) if r.protection else "aucune", ""],
                ["Référentiel", r.contexte.nom, ""],
                ["γ_M,fi", _txt(r.contexte.gamma_M_fi, 2), EC3_GAMMA_M_FI.courte],
                ["κ₁", _txt(r.kappa_1, 2),
                 f"{EC3_KAPPA.courte} — {_origine_kappa_1(r)}"],
                ["κ₂ ; C₁", f"{_txt(r.kappa_2, 2)} ; {_txt(r.C1, 2)}", ""],
            ],
        ),
        _titre("2. Section"),
    ]

    if section is not None and hasattr(section, "plaques"):
        rangees = [
            [pl.nom or "tôle", f"{pl.largeur * 1e3:.0f} × {pl.hauteur * 1e3:.0f}",
             _txt(pl.aire * 1e4, 2)]
            for pl in section.plaques()
        ]
        blocs.append(_tableau(["Tôle", "b × h [mm]", "Aire [cm²]"], rangees))
        somme = " + ".join(n(pl.aire * 1e4, 2) for pl in section.plaques())
        blocs.append(_calcul(
            "Aire de la section", "somme des tôles, congés et soudures négligés",
            r"A = \sum b_i \cdot h_i",
            rf"A = {somme} = \mathbf{{{n(p.A * 1e4, 2)}\ \mathrm{{cm^2}}}}",
        ))

    rangees = [
        ["h ; b", f"{p.h * 1e3:.0f} ; {p.b * 1e3:.0f} mm"],
        ["t_w ; t_f", f"{_txt(p.tw * 1e3, 1)} ; {_txt(p.tf * 1e3, 1)} mm"],
        ["A", f"{_txt(p.A * 1e4, 2)} cm²"],
        ["I_y ; I_z", f"{p.Iy * 1e8:.0f} ; {p.Iz * 1e8:.0f} cm⁴"],
        ["W_el,y ; W_el,z", f"{p.Wely * 1e6:.0f} ; {p.Welz * 1e6:.0f} cm³"],
        ["W_pl,y ; W_pl,z", f"{p.Wply * 1e6:.0f} ; {p.Wplz * 1e6:.0f} cm³"],
        ["i_y ; i_z", f"{_txt(p.iy * 1e3, 1)} ; {_txt(p.iz * 1e3, 1)} mm"],
    ]
    if p.It is not None:
        rangees.append(["I_t", f"{_txt(p.It * 1e8, 1)} cm⁴"])
    if p.Um:
        rangees.append(["Périmètre développé U_m", f"{p.Um * 1e3:.0f} mm"])
    blocs.append(_tableau(["Caractéristique", "Valeur"], rangees))

    signe = "compression" if cas.comprime else ("traction" if cas.tendu else "nul")
    blocs += [
        _titre("3. Sollicitations en situation d'incendie"),
        _para(
            "Convention de signe : l'effort normal est négatif en compression. "
            "Les formules de l'EN 1993-1-2 raisonnent en compression positive ; "
            "la note emploie N_fi,Ed en valeur absolue dans les formules."
        ),
        _tableau(
            ["Grandeur", "Valeur"],
            [
                ["N_fi,Ed", f"{en_kN(cas.N_fi_Ed):.0f} kN ({signe})"],
                ["M_y,fi,Ed ; M_z,fi,Ed",
                 f"{_txt(en_kNm(cas.My_fi_Ed), 1)} ; {_txt(en_kNm(cas.Mz_fi_Ed), 1)} kN·m"],
                ["Longueur d'épure L", f"{_txt(cas.L, 2)} m"],
                ["l_fi,y ; l_fi,z", f"{_txt(cas.longueur_flambement_y(), 2)} ; "
                 f"{_txt(cas.longueur_flambement_z(), 2)} m"],
                ["Longueur de déversement", f"{_txt(cas.longueur_deversement(), 2)} m"],
                ["β_M,y ; β_M,z ; β_M,LT", f"{_txt(cas.beta_M_y, 2)} ; "
                 f"{_txt(cas.beta_M_z, 2)} ; {_txt(cas.beta_M_LT, 2)}"],
            ],
        ),
    ]
    return blocs


def _origine_kappa_1(r: ResultatVerification) -> str:
    """D'où vient κ₁ : la règle d'exposition, ou une valeur imposée."""
    attendu = kappa_1_pour(r.exposition.trois_faces, r.protection is not None)
    if abs(attendu - r.kappa_1) > 1e-9:
        return "valeur imposée"
    if not r.exposition.trois_faces:
        return "quatre faces exposées"
    return "trois faces, " + ("protégé" if r.protection is not None else "non protégé")


def _materiau_et_classe(r: ResultatVerification) -> list[Bloc]:
    res = r.utilisation_initiale.resistances
    fy = res.fy / 1e6
    c = r.classification
    blocs = [
        _titre("4. Matériau et classification"),
        _para(
            f"Limite d'élasticité de la nuance {r.nuance.value} pour une épaisseur "
            f"de semelle de {_txt(r.profil.tf * 1e3, 1)} mm : f_y = {fy:.0f} N/mm²."
        ),
        _calcul(
            "Coefficient ε à chaud", EC3_EPSILON.courte,
            r"\varepsilon = 0{,}85\,\sqrt{235/f_y}",
            rf"\varepsilon = 0{{,}}85 \cdot \sqrt{{235/{fy:.0f}}} = \mathbf{{{n(c.epsilon)}}}",
        ),
        _calcul(
            "Élancements de parois et classe", EC3_1_1_CLASSES.courte,
            rf"(c/t)_{{\mathrm{{semelle}}}} = {n(c.elancement_semelle, 2)}"
            rf" = {n(c.elancement_semelle / c.epsilon, 2)}\,\varepsilon"
            rf"\quad \rightarrow\ \mathrm{{classe}}\ {c.classe_semelle}",
            rf"(c/t)_{{\mathrm{{\hat{{a}}me}}}} = {n(c.elancement_ame, 2)}"
            rf" = {n(c.elancement_ame / c.epsilon, 2)}\,\varepsilon"
            rf"\quad (\alpha = {n(c.alpha, 3)})"
            rf"\quad \rightarrow\ \mathrm{{classe}}\ {c.classe_ame}",
            rf"\mathbf{{Section\ de\ classe\ {c.classe}}}",
        ),
    ]
    module = "plastique W_pl" if c.plastique else "élastique W_el"
    blocs.append(_para(
        f"La classe {c.classe} conduit à retenir le module {module} pour les "
        "moments résistants."
    ))
    return blocs


def _elancements(r: ResultatVerification) -> list[Bloc]:
    p, cas = r.profil, r.cas
    res = r.utilisation_initiale.resistances
    fy = res.fy
    lambda_1 = math.pi * math.sqrt(E_A / fy)
    blocs = [
        _titre("5. Élancements réduits à 20 °C"),
        _calcul(
            "Élancement de référence", "EN 1993-1-1 §6.3.1.3",
            r"\lambda_1 = \pi\,\sqrt{E/f_y}",
            rf"\lambda_1 = \pi \cdot \sqrt{{{E_A / 1e6:.0f}/{fy / 1e6:.0f}}}"
            rf" = \mathbf{{{n(lambda_1, 2)}}}",
        ),
    ]
    for axe, longueur, rayon, lam in (
        ("y", cas.longueur_flambement_y(), p.iy, res.lambda_y_theta),
        ("z", cas.longueur_flambement_z(), p.iz, res.lambda_z_theta),
    ):
        blocs.append(_calcul(
            f"Élancement réduit, axe {axe}", "EN 1993-1-1 §6.3.1.3",
            rf"\bar{{\lambda}}_{axe} = \dfrac{{l_{{fi,{axe}}}/i_{axe}}}{{\lambda_1}}",
            rf"\bar{{\lambda}}_{axe} = \dfrac{{{longueur * 1e3:.0f}/{n(rayon * 1e3, 1)}}}"
            rf"{{{n(lambda_1, 2)}}} = \mathbf{{{n(lam)}}}",
        ))

    lam_LT = res.lambda_LT_theta
    if lam_LT > 0.0:
        L = cas.longueur_deversement()
        M_cr = moment_critique_elastique(p, L, r.C1)
        I_t = p.It or 0.0
        I_w = p.Iw if p.Iw is not None else p.Iz * (p.h - p.tf) ** 2 / 4.0
        W = p.Wply if r.classification.plastique else p.Wely
        blocs += [
            _calcul(
                "Moment critique de déversement", MCR_C1.courte,
                r"M_{cr} = C_1\,\dfrac{\pi^2 E I_z}{L^2}\,"
                r"\sqrt{\dfrac{I_w}{I_z} + \dfrac{L^2 G I_t}{\pi^2 E I_z}}",
                rf"M_{{cr}} = {n(r.C1, 2)} \cdot \dfrac{{\pi^2 \cdot {E_A / 1e9:.0f}"
                rf"\cdot 10^9 \cdot {n(p.Iz * 1e8, 0)} \cdot 10^{{-8}}}}{{{n(L, 2)}^2}}"
                rf"\cdot \sqrt{{\dfrac{{{n(I_w * 1e12, 0)} \cdot 10^{{-12}}}}"
                rf"{{{n(p.Iz * 1e8, 0)} \cdot 10^{{-8}}}} + \dfrac{{{n(L, 2)}^2 \cdot "
                rf"{G_ACIER / 1e9:.0f} \cdot 10^9 \cdot {n(I_t * 1e8, 1)} \cdot 10^{{-8}}}}"
                rf"{{\pi^2 \cdot {E_A / 1e9:.0f} \cdot 10^9 \cdot {n(p.Iz * 1e8, 0)}"
                rf"\cdot 10^{{-8}}}}}}",
                rf"M_{{cr}} = \mathbf{{{n(M_cr / 1e3, 1)}\ \mathrm{{kN\cdot m}}}}",
            ),
            _calcul(
                "Élancement réduit de déversement", EC3_DEVERSEMENT.courte,
                r"\bar{\lambda}_{LT} = \sqrt{W_y f_y / M_{cr}}",
                rf"\bar{{\lambda}}_{{LT}} = \sqrt{{{n(W * 1e6, 0)} \cdot 10^{{-6}}"
                rf"\cdot {fy / 1e6:.0f} \cdot 10^6 / ({n(M_cr / 1e3, 1)} \cdot 10^3)}}"
                rf" = \mathbf{{{n(lam_LT)}}}",
            ),
        ]
    elif cas.My_fi_Ed > 0.0:
        blocs.append(_para(
            "Pas de déversement : la semelle comprimée est maintenue, ou la "
            "section est un profil creux, dont la rigidité de torsion l'exclut."
        ))
    return blocs


def _chi(intitule: str, lam_theta: float, fy: float, chi: float) -> Bloc:
    alpha = alpha_flambement_feu(fy)
    phi = 0.5 * (1.0 + alpha * lam_theta + lam_theta**2)
    return _calcul(
        intitule, f"{EC3_PHI_THETA.courte} et {EC3_CHI_FI.courte}",
        r"\varphi_\theta = \dfrac{1}{2}\left[1 + \alpha\,\bar{\lambda}_\theta"
        r" + \bar{\lambda}_\theta^2\right] \qquad \chi_{fi} = \dfrac{1}"
        r"{\varphi_\theta + \sqrt{\varphi_\theta^2 - \bar{\lambda}_\theta^2}}",
        rf"\varphi_\theta = \dfrac{{1}}{{2}}\left[1 + {n(alpha)} \cdot {n(lam_theta)}"
        rf" + {n(lam_theta)}^2\right] = {n(phi)}",
        rf"\chi_{{fi}} = \dfrac{{1}}{{{n(phi)} + \sqrt{{{n(phi)}^2 - {n(lam_theta)}^2}}}}"
        rf" = \mathbf{{{n(chi)}}}",
    )


def _resistances(r: ResultatVerification, res, theta_txt: str) -> list[Bloc]:
    """Résistances à une température, avec leur application numérique."""
    p, cas = r.profil, r.cas
    fy, g = res.fy, res.gamma_M_fi
    ky = res.k_y_theta
    blocs: list[Bloc] = []
    if cas.comprime:
        blocs.append(_chi(f"Flambement, axe y — {theta_txt}", res.lambda_y_theta, fy,
                          res.chi_y_fi))
        blocs.append(_chi(f"Flambement, axe z — {theta_txt}", res.lambda_z_theta, fy,
                          res.chi_z_fi))
        chi_min = min(res.chi_y_fi, res.chi_z_fi)
        blocs.append(_calcul(
            f"Résistance au flambement — {theta_txt}", EC3_FLAMBEMENT.courte,
            r"N_{b,fi,Rd} = \chi_{min}\,A\,k_{y,\theta}\,f_y/\gamma_{M,fi}",
            rf"N_{{b,fi,Rd}} = {n(chi_min)} \cdot {n(p.A * 1e4, 2)} \cdot 10^{{-4}}"
            rf"\cdot {n(ky)} \cdot {fy / 1e6:.0f} \cdot 10^6 / {n(g, 2)}"
            rf" = \mathbf{{{n(en_kN(res.N_Rd), 0)}\ \mathrm{{kN}}}}",
        ))
    elif cas.tendu:
        blocs.append(_calcul(
            f"Résistance à la traction — {theta_txt}", "EN 1993-1-2 §4.2.3.1, éq. (4.3)",
            r"N_{fi,\theta,Rd} = k_{y,\theta}\,A\,f_y/\gamma_{M,fi}",
            rf"N_{{fi,\theta,Rd}} = {n(ky)} \cdot {n(p.A * 1e4, 2)} \cdot 10^{{-4}}"
            rf"\cdot {fy / 1e6:.0f} \cdot 10^6 / {n(g, 2)}"
            rf" = \mathbf{{{n(en_kN(res.N_Rd), 0)}\ \mathrm{{kN}}}}",
        ))

    plastique = r.classification.plastique
    for axe, effort, M_Rd, W in (
        ("y", cas.My_fi_Ed, res.My_Rd, p.Wply if plastique else p.Wely),
        ("z", cas.Mz_fi_Ed, res.Mz_Rd, p.Wplz if plastique else p.Welz),
    ):
        if effort <= 0.0:
            continue
        blocs.append(_calcul(
            f"Moment résistant, axe {axe} — {theta_txt}", EC3_MOMENT_SECTION.courte,
            rf"M_{{{axe},fi,Rd}} = \dfrac{{W_{axe}\,k_{{y,\theta}}\,f_y}}"
            r"{\gamma_{M,fi}\,\kappa_1\,\kappa_2}",
            rf"M_{{{axe},fi,Rd}} = \dfrac{{{n(W * 1e6, 0)} \cdot 10^{{-6}} \cdot {n(ky)}"
            rf"\cdot {fy / 1e6:.0f} \cdot 10^6}}{{{n(g, 2)} \cdot {n(r.kappa_1, 2)}"
            rf"\cdot {n(r.kappa_2, 2)}}} = \mathbf{{{n(en_kNm(M_Rd), 1)}"
            r"\ \mathrm{kN\cdot m}}",
        ))
    if cas.My_fi_Ed > 0.0 and res.lambda_LT_theta > 0.0 and not cas.maintien_lateral:
        blocs.append(_chi(f"Déversement — {theta_txt}", res.lambda_LT_theta, fy,
                          res.chi_LT_fi))
        W = p.Wply if plastique else p.Wely
        blocs.append(_calcul(
            f"Moment résistant au déversement — {theta_txt}", EC3_DEVERSEMENT.courte,
            r"M_{b,fi,Rd} = \chi_{LT,fi}\,W_y\,k_{y,\theta}\,f_y/\gamma_{M,fi}",
            rf"M_{{b,fi,Rd}} = {n(res.chi_LT_fi)} \cdot {n(W * 1e6, 0)} \cdot 10^{{-6}}"
            rf"\cdot {n(ky)} \cdot {fy / 1e6:.0f} \cdot 10^6 / {n(g, 2)}"
            rf" = \mathbf{{{n(en_kNm(res.Mb_Rd), 1)}\ \mathrm{{kN\cdot m}}}}",
        ))
    return blocs


def _resistances_froid(r: ResultatVerification) -> list[Bloc]:
    res = r.utilisation_initiale.resistances
    blocs = [
        _titre("6. Résistances à 20 °C sous charges d'incendie"),
        _para(
            "À 20 °C, k_y,θ = k_E,θ = 1 : les élancements à chaud sont égaux aux "
            "élancements à froid. Le facteur d'imperfection est celui de la "
            "courbe de flambement unique à chaud."
        ),
        _calcul(
            "Facteur d'imperfection", EC3_ALPHA.courte,
            r"\alpha = 0{,}65\,\sqrt{235/f_y}",
            rf"\alpha = 0{{,}}65 \cdot \sqrt{{235/{res.fy / 1e6:.0f}}}"
            rf" = \mathbf{{{n(alpha_flambement_feu(res.fy))}}}",
        ),
    ]
    return blocs + _resistances(r, res, "20 °C")


def _taux(r: ResultatVerification, u, theta_txt: str) -> list[Bloc]:
    """Facteurs d'interaction et taux d'utilisation, appliqués."""
    cas, res = r.cas, u.resistances
    N = abs(cas.N_fi_Ed)
    My, Mz = cas.My_fi_Ed, cas.Mz_fi_Ed
    blocs: list[Bloc] = []

    if cas.tendu:
        blocs.append(_calcul(
            f"Taux d'utilisation, traction et flexion — {theta_txt}",
            "somme linéaire, hors §4.2.3.5",
            r"\dfrac{N}{N_{Rd}} + \dfrac{M_y}{M_{y,Rd}} + \dfrac{M_z}{M_{z,Rd}}",
            rf"= \dfrac{{{n(en_kN(N), 0)}}}{{{n(en_kN(res.N_Rd), 0)}}} + "
            rf"\dfrac{{{n(en_kNm(My), 1)}}}{{{n(en_kNm(res.My_Rd), 1)}}} + "
            rf"\dfrac{{{n(en_kNm(Mz), 1)}}}{{{n(en_kNm(res.Mz_Rd), 1)}}}"
            rf" = \mathbf{{{n(u.valeur)}}}",
        ))
        return blocs

    f = u.facteurs
    if f is None:
        return blocs
    A_ky_fy = r.profil.A * res.k_y_theta * res.fy / res.gamma_M_fi
    blocs.append(_calcul(
        f"Facteurs d'interaction — {theta_txt}", EC3_FACTEURS_INTERACTION.courte,
        rf"\mu_y = (1{{,}}2\,\beta_{{M,y}} - 3)\,\bar{{\lambda}}_{{y,\theta}}"
        rf" + 0{{,}}44\,\beta_{{M,y}} - 0{{,}}29 = (1{{,}}2 \cdot {n(cas.beta_M_y, 2)} - 3)"
        rf"\cdot {n(res.lambda_y_theta)} + 0{{,}}44 \cdot {n(cas.beta_M_y, 2)} - 0{{,}}29"
        rf" = {n(f.mu_y)} \ \ (\leq 0{{,}}8)",
        rf"k_y = 1 - \dfrac{{\mu_y\,N_{{fi,Ed}}}}{{\chi_{{y,fi}}\,A\,k_{{y,\theta}}\,f_y"
        rf"/\gamma_{{M,fi}}}} = 1 - \dfrac{{{n(f.mu_y)} \cdot {n(en_kN(N), 0)}}}"
        rf"{{{n(res.chi_y_fi)} \cdot {n(en_kN(A_ky_fy), 0)}}} = \mathbf{{{n(f.k_y)}}}"
        rf"\ \ (\leq 3)",
        rf"\mu_z = (2\,\beta_{{M,z}} - 5)\,\bar{{\lambda}}_{{z,\theta}}"
        rf" + 0{{,}}44\,\beta_{{M,z}} - 0{{,}}29 = {n(f.mu_z)} \qquad"
        rf"k_z = 1 - \dfrac{{{n(f.mu_z)} \cdot {n(en_kN(N), 0)}}}"
        rf"{{{n(res.chi_z_fi)} \cdot {n(en_kN(A_ky_fy), 0)}}} = \mathbf{{{n(f.k_z)}}}",
        rf"\mu_{{LT}} = 0{{,}}15\,\bar{{\lambda}}_{{z,\theta}}\,\beta_{{M,LT}} - 0{{,}}15"
        rf" = {n(f.mu_LT)} \qquad k_{{LT}} = 1 - \dfrac{{{n(f.mu_LT)} \cdot"
        rf"{n(en_kN(N), 0)}}}{{{n(res.chi_z_fi)} \cdot {n(en_kN(A_ky_fy), 0)}}}"
        rf" = \mathbf{{{n(f.k_LT)}}}\ \ (\leq 1)",
    ))
    chi_min = min(res.chi_y_fi, res.chi_z_fi)
    blocs.append(_calcul(
        f"Flambement par flexion — {theta_txt}", EC3_INTERACTION_FLAMBEMENT.courte,
        r"\dfrac{N_{fi,Ed}}{\chi_{min,fi}\,A\,k_{y,\theta}\,f_y/\gamma_{M,fi}}"
        r" + \dfrac{k_y\,M_{y,fi,Ed}}{M_{y,fi,Rd}} + \dfrac{k_z\,M_{z,fi,Ed}}{M_{z,fi,Rd}}",
        rf"= \dfrac{{{n(en_kN(N), 0)}}}{{{n(chi_min)} \cdot {n(en_kN(A_ky_fy), 0)}}}"
        rf" + \dfrac{{{n(f.k_y)} \cdot {n(en_kNm(My), 1)}}}{{{n(en_kNm(res.My_Rd), 1)}}}"
        rf" + \dfrac{{{n(f.k_z)} \cdot {n(en_kNm(Mz), 1)}}}{{{n(en_kNm(res.Mz_Rd), 1)}}}"
        rf" = \mathbf{{{n(u.taux_flambement)}}}",
    ))
    if u.taux_deversement > 0.0:
        blocs.append(_calcul(
            f"Déversement — {theta_txt}", EC3_INTERACTION_DEVERSEMENT.courte,
            r"\dfrac{N_{fi,Ed}}{\chi_{z,fi}\,A\,k_{y,\theta}\,f_y/\gamma_{M,fi}}"
            r" + \dfrac{k_{LT}\,M_{y,fi,Ed}}{M_{b,fi,Rd}} + \dfrac{k_z\,M_{z,fi,Ed}}"
            r"{M_{z,fi,Rd}}",
            rf"= \dfrac{{{n(en_kN(N), 0)}}}{{{n(res.chi_z_fi)} \cdot {n(en_kN(A_ky_fy), 0)}}}"
            rf" + \dfrac{{{n(f.k_LT)} \cdot {n(en_kNm(My), 1)}}}"
            rf"{{{n(en_kNm(res.Mb_Rd), 1)}}} + \dfrac{{{n(f.k_z)} \cdot {n(en_kNm(Mz), 1)}}}"
            rf"{{{n(en_kNm(res.Mz_Rd), 1)}}} = \mathbf{{{n(u.taux_deversement)}}}",
        ))
    return blocs


def _interaction(r: ResultatVerification) -> list[Bloc]:
    u = r.utilisation_initiale
    blocs = [_titre("7. Interaction N + M et degré d'utilisation μ₀")]
    blocs += _taux(r, u, "20 °C")
    blocs.append(_calcul(
        "Degré d'utilisation à t = 0", EC3_MU_0.courte,
        r"\mu_0 = \max(\mathrm{flambement},\ \mathrm{d\acute{e}versement})",
        rf"\mu_0 = \mathbf{{{n(r.mu_0)}}}",
    ))
    blocs.append(_para(f"Critère qui gouverne : {u.critere}."))
    return blocs


def _temperature_critique(r: ResultatVerification) -> list[Bloc]:
    blocs = [_titre("8. Température critique")]
    if r.theta_cr_nomogramme is not None:
        mu = r.mu_0
        blocs.append(_calcul(
            "Température critique, méthode du nomogramme", EC3_THETA_CR.courte,
            r"\theta_{a,cr} = 39{,}19\,\ln\left[\dfrac{1}{0{,}9674\,\mu_0^{3{,}833}}"
            r" - 1\right] + 482",
            rf"\theta_{{a,cr}} = 39{{,}}19 \cdot \ln\left[\dfrac{{1}}{{0{{,}}9674 \cdot"
            rf"{n(mu)}^{{3{{,}}833}}}} - 1\right] + 482"
            rf" = \mathbf{{{n(r.theta_cr_nomogramme, 1)}\ \mathrm{{°C}}}}",
        ))
    else:
        blocs.append(_para(
            "L'équation (4.22) ne s'applique pas ici (classe 4, ou μ₀ hors de son "
            "domaine) : voir les avertissements."
        ))

    if r.theta_cr_exact is not None and r.mu_0 < 1.0:
        theta = r.theta_cr_exact
        blocs.append(_para(
            "Vérification croisée : la température à laquelle le taux complet, "
            "flambement et interaction compris, atteint 1,00. Elle est trouvée par "
            "dichotomie ; les lignes qui suivent en refont le calcul à cette "
            f"température, θ = {_txt(theta, 1)} °C."
        ))
        u = _taux_a(
            theta, r.profil, r.nuance, r.cas, r.contexte,
            r.utilisation_initiale.resistances.lambda_y_theta,
            r.utilisation_initiale.resistances.lambda_z_theta,
            r.utilisation_initiale.resistances.lambda_LT_theta,
            r.classification, r.kappa_1, r.kappa_2,
        )
        res = u.resistances
        lam0 = r.utilisation_initiale.resistances
        blocs.append(_calcul(
            f"Facteurs de réduction à {_txt(theta, 1)} °C", EC3_TABLEAU_3_1.courte,
            rf"k_{{y,\theta}} = {n(k_y(theta))} \qquad k_{{E,\theta}} = {n(k_E(theta))}"
            r"\qquad \mathrm{(interpolation\ lin\acute{e}aire\ du\ tableau)}",
        ))
        lignes = []
        for axe, lam, lam_t in (("y", lam0.lambda_y_theta, res.lambda_y_theta),
                                ("z", lam0.lambda_z_theta, res.lambda_z_theta)):
            lignes.append(
                rf"\bar{{\lambda}}_{{{axe},\theta}} = \bar{{\lambda}}_{axe}\,"
                rf"\sqrt{{k_{{y,\theta}}/k_{{E,\theta}}}} = {n(lam)} \cdot"
                rf"\sqrt{{{n(k_y(theta))}/{n(k_E(theta))}}} = \mathbf{{{n(lam_t)}}}"
            )
        blocs.append(_calcul(
            f"Élancements à {_txt(theta, 1)} °C", EC3_ELANCEMENT_THETA.courte, *lignes
        ))
        blocs += _resistances(r, res, f"{_txt(theta, 1)} °C")
        blocs += _taux(r, u, f"{_txt(theta, 1)} °C")
        blocs.append(_para(
            f"Le taux vaut {_txt(u.valeur, 3)} ≈ 1,00 : θ_cr,exact = "
            f"{_txt(theta, 1)} °C ({EC3_RESISTANCES.courte})."
        ))

    candidats = []
    if r.theta_cr_nomogramme is not None:
        candidats.append(n(r.theta_cr_nomogramme, 1))
    if r.theta_cr_exact is not None:
        candidats.append(n(r.theta_cr_exact, 1))
    if candidats:
        liste = r" ;\ ".join(candidats)
        blocs.append(_calcul(
            "Température critique retenue", "la plus défavorable des deux voies",
            rf"\theta_{{cr}} = \min({liste})"
            rf" = \mathbf{{{n(r.theta_cr, 1)}\ \mathrm{{°C}}}}",
        ))
    blocs.append(_para(f"Source : {r.source_theta_cr}."))
    return blocs


def _thermique(r: ResultatVerification) -> list[Bloc]:
    p, th = r.profil, r.thermique
    perimetre = perimetre_expose(p, r.exposition)
    blocs = [
        _titre("9. Échauffement de l'acier"),
        _calcul(
            "Facteur de massiveté", EC3_MASSIVETE.courte,
            r"A_m/V = P_{\mathrm{expos\acute{e}}}/A",
            rf"A_m/V = {n(perimetre, 4)}\ \mathrm{{m}} / {n(p.A * 1e4, 2)}"
            rf"\cdot 10^{{-4}}\ \mathrm{{m^2}} = \mathbf{{{n(th.Am_sur_V, 1)}\ \mathrm{{m^{{-1}}}}}}",
        ),
    ]
    if r.protection is None:
        if p.forme is Forme.PROFIL_CREUX:
            blocs.append(_para("Profil creux, sans partie concave : k_sh = 1."))
        else:
            caisson = facteur_massivete_caisson(p, r.exposition)
            coef = "0{,}9 \\cdot " if r.courbe.nominale else ""
            blocs.append(_calcul(
                "Facteur d'ombre", EC3_OMBRE.courte,
                r"k_{sh} = 0{,}9\,[A_m/V]_b / [A_m/V]",
                rf"k_{{sh}} = {coef}{n(caisson, 1)} / {n(th.Am_sur_V, 1)}"
                rf" = \mathbf{{{n(th.k_sh)}}}",
            ))
    blocs += _pas_thermique(r)

    duree = en_minutes(th.duree)
    pas = 10.0 if en_minutes(r.duree_requise) <= 120 else 15.0
    rangees = []
    for minute, theta in th.echantillons(pas):
        if minute > max(en_minutes(r.duree_requise) * 1.5, 30.0) or minute > duree:
            break
        rangees.append([f"{minute:.0f}", f"{r.courbe.temperature(minute * 60.0):.0f}",
                        f"{theta:.0f}"])
    blocs.append(_para(
        f"Intégration pas à pas sur {duree:.0f} min. Évolution des températures :"
    ))
    blocs.append(_tableau(["t [min]", "θ_g [°C]", "θ_a [°C]"], rangees))
    return blocs


def _pas_thermique(r: ResultatVerification) -> list[Bloc]:
    """Un pas de l'intégration, refait à la main au voisinage de l'échéance."""
    th = r.thermique
    temps = th.temps
    dt = temps[1] - temps[0]
    i = max(1, min(len(temps) - 2, int(r.duree_requise / dt) - 1))
    t, theta_a = temps[i], th.temperatures[i]
    theta_g = r.courbe.temperature(t)
    delta_g = r.courbe.temperature(t + dt) - theta_g
    c_a = chaleur_specifique(theta_a)
    tm = _txt(en_minutes(t), 2)
    blocs = [_para(
        f"Les équations sont intégrées pas à pas (Δt = {dt:.0f} s). Pour rendre le "
        f"calcul contrôlable, le pas à t = {tm} min est refait ci-dessous."
    )]
    blocs.append(_calcul(
        "Chaleur spécifique de l'acier", "EN 1993-1-2 §3.4.1.2, éq. (3.2a)",
        rf"c_a(\theta_a = {n(theta_a, 1)}\ \mathrm{{°C}}) = \mathbf{{{n(c_a, 1)}"
        r"\ \mathrm{J/(kg\cdot K)}}",
    ))
    protection = r.protection
    d_p = protection.epaisseur_saine(t) if protection is not None else 0.0
    perdue = protection is not None and protection.combustible and d_p < EPAISSEUR_SAINE_MIN

    if protection is None or perdue:
        alpha_c = r.courbe.alpha_c
        h_c = flux_convectif(theta_g, theta_a, alpha_c)
        h_r = flux_radiatif(theta_g, theta_a, EPSILON_ACIER_CARBONE, EPSILON_FEU, PHI_DEFAUT)
        Am = th.Am_sur_V
        k_sh = th.k_sh
        if perdue:
            from .profils.geometrie import Exposition, facteur_massivete, facteur_ombre

            nue = (Exposition.CONTOUR_3_FACES if r.exposition.trois_faces
                   else Exposition.CONTOUR_4_FACES)
            Am = facteur_massivete(r.profil, nue)
            k_sh = facteur_ombre(r.profil, nue, feu_nominal=r.courbe.nominale)
        delta = k_sh * Am / (c_a * RHO_A) * (h_c + h_r) * dt
        blocs += [
            _calcul(
                "Flux net", "EN 1991-1-2 §3.1, éq. (3.2) et (3.3)",
                rf"\dot{{h}}_{{net,c}} = \alpha_c\,(\theta_g - \theta_a) = {n(alpha_c, 0)}"
                rf"\cdot ({n(theta_g, 1)} - {n(theta_a, 1)}) = {n(h_c, 0)}\ \mathrm{{W/m^2}}",
                rf"\dot{{h}}_{{net,r}} = \Phi\,\varepsilon_m\,\varepsilon_f\,\sigma\,"
                rf"[(\theta_g+273)^4 - (\theta_a+273)^4] = {n(PHI_DEFAUT, 1)} \cdot"
                rf"{n(EPSILON_ACIER_CARBONE, 1)} \cdot {n(EPSILON_FEU, 1)} \cdot"
                rf"{n(SIGMA * 1e8, 2)} \cdot 10^{{-8}} \cdot [{n(theta_g + 273, 1)}^4 -"
                rf"{n(theta_a + 273, 1)}^4] = {n(h_r, 0)}\ \mathrm{{W/m^2}}",
            ),
            _calcul(
                "Incrément de température, acier nu", EC3_ECHAUFFEMENT_NU.courte,
                r"\Delta\theta_{a,t} = k_{sh}\,\dfrac{A_m/V}{c_a\,\rho_a}\,"
                r"\dot{h}_{net}\,\Delta t",
                rf"\Delta\theta_{{a,t}} = {n(k_sh)} \cdot \dfrac{{{n(Am, 1)}}}"
                rf"{{{n(c_a, 1)} \cdot {RHO_A:.0f}}} \cdot {n(h_c + h_r, 0)} \cdot {dt:.0f}"
                rf" = \mathbf{{{n(delta, 3)}\ \mathrm{{K}}}}",
            ),
        ]
        if perdue:
            blocs.insert(1, _para(
                "À cet instant la protection combustible est perdue : l'acier est "
                "calculé nu, exposé en contour."
            ))
    else:
        Ap = th.Am_sur_V
        lam_p = protection.conductivite(theta_a)
        phi = protection.c_p * protection.rho_p / (c_a * RHO_A) * d_p * Ap
        brut = (lam_p * Ap / (d_p * c_a * RHO_A) * (theta_g - theta_a) / (1 + phi / 3) * dt
                - (math.exp(phi / 10) - 1) * delta_g)
        if protection.combustible:
            blocs.append(_calcul(
                "Épaisseur de bois sain", f"{EC5_CARBONISATION.courte}, {EC5_BETA_N.courte}",
                r"d(t) = d_p - \beta_n\,t",
                rf"d = {n(protection.d_p * 1e3, 1)} - {n(protection.beta_n * 6e4, 2)}"
                rf"\cdot {n(en_minutes(t), 2)} = \mathbf{{{n(d_p * 1e3, 1)}\ \mathrm{{mm}}}}",
            ))
        blocs += [
            _calcul(
                "Rapport des capacités thermiques", EC3_PHI_PROTECTION.courte,
                r"\phi = \dfrac{c_p\,\rho_p}{c_a\,\rho_a}\,d_p\,A_p/V",
                rf"\phi = \dfrac{{{protection.c_p:.0f} \cdot {protection.rho_p:.0f}}}"
                rf"{{{n(c_a, 1)} \cdot {RHO_A:.0f}}} \cdot {n(d_p, 4)} \cdot {n(Ap, 1)}"
                rf" = \mathbf{{{n(phi, 4)}}}",
            ),
            _calcul(
                "Incrément de température, acier protégé", EC3_ECHAUFFEMENT_PROTEGE.courte,
                r"\Delta\theta_{a,t} = \dfrac{\lambda_p\,A_p/V}{d_p\,c_a\,\rho_a}\,"
                r"\dfrac{\theta_{g,t} - \theta_{a,t}}{1 + \phi/3}\,\Delta t"
                r" - (e^{\phi/10} - 1)\,\Delta\theta_{g,t}",
                rf"\Delta\theta_{{a,t}} = \dfrac{{{n(lam_p, 3)} \cdot {n(Ap, 1)}}}"
                rf"{{{n(d_p, 4)} \cdot {n(c_a, 1)} \cdot {RHO_A:.0f}}} \cdot "
                rf"\dfrac{{{n(theta_g, 1)} - {n(theta_a, 1)}}}{{1 + {n(phi, 4)}/3}}"
                rf"\cdot {dt:.0f} - (e^{{{n(phi, 4)}/10}} - 1) \cdot {n(delta_g, 3)}",
                rf"\Delta\theta_{{a,t}} = \mathbf{{{n(max(brut, 0.0), 3)}\ \mathrm{{K}}}}",
            ),
        ]
    reel = th.temperatures[i + 1] - theta_a
    blocs.append(_para(
        f"Contrôle : l'historique calculé donne θ_a = {_txt(theta_a, 2)} °C puis "
        f"{_txt(th.temperatures[i + 1], 2)} °C, soit un incrément de "
        f"{_txt(reel, 3)} K."
    ))
    return blocs


def _verdict(r: ResultatVerification) -> list[Bloc]:
    duree = en_minutes(r.duree_requise)
    t_fi = (f"{_txt(r.t_fi_d_minutes, 1)} min" if r.t_fi_d_minutes is not None
            else f"> {en_minutes(r.thermique.duree):.0f} min")
    signe = r"\leq" if r.theta_a_a_echeance <= r.theta_cr else ">"
    t_fi_math = t_fi.replace(",", "{,}").replace(" ", r"\ ")
    blocs = [
        _titre("10. Vérification"),
        _calcul(
            f"Critère en température à R{duree:.0f}", "EN 1993-1-2 §4.2.4",
            rf"\theta_a(t = {duree:.0f}\ \mathrm{{min}}) = {n(r.theta_a_a_echeance, 1)}"
            rf"\ \mathrm{{°C}}\ {signe}\ \theta_{{cr}} = {n(r.theta_cr, 1)}\ \mathrm{{°C}}",
            rf"\mathrm{{marge}} = {n(r.marge_temperature, 1)}\ \mathrm{{K}}"
            rf"\qquad t_{{fi,d}} = \mathrm{{{t_fi_math}}}",
        ),
        _para(f"Exigence R{duree:.0f} : {r.verdict.value.upper()}."),
    ]
    if r.avertissements:
        blocs.append(_titre("Avertissements"))
        blocs += [_para(f"• {a}") for a in r.avertissements]
    restantes = a_recouper()
    if restantes:
        blocs.append(_titre("Clauses restant à recouper"))
        blocs.append(_para(
            "Ces références proviennent de la connaissance du corpus normatif et "
            "n'ont pas été confrontées à un exemplaire officiel."
        ))
        blocs += [_para(f"• {ref.complete}") for ref in restantes]
    blocs.append(_para(
        "Note produite par Nommogramme. Cet outil ne constitue pas une "
        "justification de projet : les clauses et valeurs signalées restent à "
        "recouper avec les normes et les agréments des produits."
    ))
    return blocs


# --- mise en page --------------------------------------------------------------

_A4 = (8.27, 11.69)
_MARGE = 0.7
_ENCRE = "#17191C"
_DISCRET = "#666A70"
_ACCENT = "#0B4F6C"
_FILET = "#D6D4CC"


class _Composeur:
    """Place les blocs sur des pages A4 successives, en pouces depuis le haut."""

    def __init__(self, pdf, entete: str) -> None:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure

        self._Figure = Figure
        self._Canevas = FigureCanvasAgg
        self.pdf = pdf
        self.entete = entete
        self.page = None
        self.y = 0.0
        self.numero = 0
        brouillon = Figure(figsize=_A4)
        self._canevas_brouillon = FigureCanvasAgg(brouillon)
        self._brouillon = brouillon
        self.largeur = _A4[0] - 2 * _MARGE

    # -- mesures --

    def _mesure(self, texte: str, taille: float, **style) -> tuple[float, float]:
        artiste = self._brouillon.text(0, 0, texte, fontsize=taille, **style)
        boite = artiste.get_window_extent(renderer=self._canevas_brouillon.get_renderer())
        artiste.remove()
        return boite.width / self._brouillon.dpi, boite.height / self._brouillon.dpi

    # -- pages --

    def _nouvelle_page(self) -> None:
        self._fermer()
        self.page = self._Figure(figsize=_A4)
        self._Canevas(self.page)
        self.numero += 1
        self.page.text(_MARGE / _A4[0], 1 - 0.4 / _A4[1], self.entete,
                       fontsize=7.5, color=_DISCRET, va="top")
        self.page.text(1 - _MARGE / _A4[0], 0.35 / _A4[1], f"page {self.numero}",
                       fontsize=7.5, color=_DISCRET, ha="right")
        self.y = _MARGE

    def _fermer(self) -> None:
        if self.page is not None:
            self.pdf.savefig(self.page)
            self.page = None

    def _reserver(self, hauteur: float) -> None:
        if self.page is None or self.y + hauteur > _A4[1] - _MARGE:
            self._nouvelle_page()

    def _texte(self, x: float, texte: str, taille: float, **style):
        return self.page.text(x / _A4[0], 1 - self.y / _A4[1], texte,
                              fontsize=taille, va="top", **style)

    def _filet(self, y: float, couleur: str = _FILET, epaisseur: float = 0.6) -> None:
        from matplotlib.lines import Line2D

        hauteur = 1 - y / _A4[1]
        self.page.add_artist(Line2D(
            [_MARGE / _A4[0], 1 - _MARGE / _A4[0]], [hauteur, hauteur],
            transform=self.page.transFigure, color=couleur, linewidth=epaisseur,
        ))

    # -- blocs --

    def titre_document(self, titre: str, sous_titre: str, verdict: str, ok: bool) -> None:
        self._nouvelle_page()
        self._texte(_MARGE, "NOTE DE CALCUL — RÉSISTANCE AU FEU", 8, color=_DISCRET)
        self.y += 0.25
        self._texte(_MARGE, titre, 18, weight="bold", color=_ENCRE)
        self.y += 0.42
        for ligne in textwrap.wrap(sous_titre, 105):
            self._texte(_MARGE, ligne, 9.5, color=_DISCRET)
            self.y += 0.2
        self.y += 0.1
        self._texte(_MARGE, verdict, 12, weight="bold",
                    color="#2E7D32" if ok else "#B3261E")
        self.y += 0.32
        self._filet(self.y, _ENCRE, 1.2)
        self.y += 0.2

    def titre(self, texte: str) -> None:
        self._reserver(0.9)
        self.y += 0.12
        self._texte(_MARGE, texte, 12.5, weight="bold", color=_ACCENT)
        self.y += 0.28
        self._filet(self.y - 0.06)

    def paragraphe(self, texte: str) -> None:
        colonnes = int(self.largeur * 72 / (9.2 * 0.52))
        for ligne in textwrap.wrap(texte, colonnes) or [""]:
            self._reserver(0.19)
            self._texte(_MARGE, ligne, 9.2, color=_ENCRE)
            self.y += 0.18
        self.y += 0.06

    def calcul(self, bloc: Bloc) -> None:
        tailles = []
        hauteur = 0.25
        for ligne in bloc.lignes:
            taille = 11.0
            largeur, haut = self._mesure(f"${ligne}$", taille)
            while largeur > self.largeur - 0.3 and taille > 6.5:
                taille -= 0.5
                largeur, haut = self._mesure(f"${ligne}$", taille)
            tailles.append((taille, haut))
            hauteur += haut + 0.1
        self._reserver(hauteur + 0.1)
        self._texte(_MARGE, bloc.texte, 9.2, weight="bold", color=_ENCRE)
        if bloc.reference:
            self._texte(_A4[0] - _MARGE, bloc.reference, 7.8, color=_DISCRET, ha="right")
        self.y += 0.23
        for ligne, (taille, haut) in zip(bloc.lignes, tailles):
            self._texte(_MARGE + 0.25, f"${ligne}$", taille, color=_ENCRE)
            self.y += haut + 0.1
        self.y += 0.08

    def tableau(self, bloc: Bloc) -> None:
        colonnes = len(bloc.entetes)
        largeurs = [
            max([self._mesure(str(c[j]), 8.8)[0] for c in bloc.rangees + [bloc.entetes]])
            + 0.25
            for j in range(colonnes)
        ]
        echelle = min(1.0, self.largeur / sum(largeurs))
        positions = [_MARGE]
        for largeur in largeurs[:-1]:
            positions.append(positions[-1] + largeur * echelle)
        pas = 0.21
        # Un tableau court reste d'un seul tenant ; un long peut se couper.
        lignes = len(bloc.rangees) + 1
        self._reserver(pas * lignes + 0.12 if lignes <= 25 else pas * 6)
        for j, entete in enumerate(bloc.entetes):
            self._texte(positions[j], entete, 8.4, weight="bold", color=_DISCRET)
        self.y += pas
        self._filet(self.y - 0.05)
        for rangee in bloc.rangees:
            self._reserver(pas)
            for j, cellule in enumerate(rangee):
                self._texte(positions[j], str(cellule), 8.8, color=_ENCRE)
            self.y += pas
        self.y += 0.12

    def figure(self, figure, legende: str) -> None:
        """Insère une figure matplotlib, rastérisée, à la largeur utile."""
        tampon = io.BytesIO()
        figure.savefig(tampon, format="png", dpi=200, bbox_inches="tight",
                       facecolor="white")
        tampon.seek(0)
        import matplotlib.image as mpimg

        image = mpimg.imread(tampon)
        hauteur_px, largeur_px = image.shape[:2]
        largeur = self.largeur
        hauteur = largeur * hauteur_px / largeur_px
        if hauteur > _A4[1] - 2 * _MARGE - 0.6:
            hauteur = _A4[1] - 2 * _MARGE - 0.6
            largeur = hauteur * largeur_px / hauteur_px
        self._reserver(hauteur + 0.45)
        axes = self.page.add_axes([
            _MARGE / _A4[0], 1 - (self.y + hauteur) / _A4[1],
            largeur / _A4[0], hauteur / _A4[1],
        ])
        axes.imshow(image)
        axes.axis("off")
        self.y += hauteur + 0.08
        self._texte(_MARGE, legende, 8.4, color=_DISCRET, style="italic")
        self.y += 0.35

    def terminer(self) -> None:
        self._fermer()


def note_pdf(r: ResultatVerification, chemin, section=None):
    """Écrit la note de calcul détaillée en PDF, figures comprises.

    ``chemin`` est un chemin de fichier, ou un flux binaire ouvert (l'interface
    web télécharge depuis la mémoire). ``section`` est la section soudée
    d'origine, facultative : elle ajoute le détail des tôles et la coupe cotée.
    """
    from matplotlib.backends.backend_pdf import PdfPages

    from .nomogramme.trace import tracer_echauffement, tracer_nomogramme, tracer_section

    if isinstance(chemin, (str, Path)):
        chemin = Path(chemin)
        chemin.parent.mkdir(parents=True, exist_ok=True)
    duree = en_minutes(r.duree_requise)
    entete = f"Nommogramme — {r.profil.nom} — R{duree:.0f} — {date.today():%d.%m.%Y}"

    with PdfPages(chemin) as pdf:
        info = pdf.infodict()
        info["Title"] = f"Note de calcul — {r.profil.nom} — R{duree:.0f}"
        info["Creator"] = "Nommogramme"

        page = _Composeur(pdf, entete)
        page.titre_document(
            f"Vérification au feu — {r.profil.nom}",
            f"{r.nuance.value} · {r.exposition.value} · {r.courbe.nom} · "
            f"{r.protection or 'sans protection'} · {r.contexte.nom}",
            f"{r.verdict.value.upper()} pour R{duree:.0f} — θ_cr = {r.theta_cr:.0f} °C, "
            f"θ_a = {r.theta_a_a_echeance:.0f} °C à {duree:.0f} min",
            bool(r.verdict),
        )
        for bloc in etapes_de_calcul(r, section):
            if bloc.genre == "titre":
                page.titre(bloc.texte)
            elif bloc.genre == "texte":
                page.paragraphe(bloc.texte)
            elif bloc.genre == "calcul":
                page.calcul(bloc)
            elif bloc.genre == "tableau":
                page.tableau(bloc)

        page._nouvelle_page()
        page.titre("Figures")
        for tracer, legende in (
            (tracer_nomogramme, "Nomogramme : μ₀ → θ_cr (gauche), échauffement (droite)."),
            (tracer_echauffement, "Échauffement de l'acier et des gaz."),
        ):
            figure = tracer(r)
            page.figure(figure, legende)
            _fermer_figure(figure)
        if section is not None:
            figure = tracer_section(section, exposition=r.exposition)
            page.figure(figure, "Coupe de la section soudée, à l'échelle.")
            _fermer_figure(figure)
        page.terminer()
    return chemin


def _fermer_figure(figure) -> None:
    import matplotlib.pyplot as plt

    plt.close(figure)
