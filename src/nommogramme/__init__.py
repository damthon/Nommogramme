"""Résistance au feu de profilés métalliques par la méthode du nomogramme.

Normes de référence : SIA 263 et EN 1993-1-2, actions de feu selon
EN 1991-1-2. La conception d'ensemble est décrite dans
``docs/plan-conception.html``.

Ce que couvre la bibliothèque :

* catalogue SZS, sections reconstituées soudées, géométrie d'exposition et
  facteurs de massiveté ;
* propriétés de l'acier à chaud et matériaux de protection ;
* courbes de feu, flux thermique net, diffusion de chaleur ;
* résistances mécaniques à chaud, χ_fi et χ_LT,fi ;
* interaction N + M, degré d'utilisation, équation (4.22) ;
* orchestration, vérification croisée, note de calcul ;
* tracés — nomogramme, échauffement, coupe de section cotée ;
* trois surfaces : ligne de commande, navigateur, fenêtre de bureau.

Toutes les clauses citées sont rassemblées dans ``nommogramme.references``,
avec la mention de celles qui restent à recouper avec un exemplaire officiel
des normes.

Exemple :

    >>> from nommogramme import catalogue, Exposition, CasDeCharge, Nuance, verifier
    >>> cas = CasDeCharge(N_fi_Ed=850e3, My_fi_Ed=120e3, L=4.0, l_fi_y=2.0, l_fi_z=2.0)
    >>> r = verifier(catalogue["HEB 300"], Nuance.S355, cas,
    ...              Exposition.CONTOUR_4_FACES, duree_requise_min=60)
    >>> round(r.mu_0, 3)
    0.407
"""

from __future__ import annotations

from .contexte import EUROCODE_REC, SUISSE_SIA, ContexteNormatif
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
from .mecanique import (
    CasDeCharge,
    ClassificationSection,
    Resistances,
    TauxUtilisation,
    beta_M_lineaire,
    chi_LT_fi,
    chi_fi,
    classifier,
    combinaison_accidentelle,
    eta_fi,
)
from .nomogramme import (
    ResultatVerification,
    Verdict,
    degre_utilisation_pour,
    temperature_critique,
    verifier,
)
from .profils import (
    Catalogue,
    Exposition,
    FaceCouverte,
    Famille,
    Profil,
    SectionCaisson,
    SectionH,
    charger_csv,
    facteur_massivete,
    facteur_ombre,
    perimetre_expose,
)
from .references import REFERENCES, Reference, a_recouper
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

__version__ = "0.2.0"

__all__ = [
    "Catalogue",
    "CasDeCharge",
    "ClassificationSection",
    "ContexteNormatif",
    "CourbeFeu",
    "EUROCODE_REC",
    "EpaisseurRequise",
    "Exposition",
    "FEU_EXTERIEUR",
    "FaceCouverte",
    "Famille",
    "HYDROCARBURE",
    "ISO834",
    "Nuance",
    "Profil",
    "Protection",
    "REFERENCES",
    "RHO_A",
    "Reference",
    "Resistances",
    "ResultatThermique",
    "ResultatVerification",
    "SUISSE_SIA",
    "SectionCaisson",
    "SectionH",
    "TABLEAU_3_1",
    "TauxUtilisation",
    "Verdict",
    "__version__",
    "a_recouper",
    "beta_M_lineaire",
    "catalogue",
    "catalogue_protections",
    "chaleur_specifique",
    "charger_csv",
    "chi_LT_fi",
    "chi_fi",
    "classifier",
    "combinaison_accidentelle",
    "conductivite",
    "degre_utilisation_pour",
    "duree_avant_temperature",
    "echauffement",
    "en_minutes",
    "epaisseur_requise",
    "epaisseur_requise_minutes",
    "eta_fi",
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
    "temperature_critique",
    "verifier",
]


def __getattr__(nom: str) -> object:
    """Charge le catalogue au premier accès à ``nommogramme.catalogue``."""
    if nom == "catalogue":
        valeur = charger_csv()
        globals()["catalogue"] = valeur
        return valeur
    raise AttributeError(f"module {__name__!r} n'a pas d'attribut {nom!r}")
