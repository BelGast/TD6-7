"""Génération d'un fichier PDF imprimable à partir d'un questionnaire OpenStudy."""

from contextlib import closing
import os
import sqlite3
from typing import Iterable

from src.ingestion import charger_questionnaire

# Dimensions A4 en points PDF (1 pt = 1/72 pouce)
A4_LARGEUR = 595.28
A4_HAUTEUR = 841.89
MARGE_G = 48.0
MARGE_D = 48.0
MARGE_H = 50.0
MARGE_B = 50.0
LARGEUR_UTILE = A4_LARGEUR - MARGE_G - MARGE_D


def _encoder_pdf_texte(texte: str) -> bytes:
    """Encode une chaîne en WinAnsi (cp1252) et échappe les caractères spéciaux PDF."""
    remplacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u0153": "oe",
        "\u0152": "OE",
        "\u2026": "...",
        "\u00a0": " ",
    }
    for src, dst in remplacements.items():
        texte = texte.replace(src, dst)

    brut = texte.encode("cp1252", errors="replace")
    echappe = bytearray()
    for b in brut:
        if b in (ord("\\"), ord("("), ord(")")):
            echappe.append(ord("\\"))
        echappe.append(b)
    return bytes(echappe)


def _largeur_approx(texte: str, taille: float, gras: bool = False) -> float:
    """Estime la largeur d'un texte Helvetica en points pour le retour à la ligne."""
    largeur = 0.0
    for ch in texte:
        if ch in "iIljft.,:;!'|` ":
            largeur += 0.28
        elif ch in "mwMW@%":
            largeur += 0.80
        elif ch.isupper() or ch in "—–":
            largeur += 0.68
        else:
            largeur += 0.54
    facteur = 1.07 if gras else 1.0
    return largeur * taille * facteur


def _decouper_lignes(texte: str, largeur_max: float, taille: float, gras: bool = False) -> list[str]:
    """Découpe un texte en lignes tenant dans `largeur_max`."""
    lignes = []
    for paragraphe in str(texte).splitlines() or [""]:
        mots = paragraphe.split()
        if not mots:
            lignes.append("")
            continue
        courante = mots[0]
        for mot in mots[1:]:
            test = f"{courante} {mot}"
            if _largeur_approx(test, taille, gras=gras) <= largeur_max:
                courante = test
            else:
                lignes.append(courante)
                courante = mot
        lignes.append(courante)
    return lignes


def _formater_nombre(val) -> str:
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


def charger_questionnaire_depuis_db(id_questionnaire: int, db_path: str = "data/plateforme.db") -> dict:
    """
    Charge la définition d'un questionnaire depuis SQLite sous le même format
    dictionnaire que `charger_questionnaire` (JSON).
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"La base de données '{db_path}' est introuvable.")

    with closing(sqlite3.connect(db_path)) as conn:
        row_q = conn.execute(
            """
            SELECT titre, date_creation
            FROM questionnaire
            WHERE id_questionnaire = ?
            """,
            (id_questionnaire,),
        ).fetchone()

        if row_q is None:
            raise ValueError(f"Aucun questionnaire trouvé en base avec l'ID {id_questionnaire}.")

        titre, date_creation = row_q
        rows_questions = conn.execute(
            """
            SELECT id_question, libellé, type, min, max, pondération, inversé
            FROM question
            WHERE id_questionnaire = ?
            ORDER BY id_question ASC
            """,
            (id_questionnaire,),
        ).fetchall()

        if not rows_questions:
            raise ValueError(f"Le questionnaire ID {id_questionnaire} ne contient aucune question.")

        questions = {}
        for idx, (id_q, libelle, type_q, q_min, q_max, ponderation, inverse) in enumerate(rows_questions, start=1):
            cle = f"q{idx}"
            def_q = {
                "libellé": libelle,
                "type": type_q,
                "pondération": ponderation,
                "inversé": bool(inverse),
            }
            if type_q == "numerique":
                def_q["intervalle"] = [q_min, q_max]
            elif type_q == "choix_multiple":
                rows_vals = conn.execute(
                    """
                    SELECT valeur_libellé, valeur_score
                    FROM question_valeur
                    WHERE id_question = ?
                    ORDER BY rowid ASC
                    """,
                    (id_q,),
                ).fetchall()
                def_q["réponses_possibles"] = {lib: score for lib, score in rows_vals}

            questions[cle] = def_q

    return {
        "titre": titre,
        "version": f"BDD #{id_questionnaire} ({date_creation[:10]})",
        "questions": questions,
    }


class _ConstructeurPDF:
    """Assemble des pages vectorielles et textuelles au format PDF 1.4 sans dépendance externe."""

    def __init__(self) -> None:
        self.pages: list[list[bytes]] = []
        self.courante: list[bytes] = []
        self.nouvelle_page()

    def nouvelle_page(self) -> None:
        self.courante = []
        self.pages.append(self.courante)

    def texte(self, x: float, y: float, contenu: str, taille: float = 11.0, gras: bool = False, gris: float = 0.0) -> None:
        police = "F2" if gras else "F1"
        brut = _encoder_pdf_texte(contenu)
        cmd = (
            f"BT {gris:.2f} g /{police} {taille:.2f} Tf "
            f"1 0 0 1 {x:.2f} {y:.2f} Tm (".encode("ascii")
            + brut
            + b") Tj ET"
        )
        self.courante.append(cmd)

    def ligne(self, x1: float, y1: float, x2: float, y2: float, epaisseur: float = 0.7, gris: float = 0.3) -> None:
        self.courante.append(
            f"q {gris:.2f} G {epaisseur:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q".encode("ascii")
        )

    def rectangle(self, x: float, y: float, w: float, h: float, epaisseur: float = 0.8, gris: float = 0.2, fond: float | None = None) -> None:
        if fond is not None:
            cmd = f"q {gris:.2f} G {fond:.2f} g {epaisseur:.2f} w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re B Q"
        else:
            cmd = f"q {gris:.2f} G {epaisseur:.2f} w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S Q"
        self.courante.append(cmd.encode("ascii"))

    def compiler(self) -> bytes:
        """Génère le binaire complet d'un document PDF 1.4 avec table xref valide."""
        objets: list[bytes] = []

        # 1: Catalog, 2: Pages, 3: F1 Helvetica, 4: F2 Helvetica-Bold
        objets.append(b"")  # placeholder 1 (Catalog)
        objets.append(b"")  # placeholder 2 (Pages)
        objets.append(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        )
        objets.append(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        )

        page_ids = []
        for cmds in self.pages:
            stream_data = b"\n".join(cmds)
            stream_obj_id = len(objets) + 1
            objets.append(
                f"<< /Length {len(stream_data)} >>\nstream\n".encode("ascii")
                + stream_data
                + b"\nendstream"
            )
            page_obj_id = len(objets) + 1
            page_ids.append(page_obj_id)
            objets.append(
                (
                    f"<< /Type /Page /Parent 2 0 R "
                    f"/MediaBox [0 0 {A4_LARGEUR:.2f} {A4_HAUTEUR:.2f}] "
                    f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                    f"/Contents {stream_obj_id} 0 R >>"
                ).encode("ascii")
            )

        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objets[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objets[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

        buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for idx, contenu in enumerate(objets, start=1):
            offsets.append(len(buf))
            buf.extend(f"{idx} 0 obj\n".encode("ascii"))
            buf.extend(contenu)
            buf.extend(b"\nendobj\n")

        xref_pos = len(buf)
        buf.extend(f"xref\n0 {len(objets) + 1}\n".encode("ascii"))
        buf.extend(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            buf.extend(f"{off:010d} 00000 n \n".encode("ascii"))

        buf.extend(
            (
                f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_pos}\n%%EOF\n"
            ).encode("ascii")
        )
        return bytes(buf)


def generer_pdf_questionnaire(questionnaire: dict, output_path: str) -> str:
    """
    Génère un fichier PDF prêt à imprimer pour un questionnaire donné.

    Entrées :
        questionnaire : dictionnaire conforme à la structure OpenStudy
            ('titre', 'version', 'questions').
        output_path : chemin du fichier PDF à créer.

    Sorties :
        Chemin du fichier PDF créé.
    """
    titre = questionnaire["titre"]
    version = questionnaire.get("version", "")
    questions = questionnaire["questions"]

    dossier_sortie = os.path.dirname(output_path)
    if dossier_sortie:
        os.makedirs(dossier_sortie, exist_ok=True)

    pdf = _ConstructeurPDF()
    y = A4_HAUTEUR - MARGE_H

    def saut_si_necessaire(hauteur_requise: float) -> None:
        nonlocal y
        if y - hauteur_requise < MARGE_B + 22:
            pdf.nouvelle_page()
            y = A4_HAUTEUR - MARGE_H

    # --- En-tête du document ---
    lignes_titre = _decouper_lignes(titre, LARGEUR_UTILE, taille=16.0, gras=True)
    for lt in lignes_titre:
        pdf.texte(MARGE_G, y, lt, taille=16.0, gras=True)
        y -= 20.0

    sous_titre = f"OpenStudy — Version : {version}" if version else "OpenStudy"
    pdf.texte(MARGE_G, y, sous_titre, taille=9.5, gris=0.35)
    y -= 14.0
    pdf.texte(
        MARGE_G,
        y,
        "Merci de remplir ce questionnaire lisiblement au stylo (une seule case par question à choix multiple).",
        taille=9.5,
        gris=0.25,
    )
    y -= 10.0
    pdf.ligne(MARGE_G, y, A4_LARGEUR - MARGE_D, y, epaisseur=1.0, gris=0.2)
    y -= 18.0

    # --- Section Informations du participant ---
    hauteur_bloc_info = 104.0
    pdf.rectangle(MARGE_G, y - hauteur_bloc_info, LARGEUR_UTILE, hauteur_bloc_info, epaisseur=0.7, gris=0.45, fond=0.97)
    y_info = y - 16.0
    pdf.texte(MARGE_G + 10, y_info, "Informations du participant", taille=11.0, gras=True)

    y_info -= 22.0
    pdf.texte(MARGE_G + 10, y_info, "Nom :", taille=10.0, gras=True)
    pdf.ligne(MARGE_G + 46, y_info - 2, MARGE_G + 235, y_info - 2, epaisseur=0.6, gris=0.4)
    pdf.texte(MARGE_G + 255, y_info, "Prénom :", taille=10.0, gras=True)
    pdf.ligne(MARGE_G + 306, y_info - 2, A4_LARGEUR - MARGE_D - 12, y_info - 2, epaisseur=0.6, gris=0.4)

    y_info -= 24.0
    pdf.texte(MARGE_G + 10, y_info, "Âge :", taille=10.0, gras=True)
    pdf.ligne(MARGE_G + 42, y_info - 2, MARGE_G + 100, y_info - 2, epaisseur=0.6, gris=0.4)
    pdf.texte(MARGE_G + 125, y_info, "Sexe :", taille=10.0, gras=True)
    x_sexe = MARGE_G + 165
    for opt_sexe in ("F", "M", "Autre :"):
        pdf.rectangle(x_sexe, y_info - 1, 9, 9, epaisseur=0.7, gris=0.2)
        pdf.texte(x_sexe + 14, y_info, opt_sexe, taille=10.0)
        x_sexe += 52 if opt_sexe != "Autre :" else 60
    pdf.ligne(x_sexe - 12, y_info - 2, A4_LARGEUR - MARGE_D - 12, y_info - 2, epaisseur=0.6, gris=0.4)

    y_info -= 24.0
    pdf.texte(MARGE_G + 10, y_info, "Email :", taille=10.0, gras=True)
    pdf.ligne(MARGE_G + 52, y_info - 2, A4_LARGEUR - MARGE_D - 12, y_info - 2, epaisseur=0.6, gris=0.4)

    y -= hauteur_bloc_info + 22.0

    # --- Questions ---
    pdf.texte(MARGE_G, y, "Questions", taille=12.5, gras=True)
    y -= 18.0

    for num_q, (_, def_q) in enumerate(questions.items(), start=1):
        enonce = f"{num_q}. {def_q['libellé']}"
        lignes_enonce = _decouper_lignes(enonce, LARGEUR_UTILE, taille=10.5, gras=True)
        type_q = def_q["type"]

        # Estimation de la hauteur du bloc question pour éviter de le couper sur 2 pages
        hauteur_bloc = len(lignes_enonce) * 14.0 + 10.0
        if type_q == "numerique":
            hauteur_bloc += 24.0
        elif type_q == "choix_multiple":
            options = list(def_q.get("réponses_possibles", {}).keys())
            for opt in options:
                lignes_opt = _decouper_lignes(opt, LARGEUR_UTILE - 34, taille=10.0)
                hauteur_bloc += max(1, len(lignes_opt)) * 14.0 + 3.0

        saut_si_necessaire(hauteur_bloc + 8.0)

        for le in lignes_enonce:
            pdf.texte(MARGE_G, y, le, taille=10.5, gras=True)
            y -= 14.0

        y -= 2.0
        if type_q == "numerique":
            min_v, max_v = def_q.get("intervalle", [None, None])
            if min_v is not None and max_v is not None:
                indication = f"Réponse (valeur entre {_formater_nombre(min_v)} et {_formater_nombre(max_v)}) :"
            else:
                indication = "Réponse numérique :"
            pdf.texte(MARGE_G + 14, y, indication, taille=10.0, gris=0.2)
            x_boite = MARGE_G + 14 + _largeur_approx(indication, 10.0) + 10.0
            x_boite = min(x_boite, A4_LARGEUR - MARGE_D - 95)
            pdf.rectangle(x_boite, y - 4, 85, 16, epaisseur=0.7, gris=0.35)
            y -= 22.0

        elif type_q == "choix_multiple":
            for opt in def_q.get("réponses_possibles", {}):
                lignes_opt = _decouper_lignes(opt, LARGEUR_UTILE - 34, taille=10.0)
                pdf.rectangle(MARGE_G + 14, y - 1, 9.5, 9.5, epaisseur=0.75, gris=0.15)
                for idx_l, lo in enumerate(lignes_opt):
                    pdf.texte(MARGE_G + 30, y, lo, taille=10.0)
                    y -= 14.0
                y -= 2.0

        y -= 8.0
        pdf.ligne(MARGE_G, y + 3, A4_LARGEUR - MARGE_D, y + 3, epaisseur=0.35, gris=0.82)
        y -= 8.0

    # --- Zone de commentaire libre ---
    hauteur_commentaire = 78.0
    saut_si_necessaire(hauteur_commentaire + 10.0)
    pdf.texte(MARGE_G, y, "Commentaire (facultatif) :", taille=10.5, gras=True)
    y -= 8.0
    pdf.rectangle(MARGE_G, y - 58, LARGEUR_UTILE, 58, epaisseur=0.7, gris=0.4)
    for dy in (19, 38):
        pdf.ligne(MARGE_G + 8, y - dy, A4_LARGEUR - MARGE_D - 8, y - dy, epaisseur=0.35, gris=0.75)

    # --- Pieds de page numérotés ---
    total_pages = len(pdf.pages)
    titre_court = titre if len(titre) <= 65 else titre[:62] + "..."
    for idx_page, cmds in enumerate(pdf.pages, start=1):
        pdf.courante = cmds
        y_pied = 26.0
        pdf.ligne(MARGE_G, y_pied + 10, A4_LARGEUR - MARGE_D, y_pied + 10, epaisseur=0.4, gris=0.75)
        pdf.texte(MARGE_G, y_pied, titre_court, taille=8.5, gris=0.45)
        mention_page = f"Page {idx_page} / {total_pages}"
        x_page = A4_LARGEUR - MARGE_D - _largeur_approx(mention_page, 8.5)
        pdf.texte(x_page, y_pied, mention_page, taille=8.5, gris=0.45)

    donnees_pdf = pdf.compiler()
    with open(output_path, "wb") as f:
        f.write(donnees_pdf)

    return output_path


def generer_pdf_depuis_json(json_path: str, output_path: str) -> str:
    """Charge un questionnaire JSON et génère le PDF imprimable correspondant."""
    questionnaire = charger_questionnaire(json_path)
    return generer_pdf_questionnaire(questionnaire, output_path)


def generer_pdf_depuis_db(
    id_questionnaire: int,
    output_path: str,
    db_path: str = "data/plateforme.db",
) -> str:
    """Charge un questionnaire depuis SQLite par son ID et génère le PDF imprimable."""
    questionnaire = charger_questionnaire_depuis_db(id_questionnaire, db_path=db_path)
    return generer_pdf_questionnaire(questionnaire, output_path)
