"""
=============================================================================
 ETL - ETAPE 2 : chargement de DIM_NIVEAU
=============================================================================

OBJECTIF
    Construire la liste des niveaux d'etude possibles : S1/S2 (annee 1),
    S3/S4 (annee 2), S5/S6 (annee 3) pour la Licence, et M1, M2 pour le
    Master. Cette dimension ne depend d'aucun fichier source directement :
    elle se deduit du referentiel des filieres (colonne "cycle") croise
    avec les annees d'etude presentes dans les modules.

    Aucune anomalie a traiter ici.

COMMENT L'EXECUTER
    1. Verifie que MySQL tourne dans XAMPP (vert, port 3306)
    2. Verifie les parametres de connexion MySQL ci-dessous
    3. python 03_etl_dim_niveau.py
=============================================================================
"""

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

# -----------------------------------------------------------------------
# CONFIGURATION -- ADAPTE CETTE VALEUR SI BESOIN
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
filieres = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx", sheet_name="Filieres")
modules = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx", sheet_name="Modules")
print(f"  {len(filieres)} filieres, {len(modules)} modules lus")


# =========================================================================
# 2. TRANSFORMATION
# =========================================================================
print("\n[TRANSFORMATION]")

# On recupere les couples (annee_etude, cycle) reellement utilises,
# en passant par les modules (qui portent l'annee_etude) joints aux
# filieres (qui portent le cycle).
combinaisons = (
    modules[["code_filiere", "annee_etude"]]
    .drop_duplicates()
    .merge(filieres[["code_filiere", "cycle"]], on="code_filiere")
    [["annee_etude", "cycle"]]
    .drop_duplicates()
    .sort_values(["cycle", "annee_etude"])
    .reset_index(drop=True)
)

# On construit le libelle du niveau : semestres pour la Licence, "M1"/"M2"
# pour le Master -- ce qui correspond a l'usage reel dans les etablissements
def construire_niveau(row):
    if row["cycle"] == "Licence":
        s1 = row["annee_etude"] * 2 - 1
        s2 = row["annee_etude"] * 2
        return f"S{s1}/S{s2}"
    else:
        return f"M{row['annee_etude']}"

combinaisons["niveau"] = combinaisons.apply(construire_niveau, axis=1)

df_final = combinaisons[["niveau", "annee_etude", "cycle"]]

print(f"  {len(df_final)} niveaux distincts construits :")
print(df_final.to_string(index=False))


# =========================================================================
# 3. CHARGEMENT
# =========================================================================
print("\n[CHARGEMENT]")
with moteur.connect() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    conn.execute(text("TRUNCATE TABLE DIM_NIVEAU;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    conn.commit()
    print("  Table DIM_NIVEAU videe")

df_final.to_sql("DIM_NIVEAU", con=moteur, if_exists="append", index=False)
print(f"  {len(df_final)} lignes inserees dans DIM_NIVEAU")


# =========================================================================
# 4. VERIFICATION
# =========================================================================
print("\n[VERIFICATION]")
verif = pd.read_sql("SELECT * FROM DIM_NIVEAU ORDER BY cle_niveau;", con=moteur)
print(verif.to_string(index=False))
print(f"\nOK -- DIM_NIVEAU contient maintenant {len(verif)} lignes.")
