"""Prediction history: each user reads and edits only their own rows."""

from __future__ import annotations

import json
import math
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

import security
from db_api.db import date_bounds, get_conn, utc_now


router = APIRouter(
    prefix="/predictions",
    tags=["Lịch sử dự đoán"],
)


class PredictionIn(BaseModel):
    task: Literal["regression", "classification"]
    model: str = Field(..., min_length=1, max_length=64)
    input: dict
    predicted_value: float | None = None
    predicted_label: str | None = Field(None, max_length=64)
    actual_value: float | None = Field(None, ge=0, le=100)
    runtime_ms: float | None = Field(None, ge=0)
    batch_id: str | None = Field(None, max_length=64)


class PredictionBatch(BaseModel):
    items: list[PredictionIn] = Field(
        ...,
        min_length=1,
        max_length=20,
    )


class ActualValue(BaseModel):
    actual_value: float | None = Field(
        ...,
        ge=0,
        le=100,
    )


def row_to_dict(cursor, row) -> dict:
    """Convert one pyodbc row to a normal dictionary."""
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def prediction_out(cursor, row) -> dict:
    """Convert a SQL Server prediction row to API output."""
    d = row_to_dict(cursor, row)
    d["input"] = json.loads(d.pop("input_json"))
    return d


def history_filter(
    user_id: int,
    model: str | None,
    date_from: date | None,
    date_to: date | None,
):
    """Build SQL WHERE clause and parameters."""

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            422,
            "Ngày bắt đầu phải trước ngày kết thúc",
        )

    where = ["user_id = ?"]
    args = [user_id]

    if model:
        where.append("model = ?")
        args.append(model)

    start, end = date_bounds(
        date_from,
        date_to,
    )

    if start:
        where.append("created_at >= ?")
        args.append(start)

    if end:
        where.append("created_at < ?")
        args.append(end)

    return " AND ".join(where), args


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_predictions(
    body: PredictionBatch,
    user: dict = Depends(security.current_user),
    conn=Depends(get_conn),
):
    """Store one or several predictions for the current user."""

    # Lưu thời gian theo UTC.
    # Giao diện sẽ chuyển sang giờ Việt Nam khi hiển thị.
    created_at = utc_now()

    batch_id = (
        uuid.uuid4().hex[:12]
        if len(body.items) > 1
        else None
    )

    ids = []

    cursor = conn.cursor()

    for item in body.items:
        cursor.execute(
            """
            INSERT INTO predictions (
                user_id,
                created_at,
                task,
                model,
                input_json,
                predicted_value,
                predicted_label,
                actual_value,
                runtime_ms,
                batch_id
            )
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            user["id"],
            created_at,
            item.task,
            item.model,
            json.dumps(
                item.input,
                ensure_ascii=False,
            ),
            item.predicted_value,
            item.predicted_label,
            item.actual_value,
            item.runtime_ms,
            item.batch_id or batch_id,
        )

        row = cursor.fetchone()

        if row is not None:
            ids.append(int(row[0]))

    conn.commit()

    return {
        "ids": ids,
        "created_at": created_at,
        "batch_id": batch_id,
    }


@router.get("")
def list_predictions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    model: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    user: dict = Depends(security.current_user),
    conn=Depends(get_conn),
):
    """Return the current user's prediction history."""

    where, args = history_filter(
        user["id"],
        model,
        date_from,
        date_to,
    )

    cursor = conn.cursor()

    cursor.execute(
        f"""
        SELECT COUNT(*)
        FROM predictions
        WHERE {where}
        """,
        *args,
    )

    total = cursor.fetchone()[0]

    offset = (page - 1) * page_size

    cursor.execute(
        f"""
        SELECT *
        FROM predictions
        WHERE {where}
        ORDER BY created_at DESC, id DESC
        OFFSET ? ROWS
        FETCH NEXT ? ROWS ONLY
        """,
        *args,
        offset,
        page_size,
    )

    rows = cursor.fetchall()

    items = [
        prediction_out(cursor, row)
        for row in rows
    ]

    cursor.execute(
        """
        SELECT DISTINCT model
        FROM predictions
        WHERE user_id = ?
        ORDER BY model
        """,
        user["id"],
    )

    models = [
        row[0]
        for row in cursor.fetchall()
    ]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(
            1,
            math.ceil(total / page_size),
        ),
        "models": models,
    }


@router.patch("/{prediction_id}")
def set_actual_value(
    prediction_id: int,
    body: ActualValue,
    user: dict = Depends(security.current_user),
    conn=Depends(get_conn),
):
    """Record or clear actual value."""

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE predictions
        SET actual_value = ?
        WHERE id = ?
          AND user_id = ?
        """,
        body.actual_value,
        prediction_id,
        user["id"],
    )

    conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(
            404,
            "Không tìm thấy bản ghi",
        )

    cursor.execute(
        """
        SELECT *
        FROM predictions
        WHERE id = ?
        """,
        prediction_id,
    )

    row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            404,
            "Không tìm thấy bản ghi",
        )

    return prediction_out(cursor, row)