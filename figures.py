"""Generate every plot used by the LaTeX report and the slide deck."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402

import data_loader as dl

DPI = 200
PALETTE = {"setosa": "#4f46e5", "versicolor": "#0ea5e9", "virginica": "#f97316"}
LABEL_VN = {
    "sepal_length": "Dài đài hoa (cm)",
    "sepal_width": "Rộng đài hoa (cm)",
    "petal_length": "Dài cánh hoa (cm)",
    "petal_width": "Rộng cánh hoa (cm)",
}

sns.set_theme(style="whitegrid", font_scale=1.0)


def _save(fig, path: Path) -> Path:
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def pairplot(df: pd.DataFrame, out: Path) -> Path:
    grid = sns.pairplot(
        df[dl.FEATURES + ["species"]],
        hue="species",
        palette=PALETTE,
        diag_kind="kde",
        height=2.0,
        plot_kws={"s": 28, "alpha": 0.8, "edgecolor": "white", "linewidth": 0.4},
    )
    grid.figure.suptitle("Quan hệ từng cặp đặc trưng theo loài", y=1.02, fontsize=13)
    path = out / "01_pairplot.png"
    grid.figure.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(grid.figure)
    return path


def boxplots(df: pd.DataFrame, out: Path) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, feat in zip(axes.ravel(), dl.FEATURES):
        sns.boxplot(data=df, x="species", y=feat, hue="species", palette=PALETTE, ax=ax, legend=False)
        sns.stripplot(data=df, x="species", y=feat, ax=ax, color="0.25", size=2.5, alpha=0.5)
        ax.set_title(LABEL_VN[feat], fontsize=11)
        ax.set_xlabel("")
        ax.set_ylabel("cm")
    fig.suptitle("Phân bố từng đặc trưng theo loài", fontsize=13)
    fig.tight_layout()
    return _save(fig, out / "02_boxplot.png")


def correlation(df: pd.DataFrame, out: Path) -> Path:
    corr = df[dl.FEATURES].corr()
    fig, ax = plt.subplots(figsize=(6.2, 5))
    sns.heatmap(
        corr, annot=True, fmt=".3f", cmap="RdBu_r", vmin=-1, vmax=1, square=True,
        linewidths=0.5, cbar_kws={"label": "Hệ số tương quan Pearson"}, ax=ax,
    )
    ax.set_title("Ma trận tương quan giữa 4 đặc trưng", fontsize=13)
    ax.set_xticklabels([LABEL_VN[f].split(" (")[0] for f in dl.FEATURES], rotation=25, ha="right")
    ax.set_yticklabels([LABEL_VN[f].split(" (")[0] for f in dl.FEATURES], rotation=0)
    return _save(fig, out / "03_correlation.png")


def decision_boundary(df: pd.DataFrame, model: Pipeline, out: Path) -> Path:
    """Refit an SVM on the two petal features so the boundary can be drawn in 2D."""
    feats = ["petal_length", "petal_width"]
    X = df[feats].to_numpy(float)
    y = df["target"].to_numpy(int)

    svc_params = model.named_steps["svc"].get_params()
    keep = {k: svc_params[k] for k in ("kernel", "C", "gamma", "degree") if k in svc_params}
    pipe = Pipeline([("scaler", StandardScaler()), ("svc", SVC(**keep))]).fit(X, y)

    pad = 0.4
    xx, yy = np.meshgrid(
        np.linspace(X[:, 0].min() - pad, X[:, 0].max() + pad, 400),
        np.linspace(X[:, 1].min() - pad, X[:, 1].max() + pad, 400),
    )
    zz = pipe.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.contourf(xx, yy, zz, alpha=0.18, levels=[-0.5, 0.5, 1.5, 2.5],
                colors=[PALETTE["setosa"], PALETTE["versicolor"], PALETTE["virginica"]])
    ax.contour(xx, yy, zz, levels=[0.5, 1.5], colors="0.3", linewidths=1.0, linestyles="--")
    for cid, name in enumerate(dl.TARGET_NAMES):
        mask = y == cid
        ax.scatter(X[mask, 0], X[mask, 1], c=PALETTE[name], label=name, s=38,
                   edgecolor="white", linewidth=0.6, zorder=3)

    sv = pipe.named_steps["scaler"].inverse_transform(pipe.named_steps["svc"].support_vectors_)
    ax.scatter(sv[:, 0], sv[:, 1], s=140, facecolors="none", edgecolors="black",
               linewidth=1.1, label=f"Vector hỗ trợ ({len(sv)})", zorder=4)

    ax.set_xlabel(LABEL_VN["petal_length"])
    ax.set_ylabel(LABEL_VN["petal_width"])
    ax.set_title(f"Biên quyết định của SVM (kernel = {keep.get('kernel')}) trên 2 đặc trưng cánh hoa", fontsize=12)
    ax.legend(loc="upper left", framealpha=0.95)
    return _save(fig, out / "04_decision_boundary.png")


def pca_plot(df: pd.DataFrame, out: Path) -> Path:
    X = StandardScaler().fit_transform(df[dl.FEATURES].to_numpy(float))
    pca = PCA(n_components=2, random_state=0)
    comps = pca.fit_transform(X)
    ev = pca.explained_variance_ratio_

    fig, ax = plt.subplots(figsize=(7.5, 6))
    for cid, name in enumerate(dl.TARGET_NAMES):
        mask = df["target"].to_numpy() == cid
        ax.scatter(comps[mask, 0], comps[mask, 1], c=PALETTE[name], label=name,
                   s=40, edgecolor="white", linewidth=0.5)
    ax.set_xlabel(f"Thành phần chính 1 ({ev[0]*100:.1f}% phương sai)")
    ax.set_ylabel(f"Thành phần chính 2 ({ev[1]*100:.1f}% phương sai)")
    ax.set_title(f"PCA 2 chiều — giữ lại {ev.sum()*100:.1f}% phương sai", fontsize=13)
    ax.legend()
    return _save(fig, out / "05_pca.png")


def confusion(cm: np.ndarray, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", cbar=False, square=True,
                xticklabels=dl.TARGET_NAMES, yticklabels=dl.TARGET_NAMES, ax=ax,
                annot_kws={"fontsize": 14})
    ax.set_xlabel("Dự đoán")
    ax.set_ylabel("Thực tế")
    ax.set_title("Ma trận nhầm lẫn trên tập kiểm tra", fontsize=13)
    return _save(fig, out / "06_confusion_matrix.png")


def kernel_chart(rows: list[dict], out: Path) -> Path:
    frame = pd.DataFrame(rows)
    x = np.arange(len(frame))
    width = 0.38

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width / 2, frame["cv_mean"], width, yerr=frame["cv_std"], capsize=4,
           label="Accuracy CV (5-fold)", color="#4f46e5")
    ax.bar(x + width / 2, frame["test_accuracy"], width, label="Accuracy tập kiểm tra", color="#f97316")
    for i, row in frame.iterrows():
        ax.text(i - width / 2, row["cv_mean"] + 0.02, f"{row['cv_mean']:.3f}", ha="center", fontsize=9)
        ax.text(i + width / 2, row["test_accuracy"] + 0.005, f"{row['test_accuracy']:.3f}", ha="center", fontsize=9)

    ax.set_xticks(x, frame["kernel"])
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("Accuracy")
    ax.set_xlabel("Kernel")
    ax.set_title("So sánh các kernel của SVM (tham số mặc định)", fontsize=13)
    ax.legend(loc="lower right")
    return _save(fig, out / "07_kernel_comparison.png")


def class_distribution(df: pd.DataFrame, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    counts = df["species"].value_counts().sort_index()
    ax.bar(counts.index, counts.values, color=[PALETTE[s] for s in counts.index])
    for i, v in enumerate(counts.values):
        ax.text(i, v + 1, str(v), ha="center", fontsize=11)
    ax.set_ylim(0, counts.max() * 1.2)
    ax.set_ylabel("Số mẫu")
    ax.set_title("Phân bố số mẫu theo loài (dữ liệu cân bằng)", fontsize=13)
    return _save(fig, out / "00_class_distribution.png")


def build_all(df, model, X_train, y_train, X_test, y_test, cm, kernel_rows, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    return [
        class_distribution(df, out),
        pairplot(df, out),
        boxplots(df, out),
        correlation(df, out),
        decision_boundary(df, model, out),
        pca_plot(df, out),
        confusion(np.asarray(cm), out),
        kernel_chart(kernel_rows, out),
    ]
