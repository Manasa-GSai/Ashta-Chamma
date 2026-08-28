"""FastAPI route handlers (controllers).

Each module in this package exports a single ``router = APIRouter(...)``
instance that is registered in ``server/main.py``.  Route handlers are thin:
parse request → call service → format response.  No business logic lives here.
"""
