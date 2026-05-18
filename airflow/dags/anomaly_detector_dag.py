"""
Airflow DAG: Anomaly Detector

Runs the anomaly-detector service as a Pod in Kubernetes.
Accepts a JSON metric config, detects anomalies, saves results to ClickHouse.

Airflow Variables (Admin → Variables):
  ANOMALY_DETECTOR_IMAGE      — Docker image (default: registry.your-company.com/anomaly-detector:latest)
  ANOMALY_DETECTOR_NAMESPACE  — Kubernetes namespace (default: airflow)
  ANOMALY_DETECTOR_DATA_PVC   — PVC for artifacts (default: anomaly-detector-data)

Params (set when triggering manually):
  config_json  — full JSON config for the anomaly service
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from airflow import DAG
from airflow.models import Param, Variable
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import models as k8s

# ── CONFIG ────────────────────────────────────────────────────────────────────

IMAGE     = Variable.get("ANOMALY_DETECTOR_IMAGE",     default_var="registry.your-company.com/anomaly-detector:latest")
NAMESPACE = Variable.get("ANOMALY_DETECTOR_NAMESPACE", default_var="airflow")
DATA_PVC  = Variable.get("ANOMALY_DETECTOR_DATA_PVC",  default_var="anomaly-detector-data")

# ── DAG ───────────────────────────────────────────────────────────────────────

default_args = {
    "owner": "airflow",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

_CONFIG_EXAMPLE = json.dumps({
    "defaults": {
        "source": {
            "type": "prometheus",
            "prometheus": {
                "url": "http://prometheus:9090",
                "step": "5m",
                "disable_ssl": True,
            },
            "time_range": {"lookback_days": 14},
        },
        "detector": {
            "algorithm": "rolling_iqr",
            "params": {"window": 60, "scale": 1.5},
        },
        "output": {
            "clickhouse": {"table": "anomaly_results"},
            "console": True,
            "only_anomalies": True,
        },
    },
    "metrics": [
        {
            "service": "api-gateway",
            "metric": "memory_gb",
            "source": {
                "query": "sum(container_memory_working_set_bytes{container='api-gateway'})",
                "preprocess": {"scale": 1e-9},
            },
        }
    ],
    "continue_on_error": True,
}, indent=2)

with DAG(
    dag_id="anomaly_detector",
    default_args=default_args,
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["anomaly-detector", "anomaly", "ml", "k8s"],
    params={
        "config_json": Param(
            _CONFIG_EXAMPLE,
            type="string",
            description=(
                "JSON config for the anomaly-detector service: metrics[], defaults, continue_on_error. "
                "Full schema — see CONFIG.md."
            ),
        ),
    },
) as dag:

    run_anomaly_detector = KubernetesPodOperator(
        task_id="run_anomaly_detector",
        name="anomaly-detector",
        namespace=NAMESPACE,
        image=IMAGE,
        image_pull_policy="Always",

        env_vars={
            "ANOMALY_CH_HOST":     "{{ var.value.ANOMALY_CH_HOST }}",
            "ANOMALY_CH_PORT":     "{{ var.value.ANOMALY_CH_PORT }}",
            "ANOMALY_CH_USER":     "{{ var.value.ANOMALY_CH_USER }}",
            "ANOMALY_CH_PASSWORD": "{{ var.value.ANOMALY_CH_PASSWORD }}",
            "ANOMALY_CH_DATABASE": "{{ var.value.ANOMALY_CH_DATABASE }}",
            "ANOMALY_SERVICE_CONFIG": "{{ params.config_json }}",
            "AIRFLOW_RUN_ID":         "{{ run_id }}",
        },

        security_context=k8s.V1PodSecurityContext(
            run_as_non_root=True,
            run_as_user=1000,
        ),
        container_security_context=k8s.V1SecurityContext(
            read_only_root_filesystem=False,
            run_as_non_root=True,
            run_as_user=1000,
        ),

        volumes=[
            k8s.V1Volume(
                name="data",
                persistent_volume_claim=k8s.V1PersistentVolumeClaimVolumeSource(claim_name=DATA_PVC),
            ),
            k8s.V1Volume(
                name="tmp",
                empty_dir=k8s.V1EmptyDirVolumeSource(),
            ),
        ],

        volume_mounts=[
            k8s.V1VolumeMount(name="data", mount_path="/data"),
            k8s.V1VolumeMount(name="tmp",  mount_path="/tmp"),
        ],

        container_resources=k8s.V1ResourceRequirements(
            requests={"cpu": "250m", "memory": "512Mi"},
            limits={"cpu": "2",     "memory": "4Gi"},
        ),

        get_logs=True,
        is_delete_operator_pod=True,
        in_cluster=True,
    )
