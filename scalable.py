import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
import pandas as pd
import numpy as np
import re
from datetime import datetime

# === Fetch Jobs from NHS API ===
def fetch_nhs_jobs(keyword="visa sponsorship", max_pages=100):
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
            print(f"Error on page {page}: {response.status_code}")
            break

        soup = BeautifulSoup(response.content, "xml")
        vacancy_list = soup.find_all("vacancyDetails")

        if not vacancy_list:
            break

        for job in vacancy_list:
            title_text = job.title.text if job.title else ""
            similarity = fuzz.token_set_ratio(keyword.lower(), title_text.lower())

            if similarity < 80:
                continue  # Skip low-similarity titles

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

        print(f"Page {page} processed. Jobs collected so far: {len(job_records)}")
        page += 1

    return pd.DataFrame(job_records)

# === Extract Min/Max Salary from Salary Text ===
def extract_salary_fields(df):
    def parse_salary(row):
        text = row.get('Salary', '')
        match_range = re.search(r'£?([\d,\.]+)\s+to\s+£?([\d,\.]+)', text)
        match_single = re.search(r'£?([\d,\.]+)', text)

        if match_range:
            min_salary = float(match_range.group(1).replace(",", ""))
            max_salary = float(match_range.group(2).replace(",", ""))
        elif match_single:
            min_salary = max_salary = float(match_single.group(1).replace(",", ""))
        else:
            min_salary = max_salary = np.nan

        return pd.Series([min_salary, max_salary])

    df[['Min Salary', 'Max Salary']] = df.apply(parse_salary, axis=1)
    return df

# === Parse Posting Date to Datetime and Add Days Since Posted ===
def process_dates(df):
    df['Post Date'] = pd.to_datetime(df['Post Date'], errors='coerce')
    df['Days Since Posted'] = (pd.to_datetime('today') - df['Post Date']).dt.days
    return df

# === Get Pay Band from Job URL ===
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

# === Enrich DataFrame with Pay Band ===
def enrich_with_pay_band(df):
    print("Fetching pay bands (this may take a few minutes)...")
    df['Pay Band'] = df['URL'].apply(get_pay_band)
    return df

# === Filter by Pay Band 3 and Above ===
def filter_by_band(df, min_band=3):
    def extract_band_number(band_text):
        match = re.search(r'(\d+)', band_text)
        return int(match.group(1)) if match else None

    df['Band Number'] = df['Pay Band'].apply(extract_band_number)
    df = df[df['Band Number'].notnull() & (df['Band Number'] >= min_band)]
    return df

# === Save Final DataFrame to CSV ===
def save_to_csv(df, filename="nhs_jobs_filtered.csv"):
    df.to_csv(filename, index=False)
    print(f"✅ Saved {len(df)} jobs to {filename}")

# === Main Workflow ===
def main():
    keyword = input("Enter job keyword (e.g., visa sponsorship): ").strip()
    df = fetch_nhs_jobs(keyword=keyword)
    if df.empty:
        print("No jobs found.")
        return

    df = extract_salary_fields(df)
    df = process_dates(df)
    df = enrich_with_pay_band(df)
    df = filter_by_band(df)
    save_to_csv(df)

if __name__ == "__main__":
    main()
