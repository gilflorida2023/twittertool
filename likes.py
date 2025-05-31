import streamlit as st
import os
import json
import time
import random
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

COOKIE_FILE = "twitter_cookies.json"

def configure_chrome_options():
    options = Options()
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

def perform_likes(driver, search_query, like_count):
    # Calculate date range for recent tweets (last 10 days)
    current_date = datetime.now()
    ten_days_ago = current_date - timedelta(days=10)
    date_str = ten_days_ago.strftime("%Y-%m-%d")
    
    # Build search URL with filters
    search_url = f"https://x.com/search?q={search_query} since:{date_str}&src=typed_query"
    driver.get(search_url)
    time.sleep(5)  # Give more time for initial load
    
    # Wait for search results to load
    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, '//article'))
        )
        st.info("Search results loaded successfully")
    except:
        st.warning("Timed out waiting for search results. Trying alternative approach...")
        # Try alternative loading method
        driver.refresh()
        time.sleep(5)
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, '//article'))
            )
        except:
            st.error("Failed to load search results. Please try a different search term.")
            return 0

    liked = 0
    attempts = 0
    max_attempts = like_count * 15
    
    # Create a set to track liked tweet IDs to avoid duplicates
    liked_tweet_ids = set()

    while liked < like_count and attempts < max_attempts:
        attempts += 1
        
        # Get all visible tweet articles
        tweets = driver.find_elements(By.XPATH, '//article')
        st.info(f"Found {len(tweets)} tweets on page")
        
        if not tweets:
            st.warning("No tweets found. Scrolling to load more...")
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(3)
            continue
        
        # Filter tweets that haven't been liked yet and are visible
        likeable_tweets = []
        for tweet in tweets:
            try:
                # Get tweet ID for tracking
                tweet_id = tweet.get_attribute("aria-labelledby") or tweet.get_attribute("data-testid")
                if not tweet_id:
                    continue
                
                # Skip if we've already liked this tweet
                if tweet_id in liked_tweet_ids:
                    continue
                
                # Skip promoted tweets
                try:
                    if tweet.find_element(By.XPATH, './/span[contains(text(), "Promoted")]'):
                        continue
                except:
                    pass
                
                # NEW: Target the like button using multiple reliable attributes
                try:
                    # Using data-testid="like" as primary selector
                    like_button = tweet.find_element(By.XPATH, './/button[@data-testid="like"]')
                except:
                    try:
                        # Fallback to aria-label containing "Like"
                        like_button = tweet.find_element(By.XPATH, './/button[contains(@aria-label, "Like")]')
                    except:
                        try:
                            # Fallback to SVG with known path data
                            like_button = tweet.find_element(
                                By.XPATH, 
                                './/button[.//path[@d="M16.697 5.5c-1.222-.06-2.679.51-3.89 2.16l-.805 1.09-.806-1.09C9.984 6.01 8.526 5.44 7.304 5.5c-1.243.07-2.349.78-2.91 1.91-.552 1.12-.633 2.78.479 4.82 1.074 1.97 3.257 4.27 7.129 6.61 3.87-2.34 6.052-4.64 7.126-6.61 1.111-2.04 1.03-3.7.477-4.82-.561-1.13-1.666-1.84-2.908-1.91zm4.187 7.69c-1.351 2.48-4.001 5.12-8.379 7.67l-.503.3-.504-.3c-4.379-2.55-7.029-5.19-8.382-7.67-1.36-2.5-1.41-4.86-.514-6.67.887-1.79 2.647-2.91 4.601-3.01 1.651-.09 3.368.56 4.798 2.01 1.429-1.45 3.146-2.1 4.796-2.01 1.954.1 3.714 1.22 4.601 3.01.896 1.81.846 4.17-.514 6.67z"]]'
                            )
                        except:
                            continue
                
                # Only include if visible and clickable
                if like_button.is_displayed() and like_button.is_enabled():
                    likeable_tweets.append((tweet, like_button, tweet_id))
            except Exception as e:
                # st.warning(f"Error processing tweet: {str(e)}")
                continue
        
        st.info(f"Found {len(likeable_tweets)} likeable tweets")
        
        if not likeable_tweets:
            st.warning("No likeable tweets found. Scrolling...")
            # Scroll down to load more tweets
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(2)
            continue
        
        # Randomly select a tweet to like
        tweet, like_button, tweet_id = random.choice(likeable_tweets)
        
        try:
            # Scroll to the tweet
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", tweet)
            time.sleep(1)
            
            # Hover over the button first
            ActionChains(driver).move_to_element(like_button).pause(0.5).perform()
            
            # Click using JavaScript
            driver.execute_script("arguments[0].click();", like_button)
            liked += 1
            liked_tweet_ids.add(tweet_id)
            st.success(f"Liked tweet #{liked}")
            
            # Visual confirmation
            st.balloons()
            
            # Wait after liking
            time.sleep(random.uniform(2.0, 3.0))
            
        except Exception as e:
            st.warning(f"Error liking tweet: {str(e)}")
        
        # Scroll to load new content
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(random.uniform(1.0, 1.5))  # Random delay between tweets
    
    return liked

def main():
    st.title("X/Twitter Automated Liking Tool")
    st.subheader("Randomly like recent tweets matching your search criteria")
    
    # Add some information about the tool
    with st.expander("How to use this tool"):
        st.markdown("""
        1. Export your Twitter cookies using a browser extension (EditThisCookie or Cookie-Editor)
        2. Save the cookies as `twitter_cookies.json` in the same directory
        3. Click 'Start Session with Cookies' to log in
        4. Enter your search criteria and number of likes
        5. Click 'Start Liking'
        
        **Notes:**
        - Only tweets from the last 10 days will be considered
        - The tool will randomly select tweets to like
        - Delays are built in to avoid detection
        - Browser will automatically close after completion
        """)

    if not os.path.exists(COOKIE_FILE):
        st.error(
            f"Cookie file '{COOKIE_FILE}' not found. "
            "Please export your cookies from Chrome and place the file here."
        )
        st.info(
            "**How to export cookies:**\n"
            "1. Log in to https://x.com in Chrome\n"
            "2. Install the 'EditThisCookie' extension\n"
            "3. Click the extension icon and select 'Export Cookies'\n"
            "4. Save as 'twitter_cookies.json' in this folder\n"
            "5. Refresh this page"
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
                try:
                    driver = initialize_driver()
                    load_cookies(driver, COOKIE_FILE)
                    driver.get("https://x.com/home")
                    time.sleep(3)
                    
                    # Take screenshot for debugging
                    driver.save_screenshot("login_check.png")
                    st.image("login_check.png", caption="Browser View", use_column_width=True)
                    
                    if is_logged_in(driver):
                        st.success("Logged in with cookies! 🎉")
                        st.session_state.logged_in = True
                        st.session_state.driver = driver
                    else:
                        st.error("Failed to log in with cookies. Cookies may be expired or invalid.")
                        driver.quit()
                except Exception as e:
                    st.error(f"Error during login: {str(e)}")
    
    # Show liking interface if logged in
    if st.session_state.logged_in and st.session_state.driver:
        st.success("You are logged in!")
        
        with st.form("like_form"):
            st.subheader("Search Criteria")
            search_query = st.text_input("Search query", "technology", 
                                        help="Enter keywords, hashtags, or phrases to search for")
            
            like_count = st.slider(
                "Number of likes to generate", 
                min_value=1, 
                max_value=3000, 
                value=10,
                help="Number of tweets to randomly like"
            )
            
            st.markdown("**Note:** The tool will search for recent tweets matching your query and randomly like them")
            submit = st.form_submit_button("Start Liking")
        
        if submit:
            with st.spinner(f"Searching for recent '{search_query}' tweets and liking randomly..."):
                try:
                    liked = perform_likes(st.session_state.driver, search_query, like_count)
                    if liked > 0:
                        st.success(f"Successfully liked {liked} tweets! 🎉")
                        st.balloons()
                    else:
                        st.warning("No tweets were liked. Try a different search term or check the browser view.")
                except Exception as e:
                    st.error(f"Error during liking process: {str(e)}")
            
            # Clean up after completion
            try:
                st.session_state.driver.quit()
            except:
                pass
            st.session_state.logged_in = False
            st.session_state.driver = None
            st.info("Browser session closed. Start a new session to perform more actions.")

if __name__ == "__main__":
    main()
