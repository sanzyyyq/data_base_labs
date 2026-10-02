import pandas as pd
import streamlit as st

from backend import backend as db
from backend.documents import group_document, nir_card, nir_card_app

DATA_TABLES = ["VYST_MO", "VUZ", "GRNTIRUB"]
TABLE_KEY = "nir_table"
ROW_HEIGHT = 35

st.set_page_config(layout="wide", page_title="Выставочные экспонаты")


@st.cache_resource
def init_db():
    db.ensure_schema()


init_db()

defaults = {
    "page": "Данные",
    "user": None,
    "filters": {},
    "sort_desc": False,
    "select_id": None,  # id записи, на которую нужно поставить курсор
    "dialog_n": 0,  # счётчик открытий диалога: даёт полям формы свежие ключи
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)


def logged_in():
    return st.session_state.user is not None


def display_frame(df, table):
    """Копия таблицы для показа: расшифрованное наличие экспоната."""
    df = df.copy()
    if table == "vyst_mo":
        df[db.F_EXHIBIT] = df[db.F_EXHIBIT].map(db.EXHIBIT_TYPES).fillna(df[db.F_EXHIBIT])
    return df


def column_config(table):
    labels = db.SHORT_LABELS[table]
    wide = {
        db.F_SUBJECT,
        db.F_VYSTAVKI,
        db.F_EXPONAT,
        "Полное наименование",
        "Наименование рубрики",
    }
    small = {db.F_VUZ, db.F_TYPE, db.F_REG, "Код", "Тип", "Профиль"}
    cfg = {}
    for col, label in labels.items():
        width = "large" if col in wide else "small" if col in small else "medium"
        cfg[col] = st.column_config.Column(label, width=width, help=col)
    return cfg


def scroll_table_to(row):
    """Прокручивает таблицу НИР так, чтобы строка row оказалась в середине."""
    st.session_state.dialog_n += 1  # уникальный текст, чтобы скрипт выполнился заново
    st.html(
        f"""<script>/* {st.session_state.dialog_n} */
        (() => {{
          let tries = 0;
          const timer = setInterval(() => {{
            const sc = document.querySelector(".st-key-{TABLE_KEY} .dvn-scroller");
            if (sc && sc.scrollHeight > sc.clientHeight) {{
              sc.scrollTop = Math.max(0, ({row} + 1) * {ROW_HEIGHT} - sc.clientHeight / 2);
              clearInterval(timer);
            }}
            if (++tries > 50) clearInterval(timer);
          }}, 100);
        }})();
        </script>""",
        unsafe_allow_javascript=True,
    )


# ---------- Диалоги ----------


@st.dialog("Вход")
def login_dialog():
    with st.form("login_form", border=False):
        login = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        submitted = st.form_submit_button("Войти", type="primary")
    if submitted:
        if db.check_credentials(login, password):
            st.session_state.user = login
            st.rerun()
        st.error("Неверный логин или пароль.")


def _grnti_parts(value):
    """Разбивает строку ГРНТИ на коды, а коды — на пары цифр."""
    codes = []
    for code in db.split_grnti(value)[:2]:
        parts = [p for p in code.replace(",", ".").split(".") if p]
        codes.append((parts + ["", "", ""])[:3])
    return codes


def grnti_input(prefix, initial):
    """Ввод кода ГРНТИ по группам цифр ХХ.ХХ.ХХ; до двух кодов."""
    rubrics = db.get_rubrics()
    rub_codes = [f"{int(c):02d}" for c in rubrics["Код"]]
    rub_names = dict(zip(rub_codes, rubrics["Наименование рубрики"]))
    initial = _grnti_parts(initial)

    st.markdown("**Код ГРНТИ** — рубрика, подрубрика и раздел по две цифры")
    use_second = st.checkbox(
        "Второй код ГРНТИ", value=len(initial) > 1, key=f"{prefix}_two"
    )
    codes = []
    for n in range(2 if use_second else 1):
        p1, p2, p3 = initial[n] if n < len(initial) else ("", "", "")
        c1, c2, c3 = st.columns([3, 1, 1])
        rubric = c1.selectbox(
            f"Рубрика {n + 1}",
            rub_codes,
            index=rub_codes.index(p1) if p1 in rub_codes else None,
            format_func=lambda c: f"{c} — {rub_names[c]}",
            placeholder="ХХ",
            key=f"{prefix}_r{n}",
        )
        sub = c2.text_input(
            "Подрубрика", p2, max_chars=2, placeholder="ХХ", key=f"{prefix}_s{n}"
        )
        sec = c3.text_input(
            "Раздел", p3, max_chars=2, placeholder="ХХ", key=f"{prefix}_c{n}"
        )
        if rubric is None and not sub and not sec:
            continue
        codes.append(".".join(p for p in (rubric or "", sub.strip(), sec.strip()) if p))
    return ", ".join(codes)


@st.dialog("Запись НИР", width="large")
def record_dialog(record=None):
    """Добавление (record=None) или редактирование записи — одна и та же форма."""
    record = record or {}
    p = f"rec{st.session_state.dialog_n}"
    st.subheader("Редактирование записи" if record else "Новая запись")

    vuz = db.get_vuz_list()
    vuz_codes = vuz["Код"].tolist()
    vuz_names = dict(
        zip(vuz["Код"], vuz["Сокращенное наименование"] + " (" + vuz["Город"] + ")")
    )
    c1, c2, c3 = st.columns([3, 1, 1])
    vuz_code = c1.selectbox(
        "Вуз (код)",
        vuz_codes,
        index=(
            vuz_codes.index(record[db.F_VUZ])
            if record.get(db.F_VUZ) in vuz_codes
            else None
        ),
        format_func=lambda c: f"{c} — {vuz_names[c]}",
        placeholder="Выберите вуз",
        key=f"{p}_vuz",
    )
    types = list(db.NIR_TYPES)
    nir_type = c2.radio(
        "Форма НИР",
        types,
        index=types.index(record[db.F_TYPE]) if record.get(db.F_TYPE) in types else 0,
        format_func=db.NIR_TYPES.get,
        key=f"{p}_type",
    )
    reg = c3.text_input("Рег. №", record.get(db.F_REG) or "", key=f"{p}_reg")

    subject = st.text_area(
        "Наименование проекта/НИР", record.get(db.F_SUBJECT) or "", key=f"{p}_subj"
    )
    grnti = grnti_input(p, record.get(db.F_GRNTI))

    c1, c2 = st.columns(2)
    boss = c1.text_input("Руководитель", record.get(db.F_BOSS) or "", key=f"{p}_boss")
    boss_title = c2.text_input(
        "Должность руководителя", record.get(db.F_BOSS_TITLE) or "", key=f"{p}_title"
    )

    ex_types = list(db.EXHIBIT_TYPES)
    exhibit = st.radio(
        "Наличие экспоната",
        ex_types,
        index=(
            ex_types.index(record[db.F_EXHIBIT])
            if record.get(db.F_EXHIBIT) in ex_types
            else 0
        ),
        format_func=lambda e: f"{e} — {db.EXHIBIT_TYPES[e]}",
        horizontal=True,
        key=f"{p}_ex",
    )
    vystavki = st.text_area(
        "Информация о выставке", record.get(db.F_VYSTAVKI) or "", key=f"{p}_vyst"
    )
    exponat = st.text_input(
        "Название выставочного экспоната", record.get(db.F_EXPONAT) or "", key=f"{p}_expo"
    )

    new = {
        db.F_VUZ: vuz_code,
        db.F_TYPE: nir_type,
        db.F_REG: reg,
        db.F_SUBJECT: subject,
        db.F_GRNTI: grnti,
        db.F_BOSS: boss,
        db.F_BOSS_TITLE: boss_title,
        db.F_EXHIBIT: exhibit,
        db.F_VYSTAVKI: vystavki,
        db.F_EXPONAT: exponat,
    }
    st.caption(f"Код ГРНТИ будет сохранён как: {grnti or '—'}")
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Сохранить", type="primary"):
        try:
            if record:
                db.update_record(record["id"], new)
                st.session_state.select_id = record["id"]
            else:
                st.session_state.select_id = db.add_record(new)
        except ValueError as e:
            for msg in str(e).splitlines():
                st.error(msg)
        else:
            st.rerun()
    if c2.button("Отмена"):
        st.rerun()


@st.dialog("Удаление записи")
def delete_dialog(record):
    st.write(
        f"Удалить НИР **{record[db.F_VUZ]} / {record[db.F_TYPE]} / {record[db.F_REG]}** "
        f"({record[db.F_VUZ_NAME]})?"
    )
    st.caption(record[db.F_SUBJECT])
    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Удалить", type="primary"):
        db.delete_record(record["id"])
        st.session_state.select_id = None
        st.rerun()
    if c2.button("Отмена"):
        st.rerun()


@st.dialog("Фильтр", width="large")
def filter_dialog():
    flt = st.session_state.filters
    geo = db.get_geography()
    p = f"flt{st.session_state.dialog_n}"

    st.markdown("**География вуза**")
    regions = st.multiselect(
        "Федеральный округ",
        sorted(geo["Федеральный округ"].unique()),
        flt.get("regions", []),
        placeholder="Все",
        key=f"{p}_reg",
    )
    if regions:
        geo = geo[geo["Федеральный округ"].isin(regions)]
    subjects = st.multiselect(
        "Субъект РФ",
        sorted(geo["Субъект РФ"].unique()),
        [s for s in flt.get("subjects", []) if s in set(geo["Субъект РФ"])],
        placeholder="Все",
        key=f"{p}_subj",
    )
    if subjects:
        geo = geo[geo["Субъект РФ"].isin(subjects)]
    cities = st.multiselect(
        "Город",
        sorted(geo["Город"].unique()),
        [c for c in flt.get("cities", []) if c in set(geo["Город"])],
        placeholder="Все",
        key=f"{p}_city",
    )

    st.markdown("**ГРНТИ**")
    rubrics = db.get_rubrics()
    rub_names = dict(zip(rubrics["Код"], rubrics["Наименование рубрики"]))
    c1, c2 = st.columns([3, 1])
    sel_rubrics = c1.multiselect(
        "Рубрика",
        rubrics["Код"].tolist(),
        flt.get("rubrics", []),
        format_func=lambda c: f"{int(c):02d} — {rub_names[c]}",
        placeholder="Все",
        key=f"{p}_rub",
    )
    grnti = c2.text_input(
        "Код (начало)", flt.get("grnti", ""), placeholder="27.35", key=f"{p}_code"
    )

    st.markdown("**Степень готовности экспоната**")
    exhibit = st.multiselect(
        "Экспонат",
        list(db.EXHIBIT_TYPES),
        flt.get("exhibit", []),
        format_func=db.EXHIBIT_TYPES.get,
        placeholder="Все",
        key=f"{p}_ex",
    )

    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("Применить", type="primary"):
        st.session_state.filters = {
            k: v
            for k, v in {
                "regions": regions,
                "subjects": subjects,
                "cities": cities,
                "rubrics": sel_rubrics,
                "grnti": grnti.strip(),
                "exhibit": exhibit,
            }.items()
            if v
        }
        st.rerun()
    if c2.button("Сбросить"):
        st.session_state.filters = {}
        st.rerun()


@st.dialog("Добавить в группу НИР")
def to_group_dialog(selected_ids, filtered_ids):
    p = f"grp{st.session_state.dialog_n}"
    scope = st.radio(
        "Какие записи добавить",
        ["selected", "filtered"],
        format_func=lambda s: (
            f"Выделенные ({len(selected_ids)})"
            if s == "selected"
            else f"Все отобранные фильтром ({len(filtered_ids)})"
        ),
        index=0 if selected_ids else 1,
        key=f"{p}_scope",
    )
    groups = db.get_groups()
    options = ["__new__"] + groups["id"].tolist()
    names = dict(zip(groups["id"], groups["name"]))
    target = st.selectbox(
        "Группа",
        options,
        format_func=lambda g: "Новая группа…" if g == "__new__" else names[g],
        key=f"{p}_target",
    )
    name = (
        st.text_input("Название новой группы", key=f"{p}_name")
        if target == "__new__"
        else None
    )
    filter_desc = db.describe_filter(st.session_state.filters)
    if target == "__new__":
        st.caption(f"Условия фильтрации сохранятся в группе: {filter_desc}")

    ids = selected_ids if scope == "selected" else filtered_ids
    if st.button("Добавить", type="primary", disabled=not ids):
        try:
            group_id = (
                db.create_group(name, filter_desc) if target == "__new__" else target
            )
            db.add_to_group(group_id, ids)
        except ValueError as e:
            st.error(str(e))
        else:
            st.session_state.group_id = group_id
            st.toast(f"Добавлено записей: {len(ids)}")
            st.rerun()


@st.dialog("Карточка НИР", width="large")
def card_dialog(record):
    st.html(nir_card_app(record))
    st.download_button(
        "Скачать карточку",
        nir_card(record),
        file_name=f"НИР_{record[db.F_VUZ]}_{record[db.F_TYPE]}_{record[db.F_REG]}.html",
        mime="text/html",
    )


def open_dialog(fn, *args):
    st.session_state.dialog_n += 1
    fn(*args)


# ---------- Меню ----------

menu, _, auth = st.columns([2, 5, 2], vertical_alignment="center")
with menu:
    b1, b2 = st.columns(2)
    for col, page in ((b1, "Данные"), (b2, "Группы")):
        if col.button(
            page,
            type="primary" if st.session_state.page == page else "secondary",
            use_container_width=True,
        ):
            st.session_state.page = page
            st.rerun()
with auth:
    if logged_in():
        a1, a2 = st.columns([2, 1], vertical_alignment="center")
        a1.caption(f"Пользователь: **{st.session_state.user}**")
        if a2.button("Выйти"):
            st.session_state.user = None
            st.rerun()
    elif st.button(
        "Войти", use_container_width=True, help="Вход нужен для изменения данных"
    ):
        login_dialog()

LOGIN_HELP = "Для изменения данных выполните вход"


# ---------- Страница «Данные» ----------


def data_page():
    table = st.session_state.get("selected_table", DATA_TABLES[0]).lower()
    df = db.get_data(table)
    scroll_to = None
    is_nir = table == "vyst_mo"

    if is_nir:
        df = db.apply_filter(df, st.session_state.filters)
        if st.session_state.sort_desc:
            df = db.sort_by_key(df, ascending=False)

        # при смене фильтра или сортировки старое выделение указывает не на те строки
        view = repr((st.session_state.filters, st.session_state.sort_desc))
        if st.session_state.get("table_view") != view:
            st.session_state.table_view = view
            st.session_state[TABLE_KEY] = {
                "selection": {"rows": [], "columns": [], "cells": []}
            }

        # курсор на добавленную/изменённую запись
        if st.session_state.select_id is not None:
            pos = df.index[df["id"] == st.session_state.select_id].tolist()
            if pos:
                scroll_to = df.index.get_loc(pos[0])
                st.session_state[TABLE_KEY] = {
                    "selection": {"rows": [scroll_to], "columns": [], "cells": []}
                }
            else:
                st.toast("Запись сохранена, но не попадает под текущий фильтр.")
            st.session_state.select_id = None

    st.markdown(f"##### {table.upper()} — {len(df)} записей")
    if is_nir and st.session_state.filters:
        st.caption(f"Фильтр: {db.describe_filter(st.session_state.filters)}")

    event = st.dataframe(
        display_frame(df, table),
        hide_index=True,
        height=460,
        row_height=ROW_HEIGHT,
        column_config=column_config(table),
        column_order=db.COLUMN_ORDER[table],
        key=TABLE_KEY if is_nir else f"table_{table}",
        on_select="rerun" if is_nir else "ignore",
        selection_mode="multi-row",
    )
    if scroll_to is not None:
        scroll_table_to(scroll_to)

    # всё управление — под таблицей
    st.pills(
        "Таблица",
        options=DATA_TABLES,
        default=DATA_TABLES[0],
        selection_mode="single",
        key="selected_table",
        required=True,
    )
    if not is_nir:
        st.caption("Справочник только для просмотра.")
        return

    rows = [r for r in (event.selection.rows if event else []) if r < len(df)]
    selected = df.iloc[rows] if rows else df.iloc[0:0]
    one = selected.iloc[0].to_dict() if len(selected) == 1 else None

    st.radio(
        "Сортировка по составному ключу (код вуза + форма + рег. №)",
        [False, True],
        format_func=lambda d: "по убыванию" if d else "по возрастанию",
        horizontal=True,
        key="sort_desc",
    )

    can_edit = logged_in()
    cols = st.columns(7)
    if cols[0].button("Фильтр", use_container_width=True):
        open_dialog(filter_dialog)
    if cols[1].button(
        "Сбросить фильтр", use_container_width=True, disabled=not st.session_state.filters
    ):
        st.session_state.filters = {}
        st.rerun()
    if cols[2].button(
        "Добавить запись",
        use_container_width=True,
        disabled=not can_edit,
        help=None if can_edit else LOGIN_HELP,
    ):
        open_dialog(record_dialog)
    if cols[3].button(
        "Изменить",
        use_container_width=True,
        disabled=not (can_edit and one),
        help=LOGIN_HELP if not can_edit else "Выделите одну строку",
    ):
        open_dialog(record_dialog, one)
    if cols[4].button(
        "Удалить запись",
        use_container_width=True,
        disabled=not (can_edit and one),
        help=LOGIN_HELP if not can_edit else "Выделите одну строку",
    ):
        open_dialog(delete_dialog, one)
    if cols[5].button(
        "В группу НИР",
        use_container_width=True,
        disabled=not can_edit,
        help=None if can_edit else LOGIN_HELP,
    ):
        open_dialog(to_group_dialog, selected["id"].tolist(), df["id"].tolist())
    if cols[6].button(
        "Карточка НИР",
        use_container_width=True,
        disabled=not one,
        help="Выделите одну строку",
    ):
        open_dialog(card_dialog, one)


# ---------- Страница «Группы» ----------


def groups_page():
    groups = db.get_groups()
    if groups.empty:
        st.info(
            "Групп НИР пока нет. Отберите записи на странице «Данные» и нажмите «В группу НИР»."
        )
        return

    ids = groups["id"].tolist()
    if st.session_state.get("group_id") not in ids:
        st.session_state.group_id = ids[0]
    group = groups.set_index("id").loc[st.session_state.group_id]
    items = db.get_group_items(st.session_state.group_id)

    st.markdown(
        f"##### Группа «{group['name']}» — {len(items)} НИР, в выставку: {int(group['n_included'])}"
    )
    st.caption(
        f"Условия отбора: {group['filter_desc'] or 'без фильтра'} · создана {group['created']}"
    )

    view = display_frame(items, "vyst_mo")
    view.insert(0, "remove", False)
    cfg = column_config("vyst_mo")
    cfg["included"] = st.column_config.CheckboxColumn(
        "В выставку", help="НИР включена в группу экспонентов выставки"
    )
    cfg["remove"] = st.column_config.CheckboxColumn("Убрать", help="Убрать НИР из группы")
    can_edit = logged_in()
    edited = st.data_editor(
        view,
        hide_index=True,
        height=min(460, (len(view) + 1) * ROW_HEIGHT + 3),
        row_height=ROW_HEIGHT,
        column_config=cfg,
        column_order=["included", "remove", *db.COLUMN_ORDER["vyst_mo"]],
        disabled=(
            [c for c in view.columns if c not in ("included", "remove")]
            if can_edit
            else True
        ),
        key=f"group_editor_{st.session_state.group_id}",
    )

    # управление — под таблицей
    st.selectbox(
        "Группа НИР",
        ids,
        format_func=dict(
            zip(groups["id"], groups["name"] + " (" + groups["n"].astype(str) + ")")
        ).get,
        key="group_id",
    )
    cols = st.columns(5)
    if cols[0].button(
        "Сохранить отметки",
        use_container_width=True,
        disabled=not can_edit,
        help=None if can_edit else LOGIN_HELP,
    ):
        db.save_group_marks(
            st.session_state.group_id, dict(zip(edited["id"], edited["included"]))
        )
        removed = edited.loc[edited["remove"], "id"].tolist()
        if removed:
            db.remove_from_group(st.session_state.group_id, removed)
        st.toast("Изменения группы сохранены")
        st.rerun()
    cols[1].download_button(
        "Список группы",
        group_document(group["name"], group["filter_desc"], items),
        file_name=f"Группа НИР {group['name']}.html",
        mime="text/html",
        use_container_width=True,
    )
    cols[2].download_button(
        "Список (CSV)",
        items.drop(columns=["id"]).to_csv(index=False).encode("utf-8-sig"),
        file_name=f"Группа НИР {group['name']}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    if cols[3].button(
        "Удалить группу",
        use_container_width=True,
        disabled=not can_edit,
        help=None if can_edit else LOGIN_HELP,
    ):
        db.delete_group(st.session_state.group_id)
        st.rerun()


if st.session_state.page == "Данные":
    data_page()
else:
    groups_page()
