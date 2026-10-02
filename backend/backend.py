import hashlib
import os
import re
import secrets
import shutil
import sqlite3
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_DIR = BASE_DIR / "data"
MAIN_DB_NAME = "database"
# путь можно переопределить, например для проверки на копии БД
DB_PATH = Path(os.environ.get("VYST_DB", DB_DIR / f"{MAIN_DB_NAME}.db"))

# Поля таблицы НИР (имена столбцов в БД)
F_VUZ = "Код ВУЗа"
F_VUZ_NAME = "Краткое наименование ВУЗа"
F_TYPE = "Форма НИР"
F_REG = "Регистрационный номер НИР"
F_SUBJECT = "Наименование проекта/НИР"
F_GRNTI = "Код ГРНТИ"
F_BOSS = "Руководитель"
F_BOSS_TITLE = "Должность руководителя"
F_EXHIBIT = "Наличие экспоната"
F_VYSTAVKI = "Информация о выставке"
F_EXPONAT = "Название выставочного экспоната"

# Составной ключ: код вуза + форма НИР + регистрационный номер НИР
KEY_FIELDS = [F_VUZ, F_TYPE, F_REG]

NIR_TYPES = {"Е": "Е — тематический план", "М": "М — НТП"}
EXHIBIT_TYPES = {"Е": "есть", "П": "планируется", "Н": "нет"}

COLUMN_ORDER = {
    "vyst_mo": [
        F_VUZ,
        F_TYPE,
        F_REG,
        F_EXHIBIT,
        F_VUZ_NAME,
        F_GRNTI,
        F_SUBJECT,
        F_BOSS,
        F_BOSS_TITLE,
        F_VYSTAVKI,
        F_EXPONAT,
    ],
    "vuz": [
        "Код",
        "Сокращенное наименование",
        "Город",
        "Профиль",
        "Статус",
        "Тип",
        "Расшифровка",
        "Полное наименование",
        "Федеральный округ",
        "Код субъекта РФ",
        "Субъект РФ",
    ],
    "grntirub": ["Код", "Наименование рубрики"],
}

# Сокращённые названия столбцов для отображения
SHORT_LABELS = {
    "vyst_mo": {
        F_VUZ: "Код вуза",
        F_TYPE: "Форма",
        F_REG: "Рег. №",
        F_EXHIBIT: "Экспонат",
        F_VUZ_NAME: "Вуз",
        F_GRNTI: "ГРНТИ",
        F_SUBJECT: "НИР",
        F_BOSS: "Руковод.",
        F_BOSS_TITLE: "Должность",
        F_VYSTAVKI: "Выставки",
        F_EXPONAT: "Назв. экспоната",
    },
    "vuz": {
        "Код": "Код",
        "Сокращенное наименование": "Вуз",
        "Город": "Город",
        "Профиль": "Профиль",
        "Статус": "Статус",
        "Тип": "Тип",
        "Расшифровка": "Наименование",
        "Полное наименование": "Полное наим.",
        "Федеральный округ": "Фед. округ",
        "Код субъекта РФ": "Код субъекта",
        "Субъект РФ": "Субъект РФ",
    },
    "grntirub": {"Код": "Код", "Наименование рубрики": "Рубрика"},
}

GRNTI_CODE_RE = re.compile(r"\d{2}\.\d{2}(\.\d{2})?")


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema():
    """Добавляет в БД то, чего не было в исходных данных: суррогатный ключ id
    у таблицы НИР (нужен для редактирования, удаления и групп), пользователей
    и группы НИР. Перед первой миграцией делается резервная копия БД."""
    with connect() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(vyst_mo)")]
        if "id" not in cols:
            shutil.copy2(DB_PATH, DB_PATH.with_suffix(".bak.db"))
            col_defs = ", ".join(f'"{c}"' for c in cols)
            conn.executescript(f"""
                ALTER TABLE vyst_mo RENAME TO vyst_mo_old;
                CREATE TABLE vyst_mo (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    "{F_VUZ}" INTEGER,
                    "{F_VUZ_NAME}" TEXT,
                    "{F_SUBJECT}" TEXT,
                    "{F_VYSTAVKI}" TEXT,
                    "{F_EXPONAT}" TEXT,
                    "{F_EXHIBIT}" TEXT,
                    "{F_TYPE}" TEXT,
                    "{F_REG}" TEXT,
                    "{F_GRNTI}" TEXT,
                    "{F_BOSS}" TEXT,
                    "{F_BOSS_TITLE}" TEXT
                );
                INSERT INTO vyst_mo ({col_defs}) SELECT {col_defs} FROM vyst_mo_old;
                DROP TABLE vyst_mo_old;
                """)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                login TEXT PRIMARY KEY,
                salt TEXT NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS nir_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                filter_desc TEXT,
                created TEXT DEFAULT (datetime('now', 'localtime'))
            );
            CREATE TABLE IF NOT EXISTS nir_group_items (
                group_id INTEGER NOT NULL REFERENCES nir_groups(id) ON DELETE CASCADE,
                nir_id INTEGER NOT NULL REFERENCES vyst_mo(id) ON DELETE CASCADE,
                included INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (group_id, nir_id)
            );
            """)
        if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            _create_user(conn, "admin", os.environ.get("DB_ADMIN_PASSWORD", "admin"))


# ---------- Вход ----------


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 100_000
    ).hex()


def _create_user(conn, login, password):
    salt = secrets.token_hex(16)
    conn.execute(
        "INSERT INTO users (login, salt, password_hash) VALUES (?, ?, ?)",
        (login, salt, _hash_password(password, salt)),
    )


def check_credentials(login, password):
    with connect() as conn:
        row = conn.execute(
            "SELECT salt, password_hash FROM users WHERE login = ?", (login,)
        ).fetchone()
    if row is None:
        return False
    return secrets.compare_digest(_hash_password(password, row[0]), row[1])


# ---------- Чтение данных ----------


def get_data(table_name):
    with connect() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table_name.lower()}", conn)
    if table_name.lower() == "vyst_mo":
        df = sort_by_key(df)
    return df


def sort_by_key(df, ascending=True):
    """Сортировка по составному ключу. Рег. номер сравнивается как число,
    если он числовой, иначе как строка."""
    reg = df[F_REG].astype(str).str.strip()
    order = df.assign(
        _vuz=pd.to_numeric(df[F_VUZ], errors="coerce"),
        _reg_num=pd.to_numeric(reg, errors="coerce"),
        _reg=reg,
    ).sort_values(
        ["_vuz", F_TYPE, "_reg_num", "_reg"],
        ascending=ascending,
        kind="stable",
        na_position="last",
    )
    return df.loc[order.index].reset_index(drop=True)


def get_vuz_list():
    with connect() as conn:
        return pd.read_sql_query(
            'SELECT "Код", "Сокращенное наименование", "Город", "Субъект РФ", '
            '"Федеральный округ" FROM vuz ORDER BY "Код"',
            conn,
        )


def get_rubrics():
    with connect() as conn:
        return pd.read_sql_query(
            'SELECT "Код", "Наименование рубрики" FROM grntirub ORDER BY "Код"', conn
        )


def get_geography():
    """Федеральные округа, субъекты и города из справочника вузов."""
    with connect() as conn:
        return pd.read_sql_query(
            'SELECT DISTINCT "Федеральный округ", "Субъект РФ", "Город" FROM vuz', conn
        ).dropna()


# ---------- Фильтр ----------


def split_grnti(value):
    return [p.strip() for p in re.split(r"[;,]\s*|\s+", str(value or "")) if p.strip()]


def apply_filter(df, flt):
    """Фильтрация НИР по географии вуза (поля таблицы vuz), коду/рубрике ГРНТИ
    и степени готовности экспоната."""
    if not flt:
        return df
    mask = pd.Series(True, index=df.index)

    geo_fields = {
        "regions": "Федеральный округ",
        "subjects": "Субъект РФ",
        "cities": "Город",
    }
    if any(flt.get(k) for k in geo_fields):
        vuz = get_vuz_list()
        for key, field in geo_fields.items():
            if flt.get(key):
                vuz = vuz[vuz[field].isin(flt[key])]
        mask &= df[F_VUZ].isin(vuz["Код"])

    if flt.get("rubrics"):
        prefixes = {f"{int(r):02d}" for r in flt["rubrics"]}
        mask &= df[F_GRNTI].apply(
            lambda v: any(c[:2] in prefixes for c in split_grnti(v))
        )
    if flt.get("grnti"):
        code = flt["grnti"].strip()
        mask &= df[F_GRNTI].apply(
            lambda v: any(c.startswith(code) for c in split_grnti(v))
        )

    if flt.get("exhibit"):
        mask &= df[F_EXHIBIT].isin(flt["exhibit"])

    return df[mask]


def describe_filter(flt):
    if not flt:
        return "без фильтра"
    parts = []
    names = {"regions": "Фед. округ", "subjects": "Субъект РФ", "cities": "Город"}
    for key, label in names.items():
        if flt.get(key):
            parts.append(f"{label}: {', '.join(flt[key])}")
    if flt.get("rubrics"):
        parts.append(
            "Рубрики ГРНТИ: " + ", ".join(f"{int(r):02d}" for r in flt["rubrics"])
        )
    if flt.get("grnti"):
        parts.append(f"Код ГРНТИ: {flt['grnti']}*")
    if flt.get("exhibit"):
        parts.append("Экспонат: " + ", ".join(EXHIBIT_TYPES[e] for e in flt["exhibit"]))
    return "; ".join(parts) if parts else "без фильтра"


# ---------- Изменение данных ----------


def _is_empty(value):
    return (
        value is None
        or (isinstance(value, float) and pd.isna(value))
        or str(value).strip() == ""
    )


def validate_record(record, record_id=None):
    """Возвращает список ошибок. Пустой список — запись корректна."""
    errors = []
    for field in (
        F_VUZ,
        F_TYPE,
        F_REG,
        F_SUBJECT,
        F_GRNTI,
        F_BOSS,
        F_BOSS_TITLE,
        F_EXHIBIT,
    ):
        if _is_empty(record.get(field)):
            errors.append(
                f"Поле «{SHORT_LABELS['vyst_mo'][field]}» не может быть пустым."
            )
    if errors:
        return errors

    with connect() as conn:
        if not conn.execute(
            'SELECT 1 FROM vuz WHERE "Код" = ?', (record[F_VUZ],)
        ).fetchone():
            errors.append(f"Вуза с кодом {record[F_VUZ]} нет в справочнике вузов.")

        dup = conn.execute(
            f'SELECT id FROM vyst_mo WHERE "{F_VUZ}" = ? AND "{F_TYPE}" = ? '
            f'AND TRIM("{F_REG}") = ? AND id IS NOT ?',
            (record[F_VUZ], record[F_TYPE], str(record[F_REG]).strip(), record_id),
        ).fetchone()
        if dup:
            errors.append(
                "Запись с таким составным ключом (код вуза + форма + рег. №) уже существует."
            )

        rubrics = {r[0] for r in conn.execute('SELECT "Код" FROM grntirub')}

    if record[F_TYPE] not in NIR_TYPES:
        errors.append("Форма НИР должна быть «Е» или «М».")

    for code in split_grnti(record[F_GRNTI]):
        if not GRNTI_CODE_RE.fullmatch(code):
            errors.append(f"Код ГРНТИ «{code}» должен иметь вид ХХ.ХХ или ХХ.ХХ.ХХ.")
        elif int(code[:2]) not in rubrics:
            errors.append(f"Рубрики ГРНТИ {code[:2]} нет в справочнике.")

    exhibit = record[F_EXHIBIT]
    if exhibit not in EXHIBIT_TYPES:
        errors.append("Наличие экспоната должно быть «Е», «П» или «Н».")
    elif exhibit == "Е" and _is_empty(record.get(F_VYSTAVKI)):
        errors.append("Если экспонат есть, нужно заполнить «Выставки».")
    elif exhibit == "П" and _is_empty(record.get(F_EXPONAT)):
        errors.append("Если экспонат планируется, нужно заполнить «Назв. экспоната».")
    elif exhibit == "Н" and not (
        _is_empty(record.get(F_VYSTAVKI)) and _is_empty(record.get(F_EXPONAT))
    ):
        errors.append(
            "Если экспоната нет, поля «Выставки» и «Назв. экспоната» должны быть пустыми."
        )

    return errors


def _vuz_short_name(conn, vuz_code):
    row = conn.execute(
        'SELECT "Сокращенное наименование" FROM vuz WHERE "Код" = ?', (vuz_code,)
    ).fetchone()
    return row[0] if row else None


def _q(field):
    return '"' + field + '"'


def _clean(record):
    return {
        k: (None if _is_empty(v) else str(v).strip() if isinstance(v, str) else v)
        for k, v in record.items()
    }


def add_record(record):
    record = _clean(record)
    errors = validate_record(record)
    if errors:
        raise ValueError("\n".join(errors))
    with connect() as conn:
        record[F_VUZ_NAME] = _vuz_short_name(conn, record[F_VUZ])
        fields = list(record)
        cur = conn.execute(
            f"INSERT INTO vyst_mo ({', '.join(_q(f) for f in fields)}) "
            f"VALUES ({', '.join('?' for _ in fields)})",
            [record[f] for f in fields],
        )
        return cur.lastrowid


def update_record(record_id, record):
    record = _clean(record)
    errors = validate_record(record, record_id)
    if errors:
        raise ValueError("\n".join(errors))
    with connect() as conn:
        record[F_VUZ_NAME] = _vuz_short_name(conn, record[F_VUZ])
        conn.execute(
            f"UPDATE vyst_mo SET {', '.join(_q(f) + ' = ?' for f in record)} WHERE id = ?",
            [*record.values(), record_id],
        )


def delete_record(record_id):
    with connect() as conn:
        conn.execute("DELETE FROM vyst_mo WHERE id = ?", (record_id,))


# ---------- Группы НИР ----------


def get_groups():
    with connect() as conn:
        return pd.read_sql_query(
            "SELECT g.id, g.name, g.filter_desc, g.created, COUNT(i.nir_id) AS n, "
            "COALESCE(SUM(i.included), 0) AS n_included "
            "FROM nir_groups g LEFT JOIN nir_group_items i ON i.group_id = g.id "
            "GROUP BY g.id ORDER BY g.name",
            conn,
        )


def create_group(name, filter_desc):
    name = name.strip()
    if not name:
        raise ValueError("Название группы не может быть пустым.")
    with connect() as conn:
        if conn.execute("SELECT 1 FROM nir_groups WHERE name = ?", (name,)).fetchone():
            raise ValueError(f"Группа «{name}» уже существует.")
        return conn.execute(
            "INSERT INTO nir_groups (name, filter_desc) VALUES (?, ?)",
            (name, filter_desc),
        ).lastrowid


def add_to_group(group_id, nir_ids):
    with connect() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO nir_group_items (group_id, nir_id) VALUES (?, ?)",
            [(group_id, int(i)) for i in nir_ids],
        )


def get_group_items(group_id):
    with connect() as conn:
        df = pd.read_sql_query(
            "SELECT v.*, i.included FROM nir_group_items i "
            "JOIN vyst_mo v ON v.id = i.nir_id WHERE i.group_id = ?",
            conn,
            params=(group_id,),
        )
    df["included"] = df["included"].astype(bool)
    return sort_by_key(df)


def save_group_marks(group_id, marks):
    """marks: {nir_id: включена ли НИР в группу экспонентов выставки}"""
    with connect() as conn:
        conn.executemany(
            "UPDATE nir_group_items SET included = ? WHERE group_id = ? AND nir_id = ?",
            [(int(v), group_id, int(k)) for k, v in marks.items()],
        )


def remove_from_group(group_id, nir_ids):
    with connect() as conn:
        conn.executemany(
            "DELETE FROM nir_group_items WHERE group_id = ? AND nir_id = ?",
            [(group_id, int(i)) for i in nir_ids],
        )


def delete_group(group_id):
    with connect() as conn:
        conn.execute("DELETE FROM nir_groups WHERE id = ?", (group_id,))
