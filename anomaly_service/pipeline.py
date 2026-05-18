"""
Main orchestrator for the anomaly detection service.

run_metric() is the top-level function: given a MetricConfig and Settings,
it fetches data, runs anomaly detection, writes outputs, and returns a
MetricAnomalyResult.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pandas as pd

from anomaly_service.config import MetricConfig, SourceConfig
from anomaly_service.detectors.base import AnomalyResult
from anomaly_service.detectors.registry import get_detector
from anomaly_service.settings import Settings

if TYPE_CHECKING:
    from anomaly_service.sources.base import DataSource

logger = logging.getLogger(__name__)


@dataclass
class MetricAnomalyResult:
    """Summary of anomaly detection for a single metric."""
    service: str
    metric: str
    detector_name: str
    total_points: int
    anomaly_count: int
    anomaly_fraction: float
    result: AnomalyResult


def _build_source(source_cfg: SourceConfig) -> "DataSource":
    """Instantiate the appropriate DataSource from config."""
    src_type = source_cfg.type
    preprocess = source_cfg.preprocess

    if src_type == "clickhouse":
        from anomaly_service.sources.clickhouse import ClickHouseSource
        if source_cfg.clickhouse is None:
            raise ValueError("source.type='clickhouse' requires source.clickhouse connection config.")
        return ClickHouseSource(cfg=source_cfg.clickhouse, preprocess=preprocess)
    elif src_type == "prometheus":
        from anomaly_service.sources.prometheus import PrometheusSource
        if source_cfg.prometheus is None:
            raise ValueError("source.type='prometheus' requires source.prometheus connection config.")
        return PrometheusSource(cfg=source_cfg.prometheus, preprocess=preprocess)
    else:
        raise ValueError(f"Unknown source type '{src_type}'. Valid: 'clickhouse', 'prometheus'.")


def _resolve_time_range(source_cfg: SourceConfig) -> tuple[datetime, datetime]:
    """Compute start/end datetimes from the time_range config."""
    now = datetime.now(tz=timezone.utc)
    tr = source_cfg.time_range

    if tr is None:
        return now - timedelta(days=90), now

    if tr.lookback_days is not None:
        return now - timedelta(days=tr.lookback_days), now

    if tr.start is not None and tr.end is not None:
        from dateutil import parser as dtparser
        start = dtparser.parse(tr.start)
        end = dtparser.parse(tr.end)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return start, end

    return now - timedelta(days=90), now


def run_metric(
    metric_cfg: MetricConfig,
    settings: Settings,
    run_id: str,
) -> MetricAnomalyResult:
    """
    Run the full anomaly detection pipeline for one metric.

    Steps:
    1. Build DataSource from config.
    2. Resolve time range.
    3. Fetch time series.
    4. Build detector from DetectorConfig.
    5. Run detector.
    6. Write to configured outputs.
    7. Return MetricAnomalyResult.
    """
    service = metric_cfg.service
    metric = metric_cfg.metric

    logger.info("=" * 60)
    logger.info("Processing metric: service='%s' metric='%s'", service, metric)
    logger.info("=" * 60)

    # ── 1. Build source ───────────────────────────────────────────────────────
    source = _build_source(metric_cfg.source)

    # ── 2 & 3. Fetch data ─────────────────────────────────────────────────────
    start, end = _resolve_time_range(metric_cfg.source)
    logger.info("Fetching data from %s to %s ...", start.isoformat(), end.isoformat())
    series = source.fetch(query=metric_cfg.source.query, start=start, end=end)

    if series.empty:
        raise ValueError(f"No data returned for service='{service}' metric='{metric}'.")

    logger.info("Fetched %d data points. Range: %s → %s", len(series), series.index[0], series.index[-1])

    # ── 4. Build detector ─────────────────────────────────────────────────────
    detector_cfg = metric_cfg.detector
    detector = get_detector({"algorithm": detector_cfg.algorithm, "params": detector_cfg.params})
    logger.info("Running detector: %s", detector.name)

    # ── 5. Detect anomalies ───────────────────────────────────────────────────
    points = detector.detect(series)

    anomaly_result = AnomalyResult(
        service=service,
        metric=metric,
        detector_name=detector.name,
        points=points,
    )

    logger.info(
        "Detection complete: %d anomalies out of %d points (%.2f%%)",
        anomaly_result.anomaly_count,
        len(points),
        anomaly_result.anomaly_fraction * 100,
    )

    # ── 6. Write outputs ──────────────────────────────────────────────────────
    output_cfg = metric_cfg.output
    only_anomalies = output_cfg.only_anomalies

    if output_cfg.console:
        from anomaly_service.output.console import ConsoleSink
        ConsoleSink().write(anomaly_result, only_anomalies=only_anomalies)

    if output_cfg.clickhouse is not None:
        from anomaly_service.output.clickhouse import ClickHouseSink
        table = output_cfg.clickhouse.table
        sink = ClickHouseSink(settings=settings, table=table, run_id=run_id)
        sink.write(anomaly_result, only_anomalies=only_anomalies)

    # ── 7. Return result ──────────────────────────────────────────────────────
    return MetricAnomalyResult(
        service=service,
        metric=metric,
        detector_name=detector.name,
        total_points=len(points),
        anomaly_count=anomaly_result.anomaly_count,
        anomaly_fraction=anomaly_result.anomaly_fraction,
        result=anomaly_result,
    )
