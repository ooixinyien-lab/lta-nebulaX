"""One server serves both the API and the lightweight, no-build frontend."""
from contextlib import asynccontextmanager
import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings, ROOT
from .database import Database
from .db.seed import seed_official_instance
from .db.reset import should_auto_seed
from .api.ps1_routes import router as ps1_router
from .api.ps1_calendar_routes import router as ps1_calendar_router
from .api.ps1_network_routes import router as ps1_network_router
from .api.schedule_insertion_routes import router as schedule_insertion_router
from .api.planning_routes import router as planning_router


try:
    from .ps1.ps1_routes import router as ps1_ui_router
except Exception:
    ps1_ui_router = None

def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    db = Database(settings.database_path, settings.dataset_path)
    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        with db.connection() as connection:
            auto_seed = should_auto_seed(connection)
        if auto_seed:
            inst_id, rev_id = seed_official_instance(db, settings.official_data_path)
            app.state.official_instance_id = inst_id
            app.state.official_revision_id = rev_id
        yield
    app = FastAPI(title="ForRail Rail Scheduling Engine", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.official_instance_id = None
    app.state.official_revision_id = None

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

    app.include_router(ps1_router)
    app.include_router(ps1_network_router)
    app.include_router(ps1_calendar_router)
    app.include_router(schedule_insertion_router)
    app.include_router(planning_router)
    if ps1_ui_router is not None:
        app.include_router(ps1_ui_router)
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
        """Redirect to modern UI when built, otherwise FastAPI docs."""
        if (ROOT / "nebula-ui" / "dist" / "index.html").is_file():
            return RedirectResponse(url="/network-map", status_code=307)
        return RedirectResponse(url="/docs", status_code=307)
    return app

app = create_app()
