"""Matériaux de protection incendie.

Référence : EN 1993-1-2 §4.2.5.2. Le modèle normatif suppose une couche
isolante d'épaisseur constante, en contact avec l'acier, caractérisée par sa
conductivité, sa masse volumique et sa chaleur spécifique.

Les valeurs livrées dans ``data/protections.toml`` sont génériques. Une étude
de projet doit utiliser celles de l'agrément technique du produit retenu.
"""

from __future__ import annotations

import tomllib
from bisect import bisect_left
from dataclasses import dataclass, field
from pathlib import Path

from ..profils.geometrie import Exposition

__all__ = ["Protection", "catalogue_protections", "charger_protections"]


_TOML_DEFAUT = Path(__file__).resolve().parent.parent / "data" / "protections.toml"


@dataclass(frozen=True, slots=True)
class Protection:
    """Une couche de protection incendie, en unités SI.

    ``lambda_p_variable`` permet de décrire une peinture intumescente, dont la
    conductivité apparente dépend fortement de la température : le film gonfle
    d'un facteur cinquante à cent, et la traiter à conductivité constante est
    physiquement faux. Fournir une table ``[(θ [°C], λ_p [W/m·K]), ...]``
    croissante en température ; ``lambda_p`` sert alors de valeur de repli
    hors du domaine tabulé.
    """

    nom: str
    lambda_p: float
    """Conductivité thermique [W/m·K]."""
    rho_p: float
    """Masse volumique [kg/m³]."""
    c_p: float
    """Chaleur spécifique [J/kg·K]."""
    d_p: float
    """Épaisseur [m]."""

    libelle: str = ""
    pose: str = "contour"
    """« contour » ou « caisson » — détermine l'exposition par défaut."""

    humidite: float = 0.0
    """Teneur en eau [% de la masse], pour le délai d'évaporation.

    EN 1993-1-2 §4.2.5.2(6). Zéro par défaut, ce qui est sécuritaire.
    """

    lambda_p_variable: tuple[tuple[float, float], ...] = field(default=())

    def __post_init__(self) -> None:
        if self.d_p <= 0.0:
            raise ValueError(f"Épaisseur de protection non positive : {self.d_p} m")
        if self.lambda_p <= 0.0:
            raise ValueError(f"Conductivité non positive : {self.lambda_p} W/m·K")
        if self.pose not in ("contour", "caisson"):
            raise ValueError(f"Pose inconnue : {self.pose!r}")

    def conductivite(self, theta_a: float) -> float:
        """Conductivité à la température d'acier donnée [W/m·K].

        Constante pour un isolant classique ; interpolée linéairement pour une
        peinture intumescente décrite par une table.
        """
        table = self.lambda_p_variable
        if not table:
            return self.lambda_p

        temperatures = [point[0] for point in table]
        if theta_a <= temperatures[0]:
            return table[0][1]
        if theta_a >= temperatures[-1]:
            return table[-1][1]

        indice = bisect_left(temperatures, theta_a)
        (t0, v0), (t1, v1) = table[indice - 1], table[indice]
        return v0 + (v1 - v0) * (theta_a - t0) / (t1 - t0)

    def exposition_par_defaut(self, trois_faces: bool = False) -> Exposition:
        """Exposition déduite du mode de pose du produit."""
        if self.pose == "caisson":
            return (
                Exposition.CAISSON_3_FACES if trois_faces else Exposition.CAISSON_4_FACES
            )
        return Exposition.CONTOUR_3_FACES if trois_faces else Exposition.CONTOUR_4_FACES

    def avec_epaisseur(self, d_p: float) -> "Protection":
        """Copie de la protection avec une autre épaisseur [m].

        Utilisé par la recherche d'épaisseur requise, qui balaie ``d_p`` sans
        modifier l'objet d'origine.
        """
        return Protection(
            nom=self.nom,
            lambda_p=self.lambda_p,
            rho_p=self.rho_p,
            c_p=self.c_p,
            d_p=d_p,
            libelle=self.libelle,
            pose=self.pose,
            humidite=self.humidite,
            lambda_p_variable=self.lambda_p_variable,
        )

    @classmethod
    def depuis_catalogue(
        cls,
        nom: str,
        d_p: float,
        humidite: float = 0.0,
        chemin: Path | str | None = None,
    ) -> "Protection":
        """Construit une protection depuis la base livrée avec le paquet.

        ``d_p`` en mètres. Un avertissement n'est pas levé si l'épaisseur sort
        de la plage usuelle du produit : la plage est indicative, le solveur
        doit pouvoir l'explorer librement.
        """
        base = charger_protections(chemin)
        if nom not in base:
            raise KeyError(
                f"Protection {nom!r} inconnue. Disponibles : {', '.join(sorted(base))}"
            )
        fiche = base[nom]
        return cls(
            nom=nom,
            lambda_p=fiche["lambda_p"],
            rho_p=fiche["rho_p"],
            c_p=fiche["c_p"],
            d_p=d_p,
            libelle=fiche.get("libelle", nom),
            pose=fiche.get("pose", "contour"),
            humidite=humidite,
        )

    def __str__(self) -> str:
        return f"{self.libelle or self.nom}, {self.d_p * 1e3:.1f} mm"


def charger_protections(chemin: Path | str | None = None) -> dict[str, dict]:
    """Charge la base de matériaux de protection depuis un fichier TOML."""
    chemin = Path(chemin) if chemin is not None else _TOML_DEFAUT
    with chemin.open("rb") as fichier:
        return tomllib.load(fichier)


def catalogue_protections(chemin: Path | str | None = None) -> list[str]:
    """Noms des produits disponibles dans la base."""
    return sorted(charger_protections(chemin))
