# Terroirs

Une application Django pour explorer le vin français : un graphe parcourable des régions, appellations,
cépages et arômes, un blind test façon jeu de déduction, et « Le Nez », qui propose les cinq vins les plus
probables à partir de descripteurs olfactifs.

## Démarrage rapide

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # DJANGO_DEBUG=true pour le développement
python manage.py migrate
python manage.py load_seed      # charge le jeu de données France
python manage.py createsuperuser
python manage.py runserver
```

Avec Docker et PostgreSQL :

```bash
docker compose up --build       # http://localhost:8000
```

## Fonctionnalités

| Onglet | Ce qu'il fait |
|---|---|
| **Graphe** (`/graphe/`) | Graphe Cytoscape des entités. Vues prédéfinies, choix des types de nœuds, filtres (couleur, région, prix, intensité des arômes, part des cépages), quatre dispositions, recherche, centrage sur le voisinage (double-clic), **plus court chemin entre deux entités**, fiche latérale (HTMX), export PNG. L'URL garde l'état : une vue se partage. |
| **Blind test** (`/blind-test/`) | Un profil type mystère : robe, structure en bouche, premiers arômes. Le joueur saisit librement régions, appellations ou cépages (autocomplétion, accents et synonymes tolérés) pour reconstituer l'étiquette. Retour par essai : trouvé, proche (bonne région, cépage minoritaire), raté avec distance et direction. Chaque essai manqué dévoile un indice (arômes, garde, prix, accords, commentaire masqué, initiale, forme du nom). Défi du jour commun à tous et parties libres. |
| **Le Nez** (`/le-nez/`) | Saisie de descripteurs (ou familles) en puces, ou par la roue des arômes. Top 5 des profils avec probabilités, arômes retrouvés, proches ou absents, et suggestions de descripteurs pour départager. |
| **Catalogue** (`/catalogue/`) | Fiches des régions, appellations, profils types, cépages et arômes. |
| **Comptes** (`/compte/`) | Inscription, connexion, historique, réussite par région, classement du jour et général. Les parties jouées sans compte sont rattachées à la connexion. |

## Architecture

```
config/                 réglages (variables d'environnement), urls
apps/catalog/           modèles du vin, jeu de données, imports, recherche floue
  data/fr/*.yaml        régions, cépages, arômes, appellations et profils types
  management/commands/  load_seed, import_inao, import_wikidata
apps/explorer/          construction du graphe, filtres, plus court chemin, API JSON
apps/blindtest/         moteur de jeu (engine.py), parties et essais
apps/nose/              classifieur bayésien naïf avec repli par famille
apps/accounts/          inscription, profil, classement
templates/, static/     HTML, CSS, JS ; Cytoscape, HTMX et polices servis en local
```

**Modèle de données.** `Country → Region (hiérarchique) → Appellation → WineProfile`. Un profil type
porte une couleur, un style, une structure (corps, acidité, tanins, sucrosité sur 5), un encépagement
pondéré (`ProfileGrape.share`) et des arômes pondérés (`ProfileAroma.intensity` de 1 à 3). La
classification est générique (AOC, IGP, DOC, DOCG, AVA) pour accueillir d'autres pays.

**Le Nez.** Pour chaque profil `p` et descripteur `a` :
`P(a|p) = (w_pa + α·w_pf/n_f + β) / (T_p(1+α) + βN)`, où `w_pf` est le poids du profil dans la famille
de `a`. La famille donne une vraisemblance partielle (la framboise est proche de la fraise). Les
log-vraisemblances sont tempérées puis normalisées en probabilités (`apps/nose/predictor.py`).

**Performance.** Le graphe complet, l'index de recherche et le modèle du Nez sont construits une fois par
version des données et gardés en mémoire ; l'API graphe est mise en cache 5 minutes. `load_seed` vide
ces caches.

## Données

Le jeu fourni compte 98 profils types, 83 appellations, 54 cépages et 99 descripteurs répartis en
14 familles. Il a été rédigé à la main et vérifié au chargement : toute référence inconnue ou tout
encépagement qui ne totalise pas 100 % fait échouer `load_seed`. Les prix et gardes sont indicatifs ;
les coordonnées correspondent à une commune centrale.

Pour enrichir avec des sources ouvertes :

```bash
# INAO, « Aires et produits AOC/AOP et IGP » (data.gouv.fr, Licence Ouverte 2.0)
python manage.py import_inao chemin/vers/aires-produits.csv --dry-run
python manage.py import_inao chemin/vers/aires-produits.csv --create

# Wikidata (CC0) : identifiants et coordonnées
python manage.py import_wikidata --dry-run
```

`import_inao` reconnaît plusieurs variantes de noms de colonnes : vérifiez la ligne « Colonnes
utilisées » sur le fichier réel. Les deux imports n'ont pas encore été testés sur les fichiers réels.

Pour ajouter une appellation, complétez un fichier `apps/catalog/data/fr/appellations_*.yaml` puis
relancez `python manage.py load_seed --check` et `load_seed`.

## Qualité

```bash
python manage.py test           # 39 tests : données, graphe, jeu, Nez, comptes
ruff check .
```

Les tests passent sous SQLite et PostgreSQL 16.

## Pistes

- Brancher les imports INAO et Wikidata sur les fichiers réels, puis rattacher les nouvelles appellations.
- Ouvrir le monde : un dossier `data/<pays>/` par pays, `load_seed --country it`.
- Traduction anglaise : `LANGUAGES` et `LocaleMiddleware` sont en place, les chaînes restent à extraire avec `gettext`.
- Niveaux de difficulté au blind test (région donnée d'emblée, moins d'essais).
