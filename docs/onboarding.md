# User Onboarding

This guide is for people who want to run the open-source Engram AI product locally. It keeps the default path small and moves optional setup into separate sections.

Engram is a full-stack app:

- FastAPI backend on `http://localhost:8000`
- Next.js frontend on `http://localhost:3000`
- PostgreSQL with pgvector for documents, chunks, and embeddings
- Redis + Celery for background ingestion jobs
- an LLM provider key for chat responses
- optional GitHub OAuth for repository ingestion and login
- optional Notion OAuth for Notion ingestion
- optional MCP access for external AI clients

## Minimal Local Setup

Install:

- Python 3.11 or newer
- Node.js 20 or newer
- Docker
- Git

Check your local tools:

```bash
python --version
node --version
docker compose version
docker compose ps
```

`docker compose ps` should run without a permission error. If it cannot connect to the Docker socket, fix Docker Desktop or Linux group permissions before continuing.

Clone the repo:

```bash
git clone https://github.com/engramAI-dev/engramAI.git
cd engramAI
cp .env.example .env
```

Set one AI provider in `.env`.

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

Start Postgres and Redis:

```bash
docker compose up -d postgres redis
```

Start the backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

Start the worker in a second terminal:

```bash
cd backend
source .venv/bin/activate
celery -A celery_app.celery worker --loglevel=info --concurrency=1
```

Start the frontend in a third terminal:

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## GitHub Login and Repository Ingestion

Local login and GitHub repository ingestion use GitHub OAuth.

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

5. Add the credentials to `.env`:

```env
GITHUB_CLIENT_ID=your-client-id
GITHUB_CLIENT_SECRET=your-client-secret
GITHUB_REDIRECT_URI=http://localhost:8000/api/auth/callback
```

Restart the backend, open the app, and complete GitHub login.

After logging in:

1. Go to the connections page.
2. Add a GitHub repository URL.
3. Start indexing.
4. Watch the jobs page for progress.

When indexing completes, ask questions such as:

```text
How does authentication work?
```

```text
Where is the ingestion pipeline implemented?
```

```text
Explain the database models for documents and chunks.
```

## Notion

Notion support is optional.

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

## MCP Usage

The backend exposes MCP over:

```text
http://localhost:8000/mcp
```

MCP requests require a bearer token. Create an MCP token from the settings UI, then configure your MCP-compatible client to use the local MCP URL and token.

Example client configuration:

```json
{
  "mcpServers": {
    "engram": {
      "url": "http://localhost:8000/mcp",
      "headers": {
        "Authorization": "Bearer <your-engram-token>"
      }
    }
  }
}
```

Available tools include:

- `search_knowledge`
- `fetch_document`
- `cite`

## Configuration Reference

`.env.example` contains local defaults for:

- `SECRET_KEY`
- `DATABASE_URL`
- `REDIS_URL`
- `FRONTEND_URL`
- `NEXT_PUBLIC_API_URL`
- `GITHUB_REDIRECT_URI`
- `NOTION_REDIRECT_URI`

Most local users only need to add:

- one LLM provider key
- GitHub OAuth credentials if using login or repository ingestion
- Notion OAuth credentials if using Notion

Do not commit `.env`.

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

The embedding model is downloaded on first use. This is normal. Later runs should be faster because the model is cached locally.

### Database errors

Make sure Postgres is running and migrations are applied:

```bash
docker compose ps postgres
cd backend
alembic upgrade head
```