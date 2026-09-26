"""Train and compare the five regression models (target: petal_width).

Run:  python train_regression.py

Outputs regression_models.pkl and regression_metrics.json, which the model API
serves under /regression/*. The same training can be triggered from the web page
through POST /regression/train.
"""

from __future__ import annotations

import sys

import regression as reg


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("[1/3] Huấn luyện 5 mô hình hồi quy dự đoán petal_width (GridSearchCV, KFold 5):")
    models, report = reg.train_all()
    best = next(r for r in report["models"] if r["model"] == report["best_model"])
    print(f"[2/3] Mô hình tốt nhất theo CV R²: {best['label']} "
          f"(CV R² = {best['cv_r2_mean']:.4f} ± {best['cv_r2_std']:.4f}, test R² = {best['r2']:.4f})")
    reg.save(models, report)
    print(f"[3/3] Đã lưu {reg.MODELS_PATH.name} và {reg.METRICS_PATH.name}")


if __name__ == "__main__":
    main()
