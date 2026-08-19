# Rapport de validation

État au lot 8. Ce document dit **ce qui est établi, ce qui ne l'est pas, et par
quel moyen** — de façon qu'un lecteur puisse décider lui-même du crédit à
accorder à un résultat de l'outil.

## Ce qui n'a pas pu être fait

Le lot 8 prévoyait la confrontation à des **exemples de calcul normatifs
publiés** : recueils JRC, SCI P375, guides Infosteel, documentation SZS. Cela
n'a pas été possible.

Le proxy réseau de l'environnement de développement bloque l'accès à
`szs.ch`, `eurocodes.jrc.ec.europa.eu`, `steelconstruction.info`,
`infosteel.be` et aux autres sources consultées. Les normes elles-mêmes sont
sous droits et ne sont pas accessibles en ligne.

Une seule source restait joignable, `raw.githubusercontent.com`. Elle n'a pas
été utilisée : reprendre l'implémentation non validée d'un tiers ne vaut pas
validation, et cela sortirait du périmètre de dépôts autorisé pour la session.

**Conséquence : aucun résultat de cet outil n'a été comparé à un calcul de
référence externe.** L'avertissement du README reste entier.

## Ce qui a été fait à la place

Faute de source externe, la validation repose sur des **recoupements
internes** : confronter chaque résultat à une solution du même problème
physique obtenue par une voie délibérément différente, de sorte qu'une erreur
d'implémentation ne puisse pas se reproduire à l'identique des deux côtés.

Les solutions de référence sont dans `tests/reference.py`, les contrôles dans
`tests/test_validation.py`.

### 1. L'équation (4.22) contre le tableau 3.1

L'équation (4.22) est un ajustement analytique de la courbe k_y,θ(θ). Pour un
élément dont la ruine est gouvernée par la résistance de section, la ruine
survient quand k_y,θ = μ₀. La formule fermée et l'interpolation du tableau
doivent donc désigner la même température.

| μ₀ | θ_cr par l'éq. (4.22) | k_y,θ à cette température | Écart |
|---:|---:|---:|---:|
| 0,05 | 933 °C | 0,0533 | +6,7 % |
| 0,10 | 829 °C | 0,0954 | −4,6 % |
| 0,20 | 725 °C | 0,2000 | +0,0 % |
| 0,30 | 664 °C | 0,3169 | +5,7 % |
| 0,50 | 585 °C | 0,5175 | +3,5 % |
| 0,70 | 526 °C | 0,7001 | +0,0 % |
| 0,90 | 458 °C | 0,8715 | −3,2 % |

Ce qui compte n'est pas l'amplitude de l'écart mais **sa forme** : les résidus
changent de signe cinq fois et s'annulent exactement à μ₀ = 0,20 et 0,70.
C'est la signature d'un ajustement lissé sur une courbe tabulée par morceaux.
Une erreur de transcription — dans l'un des quatre coefficients 39,19 / 0,9674
/ 3,833 / 482, ou dans une valeur du tableau 3.1 — produirait un biais
systématique, pas cette alternance.

**Établi :** l'équation (4.22) et le tableau 3.1 sont mutuellement cohérents.

### 2. Les équations (4.25) et (4.27) contre une quadrature

Le code applique le schéma d'Euler explicite imposé par la norme, qui intègre
en temps. La référence résout la **même équation différentielle par séparation
des variables**, en intégrant en température par quadrature de Simpson :

    t = ∫ dθ / v(θ)

Cette voie n'a aucun code commun avec celle testée. Elle exige une vitesse ne
dépendant que de θ, donc une température de gaz constante : les contrôles sont
menés sous four isotherme à 400, 500, 700, 900 et 1000 °C.

Les deux voies concordent **à moins de 1 %**, y compris sur un parcours
traversant le pic de chaleur spécifique de 735 °C. L'erreur décroît d'un
facteur supérieur à 4 quand le pas passe de 4 s à 0,5 s, ce qui confirme
l'ordre 1 attendu d'Euler explicite.

**Établi :** le schéma d'intégration des éq. (4.25) et (4.27) est correct, et
le pas de 2 s retenu par défaut est largement suffisant.

### 3. Bilan d'énergie

L'énergie absorbée par le profilé, accumulée pas à pas depuis le flux entrant,
est confrontée à la variation d'enthalpie calculée par **intégration
analytique en forme close** des équations (3.2a) à (3.2d).

Les deux quantités concordent à 0,5 % sur un IPE 300, un HEB 300 et un
HEM 400 sous ISO 834, et à 1 % pour un élément protégé.

**Établi :** l'intégration conserve l'énergie ; c_a(θ) est bien réévaluée à
chaque pas.

### 4. Invariants d'échelle

Propriétés que la physique impose indépendamment de tout chiffrage :

- deux profilés de même produit k_sh·A_m/V atteignent la même température à
  5 °C près — c'est le seul paramètre géométrique de l'éq. (4.25) ;
- à φ ≈ 0, doubler l'épaisseur d'isolant double exactement le temps
  d'échauffement, et doubler λ_p le divise par deux, conformément à
  τ = d_p·c_a·ρ_a / (λ_p·(A_p/V)) ;
- χ_fi reste toujours sous la charge d'Euler 1/λ̄², et χ_fi·λ̄² croît de façon
  monotone vers 1 quand l'élancement augmente.

### 5. Cohérence interne du catalogue

Les grandeurs tabulées sont liées : i = √(I/A), W_el,y = I_y/(h/2), m = ρ·A,
W_pl/W_el compris entre 1,0 et 1,75. Le module `profils/coherence.py` les
confronte, et la commande `nommo controler` restitue l'audit.

C'est ce contrôle qui a révélé l'anomalie ci-dessous.

## Anomalie trouvée dans le fichier source

### Le rayon de giration des tubes RRW est faux

Dans `Profilé SZS.xlsx`, la colonne `iz3` est **figée à 15,0018 mm sur les 108
lignes RRW**. C'est la valeur du premier tube de la série, RRW 40/40/3,
inscrite en dur au lieu d'être calculée — une recopie vers le bas qui n'a pas
été faite. Le contrôle i = √(I/A) la détecte sur 106 des 108 lignes.

L'enjeu n'est pas cosmétique. Pour un poteau RRW 400/400/10 de 6 m en S355 :

| | i_z | λ̄ | χ_fi | N_b,Rd |
|---|---:|---:|---:|---:|
| Valeur du fichier | 15,0 mm | 5,23 | 0,033 | 182 kN |
| Valeur correcte | 158,9 mm | 0,49 | 0,757 | **4165 kN** |

La résistance au flambement serait **sous-estimée d'un facteur 23**. L'erreur
va dans le sens de la sécurité, mais rendrait tout tube élancé impossible à
justifier.

**Correction appliquée.** Tous les tubes du catalogue étant carrés, I_z = I_y
et i_z = √(I_z/A) sans ambiguïté. Le chargeur recalcule i_z pour toute la
famille RRW et conserve la valeur d'origine dans `Profil.iz_tabule`. La
correction est uniforme, sans seuil : la cause est identifiée et vaut pour
toutes les lignes, y compris les trois où la valeur figée se trouve tomber
près de la bonne.

**Le fichier source n'a pas été modifié** — la correction est faite à la
lecture, et tracée.

### Une anomalie non résolue : HHD 320.74

| Grandeur | Valeur |
|---|---:|
| i_z tabulé | 72,40 mm |
| √(I_z/A) avec l'I_z tabulé | 69,42 mm |
| √(I_z/A) avec l'I_z estimé par la géométrie | 72,35 mm |

Ici l'écart est **de nature inverse** : c'est l'i_z tabulé qui concorde avec la
géométrie, et l'I_z tabulé qui paraît bas d'environ 8 %. Corriger i_z par
√(I_z/A), comme pour les RRW, propagerait l'erreur au lieu de la lever.

**Aucune correction n'est appliquée.** L'anomalie est signalée par
`nommo controler` et demande une vérification sur les tables SZS d'origine.
Un seul profilé sur 277 est concerné.

## Ce qui reste non validé

| Point | État |
|---|---|
| Conformité à des exemples de calcul publiés | **non fait** — sources inaccessibles |
| Numérotation exacte des éq. des facteurs k_y, k_z, k_LT (§4.2.3.5) | à recouper |
| Chiffre SIA 263 traitant la résistance au feu | à recouper |
| Valeurs conventionnelles suisses de θ_cr (500 / 540 / 570 °C) | à recouper |
| Formule du délai d'évaporation t_v = p·ρ_p·d_p²/(5·λ_p) | à recouper, désactivée par défaut |
| Constante de gauchissement I_w ≈ I_z·(h−t_f)²/4 | approximation, absente du catalogue SZS |
| Facteurs d'imperfection et courbe unique à chaud | cohérents entre eux, non confrontés à un exemple |
| I_z du HHD 320.74 | anomalie signalée, non tranchée |

## Comment ajouter vos propres cas de référence

C'est le complément le plus utile à ce qui précède, et il ne demande aucune
source externe : vos cas déjà dimensionnés par un autre moyen — abaque SZS
papier, logiciel du bureau, feuille de calcul existante — valent mieux que
n'importe quel exemple de la littérature, parce qu'ils portent sur vos
profilés et vos pratiques.

Un cas se déclare dans `tests/cas_reference.toml` :

```toml
[[cas]]
libelle = "Poteau HEB 300, R60, vérifié à la main le 12.03"
source = "note de calcul interne 2024-117"
profil = "HEB 300"
nuance = "S355"
N_fi_Ed_kN = 850.0
My_fi_Ed_kNm = 120.0
L = 4.0
l_fi_y = 2.0
l_fi_z = 2.0
exposition = "contour4"
duree_min = 60.0
# Valeurs attendues, et tolérance relative admise
attendu.mu_0 = 0.407
attendu.theta_cr = 617.0
tolerance = 0.05
```

`python -m pytest tests/test_cas_reference.py` les rejoue tous. Chaque cas
ajouté devient un test de non-régression : toute modification ultérieure du
code qui déplacerait le résultat sera signalée.
