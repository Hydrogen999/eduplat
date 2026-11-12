from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api.v1 import auth, users, study, payments, exams, admin

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs" if settings.ENV != "prod" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN, "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    import logging
    logging.getLogger("app").exception("unhandled", exc_info=exc)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)

for mod in (auth, users, study, payments, exams, admin):
    app.include_router(mod.router, prefix=settings.API_V1_PREFIX)

@app.get("/healthz")
async def health():
    return {"ok": True}

# Serve frontend — mounted LAST so API routes take priority
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")