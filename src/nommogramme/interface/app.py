"""Interface graphique Streamlit.

Couche de présentation, et rien d'autre. Ce module ne contient **aucun
calcul** : il collecte des valeurs dans des widgets, les convertit en unités
SI, appelle ``verifier()``, et affiche ce qui en revient. Les figures viennent
de ``nomogramme.trace``, la note de calcul de ``rapport``.

C'est la même contrainte que pour la ligne de commande, et pour la même
raison : deux surfaces qui recalculeraient chacune de leur côté finiraient par
diverger, et il faudrait alors se demander laquelle a raison.

Lancement :

    nommo interface

ou directement :

    streamlit run src/nommogramme/interface/app.py
"""

from __future__ import annotations

import streamlit as st

# Imports absolus, et non relatifs : « streamlit run » exécute ce fichier
# comme un script isolé, sans paquet parent, ce qui ferait échouer un
# « from ..contexte import … ». Le paquet étant installé, la forme absolue
# fonctionne quel que soit le mode de lancement.
from nommogramme.interface.saisie import (
    CONTEXTES as _CONTEXTES,
)
from nommogramme.interface.saisie import (
    DUREES as _DUREES,
)
from nommogramme.interface.saisie import (
    EXPOSITIONS as _EXPOSITIONS,
)
from nommogramme.interface.saisie import (
    AIDES,
    CATALOGUE,
    FACES_COUVERTES,
    H_SOUDE,
    SANS_PROTECTION,
    TYPES_SECTION,
    Saisie,
    executer,
    noms_par_famille,
    produits,
)
from nommogramme.materiaux.acier import Nuance
from nommogramme.nomogramme.trace import (
    tracer_echauffement,
    tracer_nomogramme,
    tracer_section,
)
from nommogramme.nomogramme.verification import ResultatVerification
from nommogramme.references import EC3_MU_0, EC3_RESISTANCES, EC3_THETA_CR
from nommogramme.thermique.courbes import COURBES
from nommogramme.unites import en_minutes

__all__ = ["principal"]

_LIEN_VALIDATION = (
    "https://github.com/damthon/Nommogramme/blob/main/docs/validation.md"
)


@st.cache_data(show_spinner=False)
def _theme_figures() -> str:
    """Aligne les figures sur le thème de Streamlit."""
    return "sombre" if st.get_option("theme.base") == "dark" else "clair"


# --- saisie -------------------------------------------------------------------


def _section_soudee(defaut: Saisie, type_section: str) -> dict[str, float | str]:
    """Les dimensions d'une section reconstituée, en millimètres.

    Les mêmes champs servent aux deux formes sans désigner la même chose :
    ``b`` est la largeur du caisson ou celle de la semelle supérieure du H.
    Les libellés changent donc avec le type retenu.
    """
    en_h = type_section == H_SOUDE
    st.sidebar.caption(
        "Cotes en millimètres. Les gorges de soudure et les congés sont "
        "négligés, ce qui minore l'aire comme le périmètre exposé."
    )
    dimensions: dict[str, float | str] = {
        "h_soudee": st.sidebar.number_input(
            "h — hauteur totale  [mm]", value=defaut.h_soudee,
            min_value=20.0, step=10.0, key="h_soudee",
        ),
        "b_soudee": st.sidebar.number_input(
            "b_sup — semelle supérieure  [mm]" if en_h else "b — largeur  [mm]",
            value=defaut.b_soudee, min_value=10.0, step=10.0, key="b_soudee",
        ),
        "tf_soudee": st.sidebar.number_input(
            "t_f,sup  [mm]" if en_h else "t_f — semelles  [mm]",
            value=defaut.tf_soudee, min_value=1.0, step=1.0, key="tf_soudee",
        ),
        "tw_soudee": st.sidebar.number_input(
            "t_w — âme  [mm]" if en_h else "t_w — âmes  [mm]",
            value=defaut.tw_soudee, min_value=1.0, step=1.0, key="tw_soudee",
        ),
    }
    if en_h:
        dimensions["b_inf_soudee"] = st.sidebar.number_input(
            "b_inf — semelle inférieure  [mm]", value=defaut.b_inf_soudee,
            min_value=10.0, step=10.0, key="b_inf_soudee",
        )
        dimensions["tf_inf_soudee"] = st.sidebar.number_input(
            "t_f,inf  [mm]", value=defaut.tf_inf_soudee,
            min_value=1.0, step=1.0, key="tf_inf_soudee",
        )
        dimensions["face_couverte"] = st.sidebar.selectbox(
            "Dalle sur", list(FACES_COUVERTES), key="face_couverte",
            help=AIDES["face_couverte"],
        )
    return dimensions


def _saisie() -> Saisie:
    """Collecte les paramètres dans la barre latérale."""
    defaut = Saisie()
    st.sidebar.header("Élément")

    type_section = st.sidebar.selectbox(
        "Type de section", list(TYPES_SECTION), key="type_section",
        help=AIDES["type_section"],
    )

    noms = noms_par_famille()
    familles = list(noms)
    profil = defaut.profil
    dimensions: dict[str, float | str] = {}
    if type_section == CATALOGUE:
        famille = st.sidebar.selectbox(
            "Famille", familles, key="famille",
            index=familles.index("HEB") if "HEB" in familles else 0,
        )
        liste = list(noms[famille])
        profil = st.sidebar.selectbox(
            "Profilé", liste, key="profil",
            index=liste.index("HEB300") if "HEB300" in liste else len(liste) // 2,
        )
    else:
        dimensions = _section_soudee(defaut, type_section)

    nuance = st.sidebar.selectbox(
        "Nuance", [n.value for n in Nuance], key="nuance",
        index=[n.value for n in Nuance].index("S355"),
        help=AIDES["nuance"],
    )

    st.sidebar.header("Sollicitations en incendie")
    st.sidebar.caption(
        "Combinaison accidentelle, pas l'ELU fondamental. "
        "N positif en compression."
    )
    N = st.sidebar.number_input("N_fi,Ed  [kN]", value=850.0, step=50.0, key="N")
    My = st.sidebar.number_input("M_y,fi,Ed  [kN·m]", value=120.0, min_value=0.0, step=10.0, key="My")
    Mz = st.sidebar.number_input("M_z,fi,Ed  [kN·m]", value=0.0, min_value=0.0, step=10.0, key="Mz")

    st.sidebar.header("Géométrie")
    L = st.sidebar.number_input(
        "Vide d'étage L  [m]", value=4.0, min_value=0.0, step=0.5, key="L",
        help=AIDES["L"],
    )
    st.sidebar.caption(
        "Poteau continu d'un contreventement : l_fi = 0,5·L en étage courant, "
        "0,7·L au dernier étage."
    )
    l_fi = st.sidebar.number_input(
        "Longueur de flambement l_fi  [m]", value=2.0, min_value=0.0, step=0.5,
        key="l_fi", help=AIDES["l_fi"],
    )
    maintien = st.sidebar.checkbox(
        "Semelle comprimée maintenue latéralement", key="maintien",
        help=AIDES["maintien"],
    )
    beta_M = st.sidebar.number_input(
        "β_M  [-]", value=1.4, key="beta_M", min_value=1.0, max_value=2.5, step=0.1,
        help=AIDES["beta_M"],
    )

    st.sidebar.header("Exposition au feu")
    exposition = st.sidebar.selectbox(
        "Configuration", list(_EXPOSITIONS), key="exposition",
        help=AIDES["exposition"],
    )
    feu = st.sidebar.selectbox(
        "Courbe de feu", list(COURBES), key="feu",
        format_func=lambda cle: COURBES[cle].nom,
        help=AIDES["feu"],
    )
    duree = st.sidebar.select_slider(
        "Durée exigée  [min]", options=list(_DUREES), value=60, key="duree"
    )

    st.sidebar.header("Protection")
    fiches = produits()
    choix = st.sidebar.selectbox(
        "Produit", [SANS_PROTECTION] + sorted(fiches), key="produit",
        format_func=lambda cle: (
            SANS_PROTECTION if cle == SANS_PROTECTION
            else fiches[cle].get("libelle", cle)
        ),
    )
    epaisseur = None
    if choix != SANS_PROTECTION:
        fiche = fiches[choix]
        epaisseur = st.sidebar.number_input(
            "Épaisseur d_p  [mm]", key="dp",
            value=float(fiche["dp_min"] * 1e3),
            min_value=0.1, step=1.0,
        )
        st.sidebar.caption(
            f"λ_p = {fiche['lambda_p']} W/m·K · ρ_p = {fiche['rho_p']:.0f} kg/m³ · "
            f"c_p = {fiche['c_p']:.0f} J/kg·K · pose {fiche['pose']}. "
            "Valeurs génériques, à remplacer par celles de l'agrément du produit."
        )

    with st.sidebar.expander("Paramètres avancés"):
        contexte = st.selectbox(
            "Référentiel", list(_CONTEXTES), key="contexte", help=AIDES["contexte"]
        )
        kappa_1 = st.number_input(
            "κ₁  [-]", value=1.00, key="kappa_1", min_value=0.5, max_value=1.0, step=0.05,
            help=AIDES["kappa_1"],
        )
        kappa_2 = st.number_input(
            "κ₂  [-]", value=1.00, key="kappa_2", min_value=0.5, max_value=1.0, step=0.05,
            help=AIDES["kappa_2"],
        )
        C1 = st.number_input(
            "C₁  [-]", value=1.00, key="C1", min_value=1.0, max_value=2.8, step=0.05,
            help=AIDES["C1"],
        )

    return Saisie(
        profil=profil, nuance=nuance, type_section=type_section,
        N=N, My=My, Mz=Mz, L=L, l_fi=l_fi,
        maintien=maintien, beta_M=beta_M, exposition=exposition, feu=feu,
        duree=duree, protection=choix, epaisseur=epaisseur,
        contexte=contexte, kappa_1=kappa_1, kappa_2=kappa_2, C1=C1,
        **dimensions,
    )


def _verifier(saisie: Saisie) -> ResultatVerification:
    """Délègue à ``saisie.executer()`` — la traduction est partagée.

    Streamlit et l'interface de bureau passent par le même point : deux
    conversions d'unités écrites séparément finiraient par diverger.
    """
    return executer(saisie)


# --- affichage ----------------------------------------------------------------


def _verdict(r: ResultatVerification) -> None:
    duree = en_minutes(r.duree_requise)
    message = (
        f"**R{duree:.0f} {r.verdict.value}** — "
        f"θ_a = {r.theta_a_a_echeance:.0f} °C à l'échéance "
        f"contre θ_cr = {r.theta_cr:.0f} °C, "
        f"soit une marge de {r.marge_temperature:+.0f} °C."
    )
    (st.success if r.verdict else st.error)(message)


def _indicateurs(r: ResultatVerification) -> None:
    duree = en_minutes(r.duree_requise)
    colonnes = st.columns(4)
    colonnes[0].metric(
        "μ₀", f"{r.mu_0:.3f}",
        help=f"Degré d'utilisation à 20 °C — {EC3_MU_0.courte}",
    )
    colonnes[1].metric("θ_cr retenue", f"{r.theta_cr:.0f} °C", help=r.source_theta_cr)
    colonnes[2].metric(f"θ_a à R{duree:.0f}", f"{r.theta_a_a_echeance:.0f} °C")
    colonnes[3].metric(
        "t_fi,d",
        f"{r.t_fi_d_minutes:.0f} min" if r.t_fi_d_minutes is not None else "non atteinte",
        help="Durée avant que l'acier n'atteigne la température critique",
    )


def _temperatures_critiques(r: ResultatVerification) -> None:
    st.subheader("Les deux voies")
    gauche, droite = st.columns(2)
    gauche.metric(
        f"Nomogramme — {EC3_THETA_CR.courte}",
        f"{r.theta_cr_nomogramme:.0f} °C" if r.theta_cr_nomogramme else "—",
        help=EC3_THETA_CR.complete,
    )
    # Le delta n'est montré que lorsque les deux voies divergent vraiment :
    # un écart de 1 °C est le cas normal, l'afficher en rouge serait alarmiste.
    ecart_notable = r.ecart_nomogramme is not None and r.ecart_nomogramme > 5.0
    droite.metric(
        f"Vérification croisée — {EC3_RESISTANCES.courte}",
        f"{r.theta_cr_exact:.0f} °C" if r.theta_cr_exact else "—",
        delta=f"-{r.ecart_nomogramme:.0f} °C" if ecart_notable else None,
        help=EC3_RESISTANCES.infobulle(
            "Température à laquelle le taux d'utilisation complet atteint 1, "
            "χ_fi et interaction N + M compris."
        ),
    )
    if r.ecart_nomogramme is not None and r.ecart_nomogramme > 10.0:
        st.warning(
            f"L'{EC3_THETA_CR.courte} donne {r.ecart_nomogramme:.0f} °C de plus "
            "que la vérification complète : l'instabilité gouverne, et le "
            "nomogramme seul serait non conservatif. C'est la valeur basse qui "
            "est retenue."
        )
    st.caption(f"Critère gouvernant : {r.gouverne_par} · {r.classification}")


def _figures(r: ResultatVerification, saisie: Saisie) -> None:
    theme = _theme_figures()
    section = saisie.section()
    titres = ["Nomogramme", "Échauffement"]
    if section is not None:
        titres.append("Coupe de la section")
    onglets = st.tabs(titres)

    with onglets[0]:
        st.pyplot(tracer_nomogramme(r, theme=theme))
        st.caption(
            "Les deux quadrants partagent l'axe des températures. Le chemin de "
            f"lecture part de μ₀, remonte à la courbe de l'{EC3_THETA_CR.courte}, "
            "traverse et redescend sur l'axe des temps."
        )
    with onglets[1]:
        st.pyplot(tracer_echauffement(r, theme=theme))
    if section is not None:
        with onglets[2]:
            st.pyplot(
                tracer_section(section, theme=theme, exposition=r.exposition)
            )
            st.caption(
                "Coupe à l'échelle. Une saisie fautive d'un facteur dix se voit "
                "ici, et pas dans un tableau de nombres."
            )


def _note(r: ResultatVerification) -> None:
    note = r.note_de_calcul()
    st.download_button(
        "Télécharger la note de calcul",
        data=note.encode("utf-8"),
        file_name=f"note-{r.profil.nom.replace(' ', '')}-R"
                  f"{en_minutes(r.duree_requise):.0f}.md",
        mime="text/markdown",
    )
    with st.expander("Voir la note de calcul"):
        st.markdown(note)


def principal() -> None:
    """Point d'entrée de l'application."""
    st.set_page_config(
        page_title="Nommogramme", page_icon="🔥", layout="wide",
    )

    st.title("Nommogramme")
    st.caption(
        "Résistance au feu de profilés métalliques par la méthode du "
        "nomogramme — SIA 263 et EN 1993-1-2."
    )

    saisie = _saisie()

    try:
        resultat = _verifier(saisie)
    except (KeyError, ValueError) as erreur:
        st.error(f"Saisie inexploitable : {erreur}")
        return

    _verdict(resultat)
    _indicateurs(resultat)
    _temperatures_critiques(resultat)

    for avertissement in resultat.avertissements:
        st.warning(avertissement)
    for reserve in saisie.controles_section():
        st.warning(reserve)

    _figures(resultat, saisie)
    _note(resultat)

    st.divider()
    st.caption(
        "**Outil en développement.** La compression et la flexion simple sont "
        "recoupées avec la documentation SZS steeltec 02:2015 ; le déversement "
        "et l'interaction N + M ne le sont pas — voir "
        f"[validation.md]({_LIEN_VALIDATION}). "
        "Il ne constitue pas une justification de projet. Les propriétés des "
        "produits de protection sont des valeurs génériques, à remplacer par "
        "celles de l'agrément technique du produit retenu."
    )


if __name__ == "__main__":
    principal()
else:  # pragma: no cover - Streamlit importe le module puis l'exécute
    if st.runtime.exists():
        principal()
