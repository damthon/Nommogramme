"""Courbes de feu, flux thermique et diffusion de chaleur dans l'acier."""

from .courbes import COURBES, FEU_EXTERIEUR, HYDROCARBURE, ISO834, CourbeFeu, courbe
from .evolution import (
    DT_MAX_NON_PROTEGE,
    DT_MAX_PROTEGE,
    DT_NON_PROTEGE,
    DT_PROTEGE,
    ResultatThermique,
    echauffement,
)
from .flux import (
    EPSILON_ACIER_CARBONE,
    EPSILON_ACIER_INOX,
    EPSILON_FEU,
    SIGMA,
    flux_convectif,
    flux_net,
    flux_radiatif,
)
from .solveur import (
    EPAISSEURS_COMMERCIALES,
    EpaisseurRequise,
    duree_avant_temperature,
    epaisseur_requise,
    epaisseur_requise_minutes,
)

__all__ = [
    "COURBES",
    "DT_MAX_NON_PROTEGE",
    "DT_MAX_PROTEGE",
    "DT_NON_PROTEGE",
    "DT_PROTEGE",
    "EPAISSEURS_COMMERCIALES",
    "EPSILON_ACIER_CARBONE",
    "EPSILON_ACIER_INOX",
    "EPSILON_FEU",
    "FEU_EXTERIEUR",
    "HYDROCARBURE",
    "ISO834",
    "SIGMA",
    "CourbeFeu",
    "EpaisseurRequise",
    "ResultatThermique",
    "courbe",
    "duree_avant_temperature",
    "echauffement",
    "epaisseur_requise",
    "epaisseur_requise_minutes",
    "flux_convectif",
    "flux_net",
    "flux_radiatif",
]
