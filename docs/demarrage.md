# Démarrer avec le projet

Guide pas à pas pour récupérer le code depuis GitHub et le faire tourner sur
votre machine, avec Visual Studio Code. Écrit pour quelqu'un qui découvre Git
et Python — les commandes sont à recopier telles quelles.

Les commandes sont données pour **Windows / PowerShell**. Les variantes
macOS et Linux sont indiquées à chaque fois qu'elles diffèrent.

---

## 1. Ce qu'il faut installer une fois pour toutes

| Logiciel | Où | Comment vérifier |
|---|---|---|
| **Git** | [git-scm.com](https://git-scm.com/downloads) | `git --version` |
| **Python 3.11 ou plus** | [python.org](https://www.python.org/downloads/) | `python --version` |
| **Visual Studio Code** | [code.visualstudio.com](https://code.visualstudio.com/) | — |

À l'installation de Python sous Windows, **cochez « Add python.exe to PATH »**
sur le premier écran. C'est l'oubli le plus fréquent ; sans cela, la commande
`python` reste introuvable.

Ouvrez ensuite un terminal (touche Windows, tapez `powershell`) et vérifiez :

```powershell
git --version
python --version
```

Vous devez voir quelque chose comme `git version 2.44.0` et
`Python 3.12.2`. Si Python affiche 3.10 ou moins, installez une version plus
récente : le projet utilise `tomllib`, apparu en 3.11.

### Deux extensions VS Code

Ouvrez VS Code, cliquez sur l'icône des extensions dans la barre de gauche
(les quatre carrés), et installez :

- **Python** (éditeur Microsoft) — coloration, exécution, débogage
- **Pylance** — complétion et vérification de types

Elles s'installent souvent ensemble.

---

## 2. Récupérer le code

« Cloner » un dépôt, c'est en télécharger une copie complète, historique
compris, reliée à GitHub.

### Par VS Code, sans ligne de commande

1. Ouvrez VS Code sur l'écran d'accueil (aucun dossier ouvert).
2. **Ctrl+Shift+P** pour ouvrir la palette de commandes.
3. Tapez `Git: Clone` et validez.
4. Collez l'adresse : `https://github.com/damthon/Nommogramme.git`
5. Choisissez le dossier où déposer le projet — par exemple
   `C:\Users\<vous>\Documents\Projets`.
6. VS Code propose d'ouvrir le dossier cloné : acceptez.

Au premier clonage, GitHub demandera de vous authentifier dans le navigateur.
Laissez-vous guider, c'est une fois pour toutes.

### Ou en ligne de commande

```powershell
cd $HOME\Documents\Projets
git clone https://github.com/damthon/Nommogramme.git
cd Nommogramme
code .
```

`code .` ouvre VS Code sur le dossier courant.

---

## 3. Créer un environnement virtuel

Un environnement virtuel est un dossier qui contient une installation de
Python isolée, propre à ce projet. Sans lui, les bibliothèques de tous vos
projets s'empilent au même endroit et finissent par se contredire.

Dans VS Code, ouvrez un terminal : **Ctrl+ù** (ou menu *Terminal → Nouveau
terminal*). Puis :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Sur **macOS / Linux** :

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Le nom `(.venv)` apparaît alors au début de la ligne de commande : c'est le
signe que l'environnement est actif.

> **Si PowerShell refuse d'exécuter le script** — message
> « l'exécution de scripts est désactivée sur ce système » — lancez une fois :
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```
> puis réessayez. C'est un réglage de sécurité Windows, sans danger à ce
> niveau.

### Dire à VS Code d'utiliser cet environnement

**Ctrl+Shift+P** → tapez `Python: Select Interpreter` → choisissez celui dont
le chemin contient `.venv`. VS Code s'en souviendra pour ce projet.

C'est cette étape qui fait fonctionner la complétion, les avertissements et
le bouton d'exécution.

---

## 4. Installer le projet

Toujours dans le terminal, avec `(.venv)` actif :

```powershell
pip install -e ".[dev,trace]"
```

Trois choses dans cette commande :

- `-e` installe en mode « éditable » : vos modifications du code prennent
  effet immédiatement, sans réinstaller ;
- `[dev]` ajoute `pytest` (les tests) et `openpyxl` (lecture du classeur SZS) ;
- `[trace]` ajoute `matplotlib`, nécessaire aux figures.

Comptez une à deux minutes.

---

## 5. Vérifier que tout marche

### Les tests

```powershell
python -m pytest
```

Attendu : **269 tests au vert**, en une dizaine de secondes. Si c'est le cas,
votre installation est bonne — inutile de chercher plus loin.

### Un calcul

```powershell
nommo verifier "HEB 300" --nuance S355 --N 850 --My 120 --L 4 --lfi 2 --duree R60
```

Vous devez voir apparaître μ₀, les deux températures critiques et le verdict.

### Une figure

```powershell
nommo verifier "HEB 300" --N 850 --My 120 --L 8 --lfi 8 --duree R90 --protection flocage_fibreux --dp 30 --tracer nomogramme.png
```

Le fichier `nomogramme.png` apparaît dans le dossier du projet. Cliquez
dessus dans l'explorateur de VS Code, à gauche : il s'affiche dans l'éditeur.

---

## 6. Écrire vos propres calculs

Créez un fichier `mon_calcul.py` à la racine du projet :

```python
from nommogramme import (
    catalogue, CasDeCharge, Exposition, Nuance, Protection, verifier,
)

cas = CasDeCharge(
    N_fi_Ed=850e3,      # N — attention, des newtons, pas des kN
    My_fi_Ed=120e3,     # N·m
    L=4.0,              # m
    l_fi_y=2.0,
    l_fi_z=2.0,
)

r = verifier(
    profil=catalogue["HEB 300"],
    nuance=Nuance.S355,
    cas=cas,
    exposition=Exposition.CONTOUR_4_FACES,
    duree_requise_min=60,
    protection=Protection.depuis_catalogue("flocage_fibreux", d_p=0.025),
)

print(f"μ₀       = {r.mu_0:.3f}")
print(f"θ_cr     = {r.theta_cr:.0f} °C")
print(f"θ_a à R60 = {r.theta_a_a_echeance:.0f} °C")
print(f"Verdict  : {r.verdict.value}")
```

Exécutez-le avec le bouton **▷** en haut à droite de l'éditeur, ou par
`python mon_calcul.py`.

Si les kN vous vont mieux que les newtons :

```python
from nommogramme import kN, kNm

cas = CasDeCharge(N_fi_Ed=kN(850), My_fi_Ed=kNm(120), L=4.0, l_fi_y=2.0, l_fi_z=2.0)
```

---

## 7. Le travail au quotidien

### Avant de commencer, récupérez les nouveautés

```powershell
git pull
```

À faire systématiquement en début de séance. Sinon vous travaillez sur une
version périmée, et les conflits arrivent.

### Pour envoyer vos modifications

Par l'interface de VS Code, onglet **Source Control** (l'icône en forme
d'embranchement dans la barre de gauche) :

1. Vos fichiers modifiés apparaissent sous *Changes*.
2. Cliquez sur **+** à côté de chacun pour le retenir dans le prochain commit.
3. Écrivez un message décrivant le changement.
4. **Ctrl+Entrée** pour valider le commit.
5. Bouton **Sync Changes** pour l'envoyer sur GitHub.

En ligne de commande, l'équivalent :

```powershell
git add .
git commit -m "Ajout de mes cas de référence"
git push
```

### Le piège classique

**Ne modifiez jamais un fichier à la fois sur GitHub web et sur votre
machine sans faire `git pull` entre les deux.** C'est la cause numéro un des
conflits chez les débutants. Une seule règle suffit à les éviter :
`git pull` en arrivant, `git push` en partant.

---

## 8. Ce que vous pouvez faire de plus utile

Le point faible du projet est la validation : aucun résultat n'a encore été
comparé à un calcul de référence externe — voir
[`validation.md`](validation.md).

Si vous avez des cas déjà dimensionnés par un autre moyen — abaque SZS
papier, logiciel du bureau, feuille de calcul — déposez-les dans
`tests/cas_reference.toml`. Le fichier contient un modèle commenté. Chaque
cas ajouté devient un test automatique, sans écrire une ligne de code.

Trois ou quatre cas suffiraient à changer le statut de l'outil.

---

## En cas de blocage

| Message | Cause | Solution |
|---|---|---|
| `python n'est pas reconnu` | Python absent du PATH | Réinstaller en cochant « Add to PATH » |
| `nommo n'est pas reconnu` | environnement non activé | `.\.venv\Scripts\Activate.ps1` |
| `ModuleNotFoundError: nommogramme` | projet non installé | `pip install -e ".[dev,trace]"` |
| `ModuleNotFoundError: matplotlib` | extra manquant | `pip install -e ".[trace]"` |
| l'exécution de scripts est désactivée | politique PowerShell | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| VS Code ne complète pas le code | mauvais interpréteur | `Python: Select Interpreter` → celui du `.venv` |
