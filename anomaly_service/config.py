"""
Pydantic v2 schema for the JSON configuration file / ANOMALY_SERVICE_CONFIG env var.

The top-level structure is AnomalyServiceConfig.
Each metric config is MetricConfig (after deep-merging with defaults).
"""
from __future__ import annotations

import copy
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


# ── Source sub-configs ────────────────────────────────────────────────────────

class ClickHouseSourceConfig(BaseModel):
    host: str = "localhost"
    port: int = 8123
    user: str = "default"
    password: str = ""
    database: str = "default"


class PrometheusSourceConfig(BaseModel):
    url: str = "http://localhost:9090"
    step: str = "5m"
    username: str = ""
    password: str = ""
    disable_ssl: bool = False


class TimeRangeConfig(BaseModel):
    lookback_days: Optional[int] = None
    start: Optional[str] = None  # ISO8601
    end: Optional[str] = None    # ISO8601

    @model_validator(mode="after")
    def validate_range(self) -> "TimeRangeConfig":
        has_lookback = self.lookback_days is not None
        has_explicit = self.start is not None or self.end is not None
        if has_lookback and has_explicit:
            raise ValueError("Specify either lookback_days or start/end, not both.")
        if has_explicit and (self.start is None or self.end is None):
            raise ValueError("Both 'start' and 'end' must be provided together.")
        return self


class PreprocessConfig(BaseModel):
    scale: Optional[float] = None


class SourceConfig(BaseModel):
    type: Literal["clickhouse", "prometheus"] = "clickhouse"
    clickhouse: Optional[ClickHouseSourceConfig] = None
    prometheus: Optional[PrometheusSourceConfig] = None
    query: str = ""
    time_range: Optional[TimeRangeConfig] = None
    preprocess: Optional[PreprocessConfig] = None


# ── Detector sub-config ───────────────────────────────────────────────────────

class DetectorConfig(BaseModel):
    algorithm: str = "rolling_iqr"
    params: dict[str, Any] = Field(default_factory=dict)


# ── Output sub-config ─────────────────────────────────────────────────────────

class ClickHouseOutputConfig(BaseModel):
    table: str = "anomaly_results"


class OutputConfig(BaseModel):
    clickhouse: Optional[ClickHouseOutputConfig] = None
    console: bool = True
    only_anomalies: bool = True


# ── Per-metric config ─────────────────────────────────────────────────────────

class MetricConfig(BaseModel):
    service: str
    metric: str
    source: SourceConfig
    detector: DetectorConfig = Field(default_factory=DetectorConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)


# ── Top-level config ──────────────────────────────────────────────────────────

class AnomalyServiceConfig(BaseModel):
    defaults: dict[str, Any] = Field(default_factory=dict)
    metrics: list[dict[str, Any]]
    continue_on_error: bool = True

    def resolved_metrics(self) -> list[MetricConfig]:
        """Return list of MetricConfig after deep-merging defaults into each metric."""
        result: list[MetricConfig] = []
        for raw in self.metrics:
            merged = _deep_merge(copy.deepcopy(self.defaults), copy.deepcopy(raw))
            result.append(MetricConfig.model_validate(merged))
        return result


# ── Deep merge utility ────────────────────────────────────────────────────────

def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merge override into base. Override wins on scalar conflicts.
    Dicts are merged recursively; all other types (including lists) are replaced.
    """
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result
