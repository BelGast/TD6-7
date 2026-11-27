# AGENTS.md — Consignes pour les agents de code (OpenStudy / TD6-7)

## Contexte du dépôt
Dépôt collaboratif du projet **OpenStudy** (gestion, passation, export et analyse de questionnaires).
Chaque fonctionnalité est développée sur une branche dédiée puis relue avant fusion dans `main` (voir `aRendre.md`).

## Conventions techniques
- **Langage** : Python 3.11+ (privilégier la bibliothèque standard pour fonctionner sans dépendances externes).
- **Encodage** : UTF-8 pour tous les fichiers source, JSON et SQL (WinAnsi / `cp1252` géré côté génération PDF pour les accents français).
- **SQLite** : toujours activer `PRAGMA foreign_keys = ON;` et fermer explicitement les connexions (`contextlib.closing`) pour éviter les verrous de fichiers sous Windows.
- **Structure minimale attendue** :
  - `conception/schema.sql` : schéma relationnel SQLite (`utilisateur`, `questionnaire`, `question`, `valeur`, `question_valeur`, `participant`, `repond`).
  - `src/ingestion.py` : chargement et validation des questionnaires JSON (`charger_questionnaire`) et réponses CSV/XLSX.
  - `src/pdf_questionnaire.py` & `generer_pdf.py` : génération de questionnaires PDF imprimables depuis un JSON ou un `id_questionnaire` en base SQLite.
  - `data/sommeil.json` : jeu de définition de questionnaire de référence.
  - `tests/` : tests unitaires et d'intégration (`unittest`).

## Commandes de vérification
Avant tout commit ou Pull Request, exécuter depuis la racine du dépôt :
```bash
python -m unittest discover -s tests -v
```
Exemple d'exécution de l'outil PDF :
```bash
python generer_pdf.py --json data/sommeil.json -o sommeil_papier.pdf
python generer_pdf.py --id 1 -o questionnaire_1_papier.pdf
```
