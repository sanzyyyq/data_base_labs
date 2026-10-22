import re
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "database.db"
TABLES_DIR = BASE_DIR / "tables"
KEY = ["codvuz", "type", "regnumber"]


def next_regnumber(reg):
    m = re.fullmatch(r"(.*?)(\d+)(\D*)", reg)
    if not m:
        return reg + "1"
    head, num, tail = m.groups()
    return f"{head}{int(num) + 1:0{len(num)}d}{tail}"


def normalize_grnti(value):
    if not isinstance(value, str):
        return value
    codes, building = [], False
    for token in re.split(r"[;,\s]+", value.strip()):
        if not token:
            continue
        if building and "." not in token and len(codes[-1].split(".")) < 3:
            codes[-1] += "." + token
        else:
            codes.append(token)
            building = "." not in token
    return "; ".join(codes)


def fix_vuz_codes(nir, vuz):
    codes = sorted(vuz["codvuz"])
    names = dict(zip(vuz["codvuz"], vuz["shortname"]))
    for code in sorted(set(nir["codvuz"]) - set(codes)):
        new = min(codes, key=lambda c: (abs(c - code), c))
        rows = nir["codvuz"] == code
        nir.loc[rows, "codvuz"] = new
        nir.loc[rows, "shortname"] = names[new]
        print(
            f"Вуза с кодом {code} нет в справочнике: код заменён на {new} ({names[new]}), записей: {rows.sum()}"
        )
    return nir


def make_keys_unique(nir):
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

    vuz = pd.read_excel(TABLES_DIR / "VUZ.xlsx")
    nir = pd.read_excel(TABLES_DIR / "Vyst_mo.xlsx", dtype={"regnumber": str})
    for col in nir.select_dtypes(exclude="number"):
        nir[col] = nir[col].str.strip()
    nir = fix_vuz_codes(nir, vuz)
    nir = make_keys_unique(nir)
    nir["grnti"] = nir["grnti"].map(normalize_grnti)
    fields = [c for c in nir.columns if c != "codvuz"]

    with sqlite3.connect(DB_PATH) as conn:
        vuz.to_sql("vuz", conn, index=False)
        pd.read_excel(TABLES_DIR / "grntirub.xlsx").to_sql("grntirub", conn, index=False)
        conn.executescript(f"""
            CREATE TABLE vyst_mo (
                id INTEGER PRIMARY KEY,
                codvuz INTEGER,
                {", ".join(f"{f} TEXT" for f in fields)},
                UNIQUE (codvuz, type, regnumber)
            );
            CREATE TABLE nir_groups (
                id INTEGER PRIMARY KEY,
                name TEXT UNIQUE,
                filter_desc TEXT
            );
            CREATE TABLE nir_group_items (
                group_id INTEGER REFERENCES nir_groups(id) ON DELETE CASCADE,
                nir_id INTEGER REFERENCES vyst_mo(id) ON DELETE CASCADE,
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
