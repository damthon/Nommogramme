# Normes en Markdown

Ce dossier stocke les normes de référence de l'outil — SIA 263, EN 1993-1-2,
EN 1991-1-2, … — transcrites des PDF originaux en Markdown. Il sert à recouper
les clauses citées par l'outil (voir [`docs/references.md`](../docs/references.md))
sans rouvrir le PDF.

## Règle première : copie exacte, jamais de simplification

Un fichier `.md` de norme est la **reproduction fidèle** du PDF original. Il ne
résume pas, ne reformule pas, ne réordonne pas et n'omet rien.

- **Tout le texte**, mot pour mot : avant-propos, domaine d'application,
  clauses, notes, remarques, notes de bas de page, annexes (normatives et
  informatives), bibliographie.
- **Numérotation d'origine** des paragraphes, alinéas `(1)`, `(2)`…, tableaux,
  figures et équations. Les titres Markdown suivent la hiérarchie du PDF :
  `#` chapitre, `##` paragraphe `4.2`, `###` sous-paragraphe `4.2.3`, etc.
- **Équations** en LaTeX, avec leur numéro d'origine :

  ```markdown
  $$ \theta_{a,cr} = 39{,}19 \ln\left[\frac{1}{0{,}9674\,\mu_0^{3{,}833}} - 1\right] + 482 \qquad (4.22) $$
  ```

  Symboles, indices, unités et séparateur décimal (virgule) restent ceux du PDF.
- **Tableaux** en tableaux Markdown. Si le tableau a des cellules fusionnées
  qu'un tableau Markdown ne sait pas rendre, utiliser un `<table>` HTML avec
  `rowspan` / `colspan` plutôt que de le simplifier.
- **Notes et remarques** en citation, avec leur libellé d'origine :
  `> NOTE 1 ...`.
- **Pagination** : un repère au début de chaque page du PDF, pour retrouver la
  source :

  ```markdown
  <!-- page 27 -->
  ```

- Une coquille du PDF se **recopie telle quelle** ; on peut la signaler par un
  commentaire `<!-- sic : ... -->`, jamais la corriger dans le texte.

## Images : toutes extraites, rangées dans un zip

Chaque image du PDF — figures, diagrammes, schémas, courbes, logos, équations
scannées, tableaux scannés — est extraite et rangée dans **un fichier zip** à
côté du Markdown. Aucune image n'est laissée de côté, et aucune ne l'est sans
renvoi dans le `.md`.

### Organisation

```
normes/
├── pdf/                        # PDF originaux, non versionnés
│   └── EN-1993-1-2.pdf
└── EN-1993-1-2/
    ├── EN-1993-1-2.md          # texte intégral
    └── EN-1993-1-2-images.zip  # toutes les images, sous images/
```

- Un dossier par norme, nommé par sa désignation (espaces → `-`) :
  `SIA-263`, `EN-1993-1-2`, `EN-1991-1-2`…
- Le zip contient un unique dossier `images/`. Une fois décompressé à côté du
  `.md`, les liens s'affichent directement.
- Les PDF originaux se déposent dans `normes/pdf/`, qui n'est **pas versionné**
  (voir [`.gitignore`](../.gitignore)) : seuls le `.md` et le zip entrent dans git.
- Le dossier `images/` décompressé n'est **pas versionné** (voir
  [`.gitignore`](../.gitignore)) : le zip fait foi.

### Nommage des images

| Cas | Nom du fichier |
|---|---|
| Figure numérotée | `figure-4.1.png` (sous-figures : `figure-4.1a.png`, `figure-4.1b.png`) |
| Image dans un tableau | `tableau-3.1.png` |
| Équation scannée | `equation-4.22.png` |
| Toute autre image | `page-027-1.png` (page du PDF sur 3 chiffres, rang dans la page) |

### Renvois dans le Markdown

Chaque image est appelée **à l'endroit exact** où elle se trouve dans le PDF,
avec sa légende d'origine en texte alternatif, puis la légende recopiée
en dessous :

```markdown
![Figure 4.1 — Facteurs de réduction de la relation contrainte-déformation](images/figure-4.1.png)

*Figure 4.1 — Facteurs de réduction de la relation contrainte-déformation de l'acier au carbone à températures élevées*
```

- Chemin **relatif** au `.md` : toujours `images/<nom>`.
- Quand le texte renvoie à une figure (« voir Figure 4.1 »), on garde le texte
  tel quel ; on peut en faire un lien vers l'ancre de la figure, sans changer
  les mots.
- Les données qu'une figure porte (valeurs lues sur une courbe, etc.) ne
  remplacent jamais l'image : l'image est extraite, le texte du PDF est
  recopié, rien n'est réinterprété.

## Procédure de transcription

Outils : `pdfimages`, `pdftoppm` (paquet `poppler-utils`), `zip`.

1. **Extraire les images bitmap** avec leur numéro de page :

   ```bash
   mkdir -p normes/EN-1993-1-2/images
   pdfimages -png -p normes/pdf/EN-1993-1-2.pdf normes/EN-1993-1-2/images/page
   ```

   Les fichiers sortent en `page-027-003.png` (page 27, 3ᵉ image du PDF). On les
   renomme ensuite selon le tableau ci-dessus. On supprime les seuls doublons
   techniques (masques de transparence, même image répétée sur chaque page) —
   pas les figures.

2. **Rendre les figures vectorielles**, que `pdfimages` ne voit pas (courbes,
   schémas dessinés en traits). On rend la zone de la page à 300 dpi :

   ```bash
   # page 27, zone x y largeur hauteur en pixels à 300 dpi
   pdftoppm -png -r 300 -f 27 -l 27 -x 250 -y 900 -W 2000 -H 1400 -singlefile \
     normes/pdf/EN-1993-1-2.pdf normes/EN-1993-1-2/images/figure-4.1
   ```

3. **Transcrire le texte** page par page en suivant les règles ci-dessus, en
   plaçant les renvois `![...](images/...)` au fil du texte.

4. **Créer le zip** (sans entrées de dossier, pour la vérification) :

   ```bash
   cd normes/EN-1993-1-2 && zip -rD EN-1993-1-2-images.zip images/
   ```

5. **Vérifier** que chaque image du zip est appelée dans le `.md` et que chaque
   renvoi pointe vers une image du zip — la commande ne doit rien afficher :

   ```bash
   cd normes/EN-1993-1-2 && diff \
     <(grep -o '](images/[^)]*' EN-1993-1-2.md | cut -c3- | sort -u) \
     <(unzip -Z1 EN-1993-1-2-images.zip | sort)
   ```

## Relecture avant commit

- [ ] Toutes les pages du PDF ont leur repère `<!-- page N -->`, dans l'ordre.
- [ ] Aucun paragraphe, alinéa, note, tableau ou annexe manquant (comparer la
      table des matières du PDF aux titres du `.md`).
- [ ] Équations et tableaux recopiés avec leur numéro d'origine.
- [ ] Le nombre de figures du PDF égale le nombre de renvois `![Figure`.
- [ ] La vérification de l'étape 5 ne signale aucun écart.

## Droits d'auteur

Les normes SIA et EN sont protégées. Une transcription intégrale reste soumise
aux droits de l'éditeur : le dépôt doit rester **privé**, et réservé aux
détenteurs d'une licence de la norme.
