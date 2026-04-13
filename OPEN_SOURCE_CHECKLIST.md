# Checklist avant publication / première PR publique

Utilise cette liste sur une **copie propre** du dépôt (clone frais ou `git status` vide), pas sur un dossier de dev rempli d’artefacts locaux.

## Ne jamais versionner

- [ ] Aucun fichier sous `data/` (SQLite, `antigravity_refresh_token.txt`, `output/`, `prompts/` utilisateur, etc.)
- [ ] Aucun `.env`, `.env.local`, clé `GEMINI_API_KEY`, refresh token dans le dépôt
- [ ] Aucun `node_modules/`, `.next/`, `.venv/`, `python/.venv/`, `.pytest_cache/`

Les entrées correspondantes sont dans [.gitignore](.gitignore) et [apps/web/.gitignore](apps/web/.gitignore) ; vérifie quand même avec `git status` avant le premier push.

## Configuration OAuth Antigravity (à comprendre)

- [ ] Les défauts Antigravity (`client_id` / `client_secret` / `project_id`) sont les **mêmes constantes desktop publiques** que [opencode-antigravity-auth](https://github.com/NoeFabris/opencode-antigravity-auth), stockées en **hex** dans le code pour la *push protection* GitHub — pas des équivalents de `GEMINI_API_KEY` ou d’un refresh token.
- [ ] Les **vrais secrets** à protéger restent : refresh tokens, clés API, contenu de `data/`, fichiers locaux d’environnement. Voir [SECURITY.md](SECURITY.md).

## Vérifications automatiques (alignées sur la CI)

**Prérequis :** Python **3.10+** localement (la CI utilise 3.11). Si `pip install -e "./python[dev]"` refuse 3.9, mets à jour Python.

À la racine du dépôt, après installation comme dans [README.md](README.md) :

```bash
python -m pip install -U pip
pip install -e "./python[dev]"
pytest python/tests -q
```

Frontend :

```bash
cd apps/web && npm ci && npm run lint && npm run build
```

## Dernière relecture

- [ ] [README.md](README.md) à jour pour un lecteur sans contexte
- [ ] [CONTRIBUTING.md](CONTRIBUTING.md) et commandes CI cohérentes
- [ ] Licence [LICENSE](LICENSE) et signalement [SECURITY.md](SECURITY.md) visibles
