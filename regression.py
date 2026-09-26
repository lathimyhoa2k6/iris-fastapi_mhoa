"""Five regression models that predict petal_width from the other Iris measurements.

The regression task complements the SVM classifier: the target is `petal_width`,
the inputs are `sepal_length`, `sepal_width`, `petal_length` plus a one-hot
encoding of the species (setosa is the baseline, so two dummy columns).

Only numpy / scikit-learn / the standard library are used, so the API can import
this module on Render without pandas.

Outputs of `train_all()`:
    regression_models.pkl     the five fitted pipelines
    regression_metrics.json   metrics, timings, regularization paths, diagnostics
"""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.base import clone
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GridSearchCV, KFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "data" / "Iris.csv"
MODELS_PATH = BASE_DIR / "regression_models.pkl"
METRICS_PATH = BASE_DIR / "regression_metrics.json"

RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

NUMERIC_FEATURES = ["sepal_length", "sepal_width", "petal_length"]
TARGET = "petal_width"
SPECIES = ["setosa", "versicolor", "virginica"]
# setosa is the reference level of the one-hot encoding
FEATURE_NAMES = NUMERIC_FEATURES + ["species_versicolor", "species_virginica"]
ALL_MEASUREMENTS = ["sepal_length", "sepal_width", "petal_length", "petal_width"]

_CSV_COLUMNS = {
    "SepalLengthCm": "sepal_length",
    "SepalWidthCm": "sepal_width",
    "PetalLengthCm": "petal_length",
    "PetalWidthCm": "petal_width",
}

MODEL_KEYS = ["linear", "polynomial", "ridge", "lasso", "elasticnet"]
MODEL_LABELS = {
    "linear": "Linear Regression",
    "polynomial": "Polynomial Regression",
    "ridge": "Ridge",
    "lasso": "Lasso",
    "elasticnet": "ElasticNet",
}
REGULARIZED = ["ridge", "lasso", "elasticnet"]

# Speed tiers relative to the fastest model: ratio <= FAST -> fast, <= MEDIUM -> medium.
SPEED_THRESHOLDS = {"fast": 1.5, "medium": 3.0}
SPEED_LABELS = {"fast": "Nhanh", "medium": "Trung bình", "slow": "Chậm"}

PATH_ALPHAS = np.logspace(-4, 3, 36)
PREDICT_REPEATS = 200
ARENA_TIMING_REPEATS = 5


# ----------------------------------------------------------------- data


def load_dataset(csv_path: Path = CSV_PATH) -> dict:
    """Read the Kaggle Iris.csv with the csv module and return numpy arrays."""
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for rec in csv.DictReader(fh):
            rows.append(
                {
                    **{name: float(rec[col]) for col, name in _CSV_COLUMNS.items()},
                    "species": rec["Species"].replace("Iris-", ""),
                }
            )
    measurements = np.array([[r[f] for f in ALL_MEASUREMENTS] for r in rows], dtype=float)
    species = np.array([r["species"] for r in rows])
    return {"measurements": measurements, "species": species}


def make_features(numeric: np.ndarray, species) -> np.ndarray:
    """Stack the three numeric inputs with the species one-hot columns."""
    numeric = np.atleast_2d(np.asarray(numeric, dtype=float))
    species = np.atleast_1d(np.asarray(species))
    unknown = set(species) - set(SPECIES)
    if unknown:
        raise ValueError(f"unknown species: {sorted(unknown)}")
    dummies = np.column_stack([(species == s).astype(float) for s in SPECIES[1:]])
    return np.hstack([numeric, dummies])


def split(dataset: dict) -> dict:
    """Fixed, stratified 80/20 split shared by training and the diagnostics."""
    m = dataset["measurements"]
    X = make_features(m[:, :3], dataset["species"])
    y = m[:, 3]
    idx = np.arange(len(y))
    idx_train, idx_test = train_test_split(
        idx, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=dataset["species"]
    )
    return {
        "X_train": X[idx_train], "X_test": X[idx_test],
        "y_train": y[idx_train], "y_test": y[idx_test],
        "idx_train": idx_train, "idx_test": idx_test,
    }


# ----------------------------------------------------------------- models


def build_candidates() -> dict[str, tuple[Pipeline, dict]]:
    """Pipeline and hyper-parameter grid of each of the five models."""
    return {
        "linear": (
            Pipeline([("scaler", StandardScaler()), ("model", LinearRegression())]),
            {},
        ),
        "polynomial": (
            Pipeline([
                ("scaler", StandardScaler()),
                ("poly", PolynomialFeatures(include_bias=False)),
                ("model", LinearRegression()),
            ]),
            {"poly__degree": [2, 3, 4]},
        ),
        "ridge": (
            Pipeline([("scaler", StandardScaler()), ("model", Ridge())]),
            {"model__alpha": np.logspace(-3, 3, 13).tolist()},
        ),
        "lasso": (
            Pipeline([("scaler", StandardScaler()), ("model", Lasso(max_iter=50_000))]),
            {"model__alpha": np.logspace(-4, 1, 11).tolist()},
        ),
        "elasticnet": (
            Pipeline([("scaler", StandardScaler()), ("model", ElasticNet(max_iter=50_000))]),
            {
                "model__alpha": np.logspace(-4, 1, 11).tolist(),
                "model__l1_ratio": [0.1, 0.3, 0.5, 0.7, 0.9],
            },
        ),
    }


def speed_tiers(values: dict[str, float]) -> dict[str, dict]:
    """Label each timing Nhanh / Trung bình / Chậm by its ratio to the fastest one."""
    positive = [v for v in values.values() if v is not None and v > 0]
    fastest = min(positive) if positive else None
    out = {}
    for key, value in values.items():
        ratio = value / fastest if fastest else 1.0
        if ratio <= SPEED_THRESHOLDS["fast"]:
            tier = "fast"
        elif ratio <= SPEED_THRESHOLDS["medium"]:
            tier = "medium"
        else:
            tier = "slow"
        out[key] = {"tier": tier, "label": SPEED_LABELS[tier], "ratio_to_fastest": round(ratio, 2)}
    return out


def _clean_params(params: dict) -> dict:
    clean = {}
    for k, v in params.items():
        name = k.split("__", 1)[-1]
        clean[name] = round(float(v), 6) if isinstance(v, (float, np.floating)) else v
    return clean


def _coefficients(pipe: Pipeline) -> np.ndarray:
    return np.ravel(pipe.named_steps["model"].coef_)


def _time_predict(pipe: Pipeline, X: np.ndarray, repeats: int = PREDICT_REPEATS) -> float:
    """Average prediction time in milliseconds per sample over `repeats` batch calls."""
    pipe.predict(X)  # warm-up
    started = time.perf_counter()
    for _ in range(repeats):
        pipe.predict(X)
    return (time.perf_counter() - started) * 1000 / (repeats * len(X))


def regularization_path(key: str, X_train, y_train, l1_ratio: float = 0.5) -> dict:
    """Coefficients (on standardised inputs) as alpha sweeps a log scale."""
    estimators = {
        "ridge": lambda a: Ridge(alpha=a),
        "lasso": lambda a: Lasso(alpha=a, max_iter=50_000),
        "elasticnet": lambda a: ElasticNet(alpha=a, l1_ratio=l1_ratio, max_iter=50_000),
    }
    Xs = StandardScaler().fit_transform(X_train)
    coefs = []
    for alpha in PATH_ALPHAS:
        coefs.append(estimators[key](alpha).fit(Xs, y_train).coef_.tolist())
    coefs = np.array(coefs)
    return {
        "model": key,
        "label": MODEL_LABELS[key],
        "l1_ratio": l1_ratio if key == "elasticnet" else None,
        "alphas": [float(a) for a in PATH_ALPHAS],
        "features": FEATURE_NAMES,
        "coefficients": {f: [round(float(c), 6) for c in coefs[:, i]] for i, f in enumerate(FEATURE_NAMES)},
        "n_nonzero": [int((np.abs(row) > 1e-10).sum()) for row in coefs],
    }


def train_all(csv_path: Path = CSV_PATH, log=print) -> tuple[dict, dict]:
    """Tune, fit, evaluate and time the five models. Returns (models, report)."""
    dataset = load_dataset(csv_path)
    parts = split(dataset)
    X_train, X_test, y_train, y_test = parts["X_train"], parts["X_test"], parts["y_train"], parts["y_test"]
    cv = KFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

    models: dict[str, Pipeline] = {}
    rows: list[dict] = []
    for key, (pipe, grid) in build_candidates().items():
        search = GridSearchCV(pipe, grid or [{}], cv=cv, scoring="r2", n_jobs=1, refit=True)
        started = time.perf_counter()
        search.fit(X_train, y_train)
        tuning_seconds = time.perf_counter() - started

        # Training time of the chosen configuration alone, comparable across models.
        best = clone(search.best_estimator_)
        started = time.perf_counter()
        best.fit(X_train, y_train)
        train_seconds = time.perf_counter() - started

        y_pred = best.predict(X_test)
        mse = float(mean_squared_error(y_test, y_pred))
        coefs = _coefficients(best)
        i = search.best_index_
        row = {
            "model": key,
            "label": MODEL_LABELS[key],
            "r2": round(float(r2_score(y_test, y_pred)), 4),
            "mae": round(float(mean_absolute_error(y_test, y_pred)), 4),
            "mse": round(mse, 5),
            "rmse": round(float(np.sqrt(mse)), 4),
            "cv_r2_mean": round(float(search.cv_results_["mean_test_score"][i]), 4),
            "cv_r2_std": round(float(search.cv_results_["std_test_score"][i]), 4),
            "train_seconds": round(train_seconds, 5),
            "tuning_seconds": round(tuning_seconds, 3),
            "predict_ms_per_sample": round(_time_predict(best, X_test), 5),
            "n_coefficients": int(coefs.size),
            "n_nonzero_coef": int((np.abs(coefs) > 1e-10).sum()),
            "best_params": _clean_params(search.best_params_),
            "n_configs": len(search.cv_results_["params"]),
        }
        if key != "polynomial":
            row["coefficients"] = {f: round(float(c), 5) for f, c in zip(FEATURE_NAMES, coefs)}
        models[key] = best
        rows.append(row)
        log(
            f"  {row['label']:<22} R²={row['r2']:.4f}  RMSE={row['rmse']:.4f}  "
            f"CV R²={row['cv_r2_mean']:.4f}±{row['cv_r2_std']:.4f}  "
            f"train={row['train_seconds'] * 1000:.2f}ms  predict={row['predict_ms_per_sample']:.4f}ms/mẫu  "
            f"hệ số≠0={row['n_nonzero_coef']}/{row['n_coefficients']}  {row['best_params']}"
        )

    predict_tiers = speed_tiers({r["model"]: r["predict_ms_per_sample"] for r in rows})
    train_tiers = speed_tiers({r["model"]: r["train_seconds"] for r in rows})
    for r in rows:
        r["predict_speed"] = predict_tiers[r["model"]]
        r["train_speed"] = train_tiers[r["model"]]

    # Model selection uses cross-validation, never the test set.
    best_key = max(rows, key=lambda r: r["cv_r2_mean"])["model"]

    elastic_l1 = next(r for r in rows if r["model"] == "elasticnet")["best_params"]["l1_ratio"]
    paths = {
        key: regularization_path(key, X_train, y_train, l1_ratio=elastic_l1)
        for key in REGULARIZED
    }

    test_inputs = [
        {
            **{f: float(v) for f, v in zip(ALL_MEASUREMENTS, dataset["measurements"][j])},
            "species": str(dataset["species"][j]),
        }
        for j in parts["idx_test"]
    ]
    diagnostics = {}
    for key, pipe in models.items():
        pred = pipe.predict(X_test)
        diagnostics[key] = {
            "actual": [round(float(v), 4) for v in y_test],
            "predicted": [round(float(v), 4) for v in pred],
            "residuals": [round(float(a - p), 4) for a, p in zip(y_test, pred)],
        }

    report = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {"scikit_learn": sklearn.__version__, "numpy": np.__version__},
        "task": {
            "target": TARGET,
            "features": FEATURE_NAMES,
            "numeric_features": NUMERIC_FEATURES,
            "species_baseline": SPECIES[0],
            "description": "Dự đoán chiều rộng cánh hoa (petal_width) từ 3 kích thước còn lại và loài (one-hot).",
        },
        "data": {
            "source": "Kaggle uciml/iris (data/Iris.csv)",
            "n_samples": int(len(dataset["species"])),
            "train_size": int(len(y_train)),
            "test_size": int(len(y_test)),
            "test_ratio": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "cv": f"KFold(n_splits={CV_FOLDS}, shuffle=True, random_state={RANDOM_STATE})",
            "target_mean": round(float(dataset["measurements"][:, 3].mean()), 4),
            "target_std": round(float(dataset["measurements"][:, 3].std()), 4),
        },
        "speed_thresholds": SPEED_THRESHOLDS,
        "best_model": best_key,
        "selection_metric": "cv_r2_mean",
        "models": rows,
        "regularization_paths": paths,
        "diagnostics": {"test_inputs": test_inputs, "by_model": diagnostics},
    }
    return models, report


def save(models: dict, report: dict) -> None:
    joblib.dump({"models": models, "feature_names": FEATURE_NAMES, "trained_at": report["trained_at"]}, MODELS_PATH)
    METRICS_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def load() -> tuple[dict, dict]:
    """Load the saved pipelines and report written by `save()`."""
    bundle = joblib.load(MODELS_PATH)
    report = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return bundle["models"], report


def predict_one(pipe: Pipeline, features: np.ndarray, repeats: int = 1) -> tuple[float, float]:
    """Return (prediction, runtime in ms) measured with perf_counter.

    With repeats > 1 the runtime is the median of that many calls, after one untimed
    warm-up call, which damps the noise of sub-millisecond timings.
    """
    if repeats > 1:
        pipe.predict(features)
    timings = []
    for _ in range(max(1, repeats)):
        started = time.perf_counter()
        value = float(pipe.predict(features)[0])
        timings.append((time.perf_counter() - started) * 1000)
    return value, float(np.median(timings))


def arena(models: dict, sepal_length: float, sepal_width: float, petal_length: float, species: str) -> dict:
    """Run the five models on one input and compare them to their consensus (median)."""
    X = make_features([[sepal_length, sepal_width, petal_length]], [species])
    results = []
    for key in MODEL_KEYS:
        value, ms = predict_one(models[key], X, repeats=ARENA_TIMING_REPEATS)
        results.append({"model": key, "label": MODEL_LABELS[key], "prediction": round(value, 4), "runtime_ms": round(ms, 4)})

    values = np.array([r["prediction"] for r in results])
    consensus = float(np.median(values))
    for r in results:
        r["deviation"] = round(r["prediction"] - consensus, 4)
    tiers = speed_tiers({r["model"]: r["runtime_ms"] for r in results})
    for r in results:
        r["speed"] = tiers[r["model"]]
    outlier = max(results, key=lambda r: abs(r["deviation"]))
    return {
        "input": {"sepal_length": sepal_length, "sepal_width": sepal_width,
                  "petal_length": petal_length, "species": species},
        "consensus": round(consensus, 4),
        "consensus_method": "median",
        "timing": f"median of {ARENA_TIMING_REPEATS} perf_counter runs per model",
        "mean": round(float(values.mean()), 4),
        "spread": round(float(values.max() - values.min()), 4),
        "most_deviant": {"model": outlier["model"], "label": outlier["label"], "deviation": outlier["deviation"]},
        "results": results,
    }
