"""
=============================================================================
 ETL - ETAPE 4 : chargement et NETTOYAGE de DIM_ETUDIANT
=============================================================================

OBJECTIF
    C'est la premiere table qui contient de vraies anomalies. On corrige ici
    4 des 9 anomalies mesurees a l'exploration (Chapitre 1) :

        A2 - le sexe est ecrit de 6 facons differentes
        A3 - les villes ont une casse et un espacement incoherents
        A8 - la mention au bac est parfois manquante
        A9 - certaines lignes sont des doublons stricts

    Chaque etape ci-dessous affiche AVANT / APRES, pour que le rapport
    puisse citer des chiffres precis.

COMMENT L'EXECUTER
    1. Verifie que MySQL tourne dans XAMPP (vert, port 3306)
    2. python 05_etl_dim_etudiant.py
=============================================================================
"""

import numpy as np
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
etudiants = pd.read_excel(f"{DOSSIER_SOURCES}/scolarite_etudiants.xlsx")
nb_lignes_brutes = len(etudiants)
print(f"  {nb_lignes_brutes} lignes lues depuis scolarite_etudiants.xlsx")


# =========================================================================
# 2. TRANSFORMATION -- 4 regles de nettoyage, une par une
# =========================================================================
print("\n[TRANSFORMATION]")
df = etudiants.copy()

# -------------------------------------------------------------------
# REGLE A9 -- Suppression des doublons stricts
# On la fait EN PREMIER : pas la peine de nettoyer deux fois la meme
# ligne si elle est dupliquee.
# -------------------------------------------------------------------
avant = len(df)
df = df.drop_duplicates()
apres = len(df)
print(f"\n  [A9] Doublons stricts")
print(f"       avant : {avant} lignes -> apres : {apres} lignes "
      f"({avant - apres} doublon(s) supprime(s))")

# -------------------------------------------------------------------
# REGLE A2 -- Normalisation du sexe
# 6 ecritures observees -> 2 valeurs cibles : 'M' ou 'F'
# On utilise un dictionnaire de correspondance (table de mapping),
# la methode standard pour ce type de nettoyage.
# -------------------------------------------------------------------
avant_valeurs = df["sexe"].value_counts().to_dict()

correspondance_sexe = {
    "M": "M", "Masculin": "M", "H": "M",
    "F": "F", "Feminin": "F", "Fem": "F",
}
df["sexe"] = df["sexe"].map(correspondance_sexe)

non_reconnus = df["sexe"].isna().sum()
print(f"\n  [A2] Normalisation du sexe")
print(f"       valeurs rencontrees avant : {avant_valeurs}")
print(f"       valeurs apres normalisation : {df['sexe'].value_counts().to_dict()}")
if non_reconnus > 0:
    print(f"       ATTENTION : {non_reconnus} valeur(s) non reconnue(s)")

# -------------------------------------------------------------------
# REGLE A3 -- Normalisation des villes
# On enleve les espaces en trop (strip) et on uniformise la casse
# (Title -> "rabat" et "RABAT" deviennent tous les deux "Rabat")
# -------------------------------------------------------------------
avant_distinctes = df["ville_origine"].nunique()
df["ville_origine"] = df["ville_origine"].str.strip().str.title()
apres_distinctes = df["ville_origine"].nunique()
print(f"\n  [A3] Normalisation des villes")
print(f"       valeurs distinctes avant : {avant_distinctes}")
print(f"       valeurs distinctes apres : {apres_distinctes}")
print(f"       -> {avant_distinctes - apres_distinctes} variante(s) parasite(s) eliminee(s)")

# -------------------------------------------------------------------
# REGLE A8 -- Valeurs manquantes (mention au bac)
# On ne PEUT PAS deviner une mention manquante. La bonne pratique est
# de la rendre explicite plutot que de la laisser vide silencieusement :
# on cree une categorie "Non renseignee" qui apparaitra clairement
# dans les futurs tableaux de bord, au lieu de disparaitre sans trace.
# -------------------------------------------------------------------
nb_manquants_avant = df["mention_bac"].isna().sum()
df["mention_bac"] = df["mention_bac"].fillna("Non renseignee")
print(f"\n  [A8] Valeurs manquantes (mention au bac)")
print(f"       {nb_manquants_avant} valeur(s) manquante(s) "
      f"-> remplacees par 'Non renseignee'")

# -------------------------------------------------------------------
# Colonne calculee utile pour les tableaux de bord : age actuel
# -------------------------------------------------------------------
aujourd_hui = pd.Timestamp.now()
df["age_actuel"] = ((aujourd_hui - df["date_naissance"]).dt.days // 365).astype("Int64")

# -------------------------------------------------------------------
# Conversion boursier / handicap : 'Oui'/'Non' -> 'O'/'N'
# (la table MySQL attend un seul caractere, cf. script de creation)
# -------------------------------------------------------------------
df["boursier"] = df["boursier"].map({"Oui": "O", "Non": "N"}).fillna("N")
df["situation_handicap"] = df["situation_handicap"].map({"Oui": "O", "Non": "N"}).fillna("N")

# -------------------------------------------------------------------
# Selection et ordre final des colonnes, pour correspondre exactement
# a la table DIM_ETUDIANT cote MySQL
# -------------------------------------------------------------------
df_final = df[[
    "CNE", "nom", "prenom", "sexe", "date_naissance", "age_actuel",
    "ville_origine", "nationalite", "type_bac", "annee_bac",
    "mention_bac", "note_bac", "boursier", "situation_handicap",
]].rename(columns={"CNE": "cne"})

print(f"\n  Table finale prete : {len(df_final)} lignes, {df_final.shape[1]} colonnes")
print(f"  Taux de reduction global : {nb_lignes_brutes} -> {len(df_final)} lignes "
      f"({nb_lignes_brutes - len(df_final)} lignes supprimees par dedoublonnage)")


# =========================================================================
# 3. CHARGEMENT
# =========================================================================
print("\n[CHARGEMENT]")
with moteur.connect() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    conn.execute(text("TRUNCATE TABLE DIM_ETUDIANT;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    conn.commit()
    print("  Table DIM_ETUDIANT videe")

df_final.to_sql("DIM_ETUDIANT", con=moteur, if_exists="append", index=False)
print(f"  {len(df_final)} lignes inserees dans DIM_ETUDIANT")


# =========================================================================
# 4. VERIFICATION
# =========================================================================
print("\n[VERIFICATION]")
verif = pd.read_sql("""
    SELECT sexe, COUNT(*) AS nb
    FROM DIM_ETUDIANT
    GROUP BY sexe;
""", con=moteur)
print("  Repartition du sexe dans MySQL (doit montrer uniquement M et F) :")
print(verif.to_string(index=False))

nb_total = pd.read_sql("SELECT COUNT(*) AS n FROM DIM_ETUDIANT;", con=moteur)["n"][0]
nb_villes = pd.read_sql("SELECT COUNT(DISTINCT ville_origine) AS n FROM DIM_ETUDIANT;",
                        con=moteur)["n"][0]
print(f"\n  Total etudiants dans DIM_ETUDIANT : {nb_total}")
print(f"  Nombre de villes distinctes        : {nb_villes} (etait 87 avant nettoyage)")

print(f"\nOK -- DIM_ETUDIANT contient maintenant {nb_total} lignes propres.")
