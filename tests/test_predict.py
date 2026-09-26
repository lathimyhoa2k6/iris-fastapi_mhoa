"""R1.2 / R2 / R3.2 / R4.1: SVM contract, regression predictions, timings, arena."""

import regression as reg
from conftest import REG_INPUT, SETOSA


def test_svm_predict_contract_unchanged(client):
    res = client.post("/predict", json=SETOSA)
    assert res.status_code == 200
    body = res.json()
    assert body["class_id"] == 0 and body["species_key"] == "setosa"
    for field in ("display_name", "description", "probabilities", "image_url", "alt_text", "source", "license"):
        assert field in body
    assert abs(sum(body["probabilities"].values()) - 1) < 0.01


def test_svm_rejects_negative_input(client):
    assert client.post("/predict", json={**SETOSA, "petal_width": -1}).status_code == 422


def test_regression_metrics_has_five_models(client):
    body = client.get("/regression/metrics").json()
    assert [m["model"] for m in body["models"]] == reg.MODEL_KEYS
    for m in body["models"]:
        for key in ("r2", "mae", "mse", "rmse", "cv_r2_mean", "cv_r2_std", "train_seconds",
                    "predict_ms_per_sample", "n_nonzero_coef", "best_params"):
            assert key in m
        assert m["predict_speed"]["label"] in ("Nhanh", "Trung bình", "Chậm")
    assert body["best_model"] in reg.MODEL_KEYS


def test_regression_predict_each_model(client):
    for key in reg.MODEL_KEYS:
        res = client.post("/regression/predict", json={**REG_INPUT, "model": key})
        assert res.status_code == 200, res.text
        body = res.json()
        assert 0 < body["prediction"] < 3  # petal_width in cm
        assert body["runtime_ms"] >= 0


def test_regression_predict_validates_species(client):
    res = client.post("/regression/predict", json={**REG_INPUT, "species": "rose"})
    assert res.status_code == 422


def test_arena_consensus_and_outlier(client):
    body = client.post("/regression/arena", json=REG_INPUT).json()
    preds = sorted(r["prediction"] for r in body["results"])
    assert len(preds) == 5
    assert body["consensus"] == preds[2]  # median of five
    worst = max(body["results"], key=lambda r: abs(r["deviation"]))
    assert body["most_deviant"]["model"] == worst["model"]
    assert any(r["speed"]["label"] == "Nhanh" for r in body["results"])  # the fastest is always fast


def test_speed_tiers_are_relative_to_fastest():
    tiers = reg.speed_tiers({"a": 1.0, "b": 1.4, "c": 2.5, "d": 10.0})
    assert [tiers[k]["label"] for k in "abcd"] == ["Nhanh", "Nhanh", "Trung bình", "Chậm"]


def test_regularization_path_and_diagnostics(client):
    path = client.get("/regression/regularization-path", params={"model": "lasso"}).json()
    assert len(path["alphas"]) == len(path["n_nonzero"])
    assert path["n_nonzero"][-1] <= path["n_nonzero"][0]  # Lasso zeroes coefficients as alpha grows
    diag = client.get("/regression/diagnostics", params={"model": "polynomial"}).json()
    assert len(diag["actual"]) == len(diag["predicted"]) == len(diag["residuals"]) == 30


def test_dataset_summary_from_csv(client):
    body = client.get("/dataset/summary").json()
    assert body["n_samples"] == 150
    assert [s["count"] for s in body["species"]] == [50, 50, 50]
    setosa = body["species"][0]
    assert abs(sum(setosa["mean_shares"].values()) - 100) < 0.5


def test_dataset_pca_projects_every_sample(client):
    body = client.get("/dataset/pca").json()
    assert len(body["points"]) == 150
    assert {p["species"] for p in body["points"]} == set(reg.SPECIES)
    ratios = body["explained_variance_ratio"]
    assert len(ratios) == 2 and ratios[0] >= ratios[1] > 0 and sum(ratios) <= 1


def test_train_requires_login(client):
    assert client.post("/regression/train").status_code == 401


def test_train_with_token(client, user, tmp_path, monkeypatch):
    # Keep the committed model files untouched.
    monkeypatch.setattr(reg, "MODELS_PATH", tmp_path / "models.pkl")
    monkeypatch.setattr(reg, "METRICS_PATH", tmp_path / "metrics.json")
    res = client.post("/regression/train", headers=user["headers"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["models"]) == 5 and body["trained_by"] == user["username"]
    assert (tmp_path / "models.pkl").exists()
