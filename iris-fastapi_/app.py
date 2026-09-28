"""Iris flower classification API backed by an SVM model.

Run locally:  uvicorn app:app --reload
API docs:     http://127.0.0.1:8000/docs

This is the model module (SVM classification + five-model regression). With
SERVICE_MODE=single (the default, used on Render) it also mounts the database API
under /db and serves the web module at /, so one process runs all three modules.
run.sh / run.ps1 set SERVICE_MODE=split and start each module on its own port.
"""

from __future__ import annotations

import json
import mimetypes
import time
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import regression_api
import settings
import species as sp

BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "svm_model.pkl"
METRICS_PATH = BASE_DIR / "metrics.json"
STATIC_DIR = BASE_DIR / "static"
WEB_DIR = BASE_DIR / "web" / "public"
SINGLE_SERVICE = settings.SERVICE_MODE != "split"

# Windows can map .js to text/plain through the registry, which breaks ES modules.
mimetypes.add_type("application/javascript", ".js")

FEATURE_ORDER = ["sepal_length", "sepal_width", "petal_length", "petal_width"]

state: dict = {"model": None, "metrics": {}, "loaded_at": None, "error": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the model exactly once at startup instead of on every request."""
    try:
        state["model"] = joblib.load(MODEL_PATH)
        state["loaded_at"] = time.time()
        print(f"[api] Model loaded from {MODEL_PATH}")
    except Exception as exc:
        state["error"] = f"Không nạp được mô hình: {exc}"
        print(f"[api] ERROR: {state['error']}")

    if METRICS_PATH.exists():
        state["metrics"] = json.loads(METRICS_PATH.read_text(encoding="utf-8"))

    regression_api.load()
    if SINGLE_SERVICE:
        # Render's disk is wiped on every deploy: recreate the demo account and first run.
        try:
            import seed

            seed.seed_database()
        except Exception as exc:
            print(f"[api] WARNING: seeding the database failed: {exc}")
    yield
    state["model"] = None


app = FastAPI(
    title="Iris Classification API",
    description=(
        "Phân loại hoa Iris (setosa / versicolor / virginica) bằng mô hình SVM "
        "huấn luyện trên bộ dữ liệu Iris của UCI (Kaggle uciml/iris)."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.csv_list("MODEL_API_CORS_ORIGINS", "*"),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class IrisInput(BaseModel):
    """The four flower measurements, in centimetres."""

    sepal_length: float = Field(..., gt=0, le=30, examples=[5.1], description="Dài đài hoa (cm)")
    sepal_width: float = Field(..., gt=0, le=30, examples=[3.5], description="Rộng đài hoa (cm)")
    petal_length: float = Field(..., gt=0, le=30, examples=[1.4], description="Dài cánh hoa (cm)")
    petal_width: float = Field(..., gt=0, le=30, examples=[0.2], description="Rộng cánh hoa (cm)")


class PredictionOutput(BaseModel):
    """Everything the web page needs to render one prediction."""

    class_id: int
    species_key: str
    display_name: str
    vietnamese_name: str
    description: str
    confidence: float
    probabilities: dict[str, float]
    image_url: str
    alt_text: str
    source: str
    license: str
    source_url: str = ""


def get_model():
    """Return the loaded model, or fail with 503 if startup could not load it."""
    model = state.get("model")
    if model is None:
        raise HTTPException(status_code=503, detail=state.get("error") or "Mô hình chưa sẵn sàng")
    return model


@app.get("/", include_in_schema=False)
def home():
    """Single-service mode serves the web module; split mode points to its own server."""
    if not SINGLE_SERVICE:
        return RedirectResponse(settings.get("WEB_URL", "http://127.0.0.1:8080/"))
    index = WEB_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "Iris SVM API is running", "docs": "/docs"}


@app.get("/health", tags=["Hệ thống"])
def health():
    """Service health probe — Render calls this endpoint (healthCheckPath)."""
    healthy = state.get("model") is not None
    return {
        "status": "healthy" if healthy else "unhealthy",
        "model_loaded": healthy,
        "model_file": MODEL_PATH.name,
        "regression_loaded": regression_api.state["models"] is not None,
        "service_mode": "single" if SINGLE_SERVICE else "split",
        "uptime_seconds": round(time.time() - state["loaded_at"], 1) if state.get("loaded_at") else None,
    }


@app.get("/species", tags=["Thông tin"])
def species_list():
    """List the three species the model can recognise."""
    items = [sp.get(i) for i in range(len(sp.SPECIES))]
    return {"count": len(items), "species": items}


@app.get("/metrics", tags=["Thông tin"])
def metrics():
    """Evaluation figures for the running model (produced by train.py)."""
    if not state["metrics"]:
        raise HTTPException(status_code=404, detail="Chưa có metrics.json — hãy chạy train.py")
    m = state["metrics"]
    return {
        "generated_at": m.get("generated_at"),
        "data": {k: m["data"][k] for k in ("source_used", "n_samples", "train_size", "test_size") if k in m.get("data", {})},
        "model": m.get("model"),
        "performance": m.get("performance"),
        "kernel_comparison": m.get("kernel_comparison"),
    }


@app.post("/predict", response_model=PredictionOutput, tags=["Dự đoán"])
def predict(data: IrisInput):
    """Predict the species from the four measurements."""
    model = get_model()
    features = np.array([[getattr(data, name) for name in FEATURE_ORDER]], dtype=float)

    class_id = int(model.predict(features)[0])
    proba = model.predict_proba(features)[0]
    probabilities = {sp.BY_ID[i]["species_key"]: round(float(p), 4) for i, p in enumerate(proba)}

    info = sp.get(class_id)
    return PredictionOutput(
        class_id=class_id,
        species_key=info["species_key"],
        display_name=info["display_name"],
        vietnamese_name=info["vietnamese_name"],
        description=info["description"],
        confidence=round(float(proba[class_id]), 4),
        probabilities=probabilities,
        image_url=info["image_url"],
        alt_text=info["alt_text"],
        source=info["source"],
        license=info["license"],
        source_url=info.get("source_url", ""),
    )


app.include_router(regression_api.router)

if SINGLE_SERVICE:
    # One process for Render's free plan: database API under /db, web module at /.
    from db_api.main import app as db_app

    app.mount("/db", db_app)

    @app.get("/config.js", include_in_schema=False)
    def web_config():
        """API addresses for the web module: same origin, database API under /db."""
        return Response('window.APP_CONFIG = {"modelApi": "", "dbApi": "/db"};\n',
                        media_type="application/javascript")

    if WEB_DIR.exists():
        # Mounted last so every API route above keeps priority over static files.
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
