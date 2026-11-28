# CINEMIND (StoryForge) — AI Story & Shot Planner

**CINEMIND** (*Contextual Intelligence for Narrative, Emotion, Meaning and Intelligent Direction*) transforms a creator's one-line idea or written story into a production-ready, scene-wise and shot-wise cinematic plan.

## Repository Structure

```text
.
├── frontend/               # React 18 + TypeScript + Vite ChatGPT-style UI + Login Gate
├── backend/                # FastAPI + PostgreSQL (Story/Planner) + MongoDB (Single-Credential Auth)
├── docs/
│   ├── architecture.md     # Modular monolith & engine integration architecture
│   └── implementation_plan.md
└── .gitignore
```

## Database Responsibilities

- **MongoDB (`story_planner_auth`)**: Exclusively stores the single authorized login account (`authorized_credentials`, `_id: "authorized_account"`) with Argon2id password hashes and JWT revocation tokens (`revoked_tokens`).
- **PostgreSQL (`cinemind_db`)**: Exclusively stores CINEMIND application data (projects, conversations, messages, stories, scenes, shots, continuity, and usage records).

## Quick Links

- **Frontend setup:** See `frontend/package.json` (`npm run dev` on `http://localhost:5173`)
- **Backend, MongoDB Auth & Windows PowerShell guide:** See [backend/README.md](backend/README.md)
- **Architecture:** See [docs/architecture.md](docs/architecture.md)
- **Roadmap:** See [docs/implementation_plan.md](docs/implementation_plan.md)
