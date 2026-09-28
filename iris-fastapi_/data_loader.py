"""Iris dataset loading.

Primary source:  Kaggle `uciml/iris`, downloaded with kagglehub.
Fallback source: `sklearn.datasets.load_iris()` when the machine is offline.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pandas as pd

FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
TARGET_NAMES = ["setosa", "versicolor", "virginica"]
KAGGLE_DATASET = "uciml/iris"

DATA_DIR = Path(__file__).resolve().parent / "data"
CSV_PATH = DATA_DIR / "Iris.csv"

_KAGGLE_RENAME = {
    "SepalLengthCm": "sepal_length",
    "SepalWidthCm": "sepal_width",
    "PetalLengthCm": "petal_length",
    "PetalWidthCm": "petal_width",
}


def download_kaggle_csv(force: bool = False) -> Path:
    """Download Iris.csv from Kaggle into `data/` and return its path."""
    if CSV_PATH.exists() and not force:
        return CSV_PATH

    import kagglehub  # imported lazily: only training needs it, the API does not

    cache_dir = Path(kagglehub.dataset_download(KAGGLE_DATASET))
    source = cache_dir / "Iris.csv"
    if not source.exists():
        raise FileNotFoundError(f"Iris.csv not found in {cache_dir}")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, CSV_PATH)
    return CSV_PATH


def load_kaggle() -> pd.DataFrame:
    """Read the Kaggle copy, normalising column names and labels."""
    path = download_kaggle_csv()
    df = pd.read_csv(path)
    df = df.drop(columns=[c for c in ("Id",) if c in df.columns])
    df = df.rename(columns=_KAGGLE_RENAME)
    df["species"] = df["Species"].str.replace("Iris-", "", regex=False)
    df = df.drop(columns=["Species"])
    df["target"] = df["species"].map({name: i for i, name in enumerate(TARGET_NAMES)})
    return df[FEATURES + ["species", "target"]]


def load_sklearn() -> pd.DataFrame:
    """Read the copy bundled with scikit-learn."""
    from sklearn.datasets import load_iris

    bunch = load_iris()
    df = pd.DataFrame(bunch.data, columns=FEATURES)
    df["target"] = bunch.target
    df["species"] = [TARGET_NAMES[i] for i in bunch.target]
    return df[FEATURES + ["species", "target"]]


def load_data(source: str = "auto") -> tuple[pd.DataFrame, str]:
    """Return (DataFrame, name of the source actually used).

    source: "kaggle" | "sklearn" | "auto" (try Kaggle first, fall back to sklearn).
    """
    if source == "kaggle":
        return load_kaggle(), "kaggle"
    if source == "sklearn":
        return load_sklearn(), "sklearn"
    if source != "auto":
        raise ValueError(f"invalid source: {source!r}")

    try:
        return load_kaggle(), "kaggle"
    except Exception as exc:  # offline, Kaggle layout changed, kagglehub missing...
        print(f"[data] Could not fetch the Kaggle copy ({exc}); using the scikit-learn one.")
        return load_sklearn(), "sklearn"


def compare_sources() -> dict:
    """Compare both sources to show they describe the same dataset.

    The report quotes these numbers, so the note is written in Vietnamese.
    """
    kaggle = load_kaggle()
    sk = load_sklearn()

    xk = kaggle[FEATURES].to_numpy(dtype=float)
    xs = sk[FEATURES].to_numpy(dtype=float)

    diff_idx = np.where(np.abs(xk - xs).sum(axis=1) > 0)[0]
    differing_rows = [
        {
            "row": int(i) + 1,  # numbered as in the CSV file (1-based)
            "species": kaggle["species"].iloc[i],
            "kaggle": [float(v) for v in xk[i]],
            "sklearn": [float(v) for v in xs[i]],
        }
        for i in diff_idx
    ]

    return {
        "kaggle_shape": list(kaggle.shape),
        "sklearn_shape": list(sk.shape),
        "kaggle_class_counts": kaggle["species"].value_counts().sort_index().to_dict(),
        "sklearn_class_counts": sk["species"].value_counts().sort_index().to_dict(),
        "labels_match": bool((kaggle["target"].to_numpy() == sk["target"].to_numpy()).all()),
        "identical_values": bool(np.allclose(xk, xs)),
        "n_differing_rows": int(len(diff_idx)),
        "max_abs_diff": float(np.abs(xk - xs).max()),
        "differing_rows": differing_rows,
        "note": (
            "Bản Kaggle (UCI) và bản scikit-learn lệch nhau đúng 2 dòng (35 và 38) do lỗi "
            "sao chép trong kho UCI; scikit-learn đã sửa lại theo bài báo gốc của Fisher. "
            "Phần còn lại hoàn toàn trùng khớp."
        ),
    }


def describe(df: pd.DataFrame) -> dict:
    """Descriptive statistics used by the report."""
    stats = df[FEATURES].describe().to_dict()
    return {
        "n_samples": int(len(df)),
        "n_features": len(FEATURES),
        "class_counts": df["species"].value_counts().sort_index().to_dict(),
        "missing_values": int(df.isna().sum().sum()),
        "duplicated_rows": int(df.duplicated(subset=FEATURES).sum()),
        "feature_stats": {
            feat: {k: round(float(v), 4) for k, v in vals.items()}
            for feat, vals in stats.items()
        },
    }


if __name__ == "__main__":
    frame, used = load_data()
    print(f"Data source: {used}")
    print(frame.head())
    print(describe(frame))
