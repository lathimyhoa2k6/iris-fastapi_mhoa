"""Seed the system: first training of the five regression models, demo user, first run in the DB.

Run:  python seed.py [--retrain]

Idempotent: the models are trained only if regression_models.pkl is missing (or
with --retrain), the demo account is created only if absent, and the first
training run is copied into model_runs only while that table is empty.
In single-service mode app.py calls `seed_database()` at startup, so a fresh
SQLite file on Render gets the demo account back after every deploy.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys

import regression as reg
from db_api.auth import create_user
from db_api.db import connect
from db_api.runs import TrainingRunIn, store_run

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo123"


def ensure_models(retrain: bool = False, log=print) -> dict:
    if retrain or not reg.MODELS_PATH.exists() or not reg.METRICS_PATH.exists():
        log("[seed] Huấn luyện 5 mô hình hồi quy lần đầu...")
        models, report = reg.train_all(log=log)
        report["trained_by"] = "seed"
        reg.save(models, report)
        return report
    return reg.load()[1]


def seed_database(report: dict | None = None, log=print) -> None:
    """Create the demo user and store the current evaluation table if the DB has none."""
    conn = connect()
    try:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (DEMO_USERNAME,)).fetchone()
        if row is None:
            try:
                user_id = create_user(conn, DEMO_USERNAME, DEMO_PASSWORD)
                log(f"[seed] Đã tạo tài khoản demo: {DEMO_USERNAME} / {DEMO_PASSWORD}")
            except sqlite3.IntegrityError:  # created concurrently by another worker
                user_id = conn.execute("SELECT id FROM users WHERE username = ?", (DEMO_USERNAME,)).fetchone()[0]
        else:
            user_id = row[0]

        if conn.execute("SELECT COUNT(*) FROM training_runs").fetchone()[0] == 0:
            report = report or reg.load()[1]
            run_id = store_run(conn, user_id, TrainingRunIn(
                trained_at=report["trained_at"],
                target=report["task"]["target"],
                train_size=report["data"]["train_size"],
                test_size=report["data"]["test_size"],
                best_model=report["best_model"],
                total_seconds=report.get("total_seconds"),
                models=report["models"],
            ))
            log(f"[seed] Đã lưu bảng đánh giá 5 mô hình vào model_runs (lần train #{run_id})")
    finally:
        conn.close()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Khởi tạo dữ liệu: train lần đầu + tài khoản demo")
    parser.add_argument("--retrain", action="store_true", help="Train lại 5 mô hình dù đã có")
    args = parser.parse_args()
    report = ensure_models(args.retrain)
    seed_database(report)
    print("[seed] Xong.")


if __name__ == "__main__":
    main()
