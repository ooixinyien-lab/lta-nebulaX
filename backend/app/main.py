"""One server serves both the API and the lightweight, no-build frontend."""
from contextlib import asynccontextmanager
import sqlite3
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings, ROOT
from .database import Database
from .db.seed import seed_official_instance
from .api.ps1_routes import router as ps1_router

try:
    from .api.routes import router
except ModuleNotFoundError as exc:
    # The historical transition router depends on the retired synthetic
    # models module. Keep the official PS1 API bootable while that router is
    # removed or migrated separately.
    if exc.name != "backend.app.models":
        raise
    logging.getLogger(__name__).warning("Legacy API unavailable: baseline backend.app.models is missing; PS1 routes remain available")
    router = None


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    db = Database(settings.database_path, settings.dataset_path)
    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        seed_official_instance(db, settings.official_data_path)
        yield
    app = FastAPI(title="NebulaX scheduling API", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db

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
    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "frontend" / "index.html")
    return app

app = create_app()
