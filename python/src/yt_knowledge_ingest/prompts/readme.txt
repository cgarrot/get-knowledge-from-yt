Ce répertoire contient normalement des fichiers *.md (un prompt = un fichier <nom>.md).

Les fichiers *.md sont ignorés par Git (voir .gitignore dans ce dossier) pour que tu puisses garder tes prompts privés.

Comportement sans fichiers .md ici :
- « default » et « game-theory » sont fournis par le code Python (même contenu qu’avant).
- Tu peux toujours ajouter localement default.md, game-theory.md ou d’autres noms ; s’ils existent, ils remplacent le repli du code pour ce nom.

Si ces fichiers étaient déjà suivis par Git avant l’ajout du .gitignore, retire-les de l’index une fois :
  git rm --cached python/src/yt_knowledge_ingest/prompts/*.md

Les overrides utilisateur de l’API restent sous data/prompts/ (déjà ignoré via data/ à la racine).
