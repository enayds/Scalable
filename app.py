import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from rapidfuzz import fuzz
from datetime import datetime
import re

# ----------- UTILITY FUNCTIONS ------------

def extract_numeric_band(band_text):
    match = re.search(r'\bBand\s*(\d+)', band_text, re.IGNORECASE)
    return int(match.group(1)) if match else None

def extract_numeric_salary(salary_text):
    salary_clean = re.sub(r'[^\d]', '', salary_text.split()[0])
    return int(salary_clean) if salary_clean else None

def get_search_results_page(page, keyword):
    base_url = "https://www.jobs.nhs.uk/candidate/search/results"
    params = {
        "searchFormType": "main",
        "keyword": keyword,
        "language": "en",
        "page": page
    }
    headers = {'User-Agent': 'Mozilla/5.0'}

    try:
        response = requests.get(base_url, headers=headers, params=params)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        st.error(f"Error fetching page {page}: {e}")
        return None
    
def detect_sponsorship(soup):
    """Return 'Not Offered' if any denial phrase is found, else 'Likely Offered'."""
    denial_phrases = [
        "not offer sponsorship",
        "no sponsorship",
        "unable to sponsor",
        "not able to sponsor",
        "must have right to work",
        "cannot provide visa",
        "cannot sponsor",
        "uk residency required"
    ]
    description_block = soup.get_text(separator=" ", strip=True).lower()
    if any(phrase in description_block for phrase in denial_phrases):
        return "Not Offered"
    return "Likely Offered"


def get_job_details(link):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(link, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Band detection
        band_tag = soup.select_one("#payscheme-band")
        band_text = band_tag.get_text(strip=True) if band_tag else ""
        band_num = extract_numeric_band(band_text)

        # Sponsorship detection
        sponsorship = detect_sponsorship(soup)

        return f"Band {band_num}" if band_num else None, band_num, sponsorship

    except Exception:
        return None, None, "Unknown"


def job_passes_filters(title, job_info, user_filters, keyword):
    if fuzz.partial_ratio(title.lower(), keyword.lower()) < 70:
        return False
    if user_filters["contract_type"].lower() not in job_info["contract_type"].lower():
        return False
    if user_filters["location"] and user_filters["location"].lower() not in job_info["location"].lower():
        return False
    if user_filters["working_pattern"].lower() != "both" and user_filters["working_pattern"].lower() not in job_info["working_pattern"].lower():
        return False
    if user_filters["min_salary"] and (not job_info["salary_num"] or job_info["salary_num"] < user_filters["min_salary"]):
        return False
    return True

# ----------- STREAMLIT APP MAIN FUNCTION ------------

def main():
    st.set_page_config(page_title="NHS Job Filter", layout="wide")
    st.title("🔍 NHS Job Scraper with Smart Filters")

    with st.sidebar:
        keyword = st.text_input("Job Keyword", value="Healthcare support worker")
        location_filter = st.text_input("Location (optional)", "")
        contract_type = st.selectbox("Contract Type", ["Permanent", "Fixed Term", "Bank", "Any"], index=0)
        working_pattern = st.selectbox("Working Pattern", ["Full time", "Part time", "Both"], index=0)
        min_band = st.number_input("Minimum Band", min_value=3, max_value = 9, value = 3)
        max_band = st.number_input("Miximum Band", min_value=1, max_value = 9, value = 3)
        min_salary = st.number_input("Minimum Salary (£)", min_value=0, value=24000)
        sponsorship_filter = st.selectbox("Sponsorship", ["All", "Only with sponsorship", "Only without sponsorship"], index=0)
        num_pages = st.number_input("Pages to Scrape", min_value=1, max_value=50, value=1)
        run_search = st.button("🔎 Search Jobs")

    if not run_search:
        st.info("Set your filters in the sidebar and click **Search Jobs**.")
        return

    filters = {
        "location": location_filter,
        "contract_type": contract_type if contract_type != "Any" else "",
        "working_pattern": working_pattern,
        "min_band": min_band,
        "max_band": max_band,
        "min_salary": min_salary,
        "sponsorship_filter": sponsorship_filter
    }

    results = []
    with st.spinner("Scraping jobs..."):
        for page in range(1, num_pages + 1):
            st.write(f"🔄 Scraping page {page}...")
            soup = get_search_results_page(page, keyword)
            if not soup:
                continue

            job_listings = soup.select("li[data-test='search-result']")
            progress_bar = st.progress(0)
            total_jobs = len(job_listings)

            for idx, job in enumerate(job_listings):
                progress_bar.progress((idx + 1) / total_jobs)
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
                    salary_text = re.sub(r'\s+', ' ', salary_text)
                    salary_num = extract_numeric_salary(salary_text)

                    date_posted_tag = job.select_one("li[data-test='search-result-publicationDate']")
                    date_posted = date_posted_tag.get_text(strip=True) if date_posted_tag else None

                    closing_date_tag = job.select_one("li[data-test='search-result-closingDate']")
                    closing_date = closing_date_tag.get_text(strip=True) if closing_date_tag else None

                    contract_tag = job.select_one("li[data-test='search-result-jobType']")
                    contract = contract_tag.get_text(strip=True) if contract_tag else ""

                    pattern_tag = job.select_one("li[data-test='search-result-workingPattern']")
                    pattern = pattern_tag.get_text(strip=True) if pattern_tag else ""

                    job_info = {
                        "contract_type": contract,
                        "location": location,
                        "working_pattern": pattern,
                        "salary_num": salary_num
                    }

                    if not job_passes_filters(title, job_info, filters, keyword):
                        continue

                    band_text, band_num, sponsorship = get_job_details(full_link)
                    if not band_num:
                        continue
                    if band_num < filters["min_band"] or band_num > filters["max_band"]:
                        continue
                    # Apply sponsorship filter
                    if filters["sponsorship_filter"] == "Only with sponsorship" and sponsorship != "Likely Offered":
                        continue
                    if filters["sponsorship_filter"] == "Only without sponsorship" and sponsorship != "Not Offered":
                        continue


                    results.append({
                        "Title": title,
                        "Link": full_link,
                        "Organisation": organisation,
                        "Location": location,
                        "Salary": salary_text.split(":")[-1],
                        "Date Posted": datetime.strptime(date_posted.split(":")[-1].strip(), "%d %B %Y"),
                        "Closing Date": datetime.strptime(closing_date.split(":")[-1].strip(), "%d %B %Y"),
                        "Contract Type": contract.split(":")[-1],
                        "Working Pattern": pattern.split(":")[-1],
                        "Band": band_text,
                        "Sponsorship": sponsorship
                    })

                    time.sleep(1)

                except Exception as e:
                    st.warning(f"Error parsing a job: {e}")
                    continue

    df = pd.DataFrame(results)
    df = df[df["Date Posted"].notnull()].sort_values(by="Date Posted", ascending=False)

    st.success(f"✅ Found {len(df)} matching job(s).")
    st.dataframe(df)

    if not df.empty:
        st.download_button("Download CSV", df.to_csv(index=False), file_name="filtered_jobs.csv", mime="text/csv")

# ----------- ENTRY POINT ------------

if __name__ == "__main__":
    main()
