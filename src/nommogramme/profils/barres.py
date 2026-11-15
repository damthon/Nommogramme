"""Barres et tubes du commerce : ronds, carrés, tubes ronds, plats, larges plats.

Source : Stahlbau-Tabellen SZS, pages 54 (RND), 55 (VKT), 60-61 (ROR) et 74
(FLA, FLB). Seules les **dimensions** disponibles en sont reprises ; les
caractéristiques se calculent exactement depuis la forme (cercle, carré,
couronne, rectangle), à angles vifs. Les tests les recoupent avec les valeurs
tabulées.

Conventions, pour entrer dans le modèle des profilés en I :

* h et b sont les cotes extérieures ; un plat b × t est **debout** : h = b
  (axe fort y), b = t ;
* t_w = t_f = l'épaisseur qui fixe f_y (EN 10025) : le diamètre d'un rond, le
  côté d'un carré, l'épaisseur d'un tube ou d'un plat ;
* la masse est ρ·A avec ρ = 7850 kg/m³ (le tableau FLB prend 8000 kg/m³ pour
  couvrir les tolérances ; cela ne touche que l'affichage).
"""

from __future__ import annotations

import math
from dataclasses import replace

from ..unites import mm
from .modele import Famille, Profil

__all__ = ["BOULON", "barres", "boulon", "rond", "carre", "tube", "plat"]

BOULON = "Boulon Ø"
"""Préfixe du nom d'une tige de boulon, pour la distinguer d'un rond du catalogue."""

_RHO = 7850.0

# --- dimensions disponibles [mm] ------------------------------------------------

_RND = (10, 12, 14, 15, 16, 18, 20, 22, 24, 25, 26, 28, 30, 35, 40, 45, 50, 60,
        70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 220,
        240, 250, 260, 280, 300, 320, 350, 380, 400, 420, 450, 500)

_VKT = (10, 12, 14, 15, 16, 18, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100,
        110, 120, 130, 140, 150, 160, 180, 200, 220, 240, 250, 260, 280, 300,
        320, 350, 380, 400, 420, 450, 500)

# D → épaisseurs t ; pages 60-61, jusqu'au D = 159 de la page 61.
_ROR: dict[float, tuple[float, ...]] = {
    21.3: (2.0,),
    26.9: (2.3, 2.6, 5.0),
    33.7: (2.3, 2.6, 2.9, 5.0),
    38.0: (2.3, 2.6, 2.9, 5.0, 10.0),
    42.4: (2.3, 2.6, 2.9, 5.0, 10.0),
    44.5: (2.3, 2.6, 2.9, 5.0, 10.0),
    48.3: (2.3, 2.6, 2.9, 5.0, 10.0),
    51.0: (2.6, 2.9, 5.0, 10.0),
    54.0: (2.6, 2.9, 5.0, 10.0),
    57.0: (2.6, 2.9, 3.2, 5.0, 10.0),
    60.3: (2.9, 3.2, 5.0, 10.0),
    63.5: (2.9, 3.2, 5.0, 10.0),
    70.0: (2.9, 3.2, 5.0, 10.0),
    76.1: (2.9, 3.2, 5.0, 10.0),
    82.5: (3.2, 3.6, 5.0, 10.0),
    88.9: (3.2, 3.6, 5.0, 10.0),
    95.0: (3.2, 3.6, 4.0, 5.0, 10.0),
    101.6: (3.6, 4.0, 5.0, 7.1, 10.0, 12.5),
    108.0: (3.6, 4.0, 5.0, 7.1, 10.0, 12.5),
    114.3: (3.6, 4.0, 7.1, 10.0, 16.0),
    121.0: (4.0, 4.5, 7.1, 10.0, 16.0),
    127.0: (4.0, 4.5, 7.1, 10.0, 16.0),
    133.0: (4.0, 4.5, 7.1, 10.0, 16.0),
    139.7: (4.0, 4.5, 7.1, 10.0, 16.0),
    152.4: (4.0, 4.5, 5.0, 7.1, 10.0, 16.0),
    159.0: (4.0, 4.5),
}

_EPAISSEURS_PLATS = (4, 5, 6, 8, 10, 12, 15, 16, 18, 20, 25, 30, 35, 40, 45, 50,
                     60, 80, 100)

# FLA : largeur b → épaisseur maximale tabulée (la grille est pleine jusque-là).
_FLA = {20: 18, 25: 20, 30: 25, 35: 30, 40: 35, 45: 40, 50: 45, 55: 50, 60: 50,
        65: 60, 70: 60, 75: 60, 80: 60, 90: 80, 100: 80, 110: 100, 120: 100,
        130: 100, 140: 100, 150: 100}

_FLB = (160, 170, 180, 190, 200, 220, 240, 250, 260, 280, 300, 350, 400, 450,
        500, 550, 600, 650, 700, 750, 800, 850, 900, 950, 1000, 1100, 1200, 1300,
        1400, 1500, 1750, 2000)


def _cote(valeur: float) -> str:
    """60.3 → « 60.3 », 5.0 → « 5 »."""
    return f"{valeur:g}"


def rond(D_mm: float) -> Profil:
    """Rond plein de diamètre D."""
    D = mm(D_mm)
    A = math.pi * D**2 / 4.0
    I = math.pi * D**4 / 64.0
    return Profil(
        nom=f"RND {_cote(D_mm)}", famille=Famille.RND, masse=_RHO * A, A=A,
        h=D, b=D, tw=D, tf=D, r=D / 2.0,
        Iy=I, Iz=I, Wely=I / (D / 2.0), Wply=D**3 / 6.0,
        Welz=I / (D / 2.0), Wplz=D**3 / 6.0, iy=D / 4.0, iz=D / 4.0,
        Um=math.pi * D, It=2.0 * I, Iw=0.0,
    )


def boulon(d_mm: float) -> Profil:
    """Tige de boulon de diamètre d, quelconque : un rond plein, renommé.

    Même calcul que ``rond`` — un boulon de 20 mm et le RND 20 ont exactement
    les mêmes caractéristiques. Seul le nom change, pour que la note ne le
    présente pas comme un produit du catalogue. C'est la section **lisse**
    (diamètre nominal) : la section résistante A_s du filetage n'est pas
    prise en compte.
    """
    if d_mm <= 0.0:
        raise ValueError(f"Le diamètre du boulon doit être positif, reçu {d_mm} mm.")
    return replace(rond(d_mm), nom=f"{BOULON}{_cote(d_mm)}")


def carre(b_mm: float) -> Profil:
    """Carré plein de côté b."""
    b = mm(b_mm)
    A = b * b
    I = b**4 / 12.0
    return Profil(
        nom=f"VKT {_cote(b_mm)}", famille=Famille.VKT, masse=_RHO * A, A=A,
        h=b, b=b, tw=b, tf=b, r=0.0,
        Iy=I, Iz=I, Wely=b**3 / 6.0, Wply=b**3 / 4.0,
        Welz=b**3 / 6.0, Wplz=b**3 / 4.0, iy=b / math.sqrt(12.0), iz=b / math.sqrt(12.0),
        Um=4.0 * b, It=0.1406 * b**4, Iw=0.0,
    )


def tube(D_mm: float, t_mm: float) -> Profil:
    """Tube rond D × t."""
    D, t = mm(D_mm), mm(t_mm)
    d = D - 2.0 * t
    A = math.pi * (D**2 - d**2) / 4.0
    I = math.pi * (D**4 - d**4) / 64.0
    i = math.sqrt(I / A)
    W_el = I / (D / 2.0)
    W_pl = (D**3 - d**3) / 6.0
    return Profil(
        nom=f"ROR {_cote(D_mm)}/{_cote(t_mm)}", famille=Famille.ROR,
        masse=_RHO * A, A=A, h=D, b=D, tw=t, tf=t, r=D / 2.0,
        Iy=I, Iz=I, Wely=W_el, Wply=W_pl, Welz=W_el, Wplz=W_pl, iy=i, iz=i,
        Um=math.pi * D, It=2.0 * I, Iw=0.0,
        Av=2.0 * A / math.pi,  # EN 1993-1-1 §6.2.6(3)(g)
    )


def plat(b_mm: float, t_mm: float, famille: Famille = Famille.FLA) -> Profil:
    """Plat b × t, debout : axe fort parallèle à t."""
    b, t = mm(b_mm), mm(t_mm)
    A = b * t
    # Torsion d'un rectangle plein (Roark) : I_t = b·t³/3·(1 − 0,63·t/b).
    I_t = b * t**3 / 3.0 * (1.0 - 0.63 * t / b)
    return Profil(
        nom=f"{famille.value} {_cote(b_mm)}/{_cote(t_mm)}", famille=famille,
        masse=_RHO * A, A=A, h=b, b=t, tw=t, tf=t, r=0.0,
        Iy=t * b**3 / 12.0, Iz=b * t**3 / 12.0,
        Wely=t * b**2 / 6.0, Wply=t * b**2 / 4.0,
        Welz=b * t**2 / 6.0, Wplz=b * t**2 / 4.0,
        iy=b / math.sqrt(12.0), iz=t / math.sqrt(12.0),
        Um=2.0 * (b + t), It=I_t, Iw=b**3 * t**3 / 144.0,
    )


def barres() -> list[Profil]:
    """Toutes les barres et tous les tubes disponibles, famille par famille."""
    profils = [rond(D) for D in _RND]
    profils += [carre(b) for b in _VKT]
    profils += [tube(D, t) for D, epaisseurs in _ROR.items() for t in epaisseurs]
    profils += [
        plat(b, t) for b, t_max in _FLA.items()
        for t in _EPAISSEURS_PLATS if t <= t_max
    ]
    profils += [plat(b, t, Famille.FLB) for b in _FLB for t in _EPAISSEURS_PLATS]
    return profils
