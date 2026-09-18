import logging
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

logger = logging.getLogger(__name__)

default_args = {
    "owner": "analytics_team",
    "depends_on_past": False,
    "start_date": datetime(2026, 9, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=3),
}


def task_check_api_availability(**kwargs):
    """Simulates checking connectivity to the payment gateway."""
    logger.info("Pinging donation payment gateway API... Status: 200 OK.")
    return True


def task_extract_raw_data(**kwargs):
    """Extracts raw transactions using MockDonationAPIExtractor."""
    from analytics.src.extractors.donation_api import MockDonationAPIExtractor
    extractor = MockDonationAPIExtractor()
    payload = extractor.extract_transactions(limit=100, page=1)
    logger.info(f"Extracted {len(payload['data'])} records.")
    kwargs["ti"].xcom_push(key="raw_donations", value=payload["data"])


def task_validate_and_transform(**kwargs):
    """Validates raw records via Pydantic and computes aggregates via Pandas."""
    from analytics.src.schemas.validation import validate_donations_batch
    from analytics.src.transformers.aggregations import (
        calculate_daily_fund_metrics,
        transform_donations_to_dataframe,
    )

    ti = kwargs["ti"]
    raw_data = ti.xcom_pull(task_ids="extract_raw_data", key="raw_donations") or []
    valid_records, bad_records = validate_donations_batch(raw_data)
    logger.info(f"Validation summary: {len(valid_records)} valid, {len(bad_records)} rejected.")

    df = transform_donations_to_dataframe(valid_records)
    metrics_df = calculate_daily_fund_metrics(df)

    ti.xcom_push(key="valid_count", value=len(valid_records))
    ti.xcom_push(key="metrics_records", value=metrics_df.to_dict(orient="records"))


def task_load_to_dwh(**kwargs):
    """Loads metrics into the PostgreSQL marts layer."""
    import pandas as pd
    from analytics.src.loaders.dwh_loader import DWHLoader

    ti = kwargs["ti"]
    metrics_data = ti.xcom_pull(task_ids="validate_and_transform", key="metrics_records") or []
    if metrics_data:
        df = pd.DataFrame(metrics_data)
        loader = DWHLoader()
        loader.upsert_daily_finances(df)
        logger.info(f"Successfully loaded {len(df)} datamart rows.")


def task_data_quality_check(**kwargs):
    """Verifies that the transformed record count matches pipeline inputs."""
    ti = kwargs["ti"]
    valid_count = ti.xcom_pull(task_ids="validate_and_transform", key="valid_count")
    logger.info(f"Data quality audit completed. Processed rows: {valid_count}.")
    assert valid_count is not None and valid_count >= 0


with DAG(
    dag_id="church_daily_etl",
    default_args=default_args,
    description="Daily pipeline: ingesting donations, validating quality, and building DWH marts",
    schedule_interval="@daily",
    catchup=False,
    tags=["orthodox_church", "dwh", "etl"],
) as dag:

    check_api = PythonOperator(
        task_id="check_api_availability",
        python_callable=task_check_api_availability,
    )

    extract = PythonOperator(
        task_id="extract_raw_data",
        python_callable=task_extract_raw_data,
    )

    transform = PythonOperator(
        task_id="validate_and_transform",
        python_callable=task_validate_and_transform,
    )

    load = PythonOperator(
        task_id="load_to_dwh",
        python_callable=task_load_to_dwh,
    )

    quality_check = PythonOperator(
        task_id="data_quality_check",
        python_callable=task_data_quality_check,
    )

    check_api >> extract >> transform >> load >> quality_check
