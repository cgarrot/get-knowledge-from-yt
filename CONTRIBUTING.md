# Contributing

1. Fork le dépôt et crée une branche pour ton changement.
2. Ne commite **jamais** `data/`, `.env`, `apps/web/.env.local`, jetons ou clés API — voir [SECURITY.md](SECURITY.md) et [OPEN_SOURCE_CHECKLIST.md](OPEN_SOURCE_CHECKLIST.md).

## Checks avant une PR (alignés sur la CI)

Ces commandes sont celles exécutées par [.github/workflows/ci.yml](.github/workflows/ci.yml).

### Package Python

À la **racine du monorepo** (pas seulement `python/`) :

```bash
python -m pip install -U pip
pip install -e "./python[dev]"
pytest python/tests -q
```

Tu peux aussi travailler depuis `python/` avec `pip install -e ".[dev]"` puis `pytest` si tu restes dans ce répertoire.

### API

Installe les dépendances comme dans [README.md](README.md), puis lance l’API depuis `services/api` :

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd apps/web
npm ci
npm run lint
npm run build
```

## Pull request

Ouvre une PR avec une description claire du comportement attendu et des risques éventuels (API, schéma SQLite, contrats front/API).

Les fichiers `*.md` sous `python/src/yt_knowledge_ingest/prompts/` sont **gitignorés** : tu peux y mettre tes prompts localement sans les publier. Les noms `default` et `game-theory` restent fournis par le code si aucun `.md` n’est présent. Les overrides API utilisateur restent sous `data/prompts/` (déjà exclu via `data/`).
