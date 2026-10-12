"""Note de calcul détaillée en PDF.

Le PDF lui-même ne se relit pas sans dépendance supplémentaire : on vérifie
qu'il est produit et bien formé, et on vérifie le **contenu** sur la liste des
étapes qui l'alimente, là où les nombres sont lisibles.
"""

from __future__ import annotations

import io

import pytest

from nommogramme import CasDeCharge, Exposition, Nuance, verifier
from nommogramme.cli import main
from nommogramme.materiaux.protection import Protection
from nommogramme.note_pdf import etapes_de_calcul, n
from nommogramme.profils.composes import SectionCaisson
from nommogramme.unites import mm

pytest.importorskip("matplotlib")


@pytest.fixture(scope="module")
def cas():
    section = SectionCaisson(h=mm(400), b=mm(300), tf=mm(20), tw=mm(12))
    resultat = verifier(
        profil=section.profil(), nuance=Nuance.S355,
        cas=CasDeCharge(N_fi_Ed=-3500e3, My_fi_Ed=100e3, L=4.0,
                        l_fi_y=2.0, l_fi_z=2.0,
                        beta_M_y=1.4, beta_M_z=1.4, beta_M_LT=1.4),
        exposition=Exposition.CAISSON_4_FACES, duree_requise_min=90,
        protection=Protection.depuis_catalogue("plaques_silicate", d_p=0.015),
    )
    return resultat, section


def _texte(blocs) -> str:
    return "\n".join(
        [b.texte for b in blocs] + [l for b in blocs for l in b.lignes]
        + [b.reference for b in blocs]
    )


class TestContenu:
    def test_virgule_decimale(self) -> None:
        assert n(0.3421) == "0{,}342"
        assert n(-1.5, 1) == "-1{,}5"

    def test_l_equation_4_22_est_appliquee(self, cas) -> None:
        resultat, section = cas
        texte = _texte(etapes_de_calcul(resultat, section))
        assert "EN 1993-1-2 §4.2.4, éq. (4.22)" in texte
        assert n(resultat.mu_0) in texte
        assert n(resultat.theta_cr_nomogramme, 1) in texte

    def test_chaque_calcul_porte_sa_reference_et_son_application(self, cas) -> None:
        resultat, section = cas
        calculs = [b for b in etapes_de_calcul(resultat, section) if b.genre == "calcul"]
        assert len(calculs) > 20
        for bloc in calculs:
            assert bloc.reference, f"« {bloc.texte} » sans référence"
            assert any(c.isdigit() for ligne in bloc.lignes for c in ligne), (
                f"« {bloc.texte} » sans application numérique"
            )

    def test_la_verification_croisee_retombe_sur_un(self, cas) -> None:
        resultat, section = cas
        texte = _texte(etapes_de_calcul(resultat, section))
        assert f"θ = {resultat.theta_cr_exact:.1f}".replace(".", ",") in texte

    def test_le_pas_thermique_refait_concorde(self, cas) -> None:
        """L'incrément refait à la main doit être celui de l'historique."""
        resultat, section = cas
        blocs = etapes_de_calcul(resultat, section)
        increment = next(b for b in blocs if b.texte.startswith("Incrément"))
        controle = next(b for b in blocs if b.texte.startswith("Contrôle"))
        calcule = increment.lignes[-1].split(r"\mathbf{")[1].split(r"\ ")[0]
        historique = controle.texte.rsplit("incrément de ", 1)[1].split(" K")[0]
        assert float(calcule.replace("{,}", ".")) == pytest.approx(
            float(historique.replace(",", ".")), abs=0.002
        )

    def test_section_soudee_detaillee(self, cas) -> None:
        resultat, section = cas
        texte = _texte(etapes_de_calcul(resultat, section))
        assert "Aire de la section" in texte
        assert n(resultat.profil.A * 1e4, 2) in texte

    def test_protection_combustible(self, cas) -> None:
        resultat, section = cas
        bois = verifier(
            profil=resultat.profil, nuance=Nuance.S355, cas=resultat.cas,
            exposition=Exposition.CAISSON_4_FACES, duree_requise_min=90,
            protection=Protection.depuis_catalogue("bois_lamelle_colle", d_p=0.080),
        )
        texte = _texte(etapes_de_calcul(bois, section))
        assert "EN 1995-1-2 §3.4.2(2), éq. (3.2)" in texte


class TestFichier:
    def test_pdf_en_memoire(self, cas) -> None:
        resultat, section = cas
        tampon = io.BytesIO()
        resultat.note_de_calcul_pdf(tampon, section)
        contenu = tampon.getvalue()
        assert contenu.startswith(b"%PDF")
        assert contenu.count(b"/Type /Page\n") + contenu.count(b"/Type /Page ") >= 5 \
            or len(contenu) > 50_000

    def test_ligne_de_commande(self, tmp_path, capsys) -> None:
        destination = tmp_path / "note.pdf"
        assert main([
            "verifier", "--section", "caisson", "--h", "400", "--b", "300",
            "--tf", "20", "--tw", "12", "--N=-3500", "--My", "100", "--L", "4",
            "--lfi", "2", "--exposition", "caisson4", "--duree", "R90",
            "--protection", "plaques_silicate", "--dp", "15",
            "--rapport", str(destination),
        ]) in (0, 2)
        assert destination.read_bytes().startswith(b"%PDF")
