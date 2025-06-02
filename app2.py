import streamlit as st
import pandas as pd
import numpy as np
import re
import requests
from bs4 import BeautifulSoup
from rapidfuzz import fuzz
from datetime import datetime
import smtplib
from email.message import EmailMessage
import ssl

def send_email_with_csv(receiver_email, subject, body, csv_data, filename="nhs_jobs.csv"):
    sender_email = "your.email@example.com"   # Replace with your email
    sender_password = "your_app_password"     # Use App Password if using Gmail

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg.set_content(body)

    msg.add_attachment(csv_data.encode(), maintype="text", subtype="csv", filename=filename)

    # Gmail SMTP
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)


# --- Helper: Scrape NHS Jobs ---
def fetch_nhs_jobs(keyword, salary_from, max_pages, location_filter, band_from, band_to, progress_callback=None):
    base_url = "https://www.jobs.nhs.uk/api/v1/search_xml"
    jobs = []
    for page in range(1, max_pages + 1):
        params = {
            "keyword": keyword,
            "page": page,
            "sort": "publicationDateDesc",
            "contractType": "Permanent",
            "salaryFrom": salary_from
        }

        if location_filter:
            params["location"] = location_filter
            params["distance"] = 100  # arbitrary radius

        response = requests.get(base_url, params=params)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.content, "xml")
        listings = soup.find_all("vacancyDetails")

        if not listings:
            break

        for job in listings:
            title = job.title.text if job.title else ""
            if fuzz.token_set_ratio(keyword.lower(), title.lower()) < 80:
                continue

            jobs.append({
                "Title": title,
                "Employer": job.employer.text if job.employer else "",
                "Description": job.description.text if job.description else "",
                "Location(s)": ", ".join([loc.text for loc in job.find_all("locations")]),
                "Salary": job.salary.text if job.salary else "",
                "Closing Date": job.closeDate.text if job.closeDate else "",
                "Post Date": job.postDate.text if job.postDate else "",
                "Reference": job.reference.text if job.reference else "",
                "URL": job.url.text if job.url else ""
            })

        if progress_callback:
            progress_callback(page / max_pages)

    return pd.DataFrame(jobs)

# --- Helper: Clean salary ---
def parse_salary_fields(df):
    def parse(row):
        match_range = re.search(r'£?([\d,\.]+)\s+to\s+£?([\d,\.]+)', row)
        match_single = re.search(r'£?([\d,\.]+)', row)
        if match_range:
            return float(match_range.group(1).replace(",", "")), float(match_range.group(2).replace(",", ""))
        elif match_single:
            val = float(match_single.group(1).replace(",", ""))
            return val, val
        return np.nan, np.nan

    df[['Min Salary', 'Max Salary']] = df['Salary'].apply(lambda s: pd.Series(parse(s)))
    return df

# --- Helper: Parse date ---
def clean_dates(df):
    df['Post Date'] = pd.to_datetime(df['Post Date'], errors='coerce')
    df['Days Since Posted'] = (pd.to_datetime('today') - df['Post Date']).dt.days
    return df

# --- Helper: Get band from job page ---
def get_pay_band(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            band = soup.select_one("#payscheme-band")
            return band.get_text(strip=True) if band else "Not found"
    except:
        pass
    return "Not found"

# --- Helper: Band filter ---
def apply_band_filter(df, band_from, band_to):
    st.info("Fetching job details (band + job type)... ⏳")
    def extract_number(text):
        match = re.search(r'(\d+)', text)
        return int(match.group(1)) if match else None

    df['Pay Band'] = df['URL'].apply(get_pay_band)
    df['Band Num'] = df['Pay Band'].apply(extract_number)
    df = df[df['Band Num'].notnull() & (df['Band Num'] >= band_from) & (df['Band Num'] <= band_to)]
    return df

# --- Streamlit UI ---
st.set_page_config("NHS Job Search Tool", layout="wide")
st.title("🔍 NHS Job Scraper with Band Filtering")

with st.sidebar.form("search_form"):
    st.markdown("### Filter Criteria")
    keyword = st.text_input("Keyword", value="project manager")
    salary_from = st.number_input("Minimum Salary (£)", value=24000, min_value=0, step=1000)
    band_from = st.number_input("Band From", value=3, min_value=1, max_value=9)
    band_to = st.number_input("Band To", value=8, min_value=1, max_value=9)
    pages = st.number_input("Pages to Search", value=5, min_value=1, max_value=10000)
    location = st.text_input("Location (optional)", value="")

    submit = st.form_submit_button("Search")

if submit:
    progress = st.progress(0)
    status = st.empty()

    df = fetch_nhs_jobs(
        keyword=keyword,
        salary_from=salary_from,
        max_pages=pages,
        location_filter=location,
        band_from=band_from,
        band_to=band_to,
        progress_callback=lambda p: progress.progress(p)
    )

    if df.empty:
        st.error("No matching jobs found.")
    else:
        df = parse_salary_fields(df)
        df = clean_dates(df)
        df = apply_band_filter(df, band_from, band_to)

        if df.empty:
            st.warning("No jobs matched the selected band filters.")
        else:
            st.success(f"✅ Found {len(df)} job(s) matching your filters.")
            st.dataframe(df)

            # Prepare CSV
            csv = df.to_csv(index=False)

            # Download Button
            st.download_button("📥 Download Results as CSV", csv, "nhs_jobs.csv", "text/csv")

            # Email Option
            with st.expander("📤 Send Results to Email"):
                receiver_email = st.text_input("Recipient Email Address", placeholder="you@example.com")
                send = st.button("Send Email")

                if send:
                    if not receiver_email or "@" not in receiver_email:
                        st.error("❌ Please enter a valid email address.")
                    else:
                        try:
                            send_email_with_csv(
                                receiver_email=receiver_email,
                                subject="NHS Job Search Results",
                                body="Attached are your NHS job search results.",
                                csv_data=csv
                            )
                            st.success(f"📧 Email successfully sent to {receiver_email}")
                        except Exception as e:
                            st.error(f"❌ Failed to send email: {e}")

