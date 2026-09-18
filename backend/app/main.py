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
from .api.ps1_calendar_routes import router as ps1_calendar_router
from .api.ps1_network_routes import router as ps1_network_router


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
    app = FastAPI(title="NEBULA X Rail Scheduling Engine", version="0.2.0", lifespan=lifespan)
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
    app.include_router(ps1_network_router)
    app.include_router(ps1_calendar_router)
    if ps1_ui_router is not None:
        app.include_router(ps1_ui_router)
    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")

    nebula_dist = ROOT / "nebula-ui" / "dist"
    if nebula_dist.is_dir():
        nebula_assets = nebula_dist / "assets"
        if nebula_assets.is_dir():
            app.mount("/network-map/assets", StaticFiles(directory=nebula_assets), name="nebula_nm_assets")
            app.mount("/assets", StaticFiles(directory=nebula_assets), name="nebula_assets")

        @app.get("/network-map", include_in_schema=False)
        @app.get("/network-map/{path:path}", include_in_schema=False)
        @app.get("/calendar", include_in_schema=False)
        def network_map_page(path: str = ""):
            target_file = nebula_dist / path if path else nebula_dist / "index.html"
            if target_file.is_file():
                return FileResponse(target_file)
            return FileResponse(nebula_dist / "index.html")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "frontend" / "index.html")
    return app

app = create_app()
