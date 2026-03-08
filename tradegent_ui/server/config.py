"""Configuration for Tradegent Agent UI."""
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache

# Get the directory containing this config file
CONFIG_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    agui_host: str = "0.0.0.0"
    agui_port: int = 8080
    frontend_url: str = "http://localhost:3000"

    # LLM
    llm_provider: str = "openrouter"
    llm_api_key: str = ""
    llm_model: str = "google/gemini-2.0-flash-001"
    llm_base_url: str = "https://openrouter.ai/api/v1"

    # MCP Servers
    ib_mcp_url: str = "http://localhost:8100/mcp/"
    rag_mcp_cmd: str = "python -m tradegent.rag.mcp_server"
    graph_mcp_cmd: str = "python -m tradegent.graph.mcp_server"
    mcp_cwd: str = "/opt/data/tradegent_swarm"

    # Database
    pg_host: str = "localhost"
    pg_port: int = 5433
    pg_user: str = "tradegent"
    pg_pass: str = ""
    pg_db: str = "tradegent"

    # Timeouts
    mcp_timeout: float = 60.0
    llm_timeout: float = 120.0
    task_timeout: float = 600.0  # 10 min for long-running analyses

    # Runtime environment and feature flags
    app_env: str = "development"  # development | test | production
    debug: bool = False
    allow_demo_tokens: bool = False

    # ==========================================================================
    # ADMIN USER (Superuser) - REQUIRED
    # Similar to PostgreSQL's postgres user, this is the system superuser.
    # Credentials MUST be set in .env file. Authentication is ALWAYS enabled.
    # ==========================================================================
    admin_email: str = ""  # REQUIRED: e.g., "admin@tradegent.local"
    admin_password: str = ""  # REQUIRED: plaintext password (hashed at runtime)
    admin_name: str = "System Administrator"

    # Demo Account (optional, for testing)
    demo_email: str = ""
    demo_password: str = ""

    # JWT settings for local auth (when Auth0 is not configured)
    jwt_secret: str = ""  # Generate with: openssl rand -base64 32
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Auth0 Configuration (optional - leave empty for built-in auth)
    auth0_domain: str = ""  # e.g., "your-tenant.auth0.com"
    auth0_client_id: str = ""
    auth0_client_secret: str = ""
    auth0_audience: str = "https://tradegent-api.local"
    auth0_algorithms: list[str] = ["RS256"]

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60

    # Session management
    max_sessions_per_user: int = 5

    @property
    def auth0_configured(self) -> bool:
        """Check if Auth0 is configured."""
        return bool(self.auth0_domain and self.auth0_client_id)

    @property
    def admin_configured(self) -> bool:
        """Check if admin user is configured. REQUIRED for startup."""
        return bool(self.admin_email and self.admin_password)

    def validate_required(self) -> None:
        """Validate required configuration. Raises ValueError if missing."""
        errors = []
        if not self.admin_email:
            errors.append("ADMIN_EMAIL is required in .env")
        if not self.admin_password:
            errors.append("ADMIN_PASSWORD is required in .env")
        if not self.jwt_secret:
            errors.append("JWT_SECRET is required in .env (generate with: openssl rand -base64 32)")

        # Basic secret quality checks
        if self.admin_password and len(self.admin_password) < 12:
            errors.append("ADMIN_PASSWORD must be at least 12 characters")
        if self.jwt_secret and len(self.jwt_secret) < 32:
            errors.append("JWT_SECRET appears too short (expected >= 32 chars)")

        env_value = (self.app_env or "development").strip().lower()
        if env_value not in {"development", "test", "production"}:
            errors.append("APP_ENV must be one of: development, test, production")

        # Never allow demo-token bypass outside dev/test.
        if self.allow_demo_tokens and env_value not in {"development", "test"}:
            errors.append("ALLOW_DEMO_TOKENS may only be enabled in development or test")

        # Production should never run with DEBUG enabled.
        if self.debug and env_value == "production":
            errors.append("DEBUG=true is not allowed when APP_ENV=production")

        if errors:
            raise ValueError(
                "Missing required configuration:\n" +
                "\n".join(f"  - {e}" for e in errors)
            )

    class Config:
        env_prefix = ""
        env_file = str(CONFIG_DIR / ".env")
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
