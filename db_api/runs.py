"""Training runs: the evaluation table of the five models, stored once per training."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

import security
from db_api.db import get_conn, utc_now

router = APIRouter(prefix="/model-runs", tags=["Kết quả đánh giá"])


class ModelRow(BaseModel):
    model: str
    label: str | None = None
    r2: float
    mae: float
    mse: float
    rmse: float
    cv_r2_mean: float
    cv_r2_std: float
    train_seconds: float
    predict_ms_per_sample: float
    n_nonzero_coef: int
    n_coefficients: int
    best_params: dict = {}


class TrainingRunIn(BaseModel):
    trained_at: str | None = None
    target: str = "petal_width"
    train_size: int | None = None
    test_size: int | None = None
    best_model: str
    total_seconds: float | None = None
    models: list[ModelRow] = Field(..., min_length=1, max_length=10)


def run_with_models(conn, run_row) -> dict:
    models = conn.execute("SELECT * FROM model_runs WHERE run_id = ? ORDER BY id", (run_row["id"],)).fetchall()
    out = dict(run_row)
    out["models"] = [{**dict(m), "best_params": json.loads(m["best_params_json"] or "{}")} for m in models]
    return out


def store_run(conn, user_id: int | None, body: TrainingRunIn) -> int:
    """Insert one training_runs row and its model_runs rows; returns the run id."""
    cur = conn.execute(
        """INSERT INTO training_runs (user_id, created_at, trained_at, target, train_size, test_size,
                                      best_model, total_seconds) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, utc_now(), body.trained_at, body.target, body.train_size, body.test_size,
         body.best_model, body.total_seconds),
    )
    run_id = cur.lastrowid
    for m in body.models:
        conn.execute(
            """INSERT INTO model_runs (run_id, model, label, r2, mae, mse, rmse, cv_r2_mean, cv_r2_std,
                   train_seconds, predict_ms_per_sample, n_nonzero_coef, n_coefficients,
                   best_params_json, is_best)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (run_id, m.model, m.label, m.r2, m.mae, m.mse, m.rmse, m.cv_r2_mean, m.cv_r2_std,
             m.train_seconds, m.predict_ms_per_sample, m.n_nonzero_coef, m.n_coefficients,
             json.dumps(m.best_params, ensure_ascii=False), int(m.model == body.best_model)),
        )
    conn.commit()
    return run_id


@router.post("", status_code=status.HTTP_201_CREATED)
def create_model_run(body: TrainingRunIn, user: dict = Depends(security.current_user), conn=Depends(get_conn)):
    """Store the evaluation table of the five models from one training run."""
    run_id = store_run(conn, user["id"], body)
    run = conn.execute("SELECT * FROM training_runs WHERE id = ?", (run_id,)).fetchone()
    return run_with_models(conn, run)


@router.get("")
def list_model_runs(limit: int = Query(20, ge=1, le=100), conn=Depends(get_conn)):
    """Recent training runs, newest first, each with its five model rows."""
    rows = conn.execute(
        """SELECT r.*, u.username FROM training_runs r LEFT JOIN users u ON u.id = r.user_id
           ORDER BY r.id DESC LIMIT ?""", (limit,)).fetchall()
    return {"runs": [run_with_models(conn, r) for r in rows]}
