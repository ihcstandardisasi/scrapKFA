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
st.markdown("Aplikasi ini menarik master data **Produk Varian Alat Kesehatan (KFA)** secara lengkap dari SATUSEHAT Kemenkes RI.")

# Endpoint Utama
URL_SEARCH = "https://satusehat.kemkes.go.id/kfa-browser/alkes/api/product-template/search-template"
URL_DETAIL = "https://satusehat.kemkes.go.id/kfa-browser/alkes/api/product-template/get-template-by-id"

headers = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Origin": "https://satusehat.kemkes.go.id",
    "Referer": "https://satusehat.kemkes.go.id/kfa-browser/alkes"
}

# Sidebar Pengaturan
st.sidebar.header("⚙️ Konfigurasi Request")
batch_size = st.sidebar.slider("Jumlah Data Per Request (Size)", min_value=10, max_value=100, value=50, step=10)
max_pages = st.sidebar.number_input("Batas Maksimal Halaman (0 = Tanpa Batas)", min_value=0, value=0, step=1)
search_keyword = st.sidebar.text_input("Kata Kunci Pencarian (Ketikan 'cath' atau kosongkan)", value="cath")

if "all_fetched_data" not in st.session_state:
    st.session_state["all_fetched_data"] = None

# Fungsi untuk mengambil detail varian berdasarkan ID Template
def fetch_template_detail(template_id):
    try:
        url = f"{URL_DETAIL}?id={template_id}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

# Fungsi parsing respons menjadi baris-baris varian lengkap
def parse_details_to_rows(details_list):
    rows = []
    for item in details_list:
        if not item:
            continue
            
        kfa_code = item.get("kfa_code") or item.get("kfaCode") or ""
        template_name = item.get("name") or item.get("product_template_name") or ""
        
        variants = item.get("product_variants") or item.get("variants") or []
        
        if variants:
            for v in variants:
                row = {
                    "Kode KFA (PA)": kfa_code,
                    "Nama produk varian": v.get("name") or v.get("product_variant_name") or template_name,
                    "Nomor ijin edar": v.get("nie") or item.get("nie") or "",
                    "Pemilik NIE": v.get("registrar") or v.get("registrar_name") or item.get("registrar") or "",
                    "Pabrik": v.get("manufacturer") or v.get("manufacturer_name") or item.get("manufacturer") or "",
                    "BMHP": v.get("bmhp") or item.get("bmhp") or "",
                    "Asal Produk": v.get("made_origin") or item.get("made_origin") or ""
                }
                rows.append(row)
        else:
            # Fallback jika tidak ada turunan array varian
            row = {
                "Kode KFA (PA)": kfa_code,
                "Nama produk varian": template_name,
                "Nomor ijin edar": item.get("nie") or "",
                "Pemilik NIE": item.get("registrar") or "",
                "Pabrik": item.get("manufacturer") or "",
                "BMHP": item.get("bmhp") or "",
                "Asal Produk": item.get("made_origin") or ""
            }
            rows.append(row)
            
    return rows

ALL_POSSIBLE_COLUMNS = [
    "Kode KFA (PA)",
    "Nama produk varian",
    "Nomor ijin edar",
    "Pemilik NIE",
    "Pabrik",
    "BMHP",
    "Asal Produk"
]

st.subheader("📌 Pilih Kolom yang Ingin Diunduh")
selected_columns = st.multiselect(
    "Silakan pilih atau sesuaikan kolom yang dibutuhkan:",
    options=ALL_POSSIBLE_COLUMNS,
    default=ALL_POSSIBLE_COLUMNS[:5]
)

st.divider()

start_download = st.button("🚀 Mulai Penarikan Data Produk Varian Lengkap", type="primary")

if start_download:
    all_rows = []
    page = 1
    
    status_text = st.empty()
    table_placeholder = st.empty()

    while True:
        status_text.info(f"⏳ Sedang mengambil daftar ID Halaman **{page}** ({batch_size} item per request)...")
        
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
                raw_items = res_json.get('items') or res_json.get('data') or []
                
                if not raw_items:
                    status_text.success(f"✅ Penarikan data selesai! Total **{len(all_rows)}** baris varian berhasil diambil.")
                    break
                    
                # Tahap 2: Fetch detail untuk setiap ID
                fetched_details = []
                for idx, item in enumerate(raw_items):
                    item_id = item.get("id") or item.get("product_template_id")
                    status_text.info(f"⏳ Halaman **{page}** | Mengambil detail varian {idx+1}/{len(raw_items)}...")
                    
                    if item_id:
                        detail_data = fetch_template_detail(item_id)
                        if detail_data:
                            fetched_details.append(detail_data)
                        else:
                            fetched_details.append(item)
                    else:
                        fetched_details.append(item)
                
                # Parsing detail menjadi baris lengkap
                page_rows = parse_details_to_rows(fetched_details)
                all_rows.extend(page_rows)
                
                status_text.info(f"🔄 Halaman {page}: Berhasil mengekstrak **{len(page_rows)}** varian lengkap (Total: **{len(all_rows)}** data)")
                
                df_current = pd.DataFrame(all_rows)
                if selected_columns:
                    cols_to_show = [c for c in selected_columns if c in df_current.columns]
                    if cols_to_show:
                        df_current = df_current[cols_to_show]
                table_placeholder.dataframe(df_current.tail(10), use_container_width=True)
                
                if len(raw_items) < batch_size:
                    status_text.success(f"✅ Mencapai akhir halaman. Total **{len(all_rows)}** baris varian berhasil diambil.")
                    break
                    
                if max_pages > 0 and page >= max_pages:
                    status_text.warning(f"⚠️ Penarikan dihentikan karena mencapai batas halaman ({max_pages}). Total: **{len(all_rows)}** data.")
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
