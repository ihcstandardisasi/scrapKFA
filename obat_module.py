import streamlit as st
import pandas as pd
import io
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

BASE_URL_FARMASI = "https://satusehat.kemkes.go.id/kfa-browser/farmasi"

# 105 Suku Kata Konsonan + Vokal + '9'
VOWELS = ['a', 'i', 'u', 'e', 'o']
CONSONANTS = ['b', 'c', 'd', 'f', 'g', 'h', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 'r', 's', 't', 'v', 'w', 'x', 'y', 'z']
OBAT_SWEEP_PREFIXES = [f"{c}{v}9" for c in CONSONANTS for v in VOWELS]

CATEGORIES = {
    "Produk Varian": "product-variants",
    "Produk Cangkang (Templates)": "product-templates",
    "Kemasan Produk (Packagings)": "product-packagings",
    "Zat Aktif (Active Ingredients)": "active-ingredients"
}

def render_obat_page():
    st.header("💊 KFA Farmasi / Obat (Selenium Driver Engine)")
    
    selected_cat_name = st.radio(
        "Pilih Kategori Obat:",
        list(CATEGORIES.keys()),
        horizontal=True
    )
    
    col1, col2 = st.columns(2)
    with col1:
        search_keyword = st.text_input("Kata Kunci Pencarian (Kosongkan untuk Auto-Sweep 105 Suku Kata 'xx9')", value="", key="obat_keyword")
    with col2:
        max_items = st.number_input("Batas Maksimal Item Data (0 = Tanpa Batas)", min_value=0, value=0, step=100)

    if st.button(f"🚀 Mulai Penarikan Data Obat", type="primary"):
        kw_clean = search_keyword.strip()
        keywords_to_process = [kw_clean] if kw_clean else OBAT_SWEEP_PREFIXES
        
        status = st.empty()
        table_p = st.empty()
        
        all_rows = []
        seen_ids = set()
        
        status.info("⏳ Memulai Headless Browser (Chrome)...")
        
        # Setup Chrome Options
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.get(BASE_URL_FARMASI)
            time.sleep(3)
            
            total_kw = len(keywords_to_process)
            
            for idx, kw in enumerate(keywords_to_process, start=1):
                status.info(f"⏳ Progress: **[{idx}/{total_kw}]** | Kata Kunci: **'{kw}'** | Total Data Unik: **{len(all_rows):,}**")
                
                try:
                    # Cari input field pencarian
                    search_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search' or @type='text']"))
                    )
                    search_box.clear()
                    search_box.send_keys(kw)
                    
                    # Klik tombol Search
                    search_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Search') or @type='submit']")
                    search_btn.click()
                    
                    time.sleep(2.5) # Tunggu rendering tabel
                    
                    # Ambil baris tabel
                    rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
                    
                    recent_added = []
                    for row in rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 2:
                            kfa_code = cols[0].text.strip()
                            name_val = cols[1].text.strip()
                            
                            if kfa_code and kfa_code not in seen_ids:
                                seen_ids.add(kfa_code)
                                item_dict = {
                                    "Kode KFA": kfa_code,
                                    "Nama Obat / Produk": name_val,
                                    "Kategori": selected_cat_name,
                                    "Kata Kunci Match": kw
                                }
                                all_rows.append(item_dict)
                                recent_added.append(item_dict)
                    
                    if recent_added:
                        table_p.dataframe(pd.DataFrame(recent_added).tail(10), use_container_width=True)
                        
                    if max_items > 0 and len(all_rows) >= max_items:
                        break
                        
                except Exception as e:
                    continue
                    
            driver.quit()
            
            if all_rows:
                status.success(f"✅ Penarikan Selesai! Total **{len(all_rows):,}** data obat berhasil didapatkan.")
                _render_download(pd.DataFrame(all_rows), "kfa_obat_extracted.txt")
            else:
                status.error("❌ Gagal mengekstrak data dari tabel browser.")
                
        except Exception as e:
            status.error(f"❌ Error Driver Browser: {str(e)}")

def _render_download(df, filename):
    st.divider()
    buf = io.StringIO()
    df.to_csv(buf, sep="|", index=False, encoding="utf-8")
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📄 Download File TXT (Separator |)", data=buf.getvalue().encode("utf-8"), file_name=filename, mime="text/plain", type="primary")
    with col2:
        st.metric("Total Baris Data Unik", f"{len(df):,}")
    st.dataframe(df.head(10), use_container_width=True)
