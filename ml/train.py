"""
Kasi Flavour — Production Recommender Training Pipeline
Hybrid system:
- Implicit CF (SVD)
- Popularity fallback
- Hybrid ranking model
"""

import os
import sys
import json
import pickle
import argparse
import logging
import numpy as np
import pandas as pd
from datetime import datetime

# ─────────────────────────────────────────────
# Setup paths
# ─────────────────────────────────────────────

_ml_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_ml_dir, ".."))
_backend_dir = os.path.join(_project_root, "backend")

for p in [_backend_dir, _project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

MODEL_PATH = os.path.join(_ml_dir, "model.pkl")
REPORT_PATH = os.path.join(_ml_dir, "training_report.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("kasi.train")


# ═════════════════════════════════════════════════════════════════════
# SERIALIZABLE MODELS
# ═════════════════════════════════════════════════════════════════════

class SurpriseWrapper:
    def __init__(self, algo):
        self.algo = algo

    def predict(self, X):
        return np.array([
            self.algo.predict(int(u), int(i)).est
            for u, i in X
        ])


class PopularityModel:
    def __init__(self, pop_series):
        self.pop = pop_series

    def predict(self, X):
        return np.array([
            self.pop.get(int(i), 0.0)
            for _, i in X
        ])


class HybridRecommender:
    def __init__(self, cf_model, pop_model, alpha=0.75):
        self.cf = cf_model
        self.pop = pop_model
        self.alpha = alpha

    def predict(self, X):
        cf_scores = self.cf.predict(X)
        pop_scores = self.pop.predict(X)
        return self.alpha * cf_scores + (1 - self.alpha) * pop_scores


# ═════════════════════════════════════════════════════════════════════
# DATA
# ═════════════════════════════════════════════════════════════════════

def fetch_interactions(db):
    from models.models import Order, OrderItem

    rows = (
        db.query(Order.customer_id, OrderItem.menu_item_id, OrderItem.quantity)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(Order.status == "delivered")
        .all()
    )

    if not rows:
        log.warning("No real data → using synthetic fallback")
        return _synthetic(db)

    df = pd.DataFrame(rows, columns=["user_id", "menu_item_id", "quantity"])
    df = df.groupby(["user_id", "menu_item_id"], as_index=False)["quantity"].sum()

    # implicit signal
    df["rating"] = np.log1p(df["quantity"])

    return df


def _synthetic(db):
    from models.models import MenuItem

    items = db.query(MenuItem).filter(MenuItem.available == True).all()

    if not items:
        raise ValueError("No menu items found")

    item_ids = [i.id for i in items]
    prices = np.array([i.price for i in items], dtype=float)

    weights = 1 / (prices + 1)
    weights = weights / weights.sum()

    rows = []
    for _ in range(800):
        rows.append((
            np.random.randint(1, 100),
            np.random.choice(item_ids, p=weights),
            np.random.randint(1, 5)
        ))

    df = pd.DataFrame(rows, columns=["user_id", "menu_item_id", "quantity"])
    df = df.groupby(["user_id", "menu_item_id"], as_index=False)["quantity"].sum()
    df["rating"] = np.log1p(df["quantity"])

    return df


# ═════════════════════════════════════════════════════════════════════
# MODEL TRAINING
# ═════════════════════════════════════════════════════════════════════

def train_cf(df):
    from surprise import SVD, Dataset, Reader
    from surprise.model_selection import cross_validate, KFold

    reader = Reader(rating_scale=(0, df["rating"].max()))
    data = Dataset.load_from_df(df[["user_id", "menu_item_id", "rating"]], reader)

    algo = SVD(
        n_factors=64,
        n_epochs=20,
        lr_all=0.005,
        reg_all=0.02,
        random_state=42
    )

    cv = cross_validate(
        algo,
        data,
        measures=["RMSE", "MAE"],
        cv=KFold(n_splits=3, random_state=42),
        verbose=False
    )

    algo.fit(data.build_full_trainset())

    return algo, {
        "rmse": float(np.mean(cv["test_rmse"])),
        "mae": float(np.mean(cv["test_mae"]))
    }


def train_popularity(df):
    pop = df.groupby("menu_item_id")["quantity"].sum().sort_values(ascending=False)

    return PopularityModel(pop)


# ═════════════════════════════════════════════════════════════════════
# EVALUATION
# ═════════════════════════════════════════════════════════════════════

def evaluate(model, df, k=5):
    users = df["user_id"].unique()
    all_items = df["menu_item_id"].unique()

    precisions, recalls = [], []

    for u in users:
        udf = df[df["user_id"] == u]
        if len(udf) < 3:
            continue

        split = int(len(udf) * 0.8)
        train_items = set(udf.iloc[:split]["menu_item_id"])
        test_items = set(udf.iloc[split:]["menu_item_id"])

        candidates = [i for i in all_items if i not in train_items]

        X = [[u, i] for i in candidates]
        scores = model.predict(X)

        topk = [candidates[i] for i in np.argsort(scores)[-k:]]

        hits = len(set(topk) & test_items)

        precisions.append(hits / k)
        recalls.append(hits / max(len(test_items), 1))

    return {
        f"precision@{k}": float(np.mean(precisions)) if precisions else 0,
        f"recall@{k}": float(np.mean(recalls)) if recalls else 0,
    }


# ═════════════════════════════════════════════════════════════════════
# TRAIN PIPELINE
# ═════════════════════════════════════════════════════════════════════

def train(db, force_synthetic=False):

    log.info("==== Kasi Flavour Training ====")

    df = _synthetic(db) if force_synthetic else fetch_interactions(db)

    n_users = df["user_id"].nunique()
    n_items = df["menu_item_id"].nunique()

    log.info("Users: %s Items: %s", n_users, n_items)

    # CF + POP
    cf_model, cv = train_cf(df)
    pop_model = train_popularity(df)

    model = HybridRecommender(cf_model, pop_model)

    metrics = evaluate(model, df)

    log.info("Precision@5: %.4f Recall@5: %.4f",
             metrics["precision@5"],
             metrics["recall@5"])

    # save
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)

    report = {
        "model": "HybridCF+Popularity",
        "users": int(n_users),
        "items": int(n_items),
        "cv": cv,
        "metrics": metrics,
        "trained_at": datetime.now().isoformat()
    }

    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    log.info("Model saved → %s", MODEL_PATH)

    return report


# ═════════════════════════════════════════════════════════════════════
# ENTRY
# ═════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()

    from database import SessionLocal

    db = SessionLocal()

    try:
        report = train(db, args.synthetic)
        print("\nDONE")
        print(json.dumps(report, indent=2))
    finally:
        db.close()