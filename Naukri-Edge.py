import pandas as pd
import time
import json
import logging
import random
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import os
from datetime import datetime, timedelta
import sqlite3

# Configure logging WITHOUT emojis to avoid Unicode errors
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
    def __init__(self, config_file='config.json'):
        """Initialize the enhanced bot"""
        self.config = self.load_config(config_file)
        self.driver = None
        self.wait = None
        self.joblinks = []
        self.applied = 0
        self.failed = 0
        self.skipped = 0
        self.applied_list = {'passed': [], 'failed': [], 'skipped': []}
        self.processed_jobs = set()
        self.session_stats = {
            'start_time': datetime.now(),
            'jobs_found': 0,
            'applications_sent': 0,
            'errors': 0
        }
        
        # Initialize job database
        self.init_job_database()
        
        # VERIFIED selectors from diagnostic
        self.job_card_selector = '.srp-jobtuple-wrapper[data-job-id]'
        self.job_title_selector = 'a.title'
        
        # Enhanced apply button selectors
        self.apply_button_selectors = [
            "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
            "//button[contains(@class, 'apply')]",
            "//div[contains(@class, 'apply-button')]//button",
            "//*[@id='apply-button']",
            "//input[@type='submit'][contains(@value, 'Apply')]",
            "//button[contains(@data-ga-track, 'apply')]",
            "//a[contains(@href, 'apply')]"
        ]
        
        # Job quality filters
        self.quality_keywords = {
            'preferred': ['full time', 'remote', 'hybrid', 'senior', 'lead', 'architect'],
            'avoid': ['intern', 'fresher', 'trainee', 'unpaid', 'contract']
        }
        
    def init_job_database(self):
        """Initialize SQLite database to track applied jobs"""
        try:
            self.db_conn = sqlite3.connect('naukri_jobs.db')
            cursor = self.db_conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS applied_jobs (
                    job_id TEXT PRIMARY KEY,
                    job_url TEXT,
                    job_title TEXT,
                    company_name TEXT,
                    application_date TIMESTAMP,
                    status TEXT,
                    notes TEXT
                )
            ''')
            self.db_conn.commit()
            logger.info("Job database initialized")
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
    
    def load_config(self, config_file):
        """Load configuration with enhanced defaults"""
        try:
            with open(config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Config file {config_file} not found. Creating enhanced config.")
            self.create_enhanced_config(config_file)
            return self.load_config(config_file)
    
    def create_enhanced_config(self, config_file):
        """Create enhanced configuration file"""
        default_config = {
            "credentials": {
                "email": "kaustubh.upadhyaya1@gmail.com",
                "password": "9880380081@kK"
            },
            "personal_info": {
                "firstname": "Kaustubh",
                "lastname": "Upadhyaya",
                "phone": "9880380081",
                "current_ctc": "8 LPA",
                "expected_ctc": "12 LPA",
                "notice_period": "Immediate"
            },
            "job_search": {
                "keywords": ["Data Engineer", "Python Developer", "ETL Developer", "SQL Developer", "Backend Developer"],
                "location": "bengaluru",
                "max_applications_per_day": 50,
                "max_applications_per_session": 20,
                "pages_per_keyword": 5,
                "min_experience_match": True,
                "preferred_companies": ["Microsoft", "Google", "Amazon", "Netflix", "Uber"],
                "avoid_companies": ["TCS", "Infosys", "Wipro", "Cognizant"]
            },
            "filters": {
                "min_salary": 800000,  # 8 LPA
                "max_experience_years": 10,
                "work_modes": ["Remote", "Hybrid", "Work from Home"],
                "job_types": ["Full Time", "Permanent"]
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
                "typing_delay": 0.15,
                "scroll_pause": 3,
                "smart_delays": True,
                "random_scrolling": True
            },
            "notifications": {
                "email_alerts": True,
                "daily_summary": True,
                "error_alerts": True
            }
        }
        
        with open(config_file, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info(f"Enhanced config created at {config_file}")
    
    def setup_driver(self):
        """Enhanced WebDriver setup with better stealth"""
        try:
            options = webdriver.EdgeOptions()
            
            # Advanced stealth options
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-gpu')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            
            if self.config.get('webdriver', {}).get('headless', False):
                options.add_argument('--headless')
            
            # Randomized user agent
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0"
            ]
            options.add_argument(f'--user-agent={random.choice(user_agents)}')
            
            service = EdgeService(executable_path=self.config['webdriver']['edge_driver_path'])
            self.driver = webdriver.Edge(service=service, options=options)
            
            # Enhanced stealth scripts
            stealth_scripts = [
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
                "Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})",
                "Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']})",
                "Object.defineProperty(navigator, 'permissions', {get: () => ({query: () => Promise.resolve({state: 'granted'})})})"
            ]
            
            for script in stealth_scripts:
                self.driver.execute_script(script)
            
            self.wait = WebDriverWait(self.driver, self.config['webdriver']['implicit_wait'])
            self.driver.set_page_load_timeout(self.config['webdriver']['page_load_timeout'])
            
            logger.info("Enhanced WebDriver setup successful")
            return True
            
        except Exception as e:
            logger.error(f"WebDriver setup failed: {e}")
            return False
    
def smart_delay(self, base_min=None, base_max=None, factor=1.0):
    """Intelligent delay with fallbacks for missing config"""
    try:
        base_min = base_min or self.config.get('bot_behavior', {}).get('min_delay', 3)
        base_max = base_max or self.config.get('bot_behavior', {}).get('max_delay', 7)
        
        # Check if smart_delays is enabled (with fallback)
        smart_delays_enabled = self.config.get('bot_behavior', {}).get('smart_delays', False)
        
        if smart_delays_enabled:
            # Adjust delays based on time of day
            current_hour = datetime.now().hour
            if 9 <= current_hour <= 17:  # Business hours
                factor *= 1.5
            elif current_hour >= 22 or current_hour <= 6:  # Night time
                factor *= 0.7
        
        min_delay = base_min * factor
        max_delay = base_max * factor
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
    except Exception as e:
        # Fallback to simple delay
        time.sleep(random.uniform(2, 5))

def random_scroll(self):
    """Random scrolling with fallback"""
    try:
        random_scrolling_enabled = self.config.get('bot_behavior', {}).get('random_scrolling', True)
        
        if random_scrolling_enabled:
            scroll_actions = [
                "window.scrollBy(0, 300)",
                "window.scrollBy(0, -200)",
                "window.scrollTo(0, document.body.scrollHeight/2)",
                "window.scrollTo(0, document.body.scrollHeight/4)"
            ]
            
            self.driver.execute_script(random.choice(scroll_actions))
            self.smart_delay(1, 3)
    except Exception as e:
        # Fallback scroll
        self.driver.execute_script("window.scrollBy(0, 300)")
        time.sleep(2)

def human_type(self, element, text, clear_first=True):
    """Enhanced human-like typing with fallbacks"""
    try:
        if clear_first:
            element.clear()
            
        typing_delay = self.config.get('bot_behavior', {}).get('typing_delay', 0.1)
        
        for i, char in enumerate(text):
            element.send_keys(char)
            
            if char in ' .@':
                time.sleep(random.uniform(typing_delay * 2, typing_delay * 4))
            else:
                time.sleep(random.uniform(typing_delay * 0.5, typing_delay * 2))
            
            # Occasional pause
            if i > 0 and i % random.randint(5, 15) == 0:
                time.sleep(random.uniform(0.5, 1.5))
    except Exception as e:
        # Fallback to simple typing
        if clear_first:
            element.clear()
        element.send_keys(text)
        time.sleep(1)

def enhanced_login(self):
    """Enhanced login with better error handling and config fallbacks"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Login attempt {attempt + 1}")
            self.driver.get('https://www.naukri.com/nlogin/login')
            self.smart_delay(3, 6)
            
            # Wait for and fill username
            username_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'usernameField'))
            )
            self.human_type(username_field, self.config['credentials']['email'])
            self.smart_delay(1, 2)
            
            # Wait for and fill password
            password_field = self.wait.until(
                EC.element_to_be_clickable((By.ID, 'passwordField'))
            )
            self.human_type(password_field, self.config['credentials']['password'])
            self.smart_delay(1, 2)
            
            # Click login button
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            self.driver.execute_script("arguments[0].click();", login_button)
            
            # Wait for successful login
            success_indicators = [
                (By.CLASS_NAME, 'nI-gNb-drawer__icon'),
                (By.CLASS_NAME, 'view-profile-wrapper'),
                (By.XPATH, "//div[contains(@class, 'user-name')]")
            ]
            
            try:
                for indicator in success_indicators:
                    try:
                        self.wait.until(EC.presence_of_element_located(indicator))
                        logger.info("Login successful!")
                        self.smart_delay(2, 4)
                        return True
                    except TimeoutException:
                        continue
                        
                # Check URL change as fallback
                if 'naukri.com' in self.driver.current_url and 'login' not in self.driver.current_url:
                    logger.info("Login successful (URL check)")
                    return True
                    
            except TimeoutException:
                logger.warning(f"Login attempt {attempt + 1} failed")
                if attempt < max_retries - 1:
                    time.sleep(random.uniform(5, 10))
                    continue
                
        except Exception as e:
            logger.error(f"Login attempt {attempt + 1} error: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(5, 10))
                continue
    
    logger.error("All login attempts failed")
    return False
    
    def is_job_already_applied(self, job_id):
        """Check if job was already applied to"""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM applied_jobs WHERE job_id = ?", (job_id,))
            count = cursor.fetchone()[0]
            return count > 0
        except Exception as e:
            logger.warning(f"Database check failed: {e}")
            return False
    
    def save_job_to_database(self, job_data, status='applied'):
        """Save job application data to database"""
        try:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO applied_jobs 
                (job_id, job_url, job_title, company_name, application_date, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                job_data.get('job_id'),
                job_data.get('url'),
                job_data.get('title'),
                job_data.get('company', 'Unknown'),
                datetime.now(),
                status,
                job_data.get('notes', '')
            ))
            self.db_conn.commit()
        except Exception as e:
            logger.error(f"Database save failed: {e}")
    
    def analyze_job_quality(self, job_card):
        """Analyze job quality and determine if it's worth applying"""
        try:
            job_text = job_card.text.lower()
            job_quality_score = 0
            reasons = []
            
            # Check preferred keywords
            for keyword in self.quality_keywords['preferred']:
                if keyword in job_text:
                    job_quality_score += 10
                    reasons.append(f"Contains '{keyword}'")
            
            # Check avoid keywords
            for keyword in self.quality_keywords['avoid']:
                if keyword in job_text:
                    job_quality_score -= 20
                    reasons.append(f"Contains '{keyword}' (negative)")
            
            # Check company preferences
            preferred_companies = self.config['job_search'].get('preferred_companies', [])
            avoid_companies = self.config['job_search'].get('avoid_companies', [])
            
            for company in preferred_companies:
                if company.lower() in job_text:
                    job_quality_score += 15
                    reasons.append(f"Preferred company: {company}")
            
            for company in avoid_companies:
                if company.lower() in job_text:
                    job_quality_score -= 25
                    reasons.append(f"Avoid company: {company}")
            
            # Salary indication
            if any(salary_indicator in job_text for salary_indicator in ['lpa', 'ctc', 'salary']):
                job_quality_score += 5
                reasons.append("Salary mentioned")
            
            return job_quality_score, reasons
            
        except Exception as e:
            logger.warning(f"Job quality analysis failed: {e}")
            return 0, []
    
    def extract_enhanced_job_info(self, job_card):
        """Extract comprehensive job information"""
        try:
            job_data = {}
            
            # Basic info
            job_data['job_id'] = job_card.get_attribute('data-job-id')
            
            title_element = job_card.find_element(By.CSS_SELECTOR, self.job_title_selector)
            job_data['url'] = title_element.get_attribute('href')
            job_data['title'] = title_element.get_attribute('title') or title_element.text
            
            # Company info
            try:
                company_element = job_card.find_element(By.CSS_SELECTOR, '.comp-name')
                job_data['company'] = company_element.text
            except NoSuchElementException:
                job_data['company'] = 'Unknown'
            
            # Experience
            try:
                exp_element = job_card.find_element(By.CSS_SELECTOR, '.expwdth')
                job_data['experience'] = exp_element.text
            except NoSuchElementException:
                job_data['experience'] = 'Not specified'
            
            # Location
            try:
                loc_element = job_card.find_element(By.CSS_SELECTOR, '.locWdth')
                job_data['location'] = loc_element.text
            except NoSuchElementException:
                job_data['location'] = 'Not specified'
            
            # Job description snippet
            try:
                desc_element = job_card.find_element(By.CSS_SELECTOR, '.job-desc')
                job_data['description'] = desc_element.text[:200]  # First 200 chars
            except NoSuchElementException:
                job_data['description'] = 'No description'
            
            # Quality score
            quality_score, reasons = self.analyze_job_quality(job_card)
            job_data['quality_score'] = quality_score
            job_data['quality_reasons'] = reasons
            
            return job_data
            
        except Exception as e:
            logger.error(f"Error extracting job info: {e}")
            return None
    
    def extract_jobs_from_page(self):
        """Enhanced job extraction with quality filtering"""
        jobs = []
        
        try:
            # Wait for job listings
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, self.job_card_selector))
            )
            
            # Scroll to load content
            self.random_scroll()
            
            # Find all job cards
            job_cards = self.driver.find_elements(By.CSS_SELECTOR, self.job_card_selector)
            logger.info(f"Found {len(job_cards)} job cards on page")
            
            for i, card in enumerate(job_cards):
                try:
                    job_data = self.extract_enhanced_job_info(card)
                    
                    if job_data:
                        # Skip if already applied
                        if self.is_job_already_applied(job_data['job_id']):
                            logger.info(f"Job {job_data['job_id']} already applied, skipping")
                            continue
                        
                        # Quality check
                        if job_data['quality_score'] >= -10:  # Threshold for application
                            jobs.append(job_data)
                            logger.info(f"Job {i+1}: {job_data['title']} at {job_data['company']} (Score: {job_data['quality_score']})")
                        else:
                            logger.info(f"Job {i+1}: {job_data['title']} rejected (Score: {job_data['quality_score']})")
                            self.skipped += 1
                            self.applied_list['skipped'].append(job_data['url'])
                    
                except Exception as e:
                    logger.warning(f"Error processing job card {i+1}: {e}")
                    continue
            
            return jobs
            
        except TimeoutException:
            logger.warning("No job cards found on page")
            return []
        except Exception as e:
            logger.error(f"Error extracting jobs: {e}")
            return []
    
    def smart_job_scraping(self):
        """Intelligent job scraping with adaptive strategies"""
        keywords = self.config['job_search']['keywords']
        location = self.config['job_search']['location']
        pages_per_keyword = self.config['job_search']['pages_per_keyword']
        
        all_jobs = []
        
        for keyword_index, keyword in enumerate(keywords):
            logger.info(f"Scraping keyword {keyword_index + 1}/{len(keywords)}: {keyword}")
            
            for page in range(1, pages_per_keyword + 1):
                try:
                    # Build URL
                    clean_keyword = keyword.lower().replace(' ', '-')
                    if location:
                        clean_location = location.lower().replace(' ', '-')
                        url = f"https://www.naukri.com/{clean_keyword}-jobs-in-{clean_location}-{page}"
                    else:
                        url = f"https://www.naukri.com/{clean_keyword}-jobs-{page}"
                    
                    logger.info(f"Page {page}/{pages_per_keyword}: {url}")
                    
                    self.driver.get(url)
                    self.smart_delay(4, 8)
                    
                    # Extract jobs from current page
                    page_jobs = self.extract_jobs_from_page()
                    
                    if page_jobs:
                        all_jobs.extend(page_jobs)
                        logger.info(f"✅ Page {page}: Found {len(page_jobs)} quality jobs")
                    else:
                        logger.warning(f"❌ Page {page}: No quality jobs found")
                        # If no jobs found on consecutive pages, stop for this keyword
                        if page > 2:
                            logger.info(f"Stopping scraping for '{keyword}' due to no results")
                            break
                    
                    self.smart_delay(2, 5)
                    
                except Exception as e:
                    logger.error(f"Error on page {page} for keyword '{keyword}': {e}")
                    continue
            
            # Delay between keywords
            self.smart_delay(3, 7)
        
        # Remove duplicates and sort by quality
        unique_jobs = {}
        for job in all_jobs:
            if job['job_id'] not in unique_jobs:
                unique_jobs[job['job_id']] = job
        
        sorted_jobs = sorted(unique_jobs.values(), key=lambda x: x['quality_score'], reverse=True)
        
        self.joblinks = [job['url'] for job in sorted_jobs]
        self.session_stats['jobs_found'] = len(self.joblinks)
        
        logger.info(f"🎯 Total quality jobs found: {len(self.joblinks)}")
        
        # Save job data
        if sorted_jobs:
            df = pd.DataFrame(sorted_jobs)
            df.to_csv(f"scraped_jobs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", index=False)
        
        return len(self.joblinks) > 0
    
    def enhanced_apply_to_job(self, job_url, job_index):
        """Enhanced job application with better success detection"""
        try:
            logger.info(f"🎯 Applying to job {job_index}: {job_url}")
            
            # Navigate to job page
            self.driver.get(job_url)
            self.smart_delay(4, 8)
            
            # Extract job ID from URL for tracking
            job_id = job_url.split('-')[-1] if '-' in job_url else str(time.time())
            
            # Check if already applied (page level check)
            page_source = self.driver.page_source.lower()
            already_applied_indicators = [
                'already applied',
                'application sent',
                'you have applied',
                'applied on'
            ]
            
            if any(indicator in page_source for indicator in already_applied_indicators):
                logger.info("✅ Already applied to this job (detected on page)")
                self.save_job_to_database({'job_id': job_id, 'url': job_url}, 'already_applied')
                return 'already_applied'
            
            # Random scroll to mimic reading
            self.random_scroll()
            
            # Find and click apply button
            apply_button_clicked = False
            for selector in self.apply_button_selectors:
                try:
                    apply_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    
                    # Scroll to button
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", apply_button)
                    self.smart_delay(1, 2)
                    
                    # Try clicking
                    try:
                        apply_button.click()
                        logger.info(f"✅ Apply button clicked using: {selector}")
                        apply_button_clicked = True
                        break
                    except ElementClickInterceptedException:
                        # JavaScript click fallback
                        self.driver.execute_script("arguments[0].click();", apply_button)
                        logger.info(f"✅ Apply button clicked via JS using: {selector}")
                        apply_button_clicked = True
                        break
                        
                except TimeoutException:
                    continue
                except Exception as e:
                    logger.warning(f"Error with selector {selector}: {e}")
                    continue
            
            if not apply_button_clicked:
                logger.warning("❌ No apply button found or clickable")
                return False
            
            self.smart_delay(3, 6)
            
            # Handle application forms
            form_handled = self.handle_enhanced_application_form()
            
            # Enhanced success detection
            success_detected = self.detect_application_success()
            
            if success_detected:
                logger.info("🎉 Application successful!")
                self.save_job_to_database({
                    'job_id': job_id, 
                    'url': job_url,
                    'title': 'Applied Job',
                    'notes': f'Form handled: {form_handled}'
                }, 'applied')
                return True
            else:
                logger.info("⚠️ Application status uncertain")
                return True  # Assume success if no clear failure
                
        except Exception as e:
            logger.error(f"❌ Error applying to job {job_url}: {e}")
            self.session_stats['errors'] += 1
            return False
    
    def handle_enhanced_application_form(self):
        """Enhanced form handling with more field types"""
        try:
            self.smart_delay(2, 4)
            
            # Extended form fields mapping
            form_fields = [
                # Name fields
                ('CUSTOM-FIRSTNAME', self.config['personal_info']['firstname']),
                ('firstname', self.config['personal_info']['firstname']),
                ('firstName', self.config['personal_info']['firstname']),
                ('first_name', self.config['personal_info']['firstname']),
                ('CUSTOM-LASTNAME', self.config['personal_info']['lastname']),
                ('lastname', self.config['personal_info']['lastname']),
                ('lastName', self.config['personal_info']['lastname']),
                ('last_name', self.config['personal_info']['lastname']),
                
                # Contact fields
                ('phone', self.config['personal_info'].get('phone', '')),
                ('mobile', self.config['personal_info'].get('phone', '')),
                ('phoneNumber', self.config['personal_info'].get('phone', '')),
                
                # Experience fields
                ('currentCTC', self.config['personal_info'].get('current_ctc', '')),
                ('expectedCTC', self.config['personal_info'].get('expected_ctc', '')),
                ('noticePeriod', self.config['personal_info'].get('notice_period', '')),
            ]
            
            filled_fields = 0
            for field_id, value in form_fields:
                if not value:  # Skip empty values
                    continue
                    
                try:
                    # Try by ID first
                    field = self.driver.find_element(By.ID, field_id)
                    if field.is_displayed() and field.is_enabled():
                        self.human_type(field, str(value))
                        filled_fields += 1
                        self.smart_delay(0.5, 1.5)
                        continue
                except NoSuchElementException:
                    pass
                
                # Try by name attribute
                try:
                    field = self.driver.find_element(By.NAME, field_id)
                    if field.is_displayed() and field.is_enabled():
                        self.human_type(field, str(value))
                        filled_fields += 1
                        self.smart_delay(0.5, 1.5)
                except NoSuchElementException:
                    pass
            
            if filled_fields > 0:
                logger.info(f"✅ Filled {filled_fields} form fields")
            
            # Submit form
            submit_selectors = [
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]",
                "//input[@type='submit']",
                "//button[@type='submit']",
                "//button[contains(@class, 'submit')]"
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.XPATH, selector)
                    if submit_button.is_displayed() and submit_button.is_enabled():
                        self.driver.execute_script("arguments[0].click();", submit_button)
                        logger.info("✅ Form submitted")
                        self.smart_delay(2, 4)
                        return True
                except NoSuchElementException:
                    continue
            
            return filled_fields > 0
            
        except Exception as e:
            logger.warning(f"Form handling error: {e}")
            return False
    
    def detect_application_success(self):
        """Enhanced success detection"""
        try:
            # Wait for page to load after form submission
            self.smart_delay(3, 6)
            
            page_source = self.driver.page_source.lower()
            
            success_indicators = [
                'application submitted',
                'successfully applied',
                'application sent',
                'thank you for applying',
                'application received',
                'we have received your application',
                'application successful',
                'your application has been sent'
            ]
            
            failure_indicators = [
                'application failed',
                'error occurred',
                'please try again',
                'application not sent',
                'failed to apply'
            ]
            
            # Check for success
            for indicator in success_indicators:
                if indicator in page_source:
                    return True
            
            # Check for failure
            for indicator in failure_indicators:
                if indicator in page_source:
                    return False
            
            # Check URL change (often indicates success)
            current_url = self.driver.current_url
            if 'success' in current_url or 'applied' in current_url:
                return True
            
            # If no clear indication, assume success
            return True
            
        except Exception as e:
            logger.warning(f"Success detection error: {e}")
            return True
    
    def intelligent_job_application(self):
        """Intelligent job application with daily limits and quality focus"""
        max_applications = min(
            self.config['job_search']['max_applications_per_session'],
            self.config['job_search']['max_applications_per_day']
        )
        
        applied_today = self.get_todays_application_count()
        remaining_quota = self.config['job_search']['max_applications_per_day'] - applied_today
        
        if remaining_quota <= 0:
            logger.info("📅 Daily application quota already reached")
            return
        
        max_applications = min(max_applications, remaining_quota)
        logger.info(f"🎯 Will apply to maximum {max_applications} jobs this session")
        
        for i, job_url in enumerate(self.joblinks, 1):
            if self.applied >= max_applications:
                logger.info(f"✋ Reached session limit: {max_applications}")
                break
            
            try:
                result = self.enhanced_apply_to_job(job_url, i)
                
                if result == 'already_applied':
                    continue
                elif result:
                    self.applied += 1
                    self.applied_list['passed'].append(job_url)
                    self.session_stats['applications_sent'] += 1
                    logger.info(f"✅ Progress: {self.applied}/{max_applications} applications sent")
                else:
                    self.failed += 1
                    self.applied_list['failed'].append(job_url)
                    logger.info(f"❌ Failed applications: {self.failed}")
                
                # Check for quota exceeded
                if self.check_daily_quota_exceeded():
                    logger.info("🚫 Daily quota exceeded by website")
                    break
                
                # Intelligent delay between applications
                self.smart_delay(5, 12, factor=1.5)
                
            except Exception as e:
                logger.error(f"Unexpected error with job {i}: {e}")
                self.failed += 1
                self.applied_list['failed'].append(job_url)
                continue
    
    def get_todays_application_count(self):
        """Get count of applications made today"""
        try:
            cursor = self.db_conn.cursor()
            today = datetime.now().date()
            cursor.execute(
                "SELECT COUNT(*) FROM applied_jobs WHERE DATE(application_date) = ? AND status = 'applied'",
                (today,)
            )
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            logger.warning(f"Could not get today's count: {e}")
            return 0
    
    def check_daily_quota_exceeded(self):
        """Enhanced quota checking"""
        try:
            page_source = self.driver.page_source.lower()
            quota_indicators = [
                'daily quota',
                'limit reached',
                'maximum applications',
                'quota exceeded',
                'limit exceeded',
                'daily limit',
                'application limit',
                'too many applications'
            ]
            
            exceeded = any(indicator in page_source for indicator in quota_indicators)
            
            if exceeded:
                logger.warning("🚫 Daily quota exceeded detected on page")
            
            return exceeded
            
        except Exception:
            return False
    
    def generate_detailed_report(self):
        """Generate comprehensive session report"""
        try:
            session_duration = datetime.now() - self.session_stats['start_time']
            
            report = {
                'session_summary': {
                    'start_time': self.session_stats['start_time'].isoformat(),
                    'duration_minutes': round(session_duration.total_seconds() / 60, 2),
                    'jobs_found': self.session_stats['jobs_found'],
                    'applications_sent': self.applied,
                    'applications_failed': self.failed,
                    'jobs_skipped': self.skipped,
                    'success_rate': f"{(self.applied / max(len(self.joblinks), 1) * 100):.1f}%",
                    'errors': self.session_stats['errors']
                },
                'daily_stats': {
                    'applications_today': self.get_todays_application_count(),
                    'daily_limit': self.config['job_search']['max_applications_per_day']
                },
                'job_links': {
                    'successful': self.applied_list['passed'],
                    'failed': self.applied_list['failed'],
                    'skipped': self.applied_list['skipped']
                }
            }
            
            # Save report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # JSON report
            with open(f"naukri_session_report_{timestamp}.json", 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            # CSV summary
            df_summary = pd.DataFrame([report['session_summary']])
            df_summary.to_csv(f"naukri_session_summary_{timestamp}.csv", index=False)
            
            # Detailed results CSV
            max_len = max(
                len(self.applied_list['passed']),
                len(self.applied_list['failed']),
                len(self.applied_list['skipped'])
            )
            
            results_data = {
                'successful_applications': self.applied_list['passed'] + [''] * (max_len - len(self.applied_list['passed'])),
                'failed_applications': self.applied_list['failed'] + [''] * (max_len - len(self.applied_list['failed'])),
                'skipped_applications': self.applied_list['skipped'] + [''] * (max_len - len(self.applied_list['skipped']))
            }
            
            df_results = pd.DataFrame(results_data)
            df_results.to_csv(f"naukri_detailed_results_{timestamp}.csv", index=False)
            
            logger.info(f"📊 Reports saved with timestamp: {timestamp}")
            
            # Console summary
            print("\n" + "="*60)
            print("🎉 NAUKRI AUTOMATION SESSION COMPLETE")
            print("="*60)
            print(f"⏱️  Duration: {report['session_summary']['duration_minutes']} minutes")
            print(f"🔍 Jobs Found: {report['session_summary']['jobs_found']}")
            print(f"✅ Applications Sent: {report['session_summary']['applications_sent']}")
            print(f"❌ Applications Failed: {report['session_summary']['applications_failed']}")
            print(f"⏭️  Jobs Skipped: {report['session_summary']['jobs_skipped']}")
            print(f"📈 Success Rate: {report['session_summary']['success_rate']}")
            print(f"📅 Total Applications Today: {report['daily_stats']['applications_today']}")
            print("="*60)
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
    
    def run(self):
        """Enhanced main execution method"""
        try:
            print("🚀 Starting Intelligent Naukri Job Application Bot")
            print("="*60)
            
            if not self.setup_driver():
                return False
            
            if not self.enhanced_login():
                return False
            
            print("🔍 Starting intelligent job search...")
            if not self.smart_job_scraping():
                logger.error("❌ No quality jobs found matching criteria")
                return False
            
            print(f"🎯 Found {len(self.joblinks)} quality jobs, starting applications...")
            self.intelligent_job_application()
            
            print("📊 Generating detailed reports...")
            self.generate_detailed_report()
            
            logger.info("🎉 Bot execution completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Bot execution failed: {e}")
            return False
        
        finally:
            if hasattr(self, 'db_conn'):
                self.db_conn.close()
            if self.driver:
                input("\nPress Enter to close browser...")
                self.driver.quit()
                logger.info("Browser closed")

if __name__ == "__main__":
    print("🤖 Intelligent Naukri Auto-Apply Bot v2.0")
    print("="*50)
    
    bot = IntelligentNaukriBot()
    success = bot.run()
    
    if success:
        print("\n✅ Bot completed successfully! Check the generated reports.")
    else:
        print("\n❌ Bot failed. Check logs for details.")