"""Point d'entrée de l'exécutable distribué.

Volontairement minuscule : PyInstaller analyse ce fichier pour découvrir ce
qu'il faut embarquer, et un script court donne un graphe de dépendances
lisible. Tout le reste est dans ``nommogramme.interface.bureau``.

Le backend matplotlib est fixé ici, avant tout import de ``pyplot``. Laissé à
la détection automatique, matplotlib irait chercher un backend absent du
paquet et échouerait au premier tracé — sur la machine de l'utilisateur, pas
sur celle qui a compilé.
"""

from __future__ import annotations

import multiprocessing
import sys


def _sortie_en_utf8() -> None:
    """Rend la console capable d'afficher les symboles du domaine.

    Sous Windows, la console hérite d'une page de code héritée — cp1252 en
    Europe de l'Ouest — qui ne contient ni « θ », ni « μ », ni les exposants.
    Le premier ``print`` contenant θ_cr lève alors ``UnicodeEncodeError`` et le
    programme s'arrête, alors que le calcul lui-même s'est bien passé.

    Le piège est qu'il ne se manifeste que sur la machine de l'utilisateur, ou
    sur un coureur Windows : sous Linux et macOS la sortie est en UTF-8 par
    défaut et tout passe.

    ``errors="replace"`` garde le filet : si la reconfiguration échoue sur un
    terminal exotique, un caractère de remplacement vaut mieux qu'une pile
    d'appels.
    """
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):  # pragma: no cover
            pass


def autotest() -> int:
    """Vérifie que l'exécutable est complet, sans ouvrir de fenêtre.

    Un paquet PyInstaller peut se compiler sans erreur et être inutilisable :
    il suffit qu'un fichier de données manque, ou qu'un import différé n'ait
    pas été vu par l'analyse. Rien ne le révèle avant le premier lancement sur
    la machine de l'utilisateur.

    Cette fonction fait le tour des points fragiles — le catalogue de
    profilés, la base de produits, un calcul complet, un tracé — et rend un
    code de sortie. L'intégration continue l'appelle sur l'exécutable qu'elle
    vient de produire, et refuse de publier s'il échoue.
    """
    import matplotlib

    matplotlib.use("Agg")

    # Les modules que l'interface ne charge qu'au moment d'afficher une
    # figure. PyInstaller ne les voit pas par analyse statique, et leur
    # absence ne se manifeste qu'au premier tracé, sur la machine de
    # l'utilisateur. « PIL._tkinter_finder » a précisément été oublié une
    # première fois, sans que rien à la compilation ne le signale.
    differes = (
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        "matplotlib.backends.backend_agg",
        "PIL.Image",
        "PIL.ImageTk",
        "PIL._tkinter_finder",
    )
    import importlib

    for module in differes:
        try:
            importlib.import_module(module)
        except ImportError as souci:
            print(f"Module manquant dans le paquet : {module} ({souci})", file=sys.stderr)
            return 1

    from nommogramme.interface.saisie import Saisie, executer, noms_par_famille, produits
    from nommogramme.nomogramme.trace import tracer_nomogramme

    profils = sum(len(noms) for noms in noms_par_famille().values())
    if profils < 200:
        print(f"Catalogue incomplet : {profils} profilés", file=sys.stderr)
        return 1
    if not produits():
        print("Base de produits de protection vide", file=sys.stderr)
        return 1

    resultat = executer(Saisie(protection="flocage_fibreux", epaisseur=25.0))
    if resultat.theta_cr is None or not 300.0 < resultat.theta_cr < 900.0:
        print(f"Température critique aberrante : {resultat.theta_cr}", file=sys.stderr)
        return 1

    tracer_nomogramme(resultat)

    print(
        f"Autotest réussi — {len(differes)} modules différés présents, "
        f"{profils} profilés, {len(produits())} produits, "
        f"θ_cr = {resultat.theta_cr:.0f} °C, figure tracée."
    )
    return 0


def autotest_fenetre() -> int:
    """Ouvre la fenêtre, la peint une fois, la referme.

    C'est le seul contrôle qui parcoure vraiment le chemin d'affichage : la
    conversion de la figure en image Tk, celle-là même qui échouait sur un
    module manquant. Il demande un écran — l'intégration continue le lance sur
    le coureur Windows, qui en a un.
    """
    import tkinter as tk

    import matplotlib

    matplotlib.use("Agg")

    from nommogramme.interface.bureau import Application

    racine = tk.Tk()
    racine.geometry("1200x800")
    application = Application(racine)
    racine.update()
    application.dessiner_figures()
    racine.update()

    peintes = [cle for cle, cadre in application.cadre_figure.items()
               if cadre.winfo_children()]
    images = len(application._images)
    racine.destroy()

    if not peintes or not images:
        print("La fenêtre s'ouvre mais aucune figure n'est peinte.", file=sys.stderr)
        return 1

    print(f"Autotest fenêtre réussi — onglets peints : {peintes}, {images} image(s).")
    return 0


def main() -> int:
    multiprocessing.freeze_support()
    _sortie_en_utf8()

    if "--autotest" in sys.argv[1:]:
        return autotest()
    if "--autotest-fenetre" in sys.argv[1:]:
        return autotest_fenetre()

    import matplotlib

    matplotlib.use("TkAgg")

    from nommogramme.interface.bureau import lancer

    lancer()
    return 0


if __name__ == "__main__":
    sys.exit(main())
