"""API Routes for Tradegent Agent UI."""
from .auth import router as auth_router
from .admin import router as admin_router
from .users import router as users_router
from .settings import router as settings_router
from .trades import router as trades_router
from .watchlist import router as watchlist_router
from .scanners import router as scanners_router
from .sessions import router as sessions_router
# Safety and automation routes
from .automation import router as automation_router
from .alerts import router as alerts_router
from .notifications import router as notifications_router
# Analytics routes
from .analytics import router as analytics_router
# Order and schedule routes
from .orders import router as orders_router
from .schedules import router as schedules_router
# Graph visualization routes
from .graph import router as graph_router

__all__ = [
    "auth_router",
    "admin_router",
    "users_router",
    "settings_router",
    "trades_router",
    "watchlist_router",
    "scanners_router",
    "sessions_router",
    # Safety and automation
    "automation_router",
    "alerts_router",
    "notifications_router",
    # Analytics
    "analytics_router",
    # Orders and schedules
    "orders_router",
    "schedules_router",
    # Graph
    "graph_router",
]
