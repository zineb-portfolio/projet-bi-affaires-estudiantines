-- =============================================================================
--  PROJET : Systeme d'aide a la decision - Affaires Estudiantines
--  ETAPE  : Creation du schema en etoile dans l'entrepot de donnees
--
--  A EXECUTER DANS phpMyAdmin :
--    1. Ouvre localhost/phpmyadmin
--    2. Clique sur la base dw_affaires_estudiantines (colonne de gauche)
--    3. Clique sur l'onglet SQL en haut
--    4. Colle tout ce fichier
--    5. Clique sur le bouton Executer
-- =============================================================================

USE dw_affaires_estudiantines;

-- On supprime les tables si elles existent deja (permet de relancer le
-- script proprement pendant les tests, sans erreur "table already exists")
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS FAIT_RESULTAT_MODULE;
DROP TABLE IF EXISTS FAIT_MOBILITE;
DROP TABLE IF EXISTS FAIT_INSCRIPTION;
DROP TABLE IF EXISTS DIM_MODULE;
DROP TABLE IF EXISTS DIM_STATUT;
DROP TABLE IF EXISTS DIM_NIVEAU;
DROP TABLE IF EXISTS DIM_FILIERE;
DROP TABLE IF EXISTS DIM_TEMPS;
DROP TABLE IF EXISTS DIM_ETUDIANT;
SET FOREIGN_KEY_CHECKS = 1;


-- =============================================================================
-- LES DIMENSIONS  (les "petits tableaux" qui decrivent)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- DIM_ETUDIANT : qui est l'etudiant
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_ETUDIANT (
    cle_etudiant        INT AUTO_INCREMENT PRIMARY KEY,
    cne                 VARCHAR(20)  NOT NULL UNIQUE,
    nom                 VARCHAR(100) NOT NULL,
    prenom              VARCHAR(100) NOT NULL,
    sexe                CHAR(1)      NOT NULL,          -- 'M' ou 'F', normalise par l'ETL
    date_naissance      DATE,
    age_actuel          INT,
    ville_origine       VARCHAR(100),
    nationalite         VARCHAR(100),
    type_bac            VARCHAR(100),
    annee_bac           INT,
    mention_bac         VARCHAR(30),
    note_bac            DECIMAL(4,2),
    boursier            CHAR(1)      DEFAULT 'N',        -- 'O' ou 'N'
    situation_handicap  CHAR(1)      DEFAULT 'N',
    date_chargement     TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- DIM_TEMPS : quelle annee universitaire
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_TEMPS (
    cle_temps            INT AUTO_INCREMENT PRIMARY KEY,
    annee_universitaire  VARCHAR(9)  NOT NULL UNIQUE,   -- ex: '2022-2023'
    annee_debut          INT         NOT NULL,          -- ex: 2022
    annee_fin            INT         NOT NULL,          -- ex: 2023
    rang_annee           INT         NOT NULL           -- 1 = plus ancienne, 5 = plus recente
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- DIM_FILIERE : quelle filiere
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_FILIERE (
    cle_filiere         INT AUTO_INCREMENT PRIMARY KEY,
    code_filiere        VARCHAR(10)  NOT NULL UNIQUE,
    libelle_filiere     VARCHAR(150) NOT NULL,
    code_departement    VARCHAR(20),
    libelle_departement VARCHAR(150),
    cycle               VARCHAR(20)  NOT NULL,          -- 'Licence' ou 'Master'
    duree_annees        INT,
    capacite_annuelle   INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- DIM_NIVEAU : quelle annee d'etude dans le cursus
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_NIVEAU (
    cle_niveau      INT AUTO_INCREMENT PRIMARY KEY,
    niveau          VARCHAR(20) NOT NULL,               -- ex: 'S1/S2', 'M1'
    annee_etude     INT         NOT NULL,               -- 1, 2 ou 3
    cycle           VARCHAR(20) NOT NULL,
    UNIQUE KEY uk_niveau (niveau, cycle)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- DIM_STATUT : le resultat de fin d'annee
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_STATUT (
    cle_statut      INT AUTO_INCREMENT PRIMARY KEY,
    libelle_statut  VARCHAR(30) NOT NULL UNIQUE          -- 'Admis','Ajourne','Abandon','Non cloture'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------------------------
-- DIM_MODULE : pour la table de faits secondaire
-- -----------------------------------------------------------------------------
CREATE TABLE DIM_MODULE (
    cle_module       INT AUTO_INCREMENT PRIMARY KEY,
    code_module      VARCHAR(20)  NOT NULL UNIQUE,
    libelle_module   VARCHAR(150) NOT NULL,
    code_filiere     VARCHAR(10),
    annee_etude      INT,
    semestre         VARCHAR(10),
    coefficient      INT,
    volume_horaire   INT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- LES TABLES DE FAITS  (la "grande table" au centre)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- FAIT_INSCRIPTION : grain = un etudiant, une filiere, une annee universitaire
-- -----------------------------------------------------------------------------
CREATE TABLE FAIT_INSCRIPTION (
    cle_inscription           INT AUTO_INCREMENT PRIMARY KEY,

    -- cles etrangeres vers les dimensions
    cle_etudiant              INT NOT NULL,
    cle_temps                 INT NOT NULL,
    cle_filiere               INT NOT NULL,
    cle_niveau                INT NOT NULL,
    cle_statut                INT,

    -- attributs degeneres (utiles mais ne meritent pas leur propre dimension)
    type_inscription          VARCHAR(20),               -- 'Inscription' / 'Reinscription'
    date_inscription          DATE,
    regime                    VARCHAR(20),

    -- mesures numeriques
    nb_redoublements          INT DEFAULT 0,
    moyenne_annuelle          DECIMAL(4,2),
    nb_modules_valides        INT,
    nb_modules_total          INT,

    -- mesures 0/1 : l'astuce qui permet de calculer n'importe quel taux
    -- avec un simple AVG(), a n'importe quel niveau de regroupement
    est_nouvelle_inscription  TINYINT DEFAULT 0,
    est_admis                 TINYINT DEFAULT 0,
    est_ajourne                TINYINT DEFAULT 0,
    est_abandon                TINYINT DEFAULT 0,

    date_chargement           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_ins_etudiant FOREIGN KEY (cle_etudiant) REFERENCES DIM_ETUDIANT(cle_etudiant),
    CONSTRAINT fk_ins_temps    FOREIGN KEY (cle_temps)    REFERENCES DIM_TEMPS(cle_temps),
    CONSTRAINT fk_ins_filiere  FOREIGN KEY (cle_filiere)  REFERENCES DIM_FILIERE(cle_filiere),
    CONSTRAINT fk_ins_niveau   FOREIGN KEY (cle_niveau)   REFERENCES DIM_NIVEAU(cle_niveau),
    CONSTRAINT fk_ins_statut   FOREIGN KEY (cle_statut)   REFERENCES DIM_STATUT(cle_statut),

    -- un etudiant ne peut avoir qu'UNE seule inscription par annee
    UNIQUE KEY uk_inscription (cle_etudiant, cle_temps)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Index pour accelerer les regroupements les plus frequents
CREATE INDEX idx_ins_filiere_temps ON FAIT_INSCRIPTION(cle_filiere, cle_temps);
CREATE INDEX idx_ins_statut        ON FAIT_INSCRIPTION(cle_statut);

-- -----------------------------------------------------------------------------
-- FAIT_RESULTAT_MODULE : grain = un etudiant, un module, une session
-- -----------------------------------------------------------------------------
CREATE TABLE FAIT_RESULTAT_MODULE (
    cle_resultat     INT AUTO_INCREMENT PRIMARY KEY,

    cle_etudiant     INT NOT NULL,
    cle_temps        INT NOT NULL,
    cle_module       INT NOT NULL,

    session          VARCHAR(20) NOT NULL,               -- 'Normale' / 'Rattrapage'
    note             DECIMAL(4,2),
    est_valide       TINYINT,                             -- 1 si note >= 10

    date_chargement  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_res_etudiant FOREIGN KEY (cle_etudiant) REFERENCES DIM_ETUDIANT(cle_etudiant),
    CONSTRAINT fk_res_temps    FOREIGN KEY (cle_temps)    REFERENCES DIM_TEMPS(cle_temps),
    CONSTRAINT fk_res_module   FOREIGN KEY (cle_module)   REFERENCES DIM_MODULE(cle_module)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_res_module ON FAIT_RESULTAT_MODULE(cle_module);

-- -----------------------------------------------------------------------------
-- FAIT_MOBILITE : grain = une mobilite realisee par un etudiant
-- -----------------------------------------------------------------------------
CREATE TABLE FAIT_MOBILITE (
    cle_mobilite      INT AUTO_INCREMENT PRIMARY KEY,

    cle_etudiant      INT NOT NULL,
    cle_temps         INT NOT NULL,

    type_mobilite     VARCHAR(20),                        -- 'Sortante' / 'Entrante'
    pays_destination  VARCHAR(100),
    programme         VARCHAR(100),
    duree_mois        INT,
    statut            VARCHAR(20),                        -- 'Realisee' / 'Annulee' / 'En cours'

    date_chargement   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_mob_etudiant FOREIGN KEY (cle_etudiant) REFERENCES DIM_ETUDIANT(cle_etudiant),
    CONSTRAINT fk_mob_temps    FOREIGN KEY (cle_temps)    REFERENCES DIM_TEMPS(cle_temps)

) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- ALIMENTATION DES DIMENSIONS FIXES
--   (celles qui ne dependent pas des fichiers sources : on peut les remplir
--    directement en SQL, l'ETL Python n'aura pas besoin d'y toucher)
-- =============================================================================

INSERT INTO DIM_TEMPS (annee_universitaire, annee_debut, annee_fin, rang_annee) VALUES
('2020-2021', 2020, 2021, 1),
('2021-2022', 2021, 2022, 2),
('2022-2023', 2022, 2023, 3),
('2023-2024', 2023, 2024, 4),
('2024-2025', 2024, 2025, 5);

INSERT INTO DIM_STATUT (libelle_statut) VALUES
('Admis'), ('Ajourne'), ('Abandon'), ('Non cloture');


-- =============================================================================
-- VERIFICATION
-- =============================================================================
SELECT 'DIM_ETUDIANT'          AS table_name, COUNT(*) AS nb_lignes FROM DIM_ETUDIANT
UNION ALL SELECT 'DIM_TEMPS',            COUNT(*) FROM DIM_TEMPS
UNION ALL SELECT 'DIM_FILIERE',          COUNT(*) FROM DIM_FILIERE
UNION ALL SELECT 'DIM_NIVEAU',           COUNT(*) FROM DIM_NIVEAU
UNION ALL SELECT 'DIM_STATUT',           COUNT(*) FROM DIM_STATUT
UNION ALL SELECT 'DIM_MODULE',           COUNT(*) FROM DIM_MODULE
UNION ALL SELECT 'FAIT_INSCRIPTION',     COUNT(*) FROM FAIT_INSCRIPTION
UNION ALL SELECT 'FAIT_RESULTAT_MODULE', COUNT(*) FROM FAIT_RESULTAT_MODULE
UNION ALL SELECT 'FAIT_MOBILITE',        COUNT(*) FROM FAIT_MOBILITE;

-- Tu dois voir 8 lignes. DIM_TEMPS = 5, DIM_STATUT = 4, le reste = 0
-- (normal : elles seront remplies par le script ETL Python a l'etape suivante)
