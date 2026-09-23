import shutil
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "data"
MAIN_DB_NAME = "database"

COLUMN_ORDER = {
    "vyst_mo": [
        "codvuz",
        "type",
        "regnumber",
        "shortname",
        "subject",
        "grnti",
        "bossname",
        "bosstitle",
        "exhitype",
        "vystavki",
        "exponat",
    ],
    "vuz": [
        "codvuz",
        "shortname",
        "city",
        "profile",
        "status",
        "gr_ved",
        "name",
        "fullname",
        "region",
        "obl",
        "oblname",
    ],
    "grntirub": ["codrub", "rubrika"],
}


def get_profiles_list():
    return [f.stem for f in DB_DIR.iterdir() if f.is_file()]


def get_data(table_name, profile):
    with sqlite3.connect(DB_DIR / f"{profile}.db") as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table_name.lower()}", conn)
    return df


def make_db_copy(current_profile, new_profile):
    shutil.copy2(DB_DIR / f"{current_profile}.db", DB_DIR / f"{new_profile}.db")


def import_data(profile, table_name, data):
    db_file_path = DB_DIR / f"{profile}.db"
    conn = sqlite3.connect(db_file_path)
    try:
        data.to_sql(name=table_name.lower(), con=conn, if_exists="replace", index=False)
    except Exception as e:
        raise e
    finally:
        conn.close()
