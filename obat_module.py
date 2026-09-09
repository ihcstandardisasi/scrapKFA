import streamlit as st
import requests
import pandas as pd
import io
import string

BASE_URL_OBAT = "https://satusehat.kemkes.go.id/kfa-browser/farmasi/api/detail/"

# Header browser lengkap untuk lolos dari proteksi API Gateway Kemenkes
headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Origin": "https://satusehat.kemkes.go.id",
    "Referer": "https://satusehat.kemkes.go.id/kfa-browser/farmasi",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin"
}

# 105 Kombinasi Suku Kata (Konsonan + Vokal + '9')
VOWELS = ['a', 'i', 'u', 'e', 'o']
CONSONANTS = [c for c in string.ascii_lowercase if c not in VOWELS]
OBAT_SWEEP_PREFIXES = [f"{c}{v}9" for c in CONSONANTS for v in VOWELS]

CATEGORIES = {
    "Produk Varian": {
        "endpoint": "product-variants",
        "key_id": "Kode KFA",
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
        "key_id": "Kode KFA",
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
        "key_id": "Kode KFA Kemasan",
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
        "key_id": "Kode KFA",
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
        max_pages = st.number_input("Batas Halaman Per Kata Kunci (0 = Tanpa Batas)", min_value=0, value=0, step=1, key="obat_pages")
    with col3:
        search_keyword = st.text_input("Kata Kunci Pencarian (Kosongkan untuk Auto-Sweep 105 Suku Kata 'xx9')", value="", key="obat_keyword")
        
    selected_cols = st.multiselect("Pilih Kolom:", config["all_cols"], default=config["default_cols"], key="obat_cols")
    
    if st.button(f"🚀 Mulai Penarikan Data {selected_cat_name}", type="primary"):
        kw_clean = search_keyword.strip()
        
        if kw_clean:
            keywords_to_process = [kw_clean]
        else:
            keywords_to_process = OBAT_SWEEP_PREFIXES
            st.toast("⚡ Menjalankan Auto-Sweep presisi Obat (105 Kombinasi 'xx9')...", icon="⚡")

        all_rows = []
        seen_ids = set()
        status = st.empty()
        table_p = st.empty()
        
        target_url = f"{BASE_URL_OBAT}{config['endpoint']}"
        total_kw = len(keywords_to_process)
        
        for idx, kw in enumerate(keywords_to_process, start=1):
            page = 1
            while True:
                status.info(f"⏳ Progress: **[{idx}/{total_kw}]** | Kata Kunci: **'{kw}'** | Halaman **{page}** | Total Unik: **{len(all_rows):,}**")
                
                payload = {
                    "page": int(page),
                    "size": int(batch_size),
                    "search": str(kw),
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
                            break
                            
                        recent_added = []
                        for item in items:
                            parsed_item = config["parser"](item)
                            unique_key = parsed_item.get(config["key_id"]) or str(parsed_item)
                            
                            if unique_key and unique_key in seen_ids:
                                continue
                            if unique_key:
                                seen_ids.add(unique_key)

                            all_rows.append(parsed_item)
                            recent_added.append(parsed_item)
                            
                        if recent_added:
                            df_preview = pd.DataFrame(recent_added)
                            valid_c = [c for c in selected_cols if c in df_preview.columns]
                            if valid_c:
                                table_p.dataframe(df_preview[valid_c].tail(10), use_container_width=True)
                        
                        if len(items) < batch_size or (max_pages > 0 and page >= max_pages):
                            break
                        page += 1
                    else:
                        break
                except Exception as e:
                    status.error(f"❌ Error pada kata kunci '{kw}': {str(e)}")
                    break
                    
        if all_rows:
            status.success(f"✅ Penarikan Selesai! Total **{len(all_rows):,}** data obat unik berhasil dikumpulkan.")
            _render_download(pd.DataFrame(all_rows), selected_cols, f"kfa_obat_{config['endpoint']}.txt")
        else:
            status.error("❌ Tidak ada data yang berhasil diambil.")

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
        st.metric("Total Baris Data Unik", f"{len(df):,}")
    st.dataframe(df.head(10), use_container_width=True)
