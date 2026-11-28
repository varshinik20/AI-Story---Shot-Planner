# CINEMIND Backend

**CINEMIND** (*Contextual Intelligence for Narrative, Emotion, Meaning and Intelligent Direction*) is an AI-powered cinematic story intelligence and shot-planning platform.

This directory contains the **Phase 1 Backend Foundation** built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.x (async)**, and **Alembic**.

---

## 1. Architecture Overview

The backend follows a **modular monolith** architecture with strict separation of concerns:

- **API Layer (`app/api/v1/endpoints/`)**: Handles HTTP routing, request parsing, schema validation, and HTTP status codes.
- **Service Layer (`app/services/`)**: Enforces business rules, validates parent/child entity existence, coordinates repositories, and commits transactions.
- **Repository Layer (`app/repositories/`)**: Encapsulates all asynchronous SQLAlchemy queries, pagination, and ORM persistence.
- **Database Layer (`app/db/`)**: Configures the async PostgreSQL engine (`asyncpg`), `AsyncSession` dependency injection, and declarative models (`Project`, `Conversation`, `Message`).
- **Core Layer (`app/core/`)**: Provides structured logging, domain constants, custom exceptions, and centralized JSON error handlers.
- **Future Boundaries (`app/engines/` & `app/orchestrator/`)**: Reserved integration points for Story Intelligence, Narrative Emotion Graph (NetworkX), Creative Direction, Cinematic Reasoning, What-If, Continuity, Audience, and Production engines.

---

## 2. Technology Stack

- **Python**: 3.10+
- **Web Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL
- **ORM / Driver**: SQLAlchemy 2.x (`sqlalchemy[asyncio]`) + `asyncpg`
- **Migrations**: Alembic
- **Validation & Settings**: Pydantic 2 + `pydantic-settings` + `python-dotenv`
- **Testing**: Pytest + `pytest-asyncio` + HTTPX

---

## 3. Folder Structure

```text
backend/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   ├── api/v1/
│   │   ├── router.py
│   │   └── endpoints/
│   │       ├── health.py
│   │       ├── projects.py
│   │       ├── conversations.py
│   │       └── messages.py
│   ├── core/
│   │   ├── constants.py
│   │   ├── error_handlers.py
│   │   ├── exceptions.py
│   │   └── logging.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models/
│   │       ├── project.py
│   │       ├── conversation.py
│   │       └── message.py
│   ├── schemas/
│   │   ├── common.py
│   │   ├── project.py
│   │   ├── conversation.py
│   │   └── message.py
│   ├── repositories/
│   │   ├── project_repository.py
│   │   ├── conversation_repository.py
│   │   └── message_repository.py
│   ├── services/
│   │   ├── project_service.py
│   │   ├── conversation_service.py
│   │   └── message_service.py
│   ├── engines/
│   └── orchestrator/
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_projects.py
│   ├── test_conversations.py
│   └── test_messages.py
├── .env.example
├── alembic.ini
├── pytest.ini
└── requirements.txt
```

---

## 4. Prerequisites (Windows)

1. **Python 3.10+** installed and added to `PATH`.
2. **PostgreSQL 14+** installed locally and running on port `5432` (Windows service `postgresql-x64-*` started).

---

## 5. Python Environment Setup (PowerShell)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 6. PostgreSQL Setup (PowerShell)

Create the development and isolated test databases in PostgreSQL using `psql`:

```powershell
psql -U postgres -c "CREATE DATABASE cinemind_db;"
psql -U postgres -c "CREATE DATABASE cinemind_test_db;"
```

*(If `psql` is not on your `PATH`, run it from `C:\Program Files\PostgreSQL\<version>\bin\psql.exe` or create both databases using pgAdmin.)*

---

## 7. Environment Variables

Copy `.env.example` to `.env` inside `backend/`:

```powershell
Copy-Item .env.example .env
```

Update `.env` with your PostgreSQL credentials:

| Variable | Description | Example |
|---|---|---|
| `APP_NAME` | Application display name | `CINEMIND` |
| `APP_ENV` | Runtime environment (`development`, `test`, `production`) | `development` |
| `DEBUG` | Enables SQLAlchemy SQL echo when `true` | `true` |
| `API_V1_PREFIX` | Base prefix for v1 API endpoints | `/api/v1` |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) | `INFO` |
| `DATABASE_URL` | Async PostgreSQL connection URI | `postgresql+asyncpg://postgres:your_password@localhost:5432/cinemind_db` |
| `TEST_DATABASE_URL` | Separate PostgreSQL database URI for `pytest` | `postgresql+asyncpg://postgres:your_password@localhost:5432/cinemind_test_db` |
| `CORS_ORIGINS` | Allowed frontend origins | `["http://localhost:5173","http://127.0.0.1:5173"]` |

---

## 8. Database Migration Commands (PowerShell)

Apply all Alembic migrations to PostgreSQL:

```powershell
alembic upgrade head
```

Rollback the last migration (to test downgrade):

```powershell
alembic downgrade -1
```

Preview generated SQL offline without connecting to PostgreSQL:

```powershell
alembic upgrade head --sql
```

Generate a new migration after future model changes:

```powershell
alembic revision --autogenerate -m "describe_change"
```

---

## 9. Running the Backend (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

The API will listen on `http://127.0.0.1:8000`.

---

## 10. Running Tests (PowerShell)

Make sure `cinemind_test_db` exists in PostgreSQL and `TEST_DATABASE_URL` is configured in `.env`, then run:

```powershell
.\.venv\Scripts\Activate.ps1
pytest -v
```

> **Note:** Integration tests in `tests/` automatically create and tear down tables inside `TEST_DATABASE_URL` (`cinemind_test_db`) and refuse to run against `DATABASE_URL`. If PostgreSQL is not reachable, DB-backed tests skip explicitly rather than faking results with SQLite.

---

## 11. Interactive API Documentation

- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

---

## 12. API Endpoint List

### Health
- `GET /health` — Verifies application responsiveness and live PostgreSQL connectivity (`SELECT 1`). Returns `200` when connected or `503` when unavailable.

### Authentication (`/api/v1/auth` — MongoDB `story_planner_auth`)
- `POST /api/v1/auth/login` — Authenticate with the single authorized credential (`username`, `password`); sets HttpOnly JWT cookie + CSRF cookie (`200` / `401` / `429` / `503`).
- `GET /api/v1/auth/me` — Verify active session cookie (`200` with `authenticated: true | false`).
- `POST /api/v1/auth/logout` — Revoke current JWT `jti` in MongoDB and clear cookies (`200`).

Manage or rotate the single authorized account interactively (no public registration or password-change HTTP endpoint exists):

```powershell
Set-Location backend
.\.venv\Scripts\python.exe scripts\manage_auth_credential.py status
.\.venv\Scripts\python.exe scripts\manage_auth_credential.py init
.\.venv\Scripts\python.exe scripts\manage_auth_credential.py update
```

### Projects (`/api/v1/projects`)
- `POST /api/v1/projects` — Create a project (`201`).
- `GET /api/v1/projects?limit=20&offset=0` — List projects paginated, ordered by `updated_at DESC` (`200`).
- `GET /api/v1/projects/{project_id}` — Get a project by UUID (`200` / `404`).
- `PATCH /api/v1/projects/{project_id}` — Partially update title, description, or status (`200` / `404`).
- `DELETE /api/v1/projects/{project_id}` — Delete project and cascade to its conversations and messages (`204` / `404`).

### Conversations (`/api/v1`)
- `POST /api/v1/projects/{project_id}/conversations` — Create a conversation under a project (`201` / `404`).
- `GET /api/v1/projects/{project_id}/conversations?limit=20&offset=0` — List project conversations paginated (`200` / `404`).
- `GET /api/v1/conversations/{conversation_id}` — Get conversation by UUID (`200` / `404`).
- `PATCH /api/v1/conversations/{conversation_id}` — Partially update conversation title or status (`200` / `404`).
- `DELETE /api/v1/conversations/{conversation_id}` — Delete conversation and cascade its messages (`204` / `404`).

### Messages (`/api/v1`)
- `POST /api/v1/conversations/{conversation_id}/messages` — Store a message (`system`, `user`, or `assistant`) and update conversation `updated_at` (`201` / `404` / `422`).
- `GET /api/v1/conversations/{conversation_id}/messages?limit=20&offset=0` — Retrieve messages in strict chronological order (`200` / `404`).

---

## 13. Troubleshooting Common Errors

- **`ConnectionRefusedError` / `DATABASE_UNAVAILABLE` (`503`)**:
  Ensure the PostgreSQL Windows service is running (`services.msc` -> `postgresql-x64-*` -> Start) and that host, port (`5432`), username, and password in `.env` match your local server.
- **`password authentication failed for user "postgres"`**:
  Verify the password in `DATABASE_URL` and `TEST_DATABASE_URL` inside `.env`.
- **`database "cinemind_db" does not exist`**:
  Create `cinemind_db` and `cinemind_test_db` via `psql` or pgAdmin, then run `alembic upgrade head`.
- **`ExecutionPolicy` blocks `Activate.ps1` in PowerShell**:
  Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once in PowerShell, or invoke `.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload` directly.
- **`ValidationError: DATABASE_URL Field required`**:
  Ensure `backend/.env` exists (copied from `.env.example`) before running `uvicorn` or `alembic`.
