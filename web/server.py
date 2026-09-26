"""Web module: serves the static front-end on its own port.

Run:  uvicorn web.server:app --port 8080

It never loads a model or opens the database; the pages only call the model API
and the database API, whose addresses come from /config.js (MODEL_API_URL,
DB_API_URL environment variables).
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

import settings

WEB_DIR = Path(__file__).resolve().parent / "public"

# Windows can map .js to text/plain through the registry, which breaks ES modules.
mimetypes.add_type("application/javascript", ".js")

app = FastAPI(title="Iris Web", docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/config.js", include_in_schema=False)
def config_js():
    config = {
        "modelApi": settings.get("MODEL_API_URL", "http://127.0.0.1:8000").rstrip("/"),
        "dbApi": settings.get("DB_API_URL", "http://127.0.0.1:8001").rstrip("/"),
    }
    return Response(f"window.APP_CONFIG = {json.dumps(config)};\n", media_type="application/javascript")


@app.get("/health", include_in_schema=False)
def health():
    return {"status": "healthy", "module": "web"}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
