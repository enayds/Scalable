import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from rapidfuzz.fuzz import partial_ratio
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor
import streamlit as st
import gdrive_uploader 


# -------------------- Trac Scraper Helpers --------------------

def generate_trac_url(keyword, page=1):
    base_url = "https://www.healthjobsuk.com/job_list/ns"
    query_params = {
        "JobSearch_q": keyword,
        "JobSearch_QueryIntegratedSubmit": "Search",
        "_tr": "JobSearch",
        "_ts": "1",
        "page": page
    }
    return f"{base_url}?{urlencode(query_params)}"


def extract_job_listings(soup):
    return soup.select("#hj-job-list > ol > li")


def extract_text(soup, selector):
    element = soup.select_one(selector)
    return element.get_text(strip=True) if element else ""


def normalize_band(band_str):
    match = re.search(r'Band\s*(\d+)', band_str)
    return f"Band {match.group(1)}" if match else ""


def extract_salary_bounds(salary_str):
    salary_str = salary_str.replace(',', '')
    match = re.findall(r"£(\d{2,6})", salary_str)
    if len(match) == 2:
        return int(match[0]), int(match[1])
    elif len(match) == 1:
        return int(match[0]), int(match[0])
    return None, None


def filter_by_band(band_str, min_band, max_band):
    try:
        band_number = int(re.search(r'\d+', band_str).group())
        return min_band <= band_number <= max_band
    except Exception:
        return False


def filter_by_salary(salary_str, min_salary):
    digits = ''.join(filter(lambda x: x.isdigit() or x == '.', salary_str.replace(',', '')))
    try:
        salary = float(digits)
        return salary >= min_salary
    except ValueError:
        return False


def job_detail_passes_filters(job_url, contract_type, working_pattern, requires_license, sponsorship_required):
    try:
        detail_response = requests.get(job_url, timeout=10)
        detail_soup = BeautifulSoup(detail_response.text, "html.parser")

        contract = extract_text(detail_soup, "#hj-job-summary > div > div > div > dl:nth-child(1) > dd:nth-child(6)")
        pattern = extract_text(detail_soup, "#hj-job-summary > div > div > div > dl:nth-child(1) > dd:nth-child(8)")
        description = extract_text(detail_soup, "#hj-job-advert-overview").lower()

        info = {
            "Requires Sponsorship": "sponsorship" in description,
            "Requires Driver's License": "driver" in description or "licence" in description or "license" in description
        }

        if contract_type and contract_type.lower() not in contract.lower():
            return False, info
        if working_pattern and working_pattern.lower() not in pattern.lower():
            return False, info
        if requires_license and not info["Requires Driver's License"]:
            return False, info
        if not sponsorship_required and info["Requires Sponsorship"]:
            return False, info

        return True, info
    except requests.RequestException:
        return False, {"Requires Sponsorship": None, "Requires Driver's License": None}


def process_single_job(job, keyword, min_salary, contract_type, working_pattern, min_band, max_band,
                       requires_license, sponsorship_required):
    link_tag = job.select_one("a")
    if not link_tag:
        return None

    job_url = "https://www.healthjobsuk.com" + link_tag.get("href", "")
    title = extract_text(job, "div.hj-jobtitle.hj-job-detail")
    band_raw = extract_text(job, "div.hj-grade.hj-job-detail")
    band = normalize_band(band_raw)
    employer = extract_text(job, "div.hj-employer-details")
    salary = extract_text(job, "div.hj-salary.hj-job-detail")
    min_sal, max_sal = extract_salary_bounds(salary)

    if partial_ratio(title.lower(), keyword.lower()) < 70:
        return None
    if not filter_by_band(band, min_band, max_band):
        return None
    if not filter_by_salary(salary, min_salary):
        return None

    passed, info = job_detail_passes_filters(
        job_url, contract_type, working_pattern, requires_license, sponsorship_required
    )
    if not passed:
        return None

    return {
        "Title": title,
        "Employer": employer,
        "Band": band,
        "Min Salary": min_sal,
        "Max Salary": max_sal,
        "URL": job_url,
        "Does Not Offer Sponsorship": info.get("Requires Sponsorship"),
        "Requires Driver's License": info.get("Requires Driver's License")
    }


def scrape_trac_jobs(keyword, min_salary, contract_type, working_pattern, min_band, max_band,
                     requires_license=False, sponsorship_required=True, pages_to_scrape=3):
    all_results = []
    progress = st.progress(0)
    total_jobs_est = pages_to_scrape * 10
    job_counter = 0

    for page in range(1, pages_to_scrape + 1):
        url = generate_trac_url(keyword, page)
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        job_listings = extract_job_listings(soup)

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(
                process_single_job, job, keyword, min_salary, contract_type,
                working_pattern, min_band, max_band, requires_license, sponsorship_required
            ) for job in job_listings]

            for future in futures:
                result = future.result()
                job_counter += 1
                progress.progress(min(job_counter / total_jobs_est, 1.0))
                if result:
                    all_results.append(result)

        time.sleep(1)

    return pd.DataFrame(all_results)


# -------------------- Streamlit UI --------------------

st.title("🧰 Trac Job Scraper (Multi-Keyword + Drive Upload)")

# Sidebar filters
st.sidebar.header("🔍 Job Search Filters")

keywords_input = st.sidebar.text_input("Job Keywords (comma-separated)", value="Healthcare support worker")
keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]

min_salary = st.sidebar.number_input("Minimum Salary (£)", min_value=0, value=24000)

st.sidebar.markdown("#### Contract Details")
contract_type = st.sidebar.selectbox("Contract Type", ["", "Permanent", "Fixed Term", "Bank", "Secondment"], index = 1)
working_pattern = st.sidebar.selectbox("Working Pattern", ["", "Full Time", "Part Time", "Flexible Working"], index = 1)

st.sidebar.markdown("#### NHS Band Range")
col1, col2 = st.sidebar.columns(2)
with col1:
    min_band = st.number_input("Min Band", min_value=1, max_value=9, value=3, key="min_band")
with col2:
    max_band = st.number_input("Max Band", min_value=1, max_value=9, value=5, key="max_band")

st.sidebar.markdown("#### Other Requirements")
requires_license = st.sidebar.checkbox("Does Not Require Driver's License", value=True)
sponsorship_required = st.sidebar.checkbox("Must Offer Sponsorship", value=True)

pages_to_scrape = st.sidebar.slider("Pages to Scrape", 1, 30, 3)
run_search = st.sidebar.button("🔎 Search Jobs")

# Run scraping
if run_search:
    st.info("🔄 Starting search...")

    all_results = []
    status = st.empty()

    for keyword in keywords:
        status.info(f"🔍 Scraping jobs for keyword: **{keyword}**...")
        df_partial = scrape_trac_jobs(
            keyword, min_salary, contract_type, working_pattern,
            min_band, max_band, requires_license, sponsorship_required, pages_to_scrape
        )

        if not df_partial.empty:
            all_results.append(df_partial)

    status.empty()

    if not all_results:
        st.warning("❌ No jobs found across all keywords.")
    else:
        df_combined = pd.concat(all_results, ignore_index=True).drop_duplicates(subset=["URL"])
        sort_column = "Min Salary" if "Min Salary" in df_combined.columns else df_combined.columns[0]
        df_sorted = df_combined.sort_values(by=sort_column, ascending=False).reset_index(drop=True)

        st.session_state["df_trac"] = df_sorted

        st.success(f"✅ Found {len(df_sorted)} unique jobs across {len(keywords)} keyword(s).")
        st.dataframe(df_sorted.head(20))

        st.download_button(
            label="📥 Download results as CSV",
            data=df_sorted.to_csv(index=False),
            file_name="trac_jobs.csv",
            mime="text/csv"
        )

# -------------------- Upload to Google Drive --------------------

if "df_trac" in st.session_state:
    st.markdown("---")
    st.subheader("📤 Upload to Google Drive")
    st.markdown("#### Select Job Category for Upload")
    category = st.selectbox("Job Category", [
        "Admin",
        "Healthcare",
        "Business (PM, BA)",
        "Finance",
        "Tech"
    ], index=None, placeholder="Choose a category")

    if category and st.button("📤 Upload to Drive"):
        try:
            message = gdrive_uploader.upload_to_drive(st.session_state["df_trac"], category, prefix='trac')
            st.success("✅ Upload completed successfully!")
            st.caption(message)
        except Exception as e:
            st.error(f"❌ Upload failed: {str(e)}")
    elif not category:
        st.warning("⚠️ Please select a category before uploading.")
else:
    st.info("Please run a job search before uploading to Google Drive.")
