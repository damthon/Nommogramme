"""Sections reconstituées soudées — caisson rectangulaire et H.

Ce que ces tests garantissent tient en trois points.

**Les caractéristiques sont exactes**, et pas seulement plausibles. Les deux
formes se décomposent en rectangles à angles droits, dont l'aire, l'inertie et
le module plastique s'écrivent en forme close ; chaque grandeur calculée est
confrontée à sa formule, pas à une valeur figée dont personne ne saurait
redire d'où elle vient. Une valeur de référence recopiée d'une exécution
précédente n'aurait rien vérifié du tout.

**Le cas monosymétrique est traité comme tel.** Une section à semelles
inégales a son centre de gravité hors de la mi-hauteur, deux modules
élastiques différents et une constante de gauchissement qui n'est pas celle
d'une section doublement symétrique. Les tests le vérifient point par point, y
compris la propriété qui fait l'axe neutre plastique : il partage l'aire en
deux moitiés égales.

**La chaîne complète les accepte.** Une section soudée devient un ``Profil`` et
traverse ensuite classification, massiveté, échauffement et nomogramme sans
qu'aucun de ces modules ait à savoir d'où elle vient.

Ce qu'ils ne garantissent pas : la justesse de la vérification au feu qui en
découle. Aucun exemple de référence externe ne couvre le déversement d'une
section soudée — c'est écrit dans ``docs/validation.md``, et ce n'est pas un
test qui peut y remédier.
"""

from __future__ import annotations

import math

import pytest

from nommogramme import CasDeCharge, Exposition, Nuance, verifier
from nommogramme.materiaux.acier import RHO_A
from nommogramme.profils import (
    FaceCouverte,
    Forme,
    SectionCaisson,
    SectionH,
    charger_csv,
    facteur_massivete,
    perimetre_expose,
)
from nommogramme.profils.composes import Plaque, caracteristiques

# Deux sections de travail, l'une fermée, l'autre ouverte et monosymétrique.
CAISSON = SectionCaisson(h=0.400, b=0.300, tf=0.020, tw=0.012)
H_SYMETRIQUE = SectionH(
    h=0.600, tw=0.010, b_sup=0.300, tf_sup=0.020, b_inf=0.300, tf_inf=0.020
)
H_MONOSYMETRIQUE = SectionH(
    h=0.600, tw=0.010, b_sup=0.300, tf_sup=0.020, b_inf=0.200, tf_inf=0.015
)


class TestCaracteristiquesDeRectangles:
    """Le socle : aire, inertie et module plastique d'un assemblage."""

    def test_un_rectangle_seul(self) -> None:
        c = caracteristiques([Plaque(y=0.0, z=0.15, largeur=0.1, hauteur=0.3)])
        assert c.A == pytest.approx(0.03)
        assert c.z_g == pytest.approx(0.15)
        assert c.Iy == pytest.approx(0.1 * 0.3**3 / 12.0)
        assert c.Iz == pytest.approx(0.3 * 0.1**3 / 12.0)
        assert c.Wply == pytest.approx(0.1 * 0.3**2 / 4.0)
        assert c.Wplz == pytest.approx(0.3 * 0.1**2 / 4.0)

    def test_l_axe_plastique_est_celui_qui_minimise_les_moments_statiques(self) -> None:
        """La propriété qui définit l'axe neutre plastique.

        La somme ∫|z − c| dA est minimale là où l'aire se partage en deux
        moitiés égales — sa dérivée y change de signe. Déplacer l'axe ne peut
        donc que faire croître le résultat, et c'est ce qui distingue un axe
        plastique correct d'un axe posé au jugé, par exemple à mi-hauteur.

        Le contrôle vaut d'autant plus pour une section dissymétrique, où
        l'axe ne tombe ni à mi-hauteur ni sur une interface de tôles.
        """
        plaques = H_MONOSYMETRIQUE.plaques()
        c = caracteristiques(plaques)
        assert c.Wply > 0.0
        for ecart in (-0.02, -0.005, 0.005, 0.02):
            assert _module_autour(plaques, c, ecart) > c.Wply

    def test_l_aire_se_partage_bien_en_deux(self) -> None:
        from nommogramme.profils.composes import _aire_en_dessous, _fibres

        plaques = H_MONOSYMETRIQUE.plaques()
        from nommogramme.profils.composes import _axe_plastique

        coupe = _axe_plastique(plaques, selon_z=True)
        aire = caracteristiques(plaques).A
        assert _aire_en_dessous(_fibres(plaques, True), coupe) == pytest.approx(
            aire / 2.0, rel=1e-9
        )

    def test_le_module_plastique_depasse_l_elastique(self) -> None:
        for section in (CAISSON, H_SYMETRIQUE, H_MONOSYMETRIQUE):
            profil = section.profil()
            assert profil.Wply > profil.Wely
            assert profil.Wplz > profil.Welz


def _module_autour(plaques, carac, ecart: float) -> float:
    """Somme des moments statiques autour d'un axe volontairement décalé."""
    from nommogramme.profils.composes import _axe_plastique

    coupe = _axe_plastique(plaques, selon_z=True) + ecart
    total = 0.0
    for plaque in plaques:
        bas = plaque.z - plaque.hauteur / 2.0
        haut = plaque.z + plaque.hauteur / 2.0
        sommet = min(haut, coupe)
        if sommet > bas:
            total += plaque.largeur * (sommet - bas) * abs(coupe - 0.5 * (bas + sommet))
        pied = max(bas, coupe)
        if haut > pied:
            total += plaque.largeur * (haut - pied) * abs(0.5 * (pied + haut) - coupe)
    return total


class TestCaisson:
    """Le caisson se compare au rectangle plein privé de son vide."""

    def test_aire(self) -> None:
        attendu = 2 * 0.300 * 0.020 + 2 * (0.400 - 2 * 0.020) * 0.012
        assert CAISSON.profil().A == pytest.approx(attendu)

    def test_inerties(self) -> None:
        h, b, tf, tw = CAISSON.h, CAISSON.b, CAISSON.tf, CAISSON.tw
        Iy = b * h**3 / 12.0 - (b - 2 * tw) * (h - 2 * tf) ** 3 / 12.0
        Iz = h * b**3 / 12.0 - (h - 2 * tf) * (b - 2 * tw) ** 3 / 12.0
        profil = CAISSON.profil()
        assert profil.Iy == pytest.approx(Iy)
        assert profil.Iz == pytest.approx(Iz)

    def test_modules_plastiques(self) -> None:
        h, b, tf, tw = CAISSON.h, CAISSON.b, CAISSON.tf, CAISSON.tw
        Wply = b * h**2 / 4.0 - (b - 2 * tw) * (h - 2 * tf) ** 2 / 4.0
        Wplz = h * b**2 / 4.0 - (h - 2 * tf) * (b - 2 * tw) ** 2 / 4.0
        profil = CAISSON.profil()
        assert profil.Wply == pytest.approx(Wply)
        assert profil.Wplz == pytest.approx(Wplz)

    def test_torsion_par_bredt(self) -> None:
        """Section fermée : I_t = 4·A_m²/∮(ds/t)."""
        aire_moyenne = (CAISSON.b - CAISSON.tw) * (CAISSON.h - CAISSON.tf)
        circuit = (
            2 * (CAISSON.b - CAISSON.tw) / CAISSON.tf
            + 2 * (CAISSON.h - CAISSON.tf) / CAISSON.tw
        )
        assert CAISSON.It == pytest.approx(4.0 * aire_moyenne**2 / circuit)

    def test_la_torsion_ecrase_celle_d_un_H_de_meme_encombrement(self) -> None:
        """C'est ce qui écarte le déversement d'un caisson.

        Deux ordres de grandeur séparent une section fermée d'une section
        ouverte de même hauteur ; la figure et le calcul en dépendent.
        """
        ouvert = SectionH(
            h=0.400, tw=0.012, b_sup=0.300, tf_sup=0.020,
            b_inf=0.300, tf_inf=0.020,
        )
        assert CAISSON.It > 100.0 * ouvert.It

    def test_le_deversement_est_ecarte(self) -> None:
        from nommogramme.mecanique.resistances import moment_critique_elastique

        profil = CAISSON.profil()
        assert profil.forme is Forme.PROFIL_CREUX
        assert not math.isfinite(moment_critique_elastique(profil, 6.0))

    def test_perimetre_developpe(self) -> None:
        profil = CAISSON.profil()
        assert profil.Um == pytest.approx(2 * (CAISSON.h + CAISSON.b))
        assert perimetre_expose(profil, Exposition.CONTOUR_4_FACES) == pytest.approx(
            profil.Um
        )
        assert perimetre_expose(profil, Exposition.CONTOUR_3_FACES) == pytest.approx(
            profil.Um - CAISSON.b
        )

    def test_pas_de_facteur_d_ombre(self) -> None:
        """Une section fermée n'a aucune partie concave."""
        from nommogramme.profils import facteur_ombre

        assert facteur_ombre(
            CAISSON.profil(), Exposition.CONTOUR_4_FACES
        ) == pytest.approx(1.0)


class TestHSymetrique:
    """À semelles égales, les formules classiques doivent tomber juste."""

    def test_aire_et_masse(self) -> None:
        s = H_SYMETRIQUE
        attendu = 2 * s.b_sup * s.tf_sup + s.hw * s.tw
        profil = s.profil()
        assert profil.A == pytest.approx(attendu)
        assert profil.masse == pytest.approx(attendu * RHO_A)

    def test_inertie_forte(self) -> None:
        s = H_SYMETRIQUE
        bras = (s.h - s.tf_sup) / 2.0
        attendu = (
            2 * (s.b_sup * s.tf_sup**3 / 12.0 + s.b_sup * s.tf_sup * bras**2)
            + s.tw * s.hw**3 / 12.0
        )
        assert s.profil().Iy == pytest.approx(attendu)

    def test_module_plastique_fort(self) -> None:
        s = H_SYMETRIQUE
        attendu = s.b_sup * s.tf_sup * (s.h - s.tf_sup) + s.tw * s.hw**2 / 4.0
        assert s.profil().Wply == pytest.approx(attendu)

    def test_le_centre_de_gravite_est_a_mi_hauteur(self) -> None:
        c = caracteristiques(H_SYMETRIQUE.plaques())
        assert c.z_g == pytest.approx(H_SYMETRIQUE.h / 2.0)

    def test_gauchissement_retrouve_la_forme_doublement_symetrique(self) -> None:
        """À semelles égales, I_w doit redonner I_z·h_s²/4.

        C'est l'approximation employée pour les profilés du catalogue : les
        deux voies doivent coïncider là où elles sont toutes deux valables,
        sans quoi une section soudée et son équivalent laminé donneraient des
        déversements différents.
        """
        s = H_SYMETRIQUE
        h_s = s.h - s.tf_sup
        Iz_semelles = 2 * s.tf_sup * s.b_sup**3 / 12.0
        assert s.Iw == pytest.approx(Iz_semelles * h_s**2 / 4.0, rel=1e-9)

    def test_perimetre_developpe(self) -> None:
        s = H_SYMETRIQUE
        assert s.profil().Um == pytest.approx(2 * s.h + 4 * s.b_sup - 2 * s.tw)


class TestHMonosymetrique:
    """Ce que la dissymétrie change, et que rien d'autre ne teste."""

    def test_le_centre_de_gravite_remonte_vers_la_grande_semelle(self) -> None:
        s = H_MONOSYMETRIQUE
        c = caracteristiques(s.plaques())
        assert c.z_g > s.h / 2.0

    def test_le_module_elastique_est_celui_de_la_fibre_la_plus_eloignee(self) -> None:
        """Le plus petit des deux : c'est lui qui plastifie en premier."""
        s = H_MONOSYMETRIQUE
        c = caracteristiques(s.plaques())
        modules = (c.Iy / c.z_g, c.Iy / (s.h - c.z_g))
        assert s.profil().Wely == pytest.approx(min(modules))

    def test_gauchissement_monosymetrique(self) -> None:
        s = H_MONOSYMETRIQUE
        I_fs = s.tf_sup * s.b_sup**3 / 12.0
        I_fi = s.tf_inf * s.b_inf**3 / 12.0
        h_s = s.h - (s.tf_sup + s.tf_inf) / 2.0
        assert s.Iw == pytest.approx(I_fs * I_fi / (I_fs + I_fi) * h_s**2)

    def test_le_gauchissement_est_inferieur_a_celui_du_H_symetrique(self) -> None:
        """Amputer une semelle affaiblit la résistance au gauchissement."""
        assert H_MONOSYMETRIQUE.Iw < H_SYMETRIQUE.Iw

    def test_la_face_couverte_change_le_perimetre_expose(self) -> None:
        """Le point sur lequel il est le plus facile de se tromper.

        Deux sections identiques, la dalle sur l'une ou l'autre semelle : le
        périmètre exposé diffère de l'écart des deux largeurs, et le facteur
        de massiveté avec lui.
        """
        s = H_MONOSYMETRIQUE
        dessus = s.profil()
        dessous = SectionH(
            h=s.h, tw=s.tw, b_sup=s.b_sup, tf_sup=s.tf_sup,
            b_inf=s.b_inf, tf_inf=s.tf_inf,
            face_couverte=FaceCouverte.INFERIEURE,
        ).profil()

        expose_dessus = perimetre_expose(dessus, Exposition.CONTOUR_3_FACES)
        expose_dessous = perimetre_expose(dessous, Exposition.CONTOUR_3_FACES)
        assert expose_dessous - expose_dessus == pytest.approx(s.b_sup - s.b_inf)
        assert facteur_massivete(dessous, Exposition.CONTOUR_3_FACES) > facteur_massivete(
            dessus, Exposition.CONTOUR_3_FACES
        )

    def test_sur_quatre_faces_la_face_couverte_ne_change_rien(self) -> None:
        s = H_MONOSYMETRIQUE
        autre = SectionH(
            h=s.h, tw=s.tw, b_sup=s.b_sup, tf_sup=s.tf_sup,
            b_inf=s.b_inf, tf_inf=s.tf_inf,
            face_couverte=FaceCouverte.INFERIEURE,
        )
        assert perimetre_expose(
            s.profil(), Exposition.CONTOUR_4_FACES
        ) == pytest.approx(
            perimetre_expose(autre.profil(), Exposition.CONTOUR_4_FACES)
        )

    def test_l_epaisseur_de_semelle_retenue_est_la_plus_epaisse(self) -> None:
        """C'est elle qui donne la plus faible limite d'élasticité."""
        assert H_MONOSYMETRIQUE.profil().tf == pytest.approx(
            max(H_MONOSYMETRIQUE.tf_sup, H_MONOSYMETRIQUE.tf_inf)
        )


class TestComparaisonAuCatalogue:
    """Un H soudé aux cotes d'un laminé doit s'en approcher.

    L'écart attendu est connu et d'un seul signe : la section soudée n'a pas
    de congé de raccordement, elle est donc plus légère. Le contrôle porte sur
    l'ordre de grandeur de cet écart — quelques pour-cent — ce qui suffit à
    détecter une erreur de formule ou d'unité, et pas à prétendre que les deux
    sections sont la même.
    """

    @pytest.fixture(scope="class")
    @classmethod
    def cat(cls):
        return charger_csv()

    @pytest.mark.parametrize("nom", ["HEB300", "IPE400", "HEA200"])
    def test_aire_et_inertie_a_quelques_pour_cent(self, cat, nom: str) -> None:
        laminé = cat[nom]
        soude = SectionH(
            h=laminé.h, tw=laminé.tw,
            b_sup=laminé.b, tf_sup=laminé.tf,
            b_inf=laminé.b, tf_inf=laminé.tf,
        ).profil()

        assert soude.A < laminé.A, "sans congés, la section soudée est plus légère"
        assert soude.Iy < laminé.Iy
        assert soude.A == pytest.approx(laminé.A, rel=0.10)
        assert soude.Iy == pytest.approx(laminé.Iy, rel=0.07)
        assert soude.Wply == pytest.approx(laminé.Wply, rel=0.08)
        assert soude.iy == pytest.approx(laminé.iy, rel=0.03)


class TestChaineComplete:
    """Une section soudée traverse tout le paquet comme un profilé du catalogue."""

    @pytest.mark.parametrize(
        "section", [CAISSON, H_SYMETRIQUE, H_MONOSYMETRIQUE], ids=str
    )
    def test_la_verification_aboutit(self, section) -> None:
        resultat = verifier(
            profil=section.profil(),
            nuance=Nuance.S355,
            cas=CasDeCharge(
                N_fi_Ed=600e3, My_fi_Ed=100e3, L=5.0, l_fi_y=5.0, l_fi_z=5.0,
                beta_M_y=1.4,
            ),
            exposition=Exposition.CONTOUR_4_FACES,
            duree_requise_min=30,
        )
        assert 0.0 < resultat.mu_0 < 1.0
        assert 20.0 < resultat.theta_cr <= 1200.0
        assert resultat.Am_sur_V > 0.0

    def test_la_note_de_calcul_decrit_la_section(self) -> None:
        """Une section soudée n'existe nulle part ailleurs que dans la note."""
        resultat = verifier(
            profil=H_MONOSYMETRIQUE.profil(), nuance=Nuance.S355,
            cas=CasDeCharge(N_fi_Ed=400e3, My_fi_Ed=80e3, L=5.0, l_fi_y=5.0, l_fi_z=5.0),
            exposition=Exposition.CONTOUR_3_FACES, duree_requise_min=60,
        )
        note = resultat.note_de_calcul()
        assert "Section reconstituée soudée" in note
        assert "Hauteur d'âme" in note
        assert "Largeur masquée par la dalle" in note

    def test_la_classification_utilise_les_elancements_de_la_section(self) -> None:
        """Pas de congé : l'âme est plus élancée qu'un laminé de même hauteur.

        Sans les élancements imposés, la classification retomberait sur
        ``h − 2·t_f − 2·r`` avec r = 0, ce qui donnerait par chance la bonne
        valeur pour un caisson mais pas pour un H à semelles inégales.
        """
        profil = H_MONOSYMETRIQUE.profil()
        assert profil.c_sur_t_ame == pytest.approx(
            H_MONOSYMETRIQUE.hw / H_MONOSYMETRIQUE.tw
        )
        assert profil.c_sur_t_semelle == pytest.approx(
            max(
                (H_MONOSYMETRIQUE.b_sup - H_MONOSYMETRIQUE.tw) / 2 / H_MONOSYMETRIQUE.tf_sup,
                (H_MONOSYMETRIQUE.b_inf - H_MONOSYMETRIQUE.tw) / 2 / H_MONOSYMETRIQUE.tf_inf,
            )
        )


class TestGeometriesRefusees:
    """Une géométrie impossible doit être refusée à la construction.

    Plus tôt le refus, plus clair le message : une hauteur inférieure à ses
    deux semelles produirait sinon une aire d'âme négative, et une inertie qui
    n'aurait l'air de rien de particulier.
    """

    @pytest.mark.parametrize(
        "dimensions",
        [
            {"h": 0.030, "b": 0.300, "tf": 0.020, "tw": 0.012},
            {"h": 0.400, "b": 0.020, "tf": 0.020, "tw": 0.012},
            {"h": 0.400, "b": 0.300, "tf": 0.0, "tw": 0.012},
            {"h": -0.400, "b": 0.300, "tf": 0.020, "tw": 0.012},
        ],
    )
    def test_caisson(self, dimensions) -> None:
        with pytest.raises(ValueError):
            SectionCaisson(**dimensions)

    @pytest.mark.parametrize(
        "dimensions",
        [
            {"h": 0.030, "tw": 0.010, "b_sup": 0.300, "tf_sup": 0.020,
             "b_inf": 0.300, "tf_inf": 0.020},
            {"h": 0.600, "tw": 0.400, "b_sup": 0.300, "tf_sup": 0.020,
             "b_inf": 0.300, "tf_inf": 0.020},
            {"h": 0.600, "tw": 0.010, "b_sup": 0.300, "tf_sup": 0.0,
             "b_inf": 0.300, "tf_inf": 0.020},
        ],
    )
    def test_h(self, dimensions) -> None:
        with pytest.raises(ValueError):
            SectionH(**dimensions)


class TestReserves:
    """Les avertissements qui accompagnent une géométrie."""

    def test_une_ame_tres_elancee_est_signalee(self) -> None:
        mince = SectionH(
            h=1.600, tw=0.006, b_sup=0.400, tf_sup=0.025,
            b_inf=0.400, tf_inf=0.025,
        )
        assert any("Âme élancée" in message for message in mince.controles())

    def test_la_monosymetrie_est_signalee(self) -> None:
        assert any(
            "monosymétrique" in message
            for message in H_MONOSYMETRIQUE.controles()
        )

    def test_une_section_courante_ne_declenche_rien(self) -> None:
        assert CAISSON.controles() == ()
        assert H_SYMETRIQUE.controles() == ()
