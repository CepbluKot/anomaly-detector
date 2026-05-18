"""Prometheus data source implementation."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pandas as pd

from anomaly_service.config import PreprocessConfig, PrometheusSourceConfig

logger = logging.getLogger(__name__)


class PrometheusSource:
    """
    Fetches time-series data from a Prometheus-compatible endpoint.

    Uses the Prometheus HTTP API /api/v1/query_range via requests.
    The query is a PromQL expression. The result is parsed into a pd.Series
    by extracting the first returned metric's values.
    """

    def __init__(
        self,
        cfg: PrometheusSourceConfig,
        preprocess: Optional[PreprocessConfig] = None,
    ) -> None:
        self._cfg = cfg
        self._preprocess = preprocess

    def fetch(self, query: str, start: datetime, end: datetime) -> pd.Series:
        logger.debug(
            "PrometheusSource.fetch: url=%s step=%s start=%s end=%s",
            self._cfg.url,
            self._cfg.step,
            start.isoformat(),
            end.isoformat(),
        )

        try:
            import requests  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "requests is required for PrometheusSource. "
                "Install it with: pip install requests"
            ) from exc

        params = {
            "query": query,
            "start": start.timestamp(),
            "end":   end.timestamp(),
            "step":  self._cfg.step,
        }

        auth = None
        if self._cfg.username:
            auth = (self._cfg.username, self._cfg.password)

        url = self._cfg.url.rstrip("/") + "/api/v1/query_range"

        try:
            resp = requests.get(
                url,
                params=params,
                auth=auth,
                verify=not self._cfg.disable_ssl,
                timeout=120,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logger.error("Prometheus query failed: %s", exc)
            raise

        if payload.get("status") != "success":
            raise ValueError(f"Prometheus returned non-success status: {payload.get('status')}")

        result = payload.get("data", {}).get("result", [])
        if not result:
            logger.warning("Prometheus query returned empty result for query: %s", query)
            return pd.Series(dtype=float, name="value")

        if len(result) > 1:
            logger.warning(
                "Prometheus query returned %d metric series; using the first one. "
                "Consider making your PromQL more specific.",
                len(result),
            )

        metric_data = result[0]
        values_raw = metric_data.get("values", [])

        if not values_raw:
            logger.warning("Prometheus metric has no values.")
            return pd.Series(dtype=float, name="value")

        timestamps = []
        values = []
        for ts_epoch, val_str in values_raw:
            ts = pd.Timestamp(float(ts_epoch), unit="s", tz="UTC")
            try:
                val = float(val_str)
            except (ValueError, TypeError):
                val = float("nan")
            timestamps.append(ts)
            values.append(val)

        series = pd.Series(values, index=pd.DatetimeIndex(timestamps), name="value")
        series = series.sort_index()

        if self._preprocess is not None and self._preprocess.scale is not None:
            logger.debug("Applying scale factor: %s", self._preprocess.scale)
            series = series * self._preprocess.scale

        logger.info("Fetched %d data points from Prometheus.", len(series))
        return series
