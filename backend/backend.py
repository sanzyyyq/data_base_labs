import re
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "database.db"

LABELS = {
    "vyst_mo": {
        "codvuz": "Код вуза",
        "type": "Форма НИР",
        "regnumber": "Рег. №",
        "exhitype": "Экспонат",
        "subject": "Наименование НИР",
        "grnti": "Код ГРНТИ",
        "shortname": "Вуз",
        "bossname": "Руководитель",
        "bosstitle": "Должность",
        "vystavki": "Информация о выставке",
        "exponat": "Название экспоната",
    },
    "vuz": {
        "codvuz": "Код",
        "shortname": "Сокр. наименование",
        "city": "Город",
        "profile": "Профиль",
        "status": "Статус",
        "gr_ved": "Тип",
        "name": "Наименование",
        "fullname": "Полное наименование",
        "region": "Федеральный округ",
        "obl": "Код субъекта",
        "oblname": "Субъект РФ",
    },
    "grntirub": {"codrub": "Код", "rubrika": "Рубрика"},
}
NIR_FIELDS = list(LABELS["vyst_mo"])
NIR_TYPES = ["Е", "М"]
EXHIBIT_TYPES = {"Е": "есть", "П": "планируется", "Н": "нет"}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, params=()):
    with connect() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def get_table(table):
    return query(f"SELECT * FROM {table}")


def sort_by_key(df, ascending=True):
    """Сортировка по составному ключу: код вуза + форма НИР + рег. номер."""
    tmp = df.assign(
        _vuz=pd.to_numeric(df["codvuz"], errors="coerce"),
        _reg=pd.to_numeric(df["regnumber"], errors="coerce"),
    )
    order = tmp.sort_values(["_vuz", "type", "_reg", "regnumber"], ascending=ascending)
    return df.loc[order.index].reset_index(drop=True)


def split_grnti(value):
    return [p for p in re.split(r"[;,\s]+", str(value or "")) if p]


GEO_FIELDS = ("region", "oblname", "city", "codvuz")  # поля фильтра из справочника вузов


def vuz_names():
    """{код вуза: сокращённое наименование}"""
    vuz = get_table("vuz")
    return dict(zip(vuz["codvuz"], vuz["shortname"]))


def rubric_names():
    """{код рубрики ГРНТИ: «XX - название рубрики»}"""
    rub = get_table("grntirub")
    return {c: f"{c:02d} - {r}" for c, r in zip(rub["codrub"], rub["rubrika"])}


def record_rubrics(grnti):
    """Рубрики (первые две цифры) кодов ГРНТИ записи."""
    return {int(c[:2]) for c in split_grnti(grnti) if re.match(r"\d{2}\.", c)}


def apply_filter(df, flt):
    geo = {k: v for k, v in flt.items() if k in GEO_FIELDS and v}
    if geo:
        vuz = get_table("vuz")
        for field, values in geo.items():
            vuz = vuz[vuz[field].isin(values)]
        df = df[df["codvuz"].astype(int).isin(vuz["codvuz"])]
    if flt.get("rubrics"):
        df = df[
            df["grnti"].apply(lambda v: bool(record_rubrics(v) & set(flt["rubrics"])))
        ]
    if flt.get("exhitype"):
        df = df[df["exhitype"].isin(flt["exhitype"])]
    return df


def describe_filter(flt):
    """Условия фильтра по-русски, например «Город: Владивосток; Экспонат: есть»."""
    labels = {
        "region": "Федеральный округ",
        "oblname": "Субъект РФ",
        "city": "Город",
        "codvuz": "Вуз",
        "rubrics": "Рубрика ГРНТИ",
        "exhitype": "Экспонат",
    }
    parts = []
    for key, value in flt.items():
        if key == "exhitype":
            value = [EXHIBIT_TYPES[v] for v in value]
        if key == "codvuz":
            names = vuz_names()
            value = [names[v] for v in value]
        if key == "rubrics":
            names = rubric_names()
            value = [names[v] for v in value]
        parts.append(
            f"{labels[key]}: {value if isinstance(value, str) else ', '.join(value)}"
        )
    return "; ".join(parts) or "без фильтра"


def validate(rec, rec_id=None):
    errors = [
        f"Не заполнено поле «{LABELS['vyst_mo'][f]}»"
        for f in ("codvuz", "type", "regnumber", "subject", "grnti", "exhitype")
        if not rec.get(f)
    ]
    if errors:
        return errors
    with connect() as conn:
        if not conn.execute(
            "SELECT 1 FROM vuz WHERE codvuz = ?", (rec["codvuz"],)
        ).fetchone():
            errors.append("Вуза с таким кодом нет в справочнике")
        if conn.execute(
            "SELECT 1 FROM vyst_mo WHERE codvuz = ? AND type = ? AND regnumber = ? AND id IS NOT ?",
            (rec["codvuz"], rec["type"], rec["regnumber"], rec_id),
        ).fetchone():
            errors.append("Запись с таким ключом (вуз + форма + рег. №) уже есть")
        rubrics = {r for (r,) in conn.execute("SELECT codrub FROM grntirub")}
    for code in split_grnti(rec["grnti"]):
        if not re.fullmatch(r"\d{2}\.\d{2}(\.\d{2})?", code):
            errors.append(f"Код ГРНТИ «{code}» должен иметь вид ХХ.ХХ.ХХ")
        elif int(code[:2]) not in rubrics:
            errors.append(f"Рубрики ГРНТИ {code[:2]} нет в справочнике")
    return errors


def save_record(rec, rec_id=None):
    """Добавляет (rec_id=None) или изменяет запись НИР. Возвращает (ошибки, id записи)."""
    rec = {k: (str(v).strip() or None) if v is not None else None for k, v in rec.items()}
    errors = validate(rec, rec_id)
    if errors:
        return errors, None
    with connect() as conn:
        (rec["shortname"],) = conn.execute(
            "SELECT shortname FROM vuz WHERE codvuz = ?", (rec["codvuz"],)
        ).fetchone()
        if rec_id is None:
            rec_id = conn.execute(
                f"INSERT INTO vyst_mo ({', '.join(rec)}) VALUES ({', '.join('?' * len(rec))})",
                list(rec.values()),
            ).lastrowid
        else:
            conn.execute(
                f"UPDATE vyst_mo SET {', '.join(f'{k} = ?' for k in rec)} WHERE id = ?",
                [*rec.values(), rec_id],
            )
    return [], rec_id


def execute(sql, params=()):
    with connect() as conn:
        return conn.execute(sql, params).lastrowid


def get_groups():
    return query("SELECT * FROM nir_groups ORDER BY name")


def add_to_group(name, filter_desc, nir_ids):
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO nir_groups (name, filter_desc) VALUES (?, ?)",
            (name, filter_desc),
        )
        (group_id,) = conn.execute(
            "SELECT id FROM nir_groups WHERE name = ?", (name,)
        ).fetchone()
        conn.executemany(
            "INSERT OR IGNORE INTO nir_group_items (group_id, nir_id) VALUES (?, ?)",
            [(group_id, int(i)) for i in nir_ids],
        )


def get_group_items(group_id):
    df = query(
        "SELECT v.*, i.included FROM nir_group_items i JOIN vyst_mo v ON v.id = i.nir_id "
        "WHERE i.group_id = ?",
        (group_id,),
    )
    df["included"] = df["included"].astype(bool)
    return sort_by_key(df)


def save_marks(group_id, marks):
    with connect() as conn:
        conn.executemany(
            "UPDATE nir_group_items SET included = ? WHERE group_id = ? AND nir_id = ?",
            [(int(v), group_id, int(k)) for k, v in marks.items()],
        )
