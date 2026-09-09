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
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Pemetaan komprehensif nama atribut nested ke bahasa Indonesia
COLUMN_MAPPING = {
    "kfa_code": "Kode KFA (PA)",
    "kfaCode": "Kode KFA (PA)",
    "name": "Nama produk varian",
    "product_variant_name": "Nama produk varian",
    "nie": "Nomor ijin edar",
    "registrar": "Pemilik NIE",
    "registrar_name": "Pemilik NIE",
    "registrar.name": "Pemilik NIE",
    "manufacturer": "Pabrik",
    "manufacturer_name": "Pabrik",
    "manufacturer.name": "Pabrik",
    "made_origin": "Asal Produk",
    "bmhp": "BMHP"
}

# Fungsi normalisasi JSON nested
def parse_items_to_df(items):
    if not items:
        return pd.DataFrame()
    # Meratakan struktur JSON nested
    df = pd.json_normalize(items)
    
    # Menyesuaikan nama kolom sesuai mapping yang cocok
    renamed_cols = {}
    for col in df.columns:
        # Cek jika ada kecocokan di dictionary mapping
        for key, val in COLUMN_MAPPING.items():
            if col == key or col.endswith('.' + key):
                renamed_cols[col] = val
                break
    df.rename(columns=renamed_cols, inplace=True)
    return df

# Sidebar Pengaturan
st.sidebar.header("⚙️ Konfigurasi Request")
batch_size = st.sidebar.number_input("Jumlah Data Per Request (Size)", min_value=10, max_value=5000, value=1000, step=100)
max_pages = st.sidebar.number_input("Batas Maksimal Halaman (0 = Tanpa Batas)", min_value=0, value=0, step=1)
search_keyword = st.sidebar.text_input("Kata Kunci Pencarian (Biarkan kosong untuk semua data)", value="")

if "all_fetched_data" not in st.session_state:
    st.session_state["all_fetched_data"] = None

# Step 1: Pre-fetch schema
@st.cache_data(ttl=3600)
def get_variant_schema():
    payload = {
        "search": "",
        "size": 5,
        "page": 1,
        "kfa_code": "",
        "bmhp": "",
        "made_origin": "",
        "manufacturer": "",
        "registrar": ""
    }
    try:
        resp = requests.post(URL_VARIANT, headers=headers, json=payload, timeout=10)
        if resp.status_code == 200:
            res_json = resp.json()
            items = res_json.get('items') or res_json.get('data') or []
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

sample_columns = get_variant_schema()

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

# Tombol Ekstraksi Data
start_download = st.button("🚀 Mulai Penarikan Data Produk Varian", type="primary")

if start_download:
    all_data = []
    page = 1
    
    status_text = st.empty()
    table_placeholder = st.empty()

    while True:
        status_text.info(f"⏳ Sedang mengambil data Produk Varian Halaman **{page}** ({batch_size} item per request)...")
        
        payload = {
            "search": search_keyword,
            "size": batch_size,
            "page": page,
            "kfa_code": "",
            "bmhp": "",
            "made_origin": "",
            "manufacturer": "",
            "registrar": ""
        }
        
        try:
            response = requests.post(URL_VARIANT, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                res_json = response.json()
                items = res_json.get('items') or res_json.get('data') or []
                
                if not items:
                    status_text.success(f"✅ Penarikan data selesai! Total **{len(all_data)}** data varian berhasil diambil.")
                    break
                    
                all_data.extend(items)
                status_text.info(f"🔄 Berhasil mengambil **{len(items)}** varian dari Halaman {page} (Total Sementara: **{len(all_data)}** data)")
                
                # Render preview
                df_current = parse_items_to_df(all_data)
                if selected_columns:
                    cols_to_show = [c for c in selected_columns if c in df_current.columns]
                    if cols_to_show:
                        df_current = df_current[cols_to_show]
                table_placeholder.dataframe(df_current.tail(10), use_container_width=True)
                
                if len(items) < batch_size:
                    status_text.success(f"✅ Mencapai akhir halaman. Total **{len(all_data)}** data varian berhasil diambil.")
                    break
                    
                if max_pages > 0 and page >= max_pages:
                    status_text.warning(f"⚠️ Penarikan dihentikan karena mencapai batas halaman ({max_pages}). Total: **{len(all_data)}** data.")
                    break
                    
                page += 1
            else:
                status_text.error(f"❌ HTTP Error {response.status_code} pada halaman {page}.")
                break
                
        except Exception as e:
            status_text.error(f"❌ Terjadi kesalahan koneksi: {str(e)}")
            break

    if all_data:
        st.session_state["all_fetched_data"] = all_data

# Ekspor Data
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
