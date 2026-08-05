"""
XGBoost-based binary anomaly classifier for cluster resource metrics.
Complements the LSTM forecaster: where LSTM predicts *future values*,
this model classifies whether a *current* metric snapshot looks anomalous
based on engineered features (rate-of-change, restart count, error rate, etc).

Falls back to a statistical z-score / threshold heuristic when no trained
model is available yet, so anomaly detection works from the very first request.
"""
import os
from typing import List, Dict

import numpy as np
import joblib

from app.config import settings
from app.core.logging_config import logger

MODEL_PATH = os.path.join(settings.MODEL_ARTIFACTS_DIR, "xgboost_anomaly.joblib")

FEATURE_NAMES = [
    "cpu_usage_percent", "memory_usage_percent", "network_in_mbps", "network_out_mbps",
    "disk_io_ops", "restart_count", "error_rate", "latency_ms",
]


class XGBoostAnomalyDetector:
    def __init__(self):
        self.model = None
        self._try_load()

    def _try_load(self):
        if os.path.exists(MODEL_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                logger.info("Loaded trained XGBoost anomaly model from disk.")
            except Exception as e:
                logger.warning(f"Could not load XGBoost model: {e}")

    def train(self, feature_rows: List[Dict], labels: List[int]) -> dict:
        """
        feature_rows: list of dicts with keys matching FEATURE_NAMES
        labels: 1 = anomalous, 0 = normal
        """
        import xgboost as xgb
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, f1_score

        if len(feature_rows) < 30:
            return {"trained": False, "reason": "insufficient_labeled_data", "min_required": 30}

        X = np.array([[row.get(f, 0.0) for f in FEATURE_NAMES] for row in feature_rows])
        y = np.array(labels)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

        model = xgb.XGBClassifier(
            n_estimators=150, max_depth=5, learning_rate=0.08,
            subsample=0.85, colsample_bytree=0.85, eval_metric="logloss",
        )
        model.fit(X_train, y_train)
        preds = model.predict(X_test)

        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        self.model = model

        return {
            "trained": True,
            "accuracy": float(accuracy_score(y_test, preds)),
            "f1_score": float(f1_score(y_test, preds, zero_division=0)),
            "n_samples": len(feature_rows),
        }

    def predict(self, features: Dict) -> Dict:
        x = np.array([[features.get(f, 0.0) for f in FEATURE_NAMES]])

        if self.model is None:
            return self._fallback_predict(features)

        proba = float(self.model.predict_proba(x)[0][1])
        return {
            "is_anomalous": proba >= settings.ANOMALY_THRESHOLD,
            "anomaly_score": proba,
            "method": "xgboost",
        }

    @staticmethod
    def _fallback_predict(features: Dict) -> Dict:
        """Heuristic scoring when no trained model exists yet — weighted threshold rule."""
        score = 0.0
        score += max(0, features.get("cpu_usage_percent", 0) - 85) / 15 * 0.3
        score += max(0, features.get("memory_usage_percent", 0) - 85) / 15 * 0.3
        score += min(1.0, features.get("restart_count", 0) / 5) * 0.2
        score += min(1.0, features.get("error_rate", 0) / 10) * 0.15
        score += min(1.0, features.get("latency_ms", 0) / 2000) * 0.05
        score = min(1.0, score)

        return {
            "is_anomalous": score >= settings.ANOMALY_THRESHOLD,
            "anomaly_score": round(score, 4),
            "method": "heuristic_fallback",
        }


xgboost_detector = XGBoostAnomalyDetector()
