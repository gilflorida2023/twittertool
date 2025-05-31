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
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

COOKIE_FILE = "twitter_cookies.json"

def configure_chrome_options():
    options = Options()
    # options.add_argument("--headless=new") # Enable for headless operation if needed
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
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        st.error(f"Failed to initialize Chrome WebDriver: {e}")
        st.error("This might be due to an issue with ChromeDriverManager or your Chrome installation.")
        st.info("Consider: \n1. Ensuring Chrome is installed and up to date. \n2. Checking your internet connection. \n3. If behind a proxy, ChromeDriverManager might need proxy settings.")
        return None


def load_cookies(driver, cookie_file):
    with open(cookie_file, "r") as f:
        cookies = json.load(f)
    driver.get("https://x.com/") # Go to a page on the domain before adding cookies
    for cookie in cookies:
        # Remove sameSite if present, common issue, ensure domain is set
        if 'sameSite' in cookie:
            del cookie['sameSite']
        # Ensure domain is correct if it's missing or too broad
        if 'domain' not in cookie or 'x.com' not in cookie['domain']:
            cookie['domain'] = '.x.com' # Set to base domain
            
        if 'expiry' in cookie and cookie['expiry'] is not None:
            cookie['expiry'] = int(cookie['expiry'])
        else: # If expiry is None or not present, it's often a session cookie
            if 'expiry' in cookie: del cookie['expiry']


        try:
            driver.add_cookie(cookie)
        except Exception as e:
            st.warning(f"Could not add cookie '{cookie.get('name')}': {e}")
            pass
    st.write(f"Attempted to load {len(cookies)} cookies.")

def is_logged_in(driver):
    st.write("Navigating to x.com/home to check login status...")
    driver.get("https://x.com/home")
    time.sleep(4) # Increased sleep for page load and redirects
    current_url = driver.current_url
    page_title = driver.title
    st.write(f"Current URL: {current_url}, Page Title: {page_title}")

    if "login" in current_url or "i/flow/login" in current_url:
        st.write("Login page detected by URL.")
        return False
    
    # Check for a known element that indicates being logged in (e.g., primary column, home timeline)
    try:
        WebDriverWait(driver, 7).until(
            EC.presence_of_element_located((By.XPATH, '//div[@data-testid="primaryColumn"]//section[.//h1[contains(text(),"Home")]] | //main[@role="main"]//div[contains(@data-testid,"primaryColumn")]'))
        )
        st.write("Logged-in specific element (primary column/Home header) found.")
        return True
    except TimeoutException:
        st.write("Logged-in specific element not found after timeout. Assuming not logged in.")
        # driver.save_screenshot("debug_is_logged_in_fail.png")
        # st.image("debug_is_logged_in_fail.png", caption="Login Check Failed Screenshot")
        return False

def go_to_profile(driver):
    try:
        st.write("Attempting to navigate to profile...")
        profile_link_selectors = [
            '//a[@data-testid="AppTabBar_Profile_Link"]', # Primary test ID
            '//a[@aria-label="Profile"]', # Accessibility label
        ]
        profile_link_element = None
        for i, selector in enumerate(profile_link_selectors):
            try:
                st.write(f"Trying profile selector {i+1}: {selector}")
                profile_link_element = WebDriverWait(driver, 7).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                if profile_link_element:
                    st.write("Profile link found and clickable.")
                    break
            except TimeoutException:
                st.write(f"Profile selector {i+1} timed out.")
                continue
        
        if profile_link_element:
            driver.execute_script("arguments[0].click();", profile_link_element) # JS click can be more robust
            # ActionChains(driver).move_to_element(profile_link_element).click().perform()
            
            # Wait for profile page to load by checking for profile specific navigation
            WebDriverWait(driver, 10).until(
                 EC.presence_of_element_located((By.XPATH, '//nav[@aria-label="Profile timelines"]')) 
            )
            time.sleep(2) # Additional pause for content to settle
            st.write("Successfully navigated to profile page.")
            return True
        else:
            st.error("Profile link not found with any selector.")
            # driver.save_screenshot("debug_profile_link_not_found.png")
            # st.image("debug_profile_link_not_found.png")
            return False
    except Exception as e:
        st.error(f"Error navigating to profile: {e}")
        # driver.save_screenshot(f"debug_profile_nav_exception.png")
        # st.image(f"debug_profile_nav_exception.png")
        return False

def go_to_tab(driver, tab_name):
    try:
        st.write(f"Attempting to navigate to '{tab_name}' tab...")
        tab_xpath = f'//nav[@aria-label="Profile timelines"]//a[.//span[text()="{tab_name}"]]'
        st.write(f"Using XPath for tab: {tab_xpath}")
        tab_element = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, tab_xpath))
        )
        st.write(f"'{tab_name}' tab element found. Clicking...")
        driver.execute_script("arguments[0].click();", tab_element) # JS click
        # tab_element.click()

        WebDriverWait(driver, 10).until(
            EC.attribute_to_be((By.XPATH, tab_xpath), "aria-selected", "true")
        )
        time.sleep(2) 
        st.success(f"Successfully navigated to '{tab_name}' tab.")
        return True
    except TimeoutException:
        st.error(f"Could not find or click the '{tab_name}' tab. It might not be visible, the selector is outdated, or navigation confirmation failed.")
        # driver.save_screenshot(f"debug_goto_{tab_name}_tab_fail.png") 
        # st.image(f"debug_goto_{tab_name}_tab_fail.png")
        return False
    except Exception as e:
        st.error(f"Error navigating to '{tab_name}' tab: {e}")
        return False

def find_more_button(article_element):
    selectors = [
        './/div[@data-testid="caret"]', 
        './/div[contains(@aria-label,"More") and @role="button"]', # More flexible aria-label check
        './/div[@role="button" and @tabindex="0" and .//*[local-name()="svg" and (contains(@aria-label,"More") or @aria-label="Down arrow")]]',
    ]
    for i, sel in enumerate(selectors):
        # st.write(f"Trying 'More' button selector #{i+1}: {sel} within article.")
        try:
            btns = article_element.find_elements(By.XPATH, sel)
            if btns:
                for btn_idx, btn in enumerate(btns): 
                    if btn.is_displayed() and btn.is_enabled():
                        # st.write(f"'More' button found with selector #{i+1}, element index {btn_idx}.")
                        return btn
        except NoSuchElementException:
            continue
    # st.write("No 'More' button found with any selector in this article.")
    return None

def hover_and_find_more(driver, article, article_idx, tab_name):
    st.write(f"[{tab_name}] Article {article_idx+1}: Attempting to find 'More' button...")
    try:
        # Scroll article to center for better hover interaction
        # st.write(f"[{tab_name}] Article {article_idx+1}: Scrolling article to center.")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", article)
        time.sleep(0.5) # Pause for scrolling

        # st.write(f"[{tab_name}] Article {article_idx+1}: Hovering over article.")
        ActionChains(driver).move_to_element(article).perform()
        time.sleep(1.0) # Wait for 'More' button to appear after hover
        
        more_btn = find_more_button(article)
        if more_btn:
            st.write(f"[{tab_name}] Article {article_idx+1}: 'More' button found after hover.")
            return more_btn
        else: # Button not found after initial hover
             st.write(f"[{tab_name}] Article {article_idx+1}: 'More' button not found on first hover/scroll. Will try one more time with slight move.")
             # Try a slight move then re-hover, sometimes helps
             ActionChains(driver).move_by_offset(0,1).move_by_offset(0,-1).perform() # Jiggle mouse
             time.sleep(0.5)
             ActionChains(driver).move_to_element(article).perform()
             time.sleep(1.0)
             more_btn = find_more_button(article)
             if more_btn:
                 st.write(f"[{tab_name}] Article {article_idx+1}: 'More' button found after second hover attempt.")
                 return more_btn

        st.warning(f"[{tab_name}] Article {article_idx+1}: 'More' button NOT found after multiple attempts.")
        return None
    except StaleElementReferenceException:
        st.warning(f"[{tab_name}] Article {article_idx+1}: Stale element during hover/find_more. Article might have been removed or DOM refreshed.")
        return None
    except Exception as e:
        st.error(f"[{tab_name}] Article {article_idx+1}: Exception during hover/find_more_button: {e}")
        return None

def delete_empty_tweets_in_tab(driver, tab_name):
    if not go_to_profile(driver): return 0
    if not go_to_tab(driver, tab_name): return 0

    deleted_count = 0
    scroll_attempts = 0
    max_empty_scrolls = 3
    empty_scrolls_in_a_row = 0
    checked_article_ids = set()

    while empty_scrolls_in_a_row < max_empty_scrolls:
        st.write(f"--- Starting scroll pass {scroll_attempts + 1} for {tab_name} ---")
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//article[@data-testid="tweet"]'))
            )
            articles_on_page = driver.find_elements(By.XPATH, '//article[@data-testid="tweet"]')
            st.write(f"Found {len(articles_on_page)} articles on this pass.")
            
            if not articles_on_page and scroll_attempts > 0:
                empty_scrolls_in_a_row += 1
                st.write(f"No articles found on this scroll. Empty scroll count: {empty_scrolls_in_a_row}")
            
            new_articles_processed_this_pass = 0
            for idx, article_element in enumerate(articles_on_page):
                article_id_for_check = f"scroll{scroll_attempts}-idx{idx}" # Simple ID for now
                try:
                    # More robust ID from permalink if possible
                    permalink_elements = article_element.find_elements(By.XPATH, './/a[.//time and contains(@href,"/status/")]')
                    if permalink_elements and permalink_elements[0].get_attribute("href"):
                        article_id_for_check = permalink_elements[0].get_attribute("href")
                except: pass

                if article_id_for_check in checked_article_ids:
                    # st.write(f"Article {idx+1} (ID: {article_id_for_check.split('/')[-1]}) already checked. Skipping.")
                    continue
                
                new_articles_processed_this_pass += 1
                tweet_text_preview = article_element.text[:70].replace('\n', ' ')
                st.markdown(f"**Processing Article {idx+1} (ID: `{article_id_for_check.split('/')[-1]}`):** '{tweet_text_preview}...'")

                more_button = hover_and_find_more(driver, article_element, idx, tab_name)
                if not more_button:
                    st.warning(f"[{tab_name}] Article {idx+1}: Could not find 'More' button. Skipping.")
                    checked_article_ids.add(article_id_for_check)
                    continue

                st.write(f"[{tab_name}] Article {idx+1}: 'More' button found. Scrolling it into view...")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'center'});", more_button)
                time.sleep(0.3) # Wait for scroll

                clicked_more_button = False
                st.write(f"[{tab_name}] Article {idx+1}: Attempting to click 'More' button...")
                try:
                    # Try JavaScript click first as it can be more direct
                    st.write(f"[{tab_name}] Article {idx+1}: Trying JS click on 'More' button.")
                    driver.execute_script("arguments[0].click();", more_button)
                    clicked_more_button = True
                    st.write(f"[{tab_name}] Article {idx+1}: JS click on 'More' button succeeded (apparently).")
                except Exception as e_js_click:
                    st.write(f"[{tab_name}] Article {idx+1}: JS click failed: {e_js_click}. Trying ActionChains click.")
                    try:
                        ActionChains(driver).move_to_element(more_button).click().perform()
                        clicked_more_button = True
                        st.write(f"[{tab_name}] Article {idx+1}: ActionChains click on 'More' succeeded (apparently).")
                    except Exception as e_ac_click:
                        st.error(f"[{tab_name}] Article {idx+1}: ActionChains click also failed: {e_ac_click}")
                
                if not clicked_more_button:
                    st.error(f"[{tab_name}] Article {idx+1}: All attempts to click 'More' button FAILED.")
                    checked_article_ids.add(article_id_for_check)
                    continue
                
                time.sleep(0.8) # Crucial: Wait for the menu to actually open after the click
                st.write(f"[{tab_name}] Article {idx+1}: Clicked 'More'. Now waiting for 'Delete' option in menu...")
                
                delete_option_xpath = '//div[@role="menuitem" and (.//span[contains(translate(text(),"DELETE","delete"),"delete")] or contains(translate(@aria-label,"DELETE","delete"),"delete"))]'
                delete_menu_item = None
                try:
                    delete_menu_item = WebDriverWait(driver, 5).until( # Reduced wait slightly, menu should appear fast
                        EC.visibility_of_element_located((By.XPATH, delete_option_xpath))
                    )
                    st.success(f"[{tab_name}] Article {idx+1}: 'Delete' option found and VISIBLE in menu.")
                except TimeoutException:
                    st.error(f"CRITICAL: [{tab_name}] Article {idx+1}: 'Delete' option DID NOT APPEAR after clicking 'More'.")
                    st.info("This is the common failure point. The 'More' menu might not have opened, or its content is unexpected.")
                    # driver.save_screenshot(f"debug_article_{idx+1}_{tab_name}_NO_DELETE_OPTION.png")
                    # st.image(f"debug_article_{idx+1}_{tab_name}_NO_DELETE_OPTION.png", caption=f"Article {idx+1} - No Delete Option Screenshot")
                    st.warning("If you see this, please check the screenshot (if enabled) or the browser state if not headless. The menu may have closed or its XPaths changed.")
                    driver.execute_script("document.body.click();") # Attempt to close any unexpected menu/dialog
                    time.sleep(0.5)
                    checked_article_ids.add(article_id_for_check)
                    continue 
                
                # --- If Delete option is found, proceed with stat checking and deletion ---
                replies, reposts, likes = 0,0,0 # Initialize stats
                try:
                    stat_elements_config = {
                        "reply": './/button[@data-testid="reply"]//span[@data-testid="app-text-transition-container"]/span',
                        "retweet": './/button[@data-testid="retweet"]//span[@data-testid="app-text-transition-container"]/span',
                        "like": './/button[@data-testid="like"]//span[@data-testid="app-text-transition-container"]/span',
                    }
                    temp_stats = {}
                    for stat_name, stat_xpath in stat_elements_config.items():
                        elements = article_element.find_elements(By.XPATH, stat_xpath)
                        for el in elements:
                            if el.is_displayed() and el.text.strip():
                                temp_stats[stat_name] = int(el.text.strip().replace(',', ''))
                                break
                        if stat_name not in temp_stats: temp_stats[stat_name] = 0 # Default to 0 if not found

                    replies = temp_stats.get("reply",0)
                    reposts = temp_stats.get("retweet",0)
                    likes = temp_stats.get("like",0)
                    st.write(f"[{tab_name}] Article {idx+1}: Stats: Replies={replies}, Reposts={reposts}, Likes={likes}")
                except Exception as e_stat:
                    st.warning(f"[{tab_name}] Article {idx+1}: Could not parse stats reliably: {e_stat}. Assuming 0 for safety (will attempt delete if other conditions met).")


                if replies == 0 and reposts == 0 and likes == 0:
                    st.write(f"[{tab_name}] Article {idx+1}: Conditions met for deletion (0 engagement). Clicking 'Delete' option...")
                    try:
                        # Click the "Delete" menu item
                        driver.execute_script("arguments[0].click();", delete_menu_item) # JS click often better for menu items
                        # ActionChains(driver).move_to_element(delete_menu_item).click().perform()
                        time.sleep(0.8) # Wait for confirmation dialog

                        st.write(f"[{tab_name}] Article {idx+1}: Clicked 'Delete'. Waiting for confirmation button...")
                        confirm_button_xpath = '//div[@data-testid="confirmationSheetConfirm"]'
                        confirm_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, confirm_button_xpath))
                        )
                        st.write(f"[{tab_name}] Article {idx+1}: Confirmation button found. Clicking confirm...")
                        driver.execute_script("arguments[0].click();", confirm_button) # JS click
                        # ActionChains(driver).move_to_element(confirm_button).click().perform()
                        
                        st.success(f"[{tab_name}] Article {idx+1}: DELETED '{tweet_text_preview}...'.")
                        deleted_count += 1
                        empty_scrolls_in_a_row = 0 # Reset since an action was taken
                        time.sleep(2.0) # Wait for UI to update after deletion
                        
                        st.write(f"[{tab_name}] Breaking from article loop to refresh list after deletion.")
                        break # Break from the for loop (articles_on_page) to get a fresh list
                    except Exception as e_final_delete:
                        st.error(f"[{tab_name}] Article {idx+1}: Error during final delete/confirmation: {e_final_delete}")
                        # driver.save_screenshot(f"debug_final_delete_fail_article_{idx+1}_{tab_name}.png")
                        # st.image(f"debug_final_delete_fail_article_{idx+1}_{tab_name}.png")
                        driver.execute_script("document.body.click();") # Try to dismiss dialog
                        time.sleep(0.5)
                else:
                    st.info(f"[{tab_name}] Article {idx+1}: Not deleting (engagement: R:{replies}, RP:{reposts}, L:{likes}). Closing menu.")
                    driver.execute_script("document.body.click();") # Click away to close "More" menu
                    time.sleep(0.5)
                
                checked_article_ids.add(article_id_for_check)

            except StaleElementReferenceException:
                st.warning(f"[{tab_name}] Article {idx+1} became stale. Breaking to refresh article list.")
                break 
            except Exception as e_article_loop:
                st.error(f"[{tab_name}] Unexpected error processing article {idx+1}: {e_article_loop}")
                # driver.save_screenshot(f"debug_article_loop_error_article_{idx+1}_{tab_name}.png")
                # st.image(f"debug_article_loop_error_article_{idx+1}_{tab_name}.png")
                driver.execute_script("document.body.click();") 
                time.sleep(0.5)
                checked_article_ids.add(article_id_for_check) # Add to checked to prevent re-processing same error
                continue 
            
            # If a deletion happened, the 'break' inside the loop would have occurred.
            # If loop completed without break (no deletion), then check if we processed new articles.
            if idx == len(articles_on_page) - 1 and new_articles_processed_this_pass == 0 and articles_on_page:
                # Reached end of current article list, and all were already checked ones.
                st.write(f"All {len(articles_on_page)} articles on this pass were already processed. Incrementing empty scroll.")
                empty_scrolls_in_a_row +=1


        except TimeoutException: 
            st.warning(f"[{tab_name}] Timed out waiting for initial articles on pass. Empty scroll count: {empty_scrolls_in_a_row + 1}")
            empty_scrolls_in_a_row += 1
        except Exception as e_outer_loop:
            st.error(f"[{tab_name}] Critical error in main processing loop for {tab_name}: {e_outer_loop}")
            # driver.save_screenshot(f"debug_critical_error_{tab_name}.png")
            # st.image(f"debug_critical_error_{tab_name}.png")
            break 

        if empty_scrolls_in_a_row >= max_empty_scrolls:
             st.info(f"[{tab_name}] Reached max empty scrolls ({max_empty_scrolls}). Assuming end of content for '{tab_name}'.")
             break

        st.write(f"[{tab_name}] Scrolling down. Attempt {scroll_attempts + 1}, Empty Scrolls: {empty_scrolls_in_a_row}...")
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3.5) 
        scroll_attempts += 1
        
        if scroll_attempts > 70: # Increased safety break
            st.warning(f"[{tab_name}] Reached {scroll_attempts} scroll attempts. Stopping this tab to prevent infinite loop.")
            break

    st.success(f"Finished processing '{tab_name}'. Total deleted in this session for this tab: {deleted_count}")
    return deleted_count

def main():
    st.set_page_config(layout="wide")
    st.title("X/Twitter Bulk Deletion Tool 🐦🗑️ v2")
    st.markdown("""
    This tool attempts to delete your items on X/Twitter that have zero engagement.
    **USE WITH EXTREME CAUTION. Deletions are permanent.**
    Requires your X/Twitter cookies as `twitter_cookies.json`.
    Enable screenshots (uncomment `driver.save_screenshot` lines) in the code for debugging if issues occur.
    """)

    if not os.path.exists(COOKIE_FILE):
        st.error(f"Cookie file '{COOKIE_FILE}' not found. Please export cookies.")
        # ... (cookie export instructions - kept concise for brevity here)
        return

    if "logged_in" not in st.session_state: st.session_state.logged_in = False
    if "driver" not in st.session_state: st.session_state.driver = None

    if not st.session_state.logged_in:
        if st.button("Start Session with Cookies 🍪"):
            with st.spinner("🚀 Launching browser & loading cookies..."):
                driver_instance = initialize_driver()
                if not driver_instance:
                    st.error("Browser initialization failed. Cannot proceed.")
                    return
                
                st.session_state.driver = driver_instance
                load_cookies(st.session_state.driver, COOKIE_FILE)
                
                if is_logged_in(st.session_state.driver):
                    st.success("🎉 Logged in with cookies!")
                    st.session_state.logged_in = True
                else:
                    st.error("❌ Login FAILED. Cookies might be old/invalid or login check needs update.")
                    if st.session_state.driver: st.session_state.driver.quit()
                    st.session_state.driver = None
    
    if st.session_state.logged_in and st.session_state.driver:
        st.success("✅ Logged In. Browser session active.")
        
        action_choice = st.radio(
            "Delete items with 0 replies, 0 reposts, 0 likes:",
            ("Only My Posts", "Only My Replies", "Both My Posts & My Replies"),
            index=None, key="action_choice"
        )

        if action_choice:
            st.warning(f"🚨 Confirm Deletion: **{action_choice}**. This is irreversible.")
            confirm_delete = st.checkbox(f"I understand and want to delete '{action_choice}'.")
            
            if st.button(f"🚀 Start Deleting: {action_choice}", disabled=not confirm_delete, type="primary"):
                total_deleted_posts = 0
                total_deleted_replies = 0

                if "Posts" in action_choice or "Both" in action_choice:
                    st.info("--- Processing 'Posts' tab ---")
                    with st.spinner("🗑️ Working on Posts..."):
                        deleted_posts = delete_empty_tweets_in_tab(st.session_state.driver, "Posts")
                        total_deleted_posts += deleted_posts
                    st.success(f"Finished 'Posts'. Deleted: {deleted_posts}")

                if "Replies" in action_choice or "Both" in action_choice:
                    st.info("--- Processing 'Replies' tab ---")
                    with st.spinner("🗑️ Working on Replies..."):
                        deleted_replies = delete_empty_tweets_in_tab(st.session_state.driver, "Replies")
                        total_deleted_replies += deleted_replies
                    st.success(f"Finished 'Replies'. Deleted: {deleted_replies}")
                
                st.balloons()
                st.header(f"🎉 Deletion Process Finished! 🎉")
                st.write(f"Total Posts deleted: {total_deleted_posts}")
                st.write(f"Total Replies deleted: {total_deleted_replies}")
        
        if st.button("🚪 End Session & Close Browser"):
            with st.spinner("Shutting down..."):
                if st.session_state.driver: st.session_state.driver.quit()
            st.session_state.driver = None
            st.session_state.logged_in = False
            st.info("Session ended. Refresh page to restart.")
            time.sleep(1); st.rerun()

if __name__ == "__main__":
    main()
