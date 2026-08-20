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
from nommogramme.contexte import EUROCODE_REC, SUISSE_SIA
from nommogramme.materiaux.acier import Nuance
from nommogramme.materiaux.protection import Protection, charger_protections
from nommogramme.mecanique.actions import CasDeCharge
from nommogramme.nomogramme.trace import tracer_echauffement, tracer_nomogramme
from nommogramme.nomogramme.verification import ResultatVerification, verifier
from nommogramme.profils import Exposition, Famille, charger_csv
from nommogramme.thermique.courbes import COURBES
from nommogramme.unites import en_minutes, kN, kNm

__all__ = ["principal"]


_EXPOSITIONS = {
    "Contour, 4 faces": Exposition.CONTOUR_4_FACES,
    "Contour, 3 faces": Exposition.CONTOUR_3_FACES,
    "Caisson, 4 faces": Exposition.CAISSON_4_FACES,
    "Caisson, 3 faces": Exposition.CAISSON_3_FACES,
}

_CONTEXTES = {
    "Suisse — SIA 263 / SIA 260": SUISSE_SIA,
    "Eurocode — valeurs recommandées": EUROCODE_REC,
}

_DUREES = [15, 30, 60, 90, 120, 180]

_LIEN_VALIDATION = (
    "https://github.com/damthon/Nommogramme/blob/main/docs/validation.md"
)


@st.cache_data(show_spinner=False)
def _catalogue_noms() -> dict[str, list[str]]:
    """Noms de profilés par famille, mis en cache entre les interactions."""
    catalogue = charger_csv()
    return {
        famille.value: [p.nom for p in catalogue.famille(famille)]
        for famille in Famille
    }


@st.cache_resource(show_spinner=False)
def _catalogue():
    return charger_csv()


def _theme_figures() -> str:
    """Aligne les figures sur le thème de Streamlit."""
    return "sombre" if st.get_option("theme.base") == "dark" else "clair"


# --- saisie -------------------------------------------------------------------


def _saisie() -> dict:
    """Collecte les paramètres dans la barre latérale."""
    st.sidebar.header("Élément")

    noms = _catalogue_noms()
    familles = [f for f, liste in noms.items() if liste]
    famille = st.sidebar.selectbox(
        "Famille", familles, key="famille",
        index=familles.index("HEB") if "HEB" in familles else 0,
    )
    liste = noms[famille]
    profil = st.sidebar.selectbox(
        "Profilé", liste, key="profil",
        index=liste.index("HEB300") if "HEB300" in liste else len(liste) // 2,
    )
    nuance = st.sidebar.selectbox(
        "Nuance", [n.value for n in Nuance], key="nuance",
        index=[n.value for n in Nuance].index("S355"),
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
    L = st.sidebar.number_input("Longueur d'épure L  [m]", value=4.0, min_value=0.0, step=0.5, key="L")
    st.sidebar.caption(
        "Poteau continu d'un contreventement : l_fi = 0,5·L en étage courant, "
        "0,7·L au dernier étage (§4.2.3.2(4))."
    )
    l_fi = st.sidebar.number_input(
        "Longueur de flambement l_fi  [m]", value=2.0, min_value=0.0, step=0.5,
        key="l_fi",
    )
    maintien = st.sidebar.checkbox(
        "Semelle comprimée maintenue latéralement", key="maintien",
        help="Écarte le critère de déversement de l'éq. (4.21b), que le "
             "§4.2.3.5 n'impose qu'aux éléments pour lesquels le déversement "
             "est un mode de ruine potentiel.",
    )
    beta_M = st.sidebar.number_input(
        "β_M  [-]", value=1.4, key="beta_M", min_value=1.0, max_value=2.5, step=0.1,
        help="Facteur de moment uniforme équivalent, figure 4.2. "
             "1,3 charge répartie · 1,4 charge concentrée · "
             "1,8 − 0,7·ψ diagramme linéaire.",
    )

    st.sidebar.header("Exposition au feu")
    exposition = st.sidebar.selectbox("Configuration", list(_EXPOSITIONS), key="exposition")
    feu = st.sidebar.selectbox(
        "Courbe de feu", list(COURBES), key="feu",
        format_func=lambda cle: COURBES[cle].nom,
    )
    duree = st.sidebar.select_slider(
        "Durée exigée  [min]", options=_DUREES, value=60, key="duree"
    )

    st.sidebar.header("Protection")
    produits = charger_protections()
    choix = st.sidebar.selectbox(
        "Produit", ["Aucune"] + sorted(produits), key="produit",
        format_func=lambda cle: (
            "Aucune" if cle == "Aucune" else produits[cle].get("libelle", cle)
        ),
    )
    epaisseur = None
    if choix != "Aucune":
        fiche = produits[choix]
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
        contexte = st.selectbox("Référentiel", list(_CONTEXTES), key="contexte")
        kappa_1 = st.number_input(
            "κ₁  [-]", value=1.00, key="kappa_1", min_value=0.5, max_value=1.0, step=0.05,
            help="1,00 exposée 4 faces · 0,70 sur 3 faces avec dalle béton · "
                 "0,85 sur 3 faces avec dalle mixte (§4.2.3.3).",
        )
        kappa_2 = st.number_input(
            "κ₂  [-]", value=1.00, key="kappa_2", min_value=0.5, max_value=1.0, step=0.05,
            help="0,85 aux appuis d'une poutre hyperstatique, 1,00 sinon.",
        )
        C1 = st.number_input(
            "C₁  [-]", value=1.00, key="C1", min_value=1.0, max_value=2.8, step=0.05,
            help="Facteur de forme du diagramme de moment, pour le moment "
                 "critique de déversement. 1,0 = moment constant, le plus "
                 "défavorable.",
        )

    return dict(
        profil=profil, nuance=nuance, N=N, My=My, Mz=Mz, L=L, l_fi=l_fi,
        maintien=maintien, beta_M=beta_M, exposition=exposition, feu=feu,
        duree=duree, protection=choix, epaisseur=epaisseur,
        contexte=contexte, kappa_1=kappa_1, kappa_2=kappa_2, C1=C1,
    )


def _verifier(saisie: dict) -> ResultatVerification:
    """Traduit la saisie en appel de bibliothèque. Aucun calcul ici."""
    protection = None
    if saisie["protection"] != "Aucune":
        protection = Protection.depuis_catalogue(
            saisie["protection"], d_p=saisie["epaisseur"] * 1e-3
        )

    cas = CasDeCharge(
        N_fi_Ed=kN(saisie["N"]),
        My_fi_Ed=kNm(saisie["My"]),
        Mz_fi_Ed=kNm(saisie["Mz"]),
        L=saisie["L"],
        l_fi_y=saisie["l_fi"] or None,
        l_fi_z=saisie["l_fi"] or None,
        beta_M_y=saisie["beta_M"],
        beta_M_z=saisie["beta_M"],
        beta_M_LT=saisie["beta_M"],
        maintien_lateral=saisie["maintien"],
    )

    return verifier(
        profil=_catalogue()[saisie["profil"]],
        nuance=Nuance(saisie["nuance"]),
        cas=cas,
        exposition=_EXPOSITIONS[saisie["exposition"]],
        duree_requise_min=float(saisie["duree"]),
        protection=protection,
        courbe=COURBES[saisie["feu"]],
        contexte=_CONTEXTES[saisie["contexte"]],
        kappa_1=saisie["kappa_1"],
        kappa_2=saisie["kappa_2"],
        C1=saisie["C1"],
    )


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
    colonnes[0].metric("μ₀", f"{r.mu_0:.3f}", help="Degré d'utilisation à 20 °C, éq. (4.23)")
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
        "Nomogramme — éq. (4.22)",
        f"{r.theta_cr_nomogramme:.0f} °C" if r.theta_cr_nomogramme else "—",
    )
    # Le delta n'est montré que lorsque les deux voies divergent vraiment :
    # un écart de 1 °C est le cas normal, l'afficher en rouge serait alarmiste.
    ecart_notable = r.ecart_nomogramme is not None and r.ecart_nomogramme > 5.0
    droite.metric(
        "Vérification croisée — §4.2.3",
        f"{r.theta_cr_exact:.0f} °C" if r.theta_cr_exact else "—",
        delta=f"-{r.ecart_nomogramme:.0f} °C" if ecart_notable else None,
        help="Température à laquelle le taux d'utilisation complet atteint 1, "
             "χ_fi et interaction N + M compris.",
    )
    if r.ecart_nomogramme is not None and r.ecart_nomogramme > 10.0:
        st.warning(
            f"L'équation (4.22) donne {r.ecart_nomogramme:.0f} °C de plus que la "
            "vérification complète : l'instabilité gouverne, et le nomogramme seul "
            "serait non conservatif. C'est la valeur basse qui est retenue."
        )
    st.caption(f"Critère gouvernant : {r.gouverne_par} · {r.classification}")


def _figures(r: ResultatVerification) -> None:
    theme = _theme_figures()
    nomogramme, echauffement = st.tabs(["Nomogramme", "Échauffement"])
    with nomogramme:
        st.pyplot(tracer_nomogramme(r, theme=theme))
        st.caption(
            "Les deux quadrants partagent l'axe des températures. Le chemin de "
            "lecture part de μ₀, remonte à la courbe (4.22), traverse et "
            "redescend sur l'axe des temps."
        )
    with echauffement:
        st.pyplot(tracer_echauffement(r, theme=theme))


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

    _figures(resultat)
    _note(resultat)

    st.divider()
    st.caption(
        "**Outil en développement.** Seule la chaîne de l'élément comprimé "
        "protégé est recoupée avec une référence externe ; la flexion, le "
        "déversement, l'interaction N + M et les éléments non protégés ne le "
        f"sont pas — voir [validation.md]({_LIEN_VALIDATION}). "
        "Il ne constitue pas une justification de projet. Les propriétés des "
        "produits de protection sont des valeurs génériques, à remplacer par "
        "celles de l'agrément technique du produit retenu."
    )


if __name__ == "__main__":
    principal()
else:  # pragma: no cover - Streamlit importe le module puis l'exécute
    if st.runtime.exists():
        principal()
