# Nommogramme

Calcul de la résistance au feu de profilés métalliques, protégés et non
protégés, par la méthode du nomogramme. Normes de référence : **SIA 263** et
**EN 1993-1-2**, actions de feu selon **EN 1991-1-2**.

La conception d'ensemble — architecture, équations et clauses normatives — est
décrite dans [`docs/plan-conception.html`](docs/plan-conception.html).
GitHub affichant le code source d'un fichier HTML plutôt que son rendu, ouvrez
plutôt la version mise en page :
<https://claude.ai/code/artifact/1797f310-075b-4bfc-963b-63f8cfd3c14e>

## État d'avancement

Trois des neuf lots prévus sont implantés et testés.

| Lot | Contenu | État |
|:---:|---|:---|
| 1 | Catalogue SZS, géométrie d'exposition, A_m/V, k_sh | fait |
| 2 | Acier à chaud (tableau 3.1, c_a(θ), λ_a(θ)), protections | fait |
| 3 | Courbes de feu, flux net, diffusion de chaleur, solveur d_p | fait |
| 4 | Résistances mécaniques à chaud, χ_fi, χ_LT,fi | à venir |
| 5 | Interaction N + M, degré d'utilisation, éq. (4.22) | à venir |
| 6 | Orchestration, vérification croisée, note de calcul | à venir |
| 7 | Tracé du nomogramme | à venir |
| 8 | Validation sur exemples normatifs | à venir |
| 9 | Interface graphique | à venir |

**Conséquence pratique :** la température critique n'est pas encore calculée
depuis le chargement. Elle doit être fournie explicitement (`--theta-cr`). Tout
ce qui relève de la diffusion de chaleur est en revanche opérationnel.

## Installation

```bash
pip install -e ".[dev]"
```

Python 3.11 ou plus récent. Aucune dépendance obligatoire à l'exécution :
`openpyxl` ne sert qu'à régénérer le catalogue depuis le classeur SZS.

## Utilisation en ligne de commande

```bash
# Catalogue et facteurs de massiveté
nommo profils --famille HEB
nommo profils --nom "IPE 300" --exposition contour3

# Échauffement d'un profilé nu, avec vérification d'une température critique
nommo echauffement "IPE 300" --duree R60 --theta-cr 600

# Échauffement d'un profilé protégé
nommo echauffement "HEB 300" --duree R90 --protection flocage_fibreux --dp 20

# Épaisseur de protection nécessaire
nommo dimensionner "IPE 300" --theta-cr 550 --duree R90 --protection flocage_fibreux

# Quels profilés d'une famille tiennent, sans protection ?
nommo balayer --famille HEM --theta-cr 550

# Produits de protection disponibles
nommo protections
```

Options communes : `--exposition {contour4,contour3,caisson4,caisson3}`,
`--feu {iso834,hydrocarbure,exterieur}`, `--format {texte,csv}`.

## Utilisation comme bibliothèque

```python
from nommogramme import catalogue, Exposition, Protection, echauffement, minutes

profil = catalogue["HEB 300"]

# Élément nu
resultat = echauffement(profil, Exposition.CONTOUR_4_FACES, minutes(30))
resultat.temperature_finale          # °C à 30 min
resultat.minutes_pour_atteindre(600) # min avant 600 °C
resultat.Am_sur_V, resultat.k_sh

# Élément protégé
flocage = Protection.depuis_catalogue("flocage_fibreux", d_p=0.020)
protege = echauffement(
    profil, Exposition.CONTOUR_4_FACES, minutes(90), protection=flocage
)

# Épaisseur requise
from nommogramme import epaisseur_requise_minutes

requis = epaisseur_requise_minutes(
    profil=profil,
    exposition=Exposition.CONTOUR_4_FACES,
    protection=flocage,
    theta_cible=550.0,
    duree_requise_min=90.0,
)
print(requis)   # → « … : 12.4 mm requis → 12.5 mm retenus (θ_a = 548 °C à 90 min) »
```

Les unités internes sont strictement SI (m, m², N, W, s). Les températures
sont en degrés Celsius, comme dans la norme.

## Données

`Profilé SZS.xlsx` — les 277 profilés du catalogue SZS C5 : IPE, PEA, INP,
HEA, HEB, HEM, HHD, HL et tubes RRW. Le classeur est converti une fois pour
toutes en un CSV normalisé, versionné dans
`src/nommogramme/data/profils_szs.csv`. Pour le régénérer après modification
du classeur :

```bash
python -m nommogramme.profils.chargeur
```

La conversion recoupe systématiquement le périmètre calculé géométriquement
avec la colonne `Um` du SZS : **écart moyen 0,61 %** sur les 277 profilés.

Les propriétés des produits de protection
(`src/nommogramme/data/protections.toml`) sont des **valeurs génériques de la
littérature**, destinées au développement et aux études de faisabilité. Une
étude de projet doit utiliser celles de l'agrément technique du produit
retenu (ETE, reconnaissance AEAI).

## Tests

```bash
python -m pytest
```

115 tests couvrent le tableau 3.1 ligne à ligne, la continuité de c_a(θ) et le
pic de transformation de phase à 735 °C, les valeurs de référence des courbes
de feu, les facteurs de massiveté comparés aux tables publiées, la convergence
en pas de temps, et les invariants physiques de l'échauffement.

## Avertissement

Cet outil est en développement et n'a pas encore été confronté à des exemples
normatifs complets (lot 8). Il ne doit pas servir de justification de projet en
l'état. Les clauses citées dans le code proviennent de la connaissance du
corpus normatif et sont à recouper avec les exemplaires officiels des normes —
la liste des points à vérifier figure au §18 du plan de conception.
