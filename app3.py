from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# === Setup ChromeDriver path ===
CHROMEDRIVER_PATH = "C:/Users/hp/Desktop/Scalable Hire/chromedriver-win64/chromedriver.exe"
service = Service(CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service)

try:
    # === Step 1: Open NHS Jobs ===
    driver.get("https://www.jobs.nhs.uk/candidate/search/results")
    driver.maximize_window()

    # === Step 2: Enter search keyword ===
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#keyword"))
    )
    search_input = driver.find_element(By.CSS_SELECTOR, "#keyword")
    search_input.clear()
    search_input.send_keys("visa sponsorship")  # You can change this keyword

    # === Step 3: Click search button ===
    driver.find_element(By.CSS_SELECTOR, "#search").click()

    # === Step 4: Wait for results to load ===
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, "job-summary"))
    )

    # === Step 5: Click to expand Contract Type filter ===
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#refineFilter > form > fieldset > details:nth-child(16) > summary > span"))
    ).click()

    # === Step 6: Click "Permanent" option ===
    WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#contract-type-details > div > div:nth-child(1) > label"))
    ).click()

    print("✅ Search and filter applied successfully.")

    # Optional pause to see the result visually
    time.sleep(5)

finally:
    # driver.quit()
    pass
