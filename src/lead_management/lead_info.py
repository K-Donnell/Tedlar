import os
import pandas as pd
import time
import random
import re
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import threading
from concurrent.futures import ThreadPoolExecutor

# Base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Paths
INPUT_DIR = os.path.join(BASE_DIR, 'lead_generation', 'data')
INPUT_CSV = os.path.join(INPUT_DIR, 'caprank.csv')
OUTPUT_DIR = os.path.join(BASE_DIR, 'lead_management', 'data')
OUTPUT_CSV = os.path.join(OUTPUT_DIR, 'lead_info.csv')

os.makedirs(OUTPUT_DIR, exist_ok=True)

# protect writes to CSV
write_lock = threading.Lock()


def setup_driver():
    chrome_options = Options()
    # leave headless off so you can watch
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    return webdriver.Chrome(options=chrome_options)


def human_typing(element, text):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.07, 0.15))


def clean_linkedin_url(raw_url):
    if not raw_url:
        return "Not Found"
    parsed = urlparse(raw_url)
    return f"https://{parsed.netloc}{parsed.path}"


def clean_name_from_url(url):
    # 1) extract the slug
    if '/in/' in url:
        slug = url.split('/in/')[-1]
    elif '/pub/' in url:
        slug = url.split('/pub/')[-1]
    else:
        return "Unknown"

    # 2) drop any trailing path bits
    slug = slug.split('/')[0]

    # 3) split on hyphens
    parts = slug.split('-')

    # 4) if the last part has more than 2 digits, drop it
    if len(parts) > 1:
        last = parts[-1]
        if sum(c.isdigit() for c in last) > 2:
            parts = parts[:-1]

    # 5) for single-part slugs, strip off any trailing digits
    if len(parts) == 1:
        parts[0] = re.sub(r'\d+$', '', parts[0])

    # 6) remove any remaining digits from each part
    parts = [re.sub(r'\d+', '', p) for p in parts]

    # 7) filter out any empty strings
    parts = [p for p in parts if p]

    # 8) join and title-case
    return ' '.join(parts).title()


def search_company_leads(driver, company_name, max_results=10):
    leads = []
    for attempt in range(3):
        try:
            driver.get("https://www.google.com/")
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, "q")))
            time.sleep(random.uniform(1.5, 3.0))

            query = (
                f"{company_name} "
                "(Director of Marketing OR VP of Marketing OR "
                "VP of Product Development OR Director of Innovation OR "
                "Head of R&D OR R&D Director) site:linkedin.com"
            )

            box = driver.find_element(By.NAME, "q")
            box.clear()
            human_typing(box, query)
            time.sleep(random.uniform(1.0, 2.0))
            box.send_keys(Keys.RETURN)

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "div#search")))
            time.sleep(random.uniform(1.0, 2.0))

            results = driver.find_elements(By.CSS_SELECTOR, "div#search a")
            seen = set()
            for r in results:
                href = r.get_attribute("href")
                if href and ("linkedin.com/in/" in href or "linkedin.com/pub/" in href):
                    clean_href = clean_linkedin_url(href)
                    if clean_href not in seen:
                        seen.add(clean_href)
                        leads.append((clean_name_from_url(clean_href), clean_href))
                        if len(leads) >= max_results:
                            break

            if leads:
                return leads
            else:
                # no results this attempt
                break
        except Exception:
            time.sleep(random.uniform(3.0, 6.0))
    return leads or [("Not Found", "Not Found")]


def save_leads_to_csv(entry):
    df = pd.DataFrame([entry])
    with write_lock:
        if os.path.exists(OUTPUT_CSV):
            df.to_csv(OUTPUT_CSV, mode='a', header=False, index=False)
        else:
            df.to_csv(OUTPUT_CSV, mode='w', header=True, index=False)


def process_company(company):
    driver = setup_driver()
    try:
        leads = search_company_leads(driver, company, max_results=10)
        entry = {'Company Name': company}
        for i, (name, link) in enumerate(leads, start=1):
            entry[f'Lead {i} Name'] = name
            entry[f'Lead {i} LinkedIn'] = link
        save_leads_to_csv(entry)
        time.sleep(random.uniform(2.0, 4.0))
    finally:
        driver.quit()


def main():
    df = pd.read_csv(INPUT_CSV)
    if 'Company Name' in df.columns:
        companies = df['Company Name'].tolist()
    elif 'Name' in df.columns:
        companies = df['Name'].tolist()
    else:
        raise RuntimeError("No company column found in input CSV.")

    # adjust max_workers to what your machine can handle
    with ThreadPoolExecutor(max_workers=4) as exe:
        exe.map(process_company, companies)

    print(f"Finished! Leads saved to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
