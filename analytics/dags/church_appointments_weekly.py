from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.bash import BashOperator

with DAG(
    dag_id="church_appointments_weekly",
    description="Publish weekly appointment counts",
    start_date=pendulum.datetime(2026, 11, 23, 1, tz="Europe/Moscow"),
    schedule_interval="0 1 * * 1",
    catchup=False,
    max_active_runs=1,
    tags=["orthodox_church", "dwh", "etl"],
) as dag:
    refresh = BashOperator(
        task_id="refresh",
        bash_command="python -m analytics.src.loaders.appointment_metrics refresh",
        retries=6,
        retry_delay=timedelta(minutes=5),
        do_xcom_push=False,
    )
