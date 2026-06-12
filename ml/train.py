"""
ml/train.py – Train and save the Kasi Flavour recommendation model
===================================================================
Run:  python ml/train.py
      → saves model.pkl for use by recommend.py

Uses a simple SVD-based collaborative filtering model (surprise library)
with a fallback to sklearn's SGDRegressor when surprise is unavailable.
"""

import os
import pickle
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

# Add backend to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from database import SessionLocal
from models.models import Order, OrderItem, MenuItem

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.pkl")


def fetch_order_matrix(db: Session) -> pd.DataFrame:
    """Build a user-item interaction matrix from order history."""
    rows = (
        db.query(Order.customer_id, OrderItem.menu_item_id, OrderItem.quantity)
        .join(OrderItem, OrderItem.order_id == Order.id)
        .all()
    )
    if not rows:
        print("No order data found. Using synthetic data for demo.")
        # Synthetic data for initial training
        np.random.seed(42)
        n = 500
        rows = [
            (np.random.randint(1, 50), np.random.randint(1, 30), np.random.randint(1, 5))
            for _ in range(n)
        ]

    df = pd.DataFrame(rows, columns=["user_id", "menu_item_id", "quantity"])
    # Normalize quantity to 0-1 rating
    df["rating"] = df["quantity"] / df["quantity"].max()
    return df


def train(db: Session):
    print("Fetching order data...")
    df = fetch_order_matrix(db)
    print(f"  {len(df)} interactions loaded")

    X = df[["user_id", "menu_item_id"]].values
    y = df["rating"].values

    try:
        # Preferred: SVD collaborative filter via surprise
        from surprise import SVD, Dataset, Reader
        from surprise.model_selection import cross_validate

        reader = Reader(rating_scale=(0, 1))
        data = Dataset.load_from_df(df[["user_id", "menu_item_id", "rating"]], reader)
        model = SVD(n_factors=50, n_epochs=30, lr_all=0.005, reg_all=0.02)
        cross_validate(model, data, measures=["RMSE"], cv=3, verbose=True)

        # Train on full dataset
        trainset = data.build_full_trainset()
        model.fit(trainset)

        # Wrap to match sklearn predict(X) interface
        class SurpriseWrapper:
            def __init__(self, algo):
                self.algo = algo
            def predict(self, X):
                return np.array([
                    self.algo.predict(int(row[0]), int(row[1])).est
                    for row in X
                ])

        final_model = SurpriseWrapper(model)
        print("Trained SVD collaborative filter (surprise)")

    except ImportError:
        # Fallback: sklearn SGD regressor
        from sklearn.linear_model import SGDRegressor
        from sklearn.preprocessing import StandardScaler
        from sklearn.pipeline import Pipeline

        final_model = Pipeline([
            ("scaler", StandardScaler()),
            ("sgd",    SGDRegressor(max_iter=1000, tol=1e-3, random_state=42))
        ])
        final_model.fit(X, y)
        print("Trained SGDRegressor fallback model (install surprise for better results)")

    # Save
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(final_model, f)
    print(f"Model saved → {MODEL_PATH}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        train(db)
    finally:
        db.close()
