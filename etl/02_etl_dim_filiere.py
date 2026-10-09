"""
=============================================================================
 ETL - ETAPE 1 : chargement de DIM_FILIERE
=============================================================================

OBJECTIF
    Lire l'onglet "Filieres" et l'onglet "Departements" de referentiel.xlsx,
    les combiner, et les inserer dans la table DIM_FILIERE de MySQL.

    C'est la table la plus simple : aucune anomalie detectee a l'exploration.
    Elle sert de premier test du pipeline avant d'attaquer les tables sales.

PREREQUIS
    pip install sqlalchemy pymysql pandas openpyxl

COMMENT L'EXECUTER
    1. Verifie que MySQL tourne dans XAMPP (vert, port 3306)
    2. Verifie les parametres de connexion MySQL ci-dessous
    3. python 02_etl_dim_filiere.py
=============================================================================
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# -----------------------------------------------------------------------
# CONFIGURATION -- ADAPTE CES VALEURS
# -----------------------------------------------------------------------
# Dossier des donnees : calcule a partir de l'emplacement du script (fonctionne sur tout ordinateur)
DOSSIER_SOURCES = Path(__file__).resolve().parent.parent / "data"

# Parametres de connexion a MySQL (XAMPP par defaut : utilisateur root, sans mot de passe)
MYSQL_USER = "root"
MYSQL_PASSWORD = ""          # vide par defaut sous XAMPP
MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "dw_affaires_estudiantines"

# -----------------------------------------------------------------------
# CONNEXION A MYSQL
# -----------------------------------------------------------------------
url_connexion = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
moteur = create_engine(url_connexion)

print("Test de connexion a MySQL...")
with moteur.connect() as conn:
    resultat = conn.execute(text("SELECT DATABASE();"))
    print("  Connecte a la base :", resultat.scalar())


# =========================================================================
# 1. EXTRACTION -- lire les deux onglets du fichier referentiel
# =========================================================================
print("\n[EXTRACTION]")
filieres = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx", sheet_name="Filieres")
departements = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx", sheet_name="Departements")
print(f"  {len(filieres)} filieres lues")
print(f"  {len(departements)} departements lus")


# =========================================================================
# 2. TRANSFORMATION -- combiner filieres + departements
# =========================================================================
print("\n[TRANSFORMATION]")

# On rapproche chaque filiere de son departement grace au code commun.
# C'est une jointure : on "colle" le libelle du departement sur chaque
# ligne de filiere qui partage le meme code_departement.
df = filieres.merge(departements, on="code_departement", how="left")

# On verifie qu'aucune filiere n'est restee sans departement associe
manquants = df["libelle_departement"].isna().sum()
if manquants > 0:
    print(f"  ATTENTION : {manquants} filiere(s) sans departement trouve")
else:
    print("  Toutes les filieres ont ete rattachees a un departement")

# On renomme et on ordonne les colonnes pour correspondre exactement
# aux colonnes de la table DIM_FILIERE cote MySQL
df_final = df.rename(columns={
    "code_filiere": "code_filiere",
    "libelle_filiere": "libelle_filiere",
    "code_departement": "code_departement",
    "libelle_departement": "libelle_departement",
    "cycle": "cycle",
    "duree_annees": "duree_annees",
    "capacite_annuelle": "capacite_annuelle",
})[["code_filiere", "libelle_filiere", "code_departement",
    "libelle_departement", "cycle", "duree_annees", "capacite_annuelle"]]

print(f"  Table finale prete : {len(df_final)} lignes, {df_final.shape[1]} colonnes")
print(df_final.to_string(index=False))


# =========================================================================
# 3. CHARGEMENT -- inserer dans MySQL
# =========================================================================
print("\n[CHARGEMENT]")

with moteur.connect() as conn:
    # On vide la table avant de la remplir, pour pouvoir relancer
    # le script plusieurs fois sans creer de doublons
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    conn.execute(text("TRUNCATE TABLE DIM_FILIERE;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    conn.commit()
    print("  Table DIM_FILIERE videe")

df_final.to_sql("DIM_FILIERE", con=moteur, if_exists="append", index=False)
print(f"  {len(df_final)} lignes inserees dans DIM_FILIERE")


# =========================================================================
# 4. VERIFICATION
# =========================================================================
print("\n[VERIFICATION]")
verif = pd.read_sql("SELECT * FROM DIM_FILIERE ORDER BY cle_filiere;", con=moteur)
print(verif.to_string(index=False))

print(f"\nOK -- DIM_FILIERE contient maintenant {len(verif)} lignes.")
