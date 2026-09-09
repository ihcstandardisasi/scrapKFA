import streamlit as st
import requests
import pandas as pd
import io

BASE_URL_OBAT = "https://satusehat.kemkes.go.id/kfa-browser/farmasi/api/detail/"

headers = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Origin": "https://satusehat.kemkes.go.id",
    "Referer": "https://satusehat.kemkes.go.id/kfa-browser/farmasi"
}

CATEGORIES = {
    "Produk Varian": {
        "endpoint": "product-variants",
        "all_cols": ["Kode KFA", "Nama Produk", "Merk Dagang", "Unit Logistik Terkecil", "Bentuk Sediaan", "Golongan Obat", "Nomor Izin Edar", "Fornas"],
        "default_cols": ["Kode KFA", "Nama Produk", "Merk Dagang", "Unit Logistik Terkecil", "Bentuk Sediaan", "Golongan Obat", "Nomor Izin Edar", "Fornas"],
        "parser": lambda item: {
            "Kode KFA": item.get("kfaCode", ""),
            "Nama Produk": item.get("name", ""),
            "Merk Dagang": item.get("tradeName", ""),
            "Unit Logistik Terkecil": item.get("uomName", ""),
            "Bentuk Sediaan": item.get("dosageFormName", ""),
            "Golongan Obat": item.get("farmalkesType", {}).get("name", "") if isinstance(item.get("farmalkesType"), dict) else "",
            "Nomor Izin Edar": item.get("nie", ""),
            "Fornas": "Ya" if item.get("isFornas") else "Tidak"
        }
    },
    "Produk Cangkang (Templates)": {
        "endpoint": "product-templates",
        "all_cols": ["Kode KFA", "Nama Produk Cangkang", "Total Varian", "Unit Logistik", "Golongan Obat", "Fornas"],
        "default_cols": ["Kode KFA", "Nama Produk Cangkang", "Total Varian", "Unit Logistik", "Golongan Obat", "Fornas"],
        "parser": lambda item: {
            "Kode KFA": item.get("kfaCode", ""),
            "Nama Produk Cangkang": item.get("name", ""),
            "Total Varian": item.get("totalVariants", 0),
            "Unit Logistik": item.get("uomName", ""),
            "Golongan Obat": item.get("farmalkesType", {}).get("name", "") if isinstance(item.get("farmalkesType"), dict) else "",
            "Fornas": "Ya" if item.get("isFornas") else "Tidak"
        }
    },
    "Kemasan Produk (Packagings)": {
        "endpoint": "product-packagings",
        "all_cols": ["Kode KFA Kemasan", "Nama Varian", "Nama Kemasan", "Qty", "Harga (HET/KFA)", "Satuan (UOM)", "Golongan Obat"],
        "default_cols": ["Kode KFA Kemasan", "Nama Varian", "Nama Kemasan", "Qty", "Harga (HET/KFA)", "Satuan (UOM)", "Golongan Obat"],
        "parser": lambda item: {
            "Kode KFA Kemasan": item.get("kfaCode", ""),
            "Nama Varian": item.get("variantDisplayName", ""),
            "Nama Kemasan": item.get("packageName", ""),
            "Qty": item.get("qty", 0),
            "Harga (HET/KFA)": item.get("price", 0),
            "Satuan (UOM)": item.get("uomName", ""),
            "Golongan Obat": item.get("farmalkesType", {}).get("name", "") if isinstance(item.get("farmalkesType"), dict) else ""
        }
    },
    "Zat Aktif (Active Ingredients)": {
        "endpoint": "active-ingredients",
        "all_cols": ["Kode KFA", "Nama Zat Aktif", "Satuan Dosis (UCUM)"],
        "default_cols": ["Kode KFA", "Nama Zat Aktif", "Satuan Dosis (UCUM)"],
        "parser": lambda item: {
            "Kode KFA": item.get("kfaCode", ""),
            "Nama Zat Aktif": item.get("name", ""),
            "Satuan Dosis (UCUM)": item.get("ucumSymbol", "")
        }
    }
}

def render_obat_page():
    st.header("💊 KFA Farmasi / Obat")
    
    selected_cat_name = st.radio(
        "Pilih Kategori Obat:",
        list(CATEGORIES.keys()),
        horizontal=True
    )
    
    config = CATEGORIES[selected_cat_name]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        batch_size = st.number_input("Jumlah Data Per Request (Size)", min_value=1, max_value=1000, value=100, step=10, key="obat_size")
    with col2:
        max_pages = st.number_input("Batas Maksimal Halaman (0 = Tanpa Batas)", min_value=0, value=0, step=1, key="obat_pages")
    with col3:
        search_keyword = st.text_input("Kata Kunci Pencarian", value="paracetamol", key="obat_keyword")
        
    selected_cols = st.multiselect("Pilih Kolom:", config["all_cols"], default=config["default_cols"], key="obat_cols")
    
    if st.button(f"🚀 Mulai Penarikan Data {selected_cat_name}", type="primary"):
        active_search = search_keyword.strip()
        if not active_search:
            active_search = "paracetamol"
            st.info("ℹ️ Kata kunci kosong, menggunakan default kata kunci: **'paracetamol'**.")

        all_rows = []
        page = 1
        status = st.empty()
        table_p = st.empty()
        
        target_url = f"{BASE_URL_OBAT}{config['endpoint']}"
        
        while True:
            status.info(f"⏳ Mengambil Data dengan Kata Kunci: **'{active_search}'** | Halaman **{page}** ({batch_size} item/request)...")
            
            # Payload disesuaikan dengan format camelCase resmi backend KFA Farmasi
            payload = {
                "page": int(page),
                "size": int(batch_size),
                "search": str(active_search),
                "search_by": "name",
                "kfaCode": "",
                "farmalkesType": "",
                "registrar": "",
                "manufacturer": "",
                "madeOrigin": "",
                "productTemplateId": ""
            }
            
            try:
                resp = requests.post(target_url, headers=headers, json=payload, timeout=30)
                if resp.status_code == 200:
                    res_json = resp.json()
                    
                    items = res_json.get("data", [])
                    if isinstance(items, dict):
                        items = items.get("data", [])
                    
                    if not items:
                        status.success(f"✅ Penarikan Selesai! Total **{len(all_rows)}** data terambil.")
                        break
                        
                    for item in items:
                        all_rows.append(config["parser"](item))
                        
                    status.info(f"🔄 Halaman {page}: +{len(items)} items (Total Sementara: {len(all_rows)})")
                    df_curr = pd.DataFrame(all_rows)
                    valid_c = [c for c in selected_cols if c in df_curr.columns]
                    if valid_c:
                        table_p.dataframe(df_curr[valid_c].tail(10), use_container_width=True)
                    
                    if len(items) < batch_size or (max_pages > 0 and page >= max_pages):
                        status.success(f"✅ Penarikan Selesai! Total **{len(all_rows)}** data terambil.")
                        break
                    page += 1
                else:
                    error_msg = ""
                    try:
                        error_msg = resp.json().get("message") or resp.text
                    except:
                        error_msg = resp.text
                    status.error(f"❌ HTTP Error {resp.status_code} pada halaman {page}. Detail Server: {error_msg}")
                    break
            except Exception as e:
                status.error(f"❌ Error Koneksi: {str(e)}")
                break
                
        if all_rows:
            _render_download(pd.DataFrame(all_rows), selected_cols, f"kfa_obat_{config['endpoint']}.txt")

def _render_download(df, cols, filename):
    st.divider()
    valid_cols = [c for c in cols if c in df.columns]
    if valid_cols:
        df = df[valid_cols]
    
    buf = io.StringIO()
    df.to_csv(buf, sep="|", index=False, encoding="utf-8")
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📄 Download File TXT (Separator |)", data=buf.getvalue().encode("utf-8"), file_name=filename, mime="text/plain", type="primary")
    with col2:
        st.metric("Total Baris Data", f"{len(df):,}")
    st.dataframe(df.head(10), use_container_width=True)
