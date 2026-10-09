"""
=============================================================================
 PROJET : Systeme d'aide a la decision - Service des Affaires Estudiantines
 ETAPE  : 01 - ANALYSE EXPLORATOIRE DES DONNEES (Chapitre 1 du rapport)
=============================================================================

OBJECTIF
    Ouvrir les 5 sources, decrire leur contenu, et QUANTIFIER leurs defauts
    de qualite. Ce script ne modifie AUCUNE donnee : il ne fait qu'observer.
    Le nettoyage viendra a l'etape suivante (ETL).

SORTIES
    - un affichage detaille dans la console
    - un dossier de graphiques (PNG) reutilisables dans le rapport
    - un fichier docs/rapport_qualite.csv resumant les anomalies

COMMENT L'EXECUTER
    1. Ouvre un terminal a la racine du depot
    2. Lance :  python exploration/01_exploration.py
    Les graphiques sont ecrits dans docs/figures, le tableau dans docs/.
=============================================================================
"""

import os
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # permet de generer les images sans fenetre
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# -----------------------------------------------------------------------
# CONFIGURATION  --  chemins relatifs au depot (rien a adapter)
# -----------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_SOURCES = RACINE / "data"
DOSSIER_FIGURES = RACINE / "docs" / "figures"

os.makedirs(DOSSIER_FIGURES, exist_ok=True)

# Style graphique sobre, adapte a un rapport imprime
plt.rcParams.update({
    "figure.figsize": (9, 5),
    "figure.dpi": 130,
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
})
COULEUR = "#2E5C8A"
PALETTE = ["#2E5C8A", "#8AAFD1", "#C4553B", "#E0A08E", "#5B8C5A", "#A8C4A2"]


def titre(texte):
    """Affiche un titre de section lisible dans la console."""
    print("\n" + "=" * 76)
    print("  " + texte)
    print("=" * 76)


def sous_titre(texte):
    print("\n--- " + texte + " " + "-" * max(0, 68 - len(texte)))


# =======================================================================
# 1. CHARGEMENT DES SOURCES
# =======================================================================
titre("1. CHARGEMENT DES 5 SOURCES HETEROGENES")

# Source 1 : Excel du service scolarite
etudiants = pd.read_excel(f"{DOSSIER_SOURCES}/scolarite_etudiants.xlsx",
                          sheet_name="Etudiants")

# Source 2 : CSV de l'application d'inscription (separateur point-virgule)
inscriptions = pd.read_csv(f"{DOSSIER_SOURCES}/inscriptions.csv", sep=";")

# Source 3 : CSV de l'application de gestion des notes (separateur virgule)
notes = pd.read_csv(f"{DOSSIER_SOURCES}/notes_examens.csv", sep=",")

# Source 4 : Excel referentiel, 3 onglets
departements = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx",
                             sheet_name="Departements")
filieres = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx",
                         sheet_name="Filieres")
modules = pd.read_excel(f"{DOSSIER_SOURCES}/referentiel.xlsx",
                        sheet_name="Modules")

# Source 5 : CSV mobilite
mobilite = pd.read_csv(f"{DOSSIER_SOURCES}/mobilite_estudiantine.csv", sep=",")

sources = {
    "Etudiants (Excel)": etudiants,
    "Inscriptions (CSV)": inscriptions,
    "Notes examens (CSV)": notes,
    "Departements (Excel)": departements,
    "Filieres (Excel)": filieres,
    "Modules (Excel)": modules,
    "Mobilite (CSV)": mobilite,
}

print(f"{'SOURCE':<24}{'LIGNES':>10}{'COLONNES':>10}{'MEMOIRE':>12}")
print("-" * 56)
for nom, df in sources.items():
    memoire = df.memory_usage(deep=True).sum() / 1024**2
    print(f"{nom:<24}{len(df):>10,}{df.shape[1]:>10}{memoire:>10.1f} Mo")


# =======================================================================
# 2. STRUCTURE DES TABLES PRINCIPALES
# =======================================================================
titre("2. STRUCTURE DES TABLES")

for nom in ["Etudiants (Excel)", "Inscriptions (CSV)", "Notes examens (CSV)"]:
    df = sources[nom]
    sous_titre(nom)
    info = pd.DataFrame({
        "type": df.dtypes.astype(str),
        "non_nuls": df.notna().sum(),
        "manquants": df.isna().sum(),
        "% manquants": (df.isna().mean() * 100).round(2),
        "valeurs_distinctes": df.nunique(),
    })
    print(info.to_string())


# =======================================================================
# 3. DIAGNOSTIC DE QUALITE  --  LE COEUR DU CHAPITRE 1
# =======================================================================
titre("3. DIAGNOSTIC DE QUALITE DES DONNEES")

anomalies = []   # on collecte tout pour produire un tableau de synthese


def signaler(code, source, description, nb, total):
    """Enregistre une anomalie detectee et l'affiche."""
    pct = nb / total * 100 if total else 0
    anomalies.append({
        "code": code, "source": source, "anomalie": description,
        "nb_lignes": nb, "total_lignes": total, "pourcentage": round(pct, 2),
    })
    print(f"  [{code}] {description:<52} {nb:>6,} lignes ({pct:5.2f} %)")


# --- A1 : formats de date multiples --------------------------------------
sous_titre("A1 - Coherence des formats de date")
formats_detectes = {}
for val in inscriptions["date_inscription"].dropna().astype(str):
    if "/" in val:
        cle = "JJ/MM/AAAA"
    elif val[:4].isdigit() and val.count("-") == 2:
        cle = "AAAA-MM-JJ"
    else:
        cle = "JJ-MM-AAAA"
    formats_detectes[cle] = formats_detectes.get(cle, 0) + 1
for fmt, nb in sorted(formats_detectes.items(), key=lambda x: -x[1]):
    print(f"    format {fmt:<14} : {nb:>6,} lignes")
signaler("A1", "inscriptions", "Formats de date heterogenes",
         len(inscriptions) - max(formats_detectes.values()), len(inscriptions))

# --- A2 : codage du sexe --------------------------------------------------
sous_titre("A2 - Codage de la variable sexe")
print(etudiants["sexe"].value_counts().to_string())
non_std = (~etudiants["sexe"].isin(["M", "F"])).sum()
signaler("A2", "etudiants", "Modalites de sexe non normalisees",
         non_std, len(etudiants))

# --- A3 : casse et espaces sur la ville -----------------------------------
sous_titre("A3 - Normalisation de la ville d'origine")
villes_brutes = etudiants["ville_origine"].nunique()
villes_propres = etudiants["ville_origine"].str.strip().str.title().nunique()
print(f"    Valeurs distinctes brutes  : {villes_brutes}")
print(f"    Valeurs distinctes reelles : {villes_propres}")
print(f"    => {villes_brutes - villes_propres} variantes parasites")
mal_formees = (etudiants["ville_origine"] !=
               etudiants["ville_origine"].str.strip().str.title()).sum()
signaler("A3", "etudiants", "Villes en casse ou espacement incorrects",
         mal_formees, len(etudiants))

# --- A4 : codes filiere en minuscules -------------------------------------
sous_titre("A4 - Codes filiere")
minuscules = (inscriptions["code_filiere"] !=
              inscriptions["code_filiere"].str.upper()).sum()
signaler("A4", "inscriptions", "Codes filiere en minuscules", minuscules,
         len(inscriptions))

# --- A5 : libelles de statut ----------------------------------------------
sous_titre("A5 - Libelles du statut de fin d'annee")
print(inscriptions["statut_fin_annee"].value_counts(dropna=False).to_string())
statuts_ok = ["Admis", "Ajourne", "Abandon"]
non_norm = (~inscriptions["statut_fin_annee"].isin(statuts_ok) &
            inscriptions["statut_fin_annee"].notna()).sum()
signaler("A5", "inscriptions", "Libelles de statut non normalises",
         non_norm, len(inscriptions))

# --- A6 : separateur decimal des notes ------------------------------------
sous_titre("A6 - Format numerique des notes")
notes_txt = notes["note"].astype(str)
avec_virgule = notes_txt.str.contains(",", na=False).sum()
signaler("A6", "notes", "Notes avec separateur decimal virgule",
         avec_virgule, len(notes))

# --- A7 : notes hors bornes -----------------------------------------------
sous_titre("A7 - Validite des notes (regle metier : 0 <= note <= 20)")
notes_num = pd.to_numeric(notes_txt.str.replace(",", ".", regex=False),
                          errors="coerce")
hors_bornes = ((notes_num < 0) | (notes_num > 20)).sum()
print("    Valeurs aberrantes rencontrees :",
      sorted(notes_num[(notes_num < 0) | (notes_num > 20)].unique()))
signaler("A7", "notes", "Notes hors de l'intervalle [0 ; 20]",
         hors_bornes, len(notes))

# --- A8 : valeurs manquantes ----------------------------------------------
sous_titre("A8 - Valeurs manquantes par champ sensible")
for src, col in [(etudiants, "mention_bac"), (etudiants, "note_bac"),
                 (inscriptions, "statut_fin_annee"), (notes, "note")]:
    nb = src[col].isna().sum()
    print(f"    {col:<22} : {nb:>6,} manquants "
          f"({nb / len(src) * 100:5.2f} %)")
signaler("A8", "toutes", "Champs obligatoires non renseignes",
         int(etudiants["mention_bac"].isna().sum() +
             inscriptions["statut_fin_annee"].isna().sum() +
             notes_num.isna().sum()),
         len(etudiants) + len(inscriptions) + len(notes))

# --- A9 : doublons --------------------------------------------------------
sous_titre("A9 - Doublons stricts")
for nom, df in [("etudiants", etudiants), ("inscriptions", inscriptions),
                ("notes", notes)]:
    nb = df.duplicated().sum()
    print(f"    {nom:<16} : {nb:>6,} lignes dupliquees")
signaler("A9", "toutes", "Lignes strictement dupliquees",
         int(etudiants.duplicated().sum() + inscriptions.duplicated().sum() +
             notes.duplicated().sum()),
         len(etudiants) + len(inscriptions) + len(notes))

# --- Integrite referentielle ----------------------------------------------
sous_titre("Integrite referentielle entre les sources")
cne_etu = set(etudiants["CNE"])
cne_ins = set(inscriptions["CNE"])
cne_not = set(notes["CNE"])
print(f"    CNE dans inscriptions absents du fichier etudiants : "
      f"{len(cne_ins - cne_etu)}")
print(f"    CNE dans notes absents du fichier etudiants        : "
      f"{len(cne_not - cne_etu)}")
print(f"    Etudiants sans aucune inscription                  : "
      f"{len(cne_etu - cne_ins)}")

fil_ins = set(inscriptions["code_filiere"].str.upper())
fil_ref = set(filieres["code_filiere"])
print(f"    Codes filiere inconnus du referentiel              : "
      f"{len(fil_ins - fil_ref)}")


# =======================================================================
# 4. ANALYSE DESCRIPTIVE  --  PREMIERS CONSTATS METIER
# =======================================================================
titre("4. ANALYSE DESCRIPTIVE (avant nettoyage, a titre indicatif)")

# On prepare une copie minimalement normalisee juste pour explorer
ins = inscriptions.copy()
ins["code_filiere"] = ins["code_filiere"].str.upper()
ins["statut_fin_annee"] = ins["statut_fin_annee"].str.capitalize()
ins = ins.drop_duplicates()

sous_titre("Evolution des effectifs par annee universitaire")
effectifs = ins.groupby("annee_universitaire").size()
print(effectifs.to_string())

sous_titre("Repartition par filiere")
rep_fil = (ins.groupby("code_filiere").size()
           .sort_values(ascending=False))
print(rep_fil.to_string())

sous_titre("Statut de fin d'annee")
print(ins["statut_fin_annee"].value_counts(normalize=True)
      .mul(100).round(1).to_string())

sous_titre("Taux de reussite par filiere")
taux = (ins.dropna(subset=["statut_fin_annee"])
        .groupby("code_filiere")["statut_fin_annee"]
        .apply(lambda s: (s == "Admis").mean() * 100)
        .sort_values(ascending=False).round(1))
print(taux.to_string())

sous_titre("Taux d'abandon par filiere")
abandon = (ins.dropna(subset=["statut_fin_annee"])
           .groupby("code_filiere")["statut_fin_annee"]
           .apply(lambda s: (s == "Abandon").mean() * 100)
           .sort_values(ascending=False).round(1))
print(abandon.to_string())


# =======================================================================
# 5. GRAPHIQUES POUR LE RAPPORT
# =======================================================================
titre("5. GENERATION DES GRAPHIQUES")


def sauver(nom_fichier):
    plt.tight_layout()
    chemin = f"{DOSSIER_FIGURES}/{nom_fichier}"
    plt.savefig(chemin, bbox_inches="tight")
    plt.close()
    print(f"    figure enregistree : {nom_fichier}")


# Fig 1 : evolution des effectifs
fig, ax = plt.subplots()
ax.plot(effectifs.index, effectifs.values, marker="o", color=COULEUR, lw=2)
ax.fill_between(range(len(effectifs)), effectifs.values, alpha=0.12,
                color=COULEUR)
ax.set_title("Evolution des effectifs inscrits par annee universitaire")
ax.set_ylabel("Nombre d'inscriptions")
ax.set_ylim(bottom=0)
plt.xticks(rotation=20)
sauver("fig1_evolution_effectifs.png")

# Fig 2 : repartition par filiere
fig, ax = plt.subplots()
ax.barh(rep_fil.index[::-1], rep_fil.values[::-1], color=COULEUR)
ax.set_title("Repartition des inscriptions par filiere (5 annees cumulees)")
ax.set_xlabel("Nombre d'inscriptions")
sauver("fig2_repartition_filieres.png")

# Fig 3 : statut de fin d'annee
fig, ax = plt.subplots(figsize=(6, 6))
vc = ins["statut_fin_annee"].value_counts()
ax.pie(vc.values, labels=vc.index, autopct="%1.1f%%",
       colors=PALETTE[:len(vc)], startangle=90,
       wedgeprops={"edgecolor": "white", "linewidth": 2})
ax.set_title("Repartition des statuts de fin d'annee")
sauver("fig3_statuts.png")

# Fig 4 : taux de reussite et d'abandon par filiere
fig, ax = plt.subplots()
x = np.arange(len(taux))
ax.bar(x - 0.2, taux.values, 0.4, label="Taux de reussite", color=PALETTE[0])
ax.bar(x + 0.2, abandon.reindex(taux.index).values, 0.4,
       label="Taux d'abandon", color=PALETTE[2])
ax.set_xticks(x)
ax.set_xticklabels(taux.index)
ax.set_ylabel("%")
ax.set_title("Reussite et abandon par filiere")
ax.legend()
sauver("fig4_reussite_abandon.png")

# Fig 5 : distribution des notes
fig, ax = plt.subplots()
valides = notes_num[(notes_num >= 0) & (notes_num <= 20)]
ax.hist(valides, bins=40, color=COULEUR, edgecolor="white")
ax.axvline(10, color=PALETTE[2], ls="--", lw=2, label="Seuil de validation")
ax.set_title("Distribution des notes obtenues (toutes sessions)")
ax.set_xlabel("Note sur 20")
ax.set_ylabel("Effectif")
ax.legend()
sauver("fig5_distribution_notes.png")

# Fig 6 : completude des donnees
fig, ax = plt.subplots()
comp = pd.Series({
    "mention_bac": etudiants["mention_bac"].notna().mean() * 100,
    "note_bac": etudiants["note_bac"].notna().mean() * 100,
    "statut_fin_annee": inscriptions["statut_fin_annee"].notna().mean() * 100,
    "note": notes_num.notna().mean() * 100,
    "ville_origine": etudiants["ville_origine"].notna().mean() * 100,
}).sort_values()
ax.barh(comp.index, comp.values, color=PALETTE[4])
ax.set_xlim(0, 100)
ax.set_xlabel("Taux de completude (%)")
ax.set_title("Completude des champs sensibles avant nettoyage")
for i, v in enumerate(comp.values):
    ax.text(v + 1, i, f"{v:.1f} %", va="center", fontsize=9)
sauver("fig6_completude.png")


# =======================================================================
# 6. TABLEAU DE SYNTHESE DES ANOMALIES
# =======================================================================
titre("6. SYNTHESE DES ANOMALIES DETECTEES")
df_anomalies = pd.DataFrame(anomalies)
print(df_anomalies.to_string(index=False))

chemin_csv = RACINE / "docs" / "rapport_qualite.csv"
df_anomalies.to_csv(chemin_csv, index=False, sep=";", encoding="utf-8-sig")
print(f"\nTableau enregistre : {chemin_csv}")

titre("EXPLORATION TERMINEE")
print("""
  Ce que tu dois retenir pour le Chapitre 1 :
    - les 5 sources sont heterogenes (2 formats, 3 separateurs differents)
    - 9 categories d'anomalies sont mesurees et quantifiees
    - l'integrite referentielle entre sources est verifiee
    - 6 graphiques sont prets a etre inseres dans le rapport

  Etape suivante : conception du modele en etoile, puis ETL de nettoyage.
""")
