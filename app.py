import streamlit as st
from alkes_module import render_alkes_page
from obat_module import render_obat_page

st.set_page_config(
    page_title="KFA Kemenkes Master Extractor",
    page_icon="🏥",
    layout="wide"
)

st.sidebar.title("📌 Navigasi Utama")
main_menu = st.sidebar.radio(
    "Pilih Kelompok Master Data:",
    ["1. KFA Obat (Farmasi)", "2. KFA Alat Kesehatan (Alkes)"]
)

st.sidebar.divider()
st.sidebar.caption("SATUSEHAT KFA Scraper v2.0 - Modular Version")

if "1. KFA Obat" in main_menu:
    render_obat_page()
else:
    render_alkes_page()
