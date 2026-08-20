# Rapport de validation

État au lot 8. Ce document dit **ce qui est établi, ce qui ne l'est pas, et par
quel moyen** — de façon qu'un lecteur puisse décider lui-même du crédit à
accorder à un résultat de l'outil.

## Références externes

Deux supports du cycle **steelacademy 2019**, fournis par l'utilisateur :

| | Source | Ce qu'elle couvre |
|---|---|---|
| **A** | Horw, 12 septembre 2019, Dr. Patrick Roman Schulthess — « Beispiel: Durchlaufende HEA Stütze », planches 36 à 39, et la table de températures critiques à l_k,fi = 0,5·L_k0 qui l'accompagne | poteau comprimé **protégé** |
| **B** | Lausanne, 25 septembre 2019, Dr. Roland Bärtschi — « Exemple d'application : poteau en acier non revêtu », planches 22 et 23 | poteau comprimé **nu**, et la table SZS des facteurs de massiveté |
| **C** | **SZS steeltec 02:2015**, « Protection incendie des structures », chapitre 3 « Application du nomogramme », pages 31 à 33 — huit exemples A à H | la **source primaire** : compression, **flexion**, protections, facteur d'ombre |

La source C est le document dont les deux cours sont tirés ; son exemple A est
mot pour mot celui des planches de Horw. C'est la référence de loin la plus
large, et la seule à sortir de la compression.

Les contrôles correspondants sont dans `tests/test_reference_szs.py` (source A),
`tests/test_reference_bartschi.py` et `tests/test_reference_massivete.py`
(source B), `tests/test_reference_steeltec.py` (source C).

## Source A — le poteau protégé

### La table des températures critiques

Soixante points de la table, couvrant μ_fi,0 de 0,20 à 0,70 et λ̄₀ de 0,2 à
2,0, ont été confrontés aux deux voies de l'outil.

| Voie | Écart moyen | Écart maximal |
|---|---:|---:|
| **Vérification croisée** (§4.2.3, χ_fi + interaction) | **0,7 °C** | **2 °C** |
| Équation (4.22) seule | 15,7 °C | 49 °C |

La vérification croisée reproduit la table publiée à 2 °C près sur toute son
étendue. C'est la validation la plus forte dont dispose le projet : la table
SZS est construite indépendamment, et l'accord porte sur toute la chaîne
mécanique — χ_fi, la courbe de flambement unique α = 0,65·√(235/f_y),
l'élancement corrigé λ̄_θ = λ̄·√(k_y,θ/k_E,θ), et les facteurs du tableau 3.1.

L'écart de l'équation (4.22) n'est pas un bruit : il **croît de façon
monotone** avec l'élancement, de −2 °C en moyenne à λ̄₀ = 0,2 jusqu'à +35 °C à
λ̄₀ = 2,0. C'est exactement le défaut annoncé au §13 du plan de conception,
mesuré ici contre une référence externe au lieu d'être estimé. La décision de
rendre la vérification croisée obligatoire s'en trouve justifiée.

### L'exemple chiffré

HEA 300 en S235, encaissée de plaques fibres-silicate de calcium de 20 mm,
N_Ed,fi = 1205 kN, L_k0 = 3,0 m, l_k,fi = 0,5·L_k0.

| Grandeur | Planche | Outil |
|---|---:|---:|
| α | 0,65 | 0,650 |
| λ̄₀ | 0,427 | 0,426 |
| χ_fi à 20 °C | 0,756 | 0,757 |
| N_b,fi,0,Rd | 2010 kN | 2010 kN |
| A_p/V, encaissement 4 faces | 104 m⁻¹ | 104,4 m⁻¹ |
| φ | 0,318 | 0,319 |
| **θ_crit** | **580 °C** | **579 °C** |
| **Durée de résistance** | **111 min** | **110 min** |

La planche donne deux lectures de durée : 100 min en négligeant φ, 111 min en
en tenant compte. L'intégration pas à pas de l'équation (4.27) retrouve la
seconde.

### Une différence de convention à connaître

Le seul écart notable porte sur le **degré d'utilisation** : la planche donne
μ = 0,60, l'outil affiche 0,52. Ce n'est pas une erreur, mais deux portes
d'entrée différentes :

* la **table SZS** se lit avec μ₀ et λ̄₀ calculés à **température ambiante**,
  donc avec L_k0 ; le facteur 0,5 de la longueur d'incendie est incorporé dans
  la table elle-même — d'où la mention « Wichtig, dass Knicklänge für System
  bei Raumtemperatur eingesetzt wird » sur la planche ;
* l'**EN 1993-1-2 §4.2.4** définit μ₀ = E_fi,d / R_fi,d,0 où R_fi,d,0 est la
  résistance à t = 0 **avec les conditions d'appui de l'incendie**, donc avec
  l_fi.

Les deux mènent à la même température critique — la table est construite pour
cela, et les 60 points ci-dessus le confirment. Mais si vous comparez un μ₀
affiché par cet outil à celui d'une note de calcul suisse, attendez-vous à
l'écart.

## Source B — le poteau nu, et la table de massiveté

### L'énoncé

HEB 360 en S355, longueur 4,00 m, bi-articulé donc l_fi = 4,00 m. Quelle
capacité portante subsiste après 30 minutes de feu ISO ? La planche lit
θ = 770 °C sur le nomogramme SZS, puis en déduit N_b,fi,t,Rd = 537 kN.

| Grandeur | Planche | Outil |
|---|---:|---:|
| A | 18 060 mm² | 18 100 mm² |
| I_z | 1,01·10⁸ mm⁴ | 1,01·10⁸ mm⁴ |
| i_z | 74,8 mm | 74,9 mm |
| λ̄₀ | 0,70 | 0,699 |
| α | 0,529 | 0,529 |
| A_m/V, contour 4 faces | 102 m⁻¹ | 102,2 m⁻¹ |
| **θ_a à 30 min** | **770 °C** | **770,5 °C** |
| k_y,θ | 0,146 | 0,1460 |
| k_E,θ | 0,102 | 0,1020 |
| λ̄_θ | 0,838 | 0,836 |
| φ_θ | 1,072 | 1,072 |
| χ_fi | 0,574 | 0,575 |
| **N_b,fi,t,Rd** | **537 kN** | **539 kN** |

Les 2 kN d'écart final viennent de la section : 18 100 mm² au catalogue contre
18 060 sur la planche, soit 0,2 %.

C'est la première validation de l'**échauffement d'un profilé nu**. La
température à 30 minutes se joue à 0,5 °C — ce qui met en cause d'un coup
l'équation (4.25), le flux net de l'EN 1991-1-2 §3.1, la chaleur spécifique
c_a(θ) de l'équation (3.2) et l'intégration en temps. Aucun de ces quatre
éléments n'avait de référence externe auparavant.

### Le facteur d'ombre : une divergence de convention, pas de calcul

La lecture du nomogramme est faite à A_m/V = 102 m⁻¹, la valeur géométrique
brute. Le facteur d'ombre du §4.2.5.1(2) n'est pas appliqué ; avec lui,
l'entrée serait k_sh · A_m/V = 0,642 · 102 = 65,6 m⁻¹.

| Entrée | θ à 30 min | N_b,fi,t,Rd |
|---|---:|---:|
| 102 m⁻¹ — planche | 770 °C | 537 kN |
| 65,6 m⁻¹ — §4.2.5.1(2) | 730 °C | 676 kN |

**L'outil applique k_sh** et affiche donc 730 °C. Ce n'est pas un désaccord sur
le calcul : nourri de la même entrée, il retrouve les 770 °C de la planche à
0,5 °C près. C'est un désaccord sur ce qu'il faut entrer, et il pèse 40 °C et
26 % de capacité résiduelle. La planche est du côté sûr.

> **Tranché depuis.** La source C ci-dessous — la documentation SZS elle-même —
> lève l'ambiguïté : son exemple G calcule explicitement
> [A_m/V]_sh = [A_m/V]·k_sh = 0,9·[A_m/V]_b = 0,9·74 = 67 m⁻¹ avant de lire la
> durée sur le nomogramme. La SZS applique donc k_sh ; ses courbes ne
> l'intègrent pas. **L'outil est dans la convention de la SZS**, et cette
> planche de cours simplifiait. Reste l'avertissement pratique : comparer un
> θ_a de cet outil à une lecture de nomogramme suppose de savoir laquelle des
> deux entrées a servi.

### La table SZS des facteurs de massiveté

La planche 23 reproduit la table SZS des « Profilfaktoren ». Les colonnes IPE,
HEA et HEB en ont été relevées : **264 valeurs**, soit 66 profilés × 4
expositions.

| | |
|---|---:|
| Valeurs comparées | 264 |
| Écart médian | +0,47 |
| Dans une bande de 2 % | 257, soit 97,3 % |
| Écart maximal | +5,7 (HEB 280) |

L'écart médian de +0,5 n'est pas un biais : c'est la signature d'une table
**tronquée** et non arrondie. Une table arrondie donnerait une médiane nulle
et symétrique. Le module de géométrie tombe donc juste, et le résidu est une
convention d'affichage.

Le lot 1 ne disposait jusqu'ici que d'un recoupement interne — le périmètre
calculé contre la colonne `Um` du classeur de l'utilisateur. Cette table est
externe, et elle porte sur le rapport A_m/V complet, donc aussi sur la section.
Elle confirme au passage l'interprétation des quatre expositions : le HEB 360
publié à 102 / 73 / 85 / 56 est calculé à 102,2 / 72,9 / 85,7 / 56,4.

### Une seconde anomalie de catalogue : le HEB 280

Sept valeurs sur 264 s'écartent de plus de 2 %. Trois sont isolées dans leur
ligne — un seul chiffre en cause, le profil typique d'une erreur de relevé sur
une capture d'écran de basse définition. Les quatre autres sont les **quatre
colonnes du HEB 280**, toutes fausses du même rapport :

| Exposition | Table | Calculé | Rapport |
|---|---:|---:|---:|
| contour 4 faces | 118 | 123,7 | 1,048 |
| caisson 4 faces | 82 | 85,5 | 1,043 |
| contour 3 faces | 97 | 102,3 | 1,055 |
| caisson 3 faces | 61 | 64,1 | 1,051 |

Quatre chiffres ne se lisent pas mal du même pourcentage. Un rapport constant
sur les quatre expositions désigne le **dénominateur commun**, c'est-à-dire la
section A : le périmètre change d'une colonne à l'autre, pas elle. Le catalogue
retient A = 131,0 cm², valeur courante du HEB 280 ; la table impliquerait
137 cm². Les voisins immédiats, HEB 260 et HEB 300, concordent tous les huit.

**Aucune correction n'est appliquée** — même traitement que le HHD 320.74.
Trancher demande les tables SZS d'origine. Si vous les avez sous la main, c'est
une vérification d'une minute qui lèverait le doute.

## Source C — les huit exemples de steeltec 02:2015

C'est la documentation SZS elle-même, chapitre 3, huit exemples chiffrés de
bout en bout. Elle apporte trois choses qu'aucune autre source n'apportait :
la **flexion**, la **confirmation du facteur d'ombre**, et le
**dimensionnement des protections**.

| Ex. | Cas | Grandeur | Document | Outil |
|---|---|---|---:|---:|
| **A** | HEA 300 revêtu, silicate 20 mm | (A_p/V)(λ_p/d_p) | 780 W/m³K | 780 |
| | | φ | 0,318 | 0,318 |
| | | délai d'évaporation t_v | 1 min | 0,96 |
| **B** | Solive IPE 300 revêtue, R90 | M_fi,t=0,Rd | 148 kNm | 147,6 |
| | | **θ_crit** (μ_fi,t = 0,456, κ = 0,7) | **654 °C** | **654,4** |
| | | A_p/V caisson 3 faces | 139 m⁻¹ | 139,4 |
| | | d_p requis | 18 mm | 17,8 |
| **C** | Âme mince classe 4, R60 | plafond de massiveté | 610 W/m³K | 614 |
| | | d_p requis | 50 mm | 48,9 |
| **D** | Rond ⌀280 continu, l_fi = 0,5·L | λ̄₀ / χ_fi | 0,609 / 0,657 | 0,608 / 0,657 |
| | | μ_fi,0 | 0,315 | 0,316 |
| | | **θ_crit** | **684 °C** | **684** |
| | | durée nue | 63 min | 62,2 |
| **E** | Rond ⌀280 articulé, l_fi = 1,0·L | λ̄₀ / χ_fi | 0,456 / 0,741 | 0,456 / 0,740 |
| | | **θ_crit** | **667 °C** | **667** |
| | | durée nue | 61 min | 60,1 |
| **F** | Poutre mixte IPE 270, R60 | **θ_crit** (μ_fi,t = 0,49, κ = 0,7) | **643 °C** | **643,4** |
| | | A_m/V 3 faces | 197 m⁻¹ | 197,2 |
| | | durée nue | 15 min | 15,8 |
| | | d_p spray, φ = 0 puis φ = 0,18 | 12 puis 11 mm | 12,2 puis 10,8 |
| **G** | HEB 340 nu, l_fi = 0,7·L | λ̄₀ / χ_fi | 0,57 / 0,678 | 0,566 / 0,680 |
| | | N_b,fi,0,Rd | 2725 kN | 2734 |
| | | **θ_crit** | **683 °C** | **685** |
| | | **[A_m/V]_sh** | **67 m⁻¹** | **67,4** |
| | | **durée nue** | **25 min** | **25,0** |
| **H** | Le même, peinture intumescente | A_m/V pour les tables produit | 105 m⁻¹ | 105,8 |

### 1. La flexion, enfin

Les exemples B et F sont les **premières références externes du projet qui ne
portent pas sur la compression**. Ils entrent dans le nomogramme avec μ_fi,t et
le facteur d'adaptation κ, et donnent θ_crit à l'unité : 654 °C et 643 °C,
retrouvés à 0,4 °C près par l'équation (4.22).

Ils fixent aussi la **convention d'entrée**, que l'exemple F écrit noir sur
blanc : « pour μ₀ = μ_fi,t · κ = 0,49 · 0,7 = 0,34 cette formule donne
Θ_crit = 643 °C ». C'est bien ce que fait l'outil, qui divise le moment
résistant par κ₁·κ₂.

Passé à `verifier()` de bout en bout, l'exemple B rend μ₀ = 0,320 contre 0,319,
θ_crit = 654 °C, A_p/V = 139,4 m⁻¹, et les 18 mm du document donnent 101 min,
donc R90 satisfait.

Reste hors d'atteinte : le **déversement** (les deux exemples l'excluent par la
dalle) et l'**interaction N + M** (aucun exemple ne combine les deux).

### 2. Le facteur d'ombre, tranché

L'exemple G écrit l'identité en toutes lettres :

    [A_m/V]_sh = [A_m/V] · k_sh    avec    k_sh = 0,9 · [A_m/V]_b / [A_m/V]

soit [A_m/V]_sh = 0,9 · [A_m/V]_b = 0,9 · 74 = 67 m⁻¹ pour le HEB 340, et lit
la durée sur cette valeur — 25 minutes, que l'outil retrouve à 0,0 min près.

**La SZS applique donc k_sh ; ses courbes ne l'intègrent pas.** L'ambiguïté
laissée par la source B est levée, et l'outil est du bon côté. La planche de
Lausanne simplifiait.

L'exemple H ajoute une nuance qu'il est facile de manquer : les tables
d'épaisseur de peinture intumescente se lisent sur le facteur de massiveté
**brut** (105 m⁻¹), pas sur [A_m/V]_sh. Le facteur d'ombre corrige le
rayonnement reçu par un profilé nu ; il ne concerne pas le dimensionnement
d'un revêtement.

### 3. Deux points « à recouper » désormais confirmés

- **Le délai d'évaporation.** t_v = p·ρ_p·d_p²/(5·λ_p) est bien la formule de
  la SZS, avec **p exprimé en pourcent** — c'est aussi la convention du champ
  `Protection.humidite`. L'exemple A donne 1 minute pour p = 3 %, ρ_p = 600,
  d_p = 20 mm, λ_p = 0,15 ; l'outil calcule 0,96 min.
  *À noter : la formule imprimée dans le document porte d_p = 0,025 alors que
  son propre énoncé dit 20 mm. Avec 0,025 le résultat serait 1,5 min. C'est le
  0,025 imprimé qui est faux.*
- **La température critique conventionnelle des sections de classe 4.**
  L'exemple C confirme θ_crit = 350 °C et son renvoi, **SIA 263 chiffre
  4.8.5.9**. Les exemples G et H confirment par ailleurs la valeur de 500 °C du
  Répertoire suisse de la protection incendie, utilisable sans vérifier le taux
  de sollicitation.

### 4. Une divergence de numérotation

Le document cite la formule de la température critique comme l'**équation 4.18**
de l'EN 1993-1-2, là où cet outil la cite comme l'**équation (4.22)** — la
numérotation de l'EN 1993-1-2:2005. La formule est identique au coefficient
près (39,19 · ln[1/(0,9674·μ₀^3,833) − 1] + 482). C'est un écart d'édition, pas
de contenu, mais il faut le savoir en comparant les références.

### 5. Ce que les exemples D et E montrent en creux

Même barreau rond, même effort, deux longueurs de flambement. L'effort relatif
μ₀·χ_fi est identique à 0,001 près (0,207), et pourtant θ_crit vaut 684 °C
d'un côté et 667 °C de l'autre. Seul l'élancement les sépare.

C'est exactement ce que la **vérification croisée** capte et que l'équation
(4.22) — qui ne connaît que μ₀ — ne peut pas voir. La SZS y répond par des
abaques distincts selon le rapport l_fi/L_K,0 (figures 47, 48, 49 pour 0,5,
0,7 et 1,0). L'outil n'a pas besoin de ces trois abaques : il recalcule.

### Ce qui reste hors d'atteinte

Les recueils d'exemples publiés — JRC, SCI P375, guides Infosteel, et
`szs.ch` lui-même — restent inaccessibles depuis l'environnement de
développement : le proxy réseau les bloque, et les normes sont sous droits.
Les trois références ci-dessus ont pu être exploitées uniquement parce que
l'utilisateur en a fourni les pages.

Ce qui manque encore, par ordre d'utilité :

1. **Le déversement.** Les deux exemples fléchis l'excluent par la dalle. Aucun
   contrôle externe ne porte sur χ_LT,fi.
2. **L'interaction N + M.** Aucun exemple ne combine effort normal et moment ;
   les équations (4.21a) et (4.21b) ne sont vérifiées que par cohérence interne.
3. **Les nuances autres que S235 et S355**, et les **profilés creux**, dont le
   facteur d'ombre vaut 1 par une autre voie.

## Recoupements internes

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
| Élément comprimé protégé — θ_crit, φ, durée | **validé** — sources A et C (ex. A) |
| Élément comprimé nu — éq. (4.25), flux net, c_a(θ) | **validé** — source B à 0,5 °C, source C (ex. D, E, F, G) |
| **Flexion** — éq. (4.22) avec κ, dimensionnement d_p | **validé** — source C (ex. B et F) |
| Facteur d'ombre k_sh et sa convention d'entrée | **validé** — source C (ex. G), à 0,4 m⁻¹ |
| Facteurs de massiveté, 4 expositions | **validé** — table SZS, 257 valeurs sur 264 |
| χ_fi, λ̄_θ, α à chaud | **validé** — 4 profilés, 2 nuances, élancements de 0,43 à 0,70 |
| Vérification croisée contre abaques l_fi/L distincts | **validé** — source C (ex. D et E) |
| Délai d'évaporation t_v = p·ρ_p·d_p²/(5·λ_p), p en % | **validé** — source C (ex. A) |
| θ_crit conventionnel 350 °C classe 4, SIA 263 4.8.5.9 | **validé** — source C (ex. C) |
| θ_crit conventionnel 500 °C, Répertoire suisse | **validé** — source C (ex. G et H) |
| **Déversement — χ_LT,fi** | **non validé** — les exemples fléchis l'excluent |
| **Interaction N + M — éq. (4.21a) et (4.21b)** | **non validé** — aucune référence externe |
| Profilés creux, nuances hors S235 / S355 | **non validé** |
| A du HEB 280 | anomalie signalée, non tranchée |
| I_z du HHD 320.74 | anomalie signalée, non tranchée |
| Numérotation exacte des éq. des facteurs k_y, k_z, k_LT (§4.2.3.5) | à recouper |
| Chiffre SIA 263 traitant la résistance au feu | à recouper |
| Constante de gauchissement I_w ≈ I_z·(h−t_f)²/4 | approximation, absente du catalogue SZS |

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
