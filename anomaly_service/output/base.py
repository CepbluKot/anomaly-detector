"""Protocol definition for output sinks."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from anomaly_service.detectors.base import AnomalyResult


@runtime_checkable
class OutputSink(Protocol):
    """Write anomaly detection results to some destination."""

    def write(self, result: "AnomalyResult", only_anomalies: bool = True) -> None:
        """
        Write an AnomalyResult to this sink.

        Parameters
        ----------
        result:
            The completed anomaly detection result to persist or display.
        only_anomalies:
            If True, only write points where is_anomaly=True.
            If False, write all points with their is_anomaly flag.
        """
        ...
