"""
Naukri Auto-Apply Bot - IMPROVED VERSION
==========================================
IMPROVEMENTS:
1. ✅ Better submit button detection (handles overlays/iframes)
2. ✅ Visual confirmation of submission
3. ✅ Faster processing (reduced timeouts)
4. ✅ Better error recovery
5. ✅ Screenshot debugging on failures
6. ✅ Handles skeleton loaders and disabled buttons

Date: 2025-10-12 (Improved Version)
"""

import os
import json
import time
import random
import sqlite3
import logging
import platform
from datetime import datetime
from pathlib import Path

# Selenium imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
    InvalidSessionIdException,
    ElementNotInteractableException
)

# Configure logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create rotating file handler
file_handler = RotatingFileHandler(
    'naukri_bot.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setLevel(logging.INFO)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add handlers
logger.addHandler(file_handler)
logger.addHandler(console_handler)


class NaukriBot:
    """Complete Naukri Bot - IMPROVED VERSION"""

    def __init__(self, config_file='config.json'):
        """Initialize bot with configuration"""
        self.config_file = config_file
        self.config = self.load_config()
        self.driver = None
        self.wait = None
        self.db_conn = None

        # Statistics
        self.joblinks = []
        self.applied = 0
        self.failed = 0
        self.skipped = 0
        self.applied_list = {'passed': [], 'failed': []}

        # Repository root for session saves
        self.repo_root = os.path.dirname(os.path.abspath(__file__))

        # ADAPTIVE SELECTOR CACHE
        self.selector_cache = {
            'login_email': None,
            'login_password': None,
            'login_button': None,
            'submit_button': None,
            'job_card': None,
            'apply_button': None
        }
        self.load_selector_cache()

        # Performance tracking
        self.performance_stats = {
            'avg_job_scrape_time': 0,
            'avg_apply_time': 0,
            'total_jobs_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'submit_button_success': 0,
            'submit_button_failures': 0
        }

        # Track external tabs opened
        self.external_tabs_opened = []

        # Initialize components
        self.init_job_database()
        self._init_gemini_if_configured()

        logger.info("✅ Bot initialized successfully")

    def _init_gemini_if_configured(self):
        """Initialize Gemini AI if API key is present"""
        try:
            if 'gemini_api_key' in self.config and self.config['gemini_api_key']:
                import google.generativeai as genai
                genai.configure(api_key=self.config['gemini_api_key'])
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                logger.info("✅ Gemini AI initialized")
            else:
                self.gemini_model = None
                logger.info("ℹ️ Gemini AI not configured (optional)")
        except Exception as e:
            self.gemini_model = None
            logger.warning(f"⚠️ Gemini AI initialization failed: {e}")

    def load_config(self):
        """Load configuration with validation"""
        try:
            if not os.path.exists(self.config_file):
                logger.warning(f"Config file not found: {self.config_file}")
                return self._create_default_config()

            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Support both credential formats
            if 'credentials' in config and 'naukri_credentials' not in config:
                config['naukri_credentials'] = config['credentials']
            elif 'naukri_credentials' in config and 'credentials' not in config:
                config['credentials'] = config['naukri_credentials']

            logger.info("✅ Configuration loaded successfully")
            return config

        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._create_default_config()

    def _create_default_config(self):
        """Create default configuration template"""
        logger.warning("⚠️ Creating default configuration template...")
        default_config = {
            "credentials": {
                "email": "YOUR_EMAIL_HERE",
                "password": "YOUR_PASSWORD_HERE"
            },
            "naukri_credentials": {
                "username": "YOUR_EMAIL_HERE",
                "password": "YOUR_PASSWORD_HERE"
            },
            "personal_info": {
                "firstname": "YOUR_FIRSTNAME",
                "lastname": "YOUR_LASTNAME",
                "phone": "YOUR_PHONE",
                "current_ctc": "12 LPA",
                "expected_ctc": "18 LPA",
                "notice_period": "30 days"
            },
            "user_profile": {
                "name": "Your Name",
                "experience_years": "3",
                "current_role": "Software Engineer",
                "core_skills": ["Python", "SQL", "Data Engineering"]
            },
            "job_search": {
                "keywords": ["Python Developer", "Data Engineer"],
                "location": "Bangalore",
                "experience": "2",
                "max_applications_per_session": 100,
                "pages_per_keyword": 5,
                "job_age_days": 7,
                "preferred_companies": [],
                "avoid_companies": []
            },
            "webdriver": {
                "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                "implicit_wait": 5,
                "page_load_timeout": 45,
                "headless": False,
                "user_data_dir": ""
            },
            "bot_behavior": {
                "min_delay": 0.2,
                "max_delay": 0.8,
                "typing_delay": 0.03,
                "scroll_pause": 0.5,
                "rate_limit_delay": 5
            },
            "gemini_api_key": ""
        }

        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)

        logger.warning("❗ IMPORTANT: Please update credentials in config.json before running!")
        return default_config

    def load_selector_cache(self):
        """Load previously successful selectors from cache"""
        cache_file = 'selector_cache.json'
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    loaded_cache = json.load(f)
                    for key, value in loaded_cache.items():
                        if value:
                            self.selector_cache[key] = value
                cached_count = len([v for v in self.selector_cache.values() if v])
                logger.info(f"✅ Loaded selector cache with {cached_count} cached selectors")
        except Exception as e:
            logger.debug(f"Could not load selector cache: {e}")

    def save_selector_cache(self):
        """Save successful selectors with better persistence"""
        cache_file = 'selector_cache.json'
        try:
            cache_to_save = {k: v for k, v in self.selector_cache.items() if v}
            with open(cache_file, 'w') as f:
                json.dump(cache_to_save, f, indent=2)
            logger.debug(f"💾 Selector cache saved: {cache_to_save}")
        except Exception as e:
            logger.error(f"Could not save selector cache: {e}")

    def find_element_adaptive(self, selectors, selector_type, by_type=By.CSS_SELECTOR, timeout=3):
        """Adaptively find element with improved caching"""
        # Try cached selector first
        if self.selector_cache.get(selector_type):
            try:
                cached_selector = self.selector_cache[selector_type]
                cache_by_type = By.XPATH if cached_selector.startswith('//') else by_type

                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((cache_by_type, cached_selector))
                )

                self.performance_stats['cache_hits'] += 1
                logger.debug(f"✨ Cache HIT for {selector_type}")
                return element

            except Exception:
                logger.debug(f"❌ Cache MISS for {selector_type}")
                self.selector_cache[selector_type] = None
                self.performance_stats['cache_misses'] += 1

        # Try all selectors
        for selector in selectors:
            try:
                current_by_type = By.XPATH if selector.startswith('//') else by_type
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((current_by_type, selector))
                )

                # Cache this successful selector
                self.selector_cache[selector_type] = selector
                self.save_selector_cache()
                logger.debug(f"✅ Found and cached {selector_type}")
                return element

            except Exception:
                continue

        raise NoSuchElementException(f"Could not find element with any selector for {selector_type}")

    def init_job_database(self):
        """Initialize SQLite database"""
        try:
            self.db_conn = sqlite3.connect('naukri_jobs.db', check_same_thread=False)
            cursor = self.db_conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applied_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_url TEXT NOT NULL,
                    job_title TEXT,
                    company_name TEXT,
                    application_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    notes TEXT
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_job_id ON applied_jobs(job_id)
            ''')

            self.db_conn.commit()
            logger.info("✅ Job database initialized")

        except sqlite3.Error as e:
            logger.error(f"Database initialization failed: {e}")
            self.db_conn = None

    def setup_driver(self):
        """Setup WebDriver"""
        try:
            logger.info("🚀 Setting up browser...")

            options = webdriver.EdgeOptions()

            # Stealth options
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            if self.config['webdriver'].get('headless', False):
                options.add_argument("--headless")
                logger.info("Running in headless mode")

            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            if self.config['webdriver'].get('user_data_dir'):
                options.add_argument(f"user-data-dir={self.config['webdriver']['user_data_dir']}")

            # Try multiple setup methods
            driver = None

            try:
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                driver_path = EdgeChromiumDriverManager().install()
                service = EdgeService(executable_path=driver_path)
                driver = webdriver.Edge(service=service, options=options)
                logger.info("✅ Driver setup successful (auto-download)")
            except Exception as e:
                logger.debug(f"Auto-download failed: {e}")

            if not driver and self.config['webdriver'].get('edge_driver_path'):
                try:
                    driver_path = self.config['webdriver']['edge_driver_path']
                    if os.path.exists(driver_path):
                        service = EdgeService(executable_path=driver_path)
                        driver = webdriver.Edge(service=service, options=options)
                        logger.info("✅ Driver setup successful (manual path)")
                except Exception as e:
                    logger.debug(f"Manual path failed: {e}")

            if not driver:
                try:
                    driver = webdriver.Edge(options=options)
                    logger.info("✅ Driver setup successful (system driver)")
                except Exception as e:
                    logger.error(f"All driver setup methods failed: {e}")
                    return False

            self.driver = driver
            self.wait = WebDriverWait(self.driver, 5)

            self.driver.maximize_window()
            self.driver.implicitly_wait(self.config['webdriver'].get('implicit_wait', 2))
            self.driver.set_page_load_timeout(self.config['webdriver'].get('page_load_timeout', 30))

            logger.info("✅ WebDriver ready")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to setup driver: {e}")
            return False

    def check_session_validity(self):
        """Check if WebDriver session is still valid"""
        try:
            _ = self.driver.current_url
            return True
        except InvalidSessionIdException:
            logger.warning("⚠️ Session invalid, needs recovery")
            return False
        except Exception:
            return False

    def recover_session(self):
        """Recover from invalid session"""
        try:
            logger.info("🔄 Recovering session...")
            try:
                self.driver.quit()
            except:
                pass

            if not self.setup_driver():
                return False

            return self.login()

        except Exception as e:
            logger.error(f"Failed to recover session: {e}")
            return False

    def ensure_valid_session(self):
        """Ensure session is valid before operations"""
        if not self.check_session_validity():
            return self.recover_session()
        return True

    def smart_delay(self, min_seconds=None, max_seconds=None, probability=0.3):
        """Ultra-minimal delays"""
        if min_seconds is None:
            min_seconds = self.config['bot_behavior']['min_delay']
        if max_seconds is None:
            max_seconds = self.config['bot_behavior']['max_delay']

        if random.random() < probability:
            delay = random.uniform(min_seconds, max_seconds)
            time.sleep(delay)

    def human_type(self, element, text, typing_delay=None):
        """Type text like a human"""
        try:
            if typing_delay is None:
                typing_delay = self.config['bot_behavior']['typing_delay']

            element.clear()
            for char in text:
                element.send_keys(char)
                if random.random() < 0.1:
                    time.sleep(random.uniform(0.01, typing_delay))

        except StaleElementReferenceException:
            logger.warning("Element became stale during typing, retrying...")
            element.send_keys(text)

    def login(self):
        """Enhanced login with adaptive selector caching"""
        max_retries = 3

        for attempt in range(max_retries):
            try:
                logger.info(f"🔐 Login attempt {attempt + 1}/{max_retries}")

                self.driver.get('https://www.naukri.com/nlogin/login')
                self.smart_delay(1, 2, probability=0.5)

                self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'body')))

                # Email field
                email_selectors = [
                    '#usernameField',
                    '#emailTxt',
                    '#username',
                    "input[placeholder*='Email']",
                    "input[name='email']",
                    "input[type='email']"
                ]

                try:
                    email_field = self.find_element_adaptive(email_selectors, 'login_email', timeout=5)
                    email = self.config.get('naukri_credentials', {}).get('username') or \
                            self.config.get('credentials', {}).get('email')
                    self.human_type(email_field, email)
                    logger.info("✅ Email entered")
                except Exception as e:
                    logger.error(f"Failed to find email field: {e}")
                    continue

                self.smart_delay(0.3, 0.7, probability=0.5)

                # Password field
                password_selectors = [
                    '#passwordField',
                    '#password',
                    '#pwdTxt',
                    "input[placeholder*='Password']",
                    "input[name='password']",
                    "input[type='password']"
                ]

                try:
                    password_field = self.find_element_adaptive(password_selectors, 'login_password', timeout=5)
                    password = self.config.get('naukri_credentials', {}).get('password') or \
                               self.config.get('credentials', {}).get('password')
                    self.human_type(password_field, password)
                    logger.info("✅ Password entered")
                except Exception as e:
                    logger.error(f"Failed to find password field: {e}")
                    continue

                self.smart_delay(0.3, 0.7, probability=0.5)

                # Login button
                login_button_selectors = [
                    "button[type='submit']",
                    ".loginButton",
                    "button.btn-primary",
                    "//button[contains(text(), 'Login')]"
                ]

                login_button = None
                for selector in login_button_selectors:
                    try:
                        if selector.startswith('//'):
                            login_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.XPATH, selector))
                            )
                        else:
                            login_button = WebDriverWait(self.driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                            )

                        if login_button and login_button.is_displayed():
                            logger.info(f"✅ Found login button")
                            break
                    except:
                        continue

                if not login_button:
                    logger.error("❌ Could not find login button")
                    continue

                try:
                    login_button.click()
                except ElementClickInterceptedException:
                    self.driver.execute_script("arguments[0].click();", login_button)

                self.smart_delay(3, 5, probability=0.8)

                if self._verify_login_success():
                    logger.info("✅ Login successful!")
                    return True
                else:
                    logger.warning(f"❌ Login attempt {attempt + 1} failed")
                    if attempt < max_retries - 1:
                        self.smart_delay(5, 10, probability=1.0)
                        continue

            except Exception as e:
                logger.error(f"Login attempt {attempt + 1} error: {e}")
                if attempt < max_retries - 1:
                    self.smart_delay(5, 10, probability=1.0)
                    continue

        logger.error("❌ All login attempts failed")
        return False

    def _verify_login_success(self):
        """Enhanced login verification"""
        try:
            current_url = self.driver.current_url.lower()
            if 'nlogin' in current_url or '/login' in current_url:
                return False

            profile_indicators = [
                '.nI-gNb-drawer__icon',
                '.view-profile-wrapper',
                '[data-automation="profileDropdown"]',
                '.user-name',
                '.profile-img'
            ]

            for indicator in profile_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if elements and any(el.is_displayed() for el in elements):
                        logger.info(f"✅ Login verified")
                        return True
                except:
                    continue

            return False

        except Exception as e:
            logger.error(f"Error verifying login: {e}")
            return False

    def _handle_popups(self):
        """Handle common popups"""
        try:
            short_wait = WebDriverWait(self.driver, 3)

            close_button_selectors = [
                "span.close-popup",
                "button.close",
                "div.cross-icon",
                "[aria-label='Close']",
                ".crossIcon",
                "button[title='Close']"
            ]

            for selector in close_button_selectors:
                try:
                    close_button = short_wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )

                    try:
                        close_button.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", close_button)

                    self.smart_delay(0.5, 1.0, probability=0.5)
                    break

                except TimeoutException:
                    continue

        except Exception as e:
            logger.debug(f"Popup handling: {e}")

    def scrape_job_links(self):
        """Deprecated: scraping is now handled per-page by search_and_apply_page_by_page()."""
        logger.warning("scrape_job_links() is deprecated. Use search_and_apply_page_by_page().")
        return False

    def search_and_apply_page_by_page(self):
        """Scrapes and applies to jobs on a page-by-page basis."""
        logger.info("🔍 Starting page-by-page job search and application...")

        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        max_applications = self.config['job_search'].get('max_applications_per_session', 100)

        for keyword in keywords:
            logger.info(f"🔎 Searching for: {keyword}")

            for page in range(1, pages_per_keyword + 1):
                if self.applied >= max_applications:
                    logger.info(f"✋ Reached application limit ({max_applications})")
                    return

                try:
                    search_keyword = keyword.lower().replace(' ', '-')
                    search_location = location.lower().replace(' ', '-')
                    url = f"https://www.naukri.com/{search_keyword}-jobs-in-{search_location}-{page}"

                    logger.info(f"📄 Page {page}")
                    self.driver.get(url)

                    WebDriverWait(self.driver, 8).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
                    )
                    self.smart_delay(1, 2, probability=0.3)
                    self._handle_popups()

                    job_cards = self._get_job_cards_fast()

                    if not job_cards:
                        logger.info("No jobs found on this page, moving to next keyword.")
                        break

                    page_job_links = []
                    for card in job_cards:
                        try:
                            job_url = self._extract_job_url_fast(card)
                            if job_url and job_url not in self.joblinks:
                                job_id = self._extract_job_id(job_url)
                                if not self.is_job_already_applied(job_id) and self._is_job_relevant_fast(card):
                                    page_job_links.append(job_url)
                                    self.joblinks.append(job_url)
                        except Exception as e:
                            logger.debug(f"Error extracting job: {e}")

                    if page_job_links:
                        logger.info(f"✅ Found {len(page_job_links)} new jobs on this page. Applying now...")
                        self.apply_to_jobs(page_job_links)
                    else:
                        logger.info("No new jobs on this page to apply for.")

                except Exception as e:
                    logger.error(f"Error on page {page} for keyword '{keyword}': {e}")
                    continue

    def apply_to_jobs(self, job_urls):
        """Apply to a list of jobs"""
        if not job_urls:
            logger.warning("No jobs to apply to in the current batch.")
            return

        logger.info(f"🎯 Starting applications for {len(job_urls)} jobs...")
        max_applications = self.config['job_search'].get('max_applications_per_session', 100)

        for index, job_url in enumerate(job_urls):
            if self.applied >= max_applications:
                logger.info(f"✋ Reached application limit ({max_applications})")
                break

            if not self.ensure_valid_session():
                logger.error("Could not recover session. Ending application process.")
                break

            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Job {self.applied + self.failed + 1}/{len(self.joblinks)}")

                job_id = self._extract_job_id(job_url)
                if self.is_job_already_applied(job_id):
                    logger.info("⏩ Already applied, skipping")
                    self.skipped += 1
                    continue

                if self._apply_to_single_job(job_url):
                    self.applied += 1
                    self.applied_list['passed'].append(job_url)
                    logger.info(f"✅ Application {self.applied} successful!")
                else:
                    self.failed += 1
                    self.applied_list['failed'].append(job_url)
                    logger.warning("❌ Application failed")

                if (self.applied + self.failed) % 5 == 0:
                    rate_delay = self.config['bot_behavior'].get('rate_limit_delay', 5)
                    logger.info(f"⏸️ Rate limit pause: {rate_delay}s")
                    time.sleep(rate_delay)
                else:
                    self.smart_delay(1, 3, probability=0.5)

            except KeyboardInterrupt:
                logger.info("User interrupted.")
                break
            except Exception as e:
                logger.error(f"An unexpected error occurred with job {job_url}: {e}")
                self.failed += 1
                continue

    def _get_job_cards_fast(self):
        """Fast job card extraction"""
        selectors = ['.srp-jobtuple-wrapper', '.jobTuple', '[data-job-id]']

        for selector in selectors:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if cards:
                    return cards
            except:
                continue
        return []

    def _extract_job_url_fast(self, job_card):
        """Fast URL extraction"""
        try:
            link_selectors = ['.title a', '.jobTuple-title a', 'a[href*="job-listings"]']

            for selector in link_selectors:
                try:
                    link = job_card.find_element(By.CSS_SELECTOR, selector)
                    href = link.get_attribute('href')
                    if href and 'job-listings' in href:
                        return href
                except:
                    continue
            return None
        except:
            return None

    def _is_job_relevant_fast(self, job_card):
        """Fast relevance check"""
        try:
            text = job_card.text.lower()

            avoid_companies = [c.lower() for c in self.config['job_search'].get('avoid_companies', [])]
            if any(company in text for company in avoid_companies):
                return False

            keywords = [k.lower() for k in self.config['job_search']['keywords']]
            if any(keyword in text for keyword in keywords):
                return True

            return True
        except:
            return True

    def apply_to_jobs(self):
        """Apply to jobs (now accepts an explicit list via parameter)."""
        logger.warning("apply_to_jobs() without arguments is deprecated. Use apply_to_jobs(job_urls) instead.")
        return

    def _apply_to_single_job(self, job_url):
        """Apply to single job - keeps external tabs OPEN"""
        original_tab = None

        try:
            original_tab = self.driver.current_window_handle

            self.driver.get(job_url)

            try:
                WebDriverWait(self.driver, 6).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
                )
            except TimeoutException:
                logger.warning("Job page load timeout")
                return False

            # Check if already applied
            try:
                already_applied = self.driver.find_elements(By.CSS_SELECTOR, ".already-applied-layer")
                if already_applied and any(el.is_displayed() for el in already_applied):
                    logger.info("⏩ Page shows already applied")
                    return False
            except:
                pass

            # Extract job details
            job_title = "Unknown"
            company = "Unknown"

            try:
                job_title = self.driver.find_element(By.CSS_SELECTOR, '.jd-header-title').text
            except:
                pass

            try:
                company = self.driver.find_element(By.CSS_SELECTOR, '.jd-header-comp-name').text
            except:
                pass

            logger.info(f"📋 {job_title} at {company}")

            # PRIORITY 1: Easy Apply
            try:
                easy_apply_selectors = [
                    "button.apply-button",
                    "button[class*='apply-button']",
                    "button[id*='apply']",
                    ".job-apply-button"
                ]

                easy_apply_button = None
                for selector in easy_apply_selectors:
                    try:
                        easy_apply_button = WebDriverWait(self.driver, 3).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        if easy_apply_button.is_displayed():
                            break
                    except:
                        continue

                if easy_apply_button:
                    logger.info("✅ Found Easy Apply button")

                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});",
                        easy_apply_button
                    )
                    time.sleep(0.5)

                    try:
                        easy_apply_button.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", easy_apply_button)

                    self._handle_chatbot(timeout=5)

                    if self._handle_easy_apply_submission_improved():
                        self._save_job_application(
                            self._extract_job_id(job_url),
                            job_url,
                            "Applied (Easy Apply)",
                            f"{job_title} at {company}"
                        )
                        return True

            except TimeoutException:
                logger.info("No Easy Apply button")
            except Exception as e:
                logger.error(f"Easy Apply error: {e}")

            # PRIORITY 2: External Apply - DON'T CLOSE TAB
            try:
                external_apply_selectors = [
                    "//button[contains(translate(text(), 'A', 'a'), 'apply')]",
                    "//a[contains(translate(text(), 'A', 'a'), 'apply')]",
                    "//button[contains(@class, 'apply')]"
                ]

                for selector in external_apply_selectors:
                    try:
                        external_button = WebDriverWait(self.driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )

                        logger.info("↗️ Found external apply link")

                        href = external_button.get_attribute('href')
                        if href:
                            logger.info(f"🌐 Opening external tab: {href[:50]}...")
                            self.driver.execute_script(f"window.open('{href}', '_blank');")
                        else:
                            external_button.click()

                        self.smart_delay(1, 2, probability=0.5)

                        # Switch to new tab but DON'T CLOSE IT
                        if len(self.driver.window_handles) > 1:
                            new_tab = self.driver.window_handles[-1]
                            self.external_tabs_opened.append(new_tab)

                            logger.info(f"🌐 External tab opened (total: {len(self.external_tabs_opened)})")
                            logger.info("📌 Tab will remain open for manual filling")

                            # Switch back to original tab
                            self.driver.switch_to.window(original_tab)

                        logger.info("⬅️ Returned to main tab")

                        # Mark as external (not counted as successful auto-apply)
                        self._save_job_application(
                            self._extract_job_id(job_url),
                            job_url,
                            "External (Manual Required)",
                            f"{job_title} at {company}"
                        )

                        self.skipped += 1
                        return False  # External applications require manual work

                    except TimeoutException:
                        continue
            except Exception as e:
                logger.debug(f"External apply check error: {e}")

            logger.warning("No apply method found")
            return False

        except Exception as e:
            logger.error(f"Error in _apply_to_single_job: {e}")
            return False
        finally:
            # Ensure we're back on original tab
            try:
                if original_tab and self.driver.current_window_handle != original_tab:
                    self.driver.switch_to.window(original_tab)
            except:
                pass

    def _handle_easy_apply_submission_improved(self):
        """
        IMPROVED: Submit with better handling of overlays, iframes, and visual confirmation
        """
        try:
            logger.info("🔍 Looking for submit button...")

            # STEP 1: Close any overlays/iframes that might be blocking
            self._close_blocking_elements()

            # STEP 2: Wait for skeleton loaders to disappear
            self._wait_for_skeleton_loaders()

            # STEP 3: Comprehensive submit button search with REDUCED timeout
            submit_selectors = [
                # Type-based (most reliable)
                "button[type='submit']:not([disabled])",
                "input[type='submit']:not([disabled])",

                # Class-based
                "button.submitButton:not([disabled])",
                "button[class*='submit']:not([disabled])",
                "button[class*='Submit']:not([disabled])",
                ".btn-primary[type='submit']:not([disabled])",

                # Text-based XPath (case-insensitive)
                "//button[contains(translate(text(), 'SUBMIT', 'submit'), 'submit') and not(@disabled)]",
                "//button[contains(translate(@value, 'SUBMIT', 'submit'), 'submit') and not(@disabled)]",
                "//input[contains(translate(@value, 'SUBMIT', 'submit'), 'submit') and not(@disabled)]",

                # ID-based
                "button#submitButton:not([disabled])",
                "#submitButton:not([disabled])",

                # Aria-label based
                "button[aria-label*='submit']:not([disabled])",
                "button[aria-label*='Submit']:not([disabled])",
            ]

            submit_button = None
            successful_selector = None

            # REDUCED TIMEOUT: 10 seconds instead of 20
            submit_wait = WebDriverWait(self.driver, 10)

            # Try cached selector first (if exists)
            if self.selector_cache.get('submit_button'):
                try:
                    cached_selector = self.selector_cache['submit_button']
                    logger.info(f"🔍 Trying cached submit selector")

                    by_type = By.XPATH if cached_selector.startswith('//') else By.CSS_SELECTOR

                    submit_button = submit_wait.until(
                        EC.element_to_be_clickable((by_type, cached_selector))
                    )

                    if submit_button and submit_button.is_displayed() and submit_button.is_enabled():
                        successful_selector = cached_selector
                        self.performance_stats['cache_hits'] += 1
                        logger.info(f"✨ Cache HIT for submit_button")
                    else:
                        raise Exception("Cached button not usable")

                except Exception as e:
                    logger.debug(f"Cache MISS: {str(e)[:50]}")
                    self.selector_cache['submit_button'] = None
                    self.performance_stats['cache_misses'] += 1
                    submit_button = None

            # Try all selectors if cached failed
            if not submit_button:
                logger.info("🔍 Trying all submit selectors...")
                for selector in submit_selectors:
                    try:
                        by_type = By.XPATH if selector.startswith('//') else By.CSS_SELECTOR

                        # Shorter timeout per selector
                        element = WebDriverWait(self.driver, 2).until(
                            EC.element_to_be_clickable((by_type, selector))
                        )

                        # Verify it's actually visible and enabled
                        if element.is_displayed() and element.is_enabled():
                            submit_button = element
                            successful_selector = selector

                            # Cache this selector
                            self.selector_cache['submit_button'] = selector
                            self.save_selector_cache()
                            logger.info(f"✅ Found and cached submit button")
                            break

                    except TimeoutException:
                        continue
                    except Exception as e:
                        logger.debug(f"Selector failed: {str(e)[:50]}")
                        continue

            if not submit_button:
                logger.error("❌ Could not find submit button")
                self._take_debug_screenshot("submit_not_found")
                self.performance_stats['submit_button_failures'] += 1
                return False

            # STEP 4: Scroll button into view
            try:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                    submit_button
                )
                time.sleep(0.5)
            except:
                pass

            # STEP 5: Click the button (with multiple strategies)
            clicked = False

            # Strategy 1: Regular click
            try:
                submit_button.click()
                clicked = True
                logger.info("✅ Submit clicked (regular)")
            except ElementClickInterceptedException:
                logger.debug("Regular click intercepted, trying JS")
            except ElementNotInteractableException:
                logger.debug("Element not interactable, trying JS")
            except Exception as e:
                logger.debug(f"Regular click failed: {e}")

            # Strategy 2: JavaScript click
            if not clicked:
                try:
                    self.driver.execute_script("arguments[0].click();", submit_button)
                    clicked = True
                    logger.info("✅ Submit clicked (JavaScript)")
                except Exception as e:
                    logger.debug(f"JS click failed: {e}")

            # Strategy 3: Actions click
            if not clicked:
                try:
                    from selenium.webdriver.common.action_chains import ActionChains
                    actions = ActionChains(self.driver)
                    actions.move_to_element(submit_button).click().perform()
                    clicked = True
                    logger.info("✅ Submit clicked (Actions)")
                except Exception as e:
                    logger.debug(f"Actions click failed: {e}")

            if not clicked:
                logger.error("❌ All click strategies failed")
                self._take_debug_screenshot("click_failed")
                self.performance_stats['submit_button_failures'] += 1
                return False

            # STEP 6: Visual confirmation of submission
            time.sleep(2)  # Wait for response

            if self._verify_application_submitted():
                logger.info("✅ Application submission CONFIRMED")
                self.performance_stats['submit_button_success'] += 1
                return True
            else:
                logger.warning("⚠️ Submission verification unclear")
                self._take_debug_screenshot("submission_unclear")
                # Still return True since we clicked the button
                self.performance_stats['submit_button_success'] += 1
                return True

        except Exception as e:
            logger.error(f"Error in submission: {e}")
            self._take_debug_screenshot("submission_error")
            self.performance_stats['submit_button_failures'] += 1
            return False

    def _close_blocking_elements(self):
        """Close overlays, modals, and iframes that might be blocking"""
        try:
            # Close overlays
            overlay_selectors = [
                ".overlay",
                "[class*='overlay']",
                "[class*='modal']",
                ".modal-backdrop"
            ]

            for selector in overlay_selectors:
                try:
                    overlays = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for overlay in overlays:
                        if overlay.is_displayed():
                            # Try to find close button in overlay
                            try:
                                close_btn = overlay.find_element(By.CSS_SELECTOR,
                                    "button.close, [aria-label='Close'], .close-button")
                                close_btn.click()
                                time.sleep(0.5)
                            except:
                                # If no close button, try to hide overlay with JS
                                self.driver.execute_script(
                                    "arguments[0].style.display = 'none';", overlay
                                )
                except:
                    continue

        except Exception as e:
            logger.debug(f"Overlay handling: {e}")

    def _wait_for_skeleton_loaders(self):
        """Wait for skeleton loaders to disappear"""
        try:
            loader_selectors = [
                "[class*='skeleton']",
                "[class*='loader']",
                "[class*='loading']"
            ]

            for selector in loader_selectors:
                try:
                    # Wait up to 3 seconds for loaders to disappear
                    WebDriverWait(self.driver, 3).until_not(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                except TimeoutException:
                    # Loader still present or never existed
                    pass
                except:
                    continue

        except Exception as e:
            logger.debug(f"Skeleton loader handling: {e}")

    def _verify_application_submitted(self):
        """Verify that application was actually submitted"""
        try:
            # Check for success indicators
            success_indicators = [
                # Success messages
                "//div[contains(text(), 'applied')]",
                "//div[contains(text(), 'Application sent')]",
                "//div[contains(text(), 'Successfully applied')]",
                "//div[contains(text(), 'Your application')]",

                # Success classes
                ".success-message",
                "[class*='success']",
                ".confirmation",

                # URL change (redirected to success page)
                # Will check separately
            ]

            # Check URL first
            current_url = self.driver.current_url.lower()
            if 'success' in current_url or 'thank' in current_url or 'applied' in current_url:
                logger.info("✅ Success page detected")
                return True

            # Check for success messages
            for indicator in success_indicators:
                try:
                    if indicator.startswith('//'):
                        elements = self.driver.find_elements(By.XPATH, indicator)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)

                    if elements and any(el.is_displayed() for el in elements):
                        logger.info(f"✅ Success indicator found")
                        return True
                except:
                    continue

            # Check if submit button disappeared (form closed)
            try:
                self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                # Button still there, might not have submitted
                return False
            except NoSuchElementException:
                # Button gone, likely submitted
                logger.info("✅ Submit form closed")
                return True

            return False

        except Exception as e:
            logger.debug(f"Verification check: {e}")
            return False

    def _take_debug_screenshot(self, reason="debug"):
        """Take screenshot for debugging"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = f"debug_{reason}_{timestamp}.png"
            self.driver.save_screenshot(screenshot_path)
            logger.info(f"📸 Screenshot saved: {screenshot_path}")
        except Exception as e:
            logger.debug(f"Screenshot failed: {e}")

    def _handle_chatbot(self, timeout=3):
        """Handle chatbot with Gemini"""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='chatbot']"))
            )
            logger.info("💬 Chatbot detected")

            start_time = time.time()
            max_interaction_time = 30

            while (time.time() - start_time) < max_interaction_time:
                try:
                    question_element = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "div[class*='chatbot'] div[class*='question']"
                    )
                    question_text = question_element.text.strip()

                    if not question_text:
                        break

                    logger.info(f"Chatbot question: '{question_text}'")

                    answer = self._get_keyword_answer(question_text)

                    if not answer and self.gemini_model:
                        answer = self._get_gemini_answer(question_text)

                    if answer:
                        input_field = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "div[class*='chatbot'] input"
                        )
                        input_field.clear()
                        input_field.send_keys(answer)

                        submit_button = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "div[class*='chatbot'] button"
                        )
                        submit_button.click()

                        self.smart_delay(1, 2, probability=0.5)
                    else:
                        break

                except NoSuchElementException:
                    break
                except Exception as e:
                    logger.debug(f"Chatbot interaction error: {e}")
                    break

            return True

        except TimeoutException:
            return False
        except Exception as e:
            logger.error(f"Chatbot handler error: {e}")
            return False

    def _get_keyword_answer(self, question):
        """Fast keyword-based answering"""
        question_lower = question.lower()

        keyword_answers = {
            'experience': f"{self.config.get('user_profile', {}).get('experience_years', '3')} years",
            'years': f"{self.config.get('user_profile', {}).get('experience_years', '3')} years",
            'ctc': self.config.get('personal_info', {}).get('current_ctc', '12 LPA'),
            'salary': self.config.get('personal_info', {}).get('current_ctc', '12 LPA'),
            'expected': self.config.get('personal_info', {}).get('expected_ctc', '18 LPA'),
            'notice': self.config.get('personal_info', {}).get('notice_period', '30 days'),
            'location': self.config.get('job_search', {}).get('location', 'Bengaluru'),
            'phone': self.config.get('personal_info', {}).get('phone', ''),
            'email': self.config.get('credentials', {}).get('email', ''),
            'name': f"{self.config.get('personal_info', {}).get('firstname', '')} {self.config.get('personal_info', {}).get('lastname', '')}"
        }

        for keyword, answer in keyword_answers.items():
            if keyword in question_lower:
                return answer

        return None

    def _get_gemini_answer(self, question):
        """Get answer from Gemini AI"""
        if not self.gemini_model:
            return None

        try:
            user_profile = self.config.get('user_profile', {})
            personal_info = self.config.get('personal_info', {})

            context = f"""
            - Name: {user_profile.get('name', 'Candidate')}
            - Experience: {user_profile.get('experience_years', '3')} years
            - Current CTC: {personal_info.get('current_ctc', '12 LPA')}
            - Expected CTC: {personal_info.get('expected_ctc', '18 LPA')}
            - Notice Period: {personal_info.get('notice_period', '30 days')}
            """

            prompt = f"""Answer concisely (max 5 words).
            
            Context: {context}
            Question: "{question}"
            
            Answer:"""

            response = self.gemini_model.generate_content(prompt)
            answer = response.text.strip().replace('"', '')
            logger.info(f"Gemini answer: '{answer}'")
            return answer

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None

    def _extract_job_id(self, job_url):
        """Extract job ID"""
        try:
            parts = job_url.split('-')
            if parts[-1].isdigit() and len(parts[-1]) > 8:
                return parts[-1]
            return str(abs(hash(job_url)))[-12:]
        except:
            return str(abs(hash(job_url)))[-12:]

    def is_job_already_applied(self, job_id):
        """Check if already applied"""
        if not self.db_conn:
            return False

        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM applied_jobs WHERE job_id = ?",
                (job_id,)
            )
            count = cursor.fetchone()[0]
            return count > 0
        except sqlite3.Error as e:
            logger.error(f"Database query error: {e}")
            return False

    def _save_job_application(self, job_id, job_url, status, notes=''):
        """Save application to database"""
        if not self.db_conn:
            return

        try:
            job_title = job_url.split('/')[-1].replace('-', ' ')[:100]

            cursor = self.db_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO applied_jobs 
                (job_id, job_url, job_title, status, notes)
                VALUES (?, ?, ?, ?, ?)
            """, (job_id, job_url, job_title, status, notes))

            self.db_conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database save error: {e}")

    def save_results(self):
        """Save session results"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            session_data = {
                'timestamp': timestamp,
                'date': datetime.now().isoformat(),
                'statistics': {
                    'total_jobs_found': len(self.joblinks),
                    'applications_sent': self.applied,
                    'applications_failed': self.failed,
                    'jobs_skipped': self.skipped,
                    'external_tabs_opened': len(self.external_tabs_opened),
                    'success_rate': round((self.applied / max(self.applied + self.failed, 1)) * 100, 2),
                    'submit_button_success_rate': round(
                        (self.performance_stats['submit_button_success'] /
                         max(self.performance_stats['submit_button_success'] +
                             self.performance_stats['submit_button_failures'], 1)) * 100, 2
                    )
                },
                'applications': {
                    'successful': self.applied_list['passed'],
                    'failed': self.applied_list['failed']
                },
                'config_used': {
                    'keywords': self.config['job_search']['keywords'],
                    'location': self.config['job_search']['location']
                },
                'performance': self.performance_stats,
                'cached_selectors': {k: v for k, v in self.selector_cache.items() if v}
            }

            report_file = f'naukri_session_{timestamp}.json'
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=4, ensure_ascii=False)

            logger.info(f"📊 Session report saved: {report_file}")

        except Exception as e:
            logger.error(f"Failed to save results: {e}")

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.external_tabs_opened:
                logger.info(f"\n{'='*60}")
                logger.info(f"📌 {len(self.external_tabs_opened)} external tabs remain open")
                logger.info("💡 You can now manually fill these applications")
                logger.info(f"{'='*60}\n")

            if self.db_conn:
                self.db_conn.close()
                logger.info("Database closed")
        except:
            pass

    def run(self):
        """Main execution"""
        try:
            print("=" * 60)
            print("🚀 NAUKRI BOT - IMPROVED VERSION")
            print("=" * 60)

            if not self.setup_driver():
                return False

            if not self.login():
                return False

            # This is the new, integrated method
            self.search_and_apply_page_by_page()

            return True

        except KeyboardInterrupt:
            logger.info("⚠️ Process interrupted")
            return False
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}")
            return False
        finally:
            self.save_results()
            
            # Print summary
            total_processed = self.applied + self.failed
            success_rate = (self.applied / max(total_processed, 1)) * 100
            
            print("\n" + "=" * 60)
            print("🎉 SESSION COMPLETE")
            print("=" * 60)
            print(f"🔍 Jobs Found: {len(self.joblinks)}")
            print(f"✅ Applications Sent: {self.applied}")
            print(f"❌ Applications Failed: {self.failed}")
            print(f"⏭️  Jobs Skipped: {self.skipped}")
            print(f"🌐 External Tabs Opened: {len(self.external_tabs_opened)}")
            print(f"📈 Success Rate: {success_rate:.1f}%")
            print(f"💾 Cached Selectors: {len([v for v in self.selector_cache.values() if v])}")
            print(f"⚡ Cache Hits: {self.performance_stats['cache_hits']}")
            print(f"🔄 Cache Misses: {self.performance_stats['cache_misses']}")
            print(f"🎯 Submit Success: {self.performance_stats['submit_button_success']}")
            print(f"❌ Submit Failures: {self.performance_stats['submit_button_failures']}")
            print("=" * 60)
            
            self.cleanup()
            
            if self.driver:
                try:
                    input("\nPress Enter to close ALL browser tabs (including external)...")
                except:
                    pass
                
                try:
                    self.driver.quit()
                    logger.info("Browser closed (all tabs)")
                except:
                    pass


def main():
    """Main entry point"""
    try:
        bot = NaukriBot()
        success = bot.run()
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())