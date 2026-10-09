"""
=============================================================================
 ETL - ETAPE 3 : chargement de DIM_MODULE
=============================================================================

OBJECTIF
    Charger la liste des 120 modules d'enseignement depuis l'onglet
    "Modules" de referentiel.xlsx. Aucune anomalie a traiter : le fichier
    est deja propre (0 doublon, 0 valeur manquante), et ses colonnes
    correspondent deja exactement a celles de la table DIM_MODULE.

    C'est la derniere des 3 dimensions "faciles". A partir du script
    suivant (DIM_ETUDIANT), on attaque le vrai nettoyage.

COMMENT L'EXECUTER
    1. Verifie que MySQL tourne dans XAMPP (vert, port 3306)
    2. python 04_etl_dim_module.py
=============================================================================
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# -----------------------------------------------------------------------
# Dossier des donnees : calcule a partir de l'emplacement du script (fonctionne sur tout ordinateur)
DOSSIER_SOURCES = Path(__file__).resolve().parent.parent / "data"

MYSQL_USER = "root"
MYSQL_PASSWORD = ""
MYSQL_HOST = "localhost"
MYSQL_PORT = "3306"
MYSQL_DB = "dw_affaires_estudiantines"
# -----------------------------------------------------------------------

url_connexion = f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
moteur = create_engine(url_connexion)

print("Test de connexion a MySQL...")
with moteur.connect() as conn:
    print("  Connecte a la base :", conn.execute(text("SELECT DATABASE();")).scalar())


# =========================================================================
# 1. EXTRACTION
# =========================================================================
print("\n[EXTRACTION]")
modules = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx", sheet_name="Modules")
print(f"  {len(modules)} modules lus")


# =========================================================================
# 2. TRANSFORMATION
# =========================================================================
print("\n[TRANSFORMATION]")

# Controle de qualite -- on verifie qu'il n'y a vraiment rien a nettoyer
nb_doublons = modules.duplicated(subset=["code_module"]).sum()
nb_manquants = modules.isna().sum().sum()
print(f"  Doublons sur code_module : {nb_doublons}")
print(f"  Valeurs manquantes       : {nb_manquants}")

if nb_doublons > 0:
    modules = modules.drop_duplicates(subset=["code_module"], keep="first")
    print(f"  -> {nb_doublons} doublon(s) supprime(s)")

# Les colonnes sont deja dans le bon ordre et le bon nommage
df_final = modules[["code_module", "libelle_module", "code_filiere",
                     "annee_etude", "semestre", "coefficient", "volume_horaire"]]

print(f"  Table finale prete : {len(df_final)} lignes")


# =========================================================================
# 3. CHARGEMENT
# =========================================================================
print("\n[CHARGEMENT]")
with moteur.connect() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    conn.execute(text("TRUNCATE TABLE DIM_MODULE;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    conn.commit()
    print("  Table DIM_MODULE videe")

df_final.to_sql("DIM_MODULE", con=moteur, if_exists="append", index=False)
print(f"  {len(df_final)} lignes inserees dans DIM_MODULE")


# =========================================================================
# 4. VERIFICATION
# =========================================================================
print("\n[VERIFICATION]")
verif = pd.read_sql("SELECT COUNT(*) AS nb_lignes, "
                     "COUNT(DISTINCT code_module) AS codes_uniques "
                     "FROM DIM_MODULE;", con=moteur)
print(verif.to_string(index=False))

apercu = pd.read_sql("SELECT * FROM DIM_MODULE ORDER BY cle_module LIMIT 8;", con=moteur)
print("\nAper\u00e7u des 8 premiers modules :")
print(apercu.to_string(index=False))

print(f"\nOK -- DIM_MODULE contient maintenant {verif['nb_lignes'][0]} lignes.")
