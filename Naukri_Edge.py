"""
Naukri Auto-Apply Bot - Complete Fixed Version
Author: Fixed for Kaustubh Upadhyaya
Date: September 2025
"""

import pandas as pd
import os
import time
import json
import logging
import random
import platform
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from bs4 import BeautifulSoup
from datetime import datetime
import sqlite3
import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('naukri_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IntelligentNaukriBot:
    """Fixed Naukri Bot with updated login and selectors"""
    
    def __init__(self, config_file='enhanced_config.json'):
        """Initialize the bot with configuration"""
        self.config = self.load_config(config_file)
        
        # --- Configure Gemini API ---
        try:
            gemini_api_key = self.config.get('gemini_api_key')
            if gemini_api_key:
                genai.configure(api_key=gemini_api_key)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("Gemini API configured successfully.")
            else:
                self.gemini_model = None
                logger.warning("Gemini API key not found in config. AI chatbot will be disabled.")
        except Exception as e:
            self.gemini_model = None
            logger.error(f"Failed to configure Gemini API: {e}")

        self.driver = None
        self.wait = None
        self.joblinks = []
        self.applied = 0
        self.failed = 0
        self.skipped = 0
        self.applied_list = {'passed': [], 'failed': [], 'skipped': []}
        self.processed_jobs = set()
        
        # Initialize simple job tracking
        self.init_job_database()
        # Repository root (used for saving CSVs and README updates)
        try:
            self.repo_root = os.path.abspath(os.path.dirname(__file__))
        except Exception:
            self.repo_root = os.getcwd()
        
        self.job_card_selector = '.srp-jobtuple-wrapper'
        self.job_title_selector = '.title a'
        
        logger.info("Bot initialized successfully")
    
    def load_config(self, config_file):
        """Load configuration with smart defaults"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                logger.info("Configuration loaded successfully")
                return config
        except FileNotFoundError:
            logger.info("Config file not found. Creating default configuration...")
            default_config = {
                "credentials": {
                    "email": "kaustubh.upadhyaya1@gmail.com", 
                    "password": "9880380081@kK"
                },
                "personal_info": {
                    "firstname": "Kaustubh",
                    "lastname": "Upadhyaya", 
                    "phone": "9880380081"
                },
                "job_search": {
                    "keywords": ["Data Engineer", "Python Developer", "ETL Developer", "SQL Developer"],
                    "location": "bengaluru",
                    "max_applications_per_session": 20,
                    # FIXED ISSUE 2: Increased pages to find more jobs
                    "pages_per_keyword": 10,
                    # FIXED ISSUE 1: Added filter for recent jobs
                    "job_age_days": 3,
                    "preferred_companies": ["Microsoft", "Google", "Amazon", "Netflix"],
                    "avoid_companies": ["TCS", "Infosys", "Wipro"]
                },
                "webdriver": {
                    "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                    "implicit_wait": 15,
                    "page_load_timeout": 45,
                    "headless": False
                },
                "bot_behavior": {
                    "min_delay": 3,
                    "max_delay": 7,
                    "typing_delay": 0.1,
                    "scroll_pause": 2
                }
            }
            
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            
            logger.info(f"Default config created at {config_file}")
            return default_config
    
    def init_job_database(self):
        """Initialize simple job tracking database"""
        try:
            self.db_conn = sqlite3.connect('naukri_jobs.db')
            cursor = self.db_conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applied_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_url TEXT,
                    job_title TEXT,
                    application_date TIMESTAMP,
                    status TEXT
                )
            ''')
            self.db_conn.commit()
            logger.info("Job database initialized")
        except Exception as e:
            logger.warning(f"Database initialization failed: {e}")
            self.db_conn = None
    
    def setup_driver(self):
        """Setup WebDriver with enhanced stability and stealth options."""
        logger.info("Setting up new browser session...")
        try:
            options = webdriver.EdgeOptions()
            # --- CRITICAL STABILITY OPTIONS ---
            # Respect the config setting for headless (allow turning off headless to avoid access blocks)
            headless_cfg = self.config.get('webdriver', {}).get('headless', True)
            if headless_cfg:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-extensions")
            options.add_argument("--log-level=3")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-features=IsolateOrigins,site-per-process')

            prefs = {"profile.managed_default_content_settings.images": 2}
            options.add_experimental_option("prefs", prefs)

            # Optionally reuse a user profile to bypass some bot protections (set path in config)
            user_data_dir = self.config.get('webdriver', {}).get('user_data_dir')
            if user_data_dir and os.path.exists(user_data_dir):
                try:
                    options.add_argument(f"--user-data-dir={user_data_dir}")
                    logger.info(f"Using existing browser profile from: {user_data_dir}")
                except Exception:
                    logger.debug("Failed to apply user data dir for browser profile")

            # Prefer a local driver path if provided to avoid network calls in restricted environments
            local_path = self.config.get('webdriver', {}).get('edge_driver_path')
            if local_path and os.path.exists(local_path):
                try:
                    service = EdgeService(local_path)
                    self.driver = webdriver.Edge(service=service, options=options)
                except Exception:
                    self.driver = None
            else:
                # Fall back to webdriver-manager (may require network access)
                try:
                    from webdriver_manager.microsoft import EdgeChromiumDriverManager
                    service = EdgeService(EdgeChromiumDriverManager().install())
                    self.driver = webdriver.Edge(service=service, options=options)
                except Exception as e:
                    logger.error(f"webdriver-manager fallback failed: {e}")
                    self.driver = None

            self.driver.set_page_load_timeout(60)
            self.wait = WebDriverWait(self.driver, 20)
            logger.info("✅ Browser setup successful.")
            return True
        except Exception as e:
            logger.error(f"WebDriver setup failed: {e}")
            return False
    
    def _try_webdriver_manager(self, options):
        """Try automatic driver download"""
        try:
            from webdriver_manager.microsoft import EdgeChromiumDriverManager
            logger.info("🔄 Attempting automatic driver download...")
            service = EdgeService(EdgeChromiumDriverManager().install())
            return webdriver.Edge(service=service, options=options)
        except Exception as e:
            logger.warning(f"Webdriver manager failed: {e}")
            raise
    
    def _try_manual_path(self, options):
        """Try manual driver path"""
        manual_path = self.config['webdriver']['edge_driver_path']
        logger.info(f"🔄 Trying manual path: {manual_path}")
        
        if os.path.exists(manual_path):
            service = EdgeService(manual_path)
            return webdriver.Edge(service=service, options=options)
        else:
            raise FileNotFoundError(f"Manual driver not found: {manual_path}")
    
    def _try_system_driver(self, options):
        """Try system-installed driver"""
        logger.info("🔄 Trying system-installed driver...")
        return webdriver.Edge(options=options)
    
    def smart_delay(self, min_seconds=3, max_seconds=7):
        """Smart delay with randomization"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)
    
    def human_type(self, element, text, typing_delay=None):
        """Type text like a human"""
        if typing_delay is None:
            typing_delay = self.config['bot_behavior']['typing_delay']
        
        element.clear()
        for char in text:
            element.send_keys(char)
            time.sleep(typing_delay + random.uniform(0, 0.1))
    
    def login(self):
        """FIXED: Enhanced login with updated selectors"""
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Login attempt {attempt + 1}/{max_retries}")
                
                # Navigate to login page
                self.driver.get('https://www.naukri.com/nlogin/login')
                self.smart_delay(3, 5)
                # Try to close any popups that might obscure the form
                try:
                    self._handle_popups()
                except Exception:
                    pass
                
                # UPDATED LOGIN SELECTORS - Try multiple selectors for email field
                email_selectors = [
                    '#usernameField',
                    '#emailField', 
                    '#email',
                    '#username',
                    "input[placeholder*='Email']",
                    "input[placeholder*='email']",
                    "input[name='email']",
                    "input[type='email']"
                ]
                
                email_field = None
                # Try searching for selectors in the main document first
                for selector in email_selectors:
                    try:
                        email_field = WebDriverWait(self.driver, 8).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                        )
                        if email_field.is_displayed() and email_field.is_enabled():
                            logger.info("✅ Found email field in main document")
                            break
                    except Exception:
                        email_field = None
                        continue

                # If not found, try inside iframes (some login flows embed the form)
                if not email_field:
                    try:
                        frames = self.driver.find_elements(By.TAG_NAME, 'iframe')
                        for fr in frames:
                            try:
                                self.driver.switch_to.frame(fr)
                                for selector in email_selectors:
                                    try:
                                        email_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                                        if email_field.is_displayed() and email_field.is_enabled():
                                            logger.info("✅ Found email field inside an iframe")
                                            break
                                    except Exception:
                                        continue
                                self.driver.switch_to.default_content()
                                if email_field:
                                    break
                            except Exception:
                                try:
                                    self.driver.switch_to.default_content()
                                except Exception:
                                    pass
                                continue
                    except Exception:
                        pass
                
                if not email_field:
                    logger.error("❌ Could not find email field")
                    # Save a debug snapshot for inspection
                    try:
                        with open('login_debug_snapshot.html', 'w', encoding='utf-8') as f:
                            f.write(self.driver.page_source)
                        logger.info("Saved login_debug_snapshot.html for troubleshooting")
                    except Exception:
                        pass
                    continue
                
                # Enter email
                self.human_type(email_field, self.config['credentials']['email'])
                self.smart_delay(1, 2)
                
                # UPDATED PASSWORD SELECTORS
                password_selectors = [
                    '#passwordField',
                    '#password',
                    '#pass',
                    "input[placeholder*='Password']",
                    "input[placeholder*='password']",
                    "input[name='password']",
                    "input[type='password']"
                ]
                
                password_field = None
                for selector in password_selectors:
                    try:
                        password_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if password_field.is_displayed() and password_field.is_enabled():
                            logger.info(f"✅ Found password field with selector: {selector}")
                            break
                    except NoSuchElementException:
                        continue
                
                if not password_field:
                    logger.error("❌ Could not find password field")
                    continue
                
                # Enter password
                self.human_type(password_field, self.config['credentials']['password'])
                self.smart_delay(1, 2)
                
                # UPDATED LOGIN BUTTON SELECTORS
                login_button_selectors = [
                    "//button[@type='submit']",
                    "//button[contains(text(), 'Login')]",
                    "//button[contains(text(), 'Sign in')]",
                    "//input[@type='submit']",
                    ".loginButton",
                    "#login-submit"
                ]
                
                login_button = None
                for selector in login_button_selectors:
                    try:
                        if selector.startswith('//'):
                            login_button = self.driver.find_element(By.XPATH, selector)
                        else:
                            login_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if login_button.is_displayed() and login_button.is_enabled():
                            logger.info(f"✅ Found login button with selector: {selector}")
                            break
                    except NoSuchElementException:
                        continue
                
                if not login_button:
                    logger.error("❌ Could not find login button")
                    continue
                
                # Click login button with multiple methods
                try:
                    # Try regular click first
                    login_button.click()
                except ElementClickInterceptedException:
                    try:
                        # Try JavaScript click
                        self.driver.execute_script("arguments[0].click();", login_button)
                    except:
                        try:
                            # Try action chains
                            ActionChains(self.driver).move_to_element(login_button).click().perform()
                        except:
                            logger.error("All click methods failed")
                            continue
                
                # Wait for login to process
                self.smart_delay(5, 8)
                
                # UPDATED SUCCESS VERIFICATION - Check multiple indicators
                if self._verify_login_success():
                    logger.info("✅ Login successful!")
                    return True
                else:
                    logger.warning(f"❌ Login attempt {attempt + 1} failed")
                    if attempt < max_retries - 1:
                        self.smart_delay(5, 10)
                        continue
                        
            except Exception as e:
                logger.error(f"Login attempt {attempt + 1} error: {e}")
                if attempt < max_retries - 1:
                    self.smart_delay(5, 10)
                    continue
        
        logger.error("❌ All login attempts failed")
        return False
    
    def _verify_login_success(self):
        """FIXED: Verify login success with multiple indicators"""
        try:
            # Check URL - should not contain 'login' after successful login
            current_url = self.driver.current_url.lower()
            if 'nlogin' in current_url or '/login' in current_url:
                logger.debug("Still on login page")
                return False
            
            # Check for user profile indicators
            profile_indicators = [
                '.nI-gNb-drawer__icon',  # Profile menu icon
                '.view-profile-wrapper',  # Profile wrapper
                '[data-automation="profileDropdown"]',  # Profile dropdown
                '.nI-gNb-menuExpanded',  # Menu expanded
                '.user-name',  # User name display
                '[title*="Profile"]',  # Profile title
                '.mn-hdr__profileName'  # Profile name
            ]
            
            for indicator in profile_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if elements and any(el.is_displayed() for el in elements):
                        logger.info(f"✅ Login verified using: {indicator}")
                        return True
                except:
                    continue
            
            # Check if we can access a protected page
            try:
                self.driver.get('https://www.naukri.com/mnjuser/profile')
                self.smart_delay(2, 3)
                
                if 'login' not in self.driver.current_url.lower():
                    logger.info("✅ Login verified by accessing profile page")
                    return True
            except:
                pass
            
            logger.debug("No login indicators found")
            return False
            
        except Exception as e:
            logger.error(f"Error verifying login: {e}")
            return False
    
    def _handle_popups(self):
        """Handles common pop-ups and overlays that can block the main content."""
        try:
            # Use a short wait time for pop-ups as they may not always appear
            short_wait = WebDriverWait(self.driver, 5)
            
            # Common selectors for pop-up close buttons
            close_button_selectors = [
                "span.close-popup",      # Generic close icon
                "button.close",          # Common button class
                "div.cross-icon",        # Another common icon
                "[aria-label='Close']",  # Accessibility label
                "i.naukri-icon-close"    # Naukri-specific icon
            ]
            
            for selector in close_button_selectors:
                try:
                    close_button = short_wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    logger.info(f"Found and closing a pop-up with selector: {selector}")
                    try:
                        close_button.click()
                    except Exception:
                        # Try JS click as a fallback
                        try:
                            self.driver.execute_script("arguments[0].click();", close_button)
                        except Exception:
                            logger.debug(f"Failed to click pop-up close button for selector: {selector}")
                    self.smart_delay(1, 2) # Wait for pop-up to disappear
                except TimeoutException:
                    pass # Pop-up with this selector was not found, which is fine
                    
        except Exception as e:
            logger.warning(f"An error occurred while handling pop-ups: {e}")

    def scrape_job_links(self):
        """
        OPTIMIZED: Scrape job links and automatically stop searching a keyword
        if multiple consecutive pages yield no new results.
        """
        try:
            logger.info("🔍 Starting definitive job search with scroll handling...")
            
            keywords = self.config['job_search']['keywords']
            location = self.config['job_search']['location']
            pages_per_keyword = self.config['job_search']['pages_per_keyword']
            
            for keyword in keywords:
                logger.info(f"Searching for: {keyword}")
                
                # --- START OF OPTIMIZATION LOGIC ---
                consecutive_pages_with_no_new_jobs = 0
                # --- END OF OPTIMIZATION LOGIC ---

                for page in range(1, pages_per_keyword + 1):
                    # --- START OF OPTIMIZATION CHECK ---
                    if consecutive_pages_with_no_new_jobs >= 3:
                        logger.info(f"Found no new jobs for '{keyword}' for 3 consecutive pages. Moving to next keyword.")
                        break
                    # --- END OF OPTIMIZATION CHECK ---

                    try:
                        search_keyword = keyword.lower().replace(' ', '-')
                        search_location = location.lower().replace(' ', '-')
                        
                        base_url = f"https://www.naukri.com/{search_keyword}-jobs-in-{search_location}-{page}"
                        job_age_days = self.config['job_search'].get('job_age_days')

                        if job_age_days and int(job_age_days) > 0:
                            url = f"{base_url}?jobAge={job_age_days}"
                        else:
                            url = base_url
                        
                        logger.info(f"Page {page}: {url}")
                        self.driver.get(url)
                        self._handle_popups()

                        logger.info("Scrolling page to trigger job loading...")
                        for _ in range(3):
                            self.driver.execute_script("window.scrollBy(0, 500);")
                            time.sleep(1)

                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.job_card_selector)))
                        
                        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                        job_cards = soup.select('.srp-jobtuple-wrapper')
                        logger.info(f"Found {len(job_cards)} job cards on page")

                        new_links_found_on_this_page = 0
                        for card in job_cards:
                            try:
                                title_element = card.select_one('a.title')
                                if title_element and title_element.has_attr('href'):
                                    job_url = title_element['href']
                                    
                                    if job_url and job_url not in self.processed_jobs:
                                        job_text = card.get_text().lower()
                                        if self._is_relevant_job(job_text):
                                            self.joblinks.append(job_url)
                                            self.processed_jobs.add(job_url)
                                            new_links_found_on_this_page += 1
                            except Exception as e:
                                logger.debug(f"Error processing a job card: {e}")
                                continue
                                
                        logger.info(f"Page {page}: Found {new_links_found_on_this_page} new relevant jobs")

                        # --- START OF OPTIMIZATION COUNTER ---
                        if new_links_found_on_this_page == 0:
                            consecutive_pages_with_no_new_jobs += 1
                        else:
                            consecutive_pages_with_no_new_jobs = 0
                        # --- END OF OPTIMIZATION COUNTER ---

                        self.smart_delay(1, 2)
                        
                    except Exception as e:
                        logger.error(f"Error on page {page} for '{keyword}': {e}")
                        consecutive_pages_with_no_new_jobs += 1 # Count error pages as empty
                        continue
            
            logger.info(f"✅ Job search completed. Found {len(self.joblinks)} total new jobs.")
            return len(self.joblinks) > 0
            
        except Exception as e:
            logger.error(f"Fatal error in scrape_job_links: {e}")
            return False
    
    def _is_relevant_job(self, job_text):
        """
        A more lenient filter to gather potentially relevant jobs for further analysis.
        """
        text_lower = job_text.lower()

        # 1. Broadly exclude positions that are clearly not a fit.
        exclude_keywords = [
            'sales', 'marketing', 'hr', 'recruiter', 'bpo', 'customer service',
            'voice process', 'support engineer'
        ]
        if any(keyword in text_lower for keyword in exclude_keywords):
            return False

        # 2. Ensure at least one of the core keywords from your search is present.
        #    This prevents completely unrelated jobs from getting through.
        search_keywords = [kw.lower() for kw in self.config['job_search']['keywords']]
        if not any(keyword in text_lower for keyword in search_keywords):
            # This check might be too strict if the card text is minimal.
            # We can be even more lenient and trust the search results initially.
            pass

        # 3. If it's not explicitly excluded, consider it relevant for now.
        #    The detailed check will happen during the application phase.
        return True
    
    def apply_to_jobs(self):
        """Apply to jobs with enhanced error handling and self-healing browser checks"""
        try:
            if not self.joblinks:
                logger.warning("No jobs to apply to")
                return
            logger.info(f"🎯 Starting applications to {len(self.joblinks)} jobs...")
            for index, job_url in enumerate(self.joblinks):

                try:
                    logger.info(f"Applying to job {index + 1}/{len(self.joblinks)}: {job_url}")
                    
                    # Check if already applied
                    job_id = self._extract_job_id(job_url)
                    if self.is_job_already_applied(job_id):
                        logger.info("Already applied to this job, skipping...")
                        self.skipped += 1
                        continue
                    
                    # Apply to job
                    if self._apply_to_single_job(job_url):
                        self.applied += 1
                        self.applied_list['passed'].append(job_url)
                        logger.info(f"✅ Application {self.applied} successful!")
                    else:
                        self.failed += 1
                        self.applied_list['failed'].append(job_url)
                        logger.warning(f"❌ Application failed")
                    
                    # Smart delay between applications
                    self.smart_delay(5, 10)
                    
                except Exception as e:
                    logger.error(f"Unexpected error with job {index + 1}: {e}")
                    self.failed += 1
                    self.applied_list['failed'].append(job_url)
                    continue
                    
        except Exception as e:
            logger.error(f"Error in apply_to_jobs: {e}")
    
    def _apply_to_single_job(self, job_url):
        """
        Applies to a single job.
        - "Easy Apply" is a full attempt.
        - External links are opened in a new tab and the bot immediately returns.
        """
        try:
            # Keep track of the original tab
            original_tab = self.driver.current_window_handle

            # Navigate to the job page
            self.driver.get(job_url)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))

            # Check if job is already marked as applied on the page itself
            try:
                if self.driver.find_element(By.CSS_SELECTOR, ".already-applied-layer").is_displayed():
                    logger.info("⏩ Page indicates this job has already been applied to. Skipping.")
                    self._save_job_application(self._extract_job_id(job_url), job_url, "Skipped (Already Applied)")
                    return False
            except NoSuchElementException:
                pass

            # PRIORITY 1: Handle "Easy Apply"
            try:
                easy_apply_button = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.apply-button")))
                logger.info("✅ Found 'Easy Apply' button. Initiating on-site application.")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", easy_apply_button)
                time.sleep(1)
                easy_apply_button.click()
                
                self._handle_chatbot()
                
                if self._handle_easy_apply_submission():
                    self._save_job_application(self._extract_job_id(job_url), job_url, "Applied (Easy Apply)")
                    return True # This is the ONLY success case
                else:
                    logger.warning("Easy Apply submission could not be confirmed.")
                    return False

            except TimeoutException:
                logger.info("-> No 'Easy Apply' button found. Checking for external site link.")
                pass

            # PRIORITY 2: Handle External Site Links
            try:
                apply_button_selectors = [
                    "//button[contains(translate(text(), 'A', 'a'), 'apply')]", "//a[contains(translate(text(), 'A', 'a'), 'apply')]"
                ]
                for selector in apply_button_selectors:
                    try:
                        external_apply_button = WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((By.XPATH, selector)))
                        
                        logger.info("↗️ Found external apply link. Opening in new tab.")
                        job_id = self._extract_job_id(job_url)
                        self._save_job_application(job_id, job_url, "Skipped (External Site)")

                        # Open the link in a new tab and switch back
                        self.driver.switch_to.new_window('tab')
                        self.driver.get(job_url) # Re-navigate to the job page in the new tab to click the button
                        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, selector))).click()
                        
                        self.driver.switch_to.window(original_tab) # Switch back to the main tab
                        logger.info("⬅️ Switched back to main tab.")
                        return False # Not counted as a success
                    except TimeoutException:
                        continue
            except Exception as e:
                logger.error(f"Error handling external link: {e}")
                pass

            logger.warning("❌ No actionable apply button of any kind was found on the page.")
            return False
            
        except Exception as e:
            logger.error(f"Error in _apply_to_single_job for {job_url}: {e}")
            return False

    def _handle_easy_apply_submission(self):
        """
        Handles the final submission on the 'Easy Apply' pop-up/modal with more robust selectors.
        """
        try:
            # More comprehensive list of possible selectors for the final submit button
            submit_selectors = [
                "//button[contains(text(), 'Submit Application')]",
                "//button[contains(text(), 'Submit')]",
                "//button[contains(text(), 'Confirm')]",
                "//button[@id='submit-application']",
                "//button[contains(@class, 'submit-btn')]",
                "//button[@type='submit']"
            ]
            
            for selector in submit_selectors:
                try:
                    # Use a slightly shorter wait here to cycle through options faster
                    submit_button = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    logger.info(f"Found easy apply submission button with selector: {selector}")
                    submit_button.click()
                    self.smart_delay(3, 5) # Wait for confirmation screen
                    logger.info("✅ 'Easy Apply' submission successful.")
                    return True
                except TimeoutException:
                    continue # Try the next selector
            
            logger.warning("Could not find the final 'Submit' button for easy apply after trying all selectors.")
            return False
        except Exception as e:
            logger.error(f"An error occurred during easy apply submission: {e}")
            return False

    def _get_gemini_answer(self, question):
        """Sends the question to Gemini for a concise answer based on the user's config data."""
        if not getattr(self, 'gemini_model', None):
            return "AI model not configured."

        try:
            user_profile = self.config.get('user_profile', {})
            personal_info = self.config.get('personal_info', {})

            context = f"""
            - Name: {user_profile.get('name')}
            - Total Experience: {user_profile.get('experience_years')} years
            - Current Role: {user_profile.get('current_role')}
            - Core Skills: {', '.join(user_profile.get('core_skills', []))}
            - Current CTC: {personal_info.get('current_ctc')}
            - Expected CTC: {personal_info.get('expected_ctc')}
            - Notice Period: {personal_info.get('notice_period')}
            """

            prompt = f"""
            You are an AI assistant for a job applicant. Answer the chatbot's question concisely and professionally based ONLY on the provided context.
            Keep answers very short (e.g., "2 years", "18 LPA", "Immediate"). Do not add any extra conversational text.

            **Context about the Applicant:**
            {context}

            **IMPORTANT RULE:** For any question about years of experience in a *specific technical skill* (like Python, AWS, etc.), the required answer is always "2.5 years".

            **Chatbot's Question:**
            "{question}"

            **Your concise, direct answer:**
            """
            response = self.gemini_model.generate_content(prompt)
            answer = getattr(response, 'text', str(response)).strip().replace('"', '')
            logger.info(f"Gemini generated answer: '{answer}' for question: '{question}'")
            return answer
        except Exception as e:
            logger.error(f"Error getting response from Gemini: {e}")
            return "Unable to process this request."

    def _handle_chatbot(self, timeout=15):
        """HYBRID AI: Handles chatbot with keywords first, then falls back to Gemini AI."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='chatbot']"))
            )
            logger.info("Hybrid AI Chatbot Handler: Detected chatbot drawer.")
            
            for _ in range(5): # Try to answer up to 5 questions
                time.sleep(2) # Wait for question to render

                try:
                    question_elements = self.driver.find_elements(By.CSS_SELECTOR, "li.botItem:last-of-type div.botMsg span")
                    if not question_elements:
                        break
                    
                    question_text = question_elements[-1].text.strip() # Keep original case for logging
                    if not question_text:
                        continue

                    # Log the question for later analysis
                    try:
                        self._log_chatbot_question(question_text)
                    except Exception:
                        logger.debug("Failed to log chatbot question")

                    logger.info(f"Chatbot asks: '{question_text}'")
                    question_lower = question_text.lower() # Use lower case for matching

                    answer_text = None
                    # 1. Fast keyword matching
                    if 'experience' in question_lower and 'python' in question_lower:
                        answer_text = "2.5 years"
                    elif 'experience' in question_lower and 'sql' in question_lower:
                        answer_text = "2.5 years"
                    elif 'total experience' in question_lower or 'overall experience' in question_lower:
                        answer_text = str(self.config.get('user_profile', {}).get('experience_years'))
                    elif 'notice period' in question_lower or 'notice' in question_lower:
                        answer_text = str(self.config.get('personal_info', {}).get('notice_period', ''))
                    elif 'current ctc' in question_lower or 'current salary' in question_lower:
                        answer_text = str(self.config.get('personal_info', {}).get('current_ctc', ''))
                    elif 'expected ctc' in question_lower or 'expected salary' in question_lower:
                        answer_text = str(self.config.get('personal_info', {}).get('expected_ctc', ''))

                    # 2. If no keyword match, consult Gemini if available
                    if not answer_text:
                        if getattr(self, 'gemini_model', None):
                            logger.info("No keyword match found. Consulting Gemini...")
                            answer_text = self._get_gemini_answer(question_text)
                        else:
                            logger.warning("No keyword match and Gemini is disabled. Cannot answer.")
                            return False

                    # 3. Type the answer and submit
                    try:
                        input_field = None
                        try:
                            input_field = self.driver.find_element(By.CSS_SELECTOR, "div.textArea[contenteditable='true'], div.textArea, div[contenteditable='true'], textarea[placeholder*='Type'], textarea")
                        except Exception:
                            pass

                        if input_field is None:
                            logger.warning("Could not find chat input field to type the answer.")
                            return False

                        # Type the answer
                        tag = input_field.tag_name.lower()
                        if tag == 'div' and input_field.get_attribute('contenteditable') == 'true':
                            self.driver.execute_script("arguments[0].innerText = '';", input_field)
                            for ch in str(answer_text):
                                input_field.send_keys(ch)
                                time.sleep(self.config.get('bot_behavior', {}).get('typing_delay', 0.08))
                        else:
                            input_field.clear()
                            self.human_type(input_field, str(answer_text))

                        # Send
                        try:
                            send_btn = self.driver.find_element(By.CSS_SELECTOR, "button.send, button[type='submit'], .send")
                            self.driver.execute_script("arguments[0].click();", send_btn)
                        except Exception:
                            try:
                                input_field.send_keys(Keys.ENTER)
                            except Exception:
                                pass

                    except Exception as e:
                        logger.error(f"Error while typing/submitting chat answer: {e}")
                        return False

                except NoSuchElementException:
                    break
                except Exception as e:
                    logger.error(f"Error during chatbot turn: {e}")
                    break
            
            logger.info("Chatbot interaction finished.")
            return True
        except TimeoutException:
            logger.info("No chatbot detected within the timeout period.")
            return False
        except Exception as e:
            logger.error(f"A fatal error occurred in the Hybrid AI chatbot handler: {e}")
            return False
    
    def _extract_job_id(self, job_url):
        """Extract job ID from URL"""
        try:
            # Extract ID from URL pattern
            # Example: ...-sql-developer-bengaluru-2-to-6-years-100523503538
            parts = job_url.split('-')
            # The job ID is usually the last part if it's numeric and long
            if parts[-1].isdigit() and len(parts[-1]) > 8:
                return parts[-1]
            else:
                # Fallback for different URL structures
                return str(hash(job_url))[-12:]
        except:
            # Ultimate fallback
            return str(hash(job_url))[-12:]
    
    def is_job_already_applied(self, job_id):
        """Check if we already applied to this job"""
        if not self.db_conn:
            return False
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM applied_jobs WHERE job_id = ?", (job_id,))
            count = cursor.fetchone()[0]
            return count > 0
        except:
            return False
    
    def _save_job_application(self, job_id, job_url, status):
        """Save application details to database"""
        if not self.db_conn:
            return
        
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO applied_jobs 
                (job_id, job_url, job_title, application_date, status) 
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, job_url, "Applied Job", datetime.now(), status))
            self.db_conn.commit()
        except Exception as e:
            logger.debug(f"Database save error: {e}")
    
    def save_results(self):
        """Save session results to files"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create results summary
            total_processed = self.applied + self.failed + self.skipped
            success_rate = (self.applied / max(self.applied + self.failed, 1)) * 100

            results = {
                'session_date': datetime.now().isoformat(),
                'total_jobs_found': len(self.joblinks),
                'total_jobs_processed': total_processed,
                'applications_sent': self.applied,
                'applications_failed': self.failed,
                'jobs_skipped_already_in_db': self.skipped,
                'success_rate': f"{success_rate:.1f}%",
                'applied_jobs': self.applied_list['passed'],
                'failed_jobs': self.applied_list['failed']
            }
            
            # Save as JSON
            with open(f"naukri_session_{timestamp}.json", 'w') as f:
                json.dump(results, f, indent=2)
            
            # Save as CSV for easy analysis
            if self.applied_list['passed'] or self.applied_list['failed']:
                applied_df = pd.DataFrame({'job_url': self.applied_list['passed'], 'status': 'applied'})
                failed_df = pd.DataFrame({'job_url': self.applied_list['failed'], 'status': 'failed'})
                df = pd.concat([applied_df, failed_df], ignore_index=True)
                df.to_csv(f"naukri_applications_{timestamp}.csv", index=False)
            
            logger.info(f"Results saved with timestamp: {timestamp}")
            logger.info(f"SUMMARY - Found: {len(self.joblinks)}, Applied: {self.applied}, Failed: {self.failed}, Skipped: {self.skipped}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    def _log_chatbot_question(self, question_text: str):
        """Append chatbot question + timestamp to `chatbot_questions.csv` in the repo root."""
        try:
            import csv
            csv_path = os.path.join(self.repo_root, 'chatbot_questions.csv')
            write_header = not os.path.exists(csv_path)
            with open(csv_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if write_header:
                    writer.writerow(['timestamp', 'question'])
                writer.writerow([datetime.utcnow().isoformat(), question_text])
        except Exception as e:
            logger.debug(f"Failed to write chatbot question: {e}")

    def _update_readme_report(self):
        """Append a short run summary to README.md for quick visibility."""
        try:
            readme_path = os.path.join(self.repo_root, 'README.md')
            summary = f"\n\n- Last run: {datetime.utcnow().isoformat()} UTC\n- Jobs discovered: {len(self.joblinks)}\n- Applied (easy apply): {self.applied}\n- Skipped (external): {self.skipped}\n"
            with open(readme_path, 'a', encoding='utf-8') as f:
                f.write(summary)
        except Exception as e:
            logger.debug(f"Failed to update README report: {e}")
    
    def run(self):
        """Main execution method with a focus on a single, stable session."""
        try:
            print("🚀 Starting Enhanced Naukri Job Application Bot")
            print("=" * 60)
            
            if not self.setup_driver():
                return False
            
            if not self.login():
                return False
            
            if not self.scrape_job_links():
                logger.warning("No new jobs found in this session.")
            
            if self.joblinks:
                self.apply_to_jobs()

        except Exception as e:
            logger.error(f"A fatal error occurred during bot execution: {e}")
            return False
        finally:
            self.save_results() # Save results even if an error occurs
            try:
                self._update_readme_report()
            except Exception:
                logger.debug("Failed to update README report")
            # Final summary printout
            total_processed = self.applied + self.failed
            success_rate = (self.applied / max(total_processed, 1)) * 100
            print("\n" + "=" * 60)
            print("🎉 NAUKRI AUTOMATION SESSION COMPLETE")
            print("=" * 60)
            print(f"🔍 Jobs Found: {len(self.joblinks)}")
            print(f"✅ Applications Sent (Easy Apply): {self.applied}")
            print(f"❌ Applications Failed: {self.failed}")
            print(f"⏭️  Jobs Skipped: {self.skipped}")
            print(f"📈 Success Rate: {success_rate:.1f}%")
            print("=" * 60)

            if self.driver:
                input("\nPress Enter to close browser...")
                self.driver.quit()
                logger.info("Browser closed")
        
        logger.info("Bot execution completed.")
        return True

# Main execution
if __name__ == "__main__":
    print("🤖 Enhanced Naukri Auto-Apply Bot")
    print("=" * 50)
    
    bot = IntelligentNaukriBot()
    success = bot.run()
    
    if success:
        print("\n✅ Bot completed its run! Check the logs and generated reports for details.")
    else:
        print("\n❌ Bot encountered an error. Check logs for details.")