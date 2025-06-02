from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pandas as pd
import time

# Setup WebDriver
CHROMEDRIVER_PATH = "C:/Users/hp/Desktop/Scalable Hire/chromedriver-win64/chromedriver.exe"
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service)

# Go to NHS Jobs site
driver.get("https://www.jobs.nhs.uk/candidate/search/results")

# Wait for page and search box to load
WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.ID, "keyword"))
)

# Enter search keyword
search_box = driver.find_element(By.ID, "keyword")
search_box.clear()
search_box.send_keys("visa sponsorship")

# Submit search
search_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
search_button.click()

# Wait for results
WebDriverWait(driver, 10).until(
    EC.presence_of_all_elements_located((By.CLASS_NAME, "job-summary"))
)

# Extract job cards from first page
jobs = driver.find_elements(By.CLASS_NAME, "job-summary")


