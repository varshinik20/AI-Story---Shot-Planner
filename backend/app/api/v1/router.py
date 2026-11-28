from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    ai_chat,
    auth,
    chat,
    conversations,
    intent,
    messages,
    narrative,
    planner,
    projects,
    scenes,
    shots,
    stories,
    usage,
    validation,
)
from app.dependencies import require_authenticated_user

api_router = APIRouter()

# Authentication endpoints (login, me, logout) manage session state directly.
api_router.include_router(auth.router)

# All application domain endpoints require an active authenticated session (+ CSRF for mutations).
protected_router = APIRouter(dependencies=[Depends(require_authenticated_user)])
protected_router.include_router(projects.router)
protected_router.include_router(conversations.router)
protected_router.include_router(messages.router)
protected_router.include_router(ai_chat.router)
protected_router.include_router(chat.router)
protected_router.include_router(stories.router)
protected_router.include_router(intent.router)
protected_router.include_router(narrative.router)
protected_router.include_router(scenes.router)
protected_router.include_router(shots.router)
protected_router.include_router(validation.router)
protected_router.include_router(planner.router)
protected_router.include_router(usage.router)

api_router.include_router(protected_router)
