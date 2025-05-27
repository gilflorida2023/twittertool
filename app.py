import streamlit as st
import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager

COOKIE_FILE = "twitter_cookies.json"

def configure_chrome_options():
    options = Options()
    # Headless REMOVED for visibility and to avoid bot detection
    # options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return options

def initialize_driver():
    options = configure_chrome_options()
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def load_cookies(driver, cookie_file):
    with open(cookie_file, "r") as f:
        cookies = json.load(f)
    driver.get("https://x.com/")
    for cookie in cookies:
        cookie.pop('sameSite', None)
        if 'expiry' in cookie:
            cookie['expiry'] = int(cookie['expiry'])
        try:
            driver.add_cookie(cookie)
        except Exception:
            pass

def is_logged_in(driver):
    driver.get("https://x.com/home")
    time.sleep(3)
    return "Home / X" in driver.title or "profile" in driver.page_source.lower()

def go_to_profile(driver):
    # Try both common selectors for the profile tab
    try:
        profile_link = driver.find_element(By.XPATH, '//a[@aria-label="Profile"]')
    except:
        try:
            profile_link = driver.find_element(By.XPATH, '//a[@data-testid="AppTabBar_Profile_Link"]')
        except:
            profile_link = None
    if profile_link:
        profile_link.click()
        time.sleep(3)
        return True
    return False

def go_to_likes_tab(driver):
    try:
        likes_tab = driver.find_element(By.XPATH, '//a[.//span[text()="Likes"]]')
        likes_tab.click()
        time.sleep(3)
        return True
    except Exception as e:
        print("Could not find Likes tab:", e)
        return False

def delete_likes(driver):
    # Go to profile first
    if not go_to_profile(driver):
        st.warning("Could not find profile tab. Make sure you are logged in.")
        return 0
    # Click the Likes tab
    if not go_to_likes_tab(driver):
        st.warning("Could not find Likes tab on profile.")
        return 0

    time.sleep(5)
    deleted = 0
    scroll_attempts = 0
    max_empty_scrolls = 5  # Stop after 5 scrolls in a row with no new likes found
    empty_scrolls = 0
    wait = WebDriverWait(driver, 10)

    while empty_scrolls < max_empty_scrolls:
        try:
            unlike_buttons = wait.until(
                EC.presence_of_all_elements_located((By.XPATH, '//*[@data-testid="unlike"]'))
            )
            st.write(f"Found {len(unlike_buttons)} Unlike buttons on scroll {scroll_attempts+1}")
            if not unlike_buttons:
                empty_scrolls += 1
                st.write(f"No Unlike buttons found. Empty scrolls: {empty_scrolls}/{max_empty_scrolls}")
            else:
                empty_scrolls = 0  # Reset if we found likes
                for btn in unlike_buttons:
                    try:
                        ActionChains(driver).move_to_element(btn).perform()
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1.5)
                        deleted += 1
                        st.write(f"Deleted like #{deleted}")
                    except Exception as e:
                        st.write(f"Failed to click Unlike button: {e}")
                        continue
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            scroll_attempts += 1
        except Exception as e:
            st.warning(f"Error: {e}")
            break
    return deleted

def main():
    st.title("X/Twitter Likes Deletion Tool (Delete ALL Likes)")

    if not os.path.exists(COOKIE_FILE):
        st.error(
            f"Cookie file '{COOKIE_FILE}' not found. "
            "Please export your cookies from Chrome and place the file here."
        )
        st.info(
            "How to export cookies:\n"
            "1. Log in to https://x.com in Chrome.\n"
            "2. Use the 'EditThisCookie' or 'Cookie-Editor' extension to export cookies as JSON.\n"
            "3. Save as 'twitter_cookies.json' in this folder."
        )
        return

    # Initialize session state
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "driver" not in st.session_state:
        st.session_state.driver = None

    # Login block
    if not st.session_state.logged_in:
        if st.button("Start Session with Cookies"):
            with st.spinner("Launching browser and loading cookies..."):
                driver = initialize_driver()
                load_cookies(driver, COOKIE_FILE)
                driver.get("https://x.com/home")
                time.sleep(3)
                if is_logged_in(driver):
                    st.success("Logged in with cookies! 🎉")
                    st.session_state.logged_in = True
                    st.session_state.driver = driver
                else:
                    st.error("Failed to log in with cookies. Cookies may be expired or invalid.")
                    driver.quit()
    # Always show the form if logged in
    if st.session_state.logged_in and st.session_state.driver:
        st.success("You are logged in!")
        with st.form("delete_likes_form"):
            submit = st.form_submit_button("Delete ALL Likes")
        if submit:
            with st.spinner("Deleting all likes..."):
                deleted = delete_likes(st.session_state.driver)
                st.success(f"Deleted {deleted} likes!")
            st.session_state.driver.quit()
            st.session_state.logged_in = False
            st.session_state.driver = None

if __name__ == "__main__":
    main()

