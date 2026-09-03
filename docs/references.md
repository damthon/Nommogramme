# Références normatives

Toutes les clauses citées par l'outil — à l'écran, dans les infobulles, sur les
figures et dans la note de calcul — viennent d'un registre unique,
[`src/nommogramme/references.py`](../src/nommogramme/references.py). Cette page
en est la copie lisible ; elle se régénère par :

```bash
python -m nommogramme.references
```

## Pourquoi une référence complète

« éq. (4.22) » ne se retrouve pas. Il faut déjà savoir de quelle norme il
s'agit, puis feuilleter jusqu'au bon chapitre. Une référence utile porte les
trois éléments — **norme, paragraphe, équation** — et l'outil les affiche
désormais partout sous la même forme :

> EN 1993-1-2 §4.2.4, éq. (4.22)

Les paramètres qui ne se comprennent pas sans leur clause — κ₁, κ₂, C₁, β_M,
l_fi — portent une **infobulle** qui donne l'explication, la référence, et la
réserve s'il y en a une. Dans l'interface de bureau elle apparaît au survol ou
à la prise de focus clavier ; dans l'interface web, c'est le point
d'interrogation de Streamlit.

## Ce qui reste à recouper

Cinq clauses sur trente-six n'ont **pas** été confrontées à un exemplaire
officiel des normes. Elles sont marquées comme telles dans le registre, dans
les infobulles, et en fin de note de calcul. Ce n'est pas un détail
d'affichage : c'est la seule façon honnête de distinguer ce qui a été vérifié
de ce qui vient de la connaissance du corpus.

### EN 1993-1-2 §4.2.3.3(7) — les facteurs d'adaptation κ₁ et κ₂

Le contenu retenu est :

- κ₁ = 1,00 pour une poutre exposée sur ses quatre faces ;
- κ₁ = 0,70 pour une poutre **non protégée** exposée sur trois faces, avec une
  dalle béton ou mixte en quatrième face ;
- κ₁ = 0,85 pour une poutre **protégée** dans la même configuration ;
- κ₂ = 0,85 aux appuis d'une poutre hyperstatique, 1,00 dans tous les autres cas.

**Une divergence est signalée et non tranchée.** La documentation SZS
*steeltec 02:2015* retient κ = 0,70 dans ses exemples B (solive IPE 300
revêtue) et F (poutre mixte IPE 270 avec peinture intumescente), tous deux
**protégés** — là où le critère ci-dessus donnerait 0,85. Or 0,70 est le choix
le *moins* conservatif des deux : μ₀ = μ_fi,t · κ, donc un κ plus petit relève
la température critique.

L'outil ne tranche pas, et n'a pas à le faire : κ₁ est une **donnée d'entrée**.
Les deux exemples SZS sont reproduits à 0,4 °C près avec κ = 0,70, ce qui
valide la chaîne de calcul indépendamment du choix de la valeur. C'est à
l'ingénieur de retenir la sienne, en connaissance de cet écart.

### EN 1993-1-2 §4.2.3.5 — la numérotation des facteurs d'interaction

Les six expressions de k_y, k_z, k_LT et μ_y, μ_z, μ_LT sont bien celles du
§4.2.3.5, et le contenu en est certain. C'est leur **numérotation exacte**
dans le texte normatif qui reste à confirmer ; l'outil cite donc le paragraphe
sans numéro d'équation.

### ENV 1993-1-1 annexe F — le moment critique M_cr et le facteur C₁

Ni l'EN 1993-1-1:2005 ni l'EN 1993-1-2 ne donnent le moment critique élastique
de déversement. La formule employée vient de l'ENV 1993-1-1 annexe F, reprise
par le NCCI SN003a-FR. Valeurs usuelles de C₁ proposées dans l'infobulle :

| Diagramme de moment | C₁ |
|---|---:|
| constant | 1,00 |
| charge répartie | 1,13 |
| charge concentrée à mi-portée | 1,35 |
| double courbure symétrique | 1,88 |

### SIA 263 et SIA 260 — les numéros de chiffres

La SIA 263 ne redonne pas les équations de résistance au feu : elle renvoie à
l'EN 1993-1-2, dont proviennent toutes les clauses citées ici. Ce qui relève du
référentiel suisse est l'**encadrement** — combinaison d'actions, facteurs
partiels, ψ₂ pour toutes les actions variables — et se concentre dans
[`contexte.py`](../src/nommogramme/contexte.py).

Les numéros de chiffres SIA correspondants n'ont pas été recoupés, et l'outil
préfère ne pas en inventer : il nomme le chapitre plutôt qu'un numéro dont il
n'est pas sûr.

## Le registre complet

| Norme | Paragraphe | Équation | Objet | État |
|---|---|---|---|---|
| EN 1991-1-2 | §3.2 | — | courbes de feu nominales ISO 834, hydrocarbure, extérieur | confirmée |
| EN 1991-1-2 | §4.3.1 | — | combinaison d'actions en situation d'incendie | confirmée |
| EN 1993-1-1 | §5.5.2, tab. 5.2 | — | élancements limites de parois, classes 1 à 4 | confirmée |
| EN 1993-1-1 | §6.2.6 | — | aire de cisaillement A_v | confirmée |
| EN 1993-1-2 | annexe E | — | température critique conventionnelle de classe 4 | confirmée |
| EN 1993-1-2 | fig. 4.2 | — | facteur de moment uniforme équivalent β_M | confirmée |
| EN 1993-1-2 | §2.3(1)P | — | facteur partiel γ_M,fi en situation d'incendie | confirmée |
| EN 1993-1-2 | §2.4.2 | (2.5) | niveau de charge η_fi | confirmée |
| EN 1993-1-2 | §3.2.1, tab. 3.1 | — | facteurs de réduction k_y,θ, k_p,θ et k_E,θ | confirmée |
| EN 1993-1-2 | §4.2.2 | — | coefficient ε = 0,85·√(235/f_y) à chaud | confirmée |
| EN 1993-1-2 | §4.2.3 | — | résistances complètes à chaud — la vérification croisée | confirmée |
| EN 1993-1-2 | §4.2.3.1 | (4.3) | résistance à la traction | confirmée |
| EN 1993-1-2 | §4.2.3.2 | (4.5) | résistance au flambement par flexion | confirmée |
| EN 1993-1-2 | §4.2.3.2 | (4.6) | coefficient de réduction χ_fi | confirmée |
| EN 1993-1-2 | §4.2.3.2 | (4.7) | terme φ_θ de la courbe de flambement | confirmée |
| EN 1993-1-2 | §4.2.3.2 | (4.8) | facteur d'imperfection α = 0,65·√(235/f_y) | confirmée |
| EN 1993-1-2 | §4.2.3.2 | (4.9) | élancement réduit à chaud λ̄_θ | confirmée |
| EN 1993-1-2 | §4.2.3.2(4) | — | longueur de flambement d'un poteau continu d'un contreventement | confirmée |
| EN 1993-1-2 | §4.2.3.3 | — | moment résistant de section en classes 1 et 2 | confirmée |
| EN 1993-1-2 | §4.2.3.3(4) | (4.11) | moment résistant au déversement | confirmée |
| EN 1993-1-2 | §4.2.3.3(6) | — | résistance à l'effort tranchant | confirmée |
| EN 1993-1-2 | §4.2.3.3(7) | — | facteurs d'adaptation κ₁ et κ₂ pour température non uniforme | **à recouper** |
| EN 1993-1-2 | §4.2.3.5 | (4.21a) | interaction N + M, flambement par flexion | confirmée |
| EN 1993-1-2 | §4.2.3.5 | (4.21b) | interaction N + M, déversement | confirmée |
| EN 1993-1-2 | §4.2.3.5 | — | facteurs d'interaction k_y, k_z, k_LT et μ_y, μ_z, μ_LT | **à recouper** |
| EN 1993-1-2 | §4.2.4 | (4.22) | température critique de l'acier | confirmée |
| EN 1993-1-2 | §4.2.4 | (4.23) | degré d'utilisation μ₀ à 20 °C | confirmée |
| EN 1993-1-2 | §4.2.5.1 | (4.25) | échauffement d'un élément non protégé | confirmée |
| EN 1993-1-2 | §4.2.5.1 | (4.26a) et (4.26b) | facteur d'ombre k_sh | confirmée |
| EN 1993-1-2 | §4.2.5.1, tab. 4.2 et 4.3 | — | facteur de massiveté A_m/V et périmètres exposés | confirmée |
| EN 1993-1-2 | §4.2.5.2 | (4.27) | échauffement d'un élément protégé | confirmée |
| EN 1993-1-2 | §4.2.5.2 | (4.28) | rapport des capacités thermiques φ | confirmée |
| ENV 1993-1-1 | annexe F | — | moment critique élastique de déversement et facteur C₁ | **à recouper** |
| SIA 260 | situations de projet accidentelles | — | combinaison d'actions, ψ₂ pour toutes les actions variables | **à recouper** |
| SIA 263 | chapitre « Résistance au feu » | — | cadre suisse — renvoi à l'EN 1993-1-2 pour les méthodes détaillées | **à recouper** |
| SZS C5/05 | tables de construction | — | catalogue de profilés laminés | confirmée |

« Confirmée » signifie ici *cohérente avec la structure connue de la norme et
avec les recoupements externes du projet* — pas *lue dans l'exemplaire
officiel*. Les recoupements en question sont dans
[`validation.md`](validation.md).
