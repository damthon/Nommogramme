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
from nommogramme.profils import Catalogue, Exposition, Famille, charger_csv
from nommogramme.thermique.courbes import COURBES
from nommogramme.unites import kN, kNm

__all__ = [
    "CONTEXTES",
    "DUREES",
    "EXPOSITIONS",
    "SANS_PROTECTION",
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

    N: float = 850.0
    """Effort normal [kN], **positif en compression**."""
    My: float = 120.0
    """Moment autour de l'axe fort [kN·m]."""
    Mz: float = 0.0
    """Moment autour de l'axe faible [kN·m]."""

    L: float = 4.0
    """Longueur d'épure [m]."""
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
        profil=catalogue()[saisie.profil],
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
