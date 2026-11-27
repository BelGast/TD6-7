-- Schéma SQLite de la plateforme OpenStudy
-- Reconstitué à partir des requêtes de charger_vers_db.py et statistiques_questionnaire.py

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS utilisateur (
    id_utilisateur INTEGER PRIMARY KEY AUTOINCREMENT,
    nom            TEXT NOT NULL UNIQUE,
    prénom         TEXT,
    email          TEXT,
    rôle           TEXT NOT NULL DEFAULT 'chercheur'
);

CREATE TABLE IF NOT EXISTS questionnaire (
    id_questionnaire INTEGER PRIMARY KEY AUTOINCREMENT,
    titre            TEXT NOT NULL UNIQUE,
    visibilité       TEXT NOT NULL DEFAULT 'public',
    date_creation    TEXT NOT NULL,
    id_utilisateur   INTEGER NOT NULL,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur)
);

CREATE TABLE IF NOT EXISTS question (
    id_question      INTEGER PRIMARY KEY AUTOINCREMENT,
    libellé          TEXT NOT NULL,
    type             TEXT NOT NULL CHECK (type IN ('numerique', 'choix_multiple')),
    min              REAL,
    max              REAL,
    pondération      REAL NOT NULL DEFAULT 1.0,
    inversé          INTEGER NOT NULL DEFAULT 0 CHECK (inversé IN (0, 1)),
    id_questionnaire INTEGER NOT NULL,
    FOREIGN KEY (id_questionnaire) REFERENCES questionnaire(id_questionnaire) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS valeur (
    libellé TEXT NOT NULL,
    score   REAL NOT NULL,
    PRIMARY KEY (libellé, score)
);

CREATE TABLE IF NOT EXISTS question_valeur (
    id_question    INTEGER NOT NULL,
    valeur_libellé TEXT NOT NULL,
    valeur_score   REAL NOT NULL,
    PRIMARY KEY (id_question, valeur_libellé, valeur_score),
    FOREIGN KEY (id_question) REFERENCES question(id_question) ON DELETE CASCADE,
    FOREIGN KEY (valeur_libellé, valeur_score) REFERENCES valeur(libellé, score) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS participant (
    id_participant   INTEGER PRIMARY KEY AUTOINCREMENT,
    age              INTEGER,
    genre            TEXT,
    score_total      REAL,
    commentaire      TEXT,
    id_questionnaire INTEGER NOT NULL,
    id_utilisateur   INTEGER NOT NULL,
    FOREIGN KEY (id_questionnaire) REFERENCES questionnaire(id_questionnaire) ON DELETE CASCADE,
    FOREIGN KEY (id_utilisateur) REFERENCES utilisateur(id_utilisateur)
);

CREATE TABLE IF NOT EXISTS repond (
    id_participant INTEGER NOT NULL,
    id_question    INTEGER NOT NULL,
    valeur         TEXT NOT NULL,
    date_heure     TEXT NOT NULL,
    PRIMARY KEY (id_participant, id_question),
    FOREIGN KEY (id_participant) REFERENCES participant(id_participant) ON DELETE CASCADE,
    FOREIGN KEY (id_question) REFERENCES question(id_question) ON DELETE CASCADE
);
