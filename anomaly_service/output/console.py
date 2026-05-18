"""Console/log output sink — prints a human-readable anomaly detection summary."""
from __future__ import annotations

import logging

from anomaly_service.detectors.base import AnomalyResult

logger = logging.getLogger(__name__)

_MAX_ANOMALY_ROWS = 20


class ConsoleSink:
    """
    Writes a summary of the anomaly detection result to the log (INFO level).

    Prints: service, metric, detector, total points, anomaly count, fraction.
    Then lists anomalous timestamps and values (capped at 20 rows).
    """

    def write(self, result: AnomalyResult, only_anomalies: bool = True) -> None:
        logger.info("─" * 60)
        logger.info(
            "RESULT  service=%-20s metric=%s",
            result.service,
            result.metric,
        )
        logger.info("  Detector:      %s", result.detector_name)
        logger.info("  Total points:  %d", len(result.points))
        logger.info(
            "  Anomalies:     %d  (%.2f%%)",
            result.anomaly_count,
            result.anomaly_fraction * 100,
        )

        anomalous = [p for p in result.points if p.is_anomaly]
        if anomalous:
            shown = anomalous[:_MAX_ANOMALY_ROWS]
            logger.info("  Anomalous timestamps (first %d of %d):", len(shown), len(anomalous))
            for p in shown:
                lo = f"{p.lower_bound:.4f}" if not _is_nan(p.lower_bound) else "n/a"
                hi = f"{p.upper_bound:.4f}" if not _is_nan(p.upper_bound) else "n/a"
                logger.info(
                    "    %s  value=%.4f  score=%.4f  bounds=[%s, %s]",
                    p.timestamp.isoformat(),
                    p.value,
                    p.score,
                    lo,
                    hi,
                )
        else:
            logger.info("  No anomalies detected.")

        logger.info("─" * 60)


def _is_nan(v: float) -> bool:
    return v != v
