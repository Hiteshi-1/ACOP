"""
Unifies signal from the XGBoost classifier and LSTM forecast-deviation
into a single anomaly verdict + contributing factors list, consumed by
the Monitoring/Prediction agents.
"""
from typing import Dict, List

from app.ml.xgboost_model import xgboost_detector
from app.ml.lstm_model import lstm_forecaster


def evaluate_snapshot(features: Dict, recent_cpu: List[float], recent_memory: List[float]) -> Dict:
    xgb_result = xgboost_detector.predict(features)

    contributing_factors: List[str] = []
    if features.get("cpu_usage_percent", 0) > 85:
        contributing_factors.append("CPU usage above 85%")
    if features.get("memory_usage_percent", 0) > 85:
        contributing_factors.append("Memory usage above 85%")
    if features.get("restart_count", 0) >= 3:
        contributing_factors.append(f"High restart count ({features['restart_count']})")
    if features.get("error_rate", 0) > 5:
        contributing_factors.append(f"Elevated error rate ({features['error_rate']}%)")
    if features.get("latency_ms", 0) > 1000:
        contributing_factors.append(f"High latency ({features['latency_ms']}ms)")

    # Forecast-based early warning: is the trajectory heading toward saturation?
    forecast_warning = None
    if len(recent_cpu) >= 5 and len(recent_memory) >= 5:
        forecast = lstm_forecaster.forecast(recent_cpu, recent_memory, horizon=5)
        max_future_cpu = max(p[0] for p in forecast)
        max_future_mem = max(p[1] for p in forecast)
        if max_future_cpu > 90 or max_future_mem > 90:
            forecast_warning = (
                f"Forecast trajectory reaches CPU {max_future_cpu:.1f}% / "
                f"Memory {max_future_mem:.1f}% within next 5 intervals"
            )
            contributing_factors.append(forecast_warning)

    is_anomalous = xgb_result["is_anomalous"] or forecast_warning is not None

    return {
        "is_anomalous": is_anomalous,
        "anomaly_score": xgb_result["anomaly_score"],
        "detection_method": xgb_result["method"],
        "contributing_factors": contributing_factors,
        "forecast_warning": forecast_warning,
    }
