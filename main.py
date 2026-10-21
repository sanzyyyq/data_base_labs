from datetime import date

import pandas as pd
import streamlit as st

from backend import backend as db

TITLE = "Обработка данных о выставочных экспонатах"
st.set_page_config(layout="wide", page_title=TITLE)
if not db.DB_PATH.exists():
    st.error("База данных не найдена. Создайте её: python backend/convert.py")
    st.stop()
st.session_state.setdefault("filters", {})
st.session_state.setdefault("page", "Данные")
st.session_state.setdefault("candidates", set())
ROW_HEIGHT = 35
TABLE_HEIGHT = 708


def column_config(table):
    widths = {"subject": 800, "exponat": 600, "vystavki": 1380}
    return {
        c: st.column_config.Column(l, width=widths.get(c))
        for c, l in db.LABELS[table].items()
    }


GRNTI_LABEL = "Код ГРНТИ (только цифры)"


def grnti_mask():
    st.html(
        f"""<style>
        [data-testid="stMainBlockContainer"] {{ padding-top: 1rem; padding-bottom: 1rem; }}
        .st-key-dblclick {{ position: absolute; left: -10000px; }}
        [data-testid="stHeading"] h3 {{ padding: 0 0 0 1rem; }}
        [id^="gdg-overlay-"] {{ display: none !important; }}
        [data-testid="stHeader"] {{ background: transparent; pointer-events: none; }}
        [data-testid="stHeader"] * {{ pointer-events: none; }}
        [data-testid="stHeader"] button, [data-testid="stHeader"] a {{ pointer-events: auto; }}
        [class*="st-key-gcard_"] {{ position: relative; transition: border-color .15s, background .15s; }}
        [class*="st-key-gcard_"]:hover {{ border-color: #ff4b4b; background: rgba(255, 75, 75, .04); }}
        [class*="st-key-gopen_"] {{ position: absolute; inset: 0; z-index: 1; margin: 0;
          width: 100% !important; height: 100% !important; }}
        [class*="st-key-gopen_"] * {{ width: 100% !important; height: 100% !important; }}
        [class*="st-key-gopen_"] button {{ opacity: 0; cursor: pointer; }}
        [class*="st-key-gsel_"] {{ position: relative; z-index: 2; }}
        .st-key-card input, .st-key-card textarea {{
          color: inherit !important; -webkit-text-fill-color: currentColor !important;
          opacity: 1 !important; cursor: text !important;
        }}
        .st-key-card label, .st-key-card label p {{ color: inherit !important; opacity: 1 !important; }}
        [data-testid="stElementContainer"]:has(> [data-testid="stHtml"] > script) {{ display: none; }}
        </style>
        <script>
        (() => {{
          if (window.grntiMaskOff) window.grntiMaskOff();
          const MAX_CODES = 3;
          const format = (value, deleting) => {{
            const codes = value.split(/[,;]/).map(part => part.replace(/\\D/g, ""));
            for (let i = 0; i < codes.length; i++) {{
              if (codes[i].length <= 6) continue;
              const extra = codes[i].slice(6);
              codes[i] = codes[i].slice(0, 6);
              if (i + 1 < codes.length) codes[i + 1] = extra + codes[i + 1];
              else codes.push(extra);
            }}
            if (deleting) while (codes.length > 1 && !codes[codes.length - 1]) codes.pop();
            return codes.slice(0, MAX_CODES)
              .map(d => (d.match(/.{{1,2}}/g) || []).join("."))
              .join("; ");
          }};
          const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
          const isMasked = el => el.tagName === "INPUT" && el.closest(".st-key-rec_grnti");
          const onFocus = e => {{
            if (isMasked(e.target)) e.target.dataset.prev = e.target.value;
          }};
          const onInput = e => {{
            const el = e.target;
            if (!isMasked(el)) return;
            const deleting = (e.inputType || "").startsWith("delete");
            let value = el.value, caret = el.selectionStart;
            const prev = el.dataset.prev || "";
            const digitsOf = v => v.replace(/\\D/g, "");
            if (deleting && value !== prev && digitsOf(value) === digitsOf(prev)) {{
              const back = e.inputType === "deleteContentBackward";
              let i = back ? caret - 1 : caret;
              while (i >= 0 && i < value.length && !/\\d/.test(value[i])) i += back ? -1 : 1;
              if (i >= 0 && i < value.length) {{
                value = value.slice(0, i) + value.slice(i + 1);
                if (back) caret = i;
              }}
            }}
            const formatted = format(value, deleting);
            el.dataset.prev = formatted;
            if (formatted === el.value) return;
            const digits = digitsOf(value.slice(0, caret)).length;
            let pos = 0;
            for (let n = 0; pos < formatted.length && n < digits; pos++)
              if (/\\d/.test(formatted[pos])) n++;
            setValue.call(el, formatted);
            el.setSelectionRange(pos, pos);
            el.dispatchEvent(new Event("input", {{ bubbles: true }}));
          }};
          document.addEventListener("focusin", onFocus, true);
          const onDblClick = e => {{
            const grid = e.target.closest('[class*="st-key-nir_table_"], [class*="st-key-group_"]');
            const input = document.querySelector(".st-key-dblclick input");
            const sc = grid && grid.querySelector(".dvn-scroller");
            if (!sc || !input) return;
            const y = e.clientY - sc.getBoundingClientRect().top - {ROW_HEIGHT};
            if (y < 0) return;
            input.focus();
            setValue.call(input, `${{Math.floor((y + sc.scrollTop) / {ROW_HEIGHT})}}:${{Date.now()}}`);
            input.dispatchEvent(new Event("input", {{ bubbles: true }}));
            input.blur();
          }};
          document.addEventListener("input", onInput, true);
          document.addEventListener("dblclick", onDblClick, true);
          window.grntiMaskOff = () => {{
            document.removeEventListener("focusin", onFocus, true);
            document.removeEventListener("input", onInput, true);
            document.removeEventListener("dblclick", onDblClick, true);
          }};
        }})();
        </script>""",
        unsafe_allow_javascript=True,
    )


def save_menu(
    container, label, df, filename, title, notes=(), primary=False, width="stretch"
):
    menu = container.popover(
        label, type="primary" if primary else "secondary", width=width
    )
    for fmt in db.FORMATS:
        data, ext, mime = db.export(df, fmt, title, notes)
        menu.download_button(
            fmt, data, file_name=f"{filename}.{ext}", mime=mime, width="stretch"
        )


def show(df, table, **kwargs):
    order, config = list(db.LABELS[table]), column_config(table)
    if "candidate" in df:
        order = ["candidate", *order]
        config["candidate"] = st.column_config.CheckboxColumn("Кандидат")
    return st.dataframe(
        df.fillna(""),
        hide_index=True,
        column_order=order,
        column_config=config,
        height=TABLE_HEIGHT,
        width="stretch",
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
        return col.container(key=f"rec_{name}")

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
            empty = [msg for fields, msg in errors if not new.get(fields[-1])]
            lines = [msg for fields, msg in errors if new.get(fields[-1])]
            lines += ["Заполните выделенные поля"] if empty else []
            message.error("\n".join(f"- {line}" for line in lines))
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
            st.session_state.select_id = rec_id
            st.rerun()


def suggest_group_name(flt, picked, existing):
    names = db.vuz_names()
    parts = [v for f in ("region", "oblname", "city") for v in flt.get(f, [])]
    parts += [names[v] for v in flt.get("codvuz", [])]
    parts += [f"ГРНТИ {r:02d}" for r in flt.get("rubrics", [])]
    parts += [f"экспонат {db.EXHIBIT_TYPES[e]}" for e in flt.get("exhitype", [])]
    today = f"{date.today():%d.%m.%Y}"
    if picked or not parts:
        full = short = f"{'Выбранные НИР' if picked else 'Все НИР'} {today}"
    else:
        full = f"{', '.join(parts)} {today}"
        short = (
            f"{parts[0]}{f' и ещё {len(parts) - 1}' if len(parts) > 1 else ''} {today}"
        )
    name, n = short, 1
    while name in existing:
        n += 1
        name = f"{short} ({n})"
    return name, full


def card_dialog(rec):
    st.dialog(rec.get("subject") or "Карточка НИР", width="large")(card_body)(rec)


def card_body(rec):
    def field(col, label, value, area=False):
        widget = col.text_area if area else col.text_input
        kwargs = {"height": 68} if area else {}
        widget(label, value or "—", disabled=True, **kwargs)

    nir_types = {"Е": "тематический план", "М": "научно-техническая программа"}
    vuz_name = db.vuz_names().get(int(rec["codvuz"]), rec.get("shortname") or "")
    box = st.container(key="card")
    c1, c2, c3 = box.columns([5, 3, 2])
    field(c1, "Вуз", f"{rec['codvuz']} — {vuz_name}")
    field(c2, "Форма НИР", f"{rec['type']} — {nir_types.get(rec['type'], '')}")
    field(c3, "Рег. №", rec.get("regnumber"))
    c1, c2, c3 = box.columns([2, 2, 1])
    field(c1, "Код ГРНТИ", rec.get("grnti"))
    field(c2, "Руководитель", rec.get("bossname"))
    field(c3, "Должность", rec.get("bosstitle"))
    field(box, "Экспонат", db.EXHIBIT_TYPES.get(rec.get("exhitype"), rec.get("exhitype")))
    if rec.get("exhitype") != "Н":
        c1, c2 = box.columns(2)
        field(c1, "Информация о выставке", rec.get("vystavki"), area=True)
        field(c2, "Название экспоната", rec.get("exponat"), area=True)
    card = pd.DataFrame(db.nir_card(int(rec["id"])), columns=["Поле", "Значение"])
    save_menu(
        st.container(horizontal=True),
        "Сохранить карточку",
        card,
        f"Карточка НИР {rec['codvuz']}-{rec.get('regnumber')}",
        "Карточка НИР",
        primary=True,
        width="content",
    )


@st.dialog("Удаление записей")
def delete_dialog(records):
    st.write(f"Удалить выбранные записи ({len(records)})? Это действие нельзя отменить.")
    lines = [
        f"- {r.codvuz} / {r.type} / {r.regnumber} — {r.subject}"
        for r in records.head(10).itertuples()
    ]
    if len(records) > 10:
        lines.append(f"- …и ещё {len(records) - 10}")
    st.markdown("\n".join(lines))
    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Удалить", type="primary"):
        for rec_id in records["id"]:
            db.execute("DELETE FROM vyst_mo WHERE id = ?", (int(rec_id),))
        reset_selection()
        st.rerun()
    if c.button("Отмена"):
        st.rerun()


@st.dialog("Сохранить группу")
def group_dialog(ids, flt, picked):
    filter_desc = db.describe_filter(flt)
    existing = db.get_groups()["name"].tolist()
    suggested, full = suggest_group_name(flt, picked, existing)
    name = st.text_input("Название новой группы", suggested).strip()
    if name == suggested and full != suggested:
        st.caption(f"Полное название: {full}")
    st.caption(f"Записей: {len(ids)}. Условия отбора: {filter_desc}")
    if name in existing:
        st.warning("Группа с таким названием уже есть, введите другое")
    if st.button("Сохранить", type="primary", disabled=not name or name in existing):
        db.add_to_group(name, filter_desc, ids)
        st.toast("Сохранено")
        st.rerun()


@st.dialog("Перенос кандидатов в группу")
def transfer_dialog(ids):
    groups = db.get_groups()["name"].tolist()
    if not groups:
        st.info("Групп пока нет. Создайте группу кнопкой «Сохранить группу».")
        return
    name = st.selectbox("Группа", groups, index=None, placeholder="Выберите группу")
    clear = st.checkbox("Снять отметки после переноса", value=True)
    st.caption(f"Кандидатов: {len(ids)}")
    if st.button("Перенести", type="primary", disabled=not name):
        db.add_to_group(name, "", ids)
        if clear:
            st.session_state.candidates.clear()
        st.toast(f"Перенесено в группу «{name}»")
        st.rerun()


@st.dialog("Добавить в группу")
def add_to_group_dialog(ids, current):
    groups = [g for g in db.get_groups()["name"] if g != current]
    if not groups:
        st.info("Других групп нет")
        return
    name = st.selectbox("Группа", groups, index=None, placeholder="Выберите группу")
    st.caption(f"Записей: {len(ids)}")
    if st.button("Добавить", type="primary", disabled=not name):
        db.add_to_group(name, "", ids)
        st.toast(f"Добавлено в группу «{name}»")
        st.rerun()


@st.dialog("Фильтр")
def filter_dialog():
    flt = st.session_state.filters
    geo = db.get_table("vuz")[list(db.GEO_FIELDS)].dropna()
    nir = db.get_table("vyst_mo")[["codvuz", "grnti", "exhitype"]]
    nir = nir.assign(rubrics=nir["grnti"].apply(lambda v: sorted(db.record_rubrics(v))))
    nir = nir.explode("rubrics").merge(geo, on="codvuz")
    nir_fields = ("rubrics", "exhitype")
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
    p = f"flt{st.session_state.flt_n}"
    sel = {f: st.session_state.get(f"{p}_{f}", flt.get(f, [])) for f in fields}
    new = {}
    for f in fields:
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
    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Применить", type="primary"):
        st.session_state.filters = {k: v for k, v in new.items() if v}
        st.rerun()
    if c.button("Сбросить фильтр"):
        st.session_state.filters = {}
        st.rerun()


def open_card_on_dblclick(df):
    def remember_row():
        value = st.session_state.dblclick
        st.session_state.dblclick = ""
        if value:
            st.session_state.card_row = int(value.split(":")[0])

    st.text_input(
        "dblclick", key="dblclick", on_change=remember_row, label_visibility="collapsed"
    )
    row = st.session_state.pop("card_row", None)
    if row is not None and row < len(df):
        card_dialog({k: None if v != v else v for k, v in df.iloc[row].to_dict().items()})


def table_key():
    return f"nir_table_{st.session_state.get('table_n', 0)}"


def reset_selection():
    st.session_state.table_n = st.session_state.get("table_n", 0) + 1


def scroll_to_row(row):
    st.session_state.scroll_n = st.session_state.get("scroll_n", 0) + 1
    st.html(
        f"""<script>
        window.scrollN = {st.session_state.scroll_n};
        (() => {{
          const n = window.scrollN, row = {row}, h = {ROW_HEIGHT};
          let tries = 0, scrolledAt = null, userScrolled = false;
          const timer = setInterval(() => {{
            if (window.scrollN !== n || userScrolled || ++tries > 100) return clearInterval(timer);
            const sc = document.querySelector(".st-key-{table_key()} .dvn-scroller");
            if (!sc || sc.scrollHeight < (row + 2) * h) return;
            const top = Math.min(
              Math.max(0, (row + 1) * h - sc.clientHeight / 2),
              sc.scrollHeight - sc.clientHeight,
            );
            if (scrolledAt === null) {{
              sc.addEventListener("wheel", () => (userScrolled = true), {{ once: true }});
            }}
            if (scrolledAt === null) {{
              sc.scrollTo({{ top, behavior: "smooth" }});
              scrolledAt = tries;
            }} else if (tries - scrolledAt > 15 && Math.abs(sc.scrollTop - top) > h) {{
              sc.scrollTop = top;
              scrolledAt = tries;
            }} else if (tries - scrolledAt > 40) {{
              clearInterval(timer);
            }}
          }}, 100);
        }})();
        </script>""",
        unsafe_allow_javascript=True,
    )


def data_page():
    table = st.session_state.get("table", "vyst_mo")
    df = db.get_table(table)
    if table != "vyst_mo":
        st.caption(f"Записей: {len(df)}")
        show(df, table)
        return

    cands = st.session_state.candidates
    cands &= set(df["id"])
    if st.session_state.pop("open_transfer", False):
        transfer_dialog(sorted(cands))
    flt = st.session_state.filters
    df = db.apply_filter(df, flt).assign(candidate=lambda d: d["id"].isin(cands))
    sort = st.session_state.get("sort", "без сортировки")
    if sort != "без сортировки":
        df = db.sort_by_key(df, ascending=sort == "по возрастанию")
    df = df.reset_index(drop=True)

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
        f"Записей: {len(df)}"
        + (f". Кандидатов: {len(cands)}" if cands else "")
        + (f". Фильтр: {db.describe_filter(flt)}" if flt else "")
    )
    event = show(
        df,
        table,
        key=table_key(),
        on_select="rerun",
        selection_mode="multi-row",
        row_height=ROW_HEIGHT,
    )
    selected = df.iloc[[r for r in event.selection.rows if r < len(df)]]
    open_card_on_dblclick(df)
    one = selected.iloc[0].to_dict() if len(selected) == 1 else None
    if one:
        one = {k: None if v != v else v for k, v in one.items()}

    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Фильтр", width="stretch"):
        st.session_state.flt_n = st.session_state.get("flt_n", 0) + 1
        filter_dialog()
    c.selectbox(
        "Сортировка",
        ["без сортировки", "по возрастанию", "по убыванию"],
        format_func=lambda v: f"Сортировка: {v}",
        key="sort",
        label_visibility="collapsed",
        help="По составному ключу: код вуза + форма НИР + рег. №",
        width=260,
    )
    if c.button("Добавить", width="stretch"):
        record_dialog()
    if c.button("Изменить", disabled=not one, width="stretch"):
        record_dialog(one)
    if c.button("Удалить", disabled=selected.empty, width="stretch"):
        delete_dialog(selected)
    if c.button("Карточка НИР", disabled=not one, width="stretch"):
        card_dialog(one)
    if c.button("Сохранить группу", width="stretch"):
        group_dialog(
            (selected if len(selected) else df)["id"].tolist(), flt, len(selected) > 0
        )
    if st.session_state.pop("close_cand", False):
        st.session_state.cand_menu = False
    menu = c.popover("Кандидаты", width="stretch", key="cand_menu", on_change="rerun")
    ids = set(selected["id"])
    actions = [
        ("Отметить выделенные", selected.empty, lambda: cands.update(ids)),
        (
            "Снять отметку с выделенных",
            selected.empty,
            lambda: cands.difference_update(ids),
        ),
        ("Снять все отметки", not cands, cands.clear),
        (
            "Перенести в группу…",
            not cands,
            lambda: st.session_state.update(open_transfer=True),
        ),
    ]
    for label, disabled, action in actions:
        if menu.button(label, disabled=disabled, width="stretch"):
            action()
            st.session_state.close_cand = True
            st.rerun()

    if scroll_row is not None:
        scroll_to_row(scroll_row)


@st.dialog("Удаление групп")
def delete_groups_dialog(groups):
    st.write(f"Удалить выбранные группы ({len(groups)})? Записи НИР останутся в базе.")
    st.markdown("\n".join(f"- {name}" for name in groups["name"]))
    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Удалить", type="primary"):
        for gid in groups["id"]:
            db.execute("DELETE FROM nir_groups WHERE id = ?", (int(gid),))
        st.session_state.groups_n = st.session_state.get("groups_n", 0) + 1
        st.rerun()
    if c.button("Отмена"):
        st.rerun()


@st.dialog("Объединение групп")
def merge_dialog(selected, groups):
    names = selected["name"].tolist()
    st.write("Записи из групп: " + ", ".join(f"«{n}»" for n in names))
    suggested = " + ".join(names) if len(names) > 1 else None
    existing = groups["name"].tolist()
    options = ([suggested] if suggested and suggested not in existing else []) + existing
    target = st.selectbox(
        "Добавить в группу",
        options,
        index=0 if suggested else None,
        format_func=lambda g: f"{g} (новая)" if g not in existing else g,
        accept_new_options=True,
        placeholder="Выберите группу или введите название новой",
    )
    drop = st.checkbox("Удалить исходные группы после объединения")
    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Объединить", type="primary", disabled=not target or [target] == names):
        target_id = db.merge_groups(
            selected["id"], target.strip(), "Объединение групп: " + ", ".join(names)
        )
        if drop:
            for gid in selected["id"]:
                if int(gid) != target_id:
                    db.execute("DELETE FROM nir_groups WHERE id = ?", (int(gid),))
        st.session_state.groups_n = st.session_state.get("groups_n", 0) + 1
        st.toast("Группы объединены")
        st.rerun()
    if c.button("Отмена"):
        st.rerun()


def groups_list():
    groups = db.get_groups()
    if groups.empty:
        st.info(
            "Групп пока нет. Отберите записи на странице «Данные» и нажмите «Сохранить группу»."
        )
        return
    st.caption(
        f"Групп: {len(groups)}. Нажмите на группу, чтобы открыть её; "
        "отметьте группы галочками, чтобы объединить или удалить"
    )
    n = st.session_state.get("groups_n", 0)
    grid = st.container(height=TABLE_HEIGHT, border=False)
    for g in groups.itertuples():
        card = grid.container(border=True, key=f"gcard_{g.id}")
        top = card.container(horizontal=True, vertical_alignment="top", wrap=False)
        top.checkbox(
            "Выбрать",
            key=f"gsel_{n}_{g.id}",
            label_visibility="collapsed",
            width="content",
        )
        top.markdown(f"**{g.name}**")
        card.caption(
            f"НИР: {g.n} · В выставку: {g.n_included} · Условия отбора: {g.filter_desc}"
        )
        if card.button("Открыть", key=f"gopen_{g.id}"):
            st.session_state.open_group = int(g.id)
            st.session_state.groups_n = n + 1
            st.rerun()
    selected = groups[
        [bool(st.session_state.get(f"gsel_{n}_{gid}")) for gid in groups["id"]]
    ]
    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Объединить", disabled=selected.empty, width="stretch"):
        merge_dialog(selected, groups)
    if c.button("Удалить", disabled=selected.empty, width="stretch"):
        delete_groups_dialog(selected)


@st.dialog("Убрать записи из группы")
def remove_items_dialog(gid, records):
    st.write(
        f"Убрать выбранные записи ({len(records)}) из группы? В базе НИР они останутся."
    )
    st.markdown(
        "\n".join(
            f"- {r.codvuz} / {r.type} / {r.regnumber} — {r.subject}"
            for r in records.head(10).itertuples()
        )
        + (f"\n- …и ещё {len(records) - 10}" if len(records) > 10 else "")
    )
    c = st.container(horizontal=True, gap="xsmall")
    if c.button("Убрать", type="primary"):
        db.remove_from_group(gid, records["id"])
        st.session_state.group_n = st.session_state.get("group_n", 0) + 1
        st.rerun()
    if c.button("Отмена"):
        st.rerun()


def group_view(gid):
    groups = db.get_groups().set_index("id")
    if gid not in groups.index:
        st.session_state.open_group = None
        st.rerun()
    group = groups.loc[gid]
    st.caption(f"Группа «{group['name']}». Условия отбора: {group['filter_desc']}")
    items = db.get_group_items(gid)
    event = st.dataframe(
        items.fillna(""),
        hide_index=True,
        key=f"group_{gid}_{st.session_state.get('group_n', 0)}",
        column_order=["included", *db.LABELS["vyst_mo"]],
        column_config={
            "included": st.column_config.CheckboxColumn("В выставку"),
            **column_config("vyst_mo"),
        },
        on_select="rerun",
        selection_mode="multi-row",
        height=TABLE_HEIGHT,
        width="stretch",
    )
    chosen = items.iloc[[r for r in event.selection.rows if r < len(items)]]
    open_card_on_dblclick(items)
    c = st.container(horizontal=True, gap="xsmall")
    if c.button("К списку групп", width="stretch"):
        st.session_state.open_group = None
        st.rerun()
    for label, mark in (("В выставку", True), ("Убрать из выставки", False)):
        if c.button(label, disabled=chosen.empty, width="stretch"):
            db.save_marks(gid, {rec_id: mark for rec_id in chosen["id"]})
            st.rerun()
    if c.button("Карточка НИР", disabled=len(chosen) != 1, width="stretch"):
        card_dialog(
            {k: None if v != v else v for k, v in chosen.iloc[0].to_dict().items()}
        )
    if c.button("Добавить в группу", disabled=chosen.empty, width="stretch"):
        add_to_group_dialog(chosen["id"].tolist(), group["name"])
    if c.button("Убрать из группы", disabled=chosen.empty, width="stretch"):
        remove_items_dialog(gid, chosen)
    table = items.assign(included=items["included"].map({True: "да", False: "нет"}))
    save_menu(
        c,
        "Сохранить список",
        table[["included", *db.LABELS["vyst_mo"]]].rename(
            columns={**db.LABELS["vyst_mo"], "included": "В выставку"}
        ),
        f"Группа {group['name']}",
        f"Список группы НИР «{group['name']}»",
        [
            f"Условия отбора: {group['filter_desc']}",
            f"Всего НИР: {len(items)}, включено в выставку: {int(items['included'].sum())}",
            f"Дата формирования: {date.today():%d.%m.%Y}",
        ],
    )


def groups_page():
    gid = st.session_state.get("open_group")
    if gid is None:
        groups_list()
    else:
        group_view(gid)


TABLES = {
    "vyst_mo": "НИР (VYST_MO)",
    "vuz": "Вузы (VUZ)",
    "grntirub": "Рубрики ГРНТИ (GRNTIRUB)",
}
if st.session_state.pop("close_menu", False):
    st.session_state.data_menu = False
menu = st.container(horizontal=True, gap="xsmall", vertical_alignment="center")
data_menu = menu.popover(
    "Данные",
    type="primary" if st.session_state.page == "Данные" else "secondary",
    key="data_menu",
    on_change="rerun",
)
for table, title in TABLES.items():
    current = (
        st.session_state.page == "Данные"
        and st.session_state.get("table", "vyst_mo") == table
    )
    if data_menu.button(
        title, type="primary" if current else "secondary", width="stretch"
    ):
        st.session_state.page, st.session_state.table = "Данные", table
        st.session_state.close_menu = True
        st.rerun()
if menu.button(
    "Группы", type="primary" if st.session_state.page == "Группы" else "secondary"
):
    st.session_state.page, st.session_state.open_group = "Группы", None
    st.rerun()
menu.subheader(TITLE, anchor=False)
if st.session_state.page == "Данные":
    data_page()
else:
    groups_page()
grnti_mask()
