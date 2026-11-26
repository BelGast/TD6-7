"""
Outil interactif de création de questionnaires en ligne de commande.

Format JSON compatible avec la structure utilisée dans les TD précédents :
{
    "titre": "...",
    "version": "1.0",
    "questions": {
        "identifiant_question": {
            "libellé": "...",
            "type": "numerique" | "choix_multiple",
            "pondération": 1.0,
            "inversé": false,
            ...
        }
    }
}

Sauvegarde possible en JSON ou dans MySQL.
Pour MySQL, installer mysql-connector-python et définir les variables :
MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE.
"""

import json
import os
import re
import sys
from pathlib import Path


def demander_texte(message, valeur_defaut=None):
    while True:
        suffixe = f" [{valeur_defaut}]" if valeur_defaut is not None else ""
        valeur = input(f"{message}{suffixe} : ").strip()
        if valeur:
            return valeur
        if valeur_defaut is not None:
            return valeur_defaut
        print("Ce champ est obligatoire.")


def demander_nombre(message, minimum=None, maximum=None, defaut=None):
    while True:
        suffixe = f" [{defaut}]" if defaut is not None else ""
        valeur = input(f"{message}{suffixe} : ").strip()
        if not valeur and defaut is not None:
            return float(defaut)
        try:
            nombre = float(valeur.replace(",", "."))
            if minimum is not None and nombre < minimum:
                print(f"La valeur doit être supérieure ou égale à {minimum}.")
                continue
            if maximum is not None and nombre > maximum:
                print(f"La valeur doit être inférieure ou égale à {maximum}.")
                continue
            return nombre
        except ValueError:
            print("Veuillez saisir un nombre valide.")


def demander_oui_non(message, defaut=False):
    indication = "O/n" if defaut else "o/N"
    while True:
        valeur = input(f"{message} ({indication}) : ").strip().lower()
        if not valeur:
            return defaut
        if valeur in ("o", "oui", "y", "yes"):
            return True
        if valeur in ("n", "non", "no"):
            return False
        print("Répondez par o ou n.")


def creer_identifiant(libelle, numero, identifiants):
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", libelle.lower()).strip("_")
    if not base:
        base = f"question_{numero}"
    if base[0].isdigit():
        base = f"q_{base}"
    identifiant = base
    compteur = 2
    while identifiant in identifiants:
        identifiant = f"{base}_{compteur}"
        compteur += 1
    return identifiant


def creer_question(numero, identifiants):
    print(f"\n--- Question {numero} ---")
    libelle = demander_texte("Libellé de la question")
    identifiant_suggere = creer_identifiant(libelle, numero, identifiants)
    identifiant = demander_texte("Identifiant technique", identifiant_suggere)

    while identifiant in identifiants:
        print("Cet identifiant existe déjà. Choisissez-en un autre.")
        identifiant = demander_texte("Identifiant technique")

    print("\nType de question :")
    print("1. Numérique (une valeur comprise dans un intervalle)")
    print("2. Choix multiple (une réponse parmi plusieurs propositions)")
    while True:
        choix = input("Votre choix (1/2) : ").strip()
        if choix in ("1", "2"):
            break
        print("Choisissez 1 ou 2.")

    question = {
        "libellé": libelle,
        "type": "numerique" if choix == "1" else "choix_multiple",
    }

    if choix == "1":
        minimum = demander_nombre("Valeur minimale")
        maximum = demander_nombre("Valeur maximale", minimum=minimum)
        question["intervalle"] = [minimum, maximum]
    else:
        reponses = {}
        print("\nSaisissez les propositions de réponse et leur score.")
        print("Exemple : Jamais = 0 ; Souvent = 3.")
        while True:
            libelle_reponse = demander_texte("Libellé de la réponse")
            while libelle_reponse in reponses:
                print("Cette proposition existe déjà.")
                libelle_reponse = demander_texte("Libellé de la réponse")
            score = demander_nombre(f"Score associé à « {libelle_reponse} »")
            reponses[libelle_reponse] = score
            if not demander_oui_non("Ajouter une autre proposition ?", defaut=True):
                break
        question["réponses_possibles"] = reponses

    question["pondération"] = demander_nombre("Pondération", minimum=0, defaut=1)
    question["inversé"] = demander_oui_non("La question est-elle inversée ?", defaut=False)
    identifiants.add(identifiant)
    return identifiant, question


def creer_questionnaire():
    print("\n" + "=" * 52)
    print("          CRÉATION D'UN QUESTIONNAIRE")
    print("=" * 52)

    titre = demander_texte("Titre du questionnaire")
    version = demander_texte("Version", "1.0")
    questions = {}
    identifiants = set()

    while True:
        if not demander_oui_non("\nSouhaitez-vous ajouter une question ?", defaut=not questions):
            if not questions:
                print("Un questionnaire doit contenir au moins une question.")
                continue
            break
        identifiant, question = creer_question(len(questions) + 1, identifiants)
        questions[identifiant] = question
        print(f"\nQuestion « {identifiant} » ajoutée.")

    return {
        "titre": titre,
        "version": version,
        "questions": questions,
    }


def valider_questionnaire(questionnaire):
    if not isinstance(questionnaire, dict):
        raise ValueError("Le questionnaire doit être un dictionnaire.")
    for cle in ("titre", "version", "questions"):
        if cle not in questionnaire:
            raise ValueError(f"Clé obligatoire manquante : {cle}.")
    if not isinstance(questionnaire["titre"], str) or not questionnaire["titre"].strip():
        raise ValueError("Le titre doit être une chaîne non vide.")
    if not isinstance(questionnaire["version"], str) or not questionnaire["version"].strip():
        raise ValueError("La version doit être une chaîne non vide.")
    questions = questionnaire["questions"]
    if not isinstance(questions, dict) or not questions:
        raise ValueError("Le questionnaire doit contenir au moins une question.")

    for identifiant, question in questions.items():
        if not isinstance(question, dict):
            raise ValueError(f"La question {identifiant} doit être un dictionnaire.")
        for champ in ("libellé", "type", "pondération"):
            if champ not in question:
                raise ValueError(f"La question {identifiant} ne contient pas « {champ} ».")
        if not isinstance(question["libellé"], str) or not question["libellé"].strip():
            raise ValueError(f"Le libellé de {identifiant} est vide.")
        if isinstance(question["pondération"], bool) or not isinstance(question["pondération"], (int, float)):
            raise ValueError(f"La pondération de {identifiant} doit être numérique.")
        if question["pondération"] < 0:
            raise ValueError(f"La pondération de {identifiant} ne peut pas être négative.")
        if "inversé" in question and not isinstance(question["inversé"], bool):
            raise ValueError(f"Le champ « inversé » de {identifiant} doit être booléen.")

        if question["type"] == "numerique":
            intervalle = question.get("intervalle")
            if (
                not isinstance(intervalle, list)
                or len(intervalle) != 2
                or any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in intervalle)
                or intervalle[0] > intervalle[1]
            ):
                raise ValueError(f"Intervalle invalide pour la question {identifiant}.")
        elif question["type"] == "choix_multiple":
            reponses = question.get("réponses_possibles")
            if not isinstance(reponses, dict) or not reponses:
                raise ValueError(f"Les réponses possibles de {identifiant} sont absentes ou invalides.")
            for libelle, score in reponses.items():
                if not isinstance(libelle, str) or not libelle.strip():
                    raise ValueError(f"Libellé de réponse invalide dans {identifiant}.")
                if isinstance(score, bool) or not isinstance(score, (int, float)):
                    raise ValueError(f"Le score de « {libelle} » doit être numérique.")
        else:
            raise ValueError(
                f"Type inconnu pour {identifiant} : {question['type']}. "
                "Types acceptés : numerique, choix_multiple."
            )
    return True


def sauvegarder_json(questionnaire):
    dossier = Path("data")
    dossier.mkdir(exist_ok=True)
    nom_defaut = re.sub(r"[^a-zA-Z0-9_-]+", "_", questionnaire["titre"]).strip("_").lower()
    chemin = demander_texte("Chemin du fichier JSON", str(dossier / f"{nom_defaut or 'questionnaire'}.json"))
    destination = Path(chemin)
    if destination.suffix.lower() != ".json":
        destination = destination.with_suffix(".json")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", encoding="utf-8") as fichier:
        json.dump(questionnaire, fichier, ensure_ascii=False, indent=2)
        fichier.write("\n")
    print(f"\nQuestionnaire sauvegardé dans : {destination}")
    return destination


def sauvegarder_mysql(questionnaire):
    try:
        import mysql.connector
        from mysql.connector import Error
    except ImportError as exc:
        raise RuntimeError(
            "Le connecteur MySQL n'est pas installé. Exécutez : "
            "python -m pip install mysql-connector-python"
        ) from exc

    configuration = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER") or demander_texte("Utilisateur MySQL"),
        "password": os.getenv("MYSQL_PASSWORD") or input("Mot de passe MySQL : "),
        "database": os.getenv("MYSQL_DATABASE") or demander_texte("Nom de la base de données"),
    }

    connexion = None
    curseur = None
    try:
        connexion = mysql.connector.connect(**configuration)
        curseur = connexion.cursor()
        curseur.execute(
            """
            CREATE TABLE IF NOT EXISTS questionnaires (
                id INT AUTO_INCREMENT PRIMARY KEY,
                titre VARCHAR(255) NOT NULL,
                version VARCHAR(50) NOT NULL,
                definition JSON NOT NULL,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        curseur.execute(
            """
            INSERT INTO questionnaires (titre, version, definition)
            VALUES (%s, %s, %s)
            """,
            (
                questionnaire["titre"],
                questionnaire["version"],
                json.dumps(questionnaire, ensure_ascii=False),
            ),
        )
        connexion.commit()
        identifiant = curseur.lastrowid
        print(f"\nQuestionnaire enregistré dans MySQL. Identifiant : {identifiant}")
        print("Table utilisée : questionnaires (colonne definition au format JSON).")
        return identifiant
    except Error as exc:
        if connexion and connexion.is_connected():
            connexion.rollback()
        raise RuntimeError(f"Échec de l'enregistrement MySQL : {exc}") from exc
    finally:
        if curseur is not None:
            curseur.close()
        if connexion is not None and connexion.is_connected():
            connexion.close()


def main():
    try:
        questionnaire = creer_questionnaire()
        valider_questionnaire(questionnaire)

        print("\n" + "=" * 52)
        print("          RÉCAPITULATIF DU QUESTIONNAIRE")
        print("=" * 52)
        print(f"Titre : {questionnaire['titre']}")
        print(f"Version : {questionnaire['version']}")
        print(f"Nombre de questions : {len(questionnaire['questions'])}")
        for identifiant, question in questionnaire["questions"].items():
            print(f"- {identifiant} [{question['type']}] : {question['libellé']}")

        print("\nMode de sauvegarde :")
        print("1. Fichier JSON")
        print("2. Base de données MySQL")
        while True:
            choix = input("Votre choix (1/2) : ").strip()
            if choix == "1":
                sauvegarder_json(questionnaire)
                break
            if choix == "2":
                sauvegarder_mysql(questionnaire)
                break
            print("Choisissez 1 ou 2.")

    except (KeyboardInterrupt, EOFError):
        print("\nCréation interrompue.")
        sys.exit(1)
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"\nErreur : {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
