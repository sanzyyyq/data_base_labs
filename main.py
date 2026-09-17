import streamlit as st
from backend.backend import data
import numpy as np

dataframe = np.random.randn(10, 20)
st.dataframe(dataframe)
st.subheader(data())

st.text_input("Your name", key="name")

# You can access the value at any point with:
if st.session_state.name:
    st.text(f"Your name is {st.session_state.name}")
