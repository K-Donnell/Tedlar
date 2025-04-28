import os
import re
import pandas as pd
from rapidfuzz import process, fuzz

# ——— Paths ———
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_COLLECTION_DIR = os.path.join(BASE_DIR, 'data_collection', 'data')

VENDORS_CSV = os.path.join(DATA_COLLECTION_DIR, 'vendors.csv')
LEADS_CSV   = os.path.join(DATA_COLLECTION_DIR, 'leads.csv')

MG_DATA_DIR = os.path.join(BASE_DIR, 'lead_generation', 'data')
INPUT_CSV   = os.path.join(MG_DATA_DIR, 'company_market_caps.csv')
OUTPUT_CSV  = os.path.join(MG_DATA_DIR, 'caprank.csv')

# ——— Helpers ———
def normalize_name(s: str) -> str:
    s = s.lower()
    s = re.sub(r'\d+', '', s)            # strip digits
    s = re.sub(r'[^a-z\s]', ' ', s)      # strip punctuation
    return re.sub(r'\s+', ' ', s).strip()

def safe_fuzzy_lookup(needle, haystack, scorer, threshold):
    if not haystack:
        return None
    best = process.extractOne(str(needle), haystack, scorer=scorer)
    return best[0] if best and best[1] >= threshold else None

# ——— Load data ———
df = pd.read_csv(INPUT_CSV)

try:
    vendors_df = pd.read_csv(VENDORS_CSV)
except FileNotFoundError:
    print(f"Warning: {VENDORS_CSV} not found. Trade-show info will be blank.")
    vendors_df = pd.DataFrame(columns=['Trade Show', 'Vendor'])

try:
    leads_df = pd.read_csv(LEADS_CSV)
except FileNotFoundError:
    print(f"Warning: {LEADS_CSV} not found. Dates will be unavailable.")
    leads_df = pd.DataFrame(columns=['Trade Show Name', 'Dates'])

# ——— Column names ———
COMPANY_COL    = 'Company' if 'Company' in df.columns else df.columns[0]
VENDOR_COL     = 'Vendor'
SHOW_COL       = 'Trade Show'
LEADS_NAME_COL = 'Trade Show Name'
LEADS_DATE_COL = 'Dates'

# ——— Market-cap parsing ———
def parse_market_cap(m):
    if m == 'Not Found' or pd.isna(m):
        return float('-inf')
    s = m.replace('$','').replace(',','').strip().upper()
    if 'TRILLION' in s:
        return float(s.replace('TRILLION','')) * 1e12
    if 'BILLION'  in s:
        return float(s.replace('BILLION',''))  * 1e9
    if 'MILLION'  in s:
        return float(s.replace('MILLION',''))  * 1e6
    print(f"Warning: Unrecognized format: {m}")
    return float('-inf')

df['Market Cap Value'] = df['Market Cap'].apply(parse_market_cap)

# ——— Fuzzy prep ———
THRESH_STRICT = 80
THRESH_LOOSE  = 60

vendor_list = vendors_df[VENDOR_COL].astype(str).tolist() if VENDOR_COL in vendors_df else []
leads_list  = leads_df[LEADS_NAME_COL].astype(str).tolist() if LEADS_NAME_COL in leads_df else []

leads_norm     = [normalize_name(n) for n in leads_list]
norm_to_raw    = dict(zip(leads_norm, leads_list))

def find_trade_info(company_name):
    # 1) match company → vendor → show
    vendor_match = safe_fuzzy_lookup(company_name, vendor_list,
                                     scorer=fuzz.token_set_ratio,
                                     threshold=THRESH_STRICT)
    if not vendor_match:
        return pd.Series({SHOW_COL: None, LEADS_DATE_COL: None})

    show = vendors_df.loc[vendors_df[VENDOR_COL] == vendor_match, SHOW_COL].iloc[0]
    date = None

    # 2) match show → leads.csv → date
    if LEADS_NAME_COL in leads_df and LEADS_DATE_COL in leads_df:
        # exact
        exact = leads_df[leads_df[LEADS_NAME_COL] == show]
        if not exact.empty:
            date = exact[LEADS_DATE_COL].iloc[0]
        else:
            # normalized token_set_ratio
            show_norm = normalize_name(show)
            best_norm = process.extractOne(show_norm, leads_norm,
                                           scorer=fuzz.token_set_ratio)
            if best_norm and best_norm[1] >= THRESH_STRICT:
                raw_name = norm_to_raw[best_norm[0]]
                subset = leads_df[leads_df[LEADS_NAME_COL] == raw_name]
                if not subset.empty:
                    date = subset[LEADS_DATE_COL].iloc[0]
            else:
                # loose partial_ratio fallback
                best_part = process.extractOne(show, leads_list,
                                               scorer=fuzz.partial_ratio)
                if best_part and best_part[1] >= THRESH_LOOSE:
                    subset = leads_df[leads_df[LEADS_NAME_COL] == best_part[0]]
                    if not subset.empty:
                        date = subset[LEADS_DATE_COL].iloc[0]

    return pd.Series({SHOW_COL: show, LEADS_DATE_COL: date})

# ——— Apply & save ———
trade_info = df[COMPANY_COL].apply(find_trade_info)
df = pd.concat([df, trade_info], axis=1)

df_sorted = (
    df
    .sort_values(by='Market Cap Value', ascending=False)
    .drop(columns=['Market Cap Value'])
)
df_sorted.to_csv(OUTPUT_CSV, index=False)
print(f"Saved ranked companies with trade-show dates to {OUTPUT_CSV}")
