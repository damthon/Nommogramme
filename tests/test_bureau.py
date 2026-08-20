"""L'interface de bureau, et le jeu de paramètres que les deux surfaces partagent.

Deux niveaux, testés différemment.

``saisie.py`` ne touche à aucun widget : il se teste comme n'importe quel
module, et c'est là que vit tout ce qui peut se tromper d'unité.

``bureau.py`` demande un serveur graphique. Les tests l'instancient sur une
racine Tk sans jamais entrer dans la boucle d'événements — on pousse des
valeurs dans les champs, on appelle ``update()``, on lit ce qui s'affiche.
Sur une machine sans écran, ``tkinter`` refuse de démarrer et toute la classe
est écartée ; l'intégration continue les exécute sous Xvfb.

Ce que ces tests cherchent vraiment, c'est la **cohérence entre les deux
interfaces**. Elles affichent les mêmes nombres parce qu'elles appellent le
même ``executer()`` ; si quelqu'un rétablit un jour un calcul dans l'une des
deux, ``test_les_deux_interfaces_partagent_la_traduction`` le verra.
"""

from __future__ import annotations

import pytest

from nommogramme.interface.saisie import (
    CONTEXTES,
    DUREES,
    EXPOSITIONS,
    SANS_PROTECTION,
    Saisie,
    executer,
    noms_par_famille,
    produits,
)
from nommogramme.unites import kN, kNm


class TestSaisie:
    """Le jeu de paramètres partagé, sans aucun widget."""

    def test_les_valeurs_par_defaut_donnent_un_cas_calculable(self) -> None:
        """Un écran qui s'ouvre doit déjà montrer un résultat sensé."""
        resultat = executer(Saisie())
        assert 0.0 < resultat.mu_0 < 1.0
        assert resultat.theta_cr is not None
        assert 400 < resultat.theta_cr < 800

    def test_le_profil_par_defaut_existe(self) -> None:
        defaut = Saisie()
        assert defaut.profil in {n for noms in noms_par_famille().values() for n in noms}

    def test_les_libelles_designent_de_vraies_valeurs(self) -> None:
        """Aucun libellé d'écran ne doit pointer dans le vide."""
        defaut = Saisie()
        assert defaut.exposition in EXPOSITIONS
        assert defaut.contexte in CONTEXTES
        assert defaut.duree in DUREES

    def test_avec_ne_modifie_pas_l_original(self) -> None:
        """``Saisie`` est gelée : ``avec()`` renvoie une copie."""
        defaut = Saisie()
        autre = defaut.avec(N=1200.0)
        assert defaut.N == 850.0
        assert autre.N == 1200.0
        assert autre.profil == defaut.profil

    def test_conversion_des_unites(self) -> None:
        """kN → N et kN·m → N·m, la seule conversion que l'interface fait.

        Contrôlée en comparant à un appel direct de la bibliothèque : si
        ``executer`` se trompait d'un facteur 1000, les deux divergeraient.
        """
        from nommogramme import CasDeCharge, Exposition, Nuance, catalogue, verifier

        saisie = Saisie(N=700.0, My=90.0, Mz=5.0, protection=SANS_PROTECTION)
        par_interface = executer(saisie)

        cas = CasDeCharge(
            N_fi_Ed=kN(700.0), My_fi_Ed=kNm(90.0), Mz_fi_Ed=kNm(5.0),
            L=saisie.L, l_fi_y=saisie.l_fi, l_fi_z=saisie.l_fi,
            beta_M_y=saisie.beta_M, beta_M_z=saisie.beta_M,
            beta_M_LT=saisie.beta_M, maintien_lateral=saisie.maintien,
        )
        direct = verifier(
            profil=catalogue[saisie.profil], nuance=Nuance(saisie.nuance), cas=cas,
            exposition=Exposition.CONTOUR_4_FACES, duree_requise_min=60.0,
        )
        assert par_interface.mu_0 == pytest.approx(direct.mu_0)
        assert par_interface.theta_cr == pytest.approx(direct.theta_cr)

    def test_l_epaisseur_en_millimetres(self) -> None:
        """25 dans le champ doit donner 0,025 m dans la protection."""
        resultat = executer(
            Saisie(protection="flocage_fibreux", epaisseur=25.0)
        )
        assert resultat.protection is not None
        assert resultat.protection.d_p == pytest.approx(0.025)

    def test_l_epaisseur_omise_retombe_sur_le_minimum_du_produit(self) -> None:
        saisie = Saisie(protection="flocage_fibreux", epaisseur=None)
        attendu = produits()["flocage_fibreux"]["dp_min"]
        resultat = executer(saisie)
        assert resultat.protection is not None
        assert resultat.protection.d_p == pytest.approx(attendu)

    def test_une_longueur_de_flambement_nulle_retombe_sur_L(self) -> None:
        """Champ laissé à zéro : ``verifier()`` doit prendre la longueur d'épure."""
        sans = executer(Saisie(L=5.0, l_fi=0.0))
        avec = executer(Saisie(L=5.0, l_fi=5.0))
        assert sans.mu_0 == pytest.approx(avec.mu_0)

    def test_la_protection_change_le_verdict(self) -> None:
        """Contrôle grossier, mais il attrape un produit ignoré en silence."""
        nu = executer(Saisie())
        protege = executer(Saisie(protection="flocage_fibreux", epaisseur=25.0))
        assert not nu.verdict
        assert protege.verdict
        assert protege.theta_a_a_echeance < nu.theta_a_a_echeance


# tkinter est dans la bibliothèque standard, mais les distributions Linux le
# livrent dans un paquet séparé (python3-tk). L'import est donc optionnel — et
# il ne conditionne que les classes qui ouvrent une fenêtre : les tests de
# ``Saisie`` ci-dessus n'en ont aucun besoin et doivent tourner partout.
try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:  # pragma: no cover - dépend de l'installation
    tk = ttk = None  # type: ignore[assignment]

_SANS_INTERFACE = pytest.mark.skipif(
    tk is None, reason="tkinter absent de cette installation (paquet python3-tk)"
)


@pytest.fixture(scope="module")
def racine():
    """Une racine Tk, ou les tests de fenêtre sont écartés faute d'écran."""
    pytest.importorskip("matplotlib", reason="l'interface de bureau trace des figures")
    try:
        fenetre = tk.Tk()
    except tk.TclError as souci:  # pragma: no cover - dépend de l'environnement
        pytest.skip(f"aucun serveur graphique disponible : {souci}")
    fenetre.geometry("1200x800")
    yield fenetre
    fenetre.destroy()


@pytest.fixture
def app(racine):
    """Une application neuve par test.

    Neuve, et non partagée : ces tests poussent des valeurs dans les champs,
    donc une instance de module se traînerait l'état du test précédent.
    """
    from nommogramme.interface.bureau import Application

    application = Application(racine)
    racine.update()
    yield application
    application.destroy()


@_SANS_INTERFACE
class TestApplicationBureau:
    def test_l_ecran_s_ouvre_deja_calcule(self, app) -> None:
        assert app.resultat is not None
        assert app.erreur is None
        assert "R60" in app.banniere.cget("text")
        assert app.indicateur["mu_0"].cget("text") != "—"

    def test_la_banniere_dit_le_verdict(self, app, racine) -> None:
        assert "non satisfait" in app.banniere.cget("text")

        app.var["protection"].set(
            app._libelle_produit("flocage_fibreux")
        )
        app.var["epaisseur"].set(25.0)
        racine.update()

        texte = app.banniere.cget("text")
        assert "non satisfait" not in texte
        assert "satisfait" in texte

    def test_les_chiffres_suivent_la_saisie(self, app, racine) -> None:
        avant = app.resultat.mu_0
        app.var["N"].set(1500.0)
        racine.update()
        assert app.resultat.mu_0 > avant
        assert app.indicateur["mu_0"].cget("text") == f"{app.resultat.mu_0:.3f}"

    def test_changer_de_famille_choisit_un_profil_valide(self, app, racine) -> None:
        """La liste des profilés suit la famille, sans laisser un nom orphelin."""
        app.var["famille"].set("IPE")
        racine.update()
        assert app.var["profil"].get() in noms_par_famille()["IPE"]
        assert app.resultat is not None or app.erreur is not None

    def test_le_champ_d_epaisseur_ne_sert_que_s_il_y_a_un_produit(self, app, racine) -> None:
        assert str(app.champ_epaisseur.cget("state")) == "disabled"

        app.var["protection"].set(app._libelle_produit("plaques_silicate"))
        racine.update()
        assert str(app.champ_epaisseur.cget("state")) == "normal"
        assert "λ_p" in app.note_produit.cget("text")

        app.var["protection"].set(SANS_PROTECTION)
        racine.update()
        assert str(app.champ_epaisseur.cget("state")) == "disabled"
        assert app.note_produit.cget("text") == ""

    def test_le_facteur_d_ombre_n_est_montre_que_sur_l_element_nu(self, app, racine) -> None:
        """k_sh = 1 sur un élément protégé, et l'afficher tromperait.

        Le facteur d'ombre ne concerne que l'acier nu. Sur un élément protégé
        la ligne doit parler d'A_p/V et du produit, pas d'un k_sh unitaire qui
        se lirait comme un oubli.
        """
        assert "k_sh" in app.details.cget("text")

        app.var["protection"].set(app._libelle_produit("flocage_fibreux"))
        racine.update()
        details = app.details.cget("text")
        assert "k_sh" not in details
        assert "A_p/V" in details

    def test_une_saisie_a_moitie_tapee_ne_casse_rien(self, app, racine) -> None:
        """Un champ vidé au clavier ne doit ni planter ni figer l'écran."""
        app.var["N"].set("")
        racine.update()
        assert app.resultat is not None
        assert app.erreur is None

    def test_l_avertissement_de_validation_est_affiche(self, app) -> None:
        """Le pied d'écran doit dire où s'arrête la validation.

        Une ligne, pas un pavé : l'avertissement complet est derrière le
        bouton « À propos ». Ce test tient aux deux — le pied porte le nom de
        ce qui n'est pas validé, le texte long porte le reste.
        """
        from nommogramme.interface import bureau

        def textes(widget) -> str:
            recolte = []
            for enfant in widget.winfo_children():
                if "text" in enfant.keys():
                    recolte.append(str(enfant.cget("text")))
                recolte.append(textes(enfant))
            return " ".join(recolte)

        pied = textes(app)
        assert "développement" in pied
        assert "déversement" in pied
        assert "N + M" in pied

        assert "steeltec" in bureau._AVERTISSEMENT
        assert "agrément" in bureau._AVERTISSEMENT
        assert callable(app.a_propos)

    def test_la_fenetre_tient_sur_un_petit_ecran(self, racine) -> None:
        """Une géométrie plus haute que l'écran met les boutons hors d'atteinte.

        Le défaut ne se voit pas sur un grand moniteur : la fenêtre s'ouvre,
        tout paraît normal, et sur un portable le pied de page et les boutons
        d'enregistrement sont simplement sous le bord de l'écran.
        """
        from nommogramme.interface import bureau

        bureau._dimensionner(racine)
        racine.update_idletasks()

        geometrie = racine.geometry()
        taille, _, _ = geometrie.partition("+")
        largeur, hauteur = (int(v) for v in taille.split("x"))
        assert largeur <= racine.winfo_screenwidth()
        assert hauteur <= racine.winfo_screenheight() - 100

    def test_le_panneau_de_parametres_defile(self, app) -> None:
        """Tous les champs restent atteignables, même sur un écran court."""
        canevas = next(
            enfant
            for cadre in app.winfo_children()
            for enfant in cadre.winfo_children()
            if isinstance(enfant, tk.Canvas)
        )
        assert canevas.cget("yscrollcommand")
        for cle in ("kappa_2", "C1"):
            assert cle in app.var

    def test_les_figures_se_dessinent(self, app, racine) -> None:
        app.dessiner_figures()
        racine.update()
        assert app.cadre_figure["nomogramme"].winfo_children()

    def test_l_image_garde_le_rapport_de_forme_de_la_figure(self, app, racine) -> None:
        """L'écraser ferait chevaucher la légende et le nom de l'axe.

        L'espacement des annotations, des noms d'axes et de la légende est
        calculé pour le rapport de forme de composition. Ce qui est affiché
        est une image rendue hors écran : c'est donc sur **ses pixels** que
        porte le contrôle, et ils doivent tenir dans le cadre.
        """
        app.dessiner_figures()
        racine.update()

        cle = "nomogramme"
        cadre = app.cadre_figure[cle]
        compose_l, compose_h = app._figures[cle].get_size_inches()

        image = app._images[cle]
        largeur, hauteur = image.width(), image.height()

        assert largeur / hauteur == pytest.approx(compose_l / compose_h, rel=0.02)
        assert largeur <= cadre.winfo_width()
        assert hauteur <= cadre.winfo_height()

    def test_la_figure_retrecit_par_le_dpi_et_non_par_la_taille(self, app, racine) -> None:
        """Réduire les pouces laisserait les polices — en points — se chevaucher.

        Une figure moitié moins large avec des textes de même taille absolue
        voit sa légende recouvrir le nom de l'axe. Faire varier le DPI met
        tout à l'échelle ensemble : traits, textes et marges.
        """
        app.dessiner_figures()
        racine.update()

        figure = app._figures["nomogramme"]
        cadre = app.cadre_figure["nomogramme"]

        assert figure.get_size_inches()[0] == pytest.approx(11.0, rel=0.05)
        assert figure.get_dpi() < 100.0, "la figure devrait avoir été réduite"
        assert figure.get_dpi() * figure.get_size_inches()[0] <= cadre.winfo_width()

    def test_les_figures_precedentes_sont_refermees(self, app, racine) -> None:
        """pyplot garde ses figures : les oublier, c'est les accumuler.

        Chaque redessin crée une figure ; sans ``plt.close`` sur la
        précédente, une session de saisie en abandonne des dizaines, chacune
        avec ses tableaux de points.
        """
        import matplotlib.pyplot as plt

        plt.close("all")
        for _ in range(5):
            app.dessiner_figures()
            racine.update()

        assert len(plt.get_fignums()) <= 2, (
            f"{len(plt.get_fignums())} figures encore ouvertes après 5 redessins"
        )

    def test_les_figures_ne_sont_pas_redessinees_a_chaque_frappe(self, app) -> None:
        """Une frappe programme un redessin différé, elle ne le déclenche pas.

        Les figures coûtent plus d'une seconde ; les tracer à chaque caractère
        gèlerait la fenêtre. Le test vérifie qu'une tâche est bien en attente,
        pas que le dessin a eu lieu.
        """
        app.var["N"].set(900.0)
        assert app._tache_figures is not None

    def test_la_note_de_calcul_est_produite(self, app) -> None:
        note = app.resultat.note_de_calcul()
        assert "HEB" in note
        assert len(note) > 500


@_SANS_INTERFACE
class TestCoherenceDesDeuxInterfaces:
    def test_les_deux_interfaces_partagent_la_traduction(self, app) -> None:
        """L'écran de bureau affiche ce que ``executer()`` renvoie, rien d'autre."""
        attendu = executer(app.saisie())
        assert app.resultat.mu_0 == pytest.approx(attendu.mu_0)
        assert app.resultat.theta_cr == pytest.approx(attendu.theta_cr)
        assert app.resultat.verdict is attendu.verdict

    def test_streamlit_passe_par_le_meme_point(self) -> None:
        """``app._verifier`` ne doit rien faire d'autre que déléguer."""
        streamlit = pytest.importorskip("streamlit")  # noqa: F841
        from nommogramme.interface import app as streamlit_app

        saisie = Saisie(N=640.0, My=75.0)
        assert streamlit_app._verifier(saisie).theta_cr == pytest.approx(
            executer(saisie).theta_cr
        )
