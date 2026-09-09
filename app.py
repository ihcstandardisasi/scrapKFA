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
search_keyword = st.sidebar.text_input("Kata Kunci Pencarian (Biarkan kosong atau isi misal 'cath')", value="cath")

if "all_fetched_data" not in st.session_state:
    st.session_state["all_fetched_data"] = None

# Fungsi penarik nilai fleksibel dari dictionary
def extract_value(d, keys):
    if not isinstance(d, dict):
        return ""
    for k in keys:
        if k in d and d[k]:
            val = d[k]
            if isinstance(val, str):
                return val.strip()
            elif isinstance(val, dict):
                return val.get("name") or val.get("title") or str(val)
            elif isinstance(val, list) and len(val) > 0:
                first = val[0]
                if isinstance(first, dict):
                    return first.get("name") or first.get("title") or str(first)
                return str(first)
            return str(val)
    return ""

def fetch_template_detail(template_id):
    try:
        url = f"{URL_DETAIL}?id={template_id}"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None

def parse_item_to_rows(item):
    rows = []
    if not isinstance(item, dict):
        return rows
        
    # Ambil Kode KFA
    kfa_code = extract_value(item, ["kfa_code", "kfaCode", "code", "id"])
    template_name = extract_value(item, ["name", "product_template_name", "template_name"])
    
    # Cari list varian
    variants = item.get("product_variants") or item.get("variants") or item.get("items") or []
    
    if isinstance(variants, list) and len(variants) > 0:
        for v in variants:
            var_dict = v if isinstance(v, dict) else {}
            row = {
                "Kode KFA (PA)": kfa_code,
                "Nama produk varian": extract_value(var_dict, ["name", "product_variant_name", "variant_name"]) or template_name,
                "Nomor ijin edar": extract_value(var_dict, ["nie", "nie_number", "no_nie"]) or extract_value(item, ["nie", "nie_number", "no_nie"]),
                "Pemilik NIE": extract_value(var_dict, ["registrar", "registrar_name", "pemilik_nie"]) or extract_value(item, ["registrar", "registrar_name", "pemilik_nie"]),
                "Pabrik": extract_value(var_dict, ["manufacturer", "manufacturer_name", "pabrik"]) or extract_value(item, ["manufacturer", "manufacturer_name", "pabrik"]),
                "BMHP": extract_value(var_dict, ["bmhp"]) or extract_value(item, ["bmhp"]),
                "Asal Produk": extract_value(var_dict, ["made_origin", "madeOrigin"]) or extract_value(item, ["made_origin", "madeOrigin"])
            }
            rows.append(row)
    else:
        row = {
            "Kode KFA (PA)": kfa_code,
            "Nama produk varian": template_name,
            "Nomor ijin edar": extract_value(item, ["nie", "nie_number", "no_nie"]),
            "Pemilik NIE": extract_value(item, ["registrar", "registrar_name", "pemilik_nie"]),
            "Pabrik": extract_value(item, ["manufacturer", "manufacturer_name", "pabrik"]),
            "BMHP": extract_value(item, ["bmhp"]),
            "Asal Produk": extract_value(item, ["made_origin", "madeOrigin"])
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
        status_text.info(f"⏳ Mengambil daftar Halaman **{page}** ({batch_size} item per request)...")
        
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
                    status_text.success(f"✅ Penarikan data selesai! Total **{len(all_rows)}** data varian berhasil diambil.")
                    break
                    
                page_rows = []
                for idx, item in enumerate(raw_items):
                    item_id = item.get("id") or item.get("product_template_id")
                    status_text.info(f"⏳ Halaman **{page}** | Mengambil detail item {idx+1}/{len(raw_items)}...")
                    
                    detail = None
                    if item_id:
                        detail = fetch_template_detail(item_id)
                    
                    # Gunakan detail jika ada, jika tidak fallback ke item utama
                    target_item = detail if detail else item
                    rows = parse_item_to_rows(target_item)
                    page_rows.extend(rows)
                
                all_rows.extend(page_rows)
                status_text.info(f"🔄 Halaman {page}: Berhasil mengekstrak **{len(page_rows)}** baris varian (Total: **{len(all_rows)}** data)")
                
                df_current = pd.DataFrame(all_rows)
                if selected_columns:
                    cols_to_show = [c for c in selected_columns if c in df_current.columns]
                    if cols_to_show:
                        df_current = df_current[cols_to_show]
                table_placeholder.dataframe(df_current.tail(10), use_container_width=True)
                
                if len(raw_items) < batch_size:
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
