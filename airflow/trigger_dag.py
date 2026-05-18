"""Triggers the anomaly_detector DAG via the Airflow REST API.

Run with hardcoded config:
    python airflow/trigger_dag.py

Run with config from file:
    python airflow/trigger_dag.py airflow/config_example.json
"""
import json
import sys
import urllib.request
import urllib.error
from base64 import b64encode
from pathlib import Path


# ── CONFIG ────────────────────────────────────────────────────────────────────

AIRFLOW_URL      = "http://localhost:8080"
AIRFLOW_USERNAME = "airflow"
AIRFLOW_PASSWORD = "airflow"

# ── ANOMALY-DETECTOR CONFIG ───────────────────────────────────────────────────

CONFIG = {
    "defaults": {
        "source": {
            "type": "prometheus",
            "prometheus": {
                "url": "https://prometheus.your-company.com",
                "step": "5m",
                "disable_ssl": True,
            },
            "time_range": {"lookback_days": 14},
        },
        "detector": {
            "algorithm": "rolling_iqr",
            "params": {
                "window": 60,
                "scale": 1.5,
                "min_periods": 30,
            },
        },
        "output": {
            "clickhouse": {"table": "anomaly_results"},
            "console": True,
            "only_anomalies": True,
        },
    },
    "metrics": [
        {
            "service": "airflow-worker",
            "metric": "memory_gb",
            "source": {
                "query": (
                    "sum(container_memory_working_set_bytes"
                    "{container='airflow-worker', node='ndp-v01wnl-n19'})"
                ),
                "preprocess": {"scale": 1e-9},
            },
        },
    ],
    "continue_on_error": True,
}

# ── RUN ───────────────────────────────────────────────────────────────────────

def _load_config() -> dict:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        print(f"Loading config from: {path}")
        return json.loads(path.read_text())
    return CONFIG


def main() -> None:
    url = f"{AIRFLOW_URL.rstrip('/')}/api/v1/dags/anomaly_detector/dagRuns"

    payload = {
        "conf": {
            "config_json": json.dumps(_load_config()),
        }
    }

    token = b64encode(f"{AIRFLOW_USERNAME}:{AIRFLOW_PASSWORD}".encode()).decode()
    body  = json.dumps(payload).encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Basic {token}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}", file=sys.stderr)
        sys.exit(1)

    print(f"dag_run_id:   {result['dag_run_id']}")
    print(f"state:        {result['state']}")
    print(f"logical_date: {result.get('logical_date', '—')}")


if __name__ == "__main__":
    main()
