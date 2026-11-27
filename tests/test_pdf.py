from contextlib import closing
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from src.pdf_questionnaire import (
    charger_questionnaire_depuis_db,
    generer_pdf_depuis_db,
    generer_pdf_depuis_json,
    generer_pdf_questionnaire,
)


def _peupler_db_exemple(db_path: str, schema_path: str, json_path: str) -> int:
    """Initialise une base SQLite temporaire avec le schéma et un questionnaire JSON."""
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    with open(json_path, "r", encoding="utf-8") as f:
        q_data = json.load(f)

    with closing(sqlite3.connect(db_path)) as conn, conn:
        conn.executescript(schema_sql)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO utilisateur (nom, prénom, email, rôle) VALUES (?, ?, ?, ?)",
            ("test_user", "Test", "test@openstudy.local", "chercheur"),
        )
        id_user = cur.lastrowid
        cur.execute(
            "INSERT INTO questionnaire (titre, visibilité, date_creation, id_utilisateur) VALUES (?, ?, ?, ?)",
            (q_data["titre"], "public", "2026-11-27 12:00:00", id_user),
        )
        id_q = cur.lastrowid

        for def_q in q_data["questions"].values():
            q_min, q_max = def_q.get("intervalle", [None, None]) if def_q["type"] == "numerique" else (None, None)
            cur.execute(
                """
                INSERT INTO question (libellé, type, min, max, pondération, inversé, id_questionnaire)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    def_q["libellé"],
                    def_q["type"],
                    q_min,
                    q_max,
                    def_q["pondération"],
                    1 if def_q.get("inversé", False) else 0,
                    id_q,
                ),
            )
            id_question = cur.lastrowid
            if def_q["type"] == "choix_multiple":
                for lib, score in def_q["réponses_possibles"].items():
                    cur.execute("INSERT OR IGNORE INTO valeur (libellé, score) VALUES (?, ?)", (lib, float(score)))
                    cur.execute(
                        "INSERT OR IGNORE INTO question_valeur (id_question, valeur_libellé, valeur_score) VALUES (?, ?, ?)",
                        (id_question, lib, float(score)),
                    )
    return id_q


class TestGenerationPDF(unittest.TestCase):
    def test_pdf_depuis_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_json = os.path.join(tmpdir, "sommeil.pdf")
            generer_pdf_depuis_json("data/sommeil.json", pdf_json)
            self.assertTrue(os.path.exists(pdf_json))
            with open(pdf_json, "rb") as f:
                contenu = f.read()
            self.assertTrue(contenu.startswith(b"%PDF-1.4"))
            self.assertIn(b"%%EOF", contenu)
            self.assertIn(b"xref", contenu)
            self.assertIn(b"Ces deux derni", contenu)

    def test_pdf_depuis_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            id_q = _peupler_db_exemple(db_path, "conception/schema.sql", "data/sommeil.json")
            q_db = charger_questionnaire_depuis_db(id_q, db_path=db_path)
            self.assertEqual(len(q_db["questions"]), 7)

            pdf_db = os.path.join(tmpdir, "db.pdf")
            generer_pdf_depuis_db(id_q, pdf_db, db_path=db_path)
            with open(pdf_db, "rb") as f:
                contenu = f.read()
            self.assertTrue(contenu.startswith(b"%PDF-1.4"))
            self.assertIn(b"%%EOF", contenu)
            self.assertIn(b"Tous les jours", contenu)

    def test_pdf_multipages_et_erreurs(self):
        questions = {
            f"q{i}": {
                "libellé": f"Question numéro {i} avec un intitulé suffisamment long pour tester le retour à la ligne.",
                "type": "choix_multiple",
                "réponses_possibles": {"Option A": 0.0, "Option B": 0.5, "Option C": 1.0},
                "pondération": 1.0,
            }
            for i in range(1, 21)
        }
        q_long = {"titre": "Grand questionnaire de test", "version": "2.0", "questions": questions}
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_long = os.path.join(tmpdir, "long.pdf")
            generer_pdf_questionnaire(q_long, pdf_long)
            with open(pdf_long, "rb") as f:
                data = f.read()
            self.assertGreaterEqual(data.count(b"/Type /Page "), 2)

            db_path = os.path.join(tmpdir, "vide.db")
            _peupler_db_exemple(db_path, "conception/schema.sql", "data/sommeil.json")
            with self.assertRaises(ValueError):
                charger_questionnaire_depuis_db(999, db_path=db_path)

            with self.assertRaises(FileNotFoundError):
                charger_questionnaire_depuis_db(1, db_path=os.path.join(tmpdir, "absent.db"))

    def test_cli_generer_pdf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sortie = os.path.join(tmpdir, "cli.pdf")
            res = subprocess.run(
                [sys.executable, "generer_pdf.py", "--json", "data/sommeil.json", "-o", sortie],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)
            self.assertTrue(os.path.exists(sortie))


if __name__ == "__main__":
    unittest.main()
