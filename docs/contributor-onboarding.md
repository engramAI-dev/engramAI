# Contributor Onboarding

This guide is for people who want to contribute code to Engram AI. If you only want to run the product locally, start with [onboarding.md](onboarding.md).

## Fork and Clone

Fork the repository on GitHub, then clone your fork:

```bash
git clone https://github.com/<your-user>/engramAI.git
cd engramAI
```

Add the upstream repo:

```bash
git remote add upstream https://github.com/engramAI-dev/engramAI.git
git remote -v
```

Before starting work:

```bash
git fetch upstream
git checkout main
git merge --ff-only upstream/main
git checkout -b your-feature-branch
```

## Development Requirements

Install:

- Python 3.11 or newer
- Node.js 20 or newer
- Docker
- Git

Check your local tools before installing dependencies:

```bash
python --version
node --version
npm --version
docker compose version
docker compose ps
```

`docker compose ps` should run without a permission error. If it cannot connect to the Docker socket, fix Docker Desktop or Linux group permissions before continuing.

Recommended:

- a Python virtual environment
- a recent `pip`
- a GitHub OAuth App for end-to-end login and repository ingestion testing

## Local Services

Start Postgres and Redis:

```bash
docker compose up -d postgres redis
docker compose ps
```

Copy local configuration:

```bash
cp .env.example .env
```

For day-to-day development, set one LLM provider key in `.env`. Add GitHub or Notion OAuth credentials only when working on those flows.

## Backend Setup

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

## Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:3000
```

## Test and Lint

Run backend checks:

```bash
cd backend
ruff check .
pytest
```

Run frontend checks:

```bash
cd frontend
npm run lint
npm run test:run
```

Run only focused tests when iterating, but run the relevant full check before opening a pull request.

## Common Development Tasks

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

Create a migration after changing SQLAlchemy models:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## Project Structure

```text
backend/api/          FastAPI routes and middleware
backend/chat/         LLM abstraction and chat engine
backend/ingestion/    GitHub and Notion ingestion pipeline
backend/knowledge/    Retrieval and cross-validation logic
backend/models/       SQLAlchemy models and database session
backend/mcp_shared/   MCP tool definitions and shared server logic
frontend/src/app/     Next.js App Router pages
frontend/src/components/
docs/                 Public docs and contracts
```

## Pull Requests

Before opening a PR:

1. Keep the branch focused on one concern.
2. Update docs when behavior or setup changes.
3. Run relevant backend and frontend checks.
4. Fill out the PR template.
5. Mention any checks you could not run.

Never commit secrets, tokens, `.env`, private repository content, or customer data.

## Architecture Notes

- Ingestion runs asynchronously through Celery.
- API request handlers should not perform long-running indexing work.
- LLM calls should go through `backend/chat/llm.py`.
- Embeddings are stored in PostgreSQL with pgvector.
- MCP exposes indexed knowledge to external AI clients.