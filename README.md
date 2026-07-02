# Engram AI

Engram AI is an open-source engineering context layer for AI-native teams. It connects code and documentation, indexes them into a searchable knowledge base, and exposes grounded context through chat and MCP-compatible tools.

This repository contains the free, self-hostable core.

## What You Can Run

- A web app for asking questions over indexed engineering knowledge
- A FastAPI backend for auth, ingestion, retrieval, outputs, chat, and MCP
- GitHub and Notion ingestion pipelines
- Local embeddings with PostgreSQL + pgvector
- MCP tools for `search_knowledge`, `fetch_document`, and `cite`

## Quickstart

The shortest path is:

1. Clone the repo.
2. Add one AI provider API key.
3. Start the local services.
4. Open the app.

```bash
git clone https://github.com/engramAI-dev/engramAI.git
cd engramAI
```

Check local prerequisites before continuing:

```bash
python --version   # 3.11 or newer
node --version     # 20 or newer
docker compose version
docker compose ps  # confirms your user can access Docker
```

Then create local configuration:

```bash
cp .env.example .env
```

Set one model provider in `.env`.

Recommended for normal use:

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your-anthropic-api-key
```

Low-cost local testing:

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=your-google-api-key
```

Then start the local stack:

```bash
docker compose up -d postgres redis
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

In a second terminal:

```bash
cd backend
source .venv/bin/activate
celery -A celery_app.celery worker --loglevel=info --concurrency=1
```

In a third terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

For the full self-hosting walkthrough, including GitHub OAuth, Notion, MCP, and troubleshooting, see [docs/onboarding.md](docs/onboarding.md).

## MCP

Engram exposes MCP at:

```text
http://localhost:8000/mcp
```

Create an MCP token in the app settings, then configure your MCP-compatible client with that URL and bearer token.

## Contributing

If you want to work on Engram itself, start with [docs/contributor-onboarding.md](docs/contributor-onboarding.md).

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Project Structure

```text
backend/      FastAPI app, models, ingestion, retrieval, chat, MCP
frontend/     Next.js app
docs/         Public API and onboarding docs
.github/      Issue templates, PR template, CI
```

## License

Apache-2.0. See [LICENSE](LICENSE).