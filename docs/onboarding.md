# Developer Onboarding

This guide walks through running Engram AI from a fork of the open-source repo.

Engram is a full-stack app:

- FastAPI backend on `http://localhost:8000`
- Next.js frontend on `http://localhost:3000`
- PostgreSQL with pgvector for documents, chunks, and embeddings
- Redis + Celery for background ingestion jobs
- GitHub OAuth for local login
- an LLM provider key for chat responses

## 1. Fork and Clone

Fork the repository on GitHub, then clone your fork:

```bash
git clone https://github.com/<your-user>/engramAI.git
cd engramAI
```

Add the upstream repo so you can pull future changes:

```bash
git remote add upstream https://github.com/engramAI-dev/engramAI.git
git remote -v
```

## 2. Prerequisites

Install:

- Python 3.11 or newer
- Node.js 20 or newer
- Docker
- Git

Optional but recommended:

- a Python virtual environment
- a recent `pip`

## 3. Start Postgres and Redis

From the repo root:

```bash
docker compose up -d postgres redis
```

Confirm both containers are running:

```bash
docker compose ps
```

## 4. Configure Environment Variables

Copy the example env file:

```bash
cp .env.example .env
```

At minimum, set:

```env
SECRET_KEY=replace-with-a-long-random-string
DATABASE_URL=postgresql+asyncpg://engram:engram@localhost:5432/engram
REDIS_URL=redis://localhost:6379/0
FRONTEND_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then configure one LLM provider.

For Gemini:

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
GOOGLE_API_KEY=your-google-api-key
```

For Claude:

```env
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=your-anthropic-api-key
```

Do not commit `.env`.

## 5. Create a GitHub OAuth App

Local login uses GitHub OAuth.

Create a GitHub OAuth App:

1. Open GitHub Developer Settings.
2. Create a new OAuth App.
3. Set homepage URL to:

```text
http://localhost:3000
```

4. Set callback URL to:

```text
http://localhost:8000/api/auth/callback
```

5. Copy the client ID and client secret into `.env`:

```env
GITHUB_CLIENT_ID=your-client-id
GITHUB_CLIENT_SECRET=your-client-secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

GitHub repo ingestion uses the OAuth token from this login flow. For private
repos, your GitHub account must have access to the repo.

## 6. Install Backend Dependencies

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Apply database migrations:

```bash
alembic upgrade head
```

Start the backend API:

```bash
uvicorn main:app --reload
```

Keep this terminal running.

## 7. Start the Celery Worker

Open a second terminal:

```bash
cd backend
source .venv/bin/activate
celery -A celery_app.celery worker --loglevel=info --concurrency=1
```

The worker handles GitHub/Notion ingestion and embedding jobs.

The first embedding run may download the local embedding model. That can take
a few minutes.

## 8. Install and Start the Frontend

Open a third terminal:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

Click login and complete GitHub OAuth.

## 9. Index a Repository

After logging in:

1. Go to the connections page.
2. Add a GitHub repository URL.
3. Start indexing.
4. Watch the jobs page for progress.

Behind the scenes:

- the API creates an ingest job
- Celery clones the repo
- the chunker splits files into searchable chunks
- the embedding worker stores vectors in Postgres/pgvector

After indexing completes, ask a question in the chat page.

Example questions:

```text
How does authentication work?
```

```text
Where is the ingestion pipeline implemented?
```

```text
Explain the database models for documents and chunks.
```

## 10. Optional: Connect Notion

Notion requires OAuth configuration.

Create a public Notion integration and set the redirect URI to:

```text
http://localhost:8000/api/providers/notion/callback
```

Then set:

```env
NOTION_CLIENT_ID=your-notion-client-id
NOTION_CLIENT_SECRET=your-notion-client-secret
NOTION_REDIRECT_URI=http://localhost:8000/api/providers/notion/callback
```

Restart the backend, then connect Notion from the connections page.

## 11. MCP Usage

The backend exposes MCP over:

```text
http://localhost:8000/mcp
```

MCP requests require a bearer token. In the app, create an MCP token from the
settings UI, then configure your MCP-compatible client to use the local MCP URL
and token.

Available tools include:

- `search_knowledge`
- `fetch_document`
- `cite`

## 12. Useful Commands

Backend checks:

```bash
cd backend
ruff check .
pytest
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run test:run
```

Reset local infrastructure:

```bash
docker compose down
docker compose up -d postgres redis
```

Reset local database data:

```bash
docker compose down -v
docker compose up -d postgres redis
cd backend
alembic upgrade head
```

## Troubleshooting

### Login redirects fail

Check that your GitHub OAuth callback URL exactly matches:

```text
http://localhost:8000/api/auth/callback
```

Also check:

```env
GITHUB_REDIRECT_URI=http://localhost:8000/api/auth/callback
FRONTEND_URL=http://localhost:3000
```

### Chat responds with an error

Check that:

- the backend is running
- your LLM API key is set
- `LLM_PROVIDER` matches the key you configured
- at least one repo or doc source has been indexed

### Ingestion job stays queued

Make sure the Celery worker is running:

```bash
cd backend
celery -A celery_app.celery worker --loglevel=info --concurrency=1
```

Also confirm Redis is running:

```bash
docker compose ps redis
```

### Embedding is slow on first run

The embedding model is downloaded on first use. This is normal. Later runs
should be faster because the model is cached locally.

### Database errors

Make sure Postgres is running and migrations are applied:

```bash
docker compose ps postgres
cd backend
alembic upgrade head
```

## Contributing Changes

Before opening a pull request:

```bash
cd backend
ruff check .
pytest
```

```bash
cd frontend
npm run lint
npm run test:run
```

If a check fails because of known pre-existing project debt, mention it in the
pull request description.
