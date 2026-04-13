# Engram API Contract (v0.1)

Base URL: `http://localhost:8000/api`

This is the shared contract between Track A and Track B. Neither partner should change endpoint shapes without updating this doc and notifying the other.

---

## Ownership

| Endpoint Group | Implemented By | Consumed By |
|----------------|---------------|-------------|
| `/auth/*` | Track A | Both |
| `/chat/*` | Track A | Track B (output generator reads chat results) |
| `/documents/*` | Track A | Track B (enrichment, staleness UI) |
| `/ingest/*` | Track A | Track B (settings UI triggers re-index) |
| `/outputs/*` | Track B | Track A (context panel links to outputs) |
| `/health` | Track A | Both |

---

## Auth

**Owner: Track A**

Track B depends on these to protect her routes and identify the current user.

### `GET /auth/login`

Redirects to GitHub OAuth authorization page.

### `GET /auth/callback?code={code}`

Exchanges OAuth code for access token. Creates or updates user. Sets session.

**Response `200`:**
```json
{
  "access_token": "eyJhbG...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "github_username": "octocat",
    "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4"
  }
}
```

### `GET /auth/me`

Returns current authenticated user.

**Headers:** `Authorization: Bearer <jwt>`

**Response `200`:**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "github_username": "octocat",
  "avatar_url": "https://avatars.githubusercontent.com/u/1?v=4",
  "created_at": "2026-04-12T18:00:00Z"
}
```

### JWT Structure

Track B needs this to implement auth middleware on output routes.

```json
{
  "sub": "550e8400-e29b-41d4-a716-446655440000",
  "github_username": "octocat",
  "exp": 1744502400
}
```

Signed with `SECRET_KEY` from env using HS256. Validate with `python-jose`:

```python
from jose import jwt
from config import settings

payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
user_id = payload["sub"]
```

---

## Chat

**Owner: Track A**

Track B's output generator consumes the response shape from this endpoint.

### `POST /chat`

Send a message. Response is streamed via Server-Sent Events (SSE).

**Headers:** `Authorization: Bearer <jwt>`

**Request:**
```json
{
  "message": "Explain how the auth middleware works",
  "conversation_id": "uuid | null"
}
```

**Response (SSE stream):**
```
data: {"type": "text", "content": "The auth middleware..."}
data: {"type": "text", "content": " validates the JWT token..."}
data: {"type": "sources", "content": [{"chunk_id": "uuid", "document_id": "uuid", "document_title": "auth.py", "file_path": "backend/api/middleware.py", "source": "github", "url": "https://github.com/...", "relevance_score": 0.95, "content_preview": "def verify_token(token: str)..."}]}
data: {"type": "done", "conversation_id": "uuid", "message_id": "uuid"}
```

**SSE Event Types:**

| Type | Description | Track B Cares? |
|------|-------------|-----------------|
| `text` | Partial streamed text from LLM | Yes — display in output panel |
| `sources` | Retrieved chunks used for this response | Yes — display in context panel, feed to output generator |
| `done` | Stream complete, includes final IDs | Yes — use `message_id` to link outputs |

### `ChatEngineResult` (Internal)

This is the structured object Track A's engine returns **before** SSE serialization. Track B's output generator receives this shape when processing a chat response into a formatted output.

```python
@dataclass
class SourceChunk:
    chunk_id: str
    document_id: str
    document_title: str
    file_path: str | None
    source: str  # "github" | "notion"
    url: str
    relevance_score: float
    content_preview: str  # first 200 chars of chunk

@dataclass
class ChatEngineResult:
    response_text: str
    sources: list[SourceChunk]
    conversation_id: str
    message_id: str
    intent: str  # "explain" | "generate" | "question"
    model: str
    input_tokens: int
    output_tokens: int
```

**Track B:** Your output generator takes `ChatEngineResult` and produces a formatted output (code snippet, summary, report). The `intent` field tells you what type of output to produce. The `sources` list gives you provenance for citations.

### `GET /chat/conversations`

List user's conversations.

**Headers:** `Authorization: Bearer <jwt>`

**Response `200`:**
```json
{
  "conversations": [
    {
      "id": "uuid",
      "title": "Auth middleware explanation",
      "message_count": 4,
      "updated_at": "2026-04-12T18:30:00Z"
    }
  ],
  "total": 15,
  "page": 1
}
```

### `GET /chat/conversations/{id}/messages`

Get messages for a conversation.

**Headers:** `Authorization: Bearer <jwt>`

**Response `200`:**
```json
{
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "Explain how the auth middleware works",
      "sources": [],
      "created_at": "2026-04-12T18:00:00Z"
    },
    {
      "id": "uuid",
      "role": "assistant",
      "content": "The auth middleware validates...",
      "sources": [
        {
          "chunk_id": "uuid",
          "document_id": "uuid",
          "document_title": "auth.py",
          "file_path": "backend/api/middleware.py",
          "source": "github",
          "url": "https://github.com/...",
          "relevance_score": 0.95,
          "content_preview": "def verify_token..."
        }
      ],
      "created_at": "2026-04-12T18:00:05Z"
    }
  ]
}
```

---

## Documents

**Owner: Track A**

Track B reads these for enrichment (Notion hierarchy, freshness) and the staleness comparison UI.

### `GET /documents`

List all indexed documents for the user.

**Headers:** `Authorization: Bearer <jwt>`

**Query params:** `?source=github|notion&page=1&limit=20`

**Response `200`:**
```json
{
  "documents": [
    {
      "id": "uuid",
      "title": "auth.py",
      "source": "github",
      "repo": "owner/repo",
      "file_path": "backend/api/middleware.py",
      "url": "https://github.com/owner/repo/blob/main/backend/api/middleware.py",
      "language": "python",
      "indexed_at": "2026-04-12T17:00:00Z",
      "chunk_count": 12,
      "is_stale": false
    }
  ],
  "total": 342,
  "page": 1
}
```

### `GET /documents/{id}`

Get document details including its chunks.

**Headers:** `Authorization: Bearer <jwt>`

**Response `200`:**
```json
{
  "id": "uuid",
  "title": "auth.py",
  "source": "github",
  "repo": "owner/repo",
  "file_path": "backend/api/middleware.py",
  "url": "https://github.com/...",
  "language": "python",
  "indexed_at": "2026-04-12T17:00:00Z",
  "chunks": [
    {
      "id": "uuid",
      "content": "def verify_token(token: str) -> dict:\n    ...",
      "start_line": 15,
      "end_line": 42,
      "chunk_type": "function"
    }
  ],
  "cross_validation": {
    "related_notion_pages": [
      {
        "document_id": "uuid",
        "title": "Auth Architecture",
        "staleness_score": 0.3,
        "last_validated_at": "2026-04-12T17:00:00Z"
      }
    ]
  }
}
```

**Track B:** The `cross_validation` field is what you need for the side-by-side staleness comparison UI (B10). `staleness_score` ranges from 0.0 (fresh) to 1.0 (completely outdated). You can fetch both the code document and the related Notion page to render them side by side.

---

## Ingestion

**Owner: Track A**

Track B calls these from the Settings UI to trigger re-indexing and show progress.

### `POST /ingest/github`

Trigger GitHub repo ingestion. Async — returns immediately with a job ID.

**Headers:** `Authorization: Bearer <jwt>`

**Request:**
```json
{
  "repo_url": "https://github.com/owner/repo"
}
```

**Response `202`:**
```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### `POST /ingest/notion`

Trigger Notion workspace ingestion.

**Headers:** `Authorization: Bearer <jwt>`

**Request:**
```json
{
  "workspace_id": "notion-workspace-id"
}
```

**Response `202`:**
```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

### `GET /ingest/status/{job_id}`

Poll ingestion job status. Track B: use this in the settings UI to show progress bars.

**Headers:** `Authorization: Bearer <jwt>`

**Response `200`:**
```json
{
  "job_id": "uuid",
  "status": "processing",
  "progress": 0.65,
  "documents_indexed": 128,
  "total_documents": 197,
  "error": null
}
```

**Status values:** `queued` → `processing` → `completed` | `failed`

---

## Outputs

**Owner: Track B**

Track A's context panel will link to these when a chat response has been formatted into an output.

### `POST /outputs/generate`

Generate a formatted output from a chat message.

**Headers:** `Authorization: Bearer <jwt>`

**Request:**
```json
{
  "message_id": "uuid",
  "output_type": "code_snippet | summary | report"
}
```

**Response `201`:**
```json
{
  "id": "uuid",
  "type": "code_snippet",
  "title": "Auth middleware implementation",
  "content": "def verify_token(token: str) -> dict:\n    ...",
  "metadata": {
    "language": "python",
    "file_path_suggestion": "backend/api/middleware.py",
    "source_message_id": "uuid",
    "source_conversation_id": "uuid"
  },
  "created_at": "2026-04-12T18:01:00Z"
}
```

### `GET /outputs`

List generated outputs for the user.

**Headers:** `Authorization: Bearer <jwt>`

**Query params:** `?type=code_snippet|summary|report&page=1&limit=20`

**Response `200`:**
```json
{
  "outputs": [
    {
      "id": "uuid",
      "type": "code_snippet",
      "title": "Auth middleware implementation",
      "preview": "def verify_token(token: str) -> dict:...",
      "created_at": "2026-04-12T18:01:00Z"
    }
  ],
  "total": 23,
  "page": 1
}
```

### `GET /outputs/{id}`

Get full output content.

**Headers:** `Authorization: Bearer <jwt>`

**Response `200`:**
```json
{
  "id": "uuid",
  "type": "code_snippet",
  "title": "Auth middleware implementation",
  "content": "def verify_token(token: str) -> dict:\n    payload = jwt.decode(...)\n    ...",
  "metadata": {
    "language": "python",
    "file_path_suggestion": "backend/api/middleware.py",
    "source_message_id": "uuid",
    "source_conversation_id": "uuid"
  },
  "created_at": "2026-04-12T18:01:00Z"
}
```

---

## Health

**Owner: Track A**

### `GET /health`

**Response `200`:**
```json
{ "status": "ok" }
```

---

## Common Patterns

### Authentication

All endpoints except `/auth/login`, `/auth/callback`, and `/health` require:

```
Authorization: Bearer <jwt>
```

Unauthorized requests return `401`:
```json
{ "detail": "Not authenticated" }
```

### Error Responses

All errors follow this shape:

```json
{ "detail": "Human-readable error message" }
```

| Status | Meaning |
|--------|---------|
| 400 | Bad request (validation failed) |
| 401 | Not authenticated |
| 403 | Forbidden (wrong user) |
| 404 | Resource not found |
| 422 | Unprocessable entity (Pydantic validation) |
| 500 | Internal server error |

### Pagination

Endpoints that return lists accept `?page=1&limit=20` and return:

```json
{
  "items": [...],
  "total": 100,
  "page": 1
}
```

Default limit: 20. Max limit: 100.

### IDs

All IDs are UUIDs (v4), represented as strings.

### Dates

All timestamps are ISO 8601, UTC: `"2026-04-12T18:00:00Z"`

---

## Database Tables

Shared reference so both partners know the schema shape.

### Track A's Tables

```sql
-- Users (from GitHub OAuth)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    github_id BIGINT UNIQUE NOT NULL,
    github_username VARCHAR(255) NOT NULL,
    avatar_url TEXT,
    access_token TEXT NOT NULL,  -- encrypted GitHub token
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Indexed documents (code files, Notion pages)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    source VARCHAR(50) NOT NULL,  -- 'github' | 'notion'
    repo VARCHAR(255),            -- 'owner/repo' for GitHub
    file_path TEXT,               -- file path for GitHub
    url TEXT,
    language VARCHAR(50),
    indexed_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

-- Document chunks (for embedding + retrieval)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    chunk_type VARCHAR(50),  -- 'function', 'class', 'paragraph', etc.
    embedding vector(1024),  -- pgvector, dimension depends on model
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Conversations
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Chat messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    sources JSONB DEFAULT '[]',
    intent VARCHAR(50),         -- 'explain' | 'generate' | 'question'
    token_count INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Track B's Tables

```sql
-- Generated outputs
CREATE TABLE outputs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    message_id UUID REFERENCES messages(id),  -- which chat message produced this
    conversation_id UUID REFERENCES conversations(id),
    type VARCHAR(50) NOT NULL,    -- 'code_snippet' | 'summary' | 'report'
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',  -- language, file_path_suggestion, etc.
    created_at TIMESTAMPTZ DEFAULT now()
);
```

**Track B:** Your `outputs` table has foreign keys into Track A's `users`, `messages`, and `conversations` tables. You can reference them but should not modify their schema.
