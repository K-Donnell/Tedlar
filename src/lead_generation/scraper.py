#!/usr/bin/env python3
import os
import csv
import time
import re
import sys
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Setup Selenium
options = Options()
# options.add_argument("--headless")  # Chrome visible
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        })
    """
})

# Define base directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# CSV save helper
def save_page_source(company_name, reason):
    filename = f"{company_name.replace(' ', '_')}_{reason}.html"
    filepath = os.path.join(BASE_DIR, 'logs', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(driver.page_source)
    logger.debug(f"Saved page source to {filepath}")

# Search the company; return True if page loaded, False if no result
def search_company(company_name):
    logger.info(f"Searching for {company_name}")
    driver.get('https://companiesmarketcap.com/')
    try:
        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, 'search-input'))
        )
        search_box.clear()
        search_box.send_keys(company_name)
        time.sleep(2)

        dropdown = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.ID, 'typeahead-search-results'))
        )
        links = dropdown.find_elements(By.TAG_NAME, 'a')
        if not links:
            logger.info(f"No search results for {company_name}, skipping.")
            return False
        links[0].click()
        logger.info(f"Selected first dropdown result for {company_name}")

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH,
                 "//p[contains(., 'has a market cap of') or contains(., 'market cap of')]"
                )
            )
        )
        logger.debug(f"{company_name} page loaded.")
        return True
    except TimeoutException:
        logger.info(f"{company_name} not found on search, skipping.")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during search for {company_name}: {e}")
        return False

# Extract Market Cap and Revenue from the company page
def extract_market_cap_and_revenue(company_name):
    try:
        # Extract Market Cap paragraph
        summary = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.XPATH, "//p[contains(., 'market cap of')]")
            )
        )
        text = summary.text.strip()
        logger.debug(f"Summary text: {text}")

        cap_match = re.search(
            r"market cap of\s*\$([\d,.]+)\s*(Billion|Million|Trillion)",
            text, re.IGNORECASE
        )
        market_cap = f"${cap_match.group(1).replace(',', '')}{cap_match.group(2)}" if cap_match else "Not Found"

        # Attempt to click Revenue tab
        try:
            revenue_tab = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Revenue"))
            )
            driver.execute_script("arguments[0].click();", revenue_tab)
            time.sleep(2)
        except Exception:
            logger.warning(f"Revenue tab not available for {company_name}")
            return market_cap, "Not Found"

        # Extract Revenue value
        try:
            revenue_element = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "span.background-ya"))
            )
            rev_text = revenue_element.text.strip()
            logger.debug(f"Revenue text: {rev_text}")

            rev_match = re.search(
                r"\$([\d,.]+)\s*(Billion|Million|Trillion)",
                rev_text, re.IGNORECASE
            )
            revenue = f"${rev_match.group(1).replace(',', '')}{rev_match.group(2)}" if rev_match else "Not Found"
        except TimeoutException:
            logger.info(f"Revenue not found for {company_name}")
            return market_cap, "Not Found"

        logger.info(f"{company_name} → Market Cap: {market_cap}, Revenue: {revenue}")
        return market_cap, revenue
    except Exception as e:
        logger.error(f"Error extracting data for {company_name}: {e}")
        return "Not Found", "Not Found"

# Parse a value like "$12 Billion" → numeric
def parse_numeric_value(value_str):
    if value_str == "Not Found":
        return float('-inf')
    s = value_str.replace('$', '').replace(',', '').upper()
    if 'TRILLION' in s:
        return float(s.replace('TRILLION', '')) * 1e12
    if 'BILLION' in s:
        return float(s.replace('BILLION', '')) * 1e9
    if 'MILLION' in s:
        return float(s.replace('MILLION', '')) * 1e6
    return float('-inf')

# Process one company
def process_company(company_name):
    if not search_company(company_name):
        return None, None
    return extract_market_cap_and_revenue(company_name)

# Main entry
def main():
    input_file = os.path.join(BASE_DIR, 'src', 'data_collection', 'data', 'vendors.csv')
    output_file = os.path.join(BASE_DIR, 'src', 'lead_generation', 'data', 'company_market_caps.csv')

    try:
        df = pd.read_csv(input_file)
        companies = df['Vendor'].dropna().astype(str).str.strip().unique()
    except Exception as e:
        logger.error(f"Problem loading input CSV: {e}")
        driver.quit()
        sys.exit(1)

    logger.info(f"Found {len(companies)} companies to check")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Write header
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Company Name', 'Market Cap', 'Revenue'])

    for comp in companies:
        cap, rev = process_company(comp)
        if cap is None:
            continue
        val = parse_numeric_value(rev)
        if val >= 5e7:
            logger.info(f"{comp} passed: Revenue {rev}")
            with open(output_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([comp, cap, rev])
        else:
            logger.debug(f"{comp} skipped: Revenue {rev}")
        time.sleep(4)

    driver.quit()
    logger.info("ChromeDriver closed.")

if __name__ == '__main__':
    main()
