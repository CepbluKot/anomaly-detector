"""Rolling Z-score anomaly detector."""
from __future__ import annotations

import numpy as np
import pandas as pd

from anomaly_service.detectors.base import AnomalyPoint


class RollingZScoreDetector:
    """
    Detects anomalies using a rolling Z-score threshold.

    Points where |z| = |x - rolling_mean| / rolling_std exceeds the threshold
    are flagged as anomalies.
    """

    name = "rolling_zscore"

    def __init__(
        self,
        window: int = 60,
        threshold: float = 3.0,
        min_periods: int = 30,
    ) -> None:
        self._window = window
        self._threshold = threshold
        self._min_periods = min_periods

    def detect(self, series: pd.Series) -> list[AnomalyPoint]:
        rolling = series.rolling(window=self._window, min_periods=self._min_periods)
        mean = rolling.mean()
        std = rolling.std()

        points: list[AnomalyPoint] = []
        for ts, val, mu, sigma in zip(
            series.index, series.values, mean.values, std.values
        ):
            val_f = float(val)
            mu_f = float(mu) if not np.isnan(mu) else float("nan")
            sigma_f = float(sigma) if not np.isnan(sigma) else float("nan")

            if np.isnan(mu_f) or np.isnan(sigma_f):
                score = 0.0
                is_anomaly = False
                lower_bound = float("nan")
                upper_bound = float("nan")
            else:
                denom = max(sigma_f, 1e-9)
                score = abs(val_f - mu_f) / denom
                is_anomaly = score > self._threshold
                lower_bound = mu_f - self._threshold * sigma_f
                upper_bound = mu_f + self._threshold * sigma_f

            points.append(AnomalyPoint(
                timestamp=pd.Timestamp(ts),
                value=val_f,
                is_anomaly=is_anomaly,
                score=score,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            ))

        return points
