"""
=============================================================================
 ETL - ETAPE 6 : chargement de FAIT_RESULTAT_MODULE
=============================================================================

OBJECTIF
    Charger les 57 000 notes d'examen, en corrigeant les 2 dernieres
    anomalies liees aux notes :

        A6 - certaines notes utilisent la virgule comme separateur decimal
             (ex: "13,93" au lieu de 13.93) -- Excel/CSV francophones
        A7 - certaines notes sont hors de l'intervalle possible [0 ; 20]
             (ex: -1, 25, 100, 200) -- erreurs de saisie

    On en profite aussi pour traiter A9 (doublons), deja rencontree.

    Grain de cette table : un etudiant, un module, une session.
    C'est pour cela qu'elle est bien plus volumineuse que FAIT_INSCRIPTION.

COMMENT L'EXECUTER
    1. Verifie que MySQL tourne (XAMPP, vert, port 3306)
    2. Verifie que DIM_ETUDIANT, DIM_TEMPS, DIM_MODULE sont deja remplies
    3. python 07_etl_fait_resultat_module.py
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
notes = pd.read_csv(f"{DOSSIER_SOURCES}/notes_examens.csv")
nb_lignes_brutes = len(notes)
print(f"  {nb_lignes_brutes} lignes lues depuis notes_examens.csv")


# =========================================================================
# 2. TRANSFORMATION
# =========================================================================
print("\n[TRANSFORMATION]")
df = notes.copy()

# -------------------------------------------------------------------
# REGLE A9 -- doublons stricts
# -------------------------------------------------------------------
avant = len(df)
df = df.drop_duplicates()
print(f"\n  [A9] Doublons stricts : {avant} -> {len(df)} lignes "
      f"({avant - len(df)} supprime(s))")

# -------------------------------------------------------------------
# REGLE A6 -- separateur decimal virgule
# La colonne "note" est lue comme du texte (dtype object) a cause du
# melange de formats. On remplace la virgule par un point, PUIS on
# convertit en nombre. Les valeurs deja au format point restent inchangees.
# -------------------------------------------------------------------
avec_virgule = df["note"].astype(str).str.contains(",", na=False).sum()
df["note"] = pd.to_numeric(
    df["note"].astype(str).str.replace(",", ".", regex=False),
    errors="coerce"      # toute valeur non convertible devient NaN plutot que de planter
)
print(f"\n  [A6] Separateur decimal virgule")
print(f"       {avec_virgule} valeur(s) reecrite(s) avec un point")

# -------------------------------------------------------------------
# REGLE A7 -- notes hors de l'intervalle [0 ; 20]
# On ne peut pas deviner la vraie valeur d'une note aberrante (ex: 200).
# La bonne pratique est de la REJETER (la mettre a vide) plutot que de
# la "deviner" ou de la garder telle quelle, ce qui fausserait toutes
# les moyennes calculees ensuite.
# -------------------------------------------------------------------
hors_bornes = ((df["note"] < 0) | (df["note"] > 20)).sum()
valeurs_rejetees = sorted(df.loc[(df["note"] < 0) | (df["note"] > 20), "note"].unique())
df.loc[(df["note"] < 0) | (df["note"] > 20), "note"] = None
print(f"\n  [A7] Notes hors de l'intervalle [0 ; 20]")
print(f"       {hors_bornes} valeur(s) rejetee(s) : {valeurs_rejetees}")

# -------------------------------------------------------------------
# Mesure : la note est-elle validee (>= 10) ?
# -------------------------------------------------------------------
df["est_valide"] = (df["note"] >= 10).astype("Int64")
# Les notes manquantes (rejetees ou absentes a l'origine) restent NaN
# et non 0, pour ne pas etre comptees comme des echecs par erreur
df.loc[df["note"].isna(), "est_valide"] = pd.NA

nb_manquantes_finales = df["note"].isna().sum()
print(f"\n  Notes manquantes au total (absences + rejets) : {nb_manquantes_finales} "
      f"({nb_manquantes_finales / len(df) * 100:.1f} %)")


# =========================================================================
# 3. JOINTURES
# =========================================================================
print("\n[JOINTURES]")

dim_etudiant = pd.read_sql("SELECT cle_etudiant, cne FROM DIM_ETUDIANT;", con=moteur)
dim_temps    = pd.read_sql("SELECT cle_temps, annee_universitaire FROM DIM_TEMPS;", con=moteur)
dim_module   = pd.read_sql("SELECT cle_module, code_module FROM DIM_MODULE;", con=moteur)

df = df.merge(dim_etudiant, left_on="CNE", right_on="cne", how="left")
print(f"  Etudiants non retrouves dans DIM_ETUDIANT : {df['cle_etudiant'].isna().sum()}")

df = df.merge(dim_temps, on="annee_universitaire", how="left")
print(f"  Annees non retrouvees dans DIM_TEMPS       : {df['cle_temps'].isna().sum()}")

df = df.merge(dim_module, on="code_module", how="left")
print(f"  Modules non retrouves dans DIM_MODULE      : {df['cle_module'].isna().sum()}")

lignes_incompletes = df[df[["cle_etudiant", "cle_temps", "cle_module"]].isna().any(axis=1)]
if len(lignes_incompletes) > 0:
    print(f"\n  ATTENTION : {len(lignes_incompletes)} ligne(s) rejetee(s) "
          f"(cle manquante apres jointure)")
    df = df.dropna(subset=["cle_etudiant", "cle_temps", "cle_module"])
else:
    print("\n  Toutes les lignes ont ete correctement rattachees a leurs dimensions")


# =========================================================================
# 4. SELECTION FINALE
# =========================================================================
df_final = df[["cle_etudiant", "cle_temps", "cle_module", "session", "note", "est_valide"]].copy()
df_final["cle_etudiant"] = df_final["cle_etudiant"].astype(int)
df_final["cle_temps"]    = df_final["cle_temps"].astype(int)
df_final["cle_module"]   = df_final["cle_module"].astype(int)

print(f"\n  Table finale prete : {len(df_final)} lignes")
print(f"  Taux de reduction global : {nb_lignes_brutes} -> {len(df_final)} lignes")


# =========================================================================
# 5. CHARGEMENT
# =========================================================================
print("\n[CHARGEMENT]")
with moteur.connect() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    conn.execute(text("TRUNCATE TABLE FAIT_RESULTAT_MODULE;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    conn.commit()
    print("  Table FAIT_RESULTAT_MODULE videe")

# Insertion par lots de 5000 lignes : plus rapide et plus sur pour
# un aussi grand volume (57 000 lignes) que tout inserer d'un coup
df_final.to_sql("FAIT_RESULTAT_MODULE", con=moteur, if_exists="append",
                 index=False, chunksize=5000)
print(f"  {len(df_final)} lignes inserees dans FAIT_RESULTAT_MODULE")


# =========================================================================
# 6. VERIFICATION
# =========================================================================
print("\n[VERIFICATION]")

verif1 = pd.read_sql("""
    SELECT MIN(note) AS note_min, MAX(note) AS note_max,
           ROUND(AVG(note), 2) AS note_moyenne
    FROM FAIT_RESULTAT_MODULE;
""", con=moteur)
print("  Bornes des notes dans MySQL (doit etre entre 0 et 20) :")
print(verif1.to_string(index=False))

verif2 = pd.read_sql("""
    SELECT session, ROUND(AVG(est_valide) * 100, 1) AS taux_validation_pct
    FROM FAIT_RESULTAT_MODULE
    WHERE est_valide IS NOT NULL
    GROUP BY session;
""", con=moteur)
print("\n  Taux de validation par session :")
print(verif2.to_string(index=False))

nb_total = pd.read_sql("SELECT COUNT(*) AS n FROM FAIT_RESULTAT_MODULE;", con=moteur)["n"][0]
print(f"\nOK -- FAIT_RESULTAT_MODULE contient maintenant {nb_total} lignes.")
