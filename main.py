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


def column_config(table):
    # длинные текстовые столбцы шире остальных (ширина в пикселях): наименование НИР
    # в среднем ~120 символов, название экспоната ~65; информация о выставке —
    # по самой длинной записи (196 символов), чтобы все записи помещались целиком
    widths = {"subject": 800, "exponat": 600, "vystavki": 1380}
    return {
        c: st.column_config.Column(l, width=widths.get(c))
        for c, l in db.LABELS[table].items()
    }


GRNTI_LABEL = "Код ГРНТИ (только цифры)"


def grnti_mask():
    """Маска ввода ГРНТИ: точки (ХХ.ХХ.ХХ) и разделитель кодов «; » ставятся сами.
    Скрипт ставит обработчики на документ (новая версия скрипта снимает старые),
    поле находит по контейнеру rec_grnti в форме записи.
    Здесь же стили страницы: без лишнего отступа снизу, а элементы со скриптами
    (этот и прокрутка таблицы) скрыты, чтобы не занимали места."""
    st.html(
        f"""<style>
        [data-testid="stMainBlockContainer"] {{ padding-bottom: 1rem; }}
        [data-testid="stElementContainer"]:has(> [data-testid="stHtml"] > script) {{ display: none; }}
        </style>
        <script>
        (() => {{
          if (window.grntiMaskOff) window.grntiMaskOff();
          const MAX_CODES = 3;  // в исходных данных бывает до трёх кодов
          const format = (value, max, deleting) => {{
            const codes = [];
            for (const part of value.split(/[,;]/)) {{
              let d = part.replace(/\\D/g, "");
              while (d.length > 6) {{ codes.push(d.slice(0, 6)); d = d.slice(6); }}
              codes.push(d);
            }}
            // при стирании пустой последний код убирается вместе с разделителем «; »
            if (deleting) while (codes.length > 1 && !codes[codes.length - 1]) codes.pop();
            return codes.slice(0, max)
              .map(d => (d.match(/.{{1,2}}/g) || []).join("."))
              .join("; ");
          }};
          const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
          const isMasked = el => el.tagName === "INPUT" && el.closest(".st-key-rec_grnti");
          // значение до ввода: по нему видно, что стёрт только разделитель
          const onFocus = e => {{
            if (isMasked(e.target)) e.target.dataset.prev = e.target.value;
          }};
          const onInput = e => {{
            const el = e.target;
            if (!isMasked(el)) return;
            const max = MAX_CODES;
            const deleting = (e.inputType || "").startsWith("delete");
            let value = el.value, caret = el.selectionStart;
            const prev = el.dataset.prev || "";
            const digitsOf = v => v.replace(/\\D/g, "");
            // стёрт только разделитель (точка или «; ») — стираем и соседнюю цифру,
            // иначе маска сразу вернёт разделитель и курсор застрянет
            if (deleting && value !== prev && digitsOf(value) === digitsOf(prev)) {{
              const back = e.inputType === "deleteContentBackward";
              let i = back ? caret - 1 : caret;
              while (i >= 0 && i < value.length && !/\\d/.test(value[i])) i += back ? -1 : 1;
              if (i >= 0 && i < value.length) {{
                value = value.slice(0, i) + value.slice(i + 1);
                if (back) caret = i;
              }}
            }}
            const formatted = format(value, max, deleting);
            el.dataset.prev = formatted;
            if (formatted === el.value) return;
            // курсор остаётся после того же количества цифр
            const digits = digitsOf(value.slice(0, caret)).length;
            let pos = 0;
            for (let n = 0; pos < formatted.length && n < digits; pos++)
              if (/\\d/.test(formatted[pos])) n++;
            setValue.call(el, formatted);
            el.setSelectionRange(pos, pos);
            el.dispatchEvent(new Event("input", {{ bubbles: true }}));
          }};
          document.addEventListener("focusin", onFocus, true);
          document.addEventListener("input", onInput, true);
          window.grntiMaskOff = () => {{
            document.removeEventListener("focusin", onFocus, true);
            document.removeEventListener("input", onInput, true);
          }};
        }})();
        </script>""",
        unsafe_allow_javascript=True,
    )


def show(df, table, **kwargs):
    labels = db.LABELS[table]
    return st.dataframe(
        df.fillna(""),  # пустые значения — пустыми ячейками, а не «None»
        hide_index=True,
        column_order=list(labels),
        column_config=column_config(table),
        **kwargs,
    )


@st.dialog("Запись НИР", width="large")
def record_dialog(rec=None):
    rec = rec or {}
    vuz = db.get_table("vuz")
    codes = vuz["codvuz"].tolist()
    names = dict(zip(vuz["codvuz"], vuz["shortname"]))
    cur_vuz = int(rec["codvuz"]) if rec.get("codvuz") else None

    def field(col, name):
        # контейнер с ключом: по нему поле подсвечивается, если в нём ошибка
        return col.container(key=f"rec_{name}")

    # короткие поля по нескольку в ряд, чтобы форма помещалась на экране
    c1, c2, c3 = st.columns([3, 1, 1])
    new = {
        "codvuz": field(c1, "codvuz").selectbox(
            "Вуз",
            codes,
            codes.index(cur_vuz) if cur_vuz in codes else None,
            format_func=lambda c: f"{c} — {names[c]}",
            placeholder="Выберите вуз",
        ),
        "type": field(c2, "type").radio(
            "Форма НИР",
            db.NIR_TYPES,
            db.NIR_TYPES.index(rec.get("type", "Е")),
            horizontal=True,
        ),
        "regnumber": field(c3, "regnumber").text_input(
            "Рег. №", rec.get("regnumber") or ""
        ),
        "subject": field(st, "subject").text_area(
            "Наименование НИР", rec.get("subject") or "", height=68
        ),
    }
    c1, c2, c3 = st.columns([2, 2, 1])
    new["grnti"] = field(c1, "grnti").text_input(
        GRNTI_LABEL, rec.get("grnti") or "", placeholder="ХХ.ХХ.ХХ; ХХ.ХХ.ХХ"
    )
    new["bossname"] = field(c2, "bossname").text_input(
        "Руководитель", rec.get("bossname") or ""
    )
    new["bosstitle"] = field(c3, "bosstitle").text_input(
        "Должность", rec.get("bosstitle") or ""
    )
    new["exhitype"] = field(st, "exhitype").radio(
        "Экспонат",
        list(db.EXHIBIT_TYPES),
        list(db.EXHIBIT_TYPES).index(rec.get("exhitype") or "Н"),
        format_func=db.EXHIBIT_TYPES.get,
        horizontal=True,
    )
    # если экспоната нет, поля сведений о нём скрыты (прежние значения записи сохраняются);
    # если есть — оба поля обязательны
    new["vystavki"], new["exponat"] = rec.get("vystavki"), rec.get("exponat")
    if new["exhitype"] != "Н":
        required = " *" if new["exhitype"] == "Е" else ""
        c1, c2 = st.columns(2)
        new["vystavki"] = field(c1, "vystavki").text_area(
            "Информация о выставке" + required, rec.get("vystavki") or "", height=68
        )
        new["exponat"] = field(c2, "exponat").text_area(
            "Название экспоната" + required, rec.get("exponat") or "", height=68
        )
    button, message = st.columns([1, 5], vertical_alignment="center")
    if button.button("Сохранить", type="primary"):
        errors, rec_id = db.save_record(new, rec.get("id"))
        if errors:
            # одной плашкой справа от кнопки, чтобы форма не росла вниз
            # о пустых полях — одной строкой (сами поля подсвечены), остальные ошибки списком
            empty = [msg for fields, msg in errors if not new.get(fields[-1])]
            lines = [msg for fields, msg in errors if new.get(fields[-1])]
            lines += ["Заполните выделенные поля"] if empty else []
            message.error("\n".join(f"- {line}" for line in lines))
            # подсветка полей с ошибками
            keys = {f".st-key-rec_{f}" for fields, _ in errors for f in fields}
            message.html(
                "<style>"
                + ", ".join(
                    f"{k} [data-testid=stTextInputRootElement], "
                    f"{k} [data-testid=stTextAreaRootElement], "
                    f"{k} [data-testid=stSelectbox] > div:has(input) > div"
                    for k in keys
                )
                + " { box-shadow: inset 0 0 0 1px #ff4b4b;"
                " background-color: rgba(255, 75, 75, 0.12) !important; }</style>"
            )
        else:
            st.session_state.select_id = rec_id  # курсор на добавленную/изменённую запись
            st.rerun()


def suggest_group_name(flt, picked, existing):
    """Название новой группы по условиям фильтра и дате, например «Владивосток, экспонат есть 05.10.2026»."""
    names = db.vuz_names()
    parts = [v for f in ("region", "oblname", "city") for v in flt.get(f, [])]
    parts = (parts + [names[v] for v in flt.get("codvuz", [])])[:3]
    if flt.get("rubrics"):
        parts.append("ГРНТИ " + ", ".join(f"{r:02d}" for r in flt["rubrics"]))
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
    vuz = db.get_table("vuz")
    geo = vuz[list(db.GEO_FIELDS)].dropna()
    # НИР с географией вуза: по строке на каждую рубрику записи
    nir = db.get_table("vyst_mo")[["codvuz", "grnti", "exhitype"]]
    nir = nir.assign(rubrics=nir["grnti"].apply(lambda v: sorted(db.record_rubrics(v))))
    nir = nir.explode("rubrics").merge(geo, on="codvuz")
    nir_fields = ("rubrics", "exhitype")  # поля, которые есть только у НИР
    fields = (*db.GEO_FIELDS, *nir_fields)

    vuz_names, rubrics = db.vuz_names(), db.rubric_names()
    labels = {
        **db.LABELS["vuz"],
        "codvuz": "Вуз",
        "rubrics": "Рубрика ГРНТИ",
        "exhitype": "Экспонат",
    }
    formats = {
        "codvuz": lambda c: f"{c} — {vuz_names[c]}",
        "rubrics": rubrics.get,
        "exhitype": db.EXHIBIT_TYPES.get,
    }
    p = f"flt{st.session_state.flt_n}"  # новые ключи при каждом открытии формы
    sel = {f: st.session_state.get(f"{p}_{f}", flt.get(f, [])) for f in fields}
    new = {}
    for f in fields:
        # варианты поля ограничены значениями, выбранными в остальных полях;
        # пока рубрика и экспонат не выбраны, география берётся из всего справочника вузов
        by_nir = f in nir_fields or any(sel[g] for g in nir_fields)
        rows = nir if by_nir else geo
        for g in fields:
            if g != f and sel[g]:
                rows = rows[rows[g].isin(sel[g])]
        present = set(rows[f].dropna())
        if f == "exhitype":
            options = [e for e in db.EXHIBIT_TYPES if e in present]
        else:
            options = sorted(present)
        new[f] = st.multiselect(
            labels[f],
            options,
            [v for v in sel[f] if v in options],
            format_func=formats.get(f, str),
            placeholder="Все",
            key=f"{p}_{f}",
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
    sort = st.session_state.get("sort", "без сортировки")
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
        index=0,
        horizontal=True,
        key="sort",
    )
    selected = df.iloc[[r for r in event.selection.rows if r < len(df)]]
    one = selected.iloc[0].to_dict() if len(selected) == 1 else None
    if one:  # пустые ячейки приходят как NaN — в форме это должны быть пустые поля
        one = {k: None if v != v else v for k, v in one.items()}

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
            **column_config("vyst_mo"),
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
grnti_mask()
