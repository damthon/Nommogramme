"""Sections reconstituées soudées, décrites par l'utilisateur.

Deux formes couvrent l'essentiel de ce qui se soude en atelier :

* le **caisson rectangulaire** (``SectionCaisson``) — deux semelles et deux
  âmes, section fermée, très raide en torsion ;
* le **profilé en H** (``SectionH``, un PRS) — une âme et deux semelles, dont
  les dimensions peuvent différer.

Pourquoi ce module produit un ``Profil``
----------------------------------------

Tout le reste du paquet — massiveté, échauffement, classification,
résistances, nomogramme, note de calcul — travaille sur un ``Profil``. Une
section soudée n'est pas un objet d'un autre genre : c'est un ``Profil`` dont
les caractéristiques ne viennent pas d'une table mais d'un calcul. Elle entre
donc dans la chaîne existante sans qu'aucun de ces modules ait à savoir d'où
elle sort.

Trois choses distinguent malgré tout une section soudée d'un profilé laminé,
et ce sont exactement les champs facultatifs de ``Profil`` :

* elle n'a **pas de congé de raccordement** — le rayon vaut zéro, et les
  élancements de paroi se mesurent entre soudures, pas entre congés ;
* ses semelles peuvent être **inégales**, ce qui invalide la constante de
  gauchissement des sections doublement symétriques et rend la question
  « quelle semelle la dalle recouvre-t-elle ? » significative ;
* elle n'a **pas de valeur tabulée** à laquelle se comparer : le périmètre
  développé est calculé, et c'est la seule source.

Exactitude des caractéristiques
-------------------------------

Les deux sections se décomposent en rectangles à angles droits. Aire, centre
de gravité, inerties et modules plastiques sont donc **exacts**, et non
approchés : les gorges de soudure sont simplement négligées, ce qui va dans le
sens de la sécurité pour l'aire comme pour le périmètre exposé.

Ne sont pas exacts, et le sont d'ailleurs rarement : la constante de torsion
uniforme — somme des rectangles minces pour le H, formule de Bredt pour le
caisson — et la constante de gauchissement d'une section monosymétrique.

Avertissement
-------------

L'outil ne dispose d'aucun exemple de référence externe sur section soudée.
Les caractéristiques géométriques se recoupent avec les tables SZS pour un H
dont on reproduit les dimensions ; la vérification au feu qui en découle, en
particulier le déversement d'une section à semelles inégales, ne l'est pas.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from ..materiaux.acier import RHO_A
from .modele import Famille, Profil

__all__ = [
    "FaceCouverte",
    "Plaque",
    "SectionCaisson",
    "SectionH",
    "SectionSoudee",
    "caracteristiques",
]


_ETA_CISAILLEMENT = 1.0
"""Facteur η de l'aire de cisaillement A_v = η·Σ(h_w·t_w) [-].

EN 1993-1-1 §6.2.6(3). La valeur recommandée est 1,2 jusqu'à la nuance S460 ;
1,0 est retenu ici, ce qui minore A_v et va donc dans le sens de la sécurité.
"""


class FaceCouverte(str, Enum):
    """Semelle masquée par la dalle, en exposition sur trois faces.

    La question ne se pose que pour une section en H à semelles inégales : le
    périmètre exposé diminue de la largeur de **cette** semelle-là, et se
    tromper de face fausse le facteur de massiveté, donc l'échauffement.
    """

    SUPERIEURE = "semelle supérieure"
    INFERIEURE = "semelle inférieure"


@dataclass(frozen=True, slots=True)
class Plaque:
    """Une tôle rectangulaire, dans le repère de la section [m].

    ``y`` est l'abscisse du centre selon l'axe faible, ``z`` son ordonnée
    mesurée depuis la fibre inférieure de la section.
    """

    y: float
    z: float
    largeur: float
    """Extension selon y [m]."""
    hauteur: float
    """Extension selon z [m]."""
    nom: str = ""

    @property
    def aire(self) -> float:
        return self.largeur * self.hauteur


# --- caractéristiques d'un assemblage de rectangles ---------------------------
#
# Les fonctions qui suivent ne connaissent que des rectangles : elles servent
# aussi bien au caisson qu'au H, et se testent sur des cas dont la réponse
# s'écrit à la main.


def _fibres(plaques: list[Plaque], selon_z: bool) -> list[tuple[float, float, float]]:
    """(centre, épaisseur, largeur transverse) de chaque plaque selon un axe.

    ``selon_z`` empile les fibres verticalement — c'est la flexion autour de
    l'axe fort ; sinon elles s'empilent horizontalement.
    """
    if selon_z:
        return [(p.z, p.hauteur, p.largeur) for p in plaques]
    return [(p.y, p.largeur, p.hauteur) for p in plaques]


def _aire(plaques: list[Plaque]) -> float:
    return sum(p.aire for p in plaques)


def _centre(plaques: list[Plaque]) -> tuple[float, float]:
    """Centre de gravité (y_g, z_g) [m]."""
    aire = _aire(plaques)
    if aire <= 0.0:
        raise ValueError("Section d'aire nulle.")
    y_g = sum(p.aire * p.y for p in plaques) / aire
    z_g = sum(p.aire * p.z for p in plaques) / aire
    return y_g, z_g


def _inertie(plaques: list[Plaque], centre: float, selon_z: bool) -> float:
    """Moment d'inertie autour d'un axe passant par ``centre`` [m⁴]."""
    total = 0.0
    for position, epaisseur, largeur in _fibres(plaques, selon_z):
        total += largeur * epaisseur**3 / 12.0
        total += largeur * epaisseur * (position - centre) ** 2
    return total


def _aire_en_dessous(fibres, coupe: float) -> float:
    """Aire située du côté des ordonnées inférieures à ``coupe`` [m²]."""
    total = 0.0
    for position, epaisseur, largeur in fibres:
        bas = position - epaisseur / 2.0
        total += largeur * min(max(coupe - bas, 0.0), epaisseur)
    return total


def _axe_plastique(plaques: list[Plaque], selon_z: bool) -> float:
    """Position de l'axe neutre plastique — celui qui partage l'aire en deux.

    L'aire en dessous d'une coupe croît continûment et sans plateau au sein de
    la matière : la dichotomie converge sans ambiguïté. Deux cents itérations
    portent l'incertitude bien en deçà du micron.
    """
    fibres = _fibres(plaques, selon_z)
    demi = _aire(plaques) / 2.0
    bas = min(position - epaisseur / 2.0 for position, epaisseur, _ in fibres)
    haut = max(position + epaisseur / 2.0 for position, epaisseur, _ in fibres)
    for _ in range(200):
        milieu = 0.5 * (bas + haut)
        if _aire_en_dessous(fibres, milieu) < demi:
            bas = milieu
        else:
            haut = milieu
    return 0.5 * (bas + haut)


def _module_plastique(plaques: list[Plaque], selon_z: bool) -> float:
    """Module plastique [m³] : la somme des moments statiques des deux moitiés."""
    coupe = _axe_plastique(plaques, selon_z)
    total = 0.0
    for position, epaisseur, largeur in _fibres(plaques, selon_z):
        bas = position - epaisseur / 2.0
        haut = position + epaisseur / 2.0

        sommet_inferieur = min(haut, coupe)
        if sommet_inferieur > bas:
            aire = largeur * (sommet_inferieur - bas)
            total += aire * (coupe - 0.5 * (bas + sommet_inferieur))

        pied_superieur = max(bas, coupe)
        if haut > pied_superieur:
            aire = largeur * (haut - pied_superieur)
            total += aire * (0.5 * (pied_superieur + haut) - coupe)
    return total


@dataclass(frozen=True, slots=True)
class Caracteristiques:
    """Les grandeurs de section d'un assemblage de rectangles, en SI."""

    A: float
    y_g: float
    z_g: float
    Iy: float
    Iz: float
    Wply: float
    Wplz: float


def caracteristiques(plaques: list[Plaque]) -> Caracteristiques:
    """Aire, centre de gravité, inerties et modules plastiques [SI].

    Exactes pour toute section composée de rectangles à angles droits.

    >>> carre = [Plaque(y=0.0, z=0.05, largeur=0.1, hauteur=0.1)]
    >>> c = caracteristiques(carre)
    >>> round(c.A, 6), round(c.Iy * 1e8, 3), round(c.Wply * 1e6, 3)
    (0.01, 833.333, 250.0)
    """
    y_g, z_g = _centre(plaques)
    return Caracteristiques(
        A=_aire(plaques),
        y_g=y_g,
        z_g=z_g,
        Iy=_inertie(plaques, z_g, selon_z=True),
        Iz=_inertie(plaques, y_g, selon_z=False),
        Wply=_module_plastique(plaques, selon_z=True),
        Wplz=_module_plastique(plaques, selon_z=False),
    )


def _format_mm(valeur: float) -> str:
    """Une dimension en millimètres, sans décimale inutile."""
    millimetres = valeur * 1e3
    return f"{millimetres:.0f}" if abs(millimetres - round(millimetres)) < 5e-2 \
        else f"{millimetres:.1f}"


def _exiger_positif(**dimensions: float) -> None:
    for nom, valeur in dimensions.items():
        if valeur <= 0.0:
            raise ValueError(f"{nom} doit être strictement positif, reçu {valeur} m.")


# --- caisson rectangulaire soudé ----------------------------------------------


@dataclass(frozen=True, slots=True)
class SectionCaisson:
    """Caisson rectangulaire soudé — quatre tôles, en unités SI.

    Les deux semelles occupent toute la largeur ``b`` ; les deux âmes se
    logent entre elles, sur la hauteur libre ``h − 2·t_f``. C'est la
    disposition usuelle en atelier, et celle qui rend le caisson exactement
    égal au rectangle plein ``b × h`` privé de son vide intérieur.

    >>> caisson = SectionCaisson(h=0.400, b=0.300, tf=0.020, tw=0.012)
    >>> profil = caisson.profil()
    >>> round(profil.A * 1e4, 1)          # cm²
    206.4
    >>> profil.famille.value
    'CRS'
    """

    h: float
    """Hauteur totale [m]."""
    b: float
    """Largeur totale [m]."""
    tf: float
    """Épaisseur des deux semelles [m]."""
    tw: float
    """Épaisseur des deux âmes [m]."""
    nom: str = ""

    def __post_init__(self) -> None:
        _exiger_positif(h=self.h, b=self.b, tf=self.tf, tw=self.tw)
        if self.h <= 2.0 * self.tf:
            raise ValueError(
                f"Hauteur {_format_mm(self.h)} mm insuffisante pour deux semelles "
                f"de {_format_mm(self.tf)} mm."
            )
        if self.b <= 2.0 * self.tw:
            raise ValueError(
                f"Largeur {_format_mm(self.b)} mm insuffisante pour deux âmes "
                f"de {_format_mm(self.tw)} mm."
            )

    # -- géométrie --------------------------------------------------------

    @property
    def hw(self) -> float:
        """Hauteur libre d'âme, entre semelles [m]."""
        return self.h - 2.0 * self.tf

    @property
    def bw(self) -> float:
        """Largeur libre de semelle, entre âmes [m]."""
        return self.b - 2.0 * self.tw

    def plaques(self) -> list[Plaque]:
        """Les quatre tôles, dans le repère de la section."""
        return [
            Plaque(0.0, self.tf / 2.0, self.b, self.tf, "semelle inférieure"),
            Plaque(0.0, self.h - self.tf / 2.0, self.b, self.tf, "semelle supérieure"),
            Plaque(-(self.b - self.tw) / 2.0, self.h / 2.0, self.tw, self.hw, "âme gauche"),
            Plaque(+(self.b - self.tw) / 2.0, self.h / 2.0, self.tw, self.hw, "âme droite"),
        ]

    @property
    def It(self) -> float:
        """Constante de torsion uniforme, formule de Bredt [m⁴].

        Section fermée à parois minces : I_t = 4·A_m²/∮(ds/t), l'aire A_m étant
        celle qu'enferme la ligne moyenne des parois. C'est cette rigidité,
        deux à trois ordres de grandeur au-dessus de celle d'un H, qui écarte
        le déversement d'un caisson.
        """
        aire_moyenne = (self.b - self.tw) * (self.h - self.tf)
        circuit = 2.0 * (self.b - self.tw) / self.tf + 2.0 * (self.h - self.tf) / self.tw
        return 4.0 * aire_moyenne**2 / circuit

    def nom_par_defaut(self) -> str:
        return (
            f"CRS {_format_mm(self.h)}×{_format_mm(self.b)}×"
            f"{_format_mm(self.tf)}/{_format_mm(self.tw)}"
        )

    # -- traduction en Profil ---------------------------------------------

    def profil(self) -> Profil:
        """La section, sous la forme que tout le reste du paquet attend."""
        c = caracteristiques(self.plaques())
        aire_ame = 2.0 * self.hw * self.tw
        return Profil(
            nom=self.nom or self.nom_par_defaut(),
            famille=Famille.CRS,
            masse=c.A * RHO_A,
            A=c.A,
            h=self.h,
            b=self.b,
            tw=self.tw,
            tf=self.tf,
            r=0.0,
            Iy=c.Iy,
            Iz=c.Iz,
            Wely=c.Iy / (self.h / 2.0),
            Wply=c.Wply,
            Welz=c.Iz / (self.b / 2.0),
            Wplz=c.Wplz,
            iy=math.sqrt(c.Iy / c.A),
            iz=math.sqrt(c.Iz / c.A),
            Um=2.0 * (self.h + self.b),
            It=self.It,
            Av=_ETA_CISAILLEMENT * aire_ame,
            Aw=aire_ame,
            Iw=0.0,
            b_couverte=self.b,
            c_sur_t_semelle=self.bw / self.tf,
            c_sur_t_ame=self.hw / self.tw,
            hw_impose=self.hw,
            soudee=True,
        )

    def controles(self) -> tuple[str, ...]:
        """Ce qui mérite d'être signalé sur cette géométrie."""
        messages: list[str] = []
        if self.hw / self.tw > 120.0:
            messages.append(
                f"Âme élancée : h_w/t_w = {self.hw / self.tw:.0f}. Le voilement "
                "par cisaillement et la nécessité de raidisseurs relèvent de "
                "l'EN 1993-1-5, que cet outil ne traite pas."
            )
        if self.bw / self.tf > 60.0:
            messages.append(
                f"Semelles élancées : b_w/t_f = {self.bw / self.tf:.0f}. La "
                "section sera vraisemblablement de classe 4 à chaud."
            )
        return tuple(messages)

    def resume(self) -> str:
        return (
            f"Caisson soudé {_format_mm(self.h)} × {_format_mm(self.b)} mm · "
            f"semelles {_format_mm(self.tf)} mm · âmes {_format_mm(self.tw)} mm"
        )


# --- profilé en H soudé (PRS) -------------------------------------------------


@dataclass(frozen=True, slots=True)
class SectionH:
    """Profilé en H soudé — une âme, deux semelles, en unités SI.

    Les deux semelles sont indépendantes : largeurs et épaisseurs peuvent
    différer, ce qui donne une section **monosymétrique**. Trois conséquences,
    toutes traitées ici :

    * le centre de gravité n'est plus à mi-hauteur, et les deux modules
      élastiques diffèrent — ``Wely`` retient le plus petit, celui de la fibre
      la plus sollicitée ;
    * la constante de gauchissement n'est plus ``I_z·(h − t_f)²/4`` mais celle
      d'une section monosymétrique, portée par ``Profil.Iw`` ;
    * en exposition sur trois faces, la largeur retirée du périmètre exposé
      est celle de la semelle que la dalle recouvre, et d'elle seule.

    >>> prs = SectionH(h=0.600, tw=0.010, b_sup=0.300, tf_sup=0.020,
    ...                b_inf=0.200, tf_inf=0.015)
    >>> profil = prs.profil()
    >>> round(profil.A * 1e4, 1)          # cm²
    146.5
    >>> round(profil.h * 1e3)             # hauteur totale, mm
    600
    """

    h: float
    """Hauteur totale, semelles comprises [m]."""
    tw: float
    """Épaisseur d'âme [m]."""
    b_sup: float
    """Largeur de la semelle supérieure [m]."""
    tf_sup: float
    """Épaisseur de la semelle supérieure [m]."""
    b_inf: float
    """Largeur de la semelle inférieure [m]."""
    tf_inf: float
    """Épaisseur de la semelle inférieure [m]."""
    face_couverte: FaceCouverte = FaceCouverte.SUPERIEURE
    """Semelle masquée par la dalle, en exposition sur trois faces."""
    nom: str = ""

    def __post_init__(self) -> None:
        _exiger_positif(
            h=self.h, tw=self.tw, b_sup=self.b_sup, tf_sup=self.tf_sup,
            b_inf=self.b_inf, tf_inf=self.tf_inf,
        )
        if self.h <= self.tf_sup + self.tf_inf:
            raise ValueError(
                f"Hauteur {_format_mm(self.h)} mm insuffisante pour des semelles "
                f"de {_format_mm(self.tf_sup)} et {_format_mm(self.tf_inf)} mm."
            )
        for cote, largeur in (("supérieure", self.b_sup), ("inférieure", self.b_inf)):
            if largeur < self.tw:
                raise ValueError(
                    f"Semelle {cote} plus étroite que l'âme : "
                    f"{_format_mm(largeur)} mm contre {_format_mm(self.tw)} mm."
                )

    # -- géométrie --------------------------------------------------------

    @property
    def hw(self) -> float:
        """Hauteur libre d'âme, entre semelles [m]."""
        return self.h - self.tf_sup - self.tf_inf

    @property
    def b(self) -> float:
        """Largeur hors tout — la plus large des deux semelles [m]."""
        return max(self.b_sup, self.b_inf)

    @property
    def symetrique(self) -> bool:
        return self.b_sup == self.b_inf and self.tf_sup == self.tf_inf

    @property
    def largeur_couverte(self) -> float:
        """Largeur retirée du périmètre exposé sur trois faces [m]."""
        if self.face_couverte is FaceCouverte.SUPERIEURE:
            return self.b_sup
        return self.b_inf

    def plaques(self) -> list[Plaque]:
        """Les trois tôles, dans le repère de la section."""
        return [
            Plaque(0.0, self.tf_inf / 2.0, self.b_inf, self.tf_inf, "semelle inférieure"),
            Plaque(0.0, self.tf_inf + self.hw / 2.0, self.tw, self.hw, "âme"),
            Plaque(0.0, self.h - self.tf_sup / 2.0, self.b_sup, self.tf_sup,
                   "semelle supérieure"),
        ]

    @property
    def It(self) -> float:
        """Constante de torsion uniforme [m⁴].

        Section ouverte à parois minces : I_t = ⅓·Σ(b_i·t_i³). L'apport des
        congés, qu'une section soudée n'a pas, est par construction absent.
        """
        return (
            self.b_sup * self.tf_sup**3
            + self.b_inf * self.tf_inf**3
            + self.hw * self.tw**3
        ) / 3.0

    @property
    def Iw(self) -> float:
        """Constante de gauchissement d'une section monosymétrique [m⁶].

            I_w = I_fs·I_fi/(I_fs + I_fi) · h_s²

        ``h_s`` étant la distance entre les centres des deux semelles. À
        semelles égales, l'expression redonne ``I_z·h_s²/4``, c'est-à-dire
        l'approximation employée pour les profilés du catalogue.
        """
        I_fs = self.tf_sup * self.b_sup**3 / 12.0
        I_fi = self.tf_inf * self.b_inf**3 / 12.0
        h_s = self.h - (self.tf_sup + self.tf_inf) / 2.0
        return I_fs * I_fi / (I_fs + I_fi) * h_s**2

    @property
    def c_sur_t_semelle(self) -> float:
        """Élancement de paroi de la semelle la plus élancée [-].

        Chaque semelle est deux consoles de largeur (b − t_w)/2. La plus
        élancée des deux gouverne la classe, quelle que soit celle qui est
        comprimée : la classification est faite sur la section, non sur un
        sens de flexion.
        """
        return max(
            (self.b_sup - self.tw) / 2.0 / self.tf_sup,
            (self.b_inf - self.tw) / 2.0 / self.tf_inf,
        )

    def nom_par_defaut(self) -> str:
        if self.symetrique:
            return (
                f"PRS {_format_mm(self.h)}×{_format_mm(self.b_sup)}×"
                f"{_format_mm(self.tf_sup)}/{_format_mm(self.tw)}"
            )
        return (
            f"PRS {_format_mm(self.h)}×{_format_mm(self.b_sup)}×"
            f"{_format_mm(self.tf_sup)}+{_format_mm(self.b_inf)}×"
            f"{_format_mm(self.tf_inf)}/{_format_mm(self.tw)}"
        )

    # -- traduction en Profil ---------------------------------------------

    def profil(self) -> Profil:
        """La section, sous la forme que tout le reste du paquet attend."""
        c = caracteristiques(self.plaques())
        aire_ame = self.hw * self.tw
        # La fibre la plus éloignée du centre de gravité donne le plus petit
        # module élastique : c'est elle qui plastifie la première.
        distance_extreme = max(c.z_g, self.h - c.z_g)
        return Profil(
            nom=self.nom or self.nom_par_defaut(),
            famille=Famille.PRS,
            masse=c.A * RHO_A,
            A=c.A,
            h=self.h,
            b=self.b,
            tw=self.tw,
            # L'épaisseur de semelle sert à lire la limite d'élasticité, qui
            # décroît avec elle : la plus épaisse des deux est la plus
            # défavorable.
            tf=max(self.tf_sup, self.tf_inf),
            r=0.0,
            Iy=c.Iy,
            Iz=c.Iz,
            Wely=c.Iy / distance_extreme,
            Wply=c.Wply,
            Welz=c.Iz / (self.b / 2.0),
            Wplz=c.Wplz,
            iy=math.sqrt(c.Iy / c.A),
            iz=math.sqrt(c.Iz / c.A),
            Um=2.0 * self.h + 2.0 * self.b_sup + 2.0 * self.b_inf - 2.0 * self.tw,
            It=self.It,
            Av=_ETA_CISAILLEMENT * aire_ame,
            Aw=aire_ame,
            Iw=self.Iw,
            b_couverte=self.largeur_couverte,
            c_sur_t_semelle=self.c_sur_t_semelle,
            c_sur_t_ame=self.hw / self.tw,
            hw_impose=self.hw,
            soudee=True,
        )

    def controles(self) -> tuple[str, ...]:
        """Ce qui mérite d'être signalé sur cette géométrie."""
        messages: list[str] = []
        if self.hw / self.tw > 124.0:
            messages.append(
                f"Âme élancée : h_w/t_w = {self.hw / self.tw:.0f}. Au-delà de "
                "124·ε l'EN 1993-1-5 impose une vérification au voilement par "
                "cisaillement, hors du domaine de cet outil."
            )
        if not self.symetrique:
            messages.append(
                "Section monosymétrique : le déversement est calculé avec la "
                "constante de gauchissement d'une section à semelles inégales, "
                "sans terme de monosymétrie (coefficient de Wagner). "
                "Aucun exemple de référence externe ne couvre ce cas."
            )
        return tuple(messages)

    def resume(self) -> str:
        if self.symetrique:
            return (
                f"H soudé {_format_mm(self.h)} mm · semelles "
                f"{_format_mm(self.b_sup)} × {_format_mm(self.tf_sup)} mm · "
                f"âme {_format_mm(self.tw)} mm"
            )
        return (
            f"H soudé {_format_mm(self.h)} mm · semelle supérieure "
            f"{_format_mm(self.b_sup)} × {_format_mm(self.tf_sup)} mm · "
            f"inférieure {_format_mm(self.b_inf)} × {_format_mm(self.tf_inf)} mm · "
            f"âme {_format_mm(self.tw)} mm"
        )


SectionSoudee = SectionCaisson | SectionH
"""L'une ou l'autre des deux sections reconstituées."""
