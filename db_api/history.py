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

router = APIRouter(prefix="/predictions", tags=["Lịch sử dự đoán"])


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
    items: list[PredictionIn] = Field(..., min_length=1, max_length=20)


class ActualValue(BaseModel):
    actual_value: float | None = Field(..., ge=0, le=100)


def prediction_out(row) -> dict:
    d = dict(row)
    d["input"] = json.loads(d.pop("input_json"))
    return d


def history_filter(user_id: int, model: str | None, date_from: date | None, date_to: date | None):
    """SQL WHERE clause + args for the user's rows, by model and local calendar day."""
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Ngày bắt đầu phải trước ngày kết thúc")
    where, args = ["user_id = ?"], [user_id]
    if model:
        where.append("model = ?")
        args.append(model)
    start, end = date_bounds(date_from, date_to)
    if start:
        where.append("created_at >= ?")
        args.append(start)
    if end:
        where.append("created_at < ?")
        args.append(end)
    return " AND ".join(where), args


@router.post("", status_code=status.HTTP_201_CREATED)
def create_predictions(body: PredictionBatch, user: dict = Depends(security.current_user), conn=Depends(get_conn)):
    """Store one or several predictions (e.g. the five arena results) for the current user."""
    created_at = utc_now()
    batch_id = uuid.uuid4().hex[:12] if len(body.items) > 1 else None
    ids = []
    for item in body.items:
        cur = conn.execute(
            """INSERT INTO predictions (user_id, created_at, task, model, input_json, predicted_value,
                                        predicted_label, actual_value, runtime_ms, batch_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user["id"], created_at, item.task, item.model, json.dumps(item.input, ensure_ascii=False),
             item.predicted_value, item.predicted_label, item.actual_value, item.runtime_ms,
             item.batch_id or batch_id),
        )
        ids.append(cur.lastrowid)
    conn.commit()
    return {"ids": ids, "created_at": created_at, "batch_id": batch_id}


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
    """The current user's history, newest first, filtered by model and local date."""
    where, args = history_filter(user["id"], model, date_from, date_to)
    total = conn.execute(f"SELECT COUNT(*) FROM predictions WHERE {where}", args).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM predictions WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        [*args, page_size, (page - 1) * page_size],
    ).fetchall()
    models = [r[0] for r in conn.execute(
        "SELECT DISTINCT model FROM predictions WHERE user_id = ? ORDER BY model", (user["id"],))]
    return {
        "items": [prediction_out(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, math.ceil(total / page_size)),
        "models": models,
    }


@router.patch("/{prediction_id}")
def set_actual_value(prediction_id: int, body: ActualValue,
                     user: dict = Depends(security.current_user), conn=Depends(get_conn)):
    """Record (or clear) the measured value for one of the user's predictions."""
    cur = conn.execute("UPDATE predictions SET actual_value = ? WHERE id = ? AND user_id = ?",
                       (body.actual_value, prediction_id, user["id"]))
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "Không tìm thấy bản ghi")
    row = conn.execute("SELECT * FROM predictions WHERE id = ?", (prediction_id,)).fetchone()
    return prediction_out(row)
