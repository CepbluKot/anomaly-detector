"""Factory for anomaly detectors."""
from __future__ import annotations

from typing import Union

from anomaly_service.detectors.base import AnomalyDetector

_REGISTRY: dict[str, type] = {}


def _register() -> None:
    global _REGISTRY
    from anomaly_service.detectors.rolling_iqr import RollingIQRDetector
    from anomaly_service.detectors.rolling_zscore import RollingZScoreDetector
    from anomaly_service.detectors.mad import MADDetector
    from anomaly_service.detectors.isolation_forest import IsolationForestDetector

    _REGISTRY = {
        "rolling_iqr":       RollingIQRDetector,
        "rolling_zscore":    RollingZScoreDetector,
        "mad":               MADDetector,
        "isolation_forest":  IsolationForestDetector,
    }


def get_detector(spec: Union[str, dict]) -> AnomalyDetector:
    """
    Instantiate an anomaly detector from a string name or a dict spec.

    String form:
        "rolling_iqr"

    Dict form:
        {"algorithm": "rolling_iqr", "params": {"window": 120, "scale": 2.0}}

    Supported algorithms: rolling_iqr, rolling_zscore, mad, isolation_forest
    """
    if not _REGISTRY:
        _register()

    if isinstance(spec, str):
        algorithm = spec
        params: dict = {}
    else:
        algorithm = spec.get("algorithm", "rolling_iqr")
        params = spec.get("params", {})

    if algorithm not in _REGISTRY:
        raise ValueError(
            f"Unknown detector algorithm '{algorithm}'. "
            f"Valid options: {sorted(_REGISTRY.keys())}"
        )

    return _REGISTRY[algorithm](**params)
