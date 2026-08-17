"""Résistance au feu de profilés métalliques par la méthode du nomogramme.

Normes de référence : SIA 263 et EN 1993-1-2, actions de feu selon
EN 1991-1-2. La conception d'ensemble est décrite dans
``docs/plan-conception.html``.

État d'avancement — lots 1 à 3 des neuf prévus :

* catalogue SZS, géométrie d'exposition, facteurs de massiveté ;
* propriétés de l'acier à chaud et matériaux de protection ;
* courbes de feu, flux thermique net, diffusion de chaleur.

Ne sont pas encore implantés : les résistances mécaniques à chaud, le degré
d'utilisation, la température critique de l'équation (4.22) et la
vérification croisée en interaction N + M.

Exemple :

    >>> from nommogramme import catalogue, Exposition, echauffement, minutes
    >>> ipe = catalogue["IPE 300"]
    >>> resultat = echauffement(ipe, Exposition.CONTOUR_4_FACES, minutes(15))
    >>> round(resultat.temperature_finale)
    635
"""

from __future__ import annotations

from .materiaux import (
    RHO_A,
    TABLEAU_3_1,
    Nuance,
    Protection,
    catalogue_protections,
    chaleur_specifique,
    conductivite,
    k_E,
    k_p,
    k_y,
    limite_elasticite,
)
from .profils import (
    Catalogue,
    Exposition,
    Famille,
    Profil,
    charger_csv,
    facteur_massivete,
    facteur_ombre,
    perimetre_expose,
)
from .thermique import (
    FEU_EXTERIEUR,
    HYDROCARBURE,
    ISO834,
    CourbeFeu,
    EpaisseurRequise,
    ResultatThermique,
    duree_avant_temperature,
    echauffement,
    epaisseur_requise,
    epaisseur_requise_minutes,
    flux_net,
)
from .unites import en_minutes, kN, kNm, minutes, mm

__version__ = "0.1.0"

__all__ = [
    "Catalogue",
    "CourbeFeu",
    "EpaisseurRequise",
    "Exposition",
    "FEU_EXTERIEUR",
    "Famille",
    "HYDROCARBURE",
    "ISO834",
    "Nuance",
    "Profil",
    "Protection",
    "RHO_A",
    "ResultatThermique",
    "TABLEAU_3_1",
    "__version__",
    "catalogue",
    "catalogue_protections",
    "chaleur_specifique",
    "charger_csv",
    "conductivite",
    "duree_avant_temperature",
    "echauffement",
    "en_minutes",
    "epaisseur_requise",
    "epaisseur_requise_minutes",
    "facteur_massivete",
    "facteur_ombre",
    "flux_net",
    "kN",
    "kNm",
    "k_E",
    "k_p",
    "k_y",
    "limite_elasticite",
    "minutes",
    "mm",
    "perimetre_expose",
]


def __getattr__(nom: str) -> object:
    """Charge le catalogue au premier accès à ``nommogramme.catalogue``."""
    if nom == "catalogue":
        valeur = charger_csv()
        globals()["catalogue"] = valeur
        return valeur
    raise AttributeError(f"module {__name__!r} n'a pas d'attribut {nom!r}")
