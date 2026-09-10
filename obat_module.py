import streamlit as st
import pandas as pd
import io
import time
import string
import os
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

BASE_URL_FARMASI = "https://satusehat.kemkes.go.id/kfa-browser/farmasi"
CHECKPOINT_FILE = "kfa_obat_checkpoint.csv"

VOWELS = ['a', 'i', 'u', 'e', 'o']
CONSONANTS = [c for c in string.ascii_lowercase if c not in VOWELS]
OBAT_SWEEP_PREFIXES = [f"{c}{v}9" for c in CONSONANTS for v in VOWELS]

def clean_text_field(val):
    if isinstance(val, dict):
        return val.get("name") or val.get("title") or val.get("code") or ""
    elif isinstance(val, list):
        items = [clean_text_field(x) for x in val]
        return ", ".join([x for x in items if x])
    elif val is None:
        return ""
    return str(val).strip()

CATEGORIES = {
    "Produk Varian": {
        "tab_text": "Produk Varian",
        "api_keyword": "product-variant",
        "key_id": "Kode KFA",
        "all_cols": ["Kode KFA", "Nama Produk", "Merk Dagang", "Unit Logistik Terkecil", "Bentuk Sediaan", "Golongan Obat", "Nomor Izin Edar", "Fornas"],
        "default_cols": ["Kode KFA", "Nama Produk", "Merk Dagang", "Unit Logistik Terkecil", "Bentuk Sediaan", "Golongan Obat", "Nomor Izin Edar", "Fornas"],
        "parser": lambda item: {
            "Kode KFA": clean_text_field(item.get("kfa_code") or item.get("kfaCode")),
            "Nama Produk": clean_text_field(item.get("product_variant_name") or item.get("name")),
            "Merk Dagang": clean_text_field(item.get("trade_name") or item.get("tradeName")),
            "Unit Logistik Terkecil": clean_text_field(item.get("uom_name") or item.get("uomName") or item.get("uom")),
            "Bentuk Sediaan": clean_text_field(item.get("dosage_form_name") or item.get("dosageFormName") or item.get("dosageForm")),
            "Golongan Obat": clean_text_field(item.get("farmalkes_type") or item.get("farmalkesType")),
            "Nomor Izin Edar": clean_text_field(item.get("nie")),
            "Fornas": "Ya" if item.get("is_fornas") or item.get("isFornas") else "Tidak"
        }
    },
    "Produk Cangkang (Templates)": {
        "tab_text": "Produk Cangkang",
        "api_keyword": "product-template",
        "key_id": "Kode KFA",
        "all_cols": ["Kode KFA", "Nama Produk Cangkang", "Total Varian", "Unit Logistik"],
        "default_cols": ["Kode KFA", "Nama Produk Cangkang", "Total Varian", "Unit Logistik"],
        "parser": lambda item: {
            "Kode KFA": clean_text_field(item.get("kfa_code") or item.get("kfaCode")),
            "Nama Produk Cangkang": clean_text_field(item.get("product_template_name") or item.get("name")),
            "Total Varian": item.get("total_variants") or item.get("totalVariants") or 0,
            "Unit Logistik": clean_text_field(item.get("uom_name") or item.get("uomName") or item.get("uom"))
        }
    },
    "Kemasan Produk (Packagings)": {
        "tab_text": "Kemasan",
        "api_keyword": "product-packaging",
        "key_id": "Kode KFA Kemasan",
        "all_cols": ["Kode KFA Kemasan", "Nama Varian", "Nama Kemasan", "Qty", "Harga (HET/KFA)", "Satuan (UOM)"],
        "default_cols": ["Kode KFA Kemasan", "Nama Varian", "Nama Kemasan", "Qty", "Harga (HET/KFA)", "Satuan (UOM)"],
        "parser": lambda item: {
            "Kode KFA Kemasan": clean_text_field(item.get("kfa_code") or item.get("kfaCode")),
            "Nama Varian": clean_text_field(item.get("variant_display_name") or item.get("variantDisplayName") or item.get("name")),
            "Nama Kemasan": clean_text_field(item.get("package_name") or item.get("packageName")),
            "Qty": item.get("qty", 0),
            "Harga (HET/KFA)": item.get("price", 0),
            "Satuan (UOM)": clean_text_field(item.get("uom_name") or item.get("uomName") or item.get("uom"))
        }
    },
    "Zat Aktif (Active Ingredients)": {
        "tab_text": "Zat Aktif",
        "api_keyword": "active-ingredient",
        "key_id": "Kode KFA",
        "all_cols": ["Kode KFA", "Nama Zat Aktif", "Satuan Dosis (UCUM)"],
        "default_cols": ["Kode KFA", "Nama Zat Aktif", "Satuan Dosis (UCUM)"],
        "parser": lambda item: {
            "Kode KFA": clean_text_field(item.get("kfa_code") or item.get("kfaCode")),
            "Nama Zat Aktif": clean_text_field(item.get("name") or item.get("active_ingredient_name")),
            "Satuan Dosis (UCUM)": clean_text_field(item.get("ucum_symbol") or item.get("ucumSymbol") or item.get("ucum"))
        }
    }
}

def init_driver(headless=False):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get(BASE_URL_FARMASI)
    time.sleep(4)
    return driver

def switch_to_tab(driver, category_name):
    try:
        config = CATEGORIES[category_name]
        tab_keyword = config["tab_text"]
        tabs = driver.find_elements(By.XPATH, f"//button[contains(text(), '{tab_keyword}')] | //a[contains(text(), '{tab_keyword}')] | //div[contains(text(), '{tab_keyword}')]")
        if tabs:
            tabs[0].click()
            time.sleep(2)
    except Exception:
        pass

def extract_json_from_logs(driver, config):
    items_extracted = []
    try:
        logs = driver.get_log('performance')
        for entry in logs:
            try:
                log_json = json.loads(entry['message'])
                message = log_json.get('message', {})
                if message.get('method') == 'Network.responseReceived':
                    resp_url = message.get('params', {}).get('response', {}).get('url', '')
                    if 'api' in resp_url and config["api_keyword"] in resp_url:
                        req_id = message.get('params', {}).get('requestId')
                        try:
                            body = driver.execute_cdp_cmd('Network.getResponseBody', {'requestId': req_id})
                            res_text = body.get('body', '')
                            res_data = json.loads(res_text)
                            
                            raw_items = res_data.get('items') or res_data.get('data') or []
                            if isinstance(raw_items, dict):
                                raw_items = raw_items.get('items') or raw_items.get('data') or []
                                
                            for item in raw_items:
                                if isinstance(item, dict):
                                    parsed = config["parser"](item)
                                    if parsed.get(config["key_id"]):
                                        items_extracted.append(parsed)
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass
    return items_extracted

def go_to_next_page(driver, target_page_num):
    """Mengeklik tombol Next Page & otomatis mendeteksi jika tombol sudah terkunci / disabled"""
    xpath_selectors = [
        "//i[contains(@class, 'pi-chevron-right')]/parent::button",
        "//button[contains(@class, 'leading-none') and .//i[contains(@class, 'pi-chevron-right')]]",
        "//i[contains(@class, 'pi-chevron-right')]",
        f"//button[text()='{target_page_num}']"
    ]
    
    for xpath in xpath_selectors:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
            for el in elements:
                if el.is_displayed():
                    # Cek apakah tombol atau induknya memiliki status disabled / not-allowed
                    is_disabled = el.get_attribute("disabled") or el.get_attribute("aria-disabled")
                    cls = el.get_attribute("class") or ""
                    
                    # Cek juga atribut di tombol induk jika yang ditemukan adalah elemen <i>
                    parent_el = el.find_element(By.XPATH, "..")
                    parent_cls = parent_el.get_attribute("class") or ""
                    parent_disabled = parent_el.get_attribute("disabled") or parent_el.get_attribute("aria-disabled")

                    if is_disabled or parent_disabled or "disabled" in cls or "disabled" in parent_cls or "cursor-not-allowed" in cls or "cursor-not-allowed" in parent_cls:
                        return False # Halaman sudah paling akhir (tombol terkunci)

                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
                    time.sleep(0.3)
                    driver.execute_script("arguments[0].click();", el)
                    return True
        except Exception:
            continue
            
    return False

def render_obat_page():
    st.header("💊 KFA Farmasi / Obat")
    
    selected_cat_name = st.radio("Pilih Kategori Obat:", list(CATEGORIES.keys()), horizontal=True)
    config = CATEGORIES[selected_cat_name]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        target_size = st.number_input("Target Total Data Per Kata Kunci", min_value=1, max_value=5000, value=2000, step=100, key="obat_size")
        st.caption("ℹ️ Default web KFA: **10 item/halaman**.")
    with col2:
        max_pages = st.number_input("Batas Maksimal Halaman (0 = Tanpa Batas)", min_value=0, value=0, step=1, key="obat_pages")
    with col3:
        search_keyword = st.text_input("Kata Kunci Pencarian (Kosongkan untuk Auto-Sweep 'xx9'):", value="", key="obat_keyword")
        
    selected_cols = st.multiselect("Pilih Kolom:", config["all_cols"], default=config["default_cols"], key="obat_cols")
    
    col_a, col_b = st.columns(2)
    with col_a:
        headless_mode = st.checkbox("Jalankan Tersembunyi (Headless)", value=False)
    with col_b:
        if st.button("🗑️ Hapus Riwayat Checkpoint (Reset Data)"):
            if os.path.exists(CHECKPOINT_FILE):
                os.remove(CHECKPOINT_FILE)
                st.success("✅ Riwayat checkpoint berhasil dihapus!")
            else:
                st.info("ℹ️ Belum ada file checkpoint tersimpan.")

    if st.button(f"🚀 Mulai Penarikan Data {selected_cat_name}", type="primary"):
        kw_clean = search_keyword.strip()
        keywords_to_process = [kw_clean] if kw_clean else OBAT_SWEEP_PREFIXES
        
        status = st.empty()
        table_p = st.empty()
        seen_ids = set()
        all_rows = []
        
        if os.path.exists(CHECKPOINT_FILE):
            try:
                existing_df = pd.read_csv(CHECKPOINT_FILE, sep="|")
                if config["key_id"] in existing_df.columns:
                    seen_ids = set(existing_df[config["key_id"]].astype(str).tolist())
                    st.toast(f"🔄 Checkpoint dimuat: {len(seen_ids):,} data unik tersimpan.", icon="📂")
            except Exception:
                pass

        total_kw = len(keywords_to_process)
        driver = None
        
        try:
            status.info("⏳ Membuka Browser Chrome...")
            driver = init_driver(headless=headless_mode)
            
            switch_to_tab(driver, selected_cat_name)

            for idx, kw in enumerate(keywords_to_process, start=1):
                current_page = 1
                kw_collected = 0
                no_new_data_counter = 0 # Detektor kebuntuan data
                
                while True:
                    status.info(f"⏳ Progress: **[{idx}/{total_kw}]** | Keyword: **'{kw}'** | Halaman: **{current_page}** | Terkumpul dari '{kw}': **{kw_collected}** | Total Unik Overall: **{len(seen_ids):,}**")
                    
                    try:
                        if current_page == 1:
                            search_box = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((
                                    By.XPATH, 
                                    "//input[contains(@placeholder,'Cari') or contains(@placeholder,'Search') or @type='text']"
                                ))
                            )
                            search_box.send_keys(Keys.CONTROL + "a")
                            search_box.send_keys(Keys.BACKSPACE)
                            time.sleep(0.3)
                            search_box.send_keys(kw)
                            time.sleep(0.3)
                            search_box.send_keys(Keys.ENTER)
                            time.sleep(2.5)
                        
                        extracted_items = extract_json_from_logs(driver, config)
                        new_added = []
                        
                        for item in extracted_items:
                            unique_key = item.get(config["key_id"])
                            if unique_key and str(unique_key) not in seen_ids:
                                seen_ids.add(str(unique_key))
                                all_rows.append(item)
                                new_added.append(item)
                                kw_collected += 1
                        
                        # Fallback ekstraksi dari DOM jika JSON belum tertangkap
                        if not new_added:
                            rows = driver.find_elements(By.XPATH, "//tbody/tr")
                            for row in rows:
                                cols = row.find_elements(By.TAG_NAME, "td")
                                if len(cols) >= 2:
                                    kfa_code = cols[0].text.strip()
                                    name_val = cols[1].text.strip()
                                    if kfa_code and kfa_code.lower() != "tidak ada data" and kfa_code not in seen_ids:
                                        seen_ids.add(kfa_code)
                                        fallback_item = {col: "" for col in config["all_cols"]}
                                        fallback_item[config["key_id"]] = kfa_code
                                        fallback_item["Nama Produk"] = name_val
                                        all_rows.append(fallback_item)
                                        new_added.append(fallback_item)
                                        kw_collected += 1

                        if new_added:
                            no_new_data_counter = 0 # Reset hitungan jika ada data baru
                            df_new = pd.DataFrame(new_added)
                            header_needed = not os.path.exists(CHECKPOINT_FILE)
                            df_new.to_csv(CHECKPOINT_FILE, mode='a', index=False, header=header_needed, sep="|")
                            
                            valid_c = [c for c in selected_cols if c in df_new.columns]
                            if valid_c:
                                table_p.dataframe(df_new[valid_c].tail(10), use_container_width=True)
                        else:
                            no_new_data_counter += 1

                        # Proteksi 1: Hentikan jika sudah mencapai target jumlah data atau batas halaman
                        if kw_collected >= target_size:
                            break
                        if max_pages > 0 and current_page >= max_pages:
                            break
                            
                        # Proteksi 2: Hentikan jika 2 halaman berturut-turut tidak memberikan data baru (data habis)
                        if no_new_data_counter >= 2:
                            break

                        # Pindah ke Halaman Berikutnya
                        next_page_num = current_page + 1
                        clicked = go_to_next_page(driver, next_page_num)
                        if clicked:
                            time.sleep(2.5)
                            current_page += 1
                        else:
                            break # Halaman habis (tombol Next terkunci/disabled)

                    except Exception as kw_err:
                        break

            if driver:
                driver.quit()

            if os.path.exists(CHECKPOINT_FILE):
                final_df = pd.read_csv(CHECKPOINT_FILE, sep="|")
                status.success(f"✅ Penarikan Selesai! Total **{len(final_df):,}** data obat unik berhasil dikumpulkan.")
                _render_download(final_df, selected_cols, f"kfa_obat_{config['api_keyword']}.txt")
            else:
                status.error("❌ Tidak ada data terambil.")

        except Exception as e:
            if driver:
                driver.quit()
            status.error(f"❌ Error Driver Browser: {str(e)}")

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
        st.metric("Total Baris Data Unik Terkumpul", f"{len(df):,}")
    st.dataframe(df.head(10), use_container_width=True)
