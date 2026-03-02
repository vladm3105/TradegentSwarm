"""API Routes for Tradegent Agent UI."""
from .auth import router as auth_router
from .admin import router as admin_router
from .users import router as users_router
from .settings import router as settings_router
from .trades import router as trades_router
from .watchlist import router as watchlist_router
from .scanners import router as scanners_router
from .sessions import router as sessions_router

__all__ = [
    "auth_router",
    "admin_router",
    "users_router",
    "settings_router",
    "trades_router",
    "watchlist_router",
    "scanners_router",
    "sessions_router",
]
