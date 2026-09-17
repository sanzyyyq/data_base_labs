import streamlit as st
from backend.backend import data

DATA_TABLES = ["VYST_MO", "VUZ", "GRNTIRUB"]

st.set_page_config(layout="wide")

table = st.selectbox("Выберите таблицу", options=DATA_TABLES)

st.markdown(f"##### {table}")
st.dataframe(data(table), hide_index=True)

enable = st.checkbox("Enable camera")
picture = None
if enable:
    picture = st.camera_input("Take a picture")

if picture:
    st.markdown(f"## It's you")
    st.image(picture)
