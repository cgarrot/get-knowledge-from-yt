# yt-knowledge-ingest

Package Python : chaîne d’ingestion YouTube → markdown wiki (Gemini multimodal, prompts `.md`). Voir le [README du dépôt](../README.md) pour l’API et le front Next.js.

**Python 3.10+** requis (recommandé : 3.11+). Avant publication ou PR, voir aussi [OPEN_SOURCE_CHECKLIST.md](../OPEN_SOURCE_CHECKLIST.md).

## Installation et usage

```bash
cd python
pip install -e ".[dev]"
export GEMINI_API_KEY=...
yt-knowledge-ingest --output-dir ./out playlist.txt
# ou, depuis la racine du monorepo :
# pip install -e "./python[dev]"
# python -m yt_knowledge_ingest --output-dir ./out playlist.txt
```

## Tests

Depuis la **racine du dépôt** :

```bash
pip install -e "./python[dev]"
pytest python/tests -q
```

## Prompts

Les fichiers `*.md` dans `src/yt_knowledge_ingest/prompts/` sont **ignorés par Git** : copie-y tes prompts localement. Sans fichiers, `default` et `game-theory` viennent du code embarqué.
