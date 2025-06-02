import streamlit as st
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import pandas as pd
import numpy as np
import re
from datetime import datetime

# === Fetch Jobs from NHS API ===
def fetch_nhs_jobs(keyword="visa sponsorship", max_pages=30, update_progress=None):
    base_url = "https://www.jobs.nhs.uk/api/v1/search_xml"
    job_records = []
    page = 1

    while page <= max_pages:
        params = {
            "keyword": keyword,
            "page": page,
            "sort": "publicationDateDesc",
            "contractType": "Permanent",
            "salaryFrom": 24000,
        }

        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.content, "xml")
        vacancy_list = soup.find_all("vacancyDetails")
        if not vacancy_list:
            break

        for job in vacancy_list:
            title_text = job.title.text if job.title else ""
            similarity = fuzz.token_set_ratio(keyword.lower(), title_text.lower())
            if similarity < 80:
                continue

            job_records.append({
                "Title": title_text,
                "Employer": job.employer.text if job.employer else "",
                "Description": job.description.text if job.description else "",
                "Location(s)": ", ".join([loc.text for loc in job.find_all("locations")]),
                "Salary": job.salary.text if job.salary else "",
                "Closing Date": job.closeDate.text if job.closeDate else "",
                "Post Date": job.postDate.text if job.postDate else "",
                "Reference": job.reference.text if job.reference else "",
                "URL": job.url.text if job.url else ""
            })

        if update_progress:
            update_progress(page / max_pages)

        page += 1

    return pd.DataFrame(job_records)


# === Helpers ===

def extract_salary_fields(df):
    def parse_salary(row):
        text = row.get('Salary', '')
        match_range = re.search(r'£?([\d,\.]+)\s+to\s+£?([\d,\.]+)', text)
        match_single = re.search(r'£?([\d,\.]+)', text)

        if match_range:
            return pd.Series([float(match_range.group(1).replace(",", "")), float(match_range.group(2).replace(",", ""))])
        elif match_single:
            val = float(match_single.group(1).replace(",", ""))
            return pd.Series([val, val])
        else:
            return pd.Series([np.nan, np.nan])

    df[['Min Salary', 'Max Salary']] = df.apply(parse_salary, axis=1)
    return df


def process_dates(df):
    df['Post Date'] = pd.to_datetime(df['Post Date'], errors='coerce')
    df['Days Since Posted'] = (pd.to_datetime('today') - df['Post Date']).dt.days
    return df


def get_pay_band(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            pay_band_element = soup.select_one("#payscheme-band")
            if pay_band_element:
                return pay_band_element.get_text(strip=True)
    except:
        pass
    return "Not found"


def enrich_with_pay_band(df):
    df['Pay Band'] = df['URL'].apply(get_pay_band)
    return df


def filter_by_band(df, min_band=3):
    def extract_band_number(band_text):
        match = re.search(r'(\d+)', band_text)
        return int(match.group(1)) if match else None

    df['Band Number'] = df['Pay Band'].apply(extract_band_number)
    df = df[df['Band Number'].notnull() & (df['Band Number'] >= min_band)]
    return df

# === Streamlit App ===
st.set_page_config("NHS Job Finder", layout="wide")
st.title("🔍 NHS Job Scraper (Visa Sponsorship / Band Filter)")

with st.sidebar:
    st.markdown("### Search Criteria")
    keyword = st.text_input("Job Keyword", value="visa sponsorship")
    pages = st.number_input("Number of Pages", min_value=1, max_value=100, value=10)
    band_min = st.slider("Minimum Band", min_value=1, max_value=9, value=3)
    run_search = st.button("Search NHS Jobs")

if run_search:
    progress_bar = st.progress(0.0)
    st.info("Fetching job listings. Please wait...")

    df = fetch_nhs_jobs(keyword=keyword, max_pages=pages, update_progress=lambda p: progress_bar.progress(p))

    if df.empty:
        st.warning("No jobs found for the given criteria.")
    else:
        st.success(f"Fetched {len(df)} jobs. Processing now...")

        df = extract_salary_fields(df)
        df = process_dates(df)
        df = enrich_with_pay_band(df)
        df = filter_by_band(df, min_band=band_min)

        if df.empty:
            st.warning("No jobs matched the minimum band filter.")
        else:
            st.success(f"{len(df)} job(s) matched your filters.")
            st.dataframe(df)

            # Download option
            csv = df.to_csv(index=False)
            st.download_button("📥 Download CSV", csv, "nhs_jobs_filtered.csv", "text/csv")
