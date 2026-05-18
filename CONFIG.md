# anomaly-detector — JSON Config Guide

The service accepts config two ways:
- environment variable `ANOMALY_SERVICE_CONFIG` (used in Kubernetes / Airflow)
- directly from a file: `python -m anomaly_service airflow/config_example.json`

---

## Top-level structure

```json
{
  "defaults":          { },     // shared settings — inherited by all metrics
  "metrics":           [ ],     // list of metrics (required, at least one)
  "continue_on_error": true     // do not abort on a single metric failure (default: true)
}
```

`defaults` and each `metrics` entry share the same schema.
On each metric, the service performs a **deep merge**: `defaults` is the base, metric fields override it.
This means you can describe the source and detector once in `defaults`, and only write differences per metric.

---

## Metric schema

```
{
  "service":  "my-service",   // required — service name
  "metric":   "memory_gb",    // required — metric name

  "source":   { ... },        // where to fetch data from
  "detector": { ... },        // which algorithm and params to use
  "output":   { ... }         // where to write results
}
```

---

## source — data source

```json
"source": {
  "type": "prometheus",         // "prometheus" | "clickhouse"

  "prometheus": {
    "url":         "http://prometheus:9090",
    "step":        "5m",        // scrape step
    "username":    "",
    "password":    "",
    "disable_ssl": false
  },

  "clickhouse": {               // used when type = "clickhouse"
    "host":     "localhost",
    "port":     8123,
    "user":     "default",
    "password": "",
    "database": "default"
  },

  "query": "sum(container_memory_working_set_bytes{container='svc'})",

  "time_range": {
    "lookback_days": 14         // OR explicit bounds:
    // "start": "2025-01-01T00:00:00Z",
    // "end":   "2025-02-01T00:00:00Z"
  },

  "preprocess": {
    "scale": 1e-9               // multiply all values by a factor (e.g. bytes → GB)
  }
}
```

`time_range` accepts either `lookback_days` or a `start`/`end` pair — not both.
If `time_range` is omitted, the service defaults to 90 days of lookback.

For ClickHouse queries, use `{start}` and `{end}` as named placeholders (ISO8601 strings):
```sql
SELECT ts, value FROM my_table WHERE ts BETWEEN {start} AND {end} ORDER BY ts
```

---

## detector — anomaly detection algorithm

```json
"detector": {
  "algorithm": "rolling_iqr",   // see algorithm list below
  "params":    { }              // algorithm-specific parameters
}
```

### Available algorithms

#### `rolling_iqr` — Rolling IQR Fence (default)

Flags points outside the rolling interquartile range fence.

```json
"detector": {
  "algorithm": "rolling_iqr",
  "params": {
    "window":      60,    // rolling window size in data points
    "scale":       1.5,   // fence multiplier (Tukey's k; use 3.0 for stricter)
    "min_periods": 30     // minimum points in window before scoring starts
  }
}
```

- **Lower bound**: rolling Q1 - scale × IQR
- **Upper bound**: rolling Q3 + scale × IQR
- **Score**: distance from the nearest violated bound, divided by IQR
- Best for: data with seasonal or non-stationary variance where a global baseline doesn't apply

#### `rolling_zscore` — Rolling Z-Score

Flags points whose Z-score exceeds a threshold in a sliding window.

```json
"detector": {
  "algorithm": "rolling_zscore",
  "params": {
    "window":      60,    // rolling window size in data points
    "threshold":   3.0,   // Z-score cutoff (1.5 = sensitive, 4.0 = conservative)
    "min_periods": 30     // minimum points in window before scoring starts
  }
}
```

- **Score**: |x - rolling_mean| / rolling_std
- **Anomaly**: score > threshold
- Best for: roughly Gaussian data where you expect few outliers

#### `mad` — Median Absolute Deviation (global)

Global, robust alternative to Z-score that is resistant to outliers.

```json
"detector": {
  "algorithm": "mad",
  "params": {
    "threshold": 3.5    // modified Z-score cutoff (3.5 is the Iglewicz-Hoaglin recommendation)
  }
}
```

- **Score**: 0.6745 × |x − median| / MAD
- **Anomaly**: score > threshold
- **Bounds**: median ± threshold × MAD / 0.6745
- Best for: short series, heavy-tailed distributions, or data with many repeated values

#### `isolation_forest` — Isolation Forest

Unsupervised ML detector; works well on complex, non-parametric distributions.
Requires `scikit-learn`.

```json
"detector": {
  "algorithm": "isolation_forest",
  "params": {
    "contamination":  0.05,    // expected fraction of anomalies (0.01–0.5)
    "n_estimators":   100,     // number of isolation trees
    "random_state":   42
  }
}
```

- **Score**: negated `score_samples` output (higher = more anomalous)
- **Anomaly**: model predicts -1 for the point
- **Bounds**: not applicable (NaN)
- Best for: complex multimodal distributions; requires enough data to fit

---

## output — where to write results

```json
"output": {
  "clickhouse": {
    "table": "anomaly_results"   // ClickHouse table (connection from env ANOMALY_CH_*)
  },
  "console":        true,        // print summary to stdout
  "only_anomalies": true         // true = write only anomalous points; false = write all points
}
```

When `only_anomalies` is `false`, every input point is written with its `is_anomaly` flag set to 0 or 1.
This is useful for dashboard exploration or baseline analysis.

### ClickHouse table schema

The table is created automatically (CREATE IF NOT EXISTS):

```sql
CREATE TABLE anomaly_results (
    detected_at   DateTime64(3),   -- when the detection run executed
    run_id        String,          -- Airflow run_id or a UUID
    service       String,
    metric        String,
    detector      String,          -- algorithm name
    timestamp     DateTime64(3),   -- original data point timestamp
    value         Float64,
    is_anomaly    UInt8,           -- 1 = anomaly, 0 = normal
    anomaly_score Float64,         -- higher = more anomalous
    lower_bound   Float64,         -- NaN if not applicable (e.g. isolation_forest)
    upper_bound   Float64
)
ENGINE = MergeTree()
ORDER BY (service, metric, detected_at, timestamp)
```

---

## Full example with defaults

```json
{
  "defaults": {
    "source": {
      "type": "prometheus",
      "prometheus": {
        "url":         "https://prometheus.internal",
        "step":        "5m",
        "disable_ssl": true
      },
      "time_range": { "lookback_days": 14 }
    },
    "detector": {
      "algorithm": "rolling_iqr",
      "params": { "window": 60, "scale": 1.5, "min_periods": 30 }
    },
    "output": {
      "clickhouse": { "table": "anomaly_results" },
      "console":        true,
      "only_anomalies": true
    }
  },
  "metrics": [
    {
      "service": "api-gateway",
      "metric":  "memory_gb",
      "source": {
        "query": "sum(container_memory_working_set_bytes{container='api-gateway'})",
        "preprocess": { "scale": 1e-9 }
      }
    },
    {
      "service": "api-gateway",
      "metric":  "rps",
      "source": {
        "query": "sum(rate(http_requests_total{service='api-gateway'}[1m]))"
      },
      "detector": {
        "algorithm": "rolling_zscore",
        "params": { "window": 120, "threshold": 2.5 }
      }
    },
    {
      "service": "db",
      "metric":  "query_latency_p99_ms",
      "source": {
        "type": "clickhouse",
        "clickhouse": {
          "host": "clickhouse.internal",
          "port": 8123,
          "user": "default",
          "password": "",
          "database": "metrics"
        },
        "query": "SELECT toStartOfMinute(ts), quantile(0.99)(latency_ms) FROM query_log WHERE ts BETWEEN {start} AND {end} GROUP BY 1 ORDER BY 1",
        "time_range": { "lookback_days": 7 }
      },
      "detector": {
        "algorithm": "mad",
        "params": { "threshold": 3.5 }
      }
    },
    {
      "service": "worker",
      "metric":  "queue_depth",
      "source": {
        "query": "rabbitmq_queue_messages{queue='main'}"
      },
      "detector": {
        "algorithm": "isolation_forest",
        "params": { "contamination": 0.03 }
      }
    },
    {
      "service": "api-gateway",
      "metric":  "error_rate",
      "source": {
        "query": "sum(rate(http_requests_total{service='api-gateway',status=~'5..'}[1m])) / sum(rate(http_requests_total{service='api-gateway'}[1m]))"
      },
      "output": {
        "clickhouse": { "table": "anomaly_results" },
        "console":        true,
        "only_anomalies": false
      }
    }
  ],
  "continue_on_error": true
}
```

---

## How to run

### Direct (without Airflow)

```bash
# From a config file
python -m anomaly_service airflow/config_example.json

# From env var
ANOMALY_SERVICE_CONFIG=$(cat airflow/config_example.json) \
ANOMALY_CH_HOST=localhost \
ANOMALY_CH_PORT=8123 \
python -m anomaly_service
```

### Via Airflow

```bash
# With hardcoded config in trigger_dag.py
python airflow/trigger_dag.py

# With config from file
python airflow/trigger_dag.py airflow/config_example.json
```

Required Airflow Variables (set in Admin → Variables):
- `ANOMALY_DETECTOR_IMAGE` — Docker image tag
- `ANOMALY_DETECTOR_NAMESPACE` — Kubernetes namespace
- `ANOMALY_DETECTOR_DATA_PVC` — PVC name
- `ANOMALY_CH_HOST`, `ANOMALY_CH_PORT`, `ANOMALY_CH_USER`, `ANOMALY_CH_PASSWORD`, `ANOMALY_CH_DATABASE`
