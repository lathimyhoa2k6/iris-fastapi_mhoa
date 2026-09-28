"""Generate the regression plots used by the LaTeX report and the slide deck.

Reads regression_metrics.json (written by train_regression.py), so the figures
always show the numbers of the saved models.

Run:  python figures_regression.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import seaborn as sns  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent
METRICS_PATH = BASE_DIR / "regression_metrics.json"
FIGURE_DIR = BASE_DIR / "figures"

DPI = 200
# Same fixed colour per model as the web dashboard.
MODEL_COLORS = {
    "linear": "#6C63FF", "polynomial": "#B38BFA", "ridge": "#5CB85C",
    "lasso": "#6FA8DC", "elasticnet": "#F4A261",
}
FEATURE_VN = {
    "sepal_length": "Dài đài hoa", "sepal_width": "Rộng đài hoa", "petal_length": "Dài cánh hoa",
    "species_versicolor": "Loài = versicolor", "species_virginica": "Loài = virginica",
}
FEATURE_COLORS = ["#6C63FF", "#B38BFA", "#5CB85C", "#6FA8DC", "#F4A261"]

sns.set_theme(style="whitegrid", font_scale=1.0)


def _save(fig, path: Path) -> Path:
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def comparison(report: dict, out: Path) -> Path:
    """CV R² interval and test R² per model (left), test errors (right)."""
    rows = report["models"]
    labels = [r["label"].replace(" Regression", "") for r in rows]
    x = np.arange(len(rows))
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))

    for i, r in enumerate(rows):
        color = MODEL_COLORS[r["model"]]
        ax1.errorbar(i - 0.1, r["cv_r2_mean"], yerr=r["cv_r2_std"], fmt="o", color=color,
                     capsize=6, markersize=8, linewidth=2, label="CV R² (TB ± độ lệch)" if i == 0 else None)
        ax1.plot(i + 0.12, r["r2"], "s", color="#1E2A5A", markersize=7, label="R² tập test" if i == 0 else None)
    best_labels = [f"{lab}\n(tốt nhất)" if r["model"] == report["best_model"] else lab
                   for lab, r in zip(labels, rows)]
    ax1.set_xticks(x, best_labels)
    ax1.set_ylabel("R²")
    ax1.set_title("Độ chính xác: CV R² (5 fold) và R² tập test")
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=9, frameon=False)

    width = 0.38
    ax2.bar(x - width / 2, [r["mae"] for r in rows], width, label="MAE", color="#6C63FF")
    ax2.bar(x + width / 2, [r["rmse"] for r in rows], width, label="RMSE", color="#B38BFA")
    ax2.set_xticks(x, labels)
    ax2.set_ylabel("cm")
    ax2.set_title("Sai số trên tập test (càng thấp càng tốt)")
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2, fontsize=9, frameon=False)
    fig.suptitle(f"So sánh 5 mô hình hồi quy dự đoán {report['task']['target']}", fontsize=13)
    fig.tight_layout()
    return _save(fig, out / "20_hoi_quy_so_sanh.png")


def regularization_paths(report: dict, out: Path) -> Path:
    """Coefficient paths of Ridge, Lasso and ElasticNet against alpha (log scale)."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    best = {r["model"]: r["best_params"].get("alpha") for r in report["models"]}
    for ax, key in zip(axes, ["ridge", "lasso", "elasticnet"]):
        path = report["regularization_paths"][key]
        for color, feat in zip(FEATURE_COLORS, path["features"]):
            ax.plot(path["alphas"], path["coefficients"][feat], color=color, linewidth=2,
                    label=FEATURE_VN.get(feat, feat))
        if best.get(key):
            ax.axvline(best[key], color="#1E2A5A", linestyle="--", linewidth=1.2,
                       label=f"α tốt nhất = {best[key]:g}")
        ax.set_xscale("log")
        ax.axhline(0, color="0.4", linewidth=0.8)
        title = path["label"] + (f" (l1_ratio = {path['l1_ratio']:g})" if path.get("l1_ratio") else "")
        ax.set_title(title)
        ax.set_xlabel("α (thang log)")
    axes[0].set_ylabel("Hệ số (đặc trưng đã chuẩn hoá)")
    axes[1].legend(fontsize=8, loc="upper right")
    fig.suptitle("Regularization path: hệ số co lại khi α tăng", fontsize=13)
    fig.tight_layout()
    return _save(fig, out / "21_hoi_quy_regularization_path.png")


def diagnostics(report: dict, out: Path) -> Path:
    """Actual vs predicted and residuals on the test set for the selected model."""
    key = report["best_model"]
    d = report["diagnostics"]["by_model"][key]
    label = next(r["label"] for r in report["models"] if r["model"] == key)
    actual, pred, res = map(np.array, (d["actual"], d["predicted"], d["residuals"]))
    color = MODEL_COLORS[key]
    lo, hi = min(actual.min(), pred.min()) - 0.1, max(actual.max(), pred.max()) + 0.1

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))
    ax1.scatter(actual, pred, color=color, edgecolor="white", s=55, label="Mẫu test")
    ax1.plot([lo, hi], [lo, hi], "--", color="#1E2A5A", linewidth=1.2, label="y = x")
    ax1.set(xlim=(lo, hi), ylim=(lo, hi), xlabel="Giá trị thật (cm)", ylabel="Dự đoán (cm)",
            title="Actual vs Predicted")
    ax1.legend(fontsize=9)
    ax2.scatter(pred, res, color=color, edgecolor="white", s=55)
    ax2.axhline(0, color="#1E2A5A", linestyle="--", linewidth=1.2)
    lim = np.abs(res).max() * 1.2
    ax2.set(ylim=(-lim, lim), xlabel="Dự đoán (cm)", ylabel="Thật − dự đoán (cm)", title="Phần dư")
    fig.suptitle(f"Chẩn đoán mô hình {label} trên {len(actual)} mẫu test", fontsize=13)
    fig.tight_layout()
    return _save(fig, out / "22_hoi_quy_chan_doan.png")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    report = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    FIGURE_DIR.mkdir(exist_ok=True)
    created = [comparison(report, FIGURE_DIR), regularization_paths(report, FIGURE_DIR),
               diagnostics(report, FIGURE_DIR)]
    print(f"Đã tạo {len(created)} hình hồi quy trong figures/: {', '.join(p.name for p in created)}")


if __name__ == "__main__":
    main()
