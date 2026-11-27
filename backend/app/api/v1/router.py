from fastapi import APIRouter

from app.api.v1.endpoints import conversations, messages, projects

api_router = APIRouter()
api_router.include_router(projects.router)
api_router.include_router(conversations.router)
api_router.include_router(messages.router)
