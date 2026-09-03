"""Le jeu de paramètres d'une vérification, et sa traduction en appel.

Ce module est le **point de traduction unique** entre ce qu'un utilisateur
saisit — des kN, des mm, des libellés — et ce que la bibliothèque attend : des
newtons, des mètres, des objets. Il ne contient aucun calcul de résistance au
feu ; il appelle ``verifier()``.

Pourquoi le sortir des interfaces
---------------------------------

Il y a deux surfaces graphiques, Streamlit et Tkinter, et une ligne de
commande. Si chacune convertissait ses propres kN en newtons et choisissait
elle-même quoi passer à ``verifier()``, elles finiraient par diverger — sur un
défaut, sur une unité, sur un paramètre oublié lors d'une évolution. Il
faudrait alors se demander laquelle a raison.

Elles partagent donc ``Saisie`` et ``executer()``. Une interface n'a plus qu'à
remplir des champs et afficher un résultat.

Les unités de ``Saisie`` sont celles de l'écran — kN, kN·m, mètres,
millimètres, minutes — et non les unités SI internes. C'est le seul endroit du
paquet où cette entorse est admise, et c'est sa raison d'être.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache

from nommogramme.contexte import EUROCODE_REC, SUISSE_SIA, ContexteNormatif
from nommogramme.materiaux.acier import Nuance
from nommogramme.materiaux.protection import Protection, charger_protections
from nommogramme.mecanique.actions import CasDeCharge
from nommogramme.nomogramme.verification import ResultatVerification, verifier
from nommogramme.profils import Catalogue, Exposition, Famille, Profil, charger_csv
from nommogramme.profils.composes import (
    FaceCouverte,
    SectionCaisson,
    SectionH,
    SectionSoudee,
)
from nommogramme.references import (
    EC1_COURBES,
    EC3_BETA_M,
    EC3_GAMMA_M_FI,
    EC3_INTERACTION_DEVERSEMENT,
    EC3_KAPPA,
    EC3_LONGUEUR_FLAMBEMENT,
    EC3_MASSIVETE,
    MCR_C1,
)
from nommogramme.thermique.courbes import COURBES
from nommogramme.unites import kN, kNm, mm

__all__ = [
    "AIDES",
    "CAISSON_SOUDE",
    "CATALOGUE",
    "CONTEXTES",
    "DUREES",
    "EXPOSITIONS",
    "FACES_COUVERTES",
    "H_SOUDE",
    "SANS_PROTECTION",
    "TYPES_SECTION",
    "Saisie",
    "catalogue",
    "executer",
    "noms_par_famille",
    "produits",
]


EXPOSITIONS: dict[str, Exposition] = {
    "Contour, 4 faces": Exposition.CONTOUR_4_FACES,
    "Contour, 3 faces": Exposition.CONTOUR_3_FACES,
    "Caisson, 4 faces": Exposition.CAISSON_4_FACES,
    "Caisson, 3 faces": Exposition.CAISSON_3_FACES,
}

CONTEXTES: dict[str, ContexteNormatif] = {
    "Suisse — SIA 263 / SIA 260": SUISSE_SIA,
    "Eurocode — valeurs recommandées": EUROCODE_REC,
}

DUREES: tuple[int, ...] = (15, 30, 60, 90, 120, 180)

SANS_PROTECTION = "Aucune"
"""Libellé de l'absence de protection, dans les listes déroulantes."""

CATALOGUE = "Profilé laminé (catalogue SZS)"
CAISSON_SOUDE = "Caisson rectangulaire soudé"
H_SOUDE = "Profilé en H soudé (PRS)"

TYPES_SECTION: tuple[str, ...] = (CATALOGUE, CAISSON_SOUDE, H_SOUDE)
"""Origines possibles de la section, dans l'ordre des listes déroulantes."""

FACES_COUVERTES: dict[str, FaceCouverte] = {
    "Semelle supérieure": FaceCouverte.SUPERIEURE,
    "Semelle inférieure": FaceCouverte.INFERIEURE,
}


AIDES: dict[str, str] = {
    "l_fi": EC3_LONGUEUR_FLAMBEMENT.infobulle(
        "Longueur de flambement en situation d'incendie. Un poteau continu "
        "d'un contreventement est bridé par les étages froids adjacents : sa "
        "longueur de flambement y est plus courte qu'à froid. Zéro reprend le "
        "vide d'étage."
    ),
    "L": (
        "Longueur d'épure de l'élément : le vide d'étage pour un poteau, la "
        "portée entre appuis pour une poutre. Sert de longueur de flambement "
        "par défaut."
    ),
    "maintien": EC3_INTERACTION_DEVERSEMENT.infobulle(
        "Semelle comprimée bloquée latéralement sur toute sa longueur, par "
        "exemple par une dalle solidaire. Écarte le critère de déversement, "
        "que la norme n'impose qu'aux éléments pour lesquels le déversement "
        "est un mode de ruine potentiel."
    ),
    "beta_M": EC3_BETA_M.infobulle(
        "Facteur de moment uniforme équivalent : il ramène un diagramme de "
        "moment quelconque au moment constant équivalent."
    ),
    "kappa_1": EC3_KAPPA.infobulle(
        "Facteur d'adaptation pour température non uniforme sur la section. "
        "Une poutre sous dalle est plus froide en semelle supérieure que ne "
        "le suppose l'hypothèse de température uniforme."
    ),
    "kappa_2": EC3_KAPPA.infobulle(
        "Facteur d'adaptation pour température non uniforme le long de la "
        "poutre."
    ),
    "C1": MCR_C1.infobulle(
        "Facteur de forme du diagramme de moment, au numérateur du moment "
        "critique élastique de déversement M_cr."
    ),
    "exposition": EC3_MASSIVETE.infobulle(
        "« Contour » suit la forme du profilé — élément nu, flocage, "
        "peinture. « Caisson » est un encaissement rectangulaire par "
        "plaques. Trois faces désigne une poutre dont une semelle est "
        "couverte par une dalle."
    ),
    "feu": EC1_COURBES.infobulle(
        "Courbe de feu nominale. ISO 834 est le feu normalisé des essais de "
        "résistance ; la courbe hydrocarbure est plus sévère, la courbe "
        "extérieure plus clémente."
    ),
    "contexte": EC3_GAMMA_M_FI.infobulle(
        "Référentiel : ce qui change entre pratique suisse et Eurocodes "
        "relève de l'encadrement — combinaison d'actions, facteurs partiels — "
        "et non des équations, communes aux deux."
    ),
    "nuance": (
        "Nuance d'acier. La limite d'élasticité décroît avec l'épaisseur de "
        "semelle, et cette décroissance est appliquée automatiquement."
    ),
    "face_couverte": EC3_MASSIVETE.infobulle(
        "Semelle que la dalle recouvre, en exposition sur trois faces. Sur "
        "une section à semelles inégales, se tromper de face fausse le "
        "périmètre exposé, donc l'échauffement."
    ),
    "type_section": (
        "Profilé du catalogue SZS, ou section reconstituée soudée dont vous "
        "donnez les dimensions. Une section soudée n'a ni congé de "
        "raccordement ni valeur tabulée : toutes ses caractéristiques sont "
        "calculées depuis les tôles, gorges de soudure négligées."
    ),
}
"""Textes d'aide des paramètres, partagés par les deux interfaces graphiques.

Ils vivent ici pour la même raison que la traduction des unités : écrits deux
fois, ils finiraient par diverger, et la référence normative affichée par une
interface ne serait plus celle affichée par l'autre.
"""


@lru_cache(maxsize=1)
def catalogue() -> Catalogue:
    """Le catalogue de profilés, chargé une seule fois."""
    return charger_csv()


@lru_cache(maxsize=1)
def noms_par_famille() -> dict[str, tuple[str, ...]]:
    """Noms de profilés par famille, dans l'ordre du catalogue."""
    cat = catalogue()
    return {
        famille.value: tuple(p.nom for p in cat.famille(famille))
        for famille in Famille
        if cat.famille(famille)
    }


@lru_cache(maxsize=1)
def produits() -> dict[str, dict]:
    """Les fiches de produits de protection."""
    return charger_protections()


@dataclass(frozen=True, slots=True)
class Saisie:
    """Un jeu de paramètres complet, dans les unités de l'écran.

    Les valeurs par défaut sont celles qui s'affichent à l'ouverture d'une
    interface. Elles décrivent un cas plausible et non trivial — un HEB 300
    comprimé et fléchi, R60, sans protection — plutôt qu'un cas vide : un
    écran qui s'ouvre déjà calculé se comprend plus vite qu'un formulaire
    blanc, et le premier profilé du catalogue sous 850 kN donnerait un degré
    d'utilisation absurde.
    """

    profil: str = "HEB300"
    nuance: str = "S355"

    type_section: str = CATALOGUE
    """Origine de la section : catalogue, caisson soudé ou H soudé."""

    # Dimensions d'une section soudée, en **millimètres**. Elles ne servent
    # que si ``type_section`` n'est pas le catalogue ; les valeurs par défaut
    # décrivent une section plausible, pour que l'écran montre tout de suite
    # un dessin plutôt qu'un cadre vide.
    h_soudee: float = 400.0
    """Hauteur totale [mm]."""
    b_soudee: float = 300.0
    """Largeur totale du caisson, ou de la semelle supérieure du H [mm]."""
    tf_soudee: float = 20.0
    """Épaisseur des semelles du caisson, ou de la semelle supérieure [mm]."""
    tw_soudee: float = 12.0
    """Épaisseur d'âme — les deux âmes, pour un caisson [mm]."""
    b_inf_soudee: float = 300.0
    """Largeur de la semelle inférieure du H [mm]. Ignorée pour un caisson."""
    tf_inf_soudee: float = 20.0
    """Épaisseur de la semelle inférieure du H [mm]. Ignorée pour un caisson."""
    face_couverte: str = "Semelle supérieure"
    """Semelle masquée par la dalle, en exposition sur trois faces."""

    N: float = 850.0
    """Effort normal [kN], **positif en compression**."""
    My: float = 120.0
    """Moment autour de l'axe fort [kN·m]."""
    Mz: float = 0.0
    """Moment autour de l'axe faible [kN·m]."""

    L: float = 4.0
    """Vide d'étage — longueur d'épure de l'élément [m]."""
    l_fi: float = 2.0
    """Longueur de flambement en situation d'incendie [m]. 0 ⇒ prendre L."""
    maintien: bool = False
    """Semelle comprimée maintenue latéralement — écarte le déversement."""
    beta_M: float = 1.4
    """Facteur de moment uniforme équivalent [-]."""

    exposition: str = "Contour, 4 faces"
    feu: str = "iso834"
    duree: int = 60
    """Durée de résistance exigée [min]."""

    protection: str = SANS_PROTECTION
    epaisseur: float | None = None
    """Épaisseur de protection [mm]. Ignorée sans protection."""

    contexte: str = "Suisse — SIA 263 / SIA 260"
    kappa_1: float = 1.0
    kappa_2: float = 1.0
    C1: float = 1.0

    def avec(self, **champs) -> Saisie:
        """Une copie, un ou plusieurs champs remplacés."""
        return replace(self, **champs)

    @property
    def protegee(self) -> bool:
        return self.protection != SANS_PROTECTION

    def fiche_protection(self) -> dict | None:
        """La fiche du produit retenu, ou ``None`` sans protection."""
        return produits()[self.protection] if self.protegee else None

    def epaisseur_par_defaut(self) -> float | None:
        """Épaisseur minimale usuelle du produit retenu [mm]."""
        fiche = self.fiche_protection()
        return float(fiche["dp_min"] * 1e3) if fiche else None

    # -- section ----------------------------------------------------------

    @property
    def soudee(self) -> bool:
        """La section est-elle reconstituée plutôt que tirée du catalogue ?"""
        return self.type_section != CATALOGUE

    def section(self) -> SectionSoudee | None:
        """La section soudée décrite, ou ``None`` si elle vient du catalogue.

        C'est ici que les millimètres de l'écran deviennent des mètres, comme
        pour toutes les autres conversions du module. ``SectionCaisson`` et
        ``SectionH`` ne connaissent que le SI.
        """
        if self.type_section == CAISSON_SOUDE:
            return SectionCaisson(
                h=mm(self.h_soudee), b=mm(self.b_soudee),
                tf=mm(self.tf_soudee), tw=mm(self.tw_soudee),
            )
        if self.type_section == H_SOUDE:
            return SectionH(
                h=mm(self.h_soudee), tw=mm(self.tw_soudee),
                b_sup=mm(self.b_soudee), tf_sup=mm(self.tf_soudee),
                b_inf=mm(self.b_inf_soudee), tf_inf=mm(self.tf_inf_soudee),
                face_couverte=FACES_COUVERTES[self.face_couverte],
            )
        if self.type_section != CATALOGUE:
            raise ValueError(
                f"Type de section inconnu : {self.type_section!r}. "
                f"Attendu : {', '.join(TYPES_SECTION)}."
            )
        return None

    def profil_retenu(self) -> Profil:
        """Le profilé sur lequel porte la vérification.

        Catalogue ou section soudée, le reste de la chaîne reçoit un
        ``Profil`` et ne fait pas la différence.
        """
        section = self.section()
        return section.profil() if section is not None else catalogue()[self.profil]

    def controles_section(self) -> tuple[str, ...]:
        """Les réserves propres à la section soudée décrite, s'il y en a."""
        section = self.section()
        return section.controles() if section is not None else ()


def executer(saisie: Saisie) -> ResultatVerification:
    """Traduit une saisie en appel de bibliothèque, et rien de plus.

    Toute la conversion d'unités du projet côté interface tient ici : kN vers
    newtons, kN·m vers newtons-mètres, millimètres vers mètres. Les longueurs
    sont déjà en mètres et les minutes déjà en minutes, ``verifier()`` les
    prenant sous cette forme.
    """
    protection = None
    if saisie.protegee:
        epaisseur = saisie.epaisseur
        if epaisseur is None:
            epaisseur = saisie.epaisseur_par_defaut()
        protection = Protection.depuis_catalogue(
            saisie.protection, d_p=float(epaisseur) * 1e-3
        )

    cas = CasDeCharge(
        N_fi_Ed=kN(saisie.N),
        My_fi_Ed=kNm(saisie.My),
        Mz_fi_Ed=kNm(saisie.Mz),
        L=saisie.L,
        l_fi_y=saisie.l_fi or None,
        l_fi_z=saisie.l_fi or None,
        beta_M_y=saisie.beta_M,
        beta_M_z=saisie.beta_M,
        beta_M_LT=saisie.beta_M,
        maintien_lateral=saisie.maintien,
    )

    return verifier(
        profil=saisie.profil_retenu(),
        nuance=Nuance(saisie.nuance),
        cas=cas,
        exposition=EXPOSITIONS[saisie.exposition],
        duree_requise_min=float(saisie.duree),
        protection=protection,
        courbe=COURBES[saisie.feu],
        contexte=CONTEXTES[saisie.contexte],
        kappa_1=saisie.kappa_1,
        kappa_2=saisie.kappa_2,
        C1=saisie.C1,
    )
