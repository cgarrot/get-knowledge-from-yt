# Security

## Signaler un problème

Si tu penses avoir trouvé une vulnérabilité de sécurité, **ne pas** ouvrir une issue publique tout de suite. Envoie plutôt un résumé et, si possible, des étapes de reproduction au mainteneur du dépôt (contact via l’onglet *Security* / *Advisories* du projet sur la forge Git, ou par message privé si un canal est indiqué dans le README).

## Ce qu’il ne faut jamais commiter

- Clés API (`GEMINI_API_KEY`, etc.) et tout jeton utilisateur (refresh token OAuth, cookies de session, etc.).
- Contenu du répertoire `data/` : base SQLite, `antigravity_refresh_token.txt`, exports sensibles sous `output/`, etc.
- Fichiers d’environnement locaux : `.env`, `apps/web/.env.local`, copies de credentials.

Ces chemins sont couverts par [.gitignore](.gitignore) ; en cas de doute avant un push, exécute `git status` et consulte [OPEN_SOURCE_CHECKLIST.md](OPEN_SOURCE_CHECKLIST.md).

## OAuth Antigravity : « secret » client vs secrets utilisateur

Le flux Antigravity utilise les **mêmes constantes OAuth publiques** (identifiant client, secret client de type application desktop, ID projet) que [opencode-antigravity-auth](https://github.com/NoeFabris/opencode-antigravity-auth) (`src/constants.ts`). Elles ne remplacent pas une authentification utilisateur. Elles ne sont **pas** committées ici : la protection anti‑secret de GitHub bloque ces chaînes même lorsqu’elles sont publiques ; configure-les en local via `ANTIGRAVITY_OAUTH_CLIENT_ID`, `ANTIGRAVITY_OAUTH_CLIENT_SECRET`, `ANTIGRAVITY_PROJECT_ID` (voir README).

Les **secrets à traiter comme confidentiels** restent :

- le **refresh token** obtenu après connexion (fichier sous `data/`, variable `ANTIGRAVITY_REFRESH_TOKEN`, ou fichier OpenCode sur la machine) ;
- toute **clé API** Gemini ou autre ;
- tout artefact runtime contenant des données personnelles ou des jetons.

En cas de fuite accidentelle d’un refresh token ou d’une clé API dans l’historique Git, révoque le jeton ou la clé côté fournisseur et fais pivoter les identifiants ; ne compte pas sur un simple revert pour effacer l’exposition dans l’historique public.
