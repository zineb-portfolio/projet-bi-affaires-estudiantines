"""
=============================================================================
 ETL - ETAPE 5 : chargement de FAIT_INSCRIPTION (la table centrale)
=============================================================================

OBJECTIF
    C'est la table de faits principale : le coeur de l'entrepot. Ce script
    corrige 3 anomalies et relie l'inscription a ses 5 dimensions.

        A1 - 3 formats de date coexistent (JJ/MM/AAAA, AAAA-MM-JJ, JJ-MM-AAAA)
        A4 - certains codes filiere sont en minuscules ("smp" au lieu de "SMP")
        A5 - certains statuts ne sont pas normalises ("ADMIS", "ajourne")
        A9 - des lignes sont dupliquees

    NOUVEAU CONCEPT DANS CE SCRIPT : LA JOINTURE
        Le fichier source dit "l'etudiant R2020000001 est inscrit en SMP".
        Mais MySQL ne connait ni "R2020000001" ni "SMP" -- il connait
        cle_etudiant=147 et cle_filiere=3. Une jointure consiste a
        remplacer chaque code metier par la cle numerique correspondante,
        en allant la chercher dans la dimension deja chargee dans MySQL.

COMMENT L'EXECUTER
    1. Verifie que MySQL tourne (XAMPP, vert, port 3306)
    2. Verifie que DIM_ETUDIANT, DIM_TEMPS, DIM_FILIERE, DIM_NIVEAU,
       DIM_STATUT, DIM_MODULE sont deja remplies (scripts precedents)
    3. python 06_etl_fait_inscription.py
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
inscriptions = pd.read_csv(f"{DOSSIER_SOURCES}/inscriptions.csv", sep=";")
nb_lignes_brutes = len(inscriptions)
print(f"  {nb_lignes_brutes} lignes lues depuis inscriptions.csv")

# On recharge aussi les modules pour calculer nb_modules_total par
# (filiere, annee_etude) -- necessaire pour une mesure de la table de faits
modules_ref = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx", sheet_name="Modules")
nb_modules_par_filiere_annee = (
    modules_ref.groupby(["code_filiere", "annee_etude"])
    .size().reset_index(name="nb_modules_total")
)


# =========================================================================
# 2. TRANSFORMATION -- nettoyage puis jointures
# =========================================================================
print("\n[TRANSFORMATION]")
df = inscriptions.copy()

# -------------------------------------------------------------------
# REGLE A9 -- doublons stricts, en premier
# -------------------------------------------------------------------
avant = len(df)
df = df.drop_duplicates()
print(f"\n  [A9] Doublons stricts : {avant} -> {len(df)} lignes "
      f"({avant - len(df)} supprime(s))")

# -------------------------------------------------------------------
# REGLE A4 -- codes filiere en minuscules
# -------------------------------------------------------------------
nb_minuscules = (df["code_filiere"] != df["code_filiere"].str.upper()).sum()
df["code_filiere"] = df["code_filiere"].str.upper()
print(f"\n  [A4] Codes filiere : {nb_minuscules} valeur(s) mises en majuscules")

# -------------------------------------------------------------------
# REGLE A5 -- statuts non normalises
# -------------------------------------------------------------------
avant_valeurs = df["statut_fin_annee"].value_counts(dropna=False).to_dict()
df["statut_fin_annee"] = df["statut_fin_annee"].str.capitalize()
# "capitalize()" met en forme "ADMIS"->"Admis", "ajourne"->"Ajourne", etc.
# On uniformise aussi l'orthographe (accent absent dans les fichiers sources)
df["statut_fin_annee"] = df["statut_fin_annee"].replace({
    "Ajourne": "Ajourne",  # deja correct, ligne gardee pour lisibilite
})
apres_valeurs = df["statut_fin_annee"].value_counts(dropna=False).to_dict()
print(f"\n  [A5] Normalisation des statuts")
print(f"       avant : {avant_valeurs}")
print(f"       apres : {apres_valeurs}")
# les lignes sans statut (dossier non cloture) recoivent une valeur explicite
df["statut_fin_annee"] = df["statut_fin_annee"].fillna("Non cloture")

# -------------------------------------------------------------------
# REGLE A1 -- 3 formats de date coexistants
# On detecte automatiquement le format de CHAQUE ligne et on la
# convertit vers un format unique (AAAA-MM-JJ, le standard SQL)
# -------------------------------------------------------------------
def parser_date_heterogene(valeur):
    """Essaie plusieurs formats de date jusqu'a trouver celui qui marche."""
    if pd.isna(valeur):
        return pd.NaT
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return pd.to_datetime(valeur, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT  # aucun format n'a fonctionne

avant_nat = df["date_inscription"].isna().sum()
df["date_inscription"] = df["date_inscription"].apply(parser_date_heterogene)
apres_nat = df["date_inscription"].isna().sum()
print(f"\n  [A1] Formats de date heterogenes")
print(f"       dates non interpretables avant conversion : {avant_nat}")
print(f"       dates non interpretables apres conversion : {apres_nat}")
if apres_nat > avant_nat:
    print(f"       ATTENTION : {apres_nat - avant_nat} date(s) n'ont pas pu etre lues")
else:
    print("       Toutes les dates ont ete converties avec succes")


# -------------------------------------------------------------------
# On rajoute le nombre total de modules de l'annee (pour calculer un
# taux de validation dans les futurs tableaux de bord)
# -------------------------------------------------------------------
df = df.merge(nb_modules_par_filiere_annee, on=["code_filiere", "annee_etude"], how="left")

# -------------------------------------------------------------------
# Construction des mesures 0/1 -- l'astuce qui permet de calculer
# n'importe quel taux avec un simple AVG()
# -------------------------------------------------------------------
df["est_nouvelle_inscription"] = (df["type_inscription"] == "Inscription").astype(int)
df["est_admis"]   = (df["statut_fin_annee"] == "Admis").astype(int)
df["est_ajourne"] = (df["statut_fin_annee"] == "Ajourne").astype(int)
df["est_abandon"] = (df["statut_fin_annee"] == "Abandon").astype(int)


# =========================================================================
# 3. JOINTURES -- remplacer les codes metier par les cles numeriques MySQL
# =========================================================================
print("\n[JOINTURES]")

# On recupere chaque dimension deja chargee dans MySQL
dim_etudiant = pd.read_sql("SELECT cle_etudiant, cne FROM DIM_ETUDIANT;", con=moteur)
dim_temps    = pd.read_sql("SELECT cle_temps, annee_universitaire FROM DIM_TEMPS;", con=moteur)
dim_filiere  = pd.read_sql("SELECT cle_filiere, code_filiere FROM DIM_FILIERE;", con=moteur)
dim_niveau   = pd.read_sql("SELECT cle_niveau, niveau, cycle FROM DIM_NIVEAU;", con=moteur)
dim_statut   = pd.read_sql("SELECT cle_statut, libelle_statut FROM DIM_STATUT;", con=moteur)

# Jointure 1 : CNE -> cle_etudiant
df = df.merge(dim_etudiant, left_on="CNE", right_on="cne", how="left")
non_trouves = df["cle_etudiant"].isna().sum()
print(f"  Etudiants non retrouves dans DIM_ETUDIANT : {non_trouves}")

# Jointure 2 : annee_universitaire -> cle_temps
df = df.merge(dim_temps, on="annee_universitaire", how="left")
non_trouves = df["cle_temps"].isna().sum()
print(f"  Annees non retrouvees dans DIM_TEMPS       : {non_trouves}")

# Jointure 3 : code_filiere -> cle_filiere
df = df.merge(dim_filiere, on="code_filiere", how="left")
non_trouves = df["cle_filiere"].isna().sum()
print(f"  Filieres non retrouvees dans DIM_FILIERE   : {non_trouves}")

# Jointure 4 : (niveau, cycle) -> cle_niveau
df = df.merge(dim_niveau, on=["niveau", "cycle"], how="left")
non_trouves = df["cle_niveau"].isna().sum()
print(f"  Niveaux non retrouves dans DIM_NIVEAU       : {non_trouves}")

# Jointure 5 : statut_fin_annee -> cle_statut
df = df.merge(dim_statut, left_on="statut_fin_annee", right_on="libelle_statut", how="left")
non_trouves = df["cle_statut"].isna().sum()
print(f"  Statuts non retrouves dans DIM_STATUT        : {non_trouves}")

# Si des lignes n'ont pas trouve leur cle (probleme d'integrite),
# on les signale clairement plutot que de les charger avec des cles nulles
lignes_incompletes = df[df[["cle_etudiant", "cle_temps", "cle_filiere",
                            "cle_niveau"]].isna().any(axis=1)]
if len(lignes_incompletes) > 0:
    print(f"\n  ATTENTION : {len(lignes_incompletes)} ligne(s) rejetee(s) "
          f"(cle manquante apres jointure)")
    df = df.dropna(subset=["cle_etudiant", "cle_temps", "cle_filiere", "cle_niveau"])
else:
    print("\n  Toutes les lignes ont ete correctement rattachees a leurs dimensions")


# =========================================================================
# 4. SELECTION FINALE DES COLONNES
# =========================================================================
df_final = df[[
    "cle_etudiant", "cle_temps", "cle_filiere", "cle_niveau", "cle_statut",
    "type_inscription", "date_inscription", "regime",
    "nb_redoublements", "moyenne_annuelle", "modules_valides", "nb_modules_total",
    "est_nouvelle_inscription", "est_admis", "est_ajourne", "est_abandon",
]].rename(columns={"modules_valides": "nb_modules_valides"})

# types corrects pour l'insertion SQL
df_final["cle_etudiant"] = df_final["cle_etudiant"].astype(int)
df_final["cle_temps"]    = df_final["cle_temps"].astype(int)
df_final["cle_filiere"]  = df_final["cle_filiere"].astype(int)
df_final["cle_niveau"]   = df_final["cle_niveau"].astype(int)
df_final["cle_statut"]   = df_final["cle_statut"].astype("Int64")

print(f"\n  Table finale prete : {len(df_final)} lignes, {df_final.shape[1]} colonnes")
print(f"  Taux de reduction global : {nb_lignes_brutes} -> {len(df_final)} lignes")


# =========================================================================
# 5. CHARGEMENT
# =========================================================================
print("\n[CHARGEMENT]")
with moteur.connect() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
    conn.execute(text("TRUNCATE TABLE FAIT_INSCRIPTION;"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
    conn.commit()
    print("  Table FAIT_INSCRIPTION videe")

df_final.to_sql("FAIT_INSCRIPTION", con=moteur, if_exists="append", index=False)
print(f"  {len(df_final)} lignes inserees dans FAIT_INSCRIPTION")


# =========================================================================
# 6. VERIFICATION -- on recalcule des indicateurs directement en SQL
# =========================================================================
print("\n[VERIFICATION]")

verif1 = pd.read_sql("""
    SELECT s.libelle_statut, COUNT(*) AS nb
    FROM FAIT_INSCRIPTION f
    JOIN DIM_STATUT s ON f.cle_statut = s.cle_statut
    GROUP BY s.libelle_statut;
""", con=moteur)
print("  Repartition des statuts (doit montrer des libelles propres) :")
print(verif1.to_string(index=False))

verif2 = pd.read_sql("""
    SELECT ROUND(AVG(est_admis) * 100, 1) AS taux_reussite_pct,
           ROUND(AVG(est_abandon) * 100, 1) AS taux_abandon_pct,
           ROUND(AVG(moyenne_annuelle), 2) AS moyenne_generale
    FROM FAIT_INSCRIPTION;
""", con=moteur)
print("\n  Indicateurs globaux calcules directement depuis MySQL :")
print(verif2.to_string(index=False))

nb_total = pd.read_sql("SELECT COUNT(*) AS n FROM FAIT_INSCRIPTION;", con=moteur)["n"][0]
print(f"\nOK -- FAIT_INSCRIPTION contient maintenant {nb_total} lignes.")
