"""
Naukri Auto-Apply Bot - Complete Fixed Version
Author: Fixed for Kaustubh Upadhyaya
Date: July 2025
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
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from bs4 import BeautifulSoup
from datetime import datetime
import sqlite3

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
    
    def __init__(self, config_file='config.json'):
        """Initialize the bot with configuration"""
        self.config = self.load_config(config_file)
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
        
        # Updated selectors based on current Naukri structure
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
                    "pages_per_keyword": 3,
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
        """Setup WebDriver with enhanced error handling"""
        try:
            logger.info("Setting up browser...")
            logger.info(f"Operating System: {platform.platform()}")
            
            # Enhanced Edge options for stealth
            options = webdriver.EdgeOptions()
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-extensions")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-features=msSmartScreenProxy")
            
            # Add realistic user agent
            options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0")
            
            if self.config['webdriver'].get('headless', False):
                options.add_argument("--headless")
            
            # Try multiple driver setup methods
            driver_methods = [
                self._try_webdriver_manager,
                self._try_manual_path,
                self._try_system_driver
            ]
            
            for method in driver_methods:
                try:
                    self.driver = method(options)
                    if self.driver:
                        break
                except Exception as e:
                    logger.warning(f"Driver setup method failed: {e}")
                    continue
            
            if not self.driver:
                logger.error("All driver setup methods failed")
                return False
            
            # Configure driver
            self.driver.implicitly_wait(self.config['webdriver']['implicit_wait'])
            self.driver.set_page_load_timeout(self.config['webdriver']['page_load_timeout'])
            self.wait = WebDriverWait(self.driver, 20)
            
            # Test driver with simple navigation
            self.driver.get("https://www.google.com")
            logger.info("✅ Browser setup successful")
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
                for selector in email_selectors:
                    try:
                        email_field = self.driver.find_element(By.CSS_SELECTOR, selector)
                        if email_field.is_displayed() and email_field.is_enabled():
                            logger.info(f"✅ Found email field with selector: {selector}")
                            break
                    except NoSuchElementException:
                        continue
                
                if not email_field:
                    logger.error("❌ Could not find email field")
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
    
    def scrape_job_links(self):
        """Scrape job links with updated selectors"""
        try:
            logger.info("🔍 Starting enhanced job search...")
            
            keywords = self.config['job_search']['keywords']
            location = self.config['job_search']['location']
            pages_per_keyword = self.config['job_search']['pages_per_keyword']
            
            for keyword in keywords:
                logger.info(f"Searching for: {keyword}")
                
                for page in range(1, pages_per_keyword + 1):
                    try:
                        # Build search URL
                        search_keyword = keyword.lower().replace(' ', '-')
                        search_location = location.lower().replace(' ', '-') 
                        url = f"https://www.naukri.com/{search_keyword}-jobs-in-{search_location}-{page}"
                        
                        logger.info(f"Page {page}: {url}")
                        self.driver.get(url)
                        self.smart_delay(3, 5)
                        
                        # Wait for job cards to load
                        try:
                            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, self.job_card_selector)))
                        except TimeoutException:
                            logger.warning("Job cards did not load in time")
                            continue
                        
                        # Extract job links
                        job_cards = self.driver.find_elements(By.CSS_SELECTOR, self.job_card_selector)
                        logger.info(f"Found {len(job_cards)} job cards")
                        
                        page_links = []
                        for card in job_cards:
                            try:
                                # Get job link
                                title_element = card.find_element(By.CSS_SELECTOR, self.job_title_selector)
                                job_url = title_element.get_attribute('href')
                                
                                if job_url and job_url not in self.processed_jobs:
                                    # Get job text for basic filtering
                                    job_text = card.text.lower()
                                    
                                    if self._is_relevant_job(job_text):
                                        page_links.append(job_url)
                                        self.processed_jobs.add(job_url)
                                        
                            except Exception as e:
                                logger.debug(f"Error extracting job card: {e}")
                                continue
                        
                        logger.info(f"Page {page}: Found {len(page_links)} relevant jobs")
                        self.joblinks.extend(page_links)
                        
                        # Delay between pages
                        self.smart_delay(3, 5)
                        
                    except Exception as e:
                        logger.error(f"Error on page {page}: {e}")
                        continue
            
            logger.info(f"✅ Job search completed. Found {len(self.joblinks)} total jobs")
            return len(self.joblinks) > 0
            
        except Exception as e:
            logger.error(f"Error in scrape_job_links: {e}")
            return False
    
    def _is_relevant_job(self, job_text):
        """Filter jobs based on relevance"""
        text_lower = job_text.lower()
        
        # Exclude irrelevant positions
        exclude_keywords = ['sales', 'marketing', 'hr', 'recruiter', 'bpo', 'call center', 'customer service']
        if any(keyword in text_lower for keyword in exclude_keywords):
            return False
        
        # Must contain relevant keywords  
        relevant_keywords = ['python', 'data', 'engineer', 'developer', 'sql', 'etl', 'analytics', 'software']
        if not any(keyword in text_lower for keyword in relevant_keywords):
            return False
        
        # Check experience level (prefer 1-5 years)
        experience_patterns = ['1-3', '2-5', '3-5', '1-4', '2-4', '0-3', '1-2']
        if not any(pattern in text_lower for pattern in experience_patterns):
            # Allow if no specific experience mentioned
            if any(senior in text_lower for senior in ['senior', 'lead', '5+', '6+', '7+']):
                return False
        
        # Check location preference
        if 'bengaluru' in text_lower or 'bangalore' in text_lower or 'remote' in text_lower:
            return True
        
        # Default to include if basic criteria met
        return True
    
    def apply_to_jobs(self):
        """Apply to jobs with enhanced error handling"""
        try:
            if not self.joblinks:
                logger.warning("No jobs to apply to")
                return
            
            logger.info(f"🎯 Starting applications to {len(self.joblinks)} jobs...")
            max_applications = self.config['job_search']['max_applications_per_session']
            
            for index, job_url in enumerate(self.joblinks):
                if self.applied >= max_applications:
                    logger.info(f"Reached application limit: {max_applications}")
                    break
                
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
        Apply to a single job with a priority for 'Easy Apply', fallback to standard
        application, and improved waiting and checking logic.
        """
        try:
            self.driver.get(job_url)
            # Use wait for the page to load, e.g., for a known element in the footer
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'body')))

            # 1. CHECK IF ALREADY APPLIED ON THE PAGE
            try:
                applied_text_element = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Applied')]")
                if applied_text_element.is_displayed():
                    logger.info("⏩ Job is already marked as 'Applied' on the page. Skipping.")
                    self.skipped += 1
                    return False
            except NoSuchElementException:
                pass # Not applied, so continue

            # 2. PRIORITY 1: Look for 'Apply on Naukri' (Easy Apply)
            try:
                easy_apply_selector = "//button[contains(text(), 'Apply on Naukri') or contains(text(), 'Easy Apply')]"
                easy_apply_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, easy_apply_selector)))
                
                logger.info("✅ Found 'Easy Apply' button. Initiating on-site application.")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", easy_apply_button)
                self.smart_delay(1, 2) # A small delay can still be useful here
                easy_apply_button.click()
                
                if self._handle_easy_apply_submission():
                    job_id = self._extract_job_id(job_url)
                    self._save_job_application(job_id, job_url, "Applied (Easy Apply)")
                    return True
                else:
                    logger.warning("Easy Apply submission could not be confirmed.")
                    return False

            except TimeoutException:
                logger.info("-> No 'Easy Apply' button found. Searching for a standard apply button.")
                pass

            # 3. PRIORITY 2: Fallback to Standard Apply Button
            apply_button_selectors = [
                "//button[contains(translate(text(), 'A', 'a'), 'apply')]",
                ".btn-apply",
                "[data-job-apply]",
                "#apply-button"
            ]
            
            for selector in apply_button_selectors:
                try:
                    apply_button = self.wait.until(EC.element_to_be_clickable((By.XPATH if selector.startswith('//') else By.CSS_SELECTOR, selector)))
                    logger.info(f"Found standard apply button with selector: {selector}")
                    self.driver.execute_script("arguments[0].click();", apply_button)
                    self.smart_delay(4, 6) # Wait for potential new tab
                    
                    logger.info("✔️ Standard apply button clicked (likely redirected to external site).")
                    job_id = self._extract_job_id(job_url)
                    self._save_job_application(job_id, job_url, "Applied (External)")
                    return True
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                    continue

            logger.warning("❌ No actionable apply button was found on the page.")
            return False
            
        except Exception as e:
            logger.error(f"Error in _apply_to_single_job for {job_url}: {e}")
            return False

    def _handle_easy_apply_submission(self):
        """Handles the final submission on the 'Easy Apply' pop-up/modal."""
        try:
            submit_selectors = [
                "//button[contains(text(), 'Submit') and contains(@class, 'btn-primary')]",
                "//button[@id='submit-application']",
                "//button[contains(text(), 'Confirm')]"
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    logger.info(f"Found easy apply submission button: {selector}")
                    submit_button.click()
                    self.smart_delay(3, 5) # Wait for confirmation
                    logger.info("✅ 'Easy Apply' submission successful.")
                    return True
                except TimeoutException:
                    continue
                    
            logger.warning("Could not find the final 'Submit' button for easy apply.")
            return False
        except Exception as e:
            logger.error(f"An error occurred during easy apply submission: {e}")
            return False
    
    def _extract_job_id(self, job_url):
        """Extract job ID from URL"""
        try:
            # Extract ID from URL pattern
            if '-' in job_url:
                return job_url.split('-')[-1]
            else:
                return str(hash(job_url))[-10:]
        except:
            return str(hash(job_url))[-10:]
    
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
            results = {
                'session_date': datetime.now().isoformat(),
                'total_jobs_found': len(self.joblinks),
                'applications_sent': self.applied,
                'applications_failed': self.failed,
                'jobs_skipped': self.skipped,
                'success_rate': f"{(self.applied / max(len(self.joblinks), 1) * 100):.1f}%",
                'applied_jobs': self.applied_list['passed'],
                'failed_jobs': self.applied_list['failed']
            }
            
            # Save as JSON
            with open(f"naukri_session_{timestamp}.json", 'w') as f:
                json.dump(results, f, indent=2)
            
            # Save as CSV for easy analysis
            if self.joblinks:
                df = pd.DataFrame({
                    'job_url': self.joblinks[:len(self.applied_list['passed']) + len(self.applied_list['failed'])],
                    'status': ['applied'] * len(self.applied_list['passed']) + ['failed'] * len(self.applied_list['failed'])
                })
                df.to_csv(f"naukri_applications_{timestamp}.csv", index=False)
            
            logger.info(f"Results saved with timestamp: {timestamp}")
            logger.info(f"SUMMARY - Found: {len(self.joblinks)}, Applied: {self.applied}, Failed: {self.failed}, Skipped: {self.skipped}")
            
        except Exception as e:
            logger.error(f"Error saving results: {e}")
    
    def run(self):
        """Main execution method - the complete workflow"""
        try:
            print("🚀 Starting Enhanced Naukri Job Application Bot")
            print("=" * 60)
            
            # Step 1: Setup WebDriver
            logger.info("Setting up browser...")
            if not self.setup_driver():
                logger.error("Failed to setup browser")
                return False
            
            # Step 2: Login to Naukri
            logger.info("Logging into Naukri...")
            if not self.login():
                logger.error("Failed to login to Naukri")
                return False
            
            # Step 3: Scrape job listings
            logger.info("Starting intelligent job search...")
            if not self.scrape_job_links():
                logger.error("No quality jobs found matching criteria")
                return False
            
            print(f"✅ Found {len(self.joblinks)} quality jobs, starting applications...")
            
            # Step 4: Apply to jobs
            logger.info("Starting job applications...")
            self.apply_to_jobs()
            
            # Step 5: Save results
            logger.info("Saving results...")
            self.save_results()
            
            # Final summary
            print("\n" + "=" * 60)
            print("🎉 NAUKRI AUTOMATION SESSION COMPLETE")
            print("=" * 60)
            print(f"🔍 Jobs Found: {len(self.joblinks)}")
            print(f"✅ Applications Sent: {self.applied}")
            print(f"❌ Applications Failed: {self.failed}")
            print(f"⏭️  Jobs Skipped: {self.skipped}")
            print(f"📈 Success Rate: {(self.applied / max(len(self.joblinks), 1) * 100):.1f}%")
            print("=" * 60)
            
            logger.info("Bot execution completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Bot execution failed: {e}")
            return False
        
        finally:
            # Cleanup
            if hasattr(self, 'db_conn') and self.db_conn:
                self.db_conn.close()
            if self.driver:
                input("\nPress Enter to close browser...")
                self.driver.quit()
                logger.info("Browser closed")

# Main execution
if __name__ == "__main__":
    print("🤖 Enhanced Naukri Auto-Apply Bot")
    print("=" * 50)
    
    bot = IntelligentNaukriBot()
    success = bot.run()
    
    if success:
        print("\n✅ Bot completed successfully! Check the generated reports.")
    else:
        print("\n❌ Bot failed. Check logs for details.")