2- Expérimentez avec un agent de code
Chaque membre du groupe collabore et encadre un agent de code pour ajouter au dépôt
collaboratif (en premier lieu dans une branche, qui sera fusionnée après vérification par un
autre membre du groupe) un des éléments suivants :
1. Un outil pour faire passer des questionnaires en ligne de commande (dans le
terminal), et donc qui prend en paramètre soit un fichier JSON de définition d’un
questionnaire, soit l'identifiant d’un questionnaire dans la base de données, pose les
questions, obtient les réponses et sauvegarde ces réponses, anonymisées, dans la
base de données ou dans un fichier JSON.
2. Un outil pour définir un questionnaire en ligne de commande (dans le terminal), et
donc qui demande successivement si une nouvelle question doit être créée, quel est
son libellé, de quel type il s’agit, quelle est sa pondération et si elle est inversée, etc.
Une fois terminé, l’utilisateur peut sauvegarder le questionnaire dans la base de
données ou sous la forme d’un fichier JSON.
3. Un script permettant de prendre un questionnaire (fichier JSON ou à partir de son
identifiant dans la base de données) et créer un fichier PDF qui permet de l’imprimer
pour être rempli sur papier.

--> je m'en occupe!

4. Un script permettant de produire un rapport, au format markdown (.md) concernant
les résultats d’un questionnaire (obtenu à partir de la base de données, d’un fichier
Excel ou d’un fichier csv), incluant une description (avec quelques statistiques) des
scores et des réponses, et l’exploration d’éventuelles relations avec l’âge et le genre.
La relecture et la fusion signifient : pousser la branche (commit/push), ouvrir une demande
de fusion (ex : pull request dans github), désigner un relecteur, ne fusionner qu’après
approbation (merge). Aussi, une fois les quatre branches fusionnées, récupérez la branche
main et vérifiez que la suite de tests passe toujours.
3- Organiser le cycle de vie, faire des revues de code
Suite au CM7, réaliser les revues de code des productions ci-dessus au sein du groupe,
ainsi que les tests d’intégration.
Rendu (un par groupe) : Envoyez avant le vendredi 27/11 18h une invitation à “mdaquin” sur
votre dépôt github ou gitlab, ou à l’adresse email “mathieu.daquin.w@gmail.com” si vous
utilisez une autre plateforme. Ce dépôt devrait avoir visible les commit réalisés, branches
créées et fusionnées. Incluez aussi les rapports de tests (au moins unitaires et d’intégration).
Assurez-vous que les agents de code utilisés aient créé et mis à jour le fichier AGENTS.md.
Incluez dans un répertoire spécial de votre dépôt les traces d’IA et placez-y les
transcriptions de vos sessions avec les agents de code (/export sur OpenCode et Claude
code).