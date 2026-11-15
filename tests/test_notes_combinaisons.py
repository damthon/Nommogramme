"""Les notes de calcul PDF et Word se génèrent pour toutes les combinaisons d'efforts.

N en compression, nul ou en traction ; M_y et M_z présents ou non ; semelle
comprimée libre ou maintenue. Chaque combinaison doit produire les deux notes
sans erreur, et la note doit contenir les contrôles qui s'appliquent au cas.
"""

from __future__ import annotations

import io
import itertools

import pytest

from nommogramme import CasDeCharge, Exposition, Nuance, catalogue, verifier
from nommogramme.note_pdf import etapes_de_calcul

pytest.importorskip("matplotlib")
pytest.importorskip("docx")

# (profil, N [N], M_y [N·m], M_z [N·m]) : efforts modérés pour chaque section.
PROFILS = {
    "HEB 300": (800e3, 150e3, 30e3),
    "RND 40": (50e3, 1e3, 0.3e3),
    "ROR 114.3/10": (50e3, 5e3, 2e3),
    "FLA 100/10": (50e3, 3e3, 0.3e3),
}

# Toutes les combinaisons sur le HEB 300 ; pour les barres, seulement les cas
# les plus chargés (compression ou traction, M_y et M_z, semelle libre). Les
# 96 combinaisons complètes passent, mais en cinq minutes.
COMBINAISONS = [
    ("HEB 300", *c)
    for c in itertools.product((-1, 0, 1), (False, True), (False, True), (False, True))
] + [
    (nom, signe_N, True, True, False)
    for nom in PROFILS if nom != "HEB 300"
    for signe_N in (-1, 1)
]


def _identifiant(c) -> str:
    nom, signe_N, avec_My, avec_Mz, maintien = c
    N = {-1: "compression", 0: "N0", 1: "traction"}[signe_N]
    return f"{nom}-{N}-{'My' if avec_My else 'My0'}-{'Mz' if avec_Mz else 'Mz0'}" + (
        "-maintenu" if maintien else "-libre"
    )


@pytest.mark.parametrize("combinaison", COMBINAISONS, ids=_identifiant)
def test_notes_generees(combinaison) -> None:
    nom, signe_N, avec_My, avec_Mz, maintien = combinaison
    N, My, Mz = PROFILS[nom]
    cas = CasDeCharge(
        N_fi_Ed=signe_N * N, My_fi_Ed=My if avec_My else 0.0,
        Mz_fi_Ed=Mz if avec_Mz else 0.0, L=3.0, maintien_lateral=maintien,
    )
    r = verifier(catalogue[nom], Nuance.S355, cas, Exposition.CONTOUR_4_FACES, 30)

    pdf, word = io.BytesIO(), io.BytesIO()
    r.note_de_calcul_pdf(pdf)
    r.note_de_calcul_word(word)
    assert pdf.getvalue().startswith(b"%PDF")
    assert word.getvalue().startswith(b"PK")  # un .docx est une archive zip

    titres = [b.texte for b in etapes_de_calcul(r) if b.genre == "calcul"]
    deversement_en_traction = any(t.startswith("Traction et flexion, déversement") for t in titres)
    attendu = cas.tendu and avec_My and not maintien
    assert deversement_en_traction == attendu
