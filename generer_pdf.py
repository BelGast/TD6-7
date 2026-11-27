import argparse
import os
import sys

from src.pdf_questionnaire import generer_pdf_depuis_db, generer_pdf_depuis_json


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Génère un questionnaire PDF prêt à imprimer depuis un fichier JSON ou la base SQLite."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--json",
        dest="json_path",
        help="Chemin vers le fichier JSON définissant le questionnaire.",
    )
    source.add_argument(
        "--id",
        dest="id_questionnaire",
        type=int,
        help="Identifiant du questionnaire dans la base de données SQLite.",
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        default="data/plateforme.db",
        help="Chemin vers la base SQLite (défaut : data/plateforme.db).",
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_path",
        help="Chemin du fichier PDF à générer (optionnel).",
    )

    args = parser.parse_args()

    try:
        if args.json_path:
            if args.output_path:
                sortie = args.output_path
            else:
                nom_base = os.path.splitext(os.path.basename(args.json_path))[0]
                sortie = f"{nom_base}_papier.pdf"
            chemin_cree = generer_pdf_depuis_json(args.json_path, sortie)
        else:
            sortie = args.output_path or f"questionnaire_{args.id_questionnaire}_papier.pdf"
            chemin_cree = generer_pdf_depuis_db(args.id_questionnaire, sortie, db_path=args.db_path)

        print(f"Succès : PDF généré dans '{chemin_cree}'.")
    except (FileNotFoundError, IsADirectoryError, ValueError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
