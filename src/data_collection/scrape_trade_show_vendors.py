import csv
import time
import random
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException, ElementNotInteractableException
from fake_useragent import UserAgent
from urllib.parse import urlparse

# Paths
INPUT_CSV = 'data/leads.csv'          # Input file with Trade Show Name, Dates, Location, Website
OUTPUT_CSV = 'data/vendors.csv'       # Output file to save Trade Show and Vendor pairs

# Constants for trade show names
SIGNEXPO_NAME = 'ISA Sign Expo'
HVACR_NAME = '2025 HVAC Excellence National HVACR Education Conference'
COVERINGS_NAME = 'Coverings 2025'

# Scraper for ISA Sign Expo
def scrape_signexpo(driver):
    gallery_url = 'https://isasignexpo2025.mapyourshow.com/8_0/explore/exhibitor-gallery.cfm?featured=false'
    driver.get(gallery_url)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h3.card-Title'))
        )
    except TimeoutException:
        time.sleep(5)
    # Load all results
    while True:
        try:
            btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Load More Results')]")
            if not btn.is_displayed(): break
            driver.execute_script("arguments[0].scrollIntoView();", btn)
            time.sleep(random.uniform(1, 2))
            btn.click(); time.sleep(random.uniform(2,4))
        except Exception:
            break
    # Extract names
    elems = driver.find_elements(By.CSS_SELECTOR, 'h3.card-Title')
    return [e.text.strip() for e in elems if e.text.strip()]

# Scraper for HVAC Excellence Conference
def scrape_hvacr(driver):
    url = 'https://site.pheedloop.com/event/HVACExcellence2025/exhibitors/exhibitors-directory'
    driver.get(url)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h2.pl-card-title'))
        )
    except TimeoutException:
        time.sleep(5)
    while True:
        try:
            btn = driver.find_element(By.XPATH, "//button[contains(text(), 'Load More')]")
            if not btn.is_displayed(): break
            driver.execute_script("arguments[0].scrollIntoView();", btn)
            time.sleep(random.uniform(1,2))
            btn.click(); time.sleep(random.uniform(2,4))
        except Exception:
            break
    elems = driver.find_elements(By.CSS_SELECTOR, 'h2.pl-card-title')
    return [e.text.strip() for e in elems if e.text.strip()]

# Scraper for Coverings 2025
# Uses card layout: vendor names are in <h5 data-generic-layout="heading"> within card headers citeturn5file7
def scrape_coverings(driver):
    url = 'https://coverings2025.smallworldlabs.com/exhibitors'
    driver.get(url)
    try:
        # Wait for the card deck to load
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.generic-horizontal-wrapper.card-deck'))
        )
    except TimeoutException:
        time.sleep(5)
    vendors = []
    while True:
        # Extract vendor names from card headers
        headers = driver.find_elements(By.CSS_SELECTOR, 'div.card-header h5[data-generic-layout="heading"]')
        for h in headers:
            name = h.text.strip()
            if name and name not in vendors:
                vendors.append(name)
        # Attempt to click the paginator ("Next" page) button
        try:
            paginator = driver.find_element(By.CSS_SELECTOR, '[data-option-action="paginator"]')
            if not paginator.is_displayed():
                break
            driver.execute_script("arguments[0].scrollIntoView();", paginator)
            time.sleep(random.uniform(1, 2))
            paginator.click()
            time.sleep(random.uniform(2, 4))
        except (NoSuchElementException, ElementNotInteractableException, TimeoutException):
            break
    return vendors

# Initialize Selenium driver
def init_driver():
    ua = UserAgent()
    opts = webdriver.ChromeOptions()
    opts.add_argument(f"--user-agent={ua.random}")
    drv = webdriver.Chrome(options=opts)
    drv.maximize_window()
    return drv

# Main routine
def main():
    df = pd.read_csv(INPUT_CSV)
    driver = init_driver()
    mapping = {
        'signexpo.org': (scrape_signexpo, SIGNEXPO_NAME),
        'mapyourshow.com': (scrape_signexpo, SIGNEXPO_NAME),
        'pheedloop.com': (scrape_hvacr, HVACR_NAME),
        'coverings2025.smallworldlabs.com': (scrape_coverings, COVERINGS_NAME),
    }
    results = []
    for _, row in df.iterrows():
        url = row.get('Website') or row.get('URL')
        if pd.isna(url) or not str(url).lower().startswith('http'): continue
        domain = urlparse(str(url).strip()).netloc
        pair = next(((fn,name) for k,(fn,name) in mapping.items() if k in domain), None)
        if not pair: continue
        fn, show = pair
        for v in fn(driver):
            results.append({'Trade Show': show, 'Vendor': v})
    driver.quit()
    pd.DataFrame(results).to_csv(OUTPUT_CSV, index=False)
    print(f"Saved {len(results)} vendor entries to {OUTPUT_CSV}")

if __name__ == '__main__':
    main()
