import streamlit as st
import requests
import json
import pandas as pd
import io

st.set_page_config(
    page_title="KFA Alkes Variant Extractor",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 SATUSEHAT KFA Alkes Produk Varian Extractor")
st.markdown("Aplikasi ini menarik master data **Produk Varian Alat Kesehatan (KFA)** dari SATUSEHAT Kemenkes RI.")

URL_VARIANT = "https://satusehat.kemkes.go.id/kfa-browser/alkes/api/product-variant/search-variant"

headers = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Origin": "https://satusehat.kemkes.go.id",
    "Referer": "https://satusehat.kemkes.go.id/kfa-browser/alkes"
}

COLUMN_MAPPING = {
    "kfa_code": "Kode KFA (PA)",
    "kfaCode": "Kode KFA (PA)",
    "name": "Nama produk varian",
    "product_variant_name": "Nama produk varian",
    "productVariantName": "Nama produk varian",
    "nie": "Nomor ijin edar",
    "registrar": "Pemilik NIE",
    "registrar_name": "Pemilik NIE",
    "registrar.name": "Pemilik NIE",
    "manufacturer": "Pabrik",
    "manufacturer_name": "Pabrik",
    "manufacturer.name": "Pabrik",
    "made_origin": "Asal Produk",
    "madeOrigin": "Asal Produk",
    "bmhp": "BMHP"
}

def parse_items_to_df(items):
    if not items:
        return pd.DataFrame()
    df = pd.json_normalize(items)
    
    renamed_cols = {}
    for col in df.columns:
        for key, val in COLUMN_MAPPING.items():
            if col == key or col.endswith('.' + key):
                renamed_cols[col] = val
                break
    df.rename(columns=renamed_cols, inplace=True)
    return df

def build_payload(keyword, page, size):
    return {
        "page": int(page),
        "size": int(size),
        "search": keyword.strip(),
        "kfa_code": "",
        "bmhp": "",
        "made_origin": "",
        "manufacturer": "",
        "registrar": ""
    }

# Sidebar Pengaturan
st.sidebar.header("⚙️ Konfigurasi Request")
batch_size = st.sidebar.slider("Jumlah Data Per Request (Size)", min_value=10, max_value=100, value=100, step=10)
max_pages = st.sidebar.number_input("Batas Maksimal Halaman Per Kata Kunci (0 = Tanpa Batas)", min_value=0, value=0, step=1)
search_keyword = st.sidebar.text_input("Kata Kunci Pencarian (Jika kosong, akan auto-fetch kata kunci huruf vokal)", value="cath")

if "all_fetched_data" not in st.session_state:
    st.session_state["all_fetched_data"] = None

@st.cache_data(ttl=3600)
def get_variant_schema(sample_query):
    payload = build_payload(sample_query, 1, 5)
    try:
        resp = requests.post(URL_VARIANT, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            res_json = resp.json()
            items = []
            if isinstance(res_json, dict):
                items = res_json.get('items') or res_json.get('data') or res_json.get('content') or []
                if isinstance(items, dict):
                    items = items.get('items') or items.get('data') or []
            elif isinstance(res_json, list):
                items = res_json

            if items:
                df_sample = parse_items_to_df(items)
                return list(df_sample.columns)
    except Exception:
        pass
    
    return [
        "Kode KFA (PA)",
        "Nama produk varian",
        "Nomor ijin edar",
        "Pemilik NIE",
        "Pabrik"
    ]

sample_query = search_keyword if search_keyword.strip() else "cath"
sample_columns = get_variant_schema(sample_query)

PREFERRED_ORDER = [
    "Kode KFA (PA)",
    "Nama produk varian",
    "Nomor ijin edar",
    "Pemilik NIE",
    "Pabrik"
]

default_selected = [c for c in PREFERRED_ORDER if c in sample_columns] or sample_columns

st.subheader("📌 Pilih Kolom yang Ingin Diunduh")
selected_columns = st.multiselect(
    "Silakan pilih atau sesuaikan kolom yang dibutuhkan:",
    options=sample_columns,
    default=default_selected
)

st.divider()

start_download = st.button("🚀 Mulai Penarikan Data Produk Varian", type="primary")

if start_download:
    all_raw_data = []
    seen_ids = set()  # Untuk membuang data duplikat jika menggunakan multiple keyword
    
    status_text = st.empty()
    table_placeholder = st.empty()

    # Jika user tidak mengisi kata kunci, gunakan daftar huruf umum
    keywords_to_search = [search_keyword.strip()] if search_keyword.strip() else ["a", "e", "i", "o", "u"]

    for kw in keywords_to_search:
        page = 1
        st.toast(f"Mulai mencari kata kunci: '{kw}'")
        
        while True:
            status_text.info(f"⏳ Kata kunci **'{kw}'** | Halaman **{page}** ({batch_size} item per request)...")
            
            payload = build_payload(kw, page, batch_size)
            
            try:
                response = requests.post(URL_VARIANT, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    res_json = response.json()
                    
                    items = []
                    if isinstance(res_json, dict):
                        items = res_json.get('items') or res_json.get('data') or res_json.get('content') or []
                        if isinstance(items, dict):
                            items = items.get('items') or items.get('data') or []
                    elif isinstance(res_json, list):
                        items = res_json
                    
                    if not items:
                        break
                        
                    # Eliminasi duplikat berdasarkan kfa_code atau kfaCode
                    added_count = 0
                    for item in items:
                        code = item.get('kfa_code') or item.get('kfaCode') or item.get('id') or str(item)
                        if code not in seen_ids:
                            seen_ids.add(code)
                            all_raw_data.append(item)
                            added_count += 1
                            
                    status_text.info(f"🔄 Kata kunci **'{kw}'** | Halaman {page}: Berhasil menambah **{added_count}** data baru (Total Unik: **{len(all_raw_data)}**)")
                    
                    df_current = parse_items_to_df(all_raw_data)
                    if selected_columns:
                        cols_to_show = [c for c in selected_columns if c in df_current.columns]
                        if cols_to_show:
                            df_current = df_current[cols_to_show]
                    table_placeholder.dataframe(df_current.tail(10), use_container_width=True)
                    
                    if len(items) < batch_size:
                        break
                        
                    if max_pages > 0 and page >= max_pages:
                        break
                        
                    page += 1
                else:
                    status_text.error(f"❌ HTTP Error {response.status_code} pada halaman {page}.")
                    break
                    
            except Exception as e:
                status_text.error(f"❌ Terjadi kesalahan koneksi: {str(e)}")
                break

    if all_raw_data:
        status_text.success(f"✅ Penarikan data selesai! Total **{len(all_raw_data)}** data unik berhasil dikumpulkan.")
        st.session_state["all_fetched_data"] = all_raw_data

if st.session_state["all_fetched_data"]:
    st.divider()
    st.subheader("📥 Download Hasil Data")
    
    df_final = parse_items_to_df(st.session_state["all_fetched_data"])
    
    if selected_columns:
        valid_cols = [c for c in selected_columns if c in df_final.columns]
        if valid_cols:
            df_final = df_final[valid_cols]
            
    buffer = io.StringIO()
    df_final.to_csv(buffer, sep="|", index=False, encoding="utf-8")
    txt_bytes = buffer.getvalue().encode("utf-8")
    
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📄 Download File TXT (Separator |)",
            data=txt_bytes,
            file_name="kfa_alkes_produk_varian.txt",
            mime="text/plain",
            type="primary"
        )
    with col_dl2:
        st.metric(label="Total Baris Data Varian", value=f"{len(df_final):,}")
        st.metric(label="Total Kolom Terpilih", value=f"{len(df_final.columns)}")
        
    st.subheader("👀 Preview Data Akhir (10 Baris Pertama)")
    st.dataframe(df_final.head(10), use_container_width=True)
