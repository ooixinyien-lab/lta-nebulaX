"""Runtime configuration for authentication, persistence and scheduling."""
from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator

ROOT = Path(__file__).resolve().parents[2]
DEMO_USERS = {
    "demo-track": {"id": "demo-track", "name": "Track team", "role": "requester"},
    "demo-signals": {"id": "demo-signals", "name": "Systems team", "role": "requester"},
    "demo-officer": {"id": "demo-officer", "name": "Planning officer", "role": "officer"},
}

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    app_env: Literal["development", "test", "production"] = "development"
    auth_mode: Literal["demo", "supabase"] = "demo"
    solver_engine: Literal["cp_sat", "demo_search"] = "cp_sat"
    ui_demo: bool = False
    solver_time_limit_seconds: float = 8.0
    database_path: str = str(ROOT / "backend" / "nebulax.sqlite3")
    database_url: str = ""
    upload_storage_path: str = str(ROOT / "backend" / "uploads")
    dataset_path: str = str(ROOT / "data" / "comprehensive_synthetic_data.json")
    official_data_path: str = str(ROOT / "data")
    supabase_url: str = ""
    supabase_publishable_key: str = ""
    officer_user_ids: str = ""

    @property
    def effective_database_url(self) -> str:
        """Return the configured server URL or a local SQLite fallback."""
        return self.database_url or f"sqlite:///{Path(self.database_path).resolve().as_posix()}"

    @property
    def officer_ids(self) -> set[str]:
        return {s.strip() for s in self.officer_user_ids.split(",") if s.strip()}

    @model_validator(mode="after")
    def validate_environment(self):
        if self.app_env == "production" and self.auth_mode == "demo":
            raise ValueError("Demo identity is NOT authentication. Refusing production + demo mode.")
        if not 0.1 <= self.solver_time_limit_seconds <= 60:
            raise ValueError("Solver time limit must be between 0.1 and 60 seconds")
        if not self.database_url and not Path(self.dataset_path).is_file():
            raise ValueError(f"Dataset file does not exist: {self.dataset_path}")
        if self.auth_mode == "supabase":
            if not self.supabase_url.startswith("https://"):
                raise ValueError("Supabase mode requires an HTTPS project URL")
            if not self.supabase_publishable_key.startswith("sb_publishable_"):
                raise ValueError("Use the Supabase publishable key (sb_publishable_...), never a secret key")
        return self
