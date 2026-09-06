"""One server serves both the API and the lightweight, no-build frontend."""
from contextlib import asynccontextmanager
import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings, ROOT
from .database import Database
from .api.routes import router


def create_app(settings: Settings | None = None):
    settings = settings or Settings()
    db = Database(settings.database_path)
    @asynccontextmanager
    async def lifespan(app):
        db.initialize()
        yield
    app = FastAPI(title="RailPlan starter API", version="0.1.0", lifespan=lifespan)
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

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(ROOT / "frontend" / "index.html")
    return app

app = create_app()
