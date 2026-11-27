# CINEMIND Architecture

## 1. Architectural Style: Modular Monolith

CINEMIND is structured as a **modular monolith** built on FastAPI, asynchronous SQLAlchemy 2.x, and PostgreSQL. This keeps deployment simple during early phases while enforcing clean module boundaries so domain engines can evolve independently without rewriting the core platform.

Guiding design principle:

> **AI proposes, deterministic systems validate, and the creator decides.**

---

## 2. Backend Layering

```text
HTTP Request
   │
   ▼
API Layer (app/api/v1/endpoints/)
   │  - Request validation via Pydantic 2
   │  - Dependency injection (services, settings)
   │  - HTTP status codes & OpenAPI contracts
   ▼
Service Layer (app/services/)
   │  - Business rules & cross-entity checks
   │  - Transaction boundaries (commit/rollback)
   │  - Domain exceptions (ProjectNotFoundError, etc.)
   ▼
Repository Layer (app/repositories/)
   │  - Pure async SQLAlchemy 2.x queries
   │  - Pagination & ordering
   ▼
PostgreSQL (via asyncpg + SQLAlchemy AsyncSession)
```

Cross-cutting concerns live in `app/core/`:
- `constants.py` — Enums (`ProjectStatus`, `ConversationStatus`, `MessageRole`) and pagination/length limits.
- `exceptions.py` — Typed `CineMindException` hierarchy mapped to HTTP status codes.
- `error_handlers.py` — Centralized exception handlers emitting a uniform `{"error": {"code": ..., "message": ...}}` JSON envelope without leaking SQL or credentials.
- `logging.py` — Structured stdout logging configuration.

---

## 3. Phase 1 Database Schema

```text
projects (1) ──────< (N) conversations (1) ──────< (N) messages
```

- **`projects`**: Root creative entity (`id`, `title`, `description`, `status`, `created_at`, `updated_at`). Deleting a project cascades to its conversations and messages (`ON DELETE CASCADE` + ORM `all, delete-orphan`).
- **`conversations`**: Conversational session belonging to a project (`id`, `project_id`, `title`, `status`, `created_at`, `updated_at`).
- **`messages`**: Chronological messages inside a conversation (`id`, `conversation_id`, `role`, `content`, `message_type`, `metadata` JSONB, `created_at`). Indexed on `(conversation_id, created_at)` and constrained at the DB level (`role IN ('system', 'user', 'assistant')`).

All schema changes are managed strictly via Alembic (`backend/migrations/`).

---

## 4. Future Integration Boundaries (Phases 2+)

Two dedicated packages are reserved in `backend/app/`:

1. **`app/engines/`** — Domain intelligence modules:
   - `story_intelligence/`: Premise expansion, narrative beats, inline improvement proposals.
   - `narrative_emotion/`: NetworkX narrative & emotion graph modeling.
   - `creative_direction/`: Adaptive visual style, mood, and camera intent capture.
   - `cinematic_reasoning/`: Hybrid LLM + deterministic rules + scoring for emotion-to-cinematography translation.
   - `what_if/`: Multi-director comparative variations.
   - `continuity/`: Character, prop, lighting, and spatial continuity checks.
   - `audience/`: Pacing and audience experience evaluation.
   - `production/`: Feasibility checks, schedule/budget hints, and shot-plan PDF export.

2. **`app/orchestrator/`** — Central workflow coordinator:
   - Maintains compact project context across conversation turns.
   - Determines engine execution order.
   - Enforces creator approval gates (no silent overwrites of story or shot plans).
   - Coordinates progressive scene-by-scene and shot-by-shot generation.
   - Records model usage and execution status via `messages.metadata` and future domain tables.
