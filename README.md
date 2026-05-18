# anomaly-detector

A standalone Python service that fetches a time series from Prometheus or ClickHouse, runs an anomaly detection algorithm on it, and writes results (timestamp, value, is_anomaly flag, score, bounds) to ClickHouse and/or the console. Controlled entirely by a JSON config.

## Install

```bash
pip install -r requirements.txt
```

Copy and fill in the environment file:

```bash
cp .env.anomaly-detector.example .env.anomaly-detector
# edit .env.anomaly-detector with your ClickHouse connection details
```

## Run

```bash
# From a config file
python -m anomaly_service airflow/config_example.json

# From env var (production / Docker / Airflow)
ANOMALY_SERVICE_CONFIG=$(cat airflow/config_example.json) python -m anomaly_service

# Trigger via Airflow REST API
python airflow/trigger_dag.py airflow/config_example.json
```

## Algorithms

| Name | Best for |
|------|----------|
| `rolling_iqr` | Non-stationary data with time-varying variance |
| `rolling_zscore` | Roughly Gaussian data with a sliding baseline |
| `mad` | Short series or heavy-tailed distributions |
| `isolation_forest` | Complex, non-parametric distributions (requires scikit-learn) |

## Configuration

See [CONFIG.md](CONFIG.md) for the full config schema, all algorithm parameters, and examples.

## Output

Results are written to a ClickHouse table (schema auto-created) with one row per point:

| Column | Description |
|--------|-------------|
| `detected_at` | When the detection run executed |
| `run_id` | Airflow run_id or UUID |
| `service` / `metric` | Source identifiers |
| `detector` | Algorithm name |
| `timestamp` | Original data point timestamp |
| `value` | Observed value |
| `is_anomaly` | 1 = anomalous, 0 = normal |
| `anomaly_score` | Higher = more anomalous |
| `lower_bound` / `upper_bound` | Detection fence (NaN for isolation_forest) |
