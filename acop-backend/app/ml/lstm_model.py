"""
LSTM-based time-series forecaster for cluster resource metrics (CPU/memory).
Used by the Prediction Agent to forecast near-future resource usage and
flag trajectories heading toward saturation before they become incidents.

Trains on historical MetricSnapshot rows. If insufficient history exists
(cold start / demo mode), falls back to a lightweight exponential-smoothing
forecast so the API always returns a usable result.
"""
import os
from typing import List, Tuple

import numpy as np

from app.config import settings
from app.core.logging_config import logger

MODEL_PATH = os.path.join(settings.MODEL_ARTIFACTS_DIR, "lstm_forecaster.keras")


def _build_model(sequence_length: int, n_features: int):
    from tensorflow import keras
    from tensorflow.keras import layers

    model = keras.Sequential([
        layers.Input(shape=(sequence_length, n_features)),
        layers.LSTM(64, return_sequences=True),
        layers.Dropout(0.2),
        layers.LSTM(32),
        layers.Dropout(0.2),
        layers.Dense(16, activation="relu"),
        layers.Dense(n_features),  # predict next-step [cpu, memory]
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


class LSTMForecaster:
    def __init__(self, sequence_length: int = None):
        self.sequence_length = sequence_length or settings.LSTM_SEQUENCE_LENGTH
        self.n_features = 2  # cpu_usage_percent, memory_usage_percent
        self.model = None
        self._try_load()

    def _try_load(self):
        if os.path.exists(MODEL_PATH):
            try:
                from tensorflow import keras
                self.model = keras.models.load_model(MODEL_PATH)
                logger.info("Loaded trained LSTM forecaster from disk.")
            except Exception as e:
                logger.warning(f"Could not load LSTM model, will train fresh when data allows: {e}")

    def _make_sequences(self, series: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        X, y = [], []
        for i in range(len(series) - self.sequence_length):
            X.append(series[i:i + self.sequence_length])
            y.append(series[i + self.sequence_length])
        return np.array(X), np.array(y)

    def train(self, cpu_series: List[float], memory_series: List[float], epochs: int = 20) -> dict:
        series = np.column_stack([cpu_series, memory_series]).astype("float32")
        if len(series) <= self.sequence_length + 5:
            return {"trained": False, "reason": "insufficient_history",
                    "required_points": self.sequence_length + 5, "available_points": len(series)}

        X, y = self._make_sequences(series)
        self.model = _build_model(self.sequence_length, self.n_features)
        history = self.model.fit(X, y, epochs=epochs, batch_size=16, verbose=0, validation_split=0.1)

        os.makedirs(settings.MODEL_ARTIFACTS_DIR, exist_ok=True)
        self.model.save(MODEL_PATH)

        return {
            "trained": True,
            "final_loss": float(history.history["loss"][-1]),
            "final_val_loss": float(history.history.get("val_loss", [None])[-1]),
            "epochs": epochs,
        }

    def forecast(self, cpu_series: List[float], memory_series: List[float], horizon: int = 5) -> List[Tuple[float, float]]:
        """Returns `horizon` future (cpu, memory) points, auto-regressively rolling the window."""
        series = np.column_stack([cpu_series, memory_series]).astype("float32")

        if self.model is None or len(series) < self.sequence_length:
            return self._fallback_forecast(cpu_series, memory_series, horizon)

        window = series[-self.sequence_length:].copy()
        predictions = []
        for _ in range(horizon):
            x = window.reshape(1, self.sequence_length, self.n_features)
            next_point = self.model.predict(x, verbose=0)[0]
            next_point = np.clip(next_point, 0, 100)
            predictions.append((float(next_point[0]), float(next_point[1])))
            window = np.vstack([window[1:], next_point])

        return predictions

    @staticmethod
    def _fallback_forecast(cpu_series: List[float], memory_series: List[float], horizon: int) -> List[Tuple[float, float]]:
        """Simple exponential smoothing fallback when no trained model / insufficient data exists."""
        alpha = 0.3

        def smooth_and_extrapolate(series: List[float]) -> List[float]:
            if not series:
                return [0.0] * horizon
            level = series[0]
            trend = 0.0
            for i in range(1, len(series)):
                new_level = alpha * series[i] + (1 - alpha) * (level + trend)
                trend = 0.2 * (new_level - level) + 0.8 * trend
                level = new_level
            return [max(0.0, min(100.0, level + trend * (i + 1))) for i in range(horizon)]

        cpu_forecast = smooth_and_extrapolate(cpu_series)
        mem_forecast = smooth_and_extrapolate(memory_series)
        return list(zip(cpu_forecast, mem_forecast))


lstm_forecaster = LSTMForecaster()
