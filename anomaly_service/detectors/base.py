"""
Protocol definition for anomaly detectors, plus the result dataclasses.

Using Protocol (structural subtyping) rather than ABC so that custom detectors
can be used without inheriting from our base class.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import pandas as pd


@dataclass
class AnomalyPoint:
    """A single time-series point annotated with anomaly information."""
    timestamp: pd.Timestamp
    value: float
    is_anomaly: bool
    score: float          # higher = more anomalous; detector-specific scale
    lower_bound: float    # float("nan") if not applicable
    upper_bound: float    # float("nan") if not applicable


@dataclass
class AnomalyResult:
    """All annotated points for a single metric run."""
    service: str
    metric: str
    detector_name: str
    points: list[AnomalyPoint]

    @property
    def anomaly_count(self) -> int:
        return sum(1 for p in self.points if p.is_anomaly)

    @property
    def anomaly_fraction(self) -> float:
        if not self.points:
            return 0.0
        return self.anomaly_count / len(self.points)


@runtime_checkable
class AnomalyDetector(Protocol):
    """Duck-typing interface for all anomaly detectors."""

    name: str

    def detect(self, series: pd.Series) -> list[AnomalyPoint]:
        """
        Run anomaly detection on the provided time series.

        Parameters
        ----------
        series:
            pd.Series with DatetimeIndex (UTC) and float values.

        Returns
        -------
        list[AnomalyPoint]
            One entry per input point, in input order.
        """
        ...
