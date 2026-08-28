"""Route package — exports all FastAPI routers for registration in main.py."""

from app.routes.websocket import router as ws_router

__all__ = ["ws_router"]
