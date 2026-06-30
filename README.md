# Engram AI

Engram AI is an open-source engineering context layer for AI-native teams. It connects code and documentation, indexes them into a searchable knowledge base, and exposes grounded context through chat and MCP-compatible tools.

This repository contains the free, self-hostable core.

## What is included

- FastAPI backend for auth, chat, ingestion, retrieval, outputs, and MCP
- Next.js frontend for chat, sources, library, jobs, connections, and outputs
- GitHub and Notion ingestion pipeline
- Local embedding support through sentence-transformers
- PostgreSQL + pgvector retrieval
- Celery/Redis background jobs
- MCP tools for searching knowledge and fetching indexed documents

## Local development

For a full fork-to-running-app walkthrough, see
[`docs/onboarding.md`](docs/onboarding.md).

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker
- Git

### Start infrastructure

```bash
docker compose up -d postgres redis
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Configuration

Copy `.env.example` to `.env` and fill in the values you need.

At minimum, local development usually needs:

- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- one LLM provider key, such as `GOOGLE_API_KEY` or `ANTHROPIC_API_KEY`

## Project structure

```text
backend/      FastAPI app, models, ingestion, retrieval, chat, MCP
frontend/     Next.js app
docs/         Public API and architecture notes
.github/      Issue templates, PR template, CI
```

## License

Apache-2.0. See `LICENSE`.

## Contributing

Contributions are welcome. See `CONTRIBUTING.md`.
