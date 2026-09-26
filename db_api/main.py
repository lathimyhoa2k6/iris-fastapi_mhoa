"""Database API: users and JWT auth, prediction history, training runs, Excel export.

Run on its own port:  uvicorn db_api.main:app --port 8001
In single-service mode app.py mounts this app under /db instead.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import settings
from db_api import auth, export, history, runs
from db_api.db import get_conn

app = FastAPI(
    title="Iris Database API",
    description="Người dùng (bcrypt + JWT), lịch sử dự đoán, kết quả đánh giá các lần train và xuất Excel.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.csv_list(
        "CORS_ORIGINS", "http://127.0.0.1:8080,http://localhost:8080,http://127.0.0.1:8000,http://localhost:8000"
    ),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.get("/health", tags=["Hệ thống"])
def health(conn=Depends(get_conn)):
    versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
    return {"status": "healthy", "database": settings.db_path().name, "migrations": versions}


app.include_router(auth.router)
app.include_router(history.router)
app.include_router(runs.router)
app.include_router(export.router)
