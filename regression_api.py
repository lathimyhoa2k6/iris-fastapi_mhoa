"""Model-API routes for the five-model regression comparison (target: petal_width).

Mounted by app.py next to the SVM classification routes, which stay unchanged.
Training needs a valid JWT issued by the database API; everything else is public.
"""

from __future__ import annotations

import threading
import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import dataset
import regression as reg
import security

router = APIRouter()

state: dict = {"models": None, "report": None, "error": None}
_train_lock = threading.Lock()

ModelKey = Literal["linear", "polynomial", "ridge", "lasso", "elasticnet"]
RegularizedKey = Literal["ridge", "lasso", "elasticnet"]
Species = Literal["setosa", "versicolor", "virginica"]


def load() -> None:
    """Load the saved regression models once at startup (called from app.py's lifespan)."""
    try:
        state["models"], state["report"] = reg.load()
        state["error"] = None
        print(f"[api] Regression models loaded from {reg.MODELS_PATH.name}")
    except Exception as exc:
        state["error"] = f"Chưa có mô hình hồi quy: {exc}"
        print(f"[api] WARNING: {state['error']}")


def _require_models() -> tuple[dict, dict]:
    if state["models"] is None:
        raise HTTPException(503, state["error"] or "Mô hình hồi quy chưa sẵn sàng — hãy train trước")
    return state["models"], state["report"]


class RegressionInput(BaseModel):
    """Inputs of the regression task: three measurements (cm) and the species."""

    sepal_length: float = Field(..., gt=0, le=30, examples=[5.8], description="Dài đài hoa (cm)")
    sepal_width: float = Field(..., gt=0, le=30, examples=[3.0], description="Rộng đài hoa (cm)")
    petal_length: float = Field(..., gt=0, le=30, examples=[4.35], description="Dài cánh hoa (cm)")
    species: Species = Field(..., examples=["versicolor"], description="Loài hoa")


class SinglePredictInput(RegressionInput):
    model: ModelKey = Field("ridge", description="Mô hình dùng để dự đoán")


def _public_report(report: dict) -> dict:
    """The report without the bulky path / diagnostics arrays."""
    return {k: v for k, v in report.items() if k not in ("regularization_paths", "diagnostics")}


@router.get("/regression/metrics", tags=["Hồi quy"])
def regression_metrics():
    """Comparison table of the five models from the latest training run."""
    _, report = _require_models()
    return _public_report(report)


@router.post("/regression/train", tags=["Hồi quy"])
def regression_train(user: dict = Depends(security.current_user)):
    """Retrain the five models (GridSearchCV + KFold 5), save them and return the new table.

    Requires `Authorization: Bearer <token>` from the database API.
    """
    if not _train_lock.acquire(blocking=False):
        raise HTTPException(409, "Đang có một lần train khác chạy, hãy thử lại sau ít giây")
    try:
        started = time.perf_counter()
        models, report = reg.train_all(log=lambda *_: None)
        report["total_seconds"] = round(time.perf_counter() - started, 3)
        report["trained_by"] = user["username"]
        reg.save(models, report)
        state["models"], state["report"], state["error"] = models, report, None
        return _public_report(report)
    finally:
        _train_lock.release()


@router.post("/regression/predict", tags=["Hồi quy"])
def regression_predict(data: SinglePredictInput):
    """Predict petal_width with one model; runtime measured with time.perf_counter."""
    models, _ = _require_models()
    X = reg.make_features([[data.sepal_length, data.sepal_width, data.petal_length]], [data.species])
    value, ms = reg.predict_one(models[data.model], X)
    return {
        "model": data.model,
        "label": reg.MODEL_LABELS[data.model],
        "target": reg.TARGET,
        "prediction": round(value, 4),
        "runtime_ms": round(ms, 4),
        "input": data.model_dump(exclude={"model"}),
    }


@router.post("/regression/arena", tags=["Hồi quy"])
def regression_arena(data: RegressionInput):
    """Model arena: all five models on the same input, with consensus and deviations."""
    models, _ = _require_models()
    started = time.perf_counter()
    result = reg.arena(models, data.sepal_length, data.sepal_width, data.petal_length, data.species)
    result["total_ms"] = round((time.perf_counter() - started) * 1000, 4)
    return result


@router.get("/regression/regularization-path", tags=["Hồi quy"])
def regression_path(model: RegularizedKey = Query("lasso")):
    """Coefficients (standardised inputs) as alpha grows on a log scale."""
    _, report = _require_models()
    return report["regularization_paths"][model]


@router.get("/regression/diagnostics", tags=["Hồi quy"])
def regression_diagnostics(model: ModelKey = Query("ridge")):
    """Actual vs predicted and residuals on the test set for one model."""
    _, report = _require_models()
    diag = report["diagnostics"]
    row = next(r for r in report["models"] if r["model"] == model)
    return {
        "model": model,
        "label": reg.MODEL_LABELS[model],
        "metrics": {k: row[k] for k in ("r2", "mae", "rmse")},
        "inputs": diag["test_inputs"],
        **diag["by_model"][model],
    }


@router.get("/dataset/summary", tags=["Dữ liệu"])
def dataset_summary():
    """Per-species statistics computed from data/Iris.csv (overview page)."""
    return dataset.summary()


@router.get("/dataset/pca", tags=["Dữ liệu"])
def dataset_pca():
    """PCA 2D of the 150 standardised samples (advanced analysis page)."""
    return dataset.pca()
