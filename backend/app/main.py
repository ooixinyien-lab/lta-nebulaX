"""One server serves both the API and the lightweight, no-build frontend."""
from contextlib import asynccontextmanager
import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings, ROOT
from .database import Database
from .db import create_engine_and_session, create_schema
from .db.seed import seed_official_instance
from .api.ps1_routes import router as ps1_router

try:
    from .ps1.ps1_routes import router as ps1_ui_router
except Exception:
    ps1_ui_router = None

try:
    from .api.routes import router
except ModuleNotFoundError as exc:
    # The historical transition router depends on the retired synthetic
    # models module. Keep the official PS1 API bootable while that router is
    # removed or migrated separately.
    if exc.name != "backend.app.models":
        raise
    router = None


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    db = Database(settings.database_path, settings.dataset_path)
    ps1_db = create_engine_and_session(settings.effective_database_url)
    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        if settings.app_env != "production":
            create_schema(ps1_db)
        seed_official_instance(ps1_db, settings.official_data_path)
        yield
    app = FastAPI(title="NEBULA X Rail Scheduling Engine", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.ps1_db = ps1_db

    @app.exception_handler(sqlite3.OperationalError)
    async def database_error(request: Request, exc):
        return JSONResponse(status_code=503, content={"detail": "Database is busy or unavailable. Retry; no partial change was saved."})

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    if router is not None:
        app.include_router(router)
    app.include_router(ps1_router)
    if ps1_ui_router is not None:
        app.include_router(ps1_ui_router)
    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "frontend" / "index.html")
    return app

app = create_app()
