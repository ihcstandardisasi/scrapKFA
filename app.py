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

URL_SEARCH = "https://satusehat.kemkes.go.id/kfa-browser/alkes/api/product-template/search-template"

headers = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Origin": "https://satusehat.kemkes.go.id",
    "Referer": "https://satusehat.kemkes.go.id/kfa-browser/alkes"
}

# Pemetaan resmi kunci JSON API Kemenkes ke Label Bahasa Indonesia
COLUMN_MAPPING = {
    "kfaCode": "Kode KFA (PA)",
    "productTemplateName": "Nama produk varian",
    "nie": "Nomor ijin edar",
    "registrar": "Pemilik NIE",
    "manufacturer": "Pabrik",
    "madeOrigins": "Asal Produk",
    "productVariantCount": "Jumlah Varian"
}

# Sidebar Pengaturan
st.sidebar.header("⚙️ Konfigurasi Request")
batch_size = st.sidebar.slider("Jumlah Data Per Request (Size)", min_value=10, max_value=500, value=100, step=10)
max_pages = st.sidebar.number_input("Batas Maksimal Halaman (0 = Tanpa Batas)", min_value=0, value=0, step=1)
search_keyword = st.sidebar.text_input("Kata Kunci Pencarian (Biarkan kosong atau isi misal 'cath')", value="cath")

if "all_fetched_data" not in st.session_state:
    st.session_state["all_fetched_data"] = None

ALL_POSSIBLE_COLUMNS = [
    "Kode KFA (PA)",
    "Nama produk varian",
    "Nomor ijin edar",
    "Pemilik NIE",
    "Pabrik",
    "Asal Produk",
    "Jumlah Varian"
]

st.subheader("📌 Pilih Kolom yang Ingin Diunduh")
selected_columns = st.multiselect(
    "Silakan pilih atau sesuaikan kolom yang dibutuhkan:",
    options=ALL_POSSIBLE_COLUMNS,
    default=ALL_POSSIBLE_COLUMNS[:5]
)

st.divider()

start_download = st.button("🚀 Mulai Penarikan Data Produk Varian", type="primary")

if start_download:
    all_rows = []
    page = 1
    
    status_text = st.empty()
    table_placeholder = st.empty()

    while True:
        status_text.info(f"⏳ Sedang mengambil data Halaman **{page}** ({batch_size} item per request)...")
        
        payload = {
            "page": int(page),
            "size": int(batch_size),
            "search": search_keyword.strip() if search_keyword else "",
            "kfa_code": "",
            "bmhp": "",
            "made_origin": "",
            "manufacturer": "",
            "registrar": ""
        }
        
        try:
            response = requests.post(URL_SEARCH, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                res_json = response.json()
                items = res_json.get('items') or res_json.get('data') or []
                
                if not items:
                    status_text.success(f"✅ Penarikan data selesai! Total **{len(all_rows)}** data berhasil diambil.")
                    break
                    
                # Parsing dan pemetaan langsung
                for item in items:
                    row = {
                        "Kode KFA (PA)": item.get("kfaCode", ""),
                        "Nama produk varian": item.get("productTemplateName", ""),
                        "Nomor ijin edar": item.get("nie", ""),
                        "Pemilik NIE": item.get("registrar", ""),
                        "Pabrik": item.get("manufacturer", ""),
                        "Asal Produk": item.get("madeOrigins", ""),
                        "Jumlah Varian": item.get("productVariantCount", "")
                    }
                    all_rows.append(row)
                
                status_text.info(f"🔄 Halaman {page}: Berhasil mengambil **{len(items)}** data (Total Sementara: **{len(all_rows)}** data)")
                
                df_current = pd.DataFrame(all_rows)
                if selected_columns:
                    cols_to_show = [c for c in selected_columns if c in df_current.columns]
                    if cols_to_show:
                        df_current = df_current[cols_to_show]
                table_placeholder.dataframe(df_current.tail(10), use_container_width=True)
                
                if len(items) < batch_size:
                    status_text.success(f"✅ Mencapai akhir halaman. Total **{len(all_rows)}** data berhasil diambil.")
                    break
                    
                if max_pages > 0 and page >= max_pages:
                    status_text.warning(f"⚠️ Penarikan dihentikan sesuai batas halaman ({max_pages}). Total: **{len(all_rows)}** data.")
                    break
                    
                page += 1
            else:
                status_text.error(f"❌ HTTP Error {response.status_code} pada halaman {page}.")
                break
                
        except Exception as e:
            status_text.error(f"❌ Terjadi kesalahan koneksi: {str(e)}")
            break

    if all_rows:
        st.session_state["all_fetched_data"] = all_rows

if st.session_state["all_fetched_data"]:
    st.divider()
    st.subheader("📥 Download Hasil Data")
    
    df_final = pd.DataFrame(st.session_state["all_fetched_data"])
    
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
        st.metric(label="Total Baris Data", value=f"{len(df_final):,}")
        st.metric(label="Total Kolom Terpilih", value=f"{len(df_final.columns)}")
        
    st.subheader("👀 Preview Data Akhir (10 Baris Pertama)")
    st.dataframe(df_final.head(10), use_container_width=True)
