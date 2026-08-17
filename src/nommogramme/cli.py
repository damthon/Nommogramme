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

from .contexte import EUROCODE_REC, SUISSE_SIA
from .materiaux.acier import Nuance
from .materiaux.protection import Protection
from .mecanique.actions import CasDeCharge
from .nomogramme.verification import verifier
from .profils import Exposition, charger_csv, facteur_massivete, facteur_ombre
from .thermique import echauffement
from .thermique.courbes import COURBES, courbe as courbe_par_nom
from .thermique.solveur import epaisseur_requise_minutes
from .unites import kN, kNm, minutes

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

    # --- verifier ------------------------------------------------------------
    p_ver = sous.add_parser(
        "verifier",
        help="Vérification complète N + M par la méthode du nomogramme",
    )
    p_ver.add_argument("profil")
    p_ver.add_argument("--nuance", choices=[n.value for n in Nuance], default="S355")
    p_ver.add_argument("--duree", type=_duree_minutes, required=True, help="En minutes")
    p_ver.add_argument("--N", type=float, default=0.0,
                       help="Effort normal [kN], positif en compression")
    p_ver.add_argument("--My", type=float, default=0.0, help="Moment axe fort [kN·m]")
    p_ver.add_argument("--Mz", type=float, default=0.0, help="Moment axe faible [kN·m]")
    p_ver.add_argument("--L", type=float, default=0.0, help="Longueur d'épure [m]")
    p_ver.add_argument("--lfi", type=float, help="Longueur de flambement en incendie [m]")
    p_ver.add_argument("--lfi-y", type=float, help="Idem, plan fort [m]")
    p_ver.add_argument("--lfi-z", type=float, help="Idem, plan faible [m]")
    p_ver.add_argument("--L-LT", type=float, help="Longueur de déversement [m]")
    p_ver.add_argument(
        "--maintien-lateral", action="store_true",
        help="Semelle comprimée maintenue : écarte le critère de déversement",
    )
    p_ver.add_argument("--beta-M", type=float, default=1.3,
                       help="Facteur de moment uniforme équivalent [-]")
    p_ver.add_argument("--kappa1", type=float, default=1.0,
                       help="Facteur d'adaptation sur la section [-]")
    p_ver.add_argument("--kappa2", type=float, default=1.0,
                       help="Facteur d'adaptation sur la longueur [-]")
    p_ver.add_argument("--C1", type=float, default=1.0,
                       help="Facteur de forme du diagramme de moment [-]")
    p_ver.add_argument("--exposition", choices=sorted(_EXPOSITIONS), default="contour4")
    p_ver.add_argument("--feu", choices=sorted(COURBES), default="iso834")
    p_ver.add_argument("--protection")
    p_ver.add_argument("--dp", type=float, help="Épaisseur de protection [mm]")
    p_ver.add_argument("--contexte", choices=("sia", "eurocode"), default="sia")
    p_ver.add_argument("--rapport", help="Écrire la note de calcul dans ce fichier")

    p_ctrl = sous.add_parser(
        "controler",
        help="Auditer la cohérence interne du catalogue de profilés",
    )
    p_ctrl.add_argument("--famille", help="Restreindre à une famille")

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
    if a.commande == "verifier":
        return _cmd_verifier(a)
    if a.commande == "controler":
        return _cmd_controler(a)
    raise ValueError(f"Commande inconnue : {a.commande}")


def _cmd_controler(a: argparse.Namespace) -> int:
    from .profils import Gravite, auditer_catalogue

    cat = charger_csv()
    profils = cat.famille(a.famille) if a.famille else list(cat)
    anomalies = auditer_catalogue(profils)

    corriges = [p for p in profils if p.iz_tabule is not None]
    if corriges:
        print(
            f"{len(corriges)} profilés dont i_z a été recalculé à la lecture "
            "(colonne figée dans le classeur SZS) :"
        )
        for profil in corriges[:5]:
            print(
                f"  {profil.nom:20s} {profil.iz_tabule * 1e3:7.2f} → "
                f"{profil.iz * 1e3:7.2f} mm"
            )
        if len(corriges) > 5:
            print(f"  … et {len(corriges) - 5} autres")
        print()

    if not anomalies:
        print(f"{len(profils)} profilés contrôlés : aucune anomalie résiduelle.")
        return 0

    erreurs = [a for a in anomalies if a.gravite is Gravite.ERREUR]
    print(f"{len(profils)} profilés contrôlés, {len(anomalies)} anomalie(s) :\n")
    for anomalie in anomalies:
        print(f"  [{anomalie.gravite.value:13s}] {anomalie}")
    print(
        "\nCes écarts sont à recouper avec les tables SZS d'origine. "
        "Un avertissement peut relever de l'arrondi de tabulation ; "
        "une erreur traduit une donnée fausse."
    )
    return 1 if erreurs else 0


def _cmd_verifier(a: argparse.Namespace) -> int:
    cat = charger_csv()
    profil = cat[a.profil]
    contexte = SUISSE_SIA if a.contexte == "sia" else EUROCODE_REC

    cas = CasDeCharge(
        N_fi_Ed=kN(a.N),
        My_fi_Ed=kNm(a.My),
        Mz_fi_Ed=kNm(a.Mz),
        L=a.L,
        l_fi_y=a.lfi_y if a.lfi_y is not None else a.lfi,
        l_fi_z=a.lfi_z if a.lfi_z is not None else a.lfi,
        L_LT=a.L_LT,
        beta_M_y=a.beta_M,
        beta_M_z=a.beta_M,
        beta_M_LT=a.beta_M,
        maintien_lateral=a.maintien_lateral,
    )

    resultat = verifier(
        profil=profil,
        nuance=Nuance(a.nuance),
        cas=cas,
        exposition=_EXPOSITIONS[a.exposition],
        duree_requise_min=a.duree,
        protection=_protection_depuis_arguments(a),
        courbe=courbe_par_nom(a.feu),
        contexte=contexte,
        kappa_1=a.kappa1,
        kappa_2=a.kappa2,
        C1=a.C1,
    )

    if a.rapport:
        with open(a.rapport, "w", encoding="utf-8") as fichier:
            fichier.write(resultat.note_de_calcul())
        print(f"Note de calcul écrite dans {a.rapport}")

    print(f"Profilé          : {profil.nom} — {a.nuance}")
    print(f"Référentiel      : {contexte.nom}")
    print(f"Classification   : {resultat.classification}")
    print()
    print("Voie mécanique")
    print(f"  critère gouvernant : {resultat.gouverne_par}")
    print(f"  μ₀                 : {resultat.mu_0:.3f}")
    if resultat.theta_cr_nomogramme is not None:
        print(f"  θ_cr éq. (4.22)    : {resultat.theta_cr_nomogramme:.0f} °C")
    if resultat.theta_cr_exact is not None:
        print(f"  θ_cr vérif. croisée: {resultat.theta_cr_exact:.0f} °C")
    if resultat.ecart_nomogramme is not None:
        print(f"  écart              : {resultat.ecart_nomogramme:+.0f} °C")
    print(f"  θ_cr retenue       : {resultat.theta_cr:.0f} °C  ({resultat.source_theta_cr})")
    print()
    print("Voie thermique")
    print(f"  A_m/V              : {resultat.Am_sur_V:.1f} m⁻¹")
    print(f"  k_sh               : {resultat.k_sh:.3f}")
    if resultat.thermique.phi is not None:
        print(f"  φ (éq. 4.28)       : {resultat.thermique.phi:.3f}")
    print(f"  θ_a à {a.duree:.0f} min      : {resultat.theta_a_a_echeance:.0f} °C")
    print()
    duree_atteinte = (
        f"{resultat.t_fi_d_minutes:.1f} min"
        if resultat.t_fi_d_minutes is not None
        else "non atteinte sur la durée simulée"
    )
    print(f"t_fi,d             : {duree_atteinte}")
    print(f"Marge              : {resultat.marge_temperature:+.0f} °C")
    print(f"R{a.duree:.0f}                : {resultat.verdict.value.upper()}")

    for avertissement in resultat.avertissements:
        print(f"\nAvertissement : {avertissement}")
    return 0 if resultat.verdict else 2


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
