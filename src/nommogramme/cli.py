"""Interface en ligne de commande.

Couverture des lots 1 à 3 : consultation du catalogue, facteurs de massiveté,
échauffement de l'acier et dimensionnement de la protection à température
critique imposée.

Le calcul de la température critique depuis le chargement (méthode du
nomogramme proprement dite) relève des lots suivants ; en attendant,
``--theta-cr`` doit être fourni explicitement.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Sequence

from .materiaux.protection import Protection, catalogue_protections
from .profils import Exposition, charger_csv, facteur_massivete, facteur_ombre
from .thermique import echauffement
from .thermique.courbes import COURBES, courbe as courbe_par_nom
from .thermique.solveur import epaisseur_requise_minutes
from .unites import en_minutes, minutes

_EXPOSITIONS = {
    "contour4": Exposition.CONTOUR_4_FACES,
    "contour3": Exposition.CONTOUR_3_FACES,
    "caisson4": Exposition.CAISSON_4_FACES,
    "caisson3": Exposition.CAISSON_3_FACES,
}

_DUREES_USUELLES = (15, 30, 60, 90, 120, 180)


def _duree_minutes(valeur: str) -> float:
    """Accepte « 60 », « R60 » ou « 60min »."""
    nettoye = valeur.strip().upper().removeprefix("R").removesuffix("MIN")
    try:
        duree = float(nettoye)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Durée illisible : {valeur!r}. Attendu : « 60 », « R60 » ou « 60min »."
        ) from None
    if duree <= 0:
        raise argparse.ArgumentTypeError(f"Durée non positive : {valeur!r}")
    return duree


def _construire_analyseur() -> argparse.ArgumentParser:
    analyseur = argparse.ArgumentParser(
        prog="nommo",
        description=(
            "Résistance au feu de profilés métalliques — SIA 263 / EN 1993-1-2. "
            "Lots 1 à 3 : catalogue, matériaux, diffusion de chaleur."
        ),
    )
    sous = analyseur.add_subparsers(dest="commande", required=True)

    # --- profils -------------------------------------------------------------
    p_profils = sous.add_parser(
        "profils", help="Lister les profilés du catalogue et leurs facteurs de massiveté"
    )
    p_profils.add_argument("--famille", help="Filtrer sur une famille (IPE, HEB, RRW…)")
    p_profils.add_argument("--nom", help="Filtrer sur un fragment de nom")
    p_profils.add_argument(
        "--exposition", choices=sorted(_EXPOSITIONS), default="contour4"
    )
    p_profils.add_argument("--format", choices=("texte", "csv"), default="texte")

    # --- echauffement --------------------------------------------------------
    p_ech = sous.add_parser(
        "echauffement", help="Calculer l'évolution de la température de l'acier"
    )
    p_ech.add_argument("profil", help="Nom du profilé, par exemple « HEB 300 »")
    p_ech.add_argument(
        "--exposition", choices=sorted(_EXPOSITIONS), default="contour4"
    )
    p_ech.add_argument("--duree", type=_duree_minutes, default=60.0, help="En minutes")
    p_ech.add_argument("--feu", choices=sorted(COURBES), default="iso834")
    p_ech.add_argument("--protection", help="Produit de la base (voir « nommo protections »)")
    p_ech.add_argument("--dp", type=float, help="Épaisseur de protection [mm]")
    p_ech.add_argument("--theta-cr", type=float, help="Température critique [°C]")
    p_ech.add_argument("--pas-sortie", type=float, default=5.0, help="Pas d'affichage [min]")
    p_ech.add_argument("--format", choices=("texte", "csv"), default="texte")

    # --- dimensionner --------------------------------------------------------
    p_dim = sous.add_parser(
        "dimensionner", help="Trouver l'épaisseur de protection requise"
    )
    p_dim.add_argument("profil")
    p_dim.add_argument("--theta-cr", type=float, required=True, help="[°C]")
    p_dim.add_argument("--duree", type=_duree_minutes, required=True, help="En minutes")
    p_dim.add_argument("--protection", required=True)
    p_dim.add_argument(
        "--exposition", choices=sorted(_EXPOSITIONS), default="contour4"
    )
    p_dim.add_argument("--feu", choices=sorted(COURBES), default="iso834")

    # --- balayer -------------------------------------------------------------
    p_bal = sous.add_parser(
        "balayer", help="Durée atteinte, sans protection, pour toute une famille"
    )
    p_bal.add_argument("--famille", required=True)
    p_bal.add_argument("--theta-cr", type=float, required=True, help="[°C]")
    p_bal.add_argument(
        "--exposition", choices=sorted(_EXPOSITIONS), default="contour4"
    )
    p_bal.add_argument("--feu", choices=sorted(COURBES), default="iso834")
    p_bal.add_argument("--format", choices=("texte", "csv"), default="texte")

    sous.add_parser("protections", help="Lister les produits de protection disponibles")

    return analyseur


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _construire_analyseur().parse_args(argv)
    try:
        return _executer(arguments)
    except (KeyError, ValueError, FileNotFoundError) as erreur:
        print(f"Erreur : {erreur}", file=sys.stderr)
        return 1


def _executer(a: argparse.Namespace) -> int:
    if a.commande == "protections":
        return _cmd_protections()
    if a.commande == "profils":
        return _cmd_profils(a)
    if a.commande == "echauffement":
        return _cmd_echauffement(a)
    if a.commande == "dimensionner":
        return _cmd_dimensionner(a)
    if a.commande == "balayer":
        return _cmd_balayer(a)
    raise ValueError(f"Commande inconnue : {a.commande}")


def _cmd_protections() -> int:
    from .materiaux.protection import charger_protections

    base = charger_protections()
    print(f"{'identifiant':22s} {'λp':>6s} {'ρp':>7s} {'cp':>6s}  {'pose':8s} libellé")
    print("-" * 88)
    for nom in sorted(base):
        fiche = base[nom]
        print(
            f"{nom:22s} {fiche['lambda_p']:6.2f} {fiche['rho_p']:7.0f} "
            f"{fiche['c_p']:6.0f}  {fiche['pose']:8s} {fiche.get('libelle', '')}"
        )
    print("\nValeurs génériques. Une étude de projet doit utiliser celles de")
    print("l'agrément technique du produit (ETE, reconnaissance AEAI).")
    return 0


def _cmd_profils(a: argparse.Namespace) -> int:
    cat = charger_csv()
    exposition = _EXPOSITIONS[a.exposition]

    profils = cat.famille(a.famille) if a.famille else list(cat)
    if a.nom:
        fragment = a.nom.upper().replace(" ", "")
        profils = [p for p in profils if fragment in p.nom.upper().replace(" ", "")]

    if not profils:
        print("Aucun profilé ne correspond.", file=sys.stderr)
        return 1

    lignes = [
        (
            p.nom,
            p.masse,
            p.A * 1e4,
            p.h * 1e3,
            p.b * 1e3,
            p.Wply * 1e6,
            facteur_massivete(p, exposition),
            facteur_ombre(p, exposition),
        )
        for p in profils
    ]

    if a.format == "csv":
        redacteur = csv.writer(sys.stdout)
        redacteur.writerow(
            ["nom", "masse_kg_m", "A_cm2", "h_mm", "b_mm", "Wply_cm3", "Am_sur_V_1_m", "ksh"]
        )
        for ligne in lignes:
            redacteur.writerow([ligne[0]] + [f"{v:.4g}" for v in ligne[1:]])
        return 0

    print(f"Exposition : {exposition.value}\n")
    print(
        f"{'profilé':16s} {'m':>7s} {'A':>8s} {'h':>7s} {'b':>7s} "
        f"{'Wply':>9s} {'Am/V':>8s} {'ksh':>6s}"
    )
    print(
        f"{'':16s} {'kg/m':>7s} {'cm²':>8s} {'mm':>7s} {'mm':>7s} "
        f"{'cm³':>9s} {'1/m':>8s} {'-':>6s}"
    )
    print("-" * 76)
    for nom, m, A, h, b, wply, amv, ksh in lignes:
        print(
            f"{nom:16s} {m:7.1f} {A:8.1f} {h:7.1f} {b:7.1f} "
            f"{wply:9.1f} {amv:8.1f} {ksh:6.3f}"
        )
    print(f"\n{len(lignes)} profilés")
    return 0


def _protection_depuis_arguments(a: argparse.Namespace) -> Protection | None:
    if not a.protection:
        return None
    if a.dp is None:
        raise ValueError("--dp (épaisseur en mm) est requis avec --protection.")
    return Protection.depuis_catalogue(a.protection, d_p=a.dp * 1e-3)


def _cmd_echauffement(a: argparse.Namespace) -> int:
    cat = charger_csv()
    profil = cat[a.profil]
    exposition = _EXPOSITIONS[a.exposition]
    feu = courbe_par_nom(a.feu)
    protection = _protection_depuis_arguments(a)

    resultat = echauffement(
        profil=profil,
        exposition=exposition,
        duree=minutes(a.duree),
        courbe=feu,
        protection=protection,
    )

    if a.format == "csv":
        redacteur = csv.writer(sys.stdout)
        redacteur.writerow(["minute", "theta_acier_C", "theta_gaz_C"])
        for minute, theta in resultat.echantillons(a.pas_sortie):
            redacteur.writerow([f"{minute:.1f}", f"{theta:.1f}",
                                f"{feu.temperature(minutes(minute)):.1f}"])
        return 0

    print(f"Profilé      : {profil.nom} ({profil.famille.value})")
    print(f"Exposition   : {exposition.value}")
    print(f"Feu          : {feu.nom}")
    print(f"Am/V         : {resultat.Am_sur_V:.1f} m⁻¹")
    print(f"k_sh         : {resultat.k_sh:.3f}")
    if protection is not None:
        print(f"Protection   : {protection}")
        if resultat.phi is not None:
            print(f"φ (éq. 4.28) : {resultat.phi:.3f}")
    else:
        print("Protection   : aucune")
    print()

    print(f"{'min':>6s} {'θ acier':>9s} {'θ gaz':>8s}")
    print("-" * 26)
    for minute, theta in resultat.echantillons(a.pas_sortie):
        print(f"{minute:6.0f} {theta:9.0f} {feu.temperature(minutes(minute)):8.0f}")

    print(f"\nTempérature à {a.duree:.0f} min : {resultat.temperature_finale:.0f} °C")

    if a.theta_cr is not None:
        instant = resultat.minutes_pour_atteindre(a.theta_cr)
        print(f"Température critique     : {a.theta_cr:.0f} °C")
        if instant is None:
            print(
                f"→ non atteinte en {a.duree:.0f} min : l'élément tient au moins "
                f"cette durée."
            )
        else:
            print(f"→ atteinte à {instant:.1f} min.")
            for exigence in _DUREES_USUELLES:
                verdict = "satisfait" if instant >= exigence else "NON satisfait"
                print(f"   R{exigence:<4d} {verdict}")

    for avertissement in resultat.avertissements:
        print(f"\nAvertissement : {avertissement}")
    return 0


def _cmd_dimensionner(a: argparse.Namespace) -> int:
    cat = charger_csv()
    profil = cat[a.profil]
    exposition = _EXPOSITIONS[a.exposition]
    gabarit = Protection.depuis_catalogue(a.protection, d_p=0.015)

    resultat = epaisseur_requise_minutes(
        profil=profil,
        exposition=exposition,
        protection=gabarit,
        theta_cible=a.theta_cr,
        duree_requise_min=a.duree,
        courbe=courbe_par_nom(a.feu),
    )

    print(f"Profilé            : {profil.nom}")
    print(f"Exposition         : {exposition.value}")
    print(f"Am/V               : {facteur_massivete(profil, exposition):.1f} m⁻¹")
    print(f"Produit            : {gabarit.libelle or gabarit.nom}")
    print(f"Exigence           : θ_a ≤ {a.theta_cr:.0f} °C à {a.duree:.0f} min")
    print()
    print(f"Épaisseur requise  : {resultat.d_p_mm:.1f} mm")
    print(f"Épaisseur retenue  : {resultat.d_p_arrondie_mm:.1f} mm (arrondi commercial)")
    print(f"θ_a à l'échéance   : {resultat.theta_arrondie:.0f} °C")
    print(f"Convergence        : {resultat.iterations} itérations")
    return 0


def _cmd_balayer(a: argparse.Namespace) -> int:
    cat = charger_csv()
    exposition = _EXPOSITIONS[a.exposition]
    feu = courbe_par_nom(a.feu)
    profils = cat.famille(a.famille)
    if not profils:
        raise ValueError(f"Famille {a.famille!r} vide ou inconnue.")

    lignes = []
    for profil in profils:
        resultat = echauffement(
            profil=profil, exposition=exposition, duree=minutes(240), courbe=feu
        )
        instant = resultat.minutes_pour_atteindre(a.theta_cr)
        lignes.append(
            (profil.nom, resultat.Am_sur_V, instant if instant is not None else float("inf"))
        )

    if a.format == "csv":
        redacteur = csv.writer(sys.stdout)
        redacteur.writerow(["nom", "Am_sur_V_1_m", "duree_atteinte_min"])
        for nom, amv, duree in lignes:
            redacteur.writerow([nom, f"{amv:.1f}", f"{duree:.1f}"])
        return 0

    print(f"Famille {a.famille.upper()}, {exposition.value}, {feu.nom}, sans protection")
    print(f"Température critique : {a.theta_cr:.0f} °C\n")
    print(f"{'profilé':16s} {'Am/V':>8s} {'durée':>9s}  tenue")
    print("-" * 52)
    for nom, amv, duree in lignes:
        satisfaites = [d for d in _DUREES_USUELLES if duree >= d]
        tenue = f"R{max(satisfaites)}" if satisfaites else "—"
        print(f"{nom:16s} {amv:8.1f} {duree:8.1f}′  {tenue}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
