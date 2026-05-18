"""Rolling IQR anomaly detector."""
from __future__ import annotations

import numpy as np
import pandas as pd

from anomaly_service.detectors.base import AnomalyPoint


class RollingIQRDetector:
    """
    Detects anomalies using a rolling interquartile range fence.

    Points outside [Q1 - scale*IQR, Q3 + scale*IQR] computed over a sliding
    window are flagged as anomalies.
    """

    name = "rolling_iqr"

    def __init__(
        self,
        window: int = 60,
        scale: float = 1.5,
        min_periods: int = 30,
    ) -> None:
        self._window = window
        self._scale = scale
        self._min_periods = min_periods

    def detect(self, series: pd.Series) -> list[AnomalyPoint]:
        rolling = series.rolling(window=self._window, min_periods=self._min_periods)
        q1 = rolling.quantile(0.25)
        q3 = rolling.quantile(0.75)
        iqr = q3 - q1

        lower = q1 - self._scale * iqr
        upper = q3 + self._scale * iqr

        points: list[AnomalyPoint] = []
        for ts, val, lo, hi, iq in zip(
            series.index, series.values, lower.values, upper.values, iqr.values
        ):
            val_f = float(val)
            lo_f = float(lo) if not np.isnan(lo) else float("nan")
            hi_f = float(hi) if not np.isnan(hi) else float("nan")
            iq_f = float(iq) if not np.isnan(iq) else float("nan")

            if np.isnan(lo_f) or np.isnan(hi_f):
                # Not enough data in window yet
                score = 0.0
                is_anomaly = False
            else:
                denom = max(iq_f, 1e-9)
                if val_f < lo_f:
                    score = (lo_f - val_f) / denom
                elif val_f > hi_f:
                    score = (val_f - hi_f) / denom
                else:
                    score = 0.0
                is_anomaly = val_f < lo_f or val_f > hi_f

            points.append(AnomalyPoint(
                timestamp=pd.Timestamp(ts),
                value=val_f,
                is_anomaly=is_anomaly,
                score=score,
                lower_bound=lo_f,
                upper_bound=hi_f,
            ))

        return points
