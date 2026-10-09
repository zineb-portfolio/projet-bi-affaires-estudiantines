"""
=============================================================================
 ETL - ETAPE 7 (DERNIERE) : chargement de FAIT_MOBILITE
=============================================================================

OBJECTIF
    Charger les sejours de mobilite estudiantine. Aucune anomalie a
    corriger ici (0 doublon, 0 valeur manquante a l'exploration) --
    seules les jointures vers DIM_ETUDIANT et DIM_TEMPS sont necessaires.

    C'est la DERNIERE brique de l'ETL. Une fois ce script execute,
    les 9 tables de l'entrepot seront entierement remplies.

COMMENT L'EXECUTER
    1. Verifie que MySQL tourne (XAMPP, vert, port 3306)
    2. Verifie que DIM_ETUDIANT et DIM_TEMPS sont deja remplies
    3. python 08_etl_fait_mobilite.py
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
mobilite = pd.read_csv(f"{DOSSIER_SOURCES}/mobilite_estudiantine.csv")
nb_lignes_brutes = len(mobilite)
print(f"  {nb_lignes_brutes} lignes lues depuis mobilite_estudiantine.csv")


# =========================================================================
# 2. TRANSFORMATION -- controle de qualite (aucune correction attendue)
# =========================================================================
print("\n[TRANSFORMATION]")
df = mobilite.copy()

nb_doublons = df.duplicated().sum()
nb_manquants = df.isna().sum().sum()
print(f"  Doublons stricts    : {nb_doublons}")
print(f"  Valeurs manquantes  : {nb_manquants}")

if nb_doublons > 0:
    df = df.drop_duplicates()
    print(f"  -> {nb_doublons} doublon(s) supprime(s) par securite")
else:
    print("  Aucune correction necessaire (source deja propre)")


# =========================================================================
# 3. JOINTURES
# =========================================================================
print("\n[JOINTURES]")

dim_etudiant = pd.read_sql("SELECT cle_etudiant, cne FROM DIM_ETUDIANT;", con=moteur)
dim_temps    = pd.read_sql("SELECT cle_temps, annee_universitaire FROM DIM_TEMPS;", con=moteur)

df = df.merge(dim_etudiant, left_on="CNE", right_on="cne", how="left")
print(f"  Etudiants non retrouves dans DIM_ETUDIANT : {df['cle_etudiant'].isna().sum()}")

df = df.merge(dim_temps, on="annee_universitaire", how="left")
print(f"  Annees non retrouvees dans DIM_TEMPS       : {df['cle_temps'].isna().sum()}")

lignes_incompletes = df[df[["cle_etudiant", "cle_temps"]].isna().any(axis=1)]
if len(lignes_incompletes) > 0:
    print(f"\n  ATTENTION : {len(lignes_incompletes)} ligne(s) rejetee(s)")
    df = df.dropna(subset=["cle_etudiant", "cle_temps"])
else:
    print("\n  Toutes les lignes ont ete correctement rattachees a leurs dimensions")


# =========================================================================
# 4. SELECTION FINALE
# =========================================================================
df_final = df[[
    "cle_etudiant", "cle_temps", "type_mobilite", "pays_destination",
    "programme", "duree_mois", "statut",
]].copy()
df_final["cle_etudiant"] = df_final["cle_etudiant"].astype(int)
df_final["cle_temps"]    = df_final["cle_temps"].astype(int)

print(f"\n  Table finale prete : {len(df_final)} lignes")


# =========================================================================
# 5. CHARGEMENT
# =========================================================================
print("\n[CHARGEMENT]")
with moteur.connect() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    conn.execute(text("TRUNCATE TABLE FAIT_MOBILITE;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    conn.commit()
    print("  Table FAIT_MOBILITE videe")

df_final.to_sql("FAIT_MOBILITE", con=moteur, if_exists="append", index=False)
print(f"  {len(df_final)} lignes inserees dans FAIT_MOBILITE")


# =========================================================================
# 6. VERIFICATION
# =========================================================================
print("\n[VERIFICATION]")

verif = pd.read_sql("""
    SELECT type_mobilite, statut, COUNT(*) AS nb
    FROM FAIT_MOBILITE
    GROUP BY type_mobilite, statut
    ORDER BY type_mobilite, statut;
""", con=moteur)
print("  Repartition par type et statut :")
print(verif.to_string(index=False))

nb_total = pd.read_sql("SELECT COUNT(*) AS n FROM FAIT_MOBILITE;", con=moteur)["n"][0]
print(f"\nOK -- FAIT_MOBILITE contient maintenant {nb_total} lignes.")


# =========================================================================
# 7. BILAN GLOBAL DE L'ENTREPOT -- toutes les tables en un coup d'oeil
# =========================================================================
print("\n" + "=" * 60)
print("  BILAN FINAL DE L'ENTREPOT DE DONNEES")
print("=" * 60)

bilan = pd.read_sql("""
    SELECT 'DIM_ETUDIANT' AS table_name, COUNT(*) AS nb_lignes FROM DIM_ETUDIANT
    UNION ALL SELECT 'DIM_TEMPS',            COUNT(*) FROM DIM_TEMPS
    UNION ALL SELECT 'DIM_FILIERE',          COUNT(*) FROM DIM_FILIERE
    UNION ALL SELECT 'DIM_NIVEAU',           COUNT(*) FROM DIM_NIVEAU
    UNION ALL SELECT 'DIM_STATUT',           COUNT(*) FROM DIM_STATUT
    UNION ALL SELECT 'DIM_MODULE',           COUNT(*) FROM DIM_MODULE
    UNION ALL SELECT 'FAIT_INSCRIPTION',     COUNT(*) FROM FAIT_INSCRIPTION
    UNION ALL SELECT 'FAIT_RESULTAT_MODULE', COUNT(*) FROM FAIT_RESULTAT_MODULE
    UNION ALL SELECT 'FAIT_MOBILITE',        COUNT(*) FROM FAIT_MOBILITE;
""", con=moteur)
print(bilan.to_string(index=False))
print("\nL'ETL EST TERMINE -- les 9 tables de l'entrepot sont remplies.")
print("Prochaine etape : la connexion de Power BI a cette base de donnees.")
