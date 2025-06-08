import streamlit as st
import urllib.parse
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime
from fuzzywuzzy import fuzz
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# --------- Utility Functions ---------
def get_search_results_page(search_url, session):
    try:
        response = session.get(search_url, timeout=10)
        if response.status_code == 200:
            return BeautifulSoup(response.text, "html.parser")
    except:
        pass
    return None

def get_total_pages(soup):
    if not soup:
        return 1
    page_info_tag = soup.select_one("span.nhsuk-pagination__page")
    if page_info_tag:
        text = page_info_tag.get_text(strip=True)
        match = re.search(r"Page \d+ of (\d+)", text)
        if match:
            return int(match.group(1))
    return 1

def extract_numeric_salary(salary_str):
    matches = re.findall(r"\d{2,3}(?:,\d{3})?", salary_str.replace("\u00a3", ""))
    if matches:
        nums = [int(s.replace(",", "")) for s in matches]
        if len(nums) == 1:
            return nums[0], nums[0]
        elif len(nums) >= 2:
            return min(nums), max(nums)
    return None, None

def extract_numeric_band(band_text):
    match = re.search(r'\bBand\s*(\d+)', band_text, re.IGNORECASE)
    return int(match.group(1)) if match else None

def clean_date(date_str):
    try:
        return pd.to_datetime(date_str, dayfirst=True).date()
    except:
        return None

def job_passes_filters(title, job_info, salary, keyword):
    if fuzz.partial_ratio(title.lower(), keyword.lower()) < 70:
        return False
    if salary and (not job_info["salary_num"] or job_info["salary_num"] < salary):
        return False
    return True

def detect_sponsorship(soup):
    denial_phrases = [
        "not offer sponsorship", "no sponsorship", "unable to sponsor",
        "not able to sponsor", "must have right to work",
        "cannot provide visa", "cannot sponsor", "uk residency required"
    ]
    description_block = soup.get_text(separator=" ", strip=True).lower()
    if any(phrase in description_block for phrase in denial_phrases):
        return "Not Offered"
    return "Likely Offered"

def detect_drivers_license(soup):
    license_phrases = [
        "full uk driving licence", "uk driving license", "driver's license required",
        "clean driving license", "must have driving licence", "access to a vehicle",
        "own transport essential", "car driver essential", "you will need to drive"
    ]
    description_block = soup.get_text(separator=" ", strip=True).lower()
    return any(phrase in description_block for phrase in license_phrases)

def fetch_job_detail(full_link, session):
    try:
        response = session.get(full_link, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        band_tag = soup.select_one("#payscheme-band")
        band_text = band_tag.get_text(strip=True) if band_tag else ""
        band_num = extract_numeric_band(band_text)

        sponsorship = detect_sponsorship(soup)
        license_required = detect_drivers_license(soup)

        return band_num, sponsorship, license_required
    except:
        return None, "Unknown", False

# --------- Main Scraper Logic ---------
def scrape_jobs(base_url, filters_cleaned, num_pages):
    results = []
    jobs_to_process = []

    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    for page in range(1, num_pages + 1):
        filters_cleaned["page"] = page
        search_url = base_url + urllib.parse.urlencode(filters_cleaned, quote_via=urllib.parse.quote)
        soup = get_search_results_page(search_url, session)
        if not soup:
            continue

        job_listings = soup.select("li[data-test='search-result']")
        for job in job_listings:
            try:
                a_tag = job.select_one("h2 a[data-test='search-result-job-title']")
                title = a_tag.get_text(strip=True) if a_tag else None
                relative_link = a_tag['href'] if a_tag and 'href' in a_tag.attrs else None
                full_link = f"https://www.jobs.nhs.uk{relative_link}" if relative_link else None

                org_tag = job.select_one("div[data-test='search-result-location'] h3")
                org_text = org_tag.get_text(separator="|", strip=True) if org_tag else ""
                organisation, location = org_text.split("|", 1) if "|" in org_text else (org_text, org_text)

                salary_tag = job.select_one("li[data-test='search-result-salary']")
                salary_text = salary_tag.get_text(strip=True) if salary_tag else ""
                min_salary, max_salary = extract_numeric_salary(salary_text)
                salary_num = min_salary

                date_posted_tag = job.select_one("li[data-test='search-result-publicationDate']")
                date_posted_raw = date_posted_tag.get_text(strip=True).split(':')[-1] if date_posted_tag else None
                date_posted = clean_date(date_posted_raw)

                closing_date_tag = job.select_one("li[data-test='search-result-closingDate']")
                closing_date_raw = closing_date_tag.get_text(strip=True).split(':')[-1] if closing_date_tag else None
                closing_date = clean_date(closing_date_raw)

                contract_tag = job.select_one("li[data-test='search-result-jobType']")
                contract = contract_tag.get_text(strip=True).split(":")[-1].strip() if contract_tag else ""

                pattern_tag = job.select_one("li[data-test='search-result-workingPattern']")
                pattern = pattern_tag.get_text(strip=True).split(":")[-1].strip() if pattern_tag else ""

                job_info = {
                    "contract_type": contract,
                    "location": location,
                    "working_pattern": pattern,
                    "salary_num": salary_num,
                    "date posted": date_posted,
                    "closing date": closing_date
                }

                if not job_passes_filters(title, job_info, filters_cleaned.get("min_salary", 0), filters_cleaned.get("keyword", "")):
                    continue

                jobs_to_process.append({
                    "Title": title,
                    "Link": full_link,
                    "Organisation": organisation,
                    "Location": location,
                    "Min Salary": min_salary,
                    "Max Salary": max_salary,
                    "Contract Type": contract,
                    "Working Pattern": pattern,
                    "Date Posted": date_posted,
                    "Closing Date": closing_date,
                })

            except:
                continue

    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_job = {
            executor.submit(fetch_job_detail, job['Link'], session): job for job in jobs_to_process
        }

        progress_bar = st.progress(0)
        for i, future in enumerate(as_completed(future_to_job)):
            job = future_to_job[future]
            try:
                band, sponsorship, license_required = future.result()

                if filters_cleaned.get("license_filter", False) and license_required:
                    continue

                job.update({
                    "Band": band,
                    "Sponsorship": sponsorship,
                    "Driver's License Required": "Yes" if license_required else "No"
                })

                results.append(job)
            except:
                continue
            progress_bar.progress((i + 1) / len(jobs_to_process))

    return results

# --------- Main UI App ---------
def main():
    # st.set_page_config(page_title="NHS Job Filter", layout="wide")
    st.title("🔍 NHS Job Scraper with Smart Filters")

    with st.sidebar:
        keyword = st.text_input("Job Keyword", value="Healthcare support worker")
        contract_type = st.selectbox("Contract Type", ["Permanent", "Any"], index=0)
        working_pattern = st.selectbox("Working Pattern", ["Full time", "Any"], index=0)

        bands = [
            "BAND_2", "BAND_3", "BAND_4", "BAND_5", "BAND_6", "BAND_7",
            "BAND_8A", "BAND_8B", "BAND_8C", "BAND_8D", "BAND_9"
        ]

        min_band = st.selectbox("Minimum Pay Band", bands, index=1)
        max_band = st.selectbox("Maximum Pay Band", bands, index=4)

        min_index = bands.index(min_band)
        max_index = bands.index(max_band)

        if min_index > max_index:
            st.warning("⚠️ Minimum band must be less than or equal to maximum band.")
            return

        min_salary = st.number_input("Minimum Salary (£)", min_value=0, value=24000)
        num_pages = st.number_input("Pages to Scrape", min_value=1, max_value=50, value=1)
        license_filter = st.checkbox("Must Not Require Driver's License")

        location_filter = st.text_input("Location (optional)", "")

        run_search = st.button("🔎 Search Jobs")

    if not run_search:
        st.info("Set your filters in the sidebar and click **Search Jobs**.")
        return

    band_range = bands[min_index:max_index + 1]

    filters = {
        "keyword": keyword,
        "location": location_filter,
        "contractType": contract_type if contract_type != "Any" else "",
        "workingPattern": "full-time" if working_pattern != "Any" else "",
        "payBand": ",".join(band_range),
        "language": "en",
        "min_salary": min_salary,
        "license_filter": license_filter
    }

    filters_cleaned = {k: v for k, v in filters.items() if v != "" and v is not None}

    base_url = "https://www.jobs.nhs.uk/candidate/search/results?"

    final_url = base_url + urllib.parse.urlencode(filters_cleaned, quote_via=urllib.parse.quote)
    soup = get_search_results_page(final_url, requests.Session())

    total_pages = get_total_pages(soup)
    pages_to_scrape = min(num_pages, total_pages)
    results = scrape_jobs(base_url, filters_cleaned, pages_to_scrape)

    df = pd.DataFrame(results)
    df_sorted = df.sort_values(by='Date Posted', ascending=False).reset_index(drop=True)

    st.subheader(f"Results ({len(df_sorted)} jobs found)")
    st.dataframe(df_sorted.head(10))

    df_sorted.to_csv("nhs_jobs_filtered.csv", index=False)
    # st.download_button("📥 Download Results as CSV", df_sorted, "nhs_jobs.csv", "text/csv")
    st.success("Saved to nhs_jobs_filtered.csv")

if __name__ == "__main__":
    main()
