import streamlit as st
import requests
import pandas as pd
import io
import string

URL_VARIANT = "https://satusehat.kemkes.go.id/kfa-browser/alkes/api/product-variant/search-variant"
URL_TEMPLATE = "https://satusehat.kemkes.go.id/kfa-browser/alkes/api/product-template/search-template"

headers = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Origin": "https://satusehat.kemkes.go.id",
    "Referer": "https://satusehat.kemkes.go.id/kfa-browser/alkes"
}

# Definisi Konsonan & Vokal
VOWELS = ['a', 'i', 'u', 'e', 'o']
CONSONANTS = [c for c in string.ascii_lowercase if c not in VOWELS]

# Menghasilkan 105 kombinasi (konsonan + vokal + '9') -> ba9, ca9, da9 ... zo9
ALKES_SWEEP_PREFIXES = [f"{c}{v}9" for c in CONSONANTS for v in VOWELS]

def render_alkes_page():
    st.header("🏥 KFA Alat Kesehatan (Alkes)")
    
    sub_menu = st.radio(
        "Pilih Sub-Kategori Alkes:",
        ["Produk Varian Alkes", "Produk Cangkang Alkes"],
        horizontal=True
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        batch_size = st.number_input("Jumlah Data Per Request (Size)", min_value=1, max_value=1000, value=100, step=10, key="alkes_size")
    with col2:
        max_pages = st.number_input("Batas Halaman Per Kata Kunci (0 = Tanpa Batas)", min_value=0, value=0, step=1, key="alkes_pages")
    with col3:
        search_keyword = st.text_input("Kata Kunci Pencarian (Kosongkan untuk Auto-Sweep 105 Suku Kata)", value="", key="alkes_keyword")

    if sub_menu == "Produk Varian Alkes":
        _fetch_alkes_variant(batch_size, max_pages, search_keyword)
    else:
        _fetch_alkes_template(batch_size, max_pages, search_keyword)

def _fetch_alkes_variant(batch_size, max_pages, search_keyword):
    ALL_COLUMNS = ["Kode KFA (PA)", "Nama produk varian", "Nomor ijin edar", "Pemilik NIE", "Pabrik", "Asal Produk"]
    selected_cols = st.multiselect("Pilih Kolom:", ALL_COLUMNS, default=ALL_COLUMNS[:5], key="alkes_var_cols")
    
    if st.button("🚀 Mulai Penarikan Varian Alkes", type="primary"):
        kw_clean = search_keyword.strip()
        
        if kw_clean:
            keywords_to_process = [kw_clean]
        else:
            keywords_to_process = ALKES_SWEEP_PREFIXES
            st.toast("⚡ Menjalankan Auto-Sweep presisi (105 Kombinasi Konsonan-Vokal+9)...", icon="⚡")

        all_rows = []
        seen_ids = set()
        status = st.empty()
        table_p = st.empty()
        
        for kw in keywords_to_process:
            page = 1
            while True:
                status.info(f"⏳ Kata Kunci: **'{kw}'** | Halaman **{page}** ({batch_size} item/request)...")
                payload = {
                    "page": int(page), "size": int(batch_size),
                    "search": kw,
                    "kfa_code": "", "bmhp": "", "made_origin": "", "manufacturer": "", "registrar": "", "product_template_id": ""
                }
                try:
                    resp = requests.post(URL_VARIANT, headers=headers, json=payload, timeout=30)
                    if resp.status_code == 200:
                        items = resp.json().get('items') or resp.json().get('data') or []
                        if isinstance(items, dict): items = items.get('items') or items.get('data') or []
                        
                        if not items:
                            break
                            
                        added_count = 0
                        for item in items:
                            kfa_code = item.get("kfa_code") or item.get("kfaCode") or item.get("code") or ""
                            
                            if kfa_code and kfa_code in seen_ids:
                                continue
                            if kfa_code:
                                seen_ids.add(kfa_code)

                            variant_name = (
                                item.get("product_variant_name") 
                                or item.get("productVariantName") 
                                or item.get("name") 
                                or item.get("product_template_name")
                                or item.get("productTemplateName")
                                or ""
                            )
                            reg = item.get("registrar") or item.get("registrar_name") or ""
                            man = item.get("manufacturer") or item.get("manufacturer_name") or ""
                            
                            all_rows.append({
                                "Kode KFA (PA)": kfa_code,
                                "Nama produk varian": variant_name,
                                "Nomor ijin edar": item.get("nie") or item.get("nie_number") or "",
                                "Pemilik NIE": reg.get("name") if isinstance(reg, dict) else str(reg),
                                "Pabrik": man.get("name") if isinstance(man, dict) else str(man),
                                "Asal Produk": item.get("made_origin") or item.get("madeOrigins") or ""
                            })
                            added_count += 1
                        
                        status.info(f"🔄 Kata Kunci **'{kw}'** | Halaman {page}: +{added_count} data baru (Total Unik: {len(all_rows)})")
                        df_curr = pd.DataFrame(all_rows)
                        valid_c = [c for c in selected_cols if c in df_curr.columns]
                        if valid_c and not df_curr.empty:
                            table_p.dataframe(df_curr[valid_c].tail(10), use_container_width=True)
                        
                        if len(items) < batch_size or (max_pages > 0 and page >= max_pages):
                            break
                        page += 1
                    else:
                        break
                except Exception as e:
                    status.error(f"❌ Error: {str(e)}")
                    break
                
        if all_rows:
            status.success(f"✅ Penarikan Selesai! Total **{len(all_rows)}** data varian unik berhasil dikumpulkan.")
            _render_download(pd.DataFrame(all_rows), selected_cols, "kfa_alkes_variant.txt")

def _fetch_alkes_template(batch_size, max_pages, search_keyword):
    selected_cols = ["Kode KFA", "Nama produk cangkang"]
    
    if st.button("🚀 Mulai Penarikan Cangkang Alkes", type="primary"):
        kw_clean = search_keyword.strip()
        
        if kw_clean:
            keywords_to_process = [kw_clean]
        else:
            keywords_to_process = ALKES_SWEEP_PREFIXES
            st.toast("⚡ Menjalankan Auto-Sweep presisi (105 Kombinasi Konsonan-Vokal+9)...", icon="⚡")

        all_rows = []
        seen_ids = set()
        status = st.empty()
        table_p = st.empty()
        
        for kw in keywords_to_process:
            page = 1
            while True:
                status.info(f"⏳ Kata Kunci: **'{kw}'** | Halaman **{page}** ({batch_size} item/request)...")
                payload = {
                    "page": int(page), "size": int(batch_size),
                    "search": kw,
                    "kfa_code": "", "bmhp": "", "made_origin": "", "manufacturer": "", "registrar": ""
                }
                try:
                    resp = requests.post(URL_TEMPLATE, headers=headers, json=payload, timeout=30)
                    if resp.status_code == 200:
                        items = resp.json().get('items') or resp.json().get('data') or []
                        if not items:
                            break
                            
                        added_count = 0
                        for item in items:
                            kfa_code = item.get("kfaCode") or item.get("kfa_code") or ""
                            if kfa_code and kfa_code in seen_ids:
                                continue
                            if kfa_code:
                                seen_ids.add(kfa_code)

                            all_rows.append({
                                "Kode KFA": kfa_code,
                                "Nama produk cangkang": item.get("productTemplateName") or item.get("name") or ""
                            })
                            added_count += 1
                            
                        status.info(f"🔄 Kata Kunci **'{kw}'** | Halaman {page}: +{added_count} data baru (Total Unik: {len(all_rows)})")
                        df_curr = pd.DataFrame(all_rows)
                        if not df_curr.empty:
                            table_p.dataframe(df_curr.tail(10), use_container_width=True)
                        
                        if len(items) < batch_size or (max_pages > 0 and page >= max_pages):
                            break
                        page += 1
                    else:
                        break
                except Exception as e:
                    status.error(f"❌ Error: {str(e)}")
                    break
                
        if all_rows:
            status.success(f"✅ Penarikan Selesai! Total **{len(all_rows)}** data cangkang unik berhasil dikumpulkan.")
            _render_download(pd.DataFrame(all_rows), selected_cols, "kfa_alkes_cangkang.txt")

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
