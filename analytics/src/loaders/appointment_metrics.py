"""Run appointment coverage activation or weekly refresh from the command line or Airflow."""

import argparse
import os
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

COMMANDS = {
    "enable": "SELECT appointment_metrics.enable()",
    "refresh": "SELECT appointment_metrics.refresh()",
}


def run(command: str) -> datetime | int:
    database_url = os.environ.get("APPOINTMENTS_ETL_DATABASE_URL")
    if not database_url:
        raise RuntimeError("Set APPOINTMENTS_ETL_DATABASE_URL before running the appointment ETL.")
    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg2")
    engine = create_engine(url, isolation_level="READ COMMITTED", hide_parameters=True)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
            conn.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
            return conn.execute(text(COMMANDS[command])).scalar_one()
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=COMMANDS)
    command = parser.parse_args().command
    try:
        result = run(command)
    except Exception as exc:
        # SQLAlchemy and psycopg exceptions can include connection details.
        raise SystemExit(f"Appointment ETL {command} failed ({type(exc).__name__}).") from None
    print(f"Appointment ETL {command} completed: {result}")


if __name__ == "__main__":
    main()
