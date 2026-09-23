import streamlit as st

from backend.backend import (
    COLUMN_ORDER,
    MAIN_DB_NAME,
    get_data,
    get_profiles_list,
    import_data,
    make_db_copy
)

DATA_TABLES = ["VYST_MO", "VUZ", "GRNTIRUB"]

st.set_page_config(layout="wide")

if "show_copy_form" not in st.session_state:
    st.session_state.show_copy_form = False
if "saved_text" not in st.session_state:
    st.session_state.saved_text = ""
if "data" not in st.session_state:
    st.session_state.data = None


def handle_copy_profile():
    current_prof = st.session_state.get("current_profile", MAIN_DB_NAME)
    make_db_copy(current_prof, st.session_state.new_profile_input)
    st.session_state.show_copy_form = False


def load_data():
    table = st.session_state.get("selected_table", DATA_TABLES[0])
    profile = st.session_state.get("current_profile", MAIN_DB_NAME)
    st.session_state.data = get_data(table, profile)


st.markdown("# Обработка данных о выставочных экспонатах.")
profiles_list = get_profiles_list()

profile = st.selectbox(
    "Выберите профиль",
    options=profiles_list,
    index=profiles_list.index(MAIN_DB_NAME),
    key="current_profile",
    on_change=load_data,
)

if profile == MAIN_DB_NAME:
    st.warning(
        "⚠️ Выбран базовый профиль, его нельзя изменять. Для изменений создайте копию."
    )

if st.button("Скопировать профиль"):
    st.session_state.show_copy_form = True

if st.session_state.show_copy_form:
    with st.form(key="new_profile_form", clear_on_submit=True):
        st.text_input("Введите название нового профиля", key="new_profile_input")
        st.form_submit_button(label="Скопировать", on_click=handle_copy_profile)

table = st.pills(
    "Выберите таблицу",
    options=DATA_TABLES,
    default=DATA_TABLES[0],
    selection_mode="single",
    key="selected_table",
    required=True,
    on_change=load_data,
)

if st.session_state.data is None:
    load_data()

st.markdown(f"##### {table}")
enable_editing = False
if profile != MAIN_DB_NAME:
    enable_editing = st.toggle("Режим редактирования")

if enable_editing:
    st.session_state.data = st.data_editor(
        st.session_state.data,
        hide_index=True,
        column_config={"exponat": st.column_config.Column(width="large")},
        column_order=COLUMN_ORDER[table.lower()],
        num_rows="dynamic",
        key="my_editor",
    )
else:
    st.dataframe(
        st.session_state.data,
        hide_index=True,
        column_config={"exponat": st.column_config.Column(width="large")},
        column_order=COLUMN_ORDER[table.lower()],
    )

col1, col2, _ = st.columns([0.15, 0.15, 0.8], gap="small")
with col1:
    st.button("Сбросить изменения", on_click=load_data)
with col2:
    if st.button("Отправить изменения"):
        if enable_editing and "my_editor" in st.session_state:
            import_data(
                st.session_state.current_profile,
                st.session_state.selected_table,
                st.session_state.data,
            )
            load_data()
            st.rerun()
