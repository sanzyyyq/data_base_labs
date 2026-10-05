from datetime import date

import streamlit as st

from backend import backend as db

st.set_page_config(layout="wide", page_title="Выставочные экспонаты")
if not db.DB_PATH.exists():
    st.error("База данных не найдена. Создайте её: python backend/convert.py")
    st.stop()
st.session_state.setdefault("filters", {})
st.session_state.setdefault("page", "Данные")
ROW_HEIGHT = 35


def show(df, table, **kwargs):
    labels = db.LABELS[table]
    return st.dataframe(
        df,
        hide_index=True,
        column_order=list(labels),
        column_config={c: st.column_config.Column(l) for c, l in labels.items()},
        **kwargs,
    )


@st.dialog("Запись НИР", width="large")
def record_dialog(rec=None):
    rec = rec or {}
    vuz = db.get_table("vuz")
    codes = vuz["codvuz"].tolist()
    names = dict(zip(vuz["codvuz"], vuz["shortname"]))
    cur_vuz = int(rec["codvuz"]) if rec.get("codvuz") else None
    new = {
        "codvuz": st.selectbox(
            "Вуз",
            codes,
            codes.index(cur_vuz) if cur_vuz in codes else None,
            format_func=lambda c: f"{c} — {names[c]}",
        ),
        "type": st.radio(
            "Форма НИР",
            db.NIR_TYPES,
            db.NIR_TYPES.index(rec.get("type", "Е")),
            horizontal=True,
        ),
        "regnumber": st.text_input("Рег. №", rec.get("regnumber") or ""),
        "subject": st.text_area("Наименование НИР", rec.get("subject") or ""),
        "grnti": st.text_input(
            "Код ГРНТИ (ХХ.ХХ.ХХ, через запятую)", rec.get("grnti") or ""
        ),
        "bossname": st.text_input("Руководитель", rec.get("bossname") or ""),
        "bosstitle": st.text_input("Должность", rec.get("bosstitle") or ""),
        "exhitype": st.radio(
            "Экспонат",
            list(db.EXHIBIT_TYPES),
            list(db.EXHIBIT_TYPES).index(rec.get("exhitype") or "Н"),
            format_func=db.EXHIBIT_TYPES.get,
            horizontal=True,
        ),
        "vystavki": st.text_area("Информация о выставке", rec.get("vystavki") or ""),
        "exponat": st.text_input("Название экспоната", rec.get("exponat") or ""),
    }
    if st.button("Сохранить", type="primary"):
        errors, rec_id = db.save_record(new, rec.get("id"))
        for e in errors:
            st.error(e)
        if not errors:
            st.session_state.select_id = rec_id  # курсор на добавленную/изменённую запись
            st.rerun()


def suggest_group_name(flt, picked, existing):
    """Название новой группы по условиям фильтра и дате, например «Владивосток, экспонат есть 05.10.2026»."""
    parts = [v for f in ("region", "oblname", "city") for v in flt.get(f, [])][:3]
    if flt.get("grnti"):
        parts.append(f"ГРНТИ {flt['grnti']}")
    if flt.get("exhitype"):
        parts.append(
            "экспонат " + ", ".join(db.EXHIBIT_TYPES[e] for e in flt["exhitype"])
        )
    base = f"{'Выбранные НИР' if picked else ', '.join(parts) or 'Все НИР'} {date.today():%d.%m.%Y}"
    name, n = base, 1
    while name in existing:
        n += 1
        name = f"{base} ({n})"
    return name


@st.dialog("Сохранить в группу НИР")
def group_dialog(ids, flt, picked):
    filter_desc = db.describe_filter(flt)
    existing = db.get_groups()["name"].tolist()
    suggested = suggest_group_name(flt, picked, existing)
    name = st.selectbox(
        "Группа (выберите или введите новую)",
        [suggested, *existing],
        index=0,
        format_func=lambda g: f"{g} (новая)" if g == suggested else g,
        accept_new_options=True,
        placeholder="Название группы",
    )
    st.caption(f"Записей: {len(ids)}. Условия отбора: {filter_desc}")
    if st.button("Сохранить", type="primary", disabled=not name):
        db.add_to_group(name.strip(), filter_desc, ids)
        st.toast("Сохранено")
        st.rerun()


@st.dialog("Фильтр")
def filter_dialog():
    flt = st.session_state.filters
    geo_fields = ("region", "oblname", "city")
    geo = db.get_table("vuz")[list(geo_fields)].dropna()
    p = f"flt{st.session_state.flt_n}"  # новые ключи при каждом открытии формы
    sel = {f: st.session_state.get(f"{p}_{f}", flt.get(f, [])) for f in geo_fields}
    new = {}
    for f in geo_fields:
        # варианты поля ограничены значениями, выбранными в двух других полях
        rows = geo
        for g in geo_fields:
            if g != f and sel[g]:
                rows = rows[rows[g].isin(sel[g])]
        options = sorted(rows[f].unique())
        new[f] = st.multiselect(
            db.LABELS["vuz"][f],
            options,
            [v for v in sel[f] if v in options],
            placeholder="Все",
            key=f"{p}_{f}",
        )
    new["grnti"] = st.text_input("Код ГРНТИ начинается с", flt.get("grnti", "")).strip()
    new["exhitype"] = st.multiselect(
        "Экспонат",
        list(db.EXHIBIT_TYPES),
        flt.get("exhitype", []),
        format_func=db.EXHIBIT_TYPES.get,
        placeholder="Все",
    )
    if st.button("Применить", type="primary"):
        st.session_state.filters = {k: v for k, v in new.items() if v}
        st.rerun()


def table_key():
    """Ключ таблицы НИР. Смена ключа пересоздаёт таблицу и сбрасывает выделение."""
    return f"nir_table_{st.session_state.get('table_n', 0)}"


def reset_selection():
    st.session_state.table_n = st.session_state.get("table_n", 0) + 1


def scroll_to_row(row):
    """Плавно прокручивает таблицу НИР к строке row. Вызывается в самом конце страницы:
    элемент со скриптом выше таблицы сдвигал бы её, и страница дёргалась бы."""
    st.session_state.scroll_n = (
        st.session_state.get("scroll_n", 0) + 1
    )  # чтобы скрипт выполнился заново
    st.html(
        f"""<script>/* {st.session_state.scroll_n} */
        (() => {{
          let tries = 0;
          const timer = setInterval(() => {{
            const sc = document.querySelector(".st-key-{table_key()} .dvn-scroller");
            if (sc && sc.scrollHeight > sc.clientHeight) {{
              sc.scrollTo({{
                top: Math.max(0, ({row} + 1) * {ROW_HEIGHT} - sc.clientHeight / 2),
                behavior: "smooth",
              }});
              clearInterval(timer);
            }}
            if (++tries > 50) clearInterval(timer);
          }}, 100);
        }})();
        </script>""",
        unsafe_allow_javascript=True,
    )


def table_choice():
    st.radio("Таблица", ["vyst_mo", "vuz", "grntirub"], horizontal=True, key="table")


def data_page():
    table = st.session_state.get("table", "vyst_mo")
    df = db.get_table(table)
    if table != "vyst_mo":
        show(df, table)
        table_choice()
        return

    flt = st.session_state.filters
    df = db.apply_filter(df, flt)
    sort = st.session_state.get("sort", "по возрастанию")
    if sort != "без сортировки":
        df = db.sort_by_key(df, ascending=sort == "по возрастанию")
    df = df.reset_index(drop=True)

    # при смене фильтра или сортировки старое выделение указывает не на те строки
    view = repr((flt, sort))
    if st.session_state.get("view") != view:
        st.session_state.view = view
        reset_selection()
    scroll_row = None
    select_id = st.session_state.pop("select_id", None)
    if select_id is not None:
        rows = df.index[df["id"] == select_id]
        if len(rows):
            scroll_row = int(rows[0])
            st.session_state[table_key()] = {
                "selection": {"rows": [scroll_row], "columns": [], "cells": []}
            }
        else:
            st.toast("Запись сохранена, но не попадает под текущий фильтр")

    st.caption(
        f"Записей: {len(df)}" + (f". Фильтр: {db.describe_filter(flt)}" if flt else "")
    )
    event = show(
        df,
        table,
        key=table_key(),
        on_select="rerun",
        selection_mode="multi-row",
        height=460,
        row_height=ROW_HEIGHT,
    )
    table_choice()
    st.radio(
        "Сортировка по ключу (код вуза + форма + рег. №)",
        ["без сортировки", "по возрастанию", "по убыванию"],
        index=1,
        horizontal=True,
        key="sort",
    )
    selected = df.iloc[[r for r in event.selection.rows if r < len(df)]]
    one = selected.iloc[0].to_dict() if len(selected) == 1 else None

    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Фильтр", width="stretch"):
        st.session_state.flt_n = st.session_state.get("flt_n", 0) + 1
        filter_dialog()
    if c.button("Сбросить фильтр", width="stretch"):
        st.session_state.filters = {}
        st.rerun()
    if c.button("Добавить", width="stretch"):
        record_dialog()
    if c.button("Изменить", disabled=not one, width="stretch"):
        record_dialog(one)
    if c.button("Удалить", disabled=not one, width="stretch"):
        db.execute("DELETE FROM vyst_mo WHERE id = ?", (one["id"],))
        reset_selection()  # иначе выделение перейдёт на следующую строку
        st.rerun()
    if c.button("В группу НИР", width="stretch"):
        group_dialog(
            (selected if len(selected) else df)["id"].tolist(), flt, len(selected) > 0
        )

    if scroll_row is not None:
        scroll_to_row(scroll_row)


def groups_page():
    groups = db.get_groups()
    if groups.empty:
        st.info("Групп пока нет")
        return
    gid = st.selectbox(
        "Группа", groups["id"], format_func=dict(zip(groups["id"], groups["name"])).get
    )
    group = groups.set_index("id").loc[gid]
    st.caption(f"Условия отбора: {group['filter_desc']}")
    items = db.get_group_items(gid)
    edited = st.data_editor(
        items,
        hide_index=True,
        key=f"group_{gid}",
        column_order=["included", *db.LABELS["vyst_mo"]],
        column_config={
            "included": st.column_config.CheckboxColumn("В выставку"),
            **{c: st.column_config.Column(l) for c, l in db.LABELS["vyst_mo"].items()},
        },
        disabled=list(db.LABELS["vyst_mo"]),
    )
    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Сохранить отметки", width="stretch"):
        db.save_marks(gid, dict(zip(edited["id"], edited["included"])))
        st.toast("Сохранено")
    c.download_button(
        "Список группы (CSV)",
        edited.rename(columns=db.LABELS["vyst_mo"])
        .drop(columns="id")
        .to_csv(index=False)
        .encode("utf-8-sig"),
        file_name=f"Группа {group['name']}.csv",
        width="stretch",
    )
    if c.button("Удалить группу", width="stretch"):
        db.execute("DELETE FROM nir_groups WHERE id = ?", (gid,))
        st.rerun()


menu, _ = st.columns([2, 7])
for col, page in zip(menu.columns(2), ["Данные", "Группы"]):
    if col.button(
        page,
        type="primary" if st.session_state.page == page else "secondary",
        use_container_width=True,
    ):
        st.session_state.page = page
        st.rerun()
if st.session_state.page == "Данные":
    data_page()
else:
    groups_page()
