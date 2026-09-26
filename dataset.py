"""Per-species statistics of the Iris dataset for the overview page.

Every number and every sentence returned here is computed from data/Iris.csv;
the web page renders them as-is and hard-codes nothing.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

import regression as reg

FEATURE_LABELS = {
    "sepal_length": "Chiều dài đài hoa (sepal)",
    "sepal_width": "Chiều rộng đài hoa (sepal)",
    "petal_length": "Chiều dài cánh hoa (petal)",
    "petal_width": "Chiều rộng cánh hoa (petal)",
}
_RANK_WORDS = {
    "sepal_length": ("ngắn nhất", "đứng giữa", "dài nhất"),
    "sepal_width": ("hẹp nhất", "đứng giữa", "rộng nhất"),
    "petal_length": ("ngắn nhất", "đứng giữa", "dài nhất"),
    "petal_width": ("hẹp nhất", "đứng giữa", "rộng nhất"),
}


def _fmt(value: float, digits: int = 2) -> str:
    """Vietnamese number format: comma as the decimal separator."""
    return f"{value:.{digits}f}".replace(".", ",")


@lru_cache(maxsize=1)
def summary() -> dict:
    data = reg.load_dataset()
    m, species = data["measurements"], data["species"]
    n_total = len(species)
    means = {s: m[species == s].mean(axis=0) for s in reg.SPECIES}

    out = []
    for s in reg.SPECIES:
        rows = m[species == s]
        mean = means[s]
        stats = {
            f: {
                "mean": round(float(rows[:, i].mean()), 3),
                "std": round(float(rows[:, i].std(ddof=1)), 3),
                "min": round(float(rows[:, i].min()), 2),
                "max": round(float(rows[:, i].max()), 2),
            }
            for i, f in enumerate(reg.ALL_MEASUREMENTS)
        }
        # Share of each measurement in the sum of the four means (the donut chart).
        total = float(mean.sum())
        shares = {f: round(float(mean[i] / total * 100), 1) for i, f in enumerate(reg.ALL_MEASUREMENTS)}

        ranks = {}
        for i, f in enumerate(reg.ALL_MEASUREMENTS):
            order = sorted(reg.SPECIES, key=lambda k: means[k][i])
            ranks[f] = order.index(s)

        others = [o for o in reg.SPECIES if o != s]
        distances = {o: float(np.linalg.norm(mean - means[o])) for o in others}
        nearest = min(distances, key=distances.get)

        highlights = [
            f"{FEATURE_LABELS[f]} trung bình {_fmt(stats[f]['mean'])} cm — "
            f"{_RANK_WORDS[f][ranks[f]]} trong 3 loài "
            f"(dao động {_fmt(stats[f]['min'], 1)}–{_fmt(stats[f]['max'], 1)} cm)."
            for f in ("petal_length", "petal_width", "sepal_width")
        ]
        ratio = stats["petal_length"]["mean"] / stats["petal_width"]["mean"]
        highlights.append(
            f"Cánh hoa dài gấp {_fmt(ratio, 1)} lần chiều rộng (tỉ lệ dài/rộng petal trung bình)."
        )

        size_rank = sorted(reg.SPECIES, key=lambda k: means[k].sum()).index(s)
        size_word = ("nhỏ nhất", "trung bình", "lớn nhất")[size_rank]
        remark = (
            f"Tổng bốn kích thước trung bình của {s} là {_fmt(total)} cm — {size_word} trong 3 loài. "
            f"Loài gần nhất về kích thước là {nearest} (khoảng cách Euclid giữa hai vector trung bình "
            f"{_fmt(distances[nearest])} cm), "
            + ("nên hai loài này dễ bị nhầm với nhau hơn."
               if distances[nearest] < 1.5 else "nên loài này tách biệt rõ với hai loài còn lại.")
        )

        out.append({
            "species": s,
            "count": int(len(rows)),
            "share_of_dataset": round(len(rows) / n_total * 100, 1),
            "stats": stats,
            "mean_shares": shares,
            "ranks": {f: int(r) for f, r in ranks.items()},
            "nearest_species": {"species": nearest, "distance_cm": round(distances[nearest], 3)},
            "highlights": highlights,
            "remark": remark,
        })

    return {
        "source": "Kaggle uciml/iris (data/Iris.csv)",
        "n_samples": int(n_total),
        "features": reg.ALL_MEASUREMENTS,
        "feature_labels": FEATURE_LABELS,
        "species": out,
    }


@lru_cache(maxsize=1)
def pca() -> dict:
    """Project the four standardised measurements onto two principal components."""
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler

    data = reg.load_dataset()
    m, species = data["measurements"], data["species"]
    model = PCA(n_components=2)
    coords = model.fit_transform(StandardScaler().fit_transform(m))
    return {
        "source": "Kaggle uciml/iris (data/Iris.csv)",
        "n_samples": int(len(species)),
        "features": reg.ALL_MEASUREMENTS,
        "explained_variance_ratio": [round(float(r), 4) for r in model.explained_variance_ratio_],
        "points": [
            {
                "species": str(s),
                "pc1": round(float(c[0]), 4),
                "pc2": round(float(c[1]), 4),
                "measurements": [float(v) for v in row],
            }
            for s, c, row in zip(species, coords, m)
        ],
    }
