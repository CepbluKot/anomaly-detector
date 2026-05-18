"""Protocol definition for data sources."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class DataSource(Protocol):
    """Fetch a time series for a given query and time range."""

    def fetch(self, query: str, start: datetime, end: datetime) -> pd.Series:
        """
        Fetch metric data.

        Parameters
        ----------
        query:
            SQL query (for ClickHouse) or PromQL expression (for Prometheus).
        start:
            Inclusive start of the time range (UTC).
        end:
            Inclusive end of the time range (UTC).

        Returns
        -------
        pd.Series
            DatetimeIndex (UTC, sorted ascending), float values.
        """
        ...
