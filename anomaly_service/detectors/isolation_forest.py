"""Isolation Forest anomaly detector."""
from __future__ import annotations

import numpy as np
import pandas as pd

from anomaly_service.detectors.base import AnomalyPoint


class IsolationForestDetector:
    """
    Detects anomalies using scikit-learn's IsolationForest.

    Fits on the entire series (unsupervised). Points predicted as -1 by
    the model are flagged as anomalies. The anomaly score is the negated
    score_samples output, so higher = more anomalous.

    Requires scikit-learn to be installed.
    """

    name = "isolation_forest"

    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        self._contamination = contamination
        self._n_estimators = n_estimators
        self._random_state = random_state

    def detect(self, series: pd.Series) -> list[AnomalyPoint]:
        try:
            from sklearn.ensemble import IsolationForest  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "scikit-learn is required for IsolationForestDetector. "
                "Install it with: pip install scikit-learn"
            ) from exc

        values = series.values.astype(float).reshape(-1, 1)

        model = IsolationForest(
            contamination=self._contamination,
            n_estimators=self._n_estimators,
            random_state=self._random_state,
        )
        model.fit(values)

        predictions = model.predict(values)       # 1 = normal, -1 = anomaly
        raw_scores = model.score_samples(values)  # more negative = more anomalous

        # Negate so that higher score = more anomalous
        scores = -raw_scores

        points: list[AnomalyPoint] = []
        for ts, val, pred, score in zip(series.index, series.values, predictions, scores):
            points.append(AnomalyPoint(
                timestamp=pd.Timestamp(ts),
                value=float(val),
                is_anomaly=bool(pred == -1),
                score=float(score),
                lower_bound=float("nan"),
                upper_bound=float("nan"),
            ))

        return points
