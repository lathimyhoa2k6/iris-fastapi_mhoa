"""Training runs: the evaluation table of the five models, stored once per training."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

import security
from db_api.db import get_conn, utc_now


router = APIRouter(
    prefix="/model-runs",
    tags=["Kết quả đánh giá"],
)


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
    models: list[ModelRow] = Field(
        ...,
        min_length=1,
        max_length=10,
    )


def row_to_dict(cursor, row) -> dict:
    """Convert one pyodbc row to a dictionary."""
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def run_with_models(conn, run_row) -> dict:
    """Return one training run together with its model results."""

    run_cursor = conn.cursor()

    run_cursor.execute(
        """
        SELECT *
        FROM model_runs
        WHERE run_id = ?
        ORDER BY id
        """,
        run_row[0],
    )

    model_rows = run_cursor.fetchall()

    # Convert training_runs row
    run_dict = row_to_dict(
        run_cursor,
        run_row,
    )

    models = []

    for model_row in model_rows:
        model_dict = row_to_dict(
            run_cursor,
            model_row,
        )

        model_dict["best_params"] = json.loads(
            model_dict.get("best_params_json") or "{}"
        )

        models.append(model_dict)

    run_dict["models"] = models

    return run_dict


def store_run(
    conn,
    user_id: int | None,
    body: TrainingRunIn,
) -> int:
    """Insert one training run and its model rows."""

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO training_runs (
            user_id,
            created_at,
            trained_at,
            target,
            train_size,
            test_size,
            best_model,
            total_seconds
        )
        OUTPUT INSERTED.id
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        user_id,
        utc_now(),
        body.trained_at,
        body.target,
        body.train_size,
        body.test_size,
        body.best_model,
        body.total_seconds,
    )

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError(
            "Không lấy được ID của training run"
        )

    run_id = int(row[0])

    for model in body.models:
        cursor.execute(
            """
            INSERT INTO model_runs (
                run_id,
                model,
                label,
                r2,
                mae,
                mse,
                rmse,
                cv_r2_mean,
                cv_r2_std,
                train_seconds,
                predict_ms_per_sample,
                n_nonzero_coef,
                n_coefficients,
                best_params_json,
                is_best
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            run_id,
            model.model,
            model.label,
            model.r2,
            model.mae,
            model.mse,
            model.rmse,
            model.cv_r2_mean,
            model.cv_r2_std,
            model.train_seconds,
            model.predict_ms_per_sample,
            model.n_nonzero_coef,
            model.n_coefficients,
            json.dumps(
                model.best_params,
                ensure_ascii=False,
            ),
            int(model.model == body.best_model),
        )

    conn.commit()

    return run_id


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_model_run(
    body: TrainingRunIn,
    user: dict = Depends(security.current_user),
    conn=Depends(get_conn),
):
    """Store the evaluation table of one training run."""

    run_id = store_run(
        conn,
        user["id"],
        body,
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM training_runs
        WHERE id = ?
        """,
        run_id,
    )

    run = cursor.fetchone()

    if run is None:
        raise RuntimeError(
            "Không tìm thấy training run vừa tạo"
        )

    return run_with_models(
        conn,
        run,
    )


@router.get("")
def list_model_runs(
    limit: int = Query(
        20,
        ge=1,
        le=100,
    ),
    conn=Depends(get_conn),
):
    """Recent training runs, newest first."""

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            r.*,
            u.username
        FROM training_runs r
        LEFT JOIN users u
            ON u.id = r.user_id
        ORDER BY r.id DESC
        OFFSET 0 ROWS
        FETCH NEXT ? ROWS ONLY
        """,
        limit,
    )

    rows = cursor.fetchall()

    return {
        "runs": [
            run_with_models(conn, row)
            for row in rows
        ]
    }