import streamlit as st
import pandas as pd
import io
import time
import string
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

BASE_URL_FARMASI = "https://satusehat.kemkes.go.id/kfa-browser/farmasi"
CHECKPOINT_FILE = "kfa_obat_checkpoint.csv"

VOWELS = ['a', 'i', 'u', 'e', 'o']
CONSONANTS = [c for c in string.ascii_lowercase if c not in VOWELS]
OBAT_SWEEP_PREFIXES = [f"{c}{v}9" for c in CONSONANTS for v in VOWELS]

CATEGORIES = [
    "Produk Varian",
    "Produk Cangkang (Templates)",
    "Kemasan Produk (Packagings)",
    "Zat Aktif (Active Ingredients)"
]

def init_driver(headless=True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(BASE_URL_FARMASI)
    time.sleep(3)
    return driver

def render_obat_page():
    st.header("💊 KFA Farmasi / Obat (Auto-Save & Anti-Crash Mode)")
    
    selected_cat_name = st.radio("Pilih Kategori Obat:", CATEGORIES, horizontal=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        search_keyword = st.text_input("Kata Kunci Pencarian (Kosongkan untuk Auto-Sweep):", value="", key="obat_keyword")
    with col2:
        headless_mode = st.checkbox("Running Tersembunyi (Headless)", value=True)
    with col3:
        restart_interval = st.number_input("Restart Browser Tiap X Kata Kunci", min_value=5, max_value=50, value=15)

    if st.button("🚀 Mulai Penarikan Data (Anti-Crash)", type="primary"):
        kw_clean = search_keyword.strip()
        keywords_to_process = [kw_clean] if kw_clean else OBAT_SWEEP_PREFIXES
        
        status = st.empty()
        table_p = st.empty()
        
        seen_ids = set()
        
        # Load data checkpoint terdahulu jika ada
        if os.path.exists(CHECKPOINT_FILE):
            try:
                existing_df = pd.read_csv(CHECKPOINT_FILE, sep="|")
                if "Kode KFA" in existing_df.columns:
                    seen_ids = set(existing_df["Kode KFA"].astype(str).tolist())
                    st.toast(f"🔄 Memuat checkpoint: {len(seen_ids):,} data lama ditemukan.", icon="📂")
            except Exception:
                pass

        total_kw = len(keywords_to_process)
        driver = None
        
        try:
            driver = init_driver(headless=headless_mode)
            
            for idx, kw in enumerate(keywords_to_process, start=1):
                status.info(f"⏳ Progress: **[{idx}/{total_kw}]** | Keyword: **'{kw}'** | Total Unik tersimpan: **{len(seen_ids):,}**")
                
                # Restart browser berkala untuk mencegah kebocoran memori RAM
                if idx > 1 and idx % restart_interval == 0:
                    status.warning("🔄 Daur ulang memori browser...")
                    driver.quit()
                    time.sleep(2)
                    driver = init_driver(headless=headless_mode)

                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "//input[@type='text' or @placeholder='Search' or contains(@class, 'input')]"))
                    )
                    search_box.clear()
                    search_box.send_keys(kw)
                    search_box.submit()
                    time.sleep(2.5)
                    
                    rows = driver.find_elements(By.XPATH, "//table//tbody//tr")
                    new_added = []
                    
                    for row in rows:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) >= 2:
                            kfa_code = cols[0].text.strip()
                            name_val = cols[1].text.strip()
                            
                            if kfa_code and kfa_code not in seen_ids:
                                seen_ids.add(kfa_code)
                                item = {
                                    "Kode KFA": kfa_code,
                                    "Nama Obat": name_val,
                                    "Kategori": selected_cat_name,
                                    "Keyword": kw
                                }
                                new_added.append(item)
                    
                    # Simpan langsung ke file lokal (Auto-Checkpoint)
                    if new_added:
                        df_new = pd.DataFrame(new_added)
                        header_needed = not os.path.exists(CHECKPOINT_FILE)
                        df_new.to_csv(CHECKPOINT_FILE, mode='a', index=False, header=header_needed, sep="|")
                        table_p.dataframe(df_new.tail(10), use_container_width=True)
                        
                except Exception as kw_err:
                    # Lanjut ke kata kunci berikutnya jika 1 kata kunci bermasalah
                    continue

            if driver:
                driver.quit()

            if os.path.exists(CHECKPOINT_FILE):
                final_df = pd.read_csv(CHECKPOINT_FILE, sep="|")
                status.success(f"✅ Penarikan Selesai! Total **{len(final_df):,}** data tersimpan di file checkpoint.")
                _render_download(final_df, "kfa_obat_final.txt")
            else:
                status.error("❌ Tidak ada data terambil.")

        except Exception as e:
            if driver:
                driver.quit()
            status.error(f"❌ Terjadi kesalahan fatal: {str(e)}")

def _render_download(df, filename):
    st.divider()
    buf = io.StringIO()
    df.to_csv(buf, sep="|", index=False, encoding="utf-8")
    
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📄 Download File TXT (Separator |)", data=buf.getvalue().encode("utf-8"), file_name=filename, mime="text/plain", type="primary")
    with col2:
        st.metric("Total Baris Data Unik Terkumpul", f"{len(df):,}")
    st.dataframe(df.head(10), use_container_width=True)
