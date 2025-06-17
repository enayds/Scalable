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


def job_detail_passes_filters(job_url, contract_type, working_pattern, filter_sponsorship, sponsorship_preference,
                               filter_license, license_preference):
    try:
        detail_response = requests.get(job_url, timeout=10)
        detail_soup = BeautifulSoup(detail_response.text, "html.parser")

        contract = extract_text(detail_soup, "#hj-job-summary > div > div > div > dl:nth-child(1) > dd:nth-child(6)")
        pattern = extract_text(detail_soup, "#hj-job-summary > div > div > div > dl:nth-child(1) > dd:nth-child(8)")
        description_block = detail_soup.get_text(separator=" ", strip=True)
        requirements = analyze_job_requirements(description_block)
        sponsorship_status = requirements["sponsorship"]
        license_status = requirements["license"]

        

        info = {
            "sponsorship": sponsorship_status,
            "license": license_status
        }


        # Filter logic
        if contract_type and contract_type.lower() not in contract.lower():
            return False, info
        if working_pattern and working_pattern.lower() not in pattern.lower():
            return False, info
        if filter_sponsorship:
            if sponsorship_preference == "Offered" and sponsorship_status == "Not Offered":
                return False, info
            if sponsorship_preference == "Not Offered" and sponsorship_status == "Offered":
                return False, info
        if filter_license:
            if license_preference == "Requires License" and license_status == "Does Not Require License":
                return False, info
            if license_preference == "Does Not Require License" and license_status == "Requires License":
                return False, info


        


        return True, info
    except requests.RequestException:
        return False, {"Requires Sponsorship": None, "Requires Driver's License": None}



def process_single_job(job, keywords, min_salary, contract_type, working_pattern, min_band, max_band,
                       filter_sponsorship, sponsorship_preference,
                       filter_license, license_preference):
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

    # ✅ Updated to check against all keywords
    if not any(partial_ratio(title.lower(), kw.lower()) >= 70 for kw in keywords):
        return None
    if not filter_by_band(band, min_band, max_band):
        return None
    if not filter_by_salary(salary, min_salary):
        return None

    passed, info = job_detail_passes_filters(
        job_url, contract_type, working_pattern, filter_sponsorship, sponsorship_preference,
    filter_license, license_preference
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
        "Sponsorship Status": info.get("sponsorship", "Likely Offered"),
        "License Requirement": info.get("license", "Possibly Not Required")
    }




def scrape_trac_jobs(keywords, min_salary, contract_type, working_pattern, min_band, max_band,
                pages_to_scrape=3):
    all_results = []

    keyword_placeholders = {kw: st.empty() for kw in keywords}

    for keyword in keywords:
        keyword_placeholder = keyword_placeholders[keyword]
        keyword_placeholder.markdown(f"### 🔍 Searching for: `{keyword}`")
        progress_bar = keyword_placeholder.progress(0)

        total_jobs_est = pages_to_scrape * 10
        job_counter = 0

        for page in range(1, pages_to_scrape + 1):
            url = generate_trac_url(keyword, page)
            try:
                response = requests.get(url, timeout=10)
                soup = BeautifulSoup(response.text, "html.parser")
                job_listings = extract_job_listings(soup)
            except Exception:
                continue  # skip failed requests

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [
                    executor.submit(
                        process_single_job, job, keywords, min_salary, contract_type,
                        working_pattern, min_band, max_band, filter_sponsorship, sponsorship_preference,
                        filter_license, license_preference
                    ) for job in job_listings
                ]

                for future in futures:
                    result = future.result()
                    job_counter += 1
                    progress_bar.progress(min(job_counter / total_jobs_est, 1.0))
                    if result:
                        all_results.append(result)

            time.sleep(1)

        progress_bar.progress(1.0)
        keyword_placeholder.markdown(f"✅ Done searching for: `{keyword}`")

    return pd.DataFrame(all_results)


def analyze_job_requirements(description: str) -> dict:
    """
    Analyze a job description and return:
        - 'sponsorship': "Offered" | "Not Offered" | "Unknown"
        - 'license': "Requires License" | "Does Not Require License" | "Unknown"
    """
    description = description.lower()
    result = {
        "sponsorship": "Unknown",
        "license": "Possibly Not Required"
    }

    # Sponsorship logic
    
    if any(phrase in description for phrase in [
    "not offer sponsorship", "no sponsorship", "unable to sponsor",
    "not able to sponsor", "sponsorship is not available",
    "cannot provide visa", "cannot sponsor", "unable to provide sponsorship"
    ]):
        result["sponsorship"] = "Not Offered"
    else:
        result["sponsorship"] = "Offered"

    # print(f"This is where we are, {result['sponsorship']}")


    # License logic
    if "no driving license required" in description:
        result["license"] = "Does Not Require License"
    elif any(phrase in description for phrase in [
        "valid driver", "full driving licence", "uk driving license",
        "requires own transport"
    ]):
        result["license"] = "Requires License"

    return result


# Streamlit UI
def job_filter_sidebar():
    st.sidebar.header("🔍 Job Search Filters")

    keyword_input = st.sidebar.text_input("Keywords (comma-separated)", value="Healthcare support worker")
    keywords = [kw.strip() for kw in keyword_input.split(",") if kw.strip()]
    min_salary = st.sidebar.number_input("Minimum Salary (£)", min_value=0, value=24500)

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

    filter_sponsorship = st.sidebar.checkbox("Filter by Sponsorship", value=False)
    sponsorship_preference = st.sidebar.radio(
        "Sponsorship Requirement",
        ["Offered", "Not Offered"],
        index=0,
        disabled=not filter_sponsorship
    )

    filter_license = st.sidebar.checkbox("Filter by Driver's License", value=False)
    license_preference = st.sidebar.radio(
        "License Requirement",
        ["Requires License", "Does Not Require License"],
        index=0,
        disabled=not filter_license
    )


    pages_to_scrape = st.sidebar.number_input(
    "Pages to Scrape", min_value=1, max_value=50, value=3, step=1
)
    search = st.sidebar.button("Search Jobs 🔎")

    return keywords, min_salary, contract_type, working_pattern, min_band, max_band, pages_to_scrape, search, filter_sponsorship, sponsorship_preference, filter_license, license_preference



# 🎯 Main UI
st.title("🧰 Trac Job Scraper (Optimized)")

(
    keywords,  # this is now a list of keywords
    min_salary,
    contract_type,
    working_pattern,
    min_band,
    max_band,
    pages_to_scrape,
    search, 
    filter_sponsorship, sponsorship_preference,
    filter_license, license_preference
) = job_filter_sidebar()

if search:
    st.info("🔄 Scraping in progress... Please wait.")

    df = scrape_trac_jobs(
        keywords,  # pass the list here
        min_salary,
        contract_type,
        working_pattern,
        min_band,
        max_band,
        pages_to_scrape
    )

    st.session_state["df_trac"] = df

    if df.empty:
        st.warning("❌ No jobs found matching your filters.")
    else:
        st.success(f"✅ Found {len(df)} job(s) matching your filters.")
        st.dataframe(df.head(20))

        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download results as CSV",
            data=csv,
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
