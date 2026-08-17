"""Conversions d'unités.

Le cœur de la bibliothèque travaille en unités SI strictes : mètre, mètre carré,
newton, watt, kelvin (ou degré Celsius pour les températures, la norme étant
écrite ainsi), seconde. Les conversions ne se font qu'aux frontières : lecture
du fichier SZS, saisie utilisateur, affichage.

Les températures restent en degrés Celsius d'un bout à l'autre, comme dans
l'EN 1993-1-2. Les seules formules qui exigent des kelvins sont les termes
radiatifs, où la conversion est faite sur place et de façon visible.
"""

from __future__ import annotations

# --- longueurs ---------------------------------------------------------------

MM = 1e-3
"""Millimètre exprimé en mètres."""

CM = 1e-2


def mm(valeur: float) -> float:
    """Millimètres → mètres."""
    return valeur * 1e-3


def en_mm(valeur: float) -> float:
    """Mètres → millimètres."""
    return valeur * 1e3


# --- aires -------------------------------------------------------------------


def mm2(valeur: float) -> float:
    """Millimètres carrés → mètres carrés."""
    return valeur * 1e-6


def en_mm2(valeur: float) -> float:
    return valeur * 1e6


def en_cm2(valeur: float) -> float:
    return valeur * 1e4


# --- inerties et modules -----------------------------------------------------


def mm4(valeur: float) -> float:
    """Millimètres puissance 4 → mètres puissance 4."""
    return valeur * 1e-12


def en_cm4(valeur: float) -> float:
    return valeur * 1e8


def mm3(valeur: float) -> float:
    """Millimètres cubes → mètres cubes."""
    return valeur * 1e-9


def en_cm3(valeur: float) -> float:
    return valeur * 1e6


# --- efforts -----------------------------------------------------------------


def kN(valeur: float) -> float:
    """Kilonewtons → newtons."""
    return valeur * 1e3


def en_kN(valeur: float) -> float:
    return valeur * 1e-3


def kNm(valeur: float) -> float:
    """Kilonewtons-mètres → newtons-mètres."""
    return valeur * 1e3


def en_kNm(valeur: float) -> float:
    return valeur * 1e-3


def MPa(valeur: float) -> float:
    """Mégapascals (= N/mm²) → pascals."""
    return valeur * 1e6


def en_MPa(valeur: float) -> float:
    return valeur * 1e-6


# --- temps -------------------------------------------------------------------


def minutes(valeur: float) -> float:
    """Minutes → secondes."""
    return valeur * 60.0


def en_minutes(valeur: float) -> float:
    """Secondes → minutes."""
    return valeur / 60.0
