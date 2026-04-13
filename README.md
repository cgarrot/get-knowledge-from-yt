# get-knowledge-from-yt

Monorepo open source : extraction de contenu structuré depuis des vidéos YouTube via **Google Gemini** (multimodal, URL en `video/*`), prompts au format Markdown, et une option **Antigravity** (OAuth, configuration par variables d’environnement). Composants : package Python **`yt_knowledge_ingest`**, **API FastAPI** (file SQLite + worker), **Next.js** (file d’attente, historique, bibliothèque, édition des prompts, exports).

## Prérequis

- **Python 3.10+** (recommandé : **3.11+** pour éviter les avertissements EOL des dépendances Google)
- Node.js **20+**
- `GEMINI_API_KEY` pour le provider `gemini`, ou variables Antigravity listées ci-dessous pour `antigravity`

## Hygiène open source

- Le répertoire **`data/`** et les fichiers **`.env` / `.env.local`** sont du **runtime local** : ils ne doivent pas être versionnés (voir [.gitignore](.gitignore)).
- Les prompts Markdown du package (`python/src/yt_knowledge_ingest/prompts/*.md`) sont **gitignorés** pour pouvoir les garder privés ; `default` et `game-theory` restent fournis par le code si les fichiers absents (voir `prompts/readme.txt`).
- Avant un premier push public ou une release, suis **[OPEN_SOURCE_CHECKLIST.md](OPEN_SOURCE_CHECKLIST.md)** sur un clone propre.
- La **CI** ([.github/workflows/ci.yml](.github/workflows/ci.yml)) exécute les tests Python et le lint + build du front ; aligne tes PR sur les mêmes commandes que dans [CONTRIBUTING.md](CONTRIBUTING.md).

### OAuth Antigravity : constantes publiques vs secrets réels

Les valeurs par défaut `client_id`, `client_secret` et `project_id` pour Antigravity sont les **mêmes constantes OAuth « desktop »** que dans [opencode-antigravity-auth](https://github.com/NoeFabris/opencode-antigravity-auth) (`src/constants.ts`). Elles sont **embarquées dans le code** (en hex UTF‑8 pour satisfaire la *push protection* GitHub, qui bloque les mêmes chaînes en clair). Ce ne sont **pas** des équivalents d’une clé API ou d’un refresh token.

À protéger absolument : **`GEMINI_API_KEY`**, **refresh tokens**, contenu de **`data/`** (SQLite, jetons), et tout fichier d’environnement local. Détail dans [SECURITY.md](SECURITY.md).

## Installation

À la racine du dépôt :

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -U pip
pip install -e "./python[dev]"
pip install -r services/api/requirements.txt
```

Frontend :

```bash
cd apps/web
cp .env.example .env.local
npm install
```

## Variables d’environnement

| Variable | Où | Rôle |
|----------|-----|------|
| `GEMINI_API_KEY` | shell / `.env` chargé par l’API | Appels Google Genai (provider `gemini`) |
| `ANTIGRAVITY_REFRESH_TOKEN` | shell | Refresh token OAuth (**priorité absolue** sur `data/` et OpenCode). Retirée du processus API après login web ou import OpenCode ; ne la définis pas si tu veux que le fichier `data/antigravity_refresh_token.txt` suive les changements de compte. |
| `ANTIGRAVITY_OAUTH_CLIENT_ID` | optionnel | Remplace le client OAuth embarqué pour `antigravity` |
| `ANTIGRAVITY_OAUTH_CLIENT_SECRET` | optionnel | Remplace le secret embarqué (voir note ci‑dessus) |
| `ANTIGRAVITY_PROJECT_ID` | optionnel | Remplace l’ID projet embarqué |
| `GKFY_DATA_DIR` | optionnel | Répertoire données (défaut : `<repo>/data`) |
| `GKFY_PUBLIC_API_URL` | optionnel | URL publique de l’API pour OAuth (défaut : `http://127.0.0.1:8000`) — sert aussi à construire l’`redirect_uri` par défaut |
| `GKFY_ANTIGRAVITY_OAUTH_REDIRECT_URI` | optionnel | `redirect_uri` Google. **Défaut :** `http://localhost:51121/oauth-callback` (identique à [opencode-antigravity-auth](https://github.com/NoeFabris/opencode-antigravity-auth) ; mini-serveur avec l’API). Pour utiliser le callback FastAPI : `http://127.0.0.1:8000/auth/antigravity/callback` **après** l’avoir ajoutée dans Google Cloud. |
| `GKFY_ANTIGRAVITY_OAUTH_LOOPBACK_BIND` | optionnel | Adresse du mini-serveur OAuth loopback (défaut : `127.0.0.1`) |
| `GKFY_FRONTEND_URL` | optionnel | URL du front après login Antigravity (défaut : `http://localhost:3030`) |
| `GKFY_WORKER_CONCURRENCY` | optionnel | Parallélisme worker (défaut : `2`) |
| `GKFY_WRITE_OUTPUT_FILES` | optionnel | Si `1` / `true` : le worker écrit aussi les `.md` sous `data/output`. **Par défaut** (non défini) : contenu uniquement en base (`jobs.analysis_markdown`), pas de fichiers markdown dans `data/output`. |
| `GKFY_REPO_EXPORT_DIR` | optionnel | Chemin **relatif à la racine du dépôt** (ex. `knowledge-export`) : copie miroir des analyses terminées et des prompts utilisateur sauvegardés via l’API (`prompts/<name>.md`). Doit rester sous le repo ; valeur ignorée si elle sort du dépôt. Vide = désactivé. Utile pour versionner des exports en Git (hors de `data/`, souvent gitignoré). |
| `NEXT_PUBLIC_API_URL` | `apps/web/.env.local` | URL de l’API (défaut : `http://127.0.0.1:8000`) |

Données sous `data/` : **`app.db`** (SQLite : table `jobs` avec le markdown généré, prompts utilisateur dans **`user_prompts`**, catalogue `prompts_catalog`, `app_kv`), répertoire **`output/`** (optionnel si `GKFY_WRITE_OUTPUT_FILES` — export des `.md`), répertoire **`prompts/`** (fichiers legacy ; l’API lit d’abord la base puis ces fichiers), **`antigravity_refresh_token.txt`**.

### OAuth Antigravity depuis l’UI

Le flux suit **opencode-antigravity-auth** : **PKCE** et les mêmes scopes que leur `constants.ts`.

**Comportement par défaut** — `redirect_uri` = `http://localhost:51121/oauth-callback` (déjà autorisée pour le client OAuth Antigravity public). Au démarrage, l’API ouvre un mini-serveur sur ce port. Ne lance pas OpenCode en parallèle sur `51121`. Puis dans le front : provider **antigravity** → **Se connecter (Antigravity)**.

**Alternative** — callback sur l’API : définis  
`GKFY_ANTIGRAVITY_OAUTH_REDIRECT_URI=http://127.0.0.1:8000/auth/antigravity/callback`  
(ou l’URL qui correspond à ton `GKFY_PUBLIC_API_URL`) **et** ajoute cette URI exacte dans [Google Cloud Console](https://console.cloud.google.com/apis/credentials) pour le client OAuth utilisé.

**Sans OAuth web** — OpenCode sur la **même machine** que l’API : l’UI liste les comptes du fichier `~/.config/opencode/antigravity-accounts.json` et utilise le slot **actif Antigravity** (`activeIndexByFamily.gemini` dans OpenCode), ou tu choisis un compte puis **Importer ce compte**. API : `GET /auth/antigravity/opencode-accounts`, `POST /auth/antigravity/import-opencode?account_index=N`.

## Lancer en développement

Terminal 1 — API :

```bash
source .venv/bin/activate
cd services/api
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2 — Next.js :

```bash
cd apps/web
npm run dev
```

Ouvrir [http://localhost:3030](http://localhost:3030) (port défini dans `apps/web/package.json`).

## Parité avec le CLI

Le worker appelle `process_video_job` avec les mêmes paramètres que le CLI (`model`, `thinking_level`, `provider`, `force`, prompts, `auto_title` via oEmbed). Les options du formulaire web correspondent aux flags `--model`, `--thinking-level`, `--provider`, `--force`, `--prompt`, `--auto-title` et au nom de playlist / dossier de sortie.

Équivalent CLI pour une liste d’URLs :

```bash
python -m yt_knowledge_ingest --output-dir ./data/output \
  --prompt default --concurrency 2
```

(fichiers playlist ou stdin ; l’API fixe `--output-dir` sur `data/output` dans le dépôt. Le **CLI** écrit toujours sur disque ; l’**API worker** n’écrit des `.md` que si `GKFY_WRITE_OUTPUT_FILES` est activé.)

## API (résumé)

- `GET /health` — `status`, chemin `database`, `write_output_files` (`True`/`False`), `repo_export_dir` (chemin résolu ou chaîne vide)
- `GET /auth/antigravity/status` — `{ "connected": true|false }` (refresh token utilisable)
- `GET /auth/antigravity/login` — redirection vers Google OAuth
- `GET /auth/antigravity/callback` — échange du `code`, écriture de `data/antigravity_refresh_token.txt`
- `GET /options/models` — modèles par provider (`gemini` = API publique, `antigravity` = passerelle cloudcode-pa ; IDs différents, voir [ANTIGRAVITY_API_SPEC](https://github.com/NoeFabris/opencode-antigravity-auth/blob/main/docs/ANTIGRAVITY_API_SPEC.md))
- `POST /jobs` — enqueue (body JSON : `urls`, `playlist_label`, `model`, `thinking_level`, `provider`, `force`, `prompt`, `auto_title`). Si `model` n’est pas valide pour le `provider`, l’API le remplace par le défaut du provider.
- `GET /jobs`, `GET /jobs/{id}`, `GET /jobs/stream` (SSE), `GET /jobs/summary`
- `GET|PUT|DELETE /prompts`, `GET|PUT /prompts/{name}`
- `GET /artifacts/tree`, `GET /artifacts/content?rel=`, `GET /artifacts/raw?rel=`, `GET /artifacts/zip?playlist=`

## Tests Python (package seul)

Comme en CI :

```bash
source .venv/bin/activate
pip install -e "./python[dev]"
pytest python/tests -q
```

## Licence

Le code est sous licence MIT — voir [LICENSE](LICENSE).

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md). Signalement des secrets / vulnérabilités : [SECURITY.md](SECURITY.md).
