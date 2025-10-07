"""
Naukri Auto-Apply Bot - COMPLETE ULTRA-OPTIMIZED VERSION
==========================================================
ALL Features Included:
- ✅ Adaptive selector caching (NEW - learns which selectors work)
- ✅ Ultra-minimal delays (NEW - mostly zero, occasional 0.5-1s)
- ✅ Short timeouts (NEW - 3-5s instead of 15s)
- ✅ Session recovery (NEW - auto-recover from failures)
- ✅ Gemini AI chatbot integration (KEPT from original)
- ✅ Comprehensive popup handling (KEPT from original)
- ✅ Full database functionality (KEPT from original)
- ✅ External apply support (KEPT from original)
- ✅ Login verification (KEPT from original)
- ✅ Stale element protection (ENHANCED)
- ✅ Memory leak prevention (ENHANCED)
- ✅ Logging rotation (NEW)
- ✅ Performance tracking (NEW)

Author: Complete Merged Version
Date: 2025-10-07
Lines: ~1350 (ALL features included)
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
    InvalidSessionIdException
)

# Configure logging with rotation
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
    """Complete Naukri Bot with ALL features - original + optimizations"""
    
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
        
        # NEW: ADAPTIVE SELECTOR CACHE - learns which selectors work
        self.selector_cache = {
            'login_email': None,
            'login_password': None,
            'login_button': None,
            'submit_button': None,
            'job_card': None,
            'apply_button': None
        }
        self.load_selector_cache()
        
        # NEW: Performance tracking
        self.performance_stats = {
            'avg_job_scrape_time': 0,
            'avg_apply_time': 0,
            'total_jobs_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Initialize components
        self.init_job_database()
        
        # Initialize Gemini if configured (KEPT from original)
        self._init_gemini_if_configured()
        
        logger.info("✅ Bot initialized successfully")
    
    def _init_gemini_if_configured(self):
        """Initialize Gemini AI if API key is present (KEPT from original)"""
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
            
            # Support both 'credentials' and 'naukri_credentials' keys
            if 'credentials' in config and 'naukri_credentials' not in config:
                config['naukri_credentials'] = config['credentials']
            elif 'naukri_credentials' in config and 'credentials' not in config:
                config['credentials'] = config['naukri_credentials']
            
            # Validate required fields
            required_fields = ['job_search', 'webdriver', 'bot_behavior']
            for field in required_fields:
                if field not in config:
                    raise ValueError(f"Missing required config section: {field}")
            
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
                "phone": "YOUR_PHONE"
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
                "max_applications_per_session": 20,
                "pages_per_keyword": 3,
                "job_age_days": 7,
                "preferred_companies": [],
                "avoid_companies": []
            },
            "webdriver": {
                "edge_driver_path": "C:\\WebDrivers\\msedgedriver.exe",
                "implicit_wait": 10,
                "page_load_timeout": 30,
                "headless": False,
                "user_data_dir": ""
            },
            "bot_behavior": {
                "min_delay": 0.5,
                "max_delay": 1.0,
                "typing_delay": 0.05,
                "scroll_pause": 1,
                "rate_limit_delay": 10
            },
            "gemini_api_key": ""
        }
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4)
        
        logger.warning("❗ IMPORTANT: Please update credentials in config.json before running!")
        return default_config
    
    # NEW: Selector caching methods
    def load_selector_cache(self):
        """Load previously successful selectors from cache"""
        cache_file = 'selector_cache.json'
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    self.selector_cache = json.load(f)
                cached_count = len([v for v in self.selector_cache.values() if v])
                logger.info(f"✅ Loaded selector cache with {cached_count} cached selectors")
        except Exception as e:
            logger.debug(f"Could not load selector cache: {e}")
    
    def save_selector_cache(self):
        """Save successful selectors to cache for next run"""
        cache_file = 'selector_cache.json'
        try:
            with open(cache_file, 'w') as f:
                json.dump(self.selector_cache, f, indent=2)
            logger.debug("💾 Selector cache saved")
        except Exception as e:
            logger.debug(f"Could not save selector cache: {e}")
    
    def find_element_adaptive(self, selectors, selector_type, by_type=By.CSS_SELECTOR, timeout=3):
        """
        NEW: Adaptively find element - tries cached selector first, then others
        Learns and caches which selector works
        """
        # Try cached selector first if available
        if self.selector_cache.get(selector_type):
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by_type, self.selector_cache[selector_type]))
                )
                self.performance_stats['cache_hits'] += 1
                logger.debug(f"✨ Used cached selector for {selector_type}")
                return element
            except:
                logger.debug(f"Cached selector failed for {selector_type}, trying others...")
                self.selector_cache[selector_type] = None
                self.performance_stats['cache_misses'] += 1
        
        # Try all selectors
        for selector in selectors:
            try:
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by_type, selector))
                )
                # Cache this successful selector
                self.selector_cache[selector_type] = selector
                self.save_selector_cache()
                logger.debug(f"✅ Found and cached selector for {selector_type}: {selector}")
                return element
            except:
                continue
        
        raise NoSuchElementException(f"Could not find element with any selector for {selector_type}")
    
    def init_job_database(self):
        """Initialize SQLite database with proper error handling"""
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
        """Setup WebDriver with enhanced error handling and fallback options"""
        try:
            logger.info("🚀 Setting up browser...")
            logger.info(f"Operating System: {platform.system()} {platform.release()}")
            
            options = webdriver.EdgeOptions()
            
            # Stealth options
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Performance options
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            
            # Headless mode if configured
            if self.config['webdriver'].get('headless', False):
                options.add_argument("--headless")
                logger.info("Running in headless mode")
            
            # User agent
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0")
            
            # User data directory
            if self.config['webdriver'].get('user_data_dir'):
                options.add_argument(f"user-data-dir={self.config['webdriver']['user_data_dir']}")
            
            # Try multiple methods to setup driver
            driver = None
            
            # Method 1: webdriver-manager
            try:
                from webdriver_manager.microsoft import EdgeChromiumDriverManager
                driver_path = EdgeChromiumDriverManager().install()
                service = EdgeService(executable_path=driver_path)
                driver = webdriver.Edge(service=service, options=options)
                logger.info("✅ Driver setup successful (auto-download)")
            except Exception as e:
                logger.debug(f"Auto-download failed: {e}")
            
            # Method 2: Manual path
            if not driver and self.config['webdriver'].get('edge_driver_path'):
                try:
                    driver_path = self.config['webdriver']['edge_driver_path']
                    if os.path.exists(driver_path):
                        service = EdgeService(executable_path=driver_path)
                        driver = webdriver.Edge(service=service, options=options)
                        logger.info("✅ Driver setup successful (manual path)")
                except Exception as e:
                    logger.debug(f"Manual path failed: {e}")
            
            # Method 3: System driver
            if not driver:
                try:
                    driver = webdriver.Edge(options=options)
                    logger.info("✅ Driver setup successful (system driver)")
                except Exception as e:
                    logger.error(f"All driver setup methods failed: {e}")
                    return False
            
            self.driver = driver
            self.wait = WebDriverWait(self.driver, 5)  # Short default timeout
            
            # Configure driver
            self.driver.maximize_window()
            self.driver.implicitly_wait(self.config['webdriver'].get('implicit_wait', 2))
            self.driver.set_page_load_timeout(self.config['webdriver'].get('page_load_timeout', 30))
            
            logger.info("✅ WebDriver ready")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to setup driver: {e}")
            return False
    
    # NEW: Session management methods
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
        """
        NEW: Ultra-minimal delays - mostly no delay, occasionally short delay
        """
        if min_seconds is None:
            min_seconds = self.config['bot_behavior']['min_delay']
        if max_seconds is None:
            max_seconds = self.config['bot_behavior']['max_delay']
        
        # Only delay with given probability
        if random.random() < probability:
            delay = random.uniform(min_seconds, max_seconds)
            time.sleep(delay)
    
    def human_type(self, element, text, typing_delay=None):
        """Type text like a human with minimal delay"""
        try:
            if typing_delay is None:
                typing_delay = self.config['bot_behavior']['typing_delay']
            
            element.clear()
            for char in text:
                element.send_keys(char)
                # Occasional tiny delay
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
                
                # Email field with adaptive caching
                email_selectors = [
                    '#usernameField',
                    '#emailTxt',
                    '#username',
                    "input[placeholder*='Email']",
                    "input[placeholder*='email']",
                    "input[name='email']",
                    "input[type='email']",
                    "input[type='text'][placeholder*='Email']"
                ]
                
                try:
                    email_field = self.find_element_adaptive(
                        email_selectors,
                        'login_email',
                        timeout=5
                    )
                    email = self.config.get('naukri_credentials', {}).get('username') or \
                            self.config.get('credentials', {}).get('email')
                    self.human_type(email_field, email)
                    logger.info("✅ Email entered")
                except Exception as e:
                    logger.error(f"Failed to find email field: {e}")
                    continue
                
                self.smart_delay(0.3, 0.7, probability=0.5)
                
                # Password field with adaptive caching
                password_selectors = [
                    '#passwordField',
                    '#password',
                    '#pwdTxt',
                    "input[placeholder*='Password']",
                    "input[placeholder*='password']",
                    "input[name='password']",
                    "input[type='password']"
                ]
                
                try:
                    password_field = self.find_element_adaptive(
                        password_selectors,
                        'login_password',
                        timeout=5
                    )
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
                    "//button[contains(text(), 'Login')]",
                    "//button[contains(text(), 'login')]",
                    "//button[contains(@class, 'loginButton')]"
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
                            logger.info(f"✅ Found login button: {selector}")
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
                
                # Verify login
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
        """KEPT: Enhanced login verification from original"""
        try:
            current_url = self.driver.current_url.lower()
            if 'nlogin' in current_url or '/login' in current_url:
                logger.debug("Still on login page")
                return False
            
            profile_indicators = [
                '.nI-gNb-drawer__icon',
                '.view-profile-wrapper',
                '[data-automation="profileDropdown"]',
                '.nI-gNb-menuExpanded',
                '.user-name',
                '[title*="Profile"]',
                '.mn-hdr__profileName',
                '.profile-img'
            ]
            
            for indicator in profile_indicators:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, indicator)
                    if elements:
                        for el in elements:
                            try:
                                if el.is_displayed():
                                    logger.info(f"✅ Login verified using: {indicator}")
                                    return True
                            except StaleElementReferenceException:
                                continue
                except Exception:
                    continue
            
            try:
                original_url = self.driver.current_url
                self.driver.get('https://www.naukri.com/mnjuser/profile')
                self.smart_delay(2, 3, probability=0.5)
                
                if 'login' not in self.driver.current_url.lower():
                    logger.info("✅ Login verified by accessing profile")
                    self.driver.get(original_url)
                    return True
            except Exception as e:
                logger.debug(f"Profile page check failed: {e}")
            
            return False
            
        except Exception as e:
            logger.error(f"Error verifying login: {e}")
            return False
    
    def _handle_popups(self):
        """KEPT: Handle common popups and overlays from original"""
        try:
            short_wait = WebDriverWait(self.driver, 3)
            
            close_button_selectors = [
                "span.close-popup",
                "button.close",
                "div.cross-icon",
                "[aria-label='Close']",
                "i.naukri-icon-close",
                ".crossIcon",
                "[class*='close']",
                "button[title='Close']"
            ]
            
            for selector in close_button_selectors:
                try:
                    close_button = short_wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"Found popup, closing with: {selector}")
                    
                    try:
                        close_button.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", close_button)
                    
                    self.smart_delay(0.5, 1.0, probability=0.5)
                    
                except TimeoutException:
                    continue
                    
        except Exception as e:
            logger.debug(f"Popup handling: {e}")
    
    def scrape_job_links(self):
        """OPTIMIZED: Fast job extraction with early termination"""
        try:
            logger.info("🔍 Starting optimized job search...")
            
            keywords = self.config['job_search']['keywords']
            location = self.config['job_search']['location']
            pages_per_keyword = self.config['job_search']['pages_per_keyword']
            
            for keyword in keywords:
                logger.info(f"🔎 Searching for: {keyword}")
                
                consecutive_empty_pages = 0
                max_consecutive_empty = 2
                
                for page in range(1, pages_per_keyword + 1):
                    if consecutive_empty_pages >= max_consecutive_empty:
                        logger.info(f"No new jobs for '{keyword}' after {consecutive_empty_pages} pages")
                        break
                    
                    try:
                        search_keyword = keyword.lower().replace(' ', '-')
                        search_location = location.lower().replace(' ', '-')
                        url = f"https://www.naukri.com/{search_keyword}-jobs-in-{search_location}-{page}"
                        
                        logger.info(f"📄 Page {page}: {url}")
                        self.driver.get(url)
                        
                        try:
                            WebDriverWait(self.driver, 8).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, 'body'))
                            )
                        except TimeoutException:
                            logger.warning("Page load timeout")
                        
                        self.smart_delay(1, 2, probability=0.3)
                        self._handle_popups()
                        
                        job_cards = self._get_job_cards_fast()
                        
                        if not job_cards:
                            logger.warning("No job cards found")
                            consecutive_empty_pages += 1
                            continue
                        
                        logger.info(f"Found {len(job_cards)} job cards")
                        
                        page_jobs_count = 0
                        for card in job_cards:
                            try:
                                max_retries = 2
                                for attempt in range(max_retries):
                                    try:
                                        job_url = self._extract_job_url_fast(card)
                                        
                                        if job_url and job_url not in self.joblinks:
                                            job_id = self._extract_job_id(job_url)
                                            if not self.is_job_already_applied(job_id):
                                                if self._is_job_relevant_fast(card):
                                                    self.joblinks.append(job_url)
                                                    page_jobs_count += 1
                                        break
                                        
                                    except StaleElementReferenceException:
                                        if attempt < max_retries - 1:
                                            continue
                                        else:
                                            raise
                                            
                            except StaleElementReferenceException:
                                logger.debug("Stale element, skipping")
                                continue
                            except Exception as e:
                                logger.debug(f"Error extracting job: {e}")
                                continue
                        
                        if page_jobs_count == 0:
                            consecutive_empty_pages += 1
                        else:
                            consecutive_empty_pages = 0
                        
                        logger.info(f"Page {page}: Found {page_jobs_count} new relevant jobs")
                        self.smart_delay(0.5, 1.0, probability=0.2)
                        
                    except Exception as e:
                        logger.error(f"Error on page {page}: {e}")
                        continue
            
            logger.info(f"✅ Job search completed. Found {len(self.joblinks)} total jobs")
            return len(self.joblinks) > 0
            
        except Exception as e:
            logger.error(f"Error in scrape_job_links: {e}")
            return False
    
    def _get_job_cards_fast(self):
        """KEPT: Fast job card extraction from original"""
        selectors = [
            '.srp-jobtuple-wrapper',
            '.jobTuple',
            '[data-job-id]',
            'article.jobTuple'
        ]
        
        for selector in selectors:
            try:
                cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if cards and len(cards) > 0:
                    return cards
            except:
                continue
        
        return []
    
    def _extract_job_url_fast(self, job_card):
        """KEPT: Fast URL extraction from original"""
        try:
            link_selectors = [
                '.title a',
                '.jobTuple-title a',
                'a.title',
                'a[href*="job-listings"]'
            ]
            
            for selector in link_selectors:
                try:
                    link = job_card.find_element(By.CSS_SELECTOR, selector)
                    href = link.get_attribute('href')
                    if href and 'job-listings' in href:
                        return href
                except:
                    continue
            
            return None
            
        except Exception:
            return None
    
    def _is_job_relevant_fast(self, job_card):
        """KEPT: Fast relevance check from original"""
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
        """ENHANCED: Apply with session validation"""
        try:
            if not self.joblinks:
                logger.warning("No jobs to apply to")
                return
            
            logger.info(f"🎯 Starting applications to {len(self.joblinks)} jobs...")
            
            max_applications = self.config['job_search'].get('max_applications_per_session', 20)
            
            for index, job_url in enumerate(self.joblinks):
                if self.applied >= max_applications:
                    logger.info(f"✋ Reached application limit ({max_applications})")
                    break
                
                # NEW: Ensure valid session
                if not self.ensure_valid_session():
                    logger.error("Could not recover session, stopping")
                    break
                
                try:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"Applying to job {index + 1}/{len(self.joblinks)}: {job_url}")
                    
                    job_id = self._extract_job_id(job_url)
                    if self.is_job_already_applied(job_id):
                        logger.info("⏩ Already applied, skipping...")
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
                    
                    # Rate limiting
                    if (index + 1) % 5 == 0:
                        rate_delay = self.config['bot_behavior'].get('rate_limit_delay', 10)
                        logger.info(f"⏸️ Rate limit pause: {rate_delay}s")
                        time.sleep(rate_delay)
                    else:
                        self.smart_delay(2, 4, probability=0.5)
                    
                except KeyboardInterrupt:
                    logger.info("User interrupted")
                    break
                except Exception as e:
                    logger.error(f"Error with job {index + 1}: {e}")
                    self.failed += 1
                    self.applied_list['failed'].append(job_url)
                    continue
                    
        except Exception as e:
            logger.error(f"Error in apply_to_jobs: {e}")
    
    def _apply_to_single_job(self, job_url):
        """COMPLETE: Apply with all features (Easy Apply + External + proper cleanup)"""
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
                    self._save_job_application(
                        self._extract_job_id(job_url),
                        job_url,
                        "Skipped (Already Applied)"
                    )
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
                    
                    self._handle_chatbot(timeout=3)
                    
                    if self._handle_easy_apply_submission():
                        self._save_job_application(
                            self._extract_job_id(job_url),
                            job_url,
                            "Applied (Easy Apply)",
                            f"{job_title} at {company}"
                        )
                        return True
                    else:
                        logger.warning("Easy Apply submission failed")
                        return False
                        
            except TimeoutException:
                logger.info("No Easy Apply button")
            except Exception as e:
                logger.error(f"Easy Apply error: {e}")
            
            # PRIORITY 2: External Apply
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
                            self.driver.execute_script(f"window.open('{href}', '_blank');")
                        else:
                            external_button.click()
                        
                        self.smart_delay(1, 2, probability=0.5)
                        
                        # PROPER TAB MANAGEMENT
                        if len(self.driver.window_handles) > 1:
                            self.driver.switch_to.window(self.driver.window_handles[-1])
                            self.smart_delay(2, 3, probability=0.5)
                            self.driver.close()  # CLOSE THE TAB!
                            self.driver.switch_to.window(original_tab)
                        
                        logger.info("⬅️ Returned from external site")
                        self.skipped += 1
                        return False
                        
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
            # ENSURE we're back on original tab
            try:
                if original_tab and self.driver.current_window_handle != original_tab:
                    self.driver.switch_to.window(original_tab)
            except:
                pass
    
    def _handle_easy_apply_submission(self):
        """ENHANCED: Submit with adaptive caching"""
        try:
            submit_wait = WebDriverWait(self.driver, 20)
            
            submit_selectors = [
                "button[type='submit']",
                "//button[contains(translate(text(), 'SUBMIT', 'submit'), 'submit')]",
                "//button[@type='submit']",
                "//button[contains(@class, 'submitButton')]",
                "button.submitButton",
                "button#submitButton",
                ".btn-primary[type='submit']",
                "input[type='submit']",
                "button.apply-submit",
                "button.naukri-apply-button",
                ".job-apply-form button[type='submit']"
            ]
            
            submit_button = None
            
            # Try cached selector first
            if self.selector_cache.get('submit_button'):
                try:
                    selector = self.selector_cache['submit_button']
                    by_type = By.XPATH if selector.startswith('//') else By.CSS_SELECTOR
                    
                    submit_button = submit_wait.until(
                        EC.element_to_be_clickable((by_type, selector))
                    )
                    self.performance_stats['cache_hits'] += 1
                    logger.debug("✨ Used cached submit selector")
                except:
                    self.selector_cache['submit_button'] = None
                    self.performance_stats['cache_misses'] += 1
            
            # Try all selectors if cached failed
            if not submit_button:
                for selector in submit_selectors:
                    try:
                        by_type = By.XPATH if selector.startswith('//') else By.CSS_SELECTOR
                        
                        submit_button = submit_wait.until(
                            EC.element_to_be_clickable((by_type, selector))
                        )
                        
                        if submit_button.is_displayed():
                            # Cache this successful selector
                            self.selector_cache['submit_button'] = selector
                            self.save_selector_cache()
                            logger.info(f"✅ Found submit button: {selector}")
                            break
                            
                    except TimeoutException:
                        continue
                    except Exception as e:
                        logger.debug(f"Submit selector {selector} failed: {e}")
                        continue
            
            if not submit_button:
                logger.warning("Could not find submit button")
                return False
            
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});",
                submit_button
            )
            time.sleep(0.5)
            
            try:
                submit_button.click()
            except:
                self.driver.execute_script("arguments[0].click();", submit_button)
            
            logger.info("✅ Submit button clicked")
            self.smart_delay(2, 3, probability=0.5)
            return True
            
        except Exception as e:
            logger.error(f"Error in Easy Apply submission: {e}")
            return False
    
    def _handle_chatbot(self, timeout=3):
        """COMPLETE: Chatbot with Gemini integration (KEPT from original)"""
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
                    
                    # Try keyword answer first (FAST)
                    answer = self._get_keyword_answer(question_text)
                    
                    # Try Gemini if no keyword match
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
                        logger.warning("No answer generated")
                        break
                        
                except NoSuchElementException:
                    break
                except Exception as e:
                    logger.debug(f"Chatbot interaction error: {e}")
                    break
            
            logger.info("Chatbot interaction completed")
            return True
            
        except TimeoutException:
            logger.info("No chatbot detected")
            return False
        except Exception as e:
            logger.error(f"Chatbot handler error: {e}")
            return False
    
    def _get_keyword_answer(self, question):
        """KEPT: Fast keyword-based answering from original"""
        question_lower = question.lower()
        
        keyword_answers = {
            'experience': f"{self.config.get('user_profile', {}).get('experience_years', '3')} years",
            'years': f"{self.config.get('user_profile', {}).get('experience_years', '3')} years",
            'ctc': self.config.get('personal_info', {}).get('current_ctc', '12 LPA'),
            'salary': self.config.get('personal_info', {}).get('current_ctc', '12 LPA'),
            'expected': self.config.get('personal_info', {}).get('expected_ctc', '18 LPA'),
            'notice': self.config.get('personal_info', {}).get('notice_period', '30 days'),
            'notice period': self.config.get('personal_info', {}).get('notice_period', '30 days'),
            'location': self.config.get('job_search', {}).get('location', 'Bengaluru'),
            'phone': self.config.get('personal_info', {}).get('phone', ''),
            'email': self.config.get('credentials', {}).get('email', ''),
            'name': f"{self.config.get('personal_info', {}).get('firstname', '')} {self.config.get('personal_info', {}).get('lastname', '')}",
            'first name': self.config.get('personal_info', {}).get('firstname', ''),
            'last name': self.config.get('personal_info', {}).get('lastname', '')
        }
        
        for keyword, answer in keyword_answers.items():
            if keyword in question_lower:
                return answer
        
        return None
    
    def _get_gemini_answer(self, question):
        """KEPT: Gemini AI integration from original"""
        if not self.gemini_model:
            return None
        
        try:
            user_profile = self.config.get('user_profile', {})
            personal_info = self.config.get('personal_info', {})
            
            context = f"""
            - Name: {user_profile.get('name', 'Candidate')}
            - Experience: {user_profile.get('experience_years', '3')} years
            - Current Role: {user_profile.get('current_role', 'Software Engineer')}
            - Skills: {', '.join(user_profile.get('core_skills', ['Python', 'SQL']))}
            - Current CTC: {personal_info.get('current_ctc', '12 LPA')}
            - Expected CTC: {personal_info.get('expected_ctc', '18 LPA')}
            - Notice Period: {personal_info.get('notice_period', '30 days')}
            """
            
            prompt = f"""Answer this job application chatbot question concisely and professionally.
            Use ONLY the context provided. Keep answer very short (max 5 words).
            
            Context: {context}
            
            Question: "{question}"
            
            Your concise answer:"""
            
            response = self.gemini_model.generate_content(prompt)
            answer = response.text.strip().replace('"', '')
            logger.info(f"Gemini answer: '{answer}'")
            return answer
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return None
    
    def _extract_job_id(self, job_url):
        """KEPT: Extract job ID from URL"""
        try:
            parts = job_url.split('-')
            if parts[-1].isdigit() and len(parts[-1]) > 8:
                return parts[-1]
            return str(abs(hash(job_url)))[-12:]
        except:
            return str(abs(hash(job_url)))[-12:]
    
    def is_job_already_applied(self, job_id):
        """KEPT: Check if job was already applied to"""
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
        """KEPT: Save application to database"""
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
        """ENHANCED: Save comprehensive session results"""
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
                    'success_rate': round((self.applied / max(self.applied + self.failed, 1)) * 100, 2)
                },
                'applications': {
                    'successful': self.applied_list['passed'],
                    'failed': self.applied_list['failed']
                },
                'config_used': {
                    'keywords': self.config['job_search']['keywords'],
                    'location': self.config['job_search']['location'],
                    'max_applications': self.config['job_search'].get('max_applications_per_session'),
                    'pages_per_keyword': self.config['job_search']['pages_per_keyword']
                },
                'performance': self.performance_stats,
                'cached_selectors': len([v for v in self.selector_cache.values() if v])
            }
            
            report_file = os.path.join(self.repo_root, f'naukri_session_{timestamp}.json')
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=4, ensure_ascii=False)
            
            logger.info(f"📊 Session report saved: {report_file}")
            
        except Exception as e:
            logger.error(f"Failed to save results: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        try:
            if self.driver:
                self.driver.quit()
                logger.info("Browser closed")
        except:
            pass
        
        try:
            if self.db_conn:
                self.db_conn.close()
                logger.info("Database closed")
        except:
            pass
    
    def run(self):
        """Main execution method"""
        try:
            print("=" * 60)
            print("🚀 COMPLETE ULTRA-OPTIMIZED NAUKRI BOT")
            print("=" * 60)
            
            if not self.setup_driver():
                logger.error("❌ Failed to setup browser")
                return False
            
            if not self.login():
                logger.error("❌ Failed to login")
                return False
            
            if not self.scrape_job_links():
                logger.warning("⚠️ No jobs found")
            
            if self.joblinks:
                self.apply_to_jobs()
            
            return True
            
        except KeyboardInterrupt:
            logger.info("⚠️ Process interrupted by user")
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
            print(f"📈 Success Rate: {success_rate:.1f}%")
            print(f"💾 Cached Selectors: {len([v for v in self.selector_cache.values() if v])}")
            print(f"⚡ Cache Hits: {self.performance_stats['cache_hits']}")
            print(f"🔄 Cache Misses: {self.performance_stats['cache_misses']}")
            print("=" * 60)
            
            if self.driver:
                try:
                    input("\nPress Enter to close browser...")
                except:
                    pass
                
                try:
                    self.driver.quit()
                except:
                    pass
            
            self.cleanup()


def main():
    """Main entry point"""
    try:
        config_file = 'config.json'
        if not os.path.exists(config_file):
            logger.warning("⚠️ No config file found, creating template...")
        
        bot = NaukriBot(config_file)
        success = bot.run()
        
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())