import csv
import json
import os
import zipfile
import xml.etree.ElementTree as ET


def _convertir_valeur(valeur_brute: str):
    """Convertit une chaîne numérique en int ou float, ou renvoie la chaîne telle quelle."""
    texte = valeur_brute.strip()
    if texte == "":
        return None
    try:
        if "." not in texte and "," not in texte and "e" not in texte.lower():
            return int(texte)
        return float(texte.replace(",", "."))
    except ValueError:
        return valeur_brute


def _lire_csv(rep_file: str) -> tuple[list[str], list[dict]]:
    """Lit un fichier CSV avec la bibliothèque standard en détectant le séparateur."""
    with open(rep_file, "r", encoding="utf-8-sig", newline="") as f:
        echantillon = f.read(4096)
        if not echantillon.strip():
            raise ValueError(f"Le fichier '{rep_file}' ne contient aucune donnée.")
        f.seek(0)
        try:
            dialecte = csv.Sniffer().sniff(echantillon, delimiters=",;\t")
            separateur = dialecte.delimiter
        except csv.Error:
            premiere_ligne = echantillon.splitlines()[0]
            separateur = ";" if ";" in premiere_ligne and "," not in premiere_ligne else ","

        lecteur = csv.DictReader(f, delimiter=separateur)
        if not lecteur.fieldnames:
            raise ValueError(f"Le fichier '{rep_file}' ne contient aucune donnée.")
        colonnes = [c.strip() for c in lecteur.fieldnames if c is not None]
        lignes = []
        for row in lecteur:
            ligne_propre = {
                k.strip(): v for k, v in row.items() if k is not None
            }
            if any(v is not None and str(v).strip() != "" for v in ligne_propre.values()):
                lignes.append(ligne_propre)
        return colonnes, lignes


def _lire_xlsx_stdlib(rep_file: str) -> tuple[list[str], list[dict]]:
    """Lit un fichier .xlsx sans dépendance externe via zipfile et ElementTree."""
    ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    with zipfile.ZipFile(rep_file) as z:
        shared_strings = []
        if "xl/sharedStrings.xml" in z.namelist():
            ss_root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared_strings = ["".join(si.itertext()) for si in ss_root]

        wb_root = ET.fromstring(z.read("xl/workbook.xml"))
        rels_root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in rels_root}

        premiere_feuille = wb_root.find(".//m:sheet", ns)
        if premiere_feuille is None:
            raise ValueError(f"Le fichier '{rep_file}' ne contient aucune feuille.")

        rid = premiere_feuille.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = rels[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = f"xl/{target}"

        sheet_root = ET.fromstring(z.read(target))
        rows_raw = []
        for row in sheet_root.findall(".//m:row", ns):
            vals = {}
            for col_idx, cell in enumerate(row.findall("m:c", ns)):
                ref = cell.attrib.get("r", "")
                lettres = "".join(ch for ch in ref if ch.isalpha())
                if lettres:
                    idx = 0
                    for ch in lettres.upper():
                        idx = idx * 26 + (ord(ch) - ord("A") + 1)
                    idx -= 1
                else:
                    idx = col_idx

                cell_type = cell.attrib.get("t")
                v_el = cell.find("m:v", ns)
                is_el = cell.find("m:is", ns)
                if v_el is not None and v_el.text is not None:
                    if cell_type == "s":
                        val = shared_strings[int(v_el.text)]
                    elif cell_type == "b":
                        val = v_el.text == "1"
                    else:
                        num = float(v_el.text)
                        val = int(num) if num.is_integer() else num
                elif is_el is not None:
                    val = "".join(is_el.itertext())
                else:
                    val = None
                vals[idx] = val
            if any(v is not None and str(v).strip() != "" for v in vals.values()):
                max_col = max(vals.keys()) + 1
                rows_raw.append([vals.get(i) for i in range(max_col)])

        if len(rows_raw) < 1:
            raise ValueError(f"Le fichier '{rep_file}' ne contient aucune donnée.")

        colonnes = [str(c).strip() if c is not None else f"col_{i}" for i, c in enumerate(rows_raw[0])]
        lignes = []
        for raw in rows_raw[1:]:
            d = {}
            for i, col in enumerate(colonnes):
                d[col] = raw[i] if i < len(raw) else None
            if any(v is not None and str(v).strip() != "" for v in d.values()):
                lignes.append(d)
        return colonnes, lignes


def charger_questionnaire(jsonfile: str) -> dict:
    """
    Charge et valide la définition d'un questionnaire à partir d'un fichier JSON.

    Entrées :
        jsonfile : chaîne de caractères représentant le chemin vers le fichier
            JSON contenant la définition du questionnaire.

    Sorties :
        Un dictionnaire Python représentant la structure et le contenu du
        questionnaire si celui-ci est valide.

    Conditions d'application :
        Le fichier spécifié par `jsonfile` doit exister, être un fichier valide,
        contenir un JSON syntaxiquement correct, et respecter scrupuleusement
        la structure attendue d'un questionnaire (titre, version, questions,
        ainsi que les attributs spécifiques aux types "numerique" et "choix_multiple").

    Erreurs levées :
        FileNotFoundError : si le fichier n'existe pas.
        IsADirectoryError : si le chemin correspond à un dossier.
        ValueError : si le fichier est vide, contient un JSON invalide,
            ou si la structure du questionnaire est incorrecte (clés manquantes,
            types de données erronés, types de questions non gérés, etc.).
    """
    if not os.path.exists(jsonfile):
        raise FileNotFoundError(f"Le fichier '{jsonfile}' est introuvable.")

    if not os.path.isfile(jsonfile):
        raise IsADirectoryError(f"Le chemin '{jsonfile}' correspond à un dossier, pas à un fichier.")

    try:
        with open(jsonfile, "r", encoding="utf-8") as f:
            contenu = f.read()
            if not contenu.strip():
                raise ValueError(f"Le fichier '{jsonfile}' est vide.")
            questionnaire = json.loads(contenu)
    except json.JSONDecodeError as e:
        raise ValueError(f"Le fichier '{jsonfile}' ne contient pas un JSON valide : {e}")

    # --- Vérification de la structure du questionnaire ---
    if not isinstance(questionnaire, dict):
        raise ValueError("Le contenu du JSON doit être un dictionnaire à la racine.")

    # Vérification des clés globales obligatoires
    for cle in ("titre", "version", "questions"):
        if cle not in questionnaire:
            raise ValueError(f"Clé obligatoire manquante à la racine du questionnaire : '{cle}'.")

    if not isinstance(questionnaire["questions"], dict):
        raise ValueError("La section 'questions' doit être un dictionnaire.")

    if not questionnaire["questions"]:
        raise ValueError("Le questionnaire ne contient aucune question.")

    # Vérification de chaque question individuellement
    for q_id, def_q in questionnaire["questions"].items():
        if not isinstance(def_q, dict):
            raise ValueError(f"La définition de la question '{q_id}' doit être un dictionnaire.")

        # Vérification des champs communs
        for champ in ("libellé", "type", "pondération"):
            if champ not in def_q:
                raise ValueError(f"La question '{q_id}' manque du champ obligatoire : '{champ}'.")

        if not isinstance(def_q["pondération"], (int, float)):
            raise ValueError(f"La pondération de la question '{q_id}' doit être un nombre.")

        type_q = def_q["type"]
        if type_q == "numerique":
            if "intervalle" not in def_q:
                raise ValueError(f"La question numérique '{q_id}' doit posséder un champ 'intervalle'.")
            intervalle = def_q["intervalle"]
            if (
                not isinstance(intervalle, list)
                or len(intervalle) != 2
                or not all(isinstance(x, (int, float)) for x in intervalle)
            ):
                raise ValueError(
                    f"L'intervalle de la question '{q_id}' doit être une liste de 2 nombres [min, max]."
                )
            if intervalle[0] > intervalle[1]:
                raise ValueError(f"L'intervalle de la question '{q_id}' est invalide (min > max).")

        elif type_q == "choix_multiple":
            if "réponses_possibles" not in def_q:
                raise ValueError(
                    f"La question à choix multiple '{q_id}' doit posséder un champ 'réponses_possibles'."
                )
            rep_possibles = def_q["réponses_possibles"]
            if not isinstance(rep_possibles, dict) or not rep_possibles:
                raise ValueError(
                    f"Le champ 'réponses_possibles' de la question '{q_id}' doit être un dictionnaire non vide."
                )
            for lib_rep, score_rep in rep_possibles.items():
                if not isinstance(score_rep, (int, float)):
                    raise ValueError(
                        f"Le score associé à la réponse '{lib_rep}' dans la question '{q_id}' doit être un nombre."
                    )

        else:
            raise ValueError(
                f"Type de question inconnu '{type_q}' pour la question '{q_id}' "
                "(attendu : 'numerique' ou 'choix_multiple')."
            )

        # Vérification optionnelle du champ 'inversé' s'il est présent
        if "inversé" in def_q and not isinstance(def_q["inversé"], bool):
            raise ValueError(
                f"Le champ 'inversé' de la question '{q_id}' doit être un booléen (True/False)."
            )

    return questionnaire


def charger_reponses(rep_file: str) -> list:
    """
    Charge une liste de réponses à un questionnaire à partir d'un fichier
    au format CSV ou Excel, avec une validation de base de la structure des données.

    Entrées :
        rep_file : chaîne de caractères représentant le chemin vers le fichier
            contenant les réponses (.csv, .xlsx, .xls).

    Sorties :
        Une liste de dictionnaires, où chaque dictionnaire représente la réponse
        d'un participant structuré avec les sections 'general' et 'reponses'.

    Conditions d'application :
        Le fichier doit exister, posséder une extension supportée (.csv, .xlsx, .xls),
        contenir des données, et inclure un minimum de colonnes d'identification
        générale (ex: 'nom').

    Erreurs levées :
        FileNotFoundError : si le fichier n'existe pas.
        IsADirectoryError : si le chemin correspond à un dossier.
        ValueError : si le format n'est pas supporté, si le fichier est vide,
            ou s'il manque des colonnes essentielles de base.
    """
    if not os.path.exists(rep_file):
        raise FileNotFoundError(f"Le fichier '{rep_file}' est introuvable.")

    if not os.path.isfile(rep_file):
        raise IsADirectoryError(f"Le chemin '{rep_file}' correspond à un dossier, pas à un fichier.")

    _, extension = os.path.splitext(rep_file)
    extension = extension.lower()

    if extension == ".csv":
        try:
            colonnes, lignes = _lire_csv(rep_file)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Erreur lors de la lecture du fichier CSV '{rep_file}' : {e}")
    elif extension == ".xlsx":
        try:
            colonnes, lignes = _lire_xlsx_stdlib(rep_file)
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Erreur lors de la lecture du fichier Excel '{rep_file}' : {e}")
    elif extension == ".xls":
        try:
            import pandas as pd

            df = pd.read_excel(rep_file)
            if df.empty:
                raise ValueError(f"Le fichier '{rep_file}' ne contient aucune donnée.")
            colonnes = list(df.columns)
            lignes = [
                {
                    col: (None if pd.isna(val) else (val.item() if hasattr(val, "item") else val))
                    for col, val in row.items()
                }
                for _, row in df.iterrows()
            ]
        except ImportError:
            raise ValueError(
                "Le format '.xls' nécessite pandas et xlrd. Enregistrez le fichier en '.csv' ou '.xlsx'."
            )
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(f"Erreur lors de la lecture du fichier Excel '{rep_file}' : {e}")
    else:
        raise ValueError(f"Format de fichier non supporté : '{extension}'. Utilisez un fichier CSV ou Excel.")

    if not lignes:
        raise ValueError(f"Le fichier '{rep_file}' ne contient aucune donnée.")

    # Validation de base : s'assurer qu'au moins le champ 'nom' est présent dans les colonnes
    if "nom" not in colonnes:
        raise ValueError(f"Le fichier '{rep_file}' ne contient pas la colonne obligatoire 'nom'.")

    # Définition des champs considérés comme généraux
    champs_generaux = {"nom", "prenom", "age", "sexe", "email", "commentaire"}
    champs_texte = {"nom", "prenom", "sexe", "email", "commentaire"}

    liste_reponses = []

    for row in lignes:
        general = {}
        reponses = {}

        for col, valeur in row.items():
            if valeur is None:
                continue
            if isinstance(valeur, str):
                if not valeur.strip():
                    continue
                if col not in champs_texte:
                    valeur = _convertir_valeur(valeur)
                    if valeur is None:
                        continue

            if col in champs_generaux:
                if col == "age" and isinstance(valeur, float) and valeur.is_integer():
                    valeur = int(valeur)
                general[col] = valeur
            else:
                reponses[col] = valeur

        liste_reponses.append({"general": general, "reponses": reponses})

    return liste_reponses
