"""Route modules for the FastAPI server.

Each module exports a `build_router(...)` factory that returns an
APIRouter with the relevant endpoints. The factory takes the shared
context it needs (storage path, auth manager, current_user dependency).

This split keeps `app.py` short and lets new endpoints land in the
right file without scrolling through 350 lines.
"""
