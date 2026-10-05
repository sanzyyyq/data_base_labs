"""Создаёт БД data/database.db из Excel-файлов в папке tables.
Запуск: python backend/convert.py (существующая БД будет пересоздана)."""

import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "database.db"
TABLES_DIR = BASE_DIR / "tables"


def convert():
    DB_PATH.parent.mkdir(exist_ok=True)
    DB_PATH.unlink(missing_ok=True)

    nir = pd.read_excel(TABLES_DIR / "Vyst_mo.xlsx", dtype={"regnumber": str})
    nir = nir.apply(lambda c: c.str.strip() if c.dtype == object else c)
    fields = [c for c in nir.columns if c != "codvuz"]

    with sqlite3.connect(DB_PATH) as conn:
        pd.read_excel(TABLES_DIR / "VUZ.xlsx").to_sql("vuz", conn, index=False)
        pd.read_excel(TABLES_DIR / "grntirub.xlsx").to_sql("grntirub", conn, index=False)
        # суррогатный ключ id нужен для изменения/удаления записей и для групп;
        # составной ключ (codvuz, type, regnumber) в исходных данных не уникален
        conn.executescript(f"""
            CREATE TABLE vyst_mo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codvuz INTEGER,
                {", ".join(f"{f} TEXT" for f in fields)}
            );
            CREATE TABLE nir_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                filter_desc TEXT
            );
            CREATE TABLE nir_group_items (
                group_id INTEGER REFERENCES nir_groups(id) ON DELETE CASCADE,
                nir_id INTEGER REFERENCES vyst_mo(id) ON DELETE CASCADE,
                included INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (group_id, nir_id)
            );
        """)
        nir.to_sql("vyst_mo", conn, if_exists="append", index=False)
        for table in ("vuz", "grntirub", "vyst_mo"):
            (n,) = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            print(f"{table}: {n} строк")
    print(f"БД сохранена: {DB_PATH}")


if __name__ == "__main__":
    convert()
