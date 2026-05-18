"""Median Absolute Deviation (MAD) anomaly detector — global, not rolling."""
from __future__ import annotations

import numpy as np
import pandas as pd

from anomaly_service.detectors.base import AnomalyPoint


class MADDetector:
    """
    Detects anomalies using the Median Absolute Deviation (MAD) method.

    Operates globally over the entire series. The modified Z-score
    0.6745 * |x - median| / MAD is compared against the threshold.
    The constant 0.6745 makes the score consistent with the standard
    normal distribution (MAD ≈ 0.6745 * std for normal data).
    """

    name = "mad"

    def __init__(self, threshold: float = 3.5) -> None:
        self._threshold = threshold

    def detect(self, series: pd.Series) -> list[AnomalyPoint]:
        values = series.values.astype(float)
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))

        denom = max(mad, 1e-9)
        lower_bound = median - self._threshold * mad / 0.6745
        upper_bound = median + self._threshold * mad / 0.6745

        points: list[AnomalyPoint] = []
        for ts, val in zip(series.index, values):
            val_f = float(val)
            score = 0.6745 * abs(val_f - median) / denom
            is_anomaly = score > self._threshold

            points.append(AnomalyPoint(
                timestamp=pd.Timestamp(ts),
                value=val_f,
                is_anomaly=is_anomaly,
                score=score,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
            ))

        return points
