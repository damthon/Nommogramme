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

Les neuf lots sont implantés, plus la mise en application. **La méthode du nomogramme est complète** : la
température critique se déduit du chargement, se lit sur une figure, et se
calcule aussi bien en ligne de commande que dans un navigateur.

| Lot | Contenu | État |
|:---:|---|:---|
| 1 | Catalogue SZS, géométrie d'exposition, A_m/V, k_sh | fait |
| 2 | Acier à chaud (tableau 3.1, c_a(θ), λ_a(θ)), protections | fait |
| 3 | Courbes de feu, flux net, diffusion de chaleur, solveur d_p | fait |
| 4 | Résistances mécaniques à chaud, χ_fi, χ_LT,fi | fait |
| 5 | Interaction N + M, degré d'utilisation, éq. (4.22) | fait |
| 6 | Orchestration, vérification croisée, note de calcul | fait |
| 7 | Tracé du nomogramme | fait |
| 8 | Validation | fait — voir [`docs/validation.md`](docs/validation.md) |
| 9 | Interface graphique | fait |
| 10 | Application de bureau distribuable | fait |

### Ce qui est validé, et contre quoi

L'outil est confronté à trois sources externes : deux supports du cycle
*steelacademy 2019*, et surtout la documentation SZS **steeltec 02:2015**
(chapitre 3, huit exemples chiffrés) dont ces cours sont tirés.

| Comparaison | Source | Écart |
|---|---|---|
| Table SZS θ_crit, 60 points (μ_fi,0 × λ̄₀) | steelacademy, Horw | moyen 0,7 °C, maximal 2 °C |
| Table SZS des facteurs de massiveté, 264 valeurs | steelacademy, Lausanne | 97,3 % à moins de 2 % |
| Poteau nu HEB 360 S355, 30 min ISO | steelacademy, Lausanne | θ_a 770,5/770 °C, N 539/537 kN |
| **Huit exemples A à H** | **steeltec 02:2015 §3** | voir ci-dessous |
| **Catalogue de profilés**, 561 valeurs sur 187 profilés | **Tables C5/05** | **aucun écart** |

Les huit exemples de la source primaire couvrent la compression protégée et
nue, **la flexion**, le dimensionnement des protections et le facteur d'ombre :

| Ex. | Grandeur | Document | Outil |
|---|---|---:|---:|
| A | φ, délai d'évaporation | 0,318 · 1 min | 0,318 · 0,96 |
| **B** | **θ_crit fléchie** (μ_fi,t = 0,456, κ = 0,7) | **654 °C** | **654,4** |
| | d_p requis pour R90 | 18 mm | 17,8 |
| C | d_p, classe 4, θ_crit = 350 °C | 50 mm | 48,9 |
| D | θ_crit / durée nue, l_fi = 0,5·L | 684 °C / 63 min | 684 / 62,2 |
| E | θ_crit / durée nue, l_fi = 1,0·L | 667 °C / 61 min | 667 / 60,1 |
| **F** | **θ_crit fléchie** (μ_fi,t = 0,49, κ = 0,7) | **643 °C** | **643,4** |
| | durée nue, d_p spray avec φ | 15 min, 11 mm | 15,8 · 10,8 |
| **G** | **[A_m/V]_sh / durée nue** | **67 m⁻¹ / 25 min** | **67,4 / 25,0** |

Trois enseignements, tous documentés :

- Le recoupement de la table θ_crit porte sur la **vérification croisée** du
  §4.2.3, pas sur l'équation (4.22) seule : celle-ci s'écarte de la table de
  15,7 °C en moyenne et jusqu'à 49 °C, l'écart croissant avec l'élancement.
  C'est la justification externe du choix de la rendre obligatoire. Les
  exemples D et E le montrent en creux : même effort relatif, 17 °C d'écart,
  et seul l'élancement les sépare.
- **Le facteur d'ombre est appliqué au bon endroit.** Une planche de cours lit
  le nomogramme sans lui, ce qui laissait planer un doute ; l'exemple G de la
  source primaire calcule [A_m/V]_sh = 0,9·[A_m/V]_b = 67 m⁻¹ avant de lire la
  durée, exactement comme cet outil, qui retrouve les 25 minutes.
- **La convention du facteur d'adaptation κ est confirmée** : le nomogramme
  s'entre avec μ₀ = μ_fi,t · κ.

Restent **sans référence externe** : le **déversement** (les deux exemples
fléchis l'excluent par la dalle) et l'**interaction N + M** (aucun exemple ne
combine les deux). Le détail — méthode, chiffres, limites, et les deux
anomalies de catalogue signalées mais non tranchées — est dans
[`docs/validation.md`](docs/validation.md), et `tests/cas_reference.toml`
accueille vos propres cas vérifiés.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate        # Windows : .\.venv\Scripts\Activate.ps1
pip install -e ".[dev,trace,ui]"
python -m pytest                 # 401 tests attendus au vert
```

Python 3.11 ou plus récent. Aucune dépendance obligatoire à l'exécution :
`openpyxl` ne sert qu'à régénérer le catalogue depuis le classeur SZS, et
`matplotlib` qu'aux figures.

Vous débutez avec Git ou Python ? Le guide
[`docs/demarrage.md`](docs/demarrage.md) reprend tout pas à pas depuis
l'installation, avec Visual Studio Code.

## Utilisation en ligne de commande

```bash
# Vérification complète N + M par la méthode du nomogramme
nommo verifier "HEB 300" --nuance S355 --N 850 --My 120 \
      --L 4 --lfi 2 --duree R60 --protection flocage_fibreux --dp 25

# La même, avec note de calcul et figures
nommo verifier "HEB 300" --N 850 --My 120 --L 4 --lfi 2 --duree R60 \
      --rapport note.md --tracer nomogramme.png --tracer-echauffement courbe.png

# Catalogue et facteurs de massiveté
nommo profils --famille HEB
nommo profils --nom "IPE 300" --exposition contour3

# Échauffement seul, à température critique imposée
nommo echauffement "IPE 300" --duree R60 --theta-cr 600

# Échauffement d'un profilé protégé
nommo echauffement "HEB 300" --duree R90 --protection flocage_fibreux --dp 20

# Épaisseur de protection nécessaire
nommo dimensionner "IPE 300" --theta-cr 550 --duree R90 --protection flocage_fibreux

# Quels profilés d'une famille tiennent, sans protection ?
nommo balayer --famille HEM --theta-cr 550

# Produits de protection disponibles
nommo protections

# Audit de cohérence du catalogue
nommo controler

# Interface graphique dans le navigateur
nommo interface
```

Options communes : `--exposition {contour4,contour3,caisson4,caisson3}`,
`--feu {iso834,hydrocarbure,exterieur}`, `--format {texte,csv}`.

Propres à `verifier` : `--contexte {sia,eurocode}` pour changer de référentiel,
`--maintien-lateral` quand la semelle comprimée est bloquée par une dalle,
`--kappa1` et `--kappa2` pour les facteurs d'adaptation du §4.2.3.3, `--C1` pour
le diagramme de moment, `--theme clair|sombre` pour les figures. Le code de
sortie vaut 0 si l'exigence est satisfaite, 2 sinon — utilisable en script.

## Utilisation comme bibliothèque

### Vérification complète

```python
from nommogramme import (
    catalogue, CasDeCharge, Exposition, Nuance, Protection, verifier,
)

cas = CasDeCharge(
    N_fi_Ed=850e3,      # N, positif en compression
    My_fi_Ed=120e3,     # N·m
    L=4.0,              # m, longueur d'épure
    l_fi_y=2.0,         # m, poteau continu d'étage courant : 0,5·L
    l_fi_z=2.0,
    beta_M_y=1.4,
)

r = verifier(
    profil=catalogue["HEB 300"],
    nuance=Nuance.S355,
    cas=cas,
    exposition=Exposition.CONTOUR_4_FACES,
    duree_requise_min=60,
    protection=Protection.depuis_catalogue("flocage_fibreux", d_p=0.025),
)

r.mu_0                  # degré d'utilisation à 20 °C
r.theta_cr_nomogramme   # °C, éq. (4.22)
r.theta_cr_exact        # °C, vérification croisée §4.2.3
r.theta_cr              # °C, la plus défavorable des deux
r.t_fi_d_minutes        # durée avant d'atteindre θ_cr
r.verdict               # Verdict.SATISFAIT
r.avertissements

print(r.note_de_calcul())   # note Markdown, avec les clauses citées
```

### Figures

```python
from nommogramme.nomogramme.trace import tracer_nomogramme, tracer_echauffement

tracer_nomogramme(r, "nomogramme.png")        # les deux quadrants + le chemin de lecture
tracer_echauffement(r, "courbe.png", theme="sombre")
```

Le nomogramme montre les deux quadrants partageant l'axe des températures :
à gauche μ₀ → θ_cr par l'équation (4.22), à droite l'échauffement sous la
courbe de feu. Quand la vérification croisée abaisse la température critique,
le décrochement est tracé et chiffré sur l'axe partagé — c'est le fait
marquant de la figure, et sans annotation il passerait pour une erreur de
tracé.

Les deux teintes de série viennent d'une palette validée pour la déficience de
vision des couleurs : séparation ΔE 24,7 en clair et 26,8 en sombre, pour un
seuil de 8. Chaque courbe porte aussi son étiquette directe, l'identité ne
reposant jamais sur la seule couleur. `matplotlib` est un extra :
`pip install 'nommogramme[trace]'`.

## Application de bureau

C'est la forme destinée à être **distribuée** : un fichier à télécharger, un
double-clic, l'écran s'ouvre. Ni Python à installer, ni ligne de commande, ni
navigateur.

Téléchargez `Nommogramme-windows.zip` depuis la page
[Releases](https://github.com/damthon/Nommogramme/releases), décompressez-le,
lancez `Nommogramme.exe`.

> **Windows affichera « Windows a protégé votre ordinateur »** : le programme
> n'est pas signé par un certificat commercial (~300 CHF/an). Cliquez sur
> « Informations complémentaires », puis « Exécuter quand même ». Si votre
> service informatique bloque les exécutables téléchargés, mieux vaut le leur
> faire autoriser que contourner la protection.

Seul Windows est compilé — c'est la seule cible demandée. Sur tout autre
système, et sur un poste où Python est installé, la même fenêtre s'obtient
par :

```bash
pip install -e ".[bureau]"
nommo bureau
```

L'exécutable pèse **47 Mo**. L'interface Streamlit ci-dessous en aurait demandé
près de 250 : elle entraîne pandas et pyarrow, 230 Mo à eux deux, dont l'outil
n'utilise rien. Elle est aussi un serveur web, ce qui veut dire un port local à
ouvrir et un pare-feu à convaincre. La version de bureau repose sur Tkinter,
livré avec Python : démarrage immédiat, aucun serveur.

### Comment l'exécutable est produit

Sur une machine Windows :

```bash
pip install -e ".[bureau]" pyinstaller
pyinstaller packaging/nommogramme.spec
```

PyInstaller embarque l'interpréteur de la machine qui compile : **on ne produit
pas un `.exe` depuis Linux.** C'est le rôle de
[`.github/workflows/executable.yml`](.github/workflows/executable.yml), qui
compile sur une machine Windows fournie par GitHub, puis publie l'archive dans
les Releases. Pousser une étiquette suffit :

```bash
git tag v0.2.0 && git push origin v0.2.0
```

Le paquet produit est contrôlé avant publication, sur l'exécutable lui-même et
non sur le code source :

```bash
./dist/Nommogramme.exe --autotest           # catalogue, produits, calcul, tracé
./dist/Nommogramme.exe --autotest-fenetre   # ouvre la fenêtre et la peint
```

Un paquet peut se compiler sans erreur et être inutilisable — il suffit qu'un
fichier de données manque, ou qu'un import différé ait échappé à l'analyse.
C'est arrivé ici deux fois : le catalogue de profilés, puis
`PIL._tkinter_finder`, sans lequel aucune figure ne s'affiche. Le second
contrôle existe parce que le premier n'avait pas suffi à l'attraper.

Un troisième piège ne tient pas à l'empaquetage mais à Windows : sa console
utilise cp1252, qui ne contient ni `θ`, ni `μ`, ni les exposants. Le premier
message affichant `θ_cr` y levait `UnicodeEncodeError` et arrêtait le
programme, alors que le calcul s'était bien passé. Le lanceur force désormais
UTF-8 sur ses sorties, et `tests/test_lanceur.py` reconstitue une console
cp1252 pour que le défaut ne puisse pas revenir — la CI tournant sous Linux,
elle ne le reverrait jamais autrement.

## Interface dans le navigateur

```bash
pip install -e ".[ui]"
nommo interface
```

Un navigateur s'ouvre sur `localhost:8501`. La barre latérale porte tous les
paramètres — profilé, nuance, charges, longueurs, exposition, courbe de feu,
protection, durée exigée, référentiel — et l'écran principal affiche le
verdict, μ₀, les deux températures critiques et leur écart, les
avertissements, les deux figures et la note de calcul téléchargeable. Chaque
modification recalcule immédiatement.

Les trois surfaces — ligne de commande, navigateur, bureau — ne contiennent
**aucun calcul**. Les deux interfaces graphiques partagent
`interface/saisie.py`, qui porte le jeu de paramètres et l'unique traduction
vers `verifier()` : deux conversions d'unités écrites séparément finiraient par
diverger, et il faudrait alors se demander laquelle a raison. Un test compare
ce que chaque écran affiche à ce que la bibliothèque renvoie.

### Thermique seule

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

Le classeur a été **confronté page à page au SZS C5/05**, l'ouvrage dont il
est la transcription : 561 valeurs sur 187 profilés — section, rayon de
giration faible, périmètre — **aucun écart**. Deux corrections restent
appliquées à la lecture, toutes deux vérifiées contre le catalogue imprimé et
sans modification du fichier source :

- ⚠️ **La colonne `iz3` est figée à 15,0018 mm sur les 108 lignes RRW.** Le C5
  publie deux tables pour les profils creux — les tubes carrés avec une seule
  colonne `i` (I_y = I_z), les rectangulaires avec i_y et i_z séparés ; la
  fusion des deux dans le classeur a propagé la valeur du premier tube. Pour
  un poteau RRW 400/400/10 de 6 m, cela sous-estimerait la résistance au
  flambement d'un facteur 23. Le chargeur recalcule `i_z = √(I_z/A)`, ce qui
  reproduit la colonne officielle à moins de 1 %.
- ⚠️ **L'`I_z` du HHD 320.74 est faux dans le SZS C5/05 lui-même**, et le
  classeur ne fait que le recopier. Le rayon de giration tabulé, le module
  élastique tabulé et la géométrie donnent tous les trois 49,6·10⁶ mm⁴ contre
  les 45,59·10⁶ imprimés. Le chargeur rétablit la valeur ; l'originale est
  conservée dans `Profil.Iz_tabule`.

`nommo controler` ne signale **plus aucune anomalie** sur les 277 profilés.
Détails et impact dans [`docs/validation.md`](docs/validation.md).

Les propriétés des produits de protection
(`src/nommogramme/data/protections.toml`) sont des **valeurs génériques de la
littérature**, destinées au développement et aux études de faisabilité. Une
étude de projet doit utiliser celles de l'agrément technique du produit
retenu (ETE, reconnaissance AEAI).

## Tests

```bash
python -m pytest
```

401 tests couvrent le tableau 3.1 ligne à ligne, la continuité de c_a(θ) et le
pic de transformation de phase à 735 °C, les valeurs de référence des courbes
de feu, les facteurs de massiveté comparés aux tables publiées, la convergence
en pas de temps, les invariants physiques de l'échauffement, les huit valeurs
de référence de l'équation (4.22) et son inversion, et le comportement attendu
de la vérification croisée sur éléments trapus et élancés.

`tests/test_validation.py` va plus loin : il confronte chaque résultat à une
solution du même problème obtenue par une voie différente — quadrature en
température contre pas-à-pas en temps, enthalpie en forme close contre
accumulation numérique, éq. (4.22) contre interpolation du tableau 3.1.

`tests/cas_reference.toml` accueille vos propres cas vérifiés : chacun devient
un test de non-régression, sans écrire de code.

Les tests de l'interface de bureau ouvrent une vraie fenêtre Tk et lisent ce
qu'elle affiche. Sous Linux, tkinter est un paquet système séparé et il faut un
écran : `sudo apt install python3-tk xvfb`, puis `xvfb-run -a python -m pytest`.
Sans eux ces tests s'écartent d'eux-mêmes — l'intégration continue refuse ce
cas, un contrôle qui ne contrôle rien étant pire que pas de contrôle.

Les tests de tracé vérifient que les figures se produisent pour chaque cas de
figure structurellement différent, que les annotations attendues y sont et que
les couleurs sont bien celles de la palette validée. Ils ne peuvent pas juger
qu'une figure est lisible : cela a demandé de les regarder.

## Avertissement

Cet outil est en développement. La compression — protégée et nue — et la
flexion simple sont recoupées avec la documentation SZS steeltec 02:2015.
**Le déversement et l'interaction N + M n'ont été comparés à aucun calcul de
référence externe.** Il ne doit pas servir de justification de projet en
l'état. Les clauses citées dans le code proviennent de la connaissance du
corpus normatif et sont à recouper avec les exemplaires officiels des normes —
la liste des points à vérifier figure au §18 du plan de conception.
