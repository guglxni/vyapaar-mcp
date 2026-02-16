import streamlit as st
st.title("Streamlit Diagnostic")
st.write("If you can see this, Streamlit is working correctly.")
st.write("Environment check:")
import os
st.json(dict(os.environ))
