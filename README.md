
# 🧰 NHS & Trac Job Scraper + Google Drive Uploader

This project is a powerful and streamlined tool for scraping job listings from NHS and Trac websites, applying smart filters, and uploading categorized data directly to Google Drive as Excel files.

Each job category is saved in its own sheet, and files are named by date and source platform (e.g., `nhs_2025-06-13.xlsx`, `trac_2025-06-13.xlsx`).

---

## 🚀 Features

- 🔍 **Real-time job search** from [jobs.nhs.uk](https://www.jobs.nhs.uk) and [healthjobsuk.com](https://www.healthjobsuk.com)
- 🎯 Apply filters: salary, contract type, working pattern, band level, sponsorship
- 🧠 Keyword matching using fuzzy logic (via `rapidfuzz`)
- 📄 View & download results directly from the UI
- 📤 Upload results to **Google Drive** with:
  - Date-based filenames
  - Sheet-based job category separation (e.g. Admin, Tech, Finance)
- 💾 Safe deduplication: prevents overwriting existing entries

---

## ⚙️ Setup Instructions

### 1. Clone the Repo

```bash
git clone https://github.com/yourusername/job-scraper-drive-uploader.git
cd job-scraper-drive-uploader
````

### 2. Install Requirements

```bash
pip install -r requirements.txt
```

> 🔐 Make sure your environment supports Streamlit and OAuth (for Google API).

### 3. Set Up Google Drive API Credentials

Create a `.streamlit/secrets.toml` file with this format:

```toml
[google]
client_id = "YOUR_CLIENT_ID"
client_secret = "YOUR_CLIENT_SECRET"
refresh_token = "YOUR_REFRESH_TOKEN"
```

See [this guide](https://docs.streamlit.io/streamlit-cloud/secrets-management) on how to manage Streamlit secrets securely.

---

## 🧪 Running the Apps

### NHS App

```bash
streamlit run nhs_app.py
```

### Trac App

```bash
streamlit run trac_app.py
```

> Each app is independent and uploads to different Google Drive files (e.g., `nhs_2025-06-13.xlsx`, `trac_2025-06-13.xlsx`).

---

## 🛠 Filtering Options

* Job Keywords (comma-separated)
* Minimum Salary
* Contract Type & Working Pattern
* Band Range (e.g., Band 2 to Band 5)
* Optional Requirements:

  * Sponsorship must be offered
  * Driver’s license must not be required

---

## ⚖️ Scraping Guidelines & Best Practices

To ensure we respect the public job platforms (like NHS Jobs and HealthJobsUK), please follow these ethical scraping practices:

- ✅ **Use fewer pages** for testing (e.g. start with 1–2 pages)
- ⏱️ **Avoid repeated scraping** within short time intervals — allow several minutes between runs
- 🚦 The scraper includes a **1-second delay per page**, but you should still avoid rapid-fire requests
- ⚙️ Adjust `pages_to_scrape` in the sidebar slider to control how much data you pull
- 🔁 Do **not schedule automated background scraping** without explicit permission from the site owners

We built this tool for **manual job exploration and analysis**, not large-scale data extraction. Respecting site limits ensures we don't disrupt access for others.

---

## 📦 Deployment

You can deploy this app to:

* [Streamlit Community Cloud](https://streamlit.io/cloud)
* Heroku, Azure, or any Python-compatible hosting

---

## 🤝 Contributing

Pull requests are welcome! If you find a bug or want to propose a feature:

1. Fork the repo
2. Create a new branch (`git checkout -b feature/awesome`)
3. Commit your changes
4. Push to the branch and open a PR

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙌 Acknowledgments

* [Streamlit](https://streamlit.io)
* [Google Drive API](https://developers.google.com/drive)
* [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
* [RapidFuzz](https://github.com/maxbachmann/RapidFuzz)

---

**Happy scraping and organizing! 🧹📊**

```
