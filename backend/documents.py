"""Формирование документов для печати: список группы НИР и карточка НИР."""

from datetime import datetime
from html import escape

import pandas as pd

from backend import backend as db

STYLE = """
<style>
  body { font-family: "Times New Roman", serif; font-size: 12pt; margin: 2em; color: #000; background: #fff; }
  h1 { font-size: 15pt; text-align: center; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #000; padding: 4px 6px; vertical-align: top; text-align: left; }
  th { background: #eee; }
  .meta { margin-bottom: 1em; }
  .card th { width: 30%; }
</style>
"""


def _v(value):
    return (
        ""
        if value is None or (isinstance(value, float) and pd.isna(value))
        else escape(str(value).strip())
    )


def _page(title, body):
    return (
        f"<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        f"<meta name='color-scheme' content='light'>"
        f"<title>{escape(title)}</title>{STYLE}</head><body>{body}</body></html>"
    )


def group_document(name, filter_desc, items):
    """Список группы НИР с условиями фильтрации, заданными при отборе."""
    rows = []
    for n, (_, r) in enumerate(items.iterrows(), 1):
        rows.append(
            "<tr>"
            f"<td>{n}</td><td>{_v(r[db.F_VUZ])}</td><td>{_v(r[db.F_VUZ_NAME])}</td>"
            f"<td>{_v(r[db.F_TYPE])}</td><td>{_v(r[db.F_REG])}</td><td>{_v(r[db.F_SUBJECT])}</td>"
            f"<td>{_v(r[db.F_GRNTI])}</td><td>{_v(r[db.F_BOSS])}</td>"
            f"<td>{escape(db.EXHIBIT_TYPES.get(r[db.F_EXHIBIT], _v(r[db.F_EXHIBIT])))}</td>"
            f"<td>{'да' if r['included'] else 'нет'}</td>"
            "</tr>"
        )
    body = (
        f"<h1>Группа НИР «{escape(name)}»</h1>"
        f"<div class='meta'>Условия отбора: {escape(filter_desc or 'без фильтра')}<br>"
        f"Всего НИР: {len(items)}, включено в выставку: {int(items['included'].sum())}<br>"
        f"Дата формирования: {datetime.now():%d.%m.%Y %H:%M}</div>"
        "<table><tr><th>№</th><th>Код вуза</th><th>Вуз</th><th>Форма</th><th>Рег. №</th>"
        "<th>Наименование НИР</th><th>ГРНТИ</th><th>Руководитель</th><th>Экспонат</th>"
        "<th>В выставку</th></tr>" + "".join(rows) + "</table>"
    )
    return _page(f"Группа НИР {name}", body)


# Стиль карточки внутри приложения: цвета берутся из текущей темы Streamlit
# (текст наследуется, фон и рамки полупрозрачные), поэтому карточка читается
# и в светлой, и в тёмной теме. Стили привязаны к классу .nir-card и не
# затрагивают остальную страницу.
APP_CARD_STYLE = """
<style>
  .nir-card { width: 100%; border-collapse: collapse; color: inherit; font-size: 0.95rem; }
  .nir-card th, .nir-card td {
    border: 1px solid rgba(128, 128, 128, 0.35);
    padding: 6px 10px; vertical-align: top; text-align: left; color: inherit;
  }
  .nir-card th { width: 32%; font-weight: 600; background: rgba(128, 128, 128, 0.12); }
  .nir-card td { background: transparent; white-space: pre-wrap; }
</style>
"""


def _card_fields(record):
    return [
        ("Код вуза", record[db.F_VUZ]),
        ("Вуз", record[db.F_VUZ_NAME]),
        ("Форма НИР", db.NIR_TYPES.get(record[db.F_TYPE], record[db.F_TYPE])),
        ("Регистрационный номер НИР", record[db.F_REG]),
        ("Наименование проекта/НИР", record[db.F_SUBJECT]),
        ("Код ГРНТИ", record[db.F_GRNTI]),
        ("Руководитель", record[db.F_BOSS]),
        ("Должность руководителя", record[db.F_BOSS_TITLE]),
        (
            "Наличие экспоната",
            db.EXHIBIT_TYPES.get(record[db.F_EXHIBIT], record[db.F_EXHIBIT]),
        ),
        ("Информация о выставке", record[db.F_VYSTAVKI]),
        ("Название выставочного экспоната", record[db.F_EXPONAT]),
    ]


def _card_rows(record):
    return "".join(
        f"<tr><th>{escape(k)}</th><td>{_v(v) or '—'}</td></tr>"
        for k, v in _card_fields(record)
    )


def nir_card(record):
    """Подробная карточка НИР — документ для скачивания и печати."""
    body = f"<h1>Карточка НИР</h1><table class='card'>{_card_rows(record)}</table>"
    return _page("Карточка НИР", body)


def nir_card_app(record):
    """Карточка НИР для показа в окне приложения (под светлую и тёмную тему)."""
    return f"{APP_CARD_STYLE}<table class='nir-card'>{_card_rows(record)}</table>"
