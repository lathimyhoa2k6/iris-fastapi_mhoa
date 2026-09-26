"""R3.3 / R3.4: prediction history per user and the model_runs table."""

import sqlite3
from datetime import date, timedelta

import settings
from conftest import REG_INPUT


def _arena_items(client):
    arena = client.post("/regression/arena", json=REG_INPUT).json()
    return [
        {"task": "regression", "model": r["model"], "input": arena["input"],
         "predicted_value": r["prediction"], "runtime_ms": r["runtime_ms"], "actual_value": 1.3}
        for r in arena["results"]
    ]


def test_save_and_list_history(client, user):
    res = client.post("/db/predictions", json={"items": _arena_items(client)}, headers=user["headers"])
    assert res.status_code == 201
    assert len(res.json()["ids"]) == 5 and res.json()["batch_id"]

    page = client.get("/db/predictions", params={"page_size": 2}, headers=user["headers"]).json()
    assert page["total"] == 5 and page["pages"] == 3 and len(page["items"]) == 2
    item = page["items"][0]
    for key in ("user_id", "created_at", "input", "model", "predicted_value", "runtime_ms", "actual_value"):
        assert key in item
    assert item["input"]["species"] == "versicolor"


def test_filter_by_model_and_date(client, user):
    client.post("/db/predictions", json={"items": _arena_items(client)}, headers=user["headers"])
    only = client.get("/db/predictions", params={"model": "lasso"}, headers=user["headers"]).json()
    assert only["total"] == 1 and only["items"][0]["model"] == "lasso"

    tomorrow = (date.today() + timedelta(days=2)).isoformat()
    future = client.get("/db/predictions", params={"date_from": tomorrow}, headers=user["headers"]).json()
    assert future["total"] == 0
    bad = client.get("/db/predictions", params={"date_from": tomorrow, "date_to": "2020-01-01"},
                     headers=user["headers"])
    assert bad.status_code == 422


def test_users_only_see_their_own_history(client, user, other_user):
    saved = client.post("/db/predictions", json={"items": _arena_items(client)[:1]}, headers=user["headers"]).json()
    theirs = client.get("/db/predictions", headers=other_user["headers"]).json()
    assert theirs["total"] == 0
    # Nor can they edit it.
    res = client.patch(f"/db/predictions/{saved['ids'][0]}", json={"actual_value": 9}, headers=other_user["headers"])
    assert res.status_code == 404


def test_set_actual_value(client, user):
    item = {**_arena_items(client)[0], "actual_value": None}
    pid = client.post("/db/predictions", json={"items": [item]}, headers=user["headers"]).json()["ids"][0]
    res = client.patch(f"/db/predictions/{pid}", json={"actual_value": 1.5}, headers=user["headers"])
    assert res.status_code == 200 and res.json()["actual_value"] == 1.5


def test_classification_history(client, user):
    item = {"task": "classification", "model": "svm", "input": {"sepal_length": 5.1},
            "predicted_label": "setosa", "runtime_ms": 3.2}
    assert client.post("/db/predictions", json={"items": [item]}, headers=user["headers"]).status_code == 201


def test_model_run_is_stored(client, user):
    metrics = client.get("/regression/metrics").json()
    payload = {
        "trained_at": metrics["trained_at"], "target": metrics["task"]["target"],
        "train_size": metrics["data"]["train_size"], "test_size": metrics["data"]["test_size"],
        "best_model": metrics["best_model"], "models": metrics["models"],
    }
    res = client.post("/db/model-runs", json=payload, headers=user["headers"])
    assert res.status_code == 201
    run = res.json()
    assert len(run["models"]) == 5
    assert sum(m["is_best"] for m in run["models"]) == 1

    runs = client.get("/db/model-runs").json()["runs"]
    assert runs[0]["id"] == run["id"]
    with sqlite3.connect(settings.db_path()) as conn:
        n = conn.execute("SELECT COUNT(*) FROM model_runs WHERE run_id = ?", (run["id"],)).fetchone()[0]
    assert n == 5


def test_migrations_recorded(client):
    assert client.get("/db/health").json()["migrations"] == ["001_initial"]
