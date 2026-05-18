"""ClickHouse output sink — writes anomaly detection results to a table."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from anomaly_service.detectors.base import AnomalyResult
from anomaly_service.settings import Settings

logger = logging.getLogger(__name__)

_CREATE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    detected_at   DateTime64(3),
    run_id        String,
    service       String,
    metric        String,
    detector      String,
    timestamp     DateTime64(3),
    value         Float64,
    is_anomaly    UInt8,
    anomaly_score Float64,
    lower_bound   Float64,
    upper_bound   Float64
)
ENGINE = MergeTree()
ORDER BY (service, metric, detected_at, timestamp)
"""


class ClickHouseSink:
    """
    Writes AnomalyResult rows to a ClickHouse table.

    The table is created (IF NOT EXISTS) on first use.
    When only_anomalies=True, only rows with is_anomaly=True are inserted.
    """

    def __init__(self, settings: Settings, table: str = "anomaly_results", run_id: str = "") -> None:
        self._settings = settings
        self._table = table
        self._run_id = run_id

    def _get_client(self):  # type: ignore[return]
        try:
            import clickhouse_connect  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "clickhouse-connect is required for ClickHouseSink. "
                "Install it with: pip install clickhouse-connect"
            ) from exc

        s = self._settings
        return clickhouse_connect.get_client(
            host=s.anomaly_ch_host,
            port=s.anomaly_ch_port,
            username=s.anomaly_ch_user,
            password=s.anomaly_ch_password,
            database=s.anomaly_ch_database,
        )

    def _ensure_table(self, client: object) -> None:
        ddl = _CREATE_TABLE_DDL.format(table=self._table)
        client.command(ddl)  # type: ignore[attr-defined]
        logger.debug("Ensured table '%s' exists.", self._table)

    def write(self, result: AnomalyResult, only_anomalies: bool = True) -> None:
        client = self._get_client()
        self._ensure_table(client)

        detected_at = datetime.now(tz=timezone.utc)

        points = result.points if not only_anomalies else [p for p in result.points if p.is_anomaly]

        if not points:
            logger.info(
                "ClickHouseSink: no points to insert for %s/%s (only_anomalies=%s, anomalies=%d).",
                result.service,
                result.metric,
                only_anomalies,
                result.anomaly_count,
            )
            return

        rows: list[list] = []
        for p in points:
            rows.append([
                detected_at,
                self._run_id,
                result.service,
                result.metric,
                result.detector_name,
                p.timestamp.to_pydatetime() if hasattr(p.timestamp, "to_pydatetime") else p.timestamp,
                p.value,
                int(p.is_anomaly),
                p.score,
                p.lower_bound,
                p.upper_bound,
            ])

        column_names = [
            "detected_at", "run_id", "service", "metric", "detector",
            "timestamp", "value", "is_anomaly", "anomaly_score",
            "lower_bound", "upper_bound",
        ]

        try:
            client.insert(  # type: ignore[attr-defined]
                table=self._table,
                data=rows,
                column_names=column_names,
            )
            logger.info(
                "ClickHouseSink: inserted %d rows into '%s' for %s/%s.",
                len(rows),
                self._table,
                result.service,
                result.metric,
            )
        except Exception as exc:
            logger.error("ClickHouseSink: insert failed: %s", exc)
            raise
