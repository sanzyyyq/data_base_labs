"""Создаёт БД data/database.db из Excel-файлов в папке tables.
Запуск: python backend/convert.py (существующая БД будет пересоздана)."""

import re
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "database.db"
TABLES_DIR = BASE_DIR / "tables"


KEY = ["codvuz", "type", "regnumber"]


def next_regnumber(reg):
    """Рег. № на 1 больше: 002 → 003, Л5 → Л6 (ведущие нули сохраняются)."""
    m = re.fullmatch(r"(.*?)(\d+)(\D*)", reg)
    if not m:  # в номере нет цифр
        return reg + "1"
    head, num, tail = m.groups()
    return f"{head}{int(num) + 1:0{len(num)}d}{tail}"


def normalize_grnti(value):
    """Коды ГРНТИ через «; »: «02.61.45,27.35» → «02.61.45; 27.35».
    Части кода, разделённые запятыми, собираются обратно: «29.19.49;29,19,45» → «29.19.49; 29.19.45».
    """
    if not isinstance(value, str):
        return value
    codes, building = [], False  # building — код собирается из частей без точек
    for token in re.split(r"[;,\s]+", value.strip()):
        if not token:
            continue
        if building and "." not in token and len(codes[-1].split(".")) < 3:
            codes[-1] += "." + token
        else:
            codes.append(token)
            building = "." not in token
    return "; ".join(codes)


def make_keys_unique(nir):
    """Повторяющимся составным ключам (код вуза + форма + рег. №) увеличивает рег. номер
    на 1, пока ключ не станет уникальным; первая запись с таким ключом остаётся без изменений.
    """
    taken = set(map(tuple, nir[KEY].values))
    for i in nir.index[nir.duplicated(KEY)]:
        vuz, type_, reg = nir.loc[i, KEY]
        new = next_regnumber(reg)
        while (vuz, type_, new) in taken:
            new = next_regnumber(new)
        nir.loc[i, "regnumber"] = new
        taken.add((vuz, type_, new))
        print(f"Повтор ключа {vuz}/{type_}/{reg}: рег. № заменён на {new}")
    return nir


def convert():
    DB_PATH.parent.mkdir(exist_ok=True)
    DB_PATH.unlink(missing_ok=True)

    nir = pd.read_excel(TABLES_DIR / "Vyst_mo.xlsx", dtype={"regnumber": str})
    for col in nir.select_dtypes(exclude="number"):  # пробелы по краям текста
        nir[col] = nir[col].str.strip()
    nir = make_keys_unique(nir)
    nir["grnti"] = nir["grnti"].map(normalize_grnti)
    fields = [c for c in nir.columns if c != "codvuz"]

    with sqlite3.connect(DB_PATH) as conn:
        pd.read_excel(TABLES_DIR / "VUZ.xlsx").to_sql("vuz", conn, index=False)
        pd.read_excel(TABLES_DIR / "grntirub.xlsx").to_sql("grntirub", conn, index=False)
        # суррогатный ключ id нужен для изменения/удаления записей и для групп
        conn.executescript(f"""
            CREATE TABLE vyst_mo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codvuz INTEGER,
                {", ".join(f"{f} TEXT" for f in fields)},
                UNIQUE (codvuz, type, regnumber)
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
