"""Validation par recoupements indépendants.

Ce fichier ne teste pas que le code fait ce que le code fait : chaque contrôle
confronte le résultat de la bibliothèque à une solution du **même problème
physique obtenue par une voie différente**, décrite dans ``reference.py``.

Ce qui est établi ici :

* la cohérence mutuelle de l'équation (4.22) et du tableau 3.1, par deux
  routes indépendantes vers la même température ;
* la justesse du schéma d'intégration des équations (4.25) et (4.27), par
  comparaison à une résolution par quadrature en température ;
* la conservation de l'énergie, par bilan d'enthalpie en forme close.

Ce qui n'est **pas** établi : la conformité à des exemples de calcul publiés.
Voir ``docs/validation.md``.
"""

from __future__ import annotations

import math

import pytest

from nommogramme.materiaux.acier import (
    RHO_A,
    chaleur_specifique,
    k_y,
    temperature_pour_k_y,
)
from nommogramme.materiaux.protection import Protection
from nommogramme.nomogramme.temperature_critique import temperature_critique
from nommogramme.profils import Exposition, charger_csv, facteur_massivete, facteur_ombre
from nommogramme.thermique import ISO834, echauffement
from nommogramme.thermique.flux import flux_net
from nommogramme.unites import minutes

from reference import CourbeConstante, enthalpie, temps_par_quadrature


@pytest.fixture(scope="module")
def cat():
    return charger_csv()


class TestEnthalpieDeReference:
    """La primitive de référence doit bien être celle de c_a(θ)."""

    @pytest.mark.parametrize("theta", [100, 300, 550, 650, 800, 1000, 1150])
    def test_derivee_redonne_la_chaleur_specifique(self, theta: int) -> None:
        pas = 1e-4
        derivee = (enthalpie(theta + pas) - enthalpie(theta - pas)) / (2.0 * pas)
        assert derivee == pytest.approx(chaleur_specifique(theta), rel=1e-6)

    def test_croissance_stricte(self) -> None:
        precedente = -1.0
        for theta in range(20, 1201, 5):
            courante = enthalpie(theta)
            assert courante > precedente
            precedente = courante

    def test_continuite_aux_raccords(self) -> None:
        """Aux raccords, l'écart ne doit valoir que la pente locale.

        Comparer les deux côtés à tolérance relative serrée ne teste rien de
        plus que la dérivée : sur un intervalle 2δ, une fonction continue
        varie déjà de c_a·2δ. C'est donc à cette valeur qu'il faut confronter
        l'écart, et non à zéro.
        """
        delta = 1e-6
        for raccord in (600.0, 735.0, 900.0):
            ecart = enthalpie(raccord + delta) - enthalpie(raccord - delta)
            pente_attendue = chaleur_specifique(raccord) * 2.0 * delta
            assert ecart == pytest.approx(pente_attendue, rel=1e-3)


class TestEquation422ContreTableau31:
    """Deux routes indépendantes vers la température critique.

    L'équation (4.22) est un ajustement analytique de la courbe k_y,θ(θ). Pour
    un élément dont la ruine est gouvernée par la résistance de section, la
    ruine survient quand k_y,θ · R(20 °C) = E, c'est-à-dire quand
    k_y,θ = μ₀. La formule fermée et l'interpolation du tableau 3.1 doivent
    donc désigner la même température.
    """

    @pytest.mark.parametrize(
        "mu_0", [0.05, 0.10, 0.15, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90]
    )
    def test_concordance(self, mu_0: float) -> None:
        theta_cr = temperature_critique(mu_0)
        assert k_y(theta_cr) == pytest.approx(mu_0, rel=0.07)

    def test_residus_oscillants_et_non_biaises(self) -> None:
        """Un ajustement lissé oscille autour de la courbe tabulée.

        Une erreur de transcription — dans l'un des quatre coefficients de
        l'éq. (4.22) ou dans une valeur du tableau 3.1 — produirait un biais
        systématique, pas cette alternance de signe.
        """
        residus = [
            k_y(temperature_critique(mu / 100.0)) - mu / 100.0
            for mu in range(5, 91, 5)
        ]
        changements = sum(
            1 for a, b in zip(residus, residus[1:]) if a * b < 0.0
        )
        assert changements >= 3, "les résidus ne changent pas assez de signe"
        moyenne = sum(residus) / len(residus)
        assert abs(moyenne) < 0.015, f"biais systématique de {moyenne:+.4f}"

    def test_inversion_par_le_tableau(self) -> None:
        """Deuxième route : l'inverse tabulé doit retrouver la même température."""
        for mu_0 in (0.25, 0.45, 0.65, 0.85):
            par_formule = temperature_critique(mu_0)
            par_tableau = temperature_pour_k_y(mu_0)
            assert par_formule == pytest.approx(par_tableau, abs=25.0)


class TestEquation425ParQuadrature:
    """Éq. (4.25) — Euler en temps confronté à une quadrature en température."""

    def _vitesse(self, profil, exposition, theta_g: float, alpha_c: float):
        Am_sur_V = facteur_massivete(profil, exposition)
        k_sh = facteur_ombre(profil, exposition, feu_nominal=True)

        def vitesse(theta: float) -> float:
            h = flux_net(theta_g, theta, alpha_c=alpha_c)
            return k_sh * Am_sur_V / (chaleur_specifique(theta) * RHO_A) * h

        return vitesse

    @pytest.mark.parametrize("theta_g", [400.0, 700.0, 1000.0])
    def test_four_isotherme(self, cat, theta_g: float) -> None:
        profil = cat["IPE 300"]
        exposition = Exposition.CONTOUR_4_FACES
        four = CourbeConstante(theta_g)
        cible = 20.0 + 0.7 * (theta_g - 20.0)

        resultat = echauffement(
            profil, exposition, minutes(240), four, dt=0.5
        )
        par_simulation = resultat.temps_pour_atteindre(cible)
        assert par_simulation is not None

        par_quadrature = temps_par_quadrature(
            20.0, cible, self._vitesse(profil, exposition, theta_g, four.alpha_c)
        )
        assert par_simulation == pytest.approx(par_quadrature, rel=0.01)

    def test_traverse_le_pic_de_735_degres(self, cat) -> None:
        """Le passage de la transformation de phase doit rester exact."""
        profil = cat["IPE 300"]
        exposition = Exposition.CONTOUR_4_FACES
        four = CourbeConstante(1000.0)

        resultat = echauffement(profil, exposition, minutes(240), four, dt=0.5)
        par_simulation = resultat.temps_pour_atteindre(800.0)
        par_quadrature = temps_par_quadrature(
            20.0, 800.0, self._vitesse(profil, exposition, 1000.0, four.alpha_c)
        )
        assert par_simulation == pytest.approx(par_quadrature, rel=0.01)

    def test_ordre_de_convergence(self, cat) -> None:
        """Euler explicite est d'ordre 1 : diviser le pas divise l'erreur."""
        profil = cat["IPE 300"]
        exposition = Exposition.CONTOUR_4_FACES
        four = CourbeConstante(800.0)
        exact = temps_par_quadrature(
            20.0, 600.0, self._vitesse(profil, exposition, 800.0, four.alpha_c)
        )

        erreurs = []
        for pas in (4.0, 2.0, 1.0, 0.5):
            obtenu = echauffement(
                profil, exposition, minutes(240), four, dt=pas
            ).temps_pour_atteindre(600.0)
            erreurs.append(abs(obtenu - exact))

        assert erreurs == sorted(erreurs, reverse=True), "l'erreur ne décroît pas"
        assert erreurs[-1] < erreurs[0] / 4.0, "convergence trop lente pour un ordre 1"


class TestEquation427ParQuadrature:
    """Éq. (4.27) — même confrontation, élément protégé.

    Le paramètre φ est mis à zéro par une capacité calorifique d'isolant
    négligeable, ce qui réduit l'équation (4.27) à un simple transfert à
    travers la couche : c'est le seul régime où la vitesse ne dépend que de la
    température de l'acier, condition de la quadrature.
    """

    @pytest.fixture
    def isolant_sans_masse(self):
        return Protection(
            nom="isolant_sans_masse",
            lambda_p=0.12,
            rho_p=1e-6,
            c_p=1e-6,
            d_p=0.020,
        )

    @pytest.mark.parametrize("theta_g", [500.0, 900.0])
    def test_four_isotherme(self, cat, isolant_sans_masse, theta_g: float) -> None:
        profil = cat["HEB 300"]
        exposition = Exposition.CONTOUR_4_FACES
        four = CourbeConstante(theta_g)
        Ap_sur_V = facteur_massivete(profil, exposition)
        cible = 20.0 + 0.6 * (theta_g - 20.0)

        def vitesse(theta: float) -> float:
            return (
                isolant_sans_masse.lambda_p
                * Ap_sur_V
                / (isolant_sans_masse.d_p * chaleur_specifique(theta) * RHO_A)
                * (theta_g - theta)
            )

        resultat = echauffement(
            profil, exposition, minutes(600), four,
            protection=isolant_sans_masse, dt=1.0,
        )
        par_simulation = resultat.temps_pour_atteindre(cible)
        assert par_simulation is not None
        assert par_simulation == pytest.approx(
            temps_par_quadrature(20.0, cible, vitesse), rel=0.01
        )

    def test_phi_negligeable_comme_attendu(self, cat, isolant_sans_masse) -> None:
        resultat = echauffement(
            cat["HEB 300"], Exposition.CONTOUR_4_FACES, minutes(60),
            CourbeConstante(600.0), protection=isolant_sans_masse, dt=1.0,
        )
        assert resultat.phi is not None
        assert resultat.phi < 1e-6


class TestBilanEnergetique:
    """L'énergie absorbée doit égaler la variation d'enthalpie.

    Membre de gauche : accumulation numérique du flux entrant, telle que la
    produit le schéma d'Euler. Membre de droite : primitive analytique de
    c_a(θ). Les deux n'ont aucun code en commun.
    """

    @pytest.mark.parametrize("nom", ["IPE 300", "HEB 300", "HEM 400"])
    def test_acier_nu(self, cat, nom: str) -> None:
        profil = cat[nom]
        exposition = Exposition.CONTOUR_4_FACES
        dt = 0.5
        resultat = echauffement(profil, exposition, minutes(45), ISO834, dt=dt)

        k_sh = resultat.k_sh
        Am_sur_V = resultat.Am_sur_V
        absorbee = 0.0
        for indice in range(len(resultat.temps) - 1):
            theta_g = resultat.temperatures_gaz[indice]
            theta_a = resultat.temperatures[indice]
            absorbee += k_sh * Am_sur_V * flux_net(
                theta_g, theta_a, alpha_c=ISO834.alpha_c
            ) * dt

        stockee = RHO_A * enthalpie(resultat.temperature_finale)
        assert absorbee == pytest.approx(stockee, rel=0.005)

    def test_element_protege(self, cat) -> None:
        """Sans terme correctif d'isolant, le bilan doit se boucler aussi."""
        profil = cat["HEB 300"]
        exposition = Exposition.CONTOUR_4_FACES
        isolant = Protection(
            nom="sans_masse", lambda_p=0.12, rho_p=1e-6, c_p=1e-6, d_p=0.015
        )
        dt = 1.0
        resultat = echauffement(
            profil, exposition, minutes(120), ISO834, protection=isolant, dt=dt
        )

        Ap_sur_V = resultat.Am_sur_V
        absorbee = 0.0
        for indice in range(len(resultat.temps) - 1):
            theta_g = resultat.temperatures_gaz[indice]
            theta_a = resultat.temperatures[indice]
            absorbee += (
                isolant.lambda_p * Ap_sur_V / isolant.d_p * (theta_g - theta_a) * dt
            )

        stockee = RHO_A * enthalpie(resultat.temperature_finale)
        assert absorbee == pytest.approx(stockee, rel=0.01)


class TestCourbesContreFormeIntegrale:
    """Les courbes de feu, confrontées à leur définition mathématique."""

    def test_iso834_par_inversion(self) -> None:
        """t = ((10^((θ−20)/345)) − 1)/8 doit redonner l'instant."""
        for minute in (5, 15, 30, 60, 120):
            theta = ISO834.temperature(minutes(minute))
            retrouve = (10.0 ** ((theta - 20.0) / 345.0) - 1.0) / 8.0
            assert retrouve == pytest.approx(minute, rel=1e-9)

    def test_derivee_toujours_positive(self) -> None:
        for seconde in range(0, 14400, 60):
            pente = (
                ISO834.temperature(seconde + 1.0) - ISO834.temperature(seconde)
            )
            assert pente > 0.0


class TestInvariantsDEchelle:
    """Propriétés que la physique impose, indépendamment du chiffrage."""

    def test_la_temperature_ne_depend_que_du_produit_ksh_amsurv(self, cat) -> None:
        """Deux profilés de même k_sh·A_m/V atteignent la même température.

        C'est le seul paramètre géométrique de l'éq. (4.25) : deux sections
        très différentes mais de massiveté effective égale doivent chauffer
        identiquement.
        """
        cibles = [
            (
                p,
                facteur_ombre(p, Exposition.CONTOUR_4_FACES)
                * facteur_massivete(p, Exposition.CONTOUR_4_FACES),
            )
            for p in cat
        ]
        reference = cat["IPE 300"]
        valeur_reference = facteur_ombre(
            reference, Exposition.CONTOUR_4_FACES
        ) * facteur_massivete(reference, Exposition.CONTOUR_4_FACES)

        jumeau = min(
            (couple for couple in cibles if couple[0].nom != reference.nom),
            key=lambda couple: abs(couple[1] - valeur_reference),
        )
        assert abs(jumeau[1] - valeur_reference) / valeur_reference < 0.01

        theta_reference = echauffement(
            reference, Exposition.CONTOUR_4_FACES, minutes(20), ISO834
        ).temperature_finale
        theta_jumeau = echauffement(
            jumeau[0], Exposition.CONTOUR_4_FACES, minutes(20), ISO834
        ).temperature_finale
        assert theta_jumeau == pytest.approx(theta_reference, abs=5.0)

    def test_epaisseur_double_double_le_temps_caracteristique(self, cat) -> None:
        """À φ ≈ 0, la constante de temps est proportionnelle à d_p.

        τ = d_p·c_a·ρ_a / (λ_p·(A_p/V)) : sous four isotherme, doubler
        l'épaisseur doit doubler le temps pour atteindre une température
        donnée.
        """
        profil = cat["HEB 300"]
        four = CourbeConstante(800.0)
        temps = []
        for epaisseur in (0.010, 0.020, 0.040):
            isolant = Protection(
                nom="sans_masse", lambda_p=0.12, rho_p=1e-6, c_p=1e-6, d_p=epaisseur
            )
            temps.append(
                echauffement(
                    profil, Exposition.CONTOUR_4_FACES, minutes(2000), four,
                    protection=isolant, dt=2.0,
                ).temps_pour_atteindre(400.0)
            )
        assert temps[1] == pytest.approx(2.0 * temps[0], rel=0.01)
        assert temps[2] == pytest.approx(4.0 * temps[0], rel=0.01)

    def test_conductivite_double_halve_le_temps(self, cat) -> None:
        profil = cat["HEB 300"]
        four = CourbeConstante(800.0)
        temps = []
        for conductivite in (0.06, 0.12):
            isolant = Protection(
                nom="sans_masse", lambda_p=conductivite,
                rho_p=1e-6, c_p=1e-6, d_p=0.020,
            )
            temps.append(
                echauffement(
                    profil, Exposition.CONTOUR_4_FACES, minutes(2000), four,
                    protection=isolant, dt=2.0,
                ).temps_pour_atteindre(400.0)
            )
        assert temps[1] == pytest.approx(temps[0] / 2.0, rel=0.01)


class TestFlambementContreEuler:
    """χ_fi confronté à la charge critique d'Euler."""

    def test_elancement_unite_correspond_a_euler(self, cat) -> None:
        """λ̄ = 1 signifie, par définition, N_cr = A·f_y.

        Contrôle indépendant : on calcule N_cr = π²·E·I/L² et on vérifie que
        la longueur donnant λ̄ = 1 est bien celle qui égalise N_cr et A·f_y.

        L'accord n'est pas exact au dernier chiffre parce que le catalogue SZS
        tabule i_z à trois chiffres significatifs : i_z² diffère de I_z/A de
        quelques centièmes de pour-cent — jusqu'à 0,21 % sur le HEA 200. C'est
        une propriété des données, pas du calcul, et elle fait l'objet du test
        ``TestCoherenceDuCatalogue`` ci-dessous.
        """
        from nommogramme.materiaux.acier import E_A
        from nommogramme.mecanique.resistances import elancement_reduit

        profil = cat["HEB 300"]
        fy = 355e6
        longueur = math.pi * profil.iz * math.sqrt(E_A / fy)

        assert elancement_reduit(longueur, profil.iz, fy) == pytest.approx(1.0)
        N_cr = math.pi**2 * E_A * profil.Iz / longueur**2
        assert N_cr == pytest.approx(profil.A * fy, rel=1e-3)

    def test_chi_reste_sous_euler(self) -> None:
        """Les imperfections ne peuvent que réduire la charge de ruine."""
        from nommogramme.mecanique.resistances import chi_fi

        for elancement in (0.5, 1.0, 2.0, 3.0, 5.0, 8.0):
            assert chi_fi(elancement, 355e6) < 1.0 / elancement**2

    def test_chi_tend_vers_euler_aux_grands_elancements(self) -> None:
        """χ·λ̄² → 1 quand λ̄ croît : la ruine devient purement élastique.

        La convergence est lente — 0,75 à λ̄ = 2, 0,96 à λ̄ = 12 — parce que le
        terme d'imperfection α·λ̄ de l'éq. (4.7) ne devient négligeable devant
        λ̄² que très progressivement. C'est la monotonie du rapport, et non sa
        valeur à un élancement donné, qui atteste du comportement asymptotique.
        """
        from nommogramme.mecanique.resistances import chi_fi

        rapports = [
            chi_fi(elancement, 355e6) * elancement**2
            for elancement in (2.0, 3.0, 4.0, 5.0, 8.0, 12.0)
        ]
        assert rapports == sorted(rapports), "le rapport ne croît pas"
        assert all(r < 1.0 for r in rapports)
        assert rapports[-1] > 0.95


class TestCoherenceDuCatalogue:
    """Redondances internes des données SZS.

    Le catalogue tabule des grandeurs liées entre elles : les vérifier les
    unes contre les autres détecte une erreur de lecture ou de conversion
    sans qu'aucune source externe soit nécessaire.
    """

    def test_rayons_de_giration(self, cat) -> None:
        """i = √(I/A) sur les 277 profilés, après les deux corrections.

        C'est ce contrôle qui a mis au jour les deux anomalies du catalogue :
        la colonne i_z figée à 15,0018 mm sur les 108 lignes RRW, et l'I_z du
        HHD 320.74, faux de 8,7 % dans le SZS C5/05 lui-même. Les deux sont
        corrigées à la lecture, et plus rien ne doit dépasser.
        """
        ecarts = []
        for profil in cat:
            for rayon, inertie in ((profil.iy, profil.Iy), (profil.iz, profil.Iz)):
                calcule = math.sqrt(inertie / profil.A)
                ecarts.append((abs(rayon - calcule) / rayon, profil.nom))

        au_dela = [nom for ecart, nom in ecarts if ecart > 0.01]
        assert not au_dela, f"écarts inattendus : {sorted(set(au_dela))}"
        assert sum(e for e, _ in ecarts) / len(ecarts) < 0.002

    def test_correction_des_tubes_creux(self, cat) -> None:
        """Les 106 tubes concernés portent la trace de leur correction."""
        corriges = [p for p in cat if p.iz_tabule is not None]
        assert len(corriges) == 108
        assert all(p.famille.value == "RRW" for p in corriges)
        for profil in corriges:
            assert profil.iz_tabule == pytest.approx(0.0150018, abs=1e-7)
            assert profil.iz == pytest.approx(math.sqrt(profil.Iz / profil.A))

    def test_tubes_carres_iy_egale_iz(self, cat) -> None:
        """Tous les RRW du catalogue sont carrés : la correction est licite."""
        for profil in cat.famille("RRW"):
            assert profil.h == pytest.approx(profil.b)
            assert profil.iz == pytest.approx(profil.iy, rel=1e-9)

    def test_audit_ne_laisse_plus_d_anomalie(self, cat) -> None:
        """Les deux anomalies connues étant corrigées, l'audit doit être vide.

        Il l'est resté après confrontation au SZS C5/05 page à page : ce test
        est le garde-fou contre une régression du chargeur.
        """
        from nommogramme.profils import auditer_catalogue

        anomalies = auditer_catalogue(cat)
        assert not anomalies, [(a.profil, a.grandeur) for a in anomalies]

    def test_correction_de_l_inertie_du_hhd_320_74(self, cat) -> None:
        """Le seul profilé dont I_z a dû être rétabli, et la trace conservée."""
        corriges = [p for p in cat if p.Iz_tabule is not None]
        assert [p.nom for p in corriges] == ["HHD320.74"]

        profil = corriges[0]
        assert profil.Iz_tabule * 1e12 == pytest.approx(45.59e6, rel=0.001)
        assert profil.Iz * 1e12 == pytest.approx(49.6e6, rel=0.001)

        # Les trois recoupements qui condamnent la valeur tabulée.
        assert math.sqrt(profil.Iz / profil.A) == pytest.approx(profil.iz, rel=0.001)
        assert profil.Welz == pytest.approx(profil.Iz / (profil.b / 2), rel=0.005)

    def test_module_plastique_superieur_a_l_elastique(self, cat) -> None:
        """W_pl/W_el est le facteur de forme : entre 1,0 et 1,7 pour ces sections."""
        for profil in cat:
            for plastique, elastique in (
                (profil.Wply, profil.Wely),
                (profil.Wplz, profil.Welz),
            ):
                facteur = plastique / elastique
                assert 1.0 <= facteur < 1.75, f"{profil.nom} : W_pl/W_el = {facteur:.2f}"

    def test_module_elastique_coherent_avec_l_inertie(self, cat) -> None:
        """W_el,y = I_y/(h/2) pour une section symétrique."""
        for profil in cat:
            attendu = profil.Iy / (profil.h / 2.0)
            assert profil.Wely == pytest.approx(attendu, rel=0.02), profil.nom

    def test_masse_lineique(self, cat) -> None:
        """m = ρ·A, aux arrondis près."""
        for profil in cat:
            assert profil.masse == pytest.approx(RHO_A * profil.A, rel=0.02), profil.nom
