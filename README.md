# Système d'aide à la décision — Service des affaires estudiantines

Projet de Business Intelligence : de cinq sources de données hétérogènes
(Excel, CSV) à un tableau de bord Power BI interactif, en passant par un
pipeline ETL Python et un entrepôt de données MySQL en schéma en étoile.

> **Les données de ce dépôt sont simulées.** Elles ne correspondent à aucun
> établissement réel : l'établissement étudié est fictif. Les indicateurs
> présentés ne sont pas des statistiques réelles.

## Objectif

Le service des affaires estudiantines d'une université gère ses données dans
cinq applications qui ne communiquent pas entre elles. Le projet consolide ces
sources, mesure et corrige leurs anomalies de qualité, puis produit des
indicateurs fiables pour piloter la scolarité.

## Architecture

```
Fichiers sources (Excel, CSV)
        ↓
Pipeline ETL Python (pandas, SQLAlchemy) : 7 scripts
        ↓
Entrepôt MySQL en schéma en étoile : 9 tables
        ↓
Tableau de bord Power BI : 3 pages, 8 visuels
```

## Les données

| Source | Format | Lignes |
| --- | --- | --- |
| `scolarite_etudiants` | Excel | 2 848 |
| `inscriptions` | CSV (séparateur `;`) | 6 183 |
| `notes_examens` | CSV | 56 954 |
| `referentiel` | Excel, 3 onglets | 133 |
| `mobilite_estudiantine` | CSV | 108 |

Une analyse exploratoire a mesuré 9 catégories d'anomalies (dates en trois
formats, sexe écrit de six façons, 87 variantes pour 18 villes, notes hors de
[0 ; 20], doublons…). Le détail est dans `docs/rapport_qualite.csv`.

## Le modèle en étoile

9 tables : 6 dimensions et 3 tables de faits.

- **Dimensions** : `DIM_ETUDIANT`, `DIM_TEMPS`, `DIM_FILIERE`, `DIM_NIVEAU`,
  `DIM_STATUT`, `DIM_MODULE`
- **Faits** : `FAIT_INSCRIPTION` (un étudiant, une filière, une année),
  `FAIT_RESULTAT_MODULE` (un étudiant, un module, une session),
  `FAIT_MOBILITE` (une mobilité réalisée)

`DIM_ETUDIANT` et `DIM_TEMPS` sont des dimensions conformes, partagées par les
trois tables de faits. Les mesures `est_admis`, `est_ajourne` et `est_abandon`
valent 0 ou 1 : leur moyenne donne directement un taux.

## Contenu du dépôt

```
data/          les 5 fichiers sources simulés
exploration/   analyse exploratoire et mesure des anomalies
sql/           script de création des 9 tables
etl/           les 7 scripts du pipeline
powerbi/       le tableau de bord (fichier .pbix)
docs/          graphiques d'exploration et tableau des anomalies
```

## Lancer le projet

Prérequis : Python 3, MySQL (par exemple via XAMPP) et phpMyAdmin.

1. Installer les bibliothèques :
   `pip install -r requirements.txt`
2. Démarrer MySQL, puis créer une base vide nommée
   `dw_affaires_estudiantines` (par exemple dans phpMyAdmin).
3. Exécuter le script `sql/01_creation_schema.sql` dans cette base.
4. Lancer les scripts de `etl/` dans l'ordre numérique, de `02` à `08` :
   les dimensions d'abord, puis les tables de faits, qui ont besoin des
   dimensions pour résoudre leurs clés.

Les chemins des données sont calculés à partir de l'emplacement des scripts :
rien à adapter. La connexion MySQL utilise les valeurs par défaut de XAMPP
(utilisateur `root`, sans mot de passe, port 3306), à modifier en haut de
chaque script si ta configuration est différente. Ne publie jamais un vrai mot
de passe dans ce dépôt.

Pour refaire l'analyse exploratoire :
`python exploration/01_exploration.py`

## Connexion de Power BI

Le connecteur MySQL natif de Power BI n'a pas fonctionné dans cet
environnement. L'import passe par le connecteur « Script Python » de Power BI,
avec les mêmes bibliothèques que l'ETL :

```python
import pandas as pd
from sqlalchemy import create_engine

moteur = create_engine("mysql+pymysql://root:@localhost:3306/dw_affaires_estudiantines")
fait_inscription = pd.read_sql("SELECT * FROM FAIT_INSCRIPTION", con=moteur)
# ... une requête par table de l'entrepôt
```

La colonne `note` était importée comme du texte à cause du séparateur décimal
régional. Elle est corrigée dans Power BI par une colonne calculée en DAX
(`Est_Valide_Num`).

## Résultats (sur données simulées)

- Taux de réussite global de 48,8 %, avec un écart marqué entre les masters et
  les licences
- Taux d'abandon en baisse à partir de 2023-2024
- Taux d'abandon plus faible chez les boursiers, une corrélation observée et non
  une causalité démontrée
- Difficulté pédagogique concentrée sur les modules de première année

## Limites

- Données simulées
- MySQL est un moteur transactionnel, adapté à cette volumétrie mais pas à
  l'analytique à très grande échelle
- Indicateurs descriptifs uniquement, sans volet prédictif

## Auteur

Zineb Lagrat
