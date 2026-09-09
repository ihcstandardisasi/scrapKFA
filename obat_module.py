import streamlit as st
import requests
import pandas as pd
import io
import string

# URL Base API Pencarian Resmi KFA Farmasi (Bukan /detail/)
URL_VARIANT = "https://satusehat.kemkes.go.id/kfa-browser/farmasi/api/product-variant/search-variant"
URL_TEMPLATE = "https://satusehat.kemkes.go.id/kfa-browser/farmasi/api/product-template/search-template"
URL_PACKAGING = "https://satusehat.kemkes.go.id/kfa-browser/farmasi/api/product-packaging/search-packaging"
URL_INGREDIENT = "https://satusehat.kemkes.go.id/kfa-browser/farmasi/api/active-ingredient/search-active-ingredient"

headers = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Origin": "https://satusehat.kemkes.go.id",
    "Referer": "https://satusehat.kemkes.go.id/kfa-browser/farmasi"
}

# 105 Kombinasi Suku Kata (Konsonan + Vokal + '9')
VOWELS = ['a', 'i', 'u', 'e', 'o']
CONSONANTS = [c for c in string.ascii_lowercase if c not in VOWELS]
OBAT_SWEEP_PREFIXES = [f"{c}{v}9" for c in CONSONANTS for v in VOWELS]

CATEGORIES = {
    "Produk Varian": {
        "url": URL_VARIANT,
        "key_id": "Kode KFA",
        "all_cols": ["Kode KFA", "Nama Produk", "Merk Dagang", "Unit Logistik Terkecil", "Bentuk Sediaan", "Golongan Obat", "Nomor Izin Edar", "Fornas"],
        "default_cols": ["Kode KFA", "Nama Produk", "Merk Dagang", "Unit Logistik Terkecil", "Bentuk Sediaan", "Golongan Obat", "Nomor Izin Edar", "Fornas"],
        "parser": lambda item: {
            "Kode KFA": item.get("kfa_code") or item.get("kfaCode") or "",
            "Nama Produk": item.get("product_variant_name") or item.get("name") or "",
            "Merk Dagang": item.get("trade_name") or item.get("tradeName") or "",
            "Unit Logistik Terkecil": item.get("uom_name") or item.get("uomName") or "",
            "Bentuk Sediaan": item.get("dosage_form_name") or item.get("dosageFormName") or "",
            "Golongan Obat": item.get("farmalkes_type") or item.get("farmalkesType") or "",
            "Nomor Izin Edar": item.get("nie") or "",
            "Fornas": "Ya" if item.get("is_fornas") or item.get("isFornas") else "Tidak"
        }
    },
    "Produk Cangkang (Templates)": {
        "url": URL_TEMPLATE,
        "key_id": "Kode KFA",
        "all_cols": ["Kode KFA", "Nama Produk Cangkang", "Total Varian", "Unit Logistik"],
        "default_cols": ["Kode KFA", "Nama Produk Cangkang", "Total Varian", "Unit Logistik"],
        "parser": lambda item: {
            "Kode KFA": item.get("kfa_code") or item.get("kfaCode") or "",
            "Nama Produk Cangkang": item.get("product_template_name") or item.get("name") or "",
            "Total Varian": item.get("total_variants") or item.get("totalVariants") or 0,
            "Unit Logistik": item.get("uom_name") or item.get("uomName") or ""
        }
    },
    "Kemasan Produk (Packagings)": {
        "url": URL_PACKAGING,
        "key_id": "Kode KFA Kemasan",
        "all_cols": ["Kode KFA Kemasan", "Nama Varian", "Nama Kemasan", "Qty", "Harga (HET/KFA)", "Satuan (UOM)"],
        "default_cols": ["Kode KFA Kemasan", "Nama Varian", "Nama Kemasan", "Qty", "Harga (HET/KFA)", "Satuan (UOM)"],
        "parser": lambda item: {
            "Kode KFA Kemasan": item.get("kfa_code") or item.get("kfaCode") or "",
            "Nama Varian": item.get("variant_display_name") or item.get("variantDisplayName") or "",
            "Nama Kemasan": item.get("package_name") or item.get("packageName") or "",
            "Qty": item.get("qty", 0),
            "Harga (HET/KFA)": item.get("price", 0),
            "Satuan (UOM)": item.get("uom_name") or item.get("uomName") or ""
        }
    },
    "Zat Aktif (Active Ingredients)": {
        "url": URL_INGREDIENT,
        "key_id": "Kode KFA",
        "all_cols": ["Kode KFA", "Nama Zat Aktif", "Satuan Dosis (UCUM)"],
        "default_cols": ["Kode KFA", "Nama Zat Aktif", "Satuan Dosis (UCUM)"],
        "parser": lambda item: {
            "Kode KFA": item.get("kfa_code") or item.get("kfaCode") or "",
            "Nama Zat Aktif": item.get("name", ""),
            "Satuan Dosis (UCUM)": item.get("ucum_symbol") or item.get("ucumSymbol") or ""
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
        search_keyword = st.text_input("Kata Kunci Pencarian (Kosongkan untuk Auto-Sweep 'xx9')", value="", key="obat_keyword")
        
    selected_cols = st.multiselect("Pilih Kolom:", config["all_cols"], default=config["default_cols"], key="obat_cols")
    
    if st.button(f"🚀 Mulai Penarikan Data {selected_cat_name}", type="primary"):
        kw_clean = search_keyword.strip()
        keywords_to_process = [kw_clean] if kw_clean else OBAT_SWEEP_PREFIXES
        
        if not kw_clean:
            st.toast("⚡ Menjalankan Auto-Sweep 105 Suku Kata KFA Obat...", icon="⚡")

        all_rows = []
        seen_ids = set()
        status = st.empty()
        table_p = st.empty()
        
        target_url = config["url"]
        total_kw = len(keywords_to_process)

        for idx, kw in enumerate(keywords_to_process, start=1):
            page = 1
            while True:
                status.info(f"⏳ Progress: **[{idx}/{total_kw}]** | Kata Kunci: **'{kw}'** | Halaman **{page}** | Total Unik: **{len(all_rows):,}**")
                
                payload = {
                    "page": int(page),
                    "size": int(batch_size),
                    "search": str(kw),
                    "kfa_code": "",
                    "farmalkes_type": "",
                    "made_origin": "",
                    "manufacturer": "",
                    "registrar": ""
                }
                
                try:
                    resp = requests.post(target_url, headers=headers, json=payload, timeout=30)
                    
                    if resp.status_code == 200:
                        res_json = resp.json()
                        items = res_json.get('items') or res_json.get('data') or []
                        if isinstance(items, dict):
                            items = items.get('items') or items.get('data') or []

                        if not items:
                            break
                            
                        recent_added = []
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                                
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
                        status.error(f"❌ Error HTTP {resp.status_code}: {resp.text[:200]}")
                        break
                except Exception as e:
                    status.error(f"❌ Error Koneksi: {str(e)}")
                    break
                    
        if all_rows:
            status.success(f"✅ Penarikan Selesai! Total **{len(all_rows):,}** data obat unik berhasil dikumpulkan.")
            _render_download(pd.DataFrame(all_rows), selected_cols, f"kfa_obat_{selected_cat_name}.txt")
        else:
            status.error("❌ Tidak ada data terambil.")

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
