import streamlit as st
import requests
import json
import pandas as pd
import io

st.set_page_config(
    page_title="KFA Alkes Extractor",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 SATUSEHAT KFA Alkes Data Extractor")
st.markdown("Aplikasi ini menarik seluruh master data **Produk Varian Alat Kesehatan (KFA)** dari SATUSEHAT Kemenkes RI dan mengekspor hasilnya dalam format **TXT (pipe-separated `|`)**.")

# Sidebar Pengaturan
st.sidebar.header("⚙️ Konfigurasi Request")
batch_size = st.sidebar.slider("Jumlah Data Per Request (Size)", min_value=10, max_value=200, value=100, step=10)
max_pages = st.sidebar.number_input("Batas Maksimal Halaman (0 = Tanpa Batas)", min_value=0, value=0, step=1)
search_keyword = st.sidebar.text_input("Kata Kunci Pencarian (Biarkan kosong untuk semua data)", value="")

# Informasi API
col1, col2 = st.columns([1, 2])
with col1:
    st.subheader("📋 Informasi API")
    st.code("""Endpoint: 
https://satusehat.kemkes.go.id/kfa-browser/alkes/api/product-template/search-template

Method: POST
Separator: Pipe (|)
Format Output: TXT""", language="text")

start_download = st.button("🚀 Mulai Penarikan Data", type="primary")

if start_download:
    url = "https://satusehat.kemkes.go.id/kfa-browser/alkes/api/product-template/search-template"
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    all_data = []
    page = 1
    
    status_text = st.empty()
    table_placeholder = st.empty()

    while True:
        status_text.info(f"⏳ Sedang mengambil data Halaman **{page}**...")
        
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
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            
            if response.status_code == 200:
                res_json = response.json()
                items = res_json.get('items') or res_json.get('data') or []
                
                if not items:
                    status_text.success(f"✅ Penarikan data selesai! Total **{len(all_data)}** data berhasil diambil.")
                    break
                    
                all_data.extend(items)
                status_text.info(f"🔄 Berhasil mengambil **{len(items)}** item dari Halaman {page} (Total Sementara: **{len(all_data)}** data)")
                
                # Update preview tabel
                df_current = pd.DataFrame(all_data)
                table_placeholder.dataframe(df_current.tail(10), use_container_width=True)
                
                if len(items) < batch_size:
                    status_text.success(f"✅ Mencapai akhir halaman. Total **{len(all_data)}** data berhasil diambil.")
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
        st.divider()
        st.subheader("📥 Download Hasil Data")
        
        df_final = pd.DataFrame(all_data)
        
        # Format ke TXT dengan pipe separator
        buffer = io.StringIO()
        df_final.to_csv(buffer, sep="|", index=False, encoding="utf-8")
        txt_bytes = buffer.getvalue().encode("utf-8")
        
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                label="📄 Download File TXT (Separator |)",
                data=txt_bytes,
                file_name="kfa_alkes_data.txt",
                mime="text/plain",
                type="primary"
            )
        with col_dl2:
            st.metric(label="Total Baris Data Ditarik", value=f"{len(df_final):,}")
            
        st.subheader("👀 Preview Data (10 Baris Pertama)")
        st.dataframe(df_final.head(10), use_container_width=True)
