"""Train, evaluate and save the SVM model that classifies Iris flowers.

Run:  python train.py  [--source auto|kaggle|sklearn]  [--no-figures]

Outputs:
    svm_model.pkl   trained StandardScaler + SVC pipeline
    metrics.json    every figure quoted by the LaTeX report and the /metrics endpoint
    figures/*.png   plots for the report
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.model_selection import (
    GridSearchCV,
    StratifiedKFold,
    cross_val_score,
    train_test_split,
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

sys.path.insert(0, str(Path(__file__).resolve().parent))
import data_loader as dl  # noqa: E402
import figures as fig  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
FIGURE_DIR = BASE_DIR / "figures"

RANDOM_STATE = 42
TEST_SIZE = 0.2
CV_FOLDS = 5

PARAM_GRID = [
    {"svc__kernel": ["linear"], "svc__C": [0.1, 1, 10, 100]},
    {
        "svc__kernel": ["rbf"],
        "svc__C": [0.1, 1, 10, 100],
        "svc__gamma": ["scale", "auto", 0.01, 0.1, 1],
    },
    {
        "svc__kernel": ["poly"],
        "svc__C": [0.1, 1, 10, 100],
        "svc__gamma": ["scale", "auto", 0.01, 0.1, 1],
        "svc__degree": [2, 3],
    },
]


def build_pipeline(**svc_kwargs) -> Pipeline:
    """Scaling lives inside the pipeline so the API never preprocesses by hand."""
    params = {"random_state": RANDOM_STATE, **svc_kwargs}
    return Pipeline([("scaler", StandardScaler()), ("svc", SVC(**params))])


def build_calibrated_pipeline(svc_params: dict) -> Pipeline:
    """Pipeline that gets deployed: wrap SVC in Platt scaling to expose predict_proba.

    `SVC(probability=True)` is deprecated since scikit-learn 1.9; the official docs
    recommend CalibratedClassifierCV(..., ensemble=False) instead. It is the same
    Platt scaling SVC used to run implicitly, only explicit and still supported.
    """
    base = SVC(random_state=RANDOM_STATE, **svc_params)
    calibrated = CalibratedClassifierCV(base, method="sigmoid", ensemble=False, cv=CV_FOLDS)
    return Pipeline([("scaler", StandardScaler()), ("svc", calibrated)])


def compare_kernels(X_train, y_train, X_test, y_test) -> list[dict]:
    """Compare kernels with default parameters — the table used by the report."""
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    rows = []
    for kernel in ("linear", "rbf", "poly", "sigmoid"):
        pipe = build_pipeline(kernel=kernel)
        started = time.perf_counter()
        scores = cross_val_score(pipe, X_train, y_train, cv=cv, scoring="accuracy")
        pipe.fit(X_train, y_train)
        rows.append(
            {
                "kernel": kernel,
                "cv_mean": round(float(scores.mean()), 4),
                "cv_std": round(float(scores.std()), 4),
                "test_accuracy": round(float(accuracy_score(y_test, pipe.predict(X_test))), 4),
                "n_support_vectors": int(pipe.named_steps["svc"].n_support_.sum()),
                "fit_seconds": round(time.perf_counter() - started, 3),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Huấn luyện SVM phân loại hoa Iris")
    parser.add_argument("--source", default="auto", choices=["auto", "kaggle", "sklearn"])
    parser.add_argument("--no-figures", action="store_true", help="Bỏ qua bước vẽ hình")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    # 1. Data --------------------------------------------------------------
    df, source_used = dl.load_data(args.source)
    print(f"[1/6] Nguồn dữ liệu: {source_used} — {len(df)} mẫu, {len(dl.FEATURES)} đặc trưng")

    stats = dl.describe(df)
    print(f"      Phân bố lớp: {stats['class_counts']}")
    print(f"      Giá trị thiếu: {stats['missing_values']} — dòng trùng: {stats['duplicated_rows']}")

    try:
        source_comparison = dl.compare_sources()
        print(
            f"      So sánh Kaggle vs scikit-learn: lệch {source_comparison['n_differing_rows']} dòng "
            f"(tối đa {source_comparison['max_abs_diff']} cm), nhãn khớp: {source_comparison['labels_match']}"
        )
    except Exception as exc:
        source_comparison = {"error": str(exc)}
        print(f"      (Bỏ qua so sánh hai nguồn: {exc})")

    X = df[dl.FEATURES].to_numpy(dtype=float)
    y = df["target"].to_numpy(dtype=int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE
    )
    print(f"[2/6] Chia dữ liệu: {len(X_train)} mẫu huấn luyện / {len(X_test)} mẫu kiểm tra (stratify)")

    # 2. Kernel comparison ---------------------------------------------------
    kernel_rows = compare_kernels(X_train, y_train, X_test, y_test)
    print("[3/6] So sánh kernel (tham số mặc định):")
    for row in kernel_rows:
        print(
            f"      {row['kernel']:<8} CV = {row['cv_mean']:.4f} ± {row['cv_std']:.4f}"
            f"   test = {row['test_accuracy']:.4f}   SV = {row['n_support_vectors']}"
        )

    # 3. Hyper-parameter search ----------------------------------------------
    cv = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    search = GridSearchCV(
        build_pipeline(), PARAM_GRID, cv=cv, scoring="accuracy", n_jobs=-1, refit=True
    )
    started = time.perf_counter()
    search.fit(X_train, y_train)
    search_seconds = time.perf_counter() - started

    best_params = {k.replace("svc__", ""): v for k, v in search.best_params_.items()}
    print(f"[4/6] GridSearchCV: thử {len(search.cv_results_['params'])} cấu hình trong {search_seconds:.1f}s")
    print(f"      Tham số tốt nhất: {best_params}")
    print(f"      Accuracy CV tốt nhất: {search.best_score_:.4f}")

    model: Pipeline = search.best_estimator_

    # Deployed model: add Platt scaling so the API can return per-class probabilities.
    deployed = build_calibrated_pipeline(best_params).fit(X_train, y_train)
    agreement = float((deployed.predict(X_test) == model.predict(X_test)).mean())

    # 4. Evaluation ----------------------------------------------------------
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    cv_scores = cross_val_score(model, X, y, cv=cv, scoring="accuracy")

    report = classification_report(
        y_test, y_pred_test, target_names=dl.TARGET_NAMES, output_dict=True, zero_division=0
    )
    cm = confusion_matrix(y_test, y_pred_test)
    svc: SVC = model.named_steps["svc"]

    print("[5/6] Kết quả mô hình tốt nhất:")
    print(f"      Accuracy train : {accuracy_score(y_train, y_pred_train):.4f}")
    print(f"      Accuracy test  : {accuracy_score(y_test, y_pred_test):.4f}")
    print(f"      Cross-val (toàn bộ dữ liệu): {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    print(f"      Macro F1       : {f1_score(y_test, y_pred_test, average='macro'):.4f}")
    print(f"      Vector hỗ trợ  : {svc.n_support_.tolist()} (tổng {int(svc.n_support_.sum())})")
    print(f"      Accuracy bản hiệu chuẩn (đem triển khai): {accuracy_score(y_test, deployed.predict(X_test)):.4f}"
          f" — trùng khớp {agreement:.1%} với bản gốc")
    print(f"      Ma trận nhầm lẫn:\n{cm}")

    metrics = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "data": {
            "source_used": source_used,
            **stats,
            "train_size": int(len(X_train)),
            "test_size": int(len(X_test)),
            "test_ratio": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "source_comparison": source_comparison,
        },
        "model": {
            "estimator": "Pipeline(StandardScaler + SVC)",
            "best_params": {k: (v if isinstance(v, (int, float, str)) else str(v)) for k, v in best_params.items()},
            "n_support_per_class": svc.n_support_.tolist(),
            "n_support_total": int(svc.n_support_.sum()),
            "n_configs_searched": len(search.cv_results_["params"]),
            "search_seconds": round(search_seconds, 2),
            "deployed_estimator": "Pipeline(StandardScaler + CalibratedClassifierCV(SVC, sigmoid))",
            "deployed_accuracy_test": round(float(accuracy_score(y_test, deployed.predict(X_test))), 4),
            "deployed_agreement_with_svc": round(agreement, 4),
        },
        "performance": {
            "accuracy_train": round(float(accuracy_score(y_train, y_pred_train)), 4),
            "accuracy_test": round(float(accuracy_score(y_test, y_pred_test)), 4),
            "best_cv_score": round(float(search.best_score_), 4),
            "cv_mean": round(float(cv_scores.mean()), 4),
            "cv_std": round(float(cv_scores.std()), 4),
            "cv_scores": [round(float(s), 4) for s in cv_scores],
            "macro_f1": round(float(f1_score(y_test, y_pred_test, average="macro")), 4),
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "labels": dl.TARGET_NAMES,
        },
        "kernel_comparison": kernel_rows,
    }

    (BASE_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    joblib.dump(deployed, BASE_DIR / "svm_model.pkl")
    print("[6/6] Đã lưu svm_model.pkl và metrics.json")

    # 5. Plots for the report ------------------------------------------------
    if not args.no_figures:
        FIGURE_DIR.mkdir(exist_ok=True)
        created = fig.build_all(df, model, X_train, y_train, X_test, y_test, cm, kernel_rows, FIGURE_DIR)
        print(f"      Đã tạo {len(created)} hình trong figures/: {', '.join(p.name for p in created)}")

    print("\nModel saved!")


if __name__ == "__main__":
    main()
